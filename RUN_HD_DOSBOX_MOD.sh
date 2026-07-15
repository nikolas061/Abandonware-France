#!/bin/sh

set -eu

BASE_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ORIGINAL_GAME_DIR="$BASE_DIR/C/LOLG"
HD_MIX_DIR="$BASE_DIR/mod_mix_vqa_fullhd"
DOSBOX_MIX_OVERRIDE_DIR=${LOLG_HD_DOSBOX_MIX_OVERRIDE_DIR:-"$BASE_DIR/output/lolg_dosbox_mix_overrides"}
LOLG_HD_DOSBOX_USE_MIX_OVERRIDES=${LOLG_HD_DOSBOX_USE_MIX_OVERRIDES:-0}
DOSBOX_BIN="$BASE_DIR/dosbox"
DOSBOX_CONF_TEMPLATE="$BASE_DIR/lol2dos.conf"
LOCAL_LIB_DIR="$BASE_DIR/lib"
RUNTIME_ROOT="$BASE_DIR/output/lolg_dosbox_mod_mix_vqa_fullhd_runtime"
RUNTIME_C="$RUNTIME_ROOT/C"
RUNTIME_GAME_DIR="$RUNTIME_C/LOLG"
RUNTIME_CONF="$RUNTIME_ROOT/lol2dos_mod_mix_vqa_fullhd.conf"
CD_ISO="$BASE_DIR/CD/CD.iso"
VISUAL_PROFILE=${LOLG_HD_DOSBOX_PROFILE:-smooth}
LOLG_HD_USE_HD_MOVIES=${LOLG_HD_USE_HD_MOVIES:-0}
LOLG_HD_USE_HD_LARGE=${LOLG_HD_USE_HD_LARGE:-0}
LOLG_HD_DOSBOX_MIX_MODE=${LOLG_HD_DOSBOX_MIX_MODE:-all}
LOLG_HD_DOSBOX_HD_INCLUDE=${LOLG_HD_DOSBOX_HD_INCLUDE:-}
LOLG_HD_DOSBOX_HD_EXCLUDE=${LOLG_HD_DOSBOX_HD_EXCLUDE:-}
DOS_KNOWN_BAD_HD_MIX=LOCALLNG.MIX
DOS_SAFE_LARGE_LIMIT=2147483647
DOS_SMALL_MIX_LIMIT=134217728
DOS_MEDIUM_MIX_LIMIT=536870912
PREPARE_ONLY=0
STATUS_ONLY=0

usage() {
	cat <<'EOF'
Usage: ./RUN_HD_DOSBOX_MOD.sh [profil-image] [options]

Lance DOSBox avec les MIX HD de mod_mix_vqa_fullhd.

Profils image:
  smooth   Ratio correct, image douce (defaut)
  sharp    Ratio correct, image nette
  pixel    Ratio correct, pixels nets sans interpolation
  crt      Ratio correct, rendu CRT VGA 1080p
  stretch  Plein 1920x1080 etire

Options:
  --prepare-only  Prepare le runtime sans lancer DOSBox
  --status        Affiche le runtime et les liens MIX
  --mix-mode=MODE Mode MIX HD: none, small, medium, safe, all, list (defaut: all)
  --hd-only=A,B   En mode list, seuls ces MIX utilisent la version HD
  --hd-exclude=A,B Exclut ces MIX HD quel que soit le mode
  --use-mix-overrides Utilise les MIX reconstruits avant les MIX HD
  --mix-override-dir=DIR Dossier des MIX reconstruits, active aussi les overrides
  --use-hd-movies Utilise MOVIES.MIX HD experimental
  --use-hd-large  Utilise aussi les MIX HD > 2 Go
EOF
}

while [ "$#" -gt 0 ]; do
	case "$1" in
		help|-h|--help)
			usage
			exit 0
			;;
		sharp|smooth|pixel|crt|stretch)
			VISUAL_PROFILE=$1
			shift
			;;
		--profile=*)
			VISUAL_PROFILE=${1#--profile=}
			shift
			;;
		--visual=*)
			VISUAL_PROFILE=${1#--visual=}
			shift
			;;
		--prepare-only)
			PREPARE_ONLY=1
			shift
			;;
		--status)
			STATUS_ONLY=1
			shift
			;;
		--mix-mode=*)
			LOLG_HD_DOSBOX_MIX_MODE=${1#--mix-mode=}
			shift
			;;
		--hd-only=*)
			LOLG_HD_DOSBOX_MIX_MODE=list
			LOLG_HD_DOSBOX_HD_INCLUDE=${1#--hd-only=}
			shift
			;;
		--hd-exclude=*)
			LOLG_HD_DOSBOX_HD_EXCLUDE=${1#--hd-exclude=}
			shift
			;;
		--use-mix-overrides)
			LOLG_HD_DOSBOX_USE_MIX_OVERRIDES=1
			shift
			;;
		--mix-override-dir=*)
			LOLG_HD_DOSBOX_USE_MIX_OVERRIDES=1
			DOSBOX_MIX_OVERRIDE_DIR=${1#--mix-override-dir=}
			shift
			;;
		--use-hd-movies)
			LOLG_HD_USE_HD_MOVIES=1
			shift
			;;
		--use-original-movies)
			LOLG_HD_USE_HD_MOVIES=0
			shift
			;;
		--use-hd-large)
			LOLG_HD_USE_HD_LARGE=1
			shift
			;;
		--skip-hd-large)
			LOLG_HD_USE_HD_LARGE=0
			shift
			;;
		*)
			echo "Option DOSBox HD inconnue: $1" >&2
			usage >&2
			exit 2
			;;
	esac
done

case "$VISUAL_PROFILE" in
	sharp)
		DOSBOX_OUTPUT=opengl
		DOSBOX_ASPECT=auto
		DOSBOX_VIEWPORT=fit
		DOSBOX_SHADER=interpolation/sharp
		;;
	smooth)
		DOSBOX_OUTPUT=opengl
		DOSBOX_ASPECT=auto
		DOSBOX_VIEWPORT=fit
		DOSBOX_SHADER=none
		;;
	pixel)
		DOSBOX_OUTPUT=openglnb
		DOSBOX_ASPECT=auto
		DOSBOX_VIEWPORT=fit
		DOSBOX_SHADER=none
		;;
	crt)
		DOSBOX_OUTPUT=opengl
		DOSBOX_ASPECT=auto
		DOSBOX_VIEWPORT=fit
		DOSBOX_SHADER=crt/vga-1080p
		;;
	stretch)
		DOSBOX_OUTPUT=opengl
		DOSBOX_ASPECT=stretch
		DOSBOX_VIEWPORT=1920x1080
		DOSBOX_SHADER=none
		;;
	*)
		echo "Profil image inconnu: $VISUAL_PROFILE" >&2
		usage >&2
		exit 2
		;;
esac

case "$LOLG_HD_DOSBOX_MIX_MODE" in
	none|small|medium|safe|all|list)
		;;
	*)
		echo "Mode MIX HD inconnu: $LOLG_HD_DOSBOX_MIX_MODE" >&2
		usage >&2
		exit 2
		;;
esac

require_file() {
	if [ ! -f "$1" ]; then
		echo "Fichier introuvable: $1" >&2
		exit 1
	fi
}

require_dir() {
	if [ ! -d "$1" ]; then
		echo "Dossier introuvable: $1" >&2
		exit 1
	fi
}

csv_has_name() {
	csv=$1
	name=$2
	[ -n "$csv" ] || return 1
	padded_csv=$(printf ',%s,' "$csv" | tr '[:lower:]' '[:upper:]')
	padded_name=$(printf ',%s,' "$name" | tr '[:lower:]' '[:upper:]')
	case "$padded_csv" in
		*"$padded_name"*) return 0 ;;
		*) return 1 ;;
	esac
}

require_dir "$ORIGINAL_GAME_DIR"
require_dir "$HD_MIX_DIR"
require_file "$DOSBOX_CONF_TEMPLATE"
require_file "$CD_ISO"

if [ ! -x "$DOSBOX_BIN" ]; then
	echo "DOSBox introuvable ou non executable: $DOSBOX_BIN" >&2
	exit 1
fi

prepare_runtime() {
	mkdir -p "$RUNTIME_GAME_DIR"

	find "$ORIGINAL_GAME_DIR" -maxdepth 1 -type f ! -iname '*.MIX' -print |
	while IFS= read -r source_path; do
		name=${source_path##*/}
		target_path="$RUNTIME_GAME_DIR/$name"
		if [ ! -e "$target_path" ]; then
			cp -a "$source_path" "$target_path"
		fi
	done

	find "$ORIGINAL_GAME_DIR" -maxdepth 1 -type f -iname '*.MIX' -print |
	while IFS= read -r original_mix; do
		name=${original_mix##*/}
		hd_mix="$HD_MIX_DIR/$name"
		override_mix="$DOSBOX_MIX_OVERRIDE_DIR/$name"
		target_mix="$RUNTIME_GAME_DIR/$name"
		if [ "$LOLG_HD_DOSBOX_USE_MIX_OVERRIDES" -eq 1 ] && [ -f "$override_mix" ] && ! csv_has_name "$LOLG_HD_DOSBOX_HD_EXCLUDE" "$name"; then
			source_mix=$override_mix
		elif [ -f "$hd_mix" ]; then
			hd_size=$(wc -c < "$hd_mix")
			use_hd=0
			case "$LOLG_HD_DOSBOX_MIX_MODE" in
				none)
					use_hd=0
					;;
				small)
					[ "$hd_size" -le "$DOS_SMALL_MIX_LIMIT" ] && use_hd=1
					;;
				medium)
					[ "$hd_size" -le "$DOS_MEDIUM_MIX_LIMIT" ] && use_hd=1
					;;
				safe)
					[ "$hd_size" -le "$DOS_SAFE_LARGE_LIMIT" ] && use_hd=1
					;;
				all)
					use_hd=1
					;;
				list)
					csv_has_name "$LOLG_HD_DOSBOX_HD_INCLUDE" "$name" && use_hd=1
					;;
			esac
			csv_has_name "$DOS_KNOWN_BAD_HD_MIX" "$name" && use_hd=0
			csv_has_name "$LOLG_HD_DOSBOX_HD_EXCLUDE" "$name" && use_hd=0
			if [ "$LOLG_HD_DOSBOX_MIX_MODE" != "all" ]; then
				if [ "$name" = "MOVIES.MIX" ] && [ "$LOLG_HD_USE_HD_MOVIES" -eq 0 ]; then
					use_hd=0
				elif [ "$hd_size" -gt "$DOS_SAFE_LARGE_LIMIT" ] && [ "$LOLG_HD_USE_HD_LARGE" -eq 0 ]; then
					use_hd=0
				fi
			fi
			if [ "$use_hd" -eq 1 ]; then
				source_mix=$hd_mix
			else
				source_mix=$original_mix
			fi
		else
			source_mix=$original_mix
		fi
		rm -f "$target_mix"
		ln -s "$source_mix" "$target_mix"
	done

	for config in OPTIONS.INI OPT3DFX.INI OPTFIX.INI; do
		[ -f "$RUNTIME_GAME_DIR/$config" ] || continue
		perl -0pi -e '
			s/Video_Game_Resolution=Low/Video_Game_Resolution=High/g;
			s/Video_Movie_Resolution=Low/Video_Movie_Resolution=High/g;
			s/Video_Texture_Resolution=Low/Video_Texture_Resolution=High/g;
			s/Video_Texture_Cache=Small/Video_Texture_Cache=Large/g;
			s/Acceleration_VGA_Automap=Yes/Acceleration_VGA_Automap=No/g;
			s/Acceleration_VGA_Movies=Yes/Acceleration_VGA_Movies=No/g;
			s/Acceleration_Use4444=Yes/Acceleration_Use4444=No/g;
			s/Acceleration_Filtering=Off/Acceleration_Filtering=On/g;
			s/Acceleration_Toggle=Off/Acceleration_Toggle=On/g;
		' "$RUNTIME_GAME_DIR/$config"
	done

	cp "$DOSBOX_CONF_TEMPLATE" "$RUNTIME_CONF"

	DOSBOX_OUTPUT=$DOSBOX_OUTPUT \
	DOSBOX_ASPECT=$DOSBOX_ASPECT \
	DOSBOX_VIEWPORT=$DOSBOX_VIEWPORT \
	DOSBOX_SHADER=$DOSBOX_SHADER \
	RUNTIME_C=$RUNTIME_C \
	CD_ISO=$CD_ISO \
	perl -0pi -e '
		my $output = $ENV{DOSBOX_OUTPUT};
		my $aspect = $ENV{DOSBOX_ASPECT};
		my $viewport = $ENV{DOSBOX_VIEWPORT};
		my $shader = $ENV{DOSBOX_SHADER};
		my $runtime_c = $ENV{RUNTIME_C};
		my $cd_iso = $ENV{CD_ISO};
		s/^fullscreen\s*=.*$/fullscreen = true/m;
		s/^fullresolution\s*=.*$/fullresolution = 1920x1080/m;
		s/^windowresolution\s*=.*$/windowresolution = 1920x1080/m;
		if (/^viewport_resolution\s*=/m) {
			s/^viewport_resolution\s*=.*$/viewport_resolution = $viewport/m;
		} else {
			s/^(windowresolution\s*=.*)$/\1\nviewport_resolution = $viewport/m;
		}
		s/^output\s*=.*$/output = $output/m;
		s/^cycles\s*=.*$/cycles = max 85%/m;
		s/^aspect\s*=.*$/aspect = $aspect/m;
		if (/^viewport\s*=/m) {
			s/^viewport\s*=.*$/viewport = $viewport/m;
		} else {
			s/^(aspect\s*=.*)$/\1\nviewport = $viewport/m;
		}
		s#^glshader\s*=.*$#glshader = $shader#m;
		s#^mount C .*$#mount C "$runtime_c"#m;
		s#^imgmount D .*$#imgmount D "$cd_iso" -t iso#m;
		s/^pause\r?$/rem pause/m;
		s/^cd\s+(?:lolg|\\)\r?$/cd lolg/mi;
		s/^lolg -CD C:\\(?:LOLG\\?)?.*$/lolg -CD C:\\LOLG\\ -LOWMEM/mi;
		s/^exit\r?$/rem exit/m;
	' "$RUNTIME_CONF"
}

print_status() {
	hd_links=$(find "$RUNTIME_GAME_DIR" -maxdepth 1 -type l -iname '*.MIX' -lname "$HD_MIX_DIR/*" 2>/dev/null | wc -l)
	override_links=$(find "$RUNTIME_GAME_DIR" -maxdepth 1 -type l -iname '*.MIX' -lname "$DOSBOX_MIX_OVERRIDE_DIR/*" 2>/dev/null | wc -l)
	original_links=$(find "$RUNTIME_GAME_DIR" -maxdepth 1 -type l -iname '*.MIX' ! -lname "$HD_MIX_DIR/*" ! -lname "$DOSBOX_MIX_OVERRIDE_DIR/*" 2>/dev/null | wc -l)
	echo "Runtime DOSBox HD: $RUNTIME_ROOT"
	echo "Config DOSBox: $RUNTIME_CONF"
	echo "Profil image DOSBox: $VISUAL_PROFILE ($DOSBOX_OUTPUT, $DOSBOX_ASPECT, $DOSBOX_VIEWPORT, $DOSBOX_SHADER)"
	echo "Mode MIX HD DOSBox: $LOLG_HD_DOSBOX_MIX_MODE"
	echo "Dossier MIX overrides: $DOSBOX_MIX_OVERRIDE_DIR"
	echo "Overrides MIX actifs: $LOLG_HD_DOSBOX_USE_MIX_OVERRIDES"
	echo "MIX HD exclus DOS connus: $DOS_KNOWN_BAD_HD_MIX"
	echo "Option MOVIES.MIX HD hors mode all: $LOLG_HD_USE_HD_MOVIES"
	echo "Option MIX HD > 2 Go hors mode all: $LOLG_HD_USE_HD_LARGE"
	if [ -n "$LOLG_HD_DOSBOX_HD_INCLUDE" ]; then
		echo "HD include: $LOLG_HD_DOSBOX_HD_INCLUDE"
	fi
	if [ -n "$LOLG_HD_DOSBOX_HD_EXCLUDE" ]; then
		echo "HD exclude: $LOLG_HD_DOSBOX_HD_EXCLUDE"
	fi
	echo "MIX HD mod_mix_vqa_fullhd: $hd_links"
	echo "MIX reconstruits override: $override_links"
	echo "MIX originaux fallback: $original_links"
	if [ -L "$RUNTIME_GAME_DIR/LOCALLNG.MIX" ]; then
		echo "LOCALLNG.MIX -> $(readlink "$RUNTIME_GAME_DIR/LOCALLNG.MIX")"
	fi
	if [ -L "$RUNTIME_GAME_DIR/MOVIES.MIX" ]; then
		echo "MOVIES.MIX -> $(readlink "$RUNTIME_GAME_DIR/MOVIES.MIX")"
	fi
	if [ -L "$RUNTIME_GAME_DIR/L20_BBI.MIX" ]; then
		echo "L20_BBI.MIX -> $(readlink "$RUNTIME_GAME_DIR/L20_BBI.MIX")"
	fi
}

prepare_runtime
print_status

if [ "$STATUS_ONLY" -eq 1 ] || [ "$PREPARE_ONLY" -eq 1 ]; then
	exit 0
fi

if [ -d "$LOCAL_LIB_DIR" ]; then
	LD_LIBRARY_PATH="$LOCAL_LIB_DIR${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
	export LD_LIBRARY_PATH
fi

cd "$BASE_DIR"
exec "$DOSBOX_BIN" -conf "$RUNTIME_CONF"
