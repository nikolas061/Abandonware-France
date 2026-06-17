#!/usr/bin/env python3
"""Probe non-oracle delta contexts for source-terminal chain replay."""

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
DEFAULT_REVIEW_CHAINS = Path("output/tex_gradient_sequence_high_safe_low_exception_source_terminal_review/chains.csv")
DEFAULT_OUTPUT = Path("output/tex_gradient_sequence_high_safe_low_exception_source_terminal_delta")

FEATURES = [
    "source_availability",
    "frontier_id",
    "start",
    "source_slot_frontier_id",
    "source_slot_start",
    "relative_offset",
    "rel_mod4",
    "rel_mod8",
    "rel_mod16",
    "seq_index",
    "target_mod32",
    "target_mod64",
    "target_x_mod32",
    "target_y_mod8",
    "source_actual_mod32",
    "source_target_delta_mod32",
    "start_mod32",
    "length_mod16",
    "control_low",
    "control_class",
    "prefix_low",
    "fragment_low",
    "window_head_byte",
    "window_tail_byte",
    "gradient_class",
    "shape_len_key",
    "shape_start_key",
    "source_relative_offset",
    "source_rel_mod4",
    "source_rel_mod8",
    "source_rel_mod16",
    "source_seq_index",
    "source_target_mod32",
    "source_target_mod64",
    "source_target_x_mod32",
    "source_target_y_mod8",
    "source_control_low",
    "source_control_class",
    "source_prefix_low",
    "source_fragment_low",
    "source_window_head_byte",
    "source_window_tail_byte",
    "source_gradient_class",
    "source_shape_len_key",
    "source_shape_start_key",
    "source_start_mod32",
    "source_length_mod16",
]

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "edge_rows",
    "review_chains",
    "review_edges",
    "features",
    "feature_sets",
    "candidate_rows",
    "best_context",
    "best_edge_correct",
    "best_edge_false",
    "best_review_exact",
    "best_review_false",
    "best_review_unknown",
    "best_false_free_context",
    "best_false_free_edge_correct",
    "best_false_free_review_exact",
    "best_false_free_review_unknown",
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
    "edge_rows",
    "loo_correct_edges",
    "loo_false_edges",
    "loo_unknown_edges",
    "loo_precision",
    "loo_coverage",
    "review_chains",
    "review_root_exact",
    "review_root_false",
    "review_root_unknown",
    "review_root_precision",
    "predicted_deltas",
    "verdict",
    "sample_context",
    "sample_prediction",
]

CHAIN_FIELDNAMES = [
    "rank",
    "candidate_context",
    "root_slot_rank",
    "terminal_slot_rank",
    "chain_length",
    "path",
    "terminal_prediction",
    "root_target_low",
    "predicted_delta_path",
    "predicted_root_low",
    "chain_verdict",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def source_actual_mod32(row: dict[str, str]) -> str:
    value = int_value(row, "source_actual_offset", -1)
    return str(value % 32) if value >= 0 else ""


def enrich_edges(slot_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    slots_by_rank = {row["rank"]: row for row in slot_rows}
    source_feature_fields = [
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
    output: list[dict[str, str]] = []
    for row in slot_rows:
        if row.get("source_location") != "in_highsafe" or row.get("source_low_delta", "") == "":
            continue
        enriched = dict(row)
        source_slot = slots_by_rank.get(row.get("source_slot_rank", ""), {})
        for field in source_feature_fields:
            enriched[f"source_{field}"] = source_slot.get(field, "")
        enriched["source_actual_mod32"] = source_actual_mod32(row)
        output.append(enriched)
    return output


def feature_sets(max_features: int) -> list[tuple[str, ...]]:
    output: list[tuple[str, ...]] = []
    for size in range(1, max_features + 1):
        output.extend(itertools.combinations(FEATURES, size))
    return output


def context_for(row: dict[str, str], fields: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(str(row.get(field, "")) for field in fields)


def low_add(low: str, deltas: list[str]) -> str:
    if not low or any(not delta for delta in deltas):
        return ""
    return f"{(int(low, 16) + sum(int(delta) for delta in deltas)) & 0x0F:x}"


def train_counts(
    rows: list[dict[str, str]],
    fields: tuple[str, ...],
) -> tuple[dict[tuple[str, ...], Counter[str]], dict[tuple[str, tuple[str, ...]], Counter[str]]]:
    all_counts: dict[tuple[str, ...], Counter[str]] = defaultdict(Counter)
    row_counts: dict[tuple[str, tuple[str, ...]], Counter[str]] = defaultdict(Counter)
    for row in rows:
        context = context_for(row, fields)
        delta = row.get("source_low_delta", "")
        all_counts[context][delta] += 1
        row_counts[(row.get("row_id", ""), context)][delta] += 1
    return all_counts, row_counts


def loo_prediction(
    row: dict[str, str],
    fields: tuple[str, ...],
    all_counts: dict[tuple[str, ...], Counter[str]],
    row_counts: dict[tuple[str, tuple[str, ...]], Counter[str]],
) -> str:
    context = context_for(row, fields)
    counts = all_counts[context].copy()
    counts.subtract(row_counts[(row.get("row_id", ""), context)])
    counts += Counter()
    return strict_prediction(counts)


def review_edge_ranks(review_chains: list[dict[str, str]]) -> set[str]:
    ranks: set[str] = set()
    for chain in review_chains:
        path = [rank for rank in chain.get("path", "").split("->") if rank]
        ranks.update(path[:-1])
    return ranks


def evaluate_review_chains(
    review_chains: list[dict[str, str]],
    edges_by_rank: dict[str, dict[str, str]],
    fields: tuple[str, ...],
    all_counts: dict[tuple[str, ...], Counter[str]],
    row_counts: dict[tuple[str, tuple[str, ...]], Counter[str]],
) -> tuple[Counter[str], list[dict[str, object]]]:
    verdicts: Counter[str] = Counter()
    rows: list[dict[str, object]] = []
    for chain in review_chains:
        path = [rank for rank in chain.get("path", "").split("->") if rank]
        deltas: list[str] = []
        for rank in path[:-1]:
            edge = edges_by_rank.get(rank, {})
            prediction = loo_prediction(edge, fields, all_counts, row_counts) if edge else ""
            deltas.append(prediction or "")
        predicted_root = low_add(chain.get("terminal_prediction", ""), deltas)
        if not predicted_root:
            verdict = "unknown"
        elif predicted_root == chain.get("root_target_low", ""):
            verdict = "exact"
        else:
            verdict = "false"
        verdicts[verdict] += 1
        rows.append(
            {
                "rank": len(rows) + 1,
                "candidate_context": "+".join(fields),
                "root_slot_rank": chain.get("root_slot_rank", ""),
                "terminal_slot_rank": chain.get("terminal_slot_rank", ""),
                "chain_length": chain.get("chain_length", ""),
                "path": chain.get("path", ""),
                "terminal_prediction": chain.get("terminal_prediction", ""),
                "root_target_low": chain.get("root_target_low", ""),
                "predicted_delta_path": "+".join(deltas),
                "predicted_root_low": predicted_root,
                "chain_verdict": verdict,
            }
        )
    return verdicts, rows


def evaluate_candidate(
    rows: list[dict[str, str]],
    review_chains: list[dict[str, str]],
    edges_by_rank: dict[str, dict[str, str]],
    fields: tuple[str, ...],
) -> tuple[dict[str, object], list[dict[str, object]]]:
    all_counts, row_counts = train_counts(rows, fields)
    grouped = {context for context in all_counts}
    predicted_deltas: Counter[str] = Counter()
    for context, counts in all_counts.items():
        prediction = strict_prediction(counts)
        if prediction:
            predicted_deltas[prediction] += sum(counts.values())

    correct = 0
    false = 0
    unknown = 0
    sample_context = ""
    sample_prediction = ""
    for row in rows:
        prediction = loo_prediction(row, fields, all_counts, row_counts)
        if not prediction:
            unknown += 1
            continue
        if not sample_context:
            sample_context = "|".join(context_for(row, fields))
            sample_prediction = prediction
        if prediction == row.get("source_low_delta", ""):
            correct += 1
        else:
            false += 1

    review_verdicts, review_rows = evaluate_review_chains(
        review_chains,
        edges_by_rank,
        fields,
        all_counts,
        row_counts,
    )
    predicted = correct + false
    review_predicted = review_verdicts["exact"] + review_verdicts["false"]
    if review_verdicts["exact"] == 0:
        verdict = "no_delta_replay_signal"
    elif review_verdicts["false"] == 0 and false == 0:
        verdict = "false_free_delta_replay_review"
    elif review_verdicts["false"] == 0:
        verdict = "narrow_delta_replay_review"
    else:
        verdict = "delta_replay_reject"
    return (
        {
            "rank": 0,
            "target_kind": "source_low_delta",
            "context_family": "+".join(fields),
            "feature_count": len(fields),
            "contexts": len(grouped),
            "edge_rows": len(rows),
            "loo_correct_edges": correct,
            "loo_false_edges": false,
            "loo_unknown_edges": unknown,
            "loo_precision": ratio(correct, predicted),
            "loo_coverage": ratio(predicted, len(rows)),
            "review_chains": len(review_chains),
            "review_root_exact": review_verdicts["exact"],
            "review_root_false": review_verdicts["false"],
            "review_root_unknown": review_verdicts["unknown"],
            "review_root_precision": ratio(review_verdicts["exact"], review_predicted),
            "predicted_deltas": "|".join(f"{delta}:{count}" for delta, count in predicted_deltas.most_common()),
            "verdict": verdict,
            "sample_context": sample_context,
            "sample_prediction": sample_prediction,
        },
        review_rows,
    )


def evaluate_candidates(
    rows: list[dict[str, str]],
    review_chains: list[dict[str, str]],
    max_features: int,
) -> tuple[list[dict[str, object]], dict[str, list[dict[str, object]]]]:
    edges_by_rank = {row["rank"]: row for row in rows}
    candidates: list[dict[str, object]] = []
    review_rows_by_context: dict[str, list[dict[str, object]]] = {}
    for fields in feature_sets(max_features):
        candidate, review_rows = evaluate_candidate(rows, review_chains, edges_by_rank, fields)
        candidates.append(candidate)
        review_rows_by_context[str(candidate["context_family"])] = review_rows
    candidates.sort(
        key=lambda row: (
            -int_value(row, "review_root_exact"),
            int_value(row, "review_root_false"),
            int_value(row, "review_root_unknown"),
            int_value(row, "loo_false_edges"),
            -int_value(row, "loo_correct_edges"),
            int_value(row, "feature_count"),
            str(row.get("context_family", "")),
        )
    )
    for index, row in enumerate(candidates, start=1):
        row["rank"] = index
    return candidates, review_rows_by_context


def best_false_free(candidates: list[dict[str, object]]) -> dict[str, object]:
    output = [
        row
        for row in candidates
        if int_value(row, "review_root_exact") > 0
        and int_value(row, "review_root_false") == 0
        and int_value(row, "loo_false_edges") == 0
    ]
    return max(
        output,
        key=lambda row: (
            int_value(row, "review_root_exact"),
            int_value(row, "loo_correct_edges"),
            -int_value(row, "review_root_unknown"),
            -int_value(row, "feature_count"),
            str(row.get("context_family", "")),
        ),
        default={},
    )


def build(
    slot_rows: list[dict[str, str]],
    review_chains: list[dict[str, str]],
    max_features: int,
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    rows = enrich_edges(slot_rows)
    edge_ranks = review_edge_ranks(review_chains)
    candidates, review_rows_by_context = evaluate_candidates(rows, review_chains, max_features)
    best = candidates[0] if candidates else {}
    false_free = best_false_free(candidates)
    selected_context = str(false_free.get("context_family") or best.get("context_family", ""))
    selected_review_rows = review_rows_by_context.get(selected_context, [])
    summary = {
        "scope": "total",
        "candidate_mode": "high_safe_low_exception_source_terminal_delta",
        "edge_rows": len(rows),
        "review_chains": len(review_chains),
        "review_edges": len(edge_ranks),
        "features": len(FEATURES),
        "feature_sets": len(feature_sets(max_features)),
        "candidate_rows": len(candidates),
        "best_context": best.get("context_family", ""),
        "best_edge_correct": best.get("loo_correct_edges", 0),
        "best_edge_false": best.get("loo_false_edges", 0),
        "best_review_exact": best.get("review_root_exact", 0),
        "best_review_false": best.get("review_root_false", 0),
        "best_review_unknown": best.get("review_root_unknown", 0),
        "best_false_free_context": false_free.get("context_family", ""),
        "best_false_free_edge_correct": false_free.get("loo_correct_edges", 0),
        "best_false_free_review_exact": false_free.get("review_root_exact", 0),
        "best_false_free_review_unknown": false_free.get("review_root_unknown", 0),
        "promotion_candidate_bytes": false_free.get("review_root_exact", 0),
        "promotion_ready_bytes": 0,
        "issue_rows": 0,
    }
    return summary, candidates, selected_review_rows


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
table {{ border-collapse: collapse; width: 100%; min-width: 2000px; }}
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
  <div class="box"><div class="num">{summary['edge_rows']}</div><div class="muted">edge rows</div></div>
  <div class="box"><div class="num">{summary['best_review_exact']}/{summary['best_review_false']}</div><div class="muted">best review exact/false</div></div>
  <div class="box"><div class="num">{summary['best_false_free_review_exact']}</div><div class="muted">false-free review exact</div></div>
  <div class="box"><div class="num">{summary['best_false_free_context']}</div><div class="muted">false-free context</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Selected chain replay</h2>{render_table(chains, CHAIN_FIELDNAMES)}</div>
<div class="panel"><h2>Candidates</h2>{render_table(candidates, CANDIDATE_FIELDNAMES)}</div>
<script type="application/json" id="gradient-sequence-high-safe-low-exception-source-terminal-delta-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe source-chain delta contexts for terminal replay.")
    parser.add_argument("--slots", type=Path, default=DEFAULT_SLOTS)
    parser.add_argument("--review-chains", type=Path, default=DEFAULT_REVIEW_CHAINS)
    parser.add_argument("--max-features", type=int, default=3)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Gradient Sequence High-Safe Low Exception Source-Terminal Delta Probe",
    )
    args = parser.parse_args()

    summary, candidates, chains = build(read_csv(args.slots), read_csv(args.review_chains), args.max_features)
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "candidates.csv", CANDIDATE_FIELDNAMES, candidates)
    write_csv(args.output / "chains.csv", CHAIN_FIELDNAMES, chains)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, candidates, chains, args.title))

    print(f"Edge rows: {summary['edge_rows']}")
    print(
        "Best delta replay: "
        f"{summary['best_context']} = "
        f"{summary['best_review_exact']} exact / {summary['best_review_false']} false"
    )
    print(
        "Best false-free delta replay: "
        f"{summary['best_false_free_context']} = "
        f"{summary['best_false_free_review_exact']} exact"
    )
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
