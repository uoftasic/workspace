"""Which PDK a layout belongs to, for the jobs (DRC, extraction, LVS, the
layer and port checks).

In this order:

1. ``--pdk`` (``explicit``);
2. the layout's technology name: ``sky130A``; ``gf180mcu`` (gf180mcuD's
   KLayout technology; this version supports variant D only); ``sg13g2``;
   ``sg13cmos5l``. The technology decides only when the layout's shapes
   fit its PDK about as well as any other PDK (``layer_fit``). File > Open
   in this image's KLayout gave a plain GDS the technology sg13g2 in one of
   the two GUI rigs that tried it and no technology in the other; this
   rule handles the first, and step 5 the second. When the technology's PDK knows
   less than ``TECH_FIT`` (3/4) of the shapes the best-fitting PDK knows,
   the technology does not decide, and the best-fitting PDK becomes the
   hint of step 5 in place of the PDK variable. The two IHP PDKs share
   their layer numbers, so they fit alike and the technology picks between
   them;
3. the PDK whose plugin library the layout's PCell variants come from
   (``sky130_magic``, ...), live or ``<defunct>``, else the PDK whose
   manifest has the device of every ``<device>__kmp_<8 hex>`` cell (a file
   saved without the libraries);
4. the only PDK that ``KMP_PDKS`` selects;
5. a guess: the PDK whose layers fit the layout best, when step 2 set
   the technology aside; else the image's ``PDK`` variable, when it names
   a supported PDK that is selected. A hand-drawn layout with no
   technology gets here, since ``KMP_PDKS=auto`` selects all four PDKs;
   the reason says it is a guess;
6. else ``PdkChoiceError``, with the candidates: the GUI asks, the command
   line needs ``--pdk``.

``choose_pdk`` returns ``(pdk, reason)``; the reason names the step that
decided, for the reports.
"""

import json
import os
import re

from .config import LIBRARY_NAMES, PDKS, SUPPORTED_PDKS, shipped_manifest

# KLayout technology names -> PDK.
TECHNOLOGIES = {
    "sky130A": "sky130A",
    "gf180mcu": "gf180mcuD",
    "gf180mcuD": "gf180mcuD",
    "sg13g2": "ihp-sg13g2",
    "ihp-sg13g2": "ihp-sg13g2",
    "sg13cmos5l": "ihp-sg13cmos5l",
    "ihp-sg13cmos5l": "ihp-sg13cmos5l",
}
_PDK_OF_LIBRARY = {lib: pdk for pdk, lib in LIBRARY_NAMES.items()}
_VARIANT = re.compile(r"^(.+)__kmp_[0-9a-f]{8}(?:\$\d+)?$")


class PdkChoiceError(Exception):
    """No rule decided. ``candidates``: the PDKs the layout could belong to;
    ``hint``: the guess (the best-fitting PDK when the technology was set
    aside, else the PDK variable's), or None; ``hint_reason``: why that is
    the guess, as a reason for the reports and a sentence for a dialog."""

    def __init__(self, message, candidates=(), hint=None, hint_reason=None, why=None):
        Exception.__init__(self, message)
        self.candidates = list(candidates)
        self.hint = hint
        self.hint_reason = hint_reason
        # Why no rule decided, for a dialog: the technology set aside, or None.
        self.why = why


# The technology's PDK must know at least this share of the shapes that the
# best-fitting PDK knows for the technology to decide. Measured on the case
# suite's inverters and hier cases: a layout under another PDK's technology
# scores at most 0.57 of its own PDK (gf180mcuD's C_NMOS_flat against
# ihp-sg13g2, whose 30/0 to 33/0 are drawing layers too).
TECH_FIT = 0.75
_IGNORED_ROLES = ("text", "boundary")
_known = {}


def _known_layers(pdk):
    """The (layer, datatype) pairs the PDK's data file knows, except those
    known only as text or boundary layers."""
    if pdk not in _known:
        try:
            from . import pdkdata
            data = pdkdata.load(pdk)
        except Exception:
            _known[pdk] = None
            return None
        _known[pdk] = data
    return _known[pdk]


def _counts(layout):
    """{(layer, datatype): shapes} over every cell under the top cells."""
    counts = {}
    try:
        indexes = list(layout.layer_indexes())
    except AttributeError:
        return counts
    cells = _tree(layout)
    for li in indexes:
        info = layout.get_info(li)
        n = 0
        for cell in cells:
            n += cell.shapes(li).size()
        if n:
            key = (info.layer, info.datatype)
            counts[key] = counts.get(key, 0) + n
    return counts


def layer_fit(layout, pdks=SUPPORTED_PDKS):
    """``({pdk: shapes on its layers}, all shapes)``: how many of the
    layout's shapes sit on GDS layers each PDK's data file knows
    (``pdkdata.load(pdk).layer(l, d)``), not counting layers known only as
    text or boundary layers, nor the mask layers Magic's mask styles write
    (names ``*.mask``, which no drawing uses: sky130A knows gf180mcuD's
    Metal1, 34/0, as cmm3.mask)."""
    counts = _counts(layout)
    total = sum(counts.values())
    fit = {}
    for p in pdks:
        data = _known_layers(p)
        if data is None:
            continue
        n = 0
        for (l, d), k in counts.items():
            row = data.layer(l, d)
            if (row is not None and row.get("role") not in _IGNORED_ROLES
                    and not str(row.get("name", "")).endswith(".mask")):
                n += k
        fit[p] = n
    return fit, total


def _pct(n, total):
    return "%d%%" % round(100.0 * n / total) if total else "0%"


def _technology_set_aside(layout, pdk, tech, candidates, prefer=None):
    """(best PDK, reason) when the layout's shapes fit another PDK clearly
    better than the technology's ``pdk``, else None. Of PDKs that fit
    alike (the two IHP PDKs), ``prefer`` (the PDK variable's) is taken, else
    the first in SUPPORTED_PDKS."""
    try:
        order = sorted(set(candidates) | {pdk}, key=SUPPORTED_PDKS.index)
        fit, total = layer_fit(layout, order)
    except Exception:
        return None
    if not total or pdk not in fit:
        return None
    best = max(fit, key=lambda p: (fit[p], p == pdk, p == prefer, -order.index(p)))
    if best == pdk or fit[best] == 0 or fit[pdk] >= TECH_FIT * fit[best] or best not in candidates:
        return None
    return best, ("the layout's technology is %s (%s), but %s of its shapes are on %s's layers and %s on %s's"
                  % (tech, pdk, _pct(fit[pdk], total), pdk, _pct(fit[best], total), best))


def _tree(layout):
    """Every cell under the layout's top cells."""
    seen = set()
    out = []
    for top in layout.top_cells():
        for ci in [top.cell_index()] + list(top.called_cells()):
            if ci not in seen:
                seen.add(ci)
                out.append(layout.cell(ci))
    return out


def library_pdks(layout):
    """{pdk: [cell names]} for the cells that are variants of a plugin
    library's PCells, registered or not."""
    found = {}
    for cell in _tree(layout):
        lib = ""
        try:
            if cell.is_library_cell() or cell.is_cold_proxy():
                lib = cell.library_name()
        except AttributeError:
            lib = ""
        pdk = _PDK_OF_LIBRARY.get(lib)
        if pdk:
            found.setdefault(pdk, []).append(cell.name)
    return found


_manifest_devices = {}


def _devices(pdk):
    if pdk not in _manifest_devices:
        try:
            with open(shipped_manifest(pdk), encoding="utf-8") as f:
                man = json.load(f)
            _manifest_devices[pdk] = {d.get("name") for d in man.get("devices", [])}
        except (OSError, ValueError, AttributeError):
            _manifest_devices[pdk] = set()
    return _manifest_devices[pdk]


def variant_pdks(layout):
    """The PDKs whose manifest has the device of every
    ``<device>__kmp_<8 hex>`` cell, or None when the layout has none."""
    devices = set()
    for cell in _tree(layout):
        m = _VARIANT.match(cell.name)
        if m:
            devices.add(m.group(1))
    if not devices:
        return None
    return [p for p in SUPPORTED_PDKS if devices <= _devices(p)]


def choose_pdk(layout=None, explicit=None, cfg=None, env=os.environ, hint_decides=True):
    """``(pdk, reason)`` for ``layout``; see the module's docstring. With
    ``hint_decides=False`` the PDK variable's guess is not taken: the error
    carries it as ``hint``, for a dialog to preselect."""
    if explicit:
        if explicit not in PDKS:
            raise PdkChoiceError("--pdk %s is not supported; this version supports %s"
                                 % (explicit, ", ".join(SUPPORTED_PDKS)), SUPPORTED_PDKS)
        return explicit, "--pdk %s" % explicit
    selected = list(cfg.pdks) if cfg is not None and cfg.pdks else list(SUPPORTED_PDKS)
    candidates = list(selected)
    layer_hint = None   # (pdk, reason) when the technology was set aside
    if layout is not None:
        tech = getattr(layout, "technology_name", "") or ""
        if tech in TECHNOLOGIES:
            layer_hint = _technology_set_aside(layout, TECHNOLOGIES[tech], tech, candidates,
                                               (env or {}).get("PDK"))
            if layer_hint is None:
                return TECHNOLOGIES[tech], "the layout's technology is %s" % tech
        libs = library_pdks(layout)
        if len(libs) == 1:
            pdk, cells = next(iter(libs.items()))
            return pdk, "the layout's PCells come from %s (%s)" % (LIBRARY_NAMES[pdk], cells[0])
        if len(libs) > 1:
            candidates = [p for p in SUPPORTED_PDKS if p in libs]
        else:
            by_variant = variant_pdks(layout)
            if by_variant is not None and len(by_variant) == 1:
                return by_variant[0], ("the layout's PCell variants (%s cells) are devices of %s"
                                       % ("__kmp_", by_variant[0]))
            if by_variant:
                candidates = [p for p in candidates if p in by_variant] or by_variant
    if cfg is not None and len(cfg.pdks) == 1 and cfg.pdks[0] in candidates:
        src = cfg.sources.get("pdks", "")
        return cfg.pdks[0], "the only PDK that KMP_PDKS selects (%s)" % src
    if layer_hint is not None and layer_hint[0] in candidates:
        hint, why = layer_hint
        reason = "a guess from the layers: %s; give --pdk to choose another" % why
        if hint_decides:
            return hint, reason
        raise PdkChoiceError("cannot tell which PDK the layout is for: %s (one of %s); choose one with --pdk"
                             % (why, ", ".join(candidates)), candidates, hint, reason, why)
    guess = (env or {}).get("PDK", "")
    hint = guess if guess in candidates else None
    reason = ("a guess from the PDK variable (PDK=%s): the layout names no technology "
              "and no PCell library; give --pdk to choose another" % hint) if hint else None
    if hint and hint_decides:
        return hint, reason
    raise PdkChoiceError("cannot tell which PDK the layout is for (one of %s); choose one with --pdk"
                         % ", ".join(candidates), candidates, hint, reason)
