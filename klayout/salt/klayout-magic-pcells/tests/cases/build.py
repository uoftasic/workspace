"""Build the 0.6 case suite for one PDK (design-0.6.md 5.1; tests/cases/README.md).

    python3 tests/cases/build.py --pdk P --out DIR [--set S]... [--no-pcell] [--magic-row]

Writes the GDS files and DIR/cases.json. Every layout is drawn here with
klayout.db; nothing binary is in the repository. The sets:

  gaps         the GAPS one-change cases, each with the rule it targets
  hier         implants, well, and both moved into a parent cell, and the flat original
               (design-0.6.md 3.1)
  whole_shape  a long well whose rule looks across the whole shape (design-0.6.md 3.1)
  names        cell names Magic renames or can't load, one minimal error each
               (design-0.6.md 2.2)
  inverters    the hand-drawn inverter, broken variants, a schematic for each,
               and the PCell inverter (needs the plugin and Magic; --no-pcell skips it)
  controls     the negative controls of design-0.6.md 3.3: seven standard cells
               copied from libs.ref, a placed row of them, and the inputs of the
               Magic-written row (needs PDK_ROOT)
  sheet        the gaps cases as D<case> subcells 40 um apart (design-0.6.md 3.1)

--magic-row also runs magic_row.tcl, so that Magic writes the row (needs Magic).
"""

import argparse
import importlib
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
for p in (REPO, os.path.join(REPO, "python"), os.path.join(REPO, "tests", "parity")):
    if p not in sys.path:
        sys.path.insert(0, p)

import klayout.db as db  # noqa: E402

from tests.cases import common  # noqa: E402
from tests.cases.common import Drawing, case, new_layout, safe_cell_name, write_gds  # noqa: E402

SETS = ("gaps", "hier", "whole_shape", "names", "inverters", "controls", "sheet")
MODULES = {"sky130A": "pdk_sky130a", "gf180mcuD": "pdk_gf180mcud",
           "ihp-sg13g2": "pdk_sg13g2", "ihp-sg13cmos5l": "pdk_sg13cmos5l"}
MAGIC_ROW_TCL = os.path.join(HERE, "magic_row.tcl")

# The review's names (design-0.6.md 2.2): names KLayout writes and Magic renames, refuses
# or misreads
CELL_NAMES = ["inv$1", "a.b", "a b", "a-b", "x/y", "brace{1}", "br[0]", "UPPER", "upper", "n" * 120,
              "café", "semi;colon"]
# What Magic's plain `load <name>` and a check did with each on sky130A (measured in the
# image; design-0.6.md 2.2)
NAMES_MAGIC = {"a.b": "load raised an error", "x/y": "Magic loaded a new empty cell y: 0 errors",
               "a b": "read as a$b; load made a new empty cell: 0 errors",
               "br[0]": "load raised nothing and the previous cell stayed loaded",
               "café": "read as caf$$; load raised nothing and the previous cell stayed loaded",
               "does_not_exist": "'Cell does_not_exist couldn't be read', 'Creating new cell'; mdrc.tcl printed MDRC_DONE 0"}

_RULE_IN_PARENS = re.compile(r"\(([^()]*)\)")
_RULE_ID = re.compile(r"(?<![\w.])([A-Za-z][A-Za-z0-9_]*(?:/[A-Za-z][A-Za-z0-9_]*)?\.[0-9]+[A-Za-z0-9_]*)")


def pdk_module(pdk):
    if pdk not in MODULES:
        raise SystemExit("unknown PDK %s (one of %s)" % (pdk, ", ".join(MODULES)))
    return importlib.import_module("tests.cases." + MODULES[pdk])


def targets_from(text):
    """Rule IDs named inside the parentheses of a case description."""
    out = []
    for inner in _RULE_IN_PARENS.findall(text):
        for rid in _RULE_ID.findall(inner):
            if rid not in out:
                out.append(rid)
    return out


def _drawing(mod):
    return mod.Cell() if hasattr(mod, "Cell") else Drawing(mod.LAYERS)


def _draw_into(mod, draw, ly, name):
    d = _drawing(mod)
    draw(d)
    return d.emit(ly, ly.create_cell(name))


def _write_one(mod, draw, out, rel, top):
    ly = new_layout()
    cell = _draw_into(mod, draw, ly, top)
    write_gds(ly, os.path.join(out, rel), cell)
    return cell


def _targets(mod, name, desc):
    """The rule IDs a gaps case targets: the module's RULE_OF where it names
    the case (the test's rule on ihp-sg13g2, u_angle.poly on
    ihp-sg13cmos5l), the variant's name on ihp-sg13cmos5l, else the IDs in
    the description's parentheses. A control targets nothing."""
    if "control" in desc:
        return []
    rule_of = getattr(mod, "RULE_OF", {})
    if name in rule_of:
        return [r for r in rule_of[name].split("/") if r != "-"]
    if name.endswith("_ok") and name[:-3] in rule_of:
        return []
    m = re.match(r"^[mu]_(.+)$", name)
    if m and mod.PDK == "ihp-sg13cmos5l":
        return [m.group(1)]
    return targets_from(desc)


# ---------------------------------------------------------------- sets
def build_gaps(mod, out, records):
    expect = common.load_expect(mod.PDK)
    sources = getattr(mod, "SOURCES", {})
    files = []
    for name, desc, draw, control in mod.CASES:
        top = safe_cell_name(name)
        rel = "gaps/%s.gds" % top
        _write_one(mod, draw, out, rel, top)
        files.append((top, rel))
        if records is None:
            continue
        exp = expect.get(name, {})
        notes = desc
        if control:
            notes += "; control: %s" % control
        records.append(case(name, top, "gaps", rel, targets=_targets(mod, name, desc), expect=exp,
                            notes=notes, source=sources.get(name, mod.SOURCE), control=control))
    return files


def build_hier(mod, out, records):
    spec = mod.HIER
    draws = dict((n, d) for n, _, d, _ in mod.CASES)
    draws.update(getattr(mod, "HIER_BASE_DRAW", {}))
    gate = set(spec.get("gate", ()))
    for base in spec["base"]:
        rel = "hier/%s.gds" % base
        _write_one(mod, draws[base], out, rel, base)
        drc, devs = spec["expect"][base]
        records.append(case(base + "_flat", base, "hier", rel,
                            expect={"magic": {"drc(full)": drc, "extract": devs}},
                            notes="the flat original of the two-level cases",
                            source="the review's two-level cells, design-0.6.md 3.1"))
        for grp, lds in spec["groups"].items():
            parent_name, child_name = "%s_%s_h" % (base, grp), "%s_%s_dev" % (base, grp)
            if parent_name not in spec["expect"]:
                continue
            ly = new_layout()
            flat = _draw_into(mod, draws[base], ly, base)
            parent, _ = common.split_hierarchy(ly, flat, parent_name, child_name, lds)
            rel = "hier/%s.gds" % parent_name
            write_gds(ly, os.path.join(out, rel), parent)
            drc, devs = spec["expect"][parent_name]
            what = {"imp": "the implants", "psd": "pSD", "nw": "the well",
                    "all": "the implants, the well and the markers"}[grp]
            notes = ("%s drawn in the parent %s over the rest in %s at the origin; layers %s"
                     % (what, parent_name, child_name, " ".join("%d/%d" % ld for ld in lds)))
            if gate and parent_name not in gate:
                notes += "; Magic reported no DRC error on this one, so it is not a gate case"
            records.append(case(parent_name, parent_name, "hier", rel,
                                expect={"magic": {"drc(full)": drc, "extract": devs}}, notes=notes,
                                source="the review's two-level cells, design-0.6.md 3.1", moved=[list(x) for x in lds],
                                child=child_name))


def build_whole_shape(mod, out, records):
    for spec in mod.WHOLE_SHAPE:
        rel = "whole_shape/%s.gds" % spec["name"]
        _write_one(mod, spec["draw"], out, rel, spec["name"])
        records.append(case(spec["name"], spec["name"], "whole_shape", rel, targets=spec["targets"],
                            expect=spec["expect"], notes=spec["notes"], source=spec["source"], box=spec["box"],
                            measured=spec.get("measured", {})))


def build_names(mod, out, records):
    layer, b, rule = mod.NAMES_ERROR
    ly = new_layout()
    top = ly.create_cell("NTOP")
    li = ly.layer(*mod.LAYERS[layer])
    for i, n in enumerate(CELL_NAMES):
        c = ly.create_cell(n)
        c.shapes(li).insert(db.DBox(*b))
        top.insert(db.DCellInstArray(c.cell_index(), db.DTrans(db.DVector(i * 5.0, 0))))
    rel = "names/names.gds"
    write_gds(ly, os.path.join(out, rel), top)
    # KLayout's GDS writer itself rewrites some names ("a b" is written as "a$b",
    # "caf\u00e9" as "caf$$"), so each case's top is the name in the file, found by position.
    back = common.read_back(os.path.join(out, rel))
    in_file = {round(i.dtrans.disp.x / 5.0): back.cell(i.cell_index).name for i in back.cell("NTOP").each_inst()}
    measured = mod.PDK == "sky130A"
    width = b[2] - b[0]
    for i, n in enumerate(CELL_NAMES + ["does_not_exist"]):
        exp = {}
        if measured:
            exp = {"magic_plain_load": NAMES_MAGIC.get(n, "the right cell, 1 error (%s)" % rule)}
        top_name = in_file.get(i, n)
        notes = ("not in the file: a job must fail (exit 2), never report clean" if n == "does_not_exist" else
                 "one %s box %.2f um wide (%s); the export must rename the cell if its name is not "
                 "[A-Za-z0-9_$]+, and the check must find the one error" % (layer, width, rule))
        if top_name != n:
            notes += "; KLayout's GDS writer wrote the name %r as %r" % (n, top_name)
        records.append(case("name_%02d" % i, top_name, "names", rel,
                            targets=[rule] if n != "does_not_exist" else [], expect=exp, notes=notes,
                            source="the review's cell names, design-0.6.md 2.2 and 6.5",
                            klayout_name=n))


def build_inverters(mod, out, records, pcell=True):
    for name, draw, notes, exp, source in mod.inverter_variants():
        rel = "inverters/%s.gds" % name
        _write_one(mod, draw, out, rel, name)
        sch = "inverters/%s.spice" % name
        with open(os.path.join(out, sch), "w", encoding="utf-8") as f:
            f.write(mod.SCHEMATIC.format(top=name, **mod.SCH_W))
        records.append(case(name, name, "inverters", rel, expect=exp, notes=notes,
                            source=source or "new in 0.6 (no GAPS measurement)", schematic=sch))
    if not pcell:
        return None
    try:
        import klayout_magic_pcells as kmp
        kmp.register(mod.PDK)
        ly = new_layout()
        top = mod.pcell_inverter(db, ly)
        rel = "inverters/inv_pcell.gds"
        write_gds(ly, os.path.join(out, rel), top)
    except Exception as e:   # the plugin or Magic is missing: say so, build the rest
        return "inv_pcell not built: %s: %s" % (type(e).__name__, e)
    sch = "inverters/inv_pcell.spice"
    with open(os.path.join(out, sch), "w", encoding="utf-8") as f:
        f.write(mod.SCHEMATIC.format(top="inv_pcell", **mod.PCELL_SCH_W))
    exp, source = mod.PCELL_EXPECT
    records.append(case("inv_pcell", "inv_pcell", "inverters", rel, expect=exp,
                        notes="the inverter from the plugin's PCells, wired at the top level",
                        source=source, schematic=sch))
    return None


def lef_widths(lef_path, names):
    """{cell: width um} from the LEF's MACRO ... SIZE w BY h lines."""
    widths, cur = {}, None
    with open(lef_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            t = line.split()
            if len(t) >= 2 and t[0] == "MACRO":
                cur = t[1]
            elif len(t) >= 4 and t[0] == "SIZE" and cur in names:
                widths[cur] = float(t[1])
    return widths


def build_controls(mod, out, records, env=os.environ):
    root = env.get("PDK_ROOT")
    lib = mod.CONTROLS["lib"]
    libdir = os.path.join(root or "", mod.PDK, "libs.ref", lib)
    gds = os.path.join(libdir, "gds", lib + ".gds")
    if not root or not os.path.exists(gds):
        return "controls not built: %s not found (PDK_ROOT=%s)" % (gds, root)
    cells = mod.CONTROLS["cells"]
    ly = db.Layout()
    ly.read(gds)
    missing = [c for c in cells if ly.cell(c) is None]
    if missing:
        return "controls not built: %s has no %s" % (gds, ", ".join(missing))
    src = "the review's negative controls, design-0.6.md 3.3 and 6.2"
    for c in cells:
        rel = "controls/%s.gds" % c
        write_gds(ly, os.path.join(out, rel), ly.cell(c))
        records.append(case(c, c, "controls", rel, notes="copied from libs.ref/%s/gds; must give no F1 to F4 "
                            "finding" % lib, source=src, negative_control=True))
    widths = lef_widths(os.path.join(libdir, "lef", lib + ".lef"), set(cells))
    xs, x = [], 0.0
    row = ly.create_cell("row")
    for c in cells:
        xs.append(round(x, 4))
        row.insert(db.DCellInstArray(ly.cell(c).cell_index(), db.DTrans(db.DVector(x, 0))))
        x += widths[c]
    rel = "controls/row.gds"
    write_gds(ly, os.path.join(out, rel), row)
    records.append(case("row", "row", "controls", rel,
                        notes="the seven cells abutted in one row, each origin at the sum of the LEF widths "
                              "before it; must give no F1 to F4 finding", source=src, negative_control=True,
                        x_um=xs))
    mag = os.path.join(libdir, "mag")
    inputs = {"cells": cells, "x_um": xs, "top": "row_magic",
              "mag_dir": mag if os.path.isdir(mag) else None,
              "gds": [] if os.path.isdir(mag) else ["controls/%s.gds" % c for c in cells]}
    records.append(case("row_magic", "row_magic", "controls", "controls/row_magic.gds",
                        notes="the same row placed by Magic (magic_row.tcl) from %s and written by Magic's gds "
                              "write; it stands in for the course's Magic-written datapath. The file exists "
                              "only after run_magic_row()" % ("libs.ref/%s/mag" % lib if inputs["mag_dir"]
                                                              else "the copied cells' GDS (the library has no mag/)"),
                        source=src, negative_control=True, magic_row=inputs))
    records.append(case("inv_control", "inv", "controls", "inverters/inv.gds",
                        notes="the PDK's clean hand-drawn inverter (the inverters set's inv) as a negative control",
                        source=src, negative_control=True))
    return None


def run_magic_row(pdk, out, rec, env=None, timeout=600):
    """Have Magic place and write the row of ``rec`` (the row_magic record).
    Returns the GDS path; raises RuntimeError when Magic fails."""
    inp = rec["magic_row"]
    out = os.path.abspath(out)
    e = dict(os.environ if env is None else env)
    root = e["PDK_ROOT"]
    e.update({"PDK": pdk, "KMP_ROW_TOP": inp["top"], "KMP_ROW_CELLS": " ".join(inp["cells"]),
              "KMP_ROW_X": " ".join("%g" % x for x in inp["x_um"]),
              "KMP_ROW_MAG": inp["mag_dir"] or "",
              "KMP_ROW_GDS": " ".join(os.path.join(out, g) for g in inp["gds"]),
              "KMP_OUT": os.path.join(out, rec["file"])})
    rc = os.path.join(root, pdk, "libs.tech", "magic", pdk + ".magicrc")
    p = subprocess.run([shutil.which("magic") or "magic", "-dnull", "-noconsole", "-rcfile", rc, MAGIC_ROW_TCL],
                       env=e, cwd=out, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       timeout=timeout, universal_newlines=True)
    with open(os.path.join(out, "controls", "row_magic.log"), "w", encoding="utf-8") as f:
        f.write(p.stdout)
    if "ROW_DONE" not in p.stdout or not os.path.exists(e["KMP_OUT"]):
        raise RuntimeError("magic_row.tcl failed (log controls/row_magic.log):\n" + p.stdout[-2000:])
    ly = common.read_back(e["KMP_OUT"])
    top = ly.cell(inp["top"])
    placed = sorted((ly.cell(i.cell_index).name, round(i.dcplx_trans.disp.x, 4)) for i in top.each_inst()) if top else []
    want = sorted(zip(inp["cells"], inp["x_um"]))
    if placed != want:
        raise RuntimeError("Magic's row %s does not hold the cells at the x positions asked for: %s, not %s"
                           % (e["KMP_OUT"], placed, want))
    return e["KMP_OUT"]


def build_sheet(mod, out, records, gaps_files):
    import sheet
    rel = "sheet/sheet.gds"
    path = os.path.join(out, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    entries = [(top, os.path.join(out, f), top) for top, f in gaps_files]
    placed, errors = sheet.build_sheet(entries, path, top_name="SHEET")
    if errors:
        raise RuntimeError("sheet: %s" % errors)
    ly = common.read_back(path)          # rewrite without timestamps, as the export writes
    write_gds(ly, path, ly.cell("SHEET"))
    records.append(case("sheet", "SHEET", "sheet", rel,
                        notes="the %d gaps cases as D<case> cells, %g um apart (placement in sheet.gds.json); "
                              "Magic loses errors on such sheets (GAPS-sky130A 2.4), so expect stays per case"
                              % (len(entries), sheet.GAP_UM),
                        source="design-0.6.md 5.1; GAPS-sky130A 2.4", cases=[t for t, _ in gaps_files]))


def build(pdk, out, sets=None, pcell=True, magic_row=False, env=os.environ):
    """Build ``sets`` (all by default) into ``out``; returns (records, warnings)."""
    mod = pdk_module(pdk)
    sets = list(sets or SETS)
    for s in sets:
        if s not in SETS:
            raise SystemExit("unknown set %s (one of %s)" % (s, ", ".join(SETS)))
    os.makedirs(out, exist_ok=True)
    for d in sets + (["gaps"] if "sheet" in sets else []):
        os.makedirs(os.path.join(out, d), exist_ok=True)
    os.makedirs(os.path.join(out, "inverters"), exist_ok=True)
    records, warnings = [], []
    gaps_files = None
    if "gaps" in sets:
        gaps_files = build_gaps(mod, out, records)
    if "hier" in sets:
        build_hier(mod, out, records)
    if "whole_shape" in sets:
        build_whole_shape(mod, out, records)
    if "names" in sets:
        build_names(mod, out, records)
    if "inverters" in sets:
        warnings.append(build_inverters(mod, out, records, pcell=pcell))
    if "controls" in sets:
        if "inverters" not in sets:
            build_inverters(mod, out, [], pcell=False)
        warnings.append(build_controls(mod, out, records, env=env))
        if magic_row and warnings[-1] is None:
            rec = next(r for r in records if r["name"] == "row_magic")
            run_magic_row(pdk, out, rec, env=env)
    if "sheet" in sets:
        if gaps_files is None:
            gaps_files = build_gaps(mod, out, None)
        build_sheet(mod, out, records, gaps_files)
    names = [r["name"] for r in records]
    dup = sorted(set(n for n in names if names.count(n) > 1))
    if dup:
        raise RuntimeError("duplicate case names: %s" % dup)
    # A build of some sets keeps the other sets' records of an earlier build in the same folder.
    path = os.path.join(out, "cases.json")
    kept, kept_sets = [], []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            old = json.load(f)
        if old.get("pdk") == pdk:
            kept = [r for r in old.get("cases", []) if r["set"] not in sets]
            kept_sets = [s for s in old.get("sets", []) if s not in sets]
    all_sets = [s for s in SETS if s in sets or s in kept_sets]
    doc = {"schema": 1, "pdk": pdk, "sets": all_sets, "anchors": mod.ANCHORS,
           "cases": sorted(kept + records, key=lambda r: SETS.index(r["set"]))}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1, ensure_ascii=False)
        f.write("\n")
    return records, [w for w in warnings if w]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--pdk", required=True, choices=sorted(MODULES))
    ap.add_argument("--out", required=True)
    ap.add_argument("--set", action="append", dest="sets", choices=SETS)
    ap.add_argument("--no-pcell", action="store_true", help="skip the PCell inverter (it needs Magic)")
    ap.add_argument("--magic-row", action="store_true", help="have Magic write controls/row_magic.gds")
    a = ap.parse_args(argv)
    records, warnings = build(a.pdk, a.out, a.sets, pcell=not a.no_pcell, magic_row=a.magic_row)
    counts = {}
    for r in records:
        counts[r["set"]] = counts.get(r["set"], 0) + 1
    print("CASES %s %s" % (a.pdk, " ".join("%s=%d" % kv for kv in sorted(counts.items()))))
    for w in warnings:
        print("WARNING " + w)
    return 0


if __name__ == "__main__":
    sys.exit(main())
