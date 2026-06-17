#!/usr/bin/env python3
"""Probe residual source-window grammar after gradient high-safe low rejections."""

from __future__ import annotations

import argparse
import csv
import html
import itertools
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_opcode_probe import write_csv
from lolg_tex_gradient_sequence_high_safe_low_probe import int_value, ratio, render_table
from lolg_tex_gradient_sequence_high_safe_row_corpus_low_probe import (
    SLOT_FIELDNAMES as ROW_CORPUS_SLOT_FIELDNAMES,
)


DEFAULT_SLOTS = Path("output/tex_gradient_sequence_high_safe_row_corpus_low/slots.csv")
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_REPLAY_FIXTURES = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_formula_replay/fixtures.csv"
)
DEFAULT_OUTPUT = Path("output/tex_gradient_sequence_high_safe_source_window")

FEATURES = [
    "gradient_class",
    "top_nibble",
    "length_band8",
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
    "unknown_before_mod16",
    "prefix_sum_mod16",
    "predicted_high",
    "high_context",
    "row_quarter",
    "row_third",
    "row_half",
    "end_mod16",
    "length_mod16",
    "source_target_delta_mod16",
    "source_target_delta_mod32",
    "target_mod64",
    "target_x_mod32",
    "start_mod64",
    "shape_len_key",
    "shape_start_key",
]

FOCUSED_4_FEATURE_SETS = [
    ("x_mod8", "src_rel_mod8", "offset_delta_bucket", "row_third"),
    ("rel_mod8", "offset_delta_bucket", "row_third", "shape_len_key"),
    ("rel_mod4", "x_mod8", "row_quarter", "prev_known_byte"),
]

GATE_CANDIDATES = [
    (21, "low+9"),
    (21, "lowsigned-7"),
    (18, "lowxor9"),
    (19, "lowxor9"),
    (20, "lowxor9"),
    (18, "low+9"),
    (19, "low+9"),
    (20, "low+9"),
    (17, "low+9"),
    (17, "lowxor9"),
    (7, "lowxor9"),
    (60, "identity"),
    (0, "identity"),
    (61, "identity"),
    (52, "identity"),
]

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "slots",
    "slot_rows",
    "scan_radius",
    "fixed_low_candidates",
    "fixed_full_candidates",
    "fixed_low_best_exact_slots",
    "fixed_low_best_false_slots",
    "fixed_low_best_candidate",
    "fixed_full_best_exact_slots",
    "fixed_full_best_false_slots",
    "fixed_full_best_candidate",
    "gate_candidates",
    "gate_feature_sets",
    "gate_rules",
    "gate_predicted_rules",
    "gate_false_free_sets",
    "gate_best_false_free_slots",
    "gate_best_false_free_candidate",
    "gate_best_false_free_feature_set",
    "gate_best_exact_slots",
    "gate_best_false_slots",
    "gate_best_candidate",
    "gate_best_feature_set",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

FIXED_FIELDNAMES = [
    "rank",
    "target_kind",
    "window_delta",
    "window_transform",
    "candidate",
    "applicable_slots",
    "exact_slots",
    "false_slots",
    "precision",
    "exact_rows",
    "sample_exact",
    "verdict",
]

GATE_FIELDNAMES = [
    "rank",
    "candidate",
    "feature_set",
    "feature_count",
    "applicable_slots",
    "predicted_slots",
    "exact_slots",
    "false_slots",
    "unknown_slots",
    "precision",
    "predicted_groups",
    "predicted_rows",
    "false_free",
    "sample_predictions",
    "verdict",
]

SLOT_FIELDNAMES = [
    *ROW_CORPUS_SLOT_FIELDNAMES,
    "best_fixed_low_candidate",
    "best_fixed_low_predicted_low",
    "best_fixed_low_verdict",
    "best_gate_candidate",
    "best_gate_feature_set",
    "best_gate_context",
    "best_gate_predicted_low",
    "best_gate_predicted_byte",
    "best_gate_verdict",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def row_key(row: dict[str, object]) -> tuple[str, str, str]:
    return (
        str(row.get("archive", "")),
        str(row.get("pcx_name", "")),
        str(row.get("frontier_id", "")),
    )


def read_bytes(path_text: str, cache: dict[str, bytes], issues: list[str], label: str) -> bytes:
    if not path_text:
        issues.append(f"missing_{label}_path")
        return b""
    if path_text not in cache:
        try:
            cache[path_text] = Path(path_text).read_bytes()
        except OSError as exc:
            issues.append(f"read_{label}_failed:{exc}")
            cache[path_text] = b""
    return cache[path_text]


def source_bytes(
    slot: dict[str, object],
    fixtures: dict[tuple[str, str, str], dict[str, str]],
    replays: dict[tuple[str, str, str], dict[str, str]],
    cache: dict[str, bytes],
    issues: list[str],
) -> bytes:
    key = row_key(slot)
    pool = str(slot.get("pool", ""))
    if pool == "decoded_formula":
        replay = replays.get(key, {})
        return read_bytes(replay.get("decoded_path", ""), cache, issues, "decoded_formula")
    fixture = fixtures.get(key, {})
    if pool == "segment_gap":
        return read_bytes(fixture.get("segment_gap_path", ""), cache, issues, "segment_gap")
    if pool == "control_prefix":
        return read_bytes(fixture.get("control_prefix_path", ""), cache, issues, "control_prefix")
    if pool == "fragment":
        return read_bytes(fixture.get("fragment_path", ""), cache, issues, "fragment")
    issues.append(f"unknown_source_pool:{pool}")
    return b""


def parse_hex(text: object) -> int | None:
    value = str(text)
    if not value or value in {"unk", "none"}:
        return None
    try:
        return int(value, 16)
    except ValueError:
        return None


def target_low(slot: dict[str, object]) -> int | None:
    return parse_hex(slot.get("target_low", ""))


def target_byte(slot: dict[str, object]) -> int | None:
    return parse_hex(slot.get("target_byte", ""))


def low_transform(source_byte: int, transform: str) -> int | None:
    low = source_byte & 0x0F
    if transform == "identity":
        return low
    if transform.startswith("low+"):
        return (low + int(transform[4:], 16)) & 0x0F
    if transform.startswith("lowxor"):
        return low ^ int(transform[6:], 16)
    if transform.startswith("lowsigned"):
        return (low + int(transform[9:])) & 0x0F
    return None


def low_transforms() -> list[str]:
    output: list[str] = []
    for value in range(16):
        output.append(f"low+{value:x}")
        output.append(f"lowxor{value:x}")
    output.extend(f"lowsigned{value:+d}" for value in range(-8, 8))
    output.append("identity")
    return output


def source_at(slot: dict[str, object], source: bytes, window_delta: int) -> int | None:
    position = int_value(slot, "source_profile_offset", -1) + window_delta
    if position < 0 or position >= len(source):
        return None
    return source[position]


def fixed_low_rows(
    slots: list[dict[str, object]],
    sources: list[bytes],
    radius: int,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    transforms = low_transforms()
    for window_delta in range(-radius, radius + 1):
        for transform in transforms:
            applicable = 0
            exact = 0
            exact_rows: set[str] = set()
            samples: list[str] = []
            for slot, source in zip(slots, sources):
                source_byte = source_at(slot, source, window_delta)
                low = target_low(slot)
                if source_byte is None or low is None:
                    continue
                predicted = low_transform(source_byte, transform)
                if predicted is None:
                    continue
                applicable += 1
                if predicted == low:
                    exact += 1
                    exact_rows.add(str(slot.get("row_id", "")))
                    if len(samples) < 6:
                        samples.append(
                            f"{slot.get('pcx_name', '')}:{slot.get('frontier_id', '')}:"
                            f"{slot.get('target_offset', '')}->{predicted:x}"
                        )
            if applicable:
                rows.append(
                    {
                        "rank": 0,
                        "target_kind": "low",
                        "window_delta": window_delta,
                        "window_transform": transform,
                        "candidate": f"{window_delta:+d}:{transform}",
                        "applicable_slots": applicable,
                        "exact_slots": exact,
                        "false_slots": applicable - exact,
                        "precision": ratio(exact, applicable),
                        "exact_rows": len(exact_rows),
                        "sample_exact": "|".join(samples),
                        "verdict": (
                            "fixed_low_window_candidate"
                            if exact > 0
                            else "fixed_low_window_reject"
                        ),
                    }
                )
    return rows


def fixed_full_rows(
    slots: list[dict[str, object]],
    sources: list[bytes],
    radius: int,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for window_delta in range(-radius, radius + 1):
        applicable = 0
        exact = 0
        exact_rows: set[str] = set()
        samples: list[str] = []
        for slot, source in zip(slots, sources):
            source_byte = source_at(slot, source, window_delta)
            target = target_byte(slot)
            if source_byte is None or target is None:
                continue
            applicable += 1
            if source_byte == target:
                exact += 1
                exact_rows.add(str(slot.get("row_id", "")))
                if len(samples) < 6:
                    samples.append(
                        f"{slot.get('pcx_name', '')}:{slot.get('frontier_id', '')}:"
                        f"{slot.get('target_offset', '')}->{source_byte:02x}"
                    )
        if applicable:
            rows.append(
                {
                    "rank": 0,
                    "target_kind": "full",
                    "window_delta": window_delta,
                    "window_transform": "identity",
                    "candidate": f"{window_delta:+d}:identity",
                    "applicable_slots": applicable,
                    "exact_slots": exact,
                    "false_slots": applicable - exact,
                    "precision": ratio(exact, applicable),
                    "exact_rows": len(exact_rows),
                    "sample_exact": "|".join(samples),
                    "verdict": "fixed_full_window_candidate" if exact > 0 else "fixed_full_window_reject",
                }
            )
    return rows


def candidate_feature_sets(max_features: int) -> list[tuple[str, ...]]:
    output: list[tuple[str, ...]] = []
    generated_max = min(max_features, 3)
    for size in range(1, generated_max + 1):
        output.extend(itertools.combinations(FEATURES, size))
    if max_features >= 4:
        output.extend(FOCUSED_4_FEATURE_SETS)
    seen: set[tuple[str, ...]] = set()
    unique: list[tuple[str, ...]] = []
    for feature_set in output:
        if feature_set in seen:
            continue
        seen.add(feature_set)
        unique.append(feature_set)
    return unique


def candidate_prediction(
    slot: dict[str, object],
    source: bytes,
    candidate: tuple[int, str],
) -> int | None:
    source_byte = source_at(slot, source, candidate[0])
    if source_byte is None:
        return None
    return low_transform(source_byte, candidate[1])


def context_for(slot: dict[str, object], features: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(str(slot.get(feature, "")) for feature in features)


def evaluate_gate_rule(
    slots: list[dict[str, object]],
    sources: list[bytes],
    candidate: tuple[int, str],
    features: tuple[str, ...],
) -> dict[str, object]:
    groups: dict[tuple[str, ...], list[int]] = defaultdict(list)
    values: list[str] = []
    for index, (slot, source) in enumerate(zip(slots, sources)):
        predicted = candidate_prediction(slot, source, candidate)
        low = target_low(slot)
        if predicted is None or low is None:
            values.append("")
            continue
        values.append("1" if predicted == low else "0")
        groups[context_for(slot, features)].append(index)

    applicable = sum(1 for value in values if value)
    exact = 0
    false = 0
    unknown = 0
    predicted_slots = 0
    predicted_groups: set[tuple[str, ...]] = set()
    predicted_rows: set[str] = set()
    samples: list[str] = []
    for context, indexes in groups.items():
        total_counts = Counter(values[index] for index in indexes if values[index])
        by_row: dict[str, Counter[str]] = defaultdict(Counter)
        for index in indexes:
            if values[index]:
                by_row[str(slots[index].get("row_id", ""))][values[index]] += 1
        peer_ok_rows: set[str] = set()
        for row_id, counts in by_row.items():
            peer_counts = total_counts.copy()
            peer_counts.subtract(counts)
            peer_counts = Counter({value: count for value, count in peer_counts.items() if count > 0})
            if len(peer_counts) == 1 and next(iter(peer_counts)) == "1":
                peer_ok_rows.add(row_id)
        for index in indexes:
            slot = slots[index]
            row_id = str(slot.get("row_id", ""))
            if not values[index] or row_id not in peer_ok_rows:
                unknown += 1
                continue
            predicted_slots += 1
            predicted_groups.add(context)
            predicted_rows.add(row_id)
            if values[index] == "1":
                exact += 1
            else:
                false += 1
            if len(samples) < 6:
                low = candidate_prediction(slot, sources[index], candidate)
                samples.append(f"{'|'.join(context)}->{low:x}" if low is not None else "|".join(context))

    false_free = predicted_slots > 0 and false == 0
    return {
        "rank": 0,
        "candidate": f"{candidate[0]:+d}:{candidate[1]}",
        "feature_set": "+".join(features),
        "feature_count": len(features),
        "applicable_slots": applicable,
        "predicted_slots": predicted_slots,
        "exact_slots": exact,
        "false_slots": false,
        "unknown_slots": unknown,
        "precision": ratio(exact, predicted_slots),
        "predicted_groups": len(predicted_groups),
        "predicted_rows": len(predicted_rows),
        "false_free": 1 if false_free else 0,
        "sample_predictions": "|".join(samples),
        "verdict": (
            "source_window_gate_false_free"
            if false_free
            else "source_window_gate_noisy"
            if predicted_slots
            else "source_window_gate_no_predictions"
        ),
    }


def build_gate_rules(
    slots: list[dict[str, object]],
    sources: list[bytes],
    *,
    max_features: int,
) -> tuple[list[dict[str, object]], list[tuple[str, ...]]]:
    feature_sets = candidate_feature_sets(max_features)
    rules: list[dict[str, object]] = []
    for candidate in GATE_CANDIDATES:
        for features in feature_sets:
            rule = evaluate_gate_rule(slots, sources, candidate, features)
            if int_value(rule, "predicted_slots") > 0:
                rules.append(rule)
    rules.sort(
        key=lambda row: (
            -int_value(row, "false_free"),
            -int_value(row, "exact_slots"),
            int_value(row, "false_slots"),
            int_value(row, "feature_count"),
            str(row["candidate"]),
            str(row["feature_set"]),
        )
    )
    for index, row in enumerate(rules, start=1):
        row["rank"] = index
    return rules, feature_sets


def best_rule(rows: list[dict[str, object]]) -> dict[str, object]:
    return max(
        rows,
        key=lambda row: (
            int_value(row, "exact_slots"),
            -int_value(row, "false_slots"),
            -int_value(row, "feature_count"),
            str(row.get("candidate", "")),
            str(row.get("feature_set", "")),
        ),
        default={},
    )


def best_false_free_rule(rows: list[dict[str, object]]) -> dict[str, object]:
    candidates = [row for row in rows if int_value(row, "false_free") > 0]
    return max(
        candidates,
        key=lambda row: (
            int_value(row, "exact_slots"),
            -int_value(row, "feature_count"),
            str(row.get("candidate", "")),
            str(row.get("feature_set", "")),
        ),
        default={},
    )


def rank_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    rows.sort(
        key=lambda row: (
            str(row.get("target_kind", "")),
            -int_value(row, "exact_slots"),
            int_value(row, "false_slots"),
            str(row.get("candidate", "")),
        )
    )
    for index, row in enumerate(rows, start=1):
        row["rank"] = index
    return rows


def annotate_slots(
    slots: list[dict[str, object]],
    sources: list[bytes],
    best_fixed_low: dict[str, object],
    best_gate: dict[str, object],
) -> list[dict[str, object]]:
    fixed_candidate = str(best_fixed_low.get("candidate", ""))
    fixed_delta = int_value(best_fixed_low, "window_delta", 0)
    fixed_transform = str(best_fixed_low.get("window_transform", ""))
    gate_candidate_text = str(best_gate.get("candidate", ""))
    gate_delta, gate_transform = 0, ""
    if ":" in gate_candidate_text:
        delta_text, gate_transform = gate_candidate_text.split(":", 1)
        try:
            gate_delta = int(delta_text)
        except ValueError:
            gate_delta = 0
    gate_features = tuple(part for part in str(best_gate.get("feature_set", "")).split("+") if part)
    output: list[dict[str, object]] = []
    for slot, source in zip(slots, sources):
        row = dict(slot)
        fixed_low = candidate_prediction(row, source, (fixed_delta, fixed_transform)) if fixed_transform else None
        gate_low = candidate_prediction(row, source, (gate_delta, gate_transform)) if gate_transform else None
        context = "|".join(context_for(row, gate_features)) if gate_features else ""
        high = parse_hex(row.get("predicted_high", ""))
        gate_byte = f"{high:x}{gate_low:x}" if high is not None and gate_low is not None else ""
        row.update(
            {
                "best_fixed_low_candidate": fixed_candidate,
                "best_fixed_low_predicted_low": "" if fixed_low is None else f"{fixed_low:x}",
                "best_fixed_low_verdict": (
                    "correct" if fixed_low is not None and fixed_low == target_low(row) else "false"
                ),
                "best_gate_candidate": gate_candidate_text,
                "best_gate_feature_set": "+".join(gate_features),
                "best_gate_context": context,
                "best_gate_predicted_low": "" if gate_low is None else f"{gate_low:x}",
                "best_gate_predicted_byte": gate_byte,
                "best_gate_verdict": (
                    "correct" if gate_low is not None and gate_low == target_low(row) else "false"
                ),
            }
        )
        output.append(row)
    return output


def build(
    slot_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    replay_rows: list[dict[str, str]],
    *,
    radius: int,
    max_features: int,
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    fixtures = {row_key(row): row for row in fixture_rows}
    replays = {row_key(row): row for row in replay_rows}
    cache: dict[str, bytes] = {}
    issues: list[str] = []
    slots: list[dict[str, object]] = [dict(row) for row in slot_rows]
    sources = [source_bytes(slot, fixtures, replays, cache, issues) for slot in slots]
    low_rows = rank_rows(fixed_low_rows(slots, sources, radius))
    full_rows = rank_rows(fixed_full_rows(slots, sources, radius))
    gate_rules, feature_sets = build_gate_rules(slots, sources, max_features=max_features)

    best_fixed_low = best_rule([row for row in low_rows if row.get("target_kind") == "low"])
    best_fixed_full = best_rule([row for row in full_rows if row.get("target_kind") == "full"])
    best_gate = best_rule(gate_rules)
    best_gate_false_free = best_false_free_rule(gate_rules)
    annotated_slots = annotate_slots(slots, sources, best_fixed_low, best_gate)
    summary = {
        "scope": "total",
        "candidate_mode": "source_window_scan_gate",
        "slots": len(slots),
        "slot_rows": len({row.get("row_id", "") for row in slots}),
        "scan_radius": radius,
        "fixed_low_candidates": len(low_rows),
        "fixed_full_candidates": len(full_rows),
        "fixed_low_best_exact_slots": best_fixed_low.get("exact_slots", 0),
        "fixed_low_best_false_slots": best_fixed_low.get("false_slots", 0),
        "fixed_low_best_candidate": best_fixed_low.get("candidate", ""),
        "fixed_full_best_exact_slots": best_fixed_full.get("exact_slots", 0),
        "fixed_full_best_false_slots": best_fixed_full.get("false_slots", 0),
        "fixed_full_best_candidate": best_fixed_full.get("candidate", ""),
        "gate_candidates": len(GATE_CANDIDATES),
        "gate_feature_sets": len(feature_sets),
        "gate_rules": len(GATE_CANDIDATES) * len(feature_sets),
        "gate_predicted_rules": len(gate_rules),
        "gate_false_free_sets": sum(1 for row in gate_rules if int_value(row, "false_free") > 0),
        "gate_best_false_free_slots": best_gate_false_free.get("exact_slots", 0),
        "gate_best_false_free_candidate": best_gate_false_free.get("candidate", ""),
        "gate_best_false_free_feature_set": best_gate_false_free.get("feature_set", ""),
        "gate_best_exact_slots": best_gate.get("exact_slots", 0),
        "gate_best_false_slots": best_gate.get("false_slots", 0),
        "gate_best_candidate": best_gate.get("candidate", ""),
        "gate_best_feature_set": best_gate.get("feature_set", ""),
        "promotion_candidate_bytes": 0,
        "promotion_ready_bytes": 0,
        "issue_rows": len(set(issues)),
    }
    return summary, annotated_slots, low_rows + full_rows, gate_rules, []


def build_html(
    summary: dict[str, object],
    slots: list[dict[str, object]],
    fixed_rows: list[dict[str, object]],
    gate_rules: list[dict[str, object]],
    title: str,
) -> str:
    top_fixed = fixed_rows[:160]
    top_gates = gate_rules[:220]
    data_json = json.dumps(
        {"summary": summary, "fixedRows": top_fixed, "gateRules": top_gates, "slots": slots},
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
  <div class="box"><div class="num">{summary['slots']}</div><div class="muted">slots</div></div>
  <div class="box"><div class="num">{summary['fixed_low_best_exact_slots']}/{summary['fixed_low_best_false_slots']}</div><div class="muted">best fixed low exact/false</div></div>
  <div class="box"><div class="num">{summary['gate_best_exact_slots']}/{summary['gate_best_false_slots']}</div><div class="muted">best gated exact/false</div></div>
  <div class="box"><div class="num">{summary['gate_best_false_free_slots']}</div><div class="muted">best gated false-free slots</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Fixed window candidates</h2>{render_table(top_fixed, FIXED_FIELDNAMES)}</div>
<div class="panel"><h2>Gated window rules</h2>{render_table(top_gates, GATE_FIELDNAMES)}</div>
<div class="panel"><h2>Slots</h2>{render_table(slots, SLOT_FIELDNAMES)}</div>
<script type="application/json" id="gradient-sequence-high-safe-source-window-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe source-window grammar for gradient high-safe residuals.")
    parser.add_argument("--slots", type=Path, default=DEFAULT_SLOTS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--replay-fixtures", type=Path, default=DEFAULT_REPLAY_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--radius", type=int, default=64)
    parser.add_argument("--max-features", type=int, default=4)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Gradient Sequence High-Safe Source-Window Probe",
    )
    args = parser.parse_args()

    summary, slots, fixed_rows, gate_rules, _issues = build(
        read_csv(args.slots),
        read_csv(args.fixtures),
        read_csv(args.replay_fixtures),
        radius=args.radius,
        max_features=args.max_features,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "slots.csv", SLOT_FIELDNAMES, slots)
    write_csv(args.output / "fixed_candidates.csv", FIXED_FIELDNAMES, fixed_rows)
    write_csv(args.output / "gated_rules.csv", GATE_FIELDNAMES, gate_rules)
    (args.output / "index.html").write_text(build_html(summary, slots, fixed_rows, gate_rules, args.title))

    print(f"Slots: {summary['slots']}")
    print(
        "Best fixed low: "
        f"{summary['fixed_low_best_candidate']} = "
        f"{summary['fixed_low_best_exact_slots']} exact / "
        f"{summary['fixed_low_best_false_slots']} false"
    )
    print(
        "Best gated rule: "
        f"{summary['gate_best_candidate']} / {summary['gate_best_feature_set']} = "
        f"{summary['gate_best_exact_slots']} exact / {summary['gate_best_false_slots']} false"
    )
    print(f"Best gated false-free slots: {summary['gate_best_false_free_slots']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
