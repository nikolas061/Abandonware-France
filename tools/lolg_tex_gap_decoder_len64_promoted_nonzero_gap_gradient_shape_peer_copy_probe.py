#!/usr/bin/env python3
"""Probe same-shape peer byte copies for unresolved gradient .tex rows."""

from __future__ import annotations

import argparse
import html
import itertools
import json
from collections import defaultdict
from pathlib import Path

from lolg_tex_gap_decoder_len64_promoted_replay import read_csv, render_table
from lolg_tex_gap_opcode_probe import int_value, write_csv


DEFAULT_GRADIENT_ROWS = Path("output/tex_gradient_macro_state_cluster/rows.csv")
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_REPLAY_FIXTURES = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_formula_replay/fixtures.csv"
)
DEFAULT_OUTPUT = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_shape_peer_copy_probe"
)

SELECTOR_FIELDS = [
    "band_shape_key",
    "step_shape_key",
    "gradient_class",
    "length_band8",
]

FEATURES = [
    "selector_family",
    "selector_key",
    "gradient_class",
    "length_band8",
    "top_nibble",
    "dominant_delta",
    "rel_mod8",
    "rel_mod16",
    "x_mod8",
    "y_mod4",
    "y_mod8",
    "prediction_high",
    "prediction_low",
    "source_peer_count",
]

SUMMARY_FIELDNAMES = [
    "scope",
    "gradient_rows",
    "fixture_rows",
    "replay_fixture_rows",
    "unknown_gradient_slots",
    "selector_families",
    "candidate_slots",
    "copy_exact_bytes",
    "copy_false_bytes",
    "copy_precision",
    "false_free_repeated_rule_sets",
    "false_free_repeated_bytes",
    "best_false_free_feature_set",
    "best_false_free_bytes",
    "best_false_free_groups",
    "best_selector_family",
    "best_selector_candidates",
    "best_selector_exact_bytes",
    "best_selector_false_bytes",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

CANDIDATE_FIELDNAMES = [
    "rank",
    "selector_family",
    "selector_key",
    "archive",
    "pcx_name",
    "frontier_id",
    "span_index",
    "op_index",
    "start",
    "end",
    "length",
    "target_offset",
    "relative_offset",
    "x",
    "y",
    "rel_mod8",
    "rel_mod16",
    "x_mod8",
    "y_mod4",
    "y_mod8",
    "gradient_class",
    "length_band8",
    "top_nibble",
    "dominant_delta",
    "prediction_byte",
    "prediction_high",
    "prediction_low",
    "expected_byte",
    "source_peer_count",
    "source_peer_rows",
    "exact",
    "verdict",
]

FAMILY_FIELDNAMES = [
    "selector_family",
    "groups",
    "candidate_slots",
    "copy_exact_bytes",
    "copy_false_bytes",
    "copy_precision",
    "deterministic_peer_groups",
    "sample_selector_key",
    "verdict",
]

RULE_FIELDNAMES = [
    "rank",
    "feature_set",
    "feature_count",
    "groups",
    "repeated_groups",
    "false_free_repeated_groups",
    "false_free_repeated_bytes",
    "exact_bytes",
    "false_bytes",
    "precision",
    "sample_false_free_groups",
    "sample_false_groups",
    "verdict",
]


def ratio(numerator: int, denominator: int) -> str:
    return f"{numerator / denominator:.6f}" if denominator else "0.000000"


def row_key(row: dict[str, str] | dict[str, object]) -> tuple[str, str, str]:
    return (
        str(row.get("archive", "")),
        str(row.get("pcx_name", "")),
        str(row.get("frontier_id", "")),
    )


def load_replay_buffers(
    fixture_rows: list[dict[str, str]],
    replay_rows: list[dict[str, str]],
) -> tuple[dict[tuple[str, str, str], tuple[bytes, bytes, bytes]], list[str]]:
    manifests = {row_key(row): row for row in fixture_rows}
    buffers: dict[tuple[str, str, str], tuple[bytes, bytes, bytes]] = {}
    issues: list[str] = []
    for replay in replay_rows:
        key = row_key(replay)
        manifest = manifests.get(key)
        if manifest is None:
            issues.append(f"missing_manifest:{key}")
            continue
        try:
            expected = Path(manifest.get("expected_gap_path", "")).read_bytes()
            decoded = Path(replay.get("decoded_path", "")).read_bytes()
            known_mask = Path(replay.get("known_mask_path", "")).read_bytes()
        except OSError as exc:
            issues.append(f"read_failed:{key}:{exc}")
            continue
        buffers[key] = (expected, decoded, known_mask)
    return buffers, issues


def row_length(row: dict[str, str] | dict[str, object]) -> int:
    return int_value(row, "length")


def group_rows(rows: list[dict[str, str]], selector_field: str) -> dict[str, list[dict[str, str]]]:
    output: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        output[row.get(selector_field, "")].append(row)
    return output


def candidate_for(
    *,
    selector_family: str,
    selector_key: str,
    target: dict[str, str],
    peers: list[dict[str, str]],
    buffers: dict[tuple[str, str, str], tuple[bytes, bytes, bytes]],
    target_offset: int,
    relative_offset: int,
) -> dict[str, object] | None:
    target_buffer = buffers.get(row_key(target))
    if target_buffer is None:
        return None
    expected, _decoded, _known_mask = target_buffer
    peer_values: list[int] = []
    peer_rows: list[str] = []
    for peer in peers:
        if peer is target or row_length(peer) <= relative_offset:
            continue
        peer_buffer = buffers.get(row_key(peer))
        if peer_buffer is None:
            continue
        _peer_expected, peer_decoded, peer_known_mask = peer_buffer
        peer_offset = int_value(peer, "start") + relative_offset
        if peer_offset >= min(len(peer_decoded), len(peer_known_mask)):
            continue
        if not peer_known_mask[peer_offset]:
            continue
        value = peer_decoded[peer_offset]
        if value == 0:
            continue
        peer_values.append(value)
        peer_rows.append(
            f"{peer.get('pcx_name', '')}:{peer.get('frontier_id', '')}:"
            f"{peer.get('span_index', '')}:{peer.get('op_index', '')}"
        )
    unique_values = sorted(set(peer_values))
    if len(unique_values) != 1:
        return None
    prediction = unique_values[0]
    if target_offset >= len(expected):
        return None
    expected_value = expected[target_offset]
    x = target_offset % 320
    y = target_offset // 320
    exact = prediction == expected_value
    return {
        "rank": 0,
        "selector_family": selector_family,
        "selector_key": selector_key,
        "archive": target.get("archive", ""),
        "pcx_name": target.get("pcx_name", ""),
        "frontier_id": target.get("frontier_id", ""),
        "span_index": target.get("span_index", ""),
        "op_index": target.get("op_index", ""),
        "start": target.get("start", ""),
        "end": target.get("end", ""),
        "length": target.get("length", ""),
        "target_offset": target_offset,
        "relative_offset": relative_offset,
        "x": x,
        "y": y,
        "rel_mod8": relative_offset % 8,
        "rel_mod16": relative_offset % 16,
        "x_mod8": x % 8,
        "y_mod4": y % 4,
        "y_mod8": y % 8,
        "gradient_class": target.get("gradient_class", ""),
        "length_band8": target.get("length_band8", ""),
        "top_nibble": target.get("top_nibble", ""),
        "dominant_delta": target.get("dominant_delta", ""),
        "prediction_byte": f"{prediction:02x}",
        "prediction_high": f"{prediction >> 4:x}",
        "prediction_low": f"{prediction & 0x0F:x}",
        "expected_byte": f"{expected_value:02x}",
        "source_peer_count": len(peer_values),
        "source_peer_rows": "|".join(peer_rows[:8]),
        "exact": 1 if exact else 0,
        "verdict": "shape_peer_copy_exact" if exact else "shape_peer_copy_false",
    }


def build_candidates(
    gradient_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    replay_rows: list[dict[str, str]],
) -> tuple[list[dict[str, object]], int, list[str]]:
    buffers, issues = load_replay_buffers(fixture_rows, replay_rows)
    unknown_slots = 0
    candidates: list[dict[str, object]] = []
    for target in gradient_rows:
        buffer = buffers.get(row_key(target))
        if buffer is None:
            issues.append(f"missing_replay_buffer:{row_key(target)}")
            continue
        _expected, _decoded, known_mask = buffer
        start = int_value(target, "start")
        end = min(int_value(target, "end"), len(known_mask))
        for offset in range(start, end):
            if not known_mask[offset]:
                unknown_slots += 1

    for selector_family in SELECTOR_FIELDS:
        groups = group_rows(gradient_rows, selector_family)
        for selector_key, peers in groups.items():
            if len(peers) < 2:
                continue
            for target in peers:
                buffer = buffers.get(row_key(target))
                if buffer is None:
                    continue
                _expected, _decoded, known_mask = buffer
                start = int_value(target, "start")
                end = min(int_value(target, "end"), len(known_mask))
                for target_offset in range(start, end):
                    if known_mask[target_offset]:
                        continue
                    relative_offset = target_offset - start
                    candidate = candidate_for(
                        selector_family=selector_family,
                        selector_key=selector_key,
                        target=target,
                        peers=peers,
                        buffers=buffers,
                        target_offset=target_offset,
                        relative_offset=relative_offset,
                    )
                    if candidate is not None:
                        candidates.append(candidate)

    candidates.sort(
        key=lambda row: (
            str(row.get("selector_family", "")),
            str(row.get("selector_key", "")),
            str(row.get("pcx_name", "")),
            int_value(row, "frontier_id"),
            int_value(row, "target_offset"),
        )
    )
    for index, row in enumerate(candidates, start=1):
        row["rank"] = index
    return candidates, unknown_slots, issues


def build_family_rows(candidates: list[dict[str, object]]) -> list[dict[str, object]]:
    by_family: dict[str, list[dict[str, object]]] = defaultdict(list)
    keys_by_family: dict[str, set[str]] = defaultdict(set)
    for row in candidates:
        family = str(row.get("selector_family", ""))
        by_family[family].append(row)
        keys_by_family[family].add(str(row.get("selector_key", "")))

    output: list[dict[str, object]] = []
    for family in SELECTOR_FIELDS:
        rows = by_family.get(family, [])
        exact = sum(int_value(row, "exact") for row in rows)
        false = len(rows) - exact
        verdict = (
            "shape_peer_copy_reject"
            if false
            else "shape_peer_copy_no_candidates"
            if not rows
            else "shape_peer_copy_review"
        )
        output.append(
            {
                "selector_family": family,
                "groups": len(keys_by_family.get(family, set())),
                "candidate_slots": len(rows),
                "copy_exact_bytes": exact,
                "copy_false_bytes": false,
                "copy_precision": ratio(exact, len(rows)),
                "deterministic_peer_groups": len(
                    {
                        str(row.get("selector_key", ""))
                        for row in rows
                    }
                ),
                "sample_selector_key": rows[0].get("selector_key", "") if rows else "",
                "verdict": verdict,
            }
        )
    output.sort(
        key=lambda row: (
            -int_value(row, "candidate_slots"),
            -int_value(row, "copy_exact_bytes"),
            str(row.get("selector_family", "")),
        )
    )
    return output


def context_for(row: dict[str, object], features: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(str(row.get(feature, "")) for feature in features)


def feature_sets(max_features: int) -> list[tuple[str, ...]]:
    output: list[tuple[str, ...]] = []
    for size in range(1, max_features + 1):
        output.extend(itertools.combinations(FEATURES, size))
    return output


def evaluate_rule(rows: list[dict[str, object]], features: tuple[str, ...]) -> dict[str, object]:
    groups: dict[tuple[str, ...], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        groups[context_for(row, features)].append(row)
    false_free_groups: list[tuple[tuple[str, ...], list[dict[str, object]]]] = []
    false_groups: list[tuple[tuple[str, ...], list[dict[str, object]]]] = []
    exact_bytes = 0
    false_bytes = 0
    repeated_groups = 0
    for context, group in groups.items():
        exact = sum(int_value(row, "exact") for row in group)
        false = len(group) - exact
        exact_bytes += exact
        false_bytes += false
        if len(group) <= 1:
            continue
        repeated_groups += 1
        if exact and not false:
            false_free_groups.append((context, group))
        elif false:
            false_groups.append((context, group))

    false_free_bytes = sum(len(group) for _context, group in false_free_groups)
    sample_false_free = [
        f"{'|'.join(context)}:{len(group)}"
        for context, group in false_free_groups[:8]
    ]
    sample_false = [
        f"{'|'.join(context)}:{sum(1 for row in group if not int_value(row, 'exact'))}/{len(group)}"
        for context, group in false_groups[:8]
    ]
    if false_free_bytes and false_bytes:
        verdict = "shape_peer_copy_position_specific"
    elif false_free_bytes:
        verdict = "shape_peer_copy_false_free_review"
    else:
        verdict = "shape_peer_copy_reject"
    return {
        "rank": 0,
        "feature_set": "+".join(features),
        "feature_count": len(features),
        "groups": len(groups),
        "repeated_groups": repeated_groups,
        "false_free_repeated_groups": len(false_free_groups),
        "false_free_repeated_bytes": false_free_bytes,
        "exact_bytes": exact_bytes,
        "false_bytes": false_bytes,
        "precision": ratio(exact_bytes, exact_bytes + false_bytes),
        "sample_false_free_groups": "|".join(sample_false_free),
        "sample_false_groups": "|".join(sample_false),
        "verdict": verdict,
    }


def build(
    gradient_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    replay_rows: list[dict[str, str]],
    *,
    max_features: int,
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    candidates, unknown_slots, issues = build_candidates(gradient_rows, fixture_rows, replay_rows)
    family_rows = build_family_rows(candidates)
    rules = [evaluate_rule(candidates, features) for features in feature_sets(max_features)]
    rules = [rule for rule in rules if int_value(rule, "false_free_repeated_bytes") > 0]
    rules.sort(
        key=lambda row: (
            -int_value(row, "false_free_repeated_bytes"),
            int_value(row, "feature_count"),
            str(row.get("feature_set", "")),
        )
    )
    for index, row in enumerate(rules, start=1):
        row["rank"] = index

    copy_exact = sum(int_value(row, "exact") for row in candidates)
    copy_false = len(candidates) - copy_exact
    best_rule = rules[0] if rules else {}
    best_family = max(
        family_rows,
        key=lambda row: (
            int_value(row, "copy_exact_bytes"),
            -int_value(row, "copy_false_bytes"),
            int_value(row, "candidate_slots"),
        ),
        default={},
    )
    summary = {
        "scope": "total",
        "gradient_rows": len(gradient_rows),
        "fixture_rows": len(fixture_rows),
        "replay_fixture_rows": len(replay_rows),
        "unknown_gradient_slots": unknown_slots,
        "selector_families": len(SELECTOR_FIELDS),
        "candidate_slots": len(candidates),
        "copy_exact_bytes": copy_exact,
        "copy_false_bytes": copy_false,
        "copy_precision": ratio(copy_exact, len(candidates)),
        "false_free_repeated_rule_sets": len(rules),
        "false_free_repeated_bytes": sum(int_value(row, "false_free_repeated_bytes") for row in rules),
        "best_false_free_feature_set": best_rule.get("feature_set", ""),
        "best_false_free_bytes": best_rule.get("false_free_repeated_bytes", 0),
        "best_false_free_groups": best_rule.get("false_free_repeated_groups", 0),
        "best_selector_family": best_family.get("selector_family", ""),
        "best_selector_candidates": best_family.get("candidate_slots", 0),
        "best_selector_exact_bytes": best_family.get("copy_exact_bytes", 0),
        "best_selector_false_bytes": best_family.get("copy_false_bytes", 0),
        "promotion_candidate_bytes": 0,
        "promotion_ready_bytes": 0,
        "issue_rows": len(issues),
    }
    return summary, candidates, family_rows, rules


def build_html(
    summary: dict[str, object],
    candidates: list[dict[str, object]],
    family_rows: list[dict[str, object]],
    rules: list[dict[str, object]],
    title: str,
) -> str:
    data_json = json.dumps(
        {"summary": summary, "candidates": candidates, "families": family_rows, "rules": rules},
        indent=2,
        sort_keys=True,
    )
    rendered_candidates = [{key: str(value) for key, value in row.items()} for row in candidates[:240]]
    rendered_families = [{key: str(value) for key, value in row.items()} for row in family_rows]
    rendered_rules = [{key: str(value) for key, value in row.items()} for row in rules[:80]]
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
  <div class="box"><div class="num">{summary['unknown_gradient_slots']}</div><div class="muted">unknown gradient slots</div></div>
  <div class="box"><div class="num">{summary['candidate_slots']}</div><div class="muted">peer-copy candidates</div></div>
  <div class="box"><div class="num">{summary['copy_exact_bytes']}</div><div class="muted">exact bytes</div></div>
  <div class="box"><div class="num">{summary['copy_false_bytes']}</div><div class="muted">false bytes</div></div>
  <div class="box"><div class="num">{summary['best_false_free_bytes']}</div><div class="muted">best false-free repeated bytes</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Selector families</h2>{render_table(rendered_families, FAMILY_FIELDNAMES)}</div>
<div class="panel"><h2>False-free repeated contexts</h2>{render_table(rendered_rules, RULE_FIELDNAMES)}</div>
<div class="panel"><h2>Peer-copy candidates</h2>{render_table(rendered_candidates, CANDIDATE_FIELDNAMES)}</div>
<script type="application/json" id="gradient-shape-peer-copy-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe same-shape peer copies for unresolved gradient .tex bytes.")
    parser.add_argument("--gradient-rows", type=Path, default=DEFAULT_GRADIENT_ROWS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--replay-fixtures", type=Path, default=DEFAULT_REPLAY_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-features", type=int, default=3)
    parser.add_argument("--title", default="Lands of Lore II .tex Gradient Shape Peer Copy Probe")
    args = parser.parse_args()

    summary, candidates, family_rows, rules = build(
        read_csv(args.gradient_rows),
        read_csv(args.fixtures),
        read_csv(args.replay_fixtures),
        max_features=args.max_features,
    )

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "candidates.csv", CANDIDATE_FIELDNAMES, candidates)
    write_csv(args.output / "families.csv", FAMILY_FIELDNAMES, family_rows)
    write_csv(args.output / "rules.csv", RULE_FIELDNAMES, rules)
    (args.output / "index.html").write_text(build_html(summary, candidates, family_rows, rules, args.title))

    print(f"Unknown gradient slots: {summary['unknown_gradient_slots']}")
    print(f"Peer-copy candidates: {summary['candidate_slots']}")
    print(f"Exact/false bytes: {summary['copy_exact_bytes']}/{summary['copy_false_bytes']}")
    print(f"Best false-free repeated bytes: {summary['best_false_free_bytes']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
