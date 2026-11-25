"""Backend tests of extraction and netgen LVS (lvsjob.py, extfile.py,
netgen.py and tcl/kmp_extract.tcl), on the PDK that KMP_PDK names; run once
per PDK. They build the inverters set of the case suite (tests/cases) into a
temporary folder. Skipped when Magic, netgen, the PDK or the klayout module
is missing.

ReadbackTest is the read-back measurement (design-0.6.md 3.2, 6.5): every
device default of the PDK generated with magic::gencell, extracted from
Magic's database, written to GDS by Magic, read back in a fresh Magic and
extracted again, with the harness's netlist-only settings (the review's
method). The differences must be the ones data/readback-<pdk>.json lists.
With KMP_READBACK_WRITE=1 the test writes that file instead:

    KMP_PDK=sky130A KMP_PDKS=sky130A KMP_READBACK_WRITE=1 \\
        python3 -m unittest tests.backend.test_lvs_backend.ReadbackTest
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "python"))
sys.path.insert(0, REPO)

from klayout_magic_pcells.config import Config  # noqa: E402

try:
    from klayout_magic_pcells import markers  # needs the klayout module
except ImportError:
    markers = None

try:
    import klayout.db as db
except ImportError:
    db = None

CACHE = tempfile.mkdtemp(prefix="kmp-lvs-cache-")
try:
    CFG = Config.load(env=dict(os.environ, KMP_CACHE_DIR=CACHE))
    HAVE_MAGIC = not CFG.problems()
    HAVE_NETGEN = HAVE_MAGIC and not CFG.job_problems()
except Exception:
    HAVE_MAGIC = HAVE_NETGEN = False
PDK = CFG.pdk if HAVE_MAGIC else "sky130A"
# KMP_LVS_TEST_OUT keeps the cases and job files for a look afterwards.
KEEP = os.environ.get("KMP_LVS_TEST_OUT")
OUT = KEEP or tempfile.mkdtemp(prefix="kmp-lvs-cases-")


def tearDownModule():
    shutil.rmtree(CACHE, ignore_errors=True)
    if not KEEP:
        shutil.rmtree(OUT, ignore_errors=True)


needs_magic = unittest.skipUnless(HAVE_MAGIC and db is not None,
                                  "Magic, the PDK or the klayout module is missing")
needs_netgen = unittest.skipUnless(HAVE_NETGEN and db is not None,
                                   "Magic, netgen, the PDK or the klayout module is missing")


# -- database extraction against GDS read-back -----------------------------------
# The measurement lives in tests/jobs/readback.py, where the harness's jobs
# step runs it too.

from tests.jobs.readback import measure_readback, readback_rows  # noqa: E402


@needs_magic
class ReadbackTest(unittest.TestCase):
    """The data file lists exactly the device defaults whose GDS read-back
    extracts differently from Magic's database."""

    def test_readback_list(self):
        work = os.path.join(OUT, "readback")
        measured = measure_readback(CFG, work)
        rows = readback_rows(measured)
        unmeasured = [(d, e) for d, mem, back, e in measured if mem is None or (back is None and e)]
        path = os.path.join(REPO, "python", "klayout_magic_pcells", "data", "readback-%s.json" % PDK)
        if os.environ.get("KMP_READBACK_WRITE") == "1":
            old = {}
            if os.path.isfile(path):
                with open(path) as f:
                    old = {r["device"]: r for r in json.load(f).get("devices", [])}
            for r in rows:
                r["note"] = old.get(r["device"], {}).get("note", "")
            doc = {"schema": 1, "pdk": PDK,
                   "method": "every device default through magic::gencell, extracted from Magic's "
                             "database and again after Magic's gds write and a fresh gds read, both with "
                             "the harness's netlist-only settings; tests/backend/test_lvs_backend.py "
                             "ReadbackTest (design-0.6.md 3.2)",
                   "measured": len(measured) - len(unmeasured),
                   "unmeasured": [{"device": d, "why": e} for d, e in unmeasured],
                   "devices": rows}
            with open(path, "w") as f:
                json.dump(doc, f, indent=1, sort_keys=False)
                f.write("\n")
        with open(path) as f:
            listed = json.load(f)
        want = {r["device"]: (r["database"], r["gds"]) for r in listed["devices"]}
        got = {r["device"]: (r["database"], r["gds"]) for r in rows}
        self.assertEqual(sorted(got), sorted(want), "devices whose read-back differs")
        for dev in got:
            self.assertEqual(got[dev], want[dev], dev)
        self.assertEqual(sorted(d for d, _ in unmeasured), sorted(r["device"] for r in listed["unmeasured"]))


# -- the extraction and LVS jobs on the case suite's inverters -------------------

_built = {}


def cases():
    """The inverters set of tests/cases for this PDK, built once: {name: record}."""
    if "cases" not in _built:
        out = os.path.join(OUT, "cases")
        subprocess.run([sys.executable, os.path.join(REPO, "tests", "cases", "build.py"), "--pdk", PDK,
                        "--out", out, "--set", "inverters", "--no-pcell"], check=True,
                       stdout=subprocess.DEVNULL)
        with open(os.path.join(out, "cases.json")) as f:
            recs = json.load(f)["cases"]
        _built["dir"] = out
        _built["cases"] = {r["name"]: r for r in recs if r["set"] == "inverters"}
    return _built["cases"]


def case_paths(name):
    rec = cases()[name]
    return os.path.join(_built["dir"], rec["file"]), os.path.join(_built["dir"], rec["schematic"]), rec["top"]


def load(path, top):
    from klayout_magic_pcells.export import load_layout
    ly = load_layout(path)
    return ly, ly.cell(top)


def run(cmd, path, top, **options):
    from klayout_magic_pcells import lvsjob, pdkdata
    ly, cell = load(path, top)
    opts = dict(options, cmd=cmd, file=path)
    task = lvsjob.prepare(ly, cell, CFG, pdkdata.load(PDK), opts)
    return task, task.start().wait()


def texts_only(src, dst, top):
    """The inverter with its pin boxes removed and every text on a layer that
    names a net in Magic but makes no port (the data file's ports table,
    design-0.6.md 3.4): sky130A
    */5 and IHP */25 texts stay; gf180mcuD's */10 port texts move to */0."""
    from klayout_magic_pcells import pdkdata
    ports = pdkdata.load(PDK).ports()
    pins = {tuple(p) for p in ports["pin"]}
    port_text = {tuple(p) for p in ports["port_text"]}
    ly, cell = load(src, top)
    for li in list(ly.layer_indexes()):
        info = ly.get_info(li)
        key = (info.layer, info.datatype)
        for c in ly.each_cell():
            shapes = c.shapes(li)
            texts = [s.dtext for s in shapes.each(db.Shapes.STexts)]
            if key in port_text and texts:
                tl = ly.layer(info.layer, 0)
                for t in texts:
                    c.shapes(tl).insert(t)
            if key in pins or key in port_text:
                shapes.clear()
    o = db.SaveLayoutOptions()
    o.write_context_info = False
    ly.write(dst, o)


def _ports(spice, name):
    """The pins of ``.subckt name`` in a SPICE file."""
    with open(spice, encoding="utf-8") as f:
        for line in f:
            t = line.split()
            if len(t) > 2 and t[0].lower() == ".subckt" and t[1] == name:
                return [x for x in t[2:] if "=" not in x]
    return []


@needs_netgen
class LvsTest(unittest.TestCase):
    def test_hand_inverter_matches(self):
        path, sch, top = case_paths("inv")
        task, out = run("lvs", path, top, schematic=sch, no_cache=True)
        self.assertEqual(out.status, 0, out.summary)
        self.assertTrue(out.verdict.matched)
        self.assertIn("Circuits match uniquely.", out.verdict.final)
        self.assertEqual(task.schematic_cell, top, "the schematic subcircuit defaults to the cell's name")
        self.assertEqual([f for f in out.findings if f["category"].startswith("netgen/")], [])
        self.assertTrue(os.path.isfile(out.files["report"]))

    def test_open_drain_marks_the_floating_drain(self):
        path, sch, top = case_paths("inv_open_drain")
        task, out = run("lvs", path, top, schematic=sch, no_cache=True)
        self.assertEqual(out.status, 1, out.summary)
        self.assertEqual(out.verdict.final, "Netlists do not match.")
        only = [f for f in out.findings if f["category"] == lvsjob_cat("CAT_LAYOUT_ONLY")]
        self.assertEqual(len(only), 1, out.findings)
        net = only[0]["text"].split(",")[0]
        # The right net: the NMOS drain, which nothing else reaches.
        ext = task.ext.cells[task.export.top]
        nmos = [d for d in ext.devices if d.model in NMOS]
        self.assertEqual(len(nmos), 1)
        self.assertIn(net, nmos[0].terminals)
        self.assertNotIn(net, [p.name for p in ext.ports])
        node = ext.nodes[net]
        x, y = task.ext.um(node.x), task.ext.um(node.y)
        l, b, r, t = only[0]["box"]
        self.assertTrue(l - 1e-3 <= x <= r + 1e-3 and b - 1e-3 <= y <= t + 1e-3, (x, y, only[0]))
        self.assertTrue(r - l > 0.05 and t - b > 0.05, "the marker is the net's diffusion shape, not a dot")
        if PDK == "sky130A":
            self.assertEqual(net, "a_300_260#")
            self.assertAlmostEqual(x, 1.50, 3)
            self.assertAlmostEqual(y, 1.30, 3)
        self.assertGreater(out.rdb.count(lvsjob_cat("CAT_LAYOUT_ONLY")), 0)

    def test_texts_only_fails_pin_matching(self):
        path, sch, top = case_paths("inv")
        dst = os.path.join(OUT, "inv_texts_only.gds")
        texts_only(path, dst, top)
        task, out = run("lvs", dst, top, schematic=sch, no_cache=True)
        self.assertEqual(out.status, 1, out.summary)
        self.assertTrue(out.verdict.pin_errors, out.verdict)
        self.assertIn("Top level cell failed pin matching.", out.verdict.final)
        self.assertTrue([f for f in out.findings if f["category"] == lvsjob_cat("CAT_PINS")])
        # Every schematic pin has an item, also the one on netgen's "(no pins)" row.
        texts = " ".join(f["text"] for f in out.findings if f["category"] == lvsjob_cat("CAT_PINS"))
        for pin in _ports(sch, top):
            self.assertIn("schematic pin %s has no pin in the layout" % pin, texts)

    def test_swapped_texts_fail(self):
        path, sch, top = case_paths("inv_swap")
        task, out = run("lvs", path, top, schematic=sch, no_cache=True)
        self.assertEqual(out.status, 1, out.summary)
        pins = [f for f in out.findings if f["category"] == lvsjob_cat("CAT_PINS")]
        self.assertTrue(any(f["box"] for f in pins), "a layout pin is marked at its port box")

    def test_ports_from_labels(self):
        """--ports-from-labels (port makeall) makes the texts-only inverter match."""
        path, sch, top = case_paths("inv")
        dst = os.path.join(OUT, "inv_texts_only_makeall.gds")
        texts_only(path, dst, top)
        task, out = run("lvs", dst, top, schematic=sch, ports_from_labels=True, no_cache=True)
        self.assertEqual(out.status, 0, out.summary)
        self.assertEqual(out.rdb.count(lvsjob_cat("CAT_PORTS_FROM_LABELS")), 1)

    def test_property_error_inside_a_pcell(self):
        """A device inside a PCell variant that netgen flattened is marked at
        its place in the top cell, through the use transform."""
        out_dir = os.path.join(OUT, "pcell")
        p = subprocess.run([sys.executable, os.path.join(REPO, "tests", "cases", "build.py"), "--pdk", PDK,
                            "--out", out_dir, "--set", "inverters"], stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, universal_newlines=True)
        path = os.path.join(out_dir, "inverters", "inv_pcell.gds")
        self.assertTrue(os.path.isfile(path), p.stdout)
        with open(os.path.join(out_dir, "inverters", "inv_pcell.spice")) as f:
            lines = f.read().splitlines()
        nmos = next(i for i, ln in enumerate(lines) if any(m in ln for m in NMOS))
        lines[nmos] = re.sub(r"(?i)\b(w=)[0-9.]+([a-z]*)", r"\g<1>0.5\2", lines[nmos])
        sch = os.path.join(out_dir, "inv_pcell_w05.spice")
        with open(sch, "w") as f:
            f.write("\n".join(lines) + "\n")
        task, out = run("lvs", path, "inv_pcell", schematic=sch, no_cache=True)
        self.assertEqual(out.status, 1, out.summary)
        self.assertTrue(out.verdict.property_errors, out.verdict)
        props = [f for f in out.findings if f["category"] == lvsjob_cat("CAT_PROPS")]
        self.assertEqual(len(props), 1, out.findings)
        self.assertIn("__kmp_", props[0]["text"])
        self.assertIsNotNone(props[0]["box"], "the device has a place")
        ly, cell = load(path, "inv_pcell")
        l, b, r, t = props[0]["box"]
        cx, cy = (l + r) / 2, (b + t) / 2
        inside = []
        for inst in cell.each_inst():
            if any(m in inst.cell.name for m in NMOS):
                bb = inst.dbbox()
                inside.append(bb.left <= cx <= bb.right and bb.bottom <= cy <= bb.top)
        self.assertEqual(inside, [True], "the marker lies in the NMOS variant's placement")

    def test_two_lvs_runs_on_one_extraction_keep_their_own_reports(self):
        # A cached extraction's directory is shared: netgen used to run in its
        # lvs/ folder, which the next LVS emptied, so the first run's report
        # path then held the second's report.
        path, sch, top = case_paths("inv")
        extra = os.path.join(OUT, "inv_extra_pin.spice")
        with open(sch) as f:
            text = f.read()
        lines = text.splitlines()
        for i, ln in enumerate(lines):
            if ln.lower().startswith(".subckt %s " % top.lower()):
                lines[i] = ln + " KMP_EXTRA"
        with open(extra, "w") as f:
            f.write("\n".join(lines) + "\n")
        _, a = run("lvs", path, top, schematic=sch)
        _, b = run("lvs", path, top, schematic=extra)
        self.assertEqual(a.status, 0, a.summary)
        self.assertEqual(b.status, 1, b.summary)
        self.assertEqual(a.files["job_dir"], b.files["job_dir"], "the second run did not reuse the extraction")
        self.assertNotEqual(a.files["report"], b.files["report"])
        with open(a.files["report"]) as f:
            self.assertNotIn("KMP_EXTRA", f.read())
        with open(b.files["report"]) as f:
            self.assertIn("KMP_EXTRA", f.read())

    @unittest.skipUnless(PDK == "sky130A", "the W 0.36 case is sky130A's")
    def test_w036_property_error(self):
        path, sch, top = case_paths("inv_w036")
        task, out = run("lvs", path, top, schematic=sch, no_cache=True)
        self.assertEqual(out.status, 1, out.summary)
        self.assertEqual(out.verdict.final, "Circuits match uniquely.")
        self.assertTrue(out.verdict.property_errors)
        self.assertIn("netgen: Property errors were found.", out.verdict.reasons)
        props = [f for f in out.findings if f["category"] == lvsjob_cat("CAT_PROPS")]
        self.assertEqual(len(props), 1, out.findings)
        self.assertIn("w: layout 0.36, schematic 0.65", props[0]["text"])
        l, b, r, t = props[0]["box"]
        self.assertTrue(l < 1.35 < r and b < 1.30 + 0.1, props[0])

    def test_cli(self):
        """lvs on the command line: exit status, the .lyrdb, the report and the JSON."""
        path, sch, top = case_paths("inv_open_drain")
        rdb, rep, js = (os.path.join(OUT, "cli." + e) for e in ("lyrdb", "txt", "json"))
        env = dict(os.environ, KMP_CACHE_DIR=CACHE, PYTHONPATH=os.path.join(REPO, "python"))
        p = subprocess.run([sys.executable, "-m", "klayout_magic_pcells", "lvs", path, "--pdk", PDK,
                            "--schematic", sch, "-o", rdb, "--report", rep, "--json", js],
                           env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        self.assertEqual(p.returncode, 1, p.stderr)
        self.assertIn("netgen: Netlists do not match.", p.stderr)
        r = markers.load(rdb)
        self.assertGreater(r.num_items(), 0)
        with open(rep) as f:
            self.assertIn("Final result: Netlists do not match.", f.read())
        with open(js) as f:
            doc = json.load(f)
        self.assertFalse(doc["verdict"]["matched"])
        self.assertTrue(any(x["category"] == lvsjob_cat("CAT_LAYOUT_ONLY") for x in doc["findings"]))
        p = subprocess.run([sys.executable, "-m", "klayout_magic_pcells", "lvs", path, "--pdk", PDK,
                            "--schematic", sch, "--schematic-cell", "nope"],
                           env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        self.assertEqual(p.returncode, 2, p.stderr)
        self.assertIn("no subcircuit nope", p.stderr)


@needs_magic
class ExtractTest(unittest.TestCase):
    def test_port_boxes_hold_their_texts(self):
        """Each port box of the .ext, in um at the job's [cif scale out]
        (design-0.6.md 6.5), holds the GDS text of that name."""
        path, _sch, top = case_paths("inv")
        task, out = run("extract", path, top, no_cache=True)
        self.assertEqual(out.status, 0, out.summary)
        self.assertAlmostEqual(task.ext.unit, 0.005, 6)
        ly, cell = load(path, top)
        texts = {}
        for li in ly.layer_indexes():
            for sh in cell.shapes(li).each(db.Shapes.STexts):
                texts[sh.dtext.string] = (sh.dtext.x, sh.dtext.y)
        ports = task.ext.ports()
        self.assertEqual(sorted(n for n, _b, _t in ports), sorted(texts))
        for name, (l, b, r, t), _typ in ports:
            x, y = texts[name]
            self.assertTrue(l - 1e-4 <= x <= r + 1e-4 and b - 1e-4 <= y <= t + 1e-4,
                            "%s: text at (%.3f, %.3f), port box %s" % (name, x, y, (l, b, r, t)))

    def test_caps_netlist_has_capacitors(self):
        path, _sch, top = case_paths("inv")
        task, out = run("extract", path, top, caps=True, no_cache=True)
        self.assertEqual(out.status, 0, out.summary)
        with open(out.files["netlist"]) as f:
            lines = f.read().splitlines()
        self.assertTrue([ln for ln in lines if ln.startswith("C")], "no C lines with --caps")
        task, out = run("extract", path, top, no_cache=True)
        with open(out.files["netlist"]) as f:
            self.assertFalse([ln for ln in f.read().splitlines() if ln.startswith("C")])

    def test_cache(self):
        path, _sch, top = case_paths("inv")
        run("extract", path, top)
        task, out = run("extract", path, top)
        self.assertEqual(task.stage, ("cached", 0))
        self.assertTrue(os.path.isfile(out.files["netlist"]))

    def test_cli_extract(self):
        path, _sch, top = case_paths("inv")
        dst = os.path.join(OUT, "inv_cli.spice")
        env = dict(os.environ, KMP_CACHE_DIR=CACHE, PYTHONPATH=os.path.join(REPO, "python"))
        p = subprocess.run([sys.executable, "-m", "klayout_magic_pcells", "extract", path, "--pdk", PDK,
                            "-o", dst, "--caps"], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           universal_newlines=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        with open(dst) as f:
            text = f.read()
        self.assertIn(".subckt %s" % top, text)


# A device of the readback list per PDK, and its library (ihp-sg13g2 has none).
READBACK_PCELL = {"sky130A": "sky130_fd_pr__cap_vpp_04p4x04p6_m1m2_shieldl1", "gf180mcuD": "rm1",
                  "ihp-sg13cmos5l": "nmoscl_2", "ihp-sg13g2": None}
NMOS = {"sky130_fd_pr__nfet_01v8", "nfet_03v3", "sg13_lv_nmos"}


def lvsjob_cat(name):
    from klayout_magic_pcells import lvsjob
    return getattr(lvsjob, name)


@needs_magic
class ReadbackMarkerTest(unittest.TestCase):
    """A placed PCell whose device Magic's GDS reader does not keep gets
    a marker in the extraction's report."""

    def test_marker(self):
        import klayout_magic_pcells as kmp
        from klayout_magic_pcells import lvsjob, pdkdata
        from klayout_magic_pcells.config import LIBRARY_NAMES
        rows = lvsjob.readback(PDK)
        dev = READBACK_PCELL[PDK]
        if dev is None:
            self.assertEqual(rows, {}, "ihp-sg13g2 has no device on the list")
            return
        self.assertIn(dev, rows)
        lib = kmp.register(PDK, cfg=CFG)
        self.assertIsNotNone(lib, "the plugin's library did not register")
        ly = db.Layout()
        top = ly.create_cell("TOP")
        var = ly.create_cell(dev, LIBRARY_NAMES[PDK], {})
        self.assertIsNotNone(var)
        places = [db.DTrans(db.DVector(5, 7)), db.DTrans(1, False, db.DVector(80, 7))]
        for t in places:
            top.insert(db.DCellInstArray(var.cell_index(), t))
        task = lvsjob.prepare(ly, top, CFG, pdkdata.load(PDK), {"cmd": "extract", "no_cache": True})
        out = task.start().wait()
        self.assertEqual(out.status, 1, out.summary)
        hits = [f for f in out.findings if f["category"] == lvsjob.CAT_READBACK]
        self.assertEqual(len(hits), 2, out.findings)
        self.assertIn("Magic's GDS reader does not keep this device; Magic's own cell extracts as", hits[0]["text"])
        boxes = sorted(tuple(h["box"]) for h in hits)
        want = sorted((b.left, b.bottom, b.right, b.top) for b in (var.dbbox().transformed(t) for t in places))
        for got, exp in zip(boxes, want):
            for g, e in zip(got, exp):
                self.assertAlmostEqual(g, e, 3)


if __name__ == "__main__":
    unittest.main()
