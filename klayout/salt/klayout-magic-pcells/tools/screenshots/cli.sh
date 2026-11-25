#!/bin/sh
# Print the command-line transcripts of guide.md, run in the pinned image
# with the repository where the guide puts it:
#
#   tools/screenshots/cli.sh > /tmp/cli.txt
#
# Each command is printed after "$ ", then its output. The cache lives in
# the container and starts empty, as on a fresh install.
set -eu
IMAGE="${KMP_IMAGE:-hpretl/iic-osic-tools@sha256:3c371645b19c6f6564dc8c7b21e39ad1c1833d274fe5b85639afe1ba9d7987e7}"
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
exec docker run --rm --user "$(id -u):$(id -g)" -e PDK=sky130A \
  -v "$REPO:/foss/designs/klayout-magic-pcells" -w /foss/designs/klayout-magic-pcells \
  "$IMAGE" --skip bash -lc /foss/designs/klayout-magic-pcells/tools/screenshots/cli_inside.sh 2>&1
