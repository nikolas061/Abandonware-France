#!/usr/bin/env python3
"""Probe source-known vertical copies after flat-walk palette formula replay."""

from __future__ import annotations

import argparse
import html
import itertools
import json
from collections import defaultdict
from pathlib import Path

from lolg_tex_gap_decoder_len64_promoted_replay import read_csv, render_table
from lolg_tex_gap_opcode_probe import int_value, write_csv
from lolg_tex_gap_decoder_seed_replay import fixture_key


DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_REPLAY_FIXTURES = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_formula_replay/fixtures.csv"
)
DEFAULT_OUTPUT = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_post_formula_vertical_copy_probe"
)
DEFAULT_DISTANCE = 320

FEATURES = [
    "x",
    "x_bucket16",
    "x_bucket32",
    "y",
    "offset_mod8",
    "offset_mod16",
    "source_byte",
    "source_high",
    "source_low",
    "frontier_id",
    "frontier_type",
    "rule_type",
    "opcode0",
    "opcode1",
]

SUMMARY_FIELDNAMES = [
    "scope",
    "fixture_rows",
    "replay_fixture_rows",
    "distance",
    "source_known_unknown_slots",
    "copy_exact_bytes",
    "copy_false_bytes",
    "copy_precision",
    "feature_sets",
    "false_free_repeated_rule_sets",
    "false_free_repeated_bytes",
    "best_false_free_feature_set",
    "best_false_free_bytes",
    "best_false_free_groups",
    "best_false_free_sample",
    "broad_copy_exact_bytes",
    "broad_copy_false_bytes",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

CANDIDATE_FIELDNAMES = [
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "target_offset",
    "source_offset",
    "x",
    "x_bucket16",
    "x_bucket32",
    "y",
    "offset_mod8",
    "offset_mod16",
    "source_byte",
    "source_high",
    "source_low",
    "expected_byte",
    "frontier_type",
    "rule_type",
    "opcode0",
    "opcode1",
    "exact",
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


def context_for(row: dict[str, object], features: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(str(row.get(feature, "")) for feature in features)


def feature_sets(max_features: int) -> list[tuple[str, ...]]:
    output: list[tuple[str, ...]] = []
    for size in range(1, max_features + 1):
        output.extend(itertools.combinations(FEATURES, size))
    return output


def build_candidates(
    fixture_rows: list[dict[str, str]],
    replay_rows: list[dict[str, str]],
    *,
    distance: int,
) -> tuple[list[dict[str, object]], list[str]]:
    manifests = {fixture_key(row): row for row in fixture_rows}
    candidates: list[dict[str, object]] = []
    issues: list[str] = []
    for replay in replay_rows:
        key = fixture_key(replay)
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
        limit = min(len(expected), len(decoded), len(known_mask))
        for target_offset in range(distance, limit):
            source_offset = target_offset - distance
            if known_mask[target_offset]:
                continue
            if not known_mask[source_offset]:
                continue
            source_value = decoded[source_offset]
            if source_value == 0:
                continue
            expected_value = expected[target_offset]
            x = target_offset % distance
            y = target_offset // distance
            exact = source_value == expected_value
            candidates.append(
                {
                    "rank": len(candidates) + 1,
                    "archive": replay.get("archive", ""),
                    "archive_tag": replay.get("archive_tag", ""),
                    "pcx_name": replay.get("pcx_name", ""),
                    "frontier_id": replay.get("frontier_id", ""),
                    "target_offset": target_offset,
                    "source_offset": source_offset,
                    "x": str(x),
                    "x_bucket16": str(x // 16),
                    "x_bucket32": str(x // 32),
                    "y": str(y),
                    "offset_mod8": str(target_offset % 8),
                    "offset_mod16": str(target_offset % 16),
                    "source_byte": f"{source_value:02x}",
                    "source_high": f"{source_value >> 4:x}",
                    "source_low": f"{source_value & 0x0F:x}",
                    "expected_byte": f"{expected_value:02x}",
                    "frontier_type": manifest.get("frontier_type", ""),
                    "rule_type": manifest.get("rule_type", ""),
                    "opcode0": manifest.get("opcode0_hex", ""),
                    "opcode1": manifest.get("opcode1_hex", ""),
                    "exact": 1 if exact else 0,
                    "verdict": "vertical_copy_exact" if exact else "vertical_copy_false",
                }
            )
    return candidates, issues


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
        verdict = "position_specific_copy_review"
    elif false_free_bytes:
        verdict = "false_free_vertical_copy_review"
    else:
        verdict = "vertical_copy_reject"
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
    fixture_rows: list[dict[str, str]],
    replay_rows: list[dict[str, str]],
    *,
    distance: int,
    max_features: int,
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    candidates, issues = build_candidates(fixture_rows, replay_rows, distance=distance)
    rules = [evaluate_rule(candidates, features) for features in feature_sets(max_features)]
    rules = [rule for rule in rules if int_value(rule, "false_free_repeated_bytes") > 0]
    rules.sort(
        key=lambda row: (
            -int_value(row, "false_free_repeated_bytes"),
            int_value(row, "feature_count"),
            str(row.get("feature_set", "")),
        )
    )
    for index, rule in enumerate(rules, start=1):
        rule["rank"] = index
    copy_exact = sum(int_value(row, "exact") for row in candidates)
    copy_false = len(candidates) - copy_exact
    false_free_bytes = sum(int_value(rule, "false_free_repeated_bytes") for rule in rules)
    best = rules[0] if rules else {}
    summary = {
        "scope": "total",
        "fixture_rows": len(fixture_rows),
        "replay_fixture_rows": len(replay_rows),
        "distance": distance,
        "source_known_unknown_slots": len(candidates),
        "copy_exact_bytes": copy_exact,
        "copy_false_bytes": copy_false,
        "copy_precision": ratio(copy_exact, len(candidates)),
        "feature_sets": len(feature_sets(max_features)),
        "false_free_repeated_rule_sets": len(rules),
        "false_free_repeated_bytes": false_free_bytes,
        "best_false_free_feature_set": best.get("feature_set", ""),
        "best_false_free_bytes": best.get("false_free_repeated_bytes", 0),
        "best_false_free_groups": best.get("false_free_repeated_groups", 0),
        "best_false_free_sample": best.get("sample_false_free_groups", ""),
        "broad_copy_exact_bytes": copy_exact,
        "broad_copy_false_bytes": copy_false,
        "promotion_candidate_bytes": 0,
        "promotion_ready_bytes": 0,
        "issue_rows": len(issues),
    }
    return summary, candidates, rules


def build_html(
    summary: dict[str, object],
    candidates: list[dict[str, object]],
    rules: list[dict[str, object]],
    title: str,
) -> str:
    data_json = json.dumps({"summary": summary, "candidates": candidates, "rules": rules}, indent=2, sort_keys=True)
    rendered_rules = [{key: str(value) for key, value in row.items()} for row in rules[:80]]
    rendered_candidates = [{key: str(value) for key, value in row.items()} for row in candidates[:240]]
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 2rem; background: #f7f4ee; color: #1f2933; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 1rem; }}
.box, .panel {{ background: white; border: 1px solid #d8d1c4; border-radius: 6px; padding: 1rem; }}
.num {{ font-size: 1.8rem; font-weight: 700; }}
.muted {{ color: #6b7280; }}
table {{ border-collapse: collapse; width: 100%; font-size: 0.85rem; }}
th, td {{ border-bottom: 1px solid #e5e7eb; padding: 0.35rem 0.45rem; text-align: left; vertical-align: top; }}
th {{ background: #f3efe7; position: sticky; top: 0; }}
.panel {{ margin-top: 1rem; overflow-x: auto; }}
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<div class="grid">
  <div class="box"><div class="num">{summary['source_known_unknown_slots']}</div><div class="muted">source-known unknown slots</div></div>
  <div class="box"><div class="num">{summary['copy_exact_bytes']}</div><div class="muted">copy-exact bytes</div></div>
  <div class="box"><div class="num">{summary['copy_false_bytes']}</div><div class="muted">copy-false bytes</div></div>
  <div class="box"><div class="num">{summary['best_false_free_bytes']}</div><div class="muted">best false-free repeated bytes</div></div>
  <div class="box"><div class="num">{summary['promotion_candidate_bytes']}</div><div class="muted">promotion candidates</div></div>
</div>
<div class="panel"><h2>False-free repeated contexts</h2>{render_table(rendered_rules, RULE_FIELDNAMES)}</div>
<div class="panel"><h2>Vertical copy candidates</h2>{render_table(rendered_candidates, CANDIDATE_FIELDNAMES)}</div>
<script type="application/json" id="post-formula-vertical-copy-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe post-formula source-known vertical copies.")
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--replay-fixtures", type=Path, default=DEFAULT_REPLAY_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--distance", type=int, default=DEFAULT_DISTANCE)
    parser.add_argument("--max-features", type=int, default=3)
    parser.add_argument("--title", default="Lands of Lore II .tex Post-Formula Vertical Copy Probe")
    args = parser.parse_args()

    fixture_rows = read_csv(args.fixtures)
    replay_rows = read_csv(args.replay_fixtures)
    summary, candidates, rules = build(
        fixture_rows,
        replay_rows,
        distance=args.distance,
        max_features=args.max_features,
    )

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "candidates.csv", CANDIDATE_FIELDNAMES, candidates)
    write_csv(args.output / "rules.csv", RULE_FIELDNAMES, rules)
    (args.output / "index.html").write_text(build_html(summary, candidates, rules, args.title))

    print(f"Post-formula vertical copy slots: {summary['source_known_unknown_slots']}")
    print(f"Exact/false bytes: {summary['copy_exact_bytes']}/{summary['copy_false_bytes']}")
    print(f"Best false-free repeated bytes: {summary['best_false_free_bytes']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
