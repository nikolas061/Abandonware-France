#!/usr/bin/env python3
"""Probe high/low nibble prediction from post-formula gradient source profiles."""

from __future__ import annotations

import argparse
import html
import itertools
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_opcode_probe import write_csv


DEFAULT_GRADIENT_PROFILE_ROWS = Path("output/tex_gradient_payload_profile/rows.csv")
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_REPLAY_FIXTURES = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_formula_replay/fixtures.csv"
)
DEFAULT_OUTPUT = Path("output/tex_gradient_source_profile_high_low")

FEATURES = [
    "pool",
    "offset_delta",
    "offset_delta_bucket",
    "gradient_class",
    "top_nibble",
    "length_band8",
    "source_byte",
    "source_high",
    "source_low",
    "source_zero",
    "rel_mod4",
    "rel_mod8",
    "rel_mod16",
    "x_mod8",
    "y_mod4",
    "y_mod8",
]

SUMMARY_FIELDNAMES = [
    "scope",
    "profile_rows",
    "slot_rows",
    "source_profile_rows",
    "feature_sets",
    "full_false_free_feature_sets",
    "full_best_exact_slots",
    "full_best_false_slots",
    "full_best_feature_set",
    "high_false_free_feature_sets",
    "high_best_false_free_slots",
    "high_best_false_free_feature_set",
    "high_best_exact_slots",
    "high_best_false_slots",
    "high_best_feature_set",
    "low_false_free_feature_sets",
    "low_best_exact_slots",
    "low_best_false_slots",
    "low_best_feature_set",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

SLOT_FIELDNAMES = [
    "rank",
    "row_id",
    "archive",
    "pcx_name",
    "frontier_id",
    "start",
    "end",
    "target_offset",
    "relative_offset",
    "pool",
    "source_profile_offset",
    "offset_delta",
    "offset_delta_bucket",
    "gradient_class",
    "top_nibble",
    "length_band8",
    "source_byte",
    "source_high",
    "source_low",
    "source_zero",
    "target_byte",
    "target_high",
    "target_low",
    "full_delta",
    "high_delta",
    "low_delta",
    "rel_mod4",
    "rel_mod8",
    "rel_mod16",
    "x_mod8",
    "y_mod4",
    "y_mod8",
]

RULE_FIELDNAMES = [
    "rank",
    "target_kind",
    "feature_set",
    "feature_count",
    "predicted_slots",
    "exact_slots",
    "false_slots",
    "precision",
    "groups",
    "predicted_groups",
    "false_free",
    "sample_predictions",
    "verdict",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        import csv

        return list(csv.DictReader(handle))


def int_value(row: dict[str, str] | dict[str, object], field: str, default: int = 0) -> int:
    try:
        return int(row.get(field, "") or default)
    except (TypeError, ValueError):
        return default


def ratio(numerator: int, denominator: int) -> str:
    return f"{numerator / denominator:.6f}" if denominator else "0.000000"


def row_key(row: dict[str, str] | dict[str, object]) -> tuple[str, str, str]:
    return (
        str(row.get("archive", "")),
        str(row.get("pcx_name", "")),
        str(row.get("frontier_id", "")),
    )


def read_bytes(path_text: str, issues: list[str], label: str) -> bytes:
    if not path_text:
        issues.append(f"missing_{label}_path")
        return b""
    try:
        return Path(path_text).read_bytes()
    except OSError as exc:
        issues.append(f"read_{label}_failed:{exc}")
        return b""


def signed_band(value: int, step: int) -> str:
    base = (value // step) * step
    return f"{base}-{base + step - 1}"


def length_band(length: int, step: int = 8) -> str:
    base = (length // step) * step
    return f"{base}-{base + step - 1}"


def feature_sets(max_features: int) -> list[tuple[str, ...]]:
    output: list[tuple[str, ...]] = []
    for size in range(1, max_features + 1):
        output.extend(itertools.combinations(FEATURES, size))
    return output


def source_pool_bytes(
    *,
    pool: str,
    manifest: dict[str, str],
    replay: dict[str, str],
    issues: list[str],
) -> tuple[str, bytes]:
    if pool == "decoded_replay":
        return "decoded_formula", read_bytes(replay.get("decoded_path", ""), issues, "decoded_formula")
    if pool in {"segment_gap", "control_prefix", "fragment"}:
        return pool, read_bytes(manifest.get(f"{pool}_path", ""), issues, pool)
    issues.append(f"unknown_source_profile_pool:{pool}")
    return pool, b""


def build_slots(
    profile_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    replay_rows: list[dict[str, str]],
) -> tuple[list[dict[str, object]], list[str]]:
    manifests = {row_key(row): row for row in fixture_rows}
    replays = {row_key(row): row for row in replay_rows}
    slots: list[dict[str, object]] = []
    issues: list[str] = []
    for row in profile_rows:
        key = row_key(row)
        manifest = manifests.get(key)
        replay = replays.get(key)
        if manifest is None:
            issues.append(f"missing_manifest:{key}")
            continue
        if replay is None:
            issues.append(f"missing_replay:{key}")
            continue
        local_issues: list[str] = []
        expected = read_bytes(manifest.get("expected_gap_path", ""), local_issues, "expected")
        known_mask = read_bytes(replay.get("known_mask_path", ""), local_issues, "known_mask")
        pool_name, source = source_pool_bytes(
            pool=row.get("best_source_profile_pool", ""),
            manifest=manifest,
            replay=replay,
            issues=local_issues,
        )
        source_offset = int_value(row, "best_source_profile_offset", -1)
        start = int_value(row, "start")
        end = int_value(row, "end")
        length = max(0, end - start)
        if source_offset < 0 or source_offset + length > len(source):
            local_issues.append("source_profile_window_out_of_range")
        if end > len(expected):
            local_issues.append("target_window_out_of_range")
        if end > len(known_mask):
            local_issues.append("known_mask_window_out_of_range")
        if local_issues:
            issues.extend(f"{key}:{issue}" for issue in local_issues)
            if source_offset < 0 or source_offset + length > len(source):
                continue
        source_window = source[source_offset : source_offset + length]
        offset_delta = source_offset - start
        row_id = "|".join((*key, str(start), str(end)))
        for rel, source_value in enumerate(source_window):
            target_offset = start + rel
            if target_offset >= len(expected) or target_offset >= len(known_mask):
                continue
            if known_mask[target_offset]:
                continue
            target_value = expected[target_offset]
            x = target_offset % 320
            y = target_offset // 320
            slots.append(
                {
                    "rank": len(slots) + 1,
                    "row_id": row_id,
                    "archive": key[0],
                    "pcx_name": key[1],
                    "frontier_id": key[2],
                    "start": start,
                    "end": end,
                    "target_offset": target_offset,
                    "relative_offset": rel,
                    "pool": pool_name,
                    "source_profile_offset": source_offset,
                    "offset_delta": offset_delta,
                    "offset_delta_bucket": signed_band(offset_delta, 64),
                    "gradient_class": row.get("gradient_class", ""),
                    "top_nibble": row.get("top_nibble", ""),
                    "length_band8": length_band(length),
                    "source_byte": f"{source_value:02x}",
                    "source_high": f"{source_value >> 4:x}",
                    "source_low": f"{source_value & 0x0F:x}",
                    "source_zero": 1 if source_value == 0 else 0,
                    "target_byte": f"{target_value:02x}",
                    "target_high": f"{target_value >> 4:x}",
                    "target_low": f"{target_value & 0x0F:x}",
                    "full_delta": (target_value - source_value) & 0xFF,
                    "high_delta": ((target_value >> 4) - (source_value >> 4)) & 0x0F,
                    "low_delta": ((target_value & 0x0F) - (source_value & 0x0F)) & 0x0F,
                    "rel_mod4": rel % 4,
                    "rel_mod8": rel % 8,
                    "rel_mod16": rel % 16,
                    "x_mod8": x % 8,
                    "y_mod4": y % 4,
                    "y_mod8": y % 8,
                }
            )
        issues.extend(f"{key}:{issue}" for issue in local_issues)
    return slots, issues


def context_for(row: dict[str, object], features: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(str(row.get(feature, "")) for feature in features)


def prediction_value(slot: dict[str, object], target_kind: str, delta: int) -> int:
    source_value = int(str(slot["source_byte"]), 16)
    if target_kind == "full":
        return (source_value + delta) & 0xFF
    if target_kind == "high":
        return ((source_value >> 4) + delta) & 0x0F
    if target_kind == "low":
        return ((source_value & 0x0F) + delta) & 0x0F
    raise ValueError(target_kind)


def target_value(slot: dict[str, object], target_kind: str) -> int:
    target = int(str(slot["target_byte"]), 16)
    if target_kind == "full":
        return target
    if target_kind == "high":
        return target >> 4
    if target_kind == "low":
        return target & 0x0F
    raise ValueError(target_kind)


def evaluate_feature_set(
    slots: list[dict[str, object]],
    features: tuple[str, ...],
    *,
    target_kind: str,
) -> dict[str, object]:
    delta_field = f"{target_kind}_delta"
    groups: dict[tuple[str, ...], list[dict[str, object]]] = defaultdict(list)
    for slot in slots:
        groups[context_for(slot, features)].append(slot)

    exact = 0
    false = 0
    predicted = 0
    predicted_groups: set[tuple[str, ...]] = set()
    samples: list[str] = []
    for context, group in groups.items():
        total_counts = Counter(int_value(slot, delta_field) for slot in group)
        by_row: dict[str, Counter[int]] = defaultdict(Counter)
        for slot in group:
            by_row[str(slot["row_id"])][int_value(slot, delta_field)] += 1
        peer_delta_by_row: dict[str, int] = {}
        for row_id, row_counts in by_row.items():
            peer_counts = total_counts.copy()
            peer_counts.subtract(row_counts)
            peer_counts = Counter({delta: count for delta, count in peer_counts.items() if count > 0})
            if len(peer_counts) == 1:
                peer_delta_by_row[row_id] = next(iter(peer_counts))
        for slot in group:
            delta = peer_delta_by_row.get(str(slot["row_id"]))
            if delta is None:
                continue
            predicted += 1
            predicted_groups.add(context)
            if prediction_value(slot, target_kind, delta) == target_value(slot, target_kind):
                exact += 1
            else:
                false += 1
            if len(samples) < 8:
                samples.append(f"{'|'.join(context)}:d={delta}")
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
        "false_free": 1 if false_free else 0,
        "sample_predictions": "|".join(samples),
        "verdict": (
            f"{target_kind}_source_profile_false_free"
            if false_free
            else f"{target_kind}_source_profile_noisy"
            if predicted
            else f"{target_kind}_source_profile_no_predictions"
        ),
    }


def build_rules(
    slots: list[dict[str, object]],
    *,
    max_features: int,
) -> list[dict[str, object]]:
    rules: list[dict[str, object]] = []
    for target_kind in ("full", "high", "low"):
        for features in feature_sets(max_features):
            rule = evaluate_feature_set(slots, features, target_kind=target_kind)
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
            str(row["feature_set"]),
        ),
        default={},
    )


def count_false_free(rules: list[dict[str, object]], target_kind: str) -> int:
    return sum(
        1
        for row in rules
        if row.get("target_kind") == target_kind and int_value(row, "false_free") > 0
    )


def build(
    profile_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    replay_rows: list[dict[str, str]],
    *,
    max_features: int,
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    slots, issues = build_slots(profile_rows, fixture_rows, replay_rows)
    rules = build_rules(slots, max_features=max_features)
    full_best = best_rule(rules, "full")
    high_best = best_rule(rules, "high")
    high_false_free = best_false_free_rule(rules, "high")
    low_best = best_rule(rules, "low")
    summary = {
        "scope": "total",
        "profile_rows": len(profile_rows),
        "slot_rows": len(slots),
        "source_profile_rows": len({row.get("row_id", "") for row in slots}),
        "feature_sets": len(feature_sets(max_features)),
        "full_false_free_feature_sets": count_false_free(rules, "full"),
        "full_best_exact_slots": full_best.get("exact_slots", 0),
        "full_best_false_slots": full_best.get("false_slots", 0),
        "full_best_feature_set": full_best.get("feature_set", ""),
        "high_false_free_feature_sets": count_false_free(rules, "high"),
        "high_best_false_free_slots": high_false_free.get("exact_slots", 0),
        "high_best_false_free_feature_set": high_false_free.get("feature_set", ""),
        "high_best_exact_slots": high_best.get("exact_slots", 0),
        "high_best_false_slots": high_best.get("false_slots", 0),
        "high_best_feature_set": high_best.get("feature_set", ""),
        "low_false_free_feature_sets": count_false_free(rules, "low"),
        "low_best_exact_slots": low_best.get("exact_slots", 0),
        "low_best_false_slots": low_best.get("false_slots", 0),
        "low_best_feature_set": low_best.get("feature_set", ""),
        "promotion_candidate_bytes": 0,
        "promotion_ready_bytes": 0,
        "issue_rows": len(issues),
    }
    return summary, slots, rules


def render_table(rows: list[dict[str, object]], fields: list[str], limit: int = 220) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


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
    )[:240]
    data_json = json.dumps({"summary": summary, "rules": rules, "slots": slots}, indent=2, sort_keys=True)
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body {{ margin: 2rem; background: #101214; color: #edf5f4; font: 14px/1.45 system-ui, sans-serif; }}
table {{ border-collapse: collapse; width: 100%; min-width: 1700px; }}
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
  <div class="box"><div class="num">{summary['slot_rows']}</div><div class="muted">source-profile slots</div></div>
  <div class="box"><div class="num">{summary['full_false_free_feature_sets']}</div><div class="muted">full false-free sets</div></div>
  <div class="box"><div class="num">{summary['high_best_false_free_slots']}</div><div class="muted">high false-free slots</div></div>
  <div class="box"><div class="num">{summary['low_false_free_feature_sets']}</div><div class="muted">low false-free sets</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Rules</h2>{render_table(top_rules, RULE_FIELDNAMES)}</div>
<div class="panel"><h2>Slots</h2>{render_table(slots, SLOT_FIELDNAMES)}</div>
<script type="application/json" id="gradient-source-profile-high-low-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe gradient source-profile high/low nibble transforms.")
    parser.add_argument("--gradient-profile-rows", type=Path, default=DEFAULT_GRADIENT_PROFILE_ROWS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--replay-fixtures", type=Path, default=DEFAULT_REPLAY_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-features", type=int, default=4)
    parser.add_argument("--title", default="Lands of Lore II .tex Gradient Source Profile High/Low Probe")
    args = parser.parse_args()

    summary, slots, rules = build(
        read_csv(args.gradient_profile_rows),
        read_csv(args.fixtures),
        read_csv(args.replay_fixtures),
        max_features=args.max_features,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "slots.csv", SLOT_FIELDNAMES, slots)
    write_csv(args.output / "rules.csv", RULE_FIELDNAMES, rules)
    (args.output / "index.html").write_text(build_html(summary, slots, rules, args.title))

    print(f"Source-profile slots: {summary['slot_rows']}")
    print(f"Full false-free feature sets: {summary['full_false_free_feature_sets']}")
    print(f"High false-free slots: {summary['high_best_false_free_slots']}")
    print(f"Low false-free feature sets: {summary['low_false_free_feature_sets']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
