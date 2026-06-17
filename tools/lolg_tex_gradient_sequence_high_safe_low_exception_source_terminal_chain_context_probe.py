#!/usr/bin/env python3
"""Probe direct chain contexts for source-terminal replay candidates."""

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
DEFAULT_TERMINALS = Path("output/tex_gradient_sequence_high_safe_low_exception_source_terminal/terminals.csv")
DEFAULT_REVIEW_CHAINS = Path("output/tex_gradient_sequence_high_safe_low_exception_source_terminal_review/chains.csv")
DEFAULT_OUTPUT = Path("output/tex_gradient_sequence_high_safe_low_exception_source_terminal_chain_context")

ROOT_FEATURES = [
    "frontier_id",
    "start",
    "relative_offset",
    "rel_mod4",
    "rel_mod8",
    "rel_mod16",
    "seq_index",
    "target_mod32",
    "target_mod64",
    "target_x_mod32",
    "target_y_mod8",
    "control_low",
    "control_class",
    "prefix_low",
    "fragment_low",
    "window_head_byte",
    "window_tail_byte",
    "gradient_class",
    "shape_len_key",
    "shape_start_key",
    "start_mod32",
    "length_mod16",
]

EDGE_FEATURES = [
    "source_slot_frontier_id",
    "source_slot_start",
    "source_actual_mod32",
    "source_target_delta_mod32",
    "relative_offset",
    "rel_mod4",
    "rel_mod8",
    "seq_index",
    "target_mod32",
    "control_low",
    "prefix_low",
    "fragment_low",
    "window_head_byte",
    "window_tail_byte",
    "gradient_class",
]

FEATURES = [
    "chain_length",
    "path_frontiers",
    "path_starts",
    "terminal_context",
    "terminal_prediction",
    "terminal_source_low",
    "terminal_target_mod32",
    *(f"root_{field}" for field in ROOT_FEATURES),
    *(f"edge1_{field}" for field in EDGE_FEATURES),
    *(f"edge2_{field}" for field in EDGE_FEATURES),
]

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "chain_rows",
    "features",
    "feature_sets",
    "candidate_rows",
    "best_context",
    "best_correct_chains",
    "best_false_chains",
    "best_unknown_chains",
    "best_precision",
    "best_coverage",
    "best_false_free_context",
    "best_false_free_chains",
    "best_false_free_unknown_chains",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

CANDIDATE_FIELDNAMES = [
    "rank",
    "target_kind",
    "context_family",
    "feature_count",
    "contexts",
    "chain_rows",
    "loo_correct_chains",
    "loo_false_chains",
    "loo_unknown_chains",
    "loo_precision",
    "loo_coverage",
    "predicted_lows",
    "verdict",
    "sample_context",
    "sample_prediction",
]

CHAIN_FIELDNAMES = [
    "rank",
    "root_slot_rank",
    "terminal_slot_rank",
    "chain_length",
    "path",
    "target_low",
    "terminal_context",
    "terminal_prediction",
    "chain_context",
    "chain_prediction",
    "chain_verdict",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def source_actual_mod32(row: dict[str, str]) -> str:
    value = int_value(row, "source_actual_offset", -1)
    return str(value % 32) if value >= 0 else ""


def enrich_edge(row: dict[str, str]) -> dict[str, str]:
    enriched = dict(row)
    enriched["source_actual_mod32"] = source_actual_mod32(row)
    return enriched


def build_chain_inputs(
    slot_rows: list[dict[str, str]],
    terminal_rows: list[dict[str, str]],
    review_chains: list[dict[str, str]],
) -> list[dict[str, str]]:
    slots_by_rank = {row["rank"]: enrich_edge(row) for row in slot_rows}
    terminals_by_rank = {row["terminal_slot_rank"]: row for row in terminal_rows}
    rows: list[dict[str, str]] = []
    for chain in review_chains:
        path = [rank for rank in chain.get("path", "").split("->") if rank]
        if not path:
            continue
        root = slots_by_rank.get(chain.get("root_slot_rank", ""), {})
        terminal = terminals_by_rank.get(chain.get("terminal_slot_rank", ""), {})
        edge1 = slots_by_rank.get(path[0], {})
        edge2 = slots_by_rank.get(path[1], {}) if len(path) > 2 else {}
        row = {
            "row_id": root.get("row_id", ""),
            "root_slot_rank": chain.get("root_slot_rank", ""),
            "terminal_slot_rank": chain.get("terminal_slot_rank", ""),
            "chain_length": chain.get("chain_length", ""),
            "path": chain.get("path", ""),
            "target_low": chain.get("root_target_low", ""),
            "terminal_context": terminal.get("terminal_context", ""),
            "terminal_prediction": terminal.get("terminal_prediction", ""),
            "terminal_source_low": terminal.get("source_low_resolved", ""),
            "terminal_target_mod32": terminal.get("target_mod32", ""),
            "path_frontiers": "->".join(slots_by_rank.get(rank, {}).get("frontier_id", "") for rank in path),
            "path_starts": "->".join(slots_by_rank.get(rank, {}).get("start", "") for rank in path),
        }
        for field in ROOT_FEATURES:
            row[f"root_{field}"] = root.get(field, "")
        for field in EDGE_FEATURES:
            row[f"edge1_{field}"] = edge1.get(field, "")
            row[f"edge2_{field}"] = edge2.get(field, "")
        rows.append(row)
    return rows


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

    predicted_lows: Counter[str] = Counter()
    for context, group in grouped.items():
        prediction = strict_prediction(all_counts[context])
        if prediction:
            predicted_lows[prediction] += len(group)

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
        verdict = "no_chain_signal"
    elif false == 0:
        verdict = "false_free_chain_context_review"
    else:
        verdict = "chain_context_reject"
    return {
        "rank": 0,
        "target_kind": "root_low",
        "context_family": "+".join(fields),
        "feature_count": len(fields),
        "contexts": len(grouped),
        "chain_rows": len(rows),
        "loo_correct_chains": correct,
        "loo_false_chains": false,
        "loo_unknown_chains": unknown,
        "loo_precision": ratio(correct, predicted),
        "loo_coverage": ratio(predicted, len(rows)),
        "predicted_lows": "|".join(f"{low}:{count}" for low, count in predicted_lows.most_common()),
        "verdict": verdict,
        "sample_context": sample_context,
        "sample_prediction": sample_prediction,
    }


def evaluate_candidates(rows: list[dict[str, str]], max_features: int) -> list[dict[str, object]]:
    candidates = [evaluate_candidate(rows, fields) for fields in feature_sets(max_features)]
    candidates.sort(
        key=lambda row: (
            -int_value(row, "loo_correct_chains"),
            int_value(row, "loo_false_chains"),
            int_value(row, "loo_unknown_chains"),
            int_value(row, "feature_count"),
            str(row.get("context_family", "")),
        )
    )
    for index, row in enumerate(candidates, start=1):
        row["rank"] = index
    return candidates


def best_false_free(candidates: list[dict[str, object]]) -> dict[str, object]:
    output = [
        row
        for row in candidates
        if int_value(row, "loo_correct_chains") > 0
        and int_value(row, "loo_false_chains") == 0
    ]
    return max(
        output,
        key=lambda row: (
            int_value(row, "loo_correct_chains"),
            -int_value(row, "loo_unknown_chains"),
            -int_value(row, "feature_count"),
            str(row.get("context_family", "")),
        ),
        default={},
    )


def chain_predictions(rows: list[dict[str, str]], context_family: str) -> dict[str, str]:
    if not context_family:
        return {}
    fields = tuple(context_family.split("+"))
    all_counts: dict[tuple[str, ...], Counter[str]] = defaultdict(Counter)
    row_counts: dict[tuple[str, tuple[str, ...]], Counter[str]] = defaultdict(Counter)
    for row in rows:
        context = context_for(row, fields)
        all_counts[context][row.get("target_low", "")] += 1
        row_counts[(row.get("row_id", ""), context)][row.get("target_low", "")] += 1

    output: dict[str, str] = {}
    for row in rows:
        context = context_for(row, fields)
        train_counts = all_counts[context].copy()
        train_counts.subtract(row_counts[(row.get("row_id", ""), context)])
        train_counts += Counter()
        prediction = strict_prediction(train_counts)
        if prediction:
            output[row.get("root_slot_rank", "")] = prediction
    return output


def annotate_chains(rows: list[dict[str, str]], context_family: str) -> list[dict[str, object]]:
    fields = tuple(context_family.split("+")) if context_family else ()
    predictions = chain_predictions(rows, context_family)
    output: list[dict[str, object]] = []
    for row in rows:
        prediction = predictions.get(row.get("root_slot_rank", ""), "")
        verdict = "unknown"
        if prediction:
            verdict = "correct" if prediction == row.get("target_low", "") else "false"
        output.append(
            {
                "rank": len(output) + 1,
                "root_slot_rank": row.get("root_slot_rank", ""),
                "terminal_slot_rank": row.get("terminal_slot_rank", ""),
                "chain_length": row.get("chain_length", ""),
                "path": row.get("path", ""),
                "target_low": row.get("target_low", ""),
                "terminal_context": row.get("terminal_context", ""),
                "terminal_prediction": row.get("terminal_prediction", ""),
                "chain_context": "|".join(context_for(row, fields)) if fields else "",
                "chain_prediction": prediction,
                "chain_verdict": verdict,
            }
        )
    return output


def build(
    slot_rows: list[dict[str, str]],
    terminal_rows: list[dict[str, str]],
    review_chains: list[dict[str, str]],
    max_features: int,
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    rows = build_chain_inputs(slot_rows, terminal_rows, review_chains)
    candidates = evaluate_candidates(rows, max_features)
    best = candidates[0] if candidates else {}
    false_free = best_false_free(candidates)
    selected_context = str(false_free.get("context_family") or best.get("context_family", ""))
    chains = annotate_chains(rows, selected_context)
    false_free_chains = int_value(false_free, "loo_correct_chains")
    summary = {
        "scope": "total",
        "candidate_mode": "high_safe_low_exception_source_terminal_chain_context",
        "chain_rows": len(rows),
        "features": len(FEATURES),
        "feature_sets": len(feature_sets(max_features)),
        "candidate_rows": len(candidates),
        "best_context": best.get("context_family", ""),
        "best_correct_chains": best.get("loo_correct_chains", 0),
        "best_false_chains": best.get("loo_false_chains", 0),
        "best_unknown_chains": best.get("loo_unknown_chains", 0),
        "best_precision": best.get("loo_precision", "0.000000"),
        "best_coverage": best.get("loo_coverage", "0.000000"),
        "best_false_free_context": false_free.get("context_family", ""),
        "best_false_free_chains": false_free_chains,
        "best_false_free_unknown_chains": false_free.get("loo_unknown_chains", 0),
        "promotion_candidate_bytes": false_free_chains,
        "promotion_ready_bytes": 0,
        "issue_rows": 0,
    }
    return summary, candidates, chains


def render_table(rows: list[dict[str, object]], fields: list[str], limit: int = 220) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, object],
    candidates: list[dict[str, object]],
    chains: list[dict[str, object]],
    title: str,
) -> str:
    data_json = json.dumps({"summary": summary, "candidates": candidates, "chains": chains}, indent=2, sort_keys=True)
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body {{ margin: 2rem; background: #101214; color: #edf5f4; font: 14px/1.45 system-ui, sans-serif; }}
table {{ border-collapse: collapse; width: 100%; min-width: 1900px; }}
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
  <div class="box"><div class="num">{summary['chain_rows']}</div><div class="muted">chain rows</div></div>
  <div class="box"><div class="num">{summary['best_correct_chains']}/{summary['best_false_chains']}</div><div class="muted">best correct/false</div></div>
  <div class="box"><div class="num">{summary['best_false_free_chains']}</div><div class="muted">false-free chains</div></div>
  <div class="box"><div class="num">{summary['best_false_free_context']}</div><div class="muted">false-free context</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Selected chains</h2>{render_table(chains, CHAIN_FIELDNAMES)}</div>
<div class="panel"><h2>Candidates</h2>{render_table(candidates, CANDIDATE_FIELDNAMES)}</div>
<script type="application/json" id="gradient-sequence-high-safe-low-exception-source-terminal-chain-context-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe direct chain contexts for source-terminal low replay.")
    parser.add_argument("--slots", type=Path, default=DEFAULT_SLOTS)
    parser.add_argument("--terminals", type=Path, default=DEFAULT_TERMINALS)
    parser.add_argument("--review-chains", type=Path, default=DEFAULT_REVIEW_CHAINS)
    parser.add_argument("--max-features", type=int, default=3)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Gradient Sequence High-Safe Low Exception Source-Terminal Chain Context Probe",
    )
    args = parser.parse_args()

    summary, candidates, chains = build(
        read_csv(args.slots),
        read_csv(args.terminals),
        read_csv(args.review_chains),
        args.max_features,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "candidates.csv", CANDIDATE_FIELDNAMES, candidates)
    write_csv(args.output / "chains.csv", CHAIN_FIELDNAMES, chains)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, candidates, chains, args.title))

    print(f"Chain rows: {summary['chain_rows']}")
    print(
        "Best chain context: "
        f"{summary['best_context']} = "
        f"{summary['best_correct_chains']} correct / {summary['best_false_chains']} false"
    )
    print(
        "Best false-free chain context: "
        f"{summary['best_false_free_context']} = "
        f"{summary['best_false_free_chains']} chains"
    )
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
