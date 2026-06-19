#!/usr/bin/env python3
"""Validate final structural coverage after bridge residual source promotion."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

from lolg_tex_gap_opcode_probe import relative_href, write_csv
from lolg_tex_gap_decoder_frontier80_clean_structural_nonzero_producer_probe import (
    ratio,
    read_csv,
)
from lolg_tex_gap_decoder_frontier80_clean_structural_nonzero_compact_control_grammar_probe import (
    int_field,
)


DEFAULT_PROMOTED_SUMMARY = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_no_bridge_bridge_residual_source_promoted_replay_probe/summary.csv"
)
DEFAULT_PROMOTED_TARGETS = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_no_bridge_bridge_residual_source_promoted_replay_probe/targets.csv"
)
DEFAULT_RESIDUAL_VALIDATION = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_no_bridge_bridge_residual_source_promoted_replay_probe/residual_validation.csv"
)
DEFAULT_TOKEN_VALIDATION = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_no_bridge_bridge_residual_source_promoted_replay_probe/token_validation.csv"
)
DEFAULT_OUTPUT = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_no_bridge_bridge_residual_final_coverage_validation_probe"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "selected_target_runs",
    "selected_target_bytes",
    "post_promoted_integrated_target_bytes",
    "post_promoted_integrated_target_ratio",
    "post_promoted_unintegrated_target_bytes",
    "full_coverage_target_runs",
    "partial_target_runs",
    "bridge_residual_promoted_bytes",
    "bridge_residual_false_bytes",
    "residual_validation_rows",
    "residual_exact_rows",
    "token_validation_rows",
    "token_exact_rows",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

TARGET_FIELDNAMES = [
    "target_id",
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "span_index",
    "run_index",
    "length",
    "post_promoted_integrated_target_bytes",
    "post_promoted_unintegrated_target_bytes",
    "promoted_bridge_residual_bytes",
    "promoted_bridge_residual_false_bytes",
    "verdict",
    "next_probe",
]


def validate_targets(targets: list[dict[str, str]], issues: list[str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for target in targets:
        length = int_field(target, "length")
        post = int_field(target, "post_promoted_integrated_target_bytes")
        remaining = int_field(target, "post_promoted_unintegrated_target_bytes")
        false = int_field(target, "promoted_bridge_residual_false_bytes")
        if post != length:
            issues.append(f"{target.get('target_id', '')}:post_integrated_mismatch:{post}!={length}")
        if remaining != 0:
            issues.append(f"{target.get('target_id', '')}:remaining_bytes:{remaining}")
        if false != 0:
            issues.append(f"{target.get('target_id', '')}:false_bytes:{false}")
        verdict = "final_structural_coverage_full" if post == length and remaining == 0 and false == 0 else "final_structural_coverage_issue"
        rows.append(
            {
                "target_id": target.get("target_id", ""),
                "rank": target.get("rank", ""),
                "archive": target.get("archive", ""),
                "archive_tag": target.get("archive_tag", ""),
                "pcx_name": target.get("pcx_name", ""),
                "frontier_id": target.get("frontier_id", ""),
                "span_index": target.get("span_index", ""),
                "run_index": target.get("run_index", ""),
                "length": target.get("length", "0"),
                "post_promoted_integrated_target_bytes": target.get("post_promoted_integrated_target_bytes", "0"),
                "post_promoted_unintegrated_target_bytes": target.get("post_promoted_unintegrated_target_bytes", "0"),
                "promoted_bridge_residual_bytes": target.get("promoted_bridge_residual_bytes", "0"),
                "promoted_bridge_residual_false_bytes": target.get("promoted_bridge_residual_false_bytes", "0"),
                "verdict": verdict,
                "next_probe": "integrate final structural nonzero replay into clean fixture base",
            }
        )
    return rows


def validate_source_rows(
    residual_rows: list[dict[str, str]],
    token_rows: list[dict[str, str]],
    issues: list[str],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    residual_exact = []
    for index, row in enumerate(residual_rows):
        if row.get("verdict", "") == "bridge_residual_source_promoted_exact" and int_field(row, "false_bytes") == 0:
            residual_exact.append(row)
        else:
            issues.append(f"residual_validation[{index}]:not_exact")
    token_exact = []
    for index, row in enumerate(token_rows):
        if row.get("exact_target_slice", "") == "1":
            token_exact.append(row)
        else:
            issues.append(f"token_validation[{index}]:not_exact")
    return residual_exact, token_exact


def build_summary(
    promoted_summary: dict[str, str],
    target_rows: list[dict[str, str]],
    residual_rows: list[dict[str, str]],
    token_rows: list[dict[str, str]],
    residual_exact: list[dict[str, str]],
    token_exact: list[dict[str, str]],
    issues: list[str],
) -> dict[str, str]:
    selected_bytes = int_field(promoted_summary, "selected_target_bytes")
    post_integrated = sum(int_field(row, "post_promoted_integrated_target_bytes") for row in target_rows)
    remaining = sum(int_field(row, "post_promoted_unintegrated_target_bytes") for row in target_rows)
    full_targets = [row for row in target_rows if row.get("verdict", "") == "final_structural_coverage_full"]
    promoted_false = sum(int_field(row, "promoted_bridge_residual_false_bytes") for row in target_rows)
    if post_integrated != selected_bytes:
        issues.append(f"post_integrated_selected_mismatch:{post_integrated}!={selected_bytes}")
    verdict = "frontier80_structural_nonzero_bridge_residual_final_coverage_validated"
    next_probe = "integrate final structural nonzero replay into clean fixture base"
    if (
        issues
        or remaining
        or promoted_false
        or len(residual_exact) != len(residual_rows)
        or len(token_exact) != len(token_rows)
        or post_integrated != selected_bytes
    ):
        verdict = "frontier80_structural_nonzero_bridge_residual_final_coverage_issues"
        next_probe = "review final structural nonzero coverage validation issues"
    return {
        "scope": "total",
        "selected_target_runs": str(len(target_rows)),
        "selected_target_bytes": str(selected_bytes),
        "post_promoted_integrated_target_bytes": str(post_integrated),
        "post_promoted_integrated_target_ratio": ratio(post_integrated, selected_bytes),
        "post_promoted_unintegrated_target_bytes": str(remaining),
        "full_coverage_target_runs": str(len(full_targets)),
        "partial_target_runs": str(len(target_rows) - len(full_targets)),
        "bridge_residual_promoted_bytes": str(
            sum(int_field(row, "promoted_bridge_residual_bytes") for row in target_rows)
        ),
        "bridge_residual_false_bytes": str(promoted_false),
        "residual_validation_rows": str(len(residual_rows)),
        "residual_exact_rows": str(len(residual_exact)),
        "token_validation_rows": str(len(token_rows)),
        "token_exact_rows": str(len(token_exact)),
        "issue_rows": str(len(issues)),
        "review_verdict": verdict,
        "next_probe": next_probe,
    }


def render_table(rows: list[dict[str, str]], fieldnames: list[str], *, limit: int = 100) -> str:
    if not rows:
        return "<p class=\"muted\">No rows.</p>"
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fieldnames)
    body = []
    for row in rows[:limit]:
        body.append(
            "<tr>"
            + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fieldnames)
            + "</tr>"
        )
    note = "" if len(rows) <= limit else f"<p class=\"muted\">Showing {limit} of {len(rows)} rows.</p>"
    return f"{note}<table><thead><tr>{header}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def build_html(
    output: Path,
    title: str,
    summary: dict[str, str],
    target_rows: list[dict[str, str]],
) -> str:
    payload = {"summary": summary, "targets": target_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    cards = [
        ("Post integrated", summary.get("post_promoted_integrated_target_bytes", "0")),
        ("Remaining", summary.get("post_promoted_unintegrated_target_bytes", "0")),
        ("Full targets", summary.get("full_coverage_target_runs", "0")),
        ("Token exact", f"{summary.get('token_exact_rows', '0')}/{summary.get('token_validation_rows', '0')}"),
        ("Verdict", summary.get("review_verdict", "")),
    ]
    card_html = "".join(
        f"<div class=\"card\"><div class=\"value\">{html.escape(value)}</div>"
        f"<div class=\"label\">{html.escape(label)}</div></div>"
        for label, value in cards
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{html.escape(title)}</title>
  <style>
    body {{ margin: 0; font: 14px/1.45 system-ui, sans-serif; color: #20242a; background: #f6f7f9; }}
    main {{ max-width: 1320px; margin: 0 auto; padding: 24px; }}
    h1 {{ margin: 0 0 8px; font-size: 24px; }}
    h2 {{ margin: 0 0 12px; font-size: 17px; }}
    .muted {{ color: #68717d; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; margin: 18px 0; }}
    .card, section {{ background: #fff; border: 1px solid #d8dde5; border-radius: 8px; }}
    .card {{ padding: 14px; }}
    .value {{ font-size: 20px; font-weight: 700; overflow-wrap: anywhere; }}
    .label {{ margin-top: 4px; color: #68717d; }}
    section {{ padding: 16px; margin: 16px 0; overflow: auto; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
    th, td {{ padding: 6px 8px; border-bottom: 1px solid #e3e7ed; text-align: left; vertical-align: top; }}
    th {{ position: sticky; top: 0; background: #eef2f6; }}
    td {{ max-width: 360px; overflow-wrap: anywhere; }}
    a {{ color: #1f5aa6; }}
  </style>
</head>
<body>
<main>
  <h1>{html.escape(title)}</h1>
  <div class="muted">Validates final structural nonzero coverage after bridge residual source promotion.</div>
  <div class="grid">{card_html}</div>
  <section><h2>Outputs</h2>
    <p><a href="{relative_href(output / 'summary.csv', output / 'index.html')}">summary.csv</a> ·
    <a href="{relative_href(output / 'targets.csv', output / 'index.html')}">targets.csv</a></p>
  </section>
  <section><h2>Targets</h2>{render_table(target_rows, TARGET_FIELDNAMES)}</section>
</main>
<script type="application/json" id="bridge-residual-final-coverage-validation-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> dict[str, str]:
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    promoted_summary_rows = read_csv(args.promoted_summary)
    promoted_summary = promoted_summary_rows[0] if promoted_summary_rows else {}
    target_rows = validate_targets(read_csv(args.promoted_targets), issues)
    residual_rows = read_csv(args.residual_validation)
    token_rows = read_csv(args.token_validation)
    residual_exact, token_exact = validate_source_rows(residual_rows, token_rows, issues)
    summary = build_summary(
        promoted_summary,
        target_rows,
        residual_rows,
        token_rows,
        residual_exact,
        token_exact,
        issues,
    )
    write_csv(output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output / "targets.csv", TARGET_FIELDNAMES, target_rows)
    (output / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""))
    (output / "index.html").write_text(build_html(output, args.title, summary, target_rows))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate final structural coverage after bridge residual source promotion."
    )
    parser.add_argument("--promoted-summary", type=Path, default=DEFAULT_PROMOTED_SUMMARY)
    parser.add_argument("--promoted-targets", type=Path, default=DEFAULT_PROMOTED_TARGETS)
    parser.add_argument("--residual-validation", type=Path, default=DEFAULT_RESIDUAL_VALIDATION)
    parser.add_argument("--token-validation", type=Path, default=DEFAULT_TOKEN_VALIDATION)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Structural No-Bridge Final Coverage Validation",
    )
    args = parser.parse_args()
    summary = write_report(args)
    print(f"Post promoted integrated bytes: {summary['post_promoted_integrated_target_bytes']}")
    print(f"Remaining bytes: {summary['post_promoted_unintegrated_target_bytes']}")
    print(f"Full coverage targets: {summary['full_coverage_target_runs']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
