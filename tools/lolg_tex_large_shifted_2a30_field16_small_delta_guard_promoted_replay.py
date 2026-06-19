#!/usr/bin/env python3
"""Replay promoted guarded shifted 0x2a30 field16 small-delta starts."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
from pathlib import Path


DEFAULT_OUTPUT = Path("output/tex_large_shifted_2a30_field16_small_delta_guard_promoted_replay")
DEFAULT_CANDIDATES = Path("output/tex_large_shifted_2a30_field16_small_delta_guard_probe/candidates.csv")
DEFAULT_REVIEW_TARGETS = Path("output/tex_large_shifted_2a30_field16_small_delta_guard_review/targets.csv")
DEFAULT_REVIEW_GUARDS = Path("output/tex_large_shifted_2a30_field16_small_delta_guard_review/guards.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_rows",
    "review_target_rows",
    "promoted_rows",
    "promoted_exact_rows",
    "promoted_large_rows",
    "promoted_remaining_rows",
    "promoted_support_rows",
    "promoted_positive_rows",
    "promoted_negative_rows",
    "promoted_zero_rows",
    "blocked_context_rows",
    "false_positive_rows",
    "unresolved_target_rows",
    "guard_rows",
    "issue_rows",
    "review_verdict",
    "next_action",
]

OPERATION_FIELDNAMES = [
    "archive_tag",
    "pcx_name",
    "row_role",
    "large_rejected",
    "remaining_large",
    "delta_group",
    "guard_id",
    "promoted",
    "target_promoted",
    "support_promoted",
    "context_blocked",
    "next_word_low_dec",
    "field16_high_dec",
    "oracle_extra",
    "chosen_extra",
    "exact_match",
    "false_positive",
    "promotion_source",
    "issues",
]

TARGET_FIELDNAMES = [
    "archive_tag",
    "pcx_name",
    "guard_id",
    "delta_group",
    "oracle_extra",
    "chosen_extra",
    "target_replayed",
    "target_exact",
    "issues",
]

GUARD_FIELDNAMES = [
    "guard_id",
    "promotion_scope",
    "source_rows",
    "promoted_rows",
    "promoted_exact_rows",
    "promoted_large_rows",
    "promoted_remaining_rows",
    "blocked_context_rows",
    "false_positive_rows",
    "verdict",
    "next_probe",
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


def row_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("archive_tag", ""), row.get("pcx_name", "").lower(), row.get("guard_id", "")


def build_operations(
    candidate_rows: list[dict[str, str]],
    review_targets: list[dict[str, str]],
) -> list[dict[str, str]]:
    target_keys = {row_key(row) for row in review_targets}
    operations: list[dict[str, str]] = []
    for row in candidate_rows:
        guard_id = row.get("guard_id", "")
        promoted = guard_id in PROMOTABLE_GUARDS and row.get("predicted_extra") != ""
        target_promoted = row_key(row) in target_keys and promoted
        support_promoted = promoted and not target_promoted
        context_blocked = guard_id == "skip_large_negative_context" and not promoted
        issues: list[str] = []
        if target_promoted and row.get("exact_match") != "yes":
            issues.append("target_not_exact")
        if support_promoted and row.get("exact_match") != "yes":
            issues.append("support_not_exact")
        if context_blocked and row.get("delta_group") != "large_negative_delta":
            issues.append("blocked_non_large_negative_context")
        if promoted and row.get("false_positive") == "yes":
            issues.append("promoted_false_positive")
        if row.get("issues"):
            issues.append(f"source_issues:{row.get('issues')}")
        if row.get("large_rejected") == "yes" and not promoted:
            issues.append("large_row_not_promoted")
        if target_promoted:
            row_role = "promotion_target"
            promotion_source = "review_target"
        elif support_promoted:
            row_role = "nonlarge_support"
            promotion_source = "guard_support"
        elif context_blocked:
            row_role = "blocked_context"
            promotion_source = "large_negative_context_skip"
        else:
            row_role = "outside_scope"
            promotion_source = "not_promoted"
        chosen_extra = row.get("predicted_extra", "") if promoted else ""
        exact_match = row.get("exact_match", "no") if promoted else "no"
        operations.append(
            {
                "archive_tag": row.get("archive_tag", ""),
                "pcx_name": row.get("pcx_name", ""),
                "row_role": row_role,
                "large_rejected": row.get("large_rejected", ""),
                "remaining_large": row.get("remaining_large", ""),
                "delta_group": row.get("delta_group", ""),
                "guard_id": guard_id,
                "promoted": "yes" if promoted else "no",
                "target_promoted": "yes" if target_promoted else "no",
                "support_promoted": "yes" if support_promoted else "no",
                "context_blocked": "yes" if context_blocked else "no",
                "next_word_low_dec": row.get("next_word_low_dec", ""),
                "field16_high_dec": row.get("field16_high_dec", ""),
                "oracle_extra": row.get("oracle_extra", ""),
                "chosen_extra": chosen_extra,
                "exact_match": exact_match,
                "false_positive": row.get("false_positive", ""),
                "promotion_source": promotion_source,
                "issues": "|".join(issues),
            }
        )
    return sorted(operations, key=lambda row: (row["row_role"], row["guard_id"], row["archive_tag"], row["pcx_name"].lower()))


def build_target_rows(operations: list[dict[str, str]]) -> list[dict[str, str]]:
    targets: list[dict[str, str]] = []
    for row in operations:
        if row.get("target_promoted") != "yes":
            continue
        issues: list[str] = []
        if row.get("exact_match") != "yes":
            issues.append("target_not_exact")
        if row.get("chosen_extra") != row.get("oracle_extra"):
            issues.append("target_extra_mismatch")
        if row.get("issues"):
            issues.append(f"operation_issues:{row.get('issues')}")
        targets.append(
            {
                "archive_tag": row.get("archive_tag", ""),
                "pcx_name": row.get("pcx_name", ""),
                "guard_id": row.get("guard_id", ""),
                "delta_group": row.get("delta_group", ""),
                "oracle_extra": row.get("oracle_extra", ""),
                "chosen_extra": row.get("chosen_extra", ""),
                "target_replayed": "yes",
                "target_exact": "yes" if not issues else "no",
                "issues": "|".join(issues),
            }
        )
    return sorted(targets, key=lambda row: (row["guard_id"], row["archive_tag"], row["pcx_name"].lower()))


def build_guard_rows(review_guards: list[dict[str, str]], operations: list[dict[str, str]]) -> list[dict[str, str]]:
    operations_by_guard: dict[str, list[dict[str, str]]] = {}
    for row in operations:
        operations_by_guard.setdefault(row.get("guard_id", ""), []).append(row)
    output: list[dict[str, str]] = []
    for guard in review_guards:
        guard_id = guard.get("guard_id", "")
        rows = operations_by_guard.get(guard_id, [])
        promoted_rows = [row for row in rows if row.get("promoted") == "yes"]
        exact_rows = [row for row in promoted_rows if row.get("exact_match") == "yes"]
        large_rows = [row for row in promoted_rows if row.get("large_rejected") == "yes"]
        remaining_rows = [row for row in promoted_rows if row.get("remaining_large") == "yes"]
        blocked_context_rows = [row for row in rows if row.get("context_blocked") == "yes"]
        false_positive_rows = [row for row in promoted_rows if row.get("false_positive") == "yes"]
        issue_rows = [row for row in rows if row.get("issues")]
        if guard_id == "skip_large_negative_context":
            verdict = "context_blocked" if len(blocked_context_rows) == len(rows) and not issue_rows else "context_issue"
            next_probe = "keep large-negative context outside small-delta replay"
        elif promoted_rows and len(promoted_rows) == len(exact_rows) and not false_positive_rows and not issue_rows:
            verdict = "promoted_exact"
            next_probe = "integrate promoted guard into shifted 0x2a30 field16 decoder"
        elif promoted_rows:
            verdict = "promoted_with_issues"
            next_probe = "fix promoted small-delta replay issues"
        else:
            verdict = "not_promoted"
            next_probe = "review guard promotion scope"
        output.append(
            {
                "guard_id": guard_id,
                "promotion_scope": guard.get("promotion_scope", ""),
                "source_rows": str(len(rows)),
                "promoted_rows": str(len(promoted_rows)),
                "promoted_exact_rows": str(len(exact_rows)),
                "promoted_large_rows": str(len(large_rows)),
                "promoted_remaining_rows": str(len(remaining_rows)),
                "blocked_context_rows": str(len(blocked_context_rows)),
                "false_positive_rows": str(len(false_positive_rows)),
                "verdict": verdict,
                "next_probe": next_probe,
            }
        )
    return output


def build_summary(
    operations: list[dict[str, str]],
    target_rows: list[dict[str, str]],
    guard_rows: list[dict[str, str]],
    review_target_rows: list[dict[str, str]],
) -> dict[str, str]:
    promoted_rows = [row for row in operations if row.get("promoted") == "yes"]
    promoted_exact_rows = [row for row in promoted_rows if row.get("exact_match") == "yes"]
    promoted_large_rows = [row for row in promoted_rows if row.get("large_rejected") == "yes"]
    promoted_remaining_rows = [row for row in promoted_rows if row.get("remaining_large") == "yes"]
    promoted_support_rows = [row for row in promoted_rows if row.get("support_promoted") == "yes"]
    blocked_context_rows = [row for row in operations if row.get("context_blocked") == "yes"]
    false_positive_rows = [row for row in promoted_rows if row.get("false_positive") == "yes"]
    unresolved_targets = [row for row in target_rows if row.get("target_exact") != "yes"]
    issue_rows = [row for row in operations if row.get("issues")]
    guard_issue_rows = [row for row in guard_rows if row.get("verdict") in {"context_issue", "promoted_with_issues"}]
    clean = (
        len(operations) == 10
        and len(review_target_rows) == 4
        and len(promoted_rows) == 6
        and len(promoted_exact_rows) == 6
        and len(promoted_large_rows) == 4
        and len(promoted_remaining_rows) == 2
        and len(promoted_support_rows) == 2
        and len(blocked_context_rows) == 4
        and not false_positive_rows
        and not unresolved_targets
        and not issue_rows
        and not guard_issue_rows
    )
    if clean:
        verdict = "small_delta_guard_promoted_replay_ready"
        next_action = "integrate promoted small-delta replay into shifted 0x2a30 field16 decoder"
    elif issue_rows or guard_issue_rows or false_positive_rows:
        verdict = "small_delta_guard_promoted_replay_issues"
        next_action = "fix promoted small-delta replay issues before decoder integration"
    else:
        verdict = "small_delta_guard_promoted_replay_incomplete"
        next_action = "complete promoted small-delta replay coverage before decoder integration"
    return {
        "scope": "total",
        "candidate_rows": str(len(operations)),
        "review_target_rows": str(len(review_target_rows)),
        "promoted_rows": str(len(promoted_rows)),
        "promoted_exact_rows": str(len(promoted_exact_rows)),
        "promoted_large_rows": str(len(promoted_large_rows)),
        "promoted_remaining_rows": str(len(promoted_remaining_rows)),
        "promoted_support_rows": str(len(promoted_support_rows)),
        "promoted_positive_rows": str(sum(1 for row in promoted_rows if row.get("guard_id") == "positive_small_nextlow_minus2")),
        "promoted_negative_rows": str(sum(1 for row in promoted_rows if row.get("guard_id") == "negative_small_extra36")),
        "promoted_zero_rows": str(sum(1 for row in promoted_rows if row.get("guard_id") == "zero_delta_extra40")),
        "blocked_context_rows": str(len(blocked_context_rows)),
        "false_positive_rows": str(len(false_positive_rows)),
        "unresolved_target_rows": str(len(unresolved_targets)),
        "guard_rows": str(len(guard_rows)),
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
    operations: list[dict[str, str]],
    target_rows: list[dict[str, str]],
    guard_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "operations": operations, "targets": target_rows, "guards": guard_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("operations.csv", output_dir / "operations.csv"),
            ("targets.csv", output_dir / "targets.csv"),
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
td {{ max-width: 420px; overflow-wrap: anywhere; }}
</style>
</head>
<body>
<main>
<h1>{html.escape(title)}</h1>
<p class="muted">Replays the promoted small-delta start guards and keeps large-negative delta context blocked.</p>
<p>{links}</p>
<h2>Summary</h2>
{render_table([summary], SUMMARY_FIELDNAMES)}
<h2>Replay Targets</h2>
{render_table(target_rows, TARGET_FIELDNAMES)}
<h2>Guard Replay</h2>
{render_table(guard_rows, GUARD_FIELDNAMES)}
<h2>Operations</h2>
{render_table(operations, OPERATION_FIELDNAMES)}
</main>
<script>const TEX_LARGE_SHIFTED_2A30_FIELD16_SMALL_DELTA_GUARD_PROMOTED_REPLAY = {data_json};</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    candidates_path: Path,
    review_targets_path: Path,
    review_guards_path: Path,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    candidate_rows = read_csv(candidates_path)
    review_target_rows = read_csv(review_targets_path)
    review_guard_rows = read_csv(review_guards_path)
    operations = build_operations(candidate_rows, review_target_rows)
    target_rows = build_target_rows(operations)
    guard_rows = build_guard_rows(review_guard_rows, operations)
    summary = build_summary(operations, target_rows, guard_rows, review_target_rows)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "operations.csv", OPERATION_FIELDNAMES, operations)
    write_csv(output_dir / "targets.csv", TARGET_FIELDNAMES, target_rows)
    write_csv(output_dir / "guards.csv", GUARD_FIELDNAMES, guard_rows)
    (output_dir / "index.html").write_text(
        build_html(summary, operations, target_rows, guard_rows, output_dir, title),
        encoding="utf-8",
    )
    return summary, operations, target_rows, guard_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay promoted shifted 0x2a30 field16 small-delta guards.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--review-targets", type=Path, default=DEFAULT_REVIEW_TARGETS)
    parser.add_argument("--review-guards", type=Path, default=DEFAULT_REVIEW_GUARDS)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Large Shifted 2a30 Field16 Small Delta Guard Promoted Replay",
    )
    args = parser.parse_args()

    summary, _operations, _target_rows, _guard_rows = write_report(
        args.output,
        args.candidates,
        args.review_targets,
        args.review_guards,
        args.title,
    )
    print(f"Candidate rows: {summary['candidate_rows']}")
    print(f"Promoted rows: {summary['promoted_exact_rows']}/{summary['promoted_rows']}")
    print(f"Promoted large rows: {summary['promoted_large_rows']}")
    print(f"Blocked context rows: {summary['blocked_context_rows']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
