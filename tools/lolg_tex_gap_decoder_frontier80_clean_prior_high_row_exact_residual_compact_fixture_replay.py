#!/usr/bin/env python3
"""Integrate compact high-row residual corrections into clean fixtures."""

from __future__ import annotations

import argparse
from pathlib import Path

import lolg_tex_gap_decoder_frontier80_clean_prior_high_row_exact_residual_context_split_fixture_replay as fixture_replay
from lolg_tex_gap_opcode_probe import int_value, write_csv


DEFAULT_OUTPUT = Path(
    "output/tex_gap_decoder_frontier80_clean_prior_high_row_exact_residual_compact_fixture_replay"
)
DEFAULT_BASE_FIXTURES = fixture_replay.DEFAULT_BASE_FIXTURES
DEFAULT_SELECTOR_ROWS = Path(
    "output/tex_gap_decoder_frontier80_clean_prior_high_row_exact_residual_compact_promoted_replay/"
    "selector_rows.csv"
)


def remap_summary(summary: dict[str, str]) -> dict[str, str]:
    issue_rows = int_value(summary, "issue_rows")
    false_bytes = int_value(summary, "residual_false_bytes")
    added_bytes = int_value(summary, "residual_added_bytes")
    target_rows = int_value(summary, "target_rows")
    skipped_known = int_value(summary, "skipped_known_bytes")
    if issue_rows == 0 and false_bytes == 0 and added_bytes > 0:
        verdict = "frontier80_prior_high_row_exact_residual_compact_fixture_replay_ready"
        next_probe = "rerun Frontier80 clean-gap queue with compact residual fixture base"
        promotion_ready = str(added_bytes)
    elif issue_rows == 0 and false_bytes == 0 and target_rows > 0 and skipped_known == target_rows:
        verdict = "frontier80_prior_high_row_exact_residual_compact_fixture_replay_already_known"
        next_probe = "derive target-offset application for compact high-row residual corrections"
        promotion_ready = "0"
    else:
        verdict = "frontier80_prior_high_row_exact_residual_compact_fixture_replay_weak"
        next_probe = "review compact residual fixture integration coverage"
        promotion_ready = "0"

    remapped = dict(summary)
    remapped["promotion_ready_bytes"] = promotion_ready
    remapped["review_verdict"] = verdict
    remapped["next_probe"] = next_probe
    return remapped


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fixtures", type=Path, default=fixture_replay.DEFAULT_FIXTURES)
    parser.add_argument("--frontiers", type=Path, default=fixture_replay.DEFAULT_FRONTIERS)
    parser.add_argument("--base-fixtures", type=Path, default=DEFAULT_BASE_FIXTURES)
    parser.add_argument("--clean-decisions", type=Path, default=fixture_replay.DEFAULT_CLEAN_DECISIONS)
    parser.add_argument("--selector-rows", type=Path, default=DEFAULT_SELECTOR_ROWS)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Prior High Row Exact Residual Compact Fixture Replay",
    )
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    summary, fixture_rows, promotion_rows = fixture_replay.build_rows(
        output_dir=args.output,
        fixture_rows=fixture_replay.read_csv(args.fixtures),
        frontier_rows=fixture_replay.read_csv(args.frontiers),
        base_fixture_rows=fixture_replay.read_csv(args.base_fixtures),
        clean_decision_rows=fixture_replay.read_csv(args.clean_decisions),
        selector_rows=fixture_replay.read_csv(args.selector_rows),
    )
    summary = remap_summary(summary)
    write_csv(args.output / "summary.csv", fixture_replay.SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "fixtures.csv", fixture_replay.FIXTURE_FIELDNAMES, fixture_rows)
    write_csv(args.output / "promotions.csv", fixture_replay.PROMOTION_FIELDNAMES, promotion_rows)
    (args.output / "index.html").write_text(
        fixture_replay.build_html(summary, fixture_rows, promotion_rows, args.output, args.title),
        encoding="utf-8",
    )
    print(f"Promoted rows: {summary['promoted_rows']}/{summary['target_rows']}")
    print(f"Added residual bytes: {summary['residual_added_bytes']}")
    print(f"Skipped known bytes: {summary['skipped_known_bytes']}")
    print(f"False bytes: {summary['residual_false_bytes']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
