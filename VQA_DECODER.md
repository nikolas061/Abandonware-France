# VQA Decoder Notes

`tools/lolg_vqa_decode.py` starts a local frame-by-frame decoder and renderer
for Westwood VQA files used by Lands of Lore II.

No external video tool is used.

## What works

- Reads direct `FORM/WVQA` files.
- Reads a VQA payload directly from a `.MIX` archive with `--entry`.
- Parses the top-level IFF-style chunks.
- Parses `VQHD` into a JSON header.
- Parses each `VQFR` frame into subchunks.
- Decompresses many LCW/Format80 `*Z` chunks, including working `CBFZ` and
  `VPTZ` cases from the game data.
- Decodes `CBFZ` streams with a header-derived codebook size when the stream
  has no explicit end marker.
- Decodes stateful `VPTZ` delta streams that copy from the previous pointer
  table, reported as `lcw_delta` in `frames.csv`.
- Decodes many `CBPZ` partial codebook payloads for inspection. Complete
  decodes are reported as `lcw`; bounded partial decodes are reported as
  `lcw_partial`. With `--experimental-window-lcw`, later compact `CBPZ`
  streams may also decode as `lcw_window*` for inspection.
- Applies vector-aligned `CBPZ`/`CBP0` append updates to the active codebook
  when a full `CBFZ`/`CBF0` base is already available. The renderer caps the
  append at the header's declared codebook capacity and reports ignored bytes.
- Exports per-frame decoded payloads when `--dump-payloads` is used.
- Exports palette previews, codebook previews, and `VPTZ` pointer-map previews.
- Renders native paletted PNG frames from `CBFZ`/`CBF0` codebooks and
  `VPTZ`/`VPT0` block pointers.
- Renders experimental `VPRZ`/`VPTR` pointer streams by expanding `0xa0NN`
  skip runs and low-12-bit codebook indices.
- Optionally decodes compact pointer streams with `--experimental-window-lcw`.
  This 64K-window LCW fallback is marked experimental in manifests and handles
  the first-frame `VPTZ`/`VPRZ` families that reference `0x82xx`/`0x83xx`
  window addresses.
- Preserves the previous frame for block pointers that do not address the
  active codebook. The first frame starts from black.
- Emits `held_frame` PNGs for declared frames that have palette/codebook state
  but no pointer chunk. These frames save the current frame buffer so all-frame
  exports keep one native and one Full HD PNG per declared VQA frame.
- Can treat a palette index as transparent with `--transparent-index`. This is
  useful for overlay-style VQA frames whose palette index 0 is a bright key
  color rather than black.
- Exports rendered frames as 1920x1080 PNG images with `--fullhd`.
- Writes `rendered_frames.csv` with draw/skip counts, partial codebook update
  status, applied update-vector counts, ignored update-byte counts, CBP decode
  diagnostics, and pointer index statistics per frame.

## Current limits

This is now a first real frame renderer, but it is not yet a complete VQA
implementation.

Known remaining work:

- Complete every LCW/Format80 edge case seen in `ARENA.MIX`.
- Decode and apply every `CBPZ` delta/update chunk that appears after the first
  frame in some VQA files.
- Finish non-append `CBPZ`/`CBP0` update forms across later frames. Several
  later `CBPZ` chunks now decode with the experimental 64K-window LCW fallback,
  but the renderer only applies the safe append case until the replacement
  mapping is proven.
- Promote the experimental 64K-window LCW pointer fallback to stable only after
  more visual validation across animations. It renders the first-frame sweep,
  but many outputs are still marked experimental.
- A 64K memory-window LCW hypothesis produced statistical candidates for many
  of those streams, but visual probes in `output/vqa_decode/window_experiments`
  still show strong artifacts, so it is not part of the stable renderer.
- Finish validating every `VPRZ`/`VPTR` command form. The current expansion
  works on tested samples but is still marked experimental in the manifest.
- Add audio handling later if needed.

## Example commands

Print structure information for a VQA stored in a `.MIX` entry:

```sh
tools/lolg_vqa_decode.py C/LOLG/ALTAR.MIX --entry 4 --info
```

Decode the first three frames into inspectable artifacts:

```sh
tools/lolg_vqa_decode.py C/LOLG/ALTAR.MIX --entry 4 \
  -o output/vqa_decode/ALTAR_0004 \
  --max-frames 3 \
  --dump-payloads
```

Render the first three frames as native PNGs and Full HD PNGs:

```sh
tools/lolg_vqa_decode.py C/LOLG/ALTAR.MIX --entry 4 \
  -o output/vqa_decode/ALTAR_0004_RENDER \
  --max-frames 3 \
  --dump-payloads \
  --fullhd
```

Render overlay-like frames while preserving pixels where codebook vectors use
palette index 0:

```sh
tools/lolg_vqa_decode.py C/LOLG/L10_DCI.MIX --entry 46 \
  -o output/vqa_decode/L10_DCI_0046_TRANSPARENT0 \
  --max-frames 6 \
  --dump-payloads \
  --fullhd \
  --experimental-window-lcw \
  --transparent-index 0
```

Batch-render the first frame from VQA entries in multiple archives:

```sh
tools/lolg_vqa_batch_export.py C/LOLG/ALTAR.MIX C/LOLG/ARENA.MIX C/LOLG/CAN.MIX \
  -o output/vqa_batch_probe \
  --max-frames 1 \
  --limit 5 \
  --dump-payloads \
  --quiet
```

Batch-render with the experimental 64K-window LCW pointer fallback:

```sh
tools/lolg_vqa_batch_export.py C/LOLG/*.MIX \
  -o output/vqa_batch_window_lcw_firstframes \
  --max-frames 1 \
  --quiet \
  --experimental-window-lcw
```

Batch-render every frame from each selected VQA entry:

```sh
tools/lolg_vqa_batch_export.py C/LOLG/L10_DCI.MIX \
  -o output/vqa_batch_allframes_probe \
  --all-frames \
  --limit 1 \
  --quiet \
  --experimental-window-lcw \
  --transparent-index 0
```

For very large all-frame exports, add `--fast-png` to disable PNG compression
optimization and trade larger files for faster writes. Add `--skip-existing`
when resuming a long export so entries with an existing `rendered_frames.csv`
are reused instead of rendered again. The batch manifest is written
incrementally after each VQA entry, so an interrupted run leaves a partial
`manifest.csv` that can still be inspected. Add `--progress-every 25` or a
similar value to print periodic batch progress during long runs. Add
`--rerender-incomplete` with `--skip-existing` when repairing an export: entries
are skipped only when the native and Full HD PNG counts match the expected
frame count, `rendered_frames.csv` has continuous frame indices, every row is
output-producing (`rendered` or `held_frame`), and the referenced PNG files
exist.

After a full export, verify the finished directory against the manifest:

```sh
tools/lolg_vqa_verify_export.py output/vqa_batch_allframes_probe --expect-all
```

This writes `verification.csv` with the actual native/Full HD PNG counts per
entry, render-row counts, held-frame counts, missing output paths/files, frame
index gaps, count mismatches, missing directories, and any entries that do not
match their declared frame count.

The frame output contains:

- `header.json`
- `frames.csv`
- `rendered_frames.csv` when `--render-frames` or `--fullhd` is used
- `frame_XXXX/*.bin` decoded payloads
- `palette.png`
- `*_codebook.png`
- `*_pointer_map.png`
- `frames_native/frame_XXXX.png` when frame rendering is enabled
- `frames_fullhd/frame_XXXX_fullhd.png` when `--fullhd` is used

Batch output contains one directory per VQA entry and a global
`manifest.csv`. The global manifest repeats the first rendered frame status,
native dimensions, declared frame count, block grid, pointer chunk, codebook
vector count, CBP decode/update status, block draw/skip counts, pointer index
statistics, per-entry render status counts, held-frame counts, output PNG
counts, and pointer decode diagnostics so it can be filtered without opening
each subdirectory. The pointer diagnostics include the chunk name, decode
status, source size, expected decoded size for `VPT*`, decoded size when
successful, first 8 source bytes as hex, and the decode error when present.

Current verified rendered samples:

- `output/vqa_decode/ALTAR_0004_RENDER`: 3 native frames and 3 Full HD frames.
- `output/vqa_decode/ARENA_0002_RENDER`: 5 native frames and 5 Full HD frames,
  including `lcw_delta` VPT frames.
- `output/vqa_decode/CHUT_0037_CBP_APPLY`: 3 native frames and 3 Full HD
  frames from the stable path; frame 0 appends 103 `CBPZ` vectors to the
  active codebook.
- `output/vqa_decode/CHUT_0037_DIAG`, `output/vqa_decode/MOVIES_0020_DIAG`,
  and `output/vqa_decode/L10_DCI_0046_DIAG`: 6 native frames and 6 Full HD
  frames each, with CBP decode diagnostics, pointer index statistics, and
  experimental `CBPZ` window-LCW inspection where applicable.
- `output/vqa_decode/L10_DCI_0046_TRANSPARENT0`: 6 native frames and 6 Full HD
  frames with palette index 0 treated as transparent. This removes the cyan key
  color from the overlay-style frames, but the compact pointer decode is still
  experimental.
- `output/vqa_decode/CAN_0034_RENDER`: 3 native frames and 3 Full HD frames
  from `VPRZ`.
- `output/vqa_decode/CAN_0017_RENDER`: 3 native frames and 3 Full HD frames
  from a small `VPRZ` animation.
- `output/vqa_decode/DANIEL_0001_RENDER`: 3 native frames and 3 Full HD frames
  from `VPRZ`.
- `output/vqa_batch_probe`: 5 VQA entries batch-rendered with one Full HD
  frame each.
- `output/vqa_batch_cbp_chut_probe`: 28 `CHUT.MIX` VQA entries batch-rendered;
  one first frame applies a truncated `CBPZ` append update.
- `output/vqa_batch_firstframes`: all 1955 detected VQA entries scanned; 999
  first frames exported as Full HD PNGs, with CBP append updates reflected in
  each `rendered_frames.csv`.
- `output/vqa_batch_window_lcw_firstframes`: all 1955 detected VQA entries
  scanned with `--experimental-window-lcw`; 1955 first frames exported as Full
  HD PNGs. Every frame rendered, but 956 entries use experimental windowed
  pointer decodes.
- `output/vqa_batch_window_lcw_transparent0_firstframes`: all 1955 detected VQA
  entries scanned with `--experimental-window-lcw --transparent-index 0`;
  1955 first frames exported as native PNGs and Full HD PNGs. This keeps the
  same coverage while preserving prior pixels for palette index 0.
- `output/vqa_batch_allframes_probe`: one `L10_DCI.MIX` VQA entry batch-rendered
  with `--all-frames`; 81 native frames and 81 Full HD frames exported.
- `output/vqa_batch_window_lcw_transparent0_allframes`: all 1955 detected VQA
  entries batch-rendered with `--all-frames --experimental-window-lcw
  --transparent-index 0`; 171167 native frames and 171167 Full HD frames
  exported. `tools/lolg_vqa_verify_export.py ... --expect-all --fail-on-issues`
  verifies 171167 render rows and reports 0 entries with issues. Four entries
  contain 13 `held_frame` rows where the VQA declares frames without pointer
  chunks:
  - `L12_CMI.MIX#0029`: 9 held frames and 1338 rendered frames.
  - `L1_DCI.MIX#0000`: 1 held frame and 834 rendered frames.
  - `L1_DCI.MIX#0005`: 1 held frame and 1377 rendered frames.
  - `L5_HCI.MIX#0003`: 2 held frames and 147 rendered frames.

Current first-frame batch coverage:

- 1955 VQA entries scanned.
- 999 entries rendered to native PNG and Full HD PNG.
- 1954 `CBFZ` codebooks decoded.
- 960 `CBPZ` payloads decoded for inspection:
  - 382 complete `lcw` decodes.
  - 578 bounded `lcw_partial` decodes.
- 1 stored `CBP0` payload decoded.
- 961 first-frame CBP updates applied to active codebooks:
  - 252 exact vector appends.
  - 39 appends with trailing unaligned bytes ignored.
  - 670 appends truncated at the header's codebook capacity.
- 131465 CBP vectors appended across the first-frame sweep.
- 956 entries parsed but not rendered yet, all currently `no_vpt`; all 956 now
  report an active codebook vector count, but their compact `VPTZ`/`VPRZ`
  pointer streams still need another compression/RLE command form.
- Pointer decode diagnostics from the enriched global manifest:
  - 935 first-frame `VPTZ` streams still fail LCW decoding.
  - 21 first-frame `VPRZ` streams still fail LCW decoding.
  - The dominant failed `VPTZ` families start with `8100fe...` and reference
    absolute copy sources such as `0x8300`, `0x8200`, or `0x8400` immediately
    after writing one byte.
  - Frequent expected pointer-table sizes among those failures are 8970 bytes
    and 5782 bytes.
- Experimental first-frame batch coverage with `--experimental-window-lcw`:
  - 1955 VQA entries scanned.
  - 1955 entries rendered to native PNG and Full HD PNG.
  - 956 entries converted from `no_vpt` to `rendered`.
  - Converted pointer statuses:
    - 342 `VPTZ` `lcw_window`.
    - 339 `VPTZ` `lcw_window_ff80`.
    - 200 `VPTZ` `lcw_window_end`.
    - 44 `VPTZ` `lcw_window_literal_tail`.
    - 10 `VPTZ` `lcw_window_eof`.
    - 18 `VPRZ` `lcw_window_end`.
    - 3 `VPRZ` `lcw_window`.
- Transparent experimental first-frame batch coverage with
  `--experimental-window-lcw --transparent-index 0`:
  - 1955 VQA entries scanned.
  - 1955 entries rendered to native PNG and Full HD PNG.
  - Pointer decode status distribution matches the non-transparent
    experimental sweep.
  - Every render note records `Palette index 0 treated as transparent`.
