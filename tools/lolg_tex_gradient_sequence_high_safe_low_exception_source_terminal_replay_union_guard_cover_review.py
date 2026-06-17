#!/usr/bin/env python3
"""Review a compact set-cover guard for replay-union roots."""

from __future__ import annotations

import argparse
import csv
import html
import itertools
import json
import math
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
from lolg_tex_micro_mixed_value_payload_state_opcode_probe import write_csv


DEFAULT_OUTPUT = Path("output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_cover")

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "chain_rows",
    "union_roots",
    "features",
    "max_features",
    "compact_context_limit",
    "raw_pure_contexts",
    "candidate_rows",
    "selected_contexts",
    "covered_roots",
    "missed_roots",
    "selected_families",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

ITEM_FIELDNAMES = [
    "rank",
    "context_family",
    "feature_count",
    "context_key",
    "exact_roots",
    "sample_roots",
    "verdict",
]

SELECTED_FIELDNAMES = [
    "rank",
    "context_family",
    "feature_count",
    "context_key",
    "exact_roots",
    "new_roots",
    "covered_roots_after",
    "sample_roots",
    "verdict",
]

ROOT_FIELDNAMES = [
    "rank",
    "root_slot_rank",
    "prediction",
    "target_low",
    "path",
    "selected_contexts",
    "verdict",
]


def read_union_rows(path: Path) -> dict[str, dict[str, str]]:
    with path.open(newline="") as handle:
        return {row["root_slot_rank"]: row for row in csv.DictReader(handle)}


def format_context(key: tuple[str, ...]) -> str:
    return "|".join(key)


def mask_for_roots(roots: list[str], root_index: dict[str, int]) -> int:
    mask = 0
    for root in roots:
        mask |= 1 << root_index[root]
    return mask


def generate_pure_items(
    rows: list[dict[str, str]],
    union_roots: set[str],
    root_index: dict[str, int],
    max_features: int,
) -> tuple[list[dict[str, object]], int]:
    best_by_mask: dict[int, tuple[tuple[int, int, str, str], dict[str, object]]] = {}
    raw_pure_contexts = 0
    for size in range(1, max_features + 1):
        for fields in itertools.combinations(STABLE_GUARD_FEATURES, size):
            grouped: dict[tuple[str, ...], dict[str, list[str]]] = defaultdict(lambda: {"covered": [], "other": []})
            for row in rows:
                root = str(row.get("root_slot_rank", ""))
                bucket = "covered" if root in union_roots else "other"
                grouped[context_for(row, fields)][bucket].append(root)
            for key, buckets in grouped.items():
                roots = sorted(set(buckets["covered"]), key=int)
                if not roots or buckets["other"]:
                    continue
                raw_pure_contexts += 1
                context_family = "+".join(fields)
                context_key = format_context(key)
                mask = mask_for_roots(roots, root_index)
                item = {
                    "mask": mask,
                    "rank": 0,
                    "context_family": context_family,
                    "feature_count": len(fields),
                    "context_key": context_key,
                    "exact_roots": len(roots),
                    "sample_roots": ",".join(roots[:8]),
                    "roots": roots,
                    "verdict": "pure_context",
                }
                score = (len(fields), len(context_key), context_family, context_key)
                previous = best_by_mask.get(mask)
                if previous is None or score < previous[0]:
                    best_by_mask[mask] = (score, item)

    items = [item for _, item in best_by_mask.values()]
    items.sort(key=lambda item: (-int(item["exact_roots"]), int(item["feature_count"]), str(item["context_family"])))

    kept: list[dict[str, object]] = []
    for item in items:
        mask = int(item["mask"])
        if any(mask | int(kept_item["mask"]) == int(kept_item["mask"]) for kept_item in kept):
            continue
        kept.append(item)
    for index, item in enumerate(kept, start=1):
        item["rank"] = index
    return kept, raw_pure_contexts


def find_cover(
    items: list[dict[str, object]],
    union_root_count: int,
    context_limit: int,
) -> list[dict[str, object]]:
    full_mask = (1 << union_root_count) - 1
    if not items:
        return []
    by_root: dict[int, list[dict[str, object]]] = defaultdict(list)
    for item in items:
        mask = int(item["mask"])
        for index in range(union_root_count):
            if mask & (1 << index):
                by_root[index].append(item)
    max_cover = max(int(item["mask"]).bit_count() for item in items)

    def search(mask: int, depth_left: int, path: list[dict[str, object]]) -> list[dict[str, object]] | None:
        if mask == full_mask:
            return path
        missing = full_mask ^ mask
        if math.ceil(missing.bit_count() / max_cover) > depth_left:
            return None
        missing_indices = [index for index in range(union_root_count) if missing & (1 << index)]
        root_index = min(
            missing_indices,
            key=lambda index: sum(1 for item in by_root[index] if int(item["mask"]) & ~mask),
        )
        candidates = [item for item in by_root[root_index] if int(item["mask"]) & ~mask]
        candidates.sort(
            key=lambda item: (
                -(int(item["mask"]) & ~mask).bit_count(),
                int(item["feature_count"]),
                str(item["context_family"]),
                str(item["context_key"]),
            )
        )
        seen_gain: set[int] = set()
        for item in candidates:
            item_mask = int(item["mask"])
            gain = item_mask & ~mask
            if gain in seen_gain:
                continue
            seen_gain.add(gain)
            result = search(mask | item_mask, depth_left - 1, path + [item])
            if result is not None:
                return result
        return None

    for limit in range(1, context_limit + 1):
        result = search(0, limit, [])
        if result is not None:
            return result
    return []


def build_selected_rows(selected: list[dict[str, object]]) -> tuple[list[dict[str, object]], set[str], dict[str, list[str]]]:
    covered: set[str] = set()
    contexts_by_root: dict[str, list[str]] = defaultdict(list)
    rows: list[dict[str, object]] = []
    for item in selected:
        roots = list(item["roots"])
        new_roots = [root for root in roots if root not in covered]
        for root in roots:
            contexts_by_root[root].append(f"{item['context_family']}={item['context_key']}")
        covered.update(roots)
        rows.append(
            {
                "rank": len(rows) + 1,
                "context_family": item["context_family"],
                "feature_count": item["feature_count"],
                "context_key": item["context_key"],
                "exact_roots": len(roots),
                "new_roots": len(new_roots),
                "covered_roots_after": len(covered),
                "sample_roots": ",".join(roots[:8]),
                "verdict": "selected_pure_context",
            }
        )
    return rows, covered, contexts_by_root


def build_root_rows(
    union_rows: dict[str, dict[str, str]],
    covered: set[str],
    contexts_by_root: dict[str, list[str]],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for root in sorted(union_rows, key=int):
        union = union_rows[root]
        prediction = union.get("prediction", "")
        target = union.get("target_low", "")
        rows.append(
            {
                "rank": len(rows) + 1,
                "root_slot_rank": root,
                "prediction": prediction,
                "target_low": target,
                "path": union.get("path", ""),
                "selected_contexts": "|".join(contexts_by_root.get(root, [])),
                "verdict": "correct" if root in covered and prediction == target else "missing_or_false",
            }
        )
    return rows


def csv_items(items: list[dict[str, object]]) -> list[dict[str, object]]:
    return [{field: item.get(field, "") for field in ITEM_FIELDNAMES} for item in items]


def build(
    slot_rows: list[dict[str, str]],
    source_terminal_rows: list[dict[str, str]],
    chains: list[dict[str, str]],
    union_roots: set[str],
    union_rows: dict[str, dict[str, str]],
    max_features: int,
    context_limit: int,
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    root_order = sorted(union_roots, key=int)
    root_index = {root: index for index, root in enumerate(root_order)}
    chain_rows = build_chain_inputs(slot_rows, source_terminal_rows, chains)
    items, raw_pure_contexts = generate_pure_items(chain_rows, union_roots, root_index, max_features)
    selected = find_cover(items, len(root_order), context_limit)
    selected_rows, covered, contexts_by_root = build_selected_rows(selected)
    root_rows = build_root_rows(union_rows, covered, contexts_by_root)
    missed_roots = len(union_roots - covered)
    issue_rows = sum(1 for row in root_rows if row["verdict"] != "correct")
    selected_families = "|".join(dict.fromkeys(str(row["context_family"]) for row in selected_rows))
    summary = {
        "scope": "total",
        "candidate_mode": "high_safe_low_exception_source_terminal_replay_union_guard_cover",
        "chain_rows": len(chain_rows),
        "union_roots": len(union_roots),
        "features": len(STABLE_GUARD_FEATURES),
        "max_features": max_features,
        "compact_context_limit": context_limit,
        "raw_pure_contexts": raw_pure_contexts,
        "candidate_rows": len(items),
        "selected_contexts": len(selected_rows),
        "covered_roots": len(covered),
        "missed_roots": missed_roots,
        "selected_families": selected_families,
        "promotion_candidate_bytes": len(covered) if missed_roots == 0 and len(selected_rows) <= context_limit else 0,
        "promotion_ready_bytes": 0,
        "issue_rows": issue_rows,
    }
    return summary, csv_items(items), selected_rows, root_rows


def render_table(rows: list[dict[str, object]], fields: list[str], limit: int = 220) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, object],
    items: list[dict[str, object]],
    selected: list[dict[str, object]],
    roots: list[dict[str, object]],
    title: str,
) -> str:
    data_json = json.dumps(
        {"summary": summary, "selected": selected, "roots": roots, "items": items[:220]},
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
Ce rapport cherche une couverture compacte de contextes purs. Chaque contexte
selectionne couvre seulement des racines de l'union, puis l'ensemble selectionne
doit couvrir toutes les racines avant promotion.
</p>
<div class="grid">
{''.join(f'<div class="box"><div class="muted">{html.escape(key)}</div><div class="num">{html.escape(str(value))}</div></div>' for key, value in summary.items())}
</div>
<h2>Contextes selectionnes</h2>
<div class="panel">{render_table(selected, SELECTED_FIELDNAMES)}</div>
<h2>Racines couvertes</h2>
<div class="panel">{render_table(roots, ROOT_FIELDNAMES)}</div>
<h2>Contextes purs candidats</h2>
<div class="panel">{render_table(items, ITEM_FIELDNAMES)}</div>
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
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    slot_rows = read_csv(args.slots)
    source_terminal_rows = read_csv(args.source_terminals)
    chains = read_csv(args.chains)
    union_roots = load_union_roots(args.union_roots)
    union_rows = read_union_rows(args.union_roots)
    summary, items, selected, roots = build(
        slot_rows,
        source_terminal_rows,
        chains,
        union_roots,
        union_rows,
        args.max_features,
        args.compact_context_limit,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "items.csv", ITEM_FIELDNAMES, items)
    write_csv(args.output / "selected.csv", SELECTED_FIELDNAMES, selected)
    write_csv(args.output / "roots.csv", ROOT_FIELDNAMES, roots)
    title = "Lands of Lore II .tex Source Terminal Replay Union Guard Cover Review"
    (args.output / "index.html").write_text(build_html(summary, items, selected, roots, title), encoding="utf-8")
    print(f"Candidate rows: {summary['candidate_rows']}")
    print(f"Selected contexts: {summary['selected_contexts']}")
    print(f"Covered roots: {summary['covered_roots']}/{summary['union_roots']}")
    print(f"Promotion candidate bytes: {summary['promotion_candidate_bytes']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
