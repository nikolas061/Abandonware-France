#!/usr/bin/env python3
"""Probe cross-row alignment for minority low exceptions."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gradient_sequence_high_safe_low_exception_probe import (
    SLOT_FIELDNAMES as LOW_EXCEPTION_SLOT_FIELDNAMES,
    low_bucket,
)
from lolg_tex_micro_mixed_value_payload_state_opcode_probe import int_value, ratio, write_csv


DEFAULT_SLOTS = Path("output/tex_gradient_sequence_high_safe_low_exception/slots.csv")
DEFAULT_OUTPUT = Path("output/tex_gradient_sequence_high_safe_low_exception_alignment")
SHIFT_RANGE = range(-12, 13)
MAJORITY_LOW_BY_BUCKET = {"lo": "8", "mid": "9", "hi": "b"}

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "slots",
    "slot_rows",
    "exception_slots",
    "alignments",
    "shift_min",
    "shift_max",
    "best_mode",
    "best_shift",
    "best_target_row",
    "best_source_row",
    "best_correct_slots",
    "best_false_slots",
    "best_precision",
    "best_coverage",
    "best_false_free_mode",
    "best_false_free_shift",
    "best_false_free_target_row",
    "best_false_free_source_row",
    "best_false_free_slots",
    "same_bucket_false_free_alignments",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

ALIGNMENT_FIELDNAMES = [
    "rank",
    "mode",
    "shift",
    "target_row_id",
    "source_row_id",
    "target_archive",
    "target_pcx_name",
    "target_frontier_id",
    "target_start",
    "target_end",
    "source_frontier_id",
    "source_start",
    "source_end",
    "source_exception_slots",
    "predicted_slots",
    "correct_slots",
    "false_slots",
    "unknown_slots",
    "precision",
    "coverage",
    "predicted_lows",
    "sample_false",
    "verdict",
]

SLOT_FIELDNAMES = [
    *LOW_EXCEPTION_SLOT_FIELDNAMES,
    "alignment_mode",
    "alignment_source_row",
    "alignment_shift",
    "alignment_prediction",
    "alignment_verdict",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def majority_low(row: dict[str, object]) -> str:
    bucket = str(row.get("low_bucket", "")) or low_bucket(str(row.get("target_low", "")))
    return MAJORITY_LOW_BY_BUCKET.get(bucket, "")


def is_exception(row: dict[str, object]) -> bool:
    return str(row.get("target_low", "")) != majority_low(row)


def build_rows(slot_rows: list[dict[str, str]]) -> tuple[list[dict[str, object]], dict[str, dict[int, dict[str, object]]], int]:
    rows: list[dict[str, object]] = []
    by_row: dict[str, dict[int, dict[str, object]]] = defaultdict(dict)
    issue_rows = 0
    for slot in slot_rows:
        bucket = slot.get("low_bucket", "") or low_bucket(slot.get("target_low", ""))
        row = {**slot, "low_bucket": bucket}
        try:
            seq_index = int(row.get("seq_index", ""))
        except (TypeError, ValueError):
            issue_rows += 1
            rows.append(row)
            continue
        rows.append(row)
        by_row[str(row.get("row_id", ""))][seq_index] = row
    return rows, by_row, issue_rows


def row_meta(row_id: str, members: dict[int, dict[str, object]]) -> dict[str, str]:
    sample = next(iter(members.values()), {})
    return {
        "archive": str(sample.get("archive", "")),
        "pcx_name": str(sample.get("pcx_name", "")),
        "frontier_id": str(sample.get("frontier_id", "")),
        "start": str(sample.get("start", "")),
        "end": str(sample.get("end", "")),
    }


def evaluate_alignment(
    target_row_id: str,
    target_slots: dict[int, dict[str, object]],
    source_row_id: str,
    source_slots: dict[int, dict[str, object]],
    shift: int,
    mode: str,
) -> dict[str, object] | None:
    predicted = 0
    correct = 0
    false = 0
    predicted_lows: Counter[str] = Counter()
    sample_false = ""
    for seq_index, target in target_slots.items():
        source = source_slots.get(seq_index + shift)
        if not source or not is_exception(source):
            continue
        if mode == "same_bucket" and source.get("low_bucket", "") != target.get("low_bucket", ""):
            continue
        prediction = str(source.get("target_low", ""))
        predicted += 1
        predicted_lows[prediction] += 1
        if prediction == str(target.get("target_low", "")):
            correct += 1
        else:
            false += 1
            if not sample_false:
                sample_false = (
                    f"seq={seq_index};pred={prediction};"
                    f"actual={target.get('target_low', '')};source_seq={seq_index + shift}"
                )
    if predicted == 0:
        return None
    target_meta = row_meta(target_row_id, target_slots)
    source_meta = row_meta(source_row_id, source_slots)
    if false == 0 and correct >= 4:
        verdict = "false_free_peer_alignment_review"
    elif false == 0:
        verdict = "sparse_false_free_peer_alignment"
    elif correct > false:
        verdict = "partial_peer_alignment_hint"
    else:
        verdict = "conflicted_peer_alignment"
    return {
        "rank": 0,
        "mode": mode,
        "shift": shift,
        "target_row_id": target_row_id,
        "source_row_id": source_row_id,
        "target_archive": target_meta["archive"],
        "target_pcx_name": target_meta["pcx_name"],
        "target_frontier_id": target_meta["frontier_id"],
        "target_start": target_meta["start"],
        "target_end": target_meta["end"],
        "source_frontier_id": source_meta["frontier_id"],
        "source_start": source_meta["start"],
        "source_end": source_meta["end"],
        "source_exception_slots": sum(1 for row in source_slots.values() if is_exception(row)),
        "predicted_slots": predicted,
        "correct_slots": correct,
        "false_slots": false,
        "unknown_slots": len(target_slots) - predicted,
        "precision": ratio(correct, predicted),
        "coverage": ratio(predicted, len(target_slots)),
        "predicted_lows": "|".join(f"{low}:{count}" for low, count in predicted_lows.most_common()),
        "sample_false": sample_false,
        "verdict": verdict,
    }


def build_alignments(by_row: dict[str, dict[int, dict[str, object]]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for target_row_id, target_slots in by_row.items():
        for source_row_id, source_slots in by_row.items():
            if source_row_id == target_row_id:
                continue
            for shift in SHIFT_RANGE:
                for mode in ("exact", "same_bucket"):
                    alignment = evaluate_alignment(
                        target_row_id,
                        target_slots,
                        source_row_id,
                        source_slots,
                        shift,
                        mode,
                    )
                    if alignment:
                        rows.append(alignment)
    rows.sort(
        key=lambda row: (
            -int_value(row, "correct_slots"),
            int_value(row, "false_slots"),
            -int_value(row, "predicted_slots"),
            str(row["mode"]),
            int_value(row, "shift"),
            str(row["target_row_id"]),
            str(row["source_row_id"]),
        )
    )
    for index, row in enumerate(rows, start=1):
        row["rank"] = index
    return rows


def best_false_free(rows: list[dict[str, object]]) -> dict[str, object]:
    candidates = [
        row
        for row in rows
        if int_value(row, "correct_slots") > 0 and int_value(row, "false_slots") == 0
    ]
    return max(
        candidates,
        key=lambda row: (
            int_value(row, "correct_slots"),
            int_value(row, "predicted_slots"),
            str(row.get("mode", "")) == "same_bucket",
            -abs(int_value(row, "shift")),
        ),
        default={},
    )


def annotate_rows(
    rows: list[dict[str, object]],
    by_row: dict[str, dict[int, dict[str, object]]],
    alignment: dict[str, object],
) -> list[dict[str, object]]:
    if not alignment:
        return [
            {
                **row,
                "alignment_mode": "",
                "alignment_source_row": "",
                "alignment_shift": "",
                "alignment_prediction": "",
                "alignment_verdict": "unknown",
            }
            for row in rows
        ]
    target_row_id = str(alignment.get("target_row_id", ""))
    source_row_id = str(alignment.get("source_row_id", ""))
    shift = int_value(alignment, "shift")
    mode = str(alignment.get("mode", ""))
    source_slots = by_row.get(source_row_id, {})
    output: list[dict[str, object]] = []
    for row in rows:
        prediction = ""
        verdict = "unknown"
        if row.get("row_id", "") == target_row_id:
            try:
                seq_index = int(str(row.get("seq_index", "")))
            except ValueError:
                seq_index = -9999
            source = source_slots.get(seq_index + shift)
            if source and is_exception(source):
                if mode != "same_bucket" or source.get("low_bucket", "") == row.get("low_bucket", ""):
                    prediction = str(source.get("target_low", ""))
                    verdict = "correct" if prediction == row.get("target_low", "") else "false"
        output.append(
            {
                **row,
                "alignment_mode": mode if row.get("row_id", "") == target_row_id else "",
                "alignment_source_row": source_row_id if row.get("row_id", "") == target_row_id else "",
                "alignment_shift": shift if row.get("row_id", "") == target_row_id else "",
                "alignment_prediction": prediction,
                "alignment_verdict": verdict,
            }
        )
    return output


def build_summary(
    rows: list[dict[str, object]],
    by_row: dict[str, dict[int, dict[str, object]]],
    alignments: list[dict[str, object]],
    issue_rows: int,
) -> dict[str, object]:
    best = alignments[0] if alignments else {}
    false_free = best_false_free(alignments)
    same_bucket_false_free = sum(
        1
        for row in alignments
        if row.get("mode") == "same_bucket"
        and int_value(row, "correct_slots") > 0
        and int_value(row, "false_slots") == 0
    )
    return {
        "scope": "total",
        "candidate_mode": "peer_exception_shift_alignment",
        "slots": len(rows),
        "slot_rows": len(by_row),
        "exception_slots": sum(1 for row in rows if is_exception(row)),
        "alignments": len(alignments),
        "shift_min": min(SHIFT_RANGE),
        "shift_max": max(SHIFT_RANGE),
        "best_mode": best.get("mode", ""),
        "best_shift": best.get("shift", ""),
        "best_target_row": best.get("target_row_id", ""),
        "best_source_row": best.get("source_row_id", ""),
        "best_correct_slots": best.get("correct_slots", 0),
        "best_false_slots": best.get("false_slots", 0),
        "best_precision": best.get("precision", "0.000000"),
        "best_coverage": best.get("coverage", "0.000000"),
        "best_false_free_mode": false_free.get("mode", ""),
        "best_false_free_shift": false_free.get("shift", ""),
        "best_false_free_target_row": false_free.get("target_row_id", ""),
        "best_false_free_source_row": false_free.get("source_row_id", ""),
        "best_false_free_slots": false_free.get("correct_slots", 0),
        "same_bucket_false_free_alignments": same_bucket_false_free,
        "promotion_candidate_bytes": false_free.get("correct_slots", 0),
        "promotion_ready_bytes": 0,
        "issue_rows": issue_rows,
    }


def build(
    slot_rows: list[dict[str, str]],
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    rows, by_row, issue_rows = build_rows(slot_rows)
    alignments = build_alignments(by_row)
    false_free = best_false_free(alignments)
    rows = annotate_rows(rows, by_row, false_free)
    summary = build_summary(rows, by_row, alignments, issue_rows)
    return summary, rows, alignments


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
    alignments: list[dict[str, object]],
    title: str,
) -> str:
    data_json = json.dumps(
        {"summary": summary, "slots": rows, "alignments": alignments},
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
  <div class="box"><div class="num">{summary['best_correct_slots']}/{summary['best_false_slots']}</div><div class="muted">best correct/false</div></div>
  <div class="box"><div class="num">{summary['best_false_free_slots']}</div><div class="muted">best false-free slots</div></div>
  <div class="box"><div class="num">{summary['same_bucket_false_free_alignments']}</div><div class="muted">same-bucket false-free alignments</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Alignments</h2>{render_table(alignments, ALIGNMENT_FIELDNAMES)}</div>
<div class="panel"><h2>Slots</h2>{render_table(rows, SLOT_FIELDNAMES)}</div>
<script type="application/json" id="gradient-sequence-high-safe-low-exception-alignment-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe cross-row alignment for low exceptions.")
    parser.add_argument("--slots", type=Path, default=DEFAULT_SLOTS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Gradient Sequence High-Safe Low Exception Alignment Probe",
    )
    args = parser.parse_args()

    summary, rows, alignments = build(read_csv(args.slots))
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "slots.csv", SLOT_FIELDNAMES, rows)
    write_csv(args.output / "alignments.csv", ALIGNMENT_FIELDNAMES, alignments)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, rows, alignments, args.title))

    print(f"Slots: {summary['slots']}")
    print(f"Exception slots: {summary['exception_slots']}")
    print(
        "Best alignment: "
        f"{summary['best_mode']} shift {summary['best_shift']} = "
        f"{summary['best_correct_slots']} correct / {summary['best_false_slots']} false"
    )
    print(
        "Best false-free alignment: "
        f"{summary['best_false_free_mode']} shift {summary['best_false_free_shift']} = "
        f"{summary['best_false_free_slots']} slots"
    )
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
