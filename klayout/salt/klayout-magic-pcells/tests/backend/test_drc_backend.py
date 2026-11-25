"""Backend tests of Magic's DRC from KLayout (drcjob.py and tcl/kmp_drc.tcl)
on the PDK that KMP_PDK names. scripts/test.sh runs this file once per PDK.
The layouts come from the case suite (tests/cases/build.py), built here into
a temporary folder. Skipped when Magic, the PDK or the klayout module is
missing.
"""

import collections
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "python"))

from klayout_magic_pcells.config import Config  # noqa: E402

try:
    import klayout.db as db
    from klayout_magic_pcells import drcjob, markers, pdkdata
    from klayout_magic_pcells.backend import MagicServer
    from klayout_magic_pcells.export import load_layout
    from tests.cases import build as cases_build
except ImportError:
    db = None

CACHE = tempfile.mkdtemp(prefix="kmp-drc-cache-")
try:
    CFG = Config.load(env=dict(os.environ, KMP_CACHE_DIR=CACHE))
    HAVE_MAGIC = not CFG.problems()
except Exception:
    HAVE_MAGIC = False

needs_magic = unittest.skipUnless(HAVE_MAGIC and db is not None,
                                  "Magic, the PDK or the klayout module is missing")
PDK = CFG.pdk if HAVE_MAGIC else "sky130A"
MDRC = os.path.join(REPO, "tests", "parity", "mdrc.tcl")
TIMEOUT = 300

# (case, styles) per PDK: a clean control, then one-change cases with the
# rule each must give, as cases.json's expect.magic has them.
GAPS = {
    "sky130A": [("inv_base", ("drc(fast)", "drc(full)")), ("a_poly8", ("drc(fast)", "drc(full)")),
                ("w_no_ptap", ("drc(full)",))],
    "gf180mcuD": [("C_NMOS", ("drc(fast)", "drc(full)")), ("PL4_e015", ("drc(full)",)),
                  ("NW1a_w080", ("drc(full)",))],
    "ihp-sg13g2": [("Gat_c_ok", ("drc(fast)", "drc(full)")), ("Gat_c", ("drc(full)",)),
                   ("M1_a", ("drc(full)",))],
    "ihp-sg13cmos5l": [("base", ("drc(fast)", "drc(full)")), ("m_Gat.c", ("drc(full)",)),
                       ("m_NW.a", ("drc(full)",))],
}

# Cells Magic reads nothing in (only implants or markers, no diffusion or
# poly under them): a finding with status 1, not a failed job (design-0.6.md 3.1).
READS_NOTHING = {"sky130A": {"s_hvtp_alone": "78/44 (hvtp.drawing)", "s_nsdm_alone": "93/44 (nsdm.drawing)",
                             "s_npc_alone": "95/20 (npc.drawing)", "s_lvtn_alone": "125/44 (lvtn.drawing)"},
                 "ihp-sg13g2": {"EXTB_a": "111/0 (EXTBlock.drawing)"}}
# The item texts' GDS layers: rules whose types the tech file names by alias
# and synonym (allm1 is *m1,rm1; m1 is metal1, cifout's key). Each rule ID
# must name the layer.
LAYER_HINTS = {
    "sky130A": {"met1.6": (68, 20), "nwell.1": (64, 20), "diff/tap.11": (65, 44)},
    "gf180mcuD": {"M1.1": (34, 0), "DN.1": (12, 0), "DF.5": (22, 0)},
    "ihp-sg13g2": {"M1.a": (8, 0), "NW.a": (31, 0), "NW.e": (1, 0)},
    "ihp-sg13cmos5l": {"M1.a": (8, 0), "NW.a": (31, 0), "NW.e": (1, 0)},
}

CASES_DIR = None
CASES = {}
DATA = None


def setUpModule():
    global CASES_DIR, CASES, DATA
    if not (HAVE_MAGIC and db is not None):
        return
    CASES_DIR = tempfile.mkdtemp(prefix="kmp-drc-cases-")
    # The PCell inverter only on sky130A (ChildOnly), where its FET variants list met1.6 on their own.
    sets = ["gaps", "hier", "whole_shape", "names", "sheet"] + (["inverters"] if PDK == "sky130A" else [])
    cases_build.build(PDK, CASES_DIR, sets=sets, pcell=PDK == "sky130A")
    with open(os.path.join(CASES_DIR, "cases.json"), encoding="utf-8") as f:
        CASES = {c["name"]: c for c in json.load(f)["cases"]}
    DATA = pdkdata.load(PDK)


def tearDownModule():
    shutil.rmtree(CACHE, ignore_errors=True)
    if CASES_DIR:
        shutil.rmtree(CASES_DIR, ignore_errors=True)


def case_path(c):
    return os.path.join(CASES_DIR, c["file"])


def per_rule(rows):
    """{rule ID: boxes} of (cell, why, box) rows."""
    return dict(collections.Counter(drcjob.rule_id(why) for _, why, _ in rows))


def run_drc(path, cells, **options):
    ly = load_layout(path)
    options.setdefault("timeout", TIMEOUT)
    options.setdefault("file", path)
    return drcjob.prepare(ly, cells, CFG, DATA, options).wait()


def run_cli(*args):
    env = dict(os.environ, KMP_CACHE_DIR=CACHE, KMP_PDKS=PDK,
               PYTHONPATH=os.path.join(REPO, "python") + os.pathsep + os.environ.get("PYTHONPATH", ""))
    p = subprocess.run([sys.executable, "-m", "klayout_magic_pcells", "drc", "--pdk", PDK] + list(args),
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, env=env,
                       stdin=subprocess.DEVNULL, timeout=TIMEOUT * 2)
    return p.returncode, p.stdout, p.stderr


def run_mdrc(gds, top, workdir):
    """tests/parity/mdrc.tcl as it is (drc(full)): Counter of (why, box in nm)."""
    out = os.path.join(workdir, "mdrc-%s.tsv" % abs(hash((gds, top))))
    env = MagicServer._env(types.SimpleNamespace(cfg=CFG))
    env.update(KMP_GDS=gds, KMP_TOP=top, KMP_OUT=out)
    p = subprocess.run([CFG.magic, "-dnull", "-noconsole", "-rcfile", CFG.magicrc, MDRC], cwd=workdir, env=env,
                       stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       universal_newlines=True, timeout=TIMEOUT)
    if "MDRC_DONE" not in p.stdout:
        raise AssertionError("mdrc.tcl failed on %s %s: %s" % (gds, top, p.stdout[-2000:]))
    got = collections.Counter()
    with open(out, encoding="utf-8") as f:
        for line in f:
            why, box = line.rstrip("\n").split("\t")
            got[(why, tuple(int(round(float(v) * 1000)) for v in box.split()))] += 1
    return got


@needs_magic
class OneChange(unittest.TestCase):
    """A clean control and one-change cases: Magic's rules as the GAPS measured them."""

    def test_cases(self):
        for name, styles in GAPS[PDK]:
            c = CASES[name]
            for style in styles:
                with self.subTest(case=name, style=style):
                    out = run_drc(case_path(c), c["top"], style=style)
                    want = c["expect"]["magic"][style]
                    self.assertEqual(per_rule(out.rows), want, out.summary)
                    self.assertEqual(out.status, 1 if want else 0)
                    self.assertIn("Style %s, mode hierarchical" % style, out.rdb.db.description)


@needs_magic
class Hierarchy(unittest.TestCase):
    """The two-level cells (design-0.6.md 3.1): the layers moved into a parent
    cell. Hierarchical mode gives Magic's result on the two-level cell, flat
    mode none."""

    def test_two_level_cells(self):
        hier = [c for c in CASES.values() if c["set"] == "hier" and c.get("child")]
        self.assertTrue(hier)
        extra = {}
        for c in hier:
            with self.subTest(case=c["name"]):
                want = c["expect"]["magic"]["drc(full)"]
                out = run_drc(case_path(c), c["top"], style="drc(full)", mode="hierarchical")
                self.assertNotEqual(out.status, 2, out.summary)
                raw = out.raw[c["top"]]
                # The top cell's own check, before the copy drop, is the check the review ran.
                top = per_rule((e.cell, e.why, e.box) for e in raw.get(c["top"], []))
                self.assertEqual(top, want, out.summary)
                # Every cell checked: the child's own check adds boxes the parent's implants or
                # well remove; neither the top's check nor the flat one lists them, so they are
                # information only, and the errors are the top cell's rules.
                rules = set(per_rule(out.rows))
                self.assertEqual(rules, set(want), out.summary)
                alone = sorted(set(per_rule(out.alone)))
                if alone:
                    extra[c["name"]] = alone
                    self.assertGreater(out.rdb.count(drcjob.alone_category(out.alone[0][1], c["child"])), 0)
                self.assertEqual(out.classes[c["top"]][drcjob.FLAT_ONLY], 0, out.summary)
                self.assertIn(drcjob.M1_NOTE, out.rdb.db.description)
                self.assertEqual(out.status, 1 if want else 0)
                if want:
                    self.assertGreater(out.rdb.count(markers.CAT_CROSS_CELL), 0)
                flat = run_drc(case_path(c), c["top"], style="drc(full)", mode="flat")
                self.assertEqual((flat.status, flat.rows), (0, []), flat.summary)
                self.assertIn(drcjob.FLAT_NOTE, flat.rdb.db.description)
        if extra:
            sys.stderr.write("\n%s: rules only the child cells' own checks list (information): %s\n"
                             % (PDK, extra))

    def test_plumbing_against_mdrc(self):
        """The plugin's boxes equal mdrc.tcl's on the same export, as a multiset at 1 nm:
        per cell in hierarchical mode (before the copy drop), and on the flat export."""
        work = tempfile.mkdtemp(prefix="kmp-drc-mdrc-")
        try:
            hier = [c for c in CASES.values() if c["set"] == "hier" and c.get("child")
                    and c["expect"]["magic"]["drc(full)"]]
            c = max(hier, key=lambda c: sum(c["expect"]["magic"]["drc(full)"].values()))
            out = run_drc(case_path(c), c["top"], style="drc(full)", mode="hierarchical", no_cache=True)
            gds = out.files["export"]
            raw = out.raw[c["top"]]
            self.assertEqual(sorted(raw), sorted([c["top"], c["child"]]))
            for cell, errs in raw.items():
                mine = collections.Counter((e.why, e.box) for e in errs)
                self.assertEqual(mine, run_mdrc(gds, cell, work), (c["name"], cell))
                self.assertTrue(mine or cell != c["top"])
            names = CASES["name_00"]
            flat = run_drc(case_path(names), "NTOP", style="drc(full)", mode="flat")
            errs = flat.raw["NTOP"]["NTOP"]
            self.assertEqual(len(errs), 12)
            self.assertEqual(collections.Counter((e.why, e.box) for e in errs),
                             run_mdrc(flat.files["export"], "NTOP", work))
        finally:
            shutil.rmtree(work, ignore_errors=True)


@needs_magic
class Area(unittest.TestCase):
    """An area check is the whole-cell check filtered to the area (design-0.6.md 3.1)."""

    def test_long_well(self):
        for c in [c for c in CASES.values() if c["set"] == "whole_shape"]:
            with self.subTest(case=c["name"]):
                whole = run_drc(case_path(c), c["top"], style="drc(full)")
                area = run_drc(case_path(c), c["top"], style="drc(full)", box=c["box"])
                self.assertNotEqual(area.status, 2, area.summary)
                # the whole-cell job's cache entry serves the area check
                self.assertEqual(area.files["job_dir"], whole.files["job_dir"])
                a = drcjob.area_nm(c["box"])
                self.assertEqual(area.rows, [r for r in whole.rows if drcjob.touches(r[2], a)])
                if PDK == "sky130A":
                    self.assertNotIn("nwell.4", per_rule(area.rows))
                    self.assertEqual(per_rule(whole.rows), c["expect"]["magic"]["drc(full)"])
                self.assertIn("Area %s um" % ",".join(drcjob.fmt_um(v) for v in a), area.rdb.db.description)

    def test_box_keeps_child_errors_through_placements(self):
        c = CASES["name_00"]
        rule = c["targets"][0]
        # Cells 2 and 3 sit at x = 10 and 15; Magic's width error box can lie beside the
        # shape (gf180mcuD M1.1: x 0.20 to 0.23 in the cell), so the area reaches past both.
        out = run_drc(case_path(c), "NTOP", box=(9.9, -1, 15.5, 2))
        self.assertEqual(per_rule(out.rows), {rule: 2}, out.summary)


@needs_magic
class Names(unittest.TestCase):
    """The review's cell names (design-0.6.md 2.2), each with one minimal error."""

    def test_every_name_in_one_hierarchical_check(self):
        names = [c for c in CASES.values() if c["set"] == "names" and c["targets"]]
        out = run_drc(case_path(names[0]), "NTOP")
        self.assertEqual(out.status, 1, out.summary)
        # Each cell, loaded under the name the export gave it, has its error in its own
        # check, under its KLayout name.
        er = out.export["NTOP"]
        own = collections.defaultdict(list)
        for fname, errs in out.raw["NTOP"].items():
            for e in errs:
                own[er.klayout_name(fname)].append(drcjob.rule_id(e.why))
        for c in names:
            self.assertEqual(own.get(c["top"]), c["targets"], c["top"])
        # NTOP's own check lists every one of them, so the report has them in NTOP.
        by_cell = collections.Counter(cell for cell, _why, _box in out.rows)
        self.assertEqual(by_cell, {"NTOP": len(names)})

    def test_each_name_as_its_own_top_and_a_missing_cell(self):
        names = [c for c in CASES.values() if c["set"] == "names" and c["targets"]]
        path = case_path(names[0])
        args = [path]
        for c in names:
            args += ["--cell", c["top"]]
        rc, out, err = run_cli(*(args + ["--tsv", "-"]))
        self.assertEqual(rc, 1, err)
        rows = [ln.split("\t") for ln in out.splitlines()[1:]]
        self.assertEqual(sorted((r[0], r[1]) for r in rows), sorted((c["top"], c["targets"][0]) for c in names))
        rc, out, err = run_cli(path, "--cell", "does_not_exist")
        self.assertEqual(rc, 2)
        self.assertIn("cell does_not_exist is not in", err)


@needs_magic
class Jobs(unittest.TestCase):
    def test_error_marker_refusal(self):
        """A layout with a 255/0 marker cell is refused, naming the cell (design-0.6.md 2.6)."""
        d = tempfile.mkdtemp(prefix="kmp-drc-m16-")
        try:
            c = CASES["name_00"]
            ly = load_layout(case_path(c))
            bad = ly.create_cell("broken_pcell")
            m = ly.layer(*DATA.error_marker)
            bad.shapes(m).insert(db.DBox(0, 0, 1, 1))
            bad.shapes(m).insert(db.DText("Magic failed", db.DTrans()))
            ly.cell("NTOP").insert(db.DCellInstArray(bad.cell_index(), db.DTrans(db.DVector(0, 20))))
            path = os.path.join(d, "m16.gds")
            ly.write(path)
            rc, out, err = run_cli(path, "--cell", "NTOP", "-o", os.path.join(d, "m16.lyrdb"))
            self.assertEqual(rc, 2, err)
            self.assertIn("broken_pcell", err)
            r = markers.load(os.path.join(d, "m16.lyrdb"))
            cats = {r.category_by_id(it.category_id()).name() for it in r.each_item()}
            self.assertIn("error-marker cells", cats)
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_batches_of_15_and_an_empty_child(self):
        """More than 15 cells take two Magic processes; a child Magic sees as
        empty is skipped, not a failure; --no-cache runs again elsewhere."""
        layer, box, rule = cases_build.pdk_module(PDK).NAMES_ERROR
        lay = cases_build.pdk_module(PDK).LAYERS[layer]
        ignored = [r["gds"] for r in DATA.layers_by_read("ignored") if r["gds"] != list(DATA.error_marker)][0]
        ly = db.Layout()
        ly.dbu = 0.001
        top = ly.create_cell("TOPB")
        li = ly.layer(*lay)
        for i in range(20):
            cc = ly.create_cell("c%02d" % i)
            cc.shapes(li).insert(db.DBox(*box))
            top.insert(db.DCellInstArray(cc.cell_index(), db.DTrans(db.DVector(i * 5.0, 0))))
        e = ly.create_cell("only_ignored")
        e.shapes(ly.layer(*ignored)).insert(db.DBox(0, 0, 1, 1))
        top.insert(db.DCellInstArray(e.cell_index(), db.DTrans(db.DVector(0, 10))))
        top.shapes(li).insert(db.DBox(0, 20, 5, 21))
        d = tempfile.mkdtemp(prefix="kmp-drc-batch-")
        try:
            path = os.path.join(d, "b.gds")
            ly.write(path)
            out = run_drc(path, "TOPB")
            self.assertEqual(out.status, 1, out.summary)
            self.assertEqual(len(out.files["jobs"]), 2)
            # Each child's own check, in one of the two processes, has its error; TOPB's
            # check lists all 20, so the report has them in TOPB.
            own = {c: len(errs) for c, errs in out.raw["TOPB"].items() if c != "TOPB"}
            self.assertEqual(own, {"c%02d" % i: 1 for i in range(20)})
            cells = collections.Counter(r[0] for r in out.rows)
            self.assertEqual(cells, {"TOPB": 20})
            self.assertIn("only_ignored", out.rdb.db.description)
            self.assertEqual(out.empty, ["only_ignored"])
            self.assertEqual(out.rdb.count(markers.CAT_READS_NOTHING), 0)
            again = run_drc(path, "TOPB")
            self.assertEqual(again.files["jobs"], out.files["jobs"])
            fresh = run_drc(path, "TOPB", no_cache=True)
            self.assertEqual(fresh.rows, out.rows)
            self.assertFalse(set(fresh.files["jobs"]) & set(out.files["jobs"]))
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_poll_and_cancel(self):
        """The GUI's path: start() returns at once, poll() until the outcome;
        cancel() ends a running task with status 2."""
        import time
        c = CASES["name_00"]
        ly = load_layout(case_path(c))
        t = drcjob.prepare(ly, "NTOP", CFG, DATA, {"no_cache": True, "timeout": TIMEOUT}).start()
        out, polls = None, 0
        deadline = time.time() + TIMEOUT
        while out is None and time.time() < deadline:
            out = t.poll()
            polls += 1
            time.sleep(0.05)
        self.assertIsNotNone(out)
        self.assertEqual(out.status, 1, out.summary)
        self.assertGreater(polls, 1)
        t = drcjob.prepare(ly, "NTOP", CFG, DATA, {"no_cache": True, "timeout": TIMEOUT}).start()
        t.cancel()
        out = t.poll()
        self.assertEqual(out.status, 2)
        self.assertIn("cancelled", out.summary)

    def test_rdb_and_tsv_from_the_command_line(self):
        c = [c for c in CASES.values() if c["set"] == "hier" and c.get("child")
             and c["expect"]["magic"]["drc(full)"]][0]
        d = tempfile.mkdtemp(prefix="kmp-drc-cli-")
        try:
            lyrdb, tsv = os.path.join(d, "h.lyrdb"), os.path.join(d, "h.tsv")
            rc, out, err = run_cli(case_path(c), "--style", "drc(full)", "-o", lyrdb, "--tsv", tsv)
            self.assertEqual(rc, 1, err)
            r = markers.load(lyrdb)
            self.assertTrue(r.generator.startswith("klayout_magic_pcells: "))
            self.assertIn("cmd='drc'", r.generator)
            self.assertIn("drc list count total", r.description)
            self.assertIn(PDK, r.description)
            with open(tsv, encoding="utf-8") as f:
                lines = f.read().splitlines()
            # A child cell in the database has its placements. The child has items only
            # where its own check lists boxes that the top cell's check lacks (information
            # on sky130A and gf180mcuD); otherwise every error is in the top cell.
            children = [rc for rc in r.each_cell() if rc.name() != c["top"]]
            for child in children:
                self.assertGreater(len(list(child.each_reference())), 0, child.name())
            if not children:
                self.assertEqual({ln.split("\t")[0] for ln in lines[1:]}, {c["top"]})
            self.assertEqual(lines[0], drcjob.TSV_HEADER)
            self.assertEqual(len(lines) - 1, sum(1 for _ in r.each_item()) - _export_items(r))
            # The markers' boxes, cell by cell, equal the TSV's rows (design-0.6.md 5.3: a marker
            # shifted in the report database only).
            rows = collections.defaultdict(collections.Counter)
            for ln in lines[1:]:
                p = ln.split("\t")
                rows[p[0]][(p[2], tuple(int(round(float(v) * 1000)) for v in p[3:7]))] += 1
            marks = _error_boxes(r)
            self.assertEqual(set(marks), set(rows))
            for cell in rows:
                self.assertEqual(marks[cell], rows[cell], cell)
            self.assertGreater(sum(len(v) for v in rows.values()), 1)
        finally:
            shutil.rmtree(d, ignore_errors=True)


@needs_magic
class ChildOnly(unittest.TestCase):
    """Hierarchical mode classifies every box of a cell other than the top:
    in the top cell's check (an error), confirmed only by the flattened
    layout's check (an error), or listed only when the cell is checked on
    its own (information, not counted)."""

    def test_a_box_the_parent_removes_is_information(self):
        """A child whose metal is too narrow on its own, inside a wide metal
        box of its parent: Magic's check from the top and the flat check
        find nothing, so the run exits 0 with the box under "only when"."""
        layer, box, rule = cases_build.pdk_module(PDK).NAMES_ERROR
        lay = cases_build.pdk_module(PDK).LAYERS[layer]
        ly = db.Layout()
        ly.dbu = 0.001
        top = ly.create_cell("PARENT")
        child = ly.create_cell("narrow")
        li = ly.layer(*lay)
        child.shapes(li).insert(db.DBox(*box))
        top.insert(db.DCellInstArray(child.cell_index(), db.DTrans(db.DVector(5.0, 0))))
        top.shapes(li).insert(db.DBox(4.0, -1.0, 7.0, 2.0))
        d = tempfile.mkdtemp(prefix="kmp-drc-alone-")
        try:
            path = os.path.join(d, "alone.gds")
            ly.write(path)
            out = run_drc(path, "PARENT", style="drc(full)")
            self.assertEqual(out.status, 0, out.summary)
            self.assertEqual(out.rows, [])
            self.assertEqual([(c, drcjob.rule_id(w)) for c, w, _ in out.alone], [("narrow", rule)])
            self.assertEqual(out.rdb.count(drcjob.alone_category(out.alone[0][1], "narrow")), 1)
            self.assertIn("1 only when the subcell is checked on its own", out.summary)
            self.assertIn("flat_check", out.files)
            self.assertEqual(out.flat_raw["PARENT"], [])
            # The flat check shares flat mode's cache entry.
            flat = run_drc(path, "PARENT", style="drc(full)", mode="flat")
            self.assertEqual(flat.files["job_dir"], out.files["flat_check"])
            # The child as its own top cell has the error.
            rc, _, err = run_cli(path, "--cell", "narrow")
            self.assertEqual(rc, 1, err)
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_the_sheet_boxes_the_top_cell_misses(self):
        """On a sheet of isolated cases (design-0.6.md 3.1), every box a case's
        own check lists is real. Magic's check from the top cell misses some
        (sky130A, gf180mcuD), and the flattened check confirms all of them."""
        c = CASES["sheet"]
        out = run_drc(case_path(c), c["top"], style="drc(full)")
        self.assertEqual(out.status, 1, out.summary)
        n = out.classes[c["top"]]
        self.assertEqual(n[drcjob.ALONE], 0, out.summary)
        # The top cell's own check, and what only the flattened check confirms.
        self.assertEqual(len(out.rows), n[drcjob.TOP] + n[drcjob.FLAT_ONLY])
        self.assertIn("only in the flattened layout's check", out.summary)
        sys.stderr.write("\n%s sheet: %s\n" % (PDK, out.summary.split(". ", 1)[1]))
        if PDK in ("sky130A", "gf180mcuD"):
            self.assertGreater(n[drcjob.FLAT_ONLY], 0, out.summary)
            texts = [markers.item_text(it) for it in out.rdb.db.each_item()]
            self.assertTrue(any(drcjob.FLAT_ONLY_TEXT in t for t in texts))

    @unittest.skipUnless(PDK == "sky130A", "the PCell inverter's met1.6 boxes are sky130A's")
    def test_pcell_inverter(self):
        """The case suite's PCell inverter: the FET variants' gate pads give
        met1.6 checked on their own; the top cell's and the flat check give
        none, so the run exits 0 with the six boxes as information."""
        c = CASES.get("inv_pcell")
        if c is None:
            self.skipTest("the PCell inverter was not built")
        d = tempfile.mkdtemp(prefix="kmp-drc-pcell-")
        try:
            lyrdb = os.path.join(d, "inv.lyrdb")
            rc, out, err = run_cli(case_path(c), "-o", lyrdb, "--tsv", "-")
            self.assertEqual(rc, 0, err)
            self.assertEqual(out.splitlines(), [drcjob.TSV_HEADER])
            self.assertIn("6 only when the subcell is checked on its own", err)
            self.assertNotIn("No errors found", err)
            r = markers.load(lyrdb)
            cats = collections.Counter()
            for it in r.each_item():
                cat = r.category_by_id(it.category_id())
                cats[(cat.parent().name() if cat.parent() else "", cat.name())] += 1
            alone = {k: v for k, v in cats.items() if k[1].startswith("only when ")}
            self.assertEqual(sum(alone.values()), 6, cats)
            self.assertEqual({k[0] for k in alone}, {"met1.6"})
            self.assertFalse(any(k[1] == "No errors found." for k in cats))
            said = [markers.item_text(it) for it in r.each_item()]
            self.assertNotIn("No errors found.", said)
            # Problem 2 of the 0.6 docs run: no cross-cell finding on it.
            self.assertFalse(any("without a layer drawn" in k[1] for k in cats), cats)
            # The met1.6 items name metal1's drawing layer (allm1 is m1, which is metal1).
            met = [t for t in (markers.item_text(it) for it in r.each_item())
                   if t.startswith("Metal1 minimum area")]
            self.assertEqual(len(met), 6, met)
            self.assertTrue(all("68/20 (met1.drawing)" in t for t in met), met)
        finally:
            shutil.rmtree(d, ignore_errors=True)


@needs_magic
class ReadsNothing(unittest.TestCase):
    """A top cell Magic reads as empty is a finding, status 1, in both modes;
    Outcome.empty names it."""

    def check(self, out, top, layer_text):
        self.assertEqual(out.status, 1, out.summary)
        self.assertIn(top, out.empty)
        self.assertEqual(out.rows, [])
        self.assertEqual(out.rdb.count(markers.CAT_READS_NOTHING), 1, out.summary)
        self.assertEqual(out.rdb.count(drcjob.CAT_FAILED), 0, out.summary)
        texts = [markers.item_text(it) for it in out.rdb.db.each_item()]
        item = [t for t in texts if t.startswith("Magic reads nothing in cell %s" % top)]
        self.assertEqual(len(item), 1, texts)
        self.assertIn(layer_text, item[0])
        self.assertIn("Magic reads nothing in %s" % top, out.summary)
        # The summary says it once, with the category's name (which says "this
        # cell") in parentheses, and never "no errors" beside status 1.
        self.assertIn(": Magic reads nothing in %s, so nothing was checked (category %s)."
                      % (top, markers.CAT_READS_NOTHING), out.summary)
        self.assertEqual(out.summary.count("Magic reads nothing in"), 2, out.summary)
        self.assertNotIn("no errors", out.summary)

    def test_a_cell_with_only_an_ignored_layer(self):
        ignored = [r for r in DATA.layers_by_read("ignored") if r["gds"] != list(DATA.error_marker)][0]
        ly = db.Layout()
        ly.dbu = 0.001
        top = ly.create_cell("ONLY_IGNORED")
        top.shapes(ly.layer(*ignored["gds"])).insert(db.DBox(0, 0, 1, 1))
        d = tempfile.mkdtemp(prefix="kmp-drc-nothing-")
        try:
            path = os.path.join(d, "n.gds")
            ly.write(path)
            for mode in drcjob.MODES:
                with self.subTest(mode=mode):
                    out = run_drc(path, "ONLY_IGNORED", mode=mode)
                    self.check(out, "ONLY_IGNORED", "%d/%d" % tuple(ignored["gds"]))
            rc, _, err = run_cli(path, "-o", os.path.join(d, "n.lyrdb"))
            self.assertEqual(rc, 1, err)
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_the_gaps_cases(self):
        cases = READS_NOTHING.get(PDK)
        if not cases:
            self.skipTest("no such gaps case on %s" % PDK)
        for name, layer in cases.items():
            with self.subTest(case=name):
                c = CASES[name]
                self.check(run_drc(case_path(c), c["top"]), c["top"], layer)


@needs_magic
class LayerHints(unittest.TestCase):
    def test_item_texts_name_the_rules_layers(self):
        aliases = drcjob.tech_aliases(DATA, CFG)
        synonyms = drcjob.tech_types(DATA, CFG)
        self.assertTrue(aliases and synonyms, "the tech files next to %s were not read" % CFG.magicrc)
        for rid, pair in LAYER_HINTS[PDK].items():
            with self.subTest(rule=rid):
                st = [r for r in DATA.drc["rules"] if rid in r.get("ids", [])]
                self.assertTrue(st, rid)
                info = drcjob.RuleInfo(DATA, st[0]["why"], {}, aliases, synonyms)
                self.assertIn(pair, info.layers, (st[0]["types"], info.item_text()))
                self.assertIn("%d/%d (" % pair, info.item_text())


def _error_boxes(r):
    """{cell: Counter((why, box in nm))} of the error items of a loaded
    report: under "Magic DRC", not under an "only when" category; the why
    is the name of the item's category (drcjob.category_path's last part)."""
    out = collections.defaultdict(collections.Counter)
    for it in r.each_item():
        cat = r.category_by_id(it.category_id())
        why = cat.name()
        alone = False
        while cat.parent() is not None:
            alone = alone or cat.name().startswith("only when ")
            cat = cat.parent()
        if cat.name() != drcjob.CAT_DRC or alone:
            continue
        boxes = [v.box() for v in it.each_value() if v.is_box()]
        text = markers.item_text(it)
        assert len(boxes) == 1 and text, (boxes, text)
        b = boxes[0]
        key = tuple(int(round(x * 1000)) for x in (b.left, b.bottom, b.right, b.top))
        assert text.startswith(why), (text, why)
        out[r.cell_by_id(it.cell_id()).name()][(why, key)] += 1
    return out


def _export_items(r):
    """Items that are not error boxes: outside "Magic DRC", or under an
    "only when <cell> is checked on its own" category."""
    n = 0
    for it in r.each_item():
        cat = r.category_by_id(it.category_id())
        alone = False
        while cat.parent() is not None:
            alone = alone or cat.name().startswith("only when ")
            cat = cat.parent()
        if cat.name() != drcjob.CAT_DRC or alone:
            n += 1
    return n


if __name__ == "__main__":
    unittest.main()
