#!/usr/bin/env python3
"""Score fixed fill-byte selector rules for nonzero gap fills."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_fill_selector_probe")
DEFAULT_PATTERNS = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_pattern_probe/patterns.csv")
DEFAULT_OPERATIONS = Path("output/tex_gap_segmentation_control_correlation_probe/operations.csv")
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")

FIXED_TRANSFORMS = ("identity", "low7", "bit_not", "nibble_swap")

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "target_bytes",
    "rule_rows",
    "false_free_rule_rows",
    "false_free_multirow_rule_rows",
    "best_false_free_correct_bytes",
    "best_false_free_rule",
    "best_false_free_applies_rows",
    "best_false_free_precision",
    "best_any_correct_bytes",
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
    "fill_byte_hex",
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
    "precision_rows",
    "precision_bytes",
    "fixtures",
    "fill_bytes_seen",
    "sample_pcx",
    "sample_frontier_id",
]

FAMILY_FIELDNAMES = [
    "rule_family",
    "rules",
    "false_free_rules",
    "best_correct_bytes",
    "best_false_bytes",
    "best_rule",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def fixture_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", "")


def op_key(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    return (
        row.get("rank", ""),
        row.get("pcx_name", ""),
        row.get("frontier_id", ""),
        row.get("expected_start", ""),
        row.get("expected_end", ""),
    )


def pattern_op_key(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    return (
        row.get("rank", ""),
        row.get("pcx_name", ""),
        row.get("frontier_id", ""),
        row.get("start", ""),
        row.get("end", ""),
    )


def safe_bytes_fromhex(value: str) -> bytes:
    if not value:
        return b""
    try:
        return bytes.fromhex(value)
    except ValueError:
        return b""


def read_bytes(path_text: str, issues: list[str], label: str) -> bytes:
    if not path_text:
        issues.append(f"missing_{label}_path")
        return b""
    try:
        return Path(path_text).read_bytes()
    except OSError as exc:
        issues.append(f"read_{label}_failed:{exc}")
        return b""


def nibble_swap(data: bytes) -> bytes:
    return bytes((((value & 0x0F) << 4) | ((value & 0xF0) >> 4)) for value in data)


def transform_bytes(data: bytes, transform: str) -> bytes:
    if transform == "identity":
        return data
    if transform == "low7":
        return bytes(value & 0x7F for value in data)
    if transform == "bit_not":
        return bytes(value ^ 0xFF for value in data)
    if transform == "nibble_swap":
        return nibble_swap(data)
    return b""


def control_signature(control_window_hex: str) -> str:
    if not control_window_hex:
        return "missing"
    return f"head={control_window_hex[:8]}|tail={control_window_hex[-8:]}"


def length_bucket(length: int) -> str:
    if length < 2:
        return "len1"
    if length < 4:
        return "len2_3"
    if length < 8:
        return "len4_7"
    return "len8_plus"


def load_expected_by_fixture(fixture_rows: list[dict[str, str]]) -> tuple[dict[tuple[str, str, str], bytes], list[str]]:
    expected: dict[tuple[str, str, str], bytes] = {}
    issues: list[str] = []
    for fixture in fixture_rows:
        local_issues: list[str] = []
        expected[fixture_key(fixture)] = read_bytes(fixture.get("expected_gap_path", ""), local_issues, "expected")
        issues.extend(f"{fixture_key(fixture)}:{issue}" for issue in local_issues)
    return expected, issues


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
        if pattern.get("pattern_class") != "fill_single_byte":
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
        if len(set(expected)) != 1:
            issues.append("not_single_byte_fill")
            continue
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
                "fill_byte_hex": f"0x{expected[0]:02x}",
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


def rule_conditions(row: dict[str, str]) -> list[tuple[str, str]]:
    return [
        ("offset_only", "all"),
        ("offset_length_bucket", f"length_bucket={row.get('length_bucket', '')}"),
        ("offset_start_mod64", f"start_mod64={row.get('start_mod64', '')}"),
        ("offset_control_ref_mod64", f"control_ref_mod64={row.get('control_ref_mod64', '')}"),
    ]


def build_rows(
    pattern_rows: list[dict[str, str]],
    operation_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    targets, pools_by_target, fixture_issues = build_targets(pattern_rows, operation_rows, fixture_rows)
    counters: dict[tuple[str, str, str, int, str], Counter[str]] = defaultdict(Counter)
    fixtures: dict[tuple[str, str, str, int, str], set[tuple[str, str, str]]] = defaultdict(set)
    fill_bytes: dict[tuple[str, str, str, int, str], set[str]] = defaultdict(set)
    samples: dict[tuple[str, str, str, int, str], dict[str, str]] = {}

    for target, pools in zip(targets, pools_by_target):
        fill_value = int(target["fill_byte_hex"], 16)
        length = int_value(target, "length")
        for pool_name, pool in pools.items():
            for transform in FIXED_TRANSFORMS:
                transformed = transform_bytes(pool, transform)
                for offset, predicted in enumerate(transformed):
                    for family, condition in rule_conditions(target):
                        key = family, pool_name, transform, offset, condition
                        counters[key]["applies_rows"] += 1
                        counters[key]["applies_bytes"] += length
                        is_correct = predicted == fill_value
                        counters[key]["correct_rows"] += 1 if is_correct else 0
                        counters[key]["correct_bytes"] += length if is_correct else 0
                        counters[key]["false_rows"] += 0 if is_correct else 1
                        counters[key]["false_bytes"] += 0 if is_correct else length
                        fixtures[key].add(fixture_key(target))
                        fill_bytes[key].add(target["fill_byte_hex"])
                        samples.setdefault(key, target)

    rule_rows = build_rule_rows(counters, fixtures, fill_bytes, samples)
    family_rows = build_family_rows(rule_rows)
    summary = build_summary(targets, rule_rows, fixture_issues)
    return summary, targets, rule_rows, family_rows


def build_rule_rows(
    counters: dict[tuple[str, str, str, int, str], Counter[str]],
    fixtures: dict[tuple[str, str, str, int, str], set[tuple[str, str, str]]],
    fill_bytes: dict[tuple[str, str, str, int, str], set[str]],
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
                "precision_rows": f"{(correct_rows / applies_rows) if applies_rows else 0.0:.6f}",
                "precision_bytes": f"{(correct_bytes / applies_bytes) if applies_bytes else 0.0:.6f}",
                "fixtures": str(len(fixtures[key])),
                "fill_bytes_seen": ";".join(sorted(fill_bytes[key])),
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
            }
        )
    rows.sort(
        key=lambda row: (
            int_value(row, "false_bytes"),
            -int_value(row, "correct_bytes"),
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
    rows: list[dict[str, str]] = []
    for family, rules in by_family.items():
        best = max(rules, key=lambda row: (int_value(row, "correct_bytes"), -int_value(row, "false_bytes")))
        rows.append(
            {
                "rule_family": family,
                "rules": str(len(rules)),
                "false_free_rules": str(sum(1 for row in rules if int_value(row, "false_bytes") == 0)),
                "best_correct_bytes": best.get("correct_bytes", "0"),
                "best_false_bytes": best.get("false_bytes", "0"),
                "best_rule": rule_label(best),
            }
        )
    rows.sort(key=lambda row: (-int_value(row, "best_correct_bytes"), int_value(row, "best_false_bytes")))
    return rows


def build_summary(
    target_rows: list[dict[str, str]],
    rule_rows: list[dict[str, str]],
    fixture_issues: list[str],
) -> dict[str, str]:
    false_free = [row for row in rule_rows if int_value(row, "false_bytes") == 0 and int_value(row, "correct_bytes") > 0]
    false_free_multi = [row for row in false_free if int_value(row, "correct_rows") > 1]
    best_false_free = max(false_free, key=lambda row: int_value(row, "correct_bytes"), default={})
    best_any = max(rule_rows, key=lambda row: (int_value(row, "correct_bytes"), -int_value(row, "false_bytes")), default={})
    return {
        "scope": "total",
        "target_rows": str(len(target_rows)),
        "target_bytes": str(sum(int_value(row, "length") for row in target_rows)),
        "rule_rows": str(len(rule_rows)),
        "false_free_rule_rows": str(len(false_free)),
        "false_free_multirow_rule_rows": str(len(false_free_multi)),
        "best_false_free_correct_bytes": best_false_free.get("correct_bytes", "0"),
        "best_false_free_rule": rule_label(best_false_free) if best_false_free else "",
        "best_false_free_applies_rows": best_false_free.get("applies_rows", "0"),
        "best_false_free_precision": best_false_free.get("precision_bytes", "0.000000"),
        "best_any_correct_bytes": best_any.get("correct_bytes", "0"),
        "best_any_false_bytes": best_any.get("false_bytes", "0"),
        "best_any_rule": rule_label(best_any) if best_any else "",
        "issue_rows": str(sum(1 for row in target_rows if row.get("issues")) + len(fixture_issues)),
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
    <div class="sub">Scores non-oracle fixed offset fill-byte selectors across every fill target.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Fill bytes</div><div class="value">{summary['target_bytes']}</div></div>
    <div class="stat"><div class="label">Rules</div><div class="value">{summary['rule_rows']}</div></div>
    <div class="stat"><div class="label">False-free rules</div><div class="value ok">{summary['false_free_rule_rows']}</div></div>
    <div class="stat"><div class="label">Best false-free bytes</div><div class="value warn">{summary['best_false_free_correct_bytes']}</div></div>
    <div class="stat"><div class="label">Best any false bytes</div><div class="value">{summary['best_any_false_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2><div>{links}</div></section>
  <section class="panel"><h2>Rule families</h2>{render_table(families, FAMILY_FIELDNAMES, 80)}</section>
  <section class="panel"><h2>Rule candidates</h2>{render_table(rules, RULE_FIELDNAMES, 360)}</section>
  <section class="panel"><h2>Targets</h2>{render_table(targets, TARGET_FIELDNAMES, 100)}</section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_FILL_SELECTOR_PROBE = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Score fixed fill-byte selectors for .tex nonzero gap fills.")
    parser.add_argument("--patterns", type=Path, default=DEFAULT_PATTERNS)
    parser.add_argument("--operations", type=Path, default=DEFAULT_OPERATIONS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Tiny Nonzero Gap Fill Selector Probe",
    )
    args = parser.parse_args()

    summary, targets, rules, families = build_rows(
        read_csv(args.patterns),
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

    print(f"Fill targets: {summary['target_rows']}")
    print(f"Rule rows: {summary['rule_rows']}")
    print(f"Best false-free bytes: {summary['best_false_free_correct_bytes']}")
    print(f"Best any false bytes: {summary['best_any_false_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
