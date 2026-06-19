#!/usr/bin/env python3
"""Probe normalized palette-walk producers for remaining Frontier80 nonzero runs."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter
from pathlib import Path

from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_frontier80_clean_nonzero_palette_walk_producer_probe")
DEFAULT_RUNS = Path(
    "output/tex_gap_decoder_unresolved_run_probe_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_fixture_replay/runs.csv"
)
DEFAULT_MANIFEST = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_CLEAN_FIXTURES = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_fixture_replay/fixtures.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "nonzero_runs",
    "nonzero_bytes",
    "candidate_runs",
    "candidate_bytes",
    "candidate_palette_bytes",
    "candidate_palette_ratio",
    "largest_candidate_bytes",
    "largest_candidate_palette_ratio",
    "candidate_high_add_0x11_bytes",
    "candidate_low_identity_bytes",
    "candidate_invert_low_control_bytes",
    "candidate_terminal_literal_bytes",
    "best_known_normalized_exact_min",
    "best_known_normalized_exact_max",
    "best_any_normalized_exact_min",
    "best_any_normalized_exact_max",
    "support_rows",
    "segment_rows",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

CANDIDATE_FIELDNAMES = [
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
    "normalized_palette_bytes",
    "normalized_palette_ratio",
    "high_prefix_bytes",
    "high_add_0x11_bytes",
    "low_identity_bytes",
    "invert_low_control_bytes",
    "terminal_literal_bytes",
    "normalized_unique_hex",
    "mode_signature",
    "normalized_delta_le3_bytes",
    "best_known_normalized_exact",
    "best_known_normalized_ratio",
    "best_known_source_key",
    "best_known_source_start",
    "best_any_normalized_exact",
    "best_any_normalized_ratio",
    "best_any_source_key",
    "best_any_source_start",
    "head_hex",
    "normalized_head_hex",
    "tail_hex",
    "normalized_tail_hex",
    "verdict",
    "next_probe",
]

SEGMENT_FIELDNAMES = [
    "target_id",
    "segment_index",
    "mode",
    "mode_code",
    "run_offset_start",
    "run_offset_end",
    "absolute_start",
    "absolute_end",
    "length",
    "normalized_palette_bytes",
    "normalized_delta_le3_bytes",
    "unique_values_hex",
    "head_hex",
    "normalized_head_hex",
    "tail_hex",
    "normalized_tail_hex",
]

SUPPORT_FIELDNAMES = [
    "target_id",
    "source_rank",
    "source_pcx_name",
    "source_frontier_id",
    "source_key",
    "source_start",
    "relative_offset",
    "source_known",
    "source_known_bytes",
    "normalized_exact_bytes",
    "normalized_exact_ratio",
    "raw_exact_bytes",
    "raw_exact_ratio",
    "source_head_hex",
    "normalized_source_head_hex",
]

MODE_CODES = {
    "high_add_0x11": "H",
    "low_identity": "L",
    "invert_low_control": "I",
    "terminal_literal": "T",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def fixture_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", "")


def key_text(key: tuple[str, str, str]) -> str:
    return ":".join(key)


def target_id(row: dict[str, str]) -> str:
    return (
        f"r{int_value(row, 'rank'):03d}_f{row.get('frontier_id', '')}_"
        f"s{row.get('span_index', '')}_run{row.get('run_index', '')}"
    )


def load_bytes(path_text: str, issues: list[str], label: str, key: tuple[str, str, str]) -> bytes:
    if not path_text:
        issues.append(f"{key_text(key)}:missing_{label}_path")
        return b""
    try:
        return Path(path_text).read_bytes()
    except OSError as exc:
        issues.append(f"{key_text(key)}:read_{label}_failed:{exc}")
        return b""


def normalize_byte(value: int) -> tuple[int, str, bool]:
    if 0x67 <= value <= 0x6E:
        return (value - 0x11) & 0xFF, "high_add_0x11", True
    if 0x53 <= value <= 0x5B:
        return value, "low_identity", True
    if 0xA7 <= value <= 0xA9:
        return value ^ 0xFF, "invert_low_control", True
    return value, "terminal_literal", False


def normalize_bytes(data: bytes) -> tuple[bytes, list[str], list[bool]]:
    values: list[int] = []
    modes: list[str] = []
    palette_hits: list[bool] = []
    for value in data:
        normalized, mode, hit = normalize_byte(value)
        values.append(normalized)
        modes.append(mode)
        palette_hits.append(hit and 0x53 <= normalized <= 0x5B)
    return bytes(values), modes, palette_hits


def signed_delta(left: int, right: int) -> int:
    value = (right - left) & 0xFF
    return value if value < 128 else value - 256


def delta_le3_count(data: bytes) -> int:
    return sum(1 for left, right in zip(data, data[1:]) if abs(signed_delta(left, right)) <= 3)


def unique_hex(data: bytes) -> str:
    return " ".join(f"{value:02x}" for value in sorted(set(data)))


def mode_signature(modes: list[str]) -> str:
    if not modes:
        return ""
    chunks: list[str] = []
    start = 0
    current = modes[0]
    for index, mode in enumerate(modes[1:], start=1):
        if mode != current:
            chunks.append(f"{MODE_CODES[current]}{index - start}")
            start = index
            current = mode
    chunks.append(f"{MODE_CODES[current]}{len(modes) - start}")
    return ".".join(chunks)


def high_prefix_len(modes: list[str]) -> int:
    prefix = 0
    for mode in modes:
        if mode != "high_add_0x11":
            break
        prefix += 1
    return prefix


def build_fixture_data(
    manifest_rows: list[dict[str, str]],
    clean_rows: list[dict[str, str]],
    issues: list[str],
) -> dict[tuple[str, str, str], dict[str, object]]:
    clean_by_key = {fixture_key(row): row for row in clean_rows}
    fixtures: dict[tuple[str, str, str], dict[str, object]] = {}
    for manifest in manifest_rows:
        key = fixture_key(manifest)
        clean = clean_by_key.get(key)
        if not clean:
            continue
        expected = load_bytes(manifest.get("expected_gap_path", ""), issues, "expected", key)
        known_mask = load_bytes(clean.get("known_mask_path", ""), issues, "known_mask", key)
        fixtures[key] = {
            "manifest": manifest,
            "clean": clean,
            "expected": expected,
            "known_mask": known_mask,
        }
    return fixtures


def source_known(mask: bytes, start: int, length: int) -> tuple[bool, int]:
    if start < 0 or length <= 0 or start + length > len(mask):
        return False, 0
    known = sum(1 for value in mask[start : start + length] if value)
    return known == length, known


def overlap_same_target(
    source_key: tuple[str, str, str],
    target_key: tuple[str, str, str],
    source_start: int,
    source_end: int,
    target_start: int,
    target_end: int,
) -> bool:
    if source_key != target_key:
        return False
    return max(source_start, target_start) < min(source_end, target_end)


def score_support_rows(
    candidate: dict[str, object],
    fixtures: dict[tuple[str, str, str], dict[str, object]],
    *,
    output_limit: int,
) -> tuple[list[dict[str, str]], dict[str, str], dict[str, str]]:
    target_key = candidate["fixture_key"]
    target_start = int(candidate["start"])
    target_end = int(candidate["end"])
    target_bytes = candidate["data"]
    target_normalized = candidate["normalized"]
    assert isinstance(target_key, tuple)
    assert isinstance(target_bytes, bytes)
    assert isinstance(target_normalized, bytes)
    length = len(target_bytes)

    rows: list[dict[str, str]] = []
    best_known: dict[str, str] = {}
    best_any: dict[str, str] = {}

    for source_key, fixture in fixtures.items():
        expected = fixture.get("expected", b"")
        known_mask = fixture.get("known_mask", b"")
        manifest = fixture.get("manifest", {})
        if not isinstance(expected, bytes) or not isinstance(known_mask, bytes):
            continue
        if not isinstance(manifest, dict):
            manifest = {}
        if len(expected) < length:
            continue
        for source_start in range(0, len(expected) - length + 1):
            source_end = source_start + length
            if overlap_same_target(source_key, target_key, source_start, source_end, target_start, target_end):
                continue
            source = expected[source_start:source_end]
            source_normalized = normalize_bytes(source)[0]
            normalized_exact = sum(
                1 for source_value, target_value in zip(source_normalized, target_normalized) if source_value == target_value
            )
            raw_exact = sum(1 for source_value, target_value in zip(source, target_bytes) if source_value == target_value)
            known_full, known_bytes = source_known(known_mask, source_start, length)
            row = {
                "target_id": str(candidate["target_id"]),
                "source_rank": manifest.get("rank", source_key[0]),
                "source_pcx_name": manifest.get("pcx_name", source_key[1]),
                "source_frontier_id": manifest.get("frontier_id", source_key[2]),
                "source_key": key_text(source_key),
                "source_start": str(source_start),
                "relative_offset": str(source_start - target_start) if source_key == target_key else "",
                "source_known": "1" if known_full else "0",
                "source_known_bytes": str(known_bytes),
                "normalized_exact_bytes": str(normalized_exact),
                "normalized_exact_ratio": f"{normalized_exact / length:.6f}" if length else "0.000000",
                "raw_exact_bytes": str(raw_exact),
                "raw_exact_ratio": f"{raw_exact / length:.6f}" if length else "0.000000",
                "source_head_hex": source[:16].hex(),
                "normalized_source_head_hex": source_normalized[:16].hex(),
            }
            if not best_any or normalized_exact > int_value(best_any, "normalized_exact_bytes"):
                best_any = row
            if known_full and (
                not best_known or normalized_exact > int_value(best_known, "normalized_exact_bytes")
            ):
                best_known = row
            rows.append(row)

    rows.sort(
        key=lambda row: (
            -int_value(row, "normalized_exact_bytes"),
            -int_value(row, "source_known"),
            -int_value(row, "source_known_bytes"),
            -int_value(row, "raw_exact_bytes"),
            row.get("source_key", ""),
            int_value(row, "source_start"),
        )
    )
    return rows[:output_limit], best_known, best_any


def build_segments(candidate: dict[str, object]) -> list[dict[str, str]]:
    modes = candidate["modes"]
    data = candidate["data"]
    normalized = candidate["normalized"]
    assert isinstance(modes, list)
    assert isinstance(data, bytes)
    assert isinstance(normalized, bytes)
    if not data:
        return []
    rows: list[dict[str, str]] = []
    run_start = 0
    current = str(modes[0])
    segment_index = 0
    for index, mode_value in enumerate(modes[1:], start=1):
        mode = str(mode_value)
        if mode != current:
            rows.append(segment_row(candidate, segment_index, run_start, index, current))
            segment_index += 1
            run_start = index
            current = mode
    rows.append(segment_row(candidate, segment_index, run_start, len(data), current))
    return rows


def segment_row(
    candidate: dict[str, object],
    segment_index: int,
    run_start: int,
    run_end: int,
    mode: str,
) -> dict[str, str]:
    data = candidate["data"]
    normalized = candidate["normalized"]
    start = int(candidate["start"])
    assert isinstance(data, bytes)
    assert isinstance(normalized, bytes)
    chunk = data[run_start:run_end]
    norm_chunk = normalized[run_start:run_end]
    palette_bytes = sum(1 for value in norm_chunk if 0x53 <= value <= 0x5B)
    return {
        "target_id": str(candidate["target_id"]),
        "segment_index": str(segment_index),
        "mode": mode,
        "mode_code": MODE_CODES.get(mode, ""),
        "run_offset_start": str(run_start),
        "run_offset_end": str(run_end),
        "absolute_start": str(start + run_start),
        "absolute_end": str(start + run_end),
        "length": str(run_end - run_start),
        "normalized_palette_bytes": str(palette_bytes),
        "normalized_delta_le3_bytes": str(delta_le3_count(norm_chunk)),
        "unique_values_hex": unique_hex(norm_chunk),
        "head_hex": chunk[:16].hex(),
        "normalized_head_hex": norm_chunk[:16].hex(),
        "tail_hex": chunk[-16:].hex(),
        "normalized_tail_hex": norm_chunk[-16:].hex(),
    }


def candidate_record(
    candidate: dict[str, object],
    best_known: dict[str, str],
    best_any: dict[str, str],
) -> dict[str, str]:
    data = candidate["data"]
    normalized = candidate["normalized"]
    modes = candidate["modes"]
    palette_hits = candidate["palette_hits"]
    assert isinstance(data, bytes)
    assert isinstance(normalized, bytes)
    assert isinstance(modes, list)
    assert isinstance(palette_hits, list)
    length = len(data)
    palette_bytes = sum(1 for hit in palette_hits if hit)
    counts = Counter(str(mode) for mode in modes)
    terminal_bytes = counts.get("terminal_literal", 0)
    best_known_exact = int_value(best_known, "normalized_exact_bytes")
    best_any_exact = int_value(best_any, "normalized_exact_bytes")
    verdict = (
        "palette_walk_non_oracle_source_ready"
        if best_known_exact >= length and terminal_bytes == 0
        else "palette_walk_non_oracle_source_needed"
    )
    next_probe = (
        "promote guarded normalized palette-walk producer"
        if verdict.endswith("_ready")
        else "derive non-oracle source and terminal split for normalized palette-walk candidates"
    )
    return {
        "target_id": str(candidate["target_id"]),
        "rank": str(candidate["rank"]),
        "archive": str(candidate["archive"]),
        "archive_tag": str(candidate["archive_tag"]),
        "pcx_name": str(candidate["pcx_name"]),
        "frontier_id": str(candidate["frontier_id"]),
        "span_index": str(candidate["span_index"]),
        "run_index": str(candidate["run_index"]),
        "start": str(candidate["start"]),
        "end": str(candidate["end"]),
        "length": str(length),
        "normalized_palette_bytes": str(palette_bytes),
        "normalized_palette_ratio": f"{palette_bytes / length:.6f}" if length else "0.000000",
        "high_prefix_bytes": str(high_prefix_len([str(mode) for mode in modes])),
        "high_add_0x11_bytes": str(counts.get("high_add_0x11", 0)),
        "low_identity_bytes": str(counts.get("low_identity", 0)),
        "invert_low_control_bytes": str(counts.get("invert_low_control", 0)),
        "terminal_literal_bytes": str(terminal_bytes),
        "normalized_unique_hex": unique_hex(normalized),
        "mode_signature": mode_signature([str(mode) for mode in modes]),
        "normalized_delta_le3_bytes": str(delta_le3_count(normalized)),
        "best_known_normalized_exact": str(best_known_exact),
        "best_known_normalized_ratio": f"{best_known_exact / length:.6f}" if length else "0.000000",
        "best_known_source_key": best_known.get("source_key", ""),
        "best_known_source_start": best_known.get("source_start", ""),
        "best_any_normalized_exact": str(best_any_exact),
        "best_any_normalized_ratio": f"{best_any_exact / length:.6f}" if length else "0.000000",
        "best_any_source_key": best_any.get("source_key", ""),
        "best_any_source_start": best_any.get("source_start", ""),
        "head_hex": data[:16].hex(),
        "normalized_head_hex": normalized[:16].hex(),
        "tail_hex": data[-16:].hex(),
        "normalized_tail_hex": normalized[-16:].hex(),
        "verdict": verdict,
        "next_probe": next_probe,
    }


def select_candidates(
    run_rows: list[dict[str, str]],
    fixtures: dict[tuple[str, str, str], dict[str, object]],
    *,
    min_length: int,
    min_palette_ratio: float,
    issues: list[str],
) -> tuple[list[dict[str, object]], int, int]:
    candidates: list[dict[str, object]] = []
    nonzero_runs = 0
    nonzero_bytes = 0
    for row in run_rows:
        if row.get("run_class") != "nonzero":
            continue
        nonzero_runs += 1
        length = int_value(row, "length")
        nonzero_bytes += length
        key = fixture_key(row)
        fixture = fixtures.get(key)
        if not fixture:
            issues.append(f"{target_id(row)}:missing_fixture_data")
            continue
        expected = fixture.get("expected", b"")
        manifest = fixture.get("manifest", {})
        if not isinstance(expected, bytes):
            continue
        if not isinstance(manifest, dict):
            manifest = {}
        start = int_value(row, "start")
        end = int_value(row, "end")
        data = expected[start:end]
        if len(data) != length:
            issues.append(f"{target_id(row)}:target_window_out_of_bounds")
            continue
        normalized, modes, palette_hits = normalize_bytes(data)
        palette_bytes = sum(1 for hit in palette_hits if hit)
        palette_ratio = palette_bytes / len(data) if data else 0.0
        if length < min_length or palette_ratio < min_palette_ratio:
            continue
        candidates.append(
            {
                "target_id": target_id(row),
                "fixture_key": key,
                "rank": row.get("rank", ""),
                "archive": row.get("archive", manifest.get("archive", "")),
                "archive_tag": row.get("archive_tag", manifest.get("archive_tag", "")),
                "pcx_name": row.get("pcx_name", ""),
                "frontier_id": row.get("frontier_id", ""),
                "span_index": row.get("span_index", ""),
                "run_index": row.get("run_index", ""),
                "start": start,
                "end": end,
                "data": data,
                "normalized": normalized,
                "modes": modes,
                "palette_hits": palette_hits,
            }
        )
    candidates.sort(
        key=lambda candidate: (
            -len(candidate["data"]) if isinstance(candidate["data"], bytes) else 0,
            str(candidate["target_id"]),
        )
    )
    return candidates, nonzero_runs, nonzero_bytes


def build_summary(
    *,
    nonzero_runs: int,
    nonzero_bytes: int,
    candidate_rows: list[dict[str, str]],
    support_rows: list[dict[str, str]],
    segment_rows: list[dict[str, str]],
    issue_count: int,
) -> dict[str, str]:
    candidate_bytes = sum(int_value(row, "length") for row in candidate_rows)
    palette_bytes = sum(int_value(row, "normalized_palette_bytes") for row in candidate_rows)
    largest = max([int_value(row, "length") for row in candidate_rows] or [0])
    largest_rows = [row for row in candidate_rows if int_value(row, "length") == largest]
    largest_ratio = largest_rows[0].get("normalized_palette_ratio", "0.000000") if largest_rows else "0.000000"
    known_values = [int_value(row, "best_known_normalized_exact") for row in candidate_rows]
    any_values = [int_value(row, "best_any_normalized_exact") for row in candidate_rows]
    ready = bool(candidate_rows) and all(row.get("verdict", "").endswith("_ready") for row in candidate_rows)
    if ready:
        verdict = "frontier80_clean_nonzero_palette_walk_producer_ready"
        next_probe = "promote guarded normalized palette-walk producer"
    elif candidate_rows:
        verdict = "frontier80_clean_nonzero_palette_walk_source_needed"
        next_probe = "derive non-oracle source and terminal split for normalized palette-walk candidates"
    else:
        verdict = "frontier80_clean_nonzero_palette_walk_no_candidates"
        next_probe = "return to clean-gap nonzero run queue"
    return {
        "scope": "total",
        "nonzero_runs": str(nonzero_runs),
        "nonzero_bytes": str(nonzero_bytes),
        "candidate_runs": str(len(candidate_rows)),
        "candidate_bytes": str(candidate_bytes),
        "candidate_palette_bytes": str(palette_bytes),
        "candidate_palette_ratio": f"{palette_bytes / candidate_bytes:.6f}" if candidate_bytes else "0.000000",
        "largest_candidate_bytes": str(largest),
        "largest_candidate_palette_ratio": largest_ratio,
        "candidate_high_add_0x11_bytes": str(sum(int_value(row, "high_add_0x11_bytes") for row in candidate_rows)),
        "candidate_low_identity_bytes": str(sum(int_value(row, "low_identity_bytes") for row in candidate_rows)),
        "candidate_invert_low_control_bytes": str(
            sum(int_value(row, "invert_low_control_bytes") for row in candidate_rows)
        ),
        "candidate_terminal_literal_bytes": str(sum(int_value(row, "terminal_literal_bytes") for row in candidate_rows)),
        "best_known_normalized_exact_min": str(min(known_values) if known_values else 0),
        "best_known_normalized_exact_max": str(max(known_values) if known_values else 0),
        "best_any_normalized_exact_min": str(min(any_values) if any_values else 0),
        "best_any_normalized_exact_max": str(max(any_values) if any_values else 0),
        "support_rows": str(len(support_rows)),
        "segment_rows": str(len(segment_rows)),
        "issue_rows": str(issue_count),
        "review_verdict": verdict,
        "next_probe": next_probe,
    }


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 120) -> str:
    if not rows:
        return "<p>No rows.</p>"
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    candidate_rows: list[dict[str, str]],
    segment_rows: list[dict[str, str]],
    support_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "candidates": candidate_rows,
        "segments": segment_rows,
        "support": support_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("candidates.csv", output_dir / "candidates.csv"),
            ("segments.csv", output_dir / "segments.csv"),
            ("source_support.csv", output_dir / "source_support.csv"),
        )
    )
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root {{
  color-scheme: dark;
  --bg: #101417;
  --panel: #171f22;
  --line: #31424a;
  --text: #edf5f4;
  --muted: #9dafb5;
  --accent: #77d3b1;
  --warn: #f0c36a;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  min-height: 100vh;
  background: var(--bg);
  color: var(--text);
  font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}}
.wrap {{ width: min(1680px, calc(100vw - 28px)); margin: 0 auto; }}
header {{ border-bottom: 1px solid var(--line); background: #12191b; padding: 18px 0 14px; }}
h1 {{ margin: 0; font-size: 21px; font-weight: 720; letter-spacing: 0; }}
h2 {{ margin: 0 0 10px; font-size: 16px; }}
.sub {{ color: var(--muted); margin-top: 4px; }}
main {{ padding: 16px 0 28px; display: grid; gap: 16px; }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 10px; }}
.stat, .panel {{ border: 1px solid var(--line); border-radius: 8px; background: var(--panel); padding: 10px; }}
.label, .muted {{ color: var(--muted); }}
.value {{ font-size: 22px; font-weight: 760; line-height: 1.05; margin-top: 4px; }}
.warn {{ color: var(--warn); }}
.panel {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; min-width: 1320px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Normalizes high palette bytes as value-0x11 and inverted a7/a8/a9 controls as low palette values.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Candidate runs</div><div class="value">{html.escape(summary['candidate_runs'])}</div></div>
    <div class="stat"><div class="label">Candidate bytes</div><div class="value">{html.escape(summary['candidate_bytes'])}</div></div>
    <div class="stat"><div class="label">Palette coverage</div><div class="value">{html.escape(summary['candidate_palette_ratio'])}</div></div>
    <div class="stat"><div class="label">Largest candidate</div><div class="value">{html.escape(summary['largest_candidate_bytes'])}</div></div>
    <div class="stat"><div class="label">Known support max</div><div class="value warn">{html.escape(summary['best_known_normalized_exact_max'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div><div class="sub">{html.escape(summary['review_verdict'])}: {html.escape(summary['next_probe'])}</div></section>
  <section class="panel"><h2>Candidates</h2>{render_table(candidate_rows, CANDIDATE_FIELDNAMES)}</section>
  <section class="panel"><h2>Segments</h2>{render_table(segment_rows, SEGMENT_FIELDNAMES)}</section>
  <section class="panel"><h2>Source support</h2>{render_table(support_rows, SUPPORT_FIELDNAMES)}</section>
</main>
<script type="application/json" id="palette-walk-producer-data">{data_json}</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    runs_path: Path,
    manifest_path: Path,
    clean_fixtures_path: Path,
    *,
    min_length: int,
    min_palette_ratio: float,
    support_limit: int,
    title: str,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    fixtures = build_fixture_data(read_csv(manifest_path), read_csv(clean_fixtures_path), issues)
    candidates, nonzero_runs, nonzero_bytes = select_candidates(
        read_csv(runs_path),
        fixtures,
        min_length=min_length,
        min_palette_ratio=min_palette_ratio,
        issues=issues,
    )
    candidate_rows: list[dict[str, str]] = []
    segment_rows: list[dict[str, str]] = []
    support_rows: list[dict[str, str]] = []
    for candidate in candidates:
        top_support, best_known, best_any = score_support_rows(candidate, fixtures, output_limit=support_limit)
        candidate_rows.append(candidate_record(candidate, best_known, best_any))
        segment_rows.extend(build_segments(candidate))
        support_rows.extend(top_support)

    summary = build_summary(
        nonzero_runs=nonzero_runs,
        nonzero_bytes=nonzero_bytes,
        candidate_rows=candidate_rows,
        support_rows=support_rows,
        segment_rows=segment_rows,
        issue_count=len(issues),
    )
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "candidates.csv", CANDIDATE_FIELDNAMES, candidate_rows)
    write_csv(output_dir / "segments.csv", SEGMENT_FIELDNAMES, segment_rows)
    write_csv(output_dir / "source_support.csv", SUPPORT_FIELDNAMES, support_rows)
    (output_dir / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""))
    (output_dir / "index.html").write_text(
        build_html(summary, candidate_rows, segment_rows, support_rows, output_dir, title)
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe normalized palette-walk producers for Frontier80 nonzero runs.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--runs", type=Path, default=DEFAULT_RUNS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--clean-fixtures", type=Path, default=DEFAULT_CLEAN_FIXTURES)
    parser.add_argument("--min-length", type=int, default=32)
    parser.add_argument("--min-palette-ratio", type=float, default=0.90)
    parser.add_argument("--support-limit", type=int, default=12)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Clean Nonzero Palette Walk Producer Probe",
    )
    args = parser.parse_args()

    summary = write_report(
        args.output,
        args.runs,
        args.manifest,
        args.clean_fixtures,
        min_length=args.min_length,
        min_palette_ratio=args.min_palette_ratio,
        support_limit=args.support_limit,
        title=args.title,
    )
    print(f"Candidate runs: {summary['candidate_runs']}")
    print(f"Candidate bytes: {summary['candidate_bytes']}")
    print(f"Palette coverage: {summary['candidate_palette_ratio']}")
    print(f"Known support max: {summary['best_known_normalized_exact_max']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
