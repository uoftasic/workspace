"""Command line: python3 -m klayout_magic_pcells <command> ...

  doctor [--pdk P]                     configuration, versions, manifest check, timing
  check DEVICE [k=v ...]               run Magic's _check once and show what it changes
  generate DEVICE [k=v ...] -o out.gds place one PCell variant and write a file
  audit FILE [--regen]                 report the Magic-generated cells in a file
  cache {stats,prune,clear}            the disk cache and the job directories
  devices [-v]                         list the PCells and their parameters

Checks that run Magic (and netgen) on a layout file:

  drc FILE [--cell C]... [--style S] [--mode hierarchical|flat] [--box L,B,R,T]
      [-o OUT.lyrdb] [--tsv OUT.tsv] [--no-cache]
  extract FILE [--cell C] [--caps] [--flatglob] [--ports-from-labels] [-o OUT.spice]
      [--rdb OUT.lyrdb] [--no-cache]
  lvs FILE --schematic SCH [--schematic-cell C] [--cell C] [--flatglob] [--ports-from-labels]
      [-o OUT.lyrdb] [--report OUT.txt] [--json OUT.json] [--no-cache]
  layers FILE [--cell C] [-o OUT.lyrdb] [--json OUT.json] [--no-cache]
  ports FILE [--cell C] [--magic] [-o OUT.lyrdb] [--json OUT.json]

--cell defaults to the file's one top cell. The PDK comes from --pdk, else
the layout's technology, its PCell libraries, KMP_PDKS when it selects one
PDK, and last the PDK variable as a guess. Exit status: 0 when the check
finds nothing, 1 when it finds something, 2 when the input or a job fails.

A device is found in the manifests of the selected PDKs (KMP_PDKS); a name
that more than one PDK has (rm1) needs --pdk.
"""

import argparse
import importlib
import importlib.util
import json
import os
import sys
import time


def _cfg(pdk=None):
    from .config import Config
    return Config.load(pdk=pdk)


def _pdks(args, cfg=None):
    """The PDKs a command works on: --pdk, else the selected ones."""
    if getattr(args, "pdk", None):
        return [args.pdk]
    cfg = cfg or _cfg()
    return list(cfg.pdks)


def _find_device(args):
    """(Config, Manifest, DeviceSpec) for args.device; exits on errors."""
    from .config import SUPPORTED_PDKS
    from .manifest import Manifest
    base = _cfg(getattr(args, "pdk", None))
    cands = [args.pdk] if getattr(args, "pdk", None) else (list(base.pdks) or list(SUPPORTED_PDKS))
    hits = []
    for p in cands:
        c = base.for_pdk(p)
        try:
            man = Manifest.load(c.manifest)
        except Exception:
            continue
        spec = man.get(args.device)
        if spec is not None:
            hits.append((c, man, spec))
    if not hits:
        raise SystemExit("error: unknown device %s in %s (try: devices)" % (args.device, ", ".join(cands)))
    if len(hits) > 1:
        raise SystemExit("error: %s is a device of %s; choose one with --pdk"
                         % (args.device, ", ".join(h[0].pdk for h in hits)))
    return hits[0]


def _kv(items, spec):
    vals = {}
    for it in items:
        if "=" not in it:
            raise SystemExit("error: expected name=value, got %r" % it)
        k, v = it.split("=", 1)
        p = spec.param(k)
        if p is None:
            raise SystemExit("error: %s has no parameter %r (try: devices -v)" % (spec.name, k))
        try:
            vals[k] = p.parse(v)
        except ValueError as e:
            # A refused value exits 2, as check does for one Magic must not see.
            sys.stderr.write("error: %s=%r is not a %s: %s\n" % (
                k, v, {"int": "whole number", "float": "number", "bool01": "0 or 1"}.get(p.type, p.type), e))
            raise SystemExit(2)
    return vals


def cmd_doctor(args):
    from .backend import MagicServer
    from .manifest import Manifest, diff_defaults
    ok = True
    try:
        base = _cfg(args.pdk)
    except Exception as e:
        print("configuration error: %s" % e)
        return 2
    print("configuration (config file: %s)" % (base.config_file or "none"))
    for name, val, src in base.describe():
        if name in ("pdk", "magicrc", "manifest", "netgen_setup"):
            continue
        print("  %-14s %-60s %s" % (name, val, src))
    for p, why in base.pdk_errors.items():
        ok = False
        print("PROBLEM: %s" % why)
    netgen_problems = [p for p in base.job_problems() if p.startswith("netgen not found")]
    for p in netgen_problems:
        ok = False
        print("PROBLEM: " + p)
    try:
        import klayout.db as kdb
        print("klayout module %s" % getattr(kdb, "__version__", "?"))
    except ImportError:
        print("klayout Python module: not importable (only needed outside KLayout)")
    pdks = [args.pdk] if args.pdk else base.pdks
    if not pdks:
        ok = False
        print("PROBLEM: no PDK selected (KMP_PDKS) or installed under %s" % base.pdk_root)
    for pdk in pdks:
        cfg = base.for_pdk(pdk)
        print("\n%s -> library %s" % (pdk, cfg.library_name))
        for name in ("magicrc", "manifest", "netgen_setup"):
            print("  %-14s %-60s %s" % (name, getattr(cfg, name), cfg.sources.get(name, "")))
        for p in cfg.job_problems():
            if p not in netgen_problems:
                ok = False
                print("PROBLEM: " + p)
        probs = cfg.problems()
        for p in probs:
            ok = False
            print("PROBLEM: " + p)
        if probs:
            continue
        man = Manifest.load(cfg.manifest)
        s = MagicServer(cfg, vendor_cells=man.vendor_cells())
        try:
            t = time.time()
            v = s.start()
            print("  Magic started in %.2f s: %s" % (time.time() - t, v.magic_banner))
            print("  magic %s, tech %s (%s), PDK commit %s, namespace %s, Tcl %s"
                  % (v.magic, v.tech, v.tech_name, v.pdk_commit or "?", v.namespace, v.tcl))
            if v.defaults_digest == man.defaults_digest:
                print("  manifest matches the running Magic (%d devices, %d box-paint generators)"
                      % (sum(1 for d in man.devices if d.kind == "device"),
                         sum(1 for d in man.devices if d.kind == "box")))
            else:
                ok = False
                print("  MANIFEST MISMATCH: defaults digest %s, manifest has %s"
                      % (v.defaults_digest[:16], man.defaults_digest[:16]))
                for dev, why in diff_defaults(man.defaults_by_device(), v.defaults):
                    print("    %s: %s" % (dev, why))
            missing = [d.name for d in man.devices if d.kind == "box" and d.name not in v.boxpaint]
            if missing:
                ok = False
                print("  MISSING box-paint generators: %s" % ", ".join(missing))
            spec = next((d for d in man.devices if d.family == "mos"), man.devices[0])
            out = os.path.join(s.run_dir, "doctor.gds")
            t = time.time()
            r = s.generate(spec.name, {}, spec.form, out)
            print("  %s defaults generated in %.1f ms (%s)" % (spec.name, (time.time() - t) * 1000, r.cell))
        except Exception as e:
            ok = False
            print("  BACKEND ERROR: %s" % e)
        finally:
            s.close()
    return 0 if ok else 1


class _Direct:
    """dialog.correct()'s generator, straight to one MagicServer, with no
    cache."""

    def __init__(self, server):
        self.server = server
        self.n = 0

    def dialog(self, spec, form, edits, want_apply_name=False):
        rep = self.server.dialog(spec, form, edits, want_apply_name=want_apply_name)
        return {"form": rep.form, "numbers": rep.numbers, "log": rep.log, "source": "magic",
                "apply_name": rep.apply_name}

    def get(self, spec, request):
        from .backend import Result, _json_kv, split_apply
        params, apply = split_apply(request)
        self.n += 1
        out = os.path.join(self.server.run_dir, "check%d.gds" % self.n)
        g = self.server.generate(spec.name, params, spec.form, out, apply=apply)
        side = {"request": dict(request), "checked": g.checked, "messages": g.log,
                "magic_cell": g.cell}
        if "opened" in g.kv:
            side.update({"opened": _json_kv(g.kv, "opened", {}),
                         "opened_numbers": _json_kv(g.kv, "opened_numbers", {}),
                         "checked_numbers": _json_kv(g.kv, "checked_numbers", {}),
                         "opened_type": g.kv.get("opened_type", ""),
                         "opened_note": g.kv.get("opened_note", "")})
        return Result("", out, side, "magic")


def cmd_check(args):
    """For a device: type the values into Magic's dialog (as the PCell form
    does), press Create, and show what the dialog then shows and whether
    Magic drew anything (a _check can hand _draw a value it fails on, such
    as the SPICE string "1.218u"). For a box-paint generator: the box Magic
    paints. Exits 1 when Magic draws nothing, 2 for a refused value."""
    from .backend import BackendError, MagicServer
    from .dialog import correct
    from .importer import gds_has_shapes
    from .manifest import InvalidValue
    from .pcell import changed_params
    cfg, man, spec = _find_device(args)
    vals = spec.defaults_values()
    vals.update(_kv(args.params, spec))
    try:
        req = spec.build_request(vals)
    except InvalidValue as e:
        print("error: %s" % e)
        return 2
    s = MagicServer(cfg, vendor_cells=man.vendor_cells())
    corr = None
    try:
        s.start()
        if spec.kind != "box":
            corr = correct(spec, vals, "", _Direct(s))
            req = corr.request
            out = corr.result.gds_path
            glog = corr.result.messages
        else:
            out = os.path.join(s.run_dir, "check.gds")
            glog = s.generate(spec.name, req, spec.form, out).log
        r = s.check(spec.name, req, spec.form if spec.kind == "box" else None)
        drawn = gds_has_shapes(out)
    except InvalidValue as e:
        print("error: %s" % e)
        return 2
    except BackendError as e:
        print("error: %s" % e)
        return 1
    finally:
        s.close()
    ch = changed_params(req, r.checked)
    if spec.kind == "box":
        messages = [ln for ln in (glog if not drawn else r.log).strip().splitlines() if ln.strip()]
        size = "%s x %s um" % (r.checked.get("w", req["w"]), r.checked.get("h", req["h"]))
        entered = " (entered %s x %s)" % (req["w"], req["h"]) if ch else ""
        if drawn:
            print("%s: Magic paints a %s box%s" % (spec.name, size, entered))
        else:
            print("%s: Magic paints nothing on a %s box%s" % (spec.name, size, entered))
    else:
        messages = []
        for ln in corr.log.strip().splitlines():
            if ln.strip() and ln not in messages:
                messages.append(ln)
        if r.kv.get("check") == "none":
            print("%s: the PDK has no _check proc for it; Magic draws the values unchecked" % spec.name)
        elif r.kv.get("check") == "failed":
            print("%s: _check failed (%s); Magic draws the values unchecked"
                  % (spec.name, r.kv.get("check_error", "")))
        if not corr.corrected and not corr.changed:
            print("%s: Magic's dialog changes nothing" % spec.name)
        for k, (typed, shown) in corr.corrected.items():
            print("%s: Magic's dialog shows %s=%s (entered %s)" % (spec.name, k, corr.shows[k], typed))
        for k, (before, shown) in corr.changed.items():
            print("%s: Magic's dialog sets %s=%s" % (spec.name, k, corr.shows[k]))
        if not drawn:
            print("%s: Magic draws nothing for these values" % spec.name)
    for line in messages:
        print("  message: " + line)
    return 0 if drawn else 1


def cmd_generate(args):
    from . import register, state_for
    cfg, man, spec = _find_device(args)
    lib = register(cfg.pdk)
    if lib is None:
        print("error: %s" % state_for(cfg.pdk).last_error)
        return 2
    from ._kl import db
    ly = db.Layout()
    ly.dbu = 0.001
    top = ly.create_cell(args.top)
    params = _kv(args.params, spec)
    if spec.kind != "box":
        # Store what Magic's dialog shows, as the GUI does.
        from . import dialog_values
        try:
            params = dialog_values(spec.name, params, pdk=cfg.pdk)
        except Exception as e:
            # The PCell then draws the error marker and says why.
            print("warning: Magic's dialog failed (%s); the values are stored as typed" % e)
    pc = ly.create_cell(spec.name, lib.name(), params)
    top.insert(db.CellInstArray(pc.cell_index(), db.Trans()))
    ly.write(args.output)
    print("wrote %s: %s (%s), bbox %s um" % (args.output, pc.name, pc.display_title(), pc.dbbox()))
    # Exit 1 when the file holds no device: the error marker, or Magic's
    # empty cell.
    from .pcell import PLACEHOLDER_LAYER
    ph = ly.find_layer(*PLACEHOLDER_LAYER)
    marker = [sh.text_string for sh in pc.shapes(ph).each() if sh.is_text()] if ph is not None else []
    if marker:
        print("error: generation failed; the cell holds the marker %r" % marker[0])
        return 1
    if pc.dbbox().empty():
        print("error: Magic drew nothing for these parameters; the cell is empty")
        return 1
    return 0


def cmd_audit(args):
    from .audit import audit, format_report
    rep = audit(args.file, regen=args.regen, notes=print)
    if args.json:
        print(json.dumps(rep, indent=1, default=str))
    else:
        print(format_report(rep))
    return 1 if any(c["problems"] for c in rep["cells"]) or rep.get("file_problems") else 0


def cmd_cache(args):
    from .backend import MagicServer
    from .cache import GdsCache, prune_jobs, versions_fields
    from .jobs import job_fingerprint
    from .manifest import Manifest
    base = _cfg(args.pdk)
    if args.action == "clear":
        GdsCache(base.cache_dir, {}, enabled=True).clear()
        print("cleared %s (entries and job directories)" % base.cache_dir)
        return 0
    # The current versions directory of each PDK this command works on
    # (--pdk, else KMP_PDKS); prune keeps those and leaves other PDKs alone.
    caches = []
    for pdk in ([args.pdk] if args.pdk else base.pdks):
        cfg = base.for_pdk(pdk)
        if cfg.problems():
            print("note: %s is not usable (%s); its entries are left alone" % (pdk, cfg.problems()[0]))
            continue
        s = MagicServer(cfg, vendor_cells=Manifest.load(cfg.manifest).vendor_cells())
        try:
            v = s.start()
        finally:
            s.close()
        caches.append((pdk, GdsCache(base.cache_dir, versions_fields(v, pdk), enabled=True)))
    if not caches:
        print("error: no usable PDK to read the current versions from")
        return 1
    current = {p: c.vdigest for p, c in caches}
    if args.action == "prune":
        removed, other = caches[0][1].prune(current=current)
        for d in removed:
            print("removed %s" % d)
        for d, pdk in sorted(other.items()):
            print("kept %s: entries of %s, which this prune doesn't work on (it works on %s; "
                  "use --pdk %s, or KMP_PDKS)" % (d, pdk, ", ".join(sorted(current)), pdk))
        for d in prune_jobs(base.cache_dir, {p: job_fingerprint(base.for_pdk(p)) for p in current}):
            print("removed %s" % d)
    # Job directories: those of --pdk's PDK, else of every PDK.
    st = caches[0][1].stats(pdks=[args.pdk] if args.pdk else None)
    st.update(root=base.cache_dir, current=current)
    print(json.dumps(st, indent=1))
    return 0


def cmd_devices(args):
    from .manifest import Manifest
    base = _cfg(args.pdk)
    for pdk in ([args.pdk] if args.pdk else base.pdks):
        cfg = base.for_pdk(pdk)
        try:
            man = Manifest.load(cfg.manifest)
        except Exception as e:
            print("%s: %s" % (pdk, e))
            continue
        print("%s (library %s)" % (pdk, cfg.library_name))
        for d in man.devices:
            extra = ", fixed layout" if d.nocell else ", box paint: %s" % d.label if d.kind == "box" else ""
            print("  %s  [%s%s]" % (d.name, d.family, extra))
            if args.verbose:
                for p in d.params:
                    print("      %-10s %-7s default %-8s %s" % (p.name, p.type, p.default, p.label))
    return 0


# -- the checks that run Magic as a job --------------------------------------

# The module that implements each job command (its cli_main(args, ctx)).
FEATURES = {"drc": "drcjob", "extract": "lvsjob", "lvs": "lvsjob", "layers": "layercheck",
            "ports": "portcheck"}


class JobContext:
    """What a job command's cli_main gets besides its arguments."""

    def __init__(self, cfg, pdk, pdk_reason, layout, cells, file, data):
        self.cfg = cfg
        self.pdk = pdk
        self.pdk_reason = pdk_reason
        self.layout = layout
        self.cells = cells
        self.file = file
        self.data = data


def _load_pdk_data(pdk):
    """The PDK's data file (pdkdata.load), or None while pdkdata.py isn't
    built."""
    if importlib.util.find_spec("klayout_magic_pcells.pdkdata") is None:
        return None
    from . import pdkdata
    return pdkdata.load(pdk)


def _feature_main(cmd):
    """The command's cli_main, or None while its module isn't built."""
    name = "klayout_magic_pcells." + FEATURES[cmd]
    if importlib.util.find_spec(name) is None:
        return None
    return importlib.import_module(name).cli_main


def _fail(msg):
    sys.stderr.write("error: %s\n" % msg)
    return 2


def job_context(args):
    """Read the file, check the cells, choose the PDK and load its data.
    Returns a JobContext, or the exit status 2 after an error message."""
    from .config import ConfigError
    from .export import ExportError, load_layout, resolve_cells
    from .pdkchoice import PdkChoiceError, choose_pdk
    # An absolute path, so the RDB's rerun record (its generator) and job
    # descriptions name the file wherever KLayout is started from.
    args.file = os.path.abspath(args.file)
    try:
        layout = load_layout(args.file)
    except ExportError as e:
        return _fail(str(e))
    names = args.cell if isinstance(args.cell, list) else ([args.cell] if args.cell else [])
    try:
        cells = resolve_cells(layout, names)
    except ExportError as e:
        if e.missing:
            return _fail("; ".join("cell %s is not in %s" % (n, args.file) for n in e.missing))
        return _fail("%s has %d top cells (%s); choose one with --cell"
                     % (args.file, len(e.tops), ", ".join(e.tops)) if e.tops else str(e))
    try:
        base = _cfg()
        pdk, reason = choose_pdk(layout, explicit=args.pdk, cfg=base)
        cfg = base.for_pdk(pdk)
    except PdkChoiceError as e:
        return _fail("%s" % e)
    except ConfigError as e:
        return _fail("configuration: %s" % e)
    if reason.startswith("a guess"):
        sys.stderr.write("note: PDK %s, %s\n" % (pdk, reason))
    try:
        data = _load_pdk_data(pdk)
    except Exception as e:
        return _fail("no PDK data for %s: %s" % (pdk, e))
    if args.cmd == "drc":
        args.style = args.style or cfg.drc_style
        args.mode = args.mode or cfg.drc_mode
    return JobContext(cfg, pdk, reason, layout, cells, args.file, data)


def cmd_job(args):
    ctx = job_context(args)
    if isinstance(ctx, int):
        return ctx
    fn = _feature_main(args.cmd)
    if fn is None:
        sys.stderr.write("%s: not built yet\n" % args.cmd)
        return 2
    return fn(args, ctx)


def _box(text):
    try:
        v = [float(x) for x in text.split(",")]
    except ValueError:
        v = []
    if len(v) != 4 or not (v[0] < v[2] and v[1] < v[3]):
        raise argparse.ArgumentTypeError("expected L,B,R,T in um with L < R and B < T, not %r" % text)
    return tuple(v)


def _join_box(argv):
    """``--box -0.592,0,1.592,1.5`` as ``--box=-0.592,0,1.592,1.5``:
    argparse takes a value that starts with "-" for an option and stops
    with "expected one argument"."""
    out = list(argv)
    for i in range(len(out) - 1):
        nxt = out[i + 1]
        if out[i] == "--box" and nxt.startswith("-"):
            try:
                ok = len([float(x) for x in nxt.split(",")]) == 4
            except ValueError:
                ok = False
            if ok:
                out[i:i + 2] = ["--box=" + nxt, None]
    return [a for a in out if a is not None]


NO_CACHE_HELP = ("run Magic again, as with KMP_CACHE=0: in a new directory under <cache>/jobs, "
                 "removed afterwards (KMP_JOB_KEEP=1 keeps it)")


def _add_job_commands(add):
    p = add("drc", cmd_job)
    p.add_argument("file")
    p.add_argument("--cell", action="append", help="a cell to check (repeatable; default: the top cell)")
    p.add_argument("--style", help="Magic's DRC style (default KMP_DRC_STYLE, drc(full))")
    p.add_argument("--mode", choices=("hierarchical", "flat"),
                   help="hierarchical (default, KMP_DRC_MODE): every cell, then the top cell; "
                        "flat: Magic's verdict on the flattened mask")
    p.add_argument("--box", type=_box, help="check this area only: L,B,R,T in um")
    p.add_argument("-o", "--output", help="write the markers to this .lyrdb file")
    p.add_argument("--tsv", help="write the error boxes to this file")
    p.add_argument("--no-cache", dest="no_cache", action="store_true", help=NO_CACHE_HELP)
    p = add("extract", cmd_job)
    p.add_argument("file")
    p.add_argument("--cell")
    p.add_argument("--caps", action="store_true", help="with parasitic capacitance")
    p.add_argument("--flatglob", action="store_true", help="flatten the plugin's __kmp_ cells")
    p.add_argument("--ports-from-labels", dest="ports_from_labels", action="store_true")
    p.add_argument("-o", "--output", help="write the netlist to this file (default: <cell>.magic.spice, "
                                           "or <cell>.magic.pex.spice with --caps, beside the layout)")
    p.add_argument("--rdb", help="write the report to this .lyrdb file")
    p.add_argument("--no-cache", dest="no_cache", action="store_true", help=NO_CACHE_HELP)
    p = add("lvs", cmd_job)
    p.add_argument("file")
    p.add_argument("--schematic", required=True, help="the schematic netlist (SPICE or CDL)")
    p.add_argument("--schematic-cell", dest="schematic_cell")
    p.add_argument("--cell")
    p.add_argument("--flatglob", action="store_true", help="flatten the plugin's __kmp_ cells")
    p.add_argument("--ports-from-labels", dest="ports_from_labels", action="store_true")
    p.add_argument("-o", "--output", help="write the markers to this .lyrdb file")
    p.add_argument("--report", help="write netgen's report to this file")
    p.add_argument("--json", help="write the findings to this file")
    p.add_argument("--no-cache", dest="no_cache", action="store_true", help=NO_CACHE_HELP)
    p = add("layers", cmd_job)
    p.add_argument("file")
    p.add_argument("--cell")
    p.add_argument("-o", "--output", help="write the markers to this .lyrdb file")
    p.add_argument("--json", help="write the findings to this file")
    p.add_argument("--no-cache", dest="no_cache", action="store_true", help=NO_CACHE_HELP)
    p = add("ports", cmd_job)
    p.add_argument("file")
    p.add_argument("--cell")
    p.add_argument("--magic", action="store_true", help="also extract with Magic and compare its ports")
    p.add_argument("-o", "--output", help="write the markers to this .lyrdb file")
    p.add_argument("--json", help="write the findings to this file")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python3 -m klayout_magic_pcells",
                                 description="KLayout PCells generated by Magic")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add(name, fn):
        p = sub.add_parser(name)
        p.add_argument("--pdk", help="the PDK (default: the selected ones, KMP_PDKS)")
        p.set_defaults(fn=fn)
        return p
    add("doctor", cmd_doctor)
    p = add("check", cmd_check)
    p.add_argument("device")
    p.add_argument("params", nargs="*")
    p = add("generate", cmd_generate)
    p.add_argument("device")
    p.add_argument("params", nargs="*")
    p.add_argument("-o", "--output", required=True)
    p.add_argument("--top", default="TOP")
    p = add("audit", cmd_audit)
    p.add_argument("file")
    p.add_argument("--regen", action="store_true")
    p.add_argument("--json", action="store_true")
    p = add("cache", cmd_cache)
    p.add_argument("action", choices=("stats", "prune", "clear"))
    p = add("devices", cmd_devices)
    p.add_argument("-v", "--verbose", action="store_true")
    _add_job_commands(add)
    args = ap.parse_args(_join_box(sys.argv[1:] if argv is None else argv))
    return args.fn(args)


if __name__ == "__main__":
    # "devices -v | head" closes the pipe early: exit quietly (status 141)
    # instead of printing a BrokenPipeError traceback. Linux only, as is the
    # plugin.
    import signal
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    sys.exit(main())
