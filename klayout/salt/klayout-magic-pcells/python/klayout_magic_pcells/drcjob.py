"""Magic's DRC from KLayout: the ``drc`` command and the GUI's Run Magic DRC.

``prepare()`` exports the cell (``export.export_cell``), ``Task`` runs
``tcl/kmp_drc.tcl`` in Magic jobs and ``Outcome`` holds a report database
for the Marker Database Browser. The command line and the GUI share this
code path (the task API, design-0.6.md 2.4).

Two modes (design-0.6.md 3.1; 6.1 says why hierarchical is the default):

- **hierarchical** (the default): the export keeps the hierarchy, Magic
  reads it with a plain ``gds read``, and every cell definition is checked
  as the edit cell, children first, then the top cell. Each cell's errors
  are in that cell's coordinates and go into its own RDB cell. The top
  cell keeps every box of its own check. Below it, a box listed under a
  parent that equals a box of one of its subcells, seen through the
  instance, is dropped from the parent (the copy drop, design-0.6.md 3.1):
  the parent's check lists most of the subcells' errors again.

  A subcell checked on its own can list boxes its context removes (a met1
  area error on a PCell's gate pad that the parent's metal joins) and boxes
  that Magic's check from the top cell misses although they are real (the
  case suite's sheet, design-0.6.md 3.1). So every box of a cell other than
  the top is classified (``classify``): (a) the top cell's listing has a
  box of its rule there, through some placement: the top cell's box
  reports it, and the subcell's is left out; (b) else, when Magic's check
  of the flattened layout has one there: an error in the subcell, and its
  text says so; (c) else information only, in the category "only when
  <cell> is checked on its own" under the rule, not counted in the exit
  status or the error count. The flattened check is one more job (flat
  mode's options, on the export read back and flattened), run only when
  some box is not (a). The top cell keeps every box of its own check,
  so a tap that the top cell lacks gives its errors there (design-0.6.md
  3.1).
- **flat**: Magic's verdict on the flattened mask. The export flattens the
  cell and Magic checks that one cell.

Magic's error list has no layer, so each item's text names the Magic types
that the rule statements with that why-text check, and the GDS layers the
gdsii style writes them on (design-0.6.md 3.1). A rule names its types by alias
(allm1) and by any of their synonyms (m1); the gdsii style names a type by
its first name in the tech file's types section (metal1). Both are read
from the tech files at run time (``tech_aliases``, ``tech_types``).
Categories: one per why-text, grouped under its rule ID, the text in the
why-text's last parentheses as the harness takes it; a why-text
without an ID is a category of its own.

A top cell that Magic reads as empty (every layer it draws is one Magic's
reader ignores or reads only to decide device types) is a finding, not a
failed job: "Export/Magic reads nothing in this cell", status 1. Subcells
Magic reads as empty are skipped and listed in ``Outcome.empty``.

``box`` (an area, in µm, in the top cell's coordinates) keeps the errors of
the whole-cell check that touch it; Magic still checks the whole cell
(no halo and no tiles, design-0.6.md 6.4), and the job cache makes the next area
check of an unchanged layout free.
"""

import json
import os
import re
import shutil
import sys
import tempfile

from . import jobs

# markers and export need the klayout module; they are imported where they
# are used, so that the pure helpers here load without it.
CAT_EXPORT = "Export"

SCRIPT = "kmp_drc.tcl"
MODES = ("hierarchical", "flat")
CAT_DRC = "Magic DRC"
CAT_FAILED = "Magic DRC did not run"
RESULT = "kmp_drc.json"          # a finished batch's record in its job directory
M1_NOTE = ("this mode checks every cell and then the top cell; Magic's check from the top cell "
           "alone can report fewer errors")
FLAT_NOTE = "Magic's verdict on the flattened mask"
GAPS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
TSV_HEADER = "cell\trule\twhy\tl\tb\tr\tt"

_RULE_RE = re.compile(r"\(([^()]*)\)\s*$")
_MAGIC_VERSION = re.compile(r"^Magic (\d+(?:\.\d+)*) revision (\d+)")
# What Magic prints on every run; the rest goes under "Magic said".
_NOISE = (re.compile(r"^Warning: Calma reading is not undoable"),
          re.compile(r"^Library (written using|name:)"),
          re.compile(r'^Reading "'),
          re.compile(r"^DRC style is now"),
          re.compile(r"^Loading DRC CIF style"),
          re.compile(r"^\d+ Magic internal units = "),
          re.compile(r"^(Input|Output) style "),
          re.compile(r"^Scaled tech values by"),
          re.compile(r"^No errors found\.$"))


# -- small pure helpers (unit-tested without Magic) -------------------------------

def rule_id(why):
    """The rule ID of a why-text: the text in its last parentheses, as
    tests/parity/drc.py takes it ("licon.9 + psdm.5a", "Grid Rules"), else
    the whole why-text (also for "()")."""
    w = why.strip()
    m = _RULE_RE.search(w)
    rid = m.group(1).strip() if m else ""
    return rid or w


def category_path(why):
    """The RDB category of a why-text: (CAT_DRC, rule ID, why-text), or
    (CAT_DRC, why-text) when it has no ID."""
    rid = rule_id(why)
    return (CAT_DRC, why) if rid == why.strip() else (CAT_DRC, rid, why)


def nm_per_unit(scale):
    """nm per Magic unit from ``[cif scale out]`` (µm per unit, printed as
    0.004999999888241291): 5.0, rounded so that whole units stay whole."""
    return round(float(scale) * 1000.0, 6)


def to_nm(value, scale):
    """A Magic coordinate in nm (an int)."""
    return int(round(float(value) * nm_per_unit(scale)))


def fmt_um(nm):
    """nm as µm text: 1350 -> "1.35", -500 -> "-0.5", 0 -> "0"."""
    s = "%.3f" % (nm / 1000.0)
    s = s.rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def touches(box, area):
    """Boxes (l, b, r, t) that overlap or share an edge or a corner."""
    return box[0] <= area[2] and box[2] >= area[0] and box[1] <= area[3] and box[3] >= area[1]


class Xf:
    """An orthogonal transformation in integer nm: a 2x2 matrix of 0 and ±1
    (rotations by multiples of 90°, mirrors) and a displacement. The export
    flattens every other instance (design-0.6.md 2.6), so these are all Magic
    can place."""

    __slots__ = ("m", "d")

    def __init__(self, m=(1, 0, 0, 1), d=(0, 0)):
        self.m = tuple(m)
        self.d = tuple(d)

    @classmethod
    def from_klayout(cls, t):
        """From a DCplxTrans (µm): angle a multiple of 90°, no magnification."""
        a = int(round(t.angle / 90.0)) % 4
        c, s = ((1, 0), (0, 1), (-1, 0), (0, -1))[a]
        my = -1 if t.is_mirror() else 1
        # R(a) * diag(1, my)
        m = (c, -s * my, s, c * my)
        return cls(m, (int(round(t.disp.x * 1000)), int(round(t.disp.y * 1000))))

    def point(self, x, y):
        a, b, c, d = self.m
        return a * x + b * y + self.d[0], c * x + d * y + self.d[1]

    def box(self, box):
        x1, y1 = self.point(box[0], box[1])
        x2, y2 = self.point(box[2], box[3])
        return (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))

    def __mul__(self, o):
        """self after o."""
        a, b, c, d = self.m
        e, f, g, h = o.m
        m = (a * e + b * g, a * f + b * h, c * e + d * g, c * f + d * h)
        dx, dy = self.point(*o.d)
        return Xf(m, (dx, dy))

    def __eq__(self, o):
        return isinstance(o, Xf) and self.m == o.m and self.d == o.d

    def __hash__(self):
        return hash((self.m, self.d))

    def __repr__(self):
        return "Xf(%r, %r)" % (self.m, self.d)


class Error:
    """One error box Magic listed: the cell (its name in the exported file),
    the why-text and the box in nm, in that cell's coordinates."""

    __slots__ = ("cell", "why", "box")

    def __init__(self, cell, why, box):
        self.cell = cell
        self.why = why
        self.box = tuple(box)

    @property
    def rule(self):
        return rule_id(self.why)

    def key(self):
        return (self.why, self.box)

    def __eq__(self, o):
        return isinstance(o, Error) and (self.cell, self.why, self.box) == (o.cell, o.why, o.box)

    def __hash__(self):
        return hash((self.cell, self.why, self.box))

    def __repr__(self):
        return "Error(%r, %r, %r)" % (self.cell, self.why, self.box)


def dedup(raw, children, order, keep=()):
    """The copy drop: drop from each cell the boxes that equal a box of one of its
    subcells (at any depth), seen through the instances. The cells in ``keep``
    (the top cell) keep all their boxes.

    ``raw``: {cell: [Error]}; ``children``: {cell: [(child, Xf)]}, one entry
    per placement; ``order``: every cell, children before parents. Returns
    ({cell: [Error kept]}, number dropped)."""
    full = {}
    kept = {}
    dropped = 0
    for c in order:
        below = set()
        for ch, xf in children.get(c, ()):
            for why, box in full.get(ch, ()):
                below.add((why, xf.box(box)))
        mine = raw.get(c, [])
        k = list(mine) if c in keep else [e for e in mine if e.key() not in below]
        dropped += len(mine) - len(k)
        kept[c] = k
        full[c] = below | {e.key() for e in mine}
    for c, errs in raw.items():
        if c not in kept:
            kept[c] = list(errs)
    return kept, dropped


def placements(children, top, order):
    """{cell: [Xf from the cell to ``top``]}, one per placement; ``order``
    children before parents, as for dedup()."""
    out = {top: [Xf()]}
    for c in reversed(order):
        for ch, xf in children.get(c, ()):
            out.setdefault(ch, []).extend(p * xf for p in out.get(c, ()))
    return out


def in_area(errors_by_cell, places, area):
    """The errors of which some placement touches ``area`` (nm, top frame)."""
    out = {}
    for c, errs in errors_by_cell.items():
        ps = places.get(c, ())
        out[c] = [e for e in errs if any(touches(p.box(e.box), area) for p in ps)]
    return out


# The classes of a box in hierarchical mode. A subcell's own check (the cell
# as the edit cell, on its own) can list boxes that its context removes, for
# example a met1 area error on a pad that the parent's metal joins, and boxes
# that Magic's check from the top cell misses although they are real. So each
# box of a cell other than the top is classified:
TOP = "top"              # a box of the top cell's own check
IN_TOP = "in top"        # (a) the top cell's check lists it too: the top's box reports it
FLAT_ONLY = "flat only"  # (b) only the flattened layout's check confirms it: an error
ALONE = "alone"          # (c) neither does: information, not an error


class BoxIndex:
    """Error boxes (nm) by rule ID on a coarse grid: ``hit(rule, box)`` is
    True when a box of that rule overlaps or touches ``box``. Magic tiles an
    error region differently from the top cell than in the cell itself
    (sky130A diff/tap.10: 21 boxes from the top, 17 from the cells;
    design-0.6.md 3.1), so a box counts as listed when a box of its rule
    meets it, not only when one equals it. Touching is enough: in doubt, a
    subcell's box counts as listed, and the top cell's box that touches it
    stays in the report."""

    STEP = 5000
    SPAN = 64        # boxes wider than this many steps are kept in a list

    def __init__(self, errors=()):
        self._grid = {}
        self._big = {}
        for e in errors:
            self.add(e.rule, e.box)

    def _cells(self, box):
        s = self.STEP
        return range(box[0] // s, box[2] // s + 1), range(box[1] // s, box[3] // s + 1)

    def add(self, rule, box):
        xs, ys = self._cells(box)
        if len(xs) > self.SPAN or len(ys) > self.SPAN:
            self._big.setdefault(rule, []).append(box)
            return
        for x in xs:
            for y in ys:
                self._grid.setdefault((rule, x, y), []).append(box)

    def hit(self, rule, box):
        if any(touches(b, box) for b in self._big.get(rule, ())):
            return True
        xs, ys = self._cells(box)
        if len(xs) > self.SPAN or len(ys) > self.SPAN:
            return any(touches(b, box) for (r, _, _), bs in self._grid.items() if r == rule for b in bs)
        for x in xs:
            for y in ys:
                if any(touches(b, box) for b in self._grid.get((rule, x, y), ())):
                    return True
        return False


def classify(kept, top, top_listing, places, flat=None):
    """The class of every box in hierarchical mode: {cell: [(Error, class)]}.

    ``kept``: {cell: [Error]} after the copy drop (and the area filter), in
    each cell's coordinates; ``top_listing``: the top cell's own check before
    the copy drop, in the
    top's coordinates; ``places``: placements(); ``flat``: the flattened
    layout's boxes, or None before that check has run. A subcell's box is
    IN_TOP when the top's listing has a box of its rule that overlaps or
    touches it through some placement, else FLAT_ONLY when the flat check
    has one, else ALONE; it is None while ``flat`` is None and it is not
    IN_TOP. A box of a cell with no placement under the top stays an error
    (IN_TOP), as before this check."""
    in_top = BoxIndex(top_listing)
    in_flat = BoxIndex(flat) if flat is not None else None
    out = {}
    for c, errs in kept.items():
        if c == top:
            out[c] = [(e, TOP) for e in errs]
            continue
        ps = places.get(c) or ()
        res = []
        for e in errs:
            boxes = [p.box(e.box) for p in ps]
            if not boxes or any(in_top.hit(e.rule, b) for b in boxes):
                cls = IN_TOP
            elif in_flat is None:
                cls = None
            elif any(in_flat.hit(e.rule, b) for b in boxes):
                cls = FLAT_ONLY
            else:
                cls = ALONE
            res.append((e, cls))
        out[c] = res
    return out


def class_counts(classes):
    """{class: boxes} over classify()'s result, the top cell's included."""
    out = {TOP: 0, IN_TOP: 0, FLAT_ONLY: 0, ALONE: 0}
    for res in classes.values():
        for _, cls in res:
            if cls in out:
                out[cls] += 1
    return out


def alone_category(why, cell):
    """The category of a box only cell ``cell`` checked on its own gives:
    under the why-text's rule ID (under the why-text when it has none)."""
    return category_path(why)[:2] + ("only when %s is checked on its own" % cell,)


ALONE_NOTE = ("Magic's check of the cell as the edit cell, on its own, lists these boxes; Magic's check "
              "from the top cell does not, and neither does its check of the flattened layout. The "
              "cell's surroundings in the layout complete what it lacks on its own (for example metal "
              "in a parent that joins a small pad, or a tap or well in another cell). Information "
              "only: they are not counted as errors and do not change the exit status.")
FLAT_ONLY_TEXT = ("Magic's check from the top cell misses this box; Magic's check of the flattened layout "
                  "confirms it")


def area_nm(box):
    """An area in µm, (l, b, r, t) or "l,b,r,t", in nm."""
    if isinstance(box, str):
        box = [float(v) for v in box.split(",")]
    l, b, r, t = [int(round(float(v) * 1000)) for v in box]
    if not (l < r and b < t):
        raise ValueError("an area needs l < r and b < t, not %r" % (box,))
    return (l, b, r, t)


def tsv_rows(rows):
    """Lines of the --tsv file: a header, then cell, rule ID, why-text and
    l b r t in µm. ``rows``: (cell, why, (l, b, r, t) in nm)."""
    out = [TSV_HEADER]
    for cell, why, box in rows:
        out.append("\t".join([cell, rule_id(why), why] + [fmt_um(v) for v in box]))
    return out


def write_tsv(path_or_file, rows):
    text = "\n".join(tsv_rows(rows)) + "\n"
    if hasattr(path_or_file, "write"):
        path_or_file.write(text)
        return
    with open(path_or_file, "w", encoding="utf-8") as f:
        f.write(text)


def parse_cell_tsv(path, scale):
    """[Error] from one drc_<i>.tsv (Magic units) of a job."""
    out = []
    try:
        f = open(path, encoding="utf-8", errors="replace")
    except OSError:
        return out
    with f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 6:
                continue
            cell, why = parts[0], parts[1]
            try:
                box = [to_nm(v, scale) for v in parts[2:6]]
            except ValueError:
                continue
            out.append(Error(cell, why, (min(box[0], box[2]), min(box[1], box[3]),
                                         max(box[0], box[2]), max(box[1], box[3]))))
    return out


def magic_said(stdout, stderr=""):
    """The lines Magic printed after it started the job script, without the
    protocol lines and what it prints on every run."""
    lines = list(stdout) + (stderr.splitlines() if stderr else [])
    start = 0
    for i, ln in enumerate(lines):
        if ln.startswith("Loading \"") and "from command line" in ln:
            start = i + 1
            break
    return [ln.strip() for ln in lines[start:] if not is_noise(ln)]


def is_noise(line):
    """A protocol line, an empty one, or one Magic prints on every run. Also
    applied to the lines a cached batch recorded, which an older version
    may have kept."""
    s = line.strip()
    return not s or s.startswith("KMP_JOB") or any(p.search(s) for p in _NOISE)


def magic_version(stdout, stderr=""):
    for ln in list(stdout) + (stderr.splitlines() if stderr else []):
        m = _MAGIC_VERSION.match(ln.strip())
        if m:
            return "%s.%s" % (m.group(1), m.group(2))
    return None


# -- the PDK data: descriptions and item texts --------------------------------------

_gaps_memo = {}


def load_gaps(pdk, path=None):
    """pkg/data/gaps-<pdk>.json's "rules" (one entry per row of the gap
    table, tools/build_gaps.py pkg_json), or {} when the file is missing."""
    path = path or os.path.join(GAPS_DIR, "gaps-%s.json" % pdk)
    if path in _gaps_memo:
        return _gaps_memo[path]
    try:
        with open(path, encoding="utf-8") as f:
            rules = json.load(f).get("rules", {}) or {}
    except (OSError, ValueError, AttributeError):
        rules = {}
    _gaps_memo[path] = rules
    return rules


def gap_rows(gaps, why, statements=()):
    """The gap table's rows for a why-text: the entries whose "lines" hold
    one of its statements' tech-file lines ("file:line"), in the
    statements' order. One printed ID can have statements in several rows
    (IHP's AFil.i), and one statement can check two rules (a split ID), so
    the line, not the ID, finds the row. Where no entry holds a line (no
    statements, or a file whose entries are keyed by printed ID, before
    0.6.1), the entries named by the rule ID, the why-text, or the
    statements' IDs and why-texts."""
    g = gaps or {}
    by_line = {}
    for row in g.values():
        if isinstance(row, dict):
            for fl in row.get("lines") or []:
                by_line.setdefault(str(fl), []).append(row)
    out = []
    for r in statements:
        for row in by_line.get("%s:%s" % (r.get("file", ""), r.get("line")), []):
            if all(row is not x for x in out):
                out.append(row)
    if out:
        return out
    keys = [rule_id(why), why]
    for r in statements:
        keys += list(r.get("ids", [])) + [r.get("why", "")]
    for k in keys:
        row = g.get(k)
        if row is not None and row not in out:
            out.append(row)
    return out


_TYPE_SPLIT = re.compile(r"[,()]")


def type_names(types):
    """The Magic type names in rule statements' type lists: "*poly",
    "(allcont)/a", "xhrpoly,uhrpoly,xpc" -> poly, allcont, xhrpoly, ..."""
    out = []
    for t in types:
        for part in _TYPE_SPLIT.split(t):
            part = part.strip().lstrip("*~!").split("/")[0].strip()
            if part and part not in out:
                out.append(part)
    return out


class RuleInfo:
    """What the PDK data says about one why-text: the rule statements, the
    types they check, the GDS layers those types are written on, and the
    gap table's row."""

    def __init__(self, data, why, gaps=None, aliases=None, synonyms=None):
        self.why = why
        self.rule = rule_id(why)
        self.statements = []
        if data is not None:
            try:
                self.statements = list(data.rules_by_why(why))
            except Exception:
                self.statements = []
        types = []
        for r in self.statements:
            types += r.get("types", [])
        self.types = type_names(types)
        self.layers = []
        cifout = getattr(data, "cifout", None) or {}
        names = {}
        for row in getattr(data, "layers", None) or []:
            names[tuple(row["gds"])] = row.get("name")
        syn = synonyms or {}
        for t in self.types:
            for name in [t] + list((aliases or {}).get(t, [])):
                # cifout is keyed by the type's first name in the tech file's
                # types section; a rule may name it by a synonym (m1 for metal1).
                for key in (name, syn.get(name)):
                    for pair in cifout.get(key, []) if key else []:
                        p = (int(pair[0]), int(pair[1]))
                        if p not in self.layers:
                            self.layers.append(p)
        self.layer_names = names
        self._text = None
        self.styles = []
        for r in self.statements:
            for s in r.get("styles", []):
                if s not in self.styles:
                    self.styles.append(s)
        self.gaps = gap_rows(gaps, why, self.statements)

    def layer_text(self):
        parts = []
        for l, d in self.layers:
            n = self.layer_names.get((l, d))
            parts.append("%d/%d (%s)" % (l, d, n) if n else "%d/%d" % (l, d))
        return ", ".join(parts)

    def item_text(self):
        """The text of every item of this why-text (design-0.6.md 3.1)."""
        if self._text is not None:
            return self._text
        t = self.why
        if self.types:
            t += "; Magic types: " + ", ".join(self.types)
        if self.layers:
            t += "; GDS layers: " + self.layer_text()
        self._text = t
        return t

    def description(self):
        lines = ["Magic: %s" % self.why]
        styles = [s for s in self.styles if s.startswith("drc(")]
        if styles:
            lines.append("In the styles: %s%s" % (", ".join(styles),
                                                   " (drc(full) only)" if styles == ["drc(full)"] else ""))
        for r in self.statements:
            v = r.get("value_um")
            val = "" if v is None else " %g %s" % (v, r.get("unit") or "um")
            lines.append("Tech file %s:%s: %s %s%s" % (r.get("file", "?"), r.get("line", "?"),
                                                      r.get("keyword", ""), " ".join(r.get("types", [])), val))
        if not self.statements:
            lines.append("The PDK data has no rule statement with this why-text.")
        if self.types:
            lines.append("Magic types: %s" % ", ".join(self.types))
        if self.layers:
            lines.append("GDS layers: %s" % self.layer_text())
        named = {self.rule, self.why} | {r.get("why", "") for r in self.statements}
        for row in self.gaps:
            kl = []
            for k in row.get("klayout", []) or []:
                v = k.get("value")
                kl.append("%s: %s%s" % (k.get("deck", "?"), k.get("name", "?"),
                                        "" if v in (None, "") else " (%s)" % v))
            # The row's key where it is not the ID Magic prints (a statement
            # joined to another rule, or one of two rules a statement checks).
            key = row.get("key")
            lines.append("Gap table: %s%s%s" % (row.get("status", "?"),
                                                " (row %s)" % key if key and key not in named else "",
                                                "; KLayout: " + "; ".join(kl) if kl else ""))
        return "\n".join(lines)


_tech_memo = {}


def _tech_tables(data, cfg):
    """({alias: [types]}, {type name: its first name}) from the aliases and
    types sections of the PDK's tech files next to the rcfile, read at run
    time; empty when they can't be read. Memoised per file set."""
    src = getattr(data, "source", None) or {}
    files = src.get("tech_files") or ([os.path.basename(src["tech"])] if src.get("tech") else [])
    techdir = os.path.dirname(getattr(cfg, "magicrc", "") or "")
    key = (techdir, tuple(files))
    if key in _tech_memo:
        return _tech_memo[key]
    aliases, synonyms = {}, {}
    for name in files:
        try:
            with open(os.path.join(techdir, name), encoding="utf-8", errors="replace") as f:
                text = f.read()
        except OSError:
            continue
        section = None
        for line in text.splitlines():
            s = line.split("#", 1)[0].strip()
            if not s:
                continue
            if section is None:
                if s in ("aliases", "types"):
                    section = s
                continue
            if s == "end":
                section = None
                continue
            parts = s.split()
            if len(parts) < 2:
                continue
            if section == "aliases":
                aliases[parts[0]] = type_names([parts[1]])
            else:
                # "  well nwell,nw" or " -well obswell": a plane, then the
                # type's names, the first of which the other sections use.
                names = [n for n in parts[1].split(",") if n]
                for n in names:
                    synonyms.setdefault(n, names[0])
    _tech_memo[key] = (aliases, synonyms)
    return aliases, synonyms


def tech_aliases(data, cfg):
    """{alias: [types]} from the data file's "aliases" when it has one, else
    from the aliases sections of the tech files next to the rcfile, read at
    run time; {} when neither can be read. Nested aliases are expanded."""
    raw = getattr(data, "raw", None)
    if isinstance(raw, dict) and isinstance(raw.get("aliases"), dict):
        table = {k: list(v) for k, v in raw["aliases"].items()}
    else:
        table = _tech_tables(data, cfg)[0]
    out = {}
    for k in table:
        seen, todo, flat = set(), list(table[k]), []
        while todo:
            t = todo.pop(0)
            if t in seen:
                continue
            seen.add(t)
            if t in table and t != k:
                todo += table[t]
            elif t not in flat:
                flat.append(t)
        out[k] = flat
    return out


def tech_types(data, cfg):
    """{type name: the type's first name} from the data file's "synonyms"
    when it has one, else from the types sections of the tech files next to
    the rcfile ("metal1 metal1,m1,met1": m1 and met1 are metal1, the name the
    gdsii style and the data file's cifout use); {} when neither can be read."""
    raw = getattr(data, "raw", None)
    if isinstance(raw, dict) and isinstance(raw.get("synonyms"), dict):
        return dict(raw["synonyms"])
    return dict(_tech_tables(data, cfg)[1])


def drc_styles(data):
    """The PDK's drc(...) styles (gf180mcuD also lists a style "empty")."""
    styles = (getattr(data, "drc", None) or {}).get("styles", []) if data is not None else []
    return [s for s in styles if s.startswith("drc(")]


# -- the task ---------------------------------------------------------------------

def _n(n, one, many):
    return "%d %s" % (n, one if n == 1 else many)


def headline(rows, n_alone, what, area=False, nothing=False):
    """The first line of the GUI's result message, in plain words: the error
    markers per rule (``rows``: (cell, why, box)), or that there are none.
    ``n_alone``: the boxes that are information only; ``area``: an area
    check; ``nothing``: Magic reads nothing in the cells asked for."""
    if nothing:
        return "Magic reads nothing in %s, so Magic DRC checked nothing." % what
    where = ("in the checked area of %s" if area else "in %s") % what
    if not rows:
        s = "No DRC errors %s." % where
        if n_alone:
            s += " %s information only." % _n(n_alone, "marker is", "markers are")
        return s
    per = {}
    for _c, why, _b in rows:
        per[rule_id(why)] = per.get(rule_id(why), 0) + 1
    head = "%s %s" % (_n(len(rows), "DRC error marker", "DRC error markers"), where)
    if len(per) == 1:
        return "%s, rule %s." % (head, next(iter(per)))
    top = sorted(per.items(), key=lambda kv: (-kv[1], kv[0]))
    listed = ", ".join("%s %d" % kv for kv in top[:6])
    more = len(top) - 6
    return "%s, %d rules: %s%s." % (head, len(per), listed, " and %d more" % more if more > 0 else "")


class Outcome:
    def __init__(self, status, rdb, summary, files=None):
        self.status = status
        self.rdb = rdb
        self.summary = summary
        self.headline = None    # the GUI message's plain first line
        self.files = files or {}
        self.rows = []          # (KLayout cell, why, (l, b, r, t) nm): the errors kept
        self.raw = {}           # {checked cell: {file cell name: [Error]}}, before the copy drop and the area
        self.counts = {}        # {checked cell: {file cell name: drc list count total}}
        self.dropped = 0        # boxes the copy drop removed
        self.export = {}        # {checked cell: ExportResult}
        # Hierarchical mode: the subcells' boxes that only their own check
        # lists, (KLayout cell, why, (l, b, r, t) nm), not in rows; the
        # classes' counts per checked cell (TOP, IN_TOP, FLAT_ONLY, ALONE);
        # and the flattened layout's boxes, per checked cell, when that
        # check ran (in the top cell's coordinates).
        self.alone = []
        self.classes = {}
        self.flat_raw = {}
        # The KLayout names of the cells Magic read as empty and did not
        # check: subcells hierarchical mode skipped, and a top cell Magic
        # reads nothing in (then a finding under "Export/Magic reads nothing
        # in this cell", status 1).
        self.empty = []


def _file_tree(layout, top):
    """The names of ``top`` and every cell under it in ``layout`` (the
    exported file read back), or [] when there is no such layout."""
    if layout is None:
        return []
    cell = layout.cell(top)
    if cell is None:
        return []
    return [layout.cell(i).name for i in cell.called_cells()] + [cell.name]


class _Unit:
    """One cell the user asked for: its export and its batches."""

    def __init__(self, cell_name, er, back):
        self.name = cell_name     # the KLayout name
        self.er = er
        self.back = back          # the exported file, read back
        self.order = None         # Magic's order (file names), from the first batch
        self.next_first = 0
        self.raw = {}             # file name -> [Error]
        self.counts = {}          # file name -> count total
        self.empty = []           # file names of the cells Magic read as empty
        self.top_empty = False    # the top cell is one of them: a finding, not a failed job
        self.us = 0
        self.dirs = []
        self.said = []
        self.magic = None
        self.tech_version = None
        self.scale = None
        # hierarchical mode: the flattened layout's check, run when some
        # subcell box is not in the top cell's listing
        self.hier = None          # (children, order, kept, dropped, places), from _hier()
        self.flat_state = None    # None, "skipped", "done"
        self.flat_er = None
        self.flat = None          # [Error] of the flattened layout
        self.flat_dir = None
        self.flat_elapsed = None
        self.flat_cached = False


class Task:
    """Runs a DRC's Magic jobs one after another (the task API,
    design-0.6.md 2.4): ``start()`` returns at once, ``poll()`` serves a GUI timer,
    ``wait()`` blocks, ``cancel()`` kills the running job."""

    def __init__(self, cfg, data, options, layout, units, outcome=None, tmpdir=None):
        self.cfg = cfg
        self.data = data
        self.options = options
        self.layout = layout
        self.units = units
        self.stage = None
        self._outcome = outcome
        self._job = None
        self._cur = None
        self._started = False
        self._tmpdir = tmpdir
        self._error = None
        self.names = [u.name for u in units]

    # -- public --

    def start(self):
        if self._started or self._outcome is not None:
            return self
        self._started = True
        self._advance()
        return self

    def poll(self):
        if self._outcome is not None:
            return self._outcome
        if not self._started:
            self.start()
            if self._outcome is not None:
                return self._outcome
        if self._job is None:
            return self._outcome
        r = self._job.poll()
        if r is None:
            self.stage = self._job.stage or self.stage
            return None
        self._handle(r)
        return self._outcome

    def wait(self):
        self.start()
        while self._outcome is None:
            if self._job is None:
                break
            self._handle(self._job.wait())
        return self._outcome

    def cancel(self):
        if self._outcome is not None:
            return
        if self._job is not None:
            self._job.cancel()
            self._job = None
        self._fail("cancelled")

    # -- running --

    def _next_batch(self):
        """(unit, first cell, kind) of the next job: "hier" for a batch of
        cells, "flat" for the flattened layout's check; (None, None, None)
        when every job is done."""
        for u in self.units:
            if u.order is None:
                return u, 0, "hier"
            if u.next_first < len(u.order):
                return u, u.next_first, "hier"
            if self.options["mode"] == "hierarchical" and u.flat_state is None:
                if self._needs_flat(u):
                    return u, 0, "flat"
                u.flat_state = "skipped"
        return None, None, None

    def _hier(self, u):
        """The copy drop, the area and the classes against the top cell's listing, once
        the unit's batches are all in."""
        if u.hier is None:
            children, bottom_up = _children(u.back, u.er.top)
            kept, dropped = dedup(u.raw, children, bottom_up, keep=(u.er.top,))
            places = placements(children, u.er.top, bottom_up)
            if self.options.get("box"):
                kept = in_area(kept, places, area_nm(self.options["box"]))
            u.hier = (children, bottom_up, kept, dropped, places)
        return u.hier

    def _needs_flat(self, u):
        children, order, kept, dropped, places = self._hier(u)
        classes = classify(kept, u.er.top, u.raw.get(u.er.top, []), places)
        return any(cls is None for res in classes.values() for _, cls in res)

    def _flat_export(self, u):
        """The flattened layout, written from the exported file read back
        (the same mask; the user's layout may have changed since prepare)."""
        from .export import export_cell
        if u.flat_er is None:
            d = self._tmpdir or tempfile.mkdtemp(prefix="kmp-drc-")
            self._tmpdir = d
            path = os.path.join(d, "flat-%s.gds" % u.er.top)
            u.flat_er = export_cell(u.back, u.er.top, path, None, flat=True)
        return u.flat_er

    def _use_cache(self):
        return not self.options.get("no_cache") and getattr(self.cfg, "cache_enabled", True)

    def _advance(self):
        while self._outcome is None:
            u, first, kind = self._next_batch()
            if u is None:
                self._finish()
                return
            if kind == "flat":
                try:
                    er = self._flat_export(u)
                except Exception as e:  # ExportError, or KLayout's RuntimeError
                    self._fail("cannot write the flattened layout of %s: %s" % (u.name, e))
                    return
                mode, what = "flat", "flattened %s" % u.name
            else:
                er, mode, what = u.er, self.options["mode"], u.name
            # The flattened check's options are flat mode's, so the two share a cache entry
            # when their files are equal.
            opts = {"style": self.options["style"], "mode": mode, "top": er.top,
                    "first": first, "count": jobs.MAX_CELLS}
            job_dir = None
            if self._use_cache():
                key = jobs.job_cache_key(er.sha256, "drc", opts, self.cfg)
                job_dir = jobs.job_dir_for(self.cfg, "drc", key)
                cached = _read_record(job_dir)
                if cached is not None:
                    self.stage = ("cached %s" % what, first)
                    if kind == "flat":
                        u.flat_cached = True
                        self._take_flat(u, job_dir, cached)
                    elif not self._take(u, first, job_dir, cached):
                        return
                    continue
            env = {"KMP_TOP": er.top, "KMP_MODE": mode,
                   "KMP_STYLE": self.options["style"], "KMP_FIRST": str(first),
                   "KMP_COUNT": str(jobs.MAX_CELLS)}
            try:
                self._job = jobs.MagicJob(self.cfg, "drc", SCRIPT, env=env, files={"in.gds": er.path},
                                          timeout=self.options.get("timeout"), job_dir=job_dir,
                                          required=(RESULT,))
                self._job.start()
            except jobs.JobError as e:
                self._job = None
                self._fail("cannot start Magic: %s" % e)
                return
            self._cur = (u, first, kind)
            self.stage = ("starting %s" % what, first)
            return

    def _handle(self, r):
        self._job = None
        u, first, kind = self._cur
        if not r.ok and kind == "hier" and _empty_error(r.error, u.er.top):
            self._take_empty(u, first, r)
            self._advance()
            return
        if not r.ok:
            u.said += magic_said(r.stdout, r.stderr)
            self._fail("Magic's DRC job%s failed: %s (job directory %s)"
                       % (" on the flattened layout" if kind == "flat" else "", r.error, r.dir))
            return
        rec = {"scale": r.scale, "said": magic_said(r.stdout, r.stderr),
               "magic": magic_version(r.stdout, r.stderr), "elapsed": r.elapsed}
        if rec["scale"] is None:
            self._fail("Magic's DRC job printed no scale (job directory %s)" % r.dir)
            return
        try:
            with open(os.path.join(r.dir, RESULT), "w", encoding="utf-8") as f:
                json.dump(rec, f, indent=1)
        except OSError:
            pass
        if kind == "flat":
            self._take_flat(u, r.dir, rec)
            self._advance()
        elif self._take(u, first, r.dir, rec):
            self._advance()

    def _take_flat(self, u, job_dir, rec):
        """Read the flattened layout's check into its unit."""
        u.flat_state = "done"
        u.flat_dir = job_dir
        u.flat_elapsed = rec.get("elapsed")
        for ln in rec.get("said", []):
            # Said about the file written for this check, not the user's layout: two
            # placements' boundaries in one cell, for example ("boundary was redefined").
            text = "on the flattened layout: %s" % ln
            if text not in u.said and not is_noise(ln):
                u.said.append(text)
        u.flat = []
        for ln in _lines(os.path.join(job_dir, "summary.tsv")):
            parts = ln.split("\t")
            if len(parts) >= 6 and parts[2] == "checked":
                u.flat += parse_cell_tsv(os.path.join(job_dir, "drc_%d.tsv" % int(parts[0])), rec["scale"])

    def _take(self, u, first, job_dir, rec):
        """Read one finished batch into its unit. False after a failure."""
        order = _lines(os.path.join(job_dir, "cells.txt"))
        if u.order is None:
            u.order = order
            if self.options["mode"] == "hierarchical":
                # A cell of the exported file that Magic's hierarchy lacks
                # (Magic made no cell from it, for example one holding only
                # layers its reader ignores) is not checked: list it as empty.
                for c in _file_tree(u.back, u.er.top):
                    if c not in order and c not in u.empty:
                        u.empty.append(c)
        elif order != u.order:
            self._fail("Magic listed the cells of %s differently in two batches" % u.name)
            return False
        u.next_first = first + jobs.MAX_CELLS
        u.dirs.append(job_dir)
        u.scale = rec["scale"]
        u.magic = u.magic or rec.get("magic")
        for ln in rec.get("said", []):
            if ln not in u.said and not is_noise(ln):
                u.said.append(ln)
        meta = dict(ln.split("\t", 1) for ln in _lines(os.path.join(job_dir, "meta.tsv")) if "\t" in ln)
        u.tech_version = u.tech_version or meta.get("tech_version")
        _read_summary(u, job_dir, rec["scale"])
        return True

    def _take_empty(self, u, first, r):
        """The batch that reached the top cell failed because Magic reads it
        as empty: keep what the batch listed before it, mark the top cell
        empty, and end the unit's jobs. The failed job is not cached."""
        order = _lines(os.path.join(r.dir, "cells.txt")) or [u.er.top]
        if u.order is None:
            u.order = order
        u.next_first = len(u.order)
        u.flat_state = "skipped"
        u.dirs.append(r.dir)
        u.scale = u.scale or r.scale
        u.magic = u.magic or magic_version(r.stdout, r.stderr)
        for ln in magic_said(r.stdout, r.stderr):
            if ln not in u.said:
                u.said.append(ln)
        _read_summary(u, r.dir, r.scale)
        u.top_empty = True
        if u.er.top not in u.empty:
            u.empty.append(u.er.top)

    def _fail(self, why):
        self._error = why
        self._finish()

    # -- the result --

    def _finish(self):
        from . import markers
        opts = self.options
        rdb = _new_rdb(self.cfg, opts, [u.name for u in self.units] or self.names)
        out = Outcome(0, rdb, "")
        area = area_nm(opts["box"]) if opts.get("box") else None
        aliases = tech_aliases(self.data, self.cfg) if self.data is not None else {}
        synonyms = tech_types(self.data, self.cfg) if self.data is not None else {}
        gaps = load_gaps(self.cfg.pdk) if self.cfg is not None else {}
        infos = {}
        made = set()        # why-texts whose category holds errors
        n_items, rules, cells_hit = 0, set(), set()
        n_empty = 0
        lines = []
        for u in self.units:
            markers.add_export_findings(rdb, u.er, cell_name=u.name)
            if u.said:
                markers.add_magic_said(rdb, u.said)
            out.export[u.name] = u.er
            for fc in u.empty:
                kn = u.er.klayout_name(fc)
                if kn not in out.empty:
                    out.empty.append(kn)
            if u.top_empty:
                markers.add_reads_nothing(rdb, u.er, cell_name=u.name, data=self.data)
                n_empty += 1
            if u.order is None:
                continue
            out.raw[u.name] = u.raw
            out.counts[u.name] = u.counts
            hier = opts["mode"] == "hierarchical"
            if hier:
                children, bottom_up, kept, dropped, places = self._hier(u)
                out.dropped += dropped
                classes = classify(kept, u.er.top, u.raw.get(u.er.top, []), places, u.flat)
                if u.flat is not None:
                    out.flat_raw[u.name] = u.flat
            else:
                kept = {c: list(e) for c, e in u.raw.items()}
                dropped = 0
                if area is not None:
                    kept = in_area(kept, {u.er.top: [Xf()]}, area)
                classes = {c: [(e, TOP) for e in errs] for c, errs in kept.items()}
            counts = class_counts(classes)
            out.classes[u.name] = counts
            n_unit = 0
            for fc in u.order:
                kname = u.er.klayout_name(fc)
                for e, cls in classes.get(fc, []):
                    info = infos.get(e.why)
                    if info is None:
                        info = infos[e.why] = RuleInfo(self.data, e.why, gaps, aliases, synonyms)
                    if cls != ALONE and e.why not in made:
                        made.add(e.why)
                        rdb.category(category_path(e.why), info.description())
                    if cls == IN_TOP:
                        # The top cell's own check lists this box: its box there reports it.
                        continue
                    if cls == ALONE:
                        cat = alone_category(e.why, kname)
                        rdb.category(cat, "%s\nCell %s, in the top cell %s." % (ALONE_NOTE, kname, u.name))
                        rdb.item(cat, kname, _dbox(e.box), "%s; information only" % info.item_text(), info=True)
                        out.alone.append((kname, e.why, e.box))
                        continue
                    text = info.item_text()
                    if cls == FLAT_ONLY:
                        text = "%s; %s" % (text, FLAT_ONLY_TEXT)
                    rdb.item(category_path(e.why), kname, _dbox(e.box), text)
                    out.rows.append((kname, e.why, e.box))
                    n_items += 1
                    n_unit += 1
                    rules.add(e.rule)
                    cells_hit.add(kname)
            if u.top_empty:
                lines.append("%s: Magic reads nothing in this cell, so nothing was checked (category %s)"
                             % (u.name, markers.CAT_READS_NOTHING))
                continue
            top_count = u.counts.get(u.er.top, 0)
            line = ("%s: %d error box%s%s; Magic's drc list count total %d in the top cell%s"
                    % (u.name, n_unit, "" if n_unit == 1 else "es",
                       ", %d dropped as copies of a subcell's boxes" % dropped if dropped else "",
                       top_count,
                       ", %d over the %d cells checked" % (sum(u.counts.values()), len(u.counts))
                       if len(u.counts) > 1 else ""))
            sub = counts[IN_TOP] + counts[FLAT_ONLY] + counts[ALONE]
            if hier and sub:
                line += ("; of the %d box%s the subcells' own checks list, %d %s in the top cell's check "
                         "(reported there), %d only in the flattened layout's check, %d only when the subcell "
                         "is checked on its own (information, not counted)"
                         % (sub, "" if sub == 1 else "es", counts[IN_TOP], "is" if counts[IN_TOP] == 1 else "are",
                            counts[FLAT_ONLY], counts[ALONE]))
            lines.append(line)
        for name, ids in self._rule_parents(infos).items():
            rdb.category((CAT_DRC, name), "Magic rule %s: %s" % (name, "; ".join(ids)))
        if self.layout is not None:
            for u in self.units:
                markers.add_parent_references(rdb, self.layout, top=u.name)
        rdb.db.description = _description(self.cfg, self.data, opts, self.units, lines, self._error)
        out.files = {"jobs": [d for u in self.units for d in u.dirs]}
        if out.files["jobs"]:
            out.files["job_dir"] = out.files["jobs"][0]
            out.files["export"] = os.path.join(out.files["jobs"][0], "in.gds")
        flat_dirs = [u.flat_dir for u in self.units if u.flat_dir]
        if flat_dirs:
            out.files["flat_check"] = flat_dirs[0]
            out.files["flat_checks"] = flat_dirs
        style, mode = opts["style"], opts["mode"]
        what = ", ".join(u.name for u in self.units) or "nothing"
        if self._error:
            rdb.info(rdb.category(CAT_FAILED, "Why Magic's DRC gave no result."), self._error)
            out.status = 2
            out.summary = "Magic DRC (%s, %s) of %s failed: %s" % (style, mode, what, self._error)
        else:
            out.status = 1 if n_items or n_empty else 0
            area_text = " in the area %s um" % ",".join(fmt_um(v) for v in area) if area else ""
            if n_items:
                head = "%d error box%s, %d rule%s, in %d cell%s" % (
                    n_items, "" if n_items == 1 else "es", len(rules), "" if len(rules) == 1 else "s",
                    len(cells_hit), "" if len(cells_hit) == 1 else "s")
            elif n_empty == len(self.units):
                # Every cell asked for is one Magic reads nothing in: one sentence says so.
                head = "Magic reads nothing in %s, so nothing was checked (category %s)" % (
                    what, markers.CAT_READS_NOTHING)
            elif n_empty:
                head = "no errors in the cells checked"
            else:
                head = "no errors"
            out.summary = "Magic DRC (%s, %s) of %s on %s%s: %s." % (style, mode, what, self.cfg.pdk, area_text, head)
            if lines and n_empty < len(self.units):
                out.summary += " %s." % "; ".join(lines)
            out.headline = headline(out.rows, len(out.alone), what, area is not None,
                                    nothing=n_empty == len(self.units))
            # The reads-nothing item is under Export too; the head names it.
            export_n = rdb.count(CAT_EXPORT) - rdb.count(markers.CAT_READS_NOTHING)
            if export_n:
                out.summary += " The export has %d finding%s (category Export)." % (
                    export_n, "" if export_n == 1 else "s")
        self._outcome = out
        if self._tmpdir:
            shutil.rmtree(self._tmpdir, ignore_errors=True)
            self._tmpdir = None

    def _rule_parents(self, infos):
        """{rule ID: [why-texts]} for the IDs that group why-texts."""
        out = {}
        for why in infos:
            p = category_path(why)
            if len(p) == 3:
                out.setdefault(p[1], []).append(why)
        return out


def _read_summary(u, job_dir, scale):
    """A batch's summary.tsv into its unit: the cells listed empty, and each
    checked cell's count, time and boxes (none without a scale)."""
    for ln in _lines(os.path.join(job_dir, "summary.tsv")):
        parts = ln.split("\t")
        if len(parts) < 6:
            continue
        i, cell, state = int(parts[0]), parts[1], parts[2]
        if state == "empty":
            if cell not in u.empty:
                u.empty.append(cell)
            continue
        if scale is None:
            continue
        u.counts[cell] = int(parts[3] or 0)
        u.us += int(parts[5] or 0)
        u.raw[cell] = parse_cell_tsv(os.path.join(job_dir, "drc_%d.tsv" % i), scale)


def _empty_error(error, top):
    """The job failed because Magic read the top cell as empty."""
    from .markers import empty_cell_error
    return empty_cell_error(error, top)


def _lines(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return [ln.rstrip("\n") for ln in f if ln.strip()]
    except OSError:
        return []


def _read_record(job_dir):
    """A finished batch's record, or None."""
    try:
        with open(os.path.join(job_dir, RESULT), encoding="utf-8") as f:
            rec = json.load(f)
        with open(os.path.join(job_dir, jobs.JOB_META), encoding="utf-8") as f:
            meta = json.load(f)
    except (OSError, ValueError, AttributeError):
        return None
    if meta.get("state") != "done" or rec.get("scale") is None:
        return None
    return rec


def _dbox(box):
    from ._kl import db
    return db.DBox(box[0] / 1000.0, box[1] / 1000.0, box[2] / 1000.0, box[3] / 1000.0)


def _children(layout, top_name):
    """({cell: [(child, Xf)]}, cells children first) of the tree under
    ``top_name`` in the read-back export, with the file's names."""
    top = layout.cell(top_name)
    if top is None:
        return {}, []
    tree = set(top.called_cells()) | {top.cell_index()}
    children = {}
    order = []
    for ci in layout.each_cell_bottom_up():
        if ci not in tree:
            continue
        c = layout.cell(ci)
        order.append(c.name)
        for inst in c.each_inst():
            ch = layout.cell(inst.cell_index).name
            for t in inst.dcell_inst.each_cplx_trans():
                children.setdefault(c.name, []).append((ch, Xf.from_klayout(t)))
    return children, order


def _versions(cfg, data, units):
    magic = next((u.magic for u in units if u.magic), None)
    tech = next((u.tech_version for u in units if u.tech_version), None)
    src = getattr(data, "source", None) or {}
    if not tech:
        tech = src.get("magic_tech_version")
    return magic or "?", tech or "?", src.get("open_pdks")


def _gone_note(d):
    """What the description says beside a job directory's path: a tmp-*
    one goes when the check ends."""
    if os.path.basename(os.path.normpath(d)).startswith(jobs.TMP_PREFIX) and not jobs.keep_job_dirs():
        return " (removed when the check ends; KMP_JOB_KEEP=1 keeps it)"
    return ""


def _description(cfg, data, opts, units, lines, error):
    magic, tech, pdk_commit = _versions(cfg, data, units)
    mode = opts["mode"]
    note = M1_NOTE if mode == "hierarchical" else "%s. The hierarchical mode %s" % (FLAT_NOTE, M1_NOTE[len("this mode "):])
    out = ["Magic DRC on %s: Magic %s, tech %s%s." % (cfg.pdk, magic, tech,
                                                     ", open_pdks %s" % pdk_commit if pdk_commit else ""),
           "Style %s, mode %s: %s." % (opts["style"], mode, note)]
    if opts.get("box"):
        out.append("Area %s um: the errors of Magic's whole-cell check that touch it."
                   % ",".join(fmt_um(v) for v in area_nm(opts["box"])))
    out += lines
    for u in units:
        if u.empty:
            out.append("%s: cells empty to Magic, not checked: %s"
                       % (u.name, ", ".join(u.er.klayout_name(c) for c in u.empty)))
        if u.dirs:
            out.append("%s: exported file %s%s" % (u.name, os.path.join(u.dirs[0], "in.gds"),
                                                   _gone_note(u.dirs[0])))
        if u.flat_dir:
            out.append("%s: some boxes of the subcells' own checks are not in the top cell's check, so "
                       "Magic also checked the flattened layout (%d box%s, %s%s): a box it confirms is an "
                       "error, the others are information only, under \"only when <cell> is checked on its "
                       "own\"" % (u.name, len(u.flat or []), "" if len(u.flat or []) == 1 else "es",
                                   "%.1f s" % u.flat_elapsed if u.flat_elapsed is not None else "time unknown",
                                   ", from the job cache" if u.flat_cached else "")
                       + "; job directory %s%s" % (u.flat_dir, _gone_note(u.flat_dir)))
    if error:
        out.append("Failed: %s" % error)
    out.append("Command: %s" % command_line(opts, [u.name for u in units], cfg.pdk if cfg else None))
    # One line: KLayout's browser lists a database as "<name> (<description>)" and
    # writes a line break there as a literal \n.
    return " ".join(ln if ln.endswith(".") else ln + "." for ln in out[:-1]) + " " + out[-1]


def _quote_sh(s):
    s = str(s)
    return s if re.match(r"^[A-Za-z0-9_./=,:+-]+$", s) else "'" + s.replace("'", "'\\''") + "'"


def command_line(opts, cells, pdk=None):
    parts = ["python3", "-m", "klayout_magic_pcells", "drc", _quote_sh(opts.get("file") or "FILE")]
    for c in cells:
        parts += ["--cell", _quote_sh(c)]
    if pdk:
        parts += ["--pdk", _quote_sh(pdk)]
    parts += ["--style", _quote_sh(opts["style"]), "--mode", opts["mode"]]
    if opts.get("box"):
        parts += ["--box", ",".join(fmt_um(v) for v in area_nm(opts["box"]))]
    return " ".join(parts)


def _new_rdb(cfg, opts, names):
    from . import markers
    name = "Magic DRC %s: %s" % (opts.get("style"), ", ".join(names))
    gen = {"cmd": "drc", "file": opts.get("file") or "", "cell": ",".join(names),
           "style": opts.get("style"), "mode": opts.get("mode"), "pdk": cfg.pdk if cfg else None}
    if opts.get("box"):
        gen["box"] = ",".join(fmt_um(v) for v in area_nm(opts["box"]))
    return markers.Rdb(name, "", markers.recipe_generator(gen), names[0] if names else "")


def _failed_task(cfg, data, options, names, why):
    t = Task(cfg, data, options, None, [])
    rdb = _new_rdb(cfg, options, names)
    rdb.info(rdb.category(CAT_FAILED, "Why Magic's DRC did not run."), why)
    rdb.db.description = "Magic DRC on %s did not run: %s" % (getattr(cfg, "pdk", "?"), why)
    t._outcome = Outcome(2, rdb, "Magic DRC (%s, %s) of %s did not run: %s"
                         % (options.get("style"), options.get("mode"), ", ".join(names) or "nothing", why))
    return t


def prepare(layout, cell, cfg, data, options):
    """Export ``cell`` (a Cell, a name, or a list of either: each is checked
    as its own top cell) and return a Task that has not started Magic.

    options: ``style`` (default cfg.drc_style), ``mode`` (hierarchical or
    flat, default cfg.drc_mode), ``box`` (an area in µm: (l, b, r, t) or
    "l,b,r,t"), ``no_cache``, ``timeout`` (seconds per job), ``file`` (the
    layout's file name, for the description and Rerun)."""
    from . import markers
    from .export import ExportError, export_cell, load_layout
    options = dict(options or {})
    options["style"] = options.get("style") or getattr(cfg, "drc_style", None) or "drc(full)"
    options["mode"] = options.get("mode") or getattr(cfg, "drc_mode", None) or "hierarchical"
    cells = cell if isinstance(cell, (list, tuple)) else [cell]
    names = [c if isinstance(c, str) else c.name for c in cells]
    if options["mode"] not in MODES:
        return _failed_task(cfg, data, options, names, "unknown mode %r (hierarchical or flat)" % options["mode"])
    styles = drc_styles(data)
    if styles and options["style"] not in styles:
        return _failed_task(cfg, data, options, names, "%s has no DRC style %s (it has %s)"
                            % (cfg.pdk, options["style"], ", ".join(styles)))
    if options.get("box"):
        try:
            area_nm(options["box"])
        except ValueError as e:
            options["box"] = None
            return _failed_task(cfg, data, options, names, str(e))
    tmp = tempfile.mkdtemp(prefix="kmp-drc-")
    units = []
    try:
        for i, c in enumerate(cells):
            path = os.path.join(tmp, "export%d.gds" % i)
            er = export_cell(layout, c, path, data, flat=options["mode"] == "flat")
            refusal = er.refusal()
            if refusal:
                shutil.rmtree(tmp, ignore_errors=True)
                t = _failed_task(cfg, data, options, names, refusal)
                markers.add_export_findings(t._outcome.rdb, er, cell_name=er.klayout_top)
                return t
            units.append(_Unit(er.klayout_top, er, load_layout(path)))
    except ExportError as e:
        shutil.rmtree(tmp, ignore_errors=True)
        return _failed_task(cfg, data, options, names, str(e))
    except RuntimeError as e:  # KLayout could not copy, write or read the cell
        shutil.rmtree(tmp, ignore_errors=True)
        return _failed_task(cfg, data, options, names, "cannot export %s: %s"
                            % (", ".join(names), str(e).splitlines()[0] if str(e) else e))
    return Task(cfg, data, options, layout, units, tmpdir=tmp)


def cli_main(args, ctx):
    options = {"style": getattr(args, "style", None), "mode": getattr(args, "mode", None),
               "box": getattr(args, "box", None), "no_cache": getattr(args, "no_cache", False),
               "file": os.path.abspath(ctx.file)}
    task = prepare(ctx.layout, list(ctx.cells), ctx.cfg, ctx.data, options)
    out = task.wait()
    if getattr(args, "output", None):
        out.rdb.save(args.output)
        out.files["rdb"] = args.output
    if getattr(args, "tsv", None):
        if args.tsv == "-":
            write_tsv(sys.stdout, out.rows)
            sys.stdout.flush()
        else:
            write_tsv(args.tsv, out.rows)
            out.files["tsv"] = args.tsv
    sys.stderr.write(out.summary + "\n")
    # The outputs are written: remove the tmp-* job directories of an
    # uncached run (a key's directory stays; KMP_JOB_KEEP=1 keeps them all).
    jobs.release([out, out.files.get("flat_checks") or []])
    return out.status
