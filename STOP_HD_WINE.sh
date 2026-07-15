#!/usr/bin/env sh

set -eu

BASE_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
DEFAULT_WINEPREFIX="$BASE_DIR/output/lolg95_fullhd_wine_prefix"
DGVOODOO_WINEPREFIX="$BASE_DIR/output/lolg95_dgvoodoo_wine_prefix"
DGVOODOO_HDMIX_WINEPREFIX="$BASE_DIR/output/lolg95_dgvoodoo_hdmix_wine_prefix"
DGVOODOO_WIN10_WINEPREFIX="$BASE_DIR/output/lolg95_dgvoodoo_win10_wine_prefix"
DGVOODOO_WIN10_MOVIES_SAFE_WINEPREFIX="$BASE_DIR/output/lolg95_dgvoodoo_win10_safevqa_movies_safe_wine_prefix"
NGLIDE_WIN10_WINEPREFIX="$BASE_DIR/output/lolg95_nglide_win10_wine_prefix"
VQA_CONTRACT_WINEPREFIX="$BASE_DIR/output/lolg95_vqa_contract_wine_prefix"
if [ -n "${WINEPREFIX:-}" ]; then
	WINEPREFIXES=$WINEPREFIX
else
	WINEPREFIXES="$DEFAULT_WINEPREFIX $DGVOODOO_WINEPREFIX $DGVOODOO_HDMIX_WINEPREFIX $DGVOODOO_WIN10_WINEPREFIX $DGVOODOO_WIN10_MOVIES_SAFE_WINEPREFIX $NGLIDE_WIN10_WINEPREFIX $VQA_CONTRACT_WINEPREFIX"
fi
WINE_PROCESSES_PATTERN="$BASE_DIR/RUN_HD_WINE.sh|$BASE_DIR/output/lolg95_fullhd_wine_runtime|$BASE_DIR/output/lolg95_locallng_sidecar_wine_runtime|$BASE_DIR/output/lolg95_dgvoodoo_win10_safevqa_movies_safe_runtime|D:\\\\WESTWOOD\\\\LOLG"

echo "Arret du runtime Wine HD du projet..."
echo "WINEPREFIX: $WINEPREFIXES"

if command -v pkill >/dev/null 2>&1; then
	pkill -TERM -f "$WINE_PROCESSES_PATTERN" 2>/dev/null || true
	sleep 1
	pkill -KILL -f "$WINE_PROCESSES_PATTERN" 2>/dev/null || true
fi

if command -v wineserver >/dev/null 2>&1; then
	for wine_prefix in $WINEPREFIXES; do
		WINEPREFIX=$wine_prefix wineserver -k >/dev/null 2>&1 || true
	done
fi

remaining=""
if command -v pgrep >/dev/null 2>&1; then
	remaining=$(pgrep -af "$WINE_PROCESSES_PATTERN" 2>/dev/null || true)
fi

if [ -n "$remaining" ]; then
	echo "Processus encore visibles:"
	printf '%s\n' "$remaining"
	exit 1
fi

echo "Runtime Wine HD arrete."
