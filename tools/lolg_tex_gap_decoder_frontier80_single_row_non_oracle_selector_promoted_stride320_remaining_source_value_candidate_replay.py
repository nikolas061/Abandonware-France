#!/usr/bin/env python3
"""Replay remaining stride-320 source values from exact support plus fallback selectors."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import lolg_tex_gradient_sequence_high_safe_low_exception_source_byte_guard_promoted_replay as source_replay
from lolg_tex_gap_decoder_frontier80_context_split_residual_low_payload_neighborhood_probe import read_csv
from lolg_tex_gap_opcode_probe import int_value, write_csv


DEFAULT_OUTPUT = Path(
    "output/tex_gap_decoder_frontier80_single_row_non_oracle_selector_promoted_stride320_remaining_source_value_candidate_replay"
)
DEFAULT_BASE_FIXTURES = Path(
    "output/tex_gap_decoder_frontier80_single_row_non_oracle_selector_promoted_stride320_target_prefix_delta_candidate_replay/fixtures.csv"
)
DEFAULT_PAIR_ROWS = Path(
    "output/tex_gap_decoder_frontier80_single_row_non_oracle_selector_promoted_stride320_pair_selector_probe/pair_rows.csv"
)
DEFAULT_REMAINING_SOURCE_DEPENDENCY = Path(
    "output/tex_gap_decoder_frontier80_single_row_non_oracle_selector_promoted_stride320_remaining_source_dependency_probe"
)
DEFAULT_REMAINING_SOURCE_FALLBACK = Path(
    "output/tex_gap_decoder_frontier80_single_row_non_oracle_selector_promoted_stride320_remaining_source_fallback_probe"
)

SUMMARY_FIELDNAMES = source_replay.SUMMARY_FIELDNAMES + [
    "candidate_source_bytes",
    "exact_source_bytes",
    "fallback_source_bytes",
    "source_offset_min",
    "source_offset_max",
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
    "support_value",
    "support_delta",
    "selector_kind",
]


def byte_hex(value: int) -> str:
    return f"{value & 0xFF:02x}"


def parse_run_id(run_id: str) -> tuple[str, str]:
    match = re.search(r"_s(?P<span>\d+)_run(?P<run>\d+)$", run_id)
    if not match:
        return "", ""
    return match.group("span"), match.group("run")


def fallback_by_offset(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row.get("source_offset", ""): row for row in rows if row.get("fallback_ready") == "1"}


def build_target_rows(
    pair: dict[str, str],
    candidate_rows: list[dict[str, str]],
    fallback_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    span_index, op_index = parse_run_id(pair.get("target_a", ""))
    fallback_lookup = fallback_by_offset(fallback_rows)
    rows: list[dict[str, str]] = []
    for candidate in candidate_rows:
        if candidate.get("source_missing") != "1":
            continue
        source_offset = candidate.get("source_offset", "")
        fallback = fallback_lookup.get(source_offset)
        if int_value(candidate, "exact_support_rows") <= 0 and not fallback:
            continue
        predicted_value = int_value(candidate, "source_value")
        if fallback:
            best_formula = fallback.get("best_formula", "stride320_remaining_source_same_pcx_le4_delta_fallback")
            best_guard_key = fallback.get("best_guard_key", "")
            support_rank = fallback.get("support_rank", "")
            support_frontier_id = fallback.get("support_frontier_id", "")
            support_start = fallback.get("support_offset", "")
            support_value = fallback.get("support_value", "")
            support_delta = fallback.get("support_delta", "")
            selector_kind = "fallback_le4"
        else:
            best_formula = "stride320_remaining_source_exact_value_support"
            best_guard_key = (
                f"source_value={candidate.get('source_value', '')}:"
                f"exact_support={candidate.get('exact_support_rows', '0')}:"
                f"same_pcx_exact={candidate.get('same_pcx_exact_support_rows', '0')}"
            )
            support_rank = candidate.get("best_support_rank", "")
            support_frontier_id = candidate.get("best_support_frontier_id", "")
            support_start = candidate.get("best_support_offset", "")
            support_value = candidate.get("best_support_value", "")
            support_delta = candidate.get("best_support_delta", "")
            selector_kind = "exact_value"
        rows.append(
            {
                "promotion_ready": "1",
                "rank": pair.get("rank", ""),
                "slot_rank": candidate.get("byte_index", ""),
                "archive": pair.get("archive", ""),
                "archive_tag": pair.get("archive_tag", ""),
                "pcx_name": pair.get("pcx_name", ""),
                "frontier_id": pair.get("frontier_id", ""),
                "span_index": span_index,
                "op_index": op_index,
                "source_offset": source_offset,
                "target_offset": source_offset,
                "relative_offset": str(int_value(candidate, "source_offset") - int_value(pair, "start_a")),
                "predicted_byte": byte_hex(predicted_value),
                "best_formula": best_formula,
                "best_guard_key": best_guard_key,
                "support_rank": support_rank,
                "support_frontier_id": support_frontier_id,
                "support_start": support_start,
                "target_id": pair.get("target_a", ""),
                "support_value": support_value,
                "support_delta": support_delta,
                "selector_kind": selector_kind,
            }
        )
    rows.sort(key=lambda row: int_value(row, "source_offset"))
    return rows


def apply_verdict(summary: dict[str, str], target_rows: list[dict[str, str]]) -> None:
    offsets = [int_value(row, "source_offset") for row in target_rows]
    candidate_bytes = len(target_rows)
    exact_bytes = sum(1 for row in target_rows if row.get("selector_kind") == "exact_value")
    fallback_bytes = sum(1 for row in target_rows if row.get("selector_kind") == "fallback_le4")
    summary["candidate_source_bytes"] = str(candidate_bytes)
    summary["exact_source_bytes"] = str(exact_bytes)
    summary["fallback_source_bytes"] = str(fallback_bytes)
    summary["source_offset_min"] = str(min(offsets)) if offsets else ""
    summary["source_offset_max"] = str(max(offsets)) if offsets else ""
    clean = (
        int_value(summary, "source_added_bytes") == candidate_bytes
        and int_value(summary, "source_exact_bytes") == candidate_bytes
        and int_value(summary, "source_false_bytes") == 0
        and int_value(summary, "issue_rows") == 0
        and candidate_bytes > 0
    )
    if clean:
        summary["review_verdict"] = "frontier80_stride320_remaining_source_value_candidate_replay_ready"
        summary["next_probe"] = "build remaining stride-320 local-delta target replay from value-selector source base"
    else:
        summary["review_verdict"] = "frontier80_stride320_remaining_source_value_candidate_replay_weak"
        summary["next_probe"] = "review remaining stride-320 source value replay misses"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fixtures", type=Path, default=source_replay.DEFAULT_FIXTURES)
    parser.add_argument("--frontiers", type=Path, default=source_replay.DEFAULT_FRONTIERS)
    parser.add_argument("--base-fixtures", type=Path, default=DEFAULT_BASE_FIXTURES)
    parser.add_argument("--clean-decisions", type=Path, default=source_replay.DEFAULT_CLEAN_DECISIONS)
    parser.add_argument("--pair-rows", type=Path, default=DEFAULT_PAIR_ROWS)
    parser.add_argument("--remaining-source-dependency", type=Path, default=DEFAULT_REMAINING_SOURCE_DEPENDENCY)
    parser.add_argument("--remaining-source-fallback", type=Path, default=DEFAULT_REMAINING_SOURCE_FALLBACK)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Stride-320 Remaining Source Value Candidate Replay",
    )
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    pair_rows = read_csv(args.pair_rows)
    pair = pair_rows[0] if pair_rows else {}
    target_rows = build_target_rows(
        pair,
        read_csv(args.remaining_source_dependency / "candidate_source_rows.csv"),
        read_csv(args.remaining_source_fallback / "fallback_rows.csv"),
    )
    summary, fixture_rows, promotions = source_replay.build_rows(
        output_dir=args.output,
        fixture_rows=read_csv(args.fixtures),
        frontier_rows=read_csv(args.frontiers),
        base_fixture_rows=read_csv(args.base_fixtures),
        clean_decision_rows=read_csv(args.clean_decisions),
        target_rows=target_rows,
    )
    summary["scope"] = "frontier80_stride320_remaining_source_value_candidate_replay"
    apply_verdict(summary, target_rows)

    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "target_rows.csv", TARGET_FIELDNAMES, target_rows)
    write_csv(args.output / "fixtures.csv", source_replay.FIXTURE_FIELDNAMES, fixture_rows)
    write_csv(args.output / "promotions.csv", source_replay.PROMOTION_FIELDNAMES, promotions)
    (args.output / "index.html").write_text(
        source_replay.build_html(summary, fixture_rows, promotions, args.output, args.title),
        encoding="utf-8",
    )

    print(f"Candidate source bytes: {summary['candidate_source_bytes']}")
    print(f"Added source bytes: {summary['source_added_bytes']}")
    print(f"False bytes: {summary['source_false_bytes']}")
    print(f"Fallback source bytes: {summary['fallback_source_bytes']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
