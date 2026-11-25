import sys, os
import klayout.db as db
OUT = "/scratch/design/exp"
mode = sys.argv[1]

class P(db.PCellDeclarationHelper):
    def __init__(self):
        super().__init__()
        self.param("w", self.TypeDouble, "w", default=1.0)
    def produce_impl(self):
        li = self.layout.layer(68, 20)
        self.cell.shapes(li).insert(db.DBox(0, 0, self.w, 1))
        # stamp variants
        self.cell.set_property("kmp_stamp", "magic=8.3.681;pdk=026824c;key=abc")
        li2 = self.layout.layer(235, 4)
        s = self.cell.shapes(li2).insert(db.DBox(0, 0, self.w, 1))
        s.set_property(1, "kmp-int-key")
        s.set_property("kmp_str", "kmp-str-key")

class L(db.Library):
    def __init__(self):
        self.description = "stamp test"
        self.layout().register_pcell("dev", P())
        self.register("KMP_Stamp")

def dump(ly, tag):
    for c in ly.each_cell():
        props = {}
        try:
            props = c.property("kmp_stamp")
        except Exception as e:
            props = "ERR %s" % e
        sp = []
        for li in ly.layer_indices():
            for sh in c.shapes(li).each():
                if sh.prop_id:
                    sp.append((str(ly.get_info(li)), dict(ly.properties_hash(sh.prop_id)) if hasattr(ly,'properties_hash') else ly.properties(sh.prop_id)))
        print(tag, repr(c.name), "proxy=%s var=%s" % (c.is_proxy(), c.is_pcell_variant()), "cellprop=", repr(props), "shapeprops=", sp)

if mode == "write":
    L()
    ly = db.Layout()
    top = ly.create_cell("TOP")
    pc = ly.create_cell("dev", "KMP_Stamp", {"w": 2.0})
    top.insert(db.CellInstArray(pc.cell_index(), db.Trans()))
    dump(ly, "mem")
    ly.write(OUT + "/stamp.gds")
    ly.write(OUT + "/stamp.oas")
elif mode == "readlib":
    L()
    for f in ("stamp.gds", "stamp.oas"):
        ly = db.Layout(); ly.read(OUT + "/" + f); dump(ly, "withlib " + f)
elif mode == "readnolib":
    for f in ("stamp.gds", "stamp.oas"):
        ly = db.Layout(); ly.read(OUT + "/" + f); dump(ly, "nolib " + f)
