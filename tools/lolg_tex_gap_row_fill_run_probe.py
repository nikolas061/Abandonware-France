#!/usr/bin/env python3
"""Probe row-local zero-fill plus literal-run grammar for .tex gaps."""

from __future__ import annotations

import argparse
import csv
import html
import json
from pathlib import Path

from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv
from lolg_tex_gap_row_delta_probe import build_row_geometry
from lolg_tex_gap_row_stride_probe import source_bytes


DEFAULT_OUTPUT = Path("output/tex_gap_row_fill_run_probe")
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_ZERO_RUN_FIXTURES = Path("output/tex_gap_zero_run_probe/fixtures.csv")
DEFAULT_CANDIDATES = Path("output/tex_gap_row_delta_probe/candidates.csv")
DEFAULT_ROW_DELTAS = Path("output/tex_gap_row_delta_probe/row_deltas.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "selected_candidates",
    "row_fill_rows",
    "fixtures",
    "min_literal_run",
    "search_before",
    "search_after",
    "literal_runs",
    "literal_bytes",
    "eligible_literal_runs",
    "eligible_literal_bytes",
    "sequential_literal_runs",
    "sequential_literal_bytes",
    "unordered_literal_runs",
    "unordered_literal_bytes",
    "full_sequential_literal_rows",
    "best_sequential_literal_bytes",
    "best_sequential_literal_ratio",
    "best_rank",
    "best_pcx",
    "best_frontier_id",
    "best_payload_offset",
    "best_source_mode",
    "issue_rows",
]

CANDIDATE_FIELDNAMES = [
    "selection_id",
    "rank",
    "rule_type",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "frontier_type",
    "payload_offset",
    "source_mode",
    "row_stride",
    "row_prefix_skip",
    "row_fill_rows",
    "literal_runs",
    "literal_bytes",
    "eligible_literal_runs",
    "eligible_literal_bytes",
    "sequential_literal_runs",
    "sequential_literal_bytes",
    "sequential_literal_ratio",
    "unordered_literal_runs",
    "unordered_literal_bytes",
    "full_sequential_literal_rows",
    "rows_with_any_sequential",
    "rows_with_unordered_only",
    "best_row_sequential_bytes",
    "worst_row_sequential_bytes",
    "issue_notes",
    "issues",
]

ROW_FIELDNAMES = [
    "selection_id",
    "rank",
    "pcx_name",
    "frontier_id",
    "row_index",
    "absolute_row",
    "row_start",
    "row_end",
    "payload_offset",
    "source_mode",
    "source_len",
    "anchor_source_start",
    "search_start",
    "search_end",
    "zero_runs",
    "zero_bytes",
    "literal_runs",
    "literal_bytes",
    "eligible_literal_runs",
    "eligible_literal_bytes",
    "sequential_literal_runs",
    "sequential_literal_bytes",
    "sequential_literal_ratio",
    "unordered_literal_runs",
    "unordered_literal_bytes",
    "full_sequential_literal_row",
    "first_missing_run_index",
    "max_source_gap_between_runs",
    "expected_row_head_hex",
    "search_window_head_hex",
    "issues",
]

RUN_FIELDNAMES = [
    "selection_id",
    "rank",
    "pcx_name",
    "frontier_id",
    "row_index",
    "run_index",
    "run_start",
    "run_end",
    "run_length",
    "run_head_hex",
    "sequential_match",
    "unordered_match",
    "source_match_start",
    "source_match_end",
    "source_gap_from_previous",
]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def fixture_key(row: dict[str, str]) -> tuple[str, str, str]:
    return (row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", ""))


def zero_key(row: dict[str, str]) -> tuple[str, str, str]:
    return (row.get("archive", ""), row.get("pcx_name", ""), row.get("frontier_id", ""))


def load_bytes(path_text: str, issues: list[str], label: str) -> bytes:
    if not path_text:
        issues.append(f"missing_{label}_path")
        return b""
    try:
        return Path(path_text).read_bytes()
    except OSError as exc:
        issues.append(f"read_{label}_failed:{exc}")
        return b""


def row_delta_lookup(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    return {
        (row.get("selection_id", ""), row.get("row_index", "")): row
        for row in rows
    }


def value_runs(data: bytes) -> list[tuple[str, int, int, bytes]]:
    runs: list[tuple[str, int, int, bytes]] = []
    if not data:
        return runs
    start = 0
    current_zero = data[0] == 0
    for index, value in enumerate(data[1:], start=1):
        is_zero = value == 0
        if is_zero != current_zero:
            kind = "zero" if current_zero else "literal"
            runs.append((kind, start, index, data[start:index]))
            start = index
            current_zero = is_zero
    kind = "zero" if current_zero else "literal"
    runs.append((kind, start, len(data), data[start:]))
    return runs


def find_bytes(haystack: bytes, needle: bytes, start: int, end: int) -> int:
    if not needle:
        return -1
    start = max(0, start)
    end = min(len(haystack), end)
    if end - start < len(needle):
        return -1
    return haystack.find(needle, start, end)


def analyze_row_runs(
    *,
    selection_id: str,
    candidate: dict[str, str],
    row: dict[str, object],
    row_index: int,
    row_expected: bytes,
    source: bytes,
    anchor_source_start: int,
    min_literal_run: int,
    search_before: int,
    search_after: int,
    context_bytes: int,
) -> tuple[dict[str, str], list[dict[str, str]]]:
    search_start = max(0, anchor_source_start - search_before)
    search_end = min(len(source), anchor_source_start + search_after)
    runs = value_runs(row_expected)
    literal_runs = [(start, end, data) for kind, start, end, data in runs if kind == "literal"]
    zero_runs = [(start, end, data) for kind, start, end, data in runs if kind == "zero"]
    eligible_runs = [
        (run_index, start, end, data)
        for run_index, (start, end, data) in enumerate(literal_runs)
        if len(data) >= min_literal_run
    ]

    current_search = search_start
    previous_end = search_start
    sequential_runs = 0
    sequential_bytes = 0
    unordered_runs = 0
    unordered_bytes = 0
    first_missing = ""
    max_gap = 0
    run_rows: list[dict[str, str]] = []

    for local_run_index, run_start, run_end, data in eligible_runs:
        sequential_start = find_bytes(source, data, current_search, search_end)
        unordered_start = find_bytes(source, data, search_start, search_end)
        matched_sequential = sequential_start >= 0
        matched_unordered = unordered_start >= 0
        source_start = sequential_start if matched_sequential else unordered_start
        source_end = source_start + len(data) if source_start >= 0 else -1
        source_gap = source_start - previous_end if matched_sequential else 0
        if matched_sequential:
            sequential_runs += 1
            sequential_bytes += len(data)
            max_gap = max(max_gap, max(0, source_gap))
            previous_end = source_end
            current_search = source_end
        elif first_missing == "":
            first_missing = str(local_run_index)
        if matched_unordered:
            unordered_runs += 1
            unordered_bytes += len(data)
        run_rows.append(
            {
                "selection_id": selection_id,
                "rank": candidate.get("rank", ""),
                "pcx_name": candidate.get("pcx_name", ""),
                "frontier_id": candidate.get("frontier_id", ""),
                "row_index": str(row_index),
                "run_index": str(local_run_index),
                "run_start": str(run_start),
                "run_end": str(run_end),
                "run_length": str(len(data)),
                "run_head_hex": data[:context_bytes].hex(),
                "sequential_match": "1" if matched_sequential else "0",
                "unordered_match": "1" if matched_unordered else "0",
                "source_match_start": "" if source_start < 0 else str(source_start),
                "source_match_end": "" if source_end < 0 else str(source_end),
                "source_gap_from_previous": str(source_gap) if matched_sequential else "",
            }
        )

    eligible_bytes = sum(len(data) for _run_index, _start, _end, data in eligible_runs)
    full_row = eligible_bytes > 0 and sequential_bytes == eligible_bytes
    row_row = {
        "selection_id": selection_id,
        "rank": candidate.get("rank", ""),
        "pcx_name": candidate.get("pcx_name", ""),
        "frontier_id": candidate.get("frontier_id", ""),
        "row_index": str(row_index),
        "absolute_row": str(row["absolute_row"]),
        "row_start": str(row["row_start"]),
        "row_end": str(row["row_end"]),
        "payload_offset": candidate.get("payload_offset", ""),
        "source_mode": candidate.get("source_mode", ""),
        "source_len": str(len(source)),
        "anchor_source_start": str(anchor_source_start),
        "search_start": str(search_start),
        "search_end": str(search_end),
        "zero_runs": str(len(zero_runs)),
        "zero_bytes": str(sum(len(data) for _start, _end, data in zero_runs)),
        "literal_runs": str(len(literal_runs)),
        "literal_bytes": str(sum(len(data) for _start, _end, data in literal_runs)),
        "eligible_literal_runs": str(len(eligible_runs)),
        "eligible_literal_bytes": str(eligible_bytes),
        "sequential_literal_runs": str(sequential_runs),
        "sequential_literal_bytes": str(sequential_bytes),
        "sequential_literal_ratio": f"{(sequential_bytes / eligible_bytes) if eligible_bytes else 0.0:.6f}",
        "unordered_literal_runs": str(unordered_runs),
        "unordered_literal_bytes": str(unordered_bytes),
        "full_sequential_literal_row": "1" if full_row else "0",
        "first_missing_run_index": first_missing,
        "max_source_gap_between_runs": str(max_gap),
        "expected_row_head_hex": row_expected[:context_bytes].hex(),
        "search_window_head_hex": source[search_start : min(search_end, search_start + context_bytes)].hex(),
        "issues": "",
    }
    return row_row, run_rows


def analyze_candidate(
    candidate: dict[str, str],
    fixture: dict[str, str],
    zero_fixture: dict[str, str],
    row_deltas: dict[tuple[str, str], dict[str, str]],
    *,
    min_literal_run: int,
    search_before: int,
    search_after: int,
    context_bytes: int,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    issues: list[str] = []
    notes: list[str] = []
    segment = load_bytes(fixture.get("segment_gap_path", ""), issues, "segment")
    expected = load_bytes(fixture.get("expected_gap_path", ""), issues, "expected")
    width = int_value(zero_fixture, "cdcache_width")
    zero_columns = int_value(zero_fixture, "leading_zero_bytes")
    rows = build_row_geometry(
        len(expected),
        gap_start=int_value(zero_fixture, "gap_start"),
        width=width,
        zero_columns=zero_columns,
    )
    try:
        source = source_bytes(segment, int_value(candidate, "payload_offset"), candidate.get("source_mode", "raw"))
    except ValueError as exc:
        source = b""
        issues.append(str(exc))

    selection_id = candidate.get("selection_id", "")
    row_rows: list[dict[str, str]] = []
    run_rows: list[dict[str, str]] = []
    for row_index, row in enumerate(rows):
        delta_row = row_deltas.get((selection_id, str(row_index)), {})
        if not delta_row:
            notes.append("missing_row_delta")
        row_start = int(row["row_start"])  # type: ignore[arg-type]
        row_end = int(row["row_end"])  # type: ignore[arg-type]
        row_row, runs = analyze_row_runs(
            selection_id=selection_id,
            candidate=candidate,
            row=row,
            row_index=row_index,
            row_expected=expected[row_start:row_end],
            source=source,
            anchor_source_start=int_value(delta_row, "best_source_start") if delta_row else 0,
            min_literal_run=min_literal_run,
            search_before=search_before,
            search_after=search_after,
            context_bytes=context_bytes,
        )
        row_rows.append(row_row)
        run_rows.extend(runs)

    eligible_bytes = sum(int_value(row, "eligible_literal_bytes") for row in row_rows)
    sequential_bytes = sum(int_value(row, "sequential_literal_bytes") for row in row_rows)
    if sequential_bytes == 0:
        notes.append("no_sequential_literal_runs")
    candidate_row = {
        "selection_id": selection_id,
        "rank": candidate.get("rank", ""),
        "rule_type": candidate.get("rule_type", ""),
        "archive": candidate.get("archive", ""),
        "archive_tag": candidate.get("archive_tag", ""),
        "pcx_name": candidate.get("pcx_name", ""),
        "frontier_id": candidate.get("frontier_id", ""),
        "frontier_type": candidate.get("frontier_type", ""),
        "payload_offset": candidate.get("payload_offset", ""),
        "source_mode": candidate.get("source_mode", ""),
        "row_stride": candidate.get("row_stride", ""),
        "row_prefix_skip": candidate.get("row_prefix_skip", ""),
        "row_fill_rows": str(len(row_rows)),
        "literal_runs": str(sum(int_value(row, "literal_runs") for row in row_rows)),
        "literal_bytes": str(sum(int_value(row, "literal_bytes") for row in row_rows)),
        "eligible_literal_runs": str(sum(int_value(row, "eligible_literal_runs") for row in row_rows)),
        "eligible_literal_bytes": str(eligible_bytes),
        "sequential_literal_runs": str(sum(int_value(row, "sequential_literal_runs") for row in row_rows)),
        "sequential_literal_bytes": str(sequential_bytes),
        "sequential_literal_ratio": f"{(sequential_bytes / eligible_bytes) if eligible_bytes else 0.0:.6f}",
        "unordered_literal_runs": str(sum(int_value(row, "unordered_literal_runs") for row in row_rows)),
        "unordered_literal_bytes": str(sum(int_value(row, "unordered_literal_bytes") for row in row_rows)),
        "full_sequential_literal_rows": str(sum(int_value(row, "full_sequential_literal_row") for row in row_rows)),
        "rows_with_any_sequential": str(sum(1 for row in row_rows if int_value(row, "sequential_literal_runs") > 0)),
        "rows_with_unordered_only": str(
            sum(
                1
                for row in row_rows
                if int_value(row, "sequential_literal_runs") == 0 and int_value(row, "unordered_literal_runs") > 0
            )
        ),
        "best_row_sequential_bytes": str(max([int_value(row, "sequential_literal_bytes") for row in row_rows] or [0])),
        "worst_row_sequential_bytes": str(min([int_value(row, "sequential_literal_bytes") for row in row_rows] or [0])),
        "issue_notes": ";".join(sorted(set(notes))),
        "issues": ";".join(issues),
    }
    return candidate_row, row_rows, run_rows


def build_rows(
    fixtures: Path,
    zero_run_fixtures: Path,
    candidates: Path,
    row_deltas: Path,
    *,
    min_literal_run: int,
    search_before: int,
    search_after: int,
    context_bytes: int,
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    fixtures_by_key = {fixture_key(row): row for row in read_rows(fixtures)}
    zero_by_key = {zero_key(row): row for row in read_rows(zero_run_fixtures)}
    deltas = row_delta_lookup(read_rows(row_deltas))
    candidate_rows: list[dict[str, str]] = []
    row_rows: list[dict[str, str]] = []
    run_rows: list[dict[str, str]] = []
    for candidate in read_rows(candidates):
        key = fixture_key(candidate)
        zero_fixture = zero_by_key.get(
            (candidate.get("archive", ""), candidate.get("pcx_name", ""), candidate.get("frontier_id", "")),
            {},
        )
        analyzed, rows, runs = analyze_candidate(
            candidate,
            fixtures_by_key.get(key, {}),
            zero_fixture,
            deltas,
            min_literal_run=min_literal_run,
            search_before=search_before,
            search_after=search_after,
            context_bytes=context_bytes,
        )
        candidate_rows.append(analyzed)
        row_rows.extend(rows)
        run_rows.extend(runs)
    return candidate_rows, row_rows, run_rows


def summary_row(
    candidate_rows: list[dict[str, str]],
    row_rows: list[dict[str, str]],
    *,
    min_literal_run: int,
    search_before: int,
    search_after: int,
) -> dict[str, str]:
    best = (
        max(
            candidate_rows,
            key=lambda row: (
                int_value(row, "sequential_literal_bytes"),
                int_value(row, "full_sequential_literal_rows"),
                int_value(row, "unordered_literal_bytes"),
            ),
        )
        if candidate_rows
        else {}
    )
    best_bytes = int_value(best, "sequential_literal_bytes")
    best_eligible = int_value(best, "eligible_literal_bytes")
    return {
        "scope": "total",
        "selected_candidates": str(len(candidate_rows)),
        "row_fill_rows": str(len(row_rows)),
        "fixtures": str(len({fixture_key(row) for row in candidate_rows})),
        "min_literal_run": str(min_literal_run),
        "search_before": str(search_before),
        "search_after": str(search_after),
        "literal_runs": str(sum(int_value(row, "literal_runs") for row in candidate_rows)),
        "literal_bytes": str(sum(int_value(row, "literal_bytes") for row in candidate_rows)),
        "eligible_literal_runs": str(sum(int_value(row, "eligible_literal_runs") for row in candidate_rows)),
        "eligible_literal_bytes": str(sum(int_value(row, "eligible_literal_bytes") for row in candidate_rows)),
        "sequential_literal_runs": str(sum(int_value(row, "sequential_literal_runs") for row in candidate_rows)),
        "sequential_literal_bytes": str(sum(int_value(row, "sequential_literal_bytes") for row in candidate_rows)),
        "unordered_literal_runs": str(sum(int_value(row, "unordered_literal_runs") for row in candidate_rows)),
        "unordered_literal_bytes": str(sum(int_value(row, "unordered_literal_bytes") for row in candidate_rows)),
        "full_sequential_literal_rows": str(
            sum(int_value(row, "full_sequential_literal_rows") for row in candidate_rows)
        ),
        "best_sequential_literal_bytes": str(best_bytes),
        "best_sequential_literal_ratio": f"{(best_bytes / best_eligible) if best_eligible else 0.0:.6f}",
        "best_rank": best.get("rank", ""),
        "best_pcx": best.get("pcx_name", ""),
        "best_frontier_id": best.get("frontier_id", ""),
        "best_payload_offset": best.get("payload_offset", ""),
        "best_source_mode": best.get("source_mode", ""),
        "issue_rows": str(sum(1 for row in candidate_rows if row.get("issues"))),
    }


def render_candidate_row(row: dict[str, str]) -> str:
    return (
        "<tr>"
        f"<td>{html.escape(row.get('selection_id', ''))}</td>"
        f"<td>{html.escape(row.get('pcx_name', ''))}</td>"
        f"<td>{html.escape(row.get('frontier_id', ''))}</td>"
        f"<td>{html.escape(row.get('source_mode', ''))}</td>"
        f"<td>{html.escape(row.get('eligible_literal_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('sequential_literal_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('sequential_literal_ratio', ''))}</td>"
        f"<td>{html.escape(row.get('unordered_literal_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('full_sequential_literal_rows', ''))}</td>"
        f"<td>{html.escape(row.get('rows_with_any_sequential', ''))}</td>"
        f"<td>{html.escape(row.get('issue_notes', ''))}</td>"
        f"<td>{html.escape(row.get('issues', ''))}</td>"
        "</tr>"
    )


def render_row_fill(row: dict[str, str]) -> str:
    return (
        "<tr>"
        f"<td>{html.escape(row.get('selection_id', ''))}</td>"
        f"<td>{html.escape(row.get('row_index', ''))}</td>"
        f"<td>{html.escape(row.get('anchor_source_start', ''))}</td>"
        f"<td>{html.escape(row.get('eligible_literal_runs', ''))}</td>"
        f"<td>{html.escape(row.get('eligible_literal_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('sequential_literal_runs', ''))}</td>"
        f"<td>{html.escape(row.get('sequential_literal_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('sequential_literal_ratio', ''))}</td>"
        f"<td>{html.escape(row.get('unordered_literal_runs', ''))}</td>"
        f"<td>{html.escape(row.get('max_source_gap_between_runs', ''))}</td>"
        f"<td><code>{html.escape(row.get('expected_row_head_hex', ''))}</code></td>"
        f"<td><code>{html.escape(row.get('search_window_head_hex', ''))}</code></td>"
        "</tr>"
    )


def render_run_match(row: dict[str, str]) -> str:
    return (
        "<tr>"
        f"<td>{html.escape(row.get('selection_id', ''))}</td>"
        f"<td>{html.escape(row.get('row_index', ''))}</td>"
        f"<td>{html.escape(row.get('run_index', ''))}</td>"
        f"<td>{html.escape(row.get('run_start', ''))}</td>"
        f"<td>{html.escape(row.get('run_length', ''))}</td>"
        f"<td>{html.escape(row.get('sequential_match', ''))}</td>"
        f"<td>{html.escape(row.get('unordered_match', ''))}</td>"
        f"<td>{html.escape(row.get('source_match_start', ''))}</td>"
        f"<td>{html.escape(row.get('source_gap_from_previous', ''))}</td>"
        f"<td><code>{html.escape(row.get('run_head_hex', ''))}</code></td>"
        "</tr>"
    )


def build_html(
    summary: dict[str, str],
    candidate_rows: list[dict[str, str]],
    row_rows: list[dict[str, str]],
    run_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "candidates": candidate_rows, "rowFills": row_rows, "runMatches": run_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("candidates.csv", output_dir / "candidates.csv"),
            ("row_fills.csv", output_dir / "row_fills.csv"),
            ("run_matches.csv", output_dir / "run_matches.csv"),
        )
    )
    candidate_markup = "\n".join(
        render_candidate_row(row)
        for row in sorted(candidate_rows, key=lambda row: int_value(row, "sequential_literal_bytes"), reverse=True)
    )
    top_rows = sorted(
        row_rows,
        key=lambda row: (int_value(row, "sequential_literal_bytes"), int_value(row, "unordered_literal_bytes")),
        reverse=True,
    )[:180]
    row_markup = "\n".join(render_row_fill(row) for row in top_rows)
    top_runs = sorted(
        run_rows,
        key=lambda row: (int_value(row, "sequential_match"), int_value(row, "run_length")),
        reverse=True,
    )[:220]
    run_markup = "\n".join(render_run_match(row) for row in top_runs)
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
header {{ border-bottom: 1px solid var(--line); background: #12171b; padding: 18px 0 14px; }}
h1 {{ margin: 0; font-size: 21px; font-weight: 700; letter-spacing: 0; }}
h2 {{ margin: 0 0 10px; font-size: 16px; }}
.sub {{ color: var(--muted); margin-top: 4px; }}
main {{ padding: 16px 0 28px; display: grid; gap: 16px; }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; }}
.stat, .panel {{ border: 1px solid var(--line); border-radius: 8px; background: var(--panel); padding: 10px; }}
.label, .muted {{ color: var(--muted); }}
.value {{ font-size: 24px; font-weight: 750; line-height: 1.05; margin-top: 4px; }}
.ok {{ color: var(--ok); }}
.panel {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; min-width: 1320px; }}
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
    <div class="sub">Runs litteraux ordonnes autour du start candidat, pour tester une grammaire zero-fill/copy.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Candidates</div><div class="value">{html.escape(summary['selected_candidates'])}</div></div>
    <div class="stat"><div class="label">Row fills</div><div class="value">{html.escape(summary['row_fill_rows'])}</div></div>
    <div class="stat"><div class="label">Seq bytes</div><div class="value ok">{html.escape(summary['sequential_literal_bytes'])}</div></div>
    <div class="stat"><div class="label">Best seq</div><div class="value ok">{html.escape(summary['best_sequential_literal_bytes'])}</div></div>
    <div class="stat"><div class="label">Full rows</div><div class="value">{html.escape(summary['full_sequential_literal_rows'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div></section>
  <section class="panel">
    <h2>Candidates</h2>
    <table>
      <thead><tr><th>ID</th><th>PCX</th><th>Frontier</th><th>Mode</th><th>Eligible bytes</th><th>Seq bytes</th><th>Seq ratio</th><th>Unordered bytes</th><th>Full rows</th><th>Rows any seq</th><th>Notes</th><th>Issues</th></tr></thead>
      <tbody>{candidate_markup}</tbody>
    </table>
  </section>
  <section class="panel">
    <h2>Top row fills</h2>
    <table>
      <thead><tr><th>ID</th><th>Row</th><th>Anchor</th><th>Eligible runs</th><th>Eligible bytes</th><th>Seq runs</th><th>Seq bytes</th><th>Seq ratio</th><th>Unordered runs</th><th>Max gap</th><th>Expected</th><th>Window</th></tr></thead>
      <tbody>{row_markup}</tbody>
    </table>
  </section>
  <section class="panel">
    <h2>Top run matches</h2>
    <table>
      <thead><tr><th>ID</th><th>Row</th><th>Run</th><th>Run start</th><th>Length</th><th>Seq</th><th>Any</th><th>Source start</th><th>Gap</th><th>Bytes</th></tr></thead>
      <tbody>{run_markup}</tbody>
    </table>
  </section>
</main>
<script>
const TEX_GAP_ROW_FILL_RUN_PROBE = {data_json};
</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    fixtures: Path,
    zero_run_fixtures: Path,
    candidates: Path,
    row_deltas: Path,
    *,
    min_literal_run: int,
    search_before: int,
    search_after: int,
    context_bytes: int,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    candidate_rows, row_rows, run_rows = build_rows(
        fixtures,
        zero_run_fixtures,
        candidates,
        row_deltas,
        min_literal_run=min_literal_run,
        search_before=search_before,
        search_after=search_after,
        context_bytes=context_bytes,
    )
    summary = summary_row(
        candidate_rows,
        row_rows,
        min_literal_run=min_literal_run,
        search_before=search_before,
        search_after=search_after,
    )
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "candidates.csv", CANDIDATE_FIELDNAMES, candidate_rows)
    write_csv(output_dir / "row_fills.csv", ROW_FIELDNAMES, row_rows)
    write_csv(output_dir / "run_matches.csv", RUN_FIELDNAMES, run_rows)
    (output_dir / "index.html").write_text(
        build_html(summary, candidate_rows, row_rows, run_rows, output_dir, title)
    )
    return summary, candidate_rows, row_rows, run_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe row-local zero-fill/literal-run .tex gap grammar.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--zero-run-fixtures", type=Path, default=DEFAULT_ZERO_RUN_FIXTURES)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--row-deltas", type=Path, default=DEFAULT_ROW_DELTAS)
    parser.add_argument("--min-literal-run", type=int, default=3)
    parser.add_argument("--search-before", type=int, default=64)
    parser.add_argument("--search-after", type=int, default=512)
    parser.add_argument("--context-bytes", type=int, default=24)
    parser.add_argument("--title", default="Lands of Lore II .tex Gap Row Fill Run Probe")
    args = parser.parse_args()

    summary, _candidate_rows, _row_rows, _run_rows = write_report(
        args.output,
        args.fixtures,
        args.zero_run_fixtures,
        args.candidates,
        args.row_deltas,
        min_literal_run=args.min_literal_run,
        search_before=args.search_before,
        search_after=args.search_after,
        context_bytes=args.context_bytes,
        title=args.title,
    )
    print(f"Selected candidates: {summary['selected_candidates']}")
    print(f"Row fill rows: {summary['row_fill_rows']}")
    print(f"Sequential literal bytes: {summary['sequential_literal_bytes']}")
    print(f"Best sequential literal bytes: {summary['best_sequential_literal_bytes']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
