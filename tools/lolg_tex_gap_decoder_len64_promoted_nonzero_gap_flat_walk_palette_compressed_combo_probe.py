#!/usr/bin/env python3
"""Probe combined compressed selectors for conflicted flat-walk palette values."""

from __future__ import annotations

import argparse
import html
import json
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_fill_selector_probe import read_csv
from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_flat_walk_palette_compressed_selector_probe import (
    DEFAULT_OUTPUT as DEFAULT_COMPRESSED_SELECTOR_OUTPUT,
    META_FEATURES,
    feature_values,
)
from lolg_tex_gap_opcode_probe import int_value, write_csv


DEFAULT_ROWS = DEFAULT_COMPRESSED_SELECTOR_OUTPUT / "rows.csv"
DEFAULT_OUTPUT = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_compressed_combo_probe"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "value_rows",
    "conflicted_value_rows",
    "tested_feature_sets",
    "selector_groups",
    "exact_transform_groups",
    "exact_pair_groups",
    "full_transform_cover_sets",
    "full_pair_cover_sets",
    "best_transform_feature_set",
    "best_transform_exact_conflicted_rows",
    "best_transform_multirow_conflicted_rows",
    "best_transform_singleton_conflicted_rows",
    "best_transform_groups",
    "best_pair_feature_set",
    "best_pair_exact_conflicted_rows",
    "best_pair_multirow_conflicted_rows",
    "best_pair_singleton_conflicted_rows",
    "best_pair_groups",
    "promotion_ready_bytes",
    "issue_rows",
]

FEATURE_SET_FIELDNAMES = [
    "rank",
    "feature_set",
    "size",
    "selector_groups",
    "covered_rows",
    "conflicted_rows",
    "exact_transform_groups",
    "exact_pair_groups",
    "exact_transform_conflicted_rows",
    "exact_pair_conflicted_rows",
    "multirow_transform_conflicted_rows",
    "multirow_pair_conflicted_rows",
    "singleton_transform_conflicted_rows",
    "singleton_pair_conflicted_rows",
    "full_transform_coverage",
    "full_pair_coverage",
    "best_transform_delta",
    "best_delta_pair",
    "sample_keys",
    "verdict",
]

GROUP_FIELDNAMES = [
    "feature_set",
    "key",
    "rows",
    "values",
    "conflicted_value_rows",
    "transform_deltas",
    "delta_pairs",
    "exact_transform_delta",
    "exact_delta_pair",
    "sample_value_hex",
    "verdict",
]


def compressed_feature_map(row: dict[str, str]) -> dict[str, str]:
    return {feature: key for feature, key in feature_values(row) if feature not in META_FEATURES and key != ""}


def feature_names(rows: list[dict[str, str]]) -> list[str]:
    return sorted({feature for row in rows for feature in compressed_feature_map(row)})


def counter_json(counter: Counter[str]) -> str:
    return json.dumps(dict(sorted(counter.items())), sort_keys=True)


def group_verdict(row_count: int, exact_transform: bool, exact_pair: bool) -> str:
    if row_count == 1:
        return "singleton_selector"
    if exact_pair:
        return "multirow_exact_pair_selector"
    if exact_transform:
        return "multirow_exact_transform_selector"
    return "mixed_selector"


def build_group_rows(
    rows: list[dict[str, str]],
    feature_maps: list[dict[str, str]],
    feature_set: tuple[str, ...],
) -> list[dict[str, object]]:
    groups: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row, row_features in zip(rows, feature_maps):
        if all(feature in row_features for feature in feature_set):
            groups[tuple(row_features[feature] for feature in feature_set)].append(row)

    output: list[dict[str, object]] = []
    feature_set_key = "+".join(feature_set)
    for key, group in groups.items():
        transform_counter = Counter(row.get("transform_delta", "") for row in group)
        pair_counter = Counter(row.get("delta_pair", "") for row in group)
        exact_transform = len(transform_counter) == 1
        exact_pair = len(pair_counter) == 1
        conflicted = [row for row in group if row.get("value_status") == "conflicted_multi_signature_value"]
        output.append(
            {
                "feature_set": feature_set_key,
                "key": "|".join(f"{feature}={value}" for feature, value in zip(feature_set, key)),
                "rows": len(group),
                "values": len({row.get("value_hex", "") for row in group}),
                "conflicted_value_rows": len(conflicted),
                "transform_deltas": counter_json(transform_counter),
                "delta_pairs": counter_json(pair_counter),
                "exact_transform_delta": next(iter(transform_counter)) if exact_transform else "",
                "exact_delta_pair": next(iter(pair_counter)) if exact_pair else "",
                "sample_value_hex": group[0].get("value_hex", ""),
                "verdict": group_verdict(len(group), exact_transform, exact_pair),
            }
        )
    output.sort(
        key=lambda row: (
            str(row.get("verdict", "")) != "multirow_exact_pair_selector",
            str(row.get("verdict", "")) != "multirow_exact_transform_selector",
            -int_value(row, "conflicted_value_rows"),
            -int_value(row, "rows"),
            str(row.get("key", "")),
        )
    )
    return output


def best_counter_value(counter: Counter[str]) -> str:
    if not counter:
        return ""
    value, count = max(counter.items(), key=lambda item: (item[1], item[0]))
    return f"{value}/{count}"


def summarize_feature_set(
    group_rows: list[dict[str, object]],
    conflicted_total: int,
    rank: int,
) -> dict[str, object]:
    transform_conflicted = 0
    pair_conflicted = 0
    multirow_transform_conflicted = 0
    multirow_pair_conflicted = 0
    singleton_transform_conflicted = 0
    singleton_pair_conflicted = 0
    transform_deltas: Counter[str] = Counter()
    delta_pairs: Counter[str] = Counter()
    covered_rows = sum(int_value(row, "rows") for row in group_rows)
    conflicted_rows = sum(int_value(row, "conflicted_value_rows") for row in group_rows)
    for row in group_rows:
        row_count = int_value(row, "rows")
        conflicted = int_value(row, "conflicted_value_rows")
        if row.get("exact_transform_delta"):
            transform_conflicted += conflicted
            transform_deltas[str(row.get("exact_transform_delta", ""))] += conflicted
            if row_count > 1:
                multirow_transform_conflicted += conflicted
            else:
                singleton_transform_conflicted += conflicted
        if row.get("exact_delta_pair"):
            pair_conflicted += conflicted
            delta_pairs[str(row.get("exact_delta_pair", ""))] += conflicted
            if row_count > 1:
                multirow_pair_conflicted += conflicted
            else:
                singleton_pair_conflicted += conflicted

    feature_set = str(group_rows[0].get("feature_set", "")) if group_rows else ""
    return {
        "rank": rank,
        "feature_set": feature_set,
        "size": len(feature_set.split("+")) if feature_set else 0,
        "selector_groups": len(group_rows),
        "covered_rows": covered_rows,
        "conflicted_rows": conflicted_rows,
        "exact_transform_groups": sum(1 for row in group_rows if row.get("exact_transform_delta")),
        "exact_pair_groups": sum(1 for row in group_rows if row.get("exact_delta_pair")),
        "exact_transform_conflicted_rows": transform_conflicted,
        "exact_pair_conflicted_rows": pair_conflicted,
        "multirow_transform_conflicted_rows": multirow_transform_conflicted,
        "multirow_pair_conflicted_rows": multirow_pair_conflicted,
        "singleton_transform_conflicted_rows": singleton_transform_conflicted,
        "singleton_pair_conflicted_rows": singleton_pair_conflicted,
        "full_transform_coverage": int(transform_conflicted == conflicted_total and conflicted_total > 0),
        "full_pair_coverage": int(pair_conflicted == conflicted_total and conflicted_total > 0),
        "best_transform_delta": best_counter_value(transform_deltas),
        "best_delta_pair": best_counter_value(delta_pairs),
        "sample_keys": " ; ".join(str(row.get("key", "")) for row in group_rows[:4]),
        "verdict": verdict_for_feature_set(
            transform_conflicted,
            pair_conflicted,
            multirow_transform_conflicted,
            multirow_pair_conflicted,
            singleton_pair_conflicted,
            conflicted_total,
        ),
    }


def verdict_for_feature_set(
    transform_conflicted: int,
    pair_conflicted: int,
    multirow_transform_conflicted: int,
    multirow_pair_conflicted: int,
    singleton_pair_conflicted: int,
    conflicted_total: int,
) -> str:
    if pair_conflicted == conflicted_total and singleton_pair_conflicted == 0 and conflicted_total > 0:
        return "full_pair_selector_review"
    if pair_conflicted == conflicted_total and conflicted_total > 0:
        return "full_pair_singleton_heavy_review"
    if transform_conflicted == conflicted_total and multirow_transform_conflicted > 0 and conflicted_total > 0:
        return "full_transform_selector_review"
    if pair_conflicted > 0 or multirow_pair_conflicted > 0:
        return "partial_pair_selector_review"
    if transform_conflicted > 0:
        return "partial_transform_selector_review"
    return "weak_selector"


def best_feature_set(feature_sets: list[dict[str, object]], prefix: str) -> dict[str, object]:
    exact_field = f"exact_{prefix}_conflicted_rows"
    multirow_field = f"multirow_{prefix}_conflicted_rows"
    singleton_field = f"singleton_{prefix}_conflicted_rows"
    return max(
        feature_sets,
        key=lambda row: (
            int_value(row, exact_field),
            int_value(row, multirow_field),
            -int_value(row, singleton_field),
            -int_value(row, "size"),
            -int_value(row, "selector_groups"),
            str(row.get("feature_set", "")),
        ),
        default={},
    )


def build_feature_set_rows(
    rows: list[dict[str, str]],
    max_size: int,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    feature_maps = [compressed_feature_map(row) for row in rows]
    features = feature_names(rows)
    conflicted_total = sum(1 for row in rows if row.get("value_status") == "conflicted_multi_signature_value")
    feature_set_rows: list[dict[str, object]] = []
    all_group_rows: list[dict[str, object]] = []
    rank = 1
    for size in range(1, max_size + 1):
        for feature_set in combinations(features, size):
            group_rows = build_group_rows(rows, feature_maps, feature_set)
            if not group_rows:
                continue
            feature_set_rows.append(summarize_feature_set(group_rows, conflicted_total, rank))
            all_group_rows.extend(group_rows)
            rank += 1

    feature_set_rows.sort(
        key=lambda row: (
            -int_value(row, "exact_pair_conflicted_rows"),
            -int_value(row, "multirow_pair_conflicted_rows"),
            int_value(row, "singleton_pair_conflicted_rows"),
            -int_value(row, "exact_transform_conflicted_rows"),
            -int_value(row, "multirow_transform_conflicted_rows"),
            int_value(row, "size"),
            int_value(row, "selector_groups"),
            str(row.get("feature_set", "")),
        )
    )
    for index, row in enumerate(feature_set_rows, start=1):
        row["rank"] = index
    all_group_rows.sort(
        key=lambda row: (
            str(row.get("verdict", "")) != "multirow_exact_pair_selector",
            str(row.get("verdict", "")) != "multirow_exact_transform_selector",
            -int_value(row, "conflicted_value_rows"),
            -int_value(row, "rows"),
            str(row.get("feature_set", "")),
            str(row.get("key", "")),
        )
    )
    return feature_set_rows, all_group_rows


def build_summary(
    rows: list[dict[str, str]],
    feature_set_rows: list[dict[str, object]],
    group_rows: list[dict[str, object]],
) -> dict[str, object]:
    best_transform = best_feature_set(feature_set_rows, "transform")
    best_pair = best_feature_set(feature_set_rows, "pair")
    return {
        "scope": "total",
        "value_rows": len(rows),
        "conflicted_value_rows": sum(
            1 for row in rows if row.get("value_status") == "conflicted_multi_signature_value"
        ),
        "tested_feature_sets": len(feature_set_rows),
        "selector_groups": len(group_rows),
        "exact_transform_groups": sum(1 for row in group_rows if row.get("exact_transform_delta")),
        "exact_pair_groups": sum(1 for row in group_rows if row.get("exact_delta_pair")),
        "full_transform_cover_sets": sum(int_value(row, "full_transform_coverage") for row in feature_set_rows),
        "full_pair_cover_sets": sum(int_value(row, "full_pair_coverage") for row in feature_set_rows),
        "best_transform_feature_set": best_transform.get("feature_set", ""),
        "best_transform_exact_conflicted_rows": best_transform.get("exact_transform_conflicted_rows", 0),
        "best_transform_multirow_conflicted_rows": best_transform.get("multirow_transform_conflicted_rows", 0),
        "best_transform_singleton_conflicted_rows": best_transform.get("singleton_transform_conflicted_rows", 0),
        "best_transform_groups": best_transform.get("selector_groups", 0),
        "best_pair_feature_set": best_pair.get("feature_set", ""),
        "best_pair_exact_conflicted_rows": best_pair.get("exact_pair_conflicted_rows", 0),
        "best_pair_multirow_conflicted_rows": best_pair.get("multirow_pair_conflicted_rows", 0),
        "best_pair_singleton_conflicted_rows": best_pair.get("singleton_pair_conflicted_rows", 0),
        "best_pair_groups": best_pair.get("selector_groups", 0),
        "promotion_ready_bytes": 0,
        "issue_rows": 0,
    }


def render_table(rows: list[dict[str, object]], fields: list[str], limit: int = 240) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, object],
    feature_set_rows: list[dict[str, object]],
    group_rows: list[dict[str, object]],
    title: str,
) -> str:
    data_json = json.dumps(
        {"summary": summary, "feature_sets": feature_set_rows, "groups": group_rows},
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
table {{ border-collapse: collapse; width: 100%; min-width: 1500px; }}
th, td {{ border: 1px solid #31424a; padding: .45rem .55rem; vertical-align: top; }}
th {{ color: #9dafb5; background: #172023; text-align: left; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: .75rem; margin: 1rem 0; }}
.box {{ border: 1px solid #31424a; background: #172023; padding: .75rem; }}
.num {{ font-size: 1.35rem; font-weight: 750; }}
.muted {{ color: #9dafb5; }}
.panel {{ overflow-x: auto; margin-top: 1rem; }}
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<div class="grid">
  <div class="box"><div class="num">{summary['conflicted_value_rows']}</div><div class="muted">conflicted rows</div></div>
  <div class="box"><div class="num">{summary['tested_feature_sets']}</div><div class="muted">tested feature sets</div></div>
  <div class="box"><div class="num">{summary['full_transform_cover_sets']}</div><div class="muted">full transform cover sets</div></div>
  <div class="box"><div class="num">{summary['full_pair_cover_sets']}</div><div class="muted">full pair cover sets</div></div>
  <div class="box"><div class="num">{summary['best_pair_multirow_conflicted_rows']}</div><div class="muted">best pair multirow conflicts</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Feature sets</h2>{render_table(feature_set_rows, FEATURE_SET_FIELDNAMES)}</div>
<div class="panel"><h2>Groups</h2>{render_table(group_rows, GROUP_FIELDNAMES)}</div>
<script type="application/json" id="flat-walk-palette-compressed-combo-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe combined compressed selectors for flat-walk palette values.")
    parser.add_argument("--rows", type=Path, default=DEFAULT_ROWS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-size", type=int, default=3)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Flat Walk Palette Compressed Combo Probe",
    )
    args = parser.parse_args()

    rows = read_csv(args.rows)
    feature_set_rows, group_rows = build_feature_set_rows(rows, max(1, args.max_size))
    summary = build_summary(rows, feature_set_rows, group_rows)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "feature_sets.csv", FEATURE_SET_FIELDNAMES, feature_set_rows)
    write_csv(args.output / "groups.csv", GROUP_FIELDNAMES, group_rows)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, feature_set_rows, group_rows, args.title))

    print(f"Conflicted value rows: {summary['conflicted_value_rows']}")
    print(
        f"Best transform feature set: {summary['best_transform_feature_set']} "
        f"{summary['best_transform_exact_conflicted_rows']} conflicted rows"
    )
    print(
        f"Best pair feature set: {summary['best_pair_feature_set']} "
        f"{summary['best_pair_exact_conflicted_rows']} conflicted rows "
        f"({summary['best_pair_singleton_conflicted_rows']} singleton)"
    )
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
