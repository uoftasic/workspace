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
