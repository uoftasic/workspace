#!/usr/bin/env bash
# Dress the workbench desktop: our wallpaper, and launchers for the tools a
# student actually opens.
#
# The stock first-launch desktop is a Johannes Kepler University wallpaper,
# cropped at 1280x800, with NO desktop icons at all — nothing to click and no
# indication of what to do next. This fixes that.
#
# Run on the HOST, against a running container:
#   ./install_desktop.sh                      # defaults to asic-edu-osic
#   CONTAINER_NAME=my-box ./install_desktop.sh
#
# Idempotent. Safe to call from post_start_services.sh on every launch.
set -euo pipefail

CONTAINER_NAME="${CONTAINER_NAME:-asic-edu-osic}"
DISPLAY_NUM="${VNC_DISPLAY:-:1}"
HERE="$(cd "$(dirname "$0")" && pwd)"
WALLPAPER="${HERE}/asic-edu-wallpaper.png"

if ! docker exec "${CONTAINER_NAME}" true 2>/dev/null; then
  echo "WARNING: container ${CONTAINER_NAME} not running — skipping desktop setup."
  exit 0
fi

[ -f "${WALLPAPER}" ] || { echo "WARNING: ${WALLPAPER} missing — skipping."; exit 0; }

docker cp "${WALLPAPER}" "${CONTAINER_NAME}:/tmp/asic-edu-wallpaper.png"

docker exec "${CONTAINER_NAME}" bash -c '
set -e
export DISPLAY="'"${DISPLAY_NUM}"'"
mkdir -p "$HOME/.local/share/asic-edu" "$HOME/Desktop"
cp /tmp/asic-edu-wallpaper.png "$HOME/.local/share/asic-edu/wallpaper.png"

# --- launchers ------------------------------------------------------------
# Xfce only trusts a .desktop file it considers executable, and only shows one
# on the desktop if it is marked trusted. Both lines below matter.
mk() {   # mk <file> <Name> <Comment> <Exec> <Icon> <Terminal>
  cat > "$HOME/Desktop/$1" <<DESKTOP
[Desktop Entry]
Version=1.0
Type=Application
Name=$2
Comment=$3
Exec=$4
Icon=$5
Terminal=$6
Categories=Development;
DESKTOP
  chmod +x "$HOME/Desktop/$1"
  gio set "$HOME/Desktop/$1" metadata::xfce-exe-checksum \
      "$(sha256sum "$HOME/Desktop/$1" | awk "{print \$1}")" 2>/dev/null || true
}

mk terminal.desktop  "Terminal"      "Where every course command is typed" \
   "xfce4-terminal --working-directory=/foss/designs" "utilities-terminal" false
mk courses.desktop   "My courses"    "List the course modules you have added" \
   "xfce4-terminal --working-directory=/foss/designs --hold --command=\"bash -lc \\\". /foss/designs/common/.designinit; mod\\\"\"" "folder-documents" false
mk xschem.desktop    "XSchem"        "Draw and simulate schematics (analog track)" \
   "bash -lc \". /foss/designs/common/.designinit >/dev/null 2>&1; exec xschem\"" "applications-electronics" false
mk magic.desktop     "Magic"         "Draw and inspect layout (analog track)" \
   "bash -lc \". /foss/designs/common/.designinit >/dev/null 2>&1; exec magic -d X11 -T sky130A\"" "applications-electronics" false
mk klayout.desktop   "KLayout"       "Open a GDSII and look at your chip" \
   "bash -lc \"exec klayout\"" "image-x-generic" false
mk surfer.desktop    "Surfer"        "Open a waveform (.vcd / .fst)" \
   "bash -lc \"exec surfer\"" "utilities-system-monitor" false
mk docs.desktop      "Course manuals" "edu.uoftasic.com" \
   "xdg-open https://edu.uoftasic.com/" "text-html" false

# --- wallpaper ------------------------------------------------------------
# xfconf needs a session bus; docker exec does not inherit one, so borrow the
# running xfce session bus if we can, then fall back to a fresh one.
set_wallpaper() {
  local bus
  bus="$(grep -z DBUS_SESSION_BUS_ADDRESS /proc/$(pgrep -f xfce4-session | head -1)/environ 2>/dev/null | tr -d "\0" | cut -d= -f2-)"
  [ -n "$bus" ] && export DBUS_SESSION_BUS_ADDRESS="$bus"
  for prop in $(xfconf-query -c xfce4-desktop -l 2>/dev/null | grep -E "last-image$"); do
    xfconf-query -c xfce4-desktop -p "$prop" -s "$HOME/.local/share/asic-edu/wallpaper.png" 2>/dev/null || true
  done
  for prop in $(xfconf-query -c xfce4-desktop -l 2>/dev/null | grep -E "image-style$"); do
    xfconf-query -c xfce4-desktop -p "$prop" -s 5 2>/dev/null || true   # 5 = zoomed
  done
}
set_wallpaper || true

# Make sure the desktop actually shows icons, then repaint.
xfconf-query -c xfce4-desktop -p /desktop-icons/style -s 2 2>/dev/null || true

# Repaint. NEVER pkill xfdesktop here: it does not come back on its own, and you
# are left with a black screen and no icons, which is worse than the wallpaper we
# were trying to replace. --reload is a no-op if it is not running, so start it.
if pgrep -x xfdesktop >/dev/null 2>&1; then
  xfdesktop --reload 2>/dev/null || true
else
  (setsid xfdesktop >/dev/null 2>&1 &) || true
fi
sleep 2
pgrep -x xfdesktop >/dev/null 2>&1 || echo "WARNING: xfdesktop is not running — desktop will be blank."
echo "desktop configured: $(ls "$HOME/Desktop" | wc -l) launchers, xfdesktop pid $(pgrep -x xfdesktop | head -1)"
'
