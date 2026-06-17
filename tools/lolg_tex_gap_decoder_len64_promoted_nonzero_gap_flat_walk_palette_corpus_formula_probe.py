#!/usr/bin/env python3
"""Validate flat-walk palette shift formulas across every candidate plan row."""

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
    read_csv,
)
from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_flat_walk_palette_mix_probe import (
    DEFAULT_OUTPUT as DEFAULT_MIX_OUTPUT,
)
from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_flat_walk_palette_normalized_context_probe import (
    parse_plan,
)
from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_flat_walk_palette_seed_probe import operation_key
from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_flat_walk_palette_value_table_probe import (
    DEFAULT_OUTPUT as DEFAULT_VALUE_TABLE_OUTPUT,
)
from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_flat_walk_source_probe import (
    source_pools,
    target_op_key,
)
from lolg_tex_gap_opcode_probe import int_value, write_csv


DEFAULT_MIX_TARGETS = DEFAULT_MIX_OUTPUT / "targets.csv"
DEFAULT_VALUE_TABLE = DEFAULT_VALUE_TABLE_OUTPUT / "values.csv"
DEFAULT_OUTPUT = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_corpus_formula_probe"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "candidate_target_rows",
    "value_rows",
    "known_multi_signature_value_rows",
    "known_conflicted_value_rows",
    "candidate_pools",
    "transform_sets",
    "shift_formula_exact_rows",
    "shift_formula_exact_known_multi_rows",
    "shift_formula_exact_conflicted_rows",
    "shift_formula_mismatch_rows",
    "missing_raw_rows",
    "promotion_ready_bytes",
    "issue_rows",
]

ROW_FIELDNAMES = [
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "span_index",
    "op_index",
    "start",
    "end",
    "candidate_pool",
    "transform_count",
    "candidate_transform_set",
    "candidate_kind",
    "value_hex",
    "value_status",
    "source_offset",
    "source_raw_hex",
    "plan_shift",
    "derived_shift",
    "shift_formula_exact",
    "issues",
]

GROUP_FIELDNAMES = [
    "candidate_pool",
    "candidate_transform_set",
    "candidate_kind",
    "target_rows",
    "value_rows",
    "known_multi_signature_value_rows",
    "known_conflicted_value_rows",
    "shift_formula_exact_rows",
    "shift_formula_mismatch_rows",
    "missing_raw_rows",
    "sample_pcx",
    "sample_frontier_id",
    "verdict",
]


def read_byte(data: bytes, offset: int) -> int | None:
    if offset < 0 or offset >= len(data):
        return None
    return data[offset]


def signed_delta(left: int, right: int) -> int:
    return ((right - left + 128) & 0xFF) - 128


def hex_byte(value: int | None) -> str:
    return "" if value is None else f"0x{value:02x}"


def value_statuses(value_table_rows: list[dict[str, str]]) -> dict[str, str]:
    return {row.get("value_hex", ""): row.get("verdict", "") for row in value_table_rows}


def build_rows(
    mix_targets: list[dict[str, str]],
    value_table_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    operation_rows: list[dict[str, str]],
) -> tuple[list[dict[str, object]], list[str]]:
    statuses = value_statuses(value_table_rows)
    fixtures = {fixture_key(row): row for row in fixture_rows}
    operations = {operation_key(row): row for row in operation_rows}
    rows: list[dict[str, object]] = []
    issues: list[str] = []
    for target in mix_targets:
        if not target.get("candidate_plan"):
            continue
        target_issues: list[str] = []
        fixture = fixtures.get(fixture_key(target), {})
        operation = operations.get(target_op_key(target), {})
        if not fixture:
            target_issues.append("missing_fixture")
        if not operation:
            target_issues.append("missing_operation")
        pools = source_pools(target, fixture, operation, target_issues)
        pool_name = target.get("candidate_pool", "")
        pool = pools.get(pool_name, b"")
        for value_hex, (plan_shift, source_offset) in sorted(parse_plan(target.get("candidate_plan", "")).items()):
            value = int(value_hex, 16)
            row_issues = list(target_issues)
            source_raw = read_byte(pool, source_offset)
            if source_raw is None:
                row_issues.append("missing_source_raw")
            derived_shift = signed_delta(source_raw, value) if source_raw is not None else 0
            rows.append(
                {
                    "rank": len(rows) + 1,
                    "archive": target.get("archive", ""),
                    "archive_tag": target.get("archive_tag", ""),
                    "pcx_name": target.get("pcx_name", ""),
                    "frontier_id": target.get("frontier_id", ""),
                    "span_index": target.get("span_index", ""),
                    "op_index": target.get("op_index", ""),
                    "start": target.get("start", ""),
                    "end": target.get("end", ""),
                    "candidate_pool": pool_name,
                    "transform_count": target.get("transform_count", ""),
                    "candidate_transform_set": target.get("candidate_transform_set", ""),
                    "candidate_kind": target.get("candidate_kind", ""),
                    "value_hex": value_hex,
                    "value_status": statuses.get(value_hex, "unknown_value"),
                    "source_offset": source_offset,
                    "source_raw_hex": hex_byte(source_raw),
                    "plan_shift": plan_shift,
                    "derived_shift": derived_shift,
                    "shift_formula_exact": int(source_raw is not None and derived_shift == plan_shift),
                    "issues": ";".join(row_issues),
                }
            )
            issues.extend(row_issues)
    return rows, issues


def status_is_multi(row: dict[str, object]) -> bool:
    return str(row.get("value_status", "")) in {
        "stable_multi_signature_transform",
        "conflicted_multi_signature_value",
    }


def status_is_conflicted(row: dict[str, object]) -> bool:
    return row.get("value_status") == "conflicted_multi_signature_value"


def build_group_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    groups: dict[tuple[str, str, str], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        key = (
            str(row.get("candidate_pool", "")),
            str(row.get("candidate_transform_set", "")),
            str(row.get("candidate_kind", "")),
        )
        groups[key].append(row)

    output: list[dict[str, object]] = []
    for (pool, transform_set, kind), group in groups.items():
        exact_rows = sum(int_value(row, "shift_formula_exact") for row in group)
        mismatch_rows = len(group) - exact_rows
        missing_raw_rows = sum(1 for row in group if "missing_source_raw" in str(row.get("issues", "")))
        verdict = "shift_formula_exact" if mismatch_rows == 0 and missing_raw_rows == 0 else "shift_formula_review"
        output.append(
            {
                "candidate_pool": pool,
                "candidate_transform_set": transform_set,
                "candidate_kind": kind,
                "target_rows": len({str(row.get("start", "")) for row in group}),
                "value_rows": len(group),
                "known_multi_signature_value_rows": sum(1 for row in group if status_is_multi(row)),
                "known_conflicted_value_rows": sum(1 for row in group if status_is_conflicted(row)),
                "shift_formula_exact_rows": exact_rows,
                "shift_formula_mismatch_rows": mismatch_rows,
                "missing_raw_rows": missing_raw_rows,
                "sample_pcx": group[0].get("pcx_name", ""),
                "sample_frontier_id": group[0].get("frontier_id", ""),
                "verdict": verdict,
            }
        )
    output.sort(
        key=lambda row: (
            str(row.get("verdict", "")) != "shift_formula_exact",
            -int_value(row, "value_rows"),
            str(row.get("candidate_pool", "")),
            str(row.get("candidate_transform_set", "")),
        )
    )
    return output


def build_summary(
    mix_targets: list[dict[str, str]],
    rows: list[dict[str, object]],
    group_rows: list[dict[str, object]],
    issues: list[str],
) -> dict[str, object]:
    return {
        "scope": "total",
        "target_rows": len(mix_targets),
        "candidate_target_rows": len({str(row.get("start", "")) for row in rows}),
        "value_rows": len(rows),
        "known_multi_signature_value_rows": sum(1 for row in rows if status_is_multi(row)),
        "known_conflicted_value_rows": sum(1 for row in rows if status_is_conflicted(row)),
        "candidate_pools": len({row.get("candidate_pool", "") for row in rows}),
        "transform_sets": len({row.get("candidate_transform_set", "") for row in rows}),
        "shift_formula_exact_rows": sum(int_value(row, "shift_formula_exact") for row in rows),
        "shift_formula_exact_known_multi_rows": sum(
            int_value(row, "shift_formula_exact") for row in rows if status_is_multi(row)
        ),
        "shift_formula_exact_conflicted_rows": sum(
            int_value(row, "shift_formula_exact") for row in rows if status_is_conflicted(row)
        ),
        "shift_formula_mismatch_rows": sum(1 for row in rows if not int_value(row, "shift_formula_exact")),
        "missing_raw_rows": sum(1 for row in rows if "missing_source_raw" in str(row.get("issues", ""))),
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
    group_rows: list[dict[str, object]],
    title: str,
) -> str:
    data_json = json.dumps({"summary": summary, "rows": rows, "groups": group_rows}, indent=2, sort_keys=True)
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
  <div class="box"><div class="num">{summary['candidate_target_rows']}</div><div class="muted">candidate target rows</div></div>
  <div class="box"><div class="num">{summary['value_rows']}</div><div class="muted">palette value rows</div></div>
  <div class="box"><div class="num">{summary['shift_formula_exact_rows']}</div><div class="muted">shift formula exact rows</div></div>
  <div class="box"><div class="num">{summary['known_conflicted_value_rows']}</div><div class="muted">known conflicted value rows</div></div>
  <div class="box"><div class="num">{summary['shift_formula_mismatch_rows']}</div><div class="muted">shift formula mismatches</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Groups</h2>{render_table(group_rows, GROUP_FIELDNAMES)}</div>
<div class="panel"><h2>Rows</h2>{render_table(rows, ROW_FIELDNAMES)}</div>
<script type="application/json" id="flat-walk-palette-corpus-formula-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate flat-walk palette formula across candidate-plan corpus.")
    parser.add_argument("--mix-targets", type=Path, default=DEFAULT_MIX_TARGETS)
    parser.add_argument("--value-table", type=Path, default=DEFAULT_VALUE_TABLE)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--operations", type=Path, default=DEFAULT_OPERATIONS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Flat Walk Palette Corpus Formula Probe",
    )
    args = parser.parse_args()

    mix_targets = read_csv(args.mix_targets)
    rows, issues = build_rows(
        mix_targets,
        read_csv(args.value_table),
        read_csv(args.fixtures),
        read_csv(args.operations),
    )
    group_rows = build_group_rows(rows)
    summary = build_summary(mix_targets, rows, group_rows, issues)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "rows.csv", ROW_FIELDNAMES, rows)
    write_csv(args.output / "groups.csv", GROUP_FIELDNAMES, group_rows)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, rows, group_rows, args.title))

    print(f"Candidate target rows: {summary['candidate_target_rows']}")
    print(f"Value rows: {summary['value_rows']}")
    print(
        f"Shift formula exact: {summary['shift_formula_exact_rows']}/{summary['value_rows']} "
        f"({summary['shift_formula_exact_conflicted_rows']} known conflicted)"
    )
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
