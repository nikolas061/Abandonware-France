#!/usr/bin/env python3
"""Probe previous-low copy rules for residual mixed-value sequence slots."""

from __future__ import annotations

import argparse
import html
import itertools
import json
from pathlib import Path

from lolg_tex_micro_mixed_value_payload_predictor_probe import (
    DEFAULT_FIXTURES,
    int_value,
    ratio,
    read_csv,
    write_csv,
)
from lolg_tex_micro_mixed_value_payload_sequence_candidate_review import (
    DEFAULT_INPUT_ROWS,
    DEFAULT_SELECTED_ROWS,
    context_for,
    enriched_selected_rows,
)
from lolg_tex_micro_mixed_value_payload_sequence_promoted_generalization_probe import (
    SLOT_FIELDNAMES as BASE_SLOT_FIELDNAMES,
    build_slots,
)
from lolg_tex_micro_mixed_value_payload_sequence_state_probe import build_entries


DEFAULT_REPLAY_FIXTURES = Path(
    "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_promoted_replay/fixtures.csv"
)
DEFAULT_OUTPUT = Path("output/tex_micro_mixed_value_payload_sequence_low_copy")

FEATURES = [
    "target_high",
    "prev1_low_eq_dominant_low",
    "run_len_bucket",
    "run_len_mod4",
    "head_offset",
    "pos4",
    "pos8",
    "pos16",
    "signal",
    "control",
    "dominant",
    "high_down_one",
]
SOURCES = ["prev1"]

SUMMARY_FIELDNAMES = [
    "scope",
    "selected_high_slots",
    "training_entries",
    "features",
    "feature_sets",
    "replayable_unknown_slots",
    "target_known_slots",
    "blocked_prerequisite_slots",
    "false_free_copy_sets",
    "best_copy_source",
    "best_copy_feature_set",
    "best_training_correct_slots",
    "best_training_false_slots",
    "best_correct_slots",
    "best_false_slots",
    "best_unknown_slots",
    "best_predicted_values",
    "best_sample_correct_slots",
    "best_sample_false_slots",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

RULE_FIELDNAMES = [
    "rank",
    "copy_source",
    "feature_set",
    "feature_count",
    "training_correct_slots",
    "training_false_slots",
    "training_slots",
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
    "best_copy_source",
    "best_copy_feature_set",
    "best_copy_context",
    "best_copy_support",
    "best_copy_predicted_byte",
    "best_copy_verdict",
    "best_split_feature_set",
    "best_split_context",
    "best_split_predicted_low",
    "best_split_predicted_byte",
    "best_split_verdict",
]


def feature_combinations(features: list[str], max_features: int) -> list[tuple[str, ...]]:
    output: list[tuple[str, ...]] = []
    for size in range(1, max_features + 1):
        output.extend(itertools.combinations(features, size))
    return output


def low_token(row: dict[str, object], source: str) -> str:
    value = str(row.get(f"{source}_low", ""))
    return "" if value == "START" else value


def copy_prediction(row: dict[str, object], source: str) -> str:
    low = low_token(row, source)
    high = str(row.get("high_prediction", row.get("target_high", "")))
    return f"{high}{low}" if high and low else ""


def high_down_one(row: dict[str, object], target_high: str) -> str:
    prev = str(row.get("prev1_high", ""))
    if prev in {"", "START"} or not target_high:
        return "False"
    return str(((int(target_high, 16) - int(prev, 16) + 16) & 0x0F) == 15)


def enrich_entry(row: dict[str, object], target_high: str | None = None) -> dict[str, object]:
    enriched = dict(row)
    high = target_high or str(row.get("high", ""))
    dominant = str(row.get("dominant", ""))
    offset = int_value(row, "offset")
    enriched["target_high"] = high
    enriched["prev1_low_eq_dominant_low"] = str(str(row.get("prev1_low", "")) == dominant[-1:])
    enriched["head_offset"] = str(offset) if offset < 8 else "body"
    enriched["high_down_one"] = high_down_one(row, high)
    for source in SOURCES:
        prediction = copy_prediction({**enriched, "high_prediction": high}, source)
        enriched[f"{source}_copy_prediction"] = prediction
        enriched[f"{source}_copy_correct"] = str(prediction == str(row.get("byte", ""))) if prediction else ""
    return enriched


def support_for_context(
    training_rows: list[dict[str, object]],
    source: str,
    feature_set: tuple[str, ...],
    target_row: dict[str, object],
) -> tuple[int, int, int]:
    context = context_for(target_row, feature_set)
    correct = 0
    false = 0
    total = 0
    target_row_index = int_value(target_row, "row_index")
    for row in training_rows:
        if int_value(row, "row_index") == target_row_index:
            continue
        if context_for(row, feature_set) != context:
            continue
        prediction = str(row.get(f"{source}_copy_prediction", ""))
        if not prediction:
            continue
        total += 1
        if prediction == str(row.get("byte", "")):
            correct += 1
        else:
            false += 1
    return correct, false, total


def sample_label(slot: dict[str, object], predicted: str = "") -> str:
    label = f"{slot.get('row_index')}:{slot.get('frontier_id')}:{slot.get('offset')}"
    return f"{label}={predicted}" if predicted else label


def evaluate_rule(
    rows_by_rank: dict[str, dict[str, object]],
    training_rows: list[dict[str, object]],
    replayable_slots: list[dict[str, object]],
    source: str,
    feature_set: tuple[str, ...],
) -> dict[str, object]:
    correct = 0
    false = 0
    unknown = 0
    training_correct = 0
    training_false = 0
    training_total = 0
    predicted_values: dict[str, int] = {}
    sample_correct: list[str] = []
    sample_false: list[str] = []
    sample_unknown: list[str] = []
    for slot in replayable_slots:
        row = rows_by_rank.get(str(slot.get("rank", "")), {})
        support_correct, support_false, support_total = support_for_context(
            training_rows,
            source,
            feature_set,
            row,
        )
        training_correct += support_correct
        training_false += support_false
        training_total += support_total
        prediction = copy_prediction(row, source)
        if support_correct <= 0 or support_false > 0 or not prediction:
            unknown += 1
            if len(sample_unknown) < 6:
                sample_unknown.append(sample_label(slot))
            continue
        predicted_values[prediction] = predicted_values.get(prediction, 0) + 1
        if prediction == str(row.get("byte", "")):
            correct += 1
            if len(sample_correct) < 6:
                sample_correct.append(sample_label(slot, prediction))
        else:
            false += 1
            if len(sample_false) < 6:
                sample_false.append(f"{sample_label(slot, prediction)}!={row.get('byte', '')}")

    predicted = correct + false
    if predicted == 0:
        verdict = "no_copy_prediction"
    elif false == 0:
        verdict = "false_free_copy_candidate"
    elif correct > 0:
        verdict = "copy_conflict"
    else:
        verdict = "copy_reject"
    return {
        "rank": 0,
        "copy_source": source,
        "feature_set": "+".join(feature_set),
        "feature_count": len(feature_set),
        "training_correct_slots": training_correct,
        "training_false_slots": training_false,
        "training_slots": training_total,
        "replayable_unknown_slots": len(replayable_slots),
        "correct_slots": correct,
        "false_slots": false,
        "unknown_slots": unknown,
        "precision": ratio(correct, predicted),
        "predicted_values": "|".join(f"{value}:{count}" for value, count in sorted(predicted_values.items())),
        "sample_correct_slots": "|".join(sample_correct),
        "sample_false_slots": "|".join(sample_false),
        "sample_unknown_slots": "|".join(sample_unknown),
        "verdict": verdict,
    }


def build(
    selected_rows: list[dict[str, str]],
    input_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    replay_rows: list[dict[str, str]],
    *,
    max_features: int,
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    entries, issues = build_entries(input_rows, fixture_rows)
    training_rows = [enrich_entry(row) for row in entries]
    selected = enriched_selected_rows(selected_rows, input_rows)
    slots, _known_by_fixture, slot_issue_rows = build_slots(selected, replay_rows)
    entry_by_slot = {
        (int_value(entry, "row_index"), int_value(entry, "offset")): entry
        for entry in entries
    }
    rows_by_rank: dict[str, dict[str, object]] = {}
    missing_target_entries = 0
    for row in selected:
        entry = entry_by_slot.get((int_value(row, "row_index"), int_value(row, "offset")))
        if entry is None:
            rows_by_rank[str(row.get("rank", ""))] = enrich_entry(row, str(row.get("high_prediction", "")))
            missing_target_entries += 1
        else:
            rows_by_rank[str(row.get("rank", ""))] = {
                **enrich_entry(entry, str(row.get("high_prediction", ""))),
                **row,
            }
    replayable_slots = [slot for slot in slots if slot.get("state") == "replayable_unknown"]
    features = [
        feature
        for feature in FEATURES
        if all(feature in row for row in training_rows)
        and all(feature in row for row in rows_by_rank.values())
    ]
    feature_sets = feature_combinations(features, max_features)
    rules = [
        evaluate_rule(rows_by_rank, training_rows, replayable_slots, source, feature_set)
        for source in SOURCES
        for feature_set in feature_sets
    ]
    rules.sort(
        key=lambda row: (
            0 if int_value(row, "correct_slots") + int_value(row, "false_slots") > 0 else 1,
            int_value(row, "false_slots"),
            -int_value(row, "correct_slots"),
            int_value(row, "unknown_slots"),
            -int_value(row, "training_correct_slots"),
            int_value(row, "feature_count"),
            str(row.get("feature_set", "")),
        )
    )
    for index, row in enumerate(rules, start=1):
        row["rank"] = index

    false_free = [
        row for row in rules if int_value(row, "correct_slots") > 0 and int_value(row, "false_slots") == 0
    ]
    best = false_free[0] if false_free else {}
    best_source = str(best.get("copy_source", ""))
    best_feature_set = tuple(part for part in str(best.get("feature_set", "")).split("+") if part)
    enriched_slots: list[dict[str, object]] = []
    promotion_candidates = 0
    for slot in slots:
        row = dict(slot)
        row.update(
            {
                "best_copy_source": best_source,
                "best_copy_feature_set": "+".join(best_feature_set),
                "best_copy_context": "",
                "best_copy_support": "",
                "best_copy_predicted_byte": "",
                "best_copy_verdict": "",
                "best_split_feature_set": "+".join(best_feature_set),
                "best_split_context": "",
                "best_split_predicted_low": "",
                "best_split_predicted_byte": "",
                "best_split_verdict": "",
            }
        )
        if best_source and best_feature_set and slot.get("state") == "replayable_unknown":
            target = rows_by_rank.get(str(slot.get("rank", "")), {})
            support = support_for_context(training_rows, best_source, best_feature_set, target)
            prediction = copy_prediction(target, best_source)
            verdict = "unknown"
            if support[0] > 0 and support[1] == 0 and prediction:
                verdict = "correct" if prediction == str(target.get("byte", "")) else "false"
            row["best_copy_context"] = "|".join(context_for(target, best_feature_set))
            row["best_copy_support"] = f"{support[0]}/{support[1]}/{support[2]}"
            row["best_copy_predicted_byte"] = prediction if verdict != "unknown" else ""
            row["best_copy_verdict"] = verdict
            row["best_split_context"] = row["best_copy_context"]
            row["best_split_predicted_byte"] = row["best_copy_predicted_byte"]
            row["best_split_predicted_low"] = prediction[1:] if prediction and verdict != "unknown" else ""
            row["best_split_verdict"] = verdict
            if verdict == "correct":
                promotion_candidates += 1
        enriched_slots.append(row)

    summary = {
        "scope": "total",
        "selected_high_slots": len(selected),
        "training_entries": len(training_rows),
        "features": len(features),
        "feature_sets": len(feature_sets) * len(SOURCES),
        "replayable_unknown_slots": len(replayable_slots),
        "target_known_slots": sum(1 for slot in slots if slot.get("state") == "target_already_known"),
        "blocked_prerequisite_slots": sum(1 for slot in slots if slot.get("state") == "blocked_prerequisites"),
        "false_free_copy_sets": len(false_free),
        "best_copy_source": best_source,
        "best_copy_feature_set": best.get("feature_set", ""),
        "best_training_correct_slots": best.get("training_correct_slots", 0),
        "best_training_false_slots": best.get("training_false_slots", 0),
        "best_correct_slots": best.get("correct_slots", 0),
        "best_false_slots": best.get("false_slots", 0),
        "best_unknown_slots": best.get("unknown_slots", 0),
        "best_predicted_values": best.get("predicted_values", ""),
        "best_sample_correct_slots": best.get("sample_correct_slots", ""),
        "best_sample_false_slots": best.get("sample_false_slots", ""),
        "promotion_candidate_bytes": promotion_candidates,
        "promotion_ready_bytes": 0,
        "issue_rows": len(issues) + slot_issue_rows + missing_target_entries,
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
table {{ border-collapse: collapse; width: 100%; min-width: 1650px; }}
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
  <div class="box"><div class="num">{summary['false_free_copy_sets']}</div><div class="muted">false-free copy sets</div></div>
  <div class="box"><div class="num">{summary['best_training_correct_slots']}/{summary['best_training_false_slots']}</div><div class="muted">best training correct/false</div></div>
  <div class="box"><div class="num">{summary['best_correct_slots']}/{summary['best_false_slots']}</div><div class="muted">best replay correct/false</div></div>
  <div class="box"><div class="num">{summary['promotion_candidate_bytes']}</div><div class="muted">promotion candidates</div></div>
</div>
<div class="panel"><h2>Sequence slots</h2>{render_table(slots, SLOT_FIELDNAMES)}</div>
<div class="panel"><h2>Low-copy rules</h2>{render_table(rules, RULE_FIELDNAMES)}</div>
<script type="application/json" id="mixed-value-sequence-low-copy-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe previous-low copy rules for mixed-value sequence slots.")
    parser.add_argument("--input-rows", type=Path, default=DEFAULT_INPUT_ROWS)
    parser.add_argument("--selected-rows", type=Path, default=DEFAULT_SELECTED_ROWS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--replay-fixtures", type=Path, default=DEFAULT_REPLAY_FIXTURES)
    parser.add_argument("--max-features", type=int, default=4)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Mixed Value Sequence Low Copy")
    args = parser.parse_args()

    summary, slots, rules = build(
        read_csv(args.selected_rows),
        read_csv(args.input_rows),
        read_csv(args.fixtures),
        read_csv(args.replay_fixtures),
        max_features=args.max_features,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "slots.csv", SLOT_FIELDNAMES, slots)
    write_csv(args.output / "rules.csv", RULE_FIELDNAMES, rules)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, slots, rules, args.title))

    print(f"False-free copy sets: {summary['false_free_copy_sets']}")
    print(
        f"Best copy: {summary['best_copy_source']} {summary['best_copy_feature_set']} "
        f"{summary['best_correct_slots']} correct, {summary['best_unknown_slots']} unknown"
    )
    print(f"Promotion candidate bytes: {summary['promotion_candidate_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
