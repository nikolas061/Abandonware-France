#!/usr/bin/env python3
"""Profile transformed high-row support for row-state source prerequisites."""

from __future__ import annotations

import argparse
import html
import json
import statistics
from collections import Counter
from pathlib import Path

from lolg_tex_gap_decoder_frontier80_context_split_residual_low_payload_neighborhood_probe import (
    load_target_runs,
    read_csv,
    signed_delta,
)
from lolg_tex_gap_decoder_frontier80_context_split_residual_low_payload_row_state_source_prereq_probe import (
    score_candidate,
    support_windows,
    target_source_rows,
)
from lolg_tex_gap_opcode_probe import int_value, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_frontier80_context_split_residual_low_payload_row_state_source_transform_probe")
DEFAULT_RUNS = Path("output/tex_gap_decoder_unresolved_run_probe_frontier80_context_split_residual_second_replay/runs.csv")
DEFAULT_MANIFEST = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_CLEAN_FIXTURES = Path(
    "output/tex_gap_decoder_frontier80_context_split_residual_second_fixture_replay/fixtures.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "target_source_rows",
    "missing_source_bytes",
    "full_support_candidate_rows",
    "best_raw_exact_total",
    "best_constant_delta_exact_total",
    "best_known_top_delta_exact_total",
    "best_known_median_delta_exact_total",
    "best_nearest_known_delta_exact_total",
    "best_bounded_delta_le4_total",
    "raw_exact_min",
    "constant_delta_exact_min",
    "known_top_delta_exact_min",
    "known_median_delta_exact_min",
    "nearest_known_delta_exact_min",
    "bounded_delta_le4_min",
    "target_rows_with_constant_delta_exact",
    "target_rows_with_bounded_delta_le4_exact",
    "constant_delta_exact_candidate_rows",
    "bounded_delta_le4_candidate_rows",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

CANDIDATE_FIELDNAMES = [
    "target_id",
    "rank",
    "frontier_id",
    "pre_source_start",
    "missing_source_bytes",
    "support_rank",
    "support_frontier_id",
    "support_start",
    "support_known_bytes",
    "support_high_plateau_bytes",
    "raw_missing_exact_bytes",
    "bounded_delta_le2_bytes",
    "bounded_delta_le4_bytes",
    "bounded_delta_le4_exact",
    "best_constant_delta",
    "best_constant_delta_exact_bytes",
    "known_delta_positions",
    "known_top_delta",
    "known_top_delta_count",
    "known_top_delta_exact_bytes",
    "known_median_delta",
    "known_median_delta_exact_bytes",
    "nearest_known_delta_exact_bytes",
    "left_known_delta_exact_bytes",
    "right_known_delta_exact_bytes",
    "interpolated_known_delta_exact_bytes",
    "top_missing_delta",
    "top_missing_delta_count",
    "same_fixture",
    "relative_offset",
    "support_head_hex",
    "target_head_hex",
]

COVERAGE_FIELDNAMES = [
    "target_id",
    "rank",
    "frontier_id",
    "pre_source_start",
    "known_source_bytes",
    "missing_source_bytes",
    "full_support_candidate_rows",
    "best_raw_exact_bytes",
    "best_raw_support_rank",
    "best_raw_support_frontier_id",
    "best_raw_support_start",
    "best_constant_delta_exact_bytes",
    "best_constant_delta",
    "best_constant_support_rank",
    "best_constant_support_frontier_id",
    "best_constant_support_start",
    "best_known_top_delta_exact_bytes",
    "best_known_median_delta_exact_bytes",
    "best_nearest_known_delta_exact_bytes",
    "best_bounded_delta_le4_bytes",
    "best_bounded_support_rank",
    "best_bounded_support_frontier_id",
    "best_bounded_support_start",
    "constant_delta_exact_candidate_rows",
    "bounded_delta_le4_candidate_rows",
]

DELTA_HIST_FIELDNAMES = [
    "target_id",
    "position",
    "sample_rows",
    "top_delta",
    "top_delta_count",
    "top_delta_ratio",
    "delta_histogram_json",
]


def add_delta(value: int, delta: int) -> int:
    return (value + delta) & 0xFF


def best_constant_delta_exact(
    support: bytes,
    target: bytes,
    positions: list[int],
    *,
    delta_min: int,
    delta_max: int,
) -> tuple[int, int]:
    best_delta = 0
    best_exact = -1
    for delta in range(delta_min, delta_max + 1):
        exact = sum(1 for position in positions if add_delta(support[position], delta) == target[position])
        if exact > best_exact:
            best_delta = delta
            best_exact = exact
    return best_delta, max(best_exact, 0)


def exact_with_delta(support: bytes, target: bytes, positions: list[int], delta: int) -> int:
    return sum(1 for position in positions if add_delta(support[position], delta) == target[position])


def nearest_known_delta_exact(
    support: bytes,
    target: bytes,
    missing_positions: list[int],
    known_positions: list[int],
    deltas: list[int],
) -> int:
    exact = 0
    for position in missing_positions:
        nearest = min(known_positions, key=lambda known_position: abs(known_position - position))
        if add_delta(support[position], deltas[nearest]) == target[position]:
            exact += 1
    return exact


def directional_known_delta_exact(
    support: bytes,
    target: bytes,
    missing_positions: list[int],
    known_positions: list[int],
    deltas: list[int],
    direction: str,
) -> int:
    exact = 0
    for position in missing_positions:
        if direction == "left":
            usable = [known_position for known_position in known_positions if known_position < position]
            selected = max(usable) if usable else None
        else:
            usable = [known_position for known_position in known_positions if known_position > position]
            selected = min(usable) if usable else None
        if selected is not None and add_delta(support[position], deltas[selected]) == target[position]:
            exact += 1
    return exact


def interpolated_known_delta_exact(
    support: bytes,
    target: bytes,
    missing_positions: list[int],
    known_positions: list[int],
    deltas: list[int],
) -> int:
    exact = 0
    for position in missing_positions:
        left = [known_position for known_position in known_positions if known_position < position]
        right = [known_position for known_position in known_positions if known_position > position]
        if not left or not right:
            continue
        delta = round((deltas[max(left)] + deltas[min(right)]) / 2)
        if add_delta(support[position], delta) == target[position]:
            exact += 1
    return exact


def transform_candidate(
    target_row: dict[str, object],
    support: dict[str, object],
    *,
    delta_min: int,
    delta_max: int,
) -> dict[str, str] | None:
    base = score_candidate(target_row, support)
    if not base:
        return None
    missing_positions = target_row["missing"]
    target_source = target_row["source"]
    target_mask = target_row["mask"]
    support_data = support["data"]
    support_mask = support["mask"]
    assert isinstance(missing_positions, list)
    assert isinstance(target_source, bytes)
    assert isinstance(target_mask, bytes)
    assert isinstance(support_data, bytes)
    assert isinstance(support_mask, bytes)
    if int_value(base, "missing_known_bytes") != len(missing_positions):
        return None

    deltas = [signed_delta(source_value, target_value) for source_value, target_value in zip(support_data, target_source)]
    abs_deltas = [abs(delta) for delta in deltas]
    missing_deltas = [deltas[position] for position in missing_positions]
    missing_counter = Counter(missing_deltas)
    top_missing_delta, top_missing_count = missing_counter.most_common(1)[0] if missing_counter else (0, 0)
    known_positions = [
        position
        for position, value in enumerate(target_mask)
        if value and support_mask[position]
    ]
    known_deltas = [deltas[position] for position in known_positions]
    known_top_delta = 0
    known_top_count = 0
    known_top_exact = 0
    known_median_delta = 0
    known_median_exact = 0
    nearest_exact = 0
    left_exact = 0
    right_exact = 0
    interpolated_exact = 0
    if known_deltas:
        known_top_delta, known_top_count = Counter(known_deltas).most_common(1)[0]
        known_top_exact = exact_with_delta(support_data, target_source, missing_positions, known_top_delta)
        known_median_delta = int(statistics.median_low(known_deltas))
        known_median_exact = exact_with_delta(support_data, target_source, missing_positions, known_median_delta)
        nearest_exact = nearest_known_delta_exact(
            support_data,
            target_source,
            missing_positions,
            known_positions,
            deltas,
        )
        left_exact = directional_known_delta_exact(
            support_data,
            target_source,
            missing_positions,
            known_positions,
            deltas,
            "left",
        )
        right_exact = directional_known_delta_exact(
            support_data,
            target_source,
            missing_positions,
            known_positions,
            deltas,
            "right",
        )
        interpolated_exact = interpolated_known_delta_exact(
            support_data,
            target_source,
            missing_positions,
            known_positions,
            deltas,
        )

    best_delta, best_delta_exact = best_constant_delta_exact(
        support_data,
        target_source,
        missing_positions,
        delta_min=delta_min,
        delta_max=delta_max,
    )
    bounded_le2 = sum(1 for position in missing_positions if abs_deltas[position] <= 2)
    bounded_le4 = sum(1 for position in missing_positions if abs_deltas[position] <= 4)
    return {
        "target_id": base.get("target_id", ""),
        "rank": base.get("rank", ""),
        "frontier_id": base.get("frontier_id", ""),
        "pre_source_start": base.get("pre_source_start", ""),
        "missing_source_bytes": base.get("missing_source_bytes", "0"),
        "support_rank": base.get("support_rank", ""),
        "support_frontier_id": base.get("support_frontier_id", ""),
        "support_start": base.get("support_start", ""),
        "support_known_bytes": base.get("support_known_bytes", "0"),
        "support_high_plateau_bytes": base.get("support_high_plateau_bytes", "0"),
        "raw_missing_exact_bytes": base.get("missing_exact_bytes", "0"),
        "bounded_delta_le2_bytes": str(bounded_le2),
        "bounded_delta_le4_bytes": str(bounded_le4),
        "bounded_delta_le4_exact": "1" if bounded_le4 == len(missing_positions) else "0",
        "best_constant_delta": str(best_delta),
        "best_constant_delta_exact_bytes": str(best_delta_exact),
        "known_delta_positions": str(len(known_positions)),
        "known_top_delta": str(known_top_delta),
        "known_top_delta_count": str(known_top_count),
        "known_top_delta_exact_bytes": str(known_top_exact),
        "known_median_delta": str(known_median_delta),
        "known_median_delta_exact_bytes": str(known_median_exact),
        "nearest_known_delta_exact_bytes": str(nearest_exact),
        "left_known_delta_exact_bytes": str(left_exact),
        "right_known_delta_exact_bytes": str(right_exact),
        "interpolated_known_delta_exact_bytes": str(interpolated_exact),
        "top_missing_delta": str(top_missing_delta),
        "top_missing_delta_count": str(top_missing_count),
        "same_fixture": base.get("same_fixture", "0"),
        "relative_offset": base.get("relative_offset", ""),
        "support_head_hex": base.get("support_head_hex", ""),
        "target_head_hex": base.get("target_head_hex", ""),
    }


def build_candidates(
    targets: list[dict[str, object]],
    supports: list[dict[str, object]],
    *,
    delta_min: int,
    delta_max: int,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for target in targets:
        for support in supports:
            row = transform_candidate(target, support, delta_min=delta_min, delta_max=delta_max)
            if row:
                rows.append(row)
    rows.sort(
        key=lambda row: (
            row.get("target_id", ""),
            -int_value(row, "bounded_delta_le4_bytes"),
            -int_value(row, "best_constant_delta_exact_bytes"),
            -int_value(row, "known_top_delta_exact_bytes"),
            -int_value(row, "raw_missing_exact_bytes"),
            row.get("support_rank", ""),
            int_value(row, "support_start"),
        )
    )
    return rows


def best_by(rows: list[dict[str, str]], field: str) -> dict[str, str]:
    return sorted(
        rows,
        key=lambda row: (
            -int_value(row, field),
            -int_value(row, "bounded_delta_le4_bytes"),
            -int_value(row, "best_constant_delta_exact_bytes"),
            -int_value(row, "raw_missing_exact_bytes"),
            row.get("support_rank", ""),
            int_value(row, "support_start"),
        ),
    )[0]


def build_coverage(targets: list[dict[str, object]], candidates: list[dict[str, str]]) -> list[dict[str, str]]:
    by_target: dict[str, list[dict[str, str]]] = {}
    for row in candidates:
        by_target.setdefault(row.get("target_id", ""), []).append(row)

    rows: list[dict[str, str]] = []
    for target in targets:
        target_info = target["target"]
        target_mask = target["mask"]
        missing = target["missing"]
        assert isinstance(target_info, dict)
        assert isinstance(target_mask, bytes)
        assert isinstance(missing, list)
        target_id = target_info.get("target_id", "")
        rows_for_target = by_target.get(target_id, [])
        best_raw = best_by(rows_for_target, "raw_missing_exact_bytes") if rows_for_target else {}
        best_constant = best_by(rows_for_target, "best_constant_delta_exact_bytes") if rows_for_target else {}
        best_top = best_by(rows_for_target, "known_top_delta_exact_bytes") if rows_for_target else {}
        best_median = best_by(rows_for_target, "known_median_delta_exact_bytes") if rows_for_target else {}
        best_nearest = best_by(rows_for_target, "nearest_known_delta_exact_bytes") if rows_for_target else {}
        best_bounded = best_by(rows_for_target, "bounded_delta_le4_bytes") if rows_for_target else {}
        rows.append(
            {
                "target_id": target_id,
                "rank": target_info.get("rank", ""),
                "frontier_id": target_info.get("frontier_id", ""),
                "pre_source_start": str(target["pre_start"]),
                "known_source_bytes": str(sum(1 for value in target_mask if value)),
                "missing_source_bytes": str(len(missing)),
                "full_support_candidate_rows": str(len(rows_for_target)),
                "best_raw_exact_bytes": best_raw.get("raw_missing_exact_bytes", "0"),
                "best_raw_support_rank": best_raw.get("support_rank", ""),
                "best_raw_support_frontier_id": best_raw.get("support_frontier_id", ""),
                "best_raw_support_start": best_raw.get("support_start", ""),
                "best_constant_delta_exact_bytes": best_constant.get("best_constant_delta_exact_bytes", "0"),
                "best_constant_delta": best_constant.get("best_constant_delta", ""),
                "best_constant_support_rank": best_constant.get("support_rank", ""),
                "best_constant_support_frontier_id": best_constant.get("support_frontier_id", ""),
                "best_constant_support_start": best_constant.get("support_start", ""),
                "best_known_top_delta_exact_bytes": best_top.get("known_top_delta_exact_bytes", "0"),
                "best_known_median_delta_exact_bytes": best_median.get("known_median_delta_exact_bytes", "0"),
                "best_nearest_known_delta_exact_bytes": best_nearest.get("nearest_known_delta_exact_bytes", "0"),
                "best_bounded_delta_le4_bytes": best_bounded.get("bounded_delta_le4_bytes", "0"),
                "best_bounded_support_rank": best_bounded.get("support_rank", ""),
                "best_bounded_support_frontier_id": best_bounded.get("support_frontier_id", ""),
                "best_bounded_support_start": best_bounded.get("support_start", ""),
                "constant_delta_exact_candidate_rows": str(
                    sum(
                        1
                        for row in rows_for_target
                        if int_value(row, "best_constant_delta_exact_bytes") == len(missing)
                    )
                ),
                "bounded_delta_le4_candidate_rows": str(
                    sum(1 for row in rows_for_target if int_value(row, "bounded_delta_le4_bytes") == len(missing))
                ),
            }
        )
    rows.sort(key=lambda row: (int_value(row, "rank"), int_value(row, "pre_source_start")))
    return rows


def build_delta_histogram_from_supports(
    targets: list[dict[str, object]],
    supports: list[dict[str, object]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for target in targets:
        target_info = target["target"]
        target_source = target["source"]
        missing_positions = target["missing"]
        assert isinstance(target_info, dict)
        assert isinstance(target_source, bytes)
        assert isinstance(missing_positions, list)
        counters: dict[int, Counter[int]] = {position: Counter() for position in missing_positions}
        for support in supports:
            candidate = score_candidate(target, support)
            if not candidate or int_value(candidate, "missing_known_bytes") != len(missing_positions):
                continue
            support_data = support["data"]
            assert isinstance(support_data, bytes)
            for position in missing_positions:
                delta = signed_delta(support_data[position], target_source[position])
                counters[position][delta] += 1
        for position, counter in counters.items():
            sample_rows = sum(counter.values())
            top_delta, top_count = counter.most_common(1)[0] if counter else (0, 0)
            rows.append(
                {
                    "target_id": target_info.get("target_id", ""),
                    "position": str(position),
                    "sample_rows": str(sample_rows),
                    "top_delta": str(top_delta),
                    "top_delta_count": str(top_count),
                    "top_delta_ratio": f"{(top_count / sample_rows) if sample_rows else 0.0:.6f}",
                    "delta_histogram_json": json.dumps(dict(sorted(counter.items()))),
                }
            )
    rows.sort(key=lambda row: (row.get("target_id", ""), int_value(row, "position")))
    return rows


def sum_field(rows: list[dict[str, str]], field: str) -> int:
    return sum(int_value(row, field) for row in rows)


def min_field(rows: list[dict[str, str]], field: str) -> int:
    return min((int_value(row, field) for row in rows), default=0)


def build_summary(
    coverage: list[dict[str, str]],
    candidates: list[dict[str, str]],
    issues: list[str],
) -> dict[str, str]:
    missing_total = sum_field(coverage, "missing_source_bytes")
    target_count = len(coverage)
    constant_exact_rows = sum(
        1
        for row in coverage
        if int_value(row, "best_constant_delta_exact_bytes") == int_value(row, "missing_source_bytes")
    )
    bounded_exact_rows = sum(
        1
        for row in coverage
        if int_value(row, "best_bounded_delta_le4_bytes") == int_value(row, "missing_source_bytes")
    )
    if bounded_exact_rows == target_count and constant_exact_rows < target_count:
        verdict = "frontier80_context_residual_low_payload_row_state_source_transform_selector_needed"
        next_probe = "derive bounded-delta selector for transformed row-state source prerequisites"
    elif constant_exact_rows == target_count and target_count:
        verdict = "frontier80_context_residual_low_payload_row_state_source_transform_exact_ready"
        next_probe = "promote constant-delta transformed row-state source prerequisites"
    else:
        verdict = "frontier80_context_residual_low_payload_row_state_source_transform_split_needed"
        next_probe = "split transformed high-row source support by delta signature"
    return {
        "scope": "total",
        "target_source_rows": str(target_count),
        "missing_source_bytes": str(missing_total),
        "full_support_candidate_rows": str(len(candidates)),
        "best_raw_exact_total": str(sum_field(coverage, "best_raw_exact_bytes")),
        "best_constant_delta_exact_total": str(sum_field(coverage, "best_constant_delta_exact_bytes")),
        "best_known_top_delta_exact_total": str(sum_field(coverage, "best_known_top_delta_exact_bytes")),
        "best_known_median_delta_exact_total": str(sum_field(coverage, "best_known_median_delta_exact_bytes")),
        "best_nearest_known_delta_exact_total": str(sum_field(coverage, "best_nearest_known_delta_exact_bytes")),
        "best_bounded_delta_le4_total": str(sum_field(coverage, "best_bounded_delta_le4_bytes")),
        "raw_exact_min": str(min_field(coverage, "best_raw_exact_bytes")),
        "constant_delta_exact_min": str(min_field(coverage, "best_constant_delta_exact_bytes")),
        "known_top_delta_exact_min": str(min_field(coverage, "best_known_top_delta_exact_bytes")),
        "known_median_delta_exact_min": str(min_field(coverage, "best_known_median_delta_exact_bytes")),
        "nearest_known_delta_exact_min": str(min_field(coverage, "best_nearest_known_delta_exact_bytes")),
        "bounded_delta_le4_min": str(min_field(coverage, "best_bounded_delta_le4_bytes")),
        "target_rows_with_constant_delta_exact": str(constant_exact_rows),
        "target_rows_with_bounded_delta_le4_exact": str(bounded_exact_rows),
        "constant_delta_exact_candidate_rows": str(
            sum(1 for row in candidates if int_value(row, "best_constant_delta_exact_bytes") == int_value(row, "missing_source_bytes"))
        ),
        "bounded_delta_le4_candidate_rows": str(sum(1 for row in candidates if row.get("bounded_delta_le4_exact") == "1")),
        "issue_rows": str(len(issues)),
        "review_verdict": verdict,
        "next_probe": next_probe,
    }


def table_html(title: str, filename: str, rows: list[dict[str, str]], fields: list[str], limit: int = 36) -> str:
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
    coverage: list[dict[str, str]],
    candidates: list[dict[str, str]],
    delta_histogram: list[dict[str, str]],
    title: str,
) -> str:
    summary_json = html.escape(json.dumps(summary, indent=2))
    stats = "".join(
        f"<div class=\"stat\"><div class=\"label\">{html.escape(key)}</div>"
        f"<div class=\"value\">{html.escape(summary.get(key, ''))}</div></div>"
        for key in (
            "missing_source_bytes",
            "best_raw_exact_total",
            "best_constant_delta_exact_total",
            "best_bounded_delta_le4_total",
            "target_rows_with_bounded_delta_le4_exact",
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
  {table_html("Coverage", "target_coverage.csv", coverage, COVERAGE_FIELDNAMES)}
  {table_html("Transform candidates", "transform_candidates.csv", candidates, CANDIDATE_FIELDNAMES)}
  {table_html("Delta histogram", "delta_histogram.csv", delta_histogram, DELTA_HIST_FIELDNAMES)}
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Profile transformed high-row support for row-state source prerequisites."
    )
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--runs", type=Path, default=DEFAULT_RUNS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--clean-fixtures", type=Path, default=DEFAULT_CLEAN_FIXTURES)
    parser.add_argument("--min-known", type=int, default=24)
    parser.add_argument("--min-high", type=int, default=28)
    parser.add_argument("--delta-min", type=int, default=-4)
    parser.add_argument("--delta-max", type=int, default=4)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Low Payload Row-State Source Transform Probe",
    )
    args = parser.parse_args()

    issues: list[str] = []
    run_rows = read_csv(args.runs)
    manifest_rows = read_csv(args.manifest)
    clean_rows = read_csv(args.clean_fixtures)
    target_runs = load_target_runs(run_rows, manifest_rows, clean_rows, issues)
    targets = target_source_rows(target_runs, issues)
    supports = support_windows(manifest_rows, clean_rows, issues, min_known=args.min_known, min_high=args.min_high)
    candidates = build_candidates(targets, supports, delta_min=args.delta_min, delta_max=args.delta_max)
    coverage = build_coverage(targets, candidates)
    delta_histogram = build_delta_histogram_from_supports(
        targets,
        supports,
    )
    summary = build_summary(coverage, candidates, issues)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "target_coverage.csv", COVERAGE_FIELDNAMES, coverage)
    write_csv(args.output / "transform_candidates.csv", CANDIDATE_FIELDNAMES, candidates)
    write_csv(args.output / "delta_histogram.csv", DELTA_HIST_FIELDNAMES, delta_histogram)
    (args.output / "issues.txt").write_text("\n".join(issues))
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, coverage, candidates, delta_histogram, args.title))

    print(
        "Source transforms: "
        f"raw={summary['best_raw_exact_total']}, "
        f"constant={summary['best_constant_delta_exact_total']}, "
        f"bounded_le4={summary['best_bounded_delta_le4_total']}"
    )
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
