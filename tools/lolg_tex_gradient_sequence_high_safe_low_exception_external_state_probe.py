#!/usr/bin/env python3
"""Probe external corpus/source state for minority low exceptions."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gradient_sequence_high_safe_low_exception_probe import (
    CANDIDATE_FIELDNAMES,
    TARGET_FIELDNAMES,
    build_entries,
    exception_targets,
    evaluate_exception_candidate,
    majority_by_bucket,
    strict_prediction,
    target_key,
)
from lolg_tex_gradient_sequence_high_safe_low_exception_probe import (
    SLOT_FIELDNAMES as LOW_EXCEPTION_SLOT_FIELDNAMES,
)
from lolg_tex_micro_mixed_value_payload_state_opcode_probe import int_value, ratio, write_csv


DEFAULT_SLOTS = Path("output/tex_gradient_sequence_high_safe_low_exception/slots.csv")
DEFAULT_OUTPUT = Path("output/tex_gradient_sequence_high_safe_low_exception_external_state")

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "slots",
    "slot_rows",
    "entry_slots",
    "majority_slots",
    "exception_slots",
    "exception_targets",
    "context_families",
    "candidate_rows",
    "best_target",
    "best_context",
    "best_correct_slots",
    "best_false_slots",
    "best_precision",
    "best_coverage",
    "best_target_recall",
    "best_false_free_target",
    "best_false_free_context",
    "best_false_free_slots",
    "combined_best_correct_slots",
    "combined_best_false_slots",
    "combined_best_unknown_slots",
    "combined_best_precision",
    "combined_best_coverage",
    "combined_false_free_slots",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

SLOT_FIELDNAMES = [
    *LOW_EXCEPTION_SLOT_FIELDNAMES,
    "external_state_context",
    "external_state_prediction",
    "external_state_verdict",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def context_functions():
    return {
        "source_profile_offset_seq": lambda row: (row["source_profile_offset"], row["seq_index"]),
        "offset_delta_bucket_seq": lambda row: (row["offset_delta_bucket"], row["seq_index"]),
        "source_byte_seq": lambda row: (row["source_byte"], row["seq_index"]),
        "source_low_seq": lambda row: (row["source_low"], row["seq_index"]),
        "source_target_delta_mod32_seq": lambda row: (
            row["source_target_delta_mod32"],
            row["seq_index"],
        ),
        "transition_source_low_seq": lambda row: (
            row["best_fixed_transition_source_low"],
            row["seq_index"],
        ),
        "transition_source_row_seq": lambda row: (
            row["best_fixed_transition_source_row"],
            row["seq_index"],
        ),
        "control_ref_mod64_seq": lambda row: (row["control_ref_mod64"], row["seq_index"]),
        "control_byte_seq": lambda row: (row["control_byte"], row["seq_index"]),
        "control_low_seq": lambda row: (row["control_low"], row["seq_index"]),
        "start_byte_seq": lambda row: (row["start_byte"], row["seq_index"]),
        "start_low_seq": lambda row: (row["start_low"], row["seq_index"]),
        "prefix_byte_seq": lambda row: (row["prefix_byte"], row["seq_index"]),
        "prefix_low_seq": lambda row: (row["prefix_low"], row["seq_index"]),
        "fragment_byte_seq": lambda row: (row["fragment_byte"], row["seq_index"]),
        "fragment_low_seq": lambda row: (row["fragment_low"], row["seq_index"]),
        "window_head_tail_seq": lambda row: (
            row["window_head_byte"],
            row["window_tail_byte"],
            row["seq_index"],
        ),
        "opcode_state_seq": lambda row: (row["opcode_state_key"], row["seq_index"]),
        "source_control_low_seq": lambda row: (
            row["source_low"],
            row["control_low"],
            row["seq_index"],
        ),
        "fragment_prefix_low_seq": lambda row: (
            row["fragment_low"],
            row["prefix_low"],
            row["seq_index"],
        ),
        "source_fragment_seq": lambda row: (
            row["source_low"],
            row["fragment_low"],
            row["seq_index"],
        ),
        "control_start_seq": lambda row: (
            row["control_byte"],
            row["start_byte"],
            row["seq_index"],
        ),
        "source_transition_seq": lambda row: (
            row["source_low"],
            row["best_fixed_transition_source_low"],
            row["seq_index"],
        ),
        "corpus_position_seq": lambda row: (
            row["archive_key"],
            row["source_profile_offset"],
            row["seq_index"],
        ),
    }


def best_candidate(rows: list[dict[str, object]]) -> dict[str, object]:
    candidates = [
        row
        for row in rows
        if int_value(row, "loo_correct_slots") + int_value(row, "loo_false_slots") > 0
    ]
    return max(
        candidates,
        key=lambda row: (
            int_value(row, "loo_correct_slots"),
            -int_value(row, "loo_false_slots"),
            float(row.get("loo_precision", "0") or 0),
            float(row.get("target_recall", "0") or 0),
            str(row.get("context_family", "")),
        ),
        default={},
    )


def best_false_free_candidate(rows: list[dict[str, object]]) -> dict[str, object]:
    candidates = [
        row
        for row in rows
        if int_value(row, "loo_correct_slots") > 0
        and int_value(row, "loo_false_slots") == 0
    ]
    return max(
        candidates,
        key=lambda row: (
            int_value(row, "loo_correct_slots"),
            -int_value(row, "loo_unknown_slots"),
            str(row.get("context_family", "")),
        ),
        default={},
    )


def evaluate_candidates(
    entries_by_bucket: dict[str, list[dict[str, object]]],
    majority: dict[str, str],
    targets: list[tuple[str, str]],
) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for bucket, target_low in targets:
        entries = entries_by_bucket.get(bucket, [])
        for context_family, context_func in context_functions().items():
            output.append(
                evaluate_exception_candidate(
                    entries,
                    bucket,
                    majority.get(bucket, ""),
                    target_low,
                    context_family,
                    context_func,
                )
            )
    output.sort(
        key=lambda row: (
            str(row["bucket"]),
            str(row["target_low"]),
            -int_value(row, "loo_correct_slots"),
            int_value(row, "loo_false_slots"),
            str(row["context_family"]),
        )
    )
    for index, row in enumerate(output, start=1):
        row["rank"] = index
    return output


def external_predictions(
    entries: list[dict[str, object]],
    target_low: str,
    context_family: str,
) -> dict[str, str]:
    if not context_family:
        return {}
    context_func = context_functions()[context_family]
    all_counts: dict[tuple[object, ...], Counter[str]] = defaultdict(Counter)
    row_counts: dict[tuple[int, tuple[object, ...]], Counter[str]] = defaultdict(Counter)
    entry_by_slot: dict[str, dict[str, object]] = {}
    for entry in entries:
        context = context_func(entry)
        all_counts[context][str(entry["low"])] += 1
        row_counts[(int(entry["row_index"]), context)][str(entry["low"])] += 1
        entry_by_slot[str(entry["slot_rank"])] = entry

    predictions: dict[str, str] = {}
    for slot_rank, entry in entry_by_slot.items():
        context = context_func(entry)
        train_counts = all_counts[context].copy()
        train_counts.subtract(row_counts[(int(entry["row_index"]), context)])
        train_counts += Counter()
        prediction = strict_prediction(train_counts)
        if prediction == target_low:
            predictions[slot_rank] = target_low
    return predictions


def build_target_rows(
    entries_by_bucket: dict[str, list[dict[str, object]]],
    majority: dict[str, str],
    targets: list[tuple[str, str]],
    candidates_by_target: dict[str, list[dict[str, object]]],
) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for bucket, target_low in targets:
        key = target_key(bucket, target_low)
        entries = entries_by_bucket.get(bucket, [])
        candidates = candidates_by_target.get(key, [])
        best = best_candidate(candidates)
        false_free = best_false_free_candidate(candidates)
        target_entries = [entry for entry in entries if str(entry["low"]) == target_low]
        output.append(
            {
                "rank": len(output) + 1,
                "target_key": key,
                "bucket": bucket,
                "majority_low": majority.get(bucket, ""),
                "target_low": target_low,
                "target_slots": len(target_entries),
                "target_rows": len({int(entry["row_index"]) for entry in target_entries}),
                "best_context": best.get("context_family", ""),
                "best_correct_slots": best.get("loo_correct_slots", 0),
                "best_false_slots": best.get("loo_false_slots", 0),
                "best_unknown_slots": best.get("loo_unknown_slots", 0),
                "best_precision": best.get("loo_precision", "0.000000"),
                "best_coverage": best.get("loo_coverage", "0.000000"),
                "best_target_recall": best.get("target_recall", "0.000000"),
                "false_free_context": false_free.get("context_family", ""),
                "false_free_slots": false_free.get("loo_correct_slots", 0),
                "false_free_unknown_slots": false_free.get("loo_unknown_slots", 0),
                "verdict": false_free.get("verdict", best.get("verdict", "")),
            }
        )
    return output


def annotate_rows(
    rows: list[dict[str, object]],
    entries_by_bucket: dict[str, list[dict[str, object]]],
    target_rows: list[dict[str, object]],
) -> tuple[list[dict[str, object]], int, int, int]:
    predictions_by_slot: dict[str, set[str]] = defaultdict(set)
    context_by_prediction: dict[tuple[str, str], str] = {}
    for target in target_rows:
        bucket = str(target["bucket"])
        target_low = str(target["target_low"])
        context = str(target.get("best_context", ""))
        context_by_prediction[(bucket, target_low)] = context
        predictions = external_predictions(entries_by_bucket.get(bucket, []), target_low, context)
        for slot_rank, prediction in predictions.items():
            predictions_by_slot[slot_rank].add(prediction)

    correct = 0
    false = 0
    unknown = 0
    output: list[dict[str, object]] = []
    for row in rows:
        predictions = sorted(predictions_by_slot.get(str(row.get("rank", "")), set()))
        prediction_text = "|".join(predictions)
        context = ""
        verdict = "unknown"
        if len(predictions) == 1:
            prediction = predictions[0]
            context = context_by_prediction.get((str(row.get("low_bucket", "")), prediction), "")
            if prediction == row.get("target_low"):
                verdict = "correct"
                correct += 1
            else:
                verdict = "false"
                false += 1
        elif predictions:
            verdict = "ambiguous"
            false += 1
        else:
            unknown += 1
        output.append(
            {
                **row,
                "external_state_context": context,
                "external_state_prediction": prediction_text,
                "external_state_verdict": verdict,
            }
        )
    return output, correct, false, unknown


def build_summary(
    rows: list[dict[str, object]],
    entries: list[dict[str, object]],
    majority: dict[str, str],
    targets: list[tuple[str, str]],
    candidates: list[dict[str, object]],
    target_rows: list[dict[str, object]],
    combined_correct: int,
    combined_false: int,
    combined_unknown: int,
    issue_rows: int,
) -> dict[str, object]:
    best = best_candidate(candidates)
    false_free = best_false_free_candidate(candidates)
    majority_slots = sum(1 for entry in entries if str(entry["low"]) == majority.get(str(entry["bucket"]), ""))
    exception_slots = len(entries) - majority_slots
    predicted = combined_correct + combined_false
    false_free_slots = sum(int_value(row, "false_free_slots") for row in target_rows)
    return {
        "scope": "total",
        "candidate_mode": "minority_low_external_state_loo",
        "slots": len(rows),
        "slot_rows": len({row.get("row_id", "") for row in rows}),
        "entry_slots": len(entries),
        "majority_slots": majority_slots,
        "exception_slots": exception_slots,
        "exception_targets": "|".join(target_key(bucket, target_low) for bucket, target_low in targets),
        "context_families": len(context_functions()),
        "candidate_rows": len(candidates),
        "best_target": best.get("target_key", ""),
        "best_context": best.get("context_family", ""),
        "best_correct_slots": best.get("loo_correct_slots", 0),
        "best_false_slots": best.get("loo_false_slots", 0),
        "best_precision": best.get("loo_precision", "0.000000"),
        "best_coverage": best.get("loo_coverage", "0.000000"),
        "best_target_recall": best.get("target_recall", "0.000000"),
        "best_false_free_target": false_free.get("target_key", ""),
        "best_false_free_context": false_free.get("context_family", ""),
        "best_false_free_slots": false_free.get("loo_correct_slots", 0),
        "combined_best_correct_slots": combined_correct,
        "combined_best_false_slots": combined_false,
        "combined_best_unknown_slots": combined_unknown,
        "combined_best_precision": ratio(combined_correct, predicted),
        "combined_best_coverage": ratio(predicted, len(entries)),
        "combined_false_free_slots": false_free_slots,
        "promotion_candidate_bytes": false_free_slots,
        "promotion_ready_bytes": 0,
        "issue_rows": issue_rows,
    }


def build(
    slot_rows: list[dict[str, str]],
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    rows, entries, issue_rows = build_entries(slot_rows)
    entries_by_bucket: dict[str, list[dict[str, object]]] = defaultdict(list)
    for entry in entries:
        entries_by_bucket[str(entry["bucket"])].append(entry)
    majority = majority_by_bucket(entries_by_bucket)
    targets = exception_targets(entries_by_bucket, majority)
    candidates = evaluate_candidates(entries_by_bucket, majority, targets)
    candidates_by_target: dict[str, list[dict[str, object]]] = defaultdict(list)
    for candidate in candidates:
        candidates_by_target[str(candidate["target_key"])].append(candidate)
    target_rows = build_target_rows(entries_by_bucket, majority, targets, candidates_by_target)
    rows, combined_correct, combined_false, combined_unknown = annotate_rows(
        rows,
        entries_by_bucket,
        target_rows,
    )
    summary = build_summary(
        rows,
        entries,
        majority,
        targets,
        candidates,
        target_rows,
        combined_correct,
        combined_false,
        combined_unknown,
        issue_rows,
    )
    return summary, rows, target_rows, candidates


def render_table(rows: list[dict[str, object]], fields: list[str], limit: int = 220) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, object],
    rows: list[dict[str, object]],
    target_rows: list[dict[str, object]],
    candidates: list[dict[str, object]],
    title: str,
) -> str:
    data_json = json.dumps(
        {"summary": summary, "slots": rows, "targets": target_rows, "candidates": candidates},
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
  <div class="box"><div class="num">{summary['exception_slots']}</div><div class="muted">exception slots</div></div>
  <div class="box"><div class="num">{summary['combined_best_correct_slots']}/{summary['combined_best_false_slots']}</div><div class="muted">combined correct/false</div></div>
  <div class="box"><div class="num">{summary['best_target']}</div><div class="muted">best target</div></div>
  <div class="box"><div class="num">{summary['combined_false_free_slots']}</div><div class="muted">combined false-free slots</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Targets</h2>{render_table(target_rows, TARGET_FIELDNAMES)}</div>
<div class="panel"><h2>Slots</h2>{render_table(rows, SLOT_FIELDNAMES)}</div>
<div class="panel"><h2>Candidates</h2>{render_table(candidates, CANDIDATE_FIELDNAMES)}</div>
<script type="application/json" id="gradient-sequence-high-safe-low-exception-external-state-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe external state for low exceptions.")
    parser.add_argument("--slots", type=Path, default=DEFAULT_SLOTS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Gradient Sequence High-Safe Low Exception External-State Probe",
    )
    args = parser.parse_args()

    summary, rows, target_rows, candidates = build(read_csv(args.slots))
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "slots.csv", SLOT_FIELDNAMES, rows)
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, target_rows)
    write_csv(args.output / "candidates.csv", CANDIDATE_FIELDNAMES, candidates)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, rows, target_rows, candidates, args.title))

    print(f"Slots: {summary['slots']}")
    print(f"Exception slots: {summary['exception_slots']}")
    print(
        "Combined external-state best: "
        f"{summary['combined_best_correct_slots']} correct / "
        f"{summary['combined_best_false_slots']} false"
    )
    print(
        "Best external target: "
        f"{summary['best_target']} / {summary['best_context']} = "
        f"{summary['best_correct_slots']} correct / {summary['best_false_slots']} false"
    )
    print(f"Combined false-free slots: {summary['combined_false_free_slots']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
