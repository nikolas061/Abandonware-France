#!/usr/bin/env python3
"""Review unresolved runs after the single-row non-oracle selector promotion."""

from __future__ import annotations

import argparse
import html
import json
from collections import defaultdict
from pathlib import Path

from lolg_tex_gap_decoder_frontier80_context_split_residual_low_payload_neighborhood_probe import read_csv
from lolg_tex_gap_opcode_probe import int_value, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_frontier80_single_row_non_oracle_selector_promoted_run_review")
DEFAULT_BEFORE_SUMMARY = Path("output/tex_gap_decoder_unresolved_run_probe_frontier80_context_split_residual_second_replay/summary.csv")
DEFAULT_BEFORE_RUNS = Path("output/tex_gap_decoder_unresolved_run_probe_frontier80_context_split_residual_second_replay/runs.csv")
DEFAULT_AFTER_SUMMARY = Path(
    "output/tex_gap_decoder_unresolved_run_probe_frontier80_single_row_non_oracle_selector_promoted_replay/summary.csv"
)
DEFAULT_AFTER_RUNS = Path(
    "output/tex_gap_decoder_unresolved_run_probe_frontier80_single_row_non_oracle_selector_promoted_replay/runs.csv"
)
DEFAULT_PROMOTION_SUMMARY = Path(
    "output/tex_gap_decoder_frontier80_context_split_residual_low_payload_row_state_source_single_row_delta_non_oracle_selector_promoted_replay/summary.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "before_unresolved_bytes",
    "after_unresolved_bytes",
    "unresolved_delta_bytes",
    "before_run_rows",
    "after_run_rows",
    "run_delta_rows",
    "source_added_bytes",
    "source_false_bytes",
    "longest_nonzero_run_length",
    "longest_nonzero_run_count",
    "largest_stride320_pair_length",
    "stride320_pair_rows",
    "top_residual_targets",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

RUN_FIELDNAMES = [
    "target_id",
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "span_index",
    "run_index",
    "run_class",
    "start",
    "end",
    "length",
    "left_clean_distance",
    "right_clean_distance",
    "stride320_pair",
    "head_hex",
    "tail_hex",
]

PAIR_FIELDNAMES = [
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "run_class",
    "length",
    "start_a",
    "start_b",
    "stride",
    "target_a",
    "target_b",
    "head_a",
    "head_b",
    "tail_a",
    "tail_b",
]


def read_summary(path: Path) -> dict[str, str]:
    rows = read_csv(path)
    return rows[0] if rows else {}


def run_target_id(row: dict[str, str]) -> str:
    return f"r{int_value(row, 'rank'):03d}_f{row.get('frontier_id', '')}_s{row.get('span_index', '')}_run{row.get('run_index', '')}"


def top_runs(rows: list[dict[str, str]], pair_ids: set[str], limit: int = 32) -> list[dict[str, str]]:
    sorted_rows = sorted(
        rows,
        key=lambda row: (
            0 if row.get("run_class") == "nonzero" else 1,
            -int_value(row, "length"),
            int_value(row, "rank"),
            int_value(row, "frontier_id"),
            int_value(row, "start"),
        ),
    )
    result: list[dict[str, str]] = []
    for row in sorted_rows[:limit]:
        target_id = run_target_id(row)
        result.append(
            {
                "target_id": target_id,
                "rank": row.get("rank", ""),
                "archive": row.get("archive", ""),
                "archive_tag": row.get("archive_tag", ""),
                "pcx_name": row.get("pcx_name", ""),
                "frontier_id": row.get("frontier_id", ""),
                "span_index": row.get("span_index", ""),
                "run_index": row.get("run_index", ""),
                "run_class": row.get("run_class", ""),
                "start": row.get("start", ""),
                "end": row.get("end", ""),
                "length": row.get("length", "0"),
                "left_clean_distance": row.get("left_clean_distance", ""),
                "right_clean_distance": row.get("right_clean_distance", ""),
                "stride320_pair": "1" if target_id in pair_ids else "0",
                "head_hex": row.get("head_hex", ""),
                "tail_hex": row.get("tail_hex", ""),
            }
        )
    return result


def stride_pairs(rows: list[dict[str, str]], stride: int = 320) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str, str, str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row.get("run_class") != "nonzero":
            continue
        key = (
            row.get("rank", ""),
            row.get("archive", ""),
            row.get("archive_tag", ""),
            row.get("pcx_name", ""),
            row.get("frontier_id", ""),
            row.get("run_class", ""),
            row.get("length", "0"),
        )
        grouped[key].append(row)
    pairs: list[dict[str, str]] = []
    for key, group in grouped.items():
        by_start = {int_value(row, "start"): row for row in group}
        for start, row in sorted(by_start.items()):
            other = by_start.get(start + stride)
            if not other:
                continue
            pairs.append(
                {
                    "rank": key[0],
                    "archive": key[1],
                    "archive_tag": key[2],
                    "pcx_name": key[3],
                    "frontier_id": key[4],
                    "run_class": key[5],
                    "length": key[6],
                    "start_a": str(start),
                    "start_b": str(start + stride),
                    "stride": str(stride),
                    "target_a": run_target_id(row),
                    "target_b": run_target_id(other),
                    "head_a": row.get("head_hex", ""),
                    "head_b": other.get("head_hex", ""),
                    "tail_a": row.get("tail_hex", ""),
                    "tail_b": other.get("tail_hex", ""),
                }
            )
    pairs.sort(
        key=lambda row: (
            -int_value(row, "length"),
            int_value(row, "rank"),
            int_value(row, "frontier_id"),
            int_value(row, "start_a"),
        )
    )
    return pairs


def build_summary(
    before_summary: dict[str, str],
    after_summary: dict[str, str],
    promotion_summary: dict[str, str],
    after_runs: list[dict[str, str]],
    pairs: list[dict[str, str]],
    issues: list[str],
) -> dict[str, str]:
    nonzero_lengths = [int_value(row, "length") for row in after_runs if row.get("run_class") == "nonzero"]
    longest = max(nonzero_lengths, default=0)
    largest_pair = max((int_value(row, "length") for row in pairs), default=0)
    top_pair_targets = []
    if pairs:
        top_pair_targets = [pairs[0].get("target_a", ""), pairs[0].get("target_b", "")]
    progressed = int_value(before_summary, "unresolved_bytes") > int_value(after_summary, "unresolved_bytes")
    if progressed and largest_pair >= 64:
        verdict = "frontier80_single_row_non_oracle_selector_promoted_run_review_stride320_pair_needed"
        next_probe = "derive stride-320 paired run selector after single-row source promotion"
    elif progressed:
        verdict = "frontier80_single_row_non_oracle_selector_promoted_run_review_next_residual_needed"
        next_probe = "profile next residual runs after single-row source promotion"
    else:
        verdict = "frontier80_single_row_non_oracle_selector_promoted_run_review_no_progress"
        next_probe = "review single-row source promotion impact"
    return {
        "scope": "total",
        "before_unresolved_bytes": before_summary.get("unresolved_bytes", "0"),
        "after_unresolved_bytes": after_summary.get("unresolved_bytes", "0"),
        "unresolved_delta_bytes": str(
            int_value(before_summary, "unresolved_bytes") - int_value(after_summary, "unresolved_bytes")
        ),
        "before_run_rows": before_summary.get("run_rows", "0"),
        "after_run_rows": after_summary.get("run_rows", "0"),
        "run_delta_rows": str(int_value(before_summary, "run_rows") - int_value(after_summary, "run_rows")),
        "source_added_bytes": promotion_summary.get("source_added_bytes", "0"),
        "source_false_bytes": promotion_summary.get("source_false_bytes", "0"),
        "longest_nonzero_run_length": str(longest),
        "longest_nonzero_run_count": str(sum(1 for length in nonzero_lengths if length == longest)),
        "largest_stride320_pair_length": str(largest_pair),
        "stride320_pair_rows": str(len(pairs)),
        "top_residual_targets": ";".join(top_pair_targets),
        "issue_rows": str(len(issues)),
        "review_verdict": verdict,
        "next_probe": next_probe,
    }


def table_html(title: str, filename: str, rows: list[dict[str, str]], fields: list[str], limit: int = 48) -> str:
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
    runs: list[dict[str, str]],
    pairs: list[dict[str, str]],
    title: str,
) -> str:
    summary_json = html.escape(json.dumps(summary, indent=2))
    stats = "".join(
        f"<div class=\"stat\"><div class=\"label\">{html.escape(key)}</div>"
        f"<div class=\"value\">{html.escape(summary.get(key, ''))}</div></div>"
        for key in (
            "unresolved_delta_bytes",
            "after_unresolved_bytes",
            "longest_nonzero_run_length",
            "largest_stride320_pair_length",
            "stride320_pair_rows",
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
  {table_html("Stride-320 pairs", "stride320_pairs.csv", pairs, PAIR_FIELDNAMES)}
  {table_html("Top residual runs", "top_runs.csv", runs, RUN_FIELDNAMES)}
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--before-summary", type=Path, default=DEFAULT_BEFORE_SUMMARY)
    parser.add_argument("--before-runs", type=Path, default=DEFAULT_BEFORE_RUNS)
    parser.add_argument("--after-summary", type=Path, default=DEFAULT_AFTER_SUMMARY)
    parser.add_argument("--after-runs", type=Path, default=DEFAULT_AFTER_RUNS)
    parser.add_argument("--promotion-summary", type=Path, default=DEFAULT_PROMOTION_SUMMARY)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Single-Row Non-Oracle Promotion Run Review",
    )
    args = parser.parse_args()

    issues: list[str] = []
    before_summary = read_summary(args.before_summary)
    after_summary = read_summary(args.after_summary)
    promotion_summary = read_summary(args.promotion_summary)
    after_runs = read_csv(args.after_runs)
    pairs = stride_pairs(after_runs)
    pair_ids = {row.get("target_a", "") for row in pairs} | {row.get("target_b", "") for row in pairs}
    runs = top_runs(after_runs, pair_ids)
    summary = build_summary(before_summary, after_summary, promotion_summary, after_runs, pairs, issues)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "top_runs.csv", RUN_FIELDNAMES, runs)
    write_csv(args.output / "stride320_pairs.csv", PAIR_FIELDNAMES, pairs)
    (args.output / "issues.txt").write_text("\n".join(issues))
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, runs, pairs, args.title))

    print(
        "Post-promotion runs: "
        f"delta={summary['unresolved_delta_bytes']}, "
        f"longest={summary['longest_nonzero_run_length']}, "
        f"stride320={summary['largest_stride320_pair_length']}"
    )
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
