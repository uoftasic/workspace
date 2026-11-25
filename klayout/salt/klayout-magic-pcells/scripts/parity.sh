#!/bin/sh
# The parity harness, in the pinned image.
#
#   scripts/parity.sh                                   # every PDK, full sweep
#   scripts/parity.sh --pdk gf180mcuD                   # one PDK
#   scripts/parity.sh --pdk all --quick                 # each generator's defaults, every PDK
#   scripts/parity.sh --pdk sky130A --devices 'sky130_fd_pr__res_*' --keep
#   scripts/parity.sh --pdk ihp-sg13g2 --update-baseline   # rewrite that PDK's baselines
#
# PDKs: sky130A, gf180mcuD, ihp-sg13g2, ihp-sg13cmos5l, or all (the default).
# Each PDK runs in its own container, with the image's PDK variable set to
# it, and writes out/parity/<pdk>/report.json and report.md. With all, the
# PDKs run one after another and out/parity/summary.json and summary.md
# collect the results. Exit status: 0 when every check of every PDK passes,
# 1 when a check fails, 2 when the harness itself fails. Arguments reach
# run_sweep.py as positional parameters of bash -c, so glob patterns arrive
# unexpanded.
set -u
HERE="$(dirname "$0")"
PDKS="sky130A gf180mcuD ihp-sg13g2 ihp-sg13cmos5l"
PDK=all
# Take --pdk out of the arguments; pass the rest on.
n=$#
i=0
while [ $i -lt $n ]; do
  a="$1"
  shift
  i=$((i + 1))
  case "$a" in
    --pdk) PDK="$1"; shift; i=$((i + 1)) ;;
    --pdk=*) PDK="${a#--pdk=}" ;;
    *) set -- "$@" "$a" ;;
  esac
done
case " $PDKS all " in
  *" $PDK "*) ;;
  *) echo "parity.sh: unknown PDK '$PDK' (one of: $PDKS, all)" >&2; exit 2 ;;
esac
RUN='p="$1"; shift; python3 tests/parity/run_sweep.py --pdk "$p" --out "/repo/out/parity/$p" "$@"'
if [ "$PDK" != all ]; then
  KMP_IMAGE_PDK="$PDK" exec "$HERE/in_image.sh" "$RUN" "$PDK" "$@"
fi
status=0
for p in $PDKS; do
  KMP_IMAGE_PDK="$p" "$HERE/in_image.sh" "$RUN" "$p" "$@"
  rc=$?
  [ $rc -gt $status ] && status=$rc
done
# The summary exits with the worst PDK's status (0, 1 or 2) on its own.
"$HERE/in_image.sh" 'python3 tests/parity/run_sweep.py --summary /repo/out/parity'
rc=$?
[ $rc -gt $status ] && status=$rc
exit $status
