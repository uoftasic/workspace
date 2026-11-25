"""The stored dialog state (kmp_dialog): when the PCell asks Magic's dialog
again, which dialog it models (New device and Create, or Edit device and
Apply), and what it stores. A fake Magic stands in here; the backend tests
and the parity harness use the real one."""

import json
import os
import unittest

from tests.unit._util import needs_klayout  # noqa: F401  (sets sys.path)
from klayout_magic_pcells import cache, dialog
from klayout_magic_pcells.backend import APPLY_KEY, dialog_request
from klayout_magic_pcells.config import SUPPORTED_PDKS, shipped_manifest
from klayout_magic_pcells.manifest import InvalidValue, Manifest

MAN = Manifest.load(shipped_manifest("sky130A"))
RES = MAN["sky130_fd_pr__res_high_po_0p69"]
MOS = MAN["sky130_fd_pr__nfet_01v8"]
MOS5 = MAN["sky130_fd_pr__nfet_g5v0d10v5"]
FIXED = MAN["sky130_fd_pr__npn_05v5_W1p00L1p00"]


class Res:
    def __init__(self, device, request, checked, opened, cell):
        self.sidecar = {"request": dict(request), "checked": checked, "opened": opened,
                        "opened_numbers": {k: "1028.0" for k, v in opened.items() if v == "1.028k"},
                        "opened_type": device, "opened_note": "", "magic_cell": cell,
                        "messages": ""}
        self.checked = checked
        self.magic_cell = cell
        self.messages = ""
        self.gds_path = ""


class FakeMagic:
    """The dialog clamps the resistor's w to 0.69 and writes val in SPICE
    text, as sky130's res_check does; Create's _check writes w as "0.690"
    and the reopened dialog shows the checked text; a MOSFET's l is clamped
    to 0.15 (0.50 for the 5 V FET). The cell name is the device and the
    checked w and l; Apply's name is the one the form gives."""

    def __init__(self):
        self.calls = []
        self.gets = []

    @staticmethod
    def _check(spec, form):
        out = dict(form)
        if spec.name == RES.name:
            out["w"], out["val"] = "0.690", "1.028k"
        elif spec.param("l") is not None and spec.family == "mos":
            lmin = 0.5 if spec.name == MOS5.name else 0.15
            if float(out["l"]) < lmin:
                out["l"] = "%.3f" % lmin
        return out

    @staticmethod
    def _name(spec, d):
        return "%s_%s" % (spec.name, "_".join(str(d.get(k)) for k in ("w", "l", "nx", "deltax")))

    def dialog(self, spec, form, edits, want_apply_name=False):
        self.calls.append((dict(form), list(edits)))
        out = dict(form)
        for n, t in edits:
            out[n] = t
        out = self._check(spec, out)
        rep = {"form": out, "numbers": {"val": "1028.0"} if out.get("val") == "1.028k" else {},
               "log": "", "source": "magic"}
        if want_apply_name:
            rep["apply_name"] = self._name(spec, self._check(spec, out))
        return rep

    def get(self, spec, request):
        self.gets.append(dict(request))
        form = {k: v for k, v in request.items() if k != APPLY_KEY}
        checked = self._check(spec, form)
        if request.get(APPLY_KEY) == "1":
            checked = self._check(spec, checked)
        opened = {n: checked[n] for n in form}
        if dialog.nocell(spec) and float(opened["nx"]) == 1:
            opened["deltax"] = "0.0"   # Magic's fixed_dialog, from the array pitch
        return Res(spec.name, request, checked, opened, self._name(spec, checked))


class NewDevice(unittest.TestCase):
    def test_the_defaults_show_what_create_shows(self):
        # Magic's Create checks the defaults once more and reopens the
        # dialog on the instance: res_high_po_0p69 opens with val 463.480
        # and then shows 1.028k. No edit, so no binding runs.
        fake = FakeMagic()
        c = dialog.correct(RES, RES.defaults_values(), "", fake)
        self.assertEqual(fake.calls, [])
        self.assertEqual(c.form, dialog.defaults_form(RES))
        self.assertEqual(c.request, dialog.defaults_form(RES))
        self.assertEqual(c.shows["val"], "1.028k")
        self.assertEqual(c.values["val"], 1028.0)
        self.assertEqual(c.flow, "new")
        self.assertIn("val", c.changed)
        # Those values are the stored dialog's: nothing is asked again.
        self.assertIsNone(dialog.correct(RES, c.values, c.dialog, fake))
        self.assertEqual(len(fake.gets), 1)

    def test_an_edit_is_typed_once_and_the_values_are_what_create_shows(self):
        fake = FakeMagic()
        vals = dict(RES.defaults_values(), w=1.0)
        c = dialog.correct(RES, vals, "", fake)
        self.assertEqual(len(fake.calls), 1)
        self.assertEqual(fake.calls[0][1], [("w", "1.0")])
        self.assertEqual(c.values["w"], 0.69)
        self.assertEqual(c.shows["w"], "0.690")           # Create's text
        self.assertEqual(c.values["val"], 1028.0)          # Magic's number for "1.028k"
        self.assertEqual(c.form["val"], "1.028k")          # what Magic gets again
        self.assertNotIn(APPLY_KEY, c.request)
        self.assertEqual(c.corrected, {"w": ("1.0", "0.690")})
        self.assertEqual(c.unshown, {"val": "1.028k"})
        # After a save a double may come back one ULP off: still the stored
        # state, and the same request.
        self.assertIsNone(dialog.correct(RES, c.values, c.dialog, fake))
        reopened = dict(c.values, w=0.6900000000000001)
        self.assertEqual(dialog.stored_request(RES, reopened, c.dialog), c.request)
        req, corr = dialog.request(RES, reopened, c.dialog, fake)
        self.assertIsNone(corr)
        self.assertEqual(req, c.request)
        self.assertEqual(len(fake.calls), 1)

    def test_edits_go_in_the_dialogs_row_order(self):
        # sky130's resistor dialog has val first, then l and w.
        order = dialog.dialog_order(RES)
        self.assertLess(order.index("val"), order.index("l"))
        self.assertLess(order.index("l"), order.index("w"))
        fake = FakeMagic()
        dialog.correct(RES, dict(RES.defaults_values(), w=0.69, l=0.0, val=50.0), "", fake)
        self.assertEqual([n for n, _t in fake.calls[0][1]], ["val", "l"])  # w is the default


class UnreadableText(unittest.TestCase):
    def test_a_value_magic_reads_no_number_from_keeps_the_field(self):
        # The PDKs' magic::spice2float maps the suffix n to "* 1.0 e-9",
        # which isn't a number: res_generic_l1 with l 0 shows 170.0n after
        # Create, and Magic gives no number for it. The field keeps the
        # typed 0.0, the state records that text for it, and a reopen with
        # 0.0 is the stored state.
        spec = MAN["sky130_fd_pr__res_generic_l1"]

        class Fake(FakeMagic):
            def get(self, spec_, request):
                r = FakeMagic.get(self, spec_, request)
                r.sidecar["opened"] = dict(r.sidecar["opened"], l="170.0n")
                r.sidecar["opened_numbers"] = {}
                return r
        fake = Fake()
        c = dialog.correct(spec, dict(spec.defaults_values(), l=0.0), "", fake)
        self.assertEqual(c.values["l"], 0.0)
        self.assertEqual(c.shows["l"], "170.0n")
        self.assertEqual(c.unshown, {"l": "170.0n"})
        self.assertIn("l", c.corrected)
        self.assertEqual(json.loads(c.dialog)["shown"], {"l": "0.0"})
        self.assertIsNone(dialog.correct(spec, c.values, c.dialog, fake))


class EditDevice(unittest.TestCase):
    def test_a_later_edit_starts_from_what_the_dialog_shows_and_is_an_apply(self):
        fake = FakeMagic()
        c = dialog.correct(MOS, dict(MOS.defaults_values(), w=2.0), "", fake)
        c2 = dialog.correct(MOS, dict(c.values, l=0.5), c.dialog, fake)
        start, edits = fake.calls[-1]
        self.assertEqual(start, c.shows)        # the Edit device dialog
        self.assertEqual(edits, [("l", "0.5")])
        self.assertEqual(c2.flow, "edit")
        self.assertEqual(c2.request[APPLY_KEY], "1")
        self.assertEqual(c2.values["l"], 0.5)
        st = dialog.decode(MOS, c2.dialog)
        self.assertTrue(st.apply)
        self.assertEqual(st.request(), c2.request)
        self.assertIsNone(dialog.correct(MOS, c2.values, c2.dialog, fake))

    def test_apply_keeps_an_instance_whose_name_does_not_change(self):
        # gencell_change: the form checked once has the instance's cell
        # name, so Apply leaves the instance as it was.
        fake = FakeMagic()
        c = dialog.correct(MOS, MOS.defaults_values(), "", fake)
        n = len(fake.gets)
        c2 = dialog.correct(MOS, dict(c.values, l=0.1), c.dialog, fake)
        self.assertTrue(c2.unchanged)
        self.assertEqual(c2.dialog, c.dialog)
        self.assertEqual(c2.request, c.request)
        self.assertEqual(c2.values, c.values)
        self.assertEqual(c2.corrected, {"l": ("0.1", "0.150")})
        self.assertEqual(len(fake.gets), n + 1)   # only the old variant, for its name

    def test_a_fixed_device_apply_is_a_create(self):
        # Magic's gencell_change draws a fixed device with the form checked
        # once, as Create does, and its dialog reopens with deltax from the
        # array's pitch: 0.0 for one copy.
        fake = FakeMagic()
        c = dialog.correct(FIXED, dict(FIXED.defaults_values(), deltax=1.0), "", fake)
        self.assertEqual(c.form["deltax"], "1.0")
        self.assertEqual(c.values["deltax"], 0.0)
        c2 = dialog.correct(FIXED, dict(c.values, nx=2), c.dialog, fake)
        self.assertEqual(c2.flow, "edit")
        self.assertNotIn(APPLY_KEY, c2.request)
        self.assertEqual(c2.form["deltax"], "0.0")
        self.assertFalse(dialog.decode(FIXED, c2.dialog).apply)
        d = json.loads(c2.dialog)
        d["apply"] = 1
        self.assertIsNone(dialog.decode(FIXED, json.dumps(d)))


class StoredState(unittest.TestCase):
    def test_a_refused_value_never_reaches_the_dialog(self):
        fake = FakeMagic()
        with self.assertRaises(InvalidValue):
            dialog.correct(MOS, dict(MOS.defaults_values(), viagb="[exec ls]"), "", fake)
        self.assertEqual(fake.calls, [])
        self.assertEqual(fake.gets, [])

    def test_a_damaged_form_is_not_used(self):
        fake = FakeMagic()
        c = dialog.correct(RES, dict(RES.defaults_values(), w=1.0), "", fake)
        d = json.loads(c.dialog)
        bad = []
        for change in ({"v": 1}, {"device": None}, {"apply": 2},
                       {"form": dict(d["form"], extra="1")},
                       {"form": {k: v for k, v in d["form"].items() if k != "w"}},
                       {"form": dict(d["form"], viagb="[exec ls]")},
                       {"shows": dict(d["shows"], w="0.69; exec ls")},
                       {"shows": {k: v for k, v in d["shows"].items() if k != "l"}},
                       {"shown": {"nope": "1"}}):
            bad.append(json.dumps(dict(d, **change)))
        bad += ["", "not json", "[]"]
        for text in bad:
            self.assertIsNone(dialog.decode(RES, text), text)
            self.assertIsNone(dialog.stored_request(RES, c.values, text), text)
        # A form from another device has other parameters.
        self.assertIsNone(dialog.decode(MOS, c.dialog))

    def test_another_devices_state_with_the_same_names_is_not_used(self):
        # Review 3, finding 5: nfet_01v8's state handed to nfet_g5v0d10v5,
        # whose dialog has the same widgets, was taken as corrected and
        # stored l 0.15 with no warning. The state names its device, so the
        # values are typed into the 5 V FET's own dialog, which shows l 0.50.
        fake = FakeMagic()
        c = dialog.correct(MOS, dict(MOS.defaults_values(), w=1.0), "", fake)
        self.assertEqual(sorted(dialog.widget_names(MOS)), sorted(dialog.widget_names(MOS5)))
        self.assertIsNone(dialog.decode(MOS5, c.dialog))
        self.assertIsNone(dialog.stored_request(MOS5, c.values, c.dialog))
        c5 = dialog.correct(MOS5, c.values, c.dialog, fake)
        self.assertEqual(c5.flow, "new")
        self.assertEqual(c5.values["l"], 0.5)
        self.assertIn("l", c5.corrected)

    def test_widgets_the_defaults_lack_go_with_the_form(self):
        # ihp-sg13g2's RF FET dialogs have topc and botc checkboxes that the
        # defaults lack: the dialog opens them empty and Create gets them.
        spec = Manifest.load(shipped_manifest("ihp-sg13g2"))["sg13_lv_rfnmos"]
        self.assertIsNone(spec.param("topc"))
        self.assertEqual(dialog.extra_widgets(spec), {"topc": "", "botc": ""})
        fake = FakeMagic()
        c = dialog.correct(spec, dict(spec.defaults_values(), w=2.0), "", fake)
        self.assertEqual((fake.calls[0][0]["topc"], fake.calls[0][0]["botc"]), ("", ""))
        self.assertEqual((c.form["topc"], c.form["botc"]), ("", ""))
        self.assertNotIn("topc", c.values)
        self.assertEqual(dialog.stored_request(spec, c.values, c.dialog), c.request)
        d = json.loads(c.dialog)
        del d["form"]["topc"]
        self.assertIsNone(dialog.decode(spec, json.dumps(d)))
        d["form"]["topc"] = "[exec ls]"
        self.assertIsNone(dialog.decode(spec, json.dumps(d)))

    def test_widgets_that_are_not_parameters_are_the_known_ones(self):
        # README: every widget of Magic's dialogs is a PCell parameter except
        # the device-type switch (gencell) and the IHP RF FETs' topc and
        # botc. A new widget that isn't a parameter shows up here.
        out = {}
        for pdk in SUPPORTED_PDKS:
            for spec in Manifest.load(shipped_manifest(pdk)).devices:
                if spec.kind == "box":
                    continue
                for kind, name in spec.raw.get("dialog_widgets") or []:
                    if kind in ("entry", "checkbox", "selectlist", "selectindex") \
                            and name != "gencell" and spec.param(name) is None:
                        out.setdefault((name, kind), []).append("%s %s" % (pdk, spec.name))
        rf = ["%s %s" % (p, d) for p in ("ihp-sg13g2", "ihp-sg13cmos5l")
              for d in ("sg13_lv_rfnmos", "sg13_lv_rfpmos", "sg13_hv_rfnmos", "sg13_hv_rfpmos")]
        self.assertEqual({k: sorted(v) for k, v in out.items()},
                         {("topc", "checkbox"): sorted(rf), ("botc", "checkbox"): sorted(rf)})

    def test_every_device_has_its_dialog_order(self):
        for pdk in SUPPORTED_PDKS:
            for spec in Manifest.load(shipped_manifest(pdk)).devices:
                if spec.kind == "box":
                    continue
                order = dialog.dialog_order(spec)
                self.assertEqual(sorted(order), sorted(p.name for p in spec.params), (pdk, spec.name))
                widgets = [n for _k, n in spec.raw["dialog_widgets"]]
                self.assertTrue(all(p.name in widgets for p in spec.params), (pdk, spec.name))
                for d in spec.raw["dialog_dependencies"]:
                    self.assertLessEqual(d["after"], len(widgets))


class DialogCacheKey(unittest.TestCase):
    """Review 3, finding 7: the dialog cache key didn't cover the plugin's
    model of the dialog, so a change to it would have been answered from
    entries the old model wrote."""

    def setUp(self):
        import tempfile
        self.d = tempfile.mkdtemp(prefix="kmp-dkey-")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.d, ignore_errors=True)

    def key(self, spec, form, edits, server_code=None, **kw):
        c = cache.GdsCache(self.d, {"format": cache.FORMAT, "pdk": "sky130A"},
                           server_code=server_code)
        return c.dialog_key(spec.name, dialog_request(spec, form, edits, **kw))

    def test_the_key_covers_the_request_and_the_server_code(self):
        form = dialog.defaults_form(RES)
        base = self.key(RES, form, [("w", "1.0")])
        self.assertEqual(base, self.key(RES, form, [("w", "1.0")]))
        self.assertNotEqual(base, self.key(RES, form, [("w", "1.1")]))
        self.assertNotEqual(base, self.key(RES, dict(form, l="2.0"), [("w", "1.0")]))
        self.assertNotEqual(base, self.key(RES, form, [("w", "1.0")], want_apply_name=True))
        self.assertNotEqual(base, self.key(RES, form, [("w", "1.0")], server_code="x" * 64))
        # The manifest's widget order and dependencies are in the request.
        spec = Manifest(dict(MAN.data, devices=[dict(RES.raw, dialog_dependencies=[])]))[RES.name]
        self.assertNotEqual(base, self.key(spec, form, [("w", "1.0")]))

    def test_the_server_code_digest_follows_the_tcl(self):
        d = cache.server_code_digest()
        self.assertEqual(len(d), 64)
        self.assertTrue(os.path.isfile(os.path.join(cache._TCL, "kmp_server.tcl")))
        self.assertEqual(d, cache.server_code_digest())


if __name__ == "__main__":
    unittest.main()
