#!/usr/bin/env python3
"""Probe literal and spatial transforms inside deterministic skip/op8 gradient macro clusters."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_micro_jump_mixed_payload_probe import (
    DISTANCE_FIELDNAMES,
    fixture_key,
    load_sources,
    transform_byte,
)
from lolg_tex_micro_mixed_value_payload_state_opcode_probe import int_value, ratio


DEFAULT_INPUT_ROWS = Path("output/tex_gradient_macro_state_cluster_payload/rows.csv")
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_REPLAY_FIXTURES = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_fill_replay/fixtures.csv")
DEFAULT_OUTPUT = Path("output/tex_gradient_macro_state_cluster_literal")

SOURCE_POOLS = ("segment_gap", "control_prefix", "fragment", "decoded_replay")
TRANSFORMS = ("identity", "xor80", "xorff", "add1", "sub1", "add2", "sub2")

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "target_bytes",
    "source_pools",
    "transforms",
    "source_best_correct_bytes",
    "source_best_false_bytes",
    "source_exact_rows",
    "source_exact_bytes",
    "source_best_prefix_bytes",
    "source_best_pool",
    "source_best_transform",
    "source_best_row_correct_bytes",
    "source_best_row_ratio",
    "spatial_best_direction",
    "spatial_best_distance",
    "spatial_best_transform",
    "spatial_best_rows",
    "spatial_best_bytes",
    "spatial_best_correct_bytes",
    "spatial_best_false_bytes",
    "spatial_best_exact_rows",
    "spatial_back_distance1_correct_bytes",
    "spatial_back_distance1_bytes",
    "spatial_fwd_distance1_correct_bytes",
    "spatial_fwd_distance1_bytes",
    "spatial_back_distance320_correct_bytes",
    "spatial_back_distance320_bytes",
    "spatial_back_distance320_exact_rows",
    "spatial_fwd_distance320_correct_bytes",
    "spatial_fwd_distance320_bytes",
    "spatial_fwd_distance320_exact_rows",
    "promotion_ready_bytes",
    "issue_rows",
]

ROW_FIELDNAMES = [
    "rank",
    "cluster_key",
    "archive",
    "pcx_name",
    "frontier_id",
    "span_index",
    "op_index",
    "length",
    "start",
    "end",
    "fixture_rule",
    "fixture_opcode_pair",
    "fixture_hi_pair",
    "fixture_skip_bucket",
    "top_nibble",
    "gradient_class",
    "best_source_pool",
    "best_source_offset",
    "best_source_transform",
    "best_source_correct",
    "best_source_false",
    "best_source_prefix",
    "best_source_ratio",
    "best_spatial_direction",
    "best_spatial_distance",
    "best_spatial_transform",
    "best_spatial_correct",
    "best_spatial_false",
    "best_spatial_ratio",
    "distance1_back_correct",
    "distance1_fwd_correct",
    "distance320_back_correct",
    "distance320_fwd_correct",
    "payload_head_hex",
    "source_head_hex",
    "spatial_head_hex",
    "issues",
]

SOURCE_FIELDNAMES = [
    "pool",
    "transform",
    "rows",
    "bytes",
    "correct_bytes",
    "false_bytes",
    "exact_rows",
    "prefix_bytes",
    "sample_pcx",
    "sample_frontier_id",
    "verdict",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def transform_data(data: bytes, transform: str) -> bytes:
    if transform == "identity":
        return data
    return bytes(transform_byte(value, transform) for value in data)


def exact_count(left: bytes, right: bytes) -> int:
    return sum(1 for a, b in zip(left, right) if a == b)


def prefix_count(left: bytes, right: bytes) -> int:
    count = 0
    for a, b in zip(left, right):
        if a != b:
            break
        count += 1
    return count


def best_source_match(payload: bytes, sources: dict[str, bytes]) -> dict[str, object]:
    best: dict[str, object] = {
        "pool": "",
        "offset": "",
        "transform": "",
        "correct": 0,
        "false": len(payload),
        "prefix": 0,
        "head_hex": "",
    }
    for pool in SOURCE_POOLS:
        source = sources.get(pool, b"")
        if not source or len(source) < len(payload):
            continue
        for offset in range(len(source) - len(payload) + 1):
            chunk = source[offset : offset + len(payload)]
            for transform in TRANSFORMS:
                transformed = transform_data(chunk, transform)
                correct = exact_count(payload, transformed)
                prefix = prefix_count(payload, transformed)
                false = len(payload) - correct
                if (correct, prefix, -false) > (
                    int(best["correct"]),
                    int(best["prefix"]),
                    -int(best["false"]),
                ):
                    best = {
                        "pool": pool,
                        "offset": offset,
                        "transform": transform,
                        "correct": correct,
                        "false": false,
                        "prefix": prefix,
                        "head_hex": transformed[:16].hex(),
                    }
    return best


def spatial_match(
    payload: bytes,
    expected: bytes,
    start: int,
    end: int,
    direction: str,
    distance: int,
    transform: str,
) -> dict[str, object] | None:
    if direction == "back":
        source_start = start - distance
        source_end = end - distance
    else:
        source_start = start + distance
        source_end = end + distance
    if source_start < 0 or source_end > len(expected):
        return None
    source = expected[source_start:source_end]
    if len(source) != len(payload):
        return None
    transformed = transform_data(source, transform)
    correct = exact_count(payload, transformed)
    return {
        "direction": direction,
        "distance": distance,
        "transform": transform,
        "correct": correct,
        "false": len(payload) - correct,
        "head_hex": transformed[:16].hex(),
    }


def best_spatial_match(payload: bytes, expected: bytes, start: int, end: int, max_distance: int) -> dict[str, object]:
    best: dict[str, object] = {
        "direction": "",
        "distance": "",
        "transform": "",
        "correct": 0,
        "false": len(payload),
        "head_hex": "",
    }
    for direction in ("back", "fwd"):
        for distance in range(1, max_distance + 1):
            for transform in TRANSFORMS:
                match = spatial_match(payload, expected, start, end, direction, distance, transform)
                if not match:
                    continue
                if (int(match["correct"]), -int(match["false"]), -distance) > (
                    int(best["correct"]),
                    -int(best["false"]),
                    -int(best["distance"] or 999999),
                ):
                    best = match
    return best


def build_rows(
    input_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    replay_rows: list[dict[str, str]],
    *,
    max_distance: int,
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]], list[str]]:
    source_by_fixture, fixture_issues = load_sources(fixture_rows, replay_rows)
    rows: list[dict[str, object]] = []
    source_counters: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    source_samples: dict[tuple[str, str], dict[str, str]] = {}
    distance_counters: dict[tuple[str, int, str], Counter[str]] = defaultdict(Counter)
    distance_samples: dict[tuple[str, int, str], dict[str, str]] = {}
    issues: list[str] = list(fixture_issues)

    for input_row in input_rows:
        row_issues = [issue for issue in input_row.get("issues", "").split(";") if issue]
        sources = source_by_fixture.get(fixture_key(input_row), {})
        expected = sources.get("expected", b"")
        start = int_value(input_row, "start")
        end = int_value(input_row, "end")
        payload = expected[start:end]
        if not payload:
            row_issues.append("missing_expected_payload")
        if input_row.get("length") and int_value(input_row, "length") != len(payload):
            row_issues.append(f"length_mismatch:{input_row.get('length')}:{len(payload)}")

        source_best = best_source_match(payload, sources)
        spatial_best = best_spatial_match(payload, expected, start, end, max_distance)
        row_distance: dict[tuple[str, int], dict[str, object]] = {}

        for pool in SOURCE_POOLS:
            source = sources.get(pool, b"")
            if not source or len(source) < len(payload):
                continue
            for offset in range(len(source) - len(payload) + 1):
                chunk = source[offset : offset + len(payload)]
                for transform in TRANSFORMS:
                    transformed = transform_data(chunk, transform)
                    correct = exact_count(payload, transformed)
                    prefix = prefix_count(payload, transformed)
                    key = (pool, transform)
                    counter = source_counters[key]
                    counter["rows"] += 1
                    counter["bytes"] += len(payload)
                    counter["correct"] += correct
                    counter["false"] += len(payload) - correct
                    counter["exact_rows"] += 1 if correct == len(payload) else 0
                    counter["prefix"] += prefix
                    source_samples.setdefault(key, input_row)

        for direction in ("back", "fwd"):
            for distance in range(1, max_distance + 1):
                for transform in TRANSFORMS:
                    match = spatial_match(payload, expected, start, end, direction, distance, transform)
                    if not match:
                        continue
                    key = (direction, distance, transform)
                    counter = distance_counters[key]
                    counter["rows"] += 1
                    counter["bytes"] += len(payload)
                    counter["correct"] += int(match["correct"])
                    counter["false"] += int(match["false"])
                    counter["exact_rows"] += 1 if int(match["correct"]) == len(payload) else 0
                    distance_samples.setdefault(key, input_row)
                    if transform == "identity" and distance in {1, 320}:
                        row_distance[(direction, distance)] = match

        rows.append(
            {
                "rank": len(rows) + 1,
                "cluster_key": input_row.get("cluster_key", ""),
                "archive": input_row.get("archive", ""),
                "pcx_name": input_row.get("pcx_name", ""),
                "frontier_id": input_row.get("frontier_id", ""),
                "span_index": input_row.get("span_index", ""),
                "op_index": input_row.get("op_index", ""),
                "length": len(payload),
                "start": start,
                "end": end,
                "fixture_rule": input_row.get("fixture_rule", ""),
                "fixture_opcode_pair": input_row.get("fixture_opcode_pair", ""),
                "fixture_hi_pair": input_row.get("fixture_hi_pair", ""),
                "fixture_skip_bucket": input_row.get("fixture_skip_bucket", ""),
                "top_nibble": input_row.get("top_nibble", ""),
                "gradient_class": input_row.get("gradient_class", ""),
                "best_source_pool": source_best["pool"],
                "best_source_offset": source_best["offset"],
                "best_source_transform": source_best["transform"],
                "best_source_correct": source_best["correct"],
                "best_source_false": source_best["false"],
                "best_source_prefix": source_best["prefix"],
                "best_source_ratio": ratio(int(source_best["correct"]), len(payload)),
                "best_spatial_direction": spatial_best["direction"],
                "best_spatial_distance": spatial_best["distance"],
                "best_spatial_transform": spatial_best["transform"],
                "best_spatial_correct": spatial_best["correct"],
                "best_spatial_false": spatial_best["false"],
                "best_spatial_ratio": ratio(int(spatial_best["correct"]), len(payload)),
                "distance1_back_correct": row_distance.get(("back", 1), {}).get("correct", ""),
                "distance1_fwd_correct": row_distance.get(("fwd", 1), {}).get("correct", ""),
                "distance320_back_correct": row_distance.get(("back", 320), {}).get("correct", ""),
                "distance320_fwd_correct": row_distance.get(("fwd", 320), {}).get("correct", ""),
                "payload_head_hex": payload[:16].hex(),
                "source_head_hex": source_best["head_hex"],
                "spatial_head_hex": spatial_best["head_hex"],
                "issues": ";".join(row_issues),
            }
        )
        issues.extend(row_issues)

    source_rows: list[dict[str, object]] = []
    for (pool, transform), counter in source_counters.items():
        sample = source_samples[(pool, transform)]
        verdict = (
            "literal_exact_candidate"
            if counter["exact_rows"]
            else "literal_partial_review"
            if counter["correct"] >= counter["false"]
            else "literal_reject"
        )
        source_rows.append(
            {
                "pool": pool,
                "transform": transform,
                "rows": counter["rows"],
                "bytes": counter["bytes"],
                "correct_bytes": counter["correct"],
                "false_bytes": counter["false"],
                "exact_rows": counter["exact_rows"],
                "prefix_bytes": counter["prefix"],
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
                "verdict": verdict,
            }
        )
    source_rows.sort(
        key=lambda row: (-int_value(row, "correct_bytes"), int_value(row, "false_bytes"), str(row["pool"]))
    )

    distance_rows: list[dict[str, object]] = []
    for (direction, distance, transform), counter in distance_counters.items():
        sample = distance_samples[(direction, distance, transform)]
        verdict = (
            "spatial_exact_candidate"
            if counter["exact_rows"]
            else "spatial_partial_review"
            if counter["correct"] >= counter["false"]
            else "spatial_reject"
        )
        distance_rows.append(
            {
                "distance": distance,
                "rows": counter["rows"],
                "bytes": counter["bytes"],
                "correct_bytes": counter["correct"],
                "false_bytes": counter["false"],
                "exact_rows": counter["exact_rows"],
                "sample_pcx": f"{direction}:{transform}:{sample.get('pcx_name', '')}",
                "sample_frontier_id": sample.get("frontier_id", ""),
                "verdict": verdict,
            }
        )
    distance_rows.sort(
        key=lambda row: (-int_value(row, "correct_bytes"), int_value(row, "false_bytes"), int_value(row, "distance"))
    )
    return rows, source_rows, distance_rows, issues


def distance_entry(distance_rows: list[dict[str, object]], direction: str, distance: int) -> dict[str, object]:
    candidates = [
        row
        for row in distance_rows
        if int_value(row, "distance") == distance
        and str(row.get("sample_pcx", "")).startswith(f"{direction}:identity:")
    ]
    return candidates[0] if candidates else {}


def build_summary(
    rows: list[dict[str, object]],
    source_rows: list[dict[str, object]],
    distance_rows: list[dict[str, object]],
    issues: list[str],
) -> dict[str, object]:
    best_source_row = max(rows, key=lambda row: int_value(row, "best_source_correct"), default={})
    source_best_correct = sum(int_value(row, "best_source_correct") for row in rows)
    source_exact_rows = [row for row in rows if int_value(row, "best_source_correct") == int_value(row, "length")]
    best_spatial = distance_rows[0] if distance_rows else {}
    best_sample = str(best_spatial.get("sample_pcx", ""))
    direction = best_sample.split(":", 1)[0] if ":" in best_sample else ""
    transform = best_sample.split(":")[1] if best_sample.count(":") >= 2 else ""
    back1 = distance_entry(distance_rows, "back", 1)
    fwd1 = distance_entry(distance_rows, "fwd", 1)
    back320 = distance_entry(distance_rows, "back", 320)
    fwd320 = distance_entry(distance_rows, "fwd", 320)
    return {
        "scope": "total",
        "target_rows": len(rows),
        "target_bytes": sum(int_value(row, "length") for row in rows),
        "source_pools": len(SOURCE_POOLS),
        "transforms": len(TRANSFORMS),
        "source_best_correct_bytes": source_best_correct,
        "source_best_false_bytes": sum(int_value(row, "length") for row in rows) - source_best_correct,
        "source_exact_rows": len(source_exact_rows),
        "source_exact_bytes": sum(int_value(row, "length") for row in source_exact_rows),
        "source_best_prefix_bytes": sum(int_value(row, "best_source_prefix") for row in rows),
        "source_best_pool": best_source_row.get("best_source_pool", ""),
        "source_best_transform": best_source_row.get("best_source_transform", ""),
        "source_best_row_correct_bytes": best_source_row.get("best_source_correct", 0),
        "source_best_row_ratio": best_source_row.get("best_source_ratio", ""),
        "spatial_best_direction": direction,
        "spatial_best_distance": best_spatial.get("distance", ""),
        "spatial_best_transform": transform,
        "spatial_best_rows": best_spatial.get("rows", 0),
        "spatial_best_bytes": best_spatial.get("bytes", 0),
        "spatial_best_correct_bytes": best_spatial.get("correct_bytes", 0),
        "spatial_best_false_bytes": best_spatial.get("false_bytes", 0),
        "spatial_best_exact_rows": best_spatial.get("exact_rows", 0),
        "spatial_back_distance1_correct_bytes": back1.get("correct_bytes", 0),
        "spatial_back_distance1_bytes": back1.get("bytes", 0),
        "spatial_fwd_distance1_correct_bytes": fwd1.get("correct_bytes", 0),
        "spatial_fwd_distance1_bytes": fwd1.get("bytes", 0),
        "spatial_back_distance320_correct_bytes": back320.get("correct_bytes", 0),
        "spatial_back_distance320_bytes": back320.get("bytes", 0),
        "spatial_back_distance320_exact_rows": back320.get("exact_rows", 0),
        "spatial_fwd_distance320_correct_bytes": fwd320.get("correct_bytes", 0),
        "spatial_fwd_distance320_bytes": fwd320.get("bytes", 0),
        "spatial_fwd_distance320_exact_rows": fwd320.get("exact_rows", 0),
        "promotion_ready_bytes": 0,
        "issue_rows": len(issues),
    }


def render_table(rows: list[dict[str, object]], fields: list[str], limit: int = 220) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, object],
    rows: list[dict[str, object]],
    source_rows: list[dict[str, object]],
    distance_rows: list[dict[str, object]],
    title: str,
) -> str:
    data_json = json.dumps(
        {"summary": summary, "rows": rows, "sources": source_rows, "distances": distance_rows},
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
table {{ border-collapse: collapse; width: 100%; min-width: 1650px; }}
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
  <div class="box"><div class="num">{summary['target_bytes']}</div><div class="muted">target bytes</div></div>
  <div class="box"><div class="num">{summary['source_best_correct_bytes']}</div><div class="muted">source best correct</div></div>
  <div class="box"><div class="num">{summary['spatial_best_direction']} {summary['spatial_best_distance']}</div><div class="muted">best spatial</div></div>
  <div class="box"><div class="num">{summary['spatial_best_correct_bytes']}</div><div class="muted">spatial correct</div></div>
  <div class="box"><div class="num">{summary['spatial_back_distance320_exact_rows']}</div><div class="muted">back 320 exact rows</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Rows</h2>{render_table(rows, ROW_FIELDNAMES)}</div>
<div class="panel"><h2>Sources</h2>{render_table(source_rows, SOURCE_FIELDNAMES)}</div>
<div class="panel"><h2>Distances</h2>{render_table(distance_rows, DISTANCE_FIELDNAMES)}</div>
<script type="application/json" id="gradient-macro-state-cluster-literal-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe literal/geometric transforms inside skip/op8 macro clusters.")
    parser.add_argument("--input-rows", type=Path, default=DEFAULT_INPUT_ROWS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--replay-fixtures", type=Path, default=DEFAULT_REPLAY_FIXTURES)
    parser.add_argument("--max-distance", type=int, default=700)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Gradient Macro State Cluster Literal")
    args = parser.parse_args()

    rows, source_rows, distance_rows, issues = build_rows(
        read_csv(args.input_rows),
        read_csv(args.fixtures),
        read_csv(args.replay_fixtures),
        max_distance=args.max_distance,
    )
    summary = build_summary(rows, source_rows, distance_rows, issues)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "rows.csv", ROW_FIELDNAMES, rows)
    write_csv(args.output / "sources.csv", SOURCE_FIELDNAMES, source_rows)
    write_csv(args.output / "distances.csv", DISTANCE_FIELDNAMES, distance_rows)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, rows, source_rows, distance_rows, args.title))

    print(f"Target bytes: {summary['target_bytes']}")
    print(
        f"Best source total: {summary['source_best_correct_bytes']} correct, "
        f"{summary['source_best_false_bytes']} false"
    )
    print(
        f"Best spatial: {summary['spatial_best_direction']} {summary['spatial_best_distance']} "
        f"{summary['spatial_best_transform']} "
        f"{summary['spatial_best_correct_bytes']} / {summary['spatial_best_bytes']}"
    )
    print(
        f"Back distance 320: {summary['spatial_back_distance320_correct_bytes']} / "
        f"{summary['spatial_back_distance320_bytes']} "
        f"exact_rows={summary['spatial_back_distance320_exact_rows']}"
    )
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
