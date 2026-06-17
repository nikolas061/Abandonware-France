#!/usr/bin/env python3
"""Probe cross-row low transitions for high-safe gradient residual slots."""

from __future__ import annotations

import argparse
import csv
import html
import itertools
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gradient_sequence_high_safe_control_opcode_probe import (
    SLOT_FIELDNAMES as CONTROL_OPCODE_SLOT_FIELDNAMES,
)
from lolg_tex_micro_mixed_value_payload_state_opcode_probe import int_value, ratio, write_csv


DEFAULT_SLOTS = Path("output/tex_gradient_sequence_high_safe_control_opcode/slots.csv")
DEFAULT_OUTPUT = Path("output/tex_gradient_sequence_high_safe_row_transition")

RELATIONS = [
    "prev_file",
    "next_file",
    "dist+320",
    "dist-320",
    "same_frontier+320",
    "same_frontier-320",
]

FIXED_TRANSFORMS = [
    ("id", 0),
    *[("+", value) for value in range(16)],
    *[("xor", value) for value in range(16)],
]

GATE_CANDIDATES = [
    ("next_file", -1, "id", 0),
    ("prev_file", 1, "id", 0),
    ("next_file", 0, "id", 0),
    ("prev_file", 0, "id", 0),
    ("next_file", 0, "+", 1),
    ("next_file", 2, "+", 1),
    ("dist-320", -2, "xor", 1),
    ("same_frontier-320", -2, "xor", 1),
    ("dist+320", 0, "+", 1),
    ("dist+320", 2, "+", 15),
    ("dist+320", -1, "+", 1),
    ("dist+320", 2, "xor", 1),
    ("same_frontier+320", -2, "xor", 1),
    ("prev_file", 2, "+", 15),
]

FEATURES = [
    "rel_mod4",
    "rel_mod8",
    "rel_mod16",
    "target_x_mod32",
    "row_quarter",
    "row_third",
    "op_index",
    "offset_delta_bucket",
    "pool",
    "source_low",
    "prev_known_byte",
    "next_known_byte",
    "gradient_class",
]

FOCUSED_4_FEATURE_SETS = [
    ("rel_mod8", "target_x_mod32", "row_third", "offset_delta_bucket"),
    ("rel_mod16", "row_quarter", "row_third", "source_low"),
]

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "slots",
    "slot_rows",
    "relations",
    "fixed_candidates",
    "fixed_best_exact_slots",
    "fixed_best_false_slots",
    "fixed_best_candidate",
    "gate_candidates",
    "gate_feature_sets",
    "gate_rules",
    "gate_predicted_rules",
    "gate_false_free_sets",
    "gate_best_false_free_slots",
    "gate_best_false_free_candidate",
    "gate_best_false_free_feature_set",
    "gate_best_exact_slots",
    "gate_best_false_slots",
    "gate_best_candidate",
    "gate_best_feature_set",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

FIXED_FIELDNAMES = [
    "rank",
    "relation",
    "relative_delta",
    "transform",
    "parameter",
    "candidate",
    "applicable_slots",
    "exact_slots",
    "false_slots",
    "precision",
    "exact_rows",
    "sample_exact",
    "verdict",
]

GATE_FIELDNAMES = [
    "rank",
    "candidate",
    "feature_set",
    "feature_count",
    "applicable_slots",
    "predicted_slots",
    "exact_slots",
    "false_slots",
    "unknown_slots",
    "precision",
    "predicted_groups",
    "predicted_rows",
    "false_free",
    "sample_predictions",
    "verdict",
]

SLOT_FIELDNAMES = [
    *CONTROL_OPCODE_SLOT_FIELDNAMES,
    "best_fixed_transition_candidate",
    "best_fixed_transition_source_row",
    "best_fixed_transition_source_low",
    "best_fixed_transition_predicted_low",
    "best_fixed_transition_verdict",
    "best_gate_transition_candidate",
    "best_gate_transition_feature_set",
    "best_gate_transition_context",
    "best_gate_transition_source_row",
    "best_gate_transition_source_low",
    "best_gate_transition_predicted_low",
    "best_gate_transition_verdict",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def parse_low(row: dict[str, object]) -> int | None:
    value = str(row.get("target_low", ""))
    if not value:
        return None
    try:
        return int(value, 16)
    except ValueError:
        return None


def transform_low(source_low: int, transform: str, parameter: int) -> int:
    if transform == "xor":
        return source_low ^ parameter
    return (source_low + parameter) & 0x0F


def transform_text(transform: str, parameter: int) -> str:
    if transform == "id":
        return "id"
    if transform == "+":
        return f"+{parameter:x}"
    return f"xor{parameter:x}"


def candidate_text(relation: str, relative_delta: int, transform: str, parameter: int) -> str:
    return f"{relation}:{relative_delta:+d}:{transform_text(transform, parameter)}"


def row_sort_key(row: dict[str, object]) -> tuple[str, str, int, int]:
    return (
        str(row.get("archive", "")),
        str(row.get("pcx_name", "")),
        int_value(row, "start"),
        int_value(row, "frontier_id"),
    )


def build_row_models(slot_rows: list[dict[str, str]]) -> tuple[list[dict[str, object]], dict[str, dict[str, object]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for slot in slot_rows:
        grouped[str(slot.get("row_id", ""))].append(slot)

    rows: list[dict[str, object]] = []
    for row_id, members in grouped.items():
        members = sorted(members, key=lambda row: int_value(row, "relative_offset"))
        lows: dict[int, int] = {}
        by_relative: dict[int, dict[str, str]] = {}
        for slot in members:
            low = parse_low(slot)
            if low is None:
                continue
            relative = int_value(slot, "relative_offset")
            lows[relative] = low
            by_relative[relative] = slot
        first = members[0]
        rows.append(
            {
                "row_id": row_id,
                "archive": first.get("archive", ""),
                "pcx_name": first.get("pcx_name", ""),
                "frontier_id": first.get("frontier_id", ""),
                "start": int_value(first, "start"),
                "end": int_value(first, "end"),
                "slots": members,
                "lows": lows,
                "by_relative": by_relative,
            }
        )
    rows.sort(key=row_sort_key)
    return rows, {str(row["row_id"]): row for row in rows}


def source_row_for(
    row: dict[str, object],
    rows_by_file: dict[tuple[str, str], list[dict[str, object]]],
    relation: str,
) -> dict[str, object] | None:
    file_key = (str(row["archive"]), str(row["pcx_name"]))
    file_rows = rows_by_file[file_key]
    index = file_rows.index(row)
    if relation == "prev_file":
        return file_rows[index - 1] if index > 0 else None
    if relation == "next_file":
        return file_rows[index + 1] if index + 1 < len(file_rows) else None
    if relation.startswith("dist") or relation.startswith("same_frontier"):
        distance = int(relation.removeprefix("dist").removeprefix("same_frontier"))
        target_start = int(row["start"]) + distance
        for candidate in file_rows:
            if int(candidate["start"]) != target_start:
                continue
            if relation.startswith("same_frontier") and candidate["frontier_id"] != row["frontier_id"]:
                continue
            return candidate
    return None


def rows_by_file(rows: list[dict[str, object]]) -> dict[tuple[str, str], list[dict[str, object]]]:
    grouped: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row["archive"]), str(row["pcx_name"]))].append(row)
    for members in grouped.values():
        members.sort(key=row_sort_key)
    return grouped


def candidate_prediction(
    slot: dict[str, object],
    row_by_id: dict[str, dict[str, object]],
    file_rows: dict[tuple[str, str], list[dict[str, object]]],
    relation: str,
    relative_delta: int,
    transform: str,
    parameter: int,
) -> tuple[int | None, int | None, str]:
    row = row_by_id.get(str(slot.get("row_id", "")))
    if row is None:
        return None, None, ""
    source_row = source_row_for(row, file_rows, relation)
    if source_row is None:
        return None, None, ""
    source_relative = int_value(slot, "relative_offset") + relative_delta
    source_low = source_row["lows"].get(source_relative, None)
    if source_low is None:
        return None, None, str(source_row["row_id"])
    return source_low, transform_low(source_low, transform, parameter), str(source_row["row_id"])


def fixed_rows(
    slots: list[dict[str, str]],
    row_by_id: dict[str, dict[str, object]],
    file_rows: dict[tuple[str, str], list[dict[str, object]]],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for relation in RELATIONS:
        for relative_delta in range(-2, 3):
            for transform, parameter in FIXED_TRANSFORMS:
                applicable = 0
                exact = 0
                exact_rows: set[str] = set()
                samples: list[str] = []
                for slot in slots:
                    low = parse_low(slot)
                    source_low, predicted, source_row = candidate_prediction(
                        slot,
                        row_by_id,
                        file_rows,
                        relation,
                        relative_delta,
                        transform,
                        parameter,
                    )
                    if low is None or predicted is None:
                        continue
                    applicable += 1
                    if predicted == low:
                        exact += 1
                        exact_rows.add(str(slot.get("row_id", "")))
                        if len(samples) < 6:
                            samples.append(
                                f"{slot.get('frontier_id', '')}:{slot.get('relative_offset', '')}:"
                                f"{source_low:x}->{predicted:x}@{source_row}"
                            )
                if applicable:
                    rows.append(
                        {
                            "rank": 0,
                            "relation": relation,
                            "relative_delta": relative_delta,
                            "transform": transform,
                            "parameter": parameter,
                            "candidate": candidate_text(relation, relative_delta, transform, parameter),
                            "applicable_slots": applicable,
                            "exact_slots": exact,
                            "false_slots": applicable - exact,
                            "precision": ratio(exact, applicable),
                            "exact_rows": len(exact_rows),
                            "sample_exact": "|".join(samples),
                            "verdict": "row_transition_candidate" if exact else "row_transition_reject",
                        }
                    )
    rows.sort(
        key=lambda row: (
            -int_value(row, "exact_slots"),
            int_value(row, "false_slots"),
            str(row.get("candidate", "")),
        )
    )
    for index, row in enumerate(rows, start=1):
        row["rank"] = index
    return rows


def candidate_feature_sets(max_features: int) -> list[tuple[str, ...]]:
    output: list[tuple[str, ...]] = []
    generated_max = min(max_features, 3)
    for size in range(1, generated_max + 1):
        output.extend(itertools.combinations(FEATURES, size))
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


def context_for(slot: dict[str, object], features: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(str(slot.get(feature, "")) for feature in features)


def evaluate_gate_rule(
    slots: list[dict[str, str]],
    row_by_id: dict[str, dict[str, object]],
    file_rows: dict[tuple[str, str], list[dict[str, object]]],
    candidate: tuple[str, int, str, int],
    features: tuple[str, ...],
) -> dict[str, object]:
    relation, relative_delta, transform, parameter = candidate
    values: list[str] = []
    predictions: list[int | None] = []
    groups: dict[tuple[str, ...], list[int]] = defaultdict(list)
    for index, slot in enumerate(slots):
        low = parse_low(slot)
        _source_low, predicted, _source_row = candidate_prediction(
            slot,
            row_by_id,
            file_rows,
            relation,
            relative_delta,
            transform,
            parameter,
        )
        predictions.append(predicted)
        if low is None or predicted is None:
            values.append("")
            continue
        values.append("1" if predicted == low else "0")
        groups[context_for(slot, features)].append(index)

    applicable = sum(1 for value in values if value)
    exact = 0
    false = 0
    unknown = 0
    predicted_slots = 0
    predicted_groups: set[tuple[str, ...]] = set()
    predicted_rows: set[str] = set()
    samples: list[str] = []
    for context, indexes in groups.items():
        total_counts = Counter(values[index] for index in indexes if values[index])
        by_row: dict[str, Counter[str]] = defaultdict(Counter)
        for index in indexes:
            if values[index]:
                by_row[str(slots[index].get("row_id", ""))][values[index]] += 1
        peer_ok_rows: set[str] = set()
        for row_id, counts in by_row.items():
            peer_counts = total_counts.copy()
            peer_counts.subtract(counts)
            peer_counts = Counter({value: count for value, count in peer_counts.items() if count > 0})
            if len(peer_counts) == 1 and next(iter(peer_counts)) == "1":
                peer_ok_rows.add(row_id)
        for index in indexes:
            slot = slots[index]
            row_id = str(slot.get("row_id", ""))
            if not values[index] or row_id not in peer_ok_rows:
                unknown += 1
                continue
            predicted_slots += 1
            predicted_groups.add(context)
            predicted_rows.add(row_id)
            if values[index] == "1":
                exact += 1
            else:
                false += 1
            if len(samples) < 6:
                predicted = predictions[index]
                samples.append(f"{'|'.join(context)}->{predicted:x}" if predicted is not None else "|".join(context))

    false_free = predicted_slots > 0 and false == 0
    return {
        "rank": 0,
        "candidate": candidate_text(relation, relative_delta, transform, parameter),
        "feature_set": "+".join(features),
        "feature_count": len(features),
        "applicable_slots": applicable,
        "predicted_slots": predicted_slots,
        "exact_slots": exact,
        "false_slots": false,
        "unknown_slots": unknown,
        "precision": ratio(exact, predicted_slots),
        "predicted_groups": len(predicted_groups),
        "predicted_rows": len(predicted_rows),
        "false_free": 1 if false_free else 0,
        "sample_predictions": "|".join(samples),
        "verdict": (
            "row_transition_gate_false_free"
            if false_free
            else "row_transition_gate_noisy"
            if predicted_slots
            else "row_transition_gate_no_predictions"
        ),
    }


def gate_rules(
    slots: list[dict[str, str]],
    row_by_id: dict[str, dict[str, object]],
    file_rows: dict[tuple[str, str], list[dict[str, object]]],
    max_features: int,
) -> tuple[list[dict[str, object]], list[tuple[str, ...]]]:
    feature_sets = candidate_feature_sets(max_features)
    rows: list[dict[str, object]] = []
    for candidate in GATE_CANDIDATES:
        for features in feature_sets:
            row = evaluate_gate_rule(slots, row_by_id, file_rows, candidate, features)
            if int_value(row, "predicted_slots") > 0:
                rows.append(row)
    rows.sort(
        key=lambda row: (
            -int_value(row, "false_free"),
            -int_value(row, "exact_slots"),
            int_value(row, "false_slots"),
            int_value(row, "feature_count"),
            str(row["candidate"]),
            str(row["feature_set"]),
        )
    )
    for index, row in enumerate(rows, start=1):
        row["rank"] = index
    return rows, feature_sets


def best_rule(rows: list[dict[str, object]]) -> dict[str, object]:
    return max(
        rows,
        key=lambda row: (
            int_value(row, "exact_slots"),
            -int_value(row, "false_slots"),
            -int_value(row, "feature_count"),
            str(row.get("candidate", "")),
            str(row.get("feature_set", "")),
        ),
        default={},
    )


def best_false_free_rule(rows: list[dict[str, object]]) -> dict[str, object]:
    return max(
        [row for row in rows if int_value(row, "false_free") > 0],
        key=lambda row: (
            int_value(row, "exact_slots"),
            -int_value(row, "feature_count"),
            str(row.get("candidate", "")),
            str(row.get("feature_set", "")),
        ),
        default={},
    )


def parse_candidate(text: str) -> tuple[str, int, str, int]:
    relation, delta_text, transform_text_value = text.split(":", 2)
    relative_delta = int(delta_text)
    if transform_text_value == "id":
        return relation, relative_delta, "id", 0
    if transform_text_value.startswith("+"):
        return relation, relative_delta, "+", int(transform_text_value[1:], 16)
    return relation, relative_delta, "xor", int(transform_text_value[3:], 16)


def annotate_slots(
    slots: list[dict[str, str]],
    row_by_id: dict[str, dict[str, object]],
    file_rows: dict[tuple[str, str], list[dict[str, object]]],
    best_fixed: dict[str, object],
    best_gate: dict[str, object],
) -> list[dict[str, object]]:
    fixed_text = str(best_fixed.get("candidate", ""))
    gate_text = str(best_gate.get("candidate", ""))
    fixed_candidate = parse_candidate(fixed_text) if fixed_text else None
    gate_candidate = parse_candidate(gate_text) if gate_text else None
    gate_features = tuple(part for part in str(best_gate.get("feature_set", "")).split("+") if part)
    output: list[dict[str, object]] = []
    for slot in slots:
        row = dict(slot)
        fixed_source_low = fixed_prediction = None
        fixed_source_row = ""
        gate_source_low = gate_prediction = None
        gate_source_row = ""
        if fixed_candidate:
            fixed_source_low, fixed_prediction, fixed_source_row = candidate_prediction(
                row, row_by_id, file_rows, *fixed_candidate
            )
        if gate_candidate:
            gate_source_low, gate_prediction, gate_source_row = candidate_prediction(
                row, row_by_id, file_rows, *gate_candidate
            )
        target = parse_low(row)
        row.update(
            {
                "best_fixed_transition_candidate": fixed_text,
                "best_fixed_transition_source_row": fixed_source_row,
                "best_fixed_transition_source_low": "" if fixed_source_low is None else f"{fixed_source_low:x}",
                "best_fixed_transition_predicted_low": "" if fixed_prediction is None else f"{fixed_prediction:x}",
                "best_fixed_transition_verdict": (
                    "correct" if fixed_prediction is not None and fixed_prediction == target else "false"
                ),
                "best_gate_transition_candidate": gate_text,
                "best_gate_transition_feature_set": "+".join(gate_features),
                "best_gate_transition_context": "|".join(context_for(row, gate_features)) if gate_features else "",
                "best_gate_transition_source_row": gate_source_row,
                "best_gate_transition_source_low": "" if gate_source_low is None else f"{gate_source_low:x}",
                "best_gate_transition_predicted_low": "" if gate_prediction is None else f"{gate_prediction:x}",
                "best_gate_transition_verdict": (
                    "correct" if gate_prediction is not None and gate_prediction == target else "false"
                ),
            }
        )
        output.append(row)
    return output


def build(
    slot_rows: list[dict[str, str]],
    max_features: int,
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    rows, row_by_id = build_row_models(slot_rows)
    file_rows = rows_by_file(rows)
    fixed = fixed_rows(slot_rows, row_by_id, file_rows)
    gated, feature_sets = gate_rules(slot_rows, row_by_id, file_rows, max_features)
    best_fixed = best_rule(fixed)
    best_gate = best_rule(gated)
    best_gate_false_free = best_false_free_rule(gated)
    annotated_slots = annotate_slots(slot_rows, row_by_id, file_rows, best_fixed, best_gate)
    summary = {
        "scope": "total",
        "candidate_mode": "cross_row_low_transition",
        "slots": len(slot_rows),
        "slot_rows": len(rows),
        "relations": len(RELATIONS),
        "fixed_candidates": len(fixed),
        "fixed_best_exact_slots": best_fixed.get("exact_slots", 0),
        "fixed_best_false_slots": best_fixed.get("false_slots", 0),
        "fixed_best_candidate": best_fixed.get("candidate", ""),
        "gate_candidates": len(GATE_CANDIDATES),
        "gate_feature_sets": len(feature_sets),
        "gate_rules": len(GATE_CANDIDATES) * len(feature_sets),
        "gate_predicted_rules": len(gated),
        "gate_false_free_sets": sum(1 for row in gated if int_value(row, "false_free") > 0),
        "gate_best_false_free_slots": best_gate_false_free.get("exact_slots", 0),
        "gate_best_false_free_candidate": best_gate_false_free.get("candidate", ""),
        "gate_best_false_free_feature_set": best_gate_false_free.get("feature_set", ""),
        "gate_best_exact_slots": best_gate.get("exact_slots", 0),
        "gate_best_false_slots": best_gate.get("false_slots", 0),
        "gate_best_candidate": best_gate.get("candidate", ""),
        "gate_best_feature_set": best_gate.get("feature_set", ""),
        "promotion_candidate_bytes": 0,
        "promotion_ready_bytes": 0,
        "issue_rows": 0,
    }
    return summary, annotated_slots, fixed, gated


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
    fixed: list[dict[str, object]],
    gated: list[dict[str, object]],
    title: str,
) -> str:
    data_json = json.dumps(
        {"summary": summary, "slots": slots, "fixed": fixed[:260], "gated": gated[:260]},
        indent=2,
        sort_keys=True,
    )
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
  <div class="box"><div class="num">{summary['slots']}</div><div class="muted">slots</div></div>
  <div class="box"><div class="num">{summary['fixed_best_exact_slots']}/{summary['fixed_best_false_slots']}</div><div class="muted">best fixed exact/false</div></div>
  <div class="box"><div class="num">{summary['gate_best_exact_slots']}/{summary['gate_best_false_slots']}</div><div class="muted">best gated exact/false</div></div>
  <div class="box"><div class="num">{summary['gate_best_false_free_slots']}</div><div class="muted">best gated false-free slots</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Fixed transitions</h2>{render_table(fixed, FIXED_FIELDNAMES)}</div>
<div class="panel"><h2>Gated transitions</h2>{render_table(gated, GATE_FIELDNAMES)}</div>
<div class="panel"><h2>Slots</h2>{render_table(slots, SLOT_FIELDNAMES)}</div>
<script type="application/json" id="gradient-sequence-high-safe-row-transition-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe cross-row low transitions for high-safe gradient residuals.")
    parser.add_argument("--slots", type=Path, default=DEFAULT_SLOTS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-features", type=int, default=4)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Gradient Sequence High-Safe Row Transition Probe",
    )
    args = parser.parse_args()

    summary, slots, fixed, gated = build(read_csv(args.slots), args.max_features)
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "slots.csv", SLOT_FIELDNAMES, slots)
    write_csv(args.output / "fixed_candidates.csv", FIXED_FIELDNAMES, fixed)
    write_csv(args.output / "gated_rules.csv", GATE_FIELDNAMES, gated)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, slots, fixed, gated, args.title))

    print(f"Slots: {summary['slots']}")
    print(
        "Best fixed transition: "
        f"{summary['fixed_best_candidate']} = "
        f"{summary['fixed_best_exact_slots']} exact / {summary['fixed_best_false_slots']} false"
    )
    print(
        "Best gated transition: "
        f"{summary['gate_best_candidate']} / {summary['gate_best_feature_set']} = "
        f"{summary['gate_best_exact_slots']} exact / {summary['gate_best_false_slots']} false"
    )
    print(f"Best gated false-free slots: {summary['gate_best_false_free_slots']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
