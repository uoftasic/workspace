"""Path B of the parity sweep: the PCell, through ``klayout -b``.

    KMP_SWEEP=sweep.json KMP_OUT=<dir> \
      klayout -b -rm pymacros/klayout_magic_pcells.lym -r tests/parity/pcell_path.py

The PDK is the one KMP_PDK names (run_sweep.py sets KMP_PDK and KMP_PDKS to
it). For each point: a layout at dbu 0.001; for a device, the point's typed
values put through the PCell's coerce as KLayout's GUI form does
(``klayout_magic_pcells.dialog_values``: Magic's dialog corrects them), and
``create_cell(device, <the PDK's library>, <those values>)``, so the variant
stores what the GUI stores; for a box-paint generator, the typed box. The
variant is placed in a top cell ``T<id>``, and ``<id>.gds`` and ``<id>.oas``
are written. For a device, a second variant made from the typed values as
they are (``create_cell`` with them, which KLayout coerces only for drawing)
must draw the same shapes. An edit point (gen_sweep.py) first puts its
``first`` values through ``dialog_values``, then the stored values with the
point's own values changed in them, as a user edits the PCell's form
afterwards (Magic's "Edit device" dialog and Apply). ``index.json``
records the variant's name, its stored parameters and what the backend
returned (the request, checked dict, messages, Magic's cell name, cache
source).
"""

import json
import os
import sys
import time
import traceback

import klayout.db as db
import klayout_magic_pcells as kmp
from klayout_magic_pcells.stamp import read_stamp

def main():
    sweep_path = os.environ["KMP_SWEEP"]
    out = os.environ["KMP_OUT"]
    os.makedirs(out, exist_ok=True)
    with open(sweep_path, encoding="utf-8") as f:
        sweep = json.load(f)
    st = kmp.state_for(os.environ.get("KMP_PDK") or "sky130A")
    LIB = st.library_name
    index = {"registered": st.library is not None, "error": st.last_error, "library": LIB,
             "versions": st.versions.as_dict() if st.versions else None,
             "created_stamp": st.created_stamp, "points": {}}
    if st.library is None:
        with open(os.path.join(out, "index.json"), "w") as f:
            json.dump(index, f, indent=1)
        print("PCELL_PATH: library not registered: %s" % st.last_error)
        return 2
    # Every result the generator hands produce, so that an empty cell (no
    # stamp to read the key from) still shows which request it got, also
    # when an earlier point already made the same request (a tie value
    # whose text equals the 12-digit point's).
    calls = []
    plain_get = st.generator.get

    def recording_get(spec, request):
        res = plain_get(spec, request)
        calls.append(res)
        return res
    st.generator.get = recording_get
    t0 = time.time()
    for pt in sweep["points"]:
        pid, dev = pt["id"], pt["device"]
        spec = st.manifest[dev]
        rec = {"device": dev}
        try:
            # The typed values come from the sweep, not from the plugin's parser.
            typed = pt["value"]
            if pt.get("edit"):
                first = kmp.dialog_values(dev, pt["first"]["value"], pdk=st.pdk)
                rec["first_stored"] = dict(first)
                typed = dict(first, **typed)
            params = typed if spec.kind == "box" else kmp.dialog_values(dev, typed, pdk=st.pdk)
            ly = db.Layout()
            ly.dbu = 0.001
            del calls[:]
            pc = ly.create_cell(dev, LIB, params)
            if pc is None:
                raise RuntimeError("create_cell returned None")
            top = ly.create_cell("T" + pid)
            top.insert(db.CellInstArray(pc.cell_index(), db.Trans()))
            ly.write(os.path.join(out, pid + ".gds"))
            ly.write(os.path.join(out, pid + ".oas"))
            # The request the PCell actually sent: the memo entry whose key
            # starts with the key in the variant's generated-by stamp.
            # An empty cell has no stamp: then the memo entry of the last
            # result the generator gave produce for this cell.
            stp = read_stamp(pc) or {}
            k16 = stp.get("key") or ""
            hits = [st.generator._memo[k] for k in st.generator._memo if k16 and k.startswith(k16)]
            if not k16:
                hits = [st.generator._memo[calls[-1].key]] if calls and calls[-1].key in st.generator._memo else []
            res = hits[0] if len(hits) == 1 else None
            req = res.sidecar.get("request") if res is not None else None
            rec.update({
                "variant": pc.name, "top": top.name,
                "title": pc.display_title(),
                "stored": {k: v for k, v in pc.pcell_parameters_by_name().items()},
                "request": req,
            })
            if spec.kind != "box":
                raw = ly.create_cell(dev, LIB, typed)
                diff = []
                for li in ly.layer_indices():
                    a = db.Region(pc.begin_shapes_rec(li))
                    b = db.Region(raw.begin_shapes_rec(li))
                    ta = sorted(str(t) for t in db.Texts(pc.begin_shapes_rec(li)).each())
                    tb = sorted(str(t) for t in db.Texts(raw.begin_shapes_rec(li)).each())
                    if not (a ^ b).is_empty() or a.count() != b.count() or ta != tb:
                        diff.append(ly.get_info(li).to_s())
                rec["typed_create"] = {"same": not diff, "diff_layers": diff,
                                       "stored": {k: v for k, v in raw.pcell_parameters_by_name().items()
                                                  if k in typed}}
            if res is not None:
                rec.update({"key": res.key, "source": res.source, "checked": res.checked,
                            "messages": res.messages, "magic_cell": res.magic_cell,
                            "stamp": res.stamp})
            else:
                rec["source"] = None
        except Exception as e:
            rec["error"] = "%s: %s" % (type(e).__name__, e)
            rec["traceback"] = traceback.format_exc()
        index["points"][pid] = rec
    index["seconds"] = round(time.time() - t0, 2)
    index["generator_stats"] = dict(st.generator.stats)
    index["server_stats"] = dict(st.server.stats)
    with open(os.path.join(out, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, indent=1, default=str)
    print("PCELL_PATH: %d points in %.1f s, generator %s"
          % (len(index["points"]), index["seconds"], st.generator.stats))
    return 0


rc = main()
if rc:
    sys.exit(rc)
