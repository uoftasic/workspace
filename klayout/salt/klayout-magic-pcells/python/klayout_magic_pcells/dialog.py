"""The values Magic's parameter dialog shows, kept with each PCell instance.

Magic's dialog (toolkit.tcl) corrects what a user types: on Return in an
entry, a click on a checkbox or a pick in a selectlist, it runs the device's
``_check`` and the device's dependency callbacks (``res_recalc`` turns a
typed resistance into a length) and writes the corrected values back into
the form. Create (``gencell_create``) checks the form once more, draws, and
reopens the dialog as "Edit device" on the new instance, which shows the
instance's values. A later edit is typed into that dialog, and its Apply
(``gencell_change``) checks the form once, compares Magic's name for the
result with the instance's cell, and only when they differ makes a new cell
with ``gencell_create`` (which checks it again).

A device PCell follows that: the first edit of an instance is "New device:
type, Return, Create"; every later one is "Edit device: type, Return,
Apply" on the instance the earlier one made. The PCell stores what the
dialog shows after Create or Apply and draws what Create or Apply made.
Magic computes every correction, every check and every name: the server's
``dialog`` op runs the widgets' bindings on a form held as data, its
``generate`` op runs Create or Apply and reports what the reopened dialog
shows (see kmp_server.tcl). Nothing here corrects a value itself.

The state goes with the instance as the hidden PCell parameter
``kmp_dialog``, JSON text::

    {"v": 2, "device": "sky130_fd_pr__res_high_po_0p69",
     "form": {"w": "0.69", "val": "1.028k", ...}, "apply": 0,
     "shows": {"w": "0.690", "val": "1.028k", ...}, "shown": {"val": "1028.0"}}

``form`` is the dialog's form when Create or Apply was pressed, which is
what the PCell sends Magic (with ``"kmp_apply": "1"`` added when ``apply``
is 1). ``shows`` is the text of every widget of the dialog that reopens on
the instance afterwards: the visible PCell values show it, and a later edit
starts from it. Both hold the widgets whose name the device's defaults lack,
which therefore aren't PCell parameters: the IHP RF FETs' dialogs have "top
gate contact" and "bottom gate contact" checkboxes (``topc``, ``botc``) that
their defaults don't have, so Magic's dialog opens them empty and hands
Create ``topc ""`` and ``botc ""``. ``shown`` holds, for a value of
``shows`` that the PCell field can't hold as typed text (Magic's SPICE
notation, ``1.028k``), the canonical text of what the field shows instead.

When the PCell's values are the ones ``shows`` shows, nothing is typed
again, so reopening a file or refreshing the library never runs ``_check``
on Magic's own output a second time (it isn't idempotent: a resistor's
``val`` can move). When they differ, the fields that differ are the edits,
typed one after another in the dialog's row order into ``shows`` (or, with
no stored state, into the defaults the "New device" dialog opens with).
"""

import json
import re

from .backend import APPLY_KEY
from .manifest import InvalidValue

DIALOG_PARAM = "kmp_dialog"
FORMAT = 2

# What a number field's form value may look like before it goes back to
# Magic: a decimal number, possibly in Magic's SPICE notation (1.028k,
# 202.5m, 1.218u), or inf/nan. The server also refuses [, ], $ and
# backslashes; this keeps anything that isn't a number away from Magic's
# unbraced expr.
_FORM_NUMBER_RE = re.compile(r"[ \t]*[+-]?(([0-9]+\.?[0-9]*|\.[0-9]+)([eE][+-]?[0-9]+)?[A-Za-z]*"
                             r"|inf|nan)[ \t]*")


def check_form_value(p, text):
    """Raise InvalidValue if a form value must not be sent to Magic."""
    if not isinstance(text, str):
        raise InvalidValue(p.name, text, "is not text")
    if p.type in ("float", "int", "bool01"):
        if not _FORM_NUMBER_RE.fullmatch(text):
            raise InvalidValue(p.name, text, "is not a number, so the stored dialog form was not "
                               "sent to Magic")
    else:
        p.check(text)


def extra_widgets(spec):
    """{name: the value Magic's dialog opens it with} for the widgets of the
    device's dialog that aren't PCell parameters and that the dialog's form
    holds (gencell_getparams reads entries, checkboxes and selectlists): the
    ones whose name the defaults lack. The device-type switch "gencell" is
    left out; Create removes it. A widget that isn't in the defaults opens
    empty (magic::add_entry and add_checkbox set ""); none of them is a
    selectlist in the shipped manifests, whose opening text the manifest
    doesn't record."""
    defaults = dict(spec.defaults)
    out = {}
    for kind, name in spec.raw.get("dialog_widgets") or []:
        if kind not in ("entry", "checkbox", "selectlist", "selectindex") or name == "gencell":
            continue
        if spec.param(name) is not None:
            continue
        out[name] = defaults.get(name, "")
    return out


def _check_extra(name, text):
    if not isinstance(text, str) or not (text == "" or _FORM_NUMBER_RE.fullmatch(text)):
        raise InvalidValue(name, text, "is not empty or a number, so the stored dialog form was "
                           "not sent to Magic")


def nocell(spec):
    """A fixed device: Magic places the vendor cell, and Apply draws the
    form checked once, as Create does."""
    return bool(spec.raw.get("nocell"))


def widget_names(spec):
    return [p.name for p in spec.params] + list(extra_widgets(spec))


def check_widgets(spec, d, what):
    """Raise InvalidValue unless ``d`` holds every widget of the device's
    dialog, and only those, each with a value that may be sent to Magic."""
    names = widget_names(spec)
    if not isinstance(d, dict) or sorted(d) != sorted(names):
        raise InvalidValue(spec.params[0].name if spec.params else "?", None,
                           "%s doesn't hold the widgets of %s's dialog" % (what, spec.name))
    extra = extra_widgets(spec)
    for p in spec.params:
        check_form_value(p, d[p.name])
    for n in extra:
        _check_extra(n, d[n])


class State:
    """A decoded kmp_dialog."""

    def __init__(self, form, apply, shows, shown):
        self.form = form
        self.apply = apply
        self.shows = shows
        self.shown = shown

    def request(self):
        """What the PCell sends Magic for this instance."""
        r = dict(self.form)
        if self.apply:
            r[APPLY_KEY] = "1"
        return r


def encode(device, form, apply, shows, shown):
    return json.dumps({"v": FORMAT, "device": device, "form": form, "apply": 1 if apply else 0,
                       "shows": shows, "shown": shown},
                      sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def decode(spec, text):
    """The State of a kmp_dialog value, or None when it is empty, not this
    format, made for another device (whose parameters may have the same
    names), or holds a value that must not reach Magic."""
    if not text:
        return None
    try:
        d = json.loads(text)
    except ValueError:
        return None
    if not isinstance(d, dict) or d.get("v") != FORMAT or d.get("device") != spec.name:
        return None
    form, shows, shown, apply = d.get("form"), d.get("shows"), d.get("shown"), d.get("apply")
    if apply not in (0, 1) or (apply and nocell(spec)) or not isinstance(shown, dict):
        return None
    names = [p.name for p in spec.params]
    if not all(isinstance(v, str) for v in shown.values()) or not set(shown) <= set(names):
        return None
    try:
        check_widgets(spec, form, "the stored form")
        check_widgets(spec, shows, "the stored dialog")
    except InvalidValue:
        return None
    order = widget_names(spec)
    return State({n: form[n] for n in order}, bool(apply), {n: shows[n] for n in order}, dict(shown))


def field_text(p, form_text, shown):
    """The canonical text of what the field of ``p`` shows for a value."""
    if p.name in shown:
        return shown[p.name]
    return p.format(p.parse(form_text))


def field_texts(spec, st):
    return {p.name: field_text(p, st.shows[p.name], st.shown) for p in spec.params}


def values_text(spec, values):
    """The canonical text of every PCell value (the text the PCell sends
    for it when it is typed)."""
    out = {}
    for p in spec.params:
        v = values.get(p.name)
        out[p.name] = p.default if v is None else p.format(v)
    return out


def defaults_form(spec):
    """The form of the "New device" dialog: every PCell parameter's default
    text and the extra widgets' opening values."""
    out = {p.name: p.default for p in spec.params}
    out.update(extra_widgets(spec))
    return out


def dialog_order(spec):
    """The editable parameters in the order of the dialog's rows."""
    names = [n for _k, n in spec.raw.get("dialog_widgets") or []]
    known = [n for n in names if spec.param(n) is not None]
    return known + [p.name for p in spec.params if p.name not in known]


def stored_request(spec, values, dialog_text):
    """The request the instance's stored state gives when the values are
    the ones its dialog shows, else None."""
    st = decode(spec, dialog_text)
    if st is None:
        return None
    try:
        expect = field_texts(spec, st)
    except (ValueError, TypeError):
        return None
    return st.request() if values_text(spec, values) == expect else None


class Plan:
    """What the dialog has to do for a set of PCell values: the form it
    starts from, what each field showed there, the edits, and whether this
    is the instance's first edit ("new": the New device dialog, then
    Create) or a later one ("edit": the Edit device dialog, then Apply)."""

    def __init__(self, start, before, edits, flow, state):
        self.start = start
        self.before = before
        self.edits = edits
        self.flow = flow
        self.state = state


def plan(spec, values, dialog_text):
    """None when the values are the ones the stored dialog shows; else a
    Plan. Raises InvalidValue for an edit that must not be sent to
    Magic."""
    typed = values_text(spec, values)
    st = decode(spec, dialog_text)
    before = None
    if st is not None:
        try:
            before = field_texts(spec, st)
        except (ValueError, TypeError):
            st = None
    if st is not None and typed == before:
        return None
    if st is None:
        start, flow = defaults_form(spec), "new"
        before = {p.name: p.format(p.default_value()) for p in spec.params}
    else:
        start, flow = dict(st.shows), "edit"
    edits = []
    for n in dialog_order(spec):
        if typed[n] != before[n]:
            spec.param(n).check(typed[n])
            edits.append((n, typed[n]))
    return Plan(start, before, edits, flow, st)


class Correction:
    """The dialog's result for one set of PCell values.

    ``values``: the PCell values the dialog shows afterwards; ``dialog``:
    the kmp_dialog text; ``form``: the dialog's form when Create or Apply
    was pressed; ``request``: what the PCell sends Magic; ``shows``: what
    the dialog shows afterwards, as Magic's text; ``edits``: [(name, typed
    text)]; ``corrected``: {name: (typed, shown)} for edits that show
    another value; ``changed``: {name: (before, shown)} for other fields
    that changed; ``unshown``: {name: text} for values the field shows only
    as Magic's number for them, or not at all; ``log``: Magic's messages;
    ``flow``: "new" or "edit"; ``unchanged``: Apply left the instance as it
    was (``note`` says why); ``result``: the generated variant.
    """

    def __init__(self, **kw):
        self.values = kw["values"]
        self.dialog = kw["dialog"]
        self.form = kw["form"]
        self.request = kw["request"]
        self.shows = kw["shows"]
        self.edits = kw["edits"]
        self.corrected = kw["corrected"]
        self.changed = kw["changed"]
        self.unshown = kw["unshown"]
        self.log = kw["log"]
        self.source = kw["source"]
        self.flow = kw["flow"]
        self.unchanged = kw.get("unchanged", False)
        self.note = kw.get("note", "")
        self.result = kw.get("result")


def _visible(spec, shows, numbers, previous):
    """(PCell values, shown, unshown) for what the dialog shows."""
    new, shown, unshown = {}, {}, {}
    for p in spec.params:
        t = shows[p.name]
        try:
            v = p.parse(t)
        except (ValueError, TypeError):
            v = None
            n = numbers.get(p.name)
            if n is not None:
                try:
                    if p.type == "float":
                        # As KLayout saves it (15 digits), so a reopened
                        # file holds the same double.
                        v = float("%.15g" % float(n))
                    elif p.type == "int" and float(n) == int(float(n)):
                        v = int(float(n))
                    elif p.type == "bool01":
                        v = bool(int(float(n)))
                except (ValueError, TypeError, OverflowError):
                    v = None
            if v is None:
                # Nothing the field can show: it keeps what it had.
                v = previous.get(p.name)
                if v is None:
                    v = p.default_value()
            shown[p.name] = p.format(v)
            unshown[p.name] = t
        new[p.name] = v
    return new, shown, unshown


def shows_of(spec, form, res):
    """(shows, numbers, note) for the variant ``res`` made from ``form``:
    what the dialog shows when it reopens on the instance, as the server
    computed it; when Magic's dialog can't reopen there (the server says
    why), what Create's gencell_setparams wrote into the dialog it had: the
    checked value of every widget."""
    opened = res.sidecar.get("opened")
    note = res.sidecar.get("opened_note") or ""
    names = widget_names(spec)
    if isinstance(opened, dict) and not note and sorted(opened) == sorted(names) \
            and res.sidecar.get("opened_type") == spec.name:
        return ({n: opened[n] for n in names}, dict(res.sidecar.get("opened_numbers") or {}), "")
    checked = res.checked or {}
    if not note:
        note = "the dialog reopens as %r with %s" % (res.sidecar.get("opened_type"),
                                                     sorted(opened or {}))
    return ({n: checked.get(n, form[n]) for n in names},
            dict(res.sidecar.get("checked_numbers") or {}), note)


def correct(spec, values, dialog_text, generator):
    """The dialog's result for ``values``, or None when they are the ones the
    stored dialog shows. Asks Magic through ``generator`` (its dialog() for
    the bindings, its get() for Create or Apply). Raises InvalidValue or
    BackendError."""
    pl = plan(spec, values, dialog_text)
    if pl is None:
        return None
    apply_check = pl.flow == "edit" and not nocell(spec)
    apply_name = ""
    if pl.edits:
        rep = generator.dialog(spec, pl.start, pl.edits, want_apply_name=True) if apply_check \
            else generator.dialog(spec, pl.start, pl.edits)
        form, log, source = rep["form"], rep.get("log", ""), rep.get("source", "magic")
        apply_name = rep.get("apply_name", "")
    else:
        form, log, source = dict(pl.start), "", "none"
    check_widgets(spec, form, "Magic's dialog form")
    form = {n: form[n] for n in widget_names(spec)}
    typed = values_text(spec, values)
    edited = dict(pl.edits)

    def summary(after, unshown=()):
        # An edit whose field can only show Magic's text as a number, or not
        # at all, was changed by the dialog even when the number reads the
        # same (res_generic_l1 with l 0 shows "170.0n").
        corrected = {n: (typed[n], after[n]) for n in edited if after[n] != typed[n] or n in unshown}
        changed = {n: (pl.before[n], after[n]) for n in after
                   if n not in edited and after[n] != pl.before[n]}
        return corrected, changed

    if apply_check:
        old_req = pl.state.request()
        old = generator.get(spec, old_req)
        if not apply_name:
            raise InvalidValue(pl.edits[0][0], pl.edits[0][1],
                               "got no cell name for Apply from Magic's dialog")
        if old.magic_cell and apply_name == old.magic_cell:
            # Magic's Apply compares the names and, when they are equal,
            # leaves the instance (and its cell) as it was.
            after = field_texts(spec, pl.state)
            unshown = {n: pl.state.shows[n] for n in pl.state.shown}
            corrected, changed = summary(after, unshown)
            vals = {p.name: p.parse(after[p.name]) for p in spec.params}
            return Correction(values=vals, dialog=dialog_text, form=dict(pl.state.form), request=old_req,
                              shows=dict(pl.state.shows), edits=pl.edits, corrected=corrected,
                              changed=changed, unshown=unshown, log=log, source=source, flow=pl.flow,
                              unchanged=True, result=old,
                              note="Magic's Apply keeps the instance: these values give its cell %s"
                                   % old.magic_cell)
    request = dict(form)
    if apply_check:
        request[APPLY_KEY] = "1"
    res = generator.get(spec, request)
    shows, numbers, note = shows_of(spec, form, res)
    vals, shown, unshown = _visible(spec, shows, numbers, values)
    after = {p.name: p.format(vals[p.name]) for p in spec.params}
    corrected, changed = summary(after, unshown)
    glog = res.messages or ""
    full = log + ("" if not glog or glog in log else glog)
    return Correction(values=vals, dialog=encode(spec.name, form, apply_check, shows, shown),
                      form=form, request=request, shows=shows, edits=pl.edits, corrected=corrected,
                      changed=changed, unshown=unshown, log=full, source=source, flow=pl.flow,
                      result=res, note=note)


def request(spec, values, dialog_text, generator):
    """The text the PCell sends Magic for these values: the stored request
    when the values are the ones its dialog shows, else what Create or
    Apply gets from the dialog."""
    req = stored_request(spec, values, dialog_text)
    if req is not None:
        return req, None
    c = correct(spec, values, dialog_text, generator)
    if c is None:  # stored_request and plan disagree only on unparsable text
        raise InvalidValue(spec.params[0].name if spec.params else "?", dialog_text[:60],
                           "is a stored dialog form that can't be read")
    return c.request, c
