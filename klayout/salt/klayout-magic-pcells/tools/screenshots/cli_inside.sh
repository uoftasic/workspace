#!/bin/bash
# Runs inside the image (see cli.sh).
cd /foss/designs/klayout-magic-pcells
export PYTHONPATH=$PWD/python
W=$(mktemp -d)
run() {
  echo "\$ $*"
  ( eval "$@" ) 2>&1
  echo "[exit status $?]"
  echo
}
run 'python3 -m klayout_magic_pcells doctor --pdk sky130A'
mkdir -p ~/.config/klayout-magic-pcells
printf '[kmp]\npdks = sky130A, ihp-sg13g2\n' > ~/.config/klayout-magic-pcells/config.ini
run 'cat ~/.config/klayout-magic-pcells/config.ini'
run 'python3 -m klayout_magic_pcells doctor | head -4'
run 'python3 -m klayout_magic_pcells devices | grep -v "^  "'
run 'KMP_PDKS=gf180mcuD python3 -m klayout_magic_pcells devices | head -4'
rm ~/.config/klayout-magic-pcells/config.ini
run 'python3 -m klayout_magic_pcells devices -v --pdk sky130A | sed -n "/^  sky130_fd_pr__nfet_01v8 /,/^  sky130_fd_pr__nfet_01v8_lvt/p" | head -12'
run 'python3 -m klayout_magic_pcells check sky130_fd_pr__nfet_01v8 w=0.1 l=0.1'
run 'python3 -m klayout_magic_pcells check sky130_fd_pr__res_high_po_0p69 w=1.0'
run 'python3 -m klayout_magic_pcells check --pdk sky130A via1 w=0.2 h=1.0'
run 'python3 -m klayout_magic_pcells check --pdk sky130A via1 w=0.263 h=1.0'
run 'python3 -m klayout_magic_pcells check via1 w=1 h=1'
cd "$W"
run 'python3 -m klayout_magic_pcells generate sky130_fd_pr__nfet_01v8 w=1.5 l=0.5 nf=3 -o nfet.gds'
run 'python3 -m klayout_magic_pcells generate sky130_fd_pr__nfet_01v8 l=0.1 -o nfet_short.gds'
run 'python3 -m klayout_magic_pcells audit nfet.gds'
run 'python3 -m klayout_magic_pcells audit nfet.gds --regen'
cd /foss/designs/klayout-magic-pcells
run 'python3 -m klayout_magic_pcells cache stats'
run 'python3 -m klayout_magic_pcells cache prune --pdk sky130A'
run 'python3 -m klayout_magic_pcells cache clear'
rm -rf "$W"
