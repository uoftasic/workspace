#!/usr/bin/env python3
"""Per-layer geometric and label comparison of two cells in two layout files.

Usage:
    python3 compare.py A.gds CELL_A B.gds CELL_B [options]

Each cell is flattened (all child cells are pulled in through a recursive
shape iterator), then compared layer by layer (GDS layer/datatype pairs):

  * polygons, boxes and paths become a pya.Region per layer, and the two
    regions are XORed (merged semantics, so splitting a shape into several
    pieces, or overlapping shapes, is not reported as a difference);
  * texts become a multiset of (string, x, y, attributes) per layer, where
    the attributes are rotation, mirror, size, justification and font, so a
    label that is renamed, moved, duplicated, turned or re-justified is
    reported (``text_attrs=False`` compares string and position only: OASIS
    keeps no text size or justification). KLayout 0.30.11's GDS reader keeps
    no font (every text reads back with font -1), so a font difference in a
    GDS file is invisible here; gds_census.text_fonts reads it from the raw
    records, and the harness compares that too;
  * with ``shape_counts=True`` the number of shapes per layer, unmerged, must
    also match, so a shape inserted twice is reported;
  * bounding boxes are reported in micrometres: the geometry bbox of each
    cell, and per-layer bboxes (printed for layers that differ, all of them
    in the --json output, which also has each cell's own bbox).

Both layouts are brought onto a common database unit first: the largest dbu
that divides both, so the scaling is an exact integer magnification and
nothing is rounded.  Two layouts that hold the same geometry at different
dbu values therefore compare as identical.

Options:
    --tol-um T        ignore XOR slivers.  Each XOR piece is shrunk by
                      h = floor(T / 2 / dbu) database units per side and is
                      dropped if nothing is left, so pieces up to 2h dbu wide
                      are ignored.  strmxor -t T gave the same verdicts for
                      T = 0.010 to 0.020 um on a 15 nm sliver.  Default 0
                      (exact).
    --align MODE      none (default), ll or center: shift B so its geometry
                      bounding box lower-left corner (or centre) lands on A's
                      before comparing, for generators with different origins
    --ignore L/D      skip a layer/datatype pair (repeatable)
    --no-texts        do not compare texts
    --no-text-attrs   compare texts as string and position only
    --shape-counts    also compare the number of unmerged shapes per layer
    --lyp FILE        read layer names from a KLayout .lyp file for the report
    --xor-out FILE    write the XOR geometry and unmatched texts to FILE
    --json FILE       also write the result as JSON to FILE ('-' = stdout)
    --quiet           print only the summary line

Exit status: 0 = identical, 1 = differences found, 2 = error.

From Python: ``compare_cells(file_a, cell_a, file_b, cell_b, *, tol_um=0,
align="none", ignore=(), texts=True, xor_out=None, lyp=None)`` returns the
same dict as ``--json``; ``compare_layouts()`` takes Layout and Cell objects
instead of file names.

Imports 'klayout.db' when it is importable, else 'pya'.  The parity
harness calls compare_cells() from python3 and from scripts run with
'klayout -b -r'; the command line is for python3.
"""

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from fractions import Fraction
from math import floor, gcd

try:
    import klayout.db as db
except ImportError:
    try:
        import pya as db
    except ImportError:
        sys.stderr.write("error: neither 'klayout.db' nor 'pya' is importable\n")
        sys.exit(2)

EXIT_SAME, EXIT_DIFF, EXIT_ERR = 0, 1, 2


class CompareError(Exception):
    pass


def read_layout(path):
    ly = db.Layout()
    try:
        ly.read(path)
    except Exception as e:
        raise CompareError(f"cannot read {path}: {e}")
    return ly


def find_cell(ly, path, name):
    cell = ly.cell(name)
    if cell is None:
        tops = ", ".join(c.name for c in ly.top_cells())
        raise CompareError(f"cell '{name}' not in {path} (top cells: {tops})")
    return cell


def dbu_fraction(dbu):
    # Layout.dbu is a float such as 0.001; go through a short decimal string
    # so 0.001 becomes 1/1000 rather than the binary expansion.
    return Fraction(f"{dbu:.12g}")


def common_dbu(dbu_a, dbu_b):
    """Return (common dbu as Fraction, integer magnification for A, for B)."""
    fa, fb = dbu_fraction(dbu_a), dbu_fraction(dbu_b)
    den = fa.denominator * fb.denominator
    num = gcd(fa.numerator * fb.denominator, fb.numerator * fa.denominator)
    common = Fraction(num, den)
    mag_a, mag_b = fa / common, fb / common
    assert mag_a.denominator == 1 and mag_b.denominator == 1
    return common, int(mag_a), int(mag_b)


def layer_pairs(ly, path, warnings):
    pairs = {}
    for li in ly.layer_indices():
        info = ly.get_info(li)
        if info.layer < 0 or info.datatype < 0:
            warnings.append(f"{path}: skipping layer '{info.name}' (no layer/datatype number)")
            continue
        pairs[(info.layer, info.datatype)] = li
    return pairs


def load_lyp_names(path):
    names = {}
    try:
        root = ET.parse(path).getroot()
    except Exception as e:
        raise CompareError(f"cannot parse {path}: {e}")
    for prop in root.iter("properties"):
        src, name = prop.findtext("source"), prop.findtext("name")
        if not src or not name:
            continue
        spec = src.split("@")[0].strip()
        try:
            l, d = (int(x) for x in spec.split("/"))
        except ValueError:
            continue
        names.setdefault((l, d), name.split(" - ")[0].strip())
    return names


def parse_ld(text):
    try:
        l, d = (int(x) for x in text.split("/"))
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected LAYER/DATATYPE, got '{text}'")
    return (l, d)


def flat_shape_count(cell, li):
    """Shapes other than texts on a layer, flattened and not merged, so a
    shape drawn twice counts twice (the merged XOR can't see it)."""
    if li is None:
        return 0
    n = 0
    it = cell.begin_shapes_rec(li)
    while not it.at_end():
        if not it.shape().is_text():
            n += 1
        it.next()
    return n


def flat_region(cell, li, mag):
    if li is None:
        return db.Region()
    r = db.Region(cell.begin_shapes_rec(li))
    if mag != 1:
        r.transform(db.ICplxTrans(mag))
    r.merge()
    return r


def _enum(v):
    return v.to_i() if hasattr(v, "to_i") else int(v)


def text_attrs(t):
    """Orientation, mirror, size, justification and font of a text, as one
    string (so a label that only turns, scales or re-justifies is reported)."""
    return "r%d%s s%d h%d v%d f%d" % (t.trans.rot * 90, "m" if t.trans.is_mirror() else "",
                                       t.size, _enum(t.halign), _enum(t.valign), t.font)


def flat_texts(cell, li, mag, attrs=True):
    if li is None:
        return Counter()
    out = Counter()
    it = cell.begin_shapes_rec(li)
    tm = db.ICplxTrans(mag)
    while not it.at_end():
        sh = it.shape()
        if sh.is_text():
            t = sh.text.transformed(tm * it.trans())
            out[(t.string, t.x, t.y, text_attrs(t) if attrs else "")] += 1
        it.next()
    return out


def bbox_um(box, unit):
    if box.empty():
        return None
    return [round(box.left * unit, 6), round(box.bottom * unit, 6),
            round(box.right * unit, 6), round(box.top * unit, 6)]


def fmt_bbox(b):
    if b is None:
        return "-"
    return "({:.3f},{:.3f})-({:.3f},{:.3f})".format(*b)


class _Opts:
    def __init__(self, **kw):
        self.file_a = kw.get("file_a", "<layout A>")
        self.file_b = kw.get("file_b", "<layout B>")
        self.tol_um = kw.get("tol_um", 0.0)
        self.align = kw.get("align", "none")
        self.ignore = list(kw.get("ignore") or [])
        self.no_texts = not kw.get("texts", True)
        # False: compare texts as (string, x, y) only.  OASIS has no field
        # for a text's size or justification, so a file saved as OASIS loses
        # them (KLayout 0.30.11).
        self.text_attrs = kw.get("text_attrs", True)
        # False: compare texts as sets, so two identical texts at one
        # position count once (a KLayout 0.30.11 OASIS file keeps one).
        self.text_dupes = kw.get("text_dupes", True)
        self.lyp = kw.get("lyp")
        self.xor_out = kw.get("xor_out")
        # True: also compare the number of (unmerged) shapes per layer.
        self.shape_counts = kw.get("shape_counts", False)


def compare_cells(file_a, cell_a, file_b, cell_b, *, tol_um=0.0, align="none", ignore=(),
                  texts=True, xor_out=None, lyp=None, text_attrs=True, shape_counts=False,
                  text_dupes=True):
    """Compare cell_a in file_a with cell_b in file_b. Raises CompareError."""
    ly_a, ly_b = read_layout(file_a), read_layout(file_b)
    ca = find_cell(ly_a, file_a, cell_a)
    cb = find_cell(ly_b, file_b, cell_b)
    opts = _Opts(file_a=file_a, file_b=file_b, tol_um=tol_um, align=align, ignore=ignore,
                 texts=texts, xor_out=xor_out, lyp=lyp, text_attrs=text_attrs,
                 shape_counts=shape_counts, text_dupes=text_dupes)
    return _compare(ly_a, ca, ly_b, cb, opts)


def compare_layouts(ly_a, cell_a, ly_b, cell_b, *, tol_um=0.0, align="none", ignore=(),
                    texts=True, xor_out=None, lyp=None, name_a="<layout A>", name_b="<layout B>",
                    text_attrs=True, text_dupes=True):
    """Like compare_cells(), for Layout and Cell objects already in memory."""
    opts = _Opts(file_a=name_a, file_b=name_b, tol_um=tol_um, align=align, ignore=ignore,
                 texts=texts, xor_out=xor_out, lyp=lyp, text_attrs=text_attrs,
                 text_dupes=text_dupes)
    return _compare(ly_a, cell_a, ly_b, cell_b, opts)


def compare(args):
    ly_a, ly_b = read_layout(args.file_a), read_layout(args.file_b)
    cell_a = find_cell(ly_a, args.file_a, args.cell_a)
    cell_b = find_cell(ly_b, args.file_b, args.cell_b)
    return _compare(ly_a, cell_a, ly_b, cell_b, args)


def _compare(ly_a, cell_a, ly_b, cell_b, args):
    warnings = []

    common, mag_a, mag_b = common_dbu(ly_a.dbu, ly_b.dbu)
    unit = float(common)  # um per common database unit

    pairs_a = layer_pairs(ly_a, args.file_a, warnings)
    pairs_b = layer_pairs(ly_b, args.file_b, warnings)
    ignore = set(args.ignore or [])
    all_pairs = sorted((set(pairs_a) | set(pairs_b)) - ignore)

    names = load_lyp_names(args.lyp) if args.lyp else {}

    regions = {}
    texts = {}
    for ld in all_pairs:
        ra = flat_region(cell_a, pairs_a.get(ld), mag_a)
        rb = flat_region(cell_b, pairs_b.get(ld), mag_b)
        if args.no_texts:
            ta, tb = Counter(), Counter()
        else:
            ta = flat_texts(cell_a, pairs_a.get(ld), mag_a, args.text_attrs)
            tb = flat_texts(cell_b, pairs_b.get(ld), mag_b, args.text_attrs)
            if not getattr(args, "text_dupes", True):
                ta, tb = Counter(set(ta)), Counter(set(tb))
        if ra.is_empty() and rb.is_empty() and not ta and not tb:
            continue  # layer exists in the file but not under these cells
        regions[ld] = (ra, rb)
        texts[ld] = (ta, tb)

    def geom_bbox(side):
        box = db.Box()
        for ra_rb in regions.values():
            box += ra_rb[side].bbox()
        return box

    bbox_a, bbox_b = geom_bbox(0), geom_bbox(1)
    shift = db.Vector(0, 0)
    if args.align != "none" and not bbox_a.empty() and not bbox_b.empty():
        if args.align == "ll":
            shift = bbox_a.p1 - bbox_b.p1
        else:
            dx2 = (bbox_a.left + bbox_a.right) - (bbox_b.left + bbox_b.right)
            dy2 = (bbox_a.bottom + bbox_a.top) - (bbox_b.bottom + bbox_b.top)
            if dx2 % 2 or dy2 % 2:
                warnings.append("--align center: centre offset is half a database unit; rounded")
            shift = db.Vector(dx2 // 2, dy2 // 2)
        if shift != db.Vector(0, 0):
            t = db.ICplxTrans(shift)
            for ld, (ra, rb) in regions.items():
                regions[ld] = (ra, rb.transformed(t))
            for ld, (ta, tb) in texts.items():
                texts[ld] = (ta, Counter({(s, x + shift.x, y + shift.y, a): n
                                          for (s, x, y, a), n in tb.items()}))
            bbox_b = geom_bbox(1)

    half_tol = 0
    if args.tol_um > 0:
        half_tol = int(floor(args.tol_um / 2 / unit + 1e-9))
        if half_tol == 0:
            warnings.append("--tol-um is below two database units; ignored")

    out_ly = out_cell = None
    if args.xor_out:
        out_ly = db.Layout()
        out_ly.dbu = unit
        out_cell = out_ly.create_cell("XOR")

    layers = []
    n_diff_layers = 0
    for ld in sorted(regions):
        ra, rb = regions[ld]
        ta, tb = texts[ld]
        xor = ra ^ rb
        if half_tol:
            xor = xor.interacting(xor.sized(-half_tol))
        only_a = sorted((ta - tb).elements())
        only_b = sorted((tb - ta).elements())
        counts = None
        if getattr(args, "shape_counts", False):
            counts = (flat_shape_count(cell_a, pairs_a.get(ld)), flat_shape_count(cell_b, pairs_b.get(ld)))
        same = xor.is_empty() and not only_a and not only_b and (counts is None or counts[0] == counts[1])
        if not same:
            n_diff_layers += 1
        area2 = unit * unit
        if ra.is_empty() and not ta:
            status = "only in B"
        elif rb.is_empty() and not tb:
            status = "only in A"
        else:
            status = "same" if same else "DIFF"
        layers.append({
            "layer": f"{ld[0]}/{ld[1]}",
            "name": names.get(ld, ""),
            "status": status,
            "polygons_a": ra.count(), "polygons_b": rb.count(),
            "area_a_um2": round(ra.area() * area2, 6),
            "area_b_um2": round(rb.area() * area2, 6),
            "xor_polygons": xor.count(),
            "xor_area_um2": round(xor.area() * area2, 6),
            "bbox_a_um": bbox_um(ra.bbox(), unit),
            "bbox_b_um": bbox_um(rb.bbox(), unit),
            "xor_bbox_um": bbox_um(xor.bbox(), unit),
            "texts_a": sum(ta.values()), "texts_b": sum(tb.values()),
            "texts_only_a": [[s, round(x * unit, 6), round(y * unit, 6), a] for s, x, y, a in only_a],
            "texts_only_b": [[s, round(x * unit, 6), round(y * unit, 6), a] for s, x, y, a in only_b],
        })
        if counts is not None:
            layers[-1]["shapes_a"], layers[-1]["shapes_b"] = counts
            layers[-1]["shape_counts_differ"] = counts[0] != counts[1]
        if out_cell is not None and not same:
            li = out_ly.layer(ld[0], ld[1])
            out_cell.shapes(li).insert(xor)
            for s, x, y, a in only_a + only_b:
                out_cell.shapes(li).insert(db.Text(s, db.Trans(db.Vector(x, y))))

    result = {
        "a": {"file": args.file_a, "cell": cell_a.name, "dbu_um": ly_a.dbu,
              "cells_below": len(cell_a.called_cells()),
              "geometry_bbox_um": bbox_um(bbox_a, unit),
              "cell_bbox_um": [round(v, 6) for v in
                               (cell_a.dbbox().left, cell_a.dbbox().bottom,
                                cell_a.dbbox().right, cell_a.dbbox().top)]},
        "b": {"file": args.file_b, "cell": cell_b.name, "dbu_um": ly_b.dbu,
              "cells_below": len(cell_b.called_cells()),
              "geometry_bbox_um": bbox_um(bbox_b, unit),
              "cell_bbox_um": [round(v, 6) for v in
                               (cell_b.dbbox().left, cell_b.dbbox().bottom,
                                cell_b.dbbox().right, cell_b.dbbox().top)]},
        "compare_dbu_um": unit, "mag_a": mag_a, "mag_b": mag_b,
        "align": args.align, "shift_b_um": [shift.x * unit, shift.y * unit],
        "tol_um": args.tol_um,
        "texts_compared": not args.no_texts,
        "ignored_layers": [f"{l}/{d}" for l, d in sorted(ignore)],
        "layers": layers,
        "diff_layers": n_diff_layers,
        "identical": n_diff_layers == 0,
        "warnings": warnings,
    }

    if out_ly is not None:
        out_ly.write(args.xor_out)
    return result


def print_report(res, quiet):
    a, b = res["a"], res["b"]
    if not quiet:
        print(f"A: {a['file']} cell {a['cell']} dbu {a['dbu_um']:g} um")
        print(f"B: {b['file']} cell {b['cell']} dbu {b['dbu_um']:g} um")
        if res["mag_a"] != 1 or res["mag_b"] != 1:
            print(f"compared at dbu {res['compare_dbu_um']:g} um "
                  f"(A x{res['mag_a']}, B x{res['mag_b']})")
        if res["shift_b_um"] != [0, 0]:
            print("B shifted by ({:.4f}, {:.4f}) um (--align {})".format(
                *res["shift_b_um"], res["align"]))
        for w in res["warnings"]:
            print(f"warning: {w}")
        print(f"geometry bbox A {fmt_bbox(a['geometry_bbox_um'])}  "
              f"B {fmt_bbox(b['geometry_bbox_um'])}")
        print()
        hdr = (f"{'layer':<8} {'name':<14} {'status':<9} {'polys A/B':>10} "
               f"{'area A um2':>11} {'area B um2':>11} {'xor n':>5} "
               f"{'xor um2':>9} {'texts A/B':>9}")
        print(hdr)
        print("-" * len(hdr))
        for L in res["layers"]:
            print(f"{L['layer']:<8} {L['name'][:14]:<14} {L['status']:<9} "
                  f"{L['polygons_a']:>4}/{L['polygons_b']:<5} "
                  f"{L['area_a_um2']:>11.4f} {L['area_b_um2']:>11.4f} "
                  f"{L['xor_polygons']:>5} {L['xor_area_um2']:>9.4f} "
                  f"{L['texts_a']:>4}/{L['texts_b']:<4}")
            if L["status"] != "same":
                print(f"{'':<8} bbox A {fmt_bbox(L['bbox_a_um'])}  B {fmt_bbox(L['bbox_b_um'])}"
                      f"  xor {fmt_bbox(L['xor_bbox_um'])}")
                for s, x, y, a in L["texts_only_a"]:
                    print(f"{'':<8} text only in A: '{s}' at ({x:.4f}, {y:.4f})")
                for s, x, y, a in L["texts_only_b"]:
                    print(f"{'':<8} text only in B: '{s}' at ({x:.4f}, {y:.4f})")
        print()
    n = len(res["layers"])
    if res["identical"]:
        print(f"IDENTICAL: {n} layers compared, no differences")
    else:
        print(f"DIFFERENT: {res['diff_layers']} of {n} layers differ")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("file_a")
    p.add_argument("cell_a")
    p.add_argument("file_b")
    p.add_argument("cell_b")
    p.add_argument("--tol-um", type=float, default=0.0)
    p.add_argument("--align", choices=["none", "ll", "center"], default="none")
    p.add_argument("--ignore", type=parse_ld, action="append")
    p.add_argument("--no-texts", action="store_true")
    p.add_argument("--no-text-attrs", dest="text_attrs", action="store_false",
                   help="compare texts as string and position only (as for OASIS)")
    p.add_argument("--shape-counts", action="store_true",
                   help="also compare the number of unmerged shapes per layer")
    p.add_argument("--lyp")
    p.add_argument("--xor-out")
    p.add_argument("--json")
    p.add_argument("--quiet", action="store_true")
    p.set_defaults(text_dupes=True)
    args = p.parse_args(argv)
    try:
        res = compare(args)
    except CompareError as e:
        sys.stderr.write(f"error: {e}\n")
        return EXIT_ERR
    print_report(res, args.quiet)
    if args.json:
        text = json.dumps(res, indent=1)
        if args.json == "-":
            print(text)
        else:
            with open(args.json, "w") as f:
                f.write(text + "\n")
    return EXIT_SAME if res["identical"] else EXIT_DIFF


if __name__ == "__main__":
    sys.exit(main())
