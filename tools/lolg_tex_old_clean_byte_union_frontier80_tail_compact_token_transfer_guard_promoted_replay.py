#!/usr/bin/env python3
"""Replay the frontier80 compact-token transfer guard as a validation promotion."""

from __future__ import annotations

import argparse
from pathlib import Path

import lolg_tex_gradient_sequence_high_safe_low_exception_source_byte_guard_promoted_replay as source_replay
import lolg_tex_old_clean_byte_union_frontier80_tail_compact_token_review as token_review
import lolg_tex_old_clean_byte_union_frontier80_tail_compact_token_transfer_guard_review as transfer_review
from lolg_tex_gap_decoder_len64_promoted_replay import read_csv
from lolg_tex_gap_opcode_probe import write_csv


DEFAULT_OUTPUT = Path(
    "output/tex_old_clean_byte_union_frontier80_tail_compact_token_transfer_guard_promoted_replay"
)
DEFAULT_BASE_FIXTURES = token_review.DEFAULT_BASE_FIXTURES
DEFAULT_TARGETS = transfer_review.DEFAULT_OUTPUT / "targets.csv"


def transfer_targets_as_promotions(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    promoted: list[dict[str, str]] = []
    for row in rows:
        promoted_row = dict(row)
        promoted_row["promotion_ready"] = "1" if row.get("transfer_ready") == "1" else "0"
        promoted.append(promoted_row)
    return promoted


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fixtures", type=Path, default=source_replay.DEFAULT_FIXTURES)
    parser.add_argument("--frontiers", type=Path, default=source_replay.DEFAULT_FRONTIERS)
    parser.add_argument("--base-fixtures", type=Path, default=DEFAULT_BASE_FIXTURES)
    parser.add_argument("--clean-decisions", type=Path, default=source_replay.DEFAULT_CLEAN_DECISIONS)
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Compact Token Transfer Guard Promoted Replay",
    )
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    target_rows = transfer_targets_as_promotions(read_csv(args.targets))
    summary, fixture_rows, promotion_rows = source_replay.build_rows(
        output_dir=args.output,
        fixture_rows=read_csv(args.fixtures),
        frontier_rows=read_csv(args.frontiers),
        base_fixture_rows=read_csv(args.base_fixtures),
        clean_decision_rows=read_csv(args.clean_decisions),
        target_rows=target_rows,
    )
    summary["scope"] = "frontier80_compact_token_transfer_guard_promoted_replay"

    write_csv(args.output / "summary.csv", source_replay.SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "fixtures.csv", source_replay.FIXTURE_FIELDNAMES, fixture_rows)
    write_csv(args.output / "promotions.csv", source_replay.PROMOTION_FIELDNAMES, promotion_rows)
    (args.output / "index.html").write_text(
        source_replay.build_html(summary, fixture_rows, promotion_rows, args.output, args.title),
        encoding="utf-8",
    )
    print(f"Promoted rows: {summary['promoted_rows']}/{summary['target_rows']}")
    print(f"Added source bytes: {summary['source_added_bytes']}")
    print(f"False bytes: {summary['source_false_bytes']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
