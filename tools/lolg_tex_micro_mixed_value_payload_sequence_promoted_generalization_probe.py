#!/usr/bin/env python3
"""Probe sequence generalization after promoted mixed-value prefix/sequence replay."""

from __future__ import annotations

import argparse
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_micro_mixed_value_payload_predictor_probe import (
    int_value,
    ratio,
    read_csv,
    strict_prediction,
    write_csv,
)
from lolg_tex_micro_mixed_value_payload_sequence_candidate_review import (
    DEFAULT_INPUT_ROWS,
    DEFAULT_SELECTED_LOW_CANDIDATES,
    DEFAULT_SELECTED_ROWS,
    context_for,
    enriched_selected_rows,
    fixture_key,
    prerequisite_offsets,
    read_bytes,
)
from lolg_tex_micro_mixed_value_payload_prefix_sequence_promoted_replay import (
    DEFAULT_OUTPUT as DEFAULT_PROMOTED_REPLAY_OUTPUT,
)


DEFAULT_REPLAY_FIXTURES = DEFAULT_PROMOTED_REPLAY_OUTPUT / "fixtures.csv"
DEFAULT_OUTPUT = Path("output/tex_micro_mixed_value_payload_sequence_promoted_generalization")

SUMMARY_FIELDNAMES = [
    "scope",
    "selected_high_slots",
    "selected_low_feature_sets",
    "replayable_unknown_slots",
    "target_known_slots",
    "blocked_prerequisite_slots",
    "false_free_feature_sets",
    "best_feature_set",
    "best_correct_slots",
    "best_false_slots",
    "best_unknown_slots",
    "best_precision",
    "promotion_ready_bytes",
    "issue_rows",
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
    "high_prediction",
    "prerequisite_offsets",
    "known_prerequisites",
    "target_known",
    "state",
    "issues",
]

RULE_FIELDNAMES = [
    "rank",
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
    "verdict",
]


def training_counts(
    rows: list[dict[str, str]],
    feature_set: tuple[str, ...],
) -> tuple[dict[tuple[str, ...], Counter[str]], dict[tuple[int, tuple[str, ...]], Counter[str]]]:
    all_counts: dict[tuple[str, ...], Counter[str]] = defaultdict(Counter)
    row_counts: dict[tuple[int, tuple[str, ...]], Counter[str]] = defaultdict(Counter)
    for row in rows:
        context = context_for(row, feature_set)
        value = row.get("low", "")
        all_counts[context][value] += 1
        row_counts[(int_value(row, "row_index"), context)][value] += 1
    return all_counts, row_counts


def known_byte(mask: bytes, offset: int) -> bool:
    return 0 <= offset < len(mask) and bool(mask[offset])


def build_slots(
    rows: list[dict[str, str]],
    replay_rows: list[dict[str, str]],
) -> tuple[list[dict[str, object]], dict[tuple[str, str, str], bytes], int]:
    replays = {fixture_key(row): row for row in replay_rows}
    known_by_fixture: dict[tuple[str, str, str], bytes] = {}
    slots: list[dict[str, object]] = []
    issue_rows = 0
    for row in rows:
        key = fixture_key(row)
        local_issues: list[str] = []
        if key not in known_by_fixture:
            known_by_fixture[key] = read_bytes(
                replays.get(key, {}).get("known_mask_path", ""),
                local_issues,
                "known_mask",
            )
        known_mask = known_by_fixture.get(key, b"")
        start = int_value(row, "start")
        offset = int_value(row, "offset")
        absolute = start + offset
        prereqs = prerequisite_offsets(row)
        known_prereqs = [1 if known_byte(known_mask, prereq) else 0 for prereq in prereqs]
        target_known = known_byte(known_mask, absolute)
        if local_issues:
            issue_rows += 1
        if not all(known_prereqs):
            state = "blocked_prerequisites"
        elif target_known:
            state = "target_already_known"
        else:
            state = "replayable_unknown"
        slots.append(
            {
                "rank": row.get("rank", ""),
                "row_index": row.get("row_index", ""),
                "archive": row.get("archive", ""),
                "pcx_name": row.get("pcx_name", ""),
                "frontier_id": row.get("frontier_id", ""),
                "span_index": row.get("span_index", ""),
                "op_index": row.get("op_index", ""),
                "start": row.get("start", ""),
                "end": row.get("end", ""),
                "offset": row.get("offset", ""),
                "absolute_offset": str(absolute),
                "byte": row.get("byte", ""),
                "high_prediction": row.get("high_prediction", ""),
                "prerequisite_offsets": "|".join(str(prereq) for prereq in prereqs),
                "known_prerequisites": "|".join(str(value) for value in known_prereqs),
                "target_known": "1" if target_known else "0",
                "state": state,
                "issues": ";".join(local_issues),
            }
        )
    return slots, known_by_fixture, issue_rows


def evaluate_rule(
    rows: list[dict[str, str]],
    replayable_slots: list[dict[str, object]],
    feature_set: tuple[str, ...],
) -> dict[str, object]:
    all_counts, row_counts = training_counts(rows, feature_set)
    rows_by_rank = {str(row.get("rank", "")): row for row in rows}
    correct = 0
    false = 0
    unknown = 0
    predicted_values: Counter[str] = Counter()
    sample_correct: list[str] = []
    sample_false: list[str] = []
    for slot in replayable_slots:
        row = rows_by_rank.get(str(slot.get("rank", "")), {})
        context = context_for(row, feature_set)
        counts = all_counts[context].copy()
        counts.subtract(row_counts[(int_value(row, "row_index"), context)])
        counts += Counter()
        prediction = strict_prediction(counts)
        if prediction is None:
            unknown += 1
            continue
        predicted_byte = f"{row.get('high_prediction', '')}{prediction}"
        predicted_values[predicted_byte] += 1
        sample = (
            f"{slot.get('row_index')}:{slot.get('frontier_id')}:"
            f"{slot.get('offset')}={predicted_byte}"
        )
        if predicted_byte == row.get("byte", ""):
            correct += 1
            if len(sample_correct) < 6:
                sample_correct.append(sample)
        else:
            false += 1
            if len(sample_false) < 6:
                sample_false.append(f"{sample}!={row.get('byte', '')}")

    predicted = correct + false
    if predicted == 0:
        verdict = "no_replayable_prediction"
    elif false == 0:
        verdict = "false_free_replayable_review"
    elif correct > 0:
        verdict = "replayable_low_conflict"
    else:
        verdict = "replayable_low_reject"
    return {
        "rank": 0,
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
        "verdict": verdict,
    }


def build(
    selected_rows: list[dict[str, str]],
    input_rows: list[dict[str, str]],
    selected_low_candidates: list[dict[str, str]],
    replay_rows: list[dict[str, str]],
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    rows = enriched_selected_rows(selected_rows, input_rows)
    slots, _known_by_fixture, issue_rows = build_slots(rows, replay_rows)
    replayable_slots = [slot for slot in slots if slot.get("state") == "replayable_unknown"]

    rules: list[dict[str, object]] = []
    for candidate in selected_low_candidates:
        feature_set = tuple(part for part in candidate.get("feature_set", "").split("+") if part)
        if not feature_set:
            continue
        rules.append(evaluate_rule(rows, replayable_slots, feature_set))
    rules.sort(
        key=lambda row: (
            0
            if int_value(row, "correct_slots") + int_value(row, "false_slots") > 0
            else 1,
            int_value(row, "false_slots"),
            -int_value(row, "correct_slots"),
            int_value(row, "unknown_slots"),
            int_value(row, "feature_count"),
            str(row.get("feature_set", "")),
        )
    )
    for index, row in enumerate(rules, start=1):
        row["rank"] = index

    best = rules[0] if rules else {}
    summary = {
        "scope": "total",
        "selected_high_slots": len(rows),
        "selected_low_feature_sets": len(rules),
        "replayable_unknown_slots": len(replayable_slots),
        "target_known_slots": sum(1 for slot in slots if slot.get("state") == "target_already_known"),
        "blocked_prerequisite_slots": sum(1 for slot in slots if slot.get("state") == "blocked_prerequisites"),
        "false_free_feature_sets": sum(
            1
            for row in rules
            if int_value(row, "correct_slots") > 0 and int_value(row, "false_slots") == 0
        ),
        "best_feature_set": best.get("feature_set", ""),
        "best_correct_slots": best.get("correct_slots", 0),
        "best_false_slots": best.get("false_slots", 0),
        "best_unknown_slots": best.get("unknown_slots", 0),
        "best_precision": best.get("precision", "0.000000"),
        "promotion_ready_bytes": 0,
        "issue_rows": issue_rows,
    }
    return summary, slots, rules


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
  <div class="box"><div class="num">{summary['replayable_unknown_slots']}</div><div class="muted">replayable unknown slots</div></div>
  <div class="box"><div class="num">{summary['target_known_slots']}</div><div class="muted">target already known slots</div></div>
  <div class="box"><div class="num">{summary['blocked_prerequisite_slots']}</div><div class="muted">blocked prerequisite slots</div></div>
  <div class="box"><div class="num">{summary['false_free_feature_sets']}</div><div class="muted">false-free feature sets</div></div>
  <div class="box"><div class="num">{summary['best_correct_slots']}/{summary['best_false_slots']}</div><div class="muted">best correct/false</div></div>
</div>
<div class="panel"><h2>Sequence slots after promotion</h2>{render_table(slots, SLOT_FIELDNAMES)}</div>
<div class="panel"><h2>Low feature sets on replayable unknown slots</h2>{render_table(rules, RULE_FIELDNAMES)}</div>
<script type="application/json" id="mixed-value-sequence-promoted-generalization-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe sequence generalization after mixed-value promotion.")
    parser.add_argument("--input-rows", type=Path, default=DEFAULT_INPUT_ROWS)
    parser.add_argument("--selected-rows", type=Path, default=DEFAULT_SELECTED_ROWS)
    parser.add_argument("--selected-low-candidates", type=Path, default=DEFAULT_SELECTED_LOW_CANDIDATES)
    parser.add_argument("--replay-fixtures", type=Path, default=DEFAULT_REPLAY_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Mixed Value Sequence Promoted Generalization")
    args = parser.parse_args()

    summary, slots, rules = build(
        read_csv(args.selected_rows),
        read_csv(args.input_rows),
        read_csv(args.selected_low_candidates),
        read_csv(args.replay_fixtures),
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "slots.csv", SLOT_FIELDNAMES, slots)
    write_csv(args.output / "rules.csv", RULE_FIELDNAMES, rules)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, slots, rules, args.title))

    print(f"Replayable unknown slots: {summary['replayable_unknown_slots']}")
    print(f"Target known slots: {summary['target_known_slots']}")
    print(f"Blocked prerequisite slots: {summary['blocked_prerequisite_slots']}")
    print(f"False-free feature sets: {summary['false_free_feature_sets']}")
    print(f"Best correct/false: {summary['best_correct_slots']}/{summary['best_false_slots']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
