# LOCALLNG VQA Header/LCW Gap

Date: 2026-07-08

## Context

`LOCALLNG.MIX[2]` still crashes the game when replaced by newly encoded VQA
payloads, even when rebuilt at the original `640x400` resolution and padded to
the original MIX entry size/offsets.

The file-level runtime audit passes for the compact 640x400 rebuild, so the
next suspect is not the MIX table or high-level chunk shape. It is the exact
VQA header/buffer contract and LCW command profile expected by the 1997 player.

## Header Comparison

```text
original:
  640x400 frames=237 blocks=16000 max_cb=4000
  VQHD max_cbfz=52198 max_vptz=22048
  max_vqfr=24786 max_sub={CBFZ:22479, CBPZ:1504, CPL0:768, VPTZ:19383}

native_exact:
  same as original, byte-identical baseline

640_windowed:
  VQHD max_cbfz=43172 max_vptz=18209
  max_vqfr=44146 max_sub={CBFZ:43172, CBPZ:4016, CPL0:768, VPTZ:18209}

640_base1024:
  VQHD max_cbfz=16646 max_vptz=16919
  max_vqfr=17620 max_sub={CBFZ:16646, CBPZ:7657, CPL0:768, VPTZ:16919}

640_compact:
  VQHD max_cbfz=7013 max_vptz=17837
  max_vqfr=17856 max_sub={CBFZ:7013, CBPZ:3831, CPL0:768, VPTZ:17837}
```

The compact rebuild is smaller than the original at the MIX/VQFR level, but it
also writes much smaller VQHD maxima. If `LOLG95.EXE` allocates playback buffers
from those VQHD fields and then the Westwood LCW decoder expands through a
larger internal buffer/window, a rebuilt payload can crash even at `640x400`.

## LCW Profile Difference

Repro command:

```sh
python3 tools/lolg_vqa_lcw_profile.py \
  --case original=C/LOLG/LOCALLNG.MIX,2 \
  --case native_exact=output/vqa_native_exact_batch_locallng_entry2/mix/LOCALLNG.MIX,2 \
  --case compact=output/vqa_contract_preserving_writer_locallng_640x400_from_hd_base1024_compact/payloads/LOCALLNG/fca4e133.vqa \
  --case origvqhd=output/vqa_contract_preserving_writer_locallng_640x400_base1024_compact_origvqhd_padded_offsets/payloads/LOCALLNG/fca4e133_origvqhd_padded_3356566.vqa \
  -o output/locallng_vqa_lcw_profile_20260708
```

The tool now also writes `dialect.csv`, comparing every non-reference case to
the original LCW command dialect. Current result:

```text
LCW dialect: 5/9 pass, gaps=4
native_exact: pass for CBFZ, CBPZ, VPTZ
compact/origvqhd: gap for CBPZ and VPTZ
```

Original and native-exact are identical. The compact 640x400 rebuild preserves
the frame shapes but changes the LCW profile substantially:

```text
original CBFZ:
  source_bytes=22479 literal_ops=2084 short_rel=3676 abs_copy=3051

640_compact CBFZ:
  source_bytes=7013 literal_ops=485 short_rel=1732 abs_copy=516

original VPTZ:
  source_bytes=3067127 literal_ops=220059 short_rel=528149
  abs_copy=115597 long_fe=1434 fill_ff=3596

640_compact VPTZ:
  source_bytes=2644750 literal_ops=333326 short_rel=467842
  abs_copy=202490 long_fe=0 fill_ff=0
```

That means the generated file is not bit-compatible with the original encoder's
LCW grammar, even when it fits the high-level VQA contract.

The strongest VPTZ contrast is that the original uses `long_fe`/`fill_ff`
commands, including a first-frame fill count of `65409`, while the compact
writer emits no `long_fe` or `fill_ff` for VPTZ and relies on smaller
literal/relative/absolute-copy commands.

`dialect.csv` records the same issue mechanically:

```text
compact VPTZ: long_copy_fe_missing;fill_ff_missing;max_command_count_shrunk
origvqhd VPTZ: long_copy_fe_missing;fill_ff_missing;max_command_count_shrunk
compact CBPZ: fill_ff_missing;max_command_count_shrunk
origvqhd CBPZ: fill_ff_missing;max_command_count_shrunk
```

The current 1280 contract variants show a narrower gap:

```sh
python3 tools/lolg_vqa_lcw_profile.py \
  --case original=C/LOLG/LOCALLNG.MIX,2 \
  --case windowed1280=output/vqa_contract_preserving_writer_locallng_1280x1024_windowed_extlcw/payloads/LOCALLNG/fca4e133.vqa \
  --case adaptive1280=output/vqa_contract_preserving_writer_locallng_1280x1024_adaptive_extlcw/payloads/LOCALLNG/fca4e133.vqa \
  -o output/locallng_vqa_lcw_profile_original_vs_1280_20260708
```

```text
LCW dialect: 4/6 pass, gaps=2
windowed1280 VPTZ: pass, max_command_count=65535
adaptive1280 VPTZ: pass, max_command_count=55634
windowed1280/adaptive1280 CBPZ: fill_ff_missing;max_command_count_shrunk
```

So the 1280 contract has mostly restored the VPTZ command dialect, but the
CBPZ update stream still differs from the original. The next encoder probe
should focus on CBPZ padding/update compatibility.

That probe now exists:

Primary 1280x1024 candidate:

```sh
./LOLG_HD.sh vqa-contract-build-locallng-1280-padded
```

Result:

```text
VQA contract-preserving writer: pass
Runtime compat: pass
Frames: 237/237
payload=6169058 bytes
LCW dialect gate: 3/3 pass, gaps=0
padded1280 CBFZ/CBPZ/VPTZ: pass against original
adaptive1280 CBPZ: fill_ff_missing;max_command_count_shrunk
```

It is generated from the decoded frames of the previous adaptive 1280
candidate. That makes it the best current contract/runtime probe, not the final
quality source.

Fallback 896x560 candidate:

```sh
./LOLG_HD.sh vqa-contract-build-locallng-896-padded
```

Result:

```text
VQA contract-preserving writer: pass
Runtime compat: pass
Frames: 237/237
payload=4117992 bytes
LCW dialect gate: 3/3 pass, gaps=0
padded896 CBFZ/CBPZ/VPTZ: pass against original
windowed896 CBPZ: fill_ff_missing;max_command_count_shrunk
```

These candidates keep the file-level runtime audit passing and restore the
measured CBPZ dialect gap. They still need a
controlled Wine runtime probe because previous LOCALLNG HD variants crashed
before gameplay.

## New Diagnostic Variant

Generated:

```text
output/vqa_contract_preserving_writer_locallng_640x400_base1024_compact_origvqhd_padded_offsets/
```

This variant takes the compact 640x400 payload, restores the exact original
`VQHD` header, and keeps the original MIX entry size/offsets.

Verification:

```text
entry_size=3356566
VQHD=640x400 frames=237 max_cbfz=52198 max_vptz=22048
MIX entry2 offset/size match original
runtime_compat_audit=pass
```

Bounded Wine smoke:

```text
output/hd_wine_smoke_test_locallng_640_compact_origvqhd/summary.csv
status=gap
issues=resolution_mismatch;process_not_seen;window_not_seen
visible window only: Command Prompt
```

This smoke did not reach `LOLG95.EXE`, so it does not prove whether the restored
VQHD header fixes the `Application Error`. It only validates the staged file
shape and identifies the next focused runtime probe.

## Next Probe

Run the restored-VQHD LOCALLNG variant through the same visual Wine/dgVoodoo
probe that previously captured the `Application Error` windows. If it still
fails, the stronger remaining hypothesis is LCW opcode/window compatibility,
not VQHD allocation fields.
