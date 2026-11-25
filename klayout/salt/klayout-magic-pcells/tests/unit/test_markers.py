"""markers.py: report databases for the Marker Database Browser (no Magic
needed)."""

import os
import shutil
import tempfile
import unittest

from tests.unit._util import REPO, needs_klayout, db  # noqa: F401

if db is not None:
    from klayout_magic_pcells import markers
    from klayout_magic_pcells.export import ExportResult
    from klayout_magic_pcells.markers import Rdb


def items_by_category(r):
    """{category path as names: [(cell name, [value strings])]} of a loaded
    ReportDatabase."""
    def path(cat):
        names = []
        while cat is not None:
            names.insert(0, cat.name())
            cat = cat.parent()
        return tuple(names)
    out = {}
    for it in r.each_item():
        cat = r.category_by_id(it.category_id())
        cell = r.cell_by_id(it.cell_id())
        out.setdefault(path(cat), []).append((cell.name(), [v.to_s() for v in it.each_value()]))
    return out


@needs_klayout
class Database(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="kmp-rdb-")

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_categories_are_nested_and_made_once(self):
        r = Rdb("Magic DRC drc(full): inv", "sky130A, hierarchical", "python3 -m klayout_magic_pcells drc x.gds",
                "inv")
        a = r.category("netgen/pins")
        b = r.category("netgen/pins", "pins that differ")
        self.assertEqual(a.rdb_id(), b.rdb_id())
        self.assertEqual(b.description, "pins that differ")
        self.assertEqual(r.category("netgen").rdb_id(), a.parent().rdb_id())
        # A name with a / in it, as Magic's rule diff/tap.8
        c = r.category(("Magic DRC", "diff/tap.8"), "Diffusion to tap spacing")
        self.assertEqual(c.name(), "diff/tap.8")
        self.assertEqual(c.parent().name(), "Magic DRC")
        with self.assertRaises(ValueError):
            r.category("a//b")
        self.assertEqual((r.db.name(), r.db.top_cell_name, r.db.generator),
                         ("Magic DRC drc(full): inv", "inv", "python3 -m klayout_magic_pcells drc x.gds"))

    def test_items_counts_and_a_saved_database(self):
        r = Rdb("Magic DRC drc(full): inv", "description", "gen", "inv")
        rule = r.category(("Magic DRC", "nwell.1"), "N-well width < 0.84um (nwell.1)")
        r.item(rule, "inv", db.DBox(0, 0, 0.5, 3), "N-well width < 0.84um (nwell.1); allnwell 64/20")
        r.item(rule, "inv_dev", db.DPolygon(db.DBox(1, 1, 2, 2)))
        r.item(("Magic DRC", "licon.8"), "inv", db.DEdge(0, 0, 1, 0))
        r.info("Magic said", "Unknown layer/datatype in boundary, layer=3 type=0")
        self.assertEqual(r.count(), 4)
        self.assertEqual(r.count(rule), 2)
        self.assertEqual(r.count("Magic DRC"), 3)
        self.assertEqual(r.count("Magic said"), 1)
        self.assertIs(r.cell("inv"), r.cell("inv"))
        path = os.path.join(self.d, "inv.lyrdb")
        r.save(path)
        back = markers.load(path)
        self.assertEqual(back.num_items(), 4)
        got = items_by_category(back)
        self.assertEqual(sorted(got), [("Magic DRC", "licon.8"), ("Magic DRC", "nwell.1"), ("Magic said",)])
        nwell = sorted(got[("Magic DRC", "nwell.1")])
        self.assertEqual([c for c, _ in nwell], ["inv", "inv_dev"])
        self.assertIn("box: (0,0;0.5,3)", nwell[0][1])
        self.assertIn("text: 'N-well width < 0.84um (nwell.1); allnwell 64/20'", nwell[0][1])
        self.assertTrue(nwell[1][1][0].startswith("polygon:"))
        self.assertTrue(got[("Magic DRC", "licon.8")][0][1][0].startswith("edge:"))
        self.assertEqual(got[("Magic said",)][0][0], "inv")
        descs = {c.name(): c.description for c in back.each_category()}
        self.assertEqual(descs["Magic DRC"], "")

    def test_export_findings(self):
        er = ExportResult()
        er.klayout_top = "inv"
        er.name_map = {"inv": "inv", "a.b": "a_b"}
        er.offgrid = [("68/20 (met1.drawing)", db.DBox(2.001, 0, 2.001, 0))]
        er.unread = [(64, 44, db.DBox(0, 0, 1, 1))]
        er.reads_as = [(16, 0, "digisub", db.DBox(0, 10, 4, 14))]
        er.cross_cell = [{"cell": "inv_dev", "layer": "nsdm.drawing", "gds": [93, 44], "drawn_in": "inv_h",
                          "box": db.DBox(10, -0.2, 12, 1.2)}]
        er.error_markers = ["bad__kmp_01234567"]
        er.flattened = [("inv", "instance of rotme at (0, 10) rotated 45°: ...")]
        r = Rdb("x", "", "", "inv")
        self.assertEqual(markers.add_export_findings(r, er), 7)
        self.assertEqual(r.count(markers.CAT_CROSS_CELL), 1)
        path = os.path.join(self.d, "e.lyrdb")
        r.save(path)
        got = items_by_category(markers.load(path))
        for cat in ("Magic snaps this shape to its 5 nm grid", "Magic does not read this layer",
                    "Magic reads this layer as another type",
                    "Magic reads this cell without a layer drawn in another cell", "error-marker cells",
                    "instances flattened for Magic", "cells renamed for Magic"):
            self.assertIn(("Export", cat), got)
        cross = got[("Export", "Magic reads this cell without a layer drawn in another cell")][0]
        self.assertEqual(cross[0], "inv")
        self.assertIn("text: 'Magic reads cell inv_dev without the nsdm.drawing drawn in cell inv_h'", cross[1])
        self.assertIn("text: 'a.b is a_b in the file Magic reads'",
                      got[("Export", "cells renamed for Magic")][0][1])

    def test_a_cell_magic_reads_nothing_in(self):
        er = ExportResult()
        er.klayout_top = "s_nsdm_alone"
        er.top = "s_nsdm_alone"
        er.bbox = db.DBox(0, 0, 0.3, 1)
        er.drawn = [(93, 44, {"name": "nsdm.drawing", "read": "device-only", "line": "sky130A.tech:3725"}),
                    (95, 20, {"name": "npc.drawing", "read": "ignored"}), (200, 7, None)]
        er.regenerated = {(95, 20)}
        r = Rdb("x", "", "", "s_nsdm_alone")
        text = markers.add_reads_nothing(r, er)
        self.assertEqual(r.count(markers.CAT_READS_NOTHING), 1)
        self.assertEqual(markers.CAT_READS_NOTHING, "Export/Magic reads nothing in this cell")
        self.assertTrue(text.startswith("Magic reads nothing in cell s_nsdm_alone. Its layers: "), text)
        self.assertIn("93/44 (nsdm.drawing): Magic's reader uses it only to decide what the diffusion or poly "
                      "under it is, and this cell has none (sky130A.tech:3725)", text)
        self.assertIn("95/20 (npc.drawing): Magic's reader ignores it (and draws its own when it writes GDS)", text)
        self.assertIn("200/7: the PDK data has no row for it, so Magic's reader does not know it", text)
        path = os.path.join(self.d, "n.lyrdb")
        r.save(path)
        (cell, values), = items_by_category(markers.load(path))[("Export", "Magic reads nothing in this cell")]
        self.assertEqual(cell, "s_nsdm_alone")
        self.assertTrue(any(v.startswith("box: ") for v in values), values)

    def test_empty_cell_error(self):
        self.assertTrue(markers.empty_cell_error("cell s_hvtp_alone is empty", "s_hvtp_alone"))
        self.assertTrue(markers.empty_cell_error("cell T has an empty bounding box", "T"))
        self.assertFalse(markers.empty_cell_error("cell T is empty", "U"))
        self.assertFalse(markers.empty_cell_error("load T failed: x", "T"))
        self.assertFalse(markers.empty_cell_error(None, "T"))

    def test_many_findings_are_capped(self):
        er = ExportResult()
        er.klayout_top = "T"
        er.offgrid = [("68/20", db.DBox(i, 0, i, 0)) for i in range(7)] + [("69/20", db.DBox(0, 0, 0, 0))]
        old = markers.MAX_ITEMS_PER_LAYER
        markers.MAX_ITEMS_PER_LAYER = 3
        try:
            r = Rdb("x", "", "", "T")
            markers.add_export_findings(r, er)
        finally:
            markers.MAX_ITEMS_PER_LAYER = old
        self.assertEqual(r.count(markers.CAT_OFFGRID), 5)   # 3 + 1, and one "4 more" item

    def test_magic_said(self):
        r = Rdb("x", "", "", "T")
        n = markers.add_magic_said(r, ["Warning: Calma reading is not undoable!", "", "KMP_JOB_DONE 1",
                                       "Warning: Calma reading is not undoable!"])
        self.assertEqual((n, r.count(markers.CAT_MAGIC_SAID)), (1, 1))
        self.assertEqual(r.count_info(markers.CAT_MAGIC_SAID), 1)

    def test_long_texts_go_in_lines(self):
        """KLayout's Info pane shows each text value on a line of its own, does
        not wrap it, and cuts it after 200 characters."""
        f2 = ("The gate at (1.350, 1.300): it is outside nwell, but Magic reads it as sky130_fd_pr__pfet_01v8 "
              "W 0.650 L 0.150. The gate has no nsdm over its diffusion, and Magic reads every such gate as a "
              "pfet, whatever the well (sky130A.tech:2597). To fix it, draw nsdm (93/44) over the n-diffusion, "
              "0.125 um past it.")
        lines = markers.text_lines(f2)
        self.assertEqual(" ".join(lines), f2)
        self.assertTrue(all(len(ln) <= markers.LINE_WIDTH for ln in lines), lines)
        self.assertEqual(lines[-1], "To fix it, draw nsdm (93/44) over the n-diffusion, 0.125 um past it.")
        self.assertEqual(markers.text_lines("short (x.1)"), ["short (x.1)"])
        r = Rdb("x", "", "", "inv")
        it = r.item("F2 transistor Magic reads as another device or none", "inv", db.DBox(0, 0, 1, 1), f2)
        values = [v.string() for v in it.each_value() if v.is_string()]
        self.assertEqual(values, lines)
        self.assertTrue(all(len(v) < 200 for v in values))
        self.assertEqual(markers.item_text(it), f2)

    def test_information_items_are_waived_and_visited(self):
        """Items that are not findings of the check: KLayout's
        browser shows them as waived, and a category of them in green."""
        er = ExportResult()
        er.klayout_top = "inv"
        er.unread = [(95, 20, db.DBox(0, 0, 1, 1))]
        er.offgrid = [("68/20 (met1.drawing)", db.DBox(2.001, 0, 2.001, 0))]
        r = Rdb("x", "", "", "inv")
        r.item("Magic DRC/li.5", "inv", db.DBox(0, 0, 1, 1), "li.5")
        markers.add_export_findings(r, er, counted=(markers.CAT_OFFGRID,))
        items = {r.db.category_by_id(it.category_id()).path(): it for it in r.db.each_item()}
        unread = items["Export.'Magic does not read this layer'"]
        self.assertIn("waived", unread.tags_str)
        self.assertTrue(unread.is_visited())
        for path in ("'Magic DRC'.'li.5'", "Export.'Magic snaps this shape to its 5 nm grid'"):
            self.assertEqual(items[path].tags_str, "", path)
            self.assertFalse(items[path].is_visited(), path)
        self.assertEqual((r.count(), r.count_info()), (3, 1))
        path = os.path.join(self.d, "w.lyrdb")
        r.save(path)
        back = markers.load(path)
        tags = sorted(it.tags_str for it in back.each_item())
        self.assertEqual(tags, ["", "", "waived"])


if __name__ == "__main__":
    unittest.main()
