#!/usr/bin/env python3
"""Probe low-nibble transforms after gradient row/corpus high-safe selection."""

from __future__ import annotations

import argparse
import csv
import html
import itertools
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_opcode_probe import write_csv
from lolg_tex_gradient_sequence_high_safe_low_probe import int_value, ratio, render_table
from lolg_tex_gradient_sequence_high_safe_row_corpus_low_probe import (
    SLOT_FIELDNAMES as ROW_CORPUS_SLOT_FIELDNAMES,
)


DEFAULT_SLOTS = Path("output/tex_gradient_sequence_high_safe_row_corpus_low/slots.csv")
DEFAULT_OUTPUT = Path("output/tex_gradient_sequence_high_safe_transform_low")

FOCUSED_FEATURES = [
    "rel_mod4",
    "rel_mod8",
    "rel_mod16",
    "x_mod8",
    "src_rel_mod4",
    "src_rel_mod8",
    "source_low",
    "source_high",
    "source_byte",
    "offset_delta_bucket",
    "prev_known_byte",
    "prev_gap_bucket",
    "next_known_byte",
    "unknown_before_mod16",
    "prefix_sum_mod16",
    "predicted_high",
    "high_context",
    "row_quarter",
    "row_third",
    "row_half",
    "end_mod16",
    "length_mod16",
    "source_target_delta_mod16",
    "source_target_delta_mod32",
    "target_mod64",
    "target_x_mod32",
    "start_mod64",
    "shape_len_key",
    "shape_start_key",
]

FOCUSED_4_FEATURE_SETS = [
    ("x_mod8", "src_rel_mod8", "offset_delta_bucket", "row_third"),
    ("rel_mod8", "offset_delta_bucket", "high_context", "row_third"),
    ("rel_mod8", "offset_delta_bucket", "row_third", "shape_len_key"),
    ("rel_mod8", "offset_delta_bucket", "row_third", "shape_start_key"),
    ("rel_mod8", "offset_delta_bucket", "row_third", "start_mod64"),
    ("rel_mod8", "x_mod8", "offset_delta_bucket", "row_third"),
    ("src_rel_mod8", "offset_delta_bucket", "high_context", "row_third"),
    ("src_rel_mod8", "offset_delta_bucket", "row_third", "shape_len_key"),
    ("src_rel_mod8", "offset_delta_bucket", "row_third", "shape_start_key"),
    ("src_rel_mod8", "offset_delta_bucket", "row_third", "start_mod64"),
    ("rel_mod4", "x_mod8", "offset_delta_bucket", "row_third"),
    ("rel_mod4", "x_mod8", "row_quarter", "prev_known_byte"),
]

TRANSFORM_BASES = [
    "source",
    "prev_known",
    "next_known",
    "prev1",
    "prev2",
    "prev4",
    "next1",
    "next2",
    "next4",
    "rel",
    "x",
    "target_mod16",
    "source_delta",
]

TRANSFORM_KINDS = ["delta", "signed", "xor"]

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "row_corpus_slots",
    "row_corpus_rows",
    "features",
    "feature_sets",
    "transform_targets",
    "candidate_rules",
    "predicted_rules",
    "false_free_transform_sets",
    "best_false_free_correct_slots",
    "best_false_free_transform_target",
    "best_false_free_feature_set",
    "best_exact_slots",
    "best_false_slots",
    "best_transform_target",
    "best_feature_set",
    "best_low_false_exact_slots",
    "best_low_false_false_slots",
    "best_low_false_transform_target",
    "best_low_false_feature_set",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

RULE_FIELDNAMES = [
    "rank",
    "transform_target",
    "feature_set",
    "feature_count",
    "applicable_slots",
    "predicted_slots",
    "exact_slots",
    "false_slots",
    "unknown_slots",
    "precision",
    "predicted_values",
    "predicted_groups",
    "predicted_rows",
    "false_free",
    "sample_predictions",
    "verdict",
]

SLOT_FIELDNAMES = [
    *ROW_CORPUS_SLOT_FIELDNAMES,
    "best_transform_target",
    "best_transform_feature_set",
    "best_transform_context",
    "best_transform_value",
    "best_transform_predicted_low",
    "best_transform_predicted_byte",
    "best_transform_verdict",
    "best_low_false_transform_target",
    "best_low_false_feature_set",
    "best_low_false_context",
    "best_low_false_value",
    "best_low_false_predicted_low",
    "best_low_false_predicted_byte",
    "best_low_false_verdict",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def parse_hex(text: object) -> int | None:
    value = str(text)
    if not value or value in {"unk", "none", "START"}:
        return None
    try:
        return int(value, 16)
    except ValueError:
        return None


def parse_int(text: object) -> int | None:
    value = str(text)
    if not value or value == "none":
        return None
    try:
        return int(value, 0)
    except ValueError:
        return None


def target_low(row: dict[str, object]) -> int | None:
    return parse_hex(row.get("target_low", ""))


def low_base(row: dict[str, object], base: str) -> int | None:
    if base == "source":
        return parse_hex(row.get("source_low", ""))
    if base == "prev_known":
        value = parse_hex(row.get("prev_known_byte", ""))
        return None if value is None else value & 0x0F
    if base == "next_known":
        value = parse_hex(row.get("next_known_byte", ""))
        return None if value is None else value & 0x0F
    if base in {"prev1", "prev2", "prev4", "next1", "next2", "next4"}:
        value = parse_hex(row.get(base, ""))
        return None if value is None else value & 0x0F
    if base == "rel":
        return int_value(row, "rel_mod16") & 0x0F
    if base == "x":
        return int_value(row, "x_mod8") & 0x0F
    if base == "target_mod16":
        return int_value(row, "target_mod16") & 0x0F
    if base == "source_delta":
        value = parse_int(row.get("source_target_delta_mod16", ""))
        return None if value is None else value & 0x0F
    raise ValueError(base)


def transform_targets() -> list[str]:
    return ["target_low", *[f"{kind}:{base}" for base in TRANSFORM_BASES for kind in TRANSFORM_KINDS]]


def transform_value(row: dict[str, object], transform: str) -> str:
    low = target_low(row)
    if low is None:
        return ""
    if transform == "target_low":
        return f"{low:x}"
    kind, base = transform.split(":", 1)
    base_low = low_base(row, base)
    if base_low is None:
        return ""
    if kind == "delta":
        return f"{(low - base_low) & 0x0F:x}"
    if kind == "signed":
        return str(((low - base_low + 8) & 0x0F) - 8)
    if kind == "xor":
        return f"{low ^ base_low:x}"
    raise ValueError(transform)


def predicted_low(row: dict[str, object], transform: str, value: str) -> int | None:
    if not value:
        return None
    if transform == "target_low":
        return parse_hex(value)
    kind, base = transform.split(":", 1)
    base_low = low_base(row, base)
    if base_low is None:
        return None
    try:
        if kind == "delta":
            return (base_low + int(value, 16)) & 0x0F
        if kind == "signed":
            return (base_low + int(value)) & 0x0F
        if kind == "xor":
            return base_low ^ (int(value, 16) & 0x0F)
    except ValueError:
        return None
    raise ValueError(transform)


def predicted_byte(row: dict[str, object], low: int | None) -> str:
    high = parse_hex(row.get("predicted_high", ""))
    if high is None or low is None:
        return ""
    return f"{high:x}{low & 0x0F:x}"


def candidate_feature_sets(max_features: int) -> list[tuple[str, ...]]:
    output: list[tuple[str, ...]] = []
    generated_max = min(max_features, 3)
    for size in range(1, generated_max + 1):
        output.extend(itertools.combinations(FOCUSED_FEATURES, size))
    if max_features >= 4:
        output.extend(FOCUSED_4_FEATURE_SETS)
    seen: set[tuple[str, ...]] = set()
    unique: list[tuple[str, ...]] = []
    for feature_set in output:
        if feature_set in seen:
            continue
        seen.add(feature_set)
        unique.append(feature_set)
    return unique


def contexts_for(slots: list[dict[str, object]], feature_set: tuple[str, ...]) -> list[tuple[str, ...]]:
    return [tuple(str(slot.get(feature, "")) for feature in feature_set) for slot in slots]


def transform_values(slots: list[dict[str, object]], transform: str) -> list[str]:
    return [transform_value(slot, transform) for slot in slots]


def evaluate_rule(
    slots: list[dict[str, object]],
    contexts: list[tuple[str, ...]],
    values: list[str],
    transform: str,
    feature_set: tuple[str, ...],
) -> dict[str, object]:
    groups: dict[tuple[str, ...], list[int]] = defaultdict(list)
    for index, value in enumerate(values):
        if value:
            groups[contexts[index]].append(index)

    applicable = sum(1 for value in values if value)
    exact = 0
    false = 0
    unknown = 0
    predicted = 0
    predicted_values: Counter[str] = Counter()
    predicted_groups: set[tuple[str, ...]] = set()
    predicted_rows: set[str] = set()
    samples: list[str] = []
    for context, indexes in groups.items():
        total_counts = Counter(values[index] for index in indexes if values[index])
        by_row: dict[str, Counter[str]] = defaultdict(Counter)
        for index in indexes:
            by_row[str(slots[index].get("row_id", ""))][values[index]] += 1
        peer_value_by_row: dict[str, str] = {}
        for row_id, counts in by_row.items():
            peer_counts = total_counts.copy()
            peer_counts.subtract(counts)
            peer_counts = Counter({value: count for value, count in peer_counts.items() if count > 0})
            if len(peer_counts) == 1:
                peer_value_by_row[row_id] = next(iter(peer_counts))
        for index in indexes:
            slot = slots[index]
            row_id = str(slot.get("row_id", ""))
            value = peer_value_by_row.get(row_id)
            if value is None:
                unknown += 1
                continue
            low = predicted_low(slot, transform, value)
            if low is None:
                unknown += 1
                continue
            predicted += 1
            predicted_groups.add(context)
            predicted_rows.add(row_id)
            predicted_values[f"{low:x}"] += 1
            if low == target_low(slot):
                exact += 1
            else:
                false += 1
            if len(samples) < 8:
                samples.append(f"{'|'.join(context)}:{transform}={value}->low={low:x}")

    false_free = predicted > 0 and false == 0
    return {
        "rank": 0,
        "transform_target": transform,
        "feature_set": "+".join(feature_set),
        "feature_count": len(feature_set),
        "applicable_slots": applicable,
        "predicted_slots": predicted,
        "exact_slots": exact,
        "false_slots": false,
        "unknown_slots": unknown,
        "precision": ratio(exact, predicted),
        "predicted_values": "|".join(f"{value}:{count}" for value, count in predicted_values.most_common()),
        "predicted_groups": len(predicted_groups),
        "predicted_rows": len(predicted_rows),
        "false_free": 1 if false_free else 0,
        "sample_predictions": "|".join(samples),
        "verdict": (
            "transform_low_false_free"
            if false_free
            else "transform_low_noisy"
            if predicted
            else "transform_low_no_predictions"
        ),
    }


def build_rules(
    slots: list[dict[str, object]],
    *,
    max_features: int,
) -> tuple[list[dict[str, object]], list[tuple[str, ...]], list[str]]:
    feature_sets = candidate_feature_sets(max_features)
    transforms = transform_targets()
    contexts_by_features = [(feature_set, contexts_for(slots, feature_set)) for feature_set in feature_sets]
    values_by_transform = {transform: transform_values(slots, transform) for transform in transforms}
    rules: list[dict[str, object]] = []
    for transform in transforms:
        values = values_by_transform[transform]
        for feature_set, contexts in contexts_by_features:
            rule = evaluate_rule(slots, contexts, values, transform, feature_set)
            if int_value(rule, "predicted_slots") > 0:
                rules.append(rule)
    rules.sort(
        key=lambda row: (
            -int_value(row, "false_free"),
            -int_value(row, "exact_slots"),
            int_value(row, "false_slots"),
            int_value(row, "feature_count"),
            str(row["transform_target"]),
            str(row["feature_set"]),
        )
    )
    for index, row in enumerate(rules, start=1):
        row["rank"] = index
    return rules, feature_sets, transforms


def best_rule(rules: list[dict[str, object]]) -> dict[str, object]:
    return max(
        rules,
        key=lambda row: (
            int_value(row, "exact_slots"),
            -int_value(row, "false_slots"),
            -int_value(row, "feature_count"),
            str(row.get("transform_target", "")),
            str(row.get("feature_set", "")),
        ),
        default={},
    )


def best_false_free_rule(rules: list[dict[str, object]]) -> dict[str, object]:
    candidates = [row for row in rules if int_value(row, "false_free") > 0]
    return max(
        candidates,
        key=lambda row: (
            int_value(row, "exact_slots"),
            -int_value(row, "feature_count"),
            str(row.get("transform_target", "")),
            str(row.get("feature_set", "")),
        ),
        default={},
    )


def best_low_false_rule(rules: list[dict[str, object]], max_false: int = 5) -> dict[str, object]:
    candidates = [
        row
        for row in rules
        if 0 <= int_value(row, "false_slots") <= max_false and int_value(row, "exact_slots") >= 10
    ]
    return max(
        candidates,
        key=lambda row: (
            int_value(row, "exact_slots"),
            -int_value(row, "false_slots"),
            -int_value(row, "feature_count"),
            str(row.get("transform_target", "")),
            str(row.get("feature_set", "")),
        ),
        default={},
    )


def false_free_count(rules: list[dict[str, object]]) -> int:
    return sum(1 for row in rules if int_value(row, "false_free") > 0)


def rule_feature_set(rule: dict[str, object]) -> tuple[str, ...]:
    return tuple(part for part in str(rule.get("feature_set", "")).split("+") if part)


def prediction_for_slot(
    slots: list[dict[str, object]],
    slot: dict[str, object],
    transform: str,
    feature_set: tuple[str, ...],
) -> tuple[str, str, str, str, str]:
    if not transform or not feature_set:
        return "", "", "", "", ""
    contexts = contexts_for(slots, feature_set)
    values = transform_values(slots, transform)
    try:
        index = slots.index(slot)
    except ValueError:
        return "", "", "", "", ""
    context = contexts[index]
    indexes = [candidate for candidate, candidate_context in enumerate(contexts) if candidate_context == context]
    total_counts = Counter(values[candidate] for candidate in indexes if values[candidate])
    row_id = str(slot.get("row_id", ""))
    own_counts = Counter(
        values[candidate]
        for candidate in indexes
        if values[candidate] and str(slots[candidate].get("row_id", "")) == row_id
    )
    total_counts.subtract(own_counts)
    counts = Counter({value: count for value, count in total_counts.items() if count > 0})
    if len(counts) != 1:
        return "|".join(context), "", "", "", "unknown"
    value = next(iter(counts))
    low = predicted_low(slot, transform, value)
    predicted = predicted_byte(slot, low)
    if low is None:
        return "|".join(context), value, "", "", "unknown"
    verdict = "correct" if low == target_low(slot) else "false"
    return "|".join(context), value, f"{low:x}", predicted, verdict


def annotate_slots(
    slots: list[dict[str, object]],
    best: dict[str, object],
    low_false: dict[str, object],
) -> list[dict[str, object]]:
    best_transform = str(best.get("transform_target", ""))
    best_features = rule_feature_set(best)
    low_false_transform = str(low_false.get("transform_target", ""))
    low_false_features = rule_feature_set(low_false)
    output: list[dict[str, object]] = []
    for slot in slots:
        row = dict(slot)
        best_context, best_value, best_low, best_byte, best_verdict = prediction_for_slot(
            slots, row, best_transform, best_features
        )
        low_context, low_value, low_low, low_byte, low_verdict = prediction_for_slot(
            slots, row, low_false_transform, low_false_features
        )
        row.update(
            {
                "best_transform_target": best_transform,
                "best_transform_feature_set": "+".join(best_features),
                "best_transform_context": best_context,
                "best_transform_value": best_value,
                "best_transform_predicted_low": best_low,
                "best_transform_predicted_byte": best_byte,
                "best_transform_verdict": best_verdict,
                "best_low_false_transform_target": low_false_transform,
                "best_low_false_feature_set": "+".join(low_false_features),
                "best_low_false_context": low_context,
                "best_low_false_value": low_value,
                "best_low_false_predicted_low": low_low,
                "best_low_false_predicted_byte": low_byte,
                "best_low_false_verdict": low_verdict,
            }
        )
        output.append(row)
    return output


def build(
    slot_rows: list[dict[str, str]],
    *,
    max_features: int,
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    slots = [dict(row) for row in slot_rows]
    rules, feature_sets, transforms = build_rules(slots, max_features=max_features)
    best = best_rule(rules)
    false_free = best_false_free_rule(rules)
    low_false = best_low_false_rule(rules)
    annotated_slots = annotate_slots(slots, best, low_false)
    summary = {
        "scope": "total",
        "candidate_mode": "focused_transform_low",
        "row_corpus_slots": len(slots),
        "row_corpus_rows": len({row.get("row_id", "") for row in slots}),
        "features": len(FOCUSED_FEATURES),
        "feature_sets": len(feature_sets),
        "transform_targets": len(transforms),
        "candidate_rules": len(feature_sets) * len(transforms),
        "predicted_rules": len(rules),
        "false_free_transform_sets": false_free_count(rules),
        "best_false_free_correct_slots": false_free.get("exact_slots", 0),
        "best_false_free_transform_target": false_free.get("transform_target", ""),
        "best_false_free_feature_set": false_free.get("feature_set", ""),
        "best_exact_slots": best.get("exact_slots", 0),
        "best_false_slots": best.get("false_slots", 0),
        "best_transform_target": best.get("transform_target", ""),
        "best_feature_set": best.get("feature_set", ""),
        "best_low_false_exact_slots": low_false.get("exact_slots", 0),
        "best_low_false_false_slots": low_false.get("false_slots", 0),
        "best_low_false_transform_target": low_false.get("transform_target", ""),
        "best_low_false_feature_set": low_false.get("feature_set", ""),
        "promotion_candidate_bytes": 0,
        "promotion_ready_bytes": 0,
        "issue_rows": 0,
    }
    return summary, annotated_slots, rules


def build_html(
    summary: dict[str, object],
    slots: list[dict[str, object]],
    rules: list[dict[str, object]],
    title: str,
) -> str:
    top_rules = sorted(
        rules,
        key=lambda row: (
            -int_value(row, "false_free"),
            -int_value(row, "exact_slots"),
            int_value(row, "false_slots"),
            int_value(row, "feature_count"),
        ),
    )[:220]
    data_json = json.dumps({"summary": summary, "rules": top_rules, "slots": slots}, indent=2, sort_keys=True)
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body {{ margin: 2rem; background: #101214; color: #edf5f4; font: 14px/1.45 system-ui, sans-serif; }}
table {{ border-collapse: collapse; width: 100%; min-width: 2100px; }}
th, td {{ border: 1px solid #31424a; padding: .45rem .55rem; vertical-align: top; }}
th {{ color: #9dafb5; background: #172023; text-align: left; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: .75rem; margin: 1rem 0; }}
.box {{ border: 1px solid #31424a; background: #172023; padding: .75rem; }}
.num {{ font-size: 1.35rem; font-weight: 750; }}
.muted {{ color: #9dafb5; }}
.panel {{ overflow-x: auto; margin-top: 1rem; }}
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<div class="grid">
  <div class="box"><div class="num">{summary['row_corpus_slots']}</div><div class="muted">row/corpus slots</div></div>
  <div class="box"><div class="num">{summary['best_false_free_correct_slots']}</div><div class="muted">best false-free slots</div></div>
  <div class="box"><div class="num">{summary['best_exact_slots']}/{summary['best_false_slots']}</div><div class="muted">best exact/false</div></div>
  <div class="box"><div class="num">{summary['best_low_false_exact_slots']}/{summary['best_low_false_false_slots']}</div><div class="muted">best low-false exact/false</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Rules</h2>{render_table(top_rules, RULE_FIELDNAMES)}</div>
<div class="panel"><h2>Slots</h2>{render_table(slots, SLOT_FIELDNAMES)}</div>
<script type="application/json" id="gradient-sequence-high-safe-transform-low-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe gradient low transforms after row/corpus high-safe selection.")
    parser.add_argument("--slots", type=Path, default=DEFAULT_SLOTS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-features", type=int, default=4)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Gradient Sequence High-Safe Transform Low Probe",
    )
    args = parser.parse_args()

    summary, slots, rules = build(read_csv(args.slots), max_features=args.max_features)
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "slots.csv", SLOT_FIELDNAMES, slots)
    write_csv(args.output / "rules.csv", RULE_FIELDNAMES, rules)
    (args.output / "index.html").write_text(build_html(summary, slots, rules, args.title))

    print(f"Row/corpus slots: {summary['row_corpus_slots']}")
    print(f"Feature sets: {summary['feature_sets']}")
    print(f"Transform targets: {summary['transform_targets']}")
    print(f"Candidate rules: {summary['candidate_rules']}")
    print(f"Best false-free slots: {summary['best_false_free_correct_slots']}")
    print(
        "Best rule: "
        f"{summary['best_transform_target']} / {summary['best_feature_set']} = "
        f"{summary['best_exact_slots']} exact / {summary['best_false_slots']} false"
    )
    print(
        "Best low-false rule: "
        f"{summary['best_low_false_transform_target']} / {summary['best_low_false_feature_set']} = "
        f"{summary['best_low_false_exact_slots']} exact / "
        f"{summary['best_low_false_false_slots']} false"
    )
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
