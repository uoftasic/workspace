"""The device manifest: what a PDK's Magic generators declare, shipped as JSON.

``tools/build_manifest.py --pdk <pdk>`` builds ``data/manifest-<pdk>.json``
by querying Magic in the pinned image. It lists the PDK's devices (every
``<ns>::<dev>_draw`` with a ``_defaults`` proc) and its box-paint generators
(``_draw`` procs that take no arguments and paint into the cursor box: the
vias, contacts, substrate contacts, guard rings and wells). This module
reads it and turns parameter values into the strings sent to Magic.
"""

import json
import re

# Manifest parameter types that become PCell parameters.
EDITABLE_TYPES = ("float", "int", "bool01", "signed", "choice", "numlist")

# Short labels used in display texts, per family (only the ones the device
# has are shown; a family not listed shows its first three numbers).
DISPLAY_PARAMS = {
    "mos": ("w", "l", "nf", "ng"),
    "moscap": ("w", "l", "nf", "ng"),
    "varactor": ("w", "l", "nf", "ng"),
    "res": ("w", "l", "nx"),
    "mim_cap": ("w", "l", "nx", "ny"),
    "cap": ("w", "l", "nx", "ny"),
    "diode": ("w", "l"),
    "photodiode": ("nx", "ny"),
    "fixed": ("nx", "ny"),
    "bjt": ("w", "l", "nx", "ny"),
    "inductor": ("diameter", "width", "turns"),
    "special": ("width", "height", "shape"),
    "other": ("metalbot", "metaltop"),
    "box_paint": ("w", "h"),
}

# A decimal number, the only thing a "numlist" element may be.
NUMBER_RE = re.compile(r"[+-]?([0-9]+\.?[0-9]*|\.[0-9]+)([eE][+-]?[0-9]+)?")

_UNIT_RE = re.compile(r"\s*(\[\+/-\])?\s*\(([^()]*)\)\s*$")
_UNITS = {"um": "µm", "um^2": "µm²", "%": "%", "ohms": "Ω", "fF": "fF"}

# What a "signed" (coverage) value may look like before it is sent to Magic:
# a decimal number with an optional + or - anchor, and optional whitespace
# around it (Tcl's own whitespace characters, ASCII digits only). sky130A.tcl
# evaluates these values with an unbraced "expr abs($viagb)", which performs
# command and variable substitution on the value, so a value such as
# "[exec ...]" would run when a file is opened. Nothing that matches this
# pattern can contain a Tcl substitution or a command name.
SIGNED_RE = re.compile(r"[ \t\n\r\f\v]*[+-]?([0-9]+\.?[0-9]*|\.[0-9]+)([eE][+-]?[0-9]+)?[ \t\n\r\f\v]*")


class ManifestError(Exception):
    pass


class InvalidValue(ValueError):
    """A parameter value that is refused before it reaches Magic."""

    def __init__(self, param, value, why):
        self.param = param
        self.value = value
        shown = repr(value) if len(str(value)) <= 60 else repr(str(value)[:60]) + "..."
        super().__init__("%s=%s %s" % (param, shown, why))


def format_float(value):
    """The text Magic gets for a float: the value as KLayout keeps it in a
    saved file, rounded to 12 significant digits, written like Python's repr
    of a float.

    KLayout 0.30.11 writes a double PCell parameter with 15 significant
    digits and parses that text back up to one ULP off: 4.257627156815 is
    written "4.257627156815" and reopens as 4.2576271568149995. Rounding the
    reopened double to 12 digits directly would then give "4.25762715681"
    where the first session sent "4.25762715682". Going through the 15-digit
    text first gives the same result for the value and for any double
    within a few ULPs of that text, so a reopened file sends the same
    request (and gets the same cache key) as the session that saved it.
    A negative zero is sent as "0.0": KLayout saves it as 0.
    """
    v = float(value)
    if v == 0:
        return "0.0"
    return repr(float("%.12g" % float("%.15g" % v)))


class ParamSpec:
    def __init__(self, d, family):
        self.name = d["name"]
        self.type = d["type"]
        self.default = d["default"]
        self.label = d.get("label") or self.name
        self.widget = d.get("widget")
        self.editable = bool(d.get("editable"))
        self.check_min = d.get("check_min")
        self.check_max = d.get("check_max")
        self.check_int = d.get("check_int")
        self.choices = list(d.get("choices") or [])
        self.family = family

    @property
    def unit(self):
        m = _UNIT_RE.search(self.label)
        if not m:
            return None
        return _UNITS.get(m.group(2).strip(), m.group(2).strip())

    @property
    def description(self):
        text = _UNIT_RE.sub("", self.label).strip() or self.name
        if self.name == "w" and self.family in ("mos", "varactor"):
            text = "Finger width"
        if self.type == "signed":
            text += " (+ or - prefix anchors the vias)"
        if self.type == "numlist":
            text += " (one number, or one per layer separated by spaces)"
        return text

    def parse(self, text):
        """Magic's string -> the Python value of the declared PCell type.

        ``signed`` and ``string`` values come back exactly as given: Magic
        reads the first character of a coverage value as its anchor, so " +50"
        is not "+50".
        """
        if self.type in ("signed", "string", "choice", "numlist"):
            return str(text)
        t = str(text).strip()
        if self.type == "float":
            return float(t)
        if self.type == "int":
            f = float(t)
            if f != int(f):
                raise ValueError("%s: %r is not an integer" % (self.name, text))
            return int(f)
        if self.type == "bool01":
            return bool(int(float(t)))
        return t

    def default_value(self):
        return self.parse(self.default)

    def format(self, value):
        """The PCell value -> the string sent to Magic.

        Floats are rounded to 12 significant digits (see format_float) and
        written the way Python writes a float ("0.35", "31.0"). The rounding
        matters because KLayout 0.30.11 doesn't keep doubles exactly in a
        saved file: "0.35" reads back as 0.35000000000000003. The ".0"
        matters because Tcl divides integer-looking strings as integers. A
        float equal to the manifest default is sent as Magic's own default
        string ("0.420"), so a request for the defaults is byte-identical to
        what Magic merges in itself. ``signed`` values are sent verbatim, whitespace included:
        Magic reads their first character as an anchor ("+50", " +50" and
        "50" are three requests). ``check()`` decides whether one may be sent.
        """
        if self.type == "float":
            text = format_float(value)
            try:
                if text == format_float(float(self.default)):
                    return self.default
            except ValueError:
                pass
            return text
        if self.type == "int":
            return str(int(value))
        if self.type == "bool01":
            return "1" if value else "0"
        return str(value)

    def check(self, text):
        """Raise InvalidValue if the string ``text`` must not reach Magic."""
        if self.type == "signed" and not SIGNED_RE.fullmatch(str(text)):
            raise InvalidValue(self.name, text, "is not a number with an optional + or - in front; "
                               "the PDK's generator code evaluates this value with an unbraced "
                               "expr, which runs any [command] in it, so it was not sent to Magic")
        if self.type == "choice" and str(text) not in self.choices:
            raise InvalidValue(self.name, text, "is not one of Magic's choices for it (%s), so it "
                               "was not sent to Magic" % ", ".join(self.choices))
        if self.type == "numlist":
            toks = str(text).split()
            if not toks or not all(NUMBER_RE.fullmatch(t) for t in toks):
                raise InvalidValue(self.name, text, "is not a number or a list of numbers separated "
                                   "by spaces; the PDK's generator code evaluates each element with "
                                   "an unbraced expr, so it was not sent to Magic")

    def canonical(self, text):
        """Round-trip a string through parse/format (used by the sweep)."""
        return self.format(self.parse(text))


class DeviceSpec:
    """A device (``kind`` "device") or a box-paint generator (``kind``
    "box", form "box", parameters w and h)."""

    def __init__(self, d):
        self.name = d["name"]
        self.kind = d.get("kind", "device")
        self.family = d["family"]
        self.nocell = bool(d.get("nocell", False))
        self.form = d.get("form") or ("box" if self.kind == "box" else
                                      "wrapper" if self.nocell else "cell")
        self.label = d.get("label") or self.name
        self.defaults = [tuple(kv) for kv in d["defaults"]]
        self.all_params = [ParamSpec(p, self.family) for p in d["params"]]
        self.params = [p for p in self.all_params if p.editable and p.type in EDITABLE_TYPES]
        self.raw = d

    @property
    def short_name(self):
        n = self.name
        for pre in ("sky130_fd_pr__", "sky130_fd_bs_flash__"):
            if n.startswith(pre):
                return n[len(pre):]
        return n

    def param(self, name):
        for p in self.params:
            if p.name == name:
                return p
        return None

    def internal(self, name):
        for k, v in self.defaults:
            if k == name:
                return v
        return None

    def build_request(self, values, check=True):
        """PCell values (name -> Python value) -> {name: string} for Magic.

        Every editable parameter is included; missing ones take the default.
        With ``check`` (the default) a value that must not reach Magic raises
        InvalidValue. ``check=False`` is for cell names and display texts,
        which must never fail and never reach Magic.
        """
        out = {}
        for p in self.params:
            v = values.get(p.name, None)
            out[p.name] = p.default if v is None else p.format(v)
            if check:
                p.check(out[p.name])
        return out

    def parse_request(self, request):
        """{name: string} -> {name: Python value} for ``Layout.create_cell``."""
        out = {}
        for k, v in request.items():
            p = self.param(k)
            if p is None:
                raise ManifestError("%s has no editable parameter %r" % (self.name, k))
            out[k] = p.parse(v)
        return out

    def defaults_values(self):
        return {p.name: p.default_value() for p in self.params}

    @property
    def batch(self):
        return self.raw.get("defaults_run", {})

    @property
    def vendor_cells(self):
        """Cells other than the top in Magic's output for the defaults: for a
        fixed device, the vendor cell from libs.ref and its children."""
        run = self.batch
        names = run.get("cell_names") or []
        tops = set(run.get("top_cells") or [])
        return [c for c in names if c not in tops] if self.nocell else []


class Manifest:
    def __init__(self, data, path=None):
        self.data = data
        self.path = path
        if data.get("format") != 1:
            raise ManifestError("unsupported manifest format %r" % data.get("format"))
        self.pdk = data["pdk"]
        self.namespace = data.get("namespace", "")
        self.devices = [DeviceSpec(d) for d in data["devices"]]
        self.devices += [DeviceSpec(dict(d, kind="box")) for d in data.get("boxpaint", [])]
        self._by_name = {d.name: d for d in self.devices}
        if len(self._by_name) != len(self.devices):
            raise ManifestError("manifest %s names a PCell twice" % path)

    @classmethod
    def load(cls, path):
        try:
            with open(path, encoding="utf-8") as f:
                return cls(json.load(f), path)
        except (OSError, ValueError, KeyError) as e:
            raise ManifestError("cannot read manifest %s: %s" % (path, e))

    def __getitem__(self, name):
        return self._by_name[name]

    def __contains__(self, name):
        return name in self._by_name

    def get(self, name):
        return self._by_name.get(name)

    @property
    def defaults_digest(self):
        return self.data.get("defaults_digest", "")

    def defaults_by_device(self):
        return {d.name: [list(kv) for kv in d.defaults] for d in self.devices if d.kind == "device"}

    def vendor_cells(self):
        out = []
        for d in self.devices:
            for c in d.vendor_cells:
                if c not in out:
                    out.append(c)
        return out

    def editable_names(self):
        names = []
        for d in self.devices:
            for p in d.params:
                if p.name not in names:
                    names.append(p.name)
        return names


def diff_defaults(manifest_defaults, live_defaults):
    """Devices whose defaults differ between the manifest and live Magic."""
    out = []
    for dev in sorted(set(manifest_defaults) | set(live_defaults)):
        a = [list(x) for x in manifest_defaults.get(dev, [])]
        b = [list(x) for x in live_defaults.get(dev, [])]
        if a != b:
            if not a:
                out.append((dev, "only in the live Magic"))
            elif not b:
                out.append((dev, "only in the manifest"))
            else:
                ka, kb = dict(map(tuple, a)), dict(map(tuple, b))
                changed = sorted(k for k in set(ka) | set(kb) if ka.get(k) != kb.get(k))
                out.append((dev, "keys differ: " + ", ".join(changed) if changed else "order differs"))
    return out
