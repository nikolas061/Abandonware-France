#!/usr/bin/env python3
"""Probe spatial/backref distances for dominant mixed-value payloads."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path


DEFAULT_INPUT_ROWS = Path("output/tex_micro_mixed_value_dominant_control/rows.csv")
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_REPLAY_FIXTURES = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_fill_replay/fixtures.csv")
DEFAULT_OUTPUT = Path("output/tex_micro_mixed_value_payload_spatial")

FOCUS_DISTANCES = (1, 2, 3, 4, 8, 16, 32, 64, 128, 256, 319, 320, 321, 322, 640)

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "target_bytes",
    "focus_distances",
    "best_aggregate_distance",
    "best_aggregate_correct_bytes",
    "best_aggregate_false_bytes",
    "best_aggregate_known_source_bytes",
    "best_per_row_correct_bytes",
    "best_per_row_false_bytes",
    "distance1_correct_bytes",
    "distance1_false_bytes",
    "distance320_rows",
    "distance320_bytes",
    "distance320_correct_bytes",
    "distance320_false_bytes",
    "distance320_known_source_bytes",
    "exact_copy_rows",
    "exact_copy_bytes",
    "known_exact_copy_rows",
    "known_exact_copy_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

ROW_FIELDNAMES = [
    "rank",
    "archive",
    "pcx_name",
    "frontier_id",
    "span_index",
    "op_index",
    "length",
    "start",
    "end",
    "control_ref_mod64",
    "best_signal_key",
    "best_distance",
    "best_correct_bytes",
    "best_false_bytes",
    "best_known_source_bytes",
    "best_precision",
    "distance1_correct_bytes",
    "distance1_false_bytes",
    "distance320_correct_bytes",
    "distance320_false_bytes",
    "distance320_known_source_bytes",
    "verdict",
    "head_hex",
    "source_head_hex",
    "issues",
]

DISTANCE_FIELDNAMES = [
    "distance",
    "rows",
    "bytes",
    "correct_bytes",
    "false_bytes",
    "known_source_bytes",
    "precision",
    "known_ratio",
    "exact_rows",
    "known_exact_rows",
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


def int_value(row: dict[str, str] | dict[str, object], field: str) -> int:
    try:
        return int(row.get(field, "") or 0)
    except (TypeError, ValueError):
        return 0


def ratio(numerator: int, denominator: int) -> str:
    return f"{(numerator / denominator) if denominator else 0.0:.6f}"


def fixture_key(row: dict[str, str] | dict[str, object]) -> tuple[str, str, str]:
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


def load_expected_and_masks(
    fixture_rows: list[dict[str, str]],
    replay_rows: list[dict[str, str]],
) -> tuple[dict[tuple[str, str, str], dict[str, bytes]], list[str]]:
    replay_by_key = {fixture_key(row): row for row in replay_rows}
    data: dict[tuple[str, str, str], dict[str, bytes]] = {}
    issues: list[str] = []
    for fixture in fixture_rows:
        key = fixture_key(fixture)
        replay = replay_by_key.get(key, {})
        local_issues: list[str] = []
        data[key] = {
            "expected": read_bytes(fixture.get("expected_gap_path", ""), local_issues, "expected"),
            "known_mask": read_bytes(replay.get("known_mask_path", ""), local_issues, "known_mask"),
        }
        issues.extend(f"{key}:{issue}" for issue in local_issues)
    return data, issues


def score_distance(expected_all: bytes, known_mask: bytes, start: int, end: int, distance: int) -> dict[str, object] | None:
    if distance <= 0 or start - distance < 0:
        return None
    target = expected_all[start:end]
    source = expected_all[start - distance : end - distance]
    if len(source) != len(target):
        return None
    correct = sum(1 for left, right in zip(source, target) if left == right)
    known = 0
    if len(known_mask) >= end - distance:
        known = sum(1 for value in known_mask[start - distance : end - distance] if value)
    return {
        "distance": distance,
        "length": len(target),
        "correct": correct,
        "false": len(target) - correct,
        "known_source": known,
        "exact": 1 if correct == len(target) else 0,
        "known_exact": 1 if correct == len(target) and known == len(target) else 0,
        "source_head_hex": source[:16].hex(),
    }


def better_row_distance(left: dict[str, object] | None, right: dict[str, object]) -> dict[str, object]:
    if left is None:
        return right
    left_score = (int(left["correct"]), -int(left["false"]), int(left["known_source"]), -int(left["distance"]))
    right_score = (int(right["correct"]), -int(right["false"]), int(right["known_source"]), -int(right["distance"]))
    return right if right_score > left_score else left


def build(
    input_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    replay_rows: list[dict[str, str]],
    *,
    max_distance: int,
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    expected_by_fixture, fixture_issues = load_expected_and_masks(fixture_rows, replay_rows)
    row_outputs: list[dict[str, object]] = []
    distance_counters: dict[int, Counter[str]] = defaultdict(Counter)
    distance_samples: dict[int, dict[str, str]] = {}

    for input_row in input_rows:
        issues = [issue for issue in input_row.get("issues", "").split(";") if issue]
        fixture_data = expected_by_fixture.get(fixture_key(input_row), {})
        expected_all = fixture_data.get("expected", b"")
        known_mask = fixture_data.get("known_mask", b"")
        start = int_value(input_row, "start")
        end = int_value(input_row, "end")
        target = expected_all[start:end]
        if not target:
            issues.append("missing_expected_payload")
            continue
        if input_row.get("length") and int_value(input_row, "length") != len(target):
            issues.append(f"length_mismatch:{input_row.get('length')}:{len(target)}")
        best: dict[str, object] | None = None
        focus_scores: dict[int, dict[str, object]] = {}
        for distance in range(1, min(max_distance, start) + 1):
            score = score_distance(expected_all, known_mask, start, end, distance)
            if score is None:
                continue
            best = better_row_distance(best, score)
            if distance in FOCUS_DISTANCES:
                focus_scores[distance] = score
            counter = distance_counters[distance]
            counter["rows"] += 1
            counter["bytes"] += int(score["length"])
            counter["correct"] += int(score["correct"])
            counter["false"] += int(score["false"])
            counter["known_source"] += int(score["known_source"])
            counter["exact_rows"] += int(score["exact"])
            counter["known_exact_rows"] += int(score["known_exact"])
            distance_samples.setdefault(distance, input_row)
        distance1 = focus_scores.get(1, {})
        distance320 = focus_scores.get(320, {})
        if best is None:
            best = {
                "distance": "",
                "correct": 0,
                "false": len(target),
                "known_source": 0,
                "source_head_hex": "",
            }
        if int(best["correct"]) == len(target) and int(best["known_source"]) == len(target):
            verdict = "known_exact_copy_review"
        elif int(best["correct"]) == len(target):
            verdict = "oracle_exact_copy_only"
        elif int(best["correct"]) >= len(target) // 2:
            verdict = "partial_copy_review"
        else:
            verdict = "spatial_copy_reject"
        row_outputs.append(
            {
                "rank": input_row.get("rank", ""),
                "archive": input_row.get("archive", ""),
                "pcx_name": input_row.get("pcx_name", ""),
                "frontier_id": input_row.get("frontier_id", ""),
                "span_index": input_row.get("span_index", ""),
                "op_index": input_row.get("op_index", ""),
                "length": len(target),
                "start": start,
                "end": end,
                "control_ref_mod64": input_row.get("control_ref_mod64", ""),
                "best_signal_key": input_row.get("best_signal_key", ""),
                "best_distance": best.get("distance", ""),
                "best_correct_bytes": best.get("correct", 0),
                "best_false_bytes": best.get("false", len(target)),
                "best_known_source_bytes": best.get("known_source", 0),
                "best_precision": ratio(int(best.get("correct", 0)), len(target)),
                "distance1_correct_bytes": distance1.get("correct", ""),
                "distance1_false_bytes": distance1.get("false", ""),
                "distance320_correct_bytes": distance320.get("correct", ""),
                "distance320_false_bytes": distance320.get("false", ""),
                "distance320_known_source_bytes": distance320.get("known_source", ""),
                "verdict": verdict,
                "head_hex": target[:16].hex(),
                "source_head_hex": best.get("source_head_hex", ""),
                "issues": ";".join(issues),
            }
        )

    distance_rows: list[dict[str, object]] = []
    for distance, counter in distance_counters.items():
        sample = distance_samples[distance]
        precision = ratio(counter["correct"], counter["bytes"])
        known_ratio = ratio(counter["known_source"], counter["bytes"])
        if counter["known_exact_rows"]:
            verdict = "known_exact_copy_review"
        elif counter["exact_rows"]:
            verdict = "oracle_exact_copy_only"
        elif counter["correct"] >= counter["false"]:
            verdict = "partial_copy_review"
        else:
            verdict = "spatial_copy_reject"
        distance_rows.append(
            {
                "distance": distance,
                "rows": counter["rows"],
                "bytes": counter["bytes"],
                "correct_bytes": counter["correct"],
                "false_bytes": counter["false"],
                "known_source_bytes": counter["known_source"],
                "precision": precision,
                "known_ratio": known_ratio,
                "exact_rows": counter["exact_rows"],
                "known_exact_rows": counter["known_exact_rows"],
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
                "verdict": verdict,
            }
        )
    distance_rows.sort(
        key=lambda row: (-int_value(row, "correct_bytes"), int_value(row, "false_bytes"), int_value(row, "distance"))
    )

    best_aggregate = distance_rows[0] if distance_rows else {}
    distance1_summary = next((row for row in distance_rows if int_value(row, "distance") == 1), {})
    distance320_summary = next((row for row in distance_rows if int_value(row, "distance") == 320), {})
    known_exact_rows = [row for row in row_outputs if row.get("verdict") == "known_exact_copy_review"]
    exact_rows = [row for row in row_outputs if row.get("verdict") in {"known_exact_copy_review", "oracle_exact_copy_only"}]
    summary = {
        "scope": "total",
        "target_rows": len(row_outputs),
        "target_bytes": sum(int_value(row, "length") for row in row_outputs),
        "focus_distances": "|".join(str(distance) for distance in FOCUS_DISTANCES),
        "best_aggregate_distance": best_aggregate.get("distance", ""),
        "best_aggregate_correct_bytes": best_aggregate.get("correct_bytes", 0),
        "best_aggregate_false_bytes": best_aggregate.get("false_bytes", 0),
        "best_aggregate_known_source_bytes": best_aggregate.get("known_source_bytes", 0),
        "best_per_row_correct_bytes": sum(int_value(row, "best_correct_bytes") for row in row_outputs),
        "best_per_row_false_bytes": sum(int_value(row, "best_false_bytes") for row in row_outputs),
        "distance1_correct_bytes": distance1_summary.get("correct_bytes", 0),
        "distance1_false_bytes": distance1_summary.get("false_bytes", 0),
        "distance320_rows": distance320_summary.get("rows", 0),
        "distance320_bytes": distance320_summary.get("bytes", 0),
        "distance320_correct_bytes": distance320_summary.get("correct_bytes", 0),
        "distance320_false_bytes": distance320_summary.get("false_bytes", 0),
        "distance320_known_source_bytes": distance320_summary.get("known_source_bytes", 0),
        "exact_copy_rows": len(exact_rows),
        "exact_copy_bytes": sum(int_value(row, "length") for row in exact_rows),
        "known_exact_copy_rows": len(known_exact_rows),
        "known_exact_copy_bytes": sum(int_value(row, "length") for row in known_exact_rows),
        "promotion_ready_bytes": 0,
        "issue_rows": sum(1 for row in row_outputs if row.get("issues")) + len(fixture_issues),
    }
    return summary, row_outputs, distance_rows


def render_table(rows: list[dict[str, object]], fields: list[str], limit: int = 240) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, object],
    rows: list[dict[str, object]],
    distances: list[dict[str, object]],
    title: str,
) -> str:
    data_json = json.dumps({"summary": summary, "rows": rows, "distances": distances}, indent=2, sort_keys=True)
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body {{ margin: 2rem; background: #111416; color: #edf5f4; font: 14px/1.45 system-ui, sans-serif; }}
table {{ border-collapse: collapse; width: 100%; min-width: 1450px; }}
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
  <div class="box"><div class="num">{summary['best_aggregate_distance']}</div><div class="muted">best aggregate distance</div></div>
  <div class="box"><div class="num">{summary['best_aggregate_correct_bytes']}</div><div class="muted">best aggregate correct</div></div>
  <div class="box"><div class="num">{summary['distance320_correct_bytes']}</div><div class="muted">distance 320 correct</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Rows</h2>{render_table(rows, ROW_FIELDNAMES)}</div>
<div class="panel"><h2>Distances</h2>{render_table(distances, DISTANCE_FIELDNAMES)}</div>
<script type="application/json" id="payload-spatial-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe spatial/backref distances for dominant mixed-value payloads.")
    parser.add_argument("--input-rows", type=Path, default=DEFAULT_INPUT_ROWS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--replay-fixtures", type=Path, default=DEFAULT_REPLAY_FIXTURES)
    parser.add_argument("--max-distance", type=int, default=700)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Mixed Value Payload Spatial Probe")
    args = parser.parse_args()

    summary, rows, distances = build(
        read_csv(args.input_rows),
        read_csv(args.fixtures),
        read_csv(args.replay_fixtures),
        max_distance=args.max_distance,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "rows.csv", ROW_FIELDNAMES, rows)
    write_csv(args.output / "distances.csv", DISTANCE_FIELDNAMES, distances)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, rows, distances, args.title))

    print(f"Target bytes: {summary['target_bytes']}")
    print(f"Best aggregate distance: {summary['best_aggregate_distance']}")
    print(f"Best aggregate correct bytes: {summary['best_aggregate_correct_bytes']}")
    print(f"Distance 320 correct bytes: {summary['distance320_correct_bytes']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
