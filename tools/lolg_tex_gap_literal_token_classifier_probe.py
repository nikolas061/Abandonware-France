#!/usr/bin/env python3
"""Classify likely .tex literal length tokens from literal-token probe rows."""

from __future__ import annotations

import argparse
import csv
import html
import json
from pathlib import Path

from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_literal_token_classifier_probe")
DEFAULT_LITERALS = Path("output/tex_gap_literal_token_probe/literals.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "literal_ops",
    "actual_token_plus3_ops",
    "actual_token_plus3_bytes",
    "small_token_selected_ops",
    "small_token_false_positive_ops",
    "high_recall_classifier",
    "high_recall_precision",
    "high_recall_recall",
    "high_recall_false_positive_ops",
    "high_precision_classifier",
    "high_precision_precision",
    "high_precision_recall",
    "high_precision_false_positive_ops",
    "classifier_rows",
    "issue_rows",
]

CLASSIFIER_FIELDNAMES = [
    "classifier",
    "description",
    "selected_ops",
    "true_positive_ops",
    "false_positive_ops",
    "false_negative_ops",
    "precision",
    "recall",
    "true_positive_bytes",
    "false_positive_bytes",
]

ERROR_FIELDNAMES = [
    "classifier",
    "error_type",
    "rank",
    "pcx_name",
    "frontier_id",
    "op_index",
    "expected_start",
    "length",
    "source_offset",
    "token_hex",
    "token_plus3_length",
    "source_delta_from_prev_literal_end",
    "source_direction",
    "expected_hex",
]

FIXTURE_FIELDNAMES = [
    "rank",
    "pcx_name",
    "frontier_id",
    "literal_ops",
    "actual_token_plus3_ops",
    "small_token_selected_ops",
    "small_token_false_positive_ops",
    "small_not_backward_selected_ops",
    "small_not_backward_false_positive_ops",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def token_value(row: dict[str, str]) -> int:
    return int_value(row, "token_value") if row.get("token_value") else -1


def source_delta(row: dict[str, str]) -> int:
    return int_value(row, "source_delta_from_prev_literal_end") if row.get("source_delta_from_prev_literal_end") else 0


def is_actual(row: dict[str, str]) -> bool:
    return row.get("token_plus3_match") == "1"


def classifier_specs():
    return [
        (
            "small_token",
            "token value <= 13",
            lambda row: 0 <= token_value(row) <= 13,
        ),
        (
            "small_nonzero_token",
            "1 <= token value <= 13",
            lambda row: 1 <= token_value(row) <= 13,
        ),
        (
            "small_not_backward",
            "token value <= 13 and source is first/forward/reuse",
            lambda row: 0 <= token_value(row) <= 13 and row.get("source_direction") != "backward",
        ),
        (
            "small_forward",
            "token value <= 13 and source direction is forward",
            lambda row: 0 <= token_value(row) <= 13 and row.get("source_direction") == "forward",
        ),
        (
            "small_abs_delta_le16",
            "token value <= 13 and absolute source delta <= 16",
            lambda row: 0 <= token_value(row) <= 13 and abs(source_delta(row)) <= 16,
        ),
        (
            "small_not_backward_abs_delta_le128",
            "token value <= 13, not backward, abs delta <= 128",
            lambda row: 0 <= token_value(row) <= 13
            and row.get("source_direction") != "backward"
            and abs(source_delta(row)) <= 128,
        ),
        (
            "small_not_backward_abs_delta_le512",
            "token value <= 13, not backward, abs delta <= 512",
            lambda row: 0 <= token_value(row) <= 13
            and row.get("source_direction") != "backward"
            and abs(source_delta(row)) <= 512,
        ),
        (
            "oracle_token_plus3",
            "token + 3 equals segmented literal length",
            is_actual,
        ),
    ]


def evaluate_classifier(
    name: str,
    description: str,
    literal_rows: list[dict[str, str]],
    predicate,
) -> dict[str, str]:
    selected = [row for row in literal_rows if predicate(row)]
    actual_rows = [row for row in literal_rows if is_actual(row)]
    true_positive = [row for row in selected if is_actual(row)]
    false_positive = [row for row in selected if not is_actual(row)]
    true_positive_keys = {id(row) for row in true_positive}
    false_negative = [row for row in actual_rows if id(row) not in true_positive_keys]
    precision = len(true_positive) / len(selected) if selected else 0.0
    recall = len(true_positive) / len(actual_rows) if actual_rows else 0.0
    return {
        "classifier": name,
        "description": description,
        "selected_ops": str(len(selected)),
        "true_positive_ops": str(len(true_positive)),
        "false_positive_ops": str(len(false_positive)),
        "false_negative_ops": str(len(false_negative)),
        "precision": f"{precision:.6f}",
        "recall": f"{recall:.6f}",
        "true_positive_bytes": str(sum(int_value(row, "length") for row in true_positive)),
        "false_positive_bytes": str(sum(int_value(row, "length") for row in false_positive)),
    }


def error_rows(literal_rows: list[dict[str, str]], classifier_name: str, predicate) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in literal_rows:
        selected = predicate(row)
        actual = is_actual(row)
        if selected and not actual:
            error_type = "false_positive"
        elif actual and not selected:
            error_type = "false_negative"
        else:
            continue
        rows.append(
            {
                "classifier": classifier_name,
                "error_type": error_type,
                "rank": row.get("rank", ""),
                "pcx_name": row.get("pcx_name", ""),
                "frontier_id": row.get("frontier_id", ""),
                "op_index": row.get("op_index", ""),
                "expected_start": row.get("expected_start", ""),
                "length": row.get("length", ""),
                "source_offset": row.get("source_offset", ""),
                "token_hex": row.get("token_hex", ""),
                "token_plus3_length": row.get("token_plus3_length", ""),
                "source_delta_from_prev_literal_end": row.get("source_delta_from_prev_literal_end", ""),
                "source_direction": row.get("source_direction", ""),
                "expected_hex": row.get("expected_hex", ""),
            }
        )
    return rows


def fixture_rows(literal_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    groups: dict[tuple[str, str, str], list[dict[str, str]]] = {}
    for row in literal_rows:
        key = (row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", ""))
        groups.setdefault(key, []).append(row)
    rows: list[dict[str, str]] = []
    for key, group in sorted(groups.items(), key=lambda item: int(item[0][0]) if item[0][0].isdigit() else 999999):
        small = [row for row in group if 0 <= token_value(row) <= 13]
        small_not_backward = [row for row in small if row.get("source_direction") != "backward"]
        rows.append(
            {
                "rank": key[0],
                "pcx_name": key[1],
                "frontier_id": key[2],
                "literal_ops": str(len(group)),
                "actual_token_plus3_ops": str(sum(1 for row in group if is_actual(row))),
                "small_token_selected_ops": str(len(small)),
                "small_token_false_positive_ops": str(sum(1 for row in small if not is_actual(row))),
                "small_not_backward_selected_ops": str(len(small_not_backward)),
                "small_not_backward_false_positive_ops": str(
                    sum(1 for row in small_not_backward if not is_actual(row))
                ),
            }
        )
    return rows


def summary_row(
    literal_rows: list[dict[str, str]],
    classifier_rows: list[dict[str, str]],
    errors: list[dict[str, str]],
) -> dict[str, str]:
    actual_rows = [row for row in literal_rows if is_actual(row)]
    small_row = next(row for row in classifier_rows if row.get("classifier") == "small_token")
    non_oracle = [row for row in classifier_rows if row.get("classifier") != "oracle_token_plus3"]
    high_recall = max(
        [row for row in non_oracle if float(row.get("recall", "0")) >= 0.90],
        key=lambda row: (float(row.get("precision", "0")), float(row.get("recall", "0"))),
    )
    high_precision = max(
        [row for row in non_oracle if float(row.get("precision", "0")) >= 0.95],
        key=lambda row: (float(row.get("recall", "0")), float(row.get("precision", "0"))),
    )
    return {
        "scope": "total",
        "literal_ops": str(len(literal_rows)),
        "actual_token_plus3_ops": str(len(actual_rows)),
        "actual_token_plus3_bytes": str(sum(int_value(row, "length") for row in actual_rows)),
        "small_token_selected_ops": small_row.get("selected_ops", "0"),
        "small_token_false_positive_ops": small_row.get("false_positive_ops", "0"),
        "high_recall_classifier": high_recall.get("classifier", ""),
        "high_recall_precision": high_recall.get("precision", ""),
        "high_recall_recall": high_recall.get("recall", ""),
        "high_recall_false_positive_ops": high_recall.get("false_positive_ops", ""),
        "high_precision_classifier": high_precision.get("classifier", ""),
        "high_precision_precision": high_precision.get("precision", ""),
        "high_precision_recall": high_precision.get("recall", ""),
        "high_precision_false_positive_ops": high_precision.get("false_positive_ops", ""),
        "classifier_rows": str(len(classifier_rows)),
        "issue_rows": str(sum(1 for row in literal_rows if row.get("issues")) + sum(1 for row in errors if row.get("issues"))),
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
    errors: list[dict[str, str]],
    fixtures: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "classifiers": classifiers,
        "errors": errors,
        "fixtures": fixtures,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("classifiers.csv", output_dir / "classifiers.csv"),
            ("classifier_errors.csv", output_dir / "classifier_errors.csv"),
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
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 10px; }}
.stat, .panel {{ border: 1px solid var(--line); border-radius: 8px; background: var(--panel); padding: 10px; }}
.label, .muted {{ color: var(--muted); }}
.value {{ font-size: 23px; font-weight: 760; line-height: 1.05; margin-top: 4px; }}
.ok {{ color: var(--ok); }}
.panel {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; min-width: 980px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Precision/recall for simple decisions that separate length tokens from source bytes.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Actual token+3 ops</div><div class="value ok">{html.escape(summary['actual_token_plus3_ops'])}</div></div>
    <div class="stat"><div class="label">Small-token false positives</div><div class="value">{html.escape(summary['small_token_false_positive_ops'])}</div></div>
    <div class="stat"><div class="label">High recall rule</div><div class="value">{html.escape(summary['high_recall_classifier'])}</div></div>
    <div class="stat"><div class="label">High precision rule</div><div class="value">{html.escape(summary['high_precision_classifier'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div></section>
  <section class="panel"><h2>Classifiers</h2>{render_table(classifiers, CLASSIFIER_FIELDNAMES)}</section>
  <section class="panel"><h2>Errors</h2>{render_table(errors, ERROR_FIELDNAMES)}</section>
  <section class="panel"><h2>Fixtures</h2>{render_table(fixtures, FIXTURE_FIELDNAMES)}</section>
</main>
<script>
const TEX_GAP_LITERAL_TOKEN_CLASSIFIER_PROBE = {data_json};
</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    literals_path: Path,
    *,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    literal_rows = read_csv(literals_path)
    specs = classifier_specs()
    classifiers = [evaluate_classifier(name, description, literal_rows, predicate) for name, description, predicate in specs]
    error_classifiers = {
        name: predicate
        for name, _description, predicate in specs
        if name in {"small_token", "small_not_backward", "small_not_backward_abs_delta_le512"}
    }
    errors: list[dict[str, str]] = []
    for name, predicate in error_classifiers.items():
        errors.extend(error_rows(literal_rows, name, predicate))
    fixtures = fixture_rows(literal_rows)
    summary = summary_row(literal_rows, classifiers, errors)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "classifiers.csv", CLASSIFIER_FIELDNAMES, classifiers)
    write_csv(output_dir / "classifier_errors.csv", ERROR_FIELDNAMES, errors)
    write_csv(output_dir / "by_fixture.csv", FIXTURE_FIELDNAMES, fixtures)
    (output_dir / "index.html").write_text(build_html(summary, classifiers, errors, fixtures, output_dir, title))
    return summary, classifiers, errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Classify .tex literal length token candidates.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--literals", type=Path, default=DEFAULT_LITERALS)
    parser.add_argument("--title", default="Lands of Lore II .tex Gap Literal Token Classifier Probe")
    args = parser.parse_args()

    summary, _classifiers, _errors = write_report(args.output, args.literals, title=args.title)
    print(f"Literal ops: {summary['literal_ops']}")
    print(f"Actual token+3 ops: {summary['actual_token_plus3_ops']}")
    print(f"Small-token false positives: {summary['small_token_false_positive_ops']}")
    print(
        "High recall: "
        f"{summary['high_recall_classifier']} p={summary['high_recall_precision']} r={summary['high_recall_recall']}"
    )
    print(
        "High precision: "
        f"{summary['high_precision_classifier']} p={summary['high_precision_precision']} "
        f"r={summary['high_precision_recall']}"
    )
    print(f"Issue rows: {summary['issue_rows']}")


if __name__ == "__main__":
    main()
