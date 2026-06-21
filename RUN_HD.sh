#!/bin/sh

set -eu

BASE_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
GAME_DIR="$BASE_DIR"
DOSBOX_BIN="$BASE_DIR/dosbox"
DOSBOX_CONF="$BASE_DIR/lol2dos.conf"
LOCAL_LIB_DIR="$BASE_DIR/lib"

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
	s/^fullscreen\s*=.*$/fullscreen = true/m;
	s/^fullresolution\s*=.*$/fullresolution = 1920x1080/m;
	s/^windowresolution\s*=.*$/windowresolution = 1920x1080/m;
	if (/^viewport_resolution\s*=/m) {
		s/^viewport_resolution\s*=.*$/viewport_resolution = 1920x1080/m;
	} else {
		s/^(windowresolution\s*=.*)$/\1\nviewport_resolution = 1920x1080/m;
	}
	s/^output\s*=.*$/output = opengl/m;
	s/^aspect\s*=.*$/aspect = stretch/m;
	if (/^viewport\s*=/m) {
		s/^viewport\s*=.*$/viewport = 1920x1080/m;
	} else {
		s/^(aspect\s*=.*)$/\1\nviewport = 1920x1080/m;
	}
	s/^glshader\s*=.*$/glshader = interpolation\/catmull-rom/m;
	s/^mount C .*$/mount C "."/m;
	s#^imgmount D .*$#imgmount D "CD/CD.iso" -t iso#m;
	s/^cd lolg\r?$/cd \\/mi;
	s/^lolg -CD C:\\LOLG\r?$/lolg -CD C:\\/mi;
' "$DOSBOX_CONF"

exec "$DOSBOX_BIN" -conf "$DOSBOX_CONF"
