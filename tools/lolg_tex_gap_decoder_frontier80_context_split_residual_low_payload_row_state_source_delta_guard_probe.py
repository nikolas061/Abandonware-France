#!/usr/bin/env python3
"""Derive guarded rows from bounded-delta row-state source selectors."""

from __future__ import annotations

import argparse
import html
import json
from collections import defaultdict
from pathlib import Path

from lolg_tex_gap_decoder_frontier80_context_split_residual_low_payload_neighborhood_probe import read_csv
from lolg_tex_gap_opcode_probe import int_value, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_frontier80_context_split_residual_low_payload_row_state_source_delta_guard_probe")
DEFAULT_SELECTOR_COVERAGE = Path(
    "output/tex_gap_decoder_frontier80_context_split_residual_low_payload_row_state_source_delta_selector_probe/selector_coverage.csv"
)
DEFAULT_SELECTOR_ROWS = Path(
    "output/tex_gap_decoder_frontier80_context_split_residual_low_payload_row_state_source_delta_selector_probe/selector_rows.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "target_source_rows",
    "missing_source_bytes",
    "guard_ready_rows",
    "guard_ready_bytes",
    "residual_rows",
    "residual_bytes",
    "best_residual_exact_total",
    "best_residual_leave_one_out_total",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

GUARD_FIELDNAMES = [
    "target_id",
    "guard_status",
    "strategy",
    "rank",
    "frontier_id",
    "pre_source_start",
    "missing_source_bytes",
    "candidate_rows",
    "best_group_key",
    "best_group_rows",
    "best_support_rank",
    "best_support_frontier_id",
    "best_support_start",
    "best_exact_bytes",
    "best_leave_one_out_exact_bytes",
    "best_raw_exact_bytes",
    "exact_ready",
    "leave_one_out_ready",
]

SELECTOR_PREVIEW_FIELDNAMES = [
    "target_id",
    "strategy",
    "group_key",
    "group_rows",
    "support_rank",
    "support_frontier_id",
    "support_start",
    "raw_exact_bytes",
    "exact_bytes",
    "leave_one_out_exact_bytes",
    "mode_delta_head",
    "leave_one_out_delta_head",
]

READY_STRATEGY_PRIORITY = {
    "target_start_mod320": 0,
    "target_start_band32": 1,
    "target_start_band16": 2,
    "target_start_band64": 3,
    "target_family": 4,
    "global_start_band32": 5,
    "global_family": 6,
}


def target_rows(coverage: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    rows: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in coverage:
        rows[row.get("target_id", "")].append(row)
    return rows


def ready_sort_key(row: dict[str, str]) -> tuple[int, int, int, int, str]:
    return (
        READY_STRATEGY_PRIORITY.get(row.get("strategy", ""), 99),
        -int_value(row, "best_leave_one_out_exact_bytes"),
        -int_value(row, "best_exact_bytes"),
        -int_value(row, "best_group_rows"),
        row.get("best_group_key", ""),
    )


def residual_sort_key(row: dict[str, str]) -> tuple[int, int, int, str]:
    return (
        -int_value(row, "best_exact_bytes"),
        -int_value(row, "best_leave_one_out_exact_bytes"),
        -int_value(row, "best_group_rows"),
        row.get("strategy", ""),
    )


def select_guard_rows(coverage: list[dict[str, str]]) -> list[dict[str, str]]:
    selected: list[dict[str, str]] = []
    for target_id, rows in sorted(target_rows(coverage).items()):
        ready = [
            row
            for row in rows
            if row.get("exact_ready") == "1" and row.get("leave_one_out_ready") == "1"
        ]
        if ready:
            best = sorted(ready, key=ready_sort_key)[0]
            guard_status = "ready"
        else:
            best = sorted(rows, key=residual_sort_key)[0]
            guard_status = "residual"
        selected.append(
            {
                "target_id": target_id,
                "guard_status": guard_status,
                "strategy": best.get("strategy", ""),
                "rank": best.get("rank", ""),
                "frontier_id": best.get("frontier_id", ""),
                "pre_source_start": best.get("pre_source_start", ""),
                "missing_source_bytes": best.get("missing_source_bytes", "0"),
                "candidate_rows": best.get("candidate_rows", "0"),
                "best_group_key": best.get("best_group_key", ""),
                "best_group_rows": best.get("best_group_rows", "0"),
                "best_support_rank": best.get("best_support_rank", ""),
                "best_support_frontier_id": best.get("best_support_frontier_id", ""),
                "best_support_start": best.get("best_support_start", ""),
                "best_exact_bytes": best.get("best_exact_bytes", "0"),
                "best_leave_one_out_exact_bytes": best.get("best_leave_one_out_exact_bytes", "0"),
                "best_raw_exact_bytes": best.get("best_raw_exact_bytes", "0"),
                "exact_ready": best.get("exact_ready", "0"),
                "leave_one_out_ready": best.get("leave_one_out_ready", "0"),
            }
        )
    selected.sort(key=lambda row: (int_value(row, "rank"), int_value(row, "pre_source_start")))
    return selected


def selector_previews(selector_rows: list[dict[str, str]], guard_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    wanted = {
        (
            row.get("target_id", ""),
            row.get("strategy", ""),
            row.get("best_group_key", ""),
            row.get("best_support_start", ""),
        )
        for row in guard_rows
    }
    previews: list[dict[str, str]] = []
    for row in selector_rows:
        key = (
            row.get("target_id", ""),
            row.get("strategy", ""),
            row.get("group_key", ""),
            row.get("support_start", ""),
        )
        if key not in wanted:
            continue
        previews.append(
            {
                "target_id": row.get("target_id", ""),
                "strategy": row.get("strategy", ""),
                "group_key": row.get("group_key", ""),
                "group_rows": row.get("group_rows", "0"),
                "support_rank": row.get("support_rank", ""),
                "support_frontier_id": row.get("support_frontier_id", ""),
                "support_start": row.get("support_start", ""),
                "raw_exact_bytes": row.get("raw_exact_bytes", "0"),
                "exact_bytes": row.get("exact_bytes", "0"),
                "leave_one_out_exact_bytes": row.get("leave_one_out_exact_bytes", "0"),
                "mode_delta_head": row.get("mode_delta_head", ""),
                "leave_one_out_delta_head": row.get("leave_one_out_delta_head", ""),
            }
        )
    previews.sort(
        key=lambda row: (
            row.get("target_id", ""),
            row.get("strategy", ""),
            int_value(row, "support_start"),
        )
    )
    return previews


def sum_field(rows: list[dict[str, str]], field: str) -> int:
    return sum(int_value(row, field) for row in rows)


def build_summary(guard_rows: list[dict[str, str]], issues: list[str]) -> dict[str, str]:
    ready_rows = [row for row in guard_rows if row.get("guard_status") == "ready"]
    residual_rows = [row for row in guard_rows if row.get("guard_status") == "residual"]
    missing_total = sum_field(guard_rows, "missing_source_bytes")
    ready_bytes = sum_field(ready_rows, "missing_source_bytes")
    residual_bytes = sum_field(residual_rows, "missing_source_bytes")
    if ready_bytes and residual_bytes:
        verdict = "frontier80_context_residual_low_payload_row_state_source_delta_guard_partial_promotion_ready"
        next_probe = "promote guarded bounded-delta selector ready rows"
    elif ready_bytes == missing_total and missing_total > 0:
        verdict = "frontier80_context_residual_low_payload_row_state_source_delta_guard_promotion_ready"
        next_probe = "promote guarded bounded-delta selector rows"
    else:
        verdict = "frontier80_context_residual_low_payload_row_state_source_delta_guard_residual_split_needed"
        next_probe = "split residual bounded-delta selector guards"
    return {
        "scope": "total",
        "target_source_rows": str(len(guard_rows)),
        "missing_source_bytes": str(missing_total),
        "guard_ready_rows": str(len(ready_rows)),
        "guard_ready_bytes": str(ready_bytes),
        "residual_rows": str(len(residual_rows)),
        "residual_bytes": str(residual_bytes),
        "best_residual_exact_total": str(sum_field(residual_rows, "best_exact_bytes")),
        "best_residual_leave_one_out_total": str(sum_field(residual_rows, "best_leave_one_out_exact_bytes")),
        "issue_rows": str(len(issues)),
        "review_verdict": verdict,
        "next_probe": next_probe,
    }


def table_html(title: str, filename: str, rows: list[dict[str, str]], fields: list[str], limit: int = 36) -> str:
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
    guard_rows: list[dict[str, str]],
    previews: list[dict[str, str]],
    title: str,
) -> str:
    summary_json = html.escape(json.dumps(summary, indent=2))
    stats = "".join(
        f"<div class=\"stat\"><div class=\"label\">{html.escape(key)}</div>"
        f"<div class=\"value\">{html.escape(summary.get(key, ''))}</div></div>"
        for key in (
            "missing_source_bytes",
            "guard_ready_bytes",
            "residual_bytes",
            "best_residual_exact_total",
            "best_residual_leave_one_out_total",
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
  {table_html("Guard rows", "guard_rows.csv", guard_rows, GUARD_FIELDNAMES)}
  {table_html("Selector previews", "selector_previews.csv", previews, SELECTOR_PREVIEW_FIELDNAMES)}
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Derive guarded rows from bounded-delta row-state source selectors."
    )
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--selector-coverage", type=Path, default=DEFAULT_SELECTOR_COVERAGE)
    parser.add_argument("--selector-rows", type=Path, default=DEFAULT_SELECTOR_ROWS)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Low Payload Row-State Source Delta Guard Probe",
    )
    args = parser.parse_args()

    issues: list[str] = []
    coverage = read_csv(args.selector_coverage)
    selector_rows = read_csv(args.selector_rows)
    guard_rows = select_guard_rows(coverage)
    previews = selector_previews(selector_rows, guard_rows)
    summary = build_summary(guard_rows, issues)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "guard_rows.csv", GUARD_FIELDNAMES, guard_rows)
    write_csv(args.output / "selector_previews.csv", SELECTOR_PREVIEW_FIELDNAMES, previews)
    (args.output / "issues.txt").write_text("\n".join(issues))
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, guard_rows, previews, args.title))

    print(
        "Delta guards: "
        f"ready={summary['guard_ready_bytes']}, "
        f"residual={summary['residual_bytes']}"
    )
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
