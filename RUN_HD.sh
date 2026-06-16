#!/bin/sh

set -eu

BASE_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
GAME_DIR="$BASE_DIR/C/LOLG"
DOSBOX_BIN="$BASE_DIR/dosbox"
DOSBOX_CONF="$BASE_DIR/lol2dos.conf"

if [ ! -x "$DOSBOX_BIN" ]; then
	echo "DOSBox introuvable ou non executable: $DOSBOX_BIN" >&2
	exit 1
fi

if [ ! -f "$DOSBOX_CONF" ]; then
	echo "Configuration DOSBox introuvable: $DOSBOX_CONF" >&2
	exit 1
fi

cd "$GAME_DIR"

for config in OPTIONS.INI OPT3DFX.INI OPTFIX.INI; do
	[ -f "$config" ] || continue
	perl -0pi -e '
		s/Video_Game_Resolution=Low/Video_Game_Resolution=High/g;
		s/Video_Movie_Resolution=Low/Video_Movie_Resolution=High/g;
		s/Video_Texture_Resolution=Low/Video_Texture_Resolution=High/g;
		s/Video_Texture_Cache=Small/Video_Texture_Cache=Large/g;
		s/Acceleration_Filtering=Off/Acceleration_Filtering=On/g;
		s/Acceleration_Toggle=Off/Acceleration_Toggle=On/g;
	' "$config"
done

cd "$BASE_DIR"

perl -0pi -e '
	s/^fullscreen\s*=.*$/fullscreen = true/m;
	s/^fullresolution\s*=.*$/fullresolution = 1920x1080/m;
	s/^windowresolution\s*=.*$/windowresolution = 1920x1080/m;
	s/^viewport_resolution\s*=.*$/viewport_resolution = 1920x1080/m;
	s/^output\s*=.*$/output = opengl/m;
	s/^aspect\s*=.*$/aspect = stretch/m;
	s/^scaler\s*=.*$/scaler = none/m;
	s/^glshader\s*=.*$/glshader = interpolation\/catmull-rom/m;
	s/^mount C .*$/mount C "C"/m;
	s#^imgmount D .*$#imgmount D "CD/CD.iso" -t iso#m;
' "$DOSBOX_CONF"

exec "$DOSBOX_BIN" -conf "$DOSBOX_CONF"
