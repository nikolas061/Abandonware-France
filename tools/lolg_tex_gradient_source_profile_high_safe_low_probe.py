#!/usr/bin/env python3
"""Probe low-nibble resolvers after source-profile high-nibble selection."""

from __future__ import annotations

import argparse
import csv
import html
import itertools
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_opcode_probe import int_value, write_csv


DEFAULT_SLOTS = Path("output/tex_gradient_source_profile_high_low/slots.csv")
DEFAULT_SUMMARY = Path("output/tex_gradient_source_profile_high_low/summary.csv")
DEFAULT_OUTPUT = Path("output/tex_gradient_source_profile_high_safe_low")

LOW_FEATURES = [
    "pool",
    "offset_delta",
    "offset_delta_bucket",
    "gradient_class",
    "top_nibble",
    "length_band8",
    "source_byte",
    "source_high",
    "source_low",
    "source_zero",
    "rel_mod4",
    "rel_mod8",
    "rel_mod16",
    "x_mod8",
    "y_mod4",
    "y_mod8",
    "predicted_high",
    "high_delta",
    "high_context",
]

SUMMARY_FIELDNAMES = [
    "scope",
    "slot_rows",
    "source_profile_rows",
    "high_feature_set",
    "high_safe_slots",
    "high_safe_rows",
    "low_feature_sets",
    "target_low_false_free_sets",
    "target_low_best_exact_slots",
    "target_low_best_false_slots",
    "target_low_best_feature_set",
    "delta_low_false_free_sets",
    "delta_low_best_exact_slots",
    "delta_low_best_false_slots",
    "delta_low_best_feature_set",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

SLOT_FIELDNAMES = [
    "rank",
    "row_id",
    "archive",
    "pcx_name",
    "frontier_id",
    "start",
    "end",
    "target_offset",
    "relative_offset",
    "pool",
    "source_profile_offset",
    "offset_delta",
    "offset_delta_bucket",
    "gradient_class",
    "top_nibble",
    "length_band8",
    "source_byte",
    "source_high",
    "source_low",
    "source_zero",
    "target_byte",
    "target_high",
    "target_low",
    "full_delta",
    "high_delta",
    "low_delta",
    "rel_mod4",
    "rel_mod8",
    "rel_mod16",
    "x_mod8",
    "y_mod4",
    "y_mod8",
    "predicted_high",
    "high_context",
]

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
    "false_free",
    "sample_predictions",
    "verdict",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def ratio(numerator: int, denominator: int) -> str:
    return f"{numerator / denominator:.6f}" if denominator else "0.000000"


def feature_sets(max_features: int) -> list[tuple[str, ...]]:
    output: list[tuple[str, ...]] = []
    for size in range(1, max_features + 1):
        output.extend(itertools.combinations(LOW_FEATURES, size))
    return output


def context_for(row: dict[str, object], features: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(str(row.get(feature, "")) for feature in features)


def parse_feature_set(summary_rows: list[dict[str, str]], explicit: str) -> tuple[str, ...]:
    if explicit:
        return tuple(part for part in explicit.split("+") if part)
    if not summary_rows:
        raise ValueError("missing source-profile high/low summary rows")
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
        total_counts = Counter(int_value(row, "high_delta") for row in group)
        by_row: dict[str, Counter[int]] = defaultdict(Counter)
        for row in group:
            by_row[row.get("row_id", "")][int_value(row, "high_delta")] += 1
        peer_delta_by_row: dict[str, int] = {}
        for row_id, counts in by_row.items():
            peer_counts = total_counts.copy()
            peer_counts.subtract(counts)
            peer_counts = Counter({delta: count for delta, count in peer_counts.items() if count > 0})
            if len(peer_counts) == 1:
                peer_delta_by_row[row_id] = next(iter(peer_counts))
        for row in group:
            row_id = row.get("row_id", "")
            delta = peer_delta_by_row.get(row_id)
            if delta is None:
                continue
            predicted_high = (int(row.get("source_high", "0"), 16) + delta) & 0x0F
            if predicted_high != int(row.get("target_high", "0"), 16):
                continue
            output_row = {field: row.get(field, "") for field in SLOT_FIELDNAMES if field not in {"rank"}}
            output_row["rank"] = 0
            output_row["predicted_high"] = f"{predicted_high:x}"
            output_row["high_context"] = "|".join(str(part) for part in context)
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


def prediction_value(slot: dict[str, object], target_kind: str, value: int) -> int:
    if target_kind == "target_low":
        return value
    if target_kind == "delta_low":
        return (int(str(slot.get("source_low", "0")), 16) + value) & 0x0F
    raise ValueError(target_kind)


def target_low(slot: dict[str, object]) -> int:
    return int(str(slot.get("target_low", "0")), 16)


def evaluate_rule(slots: list[dict[str, object]], features: tuple[str, ...], target_kind: str) -> dict[str, object]:
    value_field = "target_low" if target_kind == "target_low" else "low_delta"
    groups: dict[tuple[str, ...], list[dict[str, object]]] = defaultdict(list)
    for slot in slots:
        groups[context_for(slot, features)].append(slot)

    exact = 0
    false = 0
    predicted = 0
    predicted_groups: set[tuple[str, ...]] = set()
    samples: list[str] = []
    for context, group in groups.items():
        total_counts = Counter(int(str(slot.get(value_field, "0")), 16) if value_field == "target_low" else int_value(slot, value_field) for slot in group)
        by_row: dict[str, Counter[int]] = defaultdict(Counter)
        for slot in group:
            value = int(str(slot.get(value_field, "0")), 16) if value_field == "target_low" else int_value(slot, value_field)
            by_row[str(slot.get("row_id", ""))][value] += 1
        peer_value_by_row: dict[str, int] = {}
        for row_id, counts in by_row.items():
            peer_counts = total_counts.copy()
            peer_counts.subtract(counts)
            peer_counts = Counter({value: count for value, count in peer_counts.items() if count > 0})
            if len(peer_counts) == 1:
                peer_value_by_row[row_id] = next(iter(peer_counts))
        for slot in group:
            value = peer_value_by_row.get(str(slot.get("row_id", "")))
            if value is None:
                continue
            predicted += 1
            predicted_groups.add(context)
            if prediction_value(slot, target_kind, value) == target_low(slot):
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
        "false_free": 1 if false_free else 0,
        "sample_predictions": "|".join(samples),
        "verdict": (
            f"{target_kind}_false_free"
            if false_free
            else f"{target_kind}_noisy"
            if predicted
            else f"{target_kind}_no_predictions"
        ),
    }


def build_rules(slots: list[dict[str, object]], max_features: int) -> list[dict[str, object]]:
    rules: list[dict[str, object]] = []
    for target_kind in ("target_low", "delta_low"):
        for features in feature_sets(max_features):
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
    high_features = parse_feature_set(summary_rows, high_feature_set)
    slots = high_safe_slots(slot_rows, high_features)
    rules = build_rules(slots, max_features)
    target_best = best_rule(rules, "target_low")
    delta_best = best_rule(rules, "delta_low")
    summary = {
        "scope": "total",
        "slot_rows": len(slot_rows),
        "source_profile_rows": len({row.get("row_id", "") for row in slot_rows}),
        "high_feature_set": "+".join(high_features),
        "high_safe_slots": len(slots),
        "high_safe_rows": len({row.get("row_id", "") for row in slots}),
        "low_feature_sets": len(feature_sets(max_features)),
        "target_low_false_free_sets": false_free_count(rules, "target_low"),
        "target_low_best_exact_slots": target_best.get("exact_slots", 0),
        "target_low_best_false_slots": target_best.get("false_slots", 0),
        "target_low_best_feature_set": target_best.get("feature_set", ""),
        "delta_low_false_free_sets": false_free_count(rules, "delta_low"),
        "delta_low_best_exact_slots": delta_best.get("exact_slots", 0),
        "delta_low_best_false_slots": delta_best.get("false_slots", 0),
        "delta_low_best_feature_set": delta_best.get("feature_set", ""),
        "promotion_candidate_bytes": 0,
        "promotion_ready_bytes": 0,
        "issue_rows": 0,
    }
    return summary, slots, rules


def render_table(rows: list[dict[str, object]], fields: list[str], limit: int = 220) -> str:
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
    top_rules = sorted(
        rules,
        key=lambda row: (
            str(row["target_kind"]),
            -int_value(row, "false_free"),
            -int_value(row, "exact_slots"),
            int_value(row, "false_slots"),
            int_value(row, "feature_count"),
        ),
    )[:180]
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body {{ margin: 2rem; background: #101214; color: #edf5f4; font: 14px/1.45 system-ui, sans-serif; }}
table {{ border-collapse: collapse; width: 100%; min-width: 1600px; }}
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
  <div class="box"><div class="num">{summary['target_low_false_free_sets']}</div><div class="muted">target low false-free sets</div></div>
  <div class="box"><div class="num">{summary['delta_low_false_free_sets']}</div><div class="muted">delta low false-free sets</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Rules</h2>{render_table(top_rules, RULE_FIELDNAMES)}</div>
<div class="panel"><h2>High-safe slots</h2>{render_table(slots, SLOT_FIELDNAMES)}</div>
<script type="application/json" id="gradient-source-profile-high-safe-low-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe low nibbles after source-profile high-safe selection.")
    parser.add_argument("--slots", type=Path, default=DEFAULT_SLOTS)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--high-feature-set", default="")
    parser.add_argument("--max-features", type=int, default=4)
    parser.add_argument("--title", default="Lands of Lore II .tex Gradient Source Profile High-Safe Low Probe")
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
    print(f"Target-low false-free sets: {summary['target_low_false_free_sets']}")
    print(f"Delta-low false-free sets: {summary['delta_low_false_free_sets']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
