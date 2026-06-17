#!/usr/bin/env python3
"""Probe nonlocal gradient copies from already-known replay bytes."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_opcode_probe import write_csv


DEFAULT_GRADIENT_ROWS = Path("output/tex_gradient_payload_profile/rows.csv")
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_REPLAY_FIXTURES = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_formula_replay/fixtures.csv"
)
DEFAULT_OUTPUT = Path("output/tex_gradient_nonlocal_known_spatial")

DISTANCES = (1, 2, 3, 4, 8, 16, 32, 64, 128, 160, 256, 317, 319, 320, 321, 640)
TRANSFORMS = ("identity", "add1", "sub1", "add2", "sub2", "xor80", "xorff")

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "unknown_slots",
    "known_source_samples",
    "candidate_predictions",
    "distance_transforms",
    "false_free_rules",
    "low_false_rules",
    "best_distance",
    "best_transform",
    "best_exact_slots",
    "best_false_slots",
    "best_predicted_slots",
    "best_precision",
    "identity_back320_exact_slots",
    "identity_back320_false_slots",
    "identity_fwd320_exact_slots",
    "identity_fwd320_false_slots",
    "slots_with_exact_candidate",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

RULE_FIELDNAMES = [
    "rank",
    "distance",
    "direction",
    "transform",
    "predicted_slots",
    "exact_slots",
    "false_slots",
    "precision",
    "exact_rows",
    "verdict",
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
    "known_spatial_sources",
    "candidate_predictions",
    "exact_predictions",
    "first_exact_rule",
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


def transform_byte(value: int, transform: str) -> int:
    if transform == "identity":
        return value
    if transform == "add1":
        return (value + 1) & 0xFF
    if transform == "sub1":
        return (value - 1) & 0xFF
    if transform == "add2":
        return (value + 2) & 0xFF
    if transform == "sub2":
        return (value - 2) & 0xFF
    if transform == "xor80":
        return value ^ 0x80
    if transform == "xorff":
        return value ^ 0xFF
    raise ValueError(transform)


def build(
    gradient_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    replay_rows: list[dict[str, str]],
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    fixtures = {row_key(row): row for row in fixture_rows}
    replays = {row_key(row): row for row in replay_rows}
    rule_counts: dict[tuple[int, str], Counter[str]] = defaultdict(Counter)
    rule_rows: dict[tuple[int, str], set[str]] = defaultdict(set)
    slots: list[dict[str, object]] = []
    issues: list[str] = []
    unknown_slots = 0
    known_source_samples = 0
    candidate_predictions = 0

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
        if end > len(expected):
            local_issues.append("target_window_out_of_range")
        if len(decoded) != len(known_mask):
            local_issues.append("decoded_mask_length_mismatch")
        if local_issues:
            issues.extend(f"{'|'.join(key)}:{issue}" for issue in local_issues)
            if not expected or not decoded or not known_mask:
                continue

        row_id = "|".join((*key, str(start), str(end)))
        for target_offset in range(start, min(end, len(expected), len(known_mask))):
            if known_mask[target_offset]:
                continue
            unknown_slots += 1
            target = expected[target_offset]
            relative_offset = target_offset - start
            slot_sources = 0
            slot_predictions = 0
            exact_predictions = 0
            first_exact_rule = ""
            for sign in (-1, 1):
                for distance in DISTANCES:
                    source_offset = target_offset + sign * distance
                    if source_offset < 0 or source_offset >= len(decoded) or source_offset >= len(known_mask):
                        continue
                    if not known_mask[source_offset]:
                        continue
                    slot_sources += 1
                    known_source_samples += 1
                    source_value = decoded[source_offset]
                    signed_distance = sign * distance
                    for transform in TRANSFORMS:
                        predicted = transform_byte(source_value, transform)
                        exact = predicted == target
                        slot_predictions += 1
                        candidate_predictions += 1
                        rule_key = (signed_distance, transform)
                        counter = rule_counts[rule_key]
                        counter["predicted"] += 1
                        counter["exact"] += int(exact)
                        counter["false"] += int(not exact)
                        if exact:
                            exact_predictions += 1
                            rule_rows[rule_key].add(row_id)
                            if not first_exact_rule:
                                first_exact_rule = f"{signed_distance}:{transform}"
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
                    "known_spatial_sources": slot_sources,
                    "candidate_predictions": slot_predictions,
                    "exact_predictions": exact_predictions,
                    "first_exact_rule": first_exact_rule,
                }
            )

    rules: list[dict[str, object]] = []
    for (signed_distance, transform), counter in rule_counts.items():
        predicted = counter["predicted"]
        exact = counter["exact"]
        false = counter["false"]
        rules.append(
            {
                "rank": 0,
                "distance": signed_distance,
                "direction": "back" if signed_distance < 0 else "fwd",
                "transform": transform,
                "predicted_slots": predicted,
                "exact_slots": exact,
                "false_slots": false,
                "precision": ratio(exact, predicted),
                "exact_rows": len(rule_rows[(signed_distance, transform)]),
                "verdict": "false_free" if predicted and not false else "known_spatial_reject",
            }
        )
    rules.sort(
        key=lambda rule: (
            -int_value(rule, "exact_slots"),
            int_value(rule, "false_slots"),
            -int_value(rule, "predicted_slots"),
            int_value(rule, "distance"),
            str(rule["transform"]),
        )
    )
    for index, rule in enumerate(rules, start=1):
        rule["rank"] = index

    best = rules[0] if rules else {}
    by_key = {(int_value(rule, "distance"), str(rule["transform"])): rule for rule in rules}
    back320 = by_key.get((-320, "identity"), {})
    fwd320 = by_key.get((320, "identity"), {})
    summary = {
        "scope": "total",
        "target_rows": len(gradient_rows),
        "unknown_slots": unknown_slots,
        "known_source_samples": known_source_samples,
        "candidate_predictions": candidate_predictions,
        "distance_transforms": len(rules),
        "false_free_rules": sum(1 for rule in rules if int_value(rule, "false_slots") == 0),
        "low_false_rules": sum(
            1
            for rule in rules
            if int_value(rule, "exact_slots") >= 20 and int_value(rule, "false_slots") <= 5
        ),
        "best_distance": best.get("distance", ""),
        "best_transform": best.get("transform", ""),
        "best_exact_slots": best.get("exact_slots", 0),
        "best_false_slots": best.get("false_slots", 0),
        "best_predicted_slots": best.get("predicted_slots", 0),
        "best_precision": best.get("precision", "0.000000"),
        "identity_back320_exact_slots": back320.get("exact_slots", 0),
        "identity_back320_false_slots": back320.get("false_slots", 0),
        "identity_fwd320_exact_slots": fwd320.get("exact_slots", 0),
        "identity_fwd320_false_slots": fwd320.get("false_slots", 0),
        "slots_with_exact_candidate": sum(1 for slot in slots if int_value(slot, "exact_predictions") > 0),
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
    data_json = json.dumps({"summary": summary, "rules": rules, "slots": slots}, indent=2, sort_keys=True)
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
  <div class="box"><div class="num">{summary['unknown_slots']}</div><div class="muted">unknown gradient slots</div></div>
  <div class="box"><div class="num">{summary['known_source_samples']}</div><div class="muted">known spatial sources</div></div>
  <div class="box"><div class="num">{summary['best_exact_slots']}</div><div class="muted">best exact slots</div></div>
  <div class="box"><div class="num">{summary['best_false_slots']}</div><div class="muted">best false slots</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Rules</h2>{render_table(rules, RULE_FIELDNAMES)}</div>
<div class="panel"><h2>Slots</h2>{render_table(slots, SLOT_FIELDNAMES)}</div>
<script type="application/json" id="gradient-nonlocal-known-spatial-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe gradient copies from already-known nonlocal replay bytes.")
    parser.add_argument("--gradient-rows", type=Path, default=DEFAULT_GRADIENT_ROWS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--replay-fixtures", type=Path, default=DEFAULT_REPLAY_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Gradient Nonlocal Known-Spatial Probe")
    args = parser.parse_args()

    summary, slots, rules = build(
        read_csv(args.gradient_rows),
        read_csv(args.fixtures),
        read_csv(args.replay_fixtures),
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "slots.csv", SLOT_FIELDNAMES, slots)
    write_csv(args.output / "rules.csv", RULE_FIELDNAMES, rules)
    (args.output / "index.html").write_text(build_html(summary, slots, rules, args.title))

    print(f"Unknown slots: {summary['unknown_slots']}")
    print(f"Known spatial source samples: {summary['known_source_samples']}")
    print(
        "Best rule: "
        f"{summary['best_distance']} {summary['best_transform']} "
        f"{summary['best_exact_slots']} exact / {summary['best_false_slots']} false"
    )
    print(f"False-free rules: {summary['false_free_rules']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
