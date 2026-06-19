#!/usr/bin/env python3
"""Derive start-transform evidence for shifted 0x2a30 field16 rows."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
from collections import Counter
from pathlib import Path


DEFAULT_OUTPUT = Path("output/tex_large_shifted_2a30_field16_transform_probe")
DEFAULT_FIELD16 = Path("output/tex_large_shifted_2a30_field16_probe/field16.csv")
DEFAULT_ANCHORS = Path("output/tex_large_shifted_2a30_standard_probe/anchors.csv")
DEFAULT_CHOICES = Path("reports/te_guarded_cmd20_v10_riskaware_markerknownsymadv_plus_puddle.tsv")
DEFAULT_MARKERS = Path("reports/te_marker_fields.tsv")
DEFAULT_PROLOGUES = Path("reports/te_prologue_families.tsv")

SUMMARY_FIELDNAMES = [
    "scope",
    "standard_rows",
    "oracle_rows",
    "marker_bridge_rows",
    "prologue_rows",
    "distinct_oracle_extra",
    "oracle_extra_values",
    "field16_unit_direct_rows",
    "field16_low_direct_rows",
    "post1_direct_rows",
    "next_word_low_x4_rows",
    "next_word_low_delta_values",
    "next_word_low_delta_counts",
    "best_direct_rule",
    "best_direct_rows",
    "selector_needed_rows",
    "rule_rows",
    "issue_rows",
    "next_action",
]

TRANSFORM_FIELDNAMES = [
    "segment_id",
    "archive_tag",
    "pcx_name",
    "choice_source",
    "choice_mode",
    "choice_width",
    "choice_height",
    "choice_score",
    "choice_filled",
    "marker_pos",
    "anchor_offset",
    "oracle_extra",
    "oracle_start",
    "oracle_extra_unit",
    "post1_dec",
    "field16_hex",
    "field16_low_dec",
    "field16_high_dec",
    "field16_low_div4",
    "next_word_low_dec",
    "next_word_high_dec",
    "field16_unit_direct_match",
    "field16_low_direct_match",
    "post1_direct_match",
    "next_word_low_x4_match",
    "next_word_low_delta",
    "selector_byte_dec",
    "selector_to_oracle_delta",
    "prologue_family",
    "prologue_start",
    "prologue_start_minus_marker",
    "byte_at_start",
    "byte_before_start",
    "before_start_hex",
    "after_start_hex",
    "issues",
]

RULE_FIELDNAMES = [
    "rule_id",
    "scope",
    "rows",
    "matched_rows",
    "distinct_values",
    "values",
    "verdict",
    "next_probe",
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


def lower_name(row: dict[str, str], field: str = "pcx_name") -> str:
    return row.get(field, "").lower()


def choice_key(row: dict[str, str]) -> tuple[str, str]:
    return (row.get("level", ""), row.get("name", "").lower())


def row_key(row: dict[str, str]) -> tuple[str, str]:
    return (row.get("archive_tag", ""), lower_name(row))


def lookup_by_key(rows: list[dict[str, str]], key_fields: tuple[str, str]) -> dict[tuple[str, str], dict[str, str]]:
    left, right = key_fields
    return {(row.get(left, ""), row.get(right, "").lower()): row for row in rows}


def bool_text(value: bool) -> str:
    return "yes" if value else "no"


def build_transform_rows(
    field_rows: list[dict[str, str]],
    anchors: dict[str, dict[str, str]],
    choices: dict[tuple[str, str], dict[str, str]],
    markers: dict[tuple[str, str], dict[str, str]],
    prologues: dict[tuple[str, str], dict[str, str]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for field in field_rows:
        issues: list[str] = []
        segment_id = field.get("segment_id", "")
        anchor = anchors.get(segment_id, {})
        key = row_key(field)
        choice = choices.get(key, {})
        marker = markers.get(key, {})
        prologue = prologues.get(key, {})

        if not anchor:
            issues.append("missing_anchor")
        if not choice:
            issues.append("missing_choice")
        if not marker:
            issues.append("missing_marker")
        if not prologue:
            issues.append("missing_prologue")

        marker_pos = int_value(marker, "marker_pos")
        anchor_offset = int_value(anchor, "pair_2a30_offset")
        field16_low = int_value(field, "field16_low_dec")
        field16_high = int_value(field, "field16_high_dec")
        field16_unit = int_value(field, "field16_low_div4")
        next_low = int_value(field, "next_word_low_dec")
        next_high = int_value(field, "next_word_high_dec")
        selector = int_value(field, "selector_byte_dec")
        post1 = int_value(anchor, "post1_hex")

        choice_source = choice.get("source", "")
        oracle_extra = 0
        if choice_source == "marker":
            oracle_extra = int_value(choice, "extra")
        elif choice.get("start"):
            oracle_extra = int_value(choice, "start") - marker_pos
        else:
            issues.append("missing_oracle_start")

        if oracle_extra % 4:
            issues.append("oracle_extra_not_mod4")
        oracle_start = marker_pos + oracle_extra
        oracle_unit = oracle_extra // 4 if oracle_extra else 0

        if marker and marker.get("marker") != "2a30":
            issues.append("marker_not_2a30")
        if marker and int_value(marker, "b3") != post1:
            issues.append("marker_b3_post1_mismatch")
        if choice_source and choice_source != "marker":
            issues.append(f"choice_source:{choice_source}")

        field16_unit_match = oracle_extra == field16_unit
        field16_low_match = oracle_extra == field16_low
        post1_match = oracle_extra == post1
        next_low_x4_match = oracle_extra == next_low * 4
        next_low_delta = oracle_unit - next_low if oracle_extra else 0

        rows.append(
            {
                "segment_id": segment_id,
                "archive_tag": field.get("archive_tag", ""),
                "pcx_name": field.get("pcx_name", ""),
                "choice_source": choice_source,
                "choice_mode": choice.get("mode", ""),
                "choice_width": choice.get("width", ""),
                "choice_height": choice.get("height", ""),
                "choice_score": choice.get("score", ""),
                "choice_filled": choice.get("filled", ""),
                "marker_pos": str(marker_pos) if marker else "",
                "anchor_offset": str(anchor_offset),
                "oracle_extra": str(oracle_extra) if choice else "",
                "oracle_start": str(oracle_start) if choice and marker else "",
                "oracle_extra_unit": str(oracle_unit) if choice else "",
                "post1_dec": str(post1),
                "field16_hex": field.get("field16_hex", ""),
                "field16_low_dec": str(field16_low),
                "field16_high_dec": str(field16_high),
                "field16_low_div4": str(field16_unit),
                "next_word_low_dec": str(next_low),
                "next_word_high_dec": str(next_high),
                "field16_unit_direct_match": bool_text(field16_unit_match),
                "field16_low_direct_match": bool_text(field16_low_match),
                "post1_direct_match": bool_text(post1_match),
                "next_word_low_x4_match": bool_text(next_low_x4_match),
                "next_word_low_delta": str(next_low_delta) if choice else "",
                "selector_byte_dec": str(selector),
                "selector_to_oracle_delta": str(oracle_extra - selector) if choice else "",
                "prologue_family": prologue.get("family", ""),
                "prologue_start": prologue.get("start", ""),
                "prologue_start_minus_marker": prologue.get("start_minus_marker", ""),
                "byte_at_start": prologue.get("byte_at_start", ""),
                "byte_before_start": prologue.get("byte_before_start", ""),
                "before_start_hex": prologue.get("before_start", ""),
                "after_start_hex": prologue.get("after_start", ""),
                "issues": ";".join(dict.fromkeys(issues)),
            }
        )
    return rows


def counter_values(rows: list[dict[str, str]], field: str) -> str:
    counts = Counter(row.get(field, "") for row in rows if row.get(field, "") != "")
    return "|".join(f"{value}:{count}" for value, count in counts.most_common())


def rule_row(
    rule_id: str,
    scope: str,
    rows: list[dict[str, str]],
    matched_rows: int,
    values: list[str],
    verdict: str,
    next_probe: str,
) -> dict[str, str]:
    counts = Counter(value for value in values if value != "")
    return {
        "rule_id": rule_id,
        "scope": scope,
        "rows": str(len(rows)),
        "matched_rows": str(matched_rows),
        "distinct_values": str(len(counts)),
        "values": "|".join(f"{value}:{count}" for value, count in counts.most_common()),
        "verdict": verdict,
        "next_probe": next_probe,
    }


def build_rule_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    oracle_rows = [row for row in rows if row.get("oracle_extra")]
    delta_values = [row.get("next_word_low_delta", "") for row in oracle_rows]
    delta_distinct = len({value for value in delta_values if value != ""})
    return [
        rule_row(
            "guarded_choice_bridge",
            "choice",
            rows,
            sum(1 for row in rows if row.get("choice_source") == "marker" and row.get("choice_filled") == "1.0000"),
            [row.get("choice_mode", "") for row in rows],
            "all_rows_joined" if rows and len(oracle_rows) == len(rows) else "missing_bridge_rows",
            "use guarded TE choices as oracle starts only, not as a promotion rule",
        ),
        rule_row(
            "field16_low_unit_direct_start",
            "oracle_extra",
            oracle_rows,
            sum(1 for row in oracle_rows if row.get("field16_unit_direct_match") == "yes"),
            [row.get("field16_low_div4", "") for row in oracle_rows],
            "rejected",
            "field16 low-byte /4 is not a byte start transform",
        ),
        rule_row(
            "field16_low_direct_start",
            "oracle_extra",
            oracle_rows,
            sum(1 for row in oracle_rows if row.get("field16_low_direct_match") == "yes"),
            [row.get("field16_low_dec", "") for row in oracle_rows],
            "rejected",
            "field16 low byte is not a direct byte start transform",
        ),
        rule_row(
            "post1_direct_extra",
            "post1",
            oracle_rows,
            sum(1 for row in oracle_rows if row.get("post1_direct_match") == "yes"),
            [row.get("post1_dec", "") for row in oracle_rows],
            "partial_only",
            "split rows before treating post1 as a start length",
        ),
        rule_row(
            "next_word_low_times4",
            "next_word_low",
            oracle_rows,
            sum(1 for row in oracle_rows if row.get("next_word_low_x4_match") == "yes"),
            [row.get("next_word_low_dec", "") for row in oracle_rows],
            "partial_only",
            "derive selector for next-word low-byte deltas",
        ),
        rule_row(
            "next_word_low_delta_selector",
            "next_word_low_delta",
            oracle_rows,
            len(oracle_rows) if oracle_rows else 0,
            delta_values,
            "selector_needed" if delta_distinct > 1 else "single_delta",
            "profile broader 2a30 corpus for the delta selector before promotion",
        ),
    ]


def build_summary(rows: list[dict[str, str]], rule_rows: list[dict[str, str]]) -> dict[str, str]:
    oracle_rows = [row for row in rows if row.get("oracle_extra")]
    issue_rows = sum(1 for row in rows if row.get("issues"))
    direct_scores = {
        "field16_low_unit_direct_start": sum(
            1 for row in oracle_rows if row.get("field16_unit_direct_match") == "yes"
        ),
        "field16_low_direct_start": sum(
            1 for row in oracle_rows if row.get("field16_low_direct_match") == "yes"
        ),
        "post1_direct_extra": sum(1 for row in oracle_rows if row.get("post1_direct_match") == "yes"),
        "next_word_low_times4": sum(
            1 for row in oracle_rows if row.get("next_word_low_x4_match") == "yes"
        ),
    }
    best_rows = max(direct_scores.values(), default=0)
    best_rule = "|".join(rule for rule, matched in direct_scores.items() if matched == best_rows)
    delta_values = {row.get("next_word_low_delta", "") for row in oracle_rows if row.get("next_word_low_delta", "")}
    selector_needed = max(0, len(oracle_rows) - best_rows)
    if issue_rows:
        next_action = "fix shifted 0x2a30 field16 transform probe issues"
    elif oracle_rows and selector_needed:
        next_action = (
            "split shifted 0x2a30 field16 transform with guarded TE start selector; "
            f"best direct rule covers {best_rows}/{len(oracle_rows)} rows"
        )
    elif oracle_rows:
        next_action = f"promote shifted 0x2a30 field16 transform candidate {best_rule}"
    else:
        next_action = "no shifted 0x2a30 field16 transform rows"
    return {
        "scope": "total",
        "standard_rows": str(len(rows)),
        "oracle_rows": str(len(oracle_rows)),
        "marker_bridge_rows": str(sum(1 for row in rows if row.get("marker_pos"))),
        "prologue_rows": str(sum(1 for row in rows if row.get("prologue_family"))),
        "distinct_oracle_extra": str(len({row.get("oracle_extra", "") for row in oracle_rows})),
        "oracle_extra_values": counter_values(oracle_rows, "oracle_extra"),
        "field16_unit_direct_rows": str(direct_scores["field16_low_unit_direct_start"]),
        "field16_low_direct_rows": str(direct_scores["field16_low_direct_start"]),
        "post1_direct_rows": str(direct_scores["post1_direct_extra"]),
        "next_word_low_x4_rows": str(direct_scores["next_word_low_times4"]),
        "next_word_low_delta_values": str(len(delta_values)),
        "next_word_low_delta_counts": counter_values(oracle_rows, "next_word_low_delta"),
        "best_direct_rule": best_rule,
        "best_direct_rows": str(best_rows),
        "selector_needed_rows": str(selector_needed),
        "rule_rows": str(len(rule_rows)),
        "issue_rows": str(issue_rows),
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
    rows: list[dict[str, str]],
    rules: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "transforms": rows, "rules": rules}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("transforms.csv", output_dir / "transforms.csv"),
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
<p class="muted">Joins rejected large shifted 0x2a30 rows to guarded TE start evidence and tests simple field16 transforms.</p>
<p>{links}</p>
<h2>Summary</h2>
{render_table([summary], SUMMARY_FIELDNAMES)}
<h2>Rules</h2>
{render_table(rules, RULE_FIELDNAMES)}
<h2>Transforms</h2>
{render_table(rows, TRANSFORM_FIELDNAMES)}
</main>
<script>const TEX_LARGE_SHIFTED_2A30_FIELD16_TRANSFORM_PROBE = {data_json};</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    field16_path: Path,
    anchors_path: Path,
    choices_path: Path,
    markers_path: Path,
    prologues_path: Path,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    transform_rows = build_transform_rows(
        read_csv(field16_path),
        {row.get("segment_id", ""): row for row in read_csv(anchors_path)},
        {choice_key(row): row for row in read_csv(choices_path, delimiter="\t")},
        lookup_by_key(read_csv(markers_path, delimiter="\t"), ("level", "name")),
        lookup_by_key(read_csv(prologues_path, delimiter="\t"), ("level", "name")),
    )
    rule_rows = build_rule_rows(transform_rows)
    summary = build_summary(transform_rows, rule_rows)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "transforms.csv", TRANSFORM_FIELDNAMES, transform_rows)
    write_csv(output_dir / "rules.csv", RULE_FIELDNAMES, rule_rows)
    (output_dir / "index.html").write_text(
        build_html(summary, transform_rows, rule_rows, output_dir, title),
        encoding="utf-8",
    )
    return summary, transform_rows, rule_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Derive shifted 0x2a30 field16 start-transform evidence.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--field16", type=Path, default=DEFAULT_FIELD16)
    parser.add_argument("--anchors", type=Path, default=DEFAULT_ANCHORS)
    parser.add_argument("--choices", type=Path, default=DEFAULT_CHOICES)
    parser.add_argument("--markers", type=Path, default=DEFAULT_MARKERS)
    parser.add_argument("--prologues", type=Path, default=DEFAULT_PROLOGUES)
    parser.add_argument("--title", default="Lands of Lore II .tex Large Shifted 2a30 Field16 Transform Probe")
    args = parser.parse_args()

    summary, rows, _rules = write_report(
        args.output,
        args.field16,
        args.anchors,
        args.choices,
        args.markers,
        args.prologues,
        args.title,
    )
    print(f"Standard rows: {summary['standard_rows']}")
    print(f"Oracle rows: {summary['oracle_rows']}")
    print(f"Best direct rule: {summary['best_direct_rule']} ({summary['best_direct_rows']})")
    print(f"Selector needed rows: {summary['selector_needed_rows']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
