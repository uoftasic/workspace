#!/bin/sh
# Rebuild the gap tables in the pinned image (design-0.6.md 3.5):
#   scripts/gaps.sh                    all four PDKs: write docs/gaps/<pdk>.md and .json,
#                                      docs/gaps/README.md and pkg/data/gaps-<pdk>.json
#   scripts/gaps.sh --check            exit 1 if a rebuilt table differs from the committed one
#   scripts/gaps.sh --pdk gf180mcuD    one PDK (--pdk can be given more than once)
# Other arguments go to tools/build_gaps.py. Each PDK runs in its own
# container, with the image's PDK variable set to that PDK.
set -u
pdks=
rest=
while [ $# -gt 0 ]; do
  case "$1" in
    --pdk) pdks="$pdks $2"; shift 2 ;;
    --pdk=*) pdks="$pdks ${1#--pdk=}"; shift ;;
    *) rest="$rest $1"; shift ;;
  esac
done
[ -n "$pdks" ] || pdks="sky130A gf180mcuD ihp-sg13g2 ihp-sg13cmos5l"
rc=0
for p in $pdks; do
  # shellcheck disable=SC2086
  KMP_IMAGE_PDK=$p "$(dirname "$0")/in_image.sh" 'python3 tools/build_gaps.py "$@"' --pdk "$p" $rest || {
    r=$?; [ $r -gt $rc ] && rc=$r; }
done
exit $rc
