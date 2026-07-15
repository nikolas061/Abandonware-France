# VQA Contract Runtime Gate

Date: 2026-07-08

## Result

`wine-vqa-contract` now points at the rebuilt LOCALLNG+MOVIES contract pack:

```text
sidecar=output/vqa_contract_pair_1280x1024_windowed_runtime
LOCALLNG.MIX=output/vqa_contract_preserving_writer_locallng_1280x1024_vqaext_padded_cbpz_from_adaptive_decode/mix/LOCALLNG.MIX
MOVIES.MIX=output/vqa_contract_movies_1280_0000_0027_windowed_patch/MOVIES.MIX
```

The MOVIES runtime batch audit now passes for all tested entries:

```text
summary=output/vqa_runtime_compat_movies_0000_0027_windowed_patch_final/summary.csv
status=pass
entries_requested=28
entries_pass=28
entries_gap=0
entries_failed=0
```

This replaces the previous partial MOVIES 1280 pack, where only entries `0`,
`2`, and `3` passed the strict runtime audit.

## Rebuild Method

The final MOVIES pack was built incrementally with
`tools/lolg_mix_replace_entries.py`, replacing only entries whose fresh VQA
payload passed the runtime contract audit.

Final candidate:

```text
output/vqa_contract_movies_1280_0000_0027_windowed_patch/MOVIES.MIX
sha256=b227206c351beb99ed4b1b2e2528565e7242a10b9b9ba96ac1d2bd2f3e9c8c27
full_manifest=output/vqa_contract_movies_1280_0000_0027_windowed_patch/full_manifest.csv
```

Intermediate verified checkpoints:

```text
output/vqa_runtime_compat_movies_0000_0010_windowed_patch/summary.csv -> pass
output/vqa_runtime_compat_movies_0000_0017_windowed_patch/summary.csv -> pass
output/vqa_runtime_compat_movies_0000_0024_windowed_patch/summary.csv -> pass
output/vqa_runtime_compat_movies_0000_0027_windowed_patch_final/summary.csv -> pass
```

The difficult long entries were also accepted by the final audit:

```text
entry=19 frames=450 runtime_compat=pass
entry=20 frames=676 runtime_compat=pass
```

Follow-up LCW dialect spot checks show that MOVIES is not fully solved at the
encoder-dialect level even when the file-level runtime audit passes. Entry 2
and entry 3 pass CBFZ/CBPZ/VPTZ against the original profile, but entries 0, 19,
and 20 still show the same CBPZ pattern later fixed for LOCALLNG:

```text
MOVIES[0] CBPZ: long_copy_fe_missing;fill_ff_missing;max_command_count_shrunk
MOVIES[19] CBPZ: long_copy_fe_missing;fill_ff_missing;max_command_count_shrunk
MOVIES[20] CBPZ: long_copy_fe_missing;fill_ff_missing;max_command_count_shrunk
```

That makes CBPZ padding/VQA-common LCW the next MOVIES-side probe if the
1280 LOCALLNG candidate still fails or if MOVIES alone keeps crashing.
The slow full-frame batch rebuild timed out on `MOVIES[0]`, so the current
probe instead starts from the already passing MOVIES 0-27 pack and recompresses
only selected `CBPZ` subchunks.

```sh
python3 tools/lolg_vqa_recompress_lcw_chunks.py \
  --source output/vqa_contract_movies_1280_0000_0027_windowed_patch/MOVIES.MIX \
  --entries 0,19,20 \
  --chunk-ids CBPZ \
  --synthetic-no-room-cbpz-bytes 65536 \
  -o output/vqa_contract_movies_1280_0000_0027_cbpz_vqaext_noroom_patch
```

Launcher helper for that probe:

```sh
./LOLG_HD.sh vqa-contract-build-movies-cbpz-padded
LOLG_HD_ALLOW_CRASHING_VQA_CONTRACT=1 ./LOLG_HD.sh wine-vqa-contract-movies-noroom
```

The recompressed MOVIES probe now passes the targeted local gates:

```text
MOVIES[0] CBPZ no_room LCW dialect: 3/3 pass, gaps=0
MOVIES[19] CBPZ no_room LCW dialect: 3/3 pass, gaps=0
MOVIES[20] CBPZ no_room LCW dialect: 3/3 pass, gaps=0
MOVIES[0] runtime compat: pass
MOVIES[19] runtime compat: pass
MOVIES[20] runtime compat: pass
```

Forced Wine probe:

```text
probe=output/vqa_contract_launch_probe_20260708_004859/movies_noroom_early_100203
launcher=LOLG_HD_ALLOW_CRASHING_VQA_CONTRACT=1 ./LOLG_HD.sh wine-vqa-contract-movies-noroom
result=Wine desktop 1920x1080 appears at t=8, no Application Error window found, no LOLG95 game window found, desktop closes before t=9
capture=window.png/root.png captured the Wine desktop/window-manager surface, not an in-game frame
```

So `no_room` closes the local MOVIES LCW dialect gap, but it does not yet make
the critical paired LOCALLNG+MOVIES path playable. The current runtime symptom
for this specific paired probe is a short-lived Wine desktop with no visible
game window, rather than the earlier visible `Application Error` dialog.

MOVIES-only forced Wine probe:

```text
probe=output/vqa_contract_launch_probe_20260708_004859/movies_noroom_only_100724
launcher=LOLG_HD_ALLOW_CRASHING_VQA_CONTRACT=1 ./LOLG_HD.sh wine-vqa-contract-movies-noroom-only
result=LOLG95.EXE appears at t=9 and remains alive until manual stop; no Application Error window found
wine_log=free(): invalid pointer; wine assertion starts debugger
capture=window.png is a black 1920x1080 Wine desktop/game surface
```

After fixing `RUN_HD_WINE.sh --no-dxvk` so it also resets DLL overrides to
`ddraw,d3dimm,d3d8=b`, the true non-DXVK retest behaves the same:

```text
probe=output/vqa_contract_launch_probe_20260708_004859/movies_noroom_only_nodxvk_fixed_101451
launcher=LOLG_HD_ALLOW_CRASHING_VQA_CONTRACT=1 ./LOLG_HD.sh wine-vqa-contract-movies-noroom-only --no-dxvk
result=LOLG95.EXE appears and remains alive until stop; no Application Error window found
wine_log=free(): invalid pointer; wine assertion starts debugger
capture=window.png remains black
```

This isolates the next split: `LOCALLNG` HD still prevents the paired no_room
probe from reaching `LOLG95.EXE`, while `MOVIES` no_room alone reaches the game
process but still lands on a black/asserting Wine runtime instead of a playable
image. The MOVIES-only assertion is not a DXVK override artifact.

To check whether one specific MOVIES entry was responsible, seven single-entry
archives were built from original `C/LOLG/MOVIES.MIX` plus one HD/no_room entry
at a time:

```text
payloads=output/movies_noroom_payload_extract_20260708/
mixes=output/movies_single_entry_noroom_0000_20260708/
      output/movies_single_entry_noroom_0001_20260708/
      output/movies_single_entry_noroom_0002_20260708/
      output/movies_single_entry_noroom_0003_20260708/
      output/movies_single_entry_noroom_0004_20260708/
      output/movies_single_entry_noroom_0019_20260708/
      output/movies_single_entry_noroom_0020_20260708/
```

Probe matrix:

```text
output/vqa_contract_launch_probe_20260708_004859/single_entry_matrix_102152
0001: munmap_chunk/free invalid pointer + Wine assertion
0002: free invalid pointer + Wine assertion
0003: free invalid pointer + Wine assertion
0004: free invalid pointer + Wine assertion
0019: free invalid pointer + Wine assertion
0020: free invalid pointer + Wine assertion
```

Confirmation probe with stricter process filtering:

```text
output/vqa_contract_launch_probe_20260708_004859/single_entry_confirm_102429
original MOVIES.MIX: no free/assertion in 18s under the same no-DXVK profile
entry 0000 only: free invalid pointer + Wine assertion
entry 0002 only: free invalid pointer + Wine assertion
```

Native-size control for the same MOVIES path:

```text
build=output/vqa_contract_movies_0004_native_rewrite_20260708/
entry=0004, source=original MOVIES.MIX, target=320x400, prefer_native_frames=yes
local_result=pass; 75/75 frames; exact_block_ratio=1.000000; changed_pixel_ratio=0.000000
runtime_compat=pass; frame_shapes preserved as CBFZ+CPL0+VPTZ:1;VPTZ:74
probe=LOLG_HD_ALLOW_CRASHING_VQA_CONTRACT=1 LOLG_HD_CONTRACT_MOVIES_ONLY_DIR=output/vqa_contract_movies_0004_native_rewrite_20260708/mix ./LOLG_HD.sh wine-vqa-contract-movies-noroom-only --no-dxvk
probe_result=no free/assertion in 22s; timeout closed the Wine desktop
```

Resolution-threshold probes for MOVIES entry 0004, always with original
`LOCALLNG.MIX`, only entry 0004 replaced inside `MOVIES.MIX`, no DXVK, no
dgVoodoo:

```text
320x400: pass local; payload=889686; exact=1.000000; max_vptz=12745; no free/assertion in 22s
640x400: pass local; payload=1193518; exact=0.970592; max_vptz=18128; no free/assertion in 22s
800x500: pass local; payload=2156854; exact=0.471127; max_vptz=32531; no free/assertion in 22s
848x528: pass local; payload=2494246; exact=0.424422; max_vptz=37554; no free/assertion in 22s; X BadWindow only
872x544: pass local; payload=2621904; exact=0.425240; max_vptz=39531; no free/assertion in 22s; X BadWindow only
884x552: pass local; payload=2696934; exact=0.423414; max_vptz=40601; no free/assertion in 22s; X BadWindow only
888x552: pass local; blocks=30636; decoded_vpt_bytes=61272; max_vptz=40545; no free/assertion in 22s; X BadWindow only
892x552: pass local; blocks=30774; decoded_vpt_bytes=61548; max_vptz=40981; no free/assertion in 22s; X BadWindow only
892x556: pass local; blocks=30997; decoded_vpt_bytes=61994; max_vptz=41177; no free/assertion in 22s; X BadWindow only
896x556: pass local; blocks=31136; decoded_vpt_bytes=62272; max_vptz=40231; no free/assertion in 22s; X BadWindow only
892x560: pass local; blocks=31220; decoded_vpt_bytes=62440; max_vptz=41446; no free/assertion in 22s; X BadWindow only
896x560: pass local; payload=2664884; exact=0.437945; max_vptz=40487; free invalid pointer + Wine assertion
1280x1024 profile640: pass local; payload=4000674; exact=0.593463; max_vptz=60988; free invalid pointer + Wine assertion
1280x1024 adaptive: runtime_compat pass but build status gap; max_vptz_size_over_u16
```

This puts the first observed MOVIES entry-0004 heap/assertion boundary between
`892x560` (499,520 pixels/frame, 31,220 blocks, decoded VPT = 62,440 bytes)
and `896x560` (501,760 pixels/frame, 31,360 blocks, decoded VPT = 62,720
bytes). It is not explained by a per-chunk 64K overflow in this entry, because
the failing `896x560` payload still has `max_vptz=40487`.

Custom pair probe:

```text
launcher=LOLG_HD_ALLOW_CRASHING_VQA_CONTRACT=1 ./LOLG_HD.sh wine-vqa-contract-custom-pair --no-dxvk
LOCALLNG=output/vqa_contract_locallng_0002_1024x640_rewrite_20260708/mix/LOCALLNG.MIX
MOVIES=output/vqa_contract_movies_0004_892x560_rewrite_20260708/mix/MOVIES.MIX
pair_dir=output/vqa_contract_pair_locallng1024_movies892_runtime
result=no free/assertion in 22s; X BadWindow only during timeout cleanup
```

This proves the two currently stable candidates can be overlaid together in one
Wine stage. It is still a diagnostic pair, not a complete runtime solution,
because `MOVIES.MIX` only replaces entry 0004 below the measured threshold.

Safe-resolution planning for the rest of MOVIES:

```text
tool=tools/lolg_vqa_safe_resolution_plan.py
command=./LOLG_HD.sh vqa-plan-movies-safe
result=pass; 28 VQA entries; all targets=892x560; decoded VPT=62440 bytes
release_check=vqa_safe_resolution_plan_movies
```

The corresponding full MOVIES rebuild entry point is:

```text
command=./LOLG_HD.sh vqa-contract-build-movies-safe
dry_run=./LOLG_HD.sh vqa-contract-build-movies-safe --dry-run
smoke=./LOLG_HD.sh vqa-contract-build-movies-safe-smoke
long0_batch=./LOLG_HD.sh vqa-contract-build-movies-safe-long0
long1_batch=./LOLG_HD.sh vqa-contract-build-movies-safe-long1
long2_batch=./LOLG_HD.sh vqa-contract-build-movies-safe-long2
long3_batch=./LOLG_HD.sh vqa-contract-build-movies-safe-long3
short_batch=./LOLG_HD.sh vqa-contract-build-movies-safe-short
mid_batch=./LOLG_HD.sh vqa-contract-build-movies-safe-mid
tail_batch=./LOLG_HD.sh vqa-contract-build-movies-safe-tail
output=output/vqa_contract_batch_writer_movies_0000_0027_892x560_safe/mix/MOVIES.MIX
release_check=vqa_contract_movies_safe_build_dry_run
release_check_smoke=vqa_contract_movies_safe_smoke_dry_run
smoke_result=pass; entry=4; profile=4000; runtime_compat=pass; max_vptz=26328
long0_result=pass; entry=0; profile=4000; runtime_compat=pass; max_vptz=31742
long1_result=pass; entry=1; profile=4000; runtime_compat=pass; max_vptz=36492
long2_result=pass; entry=2; profile=4000; runtime_compat=pass; max_vptz=41996
long3_result=pass; entry=3; profile=4000; runtime_compat=pass; max_vptz=41319
short_result=pass; entries=5-18; replaced=14; profile=4000; runtime_compat=pass; max_vptz=27497
mid_result=pass; entries=19-20; replaced=2; profile=4000; runtime_compat=pass; max_vptz=21157
tail_result=pass; entries=21-27; replaced=7; profile=4000; runtime_compat=pass; max_vptz=27356
full_result=pass; entries=0-27; replaced=28; runtime_compat=pass; max_vptz=41996
wine_probe=./LOLG_HD.sh wine-dgvoodoo-win10-safevqa-movies-safe
wine_probe_scope=LOCALLNG original; MOVIES safe 892x560 full; unstable monster/level animation MIX original
wine_probe_real=gap; log=output/test_logs/wine_movies_safe_892_probe_20260708.log; process=LOLG95.EXE detected; error=Unhandled page fault read access 4E683138 at 787CEDF0
wine_probe_guard=LOLG_HD_ALLOW_CRASHING_MOVIES_SAFE=1 required for direct relaunch
```

So the MOVIES crash is not isolated to `TITLE_E` or to entries `0/19/20`.
Several independent 1280 HD MOVIES entries are individually enough to trip the
same heap/free assertion, while a native-size rewritten entry 0004 does not
trip it in the same launcher profile. That points back to an engine VQA
playback heap/buffer budget around 500k pixels per frame for this path, not a
single bad MIX offset or one corrupt entry.

Output:

```text
output/vqa_contract_movies_1280_0000_0027_cbpz_vqaext_noroom_patch/mix/MOVIES.MIX
```

This is still a diagnostic file-level improvement, not proof that critical VQA
replacement is playable in Wine.

## Launcher

These modes are now diagnostic only. They validate that the rebuilt files still
match the file-level VQA contract, but they are blocked by default because real
Wine launch probes show an immediate `Application Error` in the game.

The paired contract mode:

```sh
./LOLG_HD.sh wine-vqa-contract
```

That mode overlays:

```text
LOCALLNG.MIX contract-preserving 1280
MOVIES.MIX contract-preserving 1280, entries 0-27 rebuilt
```

and displays through the Wine launcher at 1920x1080.

The dgVoodoo-backed variant:

```sh
./LOLG_HD.sh wine-vqa-contract-dgvoodoo
```

That mode uses the same contract sidecar pack, disables the global HD MIX pack,
and routes DirectDraw/D3D through dgVoodoo win10. By default it now uses the
active dgVoodoo DLLs from `C/LOLG`; force another source only for diagnostics
with `LOLG_HD_DGVOODOO_SOURCE_DIR=...`.

To force one of these known-crashing modes for a debugger/probe:

```sh
LOLG_HD_ALLOW_CRASHING_VQA_CONTRACT=1 ./LOLG_HD.sh wine-vqa-contract-dgvoodoo
```

Check the contract pack without launching Wine:

```sh
./LOLG_HD.sh vqa-contract-status
```

`vqa-contract-status` now reports the file-level pass plus the known runtime
failure. The LOCALLNG-only mode is also diagnostic and blocked unless the same
override is set:

```sh
./LOLG_HD.sh wine-vqa-contract-locallng
```

That mode keeps `MOVIES.MIX` original, but LOCALLNG HD alone is still enough to
trigger the Wine `Application Error`.

## Runtime Finding

The audit verifies the rebuilt VQA chunk layout, frame count, frame shapes, and
MIX table integrity. It does not prove that `LOLG95.EXE` accepts the larger
critical VQA payloads at runtime. The current Wine/dgVoodoo launch probes show
that the game rejects both critical HD replacements before gameplay.

Native-exact baselines rule out the MIX writer itself:

```text
C/LOLG/MOVIES.MIX sha256 == output/vqa_native_exact_batch_movies_0000_0027/mix/MOVIES.MIX sha256
C/LOLG/LOCALLNG.MIX sha256 == output/vqa_native_exact_batch_locallng_entry2/mix/LOCALLNG.MIX sha256
```

The remaining difference is the enlarged VQA playback budget. The 1280x1024
contract keeps the chunk shape valid, but raises pointer output from about the
original `16000` block budget to `81920` blocks:

```text
MOVIES.MIX[2] original max drawn blocks ~= 15984, decoded VPTZ <= 32000 bytes
MOVIES.MIX[2] 1280 max drawn blocks = 81920, decoded VPTZ = 163840 bytes
LOCALLNG.MIX[2] original decoded VPTZ <= 32000 bytes
LOCALLNG.MIX[2] 1280 decoded VPTZ = 163840 bytes
```

Follow-up LOCALLNG probes tightened this conclusion. Reducing the decoded
pointer budget is not enough with the current generated VQA encoder:

```text
LOCALLNG.MIX[2] 896x560 contract:
  replacement decoded VPTZ = 62720 bytes
  result = Application Error
LOCALLNG.MIX[2] 640x400 rebuilt from HD frames:
  replacement decoded VPTZ = 32000 bytes, max VQFR = 44146
  result = Application Error
LOCALLNG.MIX[2] 640x400 base1024 rebuilt from HD frames:
  replacement decoded VPTZ = 32000 bytes, max VQFR = 17620, max CBFZ = 16646
  result = Application Error
LOCALLNG.MIX[2] 640x400 base1024 padded to original entry size:
  following MIX offsets match original
  result = Application Error
LOCALLNG.MIX[2] 640x400 base1024 compact LCW, padded to original entry size:
  replacement decoded VPTZ = 32000 bytes, max VQFR = 17856, max CBFZ = 7013
  following MIX offsets match original
  result = Application Error
LOCALLNG.MIX[2] 640x400 native-frame rewrite:
  output = output/vqa_contract_locallng_0002_native_rewrite_20260708/
  replacement decoded VPTZ = 32000 bytes, max_vptz = 19227, max_cbfz = 19150
  exact_block_ratio = 1.000000, changed_pixel_ratio = 0.000000
  result = no Wine exception in a 22s no-DXVK probe; X BadWindow only during timeout cleanup
```

LOCALLNG native-frame upscale probes, always with original `MOVIES.MIX`, no
DXVK, no dgVoodoo:

```text
640x400:  pass local; payload=3382036; exact=1.000000; max_vptz=19227; no exception in 22s
800x500:  pass local; payload=5301616; exact=0.610782; max_vptz=29800; no exception in 22s; X BadWindow only
884x552:  pass local; payload=6269862; exact=0.611020; max_vptz=35490; no exception in 22s; X BadWindow only
896x560:  pass local; payload=6387538; exact=0.613883; max_vptz=36059; no exception in 22s; X BadWindow only
960x600:  pass local; payload=7299866; exact=0.745033; max_vptz=41678; no exception in 22s
1024x640: pass local; payload=7660364; exact=0.635010; max_vptz=43658; no exception in 22s
```

So the current in-engine replacement problem is stricter than just resolution or
chunk size. Native-exact bit-identical output works, and a new native-frame
rewrite that is pixel-identical also survives the short Wine probe. Native-frame
upscales through `1024x640` survive the same short LOCALLNG-only probe, while
older HD-derived 640x400/base1024 variants still show `Application Error`.
Keeping the original entry size and subsequent MIX offsets also does not fix
those older HD-derived variants. That points to a content/source-frame path
assumption around how the transformed frames are produced, not simply the MIX
packaging, resolution alone, or the existence of a newly written WVQA file.

Follow-up header/LCW profiling is tracked in
`reports/locallng_vqa_header_lcw_gap.md`. The compact 640x400 rebuild preserves
frame shapes but changes the LCW command profile heavily and also writes smaller
VQHD maxima than the original. The current LCW dialect report is explicit:

```text
output/locallng_vqa_lcw_profile_20260708/dialect.csv
native_exact: CBFZ/CBPZ/VPTZ pass against original
compact/origvqhd: CBPZ and VPTZ gap
VPTZ issues: long_copy_fe_missing;fill_ff_missing;max_command_count_shrunk
```

For the active 1280 contract, the VPTZ dialect is closer but CBPZ remains
different:

```text
output/locallng_vqa_lcw_profile_original_vs_1280_20260708/dialect.csv
LCW dialect: 4/6 pass, gaps=2
windowed1280/adaptive1280 VPTZ: pass
windowed1280/adaptive1280 CBPZ: fill_ff_missing;max_command_count_shrunk
```

A follow-up LOCALLNG-only 1280x1024 candidate pads CBPZ updates to the source
budget and uses the VQA-common extended LCW meanings (`0xFF` fill, `0xFE` long
copy). It was generated from the decoded frames of the previous adaptive 1280
candidate, so it is a contract/runtime candidate rather than a final quality
source:

```text
output/vqa_contract_preserving_writer_locallng_1280x1024_vqaext_padded_cbpz_from_adaptive_decode/
runtime_compat=pass
LCW dialect gate: 3/3 pass, gaps=0
padded1280 CBFZ/CBPZ/VPTZ: pass against original
```

Regenerate it with:

```sh
./LOLG_HD.sh vqa-contract-build-locallng-1280-padded
```

Launcher for a controlled runtime probe:

```sh
LOLG_HD_ALLOW_CRASHING_VQA_CONTRACT=1 ./LOLG_HD.sh wine-vqa-contract-locallng
```

The 896x560 fallback uses the same CBPZ padding idea:

```text
output/vqa_contract_preserving_writer_locallng_896x560_vqaext_padded_cbpz/
runtime_compat=pass
LCW dialect gate: 3/3 pass, gaps=0
padded896 CBFZ/CBPZ/VPTZ: pass against original
```

Regenerate it with:

```sh
./LOLG_HD.sh vqa-contract-build-locallng-896-padded
```

Launcher for a controlled runtime probe:

```sh
LOLG_HD_ALLOW_CRASHING_VQA_CONTRACT=1 ./LOLG_HD.sh wine-vqa-contract-locallng-896-padded
```

A diagnostic variant now restores the original VQHD header while keeping the
compact payload and original MIX offsets:

```text
output/vqa_contract_preserving_writer_locallng_640x400_base1024_compact_origvqhd_padded_offsets/
runtime_compat_audit=pass
Wine smoke=gap, did not reach LOLG95.EXE, so runtime result is not proven
```

Local launch checks after this rebuild:

```text
wine-vqa-contract --dry-run -> pass
wine-vqa-contract-dgvoodoo --dry-run -> pass
vqa-contract-status -> pass, reports MOVIES sha256 and full_manifest.csv
wine-vqa-contract real launch -> Wine prefix fixed, then game exits/throws a direct-launch display exception
wine-vqa-contract-dgvoodoo real launch -> not playable; later visual probe showed an Application Error dialog
```

Follow-up launch probe:

```text
probe=output/vqa_contract_launch_probe_20260708_004859
wine_seh.log -> EXCEPTION_ACCESS_VIOLATION at 00509C19 after NtUserChangeDisplaySettings failure
fix -> force Wine setup for wine-vqa-contract-dgvoodoo, UseXRandR=N, UseXVidMode=N, WindowedAttributes=borderless
wine_seh_forced_setup.log -> no EXCEPTION_ACCESS_VIOLATION, no 00509C19, no Application Error match
remaining behavior -> fixed by no longer forcing the old dgVoodoo backup for contract/safevqa modes
```

`./LOLG_HD.sh stop` now also stops the dedicated
`output/lolg95_vqa_contract_wine_prefix` prefix.

Variants retested after the XRandR fix:

```text
output/vqa_contract_launch_probe_20260708_004859/variants/fl10.log -> status=0, no c0000005/Application Error/NtUserChangeDisplaySettings
output/vqa_contract_launch_probe_20260708_004859/variants/best.log -> status=0, no c0000005/Application Error/NtUserChangeDisplaySettings
output/vqa_contract_launch_probe_20260708_004859/variants/unforced.log -> status=0, no c0000005/Application Error/NtUserChangeDisplaySettings
output/vqa_contract_launch_probe_20260708_004859/variants/warp.log -> status=0, no c0000005/Application Error/NtUserChangeDisplaySettings
output/vqa_contract_launch_probe_20260708_004859/direct_forced_setup.log -> status=1, no c0000005/Application Error, ends after MMX detection
```

The process-lifetime checks were false positives because the Wine `Application
Error` dialog kept `LOLG95.EXE` alive. Visual probes are now required for these
VQA contract experiments.

Final launch isolation:

```text
output/vqa_contract_launch_probe_20260708_004859/originalmix_lifetime_011354/observe.txt
  -> original MIX + active C/LOLG dgVoodoo stayed alive through t=12 until controlled stop
output/vqa_contract_launch_probe_20260708_004859/contract_c_lolg_dgvoodoo_lifetime_011424/observe.txt
  -> process stayed alive through t=15, but this was later invalidated by visual Application Error probes
output/vqa_contract_launch_probe_20260708_004859/contract_default_after_source_fix_011529/observe.txt
  -> process stayed alive through t=15, but this was later invalidated by visual Application Error probes
output/vqa_contract_launch_probe_20260708_004859/wait_after_source_fix_011645/launch.log
  -> --wait mode detected LOLG95.EXE and remained active until controlled stop
output/vqa_contract_launch_probe_20260708_004859/contract_visual_after_source_fix_011816/window.png
  -> LOCALLNG+MOVIES contract pack shows Application Error inside the 1920x1080 Wine desktop
output/vqa_contract_launch_probe_20260708_004859/locallng_only_dgvoodoo_visual_011937/window.png
  -> LOCALLNG contract only, MOVIES original, also shows Application Error
output/vqa_contract_launch_probe_20260708_004859/movies_only_dgvoodoo_visual_012254/window.png
  -> MOVIES contract only, LOCALLNG original, also shows Application Error
output/vqa_contract_launch_probe_20260708_004859/locallng_896_dgvoodoo_visual/window.png
  -> LOCALLNG 896x560 contract, MOVIES original, also shows Application Error
output/vqa_contract_launch_probe_20260708_004859/locallng_640_rebuilt_dgvoodoo_visual/window.png
  -> LOCALLNG rebuilt at original 640x400, MOVIES original, also shows Application Error
output/vqa_contract_launch_probe_20260708_004859/locallng_640_base1024_dgvoodoo_visual/window.png
  -> LOCALLNG rebuilt at 640x400 with smaller chunks than original, still shows Application Error
output/vqa_contract_launch_probe_20260708_004859/locallng_640_base1024_padded_offsets_visual/window.png
  -> LOCALLNG rebuilt at 640x400, padded to original entry size/offsets, still shows Application Error
output/vqa_contract_launch_probe_20260708_004859/locallng_640_base1024_compact_padded_offsets_visual/window.png
  -> LOCALLNG compact LCW, smaller chunks, original entry size/offsets, still shows Application Error
```

The old `cmd /c start /wait` wait path was also removed from `RUN_HD_WINE.sh`.
`--wait` now launches through the Wine desktop and monitors the real
`LOLG95.EXE` process, so wait-mode probes no longer report false success when
`cmd start` exits without launching the game.

Current conclusion: the file-level VQA contract is necessary but not sufficient.
`LOLG95.EXE` appears to require stricter VQA/LCW behavior for critical
`LOCALLNG.MIX` and `MOVIES.MIX` resources than the current writer reproduces.
The playable path remains `safevqa` or another launcher that keeps
`LOCALLNG.MIX` and `MOVIES.MIX` original while using HD replacements for safer
non-critical MIX files. Full critical-VQA replacement needs either a
bit-compatible Westwood encoder, an engine patch, or an external sidecar player.
