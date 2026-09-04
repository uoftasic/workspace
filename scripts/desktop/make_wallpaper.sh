#!/usr/bin/env bash
# Render the workbench wallpaper. Run inside the shot rig (needs ImageMagick).
#
#   docker run --rm -v "$PWD:/out" asic-edu/shot-rig:2026.08 --skip bash /out/make_wallpaper.sh
#
# The stock image ships a Johannes Kepler University wallpaper that is cropped at
# 1280x800 and says nothing about this course. This replaces it with something
# that (a) belongs to us and (b) does a job: the first three commands are on it,
# so a student who forgets them does not have to go back to the browser.
set -euo pipefail
OUT="${1:-/out/asic-edu-wallpaper.png}"
W=1920; H=1200          # generated large; Xfce scales down to any desktop size
# Xfce lays desktop icons down the LEFT column, so everything here sits right of
# x=620 to stay clear of them. Re-check if the launcher set ever grows.
X=620

BG="#0E1116"            # matches the animation series palette
INK="#ECEFF1"
MUTED="#78909C"
ACCENT="#4FC3F7"

convert -size ${W}x${H} "xc:${BG}" \
  -font DejaVu-Sans-Bold -pointsize 96 -fill "${INK}" \
  -gravity NorthWest -annotate +${X}+180 'UofT ASIC' \
  -font DejaVu-Sans -pointsize 40 -fill "${ACCENT}" \
  -gravity NorthWest -annotate +${X}+310 'Internal Education Initiative' \
  -font DejaVu-Sans -pointsize 30 -fill "${MUTED}" \
  -gravity NorthWest -annotate +${X}+430 'Start here — in a terminal:' \
  -font DejaVu-Sans-Mono -pointsize 32 -fill "${INK}" \
  -gravity NorthWest -annotate +${X}+500 '. /foss/designs/common/.designinit' \
  -gravity NorthWest -annotate +${X}+552 'mod                    # list your courses' \
  -gravity NorthWest -annotate +${X}+604 'mod dd103              # enter one' \
  -font DejaVu-Sans -pointsize 26 -fill "${MUTED}" \
  -gravity NorthWest -annotate +${X}+700 'Labs also run with make alone if your setup misbehaves.' \
  -font DejaVu-Sans -pointsize 26 -fill "${MUTED}" \
  -gravity SouthWest -annotate +${X}+120 'edu.uoftasic.com   ·   discord.gg/hrJnP5UsGz' \
  "${OUT}"

# a thin accent rule under the wordmark
convert "${OUT}" -fill "${ACCENT}" -draw "rectangle ${X},280 $((X+480)),284" "${OUT}"
identify -format 'wallpaper %wx%h %b\n' "${OUT}"
