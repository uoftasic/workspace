"""Shared pieces of the case-suite builders: a drawing that collects shapes,
GDS writing with the export's options, and the case record.

Every builder draws in micrometres on a 1 nm database unit, as the gap
studies' scripts did. Nothing here needs Magic.
"""

import json
import os
import re

import klayout.db as db

DBU = 0.001
SAFE_NAME = re.compile(r"^[A-Za-z0-9_$]+$")


def save_options(cell=None):
    """The export's options: no context information, no timestamps, and only
    ``cell``'s tree when one is given."""
    o = db.SaveLayoutOptions()
    o.write_context_info = False
    o.gds2_write_timestamps = False
    if cell is not None:
        o.select_cell(cell.cell_index())
    return o


def write_gds(layout, path, cell=None):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    layout.write(path, save_options(cell))
    return path


def new_layout():
    ly = db.Layout()
    ly.dbu = DBU
    return ly


class Drawing:
    """Shapes on named layers, in um. ``layers`` maps a name to (layer,
    datatype). Boxes are (x1, y1, x2, y2) in any corner order; polygons are
    lists of (x, y) points; a polygon given as one point list that returns
    to its start and continues is drawn with KLayout's hole convention."""

    def __init__(self, layers):
        self.layers = layers
        self.items = []   # (kind, layer name, data)

    def box(self, layer, x1, y1, x2, y2):
        self.items.append(("box", layer, (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))))

    def poly(self, layer, pts):
        self.items.append(("poly", layer, [tuple(p) for p in pts]))

    def text(self, layer, s, x, y):
        self.items.append(("text", layer, (s, x, y)))

    def shape(self, layer, geom):
        """A box tuple or a point list, as the gap studies' tables hold them."""
        if isinstance(geom[0], (tuple, list)):
            self.poly(layer, geom)
        else:
            self.box(layer, *geom)

    def emit(self, layout, cell):
        for kind, layer, data in self.items:
            li = layout.layer(*self.layers[layer])
            if kind == "box":
                cell.shapes(li).insert(db.DBox(*data))
            elif kind == "poly":
                cell.shapes(li).insert(db.DPolygon([db.DPoint(x, y) for x, y in data]))
            else:
                s, x, y = data
                cell.shapes(li).insert(db.DText(s, db.DTrans(db.DVector(x, y))))
        return cell


def case(name, top, set_name, file, targets=(), expect=None, notes="", source="", **extra):
    """One cases.json record (tests/cases/README.md), plus any extra keys."""
    rec = {"name": name, "file": file, "top": top, "set": set_name,
           "targets": list(targets), "expect": expect or {}, "notes": notes, "source": source}
    rec.update(extra)
    return rec


def safe_cell_name(name):
    """A cell name Magic loads as itself (design-0.6.md 2.2): '.' and every other
    character outside [A-Za-z0-9_$] become '_'."""
    out = re.sub(r"[^A-Za-z0-9_$]", "_", name)
    assert SAFE_NAME.match(out), name
    return out


def load_expect(pdk):
    """The measured results transcribed from the gap studies' evidence
    (README "Where expect comes from"), keyed by case name."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "expect-%s.json" % pdk)
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def split_hierarchy(layout, flat, parent_name, child_name, moved):
    """A two-level cell (design-0.6.md 3.1): the shapes of ``flat`` on the (layer, datatype)
    pairs in ``moved`` go into a new cell ``parent_name``; everything else
    goes into ``child_name``, placed in the parent at the origin. ``flat`` is
    left as it is (it is the flat original)."""
    moved = {tuple(x) for x in moved}
    child = layout.create_cell(child_name)
    parent = layout.create_cell(parent_name)
    for li in layout.layer_indexes():
        info = layout.get_info(li)
        tgt = parent if (info.layer, info.datatype) in moved else child
        tgt.shapes(li).insert(flat.shapes(li))
    parent.insert(db.CellInstArray(child.cell_index(), db.Trans()))
    return parent, child


def read_back(path):
    """Read a written GDS file back; returns the layout (raises on failure)."""
    ly = db.Layout()
    ly.read(path)
    return ly
