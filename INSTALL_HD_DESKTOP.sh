#!/usr/bin/env sh

set -eu

BASE_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
TARGET_DIR=${XDG_DATA_HOME:-"$HOME/.local/share"}/applications
DRY_RUN=0

usage() {
	cat <<'EOF'
Usage: ./INSTALL_HD_DESKTOP.sh [--dry-run]

Installe les raccourcis Lands of Lore II HD dans le menu utilisateur Linux:
  ~/.local/share/applications/

Options:
  --dry-run   Affiche ce qui serait installe sans rien copier
  -h, --help  Affiche cette aide
EOF
}

while [ "$#" -gt 0 ]; do
	case "$1" in
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

install_one() {
	src=$1
	dst=$2
	if [ ! -f "$src" ]; then
		echo "Raccourci introuvable: $src" >&2
		exit 1
	fi
	if [ "$DRY_RUN" -eq 1 ]; then
		echo "dry-run: $src -> $dst"
		render_desktop "$src" | awk '/^(Exec|Path)=/ { print "  " $0 }'
		return
	fi
	mkdir -p "$TARGET_DIR"
	tmp="$dst.tmp.$$"
	render_desktop "$src" >"$tmp"
	mv "$tmp" "$dst"
	chmod 0644 "$dst"
	echo "installe: $dst"
}

render_desktop() {
	src=$1
	while IFS= read -r line || [ -n "$line" ]; do
		case "$line" in
			Exec=*RUN_HD_DESKTOP.sh*)
				args=${line#*RUN_HD_DESKTOP.sh}
				printf 'Exec=%s/RUN_HD_DESKTOP.sh%s\n' "$BASE_DIR" "$args"
				;;
			Path=*)
				printf 'Path=%s\n' "$BASE_DIR"
				;;
			*)
				printf '%s\n' "$line"
				;;
		esac
	done <"$src"
}

echo "Dossier cible: $TARGET_DIR"
install_one "$BASE_DIR/desktop/lolg-hd.desktop" "$TARGET_DIR/lolg-hd.desktop"
install_one "$BASE_DIR/desktop/lolg-hd-status.desktop" "$TARGET_DIR/lolg-hd-status.desktop"
install_one "$BASE_DIR/desktop/lolg-hd-repair.desktop" "$TARGET_DIR/lolg-hd-repair.desktop"

if [ "$DRY_RUN" -eq 0 ] && command -v update-desktop-database >/dev/null 2>&1; then
	update-desktop-database "$TARGET_DIR" >/dev/null 2>&1 || true
fi

if [ "$DRY_RUN" -eq 1 ]; then
	echo "Aucune copie effectuee."
else
	echo "Raccourcis installes dans le menu utilisateur."
fi
