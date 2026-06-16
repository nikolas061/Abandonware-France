#!/usr/bin/env python3
"""Probe local sources for flat-walk run lengths and transitions."""

from __future__ import annotations

import argparse
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_fill_selector_probe import (
    DEFAULT_FIXTURES,
    DEFAULT_OPERATIONS,
    fixture_key,
    load_expected_by_fixture,
    op_key,
    read_bytes,
    read_csv,
    safe_bytes_fromhex,
)
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_source_probe")
DEFAULT_TARGETS = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_probe/targets.csv")

TRANSFORMS = (
    "identity",
    "low4",
    "high4",
    "low4_plus1",
    "high4_plus1",
    "pairs_low_high",
    "pairs_high_low",
)

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "target_bytes",
    "length_symbol_count",
    "length_exact_total",
    "length_best_single_exact",
    "length_ge50_rows",
    "length_ge50_bytes",
    "transition_symbol_count",
    "transition_exact_total",
    "transition_best_single_exact",
    "transition_ge50_rows",
    "transition_ge50_bytes",
    "both_ge50_rows",
    "both_ge50_bytes",
    "length_source_groups",
    "transition_source_groups",
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
    "value_run_count",
    "transition_count",
    "length_best_pool",
    "length_best_transform",
    "length_best_offset",
    "length_best_exact",
    "length_best_ratio",
    "transition_best_pool",
    "transition_best_transform",
    "transition_best_offset",
    "transition_best_exact",
    "transition_best_ratio",
    "verdict",
    "issues",
]

GROUP_FIELDNAMES = [
    "source_kind",
    "pool",
    "transform",
    "rows",
    "bytes",
    "symbol_count",
    "exact_total",
    "best_single_exact",
    "ge50_rows",
    "fixtures",
    "sample_pcx",
    "sample_frontier_id",
]


def signed_delta(left: int, right: int) -> int:
    return ((right - left + 128) & 0xFF) - 128


def value_runs(data: bytes) -> list[tuple[int, int]]:
    if not data:
        return []
    runs: list[tuple[int, int]] = []
    current = data[0]
    count = 1
    for value in data[1:]:
        if value == current:
            count += 1
            continue
        runs.append((current, count))
        current = value
        count = 1
    runs.append((current, count))
    return runs


def transformed_values(data: bytes, transform: str) -> list[int]:
    if transform == "identity":
        return list(data)
    if transform == "low4":
        return [value & 0x0F for value in data]
    if transform == "high4":
        return [value >> 4 for value in data]
    if transform == "low4_plus1":
        return [(value & 0x0F) + 1 for value in data]
    if transform == "high4_plus1":
        return [(value >> 4) + 1 for value in data]
    if transform == "pairs_low_high":
        output: list[int] = []
        for value in data:
            output.extend([value & 0x0F, value >> 4])
        return output
    if transform == "pairs_high_low":
        output = []
        for value in data:
            output.extend([value >> 4, value & 0x0F])
        return output
    return []


def best_sequence_match(sequence: list[int], pools: dict[str, bytes]) -> dict[str, str]:
    best = {
        "pool": "",
        "transform": "",
        "offset": "",
        "exact": "0",
        "ratio": "0.000000",
    }
    if not sequence:
        return best
    for pool_name, pool in pools.items():
        if not pool:
            continue
        for transform in TRANSFORMS:
            values = transformed_values(pool, transform)
            if len(values) < len(sequence):
                continue
            for offset in range(0, len(values) - len(sequence) + 1):
                exact = sum(
                    1
                    for left, right in zip(sequence, values[offset : offset + len(sequence)])
                    if left == right
                )
                if exact > int_value(best, "exact"):
                    best = {
                        "pool": pool_name,
                        "transform": transform,
                        "offset": str(offset),
                        "exact": str(exact),
                        "ratio": f"{exact / len(sequence):.6f}",
                    }
    return best


def target_op_key(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    return (
        row.get("rank", ""),
        row.get("pcx_name", ""),
        row.get("frontier_id", ""),
        row.get("start", ""),
        row.get("end", ""),
    )


def source_pools(
    target: dict[str, str],
    fixture: dict[str, str],
    operation: dict[str, str],
    issues: list[str],
) -> dict[str, bytes]:
    return {
        "segment_gap": read_bytes(fixture.get("segment_gap_path", ""), issues, "segment_gap") if fixture else b"",
        "fragment": read_bytes(fixture.get("fragment_path", ""), issues, "fragment") if fixture else b"",
        "control_prefix": read_bytes(fixture.get("control_prefix_path", ""), issues, "control_prefix") if fixture else b"",
        "control_window": safe_bytes_fromhex(operation.get("control_window_hex", "")),
        "neighbor": b"".join(
            safe_bytes_fromhex(operation.get(field, ""))
            for field in ("pre1_hex", "pre2_hex", "pre4_hex", "next2_hex")
        ),
    }


def verdict_for(row: dict[str, str]) -> str:
    length_ratio = float(row.get("length_best_ratio", "0") or 0)
    transition_ratio = float(row.get("transition_best_ratio", "0") or 0)
    if length_ratio >= 0.75 and transition_ratio >= 0.75:
        return "strong_source_review"
    if length_ratio >= 0.50 and transition_ratio >= 0.50:
        return "mixed_source_review"
    if length_ratio >= 0.50 or transition_ratio >= 0.50:
        return "partial_source_review"
    return "weak_source"


def build_target_rows(
    target_rows: list[dict[str, str]],
    operation_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[str]]:
    expected_by_fixture, fixture_issues = load_expected_by_fixture(fixture_rows)
    operations = {op_key(row): row for row in operation_rows}
    fixtures = {fixture_key(row): row for row in fixture_rows}
    rows: list[dict[str, str]] = []
    for target in target_rows:
        issues = [issue for issue in target.get("issues", "").split(";") if issue]
        expected_all = expected_by_fixture.get(fixture_key(target), b"")
        start = int_value(target, "start")
        end = int_value(target, "end")
        expected = expected_all[start:end]
        if not expected:
            issues.append("missing_expected_chunk")
            continue
        runs = value_runs(expected)
        run_lengths = [count for _value, count in runs]
        run_values = [value for value, _count in runs]
        transitions = [signed_delta(run_values[index - 1], run_values[index]) for index in range(1, len(run_values))]
        fixture = fixtures.get(fixture_key(target), {})
        operation = operations.get(target_op_key(target), {})
        if not operation:
            issues.append("missing_operation")
        pools = source_pools(target, fixture, operation, issues)
        length_best = best_sequence_match(run_lengths, pools)
        transition_best = best_sequence_match(transitions, pools)
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
            "value_run_count": str(len(run_lengths)),
            "transition_count": str(len(transitions)),
            "length_best_pool": length_best["pool"],
            "length_best_transform": length_best["transform"],
            "length_best_offset": length_best["offset"],
            "length_best_exact": length_best["exact"],
            "length_best_ratio": length_best["ratio"],
            "transition_best_pool": transition_best["pool"],
            "transition_best_transform": transition_best["transform"],
            "transition_best_offset": transition_best["offset"],
            "transition_best_exact": transition_best["exact"],
            "transition_best_ratio": transition_best["ratio"],
            "verdict": "",
            "issues": ";".join(issues),
        }
        row["verdict"] = verdict_for(row)
        rows.append(row)
    return rows, fixture_issues


def build_group_rows(rows: list[dict[str, str]], source_kind: str) -> list[dict[str, str]]:
    pool_field = f"{source_kind}_best_pool"
    transform_field = f"{source_kind}_best_transform"
    exact_field = f"{source_kind}_best_exact"
    count_field = "value_run_count" if source_kind == "length" else "transition_count"
    ratio_field = f"{source_kind}_best_ratio"
    counters: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    fixtures: dict[tuple[str, str], set[tuple[str, str, str]]] = defaultdict(set)
    samples: dict[tuple[str, str], dict[str, str]] = {}
    for row in rows:
        key = row.get(pool_field, ""), row.get(transform_field, "")
        counters[key]["rows"] += 1
        counters[key]["bytes"] += int_value(row, "length")
        counters[key]["symbol_count"] += int_value(row, count_field)
        counters[key]["exact_total"] += int_value(row, exact_field)
        counters[key]["best_single_exact"] = max(counters[key]["best_single_exact"], int_value(row, exact_field))
        counters[key]["ge50_rows"] += 1 if float(row.get(ratio_field, "0") or 0) >= 0.50 else 0
        fixtures[key].add(fixture_key(row))
        samples.setdefault(key, row)
    output: list[dict[str, str]] = []
    for key, counter in counters.items():
        sample = samples[key]
        output.append(
            {
                "source_kind": source_kind,
                "pool": key[0],
                "transform": key[1],
                "rows": str(counter["rows"]),
                "bytes": str(counter["bytes"]),
                "symbol_count": str(counter["symbol_count"]),
                "exact_total": str(counter["exact_total"]),
                "best_single_exact": str(counter["best_single_exact"]),
                "ge50_rows": str(counter["ge50_rows"]),
                "fixtures": str(len(fixtures[key])),
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
            }
        )
    output.sort(
        key=lambda row: (
            -int_value(row, "exact_total"),
            -int_value(row, "bytes"),
            row.get("source_kind", ""),
            row.get("pool", ""),
            row.get("transform", ""),
        )
    )
    return output


def sum_bytes(rows: list[dict[str, str]]) -> int:
    return sum(int_value(row, "length") for row in rows)


def build_summary(
    rows: list[dict[str, str]],
    length_groups: list[dict[str, str]],
    transition_groups: list[dict[str, str]],
    fixture_issue_count: int,
) -> dict[str, str]:
    length_ge50 = [row for row in rows if float(row.get("length_best_ratio", "0") or 0) >= 0.50]
    transition_ge50 = [row for row in rows if float(row.get("transition_best_ratio", "0") or 0) >= 0.50]
    both_ge50 = [
        row
        for row in rows
        if float(row.get("length_best_ratio", "0") or 0) >= 0.50
        and float(row.get("transition_best_ratio", "0") or 0) >= 0.50
    ]
    return {
        "scope": "total",
        "target_rows": str(len(rows)),
        "target_bytes": str(sum_bytes(rows)),
        "length_symbol_count": str(sum(int_value(row, "value_run_count") for row in rows)),
        "length_exact_total": str(sum(int_value(row, "length_best_exact") for row in rows)),
        "length_best_single_exact": str(max((int_value(row, "length_best_exact") for row in rows), default=0)),
        "length_ge50_rows": str(len(length_ge50)),
        "length_ge50_bytes": str(sum_bytes(length_ge50)),
        "transition_symbol_count": str(sum(int_value(row, "transition_count") for row in rows)),
        "transition_exact_total": str(sum(int_value(row, "transition_best_exact") for row in rows)),
        "transition_best_single_exact": str(max((int_value(row, "transition_best_exact") for row in rows), default=0)),
        "transition_ge50_rows": str(len(transition_ge50)),
        "transition_ge50_bytes": str(sum_bytes(transition_ge50)),
        "both_ge50_rows": str(len(both_ge50)),
        "both_ge50_bytes": str(sum_bytes(both_ge50)),
        "length_source_groups": str(len(length_groups)),
        "transition_source_groups": str(len(transition_groups)),
        "issue_rows": str(sum(1 for row in rows if row.get("issues")) + fixture_issue_count),
    }


def build_rows(
    target_rows: list[dict[str, str]],
    operation_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    rows, fixture_issues = build_target_rows(target_rows, operation_rows, fixture_rows)
    length_groups = build_group_rows(rows, "length")
    transition_groups = build_group_rows(rows, "transition")
    summary = build_summary(rows, length_groups, transition_groups, len(fixture_issues))
    return summary, rows, length_groups, transition_groups


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
    length_groups: list[dict[str, str]],
    transition_groups: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "targets": rows,
        "lengthGroups": length_groups,
        "transitionGroups": transition_groups,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("targets.csv", output_dir / "targets.csv"),
            ("by_length_source.csv", output_dir / "by_length_source.csv"),
            ("by_transition_source.csv", output_dir / "by_transition_source.csv"),
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
table {{ width: 100%; border-collapse: collapse; min-width: 1600px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Searches local byte and nibble streams for flat-walk run lengths and value transitions.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Flat walk bytes</div><div class="value">{summary['target_bytes']}</div></div>
    <div class="stat"><div class="label">Length exact</div><div class="value ok">{summary['length_exact_total']}/{summary['length_symbol_count']}</div></div>
    <div class="stat"><div class="label">Transition exact</div><div class="value warn">{summary['transition_exact_total']}/{summary['transition_symbol_count']}</div></div>
    <div class="stat"><div class="label">Both >=50 rows</div><div class="value">{summary['both_ge50_rows']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2><div>{links}</div></section>
  <section class="panel"><h2>Length sources</h2>{render_table(length_groups, GROUP_FIELDNAMES, 80)}</section>
  <section class="panel"><h2>Transition sources</h2>{render_table(transition_groups, GROUP_FIELDNAMES, 80)}</section>
  <section class="panel"><h2>Targets</h2>{render_table(rows, TARGET_FIELDNAMES, 120)}</section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_FLAT_WALK_SOURCE_PROBE = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe local sources for .tex flat-walk run lengths.")
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("--operations", type=Path, default=DEFAULT_OPERATIONS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Tiny Nonzero Gap Flat Walk Source Probe",
    )
    args = parser.parse_args()

    summary, rows, length_groups, transition_groups = build_rows(
        read_csv(args.targets),
        read_csv(args.operations),
        read_csv(args.fixtures),
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, rows)
    write_csv(args.output / "by_length_source.csv", GROUP_FIELDNAMES, length_groups)
    write_csv(args.output / "by_transition_source.csv", GROUP_FIELDNAMES, transition_groups)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, rows, length_groups, transition_groups, args.output, args.title))

    print(f"Flat-walk targets: {summary['target_rows']}")
    print(f"Length exact: {summary['length_exact_total']}/{summary['length_symbol_count']}")
    print(f"Transition exact: {summary['transition_exact_total']}/{summary['transition_symbol_count']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
