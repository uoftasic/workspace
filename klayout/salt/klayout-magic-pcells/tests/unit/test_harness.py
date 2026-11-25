"""The parity harness's own logic (no Magic needed)."""

import json
import os
import shutil
import struct
import sys
import tempfile
import textwrap
import unittest

from tests.unit._util import REPO, needs_klayout  # noqa: F401  (puts tests/parity on sys.path)
import run_sweep  # noqa: E402

# Stands in for "magic ... magic_ref.tcl": one index line per point from
# KMP_START on; the device name says how the point behaves.
FAKE_MAGIC = textwrap.dedent("""
    import json, os, sys, time
    pts = json.load(open(os.environ["KMP_SWEEP"]))["points"]
    start = int(os.environ.get("KMP_START", "0"))
    os.makedirs(os.environ["KMP_OUT"], exist_ok=True)
    ix = open(os.path.join(os.environ["KMP_OUT"], "index.jsonl"), "a" if start else "w")
    # "xerror:N": the first N starts die opening the window, as Magic does
    # under Xvfb when it gets BadAlloc for its first pixmap.
    xe = [pt["device"] for pt in pts[start:start + 1] if pt["device"].startswith("xerror:")]
    if xe:
        tries = os.path.join(os.environ["KMP_OUT"], "tries")
        n = int(open(tries).read()) if os.path.exists(tries) else 0
        open(tries, "w").write(str(n + 1))
        if n < int(xe[0].split(":")[1]):
            print("X Error of failed request:  BadAlloc (insufficient resources for operation)")
            print("  Major opcode of failed request:  53 (X_CreatePixmap)")
            sys.stdout.flush()
            os._exit(1)
    for pt in pts[start:]:
        if pt["device"] == "crash":
            os._exit(139)
        if pt["device"] == "hang":
            time.sleep(120)
        ix.write(json.dumps({"id": pt["id"], "device": pt["device"], "rc": 0, "top": "T",
                             "magic_cell": "X", "log": "", "error": "", "checked": {}}) + "\\n")
        ix.flush()
    print("REF_DONE")
""")


class PathAWatchdog(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="kmp-patha-")

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def run_fake(self, devices, stats=None):
        fake = os.path.join(self.d, "fake_magic.py")
        with open(fake, "w") as f:
            f.write(FAKE_MAGIC)
        sweep = os.path.join(self.d, "sweep.json")
        with open(sweep, "w") as f:
            json.dump({"points": [{"id": "%04d" % (i + 1), "device": d} for i, d in enumerate(devices)]}, f)
        ref = os.path.join(self.d, "ref")
        env = run_sweep.pdk_env(KMP_SWEEP=sweep, KMP_OUT=ref)
        with open(sweep) as f:
            pts = json.load(f)["points"]
        return run_sweep.run_watched("path A", [sys.executable, fake], pts,
                                     ref, os.path.join(self.d, "path_a.log"),
                                     os.path.join(self.d, "run_a"), env, 2, stats=stats)[0]

    def test_a_crash_and_a_hang_become_errors_and_the_sweep_goes_on(self):
        recs = self.run_fake(["ok", "crash", "ok", "hang", "ok"])
        self.assertEqual(sorted(recs), ["0001", "0002", "0003", "0004", "0005"])
        self.assertEqual([recs[k]["rc"] for k in sorted(recs)], [0, 1, 0, 1, 0])
        self.assertIn("Magic exited (status 139)", recs["0002"]["error"])
        self.assertIn("no point finished for 2 s", recs["0004"]["error"])

    def test_a_crash_on_the_last_point(self):
        recs = self.run_fake(["ok", "crash"])
        self.assertEqual((recs["0001"]["rc"], recs["0002"]["rc"]), (0, 1))

    def test_a_broken_harness_is_a_harness_error(self):
        with self.assertRaises(run_sweep.HarnessError):
            self.run_fake(["crash"] * 5 + ["ok"])

    def test_an_x_error_at_start_up_is_started_again_not_a_point_error(self):
        # GitHub run 45232459515: Magic under Xvfb died with BadAlloc before
        # its first point. That start is tried again; no point fails.
        stats = {}
        recs = self.run_fake(["xerror:3", "ok"], stats=stats)
        self.assertEqual([recs[k]["rc"] for k in sorted(recs)], [0, 0])
        self.assertEqual(stats["x_retries"], 3)
        self.assertIn("BadAlloc", stats["x_errors"][0])

    def test_an_x_error_at_every_start_is_a_harness_error(self):
        with self.assertRaises(run_sweep.HarnessError) as cm:
            self.run_fake(["xerror:%d" % (run_sweep.X_START_RETRIES + 1), "ok"])
        self.assertIn("X error", str(cm.exception))


def _rec(rt, dt, body=b""):
    if len(body) % 2:
        body += b"\0"
    return struct.pack(">HBB", 4 + len(body), rt, dt) + body


def _real8(x):
    """A GDSII 8-byte real (excess-64 base-16)."""
    if x == 0:
        return b"\0" * 8
    e = 64
    while x >= 1:
        x /= 16.0
        e += 1
    while x < 1 / 16.0:
        x *= 16.0
        e -= 1
    return struct.pack(">BQ", e, int(x * (1 << 56)))[:1] + struct.pack(">Q", int(x * (1 << 56)))[1:]


def gds_with_text(path, font, string=b"A"):
    """A one-cell GDS holding one text on 5/0 whose PRESENTATION has the
    given font bits."""
    data = (_rec(0x00, 2, struct.pack(">h", 600)) + _rec(0x01, 2, b"\0" * 24) + _rec(0x02, 6, b"LIB")
            + _rec(0x03, 5, _real8(0.001) + _real8(1e-9)) + _rec(0x05, 2, b"\0" * 24)
            + _rec(0x06, 6, b"TOP") + _rec(0x0C, 0) + _rec(0x0D, 2, struct.pack(">h", 5))
            + _rec(0x16, 2, struct.pack(">h", 0)) + _rec(0x17, 1, struct.pack(">H", font << 4))
            + _rec(0x10, 3, struct.pack(">ii", 100, 200)) + _rec(0x19, 6, string) + _rec(0x11, 0)
            + _rec(0x07, 0) + _rec(0x04, 0))
    with open(path, "wb") as f:
        f.write(data)
    return path


class RawRecords(unittest.TestCase):
    """gds_census reads what KLayout's GDS reader drops."""

    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="kmp-raw-")

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_text_fonts(self):
        from gds_census import text_fonts
        for font in range(4):
            p = gds_with_text(os.path.join(self.d, "f%d.gds" % font), font)
            self.assertEqual(text_fonts(p), [["5/0", "A", font]])
        self.assertNotEqual(text_fonts(os.path.join(self.d, "f0.gds")),
                            text_fonts(os.path.join(self.d, "f2.gds")))

    @needs_klayout
    def test_klayout_does_not_keep_the_font(self):
        # Why the harness reads fonts itself: through KLayout, font 2 and
        # font 0 are the same text.
        from compare import compare_cells
        a = gds_with_text(os.path.join(self.d, "a.gds"), 0)
        b = gds_with_text(os.path.join(self.d, "b.gds"), 2)
        self.assertTrue(compare_cells(a, "TOP", b, "TOP")["identical"])

    @needs_klayout
    def test_compare_command_line(self):
        # The documented command line (it stopped with an AttributeError on
        # text_attrs in version 0.3).
        import contextlib
        import io
        import compare
        a = gds_with_text(os.path.join(self.d, "a.gds"), 0)
        b = gds_with_text(os.path.join(self.d, "b.gds"), 0, b"B")
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            self.assertEqual(compare.main([a, "TOP", a, "TOP"]), 0)
            self.assertEqual(compare.main([a, "TOP", b, "TOP", "--quiet"]), 1)
            self.assertEqual(compare.main([a, "TOP", b, "TOP", "--quiet", "--no-texts"]), 0)
            self.assertEqual(compare.main([a, "TOP", a, "TOP", "--quiet", "--no-text-attrs",
                                           "--shape-counts"]), 0)
            self.assertEqual(compare.main([a, "NOPE", a, "TOP", "--quiet"]), 2)
        self.assertIn("IDENTICAL", out.getvalue())


if __name__ == "__main__":
    unittest.main()
