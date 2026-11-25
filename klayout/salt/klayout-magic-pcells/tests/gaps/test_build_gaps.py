"""Unit tests for tools/build_gaps.py: the deck scan, the join, the aliases,
the statuses and the --check comparison, on small fixtures. No Magic,
KLayout or PDK is needed:

    python3 -m unittest tests.gaps.test_build_gaps
"""

import importlib.util
import json
import os
import re
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "python"))

_spec = importlib.util.spec_from_file_location("build_gaps", os.path.join(REPO, "tools", "build_gaps.py"))
bg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bg)

from klayout_magic_pcells.pdkdata import PdkData  # noqa: E402


def rule(line, why, ids, value=0.1, keyword="width", styles=("drc(fast)", "drc(full)"), unit="um", id_text=None):
    return {"line": line, "file": "t.tech", "keyword": keyword, "styles": list(styles), "value_um": value,
            "unit": unit, "why": why, "ids": list(ids),
            "id_text": id_text if id_text is not None else ", ".join(ids)}


RULES = [
    rule(10, "Poly width < %d (poly.1)", ["poly.1"], 0.15),
    rule(11, "Poly spacing < %d (poly.2)", ["poly.2"], 0.21),
    rule(12, "Via width < %d (via.1 + 2 * via.4)", ["via.1", "via.4"], 0.26, id_text="via.1 + 2 * via.4"),
    rule(13, "Diff spacing < %d (diff/tap.3)", ["diff/tap.3"], 0.27),
    rule(14, "Well spacing < %d (W.e/f)", ["W.e/f"], 0.3),
    rule(15, "Old name < %d (Old.1)", ["Old.1"], 0.4),
    rule(16, "Same ID, first meaning < %d (D.5)", ["D.5"], 0.12),
    rule(17, "Same ID, second meaning < %d (D.5)", ["D.5"], 0.16),
    rule(18, "Ohmic overhang < %d (FIXME)", [], 0.32),
    rule(19, "Metal area < %d (M.3)", ["M.3"], 0.144, keyword="area", unit="um2"),
    rule(20, "", [], None, keyword="exact_overlap"),
    rule(21, "Taps must be within 15um (LU.2)", ["LU.2"], 0.0, keyword="cifmaxwidth", styles=("drc(full)",)),
    rule(22, "Gate overlap < %d (G.1)", ["G.1"], 0.13),
]

ALIASES = {
    "pdk": "test",
    "magic": {
        "split": {"W.e/f": ["W.e", "W.f"]},
        "ids": {"Old.1": "New.1"},
        "lines": {"t.tech:17": ["D.17"]},
        "why": [["\\(FIXME\\)$", "varactor overhang"]],
    },
    "klayout": {
        "*": {"patterns": [["^.+_OFFGRID$", "x.1b"], ["^(.+)_(LV|MV)$", "\\1"]]},
        "deckA": {
            "names": {"m1.3ab": ["met1.3a", "met1.3b"]},
            "patterns": [["^difftap\\.(\\w+)$", "diff/tap.\\1"]],
            "other_check": {"poly.2": "core spacing, another rule"},
        },
    },
    "status": {"M.3": {"status": "measured on other shapes", "note": "fixture"}},
    "parts": [{"name": "Upper", "match": "^M\\."}, {"name": "Front", "match": ".*"}],
}


def data(rules=RULES):
    return PdkData({"schema": 1, "pdk": "test", "grid_um": 0.005,
                    "source": {"open_pdks": "abc"}, "drc": {"styles": ["drc(fast)", "drc(full)"], "rules": rules}})


def raw(inventory, tests=None, runs=None):
    runs = runs or [{"id": "harness", "deck": "deckA", "primary": True, "what": "deck A"},
                    {"id": "extra", "deck": "deckB", "primary": False, "what": "deck B"}]
    located = {"deckA": {}, "deckB": {}}
    r = {"runs": runs, "inventory": inventory, "located": located, "image": "img", "tools": {}}
    if tests:
        r["tests"] = tests
    return r


class Values(unittest.TestCase):
    def test_value_of(self):
        self.assertEqual(bg.value_of("nwell.1 : min. nwell width : 0.84um"), [0.84, "um"])
        self.assertEqual(bg.value_of("DF.6_LV : Min. COMP extend beyond gate : 0.24µm"), [0.24, "um"])
        self.assertEqual(bg.value_of("5.1.NW.b : Min. space ... is 0.62 um"), [0.62, "um"])
        self.assertEqual(bg.value_of("m1.6 : min. metal1 area : 0.083um²"), [0.083, "um2"])
        self.assertEqual(bg.value_of("NW.a ... = 0.62"), [0.62, None])
        self.assertEqual(bg.value_of("V1.4a : metal2 overlap of via1 >= 0.01 upper_metal"), [0.01, None])
        self.assertIsNone(bg.value_of("m1.4 : mcon periphery must be enclosed by m1"))
        self.assertIsNone(bg.value_of(None))

    def test_is_composite(self):
        for t in ("via.1a + 2 * via.4a", "via.5a - via.4a", "MIMTM.4-VT.4", "VT.1+VT.3", "pSD.i + pSD.d1"):
            self.assertTrue(bg.is_composite(t), t)
        for t in ("nwell.5a, 7", "diff/tap.18,20", "LU.c, LU.c1", "pSD.e/f", "poly.1", ""):
            self.assertFalse(bg.is_composite(t), t)


class Scan(unittest.TestCase):
    DECK = "\n".join([
        "if FEOL",                                         # 1
        "  nwell.width(0.84).output(\"nwell.1\", \"desc\")",  # 2
        "  # x.output(\"commented.1\", \"gone\")",         # 3
        "  unless $precheck_drc",                          # 4
        "    a.output('NW.b1', 'desc')",                   # 5
        "  end",                                           # 6
        "  [1, 2].each do |n|",                            # 7
        "    m.output(\"M#{n}.a\", \"loop\")",             # 8
        "  end",                                           # 9
        "else",                                            # 10
        "  b.output(",                                     # 11
        "    \"ELSE.1\", \"desc\")",                       # 12
        "end",                                             # 13
        "c.output(\"TOP.1\", \"desc\") if OFFGRID",        # 14
        "def output(x)",                                   # 15
        "end",                                             # 16
    ])

    def test_scan(self):
        outs = {o["name"]: o for o in bg.scan_deck(self.DECK, "deck.drc")}
        self.assertNotIn("commented.1", outs)
        self.assertEqual(outs["nwell.1"]["line"], 2)
        self.assertEqual(outs["nwell.1"]["switch"], "FEOL")
        self.assertEqual(outs["NW.b1"]["switch"], "FEOL & not precheck_drc")
        self.assertEqual(outs["M#{n}.a"]["switch"], "FEOL")
        self.assertEqual(outs["ELSE.1"]["line"], 11)
        self.assertEqual(outs["ELSE.1"]["switch"], "not (FEOL)")
        self.assertEqual(outs["TOP.1"]["switch"], "")

    def test_register_tags(self):
        text = "GF180_DRC_REGISTRY.register(\n  id: 'comp',\n  tags: %w[all feol comp]\n) do |ctx|\n" \
               "  x.output(\"DF.1a_LV\", \"d\")\nend\n"
        o = bg.scan_deck(text, "comp.rb")[0]
        self.assertEqual((o["name"], o["line"], o["tags"]), ("DF.1a_LV", 5, ["feol", "comp"]))

    def test_locate(self):
        outs = bg.scan_deck(self.DECK, "deck.drc")
        found = bg.locate(["nwell.1", "M2.a", "NOT.THERE"], outs)
        self.assertEqual(found["nwell.1"][0]["line"], 2)
        self.assertEqual(found["M2.a"][0]["line"], 8)
        self.assertNotIn("NOT.THERE", found)


class Aliases(unittest.TestCase):
    def test_magic_entries(self):
        m = bg.magic_entries(RULES, ALIASES)
        self.assertIn("W.e", m)
        self.assertIn("W.f", m)
        self.assertNotIn("W.e/f", m)
        self.assertIn("New.1", m)
        self.assertEqual(m["New.1"][0]["id"], "Old.1")
        self.assertEqual([e["line"] for e in m["D.5"]], [16])
        self.assertEqual([e["line"] for e in m["D.17"]], [17])
        self.assertEqual(m["D.17"][0]["id"], "D.5")
        self.assertIn("varactor overhang", m)
        self.assertIn("exact_overlap", m)
        self.assertFalse(m["via.1"][0]["operand"])
        self.assertTrue(m["via.4"][0]["operand"])
        self.assertEqual(m["LU.2"][0]["value"], 15.0)

    def test_empty_id_keyed_by_why(self):
        m = bg.magic_entries(RULES, {"pdk": "test"})
        self.assertIn("Ohmic overhang < %d (FIXME)", m)

    def test_kl_keys(self):
        self.assertEqual(bg.kl_keys("difftap.3", "deckA", ALIASES), (["diff/tap.3"], None))
        self.assertEqual(bg.kl_keys("difftap.3", "deckB", ALIASES), (["difftap.3"], None))
        self.assertEqual(bg.kl_keys("m1.3ab", "deckA", ALIASES)[0], ["met1.3a", "met1.3b"])
        self.assertEqual(bg.kl_keys("metal1_OFFGRID", "deckB", ALIASES)[0], ["x.1b"])
        self.assertEqual(bg.kl_keys("DF.6_MV", "deckB", ALIASES)[0], ["DF.6"])
        keys, note = bg.kl_keys("poly.2", "deckA", ALIASES)
        self.assertEqual(keys, ["poly.2 [deckA]"])
        self.assertTrue(note)

    def test_shipped_alias_files(self):
        for pdk in bg.PDKS:
            a = bg.load_aliases(pdk)
            self.assertEqual(a["pdk"], pdk)
            for scope in a.get("klayout", {}).values():
                for pat, repl in scope.get("patterns", []):
                    re.compile(pat)
            for pat, _ in a.get("magic", {}).get("why", []):
                re.compile(pat)
            for k, v in a.get("magic", {}).get("lines", {}).items():
                self.assertRegex(k, r"^[\w.-]+:\d+$")
                self.assertIsInstance(v, list)
            for k, v in a.get("status", {}).items():
                self.assertIn(v["status"], bg.STATUSES)
            self.assertEqual(a["parts"][-1]["match"], ".*", pdk)


class Statuses(unittest.TestCase):
    INV = {
        "harness": {"poly.1": [0.15, "um"], "poly.2": [0.16, "um"], "difftap.3": [0.27, "um"],
                    "via.4": [0.055, "um"], "via.1": [0.15, "um"], "M.3": [0.1444, "um2"],
                    "G.1": [0.18, "um"], "KL.only": None, "W.e_LV": [0.3, "um"], "D.17_LV": [0.16, "um"]},
        "extra": {"New.1": [0.5, "um"], "W.f": [0.3, "um"]},
    }

    def rows(self, tests=None):
        rows, one_side, counts = bg.build_rows("test", data(), ALIASES, raw(self.INV, tests))
        return {r["key"]: r for r in rows}, one_side, counts

    def test_inventory_statuses(self):
        r, _, counts = self.rows()
        self.assertEqual(r["poly.1"]["status"], "both")
        self.assertEqual(r["diff/tap.3"]["status"], "both")
        self.assertEqual(r["via.1"]["status"], "both")          # composite: no value comparison
        self.assertEqual(r["via.4"]["status"], "folded")
        self.assertEqual(r["G.1"]["status"], "both, values differ")
        self.assertIn("0.13", r["G.1"]["note"])
        self.assertIn("0.18", r["G.1"]["note"])
        self.assertEqual(r["M.3"]["status"], "measured on other shapes")
        self.assertEqual(r["poly.2"]["status"], "Magic only")
        self.assertEqual(r["poly.2 [deckA]"]["status"], "same name for another check")
        self.assertEqual(r["New.1"]["status"], "Magic only")
        self.assertIn("deckB has it, with other values", r["New.1"]["note"])
        self.assertEqual(r["W.e"]["status"], "both")
        self.assertEqual(r["W.f"]["status"], "Magic only")
        self.assertEqual(r["KL.only"]["status"], "KLayout only")
        self.assertEqual(r["M.3"]["part"], "Upper")
        self.assertEqual(sum(sum(c.values()) for c in counts.values()), len(r))

    def tests_fixture(self):
        return {
            "cases": [
                {"name": "ctl", "top": "ctl", "targets": [], "control": None},
                {"name": "bad_poly1", "top": "bad_poly1", "targets": ["poly.1"], "control": "ctl"},
                {"name": "bad_g1", "top": "bad_g1", "targets": ["G.1"], "control": "ctl"},
                {"name": "bad_old", "top": "bad_old", "targets": ["Old.1"], "control": None},
                {"name": "bad_d17", "top": "bad_d17", "targets": ["D.5", "D.17_LV"], "control": None},
            ],
            "magic": {
                "ctl": {"drc(fast)": {"Diff spacing < 0.27um (diff/tap.3)": 1}, "drc(full)": {}},
                "bad_poly1": {"drc(fast)": {"Poly width < 0.15um (poly.1)": 1,
                                            "Diff spacing < 0.27um (diff/tap.3)": 1},
                              "drc(full)": {"Poly width < 0.15um (poly.1)": 1}},
                "bad_g1": {"drc(fast)": {}, "drc(full)": {}},
                "bad_old": {"drc(fast)": {"Old name < 0.4um (Old.1)": 2}, "drc(full)": {}},
                "bad_d17": {"drc(fast)": {"Same ID, second meaning < 0.16um (D.5)": 1}, "drc(full)": {}},
            },
            "klayout": {"harness": {"ctl": {"difftap.3": 1}, "bad_poly1": {"difftap.3": 1},
                                    "bad_g1": {"G.1": 1}, "bad_old": {}, "bad_d17": {"D.17_LV": 1}},
                        "extra": {}},
        }

    def test_tests_and_did_not_fire(self):
        r, one_side, _ = self.rows(self.tests_fixture())
        self.assertEqual(r["poly.1"]["status"], "in the deck, did not fire on its case")
        self.assertIn("KLayout reported nothing on bad_poly1", r["poly.1"]["note"])
        self.assertEqual(r["poly.1"]["tested"], [{"case": "bad_poly1", "magic": "FU", "klayout": []}])
        # values differ stays, with the test in the tested column
        self.assertEqual(r["G.1"]["status"], "both, values differ")
        self.assertEqual(r["G.1"]["tested"], [{"case": "bad_g1", "magic": "", "klayout": ["harness"]}])
        # a target named by Magic's printed ID reaches the renamed row
        self.assertEqual(r["New.1"]["tested"][0]["case"], "bad_old")
        # the control's diff/tap.3 is subtracted
        self.assertNotIn("diff/tap.3", one_side["magic"])
        self.assertEqual(one_side["magic"].get("poly.1"), ["bad_poly1"])
        self.assertEqual(one_side["klayout"].get("G.1"), ["bad_g1"])
        self.assertNotIn("ctl", [c for v in one_side["magic"].values() for c in v])
        # "D.5" names two rows; the case's other target picks the one it means
        self.assertEqual(r["D.17"]["tested"], [{"case": "bad_d17", "magic": "F", "klayout": ["harness"]}])
        self.assertEqual(r["D.5"]["tested"], [])
        self.assertEqual(r["D.17"]["status"], "both")

    def test_message_keys(self):
        d = data()
        by_line = bg.magic_keys_by_line(RULES, ALIASES)
        self.assertEqual(bg.message_keys("Same ID, second meaning < 0.16um (D.5)", d, by_line), ["D.17"])
        self.assertEqual(bg.message_keys("Ohmic overhang < 0.32um (FIXME)", d, by_line), ["varactor overhang"])
        self.assertEqual(bg.message_keys("Something Magic says (Z.9)", d, by_line), ["Z.9"])
        self.assertEqual(bg.message_keys("Can't overlap those layers", d, by_line), ["Can't overlap those layers"])

    def test_composite_operand_is_not_a_target(self):
        """A case filed under via.1 is not via.4's test, though Magic prints
        via.1 for "via.1 + 2 * via.4"; a case that names via.4 itself is."""
        t = self.tests_fixture()
        t["cases"] += [{"name": "bad_via1", "top": "bad_via1", "targets": ["via.1"], "control": None},
                       {"name": "bad_via4", "top": "bad_via4", "targets": ["via.4"], "control": None}]
        t["magic"]["bad_via1"] = {"drc(fast)": {"Via width < 0.26um (via.1 + 2 * via.4)": 1}, "drc(full)": {}}
        t["magic"]["bad_via4"] = {"drc(fast)": {"Via width < 0.26um (via.1 + 2 * via.4)": 1}, "drc(full)": {}}
        t["klayout"]["harness"].update({"bad_via1": {"via.1": 1}, "bad_via4": {"via.4": 1}})
        r, _, _ = self.rows(t)
        self.assertEqual(r["via.1"]["tested"], [{"case": "bad_via1", "magic": "F", "klayout": ["harness"]}])
        self.assertEqual(r["via.4"]["tested"], [{"case": "bad_via4", "magic": "F", "klayout": ["harness"]}])
        self.assertEqual(r["via.4"]["status"], "folded")

    def test_pkg_json(self):
        rows, _, _ = bg.build_rows("test", data(), ALIASES, raw(self.INV))
        doc = bg.pkg_json("test", rows)
        self.assertEqual(doc["schema"], 2)
        p = doc["rules"]
        self.assertEqual(p["poly.1"], {"status": "both", "key": "poly.1", "ids": ["poly.1"], "lines": ["t.tech:10"],
                                       "klayout": [{"deck": "deckA", "name": "poly.1", "value": 0.15}]})
        # one entry per row, under the row's key: D.5's two statements are two rows
        self.assertEqual((p["D.5"]["lines"], p["D.5"]["ids"]), (["t.tech:16"], ["D.5"]))
        self.assertEqual((p["D.17"]["lines"], p["D.17"]["ids"]), (["t.tech:17"], ["D.5"]))
        self.assertNotIn("Same ID, second meaning < %d (D.5)", p)
        # a split ID: one statement, two rows
        self.assertEqual((p["W.e"]["lines"], p["W.f"]["lines"]), (["t.tech:14"], ["t.tech:14"]))
        self.assertEqual((p["varactor overhang"]["lines"], p["varactor overhang"]["ids"]), (["t.tech:18"], []))
        self.assertEqual(p["via.1"]["lines"], ["t.tech:12"])
        self.assertNotIn("via.4", p)    # an operand only: its statement's message is via.1's
        self.assertNotIn("KL.only", p)  # no Magic statement
        lines = [fl for e in p.values() for fl in e["lines"]]
        self.assertEqual(sorted(set(lines)), sorted("t.tech:%d" % r["line"] for r in RULES))


class Check(unittest.TestCase):
    def test_compare(self):
        with tempfile.TemporaryDirectory() as d:
            same, diff, missing = (os.path.join(d, n) for n in ("a.md", "b.md", "c.md"))
            for p in (same, diff):
                with open(p, "w", encoding="utf-8") as f:
                    f.write("one\ntwo\n")
            bad = dict(bg.compare({same: "one\ntwo\n", diff: "one\nthree\n", missing: "x\n"}))
            self.assertNotIn(same, bad)
            self.assertIn("+three", bad[diff])
            self.assertEqual(bad[missing], "missing")

    def test_outputs_are_stable(self):
        r = raw(Statuses.INV)
        a, _ = bg.outputs("test", r, data=data(), aliases=ALIASES)
        b, _ = bg.outputs("test", json.loads(json.dumps(r)), data=data(), aliases=ALIASES)
        self.assertEqual(a, b)
        for path, text in a.items():
            if path.endswith(".json"):
                json.loads(text)
        md = [t for p, t in a.items() if p.endswith(".md")][0]
        self.assertIn("| all |", md)
        self.assertNotRegex(md, r"20\d\d-\d\d-\d\d")

    def test_dumps_rows(self):
        obj = {"schema": 1, "rows": [{"key": "a"}, {"key": "b"}]}
        text = bg.dumps_rows(obj, "rows")
        self.assertEqual(json.loads(text), obj)
        self.assertEqual(len(text.splitlines()), 7)  # {, schema, "rows": [, 2 rows, ], }
        obj = {"rules": {"b": {"x": 1}, "a": {}}}
        self.assertEqual(json.loads(bg.dumps_rows(obj, "rules")), obj)


if __name__ == "__main__":
    unittest.main()
