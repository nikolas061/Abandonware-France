#!/usr/bin/env bash

set -euo pipefail

BASE_DIR=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PATCH_OUTPUT="$BASE_DIR/output/lolg95_locallng_sidecar_patch_probe"
SAFE_LOCALLNG_HD_960="$BASE_DIR/output/lolg95_locallng_probe_960_compact_first/sidecar/LOCALLNG_HD.MIX"
SAFE_LOCALLNG_HD_640="$BASE_DIR/output/lolg95_locallng_probe_640_literal_first/sidecar/LOCALLNG_HD.MIX"
DEFAULT_LOCALLNG_HD="$BASE_DIR/mod_mix_vqa_fullhd/LOCALLNG.MIX"

cd "$BASE_DIR"

if [ -n "${LOLG_HD_LOCALLNG_HD_MIX:-}" ]; then
	LOCALLNG_HD_SOURCE=$LOLG_HD_LOCALLNG_HD_MIX
elif [ -f "$SAFE_LOCALLNG_HD_960" ]; then
	LOCALLNG_HD_SOURCE=$SAFE_LOCALLNG_HD_960
elif [ -f "$SAFE_LOCALLNG_HD_640" ]; then
	LOCALLNG_HD_SOURCE=$SAFE_LOCALLNG_HD_640
else
	LOCALLNG_HD_SOURCE=$DEFAULT_LOCALLNG_HD
fi

python3 tools/lolg95_locallng_sidecar_patch_probe.py \
	-o "$PATCH_OUTPUT" \
	--hd-locallng "$LOCALLNG_HD_SOURCE"

export LOLG_HD_WINE_RUNTIME_ROOT="${LOLG_HD_WINE_RUNTIME_ROOT:-$BASE_DIR/output/lolg95_locallng_sidecar_wine_runtime}"
export LOLG_HD_WINE_HD_EXCLUDE="${LOLG_HD_WINE_HD_EXCLUDE:-LOCALLNG.MIX}"
export LOLG_HD_WINE_EXE_SOURCE="${LOLG_HD_WINE_EXE_SOURCE:-$PATCH_OUTPUT/LOLG95_LOCALLNG_SIDE.EXE}"
export LOLG_HD_WINE_EXTRA_MIX_DIR="${LOLG_HD_WINE_EXTRA_MIX_DIR:-$PATCH_OUTPUT/sidecar}"
echo "LOCALLNG_HD.MIX source: $LOCALLNG_HD_SOURCE"

exec "$BASE_DIR/RUN_HD_WINE.sh" "$@"
