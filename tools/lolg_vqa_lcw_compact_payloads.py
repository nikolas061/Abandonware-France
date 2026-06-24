#!/usr/bin/env python3
"""Materialize LCW-compacted copies of generated WVQA replacements."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import struct
from pathlib import Path

import lolg_vqa_decode as vqa
from westwood_codecs import lcw_compress


DEFAULT_ENTRIES = Path("output/vqa_runtime_oversize_budget/entries.csv")
DEFAULT_OUTPUT = Path("output/vqa_lcw_compact_payloads")
DEFAULT_COMPACT_ROOT = Path("replacements_vqa_fullhd_lcw_compact")

SUMMARY_FIELDS = [
    "status",
    "entries_available",
    "entries_selected",
    "entries_written",
    "frames",
    "chunks_recompressed",
    "chunk_roundtrip_failures",
    "original_payload_bytes",
    "compact_payload_bytes",
    "saved_bytes",
    "saved_ratio",
    "compact_root",
    "issues",
    "next_step",
]

ENTRY_FIELDS = [
    "archive",
    "index",
    "file_id",
    "replacement_path",
    "compact_path",
    "frames",
    "chunks_recompressed",
    "chunk_roundtrip_failures",
    "original_payload_bytes",
    "compact_payload_bytes",
    "saved_bytes",
    "saved_ratio",
    "original_chunk_bytes",
    "compact_chunk_bytes",
    "chunk_saved_bytes",
    "compact_sha256",
    "issues",
]

CHUNK_FIELDS = [
    "archive",
    "index",
    "file_id",
    "frame",
    "chunk",
    "decoded_size",
    "original_size",
    "compact_size",
    "saved_bytes",
    "roundtrip_ok",
    "issues",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def int_value(row: dict[str, str], field: str) -> int:
    try:
        return int(row.get(field, "0") or 0)
    except ValueError:
        return 0


def ratio_text(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        return "0.000000"
    return f"{numerator / denominator:.6f}"


def be32(data: bytes | memoryview, offset: int) -> int:
    return struct.unpack_from(">I", data, offset)[0]


def be32_bytes(value: int) -> bytes:
    return struct.pack(">I", value)


def chunk(name: str, payload: bytes) -> bytes:
    data = name.encode("ascii") + be32_bytes(len(payload)) + payload
    if len(payload) & 1:
        data += b"\x00"
    return data


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def iter_chunk_views(data: bytes | memoryview, start: int, end: int):
    pos = start
    while pos + 8 <= end:
        chunk_id = bytes(data[pos : pos + 4]).decode("ascii", errors="replace")
        size = be32(data, pos + 4)
        payload_start = pos + 8
        payload_end = payload_start + size
        if payload_end > end:
            break
        yield chunk_id, bytes(data[payload_start:payload_end])
        pos = payload_end + (size & 1)


def expected_size_for_chunk(chunk_id: str, header: vqa.VqaHeader) -> int | None:
    if chunk_id in {"VPTZ", "VPT0"}:
        return header.block_count * 2
    if chunk_id in {"CBFZ", "CBF0"}:
        return header.max_codebook_entries * header.block_width * header.block_height
    return None


def compact_output_path(root: Path, row: dict[str, str]) -> Path:
    archive = row.get("archive", "")
    file_id = row.get("file_id", "").lower()
    return root / Path(archive).stem / f"{file_id}.vqa"


def select_rows(args: argparse.Namespace) -> tuple[int, list[dict[str, str]]]:
    rows = [
        row
        for row in read_csv(args.entries)
        if row.get("replacement_path") and Path(row.get("replacement_path", "")).is_file()
    ]
    if args.min_replacement_size:
        rows = [row for row in rows if int_value(row, "replacement_size") >= args.min_replacement_size]
    if args.max_replacement_size:
        rows = [row for row in rows if int_value(row, "replacement_size") <= args.max_replacement_size]
    rows.sort(key=lambda row: int_value(row, "replacement_size"), reverse=True)
    if args.archive:
        rows = [row for row in rows if row.get("archive") == args.archive]
    if args.index:
        rows = [row for row in rows if row.get("index") == args.index]
    if args.file_id:
        rows = [row for row in rows if row.get("file_id", "").lower() == args.file_id.lower()]
    total = len(rows)
    if args.entry_limit:
        rows = rows[: args.entry_limit]
    return total, rows


def compact_payload(
    row: dict[str, str],
    compact_root: Path,
    search_depth: int,
) -> tuple[dict[str, str], list[dict[str, str]]]:
    archive = row.get("archive", "")
    index = row.get("index", "")
    file_id = row.get("file_id", "").lower()
    replacement_path = Path(row.get("replacement_path", ""))
    output_path = compact_output_path(compact_root, row)
    issues: list[str] = []
    chunk_rows: list[dict[str, str]] = []
    frames = 0
    chunks_recompressed = 0
    roundtrip_failures = 0
    original_chunk_bytes = 0
    compact_chunk_bytes = 0
    compact_data = b""
    original_data = b""

    try:
        original_data = replacement_path.read_bytes()
        if len(original_data) < 12 or original_data[:4] != b"FORM" or original_data[8:12] != b"WVQA":
            raise ValueError("not_a_wvqa_payload")
        header, _chunks = vqa.parse_vqa(original_data)
        view = memoryview(original_data)
        top_end = min(len(original_data), 8 + be32(view, 4))
        top_chunks: list[bytes] = []
        for chunk_id, payload in iter_chunk_views(view, 12, top_end):
            if chunk_id != "VQFR":
                top_chunks.append(chunk(chunk_id, payload))
                continue
            frame_index = frames
            frames += 1
            subchunks: list[bytes] = []
            for sub_id, sub_payload in iter_chunk_views(payload, 0, len(payload)):
                if sub_id not in {"CBFZ", "VPTZ"}:
                    subchunks.append(chunk(sub_id, sub_payload))
                    continue
                expected_size = expected_size_for_chunk(sub_id, header)
                row_issues: list[str] = []
                decoded = b""
                compact_sub = sub_payload
                roundtrip_ok = "0"
                try:
                    decoded = vqa.decode_lcw(
                        sub_payload,
                        expected_size=expected_size,
                        allow_signed_source=sub_id == "VPTZ",
                    )
                    compact_sub = lcw_compress(decoded, search_depth=search_depth)
                    if vqa.decode_lcw(
                        compact_sub,
                        expected_size=expected_size,
                        allow_signed_source=sub_id == "VPTZ",
                    ) != decoded:
                        row_issues.append("roundtrip_mismatch")
                    else:
                        roundtrip_ok = "1"
                    original_chunk_bytes += len(sub_payload)
                    compact_chunk_bytes += len(compact_sub)
                    chunks_recompressed += 1
                except Exception as exc:  # noqa: BLE001 - keep materializing with original chunk
                    detail = str(exc).replace("\n", " ").replace(";", ",")
                    row_issues.append(f"{type(exc).__name__}:{detail}")
                    roundtrip_failures += 1
                    compact_sub = sub_payload
                subchunks.append(chunk(sub_id, compact_sub))
                if row_issues:
                    issues.append(f"frame:{frame_index}:{sub_id}:{','.join(row_issues)}")
                chunk_rows.append(
                    {
                        "archive": archive,
                        "index": index,
                        "file_id": file_id,
                        "frame": str(frame_index),
                        "chunk": sub_id,
                        "decoded_size": str(len(decoded)),
                        "original_size": str(len(sub_payload)),
                        "compact_size": str(len(compact_sub)),
                        "saved_bytes": str(len(sub_payload) - len(compact_sub)),
                        "roundtrip_ok": roundtrip_ok,
                        "issues": ",".join(row_issues),
                    }
                )
            top_chunks.append(chunk("VQFR", b"".join(subchunks)))
        body = b"WVQA" + b"".join(top_chunks)
        compact_data = b"FORM" + be32_bytes(len(body)) + body
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(compact_data)
    except Exception as exc:  # noqa: BLE001 - report row as failed
        detail = str(exc).replace("\n", " ").replace(";", ",")
        issues.append(f"entry_failed:{type(exc).__name__}:{detail}")

    original_size = len(original_data) if original_data else int_value(row, "replacement_size")
    compact_size = len(compact_data)
    saved = original_size - compact_size if compact_size else 0
    entry_row = {
        "archive": archive,
        "index": index,
        "file_id": file_id,
        "replacement_path": str(replacement_path),
        "compact_path": str(output_path) if compact_data else "",
        "frames": str(frames),
        "chunks_recompressed": str(chunks_recompressed),
        "chunk_roundtrip_failures": str(roundtrip_failures),
        "original_payload_bytes": str(original_size),
        "compact_payload_bytes": str(compact_size),
        "saved_bytes": str(saved),
        "saved_ratio": ratio_text(saved, original_size),
        "original_chunk_bytes": str(original_chunk_bytes),
        "compact_chunk_bytes": str(compact_chunk_bytes),
        "chunk_saved_bytes": str(original_chunk_bytes - compact_chunk_bytes),
        "compact_sha256": sha256_bytes(compact_data) if compact_data else "",
        "issues": ";".join(issues),
    }
    return entry_row, chunk_rows


def build_reports(args: argparse.Namespace) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    available, selected = select_rows(args)
    entry_rows: list[dict[str, str]] = []
    chunk_rows: list[dict[str, str]] = []
    for row in selected:
        entry_row, rows = compact_payload(row, args.compact_root, args.search_depth)
        entry_rows.append(entry_row)
        chunk_rows.extend(rows)

    issues = [
        f"{Path(row.get('archive', '')).name}:{row.get('index', '')}:{row.get('issues', '')}"
        for row in entry_rows
        if row.get("issues")
    ]
    entries_written = sum(1 for row in entry_rows if row.get("compact_path"))
    failures = sum(int_value(row, "chunk_roundtrip_failures") for row in entry_rows)
    original_bytes = sum(int_value(row, "original_payload_bytes") for row in entry_rows)
    compact_bytes = sum(int_value(row, "compact_payload_bytes") for row in entry_rows)
    saved = original_bytes - compact_bytes
    summary = {
        "status": "pass" if entry_rows and entries_written == len(entry_rows) and not issues and failures == 0 else "gap",
        "entries_available": str(available),
        "entries_selected": str(len(entry_rows)),
        "entries_written": str(entries_written),
        "frames": str(sum(int_value(row, "frames") for row in entry_rows)),
        "chunks_recompressed": str(sum(int_value(row, "chunks_recompressed") for row in entry_rows)),
        "chunk_roundtrip_failures": str(failures),
        "original_payload_bytes": str(original_bytes),
        "compact_payload_bytes": str(compact_bytes),
        "saved_bytes": str(saved),
        "saved_ratio": ratio_text(saved, original_bytes),
        "compact_root": str(args.compact_root),
        "issues": ";".join(issues),
        "next_step": "broaden compact materialization, then point the runtime pack builder at the compact root once all deferred payloads are covered",
    }
    return summary, entry_rows, chunk_rows


def render_table(rows: list[dict[str, str]], fields: list[str]) -> str:
    head = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = []
    for row in rows:
        body.append("<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def write_html(path: Path, summary: dict[str, str], entries: list[dict[str, str]], chunks: list[dict[str, str]]) -> None:
    payload = {"summary": summary, "entries": entries, "chunks_sample": chunks[:500]}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    path.write_text(
        f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>LOLG VQA LCW Compact Payloads</title>
<style>
:root {{ color-scheme: dark; --bg: #101316; --panel: #171d22; --line: #2f3942; --text: #edf3f6; --muted: #9caab3; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; min-height: 100vh; background: var(--bg); color: var(--text); font: 14px/1.45 system-ui, sans-serif; }}
.wrap {{ width: min(1600px, calc(100vw - 28px)); margin: 0 auto; }}
header {{ border-bottom: 1px solid var(--line); background: #12171b; padding: 18px 0 14px; }}
h1 {{ margin: 0; font-size: 21px; font-weight: 700; letter-spacing: 0; }}
main {{ padding: 16px 0 28px; display: grid; gap: 16px; }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 10px; }}
.stat {{ border: 1px solid var(--line); border-radius: 8px; background: var(--panel); padding: 10px; }}
.label {{ color: var(--muted); }}
.value {{ font-size: 24px; font-weight: 750; line-height: 1.05; margin-top: 4px; overflow-wrap: anywhere; }}
.panel {{ border: 1px solid var(--line); border-radius: 8px; background: var(--panel); padding: 12px; overflow-x: auto; }}
h2 {{ margin: 0 0 10px; font-size: 16px; }}
table {{ width: 100%; min-width: 980px; border-collapse: collapse; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
td {{ overflow-wrap: anywhere; }}
</style>
</head>
<body>
<header><div class="wrap"><h1>LOLG VQA LCW Compact Payloads</h1></div></header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Status</div><div class="value">{html.escape(summary['status'])}</div></div>
    <div class="stat"><div class="label">Entries</div><div class="value">{html.escape(summary['entries_written'])}</div></div>
    <div class="stat"><div class="label">Frames</div><div class="value">{html.escape(summary['frames'])}</div></div>
    <div class="stat"><div class="label">Saved ratio</div><div class="value">{html.escape(summary['saved_ratio'])}</div></div>
  </section>
  <section class="panel"><h2>Synthese</h2>{render_table([summary], SUMMARY_FIELDS)}</section>
  <section class="panel"><h2>Entrees</h2>{render_table(entries, ENTRY_FIELDS)}</section>
  <section class="panel"><h2>Chunks sample</h2>{render_table(chunks[:500], CHUNK_FIELDS)}</section>
</main>
<script type="application/json" id="vqa-lcw-compact-payloads">{html.escape(data_json)}</script>
</body>
</html>
""",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Materialize LCW-compacted WVQA replacement payloads.")
    parser.add_argument("--entries", type=Path, default=DEFAULT_ENTRIES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--compact-root", type=Path, default=DEFAULT_COMPACT_ROOT)
    parser.add_argument("--entry-limit", type=int, default=1, help="Maximum selected rows; use 0 for no limit.")
    parser.add_argument("--min-replacement-size", type=int, default=0)
    parser.add_argument("--max-replacement-size", type=int, default=0)
    parser.add_argument("--archive", default="")
    parser.add_argument("--index", default="")
    parser.add_argument("--file-id", default="")
    parser.add_argument("--search-depth", type=int, default=32)
    parser.add_argument("--fail-on-gaps", action="store_true")
    args = parser.parse_args()

    summary, entries, chunks = build_reports(args)
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDS, [summary])
    write_csv(args.output / "entries.csv", ENTRY_FIELDS, entries)
    write_csv(args.output / "chunks.csv", CHUNK_FIELDS, chunks)
    write_html(args.output / "index.html", summary, entries, chunks)

    print(
        "VQA LCW compact payloads: "
        f"{summary['status']} entries={summary['entries_written']}/{summary['entries_selected']} "
        f"frames={summary['frames']} saved={summary['saved_bytes']} "
        f"ratio={summary['saved_ratio']} output={args.output / 'index.html'}"
    )
    if args.fail_on_gaps and summary["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
