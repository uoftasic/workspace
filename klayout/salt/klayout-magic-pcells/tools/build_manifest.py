#!/usr/bin/env python3
"""Build a PDK's device manifest from the installed Magic and PDK.

Run inside the pinned image (Magic, the PDK and the klayout Python module
are needed)::

    python3 tools/build_manifest.py --pdk gf180mcuD          # rewrite the shipped manifest
    python3 tools/build_manifest.py --pdk gf180mcuD --check  # compare with the shipped one
    python3 tools/build_manifest.py --all [--check]          # every supported PDK
    python3 tools/build_manifest.py --pdk sky130A --out other.json

Without --pdk or --all it works on the PDK that KMP_PDK names (sky130A by
default).

``scripts/manifest.sh`` runs either form in the image. Exit status: 0 when
written or when ``--check`` finds no difference, 1 when ``--check`` finds a
difference, 2 on errors.
"""

import argparse
import json
import math
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "python"))

from klayout_magic_pcells import backend  # noqa: E402
from klayout_magic_pcells.config import Config, SUPPORTED_PDKS, TCL_DIR, shipped_manifest  # noqa: E402

# Counts: sent as integers (IHP's _check procs test "string is int", so
# "2.0" fingers become 1 finger).
COUNT_KEYS = {"nf", "m", "nx", "ny", "ng", "turns"}
# Entries that take one number or a list of numbers, one per via layer.
NUMLIST_KEYS = {"nxcuts", "nycuts"}
HELPER_REASON = ("internal helper _draw proc: it takes required arguments, the device _draw procs "
                 "call it, and Magic's menus don't offer it")


def tcl_sources(pdk_path, pdk):
    """The PDK's generator Tcl files: <pdk>.tcl and the files next to it
    (the IHP PDKs split their generators into ihp-<pdk>-fet.tcl and so on)."""
    d = os.path.join(pdk_path, "libs.tech", "magic")
    main = os.path.join(d, pdk + ".tcl")
    try:
        others = sorted(os.path.join(d, f) for f in os.listdir(d)
                        if f.endswith(".tcl") and os.path.join(d, f) != main)
    except OSError:
        others = []
    return [main] + others


def _read_all(paths):
    text = ""
    for p in paths:
        try:
            with open(p, encoding="utf-8", errors="replace") as f:
                text += f.read() + "\n"
        except OSError:
            pass
    return text


def _command_lines(paths):
    """The Tcl source as logical lines: comment lines dropped (the IHP vias
    are commented out of the menu), backslash continuations joined."""
    lines = [l for l in _read_all(paths).splitlines() if not l.lstrip().startswith("#")]
    return re.sub(r"\\\n\s*", " ", "\n".join(lines)).splitlines()


def menu_commands(paths, ns):
    """{helper: (menu label, entry label)} for the _draw procs that the PDK's
    Tcl puts in Magic's toolkit menus as box-paint commands (bare
    "<ns>::<x>_draw" commands)."""
    lines = _command_lines(paths)
    menus = dict((tag, label) for label, tag in
                 re.findall(r'add_toolkit_menu\s+\$\w+\s+"([^"]+)"\s+(\w+)', "\n".join(lines)))
    out = {}
    for line in lines:
        for entry, helper, tag in re.findall(
                r'add_toolkit_command\s+\$\w+\s+"([^"]+)"\s*\\?\s*"' + re.escape(ns)
                + r'::(\w+)_draw"\s+(\w+)', line):
            out.setdefault(helper, (menus.get(tag, tag).strip(), entry.strip()))
    return out


def numeric(text):
    try:
        float(text)
        return True
    except (TypeError, ValueError):
        return False


def same_value(a, b):
    if a == b:
        return True
    if numeric(a) and numeric(b):
        return float(a) == float(b)
    return False


def family(name, defaults):
    d = dict(defaults)
    if "nocell" in d:
        return "fixed"
    cls = d.get("class", "")
    if "cap_var" in name or "varactor" in name or cls == "varactor":
        return "varactor"
    if "moscap" in name:
        # gf180mcu's nmoscap_3p3 and the like: class mosfet, but a capacitor
        return "moscap"
    if cls == "mosfet" or "fet" in name:
        # nfet_g5v0d16v0 and gf180mcu's nfet_10v0_asym have no "class" key
        return "mos"
    if cls == "resistor":
        return "res"
    if cls == "capacitor":
        return "mim_cap" if "mim" in name else "cap"
    if "photodiode" in name:
        return "photodiode"
    if cls == "diode":
        return "diode"
    return cls or "other"


def param_type(widget, name, default):
    if widget is None:
        return "internal"
    kind = widget["kind"]
    if kind == "checkbox":
        return "bool01"
    if kind == "message":
        return "readonly"
    if kind == "selectlist":
        # The device-type switch "gencell" selects another device: each
        # device is its own PCell here, so it isn't a parameter.
        return "enum" if name == "gencell" else "choice"
    if kind == "selectindex":
        return "enum"
    if "[+/-]" in widget["label"]:
        return "signed"
    if name in COUNT_KEYS:
        return "int"
    if name in NUMLIST_KEYS:
        return "numlist"
    return "float" if numeric(default) else "string"


def gds_info(path):
    from klayout_magic_pcells._kl import db
    ly = db.Layout()
    ly.read(path)
    tops = ly.top_cells()
    top = tops[0]
    layers, texts = set(), []
    box = db.Box()
    g = 0  # gcd of every vertex and text coordinate, in dbu
    for li in ly.layer_indices():
        info = ly.get_info(li)
        ld = "%d/%d" % (info.layer, info.datatype)
        it = top.begin_shapes_rec(li)
        has = False
        while not it.at_end():
            sh = it.shape()
            has = True
            if sh.is_text():
                t = sh.text.transformed(it.trans())
                texts.append([t.string, ld, round(t.x * ly.dbu, 4), round(t.y * ly.dbu, 4)])
                g = math.gcd(g, abs(t.x), abs(t.y))
            else:
                box += sh.bbox().transformed(it.trans())
                pol = sh.polygon
                if pol is not None:
                    pol = pol.transformed(it.trans())
                    pts = list(pol.each_point_hull())
                    for h in range(pol.holes()):
                        pts += list(pol.each_point_hole(h))
                    for pt in pts:
                        g = math.gcd(g, abs(pt.x), abs(pt.y))
            it.next()
        if has:
            layers.add(ld)
    bbox = None if box.empty() else [round(box.left * ly.dbu, 4), round(box.bottom * ly.dbu, 4),
                                     round(box.right * ly.dbu, 4), round(box.top * ly.dbu, 4)]
    return {
        "top_cells": [c.name for c in tops],
        "cells": ly.cells(),
        "cell_names": sorted(c.name for c in ly.each_cell()),
        "dbu": ly.dbu,
        "gds_bbox_um": bbox,
        "layers": sorted(layers, key=lambda s: tuple(int(x) for x in s.split("/"))),
        "texts": sorted(texts),
        # The coarsest grid all coordinates lie on, in nm; audit flags a file
        # whose dbu doesn't divide it (vendor cells with 1 nm coordinates).
        "grid_nm": int(round(g * ly.dbu * 1000)) if g else None,
    }


def run_magic(cfg, out_dir):
    env = dict(os.environ)
    env["KMP_MANIFEST_OUT"] = out_dir
    env["PDK_ROOT"] = cfg.pdk_root
    env["PDK"] = cfg.pdk
    env.pop("KMP_NS", None)
    cmd = [cfg.magic, "-dnull", "-noconsole", "-rcfile", cfg.magicrc,
           os.path.join(TCL_DIR, "kmp_manifest.tcl")]
    p = subprocess.run(cmd, cwd=out_dir, env=env, stdin=subprocess.DEVNULL,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=1800)
    text = p.stdout.decode("utf-8", errors="replace")
    if "KMP_MANIFEST_DONE" not in text:
        sys.stderr.write(text[-4000:])
        raise SystemExit("error: kmp_manifest.tcl did not finish (status %d)" % p.returncode)


def count_draw_definitions(paths, ns):
    text = _read_all(paths)
    if not text:
        return None, []
    names = re.findall(r"^\s*proc\s+(?:::)?" + re.escape(ns) + r"::(\S+)_draw\s", text, re.M)
    dups = sorted({n for n in names if names.count(n) > 1})
    return len(names), dups


def menu_defects(paths, ns, procs):
    """Menu entries whose command names a generator the PDK doesn't define."""
    out = []
    for line in _command_lines(paths):
        for entry, cmd in re.findall(
                r'add_toolkit_command\s+\$\w+\s+"([^"]+)"\s*\\?\s*"([^"]+)"', line):
            m = re.match(r"(?:magic::gencell\s+)?" + re.escape(ns) + r"::(\w+?)(_draw)?$", cmd.strip())
            if not m:
                continue
            target = m.group(1) if m.group(2) else m.group(1)
            if target not in procs:
                out.append({"entry": entry.strip(), "command": cmd.strip(),
                            "problem": "%s::%s%s is not defined" % (ns, target, m.group(2) or "")})
    return out


def build(cfg, work):
    run_magic(cfg, work)
    with open(os.path.join(work, "raw.json"), encoding="utf-8") as f:
        raw = json.load(f)
    with open(os.path.join(work, "versions.json"), encoding="utf-8") as f:
        vi = json.load(f)
    with open(os.path.join(work, "defaults.json"), encoding="utf-8") as f:
        defaults = json.load(f)
    code = backend.sha256_file(os.path.join(work, "procs.txt"))
    tech_file = vi.get("tech_file", "")
    try:
        import klayout.db as kdb
        kl_version = getattr(kdb, "__version__", "")
    except ImportError:
        kl_version = ""

    ns = vi.get("ns") or cfg.namespace
    if ns != cfg.namespace:
        sys.stderr.write("warning: the PDK's Tcl sets PDKNAMESPACE=%s; klayout_magic_pcells.config "
                         "expects %s for %s\n" % (ns, cfg.namespace, cfg.pdk))
    devices = []
    for d in raw["devices"]:
        name = d["name"]
        fam = family(name, d["defaults"])
        widgets = {w["name"]: w for w in d["widgets"] if w["kind"] != "dependency"}
        # The dialog's widgets in the order _dialog creates them, which is
        # the order of its rows; and each add_dependency call with the
        # number of widgets that existed when it ran (add_dependency binds
        # only widgets that exist already).
        order = [[w["kind"], w["name"]] for w in d["widgets"] if w["kind"] != "dependency"]
        deps, made = [], 0
        for w in d["widgets"]:
            if w["kind"] == "dependency":
                deps.append({"callback": w["name"], "params": w["extra"].split(), "after": made})
            else:
                made += 1
        probes = {}
        for pr in d["probes"]:
            probes.setdefault(pr["param"], {})[pr["value"]] = pr
        params = []
        for k, v in d["defaults"]:
            w = widgets.get(k)
            t = param_type(w, k, v)
            p = {"name": k, "default": v, "type": t,
                 "editable": t in ("float", "int", "bool01", "signed", "string", "choice", "numlist")}
            if w is not None:
                p["widget"] = w["kind"]
                p["label"] = w["label"]
            if t == "choice":
                p["choices"] = json.loads(w["extra"])
                if v not in p["choices"]:
                    # Magic's dialog would show the default anyway; keep it sendable.
                    p["choices"].insert(0, v)
            pr = probes.get(k)
            if pr and t in ("float", "signed", "int"):
                z, big, half = pr.get("0"), pr.get("10000"), pr.get("2.5")
                if z and not same_value(z["result"], "0"):
                    p["check_min"] = z["result"]
                if big and not same_value(big["result"], "10000"):
                    p["check_max"] = big["result"]
                if half:
                    p["check_int"] = not same_value(half["result"], "2.5")
                msgs = sorted({x["messages"].strip() for x in pr.values() if x["messages"].strip()})
                if msgs:
                    p["check_messages"] = msgs
                errs = sorted({"%s=%s: %s" % (k, x["value"], x["error"]) for x in pr.values()
                               if x.get("error") and x["error"] != "no _check proc"})
                if errs:
                    p["check_errors"] = errs
            params.append(p)
        gsel = widgets.get("gencell")
        run = d["defaults_run"]
        devices.append({
            "name": name,
            "family": fam,
            "nocell": d["nocell"],
            "form": d["form"],
            "has": {"check": bool(d["has_check"]), "convert": bool(d["has_convert"]),
                    "dialog": bool(d["has_dialog"])},
            "dialog_error": d["dialog_error"],
            "defaults": d["defaults"],
            "params": params,
            "device_type_switch": json.loads(gsel["extra"]) if gsel else None,
            "dialog_widgets": order,
            "dialog_dependencies": deps,
            "check_on_defaults": {
                "changes": [c for c in d["check_on_defaults"]["changes"]],
                "messages": d["check_on_defaults"]["messages"],
                "error": d["check_on_defaults"]["error"],
            },
            "defaults_run": defaults_run(run),
        })

    sources = tcl_sources(cfg.pdk_path, cfg.pdk)
    ndef, dups = count_draw_definitions(sources, ns)
    menu = menu_commands(sources, ns)
    procs = {d["name"] for d in devices} | set(raw["helpers"])
    boxpaint = []
    for b in raw.get("boxpaint", []):
        h = b["name"]
        mn = b["min_box_um"]
        entry = menu.get(h)
        label = entry[1] if entry else h
        par = []
        for k, what in (("w", "width"), ("h", "height")):
            par.append({"name": k, "default": mn if mn is not None else "1.0", "type": "float",
                        "editable": True, "widget": "box",
                        "label": "Box %s (um)" % what})
        boxpaint.append({
            "name": h,
            "family": "box_paint",
            "form": "box",
            "label": label,
            "proc": "%s::%s_draw" % (ns, h),
            "draw_args": b["draw_args"],
            "menu": ("%s / %s" % entry) if entry else None,
            "min_box_um": mn,
            "below_min": b["below_min"],
            "defaults": [[p["name"], p["default"]] for p in par],
            "params": par,
            "defaults_run": defaults_run(b["defaults_run"]),
        })
    bp_names = {b["name"] for b in boxpaint}
    editable = []
    for d in devices + boxpaint:
        for p in d["params"]:
            if p["editable"] and p["name"] not in editable:
                editable.append(p["name"])
    manifest = {
        "format": 1,
        "pdk": cfg.pdk,
        "namespace": ns,
        "built_with": {
            "magic": backend.parse_magic_version(vi.get("magic_banner", "")),
            "magic_banner": vi.get("magic_banner", ""),
            "tech": vi.get("tech", ""),
            "tech_name": vi.get("tech_name", ""),
            "tcl": vi.get("tcl", ""),
            "open_pdks": backend.read_open_pdks(cfg.pdk_path),
            "pdk_commit": backend.read_pdk_commit(cfg.pdk_path),
            "klayout_module": kl_version,
        },
        "defaults_digest": backend.defaults_digest(defaults),
        "code_digest": code,
        "techfile_digest": backend.sha256_file(tech_file) if tech_file and os.path.isfile(tech_file) else "",
        "counts": {
            "draw_proc_definitions_in_source": ndef,
            "duplicate_draw_definitions": dups,
            "draw_procs": len(devices) + len(raw["helpers"]),
            "devices": len(devices),
            "helpers": len(raw["helpers"]),
            "boxpaint": len(boxpaint),
            "editable_parameter_names": len(editable),
            "defaults_run_failures": sum(1 for d in devices if not d["defaults_run"]["ok"]),
            "defaults_run_empty": [d["name"] for d in devices + boxpaint
                                   if d["defaults_run"].get("ok") and d["defaults_run"].get("empty")],
        },
        "types": {
            "float": "number, PCell TypeDouble; sent as Magic's default string when equal to it, else rounded to 12 significant digits and written like a Python float",
            "int": "count (nf, ng, m, nx, ny, turns), PCell TypeInt",
            "bool01": "checkbox, PCell TypeBoolean, sent as 1 or 0",
            "signed": "coverage whose first character Magic reads as an anchor (+, - or none); PCell TypeString, sent verbatim when it is a decimal number with an optional + or - and optional whitespace, refused otherwise",
            "choice": "selectlist other than the device-type switch; PCell TypeString with Magic's choices, sent verbatim when it is one of them, refused otherwise",
            "numlist": "a number, or one number per layer separated by spaces (IHP via nxcuts, nycuts); PCell TypeString, sent verbatim when every element is a decimal number, refused otherwise",
            "string": "other text entry, PCell TypeString, sent verbatim",
            "enum": "the device-type switch (gencell) or a selectindex; not a PCell parameter",
            "readonly": "dialog message; not a PCell parameter",
            "internal": "no dialog widget; not a PCell parameter, Magic's default is used",
        },
        "menu_defects": menu_defects(sources, ns, procs),
        "boxpaint": boxpaint,
        "excluded": [{"name": h, "proc": "%s::%s_draw" % (ns, h), "menu": None,
                      "reason": HELPER_REASON}
                     for h in raw["helpers"] if h not in bp_names],
        "devices": devices,
    }
    return manifest


def defaults_run(run):
    dr = {"ok": run["ok"], "messages": run.get("messages", "")}
    if run["ok"]:
        info = gds_info(run["gds"])
        dr.update({"magic_cell": run["cell"], "top_cells": info["top_cells"],
                   "cells": info["cells"], "cell_names": info["cell_names"],
                   "gds_bbox_um": info["gds_bbox_um"],
                   "grid_nm": info["grid_nm"], "empty": not info["layers"],
                   "layers": info["layers"], "texts": info["texts"],
                   "checked": run["checked"]})
        if "box" in run:
            dr["box"] = run["box"]
    else:
        dr["error"] = run.get("error", "")
    return dr


def dumps(manifest):
    return json.dumps(manifest, indent=1, ensure_ascii=False) + "\n"


def compare(a, b, path=""):
    """List the paths where two JSON values differ."""
    out = []
    if type(a) is not type(b):
        return ["%s: %r != %r" % (path or "/", a, b)]
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                out.append("%s/%s: only in %s" % (path, k, "built" if k in a else "shipped"))
            else:
                out += compare(a[k], b[k], "%s/%s" % (path, k))
    elif isinstance(a, list):
        if len(a) != len(b):
            out.append("%s: %d items != %d" % (path, len(a), len(b)))
        for i, (x, y) in enumerate(zip(a, b)):
            name = x.get("name") if isinstance(x, dict) and "name" in x else i
            out += compare(x, y, "%s[%s]" % (path, name))
    elif a != b:
        out.append("%s: %r != %r" % (path, a, b))
    return out


def build_one(cfg, out, check, keep):
    probs = [p for p in cfg.problems() if "manifest" not in p]
    if probs:
        for p in probs:
            sys.stderr.write("error: %s\n" % p)
        return 2
    work = keep or tempfile.mkdtemp(prefix="kmp-manifest-")
    os.makedirs(work, exist_ok=True)
    manifest = build(cfg, work)
    if not keep:
        import shutil
        shutil.rmtree(work, ignore_errors=True)
    if check:
        try:
            with open(out, encoding="utf-8") as f:
                shipped = json.load(f)
        except (OSError, ValueError) as e:
            sys.stderr.write("error: cannot read %s: %s\n" % (out, e))
            return 2
        diffs = compare(manifest, shipped)
        if diffs:
            print("MANIFEST DIFFERS from %s (%d differences):" % (out, len(diffs)))
            for line in diffs[:200]:
                print("  " + line)
            return 1
        print("MANIFEST OK: %s matches the installed Magic and %s (%d devices, %d box-paint "
              "generators)" % (out, cfg.pdk, len(manifest["devices"]), len(manifest["boxpaint"])))
        return 0
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(dumps(manifest))
    c = manifest["counts"]
    print("wrote %s: %d devices, %d box-paint generators, %d helpers excluded, %d editable "
          "parameter names, %d failures" % (out, c["devices"], c["boxpaint"],
                                            c["helpers"] - c["boxpaint"],
                                            c["editable_parameter_names"], c["defaults_run_failures"]))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pdk", help="the PDK (default: KMP_PDK, else sky130A)")
    ap.add_argument("--all", action="store_true", help="every supported PDK")
    ap.add_argument("--out", help="default: the shipped manifest of the PDK")
    ap.add_argument("--check", action="store_true",
                    help="build into a temporary file and compare with --out")
    ap.add_argument("--keep", help="keep Magic's raw output in this directory")
    args = ap.parse_args(argv)
    base = Config.load(pdk=args.pdk)
    pdks = list(SUPPORTED_PDKS) if args.all else [base.pdk]
    if args.all and args.out:
        ap.error("--out needs a single --pdk")
    rc = 0
    for pdk in pdks:
        cfg = base.for_pdk(pdk)
        out = args.out or shipped_manifest(pdk)
        keep = os.path.join(args.keep, pdk) if (args.keep and args.all) else args.keep
        rc = max(rc, build_one(cfg, out, args.check, keep))
    return rc


if __name__ == "__main__":
    sys.exit(main())
