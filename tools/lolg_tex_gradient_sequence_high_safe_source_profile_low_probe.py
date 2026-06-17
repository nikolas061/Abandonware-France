#!/usr/bin/env python3
"""Probe source-profile low/full bytes after sequence high-safe selection."""

from __future__ import annotations

import argparse
import csv
import html
import itertools
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_opcode_probe import write_csv
from lolg_tex_gradient_sequence_high_safe_low_probe import (
    RULE_FIELDNAMES,
    SLOT_FIELDNAMES as HIGH_SAFE_SLOT_FIELDNAMES,
    int_value,
    ratio,
    render_table,
)


DEFAULT_SEQUENCE_HIGH_SAFE_SLOTS = Path("output/tex_gradient_sequence_high_safe_low/slots.csv")
DEFAULT_SOURCE_PROFILE_SLOTS = Path("output/tex_gradient_source_profile_high_low/slots.csv")
DEFAULT_OUTPUT = Path("output/tex_gradient_sequence_high_safe_source_profile_low")

SEQUENCE_FEATURES = [
    "gradient_class",
    "top_nibble",
    "length_band8",
    "rel_mod4",
    "rel_mod8",
    "rel_mod16",
    "x_mod8",
    "y_mod8",
    "prev1",
    "prev2",
    "prev4",
    "next1",
    "next2",
    "next4",
    "prev_known_byte",
    "prev_gap_bucket",
    "next_known_byte",
    "next_gap_bucket",
    "known_before_mod16",
    "unknown_before_mod16",
    "prefix_sum_mod16",
    "prefix_xor_high",
    "prefix_xor_low",
    "predicted_high",
    "high_context",
]

SOURCE_FEATURES = [
    "pool",
    "offset_delta_bucket",
    "source_byte",
    "source_high",
    "source_low",
    "source_zero",
    "src_rel_mod4",
    "src_rel_mod8",
    "src_rel_mod16",
    "src_x_mod8",
    "src_y_mod4",
    "src_y_mod8",
]

FOCUSED_4_SOURCE_FEATURES = {
    "pool",
    "offset_delta_bucket",
    "source_byte",
    "source_high",
    "source_low",
}

FOCUSED_4_SEQUENCE_FEATURES = {
    "prev_known_byte",
    "next_known_byte",
    "prev_gap_bucket",
    "next_gap_bucket",
    "x_mod8",
    "rel_mod16",
    "unknown_before_mod16",
    "high_context",
    "predicted_high",
}

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "high_safe_slots",
    "joined_slots",
    "missing_source_slots",
    "high_safe_rows",
    "feature_sets",
    "full_false_free_sets",
    "full_best_false_free_slots",
    "full_best_exact_slots",
    "full_best_false_slots",
    "full_best_feature_set",
    "full_low_false_exact_slots",
    "full_low_false_false_slots",
    "full_low_false_feature_set",
    "target_low_false_free_sets",
    "target_low_best_false_free_slots",
    "target_low_best_exact_slots",
    "target_low_best_false_slots",
    "target_low_best_feature_set",
    "target_low_low_false_exact_slots",
    "target_low_low_false_false_slots",
    "target_low_low_false_feature_set",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

SLOT_FIELDNAMES = [
    *HIGH_SAFE_SLOT_FIELDNAMES,
    "pool",
    "source_profile_offset",
    "offset_delta",
    "offset_delta_bucket",
    "source_byte",
    "source_high",
    "source_low",
    "source_zero",
    "src_rel_mod4",
    "src_rel_mod8",
    "src_rel_mod16",
    "src_x_mod8",
    "src_y_mod4",
    "src_y_mod8",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def row_slot_key(row: dict[str, object]) -> tuple[str, str]:
    return (str(row.get("row_id", "")), str(row.get("target_offset", "")))


def join_slots(
    high_safe_slots: list[dict[str, str]],
    source_profile_slots: list[dict[str, str]],
) -> tuple[list[dict[str, object]], list[str]]:
    source_by_key = {row_slot_key(row): row for row in source_profile_slots}
    joined: list[dict[str, object]] = []
    issues: list[str] = []
    for slot in high_safe_slots:
        source = source_by_key.get(row_slot_key(slot))
        if source is None:
            issues.append(f"missing_source:{slot.get('row_id', '')}:{slot.get('target_offset', '')}")
            continue
        output = {field: slot.get(field, "") for field in HIGH_SAFE_SLOT_FIELDNAMES}
        output.update(
            {
                "pool": source.get("pool", ""),
                "source_profile_offset": source.get("source_profile_offset", ""),
                "offset_delta": source.get("offset_delta", ""),
                "offset_delta_bucket": source.get("offset_delta_bucket", ""),
                "source_byte": source.get("source_byte", ""),
                "source_high": source.get("source_high", ""),
                "source_low": source.get("source_low", ""),
                "source_zero": source.get("source_zero", ""),
                "src_rel_mod4": source.get("rel_mod4", ""),
                "src_rel_mod8": source.get("rel_mod8", ""),
                "src_rel_mod16": source.get("rel_mod16", ""),
                "src_x_mod8": source.get("x_mod8", ""),
                "src_y_mod4": source.get("y_mod4", ""),
                "src_y_mod8": source.get("y_mod8", ""),
            }
        )
        joined.append(output)
    for index, row in enumerate(joined, start=1):
        row["rank"] = index
    return joined, issues


def candidate_feature_sets(max_features: int) -> list[tuple[str, ...]]:
    features = [*SEQUENCE_FEATURES, *SOURCE_FEATURES]
    output: list[tuple[str, ...]] = []
    generated_max = min(max_features, 3)
    for size in range(1, generated_max + 1):
        output.extend(itertools.combinations(features, size))
    if max_features >= 4:
        for combo in itertools.combinations(features, 4):
            if not any(feature in FOCUSED_4_SOURCE_FEATURES for feature in combo):
                continue
            if not any(feature in FOCUSED_4_SEQUENCE_FEATURES for feature in combo):
                continue
            output.append(combo)
    seen: set[tuple[str, ...]] = set()
    unique: list[tuple[str, ...]] = []
    for feature_set in output:
        if feature_set in seen:
            continue
        seen.add(feature_set)
        unique.append(feature_set)
    return unique


def context_for(slot: dict[str, object], features: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(str(slot.get(feature, "")) for feature in features)


def target_field(target_kind: str) -> str:
    if target_kind == "full":
        return "target_byte"
    if target_kind == "target_low":
        return "target_low"
    raise ValueError(target_kind)


def evaluate_rule(
    slots: list[dict[str, object]], features: tuple[str, ...], target_kind: str
) -> dict[str, object]:
    field = target_field(target_kind)
    groups: dict[tuple[str, ...], list[dict[str, object]]] = defaultdict(list)
    for slot in slots:
        groups[context_for(slot, features)].append(slot)

    exact = 0
    false = 0
    predicted = 0
    predicted_groups: set[tuple[str, ...]] = set()
    predicted_rows: set[str] = set()
    samples: list[str] = []
    for context, group in groups.items():
        total_counts = Counter(str(slot.get(field, "")) for slot in group)
        by_row: dict[str, Counter[str]] = defaultdict(Counter)
        for slot in group:
            by_row[str(slot.get("row_id", ""))][str(slot.get(field, ""))] += 1
        peer_value_by_row: dict[str, str] = {}
        for row_id, counts in by_row.items():
            peer_counts = total_counts.copy()
            peer_counts.subtract(counts)
            peer_counts = Counter({value: count for value, count in peer_counts.items() if count > 0})
            if len(peer_counts) == 1:
                peer_value_by_row[row_id] = next(iter(peer_counts))
        for slot in group:
            row_id = str(slot.get("row_id", ""))
            value = peer_value_by_row.get(row_id)
            if value is None:
                continue
            predicted += 1
            predicted_groups.add(context)
            predicted_rows.add(row_id)
            if value == str(slot.get(field, "")):
                exact += 1
            else:
                false += 1
            if len(samples) < 8:
                samples.append(f"{'|'.join(context)}:v={value}")

    false_free = predicted > 0 and false == 0
    return {
        "rank": 0,
        "target_kind": target_kind,
        "feature_set": "+".join(features),
        "feature_count": len(features),
        "predicted_slots": predicted,
        "exact_slots": exact,
        "false_slots": false,
        "precision": ratio(exact, predicted),
        "groups": len(groups),
        "predicted_groups": len(predicted_groups),
        "predicted_rows": len(predicted_rows),
        "false_free": 1 if false_free else 0,
        "sample_predictions": "|".join(samples),
        "verdict": (
            f"{target_kind}_sequence_source_profile_false_free"
            if false_free
            else f"{target_kind}_sequence_source_profile_noisy"
            if predicted
            else f"{target_kind}_sequence_source_profile_no_predictions"
        ),
    }


def build_rules(
    slots: list[dict[str, object]],
    *,
    max_features: int,
) -> list[dict[str, object]]:
    rules: list[dict[str, object]] = []
    for target_kind in ("full", "target_low"):
        for features in candidate_feature_sets(max_features):
            rule = evaluate_rule(slots, features, target_kind)
            if int_value(rule, "predicted_slots") > 0:
                rules.append(rule)
    rules.sort(
        key=lambda row: (
            str(row["target_kind"]),
            -int_value(row, "false_free"),
            -int_value(row, "exact_slots"),
            int_value(row, "false_slots"),
            int_value(row, "feature_count"),
            str(row["feature_set"]),
        )
    )
    for index, row in enumerate(rules, start=1):
        row["rank"] = index
    return rules


def best_rule(rules: list[dict[str, object]], target_kind: str) -> dict[str, object]:
    candidates = [row for row in rules if row.get("target_kind") == target_kind]
    return max(
        candidates,
        key=lambda row: (
            int_value(row, "exact_slots"),
            -int_value(row, "false_slots"),
            -int_value(row, "feature_count"),
            str(row.get("feature_set", "")),
        ),
        default={},
    )


def best_false_free_rule(rules: list[dict[str, object]], target_kind: str) -> dict[str, object]:
    candidates = [
        row
        for row in rules
        if row.get("target_kind") == target_kind and int_value(row, "false_free") > 0
    ]
    return max(
        candidates,
        key=lambda row: (
            int_value(row, "exact_slots"),
            -int_value(row, "feature_count"),
            str(row.get("feature_set", "")),
        ),
        default={},
    )


def best_low_false_rule(
    rules: list[dict[str, object]], target_kind: str, max_false: int = 5
) -> dict[str, object]:
    candidates = [
        row
        for row in rules
        if row.get("target_kind") == target_kind
        and 0 <= int_value(row, "false_slots") <= max_false
        and int_value(row, "exact_slots") >= 10
    ]
    return max(
        candidates,
        key=lambda row: (
            int_value(row, "exact_slots"),
            -int_value(row, "false_slots"),
            -int_value(row, "feature_count"),
            str(row.get("feature_set", "")),
        ),
        default={},
    )


def false_free_count(rules: list[dict[str, object]], target_kind: str) -> int:
    return sum(
        1
        for row in rules
        if row.get("target_kind") == target_kind and int_value(row, "false_free") > 0
    )


def build(
    high_safe_slots: list[dict[str, str]],
    source_profile_slots: list[dict[str, str]],
    *,
    max_features: int,
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    slots, issues = join_slots(high_safe_slots, source_profile_slots)
    rules = build_rules(slots, max_features=max_features)
    full_best = best_rule(rules, "full")
    full_false_free = best_false_free_rule(rules, "full")
    full_low_false = best_low_false_rule(rules, "full")
    low_best = best_rule(rules, "target_low")
    low_false_free = best_false_free_rule(rules, "target_low")
    low_low_false = best_low_false_rule(rules, "target_low")
    candidates = candidate_feature_sets(max_features)
    summary = {
        "scope": "total",
        "candidate_mode": "focused",
        "high_safe_slots": len(high_safe_slots),
        "joined_slots": len(slots),
        "missing_source_slots": len(issues),
        "high_safe_rows": len({row.get("row_id", "") for row in slots}),
        "feature_sets": len(candidates),
        "full_false_free_sets": false_free_count(rules, "full"),
        "full_best_false_free_slots": full_false_free.get("exact_slots", 0),
        "full_best_exact_slots": full_best.get("exact_slots", 0),
        "full_best_false_slots": full_best.get("false_slots", 0),
        "full_best_feature_set": full_best.get("feature_set", ""),
        "full_low_false_exact_slots": full_low_false.get("exact_slots", 0),
        "full_low_false_false_slots": full_low_false.get("false_slots", 0),
        "full_low_false_feature_set": full_low_false.get("feature_set", ""),
        "target_low_false_free_sets": false_free_count(rules, "target_low"),
        "target_low_best_false_free_slots": low_false_free.get("exact_slots", 0),
        "target_low_best_exact_slots": low_best.get("exact_slots", 0),
        "target_low_best_false_slots": low_best.get("false_slots", 0),
        "target_low_best_feature_set": low_best.get("feature_set", ""),
        "target_low_low_false_exact_slots": low_low_false.get("exact_slots", 0),
        "target_low_low_false_false_slots": low_low_false.get("false_slots", 0),
        "target_low_low_false_feature_set": low_low_false.get("feature_set", ""),
        "promotion_candidate_bytes": 0,
        "promotion_ready_bytes": 0,
        "issue_rows": len(issues),
    }
    return summary, slots, rules


def build_html(
    summary: dict[str, object],
    slots: list[dict[str, object]],
    rules: list[dict[str, object]],
    title: str,
) -> str:
    top_rules = sorted(
        rules,
        key=lambda row: (
            str(row["target_kind"]),
            -int_value(row, "false_free"),
            -int_value(row, "exact_slots"),
            int_value(row, "false_slots"),
            int_value(row, "feature_count"),
        ),
    )[:220]
    data_json = json.dumps({"summary": summary, "rules": rules, "slots": slots}, indent=2, sort_keys=True)
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body {{ margin: 2rem; background: #101214; color: #edf5f4; font: 14px/1.45 system-ui, sans-serif; }}
table {{ border-collapse: collapse; width: 100%; min-width: 1900px; }}
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
  <div class="box"><div class="num">{summary['joined_slots']}</div><div class="muted">joined high-safe slots</div></div>
  <div class="box"><div class="num">{summary['full_best_false_free_slots']}</div><div class="muted">full false-free slots</div></div>
  <div class="box"><div class="num">{summary['target_low_best_false_free_slots']}</div><div class="muted">target-low false-free slots</div></div>
  <div class="box"><div class="num">{summary['target_low_best_false_slots']}</div><div class="muted">best target-low false slots</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Rules</h2>{render_table(top_rules, RULE_FIELDNAMES)}</div>
<div class="panel"><h2>Joined slots</h2>{render_table(slots, SLOT_FIELDNAMES)}</div>
<script type="application/json" id="gradient-sequence-high-safe-source-profile-low-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe source-profile low/full after sequence high-safe selection.")
    parser.add_argument("--high-safe-slots", type=Path, default=DEFAULT_SEQUENCE_HIGH_SAFE_SLOTS)
    parser.add_argument("--source-profile-slots", type=Path, default=DEFAULT_SOURCE_PROFILE_SLOTS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-features", type=int, default=4)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Gradient Sequence High-Safe Source-Profile Low Probe",
    )
    args = parser.parse_args()

    summary, slots, rules = build(
        read_csv(args.high_safe_slots),
        read_csv(args.source_profile_slots),
        max_features=args.max_features,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "slots.csv", SLOT_FIELDNAMES, slots)
    write_csv(args.output / "rules.csv", RULE_FIELDNAMES, rules)
    (args.output / "index.html").write_text(build_html(summary, slots, rules, args.title))

    print(f"Joined slots: {summary['joined_slots']}")
    print(f"Feature sets: {summary['feature_sets']}")
    print(f"Full false-free slots: {summary['full_best_false_free_slots']}")
    print(
        "Best full rule: "
        f"{summary['full_best_exact_slots']} exact / {summary['full_best_false_slots']} false"
    )
    print(f"Target-low false-free slots: {summary['target_low_best_false_free_slots']}")
    print(
        "Best target-low rule: "
        f"{summary['target_low_best_exact_slots']} exact / {summary['target_low_best_false_slots']} false"
    )
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
