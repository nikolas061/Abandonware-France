#!/usr/bin/env python3
"""Probe role/target transforms for residual mixed-value sequence prerequisites."""

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
    write_csv,
)
from lolg_tex_micro_mixed_value_payload_sequence_prerequisite_expansion_probe import render_table


DEFAULT_SEQUENCE_SLOTS = Path("output/tex_micro_mixed_value_payload_sequence_low_copy_generalization/slots.csv")
DEFAULT_OUTPUT = Path("output/tex_micro_mixed_value_payload_sequence_blocked_prerequisite_role_transform")

FEATURES = [
    "role",
    "target_offset_bucket",
    "target_pos4",
    "target_pos8",
    "target_pos16",
    "target_pos32",
    "pre_pos4",
    "pre_pos8",
    "pre_pos16",
    "pre_pos32",
    "len_bucket",
    "target_high",
    "target_low",
    "target_byte",
    "rule_type",
    "frontier_type",
    "opcode0",
    "opcode1",
]

TRANSFORM_TARGETS = ["byte", "pre_high", "pre_low"]

CURATED_FEATURE_SETS = [
    ("target_pos8", "target_pos32", "target_low", "rule_type"),
    ("target_pos4", "target_pos32", "target_low", "rule_type"),
    ("target_pos8", "pre_pos16", "target_low", "rule_type"),
    ("pre_pos16", "pre_pos32", "target_low", "opcode1"),
    ("pre_pos32", "len_bucket", "target_low", "opcode1"),
    ("pre_pos32", "target_low", "frontier_type", "opcode1"),
    ("target_offset_bucket", "pre_pos32", "target_low", "opcode1"),
]

SUMMARY_FIELDNAMES = [
    "scope",
    "blocked_sequence_slots",
    "unknown_prerequisite_slots",
    "training_role_entries",
    "features",
    "feature_sets",
    "false_free_full_byte_sets",
    "false_free_high_sets",
    "false_free_low_sets",
    "full_byte_candidate_slots",
    "partial_high_slots",
    "partial_low_slots",
    "combined_nibble_candidate_slots",
    "combined_nibble_conflict_slots",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "best_full_byte_feature_set",
    "best_full_byte_correct_slots",
    "best_partial_high_feature_set",
    "best_partial_high_correct_slots",
    "best_partial_low_feature_set",
    "best_partial_low_correct_slots",
    "oracle_target_low_feature_sets",
    "issue_rows",
]

RULE_FIELDNAMES = [
    "rank",
    "target_kind",
    "feature_set",
    "feature_count",
    "correct_slots",
    "false_slots",
    "unknown_slots",
    "precision",
    "predicted_values",
    "support_values",
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
    "sequence_rank",
    "sequence_offset",
    "target_absolute_offset",
    "prerequisite_absolute_offset",
    "role",
    "byte",
    "full_byte_predictions",
    "high_predictions",
    "low_predictions",
    "combined_nibble_prediction",
    "sample_rules",
    "verdict",
]


def fixture_key(row: dict[str, object]) -> tuple[str, str, str]:
    return (str(row.get("archive", "")), str(row.get("pcx_name", "")), str(row.get("frontier_id", "")))


def fixture_key_text(row: dict[str, object]) -> str:
    return "|".join(fixture_key(row))


def len_bucket(length: int) -> str:
    if length < 64:
        return "<64"
    if length < 256:
        return "64-255"
    return "256+"


def pos_bucket(offset: int, length: int, scale: int) -> str:
    return str((offset * scale) // length) if length else "0"


def target_offset_bucket(offset: int) -> str:
    if offset <= 2:
        return "head"
    if offset < 16:
        return "near_head"
    return "body"


def feature_sets(max_features: int) -> list[tuple[str, ...]]:
    output: list[tuple[str, ...]] = []
    for size in range(1, max_features + 1):
        output.extend(itertools.combinations(FEATURES, size))
    for feature_set in CURATED_FEATURE_SETS:
        if feature_set not in output:
            output.append(feature_set)
    return output


def context_for(row: dict[str, object], features: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(str(row.get(feature, "")) for feature in features)


def build_role_entries(fixture_rows: list[dict[str, str]]) -> tuple[list[dict[str, object]], list[str]]:
    entries: list[dict[str, object]] = []
    issues: list[str] = []
    for fixture in fixture_rows:
        try:
            expected = Path(fixture.get("expected_gap_path", "")).read_bytes()
        except OSError as exc:
            issues.append(f"read_expected_failed:{fixture_key_text(fixture)}:{exc}")
            continue
        key_text = fixture_key_text(fixture)
        for offset, value in enumerate(expected):
            for role, delta in (("first", 2), ("second", 1)):
                target_offset = offset + delta
                if target_offset >= len(expected):
                    continue
                target = expected[target_offset]
                entries.append(
                    {
                        "fixture_key": key_text,
                        "archive": fixture.get("archive", ""),
                        "pcx_name": fixture.get("pcx_name", ""),
                        "frontier_id": fixture.get("frontier_id", ""),
                        "rule_type": fixture.get("rule_type", ""),
                        "frontier_type": fixture.get("frontier_type", ""),
                        "opcode0": fixture.get("opcode0_hex", ""),
                        "opcode1": fixture.get("opcode1_hex", ""),
                        "role": role,
                        "offset": offset,
                        "target_offset": target_offset,
                        "byte": f"{value:02x}",
                        "pre_high": f"{value >> 4:x}",
                        "pre_low": f"{value & 0x0F:x}",
                        "target_byte": f"{target:02x}",
                        "target_high": f"{target >> 4:x}",
                        "target_low": f"{target & 0x0F:x}",
                        "target_offset_bucket": target_offset_bucket(target_offset),
                        "target_pos4": str(target_offset % 4),
                        "target_pos8": str(target_offset % 8),
                        "target_pos16": pos_bucket(target_offset, len(expected), 16),
                        "target_pos32": pos_bucket(target_offset, len(expected), 32),
                        "pre_pos4": str(offset % 4),
                        "pre_pos8": str(offset % 8),
                        "pre_pos16": pos_bucket(offset, len(expected), 16),
                        "pre_pos32": pos_bucket(offset, len(expected), 32),
                        "len_bucket": len_bucket(len(expected)),
                    }
                )
    return entries, issues


def target_prerequisite_entries(
    sequence_slots: list[dict[str, str]],
    role_entries: list[dict[str, object]],
) -> list[dict[str, object]]:
    role_by_key = {
        (entry["fixture_key"], int(entry["offset"]), entry["role"]): entry
        for entry in role_entries
    }
    output: list[dict[str, object]] = []
    seen: set[tuple[str, int, str]] = set()
    for slot in sequence_slots:
        if slot.get("state") != "blocked_prerequisites":
            continue
        key_text = fixture_key_text(slot)
        target_absolute = int_value(slot, "absolute_offset")
        known_values = slot.get("known_prerequisites", "").split("|")
        for absolute_text, known in zip(slot.get("prerequisite_offsets", "").split("|"), known_values):
            if not absolute_text or known == "1":
                continue
            prerequisite_absolute = int(absolute_text)
            role = "first" if prerequisite_absolute == target_absolute - 2 else "second"
            lookup_key = (key_text, prerequisite_absolute, role)
            if lookup_key in seen:
                continue
            seen.add(lookup_key)
            entry = dict(role_by_key.get(lookup_key, {}))
            if not entry:
                continue
            entry.update(
                {
                    "row_index": slot.get("row_index", ""),
                    "sequence_rank": slot.get("rank", ""),
                    "sequence_offset": slot.get("offset", ""),
                    "target_absolute_offset": target_absolute,
                    "prerequisite_absolute_offset": prerequisite_absolute,
                }
            )
            output.append(entry)
    return output


def evaluate_rule(
    entries: list[dict[str, object]],
    targets: list[dict[str, object]],
    transform: str,
    features: tuple[str, ...],
) -> dict[str, object]:
    target_contexts = {context_for(target, features) for target in targets}
    all_counts: dict[tuple[str, ...], Counter[str]] = defaultdict(Counter)
    fixture_counts: dict[tuple[str, tuple[str, ...]], Counter[str]] = defaultdict(Counter)
    support_bytes: dict[tuple[str, ...], Counter[str]] = defaultdict(Counter)
    fixture_support_bytes: dict[tuple[str, tuple[str, ...]], Counter[str]] = defaultdict(Counter)
    for entry in entries:
        context = context_for(entry, features)
        if context not in target_contexts:
            continue
        value = str(entry.get(transform, ""))
        all_counts[context][value] += 1
        fixture_counts[(str(entry["fixture_key"]), context)][value] += 1
        support_bytes[context][str(entry.get("byte", ""))] += 1
        fixture_support_bytes[(str(entry["fixture_key"]), context)][str(entry.get("byte", ""))] += 1

    correct = 0
    false = 0
    unknown = 0
    predicted_values: Counter[str] = Counter()
    support_values: Counter[str] = Counter()
    sample_correct: list[str] = []
    sample_false: list[str] = []
    for target in targets:
        context = context_for(target, features)
        counts = all_counts[context].copy()
        counts.subtract(fixture_counts[(str(target["fixture_key"]), context)])
        counts += Counter()
        values = [value for value, count in counts.items() if count > 0]
        prediction = values[0] if len(values) == 1 else None
        if prediction is None:
            unknown += 1
            continue
        predicted_values[prediction] += 1
        support_byte_counts = support_bytes[context].copy()
        support_byte_counts.subtract(fixture_support_bytes[(str(target["fixture_key"]), context)])
        support_byte_counts += Counter()
        support_values.update(support_byte_counts)
        label = (
            f"{target.get('row_index')}:{target.get('frontier_id')}:"
            f"{target.get('prerequisite_absolute_offset')}={prediction}"
        )
        if prediction == str(target.get(transform, "")):
            correct += 1
            if len(sample_correct) < 8:
                sample_correct.append(label)
        else:
            false += 1
            if len(sample_false) < 8:
                sample_false.append(f"{label}!={target.get(transform, '')}")

    predicted = correct + false
    if predicted == 0:
        verdict = "no_role_transform_prediction"
    elif false == 0 and transform == "byte":
        verdict = "false_free_full_byte_review"
    elif false == 0:
        verdict = "false_free_partial_nibble_review"
    elif correct > 0:
        verdict = "role_transform_conflict"
    else:
        verdict = "role_transform_reject"
    return {
        "rank": 0,
        "target_kind": transform,
        "feature_set": "+".join(features),
        "feature_count": len(features),
        "correct_slots": correct,
        "false_slots": false,
        "unknown_slots": unknown,
        "precision": ratio(correct, predicted),
        "predicted_values": "|".join(f"{value}:{count}" for value, count in predicted_values.most_common()),
        "support_values": "|".join(f"{value}:{count}" for value, count in support_values.most_common(8)),
        "sample_correct_slots": "|".join(sample_correct),
        "sample_false_slots": "|".join(sample_false),
        "verdict": verdict,
    }


def prediction_map(
    entries: list[dict[str, object]],
    targets: list[dict[str, object]],
    rules: list[dict[str, object]],
    transform: str,
) -> dict[tuple[str, int, str], list[tuple[str, str]]]:
    output: dict[tuple[str, int, str], list[tuple[str, str]]] = defaultdict(list)
    selected = [rule for rule in rules if rule.get("target_kind") == transform and int_value(rule, "false_slots") == 0]
    for rule in selected:
        features = tuple(str(rule.get("feature_set", "")).split("+"))
        target_contexts = {context_for(target, features) for target in targets}
        all_counts: dict[tuple[str, ...], Counter[str]] = defaultdict(Counter)
        fixture_counts: dict[tuple[str, tuple[str, ...]], Counter[str]] = defaultdict(Counter)
        for entry in entries:
            context = context_for(entry, features)
            if context not in target_contexts:
                continue
            value = str(entry.get(transform, ""))
            all_counts[context][value] += 1
            fixture_counts[(str(entry["fixture_key"]), context)][value] += 1
        for target in targets:
            context = context_for(target, features)
            counts = all_counts[context].copy()
            counts.subtract(fixture_counts[(str(target["fixture_key"]), context)])
            counts += Counter()
            values = [value for value, count in counts.items() if count > 0]
            if len(values) != 1:
                continue
            if values[0] != str(target.get(transform, "")):
                continue
            key = (str(target["fixture_key"]), int(target["offset"]), str(target["role"]))
            output[key].append((values[0], str(rule["feature_set"])))
    return output


def build(
    fixture_rows: list[dict[str, str]],
    sequence_slots: list[dict[str, str]],
    *,
    max_features: int,
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    entries, issues = build_role_entries(fixture_rows)
    targets = target_prerequisite_entries(sequence_slots, entries)
    rules: list[dict[str, object]] = []
    for transform in TRANSFORM_TARGETS:
        for features in feature_sets(max_features):
            rule = evaluate_rule(entries, targets, transform, features)
            if int_value(rule, "correct_slots") > 0:
                rules.append(rule)

    rules.sort(
        key=lambda row: (
            0 if int_value(row, "false_slots") == 0 else 1,
            str(row.get("target_kind", "")) != "byte",
            -int_value(row, "correct_slots"),
            int_value(row, "unknown_slots"),
            int_value(row, "feature_count"),
            str(row.get("feature_set", "")),
        )
    )
    for index, row in enumerate(rules, start=1):
        row["rank"] = index

    full_map = prediction_map(entries, targets, rules, "byte")
    high_map = prediction_map(entries, targets, rules, "pre_high")
    low_map = prediction_map(entries, targets, rules, "pre_low")
    slot_rows: list[dict[str, object]] = []
    full_candidate_slots = 0
    partial_high_slots = 0
    partial_low_slots = 0
    combined_candidate_slots = 0
    combined_conflict_slots = 0
    for target in sorted(targets, key=lambda row: (int_value(row, "row_index"), int_value(row, "offset"), str(row["role"]))):
        key = (str(target["fixture_key"]), int(target["offset"]), str(target["role"]))
        full_predictions = sorted({prediction for prediction, _rule in full_map.get(key, [])})
        high_predictions = sorted({prediction for prediction, _rule in high_map.get(key, [])})
        low_predictions = sorted({prediction for prediction, _rule in low_map.get(key, [])})
        sample_rules = [
            *[f"byte:{rule}" for _prediction, rule in full_map.get(key, [])[:3]],
            *[f"high:{rule}" for _prediction, rule in high_map.get(key, [])[:3]],
            *[f"low:{rule}" for _prediction, rule in low_map.get(key, [])[:3]],
        ]
        combined = ""
        if len(full_predictions) == 1:
            verdict = "full_byte_candidate"
            full_candidate_slots += 1
        elif len(high_predictions) == 1 and len(low_predictions) == 1:
            combined = f"{high_predictions[0]}{low_predictions[0]}"
            if combined == str(target.get("byte", "")):
                verdict = "combined_nibble_candidate"
                combined_candidate_slots += 1
            else:
                verdict = "combined_nibble_conflict"
                combined_conflict_slots += 1
        elif high_predictions or low_predictions:
            verdict = "partial_nibble_only"
        else:
            verdict = "no_prediction"
        if high_predictions:
            partial_high_slots += 1
        if low_predictions:
            partial_low_slots += 1
        slot_rows.append(
            {
                "rank": len(slot_rows) + 1,
                "row_index": target.get("row_index", ""),
                "archive": target.get("archive", ""),
                "pcx_name": target.get("pcx_name", ""),
                "frontier_id": target.get("frontier_id", ""),
                "sequence_rank": target.get("sequence_rank", ""),
                "sequence_offset": target.get("sequence_offset", ""),
                "target_absolute_offset": target.get("target_absolute_offset", ""),
                "prerequisite_absolute_offset": target.get("prerequisite_absolute_offset", ""),
                "role": target.get("role", ""),
                "byte": target.get("byte", ""),
                "full_byte_predictions": "|".join(full_predictions),
                "high_predictions": "|".join(high_predictions),
                "low_predictions": "|".join(low_predictions),
                "combined_nibble_prediction": combined,
                "sample_rules": "|".join(sample_rules),
                "verdict": verdict,
            }
        )

    false_free_full = [row for row in rules if row.get("target_kind") == "byte" and int_value(row, "false_slots") == 0]
    false_free_high = [row for row in rules if row.get("target_kind") == "pre_high" and int_value(row, "false_slots") == 0]
    false_free_low = [row for row in rules if row.get("target_kind") == "pre_low" and int_value(row, "false_slots") == 0]
    best_full = false_free_full[0] if false_free_full else {}
    best_high = false_free_high[0] if false_free_high else {}
    best_low = false_free_low[0] if false_free_low else {}
    tested_feature_sets = feature_sets(max_features)
    summary = {
        "scope": "total",
        "blocked_sequence_slots": sum(1 for slot in sequence_slots if slot.get("state") == "blocked_prerequisites"),
        "unknown_prerequisite_slots": len(targets),
        "training_role_entries": len(entries),
        "features": len(FEATURES),
        "feature_sets": len(tested_feature_sets),
        "false_free_full_byte_sets": len(false_free_full),
        "false_free_high_sets": len(false_free_high),
        "false_free_low_sets": len(false_free_low),
        "full_byte_candidate_slots": full_candidate_slots,
        "partial_high_slots": partial_high_slots,
        "partial_low_slots": partial_low_slots,
        "combined_nibble_candidate_slots": combined_candidate_slots,
        "combined_nibble_conflict_slots": combined_conflict_slots,
        "promotion_candidate_bytes": 0,
        "promotion_ready_bytes": 0,
        "best_full_byte_feature_set": best_full.get("feature_set", ""),
        "best_full_byte_correct_slots": best_full.get("correct_slots", 0),
        "best_partial_high_feature_set": best_high.get("feature_set", ""),
        "best_partial_high_correct_slots": best_high.get("correct_slots", 0),
        "best_partial_low_feature_set": best_low.get("feature_set", ""),
        "best_partial_low_correct_slots": best_low.get("correct_slots", 0),
        "oracle_target_low_feature_sets": sum(1 for features in tested_feature_sets if "target_low" in features),
        "issue_rows": len(issues),
    }
    return summary, rules, slot_rows


def build_html(
    summary: dict[str, object],
    rules: list[dict[str, object]],
    slots: list[dict[str, object]],
    title: str,
) -> str:
    data_json = json.dumps({"summary": summary, "rules": rules, "slots": slots}, indent=2, sort_keys=True)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 2rem; background: #f7f4ee; color: #1f2933; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 1rem; }}
.box, .panel {{ background: white; border: 1px solid #d8d1c4; border-radius: 6px; padding: 1rem; }}
.num {{ font-size: 1.8rem; font-weight: 700; }}
.muted {{ color: #6b7280; }}
table {{ border-collapse: collapse; width: 100%; font-size: 0.85rem; }}
th, td {{ border-bottom: 1px solid #e5e7eb; padding: 0.35rem 0.45rem; text-align: left; vertical-align: top; }}
th {{ background: #f3efe7; position: sticky; top: 0; }}
.panel {{ margin-top: 1rem; overflow-x: auto; }}
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<div class="grid">
  <div class="box"><div class="num">{summary['unknown_prerequisite_slots']}</div><div class="muted">unknown prerequisites</div></div>
  <div class="box"><div class="num">{summary['false_free_full_byte_sets']}</div><div class="muted">full byte rule sets</div></div>
  <div class="box"><div class="num">{summary['partial_high_slots']}</div><div class="muted">partial high slots</div></div>
  <div class="box"><div class="num">{summary['partial_low_slots']}</div><div class="muted">partial low slots</div></div>
  <div class="box"><div class="num">{summary['promotion_candidate_bytes']}</div><div class="muted">promotion candidates</div></div>
</div>
<div class="panel"><h2>Slots</h2>{render_table(slots, SLOT_FIELDNAMES)}</div>
<div class="panel"><h2>Rules</h2>{render_table(rules[:120], RULE_FIELDNAMES)}</div>
<script type="application/json" id="mixed-value-sequence-blocked-prerequisite-role-transform-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe blocked prerequisite role transforms.")
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--sequence-slots", type=Path, default=DEFAULT_SEQUENCE_SLOTS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-features", type=int, default=2)
    parser.add_argument("--title", default="Lands of Lore II .tex Blocked Prerequisite Role Transform")
    args = parser.parse_args()

    fixture_rows = read_csv(args.fixtures)
    sequence_slots = read_csv(args.sequence_slots)
    summary, rules, slots = build(fixture_rows, sequence_slots, max_features=args.max_features)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "rules.csv", RULE_FIELDNAMES, rules)
    write_csv(args.output / "slots.csv", SLOT_FIELDNAMES, slots)
    (args.output / "index.html").write_text(build_html(summary, rules, slots, args.title))

    print(f"Blocked prerequisite role transform: {summary['unknown_prerequisite_slots']} unknown prerequisites")
    print(f"Full byte candidate slots: {summary['full_byte_candidate_slots']}")
    print(f"Partial high/low slots: {summary['partial_high_slots']}/{summary['partial_low_slots']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
