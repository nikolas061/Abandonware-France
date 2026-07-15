#!/usr/bin/env bash

set -euo pipefail

BASE_DIR=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
SOURCE_GAME_DIR="$BASE_DIR/C/LOLG"
HD_MIX_DIR="$BASE_DIR/mod_mix_vqa_fullhd"
RUNTIME_ROOT="${LOLG_HD_WINE_RUNTIME_ROOT:-$BASE_DIR/output/lolg95_fullhd_wine_runtime}"
STAGE_DIR="$RUNTIME_ROOT/WESTWOOD/LOLG"
WINEPREFIX="${WINEPREFIX:-$BASE_DIR/output/lolg95_fullhd_wine_prefix}"
RESOLUTION="${LOLG_HD_RESOLUTION:-1920x1080}"
LOLG_HD_USE_ORIGINAL_MOVIES="${LOLG_HD_USE_ORIGINAL_MOVIES:-1}"
LOLG_HD_WINE_HD_EXCLUDE="${LOLG_HD_WINE_HD_EXCLUDE-LOCALLNG.MIX,MOVIES.MIX}"
LOLG_HD_WINE_EXE_NAME="${LOLG_HD_WINE_EXE_NAME:-LOLG95.EXE}"
LOLG_HD_WINE_EXE_SOURCE="${LOLG_HD_WINE_EXE_SOURCE:-}"
LOLG_HD_WINE_EXTRA_MIX_DIR="${LOLG_HD_WINE_EXTRA_MIX_DIR:-}"
LOLG_HD_WINE_EXTRA_MIX_NOTE="${LOLG_HD_WINE_EXTRA_MIX_NOTE:-}"
LOLG_HD_WINE_MOVIES_LABEL="${LOLG_HD_WINE_MOVIES_LABEL:-}"
LOLG_HD_WINE_USE_HD_MIX="${LOLG_HD_WINE_USE_HD_MIX:-1}"
LOLG_HD_WINE_VERSION="${LOLG_HD_WINE_VERSION:-}"
LOLG_HD_USE_DXVK="${LOLG_HD_USE_DXVK:-0}"
LOLG_HD_SETUP_DXVK="${LOLG_HD_SETUP_DXVK:-0}"
DXVK_SETUP_BIN="${DXVK_SETUP:-dxvk-setup}"
LOLG_HD_USE_DGVOODOO="${LOLG_HD_USE_DGVOODOO:-0}"
LOLG_HD_USE_LOCAL_DDRAW="${LOLG_HD_USE_LOCAL_DDRAW:-0}"
LOLG_HD_DGVOODOO_SOURCE_DIR="${LOLG_HD_DGVOODOO_SOURCE_DIR:-$SOURCE_GAME_DIR}"
LOLG_HD_USE_NGLIDE="${LOLG_HD_USE_NGLIDE:-0}"
LOLG_HD_NGLIDE_DIR="${LOLG_HD_NGLIDE_DIR:-}"
LOLG_HD_USE_3DFX_CONFIG="${LOLG_HD_USE_3DFX_CONFIG:-0}"
LOLG_HD_DISABLE_3D_ACCEL="${LOLG_HD_DISABLE_3D_ACCEL:-0}"
LOLG_HD_NGLIDE_BACKEND="${LOLG_HD_NGLIDE_BACKEND:-}"
LOLG_HD_NGLIDE_RESOLUTION="${LOLG_HD_NGLIDE_RESOLUTION:-}"
LOLG_HD_NGLIDE_ASPECT="${LOLG_HD_NGLIDE_ASPECT:-}"
LOLG_HD_NGLIDE_REFRESH="${LOLG_HD_NGLIDE_REFRESH:-}"
LOLG_HD_NGLIDE_VSYNC="${LOLG_HD_NGLIDE_VSYNC:-}"
LOLG_HD_NGLIDE_GAMMA="${LOLG_HD_NGLIDE_GAMMA:-}"
LOLG_HD_NGLIDE_SPLASH="${LOLG_HD_NGLIDE_SPLASH:-}"
LOLG_HD_DGVOODOO_OUTPUT_API="${LOLG_HD_DGVOODOO_OUTPUT_API:-d3d11_fl11_0}"
LOLG_HD_DGVOODOO_FULLSCREEN="${LOLG_HD_DGVOODOO_FULLSCREEN:-false}"
LOLG_HD_DGVOODOO_APP_CONTROLLED="${LOLG_HD_DGVOODOO_APP_CONTROLLED:-false}"
LOLG_HD_DGVOODOO_FORCE_RESOLUTION="${LOLG_HD_DGVOODOO_FORCE_RESOLUTION:-0}"
LOLG_HD_DGVOODOO_SCALING="${LOLG_HD_DGVOODOO_SCALING:-stretched}"
LOLG_HD_DGVOODOO_DESKTOP_RESOLUTION="${LOLG_HD_DGVOODOO_DESKTOP_RESOLUTION-$RESOLUTION}"
LOLG_HD_DGVOODOO_WINDOWED_ATTRIBUTES="${LOLG_HD_DGVOODOO_WINDOWED_ATTRIBUTES-borderless}"
LOLG_HD_DGVOODOO_VRAM="${LOLG_HD_DGVOODOO_VRAM:-512}"
LOLG_HD_DGVOODOO_GLIDE_RAM="${LOLG_HD_DGVOODOO_GLIDE_RAM:-8}"
LOLG_HD_DGVOODOO_TMU_MEMORY="${LOLG_HD_DGVOODOO_TMU_MEMORY:-4096}"
LOLG_HD_DGVOODOO_FAST_VIDEO_MEMORY="${LOLG_HD_DGVOODOO_FAST_VIDEO_MEMORY:-false}"
LOLG_HD_DGVOODOO_PRIMARY_SURFACE_BATCHED="${LOLG_HD_DGVOODOO_PRIMARY_SURFACE_BATCHED:-false}"
LOLG_HD_DGVOODOO_RT_TEXTURES_FORCE_SCALE_MSAA="${LOLG_HD_DGVOODOO_RT_TEXTURES_FORCE_SCALE_MSAA:-true}"
LOLG_HD_DGVOODOO_SMOOTHED_DEPTH_SAMPLING="${LOLG_HD_DGVOODOO_SMOOTHED_DEPTH_SAMPLING:-true}"
LOLG_HD_DGVOODOO_FORCE_VSYNC="${LOLG_HD_DGVOODOO_FORCE_VSYNC:-false}"
WINE_RENDERER_EXPLICIT=${LOLG_HD_WINE_RENDERER+x}
WINE_RENDERER="${LOLG_HD_WINE_RENDERER:-gdi}"
WINE_DIRECTDRAW_RENDERER_EXPLICIT=${LOLG_HD_WINE_DIRECTDRAW_RENDERER+x}
WINE_DIRECTDRAW_RENDERER="${LOLG_HD_WINE_DIRECTDRAW_RENDERER:-$WINE_RENDERER}"
LOLG_HD_WINE_VIDEO_MEMORY_SIZE="${LOLG_HD_WINE_VIDEO_MEMORY_SIZE:-}"
WINE_DESKTOP="${LOLG_HD_WINE_DESKTOP:-LOLG_HD,$RESOLUTION}"
WINE_BIN="${WINE:-wine}"
WINEBOOT_BIN="${WINEBOOT:-wineboot}"
WINEDEBUG="${WINEDEBUG:--all}"
LOLG_HD_WINE_USE_XRANDR="${LOLG_HD_WINE_USE_XRANDR:-N}"
LOLG_HD_WINE_USE_XVIDMODE="${LOLG_HD_WINE_USE_XVIDMODE:-N}"
LOLG_HD_WINE_DLL_OVERRIDES_EXPLICIT=${LOLG_HD_WINE_DLL_OVERRIDES+x}
LOLG_HD_WINE_DLL_OVERRIDES="${LOLG_HD_WINE_DLL_OVERRIDES:-ddraw,d3dimm,d3d8=b}"
LOLG_HD_AUTO_RESIZE="${LOLG_HD_AUTO_RESIZE:-1}"
LOLG_HD_RESIZE_GAME_WINDOW="${LOLG_HD_RESIZE_GAME_WINDOW:-1}"
LOLG_HD_RESIZE_GAME_WINDOW_DELAY="${LOLG_HD_RESIZE_GAME_WINDOW_DELAY:-6}"
LOLG_HD_RESIZE_GAME_WINDOW_HOLD="${LOLG_HD_RESIZE_GAME_WINDOW_HOLD:-45}"
LOLG_HD_WINDOW_SEARCH_TIMEOUT="${LOLG_HD_WINDOW_SEARCH_TIMEOUT:-30}"
LOLG_HD_WINE_PROCESS_TIMEOUT="${LOLG_HD_WINE_PROCESS_TIMEOUT:-45}"
LOLG_HD_LOCK_WINDOW_POSITION="${LOLG_HD_LOCK_WINDOW_POSITION:-1}"
LOLG_HD_STAGE_LOCK_TIMEOUT="${LOLG_HD_STAGE_LOCK_TIMEOUT:-10}"
LOLG_HD_GAME_LOWMEM="${LOLG_HD_GAME_LOWMEM:-0}"
LOLG_HD_LOW_MEMORY_CONFIG="${LOLG_HD_LOW_MEMORY_CONFIG:-0}"
LOLG_HD_ALLOW_CRITICAL_HD_MIX="${LOLG_HD_ALLOW_CRITICAL_HD_MIX:-0}"
ALLOW_UNSUPPORTED_RESOLUTION="${LOLG_HD_ALLOW_UNSUPPORTED_RESOLUTION:-0}"
PREPARE_ONLY=0
DRY_RUN=0
SKIP_WINE_SETUP=0
WAIT_FOR_EXIT="${LOLG_HD_WINE_WAIT:-1}"
DIRECT_LAUNCH=0

usage() {
	cat <<'EOF'
Usage: ./RUN_HD_WINE.sh [options]

Options:
  --resolution WIDTHxHEIGHT  Wine virtual desktop size (default: 1920x1080)
  --allow-unsupported-resolution
                            Permit an unverified desktop size for experiments
  --prepare-only            Prepare the Full HD Wine stage, do not launch
  --dry-run                 Print the Wine command, do not run Wine setup or launch
  --skip-wine-setup         Do not touch the Wine prefix registry
  --wait                    Launch through Wine desktop and wait for LOLG95.EXE
  --detach                  Launch through explorer and return after starting
  --direct                  Launch LOLG95.EXE directly, without Wine virtual desktop
  --lowmem                  Pass -LOWMEM to the game executable
  --no-lowmem               Do not pass -LOWMEM to the game executable
  --low-memory-config       Use smaller in-game texture cache/settings
  --no-low-memory-config    Keep normal in-game texture cache/settings
  --use-original-movies     Use original MOVIES.MIX to avoid title VQA crash (default)
  --use-hd-movies           Use generated HD MOVIES.MIX
  --use-dgvoodoo            Keep local dgVoodoo files in the stage and load them native
  --no-dgvoodoo             Remove local dgVoodoo files from the stage (default)
  --use-dxvk                Prefer native DXVK DLL overrides for D3D8/9/10/11
  --setup-dxvk              Install DXVK into this Wine prefix before launch
  --no-dxvk                 Disable DXVK-specific DLL overrides
  --wine-version VERSION    Force Wine Windows version for this prefix/app
  --win95                   Shortcut for --wine-version win95
  --no-wine-version         Preserve the existing Wine Windows version
  --use-local-ddraw         Keep C/LOLG/DDraw.dll in the stage and load it as native
                            while still excluding dgVoodoo config/D3D DLLs
  --no-local-ddraw          Remove local DDraw.dll from the stage (default)
  --use-nglide              Use nGlide/Glide DLLs and the 3dfx game config
  --no-nglide               Disable nGlide mode (default)
  --nglide-dir DIR          Directory containing glide2x.dll/glide3x.dll
  --use-3dfx-config         Copy OPT3DFX.INI over staged OPTIONS.INI
  --no-3dfx-config          Keep staged OPTIONS.INI as-is
  --nglide-backend N        nGlide backend index: 0 automatic, 1 DirectX, 2 Vulkan
  --nglide-resolution N     nGlide resolution index (21 is 1920x1080)
  --hd-exclude=A,B          Keep these MIX files original in the Wine stage
                            (default: LOCALLNG.MIX,MOVIES.MIX)
  --exe-source PATH         Copy this patched executable over LOLG95.EXE in the stage
  --extra-mix-dir DIR       Link additional MIX files from DIR into the stage
  --auto-resize             Keep the Wine desktop resized with xdotool (default)
  --no-auto-resize          Do not resize the Wine desktop with xdotool
  --resize-game-window      Resize the inner game window with xdotool (default)
  --no-resize-game-window   Do not resize the inner game window with xdotool
  --resize-game-delay SECONDS
                            Wait before resizing the inner game window (default: 6)
  --resize-game-hold SECONDS
                            Keep enforcing inner game window size after first detection (default: 45)
  -h, --help                Show this help

Environment:
  LOLG_HD_RESOLUTION        Same as --resolution. Verified values: 1920x1080, 1440x1080, 1280x1024
  LOLG_HD_ALLOW_UNSUPPORTED_RESOLUTION=1 permits other WIDTHxHEIGHT values
  LOLG_HD_USE_ORIGINAL_MOVIES Use original MOVIES.MIX instead of HD MOVIES.MIX (default: 1)
  LOLG_HD_USE_DGVOODOO      Use local dgVoodoo files from C/LOLG (default: 0)
  LOLG_HD_DGVOODOO_SOURCE_DIR
                            Directory containing DDraw.dll/D3DImm.dll/D3D8.dll/dgVoodoo.conf
                            when dgVoodoo is active (default: C/LOLG)
  LOLG_HD_USE_LOCAL_DDRAW   Use the local C/LOLG/DDraw.dll wrapper without dgVoodoo (default: 0)
  LOLG_HD_USE_NGLIDE        Use nGlide/Glide DLLs and native Glide overrides (default: 0)
  LOLG_HD_NGLIDE_DIR        Directory containing glide2x.dll/glide3x.dll if not already installed
  LOLG_HD_USE_3DFX_CONFIG   Use OPT3DFX.INI as OPTIONS.INI in the stage (default: 0)
  LOLG_HD_NGLIDE_BACKEND    nGlide backend index: 0 automatic, 1 DirectX, 2 Vulkan
  LOLG_HD_NGLIDE_RESOLUTION nGlide resolution index; 21 selects 1920x1080 in nGlide 2.10
  LOLG_HD_NGLIDE_ASPECT     nGlide aspect index
  LOLG_HD_NGLIDE_REFRESH    nGlide refresh index
  LOLG_HD_NGLIDE_VSYNC      nGlide VSync index
  LOLG_HD_NGLIDE_GAMMA      nGlide gamma index
  LOLG_HD_NGLIDE_SPLASH     nGlide splash index
  LOLG_HD_DGVOODOO_OUTPUT_API dgVoodoo OutputAPI when dgVoodoo is active
                            (default: d3d11_fl11_0)
  LOLG_HD_DGVOODOO_FULLSCREEN dgVoodoo FullScreenMode value (default: false)
  LOLG_HD_DGVOODOO_APP_CONTROLLED dgVoodoo AppControlledScreenMode value
                            (default: false)
  LOLG_HD_DGVOODOO_FORCE_RESOLUTION Force dgVoodoo internal rendering to
                            WIDTHxHEIGHT instead of scaling original game mode
                            (default: 0)
  LOLG_HD_DGVOODOO_SCALING dgVoodoo ScalingMode value (default: stretched)
  LOLG_HD_DGVOODOO_VRAM    DirectX VRAM exposed by dgVoodoo, e.g. 512 or 2GB
  LOLG_HD_DGVOODOO_GLIDE_RAM Glide OnboardRAM in MB
  LOLG_HD_DGVOODOO_TMU_MEMORY Glide TMU memory in kB
  LOLG_HD_DGVOODOO_FAST_VIDEO_MEMORY Enable dgVoodoo FastVideoMemoryAccess
  LOLG_HD_DGVOODOO_PRIMARY_SURFACE_BATCHED Batch DirectDraw primary surface updates
  LOLG_HD_WINE_HD_EXCLUDE   Comma-separated MIX names kept original
                            (default: LOCALLNG.MIX,MOVIES.MIX)
  LOLG_HD_WINE_USE_HD_MIX   Link generated HD MIX files when available
                            (default: 1; use 0 for stable original animations)
  LOLG_HD_WINE_EXE_SOURCE   Patched executable copied over LOLG95.EXE in the stage
  LOLG_HD_WINE_EXTRA_MIX_DIR Directory of extra MIX sidecars linked into the stage
  LOLG_HD_WINE_EXTRA_MIX_NOTE Optional note printed when extra MIX sidecars are used
  LOLG_HD_WINE_MOVIES_LABEL Optional label printed for MOVIES.MIX source
  LOLG_HD_WINE_VERSION      Force Wine Windows version, for example win95
                            (default: preserve prefix setting)
  LOLG_HD_USE_DXVK          Use DXVK DLL override order for D3D8/9/10/11 (default: 0)
  LOLG_HD_SETUP_DXVK        Run dxvk-setup install -y for this prefix first (default: 0)
  LOLG_HD_WINE_RENDERER     Wine renderer registry value (default: gdi)
	  LOLG_HD_WINE_DIRECTDRAW_RENDERER
	                            Wine DirectDrawRenderer value (default: same as renderer;
	                            use none to remove the registry override)
	  LOLG_HD_WINE_DLL_OVERRIDES Wine DLL overrides (default: ddraw,d3dimm,d3d8=b)
	  LOLG_HD_WINE_USE_XRANDR  Wine X11 UseXRandR registry value, Y or N
	                            (default: N)
	  LOLG_HD_WINE_USE_XVIDMODE Wine X11 UseXVidMode registry value, Y or N
	                            (default: N)
	  LOLG_HD_WINE_VIDEO_MEMORY_SIZE
	                            Wine Direct3D VideoMemorySize in MB
	  LOLG_HD_AUTO_RESIZE       Resize Wine desktop with xdotool (default: 1)
  LOLG_HD_RESIZE_GAME_WINDOW Resize inner game window too (default: 1)
  LOLG_HD_RESIZE_GAME_WINDOW_DELAY Seconds before resizing inner game window (default: 6)
  LOLG_HD_RESIZE_GAME_WINDOW_HOLD Seconds to keep enforcing game size (default: 45)
  LOLG_HD_WINDOW_SEARCH_TIMEOUT Seconds to keep looking for Wine/game windows
                            after a detached launcher returns (default: 30)
  LOLG_HD_WINE_PROCESS_TIMEOUT Seconds to wait for LOLG95.EXE to appear
                            in --wait mode (default: 45)
  LOLG_HD_LOCK_WINDOW_POSITION Lock Wine/game windows at 0,0 while resizing
                            (default: 1; 1440 launcher sets 0)
  LOLG_HD_GAME_LOWMEM       Pass -LOWMEM to LOLG95.EXE (default: 0)
  LOLG_HD_LOW_MEMORY_CONFIG Set Texture_Resolution=Low and Texture_Cache=Small
                            in staged INI files (default: 0)
  LOLG_HD_DISABLE_3D_ACCEL  Set Acceleration_Toggle=Off in staged OPTIONS.INI
                            for safer VQA/DirectDraw launches (default: 0)
  LOLG_HD_WINE_WAIT         Wait for the game process (default: 1)
  WINEPREFIX                Wine prefix (default: output/lolg95_fullhd_wine_prefix)
  WINE                      Wine binary (default: wine)
EOF
}

while [ "$#" -gt 0 ]; do
	case "$1" in
		--resolution)
			[ "$#" -ge 2 ] || { echo "--resolution demande une valeur" >&2; exit 2; }
			RESOLUTION="$2"
			WINE_DESKTOP="LOLG_HD,$RESOLUTION"
			shift 2
			;;
		--allow-unsupported-resolution)
			ALLOW_UNSUPPORTED_RESOLUTION=1
			shift
			;;
		--prepare-only)
			PREPARE_ONLY=1
			shift
			;;
		--dry-run)
			DRY_RUN=1
			shift
			;;
		--skip-wine-setup)
			SKIP_WINE_SETUP=1
			shift
			;;
		--wait)
			WAIT_FOR_EXIT=1
			shift
			;;
		--detach)
			WAIT_FOR_EXIT=0
			shift
			;;
		--direct)
			DIRECT_LAUNCH=1
			shift
			;;
		--lowmem)
			LOLG_HD_GAME_LOWMEM=1
			shift
			;;
		--no-lowmem)
			LOLG_HD_GAME_LOWMEM=0
			shift
			;;
		--low-memory-config)
			LOLG_HD_LOW_MEMORY_CONFIG=1
			shift
			;;
		--no-low-memory-config)
			LOLG_HD_LOW_MEMORY_CONFIG=0
			shift
			;;
		--use-original-movies)
			LOLG_HD_USE_ORIGINAL_MOVIES=1
			shift
			;;
		--use-hd-movies)
			LOLG_HD_USE_ORIGINAL_MOVIES=0
			LOLG_HD_ALLOW_CRITICAL_HD_MIX=1
			shift
			;;
		--use-dgvoodoo)
			LOLG_HD_USE_DGVOODOO=1
			LOLG_HD_USE_LOCAL_DDRAW=1
			shift
			;;
		--no-dgvoodoo)
			LOLG_HD_USE_DGVOODOO=0
			shift
			;;
		--use-dxvk)
			LOLG_HD_USE_DXVK=1
			LOLG_HD_WINE_DLL_OVERRIDES='ddraw,d3dimm=b;d3d8,d3d9,dxgi,d3d10,d3d10_1,d3d10core,d3d11=n,b'
			shift
			;;
		--setup-dxvk)
			LOLG_HD_USE_DXVK=1
			LOLG_HD_SETUP_DXVK=1
			LOLG_HD_WINE_DLL_OVERRIDES='ddraw,d3dimm=b;d3d8,d3d9,dxgi,d3d10,d3d10_1,d3d10core,d3d11=n,b'
			shift
			;;
		--no-dxvk)
			LOLG_HD_USE_DXVK=0
			LOLG_HD_SETUP_DXVK=0
			LOLG_HD_WINE_DLL_OVERRIDES='ddraw,d3dimm,d3d8=b'
			shift
			;;
		--wine-version)
			[ "$#" -ge 2 ] || { echo "--wine-version demande une valeur" >&2; exit 2; }
			LOLG_HD_WINE_VERSION="$2"
			shift 2
			;;
		--wine-version=*)
			LOLG_HD_WINE_VERSION=${1#--wine-version=}
			shift
			;;
		--win95)
			LOLG_HD_WINE_VERSION=win95
			shift
			;;
		--no-wine-version)
			LOLG_HD_WINE_VERSION=
			shift
			;;
		--use-local-ddraw)
			LOLG_HD_USE_LOCAL_DDRAW=1
			shift
			;;
		--no-local-ddraw)
			LOLG_HD_USE_LOCAL_DDRAW=0
			shift
			;;
		--use-nglide)
			LOLG_HD_USE_NGLIDE=1
			LOLG_HD_USE_3DFX_CONFIG=1
			shift
			;;
		--no-nglide)
			LOLG_HD_USE_NGLIDE=0
			shift
			;;
		--nglide-dir)
			[ "$#" -ge 2 ] || { echo "--nglide-dir demande une valeur" >&2; exit 2; }
			LOLG_HD_NGLIDE_DIR="$2"
			shift 2
			;;
		--nglide-dir=*)
			LOLG_HD_NGLIDE_DIR=${1#--nglide-dir=}
			shift
			;;
		--nglide-backend)
			[ "$#" -ge 2 ] || { echo "--nglide-backend demande une valeur" >&2; exit 2; }
			LOLG_HD_NGLIDE_BACKEND="$2"
			shift 2
			;;
		--nglide-backend=*)
			LOLG_HD_NGLIDE_BACKEND=${1#--nglide-backend=}
			shift
			;;
		--nglide-resolution)
			[ "$#" -ge 2 ] || { echo "--nglide-resolution demande une valeur" >&2; exit 2; }
			LOLG_HD_NGLIDE_RESOLUTION="$2"
			shift 2
			;;
		--nglide-resolution=*)
			LOLG_HD_NGLIDE_RESOLUTION=${1#--nglide-resolution=}
			shift
			;;
		--use-3dfx-config)
			LOLG_HD_USE_3DFX_CONFIG=1
			shift
			;;
		--no-3dfx-config)
			LOLG_HD_USE_3DFX_CONFIG=0
			shift
			;;
		--hd-exclude=*)
			LOLG_HD_WINE_HD_EXCLUDE=${1#--hd-exclude=}
			shift
			;;
		--exe-source)
			[ "$#" -ge 2 ] || { echo "--exe-source demande une valeur" >&2; exit 2; }
			LOLG_HD_WINE_EXE_SOURCE="$2"
			shift 2
			;;
		--exe-source=*)
			LOLG_HD_WINE_EXE_SOURCE=${1#--exe-source=}
			shift
			;;
		--extra-mix-dir)
			[ "$#" -ge 2 ] || { echo "--extra-mix-dir demande une valeur" >&2; exit 2; }
			LOLG_HD_WINE_EXTRA_MIX_DIR="$2"
			shift 2
			;;
		--extra-mix-dir=*)
			LOLG_HD_WINE_EXTRA_MIX_DIR=${1#--extra-mix-dir=}
			shift
			;;
		--auto-resize)
			LOLG_HD_AUTO_RESIZE=1
			shift
			;;
		--no-auto-resize)
			LOLG_HD_AUTO_RESIZE=0
			shift
			;;
		--resize-game-window)
			LOLG_HD_RESIZE_GAME_WINDOW=1
			shift
			;;
		--no-resize-game-window)
			LOLG_HD_RESIZE_GAME_WINDOW=0
			shift
			;;
		--resize-game-delay)
			[ "$#" -ge 2 ] || { echo "--resize-game-delay demande une valeur" >&2; exit 2; }
			LOLG_HD_RESIZE_GAME_WINDOW_DELAY="$2"
			shift 2
			;;
		--resize-game-hold)
			[ "$#" -ge 2 ] || { echo "--resize-game-hold demande une valeur" >&2; exit 2; }
			LOLG_HD_RESIZE_GAME_WINDOW_HOLD="$2"
			shift 2
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

case "$RESOLUTION" in
	*[!0-9x]*|x*|*x|*x*x*)
		echo "Resolution invalide: $RESOLUTION (format attendu: 1920x1080)" >&2
		exit 2
		;;
esac

case "$LOLG_HD_RESIZE_GAME_WINDOW_DELAY" in
	''|*[!0-9]*)
		echo "Delai resize invalide: $LOLG_HD_RESIZE_GAME_WINDOW_DELAY" >&2
		exit 2
		;;
esac

case "$LOLG_HD_RESIZE_GAME_WINDOW_HOLD" in
	''|*[!0-9]*)
		echo "Maintien resize invalide: $LOLG_HD_RESIZE_GAME_WINDOW_HOLD" >&2
		exit 2
		;;
esac

case "$LOLG_HD_WINDOW_SEARCH_TIMEOUT" in
	''|*[!0-9]*)
		echo "Timeout recherche fenetre invalide: $LOLG_HD_WINDOW_SEARCH_TIMEOUT" >&2
		exit 2
		;;
esac

case "$LOLG_HD_STAGE_LOCK_TIMEOUT" in
	''|*[!0-9]*)
		echo "Timeout verrou stage invalide: $LOLG_HD_STAGE_LOCK_TIMEOUT" >&2
		exit 2
		;;
esac

case "$LOLG_HD_WINE_USE_XRANDR" in
	Y|N)
		;;
	*)
		echo "LOLG_HD_WINE_USE_XRANDR invalide: $LOLG_HD_WINE_USE_XRANDR (Y ou N attendu)" >&2
		exit 2
		;;
esac

case "$LOLG_HD_WINE_USE_XVIDMODE" in
	Y|N)
		;;
	*)
		echo "LOLG_HD_WINE_USE_XVIDMODE invalide: $LOLG_HD_WINE_USE_XVIDMODE (Y ou N attendu)" >&2
		exit 2
		;;
esac

case "$LOLG_HD_LOCK_WINDOW_POSITION" in
	0|1)
		;;
	*)
		echo "LOLG_HD_LOCK_WINDOW_POSITION invalide: $LOLG_HD_LOCK_WINDOW_POSITION (0 ou 1 attendu)" >&2
		exit 2
		;;
esac

case "$LOLG_HD_GAME_LOWMEM" in
	0|1)
		;;
	*)
		echo "LOLG_HD_GAME_LOWMEM invalide: $LOLG_HD_GAME_LOWMEM (0 ou 1 attendu)" >&2
		exit 2
		;;
esac

case "$LOLG_HD_LOW_MEMORY_CONFIG" in
	0|1)
		;;
	*)
		echo "LOLG_HD_LOW_MEMORY_CONFIG invalide: $LOLG_HD_LOW_MEMORY_CONFIG (0 ou 1 attendu)" >&2
		exit 2
		;;
esac

case "$LOLG_HD_USE_ORIGINAL_MOVIES" in
	0|1)
		;;
	*)
		echo "LOLG_HD_USE_ORIGINAL_MOVIES invalide: $LOLG_HD_USE_ORIGINAL_MOVIES (0 ou 1 attendu)" >&2
		exit 2
		;;
esac

case "$LOLG_HD_WINE_USE_HD_MIX" in
	0|1)
		;;
	*)
		echo "LOLG_HD_WINE_USE_HD_MIX invalide: $LOLG_HD_WINE_USE_HD_MIX (0 ou 1 attendu)" >&2
		exit 2
		;;
esac

case "$LOLG_HD_USE_DXVK" in
	0|1)
		;;
	*)
		echo "LOLG_HD_USE_DXVK invalide: $LOLG_HD_USE_DXVK (0 ou 1 attendu)" >&2
		exit 2
		;;
esac

case "$LOLG_HD_SETUP_DXVK" in
	0|1)
		;;
	*)
		echo "LOLG_HD_SETUP_DXVK invalide: $LOLG_HD_SETUP_DXVK (0 ou 1 attendu)" >&2
		exit 2
		;;
esac

case "$LOLG_HD_ALLOW_CRITICAL_HD_MIX" in
	0|1)
		;;
	*)
		echo "LOLG_HD_ALLOW_CRITICAL_HD_MIX invalide: $LOLG_HD_ALLOW_CRITICAL_HD_MIX (0 ou 1 attendu)" >&2
		exit 2
		;;
esac

case "$LOLG_HD_USE_LOCAL_DDRAW" in
	0|1)
		;;
	*)
		echo "LOLG_HD_USE_LOCAL_DDRAW invalide: $LOLG_HD_USE_LOCAL_DDRAW (0 ou 1 attendu)" >&2
		exit 2
		;;
esac

case "$LOLG_HD_USE_NGLIDE" in
	0|1)
		;;
	*)
		echo "LOLG_HD_USE_NGLIDE invalide: $LOLG_HD_USE_NGLIDE (0 ou 1 attendu)" >&2
		exit 2
		;;
esac

case "$LOLG_HD_USE_3DFX_CONFIG" in
	0|1)
		;;
	*)
		echo "LOLG_HD_USE_3DFX_CONFIG invalide: $LOLG_HD_USE_3DFX_CONFIG (0 ou 1 attendu)" >&2
		exit 2
		;;
esac

case "$LOLG_HD_USE_DGVOODOO" in
	0|1)
		;;
	*)
		echo "LOLG_HD_USE_DGVOODOO invalide: $LOLG_HD_USE_DGVOODOO (0 ou 1 attendu)" >&2
		exit 2
		;;
esac

case "$LOLG_HD_DGVOODOO_FORCE_RESOLUTION" in
	0|1)
		;;
	*)
		echo "LOLG_HD_DGVOODOO_FORCE_RESOLUTION invalide: $LOLG_HD_DGVOODOO_FORCE_RESOLUTION (0 ou 1 attendu)" >&2
		exit 2
		;;
esac

if [ "$LOLG_HD_USE_DGVOODOO" -eq 1 ]; then
	LOLG_HD_USE_LOCAL_DDRAW=1
	if [ -z "$LOLG_HD_WINE_DLL_OVERRIDES_EXPLICIT" ]; then
		LOLG_HD_WINE_DLL_OVERRIDES='ddraw,d3dimm,d3d8=n,b'
	fi
	if [ -z "$WINE_RENDERER_EXPLICIT" ]; then
		WINE_RENDERER=vulkan
	fi
	if [ -z "$WINE_DIRECTDRAW_RENDERER_EXPLICIT" ]; then
		WINE_DIRECTDRAW_RENDERER=$WINE_RENDERER
	fi
elif [ "$LOLG_HD_USE_LOCAL_DDRAW" -eq 1 ] && [ -z "$LOLG_HD_WINE_DLL_OVERRIDES_EXPLICIT" ]; then
	LOLG_HD_WINE_DLL_OVERRIDES='ddraw=n,b;d3dimm,d3d8=b'
fi

if [ "$LOLG_HD_USE_DXVK" -eq 1 ] && [ -z "$LOLG_HD_WINE_DLL_OVERRIDES_EXPLICIT" ]; then
	LOLG_HD_WINE_DLL_OVERRIDES='ddraw,d3dimm=b;d3d8,d3d9,dxgi,d3d10,d3d10_1,d3d10core,d3d11=n,b'
fi

case "$WINE_DIRECTDRAW_RENDERER" in
	none|off|disable|disabled|0)
		WINE_DIRECTDRAW_RENDERER=none
		;;
esac

if [ "$ALLOW_UNSUPPORTED_RESOLUTION" -ne 1 ]; then
	case "$RESOLUTION" in
			1920x1080|1440x1080|1280x1024)
				;;
			*)
				echo "Resolution non supportee: $RESOLUTION" >&2
				echo "Resolutions verifiees: 1920x1080, 1440x1080 ou 1280x1024" >&2
				echo "Pour un essai volontaire: --allow-unsupported-resolution" >&2
				exit 2
			;;
	esac
fi

require_file() {
	if [ ! -e "$1" ]; then
		echo "Fichier introuvable: $1" >&2
		exit 1
	fi
}

require_file "$SOURCE_GAME_DIR/LOLG95.EXE"
if [ "$LOLG_HD_WINE_USE_HD_MIX" -eq 1 ]; then
	require_file "$HD_MIX_DIR/MOVIES.MIX"
fi
if [ -n "$LOLG_HD_WINE_EXE_SOURCE" ]; then
	require_file "$LOLG_HD_WINE_EXE_SOURCE"
fi
if [ -n "$LOLG_HD_WINE_EXTRA_MIX_DIR" ] && [ ! -d "$LOLG_HD_WINE_EXTRA_MIX_DIR" ]; then
	echo "Dossier extra MIX introuvable: $LOLG_HD_WINE_EXTRA_MIX_DIR" >&2
	exit 1
fi
if [ -n "$LOLG_HD_NGLIDE_DIR" ] && [ ! -d "$LOLG_HD_NGLIDE_DIR" ]; then
	echo "Dossier nGlide introuvable: $LOLG_HD_NGLIDE_DIR" >&2
	exit 1
fi

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

acquire_stage_lock() {
	mkdir -p "$RUNTIME_ROOT"
	exec 9>"$RUNTIME_ROOT/.stage.lock"
	if command -v flock >/dev/null 2>&1; then
		if ! flock -w "$LOLG_HD_STAGE_LOCK_TIMEOUT" 9; then
			echo "Verrou stage Wine occupe: $RUNTIME_ROOT/.stage.lock" >&2
			echo "Un ancien Wine ou lanceur tient probablement le stage. Lance: ./LOLG_HD.sh stop" >&2
			exit 1
		fi
	fi
}

link_or_copy_file() {
	src=$1
	dst=$2
	mode=$3
	if [ -L "$dst" ]; then
		rm -f "$dst"
	fi
	if [ -e "$dst" ] && [ ! -L "$dst" ]; then
		case "$mode" in
			copy)
				cp -f "$src" "$dst"
				;;
			link)
				echo "Conflit dans le stage, fichier non lien conserve: $dst" >&2
				;;
		esac
		return
	fi
	case "$mode" in
		copy)
			cp -f "$src" "$dst"
			;;
		link)
			ln -s "$src" "$dst"
			;;
	esac
}

auto_resize_wine_windows() {
	launcher_pid=${1:-}
	[ "$LOLG_HD_AUTO_RESIZE" -eq 1 ] || return 0
	[ "$DIRECT_LAUNCH" -eq 0 ] || return 0
	command -v xdotool >/dev/null 2>&1 || return 0
	[ -n "${DISPLAY:-}" ] || return 0

	width=${RESOLUTION%x*}
	height=${RESOLUTION#*x}
	desktop_name=${WINE_DESKTOP%%,*}
	desktop_title="$desktop_name - Wine [Dd]esktop"
	found_desktop=0
	found_game=0
	reported_desktop=0
	reported_game=0
	game_resized=0
	first_game_seen_at=
	search_started_at=$SECONDS

	while :; do
		launcher_running=0
		if [ -n "$launcher_pid" ] && kill -0 "$launcher_pid" 2>/dev/null; then
			launcher_running=1
		fi

		desktop_wins=$(xdotool search --name "$desktop_title" 2>/dev/null || true)
		for desktop_win in $desktop_wins; do
			if [ "$LOLG_HD_LOCK_WINDOW_POSITION" -eq 1 ]; then
				xdotool set_window --overrideredirect 1 "$desktop_win" >/dev/null 2>&1 || true
				xdotool windowmove "$desktop_win" 0 0 >/dev/null 2>&1 || true
			elif command -v xprop >/dev/null 2>&1 && xprop -id "$desktop_win" _NET_WM_STATE 2>/dev/null | grep -q '_NET_WM_STATE_FULLSCREEN'; then
				xdotool windowactivate "$desktop_win" >/dev/null 2>&1 || true
				xdotool key alt+F11 >/dev/null 2>&1 || true
			fi
			xdotool windowsize "$desktop_win" "$width" "$height" >/dev/null 2>&1 || true
			found_desktop=1
			if [ "$reported_desktop" -eq 0 ]; then
				echo "Bureau Wine ajuste en ${width}x${height}"
				reported_desktop=1
			fi
		done

		game_wins=$(xdotool search --name 'Lands Of Lore Guardians' 2>/dev/null || true)
		if [ -n "$game_wins" ]; then
			found_game=1
			if [ -z "$first_game_seen_at" ]; then
				first_game_seen_at=$SECONDS
			fi
			game_seen_for=$((SECONDS - first_game_seen_at))
			if [ "$LOLG_HD_RESIZE_GAME_WINDOW" -ne 1 ]; then
				if [ "$reported_game" -eq 0 ]; then
					echo "Fenetre jeu detectee; resize jeu desactive"
					reported_game=1
				fi
				break
			fi
			if [ "$LOLG_HD_RESIZE_GAME_WINDOW" -eq 1 ] && [ "$game_resized" -eq 0 ] && [ "$game_seen_for" -ge "$LOLG_HD_RESIZE_GAME_WINDOW_DELAY" ]; then
				for game_win in $game_wins; do
					if [ "$LOLG_HD_LOCK_WINDOW_POSITION" -eq 1 ]; then
						xdotool windowmove "$game_win" 0 0 >/dev/null 2>&1 || true
					fi
					xdotool windowsize "$game_win" "$width" "$height" >/dev/null 2>&1 || true
				done
				if [ "$reported_game" -eq 0 ]; then
					echo "Fenetre jeu ajustee en ${width}x${height} apres ${LOLG_HD_RESIZE_GAME_WINDOW_DELAY}s"
					reported_game=1
				fi
				game_resized=1
			elif [ "$LOLG_HD_RESIZE_GAME_WINDOW" -eq 1 ] && [ "$game_resized" -eq 1 ]; then
				for game_win in $game_wins; do
					if [ "$LOLG_HD_LOCK_WINDOW_POSITION" -eq 1 ]; then
						xdotool windowmove "$game_win" 0 0 >/dev/null 2>&1 || true
					fi
					xdotool windowsize "$game_win" "$width" "$height" >/dev/null 2>&1 || true
				done
			fi
			if [ "$LOLG_HD_RESIZE_GAME_WINDOW" -eq 1 ] && [ "$launcher_running" -eq 0 ] && [ "$game_seen_for" -ge $((LOLG_HD_RESIZE_GAME_WINDOW_DELAY + LOLG_HD_RESIZE_GAME_WINDOW_HOLD)) ]; then
				break
			fi
		fi

		if [ "$found_game" -eq 1 ] && [ "$LOLG_HD_RESIZE_GAME_WINDOW" -eq 1 ] && [ "$launcher_running" -eq 0 ] && [ "$game_seen_for" -ge $((LOLG_HD_RESIZE_GAME_WINDOW_DELAY + LOLG_HD_RESIZE_GAME_WINDOW_HOLD)) ]; then
			break
		fi
		if [ -n "$launcher_pid" ] && [ "$launcher_running" -eq 0 ] && [ "$found_game" -eq 0 ] && [ $((SECONDS - search_started_at)) -ge "$LOLG_HD_WINDOW_SEARCH_TIMEOUT" ]; then
			break
		fi
		sleep 1
	done

	if [ "$found_desktop" -eq 0 ] && [ "$found_game" -eq 0 ]; then
		echo "Avertissement: bureau Wine non trouve pour auto-resize" >&2
	fi
	if [ "$found_game" -eq 0 ]; then
		echo "Avertissement: fenetre jeu non trouvee pendant le lancement" >&2
	fi
}

wait_for_lolg_process() {
	launcher_pid=${1:-}
	if ! command -v pgrep >/dev/null 2>&1; then
		if [ -n "$launcher_pid" ]; then
			wait "$launcher_pid"
			return $?
		fi
		return 0
	fi

	lolg_process_pids() {
		pgrep -af '[L]OLG95' 2>/dev/null | while IFS= read -r line; do
			pid=${line%% *}
			cmdline=${line#* }
			case "$cmdline" in
				*start.exe*|*explorer.exe*|*wineserver*|*wineboot.exe*)
					continue
					;;
			esac
			printf '%s\n' "$pid"
		done
	}

	started_at=$SECONDS
	reported=0
	while :; do
		game_pids=$(lolg_process_pids)
		if [ -n "$game_pids" ]; then
			if [ "$reported" -eq 0 ]; then
				echo "Processus jeu detecte: LOLG95.EXE"
				reported=1
			fi
			break
		fi
		if [ $((SECONDS - started_at)) -ge "$LOLG_HD_WINE_PROCESS_TIMEOUT" ]; then
			echo "Avertissement: processus LOLG95.EXE non detecte apres ${LOLG_HD_WINE_PROCESS_TIMEOUT}s" >&2
			return 1
		fi
		sleep 1
	done

	while [ -n "$(lolg_process_pids)" ]; do
		sleep 1
	done
	echo "Processus jeu termine: LOLG95.EXE"
	return 0
}

prepare_stage() {
	mkdir -p "$STAGE_DIR"

	find "$SOURCE_GAME_DIR" -mindepth 1 -maxdepth 1 | while IFS= read -r src; do
		name=$(basename "$src")
		dst="$STAGE_DIR/$name"
		lower_name=$(printf '%s' "$name" | tr '[:upper:]' '[:lower:]')

		if [ -n "$LOLG_HD_WINE_EXE_SOURCE" ] && [ "$name" = "$LOLG_HD_WINE_EXE_NAME" ]; then
			continue
		fi

		case "$lower_name" in
			ddraw.dll)
				if [ "$LOLG_HD_USE_LOCAL_DDRAW" -eq 1 ]; then
					wrapper_src="$src"
					if [ "$LOLG_HD_USE_DGVOODOO" -eq 1 ] && [ -e "$LOLG_HD_DGVOODOO_SOURCE_DIR/$name" ]; then
						wrapper_src="$LOLG_HD_DGVOODOO_SOURCE_DIR/$name"
					fi
					link_or_copy_file "$wrapper_src" "$dst" link
				else
					rm -f "$dst"
				fi
				continue
				;;
			dgvoodoo.conf)
				if [ "$LOLG_HD_USE_DGVOODOO" -eq 1 ]; then
					dg_config_src="$src"
					if [ -e "$LOLG_HD_DGVOODOO_SOURCE_DIR/$name" ]; then
						dg_config_src="$LOLG_HD_DGVOODOO_SOURCE_DIR/$name"
					fi
					link_or_copy_file "$dg_config_src" "$dst" copy
				else
					rm -f "$dst"
				fi
				continue
				;;
			d3dimm.dll|d3d8.dll|dgvoodoocpl.exe)
				if [ "$LOLG_HD_USE_DGVOODOO" -eq 1 ]; then
					dg_src="$src"
					if [ -e "$LOLG_HD_DGVOODOO_SOURCE_DIR/$name" ]; then
						dg_src="$LOLG_HD_DGVOODOO_SOURCE_DIR/$name"
					fi
					link_or_copy_file "$dg_src" "$dst" link
				else
					rm -f "$dst"
				fi
				continue
				;;
			glide.dll|glide2x.dll|glide3x.dll)
				if [ "$LOLG_HD_USE_NGLIDE" -eq 1 ]; then
					link_or_copy_file "$src" "$dst" link
				else
					rm -f "$dst"
				fi
				continue
				;;
			opt3dfx.ini)
				if [ "$LOLG_HD_USE_3DFX_CONFIG" -eq 1 ]; then
					link_or_copy_file "$src" "$dst" copy
				else
					rm -f "$dst"
				fi
				continue
				;;
			savegame)
				mkdir -p "$dst"
				continue
				;;
		esac

		if [ -d "$src" ]; then
			link_or_copy_file "$src" "$dst" link
			continue
		fi

		case "$lower_name" in
			*.ini)
				link_or_copy_file "$src" "$dst" copy
				;;
			*.mix)
				if [ "$lower_name" = "movies.mix" ] && [ "$LOLG_HD_USE_ORIGINAL_MOVIES" -eq 1 ]; then
					link_or_copy_file "$src" "$dst" link
				elif csv_has_name "$LOLG_HD_WINE_HD_EXCLUDE" "$name"; then
					link_or_copy_file "$src" "$dst" link
				elif [ "$LOLG_HD_WINE_USE_HD_MIX" -eq 1 ] && [ -f "$HD_MIX_DIR/$name" ]; then
					link_or_copy_file "$HD_MIX_DIR/$name" "$dst" link
				else
					link_or_copy_file "$src" "$dst" link
				fi
				;;
			*)
				link_or_copy_file "$src" "$dst" link
				;;
		esac
	done

	if [ -n "$LOLG_HD_WINE_EXE_SOURCE" ]; then
		link_or_copy_file "$LOLG_HD_WINE_EXE_SOURCE" "$STAGE_DIR/$LOLG_HD_WINE_EXE_NAME" copy
	fi

	if [ -n "$LOLG_HD_WINE_EXTRA_MIX_DIR" ]; then
		for extra_mix in "$LOLG_HD_WINE_EXTRA_MIX_DIR"/*.MIX "$LOLG_HD_WINE_EXTRA_MIX_DIR"/*.mix; do
			[ -e "$extra_mix" ] || continue
			link_or_copy_file "$extra_mix" "$STAGE_DIR/$(basename "$extra_mix")" link
		done

		find "$LOLG_HD_WINE_EXTRA_MIX_DIR" -mindepth 1 -type f ! -iname '*.mix' | while IFS= read -r extra_file; do
			relative_path=${extra_file#"$LOLG_HD_WINE_EXTRA_MIX_DIR"/}
			target_path="$STAGE_DIR/$relative_path"
			mkdir -p "$(dirname "$target_path")"
			link_or_copy_file "$extra_file" "$target_path" link
		done
	fi

	if [ "$LOLG_HD_USE_NGLIDE" -eq 1 ] && [ -n "$LOLG_HD_NGLIDE_DIR" ]; then
		for glide_dll in "$LOLG_HD_NGLIDE_DIR"/glide*.dll "$LOLG_HD_NGLIDE_DIR"/Glide*.dll "$LOLG_HD_NGLIDE_DIR"/GLIDE*.DLL; do
			[ -e "$glide_dll" ] || continue
			link_or_copy_file "$glide_dll" "$STAGE_DIR/$(basename "$glide_dll")" link
		done
	fi

	if [ "$LOLG_HD_USE_DGVOODOO" -eq 1 ] && [ -f "$STAGE_DIR/dgVoodoo.conf" ]; then
		dg_width=${RESOLUTION%x*}
		dg_height=${RESOLUTION#*x}
		LOLG_HD_DG_WIDTH="$dg_width" LOLG_HD_DG_HEIGHT="$dg_height" LOLG_HD_DG_OUTPUT_API="$LOLG_HD_DGVOODOO_OUTPUT_API" LOLG_HD_DG_FULLSCREEN="$LOLG_HD_DGVOODOO_FULLSCREEN" LOLG_HD_DG_APP_CONTROLLED="$LOLG_HD_DGVOODOO_APP_CONTROLLED" LOLG_HD_DG_FORCE_RESOLUTION="$LOLG_HD_DGVOODOO_FORCE_RESOLUTION" LOLG_HD_DG_SCALING="$LOLG_HD_DGVOODOO_SCALING" LOLG_HD_DG_DESKTOP_RESOLUTION="$LOLG_HD_DGVOODOO_DESKTOP_RESOLUTION" LOLG_HD_DG_WINDOWED_ATTRIBUTES="$LOLG_HD_DGVOODOO_WINDOWED_ATTRIBUTES" LOLG_HD_DG_VRAM="$LOLG_HD_DGVOODOO_VRAM" LOLG_HD_DG_GLIDE_RAM="$LOLG_HD_DGVOODOO_GLIDE_RAM" LOLG_HD_DG_TMU_MEMORY="$LOLG_HD_DGVOODOO_TMU_MEMORY" LOLG_HD_DG_FAST_VIDEO_MEMORY="$LOLG_HD_DGVOODOO_FAST_VIDEO_MEMORY" LOLG_HD_DG_PRIMARY_SURFACE_BATCHED="$LOLG_HD_DGVOODOO_PRIMARY_SURFACE_BATCHED" LOLG_HD_DG_RT_TEXTURES_FORCE_SCALE_MSAA="$LOLG_HD_DGVOODOO_RT_TEXTURES_FORCE_SCALE_MSAA" LOLG_HD_DG_SMOOTHED_DEPTH_SAMPLING="$LOLG_HD_DGVOODOO_SMOOTHED_DEPTH_SAMPLING" LOLG_HD_DG_FORCE_VSYNC="$LOLG_HD_DGVOODOO_FORCE_VSYNC" perl -0pi -e '
			my $w = $ENV{LOLG_HD_DG_WIDTH};
			my $h = $ENV{LOLG_HD_DG_HEIGHT};
			my $api = $ENV{LOLG_HD_DG_OUTPUT_API} || "d3d11_fl11_0";
			my $fullscreen = $ENV{LOLG_HD_DG_FULLSCREEN} || "false";
			my $app_controlled = $ENV{LOLG_HD_DG_APP_CONTROLLED} || "false";
			my $scaling = $ENV{LOLG_HD_DG_SCALING} || "stretched";
			my $desktop_resolution = $ENV{LOLG_HD_DG_DESKTOP_RESOLUTION} // "${w}x${h}";
			my $windowed_attributes = $ENV{LOLG_HD_DG_WINDOWED_ATTRIBUTES} // "borderless";
			my $vram = $ENV{LOLG_HD_DG_VRAM} || "512";
			my $glide_ram = $ENV{LOLG_HD_DG_GLIDE_RAM} || "8";
			my $tmu_memory = $ENV{LOLG_HD_DG_TMU_MEMORY} || "4096";
			my $fast_video_memory = $ENV{LOLG_HD_DG_FAST_VIDEO_MEMORY} || "false";
			my $primary_surface_batched = $ENV{LOLG_HD_DG_PRIMARY_SURFACE_BATCHED} || "false";
			my $rt_textures_force_scale_msaa = $ENV{LOLG_HD_DG_RT_TEXTURES_FORCE_SCALE_MSAA} || "true";
			my $smoothed_depth_sampling = $ENV{LOLG_HD_DG_SMOOTHED_DEPTH_SAMPLING} || "true";
			my $force_vsync = $ENV{LOLG_HD_DG_FORCE_VSYNC} || "false";
			my $force_resolution = ($ENV{LOLG_HD_DG_FORCE_RESOLUTION} || "0") eq "1";
			my $render_resolution = $force_resolution ? "h:${w}, v:${h}" : "unforced";
			s/^OutputAPI\s*=.*$/"OutputAPI                            = ${api}"/me;
			s/^FullScreenMode\s*=.*$/"FullScreenMode                       = ${fullscreen}"/me;
			s/^ScalingMode\s*=.*$/"ScalingMode                          = ${scaling}"/me;
			s/^InheritColorProfileInFullScreenMode\s*=.*$/InheritColorProfileInFullScreenMode  = false/m;
			s/^DesktopResolution\s*=.*$/"DesktopResolution                    = ${desktop_resolution}"/me;
			s/^Resampling\s*=.*$/Resampling                           = bilinear/m;
			s/^WindowedAttributes\s*=.*$/"WindowedAttributes                   = ${windowed_attributes}"/me;
			s/^Resolution\s*=.*$/"Resolution                          = ${render_resolution}"/meg;
			s/^OnboardRAM\s*=.*$/"OnboardRAM                          = ${glide_ram}"/me;
			s/^MemorySizeOfTMU\s*=.*$/"MemorySizeOfTMU                     = ${tmu_memory}"/me;
			s/^VRAM\s*=.*$/"VRAM                                = ${vram}"/me;
			s/^Filtering\s*=.*$/Filtering                           = bilinear/m;
			s/^AppControlledScreenMode\s*=.*$/"AppControlledScreenMode             = ${app_controlled}"/me;
			s/^BilinearBlitStretch\s*=.*$/BilinearBlitStretch                 = true/m;
			s/^FastVideoMemoryAccess\s*=.*$/"FastVideoMemoryAccess               = ${fast_video_memory}"/me;
			s/^ForceVerticalSync\s*=.*$/"ForceVerticalSync                   = ${force_vsync}"/meg;
			s/^RTTexturesForceScaleAndMSAA\s*=.*$/"RTTexturesForceScaleAndMSAA         = ${rt_textures_force_scale_msaa}"/me;
			s/^SmoothedDepthSampling\s*=.*$/"SmoothedDepthSampling               = ${smoothed_depth_sampling}"/me;
			s/^PrimarySurfaceBatchedUpdate\s*=.*$/"PrimarySurfaceBatchedUpdate         = ${primary_surface_batched}"/me;
			s/^ExtraEnumeratedResolutions\s*=.*$/"ExtraEnumeratedResolutions          = ${w}x${h}"/me;
		' "$STAGE_DIR/dgVoodoo.conf"
	fi

	for config in "$STAGE_DIR"/OPTIONS.INI "$STAGE_DIR"/OPT3DFX.INI "$STAGE_DIR"/OPTFIX.INI; do
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

	if [ "$LOLG_HD_USE_3DFX_CONFIG" -eq 1 ]; then
		if [ ! -f "$STAGE_DIR/OPT3DFX.INI" ]; then
			echo "Config 3dfx introuvable dans le stage: $STAGE_DIR/OPT3DFX.INI" >&2
			exit 1
		fi
		cp -f "$STAGE_DIR/OPT3DFX.INI" "$STAGE_DIR/OPTIONS.INI"
		perl -0pi -e '
			s/Video_Variable_Frame_Rate=Yes/Video_Variable_Frame_Rate=No/g;
			s/Acceleration_Toggle=Off/Acceleration_Toggle=On/g;
		' "$STAGE_DIR/OPTIONS.INI"
	fi

	if [ "$LOLG_HD_LOW_MEMORY_CONFIG" -eq 1 ]; then
		for config in "$STAGE_DIR"/OPTIONS.INI "$STAGE_DIR"/OPT3DFX.INI "$STAGE_DIR"/OPTFIX.INI; do
			[ -f "$config" ] || continue
			perl -0pi -e '
				s/Video_Texture_Resolution=High/Video_Texture_Resolution=Low/g;
				s/Video_Texture_Cache=Large/Video_Texture_Cache=Small/g;
			' "$config"
		done
	fi

	if [ "$LOLG_HD_DISABLE_3D_ACCEL" -eq 1 ] && [ -f "$STAGE_DIR/OPTIONS.INI" ]; then
		perl -0pi -e '
			s/Acceleration_Toggle=On/Acceleration_Toggle=Off/g;
			s/Video_Variable_Frame_Rate=No/Video_Variable_Frame_Rate=Yes/g;
		' "$STAGE_DIR/OPTIONS.INI"
	fi
}

verify_critical_mix_stage() {
	[ "$LOLG_HD_ALLOW_CRITICAL_HD_MIX" -eq 0 ] || return 0

	local bad_mix=0
	local mix target
	for mix in LOCALLNG.MIX MOVIES.MIX; do
		[ -e "$STAGE_DIR/$mix" ] || continue
		target=$(readlink -f "$STAGE_DIR/$mix" 2>/dev/null || true)
		case "$target" in
			"$SOURCE_GAME_DIR"/*)
				;;
			*)
				echo "MIX critique non original: $STAGE_DIR/$mix -> ${target:-introuvable}" >&2
				bad_mix=1
				;;
		esac
	done

	if [ "$bad_mix" -ne 0 ]; then
		echo "Lancement refuse pour eviter le page fault VQA connu sur LOCALLNG/MOVIES." >&2
		exit 1
	fi
}

wine_reg_add() {
	key=$1
	value=$2
	data=$3
	"$WINE_BIN" reg add "$key" /v "$value" /d "$data" /f >/dev/null
}

wine_reg_delete_value() {
	key=$1
	value=$2
	"$WINE_BIN" reg delete "$key" /v "$value" /f >/dev/null 2>&1
}

clear_dxvk_overrides() {
	for dll in d3d8 d3d9 dxgi d3d10 d3d10_1 d3d10core d3d11; do
		wine_reg_delete_value 'HKCU\Software\Wine\DllOverrides' "$dll" || true
	done
}

configure_nglide_overrides() {
	wine_reg_add 'HKCU\Software\Wine\DllOverrides' glide native,builtin || true
	wine_reg_add 'HKCU\Software\Wine\DllOverrides' glide2x native,builtin || true
	wine_reg_add 'HKCU\Software\Wine\DllOverrides' glide3x native,builtin || true
}

configure_nglide_settings() {
	[ "$LOLG_HD_USE_NGLIDE" -eq 1 ] || return 0

	nglide_key='HKCU\Software\Zeus Software\nGlide2'
	[ -z "$LOLG_HD_NGLIDE_BACKEND" ] || wine_reg_add "$nglide_key" Backend "$LOLG_HD_NGLIDE_BACKEND" || true
	[ -z "$LOLG_HD_NGLIDE_RESOLUTION" ] || wine_reg_add "$nglide_key" Resolution "$LOLG_HD_NGLIDE_RESOLUTION" || true
	[ -z "$LOLG_HD_NGLIDE_ASPECT" ] || wine_reg_add "$nglide_key" Aspect "$LOLG_HD_NGLIDE_ASPECT" || true
	[ -z "$LOLG_HD_NGLIDE_REFRESH" ] || wine_reg_add "$nglide_key" Refresh "$LOLG_HD_NGLIDE_REFRESH" || true
	[ -z "$LOLG_HD_NGLIDE_VSYNC" ] || wine_reg_add "$nglide_key" Vsync "$LOLG_HD_NGLIDE_VSYNC" || true
	[ -z "$LOLG_HD_NGLIDE_GAMMA" ] || wine_reg_add "$nglide_key" Gamma "$LOLG_HD_NGLIDE_GAMMA" || true
	[ -z "$LOLG_HD_NGLIDE_SPLASH" ] || wine_reg_add "$nglide_key" Splash "$LOLG_HD_NGLIDE_SPLASH" || true
}

export_nglide_environment() {
	[ "$LOLG_HD_USE_NGLIDE" -eq 1 ] || return 0

	[ -z "$LOLG_HD_NGLIDE_BACKEND" ] || export NGLIDE_BACKEND="$LOLG_HD_NGLIDE_BACKEND"
	[ -z "$LOLG_HD_NGLIDE_RESOLUTION" ] || export NGLIDE_RESOLUTION="$LOLG_HD_NGLIDE_RESOLUTION"
	[ -z "$LOLG_HD_NGLIDE_ASPECT" ] || export NGLIDE_ASPECT="$LOLG_HD_NGLIDE_ASPECT"
	[ -z "$LOLG_HD_NGLIDE_REFRESH" ] || export NGLIDE_REFRESH="$LOLG_HD_NGLIDE_REFRESH"
	[ -z "$LOLG_HD_NGLIDE_VSYNC" ] || export NGLIDE_VSYNC="$LOLG_HD_NGLIDE_VSYNC"
	[ -z "$LOLG_HD_NGLIDE_GAMMA" ] || export NGLIDE_GAMMA="$LOLG_HD_NGLIDE_GAMMA"
	[ -z "$LOLG_HD_NGLIDE_SPLASH" ] || export NGLIDE_SPLASH="$LOLG_HD_NGLIDE_SPLASH"
}

verify_nglide_available() {
	[ "$LOLG_HD_USE_NGLIDE" -eq 1 ] || return 0

	for dir in "$STAGE_DIR" "$WINEPREFIX/drive_c/windows/system32" "$WINEPREFIX/drive_c/windows/syswow64"; do
		[ -d "$dir" ] || continue
		for dll in glide.dll glide2x.dll glide3x.dll GLIDE.DLL GLIDE2X.DLL GLIDE3X.DLL; do
			if [ -e "$dir/$dll" ]; then
				echo "nGlide/Glide DLL: $dir/$dll"
				return 0
			fi
		done
	done

	echo "nGlide demande mais aucune DLL Glide trouvee." >&2
	echo "Attendu: glide2x.dll/glide3x.dll dans C/LOLG, dans --nglide-dir, ou installees dans ce prefixe Wine:" >&2
	echo "  WINEPREFIX=$WINEPREFIX" >&2
	echo "Exemple avec DLL locales:" >&2
	echo "  ./LOLG_HD.sh wine-nglide --nglide-dir /chemin/vers/nglide" >&2
	exit 1
}

map_wine_drive_d() {
	mkdir -p "$WINEPREFIX/dosdevices"
	rm -f "$WINEPREFIX/dosdevices/d:" "$WINEPREFIX/dosdevices/d::"
	ln -sT "$RUNTIME_ROOT" "$WINEPREFIX/dosdevices/d:"
}

seed_wine_x11_registry() {
	user_reg="$WINEPREFIX/user.reg"
	mkdir -p "$WINEPREFIX"

	if [ ! -f "$user_reg" ]; then
		printf 'WINE REGISTRY Version 2\n;; All keys relative to REGISTRY\\\\User\\\\S-1-5-21-0-0-0-1000\n\n' > "$user_reg"
	fi

	tmp_reg="${user_reg}.tmp.$$"
	awk '
		/^\[Software\\\\Wine\\\\X11 Driver\]/ { skip = 1; next }
		/^\[/ { skip = 0 }
		!skip { print }
	' "$user_reg" > "$tmp_reg"
	mv "$tmp_reg" "$user_reg"
	printf '\n[Software\\\\Wine\\\\X11 Driver]\n"UseXRandR"="%s"\n"UseXVidMode"="%s"\n' \
		"$LOLG_HD_WINE_USE_XRANDR" \
		"$LOLG_HD_WINE_USE_XVIDMODE" >> "$user_reg"
}

setup_dxvk_prefix() {
	if ! command -v "$DXVK_SETUP_BIN" >/dev/null 2>&1; then
		echo "Avertissement: dxvk-setup introuvable, DXVK non installe dans ce prefixe." >&2
		return 1
	fi

	if ! "$DXVK_SETUP_BIN" install --stable --yes >/dev/null 2>&1; then
		"$DXVK_SETUP_BIN" install --yes >/dev/null
	fi

	install_dxvk_d3d8 "$WINEPREFIX/drive_c/windows/system32" /usr/lib/dxvk/wine64/d3d8.dll.so
	install_dxvk_d3d8 "$WINEPREFIX/drive_c/windows/syswow64" /usr/lib/dxvk/wine32/d3d8.dll.so
	wine_reg_add 'HKCU\Software\Wine\DllOverrides' d3d8 native || true
}

install_dxvk_d3d8() {
	dst_dir=$1
	src=$2
	[ -d "$dst_dir" ] || return 0
	[ -f "$src" ] || return 0

	dst="$dst_dir/d3d8.dll"
	old="$dst.old"
	current_target=
	if [ -L "$dst" ]; then
		current_target=$(readlink "$dst" 2>/dev/null || true)
	fi
	if [ "$current_target" = "$src" ]; then
		return 0
	fi
	if [ ! -e "$old" ] && [ -e "$dst" ] && [ ! -L "$dst" ]; then
		mv "$dst" "$old"
	fi
	rm -f "$dst"
	ln -s "$src" "$dst"
}

configure_wine() {
	mkdir -p "$WINEPREFIX"
	export WINEPREFIX WINEDEBUG

	seed_wine_x11_registry
	"$WINEBOOT_BIN" -u >/dev/null
	map_wine_drive_d

	if [ "$LOLG_HD_SETUP_DXVK" -eq 1 ]; then
		setup_dxvk_prefix || true
	elif [ "$LOLG_HD_USE_DXVK" -eq 0 ]; then
		clear_dxvk_overrides
	fi

	desktop_name=${WINE_DESKTOP%%,*}
	desktop_size=$RESOLUTION
	case "$WINE_DESKTOP" in
		*,*) desktop_size=${WINE_DESKTOP#*,} ;;
	esac
	wine_reg_add 'HKCU\Software\Wine\Explorer\Desktops' "$desktop_name" "$desktop_size" || true
	wine_reg_add 'HKCU\Software\Wine\X11 Driver' UseXRandR "$LOLG_HD_WINE_USE_XRANDR" || true
	wine_reg_add 'HKCU\Software\Wine\X11 Driver' UseXVidMode "$LOLG_HD_WINE_USE_XVIDMODE" || true
	if [ -n "$LOLG_HD_WINE_VERSION" ]; then
		wine_reg_add 'HKCU\Software\Wine' Version "$LOLG_HD_WINE_VERSION" || true
		wine_reg_add "HKCU\\Software\\Wine\\AppDefaults\\$LOLG_HD_WINE_EXE_NAME" Version "$LOLG_HD_WINE_VERSION" || true
	fi

	if [ -n "$WINE_RENDERER" ]; then
		wine_reg_add 'HKCU\Software\Wine\Direct3D' renderer "$WINE_RENDERER" || true
		if [ "$WINE_DIRECTDRAW_RENDERER" = none ]; then
			wine_reg_delete_value 'HKCU\Software\Wine\Direct3D' DirectDrawRenderer || true
		else
			wine_reg_add 'HKCU\Software\Wine\Direct3D' DirectDrawRenderer "$WINE_DIRECTDRAW_RENDERER" || true
		fi
		wine_reg_add 'HKCU\Software\Wine\Direct3D' UseGLSL enabled || true
		wine_reg_add 'HKCU\Software\Wine\Direct3D' OffscreenRenderingMode fbo || true
		if [ -n "$LOLG_HD_WINE_VIDEO_MEMORY_SIZE" ]; then
			wine_reg_add 'HKCU\Software\Wine\Direct3D' VideoMemorySize "$LOLG_HD_WINE_VIDEO_MEMORY_SIZE" || true
		fi
	fi
	if [ "$LOLG_HD_USE_NGLIDE" -eq 1 ]; then
		configure_nglide_overrides
		configure_nglide_settings
	fi
}

acquire_stage_lock
prepare_stage
verify_critical_mix_stage

GAME_ARGS=()
if [ "$LOLG_HD_GAME_LOWMEM" -eq 1 ]; then
	GAME_ARGS+=('-LOWMEM')
fi

if [ "$DIRECT_LAUNCH" -eq 1 ]; then
	COMMAND=(
		"$WINE_BIN"
		"D:\\WESTWOOD\\LOLG\\$LOLG_HD_WINE_EXE_NAME"
		-CD
		'D:\WESTWOOD\LOLG'
		"${GAME_ARGS[@]}"
	)
elif [ "$WAIT_FOR_EXIT" -eq 1 ]; then
	COMMAND=(
		"$WINE_BIN"
		explorer
		"/desktop=$WINE_DESKTOP"
		"D:\\WESTWOOD\\LOLG\\$LOLG_HD_WINE_EXE_NAME"
		-CD
		'D:\WESTWOOD\LOLG'
		"${GAME_ARGS[@]}"
	)
else
	COMMAND=(
		"$WINE_BIN"
		explorer
		"/desktop=$WINE_DESKTOP"
		"D:\\WESTWOOD\\LOLG\\$LOLG_HD_WINE_EXE_NAME"
		-CD
		'D:\WESTWOOD\LOLG'
		"${GAME_ARGS[@]}"
	)
fi

echo "Stage Full HD Wine: $STAGE_DIR"
echo "Resolution Wine: $RESOLUTION"
if [ "$DIRECT_LAUNCH" -eq 1 ]; then
	echo "Mode fenetre: directe sans bureau Wine virtuel"
else
	echo "Mode fenetre: bureau Wine virtuel"
fi
if [ "$ALLOW_UNSUPPORTED_RESOLUTION" -eq 1 ]; then
	echo "Resolution supportee: non verifiee"
else
echo "Resolution supportee: oui"
fi
echo "Renderer Wine: $WINE_RENDERER"
if [ "$WINE_DIRECTDRAW_RENDERER" = none ]; then
	echo "DirectDrawRenderer Wine: non force"
else
	echo "DirectDrawRenderer Wine: $WINE_DIRECTDRAW_RENDERER"
fi
if [ -n "$LOLG_HD_WINE_VIDEO_MEMORY_SIZE" ]; then
	echo "Memoire video Wine: ${LOLG_HD_WINE_VIDEO_MEMORY_SIZE}MB"
fi
echo "Wine X11: UseXRandR=$LOLG_HD_WINE_USE_XRANDR UseXVidMode=$LOLG_HD_WINE_USE_XVIDMODE"
if [ -n "$LOLG_HD_WINE_VERSION" ]; then
	echo "Version Windows Wine: $LOLG_HD_WINE_VERSION"
else
	echo "Version Windows Wine: prefixe existant"
fi
if [ "$LOLG_HD_USE_DXVK" -eq 1 ]; then
	echo "DXVK Wine: overrides D3D8/D3D9/DXGI/D3D10/D3D11 actifs"
else
	echo "DXVK Wine: desactive"
fi
if [ "$LOLG_HD_SETUP_DXVK" -eq 1 ]; then
	echo "Installation DXVK prefixe: demandee"
else
	echo "Installation DXVK prefixe: non demandee"
fi
if [ "$LOLG_HD_LOCK_WINDOW_POSITION" -eq 1 ]; then
	echo "Position fenetre: verrouillee"
else
	echo "Position fenetre: deplacable"
fi
if [ "$LOLG_HD_AUTO_RESIZE" -eq 1 ]; then
	echo "Auto-resize fenetre: actif"
else
	echo "Auto-resize fenetre: desactive"
fi
if [ "$LOLG_HD_GAME_LOWMEM" -eq 1 ]; then
	echo "Option jeu: -LOWMEM"
else
	echo "Option jeu: aucune option memoire"
fi
if [ "$LOLG_HD_LOW_MEMORY_CONFIG" -eq 1 ]; then
	echo "Config jeu: low memory (textures Low, cache Small)"
else
	echo "Config jeu: normale"
fi
if [ "$LOLG_HD_DISABLE_3D_ACCEL" -eq 1 ]; then
	echo "Acceleration jeu: desactivee"
else
	echo "Acceleration jeu: activee"
fi
echo "DLL overrides Wine: $LOLG_HD_WINE_DLL_OVERRIDES"
if [ "$LOLG_HD_USE_DGVOODOO" -eq 1 ]; then
	echo "dgVoodoo: actif avec DDraw.dll/D3DImm.dll/D3D8.dll/dgVoodoo.conf locaux"
	echo "Source dgVoodoo: $LOLG_HD_DGVOODOO_SOURCE_DIR"
	if [ "$LOLG_HD_DGVOODOO_FORCE_RESOLUTION" -eq 1 ]; then
		echo "Resolution interne dgVoodoo: forcee en $RESOLUTION"
	else
		echo "Resolution interne dgVoodoo: non forcee"
	fi
	echo "Memoire dgVoodoo: DirectX VRAM=$LOLG_HD_DGVOODOO_VRAM Glide RAM=${LOLG_HD_DGVOODOO_GLIDE_RAM}MB TMU=${LOLG_HD_DGVOODOO_TMU_MEMORY}kB"
	echo "Optimisation dgVoodoo: FastVideoMemoryAccess=$LOLG_HD_DGVOODOO_FAST_VIDEO_MEMORY PrimarySurfaceBatchedUpdate=$LOLG_HD_DGVOODOO_PRIMARY_SURFACE_BATCHED"
elif [ "$LOLG_HD_USE_LOCAL_DDRAW" -eq 1 ]; then
	echo "DDraw local: actif sans dgVoodoo.conf/D3DImm.dll/D3D8.dll"
else
	echo "dgVoodoo: desactive par stage sans DDraw.dll/D3DImm.dll/D3D8.dll"
fi
if [ "$LOLG_HD_USE_NGLIDE" -eq 1 ]; then
	if [ -n "$LOLG_HD_NGLIDE_DIR" ]; then
		echo "nGlide: actif depuis $LOLG_HD_NGLIDE_DIR"
	else
		echo "nGlide: actif depuis le prefixe Wine ou le stage"
	fi
		if [ "$LOLG_HD_USE_3DFX_CONFIG" -eq 1 ]; then
			echo "Config jeu: OPT3DFX.INI copie vers OPTIONS.INI"
		fi
		echo "Config nGlide: Backend=${LOLG_HD_NGLIDE_BACKEND:-prefixe} Resolution=${LOLG_HD_NGLIDE_RESOLUTION:-prefixe} Aspect=${LOLG_HD_NGLIDE_ASPECT:-prefixe}"
		echo "Config nGlide: Refresh=${LOLG_HD_NGLIDE_REFRESH:-prefixe} Vsync=${LOLG_HD_NGLIDE_VSYNC:-prefixe} Gamma=${LOLG_HD_NGLIDE_GAMMA:-prefixe} Splash=${LOLG_HD_NGLIDE_SPLASH:-prefixe}"
	else
		echo "nGlide: desactive"
	fi
if [ "$LOLG_HD_WINE_USE_HD_MIX" -eq 1 ]; then
	echo "Pack MIX HD global Wine: actif quand disponible"
else
	echo "Pack MIX HD global Wine: desactive"
fi
if [ -n "$LOLG_HD_WINE_HD_EXCLUDE" ]; then
	echo "MIX HD exclus Wine: $LOLG_HD_WINE_HD_EXCLUDE"
fi
if [ -n "$LOLG_HD_WINE_EXE_SOURCE" ]; then
	echo "Executable Wine patche: $LOLG_HD_WINE_EXE_SOURCE -> $LOLG_HD_WINE_EXE_NAME"
fi
if [ -n "$LOLG_HD_WINE_EXTRA_MIX_DIR" ]; then
	echo "Dossier sidecar MIX Wine: $LOLG_HD_WINE_EXTRA_MIX_DIR"
fi
if [ -n "$LOLG_HD_WINE_EXTRA_MIX_NOTE" ]; then
	echo "Note sidecar MIX: $LOLG_HD_WINE_EXTRA_MIX_NOTE"
fi
if [ -n "$LOLG_HD_WINE_MOVIES_LABEL" ]; then
	echo "MOVIES.MIX: $LOLG_HD_WINE_MOVIES_LABEL"
elif [ "$LOLG_HD_USE_ORIGINAL_MOVIES" -eq 1 ]; then
	echo "MOVIES.MIX: original (evite crash TITLE_E.VQA)"
else
	echo "MOVIES.MIX: HD experimental"
fi

if [ "$DRY_RUN" -eq 1 ]; then
	printf 'Commande:'
	printf ' %q' "${COMMAND[@]}"
	printf '\n'
	exit 0
fi

if [ "$SKIP_WINE_SETUP" -eq 0 ]; then
	configure_wine
else
	map_wine_drive_d
fi

export WINEPREFIX WINEDEBUG
export WINEDLLOVERRIDES="$LOLG_HD_WINE_DLL_OVERRIDES${WINEDLLOVERRIDES:+;$WINEDLLOVERRIDES}"
export_nglide_environment
export __GL_THREADED_OPTIMIZATIONS="${__GL_THREADED_OPTIMIZATIONS:-1}"
export vblank_mode="${vblank_mode:-0}"

if [ "$PREPARE_ONLY" -eq 1 ]; then
	echo "Pret. Pour lancer:"
	printf '  '
	printf ' %q' "${COMMAND[@]}"
	printf '\n'
	exit 0
fi

cd "$STAGE_DIR"

if [ "$LOLG_HD_AUTO_RESIZE" -eq 1 ] && [ "$DIRECT_LAUNCH" -eq 0 ] && command -v xdotool >/dev/null 2>&1 && [ -n "${DISPLAY:-}" ]; then
	"${COMMAND[@]}" &
	launcher_pid=$!
	if [ "$WAIT_FOR_EXIT" -eq 0 ]; then
		auto_resize_wine_windows "$launcher_pid"
		exit 0
	fi
	auto_resize_wine_windows "$launcher_pid" &
	resizer_pid=$!
	launcher_status=0
	wait_for_lolg_process "$launcher_pid" || launcher_status=$?
	wait "$launcher_pid" 2>/dev/null || true
	wait "$resizer_pid" 2>/dev/null || true
	exit "$launcher_status"
fi

if [ "$WAIT_FOR_EXIT" -eq 1 ] && [ "$DIRECT_LAUNCH" -eq 0 ]; then
	"${COMMAND[@]}" &
	launcher_pid=$!
	launcher_status=0
	wait_for_lolg_process "$launcher_pid" || launcher_status=$?
	wait "$launcher_pid" 2>/dev/null || true
	exit "$launcher_status"
fi

exec "${COMMAND[@]}"
