#!/usr/bin/env python3
"""Profile LLSE command records around marker pairs and cmd20 controls."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_large_body_control_grammar_probe import int_value, read_mix_entry, write_csv


DEFAULT_OUTPUT = Path("output/tex_large_llse_command_record_probe")
DEFAULT_SEGMENTS = Path("output/tex_large_rejected_decoder_profile/segments.csv")
DEFAULT_STRUCTURE_SUMMARY = Path("output/tex_large_llse_signature_structure_probe/summary.csv")
DEFAULT_MIX_ENTRY_INDEX = 2
TARGET_CONTROL_PATH = "llse_signature"
KNOWN_MARKER_PAIRS = {
    (0x27, 0x30),
    (0x28, 0x30),
    (0x29, 0x30),
    (0x2A, 0x30),
    (0x2B, 0x30),
    (0x2B, 0x31),
}
HIGH_ARG2_SIGNATURES = {0xE0, 0xFC, 0xFD, 0xFE, 0xFF}

SUMMARY_FIELDNAMES = [
    "scope",
    "segment_rows",
    "scan_bytes_total",
    "marker_occurrences",
    "marker_groups",
    "marker_span_rows",
    "median_marker_span",
    "max_marker_span",
    "cmd20_occurrences",
    "cmd20_tuple_groups",
    "cmd20_high_arg2",
    "cmd20_zero_signature",
    "cmd20_dense_spans",
    "low_control_groups",
    "op4_candidate_occurrences",
    "issue_rows",
    "record_verdict",
    "next_action",
]

MARKER_FIELDNAMES = [
    "rank",
    "segment_id",
    "marker_pair",
    "count",
    "ratio",
    "top_next4",
    "top_prev4",
    "sample_offsets",
]

SPAN_FIELDNAMES = [
    "rank",
    "segment_id",
    "start_offset",
    "end_offset",
    "length",
    "marker_pair",
    "next_marker_pair",
    "cmd20_count",
    "low_count",
    "low_ratio",
    "zero_ratio",
    "op4_candidate_count",
    "head16_hex",
    "tail16_hex",
    "top_bytes",
    "verdict",
]

CMD20_FIELDNAMES = [
    "rank",
    "segment_id",
    "arg_tuple",
    "count",
    "ratio",
    "arg1",
    "arg2",
    "arg3",
    "signed_arg2",
    "class",
    "top_prev2",
    "top_next4",
    "top_prev_marker_pair",
    "sample_offsets",
]

LOW_FIELDNAMES = [
    "rank",
    "segment_id",
    "byte_hex",
    "count",
    "ratio",
    "class",
    "top_prev",
    "top_next",
    "top_prev2",
    "top_next2",
    "sample_offsets",
]

DETAIL_FIELDNAMES = [
    "segment_id",
    "scan_start_offset",
    "scan_bytes",
    "first_marker_offset",
    "first_marker_pair",
    "last_marker_offset",
    "cmd20_count",
    "marker_count",
    "low_ratio",
    "zero_ratio",
    "op4_candidate_count",
    "issues",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_summary(path: Path) -> dict[str, str]:
    rows = read_csv(path)
    return rows[0] if rows else {}


def ratio(count: int, total: int) -> str:
    return f"{count / max(1, total):.6f}"


def signed_byte(value: int) -> int:
    return value - 256 if value >= 128 else value


def hex_byte(value: int | None) -> str:
    return "" if value is None else f"{value:02x}"


def bytes_hex(data: bytes) -> str:
    return data.hex()


def top_counter(counter: Counter[str], limit: int = 8) -> str:
    return "|".join(f"{key}:{count}" for key, count in counter.most_common(limit))


def op4_candidate(byte: int) -> bool:
    return 0x40 <= byte <= 0x68 and byte % 4 == 0


def marker_pair_at(data: bytes, offset: int) -> str:
    if offset + 1 >= len(data):
        return ""
    pair = (data[offset], data[offset + 1])
    if pair in KNOWN_MARKER_PAIRS:
        return f"{pair[0]:02x}{pair[1]:02x}"
    return ""


def marker_offsets(data: bytes) -> list[int]:
    output: list[int] = []
    for offset in range(max(0, len(data) - 1)):
        if marker_pair_at(data, offset):
            output.append(offset)
    return output


def cmd20_class(arg1: int | None, arg2: int | None, arg3: int | None) -> str:
    if (arg1, arg2, arg3) == (0, 0, 0):
        return "zero_signature"
    if arg1 is not None and arg2 in HIGH_ARG2_SIGNATURES and arg3 is not None:
        return "high_arg2_signature"
    if arg2 is not None and arg2 >= 0xC0:
        return "signed_dy_candidate"
    if arg1 is not None and arg1 < 0x40 and arg2 is not None and arg2 < 0x40:
        return "small_xy_candidate"
    return "generic_cmd20"


def low_byte_class(value: int) -> str:
    if value == 0:
        return "zero"
    if value == 0x20:
        return "cmd20"
    if 0x27 <= value <= 0x2B:
        return "marker_first"
    if value < 0x10:
        return "low_nibble"
    return "low_control"


def load_body(row: dict[str, str], payload_cache: dict[Path, bytes], mix_entry_index: int) -> tuple[bytes, list[str]]:
    issues: list[str] = []
    archive = Path(row.get("archive", ""))
    offset = int_value(row, "body_offset")
    size = int_value(row, "body_size")
    try:
        if archive not in payload_cache:
            payload_cache[archive] = read_mix_entry(archive, mix_entry_index)
        payload = payload_cache[archive]
        body = payload[offset : offset + size]
        if len(body) != size:
            issues.append("short_body_read")
        return body, issues
    except Exception as exc:
        return b"", [f"read_failed:{exc}"]


def marker_payload_start(body: bytes) -> int:
    if body.startswith(b"LLSE"):
        marker = body.find(b"\x27\x30", 4, 256)
        if marker >= 0:
            return marker
        return 4
    marker = body.find(b"\x27\x30", 0, 256)
    return marker if marker >= 0 else 0


def bounded_sample_offsets(offsets: list[int], limit: int = 10) -> str:
    return "|".join(str(offset) for offset in offsets[:limit])


def analyze_markers(segment_id: str, scan: bytes, scan_start: int) -> tuple[list[dict[str, str]], list[int]]:
    offsets = marker_offsets(scan)
    grouped: dict[str, list[int]] = defaultdict(list)
    next4: dict[str, Counter[str]] = defaultdict(Counter)
    prev4: dict[str, Counter[str]] = defaultdict(Counter)
    for offset in offsets:
        pair = marker_pair_at(scan, offset)
        grouped[pair].append(scan_start + offset)
        next4[pair][bytes_hex(scan[offset + 2 : offset + 6])] += 1
        prev4[pair][bytes_hex(scan[max(0, offset - 4) : offset])] += 1
    rows: list[dict[str, str]] = []
    total = len(offsets)
    for rank, (pair, pair_offsets) in enumerate(
        sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0])),
        1,
    ):
        rows.append(
            {
                "rank": str(rank),
                "segment_id": segment_id,
                "marker_pair": pair,
                "count": str(len(pair_offsets)),
                "ratio": ratio(len(pair_offsets), total),
                "top_next4": top_counter(next4[pair]),
                "top_prev4": top_counter(prev4[pair]),
                "sample_offsets": bounded_sample_offsets(pair_offsets),
            }
        )
    return rows, offsets


def span_verdict(length: int, cmd20_count: int, low_ratio_value: float) -> str:
    if length <= 8:
        return "tiny_marker_span"
    if cmd20_count >= 8:
        return "cmd20_dense_marker_span"
    if low_ratio_value >= 0.50:
        return "low_control_dense_marker_span"
    if length >= 8192:
        return "long_payload_marker_span"
    return "mixed_marker_span"


def analyze_spans(
    segment_id: str,
    scan: bytes,
    scan_start: int,
    offsets: list[int],
    limit: int,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for index, start in enumerate(offsets):
        end = offsets[index + 1] if index + 1 < len(offsets) else len(scan)
        chunk = scan[start:end]
        if not chunk:
            continue
        low = sum(1 for byte in chunk if byte < 0x30)
        zero = chunk.count(0)
        cmd20 = chunk.count(0x20)
        op4 = sum(1 for byte in chunk if op4_candidate(byte))
        low_value = low / max(1, len(chunk))
        rows.append(
            {
                "rank": "",
                "segment_id": segment_id,
                "start_offset": str(scan_start + start),
                "end_offset": str(scan_start + end),
                "length": str(len(chunk)),
                "marker_pair": marker_pair_at(scan, start),
                "next_marker_pair": marker_pair_at(scan, offsets[index + 1]) if index + 1 < len(offsets) else "",
                "cmd20_count": str(cmd20),
                "low_count": str(low),
                "low_ratio": f"{low_value:.6f}",
                "zero_ratio": ratio(zero, len(chunk)),
                "op4_candidate_count": str(op4),
                "head16_hex": chunk[:16].hex(),
                "tail16_hex": chunk[-16:].hex(),
                "top_bytes": top_counter(Counter(f"{byte:02x}" for byte in chunk)),
                "verdict": span_verdict(len(chunk), cmd20, low_value),
            }
        )
    rows.sort(
        key=lambda row: (
            row["verdict"] != "cmd20_dense_marker_span",
            -int_value(row, "cmd20_count"),
            -int_value(row, "length"),
            int_value(row, "start_offset"),
        )
    )
    rows = rows[:limit]
    for rank, row in enumerate(rows, 1):
        row["rank"] = str(rank)
    return rows


def analyze_cmd20(segment_id: str, scan: bytes, scan_start: int, marker_scan_offsets: list[int], limit: int) -> list[dict[str, str]]:
    total = scan.count(0x20)
    groups: dict[tuple[int | None, int | None, int | None], list[int]] = defaultdict(list)
    prev2: dict[tuple[int | None, int | None, int | None], Counter[str]] = defaultdict(Counter)
    next4: dict[tuple[int | None, int | None, int | None], Counter[str]] = defaultdict(Counter)
    prev_marker: dict[tuple[int | None, int | None, int | None], Counter[str]] = defaultdict(Counter)
    marker_positions = sorted(marker_scan_offsets)
    marker_index = 0
    for offset, byte in enumerate(scan):
        if byte != 0x20:
            continue
        arg1 = scan[offset + 1] if offset + 1 < len(scan) else None
        arg2 = scan[offset + 2] if offset + 2 < len(scan) else None
        arg3 = scan[offset + 3] if offset + 3 < len(scan) else None
        key = (arg1, arg2, arg3)
        groups[key].append(scan_start + offset)
        prev2[key][bytes_hex(scan[max(0, offset - 2) : offset])] += 1
        next4[key][bytes_hex(scan[offset + 1 : offset + 5])] += 1
        while marker_index + 1 < len(marker_positions) and marker_positions[marker_index + 1] < offset:
            marker_index += 1
        if marker_positions and marker_positions[marker_index] < offset:
            prev_marker[key][marker_pair_at(scan, marker_positions[marker_index])] += 1
    rows: list[dict[str, str]] = []
    sorted_groups = sorted(groups.items(), key=lambda item: (-len(item[1]), tuple(-1 if value is None else value for value in item[0])))
    for rank, (key, offsets) in enumerate(sorted_groups[:limit], 1):
        arg1, arg2, arg3 = key
        rows.append(
            {
                "rank": str(rank),
                "segment_id": segment_id,
                "arg_tuple": f"{hex_byte(arg1)} {hex_byte(arg2)} {hex_byte(arg3)}".strip(),
                "count": str(len(offsets)),
                "ratio": ratio(len(offsets), total),
                "arg1": hex_byte(arg1),
                "arg2": hex_byte(arg2),
                "arg3": hex_byte(arg3),
                "signed_arg2": str(signed_byte(arg2)) if arg2 is not None else "",
                "class": cmd20_class(arg1, arg2, arg3),
                "top_prev2": top_counter(prev2[key]),
                "top_next4": top_counter(next4[key]),
                "top_prev_marker_pair": top_counter(prev_marker[key]),
                "sample_offsets": bounded_sample_offsets(offsets),
            }
        )
    return rows


def analyze_low_controls(segment_id: str, scan: bytes, scan_start: int, limit: int) -> list[dict[str, str]]:
    total = sum(1 for byte in scan if byte < 0x30)
    offsets_by_byte: dict[int, list[int]] = defaultdict(list)
    prev1: dict[int, Counter[str]] = defaultdict(Counter)
    next1: dict[int, Counter[str]] = defaultdict(Counter)
    prev2: dict[int, Counter[str]] = defaultdict(Counter)
    next2: dict[int, Counter[str]] = defaultdict(Counter)
    for offset, byte in enumerate(scan):
        if byte >= 0x30:
            continue
        offsets_by_byte[byte].append(scan_start + offset)
        prev1[byte][bytes_hex(scan[max(0, offset - 1) : offset])] += 1
        next1[byte][bytes_hex(scan[offset + 1 : offset + 2])] += 1
        prev2[byte][bytes_hex(scan[max(0, offset - 2) : offset])] += 1
        next2[byte][bytes_hex(scan[offset + 1 : offset + 3])] += 1
    rows: list[dict[str, str]] = []
    for rank, (byte, offsets) in enumerate(
        sorted(offsets_by_byte.items(), key=lambda item: (-len(item[1]), item[0]))[:limit],
        1,
    ):
        rows.append(
            {
                "rank": str(rank),
                "segment_id": segment_id,
                "byte_hex": f"{byte:02x}",
                "count": str(len(offsets)),
                "ratio": ratio(len(offsets), total),
                "class": low_byte_class(byte),
                "top_prev": top_counter(prev1[byte]),
                "top_next": top_counter(next1[byte]),
                "top_prev2": top_counter(prev2[byte]),
                "top_next2": top_counter(next2[byte]),
                "sample_offsets": bounded_sample_offsets(offsets),
            }
        )
    return rows


def build_detail_row(
    source: dict[str, str],
    scan_start: int,
    scan: bytes,
    marker_scan_offsets: list[int],
    issues: list[str],
) -> dict[str, str]:
    marker_count = len(marker_scan_offsets)
    first_marker = marker_scan_offsets[0] if marker_scan_offsets else None
    last_marker = marker_scan_offsets[-1] if marker_scan_offsets else None
    low_count = sum(1 for byte in scan if byte < 0x30)
    zero_count = scan.count(0)
    return {
        "segment_id": source.get("segment_id", ""),
        "scan_start_offset": str(scan_start),
        "scan_bytes": str(len(scan)),
        "first_marker_offset": str(scan_start + first_marker) if first_marker is not None else "",
        "first_marker_pair": marker_pair_at(scan, first_marker) if first_marker is not None else "",
        "last_marker_offset": str(scan_start + last_marker) if last_marker is not None else "",
        "cmd20_count": str(scan.count(0x20)),
        "marker_count": str(marker_count),
        "low_ratio": ratio(low_count, len(scan)),
        "zero_ratio": ratio(zero_count, len(scan)),
        "op4_candidate_count": str(sum(1 for byte in scan if op4_candidate(byte))),
        "issues": ";".join(sorted(set(issues))),
    }


def summarize(
    structure_summary: dict[str, str],
    detail_rows: list[dict[str, str]],
    marker_rows: list[dict[str, str]],
    span_rows: list[dict[str, str]],
    cmd20_rows: list[dict[str, str]],
    low_rows: list[dict[str, str]],
) -> dict[str, str]:
    issue_rows = sum(1 for row in detail_rows if row.get("issues"))
    scan_bytes = sum(int_value(row, "scan_bytes") for row in detail_rows)
    marker_occurrences = sum(int_value(row, "marker_count") for row in detail_rows)
    cmd20_occurrences = sum(int_value(row, "cmd20_count") for row in detail_rows)
    op4_occurrences = sum(int_value(row, "op4_candidate_count") for row in detail_rows)
    high_arg2 = sum(int_value(row, "count") for row in cmd20_rows if row.get("class") == "high_arg2_signature")
    zero_sig = sum(int_value(row, "count") for row in cmd20_rows if row.get("class") == "zero_signature")
    dense_spans = sum(1 for row in span_rows if row.get("verdict") == "cmd20_dense_marker_span")
    span_lengths = [int_value(row, "length") for row in span_rows if int_value(row, "length") > 0]
    median_span = int(statistics.median(span_lengths)) if span_lengths else 0
    max_span = max(span_lengths) if span_lengths else 0
    top_cmd20 = cmd20_rows[0] if cmd20_rows else {}
    top_marker = marker_rows[0] if marker_rows else {}
    if issue_rows:
        verdict = "llse_command_record_probe_issues"
        next_action = "fix LLSE command record probe inputs"
    elif dense_spans > 0 and top_cmd20.get("class") in {"high_arg2_signature", "signed_dy_candidate"}:
        verdict = "llse_cmd20_record_grammar_candidate"
        next_action = (
            "test LLSE cmd20 record grammar using "
            f"top tuple {top_cmd20.get('arg_tuple', '')} and marker {top_marker.get('marker_pair', '')}"
        )
    elif marker_occurrences and cmd20_occurrences:
        verdict = "llse_marker_cmd20_profile_ready"
        next_action = (
            "derive LLSE cmd20/control grammar from marker-span profiles; "
            f"top tuple {top_cmd20.get('arg_tuple', '') or 'none'}"
        )
    elif structure_summary.get("structure_verdict"):
        verdict = "llse_command_profile_sparse"
        next_action = structure_summary.get("next_action", "review LLSE command profile")
    else:
        verdict = "llse_command_profile_empty"
        next_action = "review LLSE command record probe inputs"
    return {
        "scope": "total",
        "segment_rows": str(len(detail_rows)),
        "scan_bytes_total": str(scan_bytes),
        "marker_occurrences": str(marker_occurrences),
        "marker_groups": str(len(marker_rows)),
        "marker_span_rows": str(len(span_rows)),
        "median_marker_span": str(median_span),
        "max_marker_span": str(max_span),
        "cmd20_occurrences": str(cmd20_occurrences),
        "cmd20_tuple_groups": str(len(cmd20_rows)),
        "cmd20_high_arg2": str(high_arg2),
        "cmd20_zero_signature": str(zero_sig),
        "cmd20_dense_spans": str(dense_spans),
        "low_control_groups": str(len(low_rows)),
        "op4_candidate_occurrences": str(op4_occurrences),
        "issue_rows": str(issue_rows),
        "record_verdict": verdict,
        "next_action": next_action,
    }


def render_table(rows: list[dict[str, str]], fieldnames: list[str]) -> str:
    if not rows:
        return "<p class=\"muted\">No rows.</p>"
    head = "".join(f"<th>{html.escape(field)}</th>" for field in fieldnames)
    body = "\n".join(
        "<tr>"
        + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fieldnames)
        + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    try:
        return os.path.relpath(Path(path_text), base_dir)
    except ValueError:
        return str(path_text)


def build_html(
    summary: dict[str, str],
    details: list[dict[str, str]],
    markers: list[dict[str, str]],
    spans: list[dict[str, str]],
    cmd20: list[dict[str, str]],
    lows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "details": details,
        "markers": markers,
        "spans": spans,
        "cmd20": cmd20,
        "low_controls": lows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f"<a href=\"{html.escape(relative_href(path, output_dir))}\">{html.escape(label)}</a>"
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("details.csv", output_dir / "details.csv"),
            ("markers.csv", output_dir / "markers.csv"),
            ("spans.csv", output_dir / "spans.csv"),
            ("cmd20.csv", output_dir / "cmd20.csv"),
            ("low_controls.csv", output_dir / "low_controls.csv"),
        )
    )
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
:root {{ color-scheme: dark; --bg: #101317; --panel: #181d23; --text: #e8edf2; --muted: #98a4b3; --accent: #74b8ff; --ok: #6fd08c; --warn: #f0b35a; }}
body {{ margin: 0; font-family: system-ui, sans-serif; background: var(--bg); color: var(--text); }}
header, main {{ max-width: 1500px; margin: 0 auto; padding: 24px; }}
h1 {{ margin: 0 0 8px; font-size: 26px; }}
h2 {{ margin: 0 0 12px; font-size: 18px; }}
.muted {{ color: var(--muted); }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin: 20px 0; }}
.stat, .panel {{ background: var(--panel); border: 1px solid #29313b; border-radius: 8px; padding: 14px; }}
.label {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }}
.value {{ font-size: 24px; font-weight: 700; }}
.ok {{ color: var(--ok); }}
.warn {{ color: var(--warn); }}
a {{ color: var(--accent); text-decoration: none; margin-right: 10px; }}
table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
th, td {{ border-bottom: 1px solid #29313b; padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); position: sticky; top: 0; background: var(--panel); }}
td {{ max-width: 560px; overflow-wrap: anywhere; }}
section {{ margin-bottom: 20px; }}
</style>
</head>
<body>
<header>
  <h1>{html.escape(title)}</h1>
  <div class="muted">Command-record profile for LLSE marker pairs, cmd20 tuples, and low controls.</div>
  <p>{links}</p>
</header>
<main>
  <section class="grid">
    <div class="stat"><div class="label">Markers</div><div class="value">{html.escape(summary['marker_occurrences'])}</div></div>
    <div class="stat"><div class="label">cmd20</div><div class="value warn">{html.escape(summary['cmd20_occurrences'])}</div></div>
    <div class="stat"><div class="label">Dense Spans</div><div class="value">{html.escape(summary['cmd20_dense_spans'])}</div></div>
    <div class="stat"><div class="label">Issues</div><div class="value ok">{html.escape(summary['issue_rows'])}</div></div>
  </section>
  <section class="panel"><h2>Summary</h2>{render_table([summary], SUMMARY_FIELDNAMES)}</section>
  <section class="panel"><h2>Details</h2>{render_table(details, DETAIL_FIELDNAMES)}</section>
  <section class="panel"><h2>Markers</h2>{render_table(markers, MARKER_FIELDNAMES)}</section>
  <section class="panel"><h2>Marker Spans</h2>{render_table(spans, SPAN_FIELDNAMES)}</section>
  <section class="panel"><h2>cmd20 Tuples</h2>{render_table(cmd20, CMD20_FIELDNAMES)}</section>
  <section class="panel"><h2>Low Controls</h2>{render_table(lows, LOW_FIELDNAMES)}</section>
</main>
<script type="application/json" id="llse-command-record-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> tuple[dict[str, str], list[dict[str, str]]]:
    args.output.mkdir(parents=True, exist_ok=True)
    structure_summary = read_summary(args.structure_summary)
    segments = [row for row in read_csv(args.segments) if row.get("control_path") == TARGET_CONTROL_PATH]
    payload_cache: dict[Path, bytes] = {}
    details: list[dict[str, str]] = []
    marker_rows: list[dict[str, str]] = []
    span_rows: list[dict[str, str]] = []
    cmd20_rows: list[dict[str, str]] = []
    low_rows: list[dict[str, str]] = []
    for source in segments:
        body, issues = load_body(source, payload_cache, args.mix_entry_index)
        if not body:
            issues.append("empty_body")
        scan_start = marker_payload_start(body)
        scan = body[scan_start : scan_start + args.scan_bytes]
        segment_id = source.get("segment_id", "")
        markers, marker_scan_offsets = analyze_markers(segment_id, scan, scan_start)
        marker_rows.extend(markers)
        span_rows.extend(analyze_spans(segment_id, scan, scan_start, marker_scan_offsets, args.span_limit))
        cmd20_rows.extend(analyze_cmd20(segment_id, scan, scan_start, marker_scan_offsets, args.cmd20_limit))
        low_rows.extend(analyze_low_controls(segment_id, scan, scan_start, args.low_limit))
        details.append(build_detail_row(source, scan_start, scan, marker_scan_offsets, issues))
    summary = summarize(structure_summary, details, marker_rows, span_rows, cmd20_rows, low_rows)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "details.csv", DETAIL_FIELDNAMES, details)
    write_csv(args.output / "markers.csv", MARKER_FIELDNAMES, marker_rows)
    write_csv(args.output / "spans.csv", SPAN_FIELDNAMES, span_rows)
    write_csv(args.output / "cmd20.csv", CMD20_FIELDNAMES, cmd20_rows)
    write_csv(args.output / "low_controls.csv", LOW_FIELDNAMES, low_rows)
    (args.output / "index.html").write_text(
        build_html(summary, details, marker_rows, span_rows, cmd20_rows, low_rows, args.output, args.title),
        encoding="utf-8",
    )
    return summary, cmd20_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile LLSE command records around markers and cmd20 controls.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--segments", type=Path, default=DEFAULT_SEGMENTS)
    parser.add_argument("--structure-summary", type=Path, default=DEFAULT_STRUCTURE_SUMMARY)
    parser.add_argument("--mix-entry-index", type=int, default=DEFAULT_MIX_ENTRY_INDEX)
    parser.add_argument("--scan-bytes", type=int, default=4 * 1024 * 1024)
    parser.add_argument("--span-limit", type=int, default=96)
    parser.add_argument("--cmd20-limit", type=int, default=96)
    parser.add_argument("--low-limit", type=int, default=48)
    parser.add_argument("--title", default="Lands of Lore II .tex LLSE Command Record Probe")
    args = parser.parse_args()

    summary, _rows = write_report(args)
    print(f"Segments: {summary['segment_rows']}")
    print(f"Markers: {summary['marker_occurrences']}")
    print(f"cmd20: {summary['cmd20_occurrences']}")
    print(f"cmd20 tuple groups: {summary['cmd20_tuple_groups']}")
    print(f"Dense spans: {summary['cmd20_dense_spans']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"Record verdict: {summary['record_verdict']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
