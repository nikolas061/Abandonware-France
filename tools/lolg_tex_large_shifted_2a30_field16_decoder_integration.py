#!/usr/bin/env python3
"""Integrate promoted shifted 0x2a30 field16 small-delta guards."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
from pathlib import Path


DEFAULT_OUTPUT = Path("output/tex_large_shifted_2a30_field16_decoder_integration")
DEFAULT_CANDIDATES = Path("output/tex_large_shifted_2a30_field16_small_delta_guard_probe/candidates.csv")
DEFAULT_REPLAY_OPERATIONS = Path(
    "output/tex_large_shifted_2a30_field16_small_delta_guard_promoted_replay/operations.csv"
)
DEFAULT_REPLAY_GUARDS = Path("output/tex_large_shifted_2a30_field16_small_delta_guard_promoted_replay/guards.csv")
DEFAULT_GUARD_DEFINITIONS = Path("output/tex_large_shifted_2a30_field16_small_delta_guard_probe/guards.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_rows",
    "decoder_rows",
    "decoder_exact_rows",
    "large_rejected_rows",
    "large_rejected_decoder_rows",
    "large_rejected_exact_rows",
    "remaining_large_rows",
    "remaining_large_decoder_rows",
    "remaining_large_exact_rows",
    "target_decoder_rows",
    "support_decoder_rows",
    "positive_guard_rows",
    "negative_guard_rows",
    "zero_guard_rows",
    "blocked_context_rows",
    "replay_operation_rows",
    "replay_promoted_rows",
    "replay_promoted_exact_rows",
    "replay_blocked_context_rows",
    "rule_rows",
    "issue_rows",
    "review_verdict",
    "next_action",
]

DECODER_FIELDNAMES = [
    "archive_tag",
    "pcx_name",
    "large_rejected",
    "remaining_large",
    "delta_group",
    "next_word_low_dec",
    "field16_high_dec",
    "oracle_extra",
    "decoder_rule",
    "decoder_condition",
    "decoder_extra",
    "decoder_status",
    "exact_match",
    "replay_promoted",
    "target_promoted",
    "support_promoted",
    "context_blocked",
    "replay_role",
    "promotion_source",
    "issues",
]

RULE_FIELDNAMES = [
    "rule_id",
    "condition",
    "predicted_extra",
    "source_rows",
    "decoder_rows",
    "exact_rows",
    "large_rows",
    "large_exact_rows",
    "remaining_rows",
    "remaining_exact_rows",
    "target_rows",
    "support_rows",
    "context_blocked_rows",
    "verdict",
    "next_probe",
]

RULE_ORDER = [
    "positive_small_nextlow_minus2",
    "negative_small_extra36",
    "zero_delta_extra40",
    "skip_large_negative_context",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def row_key(row: dict[str, str]) -> tuple[str, str]:
    return row.get("archive_tag", ""), row.get("pcx_name", "").lower()


def rule_lookup(guard_rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row.get("guard_id", ""): row for row in guard_rows if row.get("guard_id")}


def promoted_exact(row: dict[str, str]) -> bool:
    return (
        row.get("replay_promoted") == "yes"
        and row.get("decoder_extra") != ""
        and row.get("exact_match") == "yes"
        and row.get("issues") == ""
    )


def build_decoder_rows(
    candidate_rows: list[dict[str, str]],
    operation_rows: list[dict[str, str]],
    guard_definitions: list[dict[str, str]],
) -> list[dict[str, str]]:
    operations = {row_key(row): row for row in operation_rows}
    guards = rule_lookup(guard_definitions)
    rows: list[dict[str, str]] = []
    for candidate in candidate_rows:
        key = row_key(candidate)
        operation = operations.get(key, {})
        guard_id = candidate.get("guard_id", "")
        issues: list[str] = []
        if not operation:
            issues.append("missing_replay_operation")
        elif operation.get("guard_id") != guard_id:
            issues.append("guard_id_mismatch")
        if operation.get("issues"):
            issues.append(f"replay_issues:{operation.get('issues')}")
        if operation.get("false_positive") == "yes":
            issues.append("replay_false_positive")

        context_blocked = operation.get("context_blocked") == "yes"
        replay_promoted = operation.get("promoted") == "yes"
        if context_blocked:
            decoder_rule = "skip_large_negative_context"
            decoder_extra = ""
            exact = "no"
            decoder_status = "blocked_context"
            if candidate.get("delta_group") != "large_negative_delta":
                issues.append("blocked_non_large_negative_context")
        elif replay_promoted:
            decoder_rule = guard_id
            decoder_extra = operation.get("chosen_extra", "")
            exact = operation.get("exact_match", "no")
            decoder_status = "decoded_exact" if exact == "yes" and not issues else "decoded_issue"
            if decoder_extra != candidate.get("oracle_extra", ""):
                issues.append("decoder_extra_oracle_mismatch")
        else:
            decoder_rule = "not_integrated"
            decoder_extra = ""
            exact = "no"
            decoder_status = "not_integrated"
            issues.append("row_not_integrated")

        if candidate.get("large_rejected") == "yes" and decoder_status != "decoded_exact":
            issues.append("large_rejected_not_decoded")
        if candidate.get("remaining_large") == "yes" and decoder_status != "decoded_exact":
            issues.append("remaining_large_not_decoded")
        if issues and decoder_status == "decoded_exact":
            decoder_status = "decoded_issue"

        guard = guards.get(decoder_rule, {})
        rows.append(
            {
                "archive_tag": candidate.get("archive_tag", ""),
                "pcx_name": candidate.get("pcx_name", ""),
                "large_rejected": candidate.get("large_rejected", ""),
                "remaining_large": candidate.get("remaining_large", ""),
                "delta_group": candidate.get("delta_group", ""),
                "next_word_low_dec": candidate.get("next_word_low_dec", ""),
                "field16_high_dec": candidate.get("field16_high_dec", ""),
                "oracle_extra": candidate.get("oracle_extra", ""),
                "decoder_rule": decoder_rule,
                "decoder_condition": guard.get("condition", ""),
                "decoder_extra": decoder_extra,
                "decoder_status": decoder_status,
                "exact_match": exact,
                "replay_promoted": "yes" if replay_promoted else "no",
                "target_promoted": operation.get("target_promoted", "no"),
                "support_promoted": operation.get("support_promoted", "no"),
                "context_blocked": "yes" if context_blocked else "no",
                "replay_role": operation.get("row_role", ""),
                "promotion_source": operation.get("promotion_source", ""),
                "issues": "|".join(dict.fromkeys(issues)),
            }
        )
    return sorted(rows, key=lambda row: (row["decoder_rule"], row["archive_tag"], row["pcx_name"].lower()))


def build_rule_rows(
    decoder_rows: list[dict[str, str]],
    guard_definitions: list[dict[str, str]],
    replay_guard_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    guards = rule_lookup(guard_definitions)
    replay_guards = rule_lookup(replay_guard_rows)
    output: list[dict[str, str]] = []
    for rule_id in RULE_ORDER:
        rows = [row for row in decoder_rows if row.get("decoder_rule") == rule_id]
        exact_rows = [row for row in rows if promoted_exact(row)]
        large_rows = [row for row in rows if row.get("large_rejected") == "yes"]
        large_exact_rows = [row for row in large_rows if promoted_exact(row)]
        remaining_rows = [row for row in rows if row.get("remaining_large") == "yes"]
        remaining_exact_rows = [row for row in remaining_rows if promoted_exact(row)]
        target_rows = [row for row in rows if row.get("target_promoted") == "yes"]
        support_rows = [row for row in rows if row.get("support_promoted") == "yes"]
        context_rows = [row for row in rows if row.get("context_blocked") == "yes"]
        issue_rows = [row for row in rows if row.get("issues")]
        if rule_id == "skip_large_negative_context":
            verdict = "context_blocked" if rows and len(context_rows) == len(rows) and not issue_rows else "context_issue"
            next_probe = "profile blocked large-negative context outside small-delta field16 decoder"
        elif rows and len(exact_rows) == len(rows) and not issue_rows:
            verdict = "integrated_exact"
            next_probe = "route integrated rule into large shifted 0x2a30 material decode queue"
        elif rows:
            verdict = "integrated_with_issues"
            next_probe = "fix integrated field16 decoder rule issues"
        else:
            verdict = "not_applicable"
            next_probe = "keep rule inactive until matching rows exist"
        guard = guards.get(rule_id, {})
        replay_guard = replay_guards.get(rule_id, {})
        output.append(
            {
                "rule_id": rule_id,
                "condition": guard.get("condition", replay_guard.get("promotion_scope", "")),
                "predicted_extra": guard.get("predicted_extra", ""),
                "source_rows": str(len(rows)),
                "decoder_rows": str(len(exact_rows)),
                "exact_rows": str(len(exact_rows)),
                "large_rows": str(len(large_rows)),
                "large_exact_rows": str(len(large_exact_rows)),
                "remaining_rows": str(len(remaining_rows)),
                "remaining_exact_rows": str(len(remaining_exact_rows)),
                "target_rows": str(len(target_rows)),
                "support_rows": str(len(support_rows)),
                "context_blocked_rows": str(len(context_rows)),
                "verdict": verdict,
                "next_probe": next_probe,
            }
        )
    return output


def build_summary(
    decoder_rows: list[dict[str, str]],
    operation_rows: list[dict[str, str]],
    rule_rows: list[dict[str, str]],
) -> dict[str, str]:
    decoded = [row for row in decoder_rows if row.get("decoder_status") == "decoded_exact"]
    exact_rows = [row for row in decoded if row.get("exact_match") == "yes"]
    large_rows = [row for row in decoder_rows if row.get("large_rejected") == "yes"]
    large_decoded = [row for row in large_rows if row.get("decoder_status") == "decoded_exact"]
    large_exact = [row for row in large_decoded if row.get("exact_match") == "yes"]
    remaining_rows = [row for row in decoder_rows if row.get("remaining_large") == "yes"]
    remaining_decoded = [row for row in remaining_rows if row.get("decoder_status") == "decoded_exact"]
    remaining_exact = [row for row in remaining_decoded if row.get("exact_match") == "yes"]
    target_rows = [row for row in decoded if row.get("target_promoted") == "yes"]
    support_rows = [row for row in decoded if row.get("support_promoted") == "yes"]
    blocked_context = [row for row in decoder_rows if row.get("context_blocked") == "yes"]
    replay_promoted = [row for row in operation_rows if row.get("promoted") == "yes"]
    replay_promoted_exact = [row for row in replay_promoted if row.get("exact_match") == "yes"]
    replay_blocked = [row for row in operation_rows if row.get("context_blocked") == "yes"]
    issue_rows = [row for row in decoder_rows if row.get("issues")] + [
        row for row in rule_rows if row.get("verdict") in {"context_issue", "integrated_with_issues"}
    ]
    clean = (
        len(decoder_rows) == 10
        and len(decoded) == 6
        and len(exact_rows) == 6
        and len(large_rows) == 4
        and len(large_exact) == 4
        and len(remaining_rows) == 2
        and len(remaining_exact) == 2
        and len(target_rows) == 4
        and len(support_rows) == 2
        and len(blocked_context) == 4
        and len(operation_rows) == 10
        and len(replay_promoted) == 6
        and len(replay_promoted_exact) == 6
        and len(replay_blocked) == 4
        and len(rule_rows) == 4
        and not issue_rows
    )
    if clean:
        verdict = "field16_small_delta_decoder_integrated"
        next_action = "route integrated shifted 0x2a30 field16 decoder into large .tex material decode queue"
    elif issue_rows:
        verdict = "field16_small_delta_decoder_integration_issues"
        next_action = "fix integrated shifted 0x2a30 field16 decoder issues"
    else:
        verdict = "field16_small_delta_decoder_integration_incomplete"
        next_action = "complete shifted 0x2a30 field16 decoder integration coverage"
    return {
        "scope": "total",
        "candidate_rows": str(len(decoder_rows)),
        "decoder_rows": str(len(decoded)),
        "decoder_exact_rows": str(len(exact_rows)),
        "large_rejected_rows": str(len(large_rows)),
        "large_rejected_decoder_rows": str(len(large_decoded)),
        "large_rejected_exact_rows": str(len(large_exact)),
        "remaining_large_rows": str(len(remaining_rows)),
        "remaining_large_decoder_rows": str(len(remaining_decoded)),
        "remaining_large_exact_rows": str(len(remaining_exact)),
        "target_decoder_rows": str(len(target_rows)),
        "support_decoder_rows": str(len(support_rows)),
        "positive_guard_rows": str(sum(1 for row in decoded if row.get("decoder_rule") == "positive_small_nextlow_minus2")),
        "negative_guard_rows": str(sum(1 for row in decoded if row.get("decoder_rule") == "negative_small_extra36")),
        "zero_guard_rows": str(sum(1 for row in decoded if row.get("decoder_rule") == "zero_delta_extra40")),
        "blocked_context_rows": str(len(blocked_context)),
        "replay_operation_rows": str(len(operation_rows)),
        "replay_promoted_rows": str(len(replay_promoted)),
        "replay_promoted_exact_rows": str(len(replay_promoted_exact)),
        "replay_blocked_context_rows": str(len(replay_blocked)),
        "rule_rows": str(len(rule_rows)),
        "issue_rows": str(len(issue_rows)),
        "review_verdict": verdict,
        "next_action": next_action,
    }


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


def build_html(
    summary: dict[str, str],
    decoder_rows: list[dict[str, str]],
    rule_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "decoder_rows": decoder_rows, "rules": rule_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("decoder_rows.csv", output_dir / "decoder_rows.csv"),
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
td {{ max-width: 420px; overflow-wrap: anywhere; }}
</style>
</head>
<body>
<main>
<h1>{html.escape(title)}</h1>
<p class="muted">Integrates promoted shifted 0x2a30 field16 small-delta guards and keeps large-negative context blocked.</p>
<p>{links}</p>
<h2>Summary</h2>
{render_table([summary], SUMMARY_FIELDNAMES)}
<h2>Integrated Rules</h2>
{render_table(rule_rows, RULE_FIELDNAMES)}
<h2>Decoder Rows</h2>
{render_table(decoder_rows, DECODER_FIELDNAMES)}
</main>
<script>const TEX_LARGE_SHIFTED_2A30_FIELD16_DECODER_INTEGRATION = {data_json};</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    candidates_path: Path,
    replay_operations_path: Path,
    replay_guards_path: Path,
    guard_definitions_path: Path,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    candidate_rows = read_csv(candidates_path)
    operation_rows = read_csv(replay_operations_path)
    guard_definitions = read_csv(guard_definitions_path)
    replay_guard_rows = read_csv(replay_guards_path)
    decoder_rows = build_decoder_rows(candidate_rows, operation_rows, guard_definitions)
    rule_rows = build_rule_rows(decoder_rows, guard_definitions, replay_guard_rows)
    summary = build_summary(decoder_rows, operation_rows, rule_rows)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "decoder_rows.csv", DECODER_FIELDNAMES, decoder_rows)
    write_csv(output_dir / "rules.csv", RULE_FIELDNAMES, rule_rows)
    (output_dir / "index.html").write_text(
        build_html(summary, decoder_rows, rule_rows, output_dir, title),
        encoding="utf-8",
    )
    return summary, decoder_rows, rule_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Integrate promoted shifted 0x2a30 field16 decoder guards.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--replay-operations", type=Path, default=DEFAULT_REPLAY_OPERATIONS)
    parser.add_argument("--replay-guards", type=Path, default=DEFAULT_REPLAY_GUARDS)
    parser.add_argument("--guard-definitions", type=Path, default=DEFAULT_GUARD_DEFINITIONS)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Large Shifted 2a30 Field16 Decoder Integration",
    )
    args = parser.parse_args()

    summary, _decoder_rows, _rule_rows = write_report(
        args.output,
        args.candidates,
        args.replay_operations,
        args.replay_guards,
        args.guard_definitions,
        args.title,
    )
    print(f"Decoder rows: {summary['decoder_exact_rows']}/{summary['decoder_rows']}")
    print(f"Large exact rows: {summary['large_rejected_exact_rows']}/{summary['large_rejected_rows']}")
    print(f"Remaining exact rows: {summary['remaining_large_exact_rows']}/{summary['remaining_large_rows']}")
    print(f"Blocked context rows: {summary['blocked_context_rows']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
