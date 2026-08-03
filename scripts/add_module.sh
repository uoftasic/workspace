#!/usr/bin/env bash
# Clone a uoftasic course repo into workspace modules/<name>.
# Usage: add_module.sh <name>
#   e.g. add_module.sh ad101  →  modules/ad101 from github.com/uoftasic/ad101
set -euo pipefail

usage() {
  echo "Usage: $(basename "$0") <module-name>" >&2
  echo "  Clones https://github.com/uoftasic/<module-name>.git into modules/<module-name>" >&2
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ] || [ "${1:-}" = "help" ]; then
  usage
  exit 0
fi

if [ -z "${1:-}" ] || [ -n "${2:-}" ]; then
  usage
  exit 1
fi

NAME="$1"
if ! [[ "$NAME" =~ ^[a-zA-Z0-9][a-zA-Z0-9_-]*$ ]]; then
  echo "add_module: invalid module name: ${NAME}" >&2
  echo "  expected something like: ad101, ic101_setup, dd103_rtl" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DESIGNS="${DESIGNS:-${REPO_ROOT}}"
MODULES_DIR="${DESIGNS}/modules"
TARGET="${MODULES_DIR}/${NAME}"
URL="https://github.com/uoftasic/${NAME}.git"

if ! command -v git >/dev/null 2>&1; then
  echo "add_module: git not found on PATH" >&2
  exit 1
fi

mkdir -p "${MODULES_DIR}"

if [ -e "${TARGET}" ]; then
  # Refuse non-empty existing paths; allow retry only if empty dir left behind.
  if [ -d "${TARGET}" ] && [ -z "$(ls -A "${TARGET}" 2>/dev/null || true)" ]; then
    rmdir "${TARGET}" 2>/dev/null || true
  else
    echo "add_module: already exists: ${TARGET}" >&2
    echo "  use: mod ${NAME}" >&2
    exit 1
  fi
fi

echo "Cloning ${URL}"
echo "     into ${TARGET}"
if ! git clone "${URL}" "${TARGET}"; then
  # Avoid leaving a broken partial checkout.
  rm -rf "${TARGET}"
  echo "add_module: clone failed for ${NAME}" >&2
  exit 1
fi

echo "OK  module ready: ${TARGET}"
echo "    run: mod ${NAME}"
