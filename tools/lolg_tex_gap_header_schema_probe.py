#!/usr/bin/env python3
"""Probe .tex gap control headers for schema blocks and payload starts."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import defaultdict
from pathlib import Path

from lolg_tex_gap_fixture_replay import common_prefix, exact_byte_count, first_mismatch
from lolg_tex_gap_geometry_replay import geometry_mask_replay
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_header_schema_probe")
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_ZERO_RUN_FIXTURES = Path("output/tex_gap_zero_run_probe/fixtures.csv")
DEFAULT_CONTROL_HITS = Path("output/tex_gap_control_word_probe/hits.csv")
DEFAULT_GEOMETRY_BEST = Path("output/tex_gap_geometry_replay/best_by_fixture.csv")

HIT_SIZES = {"byte": 1, "u16le": 2, "u16be": 2}

SUMMARY_FIELDNAMES = [
    "scope",
    "fixture_rows",
    "block_rows",
    "payload_candidate_rows",
    "source_modes",
    "dimension_pair_blocks",
    "fixtures_with_dimension_pair",
    "row_mask_blocks",
    "fixtures_with_row_mask_block",
    "exact_match_rows",
    "exact_match_fixtures",
    "best_prefix_bytes",
    "best_exact_bytes",
    "best_rank",
    "best_pcx",
    "best_frontier_id",
    "best_payload_offset",
    "best_source_mode",
    "issue_rows",
]

FIXTURE_FIELDNAMES = [
    "rank",
    "rule_type",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "frontier_type",
    "pixel_gap",
    "segment_gap_bytes",
    "cdcache_width",
    "cdcache_height",
    "leading_zero_bytes",
    "nonzero_columns",
    "hit_count",
    "block_count",
    "dimension_pair_blocks",
    "row_mask_blocks",
    "payload_candidate_count",
    "best_payload_offset",
    "best_source_mode",
    "best_prefix_bytes",
    "best_exact_bytes",
    "full_match",
    "segment_head_hex",
    "issues",
]

BLOCK_FIELDNAMES = [
    "rank",
    "pcx_name",
    "frontier_id",
    "block_index",
    "block_type",
    "block_start",
    "block_end",
    "suggested_payload_offset",
    "hit_count",
    "metrics",
    "encodings",
    "values",
    "dimension_pair",
    "row_mask_block",
    "context_hex",
]

PAYLOAD_FIELDNAMES = [
    "rank",
    "rule_type",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "frontier_type",
    "payload_offset",
    "offset_reasons",
    "source_mode",
    "pixel_gap",
    "segment_gap_bytes",
    "stream_bytes",
    "nonzero_slots",
    "zero_columns",
    "cdcache_width",
    "gap_start",
    "prefix_bytes",
    "prefix_ratio",
    "exact_bytes",
    "exact_ratio",
    "full_match",
    "first_mismatch_at",
    "output_head_hex",
    "expected_head_hex",
    "notes",
    "issues",
]

BEST_FIELDNAMES = [
    "rank",
    "rule_type",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "frontier_type",
    "pixel_gap",
    "segment_gap_bytes",
    "best_payload_offset",
    "best_offset_reasons",
    "best_source_mode",
    "zero_columns",
    "cdcache_width",
    "best_prefix_bytes",
    "best_prefix_ratio",
    "best_exact_bytes",
    "best_exact_ratio",
    "full_match",
    "first_mismatch_at",
    "notes",
    "issues",
]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def load_bytes(path_text: str, issues: list[str], label: str) -> bytes:
    if not path_text:
        issues.append(f"missing_{label}_path")
        return b""
    try:
        return Path(path_text).read_bytes()
    except OSError as exc:
        issues.append(f"read_{label}_failed:{exc}")
        return b""


def fixture_key(row: dict[str, str]) -> tuple[str, str, str]:
    return (row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", ""))


def zero_key(row: dict[str, str]) -> tuple[str, str, str]:
    return (row.get("archive", ""), row.get("pcx_name", ""), row.get("frontier_id", ""))


def hit_size(row: dict[str, str]) -> int:
    return HIT_SIZES.get(row.get("encoding", ""), 1)


def context_hex(data: bytes, start: int, end: int, radius: int = 8) -> str:
    left = max(0, start - radius)
    right = min(len(data), end + radius)
    return data[left:right].hex()


def block_type(metrics: set[str]) -> str:
    if {"width", "height"}.issubset(metrics):
        return "dimension_block"
    if "leading_row_prefix_zero_runs" in metrics:
        return "row_prefix_block"
    if "nonzero_columns" in metrics:
        return "column_count_block"
    return "metric_block"


def build_blocks_for_fixture(
    fixture: dict[str, str],
    hits: list[dict[str, str]],
    segment: bytes,
) -> list[dict[str, str]]:
    ordered = sorted(
        hits,
        key=lambda row: (
            int_value(row, "offset"),
            row.get("encoding", ""),
            row.get("metric", ""),
        ),
    )
    groups: list[list[dict[str, str]]] = []
    current: list[dict[str, str]] = []
    current_end = -1
    for row in ordered:
        offset = int_value(row, "offset")
        end = offset + hit_size(row)
        if not current or offset - current_end <= 8:
            current.append(row)
            current_end = max(current_end, end)
        else:
            groups.append(current)
            current = [row]
            current_end = end
    if current:
        groups.append(current)

    output: list[dict[str, str]] = []
    for index, group in enumerate(groups, start=1):
        start = min(int_value(row, "offset") for row in group)
        end = max(int_value(row, "offset") + hit_size(row) for row in group)
        metrics = {row.get("metric", "") for row in group if row.get("metric")}
        encodings = {row.get("encoding", "") for row in group if row.get("encoding")}
        values = {
            f"{row.get('metric', '')}={row.get('value', '')}"
            for row in group
            if row.get("metric") and row.get("value")
        }
        has_dimensions = {"width", "height"}.issubset(metrics)
        has_row_mask = bool({"width", "zero_run_period_guess", "leading_row_prefix_zero_runs"} & metrics) and (
            "leading_row_prefix_zero_runs" in metrics
        )
        output.append(
            {
                "rank": fixture.get("rank", ""),
                "pcx_name": fixture.get("pcx_name", ""),
                "frontier_id": fixture.get("frontier_id", ""),
                "block_index": str(index),
                "block_type": block_type(metrics),
                "block_start": str(start),
                "block_end": str(end),
                "suggested_payload_offset": str(end),
                "hit_count": str(len(group)),
                "metrics": ";".join(sorted(metrics)),
                "encodings": ";".join(sorted(encodings)),
                "values": ";".join(sorted(values)),
                "dimension_pair": "1" if has_dimensions else "0",
                "row_mask_block": "1" if has_row_mask else "0",
                "context_hex": context_hex(segment, start, end),
            }
        )
    return output


def add_offset(reasons: dict[int, set[str]], offset: int, reason: str, segment_len: int) -> None:
    if 0 <= offset < segment_len:
        reasons.setdefault(offset, set()).add(reason)


def candidate_offsets(
    fixture: dict[str, str],
    hits: list[dict[str, str]],
    blocks: list[dict[str, str]],
    geometry_best: dict[str, str],
    segment_len: int,
) -> dict[int, set[str]]:
    reasons: dict[int, set[str]] = {}
    add_offset(reasons, 0, "segment_start", segment_len)
    best_raw_skip = int_value(fixture, "best_raw_skip")
    best_raw_prefix = int_value(fixture, "best_raw_prefix_bytes")
    add_offset(reasons, best_raw_skip, "fixture_best_raw_skip", segment_len)
    add_offset(reasons, best_raw_skip + best_raw_prefix, "fixture_after_best_raw_fragment", segment_len)
    if geometry_best:
        add_offset(reasons, int_value(geometry_best, "best_skip"), "geometry_best_skip", segment_len)

    for row in hits:
        offset = int_value(row, "offset")
        metric = row.get("metric", "metric")
        add_offset(reasons, offset, f"hit_{metric}", segment_len)
        add_offset(reasons, offset + hit_size(row), f"after_hit_{metric}", segment_len)
    for block in blocks:
        offset = int_value(block, "suggested_payload_offset")
        reason = f"after_{block.get('block_type', 'block')}"
        add_offset(reasons, offset, reason, segment_len)
    return reasons


def stream_from_segment(segment: bytes, offset: int, mode: str) -> bytes:
    source = segment[offset:] if 0 <= offset <= len(segment) else b""
    if mode == "raw":
        return source
    if mode == "drop_zero_source":
        return bytes(value for value in source if value != 0)
    raise ValueError(f"unknown source mode: {mode}")


def payload_candidate_row(
    fixture: dict[str, str],
    zero_fixture: dict[str, str],
    *,
    payload_offset: int,
    reasons: set[str],
    source_mode: str,
    segment: bytes,
    expected: bytes,
    context_bytes: int,
    source_issues: list[str],
) -> dict[str, str]:
    source = stream_from_segment(segment, payload_offset, source_mode)
    width = int_value(zero_fixture, "cdcache_width")
    zero_columns = int_value(zero_fixture, "leading_zero_bytes")
    gap_start = int_value(zero_fixture, "gap_start")
    output, nonzero_slots = geometry_mask_replay(
        len(expected),
        gap_start=gap_start,
        width=width,
        zero_columns=zero_columns,
        source=source,
    )
    prefix = common_prefix(output, expected)
    exact = exact_byte_count(output, expected)
    notes: list[str] = []
    if len(source) < nonzero_slots:
        notes.append("stream_short")
    full_match = bool(expected and prefix == len(expected))
    return {
        "rank": fixture.get("rank", ""),
        "rule_type": fixture.get("rule_type", ""),
        "archive": fixture.get("archive", ""),
        "archive_tag": fixture.get("archive_tag", ""),
        "pcx_name": fixture.get("pcx_name", ""),
        "frontier_id": fixture.get("frontier_id", ""),
        "frontier_type": fixture.get("frontier_type", ""),
        "payload_offset": str(payload_offset),
        "offset_reasons": ";".join(sorted(reasons)),
        "source_mode": source_mode,
        "pixel_gap": str(len(expected)),
        "segment_gap_bytes": str(len(segment)),
        "stream_bytes": str(len(source)),
        "nonzero_slots": str(nonzero_slots),
        "zero_columns": str(zero_columns),
        "cdcache_width": str(width),
        "gap_start": str(gap_start),
        "prefix_bytes": str(prefix),
        "prefix_ratio": f"{(prefix / len(expected)) if expected else 0.0:.6f}",
        "exact_bytes": str(exact),
        "exact_ratio": f"{(exact / len(expected)) if expected else 0.0:.6f}",
        "full_match": "1" if full_match else "0",
        "first_mismatch_at": first_mismatch(prefix, output, expected),
        "output_head_hex": output[:context_bytes].hex(),
        "expected_head_hex": expected[:context_bytes].hex(),
        "notes": ";".join(notes),
        "issues": ";".join(source_issues),
    }


def sort_candidate_key(row: dict[str, str]) -> tuple[int, int, int, int]:
    return (
        int_value(row, "prefix_bytes"),
        int_value(row, "exact_bytes"),
        int(row.get("full_match", "0") or 0),
        -int_value(row, "payload_offset"),
    )


def best_by_fixture(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[fixture_key(row)].append(row)

    best_rows: list[dict[str, str]] = []
    for candidates in grouped.values():
        best = max(candidates, key=sort_candidate_key)
        best_rows.append(
            {
                "rank": best.get("rank", ""),
                "rule_type": best.get("rule_type", ""),
                "archive": best.get("archive", ""),
                "archive_tag": best.get("archive_tag", ""),
                "pcx_name": best.get("pcx_name", ""),
                "frontier_id": best.get("frontier_id", ""),
                "frontier_type": best.get("frontier_type", ""),
                "pixel_gap": best.get("pixel_gap", ""),
                "segment_gap_bytes": best.get("segment_gap_bytes", ""),
                "best_payload_offset": best.get("payload_offset", ""),
                "best_offset_reasons": best.get("offset_reasons", ""),
                "best_source_mode": best.get("source_mode", ""),
                "zero_columns": best.get("zero_columns", ""),
                "cdcache_width": best.get("cdcache_width", ""),
                "best_prefix_bytes": best.get("prefix_bytes", ""),
                "best_prefix_ratio": best.get("prefix_ratio", ""),
                "best_exact_bytes": best.get("exact_bytes", ""),
                "best_exact_ratio": best.get("exact_ratio", ""),
                "full_match": best.get("full_match", ""),
                "first_mismatch_at": best.get("first_mismatch_at", ""),
                "notes": best.get("notes", ""),
                "issues": best.get("issues", ""),
            }
        )
    return sorted(best_rows, key=lambda row: int_value(row, "rank"))


def build_rows(
    fixtures: Path,
    zero_run_fixtures: Path,
    control_hits: Path,
    geometry_best_path: Path,
    *,
    limit: int,
    context_bytes: int,
) -> tuple[
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
]:
    fixture_rows = sorted(read_rows(fixtures), key=lambda row: int_value(row, "rank"))
    if limit > 0:
        fixture_rows = fixture_rows[:limit]
    zero_rows = {zero_key(row): row for row in read_rows(zero_run_fixtures)}
    hit_rows: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in read_rows(control_hits):
        hit_rows[fixture_key(row)].append(row)
    geometry_rows = {fixture_key(row): row for row in read_rows(geometry_best_path)}

    output_fixtures: list[dict[str, str]] = []
    output_blocks: list[dict[str, str]] = []
    payload_rows: list[dict[str, str]] = []

    for fixture in fixture_rows:
        issues: list[str] = []
        key = fixture_key(fixture)
        zero_fixture = zero_rows.get(zero_key(fixture), {})
        if not zero_fixture:
            issues.append("missing_zero_run_fixture")
        if fixture.get("issues"):
            issues.append("source_fixture_has_issues")
        if zero_fixture.get("issues"):
            issues.append("source_zero_probe_has_issues")
        segment = load_bytes(fixture.get("segment_gap_path", ""), issues, "segment")
        expected = load_bytes(fixture.get("expected_gap_path", ""), issues, "expected")
        if len(segment) != int_value(fixture, "segment_gap_bytes"):
            issues.append("segment_size_mismatch")
        if len(expected) != int_value(fixture, "pixel_gap"):
            issues.append("expected_size_mismatch")

        hits = hit_rows.get(key, [])
        blocks = build_blocks_for_fixture(fixture, hits, segment)
        output_blocks.extend(blocks)
        offsets = candidate_offsets(
            fixture,
            hits,
            blocks,
            geometry_rows.get(key, {}),
            len(segment),
        )
        fixture_payload_rows: list[dict[str, str]] = []
        for offset in sorted(offsets):
            for source_mode in ("raw", "drop_zero_source"):
                row = payload_candidate_row(
                    fixture,
                    zero_fixture,
                    payload_offset=offset,
                    reasons=offsets[offset],
                    source_mode=source_mode,
                    segment=segment,
                    expected=expected,
                    context_bytes=context_bytes,
                    source_issues=issues,
                )
                fixture_payload_rows.append(row)
                payload_rows.append(row)

        best = max(fixture_payload_rows, key=sort_candidate_key) if fixture_payload_rows else {}
        dimension_blocks = sum(1 for row in blocks if row.get("dimension_pair") == "1")
        row_mask_blocks = sum(1 for row in blocks if row.get("row_mask_block") == "1")
        width = int_value(zero_fixture, "cdcache_width")
        zero_columns = int_value(zero_fixture, "leading_zero_bytes")
        output_fixtures.append(
            {
                "rank": fixture.get("rank", ""),
                "rule_type": fixture.get("rule_type", ""),
                "archive": fixture.get("archive", ""),
                "archive_tag": fixture.get("archive_tag", ""),
                "pcx_name": fixture.get("pcx_name", ""),
                "frontier_id": fixture.get("frontier_id", ""),
                "frontier_type": fixture.get("frontier_type", ""),
                "pixel_gap": fixture.get("pixel_gap", ""),
                "segment_gap_bytes": fixture.get("segment_gap_bytes", ""),
                "cdcache_width": str(width),
                "cdcache_height": zero_fixture.get("cdcache_height", ""),
                "leading_zero_bytes": str(zero_columns),
                "nonzero_columns": str(max(0, width - zero_columns)),
                "hit_count": str(len(hits)),
                "block_count": str(len(blocks)),
                "dimension_pair_blocks": str(dimension_blocks),
                "row_mask_blocks": str(row_mask_blocks),
                "payload_candidate_count": str(len(fixture_payload_rows)),
                "best_payload_offset": best.get("payload_offset", ""),
                "best_source_mode": best.get("source_mode", ""),
                "best_prefix_bytes": best.get("prefix_bytes", "0"),
                "best_exact_bytes": best.get("exact_bytes", "0"),
                "full_match": best.get("full_match", "0"),
                "segment_head_hex": segment[:context_bytes].hex(),
                "issues": ";".join(issues),
            }
        )

    best_rows = best_by_fixture(payload_rows)
    return output_fixtures, output_blocks, payload_rows, best_rows


def summary_row(
    fixture_rows: list[dict[str, str]],
    block_rows: list[dict[str, str]],
    payload_rows: list[dict[str, str]],
    best_rows: list[dict[str, str]],
) -> dict[str, str]:
    best = max(payload_rows, key=sort_candidate_key) if payload_rows else {}
    best_exact = (
        max(
            payload_rows,
            key=lambda row: (
                int_value(row, "exact_bytes"),
                int_value(row, "prefix_bytes"),
                int(row.get("full_match", "0") or 0),
                -int_value(row, "payload_offset"),
            ),
        )
        if payload_rows
        else {}
    )
    dimension_blocks = [row for row in block_rows if row.get("dimension_pair") == "1"]
    row_mask_blocks = [row for row in block_rows if row.get("row_mask_block") == "1"]
    exact_match_rows = sum(1 for row in payload_rows if row.get("full_match") == "1")
    exact_match_fixtures = sum(1 for row in best_rows if row.get("full_match") == "1")
    issue_rows = sum(1 for row in fixture_rows if row.get("issues"))
    return {
        "scope": "total",
        "fixture_rows": str(len(fixture_rows)),
        "block_rows": str(len(block_rows)),
        "payload_candidate_rows": str(len(payload_rows)),
        "source_modes": str(len({row.get("source_mode", "") for row in payload_rows if row.get("source_mode")})),
        "dimension_pair_blocks": str(len(dimension_blocks)),
        "fixtures_with_dimension_pair": str(len({fixture_key(row) for row in dimension_blocks})),
        "row_mask_blocks": str(len(row_mask_blocks)),
        "fixtures_with_row_mask_block": str(len({fixture_key(row) for row in row_mask_blocks})),
        "exact_match_rows": str(exact_match_rows),
        "exact_match_fixtures": str(exact_match_fixtures),
        "best_prefix_bytes": str(int_value(best, "prefix_bytes")),
        "best_exact_bytes": str(int_value(best_exact, "exact_bytes")),
        "best_rank": best.get("rank", ""),
        "best_pcx": best.get("pcx_name", ""),
        "best_frontier_id": best.get("frontier_id", ""),
        "best_payload_offset": best.get("payload_offset", ""),
        "best_source_mode": best.get("source_mode", ""),
        "issue_rows": str(issue_rows),
    }


def render_fixture_row(row: dict[str, str]) -> str:
    return (
        "<tr>"
        f"<td>{html.escape(row.get('rank', ''))}</td>"
        f"<td>{html.escape(row.get('rule_type', ''))}</td>"
        f"<td>{html.escape(row.get('pcx_name', ''))}</td>"
        f"<td>{html.escape(row.get('frontier_id', ''))}</td>"
        f"<td>{html.escape(row.get('cdcache_width', ''))}x{html.escape(row.get('cdcache_height', ''))}</td>"
        f"<td>{html.escape(row.get('hit_count', ''))}</td>"
        f"<td>{html.escape(row.get('block_count', ''))}</td>"
        f"<td>{html.escape(row.get('dimension_pair_blocks', ''))}</td>"
        f"<td>{html.escape(row.get('row_mask_blocks', ''))}</td>"
        f"<td>{html.escape(row.get('best_payload_offset', ''))}</td>"
        f"<td>{html.escape(row.get('best_source_mode', ''))}</td>"
        f"<td>{html.escape(row.get('best_prefix_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('best_exact_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('issues', ''))}</td>"
        "</tr>"
    )


def render_block_row(row: dict[str, str]) -> str:
    return (
        "<tr>"
        f"<td>{html.escape(row.get('rank', ''))}</td>"
        f"<td>{html.escape(row.get('pcx_name', ''))}</td>"
        f"<td>{html.escape(row.get('frontier_id', ''))}</td>"
        f"<td>{html.escape(row.get('block_type', ''))}</td>"
        f"<td>{html.escape(row.get('block_start', ''))}-{html.escape(row.get('block_end', ''))}</td>"
        f"<td>{html.escape(row.get('suggested_payload_offset', ''))}</td>"
        f"<td>{html.escape(row.get('metrics', ''))}</td>"
        f"<td>{html.escape(row.get('encodings', ''))}</td>"
        f"<td><code>{html.escape(row.get('context_hex', ''))}</code></td>"
        "</tr>"
    )


def render_payload_row(row: dict[str, str]) -> str:
    return (
        "<tr>"
        f"<td>{html.escape(row.get('rank', ''))}</td>"
        f"<td>{html.escape(row.get('pcx_name', ''))}</td>"
        f"<td>{html.escape(row.get('frontier_id', ''))}</td>"
        f"<td>{html.escape(row.get('payload_offset', ''))}</td>"
        f"<td>{html.escape(row.get('source_mode', ''))}</td>"
        f"<td>{html.escape(row.get('offset_reasons', ''))}</td>"
        f"<td>{html.escape(row.get('prefix_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('exact_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('full_match', ''))}</td>"
        f"<td>{html.escape(row.get('notes', ''))}</td>"
        "</tr>"
    )


def build_html(
    summary: dict[str, str],
    fixture_rows: list[dict[str, str]],
    block_rows: list[dict[str, str]],
    payload_rows: list[dict[str, str]],
    best_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "fixtures": fixture_rows,
        "blocks": block_rows,
        "payloadCandidates": payload_rows,
        "best": best_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("fixtures.csv", output_dir / "fixtures.csv"),
            ("blocks.csv", output_dir / "blocks.csv"),
            ("payload_candidates.csv", output_dir / "payload_candidates.csv"),
            ("best_by_fixture.csv", output_dir / "best_by_fixture.csv"),
        )
    )
    fixture_markup = "\n".join(render_fixture_row(row) for row in fixture_rows)
    block_markup = "\n".join(render_block_row(row) for row in block_rows[:160])
    top_payload = sorted(payload_rows, key=sort_candidate_key, reverse=True)[:160]
    payload_markup = "\n".join(render_payload_row(row) for row in top_payload)
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root {{
  color-scheme: dark;
  --bg: #101316;
  --panel: #171d22;
  --line: #2f3942;
  --text: #edf3f6;
  --muted: #9caab3;
  --accent: #74d3ae;
  --ok: #78d98f;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  min-height: 100vh;
  background: var(--bg);
  color: var(--text);
  font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}}
.wrap {{ width: min(1600px, calc(100vw - 28px)); margin: 0 auto; }}
header {{
  border-bottom: 1px solid var(--line);
  background: #12171b;
  padding: 18px 0 14px;
}}
h1 {{ margin: 0; font-size: 21px; font-weight: 700; letter-spacing: 0; }}
.sub {{ color: var(--muted); margin-top: 4px; }}
main {{ padding: 16px 0 28px; display: grid; gap: 16px; }}
.stats {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 10px;
}}
.stat, .panel {{
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--panel);
  padding: 10px;
}}
.label, .muted {{ color: var(--muted); }}
.value {{ font-size: 24px; font-weight: 750; line-height: 1.05; margin-top: 4px; }}
.ok {{ color: var(--ok); }}
.panel {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; min-width: 1220px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
code {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; overflow-wrap: anywhere; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Groupes de mots de controle .tex et offsets plausibles de payload, verifies contre les gaps CDCACHE.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Fixtures</div><div class="value">{html.escape(summary['fixture_rows'])}</div></div>
    <div class="stat"><div class="label">Blocks</div><div class="value">{html.escape(summary['block_rows'])}</div></div>
    <div class="stat"><div class="label">Payload candidates</div><div class="value">{html.escape(summary['payload_candidate_rows'])}</div></div>
    <div class="stat"><div class="label">Dimension blocks</div><div class="value ok">{html.escape(summary['dimension_pair_blocks'])}</div></div>
    <div class="stat"><div class="label">Best prefix</div><div class="value ok">{html.escape(summary['best_prefix_bytes'])}</div></div>
    <div class="stat"><div class="label">Best exact</div><div class="value ok">{html.escape(summary['best_exact_bytes'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div></section>
  <section class="panel">
    <h2>Fixtures</h2>
    <table>
      <thead><tr><th>Rank</th><th>Rule</th><th>PCX</th><th>Frontier</th><th>Size</th><th>Hits</th><th>Blocks</th><th>Dim</th><th>Mask</th><th>Best offset</th><th>Mode</th><th>Prefix</th><th>Exact</th><th>Issues</th></tr></thead>
      <tbody>{fixture_markup}</tbody>
    </table>
  </section>
  <section class="panel">
    <h2>Header blocks</h2>
    <table>
      <thead><tr><th>Rank</th><th>PCX</th><th>Frontier</th><th>Type</th><th>Range</th><th>Payload</th><th>Metrics</th><th>Encodings</th><th>Context</th></tr></thead>
      <tbody>{block_markup}</tbody>
    </table>
  </section>
  <section class="panel">
    <h2>Top payload candidates</h2>
    <table>
      <thead><tr><th>Rank</th><th>PCX</th><th>Frontier</th><th>Offset</th><th>Mode</th><th>Reasons</th><th>Prefix</th><th>Exact</th><th>Full</th><th>Notes</th></tr></thead>
      <tbody>{payload_markup}</tbody>
    </table>
  </section>
</main>
<script>
const TEX_GAP_HEADER_SCHEMA_PROBE = {data_json};
</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    fixtures: Path,
    zero_run_fixtures: Path,
    control_hits: Path,
    geometry_best: Path,
    *,
    limit: int,
    context_bytes: int,
    title: str,
) -> tuple[
    dict[str, str],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
]:
    output_dir.mkdir(parents=True, exist_ok=True)
    fixture_rows, block_rows, payload_rows, best_rows = build_rows(
        fixtures,
        zero_run_fixtures,
        control_hits,
        geometry_best,
        limit=limit,
        context_bytes=context_bytes,
    )
    summary = summary_row(fixture_rows, block_rows, payload_rows, best_rows)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "fixtures.csv", FIXTURE_FIELDNAMES, fixture_rows)
    write_csv(output_dir / "blocks.csv", BLOCK_FIELDNAMES, block_rows)
    write_csv(output_dir / "payload_candidates.csv", PAYLOAD_FIELDNAMES, payload_rows)
    write_csv(output_dir / "best_by_fixture.csv", BEST_FIELDNAMES, best_rows)
    (output_dir / "index.html").write_text(
        build_html(summary, fixture_rows, block_rows, payload_rows, best_rows, output_dir, title)
    )
    return summary, fixture_rows, block_rows, payload_rows, best_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe .tex gap header schema and payload offsets.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--zero-run-fixtures", type=Path, default=DEFAULT_ZERO_RUN_FIXTURES)
    parser.add_argument("--control-hits", type=Path, default=DEFAULT_CONTROL_HITS)
    parser.add_argument("--geometry-best", type=Path, default=DEFAULT_GEOMETRY_BEST)
    parser.add_argument("--limit", type=int, default=32)
    parser.add_argument("--context-bytes", type=int, default=32)
    parser.add_argument("--title", default="Lands of Lore II .tex Gap Header Schema Probe")
    args = parser.parse_args()

    summary, _fixture_rows, _block_rows, _payload_rows, _best_rows = write_report(
        args.output,
        args.fixtures,
        args.zero_run_fixtures,
        args.control_hits,
        args.geometry_best,
        limit=args.limit,
        context_bytes=args.context_bytes,
        title=args.title,
    )
    print(f"Fixture rows: {summary['fixture_rows']}")
    print(f"Block rows: {summary['block_rows']}")
    print(f"Payload candidate rows: {summary['payload_candidate_rows']}")
    print(f"Dimension pair blocks: {summary['dimension_pair_blocks']}")
    print(f"Best prefix bytes: {summary['best_prefix_bytes']}")
    print(f"Best exact bytes: {summary['best_exact_bytes']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
