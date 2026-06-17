#!/usr/bin/env python3
"""Probe gradient bytes from already-known sequence state around each slot."""

from __future__ import annotations

import argparse
import csv
import html
import itertools
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_opcode_probe import write_csv


DEFAULT_GRADIENT_ROWS = Path("output/tex_gradient_payload_profile/rows.csv")
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_REPLAY_FIXTURES = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_formula_replay/fixtures.csv"
)
DEFAULT_OUTPUT = Path("output/tex_gradient_sequence_known_state")

FEATURES = [
    "gradient_class",
    "top_nibble",
    "length_band8",
    "rel_mod4",
    "rel_mod8",
    "rel_mod16",
    "x_mod8",
    "y_mod8",
    "prev1",
    "prev2",
    "prev4",
    "next1",
    "next2",
    "next4",
    "prev_known_byte",
    "prev_gap_bucket",
    "next_known_byte",
    "next_gap_bucket",
    "known_before_mod16",
    "unknown_before_mod16",
    "prefix_sum_mod16",
    "prefix_xor_high",
    "prefix_xor_low",
]

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
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
    "high_low_false_exact_slots",
    "high_low_false_false_slots",
    "high_low_false_feature_set",
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
    "target_byte",
    "target_high",
    "target_low",
    *FEATURES,
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
    "predicted_rows",
    "false_free",
    "sample_predictions",
    "verdict",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def read_bytes(path_text: str, issues: list[str], label: str) -> bytes:
    if not path_text:
        issues.append(f"missing_{label}_path")
        return b""
    try:
        return Path(path_text).read_bytes()
    except OSError as exc:
        issues.append(f"read_{label}_failed:{exc}")
        return b""


def int_value(row: dict[str, object], field: str, default: int = 0) -> int:
    raw = row.get(field, "")
    if raw == "":
        return default
    try:
        return int(str(raw), 0)
    except (TypeError, ValueError):
        return default


def ratio(numerator: int, denominator: int) -> str:
    return f"{numerator / denominator:.6f}" if denominator else "0.000000"


def row_key(row: dict[str, object]) -> tuple[str, str, str]:
    return (
        str(row.get("archive", "")),
        str(row.get("pcx_name", "")),
        str(row.get("frontier_id", "")),
    )


def length_band(length: int, step: int = 8) -> str:
    base = (length // step) * step
    return f"{base}-{base + step - 1}"


def gap_bucket(gap: int) -> str:
    if gap < 0:
        return "none"
    if gap <= 1:
        return "1"
    if gap <= 2:
        return "2"
    if gap <= 4:
        return "3-4"
    if gap <= 8:
        return "5-8"
    if gap <= 16:
        return "9-16"
    return "17+"


def neighbor_byte(decoded: bytes, known_mask: bytes, position: int, delta: int) -> str:
    source = position + delta
    if 0 <= source < len(decoded) and source < len(known_mask) and known_mask[source]:
        return f"{decoded[source]:02x}"
    return "unk"


def nearest_known(decoded: bytes, known_mask: bytes, position: int, direction: int) -> tuple[str, str]:
    for distance in range(1, 33):
        source = position + direction * distance
        if 0 <= source < len(decoded) and source < len(known_mask) and known_mask[source]:
            return f"{decoded[source]:02x}", gap_bucket(distance)
    return "none", "none"


def build_slots(
    gradient_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    replay_rows: list[dict[str, str]],
) -> tuple[list[dict[str, object]], list[str]]:
    fixtures = {row_key(row): row for row in fixture_rows}
    replays = {row_key(row): row for row in replay_rows}
    slots: list[dict[str, object]] = []
    issues: list[str] = []
    for row in gradient_rows:
        key = row_key(row)
        manifest = fixtures.get(key)
        replay = replays.get(key)
        if manifest is None:
            issues.append(f"missing_fixture:{'|'.join(key)}")
            continue
        if replay is None:
            issues.append(f"missing_replay:{'|'.join(key)}")
            continue
        local_issues: list[str] = []
        expected = read_bytes(manifest.get("expected_gap_path", ""), local_issues, "expected")
        decoded = read_bytes(replay.get("decoded_path", ""), local_issues, "decoded")
        known_mask = read_bytes(replay.get("known_mask_path", ""), local_issues, "known_mask")
        start = int_value(row, "start")
        end = int_value(row, "end")
        length = max(0, end - start)
        if end > len(expected):
            local_issues.append("target_window_out_of_range")
        if len(decoded) != len(known_mask):
            local_issues.append("decoded_mask_length_mismatch")
        if local_issues:
            issues.extend(f"{'|'.join(key)}:{issue}" for issue in local_issues)
            if not expected or not decoded or not known_mask:
                continue

        prefix_sum = 0
        prefix_xor = 0
        known_before = 0
        unknown_before = 0
        row_id = "|".join((*key, str(start), str(end)))
        for target_offset in range(start, min(end, len(expected), len(known_mask))):
            if known_mask[target_offset]:
                prefix_sum = (prefix_sum + decoded[target_offset]) & 0xFF
                prefix_xor ^= decoded[target_offset]
                known_before += 1
                continue
            target = expected[target_offset]
            relative_offset = target_offset - start
            x = target_offset % 320
            y = target_offset // 320
            prev_known_byte, prev_gap = nearest_known(decoded, known_mask, target_offset, -1)
            next_known_byte, next_gap = nearest_known(decoded, known_mask, target_offset, 1)
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
                    "relative_offset": relative_offset,
                    "target_byte": f"{target:02x}",
                    "target_high": f"{target >> 4:x}",
                    "target_low": f"{target & 0x0F:x}",
                    "gradient_class": row.get("gradient_class", ""),
                    "top_nibble": row.get("top_nibble", ""),
                    "length_band8": length_band(length),
                    "rel_mod4": relative_offset % 4,
                    "rel_mod8": relative_offset % 8,
                    "rel_mod16": relative_offset % 16,
                    "x_mod8": x % 8,
                    "y_mod8": y % 8,
                    "prev1": neighbor_byte(decoded, known_mask, target_offset, -1),
                    "prev2": neighbor_byte(decoded, known_mask, target_offset, -2),
                    "prev4": neighbor_byte(decoded, known_mask, target_offset, -4),
                    "next1": neighbor_byte(decoded, known_mask, target_offset, 1),
                    "next2": neighbor_byte(decoded, known_mask, target_offset, 2),
                    "next4": neighbor_byte(decoded, known_mask, target_offset, 4),
                    "prev_known_byte": prev_known_byte,
                    "prev_gap_bucket": prev_gap,
                    "next_known_byte": next_known_byte,
                    "next_gap_bucket": next_gap,
                    "known_before_mod16": known_before % 16,
                    "unknown_before_mod16": unknown_before % 16,
                    "prefix_sum_mod16": prefix_sum % 16,
                    "prefix_xor_high": prefix_xor >> 4,
                    "prefix_xor_low": prefix_xor & 0x0F,
                }
            )
            unknown_before += 1
    return slots, issues


def feature_sets(max_features: int) -> list[tuple[str, ...]]:
    output: list[tuple[str, ...]] = []
    for size in range(1, max_features + 1):
        output.extend(itertools.combinations(FEATURES, size))
    return output


def target_field(target_kind: str) -> str:
    if target_kind == "full":
        return "target_byte"
    if target_kind == "high":
        return "target_high"
    if target_kind == "low":
        return "target_low"
    raise ValueError(target_kind)


def context_for(slot: dict[str, object], features: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(str(slot.get(feature, "")) for feature in features)


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
            f"{target_kind}_sequence_known_state_false_free"
            if false_free
            else f"{target_kind}_sequence_known_state_noisy"
            if predicted
            else f"{target_kind}_sequence_known_state_no_predictions"
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
    gradient_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    replay_rows: list[dict[str, str]],
    *,
    max_features: int,
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    slots, issues = build_slots(gradient_rows, fixture_rows, replay_rows)
    rules = build_rules(slots, max_features=max_features)
    full_best = best_rule(rules, "full")
    high_best = best_rule(rules, "high")
    high_false_free = best_false_free_rule(rules, "high")
    high_low_false = best_low_false_rule(rules, "high")
    low_best = best_rule(rules, "low")
    summary = {
        "scope": "total",
        "target_rows": len(gradient_rows),
        "slot_rows": len(slots),
        "source_profile_rows": len({row.get("row_id", "") for row in slots}),
        "feature_sets": len(feature_sets(max_features)),
        "full_false_free_feature_sets": false_free_count(rules, "full"),
        "full_best_exact_slots": full_best.get("exact_slots", 0),
        "full_best_false_slots": full_best.get("false_slots", 0),
        "full_best_feature_set": full_best.get("feature_set", ""),
        "high_false_free_feature_sets": false_free_count(rules, "high"),
        "high_best_false_free_slots": high_false_free.get("exact_slots", 0),
        "high_best_false_free_feature_set": high_false_free.get("feature_set", ""),
        "high_best_exact_slots": high_best.get("exact_slots", 0),
        "high_best_false_slots": high_best.get("false_slots", 0),
        "high_best_feature_set": high_best.get("feature_set", ""),
        "high_low_false_exact_slots": high_low_false.get("exact_slots", 0),
        "high_low_false_false_slots": high_low_false.get("false_slots", 0),
        "high_low_false_feature_set": high_low_false.get("feature_set", ""),
        "low_false_free_feature_sets": false_free_count(rules, "low"),
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
table {{ border-collapse: collapse; width: 100%; min-width: 1800px; }}
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
  <div class="box"><div class="num">{summary['slot_rows']}</div><div class="muted">sequence slots</div></div>
  <div class="box"><div class="num">{summary['full_false_free_feature_sets']}</div><div class="muted">full false-free sets</div></div>
  <div class="box"><div class="num">{summary['high_best_false_free_slots']}</div><div class="muted">high false-free slots</div></div>
  <div class="box"><div class="num">{summary['low_false_free_feature_sets']}</div><div class="muted">low false-free sets</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Rules</h2>{render_table(top_rules, RULE_FIELDNAMES)}</div>
<div class="panel"><h2>Slots</h2>{render_table(slots, SLOT_FIELDNAMES)}</div>
<script type="application/json" id="gradient-sequence-known-state-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe gradient known sequence-state high/low bytes.")
    parser.add_argument("--gradient-rows", type=Path, default=DEFAULT_GRADIENT_ROWS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--replay-fixtures", type=Path, default=DEFAULT_REPLAY_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-features", type=int, default=3)
    parser.add_argument("--title", default="Lands of Lore II .tex Gradient Sequence Known-State Probe")
    args = parser.parse_args()

    summary, slots, rules = build(
        read_csv(args.gradient_rows),
        read_csv(args.fixtures),
        read_csv(args.replay_fixtures),
        max_features=args.max_features,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "slots.csv", SLOT_FIELDNAMES, slots)
    write_csv(args.output / "rules.csv", RULE_FIELDNAMES, rules)
    (args.output / "index.html").write_text(build_html(summary, slots, rules, args.title))

    print(f"Sequence slots: {summary['slot_rows']}")
    print(f"Full false-free feature sets: {summary['full_false_free_feature_sets']}")
    print(
        "Best full rule: "
        f"{summary['full_best_exact_slots']} exact / {summary['full_best_false_slots']} false"
    )
    print(f"High false-free slots: {summary['high_best_false_free_slots']}")
    print(
        "Best high rule: "
        f"{summary['high_best_exact_slots']} exact / {summary['high_best_false_slots']} false"
    )
    print(f"Low false-free feature sets: {summary['low_false_free_feature_sets']}")
    print(
        "Best low rule: "
        f"{summary['low_best_exact_slots']} exact / {summary['low_best_false_slots']} false"
    )
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
