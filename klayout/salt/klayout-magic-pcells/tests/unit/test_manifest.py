import json
import math
import os
import random
import shutil
import struct
import sys
import unittest

from tests.unit._util import db, needs_klayout
from klayout_magic_pcells.config import PDKS, SHIPPED_MANIFEST, SUPPORTED_PDKS, shipped_manifest
from klayout_magic_pcells.manifest import InvalidValue, Manifest, ParamSpec, format_float

MAN = Manifest.load(SHIPPED_MANIFEST)


def P(**kw):
    d = {"name": "w", "type": "float", "default": "0.420", "editable": True, "label": "Width (um)"}
    d.update(kw)
    return ParamSpec(d, kw.pop("family", "mos"))


class Formatting(unittest.TestCase):
    def test_float_default_string_is_kept(self):
        p = P()
        self.assertEqual(p.format(0.42), "0.420")
        self.assertEqual(p.format(0.42000000000000004), "0.420")

    def test_float_text(self):
        p = P()
        self.assertEqual(p.format(1.5), "1.5")
        self.assertEqual(p.format(31.0), "31.0")       # never "31": Tcl divides integers
        self.assertEqual(p.format(0.4234), "0.4234")
        self.assertEqual(p.format(1e-05), "1e-05")
        # KLayout reads "0.35" back from a file as 0.35000000000000003
        self.assertEqual(p.format(0.35000000000000003), "0.35")
        self.assertEqual(format_float(2898.6000000000004), "2898.6")

    def test_a_reopened_value_sends_the_same_text(self):
        # KLayout 0.30.11 writes a double with 15 significant digits and
        # reads that text back up to one ULP off (4.257627156815 reopens as
        # 4.2576271568149995). Values at a 12-digit tie, and values one ULP
        # from one, must give the same text for every double within two ULPs
        # of the stored text.
        rng = random.Random(7)
        vals = [4.257627156815, 6079.889030445, 0.2224999999995, 0.4224999999995002,
                0.35, 2.0001234567891234]
        for _ in range(4000):
            t = float("%d.%011d5" % (rng.randint(0, 99), rng.randint(0, 10 ** 11 - 1)))
            vals += [t, math.nextafter(t, math.inf), math.nextafter(t, -math.inf)]
            vals.append(rng.uniform(-1e6, 1e6))
        for v in vals:
            stored = float("%.15g" % v)
            near = [stored]
            for direction in (math.inf, -math.inf):
                x = stored
                for _ in range(2):
                    x = math.nextafter(x, direction)
                    near.append(x)
            for x in near:
                self.assertEqual(format_float(x), format_float(v), (repr(v), repr(x)))
        self.assertEqual(format_float(4.2576271568149995), format_float(4.257627156815))
        # KLayout saves -0.0 as 0, so a reopened -0.0 is 0.0: both send "0.0".
        self.assertEqual(format_float(-0.0), "0.0")
        self.assertEqual(format_float(float("inf")), "inf")
        self.assertEqual(format_float(float("nan")), "nan")

    @needs_klayout
    def test_text_survives_a_klayout_save_and_reopen(self):
        # The real thing: doubles saved by KLayout (as layout meta info, which
        # KLayout writes and parses like a PCell parameter) and read back in
        # a second process give the same text as the values that were saved.
        import subprocess
        import tempfile
        rng = random.Random(11)
        vals = []
        for _ in range(1500):
            t = float("%d.%011d5" % (rng.randint(0, 9), rng.randint(0, 10 ** 11 - 1)))
            vals += [t, math.nextafter(t, math.inf), math.nextafter(t, -math.inf),
                     rng.uniform(0, 1000)]
        d = tempfile.mkdtemp(prefix="kmp-ulp-")
        try:
            gds = os.path.join(d, "meta.gds")
            ly = db.Layout()
            ly.create_cell("TOP")
            for i, v in enumerate(vals):
                ly.add_meta_info(db.LayoutMetaInfo("v%d" % i, v, None, True))
            ly.write(gds)
            script = ("import json, sys, klayout.db as db\n"
                      "ly = db.Layout(); ly.read(sys.argv[1])\n"
                      "print(json.dumps([repr(ly.meta_info_value('v%d' % i)) for i in range(int(sys.argv[2]))]))\n")
            p = subprocess.run([sys.executable, "-c", script, gds, str(len(vals))],
                               stdout=subprocess.PIPE, check=True, timeout=120)
            back = [float(x) for x in json.loads(p.stdout)]
        finally:
            shutil.rmtree(d, ignore_errors=True)
        moved = sum(1 for a, b in zip(vals, back) if a != b)
        self.assertGreater(moved, 100, "KLayout kept every double exactly; the test lost its point")
        bad = [(repr(a), repr(b)) for a, b in zip(vals, back) if format_float(a) != format_float(b)]
        self.assertEqual(bad, [])

    def test_harness_formatter_agrees(self):
        # tests/parity/magic_text.py restates the contract without the
        # plugin's code; the two must agree, on zeros of either sign too
        # (version 0.3's magic_text gave "0.0" for -0.0, the plugin "-0.0").
        import magic_text
        rng = random.Random(3)
        vals = [0.0, -0.0, 1e-5, 1e16, 1e15, 0.0001, 31.0, 0.35000000000000003, 4.2576271568149995,
                -1.0, -0.4225, 5e-324, 1e300, float("inf"), float("-inf")]
        for _ in range(20000):
            vals.append(rng.uniform(-1e4, 1e4))
            t = float("%d.%011d5" % (rng.randint(0, 99), rng.randint(0, 10 ** 11 - 1)))
            vals += [t, math.nextafter(t, -math.inf)]
            vals.append(struct.unpack("d", struct.pack("Q", rng.getrandbits(64)))[0])
        for v in vals:
            if v != v:
                continue
            self.assertEqual(magic_text.float_text(v), format_float(v), repr(v))
        p = P(default="0")
        self.assertEqual((p.format(-0.0), magic_text.float_text(-0.0, "0")), ("0", "0"))
        self.assertEqual((p.format(0.0), magic_text.float_text(0.0, "0")), ("0", "0"))
        p = P()
        self.assertEqual((p.format(-0.0), magic_text.float_text(-0.0, "0.420")), ("0.0", "0.0"))

    def test_int_bool_signed(self):
        self.assertEqual(P(name="nf", type="int", default="1").format(3), "3")
        b = P(name="guard", type="bool01", default="1")
        self.assertEqual(b.format(True), "1")
        self.assertEqual(b.format(False), "0")
        self.assertIs(b.parse("0"), False)
        s = P(name="viasrc", type="signed", default="100", label="Source via coverage [+/-](%)")
        # Verbatim, whitespace included: Magic takes the anchor from the first
        # character, so " +50" (no anchor) and "+50" draw differently.
        self.assertEqual(s.format(" +50 "), " +50 ")
        self.assertEqual(s.parse("\t+30"), "\t+30")
        self.assertEqual(s.canonical(" -50"), " -50")
        self.assertEqual(s.format("-50"), "-50")
        self.assertEqual(s.unit, "%")
        self.assertIn("anchor", s.description)

    def test_signed_values_that_may_reach_magic(self):
        s = P(name="viagb", type="signed", default="0", label="Bottom via coverage [+/-](%)")
        for ok in ("+50", "-50", "50", "0", "100", "50.5", " +50", "\t-30", "+50 ", "1e2", ".5", "50."):
            s.check(ok)
        for bad in ("", "+", "-", "abc", "50abc", "50 50", "0x32", "nan", "inf", "{", "{50}",
                    "[exec touch /tmp/x]", "$x", "5$x", "\\x", "1[set a 1]", "\u0663\u0660"):
            with self.assertRaises(InvalidValue, msg=repr(bad)) as cm:
                s.check(bad)
            self.assertEqual(cm.exception.param, "viagb")
            self.assertIn("not sent to Magic", str(cm.exception))

    def test_build_request_refuses_a_command_in_a_coverage_value(self):
        d = MAN["sky130_fd_pr__nfet_01v8"]
        vals = dict(d.defaults_values(), viagb="[exec touch /tmp/x]")
        with self.assertRaises(InvalidValue):
            d.build_request(vals)
        # names and labels still work, and never reach Magic
        self.assertEqual(d.build_request(vals, check=False)["viagb"], "[exec touch /tmp/x]")

    def test_int_rejects_fraction(self):
        with self.assertRaises(ValueError):
            P(name="nf", type="int", default="1").parse("2.5")

    def test_units_and_descriptions(self):
        self.assertEqual(P().unit, "µm")
        self.assertEqual(P().description, "Finger width")
        self.assertEqual(P(family="res").description, "Width")
        self.assertEqual(P(name="area", label="Area (um^2)", family="diode").unit, "µm²")
        self.assertEqual(P(name="val", label="Value (ohms)", family="res").unit, "Ω")


# Generators per PDK in the image's PDKs (open_pdks 026824c7; IHP 7e53c777
# and ff32f48c): devices, box-paint generators, excluded helpers.
COUNTS = {"sky130A": (60, 13, 7), "gf180mcuD": (53, 6, 5), "ihp-sg13g2": (39, 14, 7),
          "ihp-sg13cmos5l": (31, 10, 6)}
MANS = {p: Manifest.load(shipped_manifest(p)) for p in SUPPORTED_PDKS}


class ShippedManifest(unittest.TestCase):
    def test_counts(self):
        self.assertEqual(sum(1 for d in MAN.devices if d.kind == "device"), 60)
        self.assertEqual(len(MAN.editable_names()), 50)
        fams = {}
        for d in MAN.devices:
            fams[d.family] = fams.get(d.family, 0) + 1
        self.assertEqual(fams, {"res": 22, "mos": 12, "fixed": 12, "diode": 8, "varactor": 3,
                                "mim_cap": 2, "photodiode": 1, "box_paint": 13})
        self.assertEqual(len(MAN.data["excluded"]), 7)

    def test_counts_per_pdk(self):
        for pdk, (dev, box, exc) in COUNTS.items():
            m = MANS[pdk]
            self.assertEqual(m.pdk, pdk)
            self.assertEqual(sum(1 for d in m.devices if d.kind == "device"), dev, pdk)
            self.assertEqual(sum(1 for d in m.devices if d.kind == "box"), box, pdk)
            self.assertEqual(len(m.data["excluded"]), exc, pdk)
            self.assertEqual(m.namespace, PDKS[pdk]["namespace"], pdk)

    def test_box_paint_generators(self):
        menu = {"mcon", "via1", "via2", "via3", "via4", "subconn", "mvsubconn", "subconn_guard",
                "mvsubconn_guard", "nwell", "mvnwell", "deep_nwell", "mvdeep_nwell"}
        bp = {d.name: d for d in MAN.devices if d.kind == "box"}
        self.assertEqual(set(bp), menu)
        for n, d in bp.items():
            self.assertTrue(d.raw["menu"].startswith("Devices 1 / "), n)
            self.assertEqual([p.name for p in d.params], ["w", "h"])
            self.assertEqual(d.form, "box")
        self.assertEqual(bp["via1"].raw["min_box_um"], "0.26")
        self.assertEqual(bp["via4"].raw["min_box_um"], "1.18")
        self.assertEqual(bp["deep_nwell"].raw["min_box_um"], "3.0")
        for e in MAN.data["excluded"]:
            self.assertIn("required arguments", e["reason"])
        for pdk, m in MANS.items():
            for d in m.devices:
                if d.kind != "box":
                    continue
                run = d.batch
                self.assertTrue(run["ok"] and not run["empty"], (pdk, d.name))
                self.assertEqual(d.params[0].default, d.raw["min_box_um"], (pdk, d.name))
                self.assertFalse(d.raw["below_min"]["painted"], (pdk, d.name))

    def test_grid_of_the_default_output(self):
        grids = {d.name: d.raw["defaults_run"]["grid_nm"] for d in MAN.devices}
        fine = sorted(n for n, g in grids.items() if g % 5)
        self.assertEqual(fine, ["sky130_fd_pr__pnp_05v5_W0p68L0p68", "sky130_fd_pr__rf_test_coil1",
                                "sky130_fd_pr__rf_test_coil2", "sky130_fd_pr__rf_test_coil3"])

    def test_types(self):
        for pdk, m in MANS.items():
            for d in m.devices:
                for p in d.params:
                    self.assertIn(p.type, ("float", "int", "bool01", "signed", "choice", "numlist"),
                                  (pdk, d.name, p.name))
                    p.default_value()  # parses
                    p.check(p.default)
                    if p.type == "choice":
                        self.assertIn(p.default, p.choices)
                self.assertNotIn("gencell", [p.name for p in d.params])
                self.assertEqual(d.form, "box" if d.kind == "box" else "wrapper" if d.nocell else "cell")
        ng = MANS["ihp-sg13g2"]["sg13_lv_nmos"].param("ng")
        self.assertEqual(ng.type, "int")
        via = MANS["ihp-sg13g2"]["via"]
        self.assertEqual(via.param("metalbot").type, "choice")
        self.assertEqual(via.param("nxcuts").type, "numlist")
        self.assertEqual(MANS["gf180mcuD"]["ppolyf_u"].param("guard_type").choices, ["nwell", "pwell"])

    def test_every_signed_default_passes_the_check(self):
        n = 0
        for d in MAN.devices:
            for p in d.params:
                if p.type == "signed":
                    p.check(p.default)
                    n += 1
        self.assertGreater(n, 50)

    def test_choice_and_numlist_checks(self):
        via = MANS["ihp-sg13g2"]["via"]
        via.param("metalbot").check("metal2")
        via.param("nxcuts").check("1 2")
        for name, bad in (("metalbot", "metal9"), ("metalbot", "[exec x]"), ("nxcuts", "1 [x]"),
                          ("nxcuts", ""), ("nxcuts", "$a")):
            with self.assertRaises(InvalidValue, msg=(name, bad)):
                via.param(name).check(bad)

    def test_request_of_defaults_is_magic_defaults(self):
        for pdk, m in MANS.items():
            for d in m.devices:
                req = d.build_request(d.defaults_values())
                magic = dict(d.defaults)
                for k, v in req.items():
                    self.assertEqual(v, magic[k], (pdk, d.name, k))

    def test_parse_request_round_trip(self):
        d = MAN["sky130_fd_pr__nfet_01v8"]
        vals = d.parse_request({"w": "1.5", "nf": "3", "guard": "0", "viasrc": "+50"})
        self.assertEqual(vals, {"w": 1.5, "nf": 3, "guard": False, "viasrc": "+50"})
        req = d.build_request(dict(d.defaults_values(), **vals))
        self.assertEqual((req["w"], req["nf"], req["guard"], req["viasrc"]), ("1.5", "3", "0", "+50"))

    def test_defaults_digest_recomputes(self):
        from klayout_magic_pcells.backend import defaults_digest
        for pdk, m in MANS.items():
            self.assertEqual(defaults_digest(m.defaults_by_device()), m.defaults_digest, pdk)

    def test_vendor_cells(self):
        v = MAN.vendor_cells()
        self.assertIn("sky130_fd_pr__rf_test_coil1", v)
        self.assertEqual(len(MAN["sky130_fd_pr__nfet_01v8"].vendor_cells), 0)

    @needs_klayout
    def test_no_name_collides_with_the_helper(self):
        from klayout_magic_pcells.pcell import check_names
        for m in MANS.values():
            for d in m.devices:
                check_names(d)

    @needs_klayout
    def test_collision_is_refused(self):
        from klayout_magic_pcells.manifest import DeviceSpec
        from klayout_magic_pcells.pcell import PCellNameError, check_names
        spec = DeviceSpec({"name": "x", "family": "mos", "nocell": False, "defaults": [["layout", "1"]],
                           "params": [{"name": "layout", "type": "float", "default": "1",
                                       "editable": True}]})
        with self.assertRaises(PCellNameError):
            check_names(spec)


if __name__ == "__main__":
    unittest.main()
