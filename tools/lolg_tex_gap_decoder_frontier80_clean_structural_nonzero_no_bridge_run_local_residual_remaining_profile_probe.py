#!/usr/bin/env python3
"""Profile remaining structural nonzero bytes after no-bridge run-local residual replay."""

from __future__ import annotations

import argparse
import html
import json
from collections import Counter
from pathlib import Path

from lolg_tex_gap_opcode_probe import relative_href, write_csv
from lolg_tex_gap_decoder_frontier80_clean_structural_nonzero_producer_probe import (
    ratio,
    read_csv,
)
from lolg_tex_gap_decoder_frontier80_clean_structural_nonzero_compact_control_grammar_probe import (
    int_field,
)


DEFAULT_COMPACT_INTEGRATED_SUMMARY = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_compact_control_integrated_replay_probe/summary.csv"
)
DEFAULT_COMPACT_INTEGRATED_TARGETS = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_compact_control_integrated_replay_probe/targets.csv"
)
DEFAULT_RUN_LOCAL_PROMOTED_SUMMARY = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_no_bridge_run_local_residual_promoted_replay_probe/summary.csv"
)
DEFAULT_RUN_LOCAL_PROMOTED_TARGETS = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_no_bridge_run_local_residual_promoted_replay_probe/targets.csv"
)
DEFAULT_OUTPUT = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_no_bridge_run_local_residual_remaining_profile_probe"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "selected_target_runs",
    "selected_target_bytes",
    "post_promoted_integrated_target_bytes",
    "post_promoted_integrated_target_ratio",
    "post_promoted_unintegrated_target_bytes",
    "remaining_target_runs",
    "remaining_bytes",
    "remaining_no_bridge_bytes",
    "remaining_bridge_bytes",
    "ordered_bridge_only_runs",
    "ordered_bridge_only_bytes",
    "compact_gap_partial_runs",
    "compact_gap_partial_bytes",
    "top_remaining_pcx",
    "top_remaining_frontiers",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

REMAINING_FIELDNAMES = [
    "target_id",
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "span_index",
    "run_index",
    "start",
    "end",
    "length",
    "integrated_after_run_local_bytes",
    "remaining_bytes",
    "remaining_ratio",
    "compact_integrated_bytes",
    "ordered_bridge_rows",
    "ordered_bridge_bytes",
    "promoted_grammar_bytes",
    "bridge_envelope_bytes",
    "token_rows",
    "generated_bytes",
    "literal_bytes",
    "remaining_class",
    "verdict",
    "next_probe",
]


def counter_text(counter: Counter[str]) -> str:
    return "|".join(f"{key}:{count}" for key, count in counter.most_common(10))


def classify_remaining(row: dict[str, str]) -> str:
    if int_field(row, "promoted_grammar_bytes") > 0:
        return "compact_gap_partial"
    if int_field(row, "ordered_bridge_bytes") > 0:
        return "ordered_bridge_only"
    return "bridge_unmapped"


def build_rows(
    compact_targets: list[dict[str, str]],
    run_local_targets: dict[str, dict[str, str]],
) -> tuple[list[dict[str, str]], list[str]]:
    rows: list[dict[str, str]] = []
    issues: list[str] = []
    for target in compact_targets:
        target_id = target.get("target_id", "")
        length = int_field(target, "length")
        if target_id in run_local_targets:
            integrated = int_field(run_local_targets[target_id], "post_promoted_integrated_target_bytes")
            remaining_class = "no_bridge_promoted"
        else:
            integrated = int_field(target, "integrated_target_bytes")
            remaining_class = classify_remaining(target)
        remaining = max(0, length - integrated)
        if integrated > length:
            issues.append(f"{target_id}:integrated_exceeds_length:{integrated}>{length}")
        if not remaining:
            continue
        rows.append(
            {
                "target_id": target_id,
                "rank": target.get("rank", ""),
                "archive": target.get("archive", ""),
                "archive_tag": target.get("archive_tag", ""),
                "pcx_name": target.get("pcx_name", ""),
                "frontier_id": target.get("frontier_id", ""),
                "span_index": target.get("span_index", ""),
                "run_index": target.get("run_index", ""),
                "start": target.get("start", ""),
                "end": target.get("end", ""),
                "length": str(length),
                "integrated_after_run_local_bytes": str(integrated),
                "remaining_bytes": str(remaining),
                "remaining_ratio": ratio(remaining, length),
                "compact_integrated_bytes": target.get("integrated_target_bytes", "0"),
                "ordered_bridge_rows": target.get("ordered_bridge_rows", "0"),
                "ordered_bridge_bytes": target.get("ordered_bridge_bytes", "0"),
                "promoted_grammar_bytes": target.get("promoted_grammar_bytes", "0"),
                "bridge_envelope_bytes": target.get("bridge_envelope_bytes", "0"),
                "token_rows": target.get("token_rows", "0"),
                "generated_bytes": target.get("generated_bytes", "0"),
                "literal_bytes": target.get("literal_bytes", "0"),
                "remaining_class": remaining_class,
                "verdict": "remaining_structural_nonzero_bridge_profiled",
                "next_probe": "derive bridge residual interval map after run-local replay",
            }
        )
    return rows, issues


def build_summary(
    run_local_summary: dict[str, str],
    remaining_rows: list[dict[str, str]],
    issue_count: int,
) -> dict[str, str]:
    remaining_bytes = sum(int_field(row, "remaining_bytes") for row in remaining_rows)
    by_class = Counter(row.get("remaining_class", "") for row in remaining_rows)
    class_bytes = Counter()
    by_pcx = Counter()
    by_frontier = Counter()
    for row in remaining_rows:
        value = int_field(row, "remaining_bytes")
        class_bytes[row.get("remaining_class", "")] += value
        by_pcx[row.get("pcx_name", "")] += value
        by_frontier[row.get("frontier_id", "")] += value
    verdict = "frontier80_structural_no_bridge_run_local_residual_remaining_profile_ready"
    next_probe = "derive bridge residual interval map after run-local replay"
    if issue_count:
        verdict = "frontier80_structural_no_bridge_run_local_residual_remaining_profile_issues"
        next_probe = "review remaining structural nonzero profile issues"
    return {
        "scope": "total",
        "selected_target_runs": run_local_summary.get("selected_target_runs", "0"),
        "selected_target_bytes": run_local_summary.get("selected_target_bytes", "0"),
        "post_promoted_integrated_target_bytes": run_local_summary.get("post_promoted_integrated_target_bytes", "0"),
        "post_promoted_integrated_target_ratio": run_local_summary.get(
            "post_promoted_integrated_target_ratio", "0"
        ),
        "post_promoted_unintegrated_target_bytes": run_local_summary.get(
            "post_promoted_unintegrated_target_bytes", str(remaining_bytes)
        ),
        "remaining_target_runs": str(len(remaining_rows)),
        "remaining_bytes": str(remaining_bytes),
        "remaining_no_bridge_bytes": str(class_bytes.get("no_bridge_promoted", 0)),
        "remaining_bridge_bytes": str(remaining_bytes - class_bytes.get("no_bridge_promoted", 0)),
        "ordered_bridge_only_runs": str(by_class.get("ordered_bridge_only", 0)),
        "ordered_bridge_only_bytes": str(class_bytes.get("ordered_bridge_only", 0)),
        "compact_gap_partial_runs": str(by_class.get("compact_gap_partial", 0)),
        "compact_gap_partial_bytes": str(class_bytes.get("compact_gap_partial", 0)),
        "top_remaining_pcx": counter_text(by_pcx),
        "top_remaining_frontiers": counter_text(by_frontier),
        "issue_rows": str(issue_count),
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
    remaining_rows: list[dict[str, str]],
) -> str:
    payload = {"summary": summary, "remaining": remaining_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    cards = [
        ("Integrated", summary.get("post_promoted_integrated_target_bytes", "0")),
        ("Remaining", summary.get("remaining_bytes", "0")),
        ("Remaining runs", summary.get("remaining_target_runs", "0")),
        ("Bridge bytes", summary.get("remaining_bridge_bytes", "0")),
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
  <div class="muted">Profiles remaining structural nonzero runs after no-bridge run-local residual promotion.</div>
  <div class="grid">{card_html}</div>
  <section><h2>Outputs</h2>
    <p><a href="{relative_href(output / 'summary.csv', output / 'index.html')}">summary.csv</a> ·
    <a href="{relative_href(output / 'remaining_targets.csv', output / 'index.html')}">remaining_targets.csv</a></p>
  </section>
  <section><h2>Remaining Targets</h2>{render_table(remaining_rows, REMAINING_FIELDNAMES)}</section>
</main>
<script type="application/json" id="no-bridge-run-local-residual-remaining-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> dict[str, str]:
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    compact_summary_rows = read_csv(args.compact_integrated_summary)
    compact_summary = compact_summary_rows[0] if compact_summary_rows else {}
    run_local_summary_rows = read_csv(args.run_local_promoted_summary)
    run_local_summary = run_local_summary_rows[0] if run_local_summary_rows else {}
    compact_targets = read_csv(args.compact_integrated_targets)
    run_local_targets = {
        row.get("target_id", ""): row for row in read_csv(args.run_local_promoted_targets)
    }
    remaining_rows, issues = build_rows(compact_targets, run_local_targets)
    expected_remaining = int_field(run_local_summary, "post_promoted_unintegrated_target_bytes")
    measured_remaining = sum(int_field(row, "remaining_bytes") for row in remaining_rows)
    if expected_remaining and measured_remaining != expected_remaining:
        issues.append(f"remaining_total_mismatch:{measured_remaining}!={expected_remaining}")
    if int_field(compact_summary, "selected_target_runs") and len(compact_targets) != int_field(
        compact_summary, "selected_target_runs"
    ):
        issues.append("compact_target_count_mismatch")

    summary = build_summary(run_local_summary, remaining_rows, len(issues))
    write_csv(output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output / "remaining_targets.csv", REMAINING_FIELDNAMES, remaining_rows)
    (output / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""))
    (output / "index.html").write_text(build_html(output, args.title, summary, remaining_rows))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Profile remaining structural nonzero bytes after no-bridge run-local residual replay."
    )
    parser.add_argument("--compact-integrated-summary", type=Path, default=DEFAULT_COMPACT_INTEGRATED_SUMMARY)
    parser.add_argument("--compact-integrated-targets", type=Path, default=DEFAULT_COMPACT_INTEGRATED_TARGETS)
    parser.add_argument("--run-local-promoted-summary", type=Path, default=DEFAULT_RUN_LOCAL_PROMOTED_SUMMARY)
    parser.add_argument("--run-local-promoted-targets", type=Path, default=DEFAULT_RUN_LOCAL_PROMOTED_TARGETS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Structural No-Bridge Run-Local Residual Remaining Profile",
    )
    args = parser.parse_args()
    summary = write_report(args)
    print(f"Integrated bytes: {summary['post_promoted_integrated_target_bytes']}")
    print(f"Remaining bytes: {summary['remaining_bytes']}")
    print(f"Remaining target runs: {summary['remaining_target_runs']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
