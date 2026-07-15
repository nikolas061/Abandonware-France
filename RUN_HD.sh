#!/bin/sh

set -eu

BASE_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
GAME_DIR="$BASE_DIR"
GAME_DOS_DIR="$GAME_DIR/C/LOLG"
DOSBOX_BIN="$BASE_DIR/dosbox"
DOSBOX_CONF="$BASE_DIR/lol2dos.conf"
LOCAL_LIB_DIR="$BASE_DIR/lib"
	VISUAL_PROFILE=${LOLG_HD_DOSBOX_PROFILE:-smooth}

usage() {
	cat <<'EOF'
Usage: ./RUN_HD.sh [profil-image]

Profils image:
  smooth   Ratio correct, image douce (defaut)
  sharp    Ratio correct, image nette
  pixel    Ratio correct, pixels nets sans interpolation
  crt      Ratio correct, rendu CRT VGA 1080p
  stretch  Plein 1920x1080 etire
EOF
}

if [ "$#" -gt 0 ]; then
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
	esac
fi

if [ "$#" -gt 0 ]; then
	echo "Option DOSBox inconnue: $1" >&2
	usage >&2
	exit 2
fi

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

export DOSBOX_OUTPUT DOSBOX_ASPECT DOSBOX_VIEWPORT DOSBOX_SHADER

if [ ! -x "$DOSBOX_BIN" ]; then
	echo "DOSBox introuvable ou non executable: $DOSBOX_BIN" >&2
	exit 1
fi

if [ ! -f "$DOSBOX_CONF" ]; then
	echo "Configuration DOSBox introuvable: $DOSBOX_CONF" >&2
	exit 1
fi

if [ ! -d "$GAME_DOS_DIR" ]; then
	echo "Dossier jeu DOS introuvable: $GAME_DOS_DIR" >&2
	exit 1
fi

cd "$GAME_DOS_DIR"

for config in OPTIONS.INI OPT3DFX.INI OPTFIX.INI; do
	[ -f "$config" ] || continue
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
	' "$config"
done

cd "$BASE_DIR"

if [ -d "$LOCAL_LIB_DIR" ]; then
	LD_LIBRARY_PATH="$LOCAL_LIB_DIR${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
	export LD_LIBRARY_PATH
fi

perl -0pi -e '
	my $output = $ENV{DOSBOX_OUTPUT};
	my $aspect = $ENV{DOSBOX_ASPECT};
	my $viewport = $ENV{DOSBOX_VIEWPORT};
	my $shader = $ENV{DOSBOX_SHADER};
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
	s/^mount C .*$/mount C "C"/m;
	s#^imgmount D .*$#imgmount D "CD/CD.iso" -t iso#m;
	s/^pause\r?$/rem pause/m;
	s/^cd\s+(?:lolg|\\)\r?$/cd lolg/mi;
	s/^lolg -CD C:\\(?:LOLG\\?)?.*$/lolg -CD C:\\LOLG\\ /mi;
	s/^exit\r?$/rem exit/m;
' "$DOSBOX_CONF"

echo "Profil image DOSBox: $VISUAL_PROFILE ($DOSBOX_OUTPUT, $DOSBOX_ASPECT, $DOSBOX_VIEWPORT, $DOSBOX_SHADER)"
exec "$DOSBOX_BIN" -conf "$DOSBOX_CONF"
