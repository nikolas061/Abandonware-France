#!/usr/bin/env sh

set -eu

BASE_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$BASE_DIR"

echo "Reparation/preparation du runtime Wine HD..."

./STOP_HD_WINE.sh
./RUN_HD_WINE.sh --prepare-only "$@"
./STOP_HD_WINE.sh
./CHECK_HD.sh
./PACK_HD_RELEASE.sh --skip-check
python3 tools/lolg_hd_status.py
