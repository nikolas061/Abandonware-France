@echo off
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0"

set "SRC=%CD%\C\LOLG"
set "HD=%CD%\mod_mix_vqa_fullhd"
set "DGVOODOO=%CD%\output\dgvoodoo_backup_before_2.84.1_20260704_134152"
set "DST=%CD%\output\lolg95_dgvoodoo_win10_safevqa_windows_runtime\WESTWOOD\LOLG"

if not exist "%SRC%\LOLG95.EXE" (
  echo Jeu introuvable: "%SRC%\LOLG95.EXE"
  echo Le dossier C\LOLG doit rester a cote de ce fichier.
  pause
  exit /b 1
)

if not exist "%HD%\ALTAR.MIX" (
  echo Pack HD introuvable: "%HD%"
  echo Le dossier mod_mix_vqa_fullhd doit rester a cote de ce fichier.
  pause
  exit /b 1
)

if not exist "%DGVOODOO%\DDraw.dll" (
  echo dgVoodoo 2.78 stable introuvable: "%DGVOODOO%"
  echo Le dossier output\dgvoodoo_backup_before_2.84.1_20260704_134152 doit rester dans le pack.
  pause
  exit /b 1
)

echo Preparation du runtime Windows safevqa...
if not exist "%DST%" mkdir "%DST%"

robocopy "%SRC%" "%DST%" /E /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 (
  echo Robocopy indisponible ou en echec, essai avec xcopy...
  xcopy "%SRC%\*" "%DST%\" /E /I /Y /Q >nul
)

if not exist "%DST%\LOLG95.EXE" (
  echo Echec copie depuis "%SRC%" vers "%DST%"
  echo Lance ce fichier directement sous Windows, ou sous Linux utilise:
  echo   ./LOLG_HD.sh wine-dgvoodoo-win10-safevqa
  pause
  exit /b 1
)

echo Application de dgVoodoo 2.78 stable...
del /Q "%DST%\DDraw.dll" "%DST%\D3DImm.dll" "%DST%\D3D8.dll" "%DST%\dgVoodoo.conf" "%DST%\dgVoodooCpl.exe" 2>nul
copy /Y "%DGVOODOO%\DDraw.dll" "%DST%\DDraw.dll" >nul
copy /Y "%DGVOODOO%\D3DImm.dll" "%DST%\D3DImm.dll" >nul
copy /Y "%DGVOODOO%\D3D8.dll" "%DST%\D3D8.dll" >nul
copy /Y "%DGVOODOO%\dgVoodoo.conf" "%DST%\dgVoodoo.conf" >nul
copy /Y "%DGVOODOO%\dgVoodooCpl.exe" "%DST%\dgVoodooCpl.exe" >nul
del /Q "%DST%\Glide.dll" "%DST%\Glide2x.dll" "%DST%\Glide3x.dll" "%DST%\OPT3DFX.INI" 2>nul

set "EXCLUDE=LOCALLNG.MIX MOVIES.MIX DANIEL.MIX DRAGON.MIX DSLAVE.MIX LIZ.MIX MCEL.MIX MENT.MIX MGAR.MIX MLIB.MIX MOFF.MIX SHAMAN.MIX SLAVES.MIX WPN.MIX MAGIC.MIX L1_DCI.MIX L3_DHI.MIX L4_HJI.MIX L5_HCI.MIX L7_DHI.MIX L8_SJI.MIX L9_DRI.MIX L10_DCI.MIX L12_CMI.MIX L13_RCI.MIX L14_HTI.MIX L16_CAI.MIX L19_BCI.MIX L20_BBI.MIX"

echo Application des MIX HD sauf VQA critiques, monstres, animations et effets...
for %%F in ("%HD%\*.MIX") do (
  set "NAME=%%~nxF"
  set "SKIP=0"
  for %%X in (%EXCLUDE%) do (
    if /I "!NAME!"=="%%X" set "SKIP=1"
  )
  if "!SKIP!"=="0" copy /Y "%%~fF" "%DST%\!NAME!" >nul
)

where powershell >nul 2>nul
if not errorlevel 1 (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$p='%DST%\dgVoodoo.conf'; if (Test-Path $p) { $s=Get-Content $p -Raw; $s=$s -replace '(?m)^DesktopResolution\s*=.*','DesktopResolution                    = 1920x1080'; $s=$s -replace '(?m)^Resolution\s*=.*','Resolution                          = h:1920, v:1080'; $s=$s -replace '(?m)^VRAM\s*=.*','VRAM                                = 2GB'; $s=$s -replace '(?m)^OnboardRAM\s*=.*','OnboardRAM                          = 2048'; $s=$s -replace '(?m)^MemorySizeOfTMU\s*=.*','MemorySizeOfTMU                     = 262144'; $s=$s -replace '(?m)^FastVideoMemoryAccess\s*=.*','FastVideoMemoryAccess               = true'; $s=$s -replace '(?m)^PrimarySurfaceBatchedUpdate\s*=.*','PrimarySurfaceBatchedUpdate         = true'; Set-Content -Path $p -Value $s -Encoding ASCII }"
) else (
  echo PowerShell introuvable: dgVoodoo.conf garde ses valeurs actuelles.
)

echo.
echo Runtime pret:
echo   %DST%
echo.
if /I "%~1"=="--prepare-only" (
  echo Prepare-only demande: lancement du jeu ignore.
  exit /b 0
)

echo Lancement de Lands of Lore II...
pushd "%DST%"
start "" "%DST%\LOLG95.EXE" -CD "%DST%"
popd
