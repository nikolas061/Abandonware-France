#!/usr/bin/env python3
"""Probe compressed-stream selectors for conflicted flat-walk palette values."""

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
    read_csv,
)
from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_flat_walk_palette_seed_probe import (
    operation_key,
)
from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_flat_walk_palette_value_split_probe import (
    DEFAULT_OUTPUT as DEFAULT_VALUE_SPLIT_OUTPUT,
)
from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_flat_walk_palette_value_table_probe import (
    DEFAULT_OUTPUT as DEFAULT_VALUE_TABLE_OUTPUT,
)
from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_flat_walk_palette_mix_probe import (
    DEFAULT_OUTPUT as DEFAULT_MIX_OUTPUT,
)
from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_flat_walk_source_probe import (
    source_pools,
    target_op_key,
)
from lolg_tex_gap_opcode_probe import int_value, write_csv


DEFAULT_VALUES = DEFAULT_VALUE_SPLIT_OUTPUT / "values.csv"
DEFAULT_VALUE_TABLE = DEFAULT_VALUE_TABLE_OUTPUT / "values.csv"
DEFAULT_MIX_TARGETS = DEFAULT_MIX_OUTPUT / "targets.csv"
DEFAULT_OUTPUT = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_compressed_selector_probe")

SUMMARY_FIELDNAMES = [
    "scope",
    "value_rows",
    "conflicted_value_rows",
    "conflicted_unique_values",
    "feature_groups",
    "multirow_feature_groups",
    "compressed_feature_groups",
    "multirow_compressed_feature_groups",
    "exact_transform_selector_groups",
    "exact_pair_selector_groups",
    "exact_transform_compressed_groups",
    "exact_pair_compressed_groups",
    "best_transform_selector",
    "best_transform_selector_rows",
    "best_transform_selector_values",
    "best_transform_selector_delta",
    "best_pair_selector",
    "best_pair_selector_rows",
    "best_pair_selector_values",
    "best_pair_selector_delta_pair",
    "promotion_ready_bytes",
    "issue_rows",
]

META_FEATURES = {"value_hex", "value_status"}

ROW_FIELDNAMES = [
    "rank",
    "signature_id",
    "value_hex",
    "value_status",
    "source_pcx_name",
    "source_frontier_id",
    "copy_pcx_name",
    "copy_frontier_id",
    "source_start",
    "copy_start",
    "source_pool",
    "copy_pool",
    "source_offset",
    "copy_offset",
    "source_raw_hex",
    "copy_raw_hex",
    "source_prev_hex",
    "copy_prev_hex",
    "source_next_hex",
    "copy_next_hex",
    "raw_delta_signed",
    "copy_raw_low4",
    "copy_raw_high4",
    "copy_offset_mod4",
    "copy_offset_mod8",
    "copy_offset_mod16",
    "transform_delta",
    "offset_delta",
    "delta_pair",
    "issues",
]

SELECTOR_FIELDNAMES = [
    "feature",
    "key",
    "rows",
    "values",
    "signatures",
    "transform_deltas",
    "delta_pairs",
    "exact_transform_delta",
    "exact_delta_pair",
    "conflicted_value_rows",
    "sample_value_hex",
    "verdict",
]


def read_byte(data: bytes, offset: int) -> int | None:
    if offset < 0 or offset >= len(data):
        return None
    return data[offset]


def hex_byte(value: int | None) -> str:
    return "" if value is None else f"0x{value:02x}"


def signed_delta(left: int | None, right: int | None) -> str:
    if left is None or right is None:
        return ""
    return str(((right - left + 128) & 0xFF) - 128)


def load_value_status(table_rows: list[dict[str, str]]) -> dict[str, str]:
    return {row.get("value_hex", ""): row.get("verdict", "") for row in table_rows}


def target_key(row: dict[str, str]) -> tuple[str, str, str, str]:
    return (
        row.get("archive", ""),
        row.get("pcx_name", ""),
        row.get("frontier_id", ""),
        row.get("start", ""),
    )


def target_by_start(targets: list[dict[str, str]]) -> dict[tuple[str, str, str, str], dict[str, str]]:
    return {target_key(row): row for row in targets}


def targets_by_start(targets: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in targets:
        grouped[row.get("start", "")].append(row)
    return grouped


def resolve_target(
    source: dict[str, str],
    start_field: str,
    keyed_targets: dict[tuple[str, str, str, str], dict[str, str]],
    start_targets: dict[str, list[dict[str, str]]],
    issues: list[str],
) -> dict[str, str]:
    key = (
        source.get("archive", ""),
        source.get("pcx_name", ""),
        source.get("frontier_id", ""),
        source.get(start_field, ""),
    )
    if target := keyed_targets.get(key):
        return target
    matches = start_targets.get(source.get(start_field, ""), [])
    if len(matches) == 1:
        return matches[0]
    issues.append(f"missing_{start_field}_target" if not matches else f"ambiguous_{start_field}_target")
    return {}


def pool_cache(
    mix_targets: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    operation_rows: list[dict[str, str]],
) -> tuple[dict[tuple[str, str, str, str], dict[str, bytes]], list[str]]:
    fixtures = {fixture_key(row): row for row in fixture_rows}
    operations = {operation_key(row): row for row in operation_rows}
    cache: dict[tuple[str, str, str, str], dict[str, bytes]] = {}
    issues: list[str] = []
    for row in mix_targets:
        row_issues: list[str] = []
        fixture = fixtures.get(fixture_key(row), {})
        operation = operations.get(target_op_key(row), {})
        if not fixture:
            row_issues.append("missing_fixture")
        if not operation:
            row_issues.append("missing_operation")
        cache[target_key(row)] = source_pools(row, fixture, operation, row_issues)
        issues.extend(f"{row.get('pcx_name', '')}:{row.get('frontier_id', '')}:{issue}" for issue in row_issues)
    return cache, issues


def build_rows(
    value_rows: list[dict[str, str]],
    value_table_rows: list[dict[str, str]],
    mix_targets: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    operation_rows: list[dict[str, str]],
) -> tuple[list[dict[str, object]], list[str]]:
    statuses = load_value_status(value_table_rows)
    keyed_targets = target_by_start(mix_targets)
    start_targets = targets_by_start(mix_targets)
    pools, issues = pool_cache(mix_targets, fixture_rows, operation_rows)
    rows: list[dict[str, object]] = []
    for source in value_rows:
        row_issues: list[str] = []
        source_target = resolve_target(source, "source_start", keyed_targets, start_targets, row_issues)
        copy_target = resolve_target(source, "copy_start", keyed_targets, start_targets, row_issues)
        source_pools_for_row = pools.get(target_key(source_target), {})
        copy_pools_for_row = pools.get(target_key(copy_target), {})
        source_pool_name = source.get("source_pool", "")
        copy_pool_name = source.get("copy_pool", "")
        source_pool = source_pools_for_row.get(source_pool_name, b"")
        copy_pool = copy_pools_for_row.get(copy_pool_name, b"")
        source_offset = int_value(source, "source_offset")
        copy_offset = int_value(source, "copy_offset")
        source_raw = read_byte(source_pool, source_offset)
        copy_raw = read_byte(copy_pool, copy_offset)
        source_prev = read_byte(source_pool, source_offset - 1)
        copy_prev = read_byte(copy_pool, copy_offset - 1)
        source_next = read_byte(source_pool, source_offset + 1)
        copy_next = read_byte(copy_pool, copy_offset + 1)
        if source_raw is None:
            row_issues.append("missing_source_raw")
        if copy_raw is None:
            row_issues.append("missing_copy_raw")
        rows.append(
            {
                "rank": len(rows) + 1,
                "signature_id": source.get("signature_id", ""),
                "value_hex": source.get("value_hex", ""),
                "value_status": statuses.get(source.get("value_hex", ""), ""),
                "source_pcx_name": source_target.get("pcx_name", ""),
                "source_frontier_id": source_target.get("frontier_id", ""),
                "copy_pcx_name": copy_target.get("pcx_name", ""),
                "copy_frontier_id": copy_target.get("frontier_id", ""),
                "source_start": source.get("source_start", ""),
                "copy_start": source.get("copy_start", ""),
                "source_pool": source_pool_name,
                "copy_pool": copy_pool_name,
                "source_offset": source.get("source_offset", ""),
                "copy_offset": source.get("copy_offset", ""),
                "source_raw_hex": hex_byte(source_raw),
                "copy_raw_hex": hex_byte(copy_raw),
                "source_prev_hex": hex_byte(source_prev),
                "copy_prev_hex": hex_byte(copy_prev),
                "source_next_hex": hex_byte(source_next),
                "copy_next_hex": hex_byte(copy_next),
                "raw_delta_signed": signed_delta(source_raw, copy_raw),
                "copy_raw_low4": "" if copy_raw is None else str(copy_raw & 0x0F),
                "copy_raw_high4": "" if copy_raw is None else str(copy_raw >> 4),
                "copy_offset_mod4": str(copy_offset % 4),
                "copy_offset_mod8": str(copy_offset % 8),
                "copy_offset_mod16": str(copy_offset % 16),
                "transform_delta": source.get("transform_delta", ""),
                "offset_delta": source.get("offset_delta", ""),
                "delta_pair": source.get("delta_pair", ""),
                "issues": ";".join(row_issues),
            }
        )
        issues.extend(row_issues)
    return rows, issues


def feature_values(row: dict[str, object]) -> list[tuple[str, str]]:
    fields = [
        "value_hex",
        "value_status",
        "source_pool",
        "copy_pool",
        "source_raw_hex",
        "copy_raw_hex",
        "source_prev_hex",
        "copy_prev_hex",
        "source_next_hex",
        "copy_next_hex",
        "raw_delta_signed",
        "copy_raw_low4",
        "copy_raw_high4",
        "copy_offset_mod4",
        "copy_offset_mod8",
        "copy_offset_mod16",
    ]
    output = [(field, str(row.get(field, ""))) for field in fields if row.get(field, "") != ""]
    output.extend(
        [
            ("pool_pair", f"{row.get('source_pool', '')}->{row.get('copy_pool', '')}"),
            ("raw_pair", f"{row.get('source_raw_hex', '')}->{row.get('copy_raw_hex', '')}"),
            ("copy_context", f"{row.get('copy_prev_hex', '')}.{row.get('copy_raw_hex', '')}.{row.get('copy_next_hex', '')}"),
            ("source_context", f"{row.get('source_prev_hex', '')}.{row.get('source_raw_hex', '')}.{row.get('source_next_hex', '')}"),
            (
                "copy_raw_offset_mod8",
                f"{row.get('copy_raw_hex', '')}|m8={row.get('copy_offset_mod8', '')}",
            ),
            (
                "copy_raw_offset_mod16",
                f"{row.get('copy_raw_hex', '')}|m16={row.get('copy_offset_mod16', '')}",
            ),
        ]
    )
    return output


def is_compressed_selector(row: dict[str, object]) -> bool:
    return str(row.get("feature", "")) not in META_FEATURES


def build_selector_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    counters: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    values: dict[tuple[str, str], set[str]] = defaultdict(set)
    signatures: dict[tuple[str, str], set[str]] = defaultdict(set)
    transform_deltas: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    delta_pairs: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    samples: dict[tuple[str, str], dict[str, object]] = {}
    for row in rows:
        for feature, key in feature_values(row):
            selector_key = (feature, key)
            counters[selector_key]["rows"] += 1
            if row.get("value_status") == "conflicted_multi_signature_value":
                counters[selector_key]["conflicted"] += 1
            values[selector_key].add(str(row.get("value_hex", "")))
            signatures[selector_key].add(str(row.get("signature_id", "")))
            transform_deltas[selector_key][str(row.get("transform_delta", ""))] += 1
            delta_pairs[selector_key][str(row.get("delta_pair", ""))] += 1
            samples.setdefault(selector_key, row)

    selector_rows: list[dict[str, object]] = []
    for (feature, key), counter in counters.items():
        transform_counter = transform_deltas[(feature, key)]
        pair_counter = delta_pairs[(feature, key)]
        exact_transform = len(transform_counter) == 1
        exact_pair = len(pair_counter) == 1
        sample = samples[(feature, key)]
        verdict = (
            "multirow_exact_pair_selector"
            if counter["rows"] > 1 and exact_pair
            else "multirow_exact_transform_selector"
            if counter["rows"] > 1 and exact_transform
            else "singleton_selector"
            if counter["rows"] == 1
            else "mixed_selector"
        )
        selector_rows.append(
            {
                "feature": feature,
                "key": key,
                "rows": counter["rows"],
                "values": len(values[(feature, key)]),
                "signatures": len(signatures[(feature, key)]),
                "transform_deltas": json.dumps(dict(sorted(transform_counter.items())), sort_keys=True),
                "delta_pairs": json.dumps(dict(sorted(pair_counter.items())), sort_keys=True),
                "exact_transform_delta": next(iter(transform_counter)) if exact_transform else "",
                "exact_delta_pair": next(iter(pair_counter)) if exact_pair else "",
                "conflicted_value_rows": counter["conflicted"],
                "sample_value_hex": sample.get("value_hex", ""),
                "verdict": verdict,
            }
        )
    selector_rows.sort(
        key=lambda row: (
            str(row.get("verdict", "")) != "multirow_exact_pair_selector",
            str(row.get("verdict", "")) != "multirow_exact_transform_selector",
            -int_value(row, "conflicted_value_rows"),
            -int_value(row, "rows"),
            str(row.get("feature", "")),
        )
    )
    return selector_rows


def best_selector(selector_rows: list[dict[str, object]], *, require_pair: bool) -> dict[str, object]:
    field = "exact_delta_pair" if require_pair else "exact_transform_delta"
    return max(
        [
            row
            for row in selector_rows
            if row.get(field) and int_value(row, "rows") > 1 and is_compressed_selector(row)
        ],
        key=lambda row: (
            int_value(row, "conflicted_value_rows"),
            int_value(row, "rows"),
            int_value(row, "values"),
            int_value(row, "signatures"),
        ),
        default={},
    )


def build_summary(
    rows: list[dict[str, object]],
    selector_rows: list[dict[str, object]],
    issues: list[str],
) -> dict[str, object]:
    conflicted_rows = [row for row in rows if row.get("value_status") == "conflicted_multi_signature_value"]
    compressed_selector_rows = [row for row in selector_rows if is_compressed_selector(row)]
    best_transform = best_selector(selector_rows, require_pair=False)
    best_pair = best_selector(selector_rows, require_pair=True)
    return {
        "scope": "total",
        "value_rows": len(rows),
        "conflicted_value_rows": len(conflicted_rows),
        "conflicted_unique_values": len({row.get("value_hex", "") for row in conflicted_rows}),
        "feature_groups": len(selector_rows),
        "multirow_feature_groups": sum(1 for row in selector_rows if int_value(row, "rows") > 1),
        "compressed_feature_groups": len(compressed_selector_rows),
        "multirow_compressed_feature_groups": sum(1 for row in compressed_selector_rows if int_value(row, "rows") > 1),
        "exact_transform_selector_groups": sum(1 for row in selector_rows if row.get("exact_transform_delta")),
        "exact_pair_selector_groups": sum(1 for row in selector_rows if row.get("exact_delta_pair")),
        "exact_transform_compressed_groups": sum(
            1 for row in compressed_selector_rows if int_value(row, "rows") > 1 and row.get("exact_transform_delta")
        ),
        "exact_pair_compressed_groups": sum(
            1 for row in compressed_selector_rows if int_value(row, "rows") > 1 and row.get("exact_delta_pair")
        ),
        "best_transform_selector": (
            f"{best_transform.get('feature', '')}={best_transform.get('key', '')}" if best_transform else ""
        ),
        "best_transform_selector_rows": best_transform.get("rows", 0),
        "best_transform_selector_values": best_transform.get("values", 0),
        "best_transform_selector_delta": best_transform.get("exact_transform_delta", ""),
        "best_pair_selector": f"{best_pair.get('feature', '')}={best_pair.get('key', '')}" if best_pair else "",
        "best_pair_selector_rows": best_pair.get("rows", 0),
        "best_pair_selector_values": best_pair.get("values", 0),
        "best_pair_selector_delta_pair": best_pair.get("exact_delta_pair", ""),
        "promotion_ready_bytes": 0,
        "issue_rows": len(issues) + sum(1 for row in rows if row.get("issues")),
    }


def render_table(rows: list[dict[str, object]], fields: list[str], limit: int = 240) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, object],
    rows: list[dict[str, object]],
    selector_rows: list[dict[str, object]],
    title: str,
) -> str:
    data_json = json.dumps({"summary": summary, "rows": rows, "selectors": selector_rows}, indent=2, sort_keys=True)
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body {{ margin: 2rem; background: #101214; color: #edf5f4; font: 14px/1.45 system-ui, sans-serif; }}
table {{ border-collapse: collapse; width: 100%; min-width: 1500px; }}
th, td {{ border: 1px solid #31424a; padding: .45rem .55rem; vertical-align: top; }}
th {{ color: #9dafb5; background: #172023; text-align: left; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: .75rem; margin: 1rem 0; }}
.box {{ border: 1px solid #31424a; background: #172023; padding: .75rem; }}
.num {{ font-size: 1.35rem; font-weight: 750; }}
.muted {{ color: #9dafb5; }}
.panel {{ overflow-x: auto; margin-top: 1rem; }}
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<div class="grid">
  <div class="box"><div class="num">{summary['conflicted_value_rows']}</div><div class="muted">conflicted value rows</div></div>
  <div class="box"><div class="num">{summary['multirow_feature_groups']}</div><div class="muted">multirow feature groups</div></div>
  <div class="box"><div class="num">{summary['best_transform_selector_rows']}</div><div class="muted">best transform selector rows</div></div>
  <div class="box"><div class="num">{html.escape(str(summary['best_transform_selector_delta']))}</div><div class="muted">best transform delta</div></div>
  <div class="box"><div class="num">{summary['best_pair_selector_rows']}</div><div class="muted">best pair selector rows</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Selectors</h2>{render_table(selector_rows, SELECTOR_FIELDNAMES)}</div>
<div class="panel"><h2>Rows</h2>{render_table(rows, ROW_FIELDNAMES)}</div>
<script type="application/json" id="flat-walk-palette-compressed-selector-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe compressed selectors for conflicted flat-walk palette values.")
    parser.add_argument("--values", type=Path, default=DEFAULT_VALUES)
    parser.add_argument("--value-table", type=Path, default=DEFAULT_VALUE_TABLE)
    parser.add_argument("--mix-targets", type=Path, default=DEFAULT_MIX_TARGETS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--operations", type=Path, default=DEFAULT_OPERATIONS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Flat Walk Palette Compressed Selector Probe",
    )
    args = parser.parse_args()

    rows, issues = build_rows(
        read_csv(args.values),
        read_csv(args.value_table),
        read_csv(args.mix_targets),
        read_csv(args.fixtures),
        read_csv(args.operations),
    )
    selector_rows = build_selector_rows(rows)
    summary = build_summary(rows, selector_rows, issues)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "rows.csv", ROW_FIELDNAMES, rows)
    write_csv(args.output / "selectors.csv", SELECTOR_FIELDNAMES, selector_rows)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, rows, selector_rows, args.title))

    print(f"Conflicted value rows: {summary['conflicted_value_rows']}")
    print(
        f"Best transform selector: {summary['best_transform_selector']} "
        f"{summary['best_transform_selector_rows']} rows -> {summary['best_transform_selector_delta']}"
    )
    print(
        f"Best pair selector: {summary['best_pair_selector']} "
        f"{summary['best_pair_selector_rows']} rows -> {summary['best_pair_selector_delta_pair']}"
    )
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
