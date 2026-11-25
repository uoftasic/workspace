#!/bin/sh
# Rebuild the shipped manifests and PDK data files from the Magic and PDKs in the pinned image:
#   scripts/manifest.sh                     rewrite python/klayout_magic_pcells/data/manifest-<pdk>.json
#                                           and pdk-<pdk>.json for every PDK
#   scripts/manifest.sh --check             exit 1 if a committed manifest or data file differs from
#                                           the installed PDK (the data check also compares the
#                                           harness's KLayout DRC PROFILES with the decks)
#   scripts/manifest.sh --pdk gf180mcuD     one PDK
# --out and --keep go to tools/build_manifest.py only.
case " $* " in
  *" --pdk "*|*" --pdk="*) ;;
  *) set -- --all "$@" ;;
esac
exec "$(dirname "$0")/in_image.sh" '
rc=0
python3 tools/build_manifest.py "$@" || rc=$?
n=$#
skip=
for a in "$@"; do
  if [ -n "$skip" ]; then skip=; continue; fi
  case "$a" in
    --out|--keep) skip=1 ;;
    --out=*|--keep=*) ;;
    *) set -- "$@" "$a" ;;
  esac
done
shift $n
python3 tools/build_pdk_data.py "$@" || { r=$?; [ $r -gt $rc ] && rc=$r; }
exit $rc' "$@"
