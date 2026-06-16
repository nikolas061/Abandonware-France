#!/usr/bin/env python3
"""Probe gradient-like noisy nonzero gap rows."""

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
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_probe")
DEFAULT_TARGETS = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_noisy_shape_probe/targets.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "target_bytes",
    "total_delta_count",
    "small_delta_count",
    "small_delta_ratio",
    "zero_delta_count",
    "step_delta_count",
    "dominant_delta_rows",
    "dominant_delta_bytes",
    "linear_ge50_rows",
    "linear_ge50_bytes",
    "linear_ge75_rows",
    "linear_ge75_bytes",
    "linear_full_rows",
    "linear_exact_bytes_total",
    "linear_best_single_exact_bytes",
    "small_delta_walk_rows",
    "small_delta_walk_bytes",
    "banded_rows",
    "banded_bytes",
    "repeated_delta_histogram_groups",
    "repeated_delta_histogram_rows",
    "repeated_delta_histogram_bytes",
    "repeated_delta_run_shape_groups",
    "repeated_delta_run_shape_rows",
    "repeated_delta_run_shape_bytes",
    "gradient_classes",
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
    "unique_bytes",
    "dominant_byte_hex",
    "dominant_ratio",
    "delta_count",
    "small_delta_count",
    "small_delta_ratio",
    "zero_delta_count",
    "zero_delta_ratio",
    "step_delta_count",
    "step_delta_ratio",
    "dominant_delta",
    "dominant_delta_count",
    "dominant_delta_ratio",
    "linear_step",
    "linear_exact_bytes",
    "linear_exact_ratio",
    "linear_full_match",
    "delta_run_count",
    "max_delta_run",
    "delta_histogram_key",
    "delta_run_shape_key",
    "top_nibble",
    "top_nibble_ratio",
    "gradient_class",
    "head_hex",
    "tail_hex",
    "issues",
]

GROUP_FIELDNAMES = [
    "group_kind",
    "group_key",
    "rows",
    "bytes",
    "linear_exact_bytes",
    "small_delta_count",
    "delta_count",
    "gradient_classes",
    "fixtures",
    "sample_pcx",
    "sample_frontier_id",
]


def signed_delta(left: int, right: int) -> int:
    return ((right - left + 128) & 0xFF) - 128


def deltas(data: bytes) -> list[int]:
    return [signed_delta(data[index - 1], data[index]) for index in range(1, len(data))]


def run_lengths(values: list[int]) -> list[tuple[int, int]]:
    if not values:
        return []
    runs: list[tuple[int, int]] = []
    current = values[0]
    count = 1
    for value in values[1:]:
        if value == current:
            count += 1
            continue
        runs.append((current, count))
        current = value
        count = 1
    runs.append((current, count))
    return runs


def linear_score(data: bytes, step: int) -> int:
    if not data:
        return 0
    expected = data[0]
    exact = 0
    for index, value in enumerate(data):
        if value == ((expected + step * index) & 0xFF):
            exact += 1
    return exact


def best_linear(data: bytes) -> tuple[int, int]:
    candidates = [(step, linear_score(data, step)) for step in range(-8, 9)]
    return max(candidates, key=lambda item: (item[1], -abs(item[0]), -item[0]))


def delta_histogram_key(delta_values: list[int]) -> str:
    counts = Counter(delta_values)
    parts = []
    for value in range(-8, 9):
        count = counts.get(value, 0)
        if count:
            parts.append(f"{value}:{count}")
    outside = sum(count for value, count in counts.items() if value < -8 or value > 8)
    if outside:
        parts.append(f"outside:{outside}")
    return ";".join(parts)


def delta_run_shape_key(delta_values: list[int]) -> str:
    parts = []
    for value, count in run_lengths(delta_values):
        if value < -8 or value > 8:
            label = "outside"
        else:
            label = str(value)
        parts.append(f"{label}x{count}")
    shape = ";".join(parts)
    if len(shape) > 180:
        return f"{shape[:180]}..."
    return shape


def top_nibble_stats(data: bytes) -> tuple[str, float]:
    if not data:
        return "", 0.0
    nibble, count = Counter(value >> 4 for value in data).most_common(1)[0]
    return f"0x{nibble:x}", count / len(data)


def classify_gradient(row: dict[str, str]) -> str:
    linear_ratio = float(row.get("linear_exact_ratio", "0") or 0)
    small_ratio = float(row.get("small_delta_ratio", "0") or 0)
    zero_ratio = float(row.get("zero_delta_ratio", "0") or 0)
    dominant_delta_ratio = float(row.get("dominant_delta_ratio", "0") or 0)
    top_nibble_ratio = float(row.get("top_nibble_ratio", "0") or 0)
    if linear_ratio >= 0.75:
        return "linear_ramp_candidate"
    if zero_ratio >= 0.45:
        return "flat_run_walk"
    if small_ratio >= 0.90 and top_nibble_ratio >= 0.80:
        return "banded_small_delta_walk"
    if small_ratio >= 0.90:
        return "small_delta_walk"
    if dominant_delta_ratio >= 0.45:
        return "dominant_delta_walk"
    if top_nibble_ratio >= 0.80:
        return "banded_mixed_walk"
    return "mixed_gradient"


def build_target_rows(
    target_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[str]]:
    expected_by_fixture, fixture_issues = load_expected_by_fixture(fixture_rows)
    rows: list[dict[str, str]] = []
    for target in target_rows:
        if target.get("classification") != "gradient_like":
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
        counts = Counter(delta_values)
        dominant_delta, dominant_delta_count = counts.most_common(1)[0] if counts else (0, 0)
        small_count = sum(1 for value in delta_values if abs(value) <= 4)
        zero_count = sum(1 for value in delta_values if value == 0)
        step_count = sum(1 for value in delta_values if abs(value) == 1)
        linear_step, linear_exact = best_linear(expected)
        delta_runs = run_lengths(delta_values)
        top_nibble, top_nibble_ratio = top_nibble_stats(expected)
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
            "unique_bytes": target.get("unique_bytes", ""),
            "dominant_byte_hex": target.get("dominant_byte_hex", ""),
            "dominant_ratio": target.get("dominant_ratio", ""),
            "delta_count": str(len(delta_values)),
            "small_delta_count": str(small_count),
            "small_delta_ratio": f"{(small_count / len(delta_values)) if delta_values else 0.0:.6f}",
            "zero_delta_count": str(zero_count),
            "zero_delta_ratio": f"{(zero_count / len(delta_values)) if delta_values else 0.0:.6f}",
            "step_delta_count": str(step_count),
            "step_delta_ratio": f"{(step_count / len(delta_values)) if delta_values else 0.0:.6f}",
            "dominant_delta": str(dominant_delta),
            "dominant_delta_count": str(dominant_delta_count),
            "dominant_delta_ratio": f"{(dominant_delta_count / len(delta_values)) if delta_values else 0.0:.6f}",
            "linear_step": str(linear_step),
            "linear_exact_bytes": str(linear_exact),
            "linear_exact_ratio": f"{(linear_exact / len(expected)) if expected else 0.0:.6f}",
            "linear_full_match": "1" if linear_exact == len(expected) else "0",
            "delta_run_count": str(len(delta_runs)),
            "max_delta_run": str(max((count for _value, count in delta_runs), default=0)),
            "delta_histogram_key": delta_histogram_key(delta_values),
            "delta_run_shape_key": delta_run_shape_key(delta_values),
            "top_nibble": top_nibble,
            "top_nibble_ratio": f"{top_nibble_ratio:.6f}",
            "gradient_class": "",
            "head_hex": expected[:16].hex(),
            "tail_hex": expected[-16:].hex(),
            "issues": ";".join(issues),
        }
        row["gradient_class"] = classify_gradient(row)
        rows.append(row)
    return rows, fixture_issues


def build_group_rows(rows: list[dict[str, str]], field: str, kind: str) -> list[dict[str, str]]:
    counters: dict[str, Counter[str]] = defaultdict(Counter)
    classes: dict[str, set[str]] = defaultdict(set)
    fixtures: dict[str, set[tuple[str, str, str]]] = defaultdict(set)
    samples: dict[str, dict[str, str]] = {}
    for row in rows:
        key = row.get(field, "")
        counters[key]["rows"] += 1
        counters[key]["bytes"] += int_value(row, "length")
        counters[key]["linear_exact_bytes"] += int_value(row, "linear_exact_bytes")
        counters[key]["small_delta_count"] += int_value(row, "small_delta_count")
        counters[key]["delta_count"] += int_value(row, "delta_count")
        classes[key].add(row.get("gradient_class", ""))
        fixtures[key].add(fixture_key(row))
        samples.setdefault(key, row)
    output: list[dict[str, str]] = []
    for key, counter in counters.items():
        sample = samples[key]
        output.append(
            {
                "group_kind": kind,
                "group_key": key,
                "rows": str(counter["rows"]),
                "bytes": str(counter["bytes"]),
                "linear_exact_bytes": str(counter["linear_exact_bytes"]),
                "small_delta_count": str(counter["small_delta_count"]),
                "delta_count": str(counter["delta_count"]),
                "gradient_classes": ";".join(sorted(classes[key])),
                "fixtures": str(len(fixtures[key])),
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
            }
        )
    output.sort(key=lambda row: (-int_value(row, "bytes"), -int_value(row, "rows"), row.get("group_key", "")))
    return output


def repeated_stats(groups: list[dict[str, str]]) -> tuple[int, int, int]:
    repeated = [row for row in groups if int_value(row, "rows") > 1]
    return len(repeated), sum(int_value(row, "rows") for row in repeated), sum(int_value(row, "bytes") for row in repeated)


def sum_bytes(rows: list[dict[str, str]]) -> int:
    return sum(int_value(row, "length") for row in rows)


def build_summary(
    rows: list[dict[str, str]],
    histogram_groups: list[dict[str, str]],
    run_groups: list[dict[str, str]],
    fixture_issue_count: int,
) -> dict[str, str]:
    total_delta_count = sum(int_value(row, "delta_count") for row in rows)
    small_delta_count = sum(int_value(row, "small_delta_count") for row in rows)
    dominant_delta_rows = [row for row in rows if float(row.get("dominant_delta_ratio", "0") or 0) >= 0.45]
    linear_ge50 = [row for row in rows if float(row.get("linear_exact_ratio", "0") or 0) >= 0.50]
    linear_ge75 = [row for row in rows if float(row.get("linear_exact_ratio", "0") or 0) >= 0.75]
    small_walk = [row for row in rows if row.get("gradient_class") in {"small_delta_walk", "banded_small_delta_walk"}]
    banded = [
        row
        for row in rows
        if row.get("gradient_class") in {"banded_small_delta_walk", "banded_mixed_walk"}
    ]
    repeated_hist = repeated_stats(histogram_groups)
    repeated_run = repeated_stats(run_groups)
    return {
        "scope": "total",
        "target_rows": str(len(rows)),
        "target_bytes": str(sum_bytes(rows)),
        "total_delta_count": str(total_delta_count),
        "small_delta_count": str(small_delta_count),
        "small_delta_ratio": f"{(small_delta_count / total_delta_count) if total_delta_count else 0.0:.6f}",
        "zero_delta_count": str(sum(int_value(row, "zero_delta_count") for row in rows)),
        "step_delta_count": str(sum(int_value(row, "step_delta_count") for row in rows)),
        "dominant_delta_rows": str(len(dominant_delta_rows)),
        "dominant_delta_bytes": str(sum_bytes(dominant_delta_rows)),
        "linear_ge50_rows": str(len(linear_ge50)),
        "linear_ge50_bytes": str(sum_bytes(linear_ge50)),
        "linear_ge75_rows": str(len(linear_ge75)),
        "linear_ge75_bytes": str(sum_bytes(linear_ge75)),
        "linear_full_rows": str(sum(1 for row in rows if row.get("linear_full_match") == "1")),
        "linear_exact_bytes_total": str(sum(int_value(row, "linear_exact_bytes") for row in rows)),
        "linear_best_single_exact_bytes": str(max((int_value(row, "linear_exact_bytes") for row in rows), default=0)),
        "small_delta_walk_rows": str(len(small_walk)),
        "small_delta_walk_bytes": str(sum_bytes(small_walk)),
        "banded_rows": str(len(banded)),
        "banded_bytes": str(sum_bytes(banded)),
        "repeated_delta_histogram_groups": str(repeated_hist[0]),
        "repeated_delta_histogram_rows": str(repeated_hist[1]),
        "repeated_delta_histogram_bytes": str(repeated_hist[2]),
        "repeated_delta_run_shape_groups": str(repeated_run[0]),
        "repeated_delta_run_shape_rows": str(repeated_run[1]),
        "repeated_delta_run_shape_bytes": str(repeated_run[2]),
        "gradient_classes": str(len({row.get("gradient_class", "") for row in rows})),
        "issue_rows": str(sum(1 for row in rows if row.get("issues")) + fixture_issue_count),
    }


def build_rows(
    target_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    rows, fixture_issues = build_target_rows(target_rows, fixture_rows)
    class_groups = build_group_rows(rows, "gradient_class", "gradient_class")
    delta_groups = build_group_rows(rows, "dominant_delta", "dominant_delta")
    histogram_groups = build_group_rows(rows, "delta_histogram_key", "delta_histogram")
    run_groups = build_group_rows(rows, "delta_run_shape_key", "delta_run_shape")
    summary = build_summary(rows, histogram_groups, run_groups, len(fixture_issues))
    return summary, rows, class_groups, delta_groups, histogram_groups, run_groups


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
    delta_groups: list[dict[str, str]],
    histogram_groups: list[dict[str, str]],
    run_groups: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "targets": rows,
        "classGroups": class_groups,
        "deltaGroups": delta_groups,
        "histogramGroups": histogram_groups,
        "runGroups": run_groups,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("targets.csv", output_dir / "targets.csv"),
            ("by_gradient_class.csv", output_dir / "by_gradient_class.csv"),
            ("by_dominant_delta.csv", output_dir / "by_dominant_delta.csv"),
            ("by_delta_histogram.csv", output_dir / "by_delta_histogram.csv"),
            ("by_delta_run_shape.csv", output_dir / "by_delta_run_shape.csv"),
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
    <div class="sub">Tests whether gradient-like noisy rows are simple ramps, small-delta walks, or banded mixed walks.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Gradient bytes</div><div class="value">{summary['target_bytes']}</div></div>
    <div class="stat"><div class="label">Small delta ratio</div><div class="value ok">{summary['small_delta_ratio']}</div></div>
    <div class="stat"><div class="label">Linear >= 75 bytes</div><div class="value warn">{summary['linear_ge75_bytes']}</div></div>
    <div class="stat"><div class="label">Small-delta walk bytes</div><div class="value">{summary['small_delta_walk_bytes']}</div></div>
    <div class="stat"><div class="label">Banded bytes</div><div class="value">{summary['banded_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2><div>{links}</div></section>
  <section class="panel"><h2>Gradient classes</h2>{render_table(class_groups, GROUP_FIELDNAMES, 80)}</section>
  <section class="panel"><h2>Dominant deltas</h2>{render_table(delta_groups, GROUP_FIELDNAMES, 80)}</section>
  <section class="panel"><h2>Delta histograms</h2>{render_table(histogram_groups, GROUP_FIELDNAMES, 120)}</section>
  <section class="panel"><h2>Delta run shapes</h2>{render_table(run_groups, GROUP_FIELDNAMES, 120)}</section>
  <section class="panel"><h2>Targets</h2>{render_table(rows, TARGET_FIELDNAMES, 120)}</section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_GRADIENT_PROBE = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe gradient-like noisy .tex nonzero gap rows.")
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Tiny Nonzero Gap Gradient Probe",
    )
    args = parser.parse_args()

    summary, rows, class_groups, delta_groups, histogram_groups, run_groups = build_rows(
        read_csv(args.targets),
        read_csv(args.fixtures),
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, rows)
    write_csv(args.output / "by_gradient_class.csv", GROUP_FIELDNAMES, class_groups)
    write_csv(args.output / "by_dominant_delta.csv", GROUP_FIELDNAMES, delta_groups)
    write_csv(args.output / "by_delta_histogram.csv", GROUP_FIELDNAMES, histogram_groups)
    write_csv(args.output / "by_delta_run_shape.csv", GROUP_FIELDNAMES, run_groups)
    html_path = args.output / "index.html"
    html_path.write_text(
        build_html(summary, rows, class_groups, delta_groups, histogram_groups, run_groups, args.output, args.title)
    )

    print(f"Gradient targets: {summary['target_rows']}")
    print(f"Gradient bytes: {summary['target_bytes']}")
    print(f"Small delta ratio: {summary['small_delta_ratio']}")
    print(f"Linear >= 75 bytes: {summary['linear_ge75_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
