"""Backend tests of the generated-layer check (layercheck.py) and the port
check (portcheck.py), on the PDK that KMP_PDK names, with Magic. Run once
per PDK:

    KMP_PDK=sky130A KMP_PDKS=sky130A python3 -m unittest tests.backend.test_layers_backend

The cases come from the case suite (tests/cases/build.py), built into a
temporary folder, with the Magic-written row written by Magic itself.
Skipped when Magic, the PDK or the klayout module is missing.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _p in (REPO, os.path.join(REPO, "python")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from klayout_magic_pcells.config import Config  # noqa: E402

try:
    import klayout.db as db
    from klayout_magic_pcells import export, jobs, layercheck, markers, pdkdata, portcheck
except ImportError:
    db = None

CACHE = tempfile.mkdtemp(prefix="kmp-layers-cache-")
try:
    CFG = Config.load(env=dict(os.environ, KMP_CACHE_DIR=CACHE))
    HAVE_MAGIC = not CFG.problems()
except Exception:
    HAVE_MAGIC = False
needs_magic = unittest.skipUnless(HAVE_MAGIC and db is not None, "Magic, the PDK or the klayout module is missing")
PDK = CFG.pdk if HAVE_MAGIC else "sky130A"

# GAPS F1 positives (design-0.6.md 3.3), with the layer F1 must name.
F1_POSITIVES = {
    "sky130A": {"a_nsdm_flush": "nsdm", "c_npc_narrow": "npc", "i_hvtp_w030": "hvtp"},
    "gf180mcuD": {"NP_flush": "nplus", "NP5a_ov010": "nplus", "PP5_ov0": "pplus", "DG_small": "dualgate"},
    "ihp-sg13g2": {"H_pmos_psdflush": "psd"},
    "ihp-sg13cmos5l": {"u_pSD.c": "psd", "u_pSD.i": "psd", "g_hv_tgo_small": "thkox"},
}
# GAPS F2 cases (design-0.6.md 3.3): a drawn gate Magic reads as another device, two, or none.
F2_CASES = {
    "sky130A": ["w_no_nwell", "d_both_implants", "a_no_nsdm", "d_nsdm_half", "i_hvtp_half"],
    "gf180mcuD": ["NP_missing", "NWmiss_pfet", "NPPP_both", "DG_partial"],
    "ihp-sg13g2": ["H_pmos_nopsd", "H_nmos_psdover", "H_pmos_nowell"],
    "ihp-sg13cmos5l": ["g_nopsd_pmos", "g_psd_on_nmos"],
}
# F3 (dropped cuts and conductor), F4 (added conductor), F5 (redrawn cuts).
F3_CASES = {"sky130A": ["c_no_li_over_licon", "l_pin_only_li"], "gf180mcuD": ["CO11_cont_field"],
            "ihp-sg13g2": ["Cnt_g", "V1_a"], "ihp-sg13cmos5l": ["m_V1.a", "u_Cnt.h"]}
F4_CASES = {"sky130A": ["s_via_m1_encl", "l_pin_only_li"], "gf180mcuD": [], "ihp-sg13g2": [],
            "ihp-sg13cmos5l": ["u_Pin.e", "u_V1.noM2"]}
F5_CASES = {"sky130A": ["c_licon_020"], "gf180mcuD": ["CO2a_s022"], "ihp-sg13g2": [],
            "ihp-sg13cmos5l": ["u_V1.b1"]}
# Port variants (design-0.6.md 3.4): case -> the P findings (as a sorted set).
PORT_CASES = {
    "sky130A": {"inv": [], "inv_no_text": ["P4"], "inv_pin_only_li": ["P5"]},
    "gf180mcuD": {"inv": [], "inv_no_text": []},
    "ihp-sg13g2": {"inv": [], "inv_no_text": []},
    "ihp-sg13cmos5l": {"inv": [], "port_lbl": ["P1"], "port_txt": ["P2"], "port_m1": ["P2"],
                       "port_pin": ["P3"], "port_txt_pin": [], "port_pin_box": ["P3"], "u_Pin.e": ["P2", "P5"]},
}

# Cells Magic reads nothing in (only implants or markers, no diffusion or
# poly under them): layers and ports --magic give a finding with status 1
# (design-0.6.md 3.3), not a failed job; the item names the cell's layer.
READS_NOTHING = {"sky130A": {"s_hvtp_alone": "78/44 (hvtp.drawing)", "s_nsdm_alone": "93/44 (nsdm.drawing)",
                             "s_npc_alone": "95/20 (npc.drawing)", "s_lvtn_alone": "125/44 (lvtn.drawing)"},
                 "ihp-sg13g2": {"EXTB_a": "111/0 (EXTBlock.drawing)", "pSD_a": "14/0 (pSD.drawing)"}}

# Where Magic's flatten of its hierarchical reading (what F2 uses,
# design-0.6.md 3.3) extracts other devices than its hierarchical
# extraction (the review's measurement, cases.json's expect): measured here,
# 2026-11-23 (design-0.6.md 7). The export's cross-cell finding still fires
# on these cases.
FLATTEN_DIFFERS = {"gf180mcuD": {"C_PMOS_all_h": {"pfet_03v3": 1}}}

OUT = None
CASES = {}
RESULTS = {}


def setUpModule():
    global OUT, CASES
    if not (HAVE_MAGIC and db is not None):
        return
    from tests.cases import build as cbuild
    OUT = tempfile.mkdtemp(prefix="kmp-layers-cases-")
    _, warnings = cbuild.build(PDK, OUT, ["gaps", "hier", "inverters", "controls"], pcell=False, magic_row=True)
    if warnings:
        raise RuntimeError("the case suite did not build: %s" % warnings)
    with open(os.path.join(OUT, "cases.json"), encoding="utf-8") as f:
        CASES = dict((c["name"], c) for c in json.load(f)["cases"])


def tearDownModule():
    shutil.rmtree(CACHE, ignore_errors=True)
    if OUT:
        shutil.rmtree(OUT, ignore_errors=True)


def layers(name):
    """The layers outcome of a case, run once per module."""
    if name not in RESULTS:
        c = CASES[name]
        ly = export.load_layout(os.path.join(OUT, c["file"]))
        task = layercheck.prepare(ly, ly.cell(c["top"]), CFG, pdkdata.load(PDK), {"no_cache": True})
        RESULTS[name] = task.wait()
    return RESULTS[name]


def ports(name, magic=False):
    c = CASES[name]
    ly = export.load_layout(os.path.join(OUT, c["file"]))
    return portcheck.prepare(ly, ly.cell(c["top"]), CFG, pdkdata.load(PDK), {"magic": magic, "no_cache": True}).wait()


def texts(out, key):
    return [f["text"] for f in out.findings.get(key, [])]


@needs_magic
class NegativeControls(unittest.TestCase):
    """The negative controls (design-0.6.md 3.3): the standard cells, their
    row, the row Magic wrote, and the hand inverter give no F1 to F4
    finding. Asserted here, not in a baseline."""

    def test_controls_give_no_f1_to_f4(self):
        names = [n for n, c in CASES.items() if c.get("negative_control")]
        self.assertEqual(len(names), 10, names)
        self.assertTrue(os.path.exists(os.path.join(OUT, CASES["row_magic"]["file"])))
        for n in names:
            with self.subTest(case=n):
                out = layers(n)
                self.assertNotEqual(out.status, 2, out.summary)
                for k in ("F1", "F2", "F3", "F4"):
                    self.assertEqual(texts(out, k), [], "%s on the negative control %s" % (k, n))
                self.assertTrue(out.findings.get("devices") or "tap" in n or "filltie" in n or "conb" in n,
                                "no device extracted from %s" % n)


@needs_magic
class Findings(unittest.TestCase):
    def test_f1_positives_fire(self):
        info = layercheck.load_devices(PDK).get("f1") != "check"
        for n, layer in F1_POSITIVES[PDK].items():
            with self.subTest(case=n):
                out = layers(n)
                f1 = [f for f in out.findings["F1"] if f["layer"] == layer]
                self.assertTrue(f1, "no F1 on %s in %s: %s" % (layer, n, out.summary))
                self.assertTrue(all(f["info"] == info for f in f1))
                self.assertIn("Magic draws %s" % layer, f1[0]["text"])
                self.assertEqual(out.status, 0 if info else 1)

    def test_f2_cases_fire(self):
        for n in F2_CASES[PDK]:
            with self.subTest(case=n):
                out = layers(n)
                self.assertTrue(out.findings["F2"], "no F2 in %s: %s" % (n, out.summary))
                self.assertEqual(out.status, 1)

    def test_f3_f4_f5_cases(self):
        for key, table in (("F3", F3_CASES), ("F4", F4_CASES), ("F5", F5_CASES)):
            for n in table[PDK]:
                with self.subTest(check=key, case=n):
                    out = layers(n)
                    self.assertTrue(out.findings[key], "no %s in %s: %s" % (key, n, out.summary))

    def test_f5_alone_is_information(self):
        for n in F5_CASES[PDK]:
            out = layers(n)
            if not any(out.findings[k] for k in ("F1", "F2", "F3", "F4")):
                self.assertEqual(out.status, 0, out.summary)

    def test_hier_set_reports_magics_hierarchical_reading(self):
        """Magic decides devices inside each cell (design-0.6.md 3.1); F2 must
        report the device Magic's hierarchical reading changed or lost, and the
        device list must be Magic's (cases.json's expect, from the review's
        measurement)."""
        flat = dict((c["top"], c) for c in CASES.values() if c["set"] == "hier" and c["name"].endswith("_flat"))
        for n, c in sorted(CASES.items()):
            if c["set"] != "hier":
                continue
            with self.subTest(case=n):
                out = layers(n)
                self.assertNotEqual(out.status, 2, out.summary)
                got = {}
                for d in out.findings["devices"]:
                    got[d["model"]] = got.get(d["model"], 0) + 1
                want = FLATTEN_DIFFERS.get(PDK, {}).get(n, c["expect"]["magic"]["extract"])
                self.assertEqual(got, want, "Magic's devices in %s" % n)
                if n in FLATTEN_DIFFERS.get(PDK, {}):
                    self.assertGreater(out.rdb.count(markers.CAT_CROSS_CELL), 0, out.summary)
                    self.assertEqual(out.status, 1)
                    continue
                if n.endswith("_flat"):
                    self.assertEqual(texts(out, "F2"), [])
                    continue
                base = flat[n.rsplit("_", 2)[0]]
                if want != base["expect"]["magic"]["extract"]:
                    f2 = texts(out, "F2")
                    self.assertTrue(f2, "no F2 in %s" % n)
                    self.assertTrue(any("Magic reads cell" in t for t in f2), f2)
                else:
                    self.assertEqual(texts(out, "F2"), [])

    def test_rdb_and_cache(self):
        n = list(F1_POSITIVES[PDK])[0]
        c = CASES[n]
        ly = export.load_layout(os.path.join(OUT, c["file"]))
        cfg = Config.load(env=dict(os.environ, KMP_CACHE_DIR=tempfile.mkdtemp(prefix="cache-", dir=OUT)))
        t1 = layercheck.prepare(ly, ly.cell(c["top"]), cfg, pdkdata.load(PDK), {})
        o1 = t1.wait()
        t2 = layercheck.prepare(ly, ly.cell(c["top"]), cfg, pdkdata.load(PDK), {})
        o2 = t2.wait()
        self.assertFalse(t1.cached)
        self.assertTrue(t2.cached)
        self.assertEqual(o1.summary, o2.summary)
        path = os.path.join(OUT, "f1.lyrdb")
        o2.rdb.save(path)
        self.assertGreater(markers.load(path).num_items(), 0)
        # The cached run's directory is the key's; "job" is its old name.
        self.assertEqual(o2.files["job_dir"], o1.files["job_dir"])
        self.assertEqual(o2.files["job"], o2.files["job_dir"])
        self.assertFalse(os.path.basename(o1.files["job_dir"]).startswith("tmp-"))
        self.assertEqual(jobs.release(o2), [])

    def test_no_cache_runs_in_a_tmp_dir_that_release_removes(self):
        n = list(F1_POSITIVES[PDK])[0]
        c = CASES[n]
        ly = export.load_layout(os.path.join(OUT, c["file"]))
        for cfg, opts in ((CFG, {"no_cache": True}),
                          (Config.load(env=dict(os.environ, KMP_CACHE_DIR=CACHE, KMP_CACHE="0")), {})):
            out = layercheck.prepare(ly, ly.cell(c["top"]), cfg, pdkdata.load(PDK), opts).wait()
            self.assertNotEqual(out.status, 2, out.summary)
            jd = out.files["job_dir"]
            self.assertEqual(os.path.dirname(jd), os.path.join(CACHE, "jobs", PDK, "rw"))
            self.assertTrue(os.path.basename(jd).startswith("tmp-"), jd)
            self.assertTrue(os.path.isfile(out.files["rw.gds"]))
            self.assertEqual(jobs.release(out), [jd])
            self.assertFalse(os.path.exists(jd))


@needs_magic
class ReadsNothing(unittest.TestCase):
    def check(self, out, top, layer):
        self.assertEqual(out.status, 1, out.summary)
        self.assertEqual(out.rdb.count(markers.CAT_READS_NOTHING), 1, out.summary)
        self.assertEqual(out.rdb.count(layercheck.CAT_JOB), 0, out.summary)
        (item,) = [f["text"] for f in out.findings["empty"]]
        self.assertTrue(item.startswith("Magic reads nothing in cell %s" % top), item)
        self.assertIn(layer, item)
        self.assertIn(item, out.summary)

    def test_layers_and_ports_on_cells_magic_reads_nothing_in(self):
        cases = READS_NOTHING.get(PDK)
        if not cases:
            self.skipTest("no such gaps case on %s" % PDK)
        for n, layer in cases.items():
            with self.subTest(case=n):
                c = CASES[n]
                out = layers(n)
                self.check(out, c["top"], layer)
                self.assertTrue(os.path.isfile(out.files["export"]), out.files)
                p = ports(n, magic=True)
                self.check(p, c["top"], layer)
                self.assertIsNone(p.magic_ports)
                self.assertNotIn("P8 0", p.summary)
                self.assertIn("P8 did not run", p.summary)


@needs_magic
class Ports(unittest.TestCase):
    def test_port_variants(self):
        for n, want in PORT_CASES[PDK].items():
            with self.subTest(case=n):
                out = ports(n)
                got = sorted(set(f["check"] for f in out.findings["ports"]))
                self.assertEqual(got, want, [f["text"] for f in out.findings["ports"]])

    def test_p8_on_the_inverter(self):
        out = ports("inv", magic=True)
        self.assertNotEqual(out.status, 2, out.summary)
        self.assertEqual(len(out.magic_ports), 4, out.summary)
        self.assertEqual([f for f in out.findings["ports"] if f["check"] == "P8"], [])

    def test_p8_finds_a_text_magic_makes_no_port_of(self):
        if PDK != "ihp-sg13cmos5l":
            self.skipTest("the port variants are drawn on ihp-sg13cmos5l")
        out = ports("u_Pin.e", magic=True)
        self.assertEqual(out.magic_ports, ["A"], out.summary)


@needs_magic
class Data(unittest.TestCase):
    def test_reads_as_types_by_one_magic_read(self):
        """The data file's reads-as layers (design-0.6.md 2.6: ihp-sg13g2 16/0
        digisub, and ihp-sg13cmos5l's, which tools/pdk_data_overrides.json sets
        by analogy) are what Magic reads."""
        data = pdkdata.load(PDK)
        rows = data.layers_by_read("reads-as")
        if not rows:
            self.skipTest("no reads-as layer on %s" % PDK)
        d = tempfile.mkdtemp(prefix="kmp-readsas-", dir=OUT)
        ly = db.Layout()
        ly.dbu = 0.001
        top = ly.create_cell("RA")
        for i, r in enumerate(rows):
            top.shapes(ly.layer(*r["gds"])).insert(db.DBox(i * 5.0, 0, i * 5.0 + 2.0, 2.0))
        gds = os.path.join(d, "ra.gds")
        ly.write(gds)
        tcl = os.path.join(d, "what.tcl")
        with open(tcl, "w") as f:
            f.write("source $::env(KMP_TCL_DIR)/kmp_job_common.tcl\nkmp_job_read $::env(KMP_GDS)\n"
                    "kmp_job_load RA\nselect top cell\nselect area\nset w [what -list]\n"
                    "set f [open [file join $::env(KMP_DIR) what.txt] w]\nputs $f [lindex $w 0]\nclose $f\n"
                    "kmp_job_done 1\n")
        r = jobs.run_job(CFG, "rw", tcl, files={"in.gds": gds}, timeout=120)
        self.assertTrue(r.ok, r.error)
        with open(r.path("what.txt")) as f:
            types = f.read().split()
        for row in rows:
            self.assertIn(row["read"].split(":", 1)[1], types, "Magic read %s as %s" % (row["gds"], types))


@needs_magic
class CommandLine(unittest.TestCase):
    def run_cli(self, *args):
        env = dict(os.environ, PYTHONPATH=os.path.join(REPO, "python"), KMP_CACHE_DIR=CACHE)
        return subprocess.run([sys.executable, "-m", "klayout_magic_pcells"] + list(args), env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=300)

    def test_layers_and_ports_commands(self):
        n = list(F1_POSITIVES[PDK])[0]
        c = CASES[n]
        rdb, js = os.path.join(OUT, "cli.lyrdb"), os.path.join(OUT, "cli.json")
        p = self.run_cli("layers", os.path.join(OUT, c["file"]), "--cell", c["top"], "--pdk", PDK,
                         "-o", rdb, "--json", js)
        info = layercheck.load_devices(PDK).get("f1") != "check"
        self.assertEqual(p.returncode, 0 if info else 1, p.stderr)
        self.assertIn("F1 1", p.stderr.replace("F1 2", "F1 1").replace("F1 3", "F1 1"))
        with open(js) as f:
            doc = json.load(f)
        self.assertTrue(any(x["check"] == "F1" for x in doc["findings"]))
        ctl = CASES["inv_control"]
        p = self.run_cli("layers", os.path.join(OUT, ctl["file"]), "--cell", ctl["top"], "--pdk", PDK)
        self.assertEqual(p.returncode, 0, p.stderr)
        p = self.run_cli("ports", os.path.join(OUT, ctl["file"]), "--cell", ctl["top"], "--pdk", PDK, "--magic")
        self.assertEqual(p.returncode, 0, p.stderr + p.stdout)


if __name__ == "__main__":
    unittest.main()
