#!/usr/bin/env python3
"""Probe backward-copy candidates for stable micro-token walks."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path


DEFAULT_TARGETS = Path("output/tex_micro_stable_walks/targets.csv")
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_REPLAY_FIXTURES = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_fill_replay/fixtures.csv")
DEFAULT_OUTPUT = Path("output/tex_micro_stable_backrefs")

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "target_bytes",
    "repeated_target_rows",
    "repeated_target_bytes",
    "exact_copy_rows",
    "exact_copy_bytes",
    "exact_known_source_rows",
    "exact_known_source_bytes",
    "exact_unresolved_source_rows",
    "exact_unresolved_source_bytes",
    "distance_320_exact_rows",
    "distance_320_exact_bytes",
    "distance_320_known_source_rows",
    "distance_320_known_source_bytes",
    "best_distance",
    "best_distance_exact_rows",
    "best_distance_exact_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

TARGET_FIELDNAMES = [
    "rank",
    "group_rank",
    "signed_shape_key",
    "micro_class",
    "archive",
    "pcx_name",
    "frontier_id",
    "start",
    "end",
    "length",
    "best_distance",
    "best_source_start",
    "best_source_end",
    "best_correct_bytes",
    "best_false_bytes",
    "best_exact",
    "best_source_known_bytes",
    "best_source_unresolved_bytes",
    "distance_320_correct_bytes",
    "distance_320_false_bytes",
    "distance_320_exact",
    "distance_320_source_known_bytes",
    "distance_320_source_unresolved_bytes",
    "verdict",
    "issues",
]

DISTANCE_FIELDNAMES = [
    "distance",
    "applies_rows",
    "applies_bytes",
    "correct_rows",
    "correct_bytes",
    "false_rows",
    "false_bytes",
    "exact_rows",
    "exact_bytes",
    "exact_known_source_rows",
    "exact_known_source_bytes",
    "exact_unresolved_source_rows",
    "exact_unresolved_source_bytes",
    "fixtures",
    "sample_pcx",
    "sample_frontier_id",
]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def int_value(row: dict[str, str], field: str) -> int:
    try:
        return int(row.get(field, "") or 0)
    except ValueError:
        return 0


def locator_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("archive", ""), row.get("pcx_name", ""), row.get("frontier_id", "")


def load_bytes(path_text: str, issues: list[str], label: str) -> bytes:
    if not path_text:
        issues.append(f"missing_{label}_path")
        return b""
    try:
        return Path(path_text).read_bytes()
    except OSError as exc:
        issues.append(f"read_{label}_failed:{exc}")
        return b""


def load_expected_by_locator(fixture_rows: list[dict[str, str]]) -> tuple[dict[tuple[str, str, str], bytes], list[str]]:
    expected: dict[tuple[str, str, str], bytes] = {}
    issues: list[str] = []
    for fixture in fixture_rows:
        local_issues: list[str] = []
        expected[locator_key(fixture)] = load_bytes(fixture.get("expected_gap_path", ""), local_issues, "expected")
        issues.extend(f"{locator_key(fixture)}:{issue}" for issue in local_issues)
    return expected, issues


def load_masks_by_locator(replay_rows: list[dict[str, str]]) -> tuple[dict[tuple[str, str, str], bytes], list[str]]:
    masks: dict[tuple[str, str, str], bytes] = {}
    issues: list[str] = []
    for fixture in replay_rows:
        local_issues: list[str] = []
        masks[locator_key(fixture)] = load_bytes(fixture.get("known_mask_path", ""), local_issues, "known_mask")
        issues.extend(f"{locator_key(fixture)}:{issue}" for issue in local_issues)
    return masks, issues


def score_copy(expected_all: bytes, mask: bytes, start: int, end: int, distance: int) -> tuple[int, int, bool, int]:
    source_start = start - distance
    source_end = end - distance
    length = end - start
    if source_start < 0 or source_end > len(expected_all):
        return 0, length, False, 0
    expected = expected_all[start:end]
    source = expected_all[source_start:source_end]
    correct = sum(1 for left, right in zip(source, expected) if left == right)
    false = len(expected) - correct
    known = sum(1 for value in mask[source_start:source_end] if value) if len(mask) >= source_end else 0
    return correct, false, false == 0, known


def update_best(
    row: dict[str, object],
    *,
    start: int,
    end: int,
    distance: int,
    correct: int,
    false: int,
    exact: bool,
    known: int,
) -> None:
    candidate = (1 if exact else 0, correct, -false, known)
    current = (
        int(row["best_exact"]),
        int(row["best_correct_bytes"]),
        -int(row["best_false_bytes"]),
        int(row["best_source_known_bytes"]),
    )
    if candidate <= current:
        return
    length = end - start
    row["best_distance"] = distance
    row["best_source_start"] = start - distance
    row["best_source_end"] = end - distance
    row["best_correct_bytes"] = correct
    row["best_false_bytes"] = false
    row["best_exact"] = 1 if exact else 0
    row["best_source_known_bytes"] = known
    row["best_source_unresolved_bytes"] = max(0, length - known)


def update_counter(counter: Counter[str], *, length: int, correct: int, false: int, exact: bool, known: int) -> None:
    counter["applies_rows"] += 1
    counter["applies_bytes"] += length
    counter["correct_rows"] += 1 if correct else 0
    counter["correct_bytes"] += correct
    counter["false_rows"] += 1 if false else 0
    counter["false_bytes"] += false
    counter["exact_rows"] += 1 if exact else 0
    counter["exact_bytes"] += length if exact else 0
    if exact and known >= length:
        counter["exact_known_source_rows"] += 1
        counter["exact_known_source_bytes"] += length
    elif exact:
        counter["exact_unresolved_source_rows"] += 1
        counter["exact_unresolved_source_bytes"] += length - known


def build_distance_rows(
    counters: dict[int, Counter[str]],
    fixtures: dict[int, set[tuple[str, str, str]]],
    samples: dict[int, dict[str, str]],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for distance, counter in counters.items():
        sample = samples[distance]
        rows.append(
            {
                "distance": distance,
                "applies_rows": counter["applies_rows"],
                "applies_bytes": counter["applies_bytes"],
                "correct_rows": counter["correct_rows"],
                "correct_bytes": counter["correct_bytes"],
                "false_rows": counter["false_rows"],
                "false_bytes": counter["false_bytes"],
                "exact_rows": counter["exact_rows"],
                "exact_bytes": counter["exact_bytes"],
                "exact_known_source_rows": counter["exact_known_source_rows"],
                "exact_known_source_bytes": counter["exact_known_source_bytes"],
                "exact_unresolved_source_rows": counter["exact_unresolved_source_rows"],
                "exact_unresolved_source_bytes": counter["exact_unresolved_source_bytes"],
                "fixtures": len(fixtures[distance]),
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
            }
        )
    rows.sort(key=lambda row: (-int(row["exact_bytes"]), -int(row["correct_bytes"]), int(row["false_bytes"])))
    return rows


def target_base(row: dict[str, str], length: int) -> dict[str, object]:
    return {
        "rank": row.get("rank", ""),
        "group_rank": row.get("group_rank", ""),
        "signed_shape_key": row.get("signed_shape_key", ""),
        "micro_class": row.get("micro_class", ""),
        "archive": row.get("archive", ""),
        "pcx_name": row.get("pcx_name", ""),
        "frontier_id": row.get("frontier_id", ""),
        "start": row.get("start", ""),
        "end": row.get("end", ""),
        "length": length,
        "best_distance": "",
        "best_source_start": "",
        "best_source_end": "",
        "best_correct_bytes": 0,
        "best_false_bytes": length,
        "best_exact": 0,
        "best_source_known_bytes": 0,
        "best_source_unresolved_bytes": length,
        "distance_320_correct_bytes": 0,
        "distance_320_false_bytes": length,
        "distance_320_exact": 0,
        "distance_320_source_known_bytes": 0,
        "distance_320_source_unresolved_bytes": length,
        "verdict": "blocked_review",
        "issues": "",
    }


def build(
    target_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    replay_rows: list[dict[str, str]],
    *,
    max_distance: int,
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    expected_by_locator, expected_issues = load_expected_by_locator(fixture_rows)
    masks_by_locator, mask_issues = load_masks_by_locator(replay_rows)
    group_counts = Counter(row.get("group_rank", "") for row in target_rows)
    repeated_group_rows = [row for row in target_rows if group_counts[row.get("group_rank", "")] > 1]
    counters: dict[int, Counter[str]] = defaultdict(Counter)
    fixtures: dict[int, set[tuple[str, str, str]]] = defaultdict(set)
    samples: dict[int, dict[str, str]] = {}
    targets: list[dict[str, object]] = []

    for target in repeated_group_rows:
        issues = [issue for issue in target.get("issues", "").split(";") if issue]
        key = locator_key(target)
        expected_all = expected_by_locator.get(key, b"")
        mask = masks_by_locator.get(key, b"")
        start = int_value(target, "start")
        end = int_value(target, "end")
        expected = expected_all[start:end]
        if not expected:
            issues.append("missing_expected_chunk")
            continue
        if not mask:
            issues.append("missing_known_mask")
        row = target_base(target, len(expected))
        for distance in range(1, min(max_distance, start) + 1):
            correct, false, exact, known = score_copy(expected_all, mask, start, end, distance)
            update_best(row, start=start, end=end, distance=distance, correct=correct, false=false, exact=exact, known=known)
            update_counter(counters[distance], length=len(expected), correct=correct, false=false, exact=exact, known=known)
            fixtures[distance].add(key)
            samples.setdefault(distance, target)
            if distance == 320:
                row["distance_320_correct_bytes"] = correct
                row["distance_320_false_bytes"] = false
                row["distance_320_exact"] = 1 if exact else 0
                row["distance_320_source_known_bytes"] = known
                row["distance_320_source_unresolved_bytes"] = max(0, len(expected) - known)
        if row["distance_320_exact"] and row["distance_320_source_known_bytes"] >= row["length"]:
            row["verdict"] = "distance_320_known_source_candidate"
        elif row["distance_320_exact"]:
            row["verdict"] = "distance_320_unresolved_source"
        elif row["best_exact"]:
            row["verdict"] = "other_exact_backref_review"
        row["issues"] = ";".join(issues)
        targets.append(row)

    distances = build_distance_rows(counters, fixtures, samples)
    best_distance = distances[0] if distances else {}
    exact_targets = [row for row in targets if row["best_exact"]]
    exact_known = [row for row in exact_targets if int(row["best_source_known_bytes"]) >= int(row["length"])]
    exact_unresolved = [row for row in exact_targets if int(row["best_source_known_bytes"]) < int(row["length"])]
    distance_320_exact = [row for row in targets if row["distance_320_exact"]]
    distance_320_known = [
        row
        for row in distance_320_exact
        if int(row["distance_320_source_known_bytes"]) >= int(row["length"])
    ]
    summary = {
        "scope": "total",
        "target_rows": len(target_rows),
        "target_bytes": sum(int_value(row, "length") for row in target_rows),
        "repeated_target_rows": len(targets),
        "repeated_target_bytes": sum(int(row["length"]) for row in targets),
        "exact_copy_rows": len(exact_targets),
        "exact_copy_bytes": sum(int(row["length"]) for row in exact_targets),
        "exact_known_source_rows": len(exact_known),
        "exact_known_source_bytes": sum(int(row["length"]) for row in exact_known),
        "exact_unresolved_source_rows": len(exact_unresolved),
        "exact_unresolved_source_bytes": sum(int(row["length"]) for row in exact_unresolved),
        "distance_320_exact_rows": len(distance_320_exact),
        "distance_320_exact_bytes": sum(int(row["length"]) for row in distance_320_exact),
        "distance_320_known_source_rows": len(distance_320_known),
        "distance_320_known_source_bytes": sum(int(row["length"]) for row in distance_320_known),
        "best_distance": best_distance.get("distance", ""),
        "best_distance_exact_rows": best_distance.get("exact_rows", 0),
        "best_distance_exact_bytes": best_distance.get("exact_bytes", 0),
        "promotion_ready_bytes": 0,
        "issue_rows": sum(1 for row in targets if row.get("issues")) + len(expected_issues) + len(mask_issues),
    }
    return summary, targets, distances


def render_table(rows: list[dict[str, object]], fields: list[str], limit: int = 180) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(summary: dict[str, object], targets: list[dict[str, object]], distances: list[dict[str, object]], title: str) -> str:
    data_json = json.dumps({"summary": summary, "targets": targets, "distances": distances}, indent=2, sort_keys=True)
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body {{ margin: 2rem; background: #111416; color: #edf5f4; font: 14px/1.45 system-ui, sans-serif; }}
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
  <div class="box"><div class="num">{summary['repeated_target_rows']}</div><div class="muted">repeated targets</div></div>
  <div class="box"><div class="num">{summary['exact_copy_bytes']}</div><div class="muted">exact copy bytes</div></div>
  <div class="box"><div class="num">{summary['distance_320_exact_bytes']}</div><div class="muted">distance +320 exact bytes</div></div>
  <div class="box"><div class="num">{summary['distance_320_known_source_bytes']}</div><div class="muted">distance +320 known-source bytes</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Distances</h2>{render_table(distances, DISTANCE_FIELDNAMES)}</div>
<div class="panel"><h2>Targets</h2>{render_table(targets, TARGET_FIELDNAMES)}</div>
<script type="application/json" id="stable-backref-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe backward copies in stable .tex micro-token walks.")
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--replay-fixtures", type=Path, default=DEFAULT_REPLAY_FIXTURES)
    parser.add_argument("--max-distance", type=int, default=640)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Micro Stable Backrefs")
    args = parser.parse_args()

    summary, targets, distances = build(
        read_rows(args.targets),
        read_rows(args.fixtures),
        read_rows(args.replay_fixtures),
        max_distance=args.max_distance,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, targets)
    write_csv(args.output / "by_distance.csv", DISTANCE_FIELDNAMES, distances)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, targets, distances, args.title))

    print(f"Repeated targets: {summary['repeated_target_rows']}")
    print(f"Distance +320 exact bytes: {summary['distance_320_exact_bytes']}")
    print(f"Distance +320 known-source bytes: {summary['distance_320_known_source_bytes']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
