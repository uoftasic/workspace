#!/usr/bin/env bash
# Enable VNC clipboard sync inside a running IIC-OSIC-TOOLS container.
# TigerVNC needs vncconfig; Xfce often needs autocutsel for PRIMARY/CLIPBOARD.
set -euo pipefail

CONTAINER_NAME="${CONTAINER_NAME:-asic-edu-osic}"
# docker (default) or container (Apple's runtime; see start_vnc_apple.sh). Both take
# the same exec/cp arguments.
CTR="${CONTAINER_CLI:-docker}"
DISPLAY_NUM="${VNC_DISPLAY:-:1}"

if ! "${CTR}" exec "${CONTAINER_NAME}" true 2>/dev/null; then
  echo "WARNING: container ${CONTAINER_NAME} not running — skip VNC desktop setup."
  exit 0
fi

if ! "${CTR}" exec "${CONTAINER_NAME}" bash -lc "command -v autocutsel >/dev/null 2>&1"; then
  "${CTR}" exec -u root "${CONTAINER_NAME}" bash -lc \
    "DEBIAN_FRONTEND=noninteractive apt-get update -qq \
     && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq autocutsel" \
    2>/dev/null || true
fi

"${CTR}" exec "${CONTAINER_NAME}" bash -lc "
set -e
export DISPLAY='${DISPLAY_NUM}'

# The patterns are anchored with ^ on purpose. pgrep -f matches whole command
# lines, and this script's own bash -lc command line contains every helper's
# name, so an unanchored pattern always matches it and no helper ever starts.
start_if_missing() {
  local pattern=\$1
  shift
  if pgrep -f \"\$pattern\" >/dev/null 2>&1; then
    return 0
  fi
  \"\$@\" >/dev/null 2>&1 &
}

if command -v vncconfig >/dev/null 2>&1; then
  start_if_missing '^vncconfig ' vncconfig -iconic -display '${DISPLAY_NUM}'
fi

if command -v autocutsel >/dev/null 2>&1; then
  start_if_missing '^autocutsel -fork\$' autocutsel -fork
  start_if_missing '^autocutsel -fork -s PRIMARY' autocutsel -fork -s PRIMARY
fi
" 2>/dev/null || echo "WARNING: VNC clipboard helpers could not be started."
