#!/usr/bin/env sh

set -eu

BASE_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$BASE_DIR"

command_name=${1:-launch}
if [ "$#" -gt 0 ]; then
	shift
fi

case "$command_name" in
	launch)
		./LOLG_HD.sh "$@" || status=$?
		;;
	status|repair|notice|check|gpu|manifest|stop)
		./LOLG_HD.sh "$command_name" "$@" || status=$?
		;;
	*)
		./LOLG_HD.sh "$command_name" "$@" || status=$?
		;;
esac

status=${status:-0}

if [ "${LOLG_HD_DESKTOP_PAUSE:-1}" = "1" ]; then
	printf '\nAppuyez sur Entree pour fermer...'
	IFS= read -r _unused || true
fi

exit "$status"
