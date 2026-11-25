"""PCell declarations built from the manifest, one class per device.

``PCellDeclarationHelper.param()`` installs a descriptor on the class, so each
device gets its own subclass; sharing one class would mix up parameters.
"""

import hashlib
import json
import logging

from . import dialog
from ._kl import db, warn, error
from .dialog import DIALOG_PARAM
from .importer import gds_grid_nm, gds_has_shapes, insert_gds_flat
from .manifest import DISPLAY_PARAMS, InvalidValue
from .stamp import apply_stamp, parse_stamp, same_versions

log = logging.getLogger("klayout_magic_pcells")

PLACEHOLDER_LAYER = (255, 0)
CREATED_PARAM = "kmp_created"


class PCellNameError(Exception):
    pass


def _ktype(helper, ptype):
    return {
        "float": helper.TypeDouble,
        "int": helper.TypeInt,
        "bool01": helper.TypeBoolean,
        "signed": helper.TypeString,
        "string": helper.TypeString,
        "choice": helper.TypeString,
        "numlist": helper.TypeString,
    }[ptype]


def _num_equal(a, b):
    if a == b:
        return True
    try:
        return float(a) == float(b)
    except (TypeError, ValueError):
        return False


def changed_params(request, checked):
    """Parameters whose value ``_check`` changed (numerically, for numbers)."""
    out = {}
    for k, v in request.items():
        if k in checked and not _num_equal(v, checked[k]):
            out[k] = checked[k]
    return out


def reserved_names():
    return set(dir(db.PCellDeclarationHelper))


def check_names(spec):
    bad = [p.name for p in spec.params
           if p.name in reserved_names() or p.name in (CREATED_PARAM, DIALOG_PARAM)]
    if bad:
        raise PCellNameError("%s: parameter name(s) %s collide with PCellDeclarationHelper "
                             "attributes" % (spec.name, ", ".join(bad)))


def box_sides(message):
    """The box-paint parameters a generator's message is about: "Via1 width
    must be at least 0.26um" names w, "... height ..." h, anything else
    both."""
    words = set(message.lower().split())
    sides = [n for n, word in (("w", "width"), ("h", "height")) if word in words]
    return sides or ["w", "h"]


def stamp_with_grid(stamp, grid_nm):
    """The generated-by stamp with the grid of this variant's Magic output
    (audit compares it with a file's dbu)."""
    return stamp + (";grid=%d" % grid_nm if grid_nm else "")


def draw_placeholder(layout, cell, device, reason):
    li = layout.layer(*PLACEHOLDER_LAYER)
    cell.shapes(li).insert(db.DBox(-0.5, -0.5, 0.5, 0.5))
    text = "KMP_ERROR %s: %s" % (device, " ".join(str(reason).split())[:400])
    cell.shapes(li).insert(db.DText(text, db.DTrans()))


def make_pcell(spec, state):
    """Return a PCellDeclarationHelper instance for ``spec``.

    ``state`` is the PDK's runtime state (a PdkState): ``state.generator``,
    ``state.created_stamp``, ``state.stamp_dict``, ``state.cfg`` and
    ``state.library_name``.
    """
    check_names(spec)
    if spec.family in DISPLAY_PARAMS:
        lead = [n for n in DISPLAY_PARAMS[spec.family] if spec.param(n)]
    else:
        lead = [p.name for p in spec.params if p.type in ("float", "int")][:3]
    lib = state.library_name
    # Box-paint generators have no dialog in Magic: their menu entry paints
    # into the box as it is.
    has_dialog = spec.kind != "box"

    class _DevicePCell(db.PCellDeclarationHelper):
        def __init__(self):
            super().__init__()
            for p in spec.params:
                kw = {"default": p.default_value(), "tooltip": p.label}
                if p.unit:
                    kw["unit"] = p.unit
                if p.type == "choice":
                    kw["choices"] = [(c, c) for c in p.choices]
                self.param(p.name, _ktype(self, p.type), p.description, **kw)
            self.param(CREATED_PARAM, self.TypeString, "Created with", hidden=True,
                       readonly=True, default=state.created_stamp)
            if has_dialog:
                # The form of Magic's dialog these values came from (see
                # dialog.py); set by coerce, never typed.
                self.param(DIALOG_PARAM, self.TypeString, "Magic's dialog form", hidden=True,
                           default="")
            self._warned = set()

        # -- helpers ------------------------------------------------------

        def _values(self):
            return {p.name: getattr(self, p.name) for p in spec.params}

        def _dialog_text(self):
            return (getattr(self, DIALOG_PARAM) or "") if has_dialog else ""

        def _request(self, check=True):
            """The text sent to Magic: for a device, the form of Magic's
            dialog these values show (computed by Magic when they aren't the
            stored form's, which only happens if coerce couldn't run); for a
            box-paint generator, the box as typed.

            check=False only for names and labels, which never reach Magic
            and must never fail (a failing cell name leaves an unreadable
            file, K3): the stored form if it is the values', else the typed
            text."""
            values = self._values()
            if not has_dialog:
                return spec.build_request(values, check=check)
            if not check:
                req = dialog.stored_request(spec, values, self._dialog_text())
                return dict(req) if req is not None else spec.build_request(values, check=False)
            if state.generator is None:
                req = dialog.stored_request(spec, values, self._dialog_text())
                if req is None:
                    raise RuntimeError("the Magic backend is not running")
                return dict(req)
            req, _corr = dialog.request(spec, values, self._dialog_text(), state.generator)
            return dict(req)

        # -- KLayout hooks ------------------------------------------------

        def display_text_impl(self):
            try:
                if has_dialog:
                    # The values Magic's dialog shows for the instance.
                    vals = self._values()
                    parts = ["%s=%s" % (n, spec.param(n).format(vals[n])) for n in lead]
                    return "%s(%s)" % (spec.short_name, " ".join(parts))
                req = self._request(check=False)
                res = state.generator.peek(spec, req) if state.generator else None
                changed = changed_params(req, res.checked) if res else {}
                parts = []
                for n in lead:
                    v = req[n]
                    if n in changed:
                        v = "%s*" % changed[n]
                    parts.append("%s=%s" % (n, v))
                return "%s(%s)" % (spec.short_name, " ".join(parts))
            except Exception as e:  # never break the GUI over a label
                return "%s(?: %s)" % (spec.short_name, e)

        def cell_name_impl(self):
            # Hash the request strings, not the raw doubles: a double read back
            # from a saved file can be one ULP off (see ParamSpec.format).
            vals = spec.build_request(self._values(), check=False)
            vals[CREATED_PARAM] = getattr(self, CREATED_PARAM)
            if has_dialog:
                vals[DIALOG_PARAM] = self._dialog_text()
            text = json.dumps(vals, sort_keys=True, separators=(",", ":"))
            return "%s__kmp_%s" % (spec.name, hashlib.sha256(text.encode("utf-8")).hexdigest()[:8])

        def wants_lazy_evaluation(self):
            return bool(state.cfg.lazy)

        def coerce_parameters_impl(self):
            # The values become what Magic's dialog shows after these edits
            # and Create (or Apply, on an instance that has a stored state;
            # dialog.py). Values that the stored dialog shows are left alone,
            # so reopening a file or refreshing the library never runs
            # _check on Magic's own output again. KLayout keeps the result in
            # the GUI form and on a library refresh; elsewhere (create_cell)
            # it hands it to produce without storing it.
            if not has_dialog:
                return
            try:
                corr = dialog.correct(spec, self._values(), self._dialog_text(), state.generator)
            except Exception as e:
                # produce then asks again and draws the error marker if it
                # fails there too.
                log.debug("%s: coerce failed: %s", spec.name, e)
                return
            if corr is None:
                return
            for p in spec.params:
                setattr(self, p.name, corr.values[p.name])
            setattr(self, DIALOG_PARAM, corr.dialog)
            if (corr.corrected or corr.unshown or corr.unchanged) and \
                    ("dialog", corr.dialog, tuple(corr.edits)) not in self._warned:
                self._warned.add(("dialog", corr.dialog, tuple(corr.edits)))
                parts = ["%s=%s (entered %s)" % (n, corr.shows[n], typed)
                         for n, (typed, _a) in corr.corrected.items()]
                parts += ["%s=%s" % (n, t) for n, t in corr.unshown.items() if n not in corr.corrected]
                msg = " | ".join(corr.log.strip().splitlines())
                warn("%s %s: %sMagic's dialog shows %s%s"
                     % (lib, spec.short_name, (corr.note + "; ") if corr.unchanged else "",
                        ", ".join(parts), (": " + msg) if msg else ""))

        def produce_impl(self):
            try:
                req = self._request()
                if state.generator is None:
                    raise RuntimeError("the Magic backend is not running")
                res = state.generator.get(spec, req)
                try:
                    insert_gds_flat(self.layout, self.cell, res.gds_path)
                except Exception as e:
                    if res.source == "magic":
                        raise
                    # A remembered or cached GDS that KLayout can't read:
                    # forget it and ask Magic once.
                    warn("%s %s: the cached GDS %s can't be read (%s); regenerating it"
                         % (lib, spec.short_name, res.gds_path, e))
                    state.generator.evict(spec, req)
                    self.cell.clear_shapes()
                    res = state.generator.get(spec, req)
                    insert_gds_flat(self.layout, self.cell, res.gds_path)
                # Before anything else: an instance saved under another Magic,
                # PDK or generator code says so even when the regenerated
                # cell comes out empty (a generator that now fails).
                created = parse_stamp(getattr(self, CREATED_PARAM) or "")
                if created and not same_versions(created, state.stamp_dict):
                    key = ("created", getattr(self, CREATED_PARAM))
                    if key not in self._warned:
                        self._warned.add(key)
                        warn("%s %s: instance created with %s, regenerated with %s"
                             % (lib, spec.short_name, getattr(self, CREATED_PARAM), state.created_stamp))
                if "grid_nm" not in res.sidecar:
                    try:
                        res.sidecar["grid_nm"] = gds_grid_nm(res.gds_path)
                    except Exception as e:  # the import above read the file
                        log.debug("grid of %s: %s", res.gds_path, e)
                        res.sidecar["grid_nm"] = None
                stamp = stamp_with_grid(res.stamp, res.sidecar.get("grid_nm"))
                if not apply_stamp(self.layout, self.cell, stamp):
                    # Magic wrote a cell with no shapes (for example resistor
                    # l=0, where _draw fails on the "1.0u" that _check puts
                    # in, or a via box below the generator's minimum).
                    # Parity means drawing the same nothing; say so.
                    if ("empty", res.key) not in self._warned:
                        self._warned.add(("empty", res.key))
                        warn("%s %s: Magic drew nothing for these parameters: %s"
                             % (lib, spec.short_name,
                                " | ".join(res.messages.strip().splitlines()) or "no message"))
                    return
                if res.messages.strip() and res.key not in self._warned:
                    self._warned.add(res.key)
                    warn("%s %s: Magic's %s: %s"
                         % (lib, spec.short_name, "messages" if spec.kind == "box" else "_check", " | ".join(res.messages.strip().splitlines())))
            except Exception as e:
                log.debug("produce failed", exc_info=True)
                error("%s %s: generation failed, drawing a placeholder on %d/%d: %s"
                      % (lib, spec.short_name, PLACEHOLDER_LAYER[0], PLACEHOLDER_LAYER[1], e))
                try:
                    self.cell.clear_shapes()
                except Exception:
                    pass
                draw_placeholder(self.layout, self.cell, spec.name, e)

        def callback_impl(self, name):
            # GUI form only: self.<p> is a PCellParameterState here. KLayout
            # calls this before coerce, which then writes the corrected
            # values into the form; the icons say what Magic's dialog did.
            states = self._param_states
            if states is None or not spec.params:
                return
            corr = stored = chk = None
            try:
                values = {p.name: states.parameter(p.name).value for p in spec.params}
                if has_dialog:
                    # Magic's Create (or Apply) draws, and what its dialog
                    # then shows comes from that, so the variant is made
                    # here even with KMP_LAZY (produce takes it from the
                    # memo).
                    dtext = states.parameter(DIALOG_PARAM).value or ""
                    req, corr = dialog.request(spec, values, dtext, state.generator)
                    stored = dialog.decode(spec, dtext) if corr is None else None
                    res = corr.result if corr is not None and corr.result is not None \
                        else state.generator.get(spec, req)
                    drawn = gds_has_shapes(res.gds_path)
                    said = res.messages or ""
                else:
                    req = spec.build_request(values)
                    chk = state.generator.check(spec, req)
                    drawn = True
                    said = chk.log
                    if not state.cfg.lazy:
                        # The form regenerates on every edit anyway (produce
                        # takes this result from the memo): see whether Magic
                        # draws anything, which the check alone doesn't tell.
                        res = state.generator.get(spec, req)
                        drawn = gds_has_shapes(res.gds_path)
                        said = res.messages or chk.log
            except InvalidValue as e:
                st = states.parameter(e.param)
                st.icon = db.PCellParameterState.ErrorIcon
                st.tooltip = str(e)
                return
            except Exception as e:
                st = states.parameter(spec.params[0].name)
                st.icon = db.PCellParameterState.ErrorIcon
                st.tooltip = "Magic backend failed: %s" % e
                return
            msg = " ".join(said.split())
            dmsg = " ".join(corr.log.split()) if corr is not None else ""
            if corr is not None and corr.unchanged:
                dmsg = corr.note + ((": " + dmsg) if dmsg else "")
            if spec.kind == "box":
                # A box-paint generator prints only when the box is below
                # its minimum, and then paints nothing; the message names
                # the side ("Via1 width must be at least 0.26um").
                changed = changed_params(req, chk.checked)
                nothing = bool(msg) if state.cfg.lazy else not drawn
                flagged = set(box_sides(msg)) if nothing else set()
            else:
                changed = {}
                nothing = not drawn
                flagged = (set(corr.corrected) if corr is not None else set()) or (
                    {spec.params[0].name} if nothing else set())
            for p in spec.params:
                st = states.parameter(p.name)
                icon, tip = db.PCellParameterState.NoIcon, p.label
                if corr is not None and p.name in corr.corrected:
                    typed, _shown = corr.corrected[p.name]
                    icon = db.PCellParameterState.WarningIcon
                    tip = "Magic's dialog shows %s (entered %s)%s" % (
                        corr.shows[p.name], typed, (": " + dmsg) if dmsg else "")
                elif corr is not None and p.name in corr.changed:
                    before, _shown = corr.changed[p.name]
                    icon = db.PCellParameterState.InfoIcon
                    tip = "Magic's dialog sets this to %s (was %s)%s" % (
                        corr.shows[p.name], before, (": " + dmsg) if dmsg else "")
                if corr is not None and p.name in corr.unshown:
                    icon = db.PCellParameterState.WarningIcon
                    tip = ("Magic's dialog shows %s here, which this field can only show as %s"
                           % (corr.unshown[p.name], p.format(corr.values[p.name])))
                elif corr is None and stored is not None and p.name in stored.shown:
                    icon = db.PCellParameterState.InfoIcon
                    tip = "Magic's dialog shows %s here" % stored.shows[p.name]
                if spec.kind == "box" and p.name in changed and not nothing:
                    icon = db.PCellParameterState.WarningIcon
                    tip = "Magic draws %s (entered %s)%s" % (changed[p.name], req[p.name], (": " + msg) if msg else "")
                if nothing and p.name in flagged:
                    icon = db.PCellParameterState.WarningIcon
                    tip = "Magic draws nothing%s%s" % ((": " + msg) if msg else "",
                                                       (" (%s)" % tip) if tip != p.label else "")
                st.icon = icon
                st.tooltip = tip

    _DevicePCell.__name__ = "PCell_" + spec.name
    return _DevicePCell()
