#!/usr/bin/env python3
"""Score non-contiguous two-byte palette selectors constrained by sequence shape."""

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
    fixture_key,
    read_csv,
    transform_bytes,
)
from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_palette_shape_value_probe import (
    DEFAULT_SHAPE_TARGETS,
    TARGET_FIELDNAMES,
    enrich_targets,
)
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_palette_pair_value_probe")

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "target_bytes",
    "rule_rows",
    "false_free_rule_rows",
    "false_free_multirow_rule_rows",
    "exact_false_free_rule_rows",
    "best_false_free_correct_bytes",
    "best_false_free_exact_bytes",
    "best_false_free_rule",
    "best_false_free_applies_rows",
    "best_false_free_precision",
    "best_exact_false_free_exact_bytes",
    "best_exact_false_free_rule",
    "best_any_correct_bytes",
    "best_any_false_bytes",
    "best_any_exact_bytes",
    "best_any_rule",
    "max_offset",
    "issue_rows",
]

RULE_FIELDNAMES = [
    "rule_family",
    "pool",
    "transform",
    "offset_a",
    "offset_b",
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


def shape_sequence(first_use_shape: str, palette: bytes) -> bytes:
    output = bytearray()
    for glyph in first_use_shape:
        index = int(glyph, 36) if glyph.isalnum() else -1
        if index < 0 or index >= len(palette):
            return b""
        output.append(palette[index])
    return bytes(output)


def pair_conditions(target: dict[str, str]) -> list[tuple[str, str]]:
    first_shape = target.get("first_use_shape", "")
    run_shape = target.get("run_length_shape", "")
    length_bucket = target.get("length_bucket", "")
    start_mod64 = target.get("start_mod64", "")
    control_ref_mod64 = target.get("control_ref_mod64", "")
    return [
        ("pair_offset_only", "all"),
        ("pair_length_bucket", f"length_bucket={length_bucket}"),
        ("pair_start_mod64", f"start_mod64={start_mod64}"),
        ("pair_control_ref_mod64", f"control_ref_mod64={control_ref_mod64}"),
        (
            "pair_length_control_ref_mod64",
            f"length_bucket={length_bucket}|control_ref_mod64={control_ref_mod64}",
        ),
        ("pair_first_use_shape", f"first_use_shape={first_shape}"),
        ("pair_run_length_shape", f"run_length_shape={run_shape}"),
        (
            "pair_first_use_shape_start_mod64",
            f"first_use_shape={first_shape}|start_mod64={start_mod64}",
        ),
        (
            "pair_run_length_shape_start_mod64",
            f"run_length_shape={run_shape}|start_mod64={start_mod64}",
        ),
        (
            "pair_first_use_shape_control_ref_mod64",
            f"first_use_shape={first_shape}|control_ref_mod64={control_ref_mod64}",
        ),
        (
            "pair_run_length_shape_control_ref_mod64",
            f"run_length_shape={run_shape}|control_ref_mod64={control_ref_mod64}",
        ),
    ]


def rule_label(row: dict[str, str]) -> str:
    return (
        f"{row.get('rule_family')}|{row.get('pool')}|{row.get('transform')}|"
        f"offset_a={row.get('offset_a')}|offset_b={row.get('offset_b')}|{row.get('condition')}"
    )


def build_rule_rows(
    counters: dict[tuple[str, str, str, int, int, str], Counter[str]],
    fixtures: dict[tuple[str, str, str, int, int, str], set[tuple[str, str, str]]],
    palettes: dict[tuple[str, str, str, int, int, str], set[str]],
    samples: dict[tuple[str, str, str, int, int, str], dict[str, str]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for key, counter in counters.items():
        family, pool, transform, offset_a, offset_b, condition = key
        applies_rows = int(counter["applies_rows"])
        applies_bytes = int(counter["applies_bytes"])
        correct_rows = int(counter["correct_rows"])
        correct_bytes = int(counter["correct_bytes"])
        false_rows = int(counter["false_rows"])
        false_bytes = int(counter["false_bytes"])
        exact_rows = int(counter["exact_rows"])
        exact_bytes = int(counter["exact_bytes"])
        exact_false_rows = int(counter["exact_false_rows"])
        exact_false_bytes = int(counter["exact_false_bytes"])
        sample = samples[key]
        rows.append(
            {
                "rule_family": family,
                "pool": pool,
                "transform": transform,
                "offset_a": str(offset_a),
                "offset_b": str(offset_b),
                "condition": condition,
                "applies_rows": str(applies_rows),
                "applies_bytes": str(applies_bytes),
                "correct_rows": str(correct_rows),
                "correct_bytes": str(correct_bytes),
                "false_rows": str(false_rows),
                "false_bytes": str(false_bytes),
                "exact_rows": str(exact_rows),
                "exact_bytes": str(exact_bytes),
                "exact_false_rows": str(exact_false_rows),
                "exact_false_bytes": str(exact_false_bytes),
                "precision_rows": f"{(correct_rows / applies_rows) if applies_rows else 0.0:.6f}",
                "precision_bytes": f"{(correct_bytes / applies_bytes) if applies_bytes else 0.0:.6f}",
                "exact_precision_bytes": f"{(exact_bytes / applies_bytes) if applies_bytes else 0.0:.6f}",
                "fixtures": str(len(fixtures[key])),
                "palettes_seen": ";".join(sorted(palettes[key])[:16]),
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
            }
        )
    rows.sort(
        key=lambda row: (
            int_value(row, "false_bytes"),
            -int_value(row, "exact_bytes"),
            -int_value(row, "correct_bytes"),
            -int_value(row, "correct_rows"),
            row.get("rule_family", ""),
            row.get("pool", ""),
            row.get("transform", ""),
            int_value(row, "offset_a"),
            int_value(row, "offset_b"),
        )
    )
    return rows


def build_family_rows(rule_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    by_family: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rule_rows:
        by_family[row.get("rule_family", "")].append(row)
    rows: list[dict[str, str]] = []
    for family, rules in by_family.items():
        best = max(
            rules,
            key=lambda row: (
                int_value(row, "correct_bytes"),
                int_value(row, "exact_bytes"),
                -int_value(row, "false_bytes"),
            ),
        )
        rows.append(
            {
                "rule_family": family,
                "rules": str(len(rules)),
                "false_free_rules": str(sum(1 for row in rules if int_value(row, "false_bytes") == 0)),
                "exact_false_free_rules": str(
                    sum(1 for row in rules if int_value(row, "exact_false_bytes") == 0)
                ),
                "best_correct_bytes": best.get("correct_bytes", "0"),
                "best_false_bytes": best.get("false_bytes", "0"),
                "best_exact_bytes": best.get("exact_bytes", "0"),
                "best_rule": rule_label(best),
            }
        )
    rows.sort(key=lambda row: (-int_value(row, "best_exact_bytes"), -int_value(row, "best_correct_bytes")))
    return rows


def build_summary(
    target_rows: list[dict[str, str]],
    rule_rows: list[dict[str, str]],
    fixture_issues: list[str],
    *,
    max_offset: int,
) -> dict[str, str]:
    false_free = [row for row in rule_rows if int_value(row, "false_bytes") == 0 and int_value(row, "correct_bytes") > 0]
    false_free_multi = [row for row in false_free if int_value(row, "correct_rows") > 1]
    exact_false_free = [
        row for row in rule_rows if int_value(row, "exact_false_bytes") == 0 and int_value(row, "exact_bytes") > 0
    ]
    best_false_free = max(
        false_free,
        key=lambda row: (int_value(row, "correct_bytes"), int_value(row, "exact_bytes")),
        default={},
    )
    best_exact_false_free = max(exact_false_free, key=lambda row: int_value(row, "exact_bytes"), default={})
    best_any = max(
        rule_rows,
        key=lambda row: (int_value(row, "exact_bytes"), int_value(row, "correct_bytes"), -int_value(row, "false_bytes")),
        default={},
    )
    return {
        "scope": "total",
        "target_rows": str(len(target_rows)),
        "target_bytes": str(sum(int_value(row, "length") for row in target_rows)),
        "rule_rows": str(len(rule_rows)),
        "false_free_rule_rows": str(len(false_free)),
        "false_free_multirow_rule_rows": str(len(false_free_multi)),
        "exact_false_free_rule_rows": str(len(exact_false_free)),
        "best_false_free_correct_bytes": best_false_free.get("correct_bytes", "0"),
        "best_false_free_exact_bytes": best_false_free.get("exact_bytes", "0"),
        "best_false_free_rule": rule_label(best_false_free) if best_false_free else "",
        "best_false_free_applies_rows": best_false_free.get("applies_rows", "0"),
        "best_false_free_precision": best_false_free.get("precision_bytes", "0.000000"),
        "best_exact_false_free_exact_bytes": best_exact_false_free.get("exact_bytes", "0"),
        "best_exact_false_free_rule": rule_label(best_exact_false_free) if best_exact_false_free else "",
        "best_any_correct_bytes": best_any.get("correct_bytes", "0"),
        "best_any_false_bytes": best_any.get("false_bytes", "0"),
        "best_any_exact_bytes": best_any.get("exact_bytes", "0"),
        "best_any_rule": rule_label(best_any) if best_any else "",
        "max_offset": str(max_offset),
        "issue_rows": str(sum(1 for row in target_rows if row.get("issues")) + len(fixture_issues)),
    }


def build_rows(
    shape_rows: list[dict[str, str]],
    operation_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    *,
    max_offset: int,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    targets, pools_by_target, expected_by_target, fixture_issues = enrich_targets(
        shape_rows,
        operation_rows,
        fixture_rows,
    )
    pair_targets: list[dict[str, str]] = []
    pair_pools: list[dict[str, bytes]] = []
    pair_expected: list[bytes] = []
    for target, pools, expected in zip(targets, pools_by_target, expected_by_target):
        if target.get("pattern_class") != "small_palette_2" or int_value(target, "palette_size") != 2:
            continue
        pair_targets.append(target)
        pair_pools.append(pools)
        pair_expected.append(expected)

    counters: dict[tuple[str, str, str, int, int, str], Counter[str]] = defaultdict(Counter)
    fixtures: dict[tuple[str, str, str, int, int, str], set[tuple[str, str, str]]] = defaultdict(set)
    palettes: dict[tuple[str, str, str, int, int, str], set[str]] = defaultdict(set)
    samples: dict[tuple[str, str, str, int, int, str], dict[str, str]] = {}

    for target, pools, expected in zip(pair_targets, pair_pools, pair_expected):
        length = len(expected)
        expected_unique = set(expected)
        first_shape = target.get("first_use_shape", "")
        for pool_name, pool in pools.items():
            for transform in FIXED_TRANSFORMS:
                transformed = transform_bytes(pool, transform)
                limit = min(len(transformed), max_offset)
                if limit < 2:
                    continue
                for offset_a in range(limit):
                    byte_a = transformed[offset_a]
                    for offset_b in range(limit):
                        if offset_a == offset_b:
                            continue
                        selected = bytes((byte_a, transformed[offset_b]))
                        if len(set(selected)) != 2:
                            continue
                        has_palette_values = set(selected) == expected_unique
                        exact_sequence = shape_sequence(first_shape, selected) == expected
                        for family, condition in pair_conditions(target):
                            key = family, pool_name, transform, offset_a, offset_b, condition
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
    summary = build_summary(pair_targets, rule_rows, fixture_issues, max_offset=max_offset)
    return summary, pair_targets, rule_rows, family_rows


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
    <div class="sub">Tests two independent source offsets for palette-2 values, then generates exact bytes through first-use shape.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Palette-2 bytes</div><div class="value">{summary['target_bytes']}</div></div>
    <div class="stat"><div class="label">Rules</div><div class="value">{summary['rule_rows']}</div></div>
    <div class="stat"><div class="label">False-free rules</div><div class="value ok">{summary['false_free_rule_rows']}</div></div>
    <div class="stat"><div class="label">False-free multi-row</div><div class="value ok">{summary['false_free_multirow_rule_rows']}</div></div>
    <div class="stat"><div class="label">Best exact false-free bytes</div><div class="value warn">{summary['best_exact_false_free_exact_bytes']}</div></div>
    <div class="stat"><div class="label">Best any false bytes</div><div class="value">{summary['best_any_false_bytes']}</div></div>
    <div class="stat"><div class="label">Max offset</div><div class="value">{summary['max_offset']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2><div>{links}</div></section>
  <section class="panel"><h2>Rule families</h2>{render_table(families, FAMILY_FIELDNAMES, 120)}</section>
  <section class="panel"><h2>Rule candidates</h2>{render_table(rules, RULE_FIELDNAMES, 420)}</section>
  <section class="panel"><h2>Targets</h2>{render_table(targets, TARGET_FIELDNAMES, 120)}</section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_PALETTE_PAIR_VALUE_PROBE = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Score two-offset palette-2 selectors for .tex nonzero gaps.")
    parser.add_argument("--shape-targets", type=Path, default=DEFAULT_SHAPE_TARGETS)
    parser.add_argument("--operations", type=Path, default=DEFAULT_OPERATIONS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--max-offset", type=int, default=64)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Tiny Nonzero Gap Palette Pair Value Probe",
    )
    args = parser.parse_args()

    summary, targets, rules, families = build_rows(
        read_csv(args.shape_targets),
        read_csv(args.operations),
        read_csv(args.fixtures),
        max_offset=args.max_offset,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, targets)
    write_csv(args.output / "rule_candidates.csv", RULE_FIELDNAMES, rules)
    write_csv(args.output / "by_rule_family.csv", FAMILY_FIELDNAMES, families)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, targets, rules, families, args.output, args.title))

    print(f"Palette-2 targets: {summary['target_rows']}")
    print(f"Rule rows: {summary['rule_rows']}")
    print(f"False-free multi-row rules: {summary['false_free_multirow_rule_rows']}")
    print(f"Best exact false-free bytes: {summary['best_exact_false_free_exact_bytes']}")
    print(f"Best any false bytes: {summary['best_any_false_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
