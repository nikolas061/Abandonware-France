#!/usr/bin/env bash

set -euo pipefail

BASE_DIR=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
OUTPUT_RESOLUTION="${LOLG_HD_GAMESCOPE_RESOLUTION:-${LOLG_HD_RESOLUTION:-1920x1080}}"
GAME_RESOLUTION="${LOLG_HD_GAMESCOPE_GAME_RESOLUTION:-640x400}"
SCALER="${LOLG_HD_GAMESCOPE_SCALER:-fsr}"
FPS_LIMIT="${LOLG_HD_GAMESCOPE_FPS:-60}"
FULLSCREEN=0
BORDERLESS=0
DRY_RUN=0
GAMESCOPE_BIN="${GAMESCOPE:-}"

usage() {
	cat <<'EOF'
Usage: ./RUN_HD_WINE_GAMESCOPE.sh [options]

Lance LOLG95 via Wine sans dgVoodoo, puis laisse gamescope agrandir l'image.
Ce mode garde LOCALLNG.MIX/MOVIES.MIX originaux et utilise les autres MIX HD.

Options:
  --resolution WIDTHxHEIGHT       Taille de la fenetre gamescope (defaut: 1920x1080)
  --game-resolution WIDTHxHEIGHT  Resolution vue par le jeu (defaut: 640x400)
  --scaler fsr|nis|integer|stretch|none
                                  Filtre de scaling gamescope (defaut: fsr)
  --fps N                         Limite FPS gamescope (defaut: 60; none pour desactiver)
  --fullscreen                    Fenetre gamescope plein ecran
  --borderless                    Fenetre gamescope sans bordure
  --movable                       Fenetre normale deplacable (defaut)
  --dry-run                       Affiche la commande sans lancer
  -h, --help                      Affiche cette aide

Exemples:
  ./RUN_HD_WINE_GAMESCOPE.sh
  ./RUN_HD_WINE_GAMESCOPE.sh --resolution 1280x1024 --scaler nis
  ./RUN_HD_WINE_GAMESCOPE.sh --resolution 1920x1080 --scaler integer
EOF
}

validate_resolution() {
	value=$1
	label=$2
	case "$value" in
		*[!0-9x]*|x*|*x|*x*x*)
			echo "$label invalide: $value (format attendu: 1920x1080)" >&2
			exit 2
			;;
	esac
}

while [ "$#" -gt 0 ]; do
	case "$1" in
		--resolution)
			[ "$#" -ge 2 ] || { echo "--resolution demande une valeur" >&2; exit 2; }
			OUTPUT_RESOLUTION=$2
			shift 2
			;;
		--resolution=*)
			OUTPUT_RESOLUTION=${1#--resolution=}
			shift
			;;
		--game-resolution)
			[ "$#" -ge 2 ] || { echo "--game-resolution demande une valeur" >&2; exit 2; }
			GAME_RESOLUTION=$2
			shift 2
			;;
		--game-resolution=*)
			GAME_RESOLUTION=${1#--game-resolution=}
			shift
			;;
		--scaler)
			[ "$#" -ge 2 ] || { echo "--scaler demande une valeur" >&2; exit 2; }
			SCALER=$2
			shift 2
			;;
		--scaler=*)
			SCALER=${1#--scaler=}
			shift
			;;
		--fps)
			[ "$#" -ge 2 ] || { echo "--fps demande une valeur" >&2; exit 2; }
			FPS_LIMIT=$2
			shift 2
			;;
		--fps=*)
			FPS_LIMIT=${1#--fps=}
			shift
			;;
		--fullscreen)
			FULLSCREEN=1
			BORDERLESS=0
			shift
			;;
		--borderless)
			BORDERLESS=1
			FULLSCREEN=0
			shift
			;;
		--movable)
			FULLSCREEN=0
			BORDERLESS=0
			shift
			;;
		--dry-run)
			DRY_RUN=1
			shift
			;;
		-h|--help)
			usage
			exit 0
			;;
		*)
			echo "Option inconnue: $1" >&2
			usage >&2
			exit 2
			;;
	esac
done

validate_resolution "$OUTPUT_RESOLUTION" "Resolution gamescope"
validate_resolution "$GAME_RESOLUTION" "Resolution jeu"

case "$SCALER" in
	fsr|nis|integer|stretch|none|off)
		;;
	*)
		echo "Scaler invalide: $SCALER (fsr, nis, integer, stretch ou none attendu)" >&2
		exit 2
		;;
esac

case "$FPS_LIMIT" in
	none|off|0)
		FPS_LIMIT=none
		;;
	''|*[!0-9]*)
		echo "FPS invalide: $FPS_LIMIT" >&2
		exit 2
		;;
esac

if [ -z "$GAMESCOPE_BIN" ]; then
	if command -v gamescope >/dev/null 2>&1; then
		GAMESCOPE_BIN=$(command -v gamescope)
	elif [ -x /usr/games/gamescope ]; then
		GAMESCOPE_BIN=/usr/games/gamescope
	else
		GAMESCOPE_BIN=gamescope
	fi
fi

if [ "$DRY_RUN" -ne 1 ] && [ "$GAMESCOPE_BIN" = gamescope ] && ! command -v gamescope >/dev/null 2>&1; then
	echo "gamescope introuvable." >&2
	echo "Installe-le puis relance: sudo apt install -t trixie-backports gamescope" >&2
	exit 127
fi

if [ "$DRY_RUN" -ne 1 ] && [ -n "${DISPLAY:-}" ] && command -v xdpyinfo >/dev/null 2>&1 && ! xdpyinfo >/dev/null 2>&1; then
	echo "Affichage X11 non accessible: DISPLAY=$DISPLAY" >&2
	echo "Relance depuis un terminal graphique de ta session utilisateur." >&2
	exit 126
fi

if [ "$DRY_RUN" -ne 1 ] && [ -z "${DISPLAY:-}" ] && [ -z "${WAYLAND_DISPLAY:-}" ]; then
	echo "Aucun affichage graphique trouve: DISPLAY et WAYLAND_DISPLAY sont vides." >&2
	echo "Relance depuis un terminal graphique de ta session utilisateur." >&2
	exit 126
fi

out_width=${OUTPUT_RESOLUTION%x*}
out_height=${OUTPUT_RESOLUTION#*x}
game_width=${GAME_RESOLUTION%x*}
game_height=${GAME_RESOLUTION#*x}

GAMESCOPE_ARGS=(
	-w "$game_width"
	-h "$game_height"
	-W "$out_width"
	-H "$out_height"
)

if [ "$FPS_LIMIT" != none ]; then
	GAMESCOPE_ARGS+=(-r "$FPS_LIMIT")
fi

case "$SCALER" in
	fsr)
		GAMESCOPE_ARGS+=(-F fsr)
		;;
	nis)
		GAMESCOPE_ARGS+=(-F nis)
		;;
	integer)
		GAMESCOPE_ARGS+=(-S integer)
		;;
	stretch)
		GAMESCOPE_ARGS+=(-S stretch)
		;;
esac

if [ "$FULLSCREEN" -eq 1 ]; then
	GAMESCOPE_ARGS+=(-f)
elif [ "$BORDERLESS" -eq 1 ]; then
	GAMESCOPE_ARGS+=(-b)
fi

RUN_ARGS=(
	"$BASE_DIR/RUN_HD_WINE.sh"
	--resolution "$GAME_RESOLUTION"
	--no-dgvoodoo
	--no-local-ddraw
	--use-original-movies
	--hd-exclude=LOCALLNG.MIX,MOVIES.MIX
	--no-auto-resize
	--no-resize-game-window
)

COMMAND=("$GAMESCOPE_BIN" "${GAMESCOPE_ARGS[@]}" -- "${RUN_ARGS[@]}")

echo "Mode alternatif: gamescope sans dgVoodoo"
echo "Stage Wine: output/lolg95_gamescope_wine_runtime/WESTWOOD/LOLG"
echo "Wine prefix: output/lolg95_gamescope_wine_prefix"
echo "Resolution fenetre gamescope: $OUTPUT_RESOLUTION"
echo "Resolution vue par le jeu: $GAME_RESOLUTION"
echo "Scaler gamescope: $SCALER"
echo "dgVoodoo: desactive"
echo "DDraw local: desactive"
echo "MIX HD Wine: actifs sauf LOCALLNG.MIX/MOVIES.MIX"
if [ "$FULLSCREEN" -eq 1 ]; then
	echo "Fenetre gamescope: plein ecran"
elif [ "$BORDERLESS" -eq 1 ]; then
	echo "Fenetre gamescope: sans bordure"
else
	echo "Fenetre gamescope: normale deplacable"
fi

if [ "$DRY_RUN" -eq 1 ]; then
	printf 'Commande:'
	printf ' %q' "${COMMAND[@]}"
	printf '\n'
	exit 0
fi

export LOLG_HD_RESOLUTION="$GAME_RESOLUTION"
export LOLG_HD_ALLOW_UNSUPPORTED_RESOLUTION="${LOLG_HD_ALLOW_UNSUPPORTED_RESOLUTION:-1}"
export LOLG_HD_USE_DGVOODOO=0
export LOLG_HD_USE_LOCAL_DDRAW=0
export LOLG_HD_WINE_USE_HD_MIX=1
export LOLG_HD_WINE_HD_EXCLUDE=LOCALLNG.MIX,MOVIES.MIX
export LOLG_HD_USE_ORIGINAL_MOVIES=1
export LOLG_HD_LOCK_WINDOW_POSITION=0
export LOLG_HD_WINE_RENDERER="${LOLG_HD_WINE_RENDERER:-gdi}"
export LOLG_HD_WINE_DIRECTDRAW_RENDERER="${LOLG_HD_WINE_DIRECTDRAW_RENDERER:-gdi}"
export LOLG_HD_WINE_DLL_OVERRIDES="${LOLG_HD_WINE_DLL_OVERRIDES:-ddraw,d3dimm,d3d8=b}"
export LOLG_HD_WINE_RUNTIME_ROOT="${LOLG_HD_WINE_RUNTIME_ROOT:-$BASE_DIR/output/lolg95_gamescope_wine_runtime}"
export WINEPREFIX="${WINEPREFIX:-$BASE_DIR/output/lolg95_gamescope_wine_prefix}"

exec "${COMMAND[@]}"
