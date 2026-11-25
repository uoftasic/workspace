"""Put many sweep points on one layout ("sheet") for DRC and extraction.

Each point's device cell is flattened into a cell ``D<id>`` and placed on a
grid with ``GAP_UM`` between bounding boxes, which is more than the 15 um
latch-up distance in Magic's drc(full) rules. Each cell moves by a multiple
of ``GRID_UM``, so that its shapes stay on the PDKs' 5 nm grid even after a
cell whose bounding box is off it (a case with a corner off the grid on
purpose). A JSON file next to the sheet records where each point landed.
"""

import json
import math
import os

import klayout.db as db

GAP_UM = 40.0
ROW_UM = 1500.0
GRID_UM = 0.005


def on_grid(v, grid=GRID_UM):
    """v rounded up to a multiple of grid (in um)."""
    return math.ceil(round(v / grid, 6)) * grid


def flat_copy(src_ly, src_cell, dst_ly, dst_cell):
    """Copy src_cell flattened into dst_cell (same dbu assumed)."""
    if abs(src_ly.dbu - dst_ly.dbu) > 1e-12:
        mag = src_ly.dbu / dst_ly.dbu
        t = db.ICplxTrans(mag)
    else:
        t = db.ICplxTrans()
    for li in src_ly.layer_indices():
        info = src_ly.get_info(li)
        it = src_cell.begin_shapes_rec(li)
        if it.at_end():
            continue
        dst_cell.shapes(dst_ly.layer(info.layer, info.datatype)).insert(it, t)


def build_sheet(entries, out_gds, top_name="SHEET", gap_um=GAP_UM, row_um=ROW_UM):
    """``entries``: list of (id, gds_path, cell_name). Writes out_gds and
    out_gds + '.json' with {id: [left, bottom, right, top] in um}."""
    ly = db.Layout()
    ly.dbu = 0.001
    top = ly.create_cell(top_name)
    placed = {}
    errors = {}
    x = y = row_top = 0.0
    for pid, path, cell_name in entries:
        try:
            src = db.Layout()
            src.read(path)
            sc = src.cell(cell_name)
            if sc is None:
                raise RuntimeError("cell %s not in %s" % (cell_name, path))
        except Exception as e:
            errors[pid] = str(e)
            continue
        d = ly.create_cell("D" + pid)
        flat_copy(src, sc, ly, d)
        b = d.dbbox()
        if b.empty():
            # Nothing to check; keep the point listed with an empty box.
            placed[pid] = None
            continue
        if x > 0 and x + b.width() > row_um:
            x = 0.0
            y = row_top + gap_um
        dx, dy = on_grid(x - b.left), on_grid(y - b.bottom)
        top.insert(db.DCellInstArray(d.cell_index(), db.DTrans(db.DVector(dx, dy))))
        placed[pid] = [round(b.left + dx, 4), round(b.bottom + dy, 4), round(b.right + dx, 4), round(b.top + dy, 4)]
        x = b.right + dx + gap_um
        row_top = max(row_top, b.top + dy)
    opts = db.SaveLayoutOptions()
    opts.write_context_info = False
    ly.write(out_gds, opts)
    with open(out_gds + ".json", "w", encoding="utf-8") as f:
        json.dump({"top": top_name, "gap_um": gap_um, "placed": placed, "errors": errors}, f, indent=1)
    return placed, errors


def chunks(items, size):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def assign(markers, placed, top="SHEET", margin_um=None):
    """Map markers (rule, cell, [l, b, r, t] um) to point ids.

    A marker reported in a cell ``D<id>`` belongs to that point. A marker in
    the top cell, or with no cell (Magic reports top-cell coordinates),
    belongs to the point whose box, grown by ``margin_um`` (half the gap by
    default), contains the marker's centre.
    """
    if margin_um is None:
        margin_um = GAP_UM / 2
    boxes = [(pid, b) for pid, b in placed.items() if b]
    out, unassigned = {}, []
    for rule, cell, box in markers:
        if cell and cell != top:
            if cell.startswith("D") and cell[1:] in placed:
                out.setdefault(cell[1:], set()).add(rule)
            else:
                unassigned.append([rule, cell, box])
            continue
        if box is None:
            unassigned.append([rule, cell, box])
            continue
        l, b, r, t = box
        cx, cy = (l + r) / 2, (b + t) / 2
        hit = None
        for pid, (bl, bb, br, bt) in boxes:
            if bl - margin_um <= cx <= br + margin_um and bb - margin_um <= cy <= bt + margin_um:
                hit = pid
                break
        if hit is None:
            unassigned.append([rule, cell, box])
        else:
            out.setdefault(hit, set()).add(rule)
    return out, unassigned


if __name__ == "__main__":
    import sys
    # python3 sheet.py out.gds id path cell [id path cell ...]
    args = sys.argv[2:]
    ents = [tuple(args[i:i + 3]) for i in range(0, len(args), 3)]
    p, e = build_sheet(ents, sys.argv[1])
    print(len(p), "placed", len(e), "errors")
