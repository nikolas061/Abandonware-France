#!/usr/bin/env python3
"""Probe .tex gap payloads as row-stride encoded nonzero slots."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import defaultdict
from pathlib import Path

from lolg_tex_gap_fixture_replay import common_prefix, exact_byte_count, first_mismatch
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_row_stride_probe")
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_ZERO_RUN_FIXTURES = Path("output/tex_gap_zero_run_probe/fixtures.csv")
DEFAULT_HEADER_BLOCKS = Path("output/tex_gap_header_schema_probe/blocks.csv")
DEFAULT_GEOMETRY_BEST = Path("output/tex_gap_geometry_replay/best_by_fixture.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "fixture_rows",
    "candidate_rows",
    "source_modes",
    "payload_offsets",
    "stride_values",
    "exact_match_rows",
    "exact_match_fixtures",
    "best_prefix_bytes",
    "best_exact_bytes",
    "best_rank",
    "best_pcx",
    "best_frontier_id",
    "best_payload_offset",
    "best_source_mode",
    "best_row_stride",
    "best_row_prefix_skip",
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
    "row_count",
    "nonzero_slots",
    "payload_offsets",
    "candidate_count",
    "best_payload_offset",
    "best_source_mode",
    "best_row_stride",
    "best_row_prefix_skip",
    "best_prefix_bytes",
    "best_exact_bytes",
    "full_match",
    "issues",
]

CANDIDATE_FIELDNAMES = [
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
    "row_stride",
    "row_prefix_skip",
    "row_count",
    "nonzero_columns",
    "pixel_gap",
    "segment_gap_bytes",
    "source_bytes",
    "nonzero_slots",
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
    "best_row_stride",
    "best_row_prefix_skip",
    "nonzero_columns",
    "row_count",
    "nonzero_slots",
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


def build_row_slots(
    expected_len: int,
    *,
    gap_start: int,
    width: int,
    zero_columns: int,
) -> list[list[tuple[int, int]]]:
    rows: list[list[tuple[int, int]]] = []
    current_row: int | None = None
    slots: list[tuple[int, int]] = []
    for offset in range(expected_len):
        absolute = gap_start + offset
        row_index = absolute // width if width else 0
        x = absolute % width if width else 0
        if current_row is None:
            current_row = row_index
        if row_index != current_row:
            rows.append(slots)
            slots = []
            current_row = row_index
        if x >= zero_columns:
            slots.append((offset, x - zero_columns))
    if slots or current_row is not None:
        rows.append(slots)
    return rows


def source_bytes(segment: bytes, offset: int, mode: str) -> bytes:
    source = segment[offset:] if 0 <= offset <= len(segment) else b""
    if mode == "raw":
        return source
    if mode == "drop_zero_source":
        return bytes(value for value in source if value != 0)
    raise ValueError(f"unknown source mode: {mode}")


def row_stride_replay(
    expected_len: int,
    rows: list[list[tuple[int, int]]],
    source: bytes,
    *,
    row_stride: int,
    row_prefix_skip: int,
) -> tuple[bytes, int, bool]:
    output = bytearray(expected_len)
    nonzero_slots = 0
    stream_short = False
    for row_index, slots in enumerate(rows):
        base = row_index * row_stride + row_prefix_skip
        for output_index, slot_index in slots:
            source_index = base + slot_index
            if source_index < len(source):
                output[output_index] = source[source_index]
            else:
                stream_short = True
            nonzero_slots += 1
    return bytes(output), nonzero_slots, stream_short


def add_offset(reasons: dict[int, set[str]], offset: int, reason: str, segment_len: int) -> None:
    if 0 <= offset < segment_len:
        reasons.setdefault(offset, set()).add(reason)


def offsets_for_fixture(
    fixture: dict[str, str],
    blocks: list[dict[str, str]],
    geometry_best: dict[str, str],
    segment_len: int,
) -> dict[int, set[str]]:
    reasons: dict[int, set[str]] = {}
    add_offset(reasons, 0, "segment_start", segment_len)
    add_offset(reasons, int_value(fixture, "best_raw_skip"), "fixture_best_raw_skip", segment_len)
    if geometry_best:
        add_offset(reasons, int_value(geometry_best, "best_skip"), "geometry_best_skip", segment_len)
    for block in blocks:
        add_offset(
            reasons,
            int_value(block, "suggested_payload_offset"),
            f"after_{block.get('block_type', 'block')}",
            segment_len,
        )
    return reasons


def candidate_row(
    fixture: dict[str, str],
    *,
    payload_offset: int,
    reasons: set[str],
    source_mode: str,
    row_stride: int,
    row_prefix_skip: int,
    rows: list[list[tuple[int, int]]],
    nonzero_columns: int,
    segment: bytes,
    expected: bytes,
    context_bytes: int,
    source_issues: list[str],
) -> dict[str, str]:
    source = source_bytes(segment, payload_offset, source_mode)
    output, nonzero_slots, stream_short = row_stride_replay(
        len(expected),
        rows,
        source,
        row_stride=row_stride,
        row_prefix_skip=row_prefix_skip,
    )
    prefix = common_prefix(output, expected)
    exact = exact_byte_count(output, expected)
    notes: list[str] = []
    if stream_short:
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
        "row_stride": str(row_stride),
        "row_prefix_skip": str(row_prefix_skip),
        "row_count": str(len(rows)),
        "nonzero_columns": str(nonzero_columns),
        "pixel_gap": str(len(expected)),
        "segment_gap_bytes": str(len(segment)),
        "source_bytes": str(len(source)),
        "nonzero_slots": str(nonzero_slots),
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


def sort_key(row: dict[str, str]) -> tuple[int, int, int, int, int, int]:
    return (
        int_value(row, "prefix_bytes"),
        int_value(row, "exact_bytes"),
        int(row.get("full_match", "0") or 0),
        -int_value(row, "payload_offset"),
        -int_value(row, "row_stride"),
        -int_value(row, "row_prefix_skip"),
    )


def best_by_fixture(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[fixture_key(row)].append(row)

    best_rows: list[dict[str, str]] = []
    for candidates in grouped.values():
        best = max(candidates, key=sort_key)
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
                "best_row_stride": best.get("row_stride", ""),
                "best_row_prefix_skip": best.get("row_prefix_skip", ""),
                "nonzero_columns": best.get("nonzero_columns", ""),
                "row_count": best.get("row_count", ""),
                "nonzero_slots": best.get("nonzero_slots", ""),
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
    header_blocks: Path,
    geometry_best_path: Path,
    *,
    limit: int,
    max_stride_extra: int,
    max_row_prefix_skip: int,
    context_bytes: int,
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    fixture_rows = sorted(read_rows(fixtures), key=lambda row: int_value(row, "rank"))
    if limit > 0:
        fixture_rows = fixture_rows[:limit]
    zero_rows = {zero_key(row): row for row in read_rows(zero_run_fixtures)}
    blocks_by_key: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in read_rows(header_blocks):
        blocks_by_key[fixture_key(row)].append(row)
    geometry_rows = {fixture_key(row): row for row in read_rows(geometry_best_path)}

    output_fixtures: list[dict[str, str]] = []
    candidate_rows: list[dict[str, str]] = []

    for fixture in fixture_rows:
        zero_fixture = zero_rows.get(zero_key(fixture), {})
        if int_value(zero_fixture, "row_prefix_zero_runs") <= 0:
            continue
        issues: list[str] = []
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

        width = int_value(zero_fixture, "cdcache_width")
        zero_columns = int_value(zero_fixture, "leading_zero_bytes")
        nonzero_columns = max(0, width - zero_columns)
        rows = build_row_slots(
            len(expected),
            gap_start=int_value(zero_fixture, "gap_start"),
            width=width,
            zero_columns=zero_columns,
        )
        max_row_slots = max([len(row) for row in rows] or [0])
        if nonzero_columns <= 0 or max_row_slots <= 0:
            issues.append("missing_nonzero_row_slots")
            continue
        key = fixture_key(fixture)
        offset_reasons = offsets_for_fixture(
            fixture,
            blocks_by_key.get(key, []),
            geometry_rows.get(key, {}),
            len(segment),
        )
        fixture_candidates: list[dict[str, str]] = []
        stride_end = min(width, nonzero_columns + max_stride_extra)
        for payload_offset in sorted(offset_reasons):
            for source_mode in ("raw", "drop_zero_source"):
                for row_stride in range(nonzero_columns, stride_end + 1):
                    max_prefix = min(max_row_prefix_skip, max(0, row_stride - max_row_slots))
                    for row_prefix_skip in range(max_prefix + 1):
                        row = candidate_row(
                            fixture,
                            payload_offset=payload_offset,
                            reasons=offset_reasons[payload_offset],
                            source_mode=source_mode,
                            row_stride=row_stride,
                            row_prefix_skip=row_prefix_skip,
                            rows=rows,
                            nonzero_columns=nonzero_columns,
                            segment=segment,
                            expected=expected,
                            context_bytes=context_bytes,
                            source_issues=issues,
                        )
                        fixture_candidates.append(row)
                        candidate_rows.append(row)
        best = max(fixture_candidates, key=sort_key) if fixture_candidates else {}
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
                "nonzero_columns": str(nonzero_columns),
                "row_count": str(len(rows)),
                "nonzero_slots": str(sum(len(row) for row in rows)),
                "payload_offsets": str(len(offset_reasons)),
                "candidate_count": str(len(fixture_candidates)),
                "best_payload_offset": best.get("payload_offset", ""),
                "best_source_mode": best.get("source_mode", ""),
                "best_row_stride": best.get("row_stride", ""),
                "best_row_prefix_skip": best.get("row_prefix_skip", ""),
                "best_prefix_bytes": best.get("prefix_bytes", "0"),
                "best_exact_bytes": best.get("exact_bytes", "0"),
                "full_match": best.get("full_match", "0"),
                "issues": ";".join(issues),
            }
        )

    best_rows = best_by_fixture(candidate_rows)
    return output_fixtures, candidate_rows, best_rows


def summary_row(
    fixture_rows: list[dict[str, str]],
    candidate_rows: list[dict[str, str]],
    best_rows: list[dict[str, str]],
) -> dict[str, str]:
    best = max(candidate_rows, key=sort_key) if candidate_rows else {}
    best_exact = (
        max(
            candidate_rows,
            key=lambda row: (
                int_value(row, "exact_bytes"),
                int_value(row, "prefix_bytes"),
                int(row.get("full_match", "0") or 0),
                -int_value(row, "payload_offset"),
                -int_value(row, "row_stride"),
                -int_value(row, "row_prefix_skip"),
            ),
        )
        if candidate_rows
        else {}
    )
    issue_rows = sum(1 for row in fixture_rows if row.get("issues"))
    return {
        "scope": "total",
        "fixture_rows": str(len(fixture_rows)),
        "candidate_rows": str(len(candidate_rows)),
        "source_modes": str(len({row.get("source_mode", "") for row in candidate_rows if row.get("source_mode")})),
        "payload_offsets": str(len({(fixture_key(row), row.get("payload_offset", "")) for row in candidate_rows})),
        "stride_values": str(len({row.get("row_stride", "") for row in candidate_rows if row.get("row_stride")})),
        "exact_match_rows": str(sum(1 for row in candidate_rows if row.get("full_match") == "1")),
        "exact_match_fixtures": str(sum(1 for row in best_rows if row.get("full_match") == "1")),
        "best_prefix_bytes": str(int_value(best, "prefix_bytes")),
        "best_exact_bytes": str(int_value(best_exact, "exact_bytes")),
        "best_rank": best.get("rank", ""),
        "best_pcx": best.get("pcx_name", ""),
        "best_frontier_id": best.get("frontier_id", ""),
        "best_payload_offset": best.get("payload_offset", ""),
        "best_source_mode": best.get("source_mode", ""),
        "best_row_stride": best.get("row_stride", ""),
        "best_row_prefix_skip": best.get("row_prefix_skip", ""),
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
        f"<td>{html.escape(row.get('nonzero_columns', ''))}</td>"
        f"<td>{html.escape(row.get('row_count', ''))}</td>"
        f"<td>{html.escape(row.get('payload_offsets', ''))}</td>"
        f"<td>{html.escape(row.get('candidate_count', ''))}</td>"
        f"<td>{html.escape(row.get('best_payload_offset', ''))}</td>"
        f"<td>{html.escape(row.get('best_row_stride', ''))}</td>"
        f"<td>{html.escape(row.get('best_row_prefix_skip', ''))}</td>"
        f"<td>{html.escape(row.get('best_prefix_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('best_exact_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('issues', ''))}</td>"
        "</tr>"
    )


def render_candidate_row(row: dict[str, str]) -> str:
    return (
        "<tr>"
        f"<td>{html.escape(row.get('rank', ''))}</td>"
        f"<td>{html.escape(row.get('pcx_name', ''))}</td>"
        f"<td>{html.escape(row.get('frontier_id', ''))}</td>"
        f"<td>{html.escape(row.get('payload_offset', ''))}</td>"
        f"<td>{html.escape(row.get('source_mode', ''))}</td>"
        f"<td>{html.escape(row.get('row_stride', ''))}</td>"
        f"<td>{html.escape(row.get('row_prefix_skip', ''))}</td>"
        f"<td>{html.escape(row.get('prefix_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('exact_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('full_match', ''))}</td>"
        f"<td>{html.escape(row.get('notes', ''))}</td>"
        "</tr>"
    )


def build_html(
    summary: dict[str, str],
    fixture_rows: list[dict[str, str]],
    candidate_rows: list[dict[str, str]],
    best_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "fixtures": fixture_rows, "best": best_rows, "candidates": candidate_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("fixtures.csv", output_dir / "fixtures.csv"),
            ("candidates.csv", output_dir / "candidates.csv"),
            ("best_by_fixture.csv", output_dir / "best_by_fixture.csv"),
        )
    )
    fixture_markup = "\n".join(render_fixture_row(row) for row in fixture_rows)
    top_candidates = sorted(candidate_rows, key=sort_key, reverse=True)[:160]
    candidate_markup = "\n".join(render_candidate_row(row) for row in top_candidates)
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
table {{ width: 100%; border-collapse: collapse; min-width: 1180px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Hypotheses de payload .tex organise par lignes: offset, stride et octets de controle par ligne.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Fixtures</div><div class="value">{html.escape(summary['fixture_rows'])}</div></div>
    <div class="stat"><div class="label">Candidates</div><div class="value">{html.escape(summary['candidate_rows'])}</div></div>
    <div class="stat"><div class="label">Payload offsets</div><div class="value">{html.escape(summary['payload_offsets'])}</div></div>
    <div class="stat"><div class="label">Best prefix</div><div class="value ok">{html.escape(summary['best_prefix_bytes'])}</div></div>
    <div class="stat"><div class="label">Best exact</div><div class="value ok">{html.escape(summary['best_exact_bytes'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div></section>
  <section class="panel">
    <h2>Fixtures</h2>
    <table>
      <thead><tr><th>Rank</th><th>Rule</th><th>PCX</th><th>Frontier</th><th>Size</th><th>Nonzero cols</th><th>Rows</th><th>Offsets</th><th>Candidates</th><th>Best offset</th><th>Stride</th><th>Prefix skip</th><th>Prefix</th><th>Exact</th><th>Issues</th></tr></thead>
      <tbody>{fixture_markup}</tbody>
    </table>
  </section>
  <section class="panel">
    <h2>Top candidates</h2>
    <table>
      <thead><tr><th>Rank</th><th>PCX</th><th>Frontier</th><th>Offset</th><th>Mode</th><th>Stride</th><th>Prefix skip</th><th>Prefix</th><th>Exact</th><th>Full</th><th>Notes</th></tr></thead>
      <tbody>{candidate_markup}</tbody>
    </table>
  </section>
</main>
<script>
const TEX_GAP_ROW_STRIDE_PROBE = {data_json};
</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    fixtures: Path,
    zero_run_fixtures: Path,
    header_blocks: Path,
    geometry_best: Path,
    *,
    limit: int,
    max_stride_extra: int,
    max_row_prefix_skip: int,
    context_bytes: int,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    fixture_rows, candidate_rows, best_rows = build_rows(
        fixtures,
        zero_run_fixtures,
        header_blocks,
        geometry_best,
        limit=limit,
        max_stride_extra=max_stride_extra,
        max_row_prefix_skip=max_row_prefix_skip,
        context_bytes=context_bytes,
    )
    summary = summary_row(fixture_rows, candidate_rows, best_rows)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "fixtures.csv", FIXTURE_FIELDNAMES, fixture_rows)
    write_csv(output_dir / "candidates.csv", CANDIDATE_FIELDNAMES, candidate_rows)
    write_csv(output_dir / "best_by_fixture.csv", BEST_FIELDNAMES, best_rows)
    (output_dir / "index.html").write_text(
        build_html(summary, fixture_rows, candidate_rows, best_rows, output_dir, title)
    )
    return summary, fixture_rows, candidate_rows, best_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe .tex gap row-stride payload layouts.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--zero-run-fixtures", type=Path, default=DEFAULT_ZERO_RUN_FIXTURES)
    parser.add_argument("--header-blocks", type=Path, default=DEFAULT_HEADER_BLOCKS)
    parser.add_argument("--geometry-best", type=Path, default=DEFAULT_GEOMETRY_BEST)
    parser.add_argument("--limit", type=int, default=32)
    parser.add_argument("--max-stride-extra", type=int, default=80)
    parser.add_argument("--max-row-prefix-skip", type=int, default=40)
    parser.add_argument("--context-bytes", type=int, default=32)
    parser.add_argument("--title", default="Lands of Lore II .tex Gap Row Stride Probe")
    args = parser.parse_args()

    summary, _fixture_rows, _candidate_rows, _best_rows = write_report(
        args.output,
        args.fixtures,
        args.zero_run_fixtures,
        args.header_blocks,
        args.geometry_best,
        limit=args.limit,
        max_stride_extra=args.max_stride_extra,
        max_row_prefix_skip=args.max_row_prefix_skip,
        context_bytes=args.context_bytes,
        title=args.title,
    )
    print(f"Fixture rows: {summary['fixture_rows']}")
    print(f"Candidate rows: {summary['candidate_rows']}")
    print(f"Payload offsets: {summary['payload_offsets']}")
    print(f"Best prefix bytes: {summary['best_prefix_bytes']}")
    print(f"Best exact bytes: {summary['best_exact_bytes']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
