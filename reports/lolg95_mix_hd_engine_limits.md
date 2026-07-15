# LOLG95 HD MIX/VQA Engine Limits

Date: 2026-07-07

## Scope

Local reverse-engineering pass on `C/LOLG/LOLG95.EXE` and the current HD archives in `mod_mix_vqa_fullhd/`.

Tools available here: `objdump`, `strings`, local Python parsers. No C decompiler such as Ghidra or IDA was installed, so this is a disassembly-level analysis, not recovered C source.

## Main Conclusion

The failing HD `.MIX` files are not primarily a dgVoodoo problem. They exceed assumptions inside the original 1997 engine:

1. The MIX file layer is 32-bit and uses signed comparisons in several places. One archive, `L20_BBI.MIX`, crosses the 2 GiB signed boundary and cannot be safe as a single HD MIX.
2. The VQA playback layer was built for the original video contract, mostly `640x400` / about `16000` VQA blocks. Current full-HD VQAs are `1920x1080` / `129600` blocks and produce much larger frame/subchunk payloads. Those animations can be valid VQA files but still break the engine playback contract.

This matches the observed behavior: the game can run with safe exclusions, then crash when a large HD monster/level/movie animation starts.

## Engine Evidence

`LOLG95.EXE` imports old 32-bit file APIs:

- `GetFileSize`
- `SetFilePointer`
- `ReadFile`

Relevant disassembly:

- MIX lookup function around `0x004e3c90`: searches loaded MIX tables and returns entry offset/size.
- MIX constructor/loader around `0x004e41e0`: reads MIX header/table and stores count/body/base/table pointer.
- File-size wrapper around `0x004eb544`: calls `GetFileSize`, stores 32-bit size in the file object, then later code uses signed comparisons.
- Seek wrapper around `0x004eb7a0`: calls `SetFilePointer` with `lpDistanceToMoveHigh = NULL`.

Key seek sequence:

```asm
004eb7e3  push esi        ; method
004eb7e4  push 0x0        ; lpDistanceToMoveHigh = NULL
004eb7e6  push edi        ; low 32-bit offset
004eb7eb  call SetFilePointer
```

That is not 64-bit-safe. Offsets and sizes at or above `0x80000000` are dangerous because other code also treats sizes/positions as signed.

The crash address previously seen, `0x00511545`, is downstream:

```asm
00511545  mov edx,DWORD PTR [eax+0x80]
```

This is a graphics/object path reading from an already bad pointer. It is a symptom after a bad VQA/MIX load or decode, not the root cause.

The VQA playback area includes fixed/old buffering and small playback structures:

```asm
0050be46  mov DWORD PTR [0x6a1ea4],0xc0
0050be50  mov DWORD PTR [0x6a1ea8],0x8000
0050be64  push 0x12
0050be66  push 0x832
0050be6b  call 0x507584
0050bebf  cmp ebx,0x13
```

Nearby strings:

- `Cant allocate uncompbuffer`
- `cant allocate playbuffer`
- `VQA playback 4.2 (Dec 04 1997 20:18:14)`

## MIX Risk Summary

Current HD archives with hard or high risk:

| MIX | HD file size | Body size | Biggest entry | Risk |
| --- | ---: | ---: | ---: | --- |
| `L20_BBI.MIX` | 2,496,546,810 | 2,496,541,200 | 165,960,780 | hard 2 GiB signed boundary failure |
| `MOVIES.MIX` | 1,478,753,081 | 1,478,752,727 | 632,087,650 | huge VQA entry/chunk contract risk |
| `L4_HJI.MIX` | 1,741,040,220 | 1,741,038,666 | 174,762,346 | huge VQA contract risk |
| `L8_SJI.MIX` | 1,160,341,794 | 1,160,339,856 | 196,726,134 | huge VQA contract risk |
| `L1_DCI.MIX` | 735,739,406 | 735,738,968 | 232,433,956 | huge VQA contract risk |
| `L3_DHI.MIX` | 287,942,282 | 287,942,108 | 109,513,814 | huge VQA contract risk |

`L20_BBI.MIX` is the only confirmed hard 2 GiB MIX-layer failure in this scan. The others are below 2 GiB but contain VQA payloads that are far outside the original runtime contract.

The MIX tables themselves are not the obvious bug: original and HD tables scan as correctly signed-sorted for the engine's binary search.

## VQA Contract Comparison

Examples measured by streaming VQA headers/chunk metadata, without loading whole entries into memory:

### Original `C/LOLG`

| Entry | Header | Blocks | Entry size | Max VQFR | Max VPTZ |
| --- | --- | ---: | ---: | ---: | ---: |
| `MOVIES.MIX[2]` | 640x400, 3576 frames | 16000 | 82,206,194 | 77,786 | 27,514 |
| `LOCALLNG.MIX[2]` | 640x400, 237 frames | 16000 | 3,356,566 | 24,786 | 19,383 |
| `L20_BBI.MIX[400]` | 640x400, 1080 frames | 16000 | 23,140,542 | 55,844 | 25,331 |
| `L1_DCI.MIX[5]` | 640x400, 1378 frames | 16000 | 36,161,114 | 56,956 | 24,133 |
| `L3_DHI.MIX[6]` | 640x400, 692 frames | 16000 | 18,107,180 | 28,940 | 23,940 |

### HD `mod_mix_vqa_fullhd`

| Entry | Header | Blocks | Entry size | Max VQFR | Max VPTZ |
| --- | --- | ---: | ---: | ---: | ---: |
| `MOVIES.MIX[2]` | 1920x1080, 3576 frames | 129600 | 632,087,650 | 205,046 | 173,637 |
| `LOCALLNG.MIX[2]` | 1920x1080, 237 frames | 129600 | 28,143,414 | 155,488 | 125,735 |
| `L20_BBI.MIX[400]` | 1920x1080, 1080 frames | 129600 | 165,960,780 | 182,680 | 161,166 |
| `L1_DCI.MIX[5]` | 1920x1080, 1378 frames | 129600 | 232,433,956 | 183,702 | 168,227 |
| `L3_DHI.MIX[6]` | 1920x1080, 692 frames | 129600 | 109,513,814 | 167,924 | 153,839 |

The important jump is not only file size. Block count goes from about `16000` to `129600`, and compressed VQFR/VPTZ chunks become several times larger. That is enough to break old buffer sizing, 16-bit fields, allocation paths, or playback ring assumptions.

### 1280 Contract Probe Update

The 1280x1024 contract-preserving rebuild fixed the file-level VQA audit but
still fails in the real Wine/dgVoodoo runtime:

| Probe | Runtime result |
| --- | --- |
| `LOCALLNG.MIX[2]` contract only, `MOVIES.MIX` original | `Application Error` before gameplay |
| `MOVIES.MIX` contract only, `LOCALLNG.MIX` original | `Application Error` before gameplay |
| `LOCALLNG.MIX` + `MOVIES.MIX` contract pair | `Application Error` before gameplay |

Native-exact writer baselines are bit-identical to the originals, so the writer
and MIX table rewrite path are not the trigger:

```text
C/LOLG/MOVIES.MIX == output/vqa_native_exact_batch_movies_0000_0027/mix/MOVIES.MIX
C/LOLG/LOCALLNG.MIX == output/vqa_native_exact_batch_locallng_entry2/mix/LOCALLNG.MIX
```

The 1280x1024 files still exceed the original playback buffer shape. Example
runtime audit maxima:

```text
MOVIES.MIX[2] original drawn blocks ~= 15984, decoded VPTZ <= 32000 bytes
MOVIES.MIX[2] 1280 drawn blocks = 81920, decoded VPTZ = 163840 bytes
LOCALLNG.MIX[2] original decoded VPTZ <= 32000 bytes
LOCALLNG.MIX[2] 1280 decoded VPTZ = 163840 bytes
```

That strongly points to an in-engine VQA playback limit near the original
640x400 block budget, not a dgVoodoo version problem.

Follow-up LOCALLNG-only probes show an even stricter limit with the current
generated VQA encoder:

```text
LOCALLNG.MIX[2] 896x560:
  decoded VPTZ = 62720 bytes, still Application Error
LOCALLNG.MIX[2] 640x400 rebuilt from HD frames:
  decoded VPTZ = 32000 bytes, max VQFR = 44146, still Application Error
LOCALLNG.MIX[2] 640x400 base1024:
  decoded VPTZ = 32000 bytes, max VQFR = 17620, max CBFZ = 16646, still Application Error
LOCALLNG.MIX[2] 640x400 base1024 padded to original entry size:
  following MIX offsets match original, still Application Error
LOCALLNG.MIX[2] 640x400 base1024 compact LCW, padded to original entry size:
  decoded VPTZ = 32000 bytes, max VQFR = 17856, max CBFZ = 7013, still Application Error
```

Native-exact rebuilt payloads are bit-identical to the original and hash-match
the original MIX files, but newly encoded critical VQAs crash even at 640x400.
Keeping the original entry size and downstream MIX offsets also fails. That
means a smaller in-engine VQA is not sufficient unless the encoder is
bit-compatible with the original Westwood decoder path or the engine is patched.

Additional LOCALLNG profiling in `reports/locallng_vqa_header_lcw_gap.md`
shows that the compact 640x400 rebuild also changes VQHD buffer maxima and LCW
opcode mix versus the original. The mechanical LCW dialect comparison now
reports `5/9` pass rows: native-exact preserves CBFZ/CBPZ/VPTZ, while compact
and restored-VQHD variants lose `long_copy_fe`/`fill_ff` usage and shrink the
maximum VPTZ command count from `65409` to `64`. The active 1280 contract is
closer for VPTZ (`windowed1280` reaches `65535`, `adaptive1280` reaches
`55634`), but both legacy 1280 variants still differ on CBPZ
(`fill_ff_missing;max_command_count_shrunk`). A new 1280x1024 LOCALLNG
candidate uses VQA-common extended LCW plus CBPZ padding and improves the
dialect result: `runtime_compat=pass`, `LCW dialect gate: 3/3 pass`, and
`padded1280` passes CBFZ/CBPZ/VPTZ against the original profile. It is exposed
only as a controlled diagnostic launcher:
`LOLG_HD_ALLOW_CRASHING_VQA_CONTRACT=1 ./LOLG_HD.sh wine-vqa-contract-locallng`.
The older 896x560 padded candidate remains available as a fallback diagnostic.
A separate diagnostic variant
restores the original VQHD header and original MIX offsets while keeping the
compact 640x400 payload; its local audit passes, but the bounded Wine smoke did
not reach `LOLG95.EXE`, so the runtime effect remains unproven.

MOVIES spot checks now show the same CBPZ-specific risk on selected entries:
`MOVIES[2]` and `MOVIES[3]` pass the LCW dialect gate, while `MOVIES[0]`,
`MOVIES[19]`, and `MOVIES[20]` keep CBPZ
`long_copy_fe_missing;fill_ff_missing;max_command_count_shrunk`. VPTZ is not
the obvious remaining MOVIES gap in those samples.

## Practical Fix Direction

Keep the current `safevqa` strategy for stable launching:

- Exclude `MOVIES.MIX`.
- Exclude `LOCALLNG.MIX` HD animation replacement unless rebuilt under a safer contract.
- Exclude HD monsters, level animations, and animated effects that use 1920x1080 VQA.

For a better HD pack without crashes:

1. `L20_BBI.MIX` must be split, sidecar-loaded, or reduced below the 2 GiB signed boundary. As one normal MIX, it is not compatible with the engine.
2. Rebuild VQAs with a contract closer to the original engine:
   - keep critical in-engine VQA original unless a bit-compatible encoder is available;
   - treat 1280x1024 in-engine VQA as failed for `LOCALLNG.MIX` and `MOVIES.MIX`;
   - treat current generated LOCALLNG VQA as failed even at 640x400/base1024;
   - cap VQFR/VPTZ sizes aggressively;
   - keep block count closer to original where possible;
   - preserve original frame counts/audio timing.
3. If full 1920x1080 VQA is mandatory, patching `LOLG95.EXE` is larger work:
   - replace file size/seek wrappers with 64-bit-safe logic;
   - audit and patch VQA buffer allocation and frame playback structures;
   - re-test both Wine and Windows, because the limit is inside the game binary.
