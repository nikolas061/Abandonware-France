#!/usr/bin/env python3
"""Probe non-oracle prefix bootstrap candidates for mixed-value payloads."""

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
)
from lolg_tex_micro_mixed_value_payload_predictor_probe import int_value, ratio, strict_prediction, write_csv
from lolg_tex_micro_mixed_value_payload_sequence_candidate_review import (
    DEFAULT_OUTPUT as DEFAULT_SEQUENCE_REVIEW_OUTPUT,
)
from lolg_tex_micro_mixed_value_payload_source_profile_probe import DEFAULT_REPLAY_FIXTURES
from lolg_tex_micro_mixed_value_payload_state_opcode_probe import (
    DEFAULT_CONTROL_ROWS,
    DEFAULT_FIXTURES,
    DEFAULT_INPUT_ROWS,
    build_entries,
    read_csv,
)


DEFAULT_SEQUENCE_REVIEW_ROWS = DEFAULT_SEQUENCE_REVIEW_OUTPUT / "rows.csv"
DEFAULT_OUTPUT = Path("output/tex_micro_mixed_value_payload_prefix_bootstrap")

FEATURES = [
    "offset_exact",
    "pos8",
    "pos16",
    "tail8",
    "signal",
    "control",
    "dominant",
    "signal_byte",
    "signal_high",
    "signal_low",
    "signal_class",
    "signal_delta",
    "control_byte",
    "control_high",
    "control_low",
    "control_class",
    "control_delta",
    "prefix_byte",
    "prefix_high",
    "prefix_class",
    "fragment_byte",
    "fragment_high",
    "fragment_class",
    "best_pool",
    "best_b0",
    "best_b1",
    "best_b2",
    "best_d0",
    "best_d2",
    "compressed_b0",
    "compressed_b1",
    "compressed_d0",
    "profile_b0",
    "profile_b1",
    "profile_d0",
]

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "prefix_slots",
    "features",
    "feature_sets",
    "false_free_byte_sets",
    "best_false_free_byte_feature_set",
    "best_false_free_byte_slots",
    "best_false_free_byte_unknown_slots",
    "union_candidate_slots",
    "union_candidate_rows",
    "union_conflict_slots",
    "sequence_prerequisite_bytes",
    "sequence_prerequisite_covered_bytes",
    "sequence_candidate_bytes",
    "sequence_candidate_unlocked_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

RULE_FIELDNAMES = [
    "rank",
    "feature_set",
    "feature_count",
    "contexts",
    "loo_correct_slots",
    "loo_false_slots",
    "loo_unknown_slots",
    "loo_precision",
    "predicted_values",
    "sample_context",
    "sample_prediction",
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
    "sequence_prerequisite",
    "verdict",
]


def feature_combinations(max_features: int) -> list[tuple[str, ...]]:
    output: list[tuple[str, ...]] = []
    for size in range(1, max_features + 1):
        output.extend(itertools.combinations(FEATURES, size))
    return output


def enrich_entries(entries: list[dict[str, object]], input_rows: list[dict[str, str]]) -> None:
    for entry in entries:
        source_row = input_rows[int(entry["row_index"])]
        offset = int(entry["offset"])
        length = int(entry["length"])
        entry["dominant"] = source_row.get("dominant_byte_hex", "")
        entry["signal"] = source_row.get("best_signal_key", "")
        entry["control"] = source_row.get("control_ref_mod64", "")
        entry["offset_exact"] = str(offset)
        entry["absolute_offset"] = int_value(source_row, "start") + offset
        entry["tail8"] = str(length - 1 - offset) if length - 1 - offset < 8 else "body"


def evaluate_rule(
    entries: list[dict[str, object]],
    feature_set: tuple[str, ...],
) -> tuple[dict[str, object], list[tuple[tuple[int, int], str, dict[str, object]]]]:
    all_counts: dict[tuple[object, ...], Counter[str]] = defaultdict(Counter)
    row_counts: dict[tuple[int, tuple[object, ...]], Counter[str]] = defaultdict(Counter)
    for entry in entries:
        context = tuple(entry[feature] for feature in feature_set)
        value = str(entry["byte"])
        all_counts[context][value] += 1
        row_counts[(int(entry["row_index"]), context)][value] += 1

    correct = 0
    false = 0
    unknown = 0
    predictions: list[tuple[tuple[int, int], str, dict[str, object]]] = []
    predicted_values: Counter[str] = Counter()
    sample_context = ""
    sample_prediction = ""
    for entry in entries:
        context = tuple(entry[feature] for feature in feature_set)
        train_counts = all_counts[context].copy()
        train_counts.subtract(row_counts[(int(entry["row_index"]), context)])
        train_counts += Counter()
        prediction = strict_prediction(train_counts)
        if prediction is None:
            unknown += 1
            continue
        if not sample_context:
            sample_context = "|".join(str(part) for part in context)
            sample_prediction = prediction
        if prediction == str(entry["byte"]):
            correct += 1
            predictions.append(((int(entry["row_index"]), int(entry["offset"])), prediction, entry))
            predicted_values[prediction] += 1
        else:
            false += 1

    row = {
        "rank": 0,
        "feature_set": "+".join(feature_set),
        "feature_count": len(feature_set),
        "contexts": len(all_counts),
        "loo_correct_slots": correct,
        "loo_false_slots": false,
        "loo_unknown_slots": unknown,
        "loo_precision": ratio(correct, correct + false),
        "predicted_values": "|".join(f"{value}:{count}" for value, count in predicted_values.most_common(8)),
        "sample_context": sample_context,
        "sample_prediction": sample_prediction,
    }
    return row, predictions


def sequence_prerequisite_slots(review_rows: list[dict[str, str]]) -> tuple[set[tuple[int, int]], dict[int, set[tuple[int, int]]]]:
    slots: set[tuple[int, int]] = set()
    by_candidate: dict[int, set[tuple[int, int]]] = {}
    for row in review_rows:
        row_index = int_value(row, "row_index")
        start = int_value(row, "start")
        candidate_slots: set[tuple[int, int]] = set()
        for absolute_text in row.get("prerequisite_offsets", "").split("|"):
            if not absolute_text:
                continue
            relative = int(absolute_text) - start
            slot = (row_index, relative)
            slots.add(slot)
            candidate_slots.add(slot)
        by_candidate[int_value(row, "rank")] = candidate_slots
    return slots, by_candidate


def build(
    input_rows: list[dict[str, str]],
    control_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    replay_rows: list[dict[str, str]],
    source_profile_rows: list[dict[str, str]],
    sequence_review_rows: list[dict[str, str]],
    *,
    max_features: int,
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    _summary_seed, _row_outputs, entries, issues = build_entries(input_rows, control_rows, fixture_rows)
    issues.extend(add_external_features(entries, input_rows, source_profile_rows, fixture_rows, replay_rows))
    enrich_entries(entries, input_rows)
    prefix_entries = [entry for entry in entries if int(entry["offset"]) < 2]

    rules: list[dict[str, object]] = []
    slot_predictions: dict[tuple[int, int], list[tuple[str, str, dict[str, object]]]] = defaultdict(list)
    for feature_set in feature_combinations(max_features):
        row, predictions = evaluate_rule(prefix_entries, feature_set)
        if int_value(row, "loo_correct_slots") > 0 and int_value(row, "loo_false_slots") == 0:
            rules.append(row)
            for slot, prediction, entry in predictions:
                slot_predictions[slot].append((prediction, str(row["feature_set"]), entry))

    rules.sort(
        key=lambda row: (
            -int_value(row, "loo_correct_slots"),
            int_value(row, "loo_unknown_slots"),
            int_value(row, "feature_count"),
            str(row["feature_set"]),
        )
    )
    for index, row in enumerate(rules, start=1):
        row["rank"] = index

    prerequisite_slots, prerequisites_by_candidate = sequence_prerequisite_slots(sequence_review_rows)
    slot_rows: list[dict[str, object]] = []
    conflict_slots = 0
    for slot, predictions in sorted(slot_predictions.items()):
        values = sorted({prediction for prediction, _rule, _entry in predictions})
        entry = predictions[0][2]
        if len(values) > 1:
            conflict_slots += 1
            verdict = "conflicted_prefix_candidate"
        elif slot in prerequisite_slots:
            verdict = "sequence_prerequisite_candidate"
        else:
            verdict = "prefix_candidate_review"
        slot_rows.append(
            {
                "rank": len(slot_rows) + 1,
                "row_index": slot[0],
                "archive": entry.get("archive", ""),
                "pcx_name": entry.get("pcx_name", ""),
                "frontier_id": entry.get("frontier_id", ""),
                "span_index": input_rows[slot[0]].get("span_index", ""),
                "op_index": input_rows[slot[0]].get("op_index", ""),
                "start": input_rows[slot[0]].get("start", ""),
                "end": input_rows[slot[0]].get("end", ""),
                "offset": slot[1],
                "absolute_offset": entry.get("absolute_offset", ""),
                "byte": entry.get("byte", ""),
                "predicted_values": "|".join(values),
                "rule_count": len(predictions),
                "sample_rules": "|".join(rule for _prediction, rule, _entry in predictions[:8]),
                "sequence_prerequisite": 1 if slot in prerequisite_slots else 0,
                "verdict": verdict,
            }
        )

    covered_prerequisites = prerequisite_slots.intersection(slot_predictions)
    unlocked_sequence_candidates = sum(
        1 for slots in prerequisites_by_candidate.values() if slots and slots.issubset(slot_predictions)
    )
    best_rule = rules[0] if rules else {}
    summary = {
        "scope": "total",
        "target_rows": len(input_rows),
        "prefix_slots": len(prefix_entries),
        "features": len(FEATURES),
        "feature_sets": len(feature_combinations(max_features)),
        "false_free_byte_sets": len(rules),
        "best_false_free_byte_feature_set": best_rule.get("feature_set", ""),
        "best_false_free_byte_slots": best_rule.get("loo_correct_slots", 0),
        "best_false_free_byte_unknown_slots": best_rule.get("loo_unknown_slots", 0),
        "union_candidate_slots": len(slot_rows),
        "union_candidate_rows": len({row["row_index"] for row in slot_rows}),
        "union_conflict_slots": conflict_slots,
        "sequence_prerequisite_bytes": len(prerequisite_slots),
        "sequence_prerequisite_covered_bytes": len(covered_prerequisites),
        "sequence_candidate_bytes": len(prerequisites_by_candidate),
        "sequence_candidate_unlocked_bytes": unlocked_sequence_candidates,
        "promotion_ready_bytes": 0,
        "issue_rows": len(issues),
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
table {{ border-collapse: collapse; width: 100%; min-width: 1500px; }}
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
  <div class="box"><div class="num">{summary['false_free_byte_sets']}</div><div class="muted">false-free byte rule sets</div></div>
  <div class="box"><div class="num">{summary['union_candidate_slots']}</div><div class="muted">union candidate slots</div></div>
  <div class="box"><div class="num">{summary['union_conflict_slots']}</div><div class="muted">union conflicts</div></div>
  <div class="box"><div class="num">{summary['sequence_prerequisite_covered_bytes']}/{summary['sequence_prerequisite_bytes']}</div><div class="muted">covered sequence prerequisites</div></div>
  <div class="box"><div class="num">{summary['sequence_candidate_unlocked_bytes']}</div><div class="muted">sequence candidates unlocked</div></div>
</div>
<div class="panel"><h2>Candidate slots</h2>{render_table(slots, SLOT_FIELDNAMES)}</div>
<div class="panel"><h2>False-free rules</h2>{render_table(rules, RULE_FIELDNAMES)}</div>
<script type="application/json" id="mixed-value-prefix-bootstrap-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe mixed-value prefix bootstrap candidates.")
    parser.add_argument("--input-rows", type=Path, default=DEFAULT_INPUT_ROWS)
    parser.add_argument("--control-rows", type=Path, default=DEFAULT_CONTROL_ROWS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--replay-fixtures", type=Path, default=DEFAULT_REPLAY_FIXTURES)
    parser.add_argument("--source-profile-rows", type=Path, default=DEFAULT_SOURCE_PROFILE_ROWS)
    parser.add_argument("--sequence-review-rows", type=Path, default=DEFAULT_SEQUENCE_REVIEW_ROWS)
    parser.add_argument("--max-features", type=int, default=3)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Mixed Value Prefix Bootstrap Probe")
    args = parser.parse_args()

    summary, rules, slots = build(
        read_csv(args.input_rows),
        read_csv(args.control_rows),
        read_csv(args.fixtures),
        read_csv(args.replay_fixtures),
        read_csv(args.source_profile_rows),
        read_csv(args.sequence_review_rows),
        max_features=args.max_features,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "rules.csv", RULE_FIELDNAMES, rules)
    write_csv(args.output / "slots.csv", SLOT_FIELDNAMES, slots)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, rules, slots, args.title))

    print(f"False-free byte rule sets: {summary['false_free_byte_sets']}")
    print(f"Union candidate slots: {summary['union_candidate_slots']}")
    print(f"Union conflicts: {summary['union_conflict_slots']}")
    print(
        f"Covered sequence prerequisites: "
        f"{summary['sequence_prerequisite_covered_bytes']}/{summary['sequence_prerequisite_bytes']}"
    )
    print(f"Sequence candidates unlocked: {summary['sequence_candidate_unlocked_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
