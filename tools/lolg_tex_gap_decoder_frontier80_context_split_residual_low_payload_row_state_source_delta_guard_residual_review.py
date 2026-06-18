#!/usr/bin/env python3
"""Review residual row-state source bytes after guarded delta promotion."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

from lolg_tex_gap_decoder_frontier80_context_split_residual_low_payload_neighborhood_probe import (
    load_target_runs,
    read_csv,
)
from lolg_tex_gap_decoder_frontier80_context_split_residual_low_payload_row_state_source_prereq_probe import (
    CANDIDATE_FIELDNAMES,
    COVERAGE_FIELDNAMES,
    TARGET_FIELDNAMES,
    build_candidates,
    build_coverage,
    support_windows,
    target_record,
    target_source_rows,
)
from lolg_tex_gap_opcode_probe import int_value, write_csv


DEFAULT_OUTPUT = Path(
    "output/tex_gap_decoder_frontier80_context_split_residual_low_payload_row_state_source_delta_guard_residual_review"
)
DEFAULT_RUNS = Path("output/tex_gap_decoder_unresolved_run_probe_frontier80_context_split_residual_second_replay/runs.csv")
DEFAULT_MANIFEST = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_CLEAN_FIXTURES = Path(
    "output/tex_gap_decoder_frontier80_context_split_residual_low_payload_row_state_source_delta_guard_promoted_replay/fixtures.csv"
)
DEFAULT_GUARD_PROMOTED_SUMMARY = Path(
    "output/tex_gap_decoder_frontier80_context_split_residual_low_payload_row_state_source_delta_guard_promoted_replay/summary.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "target_source_rows",
    "resolved_source_rows",
    "residual_source_rows",
    "source_bytes",
    "known_source_bytes",
    "missing_source_bytes",
    "guard_promoted_bytes",
    "residual_candidate_rows",
    "residual_full_support_rows",
    "best_residual_known_total",
    "best_residual_exact_total",
    "best_residual_small_delta_le2_total",
    "best_residual_small_delta_le4_total",
    "residual_target_ids",
    "issue_rows",
    "review_verdict",
    "next_probe",
]


def residual_rows(coverage: list[dict[str, str]]) -> list[dict[str, str]]:
    return [row for row in coverage if int_value(row, "missing_source_bytes") > 0]


def build_summary(
    coverage: list[dict[str, str]],
    candidates: list[dict[str, str]],
    guard_summary: dict[str, str] | None,
    issues: list[str],
) -> dict[str, str]:
    residual = residual_rows(coverage)
    missing_total = sum(int_value(row, "missing_source_bytes") for row in coverage)
    residual_le4 = sum(int_value(row, "best_missing_small_delta_le4_bytes") for row in residual)
    if len(residual) == 1 and residual_le4 == missing_total and missing_total > 0:
        verdict = "frontier80_context_residual_low_payload_row_state_source_delta_guard_residual_single_row_transform_needed"
        next_probe = "derive single-row residual delta guard for row-state source prerequisites"
    elif missing_total == 0:
        verdict = "frontier80_context_residual_low_payload_row_state_source_delta_guard_residual_clear"
        next_probe = "review row-state source replay after residual clear"
    else:
        verdict = "frontier80_context_residual_low_payload_row_state_source_delta_guard_residual_split_needed"
        next_probe = "split residual row-state source bytes after guarded selector promotion"
    return {
        "scope": "total",
        "target_source_rows": str(len(coverage)),
        "resolved_source_rows": str(sum(1 for row in coverage if int_value(row, "missing_source_bytes") == 0)),
        "residual_source_rows": str(len(residual)),
        "source_bytes": str(sum(int_value(row, "known_source_bytes") + int_value(row, "missing_source_bytes") for row in coverage)),
        "known_source_bytes": str(sum(int_value(row, "known_source_bytes") for row in coverage)),
        "missing_source_bytes": str(missing_total),
        "guard_promoted_bytes": (guard_summary or {}).get("source_added_bytes", "0"),
        "residual_candidate_rows": str(sum(int_value(row, "candidate_rows") for row in residual)),
        "residual_full_support_rows": str(sum(int_value(row, "full_missing_support_candidate_rows") for row in residual)),
        "best_residual_known_total": str(sum(int_value(row, "best_missing_known_bytes") for row in residual)),
        "best_residual_exact_total": str(sum(int_value(row, "best_missing_exact_bytes") for row in residual)),
        "best_residual_small_delta_le2_total": str(sum(int_value(row, "best_missing_small_delta_le2_bytes") for row in residual)),
        "best_residual_small_delta_le4_total": str(residual_le4),
        "residual_target_ids": ";".join(row.get("target_id", "") for row in residual),
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
    targets: list[dict[str, str]],
    coverage: list[dict[str, str]],
    candidates: list[dict[str, str]],
    title: str,
) -> str:
    summary_json = html.escape(json.dumps(summary, indent=2))
    stats = "".join(
        f"<div class=\"stat\"><div class=\"label\">{html.escape(key)}</div>"
        f"<div class=\"value\">{html.escape(summary.get(key, ''))}</div></div>"
        for key in (
            "missing_source_bytes",
            "guard_promoted_bytes",
            "residual_source_rows",
            "best_residual_exact_total",
            "best_residual_small_delta_le4_total",
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
  {table_html("Target pre-sources", "targets.csv", targets, TARGET_FIELDNAMES)}
  {table_html("Residual coverage", "residual_coverage.csv", coverage, COVERAGE_FIELDNAMES)}
  {table_html("Residual candidates", "residual_candidates.csv", candidates, CANDIDATE_FIELDNAMES)}
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Review residual row-state source bytes after guarded delta promotion."
    )
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--runs", type=Path, default=DEFAULT_RUNS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--clean-fixtures", type=Path, default=DEFAULT_CLEAN_FIXTURES)
    parser.add_argument("--guard-promoted-summary", type=Path, default=DEFAULT_GUARD_PROMOTED_SUMMARY)
    parser.add_argument("--min-known", type=int, default=24)
    parser.add_argument("--min-high", type=int, default=28)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Low Payload Row-State Source Delta Guard Residual Review",
    )
    args = parser.parse_args()

    issues: list[str] = []
    run_rows = read_csv(args.runs)
    manifest_rows = read_csv(args.manifest)
    clean_rows = read_csv(args.clean_fixtures)
    guard_summary_rows = read_csv(args.guard_promoted_summary) if args.guard_promoted_summary.exists() else []
    target_runs = load_target_runs(run_rows, manifest_rows, clean_rows, issues)
    targets = target_source_rows(target_runs, issues)
    supports = support_windows(manifest_rows, clean_rows, issues, min_known=args.min_known, min_high=args.min_high)
    candidates = build_candidates(targets, supports)
    coverage = build_coverage(targets, candidates)
    target_records = [target_record(row) for row in targets]
    summary = build_summary(coverage, candidates, guard_summary_rows[0] if guard_summary_rows else None, issues)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, target_records)
    write_csv(args.output / "residual_coverage.csv", COVERAGE_FIELDNAMES, coverage)
    write_csv(args.output / "residual_candidates.csv", CANDIDATE_FIELDNAMES, candidates)
    (args.output / "issues.txt").write_text("\n".join(issues))
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, target_records, coverage, candidates, args.title))

    print(
        "Residual source review: "
        f"missing={summary['missing_source_bytes']}, "
        f"residual_rows={summary['residual_source_rows']}, "
        f"le4={summary['best_residual_small_delta_le4_total']}"
    )
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
