"""Audit a layout file for this package's cells without registering a library.

A cell belongs to a PDK by its title, ``<defunct><library>.<device>`` (the
library names are in config.LIBRARY_NAMES), not by its cell name: rm1 is a
device of three PDKs.

Reports cells that hold a placeholder, cells with no stamp, empty cells,
stamps from a different Magic or PDK than the installed one (including a
locally edited generator file or vendor GDS, through the stamp's digest), a
file dbu that doesn't divide 5 nm, and cells whose Magic output lies on a
finer grid than the file's dbu (vendor cells with 1 nm coordinates in a
5 nm file, a box-paint cell on Magic's 5 nm grid in a 2 nm file). The grid
of each cell's Magic output is in its generated-by stamp; for stamps
written before version 0.4, which have none, the manifest's grid of the
device's default output stands in. With ``regen=True`` it keeps a copy of every cell's stored
geometry, registers the libraries those cells need with every lookup going
to Magic (not to the memo or the disk cache), and reports each cell whose
regenerated geometry differs as a problem. A disk-cache entry that differs
from what Magic generates now is reported too, and replaced.
"""

from fractions import Fraction

from .config import LIBRARY_NAMES
from .pcell import PLACEHOLDER_LAYER
from .stamp import describe, read_stamp, same_versions

PDK_OF_LIBRARY = {lib: pdk for pdk, lib in LIBRARY_NAMES.items()}
# Kept for code written against version 0.2.
DEFUNCT = "<defunct>%s." % LIBRARY_NAMES["sky130A"]


def _divides(dbu, grid_um=0.005):
    q = Fraction(str(grid_um)) / Fraction("%.12g" % dbu)
    return q.denominator == 1


def device_of(cell_name):
    """'sky130_fd_pr__nfet_01v8__kmp_3f9a12c4' -> 'sky130_fd_pr__nfet_01v8'."""
    return cell_name.split("__kmp_")[0]


def owner(title):
    """(pdk, library, device) for a title '<defunct>LIB.device(...)', else None."""
    if not title.startswith("<defunct>"):
        return None
    rest = title[len("<defunct>"):]
    lib, _, dev = rest.partition(".")
    if lib not in PDK_OF_LIBRARY:
        return None
    return PDK_OF_LIBRARY[lib], lib, dev.split("(")[0]


def _grid_problem(manifest, device, dbu, stamp=None):
    """A message if the cell's Magic output has coordinates on a grid that
    the file's dbu can't hold: the grid recorded in the cell's stamp, else
    (an older stamp) the grid of the device's default output from the
    manifest."""
    grid, what = None, "this cell's Magic output"
    try:
        grid = int((stamp or {}).get("grid") or 0) or None
    except ValueError:
        grid = None
    if grid is None:
        spec = manifest.get(device) if manifest is not None else None
        grid = spec.raw.get("defaults_run", {}).get("grid_nm") if spec is not None else None
        what = "Magic's output for this device at its defaults (the stamp records no grid)"
    if not grid or _divides(dbu, grid / 1000.0):
        return None
    return ("%s has coordinates on a %d nm grid, which the file's dbu of %g um rounds"
            % (what[0].upper() + what[1:], grid, dbu))


def _snapshot(layout, cell):
    from ._kl import db
    ly = db.Layout()
    ly.dbu = layout.dbu
    c = ly.create_cell(cell.name)
    for li in layout.layer_indices():
        info = layout.get_info(li)
        it = cell.begin_shapes_rec(li)
        if not it.at_end():
            c.shapes(ly.layer(info.layer, info.datatype)).insert(it)
    return ly, c


def _diff_layers(ly_a, cell_a, ly_b, cell_b):
    """Layers whose flattened geometry or texts differ (same dbu assumed)."""
    from ._kl import db
    pairs = {}
    for ly, c, side in ((ly_a, cell_a, 0), (ly_b, cell_b, 1)):
        for li in ly.layer_indices():
            info = ly.get_info(li)
            pairs.setdefault((info.layer, info.datatype), [None, None])[side] = (ly, c, li)
    out = []
    for ld in sorted(pairs):
        if ld == PLACEHOLDER_LAYER:
            continue
        regs, txts = [], []
        for item in pairs[ld]:
            if item is None:
                regs.append(db.Region())
                txts.append([])
                continue
            ly, c, li = item
            regs.append(db.Region(c.begin_shapes_rec(li)))
            txts.append(sorted((t.string, t.x, t.y) for t in db.Texts(c.begin_shapes_rec(li)).each()))
        if not (regs[0] ^ regs[1]).is_empty() or txts[0] != txts[1]:
            out.append("%d/%d" % ld)
    return out


def _gds_diff(path_a, path_b):
    """Layers on which two single-top-cell GDS files differ."""
    from ._kl import db
    la, lb = db.Layout(), db.Layout()
    la.read(path_a)
    lb.read(path_b)
    return _diff_layers(la, la.top_cells()[0], lb, lb.top_cells()[0])


def current_stamps(pdks, notes=None):
    """{pdk: parsed stamp of the installed Magic and PDK}, starting each
    PDK's Magic once; a PDK that can't start is left out (with a note)."""
    from .backend import MagicServer
    from .config import Config
    from .manifest import Manifest
    from .stamp import make_stamp, parse_stamp
    out = {}
    for pdk in pdks:
        try:
            cfg = Config.load(pdk=pdk)
            man = Manifest.load(cfg.manifest)
            s = MagicServer(cfg, vendor_cells=man.vendor_cells())
            try:
                out[pdk] = parse_stamp(make_stamp(s.start()))
            finally:
                s.close()
        except Exception as e:
            if notes:
                notes("note: cannot start Magic for %s to read the installed versions (%s)" % (pdk, e))
    return out


def audit(path, current=None, regen=False, manifests=None, notes=None):
    """Return a dict report.

    ``current`` is {pdk: parsed stamp} (read from the installed Magic when
    None), ``manifests`` {pdk: Manifest} (for the per-device coordinate
    grid; loaded when None). ``notes`` is called with messages about what
    couldn't be checked."""
    from ._kl import db
    ly = db.Layout()
    ly.read(path)
    rep = {"file": path, "dbu": ly.dbu, "dbu_divides_5nm": _divides(ly.dbu), "cells": []}
    cells = []
    for c in ly.each_cell():
        o = owner(c.display_title())
        if o is not None:
            cells.append((c, o))
    pdks = sorted({o[0] for _, o in cells})
    if current is None:
        current = current_stamps(pdks, notes)
    if manifests is None:
        from .config import Config
        from .manifest import Manifest
        manifests = {}
        for pdk in pdks:
            try:
                manifests[pdk] = Manifest.load(Config.load(pdk=pdk).manifest)
            except Exception as e:
                if notes:
                    notes("note: cannot read the %s manifest (%s); the coordinate grid isn't checked"
                          % (pdk, e))
    snaps = {}
    ph = ly.find_layer(*PLACEHOLDER_LAYER)
    # Cell objects of cold proxies don't survive registration; their
    # indices do.
    indices = [c.cell_index() for c, _ in cells]
    for c, (pdk, lib, dev) in cells:
        rec = {"cell": c.name, "title": c.display_title(), "pdk": pdk, "library": lib,
               "device": dev, "problems": []}
        if ph is not None and not c.shapes(ph).is_empty():
            rec["problems"].append("placeholder (generation failed when this file was saved)")
        if c.is_empty() or all(c.shapes(li).is_empty() for li in ly.layer_indices()):
            rec["problems"].append("empty cell")
        st = read_stamp(c)
        rec["stamp"] = st
        cur = current.get(pdk)
        if st is None:
            if "empty cell" not in rec["problems"]:
                rec["problems"].append("no generated-by stamp")
        elif st.get("pdk") and st.get("pdk") != pdk:
            rec["problems"].append("stamped for %s, but the cell is in the %s library" % (st["pdk"], lib))
        elif cur and not same_versions(st, cur):
            rec["problems"].append("generated with %s; installed is %s" % (describe(st), describe(cur)))
        gp = _grid_problem(manifests.get(pdk), dev, ly.dbu, st)
        if gp:
            rec["problems"].append(gp)
        rep["cells"].append(rec)
        if regen:
            snaps[c.cell_index()] = _snapshot(ly, c)
    if not rep["dbu_divides_5nm"]:
        rep["file_problems"] = ["dbu %g um doesn't divide 5 nm: Magic's coordinates get rounded"
                                % ly.dbu]
    if regen and cells:
        from . import register, state_for
        from .config import Config
        gens = {}
        for pdk in pdks:
            # "fresh": every variant comes from Magic, as if the memo and the
            # disk cache were empty, and the disk cache gets the new entries.
            # The cells revive and regenerate when the library registers.
            cfg = Config.load(pdk=pdk)
            cfg.fresh = True
            if register(pdk, cfg=cfg) is None:
                rep.setdefault("file_problems", []).append(
                    "--regen: the %s library could not be registered (%s)"
                    % (LIBRARY_NAMES[pdk], state_for(pdk).last_error))
                continue
            gens[pdk] = state_for(pdk).generator
        for rec, ci, (_c, (pdk, lib, dev)) in zip(rep["cells"], indices, cells):
            if pdk not in gens:
                rec["regen"] = "library not registered"
                continue
            live = ly.cell(ci)
            old_ly, old_c = snaps[ci]
            diff = _diff_layers(old_ly, old_c, ly, live)
            rec["regen"] = "same as stored" if not diff else "differs on " + ", ".join(diff)
            rec["live_after_register"] = live.is_pcell_variant()
            if diff:
                rec["problems"].append("regenerated geometry differs on " + ", ".join(diff))
            phl = ly.find_layer(*PLACEHOLDER_LAYER)
            if phl is not None and not live.shapes(phl).is_empty():
                texts = [sh.text_string for sh in live.shapes(phl).each() if sh.is_text()]
                rec["problems"].append("regenerates as the error marker: %s"
                                       % (texts[0] if texts else "?"))
        # Disk-cache entries that differ from what Magic writes now.
        for pdk, g in gens.items():
            for key, old in sorted(g.replaced.items()):
                res = g._memo.get(key)
                if res is None:
                    continue
                try:
                    diff = _gds_diff(old, res.gds_path)
                except Exception as e:
                    diff = ["unreadable (%s)" % e]
                if diff:
                    rep.setdefault("file_problems", []).append(
                        "the %s disk cache held a stale %s (differs on %s); replaced with what "
                        "Magic generates now" % (pdk, res.sidecar.get("device"), ", ".join(diff)))
                try:
                    import os
                    os.remove(old)
                except OSError:
                    pass
            g.replaced.clear()
    return rep


def format_report(rep):
    lines = ["%s: dbu %g um%s" % (rep["file"], rep["dbu"],
                                  "" if rep["dbu_divides_5nm"] else " (does NOT divide 5 nm)")]
    for p in rep.get("file_problems", []):
        lines.append("  file: " + p)
    if not rep["cells"]:
        lines.append("  no cells of the %s libraries" % ", ".join(sorted(PDK_OF_LIBRARY)))
    for c in rep["cells"]:
        state = "; ".join(c["problems"]) or "ok"
        lines.append("  %s  %s" % (c["cell"], state))
        if "regen" in c:
            lines.append("      regenerated: %s" % c["regen"])
    n_bad = sum(1 for c in rep["cells"] if c["problems"])
    libs = sorted({c["library"] for c in rep["cells"]})
    lines.append("%d %s cells, %d with problems" % (len(rep["cells"]), "/".join(libs) or "library",
                                                    n_bad))
    return "\n".join(lines)
