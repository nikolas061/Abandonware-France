#!/usr/bin/env bash

set -euo pipefail

BASE_DIR=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cd "$BASE_DIR"

INDEX_DIR="${LOLG_HD_EXTERNAL_SIDECAR_INDEX_DIR:-$BASE_DIR/output/vqa_external_sidecar_index}"
MANIFEST="$INDEX_DIR/manifest.json"
CACHE_DIR="${LOLG_HD_EXTERNAL_SIDECAR_CACHE_DIR:-$BASE_DIR/output/vqa_external_sidecar_cache}"
RUNTIME_DIR="${LOLG_HD_EXTERNAL_SIDECAR_RUNTIME_DIR:-$BASE_DIR/output/vqa_external_sidecar_runtime}"
REBUILD="${LOLG_HD_EXTERNAL_SIDECAR_REBUILD:-0}"
SCAN_CHUNKS="${LOLG_HD_EXTERNAL_SIDECAR_SCAN_CHUNKS:-0}"

if [ "$REBUILD" = "1" ] || [ ! -f "$MANIFEST" ]; then
	echo "Preparation de l'index sidecar VQA externe..."
	if [ "$SCAN_CHUNKS" = "1" ]; then
		python3 tools/lolg_vqa_external_sidecar_index.py \
			--hd-root mod_mix_vqa_fullhd \
			--output "$INDEX_DIR" \
			--scan-chunks
	else
		python3 tools/lolg_vqa_external_sidecar_index.py \
			--hd-root mod_mix_vqa_fullhd \
			--output "$INDEX_DIR"
	fi
fi

if [ ! -f "$MANIFEST" ]; then
	echo "Manifest sidecar externe introuvable: $MANIFEST" >&2
	exit 1
fi

mkdir -p "$CACHE_DIR" "$RUNTIME_DIR"

echo "Sidecar VQA externe: $MANIFEST"
echo "Cache sidecar VQA: $CACHE_DIR"
echo "Runtime sidecar VQA: $RUNTIME_DIR"
echo "Requete sidecar: $RUNTIME_DIR/request.json"
echo "Lecteur web sidecar: ./LOLG_HD.sh sidecar-web"
echo "Status sidecar: ./LOLG_HD.sh sidecar-status"
echo "Audit session sidecar: ./LOLG_HD.sh sidecar-audit --events 50"
echo "Bridge trace sidecar: ./LOLG_HD.sh sidecar-trace-bridge"
echo "Bridge strace sidecar: ./LOLG_HD.sh sidecar-strace-bridge"
echo "Mode live sidecar: ./LOLG_HD.sh sidecar-live"
echo "Mode live strace sidecar: ./LOLG_HD.sh sidecar-live --trace-source strace"
echo "Mode live strace toutes frames: ./LOLG_HD.sh sidecar-live --trace-source strace --max-frames 0"
echo "Alias live strace: ./LOLG_HD.sh sidecar-live-strace"
echo "Alias live strace toutes frames: ./LOLG_HD.sh sidecar-live-strace-all"
echo "Alias live strace avec player: ./LOLG_HD.sh sidecar-live-strace-player"
echo "Alias live strace toutes frames avec player: ./LOLG_HD.sh sidecar-live-strace-all-player"
echo "Alias live strace large avec player: ./LOLG_HD.sh sidecar-live-strace-wide-player"
echo "Alias live strace large toutes frames avec player: ./LOLG_HD.sh sidecar-live-strace-wide-all-player"
echo "Alias live strace large toutes frames avec HUD: ./LOLG_HD.sh sidecar-live-strace-wide-all-player --player-hud"
echo "Alias HUD court: ./LOLG_HD.sh sidecar-live-strace-wide-hud"
echo "Alias HUD court toutes frames: ./LOLG_HD.sh sidecar-live-strace-wide-all-hud"
echo "Player VQA HD: http://127.0.0.1:8765/?mode=player"
echo "Player VQA HD HUD: http://127.0.0.1:8765/?mode=player&hud=1"
echo "Mode moteur: safevqa stable; les VQA HD restent externes au moteur."

export LOLG_HD_EXTERNAL_SIDECAR_MANIFEST="$MANIFEST"
export LOLG_HD_EXTERNAL_SIDECAR_CACHE_DIR="$CACHE_DIR"
export LOLG_HD_EXTERNAL_SIDECAR_RUNTIME_DIR="$RUNTIME_DIR"
export LOLG_HD_EXTERNAL_SIDECAR_MODE="${LOLG_HD_EXTERNAL_SIDECAR_MODE:-manifest}"
export LOLG_HD_RESOLUTION="${LOLG_HD_RESOLUTION:-1920x1080}"

exec ./LOLG_HD.sh wine-dgvoodoo-win10-safevqa "$@"
