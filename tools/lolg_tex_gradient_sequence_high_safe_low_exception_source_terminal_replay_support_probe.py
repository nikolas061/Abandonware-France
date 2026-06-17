#!/usr/bin/env python3
"""Probe broader terminal contexts through source-chain oracle replay."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter
from pathlib import Path

from lolg_tex_gradient_sequence_high_safe_low_exception_source_terminal_probe import (
    enrich_terminal_rows,
    read_csv,
    terminal_predictions,
)
from lolg_tex_micro_mixed_value_payload_state_opcode_probe import int_value, ratio, write_csv


DEFAULT_SLOTS = Path("output/tex_gradient_sequence_high_safe_low_exception_source_dependency/slots.csv")
DEFAULT_TERMINALS = Path("output/tex_gradient_sequence_high_safe_low_exception_source_chain/terminals.csv")
DEFAULT_CHAINS = Path("output/tex_gradient_sequence_high_safe_low_exception_source_chain/chains.csv")
DEFAULT_CANDIDATES = Path("output/tex_gradient_sequence_high_safe_low_exception_source_terminal/candidates.csv")
DEFAULT_OUTPUT = Path("output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_support")

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "terminal_contexts",
    "terminal_contexts_without_low_bucket",
    "chain_rows",
    "best_context",
    "best_exact_chains",
    "best_false_chains",
    "best_unknown_chains",
    "best_false_free_context",
    "best_false_free_chains",
    "best_false_free_unknown_chains",
    "best_no_bucket_context",
    "best_no_bucket_exact_chains",
    "best_no_bucket_false_chains",
    "best_no_bucket_unknown_chains",
    "best_no_bucket_false_free_context",
    "best_no_bucket_false_free_chains",
    "best_no_bucket_false_free_unknown_chains",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

CANDIDATE_FIELDNAMES = [
    "rank",
    "context_family",
    "uses_low_bucket",
    "terminal_correct_slots",
    "terminal_false_slots",
    "chain_rows",
    "root_exact_chains",
    "root_false_chains",
    "root_unknown_chains",
    "root_precision",
    "root_coverage",
    "verdict",
]

CHAIN_FIELDNAMES = [
    "rank",
    "context_family",
    "root_slot_rank",
    "terminal_slot_rank",
    "chain_length",
    "path",
    "terminal_prediction",
    "delta_path",
    "predicted_root_low",
    "root_target_low",
    "chain_verdict",
]


def low_add(low: str, deltas: list[str]) -> str:
    if not low or any(not delta for delta in deltas):
        return ""
    return f"{(int(low, 16) + sum(int(delta) for delta in deltas)) & 0x0F:x}"


def replay_chains(
    context_family: str,
    predictions: dict[str, str],
    chains: list[dict[str, str]],
    slots_by_rank: dict[str, dict[str, str]],
) -> tuple[Counter[str], list[dict[str, object]]]:
    verdicts: Counter[str] = Counter()
    rows: list[dict[str, object]] = []
    for chain in chains:
        terminal_prediction = predictions.get(chain.get("terminal_slot_rank", ""), "")
        if not terminal_prediction:
            verdicts["unknown"] += 1
            continue
        path = [rank for rank in chain.get("path", "").split("->") if rank]
        deltas = [slots_by_rank.get(rank, {}).get("source_low_delta", "") for rank in path[:-1]]
        predicted_root = low_add(terminal_prediction, deltas)
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
                "context_family": context_family,
                "root_slot_rank": chain.get("root_slot_rank", ""),
                "terminal_slot_rank": chain.get("terminal_slot_rank", ""),
                "chain_length": chain.get("chain_length", ""),
                "path": chain.get("path", ""),
                "terminal_prediction": terminal_prediction,
                "delta_path": "+".join(deltas),
                "predicted_root_low": predicted_root,
                "root_target_low": chain.get("root_target_low", ""),
                "chain_verdict": verdict,
            }
        )
    return verdicts, rows


def evaluate_candidate(
    candidate: dict[str, str],
    terminal_rows: list[dict[str, str]],
    chains: list[dict[str, str]],
    slots_by_rank: dict[str, dict[str, str]],
) -> tuple[dict[str, object], list[dict[str, object]]]:
    context = candidate.get("context_family", "")
    predictions = terminal_predictions(terminal_rows, context)
    verdicts, replay_rows = replay_chains(context, predictions, chains, slots_by_rank)
    predicted = verdicts["exact"] + verdicts["false"]
    if verdicts["exact"] == 0:
        verdict = "no_terminal_replay_signal"
    elif verdicts["false"] == 0:
        verdict = "false_free_terminal_replay_review"
    else:
        verdict = "terminal_replay_reject"
    return (
        {
            "rank": 0,
            "context_family": context,
            "uses_low_bucket": "1" if "low_bucket" in context.split("+") else "0",
            "terminal_correct_slots": candidate.get("loo_correct_slots", "0"),
            "terminal_false_slots": candidate.get("loo_false_slots", "0"),
            "chain_rows": len(chains),
            "root_exact_chains": verdicts["exact"],
            "root_false_chains": verdicts["false"],
            "root_unknown_chains": verdicts["unknown"],
            "root_precision": ratio(verdicts["exact"], predicted),
            "root_coverage": ratio(predicted, len(chains)),
            "verdict": verdict,
        },
        replay_rows,
    )


def sort_candidates(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    rows.sort(
        key=lambda row: (
            -int_value(row, "root_exact_chains"),
            int_value(row, "root_false_chains"),
            int_value(row, "root_unknown_chains"),
            str(row.get("context_family", "")),
        )
    )
    for index, row in enumerate(rows, start=1):
        row["rank"] = index
    return rows


def best_false_free(rows: list[dict[str, object]]) -> dict[str, object]:
    candidates = [
        row
        for row in rows
        if int_value(row, "root_exact_chains") > 0
        and int_value(row, "root_false_chains") == 0
    ]
    return max(
        candidates,
        key=lambda row: (
            int_value(row, "root_exact_chains"),
            -int_value(row, "root_unknown_chains"),
            str(row.get("context_family", "")),
        ),
        default={},
    )


def build(
    dependency_slots: list[dict[str, str]],
    terminal_rows: list[dict[str, str]],
    chains: list[dict[str, str]],
    candidates: list[dict[str, str]],
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    enriched_terminals = enrich_terminal_rows(dependency_slots, terminal_rows)
    slots_by_rank = {row["rank"]: row for row in dependency_slots}
    evaluated: list[dict[str, object]] = []
    replay_rows_by_context: dict[str, list[dict[str, object]]] = {}
    for candidate in candidates:
        row, replay_rows = evaluate_candidate(candidate, enriched_terminals, chains, slots_by_rank)
        evaluated.append(row)
        replay_rows_by_context[str(row["context_family"])] = replay_rows
    evaluated = sort_candidates(evaluated)
    no_bucket = [row for row in evaluated if str(row.get("uses_low_bucket", "")) != "1"]
    no_bucket = sort_candidates(no_bucket)
    best = evaluated[0] if evaluated else {}
    best_ff = best_false_free(evaluated)
    best_no_bucket = no_bucket[0] if no_bucket else {}
    best_no_bucket_ff = best_false_free(no_bucket)
    selected = best_no_bucket_ff or best_ff or best
    selected_rows = replay_rows_by_context.get(str(selected.get("context_family", "")), [])
    summary = {
        "scope": "total",
        "candidate_mode": "high_safe_low_exception_source_terminal_replay_support",
        "terminal_contexts": len(evaluated),
        "terminal_contexts_without_low_bucket": len(no_bucket),
        "chain_rows": len(chains),
        "best_context": best.get("context_family", ""),
        "best_exact_chains": best.get("root_exact_chains", 0),
        "best_false_chains": best.get("root_false_chains", 0),
        "best_unknown_chains": best.get("root_unknown_chains", 0),
        "best_false_free_context": best_ff.get("context_family", ""),
        "best_false_free_chains": best_ff.get("root_exact_chains", 0),
        "best_false_free_unknown_chains": best_ff.get("root_unknown_chains", 0),
        "best_no_bucket_context": best_no_bucket.get("context_family", ""),
        "best_no_bucket_exact_chains": best_no_bucket.get("root_exact_chains", 0),
        "best_no_bucket_false_chains": best_no_bucket.get("root_false_chains", 0),
        "best_no_bucket_unknown_chains": best_no_bucket.get("root_unknown_chains", 0),
        "best_no_bucket_false_free_context": best_no_bucket_ff.get("context_family", ""),
        "best_no_bucket_false_free_chains": best_no_bucket_ff.get("root_exact_chains", 0),
        "best_no_bucket_false_free_unknown_chains": best_no_bucket_ff.get("root_unknown_chains", 0),
        "promotion_candidate_bytes": best_no_bucket_ff.get("root_exact_chains", 0),
        "promotion_ready_bytes": 0,
        "issue_rows": 0,
    }
    return summary, evaluated, selected_rows


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
  <div class="box"><div class="num">{summary['best_exact_chains']}/{summary['best_false_chains']}</div><div class="muted">best exact/false</div></div>
  <div class="box"><div class="num">{summary['best_false_free_chains']}</div><div class="muted">best false-free chains</div></div>
  <div class="box"><div class="num">{summary['best_no_bucket_exact_chains']}/{summary['best_no_bucket_false_chains']}</div><div class="muted">best no-bucket exact/false</div></div>
  <div class="box"><div class="num">{summary['best_no_bucket_false_free_chains']}</div><div class="muted">no-bucket false-free chains</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Selected chain replay</h2>{render_table(chains, CHAIN_FIELDNAMES)}</div>
<div class="panel"><h2>Candidates</h2>{render_table(candidates, CANDIDATE_FIELDNAMES)}</div>
<script type="application/json" id="gradient-sequence-high-safe-low-exception-source-terminal-replay-support-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe terminal contexts through source-chain replay.")
    parser.add_argument("--slots", type=Path, default=DEFAULT_SLOTS)
    parser.add_argument("--terminals", type=Path, default=DEFAULT_TERMINALS)
    parser.add_argument("--chains", type=Path, default=DEFAULT_CHAINS)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Gradient Sequence High-Safe Low Exception Source-Terminal Replay Support Probe",
    )
    args = parser.parse_args()

    summary, candidates, chains = build(
        read_csv(args.slots),
        read_csv(args.terminals),
        read_csv(args.chains),
        read_csv(args.candidates),
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "candidates.csv", CANDIDATE_FIELDNAMES, candidates)
    write_csv(args.output / "chains.csv", CHAIN_FIELDNAMES, chains)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, candidates, chains, args.title))

    print(
        "Best terminal replay: "
        f"{summary['best_context']} = "
        f"{summary['best_exact_chains']} exact / {summary['best_false_chains']} false"
    )
    print(
        "Best no-bucket terminal replay: "
        f"{summary['best_no_bucket_context']} = "
        f"{summary['best_no_bucket_exact_chains']} exact / {summary['best_no_bucket_false_chains']} false"
    )
    print(
        "Best no-bucket false-free replay: "
        f"{summary['best_no_bucket_false_free_context']} = "
        f"{summary['best_no_bucket_false_free_chains']} chains"
    )
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
