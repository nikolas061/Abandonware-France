#!/usr/bin/env python3
"""Probe previous-byte transform predictors for residual mixed-value sequence slots."""

from __future__ import annotations

import argparse
import html
import itertools
import json
from collections import Counter, defaultdict
from pathlib import Path

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
from lolg_tex_micro_mixed_value_payload_sequence_state_probe import build_entries


DEFAULT_OUTPUT = Path("output/tex_micro_mixed_value_payload_sequence_transform")

FEATURES = [
    "prev1",
    "prev2",
    "prev1_low",
    "prev1_high",
    "prev_delta_bucket",
    "prev_delta_pair",
    "prev_shape",
    "run_byte",
    "run_high",
    "run_len_bucket",
    "run_len_mod4",
    "pos4",
    "pos8",
    "pos16",
    "tail4",
    "signal",
    "control",
    "dominant",
]

TRANSFORM_TARGETS = [
    "low_delta_prev1",
    "low_delta_prev2",
    "low_delta_prev3",
    "low_signed_delta_prev1",
    "low_signed_delta_prev2",
    "low_signed_delta_prev3",
    "low_xor_prev1",
    "low_xor_prev2",
    "low_xor_prev3",
    "byte_delta_prev1",
    "byte_delta_prev2",
    "byte_delta_prev3",
]

SUMMARY_FIELDNAMES = [
    "scope",
    "training_scope",
    "selected_high_slots",
    "training_entries",
    "features",
    "transform_targets",
    "feature_sets",
    "replayable_unknown_slots",
    "target_known_slots",
    "blocked_prerequisite_slots",
    "false_free_transform_sets",
    "best_transform_target",
    "best_transform_feature_set",
    "best_correct_slots",
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
    "transform_target",
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
    "best_transform_target",
    "best_transform_feature_set",
    "best_transform_context",
    "best_transform_value",
    "best_transform_predicted_byte",
    "best_transform_verdict",
    "best_split_feature_set",
    "best_split_context",
    "best_split_predicted_low",
    "best_split_predicted_byte",
    "best_split_verdict",
]


def parse_hex_byte(text: object) -> int | None:
    value = str(text)
    if not value or value == "START":
        return None
    try:
        return int(value, 16)
    except ValueError:
        return None


def low_value(row: dict[str, object]) -> int | None:
    value = parse_hex_byte(row.get("low", ""))
    return None if value is None else value & 0x0F


def byte_value(row: dict[str, object]) -> int | None:
    return parse_hex_byte(row.get("byte", ""))


def previous_byte(row: dict[str, object], index: int) -> int | None:
    return parse_hex_byte(row.get(f"prev{index}", ""))


def transform_previous_index(transform: str) -> int:
    if transform.endswith("prev1"):
        return 1
    if transform.endswith("prev2"):
        return 2
    if transform.endswith("prev3"):
        return 3
    return 0


def signed_byte_delta(left: int, right: int) -> int:
    return ((left - right + 128) & 0xFF) - 128


def signed_low_delta(left: int, right: int) -> int:
    return ((left - right + 8) & 0x0F) - 8


def transform_value(row: dict[str, object], transform: str) -> str:
    previous = previous_byte(row, transform_previous_index(transform))
    target_low = low_value(row)
    target_byte = byte_value(row)
    if previous is None or target_low is None or target_byte is None:
        return ""
    previous_low = previous & 0x0F
    if transform.startswith("low_delta_"):
        return f"{(target_low - previous_low) & 0x0F:x}"
    if transform.startswith("low_signed_delta_"):
        return str(signed_low_delta(target_low, previous_low))
    if transform.startswith("low_xor_"):
        return f"{target_low ^ previous_low:x}"
    if transform.startswith("byte_delta_"):
        return str(signed_byte_delta(target_byte, previous))
    return ""


def predicted_byte(row: dict[str, object], transform: str, value: str) -> str:
    previous = previous_byte(row, transform_previous_index(transform))
    if previous is None or not value:
        return ""
    high = parse_hex_byte(row.get("high_prediction", ""))
    if high is None:
        return ""
    previous_low = previous & 0x0F
    try:
        if transform.startswith("low_delta_"):
            return f"{high:x}{(previous_low + int(value, 16)) & 0x0F:x}"
        if transform.startswith("low_signed_delta_"):
            return f"{high:x}{(previous_low + int(value)) & 0x0F:x}"
        if transform.startswith("low_xor_"):
            return f"{high:x}{previous_low ^ int(value, 16):x}"
        if transform.startswith("byte_delta_"):
            return f"{(previous + int(value)) & 0xFF:02x}"
    except ValueError:
        return ""
    return ""


def feature_combinations(features: list[str], max_features: int) -> list[tuple[str, ...]]:
    output: list[tuple[str, ...]] = []
    for size in range(1, max_features + 1):
        output.extend(itertools.combinations(features, size))
    return output


def add_transform_values(rows: list[dict[str, object]]) -> None:
    for row in rows:
        for transform in TRANSFORM_TARGETS:
            row[transform] = transform_value(row, transform)


def training_counts(
    rows: list[dict[str, object]],
    feature_set: tuple[str, ...],
    transform: str,
) -> tuple[dict[tuple[str, ...], Counter[str]], dict[tuple[int, tuple[str, ...]], Counter[str]]]:
    all_counts: dict[tuple[str, ...], Counter[str]] = defaultdict(Counter)
    row_counts: dict[tuple[int, tuple[str, ...]], Counter[str]] = defaultdict(Counter)
    for row in rows:
        value = str(row.get(transform, ""))
        if not value:
            continue
        context = context_for(row, feature_set)
        all_counts[context][value] += 1
        row_counts[(int_value(row, "row_index"), context)][value] += 1
    return all_counts, row_counts


def sample_label(slot: dict[str, object], predicted: str = "") -> str:
    label = f"{slot.get('row_index')}:{slot.get('frontier_id')}:{slot.get('offset')}"
    return f"{label}={predicted}" if predicted else label


def prediction_for_slot(
    rows_by_rank: dict[str, dict[str, object]],
    rows: list[dict[str, object]],
    slot: dict[str, object],
    transform: str,
    feature_set: tuple[str, ...],
) -> tuple[str, str, str, str]:
    row = rows_by_rank.get(str(slot.get("rank", "")), {})
    all_counts, row_counts = training_counts(rows, feature_set, transform)
    context = context_for(row, feature_set)
    counts = all_counts[context].copy()
    counts.subtract(row_counts[(int_value(row, "row_index"), context)])
    counts += Counter()
    value = strict_prediction(counts)
    if value is None:
        return "|".join(context), "", "", "unknown"
    output = predicted_byte(row, transform, value)
    if not output:
        return "|".join(context), value, "", "unknown"
    verdict = "correct" if output == str(row.get("byte", "")) else "false"
    return "|".join(context), value, output, verdict


def evaluate_rule(
    rows_by_rank: dict[str, dict[str, object]],
    replayable_slots: list[dict[str, object]],
    rows: list[dict[str, object]],
    transform: str,
    feature_set: tuple[str, ...],
) -> dict[str, object]:
    all_counts, row_counts = training_counts(rows, feature_set, transform)
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
        value = strict_prediction(counts)
        if value is None:
            unknown += 1
            if len(sample_unknown) < 6:
                sample_unknown.append(sample_label(slot))
            continue
        output = predicted_byte(row, transform, value)
        if not output:
            unknown += 1
            if len(sample_unknown) < 6:
                sample_unknown.append(sample_label(slot))
            continue
        predicted_values[output] += 1
        if output == str(row.get("byte", "")):
            correct += 1
            if len(sample_correct) < 6:
                sample_correct.append(sample_label(slot, output))
        else:
            false += 1
            if len(sample_false) < 6:
                sample_false.append(f"{sample_label(slot, output)}!={row.get('byte', '')}")

    predicted = correct + false
    if predicted == 0:
        verdict = "no_transform_prediction"
    elif false == 0:
        verdict = "false_free_transform_candidate"
    elif correct > 0:
        verdict = "transform_conflict"
    else:
        verdict = "transform_reject"
    return {
        "rank": 0,
        "transform_target": transform,
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


def build(
    selected_rows: list[dict[str, str]],
    input_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    replay_rows: list[dict[str, str]],
    *,
    training_scope: str,
    max_features: int,
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    rows: list[dict[str, object]] = enriched_selected_rows(selected_rows, input_rows)
    add_transform_values(rows)
    slots, _known_by_fixture, issue_rows = build_slots(rows, replay_rows)
    replayable_slots = [slot for slot in slots if slot.get("state") == "replayable_unknown"]
    rows_by_rank = {str(row.get("rank", "")): row for row in rows}
    training_rows = rows
    if training_scope == "corpus":
        entries, entry_issues = build_entries(input_rows, fixture_rows)
        issue_rows += len(entry_issues)
        add_transform_values(entries)
        entry_by_slot = {
            (int(entry["row_index"]), int(entry["offset"])): entry
            for entry in entries
        }
        training_rows = entries
        merged_by_rank: dict[str, dict[str, object]] = {}
        for row in rows:
            key = (int_value(row, "row_index"), int_value(row, "offset"))
            entry = entry_by_slot.get(key)
            if entry is None:
                issue_rows += 1
                merged_by_rank[str(row.get("rank", ""))] = row
            else:
                merged_by_rank[str(row.get("rank", ""))] = {**entry, **row}
        rows_by_rank = merged_by_rank
    features = [
        feature
        for feature in FEATURES
        if all(feature in row for row in training_rows)
        and all(feature in row for row in rows_by_rank.values())
    ]
    feature_sets = feature_combinations(features, max_features)
    rules = [
        evaluate_rule(rows_by_rank, replayable_slots, training_rows, transform, feature_set)
        for transform in TRANSFORM_TARGETS
        for feature_set in feature_sets
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
            str(row.get("transform_target", "")),
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
    false_free.sort(
        key=lambda row: (
            -int_value(row, "correct_slots"),
            int_value(row, "unknown_slots"),
            int_value(row, "feature_count"),
            str(row.get("transform_target", "")),
            str(row.get("feature_set", "")),
        )
    )
    best_false_free = false_free[0] if false_free else {}
    best_transform = str(best_false_free.get("transform_target", ""))
    best_feature_set = tuple(
        part for part in str(best_false_free.get("feature_set", "")).split("+") if part
    )

    enriched_slots: list[dict[str, object]] = []
    promotion_candidates = 0
    for slot in slots:
        row = dict(slot)
        row.update(
            {
                "best_transform_target": best_transform,
                "best_transform_feature_set": "+".join(best_feature_set),
                "best_transform_context": "",
                "best_transform_value": "",
                "best_transform_predicted_byte": "",
                "best_transform_verdict": "",
                "best_split_feature_set": "+".join(best_feature_set),
                "best_split_context": "",
                "best_split_predicted_low": "",
                "best_split_predicted_byte": "",
                "best_split_verdict": "",
            }
        )
        if best_transform and best_feature_set and slot.get("state") == "replayable_unknown":
            context, value, output, verdict = prediction_for_slot(
                rows_by_rank,
                training_rows,
                slot,
                best_transform,
                best_feature_set,
            )
            row["best_transform_context"] = context
            row["best_transform_value"] = value
            row["best_transform_predicted_byte"] = output
            row["best_transform_verdict"] = verdict
            row["best_split_context"] = context
            row["best_split_predicted_byte"] = output
            row["best_split_predicted_low"] = output[1:] if output else ""
            row["best_split_verdict"] = verdict
            if verdict == "correct":
                promotion_candidates += 1
        enriched_slots.append(row)

    summary = {
        "scope": "total",
        "training_scope": training_scope,
        "selected_high_slots": len(rows),
        "training_entries": len(training_rows),
        "features": len(features),
        "transform_targets": len(TRANSFORM_TARGETS),
        "feature_sets": len(feature_sets) * len(TRANSFORM_TARGETS),
        "replayable_unknown_slots": len(replayable_slots),
        "target_known_slots": sum(1 for slot in slots if slot.get("state") == "target_already_known"),
        "blocked_prerequisite_slots": sum(1 for slot in slots if slot.get("state") == "blocked_prerequisites"),
        "false_free_transform_sets": len(false_free),
        "best_transform_target": best_transform,
        "best_transform_feature_set": best_false_free.get("feature_set", ""),
        "best_correct_slots": best_false_free.get("correct_slots", 0),
        "best_unknown_slots": best_false_free.get("unknown_slots", 0),
        "best_predicted_values": best_false_free.get("predicted_values", ""),
        "best_sample_correct_slots": best_false_free.get("sample_correct_slots", ""),
        "best_sample_false_slots": best_false_free.get("sample_false_slots", ""),
        "promotion_candidate_bytes": promotion_candidates,
        "promotion_ready_bytes": 0,
        "issue_rows": issue_rows,
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
table {{ border-collapse: collapse; width: 100%; min-width: 1700px; }}
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
  <div class="box"><div class="num">{summary['false_free_transform_sets']}</div><div class="muted">false-free transform sets</div></div>
  <div class="box"><div class="num">{summary['best_correct_slots']}</div><div class="muted">best correct slots</div></div>
  <div class="box"><div class="num">{summary['best_unknown_slots']}</div><div class="muted">best unknown slots</div></div>
  <div class="box"><div class="num">{summary['promotion_candidate_bytes']}</div><div class="muted">promotion candidates</div></div>
</div>
<div class="panel"><h2>Sequence slots</h2>{render_table(slots, SLOT_FIELDNAMES)}</div>
<div class="panel"><h2>Transform rules</h2>{render_table(rules, RULE_FIELDNAMES)}</div>
<script type="application/json" id="mixed-value-sequence-transform-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe previous-byte transforms for mixed-value sequence slots.")
    parser.add_argument("--input-rows", type=Path, default=DEFAULT_INPUT_ROWS)
    parser.add_argument("--selected-rows", type=Path, default=DEFAULT_SELECTED_ROWS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--replay-fixtures", type=Path, default=DEFAULT_REPLAY_FIXTURES)
    parser.add_argument("--training-scope", choices=["selected", "corpus"], default="selected")
    parser.add_argument("--max-features", type=int, default=3)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Mixed Value Sequence Transform")
    args = parser.parse_args()

    summary, slots, rules = build(
        read_csv(args.selected_rows),
        read_csv(args.input_rows),
        read_csv(args.fixtures),
        read_csv(args.replay_fixtures),
        training_scope=args.training_scope,
        max_features=args.max_features,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "slots.csv", SLOT_FIELDNAMES, slots)
    write_csv(args.output / "rules.csv", RULE_FIELDNAMES, rules)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, slots, rules, args.title))

    print(f"False-free transform sets: {summary['false_free_transform_sets']}")
    print(
        f"Best transform: {summary['best_transform_target']} "
        f"{summary['best_transform_feature_set']} "
        f"{summary['best_correct_slots']} correct, {summary['best_unknown_slots']} unknown"
    )
    print(f"Promotion candidate bytes: {summary['promotion_candidate_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
