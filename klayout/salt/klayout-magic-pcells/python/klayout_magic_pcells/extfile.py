"""Reading Magic's ``.ext`` files, to put netgen's findings on the layout.

An extraction job (``tcl/kmp_extract.tcl``) leaves one ``<cell>.ext`` per
cell in its directory. This module reads the lines that locate things:

    scale 1000 1 500000
    use sky130_fd_pr__nfet_01v8__kmp_e044c2db sky130_fd_pr__nfet_01v8__kmp_e044c2db_0 1 0 280 0 1 280
    port "Y" 3 450 520 500 570 li
    node "a_300_260#" 229 0 300 260 ndif 0 0 ...
    substrate "VGND" 1104 0 240 10 m1 0 0 ...
    merge "VSUBS" "VGND"
    device msubckt sky130_fd_pr__nfet_01v8 270 260 271 261 l=30 w=130 "VGND" "A" 60 0 ...

Coordinates are in Magic's internal units. Their length in µm is the
``KMP_JOB_SCALE`` that the job printed from the same Magic process
(``JobResult.scale``, Magic's ``cif scale out``), never the ``scale`` line:
that line's third number is 500000 on sky130A and 0.5 on gf180mcuD and both
IHP PDKs, while a unit is 0.005 µm on all four (design-0.6.md 3.2, 6.5). The
``scale`` line is kept only as information.

A ``use`` line is ``use <cell> <id> a b c d e f``: a point (x, y) of the
child is at (a·x + b·y + c, d·x + e·y + f) in the parent. An array's id
carries ``[xlo:xhi:xsep][ylo:yhi:ysep]``; element (i, j) adds
((i - xlo)·xsep, (j - ylo)·ysep) to the child's point before the
transform. This was measured on all four PDKs against KLayout's placement
of the same file: a child in all eight orientations and a 3 × 2 array, every
node point on its own placement (the use-line table of
``tests/unit/test_extfile.py``; design-0.6.md 3.2).

A node's point is the lower left corner of its first tile, on a shape of
the net; a device's is a point inside its channel or body.
"""

import os
import re

_TOKEN = re.compile(r'"((?:[^"\\]|\\.)*)"|(\S+)')
_ARRAY = re.compile(r"\[(-?\d+):(-?\d+):(-?\d+)\]")
# Magic writes an infinite substrate's position as a huge negative number.
_NO_POSITION = 1 << 29


class ExtError(Exception):
    pass


def _tokens(line):
    """[(text, quoted)] of one line."""
    return [(m.group(1), True) if m.group(1) is not None else (m.group(2), False)
            for m in _TOKEN.finditer(line)]


class Port:
    def __init__(self, name, index, box, type_):
        self.name = name
        self.index = index
        self.box = box          # (l, b, r, t) in units
        self.type = type_       # Magic type: li, m1, ...

    def __repr__(self):
        return "Port(%r, %r, %s)" % (self.name, self.box, self.type)


class Node:
    def __init__(self, name, x, y, type_, substrate=False):
        self.name = name
        self.x = x              # units, or None (an infinite substrate)
        self.y = y
        self.type = type_
        self.substrate = substrate

    @property
    def point(self):
        return None if self.x is None else (self.x, self.y)

    def __repr__(self):
        return "Node(%r, %r, %r, %s)" % (self.name, self.x, self.y, self.type)


class Device:
    def __init__(self, cls, model, x, y, params, terminals, index):
        self.cls = cls              # msubckt, fet, rsubckt, ...
        self.model = model
        self.x = x
        self.y = y
        self.params = params        # {"l": "30", "w": "130"}, in units where Magic gives lengths
        self.terminals = terminals  # net names in the line's order (the substrate first for FETs)
        self.index = index          # its place among the cell's device lines

    @property
    def point(self):
        return (self.x, self.y)

    def __repr__(self):
        return "Device(%s %s at %d,%d %r)" % (self.cls, self.model, self.x, self.y, self.terminals)


class Use:
    def __init__(self, cell, id_, trans, array=None):
        self.cell = cell
        self.id = id_               # without the array part
        self.trans = trans          # (a, b, c, d, e, f)
        self.array = array          # (xlo, xhi, xsep, ylo, yhi, ysep) or None

    def apply(self, x, y, i=None, j=None):
        """A child point (units) in the parent, for array element (i, j)."""
        if self.array:
            xlo, _xhi, xsep, ylo, _yhi, ysep = self.array
            x += ((xlo if i is None else i) - xlo) * xsep
            y += ((ylo if j is None else j) - ylo) * ysep
        a, b, c, d, e, f = self.trans
        return a * x + b * y + c, d * x + e * y + f

    def elements(self):
        """Every (i, j) of an array, or [(None, None)]."""
        if not self.array:
            return [(None, None)]
        xlo, xhi, _xs, ylo, yhi, _ys = self.array
        xs = range(xlo, xhi + 1) if xhi >= xlo else range(xlo, xhi - 1, -1)
        ys = range(ylo, yhi + 1) if yhi >= ylo else range(ylo, yhi - 1, -1)
        return [(i, j) for i in xs for j in ys]

    def __repr__(self):
        return "Use(%s %s %r %r)" % (self.cell, self.id, self.trans, self.array)


class ExtCell:
    """One ``.ext`` file."""

    def __init__(self, name):
        self.name = name
        self.path = None
        self.scale_line = None      # the three numbers of the scale line, as information
        self.tech = None
        self.ports = []
        self.nodes = {}
        self.substrate = []         # the substrate nodes (also in nodes)
        self.devices = []
        self.uses = []
        self.merges = []            # (a, b)

    def port(self, name):
        for p in self.ports:
            if p.name == name:
                return p
        return None

    def use(self, id_):
        """The use whose id is ``id_``, or None."""
        for u in self.uses:
            if u.id == id_:
                return u
        return None

    def aliases(self, name):
        """``name`` and every name merged with it in this cell, nearest first."""
        adj = {}
        for a, b in self.merges:
            adj.setdefault(a, []).append(b)
            adj.setdefault(b, []).append(a)
        seen, order, todo = {name}, [name], [name]
        while todo:
            n = todo.pop(0)
            for m in adj.get(n, ()):
                if m not in seen:
                    seen.add(m)
                    order.append(m)
                    todo.append(m)
        return order


def _int(text):
    try:
        return int(text)
    except ValueError:
        return int(float(text))


def parse(text, name=None):
    """An ExtCell from the text of an ``.ext`` file."""
    cell = ExtCell(name)
    for lineno, line in enumerate(text.splitlines(), 1):
        if not line or line[0] == "#":
            continue
        head = line.split(None, 1)[0]
        if head not in ("scale", "tech", "use", "port", "node", "substrate", "device", "merge"):
            continue
        toks = _tokens(line)
        vals = [t for t, _q in toks]
        try:
            if head == "scale":
                cell.scale_line = tuple(float(v) for v in vals[1:4])
            elif head == "tech":
                cell.tech = vals[1]
            elif head == "use":
                m = _ARRAY.findall(vals[2])
                id_ = vals[2].split("[", 1)[0] if m else vals[2]
                array = None
                if m:
                    dims = [tuple(int(v) for v in g) for g in m]
                    if len(dims) == 1:
                        dims.append((0, 0, 0))
                    array = dims[0] + dims[1]
                cell.uses.append(Use(vals[1], id_, tuple(_int(v) for v in vals[3:9]), array))
            elif head == "port":
                l, b, r, t = (_int(v) for v in vals[3:7])
                cell.ports.append(Port(vals[1], _int(vals[2]), (l, b, r, t), vals[7] if len(vals) > 7 else ""))
            elif head in ("node", "substrate"):
                x, y = _int(vals[4]), _int(vals[5])
                if abs(x) >= _NO_POSITION or abs(y) >= _NO_POSITION:
                    x = y = None
                node = Node(vals[1], x, y, vals[6] if len(vals) > 6 else "", head == "substrate")
                cell.nodes[node.name] = node
                if node.substrate:
                    cell.substrate.append(node)
            elif head == "merge":
                cell.merges.append((vals[1], vals[2]))
            elif head == "device":
                cls, model = vals[1], vals[2]
                x, y = _int(vals[3]), _int(vals[4])
                params, terms = {}, []
                for t, quoted in toks[7:]:
                    if quoted:
                        terms.append(t)
                    elif "=" in t and not terms:
                        k, v = t.split("=", 1)
                        params[k] = v
                cell.devices.append(Device(cls, model, x, y, params, terms, len(cell.devices)))
        except (IndexError, ValueError) as e:
            raise ExtError("%s line %d: cannot read %r: %s" % (name or "ext", lineno, line[:80], e))
    return cell


def read(path):
    name = os.path.basename(path)
    if name.endswith(".ext"):
        name = name[:-4]
    with open(path, encoding="utf-8", errors="replace") as f:
        cell = parse(f.read(), name)
    cell.path = path
    return cell


def read_dir(path):
    """{cell name: ExtCell} for every ``.ext`` file in a job directory."""
    out = {}
    for n in sorted(os.listdir(path)):
        if n.endswith(".ext"):
            c = read(os.path.join(path, n))
            out[c.name] = c
    return out


class Located:
    """Where a net or device is: ``point`` in the top cell, in µm; ``type``
    the Magic type there (nets); ``cells`` the cell names from the top down;
    ``what`` the node or device record."""

    def __init__(self, point, type_, cells, what):
        self.point = point
        self.type = type_
        self.cells = cells
        self.what = what

    def __repr__(self):
        return "Located(%r, %s, %r)" % (self.point, self.type, self.cells)


_ELEMENT = re.compile(r"^(.*?)((?:\[-?\d+(?:,-?\d+)?\])+)$")


def _split_element(part):
    """'inst[1][2]' or 'inst[1,2]' -> ('inst', 1, 2); 'inst' -> ('inst', None, None)."""
    m = _ELEMENT.match(part)
    if not m:
        return part, None, None
    nums = [int(v) for v in re.findall(r"-?\d+", m.group(2))]
    return m.group(1), nums[0], (nums[1] if len(nums) > 1 else None)


class Extraction:
    """The ``.ext`` files of one job, with the unit from the job's
    ``KMP_JOB_SCALE`` (µm per unit)."""

    def __init__(self, cells, top, unit):
        if not unit or unit <= 0:
            raise ExtError("no unit: the job printed no KMP_JOB_SCALE")
        if top not in cells:
            raise ExtError("no %s.ext among the job's files" % top)
        self.cells = cells
        self.top = top
        self.unit = float(unit)

    @classmethod
    def from_dir(cls, path, top, unit):
        return cls(read_dir(path), top, unit)

    def um(self, v):
        return v * self.unit

    def box_um(self, box):
        """(l, b, r, t) in units -> in µm."""
        return tuple(v * self.unit for v in box)

    def ports(self):
        """The top cell's ports: [(name, (l, b, r, t) µm, type)]."""
        return [(p.name, self.box_um(p.box), p.type) for p in self.cells[self.top].ports]

    def _walk(self, parts, cell_name):
        """Resolve an instance path: [(use, i, j, child ExtCell)] from cell_name, or None."""
        chain = []
        cur = self.cells.get(cell_name)
        for part in parts:
            if cur is None:
                return None
            base, i, j = _split_element(part)
            use = None
            for cand in (part, base, base[1:] if base[:1] in "Xx" else None):
                if cand:
                    use = cur.use(cand)
                    if use:
                        break
            if use is None:
                return None
            child = self.cells.get(use.cell)
            chain.append((use, i, j, child))
            cur = child
        return chain

    def _to_top(self, chain, x, y):
        for use, i, j, _child in reversed(chain):
            x, y = use.apply(x, y, i, j)
        return x, y

    def locate_net(self, name, cell=None, _seen=None):
        """Where netgen's net ``name`` of circuit ``cell`` (default the top)
        is: a Located with the point in ``cell``'s coordinates, or None.
        Hierarchical names ("inst/inst/net", which netgen makes when it
        flattens a subcell) are followed through the ``use`` lines; merged
        names are tried in turn."""
        cell = cell or self.top
        seen = set() if _seen is None else _seen
        if (cell, name) in seen:
            return None
        seen.add((cell, name))
        parts = name.split("/")
        for k in range(len(parts) - 1, -1, -1):
            # The longest instance path that resolves; a net name may hold "/".
            chain = self._walk(parts[:k], cell)
            if chain is None:
                continue
            leaf = chain[-1][3] if chain else self.cells.get(cell)
            if leaf is None:
                continue
            net = "/".join(parts[k:])
            names = leaf.aliases(net)
            # The cell's own nodes and ports first, then names inside its subcells.
            for alias in names:
                node = leaf.nodes.get(alias)
                if node is not None and node.point is not None:
                    x, y = self._to_top(chain, *node.point)
                    return Located((self.um(x), self.um(y)), node.type,
                                   [cell] + [c[0].cell for c in chain], node)
                port = leaf.port(alias)
                if port is not None:
                    x, y = self._to_top(chain, port.box[0], port.box[1])
                    return Located((self.um(x), self.um(y)), port.type,
                                   [cell] + [c[0].cell for c in chain], port)
            for alias in names:
                if "/" in alias:
                    sub = self.locate_net(alias, leaf.name, seen)
                    if sub is not None:
                        x, y = self._to_top(chain, sub.point[0] / self.unit, sub.point[1] / self.unit)
                        return Located((self.um(x), self.um(y)), sub.type,
                                       [cell] + [c[0].cell for c in chain] + sub.cells[1:], sub.what)
            return None
        return None

    def locate_device(self, name, model=None, cell=None, spice=None):
        """Where netgen's device ``name`` ("0", "inst/0", as in
        "sky130_fd_pr__nfet_01v8:0") of circuit ``cell`` is. ``spice`` is
        ``spice_devices()`` of the job's netlist: it gives the device's model
        and nets, so the right ``device`` line is found even when the order
        differs; without it the n-th device line is taken."""
        cell = cell or self.top
        parts = name.split("/")
        chain = self._walk(parts[:-1], cell)
        if chain is None:
            return None
        leaf = chain[-1][3] if chain else self.cells.get(cell)
        if leaf is None:
            return None
        dev_name = parts[-1]
        inst = dev_name if dev_name[:1] in "Xx" else "X" + dev_name
        cands = [d for d in leaf.devices if model is None or d.model == model]
        found = None
        rec = (spice or {}).get(leaf.name, {}).get(inst) or (spice or {}).get(leaf.name, {}).get(dev_name)
        if rec is not None:
            nets = sorted(rec["nets"])
            same = [d for d in cands if d.model == rec["model"] and sorted(d.terminals) == nets]
            if len(same) == 1:
                found = same[0]
            elif same:
                order = [d for d in (spice or {}).get(leaf.name, {}).values() if d["model"] == rec["model"]
                         and sorted(d["nets"]) == nets]
                k = next((n for n, d in enumerate(order) if d is rec), 0)
                found = same[min(k, len(same) - 1)]
        if found is None:
            m = re.match(r"^[Xx]?(\d+)$", dev_name)
            if m and int(m.group(1)) < len(leaf.devices):
                found = leaf.devices[int(m.group(1))]
        if found is None:
            return None
        x, y = self._to_top(chain, found.x, found.y)
        return Located((self.um(x), self.um(y)), found.model, [cell] + [c[0].cell for c in chain], found)

    def instances(self, cell_pred):
        """Every placement in the top cell of the cells ``cell_pred`` accepts:
        [(path of use ids, cell name, transform function units -> µm)]."""
        out = []

        def walk(cell_name, path, chain):
            c = self.cells.get(cell_name)
            if c is None:
                return
            for use in c.uses:
                for i, j in use.elements():
                    elem = use.id if i is None else "%s[%d][%d]" % (use.id, i, j)
                    sub = chain + [(use, i, j, self.cells.get(use.cell))]
                    if cell_pred(use.cell):
                        out.append((path + [elem], use.cell, sub))
                    walk(use.cell, path + [elem], sub)

        walk(self.top, [], [])
        return out

    def point_um(self, chain, x, y):
        """A point (units) of the last cell of ``chain`` in the top, in µm."""
        x, y = self._to_top(chain, x, y)
        return self.um(x), self.um(y)


def spice_devices(path):
    """{subcircuit: {instance name: {"model", "nets", "params"}}} of the
    device and subcircuit lines of an ext2spice netlist, in file order."""
    out = {}
    if not os.path.isfile(path):
        return out
    lines = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for raw in f:
            raw = raw.rstrip("\n")
            if raw.startswith("+") and lines:
                lines[-1] += " " + raw[1:]
            else:
                lines.append(raw)
    cur = None
    for ln in lines:
        s = ln.strip()
        if not s or s[0] == "*":
            continue
        low = s.lower()
        if low.startswith(".subckt"):
            cur = s.split()[1]
            out.setdefault(cur, {})
            continue
        if low.startswith(".ends"):
            cur = None
            continue
        if cur is None or s[0] not in "XxMmRrCcDdQq":
            continue
        toks = s.split()
        plain = [t for t in toks[1:] if "=" not in t]
        params = dict(t.split("=", 1) for t in toks[1:] if "=" in t)
        if not plain:
            continue
        out[cur][toks[0]] = {"model": plain[-1], "nets": plain[:-1], "params": params}
    return out
