import sys, os
import klayout.db as db
OUT = "/scratch/design/exp"
mode, ver = sys.argv[1], sys.argv[2]
class P(db.PCellDeclarationHelper):
    def __init__(self):
        super().__init__()
        self.param("w", self.TypeDouble, "w", default=1.0)
        self.param("kmp_stamp", self.TypeString, "stamp", hidden=True, readonly=True, default="kmp1 magic=" + ver)
    def produce_impl(self):
        print("  produce sees kmp_stamp =", repr(self.kmp_stamp))
        self.cell.shapes(self.layout.layer(68, 20)).insert(db.DBox(0, 0, self.w, 1))
class L(db.Library):
    def __init__(self):
        self.layout().register_pcell("dev", P())
        self.register("KMP_Hidden")
if mode == "write":
    L(); ly = db.Layout(); top = ly.create_cell("TOP")
    pc = ly.create_cell("dev", "KMP_Hidden", {"w": 2.0})
    top.insert(db.CellInstArray(pc.cell_index(), db.Trans()))
    print("mem params", pc.pcell_parameters_by_name())
    ly.write(OUT + "/hidden.gds")
elif mode == "read":
    L(); ly = db.Layout(); ly.read(OUT + "/hidden.gds")
    for c in ly.each_cell():
        if c.is_pcell_variant(): print("reopen params", c.pcell_parameters_by_name())
