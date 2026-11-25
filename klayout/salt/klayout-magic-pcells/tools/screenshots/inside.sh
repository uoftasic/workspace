#!/bin/bash
# Runs inside the image (see take.sh). Installs the package as the guide
# does, runs gui.py's sessions and writes the PNGs to /out.
# KMP_SHOT_SESSIONS picks the sessions (default: main reopen defunct magic).
set -eu
R=/foss/designs/klayout-magic-pcells
ln -s /foss/designs/klayout-magic-pcells ~/.klayout/salt/klayout-magic-pcells
mkdir -p /work/raw
SESSIONS="${KMP_SHOT_SESSIONS:-main reopen defunct magic}"

run() {
  local session=$1
  KMP_SHOT_SESSION=$session KMP_SHOT_WORK=/work timeout 600 \
    xvfb-run -a -s "-screen 0 1440x900x24 -dpi 96" \
    klayout -e -rm "$R/tools/screenshots/gui.py" > "/work/klayout-$session.log" 2>&1 || true
  if [ ! -f "/work/done-$session" ]; then
    echo "session $session failed; gui.py's log:" >&2
    tail -40 "/work/gui-$session.log" >&2 || true
    exit 1
  fi
  echo "session $session: done"
}

for s in $SESSIONS; do
  case $s in
    # sky130_magic missing: only gf180mcuD registers.
    defunct) KMP_PDKS=gf180mcuD run defunct ;;
    # The case-suite layouts and the 250 um block, built before KLayout starts.
    magic) python3 "$R/tools/screenshots/magic_inputs.py" /work > /work/magic-inputs.log 2>&1 \
             || { tail -20 /work/magic-inputs.log >&2; exit 1; }
           run magic ;;
    *) run "$s" ;;
  esac
done
# shellcheck disable=SC2086
python3 "$R/tools/screenshots/finish.py" /work/raw /out $SESSIONS
