"""layercheck.py: F1 to F5 on synthetic pairs of files (the user's export
and a stand-in for Magic's write-back), per PDK, with the shipped data and
reading rules. No Magic needed."""

import os
import tempfile
import unittest

from tests.unit._util import needs_klayout, db  # noqa: F401

if db is not None:
    from klayout_magic_pcells import layercheck, markers, pdkdata

PDKS = ("sky130A", "gf180mcuD", "ihp-sg13g2", "ihp-sg13cmos5l")


def side(boxes, dbu=0.001):
    """A Side from {(l, d): [(l, b, r, t), ...]} in um."""
    ly = db.Layout()
    ly.dbu = dbu
    top = ly.create_cell("TOP")
    for ld, bs in boxes.items():
        li = ly.layer(ld[0], ld[1])
        for b in bs:
            top.shapes(li).insert(db.DBox(*b))
    return layercheck.Side(ly, top, 0.001)


def run(pdk, user, magic, devices=(), cross=()):
    data = pdkdata.load(pdk)
    dev = layercheck.load_devices(pdk)
    return layercheck.compare(side(user), side(magic) if magic is not None else None, list(devices), data, dev,
                              list(cross), 0.001)


def merged(d, extra):
    out = dict(d)
    out.update(extra)
    return out


def grow(b, d):
    return (b[0] - d, b[1] - d, b[2] + d, b[3] + d)


def L(pdk, name):
    return tuple(layercheck.load_devices(pdk)["layers"][name])


# One NMOS per PDK: diffusion, gate poly, the n-implant (or none), and the
# layers that make it an NMOS. sky130A and gf180mcuD draw an n-implant;
# the IHP PDKs draw no implant for an NMOS, so their F1 case is the PMOS.
DIFF = (0.0, 0.0, 2.0, 0.65)
GATE = (0.95, -0.2, 1.1, 0.85)


def nmos(pdk, implant=None):
    d = layercheck.load_devices(pdk)["layers"]
    if pdk == "sky130A":
        u = {L(pdk, "diff"): [DIFF], L(pdk, "poly"): [GATE]}
        if implant is not None:
            u[L(pdk, "nsdm")] = [grow(DIFF, implant)]
        return u
    if pdk == "gf180mcuD":
        u = {L(pdk, "comp"): [DIFF], L(pdk, "poly"): [GATE]}
        if implant is not None:
            u[L(pdk, "nplus")] = [grow(DIFF, implant)]
        return u
    u = {L(pdk, "activ"): [DIFF], L(pdk, "gatpoly"): [GATE], L(pdk, "nwell"): [grow(DIFF, 1.0)]}
    if implant is not None:
        u[L(pdk, "psd")] = [grow(DIFF, implant)]
    del d
    return u


def implant_layer(pdk):
    return {"sky130A": "nsdm", "gf180mcuD": "nplus"}.get(pdk, "psd")


def model(pdk):
    return {"sky130A": "sky130_fd_pr__nfet_01v8", "gf180mcuD": "nfet_03v3",
            "ihp-sg13g2": "sg13_lv_pmos", "ihp-sg13cmos5l": "sg13_lv_pmos"}[pdk]


def device(pdk, x=0.95, y=0.0, m=None):
    return {"class": "msubckt", "model": m or model(pdk), "x": x, "y": y, "l": 0.15, "w": 0.65}


@needs_klayout
class F1(unittest.TestCase):
    def test_flush_implant_fires_on_every_pdk(self):
        for pdk in PDKS:
            with self.subTest(pdk=pdk):
                user = nmos(pdk, 0.0)
                magic = dict(user)
                magic[L(pdk, implant_layer(pdk))] = [grow(DIFF, 0.40)]
                out = run(pdk, user, magic, [device(pdk)])
                self.assertEqual(out["F2"], [], out["F2"])
                self.assertTrue(out["F1"], "no F1 on a flush %s" % implant_layer(pdk))
                self.assertIn("stops short", out["F1"][0]["text"])
                self.assertIn("Magic draws", out["F1"][0]["text"])

    def test_enough_enclosure_is_clean_on_every_pdk(self):
        for pdk in PDKS:
            with self.subTest(pdk=pdk):
                user = nmos(pdk, 0.40)
                out = run(pdk, user, dict(user), [device(pdk)])
                self.assertEqual(out["F1"], [])
                self.assertEqual(out["F2"], [])

    def test_one_nm_short_is_within_the_tolerance(self):
        user = nmos("sky130A", 0.124)
        out = run("sky130A", user, dict(user), [device("sky130A")])
        self.assertEqual(out["F1"], [])
        user = nmos("sky130A", 0.115)
        out = run("sky130A", user, dict(user), [device("sky130A")])
        self.assertEqual(len(out["F1"]), 1)

    def test_butting_tap_edge_needs_no_enclosure(self):
        # sky130A.tech:846: nsdm grows 0 toward an abutting p-tap.
        tap = (-0.3, 0.0, 0.0, 0.65)
        user = {L("sky130A", "diff"): [DIFF], L("sky130A", "poly"): [GATE],
                L("sky130A", "nsdm"): [(0.0, -0.125, 2.125, 0.775)],
                L("sky130A", "tap"): [tap], L("sky130A", "psdm"): [(-0.425, -0.125, 0.0, 0.775)]}
        out = run("sky130A", user, dict(user), [device("sky130A")])
        self.assertEqual(out["F1"], [], [f["text"] for f in out["F1"]])
        # The same nsdm edge with no tap beside it stops short.
        del user[L("sky130A", "tap")]
        out = run("sky130A", user, dict(user), [device("sky130A")])
        self.assertEqual(len(out["F1"]), 1)

    def test_npc_is_measured_from_magics_017_cut(self):
        poly = (0.0, 0.0, 0.5, 0.5)
        base = {L("sky130A", "poly"): [poly], L("sky130A", "li"): [poly]}
        # a 0.20 cut and npc 0.085 past it: 0.10 past Magic's 0.17 cut
        user = merged(base, {L("sky130A", "licon"): [(0.15, 0.15, 0.35, 0.35)],
                             L("sky130A", "npc"): [(0.065, 0.065, 0.435, 0.435)]})
        self.assertEqual(run("sky130A", user, dict(user))["F1"], [])
        # a 0.17 cut and npc 0.04 past it
        user = merged(base, {L("sky130A", "licon"): [(0.165, 0.165, 0.335, 0.335)],
                             L("sky130A", "npc"): [(0.125, 0.125, 0.375, 0.375)]})
        f1 = run("sky130A", user, dict(user))["F1"]
        self.assertEqual(len(f1), 1)
        self.assertEqual(f1[0]["layer"], "npc")

    def test_gaps_between_two_implants_are_not_f1(self):
        # Two diffusions, each enclosed by 0.125, 0.2 apart: Magic would bridge the
        # gap between the two nsdm boxes (grow-then-shrink); that is not F1.
        a, b = (0.0, 0.0, 1.0, 0.65), (1.45, 0.0, 2.45, 0.65)
        user = {L("sky130A", "diff"): [a, b], L("sky130A", "nsdm"): [grow(a, 0.125), grow(b, 0.125)]}
        magic = dict(user)
        magic[L("sky130A", "nsdm")] = [(a[0] - 0.125, -0.125, b[2] + 0.125, 0.775)]
        self.assertEqual(run("sky130A", user, magic)["F1"], [])

    def test_f1_skips_the_diffusion_of_a_changed_device(self):
        user = nmos("sky130A", 0.0)
        out = run("sky130A", user, dict(user), [device("sky130A", m="sky130_fd_pr__pfet_01v8")])
        self.assertEqual(len(out["F2"]), 1)
        self.assertEqual(out["F1"], [])

    def test_information_only_marks_f1(self):
        dev = dict(layercheck.load_devices("sky130A"), f1="information")
        user = nmos("sky130A", 0.0)
        out = layercheck.compare(side(user), side(user), [device("sky130A")], pdkdata.load("sky130A"), dev, [], 0.001)
        self.assertTrue(out["F1"] and all(f["info"] for f in out["F1"]))
        self.assertEqual(layercheck.counted(out), 0)


@needs_klayout
class F2(unittest.TestCase):
    def test_matching_device_is_clean(self):
        user = nmos("sky130A", 0.125)
        self.assertEqual(run("sky130A", user, None, [device("sky130A")])["F2"], [])

    def test_no_nsdm_reads_as_pfet(self):
        user = nmos("sky130A", None)
        out = run("sky130A", user, None, [device("sky130A", m="sky130_fd_pr__pfet_01v8")])
        self.assertEqual(len(out["F2"]), 1)
        t = out["F2"][0]["text"]
        self.assertIn("outside nwell", t)
        self.assertIn("sky130_fd_pr__pfet_01v8", t)
        self.assertIn("sky130A.tech:2597", t)

    def test_no_device_on_a_gate(self):
        for pdk in PDKS:
            with self.subTest(pdk=pdk):
                out = run(pdk, nmos(pdk, 0.4), None, [])
                self.assertEqual(len(out["F2"]), 1)
                self.assertIn("no device", out["F2"][0]["text"])

    def test_two_devices_on_one_gate(self):
        user = nmos("gf180mcuD", 0.4)
        user[L("gf180mcuD", "dualgate")] = [(-1.0, -1.0, 2.5, 0.3)]
        devs = [device("gf180mcuD"), device("gf180mcuD", y=0.3, m="nfet_06v0")]
        out = run("gf180mcuD", user, None, devs)
        self.assertEqual(len(out["F2"]), 1)
        self.assertIn("2 devices", out["F2"][0]["text"])
        self.assertIn("DUALGATE covers only part", out["F2"][0]["text"])

    def test_variant_change_is_reported(self):
        user = nmos("ihp-sg13g2", 0.4)
        out = run("ihp-sg13g2", user, None, [device("ihp-sg13g2", m="sg13_hv_pmos")])
        self.assertEqual(len(out["F2"]), 1)
        self.assertIn("no ThickGateOx", out["F2"][0]["text"])

    def test_cross_cell_explains_the_change(self):
        user = nmos("sky130A", 0.125)
        cross = [{"cell": "dev", "layer": "nsdm.drawing", "drawn_in": "TOP", "box": db.DBox(-0.125, -0.125, 2.125, 0.775)}]
        out = run("sky130A", user, None, [device("sky130A", m="sky130_fd_pr__pfet_01v8")], cross)
        self.assertIn("Magic reads cell dev without the nsdm.drawing drawn in cell TOP", out["F2"][0]["text"])

    def test_every_device_is_listed(self):
        out = run("sky130A", nmos("sky130A", 0.125), None, [device("sky130A"), device("sky130A", x=9, y=9)])
        self.assertEqual(len(out["devices"]), 2)
        self.assertIn("no drawn gate here", out["devices"][1]["text"])


@needs_klayout
class F3F4F5(unittest.TestCase):
    def test_cut_without_conductor_is_dropped(self):
        li = (0.0, 0.0, 0.5, 0.5)
        user = {L("sky130A", "diff"): [(0.0, 0.0, 0.5, 0.5)], L("sky130A", "nsdm"): [(-0.2, -0.2, 0.7, 0.7)],
                L("sky130A", "licon"): [(0.165, 0.165, 0.335, 0.335)]}
        magic = dict(user)
        del magic[L("sky130A", "licon")]
        f3 = run("sky130A", user, magic)["F3"]
        self.assertEqual(len(f3), 1)
        self.assertIn("no li at it", f3[0]["text"])
        user[L("sky130A", "li")] = [li]
        self.assertEqual(run("sky130A", user, merged(user, {L("sky130A", "li"): [li]}))["F3"], [])

    def test_cut_on_diffusion_without_implant_names_the_implant(self):
        """li covers the cut, but the diffusion under it has
        neither nsdm nor psdm, so Magic makes no contact there; the F3 item
        says that, and not that li is missing."""
        diff = (0.0, 0.0, 0.5, 0.5)
        user = {L("sky130A", "diff"): [diff], L("sky130A", "li"): [diff],
                L("sky130A", "licon"): [(0.165, 0.165, 0.335, 0.335)]}
        magic = dict(user)
        del magic[L("sky130A", "licon")]
        f3 = run("sky130A", user, magic)["F3"]
        self.assertEqual(len(f3), 1)
        self.assertIn("The cut has li over it, but the diffusion under it has neither nsdm nor psdm", f3[0]["text"])
        self.assertNotIn("only where li", f3[0]["text"])
        # With nsdm drawn, a dropped cut gets the reason about li again.
        user[L("sky130A", "nsdm")] = [grow(diff, 0.2)]
        f3 = run("sky130A", user, magic)["F3"]
        self.assertNotIn("neither nsdm nor psdm", f3[0]["text"])

    def test_conductor_magic_drops_and_adds(self):
        for pdk in PDKS:
            with self.subTest(pdk=pdk):
                m1 = L(pdk, "met1" if pdk == "sky130A" else "metal1")
                user = {m1: [(0, 0, 1, 1)]}
                out = run(pdk, user, {m1: [(0, 0, 0.5, 1)]})
                self.assertEqual(len(out["F3"]), 1)
                out = run(pdk, user, {m1: [(0, 0, 1.2, 1)]})
                self.assertEqual(len(out["F4"]), 1)
                self.assertEqual(out["F3"], [])

    def test_pin_box_written_as_conductor_says_so(self):
        user = {(67, 16): [(0, 0, 0.3, 0.3)]}
        out = run("sky130A", user, {(67, 20): [(0, 0, 0.3, 0.3)], (67, 16): [(0, 0, 0.3, 0.3)]})
        self.assertEqual(len(out["F4"]), 1)
        self.assertIn("pin box on 67/16", out["F4"][0]["text"])

    def test_slivers_are_ignored(self):
        m1 = (68, 20)
        self.assertEqual(run("sky130A", {m1: [(0, 0, 1, 1)]}, {m1: [(0, 0, 1.001, 1)]})["F4"], [])

    def test_redrawn_cuts_are_f5(self):
        user = {(22, 0): [(0, 0, 1.2, 0.6)], (32, 0): [(-0.2, -0.2, 1.4, 0.8)], (34, 0): [(0, 0, 1.2, 0.6)],
                (33, 0): [(0.1, 0.19, 0.32, 0.41), (0.54, 0.19, 0.76, 0.41)]}
        magic = merged(user, {(33, 0): [(0.32, 0.19, 0.54, 0.41)]})
        out = run("gf180mcuD", user, magic)
        self.assertEqual(out["F3"], [])
        self.assertEqual(len(out["F5"]), 1)
        self.assertIn("you drew 2, Magic writes 1", out["F5"][0]["text"])
        self.assertIn("0.220 um squares", out["F5"][0]["text"])

    def test_f5_says_when_magics_cuts_break_the_rule(self):
        cut = (33, 0)
        user = {(22, 0): [(0, 0, 1.2, 0.6)], (32, 0): [(-0.2, -0.2, 1.4, 0.8)], (34, 0): [(0, 0, 1.2, 0.6)],
                cut: [(0.1, 0.19, 0.32, 0.41)]}
        magic = merged(user, {cut: [(0.1, 0.19, 0.30, 0.41)]})
        out = run("gf180mcuD", user, magic)
        self.assertIn("breaks the rule too", out["F5"][0]["text"])


@needs_klayout
class Headline(unittest.TestCase):
    def test_plain_words(self):
        """The GUI message's first line."""
        from klayout_magic_pcells.export import ExportResult
        er = ExportResult()
        user = nmos("sky130A", None)
        out = run("sky130A", user, None, [device("sky130A", m="sky130_fd_pr__pfet_01v8")])
        out["F3"] = [{"check": "F3", "layer": "licon1.drawing"}] * 2
        self.assertEqual(layercheck.headline(out, er, "my_inv"),
                         "In my_inv: 1 transistor that Magic reads as another device or none; "
                         "2 shapes or cuts that Magic drops (licon1.drawing).")
        self.assertEqual(layercheck.headline({}, er, "my_inv"), "No generated-layer findings in my_inv.")


@needs_klayout
class Helpers(unittest.TestCase):
    def test_read_ext_devices(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "x.ext")
        with open(p, "w") as f:
            f.write('tech sky130A\nscale 1000 1 500000\n'
                    'device msubckt sky130_fd_pr__nfet_01v8 270 260 271 261 l=30 w=130 "VGND" "a" 60 0\n'
                    'node "A" 13 35.1 248 468 li\n')
        devs = layercheck.read_ext_devices(p, 0.005)
        self.assertEqual(len(devs), 1)
        self.assertAlmostEqual(devs[0]["x"], 1.35)
        self.assertAlmostEqual(devs[0]["y"], 1.30)
        self.assertAlmostEqual(devs[0]["w"], 0.65)
        self.assertAlmostEqual(devs[0]["l"], 0.15)

    def test_magic_squares(self):
        r = db.Region(db.Box(0, 0, 200, 200))
        sq = layercheck.magic_squares(r, 0.17, 0.17, 0.001)
        self.assertEqual(sq.bbox(), db.Box(15, 15, 185, 185))
        r = db.Region(db.Box(0, 0, 600, 200))
        self.assertEqual(layercheck.magic_squares(r, 0.17, 0.17, 0.001).bbox().width(), 510)

    def test_reading_rules_cite_lines_and_match_generated_rows(self):
        for pdk in PDKS:
            with self.subTest(pdk=pdk):
                dev = layercheck.load_devices(pdk)
                data = pdkdata.load(pdk)
                for row in data.generated():
                    if row.get("enclosure_check"):
                        self.assertIn(row["from"], dev["shapes"], "no shape for %s from %s" % (row["name"], row["from"]))
                for name, spec in dev["shapes"].items():
                    self.assertTrue(spec.get("line"), name)
                    for b in spec.get("butts", []):
                        self.assertTrue(b in dev["shapes"] or b in dev.get("derived", {}), b)
                for r in dev["fets"]["magic_reads"]:
                    self.assertTrue(r.get("line") and r.get("why"), r)
                for ld in dev["layers"].values():
                    self.assertIsNotNone(data.layer(ld[0], ld[1]), "%s: %s not in the data file" % (pdk, ld))


if __name__ == "__main__":
    unittest.main()


@needs_klayout
class Prepare(unittest.TestCase):
    """prepare() never raises (design-0.6.md 2.4): an export that fails or is refused,
    or reading rules that can't be read, give a Task whose outcome has
    status 2, the reason in the RDB and the summary, and the export's
    findings. Magic never starts, so none is needed."""

    def setUp(self):
        import types
        self.data = pdkdata.load("sky130A")
        self.cfg = types.SimpleNamespace(pdk="sky130A", cache_dir=tempfile.mkdtemp(prefix="kmp-prep-"))
        self.ly = db.Layout()
        self.ly.dbu = 0.001
        self.top = self.ly.create_cell("TOP")
        self.top.shapes(self.ly.layer(68, 20)).insert(db.DBox(0, 0, 1, 1))

    def tearDown(self):
        import shutil
        shutil.rmtree(self.cfg.cache_dir, ignore_errors=True)

    def failed(self, task, *texts):
        task.start()
        o = task.poll()
        self.assertIs(task.wait(), o)
        self.assertEqual(o.status, 2, o.summary)
        self.assertTrue(o.summary.startswith("layers: "), o.summary)
        self.assertEqual(o.rdb.count(layercheck.CAT_JOB), 1)
        said = [markers.item_text(it) for it in o.rdb.db.each_item()]
        for t in texts:
            self.assertIn(t, o.summary)
            self.assertTrue(any(t in s for s in said), said)
        return o

    def test_a_cell_not_in_the_layout(self):
        self.failed(layercheck.prepare(self.ly, "nope", self.cfg, self.data, {}), "cell nope is not in the layout")

    def test_an_export_error(self):
        from klayout_magic_pcells import export
        real = export.export_cell

        def boom(*a, **k):
            raise export.ExportError("copying TOP renamed the cells x")
        export.export_cell = boom
        try:
            t = layercheck.prepare(self.ly, self.top, self.cfg, self.data, {})
        finally:
            export.export_cell = real
        self.failed(t, "copying TOP renamed the cells x")

    def test_a_refused_layout_keeps_its_export_findings(self):
        bad = self.ly.create_cell("bad__kmp_01234567")
        bad.shapes(self.ly.layer(255, 0)).insert(db.DBox(0, 0, 1, 1))
        self.top.insert(db.DCellInstArray(bad.cell_index(), db.DTrans()))
        o = self.failed(layercheck.prepare(self.ly, self.top, self.cfg, self.data, {}), "bad__kmp_01234567")
        self.assertEqual(o.rdb.count("Export/error-marker cells"), 1)

    def test_reading_rules_that_cannot_be_read(self):
        import types
        cfg = types.SimpleNamespace(pdk="no-such-pdk", cache_dir=self.cfg.cache_dir)
        self.failed(layercheck.prepare(self.ly, self.top, cfg, self.data, {}), "cannot read the reading rules")
