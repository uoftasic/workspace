"""Backend tests of the jobs: Magic run as a job (jobs.py and
tcl/kmp_job_common.tcl), on the PDK that KMP_PDK names. scripts/test.sh
runs this file once per PDK. Skipped when Magic, the PDK or the klayout
module is missing.
"""

import os
import shutil
import sys
import tempfile
import time
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "python"))

from klayout_magic_pcells import jobs  # noqa: E402
from klayout_magic_pcells.config import Config  # noqa: E402

try:
    import klayout.db as db
    from klayout_magic_pcells.export import export_cell
except ImportError:
    db = None

# The jobs keep their directories (under <cache>/jobs) for the user to look
# at; these tests use a cache of their own and delete it.
CACHE = tempfile.mkdtemp(prefix="kmp-jobs-cache-")
try:
    CFG = Config.load(env=dict(os.environ, KMP_CACHE_DIR=CACHE))
    HAVE_MAGIC = not CFG.problems()
except Exception:
    HAVE_MAGIC = False


def tearDownModule():
    shutil.rmtree(CACHE, ignore_errors=True)

needs_magic = unittest.skipUnless(HAVE_MAGIC and db is not None,
                                  "Magic, the PDK or the klayout module is missing")
PDK = CFG.pdk if HAVE_MAGIC else "sky130A"
# A layer Magic reads as metal1 on each PDK: a cell holding only shapes
# Magic ignores would be empty to it.
METAL1 = {"sky130A": (68, 20), "gf180mcuD": (34, 0), "ihp-sg13g2": (8, 0),
          "ihp-sg13cmos5l": (8, 0)}[PDK]

# The review's cell names (design-0.6.md 2.2).
NAMES = ["inv$1", "a.b", "a b", "a-b", "x/y", "brace{1}", "br[0]", "UPPER", "upper", "n" * 120, "café",
         "semi;colon"]
# What kmp_job_load must do with each name in a file KLayout wrote as it is
# (KLayout's writer itself turns "a b" into "a$b" and "café" into "caf$$").
LOADS = ["inv$1", "a-b", "brace{1}", "UPPER", "upper", "n" * 120, "semi;colon", "NTOP"]
FAILS = {"a.b": "load a.b failed", "a b": "not among the cells", "x/y": "left the cell",
         "br[0]": "left the cell", "café": "not among the cells", "does_not_exist": "not among the cells",
         "EMPTY": "is empty"}

PROBE_TCL = r"""
source $::env(KMP_TCL_DIR)/kmp_job_common.tcl
kmp_job_stage reading 0
if {[info exists ::env(KMP_WAIT)]} { after $::env(KMP_WAIT) }
kmp_job_read $::env(KMP_GDS)
set fh [open [file join $::env(KMP_DIR) self.txt] w]
set n 0
foreach cell [split $::env(KMP_CELLS) \n] {
    set us [kmp_job_us {kmp_job_load $cell}]
    puts $fh [lindex [cellname list self] 0]
    incr n
    kmp_job_stage loaded $n
}
close $fh
set fh [open [file join $::env(KMP_DIR) cells.txt] w]
foreach c [kmp_job_cells [lindex [split $::env(KMP_CELLS) \n] 0]] { puts $fh $c }
close $fh
if {[info exists ::env(KMP_HANG)]} { after 100000 }
if {[info exists ::env(KMP_BREAK)]} { nosuch_command_kmp }
kmp_job_done $n
puts stdout "AFTER_DONE"
"""


def alive(pid):
    try:
        with open("/proc/%d/status" % pid) as f:
            return "State:\tZ" not in f.read()
    except OSError:
        return False


def lines(path):
    with open(path, encoding="utf-8") as f:
        return [ln.rstrip("\n") for ln in f]


@needs_magic
class Jobs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = tempfile.mkdtemp(prefix="kmp-jobs-backend-")
        cls.script = os.path.join(cls.d, "probe.tcl")
        with open(cls.script, "w") as f:
            f.write(PROBE_TCL)
        # TOP holds B and A; B holds A; EMPTY has nothing in it.
        ly = db.Layout()
        ly.dbu = 0.001
        m1 = ly.layer(*METAL1)
        top = ly.create_cell("TOP")
        a = ly.create_cell("A")
        a.shapes(m1).insert(db.DBox(0, 0, 0.5, 1))
        b = ly.create_cell("B")
        b.shapes(m1).insert(db.DBox(0, 0, 1, 1))
        b.insert(db.DCellInstArray(a.cell_index(), db.DTrans(db.DVector(2, 0))))
        top.insert(db.DCellInstArray(b.cell_index(), db.DTrans()))
        top.insert(db.DCellInstArray(a.cell_index(), db.DTrans(db.DVector(5, 0))))
        empty = ly.create_cell("EMPTY")
        top.insert(db.DCellInstArray(empty.cell_index(), db.DTrans(db.DVector(9, 0))))
        cls.small = os.path.join(cls.d, "small.gds")
        o = db.SaveLayoutOptions()
        o.write_context_info = False
        ly.write(cls.small, o)
        # The review's names, each cell with one 0.10 um metal1 box, written as they are.
        ly = db.Layout()
        ly.dbu = 0.001
        m1 = ly.layer(*METAL1)
        ntop = ly.create_cell("NTOP")
        for i, n in enumerate(NAMES):
            c = ly.create_cell(n)
            c.shapes(m1).insert(db.DBox(0, 0, 0.10, 1.0))
            ntop.insert(db.DCellInstArray(c.cell_index(), db.DTrans(db.DVector(i * 5.0, 0))))
        empty = ly.create_cell("EMPTY")
        ntop.insert(db.DCellInstArray(empty.cell_index(), db.DTrans(db.DVector(0, 10))))
        cls.names_layout = ly
        cls.names = os.path.join(cls.d, "names.gds")
        ly.write(cls.names, o)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.d, ignore_errors=True)

    def run_probe(self, gds, cells, timeout=120, **env):
        e = {"KMP_CELLS": "\n".join(cells)}
        e.update(env)
        job = jobs.MagicJob(CFG, "drc", self.script, env=e, files={"in.gds": gds}, timeout=timeout)
        job.start()
        pid = job.pid
        r = job.wait()
        for _ in range(50):
            if not alive(pid):
                break
            time.sleep(0.1)
        self.assertFalse(alive(pid), "Magic %d still runs after its job" % pid)
        return r

    def test_a_small_cell_and_the_scale(self):
        r = self.run_probe(self.small, ["TOP", "B"])
        self.assertTrue(r.ok, "%s\n%s" % (r.error, "\n".join(r.stdout[-20:])))
        self.assertAlmostEqual(r.scale, 0.005, places=6)
        self.assertEqual(r.done, 2)
        self.assertEqual(r.stages, [("reading", 0), ("loaded", 1), ("loaded", 2)])
        self.assertEqual(lines(r.path("self.txt")), ["TOP", "B"])
        # Every cell under TOP, children before parents, then TOP.
        order = lines(r.path("cells.txt"))
        self.assertEqual(sorted(order), ["A", "B", "EMPTY", "TOP"])
        self.assertLess(order.index("A"), order.index("B"))
        self.assertEqual(order[-1], "TOP")
        self.assertNotIn("AFTER_DONE", r.stdout)

    def test_kmp_job_load_refuses_what_magic_mishandles(self):
        for name, why in sorted(FAILS.items()):
            gds = self.small if name == "EMPTY" else self.names
            r = self.run_probe(gds, [name])
            self.assertFalse(r.ok, name)
            self.assertIsNotNone(r.error, name)
            self.assertIn(why, r.error, name)
            self.assertNotIn("AFTER_DONE", r.stdout, name)
            self.assertEqual(r.stages, [("reading", 0)], name)
        r = self.run_probe(self.names, LOADS)
        self.assertTrue(r.ok, r.error)
        self.assertEqual(lines(r.path("self.txt")), LOADS)

    def test_every_name_loads_after_the_export(self):
        out = os.path.join(self.d, "export.gds")
        er = export_cell(self.names_layout, "NTOP", out, None)
        r = self.run_probe(out, [er.name_map[n] for n in NAMES + ["NTOP"]])
        self.assertTrue(r.ok, r.error)
        self.assertEqual(lines(r.path("self.txt")), [er.name_map[n] for n in NAMES + ["NTOP"]])

    def test_a_timeout_leaves_no_magic(self):
        t = time.monotonic()
        r = self.run_probe(self.small, ["TOP"], timeout=3, KMP_HANG="1")
        self.assertLess(time.monotonic() - t, 60)
        self.assertFalse(r.ok)
        self.assertEqual(r.error, "timed out after 3 s")
        self.assertEqual(r.stages[-1], ("loaded", 1))

    def test_cancel_leaves_no_magic(self):
        job = jobs.MagicJob(CFG, "drc", self.script, env={"KMP_CELLS": "TOP", "KMP_HANG": "1"},
                            files={"in.gds": self.small}, timeout=120)
        job.start()
        for _ in range(600):
            if job.stage == ("loaded", 1):
                break
            self.assertIsNone(job.poll())
            time.sleep(0.05)
        self.assertEqual(job.stage, ("loaded", 1))
        job.cancel()
        r = job.wait()
        self.assertEqual(r.error, "cancelled")
        for _ in range(50):
            if not alive(job.pid):
                break
            time.sleep(0.1)
        self.assertFalse(alive(job.pid))

    def test_two_jobs_on_one_key_at_once(self):
        # Two jobs on one key each run in a directory of their own, so neither
        # reads the other's in.gds (design-0.6.md 2.3). A waits 1.5 s before it
        # reads its file; B, on another file, starts meanwhile and ends first.
        key = jobs.job_cache_key("two-at-once", "drc", {"test": self.id()}, CFG)
        jd = jobs.job_dir_for(CFG, "drc", key)
        a = jobs.MagicJob(CFG, "drc", self.script, env={"KMP_CELLS": "TOP\nB", "KMP_WAIT": "1500"},
                          files={"in.gds": self.small}, timeout=120, job_dir=jd).start()
        time.sleep(0.3)
        b = jobs.MagicJob(CFG, "drc", self.script, env={"KMP_CELLS": "\n".join(LOADS)},
                          files={"in.gds": self.names}, timeout=120, job_dir=jd).start()
        running_in_key_dir = os.path.exists(jd)
        rb = b.wait()
        ra = a.wait()
        self.assertTrue(ra.ok, ra.error)
        self.assertTrue(rb.ok, rb.error)
        self.assertEqual(lines(ra.path("self.txt")), ["TOP", "B"])
        self.assertEqual(sorted(lines(ra.path("cells.txt"))), ["A", "B", "EMPTY", "TOP"])
        self.assertEqual(lines(rb.path("self.txt")), LOADS)
        self.assertFalse(running_in_key_dir, "a job ran in the key's directory")
        # The first to end has the key's directory, whole; the other keeps its own.
        self.assertEqual(rb.dir, jd)
        self.assertNotEqual(ra.dir, jd)
        self.assertTrue(os.path.basename(ra.dir).startswith(jobs.TMP_PREFIX), ra.dir)
        with open(os.path.join(jd, "job.json")) as f:
            self.assertIn('"state": "done"', f.read())
        self.assertEqual(jobs.release([ra.dir, rb.dir]), [ra.dir])
        self.assertTrue(os.path.isfile(os.path.join(jd, "self.txt")))

    def test_a_tcl_error_is_a_failed_job_not_a_hang(self):
        t = time.monotonic()
        r = self.run_probe(self.small, ["TOP"], timeout=120, KMP_BREAK="1")
        self.assertLess(time.monotonic() - t, 60)
        self.assertFalse(r.ok)
        self.assertIn("without KMP_JOB_DONE", r.error)
        self.assertIn("nosuch_command_kmp", r.error)


if __name__ == "__main__":
    unittest.main()
