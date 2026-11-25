"""The plugin's PCells through Magic's GDS reader (design-0.6.md 3.2, 6.5).

Every device default of the PDK is generated with ``magic::gencell``,
extracted from Magic's database, written to GDS by Magic, read back in a
fresh Magic and extracted again, with the harness's netlist-only settings
(the review's method). The devices whose two extractions differ must be
the ones ``data/readback-<pdk>.json`` lists.

The jobs step of tests/parity/run_sweep.py runs ``check()``;
tests/backend/test_lvs_backend.py's ReadbackTest uses the same functions
and can rewrite the data file (KMP_READBACK_WRITE=1).
"""

import collections
import json
import os
import shutil

from klayout_magic_pcells import jobs

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                        "python", "klayout_magic_pcells", "data")

READBACK_MEM_TCL = r"""
source $::env(KMP_TCL_DIR)/kmp_job_common.tcl
set ns $::env(KMP_NS)
set out $::env(KMP_DIR)
file mkdir [file join $out mem] [file join $out gds]
set n 0
foreach dev [split $::env(KMP_DEVS)] {
    if {[catch {
        load kmp_ref_$dev -silent
        box 0 0 0 0
        magic::gencell ${ns}::$dev kmp_inst
        set made [instance list celldef kmp_inst]
        set nocell [dict exists [${ns}::${dev}_defaults] nocell]
        set top [expr {$nocell ? "kmp_ref_$dev" : $made}]
        load $top
        select top cell
        extract path [file join $out mem]
        extract no capacitance
        extract no coupling
        extract no resistance
        extract no length
        extract all
        ext2spice lvs
        ext2spice -p [file join $out mem] -o [file join $out mem $dev.spice]
        gds write [file join $out gds $dev.gds]
        kmp_job_say "KMP_RB_MEM $dev $top"
    } err]} {
        kmp_job_say "KMP_RB_ERR $dev [string map {\n { }} $err]"
    }
    catch {load kmp_ref_base -silent}
    incr n
}
kmp_job_done $n
"""

READBACK_GDS_TCL = r"""
source $::env(KMP_TCL_DIR)/kmp_job_common.tcl
kmp_job_read $::env(KMP_GDS)
kmp_job_load $::env(KMP_TOP)
extract path $::env(KMP_DIR)
extract no capacitance
extract no coupling
extract no resistance
extract no length
extract all
ext2spice lvs
ext2spice -p $::env(KMP_DIR) -o [file join $::env(KMP_DIR) back.spice]
kmp_job_done 1
"""

_SIZE_KEYS = ("w", "l", "m", "nf", "mult", "area", "pj", "a", "p", "ng", "c", "r")


def netlist_devices(path):
    """The device lines of an ext2spice netlist as a Counter of (letter,
    model, size parameters), calls of subcircuits defined in the same file
    left out (they are the hierarchy, not devices); None for no file."""
    if not os.path.isfile(path):
        return None
    lines = []
    with open(path, errors="replace") as f:
        for raw in f:
            raw = raw.rstrip("\n")
            if raw.startswith("+") and lines:
                lines[-1] += " " + raw[1:]
            else:
                lines.append(raw)
    defined = {ln.split()[1] for ln in lines if ln.lower().startswith(".subckt") and len(ln.split()) > 1}
    out = collections.Counter()
    for ln in lines:
        s = ln.strip()
        if not s or s[0] not in "XxMmRrCcDdQq":
            continue
        toks = s.split()
        plain = [t for t in toks if "=" not in t]
        params = " ".join(sorted(t for t in toks if "=" in t and t.split("=")[0].lower() in _SIZE_KEYS))
        if s[0] in "Xx":
            model = plain[-1]
            if model in defined:
                continue
        else:
            model = plain[-1] if len(plain) > 3 else "?"
        out[(s[0].upper(), model, params)] += 1
    return out


def devices_text(counter):
    if not counter:
        return "none"
    return "; ".join("%s x%d%s" % (model, n, " (%s)" % params if params else "")
                     for (_letter, model, params), n in sorted(counter.items()))


def _kind(mem, back):
    if not back:
        return "lost"
    if {k[1] for k in mem} == {k[1] for k in back}:
        return "values"
    if {k[1] for k in mem} <= {k[1] for k in back}:
        return "split"
    return "changed"


def measure_readback(cfg, workdir):
    """[(device, mem Counter or None, back Counter or None, error)] for every
    device of the PDK's manifest."""
    from klayout_magic_pcells.manifest import Manifest
    man = Manifest.load(cfg.manifest)
    names = sorted(d.name for d in man.devices if getattr(d, "kind", "") != "box")
    os.makedirs(workdir, exist_ok=True)
    mem_tcl = os.path.join(workdir, "readback_mem.tcl")
    gds_tcl = os.path.join(workdir, "readback_gds.tcl")
    with open(mem_tcl, "w") as f:
        f.write(READBACK_MEM_TCL)
    with open(gds_tcl, "w") as f:
        f.write(READBACK_GDS_TCL)
    tops, errors = {}, {}
    memdir = os.path.join(workdir, "mem")
    for i, batch in enumerate(jobs.batches(names)):
        jd = os.path.join(workdir, "mem%d" % i)
        r = jobs.run_job(cfg, "extract", mem_tcl, env={"KMP_NS": man.namespace, "KMP_DEVS": " ".join(batch)},
                         job_dir=jd, timeout=600)
        for ln in r.stdout:
            p = ln.split(None, 2)
            if p[:1] == ["KMP_RB_MEM"] and len(p) == 3:
                tops[p[1]] = p[2]
            elif p[:1] == ["KMP_RB_ERR"] and len(p) >= 2:
                errors[p[1]] = p[2] if len(p) == 3 else "error"
        for sub in ("mem", "gds"):
            src = os.path.join(jd, sub)
            dst = os.path.join(workdir, sub)
            os.makedirs(dst, exist_ok=True)
            for n in os.listdir(src) if os.path.isdir(src) else []:
                shutil.copy(os.path.join(src, n), os.path.join(dst, n))
    out = []
    for dev in names:
        mem = netlist_devices(os.path.join(memdir, dev + ".spice"))
        gds = os.path.join(workdir, "gds", dev + ".gds")
        back, err = None, errors.get(dev)
        if dev in tops and os.path.isfile(gds):
            jd = os.path.join(workdir, "back", dev)
            r = jobs.run_job(cfg, "extract", gds_tcl, env={"KMP_GDS": gds, "KMP_TOP": tops[dev]},
                             job_dir=jd, timeout=300)
            back = netlist_devices(os.path.join(jd, "back.spice")) if r.ok else None
            if not r.ok:
                err = "read-back job failed: %s" % r.error
        elif err is None:
            err = "Magic wrote no netlist from its database"
        if mem is None and err is None:
            err = "Magic's database extraction left no netlist (ext2spice wrote no file)"
        out.append((dev, mem, back, err))
    return out


def readback_rows(measured):
    """The data file's device rows: the devices whose two extractions differ."""
    rows = []
    for dev, mem, back, err in measured:
        if mem is None:
            continue
        if back is None and err:
            continue
        if mem == back:
            continue
        rows.append({"device": dev, "database": devices_text(mem), "gds": devices_text(back),
                     "kind": _kind(mem, back or {}),
                     "database_devices": [[m, p, n] for (_l, m, p), n in sorted(mem.items())],
                     "gds_devices": [[m, p, n] for (_l, m, p), n in sorted((back or {}).items())],
                     "note": ""})
    return rows


def data_path(pdk):
    return os.path.join(DATA_DIR, "readback-%s.json" % pdk)


def unmeasured_of(measured):
    """[(device, why)] of the devices that could not be compared."""
    return [(d, e) for d, mem, back, e in measured if mem is None or (back is None and e)]


def differences(pdk, measured, path=None):
    """What the measurement shows that the data file does not list, as
    readable lines; [] when the two agree."""
    with open(path or data_path(pdk), encoding="utf-8") as f:
        listed = json.load(f)
    want = {r["device"]: (r["database"], r["gds"]) for r in listed.get("devices", [])}
    got = {r["device"]: (r["database"], r["gds"]) for r in readback_rows(measured)}
    out = []
    for dev in sorted(set(got) | set(want)):
        if dev not in want:
            out.append("%s: not in the data file; database %s, read back %s" % (dev, got[dev][0], got[dev][1]))
        elif dev not in got:
            out.append("%s: listed in the data file, but both extractions now agree" % dev)
        elif got[dev] != want[dev]:
            out.append("%s: database %s, read back %s; the data file says database %s, read back %s"
                       % (dev, got[dev][0], got[dev][1], want[dev][0], want[dev][1]))
    um = sorted(d for d, _ in unmeasured_of(measured))
    listed_um = sorted(r["device"] for r in listed.get("unmeasured", []))
    if um != listed_um:
        out.append("devices that could not be measured: %s; the data file lists %s" % (um, listed_um))
    return out
