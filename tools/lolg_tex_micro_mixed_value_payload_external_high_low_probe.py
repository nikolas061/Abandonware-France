#!/usr/bin/env python3
"""Inspect low-nibble prediction for external-source high mixed-value slots."""

from __future__ import annotations

import argparse
import csv
import html
import itertools
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_micro_mixed_value_payload_external_source_combo_probe import (
    DEFAULT_OUTPUT as DEFAULT_EXTERNAL_COMBO_OUTPUT,
    DEFAULT_SOURCE_PROFILE_ROWS,
    add_external_features,
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
from lolg_tex_micro_mixed_value_payload_source_profile_probe import DEFAULT_REPLAY_FIXTURES


DEFAULT_EXTERNAL_COMBO_SUMMARY = DEFAULT_EXTERNAL_COMBO_OUTPUT / "summary.csv"
DEFAULT_OUTPUT = Path("output/tex_micro_mixed_value_payload_external_high_low")

SUMMARY_FIELDNAMES = [
    "scope",
    "high_feature_set",
    "target_rows",
    "target_bytes",
    "selected_high_slots",
    "selected_high_rows",
    "selected_low_values",
    "low_feature_sets",
    "best_low_feature_set",
    "best_low_correct_slots",
    "best_low_false_slots",
    "best_low_unknown_slots",
    "best_low_precision",
    "false_free_low_sets",
    "false_free_low_slots",
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
    "best_pool",
    "best_d2",
    "best_b2",
    "compressed_b0",
    "profile_b0",
]

LOW_CANDIDATE_FIELDNAMES = [
    "rank",
    "feature_set",
    "feature_count",
    "contexts",
    "deterministic_slots",
    "conflicted_slots",
    "loo_correct_slots",
    "loo_false_slots",
    "loo_unknown_slots",
    "loo_precision",
    "predicted_values",
    "verdict",
    "sample_context",
    "sample_prediction",
]

LOW_FEATURES = [
    "prev1",
    "pos16",
    "pos8",
    "best_pool",
    "best_d2",
    "best_b2",
    "best_l2",
    "compressed_l0",
    "compressed_b0",
    "profile_b0",
    "profile_l0",
    "profile_b1",
    "profile_b2",
]


def read_summary(path: Path) -> dict[str, str]:
    rows = read_csv(path)
    return rows[0] if rows else {}


def feature_combinations(max_features: int) -> list[tuple[str, ...]]:
    output: list[tuple[str, ...]] = []
    for size in range(1, max_features + 1):
        output.extend(itertools.combinations(LOW_FEATURES, size))
    return output


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


def evaluate_low_candidate(
    selected: list[tuple[dict[str, object], str, tuple[object, ...]]],
    feature_set: tuple[str, ...],
) -> dict[str, object]:
    all_counts: dict[tuple[object, ...], Counter[str]] = defaultdict(Counter)
    row_counts: dict[tuple[int, tuple[object, ...]], Counter[str]] = defaultdict(Counter)
    grouped_slots: dict[tuple[object, ...], int] = defaultdict(int)
    for entry, _prediction, _high_context in selected:
        context = tuple(entry[feature] for feature in feature_set)
        value = str(entry["low"])
        all_counts[context][value] += 1
        row_counts[(int(entry["row_index"]), context)][value] += 1
        grouped_slots[context] += 1

    deterministic_slots = sum(
        grouped_slots[context]
        for context, counts in all_counts.items()
        if len([value for value, count in counts.items() if count]) == 1
    )
    conflicted_slots = sum(
        grouped_slots[context]
        for context, counts in all_counts.items()
        if len([value for value, count in counts.items() if count]) > 1
    )
    predicted_values: Counter[str] = Counter()
    for context, counts in all_counts.items():
        prediction = strict_prediction(counts)
        if prediction is not None:
            predicted_values[prediction] += grouped_slots[context]

    correct = 0
    false = 0
    unknown = 0
    sample_context = ""
    sample_prediction = ""
    for entry, _prediction, _high_context in selected:
        context = tuple(entry[feature] for feature in feature_set)
        train_counts = all_counts[context].copy()
        train_counts.subtract(row_counts[(int(entry["row_index"]), context)])
        train_counts += Counter()
        prediction = strict_prediction(train_counts)
        if prediction is None:
            unknown += 1
            continue
        if not sample_context:
            sample_context = "|".join(str(part) for part in context)
            sample_prediction = prediction
        if prediction == str(entry["low"]):
            correct += 1
        else:
            false += 1

    predicted = correct + false
    if predicted == 0:
        verdict = "no_cross_row_low_prediction"
    elif false == 0 and correct > 0:
        verdict = "false_free_low_review"
    elif correct == 0 and false > 0:
        verdict = "low_resolver_reject"
    else:
        verdict = "conflicted_low_resolver"

    return {
        "rank": 0,
        "feature_set": "+".join(feature_set),
        "feature_count": len(feature_set),
        "contexts": len(all_counts),
        "deterministic_slots": deterministic_slots,
        "conflicted_slots": conflicted_slots,
        "loo_correct_slots": correct,
        "loo_false_slots": false,
        "loo_unknown_slots": unknown,
        "loo_precision": ratio(correct, predicted),
        "predicted_values": "|".join(f"{value}:{count}" for value, count in predicted_values.most_common(8)),
        "verdict": verdict,
        "sample_context": sample_context,
        "sample_prediction": sample_prediction,
    }


def best_candidate(rows: list[dict[str, object]]) -> dict[str, object]:
    candidates = [
        row
        for row in rows
        if int_value(row, "loo_correct_slots") + int_value(row, "loo_false_slots") > 0
    ]
    if not candidates:
        return rows[0] if rows else {}
    candidates.sort(
        key=lambda row: (
            int_value(row, "loo_correct_slots"),
            -int_value(row, "loo_false_slots"),
            -int_value(row, "feature_count"),
        ),
        reverse=True,
    )
    return candidates[0]


def build(
    input_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    replay_rows: list[dict[str, str]],
    source_profile_rows: list[dict[str, str]],
    external_combo_summary: dict[str, str],
    *,
    max_features: int,
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    payloads, issues = build_payloads(input_rows, fixture_rows)
    entries = build_entries(payloads)
    issues.extend(add_external_features(entries, input_rows, source_profile_rows, fixture_rows, replay_rows))
    high_feature_text = external_combo_summary.get("best_false_free_high_feature_set", "")
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
                "best_pool": entry["best_pool"],
                "best_d2": entry["best_d2"],
                "best_b2": entry["best_b2"],
                "compressed_b0": entry["compressed_b0"],
                "profile_b0": entry["profile_b0"],
            }
        )

    candidates = [
        evaluate_low_candidate(selected, feature_set)
        for feature_set in feature_combinations(max_features)
    ]
    candidates.sort(
        key=lambda row: (
            -int_value(row, "loo_correct_slots"),
            int_value(row, "loo_false_slots"),
            int_value(row, "feature_count"),
            str(row["feature_set"]),
        )
    )
    for index, row in enumerate(candidates, start=1):
        row["rank"] = index

    best_low = best_candidate(candidates)
    false_free = [
        row
        for row in candidates
        if int_value(row, "loo_correct_slots") > 0 and int_value(row, "loo_false_slots") == 0
    ]
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
        "low_feature_sets": len(candidates),
        "best_low_feature_set": best_low.get("feature_set", ""),
        "best_low_correct_slots": best_low.get("loo_correct_slots", 0),
        "best_low_false_slots": best_low.get("loo_false_slots", 0),
        "best_low_unknown_slots": best_low.get("loo_unknown_slots", 0),
        "best_low_precision": best_low.get("loo_precision", "0.000000"),
        "false_free_low_sets": len(false_free),
        "false_free_low_slots": sum(int_value(row, "loo_correct_slots") for row in false_free),
        "promotion_ready_bytes": 0,
        "issue_rows": len(issues),
    }
    return summary, row_output, candidates


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
    candidates: list[dict[str, object]],
    title: str,
) -> str:
    data_json = json.dumps({"summary": summary, "rows": rows, "candidates": candidates}, indent=2, sort_keys=True)
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body {{ margin: 2rem; background: #111416; color: #edf5f4; font: 14px/1.45 system-ui, sans-serif; }}
table {{ border-collapse: collapse; width: 100%; min-width: 1500px; }}
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
  <div class="box"><div class="num">{summary['false_free_low_slots']}</div><div class="muted">false-free low slots</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Selected slots</h2>{render_table(rows, ROW_FIELDNAMES)}</div>
<div class="panel"><h2>Low candidates</h2>{render_table(candidates, LOW_CANDIDATE_FIELDNAMES)}</div>
<script type="application/json" id="mixed-value-external-high-low-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect low-nibble prediction for external mixed-value high slots.")
    parser.add_argument("--input-rows", type=Path, default=DEFAULT_INPUT_ROWS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--replay-fixtures", type=Path, default=DEFAULT_REPLAY_FIXTURES)
    parser.add_argument("--source-profile-rows", type=Path, default=DEFAULT_SOURCE_PROFILE_ROWS)
    parser.add_argument("--external-combo-summary", type=Path, default=DEFAULT_EXTERNAL_COMBO_SUMMARY)
    parser.add_argument("--max-features", type=int, default=3)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Mixed Value External High/Low Probe")
    args = parser.parse_args()

    summary, rows, candidates = build(
        read_csv(args.input_rows),
        read_csv(args.fixtures),
        read_csv(args.replay_fixtures),
        read_csv(args.source_profile_rows),
        read_summary(args.external_combo_summary),
        max_features=args.max_features,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "rows.csv", ROW_FIELDNAMES, rows)
    write_csv(args.output / "candidates.csv", LOW_CANDIDATE_FIELDNAMES, candidates)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, rows, candidates, args.title))

    print(f"Selected external high slots: {summary['selected_high_slots']}")
    print(f"Selected low values: {summary['selected_low_values']}")
    print(
        f"Best low resolver: {summary['best_low_feature_set']} "
        f"{summary['best_low_correct_slots']}/{summary['best_low_false_slots']}"
    )
    print(f"False-free low slots: {summary['false_free_low_slots']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
