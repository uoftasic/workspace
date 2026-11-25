"""export.py: the file Magic reads, and what Magic will do with it (no
Magic needed)."""

import os
import shutil
import tempfile
import unittest

from tests.unit._util import REPO, needs_klayout, db  # noqa: F401
from tests.unit.fixtures import mini_data

if db is not None:
    from klayout_magic_pcells import export
    from klayout_magic_pcells.export import ExportError, export_cell, load_layout, resolve_cells

# The review's cell names (design-0.6.md 2.2), each of which Magic
# mishandles in its own way or keeps.
NAMES = ["inv$1", "a.b", "a b", "a-b", "x/y", "brace{1}", "br[0]", "UPPER", "upper", "n" * 120, "café",
         "semi;colon"]

DIFF, POLY, LICON, NWELL, PWELL, NSDM, PSDM, M1, DIGI = ((65, 20), (66, 20), (66, 44), (64, 20), (64, 44),
                                                       (93, 44), (94, 20), (68, 20), (16, 0))


def read(path):
    ly = db.Layout()
    ly.read(path)
    return ly


def box(ly, cell, ld, *b):
    cell.shapes(ly.layer(*ld)).insert(db.DBox(*b))


@needs_klayout
class Export(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="kmp-export-")
        self.data = mini_data()

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def out(self, name="in.gds"):
        return os.path.join(self.d, name)

    def layout(self):
        ly = db.Layout()
        ly.dbu = 0.001
        return ly

    def test_only_the_selected_tree_without_context_info_or_timestamps(self):
        ly = self.layout()
        top = ly.create_cell("TOP")
        child = ly.create_cell("CHILD")
        box(ly, child, M1, 0, 0, 1, 1)
        top.insert(db.DCellInstArray(child.cell_index(), db.DTrans(db.DVector(2, 0))))
        other = ly.create_cell("OTHER")
        box(ly, other, M1, 0, 0, 1, 1)
        before = sorted(c.name for c in ly.each_cell())
        r1 = export_cell(ly, top, self.out("a.gds"), self.data)
        r2 = export_cell(ly, "TOP", self.out("b.gds"), self.data)
        self.assertEqual(r1.sha256, r2.sha256)
        with open(self.out("a.gds"), "rb") as f:
            raw = f.read()
        self.assertNotIn(b"CONTEXT_INFO", raw)
        back = read(self.out("a.gds"))
        self.assertEqual(sorted(c.name for c in back.each_cell()), ["CHILD", "TOP"])
        self.assertEqual((r1.top, r1.klayout_top, r1.path), ("TOP", "TOP", self.out("a.gds")))
        self.assertEqual(r1.name_map, {"TOP": "TOP", "CHILD": "CHILD"})
        self.assertEqual(r1.renamed, {})
        self.assertEqual(r1.dbu, 0.001)
        self.assertEqual(sorted(c.name for c in ly.each_cell()), before)
        # No export temp file is left beside the output.
        self.assertEqual(sorted(os.listdir(self.d)), ["a.gds", "b.gds"])

    def test_library_cells_become_plain_cells(self):
        lib = db.Library()
        lib.description = "test"
        lc = lib.layout().create_cell("DEV")
        lc.shapes(lib.layout().layer(*M1)).insert(db.Box(0, 0, 500, 500))
        lib.register("kmp_test_export_lib")
        try:
            ly = self.layout()
            top = ly.create_cell("TOP")
            proxy = ly.create_cell("DEV", "kmp_test_export_lib")
            self.assertTrue(proxy.is_library_cell())
            name = proxy.name
            top.insert(db.CellInstArray(proxy.cell_index(), db.Trans()))
            r = export_cell(ly, top, self.out(), self.data)
        finally:
            lib.delete()
        back = read(self.out())
        dev = back.cell(r.name_map[name])
        self.assertIsNotNone(dev)
        self.assertFalse(dev.is_proxy())
        self.assertEqual(dev.bbox(), db.Box(0, 0, 500, 500))

    def test_cell_names_magic_cant_load_are_renamed(self):
        ly = self.layout()
        top = ly.create_cell("NTOP")
        for i, n in enumerate(NAMES):
            c = ly.create_cell(n)
            box(ly, c, M1, 0, 0, 0.1, 1.0)
            top.insert(db.DCellInstArray(c.cell_index(), db.DTrans(db.DVector(5.0 * i, 0))))
        clash = ly.create_cell("a_b")
        box(ly, clash, M1, 0, 0, 0.1, 1.0)
        top.insert(db.DCellInstArray(clash.cell_index(), db.DTrans(db.DVector(0, 5))))
        r = export_cell(ly, top, self.out(), self.data)
        keep = {"inv$1", "UPPER", "upper", "n" * 120, "NTOP", "a_b"}
        for n in NAMES + ["a_b", "NTOP"]:
            new = r.name_map[n]
            self.assertRegex(new, r"^[A-Za-z0-9_$]+$", n)
            self.assertEqual(new == n, n in keep, n)
            self.assertEqual(r.klayout_name(new), n)
        self.assertEqual(len(set(r.name_map.values())), len(r.name_map))
        self.assertEqual(r.name_map["café"], "caf_")
        self.assertEqual(r.name_map["a b"], "a_b_1")   # a_b is taken
        back = read(self.out())
        # KLayout's GDS writer keeps every new name as it is.
        self.assertEqual(sorted(c.name for c in back.each_cell()), sorted(r.name_map.values()))
        self.assertEqual(set(r.renamed), set(NAMES + ["a_b", "NTOP"]) - keep)
        # The caller's layout keeps its names.
        self.assertIsNotNone(ly.cell("a.b"))

    def test_flat_copy(self):
        ly = self.layout()
        top = ly.create_cell("TOP")
        child = ly.create_cell("C")
        box(ly, child, M1, 0, 0, 1, 1)
        for x in (0, 3, 6):
            top.insert(db.DCellInstArray(child.cell_index(), db.DTrans(db.DVector(x, 0))))
        r = export_cell(ly, top, self.out(), self.data, flat=True)
        back = read(self.out())
        self.assertEqual([c.name for c in back.each_cell()], ["TOP"])
        self.assertEqual(back.cell("TOP").shapes(back.layer(*M1)).size(), 3)
        self.assertEqual(r.name_map, {"TOP": "TOP"})
        self.assertTrue(r.flat)

    def test_instances_magic_cant_place_are_flattened(self):
        ly = self.layout()
        top = ly.create_cell("NTOP")
        rot = ly.create_cell("rotme")
        box(ly, rot, M1, 0, 0, 0.1, 1.0)
        top.insert(db.DCellInstArray(rot.cell_index(), db.DCplxTrans(1.0, 45.0, False, db.DVector(0, 10))))
        top.insert(db.DCellInstArray(rot.cell_index(), db.DCplxTrans(2.0, 0.0, False, db.DVector(10, 10))))
        top.insert(db.DCellInstArray(rot.cell_index(), db.DCplxTrans(1.0, 90.0, True, db.DVector(20, 10))))
        r = export_cell(ly, top, self.out(), self.data)
        self.assertEqual(len(r.flattened), 2)
        self.assertEqual({c for c, _ in r.flattened}, {"NTOP"})
        why = " ".join(w for _, w in r.flattened)
        self.assertIn("rotated 45°", why)
        self.assertIn("magnified 2", why)
        back = read(self.out())
        t = back.cell("NTOP")
        insts = list(t.each_inst())
        self.assertEqual(len(insts), 1)
        self.assertFalse(insts[0].is_complex())
        self.assertEqual(t.shapes(back.layer(*M1)).size(), 2)
        # The caller's layout still has all three instances.
        self.assertEqual(len(list(top.each_inst())), 3)

    def test_off_grid_vertices(self):
        ly = self.layout()
        top = ly.create_cell("TOP")
        box(ly, top, M1, 0, 0, 1, 1)                 # on the 5 nm grid
        box(ly, top, M1, 2.001, 0, 3, 1)             # two vertices at x = 2.001
        box(ly, top, PWELL, 0.002, 0, 3, 1)          # off the grid, but Magic doesn't read 64/44
        r = export_cell(ly, top, self.out(), self.data)
        self.assertEqual(len(r.offgrid), 2)
        for text, b in r.offgrid:
            self.assertEqual(text, "68/20 (met1.drawing)")
            self.assertAlmostEqual(b.left, 2.001)
        # With the grid at the dbu nothing can be off it.
        self.assertEqual(export_cell(ly, top, self.out(), mini_data(grid_um=0.001)).offgrid, [])

    def test_layers_magic_ignores_or_reads_as_another_type(self):
        ly = self.layout()
        top = ly.create_cell("TOP")
        child = ly.create_cell("C")
        box(ly, child, PWELL, 0, 0, 1, 1)
        box(ly, child, PWELL, 0.5, 0, 2, 1)          # merged with the first one
        box(ly, top, (99, 0), 5, 5, 6, 6)            # not in the PDK's layer table
        top.shapes(ly.layer(99, 0)).insert(db.DText("A", db.DTrans(db.DVector(7, 7))))
        box(ly, top, DIGI, 0, 10, 4, 14)
        box(ly, top, M1, 0, 0, 1, 1)
        top.insert(db.DCellInstArray(child.cell_index(), db.DTrans(db.DVector(10, 0))))
        r = export_cell(ly, top, self.out(), self.data)
        unread = sorted((l, d, round(b.left, 3), round(b.bottom, 3), round(b.right, 3)) for l, d, b in r.unread)
        self.assertEqual(unread, [(64, 44, 10.0, 0.0, 12.0), (99, 0, 5.0, 5.0, 6.0), (99, 0, 7.0, 7.0, 7.0)])
        self.assertEqual([(l, d, t) for l, d, t, _ in r.reads_as], [(16, 0, "digisub")])
        self.assertEqual(r.reads_as[0][3], db.DBox(0, 10, 4, 14))
        # Without data there are no layer findings, and the file is the same.
        r0 = export_cell(ly, top, self.out("plain.gds"), None)
        self.assertEqual((r0.unread, r0.reads_as, r0.offgrid, r0.cross_cell), ([], [], [], []))
        self.assertEqual(r0.sha256, r.sha256)

    def test_error_marker_cells(self):
        ly = self.layout()
        top = ly.create_cell("TOP")
        bad = ly.create_cell("sky130_fd_pr__nfet_01v8__kmp_0123abcd")
        box(ly, bad, (255, 0), -0.5, -0.5, 0.5, 0.5)
        top.insert(db.DCellInstArray(bad.cell_index(), db.DTrans()))
        box(ly, top, M1, 0, 0, 1, 1)
        r = export_cell(ly, top, self.out(), self.data)
        self.assertEqual(r.error_markers, ["sky130_fd_pr__nfet_01v8__kmp_0123abcd"])
        self.assertIn("sky130_fd_pr__nfet_01v8__kmp_0123abcd", r.refusal())
        self.assertEqual(r.unread, [])  # 255/0 is listed once, as an error marker
        self.assertIsNone(export_cell(ly, bad, self.out(), mini_data(error_marker=[254, 0])).refusal())


@needs_klayout
class CrossCell(unittest.TestCase):
    """Magic decides device types inside each cell from that cell's own
    shapes, so a layer drawn in another cell is not there for it
    (design-0.6.md 2.6)."""

    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="kmp-b1-")
        self.data = mini_data()

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def two_level(self, parent_layers, child_layers):
        """A transistor-like child (diffusion 0..2 x 0..1, poly over it)
        placed at (10, 0) in a parent; each list says where nsdm and nwell
        go."""
        ly = db.Layout()
        ly.dbu = 0.001
        parent = ly.create_cell("inv_h")
        child = ly.create_cell("inv_dev")
        box(ly, child, DIFF, 0, 0, 2, 1)
        box(ly, child, POLY, 0.9, -0.2, 1.1, 1.2)
        box(ly, child, LICON, 0.2, 0.4, 0.37, 0.57)
        box(ly, child, M1, 0, 2, 2, 2.5)
        for ld in child_layers:
            box(ly, child, ld, -0.2, -0.2, 2.2, 1.2)
        for ld in parent_layers:
            box(ly, parent, ld, 9.8, -0.2, 12.2, 1.2)
        parent.insert(db.DCellInstArray(child.cell_index(), db.DTrans(db.DVector(10, 0))))
        return ly, parent

    def cross(self, ly, top, flat=False):
        return export_cell(ly, top, os.path.join(self.d, "in.gds"), self.data, flat=flat)

    def test_implant_in_the_parent(self):
        ly, top = self.two_level([NSDM], [])
        r = self.cross(ly, top)
        self.assertEqual(len(r.cross_cell), 1)
        f = r.cross_cell[0]
        self.assertEqual((f["cell"], f["layer"], f["gds"], f["drawn_in"]),
                         ("inv_dev", "nsdm.drawing", [93, 44], "inv_h"))
        self.assertEqual(f["box"], db.DBox(10, -0.2, 12, 1.2))

    def test_well_in_the_parent_and_both(self):
        ly, top = self.two_level([NWELL], [])
        self.assertEqual([(f["layer"], f["drawn_in"]) for f in self.cross(ly, top).cross_cell],
                         [("nwell.drawing", "inv_h")])
        ly, top = self.two_level([NWELL, PSDM], [])
        self.assertEqual(sorted(f["layer"] for f in self.cross(ly, top).cross_cell),
                         ["nwell.drawing", "psdm.drawing"])

    def test_no_finding_when_the_cell_draws_the_layer_itself(self):
        ly, top = self.two_level([NSDM], [NSDM])
        r = self.cross(ly, top)
        self.assertEqual(r.cross_cell, [])
        self.assertEqual([f["cell"] for f in r.cross_cell_covered], ["inv_dev"])

    def test_no_finding_in_flat_mode_or_in_one_cell(self):
        ly, top = self.two_level([NSDM], [])
        self.assertEqual(self.cross(ly, top, flat=True).cross_cell, [])
        ly = db.Layout()
        one = ly.create_cell("one")
        box(ly, one, DIFF, 0, 0, 2, 1)
        box(ly, one, NSDM, -0.2, -0.2, 2.2, 1.2)
        self.assertEqual(self.cross(ly, one).cross_cell, [])

    def test_a_layer_over_other_shapes_only_is_no_finding(self):
        ly = db.Layout()
        ly.dbu = 0.001
        parent = ly.create_cell("P")
        child = ly.create_cell("C")
        box(ly, child, M1, 0, 0, 2, 1)
        box(ly, child, DIFF, 5, 0, 6, 1)
        box(ly, parent, NSDM, -0.2, -0.2, 2.2, 1.2)   # over the child's metal, not its diffusion
        parent.insert(db.DCellInstArray(child.cell_index(), db.DTrans()))
        self.assertEqual(self.cross(ly, parent).cross_cell, [])

    def test_a_cut_in_the_parent_over_the_childs_own_implant_is_no_finding(self):
        """The case suite's inv_pcell: the top cell puts a contact on each
        FET PCell's tap and runs metal over it; the PCell draws the tap's
        implant itself. Magic reads the top cell as drawn (the same devices
        as the flattened cell), so nothing is reported in either direction."""
        ly = db.Layout()
        ly.dbu = 0.001
        parent = ly.create_cell("inv_pcell")
        child = ly.create_cell("nfet__kmp_e044c2db")
        box(ly, child, DIFF, -0.875, -1.04, 0.875, -0.87)    # the PCell's tap
        box(ly, child, PSDM, -1, -1.165, 1, -0.745)          # and its own implant over it
        box(ly, child, NWELL, -1, 1, 1, 2)                   # a well away from the tap
        box(ly, child, DIFF, -0.5, 1.2, 0.5, 1.8)
        box(ly, parent, LICON, 2, 0.36, 2.17, 0.53)          # a cut on the tap, in the parent
        box(ly, parent, M1, 0, 0.155, 2.8, 0.605)
        parent.insert(db.DCellInstArray(child.cell_index(), db.DTrans(db.DVector(1.4, 1.4))))
        r = self.cross(ly, parent)
        self.assertEqual((r.cross_cell, r.cross_cell_covered), ([], []))
        # An implant the parent draws over the child's diffusion still is one.
        box(ly, parent, NSDM, 0.9, 2.6, 1.9, 3.2)
        r = self.cross(ly, parent)
        self.assertEqual([(f["cell"], f["layer"], f["drawn_in"]) for f in r.cross_cell],
                         [("nfet__kmp_e044c2db", "nsdm.drawing", "inv_pcell")])

    def test_a_well_counts_over_diffusion_only(self):
        """A well decides what diffusion is, not what poly is (the IHP PCell
        inverter: the top cell's NWell over a piece of the pmos PCell's gate
        poly outside the PCell's own NWell). Implants and markers still
        count over poly."""
        ly = db.Layout()
        ly.dbu = 0.001
        parent = ly.create_cell("inv_pcell")
        child = ly.create_cell("pmos__kmp_0123abcd")
        box(ly, child, DIFF, 0, 0, 2, 1)
        box(ly, child, POLY, 0.9, -0.3, 1.1, 1.3)          # the gate reaches 0.3 past the diffusion
        box(ly, child, NWELL, -0.3, -0.3, 2.3, 1.25)        # its own well stops 0.05 short of the poly
        box(ly, parent, NWELL, -1, -1, 6, 2)                # the parent's well covers all of it
        parent.insert(db.DCellInstArray(child.cell_index(), db.DTrans()))
        r = self.cross(ly, parent)
        self.assertEqual(r.cross_cell, [])
        # The parent's well over diffusion the child doesn't cover itself is a finding.
        box(ly, child, DIFF, 4, 0, 5, 1)
        self.assertEqual([(f["cell"], f["layer"], f["drawn_in"]) for f in self.cross(ly, parent).cross_cell],
                         [("pmos__kmp_0123abcd", "nwell.drawing", "inv_pcell")])
        # An implant over the same poly piece is one too.
        ly2 = db.Layout()
        ly2.dbu = 0.001
        p2 = ly2.create_cell("P")
        c2 = ly2.create_cell("C")
        box(ly2, c2, POLY, 0.9, -0.3, 1.1, 1.3)
        box(ly2, p2, NSDM, 0.5, 1.2, 1.5, 2)
        p2.insert(db.DCellInstArray(c2.cell_index(), db.DTrans()))
        self.assertEqual([(f["cell"], f["layer"]) for f in self.cross(ly2, p2).cross_cell],
                         [("C", "nsdm.drawing")])
        self.assertEqual(export.device_roles("well"), ("diffusion",))
        self.assertEqual(export.device_roles("implant"), ("diffusion", "poly"))

    def test_drawn_layers_and_box(self):
        ly = db.Layout()
        ly.dbu = 0.001
        top = ly.create_cell("T")
        child = ly.create_cell("C")
        box(ly, child, NSDM, 0, 0, 0.3, 1)
        child.shapes(ly.layer(67, 5)).insert(db.DText("A", 0.1, 0.1))
        ly.layer(68, 20)                                     # a layer with no shape
        top.insert(db.DCellInstArray(child.cell_index(), db.DTrans(db.DVector(1, 2))))
        r = self.cross(ly, top)
        self.assertEqual([(l, d, (rec or {}).get("name")) for l, d, rec in r.drawn],
                         [(67, 5, "li1.label"), (93, 44, "nsdm.drawing")])
        self.assertEqual(r.bbox, db.DBox(1, 2, 1.3, 3))

    def test_siblings_and_every_placement(self):
        ly = db.Layout()
        ly.dbu = 0.001
        top = ly.create_cell("ROW")
        dev = ly.create_cell("DEV")
        box(ly, dev, DIFF, 0, 0, 1, 1)
        imp = ly.create_cell("IMP")
        box(ly, imp, NSDM, 0, 0, 10, 1)
        for x in (0, 4, 20):
            top.insert(db.DCellInstArray(dev.cell_index(), db.DTrans(db.DVector(x, 0))))
        top.insert(db.DCellInstArray(imp.cell_index(), db.DTrans()))
        r = self.cross(ly, top)
        self.assertEqual(sorted((f["cell"], f["drawn_in"], f["box"].left) for f in r.cross_cell),
                         [("DEV", "IMP", 0.0), ("DEV", "IMP", 4.0)])


@needs_klayout
class LoadAndResolve(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="kmp-resolve-")

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_cells(self):
        ly = db.Layout()
        a = ly.create_cell("A")
        box(ly, a, M1, 0, 0, 1, 1)
        with self.assertRaises(ExportError):
            load_layout(os.path.join(self.d, "none.gds"))
        p = os.path.join(self.d, "one.gds")
        ly.write(p)
        back = load_layout(p)
        self.assertEqual([c.name for c in resolve_cells(back, None)], ["A"])
        self.assertEqual([c.name for c in resolve_cells(back, ["A", "A"])], ["A"])
        with self.assertRaises(ExportError) as cm:
            resolve_cells(back, ["A", "x/y", "nope"])
        self.assertEqual(cm.exception.missing, ["x/y", "nope"])
        b = ly.create_cell("B")
        box(ly, b, M1, 0, 0, 1, 1)
        with self.assertRaises(ExportError) as cm:
            resolve_cells(ly, [])
        self.assertEqual(cm.exception.tops, ["A", "B"])
        self.assertEqual([c.name for c in resolve_cells(ly, ["B", "A"])], ["B", "A"])
        bad = os.path.join(self.d, "bad.gds")
        with open(bad, "wb") as f:
            f.write(b"not a layout")
        with self.assertRaises(ExportError):
            load_layout(bad)

    def test_safe_names(self):
        self.assertEqual(export.safe_name("a.b", {"a.b"}), "a_b")
        self.assertEqual(export.safe_name("a.b", {"a_b", "a_b_1"}), "a_b_2")
        self.assertEqual(export.safe_name("é", set()), "_")


if __name__ == "__main__":
    unittest.main()
