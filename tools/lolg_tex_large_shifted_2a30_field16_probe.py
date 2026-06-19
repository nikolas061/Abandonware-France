#!/usr/bin/env python3
"""Probe field16 semantics for standard shifted 0x2a30 .tex anchors."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
from collections import Counter
from pathlib import Path


DEFAULT_OUTPUT = Path("output/tex_large_shifted_2a30_field16_probe")
DEFAULT_ANCHORS = Path("output/tex_large_shifted_2a30_standard_probe/anchors.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "standard_rows",
    "branch_rows",
    "field16_values",
    "field16_low_values",
    "field16_high_values",
    "low_mod4_zero_rows",
    "low_mod8_zero_rows",
    "selector_mod8_zero_rows",
    "selector_low_delta_values",
    "next_word_values",
    "next_word_low_values",
    "next_word_high_values",
    "high_nonzero_rows",
    "rule_rows",
    "issue_rows",
    "next_action",
]

FIELD_FIELDNAMES = [
    "segment_id",
    "archive_tag",
    "pcx_name",
    "selector_byte_hex",
    "selector_byte_dec",
    "field16_hex",
    "field16_dec",
    "field16_low_hex",
    "field16_low_dec",
    "field16_high_hex",
    "field16_high_dec",
    "field16_low_div4",
    "field16_low_mod4",
    "field16_low_mod8",
    "selector_to_low_delta",
    "selector_to_field_delta",
    "next_word16_hex",
    "next_word_low_hex",
    "next_word_low_dec",
    "next_word_high_hex",
    "next_word_high_dec",
    "body_size",
    "entropy",
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


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def int_value(row: dict[str, str], field: str) -> int:
    raw = row.get(field, "")
    try:
        return int(raw, 0) if raw else 0
    except ValueError:
        return 0


def hex_byte(value: int) -> str:
    return f"0x{value:02x}"


def build_field_rows(anchor_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for anchor in anchor_rows:
        if anchor.get("is_standard") != "yes":
            continue
        issues: list[str] = []
        selector = int_value(anchor, "selector_byte_dec")
        field16 = int_value(anchor, "post_field16_le_dec")
        next_word = int_value(anchor, "next_word16_le_hex")
        low = field16 & 0xFF
        high = (field16 >> 8) & 0xFF
        next_low = next_word & 0xFF
        next_high = (next_word >> 8) & 0xFF
        if low % 4:
            issues.append("field16_low_not_mod4")
        if selector % 8:
            issues.append("selector_not_mod8")
        rows.append(
            {
                "segment_id": anchor.get("segment_id", ""),
                "archive_tag": anchor.get("archive_tag", ""),
                "pcx_name": anchor.get("pcx_name", ""),
                "selector_byte_hex": anchor.get("selector_byte_hex", ""),
                "selector_byte_dec": str(selector),
                "field16_hex": anchor.get("post_field16_le_hex", ""),
                "field16_dec": str(field16),
                "field16_low_hex": hex_byte(low),
                "field16_low_dec": str(low),
                "field16_high_hex": hex_byte(high),
                "field16_high_dec": str(high),
                "field16_low_div4": str(low // 4),
                "field16_low_mod4": str(low % 4),
                "field16_low_mod8": str(low % 8),
                "selector_to_low_delta": str(low - selector),
                "selector_to_field_delta": str(field16 - selector),
                "next_word16_hex": anchor.get("next_word16_le_hex", ""),
                "next_word_low_hex": hex_byte(next_low),
                "next_word_low_dec": str(next_low),
                "next_word_high_hex": hex_byte(next_high),
                "next_word_high_dec": str(next_high),
                "body_size": anchor.get("body_size", ""),
                "entropy": anchor.get("entropy", ""),
                "issues": ";".join(dict.fromkeys(issues)),
            }
        )
    return rows


def rule_row(
    rule_id: str,
    scope: str,
    rows: list[dict[str, str]],
    values: list[str],
    matched_rows: int,
    next_probe: str,
) -> dict[str, str]:
    counts = Counter(values)
    if matched_rows == len(rows):
        verdict = "all_standard_rows"
    elif matched_rows:
        verdict = "partial_standard_rows"
    else:
        verdict = "no_standard_rows"
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
    return [
        rule_row(
            "field16_low_mod4_zero",
            "field16_low_mod4",
            rows,
            [row.get("field16_low_mod4", "") for row in rows],
            sum(1 for row in rows if row.get("field16_low_mod4") == "0"),
            "test field16 low byte divided by 4 as the first replay unit",
        ),
        rule_row(
            "field16_low_mod8_zero",
            "field16_low_mod8",
            rows,
            [row.get("field16_low_mod8", "") for row in rows],
            sum(1 for row in rows if row.get("field16_low_mod8") == "0"),
            "avoid assuming low-byte mod8 alignment",
        ),
        rule_row(
            "selector_mod8_zero",
            "selector_byte_dec",
            rows,
            [str(int_value(row, "selector_byte_dec") % 8) for row in rows],
            sum(1 for row in rows if int_value(row, "selector_byte_dec") % 8 == 0),
            "keep selector as aligned context, not branch selector",
        ),
        rule_row(
            "selector_to_low_delta",
            "selector_to_low_delta",
            rows,
            [row.get("selector_to_low_delta", "") for row in rows],
            0,
            "reject a single selector-to-low-byte delta",
        ),
        rule_row(
            "field16_high_byte",
            "field16_high_hex",
            rows,
            [row.get("field16_high_hex", "") for row in rows],
            sum(1 for row in rows if int_value(row, "field16_high_dec") > 0),
            "treat high byte as bank or state context before promotion",
        ),
        rule_row(
            "next_word_high_byte",
            "next_word_high_hex",
            rows,
            [row.get("next_word_high_hex", "") for row in rows],
            len(rows),
            "join next-word high byte to payload/control family evidence",
        ),
    ]


def build_summary(rows: list[dict[str, str]], branch_rows: int, rule_rows: list[dict[str, str]]) -> dict[str, str]:
    issue_rows = sum(1 for row in rows if row.get("issues"))
    low_mod4_zero_rows = sum(1 for row in rows if row.get("field16_low_mod4") == "0")
    if issue_rows:
        next_action = "fix shifted 0x2a30 field16 probe issues"
    elif rows and low_mod4_zero_rows == len(rows):
        next_action = (
            f"test shifted 0x2a30 field16 low-byte /4 replay units on {len(rows)} standard rows"
        )
    elif rows:
        next_action = "split shifted 0x2a30 field16 rows before replay"
    else:
        next_action = "no shifted 0x2a30 field16 rows"
    return {
        "scope": "total",
        "standard_rows": str(len(rows)),
        "branch_rows": str(branch_rows),
        "field16_values": str(len({row.get("field16_hex", "") for row in rows if row.get("field16_hex")})),
        "field16_low_values": str(
            len({row.get("field16_low_hex", "") for row in rows if row.get("field16_low_hex")})
        ),
        "field16_high_values": str(
            len({row.get("field16_high_hex", "") for row in rows if row.get("field16_high_hex")})
        ),
        "low_mod4_zero_rows": str(low_mod4_zero_rows),
        "low_mod8_zero_rows": str(sum(1 for row in rows if row.get("field16_low_mod8") == "0")),
        "selector_mod8_zero_rows": str(sum(1 for row in rows if int_value(row, "selector_byte_dec") % 8 == 0)),
        "selector_low_delta_values": str(
            len({row.get("selector_to_low_delta", "") for row in rows if row.get("selector_to_low_delta")})
        ),
        "next_word_values": str(len({row.get("next_word16_hex", "") for row in rows if row.get("next_word16_hex")})),
        "next_word_low_values": str(
            len({row.get("next_word_low_hex", "") for row in rows if row.get("next_word_low_hex")})
        ),
        "next_word_high_values": str(
            len({row.get("next_word_high_hex", "") for row in rows if row.get("next_word_high_hex")})
        ),
        "high_nonzero_rows": str(sum(1 for row in rows if int_value(row, "field16_high_dec") > 0)),
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
    field_rows: list[dict[str, str]],
    rule_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "field_rows": field_rows, "rules": rule_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("field16.csv", output_dir / "field16.csv"),
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
<p class="muted">Field16 low/high bytes are split before any replay promotion.</p>
<p>{links}</p>
<h2>Summary</h2>
{render_table([summary], SUMMARY_FIELDNAMES)}
<h2>Rules</h2>
{render_table(rule_rows, RULE_FIELDNAMES)}
<h2>Field16 Rows</h2>
{render_table(field_rows, FIELD_FIELDNAMES)}
</main>
<script>const TEX_LARGE_SHIFTED_2A30_FIELD16_PROBE = {data_json};</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    anchors_path: Path,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    anchors = read_csv(anchors_path)
    branch_rows = sum(1 for row in anchors if row.get("is_standard") != "yes")
    field_rows = build_field_rows(anchors)
    rule_rows = build_rule_rows(field_rows)
    summary = build_summary(field_rows, branch_rows, rule_rows)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "field16.csv", FIELD_FIELDNAMES, field_rows)
    write_csv(output_dir / "rules.csv", RULE_FIELDNAMES, rule_rows)
    (output_dir / "index.html").write_text(build_html(summary, field_rows, rule_rows, output_dir, title))
    return summary, field_rows, rule_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe field16 semantics for shifted 0x2a30 standard anchors.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--anchors", type=Path, default=DEFAULT_ANCHORS)
    parser.add_argument("--title", default="Lands of Lore II .tex Large Shifted 2a30 Field16 Probe")
    args = parser.parse_args()

    summary, field_rows, rule_rows = write_report(args.output, args.anchors, args.title)
    print(f"Standard rows: {summary['standard_rows']}")
    print(f"Branch rows: {summary['branch_rows']}")
    print(f"Low mod4 zero rows: {summary['low_mod4_zero_rows']}")
    print(f"Rule rows: {summary['rule_rows']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
