"""Backend tests: need Magic and the PDKs (run them in the pinned image).

The PDK under test is the one KMP_PDK names (sky130A by default); the
harness runs this file once per PDK. Most tests run on every PDK, with the
devices of the table DEV below. Tests that depend on one PDK's own files
(sky130A's vendor GDS byte offsets, the IHP layout scripts) say so in their
skip reason. Skipped when Magic or the rcfile can't be found.
"""

import glob
import hashlib
import json
import os
import re
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "python"))

from klayout_magic_pcells.backend import BackendError, MagicServer  # noqa: E402
from klayout_magic_pcells.config import LIBRARY_NAMES, Config  # noqa: E402
from klayout_magic_pcells.manifest import Manifest  # noqa: E402

try:
    import klayout.db as db
except ImportError:
    db = None


def _cfg(**env):
    e = dict(os.environ)
    e.setdefault("KMP_CACHE_DIR", tempfile.mkdtemp(prefix="kmp-test-cache-"))
    e.update(env)
    return Config.load(env=e)


try:
    CFG = _cfg()
    HAVE_MAGIC = not CFG.problems()
except Exception:
    HAVE_MAGIC = False

needs_magic = unittest.skipUnless(HAVE_MAGIC and db is not None,
                                  "Magic, the PDK or the klayout module is missing")
PDK = CFG.pdk if HAVE_MAGIC else "sky130A"
LIB = LIBRARY_NAMES.get(PDK, "sky130_magic")
sky130_only = unittest.skipUnless(PDK == "sky130A", "edits sky130A's vendor GDS at known byte offsets")

# The devices the tests use, per PDK: a MOSFET, the MOSFETs and varactors
# whose mos_check loops forever above 28 um, the values _check clamps a
# 0.1 x 0.1 MOSFET to (l, w), a fixed device, a resistor and a second
# device, a device and size for which Magic writes an empty cell, and
# parameters whose values the PCell refuses unless they are numbers or
# Magic's choices. "vendor" is the libs.ref library that holds the fixed
# devices' GDS; the IHP PDKs draw theirs from scripts in libs.tech/magic.
DEV = {
    "sky130A": dict(
        mos="sky130_fd_pr__nfet_01v8", loop=("sky130_fd_pr__nfet_01v8", "sky130_fd_pr__cap_var_lvt"),
        small=("0.15", "0.42"), fixed="sky130_fd_pr__npn_05v5_W1p00L1p00",
        res="sky130_fd_pr__res_high_po_0p69", other="sky130_fd_pr__cap_mim_m3_1",
        empty=("sky130_fd_pr__res_generic_l1", "l"),
        refused=(("sky130_fd_pr__nfet_01v8", "viagb"), ("sky130_fd_pr__res_high_po_0p35", "viagb"),
                 ("sky130_fd_pr__cap_mim_m3_1", "ccov"), ("sky130_fd_pr__diode_pw2nd_05v5", "viagt")),
        vendor="sky130_fd_pr", script=None),
    "gf180mcuD": dict(
        mos="nfet_03v3", loop=(), small=("0.28", "0.22"), fixed="npn_00p54x02p00",
        res="ppolyf_u", other="cap_mim_2p0fF", empty=("rm1", "l"),
        refused=(("ppolyf_u", "guard_type"),), vendor="gf180mcu_fd_pr", script=None),
    "ihp-sg13g2": dict(
        mos="sg13_lv_nmos", loop=("sg13_lv_nmos",), small=("0.13", "0.15"), fixed="diodevdd_2kv",
        res="rsil", other="cap_cmim", empty=("rm1", "l"),
        refused=(("dantenna", "viagb"), ("cap_cmim", "ccov"), ("via", "nxcuts"), ("via", "metalbot")),
        vendor=None, script="diodevdd_2kv.tcl"),
    "ihp-sg13cmos5l": dict(
        mos="sg13_lv_nmos", loop=("sg13_lv_nmos",), small=("0.13", "0.15"), fixed="diodevdd_2kv",
        res="rsil", other="cap_cmomf", empty=("rm1", "l"),
        refused=(("dantenna", "viagb"), ("via", "nxcuts")), vendor=None, script="diodevdd_2kv.tcl"),
}
D = DEV.get(PDK, DEV["sky130A"])
FINGERS = "ng" if PDK.startswith("ihp") else "nf"
PY = os.path.join(REPO, "python")


def script(body):
    """A python -c script with the package on sys.path and klayout.db,
    klayout_magic_pcells (as kmp), PDK and LIB defined."""
    return ("import os, sys\nsys.path.insert(0, %r)\nimport klayout.db as db\n"
            "import klayout_magic_pcells as kmp\nPDK, LIB = %r, %r\n" % (PY, PDK, LIB)
            + textwrap.dedent(body))


def run_py(body, env, args=(), timeout=180):
    p = subprocess.run([sys.executable, "-c", script(body)] + list(args), stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, env=env, timeout=timeout)
    return p.returncode, p.stdout.decode(errors="replace")


def cli(env, *args, timeout=180, cwd=None):
    p = subprocess.run([sys.executable, "-m", "klayout_magic_pcells"] + list(args), stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, env=dict(env, PYTHONPATH=PY), timeout=timeout, cwd=cwd)
    return p.returncode, p.stdout.decode(errors="replace")


def alive(pid):
    try:
        with open("/proc/%d/status" % pid) as f:
            return "State:\tZ" not in f.read()
    except OSError:
        return False


def flat_signature(path, shift=(0, 0)):
    ly = db.Layout()
    ly.read(path)
    top = ly.top_cells()
    assert len(top) == 1, [c.name for c in top]
    out = {}
    t = db.ICplxTrans(db.Vector(*shift))
    for li in ly.layer_indices():
        info = ly.get_info(li)
        r = db.Region(top[0].begin_shapes_rec(li)).transformed(t)
        r.merge()
        tx = sorted((x.string, x.x, x.y) for x in db.Texts(top[0].begin_shapes_rec(li)).transformed(t).each())
        if not r.is_empty() or tx:
            out["%d/%d" % (info.layer, info.datatype)] = (r.area(), r.count(), str(r.bbox()), tx)
    return out


def farm(root, edit_tcl=None, drop_vendor_gds=False, edit_vendor_gds=None, remove=()):
    """A PDK_ROOT whose PDK is the installed one through symlinks.

    ``edit_tcl(name, text)`` returns the new text of each libs.tech/magic/*.tcl
    file (or the text unchanged); ``remove`` names libs.tech/magic files
    left out. With ``drop_vendor_gds``, libs.ref/<vendor>/gds is left out
    (the fixed devices' GDS); ``edit_vendor_gds(bytes)`` rewrites sky130A's
    sky130_fd_pr.gds."""
    src = os.path.join(CFG.pdk_root, PDK)
    dst = os.path.join(root, PDK)
    os.makedirs(os.path.join(dst, "libs.tech", "magic"))
    for name in os.listdir(src):
        if name == "libs.ref" and (drop_vendor_gds or edit_vendor_gds) and D["vendor"]:
            for lib in os.listdir(os.path.join(src, name)):
                d = os.path.join(dst, name, lib)
                os.makedirs(os.path.dirname(d), exist_ok=True)
                if lib != D["vendor"]:
                    os.symlink(os.path.join(src, name, lib), d)
                    continue
                os.makedirs(d)
                for sub in os.listdir(os.path.join(src, name, lib)):
                    if sub != "gds":
                        os.symlink(os.path.join(src, name, lib, sub), os.path.join(d, sub))
                    elif edit_vendor_gds is not None:
                        g = os.path.join(src, name, lib, "gds")
                        os.makedirs(os.path.join(d, "gds"))
                        for fn in os.listdir(g):
                            if fn == "sky130_fd_pr.gds":
                                with open(os.path.join(g, fn), "rb") as f:
                                    data = edit_vendor_gds(f.read())
                                with open(os.path.join(d, "gds", fn), "wb") as f:
                                    f.write(data)
                            else:
                                os.symlink(os.path.join(g, fn), os.path.join(d, "gds", fn))
        elif name != "libs.tech":
            os.symlink(os.path.join(src, name), os.path.join(dst, name))
    for name in os.listdir(os.path.join(src, "libs.tech")):
        if name != "magic":
            os.symlink(os.path.join(src, "libs.tech", name), os.path.join(dst, "libs.tech", name))
    for name in os.listdir(os.path.join(src, "libs.tech", "magic")):
        if name in remove:
            continue
        p = os.path.join(src, "libs.tech", "magic", name)
        q = os.path.join(dst, "libs.tech", "magic", name)
        if edit_tcl is not None and name.endswith(".tcl"):
            with open(p) as f:
                text = f.read()
            new = edit_tcl(name, text)
            if new != text:
                with open(q, "w") as f:
                    f.write(new)
                continue
        os.symlink(p, q)
    return root


# Register the PDK's library, then open the file named in argv.
REOPEN = """
assert kmp.register(PDK) is not None, kmp.state_for(PDK).last_error
ly = db.Layout()
ly.read(sys.argv[1])
print("OK")
"""


def insert_after_proc(proc, line):
    """An edit_tcl for farm(): ``line`` as the first statement of ``proc``
    (for example "sky130::via1_draw"), wherever the PDK defines it."""
    pat = re.compile(r"^proc %s \{[^\n]*\{\s*$" % re.escape(proc), re.M)
    done = []

    def edit(name, text):
        m = pat.search(text)
        if not m:
            return text
        done.append(name)
        return text[:m.end()] + "\n    " + line + text[m.end():]
    edit.done = done
    return edit


@needs_magic
class Server(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="kmp-backend-")
        cls.cfg = _cfg(KMP_CACHE_DIR=os.path.join(cls.tmp, "cache"))
        cls.man = Manifest.load(cls.cfg.manifest)
        cls.s = MagicServer(cls.cfg)
        cls.versions = cls.s.start()

    @classmethod
    def tearDownClass(cls):
        cls.s.close()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def out(self, name):
        return os.path.join(self.tmp, name)

    def test_versions(self):
        v = self.versions
        self.assertRegex(v.magic, r"^\d+\.\d+\.\d+$")
        self.assertTrue(v.tech)
        self.assertEqual(len(v.code), 64)
        self.assertEqual(len(v.defaults), sum(1 for d in self.man.devices if d.kind == "device"))
        self.assertEqual(sorted(v.boxpaint), sorted(d.name for d in self.man.devices if d.kind == "box"))
        self.assertEqual(v.namespace, self.man.namespace)
        self.assertEqual(len(v.techdir), 64)
        self.assertTrue(v.pdk_commit)
        self.assertEqual(v.defaults_digest, self.man.defaults_digest,
                         "the running Magic's defaults differ from the shipped manifest")

    def test_every_device_twice_in_one_session(self):
        # M3: the same parameters twice must work (the server deletes the cell).
        for spec in self.man.devices:
            sigs = []
            for k in range(2):
                p = self.out("%s_%d.gds" % (spec.short_name, k))
                req = spec.build_request(spec.defaults_values()) if spec.kind == "box" else {}
                r = self.s.generate(spec.name, req, spec.form, p)
                self.assertTrue(r.cell or spec.kind == "box", spec.name)
                self.assertFalse(r.restart, (spec.name, r.kv))
                self.assertGreater(os.path.getsize(p), 100, spec.name)
                sigs.append(flat_signature(p))
                os.remove(p)
            self.assertEqual(sigs[0], sigs[1], spec.name)
            if not spec.batch.get("empty"):
                self.assertTrue(sigs[0], spec.name + " wrote no shapes")

    def test_brace_in_a_value(self):
        # An unbalanced brace is data, not Tcl source: Magic's _check says
        # the value is not numeric and clamps it, and the session goes on.
        r = self.s.generate(D["mos"], {"w": "1{.5"}, "cell", self.out("b.gds"))
        self.assertIn("not numeric", r.log)
        self.assertEqual(r.checked["w"], D["small"][1])
        r2 = self.s.generate(D["mos"], {"w": "1.5"}, "cell", self.out("b2.gds"))
        self.assertEqual(r2.checked["w"], "1.5")

    def test_a_value_that_tcl_would_substitute_is_refused(self):
        # Defence in depth behind ParamSpec.check: the server itself refuses
        # [, ], $ and backslash in any value, whoever sends it.
        marker = self.out("server_marker")
        for op in ("generate", "check"):
            with self.assertRaises(BackendError) as cm:
                if op == "generate":
                    self.s.generate(D["mos"], {"w": "[exec touch %s]" % marker}, "cell", self.out("inj.gds"))
                else:
                    self.s.check(D["mos"], {"w": "$::env(HOME)"})
            self.assertIn("refused", str(cm.exception))
        with self.assertRaises(BackendError):
            self.s.generate("via1", {"w": "[exec touch %s]" % marker, "h": "1"}, "box", self.out("i.gds"))
        self.assertFalse(os.path.exists(marker))
        self.assertTrue(self.s.ping())

    def test_endless_check_loop_is_stopped(self):
        # mos_check (sky130A, IHP) never returns when w and l are both above
        # 28 um, whatever nf and m are. The server stops it without a
        # restart. gf180mcuD's loop ends, and the device draws.
        pid = self.s.pid
        for dev in D["loop"]:
            for params in ({"w": "35", "l": "35", FINGERS: "1"}, {"w": "29", "l": "29", FINGERS: "4"}):
                t = time.time()
                with self.assertRaises(BackendError) as cm:
                    self.s.generate(dev, params, "cell", self.out("loop.gds"))
                self.assertIn("endless loop", str(cm.exception))
                with self.assertRaises(BackendError) as cm:
                    self.s.check(dev, params)
                self.assertIn("endless loop", str(cm.exception))
                self.assertLess(time.time() - t, 10, (dev, params))
        self.assertEqual(self.s.pid, pid)
        # Just below the condition Magic terminates and draws.
        r = self.s.generate(D["mos"], {"w": "28", "l": "35"}, "cell", self.out("w28.gds"))
        self.assertTrue(r.cell)
        self.assertNotIn("endless", r.log)
        if not D["loop"]:
            r = self.s.generate(D["mos"], {"w": "35", "l": "35"}, "cell", self.out("w35.gds"))
            self.assertTrue(r.cell)

    def test_unknown_device_is_an_error(self):
        with self.assertRaises(BackendError) as cm:
            self.s.generate("nope_device", {}, "cell", self.out("n.gds"))
        self.assertIn("unknown device", str(cm.exception))
        self.assertTrue(self.s.ping())

    def test_check_messages_arrive_in_the_log(self):
        r = self.s.check(D["mos"], {"l": "0.1", "w": "0.1"})
        self.assertEqual((r.checked["l"], r.checked["w"]), D["small"])
        self.assertIn("Mos length must be >= %s um" % D["small"][0], r.log)
        r = self.s.generate(D["mos"], {"l": "0.1"}, "cell", self.out("c.gds"))
        self.assertIn("Mos length must be >= %s um" % D["small"][0], r.log)

    def test_fixed_device_array(self):
        r = self.s.generate(D["fixed"], {"nx": "2", "ny": "3"}, "wrapper", self.out("a.gds"))
        self.assertEqual((r.checked["nx"], r.checked["ny"]), ("2", "3"))
        ly = db.Layout()
        ly.read(self.out("a.gds"))
        insts = list(ly.top_cell().each_inst())
        self.assertEqual(len(insts), 1)
        self.assertEqual((insts[0].na, insts[0].nb), (3, 2))

    def test_negative_and_non_finite_box_sizes(self):
        # What Magic's box command does with them: a negative size puts the
        # box left of or below the origin and the generator paints it there;
        # -0.0, inf and nan come out below the minimum (inf and nan as
        # -2147483648 internal units), and nothing is painted.
        for spec in [d for d in self.man.devices if d.kind == "box"]:
            m = float(spec.raw["min_box_um"])
            big = max(2 * m, 1.0)
            pos = self.out("pos.gds")
            self.s.generate(spec.name, {"w": repr(big), "h": repr(big)}, "box", pos)
            want = flat_signature(pos)
            self.assertTrue(want, spec.name)
            for w, h, dx, dy in ((-big, big, 1, 0), (big, -big, 0, 1), (-big, -big, 1, 1)):
                p = self.out("neg.gds")
                r = self.s.generate(spec.name, {"w": repr(w), "h": repr(h)}, "box", p)
                self.assertEqual((float(r.checked["w"]), float(r.checked["h"])), (big, big), spec.name)
                shift = (int(round(dx * big * 1000)), int(round(dy * big * 1000)))
                self.assertEqual(flat_signature(p, shift), want, (spec.name, w, h))
            for w in ("-0.0", "inf", "-inf", "nan"):
                p = self.out("zero.gds")
                r = self.s.generate(spec.name, {"w": w, "h": repr(big)}, "box", p)
                self.assertEqual(flat_signature(p), {}, (spec.name, w))
                self.assertRegex(r.log, r"(?i)width", (spec.name, w))
            with self.assertRaises(BackendError) as cm:
                self.s.generate(spec.name, {"w": "+1", "h": "1"}, "box", self.out("x.gds"))
            self.assertIn("refused", str(cm.exception))


# Requests that leave Magic's session changed, per PDK, and the requests that
# must still draw what a fresh Magic draws after them.
DISTURB = {
    "sky130A": [("nwell", "box", {"w": "3.0", "h": "2.0"}),         # runs tech revert
                ("deep_nwell", "box", {"w": "5.0", "h": "4.0"})],   # leaves ::boxstack
    "gf180mcuD": [("subcon_3p3", "box", {"w": "1.0", "h": "1.0"})],
    "ihp-sg13g2": [("dantenna", "cell", {"w": "0"}),               # leaves layers locked
                   ("subconn", "box", {"w": "1.0", "h": "1.0"})],   # sets units microns
    "ihp-sg13cmos5l": [("dantenna", "cell", {"w": "0"}),
                       ("subconn", "box", {"w": "1.0", "h": "1.0"})],
}
AFTER = {
    "sky130A": [("via1", "box", {"w": "1.0", "h": "1.0"}), ("sky130_fd_pr__nfet_01v8", "cell", {})],
    "gf180mcuD": [("via1", "box", {"w": "1.0", "h": "1.0"}), ("nfet_03v3", "cell", {})],
    "ihp-sg13g2": [("via", "cell", {}), ("inductor2", "cell", {}), ("inductor3", "cell", {}),
                   ("via1", "box", {"w": "1.0", "h": "1.0"})],
    "ihp-sg13cmos5l": [("via", "cell", {}), ("inductor2", "cell", {}),
                       ("via1", "box", {"w": "1.0", "h": "1.0"})],
}


@needs_magic
class AnyPdk(unittest.TestCase):
    """Run for the PDK that KMP_PDK names."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="kmp-pdk-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def sigs(self, s, reqs, tag):
        out = []
        for i, (dev, form, params) in enumerate(reqs):
            p = os.path.join(self.tmp, "%s_%d.gds" % (tag, i))
            try:
                r = s.generate(dev, params, form, p)
                out.append((dev, flat_signature(p), r.kv.get("restored", "")))
            except BackendError as e:
                out.append((dev, "error: %s" % e, ""))
        return out

    def test_session_state_is_put_back_after_each_request(self):
        cfg = _cfg(KMP_CACHE_DIR=self.tmp)
        a, b = MagicServer(cfg), MagicServer(cfg)
        try:
            a.start()
            b.start()
            fresh = self.sigs(a, AFTER[PDK], "fresh")
            dist = self.sigs(b, DISTURB[PDK], "dist")
            after = self.sigs(b, AFTER[PDK], "after")
        finally:
            a.close()
            b.close()
        if PDK != "gf180mcuD":
            self.assertTrue(any(d[2] for d in dist), "no request changed the session: %s" % dist)
        for f, g in zip(fresh, after):
            self.assertEqual(f[1], g[1], f[0])

    def test_box_paint_check_reports_the_box_magic_uses(self):
        cfg = _cfg(KMP_CACHE_DIR=self.tmp)
        man = Manifest.load(cfg.manifest)
        spec = man["via1"]
        s = MagicServer(cfg)
        try:
            s.start()
            r = s.check("via1", {"w": "1.003", "h": "1.0"}, "box")
            self.assertEqual((r.checked["w"], r.checked["h"]), ("1.005", "1.0"))
            self.assertEqual(r.log.strip(), "")
            m = float(spec.raw["min_box_um"])
            r = s.check("via1", {"w": "%.3f" % (m - 0.005), "h": "1.0"}, "box")
            self.assertIn("must be at least", r.log)
            with self.assertRaises(BackendError):
                s.check("via1", {"w": "1 [exec x]", "h": "1"}, "box")
            with self.assertRaises(BackendError):
                s.generate("nope_draw", {"w": "1", "h": "1"}, "box", os.path.join(self.tmp, "x.gds"))
        finally:
            s.close()

    @unittest.skipUnless(PDK in ("ihp-sg13g2", "gf180mcuD"), "needs a device without _check or "
                         "with a _check that raises")
    def test_check_without_a_check_proc_or_with_one_that_raises(self):
        s = MagicServer(_cfg(KMP_CACHE_DIR=self.tmp))
        try:
            s.start()
            if PDK == "ihp-sg13g2":
                r = s.check("rm6", {"w": "1.0"})
                self.assertEqual(r.kv.get("check"), "none")
            else:
                r = s.check("npolyf_s", {"w": "0"})
                self.assertEqual(r.kv.get("check"), "failed")
                self.assertIn("integer value too large", r.kv.get("check_error", ""))
            self.assertTrue(r.checked)
        finally:
            s.close()


@needs_magic
class Recovery(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="kmp-recover-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_killed_magic_is_restarted_and_the_request_retried(self):
        s = MagicServer(_cfg(KMP_CACHE_DIR=self.tmp))
        try:
            s.start()
            pid = s.pid
            os.kill(pid, signal.SIGKILL)
            time.sleep(0.2)
            r = s.generate(D["mos"], {}, "cell", os.path.join(self.tmp, "k.gds"))
            self.assertTrue(r.cell)
            self.assertNotEqual(s.pid, pid)
            self.assertGreaterEqual(s.stats["spawns"], 2)
        finally:
            s.close()

    def test_timeout_restarts_magic(self):
        s = MagicServer(_cfg(KMP_CACHE_DIR=self.tmp, KMP_TIMEOUT="3"))
        try:
            s.start()
            pid = s.pid
            # An incomplete Tcl command makes Magic wait for more input (M2);
            # the next request then gets no reply until the timeout.
            s._proc.stdin.write(b"puts {unbalanced\n")
            s._proc.stdin.flush()
            t = time.time()
            r = s.generate(D["mos"], {}, "cell", os.path.join(self.tmp, "t.gds"))
            self.assertTrue(r.cell)
            self.assertGreater(time.time() - t, 2.5)
            self.assertNotEqual(s.pid, pid)
            self.assertFalse(alive(pid))
        finally:
            s.close()

    def test_magic_missing(self):
        s = MagicServer(_cfg(KMP_CACHE_DIR=self.tmp, KMP_MAGIC="/no/such/magic"))
        with self.assertRaises(BackendError):
            s.start()

    def test_start_errors_say_why(self):
        # Exit status and Magic's own stderr in the message, the real wait in
        # a timeout, and no traceback from the pipe reader threads.
        boom = os.path.join(self.tmp, "boom.sh")
        with open(boom, "w") as f:
            f.write("#!/bin/sh\necho 'boom: no tech file' >&2\nexit 3\n")
        hang = os.path.join(self.tmp, "hang.sh")
        with open(hang, "w") as f:
            f.write("#!/bin/sh\nexec cat\n")
        os.chmod(boom, 0o755)
        os.chmod(hang, 0o755)
        body = """
            import time
            from klayout_magic_pcells.backend import MagicServer
            from klayout_magic_pcells.config import Config
            env = dict(os.environ)
            for kv in sys.argv[1:]:
                k, v = kv.split("=", 1)
                env[k] = v
            s = MagicServer(Config.load(env=env))
            t = time.time()
            try:
                s.start()
                print("STARTED")
            except Exception as e:
                print("ERR %.0f %s" % (time.time() - t, e))
            finally:
                s.close()
        """
        rc = os.path.join(os.path.dirname(CFG.magicrc))
        if PDK.startswith("ihp"):
            # The IHP rcfiles load the tech file from their own directory.
            moved = os.path.join(self.tmp, "moved")
            os.makedirs(moved)
            shutil.copy(CFG.magicrc, moved)
            missing = (["KMP_MAGICRC=" + os.path.join(moved, os.path.basename(CFG.magicrc))],
                       "Could not find file '%s/%s.tech'" % (moved, PDK))
        else:
            missing = (["PDK_ROOT=/nonexistent", "KMP_MAGICRC=" + CFG.magicrc],
                       "Could not find file '/nonexistent/%s/libs.tech/magic/%s.tech'" % (PDK, PDK))
        cases = [
            (["KMP_MAGIC=/bin/false"], "Magic exited (status 1)"),
            (["KMP_MAGIC=" + boom], "Magic exited (status 3); Magic said: boom: no tech file"),
            (["KMP_MAGIC=" + hang, "KMP_TIMEOUT=1"], "timed out after 10 s waiting for Magic to load kmp_server.tcl"),
            missing,
        ]
        self.assertTrue(os.path.isdir(rc))
        for args, expect in cases:
            code, text = run_py(body, dict(os.environ), ["KMP_CACHE_DIR=" + self.tmp] + args, timeout=60)
            self.assertIn(expect, text, args)
            self.assertNotIn("Traceback", text, args)
            self.assertNotIn("Exception in thread", text, args)
            if "KMP_TIMEOUT=1" in args:
                self.assertIn("is %s Magic?" % hang, text)
                self.assertRegex(text, r"ERR (9|10|11) ")
        # Every server deleted its private run directory.
        self.assertEqual(os.listdir(os.path.join(self.tmp, "run")), [])

    def test_no_magic_left_after_the_client_exits(self):
        body = """
            from klayout_magic_pcells.backend import make_server
            from klayout_magic_pcells.config import Config
            s = make_server(Config.load())
            s.start()
            print(s.pid, flush=True)
            if sys.argv[1] == "kill":
                os.kill(os.getpid(), 9)
            # normal exit: the atexit handler closes Magic
        """
        for how in ("exit", "kill"):
            code, text = run_py(body, dict(os.environ, KMP_CACHE_DIR=self.tmp), [how], timeout=60)
            pid = int(text.split()[0])
            for _ in range(50):
                if not alive(pid):
                    break
                time.sleep(0.1)
            self.assertFalse(alive(pid), "Magic %d still running after the client's %s" % (pid, how))


@needs_magic
class GeneratorAndLibrary(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="kmp-gen-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def env(self, **kw):
        e = dict(os.environ, KMP_CACHE_DIR=os.path.join(self.tmp, "cache"), KMP_PDKS=PDK, KMP_PDK=PDK)
        e.update(kw)
        return e

    def test_memo_disk_magic(self):
        from klayout_magic_pcells.backend import Generator
        from klayout_magic_pcells.cache import GdsCache, versions_fields
        cfg = _cfg(KMP_CACHE_DIR=self.tmp)
        man = Manifest.load(cfg.manifest)
        spec = man[D["res"]]
        s = MagicServer(cfg)
        try:
            v = s.start()
            cache = GdsCache(self.tmp, versions_fields(v, cfg.pdk))
            g = Generator(s, cache, v)
            req = spec.build_request(dict(spec.defaults_values(), l=5.0, nx=2))
            a = g.get(spec, req)
            b = g.get(spec, req)
            self.assertEqual((a.source, b.source), ("magic", "memo"))
            g2 = Generator(s, GdsCache(self.tmp, versions_fields(v, cfg.pdk)), v)
            c = g2.get(spec, req)
            self.assertEqual(c.source, "disk")
            self.assertEqual(c.checked, a.checked)
            self.assertEqual(c.magic_cell, a.magic_cell)
            self.assertTrue(a.magic_cell.startswith(spec.name + "_"), a.magic_cell)
            if PDK == "sky130A":
                self.assertEqual(c.magic_cell, "sky130_fd_pr__res_high_po_0p69_G99TND")
            self.assertEqual(s.stats["generate"], 1)
        finally:
            s.close()

    def test_damaged_cache_entries_are_regenerated(self):
        # A cache GDS that is garbage, truncated, or another device's file is
        # regenerated by Magic in the next session, in produce as well.
        body = """
            import glob, shutil
            assert kmp.register(PDK) is not None, kmp.state_for(PDK).last_error
            st = kmp.state_for(PDK)
            res, other = sys.argv[2], sys.argv[3]
            def gstats():
                return {k: st.generator.stats[k] for k in ("memo", "disk", "magic", "evicted")}
            def place(dev):
                ly = db.Layout()
                c = ly.create_cell(dev, LIB, {})
                ph = ly.find_layer(255, 0)
                return "%s %s %s" % (dev, c.dbbox(), ph is not None and not c.shapes(ph).is_empty())
            print("PLACE", place(res), gstats())
            print("PLACE", place(other), gstats())
            path = glob.glob(os.path.join(os.environ["KMP_CACHE_DIR"], "v1/*/%s/*.gds" % res))[0]
            if sys.argv[1] == "live":
                # damage the file under the memo of this session
                open(path, "wb").write(b"not a GDS file")
                print("PLACE", place(res), gstats())
            elif sys.argv[1] != "none":
                oth = glob.glob(os.path.join(os.environ["KMP_CACHE_DIR"], "v1/*/%s/*.gds" % other))[0]
                if sys.argv[1] == "swap":
                    shutil.copy(oth, path)
                elif sys.argv[1] == "truncate":
                    data = open(path, "rb").read()
                    open(path, "wb").write(data[:len(data) // 2])
                else:
                    open(path, "wb").write(b"garbage" * 40)
        """
        good = None
        for damage in ("garbage", "truncate", "swap", "live"):
            env = self.env(KMP_CACHE_DIR=os.path.join(self.tmp, damage))
            outs = []
            for step in (damage, "none"):
                rc, text = run_py(body, env, [step, D["res"], D["other"]])
                outs.append(text)
                self.assertEqual(rc, 0, text)
            first, second = outs
            place = [ln for ln in first.splitlines() if ln.startswith("PLACE ")][0]
            g = place[len("PLACE "):place.index(" {")]
            self.assertTrue(g.endswith(" False"), g)
            if good is None:
                good = g
                if PDK == "sky130A":
                    self.assertEqual(good, "sky130_fd_pr__res_high_po_0p69 (-1.12,-3.355;1.12,3.355) False")
            self.assertEqual(g, good)
            # Coerce makes each variant (Magic's Create shows the values) and
            # produce takes it from the memo.
            if damage == "live":
                self.assertIn("can't be read", first)
                self.assertIn("PLACE " + good + " {'memo': 4, 'disk': 0, 'magic': 3, 'evicted': 1}", first)
            # The next session sees the damage, deletes the entry and asks Magic.
            self.assertIn("PLACE " + good + " {'memo': 1, 'disk': 0, 'magic': 1, 'evicted': 0}"
                          if damage != "live" else
                          "PLACE " + good + " {'memo': 1, 'disk': 1, 'magic': 0, 'evicted': 0}", second, damage)

    def test_the_cache_removed_under_a_running_session(self):
        # gf180mcuD tester's case: "cache clear" or "cache prune" from
        # another shell, or the cache directory removed by hand, while a
        # session is open. Every later variant drew the error marker
        # ("gds write produced no file"); now the session makes the
        # directories again, and a variant it remembered but whose file is
        # gone is generated again.
        body = """
            import shutil, subprocess
            assert kmp.register(PDK) is not None, kmp.state_for(PDK).last_error
            st = kmp.state_for(PDK)
            dev = sys.argv[1]
            spec = st.manifest[dev]
            name = spec.params[0].name
            base = float(spec.params[0].default)
            def place(i):
                ly = db.Layout()
                c = ly.create_cell(dev, LIB, {name: base + 0.01 * i})
                ph = ly.find_layer(255, 0)
                bad = ph is not None and not c.shapes(ph).is_empty()
                return "MARKER" if bad else ("EMPTY" if c.dbbox().empty() else "ok")
            cache = os.environ["KMP_CACHE_DIR"]
            print("STEP before", place(0), place(1))
            for i, how in enumerate(("clear", "prune", "rmtree")):
                if how == "rmtree":
                    shutil.rmtree(cache)
                else:
                    p = subprocess.run([sys.executable, "-m", "klayout_magic_pcells", "cache", how],
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                    assert p.returncode == 0, p.stdout
                print("STEP", how, place(10 + i), place(0), st.generator.stats["magic"])
        """
        rc, text = run_py(body, self.env(PYTHONPATH=PY), [D["mos"]])
        self.assertEqual(rc, 0, text)
        steps = [ln for ln in text.splitlines() if ln.startswith("STEP ")]
        self.assertEqual(len(steps), 4, text)
        for ln in steps:
            self.assertNotIn("MARKER", ln, text)
            self.assertNotIn("EMPTY", ln, text)
        # clear and rmtree deleted variant 0's file, so it came from Magic again.
        self.assertNotIn("can't be read", text)

    def test_prune_leaves_the_other_pdks_alone(self):
        # The testers' case: entries of two PDKs, then "cache prune" with
        # KMP_PDKS naming one; the other PDK's current entries stayed only
        # when this prune worked on all of them.
        other = "gf180mcuD" if PDK == "sky130A" else "sky130A"
        if not os.path.isfile(os.path.join(CFG.pdk_root, other, "libs.tech", "magic", other + ".magicrc")):
            self.skipTest("%s is not installed" % other)
        body = """
            for p in sys.argv[1:]:
                lib = kmp.register(p)
                assert lib is not None, kmp.state_for(p).last_error
                ly = db.Layout()
                c = ly.create_cell("via1", lib.name(), {})
                print("PLACED", p, c.dbbox())
        """
        both = self.env(KMP_PDKS="%s,%s" % (PDK, other))
        rc, text = run_py(body, both, [PDK, other])
        self.assertEqual(rc, 0, text)
        rc, stats = cli(both, "cache", "stats")
        self.assertEqual(rc, 0, stats)
        cur = json.loads(stats[stats.index("{"):])["current"]
        self.assertEqual(sorted(cur), sorted([PDK, other]))
        rc, text = cli(self.env(), "cache", "prune")
        self.assertEqual(rc, 0, text)
        self.assertNotIn("removed", text)
        self.assertIn("kept %s" % os.path.join(self.tmp, "cache", "v1", cur[other]), text)
        left = sorted(os.listdir(os.path.join(self.tmp, "cache", "v1")))
        self.assertEqual(left, sorted(cur.values()))

    def test_register_in_plain_python(self):
        body = """
            lib = kmp.register(PDK)
            assert lib is not None, kmp.state_for(PDK).last_error
            assert kmp.register(PDK) is lib
            st = kmp.state_for(PDK)
            assert st.server.stats["spawns"] == 1
            ly = db.Layout()
            top = ly.create_cell("TOP")
            c = ly.create_cell(sys.argv[1], LIB, {"w": 1.5, "l": 0.5, sys.argv[2]: 3})
            top.insert(db.CellInstArray(c.cell_index(), db.Trans()))
            b = c.dbbox()
            print("BBOX", b.left, b.bottom, b.right, b.top, c.display_title())
        """
        rc, text = run_py(body, self.env(), [D["mos"], FINGERS])
        self.assertEqual(rc, 0, text)
        short = D["mos"].replace("sky130_fd_pr__", "")
        self.assertIn(" %s.%s(w=1.5 l=0.5 %s=3)" % (LIB, short, FINGERS), text)
        if PDK == "sky130A":
            self.assertIn("BBOX -1.965 -1.745 1.965 1.745 sky130_magic.nfet_01v8(w=1.5 l=0.5 nf=3)", text)

    def test_opening_a_file_never_runs_a_command_in_a_parameter(self):
        # A saved instance whose coverage string, choice or number list holds
        # a Tcl command: placing it and reopening the file (empty cache, so
        # produce asks Magic) must not run the command, and the cell must
        # carry the error marker.
        marker = os.path.join(self.tmp, "INJECTED")
        gds = os.path.join(self.tmp, "inj.gds")
        body = """
            assert kmp.register(PDK) is not None, kmp.state_for(PDK).last_error
            st = kmp.state_for(PDK)
            marker, gds = sys.argv[1], sys.argv[2]
            if sys.argv[3] == "make":
                ly = db.Layout()
                top = ly.create_cell("TOP")
                for item in sys.argv[4:]:
                    dev, name = item.split(":")
                    vals = {name: "[exec touch %s]" % marker}
                    if st.manifest[dev].param("guard") is not None:
                        vals["guard"] = True
                    c = ly.create_cell(dev, LIB, vals)
                    top.insert(db.CellInstArray(c.cell_index(), db.Trans()))
                ly.write(gds)
            else:
                ly = db.Layout()
                ly.read(gds)
            ph = ly.layer(255, 0)
            for c in ly.each_cell():
                if c.name == "TOP":
                    continue
                texts = [t.text_string for t in c.shapes(ph).each() if t.is_text()]
                print("CELL", c.name, c.is_pcell_variant(), "|".join(texts))
            print("MARKER", os.path.exists(marker))
        """
        items = ["%s:%s" % dn for dn in D["refused"]]
        for step in ("make", "open"):
            env = self.env(KMP_CACHE_DIR=os.path.join(self.tmp, "cache-" + step))
            rc, text = run_py(body, env, [marker, gds, step] + items)
            self.assertEqual(rc, 0, text)
            self.assertIn("MARKER False", text, step)
            cells = [ln for ln in text.splitlines() if ln.startswith("CELL ")]
            self.assertEqual(len(cells), len(items), text)
            for ln in cells:
                self.assertIn(" True KMP_ERROR ", ln, step)
                self.assertIn("not sent to Magic", ln, step)

    def test_dialog_values_survive_reopen_and_refresh(self):
        # The stored values are what Magic's dialog shows; the cell is what
        # its Create makes of them. Magic's _check isn't idempotent, so a
        # reopened file or a library refresh must not run the dialog on the
        # stored values again. On sky130A, res_xhigh_po_5p73 with a typed
        # val shows l 5.997, and typing that val again gives l 5.994 (another
        # cell); res_high_po_0p35 with l 0 and val 10000 shows val 1113.259
        # (Magic draws nothing for it), and typing its l again gives
        # 1113.258. res_high_po_0p69 with w 1.0 and cap_mim_m3_1 with l 0 and
        # val 50 are the cases where one _check on Magic's own output changed
        # val. Four processes, each with the disk cache off: make and save
        # GDS and OASIS, reopen the GDS (refresh, save again), reopen the
        # OASIS, reopen the second save.
        if PDK == "sky130A":
            cases = [("sky130_fd_pr__res_high_po_0p69", {"w": 1.0}),
                     ("sky130_fd_pr__cap_mim_m3_1", {"l": 0.0, "val": 50.0}),
                     ("sky130_fd_pr__res_high_po_0p35", {"l": 0.0, "val": 10000.0}),
                     ("sky130_fd_pr__res_xhigh_po_5p73", {"val": 1000.0})]
        else:
            cases = [(D["res"], {"l": 0.1}), (D["mos"], {"l": 0.1, "w": 0.1})]
        body = """
            import json
            assert kmp.register(PDK) is not None, kmp.state_for(PDK).last_error
            st = kmp.state_for(PDK)
            lib = db.Library.library_by_name(LIB)
            step, path, out = sys.argv[1], sys.argv[2], sys.argv[3]
            cases = json.loads(sys.argv[4])

            def sig(ly, c):
                rows = []
                for li in ly.layer_indices():
                    r = db.Region(c.begin_shapes_rec(li))
                    t = sorted(str(x) for x in db.Texts(c.begin_shapes_rec(li)).each())
                    if not r.is_empty() or t:
                        rows.append([ly.get_info(li).to_s(), sorted(str(p) for p in r.merged().each()), t])
                return sorted(rows)

            def norm(params):
                # A double as the 15 digits KLayout saves it with.
                return {k: ("%.15g" % v if isinstance(v, float) else v) for k, v in params.items()}

            def snap(ly):
                return {c.name: [c.pcell_declaration().name(), norm(c.pcell_parameters_by_name()), sig(ly, c)]
                        for c in ly.each_cell() if c.is_pcell_variant()}

            ly = db.Layout()
            before = dict(st.generator.stats)
            if step == "make":
                top = ly.create_cell("TOP")
                extra = {}
                for i, (dev, typed) in enumerate(cases):
                    v = kmp.dialog_values(dev, typed)
                    c = ly.create_cell(dev, LIB, v)
                    top.insert(db.CellInstArray(c.cell_index(), db.Trans(db.Vector(i * 50000, 0))))
                    spec = st.manifest[dev]
                    form = json.loads(v["kmp_dialog"])["form"]
                    # What magic::gencell makes of the typed values (one _check)
                    # and what typing each edited field again would show.
                    raw = st.server.check(dev, dict(spec.build_request(dict(spec.defaults_values(), **typed))))
                    again = {}
                    for n in typed:
                        rep = st.server.dialog(spec, form, [(n, form[n])])
                        again[n] = {k: [form[k], rep.form[k]] for k in form if rep.form[k] != form[k]}
                    extra[c.name] = {"typed": typed, "form": form, "gencell_checked": raw.checked,
                                     "again": again}
                ly.write(path)
                ly.write(path + ".oas")
                print("EXTRA", json.dumps(extra, sort_keys=True))
            else:
                ly.read(path)
            a = snap(ly)
            lib.refresh()
            b = snap(ly)
            if out:
                ly.write(out)
            print("SNAP", json.dumps({"opened": a, "refreshed": b}, sort_keys=True, default=str))
            print("STATS", json.dumps({k: st.generator.stats[k] - before.get(k, 0) for k in st.generator.stats}))
        """
        gds = os.path.join(self.tmp, "dlg.gds")
        resaved = os.path.join(self.tmp, "dlg2.gds")
        runs = []
        for step, path, out in (("make", gds, ""), ("open", gds, resaved), ("open2", gds + ".oas", ""),
                                ("open3", resaved, "")):
            env = self.env(KMP_CACHE="0")
            rc, text = run_py(body, env, [step, path, out, json.dumps(cases)])
            self.assertEqual(rc, 0, text)
            snap = json.loads([ln for ln in text.splitlines() if ln.startswith("SNAP ")][0][5:])
            stats = json.loads([ln for ln in text.splitlines() if ln.startswith("STATS ")][0][6:])
            runs.append((step, snap, stats, text))
        made = runs[0][1]["opened"]
        extra = json.loads([ln for ln in runs[0][3].splitlines() if ln.startswith("EXTRA ")][0][6:])
        self.assertEqual(len(made), len(cases), runs[0][3])
        for step, snap, stats, text in runs:
            want = {v[0]: v[1:] for v in made.values()}
            for when in ("opened", "refreshed"):
                # By device: the cell names may differ.
                got = {v[0]: v[1:] for v in snap[when].values()}
                self.assertEqual(sorted(got), sorted(want), (step, when))
                for dev in want:
                    pa, ga = got[dev]
                    pb, gb = want[dev]
                    self.assertEqual(pa, pb, (step, when, dev))
                    self.assertEqual([g[0] for g in ga], [g[0] for g in gb], (step, when, dev))
                    for x, y in zip(ga, gb):
                        self.assertEqual(x, y, (step, when, dev, x[0]))
            if step != "make":
                # Nothing was typed into Magic's dialog again, and every
                # variant came from Magic in this process.
                self.assertEqual(stats.get("dialog_magic"), 0, (step, stats))
                self.assertGreater(stats.get("magic"), 0, (step, stats))
        for name, (dev, params, geo) in made.items():
            e = extra[name]
            if dev != "sky130_fd_pr__res_high_po_0p35":
                self.assertTrue(geo, name)
            if PDK == "sky130A" or dev == D["mos"]:
                for n, typed in e["typed"].items():
                    self.assertNotEqual(float(params[n]), typed, (name, n))   # the dialog corrected it
            if PDK == "sky130A":
                # One _check (magic::gencell) on the typed values gives other
                # values than the dialog's form.
                diff = [k for k in e["form"] if e["gencell_checked"].get(k) != e["form"][k]]
                self.assertTrue(diff, (name, e))
        if PDK == "sky130A":
            def again(dev):
                return extra[[n for n in extra if n.startswith(dev + "__")][0]]["again"]
            self.assertEqual(again("sky130_fd_pr__res_high_po_0p35")["l"], {"val": ["1113.259", "1113.258"]})
            self.assertEqual(again("sky130_fd_pr__res_xhigh_po_5p73")["val"],
                             {"l": ["5.997", "5.994"], "val": ["2.158k", "2.157k"]})

    def test_a_command_in_a_stored_dialog_form_never_runs(self):
        # kmp_dialog is text in the file: a form value that is not a number
        # is not used (the values are typed into the dialog again instead),
        # and never reaches Magic.
        marker = os.path.join(self.tmp, "INJECTED")
        body = """
            import json
            assert kmp.register(PDK) is not None, kmp.state_for(PDK).last_error
            dev, marker = sys.argv[1], sys.argv[2]
            v0 = kmp.dialog_values(dev, {"l": 0.1})
            # In the form Create was pressed with, and in what the dialog
            # shows afterwards (where a later edit starts).
            for part in ("form", "shows"):
                v = dict(v0)
                d = json.loads(v["kmp_dialog"])
                for k in d[part]:
                    if k != "l":
                        d[part][k] = "[exec touch %s]" % marker
                        break
                v["kmp_dialog"] = json.dumps(d)
                ly = db.Layout()
                c = ly.create_cell(dev, LIB, v)
                ph = ly.layer(255, 0)
                print("CELL", part, c.dbbox().empty(), c.shapes(ph).is_empty())
                v["l"] = 0.2  # an edit, which would start from "shows"
                c = ly.create_cell(dev, LIB, v)
                print("EDIT", part, c.dbbox().empty(), c.shapes(ph).is_empty())
            print("MARKER", os.path.exists(marker))
        """
        rc, text = run_py(body, self.env(KMP_CACHE="0"), [D["mos"], marker])
        self.assertEqual(rc, 0, text)
        for part in ("form", "shows"):
            self.assertIn("CELL %s False True" % part, text)
            self.assertIn("EDIT %s False True" % part, text)
        self.assertIn("MARKER False", text)

    @sky130_only
    def test_magic_behaviour_the_dialog_model_leaves_out(self):
        # Review 3, findings 1 and 2, pinned as Magic's own behaviour (the
        # README says which interaction the PCell reproduces):
        # - sky130's res_check flips w on a snake resistor shorter than
        #   5.73 um: the wmin clamp sets w to 5.73, the "Snake resistor
        #   width must be < length" test sets it back to l, and each pass
        #   reads the other's result. So the drawn w depends on how many
        #   bindings a user's Returns, Tabs and clicks run.
        # - A value typed with no Return before Create runs no binding:
        #   Create's one _check is magic::gencell's. res_generic_po with
        #   l 0 then makes an empty cell; with Return, the dialog shows
        #   l 1.65 and Create draws it.
        body = """
            import json
            assert kmp.register(PDK) is not None, kmp.state_for(PDK).last_error
            st = kmp.state_for(PDK)
            spec = st.manifest["sky130_fd_pr__res_high_po_5p73"]
            p = dict(spec.build_request(dict(spec.defaults_values(), l=1.87, snake=True)))
            ws = []
            for i in range(4):
                p = dict(st.server.check(spec.name, p).checked)
                ws.append(p["w"])
            print("SNAKE", json.dumps(ws))
            spec = st.manifest["sky130_fd_pr__res_generic_po"]
            once = st.server.check(spec.name, spec.build_request(dict(spec.defaults_values(), l=0.0)))
            print("ONCE", once.checked["l"])
            v = kmp.dialog_values(spec.name, {"l": 0.0})
            ly = db.Layout()
            c = ly.create_cell(spec.name, LIB, v)
            print("RETURN", v["l"], c.dbbox().empty())
            req = spec.build_request(dict(spec.defaults_values(), l=0.0))
            r = st.generator.get(spec, req)
            from klayout_magic_pcells.importer import gds_has_shapes
            print("NORETURN", gds_has_shapes(r.gds_path))
        """
        rc, text = run_py(body, self.env(KMP_CACHE="0"))
        self.assertEqual(rc, 0, text)
        ws = json.loads([ln for ln in text.splitlines() if ln.startswith("SNAKE ")][0][6:])
        self.assertEqual([float(w) for w in ws], [1.87, 5.73, 1.87, 5.73], text)
        self.assertIn("RETURN 1.65 False", text)
        self.assertIn("NORETURN False", text)

    def test_register_fails_cleanly_on_a_bad_manifest(self):
        with open(CFG.manifest) as f:
            man = json.load(f)
        # A parameter called "layout" would overwrite PCellDeclarationHelper.layout.
        man["devices"][0]["params"].append({"name": "layout", "type": "float", "default": "1",
                                            "editable": True})
        bad = os.path.join(self.tmp, "bad.json")
        with open(bad, "w") as f:
            json.dump(man, f)
        body = """
            assert kmp.register(PDK) is None
            assert db.Library.library_by_name(LIB) is None
            assert kmp.state_for(PDK).server is None
            print("ERR", kmp.state_for(PDK).last_error)
        """
        rc, text = run_py(body, self.env(KMP_MANIFEST=bad), timeout=60)
        self.assertEqual(rc, 0, text)
        self.assertIn("collide", text)

    def test_register_refuses_an_rcfile_that_loads_no_pdk(self):
        # An empty rcfile, and one with a Tcl syntax error: every PCell would
        # draw the marker and saving a file would replace its geometry, so
        # nothing registers, and the error says the rcfile loaded no PDK
        # (version 0.3 named the namespace sky130 for every PDK) and quotes
        # Magic.
        empty = os.path.join(self.tmp, "empty.magicrc")
        open(empty, "w").close()
        syntax = os.path.join(self.tmp, "syntax.magicrc")
        with open(syntax, "w") as f:
            f.write("this is not tcl {\n")
        body = """
            assert kmp.register(PDK) is None
            assert db.Library.library_by_name(LIB) is None
            assert kmp.state_for(PDK).server is None
            print("ERR", kmp.state_for(PDK).last_error)
        """
        n = len(Manifest.load(CFG.manifest).devices)
        for rc_file, said in ((empty, 'Using technology "minimum"'), (syntax, "missing close-brace")):
            rc, text = run_py(body, self.env(KMP_MAGICRC=rc_file))
            self.assertEqual(rc, 0, text)
            self.assertIn("the rcfile %s loaded no PDK" % rc_file, text)
            self.assertIn("none of the manifest's %d generators" % n, text)
            self.assertIn(said, text)
            self.assertNotIn("namespace sky130,", text)
            self.assertIn("KMP_MANIFEST", text)

    def test_register_refuses_another_variants_technology(self):
        # sky130A and sky130B share the generator namespace sky130, and the
        # gf180mcu variants A to F share gf180mcu; only Magic's technology
        # name tells them apart. No other variant is installed in the image,
        # so this rcfile loads the PDK and then a copy of its tech file that
        # names another technology.
        other = {"sky130A": "sky130B", "gf180mcuD": "gf180mcuC"}.get(PDK, PDK + "x")
        techdir = os.path.join(self.tmp, "magic")
        shutil.copytree(os.path.dirname(CFG.magicrc), techdir)
        tech = os.path.join(techdir, PDK + ".tech")
        with open(tech, encoding="utf-8") as f:
            text = f.read()
        text, n = re.subn(r"(?m)^(tech\s*\n\s*format\s+\d+\s*\n\s*)%s\b" % re.escape(PDK),
                          r"\g<1>" + other, text, count=1)
        self.assertEqual(n, 1, "no tech section naming %s" % PDK)
        with open(tech, "w", encoding="utf-8") as f:
            f.write(text)
        rc_file = os.path.join(self.tmp, "variant.magicrc")
        with open(rc_file, "w") as f:
            f.write("source %s\ntech load %s\n" % (CFG.magicrc, tech))
        body = """
            assert kmp.register(PDK) is None
            assert db.Library.library_by_name(LIB) is None
            print("ERR", kmp.state_for(PDK).last_error)
        """
        rc, text = run_py(body, self.env(KMP_MAGICRC=rc_file))
        self.assertEqual(rc, 0, text)
        self.assertIn("loaded the Magic technology %s, not %s" % (other, PDK), text)
        # The same rcfile without the second tech load registers.
        with open(rc_file, "w") as f:
            f.write("source %s\n" % CFG.magicrc)
        rc, text = run_py("assert kmp.register(PDK) is not None", self.env(KMP_MAGICRC=rc_file))
        self.assertEqual(rc, 0, text)

    def test_an_unwritable_cache_dir_only_turns_the_cache_off(self):
        ro = os.path.join(self.tmp, "ro")
        os.makedirs(ro)
        os.chmod(ro, 0o555)
        tmpdir = os.path.join(self.tmp, "tmpdir")
        os.makedirs(tmpdir)
        body = """
            assert kmp.register(PDK) is not None, kmp.state_for(PDK).last_error
            st = kmp.state_for(PDK)
            ly = db.Layout()
            c = ly.create_cell(sys.argv[1], LIB, {"w": 1.0})
            print("CELL", not c.dbbox().empty(), st.cfg.cache_enabled, st.generator.stats["magic"])
        """
        try:
            for cache in ("1", "0"):
                env = self.env(KMP_CACHE_DIR=os.path.join(ro, "c"), KMP_CACHE=cache, TMPDIR=tmpdir)
                rc, text = run_py(body, env, [D["mos"]])
                self.assertEqual(rc, 0, text)
                self.assertIn("CELL True False 1", text)
                if cache == "1":
                    self.assertIn("can't be used", text)
                    self.assertIn("KMP_CACHE_DIR", text)
                else:
                    self.assertNotIn("can't be used", text)
                # the session's run and no-cache directories are gone
                self.assertEqual(os.listdir(tmpdir), [], cache)
        finally:
            os.chmod(ro, 0o755)

    def test_cli_leaves_nothing_behind_and_reports_failure(self):
        tmpdir = os.path.join(self.tmp, "tmpdir")
        os.makedirs(tmpdir)
        env = self.env(TMPDIR=tmpdir)
        out = os.path.join(self.tmp, "x.gds")
        rc, text = cli(env, "generate", D["mos"], "w=1", "-o", out, cwd=self.tmp)
        self.assertEqual(rc, 0, text)
        dev, name = D["empty"]
        rc, text = cli(env, "generate", dev, "%s=0" % name, "-o", out, cwd=self.tmp)
        self.assertEqual(rc, 1, text)
        self.assertIn("Magic drew nothing", text)
        # check presses Create once too: Magic draws nothing here, although
        # its dialog hands back a value (sky130A res_high_po_0p35: val 10000,
        # then l 0, which the dialog turns into the SPICE string 1.218u,
        # which _draw fails on).
        rc, text = cli(env, "check", dev, "%s=0" % name, cwd=self.tmp)
        self.assertEqual(rc, 1, text)
        self.assertIn("Magic draws nothing for these values", text)
        if PDK == "sky130A":
            rc, text = cli(env, "check", "sky130_fd_pr__res_high_po_0p35", "val=10000", "l=0", cwd=self.tmp)
            self.assertEqual(rc, 1, text)
            self.assertIn("Magic's dialog shows l=1.218u (entered 0.0)", text)
            self.assertIn("Magic draws nothing for these values", text)
            rc, text = cli(env, "check", "sky130_fd_pr__res_generic_po", "l=0", cwd=self.tmp)
            self.assertEqual(rc, 0, text)
            self.assertIn("Magic's dialog shows l=1.650 (entered 0.0)", text)
        dev, name = D["refused"][0]
        rc, text = cli(env, "generate", dev, "%s=abc" % name, "-o", out, cwd=self.tmp)
        self.assertEqual(rc, 1, text)
        self.assertIn("KMP_ERROR", text)
        rc, text = cli(env, "check", dev, "%s=[exec ls]" % name, cwd=self.tmp)
        self.assertEqual(rc, 2, text)
        self.assertIn("not sent to Magic", text)
        # A box below the minimum on one side: Magic paints nothing.
        spec = Manifest.load(CFG.manifest)["via1"]
        m = float(spec.raw["min_box_um"])
        rc, text = cli(env, "check", "--pdk", PDK, "via1", "w=%.3f" % (m - 0.01), "h=%.3f" % (m + 0.04),
                       cwd=self.tmp)
        self.assertEqual(rc, 1, text)
        self.assertIn("via1: Magic paints nothing on a", text)
        self.assertIn("width must be at least", text)
        rc, text = cli(env, "check", "--pdk", PDK, "via1", "w=-1", "h=1", cwd=self.tmp)
        self.assertEqual(rc, 0, text)
        self.assertIn("via1: Magic paints a 1.0 x 1.0 um box (entered -1.0 x 1.0)", text)
        # A value the CLI can't parse: an error line, exit 2, no traceback.
        rc, text = cli(env, "check", D["mos"], "%s=1.5" % FINGERS, cwd=self.tmp)
        self.assertEqual(rc, 2, text)
        self.assertIn("error: ", text)
        for args in (("check", D["mos"], "w=0.1"), ("check", D["mos"], "w=abc"), ("doctor",),
                     ("cache", "stats"), ("audit", out)):
            rc, text = cli(env, *args, cwd=self.tmp)
            self.assertNotIn("Traceback", text, args)
        self.assertEqual(os.listdir(tmpdir), [])
        self.assertEqual(os.listdir(os.path.join(self.tmp, "cache", "run")), [])

    def test_form_callback_icons(self):
        # The GUI form's callback (driven here with PCellParameterStates, as
        # KLayout's form calls it): a box below its minimum on one side gets
        # the icon on that side only; a device Magic draws nothing for says
        # so; a value Magic's dialog clamps says what the dialog shows.
        body = """
            assert kmp.register(PDK) is not None, kmp.state_for(PDK).last_error
            ly = db.Library.library_by_name(LIB).layout()
            def cb(dev, vals):
                decl = ly.pcell_declaration(dev)
                states = db.PCellParameterStates()
                for pd in decl.get_parameters():
                    states.parameter(pd.name).value = vals.get(pd.name, pd.default)
                decl.callback(ly, list(vals)[0], states)
                icons = {db.PCellParameterState.WarningIcon: "WARN", db.PCellParameterState.ErrorIcon: "ERR"}
                out = {}
                for pd in decl.get_parameters():
                    st = states.parameter(pd.name)
                    if st.icon in icons:
                        out[pd.name] = (icons[st.icon], st.tooltip)
                print("CB", json.dumps(out, sort_keys=True))
            import json
            m, big = float(sys.argv[1]), float(sys.argv[2])
            cb("via1", {"w": m - 0.01, "h": big})
            cb("via1", {"h": m - 0.01, "w": big})
            cb("via1", {"w": big, "h": big})
            dev, name = sys.argv[3], sys.argv[4]
            cb(dev, {name: 0.0})
            cb(sys.argv[5], {"l": 0.1})
            cb(sys.argv[6], {sys.argv[7]: "[exec ls]"})
        """
        spec = Manifest.load(CFG.manifest)["via1"]
        m = float(spec.raw["min_box_um"])
        dev, name = D["empty"]
        rc, text = run_py(body, self.env(), [repr(m), repr(m + 1), dev, name, D["mos"]]
                          + list(D["refused"][0]))
        self.assertEqual(rc, 0, text)
        lines = [json.loads(ln[3:]) for ln in text.splitlines() if ln.startswith("CB ")]
        self.assertEqual(len(lines), 6, text)
        w_low, h_low, ok, empty, small, refused = lines
        self.assertEqual(sorted(w_low), ["w"], text)
        self.assertIn("Magic draws nothing", w_low["w"][1])
        self.assertIn("width", w_low["w"][1])
        self.assertEqual(sorted(h_low), ["h"], text)
        self.assertIn("height", h_low["h"][1])
        self.assertEqual(ok, {}, text)
        self.assertTrue(empty, text)
        self.assertTrue(all(v[0] == "WARN" and v[1].startswith("Magic draws nothing") for v in empty.values()),
                        text)
        self.assertEqual(sorted(small), ["l"], text)
        m = re.search(r"Magic's dialog shows ([0-9.]+) \(entered 0\.1\)", small["l"][1])
        self.assertTrue(m, small)
        self.assertEqual(float(m.group(1)), float(D["small"][0]), small)
        self.assertEqual(list(refused.values())[0][0], "ERR", text)

    def _make_and_audit(self, devices, dbu="0.001", env=None, audit_env=None, regen=True):
        """Place ``devices`` [(device, {params})] in a file at ``dbu``, then
        audit it. Returns (audit exit status, audit text, file)."""
        gds = os.path.join(self.tmp, "a%s.gds" % dbu)
        body = """
            assert kmp.register(PDK) is not None, kmp.state_for(PDK).last_error
            ly = db.Layout()
            ly.dbu = float(sys.argv[2])
            top = ly.create_cell("TOP")
            for dev, vals in json.loads(sys.argv[3]):
                c = ly.create_cell(dev, LIB, vals)
                top.insert(db.CellInstArray(c.cell_index(), db.Trans()))
            ly.write(sys.argv[1])
            print("OK", kmp.state_for(PDK).generator.stats)
        """
        rc, text = run_py("import json\n" + textwrap.dedent(body), env or self.env(),
                          [gds, dbu, json.dumps(devices)])
        self.assertEqual(rc, 0, text)
        args = ["audit", gds] + (["--regen"] if regen else [])
        rc, text = cli(audit_env or env or self.env(), *args)
        return rc, text, gds

    def test_audit_after_a_local_generator_edit(self):
        # via1_draw edited in the PDK's generator code (its box grown by
        # 0.1 um before it paints): the stamp's digest shows it, audit
        # --regen counts the difference as a problem and exits 1, and
        # reopening the file warns.
        ns = Manifest.load(CFG.manifest).namespace
        edit = insert_after_proc("%s::via1_draw" % ns, "box grow e 0.1um")
        root = farm(os.path.join(self.tmp, "farm"), edit_tcl=edit)
        self.assertEqual(len(edit.done), 1, edit.done)
        edited = self.env(PDK_ROOT=root)
        # via2 doesn't call via1_draw (the IHP MOSFETs and resistors do).
        rc, text, gds = self._make_and_audit([("via1", {}), ("via2", {})])
        self.assertEqual(rc, 0, text)
        rc, text = cli(edited, "audit", gds, "--regen")
        self.assertEqual(rc, 1, text)
        via = [ln for ln in text.splitlines() if "via1__kmp_" in ln][0]
        other = [ln for ln in text.splitlines() if "via2__kmp_" in ln][0]
        self.assertIn("regenerated geometry differs on", via)
        self.assertIn("digest=", via)
        self.assertIn("generated with", other)          # same tech version, other code digest
        self.assertNotIn("regenerated geometry differs", other)
        self.assertIn("2 %s cells, 2 with problems" % LIB, text)
        rc, text = run_py(REOPEN, edited, [gds])
        self.assertEqual(rc, 0, text)
        self.assertIn("via1: instance created with", text)

    def test_a_generator_that_now_fails_still_warns_on_reopen(self):
        # The gf180mcuD tester's case: a file reopened under a PDK whose
        # _draw for a saved device raises. Magic writes an empty cell (as it
        # does for a zero size), and the "created with" warning must still
        # appear: produce returned before comparing the stamps.
        ns = Manifest.load(CFG.manifest).namespace
        edit = insert_after_proc("%s::%s_draw" % (ns, D["mos"]), 'error "kmp-test: injected generator error"')
        root = farm(os.path.join(self.tmp, "farm"), edit_tcl=edit)
        self.assertEqual(len(edit.done), 1, edit.done)
        rc, text, gds = self._make_and_audit([(D["mos"], {})], regen=False)
        self.assertEqual(rc, 0, text)
        rc, text = run_py(REOPEN, self.env(PDK_ROOT=root, KMP_CACHE="0"), [gds])
        self.assertEqual(rc, 0, text)
        self.assertIn("Magic drew nothing for these parameters: kmp-test: injected generator error", text)
        self.assertIn("instance created with", text)

    @sky130_only
    def test_audit_after_a_vendor_gds_edit(self):
        # The review's case: one boundary of rf_test_coil1 in sky130_fd_pr.gds
        # moved 1 um, under the same open_pdks commit. The cache key and the
        # stamp cover the vendor GDS, so the edited PDK neither reads the old
        # cache entry nor passes the stamp check.
        def move_first_boundary(data):
            data = bytearray(data)
            i, in_bnd = 10318056, False         # rf_test_coil1's GDS_START
            while i < 10324764:
                n, rt, _ = struct.unpack(">HBB", data[i:i + 4])
                if rt == 0x08:
                    in_bnd = True
                if rt == 0x10 and in_bnd:
                    k = (n - 4) // 4
                    v = list(struct.unpack(">%di" % k, data[i + 4:i + n]))
                    for j in range(0, k, 2):
                        v[j] += 1000
                    data[i + 4:i + n] = struct.pack(">%di" % k, *v)
                    return bytes(data)
                i += n
            raise AssertionError("no boundary found")
        root = farm(os.path.join(self.tmp, "farm"), edit_vendor_gds=move_first_boundary)
        rc, text, gds = self._make_and_audit([("sky130_fd_pr__rf_test_coil1", {})], regen=False)
        rc, text = cli(self.env(PDK_ROOT=root), "audit", gds, "--regen")
        self.assertEqual(rc, 1, text)
        self.assertIn("regenerated geometry differs on", text)
        self.assertIn("generated with", text)

    def test_audit_regen_replaces_a_stale_cache_entry(self):
        # A cache entry whose GDS (with a matching sidecar digest) isn't what
        # Magic generates now: audit --regen asks Magic anyway, reports the
        # entry and replaces it, so the next session reads the new one.
        rc, text, gds = self._make_and_audit([(D["res"], {}), (D["res"], {"l": 5.0})], regen=False)
        entries = sorted(glob.glob(os.path.join(self.tmp, "cache", "v1", "*", D["res"], "*.gds")))
        self.assertEqual(len(entries), 2)
        # Put one entry's GDS under the other's key, with a matching digest.
        a, b = entries
        shutil.copyfile(b, a)
        side = a[:-4] + ".json"
        with open(side) as f:
            sc = json.load(f)
        with open(a, "rb") as f:
            sc["gds_sha256"] = hashlib.sha256(f.read()).hexdigest()
        with open(side, "w") as f:
            json.dump(sc, f)
        rc, text = cli(self.env(), "audit", gds, "--regen")
        self.assertEqual(rc, 1, text)
        self.assertIn("disk cache held a stale %s" % D["res"], text)
        self.assertEqual(text.count("regenerated: same as stored"), 2, text)
        # Replaced: a second audit finds nothing.
        rc, text = cli(self.env(), "audit", gds, "--regen")
        self.assertEqual(rc, 0, text)

    @unittest.skipUnless(D["vendor"] or D["script"], "the PDK's fixed devices need no file")
    def test_a_missing_vendor_file_is_named_in_the_marker(self):
        # sky130A and gf180mcuD copy fixed devices from libs.ref GDS; the IHP
        # PDKs draw them with a layout script in libs.tech/magic. Either one
        # missing: the marker names it (on IHP, in front of gencell_create's
        # own error, which came first and pushed it past the marker's 400
        # characters).
        if D["vendor"]:
            root = farm(os.path.join(self.tmp, "farm"), drop_vendor_gds=True)
            want = ".gds"
        else:
            root = farm(os.path.join(self.tmp, "farm"), remove=(D["script"],))
            want = "read file"
        body = """
            assert kmp.register(PDK) is not None, kmp.state_for(PDK).last_error
            ly = db.Layout()
            c = ly.create_cell(sys.argv[1], LIB, {})
            print("MARKER", [sh.text_string for sh in c.shapes(ly.layer(255, 0)).each() if sh.is_text()])
            # The same request again (coerce and produce each ask): what the
            # failed one left in Magic must not make this one succeed.
            ly2 = db.Layout()
            c1 = ly2.create_cell(sys.argv[1], LIB, {})
            print("AGAIN", not c1.shapes(ly2.layer(255, 0)).is_empty())
            c2 = ly.create_cell(sys.argv[2], LIB, {})
            print("NEXT", c2.dbbox().empty(), not c2.shapes(ly.layer(255, 0)).is_empty())
        """
        rc, text = run_py(body, self.env(PDK_ROOT=root, KMP_CACHE_DIR=os.path.join(self.tmp, "c")),
                          [D["fixed"], D["mos"]])
        self.assertEqual(rc, 0, text)
        marker = [ln for ln in text.splitlines() if ln.startswith("MARKER")][0]
        self.assertIn("KMP_ERROR %s: " % D["fixed"], marker)
        self.assertIn(want, marker)
        if D["script"]:
            self.assertIn(D["script"] + '": no such file or directory', marker)
            self.assertNotIn("-errorstack", marker)
        self.assertIn("AGAIN True", text)
        self.assertIn("NEXT False False", text)

    def test_audit_flags_cells_rounded_by_the_file_dbu(self):
        # The grid of each cell's own Magic output is in its stamp. A box on
        # Magic's 5 nm grid in a file at dbu 0.002 is rounded, although the
        # generator's default box is on 10 nm (the testers' mcon, via4,
        # bondpad and inductor cases, which audit called ok); at 0.0025 it
        # is exact.
        man = Manifest.load(CFG.manifest)
        spec = [d for d in man.devices if d.kind == "box" and d.batch.get("grid_nm") == 10][0]
        m = float(spec.raw["min_box_um"])
        fine = (spec.name, {"w": round(m + 1.005, 3), "h": round(m + 1.005, 3)})
        for dbu, want in (("0.002", 1), ("0.0025", 0), ("0.001", 0)):
            rc, text, gds = self._make_and_audit([fine, (spec.name, {})], dbu=dbu, regen=False)
            cells = [ln for ln in text.splitlines() if spec.name + "__kmp_" in ln]
            self.assertEqual(len(cells), 2, text)
            flagged = [ln for ln in cells if "grid" in ln]
            self.assertEqual(len(flagged), want, text)
            for ln in flagged:
                self.assertIn("This cell's Magic output has coordinates on a 5 nm grid", ln)
            self.assertEqual(rc, want, text)
        if PDK == "sky130A":
            # A vendor cell with 1 nm coordinates in a 5 nm file.
            for dbu, want in (("0.005", 1), ("0.001", 0)):
                rc, text, gds = self._make_and_audit([("sky130_fd_pr__pnp_05v5_W0p68L0p68", {}),
                                                      ("sky130_fd_pr__nfet_01v8", {})], dbu=dbu, regen=False)
                self.assertEqual(rc, want, text)
                pnp = [ln for ln in text.splitlines() if "pnp_05v5_W0p68L0p68__kmp_" in ln][0]
                nf = [ln for ln in text.splitlines() if "nfet_01v8__kmp_" in ln][0]
                self.assertEqual("1 nm grid" in pnp, want == 1, text)
                self.assertTrue(nf.rstrip().endswith(" ok"), text)

    def test_register_fails_cleanly_without_magic(self):
        body = """
            assert kmp.register(PDK) is None
            assert db.Library.library_by_name(LIB) is None
            print("ERR", kmp.state_for(PDK).last_error)
        """
        rc, text = run_py(body, self.env(KMP_MAGIC="/no/magic"), timeout=60)
        self.assertEqual(rc, 0, text)
        self.assertIn("KMP_MAGIC", text)


if __name__ == "__main__":
    unittest.main()
