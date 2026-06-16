#!/usr/bin/env python3
"""Score value producers for flat-walk nonzero gap rows."""

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
    fixture_key,
    load_expected_by_fixture,
    read_bytes,
    read_csv,
    transform_bytes,
)
from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_flat_walk_probe import (
    DEFAULT_OUTPUT as DEFAULT_SHAPE_OUTPUT,
    value_runs,
)
from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_flat_walk_source_probe import (
    source_pools,
    target_op_key,
)
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_value_probe")
DEFAULT_TARGETS = DEFAULT_SHAPE_OUTPUT / "targets.csv"

BASE_TRANSFORMS = ("identity", "low7", "bit_not", "nibble_swap")
SHIFT_DELTAS = (-3, -2, -1, 0, 1, 2, 3)

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "target_bytes",
    "rule_rows",
    "exact_rule_rows",
    "false_free_rule_rows",
    "false_free_multirow_rule_rows",
    "best_false_free_exact_bytes",
    "best_false_free_correct_bytes",
    "best_false_free_rule",
    "best_false_free_applies_rows",
    "best_false_free_precision",
    "best_any_exact_bytes",
    "best_any_correct_bytes",
    "best_any_false_bytes",
    "best_any_rule",
    "best_target_exact_rows",
    "best_target_exact_bytes",
    "prefix_copy_exact_rows",
    "prefix_copy_exact_bytes",
    "prefix_copy_best_distance",
    "max_offset",
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
    "value_run_count",
    "unique_run_values",
    "run_length_shape_key",
    "run_value_shape_key",
    "best_family",
    "best_pool",
    "best_transform",
    "best_offset",
    "best_correct_bytes",
    "best_false_bytes",
    "best_exact",
    "best_ratio",
    "prefix_copy_offset",
    "prefix_copy_distance",
    "prefix_copy_exact",
    "issues",
]

RULE_FIELDNAMES = [
    "rule_family",
    "pool",
    "transform",
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
    "precision_rows",
    "precision_bytes",
    "fixtures",
    "sample_pcx",
    "sample_frontier_id",
]

FAMILY_FIELDNAMES = [
    "rule_family",
    "pool",
    "transform",
    "rules",
    "false_free_rules",
    "exact_rules",
    "best_correct_bytes",
    "best_false_bytes",
    "best_exact_bytes",
    "best_rule",
]


def op_key(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    return (
        row.get("rank", ""),
        row.get("pcx_name", ""),
        row.get("frontier_id", ""),
        row.get("expected_start", ""),
        row.get("expected_end", ""),
    )


def transformed_pool(data: bytes, transform: str) -> bytes:
    if "_shift" not in transform:
        return transform_bytes(data, transform)
    base, delta_text = transform.split("_shift", 1)
    base_data = transform_bytes(data, base)
    delta = int(delta_text)
    return bytes((value + delta) & 0xFF for value in base_data)


def transform_names() -> list[str]:
    names: list[str] = []
    for base in BASE_TRANSFORMS:
        for delta in SHIFT_DELTAS:
            names.append(base if delta == 0 else f"{base}_shift{delta:+d}")
    return names


def first_use_indices(values: list[int]) -> list[int]:
    index_by_value: dict[int, int] = {}
    output: list[int] = []
    for value in values:
        if value not in index_by_value:
            index_by_value[value] = len(index_by_value)
        output.append(index_by_value[value])
    return output


def expand_runs(values: list[int], lengths: list[int]) -> bytes:
    if len(values) != len(lengths):
        return b""
    output = bytearray()
    for value, length in zip(values, lengths):
        output.extend([value & 0xFF] * length)
    return bytes(output)


def build_palette_sequence(source: bytes, offset: int, run_values: list[int], run_lengths: list[int]) -> bytes:
    indices = first_use_indices(run_values)
    palette_size = (max(indices) + 1) if indices else 0
    if palette_size <= 0 or offset + palette_size > len(source):
        return b""
    palette = source[offset : offset + palette_size]
    return expand_runs([palette[index] for index in indices], run_lengths)


def build_run_value_sequence(source: bytes, offset: int, run_lengths: list[int]) -> bytes:
    if offset + len(run_lengths) > len(source):
        return b""
    return expand_runs(list(source[offset : offset + len(run_lengths)]), run_lengths)


def best_prefix_copy(prefix: bytes, expected: bytes) -> tuple[int, int, bool]:
    if not expected or len(prefix) < len(expected):
        return -1, 0, False
    offset = prefix.rfind(expected)
    if offset >= 0:
        return offset, len(prefix) - offset, True
    best_offset = -1
    best_correct = 0
    for candidate_offset in range(0, len(prefix) - len(expected) + 1):
        correct = sum(
            1
            for left, right in zip(prefix[candidate_offset : candidate_offset + len(expected)], expected)
            if left == right
        )
        if correct > best_correct:
            best_correct = correct
            best_offset = candidate_offset
    return best_offset, (len(prefix) - best_offset) if best_offset >= 0 else 0, False


def score_bytes(candidate: bytes, expected: bytes) -> tuple[int, int, bool]:
    if len(candidate) != len(expected):
        return 0, len(expected), False
    correct = sum(1 for left, right in zip(candidate, expected) if left == right)
    false = len(expected) - correct
    return correct, false, false == 0


def control_ref_mod64(operation: dict[str, str]) -> str:
    value = operation.get("control_ref_offset", "") or "missing"
    return str(int(value) % 64) if value.isdigit() else "missing"


def length_bucket(length: int) -> str:
    if length < 16:
        return "len_lt16"
    if length < 32:
        return "len16_31"
    if length < 64:
        return "len32_63"
    return "len64_plus"


def rule_conditions(target: dict[str, str]) -> list[tuple[str, str]]:
    length = int_value(target, "length")
    return [
        ("offset_only", "all"),
        ("offset_length", f"length={length}"),
        ("offset_length_bucket", f"length_bucket={length_bucket(length)}"),
        ("offset_start_mod64", f"start_mod64={target.get('start_mod64', '')}"),
        ("offset_control_ref_mod64", f"control_ref_mod64={target.get('control_ref_mod64', '')}"),
        (
            "offset_length_start_mod64",
            f"length_bucket={length_bucket(length)}|start_mod64={target.get('start_mod64', '')}",
        ),
        ("run_length_shape", f"run_length_shape={target.get('run_length_shape_key', '')}"),
        ("run_value_shape", f"run_value_shape={target.get('run_value_shape_key', '')}"),
        (
            "shape_pair",
            f"run_length_shape={target.get('run_length_shape_key', '')}|"
            f"run_value_shape={target.get('run_value_shape_key', '')}",
        ),
    ]


def limited_pools(
    target: dict[str, str],
    fixture: dict[str, str],
    operation: dict[str, str],
    issues: list[str],
    max_offset: int,
) -> dict[str, bytes]:
    pools = source_pools(target, fixture, operation, issues)
    segment = read_bytes(fixture.get("segment_gap_path", ""), issues, "segment_gap") if fixture else b""
    if segment:
        pools["segment_head"] = segment[:max_offset]
    return {name: data[:max_offset] for name, data in pools.items() if data}


def target_base_row(
    target: dict[str, str],
    operation: dict[str, str],
    expected: bytes,
    run_values: list[int],
) -> dict[str, str]:
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
        "control_ref_offset": operation.get("control_ref_offset", "") or "missing",
        "control_ref_mod64": control_ref_mod64(operation),
        "value_run_count": str(len(run_values)),
        "unique_run_values": str(len(set(run_values))),
        "run_length_shape_key": target.get("run_length_shape_key", ""),
        "run_value_shape_key": target.get("run_value_shape_key", ""),
        "best_family": "",
        "best_pool": "",
        "best_transform": "",
        "best_offset": "",
        "best_correct_bytes": "0",
        "best_false_bytes": str(len(expected)),
        "best_exact": "0",
        "best_ratio": "0.000000",
        "prefix_copy_offset": "",
        "prefix_copy_distance": "",
        "prefix_copy_exact": "0",
        "issues": "",
    }


def update_best_target(
    row: dict[str, str],
    *,
    family: str,
    pool: str,
    transform: str,
    offset: int,
    correct: int,
    false: int,
    exact: bool,
) -> None:
    current = (
        int_value(row, "best_exact"),
        int_value(row, "best_correct_bytes"),
        -int_value(row, "best_false_bytes"),
    )
    candidate = (1 if exact else 0, correct, -false)
    if candidate <= current:
        return
    row["best_family"] = family
    row["best_pool"] = pool
    row["best_transform"] = transform
    row["best_offset"] = str(offset)
    row["best_correct_bytes"] = str(correct)
    row["best_false_bytes"] = str(false)
    row["best_exact"] = "1" if exact else "0"
    total = correct + false
    row["best_ratio"] = f"{(correct / total) if total else 0.0:.6f}"


def rule_label(row: dict[str, str]) -> str:
    return (
        f"{row.get('rule_family')}|{row.get('pool')}|{row.get('transform')}|"
        f"offset={row.get('source_offset')}|{row.get('condition')}"
    )


def build_rule_rows(
    counters: dict[tuple[str, str, str, int, str], Counter[str]],
    fixtures: dict[tuple[str, str, str, int, str], set[tuple[str, str, str]]],
    samples: dict[tuple[str, str, str, int, str], dict[str, str]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for key, counter in counters.items():
        family, pool, transform, offset, condition = key
        applies_rows = int(counter["applies_rows"])
        applies_bytes = int(counter["applies_bytes"])
        correct_rows = int(counter["correct_rows"])
        correct_bytes = int(counter["correct_bytes"])
        false_rows = int(counter["false_rows"])
        false_bytes = int(counter["false_bytes"])
        exact_rows = int(counter["exact_rows"])
        exact_bytes = int(counter["exact_bytes"])
        sample = samples[key]
        rows.append(
            {
                "rule_family": family,
                "pool": pool,
                "transform": transform,
                "source_offset": str(offset),
                "condition": condition,
                "applies_rows": str(applies_rows),
                "applies_bytes": str(applies_bytes),
                "correct_rows": str(correct_rows),
                "correct_bytes": str(correct_bytes),
                "false_rows": str(false_rows),
                "false_bytes": str(false_bytes),
                "exact_rows": str(exact_rows),
                "exact_bytes": str(exact_bytes),
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
            -int_value(row, "exact_bytes"),
            -int_value(row, "correct_bytes"),
            -int_value(row, "applies_rows"),
            row.get("rule_family", ""),
            row.get("pool", ""),
            row.get("transform", ""),
            int_value(row, "source_offset"),
        )
    )
    return rows


def build_family_rows(rule_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    by_family: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rule_rows:
        by_family[(row.get("rule_family", ""), row.get("pool", ""), row.get("transform", ""))].append(row)
    rows: list[dict[str, str]] = []
    for key, rules in by_family.items():
        family, pool, transform = key
        best = max(
            rules,
            key=lambda row: (
                int_value(row, "exact_bytes"),
                int_value(row, "correct_bytes"),
                -int_value(row, "false_bytes"),
            ),
        )
        rows.append(
            {
                "rule_family": family,
                "pool": pool,
                "transform": transform,
                "rules": str(len(rules)),
                "false_free_rules": str(
                    sum(1 for row in rules if int_value(row, "false_bytes") == 0 and int_value(row, "correct_bytes") > 0)
                ),
                "exact_rules": str(sum(1 for row in rules if int_value(row, "exact_rows") > 0)),
                "best_correct_bytes": best.get("correct_bytes", "0"),
                "best_false_bytes": best.get("false_bytes", "0"),
                "best_exact_bytes": best.get("exact_bytes", "0"),
                "best_rule": rule_label(best),
            }
        )
    rows.sort(key=lambda row: (-int_value(row, "best_exact_bytes"), -int_value(row, "best_correct_bytes")))
    return rows


def build_summary(
    targets: list[dict[str, str]],
    rules: list[dict[str, str]],
    fixture_issues: list[str],
    *,
    max_offset: int,
) -> dict[str, str]:
    false_free = [row for row in rules if int_value(row, "false_bytes") == 0 and int_value(row, "correct_bytes") > 0]
    false_free_multi = [row for row in false_free if int_value(row, "applies_rows") > 1]
    exact_rules = [row for row in rules if int_value(row, "exact_rows") > 0]
    best_false_free = max(
        false_free,
        key=lambda row: (int_value(row, "exact_bytes"), int_value(row, "correct_bytes")),
        default={},
    )
    best_any = max(
        rules,
        key=lambda row: (int_value(row, "exact_bytes"), int_value(row, "correct_bytes"), -int_value(row, "false_bytes")),
        default={},
    )
    prefix_exact = [row for row in targets if row.get("prefix_copy_exact") == "1"]
    prefix_distances = [int_value(row, "prefix_copy_distance") for row in prefix_exact]
    best_target_exact = [row for row in targets if row.get("best_exact") == "1"]
    return {
        "scope": "total",
        "target_rows": str(len(targets)),
        "target_bytes": str(sum(int_value(row, "length") for row in targets)),
        "rule_rows": str(len(rules)),
        "exact_rule_rows": str(len(exact_rules)),
        "false_free_rule_rows": str(len(false_free)),
        "false_free_multirow_rule_rows": str(len(false_free_multi)),
        "best_false_free_exact_bytes": best_false_free.get("exact_bytes", "0"),
        "best_false_free_correct_bytes": best_false_free.get("correct_bytes", "0"),
        "best_false_free_rule": rule_label(best_false_free) if best_false_free else "",
        "best_false_free_applies_rows": best_false_free.get("applies_rows", "0"),
        "best_false_free_precision": best_false_free.get("precision_bytes", "0.000000"),
        "best_any_exact_bytes": best_any.get("exact_bytes", "0"),
        "best_any_correct_bytes": best_any.get("correct_bytes", "0"),
        "best_any_false_bytes": best_any.get("false_bytes", "0"),
        "best_any_rule": rule_label(best_any) if best_any else "",
        "best_target_exact_rows": str(len(best_target_exact)),
        "best_target_exact_bytes": str(sum(int_value(row, "length") for row in best_target_exact)),
        "prefix_copy_exact_rows": str(len(prefix_exact)),
        "prefix_copy_exact_bytes": str(sum(int_value(row, "length") for row in prefix_exact)),
        "prefix_copy_best_distance": str(min(prefix_distances, default=0)),
        "max_offset": str(max_offset),
        "issue_rows": str(sum(1 for row in targets if row.get("issues")) + len(fixture_issues)),
    }


def candidate_sequences(
    family: str,
    source: bytes,
    offset: int,
    expected: bytes,
    run_lengths: list[int],
    run_values: list[int],
) -> bytes:
    if family == "full_span":
        return source[offset : offset + len(expected)]
    if family == "run_values":
        return build_run_value_sequence(source, offset, run_lengths)
    if family == "palette_first_use":
        return build_palette_sequence(source, offset, run_values, run_lengths)
    return b""


def build_rows(
    target_rows: list[dict[str, str]],
    operation_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    *,
    max_offset: int,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    expected_by_fixture, fixture_issues = load_expected_by_fixture(fixture_rows)
    operations = {op_key(row): row for row in operation_rows}
    fixtures = {fixture_key(row): row for row in fixture_rows}
    counters: dict[tuple[str, str, str, int, str], Counter[str]] = defaultdict(Counter)
    rule_fixtures: dict[tuple[str, str, str, int, str], set[tuple[str, str, str]]] = defaultdict(set)
    samples: dict[tuple[str, str, str, int, str], dict[str, str]] = {}
    enriched_targets: list[dict[str, str]] = []
    transforms = transform_names()

    for target in target_rows:
        issues = [issue for issue in target.get("issues", "").split(";") if issue]
        expected_all = expected_by_fixture.get(fixture_key(target), b"")
        start = int_value(target, "start")
        end = int_value(target, "end")
        expected = expected_all[start:end]
        if not expected:
            issues.append("missing_expected_chunk")
            continue
        operation = operations.get(target_op_key(target), {})
        if not operation:
            issues.append("missing_operation")
        fixture = fixtures.get(fixture_key(target), {})
        runs = value_runs(expected)
        run_values = [value for value, _count in runs]
        run_lengths = [count for _value, count in runs]
        row = target_base_row(target, operation, expected, run_values)
        prefix_offset, prefix_distance, prefix_exact = best_prefix_copy(expected_all[:start], expected)
        row["prefix_copy_offset"] = str(prefix_offset) if prefix_offset >= 0 else ""
        row["prefix_copy_distance"] = str(prefix_distance) if prefix_offset >= 0 else ""
        row["prefix_copy_exact"] = "1" if prefix_exact else "0"

        pools = limited_pools(target, fixture, operation, issues, max_offset=max_offset)
        for pool_name, pool in pools.items():
            for transform in transforms:
                transformed = transformed_pool(pool, transform)
                for family in ("full_span", "run_values", "palette_first_use"):
                    if family == "full_span":
                        limit = max(0, len(transformed) - len(expected) + 1)
                    elif family == "run_values":
                        limit = max(0, len(transformed) - len(run_lengths) + 1)
                    else:
                        limit = max(0, len(transformed) - len(set(run_values)) + 1)
                    for offset in range(limit):
                        candidate = candidate_sequences(family, transformed, offset, expected, run_lengths, run_values)
                        correct, false, exact = score_bytes(candidate, expected)
                        update_best_target(
                            row,
                            family=family,
                            pool=pool_name,
                            transform=transform,
                            offset=offset,
                            correct=correct,
                            false=false,
                            exact=exact,
                        )
                        for condition_family, condition in rule_conditions(target):
                            key = f"{family}_{condition_family}", pool_name, transform, offset, condition
                            counters[key]["applies_rows"] += 1
                            counters[key]["applies_bytes"] += len(expected)
                            counters[key]["correct_rows"] += 1 if correct > 0 else 0
                            counters[key]["correct_bytes"] += correct
                            counters[key]["false_rows"] += 1 if false > 0 else 0
                            counters[key]["false_bytes"] += false
                            counters[key]["exact_rows"] += 1 if exact else 0
                            counters[key]["exact_bytes"] += len(expected) if exact else 0
                            rule_fixtures[key].add(fixture_key(target))
                            samples.setdefault(key, target)

        row["issues"] = ";".join(issues)
        enriched_targets.append(row)

    rule_rows = build_rule_rows(counters, rule_fixtures, samples)
    family_rows = build_family_rows(rule_rows)
    summary = build_summary(enriched_targets, rule_rows, fixture_issues, max_offset=max_offset)
    return summary, enriched_targets, rule_rows, family_rows


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
table {{ width: 100%; border-collapse: collapse; min-width: 1900px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Scores full-span, run-value, and first-use palette generators for flat-walk nonzero gaps.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Flat-walk bytes</div><div class="value">{summary['target_bytes']}</div></div>
    <div class="stat"><div class="label">Rules</div><div class="value">{summary['rule_rows']}</div></div>
    <div class="stat"><div class="label">False-free multi-row</div><div class="value ok">{summary['false_free_multirow_rule_rows']}</div></div>
    <div class="stat"><div class="label">Best false-free exact bytes</div><div class="value warn">{summary['best_false_free_exact_bytes']}</div></div>
    <div class="stat"><div class="label">Best target exact bytes</div><div class="value">{summary['best_target_exact_bytes']}</div></div>
    <div class="stat"><div class="label">Prefix copy bytes</div><div class="value">{summary['prefix_copy_exact_bytes']}</div></div>
    <div class="stat"><div class="label">Max offset</div><div class="value">{summary['max_offset']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2><div>{links}</div></section>
  <section class="panel"><h2>Rule families</h2>{render_table(families, FAMILY_FIELDNAMES, 160)}</section>
  <section class="panel"><h2>Rule candidates</h2>{render_table(rules, RULE_FIELDNAMES, 520)}</section>
  <section class="panel"><h2>Targets</h2>{render_table(targets, TARGET_FIELDNAMES, 120)}</section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_FLAT_WALK_VALUE_PROBE = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Score .tex flat-walk value generators.")
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("--operations", type=Path, default=DEFAULT_OPERATIONS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--max-offset", type=int, default=96)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Tiny Nonzero Gap Flat Walk Value Probe",
    )
    args = parser.parse_args()

    summary, targets, rules, families = build_rows(
        read_csv(args.targets),
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

    print(f"Flat-walk targets: {summary['target_rows']}")
    print(f"Rule rows: {summary['rule_rows']}")
    print(f"False-free multi-row rules: {summary['false_free_multirow_rule_rows']}")
    print(f"Best false-free exact bytes: {summary['best_false_free_exact_bytes']}")
    print(f"Best target exact bytes: {summary['best_target_exact_bytes']}")
    print(f"Prefix copy exact bytes: {summary['prefix_copy_exact_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
