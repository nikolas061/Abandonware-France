#!/usr/bin/env python3
"""Probe row-template low grammar for high-safe gradient residual slots."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gradient_sequence_high_safe_row_markov_probe import (
    SLOT_FIELDNAMES as ROW_MARKOV_SLOT_FIELDNAMES,
)
from lolg_tex_micro_mixed_value_payload_state_opcode_probe import (
    evaluate_candidate,
    int_value,
    ratio,
    target_value,
    write_csv,
)


DEFAULT_SLOTS = Path("output/tex_gradient_sequence_high_safe_row_markov/slots.csv")
DEFAULT_OUTPUT = Path("output/tex_gradient_sequence_high_safe_row_template")

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "slots",
    "slot_rows",
    "entry_slots",
    "context_families",
    "candidate_rows",
    "best_low_context",
    "best_low_correct_slots",
    "best_low_false_slots",
    "best_low_precision",
    "best_low_coverage",
    "best_low_bucket_context",
    "best_low_bucket_correct_slots",
    "best_low_bucket_false_slots",
    "best_low_bucket_precision",
    "best_low_bucket_coverage",
    "best_low_false_free_context",
    "best_low_false_free_slots",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

CANDIDATE_FIELDNAMES = [
    "rank",
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

CONTEXT_FIELDNAMES = [
    "rank",
    "target_kind",
    "context_family",
    "context_key",
    "slots",
    "rows",
    "target_values",
    "dominant_value",
    "dominant_ratio",
    "sample_pcx",
    "sample_frontier_id",
    "verdict",
]

SLOT_FIELDNAMES = [
    *ROW_MARKOV_SLOT_FIELDNAMES,
    "frontier_band8",
    "op_band8",
    "start_band320",
    "start_phase320",
    "payload_pos16",
    "low_bucket",
    "best_template_context",
    "best_template_prediction",
    "best_template_verdict",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def low_bucket(value: str) -> str:
    if value in {"6", "7", "8"}:
        return "lo"
    if value in {"9", "a"}:
        return "mid"
    if value in {"b", "c"}:
        return "hi"
    return "other"


def context_functions():
    return {
        "seq_index": lambda row: (row["seq_index"],),
        "payload_pos16": lambda row: (row["payload_pos16"],),
        "rel_mod8": lambda row: (row["rel_mod8"],),
        "target_x": lambda row: (row["target_x_mod32"],),
        "target_x_third": lambda row: (row["target_x_mod32"], row["row_third"]),
        "target_x_quarter": lambda row: (row["target_x_mod32"], row["row_quarter"]),
        "target_x_offset": lambda row: (row["target_x_mod32"], row["offset_delta_bucket"]),
        "target_x_source_zero": lambda row: (row["target_x_mod32"], row["source_zero"]),
        "seq_source_zero": lambda row: (row["seq_index"], row["source_zero"]),
        "rel8_source_zero": lambda row: (row["rel_mod8"], row["source_zero"]),
        "target_x_third_gradient": lambda row: (
            row["target_x_mod32"],
            row["row_third"],
            row["gradient_class"],
        ),
        "rel4_target_x_target_y_third": lambda row: (
            row["rel_mod4"],
            row["target_x_mod32"],
            row["target_y_mod8"],
            row["row_third"],
        ),
        "rel4_target_x_third_start_band": lambda row: (
            row["rel_mod4"],
            row["target_x_mod32"],
            row["row_third"],
            row["start_band320"],
        ),
        "target_x_quarter_edge": lambda row: (
            row["target_x_mod32"],
            row["row_quarter"],
            row["row_edge8"],
        ),
        "target_x_quarter_edge_start_band": lambda row: (
            row["target_x_mod32"],
            row["row_quarter"],
            row["row_edge8"],
            row["start_band320"],
        ),
        "rel8_quarter_third": lambda row: (
            row["rel_mod8"],
            row["row_quarter"],
            row["row_third"],
        ),
        "rel4_third_shape_source_low": lambda row: (
            row["rel_mod4"],
            row["row_third"],
            row["shape_start_key"],
            row["source_low"],
        ),
        "rel8_quarter_frontier_source_low": lambda row: (
            row["rel_mod8"],
            row["row_quarter"],
            row["frontier_band8"],
            row["source_low"],
        ),
        "rel8_quarter_start_pool": lambda row: (
            row["rel_mod8"],
            row["row_quarter"],
            row["start_mod64"],
            row["pool"],
        ),
        "rel8_quarter_start_gradient": lambda row: (
            row["rel_mod8"],
            row["row_quarter"],
            row["start_mod64"],
            row["gradient_class"],
        ),
        "shape_source_low": lambda row: (row["shape_start_key"], row["source_low"]),
        "source_low_target_x": lambda row: (row["source_low"], row["target_x_mod32"]),
        "source_low_rel8": lambda row: (row["source_low"], row["rel_mod8"]),
        "opcode_position": lambda row: (row["op_band8"], row["target_x_mod32"], row["row_third"]),
        "frontier_position": lambda row: (row["frontier_band8"], row["target_x_mod32"], row["row_third"]),
    }


def strict_prediction(counter: Counter[str]) -> str | None:
    values = [value for value, count in counter.items() if count > 0]
    return values[0] if len(values) == 1 else None


def best_candidate(rows: list[dict[str, object]], target_kind: str) -> dict[str, object]:
    candidates = [
        row
        for row in rows
        if row.get("target_kind") == target_kind
        and int_value(row, "loo_correct_slots") + int_value(row, "loo_false_slots") > 0
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


def best_false_free_candidate(rows: list[dict[str, object]], target_kind: str) -> dict[str, object]:
    candidates = [
        row
        for row in rows
        if row.get("target_kind") == target_kind
        and int_value(row, "loo_correct_slots") > 0
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


def evaluate_candidates(entries: list[dict[str, object]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for target_kind in ("low", "low_bucket"):
        for context_family, context_func in context_functions().items():
            rows.append(evaluate_candidate(entries, target_kind, context_family, context_func))
    rows.sort(
        key=lambda row: (
            str(row["target_kind"]),
            -int_value(row, "loo_correct_slots"),
            int_value(row, "loo_false_slots"),
            str(row["context_family"]),
        )
    )
    for index, row in enumerate(rows, start=1):
        row["rank"] = index
    return rows


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


def build_entries(slot_rows: list[dict[str, str]]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for slot in slot_rows:
        grouped[str(slot.get("row_id", ""))].append(slot)
    row_indexes = {row_id: index for index, row_id in enumerate(sorted(grouped))}
    rows: list[dict[str, object]] = []
    entries: list[dict[str, object]] = []
    for row_id, members in grouped.items():
        members = sorted(members, key=lambda row: int_value(row, "relative_offset"))
        for index, slot in enumerate(members):
            start = int_value(slot, "start")
            frontier = int_value(slot, "frontier_id")
            op_index = int_value(slot, "op_index", -1)
            row = {
                **slot,
                "frontier_band8": str((frontier // 8) * 8),
                "op_band8": "NA" if op_index < 0 else str((op_index // 8) * 8),
                "start_band320": str((start // 320) * 320),
                "start_phase320": str(start % 320),
                "payload_pos16": str((index * 16) // len(members)) if members else "NA",
                "low_bucket": low_bucket(slot.get("target_low", "")),
            }
            rows.append(row)
            entries.append(
                {
                    **row,
                    "row_index": row_indexes[row_id],
                    "slot_rank": slot.get("rank", ""),
                    "low": slot.get("target_low", ""),
                }
            )
    return rows, entries


def build_context_rows(
    entries: list[dict[str, object]],
    candidates: list[dict[str, object]],
) -> list[dict[str, object]]:
    families_by_target: dict[str, set[str]] = defaultdict(set)
    for target_kind in ("low", "low_bucket"):
        ranked = [
            row
            for row in candidates
            if row.get("target_kind") == target_kind
            and int_value(row, "loo_correct_slots") + int_value(row, "loo_false_slots") > 0
        ]
        ranked.sort(
            key=lambda row: (
                int_value(row, "loo_correct_slots"),
                -int_value(row, "loo_false_slots"),
                str(row.get("context_family", "")),
            ),
            reverse=True,
        )
        for row in ranked[:5]:
            families_by_target[target_kind].add(str(row.get("context_family", "")))

    output: list[dict[str, object]] = []
    for target_kind, families in families_by_target.items():
        for family in sorted(families):
            context_func = context_functions()[family]
            grouped: dict[tuple[object, ...], list[dict[str, object]]] = defaultdict(list)
            for entry in entries:
                grouped[context_func(entry)].append(entry)
            for context, group in grouped.items():
                if len(group) < 2:
                    continue
                values = Counter(target_value(entry, target_kind) for entry in group)
                dominant_value, dominant_count = values.most_common(1)[0]
                output.append(
                    {
                        "rank": 0,
                        "target_kind": target_kind,
                        "context_family": family,
                        "context_key": "|".join(str(part) for part in context),
                        "slots": len(group),
                        "rows": len({int(entry["row_index"]) for entry in group}),
                        "target_values": "|".join(
                            f"{value}:{count}" for value, count in values.most_common(10)
                        ),
                        "dominant_value": dominant_value,
                        "dominant_ratio": ratio(dominant_count, len(group)),
                        "sample_pcx": group[0].get("pcx_name", ""),
                        "sample_frontier_id": group[0].get("frontier_id", ""),
                        "verdict": "deterministic_context" if len(values) == 1 else "conflicted_context",
                    }
                )
    output.sort(
        key=lambda row: (
            str(row["target_kind"]),
            str(row["context_family"]),
            -int_value(row, "slots"),
            str(row["context_key"]),
        )
    )
    for index, row in enumerate(output, start=1):
        row["rank"] = index
    return output


def annotate_rows(
    rows: list[dict[str, object]],
    entries: list[dict[str, object]],
    best_low: dict[str, object],
) -> list[dict[str, object]]:
    context_family = str(best_low.get("context_family", ""))
    predictions = loo_predictions(entries, context_family)
    output: list[dict[str, object]] = []
    for row in rows:
        prediction = predictions.get(str(row.get("rank", "")), "")
        annotated = dict(row)
        annotated.update(
            {
                "best_template_context": context_family,
                "best_template_prediction": prediction,
                "best_template_verdict": (
                    "unknown"
                    if not prediction
                    else "correct"
                    if prediction == row.get("target_low")
                    else "false"
                ),
            }
        )
        output.append(annotated)
    return output


def build_summary(
    rows: list[dict[str, object]],
    entries: list[dict[str, object]],
    candidates: list[dict[str, object]],
) -> dict[str, object]:
    best_low = best_candidate(candidates, "low")
    best_low_bucket = best_candidate(candidates, "low_bucket")
    best_low_false_free = best_false_free_candidate(candidates, "low")
    return {
        "scope": "total",
        "candidate_mode": "row_template_low_loo",
        "slots": len(rows),
        "slot_rows": len({row.get("row_id", "") for row in rows}),
        "entry_slots": len(entries),
        "context_families": len(context_functions()),
        "candidate_rows": len(candidates),
        "best_low_context": best_low.get("context_family", ""),
        "best_low_correct_slots": best_low.get("loo_correct_slots", 0),
        "best_low_false_slots": best_low.get("loo_false_slots", 0),
        "best_low_precision": best_low.get("loo_precision", "0.000000"),
        "best_low_coverage": best_low.get("loo_coverage", "0.000000"),
        "best_low_bucket_context": best_low_bucket.get("context_family", ""),
        "best_low_bucket_correct_slots": best_low_bucket.get("loo_correct_slots", 0),
        "best_low_bucket_false_slots": best_low_bucket.get("loo_false_slots", 0),
        "best_low_bucket_precision": best_low_bucket.get("loo_precision", "0.000000"),
        "best_low_bucket_coverage": best_low_bucket.get("loo_coverage", "0.000000"),
        "best_low_false_free_context": best_low_false_free.get("context_family", ""),
        "best_low_false_free_slots": best_low_false_free.get("loo_correct_slots", 0),
        "promotion_candidate_bytes": 0,
        "promotion_ready_bytes": 0,
        "issue_rows": 0,
    }


def build(
    slot_rows: list[dict[str, str]],
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    rows, entries = build_entries(slot_rows)
    candidates = evaluate_candidates(entries)
    summary = build_summary(rows, entries, candidates)
    rows = annotate_rows(rows, entries, best_candidate(candidates, "low"))
    contexts = build_context_rows(entries, candidates)
    return summary, rows, candidates, contexts


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
    candidates: list[dict[str, object]],
    contexts: list[dict[str, object]],
    title: str,
) -> str:
    data_json = json.dumps(
        {"summary": summary, "slots": rows, "candidates": candidates, "contexts": contexts},
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
  <div class="box"><div class="num">{summary['best_low_correct_slots']}/{summary['best_low_false_slots']}</div><div class="muted">best low correct/false</div></div>
  <div class="box"><div class="num">{summary['best_low_bucket_correct_slots']}/{summary['best_low_bucket_false_slots']}</div><div class="muted">best bucket correct/false</div></div>
  <div class="box"><div class="num">{summary['best_low_false_free_slots']}</div><div class="muted">best false-free low slots</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Slots</h2>{render_table(rows, SLOT_FIELDNAMES)}</div>
<div class="panel"><h2>Candidates</h2>{render_table(candidates, CANDIDATE_FIELDNAMES)}</div>
<div class="panel"><h2>Contexts</h2>{render_table(contexts, CONTEXT_FIELDNAMES)}</div>
<script type="application/json" id="gradient-sequence-high-safe-row-template-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe row-template low grammar for high-safe gradient residuals.")
    parser.add_argument("--slots", type=Path, default=DEFAULT_SLOTS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Gradient Sequence High-Safe Row Template Probe",
    )
    args = parser.parse_args()

    summary, rows, candidates, contexts = build(read_csv(args.slots))
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "slots.csv", SLOT_FIELDNAMES, rows)
    write_csv(args.output / "candidates.csv", CANDIDATE_FIELDNAMES, candidates)
    write_csv(args.output / "contexts.csv", CONTEXT_FIELDNAMES, contexts)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, rows, candidates, contexts, args.title))

    print(f"Slots: {summary['slots']}")
    print(
        "Best row-template low: "
        f"{summary['best_low_context']} = "
        f"{summary['best_low_correct_slots']} correct / {summary['best_low_false_slots']} false"
    )
    print(
        "Best row-template bucket: "
        f"{summary['best_low_bucket_context']} = "
        f"{summary['best_low_bucket_correct_slots']} correct / {summary['best_low_bucket_false_slots']} false"
    )
    print(f"Best false-free low slots: {summary['best_low_false_free_slots']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
