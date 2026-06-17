#!/usr/bin/env python3
"""Probe external-source combo predictors for dominant mixed-value payload slots."""

from __future__ import annotations

import argparse
import csv
import html
import itertools
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_micro_mixed_value_payload_predictor_probe import (
    DEFAULT_FIXTURES,
    DEFAULT_INPUT_ROWS,
    build_entries,
    build_payloads,
    int_value,
    ratio,
    read_csv,
    strict_prediction,
    write_csv,
)
from lolg_tex_micro_mixed_value_payload_source_profile_probe import (
    DEFAULT_OUTPUT as DEFAULT_SOURCE_PROFILE_OUTPUT,
    DEFAULT_REPLAY_FIXTURES,
    fixture_key,
    load_sources,
)


DEFAULT_SOURCE_PROFILE_ROWS = DEFAULT_SOURCE_PROFILE_OUTPUT / "rows.csv"
DEFAULT_OUTPUT = Path("output/tex_micro_mixed_value_payload_external_source_combo")

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "target_bytes",
    "source_rows",
    "features",
    "feature_sets",
    "candidate_rows",
    "false_free_byte_sets",
    "best_false_free_byte_feature_set",
    "best_false_free_byte_slots",
    "best_false_free_byte_unknown_slots",
    "false_free_high_sets",
    "best_false_free_high_feature_set",
    "best_false_free_high_slots",
    "best_false_free_high_unknown_slots",
    "best_byte_feature_set",
    "best_byte_correct_slots",
    "best_byte_false_slots",
    "best_byte_precision",
    "best_high_feature_set",
    "best_high_correct_slots",
    "best_high_false_slots",
    "best_high_precision",
    "best_band_feature_set",
    "best_band_correct_slots",
    "best_band_false_slots",
    "best_band_precision",
    "promotion_ready_bytes",
    "issue_rows",
]

CANDIDATE_FIELDNAMES = [
    "rank",
    "target_kind",
    "feature_set",
    "feature_count",
    "contexts",
    "repeated_slots",
    "conflicted_slots",
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

SOURCE_PREFIXES = ("best", "compressed", "profile")
SHIFTS = (-2, -1, 0, 1, 2)


def source_profile_key(row: dict[str, str]) -> tuple[str, str, str, str, str, str, str]:
    return (
        row.get("archive", ""),
        row.get("pcx_name", ""),
        row.get("frontier_id", ""),
        row.get("span_index", ""),
        row.get("op_index", ""),
        row.get("start", ""),
        row.get("end", ""),
    )


def byte_token(data: bytes, index: int) -> str:
    if 0 <= index < len(data):
        return f"{data[index]:02x}"
    return "NA"


def high_token(data: bytes, index: int) -> str:
    if 0 <= index < len(data):
        return f"{data[index] >> 4:x}"
    return "NA"


def low_token(data: bytes, index: int) -> str:
    if 0 <= index < len(data):
        return f"{data[index] & 0x0F:x}"
    return "NA"


def delta_token(data: bytes, index: int) -> str:
    if 1 <= index < len(data):
        delta = ((data[index] - data[index - 1] + 128) & 0xFF) - 128
        if delta == 0:
            return "0"
        magnitude = abs(delta)
        suffix = "s" if magnitude <= 4 else "m" if magnitude <= 31 else "j"
        return ("+" if delta > 0 else "-") + suffix
    return "NA"


def add_external_features(
    entries: list[dict[str, object]],
    input_rows: list[dict[str, str]],
    profile_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    replay_rows: list[dict[str, str]],
) -> list[str]:
    profiles = {source_profile_key(row): row for row in profile_rows}
    sources, issues = load_sources(fixture_rows, replay_rows)
    for entry in entries:
        source_row = input_rows[int(entry["row_index"])]
        profile = profiles.get(source_profile_key(source_row), {})
        pools = sources.get(fixture_key(source_row), {})
        for prefix, pool_field, offset_field in (
            ("best", "best_pool", "best_offset"),
            ("compressed", "compressed_best_pool", "compressed_best_offset"),
            ("profile", "profile_best_pool", "profile_best_offset"),
        ):
            pool_name = profile.get(pool_field, "")
            source = pools.get(pool_name, b"")
            source_offset = int_value(profile, offset_field)
            entry[f"{prefix}_pool"] = pool_name or "NA"
            for shift in SHIFTS:
                index = source_offset + int(entry["offset"]) + shift
                entry[f"{prefix}_b{shift}"] = byte_token(source, index)
                entry[f"{prefix}_h{shift}"] = high_token(source, index)
                entry[f"{prefix}_l{shift}"] = low_token(source, index)
                entry[f"{prefix}_d{shift}"] = delta_token(source, index)
    return issues


def feature_names() -> list[str]:
    names: list[str] = []
    for prefix in SOURCE_PREFIXES:
        names.append(f"{prefix}_pool")
        for shift in SHIFTS:
            names.extend(
                [
                    f"{prefix}_b{shift}",
                    f"{prefix}_h{shift}",
                    f"{prefix}_l{shift}",
                    f"{prefix}_d{shift}",
                ]
            )
    names.extend(["pos16", "pos8", "prev1"])
    return names


def feature_combinations(features: list[str], max_features: int) -> list[tuple[str, ...]]:
    output: list[tuple[str, ...]] = []
    for size in range(1, max_features + 1):
        output.extend(itertools.combinations(features, size))
    return output


def evaluate_combo(
    entries: list[dict[str, object]],
    target_kind: str,
    feature_set: tuple[str, ...],
) -> dict[str, object]:
    all_counts: dict[tuple[object, ...], Counter[str]] = defaultdict(Counter)
    row_counts: dict[tuple[int, tuple[object, ...]], Counter[str]] = defaultdict(Counter)
    grouped_slots: dict[tuple[object, ...], int] = defaultdict(int)
    for entry in entries:
        context = tuple(entry[feature] for feature in feature_set)
        value = str(entry[target_kind])
        all_counts[context][value] += 1
        row_counts[(int(entry["row_index"]), context)][value] += 1
        grouped_slots[context] += 1

    repeated_slots = sum(count for count in grouped_slots.values() if count > 1)
    conflicted_slots = sum(
        grouped_slots[context]
        for context, counts in all_counts.items()
        if len([value for value, count in counts.items() if count]) > 1
    )
    predicted_values: Counter[str] = Counter()
    for context, counts in all_counts.items():
        prediction = strict_prediction(counts)
        if prediction is not None:
            predicted_values[prediction] += grouped_slots[context]

    correct = 0
    false = 0
    unknown = 0
    sample_context = ""
    sample_prediction = ""
    for entry in entries:
        context = tuple(entry[feature] for feature in feature_set)
        train_counts = all_counts[context].copy()
        train_counts.subtract(row_counts[(int(entry["row_index"]), context)])
        train_counts += Counter()
        prediction = strict_prediction(train_counts)
        if prediction is None:
            unknown += 1
            continue
        if not sample_context:
            sample_context = "|".join(str(part) for part in context)
            sample_prediction = prediction
        if prediction == str(entry[target_kind]):
            correct += 1
        else:
            false += 1

    predicted = correct + false
    if predicted == 0:
        verdict = "no_cross_row_prediction"
    elif false == 0 and target_kind == "byte":
        verdict = "false_free_byte_review"
    elif false == 0:
        verdict = "false_free_nibble_review"
    elif target_kind == "byte" and false >= correct:
        verdict = "byte_source_combo_reject"
    elif correct > false:
        verdict = "partial_source_hint"
    else:
        verdict = "conflicted_source_combo"

    return {
        "rank": 0,
        "target_kind": target_kind,
        "feature_set": "+".join(feature_set),
        "feature_count": len(feature_set),
        "contexts": len(all_counts),
        "repeated_slots": repeated_slots,
        "conflicted_slots": conflicted_slots,
        "loo_correct_slots": correct,
        "loo_false_slots": false,
        "loo_unknown_slots": unknown,
        "loo_precision": ratio(correct, predicted),
        "loo_coverage": ratio(predicted, len(entries)),
        "predicted_values": "|".join(f"{value}:{count}" for value, count in predicted_values.most_common(8)),
        "verdict": verdict,
        "sample_context": sample_context,
        "sample_prediction": sample_prediction,
    }


def best_candidate(rows: list[dict[str, object]], target_kind: str) -> dict[str, object]:
    candidates = [
        row
        for row in rows
        if row.get("target_kind") == target_kind
        and int_value(row, "loo_correct_slots") + int_value(row, "loo_false_slots") > 0
    ]
    if not candidates:
        return {}
    candidates.sort(
        key=lambda row: (
            int_value(row, "loo_correct_slots"),
            -int_value(row, "loo_false_slots"),
            float(row.get("loo_precision", "0") or 0),
            -int_value(row, "feature_count"),
        ),
        reverse=True,
    )
    return candidates[0]


def best_false_free(rows: list[dict[str, object]], target_kind: str) -> dict[str, object]:
    candidates = [
        row
        for row in rows
        if row.get("target_kind") == target_kind
        and int_value(row, "loo_correct_slots") > 0
        and int_value(row, "loo_false_slots") == 0
    ]
    if not candidates:
        return {}
    candidates.sort(key=lambda row: (int_value(row, "loo_correct_slots"), -int_value(row, "feature_count")), reverse=True)
    return candidates[0]


def build(
    input_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    replay_rows: list[dict[str, str]],
    profile_rows: list[dict[str, str]],
    *,
    max_features: int,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    payloads, issues = build_payloads(input_rows, fixture_rows)
    entries = build_entries(payloads)
    issues.extend(add_external_features(entries, input_rows, profile_rows, fixture_rows, replay_rows))
    features = feature_names()
    combos = feature_combinations(features, max_features)
    candidate_rows = [
        evaluate_combo(entries, target_kind, combo)
        for target_kind in ("byte", "high", "band")
        for combo in combos
    ]
    candidate_rows.sort(
        key=lambda row: (
            str(row["target_kind"]),
            -int_value(row, "loo_correct_slots"),
            int_value(row, "loo_false_slots"),
            int_value(row, "feature_count"),
            str(row["feature_set"]),
        )
    )
    for index, row in enumerate(candidate_rows, start=1):
        row["rank"] = index

    false_free_byte = [
        row for row in candidate_rows if row.get("target_kind") == "byte" and int_value(row, "loo_false_slots") == 0 and int_value(row, "loo_correct_slots") > 0
    ]
    false_free_high = [
        row for row in candidate_rows if row.get("target_kind") == "high" and int_value(row, "loo_false_slots") == 0 and int_value(row, "loo_correct_slots") > 0
    ]
    best_byte = best_candidate(candidate_rows, "byte")
    best_high = best_candidate(candidate_rows, "high")
    best_band = best_candidate(candidate_rows, "band")
    best_false_free_byte = best_false_free(candidate_rows, "byte")
    best_false_free_high = best_false_free(candidate_rows, "high")
    summary = {
        "scope": "total",
        "target_rows": len(payloads),
        "target_bytes": sum(len(payload) for _row, payload in payloads),
        "source_rows": len(profile_rows),
        "features": len(features),
        "feature_sets": len(combos),
        "candidate_rows": len(candidate_rows),
        "false_free_byte_sets": len(false_free_byte),
        "best_false_free_byte_feature_set": best_false_free_byte.get("feature_set", ""),
        "best_false_free_byte_slots": best_false_free_byte.get("loo_correct_slots", 0),
        "best_false_free_byte_unknown_slots": best_false_free_byte.get("loo_unknown_slots", 0),
        "false_free_high_sets": len(false_free_high),
        "best_false_free_high_feature_set": best_false_free_high.get("feature_set", ""),
        "best_false_free_high_slots": best_false_free_high.get("loo_correct_slots", 0),
        "best_false_free_high_unknown_slots": best_false_free_high.get("loo_unknown_slots", 0),
        "best_byte_feature_set": best_byte.get("feature_set", ""),
        "best_byte_correct_slots": best_byte.get("loo_correct_slots", 0),
        "best_byte_false_slots": best_byte.get("loo_false_slots", 0),
        "best_byte_precision": best_byte.get("loo_precision", "0.000000"),
        "best_high_feature_set": best_high.get("feature_set", ""),
        "best_high_correct_slots": best_high.get("loo_correct_slots", 0),
        "best_high_false_slots": best_high.get("loo_false_slots", 0),
        "best_high_precision": best_high.get("loo_precision", "0.000000"),
        "best_band_feature_set": best_band.get("feature_set", ""),
        "best_band_correct_slots": best_band.get("loo_correct_slots", 0),
        "best_band_false_slots": best_band.get("loo_false_slots", 0),
        "best_band_precision": best_band.get("loo_precision", "0.000000"),
        "promotion_ready_bytes": 0,
        "issue_rows": len(issues),
    }
    return summary, candidate_rows


def render_table(rows: list[dict[str, object]], fields: list[str], limit: int = 240) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(summary: dict[str, object], candidates: list[dict[str, object]], title: str) -> str:
    data_json = json.dumps({"summary": summary, "candidates": candidates}, indent=2, sort_keys=True)
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body {{ margin: 2rem; background: #111416; color: #edf5f4; font: 14px/1.45 system-ui, sans-serif; }}
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
  <div class="box"><div class="num">{summary['target_bytes']}</div><div class="muted">target bytes</div></div>
  <div class="box"><div class="num">{summary['best_byte_correct_slots']}/{summary['best_byte_false_slots']}</div><div class="muted">best byte correct/false</div></div>
  <div class="box"><div class="num">{summary['best_false_free_byte_slots']}</div><div class="muted">best false-free byte slots</div></div>
  <div class="box"><div class="num">{summary['best_false_free_high_slots']}</div><div class="muted">best false-free high slots</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Candidates</h2>{render_table(candidates, CANDIDATE_FIELDNAMES)}</div>
<script type="application/json" id="mixed-value-external-source-combo-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe external-source combo predictors for mixed-value payloads.")
    parser.add_argument("--input-rows", type=Path, default=DEFAULT_INPUT_ROWS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--replay-fixtures", type=Path, default=DEFAULT_REPLAY_FIXTURES)
    parser.add_argument("--source-profile-rows", type=Path, default=DEFAULT_SOURCE_PROFILE_ROWS)
    parser.add_argument("--max-features", type=int, default=2)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Mixed Value External Source Combo Probe")
    args = parser.parse_args()

    summary, candidates = build(
        read_csv(args.input_rows),
        read_csv(args.fixtures),
        read_csv(args.replay_fixtures),
        read_csv(args.source_profile_rows),
        max_features=args.max_features,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "candidates.csv", CANDIDATE_FIELDNAMES, candidates)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, candidates, args.title))

    print(f"Feature sets: {summary['feature_sets']}")
    print(
        f"Best byte source combo: {summary['best_byte_feature_set']} "
        f"{summary['best_byte_correct_slots']}/{summary['best_byte_false_slots']}"
    )
    print(f"Best false-free byte slots: {summary['best_false_free_byte_slots']}")
    print(f"Best false-free high slots: {summary['best_false_free_high_slots']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
