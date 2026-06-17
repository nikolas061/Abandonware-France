#!/usr/bin/env python3
"""Probe row/corpus low/full bytes after sequence high-safe source-profile selection."""

from __future__ import annotations

import argparse
import csv
import html
import itertools
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_opcode_probe import write_csv
from lolg_tex_gradient_sequence_high_safe_low_probe import (
    RULE_FIELDNAMES,
    int_value,
    ratio,
    render_table,
)
from lolg_tex_gradient_sequence_high_safe_source_profile_low_probe import (
    SEQUENCE_FEATURES,
    SLOT_FIELDNAMES as SOURCE_PROFILE_SLOT_FIELDNAMES,
    SOURCE_FEATURES,
)


DEFAULT_SLOTS = Path("output/tex_gradient_sequence_high_safe_source_profile_low/slots.csv")
DEFAULT_OUTPUT = Path("output/tex_gradient_sequence_high_safe_row_corpus_low")
IMAGE_WIDTH = 320

ROW_CORPUS_FEATURES = [
    "target_mod16",
    "target_mod32",
    "target_mod64",
    "target_x_mod16",
    "target_x_mod32",
    "target_y_mod4",
    "target_y_mod8",
    "target_y_mod16",
    "target_y_band8",
    "row_quarter",
    "row_half",
    "row_third",
    "row_edge8",
    "start_mod16",
    "start_mod32",
    "start_mod64",
    "end_mod16",
    "length_mod16",
    "length_band32",
    "shape_len_key",
    "shape_start_key",
    "archive_key",
    "file_key",
    "source_target_delta_mod16",
    "source_target_delta_mod32",
]

FOCUSED_4_ROW_FEATURES = [
    "row_quarter",
    "row_third",
    "row_half",
    "end_mod16",
    "length_mod16",
    "source_target_delta_mod32",
    "source_target_delta_mod16",
    "target_mod64",
    "target_x_mod32",
    "start_mod64",
    "shape_len_key",
    "shape_start_key",
]

FOCUSED_4_STATE_FEATURES = [
    "rel_mod4",
    "rel_mod8",
    "rel_mod16",
    "x_mod8",
    "src_rel_mod4",
    "src_rel_mod8",
    "source_low",
    "source_high",
    "source_byte",
    "offset_delta_bucket",
    "prev_known_byte",
    "prev_gap_bucket",
    "next_known_byte",
    "next_gap_bucket",
    "unknown_before_mod16",
    "prefix_sum_mod16",
    "predicted_high",
    "high_context",
]

OBSERVED_FOCUSED_SEEDS = [
    ("rel_mod4", "x_mod8", "row_quarter"),
    ("x_mod8", "src_rel_mod4", "row_quarter"),
    ("end_mod16", "source_target_delta_mod32"),
    ("rel_mod4", "x_mod8", "source_low"),
    ("rel_mod8", "row_quarter", "row_third"),
]

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "source_profile_slots",
    "row_corpus_slots",
    "row_corpus_rows",
    "feature_sets",
    "row_corpus_features",
    "full_false_free_sets",
    "full_best_false_free_slots",
    "full_best_exact_slots",
    "full_best_false_slots",
    "full_best_feature_set",
    "full_low_false_exact_slots",
    "full_low_false_false_slots",
    "full_low_false_feature_set",
    "target_low_false_free_sets",
    "target_low_best_false_free_slots",
    "target_low_best_exact_slots",
    "target_low_best_false_slots",
    "target_low_best_feature_set",
    "target_low_low_false_exact_slots",
    "target_low_low_false_false_slots",
    "target_low_low_false_feature_set",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

SLOT_FIELDNAMES = [*SOURCE_PROFILE_SLOT_FIELDNAMES, *ROW_CORPUS_FEATURES]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def band(value: int, step: int) -> str:
    base = (value // step) * step
    return f"{base}-{base + step - 1}"


def enriched_slot(slot: dict[str, str]) -> dict[str, object]:
    output: dict[str, object] = dict(slot)
    target_offset = int_value(slot, "target_offset")
    start = int_value(slot, "start")
    end = int_value(slot, "end")
    relative_offset = int_value(slot, "relative_offset")
    source_offset = int_value(slot, "source_profile_offset", -1)
    length = max(0, end - start)
    x = target_offset % IMAGE_WIDTH
    y = target_offset // IMAGE_WIDTH
    row_quarter = (relative_offset * 4) // length if length else 0
    row_half = (relative_offset * 2) // length if length else 0
    row_third = (relative_offset * 3) // length if length else 0
    if relative_offset < 8:
        row_edge8 = "front"
    elif end - target_offset <= 8:
        row_edge8 = "tail"
    else:
        row_edge8 = "mid"

    output.update(
        {
            "target_mod16": target_offset % 16,
            "target_mod32": target_offset % 32,
            "target_mod64": target_offset % 64,
            "target_x_mod16": x % 16,
            "target_x_mod32": x % 32,
            "target_y_mod4": y % 4,
            "target_y_mod8": y % 8,
            "target_y_mod16": y % 16,
            "target_y_band8": band(y, 8),
            "row_quarter": row_quarter,
            "row_half": row_half,
            "row_third": row_third,
            "row_edge8": row_edge8,
            "start_mod16": start % 16,
            "start_mod32": start % 32,
            "start_mod64": start % 64,
            "end_mod16": end % 16,
            "length_mod16": length % 16,
            "length_band32": band(length, 32),
            "shape_len_key": f"{slot.get('gradient_class', '')}|{slot.get('top_nibble', '')}|{length // 8}",
            "shape_start_key": (
                f"{slot.get('gradient_class', '')}|{slot.get('top_nibble', '')}|"
                f"{start % 64}|{length // 8}"
            ),
            "archive_key": slot.get("archive", ""),
            "file_key": f"{slot.get('archive', '')}|{slot.get('pcx_name', '')}",
            "source_target_delta_mod16": (
                (target_offset - source_offset) % 16 if source_offset >= 0 else "none"
            ),
            "source_target_delta_mod32": (
                (target_offset - source_offset) % 32 if source_offset >= 0 else "none"
            ),
        }
    )
    return output


def enrich_slots(slots: list[dict[str, str]]) -> list[dict[str, object]]:
    enriched = [enriched_slot(slot) for slot in slots]
    enriched.sort(
        key=lambda row: (
            str(row.get("row_id", "")),
            int_value(row, "target_offset"),
        )
    )
    for index, row in enumerate(enriched, start=1):
        row["rank"] = index
    return enriched


def candidate_feature_sets(max_features: int) -> list[tuple[str, ...]]:
    base_features = [*SEQUENCE_FEATURES, *SOURCE_FEATURES]
    features = [*base_features, *ROW_CORPUS_FEATURES]
    output: list[tuple[str, ...]] = []
    generated_max = min(max_features, 3)
    for size in range(1, generated_max + 1):
        output.extend(itertools.combinations(features, size))
    if max_features >= 4:
        for row_size in (1, 2):
            for row_part in itertools.combinations(FOCUSED_4_ROW_FEATURES, row_size):
                for state_part in itertools.combinations(FOCUSED_4_STATE_FEATURES, 4 - row_size):
                    output.append((*state_part, *row_part))
        seed_pool = [*FOCUSED_4_STATE_FEATURES, *FOCUSED_4_ROW_FEATURES]
        for seed in OBSERVED_FOCUSED_SEEDS:
            for feature in seed_pool:
                combo = tuple(dict.fromkeys((*seed, feature)))
                if len(combo) == 4:
                    output.append(combo)

    seen: set[tuple[str, ...]] = set()
    unique: list[tuple[str, ...]] = []
    for feature_set in output:
        if feature_set in seen:
            continue
        seen.add(feature_set)
        unique.append(feature_set)
    return unique


def context_for(slot: dict[str, object], features: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(str(slot.get(feature, "")) for feature in features)


def target_field(target_kind: str) -> str:
    if target_kind == "full":
        return "target_byte"
    if target_kind == "target_low":
        return "target_low"
    raise ValueError(target_kind)


def evaluate_rule(
    slots: list[dict[str, object]], features: tuple[str, ...], target_kind: str
) -> dict[str, object]:
    field = target_field(target_kind)
    groups: dict[tuple[str, ...], list[dict[str, object]]] = defaultdict(list)
    for slot in slots:
        groups[context_for(slot, features)].append(slot)

    exact = 0
    false = 0
    predicted = 0
    predicted_groups: set[tuple[str, ...]] = set()
    predicted_rows: set[str] = set()
    samples: list[str] = []
    for context, group in groups.items():
        total_counts = Counter(str(slot.get(field, "")) for slot in group)
        by_row: dict[str, Counter[str]] = defaultdict(Counter)
        for slot in group:
            by_row[str(slot.get("row_id", ""))][str(slot.get(field, ""))] += 1
        peer_value_by_row: dict[str, str] = {}
        for row_id, counts in by_row.items():
            peer_counts = total_counts.copy()
            peer_counts.subtract(counts)
            peer_counts = Counter({value: count for value, count in peer_counts.items() if count > 0})
            if len(peer_counts) == 1:
                peer_value_by_row[row_id] = next(iter(peer_counts))
        for slot in group:
            row_id = str(slot.get("row_id", ""))
            value = peer_value_by_row.get(row_id)
            if value is None:
                continue
            predicted += 1
            predicted_groups.add(context)
            predicted_rows.add(row_id)
            if value == str(slot.get(field, "")):
                exact += 1
            else:
                false += 1
            if len(samples) < 8:
                samples.append(f"{'|'.join(context)}:v={value}")

    false_free = predicted > 0 and false == 0
    return {
        "rank": 0,
        "target_kind": target_kind,
        "feature_set": "+".join(features),
        "feature_count": len(features),
        "predicted_slots": predicted,
        "exact_slots": exact,
        "false_slots": false,
        "precision": ratio(exact, predicted),
        "groups": len(groups),
        "predicted_groups": len(predicted_groups),
        "predicted_rows": len(predicted_rows),
        "false_free": 1 if false_free else 0,
        "sample_predictions": "|".join(samples),
        "verdict": (
            f"{target_kind}_row_corpus_false_free"
            if false_free
            else f"{target_kind}_row_corpus_noisy"
            if predicted
            else f"{target_kind}_row_corpus_no_predictions"
        ),
    }


def build_rules(
    slots: list[dict[str, object]],
    *,
    max_features: int,
) -> list[dict[str, object]]:
    rules: list[dict[str, object]] = []
    for target_kind in ("full", "target_low"):
        for features in candidate_feature_sets(max_features):
            rule = evaluate_rule(slots, features, target_kind)
            if int_value(rule, "predicted_slots") > 0:
                rules.append(rule)
    rules.sort(
        key=lambda row: (
            str(row["target_kind"]),
            -int_value(row, "false_free"),
            -int_value(row, "exact_slots"),
            int_value(row, "false_slots"),
            int_value(row, "feature_count"),
            str(row["feature_set"]),
        )
    )
    for index, row in enumerate(rules, start=1):
        row["rank"] = index
    return rules


def best_rule(rules: list[dict[str, object]], target_kind: str) -> dict[str, object]:
    candidates = [row for row in rules if row.get("target_kind") == target_kind]
    return max(
        candidates,
        key=lambda row: (
            int_value(row, "exact_slots"),
            -int_value(row, "false_slots"),
            -int_value(row, "feature_count"),
            str(row.get("feature_set", "")),
        ),
        default={},
    )


def best_false_free_rule(rules: list[dict[str, object]], target_kind: str) -> dict[str, object]:
    candidates = [
        row
        for row in rules
        if row.get("target_kind") == target_kind and int_value(row, "false_free") > 0
    ]
    return max(
        candidates,
        key=lambda row: (
            int_value(row, "exact_slots"),
            -int_value(row, "feature_count"),
            str(row.get("feature_set", "")),
        ),
        default={},
    )


def best_low_false_rule(
    rules: list[dict[str, object]], target_kind: str, max_false: int = 5
) -> dict[str, object]:
    candidates = [
        row
        for row in rules
        if row.get("target_kind") == target_kind
        and 0 <= int_value(row, "false_slots") <= max_false
        and int_value(row, "exact_slots") >= 10
    ]
    return max(
        candidates,
        key=lambda row: (
            int_value(row, "exact_slots"),
            -int_value(row, "false_slots"),
            -int_value(row, "feature_count"),
            str(row.get("feature_set", "")),
        ),
        default={},
    )


def false_free_count(rules: list[dict[str, object]], target_kind: str) -> int:
    return sum(
        1
        for row in rules
        if row.get("target_kind") == target_kind and int_value(row, "false_free") > 0
    )


def build(
    source_profile_slots: list[dict[str, str]],
    *,
    max_features: int,
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    slots = enrich_slots(source_profile_slots)
    feature_sets = candidate_feature_sets(max_features)
    rules = build_rules(slots, max_features=max_features)
    full_best = best_rule(rules, "full")
    full_false_free = best_false_free_rule(rules, "full")
    full_low_false = best_low_false_rule(rules, "full")
    low_best = best_rule(rules, "target_low")
    low_false_free = best_false_free_rule(rules, "target_low")
    low_low_false = best_low_false_rule(rules, "target_low")
    summary = {
        "scope": "total",
        "candidate_mode": "row_corpus_focused",
        "source_profile_slots": len(source_profile_slots),
        "row_corpus_slots": len(slots),
        "row_corpus_rows": len({row.get("row_id", "") for row in slots}),
        "feature_sets": len(feature_sets),
        "row_corpus_features": len(ROW_CORPUS_FEATURES),
        "full_false_free_sets": false_free_count(rules, "full"),
        "full_best_false_free_slots": full_false_free.get("exact_slots", 0),
        "full_best_exact_slots": full_best.get("exact_slots", 0),
        "full_best_false_slots": full_best.get("false_slots", 0),
        "full_best_feature_set": full_best.get("feature_set", ""),
        "full_low_false_exact_slots": full_low_false.get("exact_slots", 0),
        "full_low_false_false_slots": full_low_false.get("false_slots", 0),
        "full_low_false_feature_set": full_low_false.get("feature_set", ""),
        "target_low_false_free_sets": false_free_count(rules, "target_low"),
        "target_low_best_false_free_slots": low_false_free.get("exact_slots", 0),
        "target_low_best_exact_slots": low_best.get("exact_slots", 0),
        "target_low_best_false_slots": low_best.get("false_slots", 0),
        "target_low_best_feature_set": low_best.get("feature_set", ""),
        "target_low_low_false_exact_slots": low_low_false.get("exact_slots", 0),
        "target_low_low_false_false_slots": low_low_false.get("false_slots", 0),
        "target_low_low_false_feature_set": low_low_false.get("feature_set", ""),
        "promotion_candidate_bytes": 0,
        "promotion_ready_bytes": 0,
        "issue_rows": 0,
    }
    return summary, slots, rules


def build_html(
    summary: dict[str, object],
    slots: list[dict[str, object]],
    rules: list[dict[str, object]],
    title: str,
) -> str:
    top_rules = sorted(
        rules,
        key=lambda row: (
            str(row["target_kind"]),
            -int_value(row, "false_free"),
            -int_value(row, "exact_slots"),
            int_value(row, "false_slots"),
            int_value(row, "feature_count"),
        ),
    )[:220]
    data_json = json.dumps({"summary": summary, "rules": rules, "slots": slots}, indent=2, sort_keys=True)
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
  <div class="box"><div class="num">{summary['row_corpus_slots']}</div><div class="muted">row/corpus slots</div></div>
  <div class="box"><div class="num">{summary['full_best_false_free_slots']}</div><div class="muted">full false-free slots</div></div>
  <div class="box"><div class="num">{summary['target_low_best_false_free_slots']}</div><div class="muted">target-low false-free slots</div></div>
  <div class="box"><div class="num">{summary['target_low_low_false_exact_slots']}/{summary['target_low_low_false_false_slots']}</div><div class="muted">best near-low exact/false</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Rules</h2>{render_table(top_rules, RULE_FIELDNAMES)}</div>
<div class="panel"><h2>Row/corpus slots</h2>{render_table(slots, SLOT_FIELDNAMES)}</div>
<script type="application/json" id="gradient-sequence-high-safe-row-corpus-low-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Probe row/corpus low/full after sequence high-safe source-profile selection."
    )
    parser.add_argument("--slots", type=Path, default=DEFAULT_SLOTS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-features", type=int, default=4)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Gradient Sequence High-Safe Row-Corpus Low Probe",
    )
    args = parser.parse_args()

    summary, slots, rules = build(read_csv(args.slots), max_features=args.max_features)
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "slots.csv", SLOT_FIELDNAMES, slots)
    write_csv(args.output / "rules.csv", RULE_FIELDNAMES, rules)
    (args.output / "index.html").write_text(build_html(summary, slots, rules, args.title))

    print(f"Row/corpus slots: {summary['row_corpus_slots']}")
    print(f"Feature sets: {summary['feature_sets']}")
    print(f"Full false-free slots: {summary['full_best_false_free_slots']}")
    print(
        "Best full rule: "
        f"{summary['full_best_exact_slots']} exact / {summary['full_best_false_slots']} false"
    )
    print(f"Target-low false-free slots: {summary['target_low_best_false_free_slots']}")
    print(
        "Best target-low rule: "
        f"{summary['target_low_best_exact_slots']} exact / {summary['target_low_best_false_slots']} false"
    )
    print(
        "Best near-low rule: "
        f"{summary['target_low_low_false_exact_slots']} exact / "
        f"{summary['target_low_low_false_false_slots']} false"
    )
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
