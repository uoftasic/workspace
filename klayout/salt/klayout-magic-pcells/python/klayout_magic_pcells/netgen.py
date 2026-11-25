"""netgen LVS: running it, and reading its verdict.

    netgen -batch lvs "<layout netlist> <cell>" "<schematic> <cell>" <setup> <report> -json

writes the text report and, beside it, ``<report without extension>.json``.
netgen exits 0 whatever the result, so the verdict comes from the report:
the "Final result" line and what follows it. netgen's library holds these
results (from ``strings`` on its binary and a grep of its Tcl, in the
pinned image; design-0.6.md 3.2):

- matches: "Circuits match uniquely.", "Circuits match with N symmetries."
  (also "Netlists match uniquely." and "Netlists match with N symmetries"
  for one circuit pair);
- failures: "Netlists do not match.", "Circuits match uniquely with port
  errors.", "Netlists match uniquely with port errors.", "Netlists match
  uniquely with property errors.", "Property errors were found.", "Cell
  pin lists for X and Y do not match.", "Top level cell failed pin
  matching.", "Subcell(s) failed matching."

A layout matches only when the final result says it matches and no
property, port, pin or subcell failure follows. ``-json`` gives, per circuit
pair, the devices per model, the net counts, ``badnets``, ``badelements``,
``properties`` and ``pins``; ``parse_json`` reads them.
"""

import json
import os
import re
import subprocess
import time

# Verdict phrases, matched at the start of a line (after "Final result: ").
_MATCH = re.compile(r"^(Circuits|Netlists) match (uniquely|with (\d+) symmetr\w*)\.?\s*$")
_PORT = re.compile(r"^(Circuits|Netlists) match (uniquely|with \d+ symmetr\w*) with port errors?\.?")
_PROP_LINE = re.compile(r"^(Circuits|Netlists) match (uniquely|with \d+ symmetr\w*) with property errors\.?")
_NOMATCH = "Netlists do not match."
_PIN_FAIL = "Top level cell failed pin matching."
_PROP_FOUND = "Property errors were found."
_SUBCELL_FAIL = "Subcell(s) failed matching."
_PINLIST = re.compile(r"^Cell pin lists for (\S+) and (\S+) do not match\.")
_FINAL = re.compile(r"^Final result:\s*(.*)$")
NO_NET = "(no matching net)"
NO_PIN = "(no matching pin)"
NO_PINS = "(no pins)"


class NetgenError(Exception):
    pass


class Verdict:
    """netgen's result. ``matched``: True only for a match with no property,
    port, pin or subcell failure. ``final``: the final result's text.
    ``reasons``: why it failed, one line each, quoting netgen.
    ``symmetries``: N of "match with N symmetries", else 0.
    ``property_cells``: the cells "The following cells had property errors"
    names. ``complete``: a final result was found at all."""

    def __init__(self):
        self.matched = False
        self.final = None
        self.reasons = []
        self.symmetries = 0
        self.property_errors = False
        self.port_errors = False
        self.pin_errors = False
        self.subcell_errors = False
        self.property_cells = []
        self.pin_lists = []          # (cell1, cell2) of "Cell pin lists ... do not match"
        self.complete = False

    def __repr__(self):
        return "Verdict(matched=%s, final=%r, reasons=%r)" % (self.matched, self.final, self.reasons)


def _reason(v, text):
    if text not in v.reasons:
        v.reasons.append(text)


def parse_report(text):
    """The Verdict of a netgen report (the text file, or netgen's stdout)."""
    v = Verdict()
    lines = [ln.rstrip() for ln in text.splitlines()]
    finals = [i for i, ln in enumerate(lines) if _FINAL.match(ln.strip())]
    for ln in lines:
        s = ln.strip()
        m = _PINLIST.match(s)
        if m:
            v.pin_errors = True
            v.pin_lists.append((m.group(1), m.group(2)))
            _reason(v, s)
    if not finals:
        _reason(v, "netgen's report has no final result")
        return v
    v.complete = True
    i = finals[-1]
    final = _FINAL.match(lines[i].strip()).group(1).strip()
    j = i + 1
    if not final:
        # netgen's stdout puts the result on the next line.
        while j < len(lines) and not lines[j].strip():
            j += 1
        final = lines[j].strip() if j < len(lines) else ""
        j += 1
    v.final = final
    after = [ln.strip() for ln in lines[j:]]
    if _PORT.match(final):
        v.port_errors = True
        _reason(v, "netgen: " + final)
    elif _PROP_LINE.match(final):
        v.property_errors = True
        _reason(v, "netgen: " + final)
    elif _MATCH.match(final):
        m = _MATCH.match(final)
        v.symmetries = int(m.group(3)) if m.group(3) else 0
    elif final.startswith(_NOMATCH):
        _reason(v, "netgen: " + final)
    elif final.startswith(_PIN_FAIL):
        v.pin_errors = True
        _reason(v, "netgen: " + final)
    else:
        _reason(v, "netgen's final result is not one this plugin knows: %r" % final)
    for k, s in enumerate(after):
        if s.startswith(_PROP_FOUND):
            v.property_errors = True
            _reason(v, "netgen: " + _PROP_FOUND)
        elif s.startswith("The following cells had property errors"):
            for t in after[k + 1:]:
                if not t or t.startswith(("Final result", "The following", "Property", "Top level")):
                    break
                v.property_cells.append(t)
        elif s.startswith(_PIN_FAIL):
            v.pin_errors = True
            _reason(v, "netgen: " + _PIN_FAIL)
        elif s.startswith(_SUBCELL_FAIL) or s.startswith("The following subcells failed to match"):
            v.subcell_errors = True
            _reason(v, "netgen: " + s)
        elif _PORT.match(s):
            v.port_errors = True
            _reason(v, "netgen: " + s)
    v.matched = (bool(_MATCH.match(final)) and not v.property_errors and not v.port_errors
                 and not v.pin_errors and not v.subcell_errors)
    return v


# -- lvs.json -------------------------------------------------------------------

class Circuit:
    """One circuit pair of lvs.json. Each pair attribute is (layout,
    schematic): ``name``; ``devices`` {model: count}; ``nets`` counts;
    ``badnets`` [(layout nets, schematic nets)], each net (name, [(device,
    pins, count)]); ``badelements`` the same shape for devices;
    ``properties`` [((layout device, {prop: value}), (schematic device,
    {prop: value}))]; ``pins`` (layout list, schematic list), paired by
    position."""

    def __init__(self, raw):
        self.raw = raw
        self.name = tuple(raw.get("name") or ("", ""))
        devs = raw.get("devices") or [[], []]
        self.devices = tuple({d[0]: d[1] for d in side if len(d) >= 2} for side in devs)
        self.nets = tuple(raw.get("nets") or (None, None))
        self.badnets = [_fragment(f) for f in raw.get("badnets") or []]
        self.badelements = [_fragment(f) for f in raw.get("badelements") or []]
        self.properties = []
        for pair in raw.get("properties") or []:
            sides = []
            for side in pair:
                name = side[0] if side else ""
                props = {}
                for pv in (side[1] if len(side) > 1 else []):
                    if len(pv) >= 2:
                        props[pv[0]] = pv[1]
                sides.append((name, props))
            while len(sides) < 2:
                sides.append(("", {}))
            self.properties.append(tuple(sides[:2]))
        pins = raw.get("pins") or [[], []]
        self.pins = tuple([p for p in side if p != ""] for side in pins)
        # The rows of the report's "Subcircuit pins:" table for this pair
        # (report_pins), set by run().
        self.report_pins = []

    def pin_pairs(self):
        """[(layout pin, schematic pin)] by position; a missing side is
        "(no matching pin)" or "(no pins)". On the layout's "(no pins)" row,
        netgen's JSON gives "(no matching pin)" for the schematic pin that its
        report names ("(no pins) | VPWR **Mismatch**"): the report's name is
        used there."""
        lay, sch = self.pins
        n = max(len(lay), len(sch))
        out = []
        for i in range(n):
            lp = lay[i] if i < len(lay) else NO_PIN
            sp = sch[i] if i < len(sch) else NO_PIN
            if lp == NO_PINS and sp in (NO_PIN, NO_PINS) and i < len(self.report_pins):
                named = self.report_pins[i][1]
                if named and not named.startswith("("):
                    sp = named
            out.append((lp, sp))
        return out

    def __repr__(self):
        return "Circuit(%r)" % (self.name,)


def _fragment(frag):
    sides = []
    for side in (frag or [])[:2]:
        items = []
        for ent in side or []:
            if not ent:
                continue
            name = ent[0]
            fan = []
            for f in (ent[1] if len(ent) > 1 else []):
                if isinstance(f, list) and len(f) >= 3:
                    fan.append((f[0], f[1], f[2]))
            items.append((name, fan))
        sides.append(items)
    while len(sides) < 2:
        sides.append([])
    return tuple(sides)


def parse_json(obj):
    """[Circuit] for the circuit pairs of lvs.json (text or parsed); the
    device-class pin entries netgen writes for black boxes are left out."""
    if isinstance(obj, (str, bytes)):
        obj = json.loads(obj)
    return [Circuit(c) for c in obj if isinstance(c, dict) and "name" in c]


def read_json(path):
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    try:
        return parse_json(text)
    except ValueError as e:
        raise NetgenError("cannot read %s: %s" % (path, e))


def circuit(circuits, layout_cell, schematic_cell=None):
    """The pair whose layout side is ``layout_cell`` (and schematic side
    ``schematic_cell``), else the last pair (netgen compares the top last)."""
    for c in circuits:
        if c.name[0] == layout_cell and (schematic_cell is None or c.name[1] == schematic_cell):
            return c
    for c in circuits:
        if c.name[0] == layout_cell:
            return c
    return circuits[-1] if circuits else None


_PIN_ROW_END = re.compile(r"\s*\*\*Mismatch\*\*\s*$")


def report_pins(text):
    """{(layout cell, schematic cell): [(layout pin, schematic pin)]} from the
    report's "Subcircuit pins:" tables, the cells' text as netgen wrote it,
    without "**Mismatch**"."""
    out = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        if lines[i].strip() != "Subcircuit pins:" or i + 1 >= len(lines):
            i += 1
            continue
        head = lines[i + 1].split("|")
        names = tuple(h.strip().split(":", 1)[-1].strip() for h in head[:2])
        rows = []
        j = i + 2
        if j < len(lines) and set(lines[j].strip()) <= set("-|"):
            j += 1
        while j < len(lines) and lines[j].strip() and not set(lines[j].strip()) <= set("-"):
            parts = lines[j].split("|", 1)
            if len(parts) == 2:
                rows.append(tuple(_PIN_ROW_END.sub("", p).strip() for p in parts))
            j += 1
        if len(names) == 2:
            out[names] = rows
        i = j
    return out


# -- the schematic --------------------------------------------------------------

_SUBCKT = re.compile(r"^\s*\.subckt\s+(\S+)", re.I | re.M)


def subcircuits(path):
    """The .subckt names of a SPICE or CDL file, in file order."""
    with open(path, encoding="utf-8", errors="replace") as f:
        return _SUBCKT.findall(f.read())


# -- running ----------------------------------------------------------------------

class Result:
    def __init__(self, returncode, output, report, json_path, elapsed, verdict, circuits):
        self.returncode = returncode
        self.output = output          # netgen's stdout and stderr
        self.report = report          # the text report's path
        self.json = json_path
        self.elapsed = elapsed
        self.verdict = verdict
        self.circuits = circuits


def command(cfg, layout, layout_cell, schematic, schematic_cell, report):
    return [cfg.netgen, "-batch", "lvs", "%s %s" % (layout, layout_cell), "%s %s" % (schematic, schematic_cell),
            cfg.netgen_setup, report, "-json"]


def run(cfg, layout, layout_cell, schematic, schematic_cell, report, cwd=None, timeout=None):
    """Run netgen and read its result. Raises NetgenError when netgen can't
    start or gives no report."""
    if " " in layout or " " in schematic:
        # netgen splits each "file cell" argument at the space.
        raise NetgenError("netgen cannot read a file whose path holds a space: %s"
                          % (layout if " " in layout else schematic))
    cmd = command(cfg, layout, layout_cell, schematic, schematic_cell, report)
    t0 = time.monotonic()
    try:
        p = subprocess.run(cmd, cwd=cwd or os.path.dirname(report), stdin=subprocess.DEVNULL,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           timeout=timeout or getattr(cfg, "job_timeout", 1800))
    except OSError as e:
        raise NetgenError("cannot start netgen (%s): %s" % (cfg.netgen, e))
    except subprocess.TimeoutExpired:
        raise NetgenError("netgen timed out")
    elapsed = time.monotonic() - t0
    out = p.stdout.decode("utf-8", errors="replace")
    if not os.path.isfile(report):
        raise NetgenError("netgen wrote no report (exit status %d): %s"
                          % (p.returncode, " | ".join(out.strip().splitlines()[-3:])))
    with open(report, encoding="utf-8", errors="replace") as f:
        text = f.read()
    verdict = parse_report(text)
    json_path = os.path.splitext(report)[0] + ".json"
    circuits = read_json(json_path)
    rows = report_pins(text)
    for c in circuits:
        c.report_pins = rows.get(c.name, [])
    return Result(p.returncode, out, report, json_path, elapsed, verdict, circuits)
