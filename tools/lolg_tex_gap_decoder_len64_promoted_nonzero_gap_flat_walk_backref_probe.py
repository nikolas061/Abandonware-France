#!/usr/bin/env python3
"""Probe backward-copy distances for flat-walk nonzero gap rows."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_fill_selector_probe import (
    DEFAULT_FIXTURES,
    fixture_key,
    load_expected_by_fixture,
    read_csv,
)
from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_flat_walk_probe import (
    DEFAULT_OUTPUT as DEFAULT_SHAPE_OUTPUT,
)
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_backref_probe")
DEFAULT_TARGETS = DEFAULT_SHAPE_OUTPUT / "targets.csv"
DEFAULT_REPLAY_FIXTURES = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_fill_replay/fixtures.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "target_bytes",
    "distance_rows",
    "rule_rows",
    "exact_copy_rows",
    "exact_copy_bytes",
    "exact_known_source_rows",
    "exact_known_source_bytes",
    "exact_unresolved_source_rows",
    "exact_unresolved_source_bytes",
    "best_distance",
    "best_distance_correct_bytes",
    "best_distance_false_bytes",
    "best_distance_exact_rows",
    "best_distance_exact_bytes",
    "best_rule",
    "best_rule_correct_bytes",
    "best_rule_false_bytes",
    "best_rule_exact_bytes",
    "max_distance",
    "issue_rows",
]

TARGET_FIELDNAMES = [
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "span_index",
    "run_index",
    "op_index",
    "length",
    "start",
    "end",
    "start_mod64",
    "control_ref_mod64",
    "run_length_shape_key",
    "run_value_shape_key",
    "best_distance",
    "best_source_start",
    "best_source_end",
    "best_correct_bytes",
    "best_false_bytes",
    "best_exact",
    "best_source_known_bytes",
    "best_source_unresolved_bytes",
    "best_ratio",
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

RULE_FIELDNAMES = [
    "rule_family",
    "distance",
    "condition",
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
    "precision_rows",
    "precision_bytes",
    "fixtures",
    "sample_pcx",
    "sample_frontier_id",
]


def load_known_masks(replay_rows: list[dict[str, str]]) -> tuple[dict[tuple[str, str, str], bytes], list[str]]:
    masks: dict[tuple[str, str, str], bytes] = {}
    issues: list[str] = []
    for row in replay_rows:
        key = fixture_key(row)
        path = row.get("known_mask_path", "")
        if not path:
            issues.append(f"{key}:missing_known_mask_path")
            masks[key] = b""
            continue
        try:
            masks[key] = Path(path).read_bytes()
        except OSError as exc:
            issues.append(f"{key}:read_known_mask_failed:{exc}")
            masks[key] = b""
    return masks, issues


def length_bucket(length: int) -> str:
    if length < 16:
        return "len_lt16"
    if length < 32:
        return "len16_31"
    if length < 64:
        return "len32_63"
    return "len64_plus"


def rule_conditions(row: dict[str, str]) -> list[tuple[str, str]]:
    length = int_value(row, "length")
    return [
        ("distance_only", "all"),
        ("distance_length", f"length={length}"),
        ("distance_length_bucket", f"length_bucket={length_bucket(length)}"),
        ("distance_start_mod64", f"start_mod64={row.get('start_mod64', '')}"),
        ("distance_control_ref_mod64", f"control_ref_mod64={row.get('control_ref_mod64', '')}"),
        (
            "distance_length_start_mod64",
            f"length_bucket={length_bucket(length)}|start_mod64={row.get('start_mod64', '')}",
        ),
        ("distance_run_length_shape", f"run_length_shape={row.get('run_length_shape_key', '')}"),
        ("distance_run_value_shape", f"run_value_shape={row.get('run_value_shape_key', '')}"),
        (
            "distance_shape_pair",
            f"run_length_shape={row.get('run_length_shape_key', '')}|"
            f"run_value_shape={row.get('run_value_shape_key', '')}",
        ),
    ]


def target_base_row(target: dict[str, str], expected: bytes) -> dict[str, str]:
    return {
        "rank": target.get("rank", ""),
        "archive": target.get("archive", ""),
        "archive_tag": target.get("archive_tag", ""),
        "pcx_name": target.get("pcx_name", ""),
        "frontier_id": target.get("frontier_id", ""),
        "span_index": target.get("span_index", ""),
        "run_index": target.get("run_index", ""),
        "op_index": target.get("op_index", ""),
        "length": str(len(expected)),
        "start": target.get("start", ""),
        "end": target.get("end", ""),
        "start_mod64": target.get("start_mod64", ""),
        "control_ref_mod64": target.get("control_ref_mod64", ""),
        "run_length_shape_key": target.get("run_length_shape_key", ""),
        "run_value_shape_key": target.get("run_value_shape_key", ""),
        "best_distance": "",
        "best_source_start": "",
        "best_source_end": "",
        "best_correct_bytes": "0",
        "best_false_bytes": str(len(expected)),
        "best_exact": "0",
        "best_source_known_bytes": "0",
        "best_source_unresolved_bytes": str(len(expected)),
        "best_ratio": "0.000000",
        "issues": "",
    }


def score_copy(expected_all: bytes, mask: bytes, start: int, end: int, distance: int) -> tuple[int, int, bool, int]:
    source_start = start - distance
    source_end = end - distance
    if source_start < 0 or source_end > len(expected_all):
        return 0, end - start, False, 0
    expected = expected_all[start:end]
    source = expected_all[source_start:source_end]
    correct = sum(1 for left, right in zip(source, expected) if left == right)
    false = len(expected) - correct
    known = sum(1 for value in mask[source_start:source_end] if value) if len(mask) >= source_end else 0
    return correct, false, false == 0, known


def update_best_target(
    row: dict[str, str],
    *,
    distance: int,
    start: int,
    end: int,
    correct: int,
    false: int,
    exact: bool,
    source_known: int,
) -> None:
    candidate = (1 if exact else 0, correct, -false, source_known)
    current = (
        int_value(row, "best_exact"),
        int_value(row, "best_correct_bytes"),
        -int_value(row, "best_false_bytes"),
        int_value(row, "best_source_known_bytes"),
    )
    if candidate <= current:
        return
    length = end - start
    source_start = start - distance
    source_end = end - distance
    row["best_distance"] = str(distance)
    row["best_source_start"] = str(source_start)
    row["best_source_end"] = str(source_end)
    row["best_correct_bytes"] = str(correct)
    row["best_false_bytes"] = str(false)
    row["best_exact"] = "1" if exact else "0"
    row["best_source_known_bytes"] = str(source_known)
    row["best_source_unresolved_bytes"] = str(max(0, length - source_known))
    row["best_ratio"] = f"{(correct / length) if length else 0.0:.6f}"


def rule_label(row: dict[str, str]) -> str:
    return f"{row.get('rule_family')}|distance={row.get('distance')}|{row.get('condition')}"


def build_distance_rows(
    counters: dict[int, Counter[str]],
    fixtures: dict[int, set[tuple[str, str, str]]],
    samples: dict[int, dict[str, str]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for distance, counter in counters.items():
        sample = samples[distance]
        rows.append(
            {
                "distance": str(distance),
                "applies_rows": str(counter["applies_rows"]),
                "applies_bytes": str(counter["applies_bytes"]),
                "correct_rows": str(counter["correct_rows"]),
                "correct_bytes": str(counter["correct_bytes"]),
                "false_rows": str(counter["false_rows"]),
                "false_bytes": str(counter["false_bytes"]),
                "exact_rows": str(counter["exact_rows"]),
                "exact_bytes": str(counter["exact_bytes"]),
                "exact_known_source_rows": str(counter["exact_known_source_rows"]),
                "exact_known_source_bytes": str(counter["exact_known_source_bytes"]),
                "exact_unresolved_source_rows": str(counter["exact_unresolved_source_rows"]),
                "exact_unresolved_source_bytes": str(counter["exact_unresolved_source_bytes"]),
                "fixtures": str(len(fixtures[distance])),
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
            }
        )
    rows.sort(
        key=lambda row: (
            -int_value(row, "exact_bytes"),
            -int_value(row, "correct_bytes"),
            int_value(row, "false_bytes"),
            int_value(row, "distance"),
        )
    )
    return rows


def build_rule_rows(
    counters: dict[tuple[str, int, str], Counter[str]],
    fixtures: dict[tuple[str, int, str], set[tuple[str, str, str]]],
    samples: dict[tuple[str, int, str], dict[str, str]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for key, counter in counters.items():
        family, distance, condition = key
        applies_rows = int(counter["applies_rows"])
        applies_bytes = int(counter["applies_bytes"])
        correct_rows = int(counter["correct_rows"])
        correct_bytes = int(counter["correct_bytes"])
        false_rows = int(counter["false_rows"])
        false_bytes = int(counter["false_bytes"])
        sample = samples[key]
        rows.append(
            {
                "rule_family": family,
                "distance": str(distance),
                "condition": condition,
                "applies_rows": str(applies_rows),
                "applies_bytes": str(applies_bytes),
                "correct_rows": str(correct_rows),
                "correct_bytes": str(correct_bytes),
                "false_rows": str(false_rows),
                "false_bytes": str(false_bytes),
                "exact_rows": str(counter["exact_rows"]),
                "exact_bytes": str(counter["exact_bytes"]),
                "exact_known_source_rows": str(counter["exact_known_source_rows"]),
                "exact_known_source_bytes": str(counter["exact_known_source_bytes"]),
                "exact_unresolved_source_rows": str(counter["exact_unresolved_source_rows"]),
                "exact_unresolved_source_bytes": str(counter["exact_unresolved_source_bytes"]),
                "precision_rows": f"{(correct_rows / applies_rows) if applies_rows else 0.0:.6f}",
                "precision_bytes": f"{(correct_bytes / applies_bytes) if applies_bytes else 0.0:.6f}",
                "fixtures": str(len(fixtures[key])),
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
            }
        )
    rows.sort(
        key=lambda row: (
            int_value(row, "false_bytes"),
            -int_value(row, "exact_known_source_bytes"),
            -int_value(row, "exact_bytes"),
            -int_value(row, "correct_bytes"),
            int_value(row, "distance"),
            row.get("rule_family", ""),
        )
    )
    return rows


def build_summary(
    targets: list[dict[str, str]],
    distance_rows: list[dict[str, str]],
    rule_rows: list[dict[str, str]],
    mask_issues: list[str],
    *,
    max_distance: int,
) -> dict[str, str]:
    exact_targets = [row for row in targets if row.get("best_exact") == "1"]
    exact_known = [
        row
        for row in exact_targets
        if int_value(row, "best_source_known_bytes") >= int_value(row, "length")
    ]
    exact_unresolved = [
        row
        for row in exact_targets
        if int_value(row, "best_source_known_bytes") < int_value(row, "length")
    ]
    best_distance = max(
        distance_rows,
        key=lambda row: (int_value(row, "exact_bytes"), int_value(row, "correct_bytes"), -int_value(row, "false_bytes")),
        default={},
    )
    best_rule = max(
        rule_rows,
        key=lambda row: (
            int_value(row, "exact_known_source_bytes"),
            int_value(row, "exact_bytes"),
            int_value(row, "correct_bytes"),
            -int_value(row, "false_bytes"),
        ),
        default={},
    )
    return {
        "scope": "total",
        "target_rows": str(len(targets)),
        "target_bytes": str(sum(int_value(row, "length") for row in targets)),
        "distance_rows": str(len(distance_rows)),
        "rule_rows": str(len(rule_rows)),
        "exact_copy_rows": str(len(exact_targets)),
        "exact_copy_bytes": str(sum(int_value(row, "length") for row in exact_targets)),
        "exact_known_source_rows": str(len(exact_known)),
        "exact_known_source_bytes": str(sum(int_value(row, "length") for row in exact_known)),
        "exact_unresolved_source_rows": str(len(exact_unresolved)),
        "exact_unresolved_source_bytes": str(sum(int_value(row, "length") for row in exact_unresolved)),
        "best_distance": best_distance.get("distance", "0"),
        "best_distance_correct_bytes": best_distance.get("correct_bytes", "0"),
        "best_distance_false_bytes": best_distance.get("false_bytes", "0"),
        "best_distance_exact_rows": best_distance.get("exact_rows", "0"),
        "best_distance_exact_bytes": best_distance.get("exact_bytes", "0"),
        "best_rule": rule_label(best_rule) if best_rule else "",
        "best_rule_correct_bytes": best_rule.get("correct_bytes", "0"),
        "best_rule_false_bytes": best_rule.get("false_bytes", "0"),
        "best_rule_exact_bytes": best_rule.get("exact_bytes", "0"),
        "max_distance": str(max_distance),
        "issue_rows": str(sum(1 for row in targets if row.get("issues")) + len(mask_issues)),
    }


def update_counters(
    counter: Counter[str],
    *,
    length: int,
    correct: int,
    false: int,
    exact: bool,
    source_known: int,
) -> None:
    counter["applies_rows"] += 1
    counter["applies_bytes"] += length
    counter["correct_rows"] += 1 if correct > 0 else 0
    counter["correct_bytes"] += correct
    counter["false_rows"] += 1 if false > 0 else 0
    counter["false_bytes"] += false
    counter["exact_rows"] += 1 if exact else 0
    counter["exact_bytes"] += length if exact else 0
    if exact and source_known >= length:
        counter["exact_known_source_rows"] += 1
        counter["exact_known_source_bytes"] += length
    elif exact:
        counter["exact_unresolved_source_rows"] += 1
        counter["exact_unresolved_source_bytes"] += length - source_known


def build_rows(
    target_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    replay_rows: list[dict[str, str]],
    *,
    max_distance: int,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    expected_by_fixture, fixture_issues = load_expected_by_fixture(fixture_rows)
    known_masks, mask_issues = load_known_masks(replay_rows)
    distance_counters: dict[int, Counter[str]] = defaultdict(Counter)
    distance_fixtures: dict[int, set[tuple[str, str, str]]] = defaultdict(set)
    distance_samples: dict[int, dict[str, str]] = {}
    rule_counters: dict[tuple[str, int, str], Counter[str]] = defaultdict(Counter)
    rule_fixtures: dict[tuple[str, int, str], set[tuple[str, str, str]]] = defaultdict(set)
    rule_samples: dict[tuple[str, int, str], dict[str, str]] = {}
    targets: list[dict[str, str]] = []

    for target in target_rows:
        issues = [issue for issue in target.get("issues", "").split(";") if issue]
        expected_all = expected_by_fixture.get(fixture_key(target), b"")
        mask = known_masks.get(fixture_key(target), b"")
        start = int_value(target, "start")
        end = int_value(target, "end")
        expected = expected_all[start:end]
        if not expected:
            issues.append("missing_expected_chunk")
            continue
        if not mask:
            issues.append("missing_known_mask")
        row = target_base_row(target, expected)
        for distance in range(1, min(max_distance, start) + 1):
            correct, false, exact, source_known = score_copy(expected_all, mask, start, end, distance)
            update_best_target(
                row,
                distance=distance,
                start=start,
                end=end,
                correct=correct,
                false=false,
                exact=exact,
                source_known=source_known,
            )
            update_counters(
                distance_counters[distance],
                length=len(expected),
                correct=correct,
                false=false,
                exact=exact,
                source_known=source_known,
            )
            distance_fixtures[distance].add(fixture_key(target))
            distance_samples.setdefault(distance, target)
            for family, condition in rule_conditions(target):
                key = family, distance, condition
                update_counters(
                    rule_counters[key],
                    length=len(expected),
                    correct=correct,
                    false=false,
                    exact=exact,
                    source_known=source_known,
                )
                rule_fixtures[key].add(fixture_key(target))
                rule_samples.setdefault(key, target)
        row["issues"] = ";".join(issues)
        targets.append(row)

    distance_rows = build_distance_rows(distance_counters, distance_fixtures, distance_samples)
    rule_rows = build_rule_rows(rule_counters, rule_fixtures, rule_samples)
    summary = build_summary(targets, distance_rows, rule_rows, fixture_issues + mask_issues, max_distance=max_distance)
    return summary, targets, distance_rows, rule_rows


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 240) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    targets: list[dict[str, str]],
    distances: list[dict[str, str]],
    rules: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "targets": targets, "distances": distances, "rules": rules}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("targets.csv", output_dir / "targets.csv"),
            ("by_distance.csv", output_dir / "by_distance.csv"),
            ("rule_candidates.csv", output_dir / "rule_candidates.csv"),
        )
    )
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root {{
  color-scheme: dark;
  --bg: #111416;
  --panel: #172023;
  --line: #31424a;
  --text: #edf5f4;
  --muted: #9dafb5;
  --accent: #77d3b1;
  --ok: #80df94;
  --warn: #f0c36a;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  min-height: 100vh;
  background: var(--bg);
  color: var(--text);
  font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}}
.wrap {{ width: min(1740px, calc(100vw - 28px)); margin: 0 auto; }}
header {{ border-bottom: 1px solid var(--line); background: #12191b; padding: 18px 0 14px; }}
h1 {{ margin: 0; font-size: 21px; font-weight: 720; letter-spacing: 0; }}
h2 {{ margin: 0 0 10px; font-size: 16px; }}
.sub {{ color: var(--muted); margin-top: 4px; }}
main {{ padding: 16px 0 28px; display: grid; gap: 16px; }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 10px; }}
.stat, .panel {{ border: 1px solid var(--line); border-radius: 8px; background: var(--panel); padding: 10px; }}
.label, .muted {{ color: var(--muted); }}
.value {{ font-size: 22px; font-weight: 760; line-height: 1.05; margin-top: 4px; }}
.ok {{ color: var(--ok); }}
.warn {{ color: var(--warn); }}
.panel {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; min-width: 1760px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Scores backward copy distances and separates exact copies by known source coverage.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Flat-walk bytes</div><div class="value">{summary['target_bytes']}</div></div>
    <div class="stat"><div class="label">Exact copy bytes</div><div class="value warn">{summary['exact_copy_bytes']}</div></div>
    <div class="stat"><div class="label">Known-source exact bytes</div><div class="value ok">{summary['exact_known_source_bytes']}</div></div>
    <div class="stat"><div class="label">Unresolved-source exact bytes</div><div class="value warn">{summary['exact_unresolved_source_bytes']}</div></div>
    <div class="stat"><div class="label">Best distance</div><div class="value">{summary['best_distance']}</div></div>
    <div class="stat"><div class="label">Max distance</div><div class="value">{summary['max_distance']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2><div>{links}</div></section>
  <section class="panel"><h2>Distances</h2>{render_table(distances, DISTANCE_FIELDNAMES, 160)}</section>
  <section class="panel"><h2>Rules</h2>{render_table(rules, RULE_FIELDNAMES, 360)}</section>
  <section class="panel"><h2>Targets</h2>{render_table(targets, TARGET_FIELDNAMES, 120)}</section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_FLAT_WALK_BACKREF_PROBE = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe .tex flat-walk backward copy distances.")
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--replay-fixtures", type=Path, default=DEFAULT_REPLAY_FIXTURES)
    parser.add_argument("--max-distance", type=int, default=640)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Tiny Nonzero Gap Flat Walk Backref Probe",
    )
    args = parser.parse_args()

    summary, targets, distances, rules = build_rows(
        read_csv(args.targets),
        read_csv(args.fixtures),
        read_csv(args.replay_fixtures),
        max_distance=args.max_distance,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, targets)
    write_csv(args.output / "by_distance.csv", DISTANCE_FIELDNAMES, distances)
    write_csv(args.output / "rule_candidates.csv", RULE_FIELDNAMES, rules)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, targets, distances, rules, args.output, args.title))

    print(f"Flat-walk targets: {summary['target_rows']}")
    print(f"Exact copy bytes: {summary['exact_copy_bytes']}")
    print(f"Known-source exact bytes: {summary['exact_known_source_bytes']}")
    print(f"Unresolved-source exact bytes: {summary['exact_unresolved_source_bytes']}")
    print(f"Best distance: {summary['best_distance']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
