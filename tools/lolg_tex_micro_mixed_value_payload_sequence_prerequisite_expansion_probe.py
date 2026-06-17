#!/usr/bin/env python3
"""Probe prerequisite byte expansion for blocked mixed-value sequence slots."""

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
)
from lolg_tex_micro_mixed_value_payload_sequence_low_split_promoted_replay import (
    DEFAULT_OUTPUT as DEFAULT_LOW_SPLIT_PROMOTED_REPLAY_OUTPUT,
)
from lolg_tex_micro_mixed_value_payload_sequence_promoted_generalization_probe import build_slots
from lolg_tex_micro_mixed_value_payload_sequence_state_probe import (
    FEATURES as SEQUENCE_FEATURES,
    build_entries,
)


DEFAULT_REPLAY_FIXTURES = DEFAULT_LOW_SPLIT_PROMOTED_REPLAY_OUTPUT / "fixtures.csv"
DEFAULT_OUTPUT = Path("output/tex_micro_mixed_value_payload_sequence_prerequisite_expansion")

SUMMARY_FIELDNAMES = [
    "scope",
    "selected_high_slots",
    "blocked_sequence_slots",
    "prerequisite_slots",
    "unknown_prerequisite_slots",
    "features",
    "feature_sets",
    "false_free_rule_sets",
    "best_feature_set",
    "best_correct_slots",
    "best_unknown_slots",
    "union_candidate_slots",
    "union_conflict_slots",
    "unlocked_sequence_slots",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

RULE_FIELDNAMES = [
    "rank",
    "feature_set",
    "feature_count",
    "unknown_prerequisite_slots",
    "correct_slots",
    "false_slots",
    "unknown_slots",
    "precision",
    "predicted_values",
    "sample_correct_slots",
    "sample_false_slots",
    "verdict",
]

SLOT_FIELDNAMES = [
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
    "absolute_offset",
    "byte",
    "predicted_values",
    "rule_count",
    "sample_rules",
    "blocked_sequence_refs",
    "verdict",
]


def feature_combinations(features: list[str], max_features: int) -> list[tuple[str, ...]]:
    output: list[tuple[str, ...]] = []
    for size in range(1, max_features + 1):
        output.extend(itertools.combinations(features, size))
    return output


def context_for(entry: dict[str, object], feature_set: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(str(entry.get(feature, "")) for feature in feature_set)


def sample_label(entry: dict[str, object], predicted: str = "") -> str:
    label = f"{entry.get('row_index')}:{entry.get('frontier_id')}:{entry.get('offset')}"
    return f"{label}={predicted}" if predicted else label


def combined_feature_names(entries: list[dict[str, object]]) -> list[str]:
    names = [*SEQUENCE_FEATURES, *external_feature_names()]
    return list(dict.fromkeys(name for name in names if all(name in entry for entry in entries)))


def target_prerequisite_entries(
    entries: list[dict[str, object]],
    selected_rows: list[dict[str, str]],
    replay_rows: list[dict[str, str]],
) -> tuple[list[dict[str, object]], list[dict[str, object]], int]:
    entry_by_slot = {
        (int(entry["row_index"]), int(entry["offset"])): entry
        for entry in entries
    }
    sequence_slots, _known_by_fixture, issue_rows = build_slots(selected_rows, replay_rows)
    targets: dict[tuple[int, int], dict[str, object]] = {}
    refs: dict[tuple[int, int], list[str]] = defaultdict(list)
    for slot in sequence_slots:
        if slot.get("state") != "blocked_prerequisites":
            continue
        row_index = int_value(slot, "row_index")
        start = int_value(slot, "start")
        slot_ref = f"{slot.get('rank')}:{slot.get('offset')}"
        prerequisites = slot.get("prerequisite_offsets", "").split("|")
        known_values = slot.get("known_prerequisites", "").split("|")
        for absolute_text, known in zip(prerequisites, known_values):
            if not absolute_text or known == "1":
                continue
            relative = int(absolute_text) - start
            key = (row_index, relative)
            entry = entry_by_slot.get(key)
            if entry is None:
                continue
            targets[key] = entry
            refs[key].append(slot_ref)
    output = []
    for key, entry in sorted(targets.items()):
        row = dict(entry)
        row["blocked_sequence_refs"] = "|".join(refs[key])
        output.append(row)
    return sequence_slots, output, issue_rows


def evaluate_rule(
    targets: list[dict[str, object]],
    feature_set: tuple[str, ...],
) -> tuple[dict[str, object], dict[tuple[int, int], str]]:
    all_counts: dict[tuple[str, ...], Counter[str]] = defaultdict(Counter)
    row_counts: dict[tuple[int, tuple[str, ...]], Counter[str]] = defaultdict(Counter)
    for target in targets:
        context = context_for(target, feature_set)
        value = str(target.get("byte", ""))
        all_counts[context][value] += 1
        row_counts[(int(target["row_index"]), context)][value] += 1

    correct = 0
    false = 0
    unknown = 0
    predicted_values: Counter[str] = Counter()
    sample_correct: list[str] = []
    sample_false: list[str] = []
    predictions: dict[tuple[int, int], str] = {}
    for target in targets:
        context = context_for(target, feature_set)
        counts = all_counts[context].copy()
        counts.subtract(row_counts[(int(target["row_index"]), context)])
        counts += Counter()
        prediction = strict_prediction(counts)
        if prediction is None:
            unknown += 1
            continue
        predicted_values[prediction] += 1
        if prediction == str(target.get("byte", "")):
            correct += 1
            predictions[(int(target["row_index"]), int(target["offset"]))] = prediction
            if len(sample_correct) < 8:
                sample_correct.append(sample_label(target, prediction))
        else:
            false += 1
            if len(sample_false) < 8:
                sample_false.append(
                    f"{sample_label(target, prediction)}!={target.get('byte', '')}"
                )

    predicted = correct + false
    if predicted == 0:
        verdict = "no_prerequisite_prediction"
    elif false == 0:
        verdict = "false_free_prerequisite_candidate"
    elif correct > 0:
        verdict = "prerequisite_conflict"
    else:
        verdict = "prerequisite_reject"
    return (
        {
            "rank": 0,
            "feature_set": "+".join(feature_set),
            "feature_count": len(feature_set),
            "unknown_prerequisite_slots": len(targets),
            "correct_slots": correct,
            "false_slots": false,
            "unknown_slots": unknown,
            "precision": ratio(correct, predicted),
            "predicted_values": "|".join(
                f"{value}:{count}" for value, count in predicted_values.most_common()
            ),
            "sample_correct_slots": "|".join(sample_correct),
            "sample_false_slots": "|".join(sample_false),
            "verdict": verdict,
        },
        predictions,
    )


def currently_known(slot: dict[str, object], candidate_slots: set[tuple[int, int]]) -> bool:
    if slot.get("state") != "blocked_prerequisites":
        return True
    row_index = int_value(slot, "row_index")
    start = int_value(slot, "start")
    prerequisites = slot.get("prerequisite_offsets", "").split("|")
    known_values = slot.get("known_prerequisites", "").split("|")
    for absolute_text, known in zip(prerequisites, known_values):
        if not absolute_text:
            continue
        relative = int(absolute_text) - start
        if known != "1" and (row_index, relative) not in candidate_slots:
            return False
    return True


def build(
    input_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    replay_rows: list[dict[str, str]],
    selected_rows: list[dict[str, str]],
    source_profile_rows: list[dict[str, str]],
    *,
    max_features: int,
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    entries, issues = build_entries(input_rows, fixture_rows)
    issues.extend(add_external_features(entries, input_rows, source_profile_rows, fixture_rows, replay_rows))
    sequence_slots, targets, slot_issue_rows = target_prerequisite_entries(entries, selected_rows, replay_rows)
    features = combined_feature_names(entries)
    rules: list[dict[str, object]] = []
    slot_predictions: dict[tuple[int, int], list[tuple[str, str]]] = defaultdict(list)
    for feature_set in feature_combinations(features, max_features):
        rule, predictions = evaluate_rule(targets, feature_set)
        if int_value(rule, "correct_slots") > 0 and int_value(rule, "false_slots") == 0:
            rules.append(rule)
            feature_label = str(rule["feature_set"])
            for slot, prediction in predictions.items():
                slot_predictions[slot].append((prediction, feature_label))

    rules.sort(
        key=lambda row: (
            -int_value(row, "correct_slots"),
            int_value(row, "unknown_slots"),
            int_value(row, "feature_count"),
            str(row.get("feature_set", "")),
        )
    )
    for index, row in enumerate(rules, start=1):
        row["rank"] = index

    target_by_slot = {(int(row["row_index"]), int(row["offset"])): row for row in targets}
    slot_rows: list[dict[str, object]] = []
    conflict_slots = 0
    candidate_slots: set[tuple[int, int]] = set()
    for slot, predictions in sorted(slot_predictions.items()):
        values = sorted({prediction for prediction, _feature in predictions})
        target = target_by_slot[slot]
        if len(values) > 1:
            verdict = "conflicted_prerequisite_candidate"
            conflict_slots += 1
        else:
            verdict = "prerequisite_candidate"
            candidate_slots.add(slot)
        slot_rows.append(
            {
                "rank": len(slot_rows) + 1,
                "row_index": target.get("row_index", ""),
                "archive": target.get("archive", ""),
                "pcx_name": target.get("pcx_name", ""),
                "frontier_id": target.get("frontier_id", ""),
                "span_index": target.get("span_index", ""),
                "op_index": target.get("op_index", ""),
                "start": target.get("start", ""),
                "end": target.get("end", ""),
                "offset": target.get("offset", ""),
                "absolute_offset": int_value(target, "start") + int_value(target, "offset"),
                "byte": target.get("byte", ""),
                "predicted_values": "|".join(values),
                "rule_count": len(predictions),
                "sample_rules": "|".join(feature for _prediction, feature in predictions[:8]),
                "blocked_sequence_refs": target.get("blocked_sequence_refs", ""),
                "verdict": verdict,
            }
        )

    blocked_sequence_slots = [slot for slot in sequence_slots if slot.get("state") == "blocked_prerequisites"]
    unlocked_sequence_slots = sum(1 for slot in blocked_sequence_slots if currently_known(slot, candidate_slots))
    best = rules[0] if rules else {}
    summary = {
        "scope": "total",
        "selected_high_slots": len(sequence_slots),
        "blocked_sequence_slots": len(blocked_sequence_slots),
        "prerequisite_slots": len(
            {
                (int_value(slot, "row_index"), int(offset) - int_value(slot, "start"))
                for slot in blocked_sequence_slots
                for offset in slot.get("prerequisite_offsets", "").split("|")
                if offset
            }
        ),
        "unknown_prerequisite_slots": len(targets),
        "features": len(features),
        "feature_sets": len(feature_combinations(features, max_features)),
        "false_free_rule_sets": len(rules),
        "best_feature_set": best.get("feature_set", ""),
        "best_correct_slots": best.get("correct_slots", 0),
        "best_unknown_slots": best.get("unknown_slots", 0),
        "union_candidate_slots": len(slot_rows),
        "union_conflict_slots": conflict_slots,
        "unlocked_sequence_slots": unlocked_sequence_slots,
        "promotion_candidate_bytes": len(slot_rows) if conflict_slots == 0 else 0,
        "promotion_ready_bytes": 0,
        "issue_rows": len(issues) + slot_issue_rows,
    }
    return summary, rules, slot_rows


def render_table(rows: list[dict[str, object]], fields: list[str], limit: int = 240) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, object],
    rules: list[dict[str, object]],
    slots: list[dict[str, object]],
    title: str,
) -> str:
    data_json = json.dumps({"summary": summary, "rules": rules, "slots": slots}, indent=2, sort_keys=True)
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
  <div class="box"><div class="num">{summary['unknown_prerequisite_slots']}</div><div class="muted">unknown prerequisite slots</div></div>
  <div class="box"><div class="num">{summary['false_free_rule_sets']}</div><div class="muted">false-free rule sets</div></div>
  <div class="box"><div class="num">{summary['union_candidate_slots']}</div><div class="muted">union candidate slots</div></div>
  <div class="box"><div class="num">{summary['union_conflict_slots']}</div><div class="muted">union conflict slots</div></div>
  <div class="box"><div class="num">{summary['unlocked_sequence_slots']}</div><div class="muted">unlocked sequence slots</div></div>
</div>
<div class="panel"><h2>Prerequisite candidates</h2>{render_table(slots, SLOT_FIELDNAMES)}</div>
<div class="panel"><h2>False-free rules</h2>{render_table(rules, RULE_FIELDNAMES)}</div>
<script type="application/json" id="mixed-value-sequence-prerequisite-expansion-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe prerequisite expansion for mixed-value sequence slots.")
    parser.add_argument("--input-rows", type=Path, default=DEFAULT_INPUT_ROWS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--replay-fixtures", type=Path, default=DEFAULT_REPLAY_FIXTURES)
    parser.add_argument("--selected-rows", type=Path, default=DEFAULT_SELECTED_ROWS)
    parser.add_argument("--source-profile-rows", type=Path, default=DEFAULT_SOURCE_PROFILE_ROWS)
    parser.add_argument("--max-features", type=int, default=2)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Mixed Value Sequence Prerequisite Expansion")
    args = parser.parse_args()

    summary, rules, slots = build(
        read_csv(args.input_rows),
        read_csv(args.fixtures),
        read_csv(args.replay_fixtures),
        read_csv(args.selected_rows),
        read_csv(args.source_profile_rows),
        max_features=args.max_features,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "rules.csv", RULE_FIELDNAMES, rules)
    write_csv(args.output / "slots.csv", SLOT_FIELDNAMES, slots)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, rules, slots, args.title))

    print(f"Unknown prerequisite slots: {summary['unknown_prerequisite_slots']}")
    print(f"False-free rule sets: {summary['false_free_rule_sets']}")
    print(f"Union candidate slots: {summary['union_candidate_slots']}")
    print(f"Union conflicts: {summary['union_conflict_slots']}")
    print(f"Unlocked sequence slots: {summary['unlocked_sequence_slots']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
