#!/usr/bin/env python3
"""Review a no-bucket union of terminal replay and chain-context candidates."""

from __future__ import annotations

import argparse
import csv
import html
import json
from pathlib import Path

from lolg_tex_gradient_sequence_high_safe_low_exception_source_terminal_chain_context_probe import (
    build_chain_inputs,
    chain_predictions,
)
from lolg_tex_gradient_sequence_high_safe_low_exception_source_terminal_probe import (
    enrich_terminal_rows,
    read_csv,
    terminal_predictions,
)
from lolg_tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_support_probe import (
    replay_chains,
)
from lolg_tex_micro_mixed_value_payload_state_opcode_probe import int_value, write_csv


DEFAULT_SLOTS = Path("output/tex_gradient_sequence_high_safe_low_exception_source_dependency/slots.csv")
DEFAULT_TERMINALS = Path("output/tex_gradient_sequence_high_safe_low_exception_source_chain/terminals.csv")
DEFAULT_SOURCE_TERMINALS = Path("output/tex_gradient_sequence_high_safe_low_exception_source_terminal/terminals.csv")
DEFAULT_CHAINS = Path("output/tex_gradient_sequence_high_safe_low_exception_source_chain/chains.csv")
DEFAULT_REVIEW_CHAINS = Path("output/tex_gradient_sequence_high_safe_low_exception_source_terminal_review/chains.csv")
DEFAULT_CHAIN_CONTEXT_CANDIDATES = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_chain_context/candidates.csv"
)
DEFAULT_REPLAY_SUPPORT_CANDIDATES = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_support/candidates.csv"
)
DEFAULT_OUTPUT = Path("output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union")

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "candidate_rows",
    "selected_candidates",
    "covered_roots",
    "covered_chain_rows",
    "conflict_roots",
    "chain_context_candidates",
    "terminal_replay_candidates",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

SELECTED_FIELDNAMES = [
    "rank",
    "source",
    "context_family",
    "candidate_roots",
    "new_roots",
    "covered_roots_after",
    "verdict",
]

ROOT_FIELDNAMES = [
    "rank",
    "root_slot_rank",
    "prediction",
    "sources",
    "contexts",
    "target_low",
    "terminal_slot_rank",
    "path",
    "verdict",
]


def chain_context_items(
    slot_rows: list[dict[str, str]],
    source_terminal_rows: list[dict[str, str]],
    review_chains: list[dict[str, str]],
    candidate_rows: list[dict[str, str]],
) -> list[dict[str, object]]:
    chain_inputs = build_chain_inputs(slot_rows, source_terminal_rows, review_chains)
    target_by_root = {row["root_slot_rank"]: row["target_low"] for row in chain_inputs}
    output: list[dict[str, object]] = []
    for candidate in candidate_rows:
        if int_value(candidate, "loo_false_chains") != 0 or int_value(candidate, "loo_correct_chains") <= 0:
            continue
        context = candidate.get("context_family", "")
        predictions = chain_predictions(chain_inputs, context)
        mapping: dict[str, str] = {}
        false = 0
        for root_rank, prediction in predictions.items():
            if prediction == target_by_root.get(root_rank, ""):
                mapping[root_rank] = prediction
            else:
                false += 1
        if false == 0 and mapping:
            output.append({"source": "chain_context", "context_family": context, "mapping": mapping})
    return output


def terminal_replay_items(
    slot_rows: list[dict[str, str]],
    terminal_rows: list[dict[str, str]],
    chains: list[dict[str, str]],
    candidate_rows: list[dict[str, str]],
) -> list[dict[str, object]]:
    enriched_terminals = enrich_terminal_rows(slot_rows, terminal_rows)
    slots_by_rank = {row["rank"]: row for row in slot_rows}
    output: list[dict[str, object]] = []
    for candidate in candidate_rows:
        context = candidate.get("context_family", "")
        if "low_bucket" in context.split("+"):
            continue
        if int_value(candidate, "root_false_chains") != 0 or int_value(candidate, "root_exact_chains") <= 0:
            continue
        predictions = terminal_predictions(enriched_terminals, context)
        verdicts, replay_rows = replay_chains(context, predictions, chains, slots_by_rank)
        if verdicts["false"] != 0:
            continue
        mapping = {
            str(row["root_slot_rank"]): str(row["predicted_root_low"])
            for row in replay_rows
            if row.get("chain_verdict") == "exact"
        }
        if mapping:
            output.append({"source": "terminal_replay", "context_family": context, "mapping": mapping})
    return output


def select_union(
    items: list[dict[str, object]],
) -> tuple[list[dict[str, object]], dict[str, str], dict[str, list[str]], dict[str, list[str]], int]:
    remaining = list(items)
    covered: dict[str, str] = {}
    sources_by_root: dict[str, list[str]] = {}
    contexts_by_root: dict[str, list[str]] = {}
    selected: list[dict[str, object]] = []
    conflicts = 0
    while True:
        best: dict[str, object] | None = None
        best_gain = 0
        for item in remaining:
            mapping = item["mapping"]
            assert isinstance(mapping, dict)
            conflict = False
            gain = 0
            for root_rank, prediction in mapping.items():
                if root_rank in covered and covered[root_rank] != prediction:
                    conflict = True
                    break
                if root_rank not in covered:
                    gain += 1
            if conflict:
                conflicts += 1
                continue
            if gain > best_gain:
                best = item
                best_gain = gain
        if best is None:
            break
        mapping = best["mapping"]
        assert isinstance(mapping, dict)
        for root_rank, prediction in mapping.items():
            if root_rank not in covered:
                covered[root_rank] = prediction
            sources_by_root.setdefault(root_rank, []).append(str(best["source"]))
            contexts_by_root.setdefault(root_rank, []).append(str(best["context_family"]))
        selected.append(
            {
                "rank": len(selected) + 1,
                "source": best["source"],
                "context_family": best["context_family"],
                "candidate_roots": len(mapping),
                "new_roots": best_gain,
                "covered_roots_after": len(covered),
                "verdict": "selected_no_conflict",
            }
        )
        remaining.remove(best)
    return selected, covered, sources_by_root, contexts_by_root, conflicts


def build_root_rows(
    covered: dict[str, str],
    sources_by_root: dict[str, list[str]],
    contexts_by_root: dict[str, list[str]],
    slot_rows: list[dict[str, str]],
    chains: list[dict[str, str]],
) -> list[dict[str, object]]:
    slots_by_rank = {row["rank"]: row for row in slot_rows}
    chain_by_root = {row["root_slot_rank"]: row for row in chains}
    output: list[dict[str, object]] = []
    for root_rank, prediction in sorted(covered.items(), key=lambda item: int(item[0])):
        slot = slots_by_rank.get(root_rank, {})
        chain = chain_by_root.get(root_rank, {})
        target_low = slot.get("target_low", "") or chain.get("root_target_low", "")
        output.append(
            {
                "rank": len(output) + 1,
                "root_slot_rank": root_rank,
                "prediction": prediction,
                "sources": "|".join(dict.fromkeys(sources_by_root.get(root_rank, []))),
                "contexts": "|".join(dict.fromkeys(contexts_by_root.get(root_rank, []))),
                "target_low": target_low,
                "terminal_slot_rank": chain.get("terminal_slot_rank", ""),
                "path": chain.get("path", ""),
                "verdict": "correct" if prediction == target_low else "false",
            }
        )
    return output


def build(
    slot_rows: list[dict[str, str]],
    terminal_rows: list[dict[str, str]],
    source_terminal_rows: list[dict[str, str]],
    chains: list[dict[str, str]],
    review_chains: list[dict[str, str]],
    chain_context_candidates: list[dict[str, str]],
    replay_support_candidates: list[dict[str, str]],
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    items = [
        *chain_context_items(slot_rows, source_terminal_rows, review_chains, chain_context_candidates),
        *terminal_replay_items(slot_rows, terminal_rows, chains, replay_support_candidates),
    ]
    selected, covered, sources_by_root, contexts_by_root, conflicts = select_union(items)
    roots = build_root_rows(covered, sources_by_root, contexts_by_root, slot_rows, chains)
    verdicts = {row["verdict"] for row in roots}
    summary = {
        "scope": "total",
        "candidate_mode": "high_safe_low_exception_source_terminal_replay_union",
        "candidate_rows": len(items),
        "selected_candidates": len(selected),
        "covered_roots": len(covered),
        "covered_chain_rows": len(roots),
        "conflict_roots": conflicts,
        "chain_context_candidates": sum(1 for item in items if item["source"] == "chain_context"),
        "terminal_replay_candidates": sum(1 for item in items if item["source"] == "terminal_replay"),
        "promotion_candidate_bytes": len(covered),
        "promotion_ready_bytes": 0,
        "issue_rows": 0 if verdicts <= {"correct"} else len([row for row in roots if row["verdict"] != "correct"]),
    }
    return summary, selected, roots


def render_table(rows: list[dict[str, object]], fields: list[str], limit: int = 220) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, object],
    selected: list[dict[str, object]],
    roots: list[dict[str, object]],
    title: str,
) -> str:
    data_json = json.dumps({"summary": summary, "selected": selected, "roots": roots}, indent=2, sort_keys=True)
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body {{ margin: 2rem; background: #101214; color: #edf5f4; font: 14px/1.45 system-ui, sans-serif; }}
table {{ border-collapse: collapse; width: 100%; min-width: 1600px; }}
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
  <div class="box"><div class="num">{summary['candidate_rows']}</div><div class="muted">candidate rows</div></div>
  <div class="box"><div class="num">{summary['selected_candidates']}</div><div class="muted">selected candidates</div></div>
  <div class="box"><div class="num">{summary['covered_roots']}</div><div class="muted">covered roots</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Selected candidates</h2>{render_table(selected, SELECTED_FIELDNAMES)}</div>
<div class="panel"><h2>Covered roots</h2>{render_table(roots, ROOT_FIELDNAMES)}</div>
<script type="application/json" id="gradient-sequence-high-safe-low-exception-source-terminal-replay-union-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Review union of source-terminal replay candidates.")
    parser.add_argument("--slots", type=Path, default=DEFAULT_SLOTS)
    parser.add_argument("--terminals", type=Path, default=DEFAULT_TERMINALS)
    parser.add_argument("--source-terminals", type=Path, default=DEFAULT_SOURCE_TERMINALS)
    parser.add_argument("--chains", type=Path, default=DEFAULT_CHAINS)
    parser.add_argument("--review-chains", type=Path, default=DEFAULT_REVIEW_CHAINS)
    parser.add_argument("--chain-context-candidates", type=Path, default=DEFAULT_CHAIN_CONTEXT_CANDIDATES)
    parser.add_argument("--replay-support-candidates", type=Path, default=DEFAULT_REPLAY_SUPPORT_CANDIDATES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Gradient Sequence High-Safe Low Exception Source-Terminal Replay Union Review",
    )
    args = parser.parse_args()

    summary, selected, roots = build(
        read_csv(args.slots),
        read_csv(args.terminals),
        read_csv(args.source_terminals),
        read_csv(args.chains),
        read_csv(args.review_chains),
        read_csv(args.chain_context_candidates),
        read_csv(args.replay_support_candidates),
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "selected.csv", SELECTED_FIELDNAMES, selected)
    write_csv(args.output / "roots.csv", ROOT_FIELDNAMES, roots)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, selected, roots, args.title))

    print(f"Candidate rows: {summary['candidate_rows']}")
    print(f"Selected candidates: {summary['selected_candidates']}")
    print(f"Covered roots: {summary['covered_roots']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
