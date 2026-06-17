#!/usr/bin/env python3
"""Probe high-safe source dependency chains for low exceptions."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gradient_sequence_high_safe_low_exception_probe import strict_prediction
from lolg_tex_micro_mixed_value_payload_state_opcode_probe import int_value, ratio, write_csv


DEFAULT_SLOTS = Path("output/tex_gradient_sequence_high_safe_low_exception_source_dependency/slots.csv")
DEFAULT_OUTPUT = Path("output/tex_gradient_sequence_high_safe_low_exception_source_chain")

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "source_dependency_slots",
    "unknown_highsafe_source_chains",
    "unique_terminal_slots",
    "cycle_chains",
    "terminal_known_source_chains",
    "terminal_unknown_outside_chains",
    "terminal_other_chains",
    "max_chain_length",
    "candidate_rows",
    "best_context",
    "best_correct_slots",
    "best_false_slots",
    "best_unknown_slots",
    "best_precision",
    "best_coverage",
    "best_false_free_context",
    "best_false_free_slots",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

CHAIN_FIELDNAMES = [
    "rank",
    "root_slot_rank",
    "root_frontier_id",
    "root_target_offset",
    "root_target_low",
    "root_low_bucket",
    "chain_length",
    "terminal_slot_rank",
    "terminal_frontier_id",
    "terminal_target_offset",
    "terminal_target_low",
    "terminal_source_availability",
    "terminal_source_location",
    "terminal_dependency_verdict",
    "chain_state",
    "path",
]

TERMINAL_FIELDNAMES = [
    "rank",
    "terminal_slot_rank",
    "terminal_frontier_id",
    "terminal_start",
    "terminal_target_offset",
    "terminal_target_low",
    "terminal_low_bucket",
    "root_chains",
    "terminal_source_availability",
    "terminal_source_location",
    "terminal_source_decoded_byte",
    "terminal_source_expected_byte",
    "terminal_source_low",
    "terminal_source_low_delta",
    "terminal_rel_mod4",
    "terminal_rel_mod8",
    "terminal_seq_index",
    "terminal_dependency_verdict",
]

CANDIDATE_FIELDNAMES = [
    "rank",
    "target_kind",
    "context_family",
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
    value = str(row.get("source_decoded_byte", ""))
    if not value:
        value = str(row.get("source_expected_byte", ""))
    return value[-1] if value else ""


def context_functions():
    return {
        "source_low": lambda row: (source_low(row),),
        "source_byte": lambda row: (row.get("source_decoded_byte", "") or row.get("source_expected_byte", ""),),
        "source_low_rel4": lambda row: (source_low(row), row.get("rel_mod4", "")),
        "source_low_rel8": lambda row: (source_low(row), row.get("rel_mod8", "")),
        "source_low_seq": lambda row: (source_low(row), row.get("seq_index", "")),
        "source_low_frontier": lambda row: (source_low(row), row.get("frontier_id", "")),
        "source_low_start": lambda row: (source_low(row), row.get("start", "")),
        "source_delta_seq": lambda row: (row.get("source_low_delta", ""), row.get("seq_index", "")),
        "source_avail_rel_seq": lambda row: (
            row.get("source_availability", ""),
            row.get("rel_mod8", ""),
            row.get("seq_index", ""),
        ),
        "frontier_rel_seq": lambda row: (
            row.get("frontier_id", ""),
            row.get("rel_mod8", ""),
            row.get("seq_index", ""),
        ),
    }


def unknown_highsafe_edges(rows: list[dict[str, str]]) -> dict[str, str]:
    return {
        row["rank"]: row["source_slot_rank"]
        for row in rows
        if row.get("source_availability") == "unknown_source"
        and row.get("source_location") == "in_highsafe"
        and row.get("source_slot_rank")
    }


def build_chains(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    by_rank = {row["rank"]: row for row in rows}
    edges = unknown_highsafe_edges(rows)
    output: list[dict[str, object]] = []
    for root_rank in sorted(edges, key=lambda value: int(value)):
        path: list[str] = []
        seen: dict[str, int] = {}
        current = root_rank
        chain_state = "terminal"
        while True:
            if current in seen:
                path.append(current)
                chain_state = "cycle"
                break
            seen[current] = len(path)
            path.append(current)
            next_rank = edges.get(current)
            if not next_rank:
                break
            current = next_rank
        root = by_rank[root_rank]
        terminal = by_rank.get(current, root)
        output.append(
            {
                "rank": len(output) + 1,
                "root_slot_rank": root_rank,
                "root_frontier_id": root.get("frontier_id", ""),
                "root_target_offset": root.get("target_offset", ""),
                "root_target_low": root.get("target_low", ""),
                "root_low_bucket": root.get("low_bucket", ""),
                "chain_length": len(path),
                "terminal_slot_rank": terminal.get("rank", ""),
                "terminal_frontier_id": terminal.get("frontier_id", ""),
                "terminal_target_offset": terminal.get("target_offset", ""),
                "terminal_target_low": terminal.get("target_low", ""),
                "terminal_source_availability": terminal.get("source_availability", ""),
                "terminal_source_location": terminal.get("source_location", ""),
                "terminal_dependency_verdict": terminal.get("source_dependency_verdict", ""),
                "chain_state": chain_state,
                "path": "->".join(path),
            }
        )
    return output


def build_terminals(
    rows: list[dict[str, str]],
    chains: list[dict[str, object]],
) -> list[dict[str, object]]:
    by_rank = {row["rank"]: row for row in rows}
    root_counts = Counter(str(chain.get("terminal_slot_rank", "")) for chain in chains)
    output: list[dict[str, object]] = []
    for terminal_rank, root_count in sorted(root_counts.items(), key=lambda item: int(item[0])):
        row = by_rank[terminal_rank]
        output.append(
            {
                "rank": len(output) + 1,
                "terminal_slot_rank": terminal_rank,
                "terminal_frontier_id": row.get("frontier_id", ""),
                "terminal_start": row.get("start", ""),
                "terminal_target_offset": row.get("target_offset", ""),
                "terminal_target_low": row.get("target_low", ""),
                "terminal_low_bucket": row.get("low_bucket", ""),
                "root_chains": root_count,
                "terminal_source_availability": row.get("source_availability", ""),
                "terminal_source_location": row.get("source_location", ""),
                "terminal_source_decoded_byte": row.get("source_decoded_byte", ""),
                "terminal_source_expected_byte": row.get("source_expected_byte", ""),
                "terminal_source_low": source_low(row),
                "terminal_source_low_delta": row.get("source_low_delta", ""),
                "terminal_rel_mod4": row.get("rel_mod4", ""),
                "terminal_rel_mod8": row.get("rel_mod8", ""),
                "terminal_seq_index": row.get("seq_index", ""),
                "terminal_dependency_verdict": row.get("source_dependency_verdict", ""),
            }
        )
    return output


def evaluate_candidate(
    terminal_rows: list[dict[str, str]],
    context_family: str,
    context_func,
) -> dict[str, object]:
    all_counts: dict[tuple[object, ...], Counter[str]] = defaultdict(Counter)
    row_counts: dict[tuple[str, tuple[object, ...]], Counter[str]] = defaultdict(Counter)
    grouped: dict[tuple[object, ...], list[dict[str, str]]] = defaultdict(list)
    for row in terminal_rows:
        context = context_func(row)
        low = str(row.get("target_low", ""))
        all_counts[context][low] += 1
        row_counts[(str(row.get("row_id", "")), context)][low] += 1
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
    for row in terminal_rows:
        context = context_func(row)
        train_counts = all_counts[context].copy()
        train_counts.subtract(row_counts[(str(row.get("row_id", "")), context)])
        train_counts += Counter()
        prediction = strict_prediction(train_counts)
        if not prediction:
            unknown += 1
            continue
        if not sample_context:
            sample_context = "|".join(str(part) for part in context)
            sample_prediction = prediction
        if prediction == row.get("target_low", ""):
            correct += 1
        else:
            false += 1

    predicted = correct + false
    if predicted == 0:
        verdict = "no_terminal_signal"
    elif false == 0 and correct > 0:
        verdict = "false_free_terminal_review"
    else:
        verdict = "terminal_source_reject"
    return {
        "rank": 0,
        "target_kind": "terminal_low",
        "context_family": context_family,
        "contexts": len(grouped),
        "terminal_slots": len(terminal_rows),
        "loo_correct_slots": correct,
        "loo_false_slots": false,
        "loo_unknown_slots": unknown,
        "loo_precision": ratio(correct, predicted),
        "loo_coverage": ratio(predicted, len(terminal_rows)),
        "predicted_values": "|".join(f"{value}:{count}" for value, count in predicted_values.most_common()),
        "verdict": verdict,
        "sample_context": sample_context,
        "sample_prediction": sample_prediction,
    }


def evaluate_candidates(terminal_rows: list[dict[str, str]]) -> list[dict[str, object]]:
    candidates = [
        evaluate_candidate(terminal_rows, context_family, context_func)
        for context_family, context_func in context_functions().items()
    ]
    candidates.sort(
        key=lambda row: (
            -int_value(row, "loo_correct_slots"),
            int_value(row, "loo_false_slots"),
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


def build(rows: list[dict[str, str]]) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    chains = build_chains(rows)
    terminals = build_terminals(rows, chains)
    terminal_by_rank = {str(row["terminal_slot_rank"]): row for row in terminals}
    rows_by_rank = {row["rank"]: row for row in rows}
    candidate_inputs: list[dict[str, str]] = []
    for terminal in terminals:
        source = rows_by_rank[str(terminal["terminal_slot_rank"])]
        candidate_inputs.append({**source, **{k.replace("terminal_", ""): v for k, v in terminal.items()}})
    candidates = evaluate_candidates(candidate_inputs)
    best = best_candidate(candidates)
    false_free = best_false_free_candidate(candidates)
    chain_states = Counter(str(chain.get("chain_state", "")) for chain in chains)
    terminal_states = Counter(
        (
            str(chain.get("terminal_source_availability", "")),
            str(chain.get("terminal_source_location", "")),
        )
        for chain in chains
    )
    summary = {
        "scope": "total",
        "candidate_mode": "high_safe_low_exception_source_chain",
        "source_dependency_slots": len(rows),
        "unknown_highsafe_source_chains": len(chains),
        "unique_terminal_slots": len(terminals),
        "cycle_chains": chain_states.get("cycle", 0),
        "terminal_known_source_chains": terminal_states.get(("known_source", "outside_highsafe"), 0),
        "terminal_unknown_outside_chains": terminal_states.get(("unknown_source", "outside_highsafe"), 0),
        "terminal_other_chains": len(chains)
        - terminal_states.get(("known_source", "outside_highsafe"), 0)
        - terminal_states.get(("unknown_source", "outside_highsafe"), 0),
        "max_chain_length": max((int_value(chain, "chain_length") for chain in chains), default=0),
        "candidate_rows": len(candidates),
        "best_context": best.get("context_family", ""),
        "best_correct_slots": best.get("loo_correct_slots", 0),
        "best_false_slots": best.get("loo_false_slots", 0),
        "best_unknown_slots": best.get("loo_unknown_slots", 0),
        "best_precision": best.get("loo_precision", "0.000000"),
        "best_coverage": best.get("loo_coverage", "0.000000"),
        "best_false_free_context": false_free.get("context_family", ""),
        "best_false_free_slots": false_free.get("loo_correct_slots", 0),
        "promotion_candidate_bytes": false_free.get("loo_correct_slots", 0),
        "promotion_ready_bytes": 0,
        "issue_rows": 0,
    }
    return summary, chains, terminals, candidates


def render_table(rows: list[dict[str, object]], fields: list[str], limit: int = 220) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, object],
    chains: list[dict[str, object]],
    terminals: list[dict[str, object]],
    candidates: list[dict[str, object]],
    title: str,
) -> str:
    data_json = json.dumps(
        {"summary": summary, "chains": chains, "terminals": terminals, "candidates": candidates},
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
  <div class="box"><div class="num">{summary['unknown_highsafe_source_chains']}</div><div class="muted">unknown high-safe chains</div></div>
  <div class="box"><div class="num">{summary['unique_terminal_slots']}</div><div class="muted">unique terminals</div></div>
  <div class="box"><div class="num">{summary['cycle_chains']}</div><div class="muted">cycle chains</div></div>
  <div class="box"><div class="num">{summary['best_correct_slots']}/{summary['best_false_slots']}</div><div class="muted">best terminal correct/false</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Chains</h2>{render_table(chains, CHAIN_FIELDNAMES)}</div>
<div class="panel"><h2>Terminals</h2>{render_table(terminals, TERMINAL_FIELDNAMES)}</div>
<div class="panel"><h2>Candidates</h2>{render_table(candidates, CANDIDATE_FIELDNAMES)}</div>
<script type="application/json" id="gradient-sequence-high-safe-low-exception-source-chain-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe high-safe source dependency chains.")
    parser.add_argument("--slots", type=Path, default=DEFAULT_SLOTS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Gradient Sequence High-Safe Low Exception Source-Chain Probe",
    )
    args = parser.parse_args()

    summary, chains, terminals, candidates = build(read_csv(args.slots))
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "chains.csv", CHAIN_FIELDNAMES, chains)
    write_csv(args.output / "terminals.csv", TERMINAL_FIELDNAMES, terminals)
    write_csv(args.output / "candidates.csv", CANDIDATE_FIELDNAMES, candidates)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, chains, terminals, candidates, args.title))

    print(f"Unknown high-safe chains: {summary['unknown_highsafe_source_chains']}")
    print(f"Unique terminal slots: {summary['unique_terminal_slots']}")
    print(f"Cycle chains: {summary['cycle_chains']}")
    print(
        "Best terminal model: "
        f"{summary['best_context']} = "
        f"{summary['best_correct_slots']} correct / {summary['best_false_slots']} false"
    )
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
