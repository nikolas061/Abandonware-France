#!/usr/bin/env python3
"""Probe non-oracle rules that reject false .tex literal length tokens."""

from __future__ import annotations

import argparse
import csv
import html
import json
from pathlib import Path

from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_literal_fp_rejection_probe")
DEFAULT_LITERALS = Path("output/tex_gap_literal_token_probe/literals.csv")
DEFAULT_OPERATIONS = Path("output/tex_gap_segmentation_control_correlation_probe/operations.csv")

REPEATED_FALSE_PRE2 = {"020a", "0703", "0704", "0002", "2f08"}
REPEATED_FALSE_PRE4 = {"6edc020a", "5d5c0703", "6bfc0704", "17542f08"}
REPEATED_FALSE_NEXT2 = {"5a5c", "5d6d", "aa6c", "7b6a"}
REPEATED_FALSE_MOD64 = {5, 28, 34}

SUMMARY_FIELDNAMES = [
    "scope",
    "literal_rows",
    "operation_rows",
    "actual_token_plus3_ops",
    "actual_token_plus3_bytes",
    "baseline_false_positive_ops",
    "baseline_false_positive_bytes",
    "full_recall_candidate",
    "full_recall_true_positive_ops",
    "full_recall_false_positive_ops",
    "full_recall_false_positive_bytes",
    "low_false_candidate",
    "low_false_true_positive_ops",
    "low_false_false_positive_ops",
    "low_false_false_positive_bytes",
    "candidate_rows",
    "rejection_rows",
    "fixture_rows",
    "issue_rows",
]

CLASSIFIER_FIELDNAMES = [
    "classifier",
    "description",
    "uses_oracle_filter",
    "selected_ops",
    "true_positive_ops",
    "false_positive_ops",
    "false_negative_ops",
    "precision",
    "recall",
    "true_positive_bytes",
    "false_positive_bytes",
    "rejected_baseline_false_positive_ops",
    "rejected_baseline_false_positive_bytes",
]

REJECTION_FIELDNAMES = [
    "rank",
    "pcx_name",
    "frontier_id",
    "op_index",
    "expected_start",
    "length",
    "source_offset",
    "token_hex",
    "token_value",
    "source_direction",
    "source_delta_from_prev_literal_end",
    "pre2_hex",
    "pre4_hex",
    "next2_hex",
    "expected_mod64",
    "rejected_by",
    "kept_by",
    "expected_hex",
]

FIXTURE_FIELDNAMES = [
    "rank",
    "pcx_name",
    "frontier_id",
    "literal_ops",
    "actual_token_plus3_ops",
    "baseline_false_positive_ops",
    "full_recall_false_positive_ops",
    "low_false_false_positive_ops",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def row_key(row: dict[str, str]) -> tuple[str, str, str, str]:
    return row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", ""), row.get("op_index", "")


def fixture_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", "")


def enrich_literals(
    literal_rows: list[dict[str, str]],
    operation_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    operations = {row_key(row): row for row in operation_rows}
    rows: list[dict[str, str]] = []
    for row in literal_rows:
        operation = operations.get(row_key(row), {})
        enriched = dict(row)
        enriched["pre2_hex"] = operation.get("pre2_hex", "")
        enriched["pre4_hex"] = operation.get("pre4_hex", "")
        enriched["next2_hex"] = operation.get("next2_hex", "")
        enriched["expected_mod64"] = operation.get("expected_mod64", "")
        enriched["join_missing"] = "0" if operation else "1"
        rows.append(enriched)
    return rows


def token_value(row: dict[str, str]) -> int:
    return int_value(row, "token_value") if row.get("token_value") else -1


def expected_mod64(row: dict[str, str]) -> int:
    return int_value(row, "expected_mod64") if row.get("expected_mod64") else -1


def is_actual(row: dict[str, str]) -> bool:
    return row.get("token_plus3_match") == "1"


def is_small(row: dict[str, str]) -> bool:
    return 0 <= token_value(row) <= 13


def is_nonzero_small(row: dict[str, str]) -> bool:
    return 1 <= token_value(row) <= 13


def classifier_specs():
    return [
        (
            "small_token",
            "baseline token value <= 13",
            False,
            is_small,
        ),
        (
            "small_nonzero_token",
            "1 <= token value <= 13",
            False,
            is_nonzero_small,
        ),
        (
            "small_nonzero_next2_clean",
            "nonzero small token and next two source bytes are not repeated false-positive signatures",
            False,
            lambda row: is_nonzero_small(row) and row.get("next2_hex") not in REPEATED_FALSE_NEXT2,
        ),
        (
            "small_nonzero_pre4_clean",
            "nonzero small token and previous four source bytes are not repeated false-positive signatures",
            False,
            lambda row: is_nonzero_small(row) and row.get("pre4_hex") not in REPEATED_FALSE_PRE4,
        ),
        (
            "small_nonzero_pre2_clean",
            "nonzero small token and previous two source bytes are not repeated false-positive signatures",
            False,
            lambda row: is_nonzero_small(row) and row.get("pre2_hex") not in REPEATED_FALSE_PRE2,
        ),
        (
            "small_not_backward_nonzero_pre2_clean",
            "nonzero small token, not a backward source jump, and previous two source bytes are clean",
            False,
            lambda row: is_nonzero_small(row)
            and row.get("source_direction") != "backward"
            and row.get("pre2_hex") not in REPEATED_FALSE_PRE2,
        ),
        (
            "small_not_backward_nonzero_pre4_mod_clean",
            "nonzero small token, not backward, clean previous four bytes, and clean output mod64",
            False,
            lambda row: is_nonzero_small(row)
            and row.get("source_direction") != "backward"
            and row.get("pre4_hex") not in REPEATED_FALSE_PRE4
            and expected_mod64(row) not in REPEATED_FALSE_MOD64,
        ),
        (
            "oracle_token_plus3",
            "token + 3 equals segmented literal length",
            True,
            is_actual,
        ),
    ]


def evaluate_classifier(
    name: str,
    description: str,
    uses_oracle: bool,
    predicate,
    literal_rows: list[dict[str, str]],
    baseline_false: list[dict[str, str]],
) -> dict[str, str]:
    selected = [row for row in literal_rows if predicate(row)]
    actual_rows = [row for row in literal_rows if is_actual(row)]
    true_positive = [row for row in selected if is_actual(row)]
    false_positive = [row for row in selected if not is_actual(row)]
    true_ids = {id(row) for row in true_positive}
    false_negative = [row for row in actual_rows if id(row) not in true_ids]
    selected_ids = {id(row) for row in selected}
    rejected_baseline = [row for row in baseline_false if id(row) not in selected_ids]
    precision = len(true_positive) / len(selected) if selected else 0.0
    recall = len(true_positive) / len(actual_rows) if actual_rows else 0.0
    return {
        "classifier": name,
        "description": description,
        "uses_oracle_filter": "1" if uses_oracle else "0",
        "selected_ops": str(len(selected)),
        "true_positive_ops": str(len(true_positive)),
        "false_positive_ops": str(len(false_positive)),
        "false_negative_ops": str(len(false_negative)),
        "precision": f"{precision:.6f}",
        "recall": f"{recall:.6f}",
        "true_positive_bytes": str(sum(int_value(row, "length") for row in true_positive)),
        "false_positive_bytes": str(sum(int_value(row, "length") for row in false_positive)),
        "rejected_baseline_false_positive_ops": str(len(rejected_baseline)),
        "rejected_baseline_false_positive_bytes": str(
            sum(int_value(row, "length") for row in rejected_baseline)
        ),
    }


def classifier_maps():
    return {
        name: predicate
        for name, _description, uses_oracle, predicate in classifier_specs()
        if not uses_oracle and name != "small_token"
    }


def rejection_rows(literal_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    baseline_false = [row for row in literal_rows if is_small(row) and not is_actual(row)]
    predicates = classifier_maps()
    rows: list[dict[str, str]] = []
    for row in baseline_false:
        rejected_by = sorted(name for name, predicate in predicates.items() if not predicate(row))
        kept_by = sorted(name for name, predicate in predicates.items() if predicate(row))
        rows.append(
            {
                "rank": row.get("rank", ""),
                "pcx_name": row.get("pcx_name", ""),
                "frontier_id": row.get("frontier_id", ""),
                "op_index": row.get("op_index", ""),
                "expected_start": row.get("expected_start", ""),
                "length": row.get("length", ""),
                "source_offset": row.get("source_offset", ""),
                "token_hex": row.get("token_hex", ""),
                "token_value": row.get("token_value", ""),
                "source_direction": row.get("source_direction", ""),
                "source_delta_from_prev_literal_end": row.get("source_delta_from_prev_literal_end", ""),
                "pre2_hex": row.get("pre2_hex", ""),
                "pre4_hex": row.get("pre4_hex", ""),
                "next2_hex": row.get("next2_hex", ""),
                "expected_mod64": row.get("expected_mod64", ""),
                "rejected_by": ";".join(rejected_by),
                "kept_by": ";".join(kept_by),
                "expected_hex": row.get("expected_hex", ""),
            }
        )
    return rows


def select_full_recall(classifiers: list[dict[str, str]], actual_ops: int) -> dict[str, str]:
    candidates = [
        row
        for row in classifiers
        if row.get("uses_oracle_filter") != "1" and int_value(row, "true_positive_ops") == actual_ops
    ]
    return min(
        candidates,
        key=lambda row: (
            int_value(row, "false_positive_bytes"),
            int_value(row, "false_positive_ops"),
            row.get("classifier", ""),
        ),
    )


def select_low_false(classifiers: list[dict[str, str]], actual_ops: int) -> dict[str, str]:
    candidates = [
        row
        for row in classifiers
        if row.get("uses_oracle_filter") != "1"
        and actual_ops
        and int_value(row, "true_positive_ops") / actual_ops >= 0.90
    ]
    return min(
        candidates,
        key=lambda row: (
            int_value(row, "false_positive_bytes"),
            int_value(row, "false_positive_ops"),
            -int_value(row, "true_positive_bytes"),
            row.get("classifier", ""),
        ),
    )


def fixture_rows(
    literal_rows: list[dict[str, str]],
    full_recall_name: str,
    low_false_name: str,
) -> list[dict[str, str]]:
    predicates = {name: predicate for name, _description, _uses_oracle, predicate in classifier_specs()}
    groups: dict[tuple[str, str, str], list[dict[str, str]]] = {}
    for row in literal_rows:
        groups.setdefault(fixture_key(row), []).append(row)
    rows: list[dict[str, str]] = []
    for key, group in sorted(groups.items(), key=lambda item: int(item[0][0]) if item[0][0].isdigit() else 999999):
        baseline_false = [row for row in group if is_small(row) and not is_actual(row)]
        full_recall_false = [
            row for row in group if predicates[full_recall_name](row) and not is_actual(row)
        ]
        low_false_false = [row for row in group if predicates[low_false_name](row) and not is_actual(row)]
        rows.append(
            {
                "rank": key[0],
                "pcx_name": key[1],
                "frontier_id": key[2],
                "literal_ops": str(len(group)),
                "actual_token_plus3_ops": str(sum(1 for row in group if is_actual(row))),
                "baseline_false_positive_ops": str(len(baseline_false)),
                "full_recall_false_positive_ops": str(len(full_recall_false)),
                "low_false_false_positive_ops": str(len(low_false_false)),
            }
        )
    return rows


def summary_row(
    literal_rows: list[dict[str, str]],
    operation_rows: list[dict[str, str]],
    classifiers: list[dict[str, str]],
    rejections: list[dict[str, str]],
    fixtures: list[dict[str, str]],
) -> dict[str, str]:
    actual_rows = [row for row in literal_rows if is_actual(row)]
    baseline = next(row for row in classifiers if row.get("classifier") == "small_token")
    full_recall = select_full_recall(classifiers, len(actual_rows))
    low_false = select_low_false(classifiers, len(actual_rows))
    return {
        "scope": "total",
        "literal_rows": str(len(literal_rows)),
        "operation_rows": str(len(operation_rows)),
        "actual_token_plus3_ops": str(len(actual_rows)),
        "actual_token_plus3_bytes": str(sum(int_value(row, "length") for row in actual_rows)),
        "baseline_false_positive_ops": baseline.get("false_positive_ops", "0"),
        "baseline_false_positive_bytes": baseline.get("false_positive_bytes", "0"),
        "full_recall_candidate": full_recall.get("classifier", ""),
        "full_recall_true_positive_ops": full_recall.get("true_positive_ops", "0"),
        "full_recall_false_positive_ops": full_recall.get("false_positive_ops", "0"),
        "full_recall_false_positive_bytes": full_recall.get("false_positive_bytes", "0"),
        "low_false_candidate": low_false.get("classifier", ""),
        "low_false_true_positive_ops": low_false.get("true_positive_ops", "0"),
        "low_false_false_positive_ops": low_false.get("false_positive_ops", "0"),
        "low_false_false_positive_bytes": low_false.get("false_positive_bytes", "0"),
        "candidate_rows": str(len(classifiers)),
        "rejection_rows": str(len(rejections)),
        "fixture_rows": str(len(fixtures)),
        "issue_rows": str(
            sum(1 for row in literal_rows if row.get("issues"))
            + sum(1 for row in literal_rows if row.get("join_missing") == "1")
        ),
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
    rejections: list[dict[str, str]],
    fixtures: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "classifiers": classifiers,
        "rejections": rejections,
        "fixtures": fixtures,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("classifiers.csv", output_dir / "classifiers.csv"),
            ("rejections.csv", output_dir / "rejections.csv"),
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
table {{ width: 100%; border-collapse: collapse; min-width: 1160px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Scores simple non-oracle rejectors for false small-token literal candidates.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Baseline false bytes</div><div class="value">{html.escape(summary['baseline_false_positive_bytes'])}</div></div>
    <div class="stat"><div class="label">Full-recall rule</div><div class="value ok">{html.escape(summary['full_recall_candidate'])}</div></div>
    <div class="stat"><div class="label">Full-recall false bytes</div><div class="value">{html.escape(summary['full_recall_false_positive_bytes'])}</div></div>
    <div class="stat"><div class="label">Low-false false bytes</div><div class="value">{html.escape(summary['low_false_false_positive_bytes'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div></section>
  <section class="panel"><h2>Classifiers</h2>{render_table(classifiers, CLASSIFIER_FIELDNAMES)}</section>
  <section class="panel"><h2>Rejected baseline false positives</h2>{render_table(rejections, REJECTION_FIELDNAMES)}</section>
  <section class="panel"><h2>Fixtures</h2>{render_table(fixtures, FIXTURE_FIELDNAMES)}</section>
</main>
<script>
const TEX_GAP_LITERAL_FP_REJECTION_PROBE = {data_json};
</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    literals_path: Path,
    operations_path: Path,
    *,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_literals = read_csv(literals_path)
    operation_rows = read_csv(operations_path)
    literal_rows = enrich_literals(raw_literals, operation_rows)
    baseline_false = [row for row in literal_rows if is_small(row) and not is_actual(row)]
    classifiers = [
        evaluate_classifier(name, description, uses_oracle, predicate, literal_rows, baseline_false)
        for name, description, uses_oracle, predicate in classifier_specs()
    ]
    rejections = rejection_rows(literal_rows)
    full_recall = select_full_recall(classifiers, sum(1 for row in literal_rows if is_actual(row)))
    low_false = select_low_false(classifiers, sum(1 for row in literal_rows if is_actual(row)))
    fixtures = fixture_rows(literal_rows, full_recall["classifier"], low_false["classifier"])
    summary = summary_row(literal_rows, operation_rows, classifiers, rejections, fixtures)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "classifiers.csv", CLASSIFIER_FIELDNAMES, classifiers)
    write_csv(output_dir / "rejections.csv", REJECTION_FIELDNAMES, rejections)
    write_csv(output_dir / "by_fixture.csv", FIXTURE_FIELDNAMES, fixtures)
    (output_dir / "index.html").write_text(build_html(summary, classifiers, rejections, fixtures, output_dir, title))
    return summary, classifiers, rejections


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe .tex literal false-positive rejection rules.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--literals", type=Path, default=DEFAULT_LITERALS)
    parser.add_argument("--operations", type=Path, default=DEFAULT_OPERATIONS)
    parser.add_argument("--title", default="Lands of Lore II .tex Gap Literal False-Positive Rejection Probe")
    args = parser.parse_args()

    summary, _classifiers, _rejections = write_report(
        args.output,
        args.literals,
        args.operations,
        title=args.title,
    )
    print(f"Literal rows: {summary['literal_rows']}")
    print(f"Baseline false positives: {summary['baseline_false_positive_ops']}")
    print(
        "Full-recall rejector: "
        f"{summary['full_recall_candidate']} false={summary['full_recall_false_positive_bytes']}"
    )
    print(
        "Low-false rejector: "
        f"{summary['low_false_candidate']} false={summary['low_false_false_positive_bytes']}"
    )
    print(f"Issue rows: {summary['issue_rows']}")


if __name__ == "__main__":
    main()
