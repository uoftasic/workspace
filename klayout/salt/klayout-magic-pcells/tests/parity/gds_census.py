"""Raw GDSII record census, without KLayout.

KLayout's GDS reader drops element types it has no shape for (NODE, which
the vendor GDS of some sky130 fixed devices holds) without a warning, so a
comparison that reads both files through KLayout can't see them. This reads
the records itself and counts the elements of each type per layer/datatype,
over all structures of the file (not flattened: an arrayed vendor cell is
counted once).

It also reads each text's font from its PRESENTATION record, which
KLayout's GDS reader drops too (KLayout 0.30.11 reads every text with font
-1 and writes font 0): ``text_fonts`` lists the (layer/texttype, string,
font) of every text in the file.

    python3 gds_census.py FILE.gds [...]
"""

import struct
import sys
from collections import Counter

EL = {0x08: "BOUNDARY", 0x09: "PATH", 0x0A: "SREF", 0x0B: "AREF", 0x0C: "TEXT", 0x15: "NODE",
      0x2D: "BOX"}
LAYER, DATATYPE, TEXTTYPE, NODETYPE, BOXTYPE, ENDEL = 0x0D, 0x0E, 0x16, 0x2A, 0x2E, 0x11
PRESENTATION, STRING = 0x17, 0x19
# Element types a KLayout cell holds as shapes or instances.
KLAYOUT_TYPES = {"BOUNDARY", "PATH", "SREF", "AREF", "TEXT"}


def _elements(path):
    """Yield one dict per element of the file: type, layer, dt, and for a
    text its string and its PRESENTATION bits (None without the record)."""
    with open(path, "rb") as f:
        data = f.read()
    i = 0
    cur = None
    while i + 4 <= len(data):
        n, rt, _dt = struct.unpack(">HBB", data[i:i + 4])
        if n < 4:
            break
        body = data[i + 4:i + n]
        if rt in EL:
            cur = {"type": EL[rt], "layer": None, "dt": None, "string": None, "presentation": None}
        elif cur is not None:
            if rt == LAYER:
                cur["layer"] = struct.unpack(">h", body[:2])[0]
            elif rt in (DATATYPE, TEXTTYPE, NODETYPE, BOXTYPE):
                cur["dt"] = struct.unpack(">h", body[:2])[0]
            elif rt == PRESENTATION:
                cur["presentation"] = struct.unpack(">H", body[:2])[0]
            elif rt == STRING:
                cur["string"] = body.rstrip(b"\0").decode("latin-1")
            elif rt == ENDEL:
                yield cur
                cur = None
        i += n


def _ld(el):
    return "-" if el["layer"] is None else "%d/%d" % (el["layer"], el["dt"] or 0)


def census(path):
    """{(element type, 'layer/datatype' or '-'): count} over the whole file."""
    elems = Counter()
    for el in _elements(path):
        elems[(el["type"], _ld(el))] += 1
    return elems


def text_fonts(path):
    """Sorted unique [layer/texttype, string, font] of every text in the
    file. The font is bits 10-11 of PRESENTATION (0 without the record).
    Unique, not counted: a PCell holds an arrayed vendor cell's texts once
    per copy, Magic's file once."""
    out = set()
    for el in _elements(path):
        if el["type"] == "TEXT":
            pres = el["presentation"] or 0
            out.add((_ld(el), el["string"] or "", (pres >> 4) & 3))
    return [list(t) for t in sorted(out)]


def lost(path):
    """Elements of types KLayout can't hold, as {'TYPE layer/dt': count}."""
    return {"%s %s" % k: v for k, v in sorted(census(path).items()) if k[0] not in KLAYOUT_TYPES}


if __name__ == "__main__":
    for p in sys.argv[1:]:
        c = census(p)
        types = Counter()
        for (k, _ld), n in c.items():
            types[k] += n
        print("%s %s lost=%s" % (p.split("/")[-1], dict(types), lost(p)))
