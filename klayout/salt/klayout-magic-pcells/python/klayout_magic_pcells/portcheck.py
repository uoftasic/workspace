"""The port check (design-0.6.md 3.4).

Reads the user's layout in KLayout, not Magic's output (Magic rewrites pin
datatypes), and checks each cell's texts and pin boxes against the PDK's
label convention, the data file's ``ports`` table: which pairs name a net
in Magic (``text``), which make a Magic port alone (``port_text``) or over
a pin box (``pin``), which the PDK's KLayout LVS reads (``klayout_lvs_text``),
and the forms both accept (``both``).

- P1: a text that neither Magic nor the KLayout LVS reads;
- P2: a text that names a net in Magic but makes no port (netgen fails pin matching);
- P3: a Magic port that the KLayout LVS can't name;
- P4: a pin box with no text over it;
- P5: a pin box with no drawing under it, or reaching past it: Magic turns
  it into conductor, KLayout doesn't;
- P6: a text over no shape of its conductor layer, looking down the hierarchy;
- P7: texts inside device PCells on a layer KLayout's LVS reads: its flat
  LVS joins every net with that name;
- P8 (--magic): a top-level text in a pin form that is missing from the
  ports of Magic's ``.subckt`` line (an extraction of the top cell as Magic
  reads it).

P1 to P7 are pure KLayout and run without Magic. With --magic, a cell Magic
reads as empty gives P1 to P7 and the finding "Export/Magic reads nothing in
this cell" (status 1) instead of P8. ``prepare`` never raises: a failed
export gives a Task whose outcome has status 2 and says why.

    python3 -m klayout_magic_pcells ports design.gds --cell my_inv [--magic] [-o ports.lyrdb]
"""

import json
import os
import re
import sys

from ._kl import db
from . import jobs
from . import layercheck
from . import markers

CATS = {
    "P1": "P1 text neither Magic nor KLayout's LVS reads",
    "P2": "P2 text names a net in Magic but makes no port",
    "P3": "P3 Magic port KLayout's LVS can't name",
    "P4": "P4 pin box with no text",
    "P5": "P5 pin box with no drawing under it",
    "P6": "P6 text over no shape of its layer",
    "P7": "P7 texts inside device cells",
    "P8": "P8 pin missing from Magic's subcircuit ports",
}
DESC = {
    "P2": "netgen matches pins by Magic's port list: a net name that is not a port fails pin matching.",
    "P3": "Magic makes this text a port, but the PDK's KLayout LVS deck reads net names from other layers.",
    "P5": "Magic reads a pin box as conductor; KLayout's decks don't, so the two tools see different metal.",
    "P7": "KLayout's flat LVS joins every net that carries the same text; texts inside device cells join "
          "the devices' terminals with each other and with top-level nets of that name.",
}
KMP_VARIANT = re.compile(r"__kmp_[0-9a-f]{8}$")


def _pairs(xs):
    return set(tuple(x) for x in xs if x)


class Convention:
    """The data file's ports table, as sets of (layer, datatype)."""

    def __init__(self, data):
        p = data.ports() if hasattr(data, "ports") else data.get("ports", {})
        self.text = _pairs(p.get("text", []))
        # Label layers Magic reads onto a type that makes no net (sky130A's
        # text.drawing, IHP's TEXT.drawing: type comment): their texts name nothing in Magic.
        self.comment = _pairs(p.get("comment", []))
        self.port_text = _pairs(p.get("port_text", []))
        self.pin = _pairs(p.get("pin", []))
        self.kl = _pairs(p.get("klayout_lvs_text", []))
        self.both = p.get("both", [])
        self.lines = p.get("lines", {})
        self.pin_for = {}
        for b in self.both:
            if b.get("pin"):
                self.pin_for.setdefault(tuple(b["text"]), set()).add(tuple(b["pin"]))
        for t in self.text | self.port_text | self.kl:
            for q in self.pin:
                if q[0] == t[0] and q != t:
                    self.pin_for.setdefault(t, set()).add(q)
        # The text layers that name a pin box, by the pin layer: its own layer
        # number's, and the text layer of the form both accept (sky130A's
        # pwell.pin 122/16 takes its text on pwell.label 64/59).
        self.texts_for_pin = {}
        for t, qs in self.pin_for.items():
            for q in qs:
                self.texts_for_pin.setdefault(q, set()).add(t)
        rows = data.layers if hasattr(data, "layers") else data.get("layers", [])
        self.drawing = {}
        for r in rows:
            if r.get("read") == "paint" and r.get("role") in ("conductor", "poly", "diffusion", "well"):
                self.drawing.setdefault(r["gds"][0], []).append(tuple(r["gds"]))
        self.names = dict((tuple(r["gds"]), r.get("name") or "") for r in rows)
        types = dict((tuple(r["gds"]), set(r.get("magic_types") or [])) for r in rows)
        self.pin_draw = {}
        for q in self.pin:
            same = [d for d in self.drawing.get(q[0], []) if types.get(d, set()) & types.get(q, set())]
            self.pin_draw[q] = same or self.drawing.get(q[0], [])

    def both_form(self, lnum):
        for b in self.both:
            if b["text"][0] == lnum:
                if b.get("pin"):
                    return "a text on %d/%d over a box on %d/%d" % (tuple(b["text"]) + tuple(b["pin"]))
                return "a text on %d/%d" % tuple(b["text"])
        return None

    def name(self, ld):
        n = self.names.get(tuple(ld))
        return "%d/%d (%s)" % (ld[0], ld[1], n) if n else "%d/%d" % tuple(ld)


def device_cell(cell):
    """A cell that is a device PCell: a variant of the plugin's PCells, or a
    PCell or library cell of KLayout."""
    try:
        if cell.is_pcell_variant() or cell.is_library_cell():
            return True
    except Exception:
        pass
    return bool(KMP_VARIANT.search(cell.name))


def _texts(cell, li):
    for s in cell.shapes(li).each(db.Shapes.STexts):
        yield s.text


def _rec_region(layout, cell, lds, box=None):
    r = db.Region()
    for ld in lds:
        li = layout.find_layer(ld[0], ld[1])
        if li is None:
            continue
        if box is None:
            r += db.Region(cell.begin_shapes_rec(li))
        else:
            r += db.Region(cell.begin_shapes_rec_touching(li, box))
    return r.merged()


def _rec_texts(layout, cell, lds, box):
    out = []
    for ld in lds:
        li = layout.find_layer(ld[0], ld[1])
        if li is None:
            continue
        it = cell.begin_shapes_rec_touching(li, box)
        it.shape_flags = db.Shapes.STexts
        while not it.at_end():
            out.append(it.shape().text.transformed(it.trans()))
            it.next()
    return out


def check_layout(layout, top, data, magic_ports=None):
    """P1 to P7 (and P8 when ``magic_ports`` is a list) on ``top`` and every
    cell under it. Returns [{"check", "cell", "layer", "box" (DBox, um,
    in that cell), "text"}]. A text on a ``comment`` layer of the ports
    table names nothing in Magic and is no finding."""
    conv = Convention(data)
    dbu = layout.dbu
    cells = [top] + [layout.cell(ci) for ci in top.called_cells()]
    out = []
    text_layers = conv.text | conv.port_text | conv.kl | conv.pin
    all_text_layers = set()
    for li in layout.layer_indexes():
        info = layout.get_info(li)
        all_text_layers.add((info.layer, info.datatype))

    def add(check, cell, ld, box, text, name=None):
        out.append({"check": check, "cell": cell.name, "layer": "%d/%d" % tuple(ld), "box": box, "text": text,
                    "name": name})

    p7 = {}
    for cell in cells:
        dev = device_cell(cell) and cell is not top
        for ld in sorted(all_text_layers):
            li = layout.find_layer(ld[0], ld[1])
            for t in _texts(cell, li):
                p = t.position()
                at = db.Box(p.x - 1, p.y - 1, p.x + 1, p.y + 1)
                dbox = db.DBox(p.x * dbu, p.y * dbu, p.x * dbu, p.y * dbu)
                s = t.string
                where = "%s %s at (%.3f, %.3f)" % ("text", repr(s), p.x * dbu, p.y * dbu)
                if dev:
                    if ld in conv.kl:
                        p7.setdefault(s, []).append((cell, ld, dbox))
                    continue
                pins = conv.pin_for.get(ld, set())
                over_pin = bool(pins) and not _rec_region(layout, cell, pins, at).is_empty()
                port = ld in conv.port_text or (ld in conv.text and over_pin) or (ld in conv.kl and over_pin
                                                                                   and ld in conv.text)
                names = ld in conv.text or port
                kl = ld in conv.kl
                form = conv.both_form(ld[0])
                advice = (" The form both accept is %s." % form) if form else ""
                if not names and not kl:
                    if ld in text_layers or ld[0] in conv.drawing:
                        add("P1", cell, ld, dbox, "%s on %s: Magic does not read it as a net name or port, and "
                            "KLayout's LVS does not read it.%s" % (where, conv.name(ld), advice), s)
                    continue
                if names and not port:
                    add("P2", cell, ld, dbox, "%s on %s names a net in Magic but makes no port, so netgen "
                        "fails pin matching%s.%s" % (where, conv.name(ld),
                                                    "" if kl else "; KLayout's LVS does not read it either",
                                                    advice), s)
                elif port and not kl:
                    add("P3", cell, ld, dbox, "%s on %s is a port in Magic, but KLayout's LVS reads net names "
                        "from other layers and can't name it.%s" % (where, conv.name(ld), advice), s)
                cond = conv.drawing.get(ld[0], []) + sorted(pins)
                if cond and _rec_region(layout, cell, cond, at).is_empty():
                    add("P6", cell, ld, dbox, "%s on %s is over no shape of layer %d: it names nothing in "
                        "Magic or KLayout." % (where, conv.name(ld), ld[0]), s)
                if magic_ports is not None and cell is top and port and s not in magic_ports:
                    add("P8", cell, ld, dbox, "%s on %s is in a pin form, but Magic's .subckt line for %s has "
                        "no port %s." % (where, conv.name(ld), top.name, s), s)
        if dev:
            continue
        for ld in sorted(conv.pin):
            li = layout.find_layer(ld[0], ld[1])
            if li is None:
                continue
            draw = conv.pin_draw.get(ld, [])
            text_lds = sorted(set([x for x in text_layers if x[0] == ld[0]] + [ld])
                              | conv.texts_for_pin.get(ld, set()))
            for poly in db.Region(cell.shapes(li)).merged().each():
                b = poly.bbox()
                dbox = db.DBox(b.left * dbu, b.bottom * dbu, b.right * dbu, b.top * dbu)
                if not _rec_texts(layout, cell, text_lds, b):
                    add("P4", cell, ld, dbox, "pin box on %s at %s has no text over it: neither tool names it."
                        % (conv.name(ld), layercheck._boxtext(dbox)))
                if draw:
                    left = db.Region(poly) - _rec_region(layout, cell, draw, b)
                    if not left.is_empty():
                        add("P5", cell, ld, dbox, "pin box on %s at %s has no %s drawing under %.4f um2 of it: "
                            "Magic turns the box into conductor, KLayout doesn't." % (
                                conv.name(ld), layercheck._boxtext(dbox),
                                " or ".join("%d/%d" % x for x in draw), left.area() * dbu * dbu))
    for s, where in sorted(p7.items()):
        for cell, ld, dbox in where:
            add("P7", cell, ld, dbox, "text %r on %s inside the device cell %s: KLayout's flat LVS joins every "
                "net named %r (%d such texts in device cells). Turn the PCell's doports parameter off "
                "(doports 0) so the device carries no texts." % (s, conv.name(ld), cell.name, s, len(where)), s)
    return out


# -- Magic's port list (P8) ---------------------------------------------------------

def subckt_ports(spice_path, top):
    """The port names of ``.subckt top`` in a SPICE file, or None."""
    with open(spice_path, encoding="utf-8", errors="replace") as f:
        lines = f.read().splitlines()
    joined = []
    for ln in lines:
        if ln.startswith("+") and joined:
            joined[-1] += " " + ln[1:]
        else:
            joined.append(ln)
    for ln in joined:
        t = ln.split()
        if len(t) >= 2 and t[0].lower() == ".subckt" and t[1] == top:
            return [x for x in t[2:] if "=" not in x]
    return None


class Outcome(layercheck.Outcome):
    pass


_PLAIN = {
    "P1": ("text that neither Magic nor KLayout's LVS reads", "texts that neither Magic nor KLayout's LVS reads"),
    "P2": ("text that names a net in Magic but makes no pin", "texts that name nets in Magic but make no pins"),
    "P3": ("pin in Magic that KLayout's LVS can't name", "pins in Magic that KLayout's LVS can't name"),
    "P4": ("pin box with no text", "pin boxes with no text"),
    "P5": ("pin box with no drawing under it", "pin boxes with no drawing under them"),
    "P6": ("text over no shape of its layer", "texts over no shape of their layer"),
    "P7": ("text inside a device cell", "texts inside device cells"),
    "P8": ("pin missing from Magic's subcircuit", "pins missing from Magic's subcircuit"),
}


def headline(found, cell):
    """The first line of the GUI's result message, in plain words: the
    findings per check, with the texts they are about, or that there are
    none."""
    parts = []
    for k in sorted(CATS):
        items = [f for f in found if f["check"] == k]
        if not items:
            continue
        one, many = _PLAIN[k]
        part = "%d %s" % (len(items), one if len(items) == 1 else many)
        names = []
        for f in items:
            if f.get("name") and f["name"] not in names:
                names.append(f["name"])
        if names and k != "P7":
            part += " (%s%s)" % (", ".join(names[:6]), ", ..." if len(names) > 6 else "")
        parts.append(part)
    if not parts:
        return "No port findings in %s." % cell
    return "In %s: %s." % (cell, "; ".join(parts))


class Task(layercheck.RwTask):
    """The ports check of one cell; with options["magic"] it also runs the
    extraction job for P8."""

    def __init__(self, layout, cell, cfg, data, options):
        options = options or {}
        self.magic = bool(options.get("magic"))
        layercheck.RwTask.__init__(self, layout, cell, cfg, data, options, mode="ports")
        self.params = {"cmd": "ports", "file": options.get("file", ""), "cell": self.cell_name,
                       "magic": "1" if self.magic else "0"}
        self.command = options.get("command") or "ports %s --cell %s" % (options.get("file", "<layout>"),
                                                                       self.cell_name)
        if self.magic and self.early is None and self.er is not None:
            self.early = self.er.refusal()
        self.early_outcome()

    def _rdb(self):
        pdk = getattr(self.data, "pdk", None) or getattr(self.cfg, "pdk", "?")
        return layercheck._new_rdb("ports", "Port check", self.cell_name, pdk, self.params, self.command)

    def reads_nothing(self, result):
        """Magic read the cell as empty, so there is no port list for P8:
        P1 to P7 and the finding, status 1."""
        out = self._result(None, dict(layercheck.job_files(result.dir)))
        text = markers.add_reads_nothing(out.rdb, self.er, cell_name=self.cell.name, data=self.data)
        markers.add_magic_said(out.rdb, self.magic_lines(result))
        out.findings["empty"] = [{"check": "empty", "cell": self.cell.name, "layer": None, "box": self.er.bbox,
                                  "text": text}]
        out.status = 1
        out.summary += "; %s, so P8 did not run (category %s)" % (text, markers.CAT_READS_NOTHING)
        return out

    def start(self):
        if self._outcome is not None:
            self._started = True
            return self
        if not self.magic:
            self._started = True
            self._outcome = self._result(None)
            return self
        return layercheck.RwTask.start(self)

    def fail(self, why, result=None):
        return self.failed("ports", why, result)

    def finish(self, job_dir, scale, stdout):
        spice = os.path.join(job_dir, "%s.spice" % self.er.top)
        ports = subckt_ports(spice, self.er.top)
        if ports is None:
            return self.fail("Magic's netlist %s has no .subckt %s" % (spice, self.er.top))
        return self._result(ports, dict(layercheck.job_files(job_dir), spice=spice))

    def _result(self, ports, files=None):
        found = check_layout(self.layout, self.cell, self.data, ports)
        rdb = self._rdb()
        fill_rdb(rdb, found, self.layout)
        counts = {}
        for f in found:
            counts[f["check"]] = counts.get(f["check"], 0) + 1
        summary = "ports on %s, cell %s: %s" % (self.data.pdk, self.cell.name,
                                                ", ".join("%s %d" % (k, counts.get(k, 0)) for k in sorted(CATS)
                                                          if k != "P8" or ports is not None))
        if ports is not None:
            summary += "; Magic's ports: %s" % (" ".join(ports) or "none")
        out = Outcome(1 if found else 0, rdb, summary, files or {}, {"ports": found},
                      headline=headline(found, self.cell.name))
        out.magic_ports = ports
        if not self.magic:
            self.cleanup()
        return out


def fill_rdb(rdb, found, layout=None):
    for f in found:
        cat = rdb.category((CATS[f["check"]],), DESC.get(f["check"], ""))
        rdb.item(cat, f["cell"], f["box"], f["text"])
    # Items in subcells need their placements for the browser to show them in
    # the top cell (design-0.6.md 2.7).
    if layout is not None and hasattr(markers, "add_parent_references"):
        try:
            markers.add_parent_references(rdb, layout)
        except (TypeError, RuntimeError, AttributeError):
            pass


def prepare(layout, cell, cfg, data, options):
    return Task(layout, cell, cfg, data, options)


def cli_main(args, ctx):
    cell = ctx.cells[0]
    cmd = "python3 -m klayout_magic_pcells ports %s --cell %s --pdk %s%s" % (
        ctx.file, cell.name, ctx.pdk, " --magic" if getattr(args, "magic", False) else "")
    # prepare() does not raise: a failed export is an outcome with status 2.
    task = prepare(ctx.layout, cell, ctx.cfg, ctx.data,
                   {"magic": getattr(args, "magic", False), "file": ctx.file, "command": cmd})
    out = task.wait()
    try:
        if getattr(args, "output", None):
            out.rdb.save(args.output)
        found = out.findings.get("ports", [])
        if getattr(args, "json", None):
            with open(args.json, "w", encoding="utf-8") as f:
                json.dump({"schema": 1, "pdk": ctx.pdk, "file": ctx.file, "cell": cell.name, "status": out.status,
                           "summary": out.summary, "magic_ports": getattr(out, "magic_ports", None),
                           "magic_reads_nothing": [x["text"] for x in out.findings.get("empty", [])],
                           "findings": [{"check": x["check"], "cell": x["cell"], "layer": x["layer"],
                                         "at": [round(x["box"].left, 4), round(x["box"].bottom, 4)],
                                         "text": x["text"]} for x in found]}, f, indent=1)
                f.write("\n")
        sys.stderr.write(out.summary + "\n")
        for x in found:
            sys.stdout.write("%s %s: %s\n" % (x["check"], x["cell"], x["text"]))
    finally:
        jobs.release(out)
    return out.status
