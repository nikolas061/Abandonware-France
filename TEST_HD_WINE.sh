#!/usr/bin/env sh

set -eu

BASE_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$BASE_DIR"

exec python3 tools/lolg_hd_wine_smoke_test.py "$@"
