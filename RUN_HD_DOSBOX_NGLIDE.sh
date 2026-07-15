#!/bin/sh

set -eu

BASE_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ORIGINAL_GAME_DIR="$BASE_DIR/C/LOLG"
HD_MIX_DIR="$BASE_DIR/mod_mix_vqa_fullhd"
DOSBOX_MIX_OVERRIDE_DIR=${LOLG_HD_DOSBOX_MIX_OVERRIDE_DIR:-"$BASE_DIR/output/lolg_dosbox_mix_overrides"}
DOSBOX_BIN="$BASE_DIR/dosbox"
DOSBOX_CONF_TEMPLATE="$BASE_DIR/lol2dos.conf"
LOCAL_LIB_DIR="$BASE_DIR/lib"
RUNTIME_ROOT_EXPLICIT=0
RUNTIME_ROOT=
if [ "${LOLG_HD_DOSBOX_NGLIDE_RUNTIME_ROOT+x}" = x ]; then
	RUNTIME_ROOT_EXPLICIT=1
	RUNTIME_ROOT=$LOLG_HD_DOSBOX_NGLIDE_RUNTIME_ROOT
fi
RUNTIME_C=
RUNTIME_GAME_DIR=
RUNTIME_CONF=
CD_ISO="$BASE_DIR/CD/CD.iso"
RESOLUTION="${LOLG_HD_DOSBOX_NGLIDE_RESOLUTION:-1920x1080}"
VISUAL_PROFILE=${LOLG_HD_DOSBOX_PROFILE:-stretch}
LOLG_HD_DOSBOX_NGLIDE_USE_HDMIX=${LOLG_HD_DOSBOX_NGLIDE_USE_HDMIX:-0}
LOLG_HD_DOSBOX_USE_MIX_OVERRIDES=${LOLG_HD_DOSBOX_USE_MIX_OVERRIDES:-0}
LOLG_HD_DOSBOX_MIX_MODE=${LOLG_HD_DOSBOX_MIX_MODE:-}
LOLG_HD_DOSBOX_HD_INCLUDE=${LOLG_HD_DOSBOX_HD_INCLUDE:-}
LOLG_HD_DOSBOX_HD_EXCLUDE=${LOLG_HD_DOSBOX_HD_EXCLUDE:-}
LOLG_HD_USE_HD_MOVIES=${LOLG_HD_USE_HD_MOVIES:-0}
LOLG_HD_USE_HD_LARGE=${LOLG_HD_USE_HD_LARGE:-0}
DOS_ALWAYS_EXCLUDED_HD_MIX=LOCALLNG.MIX,MOVIES.MIX
DOS_SAFE_EXCLUDED_HD_MIX="L1_DCI.MIX,L3_DHI.MIX"
DOS_SAFE_LARGE_LIMIT=2147483647
DOS_SMALL_MIX_LIMIT=134217728
DOS_MEDIUM_MIX_LIMIT=536870912
PREPARE_ONLY=0
STATUS_ONLY=0

usage() {
	cat <<'EOF'
Usage: ./RUN_HD_DOSBOX_NGLIDE.sh [profil-image] [options]

Lance Lands of Lore II DOS en 1920x1080 avec le profil 3dfx du jeu.
Le rendu Glide utilise l'emulation Voodoo integree de DOSBox-Staging.

Profils image:
  smooth   Ratio correct, image douce
  sharp    Ratio correct, image nette
  pixel    Ratio correct, pixels nets sans interpolation
  crt      Ratio correct, rendu CRT VGA 1080p
  stretch  Plein 1920x1080 etire (defaut)

Options:
  --resolution WIDTHxHEIGHT  Resolution DOSBox plein ecran/fenetre (defaut: 1920x1080)
  --prepare-only             Prepare le runtime sans lancer DOSBox
  --status                   Affiche le runtime et la config
  --use-hdmix                Utilise mod_mix_vqa_fullhd pour les MIX HD
  --mix-mode=MODE            Mode MIX HD: none, small, medium, safe, all, list (defaut HDMIX: safe)
  --hd-only=A,B              En mode list, seuls ces MIX utilisent la version HD
  --hd-exclude=A,B           Exclut ces MIX HD quel que soit le mode
  --use-mix-overrides        Utilise les MIX reconstruits avant les MIX HD
  --mix-override-dir=DIR     Dossier des MIX reconstruits, active aussi les overrides
  --use-hd-movies            Utilise MOVIES.MIX HD hors mode all
  --use-hd-large             Utilise aussi les MIX HD > 2 Go hors mode all
  -h, --help                 Affiche cette aide
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
		--resolution)
			[ "$#" -ge 2 ] || { echo "--resolution demande une valeur" >&2; exit 2; }
			RESOLUTION=$2
			shift 2
			;;
		--resolution=*)
			RESOLUTION=${1#--resolution=}
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
		--use-hdmix|--use-hd-mix)
			LOLG_HD_DOSBOX_NGLIDE_USE_HDMIX=1
			shift
			;;
		--no-hdmix|--no-hd-mix)
			LOLG_HD_DOSBOX_NGLIDE_USE_HDMIX=0
			shift
			;;
		--mix-mode=*)
			LOLG_HD_DOSBOX_NGLIDE_USE_HDMIX=1
			LOLG_HD_DOSBOX_MIX_MODE=${1#--mix-mode=}
			shift
			;;
		--hd-only=*)
			LOLG_HD_DOSBOX_NGLIDE_USE_HDMIX=1
			LOLG_HD_DOSBOX_MIX_MODE=list
			LOLG_HD_DOSBOX_HD_INCLUDE=${1#--hd-only=}
			shift
			;;
		--hd-exclude=*)
			LOLG_HD_DOSBOX_NGLIDE_USE_HDMIX=1
			LOLG_HD_DOSBOX_HD_EXCLUDE=${1#--hd-exclude=}
			shift
			;;
		--use-mix-overrides)
			LOLG_HD_DOSBOX_NGLIDE_USE_HDMIX=1
			LOLG_HD_DOSBOX_USE_MIX_OVERRIDES=1
			shift
			;;
		--mix-override-dir=*)
			LOLG_HD_DOSBOX_NGLIDE_USE_HDMIX=1
			LOLG_HD_DOSBOX_USE_MIX_OVERRIDES=1
			DOSBOX_MIX_OVERRIDE_DIR=${1#--mix-override-dir=}
			shift
			;;
		--use-hd-movies)
			LOLG_HD_DOSBOX_NGLIDE_USE_HDMIX=1
			LOLG_HD_USE_HD_MOVIES=1
			shift
			;;
		--use-original-movies)
			LOLG_HD_USE_HD_MOVIES=0
			shift
			;;
		--use-hd-large)
			LOLG_HD_DOSBOX_NGLIDE_USE_HDMIX=1
			LOLG_HD_USE_HD_LARGE=1
			shift
			;;
		--skip-hd-large)
			LOLG_HD_USE_HD_LARGE=0
			shift
			;;
		*)
			echo "Option DOSBox nGlide inconnue: $1" >&2
			usage >&2
			exit 2
			;;
	esac
done

case "$RESOLUTION" in
	*[!0-9x]*|x*|*x|*x*x*)
		echo "Resolution invalide: $RESOLUTION (format attendu: 1920x1080)" >&2
		exit 2
		;;
esac

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
		DOSBOX_VIEWPORT=$RESOLUTION
		DOSBOX_SHADER=none
		;;
	*)
		echo "Profil image inconnu: $VISUAL_PROFILE" >&2
		usage >&2
		exit 2
		;;
esac

case "$LOLG_HD_DOSBOX_NGLIDE_USE_HDMIX" in
	0|1)
		;;
	*)
		echo "LOLG_HD_DOSBOX_NGLIDE_USE_HDMIX doit valoir 0 ou 1" >&2
		exit 2
		;;
esac

if [ -z "$LOLG_HD_DOSBOX_MIX_MODE" ]; then
	if [ "$LOLG_HD_DOSBOX_NGLIDE_USE_HDMIX" -eq 1 ]; then
		LOLG_HD_DOSBOX_MIX_MODE=safe
	else
		LOLG_HD_DOSBOX_MIX_MODE=all
	fi
fi

case "$LOLG_HD_DOSBOX_MIX_MODE" in
	none|small|medium|safe|all|list)
		;;
	*)
		echo "Mode MIX HD inconnu: $LOLG_HD_DOSBOX_MIX_MODE" >&2
		usage >&2
		exit 2
		;;
esac

set_runtime_paths() {
	if [ "$RUNTIME_ROOT_EXPLICIT" -eq 0 ]; then
		if [ "$LOLG_HD_DOSBOX_NGLIDE_USE_HDMIX" -eq 1 ]; then
			RUNTIME_ROOT="$BASE_DIR/output/lolg_dosbox_nglide_hdmix_1920_runtime"
		else
			RUNTIME_ROOT="$BASE_DIR/output/lolg_dosbox_nglide_1920_runtime"
		fi
	fi
	RUNTIME_C="$RUNTIME_ROOT/C"
	RUNTIME_GAME_DIR="$RUNTIME_C/LOLG"
	if [ "$LOLG_HD_DOSBOX_NGLIDE_USE_HDMIX" -eq 1 ]; then
		RUNTIME_CONF="$RUNTIME_ROOT/lol2dos_nglide_hdmix_1920.conf"
	else
		RUNTIME_CONF="$RUNTIME_ROOT/lol2dos_nglide_1920.conf"
	fi
}

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

link_or_copy_file() {
	src=$1
	dst=$2
	mode=$3
	mkdir -p "$(dirname "$dst")"
	if [ -L "$dst" ]; then
		rm -f "$dst"
	fi
	if [ -e "$dst" ] && [ ! -L "$dst" ]; then
		case "$mode" in
			copy) cp -f "$src" "$dst" ;;
			link) rm -f "$dst"; ln -s "$src" "$dst" ;;
		esac
		return
	fi
	case "$mode" in
		copy) cp -f "$src" "$dst" ;;
		link) ln -s "$src" "$dst" ;;
	esac
}

replace_or_append_setting() {
	file=$1
	key=$2
	value=$3
	LOLG_HD_CONF_KEY=$key LOLG_HD_CONF_VALUE=$value perl -0pi -e '
		my $key = $ENV{LOLG_HD_CONF_KEY};
		my $value = $ENV{LOLG_HD_CONF_VALUE};
		if (!s/^\Q$key\E\s*=.*$/$key = $value/gmi) {
			$_ .= "\n$key = $value\n";
		}
	' "$file"
}

ensure_section() {
	file=$1
	section=$2
	if ! grep -qi "^\[$section\]" "$file"; then
		printf '\n[%s]\n' "$section" >> "$file"
	fi
}

set_runtime_paths
require_dir "$ORIGINAL_GAME_DIR"
if [ "$LOLG_HD_DOSBOX_NGLIDE_USE_HDMIX" -eq 1 ]; then
	require_dir "$HD_MIX_DIR"
fi
require_file "$DOSBOX_CONF_TEMPLATE"
require_file "$CD_ISO"

if [ ! -x "$DOSBOX_BIN" ]; then
	echo "DOSBox introuvable ou non executable: $DOSBOX_BIN" >&2
	exit 1
fi

apply_hd_mix_links() {
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
			csv_has_name "$DOS_ALWAYS_EXCLUDED_HD_MIX" "$name" && use_hd=0
			if [ "$LOLG_HD_DOSBOX_MIX_MODE" != "all" ]; then
				csv_has_name "$DOS_SAFE_EXCLUDED_HD_MIX" "$name" && use_hd=0
			fi
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
}

prepare_runtime() {
	mkdir -p "$RUNTIME_GAME_DIR"

	find "$ORIGINAL_GAME_DIR" -mindepth 1 -maxdepth 1 | while IFS= read -r src; do
		name=${src##*/}
		dst="$RUNTIME_GAME_DIR/$name"
		if [ -d "$src" ]; then
			link_or_copy_file "$src" "$dst" link
			continue
		fi
		case "$name" in
			OPTIONS.INI|OPT3DFX.INI|OPTFIX.INI|LOLSETUP.INI)
				link_or_copy_file "$src" "$dst" copy
				;;
			*)
				link_or_copy_file "$src" "$dst" link
				;;
		esac
	done

	if [ "$LOLG_HD_DOSBOX_NGLIDE_USE_HDMIX" -eq 1 ]; then
		apply_hd_mix_links
	fi

	cp -f "$ORIGINAL_GAME_DIR/OPT3DFX.INI" "$RUNTIME_GAME_DIR/OPTIONS.INI"
	for config in "$RUNTIME_GAME_DIR/OPTIONS.INI" "$RUNTIME_GAME_DIR/OPT3DFX.INI" "$RUNTIME_GAME_DIR/OPTFIX.INI"; do
		[ -f "$config" ] || continue
		perl -0pi -e '
			s/Video_Game_Resolution=Low/Video_Game_Resolution=High/g;
			s/Video_Movie_Resolution=Low/Video_Movie_Resolution=High/g;
			s/Video_Texture_Resolution=Low/Video_Texture_Resolution=High/g;
			s/Video_Texture_Cache=Small/Video_Texture_Cache=Large/g;
			s/Video_Variable_Frame_Rate=Yes/Video_Variable_Frame_Rate=No/g;
			s/Acceleration_VGA_Automap=Yes/Acceleration_VGA_Automap=No/g;
			s/Acceleration_VGA_Movies=Yes/Acceleration_VGA_Movies=No/g;
			s/Acceleration_Use4444=Yes/Acceleration_Use4444=No/g;
			s/Acceleration_Filtering=Off/Acceleration_Filtering=On/g;
			s/Acceleration_Toggle=Off/Acceleration_Toggle=On/g;
		' "$config"
	done

	cp -f "$DOSBOX_CONF_TEMPLATE" "$RUNTIME_CONF"
	replace_or_append_setting "$RUNTIME_CONF" fullscreen true
	replace_or_append_setting "$RUNTIME_CONF" fullresolution "$RESOLUTION"
	replace_or_append_setting "$RUNTIME_CONF" windowresolution "$RESOLUTION"
	replace_or_append_setting "$RUNTIME_CONF" viewport_resolution "$DOSBOX_VIEWPORT"
	replace_or_append_setting "$RUNTIME_CONF" output "$DOSBOX_OUTPUT"
	replace_or_append_setting "$RUNTIME_CONF" aspect "$DOSBOX_ASPECT"
	replace_or_append_setting "$RUNTIME_CONF" viewport "$DOSBOX_VIEWPORT"
	replace_or_append_setting "$RUNTIME_CONF" glshader "$DOSBOX_SHADER"
	replace_or_append_setting "$RUNTIME_CONF" machine svga_s3
	replace_or_append_setting "$RUNTIME_CONF" memsize 64
	replace_or_append_setting "$RUNTIME_CONF" mcb_fault_strategy allow
	replace_or_append_setting "$RUNTIME_CONF" cycles "max 85%"
	ensure_section "$RUNTIME_CONF" voodoo
	replace_or_append_setting "$RUNTIME_CONF" voodoo true
	replace_or_append_setting "$RUNTIME_CONF" voodoo_memsize 12
	replace_or_append_setting "$RUNTIME_CONF" voodoo_multithreading true
	replace_or_append_setting "$RUNTIME_CONF" voodoo_bilinear_filtering true

	perl -0pi -e '
		my $runtime_c = $ENV{LOLG_HD_RUNTIME_C};
		my $cd_iso = $ENV{LOLG_HD_CD_ISO};
		s#^mount C .*$#mount C "$runtime_c"#m;
		s#^imgmount D .*$#imgmount D "$cd_iso" -t iso#m;
		s/^pause\r?$/rem pause/m;
		s/^cd\s+(?:lolg|\\)\r?$/cd lolg/mi;
		s/^lolg -CD C:\\(?:LOLG\\?)?.*$/lolg -CD C:\\LOLG\\ /mi;
		s/^exit\r?$/rem exit/m;
	' "$RUNTIME_CONF"
}

print_mix_status() {
	if [ "$LOLG_HD_DOSBOX_NGLIDE_USE_HDMIX" -eq 0 ]; then
		echo "MIX HD: non, MIX originaux de C/LOLG"
		return
	fi

	hd_links=$(find "$RUNTIME_GAME_DIR" -maxdepth 1 -type l -iname '*.MIX' -lname "$HD_MIX_DIR/*" 2>/dev/null | wc -l)
	override_links=$(find "$RUNTIME_GAME_DIR" -maxdepth 1 -type l -iname '*.MIX' -lname "$DOSBOX_MIX_OVERRIDE_DIR/*" 2>/dev/null | wc -l)
	original_links=$(find "$RUNTIME_GAME_DIR" -maxdepth 1 -type l -iname '*.MIX' ! -lname "$HD_MIX_DIR/*" ! -lname "$DOSBOX_MIX_OVERRIDE_DIR/*" 2>/dev/null | wc -l)
	echo "MIX HD: actif depuis mod_mix_vqa_fullhd"
	echo "Mode MIX HD: $LOLG_HD_DOSBOX_MIX_MODE"
	echo "MIX HD mod_mix_vqa_fullhd: $hd_links"
	echo "MIX reconstruits override: $override_links"
	echo "MIX originaux fallback: $original_links"
	if [ "$LOLG_HD_DOSBOX_MIX_MODE" = "all" ]; then
		echo "MIX HD exclus DOS connus: $DOS_ALWAYS_EXCLUDED_HD_MIX"
	else
		echo "MIX HD exclus DOS connus: $DOS_ALWAYS_EXCLUDED_HD_MIX,$DOS_SAFE_EXCLUDED_HD_MIX"
	fi
	if [ -n "$LOLG_HD_DOSBOX_HD_INCLUDE" ]; then
		echo "HD include: $LOLG_HD_DOSBOX_HD_INCLUDE"
	fi
	if [ -n "$LOLG_HD_DOSBOX_HD_EXCLUDE" ]; then
		echo "HD exclude: $LOLG_HD_DOSBOX_HD_EXCLUDE"
	fi
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

export LOLG_HD_RUNTIME_C="$RUNTIME_C"
export LOLG_HD_CD_ISO="$CD_ISO"
prepare_runtime

echo "Mode DOSBox 1920 nGlide/3dfx"
echo "DOSBox: $("$DOSBOX_BIN" --version | head -n 1)"
echo "Runtime: $RUNTIME_ROOT"
echo "Config: $RUNTIME_CONF"
echo "Resolution: $RESOLUTION"
echo "Profil image: $VISUAL_PROFILE ($DOSBOX_OUTPUT, $DOSBOX_ASPECT, $DOSBOX_VIEWPORT, $DOSBOX_SHADER)"
echo "3dfx jeu: OPTIONS.INI = OPT3DFX.INI, Acceleration_Toggle=On"
echo "Glide: emulation Voodoo DOSBox-Staging (voodoo=true, memsize=12)"
print_mix_status

if [ "$STATUS_ONLY" -eq 1 ] || [ "$PREPARE_ONLY" -eq 1 ]; then
	exit 0
fi

if [ -d "$LOCAL_LIB_DIR" ]; then
	LD_LIBRARY_PATH="$LOCAL_LIB_DIR${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
	export LD_LIBRARY_PATH
fi

cd "$BASE_DIR"
exec "$DOSBOX_BIN" -conf "$RUNTIME_CONF"
