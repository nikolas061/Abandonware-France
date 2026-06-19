#!/usr/bin/env python3
"""Check guarded small-delta start formulas for shifted 0x2a30 field16 rows."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
from pathlib import Path


DEFAULT_OUTPUT = Path("output/tex_large_shifted_2a30_field16_small_delta_guard_probe")
DEFAULT_DELTAS = Path("output/tex_large_shifted_2a30_field16_delta_split_probe/deltas.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "corpus_rows",
    "applicable_rows",
    "exact_rows",
    "false_positive_rows",
    "skipped_rows",
    "large_rows",
    "large_applicable_rows",
    "large_exact_rows",
    "remaining_large_rows",
    "remaining_applicable_rows",
    "remaining_exact_rows",
    "positive_guard_rows",
    "negative_guard_rows",
    "zero_guard_rows",
    "skipped_large_negative_rows",
    "guard_rows",
    "issue_rows",
    "review_verdict",
    "next_action",
]

ROW_FIELDNAMES = [
    "archive_tag",
    "pcx_name",
    "large_rejected",
    "remaining_large",
    "delta_group",
    "next_word_low_dec",
    "field16_high_dec",
    "oracle_extra",
    "guard_id",
    "predicted_extra",
    "exact_match",
    "false_positive",
    "choice_mode",
    "issues",
]

GUARD_FIELDNAMES = [
    "guard_id",
    "condition",
    "predicted_extra",
    "rows",
    "exact_rows",
    "large_rows",
    "large_exact_rows",
    "remaining_rows",
    "remaining_exact_rows",
    "verdict",
    "next_probe",
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


def int_value(row: dict[str, str], field: str) -> int:
    raw = row.get(field, "")
    try:
        return int(raw, 0) if raw != "" else 0
    except ValueError:
        return 0


def guard_prediction(next_low: int, field16_high: int) -> tuple[str, int | None]:
    if 4 <= next_low <= 7 and field16_high in {1, 2}:
        return "positive_small_nextlow_minus2", (2 * next_low - 2) * 4
    if 8 <= next_low <= 15 and field16_high in {1, 6}:
        return "negative_small_extra36", 36
    if next_low == 10 and field16_high in {0, 64}:
        return "zero_delta_extra40", 40
    return "skip_large_negative_context", None


def build_candidate_rows(delta_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    for row in delta_rows:
        next_low = int_value(row, "next_word_low_dec")
        field16_high = int_value(row, "field16_high_dec")
        oracle_extra = int_value(row, "oracle_extra")
        guard_id, predicted_extra = guard_prediction(next_low, field16_high)
        exact_match = predicted_extra == oracle_extra if predicted_extra is not None else False
        false_positive = predicted_extra is not None and not exact_match
        issues: list[str] = []
        if false_positive:
            issues.append("predicted_extra_mismatch")
        if row.get("remaining_large") == "yes" and not exact_match:
            issues.append("remaining_large_uncovered")
        if row.get("large_rejected") == "yes" and not exact_match:
            issues.append("large_rejected_uncovered")
        if row.get("delta_group") == "large_negative_delta" and predicted_extra is not None:
            issues.append("large_negative_delta_not_skipped")
        candidates.append(
            {
                "archive_tag": row.get("archive_tag", ""),
                "pcx_name": row.get("pcx_name", ""),
                "large_rejected": row.get("large_rejected", ""),
                "remaining_large": row.get("remaining_large", ""),
                "delta_group": row.get("delta_group", ""),
                "next_word_low_dec": row.get("next_word_low_dec", ""),
                "field16_high_dec": row.get("field16_high_dec", ""),
                "oracle_extra": row.get("oracle_extra", ""),
                "guard_id": guard_id,
                "predicted_extra": "" if predicted_extra is None else str(predicted_extra),
                "exact_match": "yes" if exact_match else "no",
                "false_positive": "yes" if false_positive else "no",
                "choice_mode": row.get("choice_mode", ""),
                "issues": "|".join(issues),
            }
        )
    return sorted(candidates, key=lambda row: (row["guard_id"], row["archive_tag"], row["pcx_name"].lower()))


def build_guard_rows(candidate_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    specs = [
        (
            "positive_small_nextlow_minus2",
            "4 <= next_word_low_dec <= 7 and field16_high_dec in {1,2}",
            "(2 * next_word_low_dec - 2) * 4",
            "promote positive small-delta guard after review",
        ),
        (
            "negative_small_extra36",
            "8 <= next_word_low_dec <= 15 and field16_high_dec in {1,6}",
            "36",
            "promote negative small-delta guard after review",
        ),
        (
            "zero_delta_extra40",
            "next_word_low_dec == 10 and field16_high_dec in {0,64}",
            "40",
            "keep zero-delta support guard with small-delta promotion",
        ),
        (
            "skip_large_negative_context",
            "all other shifted 0x2a30 field16 rows",
            "",
            "keep large-negative context outside this promotion",
        ),
    ]
    output: list[dict[str, str]] = []
    for guard_id, condition, predicted_extra, next_probe in specs:
        rows = [row for row in candidate_rows if row.get("guard_id") == guard_id]
        exact_rows = [row for row in rows if row.get("exact_match") == "yes"]
        large_rows = [row for row in rows if row.get("large_rejected") == "yes"]
        large_exact_rows = [row for row in large_rows if row.get("exact_match") == "yes"]
        remaining_rows = [row for row in rows if row.get("remaining_large") == "yes"]
        remaining_exact_rows = [row for row in remaining_rows if row.get("exact_match") == "yes"]
        if guard_id == "skip_large_negative_context":
            verdict = "context_skipped" if all(row.get("delta_group") == "large_negative_delta" for row in rows) else "skip_mixed"
        elif len(rows) == len(exact_rows):
            verdict = "exact_on_applicable_rows"
        else:
            verdict = "needs_split"
        output.append(
            {
                "guard_id": guard_id,
                "condition": condition,
                "predicted_extra": predicted_extra,
                "rows": str(len(rows)),
                "exact_rows": str(len(exact_rows)),
                "large_rows": str(len(large_rows)),
                "large_exact_rows": str(len(large_exact_rows)),
                "remaining_rows": str(len(remaining_rows)),
                "remaining_exact_rows": str(len(remaining_exact_rows)),
                "verdict": verdict,
                "next_probe": next_probe,
            }
        )
    return output


def build_summary(candidate_rows: list[dict[str, str]], guard_rows: list[dict[str, str]]) -> dict[str, str]:
    applicable_rows = [row for row in candidate_rows if row.get("predicted_extra") != ""]
    exact_rows = [row for row in applicable_rows if row.get("exact_match") == "yes"]
    false_positive_rows = [row for row in candidate_rows if row.get("false_positive") == "yes"]
    large_rows = [row for row in candidate_rows if row.get("large_rejected") == "yes"]
    large_applicable_rows = [row for row in large_rows if row.get("predicted_extra") != ""]
    large_exact_rows = [row for row in large_rows if row.get("exact_match") == "yes"]
    remaining_rows = [row for row in candidate_rows if row.get("remaining_large") == "yes"]
    remaining_applicable_rows = [row for row in remaining_rows if row.get("predicted_extra") != ""]
    remaining_exact_rows = [row for row in remaining_rows if row.get("exact_match") == "yes"]
    issue_rows = [row for row in candidate_rows if row.get("issues")]
    positive_rows = [row for row in candidate_rows if row.get("guard_id") == "positive_small_nextlow_minus2"]
    negative_rows = [row for row in candidate_rows if row.get("guard_id") == "negative_small_extra36"]
    zero_rows = [row for row in candidate_rows if row.get("guard_id") == "zero_delta_extra40"]
    skipped_large_negative_rows = [
        row
        for row in candidate_rows
        if row.get("guard_id") == "skip_large_negative_context" and row.get("delta_group") == "large_negative_delta"
    ]
    if issue_rows:
        verdict = "small_delta_guard_issues"
        next_action = "fix guarded small-delta start transform issues before promotion"
    elif len(large_exact_rows) == len(large_rows) and len(remaining_exact_rows) == len(remaining_rows):
        verdict = "small_delta_guard_ready_for_review"
        next_action = "review guarded small-delta start transform for promotion on 4 large rows"
    else:
        verdict = "small_delta_guard_needs_more_corpus"
        next_action = "expand shifted 0x2a30 field16 corpus before guarded small-delta promotion"
    return {
        "scope": "total",
        "corpus_rows": str(len(candidate_rows)),
        "applicable_rows": str(len(applicable_rows)),
        "exact_rows": str(len(exact_rows)),
        "false_positive_rows": str(len(false_positive_rows)),
        "skipped_rows": str(len(candidate_rows) - len(applicable_rows)),
        "large_rows": str(len(large_rows)),
        "large_applicable_rows": str(len(large_applicable_rows)),
        "large_exact_rows": str(len(large_exact_rows)),
        "remaining_large_rows": str(len(remaining_rows)),
        "remaining_applicable_rows": str(len(remaining_applicable_rows)),
        "remaining_exact_rows": str(len(remaining_exact_rows)),
        "positive_guard_rows": str(len(positive_rows)),
        "negative_guard_rows": str(len(negative_rows)),
        "zero_guard_rows": str(len(zero_rows)),
        "skipped_large_negative_rows": str(len(skipped_large_negative_rows)),
        "guard_rows": str(len(guard_rows)),
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
    candidate_rows: list[dict[str, str]],
    guard_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "candidates": candidate_rows, "guards": guard_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("candidates.csv", output_dir / "candidates.csv"),
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
<p class="muted">Tests guarded shifted 0x2a30 field16 start formulas for positive, negative and zero small-delta rows.</p>
<p>{links}</p>
<h2>Summary</h2>
{render_table([summary], SUMMARY_FIELDNAMES)}
<h2>Guard Definitions</h2>
{render_table(guard_rows, GUARD_FIELDNAMES)}
<h2>Candidates</h2>
{render_table(candidate_rows, ROW_FIELDNAMES)}
</main>
<script>const TEX_LARGE_SHIFTED_2A30_FIELD16_SMALL_DELTA_GUARD_PROBE = {data_json};</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    deltas_path: Path,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    candidate_rows = build_candidate_rows(read_csv(deltas_path))
    guard_rows = build_guard_rows(candidate_rows)
    summary = build_summary(candidate_rows, guard_rows)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "candidates.csv", ROW_FIELDNAMES, candidate_rows)
    write_csv(output_dir / "guards.csv", GUARD_FIELDNAMES, guard_rows)
    (output_dir / "index.html").write_text(
        build_html(summary, candidate_rows, guard_rows, output_dir, title),
        encoding="utf-8",
    )
    return summary, candidate_rows, guard_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Check shifted 0x2a30 field16 small-delta guards.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--deltas", type=Path, default=DEFAULT_DELTAS)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Large Shifted 2a30 Field16 Small Delta Guard Probe",
    )
    args = parser.parse_args()

    summary, _candidate_rows, _guard_rows = write_report(args.output, args.deltas, args.title)
    print(f"Corpus rows: {summary['corpus_rows']}")
    print(f"Applicable rows: {summary['applicable_rows']}")
    print(f"Large exact rows: {summary['large_exact_rows']}/{summary['large_rows']}")
    print(f"Remaining exact rows: {summary['remaining_exact_rows']}/{summary['remaining_large_rows']}")
    print(f"False positives: {summary['false_positive_rows']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
