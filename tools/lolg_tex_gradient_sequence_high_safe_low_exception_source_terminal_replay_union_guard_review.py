#!/usr/bin/env python3
"""Review compact guards for source-terminal replay-union roots."""

from __future__ import annotations

import argparse
import csv
import html
import itertools
import json
from collections import defaultdict
from pathlib import Path

from lolg_tex_gradient_sequence_high_safe_low_exception_source_terminal_chain_context_probe import (
    build_chain_inputs,
    read_csv,
)
from lolg_tex_micro_mixed_value_payload_state_opcode_probe import ratio, write_csv


DEFAULT_SLOTS = Path("output/tex_gradient_sequence_high_safe_low_exception_source_dependency/slots.csv")
DEFAULT_SOURCE_TERMINALS = Path("output/tex_gradient_sequence_high_safe_low_exception_source_terminal/terminals.csv")
DEFAULT_CHAINS = Path("output/tex_gradient_sequence_high_safe_low_exception_source_chain/chains.csv")
DEFAULT_UNION_ROOTS = Path("output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union/roots.csv")
DEFAULT_OUTPUT = Path("output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard")

DEFAULT_COMPACT_CONTEXT_LIMIT = 9

STABLE_GUARD_FEATURES = [
    "chain_length",
    "terminal_context",
    "terminal_prediction",
    "terminal_source_low",
    "terminal_target_mod32",
    "root_frontier_id",
    "root_rel_mod4",
    "root_rel_mod8",
    "root_rel_mod16",
    "root_target_mod32",
    "root_target_x_mod32",
    "root_target_y_mod8",
    "root_control_low",
    "root_control_class",
    "root_prefix_low",
    "root_fragment_low",
    "root_gradient_class",
    "root_shape_len_key",
    "root_shape_start_key",
    "root_start_mod32",
    "root_length_mod16",
    "edge1_source_target_delta_mod32",
    "edge1_relative_offset",
    "edge1_rel_mod4",
    "edge1_rel_mod8",
    "edge1_seq_index",
    "edge1_target_mod32",
    "edge1_control_low",
    "edge1_prefix_low",
    "edge1_fragment_low",
    "edge1_gradient_class",
    "edge2_rel_mod4",
    "edge2_rel_mod8",
    "edge2_target_mod32",
    "edge2_gradient_class",
]

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "chain_rows",
    "union_roots",
    "features",
    "max_features",
    "feature_sets",
    "candidate_rows",
    "compact_context_limit",
    "best_exact_roots",
    "best_exact_contexts",
    "best_exact_context_family",
    "best_compact_roots",
    "best_compact_contexts",
    "best_compact_context_family",
    "full_cover_candidates",
    "best_full_cover_contexts",
    "best_full_cover_context_family",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

CANDIDATE_FIELDNAMES = [
    "rank",
    "context_family",
    "feature_count",
    "guard_contexts",
    "exact_roots",
    "missed_roots",
    "exact_coverage",
    "roots_per_context",
    "verdict",
    "sample_contexts",
]

CONTEXT_FIELDNAMES = [
    "rank",
    "candidate_rank",
    "context_family",
    "context_key",
    "exact_roots",
    "sample_roots",
]


def load_union_roots(path: Path) -> set[str]:
    with path.open(newline="") as handle:
        return {row["root_slot_rank"] for row in csv.DictReader(handle)}


def feature_sets(features: list[str], max_features: int) -> list[tuple[str, ...]]:
    output: list[tuple[str, ...]] = []
    for size in range(1, max_features + 1):
        output.extend(itertools.combinations(features, size))
    return output


def context_for(row: dict[str, str], fields: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(str(row.get(field, "")) for field in fields)


def verdict_for(exact_roots: int, union_root_count: int, guard_contexts: int, compact_context_limit: int) -> str:
    if exact_roots == union_root_count and guard_contexts <= compact_context_limit:
        return "compact_full_guard_ready"
    if exact_roots == union_root_count:
        return "full_fragmented_guard_review"
    if guard_contexts <= compact_context_limit:
        return "compact_partial_guard_review"
    return "fragmented_partial_guard_review"


def evaluate_guard(
    rows: list[dict[str, str]],
    union_roots: set[str],
    fields: tuple[str, ...],
    compact_context_limit: int,
) -> tuple[dict[str, object] | None, list[dict[str, object]]]:
    grouped: dict[tuple[str, ...], dict[str, list[str]]] = defaultdict(lambda: {"covered": [], "other": []})
    for row in rows:
        root = str(row.get("root_slot_rank", ""))
        key = context_for(row, fields)
        bucket = "covered" if root in union_roots else "other"
        grouped[key][bucket].append(root)

    pure_contexts = [
        (key, sorted(set(buckets["covered"]), key=int))
        for key, buckets in grouped.items()
        if buckets["covered"] and not buckets["other"]
    ]
    if not pure_contexts:
        return None, []

    pure_contexts.sort(key=lambda item: (-len(item[1]), "|".join(item[0])))
    exact_root_set = {root for _, roots in pure_contexts for root in roots}
    exact_roots = len(exact_root_set)
    guard_contexts = len(pure_contexts)
    union_root_count = len(union_roots)
    context_family = "+".join(fields)
    sample_contexts = "; ".join(
        f"{'|'.join(key)}:{','.join(roots[:4])}" for key, roots in pure_contexts[:5]
    )
    candidate = {
        "rank": 0,
        "context_family": context_family,
        "feature_count": len(fields),
        "guard_contexts": guard_contexts,
        "exact_roots": exact_roots,
        "missed_roots": union_root_count - exact_roots,
        "exact_coverage": ratio(exact_roots, union_root_count),
        "roots_per_context": ratio(exact_roots, guard_contexts),
        "verdict": verdict_for(exact_roots, union_root_count, guard_contexts, compact_context_limit),
        "sample_contexts": sample_contexts,
    }
    contexts = [
        {
            "rank": 0,
            "candidate_rank": 0,
            "context_family": context_family,
            "context_key": "|".join(key),
            "exact_roots": len(roots),
            "sample_roots": ",".join(roots[:8]),
        }
        for key, roots in pure_contexts
    ]
    return candidate, contexts


def sort_candidates(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    rows.sort(
        key=lambda row: (
            -int(row["exact_roots"]),
            int(row["guard_contexts"]),
            int(row["feature_count"]),
            str(row["context_family"]),
        )
    )
    for index, row in enumerate(rows, start=1):
        row["rank"] = index
    return rows


def best_by_context_limit(rows: list[dict[str, object]], limit: int) -> dict[str, object]:
    candidates = [row for row in rows if int(row["guard_contexts"]) <= limit]
    return max(
        candidates,
        key=lambda row: (
            int(row["exact_roots"]),
            -int(row["guard_contexts"]),
            -int(row["feature_count"]),
            str(row["context_family"]),
        ),
        default={},
    )


def build(
    slot_rows: list[dict[str, str]],
    source_terminal_rows: list[dict[str, str]],
    chains: list[dict[str, str]],
    union_roots: set[str],
    max_features: int,
    compact_context_limit: int,
    context_candidate_limit: int,
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    rows = build_chain_inputs(slot_rows, source_terminal_rows, chains)
    fields_to_scan = feature_sets(STABLE_GUARD_FEATURES, max_features)
    candidates: list[dict[str, object]] = []
    contexts_by_family: dict[str, list[dict[str, object]]] = {}
    for fields in fields_to_scan:
        candidate, contexts = evaluate_guard(rows, union_roots, fields, compact_context_limit)
        if candidate is None:
            continue
        context_family = str(candidate["context_family"])
        candidates.append(candidate)
        contexts_by_family[context_family] = contexts

    candidates = sort_candidates(candidates)
    best = candidates[0] if candidates else {}
    compact = best_by_context_limit(candidates, compact_context_limit)
    full_cover = [row for row in candidates if int(row["exact_roots"]) == len(union_roots)]
    best_full = min(
        full_cover,
        key=lambda row: (int(row["guard_contexts"]), int(row["feature_count"]), str(row["context_family"])),
        default={},
    )
    promotion_candidates = [
        row for row in full_cover if int(row["guard_contexts"]) <= compact_context_limit
    ]

    context_rows: list[dict[str, object]] = []
    for candidate in candidates[:context_candidate_limit]:
        contexts = contexts_by_family.get(str(candidate["context_family"]), [])
        for context in contexts:
            context = dict(context)
            context["rank"] = len(context_rows) + 1
            context["candidate_rank"] = candidate["rank"]
            context_rows.append(context)

    summary = {
        "scope": "total",
        "candidate_mode": "high_safe_low_exception_source_terminal_replay_union_guard",
        "chain_rows": len(rows),
        "union_roots": len(union_roots),
        "features": len(STABLE_GUARD_FEATURES),
        "max_features": max_features,
        "feature_sets": len(fields_to_scan),
        "candidate_rows": len(candidates),
        "compact_context_limit": compact_context_limit,
        "best_exact_roots": best.get("exact_roots", 0),
        "best_exact_contexts": best.get("guard_contexts", 0),
        "best_exact_context_family": best.get("context_family", ""),
        "best_compact_roots": compact.get("exact_roots", 0),
        "best_compact_contexts": compact.get("guard_contexts", 0),
        "best_compact_context_family": compact.get("context_family", ""),
        "full_cover_candidates": len(full_cover),
        "best_full_cover_contexts": best_full.get("guard_contexts", 0),
        "best_full_cover_context_family": best_full.get("context_family", ""),
        "promotion_candidate_bytes": len(union_roots) if promotion_candidates else 0,
        "promotion_ready_bytes": 0,
        "issue_rows": 0,
    }
    return summary, candidates, context_rows


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
    contexts: list[dict[str, object]],
    title: str,
) -> str:
    data_json = json.dumps(
        {"summary": summary, "candidates": candidates[:220], "contexts": contexts[:400]},
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
<p class="muted">
Ce rapport cherche une garde compacte autour des racines deja couvertes par l'union replay.
Une garde est pure si ses contextes ne contiennent aucune racine hors union.
</p>
<div class="grid">
{''.join(f'<div class="box"><div class="muted">{html.escape(key)}</div><div class="num">{html.escape(str(value))}</div></div>' for key, value in summary.items())}
</div>
<h2>Candidats de garde</h2>
<div class="panel">{render_table(candidates, CANDIDATE_FIELDNAMES)}</div>
<h2>Contextes purs des meilleurs candidats</h2>
<div class="panel">{render_table(contexts, CONTEXT_FIELDNAMES)}</div>
<script type="application/json" id="data">{html.escape(data_json)}</script>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slots", type=Path, default=DEFAULT_SLOTS)
    parser.add_argument("--source-terminals", type=Path, default=DEFAULT_SOURCE_TERMINALS)
    parser.add_argument("--chains", type=Path, default=DEFAULT_CHAINS)
    parser.add_argument("--union-roots", type=Path, default=DEFAULT_UNION_ROOTS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-features", type=int, default=3)
    parser.add_argument("--compact-context-limit", type=int, default=DEFAULT_COMPACT_CONTEXT_LIMIT)
    parser.add_argument("--context-candidate-limit", type=int, default=40)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    slot_rows = read_csv(args.slots)
    source_terminal_rows = read_csv(args.source_terminals)
    chains = read_csv(args.chains)
    union_roots = load_union_roots(args.union_roots)
    summary, candidates, contexts = build(
        slot_rows,
        source_terminal_rows,
        chains,
        union_roots,
        args.max_features,
        args.compact_context_limit,
        args.context_candidate_limit,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "candidates.csv", CANDIDATE_FIELDNAMES, candidates)
    write_csv(args.output / "contexts.csv", CONTEXT_FIELDNAMES, contexts)
    title = "Lands of Lore II .tex Source Terminal Replay Union Guard Review"
    (args.output / "index.html").write_text(build_html(summary, candidates, contexts, title), encoding="utf-8")
    print(f"Union roots: {summary['union_roots']}")
    print(f"Best full-cover guard: {summary['best_exact_roots']} roots / {summary['best_exact_contexts']} contexts")
    print(f"Best compact guard: {summary['best_compact_roots']} roots / {summary['best_compact_contexts']} contexts")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
