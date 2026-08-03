#!/usr/bin/env bash
# Host-side checks for mod() and add_module.sh (no Docker required).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FAIL=0

pass() { echo "OK  $*"; }
fail() { echo "FAIL  $*"; FAIL=1; }

TMP="$(mktemp -d)"
trap 'rm -rf "${TMP}"' EXIT

# Fake designs tree: copy helpers, stub modules
FAKE="${TMP}/designs"
mkdir -p "${FAKE}/modules/ic101_setup" "${FAKE}/common" "${FAKE}/scripts"
echo "scratch" > "${FAKE}/modules/ic101_setup/README.md"
# Noise that must NOT appear in mod listings
echo "x" > "${FAKE}/modules/README.md"
echo "ad101/" > "${FAKE}/modules/.gitignore"
cp "${ROOT}/common/.designinit" "${FAKE}/common/.designinit"
cp "${ROOT}/scripts/add_module.sh" "${FAKE}/scripts/add_module.sh"
chmod +x "${FAKE}/scripts/add_module.sh"

# Patch DESIGNS default inside sourced file by exporting before source
export DESIGNS="${FAKE}"
export PDK_ROOT="${TMP}/empty-pdk"
# Avoid sak-pdk / noisy PDK setup — source in a subshell-friendly way
# shellcheck source=/dev/null
. "${FAKE}/common/.designinit" >/dev/null

# --- mod list ---
LIST_OUT="$(mod)"
echo "${LIST_OUT}" | grep -q 'ic101_setup' && pass "mod lists ic101_setup" || fail "mod lists ic101_setup"
echo "${LIST_OUT}" | grep -q 'README.md' && fail "mod should not list README.md" || pass "mod omits README.md"
echo "${LIST_OUT}" | grep -q '\.gitignore' && fail "mod should not list .gitignore" || pass "mod omits .gitignore"

# --- mod enter ---
START="$(pwd)"
mod ic101_setup >/dev/null
[ "$(pwd)" = "${FAKE}/modules/ic101_setup" ] && pass "mod ic101_setup cds" || fail "mod ic101_setup cds (got $(pwd))"
cd "${START}"

# --- mod missing ---
if mod does_not_exist >/dev/null 2>&1; then
  fail "mod missing should fail"
else
  pass "mod missing fails"
fi
cd "${START}"

# --- mod help ---
mod help 2>/dev/null | grep -q 'mod add' && pass "mod help mentions add" || fail "mod help mentions add"

# --- add_module validation (no network) ---
if bash "${FAKE}/scripts/add_module.sh" >/dev/null 2>&1; then
  fail "add_module with no args should fail"
else
  pass "add_module no-args fails"
fi

if bash "${FAKE}/scripts/add_module.sh" 'bad name' >/dev/null 2>&1; then
  fail "add_module rejects spaces"
else
  pass "add_module rejects spaces"
fi

if bash "${FAKE}/scripts/add_module.sh" '../escape' >/dev/null 2>&1; then
  fail "add_module rejects path chars"
else
  pass "add_module rejects path chars"
fi

# Existing module refuse
if DESIGNS="${FAKE}" bash "${FAKE}/scripts/add_module.sh" ic101_setup >/dev/null 2>&1; then
  fail "add_module should refuse existing module"
else
  pass "add_module refuses existing"
fi

# Fake git clone success path
mkdir -p "${TMP}/bin"
cat > "${TMP}/bin/git" <<'EOF'
#!/usr/bin/env bash
# Minimal git stub: git clone <url> <dest>
if [ "$1" = "clone" ]; then
  dest="${3:?}"
  mkdir -p "${dest}"
  echo "stub" > "${dest}/.cloned"
  exit 0
fi
exit 1
EOF
chmod +x "${TMP}/bin/git"
export PATH="${TMP}/bin:${PATH}"

DESIGNS="${FAKE}" bash "${FAKE}/scripts/add_module.sh" ad101
[ -f "${FAKE}/modules/ad101/.cloned" ] && pass "add_module clones via git" || fail "add_module clones via git"

# mod add should cd after successful add (reuse stub git; remove first)
rm -rf "${FAKE}/modules/demo_course"
START="$(pwd)"
mod add demo_course >/dev/null
[ "$(pwd)" = "${FAKE}/modules/demo_course" ] && pass "mod add cds into module" || fail "mod add cds (got $(pwd))"
cd "${START}"

if [ "${FAIL}" -eq 0 ]; then
  echo "=== mod helper tests passed ==="
  exit 0
fi
echo "=== mod helper tests failed ==="
exit 1
