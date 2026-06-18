#!/usr/bin/env python3
"""Promote guarded bounded-delta row-state source bytes into fixtures."""

from __future__ import annotations

import argparse
from pathlib import Path

import lolg_tex_gradient_sequence_high_safe_low_exception_source_byte_guard_promoted_replay as source_replay
from lolg_tex_gap_decoder_frontier80_context_split_residual_low_payload_neighborhood_probe import (
    load_target_runs,
    read_csv,
)
from lolg_tex_gap_decoder_frontier80_context_split_residual_low_payload_row_state_source_delta_selector_probe import (
    GLOBAL_STRATEGIES,
    bounded_records,
    group_key,
    mode_deltas,
)
from lolg_tex_gap_decoder_frontier80_context_split_residual_low_payload_row_state_source_prereq_probe import (
    support_windows,
    target_source_rows,
)
from lolg_tex_gap_opcode_probe import int_value, write_csv


DEFAULT_OUTPUT = Path(
    "output/tex_gap_decoder_frontier80_context_split_residual_low_payload_row_state_source_delta_guard_promoted_replay"
)
DEFAULT_BASE_FIXTURES = Path(
    "output/tex_gap_decoder_frontier80_context_split_residual_second_fixture_replay/fixtures.csv"
)
DEFAULT_GUARD_ROWS = Path(
    "output/tex_gap_decoder_frontier80_context_split_residual_low_payload_row_state_source_delta_guard_probe/guard_rows.csv"
)
DEFAULT_RUNS = Path("output/tex_gap_decoder_unresolved_run_probe_frontier80_context_split_residual_second_replay/runs.csv")
DEFAULT_MANIFEST = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_CLEAN_FIXTURES = Path(
    "output/tex_gap_decoder_frontier80_context_split_residual_second_fixture_replay/fixtures.csv"
)

SUMMARY_FIELDNAMES = source_replay.SUMMARY_FIELDNAMES + [
    "guard_ready_rows",
    "guard_ready_bytes",
    "residual_rows",
    "residual_bytes",
    "review_verdict",
    "next_probe",
]


def add_delta(value: int, delta: int) -> int:
    return (value + delta) & 0xFF


def byte_hex(value: int) -> str:
    return f"{value & 0xFF:02x}"


def target_id(row: dict[str, object]) -> str:
    target = row["target"]
    assert isinstance(target, dict)
    return target.get("target_id", "")


def matching_records(
    records: list[dict[str, object]],
    guard: dict[str, str],
) -> list[dict[str, object]]:
    strategy = guard.get("strategy", "")
    wanted_target = guard.get("target_id", "")
    wanted_group = guard.get("best_group_key", "")
    target_records = [record for record in records if target_id(record["target"]) == wanted_target]
    scope_records = records if strategy in GLOBAL_STRATEGIES else target_records
    group = []
    for record in scope_records:
        base = record["base"]
        assert isinstance(base, dict)
        if group_key(base, strategy) == wanted_group:
            group.append(record)
    return group


def selected_record(group: list[dict[str, object]], guard: dict[str, str]) -> dict[str, object] | None:
    for record in group:
        base = record["base"]
        assert isinstance(base, dict)
        if (
            base.get("support_rank") == guard.get("best_support_rank")
            and base.get("support_frontier_id") == guard.get("best_support_frontier_id")
            and base.get("support_start") == guard.get("best_support_start")
        ):
            return record
    return None


def promotion_rows(
    *,
    guard_rows: list[dict[str, str]],
    records: list[dict[str, object]],
) -> tuple[list[dict[str, str]], list[str]]:
    rows: list[dict[str, str]] = []
    issues: list[str] = []
    ready_guards = [row for row in guard_rows if row.get("guard_status") == "ready"]
    for guard in ready_guards:
        group = matching_records(records, guard)
        record = selected_record(group, guard)
        if not group:
            issues.append(f"{guard.get('target_id', '')}:missing_guard_group")
            continue
        if record is None:
            issues.append(f"{guard.get('target_id', '')}:missing_selected_record")
            continue
        target = record["target"]
        support = record["support"]
        base = record["base"]
        assert isinstance(target, dict)
        assert isinstance(support, dict)
        assert isinstance(base, dict)
        target_row = target["target"]
        missing = target["missing"]
        assert isinstance(target_row, dict)
        assert isinstance(missing, list)
        support_data = support["data"]
        assert isinstance(support_data, bytes)
        mode_positions = list(range(32)) if guard.get("strategy", "") in GLOBAL_STRATEGIES else missing
        modes = mode_deltas(group, mode_positions)
        for position in missing:
            source_offset = int(target["pre_start"]) + int(position)
            predicted = add_delta(support_data[position], modes[position])
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
                    "predicted_byte": byte_hex(predicted),
                    "best_formula": "bounded_delta_row_state_source",
                    "best_guard_key": f"{guard.get('strategy', '')}:{guard.get('best_group_key', '')}",
                    "support_rank": base.get("support_rank", ""),
                    "support_frontier_id": base.get("support_frontier_id", ""),
                    "support_start": base.get("support_start", ""),
                    "target_id": target_row.get("target_id", ""),
                }
            )
    return rows, issues


def summary_verdict(summary: dict[str, str], guard_rows: list[dict[str, str]], issues: list[str]) -> None:
    ready_rows = [row for row in guard_rows if row.get("guard_status") == "ready"]
    residual_rows = [row for row in guard_rows if row.get("guard_status") == "residual"]
    ready_bytes = sum(int_value(row, "missing_source_bytes") for row in ready_rows)
    residual_bytes = sum(int_value(row, "missing_source_bytes") for row in residual_rows)
    summary["guard_ready_rows"] = str(len(ready_rows))
    summary["guard_ready_bytes"] = str(ready_bytes)
    summary["residual_rows"] = str(len(residual_rows))
    summary["residual_bytes"] = str(residual_bytes)
    clean = (
        int_value(summary, "source_added_bytes") == ready_bytes
        and int_value(summary, "source_exact_bytes") == ready_bytes
        and int_value(summary, "source_false_bytes") == 0
        and not issues
    )
    if clean and residual_bytes:
        summary["review_verdict"] = (
            "frontier80_context_residual_low_payload_row_state_source_delta_guard_promoted_replay_partial_ready"
        )
        summary["next_probe"] = "review residual row-state source bytes after guarded selector promotion"
    elif clean:
        summary["review_verdict"] = "frontier80_context_residual_low_payload_row_state_source_delta_guard_promoted_replay_ready"
        summary["next_probe"] = "review unresolved runs after guarded row-state source promotion"
    else:
        summary["review_verdict"] = "frontier80_context_residual_low_payload_row_state_source_delta_guard_promoted_replay_weak"
        summary["next_probe"] = "review guarded bounded-delta selector promotion misses"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fixtures", type=Path, default=source_replay.DEFAULT_FIXTURES)
    parser.add_argument("--frontiers", type=Path, default=source_replay.DEFAULT_FRONTIERS)
    parser.add_argument("--base-fixtures", type=Path, default=DEFAULT_BASE_FIXTURES)
    parser.add_argument("--clean-decisions", type=Path, default=source_replay.DEFAULT_CLEAN_DECISIONS)
    parser.add_argument("--guard-rows", type=Path, default=DEFAULT_GUARD_ROWS)
    parser.add_argument("--runs", type=Path, default=DEFAULT_RUNS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--clean-fixtures", type=Path, default=DEFAULT_CLEAN_FIXTURES)
    parser.add_argument("--min-known", type=int, default=24)
    parser.add_argument("--min-high", type=int, default=28)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Low Payload Row-State Source Delta Guard Promoted Replay",
    )
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    run_rows = read_csv(args.runs)
    manifest_rows = read_csv(args.manifest)
    clean_rows = read_csv(args.clean_fixtures)
    target_runs = load_target_runs(run_rows, manifest_rows, clean_rows, issues)
    targets = target_source_rows(target_runs, issues)
    supports = support_windows(manifest_rows, clean_rows, issues, min_known=args.min_known, min_high=args.min_high)
    records = bounded_records(targets, supports)
    guard_rows = read_csv(args.guard_rows)
    target_rows, promotion_issues = promotion_rows(guard_rows=guard_rows, records=records)
    issues.extend(promotion_issues)

    summary, fixture_rows, promotions = source_replay.build_rows(
        output_dir=args.output,
        fixture_rows=read_csv(args.fixtures),
        frontier_rows=read_csv(args.frontiers),
        base_fixture_rows=read_csv(args.base_fixtures),
        clean_decision_rows=read_csv(args.clean_decisions),
        target_rows=target_rows,
    )
    summary["scope"] = "frontier80_context_residual_low_payload_row_state_source_delta_guard_promoted_replay"
    if issues:
        summary["issue_rows"] = str(int_value(summary, "issue_rows") + len(issues))
    summary_verdict(summary, guard_rows, issues)

    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "fixtures.csv", source_replay.FIXTURE_FIELDNAMES, fixture_rows)
    write_csv(args.output / "promotions.csv", source_replay.PROMOTION_FIELDNAMES, promotions)
    (args.output / "issues.txt").write_text("\n".join(issues))
    (args.output / "index.html").write_text(
        source_replay.build_html(summary, fixture_rows, promotions, args.output, args.title),
        encoding="utf-8",
    )

    print(f"Guard promoted rows: {summary['promoted_rows']}/{summary['target_rows']}")
    print(f"Added source bytes: {summary['source_added_bytes']}")
    print(f"False bytes: {summary['source_false_bytes']}")
    print(f"Residual bytes: {summary['residual_bytes']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
