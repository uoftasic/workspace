#!/bin/sh
# Take the screenshots of guide.md again, in the pinned image:
#
#   tools/screenshots/take.sh            # writes docs/img/guide/*.png
#   tools/screenshots/take.sh /tmp/shots # somewhere else
#
# One container runs KLayout's GUI under Xvfb once per session of gui.py
# (main, reopen, defunct and magic), with the repository mounted where the
# guide puts it, /foss/designs/klayout-magic-pcells, and linked into
# KLayout's salt folder as the guide says. finish.py then writes the PNGs.
# KMP_SHOT_SESSIONS="magic" runs only the named sessions and writes only
# their PNGs. KMP_SHOT_KEEP=1 keeps the work directory (raw grabs, logs,
# the GDS).
set -eu
IMAGE="${KMP_IMAGE:-hpretl/iic-osic-tools@sha256:3c371645b19c6f6564dc8c7b21e39ad1c1833d274fe5b85639afe1ba9d7987e7}"
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="${1:-$REPO/docs/img/guide}"
mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd)"
WORK="$(mktemp -d)"
status=0
docker run --rm --user "$(id -u):$(id -g)" -e PDK=sky130A -e KMP_SHOT_SESSIONS="${KMP_SHOT_SESSIONS:-}" \
  -v "$REPO:/foss/designs/klayout-magic-pcells" -v "$WORK:/work" -v "$OUT:/out" \
  "$IMAGE" --skip bash -lc /foss/designs/klayout-magic-pcells/tools/screenshots/inside.sh || status=$?
if [ "${KMP_SHOT_KEEP:-0}" = 1 ] || [ $status -ne 0 ]; then
  echo "work directory: $WORK"
else
  rm -rf "$WORK"
fi
exit $status
