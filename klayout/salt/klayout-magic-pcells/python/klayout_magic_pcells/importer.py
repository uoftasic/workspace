"""Copy Magic's GDS into a PCell cell, flat and layer by layer; and two
readings of Magic's GDS that the PCell needs: whether it holds any shape,
and the coarsest grid its coordinates lie on."""

import math
import struct


class GdsImportError(Exception):
    pass


def insert_gds_flat(layout, cell, gds_path):
    """Read ``gds_path`` into a fresh Layout and insert its single top cell,
    flattened, into ``cell``. Never reads into ``layout`` itself: reading into
    a layout with content would switch its dbu without rescaling."""
    from ._kl import db
    src = db.Layout()
    src.read(gds_path)
    tops = src.top_cells()
    if len(tops) != 1:
        raise GdsImportError("%s: expected one top cell, found %d" % (gds_path, len(tops)))
    ratio = src.dbu / layout.dbu
    mag = int(round(ratio))
    if mag < 1 or abs(ratio - mag) > 1e-9:
        raise GdsImportError("source dbu %g is not a multiple of %g" % (src.dbu, layout.dbu))
    t = db.ICplxTrans(mag)
    top = tops[0]
    n = 0
    for li in src.layer_indices():
        info = src.get_info(li)
        it = top.begin_shapes_rec(li)
        if it.at_end():
            continue
        dst = layout.layer(info.layer, info.datatype)
        cell.shapes(dst).insert(it, t)
        n += 1
    return n


# GDSII record types of the elements that carry geometry or text.
_SHAPE_RECORDS = {0x08, 0x09, 0x0C, 0x2D}  # BOUNDARY, PATH, TEXT, BOX


def gds_has_shapes(gds_path):
    """True when the GDS file holds a boundary, path, box or text anywhere.
    Read record by record, without KLayout: Magic's file for a device it drew
    nothing for (a box below the generator's minimum, a _draw that failed)
    holds only its structure headers, or an instance of an empty cell."""
    with open(gds_path, "rb") as f:
        data = f.read()
    i = 0
    while i + 4 <= len(data):
        n, rt = struct.unpack(">HB", data[i:i + 3])
        if n < 4:
            break
        if rt in _SHAPE_RECORDS:
            return True
        i += n
    return False


def gds_grid_nm(gds_path):
    """The coarsest grid, in nm, that every vertex and text position of the
    flattened top cell lies on (the gcd of the coordinates), or None for a
    file without shapes.

    Worked out cell by cell instead of on the flat copy: a cell's grid is
    the gcd of its own coordinates, of its instances' displacements and
    array vectors, and of the grids of the cells they place (rotation and
    mirroring keep a grid). That can come out finer than the flat cell's
    true gcd, never coarser, so a file dbu that divides it never rounds
    anything. A magnified instance falls back to its flattened shapes."""
    from ._kl import db
    ly = db.Layout()
    ly.read(gds_path)
    tops = ly.top_cells()
    if len(tops) != 1:
        raise GdsImportError("%s: expected one top cell, found %d" % (gds_path, len(tops)))
    memo = {}

    def own(cell):
        g = 0
        for li in ly.layer_indices():
            for sh in cell.shapes(li).each():
                if sh.is_text():
                    p = sh.text.trans.disp
                    g = math.gcd(g, p.x, p.y)
                    continue
                pol = sh.polygon
                if pol is None:
                    continue
                for pt in pol.each_point_hull():
                    g = math.gcd(g, pt.x, pt.y)
                for h in range(pol.holes()):
                    for pt in pol.each_point_hole(h):
                        g = math.gcd(g, pt.x, pt.y)
        return g

    def flat(cell):
        g = 0
        for li in ly.layer_indices():
            it = cell.begin_shapes_rec(li)
            while not it.at_end():
                sh, t = it.shape(), it.trans()
                if sh.is_text():
                    p = sh.text.transformed(t).trans.disp
                    g = math.gcd(g, p.x, p.y)
                else:
                    pol = sh.polygon
                    if pol is not None:
                        pol = pol.transformed(t)
                        for pt in pol.each_point_hull():
                            g = math.gcd(g, pt.x, pt.y)
                        for h in range(pol.holes()):
                            for pt in pol.each_point_hole(h):
                                g = math.gcd(g, pt.x, pt.y)
                it.next()
        return g

    def grid(ci):
        if ci in memo:
            return memo[ci]
        cell = ly.cell(ci)
        g = own(cell)
        for inst in cell.each_inst():
            ca = inst.cell_inst
            if ca.is_complex() and abs(ca.cplx_trans.mag - 1.0) > 1e-12:
                g = math.gcd(g, flat(cell))
                break
            child = grid(ca.cell_index)
            if child == 0 and ly.cell(ca.cell_index).is_empty():
                continue
            d = ca.trans.disp
            g = math.gcd(g, child, d.x, d.y)
            if ca.is_regular_array():
                g = math.gcd(g, ca.a.x, ca.a.y, ca.b.x, ca.b.y)
        memo[ci] = g
        return g

    g = grid(tops[0].cell_index())
    if not g:
        return None
    return int(round(g * ly.dbu * 1000)) or None
