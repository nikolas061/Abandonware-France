#!/usr/bin/env python3
"""Probe source-enriched low splits for replayable mixed-value sequence slots."""

from __future__ import annotations

import argparse
import html
import itertools
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_micro_mixed_value_payload_external_source_combo_probe import (
    DEFAULT_SOURCE_PROFILE_ROWS,
    add_external_features,
    feature_names as external_feature_names,
)
from lolg_tex_micro_mixed_value_payload_predictor_probe import (
    DEFAULT_FIXTURES,
    int_value,
    ratio,
    read_csv,
    strict_prediction,
    write_csv,
)
from lolg_tex_micro_mixed_value_payload_sequence_candidate_review import (
    DEFAULT_INPUT_ROWS,
    DEFAULT_SELECTED_ROWS,
    context_for,
    enriched_selected_rows,
)
from lolg_tex_micro_mixed_value_payload_sequence_promoted_generalization_probe import (
    DEFAULT_REPLAY_FIXTURES,
    SLOT_FIELDNAMES as BASE_SLOT_FIELDNAMES,
    build_slots,
)
from lolg_tex_micro_mixed_value_payload_sequence_state_probe import FEATURES as SEQUENCE_FEATURES


DEFAULT_OUTPUT = Path("output/tex_micro_mixed_value_payload_sequence_low_split")

SUMMARY_FIELDNAMES = [
    "scope",
    "selected_high_slots",
    "features",
    "feature_sets",
    "replayable_unknown_slots",
    "target_known_slots",
    "blocked_prerequisite_slots",
    "false_free_split_sets",
    "best_false_free_split_feature_set",
    "best_false_free_split_correct_slots",
    "best_false_free_split_unknown_slots",
    "best_conflicted_feature_set",
    "best_conflicted_correct_slots",
    "best_conflicted_false_slots",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

RULE_FIELDNAMES = [
    "rank",
    "feature_set",
    "feature_count",
    "replayable_unknown_slots",
    "correct_slots",
    "false_slots",
    "unknown_slots",
    "precision",
    "predicted_values",
    "sample_correct_slots",
    "sample_false_slots",
    "sample_unknown_slots",
    "verdict",
]

SLOT_FIELDNAMES = [
    *BASE_SLOT_FIELDNAMES,
    "best_split_feature_set",
    "best_split_context",
    "best_split_predicted_low",
    "best_split_predicted_byte",
    "best_split_verdict",
]


def combined_feature_names(rows: list[dict[str, object]]) -> list[str]:
    names = list(SEQUENCE_FEATURES) + external_feature_names()
    return list(dict.fromkeys(name for name in names if all(name in row for row in rows)))


def feature_combinations(features: list[str], max_features: int) -> list[tuple[str, ...]]:
    output: list[tuple[str, ...]] = []
    for size in range(1, max_features + 1):
        output.extend(itertools.combinations(features, size))
    return output


def training_counts(
    rows: list[dict[str, object]],
    feature_set: tuple[str, ...],
) -> tuple[dict[tuple[str, ...], Counter[str]], dict[tuple[int, tuple[str, ...]], Counter[str]]]:
    all_counts: dict[tuple[str, ...], Counter[str]] = defaultdict(Counter)
    row_counts: dict[tuple[int, tuple[str, ...]], Counter[str]] = defaultdict(Counter)
    for row in rows:
        context = context_for(row, feature_set)
        value = str(row.get("low", ""))
        all_counts[context][value] += 1
        row_counts[(int_value(row, "row_index"), context)][value] += 1
    return all_counts, row_counts


def sample_label(slot: dict[str, object], predicted_byte: str = "") -> str:
    label = f"{slot.get('row_index')}:{slot.get('frontier_id')}:{slot.get('offset')}"
    return f"{label}={predicted_byte}" if predicted_byte else label


def evaluate_rule(
    rows_by_rank: dict[str, dict[str, object]],
    replayable_slots: list[dict[str, object]],
    all_rows: list[dict[str, object]],
    feature_set: tuple[str, ...],
) -> dict[str, object]:
    all_counts, row_counts = training_counts(all_rows, feature_set)
    correct = 0
    false = 0
    unknown = 0
    predicted_values: Counter[str] = Counter()
    sample_correct: list[str] = []
    sample_false: list[str] = []
    sample_unknown: list[str] = []
    for slot in replayable_slots:
        row = rows_by_rank.get(str(slot.get("rank", "")), {})
        context = context_for(row, feature_set)
        counts = all_counts[context].copy()
        counts.subtract(row_counts[(int_value(row, "row_index"), context)])
        counts += Counter()
        prediction = strict_prediction(counts)
        if prediction is None:
            unknown += 1
            if len(sample_unknown) < 6:
                sample_unknown.append(sample_label(slot))
            continue
        predicted_byte = f"{row.get('high_prediction', '')}{prediction}"
        predicted_values[predicted_byte] += 1
        if predicted_byte == row.get("byte", ""):
            correct += 1
            if len(sample_correct) < 6:
                sample_correct.append(sample_label(slot, predicted_byte))
        else:
            false += 1
            if len(sample_false) < 6:
                sample_false.append(f"{sample_label(slot, predicted_byte)}!={row.get('byte', '')}")

    predicted = correct + false
    if predicted == 0:
        verdict = "no_split_prediction"
    elif false == 0:
        verdict = "false_free_split_candidate"
    elif correct > 0:
        verdict = "split_conflict"
    else:
        verdict = "split_reject"
    return {
        "rank": 0,
        "feature_set": "+".join(feature_set),
        "feature_count": len(feature_set),
        "replayable_unknown_slots": len(replayable_slots),
        "correct_slots": correct,
        "false_slots": false,
        "unknown_slots": unknown,
        "precision": ratio(correct, predicted),
        "predicted_values": "|".join(f"{value}:{count}" for value, count in predicted_values.most_common()),
        "sample_correct_slots": "|".join(sample_correct),
        "sample_false_slots": "|".join(sample_false),
        "sample_unknown_slots": "|".join(sample_unknown),
        "verdict": verdict,
    }


def prediction_for_slot(
    rows_by_rank: dict[str, dict[str, object]],
    all_rows: list[dict[str, object]],
    slot: dict[str, object],
    feature_set: tuple[str, ...],
) -> tuple[str, str, str]:
    row = rows_by_rank.get(str(slot.get("rank", "")), {})
    all_counts, row_counts = training_counts(all_rows, feature_set)
    context = context_for(row, feature_set)
    counts = all_counts[context].copy()
    counts.subtract(row_counts[(int_value(row, "row_index"), context)])
    counts += Counter()
    prediction = strict_prediction(counts)
    if prediction is None:
        return "|".join(context), "", "unknown"
    predicted_byte = f"{row.get('high_prediction', '')}{prediction}"
    verdict = "correct" if predicted_byte == row.get("byte", "") else "false"
    return "|".join(context), predicted_byte, verdict


def build(
    selected_rows: list[dict[str, str]],
    input_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    replay_rows: list[dict[str, str]],
    source_profile_rows: list[dict[str, str]],
    *,
    max_features: int,
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    rows = enriched_selected_rows(selected_rows, input_rows)
    issues = add_external_features(rows, input_rows, source_profile_rows, fixture_rows, replay_rows)
    slots, _known_by_fixture, slot_issue_rows = build_slots(rows, replay_rows)
    replayable_slots = [slot for slot in slots if slot.get("state") == "replayable_unknown"]
    rows_by_rank = {str(row.get("rank", "")): row for row in rows}
    features = combined_feature_names(rows)
    rules = [
        evaluate_rule(rows_by_rank, replayable_slots, rows, feature_set)
        for feature_set in feature_combinations(features, max_features)
    ]
    rules.sort(
        key=lambda row: (
            0
            if int_value(row, "correct_slots") + int_value(row, "false_slots") > 0
            else 1,
            int_value(row, "false_slots"),
            -int_value(row, "correct_slots"),
            int_value(row, "unknown_slots"),
            int_value(row, "feature_count"),
            str(row.get("feature_set", "")),
        )
    )
    for index, row in enumerate(rules, start=1):
        row["rank"] = index

    false_free = [
        row
        for row in rules
        if int_value(row, "correct_slots") > 0 and int_value(row, "false_slots") == 0
    ]
    best_false_free = false_free[0] if false_free else {}
    conflicted = [
        row
        for row in rules
        if int_value(row, "correct_slots") > 0 and int_value(row, "false_slots") > 0
    ]
    best_conflicted = conflicted[0] if conflicted else {}
    best_feature_set = tuple(
        part for part in str(best_false_free.get("feature_set", "")).split("+") if part
    )
    enriched_slots: list[dict[str, object]] = []
    for slot in slots:
        row = dict(slot)
        row.update(
            {
                "best_split_feature_set": "+".join(best_feature_set),
                "best_split_context": "",
                "best_split_predicted_low": "",
                "best_split_predicted_byte": "",
                "best_split_verdict": "",
            }
        )
        if best_feature_set and slot.get("state") == "replayable_unknown":
            context, predicted_byte, verdict = prediction_for_slot(rows_by_rank, rows, slot, best_feature_set)
            row["best_split_context"] = context
            row["best_split_predicted_byte"] = predicted_byte
            row["best_split_predicted_low"] = predicted_byte[1:] if predicted_byte else ""
            row["best_split_verdict"] = verdict
        enriched_slots.append(row)

    summary = {
        "scope": "total",
        "selected_high_slots": len(rows),
        "features": len(features),
        "feature_sets": len(rules),
        "replayable_unknown_slots": len(replayable_slots),
        "target_known_slots": sum(1 for slot in slots if slot.get("state") == "target_already_known"),
        "blocked_prerequisite_slots": sum(1 for slot in slots if slot.get("state") == "blocked_prerequisites"),
        "false_free_split_sets": len(false_free),
        "best_false_free_split_feature_set": best_false_free.get("feature_set", ""),
        "best_false_free_split_correct_slots": best_false_free.get("correct_slots", 0),
        "best_false_free_split_unknown_slots": best_false_free.get("unknown_slots", 0),
        "best_conflicted_feature_set": best_conflicted.get("feature_set", ""),
        "best_conflicted_correct_slots": best_conflicted.get("correct_slots", 0),
        "best_conflicted_false_slots": best_conflicted.get("false_slots", 0),
        "promotion_candidate_bytes": best_false_free.get("correct_slots", 0),
        "promotion_ready_bytes": 0,
        "issue_rows": len(issues) + slot_issue_rows,
    }
    return summary, enriched_slots, rules


def render_table(rows: list[dict[str, object]], fields: list[str], limit: int = 240) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, object],
    slots: list[dict[str, object]],
    rules: list[dict[str, object]],
    title: str,
) -> str:
    data_json = json.dumps({"summary": summary, "slots": slots, "rules": rules}, indent=2, sort_keys=True)
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body {{ margin: 2rem; background: #111416; color: #edf5f4; font: 14px/1.45 system-ui, sans-serif; }}
table {{ border-collapse: collapse; width: 100%; min-width: 1600px; }}
th, td {{ border: 1px solid #31424a; padding: .45rem .55rem; vertical-align: top; }}
th {{ color: #9dafb5; background: #172023; text-align: left; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: .75rem; margin: 1rem 0; }}
.box {{ border: 1px solid #31424a; background: #172023; padding: .75rem; }}
.num {{ font-size: 1.35rem; font-weight: 750; }}
.muted {{ color: #9dafb5; }}
.panel {{ overflow-x: auto; margin-top: 1rem; }}
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<div class="grid">
  <div class="box"><div class="num">{summary['replayable_unknown_slots']}</div><div class="muted">replayable unknown slots</div></div>
  <div class="box"><div class="num">{summary['false_free_split_sets']}</div><div class="muted">false-free split sets</div></div>
  <div class="box"><div class="num">{summary['best_false_free_split_correct_slots']}</div><div class="muted">best false-free correct slots</div></div>
  <div class="box"><div class="num">{summary['best_false_free_split_unknown_slots']}</div><div class="muted">best false-free unknown slots</div></div>
  <div class="box"><div class="num">{summary['promotion_candidate_bytes']}</div><div class="muted">promotion candidate bytes</div></div>
</div>
<div class="panel"><h2>Sequence slots</h2>{render_table(slots, SLOT_FIELDNAMES)}</div>
<div class="panel"><h2>Split rules</h2>{render_table(rules, RULE_FIELDNAMES)}</div>
<script type="application/json" id="mixed-value-sequence-low-split-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe low splits for replayable mixed-value sequence slots.")
    parser.add_argument("--input-rows", type=Path, default=DEFAULT_INPUT_ROWS)
    parser.add_argument("--selected-rows", type=Path, default=DEFAULT_SELECTED_ROWS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--replay-fixtures", type=Path, default=DEFAULT_REPLAY_FIXTURES)
    parser.add_argument("--source-profile-rows", type=Path, default=DEFAULT_SOURCE_PROFILE_ROWS)
    parser.add_argument("--max-features", type=int, default=2)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Mixed Value Sequence Low Split")
    args = parser.parse_args()

    summary, slots, rules = build(
        read_csv(args.selected_rows),
        read_csv(args.input_rows),
        read_csv(args.fixtures),
        read_csv(args.replay_fixtures),
        read_csv(args.source_profile_rows),
        max_features=args.max_features,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "slots.csv", SLOT_FIELDNAMES, slots)
    write_csv(args.output / "rules.csv", RULE_FIELDNAMES, rules)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, slots, rules, args.title))

    print(f"False-free split sets: {summary['false_free_split_sets']}")
    print(
        f"Best false-free split: {summary['best_false_free_split_feature_set']} "
        f"{summary['best_false_free_split_correct_slots']} correct, "
        f"{summary['best_false_free_split_unknown_slots']} unknown"
    )
    print(f"Promotion candidate bytes: {summary['promotion_candidate_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
