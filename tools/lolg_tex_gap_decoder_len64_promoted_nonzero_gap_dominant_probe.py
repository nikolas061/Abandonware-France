#!/usr/bin/env python3
"""Probe dominant-byte structure for nonzero gap rows."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_fill_selector_probe import (
    DEFAULT_FIXTURES,
    DEFAULT_OPERATIONS,
    DEFAULT_PATTERNS,
    FIXED_TRANSFORMS,
    control_signature,
    fixture_key,
    length_bucket,
    load_expected_by_fixture,
    op_key,
    pattern_op_key,
    read_bytes,
    read_csv,
    rule_conditions,
    safe_bytes_fromhex,
    transform_bytes,
)
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_dominant_probe")

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "target_bytes",
    "dominant_bytes",
    "exception_bytes",
    "exception_shape_groups",
    "repeated_exception_shape_groups",
    "repeated_exception_shape_rows",
    "repeated_exception_shape_bytes",
    "rule_rows",
    "false_free_rule_rows",
    "false_free_multirow_rule_rows",
    "best_false_free_dominant_bytes",
    "best_false_free_rule",
    "best_false_free_applies_rows",
    "best_any_dominant_bytes",
    "best_any_false_bytes",
    "best_any_rule",
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
    "length_bucket",
    "start",
    "end",
    "start_mod64",
    "control_ref_offset",
    "control_ref_mod64",
    "control_window_signature",
    "dominant_byte_hex",
    "dominant_count",
    "dominant_ratio",
    "exception_count",
    "exception_unique_hex",
    "exception_position_shape",
    "head_hex",
    "tail_hex",
    "issues",
]

SHAPE_FIELDNAMES = [
    "exception_position_shape",
    "rows",
    "bytes",
    "dominant_bytes",
    "exception_bytes",
    "fixtures",
    "sample_pcx",
    "sample_frontier_id",
]

RULE_FIELDNAMES = [
    "rule_family",
    "pool",
    "transform",
    "source_offset",
    "condition",
    "applies_rows",
    "applies_dominant_bytes",
    "correct_rows",
    "correct_dominant_bytes",
    "false_rows",
    "false_dominant_bytes",
    "precision_rows",
    "precision_bytes",
    "fixtures",
    "dominant_bytes_seen",
    "sample_pcx",
    "sample_frontier_id",
]

FAMILY_FIELDNAMES = [
    "rule_family",
    "rules",
    "false_free_rules",
    "best_correct_dominant_bytes",
    "best_false_dominant_bytes",
    "best_rule",
]


def exception_shape(expected: bytes, dominant: int) -> str:
    return "".join("." if value == dominant else "x" for value in expected)


def build_targets(
    pattern_rows: list[dict[str, str]],
    operation_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, bytes]], list[str]]:
    operations = {op_key(row): row for row in operation_rows}
    fixtures = {fixture_key(row): row for row in fixture_rows}
    expected_by_fixture, fixture_issues = load_expected_by_fixture(fixture_rows)
    target_rows: list[dict[str, str]] = []
    target_pools: list[dict[str, bytes]] = []

    for pattern in pattern_rows:
        if pattern.get("pattern_class") != "dominant_50":
            continue
        issues: list[str] = []
        key = fixture_key(pattern)
        expected_all = expected_by_fixture.get(key, b"")
        start = int_value(pattern, "start")
        end = int_value(pattern, "end")
        expected = expected_all[start:end]
        if not expected:
            issues.append("missing_expected_chunk")
            continue
        counts = Counter(expected)
        dominant, dominant_count = counts.most_common(1)[0]
        exception_values = sorted(value for value in counts if value != dominant)
        operation = operations.get(pattern_op_key(pattern), {})
        if not operation:
            issues.append("missing_operation")
        fixture = fixtures.get(key, {})
        fragment = read_bytes(fixture.get("fragment_path", ""), issues, "fragment") if fixture else b""
        control_prefix = read_bytes(fixture.get("control_prefix_path", ""), issues, "control_prefix") if fixture else b""
        control_window_hex = operation.get("control_window_hex", "")
        control_window = safe_bytes_fromhex(control_window_hex)
        neighbor = b"".join(
            safe_bytes_fromhex(operation.get(field, ""))
            for field in ("pre1_hex", "pre2_hex", "pre4_hex", "next2_hex")
        )
        control_ref = operation.get("control_ref_offset", "") or "missing"
        control_ref_mod64 = str(int(control_ref) % 64) if control_ref.isdigit() else "missing"
        target_rows.append(
            {
                "rank": pattern.get("rank", ""),
                "archive": pattern.get("archive", ""),
                "archive_tag": pattern.get("archive_tag", ""),
                "pcx_name": pattern.get("pcx_name", ""),
                "frontier_id": pattern.get("frontier_id", ""),
                "span_index": pattern.get("span_index", ""),
                "run_index": pattern.get("run_index", ""),
                "op_index": pattern.get("op_index", ""),
                "length": str(len(expected)),
                "length_bucket": length_bucket(len(expected)),
                "start": pattern.get("start", ""),
                "end": pattern.get("end", ""),
                "start_mod64": str(start % 64),
                "control_ref_offset": control_ref,
                "control_ref_mod64": control_ref_mod64,
                "control_window_signature": control_signature(control_window_hex),
                "dominant_byte_hex": f"0x{dominant:02x}",
                "dominant_count": str(dominant_count),
                "dominant_ratio": f"{dominant_count / len(expected):.6f}",
                "exception_count": str(len(expected) - dominant_count),
                "exception_unique_hex": ";".join(f"0x{value:02x}" for value in exception_values),
                "exception_position_shape": exception_shape(expected, dominant),
                "head_hex": expected[:16].hex(),
                "tail_hex": expected[-16:].hex(),
                "issues": ";".join(issues),
            }
        )
        target_pools.append(
            {
                "control_window": control_window,
                "control_prefix": control_prefix,
                "fragment": fragment,
                "neighbor": neighbor,
            }
        )
    return target_rows, target_pools, fixture_issues


def build_rows(
    pattern_rows: list[dict[str, str]],
    operation_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    targets, pools_by_target, fixture_issues = build_targets(pattern_rows, operation_rows, fixture_rows)
    counters: dict[tuple[str, str, str, int, str], Counter[str]] = defaultdict(Counter)
    fixtures: dict[tuple[str, str, str, int, str], set[tuple[str, str, str]]] = defaultdict(set)
    dominant_values: dict[tuple[str, str, str, int, str], set[str]] = defaultdict(set)
    samples: dict[tuple[str, str, str, int, str], dict[str, str]] = {}

    for target, pools in zip(targets, pools_by_target):
        dominant_value = int(target["dominant_byte_hex"], 16)
        dominant_count = int_value(target, "dominant_count")
        for pool_name, pool in pools.items():
            for transform in FIXED_TRANSFORMS:
                transformed = transform_bytes(pool, transform)
                for offset, predicted in enumerate(transformed):
                    for family, condition in rule_conditions(target):
                        key = family, pool_name, transform, offset, condition
                        counters[key]["applies_rows"] += 1
                        counters[key]["applies_dominant_bytes"] += dominant_count
                        is_correct = predicted == dominant_value
                        counters[key]["correct_rows"] += 1 if is_correct else 0
                        counters[key]["correct_dominant_bytes"] += dominant_count if is_correct else 0
                        counters[key]["false_rows"] += 0 if is_correct else 1
                        counters[key]["false_dominant_bytes"] += 0 if is_correct else dominant_count
                        fixtures[key].add(fixture_key(target))
                        dominant_values[key].add(target["dominant_byte_hex"])
                        samples.setdefault(key, target)

    rule_rows = build_rule_rows(counters, fixtures, dominant_values, samples)
    family_rows = build_family_rows(rule_rows)
    shape_rows = build_shape_rows(targets)
    summary = build_summary(targets, shape_rows, rule_rows, fixture_issues)
    return summary, targets, shape_rows, rule_rows, family_rows


def build_rule_rows(
    counters: dict[tuple[str, str, str, int, str], Counter[str]],
    fixtures: dict[tuple[str, str, str, int, str], set[tuple[str, str, str]]],
    dominant_values: dict[tuple[str, str, str, int, str], set[str]],
    samples: dict[tuple[str, str, str, int, str], dict[str, str]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for key, counter in counters.items():
        family, pool, transform, offset, condition = key
        applies_rows = int(counter["applies_rows"])
        applies_bytes = int(counter["applies_dominant_bytes"])
        correct_rows = int(counter["correct_rows"])
        correct_bytes = int(counter["correct_dominant_bytes"])
        false_rows = int(counter["false_rows"])
        false_bytes = int(counter["false_dominant_bytes"])
        sample = samples[key]
        rows.append(
            {
                "rule_family": family,
                "pool": pool,
                "transform": transform,
                "source_offset": str(offset),
                "condition": condition,
                "applies_rows": str(applies_rows),
                "applies_dominant_bytes": str(applies_bytes),
                "correct_rows": str(correct_rows),
                "correct_dominant_bytes": str(correct_bytes),
                "false_rows": str(false_rows),
                "false_dominant_bytes": str(false_bytes),
                "precision_rows": f"{(correct_rows / applies_rows) if applies_rows else 0.0:.6f}",
                "precision_bytes": f"{(correct_bytes / applies_bytes) if applies_bytes else 0.0:.6f}",
                "fixtures": str(len(fixtures[key])),
                "dominant_bytes_seen": ";".join(sorted(dominant_values[key])),
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
            }
        )
    rows.sort(
        key=lambda row: (
            int_value(row, "false_dominant_bytes"),
            -int_value(row, "correct_dominant_bytes"),
            -int_value(row, "correct_rows"),
            row.get("rule_family", ""),
            row.get("pool", ""),
            row.get("transform", ""),
            int_value(row, "source_offset"),
        )
    )
    return rows


def rule_label(row: dict[str, str]) -> str:
    return (
        f"{row.get('rule_family')}|{row.get('pool')}|{row.get('transform')}|"
        f"offset={row.get('source_offset')}|{row.get('condition')}"
    )


def build_family_rows(rule_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    by_family: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rule_rows:
        by_family[row.get("rule_family", "")].append(row)
    output: list[dict[str, str]] = []
    for family, rows in by_family.items():
        best = max(
            rows,
            key=lambda row: (int_value(row, "correct_dominant_bytes"), -int_value(row, "false_dominant_bytes")),
        )
        output.append(
            {
                "rule_family": family,
                "rules": str(len(rows)),
                "false_free_rules": str(sum(1 for row in rows if int_value(row, "false_dominant_bytes") == 0)),
                "best_correct_dominant_bytes": best.get("correct_dominant_bytes", "0"),
                "best_false_dominant_bytes": best.get("false_dominant_bytes", "0"),
                "best_rule": rule_label(best),
            }
        )
    output.sort(key=lambda row: (-int_value(row, "best_correct_dominant_bytes"), int_value(row, "best_false_dominant_bytes")))
    return output


def build_shape_rows(targets: list[dict[str, str]]) -> list[dict[str, str]]:
    counters: dict[str, Counter[str]] = defaultdict(Counter)
    fixtures: dict[str, set[tuple[str, str, str]]] = defaultdict(set)
    samples: dict[str, dict[str, str]] = {}
    for target in targets:
        shape = target.get("exception_position_shape", "")
        counters[shape]["rows"] += 1
        counters[shape]["bytes"] += int_value(target, "length")
        counters[shape]["dominant_bytes"] += int_value(target, "dominant_count")
        counters[shape]["exception_bytes"] += int_value(target, "exception_count")
        fixtures[shape].add(fixture_key(target))
        samples.setdefault(shape, target)
    rows: list[dict[str, str]] = []
    for shape, counter in counters.items():
        sample = samples[shape]
        rows.append(
            {
                "exception_position_shape": shape,
                "rows": str(counter["rows"]),
                "bytes": str(counter["bytes"]),
                "dominant_bytes": str(counter["dominant_bytes"]),
                "exception_bytes": str(counter["exception_bytes"]),
                "fixtures": str(len(fixtures[shape])),
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
            }
        )
    rows.sort(key=lambda row: (-int_value(row, "rows"), -int_value(row, "bytes"), row.get("exception_position_shape", "")))
    return rows


def build_summary(
    targets: list[dict[str, str]],
    shape_rows: list[dict[str, str]],
    rule_rows: list[dict[str, str]],
    fixture_issues: list[str],
) -> dict[str, str]:
    false_free = [
        row for row in rule_rows if int_value(row, "false_dominant_bytes") == 0 and int_value(row, "correct_dominant_bytes") > 0
    ]
    false_free_multi = [row for row in false_free if int_value(row, "correct_rows") > 1]
    best_false_free = max(false_free, key=lambda row: int_value(row, "correct_dominant_bytes"), default={})
    best_any = max(
        rule_rows,
        key=lambda row: (int_value(row, "correct_dominant_bytes"), -int_value(row, "false_dominant_bytes")),
        default={},
    )
    repeated_shapes = [row for row in shape_rows if int_value(row, "rows") > 1]
    return {
        "scope": "total",
        "target_rows": str(len(targets)),
        "target_bytes": str(sum(int_value(row, "length") for row in targets)),
        "dominant_bytes": str(sum(int_value(row, "dominant_count") for row in targets)),
        "exception_bytes": str(sum(int_value(row, "exception_count") for row in targets)),
        "exception_shape_groups": str(len(shape_rows)),
        "repeated_exception_shape_groups": str(len(repeated_shapes)),
        "repeated_exception_shape_rows": str(sum(int_value(row, "rows") for row in repeated_shapes)),
        "repeated_exception_shape_bytes": str(sum(int_value(row, "bytes") for row in repeated_shapes)),
        "rule_rows": str(len(rule_rows)),
        "false_free_rule_rows": str(len(false_free)),
        "false_free_multirow_rule_rows": str(len(false_free_multi)),
        "best_false_free_dominant_bytes": best_false_free.get("correct_dominant_bytes", "0"),
        "best_false_free_rule": rule_label(best_false_free) if best_false_free else "",
        "best_false_free_applies_rows": best_false_free.get("applies_rows", "0"),
        "best_any_dominant_bytes": best_any.get("correct_dominant_bytes", "0"),
        "best_any_false_bytes": best_any.get("false_dominant_bytes", "0"),
        "best_any_rule": rule_label(best_any) if best_any else "",
        "issue_rows": str(sum(1 for row in targets if row.get("issues")) + len(fixture_issues)),
    }


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
    shapes: list[dict[str, str]],
    rules: list[dict[str, str]],
    families: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "targets": targets, "shapes": shapes, "rules": rules, "families": families}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("targets.csv", output_dir / "targets.csv"),
            ("by_exception_shape.csv", output_dir / "by_exception_shape.csv"),
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
    <div class="sub">Separates dominant-byte source evidence from unresolved exception positions.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Target bytes</div><div class="value">{summary['target_bytes']}</div></div>
    <div class="stat"><div class="label">Dominant bytes</div><div class="value ok">{summary['dominant_bytes']}</div></div>
    <div class="stat"><div class="label">Exception bytes</div><div class="value warn">{summary['exception_bytes']}</div></div>
    <div class="stat"><div class="label">False-free rules</div><div class="value">{summary['false_free_rule_rows']}</div></div>
    <div class="stat"><div class="label">Best false-free dominant bytes</div><div class="value">{summary['best_false_free_dominant_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2><div>{links}</div></section>
  <section class="panel"><h2>Exception shapes</h2>{render_table(shapes, SHAPE_FIELDNAMES, 80)}</section>
  <section class="panel"><h2>Rule families</h2>{render_table(families, FAMILY_FIELDNAMES, 80)}</section>
  <section class="panel"><h2>Rule candidates</h2>{render_table(rules, RULE_FIELDNAMES, 260)}</section>
  <section class="panel"><h2>Targets</h2>{render_table(targets, TARGET_FIELDNAMES, 80)}</section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_DOMINANT_PROBE = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe dominant-byte structure for .tex nonzero gaps.")
    parser.add_argument("--patterns", type=Path, default=DEFAULT_PATTERNS)
    parser.add_argument("--operations", type=Path, default=DEFAULT_OPERATIONS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Tiny Nonzero Gap Dominant Probe",
    )
    args = parser.parse_args()

    summary, targets, shapes, rules, families = build_rows(
        read_csv(args.patterns),
        read_csv(args.operations),
        read_csv(args.fixtures),
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, targets)
    write_csv(args.output / "by_exception_shape.csv", SHAPE_FIELDNAMES, shapes)
    write_csv(args.output / "rule_candidates.csv", RULE_FIELDNAMES, rules)
    write_csv(args.output / "by_rule_family.csv", FAMILY_FIELDNAMES, families)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, targets, shapes, rules, families, args.output, args.title))

    print(f"Dominant targets: {summary['target_rows']}")
    print(f"Dominant bytes: {summary['dominant_bytes']}")
    print(f"Exception bytes: {summary['exception_bytes']}")
    print(f"Best false-free dominant bytes: {summary['best_false_free_dominant_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
