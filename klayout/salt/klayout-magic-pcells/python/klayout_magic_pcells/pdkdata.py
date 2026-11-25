"""Per-PDK data: Magic's DRC rules, the GDS layers and how Magic reads them,
what its GDS output writes, the layers it regenerates, the label
convention and the LVS setup files.

The data files (``data/pdk-<pdk>.json``) are built in the pinned image by
``tools/build_pdk_data.py`` from the installed PDK and committed. This
module only reads them; it needs nothing beyond the standard library.

    data = pdkdata.load("sky130A")
    data.layer(93, 44)["read"]            # 'device-only'
    data.rules_by_why("N-well width < 0.84um (nwell.1)")
    data.generated()                      # implants Magic grows from device shapes
    data.ports()["both"]                  # the label form Magic and KLayout's LVS both accept
    data.grid_um                          # 0.005
"""

import json
import os
import re

SCHEMA = 1
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


class PdkDataError(Exception):
    pass


def shipped_data(pdk):
    return os.path.join(DATA_DIR, "pdk-%s.json" % pdk)


def _pair(gds_l, gds_d=None):
    """(layer, datatype) from two numbers, a [l, d] list or an "l/d" string."""
    if gds_d is None:
        if isinstance(gds_l, str):
            a, b = gds_l.split("/")
            return int(a), int(b)
        gds_l, gds_d = gds_l
    return int(gds_l), int(gds_d)


def _why_key(text):
    """A why-text without the value Magic prints in place of %d, so that
    the tech file's "N-well width < %d (nwell.1)" and Magic's message
    "N-well width < 0.84um (nwell.1)" have the same key. %a is an area,
    which Magic prints as, for example, "0.2025um^2"."""
    t = re.sub(r"%[dfsa]", "#", text.strip())
    t = re.sub(r"(?<![\w.])-?\d+(?:\.\d+)?(?:\s*(?:um\^?2|um|µm²|µm|nm))?(?![\w.])", "#", t)
    return re.sub(r"\s+", " ", t)


class PdkData:
    """The parsed data file of one PDK. ``raw`` is the JSON as loaded; the
    top-level keys are also attributes (``drc``, ``layers``, ``cifout``,
    ``lvs`` and so on)."""

    def __init__(self, raw, path=None):
        if raw.get("schema") != SCHEMA:
            raise PdkDataError("%s: schema %r, this version reads schema %d"
                               % (path or "data", raw.get("schema"), SCHEMA))
        self.raw = raw
        self.path = path
        self.pdk = raw["pdk"]
        self.grid_um = raw["grid_um"]
        self.source = raw.get("source", {})
        self.drc = raw.get("drc", {})
        self.layers = raw.get("layers", [])
        self.cifout = raw.get("cifout", {})
        self.lvs = raw.get("lvs", {})
        self.error_marker = tuple(raw.get("error_marker", (255, 0)))
        self._layers = {(r["gds"][0], r["gds"][1]): r for r in self.layers}
        self._why = {}
        for r in self.drc.get("rules", []):
            self._why.setdefault(r["why"], []).append(r)
            k = _why_key(r["why"])
            if k != r["why"]:
                self._why.setdefault(k, []).append(r)

    # -- lookup helpers the checks use --

    def layer(self, gds_l, gds_d=None):
        """The layer row of a GDS pair ({"gds", "name", "role", "read",
        "magic_types", ...}), or None when neither Magic's reader nor the
        PDK's layer list knows it; Magic ignores such a layer."""
        return self._layers.get(_pair(gds_l, gds_d))

    def rules_by_why(self, why_text):
        """The rule statements whose why-text is ``why_text``, either as the
        tech file writes it ("... < %d (nwell.1)") or as Magic prints it
        ("... < 0.84um (nwell.1)"). Rules with no ID in the why-text
        ("... ()") are found the same way."""
        hit = self._why.get(why_text)
        if hit is None:
            hit = self._why.get(_why_key(why_text), [])
        return list(hit)

    def generated(self):
        """The implant, marker and well layers Magic regenerates on output,
        each with the distance the gdsii style grows it from its device
        shape (``grow_um``, None where neither the parser nor the hand
        table gives one) and the tech-file line."""
        return list(self.raw.get("generated", []))

    def ports(self):
        """The label convention: ``text`` (pairs whose texts name a net in
        Magic), ``pin`` (pin-box pairs Magic reads as port and conductor),
        ``port_text`` (texts that make a Magic port), ``klayout_lvs_text``
        (pairs the KLayout LVS deck reads names from), ``both`` (the forms
        both accept: a text pair, with the pin pair it needs or None) and
        ``lines`` (citations per pair)."""
        return dict(self.raw.get("ports", {}))

    # -- more lookups --

    def rules(self, style=None, rule_id=None):
        """Rule statements, optionally only those of one style (for example
        "drc(full)") or with one rule ID."""
        out = self.drc.get("rules", [])
        if style is not None:
            out = [r for r in out if style in r["styles"]]
        if rule_id is not None:
            out = [r for r in out if rule_id in r["ids"]]
        return list(out)

    def layers_by_read(self, read):
        """Layer rows with one read mode: "ignored", "device-only", "pin",
        "text", "paint" or "reads-as" (any "reads-as:<type>")."""
        if read == "reads-as":
            return [r for r in self.layers if r["read"].startswith("reads-as:")]
        return [r for r in self.layers if r["read"] == read]

    def layers_by_role(self, *roles):
        return [r for r in self.layers if r["role"] in roles]

    def written_pairs(self, magic_type):
        """The GDS pairs Magic's gdsii output style writes a type on."""
        return [tuple(p) for p in self.cifout.get(magic_type, [])]


_cache = {}


def load(pdk, path=None):
    """The data of a PDK, from the shipped file (or ``path``)."""
    path = path or shipped_data(pdk)
    hit = _cache.get(path)
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        raise PdkDataError("no data file for %s at %s" % (pdk, path))
    if hit is not None and hit[0] == mtime and hit[1].pdk == pdk:
        return hit[1]
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError) as e:
        raise PdkDataError("cannot read %s: %s" % (path, e))
    if raw.get("pdk") != pdk:
        raise PdkDataError("%s holds the data of %s, not %s" % (path, raw.get("pdk"), pdk))
    data = PdkData(raw, path)
    _cache[path] = (mtime, data)
    return data
