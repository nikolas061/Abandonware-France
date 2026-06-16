#!/usr/bin/env python3
"""Probe dense jump-weave noisy nonzero rows for reusable alternation grammar."""

from __future__ import annotations

import argparse
import hashlib
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
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_dense_jump_probe")
DEFAULT_TARGETS = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_jump_token_probe/targets.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "target_bytes",
    "delta_count",
    "jump_delta_count",
    "jump_delta_ratio",
    "positive_jump_count",
    "negative_jump_count",
    "direction_switch_count",
    "direction_switch_ratio",
    "alternating_rows",
    "alternating_bytes",
    "island_count",
    "single_byte_islands",
    "single_byte_island_ratio",
    "dominant_nibble_rows",
    "dominant_nibble_bytes",
    "direction_shape_groups",
    "direction_repeated_groups",
    "direction_repeated_rows",
    "direction_repeated_bytes",
    "magnitude_shape_groups",
    "magnitude_repeated_groups",
    "magnitude_repeated_rows",
    "magnitude_repeated_bytes",
    "nibble_pair_shape_groups",
    "nibble_pair_repeated_groups",
    "nibble_pair_repeated_rows",
    "nibble_pair_repeated_bytes",
    "island_bucket_shape_groups",
    "island_bucket_repeated_groups",
    "island_bucket_repeated_rows",
    "island_bucket_repeated_bytes",
    "phase_shape_groups",
    "phase_repeated_groups",
    "phase_repeated_rows",
    "phase_repeated_bytes",
    "promotion_ready_bytes",
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
    "control_ref_offset",
    "control_ref_mod64",
    "control_window_signature",
    "delta_count",
    "jump_delta_count",
    "jump_delta_ratio",
    "positive_jump_count",
    "negative_jump_count",
    "direction_switch_count",
    "direction_switch_ratio",
    "island_count",
    "single_byte_islands",
    "single_byte_island_ratio",
    "top_nibble_pair",
    "top_nibble_pair_count",
    "top_nibble_pair_ratio",
    "direction_shape_key",
    "direction_shape_preview",
    "magnitude_shape_key",
    "magnitude_shape_preview",
    "nibble_pair_shape_key",
    "nibble_pair_shape_preview",
    "island_bucket_shape_key",
    "island_bucket_shape_preview",
    "phase_shape_key",
    "phase_shape_preview",
    "dense_class",
    "head_hex",
    "tail_hex",
    "issues",
]

GROUP_FIELDNAMES = [
    "group_kind",
    "group_key",
    "group_preview",
    "rows",
    "bytes",
    "delta_count",
    "jump_delta_count",
    "direction_switch_count",
    "single_byte_islands",
    "dense_classes",
    "fixtures",
    "sample_pcx",
    "sample_frontier_id",
]


def signed_delta(left: int, right: int) -> int:
    return ((right - left + 128) & 0xFF) - 128


def deltas(data: bytes) -> list[int]:
    return [signed_delta(data[index - 1], data[index]) for index in range(1, len(data))]


def jump_indices(delta_values: list[int]) -> list[int]:
    return [index + 1 for index, value in enumerate(delta_values) if abs(value) > 31]


def jump_pairs(data: bytes, jumps: list[int]) -> list[tuple[int, int, int]]:
    pairs: list[tuple[int, int, int]] = []
    for index in jumps:
        if index <= 0 or index >= len(data):
            continue
        left = data[index - 1]
        right = data[index]
        pairs.append((left, right, signed_delta(left, right)))
    return pairs


def shape_key(shape: str) -> str:
    digest = hashlib.sha1(shape.encode("ascii")).hexdigest()[:14]
    return f"len={len(shape)}|sha1={digest}"


def preview_text(value: str, limit: int = 140) -> str:
    if len(value) <= limit:
        return value
    return f"{value[:limit]}..."


def ratio(numerator: int, denominator: int) -> str:
    return f"{(numerator / denominator) if denominator else 0.0:.6f}"


def run_shape(values: list[str]) -> str:
    if not values:
        return ""
    parts: list[str] = []
    current = values[0]
    count = 1
    for value in values[1:]:
        if value == current:
            count += 1
            continue
        parts.append(f"{current}x{count}")
        current = value
        count = 1
    parts.append(f"{current}x{count}")
    return ".".join(parts)


def magnitude_label(delta: int) -> str:
    magnitude = abs(delta)
    if magnitude <= 63:
        return "32_63"
    if magnitude <= 95:
        return "64_95"
    return "96_128"


def island_lengths(length: int, jumps: list[int]) -> list[int]:
    starts = [0] + jumps
    ends = jumps + [length]
    return [max(0, end - start) for start, end in zip(starts, ends)]


def island_bucket(length: int) -> str:
    if length <= 1:
        return "1"
    if length == 2:
        return "2"
    if length == 3:
        return "3"
    if length <= 7:
        return "4_7"
    return "8_plus"


def direction_switches(directions: list[str]) -> int:
    return sum(1 for index in range(1, len(directions)) if directions[index] != directions[index - 1])


def classify_dense(row: dict[str, str]) -> str:
    switch_ratio = float(row.get("direction_switch_ratio", "0") or 0)
    single_ratio = float(row.get("single_byte_island_ratio", "0") or 0)
    top_ratio = float(row.get("top_nibble_pair_ratio", "0") or 0)
    if switch_ratio >= 0.85 and single_ratio >= 0.55:
        return "alternating_single_island_weave"
    if switch_ratio >= 0.85:
        return "alternating_dense_weave"
    if top_ratio >= 0.50:
        return "dominant_nibble_weave"
    if single_ratio >= 0.60:
        return "single_island_dense_weave"
    return "mixed_dense_weave"


def build_target_rows(
    target_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[str]]:
    expected_by_fixture, fixture_issues = load_expected_by_fixture(fixture_rows)
    rows: list[dict[str, str]] = []
    for target in target_rows:
        if target.get("jump_structure_class") != "dense_jump_weave":
            continue
        issues = [issue for issue in target.get("issues", "").split(";") if issue]
        expected_all = expected_by_fixture.get(fixture_key(target), b"")
        start = int_value(target, "start")
        end = int_value(target, "end")
        expected = expected_all[start:end]
        if not expected:
            issues.append("missing_expected_chunk")
            continue

        delta_values = deltas(expected)
        jumps = jump_indices(delta_values)
        pairs = jump_pairs(expected, jumps)
        directions = ["+" if delta > 0 else "-" for _left, _right, delta in pairs]
        magnitudes = [magnitude_label(delta) for _left, _right, delta in pairs]
        nibble_pairs = [f"{left >> 4:x}>{right >> 4:x}" for left, right, _delta in pairs]
        phases = [f"{direction}{magnitude}:{pair}" for direction, magnitude, pair in zip(directions, magnitudes, nibble_pairs)]
        islands = island_lengths(len(expected), jumps)
        island_buckets = [island_bucket(length) for length in islands]
        switch_count = direction_switches(directions)
        top_pair, top_pair_count = Counter(nibble_pairs).most_common(1)[0] if nibble_pairs else ("", 0)
        positive_count = sum(1 for value in directions if value == "+")
        negative_count = sum(1 for value in directions if value == "-")
        row = {
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
            "control_ref_offset": target.get("control_ref_offset", ""),
            "control_ref_mod64": target.get("control_ref_mod64", ""),
            "control_window_signature": target.get("control_window_signature", ""),
            "delta_count": str(len(delta_values)),
            "jump_delta_count": str(len(jumps)),
            "jump_delta_ratio": ratio(len(jumps), len(delta_values)),
            "positive_jump_count": str(positive_count),
            "negative_jump_count": str(negative_count),
            "direction_switch_count": str(switch_count),
            "direction_switch_ratio": ratio(switch_count, max(0, len(directions) - 1)),
            "island_count": str(len(islands)),
            "single_byte_islands": str(sum(1 for length in islands if length == 1)),
            "single_byte_island_ratio": ratio(sum(1 for length in islands if length == 1), len(islands)),
            "top_nibble_pair": top_pair,
            "top_nibble_pair_count": str(top_pair_count),
            "top_nibble_pair_ratio": ratio(top_pair_count, len(nibble_pairs)),
            "direction_shape_key": shape_key(run_shape(directions)),
            "direction_shape_preview": preview_text(run_shape(directions)),
            "magnitude_shape_key": shape_key(run_shape(magnitudes)),
            "magnitude_shape_preview": preview_text(run_shape(magnitudes)),
            "nibble_pair_shape_key": shape_key(".".join(nibble_pairs)),
            "nibble_pair_shape_preview": preview_text(".".join(nibble_pairs)),
            "island_bucket_shape_key": shape_key(run_shape(island_buckets)),
            "island_bucket_shape_preview": preview_text(run_shape(island_buckets)),
            "phase_shape_key": shape_key(run_shape(phases)),
            "phase_shape_preview": preview_text(run_shape(phases)),
            "dense_class": "",
            "head_hex": expected[:16].hex(),
            "tail_hex": expected[-16:].hex(),
            "issues": ";".join(issues),
        }
        row["dense_class"] = classify_dense(row)
        rows.append(row)
    return rows, fixture_issues


def build_group_rows(rows: list[dict[str, str]], key_field: str, preview_field: str, kind: str) -> list[dict[str, str]]:
    counters: dict[str, Counter[str]] = defaultdict(Counter)
    classes: dict[str, set[str]] = defaultdict(set)
    fixtures: dict[str, set[tuple[str, str, str]]] = defaultdict(set)
    previews: dict[str, str] = {}
    samples: dict[str, dict[str, str]] = {}
    for row in rows:
        key = row.get(key_field, "")
        counters[key]["rows"] += 1
        counters[key]["bytes"] += int_value(row, "length")
        counters[key]["delta_count"] += int_value(row, "delta_count")
        counters[key]["jump_delta_count"] += int_value(row, "jump_delta_count")
        counters[key]["direction_switch_count"] += int_value(row, "direction_switch_count")
        counters[key]["single_byte_islands"] += int_value(row, "single_byte_islands")
        classes[key].add(row.get("dense_class", ""))
        fixtures[key].add(fixture_key(row))
        previews.setdefault(key, row.get(preview_field, ""))
        samples.setdefault(key, row)
    output: list[dict[str, str]] = []
    for key, counter in counters.items():
        sample = samples[key]
        output.append(
            {
                "group_kind": kind,
                "group_key": key,
                "group_preview": previews.get(key, ""),
                "rows": str(counter["rows"]),
                "bytes": str(counter["bytes"]),
                "delta_count": str(counter["delta_count"]),
                "jump_delta_count": str(counter["jump_delta_count"]),
                "direction_switch_count": str(counter["direction_switch_count"]),
                "single_byte_islands": str(counter["single_byte_islands"]),
                "dense_classes": ";".join(sorted(classes[key])),
                "fixtures": str(len(fixtures[key])),
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
            }
        )
    output.sort(key=lambda row: (-int_value(row, "rows"), -int_value(row, "bytes"), row.get("group_key", "")))
    return output


def repeated_stats(groups: list[dict[str, str]]) -> tuple[int, int, int]:
    repeated = [row for row in groups if int_value(row, "rows") > 1]
    return len(repeated), sum(int_value(row, "rows") for row in repeated), sum(int_value(row, "bytes") for row in repeated)


def sum_bytes(rows: list[dict[str, str]]) -> int:
    return sum(int_value(row, "length") for row in rows)


def build_summary(
    rows: list[dict[str, str]],
    direction_groups: list[dict[str, str]],
    magnitude_groups: list[dict[str, str]],
    nibble_groups: list[dict[str, str]],
    island_groups: list[dict[str, str]],
    phase_groups: list[dict[str, str]],
    fixture_issue_count: int,
) -> dict[str, str]:
    delta_count = sum(int_value(row, "delta_count") for row in rows)
    jump_count = sum(int_value(row, "jump_delta_count") for row in rows)
    switch_count = sum(int_value(row, "direction_switch_count") for row in rows)
    switch_denominator = sum(max(0, int_value(row, "jump_delta_count") - 1) for row in rows)
    island_count = sum(int_value(row, "island_count") for row in rows)
    single_islands = sum(int_value(row, "single_byte_islands") for row in rows)
    direction_repeated = repeated_stats(direction_groups)
    magnitude_repeated = repeated_stats(magnitude_groups)
    nibble_repeated = repeated_stats(nibble_groups)
    island_repeated = repeated_stats(island_groups)
    phase_repeated = repeated_stats(phase_groups)
    alternating = [row for row in rows if float(row.get("direction_switch_ratio", "0") or 0) >= 0.85]
    dominant = [row for row in rows if float(row.get("top_nibble_pair_ratio", "0") or 0) >= 0.50]
    return {
        "scope": "total",
        "target_rows": str(len(rows)),
        "target_bytes": str(sum_bytes(rows)),
        "delta_count": str(delta_count),
        "jump_delta_count": str(jump_count),
        "jump_delta_ratio": ratio(jump_count, delta_count),
        "positive_jump_count": str(sum(int_value(row, "positive_jump_count") for row in rows)),
        "negative_jump_count": str(sum(int_value(row, "negative_jump_count") for row in rows)),
        "direction_switch_count": str(switch_count),
        "direction_switch_ratio": ratio(switch_count, switch_denominator),
        "alternating_rows": str(len(alternating)),
        "alternating_bytes": str(sum_bytes(alternating)),
        "island_count": str(island_count),
        "single_byte_islands": str(single_islands),
        "single_byte_island_ratio": ratio(single_islands, island_count),
        "dominant_nibble_rows": str(len(dominant)),
        "dominant_nibble_bytes": str(sum_bytes(dominant)),
        "direction_shape_groups": str(len(direction_groups)),
        "direction_repeated_groups": str(direction_repeated[0]),
        "direction_repeated_rows": str(direction_repeated[1]),
        "direction_repeated_bytes": str(direction_repeated[2]),
        "magnitude_shape_groups": str(len(magnitude_groups)),
        "magnitude_repeated_groups": str(magnitude_repeated[0]),
        "magnitude_repeated_rows": str(magnitude_repeated[1]),
        "magnitude_repeated_bytes": str(magnitude_repeated[2]),
        "nibble_pair_shape_groups": str(len(nibble_groups)),
        "nibble_pair_repeated_groups": str(nibble_repeated[0]),
        "nibble_pair_repeated_rows": str(nibble_repeated[1]),
        "nibble_pair_repeated_bytes": str(nibble_repeated[2]),
        "island_bucket_shape_groups": str(len(island_groups)),
        "island_bucket_repeated_groups": str(island_repeated[0]),
        "island_bucket_repeated_rows": str(island_repeated[1]),
        "island_bucket_repeated_bytes": str(island_repeated[2]),
        "phase_shape_groups": str(len(phase_groups)),
        "phase_repeated_groups": str(phase_repeated[0]),
        "phase_repeated_rows": str(phase_repeated[1]),
        "phase_repeated_bytes": str(phase_repeated[2]),
        "promotion_ready_bytes": "0",
        "issue_rows": str(sum(1 for row in rows if row.get("issues")) + fixture_issue_count),
    }


def build_rows(
    target_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    rows, fixture_issues = build_target_rows(target_rows, fixture_rows)
    class_groups = build_group_rows(rows, "dense_class", "dense_class", "dense_class")
    direction_groups = build_group_rows(rows, "direction_shape_key", "direction_shape_preview", "direction_shape")
    magnitude_groups = build_group_rows(rows, "magnitude_shape_key", "magnitude_shape_preview", "magnitude_shape")
    nibble_groups = build_group_rows(rows, "nibble_pair_shape_key", "nibble_pair_shape_preview", "nibble_pair_shape")
    island_groups = build_group_rows(rows, "island_bucket_shape_key", "island_bucket_shape_preview", "island_bucket_shape")
    phase_groups = build_group_rows(rows, "phase_shape_key", "phase_shape_preview", "phase_shape")
    summary = build_summary(
        rows,
        direction_groups,
        magnitude_groups,
        nibble_groups,
        island_groups,
        phase_groups,
        len(fixture_issues),
    )
    return summary, rows, class_groups, direction_groups, magnitude_groups, nibble_groups, island_groups, phase_groups


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 240) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    rows: list[dict[str, str]],
    class_groups: list[dict[str, str]],
    direction_groups: list[dict[str, str]],
    magnitude_groups: list[dict[str, str]],
    nibble_groups: list[dict[str, str]],
    island_groups: list[dict[str, str]],
    phase_groups: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "targets": rows,
        "classGroups": class_groups,
        "directionGroups": direction_groups,
        "magnitudeGroups": magnitude_groups,
        "nibbleGroups": nibble_groups,
        "islandGroups": island_groups,
        "phaseGroups": phase_groups,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("targets.csv", output_dir / "targets.csv"),
            ("by_dense_class.csv", output_dir / "by_dense_class.csv"),
            ("by_direction_shape.csv", output_dir / "by_direction_shape.csv"),
            ("by_magnitude_shape.csv", output_dir / "by_magnitude_shape.csv"),
            ("by_nibble_pair_shape.csv", output_dir / "by_nibble_pair_shape.csv"),
            ("by_island_bucket_shape.csv", output_dir / "by_island_bucket_shape.csv"),
            ("by_phase_shape.csv", output_dir / "by_phase_shape.csv"),
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
table {{ width: 100%; border-collapse: collapse; min-width: 1700px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Measures whether dense jump-weave rows share a reusable alternation grammar.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Dense rows</div><div class="value">{summary['target_rows']}</div></div>
    <div class="stat"><div class="label">Dense bytes</div><div class="value">{summary['target_bytes']}</div></div>
    <div class="stat"><div class="label">Direction switch ratio</div><div class="value ok">{summary['direction_switch_ratio']}</div></div>
    <div class="stat"><div class="label">Phase repeated bytes</div><div class="value warn">{summary['phase_repeated_bytes']}</div></div>
    <div class="stat"><div class="label">Promotion-ready bytes</div><div class="value warn">{summary['promotion_ready_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2><div>{links}</div></section>
  <section class="panel"><h2>Dense classes</h2>{render_table(class_groups, GROUP_FIELDNAMES, 80)}</section>
  <section class="panel"><h2>Direction shapes</h2>{render_table(direction_groups, GROUP_FIELDNAMES, 120)}</section>
  <section class="panel"><h2>Magnitude shapes</h2>{render_table(magnitude_groups, GROUP_FIELDNAMES, 120)}</section>
  <section class="panel"><h2>Nibble pair shapes</h2>{render_table(nibble_groups, GROUP_FIELDNAMES, 120)}</section>
  <section class="panel"><h2>Island bucket shapes</h2>{render_table(island_groups, GROUP_FIELDNAMES, 120)}</section>
  <section class="panel"><h2>Phase shapes</h2>{render_table(phase_groups, GROUP_FIELDNAMES, 120)}</section>
  <section class="panel"><h2>Targets</h2>{render_table(rows, TARGET_FIELDNAMES, 120)}</section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_DENSE_JUMP_PROBE = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe dense jump-weave .tex nonzero gap rows.")
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Tiny Nonzero Gap Dense Jump Probe",
    )
    args = parser.parse_args()

    summary, rows, class_groups, direction_groups, magnitude_groups, nibble_groups, island_groups, phase_groups = (
        build_rows(read_csv(args.targets), read_csv(args.fixtures))
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, rows)
    write_csv(args.output / "by_dense_class.csv", GROUP_FIELDNAMES, class_groups)
    write_csv(args.output / "by_direction_shape.csv", GROUP_FIELDNAMES, direction_groups)
    write_csv(args.output / "by_magnitude_shape.csv", GROUP_FIELDNAMES, magnitude_groups)
    write_csv(args.output / "by_nibble_pair_shape.csv", GROUP_FIELDNAMES, nibble_groups)
    write_csv(args.output / "by_island_bucket_shape.csv", GROUP_FIELDNAMES, island_groups)
    write_csv(args.output / "by_phase_shape.csv", GROUP_FIELDNAMES, phase_groups)
    html_path = args.output / "index.html"
    html_path.write_text(
        build_html(
            summary,
            rows,
            class_groups,
            direction_groups,
            magnitude_groups,
            nibble_groups,
            island_groups,
            phase_groups,
            args.output,
            args.title,
        )
    )

    print(f"Dense-jump targets: {summary['target_rows']}")
    print(f"Dense-jump bytes: {summary['target_bytes']}")
    print(f"Direction switch ratio: {summary['direction_switch_ratio']}")
    print(f"Phase repeated bytes: {summary['phase_repeated_bytes']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
