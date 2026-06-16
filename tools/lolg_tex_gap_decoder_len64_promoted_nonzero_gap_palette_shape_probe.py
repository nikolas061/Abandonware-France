#!/usr/bin/env python3
"""Classify normalized shapes for nonzero small-palette gap sequences."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_palette_selector_probe import (
    DEFAULT_FIXTURES,
    DEFAULT_OPERATIONS,
    DEFAULT_PATTERNS,
    build_targets,
    fixture_key,
    read_csv,
)
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_palette_shape_probe")

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "target_bytes",
    "small_palette_2_rows",
    "small_palette_2_bytes",
    "small_palette_4_rows",
    "small_palette_4_bytes",
    "first_use_shape_groups",
    "first_use_repeated_groups",
    "first_use_repeated_rows",
    "first_use_repeated_bytes",
    "run_length_shape_groups",
    "run_length_repeated_groups",
    "run_length_repeated_rows",
    "run_length_repeated_bytes",
    "best_first_use_shape_rows",
    "best_first_use_shape_bytes",
    "best_run_length_shape_rows",
    "best_run_length_shape_bytes",
    "alternating_rows",
    "alternating_bytes",
    "dominant75_rows",
    "dominant75_bytes",
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
    "pattern_class",
    "length",
    "length_bucket",
    "start",
    "end",
    "start_mod64",
    "control_ref_offset",
    "control_ref_mod64",
    "palette_size",
    "unique_hex",
    "first_use_shape",
    "sorted_shape",
    "rank_run_shape",
    "run_length_shape",
    "run_count",
    "max_same_run_bytes",
    "dominant_ratio",
    "is_alternating",
    "is_dominant75",
    "issues",
]

GROUP_FIELDNAMES = [
    "shape_kind",
    "shape",
    "rows",
    "bytes",
    "palette_sizes",
    "pattern_classes",
    "lengths",
    "fixtures",
    "sample_pcx",
    "sample_frontier_id",
]

GLYPHS = "0123456789abcdefghijklmnopqrstuvwxyz"


def sorted_shape(data: bytes) -> str:
    rank_by_value = {value: GLYPHS[index] for index, value in enumerate(sorted(set(data)))}
    return "".join(rank_by_value[value] for value in data)


def first_use_shape(data: bytes) -> str:
    rank_by_value: dict[int, str] = {}
    output: list[str] = []
    for value in data:
        if value not in rank_by_value:
            rank_by_value[value] = GLYPHS[len(rank_by_value)]
        output.append(rank_by_value[value])
    return "".join(output)


def run_lengths(shape: str) -> list[tuple[str, int]]:
    if not shape:
        return []
    runs: list[tuple[str, int]] = []
    current = shape[0]
    count = 1
    for value in shape[1:]:
        if value == current:
            count += 1
            continue
        runs.append((current, count))
        current = value
        count = 1
    runs.append((current, count))
    return runs


def summarize_expected(target: dict[str, str], expected: bytes) -> dict[str, str]:
    first_shape = first_use_shape(expected)
    sorted_rank_shape = sorted_shape(expected)
    runs = run_lengths(first_shape)
    counts = Counter(expected)
    max_run = max((length for _, length in runs), default=0)
    dominant_ratio = (max(counts.values()) / len(expected)) if expected else 0.0
    alternating = all(expected[index] != expected[index - 1] for index in range(1, len(expected)))
    row = {field: target.get(field, "") for field in TARGET_FIELDNAMES}
    row.update(
        {
            "first_use_shape": first_shape,
            "sorted_shape": sorted_rank_shape,
            "rank_run_shape": "-".join(f"{value}{length}" for value, length in runs),
            "run_length_shape": "-".join(str(length) for _, length in runs),
            "run_count": str(len(runs)),
            "max_same_run_bytes": str(max_run),
            "dominant_ratio": f"{dominant_ratio:.6f}",
            "is_alternating": "1" if alternating and len(expected) > 1 else "0",
            "is_dominant75": "1" if dominant_ratio >= 0.75 else "0",
        }
    )
    return row


def build_group_rows(rows: list[dict[str, str]], field: str, shape_kind: str) -> list[dict[str, str]]:
    counters: dict[str, Counter[str]] = defaultdict(Counter)
    palette_sizes: dict[str, set[str]] = defaultdict(set)
    classes: dict[str, set[str]] = defaultdict(set)
    lengths: dict[str, set[str]] = defaultdict(set)
    fixtures: dict[str, set[tuple[str, str, str]]] = defaultdict(set)
    samples: dict[str, dict[str, str]] = {}
    for row in rows:
        shape = row.get(field, "")
        length = int_value(row, "length")
        counters[shape]["rows"] += 1
        counters[shape]["bytes"] += length
        palette_sizes[shape].add(row.get("palette_size", ""))
        classes[shape].add(row.get("pattern_class", ""))
        lengths[shape].add(row.get("length", ""))
        fixtures[shape].add(fixture_key(row))
        samples.setdefault(shape, row)

    output: list[dict[str, str]] = []
    for shape, counter in counters.items():
        sample = samples[shape]
        output.append(
            {
                "shape_kind": shape_kind,
                "shape": shape,
                "rows": str(counter["rows"]),
                "bytes": str(counter["bytes"]),
                "palette_sizes": ";".join(sorted(palette_sizes[shape])),
                "pattern_classes": ";".join(sorted(classes[shape])),
                "lengths": ";".join(sorted(lengths[shape], key=lambda value: int(value) if value.isdigit() else -1)),
                "fixtures": str(len(fixtures[shape])),
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
            }
        )
    output.sort(
        key=lambda row: (
            -int_value(row, "rows"),
            -int_value(row, "bytes"),
            row.get("shape_kind", ""),
            row.get("shape", ""),
        )
    )
    return output


def repeated_stats(groups: list[dict[str, str]]) -> tuple[int, int, int]:
    repeated = [row for row in groups if int_value(row, "rows") > 1]
    return (
        len(repeated),
        sum(int_value(row, "rows") for row in repeated),
        sum(int_value(row, "bytes") for row in repeated),
    )


def sum_bytes(rows: list[dict[str, str]]) -> int:
    return sum(int_value(row, "length") for row in rows)


def build_summary(
    rows: list[dict[str, str]],
    first_groups: list[dict[str, str]],
    run_groups: list[dict[str, str]],
    extra_issue_rows: int,
) -> dict[str, str]:
    palette2 = [row for row in rows if row.get("pattern_class") == "small_palette_2"]
    palette4 = [row for row in rows if row.get("pattern_class") == "small_palette_4"]
    first_repeated_groups, first_repeated_rows, first_repeated_bytes = repeated_stats(first_groups)
    run_repeated_groups, run_repeated_rows, run_repeated_bytes = repeated_stats(run_groups)
    best_first = max(first_groups, key=lambda row: (int_value(row, "rows"), int_value(row, "bytes")), default={})
    best_run = max(run_groups, key=lambda row: (int_value(row, "rows"), int_value(row, "bytes")), default={})
    alternating = [row for row in rows if row.get("is_alternating") == "1"]
    dominant75 = [row for row in rows if row.get("is_dominant75") == "1"]
    return {
        "scope": "total",
        "target_rows": str(len(rows)),
        "target_bytes": str(sum_bytes(rows)),
        "small_palette_2_rows": str(len(palette2)),
        "small_palette_2_bytes": str(sum_bytes(palette2)),
        "small_palette_4_rows": str(len(palette4)),
        "small_palette_4_bytes": str(sum_bytes(palette4)),
        "first_use_shape_groups": str(len(first_groups)),
        "first_use_repeated_groups": str(first_repeated_groups),
        "first_use_repeated_rows": str(first_repeated_rows),
        "first_use_repeated_bytes": str(first_repeated_bytes),
        "run_length_shape_groups": str(len(run_groups)),
        "run_length_repeated_groups": str(run_repeated_groups),
        "run_length_repeated_rows": str(run_repeated_rows),
        "run_length_repeated_bytes": str(run_repeated_bytes),
        "best_first_use_shape_rows": best_first.get("rows", "0"),
        "best_first_use_shape_bytes": best_first.get("bytes", "0"),
        "best_run_length_shape_rows": best_run.get("rows", "0"),
        "best_run_length_shape_bytes": best_run.get("bytes", "0"),
        "alternating_rows": str(len(alternating)),
        "alternating_bytes": str(sum_bytes(alternating)),
        "dominant75_rows": str(len(dominant75)),
        "dominant75_bytes": str(sum_bytes(dominant75)),
        "issue_rows": str(sum(1 for row in rows if row.get("issues")) + extra_issue_rows),
    }


def build_rows(
    pattern_rows: list[dict[str, str]],
    operation_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    targets, _pools_by_target, expected_by_target, fixture_issues = build_targets(
        pattern_rows,
        operation_rows,
        fixture_rows,
    )
    rows = [summarize_expected(target, expected) for target, expected in zip(targets, expected_by_target)]
    first_groups = build_group_rows(rows, "first_use_shape", "first_use_shape")
    run_groups = build_group_rows(rows, "run_length_shape", "run_length_shape")
    summary = build_summary(rows, first_groups, run_groups, len(fixture_issues))
    return summary, rows, first_groups, run_groups


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
    first_groups: list[dict[str, str]],
    run_groups: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "rows": rows, "firstGroups": first_groups, "runGroups": run_groups}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("targets.csv", output_dir / "targets.csv"),
            ("by_first_use_shape.csv", output_dir / "by_first_use_shape.csv"),
            ("by_run_length_shape.csv", output_dir / "by_run_length_shape.csv"),
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
    <div class="sub">Normalizes small-palette byte sequences into reusable shape and run-length signatures.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Palette bytes</div><div class="value">{summary['target_bytes']}</div></div>
    <div class="stat"><div class="label">First-use shapes</div><div class="value">{summary['first_use_shape_groups']}</div></div>
    <div class="stat"><div class="label">Repeated first-use bytes</div><div class="value ok">{summary['first_use_repeated_bytes']}</div></div>
    <div class="stat"><div class="label">Run-length shapes</div><div class="value">{summary['run_length_shape_groups']}</div></div>
    <div class="stat"><div class="label">Repeated run-length bytes</div><div class="value ok">{summary['run_length_repeated_bytes']}</div></div>
    <div class="stat"><div class="label">Dominant 75 bytes</div><div class="value warn">{summary['dominant75_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2><div>{links}</div></section>
  <section class="panel"><h2>First-use shape groups</h2>{render_table(first_groups, GROUP_FIELDNAMES, 140)}</section>
  <section class="panel"><h2>Run-length shape groups</h2>{render_table(run_groups, GROUP_FIELDNAMES, 140)}</section>
  <section class="panel"><h2>Targets</h2>{render_table(rows, TARGET_FIELDNAMES, 160)}</section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_PALETTE_SHAPE_PROBE = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Classify normalized shapes for .tex nonzero small-palette gaps.")
    parser.add_argument("--patterns", type=Path, default=DEFAULT_PATTERNS)
    parser.add_argument("--operations", type=Path, default=DEFAULT_OPERATIONS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Tiny Nonzero Gap Palette Shape Probe",
    )
    args = parser.parse_args()

    summary, rows, first_groups, run_groups = build_rows(
        read_csv(args.patterns),
        read_csv(args.operations),
        read_csv(args.fixtures),
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, rows)
    write_csv(args.output / "by_first_use_shape.csv", GROUP_FIELDNAMES, first_groups)
    write_csv(args.output / "by_run_length_shape.csv", GROUP_FIELDNAMES, run_groups)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, rows, first_groups, run_groups, args.output, args.title))

    print(f"Palette targets: {summary['target_rows']}")
    print(f"First-use shapes: {summary['first_use_shape_groups']}")
    print(f"Repeated first-use bytes: {summary['first_use_repeated_bytes']}")
    print(f"Run-length shapes: {summary['run_length_shape_groups']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
