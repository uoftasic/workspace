#!/usr/bin/env python3
"""The parity harness's ``jobs`` step: the plugin's Magic jobs against
references that use no plugin code (design-0.6.md 1 and 5.2, and the
decisions of 6.1, 6.2, 6.3 and 6.5). tests/parity/run_sweep.py runs it
after DRC and extraction; it also runs alone, in the image:

    python3 tests/jobs/run_jobs.py --pdk P --out DIR [--quick] [--update-baseline] [--jobs N] [--keep]

It builds the case suite into DIR/cases (tests/jobs/build_cases.py) and runs
these checks, each counted per case in the report:

- drc_plumbing: the plugin's DRC in each style and both modes against
  tests/parity/mdrc.tcl on the plugin's own export, as multisets of (cell,
  why-text, box at 1 nm). Hierarchical mode is compared before the plugin
  drops a parent's boxes that are copies of a subcell's box (each cell's own
  listing, Outcome.raw), with mdrc.tcl checking each cell of the export as
  its own top; flat mode through the plugin's TSV.
- drc_fidelity: Magic's own reading of the original GDS, every cell checked
  as hierarchical mode does (mdrc.tcl per cell), against the plugin's
  hierarchical run on its export, per cell and rule as merged regions; the
  XOR must be empty at 1 nm.
- drc_hier: on the hier set, the top cell's own drc(full) listing equals
  cases.json expect.magic, and the extraction's devices equal
  expect.magic.extract.
- drc_names: each names case gives its one error under its KLayout name;
  a cell that is not in the file fails the job.
- lvs: the plugin's verdict equals netgen run here on the same netlists,
  read with this file's own parser.
- lvs_badnets: every badnets entry of that netgen run's JSON is one of the
  plugin's markers or report rows.
- layers, ports: the findings equal tests/jobs/expected-<pdk>.json, which
  --update-baseline rewrites.
- controls: the negative controls give no F1 to F4 finding, asserted here,
  never taken from the baseline file.
- readback: the GDS read-back check: each device extracted from Magic's
  database and again after Magic's GDS write and read matches
  data/readback-<pdk>.json (tests/jobs/readback.py).
- gaps: tools/build_gaps.py --check.

Recorded, not checked: magic_native (tests/jobs/magic_native.tcl, what a
Magic user gets, per case and rule), the sheet's hierarchical, top-only and
flat counts, and the time of every job.

The gaps set runs as the cells of the case suite's sheet: hierarchical mode
checks each D<case> cell as its own top, 15 to a process, which is the
per-case check with a fifteenth of the Magic processes. ``--quick`` builds
the inverters, gaps and controls sets without the Magic-written row, runs
the inverters set and the QUICK_EXTRA cases taken from the other two, and
skips readback and gaps.

Exit status: 0 when every check passes, 1 when one fails or a unit of work
raises (that is most often the plugin raising), 2 when the step itself
fails (the case build, for example); run_sweep.py turns the last into a
harness error.
"""

import argparse
import collections
import json
import multiprocessing
import os
import re
import shutil
import subprocess
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
for _p in (REPO, os.path.join(REPO, "python"), os.path.join(REPO, "tests", "parity")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

NATIVE_TCL = os.path.join(HERE, "magic_native.tcl")
CHECKS = ("drc_plumbing", "drc_cells", "drc_markers", "drc_coverage", "drc_fidelity", "drc_hier", "drc_names", "lvs",
          "lvs_badnets", "lvs_markers", "layers", "ports", "ports_expect", "controls", "f1_positives",
          "reads_nothing", "readback", "gaps")
BATCH = 15                       # cells per Magic process (design-0.6.md 2.1)
SAFE_NAME = re.compile(r"^[A-Za-z0-9_$]+$")
NO_NET = "(no matching net)"
LAYER_SETS = ("gaps", "hier", "whole_shape", "inverters", "controls")
P8_SETS = ("inverters", "controls")
MAX_DETAIL = 12
KEEP_RESULTS = ("drc_hier", "drc_names", "lvs", "lvs_badnets", "lvs_markers", "ports_expect", "f1_positives",
                "reads_nothing", "readback", "gaps")
# The plugin's report categories the step reads (markers.py, drcjob.py, lvsjob.py).
CAT_DRC = "Magic DRC"
CAT_ALONE_PREFIX = "only when "
CAT_READS_NOTHING = "Export/Magic reads nothing in this cell"
NET_CATS = ("netgen/nets that differ", "netgen/net only in the layout")
# --quick: the inverters set and, per PDK, a negative control, an F3 case and
# a cell Magic reads nothing in (the last only where the gaps set has one).
QUICK_EXTRA = {
    "sky130A": ("sky130_fd_sc_hd__mux2_1", "c_licon_gate", "s_npc_alone"),
    "gf180mcuD": ("gf180mcu_fd_sc_mcu7t5v0__mux2_2", "CO11_cont_field"),
    "ihp-sg13g2": ("sg13g2_mux2_1", "Cnt_g", "EXTB_a"),
    "ihp-sg13cmos5l": ("sg13cmos5l_mux2_1", "m_V1.a"),
}
# GAPS F1 positives (design-0.6.md 3.3) and the layer F1 must name:
# the table of tests/backend/test_layers_backend.py F1_POSITIVES. Asserted in
# code, also with --update-baseline, so a baseline never absorbs their loss.
F1_POSITIVES = {
    "sky130A": {"a_nsdm_flush": "nsdm", "c_npc_narrow": "npc", "i_hvtp_w030": "hvtp"},
    "gf180mcuD": {"NP_flush": "nplus", "NP5a_ov010": "nplus", "PP5_ov0": "pplus", "DG_small": "dualgate"},
    "ihp-sg13g2": {"H_pmos_psdflush": "psd"},
    "ihp-sg13cmos5l": {"u_pSD.c": "psd", "u_pSD.i": "psd", "g_hv_tgo_small": "thkox"},
}
# The gaps cases Magic reads nothing in (only implants or markers, no
# diffusion or poly under them). drc (both modes) and layers give status 1
# with a CAT_READS_NOTHING item, not a failed job; on the sheet, hierarchical
# mode lists their D<case> cells in Outcome.empty. Every other case must give
# no such item.
READS_NOTHING = {
    "sky130A": ("s_hvtp_alone", "s_hvtp_alone_ok", "s_lvtn_alone", "s_lvtn_alone_ok", "s_npc_alone",
                "s_npc_alone_ok", "s_nsdm_alone", "s_nsdm_alone_ok"),
    "gf180mcuD": (),
    "ihp-sg13g2": ("EXTB_a", "EXTB_a_ok", "EXTB_b", "EXTB_b_ok", "Sal_a", "Sal_a_ok", "TGO_e", "TGO_e_ok",
                   "TGO_f", "TGO_f_ok", "nSDB_a", "nSDB_a_ok", "nSDB_b", "nSDB_b_ok", "pSD_a", "pSD_a_ok",
                   "pSD_b", "pSD_b_ok", "pSD_k", "pSD_k_ok", "pSD_l", "pSD_l_ok"),
    "ihp-sg13cmos5l": (),
}
SHEET_STYLES = ("drc(full)", "drc(routing)", "drc(fast)")
# Sheet cells that the harness accepts as unchecked without their being in
# Outcome.empty. Empty since drcjob lists the cells Magic's hierarchy lacks
# (ihp-sg13g2 TGO_e and TGO_f, measured on 2026-11-24) as empty.
UNLISTED = {}   # cells Magic lacks are listed in Outcome.empty since the drcjob fix


def log_default(msg):
    print("[%s] %s" % (time.strftime("%H:%M:%S"), msg), flush=True)


def expected_path(pdk):
    return os.path.join(HERE, "expected-%s.json" % pdk)


def chunks(xs, n=BATCH):
    return [xs[i:i + n] for i in range(0, len(xs), n)]


def nm_box(vals):
    """[l, b, r, t] in µm as an ordered tuple of nm."""
    v = [int(round(float(x) * 1000.0)) for x in vals]
    return (min(v[0], v[2]), min(v[1], v[3]), max(v[0], v[2]), max(v[1], v[3]))


def rule_of(why):
    import drc as hdrc
    return hdrc.magic_rule_id(why)


def tree_bottom_up(layout, top_name):
    """The cells under ``top_name`` and itself, children before parents."""
    top = layout.cell(top_name)
    if top is None:
        return []
    tree = set(top.called_cells()) | {top.cell_index()}
    return [layout.cell(ci).name for ci in layout.each_cell_bottom_up() if ci in tree]


def multiset_diff(a, b):
    """(only in a, only in b), each a sorted list of at most MAX_DETAIL items."""
    ca, cb = collections.Counter(a), collections.Counter(b)
    oa = sorted((ca - cb).elements(), key=str)
    ob = sorted((cb - ca).elements(), key=str)
    return oa[:MAX_DETAIL], ob[:MAX_DETAIL], len(oa), len(ob)


# --- the worker side: one process per unit of work ---------------------------------

CTX = {}


def _init(pdk, out, cases_dir):
    from klayout_magic_pcells import pdkdata
    from klayout_magic_pcells.config import Config
    # One job cache per worker keeps the workers apart: a worker never takes
    # a result that another worker's job left in the cache. Two cases can
    # export to the same file (the names a.b and a-b both become a_b) and
    # then share a cache key; that is safe within one cache too, since a job
    # never runs in its key's directory and publishes it whole (jobs.MagicJob).
    env = dict(os.environ, KMP_PDK=pdk, KMP_PDKS=pdk, PDK=pdk,
               KMP_CACHE_DIR=os.path.join(out, "cache", "w%d" % os.getpid()))
    CTX.update(pdk=pdk, out=out, cases=cases_dir, env=env,
               cfg=Config.load(env=env, pdk=pdk), data=pdkdata.load(pdk))


class Unit:
    """What one piece of work found: results per check, records, timings."""

    def __init__(self, name):
        self.name = name
        self.results = []      # {"check", "case", "ok", "detail"}
        self.records = {}
        self.timing = []       # (kind, label, seconds)
        self.errors = []

    def result(self, check, case, ok, detail=None, **extra):
        r = {"check": check, "case": case, "ok": bool(ok)}
        if detail:
            r["detail"] = detail
        r.update(extra)
        self.results.append(r)
        return ok

    def timed(self, kind, label, fn, *a, **kw):
        t0 = time.time()
        try:
            return fn(*a, **kw)
        finally:
            self.timing.append((kind, label, round(time.time() - t0, 3)))

    def as_dict(self):
        return {"name": self.name, "results": self.results, "records": self.records,
                "timing": self.timing, "errors": self.errors}


def _work_dir(*parts):
    d = os.path.join(CTX["out"], *parts)
    os.makedirs(d, exist_ok=True)
    return d


def _safe(s):
    return re.sub(r"[^A-Za-z0-9_.-]", "_", s)


def mdrc_cells(u, gds, cells, style, tag):
    """mdrc.tcl on ``gds``, each cell its own top, BATCH to a process:
    {cell: Counter((cell, why, box nm))}."""
    import drc as hdrc
    d = _work_dir("ref", _safe(tag))
    out = {}
    for i, ch in enumerate(chunks(cells)):
        tsv = os.path.join(d, "%s_%d.tsv" % (_safe(style), i))
        got = u.timed("mdrc", "%s %s" % (tag, style), hdrc.run_mdrc, gds, ch, tsv, tsv[:-4] + ".log",
                      pdk=CTX["pdk"], style=style)
        for c, rows in got.items():
            out[c] = collections.Counter((c, why, nm_box(b)) for why, b in rows)
    return out


def run_native(u, gds, tops, tag):
    """magic_native.tcl on the file ``gds`` (or the files, a list), each of
    ``tops`` checked from the top: {cell: {style: {"total": n, "rules":
    Counter}}}."""
    d = _work_dir("native")
    res = {}
    files = "\n".join(gds) if isinstance(gds, (list, tuple)) else gds
    for i, ch in enumerate(chunks(tops)):
        tsv = os.path.join(d, "%s_%d.tsv" % (_safe(tag), i))
        env = dict(CTX["env"], KMP_GDS=files, KMP_TOP="\n".join(ch), KMP_OUT=tsv)
        cmd = ["magic", "-dnull", "-noconsole", "-rcfile", CTX["cfg"].magicrc or _magicrc(), NATIVE_TCL]
        t0 = time.time()
        with open(tsv[:-4] + ".log", "w") as lf:
            subprocess.run(cmd, env=env, cwd=d, stdin=subprocess.DEVNULL, stdout=lf, stderr=subprocess.STDOUT,
                           timeout=1800)
        u.timing.append(("native", tag, round(time.time() - t0, 3)))
        with open(tsv[:-4] + ".log", errors="replace") as lf:
            if "NATIVE_DONE" not in lf.read():
                raise RuntimeError("magic_native.tcl did not finish on %s (%s)" % (gds, tsv[:-4] + ".log"))
        with open(tsv, encoding="utf-8", errors="replace") as f:
            for line in f:
                p = line.rstrip("\n").split("\t")
                if p[0] == "count" and len(p) == 4:
                    res.setdefault(p[1], {}).setdefault(p[2], {"total": 0, "rules": collections.Counter()})
                    res[p[1]][p[2]]["total"] = int(p[3] or 0)
                elif p[0] == "box" and len(p) == 5:
                    s = res.setdefault(p[1], {}).setdefault(p[2], {"total": 0, "rules": collections.Counter()})
                    s["rules"][rule_of(p[3])] += 1
    return res


def _magicrc():
    pdk = CTX["pdk"]
    return os.path.join(os.environ.get("PDK_ROOT", "/foss/pdks"), pdk, "libs.tech", "magic", pdk + ".magicrc")


def styles():
    return [s for s in CTX["data"].drc.get("styles", []) if s.startswith("drc(")]


def plugin_drc(u, layout, top, style, mode, label, file):
    from klayout_magic_pcells import drcjob
    task = drcjob.prepare(layout, top, CTX["cfg"], CTX["data"], {"style": style, "mode": mode, "file": file})
    return u.timed("drc", "%s %s %s" % (label, style, mode), task.wait)


def read_tsv(path):
    """The plugin's --tsv file: [(KLayout cell, why, box nm)]."""
    rows = []
    with open(path, encoding="utf-8") as f:
        head = f.readline().rstrip("\n")
        if head != "cell\trule\twhy\tl\tb\tr\tt":
            raise RuntimeError("the plugin's TSV %s starts with %r, not its header" % (path, head))
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) == 7:
                rows.append((p[0], p[2], nm_box(p[3:7])))
    return rows


def rdb_error_boxes(r):
    """{KLayout cell: Counter((why, box nm))} of a report database's DRC
    error items: under "Magic DRC", not under an "only when <cell> is checked
    on its own" category; the why is the item's category name. An item
    without exactly one box counts under the why "(no single box)"."""
    out = collections.defaultdict(collections.Counter)
    for it in r.each_item():
        cat = r.category_by_id(it.category_id())
        why = cat.name()
        alone = False
        while cat.parent() is not None:
            alone = alone or cat.name().startswith(CAT_ALONE_PREFIX)
            cat = cat.parent()
        if cat.name() != CAT_DRC or alone:
            continue
        cell = r.cell_by_id(it.cell_id()).name()
        boxes = [v.box() for v in it.each_value() if v.is_box()]
        if len(boxes) != 1:
            out[cell][("(no single box)", why)] += 1
            continue
        b = boxes[0]
        out[cell][(why, nm_box([b.left, b.bottom, b.right, b.top]))] += 1
    return out


def check_markers(u, name, o, style, mode):
    """drc_markers: the boxes of the report database's error items equal
    Outcome.rows, cell by cell, as (why, box at 1 nm) multisets."""
    marks = rdb_error_boxes(o.rdb.db)
    rows = collections.defaultdict(collections.Counter)
    for c, why, b in o.rows:
        rows[c][(why, tuple(int(v) for v in b))] += 1
    bad = []
    for c in sorted(set(marks) | set(rows)):
        if marks.get(c, collections.Counter()) != rows.get(c, collections.Counter()):
            oa, ob, na, nb = multiset_diff(marks.get(c, collections.Counter()), rows.get(c, collections.Counter()))
            bad.append({"cell": c, "only_rdb": na, "only_rows": nb, "rdb": oa, "rows": ob})
    u.result("drc_markers", name, not bad, {"cells": bad[:MAX_DETAIL]} if bad else None, style=style, mode=mode,
             boxes=len(o.rows))


def check_reads_nothing_drc(u, name, o, style, mode, top):
    """A cell Magic reads nothing in: status 1, the CAT_READS_NOTHING item,
    and the cell in Outcome.empty."""
    n = o.rdb.count(CAT_READS_NOTHING)
    empty = list(getattr(o, "empty", None) or [])
    ok = o.status == 1 and n > 0 and top in empty
    u.result("reads_nothing", "%s (drc %s %s)" % (name, style, mode), ok,
             None if ok else {"status": o.status, "items": n, "empty": empty, "summary": o.summary[:300]})


def check_plumbing(u, case, o, mode, style, reported_as=None):
    """The plugin's boxes against mdrc.tcl's on the plugin's own export.
    Returns {file cell: Counter} of the reference (hierarchical mode)."""
    from klayout_magic_pcells import drcjob
    import klayout.db as db
    name = case["name"]
    if o.status == 2:
        u.result("drc_plumbing", name, False, "the plugin's DRC failed (%s, %s): %s" % (style, mode, o.summary),
                 style=style, mode=mode)
        return None
    check_markers(u, name, o, style, mode)
    er = o.export[next(iter(o.export))]
    exp = o.files["export"]
    el = db.Layout()
    el.read(exp)
    if mode == "hierarchical":
        cells = tree_bottom_up(el, er.top)
        ref = mdrc_cells(u, exp, cells, style, "%s_hier" % name)
        raw = next(iter(o.raw.values())) if o.raw else {}
        # the cells the plugin checked: the export's tree, from KLayout's
        # reading, minus the cells it says Magic read as empty
        empty = set(getattr(o, "empty", None) or [])
        known = set(UNLISTED.get(CTX["pdk"], ()))
        want = {c for c in cells if er.klayout_name(c) not in empty and er.klayout_name(c) not in known}
        got = {c for c in raw if er.klayout_name(c) not in known}
        u.result("drc_cells", name, want == got,
                 None if want == got else {"not_checked": sorted(want - got)[:MAX_DETAIL],
                                           "not_in_tree": sorted(got - want)[:MAX_DETAIL],
                                           "empty": sorted(empty)[:MAX_DETAIL]},
                 style=style, mode=mode, cells=len(cells), empty=len(empty))
        by_cell = reported_as or {}
        bad, rest = [], []
        for c in sorted(set(cells) | set(raw)):
            mine = collections.Counter((e.cell, e.why, e.box) for e in raw.get(c, []))
            theirs = ref.get(c, collections.Counter())
            ok = mine == theirs
            diff = None
            if not ok:
                oa, ob, na, nb = multiset_diff(mine, theirs)
                diff = {"cell": c, "only_plugin": na, "only_mdrc": nb, "plugin": oa, "mdrc": ob}
                bad.append(diff)
            kn = er.klayout_name(c)
            if kn in by_cell:
                u.result("drc_plumbing", by_cell[kn], ok, diff, style=style, mode=mode)
            elif diff:
                rest.append(diff)
        if not reported_as:
            u.result("drc_plumbing", name, not bad, {"cells": bad} if bad else None, style=style, mode=mode,
                     cells=len(cells), boxes=sum(len(v) for v in raw.values()))
        elif rest:
            u.result("drc_plumbing", "%s (other cells)" % name, False, {"cells": rest}, style=style, mode=mode)
        return ref
    # flat: the TSV the command line writes, against mdrc.tcl on the flat export
    tsv = os.path.join(_work_dir("plugin"), "%s_%s_flat.tsv" % (_safe(name), _safe(style)))
    drcjob.write_tsv(tsv, o.rows)
    rows = read_tsv(tsv)
    mine = collections.Counter((er.name_map.get(c, c), why, box) for c, why, box in rows)
    ref = mdrc_cells(u, exp, [er.top], style, "%s_flat" % name)
    theirs = ref.get(er.top, collections.Counter())
    ok = mine == theirs
    detail = None
    if not ok:
        oa, ob, na, nb = multiset_diff(mine, theirs)
        detail = {"only_plugin": na, "only_mdrc": nb, "plugin": oa, "mdrc": ob}
    u.result("drc_plumbing", name if not reported_as else "%s (flat)" % name, ok, detail, style=style, mode=mode,
             boxes=len(rows))
    return ref


def regions_by_rule(entries):
    """{(cell, rule): Region} from (cell, why, box nm) entries."""
    import klayout.db as db
    out = {}
    for c, why, b in entries:
        out.setdefault((c, rule_of(why)), db.Region()).insert(db.Box(*b))
    for r in out.values():
        r.merge()
    return out


def check_fidelity(u, case, o, style, original, reported_as=None):
    """Magic's reading of the original file, per cell, against the plugin's
    hierarchical run on its export: per cell and rule, merged regions."""
    if o.status == 2:
        u.result("drc_fidelity", case["name"], False, "the plugin's DRC failed: %s" % o.summary, style=style)
        return
    er = o.export[next(iter(o.export))]
    from klayout_magic_pcells import export
    ol = export.load_layout(original)
    cells = tree_bottom_up(ol, case["top"])
    skipped = [c for c in cells if not SAFE_NAME.match(c)]
    cells = [c for c in cells if SAFE_NAME.match(c)]
    ref = mdrc_cells(u, original, cells, style, "%s_orig" % case["name"])
    raw = next(iter(o.raw.values())) if o.raw else {}
    mine = [(er.klayout_name(fc), e.why, e.box) for fc, errs in raw.items() for e in errs
            if er.klayout_name(fc) in cells]
    theirs = [e for c in cells for e in ref.get(c, collections.Counter()).elements()]
    rm, rt = regions_by_rule(mine), regions_by_rule(theirs)
    by_cell = reported_as or {}
    bad = {}
    for key in sorted(set(rm) | set(rt)):
        a = rm.get(key)
        b = rt.get(key)
        import klayout.db as db
        x = (a or db.Region()) ^ (b or db.Region())
        if not x.is_empty():
            bb = x.bbox()
            bad.setdefault(key[0], []).append({"rule": key[1], "xor_area_um2": round(x.area() / 1e6, 6),
                                               "xor_bbox_um": [bb.left / 1e3, bb.bottom / 1e3, bb.right / 1e3,
                                                               bb.top / 1e3]})
    if reported_as:
        for c in cells:
            if c in by_cell:
                u.result("drc_fidelity", by_cell[c], c not in bad, {"rules": bad[c]} if c in bad else None,
                         style=style)
        return
    detail = {"cells": bad} if bad else None
    extra = {"skipped_cells": skipped} if skipped else {}
    u.result("drc_fidelity", case["name"], not bad, detail, style=style, cells=len(cells), **extra)


def native_record(u, case, native, outcomes):
    """Per style and rule: Magic's top-only check against the plugin's
    hierarchical rows (after it drops boxes that are copies of a subcell's box). Recorded only."""
    rec = {}
    for style, n in native.items():
        o = outcomes.get(style)
        if o is None or o.status == 2:
            continue
        plugin = collections.Counter(rule_of(why) for _c, why, _b in o.rows)
        top_counts = next(iter(o.counts.values())) if o.counts else {}
        diff = {r: [n["rules"].get(r, 0), plugin.get(r, 0)] for r in sorted(set(n["rules"]) | set(plugin))
                if n["rules"].get(r, 0) != plugin.get(r, 0)}
        rec[style] = {"native_count_total": n["total"], "native_boxes": sum(n["rules"].values()),
                      "plugin_boxes": len(o.rows), "plugin_count_total_summed": sum(top_counts.values()),
                      "rules_differ": diff}
    u.records.setdefault("native", {})[case["name"]] = rec


def check_hier(u, case, o_full, layout, path):
    from klayout_magic_pcells import lvsjob
    exp = (case.get("expect") or {}).get("magic") or {}
    name = case["name"]
    if "drc(full)" in exp:
        if o_full is None or o_full.status == 2:
            u.result("drc_hier", name, False, "the plugin's DRC failed")
        else:
            er = o_full.export[next(iter(o_full.export))]
            raw = next(iter(o_full.raw.values()))
            top_rows = raw.get(er.top, [])
            got = collections.Counter(rule_of(e.why) for e in top_rows)
            want = collections.Counter(exp["drc(full)"])
            extras = collections.Counter(rule_of(e.why) for c, errs in raw.items() if c != er.top for e in errs)
            ok = got == want
            u.result("drc_hier", name, ok, None if ok else {"top_cell": dict(got), "expect": dict(want)},
                     what="drc(full), the top cell's own listing", children_add=dict(extras))
    if "extract" in exp:
        task = lvsjob.prepare(layout, case["top"], CTX["cfg"], CTX["data"], {"cmd": "extract", "file": path})
        o = u.timed("extract", name, lambda: task.start().wait())
        if o.status == 2:
            u.result("drc_hier", name + " (extract)", False, o.summary)
            return
        from tests.jobs.readback import netlist_devices
        devs = collections.Counter()
        for (_l, model, _p), n in (netlist_devices(o.files["netlist"]) or {}).items():
            devs[model] += n
        want = collections.Counter(exp["extract"])
        u.result("drc_hier", name + " (extract)", devs == want,
                 None if devs == want else {"extracted": dict(devs), "expect": dict(want)})


def check_names(u, case, o):
    name = case["name"]
    kname = case.get("klayout_name")
    if kname == "does_not_exist":
        u.result("drc_names", name, o.status == 2,
                 None if o.status == 2 else "a cell not in the file gave status %d: %s" % (o.status, o.summary))
        return
    targets = case.get("targets") or []
    rules = [(c, rule_of(why)) for c, why, _b in o.rows]
    ok = o.status == 1 and len(rules) == 1 and rules[0][0] == case["top"] and rules[0][1] in targets
    u.result("drc_names", name, ok, None if ok else {"rows": rules, "status": o.status, "want": targets,
                                                    "cell": case["top"]})


# netgen's verdict, read here with nothing of netgen.py
_FINAL = re.compile(r"^\s*Final result:\s*(.*)$")
_MATCHED = re.compile(r"^(Circuits|Netlists) match (uniquely|with \d+ symmetr\w*)\.?$")
_FAILS = ("Property errors were found", "with property errors", "with port errors", "failed pin matching",
          "do not match", "failed matching", "subcells failed to match")


def harness_verdict(report_text):
    """(matched, final line) of a netgen report: a match only when the last
    "Final result" says the circuits match and no failure follows it."""
    lines = report_text.splitlines()
    idx = [i for i, ln in enumerate(lines) if _FINAL.match(ln)]
    if not idx:
        return False, None
    i = idx[-1]
    final = _FINAL.match(lines[i]).group(1).strip()
    j = i + 1
    if not final:
        while j < len(lines) and not lines[j].strip():
            j += 1
        final = lines[j].strip() if j < len(lines) else ""
        j += 1
    after = "\n".join(lines[j:])
    matched = bool(_MATCHED.match(final)) and not any(f in after for f in _FAILS)
    return matched, final


def _mentions(text, name):
    return re.search(r"(?<![\w#$/\[])%s(?![\w#$\[])" % re.escape(name), text or "") is not None


def check_lvs(u, case, layout, path):
    from klayout_magic_pcells import lvsjob
    name = case["name"]
    sch = os.path.join(CTX["cases"], case["schematic"])
    task = lvsjob.prepare(layout, case["top"], CTX["cfg"], CTX["data"],
                          {"cmd": "lvs", "schematic": sch, "file": path})
    o = u.timed("lvs", name, lambda: task.start().wait())
    if o.status == 2:
        u.result("lvs", name, False, "the plugin's LVS failed: %s" % o.summary)
        return
    cfg = CTX["cfg"]
    d = _work_dir("lvs", _safe(name))
    report = os.path.join(d, "harness.out")
    cmd = [cfg.netgen, "-batch", "lvs", "%s %s" % (o.files["netlist"], task.export.top),
           "%s %s" % (sch, task.schematic_cell), cfg.netgen_setup, report, "-json"]
    t0 = time.time()
    with open(os.path.join(d, "netgen.log"), "w") as lf:
        subprocess.run(cmd, cwd=d, stdin=subprocess.DEVNULL, stdout=lf, stderr=subprocess.STDOUT, timeout=600)
    u.timing.append(("netgen", name, round(time.time() - t0, 3)))
    try:
        with open(report, encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError:
        u.result("lvs", name, False, "netgen run by the harness wrote no report (%s)" % d)
        return
    matched, final = harness_verdict(text)
    plugin = bool(o.verdict.matched) if o.verdict is not None else None
    ok = plugin == matched and (o.status == 0) == matched
    expect = (case.get("expect") or {}).get("netgen")
    u.result("lvs", name, ok, None if ok else {"plugin": {"matched": plugin, "final": o.verdict.final,
                                                          "status": o.status},
                                              "harness": {"matched": matched, "final": final}},
             final=final, matched=matched, expect_netgen=expect)
    # every badnets entry of netgen's JSON is a marker or a report row
    try:
        with open(os.path.splitext(report)[0] + ".json", encoding="utf-8", errors="replace") as f:
            circuits = [c for c in json.load(f) if isinstance(c, dict)]
    except (OSError, ValueError) as e:
        u.result("lvs_badnets", name, False, "netgen's JSON could not be read: %s" % e)
        return
    texts = [(f["text"], f.get("box") is not None) for f in o.findings
             if f["category"].startswith(("netgen/", "Extraction/nets"))]
    missing, markers_n, rows_n, entries = [], 0, 0, 0
    badnets = set()
    for c in circuits:
        for frag in c.get("badnets") or []:
            entries += 1
            sides = [[ent[0] for ent in (side or []) if ent and ent[0] != NO_NET] for side in (frag or [])[:2]]
            need = sides[0] if sides and sides[0] else (sides[1] if len(sides) > 1 else [])
            badnets.update(sides[0] if sides else [])
            for n in need:
                hits = [has_box for t, has_box in texts if _mentions(t, n)]
                if not hits:
                    missing.append(n)
                elif any(hits):
                    markers_n += 1
                else:
                    rows_n += 1
    u.result("lvs_badnets", name, not missing, {"nets without a marker or row": missing} if missing else None,
             entries=entries, as_markers=markers_n, as_rows=rows_n)
    check_lvs_markers(u, case, task, o, layout, badnets)


def ext_nodes(path):
    """{node name: (x, y, type)} of a Magic .ext file, in Magic's units,
    read here with nothing of extfile.py."""
    out = {}
    pat = re.compile(r'^(?:node|substrate)\s+"((?:[^"\\]|\\.)*)"\s+\S+\s+\S+\s+(-?\d+)\s+(-?\d+)\s+(\S+)')
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = pat.match(line)
            if m:
                out[m.group(1)] = (int(m.group(2)), int(m.group(3)), m.group(4))
    return out


def job_scale(task, o):
    """µm per Magic unit: the job's JobResult.scale, or the kmp_result.json
    the job directory keeps."""
    r = getattr(task, "_result", None)
    if r is not None and getattr(r, "scale", None):
        return float(r.scale)
    with open(os.path.join(o.files["job_dir"], "kmp_result.json"), encoding="utf-8") as f:
        return float(json.load(f)["scale"])


def _contains(box, x, y, tol=1e-3):
    l, b, r, t = box
    return l - tol <= x <= r + tol and b - tol <= y <= t + tol


def check_lvs_markers(u, case, task, o, layout, badnets):
    """lvs_markers: each net marker of a badnets net holds that net's .ext
    node point at the job's scale. On inv_open_drain there is one, and it
    covers the NMOS drain diffusion: the piece of diffusion minus poly at the
    floating net's node point."""
    name = case["name"]
    try:
        top = task.export.top
        nodes = ext_nodes(os.path.join(o.files["job_dir"], top + ".ext"))
        scale = job_scale(task, o)
    except (OSError, ValueError, KeyError, AttributeError) as e:
        u.result("lvs_markers", name, False, "the .ext file or the job's scale could not be read: %s" % e)
        return
    bad, checked = [], []
    for f in o.findings:
        if f["category"] not in NET_CATS or f.get("box") is None:
            continue
        net = f["text"].split(",")[0]
        if net not in badnets:
            continue
        if net not in nodes:
            bad.append({"net": net, "why": "no node of this name in %s.ext" % top})
            continue
        x, y, typ = nodes[net]
        px, py = x * scale, y * scale
        box = [float(v) for v in f["box"]]
        rec = {"net": net, "node_um": [round(px, 4), round(py, 4)], "type": typ, "box": [round(v, 4) for v in box]}
        checked.append(rec)
        if not _contains(box, px, py):
            bad.append(dict(rec, why="the marker does not hold the node point"))
    if name == "inv_open_drain":
        drain = open_drain_check(layout, case["top"], checked)
        if drain:
            bad.append(drain)
    u.result("lvs_markers", name, not bad, {"markers": bad[:MAX_DETAIL]} if bad else None,
             markers=len(checked), nets=sorted(badnets)[:MAX_DETAIL], points=checked[:4])


def open_drain_check(layout, top, checked):
    """None when inv_open_drain has a net marker whose node point is on the
    NMOS drain diffusion (the piece of diffusion minus poly at that point),
    and that marker is a shape, not a dot, that covers the piece; else why
    not. The other nets netgen lists (Y) sit on metal and are not tested
    here."""
    import klayout.db as db
    cell = layout.cell(top)
    diff, poly = db.Region(), db.Region()
    for r in getattr(CTX["data"], "layers", []):
        if r.get("read") != "paint" or r.get("role") not in ("diffusion", "poly"):
            continue
        li = layout.find_layer(r["gds"][0], r["gds"][1])
        if li is None:
            continue
        reg = db.Region(cell.begin_shapes_rec(li))
        (diff if r["role"] == "diffusion" else poly).insert(reg)
    pieces_all = (diff.merged() - poly.merged()).merged()
    found = []
    for m in checked:
        x, y = (int(round(v / layout.dbu)) for v in m["node_um"])
        pieces = pieces_all.interacting(db.Region(db.Box(x - 1, y - 1, x + 1, y + 1)))
        if pieces.is_empty():
            continue
        bb = pieces.bbox()
        want = [round(v * layout.dbu, 4) for v in (bb.left, bb.bottom, bb.right, bb.top)]
        l, b, r, t = m["box"]
        if r - l <= 0.05 or t - b <= 0.05:
            return dict(m, why="the drain's marker is a dot, not the net's diffusion", drain_um=want)
        if not (_contains(m["box"], want[0], want[1]) and _contains(m["box"], want[2], want[3])):
            return dict(m, why="the marker does not cover the NMOS drain diffusion", drain_um=want)
        found.append(m)
    if not found:
        return {"why": "no net marker of inv_open_drain has its node point on the drain diffusion",
                "markers": checked}
    return None


def _box4(b):
    return [round(b.left, 3), round(b.bottom, 3), round(b.right, 3), round(b.top, 3)]


def _reason(summary):
    """A job's failure text without the paths of this run."""
    return re.sub(r"/\S+", "<path>", summary or "")


def run_layers(u, case, layout, path):
    """layers and ports findings, normalised for the baseline."""
    from klayout_magic_pcells import layercheck, portcheck
    name = case["name"]
    rec = {}
    try:
        task = layercheck.prepare(layout, case["top"], CTX["cfg"], CTX["data"], {"file": path})
        o = u.timed("layers", name, task.wait)
        lay = {"status": o.status}
        for k in ("F1", "F2", "F3", "F4", "F5"):
            lay[k] = sorted([f.get("layer")] + _box4(f["box"]) + [bool(f.get("info"))]
                            for f in o.findings.get(k, []))
        lay["devices"] = sorted(d["text"] for d in o.findings.get("devices", []))
        if o.status == 2:
            lay["reason"] = _reason(o.summary)
        rec["layers"] = lay
        rec["asserted"] = {"reads_nothing": o.rdb.count(CAT_READS_NOTHING)}
    except Exception as e:
        rec["layers"] = {"error": "%s: %s" % (type(e).__name__, e)}
    try:
        magic = case["set"] in P8_SETS
        task = portcheck.prepare(layout, layout.cell(case["top"]), CTX["cfg"], CTX["data"],
                                 {"magic": magic, "file": path})
        o = u.timed("ports", name, task.wait)
        rec["ports"] = {"status": o.status,
                        "findings": sorted([f["check"], f["cell"], f["layer"]] + _box4(f["box"])
                                           for f in o.findings.get("ports", [])),
                        "magic_ports": sorted(getattr(o, "magic_ports", None) or []) if magic else None}
        if o.status == 2:
            rec["ports"]["reason"] = _reason(o.summary)
    except Exception as e:
        rec["ports"] = {"error": "%s: %s" % (type(e).__name__, e)}
    u.records.setdefault("layers", {})[name] = rec


def work_case(case):
    """Every check of one case that is not on the sheet."""
    from klayout_magic_pcells import export
    u = Unit(case["name"])
    try:
        path = os.path.join(CTX["cases"], case["file"])
        st = case["set"]
        if st == "names" and case.get("klayout_name") == "does_not_exist":
            layout = export.load_layout(path)
            o = plugin_drc(u, layout, case["top"], "drc(full)", "hierarchical", case["name"], path)
            check_names(u, case, o)
            return u.as_dict()
        layout = export.load_layout(path)
        sts = ["drc(full)"] if st == "names" else styles()
        hier = {}
        empty_case = case["name"] in READS_NOTHING.get(CTX["pdk"], ())
        for style in sts:
            for mode in ("hierarchical", "flat"):
                o = plugin_drc(u, layout, case["top"], style, mode, case["name"], path)
                if empty_case:
                    check_reads_nothing_drc(u, case["name"], o, style, mode, case["top"])
                check_plumbing(u, case, o, mode, style)
                if mode == "hierarchical":
                    hier[style] = o
            if st != "names":
                check_fidelity(u, case, hier[style], style, path)
        if st == "names":
            check_names(u, case, hier["drc(full)"])
        else:
            native = run_native(u, path, [case["top"]], case["name"]).get(case["top"], {})
            native_record(u, case, native, hier)
        if st == "hier":
            check_hier(u, case, hier.get("drc(full)"), layout, path)
        if st == "inverters":
            check_lvs(u, case, layout, path)
        if st in LAYER_SETS:
            run_layers(u, case, layout, path)
    except Exception:
        u.errors.append("%s: %s" % (case["name"], traceback.format_exc()))
    return u.as_dict()


def work_layers(case):
    from klayout_magic_pcells import export
    u = Unit(case["name"] + " layers")
    try:
        path = os.path.join(CTX["cases"], case["file"])
        run_layers(u, case, export.load_layout(path), path)
    except Exception:
        u.errors.append("%s: %s" % (case["name"], traceback.format_exc()))
    return u.as_dict()


def work_sheet(style, sheet, cell_case):
    """The gaps cases as the sheet's cells, in one style: plumbing in both
    modes, fidelity, and the sheet's own counts."""
    from klayout_magic_pcells import export
    u = Unit("sheet %s" % style)
    try:
        path = os.path.join(CTX["cases"], sheet["file"])
        layout = export.load_layout(path)
        oh = plugin_drc(u, layout, sheet["top"], style, "hierarchical", "sheet", path)
        if oh.status != 2:
            # the D<case> cells Magic reads nothing in are the READS_NOTHING cases'
            known = set(UNLISTED.get(CTX["pdk"], ()))
            empty = sorted(c for c in (getattr(oh, "empty", None) or []) if c in cell_case and c not in known)
            want = sorted(c for c, n in cell_case.items() if n in READS_NOTHING.get(CTX["pdk"], ())
                          and c not in known)
            u.result("reads_nothing", "sheet (drc %s hierarchical)" % style, empty == want,
                     None if empty == want else {"empty": empty, "want": want}, cells=len(want))
        check_plumbing(u, sheet, oh, "hierarchical", style, reported_as=dict(cell_case, SHEET="sheet"))
        check_fidelity(u, sheet, oh, style, path, reported_as=dict(cell_case, SHEET="sheet"))
        of = plugin_drc(u, layout, sheet["top"], style, "flat", "sheet", path)
        check_plumbing(u, sheet, of, "flat", style, reported_as=cell_case)
        rec = {}
        if oh.status != 2:
            er = oh.export[next(iter(oh.export))]
            raw = next(iter(oh.raw.values()))
            rec["hierarchical"] = dict(collections.Counter(rule_of(w) for _c, w, _b in oh.rows))
            rec["top_only"] = dict(collections.Counter(rule_of(e.why) for e in raw.get(er.top, [])))
            per_cell = {}
            for fc, errs in raw.items():
                kn = er.klayout_name(fc)
                if kn in cell_case:
                    per_cell[cell_case[kn]] = dict(collections.Counter(rule_of(e.why) for e in errs))
            rec["per_case"] = per_cell
            rec["count_total_top"] = (next(iter(oh.counts.values())) or {}).get(er.top, 0)
        if of.status != 2:
            rec["flat"] = dict(collections.Counter(rule_of(w) for _c, w, _b in of.rows))
        u.records["sheet"] = {style: rec}
    except Exception:
        u.errors.append("sheet %s: %s" % (style, traceback.format_exc()))
    return u.as_dict()


def work_native(cases):
    """magic_native.tcl on the gaps cases' own files (or on the sheet's file
    for the sheet), up to BATCH files per process."""
    import klayout.db as db
    u = Unit("native %s" % cases[0]["name"])
    try:
        files = [os.path.join(CTX["cases"], c["file"]) for c in cases]
        names = []
        for f in files:
            ly = db.Layout()
            ly.read(f)
            names += [c.name for c in ly.each_cell()]
        if len(names) == len(set(names)):
            groups = [(files, cases)]
        else:      # two files hold a cell of the same name: one process each
            groups = [([f], [c]) for f, c in zip(files, cases)]
        got = {}
        for fs, cs in groups:
            got.update(run_native(u, fs, [c["top"] for c in cs], "batch_%s" % _safe(cs[0]["name"])))
        u.records["native_cells"] = {c["name"]: got.get(c["top"], {}) for c in cases}
    except Exception:
        u.errors.append("native on %s: %s" % (cases[0]["name"], traceback.format_exc()))
    return u.as_dict()


def work_readback(_arg=None):
    from tests.jobs import readback
    u = Unit("readback")
    try:
        work = os.path.join(CTX["out"], "readback")
        shutil.rmtree(work, ignore_errors=True)
        measured = u.timed("readback", "every device default", readback.measure_readback, CTX["cfg"], work)
        diffs = readback.differences(CTX["pdk"], measured)
        rows = readback.readback_rows(measured)
        u.result("readback", CTX["pdk"], not diffs, {"differences": diffs} if diffs else None,
                 measured=len(measured) - len(readback.unmeasured_of(measured)), differ=len(rows),
                 listed=[r["device"] for r in rows])
    except Exception:
        u.errors.append("readback: %s" % traceback.format_exc())
    return u.as_dict()


def work_gaps(_arg=None):
    u = Unit("gaps")
    try:
        lp = os.path.join(CTX["out"], "gaps_check.log")
        t0 = time.time()
        with open(lp, "w") as lf:
            p = subprocess.run([sys.executable, os.path.join(REPO, "tools", "build_gaps.py"), "--pdk", CTX["pdk"],
                                "--check", "--work", os.path.join(CTX["out"], "gaps")], cwd=REPO, env=CTX["env"],
                               stdin=subprocess.DEVNULL, stdout=lf, stderr=subprocess.STDOUT, timeout=3600)
        u.timing.append(("gaps", "build_gaps.py --check", round(time.time() - t0, 3)))
        with open(lp, errors="replace") as f:
            text = f.read()
        lines = [ln for ln in text.splitlines() if ln.startswith(("GAPS ", CTX["pdk"] + ":"))]
        u.result("gaps", CTX["pdk"], p.returncode == 0, None if p.returncode == 0 else
                 {"rc": p.returncode, "lines": lines[:20], "log": os.path.relpath(lp, CTX["out"])},
                 summary=lines[:3])
    except Exception:
        u.errors.append("gaps: %s" % traceback.format_exc())
    return u.as_dict()


def _dispatch(job):
    kind, arg = job
    return {"case": lambda: work_case(arg), "layers": lambda: work_layers(arg),
            "sheet": lambda: work_sheet(*arg), "native": lambda: work_native(arg),
            "readback": lambda: work_readback(), "gaps": lambda: work_gaps()}[kind]()


# --- the parent side -------------------------------------------------------------

def build_cases(pdk, out, quick, env, log):
    d = os.path.join(out, "cases")
    shutil.rmtree(d, ignore_errors=True)
    lp = os.path.join(out, "build_cases.log")
    cmd = [sys.executable, os.path.join(HERE, "build_cases.py"), "--pdk", pdk, "--out", d] + (
        ["--quick"] if quick else [])
    t0 = time.time()
    with open(lp, "w") as lf:
        p = subprocess.run(cmd, cwd=REPO, env=env, stdin=subprocess.DEVNULL, stdout=lf, stderr=subprocess.STDOUT,
                           timeout=1800)
    secs = round(time.time() - t0, 1)
    with open(lp, errors="replace") as f:
        text = f.read()
    if p.returncode != 0:
        raise RuntimeError("tests/jobs/build_cases.py failed (rc %d, %s):\n%s" % (p.returncode, lp, text[-3000:]))
    log("  " + next((ln for ln in text.splitlines() if ln.startswith("CASES")), "cases built"))
    with open(os.path.join(d, "cases.json"), encoding="utf-8") as f:
        return d, json.load(f), secs


def plan(doc, quick, pdk=None):
    """The units of work, the longest first."""
    cases = doc["cases"]
    jobs = []
    if quick:
        extra = QUICK_EXTRA.get(pdk or doc.get("pdk"), ())
        picked = [c for c in cases if c["set"] == "inverters"] + [c for c in cases if c["name"] in extra]
        missing = sorted(set(extra) - {c["name"] for c in picked})
        if missing:
            raise RuntimeError("the quick set's cases %s are not in cases.json" % missing)
        return [("case", c) for c in picked], {}
    sheet = next((c for c in cases if c["set"] == "sheet"), None)
    cell_case = {}
    if sheet is not None:
        cell_case = {"D" + t: t for t in sheet.get("cases", [])}
        by_top = {c["top"]: c["name"] for c in cases if c["set"] == "gaps"}
        cell_case = {k: by_top.get(v, v) for k, v in cell_case.items()}
        for style in ("drc(full)", "drc(routing)", "drc(fast)"):
            jobs.append(("sheet", (style, sheet, cell_case)))
        jobs.append(("native", [sheet]))
    jobs.append(("gaps", None))
    jobs.append(("readback", None))
    for c in cases:
        if c["set"] in ("gaps", "sheet"):
            continue
        jobs.append(("case", c))
    gaps = [c for c in cases if c["set"] == "gaps"]
    for ch in chunks(gaps):
        jobs.append(("native", ch))
    for c in gaps:
        jobs.append(("layers", c))
    return jobs, cell_case


def _no_f1_f4(lay):
    if "error" in lay:
        return ["the layers job failed: %s" % lay["error"]]
    if lay.get("status") == 2:
        return ["the layers job failed (status 2)"]
    return ["%s %s" % (k, item) for k in ("F1", "F2", "F3", "F4") for item in lay.get(k, []) if not item[-1]]


def asserted_layers(pdk, name, rec, controls):
    """The layers findings asserted in code, never taken from the baseline:
    {check: [problems]} for the checks that apply to ``name``."""
    lay = rec.get("layers") or {}
    out = {}
    if name in controls:
        out["controls"] = _no_f1_f4(lay)
    pos = F1_POSITIVES.get(pdk, {})
    if name in pos:
        if "error" in lay or lay.get("status") == 2:
            out["f1_positives"] = ["the layers job failed: %s" % (lay.get("error") or lay.get("reason"))]
        elif not any(item[0] == pos[name] for item in lay.get("F1", [])):
            out["f1_positives"] = ["no F1 on %s (F1: %s)" % (pos[name], lay.get("F1", []))]
        else:
            out["f1_positives"] = []
    n = (rec.get("asserted") or {}).get("reads_nothing", 0)
    if name in READS_NOTHING.get(pdk, ()):
        bad = []
        if "error" in lay or lay.get("status") != 1:
            bad.append("layers gave status %s, not 1: %s" % (lay.get("status"), lay.get("error") or
                                                              lay.get("reason")))
        bad += _no_f1_f4(lay) if "error" not in lay and lay.get("status") != 2 else []
        if not n:
            bad.append("no %r item" % CAT_READS_NOTHING)
        out["reads_nothing"] = bad
    elif n:
        out["reads_nothing"] = ["%d %r items on a case Magic reads" % (n, CAT_READS_NOTHING)]
    return out


def asserted_ports(name, rec, expect):
    """ports_expect: the P checks equal cases.json's expect.ports."""
    if "ports" not in (expect or {}):
        return None
    po = rec.get("ports") or {}
    if "error" in po:
        return ["the ports check raised: %s" % po["error"]]
    got = sorted({f[0] for f in po.get("findings", [])})
    return [] if got == sorted(set(expect["ports"])) else ["P checks %s, expected %s" % (got, expect["ports"])]


def compare_baseline(pdk, layers, cases, quick, update, section):
    """layers/ports against expected-<pdk>.json; the negative controls, the
    F1 positives, the cells Magic reads nothing in and expect.ports in code."""
    path = expected_path(pdk)
    old = {}
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            old = json.load(f).get("cases", {})
    controls = {c["name"] for c in cases if c.get("negative_control")}
    if quick:
        # the controls set's inv_control is the inverters set's inv
        controls |= {c["name"] for c in cases if c["set"] == "inverters" and c["file"] == "inverters/inv.gds"}
    expects = {c["name"]: c.get("expect") or {} for c in cases}
    results = []
    new = {}
    for name in sorted(layers):
        rec = layers[name]
        base = {k: rec[k] for k in ("layers", "ports") if k in rec}
        lay_bad = []
        for check, bad in sorted(asserted_layers(pdk, name, rec, controls).items()):
            results.append({"check": check, "case": name, "ok": not bad,
                            "detail": {"findings": bad[:MAX_DETAIL]} if bad else None})
            lay_bad += ["%s: %s" % (check, b) for b in bad]
        port_bad = asserted_ports(name, rec, expects.get(name))
        if port_bad is not None:
            results.append({"check": "ports_expect", "case": name, "ok": not port_bad,
                            "detail": {"findings": port_bad} if port_bad else None})
        new[name] = dict(base)
        if lay_bad:
            new[name]["layers"] = {"error": "not written: %s" % "; ".join(lay_bad)[:300]}
        if port_bad:
            new[name]["ports"] = {"error": "not written: %s" % "; ".join(port_bad)[:300]}
        if update:
            for k in ("layers", "ports"):
                got = rec.get(k) or {}
                if name not in controls and "error" in got:
                    results.append({"check": k, "case": name, "ok": False,
                                    "detail": "the %s check raised: %s" % (k, got["error"])})
            continue
        want = old.get(name)
        for k in ("layers", "ports"):
            got = rec.get(k)
            if got is None or "error" in got:
                # an exception never passes by equality with a baseline that holds the same one
                results.append({"check": k, "case": name, "ok": False,
                                "detail": "the %s check raised: %s" % (k, (got or {}).get("error"))})
                continue
            if want is None or k not in want:
                results.append({"check": k, "case": name, "ok": False,
                                "detail": "not in tests/jobs/expected-%s.json (run with --update-baseline)" % pdk})
                continue
            ok = got == want[k]
            detail = None
            if not ok:
                detail = {}
                for kk in sorted(set(got or {}) | set(want[k] or {})):
                    a, b = (got or {}).get(kk), (want[k] or {}).get(kk)
                    if a != b:
                        detail[kk] = {"run": a, "baseline": b}
            results.append({"check": k, "case": name, "ok": ok, "detail": detail})
    if not quick:
        # a positive that did not run is a loss too
        for name in sorted(set(F1_POSITIVES.get(pdk, {})) - set(layers)):
            results.append({"check": "f1_positives", "case": name, "ok": False,
                            "detail": "the case did not run (not in the layers results)"})
    if update:
        merged = dict(old) if quick else {}
        merged.update(new)
        doc = {"schema": 1, "pdk": pdk,
               "comment": "Findings of the plugin's layers and ports checks on the case suite, per case "
                          "(F1 to F5 as [layer, l, b, r, t, information], boxes in um; ports as [check, cell, "
                          "layer, l, b, r, t]). Written by tests/jobs/run_jobs.py --update-baseline "
                          "(run_sweep.py --update-baseline). The negative controls' F1 to F4 lists are "
                          "asserted empty in code, and the GAPS F1 positives, the cells Magic reads nothing "
                          "in and cases.json's expect.ports are asserted there too; a case that fails one "
                          "of them is never written here as it ran.",
               "cases": {k: merged[k] for k in sorted(merged)}}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(doc, f, indent=1, ensure_ascii=False)
            f.write("\n")
        section["baseline_written"] = os.path.relpath(path, REPO)
    return results


def check_coverage(pdk, jobs, cell_case, units):
    """drc_coverage: every case the plan ran has a plumbing result for each
    style and mode and a fidelity result for each style; each gaps case of
    the sheet has its hierarchical plumbing and fidelity results in each
    style, and the sheet's flat check one per style. Missing results fail."""
    from klayout_magic_pcells import pdkdata
    sts = [s for s in pdkdata.load(pdk).drc.get("styles", []) if s.startswith("drc(")]
    plumb, fid = set(), set()
    for u in units:
        for r in u["results"]:
            if r["check"] == "drc_plumbing":
                plumb.add((r["case"], r.get("style"), r.get("mode")))
            elif r["check"] == "drc_fidelity":
                fid.add((r["case"], r.get("style")))
    want = collections.OrderedDict()
    for kind, arg in jobs:
        if kind != "case":
            continue
        if arg["set"] == "names":
            if arg.get("klayout_name") == "does_not_exist":
                continue
            want[arg["name"]] = [("plumbing", "drc(full)", m) for m in ("hierarchical", "flat")]
        else:
            want[arg["name"]] = [("plumbing", s, m) for s in sts for m in ("hierarchical", "flat")] + [
                ("fidelity", s, None) for s in sts]
    if cell_case:
        for n in sorted(set(cell_case.values())):
            want.setdefault(n, []).extend([("plumbing", s, "hierarchical") for s in SHEET_STYLES] +
                                          [("fidelity", s, None) for s in SHEET_STYLES])
        want.setdefault("sheet (flat)", []).extend(("plumbing", s, "flat") for s in SHEET_STYLES)
    out = []
    for name, need in want.items():
        miss = [[k, s, m] for k, s, m in need if ((name, s, m) not in plumb if k == "plumbing" else
                                                  (name, s) not in fid)]
        out.append({"check": "drc_coverage", "case": name, "ok": not miss,
                    "detail": {"missing": miss[:MAX_DETAIL], "n_missing": len(miss)} if miss else None})
    return out


def summarize(section, units):
    counts = {c: {"pass": 0, "fail": 0} for c in CHECKS}
    failures, timing = [], collections.OrderedDict()
    native, sheet, layers = {}, {}, {}
    cpu = 0.0
    for u in units:
        for r in u["results"]:
            c = counts.setdefault(r["check"], {"pass": 0, "fail": 0})
            c["pass" if r["ok"] else "fail"] += 1
            if not r["ok"]:
                failures.append(r)
        for kind, label, secs in u["timing"]:
            t = timing.setdefault(kind, {"jobs": 0, "seconds": 0.0, "max": 0.0, "max_label": ""})
            t["jobs"] += 1
            t["seconds"] = round(t["seconds"] + secs, 3)
            if secs > t["max"]:
                t["max"], t["max_label"] = secs, label
            cpu += secs
        native.update(u["records"].get("native", {}))
        for st, rec in (u["records"].get("sheet") or {}).items():
            sheet[st] = rec
        layers.update(u["records"].get("layers", {}))
        section["errors"].extend(u["errors"])
    section["checks"] = counts
    section["failures"] = failures
    # every result of the small checks, for the report
    section["results"] = sorted((r for u in units for r in u["results"] if r["check"] in KEEP_RESULTS),
                                key=lambda r: (r["check"], r["case"]))
    section["timing"] = timing
    section["timing_detail"] = sorted(([k, lab, sec] for u in units for k, lab, sec in u["timing"]),
                                      key=lambda t: (t[0], t[1]))
    section["job_seconds"] = round(cpu, 1)
    section["native"] = native
    if sheet:
        section["sheet"] = sheet
    return layers


def native_on_sheet(section, units):
    """The gaps cases' (and the sheet's) magic_native.tcl results against
    the plugin's listings from the sheet runs: per case, the plugin's
    listing of that case's cell; for the sheet, its hierarchical rows."""
    cells = {}
    for u in units:
        cells.update(u["records"].get("native_cells") or {})
    sheet = section.get("sheet") or {}
    for name, styles_ in cells.items():
        rec = {}
        for style, n in styles_.items():
            s = sheet.get(style) or {}
            plugin = s.get("hierarchical") if name == "sheet" else (s.get("per_case") or {}).get(name, {})
            if plugin is None:
                continue
            diff = {r: [n["rules"].get(r, 0), plugin.get(r, 0)]
                    for r in sorted(set(n["rules"]) | set(plugin)) if n["rules"].get(r, 0) != plugin.get(r, 0)}
            rec[style] = {"native_count_total": n["total"], "native_boxes": sum(n["rules"].values()),
                          "plugin_boxes": sum(plugin.values()), "rules_differ": diff}
        section["native"][name] = rec


def run_step(pdk, out, quick=False, update_baseline=False, workers=1, keep=False, log=log_default, env=None):
    """Run the jobs step into ``out``; returns its report section."""
    t0 = time.time()
    os.makedirs(out, exist_ok=True)
    env = dict(env or os.environ, KMP_PDK=pdk, KMP_PDKS=pdk, PDK=pdk,
               KMP_CACHE_DIR=os.path.join(out, "cache-build"))
    section = {"pdk": pdk, "quick": quick, "errors": [], "workers": workers}
    log("jobs: building the case suite%s" % (" (inverters, gaps and controls sets)" if quick else ""))
    cases_dir, doc, build_secs = build_cases(pdk, out, quick, env, log)
    section["cases"] = collections.Counter(c["set"] for c in doc["cases"])
    jobs, cell_case = plan(doc, quick, pdk)
    section["units"] = len(jobs)
    log("jobs: %d units of work on %d worker%s" % (len(jobs), workers, "" if workers == 1 else "s"))
    ctx = multiprocessing.get_context("fork")
    units = []
    with ctx.Pool(workers, initializer=_init, initargs=(pdk, out, cases_dir)) as pool:
        for i, u in enumerate(pool.imap_unordered(_dispatch, jobs)):
            units.append(u)
            if u["errors"]:
                log("  %s: ERROR %s" % (u["name"], u["errors"][0].splitlines()[0]))
            bad = [r for r in u["results"] if not r["ok"]]
            if bad:
                log("  %s: %d failed (%s)" % (u["name"], len(bad), ", ".join(sorted({r["check"] for r in bad}))))
    units.sort(key=lambda x: x["name"])
    layers = summarize(section, units)
    if cell_case:
        native_on_sheet(section, units)
    for r in check_coverage(pdk, jobs, cell_case, units) + compare_baseline(pdk, layers, doc["cases"], quick,
                                                                             update_baseline, section):
        c = section["checks"].setdefault(r["check"], {"pass": 0, "fail": 0})
        c["pass" if r["ok"] else "fail"] += 1
        if not r["ok"]:
            section["failures"].append(r)
    section["timing"]["build"] = {"jobs": 1, "seconds": build_secs, "max": build_secs,
                                  "max_label": "tests/jobs/build_cases.py"}
    if quick:
        for c in ("readback", "gaps"):
            section["checks"][c]["skipped"] = "quick"
    section["fail"] = sum(v["fail"] for v in section["checks"].values())
    section["ok"] = not section["fail"] and not section["errors"]
    section["seconds"] = round(time.time() - t0, 1)
    section["cpu_seconds_estimate"] = round(section["job_seconds"] + build_secs, 1)
    with open(os.path.join(out, "jobs.json"), "w", encoding="utf-8") as f:
        json.dump(section, f, indent=1, default=list)
        f.write("\n")
    if section["ok"] and not keep:
        for d in ("cache", "cache-build", "cases", "ref", "native", "plugin", "readback", "gaps"):
            shutil.rmtree(os.path.join(out, d), ignore_errors=True)
    log("jobs: %s in %.1f s (%.1f s of jobs)" % ("PASS" if section["ok"] else "FAIL", section["seconds"],
                                                section["job_seconds"]))
    return section


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--pdk", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--quick", action="store_true",
                    help="the inverters set and the QUICK_EXTRA cases; no readback or gaps")
    ap.add_argument("--update-baseline", action="store_true", help="rewrite tests/jobs/expected-<pdk>.json")
    ap.add_argument("--jobs", type=int, default=max(1, min(6, os.cpu_count() or 1)))
    ap.add_argument("--keep", action="store_true", help="keep the cases, job directories and logs")
    a = ap.parse_args(argv)
    try:
        s = run_step(a.pdk, os.path.abspath(a.out), a.quick, a.update_baseline, a.jobs, a.keep)
    except Exception:
        traceback.print_exc()
        return 2
    for c, v in s["checks"].items():
        print("%-14s pass %4d  fail %4d%s" % (c, v["pass"], v["fail"], "  (%s)" % v["skipped"] if "skipped" in v
                                                else ""))
    for f in s["failures"][:40]:
        print("FAIL %s %s %s" % (f["check"], f["case"], json.dumps(f.get("detail"), default=str)[:300]))
    for e in s["errors"]:
        print("ERROR " + e)
    print("JOBS %s %s" % ("PASS" if s["ok"] else "FAIL", a.pdk))
    return 0 if s["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
