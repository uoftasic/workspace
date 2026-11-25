"""The layouts of gui.py's session "magic", built in the image before
KLayout starts (inside.sh):

    python3 magic_inputs.py WORK

- WORK/cases/sky130A: the case suite's hier, gaps and inverters sets
  (tests/cases/build.py, without the PCell inverter);
- WORK/cases/sky130A/inverters/inv_texts_only.gds: the hand inverter with
  its pin boxes removed, its texts kept (the port check's "texts without pin
  boxes");
- WORK/block250.gds: a 250 x 250 um block of sky130_fd_sc_hd cells in rows,
  flipped as a placer does, with a tap cell every 12 cells (as the 250 um
  block of design-0.6.md 6.4), long enough to cancel a flat DRC of it.
"""

import os
import subprocess
import sys

import klayout.db as db

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "python"))


def cases(out):
    cmd = [sys.executable, os.path.join(REPO, "tests", "cases", "build.py"), "--pdk", "sky130A", "--out", out,
           "--set", "hier", "--set", "gaps", "--set", "inverters", "--no-pcell"]
    subprocess.run(cmd, check=True)


def texts_only(src, dst, top):
    """``src`` without the shapes on the PDK's pin layers; the texts stay."""
    from klayout_magic_pcells import pdkdata
    pins = {tuple(p) for p in pdkdata.load("sky130A").ports()["pin"]}
    ly = db.Layout()
    ly.read(src)
    for li in ly.layer_indexes():
        info = ly.get_info(li)
        if (info.layer, info.datatype) in pins:
            for c in ly.each_cell():
                c.shapes(li).clear()
    o = db.SaveLayoutOptions()
    o.write_context_info = False
    o.select_cell(ly.cell(top).cell_index())
    ly.write(dst, o)


def block(dst, size=250.0):
    lib = os.path.join(os.environ.get("PDK_ROOT", "/foss/pdks"), "sky130A", "libs.ref", "sky130_fd_sc_hd", "gds",
                       "sky130_fd_sc_hd.gds")
    ly = db.Layout()
    ly.read(lib)
    names = ["sky130_fd_sc_hd__inv_1", "sky130_fd_sc_hd__nand2_1", "sky130_fd_sc_hd__nor2_1",
             "sky130_fd_sc_hd__dfxtp_1", "sky130_fd_sc_hd__a21oi_1"]
    cells = [ly.cell(n) for n in names]
    tap = ly.cell("sky130_fd_sc_hd__tapvpwrvgnd_1")
    boundary = ly.find_layer(235, 4)
    row_h = 2.72

    def width(c):
        b = db.DBox()
        if boundary is not None:
            for s in c.each_shape(boundary):
                b += s.dbbox()
        return b.width() if not b.empty() else c.dbbox().width()

    widths = {c.cell_index(): width(c) for c in cells + [tap]}
    top = ly.create_cell("block250")
    n = 0
    for r in range(int(size // row_h)):
        x, k = 0.0, 0
        while True:
            c = tap if k % 12 == 0 else cells[(r + k) % len(cells)]
            w = widths[c.cell_index()]
            if x + w > size:
                break
            t = db.DTrans(db.DVector(x, r * row_h)) if r % 2 == 0 else \
                db.DTrans(db.DVector(x, (r + 1) * row_h)) * db.DTrans.M0
            top.insert(db.DCellInstArray(c.cell_index(), t))
            x += w
            k += 1
            n += 1
    o = db.SaveLayoutOptions()
    o.write_context_info = False
    o.select_cell(top.cell_index())
    ly.write(dst, o)
    return n


def main(work):
    out = os.path.join(work, "cases", "sky130A")
    cases(out)
    inv = os.path.join(out, "inverters")
    texts_only(os.path.join(inv, "inv.gds"), os.path.join(inv, "inv_texts_only.gds"), "inv")
    n = block(os.path.join(work, "block250.gds"))
    print("magic inputs: cases in %s, block250.gds with %d instances" % (out, n))


if __name__ == "__main__":
    main(sys.argv[1])
