#!/usr/bin/env python3
"""Profile start selectors for shifted 0x2a30 field16 transforms."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
from collections import Counter, defaultdict
from pathlib import Path


DEFAULT_OUTPUT = Path("output/tex_large_shifted_2a30_field16_selector_probe")
DEFAULT_TRANSFORMS = Path("output/tex_large_shifted_2a30_field16_transform_probe/transforms.csv")
DEFAULT_CHOICES = Path("reports/te_guarded_cmd20_v10_riskaware_markerknownsymadv_plus_puddle.tsv")
DEFAULT_MARKERS = Path("reports/te_marker_fields.tsv")

SUMMARY_FIELDNAMES = [
    "scope",
    "corpus_rows",
    "large_rejected_rows",
    "oracle_extra_values",
    "oracle_extra_counts",
    "oracle_unit_values",
    "next_word_low_delta_values",
    "next_word_low_delta_counts",
    "formula_rows",
    "best_formula",
    "best_formula_rows",
    "best_formula_large_rows",
    "large_remaining_after_best_formula",
    "selector_rows",
    "source_only_selector_rows",
    "best_source_only_selector",
    "best_source_only_repeated_rows",
    "best_source_only_repeated_large_rows",
    "best_source_only_conflicted_rows",
    "choice_context_selector_rows",
    "best_choice_context_selector",
    "best_choice_context_repeated_rows",
    "issue_rows",
    "review_verdict",
    "next_action",
]

CORPUS_FIELDNAMES = [
    "archive_tag",
    "pcx_name",
    "large_rejected",
    "choice_mode",
    "baseline_mode",
    "choice_score",
    "choice_filled",
    "payload_len",
    "marker_pos",
    "oracle_extra",
    "oracle_unit",
    "post1_dec",
    "field16_hex",
    "field16_low_dec",
    "field16_high_dec",
    "field16_low_div4",
    "field16_low_mod4",
    "next_word_low_dec",
    "next_word_high_dec",
    "next_word_low_delta",
    "next_word_low_band",
    "post1_direct_match",
    "next_word_low_x4_match",
    "field16_unit_direct_match",
    "field16_low_direct_match",
    "large_remaining_after_best_formula",
    "issues",
]

FORMULA_FIELDNAMES = [
    "formula_id",
    "scope",
    "rows",
    "matched_rows",
    "large_rows",
    "large_matched_rows",
    "candidate_values",
    "matched_large_pcx",
    "verdict",
    "next_probe",
]

SELECTOR_FIELDNAMES = [
    "selector_kind",
    "selector_family",
    "groups",
    "rows",
    "large_rows",
    "deterministic_groups",
    "deterministic_rows",
    "deterministic_large_rows",
    "repeated_deterministic_groups",
    "repeated_deterministic_rows",
    "repeated_deterministic_large_rows",
    "conflicted_groups",
    "conflicted_rows",
    "conflicted_large_rows",
    "largest_group_rows",
    "largest_group_values",
    "sample_groups",
    "verdict",
]


def read_csv(path: Path, *, delimiter: str = ",") -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter=delimiter))


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


def row_key(level: str, name: str) -> tuple[str, str]:
    return (level, name.lower())


def yes_no(value: bool) -> str:
    return "yes" if value else "no"


def counter_text(values: list[str]) -> str:
    counts = Counter(value for value in values if value != "")
    return "|".join(f"{value}:{count}" for value, count in counts.most_common())


def next_low_band(value: int) -> str:
    if value < 16:
        return "small_lt16"
    if value < 64:
        return "medium_lt64"
    return "large_ge64"


def build_corpus_rows(
    transform_rows: list[dict[str, str]],
    marker_rows: list[dict[str, str]],
    choice_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    large_keys = {
        row_key(row.get("archive_tag", ""), row.get("pcx_name", ""))
        for row in transform_rows
        if row.get("archive_tag") and row.get("pcx_name")
    }
    choices = {
        row_key(row.get("level", ""), row.get("name", "")): row
        for row in choice_rows
        if row.get("source") == "marker" and row.get("extra")
    }
    output: list[dict[str, str]] = []
    for marker in marker_rows:
        issues: list[str] = []
        if marker.get("marker") != "2a30" or int_value(marker, "b3") != 40:
            continue
        key = row_key(marker.get("level", ""), marker.get("name", ""))
        choice = choices.get(key, {})
        if not choice:
            continue

        oracle_extra = int_value(choice, "extra")
        field16 = int_value(marker, "u16_4")
        next_word = int_value(marker, "u16_6")
        field_low = field16 & 0xFF
        field_high = (field16 >> 8) & 0xFF
        next_low = next_word & 0xFF
        next_high = (next_word >> 8) & 0xFF
        field_unit = field_low // 4
        oracle_unit = oracle_extra // 4 if oracle_extra else 0
        post1 = int_value(marker, "b3")
        if oracle_extra % 4:
            issues.append("oracle_extra_not_mod4")

        post1_match = oracle_extra == post1
        next_low_match = oracle_extra == next_low * 4
        field_unit_match = oracle_extra == field_unit
        field_low_match = oracle_extra == field_low
        best_formula_match = post1_match or next_low_match

        output.append(
            {
                "archive_tag": marker.get("level", ""),
                "pcx_name": marker.get("name", ""),
                "large_rejected": yes_no(key in large_keys),
                "choice_mode": choice.get("mode", ""),
                "baseline_mode": choice.get("baseline_mode", ""),
                "choice_score": choice.get("score", ""),
                "choice_filled": choice.get("filled", ""),
                "payload_len": marker.get("payload_len", ""),
                "marker_pos": marker.get("marker_pos", ""),
                "oracle_extra": str(oracle_extra),
                "oracle_unit": str(oracle_unit),
                "post1_dec": str(post1),
                "field16_hex": f"0x{field16:04x}",
                "field16_low_dec": str(field_low),
                "field16_high_dec": str(field_high),
                "field16_low_div4": str(field_unit),
                "field16_low_mod4": str(field_low % 4),
                "next_word_low_dec": str(next_low),
                "next_word_high_dec": str(next_high),
                "next_word_low_delta": str(oracle_unit - next_low),
                "next_word_low_band": next_low_band(next_low),
                "post1_direct_match": yes_no(post1_match),
                "next_word_low_x4_match": yes_no(next_low_match),
                "field16_unit_direct_match": yes_no(field_unit_match),
                "field16_low_direct_match": yes_no(field_low_match),
                "large_remaining_after_best_formula": yes_no(key in large_keys and not best_formula_match),
                "issues": ";".join(dict.fromkeys(issues)),
            }
        )
    return sorted(output, key=lambda row: (row["archive_tag"], row["pcx_name"].lower()))


def formula_candidate(row: dict[str, str], formula_id: str) -> int:
    post1 = int_value(row, "post1_dec")
    next_low = int_value(row, "next_word_low_dec")
    field_unit = int_value(row, "field16_low_div4")
    field_low = int_value(row, "field16_low_dec")
    candidates = {
        "post1_direct_extra": post1,
        "next_word_low_x4": next_low * 4,
        "field16_low_unit_direct": field_unit,
        "field16_low_direct": field_low,
        "constant_16": 16,
        "constant_24": 24,
        "constant_32": 32,
        "constant_36": 36,
        "constant_40": 40,
    }
    return candidates[formula_id]


def build_formula_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    formulas = [
        ("post1_direct_extra", "post1 byte as extra"),
        ("next_word_low_x4", "next-word low byte times four"),
        ("field16_low_unit_direct", "field16 low-byte /4 as byte extra"),
        ("field16_low_direct", "field16 low byte as byte extra"),
        ("constant_16", "constant extra 16"),
        ("constant_24", "constant extra 24"),
        ("constant_32", "constant extra 32"),
        ("constant_36", "constant extra 36"),
        ("constant_40", "constant extra 40"),
    ]
    formula_priority = {formula_id: index for index, (formula_id, _scope) in enumerate(formulas)}
    output: list[dict[str, str]] = []
    for formula_id, scope in formulas:
        matched: list[dict[str, str]] = []
        candidates: list[str] = []
        for row in rows:
            candidate = formula_candidate(row, formula_id)
            candidates.append(str(candidate))
            if candidate == int_value(row, "oracle_extra"):
                matched.append(row)
        large = [row for row in rows if row.get("large_rejected") == "yes"]
        large_matched = [row for row in matched if row.get("large_rejected") == "yes"]
        if len(matched) == len(rows) and rows:
            verdict = "all_rows"
        elif matched:
            verdict = "partial_only"
        else:
            verdict = "rejected"
        output.append(
            {
                "formula_id": formula_id,
                "scope": scope,
                "rows": str(len(rows)),
                "matched_rows": str(len(matched)),
                "large_rows": str(len(large)),
                "large_matched_rows": str(len(large_matched)),
                "candidate_values": counter_text(candidates),
                "matched_large_pcx": "|".join(row.get("pcx_name", "") for row in large_matched),
                "verdict": verdict,
                "next_probe": (
                    "keep as partial guard only"
                    if matched and len(matched) < len(rows)
                    else "do not promote without selector"
                ),
            }
        )
    return sorted(
        output,
        key=lambda row: (
            -int_value(row, "large_matched_rows"),
            -int_value(row, "matched_rows"),
            formula_priority.get(row["formula_id"], 999),
        ),
    )


def selector_value(row: dict[str, str], family: str) -> str:
    parts = family.split("+")
    return "|".join(row.get(part, "") for part in parts)


def build_selector_row(kind: str, family: str, rows: list[dict[str, str]]) -> dict[str, str]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[selector_value(row, family)].append(row)

    deterministic: list[tuple[str, list[dict[str, str]], set[str]]] = []
    repeated: list[tuple[str, list[dict[str, str]], set[str]]] = []
    conflicted: list[tuple[str, list[dict[str, str]], set[str]]] = []
    for key, group_rows in grouped.items():
        values = {row.get("oracle_extra", "") for row in group_rows}
        if len(values) == 1:
            deterministic.append((key, group_rows, values))
            if len(group_rows) > 1:
                repeated.append((key, group_rows, values))
        else:
            conflicted.append((key, group_rows, values))

    largest_key = ""
    largest_rows: list[dict[str, str]] = []
    largest_values: set[str] = set()
    if grouped:
        largest_key, largest_rows = max(grouped.items(), key=lambda item: len(item[1]))
        largest_values = {row.get("oracle_extra", "") for row in largest_rows}

    def count_large(groups: list[tuple[str, list[dict[str, str]], set[str]]]) -> int:
        return sum(1 for _key, group_rows, _values in groups for row in group_rows if row.get("large_rejected") == "yes")

    sample_groups = []
    for key, group_rows, values in sorted(
        deterministic + conflicted,
        key=lambda item: (-len(item[1]), item[0]),
    )[:8]:
        sample_groups.append(f"{key}->{','.join(sorted(values))}({len(group_rows)})")

    if repeated and not conflicted:
        verdict = "repeated_deterministic"
    elif repeated:
        verdict = "partial_repeated_with_conflicts"
    elif deterministic and not conflicted:
        verdict = "singletons_only"
    else:
        verdict = "conflicted"

    return {
        "selector_kind": kind,
        "selector_family": family,
        "groups": str(len(grouped)),
        "rows": str(len(rows)),
        "large_rows": str(sum(1 for row in rows if row.get("large_rejected") == "yes")),
        "deterministic_groups": str(len(deterministic)),
        "deterministic_rows": str(sum(len(group_rows) for _key, group_rows, _values in deterministic)),
        "deterministic_large_rows": str(count_large(deterministic)),
        "repeated_deterministic_groups": str(len(repeated)),
        "repeated_deterministic_rows": str(sum(len(group_rows) for _key, group_rows, _values in repeated)),
        "repeated_deterministic_large_rows": str(count_large(repeated)),
        "conflicted_groups": str(len(conflicted)),
        "conflicted_rows": str(sum(len(group_rows) for _key, group_rows, _values in conflicted)),
        "conflicted_large_rows": str(count_large(conflicted)),
        "largest_group_rows": str(len(largest_rows)),
        "largest_group_values": ",".join(sorted(largest_values)),
        "sample_groups": "|".join(sample_groups),
        "verdict": verdict,
    }


def build_selector_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    source_only = [
        "field16_high_dec",
        "field16_low_div4",
        "next_word_low_dec",
        "next_word_high_dec",
        "next_word_low_band",
        "marker_pos",
        "field16_high_dec+next_word_low_dec",
        "field16_high_dec+next_word_high_dec",
        "next_word_low_dec+next_word_high_dec",
        "marker_pos+next_word_low_dec",
        "marker_pos+field16_high_dec",
    ]
    choice_context = [
        "choice_mode",
        "baseline_mode",
        "choice_mode+field16_high_dec",
        "choice_mode+next_word_low_dec",
        "baseline_mode+field16_high_dec",
    ]
    selector_rows = [build_selector_row("source_only", family, rows) for family in source_only]
    selector_rows.extend(build_selector_row("choice_context", family, rows) for family in choice_context)
    return sorted(
        selector_rows,
        key=lambda row: (
            row["selector_kind"],
            -int_value(row, "repeated_deterministic_rows"),
            int_value(row, "conflicted_rows"),
            row["selector_family"],
        ),
    )


def best_row(rows: list[dict[str, str]], kind: str) -> dict[str, str]:
    candidates = [row for row in rows if row.get("selector_kind") == kind]
    return max(
        candidates,
        key=lambda row: (
            int_value(row, "repeated_deterministic_rows"),
            int_value(row, "repeated_deterministic_large_rows"),
            -int_value(row, "conflicted_rows"),
        ),
        default={},
    )


def build_summary(
    corpus_rows: list[dict[str, str]],
    formula_rows: list[dict[str, str]],
    selector_rows: list[dict[str, str]],
) -> dict[str, str]:
    issue_rows = sum(1 for row in corpus_rows if row.get("issues"))
    large_rows = [row for row in corpus_rows if row.get("large_rejected") == "yes"]
    formula_priority = {row.get("formula_id", ""): index for index, row in enumerate(formula_rows)}
    best_formula = max(
        formula_rows,
        key=lambda row: (
            int_value(row, "large_matched_rows"),
            int_value(row, "matched_rows"),
            -formula_priority.get(row.get("formula_id", ""), 999),
        ),
        default={},
    )
    best_source = best_row(selector_rows, "source_only")
    best_choice = best_row(selector_rows, "choice_context")
    best_formula_large = int_value(best_formula, "large_matched_rows")
    large_remaining = max(0, len(large_rows) - best_formula_large)
    if issue_rows:
        verdict = "selector_probe_issues"
        next_action = "fix shifted 0x2a30 start selector probe issues"
    elif large_remaining:
        verdict = "start_selector_split_needed"
        next_action = (
            "expand shifted 0x2a30 start-selector corpus and split remaining "
            f"{large_remaining} large rows by next-low delta"
        )
    else:
        verdict = "start_selector_ready_for_guard_review"
        next_action = "review shifted 0x2a30 start selector guard for promotion"

    return {
        "scope": "total",
        "corpus_rows": str(len(corpus_rows)),
        "large_rejected_rows": str(len(large_rows)),
        "oracle_extra_values": str(len({row.get("oracle_extra", "") for row in corpus_rows})),
        "oracle_extra_counts": counter_text([row.get("oracle_extra", "") for row in corpus_rows]),
        "oracle_unit_values": str(len({row.get("oracle_unit", "") for row in corpus_rows})),
        "next_word_low_delta_values": str(len({row.get("next_word_low_delta", "") for row in corpus_rows})),
        "next_word_low_delta_counts": counter_text([row.get("next_word_low_delta", "") for row in corpus_rows]),
        "formula_rows": str(len(formula_rows)),
        "best_formula": best_formula.get("formula_id", ""),
        "best_formula_rows": best_formula.get("matched_rows", "0"),
        "best_formula_large_rows": best_formula.get("large_matched_rows", "0"),
        "large_remaining_after_best_formula": str(large_remaining),
        "selector_rows": str(len(selector_rows)),
        "source_only_selector_rows": str(sum(1 for row in selector_rows if row.get("selector_kind") == "source_only")),
        "best_source_only_selector": best_source.get("selector_family", ""),
        "best_source_only_repeated_rows": best_source.get("repeated_deterministic_rows", "0"),
        "best_source_only_repeated_large_rows": best_source.get("repeated_deterministic_large_rows", "0"),
        "best_source_only_conflicted_rows": best_source.get("conflicted_rows", "0"),
        "choice_context_selector_rows": str(
            sum(1 for row in selector_rows if row.get("selector_kind") == "choice_context")
        ),
        "best_choice_context_selector": best_choice.get("selector_family", ""),
        "best_choice_context_repeated_rows": best_choice.get("repeated_deterministic_rows", "0"),
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
    corpus: list[dict[str, str]],
    formulas: list[dict[str, str]],
    selectors: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "corpus": corpus, "formulas": formulas, "selectors": selectors}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("corpus.csv", output_dir / "corpus.csv"),
            ("formulas.csv", output_dir / "formulas.csv"),
            ("selectors.csv", output_dir / "selectors.csv"),
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
<p class="muted">Profiles guarded TE oracle starts for the broader 0x2a30 b3=40 corpus before any start selector is promoted.</p>
<p>{links}</p>
<h2>Summary</h2>
{render_table([summary], SUMMARY_FIELDNAMES)}
<h2>Formulas</h2>
{render_table(formulas, FORMULA_FIELDNAMES)}
<h2>Selectors</h2>
{render_table(selectors, SELECTOR_FIELDNAMES)}
<h2>Corpus</h2>
{render_table(corpus, CORPUS_FIELDNAMES)}
</main>
<script>const TEX_LARGE_SHIFTED_2A30_FIELD16_SELECTOR_PROBE = {data_json};</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    transforms_path: Path,
    choices_path: Path,
    markers_path: Path,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    corpus_rows = build_corpus_rows(
        read_csv(transforms_path),
        read_csv(markers_path, delimiter="\t"),
        read_csv(choices_path, delimiter="\t"),
    )
    formula_rows = build_formula_rows(corpus_rows)
    selector_rows = build_selector_rows(corpus_rows)
    summary = build_summary(corpus_rows, formula_rows, selector_rows)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "corpus.csv", CORPUS_FIELDNAMES, corpus_rows)
    write_csv(output_dir / "formulas.csv", FORMULA_FIELDNAMES, formula_rows)
    write_csv(output_dir / "selectors.csv", SELECTOR_FIELDNAMES, selector_rows)
    (output_dir / "index.html").write_text(
        build_html(summary, corpus_rows, formula_rows, selector_rows, output_dir, title),
        encoding="utf-8",
    )
    return summary, corpus_rows, formula_rows, selector_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile shifted 0x2a30 field16 start selectors.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--transforms", type=Path, default=DEFAULT_TRANSFORMS)
    parser.add_argument("--choices", type=Path, default=DEFAULT_CHOICES)
    parser.add_argument("--markers", type=Path, default=DEFAULT_MARKERS)
    parser.add_argument("--title", default="Lands of Lore II .tex Large Shifted 2a30 Field16 Selector Probe")
    args = parser.parse_args()

    summary, _corpus, _formulas, _selectors = write_report(
        args.output,
        args.transforms,
        args.choices,
        args.markers,
        args.title,
    )
    print(f"Corpus rows: {summary['corpus_rows']}")
    print(f"Large rejected rows: {summary['large_rejected_rows']}")
    print(f"Best formula: {summary['best_formula']} ({summary['best_formula_rows']})")
    print(f"Large remaining after best formula: {summary['large_remaining_after_best_formula']}")
    print(f"Best source-only selector: {summary['best_source_only_selector']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
