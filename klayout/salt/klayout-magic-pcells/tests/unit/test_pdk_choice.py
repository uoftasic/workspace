"""pdkchoice.py: which PDK a layout belongs to (no Magic needed)."""

import os
import shutil
import tempfile
import unittest

from tests.unit._util import REPO, needs_klayout, db  # noqa: F401
from klayout_magic_pcells.config import Config
from klayout_magic_pcells.pdkchoice import PdkChoiceError, choose_pdk


def cfg(pdks="all"):
    return Config.load(env={"HOME": "/h", "KMP_PDKS": pdks}, config_path="/nonexistent.ini")


class _Layout:
    """Just enough of a db.Layout for the technology rule."""

    def __init__(self, tech):
        self.technology_name = tech

    def top_cells(self):
        return []


class Order(unittest.TestCase):
    def test_explicit_comes_first(self):
        self.assertEqual(choose_pdk(_Layout("sg13g2"), explicit="gf180mcuD", cfg=cfg()),
                         ("gf180mcuD", "--pdk gf180mcuD"))
        with self.assertRaises(PdkChoiceError):
            choose_pdk(None, explicit="gf180mcuC", cfg=cfg())

    def test_technology_names(self):
        for tech, pdk in (("sky130A", "sky130A"), ("gf180mcu", "gf180mcuD"), ("sg13g2", "ihp-sg13g2"),
                          ("sg13cmos5l", "ihp-sg13cmos5l")):
            got, why = choose_pdk(_Layout(tech), cfg=cfg(), env={"PDK": "sky130A"})
            self.assertEqual(got, pdk)
            self.assertIn("technology is %s" % tech, why)

    def test_the_only_selected_pdk(self):
        got, why = choose_pdk(_Layout(""), cfg=cfg("ihp-sg13cmos5l"), env={"PDK": "ihp-sg13g2"})
        self.assertEqual(got, "ihp-sg13cmos5l")
        self.assertIn("KMP_PDKS", why)

    def test_the_pdk_variable_is_a_guess_before_asking(self):
        got, why = choose_pdk(_Layout(""), cfg=cfg(), env={"PDK": "ihp-sg13g2"})
        self.assertEqual(got, "ihp-sg13g2")
        self.assertTrue(why.startswith("a guess from the PDK variable"))
        with self.assertRaises(PdkChoiceError) as cm:
            choose_pdk(_Layout(""), cfg=cfg(), env={"PDK": "ihp-sg13g2"}, hint_decides=False)
        self.assertEqual(cm.exception.hint, "ihp-sg13g2")
        self.assertEqual(len(cm.exception.candidates), 4)
        # A PDK variable that names no selected PDK is no guess.
        with self.assertRaises(PdkChoiceError) as cm:
            choose_pdk(_Layout(""), cfg=cfg("sky130A gf180mcuD"), env={"PDK": "ihp-sg13g2"})
        self.assertEqual(cm.exception.candidates, ["sky130A", "gf180mcuD"])
        self.assertIsNone(cm.exception.hint)
        self.assertIn("--pdk", str(cm.exception))
        with self.assertRaises(PdkChoiceError):
            choose_pdk(None, cfg=cfg(), env={})


@needs_klayout
class FromTheCells(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="kmp-pdkchoice-")

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def saved_with_library(self, libnames):
        """A file whose top cell places one cell of each library, saved with
        context information and read back after the libraries are gone, so
        its PCell cells are <defunct> (cold proxies)."""
        libs = []
        ly = db.Layout()
        top = ly.create_cell("TOP")
        try:
            for i, name in enumerate(libnames):
                lib = db.Library()
                lib.description = "test"
                c = lib.layout().create_cell("DEV%d" % i)
                c.shapes(lib.layout().layer(68, 20)).insert(db.Box(0, 0, 100, 100))
                lib.register(name)
                libs.append(lib)
                proxy = ly.create_cell("DEV%d" % i, name)
                top.insert(db.CellInstArray(proxy.cell_index(), db.Trans(db.Vector(1000 * i, 0))))
            path = os.path.join(self.d, "lib.gds")
            ly.write(path)
        finally:
            for lib in libs:
                lib.delete()
        back = db.Layout()
        back.read(path)
        return back

    def test_the_plugin_library_of_its_pcells(self):
        ly = self.saved_with_library(["gf180mcu_magic"])
        got, why = choose_pdk(ly, cfg=cfg(), env={"PDK": "ihp-sg13g2"})
        self.assertEqual(got, "gf180mcuD")
        self.assertIn("gf180mcu_magic", why)

    def test_two_libraries_narrow_the_candidates(self):
        ly = self.saved_with_library(["sg13g2_magic", "sky130_magic"])
        with self.assertRaises(PdkChoiceError) as cm:
            choose_pdk(ly, cfg=cfg(), env={"PDK": "gf180mcuD"})
        self.assertEqual(cm.exception.candidates, ["sky130A", "ihp-sg13g2"])
        self.assertEqual(choose_pdk(ly, cfg=cfg(), env={"PDK": "sky130A"})[0], "sky130A")

    def test_variant_cells_saved_without_the_library(self):
        def layout(device):
            ly = db.Layout()
            top = ly.create_cell("TOP")
            v = ly.create_cell(device + "__kmp_0123abcd")
            v.shapes(ly.layer(68, 20)).insert(db.Box(0, 0, 100, 100))
            top.insert(db.CellInstArray(v.cell_index(), db.Trans()))
            return ly
        self.assertEqual(choose_pdk(layout("sky130_fd_pr__nfet_01v8"), cfg=cfg(), env={})[0], "sky130A")
        self.assertEqual(choose_pdk(layout("nfet_03v3"), cfg=cfg(), env={})[0], "gf180mcuD")
        # The two IHP PDKs share their device names: the PDK variable picks one of them.
        with self.assertRaises(PdkChoiceError) as cm:
            choose_pdk(layout("sg13_lv_nmos"), cfg=cfg(), env={"PDK": "sky130A"})
        self.assertEqual(cm.exception.candidates, ["ihp-sg13g2", "ihp-sg13cmos5l"])
        self.assertEqual(choose_pdk(layout("sg13_lv_nmos"), cfg=cfg(), env={"PDK": "ihp-sg13cmos5l"})[0],
                         "ihp-sg13cmos5l")

    def test_a_real_layout_with_a_technology(self):
        ly = db.Layout()
        ly.technology_name = "sky130A"
        if ly.technology_name != "sky130A":
            self.skipTest("this KLayout has no technology sky130A to assign")
        self.assertEqual(choose_pdk(ly, cfg=cfg(), env={})[0], "sky130A")



class _Labelled:
    """A case-suite layout under another technology name (in case this
    KLayout does not let a technology be assigned that it doesn't know)."""

    def __init__(self, layout, tech):
        self._layout = layout
        self.technology_name = tech

    def __getattr__(self, name):
        return getattr(self._layout, name)


TECH_OF = {"sky130A": "sky130A", "gf180mcuD": "gf180mcu", "ihp-sg13g2": "sg13g2",
           "ihp-sg13cmos5l": "sg13cmos5l"}
IHP = ("ihp-sg13g2", "ihp-sg13cmos5l")


@needs_klayout
class TechnologyAgainstTheLayers(unittest.TestCase):
    """In one GUI run in the image, a plain GDS opened with File > Open got
    the technology sg13g2 (design-0.6.md 6.8). A layout whose shapes fit
    another PDK's layers clearly better is not taken for the technology's
    PDK."""

    @classmethod
    def setUpClass(cls):
        from tests.cases import build
        cls.tmp = tempfile.mkdtemp(prefix="kmp-pdkchoice-cases-")
        cls.layouts = {}
        for pdk in TECH_OF:
            out = os.path.join(cls.tmp, pdk)
            build.build(pdk, out, ["inverters", "hier"], pcell=False)
            import json
            with open(os.path.join(out, "cases.json"), encoding="utf-8") as f:
                cases = json.load(f)["cases"]
            picked = [c for c in cases if c["set"] == "inverters"][:1] + [c for c in cases if c["set"] == "hier"][:1]
            cls.layouts[pdk] = []
            for c in picked:
                ly = db.Layout()
                ly.read(os.path.join(out, c["file"]))
                cls.layouts[pdk].append((c["name"], ly))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def labelled(self, ly, tech):
        ly.technology_name = tech
        return ly if ly.technology_name == tech else _Labelled(ly, tech)

    def test_the_layers_fit_their_own_pdk_best(self):
        from klayout_magic_pcells.pdkchoice import layer_fit
        for pdk, layouts in self.layouts.items():
            for name, ly in layouts:
                fit, total = layer_fit(ly)
                self.assertGreater(total, 0, name)
                self.assertEqual(fit[pdk], max(fit.values()), "%s %s: %s" % (pdk, name, fit))
                # Every other PDK but the IHP twin knows clearly fewer of them.
                for other, n in fit.items():
                    if other != pdk and not (other in IHP and pdk in IHP):
                        self.assertLess(n, 0.75 * fit[pdk], "%s %s: %s" % (pdk, name, fit))

    def test_a_wrong_technology_does_not_decide(self):
        for pdk, layouts in self.layouts.items():
            for name, ly in layouts:
                for tech_pdk, tech in TECH_OF.items():
                    if tech_pdk == pdk or (tech_pdk in IHP and pdk in IHP):
                        continue
                    with self.subTest(layout="%s %s" % (pdk, name), technology=tech):
                        lab = self.labelled(ly, tech)
                        # The two IHP PDKs fit alike: the first of them, or the PDK variable's.
                        first = "ihp-sg13g2" if pdk in IHP else pdk
                        # The command line: the best-fitting PDK, as a guess.
                        got, why = choose_pdk(lab, cfg=cfg(), env={"PDK": tech_pdk})
                        self.assertEqual(got, first, why)
                        self.assertTrue(why.startswith("a guess from the layers"), why)
                        self.assertIn("technology is %s (%s)" % (tech, tech_pdk), why)
                        self.assertEqual(choose_pdk(lab, cfg=cfg(), env={"PDK": pdk})[0], pdk)
                        # The GUI: it asks, with that PDK preselected.
                        with self.assertRaises(PdkChoiceError) as cm:
                            choose_pdk(lab, cfg=cfg(), env={"PDK": tech_pdk}, hint_decides=False)
                        self.assertEqual(cm.exception.hint, first)
                        self.assertEqual(len(cm.exception.candidates), 4)
                        self.assertIn("layers", cm.exception.hint_reason)
                        self.assertIn("technology is %s" % tech, cm.exception.why)

    def test_the_right_technology_and_the_ihp_twins(self):
        for pdk, layouts in self.layouts.items():
            for name, ly in layouts:
                with self.subTest(layout="%s %s" % (pdk, name)):
                    got, why = choose_pdk(self.labelled(ly, TECH_OF[pdk]), cfg=cfg(), env={})
                    self.assertEqual((got, why), (pdk, "the layout's technology is %s" % TECH_OF[pdk]))
                    if pdk in IHP:
                        # The IHP PDKs share their layer numbers: the technology picks.
                        twin = [p for p in IHP if p != pdk][0]
                        got, why = choose_pdk(self.labelled(ly, TECH_OF[twin]), cfg=cfg(), env={})
                        self.assertEqual(got, twin, why)
                        self.assertIn("technology is", why)


if __name__ == "__main__":
    unittest.main()
