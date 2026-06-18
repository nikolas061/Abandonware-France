#!/usr/bin/env python3
"""Replay stride-320 outlier target values with same-PCX support and cross-PCX guards."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

import lolg_tex_gradient_sequence_high_safe_low_exception_source_byte_guard_promoted_replay as source_replay
from lolg_tex_gap_decoder_frontier80_context_split_residual_low_payload_neighborhood_probe import read_csv
from lolg_tex_gap_opcode_probe import int_value, write_csv


DEFAULT_OUTPUT = Path(
    "output/tex_gap_decoder_frontier80_single_row_non_oracle_selector_promoted_stride320_outlier_target_value_guarded_replay"
)
DEFAULT_BASE_FIXTURES = Path(
    "output/tex_gap_decoder_frontier80_single_row_non_oracle_selector_promoted_stride320_remaining_target_delta_candidate_replay/fixtures.csv"
)
DEFAULT_PAIR_ROWS = Path(
    "output/tex_gap_decoder_frontier80_single_row_non_oracle_selector_promoted_stride320_pair_selector_probe/pair_rows.csv"
)
DEFAULT_TARGET_VALUE_DEPENDENCY = Path(
    "output/tex_gap_decoder_frontier80_single_row_non_oracle_selector_promoted_stride320_outlier_target_value_dependency_probe"
)
DEFAULT_CROSS_PCX_GUARD = Path(
    "output/tex_gap_decoder_frontier80_single_row_non_oracle_selector_promoted_stride320_outlier_target_cross_pcx_guard_probe"
)

SUMMARY_FIELDNAMES = source_replay.SUMMARY_FIELDNAMES + [
    "candidate_target_bytes",
    "same_pcx_exact_target_bytes",
    "cross_pcx_guard_target_bytes",
    "target_offset_min",
    "target_offset_max",
    "target_values",
    "selector_kinds",
    "review_verdict",
    "next_probe",
]

TARGET_FIELDNAMES = [
    "promotion_ready",
    "rank",
    "slot_rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "span_index",
    "op_index",
    "source_offset",
    "target_offset",
    "relative_offset",
    "predicted_byte",
    "best_formula",
    "best_guard_key",
    "support_rank",
    "support_frontier_id",
    "support_start",
    "target_id",
    "target_value",
    "selector_kind",
    "support_value",
    "support_delta",
    "same_pcx_exact_support_rows",
    "cross_pcx_exact_support_rows",
    "same_pcx_le4_bridge_rows",
    "local_note",
]


def byte_hex(value: int) -> str:
    return f"{value & 0xFF:02x}"


def parse_run_id(run_id: str) -> tuple[str, str]:
    match = re.search(r"_s(?P<span>\d+)_run(?P<run>\d+)$", run_id)
    if not match:
        return "", ""
    return match.group("span"), match.group("run")


def cross_pcx_guard_by_offset(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row.get("target_offset", ""): row for row in rows if row.get("guard_ready") == "1"}


def build_target_rows(
    pair: dict[str, str],
    candidate_rows: list[dict[str, str]],
    guard_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    target_span, target_op = parse_run_id(pair.get("target_b", ""))
    guards = cross_pcx_guard_by_offset(guard_rows)
    rows: list[dict[str, str]] = []
    for candidate in candidate_rows:
        target_value = int_value(candidate, "target_value")
        target_offset = candidate.get("target_offset", "")
        blocker = candidate.get("blocker_reason", "")
        guard = guards.get(target_offset)
        if blocker == "ready_same_pcx_exact_support":
            best_formula = "stride320_outlier_target_same_pcx_exact_value_support"
            best_guard_key = (
                f"target_value={candidate.get('target_value', '')}:"
                f"same_pcx_exact={candidate.get('same_pcx_exact_support_rows', '0')}:"
                f"same_fixture_exact={candidate.get('same_fixture_exact_support_rows', '0')}:"
                f"byte_index={candidate.get('byte_index', '')}"
            )
            support_rank = candidate.get("best_support_rank", "")
            support_frontier_id = candidate.get("best_support_frontier_id", "")
            support_start = candidate.get("best_support_offset", "")
            support_value = candidate.get("best_support_value", "")
            support_delta = candidate.get("best_support_delta", "")
            selector_kind = "same_pcx_exact"
            cross_pcx_rows = "0"
            same_pcx_bridge_rows = "0"
        elif blocker == "cross_pcx_exact_support_only" and guard:
            best_formula = guard.get(
                "best_formula",
                "stride320_outlier_target_cross_pcx_exact_with_same_pcx_le4_bridge",
            )
            best_guard_key = guard.get("best_guard_key", "")
            support_rank = guard.get("best_exact_rank", "")
            support_frontier_id = guard.get("best_exact_frontier_id", "")
            support_start = guard.get("best_exact_offset", "")
            support_value = guard.get("bridge_support_value", "")
            support_delta = guard.get("bridge_delta", "")
            selector_kind = "cross_pcx_guard_bridge"
            cross_pcx_rows = guard.get("exact_cross_pcx_support_rows", "0")
            same_pcx_bridge_rows = guard.get("same_pcx_le4_bridge_rows", "0")
        else:
            continue
        rows.append(
            {
                "promotion_ready": "1",
                "rank": pair.get("rank", ""),
                "slot_rank": candidate.get("byte_index", ""),
                "archive": pair.get("archive", ""),
                "archive_tag": pair.get("archive_tag", ""),
                "pcx_name": pair.get("pcx_name", ""),
                "frontier_id": pair.get("frontier_id", ""),
                "span_index": target_span,
                "op_index": target_op,
                "source_offset": target_offset,
                "target_offset": target_offset,
                "relative_offset": candidate.get("byte_index", ""),
                "predicted_byte": byte_hex(target_value),
                "best_formula": best_formula,
                "best_guard_key": best_guard_key,
                "support_rank": support_rank,
                "support_frontier_id": support_frontier_id,
                "support_start": support_start,
                "target_id": pair.get("target_b", ""),
                "target_value": byte_hex(target_value),
                "selector_kind": selector_kind,
                "support_value": support_value,
                "support_delta": support_delta,
                "same_pcx_exact_support_rows": candidate.get("same_pcx_exact_support_rows", "0"),
                "cross_pcx_exact_support_rows": cross_pcx_rows,
                "same_pcx_le4_bridge_rows": same_pcx_bridge_rows,
                "local_note": candidate.get("local_note", ""),
            }
        )
    rows.sort(key=lambda row: int_value(row, "target_offset"))
    return rows


def apply_verdict(summary: dict[str, str], target_rows: list[dict[str, str]]) -> None:
    candidate_bytes = len(target_rows)
    same_pcx_exact_bytes = sum(1 for row in target_rows if row.get("selector_kind") == "same_pcx_exact")
    cross_pcx_guard_bytes = sum(1 for row in target_rows if row.get("selector_kind") == "cross_pcx_guard_bridge")
    target_offsets = [int_value(row, "target_offset") for row in target_rows]
    target_values = Counter(row.get("target_value", "") for row in target_rows if row.get("target_value"))
    selector_kinds = Counter(row.get("selector_kind", "") for row in target_rows if row.get("selector_kind"))
    summary["candidate_target_bytes"] = str(candidate_bytes)
    summary["same_pcx_exact_target_bytes"] = str(same_pcx_exact_bytes)
    summary["cross_pcx_guard_target_bytes"] = str(cross_pcx_guard_bytes)
    summary["target_offset_min"] = str(min(target_offsets)) if target_offsets else ""
    summary["target_offset_max"] = str(max(target_offsets)) if target_offsets else ""
    summary["target_values"] = json.dumps(target_values, sort_keys=True, separators=(",", ":"))
    summary["selector_kinds"] = json.dumps(selector_kinds, sort_keys=True, separators=(",", ":"))
    clean = (
        int_value(summary, "source_added_bytes") == candidate_bytes
        and int_value(summary, "source_exact_bytes") == candidate_bytes
        and int_value(summary, "source_false_bytes") == 0
        and int_value(summary, "issue_rows") == 0
        and candidate_bytes > 0
    )
    if clean:
        summary["review_verdict"] = "frontier80_stride320_outlier_target_value_guarded_replay_ready"
        summary["next_probe"] = "profile residual clean gaps after stride-320 outlier target replay"
    else:
        summary["review_verdict"] = "frontier80_stride320_outlier_target_value_guarded_replay_weak"
        summary["next_probe"] = "review guarded stride-320 target-value replay misses"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fixtures", type=Path, default=source_replay.DEFAULT_FIXTURES)
    parser.add_argument("--frontiers", type=Path, default=source_replay.DEFAULT_FRONTIERS)
    parser.add_argument("--base-fixtures", type=Path, default=DEFAULT_BASE_FIXTURES)
    parser.add_argument("--clean-decisions", type=Path, default=source_replay.DEFAULT_CLEAN_DECISIONS)
    parser.add_argument("--pair-rows", type=Path, default=DEFAULT_PAIR_ROWS)
    parser.add_argument("--target-value-dependency", type=Path, default=DEFAULT_TARGET_VALUE_DEPENDENCY)
    parser.add_argument("--cross-pcx-guard", type=Path, default=DEFAULT_CROSS_PCX_GUARD)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Stride-320 Outlier Target Value Guarded Replay",
    )
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    pair_rows = read_csv(args.pair_rows)
    pair = pair_rows[0] if pair_rows else {}
    target_rows = build_target_rows(
        pair,
        read_csv(args.target_value_dependency / "candidate_outlier_rows.csv"),
        read_csv(args.cross_pcx_guard / "guard_rows.csv"),
    )
    summary, fixture_rows, promotions = source_replay.build_rows(
        output_dir=args.output,
        fixture_rows=read_csv(args.fixtures),
        frontier_rows=read_csv(args.frontiers),
        base_fixture_rows=read_csv(args.base_fixtures),
        clean_decision_rows=read_csv(args.clean_decisions),
        target_rows=target_rows,
    )
    summary["scope"] = "frontier80_stride320_outlier_target_value_guarded_replay"
    apply_verdict(summary, target_rows)

    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "target_rows.csv", TARGET_FIELDNAMES, target_rows)
    write_csv(args.output / "fixtures.csv", source_replay.FIXTURE_FIELDNAMES, fixture_rows)
    write_csv(args.output / "promotions.csv", source_replay.PROMOTION_FIELDNAMES, promotions)
    (args.output / "index.html").write_text(
        source_replay.build_html(summary, fixture_rows, promotions, args.output, args.title),
        encoding="utf-8",
    )

    print(f"Candidate target bytes: {summary['candidate_target_bytes']}")
    print(f"Added target bytes: {summary['source_added_bytes']}")
    print(f"False bytes: {summary['source_false_bytes']}")
    print(f"Same-PCX exact target bytes: {summary['same_pcx_exact_target_bytes']}")
    print(f"Cross-PCX guard target bytes: {summary['cross_pcx_guard_target_bytes']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
