#!/usr/bin/env bash
# First-run check: tools, SKY130 PDK, and course-module helpers. Run inside the container.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)/.."
REPO_ROOT="$(cd "${REPO_ROOT}" && pwd)"
# Prefer the real mount path in-container; fall back to this checkout on the host.
export DESIGNS="${DESIGNS:-${REPO_ROOT}}"

# Remember what the CALLER's shell had before we touch anything. This script
# sources the environment itself so it can run from anywhere, which means that
# by the time it checks the PDK it has already fixed it — so on its own it can
# never tell you that your own terminal is misconfigured. That is the failure
# students actually hit: the smoke test passes, then XSchem opens on the wrong
# PDK in the very next command, because their shell never sourced anything.
INHERITED_PDK="${PDK:-unset}"
# The same for KLayout. A KLayout started from the caller's terminal loads the
# klayout-magic-pcells plugin only if that terminal's KLAYOUT_PATH includes
# $DESIGNS/klayout, and it gets .designinit's KMP_PDKS and KMP_DRC_MODE only if
# that terminal has them set.
INHERITED_KLAYOUT_PATH="${KLAYOUT_PATH:-}"
INHERITED_KMP_PDKS="${KMP_PDKS:-unset}"
INHERITED_KMP_DRC_MODE="${KMP_DRC_MODE:-unset}"

# shellcheck source=/dev/null
[ -f "${REPO_ROOT}/common/.designinit" ] && . "${REPO_ROOT}/common/.designinit"

fail=0
check() {
  if command -v "$1" >/dev/null 2>&1; then
    echo "OK  $1"
  else
    echo "FAIL  $1 not found"
    fail=1
  fi
}

echo "=== ASIC-EDU workspace smoke test ==="
check ngspice
check xschem
check magic
check netgen
check yosys
check klayout

# Check the PDK the tools are actually USING, not just that a directory exists.
#
# sky130A always exists in this image, so "is the directory there" passes even
# when the environment is pointed at a different PDK entirely. The image starts
# on ihp-sg13g2, and PDKPATH, SPICE_USERINIT_DIR and KLAYOUT_PATH follow that,
# not $PDK — so ngspice and KLayout can be reading IHP setup while this script
# cheerfully reports sky130A. That is a false pass in the one check that is
# supposed to gate the whole workbench.
if [ ! -d "${PDK_ROOT:-/foss/pdks}/sky130A" ]; then
  echo "FAIL  sky130A not present at ${PDK_ROOT:-/foss/pdks}/sky130A"
  fail=1
elif [ "${PDK:-}" != "sky130A" ]; then
  echo "FAIL  PDK is '${PDK:-unset}', not sky130A — run: . ${DESIGNS:-/foss/designs}/.designinit"
  fail=1
elif [ "${PDKPATH:-}" != "${PDK_ROOT:-/foss/pdks}/sky130A" ]; then
  # This is the failure mode that used to slip through: $PDK says sky130A while
  # the derived paths still point at whichever PDK the image booted on.
  echo "FAIL  PDKPATH is '${PDKPATH:-unset}', not ${PDK_ROOT:-/foss/pdks}/sky130A"
  echo "      run: . ${DESIGNS:-/foss/designs}/.designinit"
  fail=1
else
  echo "OK  PDK sky130A at ${PDKPATH}"
  for v in SPICE_USERINIT_DIR KLAYOUT_PATH; do
    case "${!v:-}" in
      *sky130A*) : ;;
      "")        echo "WARN  ${v} is unset" ;;
      *)         echo "WARN  ${v} does not mention sky130A: ${!v}" ;;
    esac
  done
  # Now report on the shell that called us, which we deliberately snapshotted
  # before sourcing anything.
  if [ "${INHERITED_PDK}" != "sky130A" ]; then
    echo "WARN  your shell started on PDK '${INHERITED_PDK}', not sky130A."
    echo "      This script fixed its own environment, so the checks above pass,"
    echo "      but tools you launch from that terminal will use the wrong PDK."
    echo "      Every login shell should pick this up automatically from"
    echo "      ${DESIGNS}/.designinit — if it is not, open a new terminal, or run:"
    echo "        . ${DESIGNS}/.designinit"
  fi
fi

# ngspice's banner opens with a row of asterisks and puts the version on the
# SECOND line, so "head -1" printed a bare ****** - which, in the first command
# a student ever runs, reads like something went wrong.
if ngspice -v >/dev/null 2>&1; then
  ver=$(ngspice -v 2>/dev/null | grep -m1 -oE 'ngspice-[0-9][0-9.]*' || true)
  echo "    ${ver:-ngspice (version not reported)}"
fi

# KLayout with the klayout-magic-pcells plugin, which common/.designinit puts
# on KLAYOUT_PATH. A hidden KLayout runs scripts/klayout_check.py, which prints
# what KLayout loaded and builds one PCell. Then the plugin's own doctor starts
# Magic for sky130A and checks the running Magic against the device list the
# plugin ships. The two take 5 to 10 s, most of it KLayout starting.
echo "--- KLayout ---"
plugin_dir="${REPO_ROOT}/klayout/salt/klayout-magic-pcells"
plugin_tag="$(awk '$1 == "tag" { print $2 }' "${REPO_ROOT}/klayout/PLUGIN_VERSION" 2>/dev/null || true)"
if command -v klayout >/dev/null 2>&1; then
  kl_out="$(QT_QPA_PLATFORM=offscreen klayout -z -nc -r "${REPO_ROOT}/scripts/klayout_check.py" 2>&1 || true)"
  if grep -qx 'TECH sky130A' <<<"${kl_out}"; then
    echo "OK  KLayout technology sky130A"
  else
    echo "FAIL  KLayout has no sky130A technology (KLAYOUT_PATH is '${KLAYOUT_PATH:-unset}')"
    echo "      run: . ${DESIGNS}/.designinit"
    grep -v -e '^TECH' -e '^LIB' -e '^Loaded sky130' <<<"${kl_out}" | tail -5 | sed 's/^/      /' || true
    fail=1
  fi
  if ! grep -qx 'LIB sky130_magic' <<<"${kl_out}"; then
    echo "FAIL  KLayout has no sky130_magic library (klayout-magic-pcells)"
    if [ ! -f "${plugin_dir}/grain.xml" ]; then
      echo "      ${plugin_dir} is missing: run git pull in the workspace"
    else
      case ":${KLAYOUT_PATH:-}:" in
        *":${DESIGNS}/klayout:"*)
          # Show KLayout's own messages. The doctor check below covers Magic and the PDK.
          grep -v -e '^TECH' -e '^LIB' -e '^MENU' -e '^Loaded sky130' <<<"${kl_out}" | tail -5 | sed 's/^/      /' || true ;;
        *) echo "      run: . ${DESIGNS}/.designinit" ;;
      esac
    fi
    fail=1
  else
    echo "OK  KLayout library sky130_magic (klayout-magic-pcells ${plugin_tag:-of unknown version})"
    if grep -q '^MENUITEM Run Magic DRC' <<<"${kl_out}"; then
      echo "OK  KLayout Magic menu ($(grep -c '^MENUITEM ' <<<"${kl_out}") entries)"
    else
      echo "FAIL  KLayout has no Magic menu (KMP_MENU is '${KMP_MENU:-unset}'; KMP_MENU=0 leaves the menu out)"
      fail=1
    fi
    if grep -q '^PCELL sky130_fd_pr__nfet_01v8 ' <<<"${kl_out}"; then
      echo "OK  Magic built a sky130_fd_pr__nfet_01v8 for KLayout"
    else
      echo "FAIL  sky130_magic could not build sky130_fd_pr__nfet_01v8"
      grep -v -e '^TECH' -e '^LIB' -e '^MENU' -e '^Loaded sky130' <<<"${kl_out}" | tail -5 | sed 's/^/      /' || true
      fail=1
    fi
  fi

  if doctor_out="$(PYTHONPATH="${plugin_dir}/python${PYTHONPATH:+:${PYTHONPATH}}" \
      python3 -m klayout_magic_pcells doctor 2>&1)"; then
    echo "OK  klayout-magic-pcells doctor"
  else
    echo "FAIL  klayout-magic-pcells doctor. Its findings:"
    grep -E 'PROBLEM|MISMATCH|MISSING|ERROR|error' <<<"${doctor_out}" | sed 's/^/      /' ||
      tail -5 <<<"${doctor_out}" | sed 's/^/      /'
    echo "      For the whole report, run: PYTHONPATH=${plugin_dir}/python python3 -m klayout_magic_pcells doctor"
    fail=1
  fi

  # Check the caller's own terminal too, but only when its PDK is sky130A. If
  # it is not, the PDK block above has already warned, and the same fix covers
  # KLayout.
  if [ "${INHERITED_PDK}" = "sky130A" ]; then
    case ":${INHERITED_KLAYOUT_PATH}:" in
      *":${DESIGNS}/klayout:"*) ;;
      *) echo "WARN  your shell's KLAYOUT_PATH does not include ${DESIGNS}/klayout, so a"
         echo "      KLayout started from it has no sky130_magic library and no Magic menu."
         echo "      Running sak-pdk-script.sh resets KLAYOUT_PATH. Open a new terminal, or run:"
         echo "        . ${DESIGNS}/.designinit" ;;
    esac
    if [ "${INHERITED_KMP_PDKS}" != "sky130A" ]; then
      echo "WARN  KMP_PDKS is '${INHERITED_KMP_PDKS}' in your shell, not sky130A; .designinit sets it"
    fi
    if [ "${INHERITED_KMP_DRC_MODE}" != "flat" ]; then
      echo "WARN  KMP_DRC_MODE is '${INHERITED_KMP_DRC_MODE}' in your shell, not flat. AD104-K's"
      echo "      pages expect Magic > Run Magic DRC... to open in Flat mode; .designinit sets it"
    fi
  fi
fi

echo "--- module helpers ---"
if declare -F mod >/dev/null 2>&1; then
  echo "OK  mod function loaded"
else
  echo "FAIL  mod function not defined — source common/.designinit"
  fail=1
fi

if [ -f "${DESIGNS}/scripts/add_module.sh" ]; then
  echo "OK  add_module.sh present"
else
  echo "FAIL  scripts/add_module.sh missing"
  fail=1
fi

if declare -F mod >/dev/null 2>&1; then
  list_out="$(mod 2>/dev/null || true)"
  if echo "${list_out}" | grep -q 'ic101_setup'; then
    echo "OK  mod lists ic101_setup"
  else
    echo "FAIL  mod did not list ic101_setup"
    fail=1
  fi

  here="$(pwd)"
  if mod ic101_setup >/dev/null 2>&1 && [ "$(pwd)" = "${DESIGNS}/modules/ic101_setup" ]; then
    echo "OK  mod ic101_setup"
  else
    echo "FAIL  mod ic101_setup (cwd=$(pwd))"
    fail=1
  fi
  cd "${here}" || true
fi

if [ "$fail" -eq 0 ]; then
  echo "=== All checks passed ==="
else
  echo "=== Some checks failed ==="
  exit 1
fi
