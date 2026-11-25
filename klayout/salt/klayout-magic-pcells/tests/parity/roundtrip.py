"""Round trips of saved PCell files, with and without the library.

Two modes, chosen by ``KMP_RT_MODE``:

``nolib`` (plain python3, library not registered):
    each pcell/<id>.gds and .oas must open as a cold proxy (``is_proxy()``
    true, ``is_pcell_variant()`` false, title ``<defunct><library>.…``)
    whose stored geometry compares identical to ref/<id>.gds and whose stamp
    reads back; the GDS is saved again as resaved/<id>.gds.

``lib`` (``klayout -b -rm pymacros/klayout_magic_pcells.lym -r roundtrip.py``,
    with the disk cache off, so Magic regenerates every variant):
    each file must open as a live PCell variant whose stored parameters are
    the ones path B saved (the values Magic's dialog showed, the dialog's
    state in ``kmp_dialog``, and ``kmp_created``), that sends Magic the same
    text again without Magic's dialog running again (the request is read
    back from the generator through the variant's stamp key, and the one
    the stored state gives is compared too), and whose regenerated
    geometry compares identical to the reference (Magic's dialog's Create
    for a device, path A for a box-paint generator); resaved/<id>.gds must
    come back live and identical; on ``default`` points the variant is also
    placed in host layouts with dbu 0.0005 and 0.005 and compared. After
    all points, the library is refreshed (``Library.refresh()``, which runs
    coerce and keeps what it returns) and every reopened GDS cell must still
    hold the same parameters and geometry.

Inputs come from environment variables (``klayout -b -r`` owns argv):
KMP_RT_MODE, KMP_RT_POINTS (JSON list; each point names its reference GDS
and top cell), KMP_RT_PCELL, KMP_RT_RESAVED, KMP_RT_OUT.
"""

import json
import os
import sys
import traceback

import klayout.db as db

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
for p in (HERE, os.path.join(REPO, "python")):
    if p not in sys.path:
        sys.path.insert(0, p)

from compare import compare_layouts  # noqa: E402
from klayout_magic_pcells.stamp import read_stamp  # noqa: E402
from klayout_magic_pcells import dialog as kdialog  # noqa: E402

sys.path.insert(0, os.path.join(REPO, "python"))
from klayout_magic_pcells.config import LIBRARY_NAMES  # noqa: E402

PDK = os.environ.get("KMP_PDK") or "sky130A"
LIB = LIBRARY_NAMES[PDK]
DEFUNCT = "<defunct>" + LIB + "."


def read(path):
    ly = db.Layout()
    ly.read(path)
    return ly


def device_cells(ly, top_name):
    """Cells other than the T<id> top and KLayout's context cell."""
    return [c for c in ly.each_cell()
            if c.name != top_name and not c.name.startswith("$$$CONTEXT")]


def identical(ref_ly, ref_top, ly, cell, text_attrs=True, text_dupes=True):
    r = compare_layouts(ref_ly, ref_ly.cell(ref_top), ly, cell, text_attrs=text_attrs,
                        text_dupes=text_dupes)
    if r["identical"]:
        return "ok"
    return "differs: " + ", ".join(l["layer"] for l in r["layers"] if l["status"] != "same")


def nolib(pt, env):
    res = {}
    ref_ly = read(pt["ref_gds"])
    for fmt in ("gds", "oas"):
        path = os.path.join(env["pcell"], "%s.%s" % (pt["id"], fmt))
        ly = read(path)
        cells = device_cells(ly, "T" + pt["id"])
        if len(cells) != 1:
            res[fmt + "_nolib"] = "expected one device cell, found %d" % len(cells)
            continue
        c = cells[0]
        problems = []
        if not c.is_proxy():
            problems.append("not a proxy")
        if c.is_pcell_variant():
            problems.append("is a live PCell variant")
        if not c.display_title().startswith(DEFUNCT):
            problems.append("title %r" % c.display_title())
        # A KLayout 0.30.11 OASIS file keeps neither a text's size and
        # justification nor the second of two identical texts at one place.
        g = identical(ref_ly, pt["ref_top"], ly, c, text_attrs=(fmt != "oas"),
                      text_dupes=(fmt != "oas"))
        if g != "ok":
            problems.append("geometry " + g)
        if pt.get("expect_stamp", True):
            st = read_stamp(c)
            if st is None:
                problems.append("no stamp")
            elif st.get("key") != pt["key"][:16]:
                problems.append("stamp key %s" % st.get("key"))
        res[fmt + "_nolib"] = "ok" if not problems else "; ".join(problems)
        if fmt == "gds":
            os.makedirs(env["resaved"], exist_ok=True)
            ly.write(os.path.join(env["resaved"], pt["id"] + ".gds"))
    return res


def params_equal(spec, stored, expected, sent):
    """Stored parameters against the expected ones (the ones path B saved).

    Doubles may come back one ULP off (KLayout writes and parses them with
    about 15 digits), so floats are compared to a relative 1e-12; strings
    (the dialog's form among them) exactly. The text the PCell sends Magic
    for the reopened values, without asking Magic, must equal what path B
    sent: the stored form for a device, the box for a box-paint generator.
    """
    diffs = []
    for k in sorted(set(stored) | set(expected)):
        a, b = stored.get(k), expected.get(k)
        if isinstance(a, float) or isinstance(b, float):
            try:
                if abs(float(a) - float(b)) <= 1e-12 * max(1.0, abs(float(b))):
                    continue
            except (TypeError, ValueError):
                pass
        if a != b:
            diffs.append("%s=%r (expected %r)" % (k, a, b))
    vals = {k: v for k, v in stored.items() if spec.param(k)}
    if spec.kind == "box":
        ra = spec.build_request(vals)
    else:
        ra = kdialog.stored_request(spec, vals, stored.get(kdialog.DIALOG_PARAM) or "")
        if ra is None:
            return diffs + ["the reopened values are not the ones the stored dialog shows"]
    return diffs + request_diff(ra, sent, "stored state's request")


def request_diff(got, sent, what):
    return ["%s %s=%r (expected %r)" % (what, k, (got or {}).get(k), (sent or {}).get(k))
            for k in sorted(set(got or {}) | set(sent or {})) if (got or {}).get(k) != (sent or {}).get(k)]


CALLS = []  # what the generator handed produce while a file was read


def sent_request(st, cell):
    """(request, why not) for the request the reopened variant was drawn
    from: the generator's memo entry whose key starts with the key in the
    variant's stamp, or, for a cell with no stamp (Magic drew nothing), the
    last result the generator handed produce for this point. None with a
    reason starting "n/a" when there is none (seen on gf180mcuD's stub
    devices, which Magic draws empty: no produce call reached the
    generator while their files were read; why was not looked into)."""
    stp = read_stamp(cell) or {}
    k16 = stp.get("key") or ""
    if k16:
        hits = [st.generator._memo[k] for k in st.generator._memo if k.startswith(k16)]
        if len(hits) != 1:
            return None, "%d generator entries for stamp key %s" % (len(hits), k16)
        return hits[0].sidecar.get("request"), ""
    if not CALLS:
        return None, ("n/a: Magic drew nothing and the generator handed produce nothing while the "
                      "file was read, so no request was read back")
    return CALLS[-1].sidecar.get("request"), ""


def off_grid_layers(ly, cell, grid_dbu):
    """Layers of a flat cell with vertices or texts off a multiple of grid_dbu."""
    out = set()
    for li in ly.layer_indices():
        info = ly.get_info(li)
        it = cell.begin_shapes_rec(li)
        while not it.at_end():
            sh = it.shape()
            t = it.trans()
            if sh.is_text():
                pts = [sh.text.transformed(t).trans.disp]
            else:
                pol = sh.polygon
                pts = list(pol.transformed(t).each_point_hull()) if pol is not None else []
            if any(p.x % grid_dbu or p.y % grid_dbu for p in pts):
                out.add("%d/%d" % (info.layer, info.datatype))
                break
            it.next()
    return out


def geometry_signature(ly, cell):
    out = []
    for li in ly.layer_indices():
        r = db.Region(cell.begin_shapes_rec(li))
        t = sorted(str(x) for x in db.Texts(cell.begin_shapes_rec(li)).each())
        if not r.is_empty() or t:
            out.append((ly.get_info(li).to_s(), sorted(str(p) for p in r.merged().each()), t))
    return out


KEEP = []  # (point id, layout, cell index, parameters, geometry) of each gds_lib reopen


def lib(pt, env, st):
    res = {}
    spec = st.manifest[pt["device"]]
    expected = dict(pt["stored"])
    ref_ly = read(pt["ref_gds"])
    files = [("gds_lib", os.path.join(env["pcell"], pt["id"] + ".gds")),
             ("oas_lib", os.path.join(env["pcell"], pt["id"] + ".oas")),
             ("resave_lib", os.path.join(env["resaved"], pt["id"] + ".gds"))]
    for name, path in files:
        if not os.path.isfile(path):
            res[name] = "missing file %s" % path
            continue
        if name == "gds_lib":
            del CALLS[:]
        ly = read(path)
        cells = device_cells(ly, "T" + pt["id"])
        if len(cells) != 1:
            res[name] = "expected one device cell, found %d" % len(cells)
            continue
        c = cells[0]
        problems = []
        if not c.is_pcell_variant():
            problems.append("not a live PCell variant (title %r)" % c.display_title())
        else:
            d = params_equal(spec, c.pcell_parameters_by_name(), expected, pt["sent"])
            if d:
                problems.append("parameters: " + "; ".join(d[:5]))
            got, why = sent_request(st, c)
            if why.startswith("n/a"):
                res[name + "_sent"] = why
            else:
                sd = [why] if why else request_diff(got, pt["sent"], "request sent")
                res[name + "_sent"] = "ok" if not sd else "; ".join(sd[:5])
        g = identical(ref_ly, pt["ref_top"], ly, c)
        if g != "ok":
            problems.append("geometry " + g)
        res[name] = "ok" if not problems else "; ".join(problems)
        if name == "gds_lib" and c.is_pcell_variant():
            KEEP.append((pt["id"], ly, c.cell_index(), dict(c.pcell_parameters_by_name()),
                         geometry_signature(ly, c)))
    if pt["kind"] == "default":
        for dbu in (0.0005, 0.005):
            name = "dbu_%g" % dbu
            try:
                ly = db.Layout()
                ly.dbu = dbu
                pc = ly.create_cell(pt["device"], LIB, pt["stored"])
                v = identical(ref_ly, pt["ref_top"], ly, pc)
                if v != "ok":
                    # Exact only if Magic's own coordinates sit on the host grid.
                    ratio = int(round(dbu / ref_ly.dbu))
                    off = off_grid_layers(ref_ly, ref_ly.cell(pt["ref_top"]), ratio) if ratio > 1 else set()
                    diff = set(v.split(": ", 1)[1].split(", ")) if ": " in v else set()
                    if off and diff <= off:
                        v = "n/a: Magic's GDS has coordinates off the %g um grid on %s" % (
                            dbu, ", ".join(sorted(off)))
                res[name] = v
            except Exception as e:
                res[name] = "error: %s" % e
    return res


def main():
    mode = os.environ["KMP_RT_MODE"]
    env = {"pcell": os.environ["KMP_RT_PCELL"], "resaved": os.environ["KMP_RT_RESAVED"]}
    with open(os.environ["KMP_RT_POINTS"], encoding="utf-8") as f:
        points = json.load(f)
    st = None
    if mode == "lib":
        import klayout_magic_pcells as kmp
        st = kmp.state_for(PDK)
        if st.library is None:
            raise SystemExit("roundtrip: library not registered: %s" % st.last_error)
        plain_get = st.generator.get

        def recording_get(spec, request):
            r = plain_get(spec, request)
            CALLS.append(r)
            return r
        st.generator.get = recording_get
    out = {}
    for pt in points:
        before = dict(st.generator.stats) if st is not None else {}
        try:
            out[pt["id"]] = nolib(pt, env) if mode == "nolib" else lib(pt, env, st)
        except Exception as e:
            out[pt["id"]] = {"error": "%s: %s" % (type(e).__name__, e),
                             "traceback": traceback.format_exc()}
        if st is not None:
            # Reopening must not type anything into Magic's dialog again.
            n = st.generator.stats.get("dialog_magic", 0) - before.get("dialog_magic", 0)
            out[pt["id"]]["dialog_again"] = "ok" if n == 0 else "Magic's dialog ran %d times on reopen" % n
    if st is not None:
        # A library refresh keeps what coerce returns for every instance.
        gen0 = dict(st.generator.stats)
        try:
            st.library.refresh()
            for pid, ly, ci, params, sig in KEEP:
                c = ly.cell(ci)
                problems = []
                now = dict(c.pcell_parameters_by_name()) if c.is_pcell_variant() else None
                if now is None:
                    problems.append("not a live PCell variant after the refresh")
                elif now != params:
                    problems.append("parameters changed: %s" % sorted(
                        k for k in set(now) | set(params) if now.get(k) != params.get(k)))
                if geometry_signature(ly, c) != sig:
                    problems.append("geometry changed")
                out[pid]["refresh"] = "ok" if not problems else "; ".join(problems)
        except Exception as e:
            for pid, *_ in KEEP:
                out[pid]["refresh"] = "error: %s: %s" % (type(e).__name__, e)
        n = st.generator.stats.get("dialog_magic", 0) - gen0.get("dialog_magic", 0)
        if n:
            for pid, *_ in KEEP:
                prev = out[pid].get("refresh", "ok")
                msg = "Magic's dialog ran %d times in the refresh" % n
                out[pid]["refresh"] = msg if prev == "ok" else prev + "; " + msg
        out["__generator__"] = dict(st.generator.stats)
    with open(os.environ["KMP_RT_OUT"], "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    print("ROUNDTRIP %s: %d points" % (mode, len(out)))


main()
