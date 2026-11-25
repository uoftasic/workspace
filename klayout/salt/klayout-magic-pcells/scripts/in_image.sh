#!/bin/sh
# Run a shell command inside the pinned iic-osic-tools image, with this
# repository mounted at /repo and the working directory set to it.
#
#   scripts/in_image.sh 'python3 tools/build_manifest.py --all --check'
#   KMP_IMAGE_PDK=gf180mcuD scripts/in_image.sh 'python3 -m klayout_magic_pcells doctor'
#
# KMP_IMAGE overrides the image. KMP_IMAGE_PDK (default sky130A) is the
# image's PDK variable inside the container: the image's login profile sets
# KLAYOUT_PATH and the PDK's KLayout setup from it. The login shell (bash -l)
# matters: PATH and the PDK variables come from the image's /etc/profile.d
# script.
set -eu
IMAGE="${KMP_IMAGE:-hpretl/iic-osic-tools@sha256:3c371645b19c6f6564dc8c7b21e39ad1c1833d274fe5b85639afe1ba9d7987e7}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
# Create out/ before docker mounts the repository, so nothing is created as root.
mkdir -p "$REPO/out"
CMD="$1"
shift
exec docker run --rm --user "$(id -u):$(id -g)" \
  -e PDK="${KMP_IMAGE_PDK:-sky130A}" -e KMP_IMAGE="$IMAGE" -e KMP_CACHE_DIR=/repo/out/cache \
  -v "$REPO:/repo" -w /repo "$IMAGE" --skip \
  bash -lc "$CMD" kmp "$@"
