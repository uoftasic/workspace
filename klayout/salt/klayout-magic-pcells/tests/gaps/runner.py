"""The runs behind the gap table (tools/build_gaps.py), in the pinned image.

Two kinds of runs:

- **Inventory.** Each KLayout deck that the table lists runs once on a
  one-box layout; the report's category names are the deck's rule list
  under those switches, and the category descriptions give the values. The
  descriptions are deck text, so only the parsed value leaves this module.
- **Tests.** The case suite's ``gaps`` set (tests/cases/build.py), checked
  by Magic per cell in all three styles, at most 15 cells per process, and
  by KLayout once on the suite's sheet (each case a ``D<case>`` cell, 40 um
  apart), through tests/parity/drc.py's runner; on sky130A also with the
  menu's switches and with sky130A.lydrc's FEOL on.

Everything here needs the image (Magic, KLayout, the PDKs); the join and
the tables in tools/build_gaps.py do not.
"""

import collections
import glob
import html
import json
import os
import re
import shutil
import subprocess
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
for _p in (REPO, os.path.join(REPO, "python")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from tests.parity import drc as harness  # noqa: E402  (PROFILES and the runner stay there)

MAGIC_TCL = os.path.join(HERE, "magic_why.tcl")
BUILD_CASES = os.path.join(REPO, "tests", "cases", "build.py")
MAX_CELLS = 15
LYDRC = "libs.tech/klayout/drc/sky130A.lydrc"
MR = "libs.tech/klayout/drc/sky130A_mr.drc"

# The menu's Run DRC (Full) sets only these (macros/run_drc_full.lydrc:32-34).
MENU_FLAGS = {"feol": "true", "beol": "true", "offgrid": "true"}


def batches(items, n=MAX_CELLS):
    try:
        from klayout_magic_pcells.jobs import batches as jb
        return jb(items, n)
    except Exception:  # pragma: no cover - jobs.py imports the plugin's backend
        items = list(items)
        return [items[i:i + n] for i in range(0, len(items), n)]


def pdk_root():
    return harness.PDK_ROOT


# ---------------------------------------------------------------------------
# KLayout runs


def runs(pdk):
    """The KLayout runs of a PDK: [{"id", "deck", "primary", "what"}].

    ``deck`` names the deck the run uses (the KLayout column of the table);
    ``primary`` marks the runs the status is computed against.
    """
    p = harness.PROFILES[pdk]
    if pdk == "sky130A":
        return [
            {"id": "harness", "deck": "sky130A_mr.drc", "primary": True,
             "what": "sky130A_mr.drc with the harness's switches (%s)"
                     % ", ".join("%s=%s" % kv for kv in sorted(p["flags"].items()))},
            {"id": "menu", "deck": "sky130A_mr.drc", "primary": True,
             "what": "sky130A_mr.drc with the switches of Efabless sky130 > Run DRC (Full) (%s)"
                     % ", ".join("%s=%s" % kv for kv in sorted(MENU_FLAGS.items()))},
            {"id": "lydrc", "deck": "sky130A.lydrc", "primary": False,
             "what": "sky130A.lydrc as shipped (FEOL = false)"},
            {"id": "lydrc_feol", "deck": "sky130A.lydrc", "primary": False,
             "what": "sky130A.lydrc with FEOL = true"},
        ]
    if p["kind"] == "deck":
        return [{"id": "harness", "deck": os.path.basename(p["deck"]), "primary": True,
                 "what": "%s with the harness's switches (%s)"
                         % (os.path.basename(p["deck"]),
                            ", ".join("%s=%s" % kv for kv in sorted(p["flags"].items())))}]
    return [{"id": "harness", "deck": "run_drc.py", "primary": True,
             "what": "run_drc.py --no_density --mp=1 --density_thr=1 (main and maximal decks, merged)"}]


def deck_files(pdk):
    """{deck label: [(path under the PDK, absolute path), ...]} for the text scan."""
    root = os.path.join(pdk_root(), pdk)

    def rel(paths):
        return [(os.path.relpath(a, root), a) for a in paths]

    if pdk == "sky130A":
        return {"sky130A_mr.drc": rel([os.path.join(root, MR)]),
                "sky130A.lydrc": rel([os.path.join(root, LYDRC)])}
    if pdk == "gf180mcuD":
        d = os.path.join(root, "libs.tech/klayout/tech/drc")
        return {"gf180mcu.drc": rel([os.path.join(d, "gf180mcu.drc")]
                                    + sorted(glob.glob(os.path.join(d, "rule_decks", "*.rb"))))}
    d = os.path.join(root, "libs.tech/klayout/tech/drc")
    main = [os.path.join(d, pdk + ".drc")]
    for sub in ("feol", "beol", "pin", "geometry", "forbidden"):
        main += sorted(glob.glob(os.path.join(d, "rule_decks", sub, "*.drc")))
    maximal = sorted(glob.glob(os.path.join(d, "rule_decks", "*_maximal.drc")))
    return {"main": rel([m for m in main if os.path.isfile(m)]), "maximal": rel(maximal)}


def _lydrc_text(path, feol):
    t = html.unescape(open(path, encoding="utf-8").read())
    m = re.search(r"<text>(.*)</text>", t, re.S)
    if not m:
        raise RuntimeError("no <text> in %s" % path)
    t = m.group(1)
    if feol:
        new, n = re.subn(r"^(FEOL\s*=\s*)false\b", r"\1true", t, count=1, flags=re.M)
        if n != 1:
            raise RuntimeError("cannot switch FEOL on in %s" % path)
        t = new
    return t


def run_klayout(pdk, run, gds, top, workdir, timeout=3600):
    """Run one KLayout run on ``gds``; return the report path."""
    os.makedirs(workdir, exist_ok=True)
    report = os.path.join(workdir, run["id"] + ".lyrdb")
    log = os.path.join(workdir, run["id"] + ".log")
    if os.path.exists(report):
        os.remove(report)
    root = os.path.join(pdk_root(), pdk)
    if run["id"] == "harness":
        harness.run_klayout_drc(gds, top, report, log, pdk=pdk, timeout=timeout)
        return report
    if run["id"] == "menu":
        cmd = ["klayout", "-b", "-r", os.path.join(root, MR), "-rd", "input=" + gds,
               "-rd", "top_cell=" + top, "-rd", "report=" + report]
        for k, v in sorted(MENU_FLAGS.items()):
            cmd += ["-rd", "%s=%s" % (k, v)]
    else:
        # sky130A.lydrc is a macro file; its DSL text runs as a .drc script.
        # The copy (with FEOL switched on for lydrc_feol) stays in workdir.
        script = os.path.join(workdir, run["id"] + ".drc")
        with open(script, "w", encoding="utf-8") as f:
            f.write(_lydrc_text(os.path.join(root, LYDRC), run["id"] == "lydrc_feol"))
        cmd = ["klayout", "-b", "-r", script, "-rd", "input=" + gds, "-rd", "report=" + report]
    with open(log, "w") as lf:
        r = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT, timeout=timeout, cwd=workdir)
    if not os.path.isfile(report):
        raise RuntimeError("KLayout run %s failed (status %d), see %s" % (run["id"], r.returncode, log))
    return report


def categories(report):
    """{name: description} of every category in a report, nested names
    joined with '.'. The description is deck text: callers keep only the
    value they parse from it."""
    import klayout.db  # noqa: F401
    import klayout.rdb as rdb
    d = rdb.ReportDatabase("")
    d.load(report)
    out = {}

    def walk(cats, prefix):
        for c in cats:
            name = prefix + c.name()
            out.setdefault(name, c.description)
            walk(c.each_sub_category(), name + ".")

    walk(d.each_category(), "")
    return out


def one_box(path):
    """A layout with one 1 um box on a metal layer: enough for every deck to run."""
    import klayout.db as db
    ly = db.Layout()
    ly.dbu = 0.001
    c = ly.create_cell("GAPS_ONE_BOX")
    c.shapes(ly.layer(68, 20)).insert(db.DBox(0, 0, 1, 1))
    opts = db.SaveLayoutOptions()
    opts.write_context_info = False
    opts.gds2_write_timestamps = False
    ly.write(path, opts)
    return "GAPS_ONE_BOX"


def inventory(pdk, workdir, value_of):
    """{run id: {category name: (value, unit)}} from each run on one box.
    ``value_of(description)`` parses the value; the description is dropped."""
    os.makedirs(workdir, exist_ok=True)
    gds = os.path.join(workdir, "one_box.gds")
    top = one_box(gds)
    out = {}
    for run in runs(pdk):
        rep = run_klayout(pdk, run, gds, top, os.path.join(workdir, "inv"))
        out[run["id"]] = {n: value_of(d) for n, d in categories(rep).items()}
    return out


# ---------------------------------------------------------------------------
# Tests


def build_cases(pdk, out):
    """Build the case suite's gaps and sheet sets; return cases.json."""
    cmd = [sys.executable, BUILD_CASES, "--pdk", pdk, "--out", out, "--set", "gaps", "--set", "sheet",
           "--no-pcell"]
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
    if r.returncode != 0:
        raise RuntimeError("tests/cases/build.py failed:\n" + r.stdout[-2000:])
    with open(os.path.join(out, "cases.json"), encoding="utf-8") as f:
        return json.load(f)


def _cell_names(path):
    import klayout.db as db
    ly = db.Layout()
    ly.read(path)
    return {c.name for c in ly.each_cell()}


def _magic_batches(pdk, items):
    """Split [(top, gds)] into groups of at most 15 whose files share no
    cell name, so that one Magic process can read them all."""
    groups = []
    for chunk in batches(items, MAX_CELLS):
        cur, names = [], set()
        for top, gds in chunk:
            cn = _cell_names(gds)
            if cur and names & cn:
                groups.append(cur)
                cur, names = [], set()
            cur.append((top, gds))
            names |= cn
        if cur:
            groups.append(cur)
    return groups


def magic_cases(pdk, items, styles, workdir, workers=3, timeout=1800):
    """Magic's DRC on each case cell, per style.

    ``items`` is [(top, gds path)]. Returns {top: {style: {why-text: boxes}}};
    a style with {} was checked and gave nothing."""
    os.makedirs(workdir, exist_ok=True)
    groups = _magic_batches(pdk, items)
    results = {}
    errors = []
    lock = threading.Lock()
    queue = list(enumerate(groups))

    def work():
        while True:
            with lock:
                if not queue:
                    return
                i, grp = queue.pop(0)
            tsv = os.path.join(workdir, "magic_%03d.tsv" % i)
            log = os.path.join(workdir, "magic_%03d.log" % i)
            env = dict(os.environ, KMP_FILES=" ".join(g for _, g in grp),
                       KMP_CELLS=" ".join(t for t, _ in grp), KMP_STYLES=" ".join(styles), KMP_OUT=tsv)
            cmd = ["magic", "-dnull", "-noconsole", "-rcfile", harness.magicrc(pdk), MAGIC_TCL]
            with open(log, "w") as lf:
                subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=lf, stderr=subprocess.STDOUT,
                               env=env, timeout=timeout, cwd=workdir)
            with open(log, errors="replace") as lf:
                done = "GAPS_CELLS_DONE" in lf.read()
            got = {}
            if done and os.path.isfile(tsv):
                with open(tsv, encoding="utf-8", errors="replace") as f:
                    for line in f:
                        parts = line.rstrip("\n").split("\t", 3)
                        if len(parts) != 4:
                            continue
                        cell, st, n, why = parts
                        d = got.setdefault(cell, {}).setdefault(st, {})
                        if why:
                            d[why] = d.get(why, 0) + int(n)
            with lock:
                if not done:
                    errors.append("Magic batch %d did not finish, see %s" % (i, log))
                results.update(got)

    threads = [threading.Thread(target=work) for _ in range(max(1, workers))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    if errors:
        raise RuntimeError("; ".join(errors))
    missing = [t for t, _ in items if t not in results]
    if missing:
        raise RuntimeError("Magic checked no style of %s" % ", ".join(missing[:5]))
    return results


def assign(markers, placed, margin=20.0):
    """{case: {category: markers}} from a sheet report; a marker belongs to
    the case whose D<case> cell holds it, or whose placed box (grown by
    ``margin`` um) holds its centre."""
    per = collections.defaultdict(collections.Counter)
    boxes = [(pid, b) for pid, b in placed.items() if b]
    unassigned = 0
    for rule, cell, box in markers:
        hit = None
        if cell and cell.startswith("D") and cell[1:] in placed:
            hit = cell[1:]
        elif box:
            cx, cy = (box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0
            for pid, (bl, bb, br, bt) in boxes:
                if bl - margin <= cx <= br + margin and bb - margin <= cy <= bt + margin:
                    hit = pid
                    break
        if hit is None:
            unassigned += 1
            continue
        per[hit][rule] += 1
    return {k: dict(v) for k, v in per.items()}, unassigned


def klayout_sheet(pdk, sheet_gds, workdir):
    """{run id: {case top: {category: markers}}} from each run on the sheet."""
    with open(sheet_gds + ".json", encoding="utf-8") as f:
        placed = json.load(f)["placed"]
    out = {}
    for run in runs(pdk):
        rep = run_klayout(pdk, run, sheet_gds, "SHEET", os.path.join(workdir, "sheet"))
        per, _ = assign(harness.parse_rdb(rep), placed)
        out[run["id"]] = per
    return out


def tool_versions():
    """{"magic": ..., "klayout": ...} as the tools print them."""
    out = {}
    for name, cmd in (("magic", ["magic", "--version"]), ("klayout", ["klayout", "-v"])):
        try:
            r = subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, universal_newlines=True, timeout=60)
            out[name] = r.stdout.strip().splitlines()[-1].strip() if r.stdout.strip() else None
        except Exception:
            out[name] = None
    return out


def tests(pdk, workdir, styles):
    """Build the cases and run both engines. Returns
    {"cases": [case records of the gaps set], "magic": {top: {style: {why: n}}},
     "klayout": {run: {top: {category: n}}}}."""
    cdir = os.path.join(workdir, "cases")
    shutil.rmtree(cdir, ignore_errors=True)
    cases = build_cases(pdk, cdir)
    gaps = [c for c in cases["cases"] if c["set"] == "gaps"]
    sheet = [c for c in cases["cases"] if c["set"] == "sheet"]
    if not sheet:
        raise RuntimeError("the case suite built no sheet for %s" % pdk)
    items = [(c["top"], os.path.join(cdir, c["file"])) for c in gaps]
    magic = magic_cases(pdk, items, styles, os.path.join(workdir, "magic"))
    kl = klayout_sheet(pdk, os.path.join(cdir, sheet[0]["file"]), workdir)
    return {"cases": gaps, "magic": magic, "klayout": kl}
