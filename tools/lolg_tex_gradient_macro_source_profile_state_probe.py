#!/usr/bin/env python3
"""Probe gradient low/full bytes with macro state plus source-profile features."""

from __future__ import annotations

import argparse
import csv
import html
import itertools
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_opcode_probe import write_csv


DEFAULT_SLOTS = Path("output/tex_gradient_source_profile_high_low/slots.csv")
DEFAULT_MACRO_ROWS = Path("output/tex_gradient_macro_state_cluster/rows.csv")
DEFAULT_OUTPUT = Path("output/tex_gradient_macro_source_profile_state")

MACRO_SOURCE_FIELDS = [
    "span_phase4",
    "op_phase4",
    "op_phase8",
    "frontier_count_bucket",
    "frontier_position",
    "prev_op_gap",
    "next_op_gap",
    "fixture_rule",
    "fixture_opcode_pair",
    "fixture_hi_pair",
    "fixture_opcode_delta",
    "fixture_skip_bucket",
    "control_anchor_mod64",
    "start_anchor_mod64",
    "length_band8",
    "top_nibble",
    "gradient_class",
    "dominant_delta",
]

MACRO_FEATURES = [f"macro_{field}" for field in MACRO_SOURCE_FIELDS]

SOURCE_FEATURES = [
    "pool",
    "offset_delta_bucket",
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
]

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "slot_rows",
    "joined_slots",
    "missing_macro_slots",
    "source_profile_rows",
    "macro_rows",
    "feature_sets",
    "full_false_free_feature_sets",
    "full_best_false_free_slots",
    "full_best_exact_slots",
    "full_best_false_slots",
    "full_best_feature_set",
    "target_low_false_free_feature_sets",
    "target_low_best_false_free_slots",
    "target_low_best_exact_slots",
    "target_low_best_false_slots",
    "target_low_best_feature_set",
    "target_low_low_false_exact_slots",
    "target_low_low_false_false_slots",
    "target_low_low_false_feature_set",
    "low_delta_false_free_feature_sets",
    "low_delta_best_false_free_slots",
    "low_delta_best_exact_slots",
    "low_delta_best_false_slots",
    "low_delta_best_feature_set",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

FOCUSED_FEATURE_SETS = [
    (
        "macro_fixture_hi_pair",
        "macro_gradient_class",
        "source_high",
        "rel_mod16",
    ),
    (
        "macro_fixture_hi_pair",
        "macro_gradient_class",
        "source_byte",
        "rel_mod16",
    ),
    (
        "macro_fixture_hi_pair",
        "macro_top_nibble",
        "source_high",
        "rel_mod16",
    ),
    (
        "macro_fixture_hi_pair",
        "macro_gradient_class",
        "source_low",
        "rel_mod16",
    ),
    (
        "macro_fixture_skip_bucket",
        "macro_length_band8",
        "source_high",
        "rel_mod16",
    ),
    (
        "macro_fixture_opcode_pair",
        "macro_length_band8",
        "source_high",
        "rel_mod16",
    ),
    (
        "macro_fixture_opcode_pair",
        "macro_top_nibble",
        "source_high",
        "rel_mod16",
    ),
    (
        "macro_fixture_hi_pair",
        "macro_dominant_delta",
        "source_byte",
        "rel_mod16",
    ),
    (
        "macro_span_phase4",
        "macro_next_op_gap",
        "offset_delta_bucket",
        "source_high",
    ),
    (
        "macro_prev_op_gap",
        "macro_control_anchor_mod64",
        "source_high",
        "y_mod8",
    ),
    (
        "macro_next_op_gap",
        "macro_control_anchor_mod64",
        "source_high",
        "source_zero",
    ),
    (
        "macro_prev_op_gap",
        "macro_start_anchor_mod64",
        "source_low",
        "y_mod8",
    ),
    (
        "macro_frontier_position",
        "macro_start_anchor_mod64",
        "source_low",
        "y_mod4",
    ),
    (
        "macro_control_anchor_mod64",
        "macro_top_nibble",
        "source_byte",
        "x_mod8",
    ),
    (
        "macro_fixture_opcode_pair",
        "macro_next_op_gap",
        "pool",
        "source_high",
    ),
    (
        "macro_fixture_hi_pair",
        "macro_top_nibble",
        "source_low",
        "rel_mod16",
    ),
    (
        "macro_fixture_rule",
        "macro_fixture_hi_pair",
        "source_low",
        "rel_mod16",
    ),
    (
        "macro_fixture_hi_pair",
        "macro_fixture_opcode_delta",
        "source_low",
        "rel_mod16",
    ),
    (
        "macro_fixture_hi_pair",
        "macro_fixture_skip_bucket",
        "source_low",
        "rel_mod16",
    ),
    (
        "macro_fixture_opcode_pair",
        "source_byte",
        "rel_mod4",
    ),
    (
        "macro_fixture_skip_bucket",
        "macro_gradient_class",
        "source_high",
        "rel_mod16",
    ),
    (
        "macro_fixture_hi_pair",
        "macro_length_band8",
        "source_high",
        "rel_mod16",
    ),
    (
        "macro_fixture_opcode_pair",
        "macro_gradient_class",
        "source_high",
        "rel_mod16",
    ),
    (
        "macro_next_op_gap",
        "macro_top_nibble",
        "source_high",
        "rel_mod16",
    ),
    (
        "macro_fixture_hi_pair",
        "macro_gradient_class",
        "source_zero",
        "rel_mod16",
    ),
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
    *MACRO_FEATURES,
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
    "predicted_rows",
    "false_free",
    "sample_predictions",
    "verdict",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def int_value(row: dict[str, object], field: str, default: int = 0) -> int:
    raw = row.get(field, "")
    if raw == "":
        return default
    try:
        return int(str(raw), 0)
    except (TypeError, ValueError):
        return default


def ratio(numerator: int, denominator: int) -> str:
    return f"{numerator / denominator:.6f}" if denominator else "0.000000"


def row_key(row: dict[str, object]) -> tuple[str, str, str, str, str]:
    return (
        str(row.get("archive", "")),
        str(row.get("pcx_name", "")),
        str(row.get("frontier_id", "")),
        str(row.get("start", "")),
        str(row.get("end", "")),
    )


def join_slots(
    slot_rows: list[dict[str, str]], macro_rows: list[dict[str, str]]
) -> tuple[list[dict[str, object]], list[str]]:
    macro_by_key = {row_key(row): row for row in macro_rows}
    joined: list[dict[str, object]] = []
    issues: list[str] = []
    for slot in slot_rows:
        macro = macro_by_key.get(row_key(slot))
        if macro is None:
            issues.append(f"missing_macro:{'|'.join(row_key(slot))}")
            continue
        output = {field: slot.get(field, "") for field in SLOT_FIELDNAMES if not field.startswith("macro_")}
        for field in MACRO_SOURCE_FIELDS:
            output[f"macro_{field}"] = macro.get(field, "")
        joined.append(output)
    for index, row in enumerate(joined, start=1):
        row["rank"] = index
    return joined, issues


def feature_sets(max_features: int, *, exhaustive: bool = False) -> list[tuple[str, ...]]:
    output: list[tuple[str, ...]] = []
    features = [*MACRO_FEATURES, *SOURCE_FEATURES]
    generated_max_features = max_features if exhaustive else min(max_features, 3)
    for size in range(2, generated_max_features + 1):
        for combo in itertools.combinations(features, size):
            has_macro = any(feature.startswith("macro_") for feature in combo)
            has_source = any(not feature.startswith("macro_") for feature in combo)
            if has_macro and has_source:
                output.append(combo)
    if not exhaustive:
        seen = set(output)
        for combo in FOCUSED_FEATURE_SETS:
            if len(combo) <= max_features and combo not in seen:
                output.append(combo)
                seen.add(combo)
    return output


def context_for(row: dict[str, object], features: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(str(row.get(feature, "")) for feature in features)


def target_value(slot: dict[str, object], target_kind: str) -> int:
    if target_kind == "full_delta":
        return int(str(slot.get("target_byte", "0")), 16)
    if target_kind in {"target_low", "low_delta"}:
        return int(str(slot.get("target_low", "0")), 16)
    raise ValueError(target_kind)


def predicted_value(slot: dict[str, object], target_kind: str, value: int) -> int:
    if target_kind == "full_delta":
        source = int(str(slot.get("source_byte", "0")), 16)
        return (source + value) & 0xFF
    if target_kind == "target_low":
        return value
    if target_kind == "low_delta":
        source_low = int(str(slot.get("source_low", "0")), 16)
        return (source_low + value) & 0x0F
    raise ValueError(target_kind)


def value_field(target_kind: str) -> str:
    if target_kind == "full_delta":
        return "full_delta"
    if target_kind == "target_low":
        return "target_low"
    if target_kind == "low_delta":
        return "low_delta"
    raise ValueError(target_kind)


def observed_value(slot: dict[str, object], target_kind: str) -> int:
    field = value_field(target_kind)
    if field == "target_low":
        return int(str(slot.get(field, "0")), 16)
    return int_value(slot, field)


def evaluate_rule(
    slots: list[dict[str, object]], features: tuple[str, ...], target_kind: str
) -> dict[str, object]:
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
        total_counts = Counter(observed_value(slot, target_kind) for slot in group)
        by_row: dict[str, Counter[int]] = defaultdict(Counter)
        for slot in group:
            by_row[str(slot.get("row_id", ""))][observed_value(slot, target_kind)] += 1

        peer_value_by_row: dict[str, int] = {}
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
            if predicted_value(slot, target_kind, value) == target_value(slot, target_kind):
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
            f"{target_kind}_macro_source_profile_false_free"
            if false_free
            else f"{target_kind}_macro_source_profile_noisy"
            if predicted
            else f"{target_kind}_macro_source_profile_no_predictions"
        ),
    }


def build_rules(
    slots: list[dict[str, object]], max_features: int, *, exhaustive: bool
) -> list[dict[str, object]]:
    rules: list[dict[str, object]] = []
    for target_kind in ("full_delta", "target_low", "low_delta"):
        for features in feature_sets(max_features, exhaustive=exhaustive):
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
    rules: list[dict[str, object]], target_kind: str, max_false: int = 3
) -> dict[str, object]:
    candidates = [
        row
        for row in rules
        if row.get("target_kind") == target_kind and 0 < int_value(row, "false_slots") <= max_false
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
    slot_rows: list[dict[str, str]],
    macro_rows: list[dict[str, str]],
    *,
    max_features: int,
    exhaustive: bool,
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    slots, issues = join_slots(slot_rows, macro_rows)
    candidates = feature_sets(max_features, exhaustive=exhaustive)
    rules = build_rules(slots, max_features, exhaustive=exhaustive)
    full_best = best_rule(rules, "full_delta")
    full_false_free = best_false_free_rule(rules, "full_delta")
    target_best = best_rule(rules, "target_low")
    target_false_free = best_false_free_rule(rules, "target_low")
    target_low_false = best_low_false_rule(rules, "target_low")
    low_delta_best = best_rule(rules, "low_delta")
    low_delta_false_free = best_false_free_rule(rules, "low_delta")
    summary = {
        "scope": "total",
        "candidate_mode": "exhaustive" if exhaustive else "focused",
        "slot_rows": len(slot_rows),
        "joined_slots": len(slots),
        "missing_macro_slots": len(issues),
        "source_profile_rows": len({row.get("row_id", "") for row in slots}),
        "macro_rows": len(macro_rows),
        "feature_sets": len(candidates),
        "full_false_free_feature_sets": false_free_count(rules, "full_delta"),
        "full_best_false_free_slots": full_false_free.get("exact_slots", 0),
        "full_best_exact_slots": full_best.get("exact_slots", 0),
        "full_best_false_slots": full_best.get("false_slots", 0),
        "full_best_feature_set": full_best.get("feature_set", ""),
        "target_low_false_free_feature_sets": false_free_count(rules, "target_low"),
        "target_low_best_false_free_slots": target_false_free.get("exact_slots", 0),
        "target_low_best_exact_slots": target_best.get("exact_slots", 0),
        "target_low_best_false_slots": target_best.get("false_slots", 0),
        "target_low_best_feature_set": target_best.get("feature_set", ""),
        "target_low_low_false_exact_slots": target_low_false.get("exact_slots", 0),
        "target_low_low_false_false_slots": target_low_false.get("false_slots", 0),
        "target_low_low_false_feature_set": target_low_false.get("feature_set", ""),
        "low_delta_false_free_feature_sets": false_free_count(rules, "low_delta"),
        "low_delta_best_false_free_slots": low_delta_false_free.get("exact_slots", 0),
        "low_delta_best_exact_slots": low_delta_best.get("exact_slots", 0),
        "low_delta_best_false_slots": low_delta_best.get("false_slots", 0),
        "low_delta_best_feature_set": low_delta_best.get("feature_set", ""),
        "promotion_candidate_bytes": 0,
        "promotion_ready_bytes": 0,
        "issue_rows": len(issues),
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
    top_rules = sorted(
        rules,
        key=lambda row: (
            str(row["target_kind"]),
            -int_value(row, "false_free"),
            -int_value(row, "exact_slots"),
            int_value(row, "false_slots"),
            int_value(row, "feature_count"),
        ),
    )[:240]
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
  <div class="box"><div class="num">{summary['joined_slots']}</div><div class="muted">joined slots</div></div>
  <div class="box"><div class="num">{summary['full_best_false_free_slots']}</div><div class="muted">full false-free slots</div></div>
  <div class="box"><div class="num">{summary['target_low_best_false_free_slots']}</div><div class="muted">target-low false-free slots</div></div>
  <div class="box"><div class="num">{summary['low_delta_best_false_free_slots']}</div><div class="muted">low-delta false-free slots</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Rules</h2>{render_table(top_rules, RULE_FIELDNAMES)}</div>
<div class="panel"><h2>Joined slots</h2>{render_table(slots, SLOT_FIELDNAMES)}</div>
<script type="application/json" id="gradient-macro-source-profile-state-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe gradient macro state plus source-profile transforms.")
    parser.add_argument("--slots", type=Path, default=DEFAULT_SLOTS)
    parser.add_argument("--macro-rows", type=Path, default=DEFAULT_MACRO_ROWS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-features", type=int, default=4)
    parser.add_argument("--exhaustive", action="store_true")
    parser.add_argument("--title", default="Lands of Lore II .tex Gradient Macro Source-Profile State Probe")
    args = parser.parse_args()

    summary, slots, rules = build(
        read_csv(args.slots),
        read_csv(args.macro_rows),
        max_features=args.max_features,
        exhaustive=args.exhaustive,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "slots.csv", SLOT_FIELDNAMES, slots)
    write_csv(args.output / "rules.csv", RULE_FIELDNAMES, rules)
    (args.output / "index.html").write_text(build_html(summary, slots, rules, args.title))

    print(f"Joined slots: {summary['joined_slots']}")
    print(f"Feature sets: {summary['feature_sets']}")
    print(f"Full false-free feature sets: {summary['full_false_free_feature_sets']}")
    print(f"Best full rule: {summary['full_best_exact_slots']} exact / {summary['full_best_false_slots']} false")
    print(f"Target-low false-free feature sets: {summary['target_low_false_free_feature_sets']}")
    print(
        "Best target-low rule: "
        f"{summary['target_low_best_exact_slots']} exact / {summary['target_low_best_false_slots']} false"
    )
    print(f"Low-delta false-free feature sets: {summary['low_delta_false_free_feature_sets']}")
    print(
        "Best low-delta rule: "
        f"{summary['low_delta_best_exact_slots']} exact / {summary['low_delta_best_false_slots']} false"
    )
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
