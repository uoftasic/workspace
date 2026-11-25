#!/usr/bin/env python3
"""Parity harness driver. Run it inside the pinned image (scripts/parity.sh).

    python3 tests/parity/run_sweep.py --pdk PDK --out out/parity/PDK [--quick]
        [--devices GLOB ...] [--keep] [--update-baseline] [--no-unit] [--no-drc]
        [--no-extract] [--no-jobs] [--jobs N]
    python3 tests/parity/run_sweep.py --pdk all --out out/parity [...]

With ``--pdk all`` every supported PDK runs in turn, each into --out/<pdk>,
and --out/summary.json and summary.md collect the results.

Steps, each writing under --out:
  0. unit and backend tests (tests/unit, tests/backend)
  1. versions.json
  2. sweep.json (gen_sweep.py)
  3. path A, Magic alone through magic::gencell (magic_ref.tcl) -> ref/;
     path D, Magic's own parameter dialog under Xvfb (dialog_ref.tcl) -> dlg/
  4. path B, the PCell, empty cache (pcell_path.py) -> pcell/; again warm -> pcell_warm/
  5. per-point checks against path D for a device (path A for a box-paint
     generator): the request path B sent, the stored values against the
     dialog's form, geometry, texts, bounding box, Magic cell name, checked
     dict, cache, placeholder, stamp; path A as the second reference for a
     device where it applies; the typed values drawing the same as the
     stored ones; the dialog's bindings against the server's
  6. round trips (roundtrip.py)
  7. DRC on sheets, both tools, both sides, plus the defaults one at a time
     (KLayout only where the PDK ships a deck in the image)
  8. extraction of the MOSFET points
  9. jobs (tests/jobs/run_jobs.py): the plugin's DRC, extraction, LVS,
     layers and ports jobs on the case suite against references that use no
     plugin code, the GDS read-back check and the gap table's --check;
     --quick builds the inverters, gaps and controls sets without the
     Magic-written row, runs the inverters set and run_jobs.QUICK_EXTRA's
     cases, and skips the read-back check and the gap table's --check;
     --no-jobs skips the step -> jobs/
 10. report.json, report.md

Exit status: 0 when every check passes, 1 when any check fails, 2 when the
harness itself fails.
"""

import argparse
import concurrent.futures as cf
import json
import multiprocessing
import os
import random
import re
import shutil
import signal
import subprocess
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, "python"))

import report  # noqa: E402
from klayout_magic_pcells.config import SUPPORTED_PDKS, shipped_manifest  # noqa: E402

LYM = os.path.join(REPO, "pymacros", "klayout_magic_pcells.lym")
PDK_ROOT = os.environ.get("PDK_ROOT", "/foss/pdks")
SHEET_SIZE = 250
CHECKS = ("error", "request", "dialog", "typed", "bindings", "gencell", "geometry", "texts", "census",
          "bbox", "magic_cell", "checked",
          "cache", "placeholder", "stamp", "roundtrip", "drc", "drc_baseline", "extract")

# Set by use_pdk().
PDK = "sky130A"
MANIFEST = shipped_manifest(PDK)
MAGICRC = ""
BASELINE_DIR = ""
BASELINE = ""
CENSUS_BASELINE = ""
EXTRACT_KNOWN = ""


def use_pdk(pdk):
    global PDK, MANIFEST, MAGICRC, BASELINE_DIR, BASELINE, CENSUS_BASELINE, EXTRACT_KNOWN
    PDK = pdk
    MANIFEST = shipped_manifest(pdk)
    MAGICRC = os.path.join(PDK_ROOT, pdk, "libs.tech", "magic", pdk + ".magicrc")
    BASELINE_DIR = os.path.join(HERE, "baseline", pdk)
    BASELINE = os.path.join(BASELINE_DIR, "drc-defaults.json")
    CENSUS_BASELINE = os.path.join(BASELINE_DIR, "census.json")
    EXTRACT_KNOWN = os.path.join(BASELINE_DIR, "extract-known.json")


def pdk_env(env=None, **extra):
    """The environment for a child that works on PDK alone: only its library
    registers, and the image's PDK variable points at it (KLAYOUT_PATH and
    the DRC decks follow PDK in the image's login profile)."""
    e = dict(os.environ if env is None else env)
    e.update(KMP_PDK=PDK, KMP_PDKS=PDK, PDK=PDK)
    e.update(extra)
    return e


class HarnessError(Exception):
    pass


def log(msg):
    print("[%s] %s" % (time.strftime("%H:%M:%S"), msg), flush=True)


def run(cmd, log_path, env=None, cwd=None, timeout=7200, shell=False):
    with open(log_path, "w") as lf:
        p = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                           env=env, cwd=cwd, timeout=timeout, shell=shell)
    return p.returncode


def tail(path, n=20):
    try:
        with open(path, errors="replace") as f:
            return "".join(f.readlines()[-n:])
    except OSError:
        return ""


# --- step 0: unit and backend tests ------------------------------------------

def step_unit(out):
    res = {}
    for suite in ("unit", "backend"):
        lp = os.path.join(out, "test_%s.log" % suite)
        env = pdk_env(KMP_CACHE_DIR=os.path.join(out, "cache-tests"))
        rc = run([sys.executable, "-m", "unittest", "discover", "-s", os.path.join("tests", suite),
                  "-t", ".", "-v"], lp, env=env, cwd=REPO)
        text = tail(lp, 400)
        m = re.search(r"Ran (\d+) tests?", text)
        skipped = re.search(r"skipped=(\d+)", text)
        fails = re.search(r"failures=(\d+)", text)
        errs = re.search(r"errors=(\d+)", text)
        res[suite] = {"rc": rc, "ran": int(m.group(1)) if m else 0,
                      "failures": int(fails.group(1)) if fails else 0,
                      "errors": int(errs.group(1)) if errs else 0,
                      "skipped": int(skipped.group(1)) if skipped else 0,
                      "ok": rc == 0, "log": os.path.relpath(lp, out)}
        log("tests/%s: %s" % (suite, res[suite]))
    return res


# --- step 1: versions -----------------------------------------------------------

def step_versions(out):
    from klayout_magic_pcells.backend import MagicServer
    from klayout_magic_pcells.config import Config
    cfg = Config.load(env=pdk_env(KMP_CACHE_DIR=os.path.join(out, "cache-versions")), pdk=PDK)
    s = MagicServer(cfg)
    try:
        v = s.start()
    finally:
        s.close()
    shutil.rmtree(os.path.join(out, "cache-versions"), ignore_errors=True)
    kl = subprocess.run(["klayout", "-v"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    rev = subprocess.run(["git", "-C", REPO, "rev-parse", "HEAD"], stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL)
    dirty = subprocess.run(["git", "-C", REPO, "status", "--porcelain", "--untracked-files=no"],
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    rev_s = rev.stdout.decode().strip() or "unknown"
    if dirty.stdout.strip():
        rev_s += "-dirty"
    meta = v.as_dict()
    meta.update({"pdk": PDK, "library": cfg.library_name,
                 "klayout": kl.stdout.decode().strip().replace("KLayout ", ""),
                 "image": os.environ.get("KMP_IMAGE", ""), "repo": rev_s,
                 "python": sys.version.split()[0]})
    with open(os.path.join(out, "versions.json"), "w") as f:
        json.dump(meta, f, indent=1)
    return meta


# --- steps 3 and 4: the two paths -------------------------------------------------

PATH_A_STALL = 300  # seconds without a finished point before path A counts as hung


def _count_lines(path):
    try:
        with open(path, "rb") as f:
            return sum(1 for line in f if line.endswith(b"\n"))
    except OSError:
        return 0


# Magic under Xvfb (path D, the menu check) can die while it opens its
# first window, before it reads the harness's script: in the image the
# height of its first drawing pixmap changes from one start to the next
# (718 to 4161 pixels on gf180mcuD in six starts), and on GitHub's runner
# Xvfb refused that request with BadAlloc on two PDKs (run 45232459515).
# Such a start is tried again, up to this many times in a row; it is not a
# failure of any point.
X_START_RETRIES = 8
X_ERROR = "X Error of failed request"


def x_start_error(text):
    """The X error lines of a Magic that died opening its window, or ""."""
    if X_ERROR not in text:
        return ""
    lines = text[text.index(X_ERROR):].splitlines()
    return " | ".join(ln.strip() for ln in lines[:4])


def _read_from(path, offset):
    try:
        with open(path, "rb") as f:
            f.seek(offset)
            return f.read().decode("utf-8", "replace")
    except OSError:
        return ""


def run_watched(name, cmd, pts, rec_dir, lp, run_dir, env, stall, stats=None):
    """Run a reference script (magic_ref.tcl, dialog_ref.tcl) over ``pts``.

    The script writes one line per point to rec_dir/index.jsonl and skips
    the first KMP_START points. If Magic dies or stops making progress on a
    point (a segfault, or a generator loop that prints nothing), that point
    is recorded as a Magic error and Magic is started again on the next
    point, so one bad point can't hang or end the sweep. A Magic that dies
    with an X error before it finishes a point (see X_START_RETRIES) is
    started again on the same point instead, and ``stats["x_retries"]``
    counts those starts. The script runs in its own process group, so a
    kill also ends what it started (Xvfb)."""
    ix = os.path.join(rec_dir, "index.jsonl")
    os.makedirs(run_dir, exist_ok=True)
    t = time.time()
    start, idle_runs, restarts = 0, 0, []
    x_tries = 0
    if stats is not None:
        stats.setdefault("x_retries", 0)
        stats.setdefault("x_errors", [])
    with open(lp, "w") as lf:
        while start < len(pts):
            e = dict(env, KMP_START=str(start))
            lf.flush()
            log_at = lf.tell()
            p = subprocess.Popen(cmd, stdout=lf, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                 env=e, cwd=run_dir, start_new_session=True)
            last_n, last_t, status = -1, time.monotonic(), None
            while status is None:
                try:
                    status = p.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    pass
                n = _count_lines(ix)
                if n != last_n:
                    last_n, last_t = n, time.monotonic()
                elif status is None and time.monotonic() - last_t > stall:
                    try:
                        os.killpg(p.pid, signal.SIGKILL)
                    except OSError:
                        p.kill()
                    p.wait()
                    status = "hung"
            try:
                os.killpg(p.pid, signal.SIGKILL)  # anything the script left behind
            except OSError:
                pass
            n = _count_lines(ix)
            if n >= len(pts):
                break
            if status == 0 and n > start:
                # A run that ended after KMP_LIMIT points: go on from there.
                start = n
                x_tries = 0
                continue
            lf.flush()
            xerr = x_start_error(_read_from(lp, log_at)) if n <= start and status != "hung" else ""
            if xerr:
                x_tries += 1
                if stats is not None:
                    stats["x_retries"] += 1
                    stats["x_errors"].append(xerr)
                if x_tries > X_START_RETRIES:
                    raise HarnessError("%s: Magic died with an X error before its first point %d times "
                                       "in a row (%s); see %s" % (name, x_tries, xerr, lp))
                lf.write("\n[run_sweep] Magic died with an X error before point %s (%s); starting it "
                         "again\n" % (pts[start]["id"], xerr))
                continue
            x_tries = 0
            if n <= start:
                idle_runs += 1
                if idle_runs >= 5:
                    raise HarnessError("%s made no progress in 5 runs; see %s:\n%s" % (name, lp, tail(lp)))
            else:
                idle_runs = 0
            bad = pts[n]
            why = ("no point finished for %d s" % stall) if status == "hung" else "Magic exited (status %s)" % status
            rec = {"id": bad["id"], "device": bad["device"], "rc": 1, "top": "", "magic_cell": "", "log": "",
                   "error": "%s watchdog: %s on this point; Magic restarted on the next one" % (name, why),
                   "checked": {}}
            os.makedirs(rec_dir, exist_ok=True)
            with open(ix, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec) + "\n")
            restarts.append(bad["id"])
            lf.write("\n[run_sweep] %s: %s; restarting at the next point\n" % (bad["id"], why))
            start = n + 1
    recs = {}
    if os.path.isfile(ix):
        with open(ix, encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                recs[r["id"]] = r
    missing = [pt["id"] for pt in pts if pt["id"] not in recs]
    if missing:
        raise HarnessError("%s wrote no record for %d points (first %s); see %s" % (name, len(missing), missing[0], lp))
    if restarts:
        log("  %s restarted Magic after %s" % (name, ", ".join(restarts)))
    return recs, round(time.time() - t, 1)


def path_a(out, sweep_path, cmd=None, stall=PATH_A_STALL):
    """magic_ref.tcl over the sweep: magic::gencell with the typed values,
    and for a box-paint point the menu's call on the box."""
    cmd = cmd or ["magic", "-dnull", "-noconsole", "-rcfile", MAGICRC, os.path.join(HERE, "magic_ref.tcl")]
    with open(sweep_path, encoding="utf-8") as f:
        sweep = json.load(f)
    # An edit point is a sequence of two dialogs; magic::gencell has no
    # counterpart for it.
    pts = [pt for pt in sweep["points"] if not pt.get("edit")]
    if len(pts) != len(sweep["points"]):
        sweep_path = os.path.join(out, "sweep_a.json")
        with open(sweep_path, "w", encoding="utf-8") as f:
            json.dump(dict(sweep, points=pts), f)
    ref_dir = os.path.join(out, "ref")
    env = pdk_env(KMP_SWEEP=sweep_path, KMP_OUT=ref_dir)
    env.pop("KMP_NS", None)
    # Magic looks for cells in "." first: an empty directory, so that no file
    # the harness writes can stand in for a vendor cell.
    return run_watched("path A", cmd, pts, ref_dir, os.path.join(out, "path_a.log"),
                       os.path.join(out, "run_a"), env, stall)


def xvfb_cmd(out, name, script):
    """Magic under Xvfb, with Xvfb's own messages in <out>/xvfb_<name>.log."""
    return ["xvfb-run", "-a", "-e", os.path.join(out, "xvfb_%s.log" % name), "magic", "-d", "XR",
            "-noconsole", "-rcfile", MAGICRC, os.path.join(HERE, script)]


def path_d(out, sweep_path, stall=PATH_A_STALL, stats=None):
    """dialog_ref.tcl over the device points: Magic's own dialog, under Xvfb."""
    if not shutil.which("xvfb-run"):
        raise HarnessError("xvfb-run not found: path D (Magic's dialog) needs it")
    cmd = xvfb_cmd(out, "path_d", "dialog_ref.tcl")
    with open(sweep_path, encoding="utf-8") as f:
        pts = [pt for pt in json.load(f)["points"] if pt.get("form") != "box"]
    if not pts:
        return {}, 0.0
    d = os.path.join(out, "dlg")
    env = pdk_env(KMP_SWEEP=sweep_path, KMP_OUT=d, KMP_LIMIT="50")
    env.pop("KMP_NS", None)
    env.pop("DISPLAY", None)
    return run_watched("path D", cmd, pts, d, os.path.join(out, "path_d.log"),
                       os.path.join(out, "run_d"), env, stall, stats=stats)


def path_b(out, sweep_path, dirname):
    env = pdk_env(KMP_SWEEP=sweep_path, KMP_OUT=os.path.join(out, dirname),
                  KMP_CACHE_DIR=os.path.join(out, "cache"))
    lp = os.path.join(out, "path_b_%s.log" % dirname)
    t = time.time()
    run(["klayout", "-b", "-rm", LYM, "-r", os.path.join(HERE, "pcell_path.py")], lp, env=env, cwd=out)
    ix = os.path.join(out, dirname, "index.json")
    if not os.path.isfile(ix):
        raise HarnessError("path B (%s) wrote no index; see %s:\n%s" % (dirname, lp, tail(lp)))
    with open(ix, encoding="utf-8") as f:
        data = json.load(f)
    if not data.get("registered"):
        raise HarnessError("path B: the library did not register: %s" % data.get("error"))
    return data, round(time.time() - t, 1)


# --- step 5: per-point checks ---------------------------------------------------

_CTX = {}


def _init_worker(ctx):
    _CTX.update(ctx)


# Magic's SPICE notation as magic::spice2float reads it, restated here (not
# imported from the plugin) to compare a stored double with the dialog's
# text for it ("1.028k", "202.5m", "1.218u").
_SPICE_SCALE = (("meg", 1e6), ("k", 1e3), ("m", 1e-3), ("u", 1e-6), ("n", 1e-9), ("p", 1e-12),
                ("f", 1e-15), ("a", 1e-15))


def spice_number(text):
    t = str(text).strip().lower()
    for suf, scale in _SPICE_SCALE:
        if t.endswith(suf):
            try:
                return float(t[:-len(suf)]) * scale
            except ValueError:
                return None
    try:
        return float(t)
    except ValueError:
        return None


def stored_matches_form(ptype, stored, text):
    """Does a stored PCell value show the dialog's text for it?"""
    if ptype in ("signed", "string", "choice", "numlist"):
        return stored == text
    n = spice_number(text)
    if n is None:
        return False
    if ptype == "bool01":
        return bool(stored) == (n != 0)
    if ptype == "int":
        return n == int(n) and stored == int(n)
    try:
        return stored == n or abs(float(stored) - n) <= 1e-12 * max(1.0, abs(n))
    except (TypeError, ValueError):
        return False


def _geometry(c, out, xor_name, gds_a, top_a, gds_b, top_b):
    """Layers that differ (XOR, shape counts) and texts only on one side."""
    from compare import compare_cells
    geo_diff = [l["layer"] for l in c["layers"]
                if l["xor_polygons"] or l["xor_area_um2"] or l.get("shape_counts_differ")]
    only_a = [[l["layer"]] + t for l in c["layers"] for t in l["texts_only_a"]]
    only_b = [[l["layer"]] + t for l in c["layers"] for t in l["texts_only_b"]]
    xor = None
    if geo_diff or only_a or only_b:
        xor = os.path.join(out, xor_name)
        os.makedirs(os.path.dirname(xor), exist_ok=True)
        compare_cells(gds_a, top_a, gds_b, top_b, xor_out=xor)
        xor = os.path.relpath(xor, out)
    return geo_diff, only_a, only_b, xor


def check_point(job):
    """Runs in a worker process; returns a dict of check results.

    The reference is Magic's own dialog (path D) for a device, and Magic's
    menu call (path A) for a box-paint generator, which has no dialog. Path A
    (magic::gencell with the typed values) is the second reference for a
    device: it applies where Create gets the same checked values from the
    dialog's form as gencell gets from the typed ones."""
    from compare import compare_cells
    from gds_census import lost, text_fonts
    from klayout_magic_pcells.stamp import read_stamp
    import klayout.db as db
    out, manifest_bbox = _CTX["out"], _CTX["bboxes"]
    pt, ra, pb, pw, cur = job["point"], job["ref"], job["pcell"], job["warm"], job["stamp"]
    rd = job.get("dlg")
    box = pt.get("form") == "box"
    edit = bool(pt.get("edit"))
    pid = pt["id"]
    r = {}
    errs = []
    if box and (ra is None or ra.get("rc")):
        errs.append("path A: %s" % ((ra or {}).get("error") or "no record").strip())
    if not box and (rd is None or rd.get("rc")):
        errs.append("path D (Magic's dialog): %s" % ((rd or {}).get("error") or "no record").strip())
    if pb is None or pb.get("error"):
        errs.append("path B: %s" % ((pb or {}).get("error") or "no record"))
    if errs:
        r["error"] = errs
        return pid, r
    names = _CTX["req_defaults"][pt["device"]]
    types = _CTX["types"][pt["device"]]
    got = pb.get("request") or {}
    if box:
        # What path B sent must be exactly what path A gave Magic: the
        # point's box.
        exp = dict(names)
        exp.update(pt["request"])
        ref_gds, ref_top, ref_rec = os.path.join(out, "ref", pid + ".gds"), ra["top"], ra
    else:
        # What path B sent must be the form Magic's dialog had when Create
        # (or, on an edit point, Apply) was pressed: every widget's value
        # but the device-type switch, which Create drops. Apply's cell is
        # the form checked once and then checked again by gencell_create,
        # which the request marks with kmp_apply; on a fixed device Apply
        # draws as Create does. Where Apply kept the instance (its cell is
        # the one Create made), that is Create's form.
        def widgets(d):
            return {k: v for k, v in (d or {}).items() if k != "gencell"}
        form = widgets(rd.get("form"))
        e = rd.get("edit") or {}
        nocell = bool(rd.get("nocell"))  # Magic's defaults, as path D read them
        kept = edit and e.get("button") == "Apply" and not nocell and rd["magic_cell"] == e.get("first_cell")
        if kept:
            exp = widgets(e.get("first_form"))
        elif edit and e.get("button") == "Apply" and not nocell:
            exp = dict(form, kmp_apply="1")
        else:
            exp = dict(form)
        ref_gds, ref_top, ref_rec = os.path.join(out, "dlg", pid + ".gds"), rd["top"], rd
    rdiff = {k: [exp.get(k), got.get(k)] for k in sorted(set(exp) | set(got)) if exp.get(k) != got.get(k)}
    r["sent"] = {"equal": not rdiff, "diff": rdiff}
    if not box:
        # The stored values are what the dialog shows when it reopens on the
        # instance (Magic's "Edit device" dialog), the stored state holds
        # that text and the form Create or Apply got, and the New device
        # dialog opened with the manifest's defaults. On an edit point, the
        # state after its first step (which the edit starts from) must also
        # hold what Magic's dialog showed then.
        stored = pb.get("stored") or {}
        reo = widgets(rd.get("reopened"))

        def state_diff(st, form_exp, shows_exp, apply_exp, numbers, typed_vals):
            try:
                d = json.loads(st.get("kmp_dialog") or "{}")
            except ValueError:
                d = {}
            out = {}
            for part, want in (("form", form_exp), ("shows", shows_exp)):
                got_ = d.get(part) or {}
                for k in sorted(set(want) | set(got_)):
                    if got_.get(k) != want.get(k):
                        out["%s.%s" % (part, k)] = [got_.get(k), want.get(k)]
            if d.get("apply") != apply_exp or d.get("device") != pt["device"]:
                out["apply/device"] = [d.get("apply"), d.get("device"), apply_exp]
            # A field shows what the dialog shows. A value in SPICE
            # notation shows as the number Magic's magic::spice2float
            # reads (path D asked Magic); where Magic reads none (170.0n),
            # the field keeps what it had, the typed value where one was
            # typed, and the state records the field's own text for it.
            shown = d.get("shown") or {}
            vd = {}
            for k in names:
                text = shows_exp.get(k)
                if types[k] not in ("float", "int", "bool01") or k not in numbers:
                    ok = stored_matches_form(types[k], st.get(k), text)
                elif numbers[k] == "":
                    ok = k in shown and (k not in typed_vals or st.get(k) == typed_vals[k])
                else:
                    ok = stored_matches_form(types[k], st.get(k), numbers[k])
                if not ok:
                    vd[k] = [st.get(k), text, numbers.get(k)]
            return vd, out

        sform = {k: v for k, v in exp.items() if k != "kmp_apply"}
        vdiff, fdiff = state_diff(stored, sform, reo, 1 if "kmp_apply" in exp else 0,
                                  rd.get("numbers") or {}, pt["value"])
        opened = rd.get("opened") or {}
        odiff = {k: [names[k], opened.get(k)] for k in names if opened.get(k) != names[k]}
        r["dialog"] = {"values": vdiff, "state": fdiff, "opened": odiff, "typed": rd.get("typed"),
                       "title": rd.get("title")}
        ok = not vdiff and not fdiff and not odiff
        if edit:
            v1, f1 = state_diff(pb.get("first_stored") or {}, widgets(e.get("first_form")),
                                widgets(e.get("first_reopened")), 0, e.get("first_numbers") or {},
                                pt["first"]["value"])
            r["dialog"].update({"first_values": v1, "first_state": f1, "button": e.get("button"),
                                "edit_typed": e.get("typed"), "apply_kept": kept})
            ok = ok and not v1 and not f1
        r["dialog"]["equal"] = ok
        tc = pb.get("typed_create") or {}
        r["typed"] = {"same": bool(tc.get("same")), "diff_layers": tc.get("diff_layers")}
    pc_gds = os.path.join(out, "pcell", pid + ".gds")
    try:
        c = compare_cells(ref_gds, ref_top, pc_gds, pb["variant"], shape_counts=True)
        geo_diff, only_ref, only_pc, xor = _geometry(c, out, os.path.join("xor", pid + ".gds"),
                                                     ref_gds, ref_top, pc_gds, pb["variant"])
    except Exception as e:
        r["error"] = ["compare: %s" % e]
        return pid, r
    # Elements in Magic's file that KLayout has no shape for (NODE): they
    # can't reach the PCell, so they must be the ones the baseline records
    # for this device (a change in the vendor GDS shows up here).
    try:
        lgot = lost(ref_gds)
    except Exception as e:
        lgot = {"error": str(e)}
    want = _CTX["census"].get(pt["device"], {})
    r["census"] = {"lost": lgot, "baseline": want,
                   "ok": lgot == want or _CTX.get("update_baseline", False)}
    r["geometry"] = {"identical": not geo_diff, "diff_layers": geo_diff, "xor": xor}
    # The font, which KLayout's GDS reader drops, from the raw records: the
    # PCell's file always says font 0, so any other font in Magic's file is
    # a difference that compare_cells can't see.
    try:
        fa, fb = text_fonts(ref_gds), text_fonts(pc_gds)
        fonts = {"equal": fa == fb}
        if fa != fb:
            fonts.update(only_ref=[t for t in fa if t not in fb], only_pcell=[t for t in fb if t not in fa])
    except Exception as e:
        fonts = {"equal": False, "error": str(e)}
    r["texts"] = {"identical": not only_ref and not only_pc and fonts["equal"], "only_ref": only_ref,
                  "only_pcell": only_pc, "fonts": fonts}
    bref, bpc = c["a"]["geometry_bbox_um"], c["b"]["geometry_bbox_um"]
    bb = {"ref": bref, "pcell": bpc, "equal": bref == bpc}
    if pt["kind"] == "default":
        mb = manifest_bbox.get(pt["device"])
        bb["manifest"] = mb
        bb["equal"] = bb["equal"] and (mb == bref)
    r["bbox"] = bb
    r["magic_cell"] = {"ref": ref_rec["magic_cell"], "pcell": pb.get("magic_cell"),
                       "equal": ref_rec["magic_cell"] == pb.get("magic_cell")}
    # Create's checked dict: the dialog's has the device-type switch
    # (gencell), which gencell_create removes after _check.
    ca = {k: v for k, v in (ref_rec.get("checked") or {}).items() if k != "gencell"}
    cb = pb.get("checked") or {}
    r["checked"] = {"equal": ca == cb,
                    "diff": {k: [ca.get(k), cb.get(k)] for k in sorted(set(ca) | set(cb))
                             if ca.get(k) != cb.get(k)}}
    if not box and not edit:
        # The second reference: magic::gencell with the typed values. It
        # applies where its checked dict equals the one Create got from the
        # dialog's form (then _draw gets the same values). This is also what
        # Magic's dialog draws when one value is typed and Create pressed
        # with no Return: no binding runs, and Create checks the form once.
        g = {}
        if ra is None or ra.get("rc"):
            g = {"applies": False, "ok": False,
                 "error": "path A: %s" % ((ra or {}).get("error") or "no record").strip()}
        else:
            a_chk = ra.get("checked") or {}
            g["applies"] = a_chk == cb
            if not g["applies"]:
                g["checked_diff"] = {k: [a_chk.get(k), cb.get(k)] for k in sorted(set(a_chk) | set(cb))
                                     if a_chk.get(k) != cb.get(k)}
            a_gds = os.path.join(out, "ref", pid + ".gds")
            try:
                ca2 = compare_cells(a_gds, ra["top"], pc_gds, pb["variant"], shape_counts=True)
                gd, oa, ob, gx = _geometry(ca2, out, os.path.join("xor_gencell", pid + ".gds"),
                                           a_gds, ra["top"], pc_gds, pb["variant"])
                g["same_geometry"] = not gd and not oa and not ob
                g["magic_cell_equal"] = ra["magic_cell"] == pb.get("magic_cell")
                if gx:
                    g["xor"] = gx
                    g["diff_layers"] = gd
            except Exception as e:
                g["same_geometry"] = False
                g["error"] = "compare: %s" % e
            g["ok"] = (not g["applies"]) or (g.get("same_geometry") and g.get("magic_cell_equal")
                                             and "error" not in g)
        # One value typed on a device whose dialog has no widget beyond its
        # PCell parameters: path A is then also Magic's dialog with that
        # value typed and Create pressed without Return.
        g["single_entry"] = len(pt["request"]) == 1 and not (set(form) - set(names))
        r["gencell"] = g
    # cache: cold run went to Magic, warm run came from disk, same geometry
    cache = []
    if pb.get("source") != "magic":
        cache.append("cold source %s" % pb.get("source"))
    if pw is None or pw.get("error"):
        cache.append("warm run: %s" % ((pw or {}).get("error") or "no record"))
    else:
        if pw.get("source") != "disk":
            cache.append("warm source %s" % pw.get("source"))
        try:
            cw = compare_cells(pc_gds, pb["variant"], os.path.join(out, "pcell_warm", pid + ".gds"),
                               pw["variant"])
            if not cw["identical"]:
                cache.append("warm geometry differs")
        except Exception as e:
            cache.append("warm compare: %s" % e)
    r["cache"] = "identical" if not cache else "; ".join(cache)
    # placeholder and stamp, read without the library
    ly = db.Layout()
    ly.read(pc_gds)
    cell = ly.cell(pb["variant"])
    ph = ly.find_layer(255, 0)
    r["placeholder"] = "present" if ph is not None and not cell.shapes(ph).is_empty() else "none"
    # No shapes and no texts, flattened (a fixed device may place an empty
    # vendor stub: gf180mcuD's eFuse).
    empty = bref is None and not any(l["texts_a"] for l in c["layers"])
    st = read_stamp(cell)
    if empty:
        r["stamp"] = "n/a (Magic wrote no shapes)" if st is None else "unexpected stamp"
        r["empty_output"] = True
    elif st is None:
        r["stamp"] = "missing"
    else:
        bad = [k for k in ("magic", "tech", "pdk") if st.get(k) != cur.get(k)]
        if st.get("key") != (pb.get("key") or "")[:16]:
            bad.append("key")
        r["stamp"] = "ok" if not bad else "mismatch: " + ", ".join(bad)
    if not box:
        # Recorded: what Create's own _check (the pass after the dialog's)
        # changes in the dialog's form; the stored values are Create's.
        again = {k: [got.get(k), cb.get(k)] for k in names if k in cb and got.get(k) != cb.get(k)}
        if again:
            r["create_check_changes"] = again
        if edit and r["dialog"].get("apply_kept"):
            r["apply_kept"] = True
    return pid, r


def load_census_baseline():
    try:
        with open(CENSUS_BASELINE) as f:
            return json.load(f).get("devices", {})
    except (OSError, ValueError):
        return {}


def step_checks(out, points, ref, dlg, pcell, warm, cur_stamp, manifest, jobs, update_baseline=False):
    from klayout_magic_pcells.manifest import Manifest
    bboxes = {d["name"]: d["defaults_run"].get("gds_bbox_um")
              for d in manifest["devices"] + manifest.get("boxpaint", [])}
    devs = Manifest(manifest).devices
    req_defaults = {d.name: {p.name: p.default for p in d.params} for d in devs}
    types = {d.name: {p.name: p.type for p in d.params} for d in devs}
    work = [{"point": pt, "ref": ref.get(pt["id"]), "dlg": dlg.get(pt["id"]),
             "pcell": pcell.get(pt["id"]), "warm": warm.get(pt["id"]), "stamp": cur_stamp}
            for pt in points]
    ctx = multiprocessing.get_context("fork")
    with ctx.Pool(jobs, initializer=_init_worker,
                  initargs=({"out": out, "bboxes": bboxes, "req_defaults": req_defaults,
                             "types": types, "census": load_census_baseline(),
                             "update_baseline": update_baseline},)) as pool:
        return dict(pool.map(check_point, work, chunksize=8))


def update_census_baseline(points, results, manifest, partial):
    """Write the lost-element census of each device's default point."""
    new = {}
    for pt in points:
        if pt["kind"] != "default":
            continue
        got = (results.get(pt["id"], {}).get("census") or {}).get("lost")
        if got:
            new[pt["device"]] = got
    if partial:
        new = dict(load_census_baseline(), **new)
    doc = {"comment": "GDS elements in Magic's output that KLayout has no shape for (NODE), counted "
                      "per device at its default point over all structures of the file. A PCell "
                      "can't hold them. Written by run_sweep.py --update-baseline.",
           "devices": {k: new[k] for k in sorted(new)}}
    os.makedirs(BASELINE_DIR, exist_ok=True)
    with open(CENSUS_BASELINE, "w") as f:
        json.dump(doc, f, indent=1)
        f.write("\n")


def step_bindings(points, dlg, cfg_env, manifest):
    """For each device: the update_dialog calls that each widget's binding
    runs in Magic's real dialog (path D recorded them on the device's first
    point) against the ones the server's dialog op runs, from the manifest's
    widget order and add_dependency calls. Returns {id of that point: result}."""
    from klayout_magic_pcells.backend import MagicServer
    from klayout_magic_pcells.config import Config
    from klayout_magic_pcells.manifest import Manifest
    man = Manifest(manifest)
    cfg = Config.load(env=cfg_env, pdk=PDK)
    s = MagicServer(cfg, vendor_cells=man.vendor_cells())
    s.start()
    out = {}
    try:
        for pt in points:
            rd = dlg.get(pt["id"]) or {}
            if "bindings" not in rd:
                continue
            spec = man[pt["device"]]
            rep = s.dialog(spec, {p.name: p.default for p in spec.params}, [], want_chains=True)
            real = {k: v.get("chain") for k, v in rd["bindings"].items()}
            diff = {}
            for p in spec.params:
                a, b = real.get(p.name), rep.chains.get(p.name)
                if a != b:
                    diff[p.name] = {"dialog": a, "server": b}
            missing = [p.name for p in spec.params if p.name not in real]
            out[pt["id"]] = {"same": not diff and not missing, "diff": diff,
                             "no_widget": missing, "widgets": len(real)}
    finally:
        s.close()
    return out


# --- step 5c: box-paint generators through Magic's own menu ----------------------------

MENU_KINDS = ("default", "wide", "large")


def step_menu(out, points, ref, manifest):
    """For box-paint generators that the PDK puts in Magic's menu: the menu
    entry itself, invoked under Xvfb on the box of some sweep points, must
    write what path A wrote (path A calls the generator the way the entry
    does). Returns ({id: result}, note)."""
    from compare import compare_cells
    if not shutil.which("xvfb-run"):
        return {}, "xvfb-run not found; the menu check did not run"
    menus = {b["name"]: b["menu"].split(" / ", 1)[1] for b in manifest.get("boxpaint", []) if b.get("menu")}
    jobs = []
    for pt in points:
        if pt.get("form") == "box" and pt["device"] in menus and pt["kind"] in MENU_KINDS:
            if (ref.get(pt["id"]) or {}).get("rc") == 0:
                jobs.append({"id": pt["id"], "label": menus[pt["device"]], "w": pt["request"]["w"],
                             "h": pt["request"]["h"]})
    if not jobs:
        return {}, "no box-paint generator of this PDK is in Magic's menu"
    d = os.path.join(out, "menu")
    os.makedirs(d, exist_ok=True)
    jp = os.path.join(d, "jobs.json")
    with open(jp, "w") as f:
        json.dump(jobs, f)
    env = pdk_env(KMP_JOBS=jp, KMP_OUT=d)
    env.pop("DISPLAY", None)
    lp = os.path.join(out, "menu.log")
    xerrs = []
    for _try in range(X_START_RETRIES + 1):
        ixp = os.path.join(d, "index.jsonl")
        if os.path.exists(ixp):
            os.remove(ixp)
        run(xvfb_cmd(out, "menu", "menu_ref.tcl"), lp, env=env, cwd=os.path.join(out, "run_a"),
            timeout=600)
        xerr = "" if os.path.exists(ixp) else x_start_error(_read_from(lp, 0))
        if not xerr:
            break
        xerrs.append(xerr)
        log("  the menu check's Magic died with an X error before its first job (%s); "
            "starting it again" % xerr)
    else:
        raise HarnessError("the menu check: Magic died with an X error before its first job %d "
                           "times in a row (%s); see %s" % (len(xerrs), xerrs[-1], lp))
    recs = {}
    try:
        with open(os.path.join(d, "index.jsonl")) as f:
            for line in f:
                r = json.loads(line)
                recs[r["id"]] = r
    except OSError:
        return {j["id"]: "menu run wrote nothing; see menu.log" for j in jobs}, "menu run failed"
    res = {}
    for j in jobs:
        r = recs.get(j["id"])
        if r is None or r["rc"]:
            res[j["id"]] = "error: %s" % ((r or {}).get("error") or "no record")
            continue
        try:
            c = compare_cells(os.path.join(out, "ref", j["id"] + ".gds"), ref[j["id"]]["top"],
                              os.path.join(d, j["id"] + ".gds"), r["top"])
            res[j["id"]] = "identical" if c["identical"] else "differs on " + ", ".join(
                l["layer"] for l in c["layers"] if l["status"] != "same")
        except Exception as e:
            res[j["id"]] = "compare: %s" % e
    for j in jobs:
        for ext in (".gds",):
            p = os.path.join(d, j["id"] + ext)
            if res.get(j["id"]) == "identical" and os.path.exists(p):
                os.remove(p)
    again = (", Magic started again %d times after an X error at start-up" % len(xerrs)) if xerrs else ""
    return res, "%d points through the menu entries (%s)%s" % (len(jobs), ", ".join(sorted(set(
        j["label"] for j in jobs))), again)


# --- step 6: round trips ------------------------------------------------------------

def reference(out, pt, ref, dlg):
    """(GDS, top cell) of a point's reference: Magic's dialog for a device,
    path A for a box-paint generator."""
    if pt.get("form") == "box":
        return os.path.join(out, "ref", pt["id"] + ".gds"), ref[pt["id"]]["top"]
    return os.path.join(out, "dlg", pt["id"] + ".gds"), dlg[pt["id"]]["top"]


def step_roundtrip(out, points, ref, dlg, pcell, results, seed):
    rng = random.Random(seed)
    chosen = []
    for pt in points:
        k = pt["kind"].split(":")[0]
        r = results.get(pt["id"], {})
        if "error" in r:
            continue
        # Always: the defaults, the limits, the many-digit and tie values
        # (whose text a reopened file must send again) and negative boxes.
        # Edit points: the random-to-random chains always, a fifth of the
        # others.
        if k in ("default", "min", "max", "below", "zero", "digits", "tie", "neg", "negzero") \
                or (k == "edit" and ">" in pt["kind"]) \
                or rng.random() < (0.20 if k == "edit" else 0.10):
            ref_gds, ref_top = reference(out, pt, ref, dlg)
            chosen.append({"id": pt["id"], "device": pt["device"], "kind": pt["kind"],
                           "request": pt["request"], "value": pt["value"],
                           "stored": pcell[pt["id"]].get("stored"),
                           "sent": pcell[pt["id"]].get("request"),
                           "ref_gds": ref_gds, "ref_top": ref_top,
                           "key": pcell[pt["id"]].get("key") or "",
                           "expect_stamp": not r.get("empty_output")})
    rt = os.path.join(out, "roundtrip")
    os.makedirs(rt, exist_ok=True)
    pts_path = os.path.join(rt, "points.json")
    with open(pts_path, "w") as f:
        json.dump(chosen, f)
    # The library side runs with the disk cache off, so every reopened
    # variant is regenerated by Magic in that process (or comes from the
    # memo that Magic filled there), never from the cache path B filled.
    env = pdk_env(KMP_RT_POINTS=pts_path, KMP_RT_PCELL=os.path.join(out, "pcell"),
                  KMP_RT_RESAVED=os.path.join(out, "resaved"),
                  KMP_CACHE_DIR=os.path.join(out, "cache-roundtrip"), KMP_CACHE="0")
    res = {}
    for mode in ("nolib", "lib"):
        e = dict(env, KMP_RT_MODE=mode, KMP_RT_OUT=os.path.join(rt, mode + ".json"))
        lp = os.path.join(rt, mode + ".log")
        if mode == "nolib":
            cmd = [sys.executable, os.path.join(HERE, "roundtrip.py")]
        else:
            cmd = ["klayout", "-b", "-rm", LYM, "-r", os.path.join(HERE, "roundtrip.py")]
        run(cmd, lp, env=e, cwd=out)
        if not os.path.isfile(e["KMP_RT_OUT"]):
            raise HarnessError("roundtrip %s wrote nothing; see %s:\n%s" % (mode, lp, tail(lp)))
        with open(e["KMP_RT_OUT"]) as f:
            data = json.load(f)
        stats = data.pop("__generator__", None)
        if mode == "lib" and chosen:
            if not stats or stats.get("disk") or not stats.get("magic"):
                raise HarnessError("roundtrip lib: the reopened variants did not come from Magic "
                                   "(generator stats %s); see %s" % (stats, lp))
        for pid, d in data.items():
            res.setdefault(pid, {}).update(d)
    return res, len(chosen)


# --- steps 7 and 8: DRC and extraction ------------------------------------------------

# Points whose cell is longer than this on a side get no DRC: Magic's
# dialog makes 0.9 m and 1.8 m long ihp-sg13g2 rm6 and rm7 resistors from
# val 10000 (they have no _check), and Magic's DRC crashed (signal 11) on a
# sheet that held the rm7 one, on both sides.
DRC_MAX_UM = 10000.0


def build_sheets(out, points, ref, dlg, pcell, results):
    from sheet import build_sheet, chunks
    d = os.path.join(out, "drc")
    os.makedirs(d, exist_ok=True)
    sheets = []
    ok = []
    for pt in points:
        r = results.get(pt["id"], {})
        if "error" in r or pt.get("edit"):
            # An edit point's cell is a device the other points already
            # cover; its geometry check is exact, so DRC adds nothing.
            continue
        b = (r.get("bbox") or {}).get("ref")
        if b and max(b[2] - b[0], b[3] - b[1]) > DRC_MAX_UM:
            r["drc_skipped"] = "%.0f x %.0f um, more than the %.0f um DRC limit" % (
                b[2] - b[0], b[3] - b[1], DRC_MAX_UM)
            continue
        ok.append(pt)
    # One device per sheet. On a sheet that mixed devices, Magic logged a unit
    # rescale when it read vendor cells with off-grid coordinates, and its DRC
    # result for an npn then differed from the npn checked alone.
    by_dev = {}
    for pt in ok:
        by_dev.setdefault(pt["device"], []).append(pt)
    for side in ("ref", "pcell"):
        for di, (dev, pts) in enumerate(sorted(by_dev.items())):
            ents = []
            for pt in pts:
                if side == "ref":
                    path, cell = reference(out, pt, ref, dlg)
                else:
                    path, cell = os.path.join(out, "pcell", pt["id"] + ".gds"), pcell[pt["id"]]["variant"]
                ents.append((pt["id"], path, cell))
            for k, ch in enumerate(chunks(ents, SHEET_SIZE)):
                path = os.path.join(d, "%s_%02d_%d.gds" % (side, di, k))
                placed, errors = build_sheet(ch, path)
                sheets.append({"side": side, "path": path, "placed": placed, "errors": errors,
                               "single": False, "device": dev})
    for pt in ok:
        if pt["kind"] != "default":
            continue
        path = os.path.join(d, "single_%s.gds" % pt["id"])
        placed, errors = build_sheet([(pt["id"], os.path.join(out, "pcell", pt["id"] + ".gds"),
                                       pcell[pt["id"]]["variant"])], path)
        sheets.append({"side": "pcell", "path": path, "placed": placed, "errors": errors,
                       "single": True})
    return sheets


def step_drc(out, sheets, jobs):
    import drc as drcmod
    from sheet import assign
    tasks = []
    tools = ("klayout", "magic") if drcmod.profile(PDK) else ("magic",)
    for sh in sheets:
        for tool in tools:
            tasks.append((tool, sh))

    def work(t):
        tool, sh = t
        base = sh["path"][:-4]
        err = None
        for attempt in (1, 2):
            try:
                if tool == "klayout":
                    m = drcmod.run_klayout_drc(sh["path"], "SHEET", base + ".klayout.xml",
                                               base + ".klayout.log", pdk=PDK)
                else:
                    m = drcmod.run_magic_drc(sh["path"], "SHEET", base + ".magic.tsv",
                                             base + ".magic.log", pdk=PDK)
                break
            except Exception as e:  # a crashed DRC run: once more, then an error for its points
                err = "%s DRC failed twice: %s" % (tool, e)
                log("  %s (attempt %d)" % (e, attempt))
        else:
            return tool, sh, {pid: {"ERROR: " + err} for pid in sh["placed"]}, []
        got, unassigned = assign(m, sh["placed"])
        return tool, sh, got, unassigned

    sheet_sets, single_sets, unassigned_all = {}, {}, []
    t0 = time.time()
    # Big sheets first: they take longest.
    tasks.sort(key=lambda t: (t[1]["single"], -len(t[1]["placed"])))
    with cf.ThreadPoolExecutor(max_workers=jobs) as ex:
        for tool, sh, got, unassigned in ex.map(work, tasks):
            target = single_sets if sh["single"] else sheet_sets
            for pid in sh["placed"]:
                target.setdefault(pid, {}).setdefault(tool, {})[sh["side"]] = sorted(got.get(pid, ()))
            for u in unassigned:
                unassigned_all.append([tool, os.path.basename(sh["path"])] + u)
    return sheet_sets, single_sets, unassigned_all, round(time.time() - t0, 1)


def step_extract(out, sheets, points, jobs):
    import drc as drcmod
    mos = {pt["id"] for pt in points if pt["family"] == "mos"}
    tasks = []
    for sh in sheets:
        if sh["single"]:
            continue
        cells = ["D" + pid for pid, b in sh["placed"].items() if pid in mos and b]
        if cells:
            tasks.append((sh, cells))

    def work(t):
        sh, cells = t
        base = sh["path"][:-4]
        return sh, drcmod.run_magic_extract(sh["path"], cells, base + "_ext", base + ".extract.log",
                                            pdk=PDK)

    res = {}
    with cf.ThreadPoolExecutor(max_workers=jobs) as ex:
        for sh, got in ex.map(work, tasks):
            for cell, devs in got.items():
                res.setdefault(cell[1:], {})[sh["side"]] = devs
    return res


def load_extract_known():
    try:
        with open(EXTRACT_KNOWN) as f:
            return json.load(f).get("known", [])
    except (OSError, ValueError):
        return []


def _wl_ok(d, w, l):
    return (isinstance(d[1], float) and isinstance(d[2], float)
            and abs(d[1] - w) <= 0.0051 and abs(d[2] - l) <= 0.0051)


def identity_problems(device, devs, w, l, nf, m):
    """Magic's extraction against the checked values: the model is the device,
    w and l match to the 0.01 um drawing grid, and there are nf*m devices."""
    problems = []
    models = {d[0] for d in devs}
    if models != {device}:
        problems.append("models %s" % sorted(models))
    bad = [d for d in devs if not _wl_ok(d, w, l)]
    if bad:
        problems.append("w/l %s vs checked w=%s l=%s" % (sorted(set((d[1], d[2]) for d in bad))[:3], w, l))
    if len(devs) != nf * m:
        problems.append("count %d != nf*m = %d" % (len(devs), nf * m))
    return problems


def known_extraction(device, devs, w, l, nf, m, known):
    """The entry in extract-known.json this result matches, or None.

    Two kinds of entry: "alternate" (the default; every second finger
    extracts as another model) and "model" (every finger extracts as another
    model, with w and the count right and l not compared)."""
    for k in known:
        other = k.get("devices", {}).get(device)
        if other is None or nf < k.get("min_nf", 1):
            continue
        if k.get("kind") == "model":
            if (len(devs) == nf * m and all(d[0] == other and isinstance(d[1], float)
                                            and abs(d[1] - w) <= 0.0051 for d in devs)):
                return k
            continue
        own = [d for d in devs if d[0] == device]
        rest = [d for d in devs if d[0] != device]
        if (len(devs) == nf * m and len(own) == -(-nf // 2) * m and all(_wl_ok(d, w, l) for d in own)
                and all(d[0] == other and isinstance(d[1], float) and abs(d[1] - w) <= 0.0051
                        for d in rest)):
            return k
    return None


def extract_verdict(pt, devs, checked, known=()):
    """Compare the two sides, and Magic's side with the checked values."""
    ref, pc = devs.get("ref"), devs.get("pcell")
    v = {"ref": summarize_devs(ref), "pcell": summarize_devs(pc)}
    v["equal"] = ref is not None and pc is not None and sorted(ref) == sorted(pc)
    if ref is None or not checked:
        v["identity"] = "no netlist"
        return v
    try:
        w, l = float(checked["w"]), float(checked["l"])
        # fingers: nf, or ng on the IHP PDKs
        nf = int(float(checked["nf"] if "nf" in checked else checked["ng"]))
        m = int(float(checked.get("m", "1")))
    except (KeyError, ValueError):
        v["identity"] = "checked values not numeric"
        return v
    problems = identity_problems(pt["device"], ref, w, l, nf, m)
    if not problems:
        v["identity"] = "ok"
    else:
        k = known_extraction(pt["device"], ref, w, l, nf, m, known)
        v["identity"] = ("known Magic behaviour: " + k["rule"]) if k else "; ".join(problems)
    return v


def summarize_devs(devs):
    if devs is None:
        return None
    from collections import Counter
    c = Counter(devs)
    return [[m, w, l, n] for (m, w, l), n in sorted(c.items(), key=lambda kv: str(kv[0]))]


# --- driver -----------------------------------------------------------------------------

def cleanup(out, points, results):
    for pt in points:
        r = results.get(pt["id"], {})
        if r.get("result") != "pass":
            continue
        for d in ("ref", "dlg", "pcell", "pcell_warm", "resaved"):
            for ext in (".gds", ".oas"):
                p = os.path.join(out, d, pt["id"] + ext)
                if os.path.exists(p):
                    os.remove(p)
    for name in ("cache", "cache-tests"):
        shutil.rmtree(os.path.join(out, name), ignore_errors=True)
    d = os.path.join(out, "drc")
    if os.path.isdir(d):
        # Keep the raw DRC and extraction output only for sheets with a failing point.
        for fn in sorted(os.listdir(d)):
            if not fn.endswith(".gds.json"):
                continue
            base = fn[:-len(".gds.json")]
            with open(os.path.join(d, fn)) as f:
                placed = json.load(f).get("placed", {})
            if any(results.get(pid, {}).get("result") != "pass" for pid in placed):
                continue
            for ext in (".klayout.xml", ".klayout.log", ".magic.tsv", ".magic.log", ".extract.log"):
                p = os.path.join(d, base + ext)
                if os.path.exists(p):
                    os.remove(p)
        for fn in os.listdir(d):
            p = os.path.join(d, fn)
            if fn.endswith(".gds"):
                os.remove(p)
            elif fn.endswith("_ext") and os.path.isdir(p):
                shutil.rmtree(p, ignore_errors=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pdk", default=os.environ.get("KMP_PDK") or "sky130A",
                    help="a supported PDK, or 'all' (default: KMP_PDK, else sky130A)")
    ap.add_argument("--out", default=None, help="default: out/parity/<pdk>, or out/parity with --pdk all")
    ap.add_argument("--quick", action="store_true", help="only each generator's default point")
    ap.add_argument("--devices", nargs="*", default=[], help="fnmatch patterns")
    ap.add_argument("--seed", type=int, default=1121)
    ap.add_argument("--random", type=int, default=5)
    ap.add_argument("--max-per-device", type=int, default=64)
    ap.add_argument("--keep", action="store_true", help="keep the GDS files of passing points")
    ap.add_argument("--update-baseline", action="store_true")
    ap.add_argument("--no-unit", action="store_true")
    ap.add_argument("--no-drc", action="store_true")
    ap.add_argument("--no-extract", action="store_true")
    ap.add_argument("--no-jobs", action="store_true", help="skip the jobs step (tests/jobs)")
    ap.add_argument("--jobs", type=int, default=max(1, min(6, os.cpu_count() or 1)))
    ap.add_argument("--summary", metavar="DIR",
                    help="only write DIR/summary.json and summary.md from DIR/<pdk>/report.json")
    args = ap.parse_args(argv)
    if args.summary:
        return main_summary(os.path.abspath(args.summary))
    if args.pdk == "all":
        return main_all(args)
    if args.pdk not in SUPPORTED_PDKS:
        ap.error("--pdk must be one of %s or all" % ", ".join(SUPPORTED_PDKS))
    out = os.path.abspath(args.out or os.path.join(REPO, "out", "parity", args.pdk))
    rep = run_pdk(args, args.pdk, out)
    print(report.summary_line(rep))
    return rep["exit_status"]


def main_summary(top):
    """The summary over the PDK reports that scripts/parity.sh wrote, one
    container per PDK."""
    reps = {}
    for pdk in SUPPORTED_PDKS:
        path = os.path.join(top, pdk, "report.json")
        try:
            with open(path, encoding="utf-8") as f:
                reps[pdk] = json.load(f)
        except (OSError, ValueError) as e:
            reps[pdk] = {"harness_errors": ["no report at %s (%s)" % (path, e)], "exit_status": 2,
                         "meta": {"pdk": pdk}}
    status = report.write_summary(reps, top)
    for pdk, rep in reps.items():
        print("%-15s %s" % (pdk, report.summary_line(rep)))
    print("PARITY %s over %d PDKs" % ("PASS" if status == 0 else "FAIL" if status == 1 else "ERROR",
                                      len(reps)))
    return status


def main_all(args):
    """Every supported PDK in turn; a summary over all of them."""
    top = os.path.abspath(args.out or os.path.join(REPO, "out", "parity"))
    os.makedirs(top, exist_ok=True)
    reps = {}
    for pdk in SUPPORTED_PDKS:
        log("===== %s =====" % pdk)
        reps[pdk] = run_pdk(args, pdk, os.path.join(top, pdk))
        log(report.summary_line(reps[pdk]))
    status = report.write_summary(reps, top)
    for pdk, rep in reps.items():
        print("%-15s %s" % (pdk, report.summary_line(rep)))
    print("PARITY %s over %d PDKs" % ("PASS" if status == 0 else "FAIL" if status == 1 else "ERROR",
                                      len(reps)))
    return status


def run_pdk(args, pdk, out):
    use_pdk(pdk)
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(out)
    t0 = time.time()
    rep = {"meta": {"pdk": pdk, "seed": args.seed, "quick": args.quick, "devices": args.devices,
                    "jobs": args.jobs}, "steps": {}, "harness_errors": []}
    points = []
    results = {}
    manifest = {}
    try:
        with open(MANIFEST, encoding="utf-8") as f:
            manifest = json.load(f)
        rep["exclusions"] = manifest.get("excluded", [])
        rep["menu_defects"] = manifest.get("menu_defects", [])
        rep["meta"]["generators"] = len(manifest["devices"]) + len(manifest.get("boxpaint", []))
        if not args.no_unit:
            log("step 0: unit and backend tests")
            rep["steps"]["tests"] = step_unit(out)
        log("step 1: versions and the manifest check")
        rep["meta"].update(step_versions(out))
        lp = os.path.join(out, "manifest_check.log")
        rc = run([sys.executable, os.path.join(REPO, "tools", "build_manifest.py"), "--pdk", PDK,
                  "--check"], lp, env=pdk_env(KMP_CACHE_DIR=os.path.join(out, "cache-manifest")))
        rep["steps"]["manifest"] = {"ok": rc == 0, "rc": rc,
                                    "summary": tail(lp, 1).strip(), "log": os.path.relpath(lp, out)}
        log("  " + rep["steps"]["manifest"]["summary"])
        log("step 2: sweep")
        sweep_path = os.path.join(out, "sweep.json")
        cmd = [sys.executable, os.path.join(HERE, "gen_sweep.py"), "--manifest", MANIFEST,
               "--out", sweep_path, "--seed", str(args.seed), "--random", str(args.random),
               "--max-per-device", str(args.max_per_device)]
        if args.quick:
            cmd.append("--quick")
        if args.devices:
            cmd += ["--devices"] + args.devices
        if run(cmd, os.path.join(out, "gen_sweep.log")) != 0:
            raise HarnessError("gen_sweep failed:\n" + tail(os.path.join(out, "gen_sweep.log")))
        with open(sweep_path) as f:
            sweep = json.load(f)
        points = sweep["points"]
        if not points:
            raise HarnessError("the sweep is empty (check --devices)")
        rep["meta"]["points"] = len(points)
        log("  %d points" % len(points))

        log("step 3+4: path A, path D (Magic's dialog, under Xvfb) and path B (cold) in parallel")
        d_stats = {}
        with cf.ThreadPoolExecutor(3) as ex:
            fa = ex.submit(path_a, out, sweep_path)
            fd = ex.submit(path_d, out, sweep_path, stats=d_stats)
            fb = ex.submit(path_b, out, sweep_path, "pcell")
            ref, ta = fa.result()
            dlg, td = fd.result()
            pb_data, tb = fb.result()
        pcell = pb_data["points"]
        log("  path A %.1f s, path D %.1f s, path B %.1f s %s"
            % (ta, td, tb, pb_data.get("generator_stats")))
        log("step 4: path B (warm)")
        pw_data, tw = path_b(out, sweep_path, "pcell_warm")
        warm = pw_data["points"]
        log("  warm %.1f s %s" % (tw, pw_data.get("generator_stats")))
        if d_stats.get("x_retries"):
            log("  path D started Magic again %d times after an X error at start-up"
                % d_stats["x_retries"])
        rep["steps"]["paths"] = {"a_seconds": ta, "d_seconds": td, "b_seconds": tb, "b_warm_seconds": tw,
                                 "d_x_retries": d_stats.get("x_retries", 0),
                                 "d_x_errors": d_stats.get("x_errors", [])[:5],
                                 "b_generator": pb_data.get("generator_stats"),
                                 "b_server": pb_data.get("server_stats"),
                                 "b_warm_generator": pw_data.get("generator_stats"),
                                 "b_warm_server": pw_data.get("server_stats")}

        log("step 5: per-point checks")
        from klayout_magic_pcells.stamp import parse_stamp
        cur = parse_stamp(pb_data["created_stamp"]) or {}
        t = time.time()
        results = step_checks(out, points, ref, dlg, pcell, warm, cur, manifest, args.jobs,
                              args.update_baseline)
        if args.update_baseline:
            update_census_baseline(points, results, manifest, bool(args.quick or args.devices))
        rep["steps"]["checks"] = {"seconds": round(time.time() - t, 1)}
        for pt in points:
            r = results.setdefault(pt["id"], {})
            ra, pb = ref.get(pt["id"]) or {}, pcell.get(pt["id"]) or {}
            r.update({"messages": pb.get("messages", ra.get("log", "")),
                      "pcell_cell": pb.get("variant"), "stored": pb.get("stored"),
                      "checked_dict": pb.get("checked")})

        log("step 5b: the dialog's bindings against the server's")
        binds = step_bindings(points, dlg, pdk_env(KMP_CACHE_DIR=os.path.join(out, "cache-bind")),
                              manifest)
        shutil.rmtree(os.path.join(out, "cache-bind"), ignore_errors=True)
        for pid, d in binds.items():
            results[pid]["bindings"] = d
        bdev = {pt["device"] for pt in points if pt["id"] in binds}
        rep["steps"]["bindings"] = {"devices": len(bdev), "records": len(binds),
                                    "same": sum(1 for d in binds.values() if d["same"])}
        log("  %d devices (%d records), %d records with the same bindings"
            % (len(bdev), len(binds), rep["steps"]["bindings"]["same"]))

        log("step 5c: box-paint generators through Magic's menu, under Xvfb")
        menu, note = step_menu(out, points, ref, manifest)
        for pid, v in menu.items():
            results[pid]["menu"] = v
        rep["steps"]["menu"] = {"note": note, "points": len(menu)}
        log("  " + note)

        log("step 6: round trips")
        t = time.time()
        rt, n_rt = step_roundtrip(out, points, ref, dlg, pcell, results, args.seed)
        for pid, d in rt.items():
            results[pid]["roundtrip"] = d
        rep["steps"]["roundtrip"] = {"points": n_rt, "seconds": round(time.time() - t, 1)}

        sheets = None
        if not (args.no_drc and args.no_extract):
            log("building DRC sheets")
            sheets = build_sheets(out, points, ref, dlg, pcell, results)
        if not args.no_drc:
            import drc as drcmod
            rep["meta"]["klayout_drc"] = drcmod.describe(PDK)
            log("step 7: DRC (%d sheets; KLayout: %s)" % (len(sheets), drcmod.describe(PDK)))
            sheet_sets, single_sets, unassigned, tdrc = step_drc(out, sheets, args.jobs)
            rep["steps"]["drc"] = {"sheets": sum(1 for s in sheets if not s["single"]),
                                   "singles": sum(1 for s in sheets if s["single"]),
                                   "seconds": tdrc, "unassigned_markers": unassigned[:50],
                                   "unassigned_count": len(unassigned)}
            apply_drc(points, results, sheet_sets, single_sets, args.update_baseline, rep)
            log("  DRC %.1f s, %d unassigned markers" % (tdrc, len(unassigned)))
        if not args.no_extract:
            log("step 8: extraction of MOSFET points")
            t = time.time()
            ex = step_extract(out, sheets, points, args.jobs)
            known = load_extract_known()
            for pt in points:
                if pt["family"] != "mos" or pt["id"] not in ex:
                    continue
                results[pt["id"]]["extract"] = extract_verdict(
                    pt, ex[pt["id"]], (pcell.get(pt["id"]) or {}).get("checked"), known)
            rep["steps"]["extract"] = {"points": len(ex), "seconds": round(time.time() - t, 1)}
        if not args.no_jobs:
            log("step 9: jobs, the plugin's Magic jobs against their references (tests/jobs)")
            if REPO not in sys.path:
                sys.path.insert(0, REPO)
            from tests.jobs import run_jobs
            sec = run_jobs.run_step(PDK, os.path.join(out, "jobs"), quick=args.quick,
                                    update_baseline=args.update_baseline, workers=args.jobs,
                                    keep=args.keep, log=log, env=pdk_env())
            rep["jobs"] = sec
            rep["steps"]["jobs"] = {"ok": sec["ok"], "seconds": sec["seconds"],
                                    "job_seconds": sec["job_seconds"], "units": sec["units"],
                                    "failed": sec["fail"], "errors": len(sec["errors"])}
    except Exception as e:
        rep["harness_errors"].append("%s: %s\n%s" % (type(e).__name__, e, traceback.format_exc()))
        log("HARNESS ERROR: %s" % e)

    rep["meta"]["seconds"] = round(time.time() - t0, 1)
    report.finalize(rep, points, results, manifest, out)
    if not args.keep and not rep["harness_errors"]:
        cleanup(out, points, results)
    return rep


def apply_drc(points, results, sheet_sets, single_sets, update_baseline, rep):
    baseline = {}
    if os.path.isfile(BASELINE) and not update_baseline:
        with open(BASELINE) as f:
            baseline = json.load(f).get("devices", {})
    new_baseline = {}
    for pt in points:
        pid = pt["id"]
        if pid not in sheet_sets:
            continue
        s = sheet_sets[pid]
        d = {"klayout": {"ref": s.get("klayout", {}).get("ref"), "pcell": s.get("klayout", {}).get("pcell")},
             "magic": {"ref": s.get("magic", {}).get("ref"), "pcell": s.get("magic", {}).get("pcell")}}
        tools = [t for t in ("klayout", "magic") if t in s]
        d["equal"] = all(d[t]["ref"] == d[t]["pcell"] for t in tools)
        if pt["kind"] == "default":
            single = single_sets.get(pid, {})
            d["single"] = {t: single.get(t, {}).get("pcell") for t in tools}
            d["single_matches_sheet"] = all(d["single"][t] == d[t]["pcell"] for t in tools)
            new_baseline[pt["device"]] = {t: d[t]["pcell"] for t in tools}
            b = baseline.get(pt["device"])
            if update_baseline:
                d["baseline"] = "updated"
            elif b is None:
                d["baseline"] = "missing"
            else:
                diff = [t for t in tools if sorted(b.get(t) or []) != (d[t]["pcell"] or [])
                        or sorted(b.get(t) or []) != (d[t]["ref"] or [])]
                d["baseline"] = "ok" if not diff else "differs (%s)" % ", ".join(diff)
        results[pid]["drc"] = d
    if update_baseline:
        n_gen = rep["meta"].get("generators", 0)
        if rep["meta"].get("quick") or rep["meta"].get("devices") or len(new_baseline) < n_gen:
            # A partial run would drop devices from the baseline; merge instead.
            if os.path.isfile(BASELINE):
                with open(BASELINE) as f:
                    old = json.load(f).get("devices", {})
                old.update(new_baseline)
                new_baseline = old
        import drc as drcmod
        doc = {"comment": "Rule IDs that each tool reports on each device's default point "
                          "(Magic drc(full) with catchup; KLayout: %s). Written by "
                          "run_sweep.py --update-baseline." % drcmod.describe(PDK),
               "magic": rep["meta"].get("magic"), "tech": rep["meta"].get("tech"),
               "open_pdks": rep["meta"].get("open_pdks"), "klayout": rep["meta"].get("klayout"),
               "devices": {k: new_baseline[k] for k in sorted(new_baseline)}}
        os.makedirs(os.path.dirname(BASELINE), exist_ok=True)
        with open(BASELINE, "w") as f:
            json.dump(doc, f, indent=1)
            f.write("\n")


if __name__ == "__main__":
    sys.exit(main())
