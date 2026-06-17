#!/usr/bin/env python3
"""Probe external terminal contexts for high-safe source dependency chains."""

from __future__ import annotations

import argparse
import csv
import html
import itertools
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gradient_sequence_high_safe_low_exception_probe import strict_prediction
from lolg_tex_micro_mixed_value_payload_state_opcode_probe import int_value, ratio, write_csv


DEFAULT_SLOTS = Path("output/tex_gradient_sequence_high_safe_low_exception_source_dependency/slots.csv")
DEFAULT_TERMINALS = Path("output/tex_gradient_sequence_high_safe_low_exception_source_chain/terminals.csv")
DEFAULT_OUTPUT = Path("output/tex_gradient_sequence_high_safe_low_exception_source_terminal")

FEATURES = [
    "source_low_resolved",
    "source_availability",
    "source_actual_mod32",
    "source_target_delta_mod32",
    "frontier_id",
    "start",
    "rel_mod4",
    "rel_mod8",
    "seq_index",
    "target_mod32",
    "control_low",
    "prefix_low",
    "fragment_low",
    "window_head_byte",
    "window_tail_byte",
    "best_fixed_transition_source_low",
    "root_chains",
    "terminal_state",
    "low_bucket",
]

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "terminal_slots",
    "root_chains",
    "features",
    "feature_sets",
    "candidate_rows",
    "best_context",
    "best_correct_slots",
    "best_false_slots",
    "best_unknown_slots",
    "best_precision",
    "best_coverage",
    "best_false_free_context",
    "best_false_free_slots",
    "best_false_free_unknown_slots",
    "combined_false_free_slots",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

TERMINAL_FIELDNAMES = [
    "rank",
    "terminal_slot_rank",
    "frontier_id",
    "start",
    "target_offset",
    "target_low",
    "low_bucket",
    "root_chains",
    "source_availability",
    "source_location",
    "source_decoded_byte",
    "source_expected_byte",
    "source_low_resolved",
    "source_actual_offset",
    "source_actual_mod32",
    "source_target_delta_mod32",
    "rel_mod4",
    "rel_mod8",
    "seq_index",
    "target_mod32",
    "control_low",
    "prefix_low",
    "fragment_low",
    "terminal_state",
    "terminal_context",
    "terminal_prediction",
    "terminal_verdict",
]

CANDIDATE_FIELDNAMES = [
    "rank",
    "target_kind",
    "context_family",
    "feature_count",
    "contexts",
    "terminal_slots",
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


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def source_low(row: dict[str, str] | dict[str, object]) -> str:
    value = str(row.get("source_decoded_byte", "") or row.get("source_expected_byte", ""))
    return value[-1] if value else ""


def enrich_terminal_rows(
    dependency_slots: list[dict[str, str]],
    terminal_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    dependency_by_rank = {row["rank"]: row for row in dependency_slots}
    output: list[dict[str, str]] = []
    for terminal in terminal_rows:
        source = dependency_by_rank[str(terminal["terminal_slot_rank"])]
        row = {**source, **terminal}
        source_actual = int_value(row, "source_actual_offset")
        target_offset = int_value(row, "target_offset")
        row["source_low_resolved"] = source_low(row)
        row["source_actual_mod32"] = str(source_actual % 32)
        row["source_target_delta_mod32"] = str((target_offset - source_actual) % 32)
        row["terminal_state"] = f"{row.get('source_availability', '')}|{row.get('source_location', '')}"
        output.append(row)
    return output


def feature_sets(max_features: int) -> list[tuple[str, ...]]:
    output: list[tuple[str, ...]] = []
    for size in range(1, max_features + 1):
        output.extend(itertools.combinations(FEATURES, size))
    return output


def context_for(row: dict[str, str], fields: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(str(row.get(field, "")) for field in fields)


def evaluate_candidate(rows: list[dict[str, str]], fields: tuple[str, ...]) -> dict[str, object]:
    all_counts: dict[tuple[str, ...], Counter[str]] = defaultdict(Counter)
    row_counts: dict[tuple[str, tuple[str, ...]], Counter[str]] = defaultdict(Counter)
    grouped: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        context = context_for(row, fields)
        low = row.get("target_low", "")
        all_counts[context][low] += 1
        row_counts[(row.get("row_id", ""), context)][low] += 1
        grouped[context].append(row)

    predicted_values: Counter[str] = Counter()
    for context, group in grouped.items():
        prediction = strict_prediction(all_counts[context])
        if prediction:
            predicted_values[prediction] += len(group)

    correct = 0
    false = 0
    unknown = 0
    sample_context = ""
    sample_prediction = ""
    for row in rows:
        context = context_for(row, fields)
        train_counts = all_counts[context].copy()
        train_counts.subtract(row_counts[(row.get("row_id", ""), context)])
        train_counts += Counter()
        prediction = strict_prediction(train_counts)
        if not prediction:
            unknown += 1
            continue
        if not sample_context:
            sample_context = "|".join(context)
            sample_prediction = prediction
        if prediction == row.get("target_low", ""):
            correct += 1
        else:
            false += 1
    predicted = correct + false
    if predicted == 0:
        verdict = "no_terminal_signal"
    elif false == 0:
        verdict = "false_free_terminal_review"
    else:
        verdict = "terminal_context_reject"
    return {
        "rank": 0,
        "target_kind": "terminal_low",
        "context_family": "+".join(fields),
        "feature_count": len(fields),
        "contexts": len(grouped),
        "terminal_slots": len(rows),
        "loo_correct_slots": correct,
        "loo_false_slots": false,
        "loo_unknown_slots": unknown,
        "loo_precision": ratio(correct, predicted),
        "loo_coverage": ratio(predicted, len(rows)),
        "predicted_values": "|".join(f"{value}:{count}" for value, count in predicted_values.most_common()),
        "verdict": verdict,
        "sample_context": sample_context,
        "sample_prediction": sample_prediction,
    }


def evaluate_candidates(rows: list[dict[str, str]], max_features: int) -> list[dict[str, object]]:
    candidates = [evaluate_candidate(rows, fields) for fields in feature_sets(max_features)]
    candidates.sort(
        key=lambda row: (
            -int_value(row, "loo_correct_slots"),
            int_value(row, "loo_false_slots"),
            int_value(row, "loo_unknown_slots"),
            str(row["context_family"]),
        )
    )
    for index, row in enumerate(candidates, start=1):
        row["rank"] = index
    return candidates


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
            -int_value(row, "feature_count"),
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
            -int_value(row, "feature_count"),
            str(row.get("context_family", "")),
        ),
        default={},
    )


def terminal_predictions(rows: list[dict[str, str]], context_family: str) -> dict[str, str]:
    if not context_family:
        return {}
    fields = tuple(context_family.split("+"))
    all_counts: dict[tuple[str, ...], Counter[str]] = defaultdict(Counter)
    row_counts: dict[tuple[str, tuple[str, ...]], Counter[str]] = defaultdict(Counter)
    row_by_rank: dict[str, dict[str, str]] = {}
    for row in rows:
        context = context_for(row, fields)
        low = row.get("target_low", "")
        all_counts[context][low] += 1
        row_counts[(row.get("row_id", ""), context)][low] += 1
        row_by_rank[str(row.get("terminal_slot_rank", ""))] = row

    predictions: dict[str, str] = {}
    for terminal_rank, row in row_by_rank.items():
        context = context_for(row, fields)
        train_counts = all_counts[context].copy()
        train_counts.subtract(row_counts[(row.get("row_id", ""), context)])
        train_counts += Counter()
        prediction = strict_prediction(train_counts)
        if prediction:
            predictions[terminal_rank] = prediction
    return predictions


def annotate_rows(
    rows: list[dict[str, str]],
    best_false_free: dict[str, object],
) -> list[dict[str, object]]:
    context_family = str(best_false_free.get("context_family", ""))
    predictions = terminal_predictions(rows, context_family)
    fields = tuple(context_family.split("+")) if context_family else ()
    output: list[dict[str, object]] = []
    for index, row in enumerate(rows, start=1):
        prediction = predictions.get(str(row.get("terminal_slot_rank", "")), "")
        if prediction:
            verdict = "correct" if prediction == row.get("target_low", "") else "false"
        else:
            verdict = "unknown"
        context = "|".join(context_for(row, fields)) if fields else ""
        output.append(
            {
                "rank": index,
                "terminal_slot_rank": row.get("terminal_slot_rank", ""),
                "frontier_id": row.get("frontier_id", ""),
                "start": row.get("start", ""),
                "target_offset": row.get("target_offset", ""),
                "target_low": row.get("target_low", ""),
                "low_bucket": row.get("low_bucket", ""),
                "root_chains": row.get("root_chains", ""),
                "source_availability": row.get("source_availability", ""),
                "source_location": row.get("source_location", ""),
                "source_decoded_byte": row.get("source_decoded_byte", ""),
                "source_expected_byte": row.get("source_expected_byte", ""),
                "source_low_resolved": row.get("source_low_resolved", ""),
                "source_actual_offset": row.get("source_actual_offset", ""),
                "source_actual_mod32": row.get("source_actual_mod32", ""),
                "source_target_delta_mod32": row.get("source_target_delta_mod32", ""),
                "rel_mod4": row.get("rel_mod4", ""),
                "rel_mod8": row.get("rel_mod8", ""),
                "seq_index": row.get("seq_index", ""),
                "target_mod32": row.get("target_mod32", ""),
                "control_low": row.get("control_low", ""),
                "prefix_low": row.get("prefix_low", ""),
                "fragment_low": row.get("fragment_low", ""),
                "terminal_state": row.get("terminal_state", ""),
                "terminal_context": context,
                "terminal_prediction": prediction,
                "terminal_verdict": verdict,
            }
        )
    return output


def build(
    dependency_slots: list[dict[str, str]],
    terminal_rows: list[dict[str, str]],
    max_features: int,
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    rows = enrich_terminal_rows(dependency_slots, terminal_rows)
    candidates = evaluate_candidates(rows, max_features)
    best = best_candidate(candidates)
    false_free = best_false_free_candidate(candidates)
    annotated_rows = annotate_rows(rows, false_free)
    false_free_slots = int_value(false_free, "loo_correct_slots")
    summary = {
        "scope": "total",
        "candidate_mode": "high_safe_low_exception_source_terminal",
        "terminal_slots": len(rows),
        "root_chains": sum(int_value(row, "root_chains") for row in rows),
        "features": len(FEATURES),
        "feature_sets": len(feature_sets(max_features)),
        "candidate_rows": len(candidates),
        "best_context": best.get("context_family", ""),
        "best_correct_slots": best.get("loo_correct_slots", 0),
        "best_false_slots": best.get("loo_false_slots", 0),
        "best_unknown_slots": best.get("loo_unknown_slots", 0),
        "best_precision": best.get("loo_precision", "0.000000"),
        "best_coverage": best.get("loo_coverage", "0.000000"),
        "best_false_free_context": false_free.get("context_family", ""),
        "best_false_free_slots": false_free_slots,
        "best_false_free_unknown_slots": false_free.get("loo_unknown_slots", 0),
        "combined_false_free_slots": false_free_slots,
        "promotion_candidate_bytes": false_free_slots,
        "promotion_ready_bytes": 0,
        "issue_rows": 0,
    }
    return summary, annotated_rows, candidates


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
    title: str,
) -> str:
    data_json = json.dumps({"summary": summary, "terminals": rows, "candidates": candidates}, indent=2, sort_keys=True)
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
  <div class="box"><div class="num">{summary['terminal_slots']}</div><div class="muted">terminal slots</div></div>
  <div class="box"><div class="num">{summary['best_correct_slots']}/{summary['best_false_slots']}</div><div class="muted">best correct/false</div></div>
  <div class="box"><div class="num">{summary['best_false_free_slots']}</div><div class="muted">best false-free slots</div></div>
  <div class="box"><div class="num">{summary['best_false_free_context']}</div><div class="muted">best false-free context</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Terminals</h2>{render_table(rows, TERMINAL_FIELDNAMES)}</div>
<div class="panel"><h2>Candidates</h2>{render_table(candidates, CANDIDATE_FIELDNAMES)}</div>
<script type="application/json" id="gradient-sequence-high-safe-low-exception-source-terminal-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe terminal source contexts for low exceptions.")
    parser.add_argument("--slots", type=Path, default=DEFAULT_SLOTS)
    parser.add_argument("--terminals", type=Path, default=DEFAULT_TERMINALS)
    parser.add_argument("--max-features", type=int, default=3)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Gradient Sequence High-Safe Low Exception Source-Terminal Probe",
    )
    args = parser.parse_args()

    summary, rows, candidates = build(read_csv(args.slots), read_csv(args.terminals), args.max_features)
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "terminals.csv", TERMINAL_FIELDNAMES, rows)
    write_csv(args.output / "candidates.csv", CANDIDATE_FIELDNAMES, candidates)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, rows, candidates, args.title))

    print(f"Terminal slots: {summary['terminal_slots']}")
    print(
        "Best terminal context: "
        f"{summary['best_context']} = "
        f"{summary['best_correct_slots']} correct / {summary['best_false_slots']} false"
    )
    print(
        "Best false-free terminal context: "
        f"{summary['best_false_free_context']} = "
        f"{summary['best_false_free_slots']} slots"
    )
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
