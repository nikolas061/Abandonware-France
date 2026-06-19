#!/usr/bin/env python3
"""Route shifted 0x2a30 branch rows after the promoted tail0/2 start guard."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
from pathlib import Path


DEFAULT_OUTPUT = Path("output/tex_large_shifted_2a30_branch_start_guard_route")
DEFAULT_BASE_ROUTES = Path("output/tex_large_shifted_2a30_field16_decoder_route/routes.csv")
DEFAULT_START_GUARD_OPERATIONS = Path(
    "output/tex_large_shifted_2a30_branch_start_guard_promoted_replay/operations.csv"
)
DEFAULT_START_GUARD_SUMMARY = Path(
    "output/tex_large_shifted_2a30_branch_start_guard_promoted_replay/summary.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "base_route_rows",
    "base_field16_routed_rows",
    "base_branch_blocked_rows",
    "start_guard_operation_rows",
    "start_guard_promoted_rows",
    "route_rows",
    "field16_routed_rows",
    "branch_start_guard_rows",
    "branch_start_guard_routed_rows",
    "branch_renderer_blocked_rows",
    "remaining_branch_blocked_rows",
    "non_2a30_rows",
    "missing_operation_rows",
    "issue_rows",
    "target_archive_tag",
    "target_pcx_name",
    "target_guard_id",
    "target_decoder_extra",
    "target_renderer_status",
    "target_trace_fingerprint",
    "review_verdict",
    "next_action",
]

ROUTE_FIELDNAMES = [
    "archive",
    "archive_tag",
    "texture_path",
    "pcx_name",
    "segment_index",
    "body_offset",
    "body_offset_hex",
    "segment_size",
    "body_first_word",
    "control_path",
    "pair_2a30_offset",
    "decoder_rule",
    "decoder_extra",
    "decoder_status",
    "decoder_exact",
    "target_promoted",
    "branch_guard_id",
    "branch_guard_extra",
    "branch_guard_start_exact",
    "branch_guard_score",
    "renderer_status",
    "renderer_promoted",
    "trace_fingerprint",
    "trace_support_rank1",
    "trace_support_any",
    "route_status",
    "route_priority",
    "issues",
]

RULE_FIELDNAMES = [
    "rule_id",
    "condition",
    "source_rows",
    "routed_rows",
    "target_rows",
    "renderer_promoted_rows",
    "renderer_blocked_rows",
    "verdict",
    "next_probe",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def row_key(row: dict[str, str]) -> tuple[str, str]:
    return row.get("archive_tag", ""), row.get("pcx_name", "").lower()


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    path = Path(path_text)
    try:
        relative = path.relative_to(base_dir)
    except ValueError:
        relative = Path(os.path.relpath(path, base_dir))
    return relative.as_posix()


def render_table(rows: list[dict[str, str]], columns: list[str]) -> str:
    head = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    body = []
    for row in rows:
        cells = "".join(f"<td>{html.escape(row.get(column, ''))}</td>" for column in columns)
        body.append(f"<tr>{cells}</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def route_from_base(
    base_routes: list[dict[str, str]],
    operations: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[str]]:
    operation_lookup = {row_key(row): row for row in operations if row.get("promoted_start") == "yes"}
    seen_operations: set[tuple[str, str]] = set()
    routes: list[dict[str, str]] = []
    issues: list[str] = []

    for base in base_routes:
        key = row_key(base)
        operation = operation_lookup.get(key, {})
        row_issues = [item for item in base.get("issues", "").split("|") if item]
        if operation:
            seen_operations.add(key)
            if base.get("route_status") != "blocked_shifted_2a30_branch":
                row_issues.append("start_guard_applied_to_non_branch_route")
            if operation.get("start_exact") != "yes":
                row_issues.append("start_guard_not_exact")
            if operation.get("renderer_promoted") == "yes":
                route_status = "routed_branch_start_guard_renderer"
                route_priority = "materialize_shifted_2a30_branch_preview"
                decoder_status = "decoded_start_and_renderer"
            else:
                route_status = "routed_branch_start_guard_renderer_blocked"
                route_priority = "derive_guarded_extra64_renderer_grammar"
                decoder_status = "start_guarded_renderer_blocked"
            routes.append(
                {
                    "archive": base.get("archive", ""),
                    "archive_tag": base.get("archive_tag", ""),
                    "texture_path": base.get("texture_path", ""),
                    "pcx_name": base.get("pcx_name", ""),
                    "segment_index": base.get("segment_index", ""),
                    "body_offset": base.get("body_offset", ""),
                    "body_offset_hex": base.get("body_offset_hex", ""),
                    "segment_size": base.get("segment_size", ""),
                    "body_first_word": base.get("body_first_word", ""),
                    "control_path": base.get("control_path", ""),
                    "pair_2a30_offset": base.get("pair_2a30_offset", ""),
                    "decoder_rule": operation.get("guard_id", ""),
                    "decoder_extra": operation.get("predicted_extra", ""),
                    "decoder_status": decoder_status,
                    "decoder_exact": operation.get("start_exact", ""),
                    "target_promoted": operation.get("target_promoted", ""),
                    "branch_guard_id": operation.get("guard_id", ""),
                    "branch_guard_extra": operation.get("predicted_extra", ""),
                    "branch_guard_start_exact": operation.get("start_exact", ""),
                    "branch_guard_score": operation.get("score", ""),
                    "renderer_status": operation.get("renderer_status", ""),
                    "renderer_promoted": operation.get("renderer_promoted", ""),
                    "trace_fingerprint": operation.get("trace_fingerprint", ""),
                    "trace_support_rank1": operation.get("trace_support_rank1", ""),
                    "trace_support_any": operation.get("trace_support_any", ""),
                    "route_status": route_status,
                    "route_priority": route_priority,
                    "issues": "|".join(dict.fromkeys(row_issues)),
                }
            )
            continue

        routes.append(
            {
                "archive": base.get("archive", ""),
                "archive_tag": base.get("archive_tag", ""),
                "texture_path": base.get("texture_path", ""),
                "pcx_name": base.get("pcx_name", ""),
                "segment_index": base.get("segment_index", ""),
                "body_offset": base.get("body_offset", ""),
                "body_offset_hex": base.get("body_offset_hex", ""),
                "segment_size": base.get("segment_size", ""),
                "body_first_word": base.get("body_first_word", ""),
                "control_path": base.get("control_path", ""),
                "pair_2a30_offset": base.get("pair_2a30_offset", ""),
                "decoder_rule": base.get("decoder_rule", ""),
                "decoder_extra": base.get("decoder_extra", ""),
                "decoder_status": base.get("decoder_status", ""),
                "decoder_exact": base.get("decoder_exact", ""),
                "target_promoted": base.get("target_promoted", ""),
                "branch_guard_id": "",
                "branch_guard_extra": "",
                "branch_guard_start_exact": "",
                "branch_guard_score": "",
                "renderer_status": "",
                "renderer_promoted": "",
                "trace_fingerprint": "",
                "trace_support_rank1": "",
                "trace_support_any": "",
                "route_status": base.get("route_status", ""),
                "route_priority": base.get("route_priority", ""),
                "issues": "|".join(dict.fromkeys(row_issues)),
            }
        )

    for key in sorted(set(operation_lookup) - seen_operations):
        issues.append(f"missing_base_route_for_start_guard:{key[0]}/{key[1]}")

    return (
        sorted(routes, key=lambda row: (row.get("route_priority", ""), row.get("archive_tag", ""), row.get("pcx_name", "").lower())),
        issues,
    )


def build_rule_rows(routes: list[dict[str, str]], summary: dict[str, str]) -> list[dict[str, str]]:
    guarded = [row for row in routes if row.get("branch_guard_id") == "tail0_half_start_guard"]
    target_rows = [row for row in guarded if row.get("target_promoted") == "yes"]
    renderer_promoted = [row for row in guarded if row.get("renderer_promoted") == "yes"]
    renderer_blocked = [row for row in guarded if row.get("renderer_promoted") != "yes"]
    issue_rows = [row for row in guarded if row.get("issues")]
    if guarded and target_rows and renderer_blocked and not issue_rows:
        verdict = "route_ready_renderer_blocked"
        next_probe = "derive renderer grammar for tail0/2 guarded shifted 0x2a30 branch"
    elif issue_rows:
        verdict = "route_issues"
        next_probe = "fix shifted 0x2a30 branch start guard route issues"
    else:
        verdict = "route_incomplete"
        next_probe = "complete shifted 0x2a30 branch start guard route"
    return [
        {
            "rule_id": "tail0_half_start_guard",
            "condition": "marker-local 04a900 tail0/2 predicts stream start extra",
            "source_rows": summary.get("start_guard_operation_rows", ""),
            "routed_rows": str(len(guarded)),
            "target_rows": str(len(target_rows)),
            "renderer_promoted_rows": str(len(renderer_promoted)),
            "renderer_blocked_rows": str(len(renderer_blocked)),
            "verdict": verdict,
            "next_probe": next_probe,
        }
    ]


def build_summary(
    base_routes: list[dict[str, str]],
    operations: list[dict[str, str]],
    routes: list[dict[str, str]],
    route_issues: list[str],
) -> dict[str, str]:
    base_field16 = [row for row in base_routes if row.get("route_status") == "routed_field16_decoder"]
    base_branch = [row for row in base_routes if row.get("route_status") == "blocked_shifted_2a30_branch"]
    promoted_ops = [row for row in operations if row.get("promoted_start") == "yes"]
    field16 = [row for row in routes if row.get("route_status") == "routed_field16_decoder"]
    branch_guard = [row for row in routes if row.get("branch_guard_id")]
    branch_routed = [row for row in branch_guard if row.get("branch_guard_start_exact") == "yes"]
    renderer_blocked = [row for row in branch_guard if row.get("renderer_promoted") != "yes"]
    remaining_branch = [row for row in routes if row.get("route_status") == "blocked_shifted_2a30_branch"]
    non_2a30 = [row for row in routes if row.get("route_status") == "outside_field16_decoder_scope"]
    missing_operation = [row for row in base_branch if row_key(row) not in {row_key(op) for op in promoted_ops}]
    issue_rows = [row for row in routes if row.get("issues")]
    target = branch_guard[0] if branch_guard else {}
    total_issues = len(issue_rows) + len(route_issues)
    if total_issues:
        verdict = "branch_start_guard_route_issues"
        next_action = "fix shifted 0x2a30 branch start guard route issues"
    elif branch_routed and renderer_blocked and not remaining_branch:
        verdict = "branch_start_guard_route_ready_renderer_blocked"
        next_action = "derive renderer grammar for shifted 0x2a30 branch tail0/2 guarded extra64"
    elif branch_routed and not renderer_blocked:
        verdict = "branch_start_guard_route_ready"
        next_action = "materialize shifted 0x2a30 branch route previews"
    else:
        verdict = "branch_start_guard_route_incomplete"
        next_action = "complete shifted 0x2a30 branch start guard route"
    return {
        "scope": "total",
        "base_route_rows": str(len(base_routes)),
        "base_field16_routed_rows": str(len(base_field16)),
        "base_branch_blocked_rows": str(len(base_branch)),
        "start_guard_operation_rows": str(len(operations)),
        "start_guard_promoted_rows": str(len(promoted_ops)),
        "route_rows": str(len(routes)),
        "field16_routed_rows": str(len(field16)),
        "branch_start_guard_rows": str(len(branch_guard)),
        "branch_start_guard_routed_rows": str(len(branch_routed)),
        "branch_renderer_blocked_rows": str(len(renderer_blocked)),
        "remaining_branch_blocked_rows": str(len(remaining_branch)),
        "non_2a30_rows": str(len(non_2a30)),
        "missing_operation_rows": str(len(missing_operation)),
        "issue_rows": str(total_issues),
        "target_archive_tag": target.get("archive_tag", ""),
        "target_pcx_name": target.get("pcx_name", ""),
        "target_guard_id": target.get("branch_guard_id", ""),
        "target_decoder_extra": target.get("decoder_extra", ""),
        "target_renderer_status": target.get("renderer_status", ""),
        "target_trace_fingerprint": target.get("trace_fingerprint", ""),
        "review_verdict": verdict,
        "next_action": next_action,
    }


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
<p class="muted">Routes the promoted tail0/2 stream-start guard while keeping renderer promotion blocked.</p>
<p>{links}</p>
<h2>Summary</h2>
{render_table([summary], SUMMARY_FIELDNAMES)}
<h2>Rules</h2>
{render_table(rule_rows, RULE_FIELDNAMES)}
<h2>Routes</h2>
{render_table(routes, ROUTE_FIELDNAMES)}
</main>
<script>const TEX_LARGE_SHIFTED_2A30_BRANCH_START_GUARD_ROUTE = {data_json};</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> tuple[dict[str, str], list[str]]:
    args.output.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    base_routes = read_csv(args.base_routes)
    operations = read_csv(args.start_guard_operations)
    start_guard_summary = (read_csv(args.start_guard_summary) or [{}])[0]
    if not base_routes:
        issues.append("missing_base_routes")
    if not operations:
        issues.append("missing_start_guard_operations")
    if not start_guard_summary:
        issues.append("missing_start_guard_summary")
    routes, route_issues = route_from_base(base_routes, operations)
    issues.extend(route_issues)
    summary = build_summary(base_routes, operations, routes, issues)
    rule_rows = build_rule_rows(routes, summary)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "routes.csv", ROUTE_FIELDNAMES, routes)
    write_csv(args.output / "rules.csv", RULE_FIELDNAMES, rule_rows)
    (args.output / "index.html").write_text(
        build_html(summary, routes, rule_rows, args.output, args.title),
        encoding="utf-8",
    )
    return summary, issues


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Route shifted 0x2a30 branch rows after the promoted tail0/2 start guard."
    )
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--base-routes", type=Path, default=DEFAULT_BASE_ROUTES)
    parser.add_argument("--start-guard-operations", type=Path, default=DEFAULT_START_GUARD_OPERATIONS)
    parser.add_argument("--start-guard-summary", type=Path, default=DEFAULT_START_GUARD_SUMMARY)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Large Shifted 2a30 Branch Start Guard Route",
    )
    args = parser.parse_args()

    summary, issues = write_report(args)
    print(f"Branch start guard rows: {summary['branch_start_guard_rows']}")
    print(f"Remaining branch blocked rows: {summary['remaining_branch_blocked_rows']}")
    print(f"Renderer blocked rows: {summary['branch_renderer_blocked_rows']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"Review verdict: {summary['review_verdict']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")
    if issues:
        print("Issues: " + "; ".join(issues))


if __name__ == "__main__":
    main()
