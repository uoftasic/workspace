"""tools/build_pdk_data.py on short tech-file excerpts, and pdkdata.py on
the shipped data files."""

import json
import os
import shutil
import sys
import tempfile
import textwrap
import unittest

from tests.unit._util import REPO
from klayout_magic_pcells import pdkdata
from klayout_magic_pcells.config import SUPPORTED_PDKS

sys.path.insert(0, os.path.join(REPO, "tools"))
import build_pdk_data as B  # noqa: E402


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(textwrap.dedent(text).lstrip("\n"))
    return path


def stmts_of(text, name="t.tech"):
    d = tempfile.mkdtemp()
    try:
        return B.statements(B.read_lines(write(os.path.join(d, name), text)))
    finally:
        shutil.rmtree(d)


# A tech file with every section the builder reads, in the forms the four
# PDKs use. lambda is 10 nm; the drc section's values are in nm.
MINI_TECH = """
tech
  format 35
  mini
end

version
 version 1.2.3
end

planes
  well,w
  active,a
  metal1,m1
end

types
  well nwell,nw
  well pwell,pw
  active ndiff,ndif
  active pdiff,pdif
  active nfet
  active pfet
  active ndiffc,ndc
  metal1 metal1,m1
end

contact
  ndc ndiff metal1
end

aliases
  allndiff *ndiff,nfet
  allpdiff pdiff,pfet
end

cifoutput
style gdsii variants (),(other)
 scalefactor 10 nanometers
 gridlimit 5

 layer NWELL nwell
	calma 64 20

 layer DIFF ndiff,pdiff
	calma 65 20

 templayer baseNSDM ndiff
	bloat-or allndiff * 125 allpdiff 0

 layer NSDM baseNSDM
	grow 185
	shrink 185
	close 265000
	calma 93 44

 layer MET1 metal1
	labels metal1
	calma 68 20

 layer MET1PIN
	labels metal1 port
	calma 68 16

variants (other)
 layer OTHER metal1
	calma 99 0
variants *

style drc
 scalefactor 10 nanometers

 templayer nwell_missing_tap nwell
	bloat-all nwell ndiff

end

cifinput
style mini variants ()
 scalefactor 10 nanometers
 gridlimit 5

 ignore NPC

 layer nwell NWELL

 templayer ndiffarea DIFF
	and NSDM
	and-not PSDM
	copyup ndifcheck

 layer ndiff ndiffarea
	labels DIFF

 layer pdiff DIFF
	and-not NSDM

 layer metal1 MET1,MET1TXT,MET1PIN
	labels MET1
	labels MET1PIN port
	labels MET1TXT text

 calma NWELL 64 20
 calma DIFF 65 20
 calma NSDM 93 44
 calma PSDM 94 20
 calma NPC 95 20
 calma MET1 68 20
 calma MET1TXT 68 5
 calma MET1PIN 68 16
 calma NOTUSED 77 0
end

drc
 style drc variants (fast),(full),(routing)
 scalefactor 10
 cifstyle drc

 variants (fast),(full)
 width nwell 840 \\
	"N-well width < %d (nwell.1)"
 spacing nwell nwell 1270 touching_ok \\
	"N-well spacing < %d (nwell.2a)"
 variants (full)
 cifmaxwidth nwell_missing_tap 0 bend_illegal \\
	"All nwells must contain taps (nwell.4)"
 variants *
 area metal1 83000 140 \\
	"Metal1 minimum area < %a (met1.6)"
 widespacing metal1 3000 metal1 280 touching_ok \\
	"Metal1 > 3um spacing < %d (met1.3b)
 exemption SRAMID
 surround ndc ndiff 70 absence_illegal \\
	"Diffusion overlap of contact < %d (licon.5a + psdm.5a)"
 exception SRAMID
 surround ndc ndiff 20 absence_illegal \\
	"Diffusion overlap of contact in SRAM < %d (licon.5a SRAM exception)"
 exception none
# width nwell 9999 \\
	"a commented rule with a continued why-text (nope.1)"
 exact_overlap ndc
 angles metal1 45 "Only 45 degree angles (Grid Rules)"

 style empty
 scalefactor 10
end
"""

MINI_LYP = """
<?xml version="1.0" encoding="utf-8"?>
<layer-properties>
 <properties><name>nwell.drawing - 64/20</name><source>64/20@1</source></properties>
 <properties><name>pwell.drawing - 64/44</name><source>64/44@1</source></properties>
 <properties><name>met1.label - 68/5</name><source>68/5@1</source></properties>
 <properties><name/><source>COMP_Label 22/10@1</source></properties>
 <properties><name>met1.net</name><source>68/23</source></properties>
</layer-properties>
"""

MINI_LVS = """
# conductors
met1 = polygons(68, 20)
met1_label = labels(68, 5)
# old = labels(68, 99)
"""

MINI_DECK = """
if $feol == "true"
  FEOL = true
end
report("x", $report)
source($input, $top_cell)
"""


class MiniPdk(unittest.TestCase):
    """A PDK tree in a temporary directory, built the way the real ones are."""

    @classmethod
    def setUpClass(cls):
        cls.root = tempfile.mkdtemp(prefix="kmp-pdkdata-")
        pdk = os.path.join(cls.root, "sky130A")
        write(os.path.join(pdk, "libs.tech", "magic", "sky130A.tech"), MINI_TECH)
        write(os.path.join(pdk, B.PDK_FILES["sky130A"]["lyp"]), MINI_LYP)
        write(os.path.join(pdk, B.PDK_FILES["sky130A"]["klayout_lvs"]), MINI_LVS)
        write(os.path.join(pdk, "libs.tech", "netgen", "sky130A_setup.tcl"), "# setup\n")
        write(os.path.join(pdk, "libs.tech", "klayout", "drc", "mini.drc"), MINI_DECK)
        write(os.path.join(pdk, "SOURCES"), "open_pdks 0123abc\n")
        cls.ov = {"sky130A": {"generated": {"NSDM": [{"from": "n-diffusion", "types": ["allndiff"],
                                                       "rule_ids": ["n/psdm.5a"]}]}}}
        cls.data = B.build("sky130A", cls.root, cls.ov)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def rule(self, rid):
        return [r for r in self.data["drc"]["rules"] if rid in r["ids"]]


class Reading(unittest.TestCase):
    def test_continuation_lines_join(self):
        st = stmts_of('''
            width nwell 840 \\
            \t"N-well width < %d (nwell.1)"
            ''')
        self.assertEqual(len(st), 1)
        self.assertEqual(st[0].line, 1)
        self.assertEqual(st[0].toks[:3], ["width", "nwell", "840"])
        self.assertIn('"N-well width', st[0].text)

    def test_a_commented_rule_swallows_its_continued_why_text(self):
        st = stmts_of('''
            # width nwell 9999 \\
            \t"a commented rule (nope.1)"
            width nwell 840 "x (nwell.1)"
            ''')
        self.assertEqual([s.toks[0] for s in st], ["width"])
        self.assertEqual(st[0].line, 3)

    def test_include_lines_read_the_named_file(self):
        d = tempfile.mkdtemp()
        try:
            write(os.path.join(d, "a-drc.tech"), "drc\n width x 10 \"w (A.1)\"\nend\n")
            main = write(os.path.join(d, "a.tech"), "tech\n a\nend\ninclude a-drc\n")
            lines = B.read_lines(main)
            secs = B.sections(B.statements(lines))
            self.assertIn("drc", secs)
            self.assertEqual((secs["drc"][0].file, secs["drc"][0].line), ("a-drc.tech", 2))
        finally:
            shutil.rmtree(d)

    def test_variant_blocks(self):
        body = stmts_of('''
            layer A a
            variants (other)
            layer B b
            variants *
            layer C c
            ''')
        self.assertEqual([s.toks[1] for s in B.in_variant(body, "")], ["A", "C"])
        self.assertEqual([s.toks[1] for s in B.in_variant(body, "other")], ["A", "B", "C"])


class RuleIds(unittest.TestCase):
    def ids(self, why):
        return B.rule_ids(why)[1]

    def test_single(self):
        self.assertEqual(self.ids("N-well width < %d (nwell.1)"), ["nwell.1"])

    def test_composites(self):
        self.assertEqual(self.ids("x (licon.9 + psdm.5a)"), ["licon.9", "psdm.5a"])
        self.assertEqual(self.ids("Via1 width < %d (V1.a + 2 * M2.c)"), ["V1.a", "M2.c"])
        self.assertEqual(self.ids("x (V1.c - M2.c)"), ["V1.c", "M2.c"])
        self.assertEqual(self.ids("x (CO.2a - 2 * CO.6)"), ["CO.2a", "CO.6"])
        self.assertEqual(self.ids("x (MIMTM.4-VT.4)"), ["MIMTM.4", "VT.4"])
        self.assertEqual(self.ids("x (LU.c, LU.c1)"), ["LU.c", "LU.c1"])

    def test_number_after_a_comma_belongs_to_the_family(self):
        self.assertEqual(self.ids("x (nwell.5a, 7)"), ["nwell.5a", "nwell.7"])
        self.assertEqual(self.ids("x (diff/tap.20 + diff/tap.17,19)"),
                         ["diff/tap.20", "diff/tap.17", "diff/tap.19"])

    def test_words_that_are_not_ids(self):
        self.assertEqual(self.ids("x (Cnt.c SRAM exception)"), ["Cnt.c"])
        self.assertEqual(self.ids("45 angles permitted on metal1 (Grid Rules)"), [])
        self.assertEqual(self.ids("npn emitter width < %d ()"), [])
        self.assertEqual(self.ids("no parentheses"), [])
        self.assertEqual(self.ids("x (pSD.e/f)"), ["pSD.e/f"])

    def test_why_text_without_closing_quote(self):
        why, head = B.why_text('widespacing m1 3000 m1 280 touching_ok "Metal1 > 3um (met1.3b)')
        self.assertEqual(why, "Metal1 > 3um (met1.3b)")
        self.assertEqual(head.split(), ["widespacing", "m1", "3000", "m1", "280", "touching_ok"])


class Drc(MiniPdk):
    def test_styles_and_default(self):
        drc = self.data["drc"]
        self.assertEqual(drc["styles"], ["drc(fast)", "drc(full)", "drc(routing)", "empty"])
        self.assertEqual(drc["magic_default_style"], "drc(fast)")

    def test_variants_switch_the_styles(self):
        self.assertEqual(self.rule("nwell.1")[0]["styles"], ["drc(fast)", "drc(full)"])
        self.assertEqual(self.rule("nwell.4")[0]["styles"], ["drc(full)"])
        self.assertEqual(self.rule("met1.6")[0]["styles"], ["drc(fast)", "drc(full)", "drc(routing)"])

    def test_counts_per_style(self):
        c = self.data["drc"]["counts"]
        self.assertEqual(c["rules"], 9)            # the commented rule is not one
        self.assertEqual(c["with_why"], 8)         # exact_overlap has none
        self.assertEqual(c["per_style"], {"drc(fast)": 8, "drc(full)": 9, "drc(routing)": 6,
                                          "empty": 0})

    def test_values_in_um(self):
        r = self.rule("nwell.1")[0]
        self.assertEqual((r["line"], r["keyword"], r["types"], r["value_um"], r["unit"]),
                         (119, "width", ["nwell"], 0.84, "um"))
        area = self.rule("met1.6")[0]
        self.assertEqual((area["value_um"], area["unit"]), (0.083, "um2"))
        ws = self.rule("met1.3b")[0]
        self.assertEqual((ws["value_um"], ws["width_um"], ws["types"]), (0.28, 3.0, ["metal1", "metal1"]))
        self.assertEqual(self.rule("nwell.4")[0]["value_um"], 0.0)

    def test_exemption_and_exception_blocks(self):
        rows = self.rule("licon.5a")
        self.assertEqual([r["block"] for r in rows], ["exemption SRAMID", "exception SRAMID"])
        self.assertEqual(rows[0]["ids"], ["licon.5a", "psdm.5a"])
        self.assertIsNone(self.rule("nwell.1")[0]["block"])

    def test_whole_shape_rules(self):
        self.assertTrue(self.rule("nwell.4")[0]["whole_shape"])
        self.assertFalse(self.rule("nwell.1")[0]["whole_shape"])


class Layers(MiniPdk):
    def row(self, l, d):
        return next(r for r in self.data["layers"] if r["gds"] == [l, d])

    def test_read_modes(self):
        self.assertEqual(self.row(64, 20)["read"], "paint")
        self.assertEqual(self.row(64, 20)["magic_types"], ["nwell"])
        self.assertEqual(self.row(65, 20)["read"], "paint")        # through a templayer
        self.assertIn("ndiff", self.row(65, 20)["magic_types"])
        self.assertEqual(self.row(93, 44)["read"], "device-only")
        self.assertEqual(sorted(self.row(93, 44)["decides"]), ["ndiff", "pdiff"])
        self.assertEqual(self.row(94, 20)["read"], "device-only")
        self.assertEqual(self.row(95, 20)["read"], "ignored")       # "ignore NPC"
        self.assertEqual(self.row(68, 16)["read"], "pin")
        self.assertEqual(self.row(68, 5)["read"], "text")
        self.assertEqual(self.row(77, 0)["read"], "ignored")        # mapped, never used

    def test_lyp_layers_magic_does_not_read(self):
        r = self.row(64, 44)
        self.assertEqual((r["name"], r["read"], r["in_lyp"], r["role"]),
                         ("pwell.drawing", "ignored", True, "well"))
        self.assertEqual(self.row(22, 10)["name"], "COMP_Label")
        self.assertEqual(self.row(22, 10)["role"], "text")
        self.assertEqual(self.row(68, 23)["read"], "ignored")

    def test_roles(self):
        self.assertEqual(self.row(93, 44)["role"], "implant")
        self.assertEqual(self.row(65, 20)["role"], "diffusion")
        self.assertEqual(self.row(68, 20)["role"], "conductor")
        self.assertEqual(self.row(68, 16)["role"], "pin")

    def test_layer_overrides(self):
        ov = {"layers": {"64/20": {"read": "reads-as:digisub", "_line": "t.tech:1"}}}
        secs = B.sections(B.statements(B.read_lines(
            os.path.join(self.root, "sky130A", "libs.tech", "magic", "sky130A.tech"))))
        canon, plane, contacts, aliases = B.parse_types(secs)
        rows = B.build_layers(B.parse_cifin(secs["cifinput"]), {}, canon, plane, contacts, ov)
        r = next(r for r in rows if r["gds"] == [64, 20])
        self.assertEqual(r["read"], "reads-as:digisub")
        self.assertNotIn("_line", r)


class Generated(MiniPdk):
    def test_cifout_table(self):
        c = self.data["cifout"]
        self.assertIn([93, 44], c["ndiff"])
        self.assertIn([65, 20], c["ndiff"])
        self.assertEqual(c["metal1"], [[68, 20]])   # the pin layer writes labels only
        self.assertNotIn("OTHER", json.dumps(c))       # not in the default variant

    def test_grow_from_the_device_shape(self):
        g = [g for g in self.data["generated"] if g["cif"] == "NSDM"]
        self.assertEqual(len(g), 1)
        g = g[0]
        self.assertEqual((g["gds"], g["grow_um"], g["file"], g["line"], g["from"], g["rule_ids"]),
                         ([93, 44], 0.125, "sky130A.tech", 48, "n-diffusion", ["n/psdm.5a"]))
        self.assertTrue(g["enclosure_check"])
        # the grow-then-shrink and close steps are noted, not counted
        self.assertIn("grow then shrink 0.185 um", g["note"])
        self.assertIn("close 0.265 um2", g["note"])

    def test_hand_typed_row(self):
        ov = {"generated": {"NSDM": [{"from": "n-diffusion", "types": ["nothing"], "grow_um": 0.2,
                                      "file": "sky130A.tech", "line": 12}]}}
        data = B.build("sky130A", self.root, {"sky130A": ov})
        g = next(g for g in data["generated"] if g["cif"] == "NSDM")
        self.assertEqual((g["grow_um"], g["line"], g["source"]), (0.2, 12, "overrides"))

    def test_contributions_of_grow_then_shrink(self):
        body = stmts_of('''
            layer X a
            grow 100
            bridge 270 270
            grow 130
            shrink 130
            calma 1 0
            ''')
        blocks, _ = B.parse_cif_blocks(body)
        parts = B.contributions(blocks[0], {}, 1.0)
        self.assertEqual([(p["from"], p["nm"]) for p in parts], [(["a"], 100.0)])
        self.assertEqual(len(parts[0]["closing"]), 2)


class Ports(MiniPdk):
    def test_convention(self):
        p = self.data["ports"]
        self.assertIn([68, 5], p["text"])
        self.assertIn([68, 20], p["text"])           # "labels MET1": a net name in Magic
        self.assertEqual(p["pin"], [[68, 16]])
        self.assertEqual(p["port_text"], [[68, 16]])
        self.assertEqual(p["klayout_lvs_text"], [[68, 5]])   # the commented call is not read
        self.assertEqual(p["both"], [{"text": [68, 5], "pin": [68, 16]}])
        self.assertEqual(p["magic_writes_port"], [[68, 16]])
        self.assertIn("libs.tech/klayout/lvs/sky130.lvs:3", p["lines"]["68/5"])
        self.assertIn("sky130A.tech:", p["lines"]["68/5"])

    def test_no_deck_text(self):
        text = json.dumps(self.data["ports"])
        self.assertNotIn("met1_label", text)
        self.assertNotIn("labels(", text)


class CommentLabels(unittest.TestCase):
    """A label layer that Magic reads onto a type of the comment plane
    (sky130A's text.drawing, read as comment) names no net: it goes in the
    ports table's "comment", not in "text"."""

    def test_comment_labels(self):
        tech = MINI_TECH.replace("  metal1 metal1,m1\nend", "  metal1 metal1,m1\n  comment comment\nend", 1)
        tech = tech.replace("  metal1,m1\nend", "  metal1,m1\n  comment\nend", 1)
        tech = tech.replace(" calma MET1 68 20", " layer comment TTEXT\n\tlabels TTEXT\n\n calma TTEXT 83 44\n"
                            " calma MET1 68 20", 1)
        root = tempfile.mkdtemp(prefix="kmp-pdkdata-")
        try:
            pdk = os.path.join(root, "sky130A")
            write(os.path.join(pdk, "libs.tech", "magic", "sky130A.tech"), tech)
            write(os.path.join(pdk, B.PDK_FILES["sky130A"]["lyp"]), MINI_LYP)
            write(os.path.join(pdk, B.PDK_FILES["sky130A"]["klayout_lvs"]), MINI_LVS)
            p = B.build("sky130A", root, {})["ports"]
        finally:
            shutil.rmtree(root, ignore_errors=True)
        self.assertEqual(p["comment"], [[83, 44]])
        self.assertNotIn([83, 44], p["text"])
        self.assertIn([68, 5], p["text"])

    def test_shipped(self):
        for pdk, ld in (("sky130A", [83, 44]), ("ihp-sg13g2", [63, 0]), ("ihp-sg13cmos5l", [63, 0])):
            with self.subTest(pdk=pdk):
                p = pdkdata.load(pdk).ports()
                self.assertIn(ld, p["comment"])
                self.assertNotIn(ld, p["text"])


class RuleNames(unittest.TestCase):
    def test_sky130a_enclosures_name_the_foundry_rule(self):
        """SkyWater's periphery rules name each enclosure that F1 measures on
        sky130A: licon.15 for npc, n/psdm.5b for the taps,
        hvtp.3 (not hvtp.4, the spacing) and lvtn.4b for the gates."""
        got = {(g["name"], g["from"]): g["rule_ids"] for g in pdkdata.load("sky130A").generated()
               if g["enclosure_check"]}
        self.assertEqual(got, {("psdm", "p-diffusion"): ["n/psdm.5a"], ("psdm", "p-tap"): ["n/psdm.5b"],
                               ("nsdm", "n-diffusion"): ["n/psdm.5a"], ("nsdm", "n-tap"): ["n/psdm.5b"],
                               ("lvtn", "fet gate (lvt)"): ["lvtn.4b"], ("hvtp", "pfet gate (hvt)"): ["hvtp.3"],
                               ("npc", "poly contact cut"): ["licon.15"]})


class Source(MiniPdk):
    def test_source_grid_and_lvs(self):
        d = self.data
        self.assertEqual(d["schema"], pdkdata.SCHEMA)
        self.assertEqual(d["grid_um"], 0.005)
        self.assertEqual(d["source"]["magic_tech_version"], "1.2.3")
        self.assertEqual(d["source"]["open_pdks"], "0123abc")
        self.assertEqual(d["source"]["tech"], "sky130A/libs.tech/magic/sky130A.tech")
        self.assertEqual(d["lvs"], {"netgen_setup": "libs.tech/netgen/sky130A_setup.tcl",
                                    "klayout_lvs": "libs.tech/klayout/lvs/sky130.lvs"})
        self.assertEqual(d["error_marker"], [255, 0])


class Check(MiniPdk):
    def setUp(self):
        self.out = os.path.join(self.root, "pdk-sky130A.json")
        with open(self.out, "w", encoding="utf-8") as f:
            f.write(B.dumps(self.data))
        self.saved = B.load_overrides
        B.load_overrides = lambda path=None: self.ov

    def tearDown(self):
        B.load_overrides = self.saved

    def run_check(self, profiles):
        import io
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = B.build_one("sky130A", self.root, self.out, True, profiles)
        return rc, buf.getvalue()

    GOOD = ({"sky130A": {"kind": "deck", "deck": "libs.tech/klayout/drc/mini.drc", "top": "top_cell",
                         "flags": {"feol": "true"}}}, [])

    def test_unchanged_file_passes(self):
        rc, out = self.run_check(self.GOOD)
        self.assertEqual(rc, 0, out)
        self.assertIn("PDK DATA OK", out)
        self.assertIn("KLAYOUT DRC PROFILE OK", out)

    def test_a_changed_file_fails(self):
        shipped = json.loads(B.dumps(self.data))
        shipped["drc"]["rules"][0]["value_um"] = 0.85
        with open(self.out, "w", encoding="utf-8") as f:
            f.write(B.dumps(shipped))
        rc, out = self.run_check(self.GOOD)
        self.assertEqual(rc, 1)
        self.assertIn("/drc/rules[119]/value_um: 0.84 != 0.85", out)

    def test_profile_switch_the_deck_does_not_read(self):
        bad = ({"sky130A": {"kind": "deck", "deck": "libs.tech/klayout/drc/mini.drc",
                            "top": "topcell", "flags": {"feol": "true", "beol": "true"}}}, [])
        rc, out = self.run_check(bad)
        self.assertEqual(rc, 1)
        self.assertIn("does not read the switch $beol", out)
        self.assertIn("does not read $topcell", out)

    def test_profile_deck_missing(self):
        rc, out = self.run_check(({"sky130A": {"kind": "deck", "deck": "nope.drc", "flags": {}}}, []))
        self.assertEqual(rc, 1)
        self.assertIn("not installed", out)

    def test_runner_options(self):
        write(os.path.join(self.root, "sky130A", "run_drc.py"), '"--no_density" "--mp"\n')
        prof = ({"sky130A": {"kind": "ihp", "runner": "run_drc.py"}}, ["--mp", "--no_density"])
        self.assertEqual(self.run_check(prof)[0], 0)
        prof = ({"sky130A": {"kind": "ihp", "runner": "run_drc.py"}}, ["--density_thr"])
        rc, out = self.run_check(prof)
        self.assertEqual(rc, 1)
        self.assertIn("takes no option --density_thr", out)

    def test_profiles_are_read_from_the_harness(self):
        profiles, opts = B.load_profiles()
        self.assertEqual(set(profiles), set(SUPPORTED_PDKS))
        self.assertIn("--no_density", opts)


class Shipped(unittest.TestCase):
    """The committed data files, through pdkdata."""

    def test_every_pdk_loads(self):
        for pdk in SUPPORTED_PDKS:
            d = pdkdata.load(pdk)
            self.assertEqual(d.pdk, pdk)
            self.assertEqual(d.grid_um, 0.005)
            self.assertEqual(d.drc["magic_default_style"], "drc(fast)")
            self.assertTrue(d.lvs["netgen_setup"].endswith("_setup.tcl"))
            self.assertEqual(d.error_marker, (255, 0))

    def test_rule_counts_per_style(self):
        # GAPS section 1 tables (sky130A's text says 287; its own TSV has 286 rows)
        want = {"sky130A": (249, 283, 110), "gf180mcuD": (181, 202, 172),
                "ihp-sg13g2": (307, 367, 281)}
        for pdk, (fast, full, routing) in want.items():
            c = pdkdata.load(pdk).drc["counts"]["per_style"]
            self.assertEqual((c["drc(fast)"], c["drc(full)"], c["drc(routing)"]), (fast, full, routing), pdk)
        # ihp-sg13cmos5l's table counts the 257 statements with a why-text
        rules = [r for r in pdkdata.load("ihp-sg13cmos5l").rules() if r["why"]]
        self.assertEqual(len(rules), 257)
        self.assertEqual(sum(1 for r in rules if r["styles"] == ["drc(full)"]), 38)

    def test_layers_magic_ignores(self):
        for pdk, pair in (("sky130A", (64, 44)), ("sky130A", (92, 44)), ("ihp-sg13g2", (8, 1)),
                          ("gf180mcuD", (22, 10))):
            self.assertEqual(pdkdata.load(pdk).layer(*pair)["read"], "ignored", (pdk, pair))
        d = pdkdata.load("sky130A")
        nets = [r for r in d.layers if r["name"].endswith((".net", ".probe"))]
        self.assertTrue(nets)
        self.assertTrue(all(r["read"] == "ignored" for r in nets))
        self.assertIsNone(d.layer(250, 250))

    def test_layers_read_as_another_type(self):
        self.assertEqual(pdkdata.load("ihp-sg13g2").layer("16/0")["read"], "reads-as:digisub")
        self.assertEqual(pdkdata.load("sky130A").layer([93, 44])["read"], "device-only")
        self.assertEqual(pdkdata.load("sky130A").layer(93, 44)["role"], "implant")

    def test_rules_by_why(self):
        d = pdkdata.load("sky130A")
        self.assertEqual([r["ids"] for r in d.rules_by_why("N-well width < %d (nwell.1)")], [["nwell.1"]])
        # as Magic prints it
        self.assertEqual([r["ids"] for r in d.rules_by_why("N-well width < 0.84um (nwell.1)")],
                         [["nwell.1"]])
        # a why-text with no value gives each rule once
        nw4 = [r for r in d.rules() if r["ids"] == ["nwell.4"]]
        self.assertEqual(len(d.rules_by_why(nw4[0]["why"])), len(nw4))
        # ihp-sg13g2's rule with an empty ID, keyed by its why-text
        g2 = pdkdata.load("ihp-sg13g2")
        empty = [r for r in g2.rules() if r["why"].endswith("()")]
        self.assertTrue(empty)
        self.assertIn(empty[0], g2.rules_by_why(empty[0]["why"]))

    def test_generated_cross_checks(self):
        def grow(pdk, cif, frm):
            return next(g["grow_um"] for g in pdkdata.load(pdk).generated()
                        if g["cif"] == cif and g["from"] == frm)
        self.assertEqual(grow("sky130A", "NSDM", "n-diffusion"), 0.125)   # a_nsdm_flush
        self.assertEqual(grow("ihp-sg13cmos5l", "PSD", "p-diffusion"), 0.18)    # u_pSD.c
        self.assertEqual(grow("ihp-sg13cmos5l", "PSD", "PMOS gate"), 0.3)       # u_pSD.i
        self.assertEqual(grow("ihp-sg13cmos5l", "THKOX", "HV diffusion"), 0.27)  # g_hv_tgo_small
        self.assertEqual(grow("gf180mcuD", "PPLUS", "p-tap"), 0.02)             # PP5_ov0
        for pdk in SUPPORTED_PDKS:
            for g in pdkdata.load(pdk).generated():
                if g["enclosure_check"]:
                    self.assertIsNotNone(g["grow_um"], (pdk, g["cif"], g["from"]))
                    self.assertTrue(g["line"] and g["file"], (pdk, g["cif"]))

    def test_ports(self):
        self.assertIn({"text": [67, 5], "pin": [67, 16]}, pdkdata.load("sky130A").ports()["both"])
        self.assertIn({"text": [34, 10], "pin": None}, pdkdata.load("gf180mcuD").ports()["both"])
        for pdk in ("ihp-sg13g2", "ihp-sg13cmos5l"):
            p = pdkdata.load(pdk).ports()
            self.assertIn({"text": [8, 25], "pin": [8, 2]}, p["both"])
            self.assertNotIn([8, 1], p["text"] + p["port_text"] + p["klayout_lvs_text"])

    def test_schema_keys(self):
        for pdk in SUPPORTED_PDKS:
            raw = pdkdata.load(pdk).raw
            self.assertEqual(list(raw), ["schema", "pdk", "source", "grid_um", "drc", "layers", "cifout",
                                         "generated", "ports", "lvs", "error_marker"])
            for r in raw["layers"]:
                self.assertIn(r["role"], ("implant", "marker", "well", "diffusion", "poly", "cut",
                                          "conductor", "text", "pin", "boundary", "other"))
                self.assertTrue(r["read"] in ("paint", "device-only", "pin", "text", "ignored")
                                or r["read"].startswith("reads-as:"), r)

    def test_wrong_schema_is_refused(self):
        with self.assertRaises(pdkdata.PdkDataError):
            pdkdata.PdkData({"schema": 99, "pdk": "x", "grid_um": 0.005})

    def test_wrong_pdk_is_refused(self):
        with self.assertRaises(pdkdata.PdkDataError):
            pdkdata.load("gf180mcuD", path=pdkdata.shipped_data("sky130A"))


if __name__ == "__main__":
    unittest.main()
