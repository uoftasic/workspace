"""The generated-layer check (design-0.6.md 3.3, 6.1 and 6.2).

Magic reads implants and markers only to decide what each piece of
diffusion and poly is, and draws its own when it writes GDS. This check
has Magic read the hierarchical export, write it back and extract a copy
it flattened itself (``tcl/kmp_rw.tcl``), and then compares, in KLayout:

- F1: an implant or marker that encloses a device shape by less than the
  distance Magic's gdsii output style grows that layer from the shape (the
  data file's ``generated`` rows with ``enclosure_check``). The device
  shapes are found on the user's file with the reading rules of
  ``data/devices-<pdk>.json``; the grow is zero across an edge that abuts
  the shape's exception types (the tech file's ``bloat-or ... 0``). Gaps
  Magic fills between two implant shapes are not F1. Magic's written shape
  is used only in the advice text.
- F2: a gate the user drew that Magic's extraction (of the flat copy, so in
  top-cell coordinates) makes into another device, two devices, or none.
- F3: conductor, poly or diffusion that Magic does not write back, and cuts
  with no Magic cut over them.
- F4: conductor that Magic writes and the user did not draw.
- F5: cuts Magic redrew (information).
- F6: the export's findings (off grid, unread layers, layers Magic reads as
  another type, cross-cell layers).

A cell Magic reads as empty (every layer it draws is one Magic's reader
ignores or reads only to decide device types) is a finding, status 1,
under "Export/Magic reads nothing in this cell", naming its layers; there
is nothing to compare. ``prepare`` never raises: an export that fails or is
refused, or reading rules that can't be read, give a Task whose outcome has
status 2, the reason in the RDB ("Job/failed") and the summary, and the
export's findings.

Every device Magic extracted is listed for information.

    python3 -m klayout_magic_pcells layers design.gds --cell my_inv -o layers.lyrdb
"""

import json
import os
import re
import shutil
import tempfile

from ._kl import db
from . import export as export_mod
from . import jobs as jobs_mod
from . import markers

SCRIPT = "kmp_rw.tcl"
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
FLAT_CELL = "kmp__flat"
TOL_UM = 0.001          # F1 tolerance
SLIVER_DBU = 1          # pieces narrower than 2 dbu are dropped

CAT_F1 = "F1 implant or marker stops short"
CAT_F1_INFO = "F1 Magic draws more of this layer here (information)"
CAT_F2 = "F2 transistor Magic reads as another device or none"
CAT_F3 = "F3 shape Magic drops"
CAT_F4 = "F4 conductor Magic adds"
CAT_F5 = "F5 cuts Magic redrew (information)"
CAT_DEVICES = "Devices Magic extracted (information)"
CAT_JOB = "Job/failed"
JOB_DESCRIPTION = "The check did not run; why, and what Magic said."
COUNTED = ("F1", "F2", "F3", "F4")
# The export's findings that set the status to 1 (design-0.6.md 3.3); the
# others are information in this check's report.
COUNTED_EXPORT = (markers.CAT_OFFGRID, markers.CAT_READS_AS, markers.CAT_CROSS_CELL)


class LayerCheckError(Exception):
    pass


# -- the reading rules ----------------------------------------------------------

_dev_cache = {}


def devices_path(pdk):
    return os.path.join(DATA_DIR, "devices-%s.json" % pdk)


def load_devices(pdk, path=None):
    """The reading rules of a PDK (``data/devices-<pdk>.json``)."""
    path = path or devices_path(pdk)
    if path in _dev_cache:
        return _dev_cache[path]
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError) as e:
        raise LayerCheckError("cannot read the reading rules %s: %s" % (path, e))
    if raw.get("schema") != 1 or raw.get("pdk") != pdk:
        raise LayerCheckError("%s is not schema 1 reading rules for %s" % (path, pdk))
    _dev_cache[path] = raw
    return raw


# -- regions -------------------------------------------------------------------

class Side:
    """One layout (the user's export or Magic's write-back), flattened through
    the hierarchy, as regions in a common database unit."""

    def __init__(self, layout, cell, dbu):
        self.layout = layout
        self.cell = cell
        self.dbu = dbu
        self._r = {}
        self._mag = None
        if abs(layout.dbu - dbu) > 1e-12:
            self._mag = db.ICplxTrans(layout.dbu / dbu)

    def region(self, ld):
        ld = (int(ld[0]), int(ld[1]))
        r = self._r.get(ld)
        if r is None:
            li = self.layout.find_layer(ld[0], ld[1])
            r = db.Region() if li is None else db.Region(self.cell.begin_shapes_rec(li))
            if self._mag is not None:
                r = r.transformed(self._mag)
            r.merge()
            self._r[ld] = r
        return r

    def texts(self, ld):
        li = self.layout.find_layer(int(ld[0]), int(ld[1]))
        out = []
        if li is None:
            return out
        it = self.cell.begin_shapes_rec(li)
        it.shape_flags = db.Shapes.STexts
        while not it.at_end():
            t = it.shape().text.transformed(it.trans())
            out.append(t)
            it.next()
        return out


def _layer_of(dev, name):
    ld = dev["layers"].get(name)
    if ld is None:
        raise LayerCheckError("the reading rules name an unknown layer %r" % name)
    return ld


class Evaluator:
    """Evaluates the reading rules' shape specs ({"of", "and", "not"}) on a Side."""

    def __init__(self, side, dev):
        self.side = side
        self.dev = dev
        self._d = {}

    def named(self, name):
        if name in self._d:
            return self._d[name]
        derived = self.dev.get("derived", {})
        shapes = self.dev.get("shapes", {})
        if name in derived:
            r = self.spec(derived[name])
        elif name in shapes:
            r = self.spec(shapes[name])
        else:
            r = self.side.region(_layer_of(self.dev, name))
        self._d[name] = r
        return r

    def spec(self, spec):
        r = db.Region()
        for n in spec.get("of", []):
            r += self.named(n)
        r.merge()
        for n in spec.get("and", []):
            r = r & self.named(n)
        for n in spec.get("not", []):
            r = r - self.named(n)
        return r.merged()


def _clean(r):
    """Drop slivers narrower than 2 dbu."""
    return r.sized(-SLIVER_DBU).sized(SLIVER_DBU).merged()


def _um(v, dbu):
    return int(round(v / dbu))


def _dbox(box, dbu):
    return db.DBox(box.left * dbu, box.bottom * dbu, box.right * dbu, box.top * dbu)


def _cap(text):
    if text[1:2].isupper():
        return text
    return text[:1].upper() + text[1:]


def _pt(x, y):
    return "(%.3f, %.3f)" % (x, y)


def _boxtext(b):
    return "%s-%s" % (_pt(b.left, b.bottom), _pt(b.right, b.top))


def magic_squares(region, size, space, dbu):
    """The cuts Magic's squares-grid would place in each cut polygon: their
    bounding box, centred in the polygon's box."""
    out = db.Region()
    s, sp = _um(size, dbu), _um(space, dbu)
    for p in region.each():
        b = p.bbox()
        boxes = []
        for lo, hi in ((b.left, b.right), (b.bottom, b.top)):
            w = hi - lo
            n = max(0, (w + sp) // (s + sp))
            if n == 0:
                boxes = None
                break
            ext = n * s + (n - 1) * sp
            c = lo + (w - ext) // 2
            boxes.append((c, c + ext))
        if boxes is None:
            out.insert(p)
        else:
            out.insert(db.Box(boxes[0][0], boxes[1][0], boxes[0][1], boxes[1][1]))
    return out.merged()


def coverage(gate, layer_region):
    """'all', 'none' or 'some': how much of ``gate`` (a Region) the layer covers."""
    a = gate.area()
    if a == 0:
        return "none"
    inter = (gate & layer_region).area()
    if inter == 0:
        return "none"
    if inter >= a:
        return "all"
    return "some"


def rule_matches(rule, cov):
    for key in ("all", "none", "some"):
        for n in rule.get(key, []):
            if cov.get(n) != key:
                return False
    for n in rule.get("any", []):
        if cov.get(n) not in ("all", "some"):
            return False
    return True


def first_match(rules, cov, **extra):
    for r in rules:
        if all(r.get(k) == v for k, v in extra.items()) and rule_matches(r, cov):
            return r
    return None


# -- Magic's .ext -------------------------------------------------------------

_DEV = re.compile(r"^device\s+(\S+)\s+(\S+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)(.*)$")
_PARAM = re.compile(r"\b([lw])=(-?[\d.]+)")


def read_ext_devices(path, scale):
    """[{"class", "model", "x", "y", "l", "w"}] from the device lines of a
    flat .ext file; positions and sizes in um (``scale`` um per unit)."""
    out = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = _DEV.match(line)
            if not m:
                continue
            p = dict((k, float(v) * scale) for k, v in _PARAM.findall(m.group(7)))
            out.append({"class": m.group(1), "model": m.group(2).strip('"'),
                        "x": int(m.group(3)) * scale, "y": int(m.group(4)) * scale,
                        "l": p.get("l"), "w": p.get("w")})
    return out


def _fet_class(dev, model):
    for cls, pat in dev["fets"]["models"].items():
        if re.search(pat, model):
            return cls
    return None


def _device_text(d):
    s = d["model"]
    if d.get("w") is not None and d.get("l") is not None:
        s += " W %.3f L %.3f" % (d["w"], d["l"])
    return s


# -- the comparison ----------------------------------------------------------------

def _gen_rows(data):
    rows = data.generated() if hasattr(data, "generated") else data.get("generated", [])
    return [r for r in rows if r.get("enclosure_check") and r.get("grow_um")]


def _layers_by_role(data, *roles):
    rows = data.layers if hasattr(data, "layers") else data.get("layers", [])
    return [r for r in rows if r.get("role") in roles and r.get("read") == "paint"]


def _name_of(data, ld):
    rec = data.layer(ld[0], ld[1]) if hasattr(data, "layer") else None
    return (rec or {}).get("name") or "%d/%d" % tuple(ld)


def compare(user, magic, devices, data, dev, cross_cell=(), dbu=None):
    """Compare the user's export (``user``, a Side) with Magic's write-back
    (``magic``, a Side, or None when only F2 runs) and Magic's flat device
    list. Returns {"F1": [...], ..., "F5": [...], "devices": [...]}, each
    finding a dict with "check", "layer", "box" (DBox, um), "text" and more."""
    dbu = dbu or user.dbu
    out = {"F1": [], "F2": [], "F3": [], "F4": [], "F5": [], "devices": [], "skipped": []}
    ev = Evaluator(user, dev)

    # F2 first: F1 skips the diffusions of changed devices.
    f2_gates = db.Region()
    fets = dev.get("fets")
    if fets:
        gates = ev.named(fets["gate"])
        cov_regions = dict((n, ev.named(n)) for n in fets.get("coverage", []))
        on_gate = set()
        dev_boxes = []
        for i, d in enumerate(devices):
            x, y = _um(d["x"], dbu), _um(d["y"], dbu)
            dev_boxes.append(db.Box(x - 1, y - 1, x + 1, y + 1))
        for gp in gates.each():
            g = db.Region(gp)
            gb = gp.bbox()
            here = [i for i, b in enumerate(dev_boxes) if b.overlaps(gb) and gp.sized(1).inside(b.center())]
            on_gate.update(here)
            cov = dict((n, coverage(g, r)) for n, r in cov_regions.items())
            intent = first_match(fets.get("intent", []), cov)
            read = first_match(fets.get("magic_reads", []), cov)
            found = [devices[i] for i in here]
            problem = None
            if not found:
                problem = "Magic's extraction has no device on it"
            elif len(found) > 1:
                problem = "Magic reads it as %d devices: %s" % (len(found), ", ".join(_device_text(d) for d in found))
            else:
                cls = _fet_class(dev, found[0]["model"])
                if intent and cls != intent["class"]:
                    problem = "it is %s, but Magic reads it as %s" % (intent["says"], _device_text(found[0]))
                elif intent:
                    var = first_match(fets.get("variants", []), cov, **{"class": cls})
                    if var:
                        m = found[0]["model"]
                        bad = (("model" in var and not re.search(var["model"], m))
                               or ("not_model" in var and re.search(var["not_model"], m)))
                        if bad:
                            problem = "%s, but Magic reads it as %s" % (var["says"], _device_text(found[0]))
            if problem is None:
                continue
            box = _dbox(gb, dbu)
            why = []
            hier = [c for c in cross_cell if c["box"].overlaps(box)]
            for c in hier:
                why.append("Magic reads cell %s without the %s drawn in cell %s" % (c["cell"], c["layer"], c["drawn_in"]))
            if not found:
                happened = "none"
            elif len(found) > 1:
                happened = "split"
            else:
                happened = _fet_class(dev, found[0]["model"])
            if not hier and read is not None and read.get("magic") == happened:
                why.append("%s (%s)" % (_cap(read["why"]), read["line"]))
                if read.get("fix"):
                    why.append("To fix it, %s" % read["fix"])
            text = "The gate at %s: %s." % (_pt(box.left, box.bottom), problem)
            if why:
                text += " " + ". ".join(why) + "."
            out["F2"].append({"check": "F2", "layer": "gate", "box": box, "text": text,
                              "devices": [_device_text(d) for d in found]})
            f2_gates.insert(gp)
        for i, d in enumerate(devices):
            x, y = d["x"], d["y"]
            out["devices"].append({"check": "device", "box": db.DBox(x, y, x + dbu * 10, y + dbu * 10),
                                   "text": "%s at %s%s" % (_device_text(d), _pt(x, y),
                                                           "" if i in on_gate or _fet_class(dev, d["model"]) is None
                                                           else "; no drawn gate here"),
                                   "model": d["model"]})

    if magic is None:
        return out

    diff_layers = [tuple(r["gds"]) for r in _layers_by_role(data, "diffusion")]
    changed = db.Region()
    for ld in diff_layers:
        changed += user.region(ld).interacting(f2_gates)

    # F3 and F4 on conductor, poly and diffusion; F3 and F5 on cuts.
    f3_diff = db.Region()
    for rec in _layers_by_role(data, "conductor", "poly", "diffusion"):
        ld = tuple(rec["gds"])
        u, m = user.region(ld), magic.region(ld)
        if u.is_empty() and m.is_empty():
            continue
        for p in _clean(u - m).each():
            box = _dbox(p.bbox(), dbu)
            if rec["role"] == "diffusion":
                f3_diff.insert(p)
            out["F3"].append({"check": "F3", "layer": rec["name"], "gds": list(ld), "box": box,
                              "text": "Magic does not write this %s (%d/%d) back: %.4f um2 at %s" % (
                                  rec["name"], ld[0], ld[1], p.area() * dbu * dbu, _boxtext(box))})
        if rec["role"] != "conductor":
            continue
        pins = _pin_layers(data, ld)
        for p in _clean(m - u).each():
            box = _dbox(p.bbox(), dbu)
            text = "Magic writes %s (%d/%d) here that you did not draw: %.4f um2 at %s" % (
                rec["name"], ld[0], ld[1], p.area() * dbu * dbu, _boxtext(box))
            pr = db.Region(p)
            under = [pl for pl in pins if not user.region(pl).interacting(pr).is_empty()]
            if under:
                text += ". A pin box on %s is there: %s (%s)" % (
                    ", ".join("%d/%d" % tuple(pl) for pl in under), dev.get("pins", {}).get("why", ""),
                    dev.get("pins", {}).get("line", ""))
            out["F4"].append({"check": "F4", "layer": rec["name"], "gds": list(ld), "box": box, "text": text})
    for cname, cut in sorted(dev.get("cuts", {}).items()):
        ld = tuple(_layer_of(dev, cname))
        u, m = user.region(ld), magic.region(ld)
        if u.is_empty():
            continue
        name = _name_of(data, ld)
        reach = _um(cut.get("space_um") or 0.1, dbu)
        dropped = db.Region()
        for p in u.each():
            pr = db.Region(p)
            if not m.interacting(pr.sized(reach)).is_empty():
                continue
            dropped.insert(p)
            box = _dbox(p.bbox(), dbu)
            miss = []
            for side in ("below", "above"):
                names = cut.get(side, [])
                if names and all(ev.named(n).interacting(pr).is_empty() for n in names):
                    miss.append(" or ".join(names))
            text = "Magic drops this %s cut at %s" % (name, _boxtext(box))
            if miss:
                text += "; there is no %s at it" % " and no ".join(miss)
            small = cut.get("size_um") and min(box.width(), box.height()) < cut["size_um"] - TOL_UM
            why = cut.get("why_small") if small and cut.get("why_small") else cut.get("why")
            imp = cut.get("implant")
            if imp and not miss and not small and _lacks_implant(ev, pr, imp):
                # The layers above and below are there: the diffusion under the cut has
                # no implant, so Magic gives it no contact type.
                text += ". %s (%s)" % (_cap(imp["why"]), imp.get("line", ""))
            elif why:
                text += ". %s (%s)" % (_cap(why), cut.get("line", ""))
            out["F3"].append({"check": "F3", "layer": name, "gds": list(ld), "box": box, "text": text})
        # F5: groups of nearby cuts where Magic's differ from the user's.
        kept = u - dropped
        for grp in (kept + m).merged().sized(reach // 2).merged().each():
            gr = db.Region(grp)
            uu, mm = kept.interacting(gr), m.interacting(gr)
            if uu.is_empty() or mm.is_empty() or _clean(uu ^ mm).is_empty():
                continue
            box = _dbox((uu + mm).bbox(), dbu)
            text = ("Magic redrew these %s cuts: you drew %d, Magic writes %d. Your file keeps your cuts, "
                    "which KLayout's deck checks" % (name, uu.count(), mm.count()))
            size, space = cut.get("size_um"), cut.get("space_um")
            if size and space:
                odd = [q for q in mm.each() if abs(q.bbox().width() * dbu - size) > TOL_UM
                       or abs(q.bbox().height() * dbu - size) > TOL_UM or not q.is_box()]
                close = mm.space_check(_um(space, dbu) - 1)
                if odd or not close.is_empty():
                    text += ("; Magic's own cuts here are not all %.3f um squares %.3f um apart, so its "
                             "output breaks the rule too" % (size, space))
                else:
                    text += "; Magic's cuts are %.3f um squares at least %.3f um apart (%s)" % (
                        size, space, cut.get("line", ""))
            out["F5"].append({"check": "F5", "layer": name, "gds": list(ld), "box": box, "text": text})

    # F1.
    skip = (changed + f3_diff).merged()
    f1_info = dev.get("f1", "check") != "check"
    for row in _gen_rows(data):
        spec = dev.get("shapes", {}).get(row["from"])
        if spec is None:
            out["skipped"].append("%s from %s: no shape in the reading rules" % (row["name"], row["from"]))
            continue
        d = ev.spec(spec)
        if spec.get("square_um"):
            d = magic_squares(d, spec["square_um"], spec.get("space_um", spec["square_um"]), dbu)
        d = d.not_interacting(skip) if not skip.is_empty() else d
        if d.is_empty():
            continue
        g = _um(row["grow_um"] - TOL_UM, dbu)
        edges = d.edges()
        butts = db.Region()
        for b in spec.get("butts", []):
            butts += ev.named(b)
        if not butts.is_empty():
            edges = edges.outside_part(butts.sized(1))
        need = edges.extended_out(g).merged()
        ld = tuple(row["gds"])
        miss = _clean(need - user.region(ld))
        if miss.is_empty():
            continue
        mag = magic.region(ld)
        u = user.region(ld)
        reach = _um(row["grow_um"], dbu) + 2
        for sp in d.each():
            src = db.Region(sp)
            mine = miss.interacting(src.sized(reach))
            if mine.is_empty():
                continue
            sbox = _dbox(sp.bbox(), dbu)
            mp = mag.interacting(src)
            text = "%s around the %s at %s stops short" % (row["name"], row["from"], _boxtext(sbox))
            if not mp.is_empty():
                left = (mp - u).area() * dbu * dbu
                text += (". Magic draws %s over %s here, %.3f um past the %s; your %s leaves %.4f um2 of "
                         "that uncovered" % (row["name"], _boxtext(_dbox(mp.bbox(), dbu)), row["grow_um"],
                                             row["from"], row["name"], left))
            else:
                text += ("; Magic draws %s %.3f um past the %s, and your %s leaves %.4f um2 of that "
                         "uncovered" % (row["name"], row["grow_um"], row["from"], row["name"],
                                        mine.area() * dbu * dbu))
            if row.get("rule_ids"):
                text += ". The rule is %s" % ", ".join(row["rule_ids"])
            text += " (%s:%s)" % (row.get("file") or "tech", row.get("line"))
            out["F1"].append({"check": "F1", "layer": row["name"], "gds": list(ld),
                              "box": _dbox(mine.bbox(), dbu), "text": text, "info": f1_info,
                              "rule_ids": row.get("rule_ids", [])})
    return out


def _lacks_implant(ev, cut, imp):
    """True when the cut lies on a layer of ``imp["over"]`` (diffusion or
    tap) and no layer of ``imp["any"]`` (the implants) touches it."""
    over = db.Region()
    for n in imp.get("over", []):
        over += ev.named(n)
    if over.interacting(cut).is_empty():
        return False
    return all(ev.named(n).interacting(cut).is_empty() for n in imp.get("any", []))


def _pin_layers(data, ld):
    p = data.ports() if hasattr(data, "ports") else data.get("ports", {})
    return [tuple(x) for x in p.get("pin", []) if x[0] == ld[0] and tuple(x) != tuple(ld)]


def counted(findings):
    """Findings that make the status 1: F1 to F4 (F1 only where it is a check)."""
    return sum(1 for k in COUNTED for f in findings.get(k, []) if not f.get("info"))


# -- the task ----------------------------------------------------------------

class Outcome:
    def __init__(self, status, rdb, summary, files=None, findings=None, headline=None):
        self.status = status
        self.rdb = rdb
        self.summary = summary
        self.headline = headline    # the GUI message's plain first line
        self.files = files or {}
        self.findings = findings or {}


_PLAIN = {
    "F1": ("implant or marker that stops short", "implants or markers that stop short"),
    "F2": ("transistor that Magic reads as another device or none",
           "transistors that Magic reads as other devices or none"),
    "F3": ("shape or cut that Magic drops", "shapes or cuts that Magic drops"),
    "F4": ("conductor shape that Magic adds", "conductor shapes that Magic adds"),
}


def headline(findings, er, cell):
    """The first line of the GUI's result message, in plain words: what the
    findings that set the status are (F1 to F4, and the export's off-grid,
    read-as-another-type and cross-cell findings), or that there are none."""
    parts = []
    for k in COUNTED:
        items = [f for f in findings.get(k, []) if not f.get("info")]
        if not items:
            continue
        one, many = _PLAIN[k]
        part = "%d %s" % (len(items), one if len(items) == 1 else many)
        if k in ("F1", "F3", "F4"):
            part += " (%s)" % ", ".join(sorted({f["layer"] for f in items}))
        parts.append(part)
    if er is not None:
        for n, one, many in ((len(er.offgrid), "vertex off Magic's grid", "vertices off Magic's grid"),
                             (len(er.reads_as), "shape on a layer Magic reads as another type",
                              "shapes on layers Magic reads as another type"),
                             (len(er.cross_cell), "place where Magic reads a cell without a layer drawn in "
                              "another cell", "places where Magic reads a cell without a layer drawn in "
                              "another cell")):
            if n:
                parts.append("%d %s" % (n, one if n == 1 else many))
    if not parts:
        return "No generated-layer findings in %s." % cell
    return "In %s: %s." % (cell, "; ".join(parts))


def generator_for(params):
    if hasattr(markers, "recipe_generator"):
        try:
            return markers.recipe_generator(params)
        except Exception:
            return ""
    return ""


def _new_rdb(name, what, cell_name, pdk, params, command):
    desc = "%s of cell %s on %s (%s)" % (what, cell_name, pdk, command)
    return markers.Rdb(name, desc, generator_for(params), cell_name)


def job_files(job_dir):
    """Outcome.files' entries for the job directory: "job_dir", and "job",
    its name before 0.6 (kept for one version)."""
    return {"job_dir": job_dir, "job": job_dir}


def _cached(job_dir, outputs):
    meta = os.path.join(job_dir, "job.json")
    try:
        with open(meta, encoding="utf-8") as f:
            if json.load(f).get("state") != "done":
                return False
    except (OSError, ValueError):
        return False
    return all(os.path.exists(os.path.join(job_dir, o)) for o in outputs)


def _read_scale(job_dir):
    try:
        with open(os.path.join(job_dir, "rw_times.txt"), encoding="utf-8") as f:
            for line in f:
                t = line.split()
                if len(t) == 2 and t[0] == "scale":
                    return float(t[1])
    except (OSError, ValueError):
        pass
    return None


class RwTask:
    """Export, run kmp_rw.tcl, then hand the job directory to ``finish``.
    Shared by layercheck and portcheck (--magic)."""

    outputs = ("rw.gds", FLAT_CELL + ".ext")

    def __init__(self, layout, cell, cfg, data, options, mode="rw"):
        self.layout = layout
        self.cell = cell if not isinstance(cell, str) else layout.cell(cell)
        self.cell_name = cell if isinstance(cell, str) else getattr(cell, "name", "?")
        self.cfg = cfg
        self.data = data
        self.options = dict(options or {})
        self.mode = mode
        self.stage = None
        self._job = None
        self._outcome = None
        self._started = False
        self.job_dir = None
        self.cached = False
        self.er = None
        # Why the check can't run, found in prepare(); the subclass turns it
        # into a failed outcome once its own set-up is done (early_outcome).
        self.early = None
        self.tmp = tempfile.mkdtemp(prefix="kmp-%s-" % mode)
        self.export_path = os.path.join(self.tmp, "in.gds")
        try:
            if self.cell is None:
                raise export_mod.ExportError("cell %s is not in the layout" % cell, missing=[cell])
            self.er = export_mod.export_cell(layout, self.cell, self.export_path, data)
        except export_mod.ExportError as e:
            self.early = str(e)
        except RuntimeError as e:  # KLayout could not copy or write the cell
            self.early = "cannot export cell %s: %s" % (self.cell_name, str(e).splitlines()[0] if str(e) else e)

    def early_outcome(self):
        """Set the failed outcome when prepare() found a reason the check
        can't run (the export failed or was refused, the reading rules
        can't be read). The GUI then shows the RDB like any other."""
        if self.early is None and self.er is not None and self.mode != "ports":
            self.early = self.er.refusal()
        if self.early is not None and self._outcome is None:
            self._outcome = self.fail(self.early)
        return self._outcome

    def _outputs(self):
        return self.outputs if self.mode == "rw" else ("%s.spice" % self.er.top,)

    def start(self):
        if self._started or self._outcome is not None:
            return self
        self._started = True
        refusal = self.er.refusal()
        if refusal:
            self._outcome = self.fail(refusal)
            return self
        key = jobs_mod.job_cache_key(self.er.sha256, "rw", {"top": self.er.top, "mode": self.mode}, self.cfg)
        try:
            # The key's directory, or with KMP_CACHE=0 or no_cache a new tmp-* one.
            jd, caching = jobs_mod.job_dir(self.cfg, "rw", key, self.options)
        except jobs_mod.JobError as e:
            self._outcome = self.fail(str(e))
            return self
        self.job_dir = jd
        if caching and _cached(jd, self._outputs()):
            self.cached = True
            return self
        try:
            self._job = jobs_mod.MagicJob(self.cfg, "rw", SCRIPT, env={"KMP_TOP": self.er.top, "KMP_RW_MODE": self.mode},
                                          files={"in.gds": self.export_path},
                                          timeout=self.options.get("timeout"), job_dir=jd,
                                          required=self._outputs())
            self._job.start()
        except jobs_mod.JobError as e:
            self._outcome = self.fail(str(e))
        return self

    def poll(self):
        if self._outcome is not None:
            return self._outcome
        if not self._started:
            self.start()
            if self._outcome is not None:
                return self._outcome
        if self.cached:
            self._outcome = self._finish_dir(self.job_dir, _read_scale(self.job_dir), [])
            return self._outcome
        r = self._job.poll()
        self.stage = self._job.stage
        if r is None:
            return None
        if not r.ok and markers.empty_cell_error(r.error, self.er.top):
            # Magic's reader kept none of the cell's shapes: a finding, not a failed job.
            self.job_dir = r.dir
            self._outcome = self.reads_nothing(r)
            self.cleanup()
            return self._outcome
        if not r.ok:
            self._outcome = self.fail("Magic's job failed: %s" % r.error, r)
            return self._outcome
        self.job_dir = r.dir
        self._outcome = self._finish_dir(r.dir, r.scale, r.stdout)
        return self._outcome

    def wait(self):
        if not self._started:
            self.start()
        if self._job is not None and self._outcome is None:
            self._job.wait()
        out = self.poll()
        return out

    def cancel(self):
        if self._job is not None:
            self._job.cancel()
        if self._outcome is None:
            self._outcome = self.fail("cancelled")

    def _finish_dir(self, job_dir, scale, stdout):
        if scale is None:
            return self.fail("Magic printed no scale (KMP_JOB_SCALE)")
        # The job directory holds its own copy of the export (in.gds).
        self.export_path = os.path.join(job_dir, "in.gds")
        try:
            return self.finish(job_dir, scale, stdout)
        except (LayerCheckError, OSError, RuntimeError) as e:
            return self.fail("reading Magic's results failed: %s" % e)
        finally:
            self.cleanup()

    def cleanup(self):
        """Remove the export's temporary folder (the job directory keeps its copy)."""
        if not (self.tmp and os.path.isdir(self.tmp)):
            return
        if self._job is not None and self._job.pid is not None and self._job.poll() is None:
            return  # Magic still runs
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.tmp = None

    def failed(self, prefix, why, result=None):
        """The Outcome of a check that did not run (status 2): the reason
        under "Job/failed", and the export's findings when there is an
        export (a refused layout's error-marker cells, for example)."""
        rdb = self._rdb()
        rdb.info(rdb.category(CAT_JOB, JOB_DESCRIPTION), why)
        if self.er is not None:
            markers.add_export_findings(rdb, self.er)
        if result is not None:
            markers.add_magic_said(rdb, result.stdout[-40:])
        self.cleanup()
        files = job_files(self.job_dir) if self.job_dir else {}
        export = os.path.join(self.job_dir, "in.gds") if self.job_dir else self.export_path
        if os.path.isfile(export):
            files["export"] = export
        return Outcome(2, rdb, "%s: %s" % (prefix, why), files)

    def magic_lines(self, result):
        """What Magic printed, without the protocol and its every-run lines."""
        from .drcjob import magic_said
        return magic_said(result.stdout, result.stderr)

    # subclasses
    def fail(self, why, result=None):
        raise NotImplementedError

    def reads_nothing(self, result):
        raise NotImplementedError

    def finish(self, job_dir, scale, stdout):
        raise NotImplementedError


class Task(RwTask):
    """The layers check of one cell."""

    def __init__(self, layout, cell, cfg, data, options):
        RwTask.__init__(self, layout, cell, cfg, data, options, mode="rw")
        options = options or {}
        self.command = options.get("command") or "layers %s --cell %s" % (options.get("file", "<layout>"),
                                                                        self.cell_name)
        self.params = {"cmd": "layers", "file": options.get("file", ""), "cell": self.cell_name}
        self.dev = None
        try:
            self.dev = load_devices(cfg.pdk if getattr(cfg, "pdk", None) else data.pdk)
        except LayerCheckError as e:
            self.early = self.early or str(e)
        self.early_outcome()

    def _rdb(self):
        cell = self.er.klayout_top if self.er is not None else self.cell_name
        pdk = getattr(self.data, "pdk", None) or getattr(self.cfg, "pdk", "?")
        return _new_rdb("layers", "Magic's generated-layer check", cell, pdk, self.params, self.command)

    def reads_nothing(self, result):
        """Magic read the cell as empty: the finding, status 1."""
        rdb = self._rdb()
        text = markers.add_reads_nothing(rdb, self.er, data=self.data)
        markers.add_export_findings(rdb, self.er, counted=COUNTED_EXPORT)
        markers.add_magic_said(rdb, self.magic_lines(result))
        findings = {"F1": [], "F2": [], "F3": [], "F4": [], "F5": [], "devices": [], "skipped": [],
                    "empty": [{"check": "empty", "layer": None, "box": self.er.bbox, "text": text}]}
        summary = "%s; %s, so there is nothing to compare (category %s)" % (
            summary_text(findings, self.er, self.data.pdk), text, markers.CAT_READS_NOTHING)
        files = dict(job_files(result.dir))
        export = os.path.join(result.dir, "in.gds")
        if os.path.isfile(export):
            files["export"] = export
        return Outcome(1, rdb, summary, files, findings,
                       headline="Magic reads nothing in %s, so there is nothing to compare." % self.er.klayout_top)

    def fail(self, why, result=None):
        return self.failed("layers", why, result)

    def finish(self, job_dir, scale, stdout):
        rw = os.path.join(job_dir, "rw.gds")
        ext = os.path.join(job_dir, FLAT_CELL + ".ext")
        ul = db.Layout()
        ul.read(self.export_path)
        ml = db.Layout()
        ml.read(rw)
        ucell, mcell = ul.cell(self.er.top), ml.cell(self.er.top)
        if ucell is None or mcell is None:
            raise LayerCheckError("cell %s is missing from %s" % (self.er.top, rw if mcell is None else self.export_path))
        user = Side(ul, ucell, ul.dbu)
        magic = Side(ml, mcell, ul.dbu)
        devices = read_ext_devices(ext, scale)
        findings = compare(user, magic, devices, self.data, self.dev, self.er.cross_cell, ul.dbu)
        rdb = self._rdb()
        fill_rdb(rdb, findings, self.er.klayout_top)
        markers.add_export_findings(rdb, self.er, counted=COUNTED_EXPORT)
        n = counted(findings)
        f6 = len(self.er.offgrid) + len(self.er.reads_as) + len(self.er.cross_cell)
        status = 1 if (n or f6) else 0
        summary = summary_text(findings, self.er, self.data.pdk)
        files = dict(job_files(job_dir), **{"rw.gds": rw, "ext": ext, "export": self.export_path})
        return Outcome(status, rdb, summary, files, findings, headline(findings, self.er, self.er.klayout_top))


_CAT = {"F1": CAT_F1, "F2": CAT_F2, "F3": CAT_F3, "F4": CAT_F4, "F5": CAT_F5}
_DESC = {
    "F1": "An implant or marker that encloses a device shape by less than the distance Magic's GDS output "
          "grows it. Magic's DRC does not check these layers (it draws its own on output), so only the "
          "user's file breaks the rule.",
    "F2": "A gate the user drew that Magic's extraction makes into another device, two devices or none.",
    "F3": "Conductor, poly, diffusion or cuts in the user's file that Magic does not write back.",
    "F4": "Conductor Magic writes that the user's file does not have.",
    "F5": "Cuts Magic replaced with its own (merged, resized or re-arrayed).",
}


def fill_rdb(rdb, findings, cell):
    for k in ("F1", "F2", "F3", "F4", "F5"):
        for f in findings.get(k, []):
            if k == "F1" and f.get("info"):
                path = (CAT_F1_INFO, f["layer"])
            elif k == "F2":
                path = (_CAT[k],)
            else:
                path = (_CAT[k], f["layer"])
            cat = rdb.category(path)
            rdb.category((path[0],), _DESC.get(k, ""))
            rdb.item(cat, cell, f["box"], f["text"], info=k == "F5" or bool(f.get("info")))
    for d in findings.get("devices", []):
        rdb.item(rdb.category((CAT_DEVICES,), "Every device in Magic's extraction of its own flattened "
                              "copy, with its model, W and L."), cell, d["box"], d["text"], info=True)


def summary_text(findings, er, pdk):
    parts = ["%s %d" % (k, len(findings.get(k, []))) for k in COUNTED]
    s = "layers on %s, cell %s: %s; F5 %d (information); %d devices in Magic's extraction" % (
        pdk, er.klayout_top, ", ".join(parts), len(findings.get("F5", [])), len(findings.get("devices", [])))
    if any(f.get("info") for f in findings.get("F1", [])):
        s += "; F1 is information only on %s" % pdk
    f6 = len(er.offgrid) + len(er.unread) + len(er.reads_as) + len(er.cross_cell)
    if f6:
        s += "; export: %d off grid, %d on unread layers, %d read as another type, %d cross-cell" % (
            len(er.offgrid), len(er.unread), len(er.reads_as), len(er.cross_cell))
    return s


def findings_json(outcome, pdk, file, cell):
    def box(b):
        return [round(b.left, 4), round(b.bottom, 4), round(b.right, 4), round(b.top, 4)]
    items = []
    for k in ("F1", "F2", "F3", "F4", "F5"):
        for f in outcome.findings.get(k, []):
            items.append({"check": k, "layer": f.get("layer"), "box": box(f["box"]), "text": f["text"],
                          "information": bool(f.get("info")) or k == "F5"})
    for f in outcome.findings.get("empty", []):
        items.append({"check": "empty", "layer": None, "box": box(f["box"]) if f.get("box") else None,
                      "text": f["text"], "information": False})
    return {"schema": 1, "pdk": pdk, "file": file, "cell": cell, "status": outcome.status,
            "summary": outcome.summary, "findings": items,
            "devices": [d["text"] for d in outcome.findings.get("devices", [])]}


def prepare(layout, cell, cfg, data, options):
    return Task(layout, cell, cfg, data, options)


def cli_main(args, ctx):
    import sys
    cell = ctx.cells[0]
    cmd = "python3 -m klayout_magic_pcells layers %s --cell %s --pdk %s" % (ctx.file, cell.name, ctx.pdk)
    # prepare() does not raise: a failed export is an outcome with status 2.
    task = prepare(ctx.layout, cell, ctx.cfg, ctx.data,
                   {"no_cache": getattr(args, "no_cache", False), "file": ctx.file, "command": cmd})
    out = task.wait()
    try:
        if getattr(args, "output", None):
            out.rdb.save(args.output)
        if getattr(args, "json", None):
            with open(args.json, "w", encoding="utf-8") as f:
                json.dump(findings_json(out, ctx.pdk, ctx.file, cell.name), f, indent=1)
                f.write("\n")
        sys.stderr.write(out.summary + "\n")
        for k in ("F1", "F2", "F3", "F4", "F5"):
            for f in out.findings.get(k, []):
                sys.stdout.write("%s %s: %s\n" % (k, f.get("layer"), f["text"]))
        for f in out.findings.get("empty", []):
            sys.stdout.write("Export: %s\n" % f["text"])
    finally:
        jobs_mod.release(out)
    return out.status
