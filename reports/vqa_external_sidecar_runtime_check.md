# VQA external sidecar runtime check

Date: 2026-07-08

## Verified commands

```sh
./LOLG_HD.sh sidecar-status
./LOLG_HD.sh sidecar-status --events 10
./LOLG_HD.sh sidecar-live-strace --no-web --timeout 20 --max-frames 1
./LOLG_HD.sh sidecar-live-strace-player --no-game --dry-run
./LOLG_HD.sh sidecar-live-strace-all-player --no-game --dry-run
./LOLG_HD.sh sidecar-live-strace-wide-all-player --no-game --dry-run
./LOLG_HD.sh sidecar-live-strace-wide-all-player --player-hud --no-game --dry-run
./LOLG_HD.sh sidecar-live-strace-wide-all-hud --no-game --dry-run
./LOLG_HD.sh sidecar-live-strace-wide-player --no-web --no-game --smoke --max-frames 1 --smoke-timeout 10
./LOLG_HD.sh sidecar-hd --no-game --no-web --smoke --smoke-timeout 15
./LOLG_HD.sh sidecar-trace-bridge \
  --trace-file output/vqa_external_sidecar_runtime/trace.log \
  --request-file output/vqa_external_sidecar_runtime/request.json \
  --result-file output/vqa_external_sidecar_runtime/result.json \
  --event-log output/vqa_external_sidecar_runtime/events.jsonl \
  --latest-event-file output/vqa_external_sidecar_runtime/latest_event.json \
  --max-frames 0 --process
./LOLG_HD.sh sidecar-web --check --summary
./LOLG_HD.sh sidecar-web --status --events 6
./LOLG_HD.sh sidecar-trace-bridge --line "archive=HERB.MIX index=46" --cache-root /tmp/lolg_sidecar_preserve_cache --request-file /tmp/lolg_sidecar_preserve_runtime/request.json --result-file /tmp/lolg_sidecar_preserve_runtime/result.json --event-log /tmp/lolg_sidecar_preserve_runtime/events.jsonl --latest-event-file /tmp/lolg_sidecar_preserve_runtime/latest_event.json --max-frames 1 --process
./LOLG_HD.sh sidecar-trace-bridge --line "archive=HERB.MIX index=46" --cache-root /tmp/lolg_sidecar_preserve_cache --request-file /tmp/lolg_sidecar_preserve_runtime/request.json --result-file /tmp/lolg_sidecar_preserve_runtime/result.json --event-log /tmp/lolg_sidecar_preserve_runtime/events.jsonl --latest-event-file /tmp/lolg_sidecar_preserve_runtime/latest_event.json --max-frames 0 --process
```

## Current result

- Manifest: `output/vqa_external_sidecar_index/manifest.json`
- Manifest status: `pass`
- Indexed HD MIX archives: `66`
- Indexed HD VQA entries: `1955`
- Hard 2 GiB archives: `1`
- Engine mode: `wine-dgvoodoo-win10-safevqa`
- VQA mode: `external_sidecar_player`
- Recommended live mode after the in-engine LOCALLNG/MOVIES failures:
  `./LOLG_HD.sh sidecar-hd`

This is now the practical route for critical VQA HD playback. The in-engine
contract path still crashes with `Application Error` for `LOCALLNG.MIX` and
`MOVIES.MIX` replacements, including smaller 640x400 LOCALLNG variants. The
sidecar keeps the Wine game on the stable safevqa runtime and displays the HD
VQA frames externally.

The real Wine/strace runtime check completed without a sidecar harness error.
`output/vqa_external_sidecar_runtime/strace_bridge_summary.json` reports:

```text
status=pass
lines=559370
open_mix_hits=81
read_mix_hits=7608
emitted_trace_lines=1
```

The emitted runtime event decoded:

```text
key=LOCALLNG.MIX:fca4e133
archive=LOCALLNG.MIX
index=2
offset=78
method=original_archive_offset
status=decoded
width=1920
height=1080
```

`./LOLG_HD.sh sidecar-web --check` sees the decoded player inventory:

```text
key=LOCALLNG.MIX:fca4e133
status=decoded
frames_ready=237
frames_total=237
width=1920
height=1080
```

The complete replay from the real trace decoded all frames for that VQA:

```text
Decoded 237 frames to output/vqa_external_sidecar_cache/LOCALLNG.MIX/fca4e133/decode
```

## Wide strace mode

The regular strace bridge emits only MIX reads whose visible buffer starts with
`FORM`. The optional wide mode emits all MIX reads, deduplicates by
archive/offset/syscall, and asks the trace bridge to emit each VQA key once per
session:

```text
sidecar-live-strace-wide-player
sidecar-live-strace-wide-all-player
```

On the same short Wine startup trace, the wide replay produced more candidate
hints but still resolved the same single startup VQA, which matches the run
scope:

```text
form_only_emitted_trace_lines=1
wide_emitted_trace_lines=26094
wide_pass_matches=677
wide_unique_keys=1
wide_unique_key=LOCALLNG.MIX:fca4e133
```

The wide mode is intended for longer gameplay sessions where Wine may split the
VQA reads so the visible `FORM` header is not enough.

The trace watcher is incremental: in `--watch` mode it keeps the manifest and
original MIX indexes loaded, then resolves only newly appended trace lines. This
keeps the wide mode from rereading a growing trace file on every poll.

## Event status

`./LOLG_HD.sh sidecar-status --events N` prints the recent event history from
`output/vqa_external_sidecar_runtime/events.jsonl`, including decoded key count,
unique decoded VQA keys, source trace lines, and ready frame counts. This is the
fast terminal check to run after a gameplay session.

`./LOLG_HD.sh sidecar-audit --events N` adds session coverage: how many VQA were
decoded in this run versus the full external manifest, which archives were
touched, decode failures if any, and the explicit reminder that this path is an
external player rather than an in-engine replacement.

`./LOLG_HD.sh sidecar-web --status --events N` exposes the same compact state as
JSON for the browser/player. The player accepts `?hud=1` and displays a small
diagnostic overlay with current key, frame count, latest event, runtime status,
and strace counters. The launcher option is:

```sh
./LOLG_HD.sh sidecar-live-strace-wide-all-player --player-hud
./LOLG_HD.sh sidecar-live-strace-wide-all-hud
```

Current no-game alias smoke:

```text
./LOLG_HD.sh sidecar-hd --no-game --no-web --smoke --smoke-timeout 15 -> pass
key=HERB.MIX:98e2ff4f
status=decoded
size=1920x1080
frames=6/6
```

Current audit after that smoke:

```text
./LOLG_HD.sh sidecar-audit --events 8 -> pass
unique_decoded_vqa=1/1955
decoded_archives=1/66
failed_events=0
decoded_keys=HERB.MIX:98e2ff4f
```

Current status probe after the in-engine failure isolation:

```text
./LOLG_HD.sh sidecar-live-strace-wide-all-hud --no-game --dry-run -> pass
./LOLG_HD.sh sidecar-hd --no-game --dry-run -> pass
./LOLG_HD.sh sidecar-status --events 2 -> pass, player URL includes &hud=1
current_key=HERB.MIX:98e2ff4f
current_frames=6/6
current_size=1920x1080
player=http://127.0.0.1:8765/?mode=player&hud=1
```

The web server also answers `HEAD` checks for `/`, `/api/status`, `/api/frames`,
`/api/events`, `/api/result`, `/api/event`, and `/frame`. This keeps simple
HTTP health checks such as `curl -I` from returning `501`.

## Decode continuity

Runtime trace requests now set `preserve_decode_dir=true`. The sidecar request
tool therefore keeps existing decoded frames while extending a partial decode to
a complete decode, unless `--force` is used. This avoids blanking the player
when a first small frame batch is later expanded to all frames.

The request tool also writes `result.json` at decode start with
`status=decoding`, the target key, and the `decode_dir`. The web player can
therefore switch to the new VQA immediately and count PNG frames as they appear,
instead of waiting for the final `decoded` result.

Live sessions now clear the previous `result.json` by default when they reset
the trace and event log. This avoids showing an old VQA at player startup before
the game has read a new one. Use `--keep-last-result` only when that old result
is intentionally wanted.

The preserve test used a temporary cache:

```text
HERB.MIX:98e2ff4f max_frames=1 -> 1 frame
HERB.MIX:98e2ff4f max_frames=0 -> 6 frames
decode_dir_preserved=true
```

## Important limit

This path does not inject the HD VQA frames back into the Lands of Lore II game
window. The stable Wine game still runs with the safevqa MIX exclusions, while
the sidecar detects VQA file reads through `strace` and displays the decoded HD
VQA in the external web player.

Useful launch commands:

```sh
./LOLG_HD.sh sidecar-live-strace-player
./LOLG_HD.sh sidecar-live-strace-all-player
```
