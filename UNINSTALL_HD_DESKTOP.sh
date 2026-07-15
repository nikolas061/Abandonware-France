#!/usr/bin/env sh

set -eu

TARGET_DIR=${XDG_DATA_HOME:-"$HOME/.local/share"}/applications
CONFIRM=0

usage() {
	cat <<'EOF'
Usage: ./UNINSTALL_HD_DESKTOP.sh [--confirm]

Retire les raccourcis Lands of Lore II HD du menu utilisateur Linux:
  ~/.local/share/applications/

Par securite, le mode par defaut est un dry-run. Rien n'est supprime sans
--confirm.

Options:
  --confirm  Supprime vraiment les trois raccourcis du menu utilisateur
  -h, --help Affiche cette aide
EOF
}

while [ "$#" -gt 0 ]; do
	case "$1" in
		--confirm)
			CONFIRM=1
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

remove_one() {
	dst=$1
	if [ "$CONFIRM" -eq 0 ]; then
		if [ -e "$dst" ]; then
			echo "dry-run: supprimerait $dst"
		else
			echo "dry-run: absent $dst"
		fi
		return
	fi
	if [ -e "$dst" ]; then
		rm -f "$dst"
		echo "supprime: $dst"
	else
		echo "deja absent: $dst"
	fi
}

echo "Dossier cible: $TARGET_DIR"
remove_one "$TARGET_DIR/lolg-hd.desktop"
remove_one "$TARGET_DIR/lolg-hd-status.desktop"
remove_one "$TARGET_DIR/lolg-hd-repair.desktop"

if [ "$CONFIRM" -eq 1 ] && command -v update-desktop-database >/dev/null 2>&1; then
	update-desktop-database "$TARGET_DIR" >/dev/null 2>&1 || true
fi

if [ "$CONFIRM" -eq 0 ]; then
	echo "Aucune suppression effectuee. Relancer avec --confirm pour supprimer."
else
	echo "Desinstallation des raccourcis terminee."
fi
