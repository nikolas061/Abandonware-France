#!/usr/bin/env python3
"""Probe exact low resolution after coarse low-bucket split."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gradient_sequence_high_safe_row_template_probe import (
    SLOT_FIELDNAMES as ROW_TEMPLATE_SLOT_FIELDNAMES,
    context_functions as template_context_functions,
    low_bucket,
    strict_prediction,
)
from lolg_tex_micro_mixed_value_payload_state_opcode_probe import (
    evaluate_candidate,
    int_value,
    ratio,
    target_value,
    write_csv,
)


DEFAULT_SLOTS = Path("output/tex_gradient_sequence_high_safe_row_template/slots.csv")
DEFAULT_OUTPUT = Path("output/tex_gradient_sequence_high_safe_low_bucket_split")
BUCKET_ORDER = ("lo", "mid", "hi")

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "slots",
    "slot_rows",
    "entry_slots",
    "buckets",
    "context_families",
    "candidate_rows",
    "best_bucket",
    "best_context",
    "best_correct_slots",
    "best_false_slots",
    "best_precision",
    "best_coverage",
    "best_false_free_bucket",
    "best_false_free_context",
    "best_false_free_slots",
    "combined_best_correct_slots",
    "combined_best_false_slots",
    "combined_best_unknown_slots",
    "combined_best_precision",
    "combined_best_coverage",
    "combined_baseline_correct_slots",
    "combined_baseline_precision",
    "combined_false_free_slots",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

BUCKET_FIELDNAMES = [
    "rank",
    "bucket",
    "values",
    "slots",
    "slot_rows",
    "baseline_low",
    "baseline_correct_slots",
    "baseline_precision",
    "best_context",
    "best_correct_slots",
    "best_false_slots",
    "best_unknown_slots",
    "best_precision",
    "best_coverage",
    "false_free_context",
    "false_free_slots",
    "verdict",
]

CANDIDATE_FIELDNAMES = [
    "rank",
    "bucket",
    "target_kind",
    "context_family",
    "contexts",
    "deterministic_repeated_slots",
    "deterministic_singleton_slots",
    "conflicted_slots",
    "loo_correct_slots",
    "loo_false_slots",
    "loo_unknown_slots",
    "loo_precision",
    "loo_coverage",
    "baseline_value",
    "baseline_correct_slots",
    "baseline_precision",
    "predicted_values",
    "verdict",
    "sample_context",
    "sample_prediction",
]

SLOT_FIELDNAMES = [
    *ROW_TEMPLATE_SLOT_FIELDNAMES,
    "bucket_split_context",
    "bucket_split_prediction",
    "bucket_split_verdict",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def context_functions():
    functions = dict(template_context_functions())
    functions.update(
        {
            "bucket_payload_target_x": lambda row: (
                row["payload_pos16"],
                row["target_x_mod32"],
            ),
            "bucket_payload_quarter_edge": lambda row: (
                row["payload_pos16"],
                row["row_quarter"],
                row["row_edge8"],
            ),
            "bucket_prev_low_seq": lambda row: (row["prev_low1"], row["seq_index"]),
            "bucket_prev_low_target_x": lambda row: (
                row["prev_low1"],
                row["target_x_mod32"],
            ),
            "bucket_prev_low_quarter": lambda row: (
                row["prev_low1"],
                row["row_quarter"],
                row["row_third"],
            ),
            "bucket_prev_pair_seq": lambda row: (row["prev_pair"], row["seq_index"]),
            "bucket_prev_delta_seq": lambda row: (row["prevprev_delta"], row["seq_index"]),
            "bucket_source_prev_low": lambda row: (
                row["source_low"],
                row["prev_low1"],
                row["row_quarter"],
            ),
            "bucket_source_target_shape": lambda row: (
                row["source_low"],
                row["target_x_mod32"],
                row["shape_start_key"],
            ),
            "bucket_opcode_source": lambda row: (
                row["op_band8"],
                row["source_low"],
                row["target_x_mod32"],
            ),
            "bucket_frontier_source": lambda row: (
                row["frontier_band8"],
                row["source_low"],
                row["target_x_mod32"],
            ),
        }
    )
    return functions


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
            float(row.get("loo_coverage", "0") or 0),
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


def baseline(entries: list[dict[str, object]]) -> tuple[str, int, str]:
    values = Counter(target_value(entry, "low") for entry in entries)
    if not values:
        return "", 0, "0.000000"
    value, count = values.most_common(1)[0]
    return value, count, ratio(count, len(entries))


def loo_predictions(entries: list[dict[str, object]], context_family: str) -> dict[str, str]:
    if not context_family:
        return {}
    context_func = context_functions()[context_family]
    all_counts: dict[tuple[object, ...], Counter[str]] = defaultdict(Counter)
    row_counts: dict[tuple[int, tuple[object, ...]], Counter[str]] = defaultdict(Counter)
    entry_by_slot: dict[str, dict[str, object]] = {}
    for entry in entries:
        context = context_func(entry)
        all_counts[context][target_value(entry, "low")] += 1
        row_counts[(int(entry["row_index"]), context)][target_value(entry, "low")] += 1
        entry_by_slot[str(entry["slot_rank"])] = entry

    output: dict[str, str] = {}
    for slot_rank, entry in entry_by_slot.items():
        context = context_func(entry)
        train_counts = all_counts[context].copy()
        train_counts.subtract(row_counts[(int(entry["row_index"]), context)])
        train_counts += Counter()
        prediction = strict_prediction(train_counts)
        if prediction is not None:
            output[slot_rank] = prediction
    return output


def build_entries(slot_rows: list[dict[str, str]]) -> tuple[list[dict[str, object]], list[dict[str, object]], int]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for slot in slot_rows:
        grouped[str(slot.get("row_id", ""))].append(slot)
    row_indexes = {row_id: index for index, row_id in enumerate(sorted(grouped))}
    rows: list[dict[str, object]] = []
    entries: list[dict[str, object]] = []
    issue_rows = 0
    for row_id, members in grouped.items():
        for slot in sorted(members, key=lambda row: int_value(row, "relative_offset")):
            bucket = slot.get("low_bucket", "") or low_bucket(slot.get("target_low", ""))
            row = {**slot, "low_bucket": bucket}
            rows.append(row)
            if bucket not in BUCKET_ORDER:
                issue_rows += 1
                continue
            entries.append(
                {
                    **row,
                    "row_index": row_indexes[row_id],
                    "slot_rank": slot.get("rank", ""),
                    "low": slot.get("target_low", ""),
                    "bucket": bucket,
                }
            )
    return rows, entries, issue_rows


def evaluate_candidates(entries_by_bucket: dict[str, list[dict[str, object]]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for bucket in BUCKET_ORDER:
        entries = entries_by_bucket.get(bucket, [])
        for context_family, context_func in context_functions().items():
            row = evaluate_candidate(entries, "low", context_family, context_func)
            row["bucket"] = bucket
            rows.append(row)
    rows.sort(
        key=lambda row: (
            BUCKET_ORDER.index(str(row["bucket"])),
            -int_value(row, "loo_correct_slots"),
            int_value(row, "loo_false_slots"),
            str(row["context_family"]),
        )
    )
    for index, row in enumerate(rows, start=1):
        row["rank"] = index
    return rows


def bucket_verdict(best: dict[str, object], false_free: dict[str, object], base_precision: str) -> str:
    correct = int_value(best, "loo_correct_slots")
    false = int_value(best, "loo_false_slots")
    precision = float(best.get("loo_precision", "0") or 0)
    baseline_precision = float(base_precision or 0)
    if int_value(false_free, "loo_correct_slots") >= 16:
        return "false_free_bucket_review"
    if correct > false and precision > baseline_precision:
        return "partial_bucket_hint"
    if correct > 0:
        return "conflicted_bucket_context"
    return "no_cross_row_state"


def build_bucket_rows(
    entries_by_bucket: dict[str, list[dict[str, object]]],
    candidates_by_bucket: dict[str, list[dict[str, object]]],
) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for bucket in BUCKET_ORDER:
        entries = entries_by_bucket.get(bucket, [])
        candidates = candidates_by_bucket.get(bucket, [])
        best = best_candidate(candidates)
        false_free = best_false_free_candidate(candidates)
        base_low, base_correct, base_precision = baseline(entries)
        output.append(
            {
                "rank": len(output) + 1,
                "bucket": bucket,
                "values": "|".join(f"{value}:{count}" for value, count in Counter(entry["low"] for entry in entries).most_common()),
                "slots": len(entries),
                "slot_rows": len({int(entry["row_index"]) for entry in entries}),
                "baseline_low": base_low,
                "baseline_correct_slots": base_correct,
                "baseline_precision": base_precision,
                "best_context": best.get("context_family", ""),
                "best_correct_slots": best.get("loo_correct_slots", 0),
                "best_false_slots": best.get("loo_false_slots", 0),
                "best_unknown_slots": best.get("loo_unknown_slots", 0),
                "best_precision": best.get("loo_precision", "0.000000"),
                "best_coverage": best.get("loo_coverage", "0.000000"),
                "false_free_context": false_free.get("context_family", ""),
                "false_free_slots": false_free.get("loo_correct_slots", 0),
                "verdict": bucket_verdict(best, false_free, base_precision),
            }
        )
    return output


def annotate_rows(
    rows: list[dict[str, object]],
    entries_by_bucket: dict[str, list[dict[str, object]]],
    best_by_bucket: dict[str, dict[str, object]],
) -> tuple[list[dict[str, object]], int, int, int]:
    predictions_by_bucket = {
        bucket: loo_predictions(entries_by_bucket.get(bucket, []), str(best.get("context_family", "")))
        for bucket, best in best_by_bucket.items()
    }
    correct = 0
    false = 0
    unknown = 0
    output: list[dict[str, object]] = []
    for row in rows:
        bucket = str(row.get("low_bucket", ""))
        best = best_by_bucket.get(bucket, {})
        predictions = predictions_by_bucket.get(bucket, {})
        prediction = predictions.get(str(row.get("rank", "")), "")
        verdict = "unknown"
        if prediction:
            if prediction == row.get("target_low"):
                verdict = "correct"
                correct += 1
            else:
                verdict = "false"
                false += 1
        else:
            unknown += 1
        annotated = dict(row)
        annotated.update(
            {
                "bucket_split_context": best.get("context_family", ""),
                "bucket_split_prediction": prediction,
                "bucket_split_verdict": verdict,
            }
        )
        output.append(annotated)
    return output, correct, false, unknown


def build_summary(
    rows: list[dict[str, object]],
    entries: list[dict[str, object]],
    candidates: list[dict[str, object]],
    bucket_rows: list[dict[str, object]],
    combined_correct: int,
    combined_false: int,
    combined_unknown: int,
    issue_rows: int,
) -> dict[str, object]:
    best = best_candidate(candidates)
    false_free = best_false_free_candidate(candidates)
    baseline_correct = sum(int_value(row, "baseline_correct_slots") for row in bucket_rows)
    false_free_slots = sum(int_value(row, "false_free_slots") for row in bucket_rows)
    predicted = combined_correct + combined_false
    return {
        "scope": "total",
        "candidate_mode": "actual_bucket_low_loo",
        "slots": len(rows),
        "slot_rows": len({row.get("row_id", "") for row in rows}),
        "entry_slots": len(entries),
        "buckets": "|".join(BUCKET_ORDER),
        "context_families": len(context_functions()),
        "candidate_rows": len(candidates),
        "best_bucket": best.get("bucket", ""),
        "best_context": best.get("context_family", ""),
        "best_correct_slots": best.get("loo_correct_slots", 0),
        "best_false_slots": best.get("loo_false_slots", 0),
        "best_precision": best.get("loo_precision", "0.000000"),
        "best_coverage": best.get("loo_coverage", "0.000000"),
        "best_false_free_bucket": false_free.get("bucket", ""),
        "best_false_free_context": false_free.get("context_family", ""),
        "best_false_free_slots": false_free.get("loo_correct_slots", 0),
        "combined_best_correct_slots": combined_correct,
        "combined_best_false_slots": combined_false,
        "combined_best_unknown_slots": combined_unknown,
        "combined_best_precision": ratio(combined_correct, predicted),
        "combined_best_coverage": ratio(predicted, len(entries)),
        "combined_baseline_correct_slots": baseline_correct,
        "combined_baseline_precision": ratio(baseline_correct, len(entries)),
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
    candidates = evaluate_candidates(entries_by_bucket)
    candidates_by_bucket: dict[str, list[dict[str, object]]] = defaultdict(list)
    for candidate in candidates:
        candidates_by_bucket[str(candidate["bucket"])].append(candidate)
    bucket_rows = build_bucket_rows(entries_by_bucket, candidates_by_bucket)
    best_by_bucket = {
        bucket: best_candidate(candidates_by_bucket.get(bucket, []))
        for bucket in BUCKET_ORDER
    }
    rows, combined_correct, combined_false, combined_unknown = annotate_rows(
        rows,
        entries_by_bucket,
        best_by_bucket,
    )
    summary = build_summary(
        rows,
        entries,
        candidates,
        bucket_rows,
        combined_correct,
        combined_false,
        combined_unknown,
        issue_rows,
    )
    return summary, rows, bucket_rows, candidates


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
    bucket_rows: list[dict[str, object]],
    candidates: list[dict[str, object]],
    title: str,
) -> str:
    data_json = json.dumps(
        {"summary": summary, "slots": rows, "buckets": bucket_rows, "candidates": candidates},
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
  <div class="box"><div class="num">{summary['combined_best_correct_slots']}/{summary['combined_best_false_slots']}</div><div class="muted">combined correct/false</div></div>
  <div class="box"><div class="num">{summary['combined_baseline_correct_slots']}</div><div class="muted">bucket baseline correct</div></div>
  <div class="box"><div class="num">{summary['combined_false_free_slots']}</div><div class="muted">combined false-free slots</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Buckets</h2>{render_table(bucket_rows, BUCKET_FIELDNAMES)}</div>
<div class="panel"><h2>Slots</h2>{render_table(rows, SLOT_FIELDNAMES)}</div>
<div class="panel"><h2>Candidates</h2>{render_table(candidates, CANDIDATE_FIELDNAMES)}</div>
<script type="application/json" id="gradient-sequence-high-safe-low-bucket-split-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe exact low resolution after low-bucket split.")
    parser.add_argument("--slots", type=Path, default=DEFAULT_SLOTS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Gradient Sequence High-Safe Low-Bucket Split Probe",
    )
    args = parser.parse_args()

    summary, rows, bucket_rows, candidates = build(read_csv(args.slots))
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "slots.csv", SLOT_FIELDNAMES, rows)
    write_csv(args.output / "buckets.csv", BUCKET_FIELDNAMES, bucket_rows)
    write_csv(args.output / "candidates.csv", CANDIDATE_FIELDNAMES, candidates)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, rows, bucket_rows, candidates, args.title))

    print(f"Slots: {summary['slots']}")
    print(
        "Combined best split: "
        f"{summary['combined_best_correct_slots']} correct / "
        f"{summary['combined_best_false_slots']} false"
    )
    print(
        "Best bucket resolver: "
        f"{summary['best_bucket']} / {summary['best_context']} = "
        f"{summary['best_correct_slots']} correct / {summary['best_false_slots']} false"
    )
    print(f"Combined false-free slots: {summary['combined_false_free_slots']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
