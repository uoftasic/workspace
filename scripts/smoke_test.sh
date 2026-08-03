#!/usr/bin/env bash
# First-run check: tools, SKY130 PDK, and course-module helpers. Run inside the container.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)/.."
REPO_ROOT="$(cd "${REPO_ROOT}" && pwd)"
# Prefer the real mount path in-container; fall back to this checkout on the host.
export DESIGNS="${DESIGNS:-${REPO_ROOT}}"
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

if [ -n "${PDK_ROOT:-}" ] && [ -d "${PDK_ROOT}/sky130A" ]; then
  echo "OK  PDK sky130A at ${PDK_ROOT}/sky130A"
else
  echo "FAIL  sky130A not found — run: sak-pdk sky130A"
  fail=1
fi

if ngspice -v >/dev/null 2>&1; then
  ngspice -v | head -1
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
