"""gui.py without KLayout's GUI: the menu's guards and idempotence (on a
stand-in main window), the remembered choices, and what a Rerun runs."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from tests.unit._util import REPO, needs_klayout
from klayout_magic_pcells import gui
from klayout_magic_pcells.config import Config


class _Menu:
    """Just enough of pya.AbstractMenu: items by path, in order."""

    def __init__(self):
        self.items = []      # (path, title or action)

    def is_menu(self, path):
        return any(p == path for p, _ in self.items)

    def delete_item(self, path):
        self.items = [(p, a) for p, a in self.items if p != path and not p.startswith(path + ".")]

    def insert_menu(self, before, name, title):
        self.items.append((name, title))

    def insert_item(self, where, name, action):
        self.items.append((where.rsplit(".", 1)[0] + "." + name, action))

    def insert_separator(self, where, name):
        self.items.append((where.rsplit(".", 1)[0] + "." + name, "-"))


class _Action:
    def __init__(self):
        self.title = ""
        self.on_triggered = None


class _FakePya:
    """A pya with an Application whose main window has a menu (or none)."""

    def __init__(self, with_window=True):
        menu = _Menu()
        self.menu = menu

        class MainWindow:
            def menu(self):
                return menu

        window = MainWindow() if with_window else None

        class App:
            def main_window(self):
                return window

        class Application:
            @staticmethod
            def instance():
                return App()

        self.Application = Application
        self.Action = _Action


class Menu(unittest.TestCase):
    def setUp(self):
        self._pya = gui._pya

    def tearDown(self):
        gui._pya = self._pya
        gui._actions.clear()

    def test_no_main_window(self):
        """Plain python3 (no pya.Application) and klayout -b (main_window()
        is None): no menu."""
        self.assertFalse(gui.install_menu())
        fake = _FakePya(with_window=False)
        gui._pya = lambda: fake
        self.assertFalse(gui.install_menu(env={}))

    def test_kmp_menu_0(self):
        fake = _FakePya()
        gui._pya = lambda: fake
        self.assertFalse(gui.install_menu(env={"KMP_MENU": "0"}))
        self.assertEqual(fake.menu.items, [])

    def test_twice_leaves_one_menu(self):
        fake = _FakePya()
        gui._pya = lambda: fake
        self.assertTrue(gui.install_menu(env={"KMP_MENU": "1"}))
        first = list(fake.menu.items)
        self.assertTrue(gui.install_menu(env={"KMP_MENU": "1"}))
        self.assertEqual([p for p, _ in fake.menu.items], [p for p, _ in first])
        self.assertEqual(sum(1 for p, _ in fake.menu.items if p == gui.MENU), 1)
        titles = [a.title for p, a in fake.menu.items if isinstance(a, _Action)]
        self.assertEqual(titles, ["Run Magic DRC...", "Check the visible area with Magic DRC",
                                  "Extract with Magic...", "LVS with netgen...", "Check generated layers",
                                  "Check ports", "Rule differences", "Settings..."])
        self.assertTrue(all(callable(a.on_triggered) for p, a in fake.menu.items if isinstance(a, _Action)))
        self.assertEqual(len(gui._actions), 8)

    def test_a_broken_config_keeps_the_menu(self):
        fake = _FakePya()
        gui._pya = lambda: fake
        self.assertTrue(gui.install_menu(env={"HOME": "/nonexistent", "KMP_DRC_MODE": "per-cell"}))


class NoQtAtImport(unittest.TestCase):
    def test_import_loads_neither_pya_nor_qt(self):
        code = ("import sys; sys.path.insert(0, %r); import klayout_magic_pcells.gui; "
                "print([m for m in sys.modules if m == 'pya' or 'qt' in m.lower() or m == 'klayout.lay'])"
                % os.path.join(REPO, "python"))
        p = subprocess.run([sys.executable, "-c", code], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           universal_newlines=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout.strip(), "[]")

    def test_no_qt_without_a_window(self):
        self.assertFalse(gui.has_qt())
        self.assertIsNone(gui.main_window())


class StateFile(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="kmp-gui-")
        self.path = os.path.join(self.dir, "sub", "state.json")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_round_trip(self):
        st = gui.State(self.path)
        self.assertIsNone(st.lvs("/a/inv.gds", "inv"))
        self.assertEqual(st.drc(), {})
        st.set_lvs("/a/inv.gds", "inv", "/a/inv.spice", "inv")
        st.set_lvs("/a/inv.gds", "buf", "/a/lib.spice", "buf_1")
        st.set_lvs("", "TOP", "/b/top.cdl", "top")
        st.set_drc("drc(fast)", "flat", "visible")
        again = gui.State(self.path)
        self.assertEqual(again.lvs("/a/inv.gds", "inv"), {"schematic": "/a/inv.spice", "subckt": "inv"})
        self.assertEqual(again.lvs("/a/inv.gds", "buf"), {"schematic": "/a/lib.spice", "subckt": "buf_1"})
        self.assertEqual(again.lvs(None, "TOP"), {"schematic": "/b/top.cdl", "subckt": "top"})
        self.assertIsNone(again.lvs("/a/other.gds", "inv"))
        self.assertEqual(again.drc(), {"style": "drc(fast)", "mode": "flat", "area": "visible"})
        with open(self.path) as f:
            self.assertEqual(json.load(f)["schema"], gui.STATE_SCHEMA)
        self.assertEqual([n for n in os.listdir(os.path.dirname(self.path)) if n != "state.json"], [])

    def test_unreadable_file_is_empty(self):
        os.makedirs(os.path.dirname(self.path))
        for text in ("{not json", "[1, 2]", '{"schema": 99, "lvs": {"": {"a": {}}}}'):
            with open(self.path, "w") as f:
                f.write(text)
            st = gui.State(self.path)
            self.assertIsNone(st.lvs("", "a"))
            st.set_drc("drc(full)", "hierarchical", "cell")
            self.assertEqual(gui.State(self.path).drc()["mode"], "hierarchical")

    def test_default_path_follows_config(self):
        self.assertEqual(gui.state_path({"XDG_CONFIG_HOME": "/x"}), "/x/klayout-magic-pcells/state.json")
        self.assertEqual(gui.state_path({"HOME": "/h"}), "/h/.config/klayout-magic-pcells/state.json")


def _params(generator):
    """The parameters of a generator text, as the browser hands them to
    Recipe.make (the values unquoted)."""
    import re
    body = generator.split(": ", 1)[1]
    return {k: v for k, v in re.findall(r"(\w+)='((?:[^'\\]|\\.)*)'", body)}


class Rerun(unittest.TestCase):
    """What the features write into the generator comes back as the same
    options, so the re-run's RDB carries the same generator."""

    @needs_klayout
    def test_drc(self):
        from klayout_magic_pcells import markers
        gen = markers.recipe_generator({"cmd": "drc", "file": "/w/inv.gds", "cell": "inv,buf",
                                        "style": "drc(full)", "mode": "hierarchical", "pdk": "sky130A",
                                        "box": "0,0,1.5,2"})
        cmd, cells, opts, pdk = gui.options_from_params(dict(_params(gen), rdb_index=3))
        self.assertEqual((cmd, cells, pdk), ("drc", ["inv", "buf"], "sky130A"))
        self.assertEqual(opts, {"style": "drc(full)", "mode": "hierarchical", "box": "0,0,1.5,2",
                                "file": "/w/inv.gds"})

    def test_lvs_and_extract(self):
        cmd, cells, opts, pdk = gui.options_from_params(
            {"cmd": "lvs", "file": "/w/inv.gds", "cell": "inv", "pdk": "sky130A", "schematic": "/w/inv.spice",
             "schematic_cell": "inv", "ports_from_labels": "True"})
        self.assertEqual((cmd, cells, pdk), ("lvs", ["inv"], "sky130A"))
        self.assertEqual(opts, {"cmd": "lvs", "file": "/w/inv.gds", "flatglob": False, "ports_from_labels": True,
                                "schematic": "/w/inv.spice", "schematic_cell": "inv"})
        cmd, cells, opts, pdk = gui.options_from_params({"cmd": "extract", "file": "", "cell": "inv",
                                                         "pdk": "gf180mcuD", "caps": "True"})
        self.assertEqual(opts, {"cmd": "extract", "file": "", "flatglob": False, "ports_from_labels": False,
                                "caps": True})

    def test_layers_and_ports(self):
        self.assertEqual(gui.options_from_params({"cmd": "layers", "file": "/w/a.gds", "cell": "a"}),
                         ("layers", ["a"], {"file": "/w/a.gds"}, None))
        self.assertEqual(gui.options_from_params({"cmd": "ports", "file": "/w/a.gds", "cell": "a", "magic": "0"}),
                         ("ports", ["a"], {"file": "/w/a.gds", "magic": False}, None))
        self.assertTrue(gui.options_from_params({"cmd": "ports", "cell": "a", "magic": "1"})[2]["magic"])

    def test_unknown(self):
        with self.assertRaises(ValueError):
            gui.options_from_params({"cmd": "check", "cell": "a"})
        with self.assertRaises(ValueError):
            gui.options_from_params({"cmd": "drc"})


class Pages(unittest.TestCase):
    def test_gap_tables_are_found_beside_the_package(self):
        for pdk in ("sky130A", "gf180mcuD", "ihp-sg13g2", "ihp-sg13cmos5l"):
            path = gui.gaps_page(pdk)
            self.assertEqual(path, os.path.join(REPO, "docs", "gaps", "%s.md" % pdk))
        self.assertIsNone(gui.gaps_page("sky130A", root=tempfile.gettempdir() + "/kmp-no-such-root"))

    def test_settings_rows_say_where(self):
        cfg = Config.load(env={"HOME": "/h", "KMP_PDKS": "sky130A", "KMP_DRC_STYLE": "drc(fast)"},
                          config_path="/nonexistent.ini")
        rows = {r[0]: r for r in gui.settings_rows(cfg)}
        self.assertEqual(rows["drc_style"][1:], ("KMP_DRC_STYLE, or drc_style in [kmp]", "drc(fast)",
                                                 "env KMP_DRC_STYLE"))
        self.assertEqual(rows["netgen_setup"][1], "KMP_NETGEN_SETUP_SKY130A, or netgen_setup in [kmp:sky130A]")
        self.assertEqual(rows["cache_enabled"][1], "KMP_CACHE, or cache in [kmp]")
        self.assertIn("menu", rows)

    def test_command_text(self):
        self.assertEqual(gui.command_text("ports", "/w/a.gds", "a", "sky130A", {"magic": True}),
                         "python3 -m klayout_magic_pcells ports /w/a.gds --cell a --pdk sky130A --magic")



class _Task:
    def __init__(self, stage=None):
        self.stage = stage


class StageText(unittest.TestCase):
    def test_the_flattened_check_names_itself(self):
        task = _Task()
        run = gui.Run("Magic DRC", task, None, lambda r: None)
        run.t0 = __import__("time").monotonic()
        seen = []
        for st in (None, ("starting inv", 0), ("reading", 0), ("checking inv", 1),
                   ("starting flattened inv", 0), ("reading", 0), ("checking inv", 1),
                   ("cached flattened inv", 0)):
            task.stage = st
            seen.append(run.stage_text().rsplit(" (", 1)[0])
        self.assertEqual(seen, ["Magic DRC: starting Magic", "Magic DRC: starting inv", "Magic DRC: reading",
                                "Magic DRC: checking inv 1", "Magic DRC: starting flattened inv",
                                "Magic DRC: flattened inv: reading", "Magic DRC: flattened inv: checking inv 1",
                                "Magic DRC: cached flattened inv"])


class PdkQuestion(unittest.TestCase):
    def test_the_dialog_says_why(self):
        from klayout_magic_pcells.pdkchoice import PdkChoiceError
        e = PdkChoiceError("x", ["sky130A", "ihp-sg13g2"], "sky130A", "a guess from the layers: ...",
                           "the layout's technology is sg13g2 (ihp-sg13g2), but 0% of its shapes are on "
                           "ihp-sg13g2's layers and 97% on sky130A's")
        self.assertTrue(gui.pdk_question(e).startswith("The layout's technology is sg13g2 (ihp-sg13g2), but"))
        e = PdkChoiceError("x", ["sky130A", "ihp-sg13g2"], "sky130A", "a guess from the PDK variable")
        self.assertEqual(gui.pdk_question(e), "The layout names no technology and no PCell library of the plugin")


class _Out:
    def __init__(self, files, summary="s", status=0, **kw):
        self.files = files
        self.summary = summary
        self.status = status
        self.rdb = None
        self.__dict__.update(kw)


class _Run:
    def __init__(self, out, title="Magic DRC", cancelled=False, error=None):
        self.outcome = out
        self.title = title
        self.cancelled = cancelled
        self.error = error


class Outcome(unittest.TestCase):
    """show_outcome without Qt: the message goes to the log."""

    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="kmp-gui-")
        self.cfg = Config.load(env={"HOME": self.d, "KMP_CACHE_DIR": os.path.join(self.d, "cache"),
                                    "KMP_PDKS": "sky130A"}, config_path="/nonexistent.ini").for_pdk("sky130A")
        self.msgs = []
        old = gui.message
        gui.message = lambda kind, title, text, details=None, on_close=None: self.msgs.append(
            (kind, title, text if not details else "%s\n\n%s" % (text, details)))
        self.addCleanup(setattr, gui, "message", old)
        os.environ.pop("KMP_JOB_KEEP", None)

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def ctx(self, file=""):
        import types
        return types.SimpleNamespace(view=None, cv_index=0, file=file, pdk="sky130A",
                                     cell=types.SimpleNamespace(name="inv"))

    def test_release_once_shown(self):
        from klayout_magic_pcells import jobs
        for cancelled in (False, True):
            a = jobs.tmp_job_dir(self.cfg, "drc")
            flat = jobs.tmp_job_dir(self.cfg, "drc")
            out = _Out({"job_dir": a, "jobs": [a], "flat_checks": [flat]})
            gui.show_outcome(self.ctx(), _Run(out, cancelled=cancelled))
            self.assertFalse(os.path.exists(a), "the outcome's tmp-* job directory stays")
            self.assertFalse(os.path.exists(flat), "the flat check's tmp-* directory stays")
        # A key's directory stays.
        key = jobs.job_dir_for(self.cfg, "drc", "k" * 64)
        os.makedirs(key)
        gui.show_outcome(self.ctx(), _Run(_Out({"job_dir": key})))
        self.assertTrue(os.path.isdir(key))

    def test_drc_message_shows_the_classes(self):
        from klayout_magic_pcells import drcjob
        why = "Metal1 width < 0.14um (met1.1)"
        out = _Out({}, summary="Magic DRC (drc(full), hierarchical) of inv_pcell on sky130A: no errors. x",
                   classes={"inv_pcell": {drcjob.TOP: 0, drcjob.IN_TOP: 2, drcjob.FLAT_ONLY: 1, drcjob.ALONE: 6}},
                   alone=[("nfet__kmp_1", why, (0, 0, 1, 1))] * 4 + [("pfet__kmp_2", why, (0, 0, 1, 1))] * 2)
        gui.show_outcome(self.ctx(), _Run(out))
        text = self.msgs[-1][2]
        self.assertIn("of the 9 boxes the subcells' own checks list, 2 are in the top cell's check (errors), "
                      "1 only in the flattened layout's check (errors), 6 only when", text)
        self.assertIn("4 boxes only when nfet__kmp_1 is checked on its own (information, not counted as "
                      "errors): met1.1 4.", text)
        self.assertIn("2 boxes only when pfet__kmp_2 is checked on its own", text)

    @needs_klayout
    def test_extract_never_replaces_a_file_the_plugin_did_not_write(self):
        from klayout_magic_pcells import lvsjob
        work = os.path.join(self.d, "work")
        os.makedirs(work)
        layout = os.path.join(work, "inv.gds")
        job = os.path.join(self.d, "job")
        os.makedirs(job)
        netlist = os.path.join(job, "netlist.spice")
        with open(netlist, "w") as f:
            f.write(".subckt inv A Y\n.ends\n")
        target = os.path.join(work, "inv.magic.spice")
        after = gui.extract_after(self.ctx(layout), False)
        for _ in range(2):
            out = _Out({"netlist": netlist, "job_dir": job}, summary="extract: Magic extracted inv "
                       "(netlist only, sky130A) into %s." % netlist)
            self.assertEqual(after(out), "Netlist: %s" % target)
            self.assertIn(" into %s." % target, out.summary)
            self.assertTrue(lvsjob.written_by_plugin(target))
        mine = "* my own netlist\n.subckt inv A Y\n.ends\n"
        with open(target, "w") as f:
            f.write(mine)
        for _ in range(2):
            out = _Out({"netlist": netlist, "job_dir": job}, summary="extract: x into %s." % netlist)
            note = after(out)
            self.assertTrue(note.startswith("Not written: %s exists and klayout_magic_pcells did not write it"
                                            % target), note)
            # The summary names no file then: the job directory's copy goes.
            self.assertEqual(out.summary, "extract: x.")
            with open(target) as f:
                self.assertEqual(f.read(), mine)
        self.assertEqual(gui._free_name(target), os.path.join(work, "inv.magic-2.spice"))




class ResultMessages(unittest.TestCase):
    """The result message's plain first line, the
    browser brought in front again, and netgen's report shown at its end."""

    def setUp(self):
        self._pya, self._show_text, self._message = gui._pya, gui.show_text, gui.message

    def tearDown(self):
        gui._pya, gui.show_text, gui.message = self._pya, self._show_text, self._message

    def test_headline_first_then_the_summary(self):
        import types
        out = types.SimpleNamespace(status=1, headline="2 DRC error markers in drc_02, rule li.5.",
                                    summary="Magic DRC (drc(full), hierarchical) of drc_02 on sky130A: 2 error boxes.",
                                    alone=[], classes={})
        self.assertEqual(gui.message_texts(out), (out.headline, out.summary))
        self.assertEqual(gui.message_texts(out, "Netlist: /x/drc_02.magic.spice"),
                         (out.headline, out.summary + "\n\nNetlist: /x/drc_02.magic.spice"))
        failed = types.SimpleNamespace(status=2, summary="layers: cancelled")
        self.assertEqual(gui.message_texts(failed), ("layers: cancelled", ""))

    def test_the_message_brings_the_browser_back(self):
        import types
        said = []
        gui.message = lambda *a, **k: said.append((a, k))
        ctx = types.SimpleNamespace(view=None)
        out = types.SimpleNamespace(status=0, headline="No port findings in inv.", summary="ports on sky130A",
                                    files={})
        run = types.SimpleNamespace(title="Port check", error=None, cancelled=False, outcome=out)
        gui._show_outcome(ctx, run, None, None)
        (args, kw), = said
        self.assertEqual(args, ("info", "Port check", "No port findings in inv.", "ports on sky130A"))
        self.assertIs(kw["on_close"], gui.raise_browser)

    def test_raise_browser(self):
        raised = []

        class W:
            def __init__(self, name, visible):
                self.objectName, self.visible = name, visible

            def isVisible(self):
                return self.visible

            def raise_(self):
                raised.append(("raise", self.objectName, self.visible))

            def activateWindow(self):
                raised.append(("activate", self.objectName, self.visible))

        class QApplication:
            @staticmethod
            def topLevelWidgets():
                return [W("MarkerBrowserDialog", True), W("MarkerBrowserDialog", False), W("kmp_message", True)]

        import types
        gui._pya = lambda: types.SimpleNamespace(QApplication=QApplication)
        gui.raise_browser()
        self.assertEqual(raised, [("raise", "MarkerBrowserDialog", True), ("activate", "MarkerBrowserDialog", True)])

    def test_netgens_report_opens_at_its_end_and_no_cache_path(self):
        import types
        shown = []
        gui.show_text = lambda *a, **k: shown.append((a, k))
        d = tempfile.mkdtemp(prefix="kmp-gui-")
        try:
            report = os.path.join(d, "lvs.out")
            with open(report, "w") as f:
                f.write("...\nFinal result: Circuits match uniquely.\n")
            self.assertIsNone(gui.lvs_after(types.SimpleNamespace(files={"report": report})))
            (args, kw), = shown
            self.assertTrue(kw.get("at_end"))
            self.assertIn("Final result", args[1])
        finally:
            shutil.rmtree(d, ignore_errors=True)


class Windows(unittest.TestCase):
    def test_windows_fit_the_screen(self):
        """Rule differences asked for 1100 x 760 on a 1280 x 800
        screen whose panel leaves 1280 x 769."""
        self.assertEqual(gui.fit_size((1100, 760), (1280, 769)), (1100, 699))
        self.assertEqual(gui.fit_size((1100, 760), (1920, 1050)), (1100, 760))
        self.assertEqual(gui.fit_size((1100, 760), None), (1100, 760))

    def test_extract_title_leaves_the_cell_to_the_dialog(self):
        """The window manager cut "Extract drc_02 with Magic (" at
        the dialog's width."""
        self.assertEqual(gui.extract_title("sky130A"), "Extract with Magic (sky130A)")

    def test_a_netlist_of_the_plugin_is_no_schematic(self):
        """The LVS dialog asks before it takes a netlist that
        Extract wrote."""
        d = tempfile.mkdtemp(prefix="kmp-gui-")
        try:
            mine = os.path.join(d, "drc_02.magic.spice")
            with open(mine, "w") as f:
                f.write("* Written by klayout_magic_pcells 0.6.2: Magic's netlist of drc_02\n.subckt drc_02 A\n.ends\n")
            sch = os.path.join(d, "my_inv_sch.spice")
            with open(sch, "w") as f:
                f.write(".subckt my_inv A Y VPWR VGND\n.ends\n")
            self.assertTrue(gui.plugin_netlist(mine))
            self.assertFalse(gui.plugin_netlist(sch))
            self.assertFalse(gui.plugin_netlist(""))
        finally:
            shutil.rmtree(d, ignore_errors=True)



if __name__ == "__main__":
    unittest.main()
