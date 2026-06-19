#!/usr/bin/env python3
"""Review promotion targets for guarded shifted 0x2a30 field16 small-delta starts."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
from pathlib import Path


DEFAULT_OUTPUT = Path("output/tex_large_shifted_2a30_field16_small_delta_guard_review")
DEFAULT_CANDIDATES = Path("output/tex_large_shifted_2a30_field16_small_delta_guard_probe/candidates.csv")
DEFAULT_GUARDS = Path("output/tex_large_shifted_2a30_field16_small_delta_guard_probe/guards.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_rows",
    "applicable_rows",
    "exact_rows",
    "false_positive_rows",
    "large_rows",
    "large_target_rows",
    "large_target_exact_rows",
    "remaining_large_rows",
    "remaining_target_rows",
    "remaining_target_exact_rows",
    "support_rows",
    "skipped_context_rows",
    "positive_target_rows",
    "negative_target_rows",
    "zero_target_rows",
    "selected_guard_rows",
    "guard_rows",
    "decision_template_rows",
    "issue_rows",
    "review_verdict",
    "next_action",
]

TARGET_FIELDNAMES = [
    "promotion_id",
    "archive_tag",
    "pcx_name",
    "large_rejected",
    "remaining_large",
    "delta_group",
    "guard_id",
    "next_word_low_dec",
    "field16_high_dec",
    "oracle_extra",
    "predicted_extra",
    "exact_match",
    "promotion_status",
    "promotion_reason",
    "issues",
]

SUPPORT_FIELDNAMES = [
    "archive_tag",
    "pcx_name",
    "delta_group",
    "guard_id",
    "next_word_low_dec",
    "field16_high_dec",
    "oracle_extra",
    "predicted_extra",
    "support_role",
    "issues",
]

GUARD_FIELDNAMES = [
    "guard_id",
    "condition",
    "predicted_extra",
    "source_rows",
    "source_exact_rows",
    "target_rows",
    "target_exact_rows",
    "support_rows",
    "context_rows",
    "false_positive_rows",
    "promotion_scope",
    "verdict",
]

DECISION_FIELDNAMES = [
    "promotion_id",
    "archive",
    "name",
    "guard_id",
    "predicted_extra",
    "review_status",
    "review_note",
]


PROMOTABLE_GUARDS = {
    "positive_small_nextlow_minus2",
    "negative_small_extra36",
    "zero_delta_extra40",
}


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


def write_tsv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def promotion_id(row: dict[str, str]) -> str:
    return "__".join(
        [
            row.get("archive_tag", ""),
            row.get("pcx_name", "").lower(),
            row.get("guard_id", ""),
            row.get("predicted_extra", ""),
        ]
    )


def build_target_rows(candidate_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    targets: list[dict[str, str]] = []
    for row in candidate_rows:
        issues: list[str] = []
        guard_id = row.get("guard_id", "")
        is_target = row.get("large_rejected") == "yes" and guard_id in PROMOTABLE_GUARDS
        if not is_target:
            continue
        if row.get("predicted_extra") == "":
            issues.append("missing_predicted_extra")
        if row.get("exact_match") != "yes":
            issues.append("target_not_exact")
        if row.get("false_positive") == "yes":
            issues.append("target_false_positive")
        if row.get("issues"):
            issues.append(f"source_issues:{row.get('issues')}")
        status = "ready" if not issues else "blocked"
        targets.append(
            {
                "promotion_id": promotion_id(row),
                "archive_tag": row.get("archive_tag", ""),
                "pcx_name": row.get("pcx_name", ""),
                "large_rejected": row.get("large_rejected", ""),
                "remaining_large": row.get("remaining_large", ""),
                "delta_group": row.get("delta_group", ""),
                "guard_id": guard_id,
                "next_word_low_dec": row.get("next_word_low_dec", ""),
                "field16_high_dec": row.get("field16_high_dec", ""),
                "oracle_extra": row.get("oracle_extra", ""),
                "predicted_extra": row.get("predicted_extra", ""),
                "exact_match": row.get("exact_match", ""),
                "promotion_status": status,
                "promotion_reason": "guarded_large_exact" if status == "ready" else "review_blocked",
                "issues": "|".join(issues),
            }
        )
    return sorted(targets, key=lambda row: (row["guard_id"], row["archive_tag"], row["pcx_name"].lower()))


def build_support_rows(candidate_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    support: list[dict[str, str]] = []
    for row in candidate_rows:
        guard_id = row.get("guard_id", "")
        if row.get("large_rejected") == "yes" and guard_id in PROMOTABLE_GUARDS:
            continue
        if guard_id in PROMOTABLE_GUARDS:
            role = "nonlarge_guard_support"
        elif guard_id == "skip_large_negative_context":
            role = "skipped_large_negative_context"
        else:
            role = "outside_promotion_scope"
        support.append(
            {
                "archive_tag": row.get("archive_tag", ""),
                "pcx_name": row.get("pcx_name", ""),
                "delta_group": row.get("delta_group", ""),
                "guard_id": guard_id,
                "next_word_low_dec": row.get("next_word_low_dec", ""),
                "field16_high_dec": row.get("field16_high_dec", ""),
                "oracle_extra": row.get("oracle_extra", ""),
                "predicted_extra": row.get("predicted_extra", ""),
                "support_role": role,
                "issues": row.get("issues", ""),
            }
        )
    return sorted(support, key=lambda row: (row["support_role"], row["archive_tag"], row["pcx_name"].lower()))


def build_guard_rows(
    source_guards: list[dict[str, str]],
    candidate_rows: list[dict[str, str]],
    target_rows: list[dict[str, str]],
    support_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    targets_by_guard: dict[str, list[dict[str, str]]] = {}
    support_by_guard: dict[str, list[dict[str, str]]] = {}
    candidates_by_guard: dict[str, list[dict[str, str]]] = {}
    for row in target_rows:
        targets_by_guard.setdefault(row.get("guard_id", ""), []).append(row)
    for row in support_rows:
        support_by_guard.setdefault(row.get("guard_id", ""), []).append(row)
    for row in candidate_rows:
        candidates_by_guard.setdefault(row.get("guard_id", ""), []).append(row)

    output: list[dict[str, str]] = []
    for guard in source_guards:
        guard_id = guard.get("guard_id", "")
        source = candidates_by_guard.get(guard_id, [])
        targets = targets_by_guard.get(guard_id, [])
        support = support_by_guard.get(guard_id, [])
        source_false = [row for row in source if row.get("false_positive") == "yes"]
        target_issues = [row for row in targets if row.get("issues")]
        if guard_id == "skip_large_negative_context":
            scope = "context_only"
            verdict = "not_promoted_context_skipped" if not source_false else "context_has_false_positive"
        elif targets and not source_false and not target_issues:
            scope = "promote_large_exact_targets"
            verdict = "ready"
        elif targets:
            scope = "promote_large_exact_targets"
            verdict = "blocked"
        else:
            scope = "support_only"
            verdict = "support_only"
        output.append(
            {
                "guard_id": guard_id,
                "condition": guard.get("condition", ""),
                "predicted_extra": guard.get("predicted_extra", ""),
                "source_rows": str(len(source)),
                "source_exact_rows": str(sum(1 for row in source if row.get("exact_match") == "yes")),
                "target_rows": str(len(targets)),
                "target_exact_rows": str(sum(1 for row in targets if row.get("exact_match") == "yes")),
                "support_rows": str(len(support)),
                "context_rows": str(sum(1 for row in support if row.get("support_role") == "skipped_large_negative_context")),
                "false_positive_rows": str(len(source_false)),
                "promotion_scope": scope,
                "verdict": verdict,
            }
        )
    return output


def build_decision_rows(target_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        {
            "promotion_id": row.get("promotion_id", ""),
            "archive": row.get("archive_tag", ""),
            "name": row.get("pcx_name", ""),
            "guard_id": row.get("guard_id", ""),
            "predicted_extra": row.get("predicted_extra", ""),
            "review_status": row.get("promotion_status", ""),
            "review_note": row.get("promotion_reason", ""),
        }
        for row in target_rows
    ]


def build_summary(
    candidate_rows: list[dict[str, str]],
    target_rows: list[dict[str, str]],
    support_rows: list[dict[str, str]],
    guard_rows: list[dict[str, str]],
    decision_rows: list[dict[str, str]],
) -> dict[str, str]:
    applicable_rows = [row for row in candidate_rows if row.get("predicted_extra") != ""]
    exact_rows = [row for row in applicable_rows if row.get("exact_match") == "yes"]
    false_positive_rows = [row for row in candidate_rows if row.get("false_positive") == "yes"]
    large_rows = [row for row in candidate_rows if row.get("large_rejected") == "yes"]
    large_target_rows = [row for row in target_rows if row.get("large_rejected") == "yes"]
    large_target_exact_rows = [row for row in large_target_rows if row.get("exact_match") == "yes"]
    remaining_rows = [row for row in candidate_rows if row.get("remaining_large") == "yes"]
    remaining_target_rows = [row for row in target_rows if row.get("remaining_large") == "yes"]
    remaining_target_exact_rows = [row for row in remaining_target_rows if row.get("exact_match") == "yes"]
    support_exact_rows = [
        row
        for row in support_rows
        if row.get("support_role") == "nonlarge_guard_support" and row.get("predicted_extra") != ""
    ]
    skipped_context_rows = [
        row for row in support_rows if row.get("support_role") == "skipped_large_negative_context"
    ]
    issue_rows = [row for row in target_rows if row.get("issues")]
    guard_issue_rows = [row for row in guard_rows if row.get("verdict") in {"blocked", "context_has_false_positive"}]
    all_ready = (
        len(large_rows) == 4
        and len(large_target_rows) == 4
        and len(large_target_exact_rows) == 4
        and len(remaining_rows) == 2
        and len(remaining_target_exact_rows) == 2
        and len(false_positive_rows) == 0
        and not issue_rows
        and not guard_issue_rows
    )
    if all_ready:
        verdict = "small_delta_guard_review_ready"
        next_action = "promote guarded small-delta start transform into shifted 0x2a30 field16 replay"
    elif issue_rows or guard_issue_rows or false_positive_rows:
        verdict = "small_delta_guard_review_blocked"
        next_action = "fix guarded small-delta review issues before promotion"
    else:
        verdict = "small_delta_guard_review_needs_more_corpus"
        next_action = "expand shifted 0x2a30 field16 review corpus before promotion"
    return {
        "scope": "total",
        "candidate_rows": str(len(candidate_rows)),
        "applicable_rows": str(len(applicable_rows)),
        "exact_rows": str(len(exact_rows)),
        "false_positive_rows": str(len(false_positive_rows)),
        "large_rows": str(len(large_rows)),
        "large_target_rows": str(len(large_target_rows)),
        "large_target_exact_rows": str(len(large_target_exact_rows)),
        "remaining_large_rows": str(len(remaining_rows)),
        "remaining_target_rows": str(len(remaining_target_rows)),
        "remaining_target_exact_rows": str(len(remaining_target_exact_rows)),
        "support_rows": str(len(support_exact_rows)),
        "skipped_context_rows": str(len(skipped_context_rows)),
        "positive_target_rows": str(sum(1 for row in target_rows if row.get("guard_id") == "positive_small_nextlow_minus2")),
        "negative_target_rows": str(sum(1 for row in target_rows if row.get("guard_id") == "negative_small_extra36")),
        "zero_target_rows": str(sum(1 for row in target_rows if row.get("guard_id") == "zero_delta_extra40")),
        "selected_guard_rows": str(sum(1 for row in guard_rows if row.get("promotion_scope") == "promote_large_exact_targets")),
        "guard_rows": str(len(guard_rows)),
        "decision_template_rows": str(len(decision_rows)),
        "issue_rows": str(len(issue_rows) + len(guard_issue_rows)),
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
    target_rows: list[dict[str, str]],
    support_rows: list[dict[str, str]],
    guard_rows: list[dict[str, str]],
    decision_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "targets": target_rows,
        "support": support_rows,
        "guards": guard_rows,
        "decisions": decision_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("targets.csv", output_dir / "targets.csv"),
            ("support.csv", output_dir / "support.csv"),
            ("guards.csv", output_dir / "guards.csv"),
            ("decisions_template.tsv", output_dir / "decisions_template.tsv"),
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
<p class="muted">Reviews exact guarded small-delta start targets before promoting shifted 0x2a30 field16 replay rows.</p>
<p>{links}</p>
<h2>Summary</h2>
{render_table([summary], SUMMARY_FIELDNAMES)}
<h2>Promotion Targets</h2>
{render_table(target_rows, TARGET_FIELDNAMES)}
<h2>Guard Review</h2>
{render_table(guard_rows, GUARD_FIELDNAMES)}
<h2>Support and Context</h2>
{render_table(support_rows, SUPPORT_FIELDNAMES)}
<h2>Decision Template</h2>
{render_table(decision_rows, DECISION_FIELDNAMES)}
</main>
<script>const TEX_LARGE_SHIFTED_2A30_FIELD16_SMALL_DELTA_GUARD_REVIEW = {data_json};</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    candidates_path: Path,
    guards_path: Path,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    candidate_rows = read_csv(candidates_path)
    source_guards = read_csv(guards_path)
    target_rows = build_target_rows(candidate_rows)
    support_rows = build_support_rows(candidate_rows)
    guard_rows = build_guard_rows(source_guards, candidate_rows, target_rows, support_rows)
    decision_rows = build_decision_rows(target_rows)
    summary = build_summary(candidate_rows, target_rows, support_rows, guard_rows, decision_rows)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "targets.csv", TARGET_FIELDNAMES, target_rows)
    write_csv(output_dir / "support.csv", SUPPORT_FIELDNAMES, support_rows)
    write_csv(output_dir / "guards.csv", GUARD_FIELDNAMES, guard_rows)
    write_tsv(output_dir / "decisions_template.tsv", DECISION_FIELDNAMES, decision_rows)
    (output_dir / "index.html").write_text(
        build_html(summary, target_rows, support_rows, guard_rows, decision_rows, output_dir, title),
        encoding="utf-8",
    )
    return summary, target_rows, support_rows, guard_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Review shifted 0x2a30 field16 small-delta guard promotion targets.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--guards", type=Path, default=DEFAULT_GUARDS)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Large Shifted 2a30 Field16 Small Delta Guard Review",
    )
    args = parser.parse_args()

    summary, _target_rows, _support_rows, _guard_rows = write_report(
        args.output,
        args.candidates,
        args.guards,
        args.title,
    )
    print(f"Candidate rows: {summary['candidate_rows']}")
    print(f"Large targets: {summary['large_target_exact_rows']}/{summary['large_rows']}")
    print(f"Remaining targets: {summary['remaining_target_exact_rows']}/{summary['remaining_large_rows']}")
    print(f"Selected guards: {summary['selected_guard_rows']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
