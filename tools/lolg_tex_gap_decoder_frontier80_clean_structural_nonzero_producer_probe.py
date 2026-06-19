#!/usr/bin/env python3
"""Probe run-local and segment-literal producers for structural Frontier80 nonzero runs."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter
from pathlib import Path

from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_frontier80_clean_structural_nonzero_producer_probe")
DEFAULT_RUNS = Path(
    "output/tex_gap_decoder_unresolved_run_probe_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_fixture_replay/runs.csv"
)
DEFAULT_MANIFEST = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_CLEAN_FIXTURES = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_fixture_replay/fixtures.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "target_runs",
    "target_bytes",
    "largest_run_bytes",
    "byte_rle_rows",
    "repeated_run_bytes",
    "repeated_run_ratio",
    "same_prev_transitions",
    "small_delta_le2_transitions",
    "small_delta_le2_ratio",
    "small_delta_segment_rows",
    "raw_literal_rows",
    "raw_literal_covered_bytes",
    "raw_literal_covered_ratio",
    "best_raw_literal_length",
    "best_raw_literal_segment_offset",
    "best_raw_window_exact_bytes",
    "best_raw_window_segment_offset",
    "best_raw_window_exact_ratio",
    "known_target_bytes",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

TARGET_FIELDNAMES = [
    "target_id",
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "span_index",
    "run_index",
    "start",
    "end",
    "length",
    "unique_values_hex",
    "top_byte_hex",
    "top_byte_count",
    "head_hex",
    "tail_hex",
    "byte_rle_rows",
    "repeated_run_bytes",
    "same_prev_transitions",
    "small_delta_le2_transitions",
    "small_delta_segment_rows",
    "raw_literal_rows",
    "raw_literal_covered_bytes",
    "best_raw_literal_length",
    "best_raw_window_exact_bytes",
    "segment_gap_bytes",
    "control_prefix_bytes",
    "fragment_bytes",
    "known_target_bytes",
    "verdict",
    "next_probe",
]

RLE_FIELDNAMES = [
    "target_id",
    "run_offset_start",
    "run_offset_end",
    "absolute_start",
    "absolute_end",
    "value_hex",
    "length",
    "value_class",
]

DELTA_SEGMENT_FIELDNAMES = [
    "target_id",
    "segment_index",
    "run_offset_start",
    "run_offset_end",
    "absolute_start",
    "absolute_end",
    "length",
    "max_abs_delta",
    "head_hex",
    "tail_hex",
]

RAW_LITERAL_FIELDNAMES = [
    "target_id",
    "target_offset_start",
    "target_offset_end",
    "absolute_start",
    "absolute_end",
    "length",
    "segment_offset",
    "segment_context_before_hex",
    "literal_hex",
    "segment_context_after_hex",
]

RAW_ALIGNMENT_FIELDNAMES = [
    "target_id",
    "segment_offset",
    "exact_bytes",
    "exact_ratio",
    "first_exact_offset",
    "last_exact_offset",
    "segment_head_hex",
    "target_head_hex",
    "segment_tail_hex",
    "target_tail_hex",
]

BAND_FIELDNAMES = [
    "target_id",
    "value_class",
    "bytes",
    "ratio",
    "values_hex",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def fixture_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", "")


def target_id(row: dict[str, str]) -> str:
    return (
        f"r{int_value(row, 'rank'):03d}_f{row.get('frontier_id', '')}_"
        f"s{row.get('span_index', '')}_run{row.get('run_index', '')}"
    )


def key_text(key: tuple[str, str, str]) -> str:
    return ":".join(key)


def read_bytes(path_text: str, issues: list[str], label: str, key: tuple[str, str, str]) -> bytes:
    if not path_text:
        issues.append(f"{key_text(key)}:missing_{label}_path")
        return b""
    try:
        return Path(path_text).read_bytes()
    except OSError as exc:
        issues.append(f"{key_text(key)}:read_{label}_failed:{exc}")
        return b""


def hex_byte(value: int | None) -> str:
    return "" if value is None else f"0x{value:02x}"


def signed_delta(left: int, right: int) -> int:
    value = (right - left) & 0xFF
    return value if value < 128 else value - 256


def value_class(value: int) -> str:
    if value < 0x40:
        return "dark_low"
    if 0x4F <= value <= 0x66:
        return "mid_payload"
    if 0x67 <= value <= 0x6F:
        return "high_plateau"
    if value >= 0x80:
        return "control_high"
    return "other"


def unique_hex(data: bytes) -> str:
    return " ".join(f"{value:02x}" for value in sorted(set(data)))


def ratio(value: int, total: int) -> str:
    return f"{value / total:.6f}" if total else "0.000000"


def select_largest_targets(run_rows: list[dict[str, str]], issues: list[str]) -> list[dict[str, str]]:
    nonzero = [row for row in run_rows if row.get("run_class") == "nonzero"]
    if not nonzero:
        issues.append("missing_nonzero_run_rows")
        return []
    largest = max(int_value(row, "length") for row in nonzero)
    return [
        {**row, "target_id": target_id(row)}
        for row in nonzero
        if int_value(row, "length") == largest
    ]


def load_target_payloads(
    targets: list[dict[str, str]],
    manifest_rows: list[dict[str, str]],
    clean_rows: list[dict[str, str]],
    issues: list[str],
) -> list[dict[str, object]]:
    manifest_by_key = {fixture_key(row): row for row in manifest_rows}
    clean_by_key = {fixture_key(row): row for row in clean_rows}
    payloads: list[dict[str, object]] = []
    for target in targets:
        key = fixture_key(target)
        manifest = manifest_by_key.get(key)
        clean = clean_by_key.get(key)
        if not manifest:
            issues.append(f"{target.get('target_id', '')}:missing_manifest_row")
            continue
        if not clean:
            issues.append(f"{target.get('target_id', '')}:missing_clean_fixture_row")
            clean = {}
        expected = read_bytes(manifest.get("expected_gap_path", ""), issues, "expected_gap", key)
        segment = read_bytes(manifest.get("segment_gap_path", ""), issues, "segment_gap", key)
        control = read_bytes(manifest.get("control_prefix_path", ""), issues, "control_prefix", key)
        fragment = read_bytes(manifest.get("fragment_path", ""), issues, "fragment", key)
        known_mask = read_bytes(clean.get("known_mask_path", ""), issues, "known_mask", key) if clean else b""
        start = int_value(target, "start")
        end = int_value(target, "end")
        data = expected[start:end]
        if len(data) != int_value(target, "length"):
            issues.append(f"{target.get('target_id', '')}:target_window_out_of_bounds")
        payloads.append(
            {
                "target": target,
                "manifest": manifest,
                "clean": clean,
                "expected": expected,
                "segment": segment,
                "control": control,
                "fragment": fragment,
                "known_mask": known_mask,
                "data": data,
            }
        )
    return payloads


def build_rle_rows(payload: dict[str, object]) -> list[dict[str, str]]:
    target = payload["target"]
    data = payload["data"]
    if not isinstance(target, dict) or not isinstance(data, bytes):
        return []
    rows: list[dict[str, str]] = []
    start_index = 0
    absolute_start = int_value(target, "start")
    for index in range(1, len(data) + 1):
        if index == len(data) or data[index] != data[start_index]:
            length = index - start_index
            if length >= 2:
                value = data[start_index]
                rows.append(
                    {
                        "target_id": target.get("target_id", ""),
                        "run_offset_start": str(start_index),
                        "run_offset_end": str(index),
                        "absolute_start": str(absolute_start + start_index),
                        "absolute_end": str(absolute_start + index),
                        "value_hex": f"0x{value:02x}",
                        "length": str(length),
                        "value_class": value_class(value),
                    }
                )
            start_index = index
    return rows


def build_delta_segment_rows(payload: dict[str, object], *, max_delta: int = 2) -> list[dict[str, str]]:
    target = payload["target"]
    data = payload["data"]
    if not isinstance(target, dict) or not isinstance(data, bytes):
        return []
    rows: list[dict[str, str]] = []
    if len(data) < 2:
        return rows
    absolute_start = int_value(target, "start")
    segment_start = 0
    segment_index = 0
    for index in range(1, len(data)):
        if abs(signed_delta(data[index - 1], data[index])) > max_delta:
            if index - segment_start >= 3:
                chunk = data[segment_start:index]
                deltas = [abs(signed_delta(left, right)) for left, right in zip(chunk, chunk[1:])]
                rows.append(
                    {
                        "target_id": target.get("target_id", ""),
                        "segment_index": str(segment_index),
                        "run_offset_start": str(segment_start),
                        "run_offset_end": str(index),
                        "absolute_start": str(absolute_start + segment_start),
                        "absolute_end": str(absolute_start + index),
                        "length": str(len(chunk)),
                        "max_abs_delta": str(max(deltas) if deltas else 0),
                        "head_hex": chunk[:16].hex(),
                        "tail_hex": chunk[-16:].hex(),
                    }
                )
                segment_index += 1
            segment_start = index
    if len(data) - segment_start >= 3:
        chunk = data[segment_start:]
        deltas = [abs(signed_delta(left, right)) for left, right in zip(chunk, chunk[1:])]
        rows.append(
            {
                "target_id": target.get("target_id", ""),
                "segment_index": str(segment_index),
                "run_offset_start": str(segment_start),
                "run_offset_end": str(len(data)),
                "absolute_start": str(absolute_start + segment_start),
                "absolute_end": str(absolute_start + len(data)),
                "length": str(len(chunk)),
                "max_abs_delta": str(max(deltas) if deltas else 0),
                "head_hex": chunk[:16].hex(),
                "tail_hex": chunk[-16:].hex(),
            }
        )
    return rows


def raw_literal_candidates(data: bytes, segment: bytes, *, min_length: int) -> list[tuple[int, int, int]]:
    candidates: list[tuple[int, int, int]] = []
    for target_offset in range(len(data)):
        best_length = 0
        best_segment_offset = -1
        max_length = len(data) - target_offset
        for length in range(max_length, min_length - 1, -1):
            segment_offset = segment.find(data[target_offset : target_offset + length])
            if segment_offset >= 0:
                best_length = length
                best_segment_offset = segment_offset
                break
        if best_length >= min_length:
            candidates.append((target_offset, best_segment_offset, best_length))
    candidates.sort(key=lambda item: (-item[2], item[0], item[1]))
    selected: list[tuple[int, int, int]] = []
    covered: set[int] = set()
    for target_offset, segment_offset, length in candidates:
        span = set(range(target_offset, target_offset + length))
        if span & covered:
            continue
        selected.append((target_offset, segment_offset, length))
        covered.update(span)
    selected.sort()
    return selected


def build_raw_literal_rows(payload: dict[str, object], *, min_length: int) -> list[dict[str, str]]:
    target = payload["target"]
    data = payload["data"]
    segment = payload["segment"]
    if not isinstance(target, dict) or not isinstance(data, bytes) or not isinstance(segment, bytes):
        return []
    rows: list[dict[str, str]] = []
    absolute_start = int_value(target, "start")
    for target_offset, segment_offset, length in raw_literal_candidates(data, segment, min_length=min_length):
        literal = data[target_offset : target_offset + length]
        rows.append(
            {
                "target_id": target.get("target_id", ""),
                "target_offset_start": str(target_offset),
                "target_offset_end": str(target_offset + length),
                "absolute_start": str(absolute_start + target_offset),
                "absolute_end": str(absolute_start + target_offset + length),
                "length": str(length),
                "segment_offset": str(segment_offset),
                "segment_context_before_hex": segment[max(0, segment_offset - 8) : segment_offset].hex(),
                "literal_hex": literal.hex(),
                "segment_context_after_hex": segment[
                    segment_offset + length : min(len(segment), segment_offset + length + 8)
                ].hex(),
            }
        )
    return rows


def build_raw_alignment_rows(payload: dict[str, object], *, limit: int) -> list[dict[str, str]]:
    target = payload["target"]
    data = payload["data"]
    segment = payload["segment"]
    if not isinstance(target, dict) or not isinstance(data, bytes) or not isinstance(segment, bytes):
        return []
    if not data or len(segment) < len(data):
        return []
    scored: list[tuple[int, int, int, int]] = []
    for segment_offset in range(0, len(segment) - len(data) + 1):
        exact_offsets = [
            index for index, (source, expected) in enumerate(zip(segment[segment_offset : segment_offset + len(data)], data))
            if source == expected
        ]
        if exact_offsets:
            scored.append((len(exact_offsets), segment_offset, exact_offsets[0], exact_offsets[-1]))
    scored.sort(key=lambda item: (-item[0], item[1]))
    rows: list[dict[str, str]] = []
    for exact, segment_offset, first_exact, last_exact in scored[:limit]:
        source = segment[segment_offset : segment_offset + len(data)]
        rows.append(
            {
                "target_id": target.get("target_id", ""),
                "segment_offset": str(segment_offset),
                "exact_bytes": str(exact),
                "exact_ratio": ratio(exact, len(data)),
                "first_exact_offset": str(first_exact),
                "last_exact_offset": str(last_exact),
                "segment_head_hex": source[:16].hex(),
                "target_head_hex": data[:16].hex(),
                "segment_tail_hex": source[-16:].hex(),
                "target_tail_hex": data[-16:].hex(),
            }
        )
    return rows


def build_band_rows(payload: dict[str, object]) -> list[dict[str, str]]:
    target = payload["target"]
    data = payload["data"]
    if not isinstance(target, dict) or not isinstance(data, bytes):
        return []
    by_class: dict[str, list[int]] = {}
    for value in data:
        by_class.setdefault(value_class(value), []).append(value)
    rows: list[dict[str, str]] = []
    for class_name, values in sorted(by_class.items()):
        rows.append(
            {
                "target_id": target.get("target_id", ""),
                "value_class": class_name,
                "bytes": str(len(values)),
                "ratio": ratio(len(values), len(data)),
                "values_hex": unique_hex(bytes(values)),
            }
        )
    return rows


def target_summary_row(
    payload: dict[str, object],
    rle_rows: list[dict[str, str]],
    delta_rows: list[dict[str, str]],
    raw_rows: list[dict[str, str]],
    align_rows: list[dict[str, str]],
) -> dict[str, str]:
    target = payload["target"]
    data = payload["data"]
    segment = payload["segment"]
    control = payload["control"]
    fragment = payload["fragment"]
    known_mask = payload["known_mask"]
    if not isinstance(target, dict) or not isinstance(data, bytes):
        return {}
    if not isinstance(segment, bytes):
        segment = b""
    if not isinstance(control, bytes):
        control = b""
    if not isinstance(fragment, bytes):
        fragment = b""
    if not isinstance(known_mask, bytes):
        known_mask = b""
    start = int_value(target, "start")
    end = int_value(target, "end")
    known_target = sum(1 for value in known_mask[start:end] if value)
    deltas = [signed_delta(left, right) for left, right in zip(data, data[1:])]
    top_byte, top_count = Counter(data).most_common(1)[0] if data else (None, 0)
    repeated = sum(int_value(row, "length") for row in rle_rows)
    raw_covered = sum(int_value(row, "length") for row in raw_rows)
    best_raw_literal = max((int_value(row, "length") for row in raw_rows), default=0)
    best_align = int_value(align_rows[0], "exact_bytes") if align_rows else 0
    verdict = "frontier80_structural_nonzero_segment_literal_rle_signal"
    next_probe = "derive compact-control token parser for segment-literal structural nonzero run"
    if raw_covered < max(1, len(data) // 4):
        verdict = "frontier80_structural_nonzero_runlocal_rle_signal"
        next_probe = "derive run-local RLE/delta token parser for structural nonzero run"
    return {
        "target_id": target.get("target_id", ""),
        "rank": target.get("rank", ""),
        "archive": target.get("archive", ""),
        "archive_tag": target.get("archive_tag", ""),
        "pcx_name": target.get("pcx_name", ""),
        "frontier_id": target.get("frontier_id", ""),
        "span_index": target.get("span_index", ""),
        "run_index": target.get("run_index", ""),
        "start": target.get("start", ""),
        "end": target.get("end", ""),
        "length": target.get("length", ""),
        "unique_values_hex": unique_hex(data),
        "top_byte_hex": hex_byte(top_byte),
        "top_byte_count": str(top_count),
        "head_hex": data[:16].hex(),
        "tail_hex": data[-16:].hex(),
        "byte_rle_rows": str(len(rle_rows)),
        "repeated_run_bytes": str(repeated),
        "same_prev_transitions": str(sum(1 for delta in deltas if delta == 0)),
        "small_delta_le2_transitions": str(sum(1 for delta in deltas if abs(delta) <= 2)),
        "small_delta_segment_rows": str(len(delta_rows)),
        "raw_literal_rows": str(len(raw_rows)),
        "raw_literal_covered_bytes": str(raw_covered),
        "best_raw_literal_length": str(best_raw_literal),
        "best_raw_window_exact_bytes": str(best_align),
        "segment_gap_bytes": str(len(segment)),
        "control_prefix_bytes": str(len(control)),
        "fragment_bytes": str(len(fragment)),
        "known_target_bytes": str(known_target),
        "verdict": verdict,
        "next_probe": next_probe,
    }


def write_html(
    output: Path,
    title: str,
    summary: dict[str, str],
    target_rows: list[dict[str, str]],
    raw_rows: list[dict[str, str]],
    align_rows: list[dict[str, str]],
) -> None:
    data = {
        "summary": summary,
        "targets": target_rows,
        "rawLiterals": raw_rows,
        "rawAlignments": align_rows,
    }
    target_preview = "\n".join(
        "<tr>"
        + "".join(
            f"<td>{html.escape(row.get(field, ''))}</td>"
            for field in [
                "target_id",
                "length",
                "repeated_run_bytes",
                "small_delta_le2_transitions",
                "raw_literal_covered_bytes",
                "best_raw_literal_length",
                "best_raw_window_exact_bytes",
                "verdict",
            ]
        )
        + "</tr>"
        for row in target_rows[:20]
    )
    raw_preview = "\n".join(
        "<tr>"
        + "".join(
            f"<td>{html.escape(row.get(field, ''))}</td>"
            for field in ["target_id", "target_offset_start", "length", "segment_offset", "literal_hex"]
        )
        + "</tr>"
        for row in raw_rows[:30]
    )
    html_text = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{html.escape(title)}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 24px; color: #20242a; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 16px; }}
    th, td {{ border-bottom: 1px solid #d8dde5; padding: 6px 8px; text-align: left; font-size: 13px; }}
    th {{ background: #edf1f7; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }}
    .stat {{ border: 1px solid #d8dde5; border-radius: 6px; padding: 10px 12px; }}
    .label {{ color: #5c6675; font-size: 12px; }}
    .value {{ font-size: 20px; font-weight: 650; margin-top: 2px; }}
    .links a {{ margin-right: 12px; }}
    code {{ white-space: nowrap; }}
  </style>
</head>
<body>
  <h1>{html.escape(title)}</h1>
  <div class="grid">
    <div class="stat"><div class="label">Target bytes</div><div class="value">{html.escape(summary['target_bytes'])}</div></div>
    <div class="stat"><div class="label">Repeated bytes</div><div class="value">{html.escape(summary['repeated_run_bytes'])}</div></div>
    <div class="stat"><div class="label">Raw literal covered</div><div class="value">{html.escape(summary['raw_literal_covered_bytes'])}</div></div>
    <div class="stat"><div class="label">Best raw window</div><div class="value">{html.escape(summary['best_raw_window_exact_bytes'])}</div></div>
    <div class="stat"><div class="label">Verdict</div><div class="value">{html.escape(summary['review_verdict'])}</div></div>
  </div>
  <p class="links">
    <a href="{relative_href(output / 'summary.csv', output / 'index.html')}">summary.csv</a>
    <a href="{relative_href(output / 'targets.csv', output / 'index.html')}">targets.csv</a>
    <a href="{relative_href(output / 'raw_literals.csv', output / 'index.html')}">raw_literals.csv</a>
    <a href="{relative_href(output / 'raw_alignments.csv', output / 'index.html')}">raw_alignments.csv</a>
  </p>
  <h2>Targets</h2>
  <table>
    <thead><tr><th>target</th><th>length</th><th>RLE bytes</th><th>delta&lt;=2</th><th>raw covered</th><th>best literal</th><th>best raw window</th><th>verdict</th></tr></thead>
    <tbody>{target_preview}</tbody>
  </table>
  <h2>Raw literal hits</h2>
  <table>
    <thead><tr><th>target</th><th>target offset</th><th>length</th><th>segment offset</th><th>literal</th></tr></thead>
    <tbody>{raw_preview}</tbody>
  </table>
  <script type="application/json" id="probe-data">{html.escape(json.dumps(data, ensure_ascii=True))}</script>
</body>
</html>
"""
    (output / "index.html").write_text(html_text)


def run(args: argparse.Namespace) -> dict[str, str]:
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    run_rows = read_csv(args.runs)
    manifest_rows = read_csv(args.manifest)
    clean_rows = read_csv(args.clean_fixtures)
    targets = select_largest_targets(run_rows, issues)
    payloads = load_target_payloads(targets, manifest_rows, clean_rows, issues)

    target_rows: list[dict[str, str]] = []
    rle_rows: list[dict[str, str]] = []
    delta_rows: list[dict[str, str]] = []
    raw_rows: list[dict[str, str]] = []
    align_rows: list[dict[str, str]] = []
    band_rows: list[dict[str, str]] = []

    for payload in payloads:
        payload_rle = build_rle_rows(payload)
        payload_delta = build_delta_segment_rows(payload)
        payload_raw = build_raw_literal_rows(payload, min_length=args.min_raw_literal)
        payload_align = build_raw_alignment_rows(payload, limit=args.alignment_rows)
        rle_rows.extend(payload_rle)
        delta_rows.extend(payload_delta)
        raw_rows.extend(payload_raw)
        align_rows.extend(payload_align)
        band_rows.extend(build_band_rows(payload))
        row = target_summary_row(payload, payload_rle, payload_delta, payload_raw, payload_align)
        if row:
            target_rows.append(row)

    total_bytes = sum(int_value(row, "length") for row in target_rows)
    repeated = sum(int_value(row, "repeated_run_bytes") for row in target_rows)
    small_delta = sum(int_value(row, "small_delta_le2_transitions") for row in target_rows)
    transition_total = sum(max(0, int_value(row, "length") - 1) for row in target_rows)
    raw_covered = sum(int_value(row, "raw_literal_covered_bytes") for row in target_rows)
    best_raw_literal = max((int_value(row, "best_raw_literal_length") for row in target_rows), default=0)
    best_raw_literal_offset = ""
    if raw_rows:
        best_raw = max(raw_rows, key=lambda row: int_value(row, "length"))
        best_raw_literal_offset = best_raw.get("segment_offset", "")
    best_align = max((int_value(row, "exact_bytes") for row in align_rows), default=0)
    best_align_offset = ""
    if align_rows:
        best_align_row = max(align_rows, key=lambda row: int_value(row, "exact_bytes"))
        best_align_offset = best_align_row.get("segment_offset", "")
    known_target = sum(int_value(row, "known_target_bytes") for row in target_rows)
    verdict = "frontier80_structural_nonzero_segment_literal_rle_signal"
    next_probe = "derive compact-control token parser for segment-literal structural nonzero run"
    if raw_covered < max(1, total_bytes // 4):
        verdict = "frontier80_structural_nonzero_runlocal_rle_signal"
        next_probe = "derive run-local RLE/delta token parser for structural nonzero run"
    summary = {
        "scope": "total",
        "target_runs": str(len(target_rows)),
        "target_bytes": str(total_bytes),
        "largest_run_bytes": str(max((int_value(row, "length") for row in target_rows), default=0)),
        "byte_rle_rows": str(len(rle_rows)),
        "repeated_run_bytes": str(repeated),
        "repeated_run_ratio": ratio(repeated, total_bytes),
        "same_prev_transitions": str(sum(int_value(row, "same_prev_transitions") for row in target_rows)),
        "small_delta_le2_transitions": str(small_delta),
        "small_delta_le2_ratio": ratio(small_delta, transition_total),
        "small_delta_segment_rows": str(len(delta_rows)),
        "raw_literal_rows": str(len(raw_rows)),
        "raw_literal_covered_bytes": str(raw_covered),
        "raw_literal_covered_ratio": ratio(raw_covered, total_bytes),
        "best_raw_literal_length": str(best_raw_literal),
        "best_raw_literal_segment_offset": best_raw_literal_offset,
        "best_raw_window_exact_bytes": str(best_align),
        "best_raw_window_segment_offset": best_align_offset,
        "best_raw_window_exact_ratio": ratio(best_align, total_bytes),
        "known_target_bytes": str(known_target),
        "issue_rows": str(len(issues)),
        "review_verdict": verdict,
        "next_probe": next_probe,
    }

    write_csv(output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output / "targets.csv", TARGET_FIELDNAMES, target_rows)
    write_csv(output / "byte_rle.csv", RLE_FIELDNAMES, rle_rows)
    write_csv(output / "small_delta_segments.csv", DELTA_SEGMENT_FIELDNAMES, delta_rows)
    write_csv(output / "raw_literals.csv", RAW_LITERAL_FIELDNAMES, raw_rows)
    write_csv(output / "raw_alignments.csv", RAW_ALIGNMENT_FIELDNAMES, align_rows)
    write_csv(output / "value_bands.csv", BAND_FIELDNAMES, band_rows)
    (output / "issues.txt").write_text("\n".join(issues))
    write_html(output, args.title, summary, target_rows, raw_rows, align_rows)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe structural nonzero producers for Frontier80 clean-gap runs.")
    parser.add_argument("--runs", type=Path, default=DEFAULT_RUNS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--clean-fixtures", type=Path, default=DEFAULT_CLEAN_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Structural Nonzero Producer Probe",
    )
    parser.add_argument("--min-raw-literal", type=int, default=4)
    parser.add_argument("--alignment-rows", type=int, default=20)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = run(args)
    print(f"Target bytes: {summary['target_bytes']}")
    print(f"Repeated bytes: {summary['repeated_run_bytes']}")
    print(f"Raw literal covered bytes: {summary['raw_literal_covered_bytes']}")
    print(f"Best raw window exact bytes: {summary['best_raw_window_exact_bytes']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
