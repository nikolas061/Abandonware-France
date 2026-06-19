#!/usr/bin/env python3
"""Split remaining shifted 0x2a30 start-selector rows by signed next-low delta."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
from collections import Counter, defaultdict
from pathlib import Path


DEFAULT_OUTPUT = Path("output/tex_large_shifted_2a30_field16_delta_split_probe")
DEFAULT_CORPUS = Path("output/tex_large_shifted_2a30_field16_selector_probe/corpus.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "corpus_rows",
    "large_rejected_rows",
    "remaining_large_rows",
    "delta_values",
    "small_signed_delta_rows",
    "small_signed_delta_large_rows",
    "positive_small_delta_rows",
    "negative_small_delta_rows",
    "zero_delta_rows",
    "large_negative_delta_rows",
    "remaining_exact_delta_singletons",
    "remaining_near_delta_supported",
    "split_group_rows",
    "target_rows",
    "issue_rows",
    "review_verdict",
    "next_action",
]

DELTA_FIELDNAMES = [
    "archive_tag",
    "pcx_name",
    "large_rejected",
    "remaining_large",
    "oracle_extra",
    "oracle_unit",
    "next_word_low_dec",
    "next_word_high_dec",
    "next_word_low_delta",
    "delta_group",
    "choice_mode",
    "baseline_mode",
    "field16_high_dec",
    "field16_low_div4",
    "field16_low_mod4",
    "post1_direct_match",
    "next_word_low_x4_match",
    "issues",
]

SPLIT_FIELDNAMES = [
    "delta_group",
    "rows",
    "large_rows",
    "remaining_large_rows",
    "delta_values",
    "oracle_extra_values",
    "next_low_values",
    "field16_high_values",
    "choice_modes",
    "sample_pcx",
    "verdict",
    "next_probe",
]

TARGET_FIELDNAMES = [
    "archive_tag",
    "pcx_name",
    "target_delta",
    "target_extra",
    "target_next_low",
    "target_field16_high",
    "target_choice_mode",
    "exact_delta_rows",
    "exact_delta_nonlarge_rows",
    "near_delta_rows",
    "near_delta_nonlarge_rows",
    "near_delta_values",
    "near_support_pcx",
    "exact_delta_verdict",
    "near_delta_verdict",
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


def counter_text(values: list[str]) -> str:
    counts = Counter(value for value in values if value != "")
    return "|".join(f"{value}:{count}" for value, count in counts.most_common())


def delta_group(delta: int) -> str:
    if delta == 0:
        return "zero_delta"
    if 0 < delta <= 4:
        return "positive_small_delta"
    if -4 <= delta < 0:
        return "negative_small_delta"
    if delta < 0:
        return "large_negative_delta"
    return "large_positive_delta"


def build_delta_rows(corpus_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in corpus_rows:
        delta = int_value(row, "next_word_low_delta")
        remaining = row.get("large_remaining_after_best_formula") == "yes"
        rows.append(
            {
                "archive_tag": row.get("archive_tag", ""),
                "pcx_name": row.get("pcx_name", ""),
                "large_rejected": row.get("large_rejected", ""),
                "remaining_large": "yes" if remaining else "no",
                "oracle_extra": row.get("oracle_extra", ""),
                "oracle_unit": row.get("oracle_unit", ""),
                "next_word_low_dec": row.get("next_word_low_dec", ""),
                "next_word_high_dec": row.get("next_word_high_dec", ""),
                "next_word_low_delta": row.get("next_word_low_delta", ""),
                "delta_group": delta_group(delta),
                "choice_mode": row.get("choice_mode", ""),
                "baseline_mode": row.get("baseline_mode", ""),
                "field16_high_dec": row.get("field16_high_dec", ""),
                "field16_low_div4": row.get("field16_low_div4", ""),
                "field16_low_mod4": row.get("field16_low_mod4", ""),
                "post1_direct_match": row.get("post1_direct_match", ""),
                "next_word_low_x4_match": row.get("next_word_low_x4_match", ""),
                "issues": row.get("issues", ""),
            }
        )
    return sorted(rows, key=lambda row: (row["delta_group"], row["archive_tag"], row["pcx_name"].lower()))


def build_split_rows(delta_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in delta_rows:
        groups[row.get("delta_group", "")].append(row)
    output: list[dict[str, str]] = []
    for group, rows in sorted(groups.items()):
        large_rows = [row for row in rows if row.get("large_rejected") == "yes"]
        remaining_rows = [row for row in rows if row.get("remaining_large") == "yes"]
        if remaining_rows and len(rows) > len(remaining_rows):
            verdict = "remaining_has_near_support"
        elif remaining_rows:
            verdict = "remaining_singleton_group"
        else:
            verdict = "context_support"
        output.append(
            {
                "delta_group": group,
                "rows": str(len(rows)),
                "large_rows": str(len(large_rows)),
                "remaining_large_rows": str(len(remaining_rows)),
                "delta_values": counter_text([row.get("next_word_low_delta", "") for row in rows]),
                "oracle_extra_values": counter_text([row.get("oracle_extra", "") for row in rows]),
                "next_low_values": counter_text([row.get("next_word_low_dec", "") for row in rows]),
                "field16_high_values": counter_text([row.get("field16_high_dec", "") for row in rows]),
                "choice_modes": counter_text([row.get("choice_mode", "") for row in rows]),
                "sample_pcx": "|".join(row.get("pcx_name", "") for row in rows[:5]),
                "verdict": verdict,
                "next_probe": (
                    "derive signed small-delta guard before promotion"
                    if remaining_rows
                    else "use as support context only"
                ),
            }
        )
    return output


def build_target_rows(delta_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    targets = [row for row in delta_rows if row.get("remaining_large") == "yes"]
    output: list[dict[str, str]] = []
    for target in targets:
        delta = int_value(target, "next_word_low_delta")
        exact = [row for row in delta_rows if int_value(row, "next_word_low_delta") == delta]
        exact_nonlarge = [row for row in exact if row.get("remaining_large") != "yes"]
        near = [
            row
            for row in delta_rows
            if row is not target and abs(int_value(row, "next_word_low_delta") - delta) <= 1
        ]
        near_nonlarge = [row for row in near if row.get("large_rejected") != "yes"]
        exact_verdict = "singleton_exact_delta" if len(exact) == 1 else "has_exact_delta_support"
        near_verdict = "has_near_nonlarge_support" if near_nonlarge else "near_support_missing"
        output.append(
            {
                "archive_tag": target.get("archive_tag", ""),
                "pcx_name": target.get("pcx_name", ""),
                "target_delta": target.get("next_word_low_delta", ""),
                "target_extra": target.get("oracle_extra", ""),
                "target_next_low": target.get("next_word_low_dec", ""),
                "target_field16_high": target.get("field16_high_dec", ""),
                "target_choice_mode": target.get("choice_mode", ""),
                "exact_delta_rows": str(len(exact)),
                "exact_delta_nonlarge_rows": str(len(exact_nonlarge)),
                "near_delta_rows": str(len(near)),
                "near_delta_nonlarge_rows": str(len(near_nonlarge)),
                "near_delta_values": counter_text([row.get("next_word_low_delta", "") for row in near]),
                "near_support_pcx": "|".join(row.get("pcx_name", "") for row in near_nonlarge),
                "exact_delta_verdict": exact_verdict,
                "near_delta_verdict": near_verdict,
                "next_probe": (
                    "derive signed small-delta selector from near support"
                    if near_nonlarge
                    else "expand corpus for exact delta support"
                ),
            }
        )
    return output


def build_summary(
    delta_rows: list[dict[str, str]],
    split_rows: list[dict[str, str]],
    target_rows: list[dict[str, str]],
) -> dict[str, str]:
    issue_rows = sum(1 for row in delta_rows if row.get("issues"))
    large_rows = [row for row in delta_rows if row.get("large_rejected") == "yes"]
    remaining_rows = [row for row in delta_rows if row.get("remaining_large") == "yes"]
    small_signed = [
        row
        for row in delta_rows
        if row.get("delta_group") in {"positive_small_delta", "negative_small_delta"}
    ]
    exact_singletons = sum(1 for row in target_rows if row.get("exact_delta_verdict") == "singleton_exact_delta")
    near_supported = sum(1 for row in target_rows if row.get("near_delta_verdict") == "has_near_nonlarge_support")
    if issue_rows:
        verdict = "delta_split_issues"
        next_action = "fix shifted 0x2a30 delta split probe issues"
    elif exact_singletons and near_supported == len(target_rows):
        verdict = "delta_split_near_support_ready"
        next_action = "derive signed small-delta guards for +2 barsgld and -2 dragend before promotion"
    elif exact_singletons:
        verdict = "delta_split_needs_more_corpus"
        next_action = "expand shifted 0x2a30 corpus for exact delta singleton support"
    else:
        verdict = "delta_split_ready_for_guard_review"
        next_action = "review shifted 0x2a30 delta split guard for promotion"
    return {
        "scope": "total",
        "corpus_rows": str(len(delta_rows)),
        "large_rejected_rows": str(len(large_rows)),
        "remaining_large_rows": str(len(remaining_rows)),
        "delta_values": str(len({row.get("next_word_low_delta", "") for row in delta_rows})),
        "small_signed_delta_rows": str(len(small_signed)),
        "small_signed_delta_large_rows": str(sum(1 for row in small_signed if row.get("large_rejected") == "yes")),
        "positive_small_delta_rows": str(sum(1 for row in delta_rows if row.get("delta_group") == "positive_small_delta")),
        "negative_small_delta_rows": str(sum(1 for row in delta_rows if row.get("delta_group") == "negative_small_delta")),
        "zero_delta_rows": str(sum(1 for row in delta_rows if row.get("delta_group") == "zero_delta")),
        "large_negative_delta_rows": str(sum(1 for row in delta_rows if row.get("delta_group") == "large_negative_delta")),
        "remaining_exact_delta_singletons": str(exact_singletons),
        "remaining_near_delta_supported": str(near_supported),
        "split_group_rows": str(len(split_rows)),
        "target_rows": str(len(target_rows)),
        "issue_rows": str(issue_rows),
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
    delta_rows: list[dict[str, str]],
    split_rows: list[dict[str, str]],
    target_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "delta_rows": delta_rows, "splits": split_rows, "targets": target_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("deltas.csv", output_dir / "deltas.csv"),
            ("splits.csv", output_dir / "splits.csv"),
            ("targets.csv", output_dir / "targets.csv"),
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
<p class="muted">Splits remaining shifted 0x2a30 start rows by signed next-low delta and checks exact versus near support.</p>
<p>{links}</p>
<h2>Summary</h2>
{render_table([summary], SUMMARY_FIELDNAMES)}
<h2>Targets</h2>
{render_table(target_rows, TARGET_FIELDNAMES)}
<h2>Split Groups</h2>
{render_table(split_rows, SPLIT_FIELDNAMES)}
<h2>Deltas</h2>
{render_table(delta_rows, DELTA_FIELDNAMES)}
</main>
<script>const TEX_LARGE_SHIFTED_2A30_FIELD16_DELTA_SPLIT_PROBE = {data_json};</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    corpus_path: Path,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    delta_rows = build_delta_rows(read_csv(corpus_path))
    split_rows = build_split_rows(delta_rows)
    target_rows = build_target_rows(delta_rows)
    summary = build_summary(delta_rows, split_rows, target_rows)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "deltas.csv", DELTA_FIELDNAMES, delta_rows)
    write_csv(output_dir / "splits.csv", SPLIT_FIELDNAMES, split_rows)
    write_csv(output_dir / "targets.csv", TARGET_FIELDNAMES, target_rows)
    (output_dir / "index.html").write_text(
        build_html(summary, delta_rows, split_rows, target_rows, output_dir, title),
        encoding="utf-8",
    )
    return summary, delta_rows, split_rows, target_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Split shifted 0x2a30 field16 starts by signed next-low delta.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--title", default="Lands of Lore II .tex Large Shifted 2a30 Field16 Delta Split Probe")
    args = parser.parse_args()

    summary, _delta_rows, _split_rows, _target_rows = write_report(args.output, args.corpus, args.title)
    print(f"Corpus rows: {summary['corpus_rows']}")
    print(f"Remaining large rows: {summary['remaining_large_rows']}")
    print(f"Exact delta singletons: {summary['remaining_exact_delta_singletons']}")
    print(f"Near delta supported: {summary['remaining_near_delta_supported']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
