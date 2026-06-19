#!/usr/bin/env python3
"""Promote the validated high-arg2 renderer through the guarded 0x2a30 branch route."""

from __future__ import annotations

import argparse
import csv
import html
import json
from pathlib import Path

from lolg_tex_large_shifted_2a30_branch_start_guard_route import (
    ROUTE_FIELDNAMES,
    read_csv,
    relative_href,
    render_table,
    write_csv,
)


DEFAULT_OUTPUT = Path("output/tex_large_shifted_2a30_branch_high_arg2_renderer_route_promoted_replay")
DEFAULT_ROUTE_SUMMARY = Path("output/tex_large_shifted_2a30_branch_start_guard_route/summary.csv")
DEFAULT_ROUTES = Path("output/tex_large_shifted_2a30_branch_start_guard_route/routes.csv")
DEFAULT_VALIDATION_SUMMARY = Path(
    "output/tex_large_shifted_2a30_branch_high_arg2_skip_validation_probe/summary.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "input_route_rows",
    "input_branch_start_guard_rows",
    "validation_verdict",
    "validation_target_high_arg2_skips",
    "validation_support_applicable_high_arg2_max",
    "eligible_route_rows",
    "promoted_renderer_rows",
    "remaining_renderer_blocked_rows",
    "field16_routed_rows",
    "non_2a30_rows",
    "issue_rows",
    "target_archive_tag",
    "target_pcx_name",
    "target_decoder_extra",
    "target_renderer_status",
    "review_verdict",
    "next_action",
]

RULE_FIELDNAMES = [
    "rule_id",
    "condition",
    "source_rows",
    "eligible_rows",
    "promoted_rows",
    "remaining_blocked_rows",
    "verdict",
    "next_probe",
]


def int_text(value: str | int | None, default: int = 0) -> int:
    try:
        return int(str(value), 0) if value not in (None, "") else default
    except ValueError:
        return default


def row_key(row: dict[str, str]) -> tuple[str, str]:
    return row.get("archive_tag", ""), row.get("pcx_name", "").lower()


def validation_ready(validation: dict[str, str]) -> bool:
    return (
        validation.get("target_pixels_equal") == "yes"
        and int_text(validation.get("target_high_arg2_skips")) > 0
        and int_text(validation.get("support_applicable_high_arg2_skip_max")) == 0
        and int_text(validation.get("issue_rows")) == 0
        and validation.get("validation_verdict", "").startswith("high_arg2_skip_only_integrated")
    )


def target_key(validation: dict[str, str], route_summary: dict[str, str]) -> tuple[str, str]:
    return (
        validation.get("target_archive_tag") or route_summary.get("target_archive_tag", ""),
        (validation.get("target_pcx_name") or route_summary.get("target_pcx_name", "")).lower(),
    )


def promote_routes(
    routes: list[dict[str, str]],
    route_summary: dict[str, str],
    validation: dict[str, str],
) -> tuple[list[dict[str, str]], list[str]]:
    issues: list[str] = []
    ready = validation_ready(validation)
    target = target_key(validation, route_summary)
    output: list[dict[str, str]] = []
    for route in routes:
        row = dict(route)
        eligible = (
            ready
            and row_key(row) == target
            and row.get("branch_guard_id") == "tail0_half_start_guard"
            and row.get("route_status") == "routed_branch_start_guard_renderer_blocked"
            and row.get("renderer_promoted") != "yes"
        )
        if eligible:
            row["decoder_status"] = "decoded_start_and_renderer"
            row["renderer_status"] = "renderer_promoted_high_arg2_skip_only"
            row["renderer_promoted"] = "yes"
            row["route_status"] = "routed_branch_start_guard_renderer"
            row["route_priority"] = "materialize_shifted_2a30_branch_preview"
        output.append(row)
    if ready and not any(
        row_key(row) == target and row.get("branch_guard_id") == "tail0_half_start_guard" for row in routes
    ):
        issues.append(f"missing_target_route:{target[0]}/{target[1]}")
    return output, issues


def build_summary(
    route_summary: dict[str, str],
    routes: list[dict[str, str]],
    promoted_routes: list[dict[str, str]],
    validation: dict[str, str],
    issues: list[str],
) -> dict[str, str]:
    target = target_key(validation, route_summary)
    branch_rows = [row for row in routes if row.get("branch_guard_id")]
    eligible = [
        row
        for row in routes
        if row_key(row) == target
        and row.get("branch_guard_id") == "tail0_half_start_guard"
        and row.get("route_status") == "routed_branch_start_guard_renderer_blocked"
    ]
    branch_promoted = [row for row in promoted_routes if row.get("branch_guard_id") and row.get("renderer_promoted") == "yes"]
    remaining_blocked = [
        row for row in promoted_routes if row.get("branch_guard_id") and row.get("renderer_promoted") != "yes"
    ]
    field16 = [row for row in promoted_routes if row.get("route_status") == "routed_field16_decoder"]
    non_2a30 = [row for row in promoted_routes if row.get("route_status") == "outside_field16_decoder_scope"]
    target_row = next((row for row in promoted_routes if row_key(row) == target), {})
    if issues:
        verdict = "high_arg2_renderer_route_promoted_replay_issues"
        next_action = "fix high-arg2 renderer route promotion inputs"
    elif not validation_ready(validation):
        verdict = "high_arg2_renderer_route_blocked_validation"
        next_action = "fix high-arg2 renderer validation before route promotion"
    elif branch_promoted and not remaining_blocked:
        verdict = "high_arg2_renderer_route_promoted"
        next_action = "materialize shifted 0x2a30 branch route previews"
    else:
        verdict = "high_arg2_renderer_route_no_eligible_rows"
        next_action = "inspect guarded 0x2a30 route rows before high-arg2 renderer promotion"
    return {
        "scope": "total",
        "input_route_rows": str(len(routes)),
        "input_branch_start_guard_rows": str(len(branch_rows)),
        "validation_verdict": validation.get("validation_verdict", ""),
        "validation_target_high_arg2_skips": validation.get("target_high_arg2_skips", "0"),
        "validation_support_applicable_high_arg2_max": validation.get("support_applicable_high_arg2_skip_max", "0"),
        "eligible_route_rows": str(len(eligible)),
        "promoted_renderer_rows": str(len(branch_promoted)),
        "remaining_renderer_blocked_rows": str(len(remaining_blocked)),
        "field16_routed_rows": str(len(field16)),
        "non_2a30_rows": str(len(non_2a30)),
        "issue_rows": str(len(issues)),
        "target_archive_tag": target[0],
        "target_pcx_name": target[1],
        "target_decoder_extra": target_row.get("decoder_extra", ""),
        "target_renderer_status": target_row.get("renderer_status", ""),
        "review_verdict": verdict,
        "next_action": next_action,
    }


def build_rule_rows(summary: dict[str, str]) -> list[dict[str, str]]:
    return [
        {
            "rule_id": "tail0_half_start_guard_high_arg2_renderer",
            "condition": "validated cmd20 high-arg2 skip-only renderer for guarded extra64 target",
            "source_rows": summary.get("input_branch_start_guard_rows", "0"),
            "eligible_rows": summary.get("eligible_route_rows", "0"),
            "promoted_rows": summary.get("promoted_renderer_rows", "0"),
            "remaining_blocked_rows": summary.get("remaining_renderer_blocked_rows", "0"),
            "verdict": summary.get("review_verdict", ""),
            "next_probe": summary.get("next_action", ""),
        }
    ]


def build_html(
    summary: dict[str, str],
    routes: list[dict[str, str]],
    rule_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "routes": routes, "rules": rule_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("routes.csv", output_dir / "routes.csv"),
            ("rules.csv", output_dir / "rules.csv"),
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
<p class="muted">Promotes the guarded 0x2a30 branch renderer only after the integrated high-arg2 validation passes.</p>
<p>{links}</p>
<h2>Summary</h2>
{render_table([summary], SUMMARY_FIELDNAMES)}
<h2>Rules</h2>
{render_table(rule_rows, RULE_FIELDNAMES)}
<h2>Routes</h2>
{render_table(routes, ROUTE_FIELDNAMES)}
</main>
<script>const TEX_LARGE_SHIFTED_2A30_BRANCH_HIGH_ARG2_RENDERER_ROUTE_PROMOTED_REPLAY = {data_json};</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> tuple[dict[str, str], list[str]]:
    args.output.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    route_summary = (read_csv(args.route_summary) or [{}])[0]
    routes = read_csv(args.routes)
    validation = (read_csv(args.validation_summary) or [{}])[0]
    if not route_summary:
        issues.append("missing_route_summary")
    if not routes:
        issues.append("missing_routes")
    if not validation:
        issues.append("missing_validation_summary")
    promoted_routes, route_issues = promote_routes(routes, route_summary, validation)
    issues.extend(route_issues)
    summary = build_summary(route_summary, routes, promoted_routes, validation, issues)
    rule_rows = build_rule_rows(summary)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "routes.csv", ROUTE_FIELDNAMES, promoted_routes)
    write_csv(args.output / "rules.csv", RULE_FIELDNAMES, rule_rows)
    (args.output / "index.html").write_text(
        build_html(summary, promoted_routes, rule_rows, args.output, args.title),
        encoding="utf-8",
    )
    return summary, issues


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Promote the validated high-arg2 renderer through the guarded 0x2a30 branch route."
    )
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--route-summary", type=Path, default=DEFAULT_ROUTE_SUMMARY)
    parser.add_argument("--routes", type=Path, default=DEFAULT_ROUTES)
    parser.add_argument("--validation-summary", type=Path, default=DEFAULT_VALIDATION_SUMMARY)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Large Shifted 2a30 Branch High-Arg2 Renderer Route Promoted Replay",
    )
    args = parser.parse_args()

    summary, issues = write_report(args)
    print(f"Eligible route rows: {summary['eligible_route_rows']}")
    print(f"Promoted renderer rows: {summary['promoted_renderer_rows']}")
    print(f"Remaining renderer blocked rows: {summary['remaining_renderer_blocked_rows']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"Review verdict: {summary['review_verdict']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")
    if issues:
        print("Issues: " + "; ".join(issues))


if __name__ == "__main__":
    main()
