"""The 0.6 case suite (tests/cases/): what build.py writes, read back with
klayout.db. No Magic: the PCell inverter and the Magic-written row are left
to the tests that run Magic. The controls set is built where PDK_ROOT has
the standard-cell library."""

import hashlib
import json
import os
import shutil
import tempfile
import unittest

from tests.unit._util import REPO, db, needs_klayout

PDKS = ("sky130A", "gf180mcuD", "ihp-sg13g2", "ihp-sg13cmos5l")
KEYS = ("name", "file", "top", "set", "targets", "expect", "notes", "source")
# cases per set that the suite must hold at least (README "Counts")
MIN_COUNTS = {"gaps": 49, "hier": 4, "whole_shape": 1, "names": 13, "inverters": 4, "sheet": 1}


def _sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


@needs_klayout
class CaseSuiteTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from tests.cases import build
        cls.build = build
        cls.tmp = tempfile.mkdtemp(prefix="kmp-cases-")
        cls.docs = {}
        for pdk in PDKS:
            out = os.path.join(cls.tmp, pdk)
            sets = [s for s in build.SETS if s != "controls"]
            mod = build.pdk_module(pdk)
            lib = os.path.join(os.environ.get("PDK_ROOT", "/nonexistent"), pdk, "libs.ref", mod.CONTROLS["lib"])
            if os.path.isdir(lib):
                sets.append("controls")
            build.build(pdk, out, sets, pcell=False)
            with open(os.path.join(out, "cases.json"), encoding="utf-8") as f:
                cls.docs[pdk] = json.load(f)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def cases(self, pdk, set_name=None):
        return [c for c in self.docs[pdk]["cases"] if set_name is None or c["set"] == set_name]

    def read(self, pdk, rel):
        ly = db.Layout()
        ly.read(os.path.join(self.tmp, pdk, rel))
        return ly

    def test_schema(self):
        for pdk in PDKS:
            doc = self.docs[pdk]
            self.assertEqual((doc["schema"], doc["pdk"]), (1, pdk))
            names = [c["name"] for c in doc["cases"]]
            self.assertEqual(len(names), len(set(names)), pdk)
            for c in doc["cases"]:
                for k in KEYS:
                    self.assertIn(k, c, (pdk, c["name"]))
                self.assertIn(c["set"], self.build.SETS)
                self.assertIsInstance(c["targets"], list)
                self.assertIsInstance(c["expect"], dict)
                self.assertTrue(c["source"], (pdk, c["name"]))

    def test_counts(self):
        for pdk in PDKS:
            for s, n in MIN_COUNTS.items():
                self.assertGreaterEqual(len(self.cases(pdk, s)), n, (pdk, s))

    def test_every_file_reads_back_with_its_top_cell(self):
        for pdk in PDKS:
            seen = {}
            for c in self.cases(pdk):
                if c["name"] == "row_magic":
                    continue        # Magic writes it (run_magic_row)
                if c["file"] not in seen:
                    seen[c["file"]] = self.read(pdk, c["file"])
                ly = seen[c["file"]]
                cell = ly.cell(c["top"])
                if c["top"] == "does_not_exist":
                    self.assertIsNone(cell)
                    continue
                self.assertIsNotNone(cell, (pdk, c["name"], c["file"]))
                self.assertFalse(cell.dbbox().empty(), (pdk, c["name"]))

    def test_files_have_no_context_and_safe_gaps_names(self):
        for pdk in PDKS:
            for c in self.cases(pdk, "gaps"):
                ly = self.read(pdk, c["file"])
                self.assertEqual([x.name for x in ly.each_cell()], [c["top"]], (pdk, c["name"]))
                self.assertRegex(c["top"], r"^[A-Za-z0-9_$]+$")

    def test_build_is_deterministic(self):
        out = os.path.join(self.tmp, "again")
        self.build.build("sky130A", out, ["gaps", "hier"], pcell=False)
        for rel in ("gaps/a_poly8.gds", "hier/inv_base_all_h.gds"):
            self.assertEqual(_sha(os.path.join(out, rel)), _sha(os.path.join(self.tmp, "sky130A", rel)), rel)

    def test_a_set_build_keeps_the_other_sets(self):
        out = os.path.join(self.tmp, "merge")
        self.build.build("ihp-sg13g2", out, ["gaps", "names"], pcell=False)
        self.build.build("ihp-sg13g2", out, ["names"], pcell=False)
        with open(os.path.join(out, "cases.json"), encoding="utf-8") as f:
            doc = json.load(f)
        self.assertEqual(doc["sets"], ["gaps", "names"])
        self.assertEqual(len([c for c in doc["cases"] if c["set"] == "names"]), 13)
        self.assertEqual(len([c for c in doc["cases"] if c["set"] == "gaps"]),
                         len(self.cases("ihp-sg13g2", "gaps")))

    def test_hier_moves_only_the_named_layers(self):
        for pdk in PDKS:
            two = [c for c in self.cases(pdk, "hier") if "moved" in c]
            self.assertGreaterEqual(len(two), 3, pdk)
            for c in two:
                ly = self.read(pdk, c["file"])
                parent, child = ly.cell(c["top"]), ly.cell(c["child"])
                insts = list(parent.each_inst())
                self.assertEqual(len(insts), 1)
                self.assertEqual(insts[0].cell_index, child.cell_index())
                self.assertEqual(insts[0].trans, db.Trans())
                moved = {tuple(x) for x in c["moved"]}
                for li in ly.layer_indexes():
                    info = ly.get_info(li)
                    key = (info.layer, info.datatype)
                    if key in moved:
                        self.assertTrue(child.shapes(li).is_empty(), (pdk, c["name"], key))
                    else:
                        self.assertTrue(parent.shapes(li).is_empty(), (pdk, c["name"], key))
                # the parent holds what the flat original has on those layers (C_NMOS has no well)
                base = c["child"].rsplit("_", 2)[0]
                flat = self.read(pdk, "hier/%s.gds" % base)
                for k in moved:
                    fl, pl = flat.find_layer(*k), ly.find_layer(*k)
                    n_flat = flat.cell(base).shapes(fl).size() if fl is not None else 0
                    n_par = parent.shapes(pl).size() if pl is not None else 0
                    self.assertEqual(n_par, n_flat, (pdk, c["name"], k))

    def test_hier_expectations_follow_the_review(self):
        # The review's two-level cases (design-0.6.md 3.1) report errors, the flat originals none
        gate = {"sky130A": ["inv_base_imp_h", "inv_base_nw_h", "inv_base_all_h"],
                "gf180mcuD": ["C_NMOS_imp_h", "C_PMOS_nw_h", "C_NMOS_all_h"],
                "ihp-sg13g2": ["inv_psd_h", "inv_nw_h", "inv_all_h"],
                "ihp-sg13cmos5l": ["base_psd_h", "base_nw_h", "base_all_h"]}
        for pdk, names in gate.items():
            by = {c["name"]: c for c in self.cases(pdk, "hier")}
            for n in names:
                self.assertTrue(by[n]["expect"]["magic"]["drc(full)"], (pdk, n))
            for c in by.values():
                if c["name"].endswith("_flat"):
                    self.assertEqual(c["expect"]["magic"]["drc(full)"], {}, (pdk, c["name"]))
                    self.assertEqual(len(c["expect"]["magic"]["extract"]), 2 if pdk != "gf180mcuD" else 1)

    def test_names(self):
        for pdk in PDKS:
            cs = self.cases(pdk, "names")
            self.assertEqual([c["klayout_name"] for c in cs], self.build.CELL_NAMES + ["does_not_exist"])
            ly = self.read(pdk, cs[0]["file"])
            layer = self.build.pdk_module(pdk).NAMES_ERROR[0]
            li = ly.find_layer(*self.build.pdk_module(pdk).LAYERS[layer])
            for c in cs[:-1]:
                self.assertEqual(ly.cell(c["top"]).shapes(li).size(), 1, (pdk, c["name"]))
            self.assertEqual(len({c["top"] for c in cs}), len(cs))
            self.assertEqual(len(list(ly.cell("NTOP").each_inst())), len(self.build.CELL_NAMES))

    def test_sheet_holds_every_gaps_case_40um_apart(self):
        for pdk in PDKS:
            (c,) = self.cases(pdk, "sheet")
            gaps = [g["top"] for g in self.cases(pdk, "gaps")]
            self.assertEqual(c["cases"], gaps)
            ly = self.read(pdk, c["file"])
            top = ly.cell("SHEET")
            subs = sorted(ly.cell(i.cell_index).name for i in top.each_inst())
            self.assertEqual(subs, sorted("D" + g for g in gaps), pdk)
            # Each cell moves by a multiple of 5 nm, also after a case whose box is off the grid
            # (sky130A s_m1_offgrid), so KLayout's grid checks see the cells' own shapes.
            for i in top.each_inst():
                d = i.trans.disp
                self.assertEqual((d.x % 5, d.y % 5), (0, 0), (pdk, ly.cell(i.cell_index).name))
            with open(os.path.join(self.tmp, pdk, c["file"]) + ".json", encoding="utf-8") as f:
                placed = json.load(f)["placed"]
            rows = {}
            for box in placed.values():
                rows.setdefault(box[1], []).append(box)
            for row in rows.values():
                row.sort()
                for a, b in zip(row, row[1:]):
                    self.assertGreaterEqual(round(b[0] - a[2], 3), 40.0, pdk)

    def test_anchors_carry_the_gaps_rule(self):
        for pdk in PDKS:
            by = {c["name"]: c for c in self.cases(pdk, "gaps")}
            for name, rule in self.docs[pdk]["anchors"].items():
                self.assertIn(rule, by[name]["targets"], (pdk, name))
                self.assertIn(rule, by[name]["expect"]["magic"]["drc(full)"], (pdk, name))
                ctl = by[name].get("control")
                if ctl:
                    self.assertEqual(by[ctl]["expect"]["magic"]["drc(full)"], {}, (pdk, ctl))

    def test_whole_shape(self):
        by = {c["name"]: c for c in self.cases("sky130A", "whole_shape")}
        nw = by["nwtap"]
        self.assertEqual(nw["expect"]["magic"]["drc(full)"], {})
        self.assertEqual(nw["expect"]["magic_area"]["drc(full)"], {"nwell.4": 1})
        ly = self.read("sky130A", nw["file"])
        well = ly.cell("nwtap").shapes(ly.find_layer(64, 20))
        self.assertEqual([s.dbbox() for s in well.each()], [db.DBox(0, 0, 100, 3)])
        for pdk in PDKS:
            for c in self.cases(pdk, "whole_shape"):
                self.assertEqual(len(c["box"]), 4)

    def test_inverters_have_a_schematic_each(self):
        for pdk in PDKS:
            for c in self.cases(pdk, "inverters"):
                path = os.path.join(self.tmp, pdk, c["schematic"])
                with open(path, encoding="utf-8") as f:
                    text = f.read()
                self.assertIn(".subckt %s " % c["top"], text)
                self.assertEqual(text.count("\nX"), 2, (pdk, c["name"]))

    def test_controls_where_the_library_is_installed(self):
        for pdk in PDKS:
            cs = self.cases(pdk, "controls")
            if not cs:
                continue
            mod = self.build.pdk_module(pdk)
            by = {c["name"]: c for c in cs}
            for cell in mod.CONTROLS["cells"]:
                self.assertTrue(by[cell]["negative_control"])
            row = by["row"]
            ly = self.read(pdk, row["file"])
            xs = sorted(round(i.dtrans.disp.x, 4) for i in ly.cell("row").each_inst())
            self.assertEqual(xs, sorted(row["x_um"]))
            inp = by["row_magic"]["magic_row"]
            self.assertEqual((inp["cells"], inp["x_um"]), (mod.CONTROLS["cells"], row["x_um"]))

    def test_targets_from_descriptions(self):
        t = self.build.targets_from
        self.assertEqual(t("gate poly ends 0.05 past the n-diffusion (poly.8 wants 0.13)"), ["poly.8"])
        self.assertEqual(t("pad (licon.8 0.05, licon.8a 0.08)"), ["licon.8", "licon.8a"])
        self.assertEqual(t("x (Magic DF.7 / KLayout DF.4c_LV 0.43)"), ["DF.7", "DF.4c_LV"])
        self.assertEqual(t("x (licon.9 + psdm.5a: 0.235)"), ["licon.9", "psdm.5a"])
        self.assertEqual(t("x (diff/tap.8 0.18)"), ["diff/tap.8"])
        self.assertEqual(t("x (nsdm width 0.38)"), [])
        self.assertEqual(t("no parentheses poly.8"), [])


if __name__ == "__main__":
    unittest.main()
