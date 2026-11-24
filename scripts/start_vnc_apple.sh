#!/usr/bin/env bash
# Launch IIC-OSIC-TOOLS using Apple's `container` runtime instead of Docker
# Desktop, and open the EDA desktop in the TigerVNC viewer. macOS 26+ on Apple
# silicon only.
#
#   https://github.com/apple/container
#
# Each Apple container is its own lightweight VM (Virtualization.framework).
# Docker Desktop instead runs every container inside one shared Linux VM.
#
# Same container as start_vnc.sh: named asic-edu-osic, with this repo at
# /foss/designs. Running it again replaces the container with a fresh one; files
# under /foss/designs are kept.
#
# The desktop is reachable two ways, both on this Mac only:
#   localhost::5901        the TigerVNC viewer, opened for you if it is installed
#                          (VNC_CLIENT=tigervnc, the default)
#   http://localhost:8080/ noVNC in a browser (VNC_CLIENT=browser opens this instead)
# TigerVNC connects to the VNC server directly and speaks the standard VNC
# clipboard. noVNC goes through the browser and a websocket proxy in the container.
#
# Why not macOS Screen Sharing: it greys out its clipboard commands for non-Mac
# VNC servers, so nothing copied on the Mac can be pasted into the desktop. It
# also rejects this server's default login (VeNCrypt), which TigerVNC accepts.
#
# Differences from the Docker script, and why:
#   * --memory / --cpus are passed explicitly. An Apple container is a VM whose
#     default size is 1 GiB of RAM, which is not enough for KLayout, Magic or
#     LibreLane. Docker Desktop instead hands out its whole VM's memory.
#   * No --security-opt seccomp=unconfined: the flag does not exist here, and
#     the container already runs in its own VM with its own kernel.
#   * The noVNC landing page is copied in after start instead of being
#     bind-mounted as a single file. Bind mounts here are virtiofs shares of
#     directories, not of single files.
set -euo pipefail

DOCKER_TAG="${DOCKER_TAG:-2026.08}"
IMAGE="docker.io/hpretl/iic-osic-tools:${DOCKER_TAG}"
CONTAINER_NAME="${CONTAINER_NAME:-asic-edu-osic}"
VNC_PW="${VNC_PW:-abc123}"
# Upstream image defaults to 1680x1050; a smaller desktop fits typical laptop browsers.
VNC_RESOLUTION="${VNC_RESOLUTION:-1280x800}"
# noVNC listens on 8080 here, not 80 as in start_vnc.sh, on both sides:
#   * on the Mac, Apple's runtime will not publish a host port below 1024
#     without root;
#   * inside the container, the desktop runs as your uid, which cannot bind
#     port 80 either. Docker allows that by setting
#     net.ipv4.ip_unprivileged_port_start=0 in every container; Apple's runtime
#     does not, so websockify dies and takes the container down with it.
HOST_PORT="${HOST_PORT:-8080}"
VNC_PORT="${VNC_PORT:-5901}"
VNC_CLIENT="${VNC_CLIENT:-tigervnc}"   # tigervnc, browser (noVNC), or none
TIGERVNC_DOWNLOAD="https://sourceforge.net/projects/tigervnc/files/stable/"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

die() { echo "ERROR: $*" >&2; exit 1; }

# --- preflight -------------------------------------------------------------
[ "$(uname -s)" = "Darwin" ] || die "this script is for macOS. On Linux use ./scripts/start_vnc.sh"
[ "$(uname -m)" = "arm64" ]  || die "Apple's container runtime needs Apple silicon. On an Intel Mac use ./scripts/start_vnc.sh with Docker Desktop"
command -v container >/dev/null 2>&1 || die "the 'container' command is not installed.
  Install the signed .pkg from https://github.com/apple/container/releases
  (or: brew install container), then run this script again."

# Start the container services if they are not already running. The first run
# downloads a Linux kernel; --enable-kernel-install answers that prompt so the
# script doesn't stop to ask.
if ! container system status >/dev/null 2>&1; then
  echo "Starting Apple container services..."
  container system start --enable-kernel-install
fi

# --- size the VM -----------------------------------------------------------
# Default: half the Mac's RAM (at least 4 GiB, at most 16 GiB), and all but two
# of its cores (at least 2). Override with CONTAINER_MEMORY=12g CONTAINER_CPUS=6.
host_mem_gib=$(( $(sysctl -n hw.memsize) / 1024 / 1024 / 1024 ))
host_cpus=$(sysctl -n hw.ncpu)
mem_gib=$(( host_mem_gib / 2 ))
[ "${mem_gib}" -lt 4 ]  && mem_gib=4
[ "${mem_gib}" -gt 16 ] && mem_gib=16
cpus=$(( host_cpus - 2 ))
[ "${cpus}" -lt 2 ] && cpus=2
CONTAINER_MEMORY="${CONTAINER_MEMORY:-${mem_gib}g}"
CONTAINER_CPUS="${CONTAINER_CPUS:-${cpus}}"

echo "Runtime:  Apple container ($(container --version 2>/dev/null | head -1))"
echo "Image:    ${IMAGE}"
echo "Mount:    ${REPO_ROOT} -> /foss/designs"
echo "VM size:  ${CONTAINER_CPUS} CPUs, ${CONTAINER_MEMORY} RAM  (override: CONTAINER_CPUS=… CONTAINER_MEMORY=…)"
echo ""
echo "EDA desktop (password: ${VNC_PW}, ${VNC_RESOLUTION}):"
echo "  TigerVNC viewer:    localhost::${VNC_PORT}"
echo "  Browser (noVNC):    http://localhost:${HOST_PORT}/"
echo "  (override resolution: VNC_RESOLUTION=1920x1080 ./scripts/start_vnc_apple.sh)"
echo ""
echo "Course manuals are online: https://edu.uoftasic.com/"
echo ""
echo "Confirm tag ${DOCKER_TAG} on: https://github.com/iic-jku/IIC-OSIC-TOOLS/releases"

# The image is large (several GB); the first pull takes a while. Later runs
# only check for changes.
container image pull "${IMAGE}"

# Close any TigerVNC viewer this script opened for the container we're about to
# replace; it would only sit there showing a lost connection.
pkill -f "vncviewer localhost::${VNC_PORT}\$" >/dev/null 2>&1 || true
container delete --force "${CONTAINER_NAME}" >/dev/null 2>&1 || true

container run -d --name "${CONTAINER_NAME}" \
  --cpus "${CONTAINER_CPUS}" \
  --memory "${CONTAINER_MEMORY}" \
  --shm-size 1G \
  --user "$(id -u):$(id -g)" \
  -p "127.0.0.1:${HOST_PORT}:8080" \
  -p "127.0.0.1:${VNC_PORT}:5901" \
  -e VNC_PW="${VNC_PW}" \
  -e VNC_RESOLUTION="${VNC_RESOLUTION}" \
  -e NO_VNC_PORT=8080 \
  -v "${REPO_ROOT}:/foss/designs" \
  "${IMAGE}" >/dev/null

echo "Container ${CONTAINER_NAME} started."

# Our noVNC landing page (auto-connect with the password). Docker bind-mounts
# this single file read-only; here we copy it in as root once the VM is up.
for _ in $(seq 1 45); do
  container exec "${CONTAINER_NAME}" true >/dev/null 2>&1 && break
  sleep 1
done
container exec -u root -i "${CONTAINER_NAME}" \
  sh -c 'cat > /usr/share/novnc/index.html' < "${REPO_ROOT}/docker/novnc-index.html" \
  || echo "WARNING: could not install the noVNC landing page; use http://localhost:${HOST_PORT}/vnc.html"

CONTAINER_CLI=container HOST_PORT="${HOST_PORT}" VNC_PW="${VNC_PW}" "${SCRIPT_DIR}/post_start_services.sh"

# Wait until the VNC server answers with its RFB greeting, then open the viewer.
# (A bare TCP check isn't enough: Apple's port forwarder can accept the
# connection before the server inside is listening.)
vnc_up=0
for _ in $(seq 1 30); do
  if [ "$( (sleep 1) | nc -w 2 127.0.0.1 "${VNC_PORT}" 2>/dev/null | head -c 3)" = "RFB" ]; then
    vnc_up=1; break
  fi
done

find_tigervnc() {
  local app
  for app in /Applications/TigerVNC*.app "${HOME}"/Applications/TigerVNC*.app; do
    [ -d "${app}" ] && { echo "${app}"; return 0; }
  done
  return 1
}

case "${VNC_CLIENT}" in
  tigervnc)
    if ! app="$(find_tigervnc)"; then
      echo "TigerVNC viewer not found in /Applications. Install it from ${TIGERVNC_DOWNLOAD}"
      echo "  (the TigerVNC-<version>.dmg file), then connect to localhost::${VNC_PORT}."
      echo "  Until then, the desktop is in your browser at http://localhost:${HOST_PORT}/"
    elif [ "${vnc_up}" -eq 1 ]; then
      echo "Opening the TigerVNC viewer on localhost::${VNC_PORT} (password: ${VNC_PW})"
      # -n starts a new viewer each time. Without it, macOS hands the address
      # to a viewer that is already open, which ignores it.
      open -n -a "${app}" --args "localhost::${VNC_PORT}"
    else
      echo "WARNING: the VNC server isn't answering on localhost:${VNC_PORT} yet."
      echo "  In a minute, open TigerVNC and connect to localhost::${VNC_PORT}."
    fi
    ;;
  browser) open "http://localhost:${HOST_PORT}/" ;;
  none)    : ;;
  *)       echo "WARNING: unknown VNC_CLIENT='${VNC_CLIENT}' (use tigervnc, browser or none)" ;;
esac

echo "Stop it (frees its RAM):   container stop ${CONTAINER_NAME}"
echo "Shell into it:             container exec -it ${CONTAINER_NAME} bash -l"
