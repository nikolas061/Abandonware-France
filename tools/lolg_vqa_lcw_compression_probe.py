#!/usr/bin/env python3
"""Probe LCW compression gains for oversized generated WVQA replacements."""

from __future__ import annotations

import argparse
import csv
import html
import json
import struct
from pathlib import Path

import lolg_vqa_decode as vqa
from westwood_codecs import lcw_compress


DEFAULT_ENTRIES = Path("output/vqa_runtime_oversize_budget/entries.csv")
DEFAULT_OUTPUT = Path("output/vqa_lcw_compression_probe")

SUMMARY_FIELDS = [
    "status",
    "mode",
    "entries_available",
    "entries_sampled",
    "frame_limit",
    "frames_sampled",
    "replacement_bytes",
    "sample_original_chunk_bytes",
    "sample_compressed_chunk_bytes",
    "sample_saved_bytes",
    "sample_saved_ratio",
    "sample_payload_projected_bytes",
    "issues",
    "next_step",
]

ENTRY_FIELDS = [
    "archive",
    "index",
    "file_id",
    "replacement_path",
    "replacement_size",
    "source_size",
    "frames_total",
    "frames_sampled",
    "coverage",
    "sample_original_chunk_bytes",
    "sample_compressed_chunk_bytes",
    "sample_saved_bytes",
    "sample_saved_ratio",
    "sample_payload_projected_bytes",
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
    "compressed_size",
    "saved_bytes",
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


def chunk_total(size: int) -> int:
    return 8 + size + (size & 1)


def iter_chunk_views(data: bytes | memoryview, start: int, end: int):
    pos = start
    while pos + 8 <= end:
        chunk_id = bytes(data[pos : pos + 4]).decode("ascii", errors="replace")
        size = be32(data, pos + 4)
        payload_start = pos + 8
        payload_end = payload_start + size
        if payload_end > end:
            break
        yield pos, chunk_id, size, data[payload_start:payload_end]
        pos = payload_end + (size & 1)


def parse_header(data: bytes) -> tuple[vqa.VqaHeader, list[tuple[int, str, int, memoryview]]]:
    if len(data) < 12 or data[:4] != b"FORM" or data[8:12] != b"WVQA":
        raise ValueError("not_a_wvqa_payload")
    view = memoryview(data)
    top_end = min(len(data), 8 + be32(view, 4))
    chunks = list(iter_chunk_views(view, 12, top_end))
    header_payload = next((payload for _offset, chunk_id, _size, payload in chunks if chunk_id == "VQHD"), None)
    if header_payload is None:
        raise ValueError("missing_vqhd")
    return vqa.parse_vqhd(bytes(header_payload)), chunks


def expected_size_for_chunk(chunk_id: str, header: vqa.VqaHeader) -> int | None:
    if chunk_id in {"VPTZ", "VPT0"}:
        return header.block_count * 2
    if chunk_id in {"CBFZ", "CBF0"}:
        return header.max_codebook_entries * header.block_width * header.block_height
    return None


def probe_entry(
    row: dict[str, str],
    frame_limit: int,
    search_depth: int,
) -> tuple[dict[str, str], list[dict[str, str]]]:
    archive = row.get("archive", "")
    index = row.get("index", "")
    file_id = row.get("file_id", "")
    replacement_path = Path(row.get("replacement_path", ""))
    issues: list[str] = []
    chunk_rows: list[dict[str, str]] = []
    frames_total = 0
    frames_sampled = 0
    original_chunks = 0
    compressed_chunks = 0
    payload_projected_delta = 0
    replacement_size = int_value(row, "replacement_size")

    try:
        payload = replacement_path.read_bytes()
        replacement_size = len(payload)
        header, chunks = parse_header(payload)
        for _offset, chunk_id, size, chunk_payload in chunks:
            if chunk_id != "VQFR":
                continue
            frames_total += 1
            if frame_limit and frames_sampled >= frame_limit:
                continue
            old_vqfr_total = chunk_total(size)
            new_inner_size = size
            frame_issues: list[str] = []
            for _sub_offset, sub_id, sub_size, sub_payload in iter_chunk_views(chunk_payload, 0, size):
                if sub_id not in {"CBFZ", "VPTZ"}:
                    continue
                expected_size = expected_size_for_chunk(sub_id, header)
                try:
                    decoded = vqa.decode_lcw(
                        sub_payload,
                        expected_size=expected_size,
                        allow_signed_source=sub_id == "VPTZ",
                    )
                    compressed = lcw_compress(decoded, search_depth=search_depth)
                    original_chunks += sub_size
                    compressed_chunks += len(compressed)
                    new_inner_size += chunk_total(len(compressed)) - chunk_total(sub_size)
                    chunk_rows.append(
                        {
                            "archive": archive,
                            "index": index,
                            "file_id": file_id,
                            "frame": str(frames_total - 1),
                            "chunk": sub_id,
                            "decoded_size": str(len(decoded)),
                            "original_size": str(sub_size),
                            "compressed_size": str(len(compressed)),
                            "saved_bytes": str(sub_size - len(compressed)),
                            "issues": "",
                        }
                    )
                except Exception as exc:  # noqa: BLE001 - report and continue other frames
                    detail = str(exc).replace("\n", " ").replace(";", ",")
                    frame_issues.append(f"{sub_id}:{type(exc).__name__}:{detail}")
            payload_projected_delta += chunk_total(new_inner_size) - old_vqfr_total
            frames_sampled += 1
            issues.extend(frame_issues)
    except Exception as exc:  # noqa: BLE001 - one row should not block the report
        detail = str(exc).replace("\n", " ").replace(";", ",")
        issues.append(f"entry_failed:{type(exc).__name__}:{detail}")

    saved = original_chunks - compressed_chunks
    coverage = "full" if frames_total and frames_sampled == frames_total else "sample"
    entry_row = {
        "archive": archive,
        "index": index,
        "file_id": file_id,
        "replacement_path": str(replacement_path),
        "replacement_size": str(replacement_size),
        "source_size": row.get("source_size", ""),
        "frames_total": str(frames_total),
        "frames_sampled": str(frames_sampled),
        "coverage": coverage,
        "sample_original_chunk_bytes": str(original_chunks),
        "sample_compressed_chunk_bytes": str(compressed_chunks),
        "sample_saved_bytes": str(saved),
        "sample_saved_ratio": ratio_text(saved, original_chunks),
        "sample_payload_projected_bytes": str(replacement_size + payload_projected_delta),
        "issues": ";".join(issues),
    }
    return entry_row, chunk_rows


def build_reports(args: argparse.Namespace) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    source_rows = read_csv(args.entries)
    candidates = sorted(
        (row for row in source_rows if Path(row.get("replacement_path", "")).is_file()),
        key=lambda item: int_value(item, "replacement_size"),
        reverse=True,
    )
    selected = candidates[: args.entry_limit] if args.entry_limit else candidates

    entry_rows: list[dict[str, str]] = []
    chunk_rows: list[dict[str, str]] = []
    for row in selected:
        entry_row, rows = probe_entry(row, args.frame_limit, args.search_depth)
        entry_rows.append(entry_row)
        chunk_rows.extend(rows)

    issues: list[str] = []
    issues.extend(
        f"{Path(row.get('archive', '')).name}:{row.get('index', '')}:{row.get('issues', '')}"
        for row in entry_rows
        if row.get("issues")
    )
    replacement_bytes = sum(int_value(row, "replacement_size") for row in entry_rows)
    original_chunks = sum(int_value(row, "sample_original_chunk_bytes") for row in entry_rows)
    compressed_chunks = sum(int_value(row, "sample_compressed_chunk_bytes") for row in entry_rows)
    saved = original_chunks - compressed_chunks
    frames_sampled = sum(int_value(row, "frames_sampled") for row in entry_rows)
    full_coverage = entry_rows and all(row.get("coverage") == "full" for row in entry_rows)
    summary = {
        "status": "pass" if entry_rows and not issues else "gap",
        "mode": "full" if full_coverage else "sample",
        "entries_available": str(len(candidates)),
        "entries_sampled": str(len(entry_rows)),
        "frame_limit": str(args.frame_limit),
        "frames_sampled": str(frames_sampled),
        "replacement_bytes": str(replacement_bytes),
        "sample_original_chunk_bytes": str(original_chunks),
        "sample_compressed_chunk_bytes": str(compressed_chunks),
        "sample_saved_bytes": str(saved),
        "sample_saved_ratio": ratio_text(saved, original_chunks),
        "sample_payload_projected_bytes": str(sum(int_value(row, "sample_payload_projected_bytes") for row in entry_rows)),
        "issues": ";".join(issues),
        "next_step": "run with a wider entry/frame limit; if full coverage still saves enough bytes, add this LCW mode to the replacement writer",
    }
    return summary, entry_rows, chunk_rows


def render_table(rows: list[dict[str, str]], fields: list[str]) -> str:
    head = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = []
    for row in rows:
        body.append("<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def write_html(
    path: Path,
    summary: dict[str, str],
    entries: list[dict[str, str]],
    chunks: list[dict[str, str]],
) -> None:
    payload = {"summary": summary, "entries": entries, "chunks_sample": chunks[:500]}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    path.write_text(
        f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>LOLG VQA LCW Compression Probe</title>
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
<header><div class="wrap"><h1>LOLG VQA LCW Compression Probe</h1></div></header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Status</div><div class="value">{html.escape(summary['status'])}</div></div>
    <div class="stat"><div class="label">Mode</div><div class="value">{html.escape(summary['mode'])}</div></div>
    <div class="stat"><div class="label">Frames</div><div class="value">{html.escape(summary['frames_sampled'])}</div></div>
    <div class="stat"><div class="label">Saved ratio</div><div class="value">{html.escape(summary['sample_saved_ratio'])}</div></div>
  </section>
  <section class="panel"><h2>Synthese</h2>{render_table([summary], SUMMARY_FIELDS)}</section>
  <section class="panel"><h2>Entrees</h2>{render_table(entries, ENTRY_FIELDS)}</section>
  <section class="panel"><h2>Chunks sample</h2>{render_table(chunks[:500], CHUNK_FIELDS)}</section>
</main>
<script type="application/json" id="vqa-lcw-compression-probe">{html.escape(data_json)}</script>
</body>
</html>
""",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe LCW compression savings for generated oversized WVQA payloads.")
    parser.add_argument("--entries", type=Path, default=DEFAULT_ENTRIES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--entry-limit", type=int, default=4, help="Number of largest deferred replacements to sample; 0 means all.")
    parser.add_argument("--frame-limit", type=int, default=32, help="Frames per entry to sample; 0 means all frames.")
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
        "VQA LCW compression probe: "
        f"{summary['status']} mode={summary['mode']} "
        f"entries={summary['entries_sampled']}/{summary['entries_available']} "
        f"frames={summary['frames_sampled']} "
        f"saved={summary['sample_saved_bytes']} "
        f"ratio={summary['sample_saved_ratio']} "
        f"output={args.output / 'index.html'}"
    )
    if args.fail_on_gaps and summary["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
