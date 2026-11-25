import klayout.db as db
ly = db.Layout(); ly.read("/scratch/design/exp/hidden.gds")
o = db.SaveLayoutOptions(); o.write_context_info = False
# dump context strings by reading raw GDS records
data = open("/scratch/design/exp/hidden.gds","rb").read()
import re
print(sorted(set(m.decode() for m in re.findall(rb"P\([a-z_]+\)=[^\x00]{0,40}", data))))
