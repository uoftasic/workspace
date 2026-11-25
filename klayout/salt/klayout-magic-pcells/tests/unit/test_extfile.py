"""extfile.py: reading Magic's .ext files and placing nets and devices.

The fixtures are .ext files Magic 8.3.681 wrote in this build's runs of
tcl/kmp_extract.tcl on the case suite (lines trimmed to the fields read).
The use-line table (USE_*) is the measurement of the use line's
transform: a child cell in all eight orientations and a 3 x 2 array,
written by KLayout, extracted by Magic, each node point checked to lie on
its own KLayout placement on all four PDKs.
"""

import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "python"))

from klayout_magic_pcells import extfile  # noqa: E402

UNIT = 0.004999999888241291   # KMP_JOB_SCALE on all four PDKs

# sky130A inverters/inv_open_drain.ext
SKY_OPEN = """\
timestamp 2083210096
version 8.3
tech sky130A
style ngspice()
scale 1000 1 500000
parameters sky130_fd_pr__nfet_01v8 l=l w=w a1=as p1=ps a2=ad p2=pd
port "Y" 3 450 520 500 570 li
port "A" 2 260 480 310 530 li
port "VPWR" 4 240 1140 290 1190 m1
port "VGND" 5 240 10 290 60 m1
node "a_300_260#" 229 0 300 260 ndif 0 0 0 0 0 0 0 0 28600 700 0 0
node "Y" 274 0 450 520 li 0 0 0 0 0 0 0 0 0 0 44000 840
node "A" 1117 0 260 480 li 0 0 0 0
node "VPWR" 1761 0 240 1140 m1 0 0 0 0 360000 2400
substrate "VGND" 1104 0 240 10 m1 0 0 0 0 0 0 0 0 24700 640
device msubckt sky130_fd_pr__nfet_01v8 270 260 271 261 l=30 w=130 "VGND" "A" 60 0 "VGND" 130 24700,640 "a_300_260#" 130 28600,700
device msubckt sky130_fd_pr__pfet_01v8_hvt 270 700 271 701 l=30 w=200 "VPWR" "A" 60 0 "VPWR" 200 38000,780 "Y" 200 44000,840
"""

# gf180mcuD inverters/inv_open_drain.ext: the scale line's third number is 0.5.
GF_OPEN = """\
tech gf180mcuD
scale 1000 1 0.5
port "Y" 2 230 260 230 260 m1
port "A" 1 0 260 0 260 m1
node "a_28_0#" 7 0 28 0 ndif 0 0 0 0 12960 456
node "Y" 8 0 230 260 m1 0 0 0 0
substrate "VSS" 14 0 -200 60 m1 0 0 0 0
device msubckt nfet_03v3 -28 0 -27 1 l=56 w=120 "VSS" "A" 112 0 "VSS" 120 12960,456 "a_28_0#" 120 12960,456
"""

# sky130A inverters/inv_pcell.ext and one of its PCell variants.
SKY_PCELL_TOP = """\
tech sky130A
scale 1000 1 500000
use sky130_fd_pr__pfet_01v8_hvt__kmp_76981a85 sky130_fd_pr__pfet_01v8_hvt__kmp_76981a85_0 1 0 280 0 1 920
use sky130_fd_pr__nfet_01v8__kmp_e044c2db sky130_fd_pr__nfet_01v8__kmp_e044c2db_0 1 0 280 0 1 280
port "A" 1 260 560 300 600 m1
port "Y" 2 3 582 43 622 m1
port "VGND" 3 40 56 80 96 m1
node "A" 1 0 260 560 m1 0 0
node "Y" 3 0 3 582 m1 0 0
node "VGND" 14 0 40 56 m1 0 0
substrate "VSUBS" 0 0 -1073741817 -1073741817 space 0 0
merge "sky130_fd_pr__nfet_01v8__kmp_e044c2db_0/B" "sky130_fd_pr__pfet_01v8_hvt__kmp_76981a85_0/VSUBS" 0 0
merge "sky130_fd_pr__pfet_01v8_hvt__kmp_76981a85_0/VSUBS" "VSUBS"
merge "VSUBS" "VGND"
merge "sky130_fd_pr__nfet_01v8__kmp_e044c2db_0/D" "sky130_fd_pr__pfet_01v8_hvt__kmp_76981a85_0/D" 0 0
merge "sky130_fd_pr__pfet_01v8_hvt__kmp_76981a85_0/D" "Y"
"""
SKY_PCELL_NFET = """\
tech sky130A
scale 1000 1 500000
node "S" 321 0 15 -96 ndif 0 0
node "D" 321 0 -73 -96 ndif 0 0
node "G" 400 0 -33 56 p 0 0
substrate "B" 8189 0 -175 -208 ppd 0 0
device msubckt sky130_fd_pr__nfet_01v8 -15 -96 -14 -95 l=30 w=130 "B" "G" 60 0 "D" 130 7540,376 "S" 130 7540,376
"""
SKY_PCELL_SPICE = """\
* NGSPICE file created from inv_pcell.ext - technology: sky130A

.subckt sky130_fd_pr__nfet_01v8__kmp_e044c2db G D B S
X0 S G D B sky130_fd_pr__nfet_01v8 ad=0.1885 pd=1.88 as=0.1885 ps=1.88 w=0.65 l=0.15
.ends

.subckt inv_pcell A Y VGND VPWR
Xsky130_fd_pr__pfet_01v8_hvt__kmp_76981a85_0 A Y VPWR VPWR sky130_fd_pr__pfet_01v8_hvt__kmp_76981a85
Xsky130_fd_pr__nfet_01v8__kmp_e044c2db_0 A Y VGND VGND
+ sky130_fd_pr__nfet_01v8__kmp_e044c2db
.ends
"""

# The use-line table: CHILD's one node, and TOP's use lines; the expected
# points are where the node falls on each KLayout placement, in um.
USE_CHILD = 'scale 1000 1 0.5\nnode "m1_100_60#" 1 0 100 60 m1 0 0\n'
USE_TOP = """\
scale 1000 1 0.5
use CHILD CHILD_0[0:1:1400][0:2:1200] 0 -1 4400 1 0 8000
use CHILD CHILD_1 0 -1 13200 -1 0 5200
use CHILD CHILD_2 -1 0 11600 0 1 4600
use CHILD CHILD_3 0 1 10000 1 0 4000
use CHILD CHILD_4 1 0 8400 0 -1 3400
use CHILD CHILD_5 0 1 6800 -1 0 2800
use CHILD CHILD_6 -1 0 5200 0 -1 2200
use CHILD CHILD_7 0 -1 3600 1 0 1600
use CHILD CHILD_8 1 0 2000 0 1 1000
"""
USE_EXPECT = {
    "CHILD_0[0][0]": (21.7, 40.5), "CHILD_0[0][1]": (15.7, 40.5), "CHILD_0[0][2]": (9.7, 40.5),
    "CHILD_0[1][0]": (21.7, 47.5), "CHILD_0[1][1]": (15.7, 47.5), "CHILD_0[1][2]": (9.7, 47.5),
    "CHILD_1": (65.7, 25.5), "CHILD_2": (57.5, 23.3), "CHILD_3": (50.3, 20.5), "CHILD_4": (42.5, 16.7),
    "CHILD_5": (34.3, 13.5), "CHILD_6": (25.5, 10.7), "CHILD_7": (17.7, 8.5), "CHILD_8": (10.5, 5.3),
}


def ext(cells, top):
    return extfile.Extraction({n: extfile.parse(t, n) for n, t in cells.items()}, top, UNIT)


class ParseTest(unittest.TestCase):
    def test_lines(self):
        c = extfile.parse(SKY_OPEN, "inv_open_drain")
        self.assertEqual(c.tech, "sky130A")
        self.assertEqual(c.scale_line, (1000.0, 1.0, 500000.0))
        self.assertEqual([p.name for p in c.ports], ["Y", "A", "VPWR", "VGND"])
        self.assertEqual(c.port("Y").box, (450, 520, 500, 570))
        self.assertEqual(c.port("Y").type, "li")
        n = c.nodes["a_300_260#"]
        self.assertEqual((n.x, n.y, n.type, n.substrate), (300, 260, "ndif", False))
        self.assertTrue(c.nodes["VGND"].substrate)
        self.assertEqual([s.name for s in c.substrate], ["VGND"])
        d = c.devices[0]
        self.assertEqual((d.cls, d.model, d.x, d.y), ("msubckt", "sky130_fd_pr__nfet_01v8", 270, 260))
        self.assertEqual(d.params, {"l": "30", "w": "130"})
        self.assertEqual(d.terminals, ["VGND", "A", "VGND", "a_300_260#"])
        self.assertEqual(c.devices[1].index, 1)

    def test_infinite_substrate(self):
        c = extfile.parse(SKY_PCELL_TOP, "inv_pcell")
        self.assertIsNone(c.nodes["VSUBS"].point)
        self.assertEqual(c.aliases("VSUBS")[:2], ["VSUBS", "sky130_fd_pr__pfet_01v8_hvt__kmp_76981a85_0/VSUBS"])
        self.assertIn("VGND", c.aliases("VSUBS"))

    def test_use_lines(self):
        c = extfile.parse(USE_TOP, "TOP")
        u = c.use("CHILD_0")
        self.assertEqual(u.cell, "CHILD")
        self.assertEqual(u.array, (0, 1, 1400, 0, 2, 1200))
        self.assertEqual(u.trans, (0, -1, 4400, 1, 0, 8000))
        self.assertEqual(len(u.elements()), 6)
        self.assertIsNone(c.use("CHILD_1").array)

    def test_bad_line(self):
        with self.assertRaises(extfile.ExtError):
            extfile.parse('port "Y" 3 450\n', "x")

    def test_read_dir(self):
        d = tempfile.mkdtemp()
        try:
            for name, text in (("inv_pcell", SKY_PCELL_TOP), ("sky130_fd_pr__nfet_01v8__kmp_e044c2db", SKY_PCELL_NFET)):
                with open(os.path.join(d, name + ".ext"), "w") as f:
                    f.write(text)
            with open(os.path.join(d, "netlist.spice"), "w") as f:
                f.write(SKY_PCELL_SPICE)
            cells = extfile.read_dir(d)
            self.assertEqual(sorted(cells), ["inv_pcell", "sky130_fd_pr__nfet_01v8__kmp_e044c2db"])
            e = extfile.Extraction.from_dir(d, "inv_pcell", UNIT)
            self.assertEqual(e.top, "inv_pcell")
            sp = extfile.spice_devices(os.path.join(d, "netlist.spice"))
            self.assertEqual(sp["inv_pcell"]["Xsky130_fd_pr__nfet_01v8__kmp_e044c2db_0"]["model"],
                             "sky130_fd_pr__nfet_01v8__kmp_e044c2db", "continuation lines are joined")
            self.assertEqual(sp["sky130_fd_pr__nfet_01v8__kmp_e044c2db"]["X0"]["nets"], ["S", "G", "D", "B"])
        finally:
            for n in os.listdir(d):
                os.unlink(os.path.join(d, n))
            os.rmdir(d)


class UnitTest(unittest.TestCase):
    """The unit is the job's [cif scale out], never the scale line (design-0.6.md 6.5)."""

    def assertPoint(self, got, want, places=3):
        self.assertAlmostEqual(got[0], want[0], places)
        self.assertAlmostEqual(got[1], want[1], places)

    def test_sky130A(self):
        e = ext({"inv_open_drain": SKY_OPEN}, "inv_open_drain")
        name, box, typ = e.ports()[0]
        self.assertEqual((name, typ), ("Y", "li"))
        for got, want in zip(box, (2.25, 2.60, 2.50, 2.85)):
            self.assertAlmostEqual(got, want, 4)
        # the GDS text Y at (2.375, 2.725) lies in the box (design-0.6.md 3.2)
        self.assertTrue(box[0] <= 2.375 <= box[2] and box[1] <= 2.725 <= box[3])
        loc = e.locate_net("a_300_260#")
        self.assertPoint(loc.point, (1.50, 1.30))
        self.assertEqual(loc.type, "ndif")
        self.assertAlmostEqual(e.um(int(e.cells["inv_open_drain"].devices[0].params["w"])), 0.65, 4)

    def test_gf180_scale_line_is_not_the_unit(self):
        e = ext({"inv": GF_OPEN}, "inv")
        self.assertEqual(e.cells["inv"].scale_line[2], 0.5)
        name, box, _t = e.ports()[0]
        # gf180mcuD's port is the text's point: Y at (1.15, 1.30) um, not 5e-9 um units
        self.assertPoint(box[:2], (1.15, 1.30))
        self.assertPoint(e.locate_net("a_28_0#").point, (0.14, 0.0))

    def test_no_unit(self):
        with self.assertRaises(extfile.ExtError):
            extfile.Extraction({"x": extfile.parse(SKY_OPEN, "x")}, "x", None)
        with self.assertRaises(extfile.ExtError):
            extfile.Extraction({"x": extfile.parse(SKY_OPEN, "x")}, "y", UNIT)


class PlaceTest(unittest.TestCase):
    def assertPoint(self, got, want, places=3):
        self.assertAlmostEqual(got[0], want[0], places, (got, want))
        self.assertAlmostEqual(got[1], want[1], places, (got, want))

    def test_u10_every_orientation_and_array(self):
        e = ext({"TOP": USE_TOP, "CHILD": USE_CHILD}, "TOP")
        for elem, want in USE_EXPECT.items():
            self.assertPoint(e.locate_net(elem + "/m1_100_60#").point, want)
        # netgen's flattened names keep the X of the SPICE instance
        self.assertPoint(e.locate_net("XCHILD_3/m1_100_60#").point, USE_EXPECT["CHILD_3"])
        self.assertPoint(e.locate_net("CHILD_0[1,2]/m1_100_60#").point, USE_EXPECT["CHILD_0[1][2]"])
        found = e.instances(lambda c: c == "CHILD")
        self.assertEqual(len(found), 14)
        pts = sorted(e.point_um(chain, 100, 60) for _p, _c, chain in found)
        self.assertEqual(len(pts), 14)
        for p, w in zip(pts, sorted(USE_EXPECT.values())):
            self.assertPoint(p, w)

    def test_flattened_pcell_net(self):
        e = ext({"inv_pcell": SKY_PCELL_TOP, "sky130_fd_pr__nfet_01v8__kmp_e044c2db": SKY_PCELL_NFET}, "inv_pcell")
        loc = e.locate_net("sky130_fd_pr__nfet_01v8__kmp_e044c2db_0/D")
        self.assertPoint(loc.point, (1.035, 0.92))
        self.assertEqual(loc.type, "ndif")
        self.assertEqual(loc.cells, ["inv_pcell", "sky130_fd_pr__nfet_01v8__kmp_e044c2db"])
        # a merged name with no node of its own: VSUBS is VGND
        self.assertPoint(e.locate_net("VSUBS").point, (0.20, 0.28))
        self.assertIsNone(e.locate_net("no_such_net"))
        self.assertIsNone(e.locate_net("no_such_inst/D"))

    def test_devices(self):
        e = ext({"inv_open_drain": SKY_OPEN}, "inv_open_drain")
        spice = {"inv_open_drain": {
            "X0": {"model": "sky130_fd_pr__pfet_01v8_hvt", "nets": ["Y", "A", "VPWR", "VPWR"], "params": {}},
            "X1": {"model": "sky130_fd_pr__nfet_01v8", "nets": ["a_300_260#", "A", "VGND", "VGND"], "params": {}}}}
        # the netlist's order decides, not the .ext's
        self.assertPoint(e.locate_device("0", spice=spice).point, (1.35, 3.50))
        self.assertPoint(e.locate_device("1", spice=spice).point, (1.35, 1.30))
        # without the netlist, the n-th device line
        self.assertPoint(e.locate_device("1").point, (1.35, 3.50))
        self.assertIsNone(e.locate_device("7"))

    def test_device_in_a_subcell(self):
        e = ext({"inv_pcell": SKY_PCELL_TOP, "sky130_fd_pr__nfet_01v8__kmp_e044c2db": SKY_PCELL_NFET}, "inv_pcell")
        loc = e.locate_device("sky130_fd_pr__nfet_01v8__kmp_e044c2db_0/0", "sky130_fd_pr__nfet_01v8")
        self.assertPoint(loc.point, (1.325, 0.92))


if __name__ == "__main__":
    unittest.main()
