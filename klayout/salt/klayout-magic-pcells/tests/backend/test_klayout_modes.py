"""The package in the KLayout binary: -b with -rm, and Salt autorun under -zz.

-zz runs autorun macros the way the GUI does; it is the closest headless
check of "the library loads in the GUI". The GUI itself is not driven here.
"""

import os
import shutil
import subprocess
import tempfile
import textwrap
import time
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LYM = os.path.join(REPO, "pymacros", "klayout_magic_pcells.lym")

PROBE = textwrap.dedent("""
    import klayout.db as db
    lib = db.Library.library_by_name("sky130_magic")
    print("LIB", lib is not None)
    try:
        import klayout_magic_pcells as kmp
        from klayout_magic_pcells.config import LIBRARY_NAMES
        print("IMPORT ok")
        print("LIBS", " ".join(n for n in LIBRARY_NAMES.values() if db.Library.library_by_name(n)))
        if lib is not None:
            print("PIDS", " ".join(str(st.server.pid) for st in kmp.states.values() if st.server))
            ly = db.Layout()
            c = ly.create_cell("sky130_fd_pr__pfet_01v8", "sky130_magic", {"nf": 2})
            print("CELL", c.display_title(), c.dbbox())
            print("PCELLS", len(lib.layout().pcell_names()))
            for pdk, dev in (("ihp-sg13g2", "via1"), ("gf180mcuD", "nfet_03v3")):
                l2 = db.Library.library_by_name(LIBRARY_NAMES[pdk])
                if l2 is not None:
                    c = ly.create_cell(dev, l2.name(), {})
                    print("CELL2", c.display_title(), c.dbbox())
    except ImportError as e:
        print("IMPORT failed", e)
""")


def have_klayout():
    return shutil.which("klayout") is not None and shutil.which("magic") is not None


def alive(pid):
    try:
        with open("/proc/%d/status" % pid) as f:
            return "State:\tZ" not in f.read()
    except OSError:
        return False


@unittest.skipUnless(have_klayout(), "klayout or magic is not on PATH")
@unittest.skipUnless((os.environ.get("KMP_PDK") or "sky130A") == "sky130A",
                     "runs once, in the sky130A pass")
class KLayoutModes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="kmp-modes-")
        self.probe = os.path.join(self.tmp, "probe.py")
        with open(self.probe, "w") as f:
            f.write(PROBE)
        # Every installed PDK registers (KMP_PDKS unset: auto).
        self.env = dict(os.environ, KMP_CACHE_DIR=os.path.join(self.tmp, "cache"))
        for k in ("KMP_PDKS", "KMP_PDK"):
            self.env.pop(k, None)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_kl(self, args, env=None):
        p = subprocess.run(["klayout"] + args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           env=env or self.env, timeout=180, stdin=subprocess.DEVNULL)
        return p.returncode, p.stdout.decode(errors="replace")

    def pids_of(self, text):
        for line in text.splitlines():
            if line.startswith("PIDS "):
                return [int(x) for x in line.split()[1:]]
        return []

    def test_batch_with_rm_registers_and_magic_exits_with_klayout(self):
        rc, text = self.run_kl(["-b", "-rm", LYM, "-r", self.probe])
        self.assertEqual(rc, 0, text)
        self.assertIn("LIB True", text)
        self.assertRegex(text, r"CELL sky130_magic\.pfet_01v8\(w=\S+ l=\S+ nf=2\)")
        self.assertIn("PCELLS 73", text)
        self.assertIn("LIBS sky130_magic gf180mcu_magic sg13g2_magic sg13cmos5l_magic", text)
        self.assertIn("CELL2 sg13g2_magic.via1(w=0.2 h=0.2)", text)
        self.assertIn("CELL2 gf180mcu_magic.nfet_03v3(", text)
        pids = self.pids_of(text)
        self.assertEqual(len(pids), 4, text)
        for _ in range(30):
            if not any(alive(p) for p in pids):
                break
            time.sleep(0.1)
        self.assertFalse(any(alive(p) for p in pids), "Magic outlived klayout -b")

    def salt_env(self):
        home = os.path.join(self.tmp, "home")
        os.makedirs(os.path.join(home, "salt"), exist_ok=True)
        link = os.path.join(home, "salt", "klayout-magic-pcells")
        if not os.path.lexists(link):
            os.symlink(REPO, link)
        return dict(self.env, KLAYOUT_HOME=home, KLAYOUT_PATH=home)

    def test_batch_without_rm_does_not_register(self):
        # K4: -b skips autorun macros, but a Salt package's python/ is on sys.path.
        rc, text = self.run_kl(["-b", "-r", self.probe], env=self.salt_env())
        self.assertIn("LIB False", text)
        self.assertIn("IMPORT ok", text)

    def test_salt_package_autoruns_under_zz(self):
        rc, text = self.run_kl(["-zz", "-r", self.probe], env=self.salt_env())
        self.assertEqual(rc, 0, text)
        self.assertIn("LIB True", text)
        self.assertIn("PCELLS 73", text)
        self.assertIn("LIBS sky130_magic gf180mcu_magic sg13g2_magic sg13cmos5l_magic", text)


if __name__ == "__main__":
    unittest.main()
