#!/usr/bin/env bash
# Maintainer script: replace the workspace's copy of klayout-magic-pcells with
# a tagged release.
# Usage: scripts/update_klayout_plugin.sh <tag>     e.g. v0.6.2
#
# The plugin is vendored: klayout/salt/klayout-magic-pcells is plain
# `git archive <tag>` output, and klayout/PLUGIN_VERSION records which tag it
# is. Students get it with `git pull`, and starting the container does not need
# GitHub. This script is the only part that uses the network. No other script
# in the workspace calls it, .designinit and start_vnc.sh included; a
# maintainer runs it by hand.
#
# It stages the new copy and prints what changed. Review the change, run the
# smoke test in the container, then commit.
set -euo pipefail

URL="https://github.com/uoftasic/klayout-magic-pcells"

if [ "$#" -ne 1 ] || ! [[ "$1" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Usage: $(basename "$0") <tag>     e.g. v0.6.2" >&2
  exit 1
fi
TAG="$1"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEST="${REPO_ROOT}/klayout/salt/klayout-magic-pcells"
VERSION_FILE="${REPO_ROOT}/klayout/PLUGIN_VERSION"

tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT

echo "Cloning ${URL} at ${TAG}"
git -c advice.detachedHead=false clone --quiet --depth 1 --branch "${TAG}" "${URL}" "${tmp}/src"

tag_object="$(git -C "${tmp}/src" rev-parse "refs/tags/${TAG}")"
commit="$(git -C "${tmp}/src" rev-parse "refs/tags/${TAG}^{commit}")"
if [ "$(git -C "${tmp}/src" cat-file -t "${tag_object}")" != "tag" ]; then
  echo "update_klayout_plugin: ${TAG} is a lightweight tag; the plugin's releases are annotated tags" >&2
  exit 1
fi

# KLayout's package manager shows the version in grain.xml, so that version
# has to match the tag.
grain_version="$(git -C "${tmp}/src" show "${TAG}:grain.xml" |
  sed -n 's:.*<version>\(.*\)</version>.*:\1:p' | head -1)"
if [ "${grain_version}" != "${TAG#v}" ]; then
  echo "update_klayout_plugin: grain.xml says version ${grain_version:-none}, but the tag is ${TAG}" >&2
  exit 1
fi

rm -rf "${DEST}"
mkdir -p "${DEST}"
git -C "${tmp}/src" archive --format=tar "${TAG}" | tar -x -C "${DEST}"

cat > "${VERSION_FILE}" <<EOF
tag ${TAG}
commit ${commit}
tag-object ${tag_object}
source ${URL} (git archive ${TAG})
EOF

cd "${REPO_ROOT}"
git add -A -- klayout/

# git add -A skips, without a warning, any file of the release that matches a
# pattern in the workspace's .gitignore (*.log, *.raw, ...), so that file would
# be left out of the commit.
ignored="$(git ls-files --others --ignored --exclude-standard -- klayout/)"
if [ -n "${ignored}" ]; then
  echo "update_klayout_plugin: .gitignore keeps these files of the release out of git:" >&2
  echo "${ignored}" | sed 's/^/  /' >&2
  echo "  Add them with git add -f, or a ! line in .gitignore, before committing." >&2
  exit 1
fi

echo ""
git diff --cached --stat -- klayout/ | tail -25
echo ""
echo "OK  klayout-magic-pcells ${TAG} (commit ${commit:0:7}) is staged under klayout/."
echo "    Review with: git diff --cached -- klayout/PLUGIN_VERSION"
echo "    Run scripts/smoke_test.sh in the container, then commit."
