#!/usr/bin/env python3
"""Probe non-oracle selectors for the single-row residual delta guard."""

from __future__ import annotations

import argparse
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_decoder_frontier80_context_split_residual_low_payload_neighborhood_probe import (
    load_target_runs,
    read_csv,
    signed_delta,
)
from lolg_tex_gap_decoder_frontier80_context_split_residual_low_payload_row_state_source_prereq_probe import (
    support_windows,
    target_source_rows,
)
from lolg_tex_gap_decoder_frontier80_context_split_residual_low_payload_row_state_source_single_row_delta_guard_probe import (
    add_delta,
    bounded_candidates,
    residual_targets,
    target_id,
)
from lolg_tex_gap_opcode_probe import int_value, write_csv


DEFAULT_OUTPUT = Path(
    "output/tex_gap_decoder_frontier80_context_split_residual_low_payload_row_state_source_single_row_delta_non_oracle_selector_probe"
)
DEFAULT_RUNS = Path("output/tex_gap_decoder_unresolved_run_probe_frontier80_context_split_residual_second_replay/runs.csv")
DEFAULT_MANIFEST = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_CLEAN_FIXTURES = Path(
    "output/tex_gap_decoder_frontier80_context_split_residual_low_payload_row_state_source_delta_guard_promoted_replay/fixtures.csv"
)

SELECTOR_NAME = "position_support_value_mode"

SUMMARY_FIELDNAMES = [
    "scope",
    "residual_target_rows",
    "residual_target_ids",
    "missing_source_bytes",
    "bounded_candidate_rows",
    "selector_name",
    "selected_support_rank",
    "selected_support_frontier_id",
    "selected_support_start",
    "selected_raw_exact_bytes",
    "selected_non_oracle_exact_bytes",
    "selected_table_predicted_bytes",
    "selected_fallback_predicted_bytes",
    "selected_vote_total",
    "selected_conflict_positions",
    "best_non_oracle_exact_total",
    "best_table_only_exact_total",
    "promotion_ready_rows",
    "promotion_ready_bytes",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

CANDIDATE_FIELDNAMES = [
    "target_id",
    "selector_name",
    "non_oracle_rank",
    "support_rank",
    "support_frontier_id",
    "support_start",
    "same_fixture",
    "relative_offset",
    "missing_source_bytes",
    "raw_exact_bytes",
    "predicted_exact_bytes",
    "table_predicted_bytes",
    "fallback_predicted_bytes",
    "vote_total",
    "conflict_positions",
    "uncovered_positions",
    "fallback_positions",
    "predicted_delta_head",
    "oracle_delta_head",
    "support_head_hex",
    "target_head_hex",
]

OPERATION_FIELDNAMES = [
    "target_id",
    "support_rank",
    "support_frontier_id",
    "support_start",
    "position",
    "support_value",
    "expected_value",
    "predicted_delta",
    "predicted_value",
    "oracle_delta",
    "exact",
    "prediction_source",
    "table_votes",
    "table_histogram_json",
]


def feature_key(record: dict[str, object], position: int) -> tuple[int, int]:
    support = record["support"]
    assert isinstance(support, dict)
    data = support["data"]
    assert isinstance(data, bytes)
    return (position, data[position])


def nearest_known_delta(target: dict[str, object], support_data: bytes, position: int) -> int:
    source = target["source"]
    mask = target["mask"]
    assert isinstance(source, bytes)
    assert isinstance(mask, bytes)
    known = [known_position for known_position, value in enumerate(mask) if value]
    if not known:
        return 0
    nearest = min(
        known,
        key=lambda known_position: (
            abs(known_position - position),
            0 if known_position > position else 1,
        ),
    )
    return signed_delta(support_data[position], source[nearest])


def mode_from_peers(
    record: dict[str, object],
    records: list[dict[str, object]],
    position: int,
) -> tuple[int, str, Counter[int]]:
    key = feature_key(record, position)
    counter: Counter[int] = Counter()
    for other in records:
        if other is record:
            continue
        if feature_key(other, position) != key:
            continue
        deltas = other["deltas"]
        assert isinstance(deltas, list)
        counter[int(deltas[position])] += 1
    if counter:
        return counter.most_common(1)[0][0], "table", counter

    target = record["target"]
    support = record["support"]
    assert isinstance(target, dict)
    assert isinstance(support, dict)
    support_data = support["data"]
    assert isinstance(support_data, bytes)
    return nearest_known_delta(target, support_data, position), "nearest_known", counter


def candidate_sort_key(row: dict[str, str]) -> tuple[int, int, int, int, int, str, int]:
    return (
        -int_value(row, "table_predicted_bytes"),
        int_value(row, "fallback_predicted_bytes"),
        int_value(row, "conflict_positions"),
        -int_value(row, "vote_total"),
        -int_value(row, "raw_exact_bytes"),
        row.get("support_rank", ""),
        int_value(row, "support_start"),
    )


def build_selector_rows(
    residual: list[dict[str, object]],
    supports: list[dict[str, object]],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    candidate_rows: list[dict[str, str]] = []
    operation_rows: list[dict[str, str]] = []
    for target in residual:
        source = target["source"]
        missing = target["missing"]
        assert isinstance(source, bytes)
        assert isinstance(missing, list)
        records = bounded_candidates(target, supports)
        target_rows: list[dict[str, str]] = []
        for record in records:
            base = record["base"]
            support = record["support"]
            deltas = record["deltas"]
            assert isinstance(base, dict)
            assert isinstance(support, dict)
            assert isinstance(deltas, list)
            support_data = support["data"]
            assert isinstance(support_data, bytes)
            predicted_deltas: list[int] = []
            uncovered_positions: list[int] = []
            fallback_positions: list[int] = []
            predicted_exact = 0
            table_predicted = 0
            fallback_predicted = 0
            vote_total = 0
            conflict_positions = 0
            for position in missing:
                predicted_delta, source_name, counter = mode_from_peers(record, records, position)
                predicted_value = add_delta(support_data[position], predicted_delta)
                expected_value = source[position]
                oracle_delta = int(deltas[position])
                exact = predicted_value == expected_value
                predicted_exact += int(exact)
                if source_name == "table":
                    table_predicted += 1
                    vote_total += sum(counter.values())
                    conflict_positions += int(len(counter) > 1)
                else:
                    fallback_predicted += 1
                    uncovered_positions.append(position)
                    fallback_positions.append(position)
                predicted_deltas.append(predicted_delta)
                operation_rows.append(
                    {
                        "target_id": target_id(target),
                        "support_rank": base.get("support_rank", ""),
                        "support_frontier_id": base.get("support_frontier_id", ""),
                        "support_start": base.get("support_start", ""),
                        "position": str(position),
                        "support_value": str(support_data[position]),
                        "expected_value": str(expected_value),
                        "predicted_delta": str(predicted_delta),
                        "predicted_value": str(predicted_value),
                        "oracle_delta": str(oracle_delta),
                        "exact": "1" if exact else "0",
                        "prediction_source": source_name,
                        "table_votes": str(sum(counter.values())),
                        "table_histogram_json": json.dumps(dict(sorted(counter.items())), separators=(",", ":")),
                    }
                )
            target_rows.append(
                {
                    "target_id": target_id(target),
                    "selector_name": SELECTOR_NAME,
                    "non_oracle_rank": "0",
                    "support_rank": base.get("support_rank", ""),
                    "support_frontier_id": base.get("support_frontier_id", ""),
                    "support_start": base.get("support_start", ""),
                    "same_fixture": base.get("same_fixture", "0"),
                    "relative_offset": base.get("relative_offset", ""),
                    "missing_source_bytes": str(len(missing)),
                    "raw_exact_bytes": base.get("missing_exact_bytes", "0"),
                    "predicted_exact_bytes": str(predicted_exact),
                    "table_predicted_bytes": str(table_predicted),
                    "fallback_predicted_bytes": str(fallback_predicted),
                    "vote_total": str(vote_total),
                    "conflict_positions": str(conflict_positions),
                    "uncovered_positions": ";".join(str(position) for position in uncovered_positions),
                    "fallback_positions": ";".join(str(position) for position in fallback_positions),
                    "predicted_delta_head": " ".join(str(delta) for delta in predicted_deltas[:12]),
                    "oracle_delta_head": " ".join(str(deltas[position]) for position in missing[:12]),
                    "support_head_hex": base.get("support_head_hex", ""),
                    "target_head_hex": base.get("target_head_hex", ""),
                }
            )

        target_rows.sort(key=candidate_sort_key)
        for rank, row in enumerate(target_rows, start=1):
            row["non_oracle_rank"] = str(rank)
            candidate_rows.append(row)

    candidate_rows.sort(
        key=lambda row: (
            row.get("target_id", ""),
            int_value(row, "non_oracle_rank"),
        )
    )
    operation_rows.sort(
        key=lambda row: (
            row.get("target_id", ""),
            row.get("support_rank", ""),
            row.get("support_frontier_id", ""),
            int_value(row, "support_start"),
            int_value(row, "position"),
        )
    )
    return candidate_rows, operation_rows


def selected_rows(candidate_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    by_target: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in candidate_rows:
        by_target[row.get("target_id", "")].append(row)
    return [sorted(rows, key=candidate_sort_key)[0] for _target_id, rows in sorted(by_target.items()) if rows]


def build_summary(
    residual: list[dict[str, object]],
    candidate_rows: list[dict[str, str]],
    issues: list[str],
) -> dict[str, str]:
    selected = selected_rows(candidate_rows)
    missing_total = sum(len(target["missing"]) for target in residual if isinstance(target["missing"], list))
    selected_exact = sum(int_value(row, "predicted_exact_bytes") for row in selected)
    selected_table = sum(int_value(row, "table_predicted_bytes") for row in selected)
    selected_fallback = sum(int_value(row, "fallback_predicted_bytes") for row in selected)
    selected_conflicts = sum(int_value(row, "conflict_positions") for row in selected)
    best_exact = max((int_value(row, "predicted_exact_bytes") for row in candidate_rows), default=0)
    table_only_exact = max(
        (
            int_value(row, "predicted_exact_bytes")
            for row in candidate_rows
            if int_value(row, "fallback_predicted_bytes") == 0
        ),
        default=0,
    )
    first = selected[0] if selected else {}
    ready = (
        selected_exact == missing_total
        and selected_table == missing_total
        and selected_fallback == 0
        and selected_conflicts == 0
        and missing_total > 0
    )
    fallback_ready = selected_exact == missing_total and selected_conflicts == 0 and missing_total > 0
    if ready:
        verdict = "frontier80_context_residual_low_payload_row_state_source_single_row_delta_non_oracle_selector_ready"
        next_probe = "promote single-row residual non-oracle delta selector"
    elif fallback_ready:
        verdict = "frontier80_context_residual_low_payload_row_state_source_single_row_delta_non_oracle_selector_fallback_guard_needed"
        next_probe = "guard nearest-known fallback for single-row residual selector"
    else:
        verdict = "frontier80_context_residual_low_payload_row_state_source_single_row_delta_non_oracle_selector_split_needed"
        next_probe = "split position/support-value table for single-row residual selector"
    return {
        "scope": "total",
        "residual_target_rows": str(len(residual)),
        "residual_target_ids": ";".join(target_id(target) for target in residual),
        "missing_source_bytes": str(missing_total),
        "bounded_candidate_rows": str(len(candidate_rows)),
        "selector_name": SELECTOR_NAME,
        "selected_support_rank": first.get("support_rank", ""),
        "selected_support_frontier_id": first.get("support_frontier_id", ""),
        "selected_support_start": first.get("support_start", ""),
        "selected_raw_exact_bytes": first.get("raw_exact_bytes", "0"),
        "selected_non_oracle_exact_bytes": str(selected_exact),
        "selected_table_predicted_bytes": str(selected_table),
        "selected_fallback_predicted_bytes": str(selected_fallback),
        "selected_vote_total": str(sum(int_value(row, "vote_total") for row in selected)),
        "selected_conflict_positions": str(selected_conflicts),
        "best_non_oracle_exact_total": str(best_exact),
        "best_table_only_exact_total": str(table_only_exact),
        "promotion_ready_rows": str(len(selected) if ready else 0),
        "promotion_ready_bytes": str(missing_total if ready else 0),
        "issue_rows": str(len(issues)),
        "review_verdict": verdict,
        "next_probe": next_probe,
    }


def table_html(title: str, filename: str, rows: list[dict[str, str]], fields: list[str], limit: int = 64) -> str:
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
    candidate_rows: list[dict[str, str]],
    operation_rows: list[dict[str, str]],
    title: str,
) -> str:
    summary_json = html.escape(json.dumps(summary, indent=2))
    stats = "".join(
        f"<div class=\"stat\"><div class=\"label\">{html.escape(key)}</div>"
        f"<div class=\"value\">{html.escape(summary.get(key, ''))}</div></div>"
        for key in (
            "selected_non_oracle_exact_bytes",
            "selected_table_predicted_bytes",
            "selected_fallback_predicted_bytes",
            "selected_support_rank",
            "selected_support_frontier_id",
            "selected_support_start",
            "review_verdict",
        )
    )
    selected_support = {
        (
            summary.get("selected_support_rank", ""),
            summary.get("selected_support_frontier_id", ""),
            summary.get("selected_support_start", ""),
        )
    }
    selected_operations = [
        row
        for row in operation_rows
        if (
            row.get("support_rank", ""),
            row.get("support_frontier_id", ""),
            row.get("support_start", ""),
        )
        in selected_support
    ]
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
  {table_html("Candidate rows", "candidate_rows.csv", candidate_rows, CANDIDATE_FIELDNAMES)}
  {table_html("Selected operations", "operations.csv", selected_operations, OPERATION_FIELDNAMES)}
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Probe non-oracle selectors for the single-row residual delta guard."
    )
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--runs", type=Path, default=DEFAULT_RUNS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--clean-fixtures", type=Path, default=DEFAULT_CLEAN_FIXTURES)
    parser.add_argument("--min-known", type=int, default=24)
    parser.add_argument("--min-high", type=int, default=28)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Low Payload Row-State Source Single-Row Delta Non-Oracle Selector Probe",
    )
    args = parser.parse_args()

    issues: list[str] = []
    run_rows = read_csv(args.runs)
    manifest_rows = read_csv(args.manifest)
    clean_rows = read_csv(args.clean_fixtures)
    target_runs = load_target_runs(run_rows, manifest_rows, clean_rows, issues)
    targets = target_source_rows(target_runs, issues)
    residual = residual_targets(targets)
    supports = support_windows(manifest_rows, clean_rows, issues, min_known=args.min_known, min_high=args.min_high)
    candidate_rows, operation_rows = build_selector_rows(residual, supports)
    summary = build_summary(residual, candidate_rows, issues)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "candidate_rows.csv", CANDIDATE_FIELDNAMES, candidate_rows)
    write_csv(args.output / "operations.csv", OPERATION_FIELDNAMES, operation_rows)
    (args.output / "issues.txt").write_text("\n".join(issues))
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, candidate_rows, operation_rows, args.title))

    print(
        "Single-row non-oracle selector: "
        f"selected={summary['selected_support_rank']}/"
        f"{summary['selected_support_frontier_id']}/"
        f"{summary['selected_support_start']}, "
        f"exact={summary['selected_non_oracle_exact_bytes']}/"
        f"{summary['missing_source_bytes']}"
    )
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
