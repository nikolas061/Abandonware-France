#!/usr/bin/env python3
"""Profile peer low-row transforms after the Frontier80 low-payload corpus scan."""

from __future__ import annotations

import argparse
import html
import json
from collections import Counter
from pathlib import Path

from lolg_tex_gap_decoder_frontier80_context_split_residual_low_payload_neighborhood_probe import (
    TARGET_FIELDNAMES,
    fixture_key,
    load_target_runs,
    low_target_rows,
    read_csv,
    signed_delta,
    target_row_record,
)
from lolg_tex_gap_opcode_probe import int_value, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_frontier80_context_split_residual_low_payload_role_pair_transform_probe")
DEFAULT_RUNS = Path("output/tex_gap_decoder_unresolved_run_probe_frontier80_context_split_residual_second_replay/runs.csv")
DEFAULT_MANIFEST = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_CLEAN_FIXTURES = Path(
    "output/tex_gap_decoder_frontier80_context_split_residual_second_fixture_replay/fixtures.csv"
)
DEFAULT_CORPUS_CANDIDATES = Path(
    "output/tex_gap_decoder_frontier80_context_split_residual_low_payload_corpus_source_probe/candidates.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "target_runs",
    "target_rows",
    "target_bytes",
    "low1_target_rows",
    "low2_target_rows",
    "source_window_rows",
    "candidate_rows",
    "low1_candidate_rows",
    "low2_candidate_rows",
    "strong_pair_candidate_rows",
    "relaxed_pair_candidate_rows",
    "low1_rows_with_strong_pair",
    "low2_rows_with_strong_pair",
    "low1_rows_with_relaxed_pair",
    "low2_rows_with_relaxed_pair",
    "best_low1_small_delta_le2_min",
    "best_low2_small_delta_le2_min",
    "best_low2_small_delta_le4_min",
    "best_candidate_target",
    "best_candidate_role",
    "best_candidate_source_target",
    "best_candidate_source_role",
    "best_candidate_source_delta",
    "best_candidate_exact_bytes",
    "best_candidate_small_delta_le2_bytes",
    "best_candidate_small_delta_le4_bytes",
    "source_known_min",
    "corpus_candidate_rows",
    "corpus_candidate_source_overlaps_low_rows",
    "corpus_candidate_source_dominant_low1_rows",
    "corpus_candidate_source_dominant_low2_rows",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

CANDIDATE_FIELDNAMES = [
    "target_id",
    "row_role",
    "target_rank",
    "target_frontier_id",
    "target_start",
    "source_target_id",
    "source_row_role",
    "source_rank",
    "source_frontier_id",
    "source_row_start",
    "source_start",
    "source_row_delta",
    "source_overlap_target_id",
    "source_overlap_role",
    "source_overlap_bytes",
    "source_overlap_delta",
    "same_fixture",
    "source_known_bytes",
    "strong_pair",
    "relaxed_pair",
    "exact_bytes",
    "small_delta_le1_bytes",
    "small_delta_le2_bytes",
    "small_delta_le4_bytes",
    "mean_abs_delta",
    "top_delta",
    "top_delta_count",
    "source_head_hex",
    "target_head_hex",
]

COVERAGE_FIELDNAMES = [
    "target_id",
    "row_role",
    "target_rank",
    "target_frontier_id",
    "target_start",
    "candidate_rows",
    "strong_pair_candidate_rows",
    "relaxed_pair_candidate_rows",
    "best_exact_bytes",
    "best_small_delta_le2_bytes",
    "best_small_delta_le4_bytes",
    "best_source_known_bytes",
    "best_source_target_id",
    "best_source_row_role",
    "best_source_row_delta",
    "best_source_overlap_role",
    "best_source_overlap_delta",
]

SOURCE_OVERLAP_FIELDNAMES = [
    "target_id",
    "row_role",
    "target_start",
    "source_rank",
    "source_pcx_name",
    "source_frontier_id",
    "source_start",
    "overlap_target_id",
    "overlap_row_role",
    "overlap_bytes",
    "overlap_delta",
    "overlap_low1_bytes",
    "overlap_low2_bytes",
    "exact_bytes",
    "small_delta_le2_bytes",
    "small_delta_le4_bytes",
]

SOURCE_WINDOW_FIELDNAMES = [
    "source_target_id",
    "source_row_role",
    "source_rank",
    "source_frontier_id",
    "source_row_start",
    "source_start",
    "source_row_delta",
    "source_known_bytes",
    "source_head_hex",
]


def row_target(row: dict[str, object]) -> dict[str, str]:
    target = row["target"]
    assert isinstance(target, dict)
    return target


def row_bytes(row: dict[str, object]) -> bytes:
    data = row["data"]
    assert isinstance(data, bytes)
    return data


def overlap_bytes(start: int, end: int, other_start: int, other_end: int) -> int:
    return max(0, min(end, other_end) - max(start, other_start))


def best_low_overlap(
    target_rows: list[dict[str, object]],
    source_fixture: tuple[str, str, str],
    source_start: int,
) -> dict[str, str]:
    source_end = source_start + 32
    best: dict[str, str] = {
        "overlap_target_id": "",
        "overlap_row_role": "",
        "overlap_bytes": "0",
        "overlap_delta": "",
        "overlap_low1_bytes": "0",
        "overlap_low2_bytes": "0",
    }
    low1_total = 0
    low2_total = 0
    for row in target_rows:
        target = row_target(row)
        if fixture_key(target) != source_fixture:
            continue
        row_start = int(row["row_start"])
        row_end = int(row["row_end"])
        overlap = overlap_bytes(source_start, source_end, row_start, row_end)
        if row.get("row_role") == "low1":
            low1_total += overlap
        elif row.get("row_role") == "low2":
            low2_total += overlap
        current = int_value(best, "overlap_bytes")
        if overlap > current:
            best.update(
                {
                    "overlap_target_id": target.get("target_id", ""),
                    "overlap_row_role": str(row.get("row_role", "")),
                    "overlap_bytes": str(overlap),
                    "overlap_delta": str(source_start - row_start),
                }
            )
    best["overlap_low1_bytes"] = str(low1_total)
    best["overlap_low2_bytes"] = str(low2_total)
    return best


def delta_stats(source: bytes, target: bytes) -> dict[str, str]:
    deltas = [signed_delta(source_value, target_value) for source_value, target_value in zip(source, target)]
    abs_deltas = [abs(delta) for delta in deltas]
    top_delta, top_delta_count = Counter(deltas).most_common(1)[0]
    return {
        "exact_bytes": str(sum(1 for delta in deltas if delta == 0)),
        "small_delta_le1_bytes": str(sum(1 for delta in abs_deltas if delta <= 1)),
        "small_delta_le2_bytes": str(sum(1 for delta in abs_deltas if delta <= 2)),
        "small_delta_le4_bytes": str(sum(1 for delta in abs_deltas if delta <= 4)),
        "mean_abs_delta": f"{sum(abs_deltas) / len(abs_deltas):.6f}",
        "top_delta": str(top_delta),
        "top_delta_count": str(top_delta_count),
    }


def is_strong_pair(stats: dict[str, str]) -> bool:
    return int_value(stats, "small_delta_le2_bytes") >= 18 or int_value(stats, "exact_bytes") >= 8


def is_relaxed_pair(stats: dict[str, str]) -> bool:
    return (
        int_value(stats, "small_delta_le2_bytes") >= 14
        or int_value(stats, "small_delta_le4_bytes") >= 18
        or int_value(stats, "exact_bytes") >= 6
    )


def source_window_rows(
    target_rows: list[dict[str, object]],
    delta_min: int,
    delta_max: int,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for source_row in target_rows:
        source_target = row_target(source_row)
        expected = source_row["expected"]
        known_mask = source_row["known_mask"]
        assert isinstance(expected, bytes)
        assert isinstance(known_mask, bytes)
        source_row_start = int(source_row["row_start"])
        for source_delta in range(delta_min, delta_max + 1):
            source_start = source_row_start + source_delta
            source = expected[source_start : source_start + 32]
            known = known_mask[source_start : source_start + 32]
            if len(source) != 32:
                continue
            rows.append(
                {
                    "source_row": source_row,
                    "source_target": source_target,
                    "source_start": source_start,
                    "source_row_delta": source_delta,
                    "source": source,
                    "known": known,
                    "record": {
                        "source_target_id": source_target.get("target_id", ""),
                        "source_row_role": str(source_row.get("row_role", "")),
                        "source_rank": source_target.get("rank", ""),
                        "source_frontier_id": source_target.get("frontier_id", ""),
                        "source_row_start": str(source_row_start),
                        "source_start": str(source_start),
                        "source_row_delta": str(source_delta),
                        "source_known_bytes": str(sum(1 for value in known if value)),
                        "source_head_hex": source[:16].hex(),
                    },
                }
            )
    return rows


def build_candidates(
    target_rows: list[dict[str, object]],
    sources: list[dict[str, object]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for target_row in target_rows:
        target = row_target(target_row)
        target_data = row_bytes(target_row)
        target_start = int(target_row["row_start"])
        for source_window in sources:
            source_target = source_window["source_target"]
            source = source_window["source"]
            known = source_window["known"]
            assert isinstance(source_target, dict)
            assert isinstance(source, bytes)
            assert isinstance(known, bytes)
            source_start = int(source_window["source_start"])
            same_fixture = fixture_key(target) == fixture_key(source_target)
            if same_fixture and max(source_start, target_start) < min(source_start + 32, target_start + 32):
                continue
            stats = delta_stats(source, target_data)
            if not is_relaxed_pair(stats):
                continue
            overlap = best_low_overlap(target_rows, fixture_key(source_target), source_start)
            strong = is_strong_pair(stats)
            relaxed = is_relaxed_pair(stats)
            rows.append(
                {
                    "target_id": target.get("target_id", ""),
                    "row_role": str(target_row.get("row_role", "")),
                    "target_rank": target.get("rank", ""),
                    "target_frontier_id": target.get("frontier_id", ""),
                    "target_start": str(target_start),
                    "source_target_id": source_target.get("target_id", ""),
                    "source_row_role": str(source_window["source_row"].get("row_role", "")),
                    "source_rank": source_target.get("rank", ""),
                    "source_frontier_id": source_target.get("frontier_id", ""),
                    "source_row_start": str(source_window["source_row"].get("row_start", "")),
                    "source_start": str(source_start),
                    "source_row_delta": str(source_window["source_row_delta"]),
                    "source_overlap_target_id": overlap.get("overlap_target_id", ""),
                    "source_overlap_role": overlap.get("overlap_row_role", ""),
                    "source_overlap_bytes": overlap.get("overlap_bytes", "0"),
                    "source_overlap_delta": overlap.get("overlap_delta", ""),
                    "same_fixture": "1" if same_fixture else "0",
                    "source_known_bytes": str(sum(1 for value in known if value)),
                    "strong_pair": "1" if strong else "0",
                    "relaxed_pair": "1" if relaxed else "0",
                    **stats,
                    "source_head_hex": source[:16].hex(),
                    "target_head_hex": target_data[:16].hex(),
                }
            )
    rows.sort(
        key=lambda row: (
            row.get("row_role", ""),
            row.get("target_id", ""),
            -int_value(row, "strong_pair"),
            -int_value(row, "small_delta_le2_bytes"),
            -int_value(row, "exact_bytes"),
            -int_value(row, "small_delta_le4_bytes"),
        )
    )
    return rows


def best_by_target(candidate_rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    best: dict[tuple[str, str], dict[str, str]] = {}
    for row in candidate_rows:
        key = row.get("target_id", ""), row.get("row_role", "")
        current = best.get(key)
        if current is None:
            best[key] = row
            continue
        if (
            int_value(row, "strong_pair"),
            int_value(row, "small_delta_le2_bytes"),
            int_value(row, "exact_bytes"),
            int_value(row, "small_delta_le4_bytes"),
        ) > (
            int_value(current, "strong_pair"),
            int_value(current, "small_delta_le2_bytes"),
            int_value(current, "exact_bytes"),
            int_value(current, "small_delta_le4_bytes"),
        ):
            best[key] = row
    return best


def build_coverage(
    target_rows: list[dict[str, object]],
    candidate_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    by_key: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in candidate_rows:
        by_key.setdefault((row.get("target_id", ""), row.get("row_role", "")), []).append(row)
    best = best_by_target(candidate_rows)
    rows: list[dict[str, str]] = []
    for target_row in target_rows:
        target = row_target(target_row)
        key = target.get("target_id", ""), str(target_row.get("row_role", ""))
        candidates = by_key.get(key, [])
        best_row = best.get(key, {})
        rows.append(
            {
                "target_id": key[0],
                "row_role": key[1],
                "target_rank": target.get("rank", ""),
                "target_frontier_id": target.get("frontier_id", ""),
                "target_start": str(target_row["row_start"]),
                "candidate_rows": str(len(candidates)),
                "strong_pair_candidate_rows": str(sum(int_value(row, "strong_pair") for row in candidates)),
                "relaxed_pair_candidate_rows": str(sum(int_value(row, "relaxed_pair") for row in candidates)),
                "best_exact_bytes": best_row.get("exact_bytes", "0"),
                "best_small_delta_le2_bytes": best_row.get("small_delta_le2_bytes", "0"),
                "best_small_delta_le4_bytes": best_row.get("small_delta_le4_bytes", "0"),
                "best_source_known_bytes": best_row.get("source_known_bytes", "0"),
                "best_source_target_id": best_row.get("source_target_id", ""),
                "best_source_row_role": best_row.get("source_row_role", ""),
                "best_source_row_delta": best_row.get("source_row_delta", ""),
                "best_source_overlap_role": best_row.get("source_overlap_role", ""),
                "best_source_overlap_delta": best_row.get("source_overlap_delta", ""),
            }
        )
    rows.sort(key=lambda row: (row.get("row_role", ""), row.get("target_id", "")))
    return rows


def build_corpus_source_overlaps(
    corpus_candidates: list[dict[str, str]],
    target_rows: list[dict[str, object]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for candidate in corpus_candidates:
        source_fixture = (
            candidate.get("source_rank", ""),
            candidate.get("source_pcx_name", ""),
            candidate.get("source_frontier_id", ""),
        )
        source_start = int_value(candidate, "source_start")
        overlap = best_low_overlap(target_rows, source_fixture, source_start)
        rows.append(
            {
                "target_id": candidate.get("target_id", ""),
                "row_role": candidate.get("row_role", ""),
                "target_start": candidate.get("target_start", ""),
                "source_rank": candidate.get("source_rank", ""),
                "source_pcx_name": candidate.get("source_pcx_name", ""),
                "source_frontier_id": candidate.get("source_frontier_id", ""),
                "source_start": candidate.get("source_start", ""),
                "overlap_target_id": overlap.get("overlap_target_id", ""),
                "overlap_row_role": overlap.get("overlap_row_role", ""),
                "overlap_bytes": overlap.get("overlap_bytes", "0"),
                "overlap_delta": overlap.get("overlap_delta", ""),
                "overlap_low1_bytes": overlap.get("overlap_low1_bytes", "0"),
                "overlap_low2_bytes": overlap.get("overlap_low2_bytes", "0"),
                "exact_bytes": candidate.get("exact_bytes", "0"),
                "small_delta_le2_bytes": candidate.get("small_delta_le2_bytes", "0"),
                "small_delta_le4_bytes": candidate.get("small_delta_le4_bytes", "0"),
            }
        )
    rows.sort(
        key=lambda row: (
            row.get("target_id", ""),
            -int_value(row, "overlap_bytes"),
            row.get("source_rank", ""),
            int_value(row, "source_start"),
        )
    )
    return rows


def min_best(rows: list[dict[str, str]], field: str) -> int:
    values = [int_value(row, field) for row in rows if int_value(row, "candidate_rows") > 0]
    return min(values, default=0)


def build_summary(
    *,
    target_runs: int,
    target_rows: list[dict[str, object]],
    source_windows: list[dict[str, object]],
    candidate_rows: list[dict[str, str]],
    coverage_rows: list[dict[str, str]],
    corpus_overlap_rows: list[dict[str, str]],
    issues: list[str],
) -> dict[str, str]:
    low1_coverage = [row for row in coverage_rows if row.get("row_role") == "low1"]
    low2_coverage = [row for row in coverage_rows if row.get("row_role") == "low2"]
    low1_rows = len(low1_coverage)
    low2_rows = len(low2_coverage)
    low1_strong = sum(1 for row in low1_coverage if int_value(row, "strong_pair_candidate_rows") > 0)
    low2_strong = sum(1 for row in low2_coverage if int_value(row, "strong_pair_candidate_rows") > 0)
    low1_relaxed = sum(1 for row in low1_coverage if int_value(row, "relaxed_pair_candidate_rows") > 0)
    low2_relaxed = sum(1 for row in low2_coverage if int_value(row, "relaxed_pair_candidate_rows") > 0)
    best = sorted(
        candidate_rows,
        key=lambda row: (
            -int_value(row, "strong_pair"),
            -int_value(row, "small_delta_le2_bytes"),
            -int_value(row, "exact_bytes"),
            -int_value(row, "small_delta_le4_bytes"),
        ),
    )
    best_row = best[0] if best else {}
    known_values = [int_value(row, "source_known_bytes") for row in candidate_rows]
    corpus_low_overlap = sum(1 for row in corpus_overlap_rows if int_value(row, "overlap_bytes") > 0)
    corpus_low1_overlap = sum(1 for row in corpus_overlap_rows if row.get("overlap_row_role") == "low1")
    corpus_low2_overlap = sum(1 for row in corpus_overlap_rows if row.get("overlap_row_role") == "low2")

    if low1_strong == low1_rows and low2_relaxed == low2_rows and low2_strong == 0:
        verdict = "frontier80_context_residual_low_payload_role_pair_low2_relaxed_self_reference"
        next_probe = "derive non-oracle row-role transform selector for low-payload residual rows"
    elif low1_strong == low1_rows:
        verdict = "frontier80_context_residual_low_payload_role_pair_low1_self_reference"
        next_probe = "broaden low2 row-role transform thresholds around peer low rows"
    elif low2_relaxed == low2_rows:
        verdict = "frontier80_context_residual_low_payload_role_pair_low2_relaxed_signal"
        next_probe = "resolve low1 row-role source identity before promotion"
    else:
        verdict = "frontier80_context_residual_low_payload_role_pair_weak_signal"
        next_probe = "profile opcode/control context for low-payload residual rows"

    return {
        "scope": "total",
        "target_runs": str(target_runs),
        "target_rows": str(len(target_rows)),
        "target_bytes": str(len(target_rows) * 32),
        "low1_target_rows": str(low1_rows),
        "low2_target_rows": str(low2_rows),
        "source_window_rows": str(len(source_windows)),
        "candidate_rows": str(len(candidate_rows)),
        "low1_candidate_rows": str(sum(1 for row in candidate_rows if row.get("row_role") == "low1")),
        "low2_candidate_rows": str(sum(1 for row in candidate_rows if row.get("row_role") == "low2")),
        "strong_pair_candidate_rows": str(sum(int_value(row, "strong_pair") for row in candidate_rows)),
        "relaxed_pair_candidate_rows": str(sum(int_value(row, "relaxed_pair") for row in candidate_rows)),
        "low1_rows_with_strong_pair": str(low1_strong),
        "low2_rows_with_strong_pair": str(low2_strong),
        "low1_rows_with_relaxed_pair": str(low1_relaxed),
        "low2_rows_with_relaxed_pair": str(low2_relaxed),
        "best_low1_small_delta_le2_min": str(min_best(low1_coverage, "best_small_delta_le2_bytes")),
        "best_low2_small_delta_le2_min": str(min_best(low2_coverage, "best_small_delta_le2_bytes")),
        "best_low2_small_delta_le4_min": str(min_best(low2_coverage, "best_small_delta_le4_bytes")),
        "best_candidate_target": best_row.get("target_id", ""),
        "best_candidate_role": best_row.get("row_role", ""),
        "best_candidate_source_target": best_row.get("source_target_id", ""),
        "best_candidate_source_role": best_row.get("source_row_role", ""),
        "best_candidate_source_delta": best_row.get("source_row_delta", ""),
        "best_candidate_exact_bytes": best_row.get("exact_bytes", "0"),
        "best_candidate_small_delta_le2_bytes": best_row.get("small_delta_le2_bytes", "0"),
        "best_candidate_small_delta_le4_bytes": best_row.get("small_delta_le4_bytes", "0"),
        "source_known_min": str(min(known_values, default=0)),
        "corpus_candidate_rows": str(len(corpus_overlap_rows)),
        "corpus_candidate_source_overlaps_low_rows": str(corpus_low_overlap),
        "corpus_candidate_source_dominant_low1_rows": str(corpus_low1_overlap),
        "corpus_candidate_source_dominant_low2_rows": str(corpus_low2_overlap),
        "issue_rows": str(len(issues)),
        "review_verdict": verdict,
        "next_probe": next_probe,
    }


def table_html(title: str, filename: str, rows: list[dict[str, str]], fields: list[str], limit: int = 24) -> str:
    if not rows:
        return f"<section><h2>{html.escape(title)}</h2><p>No rows.</p></section>"
    headers = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = []
    for row in rows[:limit]:
        body.append("<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>")
    return (
        f"<section><h2>{html.escape(title)}</h2><p><a href=\"{html.escape(filename)}\">"
        f"{html.escape(filename)}</a></p><table><thead><tr>{headers}</tr></thead>"
        f"<tbody>{''.join(body)}</tbody></table></section>"
    )


def build_html(
    summary: dict[str, str],
    targets: list[dict[str, str]],
    coverage: list[dict[str, str]],
    candidates: list[dict[str, str]],
    overlaps: list[dict[str, str]],
    source_windows: list[dict[str, str]],
    title: str,
) -> str:
    summary_json = html.escape(json.dumps(summary, indent=2))
    stats = "".join(
        f"<div class=\"stat\"><div class=\"label\">{html.escape(key)}</div>"
        f"<div class=\"value\">{html.escape(summary.get(key, ''))}</div></div>"
        for key in (
            "candidate_rows",
            "low1_rows_with_strong_pair",
            "low2_rows_with_strong_pair",
            "low2_rows_with_relaxed_pair",
            "corpus_candidate_source_dominant_low1_rows",
            "review_verdict",
        )
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{html.escape(title)}</title>
  <style>
    body {{ font-family: sans-serif; margin: 24px; color: #1f2933; }}
    .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }}
    .stat {{ border: 1px solid #d8dee4; border-radius: 6px; padding: 10px; background: #f8fafc; }}
    .label {{ font-size: 12px; color: #52606d; }}
    .value {{ font-weight: 700; overflow-wrap: anywhere; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 12px; margin-top: 8px; }}
    th, td {{ border: 1px solid #d8dee4; padding: 4px 6px; text-align: left; vertical-align: top; }}
    th {{ background: #eef2f7; }}
    pre {{ background: #f6f8fa; padding: 12px; overflow: auto; }}
  </style>
</head>
<body>
  <h1>{html.escape(title)}</h1>
  <div class="stats">{stats}</div>
  <h2>Summary</h2>
  <pre>{summary_json}</pre>
  {table_html("Target coverage", "target_coverage.csv", coverage, COVERAGE_FIELDNAMES)}
  {table_html("Role-pair transform candidates", "candidates.csv", candidates, CANDIDATE_FIELDNAMES)}
  {table_html("Corpus source overlaps", "corpus_source_overlaps.csv", overlaps, SOURCE_OVERLAP_FIELDNAMES)}
  {table_html("Targets", "targets.csv", targets, TARGET_FIELDNAMES)}
  {table_html("Source windows sample", "source_windows.csv", source_windows, SOURCE_WINDOW_FIELDNAMES)}
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Profile peer low-row transform windows after the Frontier80 low-payload corpus source scan."
    )
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--runs", type=Path, default=DEFAULT_RUNS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--clean-fixtures", type=Path, default=DEFAULT_CLEAN_FIXTURES)
    parser.add_argument("--corpus-candidates", type=Path, default=DEFAULT_CORPUS_CANDIDATES)
    parser.add_argument("--source-delta-min", type=int, default=-16)
    parser.add_argument("--source-delta-max", type=int, default=24)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Low Payload Role-Pair Transform Probe",
    )
    args = parser.parse_args()

    issues: list[str] = []
    run_rows = read_csv(args.runs)
    manifest_rows = read_csv(args.manifest)
    clean_rows = read_csv(args.clean_fixtures)
    corpus_candidate_rows = read_csv(args.corpus_candidates)
    target_runs = load_target_runs(run_rows, manifest_rows, clean_rows, issues)
    target_rows = low_target_rows(target_runs, issues)
    targets = [target_row_record(row) for row in target_rows]
    source_windows = source_window_rows(target_rows, args.source_delta_min, args.source_delta_max)
    candidates = build_candidates(target_rows, source_windows)
    coverage = build_coverage(target_rows, candidates)
    overlaps = build_corpus_source_overlaps(corpus_candidate_rows, target_rows)
    source_records = [window["record"] for window in source_windows]
    summary = build_summary(
        target_runs=len(target_runs),
        target_rows=target_rows,
        source_windows=source_windows,
        candidate_rows=candidates,
        coverage_rows=coverage,
        corpus_overlap_rows=overlaps,
        issues=issues,
    )

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, targets)
    write_csv(args.output / "source_windows.csv", SOURCE_WINDOW_FIELDNAMES, source_records)
    write_csv(args.output / "target_coverage.csv", COVERAGE_FIELDNAMES, coverage)
    write_csv(args.output / "candidates.csv", CANDIDATE_FIELDNAMES, candidates)
    write_csv(args.output / "corpus_source_overlaps.csv", SOURCE_OVERLAP_FIELDNAMES, overlaps)
    (args.output / "issues.txt").write_text("\n".join(issues))
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, targets, coverage, candidates, overlaps, source_records, args.title))

    print(f"Role-pair candidates: {summary['candidate_rows']}")
    print(
        "Coverage: "
        f"low1 strong {summary['low1_rows_with_strong_pair']}/{summary['low1_target_rows']}, "
        f"low2 strong {summary['low2_rows_with_strong_pair']}/{summary['low2_target_rows']}, "
        f"low2 relaxed {summary['low2_rows_with_relaxed_pair']}/{summary['low2_target_rows']}"
    )
    print(f"Corpus low1-overlap sources: {summary['corpus_candidate_source_dominant_low1_rows']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
