"""Exporting a cell for a Magic job, and finding what Magic will do with it
that no check reports.

``export_cell`` writes a cell and everything below it from the layout in
memory, so unsaved edits are checked: no ``$$$CONTEXT_INFO$$$`` structure
(Magic would read it as a cell), no GDS timestamps (equal layouts give
equal bytes, for the job cache), only the selected cell's tree, at the
layout's database unit. The caller's layout is never changed: the tree is
copied into a layout of its own (``Cell.copy_tree``, which keeps the names
and turns PCell variants into plain cells) and changed there:

- instances with a rotation that is not a multiple of 90° or a
  magnification other than 1 are flattened into their parent: Magic rounds
  the angle to 90° ("Non-Manhattan angle (45) in transform") and has no
  magnification;
- cells whose names are not made of ``[A-Za-z0-9_$]`` are renamed, and
  ``name_map`` keeps the names: Magic renames ``a b`` and ``café`` itself,
  refuses ``a.b``, loads an empty ``y`` for ``x/y`` and keeps the previous
  cell for ``br[0]``;
- with ``flat=True`` the top cell is flattened: "Magic's verdict on the
  flattened mask".

It also lists, from the PDK data's layer table, what Magic changes without
an error: vertices off its grid (Magic snaps them), shapes on layers its
GDS reader ignores, layers it reads as another type, cells that hold the
plugin's error marker (a PCell variant that failed; Magic doesn't read
255/0, so it would check the layout without that device), and, in
hierarchical mode, the cross-cell findings (design-0.6.md 2.6): Magic
decides device types inside each cell from that cell's own shapes, so an
implant, well or marker drawn in one cell (a parent, a child or a sibling)
over the diffusion or poly of another is not seen when Magic reads the
other cell. A well counts only
over diffusion: it decides what diffusion is, not what poly is.

Every box in an ``ExportResult`` is in µm, in the exported top cell's
coordinates. Cell names in it are KLayout's, except ``top`` and the values
of ``name_map``, which are the names in the written file.
"""

import hashlib
import os
import re

from ._kl import db
from .pcell import PLACEHOLDER_LAYER

SAFE_NAME = re.compile(r"^[A-Za-z0-9_$]+$")
IMPLANT_ROLES = ("implant", "well", "marker")
# The shapes whose Magic type an implant, well or marker decides. A cut is not
# one of them: a diffusion or poly contact takes its type from the diffusion
# or poly it lies on in its own cell, which this list already covers, and a
# via between metals (sky130A mcon, the ViaN layers) takes none. A cell that
# only puts an mcon on a child's tap is read as drawn (the case suite's
# inv_pcell: same devices as the flattened cell).
DEVICE_ROLES = ("diffusion", "poly")
# A well decides what the diffusion in it is (pdiff in nwell, the body of a
# FET), not what a poly is: Magic reads a gate's poly the same in or out of a
# well. So a well drawn in one cell is a finding only over another cell's
# diffusion (the IHP PCell inverter: the top cell's NWell over a piece of the
# pmos PCell's gate poly outside the PCell's own NWell is no finding).
WELL_DEVICE_ROLES = ("diffusion",)


def device_roles(role):
    """The device-shape roles an implant, well or marker of ``role`` decides."""
    return WELL_DEVICE_ROLES if role == "well" else DEVICE_ROLES


class ExportError(Exception):
    """The file can't be read, or names a cell it doesn't have. ``missing``
    lists the missing names; ``tops`` the top cells when one is needed."""

    def __init__(self, message, missing=(), tops=()):
        Exception.__init__(self, message)
        self.missing = list(missing)
        self.tops = list(tops)


class ExportResult:
    def __init__(self):
        self.path = None
        self.top = None             # the top cell's name in the written file
        self.klayout_top = None     # and in KLayout
        self.name_map = {}          # KLayout name -> name in the file
        self.sha256 = None
        self.flat = False
        self.dbu = None
        self.offgrid = []           # (layer text, DBox)
        self.unread = []            # (gds layer, gds datatype, DBox)
        self.regenerated = set()    # unread (layer, datatype) pairs that Magic draws itself on output
        self.reads_as = []          # (gds layer, gds datatype, Magic type, DBox)
        self.cross_cell = []        # {"cell", "layer", "gds", "drawn_in", "box"}
        self.cross_cell_covered = []  # the same, where the cell draws the layer there itself
        self.error_markers = []     # cells holding a 255/0 error marker
        self.flattened = []         # (cell, reason)
        self.drawn = []             # (gds layer, gds datatype, data record or None): layers with shapes in the tree
        self.bbox = None            # the top cell's DBox (um), before the export changed it

    @property
    def renamed(self):
        """{KLayout name: name in the file} for the cells that were renamed."""
        return {k: v for k, v in self.name_map.items() if k != v}

    def klayout_name(self, file_name):
        """The KLayout name of a cell named ``file_name`` in the file."""
        for k, v in self.name_map.items():
            if v == file_name:
                return k
        return file_name

    def refusal(self):
        """Why a job must not run on this export, or None (design-0.6.md 2.6)."""
        if self.error_markers:
            return ("the layout holds PCell variants that failed (error marker 255/0 in %s); "
                    "Magic would check it without those devices" % ", ".join(self.error_markers))
        return None


# -- reading and naming cells -------------------------------------------------

def load_layout(path):
    """Read a layout file (anything KLayout reads)."""
    if not os.path.isfile(path):
        raise ExportError("cannot read %s: no such file" % path)
    ly = db.Layout()
    try:
        ly.read(path)
    except RuntimeError as e:
        raise ExportError("cannot read %s: %s" % (path, str(e).splitlines()[0] if str(e) else e))
    return ly


def top_cells(layout):
    return [c for c in layout.top_cells()]


def resolve_cells(layout, names):
    """The cells ``names`` names, in that order, without repeats. With no
    names, the layout's one top cell; several top cells need a name."""
    names = [n for n in (names or []) if n is not None]
    if not names:
        tops = top_cells(layout)
        if len(tops) == 1:
            return tops
        if not tops:
            raise ExportError("the layout has no cells")
        tnames = sorted(c.name for c in tops)
        raise ExportError("the layout has %d top cells (%s); choose one with --cell"
                          % (len(tnames), ", ".join(tnames)), tops=tnames)
    out, missing = [], []
    for n in names:
        c = layout.cell(n)
        if c is None:
            missing.append(n)
        elif c not in out:
            out.append(c)
    if missing:
        raise ExportError("cell%s %s %s not in the layout" % (
            "s" if len(missing) > 1 else "", ", ".join(missing), "are" if len(missing) > 1 else "is"),
            missing=missing)
    return out


def safe_name(name, taken):
    """A name of ``[A-Za-z0-9_$]`` for ``name``, not in ``taken``."""
    base = re.sub(r"[^A-Za-z0-9_$]", "_", name) or "cell"
    if base not in taken:
        return base
    i = 1
    while "%s_%d" % (base, i) in taken:
        i += 1
    return "%s_%d" % (base, i)


def save_options(cell):
    o = db.SaveLayoutOptions()
    o.format = "GDS2"
    o.write_context_info = False
    o.gds2_write_timestamps = False
    o.select_cell(cell.cell_index())
    return o


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 16), b""):
            h.update(block)
    return h.hexdigest()


def _tree(layout, top):
    return [top] + [layout.cell(ci) for ci in top.called_cells()]


def _copy_tree(layout, cell):
    """The cell's tree in a new layout, PCell variants as plain cells. The
    copy is made in memory, not through a file: KLayout's GDS writer turns
    "a b" into "a$b" and "café" into "caf$$", which would lose the names."""
    copy = db.Layout()
    copy.dbu = layout.dbu
    top = copy.create_cell(cell.name)
    top.copy_tree(cell)
    names = {layout.cell(ci).name for ci in cell.called_cells()} | {cell.name}
    lost = sorted(n for n in names if copy.cell(n) is None)
    if lost:
        raise ExportError("copying %s renamed the cells %s" % (cell.name, ", ".join(lost)))
    return copy, top


# -- the PDK data -------------------------------------------------------------

def _data_value(data, key, default=None):
    """A top-level key of the PDK data: an attribute, else the parsed JSON."""
    if data is None:
        return default
    v = getattr(data, key, None)
    if v is not None and not callable(v):
        return v
    for attr in ("json", "raw", "data", "doc"):
        obj = getattr(data, attr, None)
        if isinstance(obj, dict) and key in obj:
            return obj[key]
    if isinstance(data, dict):
        return data.get(key, default)
    return default


def _layer_record(data, l, d):
    if data is None:
        return None
    try:
        return data.layer(l, d)
    except (KeyError, LookupError, ValueError):
        return None


def error_marker_layer(data):
    m = _data_value(data, "error_marker")
    try:
        return int(m[0]), int(m[1])
    except (TypeError, ValueError, IndexError):
        return PLACEHOLDER_LAYER


def _layers(layout, data):
    """[(layer index, gds layer, gds datatype, record or None)]."""
    out = []
    for li in layout.layer_indexes():
        info = layout.get_info(li)
        out.append((li, info.layer, info.datatype, _layer_record(data, info.layer, info.datatype)))
    return out


def layer_text(l, d, rec=None):
    name = (rec or {}).get("name") if isinstance(rec, dict) else None
    return "%d/%d (%s)" % (l, d, name) if name else "%d/%d" % (l, d)


def _read_of(rec):
    return (rec or {}).get("read", "") if isinstance(rec, dict) else ""


def _role_of(rec):
    return (rec or {}).get("role", "") if isinstance(rec, dict) else ""


# -- what Magic changes ---------------------------------------------------------

def _error_markers(layout, top, marker):
    li = layout.find_layer(marker[0], marker[1])
    if li is None:
        return []
    return sorted(c.name for c in _tree(layout, top) if c.shapes(li).size() > 0)


def _complex_reason(inst, child):
    t = inst.cplx_trans
    parts = []
    if abs(t.angle - 90.0 * round(t.angle / 90.0)) > 1e-9:
        parts.append("rotated %g°" % t.angle)
    if t.is_mag():
        parts.append("magnified %g" % t.mag)
    d = inst.dcplx_trans.disp
    return ("instance of %s at (%g, %g) %s: Magic can't place it, so it is flattened"
            % (child, d.x, d.y, " and ".join(parts) or "with a complex transform"))


def _flatten_complex(layout, top):
    """Flatten every instance Magic can't place. Returns [(cell, reason)]."""
    out = []
    for cell in _tree(layout, top):
        while True:
            inst = next((i for i in cell.each_inst() if i.is_complex()), None)
            if inst is None:
                break
            out.append((cell.name, _complex_reason(inst, layout.cell(inst.cell_index).name)))
            inst.flatten()
    return out


def _dbox(box, dbu):
    return db.DBox(box.left * dbu, box.bottom * dbu, box.right * dbu, box.top * dbu)


def _shape_boxes(layout, top, li):
    """Boxes of a layer's shapes through the hierarchy: one per merged
    polygon, and one point per text."""
    dbu = layout.dbu
    out = []
    for p in db.Region(top.begin_shapes_rec(li)).merged().each():
        out.append(_dbox(p.bbox(), dbu))
    it = top.begin_shapes_rec(li)
    it.shape_flags = db.Shapes.STexts
    while not it.at_end():
        b = it.shape().bbox().transformed(it.trans())
        out.append(_dbox(b, dbu))
        it.next()
    return out


def _offgrid(layout, top, layers, grid_um, skip):
    """(layer text, DBox) for each vertex off the grid, of layers Magic reads."""
    if not grid_um:
        return []
    ratio = grid_um / layout.dbu
    g = int(round(ratio))
    if g <= 1 or abs(ratio - g) > 1e-6:
        # A database unit at or above the grid, or one the grid isn't a
        # multiple of: no vertex can be checked against it in integers.
        return []
    out = []
    for li, l, d, rec in layers:
        if (l, d) in skip:
            continue
        reg = db.Region(top.begin_shapes_rec(li))
        if reg.is_empty():
            continue
        seen = set()
        for ep in reg.grid_check(g, g).each():
            b = ep.bbox()
            key = (b.left, b.bottom, b.right, b.top)
            if key not in seen:
                seen.add(key)
                out.append((layer_text(l, d, rec), _dbox(b, layout.dbu)))
    return out


def _owned(layout, top, cell, li):
    """The shapes ``cell`` itself draws on ``li``, at every place it is
    used, in ``top``'s coordinates."""
    it = top.begin_shapes_rec(li)
    it.unselect_all_cells()
    it.select_cells([cell.cell_index()])
    return db.Region(it)


def _cross_cell(layout, top, layers):
    """Cross-cell findings: an implant, well or marker shape drawn in cell
    P over the device shapes of another cell X, seen through the instances:
    diffusion or poly under an implant or marker, diffusion only under a
    well (``device_roles``). P can be X's parent, child or sibling. Magic reads X
    without that layer, unless X draws it there itself. Returns (findings,
    covered): the overlaps X doesn't cover with its own shapes on that
    layer, and those it does."""
    imp = [(li, l, d, rec) for li, l, d, rec in layers if _role_of(rec) in IMPLANT_ROLES]
    if not imp:
        return [], []
    cells = _tree(layout, top)
    if len(cells) < 2:
        return [], []
    devs = {}

    def device_shapes(roles):
        """(cells drawing device shapes of ``roles``, {cell index: their merged region})."""
        if roles not in devs:
            dev = [li for li, l, d, rec in layers if _role_of(rec) in roles]
            owners = [c for c in cells if any(c.shapes(li).size() for li in dev)]
            region = {}
            for c in owners:
                r = db.Region()
                for li in dev:
                    if c.shapes(li).size():
                        r += _owned(layout, top, c, li)
                region[c.cell_index()] = r.merged()
            devs[roles] = (owners, region)
        return devs[roles]

    dbu = layout.dbu
    found, covered = [], []
    for li, l, d, rec in imp:
        owners = [c for c in cells if c.shapes(li).size()]
        if not owners:
            continue
        dev_owners, dev_region = device_shapes(device_roles(_role_of(rec)))
        if not dev_owners:
            continue
        if len(owners) == 1 and len(dev_owners) == 1 and owners[0] is dev_owners[0]:
            continue
        drawn = {c.cell_index(): _owned(layout, top, c, li).merged() for c in owners}
        name = (rec or {}).get("name") or layer_text(l, d)
        for x in dev_owners:
            xr = dev_region[x.cell_index()]
            own = drawn.get(x.cell_index())
            bare = (xr - own) if own is not None else xr
            for p in owners:
                if p.cell_index() == x.cell_index():
                    continue
                pr = drawn[p.cell_index()]
                if not pr.bbox().overlaps(xr.bbox()):
                    continue
                hit = (pr & bare).merged()
                for poly in hit.each():
                    found.append({"cell": x.name, "layer": name, "gds": [l, d], "drawn_in": p.name,
                                  "box": _dbox(poly.bbox(), dbu)})
                if hit.is_empty() and own is not None:
                    for poly in (pr & xr).merged().each():
                        covered.append({"cell": x.name, "layer": name, "gds": [l, d],
                                        "drawn_in": p.name, "box": _dbox(poly.bbox(), dbu)})
    return found, covered


def _drawn(layout, top, layers):
    """(gds layer, gds datatype, record) of every layer with a shape (a text
    included) in ``top``'s tree."""
    out = []
    for li, l, d, rec in layers:
        if not top.begin_shapes_rec(li).at_end():
            out.append((l, d, rec))
    return sorted(out, key=lambda x: (x[0], x[1]))


def _rename(layout, top):
    cells = _tree(layout, top)
    taken = {c.name for c in cells}
    name_map = {}
    for c in sorted(cells, key=lambda c: c.name):
        old = c.name
        if SAFE_NAME.match(old):
            name_map[old] = old
            continue
        new = safe_name(old, taken)
        taken.add(new)
        layout.rename_cell(c.cell_index(), new)
        name_map[old] = new
    return name_map


def export_cell(layout, cell, path, data, flat=False):
    """Write ``cell`` (a Cell of ``layout``, or its name) and its tree to
    ``path`` for Magic, and list what Magic will change; see the module's
    docstring. ``data`` is the PDK's ``pdkdata.PdkData`` (or None: no layer
    findings)."""
    if isinstance(cell, str):
        name = cell
        cell = layout.cell(name)
        if cell is None:
            raise ExportError("cell %s is not in the layout" % name, missing=[name])
    copy, top = _copy_tree(layout, cell)
    res = ExportResult()
    res.flat = bool(flat)
    res.dbu = copy.dbu
    res.klayout_top = cell.name
    marker = error_marker_layer(data)
    res.error_markers = _error_markers(copy, top, marker)
    res.flattened = _flatten_complex(copy, top)
    layers = _layers(copy, data)
    res.drawn = _drawn(copy, top, layers)
    res.bbox = top.dbbox()
    if data is not None:
        unread_layers = set()
        for li, l, d, rec in layers:
            read = _read_of(rec)
            if (l, d) == marker:
                continue
            if rec is None or read == "ignored":
                unread_layers.add((l, d))
                res.unread += [(l, d, b) for b in _shape_boxes(copy, top, li)]
            elif read.startswith("reads-as:"):
                mtype = read.split(":", 1)[1]
                res.reads_as += [(l, d, mtype, b) for b in _shape_boxes(copy, top, li)]
        gen = _data_value(data, "generated") or []
        res.regenerated = {tuple(g["gds"]) for g in gen if g.get("gds")} & unread_layers
        grid = _data_value(data, "grid_um")
        res.offgrid = _offgrid(copy, top, layers, grid, unread_layers | {marker})
        if not flat:
            res.cross_cell, res.cross_cell_covered = _cross_cell(copy, top, layers)
    if flat:
        top.flatten(True)
    res.name_map = _rename(copy, top)
    res.top = res.name_map[cell.name]
    copy.write(path, save_options(top))
    res.path = path
    res.sha256 = sha256_file(path)
    return res
