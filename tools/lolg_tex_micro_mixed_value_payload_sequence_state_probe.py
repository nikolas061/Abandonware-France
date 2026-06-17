#!/usr/bin/env python3
"""Probe sequence-state predictors for dominant mixed-value payload slots."""

from __future__ import annotations

import argparse
import html
import itertools
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_micro_mixed_value_payload_predictor_probe import (
    DEFAULT_FIXTURES,
    DEFAULT_INPUT_ROWS,
    build_payloads,
    int_value,
    ratio,
    read_csv,
    strict_prediction,
    write_csv,
)


DEFAULT_OUTPUT = Path("output/tex_micro_mixed_value_payload_sequence_state")

SEQUENCE_FEATURES = [
    "prev1",
    "prev2",
    "prev3",
    "prev1_high",
    "prev1_low",
    "prev_delta_exact",
    "prev_delta_bucket",
    "prev_delta2_bucket",
    "prev_delta_pair",
    "prev_shape",
    "run_byte",
    "run_high",
    "run_len_bucket",
    "run_len_mod4",
]
LOCAL_FEATURES = ["pos4", "pos8", "pos16", "tail4", "signal", "control", "dominant"]
FEATURES = SEQUENCE_FEATURES + LOCAL_FEATURES
TARGET_KINDS = ("byte", "high", "band", "low")

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "target_bytes",
    "entry_slots",
    "sequence_features",
    "local_features",
    "feature_sets",
    "candidate_rows",
    "false_free_byte_sets",
    "best_false_free_byte_feature_set",
    "best_false_free_byte_slots",
    "false_free_high_sets",
    "best_false_free_high_feature_set",
    "best_false_free_high_slots",
    "best_false_free_high_unknown_slots",
    "best_byte_feature_set",
    "best_byte_correct_slots",
    "best_byte_false_slots",
    "best_byte_precision",
    "best_high_feature_set",
    "best_high_correct_slots",
    "best_high_false_slots",
    "best_high_precision",
    "best_low_feature_set",
    "best_low_correct_slots",
    "best_low_false_slots",
    "best_low_precision",
    "selected_high_slots",
    "selected_high_rows",
    "selected_low_values",
    "selected_low_feature_sets",
    "best_selected_low_feature_set",
    "best_selected_low_correct_slots",
    "best_selected_low_false_slots",
    "best_selected_low_unknown_slots",
    "false_free_selected_low_sets",
    "best_false_free_selected_low_feature_set",
    "best_false_free_selected_low_slots",
    "best_false_free_selected_low_unknown_slots",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

CANDIDATE_FIELDNAMES = [
    "rank",
    "target_kind",
    "feature_set",
    "feature_count",
    "contexts",
    "repeated_slots",
    "conflicted_slots",
    "loo_correct_slots",
    "loo_false_slots",
    "loo_unknown_slots",
    "loo_precision",
    "loo_coverage",
    "predicted_values",
    "verdict",
    "sample_context",
    "sample_prediction",
]

SELECTED_ROW_FIELDNAMES = [
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
    "byte",
    "high",
    "low",
    "high_context",
    "high_prediction",
    "prev1",
    "prev2",
    "prev_delta_bucket",
    "prev_shape",
    "run_len_bucket",
    "pos16",
]


def signed_delta(left: int, right: int) -> int:
    return ((right - left + 128) & 0xFF) - 128


def delta_bucket(delta: int | None) -> str:
    if delta is None:
        return "NA"
    if delta == 0:
        return "0"
    magnitude = abs(delta)
    suffix = "s" if magnitude <= 4 else "m" if magnitude <= 31 else "j"
    return ("+" if delta > 0 else "-") + suffix


def length_bucket(length: int) -> str:
    if length <= 0:
        return "0"
    if length == 1:
        return "1"
    if length == 2:
        return "2"
    if length <= 4:
        return "3-4"
    return "5+"


def band_token(value: int) -> str:
    high = value >> 4
    return f"{high:x}" if high in {5, 6, 7, 10} else "x"


def previous_shape(previous3: int | None, previous2: int | None, previous1: int | None) -> str:
    if previous3 is None or previous2 is None or previous1 is None:
        return "START"
    deltas = [signed_delta(previous3, previous2), signed_delta(previous2, previous1)]
    if deltas[0] == 0 and deltas[1] == 0:
        return "flat"
    if deltas[0] >= 0 and deltas[1] >= 0:
        return "up"
    if deltas[0] <= 0 and deltas[1] <= 0:
        return "down"
    return "zigzag"


def build_entries(input_rows: list[dict[str, str]], fixture_rows: list[dict[str, str]]) -> tuple[
    list[dict[str, object]], list[str]
]:
    payloads, issues = build_payloads(input_rows, fixture_rows)
    entries: list[dict[str, object]] = []
    for row_index, (row, payload) in enumerate(payloads):
        values = list(payload)
        run_length = 0
        run_byte: int | None = None
        for offset, value in enumerate(values):
            previous1 = values[offset - 1] if offset >= 1 else None
            previous2 = values[offset - 2] if offset >= 2 else None
            previous3 = values[offset - 3] if offset >= 3 else None
            if offset == 0 or previous1 != run_byte:
                run_byte = previous1
                run_length = 1 if previous1 is not None else 0
            else:
                run_length += 1

            previous_delta = (
                signed_delta(previous2, previous1) if previous1 is not None and previous2 is not None else None
            )
            previous_delta2 = (
                signed_delta(previous3, previous2) if previous2 is not None and previous3 is not None else None
            )
            entries.append(
                {
                    "row_index": row_index,
                    "archive": row.get("archive", ""),
                    "pcx_name": row.get("pcx_name", ""),
                    "frontier_id": row.get("frontier_id", ""),
                    "span_index": row.get("span_index", ""),
                    "op_index": row.get("op_index", ""),
                    "start": row.get("start", ""),
                    "end": row.get("end", ""),
                    "offset": offset,
                    "length": len(values),
                    "byte": f"{value:02x}",
                    "high": f"{value >> 4:x}",
                    "low": f"{value & 0x0F:x}",
                    "band": band_token(value),
                    "prev1": f"{previous1:02x}" if previous1 is not None else "START",
                    "prev2": f"{previous2:02x}" if previous2 is not None else "START",
                    "prev3": f"{previous3:02x}" if previous3 is not None else "START",
                    "prev1_high": f"{previous1 >> 4:x}" if previous1 is not None else "START",
                    "prev1_low": f"{previous1 & 0x0F:x}" if previous1 is not None else "START",
                    "prev_delta_exact": str(previous_delta) if previous_delta is not None else "START",
                    "prev_delta_bucket": delta_bucket(previous_delta),
                    "prev_delta2_bucket": delta_bucket(previous_delta2),
                    "prev_delta_pair": f"{delta_bucket(previous_delta2)}|{delta_bucket(previous_delta)}",
                    "prev_shape": previous_shape(previous3, previous2, previous1),
                    "run_byte": f"{run_byte:02x}" if run_byte is not None else "START",
                    "run_high": f"{run_byte >> 4:x}" if run_byte is not None else "START",
                    "run_len_bucket": length_bucket(run_length),
                    "run_len_mod4": str(run_length % 4),
                    "pos4": str(offset % 4),
                    "pos8": str(offset % 8),
                    "pos16": str((offset * 16) // len(values)) if values else "0",
                    "tail4": str(len(values) - 1 - offset) if len(values) - 1 - offset < 4 else "body",
                    "signal": row.get("best_signal_key", ""),
                    "control": row.get("control_ref_mod64", ""),
                    "dominant": row.get("dominant_byte_hex", ""),
                }
            )
    return entries, issues


def feature_combinations(features: list[str], max_features: int, *, require_sequence: bool) -> list[tuple[str, ...]]:
    output: list[tuple[str, ...]] = []
    sequence = set(SEQUENCE_FEATURES)
    for size in range(1, max_features + 1):
        for feature_set in itertools.combinations(features, size):
            if require_sequence and not any(feature in sequence for feature in feature_set):
                continue
            output.append(feature_set)
    return output


def evaluate_combo(
    entries: list[dict[str, object]],
    target_kind: str,
    feature_set: tuple[str, ...],
) -> dict[str, object]:
    all_counts: dict[tuple[object, ...], Counter[str]] = defaultdict(Counter)
    row_counts: dict[tuple[int, tuple[object, ...]], Counter[str]] = defaultdict(Counter)
    grouped_slots: dict[tuple[object, ...], int] = defaultdict(int)
    for entry in entries:
        context = tuple(entry[feature] for feature in feature_set)
        value = str(entry[target_kind])
        all_counts[context][value] += 1
        row_counts[(int(entry["row_index"]), context)][value] += 1
        grouped_slots[context] += 1

    repeated_slots = sum(count for count in grouped_slots.values() if count > 1)
    conflicted_slots = sum(
        grouped_slots[context]
        for context, counts in all_counts.items()
        if len([value for value, count in counts.items() if count]) > 1
    )
    predicted_values: Counter[str] = Counter()
    for context, counts in all_counts.items():
        prediction = strict_prediction(counts)
        if prediction is not None:
            predicted_values[prediction] += grouped_slots[context]

    correct = 0
    false = 0
    unknown = 0
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
        if prediction == str(entry[target_kind]):
            correct += 1
        else:
            false += 1

    predicted = correct + false
    if predicted == 0:
        verdict = "no_cross_row_prediction"
    elif false == 0 and target_kind == "byte":
        verdict = "false_free_byte_review"
    elif false == 0:
        verdict = "false_free_nibble_review"
    elif target_kind == "byte" and false >= correct:
        verdict = "byte_sequence_reject"
    elif correct > false:
        verdict = "partial_sequence_hint"
    else:
        verdict = "conflicted_sequence_state"

    return {
        "rank": 0,
        "target_kind": target_kind,
        "feature_set": "+".join(feature_set),
        "feature_count": len(feature_set),
        "contexts": len(all_counts),
        "repeated_slots": repeated_slots,
        "conflicted_slots": conflicted_slots,
        "loo_correct_slots": correct,
        "loo_false_slots": false,
        "loo_unknown_slots": unknown,
        "loo_precision": ratio(correct, predicted),
        "loo_coverage": ratio(predicted, len(entries)),
        "predicted_values": "|".join(f"{value}:{count}" for value, count in predicted_values.most_common(8)),
        "verdict": verdict,
        "sample_context": sample_context,
        "sample_prediction": sample_prediction,
    }


def best_candidate(rows: list[dict[str, object]], target_kind: str) -> dict[str, object]:
    candidates = [
        row
        for row in rows
        if row.get("target_kind") == target_kind
        and int_value(row, "loo_correct_slots") + int_value(row, "loo_false_slots") > 0
    ]
    if not candidates:
        return {}
    candidates.sort(
        key=lambda row: (
            int_value(row, "loo_correct_slots"),
            -int_value(row, "loo_false_slots"),
            float(row.get("loo_precision", "0") or 0),
            -int_value(row, "feature_count"),
        ),
        reverse=True,
    )
    return candidates[0]


def best_false_free(rows: list[dict[str, object]], target_kind: str) -> dict[str, object]:
    candidates = [
        row
        for row in rows
        if row.get("target_kind") == target_kind
        and int_value(row, "loo_correct_slots") > 0
        and int_value(row, "loo_false_slots") == 0
    ]
    if not candidates:
        return {}
    candidates.sort(key=lambda row: (int_value(row, "loo_correct_slots"), -int_value(row, "feature_count")), reverse=True)
    return candidates[0]


def selected_high_entries(
    entries: list[dict[str, object]],
    feature_set_text: str,
) -> list[tuple[dict[str, object], str, tuple[object, ...]]]:
    feature_set = tuple(part for part in feature_set_text.split("+") if part)
    all_counts: dict[tuple[object, ...], Counter[str]] = defaultdict(Counter)
    row_counts: dict[tuple[int, tuple[object, ...]], Counter[str]] = defaultdict(Counter)
    for entry in entries:
        context = tuple(entry[feature] for feature in feature_set)
        value = str(entry["high"])
        all_counts[context][value] += 1
        row_counts[(int(entry["row_index"]), context)][value] += 1

    selected: list[tuple[dict[str, object], str, tuple[object, ...]]] = []
    for entry in entries:
        context = tuple(entry[feature] for feature in feature_set)
        train_counts = all_counts[context].copy()
        train_counts.subtract(row_counts[(int(entry["row_index"]), context)])
        train_counts += Counter()
        prediction = strict_prediction(train_counts)
        if prediction is not None and prediction == str(entry["high"]):
            selected.append((entry, prediction, context))
    return selected


def build_selected_rows(selected: list[tuple[dict[str, object], str, tuple[object, ...]]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for rank, (entry, prediction, context) in enumerate(selected, start=1):
        rows.append(
            {
                "rank": rank,
                "row_index": entry["row_index"],
                "archive": entry["archive"],
                "pcx_name": entry["pcx_name"],
                "frontier_id": entry["frontier_id"],
                "span_index": entry["span_index"],
                "op_index": entry["op_index"],
                "start": entry["start"],
                "end": entry["end"],
                "offset": entry["offset"],
                "byte": entry["byte"],
                "high": entry["high"],
                "low": entry["low"],
                "high_context": "|".join(str(part) for part in context),
                "high_prediction": prediction,
                "prev1": entry["prev1"],
                "prev2": entry["prev2"],
                "prev_delta_bucket": entry["prev_delta_bucket"],
                "prev_shape": entry["prev_shape"],
                "run_len_bucket": entry["run_len_bucket"],
                "pos16": entry["pos16"],
            }
        )
    return rows


def build(
    input_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    *,
    max_features: int,
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    entries, issues = build_entries(input_rows, fixture_rows)
    combos = feature_combinations(FEATURES, max_features, require_sequence=True)
    candidates = [
        evaluate_combo(entries, target_kind, feature_set)
        for target_kind in TARGET_KINDS
        for feature_set in combos
    ]
    candidates.sort(
        key=lambda row: (
            str(row["target_kind"]),
            -int_value(row, "loo_correct_slots"),
            int_value(row, "loo_false_slots"),
            int_value(row, "feature_count"),
            str(row["feature_set"]),
        )
    )
    for index, row in enumerate(candidates, start=1):
        row["rank"] = index

    false_free_byte = [
        row
        for row in candidates
        if row.get("target_kind") == "byte"
        and int_value(row, "loo_correct_slots") > 0
        and int_value(row, "loo_false_slots") == 0
    ]
    false_free_high = [
        row
        for row in candidates
        if row.get("target_kind") == "high"
        and int_value(row, "loo_correct_slots") > 0
        and int_value(row, "loo_false_slots") == 0
    ]
    best_byte = best_candidate(candidates, "byte")
    best_high = best_candidate(candidates, "high")
    best_low = best_candidate(candidates, "low")
    best_false_free_byte = best_false_free(candidates, "byte")
    best_false_free_high = best_false_free(candidates, "high")

    selected = selected_high_entries(entries, str(best_false_free_high.get("feature_set", "")))
    selected_rows = build_selected_rows(selected)
    selected_entries = [entry for entry, _prediction, _context in selected]
    low_combos = feature_combinations(FEATURES, max_features, require_sequence=False)
    selected_low_candidates = [
        evaluate_combo(selected_entries, "low", feature_set) for feature_set in low_combos
    ] if selected_entries else []
    selected_low_candidates.sort(
        key=lambda row: (
            -int_value(row, "loo_correct_slots"),
            int_value(row, "loo_false_slots"),
            int_value(row, "feature_count"),
            str(row["feature_set"]),
        )
    )
    for index, row in enumerate(selected_low_candidates, start=1):
        row["rank"] = index
    best_selected_low = best_candidate(selected_low_candidates, "low")
    false_free_selected_low = [
        row
        for row in selected_low_candidates
        if int_value(row, "loo_correct_slots") > 0 and int_value(row, "loo_false_slots") == 0
    ]
    best_false_free_selected_low = best_false_free(selected_low_candidates, "low")

    summary = {
        "scope": "total",
        "target_rows": len(input_rows),
        "target_bytes": len(entries),
        "entry_slots": len(entries),
        "sequence_features": len(SEQUENCE_FEATURES),
        "local_features": len(LOCAL_FEATURES),
        "feature_sets": len(combos),
        "candidate_rows": len(candidates),
        "false_free_byte_sets": len(false_free_byte),
        "best_false_free_byte_feature_set": best_false_free_byte.get("feature_set", ""),
        "best_false_free_byte_slots": best_false_free_byte.get("loo_correct_slots", 0),
        "false_free_high_sets": len(false_free_high),
        "best_false_free_high_feature_set": best_false_free_high.get("feature_set", ""),
        "best_false_free_high_slots": best_false_free_high.get("loo_correct_slots", 0),
        "best_false_free_high_unknown_slots": best_false_free_high.get("loo_unknown_slots", 0),
        "best_byte_feature_set": best_byte.get("feature_set", ""),
        "best_byte_correct_slots": best_byte.get("loo_correct_slots", 0),
        "best_byte_false_slots": best_byte.get("loo_false_slots", 0),
        "best_byte_precision": best_byte.get("loo_precision", "0.000000"),
        "best_high_feature_set": best_high.get("feature_set", ""),
        "best_high_correct_slots": best_high.get("loo_correct_slots", 0),
        "best_high_false_slots": best_high.get("loo_false_slots", 0),
        "best_high_precision": best_high.get("loo_precision", "0.000000"),
        "best_low_feature_set": best_low.get("feature_set", ""),
        "best_low_correct_slots": best_low.get("loo_correct_slots", 0),
        "best_low_false_slots": best_low.get("loo_false_slots", 0),
        "best_low_precision": best_low.get("loo_precision", "0.000000"),
        "selected_high_slots": len(selected),
        "selected_high_rows": len({int(entry["row_index"]) for entry, _p, _c in selected}),
        "selected_low_values": "|".join(
            f"{value}:{count}" for value, count in Counter(str(entry["low"]) for entry in selected_entries).most_common()
        ),
        "selected_low_feature_sets": len(selected_low_candidates),
        "best_selected_low_feature_set": best_selected_low.get("feature_set", ""),
        "best_selected_low_correct_slots": best_selected_low.get("loo_correct_slots", 0),
        "best_selected_low_false_slots": best_selected_low.get("loo_false_slots", 0),
        "best_selected_low_unknown_slots": best_selected_low.get("loo_unknown_slots", 0),
        "false_free_selected_low_sets": len(false_free_selected_low),
        "best_false_free_selected_low_feature_set": best_false_free_selected_low.get("feature_set", ""),
        "best_false_free_selected_low_slots": best_false_free_selected_low.get("loo_correct_slots", 0),
        "best_false_free_selected_low_unknown_slots": best_false_free_selected_low.get("loo_unknown_slots", 0),
        "promotion_candidate_bytes": best_false_free_selected_low.get("loo_correct_slots", 0),
        "promotion_ready_bytes": 0,
        "issue_rows": len(issues),
    }
    return summary, candidates, selected_rows, selected_low_candidates


def render_table(rows: list[dict[str, object]], fields: list[str], limit: int = 240) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, object],
    candidates: list[dict[str, object]],
    selected_rows: list[dict[str, object]],
    selected_low_candidates: list[dict[str, object]],
    title: str,
) -> str:
    data_json = json.dumps(
        {
            "summary": summary,
            "candidates": candidates,
            "selected_rows": selected_rows,
            "selected_low_candidates": selected_low_candidates,
        },
        indent=2,
        sort_keys=True,
    )
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
  <div class="box"><div class="num">{summary['best_byte_correct_slots']}/{summary['best_byte_false_slots']}</div><div class="muted">best byte correct/false</div></div>
  <div class="box"><div class="num">{summary['best_false_free_high_slots']}</div><div class="muted">best false-free high slots</div></div>
  <div class="box"><div class="num">{summary['best_false_free_selected_low_slots']}</div><div class="muted">best false-free selected low slots</div></div>
  <div class="box"><div class="num">{summary['promotion_candidate_bytes']}</div><div class="muted">promotion-candidate bytes</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Selected high slots</h2>{render_table(selected_rows, SELECTED_ROW_FIELDNAMES)}</div>
<div class="panel"><h2>Sequence candidates</h2>{render_table(candidates, CANDIDATE_FIELDNAMES)}</div>
<div class="panel"><h2>Selected low candidates</h2>{render_table(selected_low_candidates, CANDIDATE_FIELDNAMES)}</div>
<script type="application/json" id="mixed-value-sequence-state-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe sequence-state mixed-value payload predictors.")
    parser.add_argument("--input-rows", type=Path, default=DEFAULT_INPUT_ROWS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--max-features", type=int, default=3)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Mixed Value Sequence State Probe")
    args = parser.parse_args()

    summary, candidates, selected_rows, selected_low_candidates = build(
        read_csv(args.input_rows),
        read_csv(args.fixtures),
        max_features=args.max_features,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "candidates.csv", CANDIDATE_FIELDNAMES, candidates)
    write_csv(args.output / "selected_rows.csv", SELECTED_ROW_FIELDNAMES, selected_rows)
    write_csv(args.output / "selected_low_candidates.csv", CANDIDATE_FIELDNAMES, selected_low_candidates)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, candidates, selected_rows, selected_low_candidates, args.title))

    print(
        f"Best byte sequence state: {summary['best_byte_feature_set']} "
        f"{summary['best_byte_correct_slots']}/{summary['best_byte_false_slots']}"
    )
    print(
        f"Best false-free high: {summary['best_false_free_high_feature_set']} "
        f"{summary['best_false_free_high_slots']}"
    )
    print(
        f"Best false-free selected low: {summary['best_false_free_selected_low_feature_set']} "
        f"{summary['best_false_free_selected_low_slots']}"
    )
    print(f"Promotion candidate bytes: {summary['promotion_candidate_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
