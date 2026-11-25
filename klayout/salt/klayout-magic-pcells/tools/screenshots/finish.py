"""Copy the raw grabs that guide.md uses to the output folder as PNGs of at
most about 300 KB: saved optimized, and reduced to a 256-colour palette
only when the full-colour file is larger than that.

    python3 finish.py RAW_DIR OUT_DIR [SESSION...]

With sessions named, only their shots are written (and required); the
default is every session.
"""

import os
import sys

from PIL import Image

LIMIT = 300 * 1024
SESSIONS = {
    "main": ["salt-package", "libraries", "place-nfet", "nfet-l-corrected", "nfet-placed",
             "via1-too-small", "layout-overview", "properties-edit", "log-viewer", "stamp"],
    "reopen": ["reopen-with-library"],
    "defunct": ["reopen-without-library"],
    "magic": ["magic-menu", "magic-drc-dialog", "magic-drc-browser", "magic-drc-visible", "magic-lvs-dialog",
              "magic-lvs-browser", "magic-extract-dialog", "magic-extract-netlist", "magic-layers-browser",
              "magic-ports-browser", "magic-gaps", "magic-settings", "magic-pdk-choice", "magic-progress",
              "magic-one-job", "magic-cancelled"],
}
SHOTS = [s for k in ("main", "reopen", "defunct", "magic") for s in SESSIONS[k]]


def main(raw, out, sessions=None):
    shots = [s for k in (sessions or SESSIONS) for s in SESSIONS[k]]
    os.makedirs(out, exist_ok=True)
    missing = []
    for name in shots:
        src = os.path.join(raw, name + ".png")
        if not os.path.exists(src):
            missing.append(name)
            continue
        dst = os.path.join(out, name + ".png")
        im = Image.open(src).convert("RGB")
        im.save(dst, optimize=True)
        if os.path.getsize(dst) > LIMIT:
            im.quantize(256, method=Image.Quantize.MEDIANCUT).save(dst, optimize=True)
        print("%-22s %4d x %-4d %4d KB" % (name, im.width, im.height, os.path.getsize(dst) // 1024))
    if missing:
        print("missing: " + ", ".join(missing))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3:] or None))
