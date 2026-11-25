import os
import tempfile
import unittest

from tests.unit._util import REPO  # noqa: F401
from klayout_magic_pcells.config import Config, ConfigError, SHIPPED_MANIFEST


def write_ini(text):
    d = tempfile.mkdtemp()
    p = os.path.join(d, "config.ini")
    with open(p, "w") as f:
        f.write(text)
    return p


class ConfigPrecedence(unittest.TestCase):
    def test_defaults(self):
        c = Config.load(env={"PATH": "/nonexistent", "HOME": "/home/x"}, config_path="/nonexistent.ini")
        self.assertEqual(c.magic, "/foss/tools/bin/magic")
        self.assertEqual(c.pdk_root, "/foss/pdks")
        self.assertEqual(c.pdk, "sky130A")
        self.assertEqual(c.magicrc, "/foss/pdks/sky130A/libs.tech/magic/sky130A.magicrc")
        self.assertEqual(c.cache_dir, "/home/x/.cache/klayout-magic-pcells")
        self.assertTrue(c.cache_enabled)
        self.assertEqual(c.backend, "server")
        self.assertEqual(c.timeout, 30.0)
        self.assertFalse(c.lazy)
        self.assertEqual(c.manifest, SHIPPED_MANIFEST)
        self.assertIsNone(c.log)

    def test_env_beats_ini_beats_default(self):
        ini = write_ini("[kmp]\nmagic = /ini/magic\npdk_root = /ini/pdks\ntimeout = 7\n")
        c = Config.load(env={"KMP_MAGIC": "/env/magic", "HOME": "/h"}, config_path=ini)
        self.assertEqual(c.magic, "/env/magic")
        self.assertEqual(c.sources["magic"], "env KMP_MAGIC")
        self.assertEqual(c.pdk_root, "/ini/pdks")
        self.assertIn("[kmp] pdk_root", c.sources["pdk_root"])
        self.assertEqual(c.timeout, 7.0)
        self.assertEqual(c.magicrc, "/ini/pdks/sky130A/libs.tech/magic/sky130A.magicrc")

    def test_xdg_dirs(self):
        c = Config.load(env={"XDG_CACHE_HOME": "/xc", "HOME": "/h"}, config_path="/nope")
        self.assertEqual(c.cache_dir, "/xc/klayout-magic-pcells")
        d = tempfile.mkdtemp()
        os.makedirs(os.path.join(d, "klayout-magic-pcells"))
        with open(os.path.join(d, "klayout-magic-pcells", "config.ini"), "w") as f:
            f.write("[kmp]\ncache = 0\n")
        c = Config.load(env={"XDG_CONFIG_HOME": d, "HOME": "/h"})
        self.assertFalse(c.cache_enabled)

    def test_pdk_variable_is_ignored(self):
        c = Config.load(env={"PDK": "ihp-sg13g2", "HOME": "/h"}, config_path="/nope")
        self.assertEqual(c.pdk, "sky130A")

    def test_unsupported_pdk(self):
        with self.assertRaises(ConfigError):
            Config.load(env={"KMP_PDK": "gf180mcuC", "HOME": "/h"}, config_path="/nope")

    def test_pdk_selection(self):
        d = tempfile.mkdtemp()
        for p in ("sky130A", "ihp-sg13g2"):
            os.makedirs(os.path.join(d, p, "libs.tech", "magic"))
            open(os.path.join(d, p, "libs.tech", "magic", p + ".magicrc"), "w").close()
        env = {"HOME": "/h", "PDK_ROOT": d}
        # auto: the supported PDKs installed under PDK_ROOT
        c = Config.load(env=env, config_path="/nope")
        self.assertEqual(c.pdks, ["sky130A", "ihp-sg13g2"])
        self.assertEqual(c.pdk, "sky130A")
        # KMP_PDK alone selects one PDK, as in version 0.2
        c = Config.load(env=dict(env, KMP_PDK="ihp-sg13g2"), config_path="/nope")
        self.assertEqual(c.pdks, ["ihp-sg13g2"])
        self.assertEqual(c.library_name, "sg13g2_magic")
        self.assertEqual(c.magicrc, os.path.join(d, "ihp-sg13g2/libs.tech/magic/ihp-sg13g2.magicrc"))
        self.assertTrue(c.manifest.endswith("manifest-ihp-sg13g2.json"))
        # an explicit list keeps a missing or unknown PDK, to fail for that PDK alone
        c = Config.load(env=dict(env, KMP_PDKS="gf180mcuD, sky130A gf180mcuC"), config_path="/nope")
        self.assertEqual(c.pdks, ["gf180mcuD", "sky130A"])
        self.assertIn("gf180mcuC", c.pdk_errors)
        g = c.for_pdk("gf180mcuD")
        self.assertTrue(g.problems())
        self.assertIn("KMP_MAGICRC_GF180MCUD", " ".join(g.problems()))
        self.assertEqual(c.pdk, "sky130A")

    def test_per_pdk_settings(self):
        ini = write_ini("[kmp]\npdks = sky130A, ihp-sg13g2\n[kmp:ihp-sg13g2]\nmagicrc = /ini/ihp.rc\n")
        c = Config.load(env={"HOME": "/h", "KMP_MANIFEST_SKY130A": "/env/m.json",
                             "KMP_MAGICRC": "/env/generic.rc"}, config_path=ini)
        self.assertEqual(c.pdks, ["sky130A", "ihp-sg13g2"])
        self.assertEqual(c.manifest, "/env/m.json")
        self.assertEqual(c.magicrc, "/env/generic.rc")       # unqualified: KMP_PDK's PDK only
        i = c.for_pdk("ihp-sg13g2")
        self.assertEqual(i.magicrc, "/ini/ihp.rc")
        self.assertIn("[kmp:ihp-sg13g2]", i.sources["magicrc"])
        self.assertTrue(i.manifest.endswith("manifest-ihp-sg13g2.json"))

    def test_bad_values(self):
        for env in ({"KMP_TIMEOUT": "soon"}, {"KMP_TIMEOUT": "-1"}, {"KMP_CACHE": "maybe"},
                    {"KMP_BACKEND": "remote"}):
            env["HOME"] = "/h"
            with self.assertRaises(ConfigError, msg=str(env)):
                Config.load(env=env, config_path="/nope")

    def test_lazy_follows_backend(self):
        c = Config.load(env={"KMP_BACKEND": "oneshot", "HOME": "/h"}, config_path="/nope")
        self.assertTrue(c.lazy)
        c = Config.load(env={"KMP_BACKEND": "oneshot", "KMP_LAZY": "0", "HOME": "/h"}, config_path="/nope")
        self.assertFalse(c.lazy)

    def test_problems_name_the_variable(self):
        c = Config.load(env={"KMP_MAGIC": "/no/magic", "PDK_ROOT": "/no/pdks", "HOME": "/h"},
                        config_path="/nope")
        text = " ".join(c.problems())
        self.assertIn("KMP_MAGIC", text)
        self.assertIn("PDK_ROOT", text)


class JobSettings(unittest.TestCase):
    """The 0.6 settings: Magic DRC style and mode, the job timeout, netgen,
    its per-PDK setup file and the menu."""

    def test_defaults(self):
        c = Config.load(env={"PATH": "/nonexistent", "HOME": "/h"}, config_path="/nonexistent.ini")
        self.assertEqual(c.drc_style, "drc(full)")
        self.assertEqual(c.drc_mode, "hierarchical")
        self.assertEqual(c.job_timeout, 1800.0)
        self.assertEqual(c.netgen, "netgen")
        self.assertEqual(c.sources["netgen"], "default (netgen on PATH)")
        self.assertTrue(c.menu)
        self.assertEqual(c.netgen_setup, "/foss/pdks/sky130A/libs.tech/netgen/sky130A_setup.tcl")
        g = c.for_pdk("ihp-sg13g2")
        self.assertEqual(g.netgen_setup, "/foss/pdks/ihp-sg13g2/libs.tech/netgen/ihp-sg13g2_setup.tcl")
        names = [r[0] for r in c.describe()]
        for n in ("drc_style", "drc_mode", "job_timeout", "netgen", "netgen_setup", "menu"):
            self.assertIn(n, names)

    def test_netgen_on_path(self):
        d = tempfile.mkdtemp()
        exe = os.path.join(d, "netgen")
        with open(exe, "w") as f:
            f.write("#!/bin/sh\n")
        os.chmod(exe, 0o755)
        c = Config.load(env={"PATH": d, "HOME": "/h"}, config_path="/nope")
        self.assertEqual(c.netgen, exe)
        self.assertFalse([p for p in c.job_problems() if p.startswith("netgen not found")])

    def test_env_beats_ini(self):
        ini = write_ini("[kmp]\ndrc_style = drc(fast)\ndrc_mode = flat\njob_timeout = 60\nmenu = 0\n"
                        "netgen = /ini/netgen\n")
        c = Config.load(env={"HOME": "/h", "KMP_DRC_MODE": "hierarchical", "KMP_JOB_TIMEOUT": "5.5"},
                        config_path=ini)
        self.assertEqual((c.drc_style, c.drc_mode, c.job_timeout, c.menu, c.netgen),
                         ("drc(fast)", "hierarchical", 5.5, False, "/ini/netgen"))
        self.assertEqual(c.sources["drc_mode"], "env KMP_DRC_MODE")
        self.assertIn("[kmp] drc_style", c.sources["drc_style"])
        c = Config.load(env={"HOME": "/h", "KMP_DRC_STYLE": "drc(routing)", "KMP_MENU": "1"}, config_path=ini)
        self.assertEqual((c.drc_style, c.drc_mode, c.menu), ("drc(routing)", "flat", True))

    def test_per_pdk_netgen_setup(self):
        ini = write_ini("[kmp]\npdks = sky130A, gf180mcuD, ihp-sg13g2\n"
                        "[kmp:gf180mcuD]\nnetgen_setup = /ini/gf.tcl\n")
        c = Config.load(env={"HOME": "/h", "KMP_NETGEN_SETUP_IHP_SG13G2": "/env/ihp.tcl",
                             "KMP_NETGEN_SETUP": "/env/generic.tcl"}, config_path=ini)
        self.assertEqual(c.netgen_setup, "/env/generic.tcl")   # unqualified: KMP_PDK's PDK only
        self.assertEqual(c.for_pdk("gf180mcuD").netgen_setup, "/ini/gf.tcl")
        self.assertIn("[kmp:gf180mcuD] netgen_setup", c.for_pdk("gf180mcuD").sources["netgen_setup"])
        i = c.for_pdk("ihp-sg13g2")
        self.assertEqual(i.netgen_setup, "/env/ihp.tcl")
        self.assertEqual(i.sources["netgen_setup"], "env KMP_NETGEN_SETUP_IHP_SG13G2")

    def test_bad_values(self):
        for env in ({"KMP_DRC_MODE": "per-cell"}, {"KMP_DRC_MODE": "tiled"}, {"KMP_JOB_TIMEOUT": "0"},
                    {"KMP_JOB_TIMEOUT": "later"}, {"KMP_JOB_TIMEOUT": "nan"}, {"KMP_MENU": "maybe"}):
            env["HOME"] = "/h"
            with self.assertRaises(ConfigError, msg=str(env)):
                Config.load(env=env, config_path="/nope")
        with self.assertRaises(ConfigError) as cm:
            Config.load(env={"HOME": "/h", "KMP_DRC_MODE": "per-cell"}, config_path="/nope")
        self.assertIn("hierarchical", str(cm.exception))

    def test_missing_netgen_is_a_job_problem_only(self):
        c = Config.load(env={"HOME": "/h", "KMP_NETGEN": "/no/netgen", "PDK_ROOT": "/no/pdks"},
                        config_path="/nope")
        text = " ".join(c.job_problems())
        self.assertIn("KMP_NETGEN", text)
        self.assertIn("KMP_NETGEN_SETUP_SKY130A", text)
        self.assertNotIn("netgen", " ".join(c.problems()))


if __name__ == "__main__":
    unittest.main()
