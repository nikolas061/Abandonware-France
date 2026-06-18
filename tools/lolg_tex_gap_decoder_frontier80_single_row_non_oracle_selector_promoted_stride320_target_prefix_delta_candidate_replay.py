#!/usr/bin/env python3
"""Replay the stride-320 target prefix from the guarded source-prefix candidate."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import lolg_tex_gradient_sequence_high_safe_low_exception_source_byte_guard_promoted_replay as source_replay
from lolg_tex_gap_decoder_frontier80_context_split_residual_low_payload_neighborhood_probe import read_csv
from lolg_tex_gap_opcode_probe import int_value, write_csv


DEFAULT_OUTPUT = Path(
    "output/tex_gap_decoder_frontier80_single_row_non_oracle_selector_promoted_stride320_target_prefix_delta_candidate_replay"
)
DEFAULT_BASE_FIXTURES = Path(
    "output/tex_gap_decoder_frontier80_single_row_non_oracle_selector_promoted_stride320_source_prefix_tail_candidate_replay/fixtures.csv"
)
DEFAULT_PAIR_ROWS = Path(
    "output/tex_gap_decoder_frontier80_single_row_non_oracle_selector_promoted_stride320_pair_selector_probe/pair_rows.csv"
)
DEFAULT_LOCAL_DELTA_PROFILE = Path(
    "output/tex_gap_decoder_frontier80_single_row_non_oracle_selector_promoted_stride320_local_delta_transform_probe/byte_profile.csv"
)
DEFAULT_SOURCE_PREFIX_PROMOTIONS = Path(
    "output/tex_gap_decoder_frontier80_single_row_non_oracle_selector_promoted_stride320_source_prefix_tail_candidate_replay/promotions.csv"
)

SUMMARY_FIELDNAMES = source_replay.SUMMARY_FIELDNAMES + [
    "candidate_target_bytes",
    "target_prefix_bytes",
    "source_guard_bytes",
    "source_dependency_bytes",
    "source_start",
    "target_start",
    "delta_min",
    "delta_max",
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
    "dependency_source_offset",
    "dependency_source_value",
    "delta",
    "target_value",
    "local_note",
]


def byte_hex(value: int) -> str:
    return f"{value & 0xFF:02x}"


def parse_hex_byte(text: str) -> int | None:
    try:
        return int(text, 16)
    except ValueError:
        return None


def optional_int(row: dict[str, str], key: str, default: int = -1) -> int:
    try:
        return int(row.get(key, ""))
    except ValueError:
        return default


def parse_run_id(run_id: str) -> tuple[str, str]:
    match = re.search(r"_s(?P<span>\d+)_run(?P<run>\d+)$", run_id)
    if not match:
        return "", ""
    return match.group("span"), match.group("run")


def source_guard_map(promotions: list[dict[str, str]]) -> dict[tuple[str, str, str, int], dict[str, str]]:
    guarded: dict[tuple[str, str, str, int], dict[str, str]] = {}
    for row in promotions:
        if row.get("issues"):
            continue
        if int_value(row, "source_false_bytes") != 0:
            continue
        if not (int_value(row, "source_exact_bytes") or int_value(row, "skipped_known_bytes")):
            continue
        guarded[
            (
                row.get("archive", ""),
                row.get("pcx_name", ""),
                row.get("frontier_id", ""),
                optional_int(row, "absolute_offset"),
            )
        ] = row
    return guarded


def build_target_rows(
    pair: dict[str, str],
    byte_profile_rows: list[dict[str, str]],
    source_promotions: list[dict[str, str]],
) -> list[dict[str, str]]:
    target_span, target_op = parse_run_id(pair.get("target_b", ""))
    guards = source_guard_map(source_promotions)
    rows: list[dict[str, str]] = []
    for profile in byte_profile_rows:
        if profile.get("bounded_prefix") != "1":
            continue
        source_offset = int_value(profile, "source_offset")
        target_offset = int_value(profile, "target_offset")
        source_value = int_value(profile, "source_value")
        delta = int_value(profile, "delta")
        predicted = (source_value + delta) & 0xFF
        if predicted != int_value(profile, "target_value"):
            continue
        guard = guards.get(
            (
                pair.get("archive", ""),
                pair.get("pcx_name", ""),
                pair.get("frontier_id", ""),
                source_offset,
            )
        )
        if not guard:
            continue
        guard_value = parse_hex_byte(guard.get("predicted_byte", ""))
        if guard_value != source_value:
            continue
        byte_index = int_value(profile, "byte_index")
        rows.append(
            {
                "promotion_ready": "1",
                "rank": pair.get("rank", ""),
                "slot_rank": str(byte_index),
                "archive": pair.get("archive", ""),
                "archive_tag": pair.get("archive_tag", ""),
                "pcx_name": pair.get("pcx_name", ""),
                "frontier_id": pair.get("frontier_id", ""),
                "span_index": target_span,
                "op_index": target_op,
                "source_offset": str(target_offset),
                "target_offset": str(target_offset),
                "relative_offset": str(byte_index),
                "predicted_byte": byte_hex(predicted),
                "best_formula": "stride320_target_prefix_local_delta",
                "best_guard_key": (
                    f"source_start={pair.get('start_a', '')}:"
                    f"target_start={pair.get('start_b', '')}:"
                    f"source_offset={source_offset}:"
                    f"delta={delta}:"
                    f"byte_index={byte_index}:"
                    "source_guard=source_prefix_tail"
                ),
                "support_rank": pair.get("rank", ""),
                "support_frontier_id": pair.get("frontier_id", ""),
                "support_start": pair.get("start_a", ""),
                "target_id": pair.get("target_b", ""),
                "dependency_source_offset": str(source_offset),
                "dependency_source_value": byte_hex(source_value),
                "delta": str(delta),
                "target_value": byte_hex(int_value(profile, "target_value")),
                "local_note": profile.get("local_note", ""),
            }
        )
    rows.sort(key=lambda row: int_value(row, "source_offset"))
    return rows


def apply_verdict(summary: dict[str, str], target_rows: list[dict[str, str]], pair: dict[str, str]) -> None:
    candidate_bytes = len(target_rows)
    deltas = [int_value(row, "delta") for row in target_rows]
    summary["candidate_target_bytes"] = str(candidate_bytes)
    summary["target_prefix_bytes"] = str(
        sum(1 for row in target_rows if row.get("best_formula") == "stride320_target_prefix_local_delta")
    )
    summary["source_guard_bytes"] = str(candidate_bytes)
    summary["source_dependency_bytes"] = str(
        len({row.get("dependency_source_offset", "") for row in target_rows if row.get("dependency_source_offset")})
    )
    summary["source_start"] = pair.get("start_a", "")
    summary["target_start"] = pair.get("start_b", "")
    summary["delta_min"] = str(min(deltas)) if deltas else ""
    summary["delta_max"] = str(max(deltas)) if deltas else ""
    clean = (
        int_value(summary, "source_added_bytes") == candidate_bytes
        and int_value(summary, "source_exact_bytes") == candidate_bytes
        and int_value(summary, "source_false_bytes") == 0
        and int_value(summary, "issue_rows") == 0
        and candidate_bytes > 0
    )
    if clean:
        summary["review_verdict"] = "frontier80_stride320_target_prefix_delta_candidate_replay_ready"
        summary["next_probe"] = "derive remaining stride-320 local-delta source dependencies after target-prefix replay"
    else:
        summary["review_verdict"] = "frontier80_stride320_target_prefix_delta_candidate_replay_weak"
        summary["next_probe"] = "review stride-320 target-prefix delta replay candidate misses"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fixtures", type=Path, default=source_replay.DEFAULT_FIXTURES)
    parser.add_argument("--frontiers", type=Path, default=source_replay.DEFAULT_FRONTIERS)
    parser.add_argument("--base-fixtures", type=Path, default=DEFAULT_BASE_FIXTURES)
    parser.add_argument("--clean-decisions", type=Path, default=source_replay.DEFAULT_CLEAN_DECISIONS)
    parser.add_argument("--pair-rows", type=Path, default=DEFAULT_PAIR_ROWS)
    parser.add_argument("--local-delta-profile", type=Path, default=DEFAULT_LOCAL_DELTA_PROFILE)
    parser.add_argument("--source-prefix-promotions", type=Path, default=DEFAULT_SOURCE_PREFIX_PROMOTIONS)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Stride-320 Target Prefix Delta Candidate Replay",
    )
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    pair_rows = read_csv(args.pair_rows)
    pair = pair_rows[0] if pair_rows else {}
    target_rows = build_target_rows(
        pair,
        read_csv(args.local_delta_profile),
        read_csv(args.source_prefix_promotions),
    )
    summary, fixture_rows, promotions = source_replay.build_rows(
        output_dir=args.output,
        fixture_rows=read_csv(args.fixtures),
        frontier_rows=read_csv(args.frontiers),
        base_fixture_rows=read_csv(args.base_fixtures),
        clean_decision_rows=read_csv(args.clean_decisions),
        target_rows=target_rows,
    )
    summary["scope"] = "frontier80_stride320_target_prefix_delta_candidate_replay"
    apply_verdict(summary, target_rows, pair)

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
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
