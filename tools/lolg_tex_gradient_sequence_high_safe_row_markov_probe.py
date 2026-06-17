#!/usr/bin/env python3
"""Probe row-local Markov low grammar for high-safe gradient residual slots."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gradient_sequence_high_safe_row_transition_probe import (
    SLOT_FIELDNAMES as ROW_TRANSITION_SLOT_FIELDNAMES,
)
from lolg_tex_micro_mixed_value_payload_state_opcode_probe import (
    evaluate_candidate,
    int_value,
    ratio,
    target_value,
    write_csv,
)


DEFAULT_SLOTS = Path("output/tex_gradient_sequence_high_safe_row_transition/slots.csv")
DEFAULT_OUTPUT = Path("output/tex_gradient_sequence_high_safe_row_markov")

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
    "best_delta_context",
    "best_delta_correct_slots",
    "best_delta_false_slots",
    "best_delta_precision",
    "best_delta_coverage",
    "best_step_context",
    "best_step_correct_slots",
    "best_step_false_slots",
    "best_step_precision",
    "best_step_coverage",
    "best_low_false_free_context",
    "best_low_false_free_slots",
    "best_delta_false_free_context",
    "best_delta_false_free_slots",
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
    *ROW_TRANSITION_SLOT_FIELDNAMES,
    "seq_index",
    "prev_low1",
    "prev_low2",
    "prev_pair",
    "prev_delta",
    "prevprev_delta",
    "target_delta",
    "target_step",
    "best_low_markov_context",
    "best_low_markov_prediction",
    "best_low_markov_verdict",
    "best_delta_markov_context",
    "best_delta_markov_prediction",
    "best_delta_markov_low",
    "best_delta_markov_verdict",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def parse_low(row: dict[str, object]) -> int | None:
    try:
        return int(str(row.get("target_low", "")), 16)
    except ValueError:
        return None


def low_hex(value: int | None, fallback: str = "") -> str:
    return fallback if value is None else f"{value:x}"


def delta_hex(left: int | None, right: int | None, fallback: str = "") -> str:
    if left is None or right is None:
        return fallback
    return f"{(right - left) & 0x0F:x}"


def step_token(delta: str) -> str:
    if delta == "":
        return ""
    if delta == "0":
        return "0"
    if delta == "1":
        return "+1"
    if delta == "f":
        return "-1"
    return "other"


def context_functions():
    return {
        "prev_low_pos16": lambda row: (row["prev_low1"], row["payload_pos16"]),
        "prev_low_rel8": lambda row: (row["prev_low1"], row["rel_mod8"]),
        "prev_low_target_x": lambda row: (row["prev_low1"], row["target_x_mod32"]),
        "prev_low_quarter": lambda row: (row["prev_low1"], row["row_quarter"]),
        "prev_low_third": lambda row: (row["prev_low1"], row["row_third"]),
        "prev_low_offset_bucket": lambda row: (row["prev_low1"], row["offset_delta_bucket"]),
        "prev_pair_pos16": lambda row: (row["prev_pair"], row["payload_pos16"]),
        "prev_pair_rel8": lambda row: (row["prev_pair"], row["rel_mod8"]),
        "prev_pair_target_x": lambda row: (row["prev_pair"], row["target_x_mod32"]),
        "prev_delta_pos16": lambda row: (row["prevprev_delta"], row["payload_pos16"]),
        "prev_delta_rel16": lambda row: (row["prevprev_delta"], row["rel_mod16"]),
        "prev_delta_target_x": lambda row: (row["prevprev_delta"], row["target_x_mod32"]),
        "prev_delta_seq": lambda row: (row["prevprev_delta"], row["seq_index"]),
        "prev_delta_seq_gradient": lambda row: (row["prevprev_delta"], row["seq_index"], row["gradient_class"]),
        "prev_delta_quarter_gradient": lambda row: (
            row["prevprev_delta"],
            row["row_quarter"],
            row["gradient_class"],
        ),
        "prev_low_target_x_gradient": lambda row: (
            row["prev_low1"],
            row["target_x_mod32"],
            row["gradient_class"],
        ),
        "prev_low_target_x_third_gradient": lambda row: (
            row["prev_low1"],
            row["target_x_mod32"],
            row["row_third"],
            row["gradient_class"],
        ),
        "prev_low_quarter_third_offset": lambda row: (
            row["prev_low1"],
            row["row_quarter"],
            row["row_third"],
            row["offset_delta_bucket"],
        ),
        "prev_pair_seq": lambda row: (row["prev_pair"], row["seq_index"]),
        "prev_pair_seq_gradient": lambda row: (row["prev_pair"], row["seq_index"], row["gradient_class"]),
        "row_state_pos": lambda row: (
            row["op_index"],
            row["target_x_mod32"],
            row["row_quarter"],
            row["row_third"],
        ),
        "source_markov_mix": lambda row: (
            row["prev_low1"],
            row["source_low"],
            row["offset_delta_bucket"],
            row["target_x_mod32"],
        ),
        "transition_markov_mix": lambda row: (
            row["prev_low1"],
            row["best_fixed_transition_predicted_low"],
            row["target_x_mod32"],
        ),
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
    for target_kind in ("low", "delta", "step"):
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


def loo_predictions(
    entries: list[dict[str, object]],
    target_kind: str,
    context_family: str,
) -> dict[str, str]:
    if not context_family:
        return {}
    context_func = context_functions()[context_family]
    all_counts: dict[tuple[object, ...], Counter[str]] = defaultdict(Counter)
    row_counts: dict[tuple[int, tuple[object, ...]], Counter[str]] = defaultdict(Counter)
    entry_by_slot: dict[str, dict[str, object]] = {}
    for entry in entries:
        if not str(entry.get(target_kind, "")):
            continue
        context = context_func(entry)
        all_counts[context][target_value(entry, target_kind)] += 1
        row_counts[(int(entry["row_index"]), context)][target_value(entry, target_kind)] += 1
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
        lows = [parse_low(row) for row in members]
        length = int_value(members[0], "end") - int_value(members[0], "start")
        for index, slot in enumerate(members):
            low = lows[index]
            prev1 = lows[index - 1] if index > 0 else None
            prev2 = lows[index - 2] if index > 1 else None
            prev_delta = delta_hex(prev2, prev1)
            target_delta = delta_hex(prev1, low)
            row = {
                **slot,
                "seq_index": index,
                "prev_low1": low_hex(prev1, "START"),
                "prev_low2": low_hex(prev2, "START"),
                "prev_pair": "START" if prev1 is None or prev2 is None else f"{prev2:x}{prev1:x}",
                "prev_delta": prev_delta or "START",
                "prevprev_delta": prev_delta or "START",
                "target_delta": target_delta,
                "target_step": step_token(target_delta),
            }
            rows.append(row)
            entries.append(
                {
                    **row,
                    "row_index": row_indexes[row_id],
                    "slot_rank": slot.get("rank", ""),
                    "low": low_hex(low),
                    "delta": target_delta,
                    "step": step_token(target_delta),
                    "payload_pos16": str((index * 16) // len(members)) if members else "NA",
                    "row_length": length,
                }
            )
    return rows, entries


def build_context_rows(
    entries: list[dict[str, object]],
    candidates: list[dict[str, object]],
) -> list[dict[str, object]]:
    families_by_target: dict[str, set[str]] = defaultdict(set)
    for target_kind in ("low", "delta", "step"):
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
        for row in ranked[:4]:
            families_by_target[target_kind].add(str(row.get("context_family", "")))

    output: list[dict[str, object]] = []
    for target_kind, families in families_by_target.items():
        for family in sorted(families):
            context_func = context_functions()[family]
            grouped: dict[tuple[object, ...], list[dict[str, object]]] = defaultdict(list)
            for entry in entries:
                if str(entry.get(target_kind, "")):
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
    best_delta: dict[str, object],
) -> list[dict[str, object]]:
    low_context = str(best_low.get("context_family", ""))
    delta_context = str(best_delta.get("context_family", ""))
    low_predictions = loo_predictions(entries, "low", low_context)
    delta_predictions = loo_predictions(entries, "delta", delta_context)
    output: list[dict[str, object]] = []
    for row in rows:
        slot_rank = str(row.get("rank", ""))
        low_prediction = low_predictions.get(slot_rank, "")
        delta_prediction = delta_predictions.get(slot_rank, "")
        prev1 = None if row.get("prev_low1") == "START" else int(str(row.get("prev_low1", "")), 16)
        delta_low = ""
        if prev1 is not None and delta_prediction:
            delta_low = f"{(prev1 + int(delta_prediction, 16)) & 0x0F:x}"
        annotated = dict(row)
        annotated.update(
            {
                "best_low_markov_context": low_context,
                "best_low_markov_prediction": low_prediction,
                "best_low_markov_verdict": (
                    "unknown"
                    if not low_prediction
                    else "correct"
                    if low_prediction == row.get("target_low")
                    else "false"
                ),
                "best_delta_markov_context": delta_context,
                "best_delta_markov_prediction": delta_prediction,
                "best_delta_markov_low": delta_low,
                "best_delta_markov_verdict": (
                    "unknown"
                    if not delta_low
                    else "correct"
                    if delta_low == row.get("target_low")
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
    best_delta = best_candidate(candidates, "delta")
    best_step = best_candidate(candidates, "step")
    best_low_false_free = best_false_free_candidate(candidates, "low")
    best_delta_false_free = best_false_free_candidate(candidates, "delta")
    return {
        "scope": "total",
        "candidate_mode": "row_local_low_markov_loo",
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
        "best_delta_context": best_delta.get("context_family", ""),
        "best_delta_correct_slots": best_delta.get("loo_correct_slots", 0),
        "best_delta_false_slots": best_delta.get("loo_false_slots", 0),
        "best_delta_precision": best_delta.get("loo_precision", "0.000000"),
        "best_delta_coverage": best_delta.get("loo_coverage", "0.000000"),
        "best_step_context": best_step.get("context_family", ""),
        "best_step_correct_slots": best_step.get("loo_correct_slots", 0),
        "best_step_false_slots": best_step.get("loo_false_slots", 0),
        "best_step_precision": best_step.get("loo_precision", "0.000000"),
        "best_step_coverage": best_step.get("loo_coverage", "0.000000"),
        "best_low_false_free_context": best_low_false_free.get("context_family", ""),
        "best_low_false_free_slots": best_low_false_free.get("loo_correct_slots", 0),
        "best_delta_false_free_context": best_delta_false_free.get("context_family", ""),
        "best_delta_false_free_slots": best_delta_false_free.get("loo_correct_slots", 0),
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
    rows = annotate_rows(rows, entries, best_candidate(candidates, "low"), best_candidate(candidates, "delta"))
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
  <div class="box"><div class="num">{summary['best_delta_correct_slots']}/{summary['best_delta_false_slots']}</div><div class="muted">best delta correct/false</div></div>
  <div class="box"><div class="num">{summary['best_step_correct_slots']}/{summary['best_step_false_slots']}</div><div class="muted">best step correct/false</div></div>
  <div class="box"><div class="num">{summary['best_delta_false_free_slots']}</div><div class="muted">best delta false-free slots</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Slots</h2>{render_table(rows, SLOT_FIELDNAMES)}</div>
<div class="panel"><h2>Candidates</h2>{render_table(candidates, CANDIDATE_FIELDNAMES)}</div>
<div class="panel"><h2>Contexts</h2>{render_table(contexts, CONTEXT_FIELDNAMES)}</div>
<script type="application/json" id="gradient-sequence-high-safe-row-markov-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe row-local Markov low grammar for high-safe gradient residuals.")
    parser.add_argument("--slots", type=Path, default=DEFAULT_SLOTS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Gradient Sequence High-Safe Row Markov Probe",
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
        "Best low Markov: "
        f"{summary['best_low_context']} = "
        f"{summary['best_low_correct_slots']} correct / {summary['best_low_false_slots']} false"
    )
    print(
        "Best delta Markov: "
        f"{summary['best_delta_context']} = "
        f"{summary['best_delta_correct_slots']} correct / {summary['best_delta_false_slots']} false"
    )
    print(f"Best delta false-free slots: {summary['best_delta_false_free_slots']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
