#!/usr/bin/env python3
"""Probe low/full bytes after false-free gradient sequence high selection."""

from __future__ import annotations

import argparse
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_opcode_probe import write_csv
from lolg_tex_gradient_sequence_known_state_probe import (
    FEATURES as BASE_FEATURES,
    SLOT_FIELDNAMES as BASE_SLOT_FIELDNAMES,
    feature_sets,
    int_value,
    ratio,
    read_csv,
    render_table,
)


DEFAULT_SLOTS = Path("output/tex_gradient_sequence_known_state/slots.csv")
DEFAULT_SUMMARY = Path("output/tex_gradient_sequence_known_state/summary.csv")
DEFAULT_OUTPUT = Path("output/tex_gradient_sequence_high_safe_low")

LOW_FEATURES = [*BASE_FEATURES, "predicted_high", "high_context"]

SUMMARY_FIELDNAMES = [
    "scope",
    "slot_rows",
    "source_profile_rows",
    "high_feature_set",
    "high_safe_slots",
    "high_safe_rows",
    "low_feature_sets",
    "full_false_free_sets",
    "full_best_false_free_slots",
    "full_best_exact_slots",
    "full_best_false_slots",
    "full_best_feature_set",
    "target_low_false_free_sets",
    "target_low_best_false_free_slots",
    "target_low_best_exact_slots",
    "target_low_best_false_slots",
    "target_low_best_feature_set",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

SLOT_FIELDNAMES = [*BASE_SLOT_FIELDNAMES, "predicted_high", "high_context"]

RULE_FIELDNAMES = [
    "rank",
    "target_kind",
    "feature_set",
    "feature_count",
    "predicted_slots",
    "exact_slots",
    "false_slots",
    "precision",
    "groups",
    "predicted_groups",
    "predicted_rows",
    "false_free",
    "sample_predictions",
    "verdict",
]


def context_for(row: dict[str, object], features: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(str(row.get(feature, "")) for feature in features)


def parse_high_features(summary_rows: list[dict[str, str]], explicit: str) -> tuple[str, ...]:
    if explicit:
        return tuple(part for part in explicit.split("+") if part)
    if not summary_rows:
        raise ValueError("missing sequence known-state summary rows")
    feature_set = summary_rows[0].get("high_best_false_free_feature_set", "")
    if not feature_set:
        raise ValueError("summary has no high_best_false_free_feature_set")
    return tuple(part for part in feature_set.split("+") if part)


def high_safe_slots(slot_rows: list[dict[str, str]], high_features: tuple[str, ...]) -> list[dict[str, object]]:
    groups: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in slot_rows:
        groups[context_for(row, high_features)].append(row)

    output: list[dict[str, object]] = []
    for context, group in groups.items():
        total_counts = Counter(row.get("target_high", "") for row in group)
        by_row: dict[str, Counter[str]] = defaultdict(Counter)
        for row in group:
            by_row[row.get("row_id", "")][row.get("target_high", "")] += 1
        peer_high_by_row: dict[str, str] = {}
        for row_id, counts in by_row.items():
            peer_counts = total_counts.copy()
            peer_counts.subtract(counts)
            peer_counts = Counter({value: count for value, count in peer_counts.items() if count > 0})
            if len(peer_counts) == 1:
                peer_high_by_row[row_id] = next(iter(peer_counts))
        for row in group:
            row_id = row.get("row_id", "")
            predicted_high = peer_high_by_row.get(row_id)
            if predicted_high is None or predicted_high != row.get("target_high", ""):
                continue
            output_row = {field: row.get(field, "") for field in BASE_SLOT_FIELDNAMES}
            output_row["predicted_high"] = predicted_high
            output_row["high_context"] = "|".join(context)
            output.append(output_row)
    output.sort(
        key=lambda row: (
            str(row.get("row_id", "")),
            int_value(row, "target_offset"),
        )
    )
    for index, row in enumerate(output, start=1):
        row["rank"] = index
    return output


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
            f"{target_kind}_sequence_high_safe_false_free"
            if false_free
            else f"{target_kind}_sequence_high_safe_noisy"
            if predicted
            else f"{target_kind}_sequence_high_safe_no_predictions"
        ),
    }


def low_feature_sets(max_features: int) -> list[tuple[str, ...]]:
    output: list[tuple[str, ...]] = []
    for feature_set in feature_sets(max_features):
        output.append(feature_set)
    if max_features >= 1:
        output.append(("predicted_high",))
        output.append(("high_context",))
    if max_features >= 2:
        output.extend(("predicted_high", feature) for feature in BASE_FEATURES)
        output.extend(("high_context", feature) for feature in BASE_FEATURES)
    if max_features >= 3:
        output.extend(("predicted_high", *feature_set) for feature_set in feature_sets(2))
        output.extend(("high_context", *feature_set) for feature_set in feature_sets(2))
    seen: set[tuple[str, ...]] = set()
    unique: list[tuple[str, ...]] = []
    for feature_set in output:
        if feature_set not in seen:
            unique.append(feature_set)
            seen.add(feature_set)
    return unique


def build_rules(slots: list[dict[str, object]], max_features: int) -> list[dict[str, object]]:
    rules: list[dict[str, object]] = []
    for target_kind in ("full", "target_low"):
        for features in low_feature_sets(max_features):
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


def false_free_count(rules: list[dict[str, object]], target_kind: str) -> int:
    return sum(
        1
        for row in rules
        if row.get("target_kind") == target_kind and int_value(row, "false_free") > 0
    )


def build(
    slot_rows: list[dict[str, str]],
    summary_rows: list[dict[str, str]],
    *,
    high_feature_set: str,
    max_features: int,
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    high_features = parse_high_features(summary_rows, high_feature_set)
    slots = high_safe_slots(slot_rows, high_features)
    rules = build_rules(slots, max_features)
    full_best = best_rule(rules, "full")
    full_false_free = best_false_free_rule(rules, "full")
    low_best = best_rule(rules, "target_low")
    low_false_free = best_false_free_rule(rules, "target_low")
    summary = {
        "scope": "total",
        "slot_rows": len(slot_rows),
        "source_profile_rows": len({row.get("row_id", "") for row in slot_rows}),
        "high_feature_set": "+".join(high_features),
        "high_safe_slots": len(slots),
        "high_safe_rows": len({row.get("row_id", "") for row in slots}),
        "low_feature_sets": len(low_feature_sets(max_features)),
        "full_false_free_sets": false_free_count(rules, "full"),
        "full_best_false_free_slots": full_false_free.get("exact_slots", 0),
        "full_best_exact_slots": full_best.get("exact_slots", 0),
        "full_best_false_slots": full_best.get("false_slots", 0),
        "full_best_feature_set": full_best.get("feature_set", ""),
        "target_low_false_free_sets": false_free_count(rules, "target_low"),
        "target_low_best_false_free_slots": low_false_free.get("exact_slots", 0),
        "target_low_best_exact_slots": low_best.get("exact_slots", 0),
        "target_low_best_false_slots": low_best.get("false_slots", 0),
        "target_low_best_feature_set": low_best.get("feature_set", ""),
        "promotion_candidate_bytes": 0,
        "promotion_ready_bytes": 0,
        "issue_rows": 0,
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
table {{ border-collapse: collapse; width: 100%; min-width: 1800px; }}
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
  <div class="box"><div class="num">{summary['high_safe_slots']}</div><div class="muted">high-safe slots</div></div>
  <div class="box"><div class="num">{summary['high_safe_rows']}</div><div class="muted">high-safe rows</div></div>
  <div class="box"><div class="num">{summary['target_low_best_false_free_slots']}</div><div class="muted">target-low false-free slots</div></div>
  <div class="box"><div class="num">{summary['target_low_best_false_slots']}</div><div class="muted">best target-low false slots</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Rules</h2>{render_table(top_rules, RULE_FIELDNAMES)}</div>
<div class="panel"><h2>High-safe slots</h2>{render_table(slots, SLOT_FIELDNAMES)}</div>
<script type="application/json" id="gradient-sequence-high-safe-low-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe low/full bytes after sequence high-safe selection.")
    parser.add_argument("--slots", type=Path, default=DEFAULT_SLOTS)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--high-feature-set", default="")
    parser.add_argument("--max-features", type=int, default=3)
    parser.add_argument("--title", default="Lands of Lore II .tex Gradient Sequence High-Safe Low Probe")
    args = parser.parse_args()

    summary, slots, rules = build(
        read_csv(args.slots),
        read_csv(args.summary),
        high_feature_set=args.high_feature_set,
        max_features=args.max_features,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "slots.csv", SLOT_FIELDNAMES, slots)
    write_csv(args.output / "rules.csv", RULE_FIELDNAMES, rules)
    (args.output / "index.html").write_text(build_html(summary, slots, rules, args.title))

    print(f"High-safe slots: {summary['high_safe_slots']}")
    print(f"High-safe rows: {summary['high_safe_rows']}")
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
