"""Report databases (KLayout's Marker Database Browser) for every job.

``Rdb`` wraps a ``ReportDatabase``: one RDB cell per checked cell, nested
categories created once by path, items with a shape in µm in that cell's
coordinates and a text value. It works in the KLayout application and with
the standalone ``klayout`` module (``klayout.rdb``; ``pya`` in older
embedded builds, where the classes are the same). The GUI adds ``rdb.db``
to a view with ``LayoutView.add_rdb``; the command line saves it as a
``.lyrdb`` file, which ``klayout LAYOUT -m FILE.lyrdb`` opens on the layout
and shows in the Marker Database Browser. The other order, ``klayout -m
FILE.lyrdb LAYOUT``, puts the report in an empty view of its own
(design-0.6.md 2.7).

A category path is a string with ``/`` between the levels ("netgen/pins"),
or a tuple or list of names, for names that contain a ``/`` themselves
(Magic's rule ``diff/tap.8``). KLayout's own category paths join names with
``.``, which rule names contain too, so this module never looks categories
up by KLayout's path.

``add_export_findings`` puts an ``export.ExportResult``'s findings under the
"Export" categories every job shares.

An item's text goes in as one text value per line (``text_lines``): the
browser's Info pane shows each value on a line of its own in a block that
does not wrap, and it cuts a value after 200 characters (KLayout 0.30's
``MarkerBrowserPage::update_info_text``). The values joined with a space are
the item's text (``item_text``).

Items that are information, not findings of the check, are marked "waived"
and visited (``Rdb.item(..., info=True)``). KLayout's browser counts every
item in a category's total; it shows the waived ones after a dash ("3 (2) -
1"), draws a category whose items are all waived in green, and leaves
visited items out of the number in parentheses.
"""

import re

try:
    import klayout.rdb as rdb
except ImportError:  # pragma: no cover - older embedded builds
    import pya as rdb

EXPORT = "Export"
CAT_OFFGRID = "Export/Magic snaps this shape to its 5 nm grid"
CAT_UNREAD = "Export/Magic does not read this layer"
CAT_READS_AS = "Export/Magic reads this layer as another type"
CAT_CROSS_CELL = "Export/Magic reads this cell without a layer drawn in another cell"
CAT_ERROR_MARKERS = "Export/error-marker cells"
CAT_FLATTENED = "Export/instances flattened for Magic"
CAT_RENAMED = "Export/cells renamed for Magic"
CAT_READS_NOTHING = "Export/Magic reads nothing in this cell"
READS_NOTHING_DESCRIPTION = (
    "Magic's GDS reader keeps none of this cell's shapes: every layer it draws is one the reader "
    "ignores, one it reads only to decide what the diffusion or poly under it is (and there is none), "
    "or one the PDK data does not know. Magic loads an empty cell, so it has nothing to check, "
    "extract or write back. KLayout's decks still check these shapes.")
CAT_MAGIC_SAID = "Magic said"

# Items per layer and category from one export; the rest are counted in one
# info item, so a layout drawn off the grid everywhere stays browsable.
MAX_ITEMS_PER_LAYER = 500

# The longest line of an item's text in the Info pane (see the module's
# docstring).
LINE_WIDTH = 80
# KLayout's tag for an item the user accepted; the browser counts such items
# apart and draws a category of them in green.
WAIVED = "waived"

_CLAUSE_END = re.compile(r"(?<=[.;]) (?=\S)")


def _greedy(piece, width):
    out = []
    while len(piece) > width:
        cut = piece.rfind(", ", 0, width)
        if cut < width // 2:
            cut = piece.rfind(" ", 0, width + 1)
            if cut <= 0:
                cut = piece.find(" ", width)
                if cut < 0:
                    break
        else:
            cut += 1
        out.append(piece[:cut].rstrip(" "))
        piece = piece[cut:].lstrip(" ")
    out.append(piece)
    return out


def _wrap(piece, width):
    """``piece`` in lines of at most ``width`` characters, broken at spaces;
    a word longer than ``width`` stays whole. The lines are as many as
    filling each line would give, but about equally long, so that no line
    holds a lone word; a break after a comma is preferred."""
    greedy = _greedy(piece, width)
    n = len(greedy)
    if n < 2:
        return greedy
    out = []
    rest = piece
    while len(out) < n - 1 and len(rest) > width:
        target = len(rest) / float(n - len(out))
        best = None
        for i, ch in enumerate(rest):
            if ch != " " or i > width:
                continue
            left = rest[:i].rstrip(" ")
            score = abs(len(left) - target) - (6 if left.endswith(",") else 0)
            if best is None or score < best[0]:
                best = (score, i)
        if best is None:
            return greedy
        out.append(rest[:best[1]].rstrip(" "))
        rest = rest[best[1]:].lstrip(" ")
    out.append(rest)
    if any(len(ln) > width for ln in out if " " in ln):
        return greedy
    return out


def text_lines(text, width=LINE_WIDTH):
    """An item's text as the lines the Info pane shows: a line per sentence
    or clause (broken after ". " and "; "), each longer one broken at spaces
    into lines of at most ``width`` characters. Joined with single spaces,
    the lines are the text again (for a text without double spaces)."""
    text = str(text)
    if len(text) <= width or "\n" in text:
        return [text]
    lines = []
    for piece in _CLAUSE_END.split(text):
        lines += _wrap(piece, width)
    return [ln for ln in lines if ln] or [text]


def item_text(item):
    """The text of an RDB item: its text values joined with spaces."""
    return " ".join(v.string() for v in item.each_value() if v.is_string())


def _parts(path):
    if isinstance(path, (tuple, list)):
        parts = [str(p) for p in path]
    else:
        parts = [p for p in str(path).split("/")]
    if not parts or any(p == "" for p in parts):
        raise ValueError("bad category path %r" % (path,))
    return tuple(parts)


class Rdb:
    def __init__(self, name, description, generator, top_cell):
        self.db = rdb.ReportDatabase(name)
        self.db.description = description or ""
        self.db.generator = generator or ""
        self.db.top_cell_name = top_cell or ""
        self.top_cell = top_cell
        self._cats = {}    # parts -> RdbCategory
        self._cells = {}   # name -> RdbCell
        self._counts = {}  # parts -> number of items directly in it
        self._info = {}    # parts -> number of information items directly in it
        self._waived = None

    def category(self, path, description=""):
        """The category at ``path``, made (with its parents) the first time.
        A description given later fills an empty one."""
        parts = _parts(path)
        parent = None
        for i in range(1, len(parts) + 1):
            key = parts[:i]
            cat = self._cats.get(key)
            if cat is None:
                if parent is None:
                    cat = self.db.create_category(key[-1])
                else:
                    cat = self.db.create_category(parent, key[-1])
                self._cats[key] = cat
                self._counts[key] = 0
            parent = cat
        if description and not parent.description:
            parent.description = description
        return parent

    def _key(self, category):
        if isinstance(category, (str, tuple, list)):
            return _parts(category)
        for k, c in self._cats.items():
            if c.rdb_id() == category.rdb_id():
                return k
        raise ValueError("the category is not from this database")

    def _cat(self, category):
        if isinstance(category, (str, tuple, list)):
            return self.category(category)
        return category

    def cell(self, name):
        c = self._cells.get(name)
        if c is None:
            c = self.db.create_cell(name)
            self._cells[name] = c
        return c

    def item(self, category, cell_name, shape, text=None, info=False):
        """One marker: ``shape`` (DBox, DPolygon, DEdge, DEdgePair, DPath or
        DText, in µm) in ``cell_name``'s coordinates, and an optional text,
        one value per line of ``text_lines``. ``info``: information, not a
        finding of the check; the item is marked waived and visited."""
        cat = self._cat(category)
        it = self.db.create_item(self.cell(cell_name or self.top_cell).rdb_id(), cat.rdb_id())
        if shape is not None:
            it.add_value(shape)
        if text is not None:
            for line in text_lines(text):
                it.add_value(line)
        k = self._key(cat)
        self._counts[k] = self._counts.get(k, 0) + 1
        if info:
            self.mark_info(it)
            self._info[k] = self._info.get(k, 0) + 1
        return it

    def mark_info(self, it):
        """Mark an item as information: waived and visited."""
        if self._waived is None:
            self._waived = self.db.tag_id(WAIVED)
        it.add_tag(self._waived)
        self.db.set_item_visited(it, True)

    def info(self, category, text, info=False):
        """An item with no shape, in the top cell."""
        return self.item(category, self.top_cell, None, text, info=info)

    def count(self, category=None):
        """Items in ``category`` and its subcategories, or in the database."""
        if category is None:
            return sum(self._counts.values())
        k = self._key(category)
        return sum(n for p, n in self._counts.items() if p[:len(k)] == k)

    def count_info(self, category=None):
        """The information items among ``count(category)``."""
        if category is None:
            return sum(self._info.values())
        k = self._key(category)
        return sum(n for p, n in self._info.items() if p[:len(k)] == k)

    def save(self, path):
        self.db.save(path)


def load(path):
    """A saved database, as a ``ReportDatabase``."""
    r = rdb.ReportDatabase("")
    r.load(path)
    return r


def _capped(rdb_, category, cell, rows, label, info=False):
    """rows: [(key, DBox, text)]; at most MAX_ITEMS_PER_LAYER per key."""
    shown = {}
    extra = {}
    for key, box, text in rows:
        n = shown.get(key, 0)
        if n < MAX_ITEMS_PER_LAYER:
            rdb_.item(category, cell, box, text, info=info)
            shown[key] = n + 1
        else:
            extra[key] = extra.get(key, 0) + 1
    for key, n in sorted(extra.items()):
        rdb_.info(category, "%s: %d more not shown" % (label(key), n), info=info)


def add_export_findings(rdb_, er, cell_name=None, counted=()):
    """Put an ExportResult's findings into ``rdb_``, in the exported top
    cell (``cell_name``, default its KLayout name). The items of the
    categories in ``counted`` are findings of the check; the others are
    information (``Rdb.item(..., info=True)``). Returns the number of items
    added."""
    cell = cell_name or er.klayout_top or rdb_.top_cell
    before = rdb_.count()

    def info(cat):
        return cat not in counted
    if er.offgrid:
        cat = rdb_.category(CAT_OFFGRID, "Magic's GDS reader snaps these vertices to its grid, prints "
                            "a warning and checks the snapped shape; it reports no DRC error for them. "
                            "The PDK's KLayout deck flags them as off-grid.")
        _capped(rdb_, cat, cell, [(lay, box, "%s: a vertex off the grid" % lay) for lay, box in er.offgrid],
                lambda k: k, info(CAT_OFFGRID))
    if er.unread:
        cat = rdb_.category(CAT_UNREAD, "Magic's GDS reader ignores these layers: the shapes have no "
                            "effect on Magic's DRC, extraction or LVS.")
        regen = getattr(er, "regenerated", set())

        def _unread_text(l, d):
            if (l, d) in regen:
                return ("GDS %d/%d: Magic's reader ignores this layer and draws its own when it "
                        "writes GDS" % (l, d))
            return "GDS %d/%d: Magic's reader ignores this layer" % (l, d)
        _capped(rdb_, cat, cell, [((l, d), box, _unread_text(l, d))
                                  for l, d, box in er.unread], lambda k: "GDS %d/%d" % k, info(CAT_UNREAD))
    if er.reads_as:
        cat = rdb_.category(CAT_READS_AS, "Magic reads these layers as a type that means something "
                            "else than the layer's KLayout name.")
        _capped(rdb_, cat, cell, [((l, d), box, "GDS %d/%d: Magic reads it as %s" % (l, d, t))
                                  for l, d, t, box in er.reads_as], lambda k: "GDS %d/%d" % k, info(CAT_READS_AS))
    if er.cross_cell:
        cat = rdb_.category(CAT_CROSS_CELL, "Magic decides device types inside each cell from that "
                            "cell's own shapes. An implant or marker drawn in one cell (a parent, a "
                            "child or a sibling) over the diffusion or poly of another, or a well over "
                            "its diffusion, is not there when Magic reads the other cell, so its DRC, "
                            "extraction and LVS see other devices than KLayout's decks do.")
        _capped(rdb_, cat, cell, [((f["cell"], f["layer"]), f["box"],
                                   "Magic reads cell %s without the %s drawn in cell %s"
                                   % (f["cell"], f["layer"], f["drawn_in"])) for f in er.cross_cell],
                lambda k: "cell %s, %s" % k, info(CAT_CROSS_CELL))
    if er.error_markers:
        cat = rdb_.category(CAT_ERROR_MARKERS, "Cells with the plugin's error marker (255/0): a PCell "
                            "variant that Magic failed to generate. Magic doesn't read 255/0, so a job "
                            "would check the layout without that device.")
        for name in er.error_markers:
            # Every check that runs Magic refuses such a layout: never information.
            rdb_.info(cat, "cell %s holds an error marker" % name)
    if er.flattened:
        cat = rdb_.category(CAT_FLATTENED, "Instances with a rotation that is not a multiple of 90° or "
                            "a magnification: Magic rounds the angle and has no magnification, so the "
                            "export flattens them into their parent.")
        for parent, reason in er.flattened:
            rdb_.info(cat, "in cell %s: %s" % (parent, reason), info=info(CAT_FLATTENED))
    if er.renamed:
        cat = rdb_.category(CAT_RENAMED, "Magic can't load cells whose names hold characters other "
                            "than letters, digits, _ and $; the export renames them.")
        for old, new in sorted(er.renamed.items()):
            rdb_.info(cat, "%s is %s in the file Magic reads" % (old, new), info=info(CAT_RENAMED))
    return rdb_.count() - before


_READ_TEXT = {
    "ignored": "Magic's reader ignores it",
    "device-only": "Magic's reader uses it only to decide what the diffusion or poly under it is, and "
                   "this cell has none",
    "text": "Magic reads it as labels only",
    "pin": "Magic reads it as pin boxes only",
}


def reads_nothing_text(er, data=None):
    """The item text of a cell Magic reads as empty: the layers it draws,
    each with what Magic's reader does with it, from the PDK data's layer
    table (``er.drawn``)."""
    regen = getattr(er, "regenerated", set()) or set()
    parts = []
    for l, d, rec in getattr(er, "drawn", None) or []:
        if not isinstance(rec, dict) and data is not None:
            try:
                rec = data.layer(l, d)
            except (KeyError, LookupError, ValueError):
                rec = None
        name = rec.get("name") if isinstance(rec, dict) else None
        lay = "%d/%d (%s)" % (l, d, name) if name else "%d/%d" % (l, d)
        if not isinstance(rec, dict):
            why = "the PDK data has no row for it, so Magic's reader does not know it"
        else:
            read = rec.get("read", "")
            why = _READ_TEXT.get(read) or "Magic reads it as %s" % (read or "unknown")
            if read == "ignored" and (l, d) in regen:
                why += " (and draws its own when it writes GDS)"
            if rec.get("line"):
                why += " (%s)" % rec["line"]
        parts.append("%s: %s" % (lay, why))
    cell = getattr(er, "klayout_top", None) or getattr(er, "top", None) or "?"
    if not parts:
        return "Magic reads nothing in cell %s: the cell has no shapes" % cell
    return "Magic reads nothing in cell %s. Its layers: %s" % (cell, "; ".join(parts))


def add_reads_nothing(rdb_, er, cell_name=None, data=None):
    """The finding for a cell Magic's reader leaves empty (its job's
    ``kmp_job_load`` says "cell X is empty"): one item under
    CAT_READS_NOTHING over the cell's box, naming its layers. Returns the
    item's text."""
    cell = cell_name or er.klayout_top or rdb_.top_cell
    text = reads_nothing_text(er, data)
    cat = rdb_.category(CAT_READS_NOTHING, READS_NOTHING_DESCRIPTION)
    box = getattr(er, "bbox", None)
    rdb_.item(cat, cell, box if box is not None and not box.empty() else None, text)
    return text


def empty_cell_error(error, top):
    """True when a job's KMP_JOB_FAIL text says that Magic read the cell
    ``top`` (its name in the exported file) as empty (kmp_job_load)."""
    if not error or not top:
        return False
    return error.strip() in ("cell %s is empty" % top, "cell %s has an empty bounding box" % top,
                             "cell %s has no bounding box" % top)


def add_magic_said(rdb_, lines):
    """Magic's warnings and errors (for example ``Unknown layer/datatype in
    boundary``) as information items under "Magic said"; repeated lines
    once."""
    seen = set()
    cat = None
    for ln in lines:
        ln = ln.strip()
        if not ln or ln in seen or ln.startswith("KMP_JOB"):
            continue
        seen.add(ln)
        if cat is None:
            cat = rdb_.category(CAT_MAGIC_SAID, "What Magic printed while it read and checked the file.")
        rdb_.info(cat, ln, info=True)
    return len(seen)


# -- Rerun and the placement of child items (design-0.6.md 2.7) --------------

RECIPE = "klayout_magic_pcells"
# References per RDB cell; the Marker Database Browser shows a child's items
# through the first one only.
MAX_REFERENCES = 1000


def _recipe_quote(text):
    """A value as KLayout's Recipe.generator() writes it: in single quotes,
    with \\ and ' escaped, \\n, \\r and \\t as such, and other control and
    non-ASCII bytes of the UTF-8 text in octal (café is 'caf\\303\\251')."""
    out = ["'"]
    for b in str(text).encode("utf-8"):
        c = chr(b)
        if c in "'\\":
            out.append("\\" + c)
        elif c == "\n":
            out.append("\\n")
        elif c == "\r":
            out.append("\\r")
        elif c == "\t":
            out.append("\\t")
        elif b < 0x20 or b >= 0x7f:
            out.append("\\%03o" % b)
        else:
            out.append(c)
    out.append("'")
    return "".join(out)


def recipe_generator(params):
    """The RDB generator that makes the browser's Rerun button call the
    plugin back: the text ``pya.Recipe.generator(params)`` gives for the
    recipe ``klayout_magic_pcells`` (design-0.6.md 2.7), for example
    ``klayout_magic_pcells: cell='inv',cmd='drc',mode='hierarchical'``.

    It needs no Recipe object, so the command line can write it and nothing
    is registered here; the GUI registers the recipe that runs it. Every
    value is written as a string; None values are left out."""
    parts = []
    for k in sorted(str(k) for k in params):
        v = params[k]
        if v is None:
            continue
        parts.append("%s=%s" % (k, _recipe_quote(v)))
    return "%s: %s" % (RECIPE, ",".join(parts))


def add_parent_references(rdb_, layout, top=None):
    """Give every RDB cell that names a cell of ``layout`` one reference per
    placement in each parent (array elements included), and the parents
    theirs, up to ``top`` (default the database's top cell). The browser
    draws a child's items through the first reference (design-0.6.md 2.7),
    so items in a child cell show in their place in the top cell. ``rdb_`` is an ``Rdb``
    or a ``ReportDatabase``; parent cells are made as needed. Only parents
    inside ``top``'s tree are followed when ``top`` is in the layout.
    Returns the number of references added."""
    if isinstance(rdb_, Rdb):
        report = rdb_.db
        cell_for = rdb_.cell
    else:
        report = rdb_

        def cell_for(name):
            rc = report.cell_by_qname(name)
            return rc if rc is not None else report.create_cell(name)
    top_name = top or report.top_cell_name
    tc = layout.cell(top_name) if top_name else None
    tree = None
    if tc is not None:
        tree = set(tc.called_cells()) | {tc.cell_index()}
    todo = [rc.name() for rc in report.each_cell()]
    seen = set()
    added = 0
    while todo:
        name = todo.pop()
        if name in seen:
            continue
        seen.add(name)
        cell = layout.cell(name)
        if cell is None or (tree is not None and cell.cell_index() not in tree):
            continue
        rc = cell_for(name)
        n = 0
        for pi in cell.each_parent_inst():
            if tree is not None and pi.parent_cell_index() not in tree:
                continue
            parent = layout.cell(pi.parent_cell_index())
            prc = cell_for(parent.name)
            # child_inst() is the placement in the parent; dinst() would be
            # the inverse.
            for t in pi.child_inst().dcell_inst.each_cplx_trans():
                if n < MAX_REFERENCES:
                    rc.add_reference(rdb.RdbReference(t, prc.rdb_id()))
                    n += 1
            todo.append(parent.name)
        added += n
    return added
