#!/usr/bin/env python3
"""Promote the single-row non-oracle delta selector into clean fixtures."""

from __future__ import annotations

import argparse
from pathlib import Path

import lolg_tex_gradient_sequence_high_safe_low_exception_source_byte_guard_promoted_replay as source_replay
from lolg_tex_gap_decoder_frontier80_context_split_residual_low_payload_neighborhood_probe import (
    load_target_runs,
    read_csv,
)
from lolg_tex_gap_decoder_frontier80_context_split_residual_low_payload_row_state_source_prereq_probe import (
    target_source_rows,
)
from lolg_tex_gap_opcode_probe import int_value, write_csv


DEFAULT_OUTPUT = Path(
    "output/tex_gap_decoder_frontier80_context_split_residual_low_payload_row_state_source_single_row_delta_non_oracle_selector_promoted_replay"
)
DEFAULT_BASE_FIXTURES = Path(
    "output/tex_gap_decoder_frontier80_context_split_residual_low_payload_row_state_source_delta_guard_promoted_replay/fixtures.csv"
)
DEFAULT_SELECTOR_ROWS = Path(
    "output/tex_gap_decoder_frontier80_context_split_residual_low_payload_row_state_source_single_row_delta_non_oracle_selector_probe/candidate_rows.csv"
)
DEFAULT_OPERATIONS = Path(
    "output/tex_gap_decoder_frontier80_context_split_residual_low_payload_row_state_source_single_row_delta_non_oracle_selector_probe/operations.csv"
)
DEFAULT_RUNS = Path("output/tex_gap_decoder_unresolved_run_probe_frontier80_context_split_residual_second_replay/runs.csv")
DEFAULT_MANIFEST = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_CLEAN_FIXTURES = DEFAULT_BASE_FIXTURES

SUMMARY_FIELDNAMES = source_replay.SUMMARY_FIELDNAMES + [
    "selector_ready_rows",
    "selector_ready_bytes",
    "selected_support_rank",
    "selected_support_frontier_id",
    "selected_support_start",
    "review_verdict",
    "next_probe",
]


def byte_hex(value: int) -> str:
    return f"{value & 0xFF:02x}"


def int_field(row: dict[str, str], field: str, default: int = 0) -> int:
    try:
        return int(row.get(field, ""))
    except (TypeError, ValueError):
        return default


def ready_selector_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    ready: list[dict[str, str]] = []
    for row in rows:
        missing = int_value(row, "missing_source_bytes")
        if (
            row.get("non_oracle_rank") == "1"
            and missing > 0
            and int_value(row, "predicted_exact_bytes") == missing
            and int_value(row, "table_predicted_bytes") == missing
            and int_value(row, "fallback_predicted_bytes") == 0
            and int_value(row, "conflict_positions") == 0
        ):
            ready.append(row)
    return ready


def target_id(row: dict[str, object]) -> str:
    target = row["target"]
    assert isinstance(target, dict)
    return target.get("target_id", "")


def selected_operations(
    operations: list[dict[str, str]],
    selector: dict[str, str],
) -> list[dict[str, str]]:
    rows = [
        row
        for row in operations
        if row.get("target_id") == selector.get("target_id")
        and row.get("support_rank") == selector.get("support_rank")
        and row.get("support_frontier_id") == selector.get("support_frontier_id")
        and row.get("support_start") == selector.get("support_start")
    ]
    rows.sort(key=lambda row: int_value(row, "position"))
    return rows


def promotion_rows(
    *,
    selectors: list[dict[str, str]],
    operations: list[dict[str, str]],
    targets: list[dict[str, object]],
) -> tuple[list[dict[str, str]], list[str]]:
    issues: list[str] = []
    rows: list[dict[str, str]] = []
    targets_by_id = {target_id(target): target for target in targets}
    for selector in selectors:
        target = targets_by_id.get(selector.get("target_id", ""))
        if not target:
            issues.append(f"{selector.get('target_id', '')}:missing_target")
            continue
        target_row = target["target"]
        missing = target["missing"]
        assert isinstance(target_row, dict)
        assert isinstance(missing, list)
        op_rows = selected_operations(operations, selector)
        if len(op_rows) != len(missing):
            issues.append(f"{selector.get('target_id', '')}:operation_count_mismatch:{len(op_rows)}:{len(missing)}")
        for op_row in op_rows:
            position = int_field(op_row, "position", -1)
            if position not in missing:
                issues.append(f"{selector.get('target_id', '')}:operation_position_not_missing:{position}")
                continue
            if op_row.get("prediction_source") != "table":
                issues.append(f"{selector.get('target_id', '')}:non_table_prediction:{position}")
                continue
            if op_row.get("exact") != "1":
                issues.append(f"{selector.get('target_id', '')}:non_exact_prediction:{position}")
                continue
            predicted_value = int_field(op_row, "predicted_value", -1)
            source_offset = int(target["pre_start"]) + position
            rows.append(
                {
                    "promotion_ready": "1",
                    "rank": target_row.get("rank", ""),
                    "slot_rank": str(position),
                    "archive": target_row.get("archive", ""),
                    "archive_tag": target_row.get("archive_tag", ""),
                    "pcx_name": target_row.get("pcx_name", ""),
                    "frontier_id": target_row.get("frontier_id", ""),
                    "span_index": target_row.get("span_index", ""),
                    "op_index": target_row.get("run_index", ""),
                    "source_offset": str(source_offset),
                    "target_offset": str(source_offset),
                    "relative_offset": str(position),
                    "predicted_byte": byte_hex(predicted_value),
                    "best_formula": selector.get("selector_name", ""),
                    "best_guard_key": (
                        f"{selector.get('support_rank', '')}:"
                        f"{selector.get('support_frontier_id', '')}:"
                        f"{selector.get('support_start', '')}"
                    ),
                    "support_rank": selector.get("support_rank", ""),
                    "support_frontier_id": selector.get("support_frontier_id", ""),
                    "support_start": selector.get("support_start", ""),
                    "target_id": selector.get("target_id", ""),
                }
            )
    return rows, issues


def apply_verdict(summary: dict[str, str], selectors: list[dict[str, str]], issues: list[str]) -> None:
    ready_bytes = sum(int_value(row, "missing_source_bytes") for row in selectors)
    first = selectors[0] if selectors else {}
    clean = (
        int_value(summary, "source_added_bytes") == ready_bytes
        and int_value(summary, "source_exact_bytes") == ready_bytes
        and int_value(summary, "source_false_bytes") == 0
        and int_value(summary, "issue_rows") == 0
        and not issues
        and ready_bytes > 0
    )
    summary["selector_ready_rows"] = str(len(selectors))
    summary["selector_ready_bytes"] = str(ready_bytes)
    summary["selected_support_rank"] = first.get("support_rank", "")
    summary["selected_support_frontier_id"] = first.get("support_frontier_id", "")
    summary["selected_support_start"] = first.get("support_start", "")
    if clean:
        summary["review_verdict"] = (
            "frontier80_context_residual_low_payload_row_state_source_single_row_delta_non_oracle_selector_promoted_replay_ready"
        )
        summary["next_probe"] = "review unresolved runs after single-row non-oracle selector promotion"
    else:
        summary["review_verdict"] = (
            "frontier80_context_residual_low_payload_row_state_source_single_row_delta_non_oracle_selector_promoted_replay_weak"
        )
        summary["next_probe"] = "review single-row non-oracle selector promotion misses"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fixtures", type=Path, default=source_replay.DEFAULT_FIXTURES)
    parser.add_argument("--frontiers", type=Path, default=source_replay.DEFAULT_FRONTIERS)
    parser.add_argument("--base-fixtures", type=Path, default=DEFAULT_BASE_FIXTURES)
    parser.add_argument("--clean-decisions", type=Path, default=source_replay.DEFAULT_CLEAN_DECISIONS)
    parser.add_argument("--selector-rows", type=Path, default=DEFAULT_SELECTOR_ROWS)
    parser.add_argument("--operations", type=Path, default=DEFAULT_OPERATIONS)
    parser.add_argument("--runs", type=Path, default=DEFAULT_RUNS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--clean-fixtures", type=Path, default=DEFAULT_CLEAN_FIXTURES)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Single-Row Non-Oracle Delta Selector Promoted Replay",
    )
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    run_rows = read_csv(args.runs)
    manifest_rows = read_csv(args.manifest)
    clean_rows = read_csv(args.clean_fixtures)
    target_runs = load_target_runs(run_rows, manifest_rows, clean_rows, issues)
    targets = target_source_rows(target_runs, issues)
    selectors = ready_selector_rows(read_csv(args.selector_rows))
    target_rows, promotion_issues = promotion_rows(
        selectors=selectors,
        operations=read_csv(args.operations),
        targets=targets,
    )
    issues.extend(promotion_issues)
    summary, fixture_rows, promotions = source_replay.build_rows(
        output_dir=args.output,
        fixture_rows=read_csv(args.fixtures),
        frontier_rows=read_csv(args.frontiers),
        base_fixture_rows=read_csv(args.base_fixtures),
        clean_decision_rows=read_csv(args.clean_decisions),
        target_rows=target_rows,
    )
    summary["scope"] = "frontier80_context_residual_low_payload_row_state_source_single_row_delta_non_oracle_selector_promoted_replay"
    if issues:
        summary["issue_rows"] = str(int_value(summary, "issue_rows") + len(issues))
    apply_verdict(summary, selectors, issues)

    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "fixtures.csv", source_replay.FIXTURE_FIELDNAMES, fixture_rows)
    write_csv(args.output / "promotions.csv", source_replay.PROMOTION_FIELDNAMES, promotions)
    (args.output / "issues.txt").write_text("\n".join(issues))
    (args.output / "index.html").write_text(
        source_replay.build_html(summary, fixture_rows, promotions, args.output, args.title),
        encoding="utf-8",
    )

    print(f"Promoted rows: {summary['promoted_rows']}/{summary['target_rows']}")
    print(f"Added source bytes: {summary['source_added_bytes']}")
    print(f"False bytes: {summary['source_false_bytes']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
