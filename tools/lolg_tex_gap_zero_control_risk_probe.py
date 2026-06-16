#!/usr/bin/env python3
"""Measure false-positive risk for .tex zero-run control signals."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import defaultdict
from pathlib import Path

from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_zero_control_risk_probe")
DEFAULT_OPERATIONS = Path("output/tex_gap_segmentation_control_correlation_probe/operations.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "operation_rows",
    "zero_ops",
    "zero_bytes",
    "nonzero_ops",
    "nonzero_bytes",
    "current_selector",
    "current_true_zero_bytes",
    "current_false_nonzero_ops",
    "current_false_nonzero_bytes",
    "false_free_candidate",
    "false_free_true_zero_bytes",
    "low_false_candidate",
    "low_false_true_zero_bytes",
    "low_false_false_nonzero_bytes",
    "classifier_rows",
    "false_positive_rows",
    "issue_rows",
]

CLASSIFIER_FIELDNAMES = [
    "classifier",
    "description",
    "uses_oracle_filter",
    "selected_ops",
    "true_zero_ops",
    "false_nonzero_ops",
    "false_negative_zero_ops",
    "precision",
    "recall",
    "true_zero_bytes",
    "false_nonzero_bytes",
]

FALSE_POSITIVE_FIELDNAMES = [
    "classifier",
    "rank",
    "pcx_name",
    "frontier_id",
    "op_index",
    "op_kind",
    "expected_start",
    "length",
    "expected_mod64",
    "length_u8_hit_offsets",
    "length_u16le_hit_offsets",
    "source_delta_u8_hit_offsets",
    "expected_hex",
]

BY_KIND_FIELDNAMES = [
    "classifier",
    "op_kind",
    "selected_ops",
    "selected_bytes",
]

BY_FIXTURE_FIELDNAMES = [
    "classifier",
    "rank",
    "pcx_name",
    "frontier_id",
    "selected_ops",
    "true_zero_ops",
    "false_nonzero_ops",
    "true_zero_bytes",
    "false_nonzero_bytes",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def fixture_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", "")


def length(row: dict[str, str]) -> int:
    return int_value(row, "length")


def expected_mod64(row: dict[str, str]) -> int:
    return int_value(row, "expected_mod64") if row.get("expected_mod64") else -1


def has_u8_length(row: dict[str, str]) -> bool:
    return bool(row.get("length_u8_hit_offsets"))


def has_u16_length(row: dict[str, str]) -> bool:
    return bool(row.get("length_u16le_hit_offsets"))


def is_zero(row: dict[str, str]) -> bool:
    return row.get("op_kind") == "zero"


def classifier_specs():
    return [
        (
            "len64",
            "operation length is exactly 64",
            False,
            lambda row: length(row) == 64,
        ),
        (
            "length_u8",
            "operation length appears as a nearby u8 value",
            False,
            has_u8_length,
        ),
        (
            "length_u16",
            "operation length appears as a nearby u16le value",
            False,
            has_u16_length,
        ),
        (
            "len64_or_u8",
            "current broad selector: length 64 or nearby u8 length hit",
            False,
            lambda row: length(row) == 64 or has_u8_length(row),
        ),
        (
            "len64_or_u8_or_u16",
            "length 64, nearby u8 length, or nearby u16le length",
            False,
            lambda row: length(row) == 64 or has_u8_length(row) or has_u16_length(row),
        ),
        (
            "len64_and_u8",
            "length 64 and nearby u8 length hit",
            False,
            lambda row: length(row) == 64 and has_u8_length(row),
        ),
        (
            "u8_len32_64",
            "nearby u8 length hit and operation length between 32 and 64",
            False,
            lambda row: has_u8_length(row) and 32 <= length(row) <= 64,
        ),
        (
            "len_ge64",
            "operation length at least 64",
            False,
            lambda row: length(row) >= 64,
        ),
        (
            "len_ge64_unaligned",
            "operation length at least 64 and neither start nor end is 64-byte aligned",
            False,
            lambda row: length(row) >= 64
            and expected_mod64(row) != 0
            and (expected_mod64(row) + length(row)) % 64 != 0,
        ),
        (
            "oracle_zero",
            "segmented operation is a zero-run",
            True,
            is_zero,
        ),
    ]


def evaluate_classifier(
    name: str,
    description: str,
    uses_oracle: bool,
    predicate,
    operation_rows: list[dict[str, str]],
) -> dict[str, str]:
    selected = [row for row in operation_rows if predicate(row)]
    zero_rows = [row for row in operation_rows if is_zero(row)]
    true_zero = [row for row in selected if is_zero(row)]
    false_nonzero = [row for row in selected if not is_zero(row)]
    true_ids = {id(row) for row in true_zero}
    false_negative = [row for row in zero_rows if id(row) not in true_ids]
    precision = len(true_zero) / len(selected) if selected else 0.0
    recall = len(true_zero) / len(zero_rows) if zero_rows else 0.0
    return {
        "classifier": name,
        "description": description,
        "uses_oracle_filter": "1" if uses_oracle else "0",
        "selected_ops": str(len(selected)),
        "true_zero_ops": str(len(true_zero)),
        "false_nonzero_ops": str(len(false_nonzero)),
        "false_negative_zero_ops": str(len(false_negative)),
        "precision": f"{precision:.6f}",
        "recall": f"{recall:.6f}",
        "true_zero_bytes": str(sum(length(row) for row in true_zero)),
        "false_nonzero_bytes": str(sum(length(row) for row in false_nonzero)),
    }


def select_false_free(classifiers: list[dict[str, str]]) -> dict[str, str]:
    candidates = [
        row
        for row in classifiers
        if row.get("uses_oracle_filter") != "1" and int_value(row, "false_nonzero_bytes") == 0
    ]
    return max(
        candidates,
        key=lambda row: (
            int_value(row, "true_zero_bytes"),
            int_value(row, "true_zero_ops"),
            row.get("classifier", ""),
        ),
    )


def select_low_false(classifiers: list[dict[str, str]]) -> dict[str, str]:
    candidates = [
        row
        for row in classifiers
        if row.get("uses_oracle_filter") != "1" and int_value(row, "false_nonzero_bytes") <= 64
    ]
    return max(
        candidates,
        key=lambda row: (
            int_value(row, "true_zero_bytes"),
            -int_value(row, "false_nonzero_bytes"),
            row.get("classifier", ""),
        ),
    )


def false_positive_rows(operation_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for name, _description, uses_oracle, predicate in classifier_specs():
        if uses_oracle:
            continue
        for row in operation_rows:
            if not is_zero(row) and predicate(row):
                rows.append(
                    {
                        "classifier": name,
                        "rank": row.get("rank", ""),
                        "pcx_name": row.get("pcx_name", ""),
                        "frontier_id": row.get("frontier_id", ""),
                        "op_index": row.get("op_index", ""),
                        "op_kind": row.get("op_kind", ""),
                        "expected_start": row.get("expected_start", ""),
                        "length": row.get("length", ""),
                        "expected_mod64": row.get("expected_mod64", ""),
                        "length_u8_hit_offsets": row.get("length_u8_hit_offsets", ""),
                        "length_u16le_hit_offsets": row.get("length_u16le_hit_offsets", ""),
                        "source_delta_u8_hit_offsets": row.get("source_delta_u8_hit_offsets", ""),
                        "expected_hex": row.get("expected_hex", ""),
                    }
                )
    return rows


def by_kind_rows(operation_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for name, _description, _uses_oracle, predicate in classifier_specs():
        groups: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in operation_rows:
            if predicate(row):
                groups[row.get("op_kind", "")].append(row)
        for kind, group in sorted(groups.items()):
            rows.append(
                {
                    "classifier": name,
                    "op_kind": kind,
                    "selected_ops": str(len(group)),
                    "selected_bytes": str(sum(length(row) for row in group)),
                }
            )
    return rows


def by_fixture_rows(operation_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    focus = {"len64_or_u8", "len64_and_u8", "u8_len32_64", "oracle_zero"}
    rows: list[dict[str, str]] = []
    for name, _description, _uses_oracle, predicate in classifier_specs():
        if name not in focus:
            continue
        groups: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
        for row in operation_rows:
            if predicate(row):
                groups[fixture_key(row)].append(row)
        for key, group in sorted(groups.items(), key=lambda item: int(item[0][0]) if item[0][0].isdigit() else 999999):
            true_zero = [row for row in group if is_zero(row)]
            false_nonzero = [row for row in group if not is_zero(row)]
            rows.append(
                {
                    "classifier": name,
                    "rank": key[0],
                    "pcx_name": key[1],
                    "frontier_id": key[2],
                    "selected_ops": str(len(group)),
                    "true_zero_ops": str(len(true_zero)),
                    "false_nonzero_ops": str(len(false_nonzero)),
                    "true_zero_bytes": str(sum(length(row) for row in true_zero)),
                    "false_nonzero_bytes": str(sum(length(row) for row in false_nonzero)),
                }
            )
    return rows


def summary_row(
    operation_rows: list[dict[str, str]],
    classifiers: list[dict[str, str]],
    false_positives: list[dict[str, str]],
) -> dict[str, str]:
    zero_rows = [row for row in operation_rows if is_zero(row)]
    nonzero_rows = [row for row in operation_rows if not is_zero(row)]
    current = next(row for row in classifiers if row.get("classifier") == "len64_or_u8")
    false_free = select_false_free(classifiers)
    low_false = select_low_false(classifiers)
    return {
        "scope": "total",
        "operation_rows": str(len(operation_rows)),
        "zero_ops": str(len(zero_rows)),
        "zero_bytes": str(sum(length(row) for row in zero_rows)),
        "nonzero_ops": str(len(nonzero_rows)),
        "nonzero_bytes": str(sum(length(row) for row in nonzero_rows)),
        "current_selector": current.get("classifier", ""),
        "current_true_zero_bytes": current.get("true_zero_bytes", "0"),
        "current_false_nonzero_ops": current.get("false_nonzero_ops", "0"),
        "current_false_nonzero_bytes": current.get("false_nonzero_bytes", "0"),
        "false_free_candidate": false_free.get("classifier", ""),
        "false_free_true_zero_bytes": false_free.get("true_zero_bytes", "0"),
        "low_false_candidate": low_false.get("classifier", ""),
        "low_false_true_zero_bytes": low_false.get("true_zero_bytes", "0"),
        "low_false_false_nonzero_bytes": low_false.get("false_nonzero_bytes", "0"),
        "classifier_rows": str(len(classifiers)),
        "false_positive_rows": str(len(false_positives)),
        "issue_rows": str(sum(1 for row in operation_rows if row.get("issues"))),
    }


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 300) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    classifiers: list[dict[str, str]],
    false_positives: list[dict[str, str]],
    kinds: list[dict[str, str]],
    fixtures: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "classifiers": classifiers,
        "falsePositives": false_positives,
        "kinds": kinds,
        "fixtures": fixtures,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("classifiers.csv", output_dir / "classifiers.csv"),
            ("false_positives.csv", output_dir / "false_positives.csv"),
            ("by_kind.csv", output_dir / "by_kind.csv"),
            ("by_fixture.csv", output_dir / "by_fixture.csv"),
        )
    )
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root {{
  color-scheme: dark;
  --bg: #101417;
  --panel: #171f22;
  --line: #31424a;
  --text: #edf5f4;
  --muted: #9dafb5;
  --accent: #77d3b1;
  --ok: #80df94;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  min-height: 100vh;
  background: var(--bg);
  color: var(--text);
  font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}}
.wrap {{ width: min(1680px, calc(100vw - 28px)); margin: 0 auto; }}
header {{ border-bottom: 1px solid var(--line); background: #12191b; padding: 18px 0 14px; }}
h1 {{ margin: 0; font-size: 21px; font-weight: 720; letter-spacing: 0; }}
h2 {{ margin: 0 0 10px; font-size: 16px; }}
.sub {{ color: var(--muted); margin-top: 4px; }}
main {{ padding: 16px 0 28px; display: grid; gap: 16px; }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 10px; }}
.stat, .panel {{ border: 1px solid var(--line); border-radius: 8px; background: var(--panel); padding: 10px; }}
.label, .muted {{ color: var(--muted); }}
.value {{ font-size: 22px; font-weight: 760; line-height: 1.05; margin-top: 4px; }}
.ok {{ color: var(--ok); }}
.panel {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; min-width: 1180px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Applies zero-run selectors to all operations to expose nonzero false-positive risk.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Zero bytes</div><div class="value ok">{html.escape(summary['zero_bytes'])}</div></div>
    <div class="stat"><div class="label">Current false bytes</div><div class="value">{html.escape(summary['current_false_nonzero_bytes'])}</div></div>
    <div class="stat"><div class="label">False-free rule</div><div class="value">{html.escape(summary['false_free_candidate'])}</div></div>
    <div class="stat"><div class="label">Low-false bytes</div><div class="value">{html.escape(summary['low_false_true_zero_bytes'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div></section>
  <section class="panel"><h2>Classifiers</h2>{render_table(classifiers, CLASSIFIER_FIELDNAMES)}</section>
  <section class="panel"><h2>False positives</h2>{render_table(false_positives, FALSE_POSITIVE_FIELDNAMES)}</section>
  <section class="panel"><h2>By kind</h2>{render_table(kinds, BY_KIND_FIELDNAMES)}</section>
  <section class="panel"><h2>By fixture</h2>{render_table(fixtures, BY_FIXTURE_FIELDNAMES)}</section>
</main>
<script>
const TEX_GAP_ZERO_CONTROL_RISK_PROBE = {data_json};
</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    operations_path: Path,
    *,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    operation_rows = read_csv(operations_path)
    classifiers = [
        evaluate_classifier(name, description, uses_oracle, predicate, operation_rows)
        for name, description, uses_oracle, predicate in classifier_specs()
    ]
    false_positives = false_positive_rows(operation_rows)
    kinds = by_kind_rows(operation_rows)
    fixtures = by_fixture_rows(operation_rows)
    summary = summary_row(operation_rows, classifiers, false_positives)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "classifiers.csv", CLASSIFIER_FIELDNAMES, classifiers)
    write_csv(output_dir / "false_positives.csv", FALSE_POSITIVE_FIELDNAMES, false_positives)
    write_csv(output_dir / "by_kind.csv", BY_KIND_FIELDNAMES, kinds)
    write_csv(output_dir / "by_fixture.csv", BY_FIXTURE_FIELDNAMES, fixtures)
    (output_dir / "index.html").write_text(
        build_html(summary, classifiers, false_positives, kinds, fixtures, output_dir, title)
    )
    return summary, classifiers


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe .tex zero-run control false-positive risk.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--operations", type=Path, default=DEFAULT_OPERATIONS)
    parser.add_argument("--title", default="Lands of Lore II .tex Gap Zero-Control Risk Probe")
    args = parser.parse_args()

    summary, _classifiers = write_report(args.output, args.operations, title=args.title)
    print(f"Operation rows: {summary['operation_rows']}")
    print(f"Zero bytes: {summary['zero_bytes']}")
    print(
        "Current selector false bytes: "
        f"{summary['current_selector']}={summary['current_false_nonzero_bytes']}"
    )
    print(
        "False-free candidate: "
        f"{summary['false_free_candidate']}={summary['false_free_true_zero_bytes']}"
    )
    print(
        "Low-false candidate: "
        f"{summary['low_false_candidate']}={summary['low_false_true_zero_bytes']}/"
        f"{summary['low_false_false_nonzero_bytes']}"
    )
    print(f"Issue rows: {summary['issue_rows']}")


if __name__ == "__main__":
    main()
