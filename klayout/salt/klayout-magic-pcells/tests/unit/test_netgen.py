"""netgen.py: the verdict on every form of netgen's result, and lvs.json.

The report tails below are copied from netgen 1.5.323 runs in the image:
the gap studies' runs on sky130A, ihp-sg13cmos5l and gf180mcuD, and the
lvs.json of a probe run on a sky130A open drain. The synthetic texts carry
netgen's own result strings, found with ``strings`` on its binary
(design-0.6.md 3.2).

EvidenceTest reads every netgen report in a folder of saved reports, laid
out as the patterns in it expect, when the environment variable
KMP_NETGEN_EVIDENCE names that folder. It is skipped when the variable is
unset, as it is in the image and in scripts/test.sh.
"""

import glob
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "python"))

from klayout_magic_pcells import netgen  # noqa: E402

# sky130A gap study, inv_base: a match.
MATCH = """\
Subcircuit summary:
Circuit 1: my_inv                          |Circuit 2: my_inv
-------------------------------------------|-------------------------------------------
sky130_fd_pr__nfet_01v8 (1)                |sky130_fd_pr__nfet_01v8 (1)
sky130_fd_pr__pfet_01v8_hvt (1)            |sky130_fd_pr__pfet_01v8_hvt (1)
Number of devices: 2                       |Number of devices: 2
Number of nets: 4                          |Number of nets: 4
---------------------------------------------------------------------------------------
Netlists match uniquely.

Subcircuit pins:
Circuit 1: my_inv                          |Circuit 2: my_inv
-------------------------------------------|-------------------------------------------
Y                                          |Y
A                                          |A
VGND                                       |VGND
VPWR                                       |VPWR
---------------------------------------------------------------------------------------
Cell pin lists are equivalent.
Device classes my_inv and my_inv are equivalent.

Final result: Circuits match uniquely.
.
"""

# sky130A gap study, d_gate_w036: W 0.36 against 0.65 (GAPS-sky130A 5.2).
PROPERTY = """\
Number of nets: 4                          |Number of nets: 4
---------------------------------------------------------------------------------------
Netlists match uniquely with property errors.
sky130_fd_pr__nfet_01v8:0 vs. sky130_fd_pr__nfet_01v8:M1:
 w circuit1: 0.36   circuit2: 0.65   (delta=57.4%, cutoff=1%)

Subcircuit pins:
Cell pin lists are equivalent.
Device classes my_inv and my_inv are equivalent.

Final result: Circuits match uniquely.
Property errors were found.

The following cells had property errors:
 my_inv
"""

# sky130A gap study, c_no_li_over_licon: the open drain.
NOMATCH = """\
Number of nets: 5 **Mismatch**             |Number of nets: 4 **Mismatch**
---------------------------------------------------------------------------------------
NET mismatches: Class fragments follow (with fanout counts):
Circuit 1: my_inv                          |Circuit 2: my_inv

---------------------------------------------------------------------------------------
Net: Y                                     |Net: Y
  sky130_fd_pr__pfet_01v8_hvt/(1|3) = 1    |  sky130_fd_pr__pfet_01v8_hvt/(1|3) = 1
                                           |  sky130_fd_pr__nfet_01v8/(1|3) = 1

Net: a_300_260#                            |(no matching net)
  sky130_fd_pr__nfet_01v8/(1|3) = 1        |
---------------------------------------------------------------------------------------
Netlists do not match.
Port matching may fail to disambiguate symmetries.

Subcircuit pins:
Cell pin lists are equivalent.
Device classes my_inv and my_inv are equivalent.

Final result: Netlists do not match.
Port matching may fail to disambiguate symmetries.
"""

# sky130A gap study, l_pin_only_li: port errors, then the pin failure.
PINS = """\
Cell my_inv (0) disconnected node: A
Number of nets: 4                          |Number of nets: 4
---------------------------------------------------------------------------------------
Netlists match uniquely with port errors.

Subcircuit pins:
Circuit 1: my_inv                          |Circuit 2: my_inv
-------------------------------------------|-------------------------------------------
Y                                          |Y
VGND                                       |VGND
VPWR                                       |VPWR
(no pin, node is a_240_460#)               |A
A                                          |(no matching pin)
---------------------------------------------------------------------------------------
Cell pin lists for my_inv and my_inv altered to match.
Device classes my_inv and my_inv are equivalent.

Final result: Top level cell failed pin matching.
"""

# ihp-sg13cmos5l gap study, port_txt: texts only, no pins.
IHP_NOPINS = """\
Subcircuit pins:
Circuit 1: port_txt                        |Circuit 2: port_txt
-------------------------------------------|-------------------------------------------
(no pins)                                  |VDD **Mismatch**
(no pin, node is A)                        |A
(no pin, node is Y)                        |Y
(no pin, node is VSS)                      |VSS
---------------------------------------------------------------------------------------
Cell pin lists for port_txt and port_txt altered to match.
Device classes port_txt and port_txt are equivalent.

Final result: Top level cell failed pin matching.
"""

# gf180mcuD gap study, inv_lab10swap: A and Y swapped.
GF_SWAP = """\
Y                                          |A **Mismatch**
VSS                                        |VSS
VDD                                        |VDD
---------------------------------------------------------------------------------------
Cell pin lists for inv and inv altered to match.
Device classes inv and inv are equivalent.

Final result: Top level cell failed pin matching.
"""

# sky130A gap study, standard cell inv_1 (netgen's log): netgen's stdout puts the result on its own line.
STDOUT_FORM = """\
Device classes sky130_fd_sc_hd__inv_1 and sky130_fd_sc_hd__inv_1 are equivalent.

Final result:
Circuits match uniquely.
.
Logging to file "/w/out/stdcell/inv_1/lvs.report" disabled
"""


def tail(final, *after):
    return "Netlists match uniquely.\n\nFinal result: %s\n%s" % (final, "".join(a + "\n" for a in after))


class VerdictTest(unittest.TestCase):
    def check(self, text, matched, final=None, **flags):
        v = netgen.parse_report(text)
        self.assertEqual(v.matched, matched, v)
        self.assertTrue(v.complete)
        if final is not None:
            self.assertEqual(v.final, final)
        for k, want in flags.items():
            self.assertEqual(getattr(v, k), want, "%s in %r" % (k, v))
        if not matched:
            self.assertTrue(v.reasons, "a failure says why")
        return v

    # -- the gap studies' reports --

    def test_match(self):
        v = self.check(MATCH, True, "Circuits match uniquely.")
        self.assertEqual(v.reasons, [])

    def test_property_errors_after_a_match(self):
        v = self.check(PROPERTY, False, "Circuits match uniquely.", property_errors=True)
        self.assertIn("netgen: Property errors were found.", v.reasons)
        self.assertEqual(v.property_cells, ["my_inv"])

    def test_no_match(self):
        self.check(NOMATCH, False, "Netlists do not match.", pin_errors=False)

    def test_pin_failure(self):
        self.check(PINS, False, "Top level cell failed pin matching.", pin_errors=True)

    def test_ihp_texts_only(self):
        self.check(IHP_NOPINS, False, "Top level cell failed pin matching.", pin_errors=True)

    def test_gf180_swap(self):
        self.check(GF_SWAP, False, "Top level cell failed pin matching.", pin_errors=True)

    def test_stdout_form(self):
        self.check(STDOUT_FORM, True, "Circuits match uniquely.")

    # -- netgen's other result strings (design-0.6.md 3.2) --

    def test_symmetries_are_a_match(self):
        v = self.check(tail("Circuits match with 2 symmetries."), True)
        self.assertEqual(v.symmetries, 2)
        v = self.check(tail("Circuits match with 1 symmetry."), True)
        self.assertEqual(v.symmetries, 1)
        self.check("Netlists match with 4 symmetries.\nFinal result: Netlists match with 4 symmetries.\n", True)

    def test_port_errors(self):
        self.check(tail("Circuits match uniquely with port errors."), False, port_errors=True)
        self.check(tail("Netlists match uniquely with port errors."), False, port_errors=True)
        self.check(tail("Netlists match with 2 symmetries with port errors."), False, port_errors=True)

    def test_property_errors_in_the_final_line(self):
        self.check(tail("Netlists match uniquely with property errors."), False, property_errors=True)

    def test_property_errors_after(self):
        self.check(tail("Circuits match uniquely.", "Property errors were found."), False, property_errors=True)
        self.check(tail("Circuits match with 3 symmetries.", "Property errors were found."), False,
                   property_errors=True)

    def test_pin_failure_after_a_match(self):
        self.check(tail("Circuits match uniquely.", "Top level cell failed pin matching."), False,
                   pin_errors=True)

    def test_pin_lists_do_not_match(self):
        text = "Cell pin lists for inv and inv do not match.\n" + tail("Circuits match uniquely.")
        v = self.check(text, False, pin_errors=True)
        self.assertEqual(v.pin_lists, [("inv", "inv")])

    def test_subcell_failure(self):
        self.check(tail("Netlists do not match.", "Subcell(s) failed matching."), False, subcell_errors=True)
        self.check(tail("Circuits match uniquely.", "The following subcells failed to match:", " inv_1"),
                   False, subcell_errors=True)

    def test_no_final_result(self):
        v = netgen.parse_report("Netlists match uniquely.\n")
        self.assertFalse(v.matched)
        self.assertFalse(v.complete)
        self.assertIn("no final result", v.reasons[0])

    def test_unknown_final_result_fails(self):
        v = netgen.parse_report("Final result: Something new.\n")
        self.assertFalse(v.matched)
        self.assertIn("Something new", v.reasons[0])

    def test_last_final_result_counts(self):
        text = "Final result: Netlists do not match.\n\nFinal result: Circuits match uniquely.\n"
        self.check(text, True)


# The probe's lvs.json (the open drain on sky130A), as netgen wrote it.
OPEN_DRAIN_JSON = """[
  {"pins": [["1","2","3","4"], ["1","2","3","4"]]},
  {"pins": [["1","2","3","4"], ["1","2","3","4"]]},
  {"name": ["my_inv", "my_inv"],
   "devices": [[["sky130_fd_pr__nfet_01v8", 1], ["sky130_fd_pr__pfet_01v8_hvt", 1 ]],
               [["sky130_fd_pr__nfet_01v8", 1 ], ["sky130_fd_pr__pfet_01v8_hvt", 1 ]]],
   "nets": [5, 4],
   "badnets": [[[["a_300_260#", [[ "sky130_fd_pr__nfet_01v8", "1|3", 1 ]]],
                 ["Y", [[ "sky130_fd_pr__pfet_01v8_hvt", "1|3", 1 ]]]],
                [["Y", [[ "sky130_fd_pr__nfet_01v8", "1|3", 1 ], [ "sky130_fd_pr__pfet_01v8_hvt", "1|3", 1 ]]],
                 ["(no matching net)", [[ "", "", 0 ]]]]]],
   "badelements": [],
   "pins": [[""], [""]]}
]"""

# This build's runs (lvsjob on the case suite's sky130A inverters).
W036_JSON = """[{"name": ["inv_w036", "inv_w036"],
 "devices": [[["sky130_fd_pr__nfet_01v8", 1], ["sky130_fd_pr__pfet_01v8_hvt", 1]],
             [["sky130_fd_pr__nfet_01v8", 1], ["sky130_fd_pr__pfet_01v8_hvt", 1]]],
 "nets": [4, 4], "badnets": [], "badelements": [],
 "properties": [[["sky130_fd_pr__nfet_01v8:0", [["w", "0.36"]]], ["sky130_fd_pr__nfet_01v8:M1", [["w", "0.65"]]]]],
 "pins": [["Y", "A", "VGND", "VPWR"], ["Y", "A", "VGND", "VPWR"]]}]"""
SWAP_JSON = """[{"name": ["inv_swap", "inv_swap"], "devices": [[], []], "nets": [4, 4], "badnets": [],
 "badelements": [], "pins": [["A", "Y", "VGND", "VPWR"], ["(no matching pin)", "(no matching pin)", "VGND", "VPWR"]]}]"""
NOTEXT_JSON = """[{"name": ["inv_no_text", "inv_no_text"], "devices": [[], []], "nets": [4, 4], "badnets": [],
 "badelements": [], "pins": [["(no pins)", "(no matching pin)", "(no matching pin)", "(no matching pin)"],
 ["(no matching pin)", "A", "Y", "VGND"]]}]"""

# The pin table of netgen's report (netgen 1.5.323) on another texts-only
# sky130A inverter, my_inv, against its schematic. Where the JSON's
# "(no pins)" row has "(no matching pin)" on the schematic side, the
# report names VPWR. The test gives NOTEXT_JSON that cell's name.
NOTEXT_REPORT = """\
Netlists match uniquely with port errors.

Subcircuit pins:
Circuit 1: my_inv                          |Circuit 2: my_inv                          
-------------------------------------------|-------------------------------------------
(no pins)                                  |VPWR **Mismatch**                          
(no pin, node is A)                        |A                                          
(no pin, node is Y)                        |Y                                          
(no pin, node is VGND)                     |VGND                                       
---------------------------------------------------------------------------------------
Cell pin lists for my_inv and my_inv altered to match.
Device classes my_inv and my_inv are equivalent.

Final result: Top level cell failed pin matching.
"""


class JsonTest(unittest.TestCase):
    def test_p3(self):
        cs = netgen.parse_json(OPEN_DRAIN_JSON)
        self.assertEqual(len(cs), 1, "the black-box pin entries are left out")
        c = cs[0]
        self.assertEqual(c.name, ("my_inv", "my_inv"))
        self.assertEqual(c.nets, (5, 4))
        self.assertEqual(c.devices[0], {"sky130_fd_pr__nfet_01v8": 1, "sky130_fd_pr__pfet_01v8_hvt": 1})
        self.assertEqual(len(c.badnets), 1)
        lay, sch = c.badnets[0]
        self.assertEqual([n for n, _ in lay], ["a_300_260#", "Y"])
        self.assertEqual([n for n, _ in sch], ["Y", netgen.NO_NET])
        self.assertEqual(lay[0][1], [("sky130_fd_pr__nfet_01v8", "1|3", 1)])
        self.assertEqual(c.pins, ([], []))
        self.assertEqual(c.pin_pairs(), [])

    def test_properties(self):
        c = netgen.parse_json(W036_JSON)[0]
        self.assertEqual(c.properties, [(("sky130_fd_pr__nfet_01v8:0", {"w": "0.36"}),
                                         ("sky130_fd_pr__nfet_01v8:M1", {"w": "0.65"}))])

    def test_pins(self):
        c = netgen.parse_json(SWAP_JSON)[0]
        self.assertEqual(c.pin_pairs()[:2], [("A", netgen.NO_PIN), ("Y", netgen.NO_PIN)])
        c = netgen.parse_json(NOTEXT_JSON)[0]
        self.assertEqual(c.pin_pairs()[0], (netgen.NO_PINS, netgen.NO_PIN))
        self.assertEqual(c.pin_pairs()[1], (netgen.NO_PIN, "A"))

    def test_the_report_names_the_pin_the_json_leaves_out(self):
        """With the report's pin table, the "(no pins)" row has
        its schematic pin, VPWR."""
        rows = netgen.report_pins(NOTEXT_REPORT)
        self.assertEqual(rows, {("my_inv", "my_inv"): [("(no pins)", "VPWR"), ("(no pin, node is A)", "A"),
                                                       ("(no pin, node is Y)", "Y"),
                                                       ("(no pin, node is VGND)", "VGND")]})
        c = netgen.parse_json(NOTEXT_JSON.replace("inv_no_text", "my_inv"))[0]
        c.report_pins = rows[c.name]
        self.assertEqual(c.pin_pairs(), [(netgen.NO_PINS, "VPWR"), (netgen.NO_PIN, "A"), (netgen.NO_PIN, "Y"),
                                         (netgen.NO_PIN, "VGND")])

    def test_circuit_choice(self):
        cs = netgen.parse_json(OPEN_DRAIN_JSON) + netgen.parse_json(W036_JSON)
        self.assertEqual(netgen.circuit(cs, "inv_w036").name[0], "inv_w036")
        self.assertEqual(netgen.circuit(cs, "nothing").name[0], "inv_w036")
        self.assertIsNone(netgen.circuit([], "x"))

    def test_command(self):
        class Cfg:
            netgen = "netgen"
            netgen_setup = "/pdk/setup.tcl"
        cmd = netgen.command(Cfg, "/j/netlist.spice", "inv", "/s/inv.spice", "inv", "/j/lvs/lvs.out")
        self.assertEqual(cmd, ["netgen", "-batch", "lvs", "/j/netlist.spice inv", "/s/inv.spice inv",
                               "/pdk/setup.tcl", "/j/lvs/lvs.out", "-json"])

    def test_subcircuits(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".spice", delete=False) as f:
            f.write("* x\n.subckt inv A Y VDD VSS\nX1 a b c d m\n.ends\n.SUBCKT buf A Y\n.ends\n")
        try:
            self.assertEqual(netgen.subcircuits(f.name), ["inv", "buf"])
        finally:
            os.unlink(f.name)


# A folder of saved netgen reports, or None: EvidenceTest runs only when
# KMP_NETGEN_EVIDENCE names one.
EVIDENCE = os.environ.get("KMP_NETGEN_EVIDENCE")


@unittest.skipUnless(EVIDENCE and os.path.isdir(EVIDENCE), "KMP_NETGEN_EVIDENCE does not name a folder")
class EvidenceTest(unittest.TestCase):
    """Every netgen report in the KMP_NETGEN_EVIDENCE folder: the verdict
    agrees with its final result, and every failure has a reason."""

    def test_all_reports(self):
        pats = ["sky130A/out/**/lvs.report", "gf180mcuD/out/**/*.netgen.txt",
                "ihp-sg13cmos5l/tests/lvs/res/*/netgen.out", "ihp-sg13g2/lvs/**/*.out",
                "design/probes/out/p3/lvs.out"]
        files = sorted({p for pat in pats for p in glob.glob(os.path.join(EVIDENCE, pat), recursive=True)})
        seen = 0
        for path in files:
            with open(path, errors="replace") as f:
                text = f.read()
            if "Final result" not in text:
                continue
            seen += 1
            v = netgen.parse_report(text)
            self.assertTrue(v.complete, path)
            after = text.split("Final result:")[-1]
            want = (v.final.startswith(("Circuits match uniquely.", "Circuits match with"))
                    and "Property errors" not in after and "failed pin matching" not in after
                    and "port errors" not in v.final)
            self.assertEqual(v.matched, want, path)
            if not v.matched:
                self.assertTrue(v.reasons, path)
        self.assertGreater(seen, 20)

    def test_all_json(self):
        for path in glob.glob(os.path.join(EVIDENCE, "**", "*.json"), recursive=True):
            if "/plugin" in path or "lvs" not in os.path.basename(path):
                continue
            with open(path, errors="replace") as f:
                try:
                    obj = json.load(f)
                except ValueError:
                    continue
            if isinstance(obj, list) and any(isinstance(c, dict) and "badnets" in c for c in obj):
                for c in netgen.parse_json(obj):
                    self.assertEqual(len(c.name), 2, path)


if __name__ == "__main__":
    unittest.main()
