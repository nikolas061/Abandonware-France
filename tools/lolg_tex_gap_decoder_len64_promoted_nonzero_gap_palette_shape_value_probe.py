#!/usr/bin/env python3
"""Score small-palette value selectors constrained by repeated palette shapes."""

from __future__ import annotations

import argparse
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_palette_selector_probe import (
    DEFAULT_FIXTURES,
    DEFAULT_OPERATIONS,
    FIXED_TRANSFORMS,
    SMALL_PALETTE_CLASSES,
    build_family_rows,
    build_rule_rows,
    build_summary,
    build_targets,
    fixture_key,
    read_csv,
    repeat_palette,
    rule_label,
    transform_bytes,
)
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_palette_shape_value_probe")
DEFAULT_SHAPE_TARGETS = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_palette_shape_probe/targets.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "target_bytes",
    "small_palette_2_rows",
    "small_palette_2_bytes",
    "small_palette_4_rows",
    "small_palette_4_bytes",
    "rule_rows",
    "false_free_rule_rows",
    "false_free_multirow_rule_rows",
    "best_false_free_correct_bytes",
    "best_false_free_exact_bytes",
    "best_false_free_rule",
    "best_false_free_applies_rows",
    "best_false_free_precision",
    "best_any_correct_bytes",
    "best_any_false_bytes",
    "best_any_exact_bytes",
    "best_any_rule",
    "exact_false_free_rule_rows",
    "best_exact_false_free_exact_bytes",
    "best_exact_false_free_rule",
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
    "control_window_signature",
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
    "head_hex",
    "tail_hex",
    "issues",
]

RULE_FIELDNAMES = [
    "rule_family",
    "pool",
    "transform",
    "palette_size",
    "source_offset",
    "condition",
    "applies_rows",
    "applies_bytes",
    "correct_rows",
    "correct_bytes",
    "false_rows",
    "false_bytes",
    "exact_rows",
    "exact_bytes",
    "exact_false_rows",
    "exact_false_bytes",
    "precision_rows",
    "precision_bytes",
    "exact_precision_bytes",
    "fixtures",
    "palettes_seen",
    "sample_pcx",
    "sample_frontier_id",
]

FAMILY_FIELDNAMES = [
    "rule_family",
    "rules",
    "false_free_rules",
    "exact_false_free_rules",
    "best_correct_bytes",
    "best_false_bytes",
    "best_exact_bytes",
    "best_rule",
]


def target_key(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    return (
        row.get("rank", ""),
        row.get("pcx_name", ""),
        row.get("frontier_id", ""),
        row.get("start", ""),
        row.get("end", ""),
    )


def enrich_targets(
    shape_rows: list[dict[str, str]],
    operation_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, bytes]], list[bytes], list[str]]:
    shape_inputs = [row for row in shape_rows if row.get("pattern_class") in SMALL_PALETTE_CLASSES]
    targets, pools_by_target, expected_by_target, fixture_issues = build_targets(
        shape_inputs,
        operation_rows,
        fixture_rows,
    )
    shapes_by_key = {target_key(row): row for row in shape_inputs}
    enriched: list[dict[str, str]] = []
    for target in targets:
        shape = shapes_by_key.get(target_key(target), {})
        row = {field: target.get(field, "") for field in TARGET_FIELDNAMES}
        for field in (
            "first_use_shape",
            "sorted_shape",
            "rank_run_shape",
            "run_length_shape",
            "run_count",
            "max_same_run_bytes",
            "dominant_ratio",
            "is_alternating",
            "is_dominant75",
        ):
            row[field] = shape.get(field, "")
        enriched.append(row)
    return enriched, pools_by_target, expected_by_target, fixture_issues


def shape_conditions(target: dict[str, str]) -> list[tuple[str, str]]:
    first_shape = target.get("first_use_shape", "")
    run_shape = target.get("run_length_shape", "")
    palette_size = target.get("palette_size", "")
    start_mod64 = target.get("start_mod64", "")
    control_ref_mod64 = target.get("control_ref_mod64", "")
    conditions = [
        ("first_use_shape", f"first_use_shape={first_shape}"),
        ("run_length_shape", f"run_length_shape={run_shape}"),
        ("first_use_shape_palette", f"palette_size={palette_size}|first_use_shape={first_shape}"),
        ("run_length_shape_palette", f"palette_size={palette_size}|run_length_shape={run_shape}"),
        (
            "first_use_shape_start_mod64",
            f"first_use_shape={first_shape}|start_mod64={start_mod64}",
        ),
        (
            "run_length_shape_start_mod64",
            f"run_length_shape={run_shape}|start_mod64={start_mod64}",
        ),
        (
            "first_use_shape_control_ref_mod64",
            f"first_use_shape={first_shape}|control_ref_mod64={control_ref_mod64}",
        ),
        (
            "run_length_shape_control_ref_mod64",
            f"run_length_shape={run_shape}|control_ref_mod64={control_ref_mod64}",
        ),
    ]
    return [(family, condition) for family, condition in conditions if "=" in condition]


def build_rows(
    shape_rows: list[dict[str, str]],
    operation_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    targets, pools_by_target, expected_by_target, fixture_issues = enrich_targets(
        shape_rows,
        operation_rows,
        fixture_rows,
    )
    counters: dict[tuple[str, str, str, int, int, str], Counter[str]] = defaultdict(Counter)
    fixtures: dict[tuple[str, str, str, int, int, str], set[tuple[str, str, str]]] = defaultdict(set)
    palettes: dict[tuple[str, str, str, int, int, str], set[str]] = defaultdict(set)
    samples: dict[tuple[str, str, str, int, int, str], dict[str, str]] = {}

    for target, pools, expected in zip(targets, pools_by_target, expected_by_target):
        length = len(expected)
        expected_unique = set(expected)
        palette_size = int_value(target, "palette_size")
        for pool_name, pool in pools.items():
            for transform in FIXED_TRANSFORMS:
                transformed = transform_bytes(pool, transform)
                if len(transformed) < palette_size:
                    continue
                for offset in range(0, len(transformed) - palette_size + 1):
                    selected = transformed[offset : offset + palette_size]
                    selected_set = set(selected)
                    has_palette_values = (
                        len(selected_set) == palette_size and expected_unique.issubset(selected_set)
                    )
                    exact_sequence = repeat_palette(selected, length) == expected
                    for family, condition in shape_conditions(target):
                        key = family, pool_name, transform, palette_size, offset, condition
                        counters[key]["applies_rows"] += 1
                        counters[key]["applies_bytes"] += length
                        counters[key]["correct_rows"] += 1 if has_palette_values else 0
                        counters[key]["correct_bytes"] += length if has_palette_values else 0
                        counters[key]["false_rows"] += 0 if has_palette_values else 1
                        counters[key]["false_bytes"] += 0 if has_palette_values else length
                        counters[key]["exact_rows"] += 1 if exact_sequence else 0
                        counters[key]["exact_bytes"] += length if exact_sequence else 0
                        counters[key]["exact_false_rows"] += 0 if exact_sequence else 1
                        counters[key]["exact_false_bytes"] += 0 if exact_sequence else length
                        fixtures[key].add(fixture_key(target))
                        palettes[key].add(" ".join(f"0x{value:02x}" for value in selected))
                        samples.setdefault(key, target)

    rule_rows = build_rule_rows(counters, fixtures, palettes, samples)
    family_rows = build_family_rows(rule_rows)
    summary = build_summary(targets, rule_rows, fixture_issues)
    return summary, targets, rule_rows, family_rows


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
    rules: list[dict[str, str]],
    families: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "targets": targets, "rules": rules, "families": families}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("targets.csv", output_dir / "targets.csv"),
            ("rule_candidates.csv", output_dir / "rule_candidates.csv"),
            ("by_rule_family.csv", output_dir / "by_rule_family.csv"),
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
table {{ width: 100%; border-collapse: collapse; min-width: 1880px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Scores fixed palette value selectors after constraining each rule by repeated sequence shape.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Palette bytes</div><div class="value">{summary['target_bytes']}</div></div>
    <div class="stat"><div class="label">Rules</div><div class="value">{summary['rule_rows']}</div></div>
    <div class="stat"><div class="label">False-free rules</div><div class="value ok">{summary['false_free_rule_rows']}</div></div>
    <div class="stat"><div class="label">False-free multi-row</div><div class="value ok">{summary['false_free_multirow_rule_rows']}</div></div>
    <div class="stat"><div class="label">Best false-free bytes</div><div class="value warn">{summary['best_false_free_correct_bytes']}</div></div>
    <div class="stat"><div class="label">Best any false bytes</div><div class="value">{summary['best_any_false_bytes']}</div></div>
    <div class="stat"><div class="label">Issues</div><div class="value ok">{summary['issue_rows']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2><div>{links}</div></section>
  <section class="panel"><h2>Rule families</h2>{render_table(families, FAMILY_FIELDNAMES, 120)}</section>
  <section class="panel"><h2>Rule candidates</h2>{render_table(rules, RULE_FIELDNAMES, 420)}</section>
  <section class="panel"><h2>Targets</h2>{render_table(targets, TARGET_FIELDNAMES, 160)}</section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_PALETTE_SHAPE_VALUE_PROBE = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Score shape-constrained palette value selectors for .tex nonzero gaps.")
    parser.add_argument("--shape-targets", type=Path, default=DEFAULT_SHAPE_TARGETS)
    parser.add_argument("--operations", type=Path, default=DEFAULT_OPERATIONS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Tiny Nonzero Gap Palette Shape Value Probe",
    )
    args = parser.parse_args()

    summary, targets, rules, families = build_rows(
        read_csv(args.shape_targets),
        read_csv(args.operations),
        read_csv(args.fixtures),
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, targets)
    write_csv(args.output / "rule_candidates.csv", RULE_FIELDNAMES, rules)
    write_csv(args.output / "by_rule_family.csv", FAMILY_FIELDNAMES, families)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, targets, rules, families, args.output, args.title))

    print(f"Palette targets: {summary['target_rows']}")
    print(f"Rule rows: {summary['rule_rows']}")
    print(f"False-free multi-row rules: {summary['false_free_multirow_rule_rows']}")
    print(f"Best false-free bytes: {summary['best_false_free_correct_bytes']}")
    print(f"Best any false bytes: {summary['best_any_false_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
