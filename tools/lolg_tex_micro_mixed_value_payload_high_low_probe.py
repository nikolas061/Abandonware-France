#!/usr/bin/env python3
"""Inspect low-nibble resolvers for sparse false-free mixed-value high contexts."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_micro_mixed_value_payload_combo_probe import (
    DEFAULT_OUTPUT as DEFAULT_COMBO_OUTPUT,
    enrich_entries,
)
from lolg_tex_micro_mixed_value_payload_predictor_probe import (
    DEFAULT_FIXTURES,
    DEFAULT_INPUT_ROWS,
    build_entries,
    build_payloads,
    int_value,
    ratio,
    read_csv,
    strict_prediction,
    write_csv,
)


DEFAULT_COMBO_SUMMARY = DEFAULT_COMBO_OUTPUT / "summary.csv"
DEFAULT_OUTPUT = Path("output/tex_micro_mixed_value_payload_high_low")

SUMMARY_FIELDNAMES = [
    "scope",
    "high_feature_set",
    "target_rows",
    "target_bytes",
    "selected_high_slots",
    "selected_high_rows",
    "selected_low_values",
    "low_context_sets",
    "best_low_feature_set",
    "best_low_correct_slots",
    "best_low_false_slots",
    "best_low_unknown_slots",
    "best_low_precision",
    "deterministic_low_contexts",
    "deterministic_low_slots",
    "promotion_ready_bytes",
    "issue_rows",
]

ROW_FIELDNAMES = [
    "rank",
    "row_index",
    "archive",
    "pcx_name",
    "frontier_id",
    "span_index",
    "op_index",
    "start",
    "end",
    "offset",
    "byte",
    "high",
    "low",
    "high_context",
    "high_prediction",
    "prev1",
    "prev_delta",
    "control",
    "dominant_byte",
]

CONTEXT_FIELDNAMES = [
    "rank",
    "feature_set",
    "context_key",
    "slots",
    "rows",
    "low_values",
    "dominant_low",
    "dominant_ratio",
    "deterministic",
    "sample_pcx",
    "sample_frontier_id",
]

LOW_FEATURE_SETS = [
    ("prev1",),
    ("prev1", "pos16"),
    ("prev1", "pos8"),
    ("prev1_low", "pos16"),
    ("pos4", "pos16"),
    ("offset_context",),
    ("dominant_byte",),
    ("signal",),
    ("control",),
    ("prev_delta", "control"),
]


def read_summary(path: Path) -> dict[str, str]:
    rows = read_csv(path)
    return rows[0] if rows else {}


def selected_high_entries(
    entries: list[dict[str, object]],
    feature_set: tuple[str, ...],
) -> list[tuple[dict[str, object], str, tuple[object, ...]]]:
    all_counts: dict[tuple[object, ...], Counter[str]] = defaultdict(Counter)
    row_counts: dict[tuple[int, tuple[object, ...]], Counter[str]] = defaultdict(Counter)
    for entry in entries:
        context = tuple(entry[feature] for feature in feature_set)
        value = str(entry["high"])
        all_counts[context][value] += 1
        row_counts[(int(entry["row_index"]), context)][value] += 1

    selected: list[tuple[dict[str, object], str, tuple[object, ...]]] = []
    for entry in entries:
        context = tuple(entry[feature] for feature in feature_set)
        train_counts = all_counts[context].copy()
        train_counts.subtract(row_counts[(int(entry["row_index"]), context)])
        train_counts += Counter()
        prediction = strict_prediction(train_counts)
        if prediction is not None and prediction == str(entry["high"]):
            selected.append((entry, prediction, context))
    return selected


def evaluate_low_feature_set(
    selected: list[tuple[dict[str, object], str, tuple[object, ...]]],
    feature_set: tuple[str, ...],
) -> dict[str, object]:
    all_counts: dict[tuple[object, ...], Counter[str]] = defaultdict(Counter)
    row_counts: dict[tuple[int, tuple[object, ...]], Counter[str]] = defaultdict(Counter)
    for entry, _prediction, _high_context in selected:
        context = tuple(entry[feature] for feature in feature_set)
        value = str(entry["low"])
        all_counts[context][value] += 1
        row_counts[(int(entry["row_index"]), context)][value] += 1

    correct = 0
    false = 0
    unknown = 0
    for entry, _prediction, _high_context in selected:
        context = tuple(entry[feature] for feature in feature_set)
        train_counts = all_counts[context].copy()
        train_counts.subtract(row_counts[(int(entry["row_index"]), context)])
        train_counts += Counter()
        prediction = strict_prediction(train_counts)
        if prediction is None:
            unknown += 1
        elif prediction == str(entry["low"]):
            correct += 1
        else:
            false += 1
    return {
        "feature_set": "+".join(feature_set),
        "correct": correct,
        "false": false,
        "unknown": unknown,
    }


def build_context_rows(
    selected: list[tuple[dict[str, object], str, tuple[object, ...]]],
    input_rows: list[dict[str, str]],
) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for feature_set in LOW_FEATURE_SETS:
        grouped: dict[tuple[object, ...], list[dict[str, object]]] = defaultdict(list)
        for entry, _prediction, _high_context in selected:
            grouped[tuple(entry[feature] for feature in feature_set)].append(entry)
        for context, members in grouped.items():
            values = Counter(str(entry["low"]) for entry in members)
            dominant, dominant_count = values.most_common(1)[0]
            source_row = input_rows[int(members[0]["row_index"])]
            output.append(
                {
                    "rank": 0,
                    "feature_set": "+".join(feature_set),
                    "context_key": "|".join(str(part) for part in context),
                    "slots": len(members),
                    "rows": len({int(entry["row_index"]) for entry in members}),
                    "low_values": "|".join(f"{value}:{count}" for value, count in values.most_common()),
                    "dominant_low": dominant,
                    "dominant_ratio": ratio(dominant_count, len(members)),
                    "deterministic": "1" if len(values) == 1 else "0",
                    "sample_pcx": source_row.get("pcx_name", ""),
                    "sample_frontier_id": source_row.get("frontier_id", ""),
                }
            )
    output.sort(
        key=lambda row: (
            -int_value(row, "deterministic"),
            -int_value(row, "slots"),
            str(row["feature_set"]),
            str(row["context_key"]),
        )
    )
    for index, row in enumerate(output, start=1):
        row["rank"] = index
    return output


def build(
    input_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    combo_summary: dict[str, str],
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    payloads, issues = build_payloads(input_rows, fixture_rows)
    entries = build_entries(payloads)
    enrich_entries(entries, input_rows)
    high_feature_text = combo_summary.get("best_false_free_high_feature_set", "")
    high_feature_set = tuple(part for part in high_feature_text.split("+") if part)
    selected = selected_high_entries(entries, high_feature_set) if high_feature_set else []

    row_output: list[dict[str, object]] = []
    for rank, (entry, prediction, high_context) in enumerate(selected, start=1):
        source_row = input_rows[int(entry["row_index"])]
        row_output.append(
            {
                "rank": rank,
                "row_index": entry["row_index"],
                "archive": source_row.get("archive", ""),
                "pcx_name": source_row.get("pcx_name", ""),
                "frontier_id": source_row.get("frontier_id", ""),
                "span_index": source_row.get("span_index", ""),
                "op_index": source_row.get("op_index", ""),
                "start": source_row.get("start", ""),
                "end": source_row.get("end", ""),
                "offset": entry["offset"],
                "byte": entry["byte"],
                "high": entry["high"],
                "low": entry["low"],
                "high_context": "|".join(str(part) for part in high_context),
                "high_prediction": prediction,
                "prev1": entry["prev1"],
                "prev_delta": entry["prev_delta"],
                "control": entry["control"],
                "dominant_byte": entry["dominant_byte"],
            }
        )

    context_rows = build_context_rows(selected, input_rows)
    low_results = [evaluate_low_feature_set(selected, feature_set) for feature_set in LOW_FEATURE_SETS]
    low_results.sort(key=lambda row: (int(row["correct"]), -int(row["false"]), -int(row["unknown"])), reverse=True)
    best_low = low_results[0] if low_results else {}
    deterministic_contexts = [row for row in context_rows if row.get("deterministic") == "1"]
    summary = {
        "scope": "total",
        "high_feature_set": high_feature_text,
        "target_rows": len(payloads),
        "target_bytes": sum(len(payload) for _row, payload in payloads),
        "selected_high_slots": len(selected),
        "selected_high_rows": len({int(entry["row_index"]) for entry, _prediction, _context in selected}),
        "selected_low_values": "|".join(
            f"{value}:{count}" for value, count in Counter(str(entry["low"]) for entry, _p, _c in selected).most_common()
        ),
        "low_context_sets": len(LOW_FEATURE_SETS),
        "best_low_feature_set": best_low.get("feature_set", ""),
        "best_low_correct_slots": best_low.get("correct", 0),
        "best_low_false_slots": best_low.get("false", 0),
        "best_low_unknown_slots": best_low.get("unknown", 0),
        "best_low_precision": ratio(int(best_low.get("correct", 0)), int(best_low.get("correct", 0)) + int(best_low.get("false", 0))),
        "deterministic_low_contexts": len(deterministic_contexts),
        "deterministic_low_slots": sum(int_value(row, "slots") for row in deterministic_contexts),
        "promotion_ready_bytes": 0,
        "issue_rows": len(issues),
    }
    return summary, row_output, context_rows


def render_table(rows: list[dict[str, object]], fields: list[str], limit: int = 220) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, object],
    rows: list[dict[str, object]],
    contexts: list[dict[str, object]],
    title: str,
) -> str:
    data_json = json.dumps({"summary": summary, "rows": rows, "contexts": contexts}, indent=2, sort_keys=True)
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body {{ margin: 2rem; background: #111416; color: #edf5f4; font: 14px/1.45 system-ui, sans-serif; }}
table {{ border-collapse: collapse; width: 100%; min-width: 1450px; }}
th, td {{ border: 1px solid #31424a; padding: .45rem .55rem; vertical-align: top; }}
th {{ color: #9dafb5; background: #172023; text-align: left; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: .75rem; margin: 1rem 0; }}
.box {{ border: 1px solid #31424a; background: #172023; padding: .75rem; }}
.num {{ font-size: 1.35rem; font-weight: 750; }}
.muted {{ color: #9dafb5; }}
.panel {{ overflow-x: auto; margin-top: 1rem; }}
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<div class="grid">
  <div class="box"><div class="num">{summary['selected_high_slots']}</div><div class="muted">selected high slots</div></div>
  <div class="box"><div class="num">{summary['selected_low_values']}</div><div class="muted">selected low values</div></div>
  <div class="box"><div class="num">{summary['best_low_correct_slots']}/{summary['best_low_false_slots']}</div><div class="muted">best low correct/false</div></div>
  <div class="box"><div class="num">{summary['best_low_unknown_slots']}</div><div class="muted">best low unknown</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Selected slots</h2>{render_table(rows, ROW_FIELDNAMES)}</div>
<div class="panel"><h2>Low contexts</h2>{render_table(contexts, CONTEXT_FIELDNAMES)}</div>
<script type="application/json" id="mixed-value-payload-high-low-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect low-nibble resolvers for mixed-value high contexts.")
    parser.add_argument("--input-rows", type=Path, default=DEFAULT_INPUT_ROWS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--combo-summary", type=Path, default=DEFAULT_COMBO_SUMMARY)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Mixed Value Payload High/Low Probe")
    args = parser.parse_args()

    summary, rows, contexts = build(
        read_csv(args.input_rows),
        read_csv(args.fixtures),
        read_summary(args.combo_summary),
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "rows.csv", ROW_FIELDNAMES, rows)
    write_csv(args.output / "contexts.csv", CONTEXT_FIELDNAMES, contexts)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, rows, contexts, args.title))

    print(f"Selected high slots: {summary['selected_high_slots']}")
    print(f"Selected low values: {summary['selected_low_values']}")
    print(
        f"Best low resolver: {summary['best_low_feature_set']} "
        f"{summary['best_low_correct_slots']}/{summary['best_low_false_slots']}"
    )
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
