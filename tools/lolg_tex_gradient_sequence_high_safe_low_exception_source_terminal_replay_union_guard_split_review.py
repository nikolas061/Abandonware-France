#!/usr/bin/env python3
"""Review split guards for replay-union guard misses."""

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
from lolg_tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_review import (
    DEFAULT_CHAINS,
    DEFAULT_COMPACT_CONTEXT_LIMIT,
    DEFAULT_SLOTS,
    DEFAULT_SOURCE_TERMINALS,
    DEFAULT_UNION_ROOTS,
    STABLE_GUARD_FEATURES,
    context_for,
    load_union_roots,
)
from lolg_tex_micro_mixed_value_payload_state_opcode_probe import ratio, write_csv


DEFAULT_GUARD_SUMMARY = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard/summary.csv"
)
DEFAULT_OUTPUT = Path("output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_split")

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "chain_rows",
    "union_roots",
    "base_context_family",
    "base_contexts",
    "base_exact_roots",
    "miss_roots",
    "extra_features",
    "max_extra_features",
    "extra_feature_sets",
    "candidate_rows",
    "compact_context_limit",
    "best_split_context_family",
    "best_split_extra_features",
    "best_split_roots",
    "best_split_contexts",
    "combined_roots",
    "combined_contexts",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

CANDIDATE_FIELDNAMES = [
    "rank",
    "split_context_family",
    "extra_feature_count",
    "split_contexts",
    "split_roots",
    "remaining_misses",
    "combined_roots",
    "combined_contexts",
    "roots_per_added_context",
    "verdict",
    "sample_contexts",
]

MISS_FIELDNAMES = [
    "rank",
    "root_slot_rank",
    "target_low",
    "union_prediction",
    "path",
    "base_context",
    "base_context_union_roots",
    "base_context_other_roots",
    "best_split_context",
    "split_verdict",
]

CONTEXT_FIELDNAMES = [
    "rank",
    "candidate_rank",
    "split_context_family",
    "context_key",
    "split_roots",
    "sample_roots",
]


def read_summary(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    with path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    return rows[0] if rows else {}


def read_union_rows(path: Path) -> dict[str, dict[str, str]]:
    with path.open(newline="") as handle:
        return {row["root_slot_rank"]: row for row in csv.DictReader(handle)}


def format_context(key: tuple[str, ...]) -> str:
    return "|".join(key)


def group_rows(
    rows: list[dict[str, str]],
    union_roots: set[str],
    fields: tuple[str, ...],
) -> dict[tuple[str, ...], dict[str, list[dict[str, str]]]]:
    grouped: dict[tuple[str, ...], dict[str, list[dict[str, str]]]] = defaultdict(
        lambda: {"covered": [], "other": []}
    )
    for row in rows:
        root = str(row.get("root_slot_rank", ""))
        bucket = "covered" if root in union_roots else "other"
        grouped[context_for(row, fields)][bucket].append(row)
    return grouped


def pure_contexts(
    grouped: dict[tuple[str, ...], dict[str, list[dict[str, str]]]],
) -> list[tuple[tuple[str, ...], list[str]]]:
    output = [
        (key, sorted({row["root_slot_rank"] for row in buckets["covered"]}, key=int))
        for key, buckets in grouped.items()
        if buckets["covered"] and not buckets["other"]
    ]
    output.sort(key=lambda item: (-len(item[1]), format_context(item[0])))
    return output


def candidate_verdict(
    combined_roots: int,
    union_root_count: int,
    combined_contexts: int,
    compact_context_limit: int,
) -> str:
    if combined_roots == union_root_count and combined_contexts <= compact_context_limit:
        return "combined_full_compact_guard_ready"
    if combined_roots == union_root_count:
        return "combined_full_fragmented_guard_review"
    return "partial_split_guard_review"


def evaluate_split(
    split_rows: list[dict[str, str]],
    union_roots: set[str],
    miss_roots: set[str],
    base_fields: tuple[str, ...],
    extra_fields: tuple[str, ...],
    base_exact_roots: set[str],
    base_contexts: int,
    compact_context_limit: int,
) -> tuple[dict[str, object] | None, list[dict[str, object]]]:
    fields = base_fields + extra_fields
    grouped = group_rows(split_rows, union_roots, fields)
    split_contexts = [
        (key, [root for root in roots if root in miss_roots])
        for key, roots in pure_contexts(grouped)
        if any(root in miss_roots for root in roots)
    ]
    if not split_contexts:
        return None, []

    split_root_set = {root for _, roots in split_contexts for root in roots}
    combined_root_count = len(base_exact_roots | split_root_set)
    combined_context_count = base_contexts + len(split_contexts)
    split_context_family = "+".join(fields)
    sample_contexts = "; ".join(
        f"{format_context(key)}:{','.join(roots[:4])}" for key, roots in split_contexts[:5]
    )
    candidate = {
        "rank": 0,
        "split_context_family": split_context_family,
        "extra_feature_count": len(extra_fields),
        "split_contexts": len(split_contexts),
        "split_roots": len(split_root_set),
        "remaining_misses": len(miss_roots - split_root_set),
        "combined_roots": combined_root_count,
        "combined_contexts": combined_context_count,
        "roots_per_added_context": ratio(len(split_root_set), len(split_contexts)),
        "verdict": candidate_verdict(
            combined_root_count,
            len(union_roots),
            combined_context_count,
            compact_context_limit,
        ),
        "sample_contexts": sample_contexts,
    }
    context_rows = [
        {
            "rank": 0,
            "candidate_rank": 0,
            "split_context_family": split_context_family,
            "context_key": format_context(key),
            "split_roots": len(roots),
            "sample_roots": ",".join(roots[:8]),
        }
        for key, roots in split_contexts
    ]
    return candidate, context_rows


def sort_candidates(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    rows.sort(
        key=lambda row: (
            -int(row["combined_roots"]),
            int(row["combined_contexts"]),
            -int(row["split_roots"]),
            int(row["extra_feature_count"]),
            str(row["split_context_family"]),
        )
    )
    for index, row in enumerate(rows, start=1):
        row["rank"] = index
    return rows


def build_miss_rows(
    misses: set[str],
    union_rows: dict[str, dict[str, str]],
    rows_by_root: dict[str, dict[str, str]],
    base_grouped: dict[tuple[str, ...], dict[str, list[dict[str, str]]]],
    base_fields: tuple[str, ...],
    best_context_by_root: dict[str, str],
) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for root in sorted(misses, key=int):
        row = rows_by_root[root]
        union = union_rows.get(root, {})
        base_context = context_for(row, base_fields)
        base_bucket = base_grouped[base_context]
        split_context = best_context_by_root.get(root, "")
        output.append(
            {
                "rank": len(output) + 1,
                "root_slot_rank": root,
                "target_low": union.get("target_low", row.get("target_low", "")),
                "union_prediction": union.get("prediction", ""),
                "path": union.get("path", row.get("path", "")),
                "base_context": format_context(base_context),
                "base_context_union_roots": ",".join(
                    sorted({item["root_slot_rank"] for item in base_bucket["covered"]}, key=int)
                ),
                "base_context_other_roots": ",".join(
                    sorted({item["root_slot_rank"] for item in base_bucket["other"]}, key=int)
                ),
                "best_split_context": split_context,
                "split_verdict": "split_exact" if split_context else "split_missing",
            }
        )
    return output


def build(
    slot_rows: list[dict[str, str]],
    source_terminal_rows: list[dict[str, str]],
    chains: list[dict[str, str]],
    union_roots: set[str],
    union_rows: dict[str, dict[str, str]],
    base_context_family: str,
    max_extra_features: int,
    compact_context_limit: int,
    context_candidate_limit: int,
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    rows = build_chain_inputs(slot_rows, source_terminal_rows, chains)
    rows_by_root = {row["root_slot_rank"]: row for row in rows}
    base_fields = tuple(base_context_family.split("+"))
    base_grouped = group_rows(rows, union_roots, base_fields)
    base_pure = pure_contexts(base_grouped)
    base_exact_roots = {root for _, roots in base_pure for root in roots}
    misses = union_roots - base_exact_roots
    mixed_base_keys = {
        key for key, buckets in base_grouped.items() if buckets["covered"] and buckets["other"]
    }
    split_rows = [row for row in rows if context_for(row, base_fields) in mixed_base_keys]
    extra_features = [feature for feature in STABLE_GUARD_FEATURES if feature not in base_fields]
    extra_sets: list[tuple[str, ...]] = []
    for size in range(1, max_extra_features + 1):
        extra_sets.extend(itertools.combinations(extra_features, size))

    candidates: list[dict[str, object]] = []
    contexts_by_family: dict[str, list[dict[str, object]]] = {}
    for extra_fields in extra_sets:
        candidate, contexts = evaluate_split(
            split_rows,
            union_roots,
            misses,
            base_fields,
            extra_fields,
            base_exact_roots,
            len(base_pure),
            compact_context_limit,
        )
        if candidate is None:
            continue
        family = str(candidate["split_context_family"])
        candidates.append(candidate)
        contexts_by_family[family] = contexts

    candidates = sort_candidates(candidates)
    best = candidates[0] if candidates else {}
    best_contexts = contexts_by_family.get(str(best.get("split_context_family", "")), [])
    best_context_by_root: dict[str, str] = {}
    for context in best_contexts:
        for root in str(context["sample_roots"]).split(","):
            if root:
                best_context_by_root[root] = str(context["context_key"])

    context_rows: list[dict[str, object]] = []
    for candidate in candidates[:context_candidate_limit]:
        contexts = contexts_by_family.get(str(candidate["split_context_family"]), [])
        for context in contexts:
            context = dict(context)
            context["rank"] = len(context_rows) + 1
            context["candidate_rank"] = candidate["rank"]
            context_rows.append(context)

    miss_rows = build_miss_rows(misses, union_rows, rows_by_root, base_grouped, base_fields, best_context_by_root)
    promotion_candidate = (
        int(best.get("combined_roots", 0)) == len(union_roots)
        and int(best.get("combined_contexts", 0)) <= compact_context_limit
    )
    summary = {
        "scope": "total",
        "candidate_mode": "high_safe_low_exception_source_terminal_replay_union_guard_split",
        "chain_rows": len(rows),
        "union_roots": len(union_roots),
        "base_context_family": base_context_family,
        "base_contexts": len(base_pure),
        "base_exact_roots": len(base_exact_roots),
        "miss_roots": len(misses),
        "extra_features": len(extra_features),
        "max_extra_features": max_extra_features,
        "extra_feature_sets": len(extra_sets),
        "candidate_rows": len(candidates),
        "compact_context_limit": compact_context_limit,
        "best_split_context_family": best.get("split_context_family", ""),
        "best_split_extra_features": best.get("extra_feature_count", 0),
        "best_split_roots": best.get("split_roots", 0),
        "best_split_contexts": best.get("split_contexts", 0),
        "combined_roots": best.get("combined_roots", len(base_exact_roots)),
        "combined_contexts": best.get("combined_contexts", len(base_pure)),
        "promotion_candidate_bytes": len(union_roots) if promotion_candidate else 0,
        "promotion_ready_bytes": 0,
        "issue_rows": 0,
    }
    return summary, candidates, miss_rows, context_rows


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
    misses: list[dict[str, object]],
    contexts: list[dict[str, object]],
    title: str,
) -> str:
    data_json = json.dumps(
        {
            "summary": summary,
            "candidates": candidates[:220],
            "misses": misses,
            "contexts": contexts[:400],
        },
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
Ce rapport garde la base compacte, puis scanne des splits sur les groupes mixtes
pour couvrir les racines restantes sans ajouter de faux.
</p>
<div class="grid">
{''.join(f'<div class="box"><div class="muted">{html.escape(key)}</div><div class="num">{html.escape(str(value))}</div></div>' for key, value in summary.items())}
</div>
<h2>Candidats de split</h2>
<div class="panel">{render_table(candidates, CANDIDATE_FIELDNAMES)}</div>
<h2>Misses de la garde compacte</h2>
<div class="panel">{render_table(misses, MISS_FIELDNAMES)}</div>
<h2>Contextes purs des meilleurs splits</h2>
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
    parser.add_argument("--guard-summary", type=Path, default=DEFAULT_GUARD_SUMMARY)
    parser.add_argument("--base-context-family", default="")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-extra-features", type=int, default=2)
    parser.add_argument("--compact-context-limit", type=int, default=DEFAULT_COMPACT_CONTEXT_LIMIT)
    parser.add_argument("--context-candidate-limit", type=int, default=40)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    guard_summary = read_summary(args.guard_summary)
    base_context_family = args.base_context_family or guard_summary.get("best_compact_context_family", "")
    if not base_context_family:
        raise SystemExit("Missing base context family; run the guard review first or pass --base-context-family.")
    slot_rows = read_csv(args.slots)
    source_terminal_rows = read_csv(args.source_terminals)
    chains = read_csv(args.chains)
    union_roots = load_union_roots(args.union_roots)
    union_rows = read_union_rows(args.union_roots)
    summary, candidates, misses, contexts = build(
        slot_rows,
        source_terminal_rows,
        chains,
        union_roots,
        union_rows,
        base_context_family,
        args.max_extra_features,
        args.compact_context_limit,
        args.context_candidate_limit,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "candidates.csv", CANDIDATE_FIELDNAMES, candidates)
    write_csv(args.output / "misses.csv", MISS_FIELDNAMES, misses)
    write_csv(args.output / "contexts.csv", CONTEXT_FIELDNAMES, contexts)
    title = "Lands of Lore II .tex Source Terminal Replay Union Guard Split Review"
    (args.output / "index.html").write_text(
        build_html(summary, candidates, misses, contexts, title),
        encoding="utf-8",
    )
    print(f"Base guard: {summary['base_exact_roots']} roots / {summary['base_contexts']} contexts")
    print(f"Miss roots: {summary['miss_roots']}")
    print(f"Best split: {summary['best_split_roots']} roots / {summary['best_split_contexts']} contexts")
    print(f"Combined guard: {summary['combined_roots']} roots / {summary['combined_contexts']} contexts")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
