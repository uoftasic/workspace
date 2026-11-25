"""portcheck.py: P1 to P7 on synthetic layouts, per PDK, with the shipped
ports tables. No Magic needed."""

import os
import tempfile
import unittest

from tests.unit._util import needs_klayout, db  # noqa: F401

if db is not None:
    from klayout_magic_pcells import markers, portcheck, pdkdata

# Per PDK: a conductor's drawing, its text and pin layers, the form both
# tools accept, and a text layer neither reads (design-0.6.md 3.4; the data
# files' ports tables).
FORMS = {
    "sky130A": {"draw": (67, 20), "text": (67, 5), "pin": (67, 16), "neither": (67, 98)},
    "gf180mcuD": {"draw": (34, 0), "text": (34, 0), "pin": (34, 10), "neither": (34, 98)},
    "ihp-sg13g2": {"draw": (8, 0), "text": (8, 25), "pin": (8, 2), "neither": (8, 1)},
    "ihp-sg13cmos5l": {"draw": (8, 0), "text": (8, 25), "pin": (8, 2), "neither": (8, 1)},
}
PDKS = tuple(FORMS)


def layout(shapes=(), texts=(), sub=None):
    """shapes: [((l, d), (l, b, r, t))]; texts: [((l, d), "A", x, y)];
    sub: (cell name, shapes, texts, (dx, dy)) placed in TOP."""
    ly = db.Layout()
    ly.dbu = 0.001
    top = ly.create_cell("TOP")

    def fill(cell, shapes, texts):
        for ld, b in shapes:
            cell.shapes(ly.layer(*ld)).insert(db.DBox(*b))
        for ld, s, x, y in texts:
            cell.shapes(ly.layer(*ld)).insert(db.DText(s, x, y))
    fill(top, shapes, texts)
    if sub:
        name, sshapes, stexts, (dx, dy) = sub
        c = ly.create_cell(name)
        fill(c, sshapes, stexts)
        top.insert(db.DCellInstArray(c.cell_index(), db.DTrans(db.DVector(dx, dy))))
    return ly, top


def checks(pdk, ly, top, ports=None):
    return sorted(f["check"] for f in portcheck.check_layout(ly, top, pdkdata.load(pdk), ports))


BOX = (0.0, 0.0, 1.0, 1.0)
PINBOX = (0.2, 0.2, 0.5, 0.5)


@needs_klayout
class Conventions(unittest.TestCase):
    def test_the_form_both_accept_is_clean(self):
        for pdk, f in FORMS.items():
            with self.subTest(pdk=pdk):
                shapes = [(f["draw"], BOX)]
                if pdk != "gf180mcuD":
                    shapes.append((f["pin"], PINBOX))
                texts = [(f["pin"] if pdk == "gf180mcuD" else f["text"], "A", 0.3, 0.3)]
                ly, top = layout(shapes, texts)
                self.assertEqual(checks(pdk, ly, top), [])

    def test_p1_a_text_neither_reads(self):
        for pdk in ("ihp-sg13g2", "ihp-sg13cmos5l"):
            f = FORMS[pdk]
            ly, top = layout([(f["draw"], BOX)], [(f["neither"], "A", 0.3, 0.3)])
            self.assertEqual(checks(pdk, ly, top), ["P1"])

    def test_p2_a_net_name_without_a_port(self):
        for pdk, ld in (("sky130A", (67, 5)), ("sky130A", (67, 20)), ("gf180mcuD", (34, 0)),
                        ("ihp-sg13g2", (8, 25)), ("ihp-sg13cmos5l", (8, 0))):
            with self.subTest(pdk=pdk, layer=ld):
                ly, top = layout([(FORMS[pdk]["draw"], BOX)], [(ld, "A", 0.3, 0.3)])
                found = portcheck.check_layout(ly, top, pdkdata.load(pdk))
                self.assertEqual([x["check"] for x in found], ["P2"])
                self.assertIn("form both accept", found[0]["text"]) if pdk != "gf180mcuD" else None

    def test_p3_a_magic_port_klayout_cannot_name(self):
        for pdk in ("sky130A", "ihp-sg13g2", "ihp-sg13cmos5l"):
            f = FORMS[pdk]
            with self.subTest(pdk=pdk):
                ly, top = layout([(f["draw"], BOX), (f["pin"], PINBOX)], [(f["pin"], "A", 0.3, 0.3)])
                self.assertEqual(checks(pdk, ly, top), ["P3"])
        ly, top = layout([((21, 0), (0, 0, 3, 3))], [((21, 10), "VNW", 1, 1)])
        self.assertEqual(checks("gf180mcuD", ly, top), ["P3"])

    def test_p4_a_pin_box_without_text(self):
        for pdk in ("sky130A", "ihp-sg13g2"):
            f = FORMS[pdk]
            ly, top = layout([(f["draw"], BOX), (f["pin"], PINBOX)])
            self.assertEqual(checks(pdk, ly, top), ["P4"])

    def test_foundry_cell_texts_and_pin_boxes(self):
        """sky130_fd_sc_hd__inv_1 as the foundry draws it: the cell's name on
        text.drawing (83/44), which Magic reads as a comment that names no
        net, and VNB on pwell.label (64/59) over a pwell.pin (122/16) box,
        the form both tools accept. Neither is a finding."""
        ly, top = layout([((64, 20), (-0.19, 1.305, 1.57, 2.91)), ((122, 16), (0.145, -0.085, 0.315, 0.085))],
                         [((83, 44), "inv_1", 0.0, 0.0), ((64, 59), "VNB", 0.23, 0.0)])
        self.assertEqual(checks("sky130A", ly, top), [])
        # Without its text the pwell.pin box is a P4 again.
        ly, top = layout([((122, 16), (0.145, -0.085, 0.315, 0.085))], [])
        self.assertEqual(checks("sky130A", ly, top), ["P4"])
        # IHP's TEXT.drawing (63/0) is a comment to Magic too.
        f = FORMS["ihp-sg13g2"]
        ly, top = layout([(f["draw"], BOX)], [((63, 0), "sub!", 0.3, 0.3)])
        self.assertEqual(checks("ihp-sg13g2", ly, top), [])

    def test_headline(self):
        """The GUI message's first line names the texts in plain words."""
        f = FORMS["sky130A"]
        ly, top = layout([(f["draw"], BOX)], [(f["text"], "A", 0.3, 0.3), (f["text"], "Y", 0.6, 0.6)])
        found = portcheck.check_layout(ly, top, pdkdata.load("sky130A"))
        self.assertEqual(portcheck.headline(found, "TOP"),
                         "In TOP: 2 texts that name nets in Magic but make no pins (A, Y).")
        self.assertEqual(portcheck.headline([], "TOP"), "No port findings in TOP.")

    def test_p5_a_pin_box_without_drawing(self):
        for pdk in ("sky130A", "ihp-sg13g2", "ihp-sg13cmos5l"):
            f = FORMS[pdk]
            with self.subTest(pdk=pdk):
                ly, top = layout([(f["draw"], BOX), (f["pin"], (0.8, 0.2, 1.3, 0.5))], [(f["text"], "A", 0.9, 0.3)])
                self.assertEqual(checks(pdk, ly, top), ["P5"])

    def test_p6_a_text_over_nothing(self):
        for pdk, f in FORMS.items():
            with self.subTest(pdk=pdk):
                ld = f["pin"] if pdk == "gf180mcuD" else f["text"]
                ly, top = layout([(f["draw"], BOX)], [(ld, "A", 5.0, 5.0)])
                self.assertIn("P6", checks(pdk, ly, top))

    def test_p6_looks_through_the_hierarchy(self):
        f = FORMS["sky130A"]
        # A top-cell text over a subcell's li and pin box is a port (design-0.6.md 3.4).
        ly, top = layout([], [(f["text"], "A", 10.3, 0.3)],
                         sub=("leaf", [(f["draw"], BOX)], [], (10.0, 0.0)))
        self.assertEqual(checks("sky130A", ly, top), ["P2"])
        ly, top = layout([(f["pin"], (10.2, 0.2, 10.5, 0.5))], [(f["text"], "A", 10.3, 0.3)],
                         sub=("leaf", [(f["draw"], BOX)], [], (10.0, 0.0)))
        self.assertEqual(checks("sky130A", ly, top), [])
        ly, top = layout([], [(f["text"], "A", 20.3, 0.3)],
                         sub=("leaf", [(f["draw"], BOX)], [], (10.0, 0.0)))
        self.assertIn("P6", checks("sky130A", ly, top))

    def test_each_cell_is_checked(self):
        f = FORMS["sky130A"]
        ly, top = layout([], [], sub=("leaf", [(f["draw"], BOX)], [(f["text"], "A", 0.3, 0.3)], (0.0, 0.0)))
        found = portcheck.check_layout(ly, top, pdkdata.load("sky130A"))
        self.assertEqual([(x["check"], x["cell"]) for x in found], [("P2", "leaf")])

    def test_p7_texts_in_device_cells(self):
        f = FORMS["ihp-sg13g2"]
        ly, top = layout([(f["draw"], BOX)], [],
                         sub=("sg13_lv_nmos__kmp_0123abcd", [(f["draw"], BOX)], [(f["text"], "S", 0.3, 0.3)], (0, 0)))
        found = portcheck.check_layout(ly, top, pdkdata.load("ihp-sg13g2"))
        self.assertEqual([x["check"] for x in found], ["P7"])
        self.assertIn("doports 0", found[0]["text"])

    def test_p8_a_pin_missing_from_magics_ports(self):
        f = FORMS["sky130A"]
        ly, top = layout([(f["draw"], BOX), (f["pin"], PINBOX)], [(f["text"], "A", 0.3, 0.3)])
        self.assertEqual(checks("sky130A", ly, top, ports=["A"]), [])
        self.assertEqual(checks("sky130A", ly, top, ports=["Y"]), ["P8"])

    def test_subckt_ports(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "inv.spice")
        with open(p, "w") as fh:
            fh.write("* x\n.subckt inv A Y\n+ VPWR VGND\nX0 Y A VGND VGND nfet w=1 l=1\n.ends\n")
        self.assertEqual(portcheck.subckt_ports(p, "inv"), ["A", "Y", "VPWR", "VGND"])
        self.assertIsNone(portcheck.subckt_ports(p, "nand"))


if __name__ == "__main__":
    unittest.main()


@needs_klayout
class Prepare(unittest.TestCase):
    """prepare() never raises (design-0.6.md 2.4): a failed export gives a Task whose
    outcome has status 2 and the reason in the RDB and the summary; with
    --magic a refused layout keeps its export findings. No Magic needed."""

    def setUp(self):
        import types
        self.data = pdkdata.load("sky130A")
        self.cfg = types.SimpleNamespace(pdk="sky130A", cache_dir=tempfile.mkdtemp(prefix="kmp-prep-"))
        self.ly, self.top = layout([((67, 20), BOX)], [((67, 5), "A", 0.5, 0.5)])

    def tearDown(self):
        import shutil
        shutil.rmtree(self.cfg.cache_dir, ignore_errors=True)

    def failed(self, task, text):
        o = task.start().wait()
        self.assertEqual(o.status, 2, o.summary)
        self.assertTrue(o.summary.startswith("ports: "), o.summary)
        self.assertIn(text, o.summary)
        self.assertEqual(o.rdb.count("Job/failed"), 1)
        said = [markers.item_text(it) for it in o.rdb.db.each_item()]
        self.assertTrue(any(text in s for s in said), said)
        return o

    def test_a_cell_not_in_the_layout(self):
        for magic in (False, True):
            with self.subTest(magic=magic):
                self.failed(portcheck.prepare(self.ly, "nope", self.cfg, self.data, {"magic": magic}),
                            "cell nope is not in the layout")

    def test_an_export_error(self):
        from klayout_magic_pcells import export
        real = export.export_cell

        def boom(*a, **k):
            raise export.ExportError("copying TOP renamed the cells x")
        export.export_cell = boom
        try:
            t = portcheck.prepare(self.ly, self.top, self.cfg, self.data, {})
        finally:
            export.export_cell = real
        self.failed(t, "copying TOP renamed the cells x")

    def test_a_refused_layout(self):
        bad = self.ly.create_cell("bad__kmp_01234567")
        bad.shapes(self.ly.layer(255, 0)).insert(db.DBox(0, 0, 1, 1))
        self.top.insert(db.DCellInstArray(bad.cell_index(), db.DTrans()))
        o = self.failed(portcheck.prepare(self.ly, self.top, self.cfg, self.data, {"magic": True}), "bad__kmp_01234567")
        self.assertEqual(o.rdb.count("Export/error-marker cells"), 1)
        # Without --magic no job runs, so P1 to P7 run as before.
        o = portcheck.prepare(self.ly, self.top, self.cfg, self.data, {}).start().wait()
        self.assertNotEqual(o.status, 2, o.summary)
