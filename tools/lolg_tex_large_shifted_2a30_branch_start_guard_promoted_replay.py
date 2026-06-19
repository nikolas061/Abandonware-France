#!/usr/bin/env python3
"""Replay the promoted tail0/2 start guard for the shifted 0x2a30 branch."""

from __future__ import annotations

import argparse
import csv
import html
import json
from pathlib import Path

from lolg_tex_large_shifted_2a30_branch_bounded_family_probe import float_text
from lolg_tex_large_shifted_2a30_branch_singleton_header_probe import (
    int_text,
    read_csv,
    relative_href,
    render_table,
    write_csv,
)


DEFAULT_OUTPUT = Path("output/tex_large_shifted_2a30_branch_start_guard_promoted_replay")
DEFAULT_BRANCHES = Path("output/tex_large_shifted_2a30_branch_probe/branches.csv")
DEFAULT_HEADER_START_SUMMARY = Path("output/tex_large_shifted_2a30_branch_header_start_probe/summary.csv")
DEFAULT_FORMULA_BESTS = Path("output/tex_large_shifted_2a30_branch_header_start_probe/formula_bests.csv")
DEFAULT_SELECTOR_SUMMARY = Path("output/tex_large_shifted_2a30_branch_selector_probe/summary.csv")
DEFAULT_RENDERER_TRACE = Path("output/tex_large_shifted_2a30_branch_selector_probe/renderer_trace.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "branch_rows",
    "header_start_formula_best_rows",
    "selector_renderer_candidate_rows",
    "operation_rows",
    "promoted_start_rows",
    "promoted_target_rows",
    "start_exact_rows",
    "renderer_promoted_rows",
    "renderer_blocked_rows",
    "target_guard_id",
    "target_predicted_extra",
    "target_selector_best_extra",
    "target_mode",
    "target_score",
    "target_score_delta_vs_selector",
    "target_trace_fingerprint",
    "target_trace_rank1_supported",
    "target_trace_any_supported",
    "tail0_half_same_tail0_cross_support",
    "issue_rows",
    "review_verdict",
    "next_action",
]

OPERATION_FIELDNAMES = [
    "archive_tag",
    "pcx_name",
    "branch_key",
    "segment_id",
    "marker_pos",
    "tail0",
    "guard_id",
    "guard_condition",
    "promoted_start",
    "target_promoted",
    "predicted_extra",
    "selector_best_extra",
    "chosen_start",
    "chosen_mode",
    "score",
    "score_delta_vs_selector",
    "start_exact",
    "renderer_promoted",
    "renderer_status",
    "trace_rank",
    "trace_fingerprint",
    "trace_support_rank1",
    "trace_support_any",
    "promotion_source",
    "issues",
]

GUARD_FIELDNAMES = [
    "guard_id",
    "condition",
    "source_formula",
    "source_rows",
    "promoted_rows",
    "target_rows",
    "start_exact_rows",
    "renderer_promoted_rows",
    "renderer_blocked_rows",
    "same_tail0_cross_support",
    "verdict",
    "next_probe",
]


def row_key(row: dict[str, str]) -> tuple[str, str]:
    return row.get("archive_tag", ""), row.get("pcx_name", "").lower()


def best_formula_lookup(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    output: dict[tuple[str, str], dict[str, str]] = {}
    for row in rows:
        if row.get("formula") != "tail0_half":
            continue
        key = row_key(row)
        current = output.get(key)
        if current is None or int_text(row.get("formula_rank"), 99) < int_text(current.get("formula_rank"), 99):
            output[key] = row
    return output


def renderer_trace_lookup(rows: list[dict[str, str]]) -> dict[tuple[str, str, str, str], dict[str, str]]:
    output: dict[tuple[str, str, str, str], dict[str, str]] = {}
    for row in rows:
        key = (
            row.get("archive_tag", ""),
            row.get("pcx_name", "").lower(),
            row.get("extra", ""),
            row.get("mode", ""),
        )
        current = output.get(key)
        if current is None or int_text(row.get("rank"), 999999) < int_text(current.get("rank"), 999999):
            output[key] = row
    return output


def build_operations(
    branch_rows: list[dict[str, str]],
    formula_bests: list[dict[str, str]],
    selector_summary: dict[str, str],
    renderer_trace_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    formulas = best_formula_lookup(formula_bests)
    traces = renderer_trace_lookup(renderer_trace_rows)
    selector_best_extra = selector_summary.get("target_best_extra", "")
    selector_best_score = float_text(selector_summary.get("target_best_score"), 999999.0)
    operations: list[dict[str, str]] = []
    for branch in branch_rows:
        key = row_key(branch)
        formula = formulas.get(key, {})
        issues: list[str] = []
        if not formula:
            issues.append("missing_tail0_half_formula")
        predicted_extra = formula.get("marker_extra", "")
        chosen_mode = formula.get("mode", "")
        trace = traces.get((key[0], key[1], predicted_extra, chosen_mode), {})
        if not trace:
            issues.append("missing_renderer_trace_for_guard_start")
        start_exact = predicted_extra == selector_best_extra and formula.get("score_delta_vs_record_best") == "0.0000"
        if not start_exact:
            issues.append("start_not_selector_best")
        renderer_promoted = (
            trace.get("support_rank1_fingerprint") == "yes"
            and trace.get("near_score") == "yes"
            and trace.get("command_bearing") == "yes"
        )
        if renderer_promoted:
            renderer_status = "renderer_promoted"
        elif trace:
            renderer_status = "blocked_renderer_fingerprint_unsupported"
        else:
            renderer_status = "blocked_missing_renderer_trace"
        operations.append(
            {
                "archive_tag": branch.get("archive_tag", ""),
                "pcx_name": branch.get("pcx_name", ""),
                "branch_key": branch.get("branch_key", ""),
                "segment_id": branch.get("segment_id", ""),
                "marker_pos": branch.get("pair_2a30_offset", ""),
                "tail0": formula.get("tail0", ""),
                "guard_id": "tail0_half_start_guard",
                "guard_condition": "marker-local 04a900 tail0/2 predicts stream start extra",
                "promoted_start": "yes" if start_exact and not issues else "no",
                "target_promoted": "yes" if formula.get("is_target") == "yes" and start_exact and not issues else "no",
                "predicted_extra": predicted_extra,
                "selector_best_extra": selector_best_extra,
                "chosen_start": formula.get("start", ""),
                "chosen_mode": chosen_mode,
                "score": formula.get("score", ""),
                "score_delta_vs_selector": f"{float_text(formula.get('score'), 999999.0) - selector_best_score:.4f}",
                "start_exact": "yes" if start_exact else "no",
                "renderer_promoted": "yes" if renderer_promoted else "no",
                "renderer_status": renderer_status,
                "trace_rank": trace.get("rank", ""),
                "trace_fingerprint": trace.get("fingerprint", ""),
                "trace_support_rank1": trace.get("support_rank1_fingerprint", ""),
                "trace_support_any": trace.get("support_any_fingerprint", ""),
                "promotion_source": "header_start_probe_tail0_half",
                "issues": "|".join(issues),
            }
        )
    return operations


def build_guard_rows(
    operations: list[dict[str, str]],
    header_start_summary: dict[str, str],
) -> list[dict[str, str]]:
    promoted = [row for row in operations if row.get("promoted_start") == "yes"]
    targets = [row for row in operations if row.get("target_promoted") == "yes"]
    start_exact = [row for row in operations if row.get("start_exact") == "yes"]
    renderer_promoted = [row for row in operations if row.get("renderer_promoted") == "yes"]
    renderer_blocked = [row for row in operations if row.get("renderer_promoted") != "yes"]
    issue_rows = [row for row in operations if row.get("issues")]
    if promoted and targets and not issue_rows and not renderer_promoted:
        verdict = "start_guard_promoted_renderer_blocked"
        next_probe = "integrate tail0/2 start guard into shifted 0x2a30 branch route before renderer grammar"
    elif issue_rows:
        verdict = "start_guard_replay_issues"
        next_probe = "fix tail0/2 start guard replay issues"
    else:
        verdict = "start_guard_replay_incomplete"
        next_probe = "complete tail0/2 start guard replay"
    return [
        {
            "guard_id": "tail0_half_start_guard",
            "condition": "marker-local 04a900 tail0/2 predicts stream start extra",
            "source_formula": "tail0_half",
            "source_rows": header_start_summary.get("formula_best_rows", ""),
            "promoted_rows": str(len(promoted)),
            "target_rows": str(len(targets)),
            "start_exact_rows": str(len(start_exact)),
            "renderer_promoted_rows": str(len(renderer_promoted)),
            "renderer_blocked_rows": str(len(renderer_blocked)),
            "same_tail0_cross_support": header_start_summary.get("tail0_half_same_tail0_cross_pcx_support", ""),
            "verdict": verdict,
            "next_probe": next_probe,
        }
    ]


def build_summary(
    branch_rows: list[dict[str, str]],
    formula_bests: list[dict[str, str]],
    header_start_summary: dict[str, str],
    selector_summary: dict[str, str],
    operations: list[dict[str, str]],
    guard_rows: list[dict[str, str]],
) -> dict[str, str]:
    promoted = [row for row in operations if row.get("promoted_start") == "yes"]
    targets = [row for row in operations if row.get("target_promoted") == "yes"]
    exact = [row for row in operations if row.get("start_exact") == "yes"]
    renderer_promoted = [row for row in operations if row.get("renderer_promoted") == "yes"]
    renderer_blocked = [row for row in operations if row.get("renderer_promoted") != "yes"]
    issue_rows = [row for row in operations if row.get("issues")]
    target = targets[0] if targets else (operations[0] if operations else {})
    guard = guard_rows[0] if guard_rows else {}
    if issue_rows:
        verdict = "branch_start_guard_replay_issues"
        next_action = "fix shifted 0x2a30 branch tail0/2 start guard replay issues"
    elif targets and exact and not renderer_promoted:
        verdict = "branch_start_guard_promoted_renderer_blocked"
        next_action = (
            "integrate promoted tail0/2 start guard into shifted 0x2a30 branch route, "
            "then derive renderer grammar for guarded extra64"
        )
    elif renderer_promoted:
        verdict = "branch_start_guard_and_renderer_promoted"
        next_action = "route shifted 0x2a30 branch through promoted start guard and renderer"
    else:
        verdict = "branch_start_guard_replay_incomplete"
        next_action = "complete shifted 0x2a30 branch tail0/2 start guard replay"
    return {
        "scope": "total",
        "branch_rows": str(len(branch_rows)),
        "header_start_formula_best_rows": str(len(formula_bests)),
        "selector_renderer_candidate_rows": selector_summary.get("renderer_candidate_rows", ""),
        "operation_rows": str(len(operations)),
        "promoted_start_rows": str(len(promoted)),
        "promoted_target_rows": str(len(targets)),
        "start_exact_rows": str(len(exact)),
        "renderer_promoted_rows": str(len(renderer_promoted)),
        "renderer_blocked_rows": str(len(renderer_blocked)),
        "target_guard_id": target.get("guard_id", ""),
        "target_predicted_extra": target.get("predicted_extra", ""),
        "target_selector_best_extra": target.get("selector_best_extra", ""),
        "target_mode": target.get("chosen_mode", ""),
        "target_score": target.get("score", ""),
        "target_score_delta_vs_selector": target.get("score_delta_vs_selector", ""),
        "target_trace_fingerprint": target.get("trace_fingerprint", ""),
        "target_trace_rank1_supported": target.get("trace_support_rank1", ""),
        "target_trace_any_supported": target.get("trace_support_any", ""),
        "tail0_half_same_tail0_cross_support": guard.get("same_tail0_cross_support", ""),
        "issue_rows": str(len(issue_rows)),
        "review_verdict": verdict,
        "next_action": next_action,
    }


def build_html(
    summary: dict[str, str],
    operations: list[dict[str, str]],
    guard_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "operations": operations, "guards": guard_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("operations.csv", output_dir / "operations.csv"),
            ("guards.csv", output_dir / "guards.csv"),
        )
    )
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root {{ color-scheme: dark; --bg: #101214; --panel: #171b1f; --line: #2b3339; --text: #edf2f4; --muted: #aab5ba; --accent: #7cc7ff; }}
body {{ margin: 0; background: var(--bg); color: var(--text); font: 14px/1.45 system-ui, -apple-system, Segoe UI, sans-serif; }}
main {{ max-width: 1500px; margin: 0 auto; padding: 28px; }}
h1 {{ font-size: 24px; margin: 0 0 8px; }}
h2 {{ font-size: 18px; margin: 26px 0 10px; }}
.muted {{ color: var(--muted); }}
a {{ color: var(--accent); text-decoration: none; margin-right: 10px; }}
table {{ width: 100%; border-collapse: collapse; background: var(--panel); border: 1px solid var(--line); margin-top: 10px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; font-size: 12px; }}
th {{ color: var(--muted); background: #20262b; }}
td {{ max-width: 520px; overflow-wrap: anywhere; }}
</style>
</head>
<body>
<main>
<h1>{html.escape(title)}</h1>
<p class="muted">Promotes only the header-derived stream start. Renderer promotion remains blocked until grammar support is derived.</p>
<p>{links}</p>
<h2>Summary</h2>
{render_table([summary], SUMMARY_FIELDNAMES)}
<h2>Guards</h2>
{render_table(guard_rows, GUARD_FIELDNAMES)}
<h2>Operations</h2>
{render_table(operations, OPERATION_FIELDNAMES)}
</main>
<script>const TEX_LARGE_SHIFTED_2A30_BRANCH_START_GUARD_PROMOTED_REPLAY = {data_json};</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> tuple[dict[str, str], list[str]]:
    args.output.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    branch_rows = read_csv(args.branches)
    header_start_summary = (read_csv(args.header_start_summary) or [{}])[0]
    formula_bests = read_csv(args.formula_bests)
    selector_summary = (read_csv(args.selector_summary) or [{}])[0]
    renderer_trace_rows = read_csv(args.renderer_trace)
    if not branch_rows:
        issues.append("missing_branch_rows")
    if not header_start_summary:
        issues.append("missing_header_start_summary")
    if not formula_bests:
        issues.append("missing_formula_bests")
    if not selector_summary:
        issues.append("missing_selector_summary")
    if not renderer_trace_rows:
        issues.append("missing_renderer_trace")
    operations = build_operations(branch_rows, formula_bests, selector_summary, renderer_trace_rows)
    guard_rows = build_guard_rows(operations, header_start_summary)
    summary = build_summary(branch_rows, formula_bests, header_start_summary, selector_summary, operations, guard_rows)
    if issues:
        summary["issue_rows"] = str(int_text(summary.get("issue_rows")) + len(issues))
        summary["review_verdict"] = "branch_start_guard_replay_input_issues"
        summary["next_action"] = "fix shifted 0x2a30 branch start guard replay inputs"
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "operations.csv", OPERATION_FIELDNAMES, operations)
    write_csv(args.output / "guards.csv", GUARD_FIELDNAMES, guard_rows)
    (args.output / "index.html").write_text(
        build_html(summary, operations, guard_rows, args.output, args.title),
        encoding="utf-8",
    )
    return summary, issues


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Replay the promoted tail0/2 start guard for the shifted 0x2a30 branch."
    )
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--branches", type=Path, default=DEFAULT_BRANCHES)
    parser.add_argument("--header-start-summary", type=Path, default=DEFAULT_HEADER_START_SUMMARY)
    parser.add_argument("--formula-bests", type=Path, default=DEFAULT_FORMULA_BESTS)
    parser.add_argument("--selector-summary", type=Path, default=DEFAULT_SELECTOR_SUMMARY)
    parser.add_argument("--renderer-trace", type=Path, default=DEFAULT_RENDERER_TRACE)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Large Shifted 2a30 Branch Start Guard Promoted Replay",
    )
    args = parser.parse_args()

    summary, issues = write_report(args)
    print(f"Promoted start rows: {summary['promoted_start_rows']}")
    print(f"Target extra: {summary['target_predicted_extra']}")
    print(f"Renderer promoted rows: {summary['renderer_promoted_rows']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"Review verdict: {summary['review_verdict']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")
    if issues:
        print("Issues: " + "; ".join(issues))


if __name__ == "__main__":
    main()
