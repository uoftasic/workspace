"""DRC and extraction runners for the parity harness, per PDK.

KLayout runs the PDK's own deck from the PDK install:

- sky130A: ``sky130A_mr.drc`` with feol, beol and offgrid on (without feol
  and beol the deck checks nothing), floating_met off and seal off;
- gf180mcuD: ``gf180mcu.drc`` with ``decks=all,-density`` (a bare
  ``-density`` selects no deck at all) and variant D;
- ihp-sg13g2 and ihp-sg13cmos5l: the PDK's ``run_drc.py`` with
  ``--no_density`` and one process, which runs the main and maximal rule
  decks and merges their reports.

The decks exit 0 or 1 whatever they find, so results come from the report
database. Magic runs ``mdrc.tcl`` (drc(full) with drc catchup, or the style
``KMP_STYLE`` names) with the PDK's rcfile. Only sets of rule IDs are
compared, never counts, and never Magic's IDs against KLayout's.
"""

import glob
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PDK_ROOT = os.environ.get("PDK_ROOT", "/foss/pdks")

PROFILES = {
    "sky130A": {"kind": "deck", "deck": "libs.tech/klayout/drc/sky130A_mr.drc", "top": "top_cell",
                "flags": {"feol": "true", "beol": "true", "offgrid": "true", "floating_met": "false",
                          "seal": "false", "thr": "1"}},
    "gf180mcuD": {"kind": "deck", "deck": "libs.tech/klayout/tech/drc/gf180mcu.drc", "top": "topcell",
                  "flags": {"decks": "all,-density", "variant": "D", "threads": "1",
                            "run_mode": "deep"}},
    "ihp-sg13g2": {"kind": "ihp", "runner": "libs.tech/klayout/tech/drc/run_drc.py"},
    "ihp-sg13cmos5l": {"kind": "ihp", "runner": "libs.tech/klayout/tech/drc/run_drc.py"},
}


def profile(pdk):
    """The KLayout DRC setup for a PDK, or None when the image has no deck."""
    p = PROFILES.get(pdk)
    if p is None:
        return None
    path = os.path.join(PDK_ROOT, pdk, p.get("deck") or p.get("runner"))
    if not os.path.isfile(path):
        return None
    return dict(p, path=path, pdk=pdk)


def describe(pdk):
    p = profile(pdk)
    if p is None:
        return "no KLayout DRC deck in the image"
    if p["kind"] == "deck":
        return "%s with %s" % (os.path.basename(p["path"]),
                               ", ".join("%s=%s" % kv for kv in sorted(p["flags"].items())))
    return "%s --no_density --mp=1 --density_thr=1" % os.path.basename(p["path"])


def magicrc(pdk):
    return os.path.join(PDK_ROOT, pdk, "libs.tech", "magic", pdk + ".magicrc")


_RULE_RE = re.compile(r"\(([^()]*)\)\s*$")


def magic_rule_id(message):
    m = _RULE_RE.search(message.strip())
    return m.group(1).strip() if m else message.strip()


def run_klayout_drc(gds, top, report, log_path, pdk="sky130A", timeout=3600):
    p = profile(pdk)
    if p is None:
        raise RuntimeError("no KLayout DRC deck for %s" % pdk)
    if p["kind"] == "deck":
        cmd = ["klayout", "-b", "-r", p["path"], "-rd", "input=" + gds, "-rd",
               "%s=%s" % (p["top"], top), "-rd", "report=" + report]
        for k, v in p["flags"].items():
            cmd += ["-rd", "%s=%s" % (k, v)]
        with open(log_path, "w") as lf:
            r = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT, timeout=timeout)
        if not os.path.isfile(report):
            raise RuntimeError("KLayout DRC failed (status %d), see %s" % (r.returncode, log_path))
        return parse_rdb(report)
    run_dir = report + ".d"
    shutil.rmtree(run_dir, ignore_errors=True)
    os.makedirs(run_dir)
    # One process and one thread: the harness runs several sheets at once,
    # and the maximal deck with the default thread count (one per CPU)
    # crashed KLayout 0.30.11 once with signal 11 (it passed when run again).
    cmd = [sys.executable, p["path"], "--path=" + gds, "--topcell=" + top, "--run_dir=" + run_dir,
           "--no_density", "--mp=1", "--density_thr=1"]
    with open(log_path, "w") as lf:
        r = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT, timeout=timeout, cwd=run_dir)
    found = glob.glob(os.path.join(run_dir, "*_full.lyrdb"))
    if not found:
        raise RuntimeError("KLayout DRC (%s) wrote no report (status %d), see %s"
                           % (os.path.basename(p["path"]), r.returncode, log_path))
    shutil.copyfile(found[0], report)
    shutil.rmtree(run_dir, ignore_errors=True)
    return parse_rdb(report)


def _value_bbox(v):
    for test, get in (("is_box", "box"), ("is_polygon", "polygon"), ("is_edge_pair", "edge_pair"),
                      ("is_edge", "edge"), ("is_path", "path"), ("is_text", "text")):
        if hasattr(v, test) and getattr(v, test)():
            shape = getattr(v, get)()
            b = shape.bbox()
            return [b.left, b.bottom, b.right, b.top]
    return None


def parse_rdb(path):
    """[(rule, cell, [l, b, r, t] um), ...] from a KLayout report database.

    The deck runs hierarchically, so a marker found inside a device cell is
    reported in that cell, in the cell's own coordinates.
    """
    import klayout.db  # noqa: F401  (binds the db types that rdb values return)
    import klayout.rdb as rdb
    db = rdb.ReportDatabase("")
    db.load(path)
    out = []
    for item in db.each_item():
        cat = db.category_by_id(item.category_id())
        name = cat.name()
        cell = db.cell_by_id(item.cell_id()).name()
        box = None
        for v in item.each_value():
            b = _value_bbox(v)
            if b is None:
                continue
            box = b if box is None else [min(box[0], b[0]), min(box[1], b[1]),
                                         max(box[2], b[2]), max(box[3], b[3])]
        out.append((name, cell, box))
    return out


def run_magic_drc(gds, top, out_tsv, log_path, pdk="sky130A", timeout=3600, style=None):
    env = dict(os.environ, KMP_GDS=gds, KMP_TOP=top, KMP_OUT=out_tsv)
    env.pop("KMP_CELLS", None)
    if style:
        env["KMP_STYLE"] = style
    cmd = ["magic", "-dnull", "-noconsole", "-rcfile", magicrc(pdk), os.path.join(HERE, "mdrc.tcl")]
    with open(log_path, "w") as lf:
        p = subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=lf, stderr=subprocess.STDOUT,
                           env=env, timeout=timeout, cwd=os.path.dirname(out_tsv))
    with open(log_path, errors="replace") as lf:
        if "MDRC_DONE" not in lf.read():
            raise RuntimeError("Magic DRC did not finish (status %d), see %s" % (p.returncode, log_path))
    out = []
    with open(out_tsv, encoding="utf-8", errors="replace") as f:
        for line in f:
            if "\t" not in line:
                continue
            msg, box = line.rstrip("\n").split("\t", 1)
            vals = [float(x) for x in box.split()]
            if len(vals) == 4:
                out.append((magic_rule_id(msg), None, vals))
    return out


def run_mdrc(gds, cells, out_tsv, log_path, pdk="sky130A", style=None, timeout=3600):
    """mdrc.tcl with KMP_CELLS: each cell of ``cells`` checked as its own top
    cell, in one Magic process. Returns {cell: [(why-text, [l, b, r, t] um)]},
    with every cell of ``cells`` present (a list of none for a clean cell)."""
    env = dict(os.environ, KMP_GDS=gds, KMP_CELLS="\n".join(cells), KMP_OUT=out_tsv)
    env.pop("KMP_TOP", None)
    if style:
        env["KMP_STYLE"] = style
    cmd = ["magic", "-dnull", "-noconsole", "-rcfile", magicrc(pdk), os.path.join(HERE, "mdrc.tcl")]
    with open(log_path, "w") as lf:
        p = subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=lf, stderr=subprocess.STDOUT,
                           env=env, timeout=timeout, cwd=os.path.dirname(out_tsv))
    with open(log_path, errors="replace") as lf:
        if "MDRC_DONE" not in lf.read():
            raise RuntimeError("Magic DRC did not finish (status %d), see %s" % (p.returncode, log_path))
    out = {c: [] for c in cells}
    with open(out_tsv, encoding="utf-8", errors="replace") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) != 3:
                continue
            vals = [float(x) for x in parts[2].split()]
            if len(vals) == 4:
                out.setdefault(parts[0], []).append((parts[1], vals))
    return out


def run_magic_extract(gds, cells, out_dir, log_path, pdk="sky130A", timeout=3600):
    """Extract each flat cell; return {cell: [(model, w, l), ...]}."""
    os.makedirs(out_dir, exist_ok=True)
    env = dict(os.environ, KMP_GDS=gds, KMP_CELLS=" ".join(cells), KMP_OUT=out_dir)
    cmd = ["magic", "-dnull", "-noconsole", "-rcfile", magicrc(pdk), os.path.join(HERE, "extract.tcl")]
    with open(log_path, "w") as lf:
        subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=lf, stderr=subprocess.STDOUT,
                       env=env, timeout=timeout, cwd=out_dir)
    with open(log_path, errors="replace") as lf:
        text = lf.read()
    if "EXTRACT_DONE" not in text:
        raise RuntimeError("Magic extraction did not finish, see %s" % log_path)
    out = {}
    for c in cells:
        path = os.path.join(out_dir, c + ".spice")
        out[c] = parse_spice(path) if os.path.isfile(path) else None
    return out


_SUFFIX = {"f": 1e-15, "p": 1e-12, "n": 1e-9, "u": 1e-6, "m": 1e-3, "k": 1e3, "meg": 1e6, "g": 1e9}


def spice_um(v):
    """A length from ext2spice in um: sky130A's netlists give plain numbers in
    um (w=0.42), gf180mcuD's SPICE values with a suffix in metres (w=0.22u)."""
    if v is None:
        return None
    t = str(v).strip().lower()
    m = re.fullmatch(r"([-+]?[0-9.]+(?:e[-+]?[0-9]+)?)(meg|[fpnumkg])?m?", t)
    if not m:
        return v
    x = float(m.group(1))
    if m.group(2):
        x = x * _SUFFIX[m.group(2)] * 1e6
    return round(x, 4)


def parse_spice(path):
    """Device lines of an ext2spice netlist as (model, w, l) tuples."""
    lines = []
    with open(path, errors="replace") as f:
        for raw in f:
            raw = raw.rstrip("\n")
            if raw.startswith("+") and lines:
                lines[-1] += " " + raw[1:]
            else:
                lines.append(raw)
    devs = []
    for line in lines:
        s = line.strip()
        if not s or s[0] not in "XxMm" or s.lower().startswith(".subckt"):
            continue
        toks = s.split()
        params = dict(t.split("=", 1) for t in toks if "=" in t)
        plain = [t for t in toks if "=" not in t]
        if len(plain) < 2:
            continue
        model = plain[-1]

        devs.append((model, spice_um(params.get("w")), spice_um(params.get("l"))))
    return devs
