#!/usr/bin/env python3
"""Replay the guarded stride-320 source prefix plus tail-byte candidate."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import lolg_tex_gradient_sequence_high_safe_low_exception_source_byte_guard_promoted_replay as source_replay
from lolg_tex_gap_decoder_frontier80_context_split_residual_low_payload_neighborhood_probe import read_csv
from lolg_tex_gap_opcode_probe import int_value, write_csv


DEFAULT_OUTPUT = Path(
    "output/tex_gap_decoder_frontier80_single_row_non_oracle_selector_promoted_stride320_source_prefix_tail_candidate_replay"
)
DEFAULT_BASE_FIXTURES = Path(
    "output/tex_gap_decoder_frontier80_context_split_residual_low_payload_row_state_source_single_row_delta_non_oracle_selector_promoted_replay/fixtures.csv"
)
DEFAULT_PAIR_ROWS = Path(
    "output/tex_gap_decoder_frontier80_single_row_non_oracle_selector_promoted_stride320_pair_selector_probe/pair_rows.csv"
)
DEFAULT_SOURCE_DEPENDENCY = Path(
    "output/tex_gap_decoder_frontier80_single_row_non_oracle_selector_promoted_stride320_source_dependency_probe"
)
DEFAULT_TAIL_SELECTOR = Path(
    "output/tex_gap_decoder_frontier80_single_row_non_oracle_selector_promoted_stride320_tail_source_selector_probe"
)

SUMMARY_FIELDNAMES = source_replay.SUMMARY_FIELDNAMES + [
    "candidate_source_bytes",
    "prefix_source_bytes",
    "tail_source_bytes",
    "tail_source_offset",
    "tail_source_value",
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
]


def byte_hex(value: int) -> str:
    return f"{value & 0xFF:02x}"


def parse_run_id(run_id: str) -> tuple[str, str]:
    match = re.search(r"_s(?P<span>\d+)_run(?P<run>\d+)$", run_id)
    if not match:
        return "", ""
    return match.group("span"), match.group("run")


def build_target_row(
    pair: dict[str, str],
    *,
    byte_index: int,
    source_offset: int,
    predicted_value: int,
    best_formula: str,
    best_guard_key: str,
) -> dict[str, str]:
    span_index, op_index = parse_run_id(pair.get("target_a", ""))
    return {
        "promotion_ready": "1",
        "rank": pair.get("rank", ""),
        "slot_rank": str(byte_index),
        "archive": pair.get("archive", ""),
        "archive_tag": pair.get("archive_tag", ""),
        "pcx_name": pair.get("pcx_name", ""),
        "frontier_id": pair.get("frontier_id", ""),
        "span_index": span_index,
        "op_index": op_index,
        "source_offset": str(source_offset),
        "target_offset": str(source_offset),
        "relative_offset": str(byte_index),
        "predicted_byte": byte_hex(predicted_value),
        "best_formula": best_formula,
        "best_guard_key": best_guard_key,
        "support_rank": pair.get("rank", ""),
        "support_frontier_id": pair.get("frontier_id", ""),
        "support_start": "",
        "target_id": pair.get("target_a", ""),
    }


def build_target_rows(
    pair: dict[str, str],
    byte_rows: list[dict[str, str]],
    tail_context_rows: list[dict[str, str]],
    tail_summary: dict[str, str],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in byte_rows:
        if row.get("dependency_ready") != "1":
            continue
        support_start = int_value(row, "support_offset") - int_value(row, "byte_index")
        target = build_target_row(
            pair,
            byte_index=int_value(row, "byte_index"),
            source_offset=int_value(row, "source_offset"),
            predicted_value=int_value(row, "source_value"),
            best_formula="stride320_source_prefix_prev32_delta",
            best_guard_key=(
                f"support_start={support_start}:"
                f"delta={row.get('delta', '')}:"
                f"byte_index={row.get('byte_index', '')}"
            ),
        )
        target["support_start"] = str(support_start)
        rows.append(target)
    for row in tail_context_rows:
        byte_index = int_value(row, "source_offset") - int_value(pair, "start_a")
        target = build_target_row(
            pair,
            byte_index=byte_index,
            source_offset=int_value(row, "source_offset"),
            predicted_value=int_value(row, "source_value"),
            best_formula="stride320_tail_constant_value",
            best_guard_key=(
                f"{tail_summary.get('best_selector', '')}:"
                f"exact_support={tail_summary.get('exact_support_rows', '0')}"
            ),
        )
        target["support_start"] = row.get("prev32_support_start", "")
        rows.append(target)
    rows.sort(key=lambda row: int_value(row, "source_offset"))
    return rows


def apply_verdict(summary: dict[str, str], target_rows: list[dict[str, str]], tail_summary: dict[str, str]) -> None:
    candidate_bytes = len(target_rows)
    prefix_bytes = sum(1 for row in target_rows if row.get("best_formula") == "stride320_source_prefix_prev32_delta")
    tail_bytes = sum(1 for row in target_rows if row.get("best_formula") == "stride320_tail_constant_value")
    summary["candidate_source_bytes"] = str(candidate_bytes)
    summary["prefix_source_bytes"] = str(prefix_bytes)
    summary["tail_source_bytes"] = str(tail_bytes)
    summary["tail_source_offset"] = tail_summary.get("tail_source_offset", "")
    summary["tail_source_value"] = tail_summary.get("tail_source_value", "")
    clean = (
        int_value(summary, "source_added_bytes") == candidate_bytes
        and int_value(summary, "source_exact_bytes") == candidate_bytes
        and int_value(summary, "source_false_bytes") == 0
        and int_value(summary, "issue_rows") == 0
        and candidate_bytes > 0
    )
    if clean:
        summary["review_verdict"] = "frontier80_stride320_source_prefix_tail_candidate_replay_ready"
        summary["next_probe"] = "derive target-prefix local delta replay using stride-320 source-prefix candidate base"
    else:
        summary["review_verdict"] = "frontier80_stride320_source_prefix_tail_candidate_replay_weak"
        summary["next_probe"] = "review stride-320 source-prefix plus tail-byte replay candidate misses"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fixtures", type=Path, default=source_replay.DEFAULT_FIXTURES)
    parser.add_argument("--frontiers", type=Path, default=source_replay.DEFAULT_FRONTIERS)
    parser.add_argument("--base-fixtures", type=Path, default=DEFAULT_BASE_FIXTURES)
    parser.add_argument("--clean-decisions", type=Path, default=source_replay.DEFAULT_CLEAN_DECISIONS)
    parser.add_argument("--pair-rows", type=Path, default=DEFAULT_PAIR_ROWS)
    parser.add_argument("--source-dependency", type=Path, default=DEFAULT_SOURCE_DEPENDENCY)
    parser.add_argument("--tail-selector", type=Path, default=DEFAULT_TAIL_SELECTOR)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Stride-320 Source Prefix Tail Candidate Replay",
    )
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    pair_rows = read_csv(args.pair_rows)
    pair = pair_rows[0] if pair_rows else {}
    byte_rows = read_csv(args.source_dependency / "byte_dependency_rows.csv")
    tail_context_rows = read_csv(args.tail_selector / "tail_context_rows.csv")
    tail_summary_rows = read_csv(args.tail_selector / "summary.csv")
    tail_summary = tail_summary_rows[0] if tail_summary_rows else {}
    target_rows = build_target_rows(pair, byte_rows, tail_context_rows, tail_summary)
    summary, fixture_rows, promotions = source_replay.build_rows(
        output_dir=args.output,
        fixture_rows=read_csv(args.fixtures),
        frontier_rows=read_csv(args.frontiers),
        base_fixture_rows=read_csv(args.base_fixtures),
        clean_decision_rows=read_csv(args.clean_decisions),
        target_rows=target_rows,
    )
    summary["scope"] = "frontier80_stride320_source_prefix_tail_candidate_replay"
    apply_verdict(summary, target_rows, tail_summary)

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
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
