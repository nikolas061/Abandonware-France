#!/usr/bin/env sh

set -eu

BASE_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$BASE_DIR"

usage() {
	cat <<'EOF'
Usage: ./LOLG_HD.sh [commande] [options]

Commande par defaut:
  wine          Lance Lands of Lore II en Full HD via Wine, 1920x1080, LOCALLNG original

Commandes:
  wine          Lance Wine HD 1920x1080 avec LOCALLNG original
  wine-1920     Lance Wine HD 1920x1080 avec LOCALLNG original
  wine-1280     Lance Wine HD 1280x1024 avec LOCALLNG original
  wine-vulkan   Lance Wine 1920x1080 en Vulkan/DXVK, Win95, sans dgVoodoo
  wine-hdmix-stable Lance Wine 1920x1080 sans dgVoodoo, MIX HD sauf LOCALLNG/MOVIES
  wine-1280-vulkan Lance Wine 1280x1024 en Vulkan/DXVK, Win95, sans dgVoodoo
  wine-gamescope Ancien diagnostic sans dgVoodoo via gamescope, non recommande
  wine-gamescope-1440 Ancien diagnostic gamescope 1440x1080, non recommande
  wine-gamescope-1280 Ancien diagnostic gamescope 1280x1024, non recommande
  wine-locallng-hd Lance Wine Vulkan avec LOCALLNG_HD.MIX, sans dgVoodoo
  wine-locallng-hd-1440 Lance Wine 1440x1080 stable, LOCALLNG/MOVIES originaux, autres MIX HD
  wine-locallng-hd-1440-lowmem Lance le mode stable avec -LOWMEM et cache textures reduit
  wine-vqa-contract Diagnostic instable LOCALLNG/MOVIES HD 1280, bloque sauf override
  wine-vqa-contract-locallng Diagnostic instable LOCALLNG HD 1280 padde seul, bloque sauf override
  vqa-contract-build-locallng-1280-padded Regenere la candidate LOCALLNG 1280 paddee + gate LCW
  wine-vqa-contract-locallng-896-padded Diagnostic LOCALLNG 896 CBPZ padde, bloque sauf override
  vqa-contract-build-locallng-896-padded Regenere la candidate LOCALLNG 896 paddee + gate LCW
  vqa-contract-build-movies-cbpz-padded Recompresse MOVIES 0/19/20 CBPZ + gates LCW/runtime
  vqa-plan-movies-safe Planifie les resolutions MOVIES sous le seuil stable mesure
  vqa-contract-build-movies-safe Regenere MOVIES 0-27 en 892x560 sous le seuil stable
  vqa-contract-build-movies-safe-smoke Teste le build batch safe sur MOVIES entree 4
  vqa-contract-build-movies-safe-long0 Teste le build batch safe sur MOVIES entree 0
  vqa-contract-build-movies-safe-long1 Teste le build batch safe sur MOVIES entree 1
  vqa-contract-build-movies-safe-long2 Teste le build batch safe sur MOVIES entree 2
  vqa-contract-build-movies-safe-long3 Teste le build batch safe sur MOVIES entree 3
  vqa-contract-build-movies-safe-short Teste le build batch safe sur MOVIES entrees 5-18
  vqa-contract-build-movies-safe-mid Teste le build batch safe sur MOVIES entrees 19-20
  vqa-contract-build-movies-safe-tail Teste le build batch safe sur MOVIES entrees 21-27
  wine-vqa-contract-movies-noroom Diagnostic LOCALLNG 1280 + MOVIES CBPZ no_room, bloque sauf override
  wine-vqa-contract-movies-noroom-only Diagnostic MOVIES CBPZ no_room seul, LOCALLNG original, bloque sauf override
  wine-vqa-contract-custom-pair Diagnostic LOCALLNG 1024x640 + MOVIES entree 4 892x560, bloque sauf override
  wine-vqa-contract-dgvoodoo Diagnostic instable LOCALLNG/MOVIES HD 1280 via dgVoodoo, bloque sauf override
  vqa-contract-status Verifie les fichiers/audits LOCALLNG+MOVIES contractuels sans lancer Wine
	  wine-dgvoodoo-win10 Lance Wine 1920x1080 avec dgVoodoo et Windows 10, sans DXVK
	  wine-dgvoodoo-win10-safevqa Meme profil, mais VQA critiques, monstres, animations de niveau et effets animes en MIX originaux
	  wine-external-sidecar Prepare l'index VQA HD externe et lance safevqa stable
	  sidecar-test Extrait et decode une petite VQA HD externe pour verifier le sidecar
	  sidecar-critical-test Decode 1 frame LOCALLNG + MOVIES via le sidecar externe
	  sidecar-critical-warmup Decode toutes les frames critiques LOCALLNG + MOVIES
	  sidecar-watch Surveille une requete runtime VQA externe et prepare le cache sidecar
	  sidecar-web Lance le lecteur web local des frames VQA sidecar
	  sidecar-status Resume l'index, le runtime et la derniere VQA sidecar
	  sidecar-critical-status Resume aussi les decodes critiques LOCALLNG/MOVIES
	  sidecar-audit Audite une session VQA sidecar et sa couverture runtime
	  sidecar-trace-bridge Convertit une trace MIX/VQA en requete sidecar
	  sidecar-strace-bridge Convertit une trace strace Wine en trace sidecar
	  sidecar-hd Lance le chemin recommande: jeu safevqa + player VQA HD HUD
	  sidecar-live Lance bridge + lecteur web + jeu Wine safevqa externe
	  sidecar-live-strace Lance le live sidecar avec capture strace Wine
	  sidecar-live-strace-all Meme mode, sans limite de frames decodees
	  sidecar-live-strace-player Lance strace et ouvre le player VQA HD
	  sidecar-live-strace-all-player Meme mode, toutes frames, avec player
	  sidecar-live-strace-wide-player Capture toutes lectures MIX et ouvre le player
		  sidecar-live-strace-wide-all-player Meme mode large, toutes frames, avec player
		  sidecar-live-strace-wide-hud Meme mode large, player avec HUD
		  sidecar-live-strace-wide-all-hud Meme mode large, toutes frames, player HUD
		  sidecar-hd-nodg Meme chemin sidecar HD, mais moteur Wine safevqa sans dgVoodoo
		  wine-nodgvoodoo-safevqa Meme profil safevqa que dgVoodoo, mais sans dgVoodoo
		  wine-dgvoodoo-win10-safevqa-movies-safe Meme profil safevqa, mais MOVIES.MIX 892x560 complet
		  wine-dgvoodoo-win95-safevqa-direct Meme profil safevqa, mais Wine win95 et lancement direct sans bureau virtuel
		  wine-dgvoodoo-win10-originalmix Meme profil, mais tous les MIX originaux
	  wine-nglide-win10 Lance Wine 1920x1080 avec nGlide 2 installe dans Wine, sans DXVK
	  wine-nglide-win10-safevqa Meme profil nGlide, mais animations de niveau en MIX originaux
	  wine-dgvoodoo-hdmix Lance Wine 1920x1080 avec dgVoodoo, LOCALLNG/MOVIES originaux, autres MIX HD
  wine-1440-hdmix Diagnostic VQA HD instable, MOVIES.MIX HD, sans -LOWMEM
  wine-1440-hdmix-lowmem Diagnostic VQA HD instable, MOVIES.MIX HD, avec -LOWMEM
  wine-locallng-hd-1440-experimental Diagnostic VQA HD instable, LOCALLNG_HD.MIX
  wine-locallng-hd-1440-experimental-lowmem Diagnostic VQA HD instable, LOCALLNG_HD.MIX avec -LOWMEM
  wine-locallng-hd-vulkan Alias explicite de wine-locallng-hd
  wine-locallng-hd-ddraw Lance Wine LOCALLNG_HD avec DDraw.dll local, sans dgVoodoo
  wine-locallng-hd-dgvoodoo Lance Wine LOCALLNG_HD avec dgVoodoo local
  wine-locallng-sidecar Alias diagnostic de wine-locallng-hd
  prepare       Prepare le stage Wine HD sans lancer le jeu
  repair        Stoppe, prepare, recontrole et affiche le status
  dosbox        Lance le chemin DOSBox original (profil image: sharp/smooth/pixel/crt/stretch)
  dosbox-hd     Lance DOSBox avec mod_mix_vqa_fullhd
  dosbox-mod    Alias de dosbox-hd
  dosbox-nglide Lance DOSBox 1920 plein ecran avec profil 3dfx et emulation Voodoo
  dosbox-nglide-hdmix Lance DOSBox 1920 3dfx/Voodoo avec MIX HD surs
  check         Valide le paquet HD et rafraichit manifeste/verif sans option
  status        Resume l'etat release sans lancer Wine
  stop          Arrete le runtime Wine HD cible du projet
  smoke         Teste rapidement le runtime Wine HD en 1920x1080
  smoke-1280    Teste rapidement le runtime Wine HD en 1280x1024
  gpu           Diagnostique le rendu Wine/OpenGL et l'acces GPU
  resolutions   Controle les resolutions Wine HD sans lancer le jeu
  manifest      Genere le manifeste local de release HD, sans copier les 19 Go
  verify-manifest Verifie le manifeste release sans hasher les gros MIX
  git-audit     Verifie que Git suit les sources legeres et ignore les gros payloads
  verify-support Verifie BUNDLE_MANIFEST.csv du paquet support
  verify-support-archive Verifie l'archive support tar.gz, son resume/SHA256 et son extraction
  install-desktop Installe les raccourcis dans le menu utilisateur Linux
  uninstall-desktop Retire les raccourcis du menu utilisateur (dry-run par defaut)
  support       Collecte un paquet diagnostic leger dans output/hd_support_bundle
  notice        Affiche la notice courte LANCER_HD.txt
  help          Affiche cette aide

Les options apres la commande sont transmises au script appele.
Exemples:
  ./LOLG_HD.sh
  ./LOLG_HD.sh wine --dry-run
  ./LOLG_HD.sh wine-1280
  ./LOLG_HD.sh wine-vulkan
  ./LOLG_HD.sh wine-hdmix-stable
  ./LOLG_HD.sh wine-1280-vulkan
	  ./LOLG_HD.sh wine-locallng-hd
	  ./LOLG_HD.sh wine-locallng-hd-1440
	  ./LOLG_HD.sh wine-locallng-hd-1440-lowmem
	  ./LOLG_HD.sh wine-vqa-contract
	  ./LOLG_HD.sh wine-vqa-contract-locallng
	  ./LOLG_HD.sh vqa-contract-build-locallng-1280-padded
	  ./LOLG_HD.sh wine-vqa-contract-locallng-896-padded
	  ./LOLG_HD.sh vqa-contract-build-locallng-896-padded
	  ./LOLG_HD.sh vqa-contract-build-movies-cbpz-padded
	  ./LOLG_HD.sh vqa-contract-build-movies-safe --dry-run
	  ./LOLG_HD.sh vqa-contract-build-movies-safe-smoke
	  ./LOLG_HD.sh vqa-contract-build-movies-safe-long0
	  ./LOLG_HD.sh vqa-contract-build-movies-safe-long1
	  ./LOLG_HD.sh vqa-contract-build-movies-safe-long2
	  ./LOLG_HD.sh vqa-contract-build-movies-safe-long3
	  ./LOLG_HD.sh vqa-contract-build-movies-safe-short
	  ./LOLG_HD.sh vqa-contract-build-movies-safe-mid
	  ./LOLG_HD.sh vqa-contract-build-movies-safe-tail
	  ./LOLG_HD.sh wine-vqa-contract-movies-noroom
	  ./LOLG_HD.sh wine-vqa-contract-movies-noroom-only
	  ./LOLG_HD.sh wine-vqa-contract-dgvoodoo
	  ./LOLG_HD.sh vqa-contract-status
	  ./LOLG_HD.sh wine-dgvoodoo-win10
	  ./LOLG_HD.sh wine-dgvoodoo-win10-safevqa
	  ./LOLG_HD.sh wine-external-sidecar
	  ./LOLG_HD.sh sidecar-test
	  ./LOLG_HD.sh sidecar-critical-test
	  ./LOLG_HD.sh sidecar-critical-warmup
	  ./LOLG_HD.sh sidecar-watch
	  ./LOLG_HD.sh sidecar-web
	  ./LOLG_HD.sh sidecar-web --check --summary
	  ./LOLG_HD.sh sidecar-status
	  ./LOLG_HD.sh sidecar-critical-status
	  ./LOLG_HD.sh sidecar-status --events 10
	  ./LOLG_HD.sh sidecar-audit
	  ./LOLG_HD.sh sidecar-audit --events 50
	  ./LOLG_HD.sh sidecar-trace-bridge --line "archive=HERB.MIX index=46" --process
	  ./LOLG_HD.sh sidecar-strace-bridge --watch
	  ./LOLG_HD.sh sidecar-hd
	  ./LOLG_HD.sh sidecar-live
	  ./LOLG_HD.sh sidecar-live --trace-source strace
	  ./LOLG_HD.sh sidecar-live --trace-source strace --max-frames 0
	  ./LOLG_HD.sh sidecar-live-strace
	  ./LOLG_HD.sh sidecar-live-strace-all
	  ./LOLG_HD.sh sidecar-live-strace-player
	  ./LOLG_HD.sh sidecar-live-strace-all-player
	  ./LOLG_HD.sh sidecar-live-strace-wide-player
	  ./LOLG_HD.sh sidecar-live-strace-wide-all-player
		  ./LOLG_HD.sh sidecar-live-strace-wide-all-player --player-hud
		  ./LOLG_HD.sh sidecar-live-strace-wide-hud
		  ./LOLG_HD.sh sidecar-live-strace-wide-all-hud
		  ./LOLG_HD.sh sidecar-hd-nodg
		  ./LOLG_HD.sh wine-nodgvoodoo-safevqa
		  ./LOLG_HD.sh wine-dgvoodoo-win10-safevqa-movies-safe
		  ./LOLG_HD.sh wine-dgvoodoo-win95-safevqa-direct
		  ./LOLG_HD.sh wine-dgvoodoo-win10-originalmix
	  ./LOLG_HD.sh wine-nglide-win10
	  ./LOLG_HD.sh wine-nglide-win10-safevqa
	  ./LOLG_HD.sh wine-dgvoodoo-hdmix
  ./LOLG_HD.sh wine-1440-hdmix
  ./LOLG_HD.sh wine-1440-hdmix-lowmem
  ./LOLG_HD.sh wine-locallng-hd-1440-experimental
  ./LOLG_HD.sh wine-locallng-hd-1440-experimental-lowmem
  ./LOLG_HD.sh wine-locallng-hd-vulkan
  ./LOLG_HD.sh wine-locallng-hd-ddraw
  ./LOLG_HD.sh wine-locallng-hd-dgvoodoo
  ./LOLG_HD.sh repair
  ./LOLG_HD.sh dosbox-hd smooth
  ./LOLG_HD.sh dosbox-hd crt
  ./LOLG_HD.sh dosbox-nglide
  ./LOLG_HD.sh dosbox-nglide-hdmix smooth
  ./LOLG_HD.sh dosbox-nglide-hdmix smooth --mix-mode=all
  ./LOLG_HD.sh dosbox sharp
  ./LOLG_HD.sh dosbox smooth
  ./LOLG_HD.sh dosbox crt
  ./LOLG_HD.sh status
  ./LOLG_HD.sh stop
  ./LOLG_HD.sh check
  ./LOLG_HD.sh gpu
  ./LOLG_HD.sh resolutions
  ./LOLG_HD.sh manifest
  ./LOLG_HD.sh verify-manifest
  ./LOLG_HD.sh git-audit
  ./LOLG_HD.sh install-desktop --dry-run
  ./LOLG_HD.sh uninstall-desktop
  ./LOLG_HD.sh support
  ./LOLG_HD.sh verify-support
  ./LOLG_HD.sh verify-support-archive
  ./LOLG_HD.sh notice
EOF
}

require_executable() {
	if [ ! -x "$1" ]; then
		echo "Script introuvable ou non executable: $1" >&2
		exit 1
	fi
}

require_vqa_contract_pass() {
	report=$1
	label=$2
	if [ ! -f "$report" ]; then
		echo "Rapport VQA contract manquant pour $label: $report" >&2
		exit 1
	fi
	status=$(awk -F, 'NR == 2 { print $1; exit }' "$report")
	if [ "$status" != "pass" ]; then
		echo "VQA contract invalide pour $label: status=$status" >&2
		echo "Rapport: $report" >&2
		exit 1
	fi
}

require_lcw_dialect_pass() {
	report=$1
	label=$2
	if [ ! -f "$report" ]; then
		echo "Rapport LCW manquant pour $label: $report" >&2
		exit 1
	fi
	gaps=$(awk -F, 'NR > 1 && $1 != "pass" { count++ } END { print count + 0 }' "$report")
	if [ "$gaps" != "0" ]; then
		echo "Gate LCW invalide pour $label: gaps=$gaps" >&2
		echo "Rapport: $report" >&2
		exit 1
	fi
}

require_vqa_contract_target() {
	link_path=$1
	expected_path=$2
	label=$3
	if [ ! -e "$link_path" ]; then
		echo "MIX VQA contract manquant pour $label: $link_path" >&2
		exit 1
	fi
	actual_path=$(readlink -f "$link_path" 2>/dev/null || true)
	if [ "$actual_path" != "$expected_path" ]; then
		echo "MIX VQA contract incorrect pour $label:" >&2
		echo "  actuel: ${actual_path:-introuvable}" >&2
		echo "  attendu: $expected_path" >&2
		exit 1
	fi
}

ensure_vqa_contract_pair_dir() {
	pair_dir=$1
	locallng_mix=$2
	movies_mix=$3
	mkdir -p "$pair_dir"
	ensure_vqa_contract_pair_link "$pair_dir/LOCALLNG.MIX" "$locallng_mix" "LOCALLNG.MIX"
	ensure_vqa_contract_pair_link "$pair_dir/MOVIES.MIX" "$movies_mix" "MOVIES.MIX"
}

ensure_vqa_contract_pair_link() {
	link_path=$1
	expected_path=$2
	label=$3
	if [ ! -f "$expected_path" ]; then
		echo "MIX VQA contract source manquant pour $label: $expected_path" >&2
		exit 1
	fi
	if [ -e "$link_path" ] && [ ! -L "$link_path" ]; then
		actual_path=$(readlink -f "$link_path" 2>/dev/null || true)
		if [ "$actual_path" != "$expected_path" ]; then
			echo "Conflit sidecar VQA contract pour $label:" >&2
			echo "  fichier existant: $link_path" >&2
			echo "  attendu: $expected_path" >&2
			exit 1
		fi
		return
	fi
	ln -sfn "$expected_path" "$link_path"
}

set_vqa_contract_paths() {
	CONTRACT_MIX_DIR="${LOLG_HD_CONTRACT_MIX_DIR:-$BASE_DIR/output/vqa_contract_pair_1280x1024_windowed_runtime}"
	CONTRACT_LOCALLNG_1280_PADDED_DIR="$BASE_DIR/output/vqa_contract_preserving_writer_locallng_1280x1024_vqaext_padded_cbpz_from_adaptive_decode"
	CONTRACT_LOCALLNG_LEGACY_DIR="$BASE_DIR/output/vqa_contract_preserving_writer_locallng_1280x1024_adaptive_extlcw"
	CONTRACT_LOCALLNG_DIR="${LOLG_HD_CONTRACT_LOCALLNG_DIR:-$CONTRACT_LOCALLNG_1280_PADDED_DIR}"
	CONTRACT_MOVIES_DIR="$BASE_DIR/output/vqa_contract_movies_1280_0000_0027_windowed_patch"
	CONTRACT_MOVIES_CBPZ_PADDED_DIR="$BASE_DIR/output/vqa_contract_movies_1280_0000_0027_cbpz_vqaext_noroom_patch"
	CONTRACT_MOVIES_RUNTIME_SUMMARY="$BASE_DIR/output/vqa_runtime_compat_movies_0000_0027_windowed_patch_final/summary.csv"
	CONTRACT_LOCALLNG_MIX="$CONTRACT_LOCALLNG_DIR/mix/LOCALLNG.MIX"
	CONTRACT_MOVIES_CBPZ_PADDED_MIX="$CONTRACT_MOVIES_CBPZ_PADDED_DIR/mix/MOVIES.MIX"
	CONTRACT_MOVIES_MIX="${LOLG_HD_CONTRACT_MOVIES_MIX:-$CONTRACT_MOVIES_DIR/MOVIES.MIX}"
	CONTRACT_MOVIES_MANIFEST="$CONTRACT_MOVIES_DIR/full_manifest.csv"
	CONTRACT_LOCALLNG_1280_PADDED_MIX="$CONTRACT_LOCALLNG_1280_PADDED_DIR/mix/LOCALLNG.MIX"
	CONTRACT_LOCALLNG_896_PADDED_DIR="$BASE_DIR/output/vqa_contract_preserving_writer_locallng_896x560_vqaext_padded_cbpz"
	CONTRACT_LOCALLNG_896_PADDED_MIX="$CONTRACT_LOCALLNG_896_PADDED_DIR/mix/LOCALLNG.MIX"
	CONTRACT_LOCALLNG_LCW_DIALECT_1280="$BASE_DIR/output/locallng_vqa_lcw_profile_1280_padded_gate_20260708/dialect.csv"
	CONTRACT_LOCALLNG_LCW_DIALECT_1280_LEGACY="$BASE_DIR/output/locallng_vqa_lcw_profile_original_vs_1280_20260708/dialect.csv"
	CONTRACT_LOCALLNG_LCW_DIALECT_896_PADDED="$BASE_DIR/output/locallng_vqa_lcw_profile_896_padded_gate_20260708/dialect.csv"
	CONTRACT_LOCALLNG_LCW_DIALECT_640="$BASE_DIR/output/locallng_vqa_lcw_profile_20260708/dialect.csv"
	CONTRACT_MOVIES_LCW_DIALECT_CBPZ_0="$BASE_DIR/output/movies_entry0_lcw_profile_cbpz_noroom_vqaext_20260708/dialect.csv"
	CONTRACT_MOVIES_LCW_DIALECT_CBPZ_19="$BASE_DIR/output/movies_entry19_lcw_profile_cbpz_noroom_vqaext_20260708/dialect.csv"
	CONTRACT_MOVIES_LCW_DIALECT_CBPZ_20="$BASE_DIR/output/movies_entry20_lcw_profile_cbpz_noroom_vqaext_20260708/dialect.csv"
	CONTRACT_MOVIES_RUNTIME_CBPZ_0="$BASE_DIR/output/vqa_runtime_compat_movies_cbpz_noroom_0000/summary.csv"
	CONTRACT_MOVIES_RUNTIME_CBPZ_19="$BASE_DIR/output/vqa_runtime_compat_movies_cbpz_noroom_0019/summary.csv"
	CONTRACT_MOVIES_RUNTIME_CBPZ_20="$BASE_DIR/output/vqa_runtime_compat_movies_cbpz_noroom_0020/summary.csv"
}

print_lcw_dialect_status() {
	label=$1
	report=$2
	if [ ! -f "$report" ]; then
		return
	fi
	lcw_pass=$(awk -F, 'NR > 1 && $1 == "pass" { count++ } END { print count + 0 }' "$report")
	lcw_total=$(awk -F, 'NR > 1 { count++ } END { print count + 0 }' "$report")
	lcw_gaps=$((lcw_total - lcw_pass))
	echo "$label LCW dialect: $lcw_pass/$lcw_total pass, gaps=$lcw_gaps"
	echo "$label LCW report: $report"
}

print_csv_status() {
	label=$1
	report=$2
	if [ ! -f "$report" ]; then
		return
	fi
	status=$(awk -F, 'NR == 2 { print $1; exit }' "$report")
	echo "$label: ${status:-unknown}"
	echo "$label report: $report"
}

validate_vqa_contract_pair() {
	allow_partial=${1:-0}
	set_vqa_contract_paths
	ensure_vqa_contract_pair_dir "$CONTRACT_MIX_DIR" "$CONTRACT_LOCALLNG_MIX" "$CONTRACT_MOVIES_MIX"
	if [ ! -f "$CONTRACT_MIX_DIR/LOCALLNG.MIX" ] || [ ! -f "$CONTRACT_MIX_DIR/MOVIES.MIX" ]; then
		echo "MIX contract-preserving introuvables dans: $CONTRACT_MIX_DIR" >&2
		echo "Regenerer d'abord LOCALLNG et MOVIES contractuels avant ce mode." >&2
		exit 1
	fi
	require_vqa_contract_pass "$CONTRACT_LOCALLNG_DIR/summary.csv" "LOCALLNG.MIX"
	require_vqa_contract_pass "$CONTRACT_LOCALLNG_DIR/runtime_compat/summary.csv" "LOCALLNG.MIX runtime"
	if [ "$allow_partial" = "1" ] && [ "${LOLG_HD_ALLOW_PARTIAL_MOVIES_CONTRACT:-0}" = "1" ]; then
		echo "ATTENTION: MOVIES.MIX contract-preserving est force malgre un audit runtime partiel/gap." >&2
		echo "Audit: $CONTRACT_MOVIES_RUNTIME_SUMMARY" >&2
	elif [ "$CONTRACT_MOVIES_MIX" = "$CONTRACT_MOVIES_CBPZ_PADDED_MIX" ]; then
		require_vqa_contract_pass "$CONTRACT_MOVIES_CBPZ_PADDED_DIR/summary.csv" "MOVIES.MIX CBPZ no_room"
		require_lcw_dialect_pass "$CONTRACT_MOVIES_LCW_DIALECT_CBPZ_0" "MOVIES.MIX entry 0 CBPZ no_room"
		require_lcw_dialect_pass "$CONTRACT_MOVIES_LCW_DIALECT_CBPZ_19" "MOVIES.MIX entry 19 CBPZ no_room"
		require_lcw_dialect_pass "$CONTRACT_MOVIES_LCW_DIALECT_CBPZ_20" "MOVIES.MIX entry 20 CBPZ no_room"
		require_vqa_contract_pass "$CONTRACT_MOVIES_RUNTIME_CBPZ_0" "MOVIES.MIX entry 0 CBPZ no_room runtime"
		require_vqa_contract_pass "$CONTRACT_MOVIES_RUNTIME_CBPZ_19" "MOVIES.MIX entry 19 CBPZ no_room runtime"
		require_vqa_contract_pass "$CONTRACT_MOVIES_RUNTIME_CBPZ_20" "MOVIES.MIX entry 20 CBPZ no_room runtime"
	else
		require_vqa_contract_pass "$CONTRACT_MOVIES_RUNTIME_SUMMARY" "MOVIES.MIX runtime batch 0-27"
	fi
	require_vqa_contract_target "$CONTRACT_MIX_DIR/LOCALLNG.MIX" "$CONTRACT_LOCALLNG_MIX" "LOCALLNG.MIX"
	require_vqa_contract_target "$CONTRACT_MIX_DIR/MOVIES.MIX" "$CONTRACT_MOVIES_MIX" "MOVIES.MIX"
}

print_vqa_contract_status() {
	validate_vqa_contract_pair 0
	echo "VQA contract pair: pass"
	echo "Sidecar: $CONTRACT_MIX_DIR"
	echo "LOCALLNG.MIX: $CONTRACT_LOCALLNG_MIX"
	echo "MOVIES.MIX: $CONTRACT_MOVIES_MIX"
	echo "MOVIES audit: $CONTRACT_MOVIES_RUNTIME_SUMMARY"
	echo "Runtime Wine: echec connu, Application Error avec LOCALLNG HD seul, MOVIES HD seul, ou les deux"
	echo "LOCALLNG runtime: echec aussi avec remplacement 640x400 compact/padde; garder original pour jouer"
	echo "Override diagnostic: LOLG_HD_ALLOW_CRASHING_VQA_CONTRACT=1"
	print_lcw_dialect_status "LOCALLNG 1280 padded" "$CONTRACT_LOCALLNG_LCW_DIALECT_1280"
	print_lcw_dialect_status "LOCALLNG 1280 legacy" "$CONTRACT_LOCALLNG_LCW_DIALECT_1280_LEGACY"
	print_lcw_dialect_status "LOCALLNG 896 padded" "$CONTRACT_LOCALLNG_LCW_DIALECT_896_PADDED"
	print_lcw_dialect_status "LOCALLNG 640 compact" "$CONTRACT_LOCALLNG_LCW_DIALECT_640"
	print_lcw_dialect_status "MOVIES entry 0 CBPZ no_room" "$CONTRACT_MOVIES_LCW_DIALECT_CBPZ_0"
	print_lcw_dialect_status "MOVIES entry 19 CBPZ no_room" "$CONTRACT_MOVIES_LCW_DIALECT_CBPZ_19"
	print_lcw_dialect_status "MOVIES entry 20 CBPZ no_room" "$CONTRACT_MOVIES_LCW_DIALECT_CBPZ_20"
	print_csv_status "MOVIES entry 0 CBPZ no_room runtime" "$CONTRACT_MOVIES_RUNTIME_CBPZ_0"
	print_csv_status "MOVIES entry 19 CBPZ no_room runtime" "$CONTRACT_MOVIES_RUNTIME_CBPZ_19"
	print_csv_status "MOVIES entry 20 CBPZ no_room runtime" "$CONTRACT_MOVIES_RUNTIME_CBPZ_20"
	if [ -f "$CONTRACT_LOCALLNG_1280_PADDED_MIX" ]; then
		echo "Best LOCALLNG runtime candidate: $CONTRACT_LOCALLNG_1280_PADDED_MIX"
		echo "Candidate launcher: LOLG_HD_ALLOW_CRASHING_VQA_CONTRACT=1 ./LOLG_HD.sh wine-vqa-contract-locallng"
	fi
	if [ -f "$CONTRACT_LOCALLNG_896_PADDED_MIX" ]; then
		echo "Fallback LOCALLNG runtime candidate: $CONTRACT_LOCALLNG_896_PADDED_MIX"
		echo "Fallback launcher: LOLG_HD_ALLOW_CRASHING_VQA_CONTRACT=1 ./LOLG_HD.sh wine-vqa-contract-locallng-896-padded"
	fi
	if [ -f "$CONTRACT_MOVIES_MANIFEST" ]; then
		echo "MOVIES manifest: $CONTRACT_MOVIES_MANIFEST"
	fi
	if [ -f "$CONTRACT_MOVIES_CBPZ_PADDED_MIX" ]; then
		echo "MOVIES CBPZ no_room probe: $CONTRACT_MOVIES_CBPZ_PADDED_MIX"
		echo "Probe build command: ./LOLG_HD.sh vqa-contract-build-movies-cbpz-padded"
	fi
	if command -v sha256sum >/dev/null 2>&1; then
		sha256sum "$CONTRACT_LOCALLNG_MIX"
		sha256sum "$CONTRACT_MOVIES_MIX"
		if [ -f "$CONTRACT_MOVIES_CBPZ_PADDED_MIX" ]; then
			sha256sum "$CONTRACT_MOVIES_CBPZ_PADDED_MIX"
		fi
	fi
}

is_dry_run_args() {
	for arg in "$@"; do
		if [ "$arg" = "--dry-run" ]; then
			return 0
		fi
	done
	return 1
}

is_prepare_only_args() {
	for arg in "$@"; do
		if [ "$arg" = "--prepare-only" ]; then
			return 0
		fi
	done
	return 1
}

require_vqa_contract_runtime_override() {
	label=$1
	shift || true
	if is_dry_run_args "$@"; then
		echo "ATTENTION: $label est un diagnostic VQA contract instable; dry-run autorise." >&2
		return 0
	fi
	if [ "${LOLG_HD_ALLOW_CRASHING_VQA_CONTRACT:-0}" = "1" ]; then
		echo "ATTENTION: lancement force de $label malgre le crash Wine connu." >&2
		return 0
	fi
	echo "Lancement bloque: $label est un diagnostic VQA contract instable/non prouve." >&2
	echo "Probes precedents: LOCALLNG HD seul, MOVIES HD seul, et LOCALLNG+MOVIES HD affichent Application Error." >&2
	echo "Pour diagnostic uniquement: LOLG_HD_ALLOW_CRASHING_VQA_CONTRACT=1 ./LOLG_HD.sh $command_name" >&2
	echo "Pour jouer: utiliser ./LOLG_HD.sh wine-dgvoodoo-win10-safevqa ou un mode qui garde LOCALLNG/MOVIES originaux." >&2
	exit 1
}

require_movies_safe_runtime_override() {
	label=$1
	shift || true
	if is_dry_run_args "$@" || is_prepare_only_args "$@"; then
		echo "ATTENTION: $label est un diagnostic MOVIES safe instable; dry-run/prepare-only autorise." >&2
		return 0
	fi
	if [ "${LOLG_HD_ALLOW_CRASHING_MOVIES_SAFE:-0}" = "1" ]; then
		echo "ATTENTION: lancement force de $label malgre le page fault Wine observe." >&2
		return 0
	fi
	echo "Lancement bloque: $label lance MOVIES.MIX safe 892x560 directement dans le moteur, mais le probe Wine page fault." >&2
	echo "Log: output/test_logs/wine_movies_safe_892_probe_20260708.log" >&2
	echo "Pour diagnostic uniquement: LOLG_HD_ALLOW_CRASHING_MOVIES_SAFE=1 ./LOLG_HD.sh $command_name" >&2
	echo "Pour jouer: utiliser ./LOLG_HD.sh sidecar-hd ou ./LOLG_HD.sh wine-dgvoodoo-win10-safevqa." >&2
	exit 1
}

if [ "$#" -eq 0 ]; then
	command_name=wine
else
	case "$1" in
		help|-h|--help)
			command_name=help
			shift
			;;
		-*)
			command_name=wine
			;;
		*)
			command_name=$1
			shift
			;;
	esac
fi

case "$command_name" in
	help|-h|--help)
		usage
		;;
	wine|wine-1920)
		require_executable ./RUN_HD_WINE.sh
		LOLG_HD_RESOLUTION=${LOLG_HD_RESOLUTION:-1920x1080}
		LOLG_HD_WINE_USE_HD_MIX=${LOLG_HD_WINE_USE_HD_MIX:-1}
		LOLG_HD_WINE_HD_EXCLUDE=${LOLG_HD_WINE_HD_EXCLUDE:-LOCALLNG.MIX,MOVIES.MIX}
		LOLG_HD_USE_ORIGINAL_MOVIES=${LOLG_HD_USE_ORIGINAL_MOVIES:-1}
		export LOLG_HD_RESOLUTION LOLG_HD_WINE_USE_HD_MIX LOLG_HD_WINE_HD_EXCLUDE LOLG_HD_USE_ORIGINAL_MOVIES
		exec ./RUN_HD_WINE.sh "$@"
		;;
	wine-1280)
		require_executable ./RUN_HD_WINE.sh
		LOLG_HD_RESOLUTION=1280x1024
		LOLG_HD_WINE_USE_HD_MIX=${LOLG_HD_WINE_USE_HD_MIX:-1}
		LOLG_HD_WINE_HD_EXCLUDE=${LOLG_HD_WINE_HD_EXCLUDE:-LOCALLNG.MIX,MOVIES.MIX}
		LOLG_HD_USE_ORIGINAL_MOVIES=${LOLG_HD_USE_ORIGINAL_MOVIES:-1}
		export LOLG_HD_RESOLUTION LOLG_HD_WINE_USE_HD_MIX LOLG_HD_WINE_HD_EXCLUDE LOLG_HD_USE_ORIGINAL_MOVIES
		exec ./RUN_HD_WINE.sh "$@"
		;;
	wine-vulkan|wine-1920-vulkan)
		require_executable ./RUN_HD_WINE.sh
		LOLG_HD_RESOLUTION=1920x1080
		LOLG_HD_USE_DGVOODOO=0
		LOLG_HD_DGVOODOO_FORCE_RESOLUTION=0
		LOLG_HD_USE_LOCAL_DDRAW=0
		LOLG_HD_WINE_RENDERER=${LOLG_HD_WINE_RENDERER:-vulkan}
		LOLG_HD_WINE_DIRECTDRAW_RENDERER=${LOLG_HD_WINE_DIRECTDRAW_RENDERER:-vulkan}
		LOLG_HD_WINE_VERSION=${LOLG_HD_WINE_VERSION:-win95}
		LOLG_HD_USE_DXVK=${LOLG_HD_USE_DXVK:-1}
		LOLG_HD_SETUP_DXVK=${LOLG_HD_SETUP_DXVK:-1}
		LOLG_HD_WINE_WAIT=${LOLG_HD_WINE_WAIT:-0}
		LOLG_HD_LOCK_WINDOW_POSITION=${LOLG_HD_LOCK_WINDOW_POSITION:-0}
		LOLG_HD_RESIZE_GAME_WINDOW_DELAY=${LOLG_HD_RESIZE_GAME_WINDOW_DELAY:-0}
		LOLG_HD_WINE_USE_HD_MIX=${LOLG_HD_WINE_USE_HD_MIX:-1}
		LOLG_HD_WINE_HD_EXCLUDE=${LOLG_HD_WINE_HD_EXCLUDE:-LOCALLNG.MIX,MOVIES.MIX}
		LOLG_HD_USE_ORIGINAL_MOVIES=${LOLG_HD_USE_ORIGINAL_MOVIES:-1}
		export LOLG_HD_RESOLUTION LOLG_HD_USE_DGVOODOO LOLG_HD_DGVOODOO_FORCE_RESOLUTION LOLG_HD_USE_LOCAL_DDRAW
		export LOLG_HD_WINE_RENDERER LOLG_HD_WINE_DIRECTDRAW_RENDERER LOLG_HD_WINE_VERSION LOLG_HD_USE_DXVK LOLG_HD_SETUP_DXVK
		export LOLG_HD_WINE_WAIT LOLG_HD_LOCK_WINDOW_POSITION LOLG_HD_RESIZE_GAME_WINDOW_DELAY
		export LOLG_HD_WINE_USE_HD_MIX LOLG_HD_WINE_HD_EXCLUDE LOLG_HD_USE_ORIGINAL_MOVIES
		exec ./RUN_HD_WINE.sh "$@"
		;;
	wine-hdmix-stable|wine-stable-hdmix|wine-nodgvoodoo-hdmix)
		require_executable ./RUN_HD_WINE.sh
		LOLG_HD_RESOLUTION=${LOLG_HD_RESOLUTION:-1920x1080}
		LOLG_HD_USE_DGVOODOO=0
		LOLG_HD_DGVOODOO_FORCE_RESOLUTION=0
		LOLG_HD_USE_LOCAL_DDRAW=0
		LOLG_HD_WINE_RENDERER=${LOLG_HD_WINE_RENDERER:-opengl}
		LOLG_HD_WINE_DIRECTDRAW_RENDERER=${LOLG_HD_WINE_DIRECTDRAW_RENDERER:-opengl}
		LOLG_HD_WINE_VERSION=${LOLG_HD_WINE_VERSION:-win95}
		LOLG_HD_USE_DXVK=${LOLG_HD_USE_DXVK:-0}
		LOLG_HD_SETUP_DXVK=${LOLG_HD_SETUP_DXVK:-0}
		LOLG_HD_WINE_USE_XRANDR=${LOLG_HD_WINE_USE_XRANDR:-Y}
		LOLG_HD_WINE_USE_XVIDMODE=${LOLG_HD_WINE_USE_XVIDMODE:-N}
		LOLG_HD_WINE_WAIT=${LOLG_HD_WINE_WAIT:-0}
		LOLG_HD_AUTO_RESIZE=${LOLG_HD_AUTO_RESIZE:-0}
		LOLG_HD_RESIZE_GAME_WINDOW=${LOLG_HD_RESIZE_GAME_WINDOW:-0}
		LOLG_HD_LOCK_WINDOW_POSITION=${LOLG_HD_LOCK_WINDOW_POSITION:-0}
		LOLG_HD_RESIZE_GAME_WINDOW_DELAY=${LOLG_HD_RESIZE_GAME_WINDOW_DELAY:-0}
		LOLG_HD_WINE_USE_HD_MIX=1
		LOLG_HD_WINE_HD_EXCLUDE=LOCALLNG.MIX,MOVIES.MIX
		LOLG_HD_USE_ORIGINAL_MOVIES=1
		WINEPREFIX=${WINEPREFIX:-"$BASE_DIR/output/lolg95_hdmix_stable_wine_prefix"}
		export LOLG_HD_RESOLUTION LOLG_HD_USE_DGVOODOO LOLG_HD_DGVOODOO_FORCE_RESOLUTION LOLG_HD_USE_LOCAL_DDRAW
		export LOLG_HD_WINE_RENDERER LOLG_HD_WINE_DIRECTDRAW_RENDERER LOLG_HD_WINE_VERSION LOLG_HD_USE_DXVK LOLG_HD_SETUP_DXVK
		export LOLG_HD_WINE_USE_XRANDR LOLG_HD_WINE_USE_XVIDMODE
		export LOLG_HD_WINE_WAIT LOLG_HD_AUTO_RESIZE LOLG_HD_RESIZE_GAME_WINDOW
		export LOLG_HD_LOCK_WINDOW_POSITION LOLG_HD_RESIZE_GAME_WINDOW_DELAY
		export LOLG_HD_WINE_USE_HD_MIX LOLG_HD_WINE_HD_EXCLUDE LOLG_HD_USE_ORIGINAL_MOVIES
		export WINEPREFIX
		exec ./RUN_HD_WINE.sh --direct "$@"
		;;
	wine-1280-vulkan)
		require_executable ./RUN_HD_WINE.sh
		LOLG_HD_RESOLUTION=1280x1024
		LOLG_HD_USE_DGVOODOO=0
		LOLG_HD_DGVOODOO_FORCE_RESOLUTION=0
		LOLG_HD_USE_LOCAL_DDRAW=0
		LOLG_HD_WINE_RENDERER=${LOLG_HD_WINE_RENDERER:-vulkan}
		LOLG_HD_WINE_DIRECTDRAW_RENDERER=${LOLG_HD_WINE_DIRECTDRAW_RENDERER:-vulkan}
		LOLG_HD_WINE_VERSION=${LOLG_HD_WINE_VERSION:-win95}
		LOLG_HD_USE_DXVK=${LOLG_HD_USE_DXVK:-1}
		LOLG_HD_SETUP_DXVK=${LOLG_HD_SETUP_DXVK:-1}
		LOLG_HD_WINE_WAIT=${LOLG_HD_WINE_WAIT:-0}
		LOLG_HD_LOCK_WINDOW_POSITION=${LOLG_HD_LOCK_WINDOW_POSITION:-0}
		LOLG_HD_RESIZE_GAME_WINDOW_DELAY=${LOLG_HD_RESIZE_GAME_WINDOW_DELAY:-0}
		LOLG_HD_WINE_USE_HD_MIX=${LOLG_HD_WINE_USE_HD_MIX:-1}
		LOLG_HD_WINE_HD_EXCLUDE=${LOLG_HD_WINE_HD_EXCLUDE:-LOCALLNG.MIX,MOVIES.MIX}
		LOLG_HD_USE_ORIGINAL_MOVIES=${LOLG_HD_USE_ORIGINAL_MOVIES:-1}
		export LOLG_HD_RESOLUTION LOLG_HD_USE_DGVOODOO LOLG_HD_DGVOODOO_FORCE_RESOLUTION LOLG_HD_USE_LOCAL_DDRAW
		export LOLG_HD_WINE_RENDERER LOLG_HD_WINE_DIRECTDRAW_RENDERER LOLG_HD_WINE_VERSION LOLG_HD_USE_DXVK LOLG_HD_SETUP_DXVK
		export LOLG_HD_WINE_WAIT LOLG_HD_LOCK_WINDOW_POSITION LOLG_HD_RESIZE_GAME_WINDOW_DELAY
		export LOLG_HD_WINE_USE_HD_MIX LOLG_HD_WINE_HD_EXCLUDE LOLG_HD_USE_ORIGINAL_MOVIES
		exec ./RUN_HD_WINE.sh "$@"
		;;
	wine-gamescope|wine-sans-dgvoodoo|wine-no-dgvoodoo|wine-mieux-dgvoodoo)
		require_executable ./RUN_HD_WINE_GAMESCOPE.sh
		LOLG_HD_GAMESCOPE_RESOLUTION=${LOLG_HD_GAMESCOPE_RESOLUTION:-1920x1080}
		export LOLG_HD_GAMESCOPE_RESOLUTION
		exec ./RUN_HD_WINE_GAMESCOPE.sh "$@"
		;;
	wine-gamescope-1440|wine-no-dgvoodoo-1440|wine-mieux-dgvoodoo-1440)
		require_executable ./RUN_HD_WINE_GAMESCOPE.sh
		LOLG_HD_GAMESCOPE_RESOLUTION=1440x1080
		export LOLG_HD_GAMESCOPE_RESOLUTION
		exec ./RUN_HD_WINE_GAMESCOPE.sh "$@"
		;;
	wine-gamescope-1280|wine-no-dgvoodoo-1280|wine-mieux-dgvoodoo-1280)
		require_executable ./RUN_HD_WINE_GAMESCOPE.sh
		LOLG_HD_GAMESCOPE_RESOLUTION=1280x1024
		export LOLG_HD_GAMESCOPE_RESOLUTION
		exec ./RUN_HD_WINE_GAMESCOPE.sh "$@"
		;;
	wine-locallng-hd|wine-locallng-hd-vulkan|wine-locallng-vulkan|wine-vulkan-locallng|wine-locallng-sidecar|wine-sidecar-locallng)
		require_executable ./RUN_HD_WINE_LOCALLNG_SIDECAR.sh
		LOLG_HD_RESOLUTION=${LOLG_HD_RESOLUTION:-1280x1024}
		LOLG_HD_USE_DGVOODOO=0
		LOLG_HD_USE_LOCAL_DDRAW=0
		LOLG_HD_WINE_RENDERER=${LOLG_HD_WINE_RENDERER:-vulkan}
		LOLG_HD_WINE_DIRECTDRAW_RENDERER=${LOLG_HD_WINE_DIRECTDRAW_RENDERER:-none}
		LOLG_HD_WINE_DLL_OVERRIDES='d3dimm,d3d8=b'
		export LOLG_HD_RESOLUTION LOLG_HD_USE_DGVOODOO LOLG_HD_USE_LOCAL_DDRAW
		export LOLG_HD_WINE_RENDERER LOLG_HD_WINE_DIRECTDRAW_RENDERER LOLG_HD_WINE_DLL_OVERRIDES
		exec ./RUN_HD_WINE_LOCALLNG_SIDECAR.sh "$@"
		;;
		wine-locallng-hd-ddraw|wine-locallng-ddraw)
			require_executable ./RUN_HD_WINE_LOCALLNG_SIDECAR.sh
			LOLG_HD_RESOLUTION=1920x1080
			LOLG_HD_USE_LOCAL_DDRAW=1
			export LOLG_HD_RESOLUTION LOLG_HD_USE_LOCAL_DDRAW
			exec ./RUN_HD_WINE_LOCALLNG_SIDECAR.sh "$@"
			;;
		wine-locallng-hd-1440|wine-1440-locallng-hd|wine-locallng-1440)
			require_executable ./RUN_HD_WINE.sh
			LOLG_HD_RESOLUTION=1440x1080
			LOLG_HD_USE_DGVOODOO=0
			LOLG_HD_DGVOODOO_FORCE_RESOLUTION=0
			LOLG_HD_WINE_RENDERER=${LOLG_HD_WINE_RENDERER:-opengl}
			LOLG_HD_WINE_DIRECTDRAW_RENDERER=${LOLG_HD_WINE_DIRECTDRAW_RENDERER:-gdi}
			LOLG_HD_WINE_WAIT=${LOLG_HD_WINE_WAIT:-0}
			LOLG_HD_LOCK_WINDOW_POSITION=${LOLG_HD_LOCK_WINDOW_POSITION:-0}
			LOLG_HD_WINE_USE_HD_MIX=${LOLG_HD_WINE_USE_HD_MIX:-1}
			LOLG_HD_WINE_HD_EXCLUDE=${LOLG_HD_WINE_HD_EXCLUDE:-LOCALLNG.MIX,MOVIES.MIX}
			LOLG_HD_USE_ORIGINAL_MOVIES=${LOLG_HD_USE_ORIGINAL_MOVIES:-1}
			WINEPREFIX=${WINEPREFIX:-"$BASE_DIR/output/lolg95_dgvoodoo_wine_prefix"}
			export LOLG_HD_RESOLUTION LOLG_HD_USE_DGVOODOO LOLG_HD_DGVOODOO_FORCE_RESOLUTION
			export LOLG_HD_WINE_RENDERER LOLG_HD_WINE_DIRECTDRAW_RENDERER LOLG_HD_WINE_WAIT LOLG_HD_LOCK_WINDOW_POSITION
			export LOLG_HD_WINE_USE_HD_MIX LOLG_HD_WINE_HD_EXCLUDE LOLG_HD_USE_ORIGINAL_MOVIES
			export WINEPREFIX
			exec ./RUN_HD_WINE.sh "$@"
			;;
		wine-locallng-hd-1440-lowmem|wine-1440-lowmem|wine-locallng-1440-lowmem)
			require_executable ./RUN_HD_WINE.sh
			LOLG_HD_RESOLUTION=1440x1080
			LOLG_HD_USE_DGVOODOO=0
			LOLG_HD_DGVOODOO_FORCE_RESOLUTION=0
			LOLG_HD_WINE_RENDERER=${LOLG_HD_WINE_RENDERER:-vulkan}
			LOLG_HD_WINE_DIRECTDRAW_RENDERER=${LOLG_HD_WINE_DIRECTDRAW_RENDERER:-vulkan}
			LOLG_HD_WINE_WAIT=${LOLG_HD_WINE_WAIT:-0}
			LOLG_HD_LOCK_WINDOW_POSITION=${LOLG_HD_LOCK_WINDOW_POSITION:-0}
			LOLG_HD_WINE_USE_HD_MIX=${LOLG_HD_WINE_USE_HD_MIX:-1}
			LOLG_HD_WINE_HD_EXCLUDE=${LOLG_HD_WINE_HD_EXCLUDE:-LOCALLNG.MIX,MOVIES.MIX}
			LOLG_HD_USE_ORIGINAL_MOVIES=${LOLG_HD_USE_ORIGINAL_MOVIES:-1}
			LOLG_HD_GAME_LOWMEM=1
			LOLG_HD_LOW_MEMORY_CONFIG=1
			WINEPREFIX=${WINEPREFIX:-"$BASE_DIR/output/lolg95_dgvoodoo_wine_prefix"}
			export LOLG_HD_RESOLUTION LOLG_HD_USE_DGVOODOO LOLG_HD_DGVOODOO_FORCE_RESOLUTION
			export LOLG_HD_WINE_RENDERER LOLG_HD_WINE_DIRECTDRAW_RENDERER LOLG_HD_WINE_WAIT LOLG_HD_LOCK_WINDOW_POSITION
			export LOLG_HD_WINE_USE_HD_MIX LOLG_HD_WINE_HD_EXCLUDE LOLG_HD_USE_ORIGINAL_MOVIES LOLG_HD_GAME_LOWMEM LOLG_HD_LOW_MEMORY_CONFIG
			export WINEPREFIX
			exec ./RUN_HD_WINE.sh "$@"
			;;
		vqa-contract-status|wine-vqa-contract-status|contract-status)
			print_vqa_contract_status
			;;
		vqa-contract-build-locallng-896-padded|build-locallng-896-padded)
			python3 tools/lolg_vqa_contract_preserving_writer.py \
				--source C/LOLG/LOCALLNG.MIX \
				--entry 2 \
				--source-dir output/locallng_entry2_source_decode_896x560 \
				--width 896 \
				--height 560 \
				-o output/vqa_contract_preserving_writer_locallng_896x560_vqaext_padded_cbpz \
				--adaptive-cbpz \
				--windowed-pointer-lcw \
				--vqa-extended-lcw \
				--pad-cbpz-to-source-budget \
				--progress-every "${LOLG_HD_VQA_BUILD_PROGRESS_EVERY:-50}" || exit 1
			python3 tools/lolg_vqa_lcw_profile.py \
				--case original=C/LOLG/LOCALLNG.MIX,2 \
				--case padded896=output/vqa_contract_preserving_writer_locallng_896x560_vqaext_padded_cbpz/payloads/LOCALLNG/fca4e133.vqa \
				-o output/locallng_vqa_lcw_profile_896_padded_gate_20260708 \
				--fail-on-dialect-gap
			;;
		vqa-contract-build-locallng-1280-padded|build-locallng-1280-padded)
			python3 tools/lolg_vqa_contract_preserving_writer.py \
				--source C/LOLG/LOCALLNG.MIX \
				--entry 2 \
				--source-dir output/vqa_contract_preserving_writer_locallng_1280x1024_adaptive_extlcw/decoded \
				--width 1280 \
				--height 1024 \
				-o output/vqa_contract_preserving_writer_locallng_1280x1024_vqaext_padded_cbpz_from_adaptive_decode \
				--adaptive-cbpz \
				--windowed-pointer-lcw \
				--vqa-extended-lcw \
				--pad-cbpz-to-source-budget \
				--progress-every "${LOLG_HD_VQA_BUILD_PROGRESS_EVERY:-50}" || exit 1
			python3 tools/lolg_vqa_lcw_profile.py \
				--case original=C/LOLG/LOCALLNG.MIX,2 \
				--case padded1280=output/vqa_contract_preserving_writer_locallng_1280x1024_vqaext_padded_cbpz_from_adaptive_decode/payloads/LOCALLNG/fca4e133.vqa \
				-o output/locallng_vqa_lcw_profile_1280_padded_gate_20260708 \
				--fail-on-dialect-gap
			;;
		vqa-contract-build-movies-cbpz-padded|build-movies-cbpz-padded)
			set_vqa_contract_paths
			movies_cbpz_entries=${LOLG_HD_MOVIES_CBPZ_ENTRIES:-0,19,20}
			if [ ! -f "$CONTRACT_MOVIES_MIX" ]; then
				echo "MOVIES.MIX contract source introuvable: $CONTRACT_MOVIES_MIX" >&2
				exit 1
			fi
			python3 tools/lolg_vqa_recompress_lcw_chunks.py \
				--source "$CONTRACT_MOVIES_MIX" \
				--entries "$movies_cbpz_entries" \
				--chunk-ids CBPZ \
				--synthetic-no-room-cbpz-bytes "${LOLG_HD_MOVIES_CBPZ_NOROOM_BYTES:-65536}" \
				-o "$CONTRACT_MOVIES_CBPZ_PADDED_DIR" || exit 1
			for movies_cbpz_entry in $(printf '%s' "$movies_cbpz_entries" | tr ',' ' '); do
				case "$movies_cbpz_entry" in
					''|*[!0-9]*)
						echo "LOLG_HD_MOVIES_CBPZ_ENTRIES doit etre une liste d'entrees numeriques separees par des virgules." >&2
						exit 1
						;;
				esac
				movies_cbpz_entry_pad=$(printf '%04d' "$movies_cbpz_entry")
				python3 tools/lolg_vqa_lcw_profile.py \
					--case original=C/LOLG/MOVIES.MIX,"$movies_cbpz_entry" \
					--case noroom"$movies_cbpz_entry"="$CONTRACT_MOVIES_CBPZ_PADDED_MIX","$movies_cbpz_entry" \
					-o output/movies_entry"$movies_cbpz_entry"_lcw_profile_cbpz_noroom_vqaext_20260708 \
					--fail-on-dialect-gap || exit 1
				python3 tools/lolg_vqa_runtime_compat_audit.py \
					--original C/LOLG/MOVIES.MIX \
					--original-entry "$movies_cbpz_entry" \
					--replacement "$CONTRACT_MOVIES_CBPZ_PADDED_MIX" \
					--replacement-entry "$movies_cbpz_entry" \
					--allow-resolution-change \
					-o output/vqa_runtime_compat_movies_cbpz_noroom_"$movies_cbpz_entry_pad" || exit 1
			done
			;;
		vqa-plan-movies-safe|plan-movies-safe|movies-safe-plan)
			movies_plan_source=${LOLG_HD_MOVIES_SAFE_PLAN_SOURCE:-C/LOLG/MOVIES.MIX}
			movies_plan_width=${LOLG_HD_MOVIES_SAFE_PLAN_WIDTH:-896}
			movies_plan_height=${LOLG_HD_MOVIES_SAFE_PLAN_HEIGHT:-560}
			movies_plan_budget=${LOLG_HD_MOVIES_SAFE_PLAN_BLOCK_BUDGET:-31220}
			movies_plan_output=${LOLG_HD_MOVIES_SAFE_PLAN_OUTPUT:-output/vqa_safe_resolution_plan_movies_896x560_budget31220_20260708}
			movies_plan_expect_entries=${LOLG_HD_MOVIES_SAFE_PLAN_EXPECT_ENTRIES:-}
			movies_plan_expect_target=${LOLG_HD_MOVIES_SAFE_PLAN_EXPECT_TARGET:-}
			if [ ! -f "$movies_plan_source" ]; then
				echo "MOVIES.MIX source introuvable pour plan safe: $movies_plan_source" >&2
				exit 1
			fi
			set -- "$movies_plan_source" \
				--desired-width "$movies_plan_width" \
				--desired-height "$movies_plan_height" \
				--block-budget "$movies_plan_budget" \
				-o "$movies_plan_output"
			if [ -n "$movies_plan_expect_entries" ]; then
				set -- "$@" --expect-entries "$movies_plan_expect_entries"
			fi
			if [ -n "$movies_plan_expect_target" ]; then
				set -- "$@" --expect-target "$movies_plan_expect_target"
			fi
			python3 tools/lolg_vqa_safe_resolution_plan.py "$@"
			;;
		vqa-contract-build-movies-safe|build-movies-safe|movies-safe-build)
			movies_safe_source=${LOLG_HD_MOVIES_SAFE_BUILD_SOURCE:-C/LOLG/MOVIES.MIX}
			movies_safe_entries=${LOLG_HD_MOVIES_SAFE_BUILD_ENTRIES:-0-27}
			movies_safe_width=${LOLG_HD_MOVIES_SAFE_BUILD_WIDTH:-892}
			movies_safe_height=${LOLG_HD_MOVIES_SAFE_BUILD_HEIGHT:-560}
			movies_safe_profiles=${LOLG_HD_MOVIES_SAFE_BUILD_PROFILES:-4000,2048,1024,640,512,480,448,416,384,256,192,128}
			movies_safe_source_root=${LOLG_HD_MOVIES_SAFE_BUILD_SOURCE_ROOT:-output/vqa_contract_batch_sources_movies_safe_892x560}
			movies_safe_output=${LOLG_HD_MOVIES_SAFE_BUILD_OUTPUT:-output/vqa_contract_batch_writer_movies_0000_0027_892x560_safe}
			movies_safe_plan_output=${LOLG_HD_MOVIES_SAFE_PLAN_OUTPUT:-output/vqa_safe_resolution_plan_movies_896x560_budget31220_20260708}
			movies_safe_reuse_roots=${LOLG_HD_MOVIES_SAFE_BUILD_REUSE_ROOTS:-output/vqa_contract_batch_writer_movies_safe_long0_0000_892x560,output/vqa_contract_batch_writer_movies_safe_long1_0001_892x560,output/vqa_contract_batch_writer_movies_safe_long2_0002_892x560,output/vqa_contract_batch_writer_movies_safe_long3_0003_892x560,output/vqa_contract_batch_writer_movies_safe_smoke_0004_892x560,output/vqa_contract_batch_writer_movies_safe_short_0005_0018_892x560,output/vqa_contract_batch_writer_movies_safe_mid_0019_0020_892x560,output/vqa_contract_batch_writer_movies_safe_tail_0021_0027_892x560}
			movies_safe_progress=${LOLG_HD_VQA_BUILD_PROGRESS_EVERY:-50}
			movies_safe_dry_run=0
			if is_dry_run_args "$@"; then
				movies_safe_dry_run=1
			fi
			if [ ! -f "$movies_safe_source" ]; then
				echo "MOVIES.MIX source introuvable pour build safe: $movies_safe_source" >&2
				exit 1
			fi
			set -- tools/lolg_vqa_contract_batch_writer.py \
				--source "$movies_safe_source" \
				--entries "$movies_safe_entries" \
				--width "$movies_safe_width" \
				--height "$movies_safe_height" \
				--profiles "$movies_safe_profiles" \
				--source-root "$movies_safe_source_root" \
				-o "$movies_safe_output" \
				--extended-lcw \
				--windowed-pointer-lcw \
				--vqa-extended-lcw \
				--pad-initial-cbfz \
				--pad-cbpz-to-source-budget \
				--progress-every "$movies_safe_progress"
			if [ -n "$movies_safe_reuse_roots" ]; then
				old_ifs=$IFS
				IFS=,
				for movies_safe_reuse_root in $movies_safe_reuse_roots; do
					IFS=$old_ifs
					if [ -n "$movies_safe_reuse_root" ]; then
						set -- "$@" --reuse-root "$movies_safe_reuse_root"
					fi
					IFS=,
				done
				IFS=$old_ifs
			fi
			if [ "$movies_safe_dry_run" -eq 1 ]; then
				echo "MOVIES safe build: dry-run"
				echo "Plan safe attendu: $movies_safe_plan_output"
				echo "Commande plan:"
				echo "  LOLG_HD_MOVIES_SAFE_PLAN_OUTPUT=$movies_safe_plan_output LOLG_HD_MOVIES_SAFE_PLAN_EXPECT_ENTRIES=28 LOLG_HD_MOVIES_SAFE_PLAN_EXPECT_TARGET=${movies_safe_width}x${movies_safe_height} ./LOLG_HD.sh vqa-plan-movies-safe"
				echo "Commande build:"
				printf '  python3'
				printf ' %s' "$@"
				printf '\n'
				exit 0
			fi
			LOLG_HD_MOVIES_SAFE_PLAN_SOURCE=$movies_safe_source \
			LOLG_HD_MOVIES_SAFE_PLAN_WIDTH=896 \
			LOLG_HD_MOVIES_SAFE_PLAN_HEIGHT=560 \
			LOLG_HD_MOVIES_SAFE_PLAN_BLOCK_BUDGET=31220 \
			LOLG_HD_MOVIES_SAFE_PLAN_EXPECT_ENTRIES=28 \
			LOLG_HD_MOVIES_SAFE_PLAN_EXPECT_TARGET=${movies_safe_width}x${movies_safe_height} \
			LOLG_HD_MOVIES_SAFE_PLAN_OUTPUT=$movies_safe_plan_output \
				./LOLG_HD.sh vqa-plan-movies-safe || exit 1
			python3 "$@"
			;;
		vqa-contract-build-movies-safe-smoke|build-movies-safe-smoke|movies-safe-smoke)
			LOLG_HD_MOVIES_SAFE_BUILD_ENTRIES=${LOLG_HD_MOVIES_SAFE_BUILD_ENTRIES:-4}
			LOLG_HD_MOVIES_SAFE_BUILD_PROFILES=${LOLG_HD_MOVIES_SAFE_BUILD_PROFILES:-4000}
			LOLG_HD_MOVIES_SAFE_BUILD_SOURCE_ROOT=${LOLG_HD_MOVIES_SAFE_BUILD_SOURCE_ROOT:-output/vqa_contract_batch_sources_movies_safe_smoke_892x560}
			LOLG_HD_MOVIES_SAFE_BUILD_OUTPUT=${LOLG_HD_MOVIES_SAFE_BUILD_OUTPUT:-output/vqa_contract_batch_writer_movies_safe_smoke_0004_892x560}
			LOLG_HD_VQA_BUILD_PROGRESS_EVERY=${LOLG_HD_VQA_BUILD_PROGRESS_EVERY:-25}
			export LOLG_HD_MOVIES_SAFE_BUILD_ENTRIES LOLG_HD_MOVIES_SAFE_BUILD_PROFILES
			export LOLG_HD_MOVIES_SAFE_BUILD_SOURCE_ROOT LOLG_HD_MOVIES_SAFE_BUILD_OUTPUT
			export LOLG_HD_VQA_BUILD_PROGRESS_EVERY
			exec ./LOLG_HD.sh vqa-contract-build-movies-safe "$@"
			;;
		vqa-contract-build-movies-safe-long0|build-movies-safe-long0|movies-safe-long0)
			LOLG_HD_MOVIES_SAFE_BUILD_ENTRIES=${LOLG_HD_MOVIES_SAFE_BUILD_ENTRIES:-0}
			LOLG_HD_MOVIES_SAFE_BUILD_PROFILES=${LOLG_HD_MOVIES_SAFE_BUILD_PROFILES:-4000}
			LOLG_HD_MOVIES_SAFE_BUILD_SOURCE_ROOT=${LOLG_HD_MOVIES_SAFE_BUILD_SOURCE_ROOT:-output/vqa_contract_batch_sources_movies_safe_long0_892x560}
			LOLG_HD_MOVIES_SAFE_BUILD_OUTPUT=${LOLG_HD_MOVIES_SAFE_BUILD_OUTPUT:-output/vqa_contract_batch_writer_movies_safe_long0_0000_892x560}
			LOLG_HD_VQA_BUILD_PROGRESS_EVERY=${LOLG_HD_VQA_BUILD_PROGRESS_EVERY:-100}
			export LOLG_HD_MOVIES_SAFE_BUILD_ENTRIES LOLG_HD_MOVIES_SAFE_BUILD_PROFILES
			export LOLG_HD_MOVIES_SAFE_BUILD_SOURCE_ROOT LOLG_HD_MOVIES_SAFE_BUILD_OUTPUT
			export LOLG_HD_VQA_BUILD_PROGRESS_EVERY
			exec ./LOLG_HD.sh vqa-contract-build-movies-safe "$@"
			;;
		vqa-contract-build-movies-safe-long1|build-movies-safe-long1|movies-safe-long1)
			LOLG_HD_MOVIES_SAFE_BUILD_ENTRIES=${LOLG_HD_MOVIES_SAFE_BUILD_ENTRIES:-1}
			LOLG_HD_MOVIES_SAFE_BUILD_PROFILES=${LOLG_HD_MOVIES_SAFE_BUILD_PROFILES:-4000}
			LOLG_HD_MOVIES_SAFE_BUILD_SOURCE_ROOT=${LOLG_HD_MOVIES_SAFE_BUILD_SOURCE_ROOT:-output/vqa_contract_batch_sources_movies_safe_long1_892x560}
			LOLG_HD_MOVIES_SAFE_BUILD_OUTPUT=${LOLG_HD_MOVIES_SAFE_BUILD_OUTPUT:-output/vqa_contract_batch_writer_movies_safe_long1_0001_892x560}
			LOLG_HD_VQA_BUILD_PROGRESS_EVERY=${LOLG_HD_VQA_BUILD_PROGRESS_EVERY:-50}
			export LOLG_HD_MOVIES_SAFE_BUILD_ENTRIES LOLG_HD_MOVIES_SAFE_BUILD_PROFILES
			export LOLG_HD_MOVIES_SAFE_BUILD_SOURCE_ROOT LOLG_HD_MOVIES_SAFE_BUILD_OUTPUT
			export LOLG_HD_VQA_BUILD_PROGRESS_EVERY
			exec ./LOLG_HD.sh vqa-contract-build-movies-safe "$@"
			;;
		vqa-contract-build-movies-safe-long2|build-movies-safe-long2|movies-safe-long2)
			LOLG_HD_MOVIES_SAFE_BUILD_ENTRIES=${LOLG_HD_MOVIES_SAFE_BUILD_ENTRIES:-2}
			LOLG_HD_MOVIES_SAFE_BUILD_PROFILES=${LOLG_HD_MOVIES_SAFE_BUILD_PROFILES:-4000}
			LOLG_HD_MOVIES_SAFE_BUILD_SOURCE_ROOT=${LOLG_HD_MOVIES_SAFE_BUILD_SOURCE_ROOT:-output/vqa_contract_batch_sources_movies_safe_long2_892x560}
			LOLG_HD_MOVIES_SAFE_BUILD_OUTPUT=${LOLG_HD_MOVIES_SAFE_BUILD_OUTPUT:-output/vqa_contract_batch_writer_movies_safe_long2_0002_892x560}
			LOLG_HD_VQA_BUILD_PROGRESS_EVERY=${LOLG_HD_VQA_BUILD_PROGRESS_EVERY:-100}
			export LOLG_HD_MOVIES_SAFE_BUILD_ENTRIES LOLG_HD_MOVIES_SAFE_BUILD_PROFILES
			export LOLG_HD_MOVIES_SAFE_BUILD_SOURCE_ROOT LOLG_HD_MOVIES_SAFE_BUILD_OUTPUT
			export LOLG_HD_VQA_BUILD_PROGRESS_EVERY
			exec ./LOLG_HD.sh vqa-contract-build-movies-safe "$@"
			;;
		vqa-contract-build-movies-safe-long3|build-movies-safe-long3|movies-safe-long3)
			LOLG_HD_MOVIES_SAFE_BUILD_ENTRIES=${LOLG_HD_MOVIES_SAFE_BUILD_ENTRIES:-3}
			LOLG_HD_MOVIES_SAFE_BUILD_PROFILES=${LOLG_HD_MOVIES_SAFE_BUILD_PROFILES:-4000}
			LOLG_HD_MOVIES_SAFE_BUILD_SOURCE_ROOT=${LOLG_HD_MOVIES_SAFE_BUILD_SOURCE_ROOT:-output/vqa_contract_batch_sources_movies_safe_long3_892x560}
			LOLG_HD_MOVIES_SAFE_BUILD_OUTPUT=${LOLG_HD_MOVIES_SAFE_BUILD_OUTPUT:-output/vqa_contract_batch_writer_movies_safe_long3_0003_892x560}
			LOLG_HD_VQA_BUILD_PROGRESS_EVERY=${LOLG_HD_VQA_BUILD_PROGRESS_EVERY:-100}
			export LOLG_HD_MOVIES_SAFE_BUILD_ENTRIES LOLG_HD_MOVIES_SAFE_BUILD_PROFILES
			export LOLG_HD_MOVIES_SAFE_BUILD_SOURCE_ROOT LOLG_HD_MOVIES_SAFE_BUILD_OUTPUT
			export LOLG_HD_VQA_BUILD_PROGRESS_EVERY
			exec ./LOLG_HD.sh vqa-contract-build-movies-safe "$@"
			;;
		vqa-contract-build-movies-safe-short|build-movies-safe-short|movies-safe-short)
			LOLG_HD_MOVIES_SAFE_BUILD_ENTRIES=${LOLG_HD_MOVIES_SAFE_BUILD_ENTRIES:-5-18}
			LOLG_HD_MOVIES_SAFE_BUILD_PROFILES=${LOLG_HD_MOVIES_SAFE_BUILD_PROFILES:-4000}
			LOLG_HD_MOVIES_SAFE_BUILD_SOURCE_ROOT=${LOLG_HD_MOVIES_SAFE_BUILD_SOURCE_ROOT:-output/vqa_contract_batch_sources_movies_safe_short_892x560}
			LOLG_HD_MOVIES_SAFE_BUILD_OUTPUT=${LOLG_HD_MOVIES_SAFE_BUILD_OUTPUT:-output/vqa_contract_batch_writer_movies_safe_short_0005_0018_892x560}
			LOLG_HD_VQA_BUILD_PROGRESS_EVERY=${LOLG_HD_VQA_BUILD_PROGRESS_EVERY:-25}
			export LOLG_HD_MOVIES_SAFE_BUILD_ENTRIES LOLG_HD_MOVIES_SAFE_BUILD_PROFILES
			export LOLG_HD_MOVIES_SAFE_BUILD_SOURCE_ROOT LOLG_HD_MOVIES_SAFE_BUILD_OUTPUT
			export LOLG_HD_VQA_BUILD_PROGRESS_EVERY
			exec ./LOLG_HD.sh vqa-contract-build-movies-safe "$@"
			;;
		vqa-contract-build-movies-safe-mid|build-movies-safe-mid|movies-safe-mid)
			LOLG_HD_MOVIES_SAFE_BUILD_ENTRIES=${LOLG_HD_MOVIES_SAFE_BUILD_ENTRIES:-19-20}
			LOLG_HD_MOVIES_SAFE_BUILD_PROFILES=${LOLG_HD_MOVIES_SAFE_BUILD_PROFILES:-4000}
			LOLG_HD_MOVIES_SAFE_BUILD_SOURCE_ROOT=${LOLG_HD_MOVIES_SAFE_BUILD_SOURCE_ROOT:-output/vqa_contract_batch_sources_movies_safe_mid_892x560}
			LOLG_HD_MOVIES_SAFE_BUILD_OUTPUT=${LOLG_HD_MOVIES_SAFE_BUILD_OUTPUT:-output/vqa_contract_batch_writer_movies_safe_mid_0019_0020_892x560}
			LOLG_HD_VQA_BUILD_PROGRESS_EVERY=${LOLG_HD_VQA_BUILD_PROGRESS_EVERY:-50}
			export LOLG_HD_MOVIES_SAFE_BUILD_ENTRIES LOLG_HD_MOVIES_SAFE_BUILD_PROFILES
			export LOLG_HD_MOVIES_SAFE_BUILD_SOURCE_ROOT LOLG_HD_MOVIES_SAFE_BUILD_OUTPUT
			export LOLG_HD_VQA_BUILD_PROGRESS_EVERY
			exec ./LOLG_HD.sh vqa-contract-build-movies-safe "$@"
			;;
		vqa-contract-build-movies-safe-tail|build-movies-safe-tail|movies-safe-tail)
			LOLG_HD_MOVIES_SAFE_BUILD_ENTRIES=${LOLG_HD_MOVIES_SAFE_BUILD_ENTRIES:-21-27}
			LOLG_HD_MOVIES_SAFE_BUILD_PROFILES=${LOLG_HD_MOVIES_SAFE_BUILD_PROFILES:-4000}
			LOLG_HD_MOVIES_SAFE_BUILD_SOURCE_ROOT=${LOLG_HD_MOVIES_SAFE_BUILD_SOURCE_ROOT:-output/vqa_contract_batch_sources_movies_safe_tail_892x560}
			LOLG_HD_MOVIES_SAFE_BUILD_OUTPUT=${LOLG_HD_MOVIES_SAFE_BUILD_OUTPUT:-output/vqa_contract_batch_writer_movies_safe_tail_0021_0027_892x560}
			LOLG_HD_VQA_BUILD_PROGRESS_EVERY=${LOLG_HD_VQA_BUILD_PROGRESS_EVERY:-25}
			export LOLG_HD_MOVIES_SAFE_BUILD_ENTRIES LOLG_HD_MOVIES_SAFE_BUILD_PROFILES
			export LOLG_HD_MOVIES_SAFE_BUILD_SOURCE_ROOT LOLG_HD_MOVIES_SAFE_BUILD_OUTPUT
			export LOLG_HD_VQA_BUILD_PROGRESS_EVERY
			exec ./LOLG_HD.sh vqa-contract-build-movies-safe "$@"
			;;
		wine-vqa-contract-locallng-896-padded|wine-locallng-contract-896-padded|wine-vqa-safe-locallng-896-padded)
			require_executable ./RUN_HD_WINE.sh
			set_vqa_contract_paths
			if [ ! -f "$CONTRACT_LOCALLNG_896_PADDED_MIX" ]; then
				echo "MIX LOCALLNG 896 padde introuvable: $CONTRACT_LOCALLNG_896_PADDED_MIX" >&2
				echo "Regenerer d'abord avec tools/lolg_vqa_contract_preserving_writer.py --vqa-extended-lcw --pad-cbpz-to-source-budget" >&2
				exit 1
			fi
			require_vqa_contract_pass "$CONTRACT_LOCALLNG_896_PADDED_DIR/summary.csv" "LOCALLNG.MIX 896 padded"
			require_vqa_contract_pass "$CONTRACT_LOCALLNG_896_PADDED_DIR/runtime_compat/summary.csv" "LOCALLNG.MIX 896 padded runtime"
			require_vqa_contract_runtime_override "wine-vqa-contract-locallng-896-padded" "$@"
			LOLG_HD_RESOLUTION=1920x1080
			LOLG_HD_USE_DGVOODOO=0
			LOLG_HD_DGVOODOO_FORCE_RESOLUTION=0
			LOLG_HD_WINE_RENDERER=${LOLG_HD_WINE_RENDERER:-vulkan}
			LOLG_HD_WINE_DIRECTDRAW_RENDERER=${LOLG_HD_WINE_DIRECTDRAW_RENDERER:-vulkan}
			LOLG_HD_WINE_VERSION=${LOLG_HD_WINE_VERSION:-win95}
			LOLG_HD_USE_DXVK=${LOLG_HD_USE_DXVK:-1}
			LOLG_HD_SETUP_DXVK=${LOLG_HD_SETUP_DXVK:-1}
			LOLG_HD_WINE_WAIT=0
			LOLG_HD_LOCK_WINDOW_POSITION=${LOLG_HD_LOCK_WINDOW_POSITION:-0}
			LOLG_HD_RESIZE_GAME_WINDOW_DELAY=${LOLG_HD_RESIZE_GAME_WINDOW_DELAY:-0}
			LOLG_HD_WINE_USE_HD_MIX=0
			LOLG_HD_WINE_HD_EXCLUDE=LOCALLNG.MIX,MOVIES.MIX
			LOLG_HD_WINE_EXTRA_MIX_DIR="$CONTRACT_LOCALLNG_896_PADDED_DIR/mix"
			if [ "$LOLG_HD_USE_DXVK" -eq 1 ]; then
				LOLG_HD_WINE_DLL_OVERRIDES=${LOLG_HD_WINE_DLL_OVERRIDES:-'ddraw,d3dimm=b;d3d8,d3d9,dxgi,d3d10,d3d10_1,d3d10core,d3d11=n,b'}
			else
				LOLG_HD_WINE_DLL_OVERRIDES=${LOLG_HD_WINE_DLL_OVERRIDES:-'ddraw,d3dimm,d3d8=b'}
			fi
			LOLG_HD_WINE_EXTRA_MIX_NOTE="diagnostic LOCALLNG.MIX 896x560 VQA LCW commun + CBPZ padde; MOVIES original"
			LOLG_HD_WINE_MOVIES_LABEL="original"
			LOLG_HD_USE_ORIGINAL_MOVIES=1
			LOLG_HD_ALLOW_CRITICAL_HD_MIX=1
			LOLG_HD_WINE_RUNTIME_ROOT=${LOLG_HD_WINE_RUNTIME_ROOT:-"$BASE_DIR/output/lolg95_vqa_contract_runtime"}
			WINEPREFIX=${WINEPREFIX:-"$BASE_DIR/output/lolg95_vqa_contract_wine_prefix"}
			export LOLG_HD_RESOLUTION LOLG_HD_USE_DGVOODOO LOLG_HD_DGVOODOO_FORCE_RESOLUTION
			export LOLG_HD_WINE_RENDERER LOLG_HD_WINE_DIRECTDRAW_RENDERER LOLG_HD_WINE_VERSION LOLG_HD_USE_DXVK LOLG_HD_SETUP_DXVK
			export LOLG_HD_WINE_DLL_OVERRIDES LOLG_HD_WINE_WAIT LOLG_HD_LOCK_WINDOW_POSITION LOLG_HD_RESIZE_GAME_WINDOW_DELAY
			export LOLG_HD_WINE_USE_HD_MIX LOLG_HD_WINE_HD_EXCLUDE LOLG_HD_WINE_EXTRA_MIX_DIR
			export LOLG_HD_WINE_EXTRA_MIX_NOTE LOLG_HD_WINE_MOVIES_LABEL
			export LOLG_HD_USE_ORIGINAL_MOVIES LOLG_HD_ALLOW_CRITICAL_HD_MIX LOLG_HD_WINE_RUNTIME_ROOT WINEPREFIX
			exec ./RUN_HD_WINE.sh "$@"
			;;
		wine-vqa-contract-locallng|wine-locallng-contract|wine-vqa-safe-locallng)
			require_executable ./RUN_HD_WINE.sh
			set_vqa_contract_paths
			if [ ! -f "$CONTRACT_LOCALLNG_MIX" ]; then
				echo "MIX LOCALLNG contract-preserving introuvable: $CONTRACT_LOCALLNG_MIX" >&2
				echo "Regenerer d'abord LOCALLNG avec tools/lolg_vqa_contract_preserving_writer.py" >&2
				exit 1
			fi
			require_vqa_contract_pass "$CONTRACT_LOCALLNG_DIR/summary.csv" "LOCALLNG.MIX"
			require_vqa_contract_pass "$CONTRACT_LOCALLNG_DIR/runtime_compat/summary.csv" "LOCALLNG.MIX runtime"
			require_vqa_contract_runtime_override "wine-vqa-contract-locallng" "$@"
			LOLG_HD_RESOLUTION=1920x1080
			LOLG_HD_USE_DGVOODOO=0
			LOLG_HD_DGVOODOO_FORCE_RESOLUTION=0
			LOLG_HD_WINE_RENDERER=${LOLG_HD_WINE_RENDERER:-vulkan}
			LOLG_HD_WINE_DIRECTDRAW_RENDERER=${LOLG_HD_WINE_DIRECTDRAW_RENDERER:-vulkan}
			LOLG_HD_WINE_VERSION=${LOLG_HD_WINE_VERSION:-win95}
			LOLG_HD_USE_DXVK=${LOLG_HD_USE_DXVK:-1}
			LOLG_HD_SETUP_DXVK=${LOLG_HD_SETUP_DXVK:-1}
			LOLG_HD_WINE_WAIT=0
			LOLG_HD_LOCK_WINDOW_POSITION=${LOLG_HD_LOCK_WINDOW_POSITION:-0}
			LOLG_HD_RESIZE_GAME_WINDOW_DELAY=${LOLG_HD_RESIZE_GAME_WINDOW_DELAY:-0}
			LOLG_HD_WINE_USE_HD_MIX=0
			LOLG_HD_WINE_HD_EXCLUDE=LOCALLNG.MIX,MOVIES.MIX
			LOLG_HD_WINE_EXTRA_MIX_DIR="$CONTRACT_LOCALLNG_DIR/mix"
			if [ "$LOLG_HD_USE_DXVK" -eq 1 ]; then
				LOLG_HD_WINE_DLL_OVERRIDES=${LOLG_HD_WINE_DLL_OVERRIDES:-'ddraw,d3dimm=b;d3d8,d3d9,dxgi,d3d10,d3d10_1,d3d10core,d3d11=n,b'}
			else
				LOLG_HD_WINE_DLL_OVERRIDES=${LOLG_HD_WINE_DLL_OVERRIDES:-'ddraw,d3dimm,d3d8=b'}
			fi
			LOLG_HD_WINE_EXTRA_MIX_NOTE="lanceur 1920x1080 sans dgVoodoo avec LOCALLNG.MIX diagnostic: $CONTRACT_LOCALLNG_MIX; MOVIES original"
			LOLG_HD_WINE_MOVIES_LABEL="original"
			LOLG_HD_USE_ORIGINAL_MOVIES=1
			LOLG_HD_ALLOW_CRITICAL_HD_MIX=1
			LOLG_HD_WINE_RUNTIME_ROOT=${LOLG_HD_WINE_RUNTIME_ROOT:-"$BASE_DIR/output/lolg95_vqa_contract_runtime"}
			WINEPREFIX=${WINEPREFIX:-"$BASE_DIR/output/lolg95_vqa_contract_wine_prefix"}
			export LOLG_HD_RESOLUTION LOLG_HD_USE_DGVOODOO LOLG_HD_DGVOODOO_FORCE_RESOLUTION
			export LOLG_HD_WINE_RENDERER LOLG_HD_WINE_DIRECTDRAW_RENDERER LOLG_HD_WINE_VERSION LOLG_HD_USE_DXVK LOLG_HD_SETUP_DXVK
			export LOLG_HD_WINE_DLL_OVERRIDES LOLG_HD_WINE_WAIT LOLG_HD_LOCK_WINDOW_POSITION LOLG_HD_RESIZE_GAME_WINDOW_DELAY
			export LOLG_HD_WINE_USE_HD_MIX LOLG_HD_WINE_HD_EXCLUDE LOLG_HD_WINE_EXTRA_MIX_DIR
			export LOLG_HD_WINE_EXTRA_MIX_NOTE LOLG_HD_WINE_MOVIES_LABEL
			export LOLG_HD_USE_ORIGINAL_MOVIES LOLG_HD_ALLOW_CRITICAL_HD_MIX LOLG_HD_WINE_RUNTIME_ROOT WINEPREFIX
			exec ./RUN_HD_WINE.sh "$@"
			;;
		wine-vqa-contract-movies-noroom|wine-vqa-contract-noroom|wine-locallng-movies-noroom)
			set_vqa_contract_paths
			if [ ! -f "$CONTRACT_MOVIES_CBPZ_PADDED_MIX" ]; then
				echo "MIX MOVIES CBPZ no_room introuvable: $CONTRACT_MOVIES_CBPZ_PADDED_MIX" >&2
				echo "Regenerer d'abord avec ./LOLG_HD.sh vqa-contract-build-movies-cbpz-padded" >&2
				exit 1
			fi
			LOLG_HD_CONTRACT_MOVIES_MIX="$CONTRACT_MOVIES_CBPZ_PADDED_MIX"
			LOLG_HD_CONTRACT_MIX_DIR="$BASE_DIR/output/vqa_contract_pair_1280x1024_movies_noroom_runtime"
			LOLG_HD_WINE_EXTRA_MIX_NOTE="lanceur 1920x1080 sans dgVoodoo avec LOCALLNG.MIX 1280 padde et MOVIES.MIX 1280 CBPZ no_room"
			LOLG_HD_WINE_MOVIES_LABEL="contract-preserving HD 1280 + CBPZ no_room sur entrees 0/19/20"
			export LOLG_HD_CONTRACT_MOVIES_MIX LOLG_HD_CONTRACT_MIX_DIR
			export LOLG_HD_WINE_EXTRA_MIX_NOTE LOLG_HD_WINE_MOVIES_LABEL
			exec ./LOLG_HD.sh wine-vqa-contract "$@"
			;;
		wine-vqa-contract-movies-noroom-only|wine-vqa-contract-movies-only|wine-movies-noroom-only)
			require_executable ./RUN_HD_WINE.sh
			set_vqa_contract_paths
			movies_only_dir="${LOLG_HD_CONTRACT_MOVIES_ONLY_DIR:-$CONTRACT_MOVIES_CBPZ_PADDED_DIR/mix}"
			movies_only_mix="${LOLG_HD_CONTRACT_MOVIES_ONLY_MIX:-$movies_only_dir/MOVIES.MIX}"
			if [ ! -f "$movies_only_mix" ]; then
				echo "MIX MOVIES diagnostic introuvable: $movies_only_mix" >&2
				echo "Regenerer d'abord avec ./LOLG_HD.sh vqa-contract-build-movies-cbpz-padded ou fournir LOLG_HD_CONTRACT_MOVIES_ONLY_DIR." >&2
				exit 1
			fi
			if [ "$movies_only_mix" = "$CONTRACT_MOVIES_CBPZ_PADDED_MIX" ]; then
				require_vqa_contract_pass "$CONTRACT_MOVIES_CBPZ_PADDED_DIR/summary.csv" "MOVIES.MIX CBPZ no_room"
				require_lcw_dialect_pass "$CONTRACT_MOVIES_LCW_DIALECT_CBPZ_0" "MOVIES.MIX entry 0 CBPZ no_room"
				require_lcw_dialect_pass "$CONTRACT_MOVIES_LCW_DIALECT_CBPZ_19" "MOVIES.MIX entry 19 CBPZ no_room"
				require_lcw_dialect_pass "$CONTRACT_MOVIES_LCW_DIALECT_CBPZ_20" "MOVIES.MIX entry 20 CBPZ no_room"
				require_vqa_contract_pass "$CONTRACT_MOVIES_RUNTIME_CBPZ_0" "MOVIES.MIX entry 0 CBPZ no_room runtime"
				require_vqa_contract_pass "$CONTRACT_MOVIES_RUNTIME_CBPZ_19" "MOVIES.MIX entry 19 CBPZ no_room runtime"
				require_vqa_contract_pass "$CONTRACT_MOVIES_RUNTIME_CBPZ_20" "MOVIES.MIX entry 20 CBPZ no_room runtime"
				movies_only_note="lanceur 1920x1080 sans dgVoodoo avec LOCALLNG.MIX original et MOVIES.MIX 1280 CBPZ no_room seul"
				movies_only_label="contract-preserving HD 1280 + CBPZ no_room seul, LOCALLNG original"
			else
				movies_only_dir=$(dirname "$movies_only_mix")
				movies_only_note="lanceur 1920x1080 sans dgVoodoo avec LOCALLNG.MIX original et MOVIES.MIX diagnostic: $movies_only_mix"
				movies_only_label="diagnostic MOVIES.MIX custom, LOCALLNG original"
			fi
			require_vqa_contract_runtime_override "wine-vqa-contract-movies-noroom-only" "$@"
			LOLG_HD_RESOLUTION=1920x1080
			LOLG_HD_USE_DGVOODOO=0
			LOLG_HD_DGVOODOO_FORCE_RESOLUTION=0
			LOLG_HD_WINE_RENDERER=${LOLG_HD_WINE_RENDERER:-vulkan}
			LOLG_HD_WINE_DIRECTDRAW_RENDERER=${LOLG_HD_WINE_DIRECTDRAW_RENDERER:-vulkan}
			LOLG_HD_WINE_VERSION=${LOLG_HD_WINE_VERSION:-win95}
			LOLG_HD_USE_DXVK=${LOLG_HD_USE_DXVK:-1}
			LOLG_HD_SETUP_DXVK=${LOLG_HD_SETUP_DXVK:-1}
			LOLG_HD_WINE_WAIT=0
			LOLG_HD_LOCK_WINDOW_POSITION=${LOLG_HD_LOCK_WINDOW_POSITION:-0}
			LOLG_HD_RESIZE_GAME_WINDOW_DELAY=${LOLG_HD_RESIZE_GAME_WINDOW_DELAY:-0}
			LOLG_HD_WINE_USE_HD_MIX=0
			LOLG_HD_WINE_HD_EXCLUDE=LOCALLNG.MIX,MOVIES.MIX
			LOLG_HD_WINE_EXTRA_MIX_DIR="$movies_only_dir"
			if [ "$LOLG_HD_USE_DXVK" -eq 1 ]; then
				LOLG_HD_WINE_DLL_OVERRIDES=${LOLG_HD_WINE_DLL_OVERRIDES:-'ddraw,d3dimm=b;d3d8,d3d9,dxgi,d3d10,d3d10_1,d3d10core,d3d11=n,b'}
			else
				LOLG_HD_WINE_DLL_OVERRIDES=${LOLG_HD_WINE_DLL_OVERRIDES:-'ddraw,d3dimm,d3d8=b'}
			fi
			LOLG_HD_WINE_EXTRA_MIX_NOTE="$movies_only_note"
			LOLG_HD_WINE_MOVIES_LABEL="$movies_only_label"
			LOLG_HD_USE_ORIGINAL_MOVIES=0
			LOLG_HD_ALLOW_CRITICAL_HD_MIX=1
			LOLG_HD_WINE_RUNTIME_ROOT=${LOLG_HD_WINE_RUNTIME_ROOT:-"$BASE_DIR/output/lolg95_vqa_contract_runtime"}
			WINEPREFIX=${WINEPREFIX:-"$BASE_DIR/output/lolg95_vqa_contract_wine_prefix"}
			export LOLG_HD_RESOLUTION LOLG_HD_USE_DGVOODOO LOLG_HD_DGVOODOO_FORCE_RESOLUTION
			export LOLG_HD_WINE_RENDERER LOLG_HD_WINE_DIRECTDRAW_RENDERER LOLG_HD_WINE_VERSION LOLG_HD_USE_DXVK LOLG_HD_SETUP_DXVK
			export LOLG_HD_WINE_DLL_OVERRIDES LOLG_HD_WINE_WAIT LOLG_HD_LOCK_WINDOW_POSITION LOLG_HD_RESIZE_GAME_WINDOW_DELAY
			export LOLG_HD_WINE_USE_HD_MIX LOLG_HD_WINE_HD_EXCLUDE LOLG_HD_WINE_EXTRA_MIX_DIR
			export LOLG_HD_WINE_EXTRA_MIX_NOTE LOLG_HD_WINE_MOVIES_LABEL
			export LOLG_HD_USE_ORIGINAL_MOVIES LOLG_HD_ALLOW_CRITICAL_HD_MIX LOLG_HD_WINE_RUNTIME_ROOT WINEPREFIX
			exec ./RUN_HD_WINE.sh "$@"
			;;
		wine-vqa-contract-custom-pair|wine-vqa-custom-pair|wine-locallng-movies-custom)
			require_executable ./RUN_HD_WINE.sh
			custom_locallng_dir="${LOLG_HD_CONTRACT_PAIR_LOCALLNG_DIR:-$BASE_DIR/output/vqa_contract_locallng_0002_1024x640_rewrite_20260708}"
			custom_movies_dir="${LOLG_HD_CONTRACT_PAIR_MOVIES_DIR:-$BASE_DIR/output/vqa_contract_movies_0004_892x560_rewrite_20260708}"
			custom_pair_dir="${LOLG_HD_CONTRACT_PAIR_DIR:-$BASE_DIR/output/vqa_contract_pair_locallng1024_movies892_runtime}"
			custom_locallng_mix="${LOLG_HD_CONTRACT_PAIR_LOCALLNG_MIX:-$custom_locallng_dir/mix/LOCALLNG.MIX}"
			custom_movies_mix="${LOLG_HD_CONTRACT_PAIR_MOVIES_MIX:-$custom_movies_dir/mix/MOVIES.MIX}"
			if [ ! -f "$custom_locallng_mix" ]; then
				echo "MIX LOCALLNG custom introuvable: $custom_locallng_mix" >&2
				exit 1
			fi
			if [ ! -f "$custom_movies_mix" ]; then
				echo "MIX MOVIES custom introuvable: $custom_movies_mix" >&2
				exit 1
			fi
			require_vqa_contract_pass "$custom_locallng_dir/summary.csv" "LOCALLNG.MIX custom pair"
			require_vqa_contract_pass "$custom_locallng_dir/runtime_compat/summary.csv" "LOCALLNG.MIX custom pair runtime"
			require_vqa_contract_pass "$custom_movies_dir/summary.csv" "MOVIES.MIX custom pair"
			require_vqa_contract_pass "$custom_movies_dir/runtime_compat/summary.csv" "MOVIES.MIX custom pair runtime"
			ensure_vqa_contract_pair_dir "$custom_pair_dir" "$custom_locallng_mix" "$custom_movies_mix"
			require_vqa_contract_runtime_override "wine-vqa-contract-custom-pair" "$@"
			LOLG_HD_RESOLUTION=1920x1080
			LOLG_HD_USE_DGVOODOO=0
			LOLG_HD_DGVOODOO_FORCE_RESOLUTION=0
			LOLG_HD_WINE_RENDERER=${LOLG_HD_WINE_RENDERER:-vulkan}
			LOLG_HD_WINE_DIRECTDRAW_RENDERER=${LOLG_HD_WINE_DIRECTDRAW_RENDERER:-vulkan}
			LOLG_HD_WINE_VERSION=${LOLG_HD_WINE_VERSION:-win95}
			LOLG_HD_USE_DXVK=${LOLG_HD_USE_DXVK:-1}
			LOLG_HD_SETUP_DXVK=${LOLG_HD_SETUP_DXVK:-1}
			LOLG_HD_WINE_WAIT=0
			LOLG_HD_LOCK_WINDOW_POSITION=${LOLG_HD_LOCK_WINDOW_POSITION:-0}
			LOLG_HD_RESIZE_GAME_WINDOW_DELAY=${LOLG_HD_RESIZE_GAME_WINDOW_DELAY:-0}
			LOLG_HD_WINE_USE_HD_MIX=0
			LOLG_HD_WINE_HD_EXCLUDE=LOCALLNG.MIX,MOVIES.MIX
			LOLG_HD_WINE_EXTRA_MIX_DIR=$custom_pair_dir
			if [ "$LOLG_HD_USE_DXVK" -eq 1 ]; then
				LOLG_HD_WINE_DLL_OVERRIDES=${LOLG_HD_WINE_DLL_OVERRIDES:-'ddraw,d3dimm=b;d3d8,d3d9,dxgi,d3d10,d3d10_1,d3d10core,d3d11=n,b'}
			else
				LOLG_HD_WINE_DLL_OVERRIDES=${LOLG_HD_WINE_DLL_OVERRIDES:-'ddraw,d3dimm,d3d8=b'}
			fi
			LOLG_HD_WINE_EXTRA_MIX_NOTE=${LOLG_HD_WINE_EXTRA_MIX_NOTE:-"lanceur 1920x1080 sans dgVoodoo avec LOCALLNG.MIX 1024x640 + MOVIES.MIX entree 4 892x560"}
			LOLG_HD_WINE_MOVIES_LABEL=${LOLG_HD_WINE_MOVIES_LABEL:-"MOVIES.MIX custom sous seuil entree 4, LOCALLNG custom 1024x640"}
			LOLG_HD_USE_ORIGINAL_MOVIES=0
			LOLG_HD_ALLOW_CRITICAL_HD_MIX=1
			LOLG_HD_WINE_RUNTIME_ROOT=${LOLG_HD_WINE_RUNTIME_ROOT:-"$BASE_DIR/output/lolg95_vqa_contract_runtime"}
			WINEPREFIX=${WINEPREFIX:-"$BASE_DIR/output/lolg95_vqa_contract_wine_prefix"}
			export LOLG_HD_RESOLUTION LOLG_HD_USE_DGVOODOO LOLG_HD_DGVOODOO_FORCE_RESOLUTION
			export LOLG_HD_WINE_RENDERER LOLG_HD_WINE_DIRECTDRAW_RENDERER LOLG_HD_WINE_VERSION LOLG_HD_USE_DXVK LOLG_HD_SETUP_DXVK
			export LOLG_HD_WINE_DLL_OVERRIDES LOLG_HD_WINE_WAIT LOLG_HD_LOCK_WINDOW_POSITION LOLG_HD_RESIZE_GAME_WINDOW_DELAY
			export LOLG_HD_WINE_USE_HD_MIX LOLG_HD_WINE_HD_EXCLUDE LOLG_HD_WINE_EXTRA_MIX_DIR
			export LOLG_HD_WINE_EXTRA_MIX_NOTE LOLG_HD_WINE_MOVIES_LABEL
			export LOLG_HD_USE_ORIGINAL_MOVIES LOLG_HD_ALLOW_CRITICAL_HD_MIX LOLG_HD_WINE_RUNTIME_ROOT WINEPREFIX
			exec ./RUN_HD_WINE.sh "$@"
			;;
		wine-vqa-contract|wine-locallng-movies-contract|wine-vqa-safe)
			require_executable ./RUN_HD_WINE.sh
			validate_vqa_contract_pair 1
			require_vqa_contract_runtime_override "wine-vqa-contract" "$@"
			LOLG_HD_RESOLUTION=1920x1080
			LOLG_HD_USE_DGVOODOO=0
			LOLG_HD_DGVOODOO_FORCE_RESOLUTION=0
			LOLG_HD_WINE_RENDERER=${LOLG_HD_WINE_RENDERER:-vulkan}
			LOLG_HD_WINE_DIRECTDRAW_RENDERER=${LOLG_HD_WINE_DIRECTDRAW_RENDERER:-vulkan}
			LOLG_HD_WINE_VERSION=${LOLG_HD_WINE_VERSION:-win95}
			LOLG_HD_USE_DXVK=${LOLG_HD_USE_DXVK:-1}
			LOLG_HD_SETUP_DXVK=${LOLG_HD_SETUP_DXVK:-1}
			LOLG_HD_WINE_WAIT=0
			LOLG_HD_LOCK_WINDOW_POSITION=${LOLG_HD_LOCK_WINDOW_POSITION:-0}
			LOLG_HD_RESIZE_GAME_WINDOW_DELAY=${LOLG_HD_RESIZE_GAME_WINDOW_DELAY:-0}
			LOLG_HD_WINE_USE_HD_MIX=0
			LOLG_HD_WINE_HD_EXCLUDE=LOCALLNG.MIX,MOVIES.MIX
			LOLG_HD_WINE_EXTRA_MIX_DIR=$CONTRACT_MIX_DIR
			if [ "$LOLG_HD_USE_DXVK" -eq 1 ]; then
				LOLG_HD_WINE_DLL_OVERRIDES=${LOLG_HD_WINE_DLL_OVERRIDES:-'ddraw,d3dimm=b;d3d8,d3d9,dxgi,d3d10,d3d10_1,d3d10core,d3d11=n,b'}
			else
				LOLG_HD_WINE_DLL_OVERRIDES=${LOLG_HD_WINE_DLL_OVERRIDES:-'ddraw,d3dimm,d3d8=b'}
			fi
			LOLG_HD_WINE_EXTRA_MIX_NOTE=${LOLG_HD_WINE_EXTRA_MIX_NOTE:-"lanceur 1920x1080 sans dgVoodoo avec LOCALLNG.MIX 1280 padde et MOVIES.MIX contract-preserving 1280 windowed"}
			LOLG_HD_WINE_MOVIES_LABEL=${LOLG_HD_WINE_MOVIES_LABEL:-"contract-preserving HD 1280 (entrees 0-27 reconstruites), affiche en 1920x1080"}
			LOLG_HD_USE_ORIGINAL_MOVIES=0
			LOLG_HD_ALLOW_CRITICAL_HD_MIX=1
			LOLG_HD_WINE_RUNTIME_ROOT=${LOLG_HD_WINE_RUNTIME_ROOT:-"$BASE_DIR/output/lolg95_vqa_contract_runtime"}
			WINEPREFIX=${WINEPREFIX:-"$BASE_DIR/output/lolg95_vqa_contract_wine_prefix"}
			export LOLG_HD_RESOLUTION LOLG_HD_USE_DGVOODOO LOLG_HD_DGVOODOO_FORCE_RESOLUTION
			export LOLG_HD_WINE_RENDERER LOLG_HD_WINE_DIRECTDRAW_RENDERER LOLG_HD_WINE_VERSION LOLG_HD_USE_DXVK LOLG_HD_SETUP_DXVK
			export LOLG_HD_WINE_DLL_OVERRIDES LOLG_HD_WINE_WAIT LOLG_HD_LOCK_WINDOW_POSITION LOLG_HD_RESIZE_GAME_WINDOW_DELAY
			export LOLG_HD_WINE_USE_HD_MIX LOLG_HD_WINE_HD_EXCLUDE LOLG_HD_WINE_EXTRA_MIX_DIR
			export LOLG_HD_WINE_EXTRA_MIX_NOTE LOLG_HD_WINE_MOVIES_LABEL
			export LOLG_HD_USE_ORIGINAL_MOVIES LOLG_HD_ALLOW_CRITICAL_HD_MIX LOLG_HD_WINE_RUNTIME_ROOT WINEPREFIX
			exec ./RUN_HD_WINE.sh "$@"
			;;
		wine-vqa-contract-dgvoodoo|wine-dgvoodoo-vqa-contract|wine-vqa-contract-win10-dgvoodoo)
			validate_vqa_contract_pair 0
			require_vqa_contract_runtime_override "wine-vqa-contract-dgvoodoo" "$@"
			LOLG_HD_WINE_USE_HD_MIX=0
			LOLG_HD_WINE_HD_EXCLUDE=LOCALLNG.MIX,MOVIES.MIX
			LOLG_HD_WINE_EXTRA_MIX_DIR=$CONTRACT_MIX_DIR
			LOLG_HD_WINE_EXTRA_MIX_NOTE="dgVoodoo win10 avec LOCALLNG.MIX et MOVIES.MIX contract-preserving 1280 windowed"
			LOLG_HD_WINE_MOVIES_LABEL="contract-preserving HD 1280 (entrees 0-27 reconstruites), via dgVoodoo"
			LOLG_HD_USE_ORIGINAL_MOVIES=0
			LOLG_HD_ALLOW_CRITICAL_HD_MIX=1
			LOLG_HD_WINE_USE_XRANDR=${LOLG_HD_WINE_USE_XRANDR:-N}
			LOLG_HD_WINE_USE_XVIDMODE=${LOLG_HD_WINE_USE_XVIDMODE:-N}
			LOLG_HD_DGVOODOO_WINDOWED_ATTRIBUTES=${LOLG_HD_DGVOODOO_WINDOWED_ATTRIBUTES:-borderless}
			LOLG_HD_SKIP_WINE_SETUP=0
			LOLG_HD_WINE_RUNTIME_ROOT=${LOLG_HD_WINE_RUNTIME_ROOT:-"$BASE_DIR/output/lolg95_vqa_contract_runtime"}
			# Use the active game dgVoodoo DLLs by default; set
			# LOLG_HD_DGVOODOO_SOURCE_DIR to force an older backup for diagnostics.
			export LOLG_HD_WINE_USE_HD_MIX LOLG_HD_WINE_HD_EXCLUDE LOLG_HD_WINE_EXTRA_MIX_DIR
			export LOLG_HD_WINE_EXTRA_MIX_NOTE LOLG_HD_WINE_MOVIES_LABEL
			export LOLG_HD_USE_ORIGINAL_MOVIES LOLG_HD_ALLOW_CRITICAL_HD_MIX
			export LOLG_HD_WINE_USE_XRANDR LOLG_HD_WINE_USE_XVIDMODE
			export LOLG_HD_DGVOODOO_WINDOWED_ATTRIBUTES
			export LOLG_HD_SKIP_WINE_SETUP LOLG_HD_WINE_RUNTIME_ROOT
			export LOLG_HD_DGVOODOO_SOURCE_DIR
			exec ./LOLG_HD.sh wine-dgvoodoo-win10 "$@"
			;;
		wine-nodgvoodoo-safevqa|wine-safevqa-nodg|wine-1920-nodgvoodoo-safevqa)
			require_executable ./RUN_HD_WINE.sh
			LOLG_HD_RESOLUTION=${LOLG_HD_RESOLUTION:-1920x1080}
			LOLG_HD_USE_DGVOODOO=0
			LOLG_HD_DGVOODOO_FORCE_RESOLUTION=0
			LOLG_HD_USE_LOCAL_DDRAW=0
			LOLG_HD_WINE_RENDERER=${LOLG_HD_WINE_RENDERER:-gdi}
			LOLG_HD_WINE_DIRECTDRAW_RENDERER=${LOLG_HD_WINE_DIRECTDRAW_RENDERER:-gdi}
			LOLG_HD_WINE_VERSION=${LOLG_HD_WINE_VERSION:-win10}
			LOLG_HD_USE_DXVK=${LOLG_HD_USE_DXVK:-0}
			LOLG_HD_SETUP_DXVK=${LOLG_HD_SETUP_DXVK:-0}
			LOLG_HD_WINE_USE_XRANDR=${LOLG_HD_WINE_USE_XRANDR:-N}
			LOLG_HD_WINE_USE_XVIDMODE=${LOLG_HD_WINE_USE_XVIDMODE:-N}
			LOLG_HD_WINE_WAIT=${LOLG_HD_WINE_WAIT:-0}
			LOLG_HD_AUTO_RESIZE=${LOLG_HD_AUTO_RESIZE:-0}
			LOLG_HD_RESIZE_GAME_WINDOW=${LOLG_HD_RESIZE_GAME_WINDOW:-0}
			LOLG_HD_LOCK_WINDOW_POSITION=${LOLG_HD_LOCK_WINDOW_POSITION:-0}
			LOLG_HD_RESIZE_GAME_WINDOW_DELAY=${LOLG_HD_RESIZE_GAME_WINDOW_DELAY:-0}
			LOLG_HD_WINE_USE_HD_MIX=${LOLG_HD_WINE_USE_HD_MIX:-1}
			LOLG_HD_UNSTABLE_ANIMATION_MIX=${LOLG_HD_UNSTABLE_ANIMATION_MIX:-DANIEL.MIX,DRAGON.MIX,DSLAVE.MIX,LIZ.MIX,MCEL.MIX,MENT.MIX,MGAR.MIX,MLIB.MIX,MOFF.MIX,SHAMAN.MIX,SLAVES.MIX,WPN.MIX,MAGIC.MIX,L1_DCI.MIX,L3_DHI.MIX,L4_HJI.MIX,L5_HCI.MIX,L7_DHI.MIX,L8_SJI.MIX,L9_DRI.MIX,L10_DCI.MIX,L12_CMI.MIX,L13_RCI.MIX,L14_HTI.MIX,L16_CAI.MIX,L19_BCI.MIX,L20_BBI.MIX}
			LOLG_HD_WINE_HD_EXCLUDE=${LOLG_HD_WINE_HD_EXCLUDE:-LOCALLNG.MIX,MOVIES.MIX,$LOLG_HD_UNSTABLE_ANIMATION_MIX}
			LOLG_HD_USE_ORIGINAL_MOVIES=${LOLG_HD_USE_ORIGINAL_MOVIES:-1}
			LOLG_HD_ALLOW_CRITICAL_HD_MIX=${LOLG_HD_ALLOW_CRITICAL_HD_MIX:-0}
			WINEPREFIX=${WINEPREFIX:-"$BASE_DIR/output/lolg95_nodgvoodoo_safevqa_wine_prefix"}
			export LOLG_HD_RESOLUTION LOLG_HD_USE_DGVOODOO LOLG_HD_DGVOODOO_FORCE_RESOLUTION LOLG_HD_USE_LOCAL_DDRAW
			export LOLG_HD_WINE_RENDERER LOLG_HD_WINE_DIRECTDRAW_RENDERER LOLG_HD_WINE_VERSION LOLG_HD_USE_DXVK LOLG_HD_SETUP_DXVK
			export LOLG_HD_WINE_USE_XRANDR LOLG_HD_WINE_USE_XVIDMODE
			export LOLG_HD_WINE_WAIT LOLG_HD_AUTO_RESIZE LOLG_HD_RESIZE_GAME_WINDOW
			export LOLG_HD_LOCK_WINDOW_POSITION LOLG_HD_RESIZE_GAME_WINDOW_DELAY
			export LOLG_HD_WINE_USE_HD_MIX LOLG_HD_WINE_HD_EXCLUDE LOLG_HD_USE_ORIGINAL_MOVIES LOLG_HD_ALLOW_CRITICAL_HD_MIX
			export WINEPREFIX
			exec ./RUN_HD_WINE.sh "$@"
			;;
		wine-dgvoodoo-win10-safevqa|wine-win10-dgvoodoo-safevqa|wine-1920-dgvoodoo-win10-safevqa)
			LOLG_HD_WINE_USE_HD_MIX=${LOLG_HD_WINE_USE_HD_MIX:-1}
			LOLG_HD_UNSTABLE_ANIMATION_MIX=${LOLG_HD_UNSTABLE_ANIMATION_MIX:-DANIEL.MIX,DRAGON.MIX,DSLAVE.MIX,LIZ.MIX,MCEL.MIX,MENT.MIX,MGAR.MIX,MLIB.MIX,MOFF.MIX,SHAMAN.MIX,SLAVES.MIX,WPN.MIX,MAGIC.MIX,L1_DCI.MIX,L3_DHI.MIX,L4_HJI.MIX,L5_HCI.MIX,L7_DHI.MIX,L8_SJI.MIX,L9_DRI.MIX,L10_DCI.MIX,L12_CMI.MIX,L13_RCI.MIX,L14_HTI.MIX,L16_CAI.MIX,L19_BCI.MIX,L20_BBI.MIX}
			LOLG_HD_WINE_HD_EXCLUDE=${LOLG_HD_WINE_HD_EXCLUDE:-LOCALLNG.MIX,MOVIES.MIX,$LOLG_HD_UNSTABLE_ANIMATION_MIX}
			LOLG_HD_USE_ORIGINAL_MOVIES=${LOLG_HD_USE_ORIGINAL_MOVIES:-1}
			LOLG_HD_ALLOW_CRITICAL_HD_MIX=${LOLG_HD_ALLOW_CRITICAL_HD_MIX:-0}
			LOLG_HD_USE_NGLIDE=0
			LOLG_HD_USE_3DFX_CONFIG=0
			LOLG_HD_DISABLE_3D_ACCEL=${LOLG_HD_DISABLE_3D_ACCEL:-0}
			# Use the active game dgVoodoo DLLs by default; set
			# LOLG_HD_DGVOODOO_SOURCE_DIR to force an older backup for diagnostics.
			export LOLG_HD_WINE_USE_HD_MIX LOLG_HD_WINE_HD_EXCLUDE LOLG_HD_USE_ORIGINAL_MOVIES LOLG_HD_ALLOW_CRITICAL_HD_MIX
			export LOLG_HD_USE_NGLIDE LOLG_HD_USE_3DFX_CONFIG LOLG_HD_DISABLE_3D_ACCEL
			export LOLG_HD_DGVOODOO_SOURCE_DIR
			exec ./LOLG_HD.sh wine-dgvoodoo-win10 "$@"
			;;
		wine-external-sidecar|wine-sidecar-wrapper|wine-fullhd-sidecar)
			require_executable ./RUN_HD_WINE_EXTERNAL_SIDECAR.sh
			exec ./RUN_HD_WINE_EXTERNAL_SIDECAR.sh "$@"
			;;
		sidecar-test|vqa-sidecar-test|external-sidecar-test)
			INDEX_DIR=${LOLG_HD_EXTERNAL_SIDECAR_INDEX_DIR:-"$BASE_DIR/output/vqa_external_sidecar_index"}
			MANIFEST=$INDEX_DIR/manifest.json
			if [ ! -f "$MANIFEST" ]; then
				python3 tools/lolg_vqa_external_sidecar_index.py --hd-root mod_mix_vqa_fullhd --output "$INDEX_DIR"
			fi
			exec python3 tools/lolg_vqa_external_sidecar_request.py \
				--manifest "$MANIFEST" \
				--smallest \
				--decode \
				--max-frames "${LOLG_HD_EXTERNAL_SIDECAR_TEST_FRAMES:-2}" \
				--fullhd \
				--fit stretch \
				--filter nearest \
				--fast-png \
				"$@"
			;;
		sidecar-critical-test|vqa-sidecar-critical-test|external-sidecar-critical-test|sidecar-critical-warmup|vqa-sidecar-critical-warmup|external-sidecar-critical-warmup)
			INDEX_DIR=${LOLG_HD_EXTERNAL_SIDECAR_INDEX_DIR:-"$BASE_DIR/output/vqa_external_sidecar_index"}
			MANIFEST=$INDEX_DIR/manifest.json
			if [ ! -f "$MANIFEST" ]; then
				python3 tools/lolg_vqa_external_sidecar_index.py --hd-root mod_mix_vqa_fullhd --output "$INDEX_DIR"
			fi
			case "$command_name" in
				sidecar-critical-warmup|vqa-sidecar-critical-warmup|external-sidecar-critical-warmup)
					CRITICAL_FRAMES=${LOLG_HD_EXTERNAL_SIDECAR_CRITICAL_TEST_FRAMES:-0}
					CRITICAL_LABEL="Sidecar critical warmup"
					;;
				*)
					CRITICAL_FRAMES=${LOLG_HD_EXTERNAL_SIDECAR_CRITICAL_TEST_FRAMES:-1}
					CRITICAL_LABEL="Sidecar critical test"
					;;
			esac
			echo "$CRITICAL_LABEL: LOCALLNG.MIX:fca4e133"
			python3 tools/lolg_vqa_external_sidecar_request.py \
				LOCALLNG.MIX:fca4e133 \
				--manifest "$MANIFEST" \
				--cache-root output/vqa_external_sidecar_cache \
				--decode \
				--max-frames "$CRITICAL_FRAMES" \
				--fullhd \
				--fit stretch \
				--filter nearest \
				--fast-png \
				--preserve-decode-dir \
				"$@"
			echo "$CRITICAL_LABEL: MOVIES.MIX:4d6efa8e"
			python3 tools/lolg_vqa_external_sidecar_request.py \
				MOVIES.MIX:4d6efa8e \
				--manifest "$MANIFEST" \
				--cache-root output/vqa_external_sidecar_cache \
				--decode \
				--max-frames "$CRITICAL_FRAMES" \
				--fullhd \
				--fit stretch \
				--filter nearest \
				--fast-png \
				--preserve-decode-dir \
				"$@"
			;;
		sidecar-watch|vqa-sidecar-watch|external-sidecar-watch)
			INDEX_DIR=${LOLG_HD_EXTERNAL_SIDECAR_INDEX_DIR:-"$BASE_DIR/output/vqa_external_sidecar_index"}
			MANIFEST=$INDEX_DIR/manifest.json
			if [ ! -f "$MANIFEST" ]; then
				python3 tools/lolg_vqa_external_sidecar_index.py --hd-root mod_mix_vqa_fullhd --output "$INDEX_DIR"
			fi
			exec python3 tools/lolg_vqa_external_sidecar_watch.py \
				--manifest "$MANIFEST" \
				"$@"
			;;
		sidecar-web|vqa-sidecar-web|external-sidecar-web)
			INDEX_DIR=${LOLG_HD_EXTERNAL_SIDECAR_INDEX_DIR:-"$BASE_DIR/output/vqa_external_sidecar_index"}
			MANIFEST=$INDEX_DIR/manifest.json
			if [ ! -f "$MANIFEST" ]; then
				python3 tools/lolg_vqa_external_sidecar_index.py --hd-root mod_mix_vqa_fullhd --output "$INDEX_DIR"
			fi
			exec python3 tools/lolg_vqa_external_sidecar_web.py \
				--manifest "$MANIFEST" \
				--process-requests \
				"$@"
			;;
		sidecar-status|vqa-sidecar-status|external-sidecar-status)
			INDEX_DIR=${LOLG_HD_EXTERNAL_SIDECAR_INDEX_DIR:-"$BASE_DIR/output/vqa_external_sidecar_index"}
			MANIFEST=$INDEX_DIR/manifest.json
			if [ ! -f "$MANIFEST" ]; then
				python3 tools/lolg_vqa_external_sidecar_index.py --hd-root mod_mix_vqa_fullhd --output "$INDEX_DIR"
			fi
			exec python3 tools/lolg_vqa_external_sidecar_status.py \
				--manifest "$MANIFEST" \
				"$@"
			;;
		sidecar-critical-status|vqa-sidecar-critical-status|external-sidecar-critical-status)
			exec ./LOLG_HD.sh sidecar-status --critical "$@"
			;;
		sidecar-audit|vqa-sidecar-audit|external-sidecar-audit)
			INDEX_DIR=${LOLG_HD_EXTERNAL_SIDECAR_INDEX_DIR:-"$BASE_DIR/output/vqa_external_sidecar_index"}
			MANIFEST=$INDEX_DIR/manifest.json
			if [ ! -f "$MANIFEST" ]; then
				python3 tools/lolg_vqa_external_sidecar_index.py --hd-root mod_mix_vqa_fullhd --output "$INDEX_DIR"
			fi
			exec python3 tools/lolg_vqa_external_sidecar_audit.py \
				--manifest "$MANIFEST" \
				"$@"
			;;
		sidecar-trace-bridge|vqa-sidecar-trace-bridge|external-sidecar-trace-bridge)
			INDEX_DIR=${LOLG_HD_EXTERNAL_SIDECAR_INDEX_DIR:-"$BASE_DIR/output/vqa_external_sidecar_index"}
			MANIFEST=$INDEX_DIR/manifest.json
			if [ ! -f "$MANIFEST" ]; then
				python3 tools/lolg_vqa_external_sidecar_index.py --hd-root mod_mix_vqa_fullhd --output "$INDEX_DIR"
			fi
			exec python3 tools/lolg_vqa_external_sidecar_trace_bridge.py \
				--manifest "$MANIFEST" \
				"$@"
			;;
		sidecar-strace-bridge|vqa-sidecar-strace-bridge|external-sidecar-strace-bridge)
			exec python3 tools/lolg_vqa_external_sidecar_strace_bridge.py "$@"
			;;
		sidecar-hd|vqa-sidecar-hd|external-sidecar-hd|fullhd-sidecar)
			exec ./LOLG_HD.sh sidecar-live --trace-source strace --strace-all-reads --strace-dedupe --trace-dedupe-key --max-frames 0 --open-player --player-hud "$@"
			;;
		sidecar-hd-nodg|sidecar-hd-no-dgvoodoo|vqa-sidecar-hd-nodg|external-sidecar-hd-nodg)
			LOLG_HD_EXTERNAL_SIDECAR_ENGINE=wine-nodgvoodoo-safevqa
			export LOLG_HD_EXTERNAL_SIDECAR_ENGINE
			exec ./LOLG_HD.sh sidecar-live --trace-source strace --strace-all-reads --strace-dedupe --trace-dedupe-key --max-frames 0 --open-player --player-hud "$@"
			;;
		sidecar-live-strace|vqa-sidecar-live-strace|external-sidecar-live-strace)
			exec ./LOLG_HD.sh sidecar-live --trace-source strace "$@"
			;;
		sidecar-live-strace-all|vqa-sidecar-live-strace-all|external-sidecar-live-strace-all)
			exec ./LOLG_HD.sh sidecar-live --trace-source strace --max-frames 0 "$@"
			;;
		sidecar-live-strace-player|vqa-sidecar-live-strace-player|external-sidecar-live-strace-player)
			exec ./LOLG_HD.sh sidecar-live --trace-source strace --open-player "$@"
			;;
		sidecar-live-strace-all-player|vqa-sidecar-live-strace-all-player|external-sidecar-live-strace-all-player)
			exec ./LOLG_HD.sh sidecar-live --trace-source strace --max-frames 0 --open-player "$@"
			;;
		sidecar-live-strace-wide-player|vqa-sidecar-live-strace-wide-player|external-sidecar-live-strace-wide-player)
			exec ./LOLG_HD.sh sidecar-live --trace-source strace --strace-all-reads --strace-dedupe --trace-dedupe-key --open-player "$@"
			;;
		sidecar-live-strace-wide-all-player|vqa-sidecar-live-strace-wide-all-player|external-sidecar-live-strace-wide-all-player)
			exec ./LOLG_HD.sh sidecar-live --trace-source strace --strace-all-reads --strace-dedupe --trace-dedupe-key --max-frames 0 --open-player "$@"
			;;
		sidecar-live-strace-wide-hud|vqa-sidecar-live-strace-wide-hud|external-sidecar-live-strace-wide-hud)
			exec ./LOLG_HD.sh sidecar-live --trace-source strace --strace-all-reads --strace-dedupe --trace-dedupe-key --open-player --player-hud "$@"
			;;
		sidecar-live-strace-wide-all-hud|vqa-sidecar-live-strace-wide-all-hud|external-sidecar-live-strace-wide-all-hud)
			exec ./LOLG_HD.sh sidecar-live --trace-source strace --strace-all-reads --strace-dedupe --trace-dedupe-key --max-frames 0 --open-player --player-hud "$@"
			;;
		sidecar-live|vqa-sidecar-live|external-sidecar-live)
			INDEX_DIR=${LOLG_HD_EXTERNAL_SIDECAR_INDEX_DIR:-"$BASE_DIR/output/vqa_external_sidecar_index"}
			MANIFEST=$INDEX_DIR/manifest.json
			if [ ! -f "$MANIFEST" ]; then
				python3 tools/lolg_vqa_external_sidecar_index.py --hd-root mod_mix_vqa_fullhd --output "$INDEX_DIR"
			fi
			exec python3 tools/lolg_vqa_external_sidecar_live.py \
				--manifest "$MANIFEST" \
				"$@"
			;;
		wine-dgvoodoo-win10-safevqa-movies-safe|wine-safevqa-movies-safe|wine-movies-safe)
			require_executable ./RUN_HD_WINE.sh
			require_movies_safe_runtime_override "wine-dgvoodoo-win10-safevqa-movies-safe" "$@"
			movies_safe_full_dir="$BASE_DIR/output/vqa_contract_batch_writer_movies_0000_0027_892x560_safe"
			movies_safe_full_mix="$movies_safe_full_dir/mix/MOVIES.MIX"
			if [ ! -f "$movies_safe_full_mix" ]; then
				echo "MIX MOVIES safe 892x560 introuvable: $movies_safe_full_mix" >&2
				echo "Regenerer d'abord avec ./LOLG_HD.sh vqa-contract-build-movies-safe." >&2
				exit 1
			fi
			require_vqa_contract_pass "$movies_safe_full_dir/summary.csv" "MOVIES.MIX safe 892x560 complet"
			LOLG_HD_WINE_USE_HD_MIX=${LOLG_HD_WINE_USE_HD_MIX:-1}
			LOLG_HD_UNSTABLE_ANIMATION_MIX=${LOLG_HD_UNSTABLE_ANIMATION_MIX:-DANIEL.MIX,DRAGON.MIX,DSLAVE.MIX,LIZ.MIX,MCEL.MIX,MENT.MIX,MGAR.MIX,MLIB.MIX,MOFF.MIX,SHAMAN.MIX,SLAVES.MIX,WPN.MIX,MAGIC.MIX,L1_DCI.MIX,L3_DHI.MIX,L4_HJI.MIX,L5_HCI.MIX,L7_DHI.MIX,L8_SJI.MIX,L9_DRI.MIX,L10_DCI.MIX,L12_CMI.MIX,L13_RCI.MIX,L14_HTI.MIX,L16_CAI.MIX,L19_BCI.MIX,L20_BBI.MIX}
			LOLG_HD_WINE_HD_EXCLUDE=${LOLG_HD_WINE_HD_EXCLUDE:-LOCALLNG.MIX,$LOLG_HD_UNSTABLE_ANIMATION_MIX}
			LOLG_HD_WINE_EXTRA_MIX_DIR=${LOLG_HD_WINE_EXTRA_MIX_DIR:-"$movies_safe_full_dir/mix"}
			LOLG_HD_WINE_EXTRA_MIX_NOTE=${LOLG_HD_WINE_EXTRA_MIX_NOTE:-"dgVoodoo win10 safevqa avec LOCALLNG.MIX original et MOVIES.MIX safe 892x560 complet"}
			LOLG_HD_WINE_MOVIES_LABEL=${LOLG_HD_WINE_MOVIES_LABEL:-"safe 892x560 complet (entrees 0-27, runtime_compat=pass)"}
			LOLG_HD_USE_ORIGINAL_MOVIES=0
			LOLG_HD_ALLOW_CRITICAL_HD_MIX=1
			LOLG_HD_USE_NGLIDE=0
			LOLG_HD_USE_3DFX_CONFIG=0
			LOLG_HD_DISABLE_3D_ACCEL=${LOLG_HD_DISABLE_3D_ACCEL:-0}
			LOLG_HD_WINE_RUNTIME_ROOT=${LOLG_HD_WINE_RUNTIME_ROOT:-"$BASE_DIR/output/lolg95_dgvoodoo_win10_safevqa_movies_safe_runtime"}
			LOLG_HD_SKIP_WINE_SETUP=${LOLG_HD_SKIP_WINE_SETUP:-0}
			WINEPREFIX=${WINEPREFIX:-"$BASE_DIR/output/lolg95_dgvoodoo_win10_safevqa_movies_safe_wine_prefix"}
			export LOLG_HD_WINE_USE_HD_MIX LOLG_HD_WINE_HD_EXCLUDE LOLG_HD_WINE_EXTRA_MIX_DIR
			export LOLG_HD_WINE_EXTRA_MIX_NOTE LOLG_HD_WINE_MOVIES_LABEL
			export LOLG_HD_USE_ORIGINAL_MOVIES LOLG_HD_ALLOW_CRITICAL_HD_MIX
			export LOLG_HD_USE_NGLIDE LOLG_HD_USE_3DFX_CONFIG LOLG_HD_DISABLE_3D_ACCEL
			export LOLG_HD_WINE_RUNTIME_ROOT LOLG_HD_SKIP_WINE_SETUP WINEPREFIX
			exec ./LOLG_HD.sh wine-dgvoodoo-win10 "$@"
			;;
		wine-dgvoodoo-win95-safevqa-direct|wine-dgvoodoo-safevqa-direct|wine-sans-fenetre-safevqa)
			LOLG_HD_WINE_VERSION=${LOLG_HD_WINE_VERSION:-win95}
			WINEPREFIX=${WINEPREFIX:-"$BASE_DIR/output/lolg95_dgvoodoo_win95_safevqa_direct_wine_prefix"}
			export LOLG_HD_WINE_VERSION WINEPREFIX
			exec ./LOLG_HD.sh wine-dgvoodoo-win10-safevqa --direct "$@"
			;;
		wine-dgvoodoo-win10-originalmix|wine-win10-dgvoodoo-originalmix|wine-1920-dgvoodoo-win10-originalmix)
			LOLG_HD_WINE_USE_HD_MIX=0
			LOLG_HD_WINE_HD_EXCLUDE=${LOLG_HD_WINE_HD_EXCLUDE:-LOCALLNG.MIX,MOVIES.MIX}
			LOLG_HD_USE_ORIGINAL_MOVIES=1
			LOLG_HD_ALLOW_CRITICAL_HD_MIX=0
			export LOLG_HD_WINE_USE_HD_MIX LOLG_HD_WINE_HD_EXCLUDE LOLG_HD_USE_ORIGINAL_MOVIES LOLG_HD_ALLOW_CRITICAL_HD_MIX
			exec ./LOLG_HD.sh wine-dgvoodoo-win10 "$@"
			;;
		wine-nglide-win10-safevqa|wine-win10-nglide-safevqa|wine-1920-nglide-win10-safevqa)
			LOLG_HD_WINE_USE_HD_MIX=${LOLG_HD_WINE_USE_HD_MIX:-1}
			LOLG_HD_WINE_HD_EXCLUDE=${LOLG_HD_WINE_HD_EXCLUDE:-LOCALLNG.MIX,MOVIES.MIX,L1_DCI.MIX,L3_DHI.MIX,L4_HJI.MIX,L5_HCI.MIX,L7_DHI.MIX,L8_SJI.MIX,L9_DRI.MIX,L10_DCI.MIX,L12_CMI.MIX,L13_RCI.MIX,L14_HTI.MIX,L16_CAI.MIX,L19_BCI.MIX,L20_BBI.MIX}
			LOLG_HD_USE_ORIGINAL_MOVIES=${LOLG_HD_USE_ORIGINAL_MOVIES:-1}
			LOLG_HD_ALLOW_CRITICAL_HD_MIX=${LOLG_HD_ALLOW_CRITICAL_HD_MIX:-0}
			export LOLG_HD_WINE_USE_HD_MIX LOLG_HD_WINE_HD_EXCLUDE LOLG_HD_USE_ORIGINAL_MOVIES LOLG_HD_ALLOW_CRITICAL_HD_MIX
			exec ./LOLG_HD.sh wine-nglide-win10 "$@"
			;;
		wine-nglide-win10|wine-win10-nglide|wine-1920-nglide-win10)
			require_executable ./RUN_HD_WINE.sh
			LOLG_HD_RESOLUTION=${LOLG_HD_RESOLUTION:-1920x1080}
			LOLG_HD_USE_DGVOODOO=0
			LOLG_HD_USE_LOCAL_DDRAW=0
			LOLG_HD_DGVOODOO_FORCE_RESOLUTION=0
			LOLG_HD_USE_NGLIDE=1
			LOLG_HD_USE_3DFX_CONFIG=1
			LOLG_HD_NGLIDE_DIR=${LOLG_HD_NGLIDE_DIR:-"$HOME/.wine/drive_c/windows/syswow64"}
			LOLG_HD_WINE_RENDERER=${LOLG_HD_WINE_RENDERER:-opengl}
			LOLG_HD_WINE_DIRECTDRAW_RENDERER=${LOLG_HD_WINE_DIRECTDRAW_RENDERER:-gdi}
			LOLG_HD_WINE_VERSION=${LOLG_HD_WINE_VERSION:-win10}
			LOLG_HD_WINE_USE_XRANDR=${LOLG_HD_WINE_USE_XRANDR:-Y}
			LOLG_HD_WINE_USE_XVIDMODE=${LOLG_HD_WINE_USE_XVIDMODE:-N}
			LOLG_HD_WINE_WAIT=${LOLG_HD_WINE_WAIT:-0}
			LOLG_HD_AUTO_RESIZE=${LOLG_HD_AUTO_RESIZE:-1}
			LOLG_HD_RESIZE_GAME_WINDOW=${LOLG_HD_RESIZE_GAME_WINDOW:-1}
			LOLG_HD_RESIZE_GAME_WINDOW_DELAY=${LOLG_HD_RESIZE_GAME_WINDOW_DELAY:-2}
			LOLG_HD_RESIZE_GAME_WINDOW_HOLD=${LOLG_HD_RESIZE_GAME_WINDOW_HOLD:-45}
			LOLG_HD_WINDOW_SEARCH_TIMEOUT=${LOLG_HD_WINDOW_SEARCH_TIMEOUT:-45}
			LOLG_HD_LOCK_WINDOW_POSITION=${LOLG_HD_LOCK_WINDOW_POSITION:-0}
			LOLG_HD_NGLIDE_BACKEND=${LOLG_HD_NGLIDE_BACKEND:-1}
			LOLG_HD_NGLIDE_RESOLUTION=${LOLG_HD_NGLIDE_RESOLUTION:-21}
			LOLG_HD_NGLIDE_VSYNC=${LOLG_HD_NGLIDE_VSYNC:-1}
			LOLG_HD_NGLIDE_SPLASH=${LOLG_HD_NGLIDE_SPLASH:-0}
			LOLG_HD_WINE_USE_HD_MIX=${LOLG_HD_WINE_USE_HD_MIX:-1}
			LOLG_HD_WINE_HD_EXCLUDE=${LOLG_HD_WINE_HD_EXCLUDE:-LOCALLNG.MIX,MOVIES.MIX}
			LOLG_HD_USE_ORIGINAL_MOVIES=${LOLG_HD_USE_ORIGINAL_MOVIES:-1}
			LOLG_HD_ALLOW_CRITICAL_HD_MIX=${LOLG_HD_ALLOW_CRITICAL_HD_MIX:-0}
			WINEPREFIX=${WINEPREFIX:-"$BASE_DIR/output/lolg95_nglide_win10_wine_prefix"}
			LOLG_HD_USE_DXVK=${LOLG_HD_USE_DXVK:-0}
			LOLG_HD_SETUP_DXVK=${LOLG_HD_SETUP_DXVK:-0}
			LOLG_HD_WINE_DLL_OVERRIDES=${LOLG_HD_WINE_DLL_OVERRIDES:-'glide,glide2x,glide3x=n,b;ddraw,d3dimm,d3d8=b'}
			export LOLG_HD_RESOLUTION LOLG_HD_USE_DGVOODOO LOLG_HD_USE_LOCAL_DDRAW LOLG_HD_DGVOODOO_FORCE_RESOLUTION
			export LOLG_HD_USE_NGLIDE LOLG_HD_USE_3DFX_CONFIG LOLG_HD_NGLIDE_DIR
			export LOLG_HD_NGLIDE_BACKEND LOLG_HD_NGLIDE_RESOLUTION LOLG_HD_NGLIDE_VSYNC LOLG_HD_NGLIDE_SPLASH
			export LOLG_HD_WINE_RENDERER LOLG_HD_WINE_DIRECTDRAW_RENDERER LOLG_HD_WINE_VERSION
			export LOLG_HD_WINE_USE_XRANDR LOLG_HD_WINE_USE_XVIDMODE
			export LOLG_HD_USE_DXVK LOLG_HD_SETUP_DXVK LOLG_HD_WINE_DLL_OVERRIDES LOLG_HD_WINE_WAIT
			export LOLG_HD_AUTO_RESIZE LOLG_HD_RESIZE_GAME_WINDOW LOLG_HD_RESIZE_GAME_WINDOW_DELAY LOLG_HD_RESIZE_GAME_WINDOW_HOLD
			export LOLG_HD_WINDOW_SEARCH_TIMEOUT LOLG_HD_LOCK_WINDOW_POSITION
			export LOLG_HD_WINE_USE_HD_MIX LOLG_HD_WINE_HD_EXCLUDE LOLG_HD_USE_ORIGINAL_MOVIES LOLG_HD_ALLOW_CRITICAL_HD_MIX
			export WINEPREFIX
			exec ./RUN_HD_WINE.sh --detach "$@"
			;;
		wine-dgvoodoo-win10|wine-win10-dgvoodoo|wine-1920-dgvoodoo-win10)
			require_executable ./RUN_HD_WINE.sh
			LOLG_HD_RESOLUTION=${LOLG_HD_RESOLUTION:-1920x1080}
			LOLG_HD_USE_DGVOODOO=1
			LOLG_HD_USE_LOCAL_DDRAW=1
			LOLG_HD_USE_NGLIDE=0
			LOLG_HD_USE_3DFX_CONFIG=0
			LOLG_HD_DGVOODOO_FORCE_RESOLUTION=${LOLG_HD_DGVOODOO_FORCE_RESOLUTION:-1}
			LOLG_HD_DGVOODOO_OUTPUT_API=${LOLG_HD_DGVOODOO_OUTPUT_API:-d3d11_fl11_0}
			LOLG_HD_DGVOODOO_FULLSCREEN=${LOLG_HD_DGVOODOO_FULLSCREEN:-false}
			LOLG_HD_DGVOODOO_SCALING=${LOLG_HD_DGVOODOO_SCALING:-stretched_ar}
			LOLG_HD_DGVOODOO_APP_CONTROLLED=${LOLG_HD_DGVOODOO_APP_CONTROLLED:-false}
			LOLG_HD_DGVOODOO_DESKTOP_RESOLUTION=${LOLG_HD_DGVOODOO_DESKTOP_RESOLUTION:-$LOLG_HD_RESOLUTION}
			LOLG_HD_DGVOODOO_WINDOWED_ATTRIBUTES=${LOLG_HD_DGVOODOO_WINDOWED_ATTRIBUTES:-fullscreensize}
			LOLG_HD_DGVOODOO_VRAM=${LOLG_HD_DGVOODOO_VRAM:-2GB}
			LOLG_HD_DGVOODOO_GLIDE_RAM=${LOLG_HD_DGVOODOO_GLIDE_RAM:-2048}
			LOLG_HD_DGVOODOO_TMU_MEMORY=${LOLG_HD_DGVOODOO_TMU_MEMORY:-262144}
			LOLG_HD_DGVOODOO_FAST_VIDEO_MEMORY=${LOLG_HD_DGVOODOO_FAST_VIDEO_MEMORY:-true}
			LOLG_HD_DGVOODOO_PRIMARY_SURFACE_BATCHED=${LOLG_HD_DGVOODOO_PRIMARY_SURFACE_BATCHED:-true}
			LOLG_HD_DGVOODOO_RT_TEXTURES_FORCE_SCALE_MSAA=${LOLG_HD_DGVOODOO_RT_TEXTURES_FORCE_SCALE_MSAA:-false}
			LOLG_HD_DGVOODOO_SMOOTHED_DEPTH_SAMPLING=${LOLG_HD_DGVOODOO_SMOOTHED_DEPTH_SAMPLING:-false}
			LOLG_HD_DGVOODOO_FORCE_VSYNC=${LOLG_HD_DGVOODOO_FORCE_VSYNC:-false}
			LOLG_HD_WINE_RENDERER=${LOLG_HD_WINE_RENDERER:-vulkan}
			LOLG_HD_WINE_DIRECTDRAW_RENDERER=${LOLG_HD_WINE_DIRECTDRAW_RENDERER:-gdi}
			LOLG_HD_WINE_VIDEO_MEMORY_SIZE=${LOLG_HD_WINE_VIDEO_MEMORY_SIZE:-2048}
			LOLG_HD_WINE_VERSION=${LOLG_HD_WINE_VERSION:-win10}
			LOLG_HD_WINE_USE_XRANDR=${LOLG_HD_WINE_USE_XRANDR:-Y}
			LOLG_HD_WINE_USE_XVIDMODE=${LOLG_HD_WINE_USE_XVIDMODE:-N}
			LOLG_HD_WINE_WAIT=${LOLG_HD_WINE_WAIT:-0}
			LOLG_HD_AUTO_RESIZE=${LOLG_HD_AUTO_RESIZE:-0}
			LOLG_HD_RESIZE_GAME_WINDOW=${LOLG_HD_RESIZE_GAME_WINDOW:-0}
			LOLG_HD_LOCK_WINDOW_POSITION=${LOLG_HD_LOCK_WINDOW_POSITION:-0}
			LOLG_HD_WINE_USE_HD_MIX=${LOLG_HD_WINE_USE_HD_MIX:-1}
			LOLG_HD_WINE_HD_EXCLUDE=${LOLG_HD_WINE_HD_EXCLUDE:-}
			LOLG_HD_USE_ORIGINAL_MOVIES=${LOLG_HD_USE_ORIGINAL_MOVIES:-0}
			LOLG_HD_ALLOW_CRITICAL_HD_MIX=${LOLG_HD_ALLOW_CRITICAL_HD_MIX:-1}
			WINEPREFIX=${WINEPREFIX:-"$BASE_DIR/output/lolg95_dgvoodoo_win10_wine_prefix"}
			LOLG_HD_USE_DXVK=${LOLG_HD_USE_DXVK:-0}
			LOLG_HD_SETUP_DXVK=${LOLG_HD_SETUP_DXVK:-0}
			LOLG_HD_WINE_DLL_OVERRIDES=${LOLG_HD_WINE_DLL_OVERRIDES:-'ddraw,d3dimm,d3d8=n,b'}
			export LOLG_HD_RESOLUTION LOLG_HD_USE_DGVOODOO LOLG_HD_USE_LOCAL_DDRAW
			export LOLG_HD_USE_NGLIDE LOLG_HD_USE_3DFX_CONFIG
			export LOLG_HD_DGVOODOO_SOURCE_DIR
			export LOLG_HD_DGVOODOO_FORCE_RESOLUTION LOLG_HD_DGVOODOO_OUTPUT_API LOLG_HD_DGVOODOO_FULLSCREEN
			export LOLG_HD_DGVOODOO_SCALING LOLG_HD_DGVOODOO_APP_CONTROLLED
			export LOLG_HD_DGVOODOO_DESKTOP_RESOLUTION LOLG_HD_DGVOODOO_WINDOWED_ATTRIBUTES
			export LOLG_HD_DGVOODOO_VRAM LOLG_HD_DGVOODOO_GLIDE_RAM LOLG_HD_DGVOODOO_TMU_MEMORY
			export LOLG_HD_DGVOODOO_FAST_VIDEO_MEMORY LOLG_HD_DGVOODOO_PRIMARY_SURFACE_BATCHED
			export LOLG_HD_DGVOODOO_RT_TEXTURES_FORCE_SCALE_MSAA LOLG_HD_DGVOODOO_SMOOTHED_DEPTH_SAMPLING
			export LOLG_HD_DGVOODOO_FORCE_VSYNC
			export LOLG_HD_WINE_RENDERER LOLG_HD_WINE_DIRECTDRAW_RENDERER LOLG_HD_WINE_VERSION
			export LOLG_HD_WINE_VIDEO_MEMORY_SIZE
			export LOLG_HD_WINE_USE_XRANDR LOLG_HD_WINE_USE_XVIDMODE
			export LOLG_HD_USE_DXVK LOLG_HD_SETUP_DXVK LOLG_HD_WINE_DLL_OVERRIDES LOLG_HD_WINE_WAIT
			export LOLG_HD_AUTO_RESIZE LOLG_HD_RESIZE_GAME_WINDOW LOLG_HD_LOCK_WINDOW_POSITION
			export LOLG_HD_WINE_USE_HD_MIX LOLG_HD_WINE_HD_EXCLUDE LOLG_HD_USE_ORIGINAL_MOVIES LOLG_HD_ALLOW_CRITICAL_HD_MIX
			export WINEPREFIX
			RUN_HD_WINE_MODE=--detach
			if [ "$LOLG_HD_WINE_WAIT" -eq 1 ]; then
				RUN_HD_WINE_MODE=--wait
			fi
			if [ -f "$WINEPREFIX/system.reg" ] && [ "$LOLG_HD_SETUP_DXVK" = 0 ] && [ "${LOLG_HD_SKIP_WINE_SETUP:-1}" = "1" ]; then
				exec ./RUN_HD_WINE.sh --skip-wine-setup "$RUN_HD_WINE_MODE" "$@"
			fi
			exec ./RUN_HD_WINE.sh "$RUN_HD_WINE_MODE" "$@"
			;;
		wine-dgvoodoo-hdmix|wine-hdmix-dgvoodoo|wine-fullhd-dgvoodoo)
			require_executable ./RUN_HD_WINE.sh
			LOLG_HD_RESOLUTION=${LOLG_HD_RESOLUTION:-1920x1080}
			LOLG_HD_USE_DGVOODOO=1
			LOLG_HD_USE_LOCAL_DDRAW=1
			LOLG_HD_DGVOODOO_FORCE_RESOLUTION=${LOLG_HD_DGVOODOO_FORCE_RESOLUTION:-0}
			LOLG_HD_DGVOODOO_OUTPUT_API=${LOLG_HD_DGVOODOO_OUTPUT_API:-bestavailable}
			LOLG_HD_DGVOODOO_SCALING=${LOLG_HD_DGVOODOO_SCALING:-unspecified}
			LOLG_HD_DGVOODOO_APP_CONTROLLED=${LOLG_HD_DGVOODOO_APP_CONTROLLED:-true}
			LOLG_HD_DGVOODOO_DESKTOP_RESOLUTION=${LOLG_HD_DGVOODOO_DESKTOP_RESOLUTION:-}
			LOLG_HD_DGVOODOO_WINDOWED_ATTRIBUTES=${LOLG_HD_DGVOODOO_WINDOWED_ATTRIBUTES:-}
			LOLG_HD_WINE_RENDERER=${LOLG_HD_WINE_RENDERER:-vulkan}
			LOLG_HD_WINE_DIRECTDRAW_RENDERER=${LOLG_HD_WINE_DIRECTDRAW_RENDERER:-gdi}
			LOLG_HD_WINE_VERSION=${LOLG_HD_WINE_VERSION:-win95}
			LOLG_HD_WINE_WAIT=${LOLG_HD_WINE_WAIT:-0}
			LOLG_HD_AUTO_RESIZE=${LOLG_HD_AUTO_RESIZE:-0}
			LOLG_HD_RESIZE_GAME_WINDOW=${LOLG_HD_RESIZE_GAME_WINDOW:-0}
			LOLG_HD_LOCK_WINDOW_POSITION=${LOLG_HD_LOCK_WINDOW_POSITION:-0}
			LOLG_HD_WINE_USE_HD_MIX=1
			LOLG_HD_WINE_HD_EXCLUDE=LOCALLNG.MIX,MOVIES.MIX
			LOLG_HD_USE_ORIGINAL_MOVIES=1
			LOLG_HD_ALLOW_CRITICAL_HD_MIX=0
			WINEPREFIX=${WINEPREFIX:-"$BASE_DIR/output/lolg95_dgvoodoo_hdmix_wine_prefix"}
			LOLG_HD_USE_DXVK=${LOLG_HD_USE_DXVK:-1}
			if [ "$LOLG_HD_USE_DXVK" -eq 1 ]; then
				if [ -L "$WINEPREFIX/drive_c/windows/syswow64/d3d11.dll" ]; then
					LOLG_HD_SETUP_DXVK=${LOLG_HD_SETUP_DXVK:-0}
				else
					LOLG_HD_SETUP_DXVK=${LOLG_HD_SETUP_DXVK:-1}
				fi
				LOLG_HD_WINE_DLL_OVERRIDES=${LOLG_HD_WINE_DLL_OVERRIDES:-'ddraw,d3dimm=n,b;d3d8,d3d9,dxgi,d3d10,d3d10_1,d3d10core,d3d11=n,b'}
			else
				LOLG_HD_SETUP_DXVK=${LOLG_HD_SETUP_DXVK:-0}
			fi
			export LOLG_HD_RESOLUTION LOLG_HD_USE_DGVOODOO LOLG_HD_USE_LOCAL_DDRAW
			export LOLG_HD_DGVOODOO_FORCE_RESOLUTION LOLG_HD_DGVOODOO_OUTPUT_API LOLG_HD_DGVOODOO_SCALING
			export LOLG_HD_DGVOODOO_APP_CONTROLLED LOLG_HD_DGVOODOO_DESKTOP_RESOLUTION LOLG_HD_DGVOODOO_WINDOWED_ATTRIBUTES
			export LOLG_HD_WINE_RENDERER LOLG_HD_WINE_DIRECTDRAW_RENDERER LOLG_HD_WINE_VERSION LOLG_HD_USE_DXVK LOLG_HD_SETUP_DXVK
			export LOLG_HD_WINE_DLL_OVERRIDES LOLG_HD_WINE_WAIT
			export LOLG_HD_AUTO_RESIZE LOLG_HD_RESIZE_GAME_WINDOW LOLG_HD_LOCK_WINDOW_POSITION
			export LOLG_HD_WINE_USE_HD_MIX LOLG_HD_WINE_HD_EXCLUDE LOLG_HD_USE_ORIGINAL_MOVIES LOLG_HD_ALLOW_CRITICAL_HD_MIX
			export WINEPREFIX
			if [ -f "$WINEPREFIX/system.reg" ] && [ "$LOLG_HD_SETUP_DXVK" = 0 ]; then
				exec ./RUN_HD_WINE.sh --skip-wine-setup --detach "$@"
			fi
			exec ./RUN_HD_WINE.sh --detach "$@"
			;;
		wine-1440-hdmix|wine-hdmix|wine-movies-hd)
			require_executable ./RUN_HD_WINE.sh
			echo "ATTENTION: mode diagnostic VQA HD instable; crash connu a chaque animation." >&2
			LOLG_HD_RESOLUTION=1440x1080
			LOLG_HD_USE_DGVOODOO=1
			LOLG_HD_DGVOODOO_FORCE_RESOLUTION=${LOLG_HD_DGVOODOO_FORCE_RESOLUTION:-1}
			LOLG_HD_WINE_RENDERER=${LOLG_HD_WINE_RENDERER:-vulkan}
			LOLG_HD_WINE_DIRECTDRAW_RENDERER=${LOLG_HD_WINE_DIRECTDRAW_RENDERER:-gdi}
			LOLG_HD_WINE_WAIT=${LOLG_HD_WINE_WAIT:-1}
			LOLG_HD_LOCK_WINDOW_POSITION=${LOLG_HD_LOCK_WINDOW_POSITION:-0}
			LOLG_HD_WINE_USE_HD_MIX=1
			LOLG_HD_WINE_HD_EXCLUDE=LOCALLNG.MIX
			LOLG_HD_USE_ORIGINAL_MOVIES=0
			LOLG_HD_ALLOW_CRITICAL_HD_MIX=1
			WINEPREFIX=${WINEPREFIX:-"$BASE_DIR/output/lolg95_dgvoodoo_wine_prefix"}
			export LOLG_HD_RESOLUTION LOLG_HD_USE_DGVOODOO LOLG_HD_DGVOODOO_FORCE_RESOLUTION
			export LOLG_HD_WINE_RENDERER LOLG_HD_WINE_DIRECTDRAW_RENDERER LOLG_HD_WINE_WAIT LOLG_HD_LOCK_WINDOW_POSITION
			export LOLG_HD_WINE_USE_HD_MIX LOLG_HD_WINE_HD_EXCLUDE LOLG_HD_USE_ORIGINAL_MOVIES LOLG_HD_ALLOW_CRITICAL_HD_MIX
			export WINEPREFIX
			exec ./RUN_HD_WINE.sh --direct "$@"
			;;
		wine-1440-hdmix-lowmem|wine-hdmix-lowmem|wine-movies-hd-lowmem)
			require_executable ./RUN_HD_WINE.sh
			echo "ATTENTION: mode diagnostic VQA HD instable; -LOWMEM ne corrige pas le crash VQA connu." >&2
			LOLG_HD_RESOLUTION=1440x1080
			LOLG_HD_USE_DGVOODOO=1
			LOLG_HD_DGVOODOO_FORCE_RESOLUTION=${LOLG_HD_DGVOODOO_FORCE_RESOLUTION:-1}
			LOLG_HD_WINE_RENDERER=${LOLG_HD_WINE_RENDERER:-vulkan}
			LOLG_HD_WINE_DIRECTDRAW_RENDERER=${LOLG_HD_WINE_DIRECTDRAW_RENDERER:-gdi}
			LOLG_HD_WINE_WAIT=${LOLG_HD_WINE_WAIT:-1}
			LOLG_HD_LOCK_WINDOW_POSITION=${LOLG_HD_LOCK_WINDOW_POSITION:-0}
			LOLG_HD_WINE_USE_HD_MIX=1
			LOLG_HD_WINE_HD_EXCLUDE=LOCALLNG.MIX
			LOLG_HD_USE_ORIGINAL_MOVIES=0
			LOLG_HD_ALLOW_CRITICAL_HD_MIX=1
			LOLG_HD_GAME_LOWMEM=1
			LOLG_HD_LOW_MEMORY_CONFIG=1
			WINEPREFIX=${WINEPREFIX:-"$BASE_DIR/output/lolg95_dgvoodoo_wine_prefix"}
			export LOLG_HD_RESOLUTION LOLG_HD_USE_DGVOODOO LOLG_HD_DGVOODOO_FORCE_RESOLUTION
			export LOLG_HD_WINE_RENDERER LOLG_HD_WINE_DIRECTDRAW_RENDERER LOLG_HD_WINE_WAIT LOLG_HD_LOCK_WINDOW_POSITION
			export LOLG_HD_WINE_USE_HD_MIX LOLG_HD_WINE_HD_EXCLUDE LOLG_HD_USE_ORIGINAL_MOVIES LOLG_HD_ALLOW_CRITICAL_HD_MIX LOLG_HD_GAME_LOWMEM LOLG_HD_LOW_MEMORY_CONFIG
			export WINEPREFIX
			exec ./RUN_HD_WINE.sh --direct "$@"
			;;
		wine-locallng-hd-1440-experimental-lowmem|wine-1440-locallng-hd-experimental-lowmem|wine-locallng-1440-experimental-lowmem)
			require_executable ./RUN_HD_WINE_LOCALLNG_SIDECAR.sh
			echo "ATTENTION: mode diagnostic LOCALLNG_HD instable; -LOWMEM ne corrige pas le crash VQA connu." >&2
			LOLG_HD_RESOLUTION=1440x1080
			LOLG_HD_USE_DGVOODOO=1
			LOLG_HD_DGVOODOO_FORCE_RESOLUTION=${LOLG_HD_DGVOODOO_FORCE_RESOLUTION:-1}
			LOLG_HD_WINE_RENDERER=${LOLG_HD_WINE_RENDERER:-vulkan}
			LOLG_HD_WINE_DIRECTDRAW_RENDERER=${LOLG_HD_WINE_DIRECTDRAW_RENDERER:-gdi}
			LOLG_HD_WINE_WAIT=${LOLG_HD_WINE_WAIT:-1}
			LOLG_HD_LOCK_WINDOW_POSITION=${LOLG_HD_LOCK_WINDOW_POSITION:-0}
			LOLG_HD_WINE_USE_HD_MIX=${LOLG_HD_WINE_USE_HD_MIX:-1}
			LOLG_HD_USE_ORIGINAL_MOVIES=${LOLG_HD_USE_ORIGINAL_MOVIES:-1}
			LOLG_HD_GAME_LOWMEM=1
			LOLG_HD_LOW_MEMORY_CONFIG=1
			WINEPREFIX=${WINEPREFIX:-"$BASE_DIR/output/lolg95_dgvoodoo_wine_prefix"}
			export LOLG_HD_RESOLUTION LOLG_HD_USE_DGVOODOO LOLG_HD_DGVOODOO_FORCE_RESOLUTION
			export LOLG_HD_WINE_RENDERER LOLG_HD_WINE_DIRECTDRAW_RENDERER LOLG_HD_WINE_WAIT LOLG_HD_LOCK_WINDOW_POSITION
			export LOLG_HD_WINE_USE_HD_MIX LOLG_HD_USE_ORIGINAL_MOVIES LOLG_HD_GAME_LOWMEM LOLG_HD_LOW_MEMORY_CONFIG WINEPREFIX
			exec ./RUN_HD_WINE_LOCALLNG_SIDECAR.sh --direct "$@"
			;;
		wine-locallng-hd-1440-experimental|wine-1440-locallng-hd-experimental|wine-locallng-1440-experimental)
			require_executable ./RUN_HD_WINE_LOCALLNG_SIDECAR.sh
			echo "ATTENTION: mode diagnostic LOCALLNG_HD instable; crash connu a chaque animation." >&2
			LOLG_HD_RESOLUTION=1440x1080
			LOLG_HD_USE_DGVOODOO=1
			LOLG_HD_DGVOODOO_FORCE_RESOLUTION=${LOLG_HD_DGVOODOO_FORCE_RESOLUTION:-1}
			LOLG_HD_WINE_RENDERER=${LOLG_HD_WINE_RENDERER:-vulkan}
			LOLG_HD_WINE_DIRECTDRAW_RENDERER=${LOLG_HD_WINE_DIRECTDRAW_RENDERER:-gdi}
			LOLG_HD_WINE_WAIT=${LOLG_HD_WINE_WAIT:-1}
			LOLG_HD_LOCK_WINDOW_POSITION=${LOLG_HD_LOCK_WINDOW_POSITION:-0}
			LOLG_HD_WINE_USE_HD_MIX=${LOLG_HD_WINE_USE_HD_MIX:-1}
			WINEPREFIX=${WINEPREFIX:-"$BASE_DIR/output/lolg95_dgvoodoo_wine_prefix"}
			export LOLG_HD_RESOLUTION LOLG_HD_USE_DGVOODOO LOLG_HD_DGVOODOO_FORCE_RESOLUTION
			export LOLG_HD_WINE_RENDERER LOLG_HD_WINE_DIRECTDRAW_RENDERER LOLG_HD_WINE_WAIT LOLG_HD_LOCK_WINDOW_POSITION
			export LOLG_HD_WINE_USE_HD_MIX WINEPREFIX
			exec ./RUN_HD_WINE_LOCALLNG_SIDECAR.sh --direct "$@"
			;;
		wine-locallng-hd-dgvoodoo|wine-locallng-dgvoodoo|wine-dgvoodoo)
			require_executable ./RUN_HD_WINE_LOCALLNG_SIDECAR.sh
		LOLG_HD_RESOLUTION=${LOLG_HD_RESOLUTION:-1280x1024}
		LOLG_HD_USE_DGVOODOO=1
		LOLG_HD_DGVOODOO_FORCE_RESOLUTION=${LOLG_HD_DGVOODOO_FORCE_RESOLUTION:-1}
		LOLG_HD_WINE_RENDERER=${LOLG_HD_WINE_RENDERER:-vulkan}
		LOLG_HD_WINE_DIRECTDRAW_RENDERER=${LOLG_HD_WINE_DIRECTDRAW_RENDERER:-gdi}
		LOLG_HD_WINE_WAIT=${LOLG_HD_WINE_WAIT:-1}
		WINEPREFIX=${WINEPREFIX:-"$BASE_DIR/output/lolg95_dgvoodoo_wine_prefix"}
		export LOLG_HD_RESOLUTION LOLG_HD_USE_DGVOODOO LOLG_HD_DGVOODOO_FORCE_RESOLUTION
		export LOLG_HD_WINE_RENDERER LOLG_HD_WINE_DIRECTDRAW_RENDERER LOLG_HD_WINE_WAIT
		export WINEPREFIX
		exec ./RUN_HD_WINE_LOCALLNG_SIDECAR.sh "$@"
		;;
	prepare)
		require_executable ./RUN_HD_WINE.sh
		exec ./RUN_HD_WINE.sh --prepare-only "$@"
		;;
	repair)
		require_executable ./REPAIR_HD_WINE.sh
		exec ./REPAIR_HD_WINE.sh "$@"
		;;
	dosbox)
		require_executable ./RUN_HD.sh
		exec ./RUN_HD.sh "$@"
		;;
	dosbox-hd|dosbox-mod)
		require_executable ./RUN_HD_DOSBOX_MOD.sh
		exec ./RUN_HD_DOSBOX_MOD.sh "$@"
		;;
	dosbox-nglide-hdmix|dosbox-3dfx-hdmix|dosbox-voodoo-hdmix)
		require_executable ./RUN_HD_DOSBOX_NGLIDE.sh
		LOLG_HD_DOSBOX_NGLIDE_USE_HDMIX=1
		export LOLG_HD_DOSBOX_NGLIDE_USE_HDMIX
		exec ./RUN_HD_DOSBOX_NGLIDE.sh "$@"
		;;
	dosbox-nglide|dosbox-3dfx|dosbox-voodoo)
		require_executable ./RUN_HD_DOSBOX_NGLIDE.sh
		exec ./RUN_HD_DOSBOX_NGLIDE.sh "$@"
		;;
	check)
		require_executable ./CHECK_HD.sh
		if [ "$#" -eq 0 ]; then
			require_executable ./PACK_HD_RELEASE.sh
			require_executable ./VERIFY_HD_MANIFEST.sh
			./CHECK_HD.sh
			python3 tools/lolg_hd_resolution_check.py
			./PACK_HD_RELEASE.sh --skip-check
			exec ./VERIFY_HD_MANIFEST.sh
		fi
		exec ./CHECK_HD.sh "$@"
		;;
	status)
		exec python3 tools/lolg_hd_status.py "$@"
		;;
	stop)
		require_executable ./STOP_HD_WINE.sh
		exec ./STOP_HD_WINE.sh "$@"
		;;
	smoke)
		require_executable ./TEST_HD_WINE.sh
		exec ./TEST_HD_WINE.sh --resolution 1920x1080 "$@"
		;;
	smoke-1280)
		require_executable ./TEST_HD_WINE.sh
		exec ./TEST_HD_WINE.sh --resolution 1280x1024 \
			-o output/hd_wine_smoke_test_1280x1024 "$@"
		;;
	gpu)
		require_executable ./CHECK_HD_GPU.sh
		exec ./CHECK_HD_GPU.sh "$@"
		;;
	resolutions|resolution|check-resolutions)
		exec python3 tools/lolg_hd_resolution_check.py "$@"
		;;
	manifest|release)
		require_executable ./PACK_HD_RELEASE.sh
		exec ./PACK_HD_RELEASE.sh "$@"
		;;
	verify-manifest|verify)
		require_executable ./VERIFY_HD_MANIFEST.sh
		exec ./VERIFY_HD_MANIFEST.sh "$@"
		;;
	git-audit|git)
		exec python3 tools/lolg_hd_git_audit.py "$@"
		;;
	verify-support|support-verify)
		exec python3 tools/lolg_hd_support_manifest_verify.py "$@"
		;;
	verify-support-archive|support-archive-verify)
		exec python3 tools/lolg_hd_support_archive_verify.py "$@"
		;;
	install-desktop|desktop-install)
		require_executable ./INSTALL_HD_DESKTOP.sh
		exec ./INSTALL_HD_DESKTOP.sh "$@"
		;;
	uninstall-desktop|desktop-uninstall)
		require_executable ./UNINSTALL_HD_DESKTOP.sh
		exec ./UNINSTALL_HD_DESKTOP.sh "$@"
		;;
	support|collect-support)
		require_executable ./COLLECT_HD_SUPPORT.sh
		exec ./COLLECT_HD_SUPPORT.sh "$@"
		;;
	notice)
		exec sed -n '1,220p' LANCER_HD.txt
		;;
	*)
		echo "Commande inconnue: $command_name" >&2
		usage >&2
		exit 2
		;;
esac
