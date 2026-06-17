#!/usr/bin/env python3
"""Probe arithmetic formulas behind compressed flat-walk palette deltas."""

from __future__ import annotations

import argparse
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_fill_selector_probe import read_csv
from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_flat_walk_palette_compressed_selector_probe import (
    DEFAULT_OUTPUT as DEFAULT_COMPRESSED_SELECTOR_OUTPUT,
)
from lolg_tex_gap_opcode_probe import int_value, write_csv


DEFAULT_ROWS = DEFAULT_COMPRESSED_SELECTOR_OUTPUT / "rows.csv"
DEFAULT_OUTPUT = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_compressed_formula_probe"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "value_rows",
    "conflicted_value_rows",
    "raw_delta_groups",
    "transform_formula_exact_rows",
    "transform_formula_exact_conflicted_rows",
    "offset_formula_exact_rows",
    "offset_formula_exact_conflicted_rows",
    "pair_formula_exact_rows",
    "pair_formula_exact_conflicted_rows",
    "pair_formula_mismatch_rows",
    "best_raw_delta_group",
    "best_raw_delta_group_rows",
    "promotion_ready_bytes",
    "issue_rows",
]

ROW_FIELDNAMES = [
    "rank",
    "signature_id",
    "value_hex",
    "value_status",
    "source_start",
    "copy_start",
    "source_pool",
    "copy_pool",
    "source_offset",
    "copy_offset",
    "source_raw_hex",
    "copy_raw_hex",
    "raw_delta_signed",
    "actual_transform_delta",
    "derived_transform_delta",
    "transform_formula_exact",
    "actual_offset_delta",
    "derived_offset_delta",
    "offset_formula_exact",
    "actual_delta_pair",
    "derived_delta_pair",
    "pair_formula_exact",
    "issues",
]

GROUP_FIELDNAMES = [
    "raw_delta_signed",
    "rows",
    "values",
    "conflicted_value_rows",
    "actual_transform_deltas",
    "derived_transform_delta",
    "transform_formula_exact_rows",
    "offset_deltas",
    "pair_formula_exact_rows",
    "sample_value_hex",
    "verdict",
]


def hex_to_int(value: str) -> int | None:
    try:
        return int(value, 16) if value else None
    except ValueError:
        return None


def signed_delta(left: int, right: int) -> int:
    return ((right - left + 128) & 0xFF) - 128


def build_rows(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for source in rows:
        issues: list[str] = []
        source_raw = hex_to_int(source.get("source_raw_hex", ""))
        copy_raw = hex_to_int(source.get("copy_raw_hex", ""))
        if source_raw is None:
            issues.append("missing_source_raw")
        if copy_raw is None:
            issues.append("missing_copy_raw")
        raw_delta = signed_delta(source_raw, copy_raw) if source_raw is not None and copy_raw is not None else 0
        derived_transform_delta = -raw_delta
        derived_offset_delta = int_value(source, "copy_offset") - int_value(source, "source_offset")
        derived_delta_pair = f"shift={derived_transform_delta}|offset={derived_offset_delta}"
        actual_transform_delta = int_value(source, "transform_delta")
        actual_offset_delta = int_value(source, "offset_delta")
        actual_delta_pair = source.get("delta_pair", "")
        if str(raw_delta) != source.get("raw_delta_signed", ""):
            issues.append("raw_delta_mismatch")
        output.append(
            {
                "rank": len(output) + 1,
                "signature_id": source.get("signature_id", ""),
                "value_hex": source.get("value_hex", ""),
                "value_status": source.get("value_status", ""),
                "source_start": source.get("source_start", ""),
                "copy_start": source.get("copy_start", ""),
                "source_pool": source.get("source_pool", ""),
                "copy_pool": source.get("copy_pool", ""),
                "source_offset": source.get("source_offset", ""),
                "copy_offset": source.get("copy_offset", ""),
                "source_raw_hex": source.get("source_raw_hex", ""),
                "copy_raw_hex": source.get("copy_raw_hex", ""),
                "raw_delta_signed": raw_delta,
                "actual_transform_delta": actual_transform_delta,
                "derived_transform_delta": derived_transform_delta,
                "transform_formula_exact": int(derived_transform_delta == actual_transform_delta),
                "actual_offset_delta": actual_offset_delta,
                "derived_offset_delta": derived_offset_delta,
                "offset_formula_exact": int(derived_offset_delta == actual_offset_delta),
                "actual_delta_pair": actual_delta_pair,
                "derived_delta_pair": derived_delta_pair,
                "pair_formula_exact": int(derived_delta_pair == actual_delta_pair),
                "issues": ";".join(issues),
            }
        )
    return output


def counter_json(counter: Counter[str]) -> str:
    return json.dumps(dict(sorted(counter.items())), sort_keys=True)


def build_group_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    groups: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        groups[str(row.get("raw_delta_signed", ""))].append(row)

    output: list[dict[str, object]] = []
    for raw_delta, group in groups.items():
        transform_counter = Counter(str(row.get("actual_transform_delta", "")) for row in group)
        offset_counter = Counter(str(row.get("actual_offset_delta", "")) for row in group)
        transform_exact = sum(int_value(row, "transform_formula_exact") for row in group)
        pair_exact = sum(int_value(row, "pair_formula_exact") for row in group)
        derived_transform = str(group[0].get("derived_transform_delta", ""))
        verdict = (
            "raw_delta_transform_formula"
            if transform_exact == len(group)
            else "raw_delta_transform_mismatch"
        )
        output.append(
            {
                "raw_delta_signed": raw_delta,
                "rows": len(group),
                "values": len({row.get("value_hex", "") for row in group}),
                "conflicted_value_rows": sum(
                    1 for row in group if row.get("value_status") == "conflicted_multi_signature_value"
                ),
                "actual_transform_deltas": counter_json(transform_counter),
                "derived_transform_delta": derived_transform,
                "transform_formula_exact_rows": transform_exact,
                "offset_deltas": counter_json(offset_counter),
                "pair_formula_exact_rows": pair_exact,
                "sample_value_hex": group[0].get("value_hex", ""),
                "verdict": verdict,
            }
        )
    output.sort(
        key=lambda row: (
            -int_value(row, "conflicted_value_rows"),
            -int_value(row, "rows"),
            int_value(row, "raw_delta_signed"),
        )
    )
    return output


def build_summary(rows: list[dict[str, object]], group_rows: list[dict[str, object]]) -> dict[str, object]:
    conflicted = [row for row in rows if row.get("value_status") == "conflicted_multi_signature_value"]
    best_group = max(group_rows, key=lambda row: (int_value(row, "conflicted_value_rows"), int_value(row, "rows")))
    pair_mismatch_rows = [row for row in rows if not int_value(row, "pair_formula_exact")]
    return {
        "scope": "total",
        "value_rows": len(rows),
        "conflicted_value_rows": len(conflicted),
        "raw_delta_groups": len(group_rows),
        "transform_formula_exact_rows": sum(int_value(row, "transform_formula_exact") for row in rows),
        "transform_formula_exact_conflicted_rows": sum(
            int_value(row, "transform_formula_exact") for row in conflicted
        ),
        "offset_formula_exact_rows": sum(int_value(row, "offset_formula_exact") for row in rows),
        "offset_formula_exact_conflicted_rows": sum(int_value(row, "offset_formula_exact") for row in conflicted),
        "pair_formula_exact_rows": sum(int_value(row, "pair_formula_exact") for row in rows),
        "pair_formula_exact_conflicted_rows": sum(int_value(row, "pair_formula_exact") for row in conflicted),
        "pair_formula_mismatch_rows": len(pair_mismatch_rows),
        "best_raw_delta_group": best_group.get("raw_delta_signed", ""),
        "best_raw_delta_group_rows": best_group.get("rows", 0),
        "promotion_ready_bytes": 0,
        "issue_rows": sum(1 for row in rows if row.get("issues")),
    }


def render_table(rows: list[dict[str, object]], fields: list[str]) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows
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
  <div class="box"><div class="num">{summary['conflicted_value_rows']}</div><div class="muted">conflicted rows</div></div>
  <div class="box"><div class="num">{summary['raw_delta_groups']}</div><div class="muted">raw-delta groups</div></div>
  <div class="box"><div class="num">{summary['transform_formula_exact_rows']}</div><div class="muted">transform formula exact rows</div></div>
  <div class="box"><div class="num">{summary['pair_formula_exact_rows']}</div><div class="muted">pair formula exact rows</div></div>
  <div class="box"><div class="num">{summary['pair_formula_mismatch_rows']}</div><div class="muted">pair formula mismatches</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Raw-delta groups</h2>{render_table(group_rows, GROUP_FIELDNAMES)}</div>
<div class="panel"><h2>Rows</h2>{render_table(rows, ROW_FIELDNAMES)}</div>
<script type="application/json" id="flat-walk-palette-compressed-formula-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe arithmetic formulas for compressed flat-walk palette deltas.")
    parser.add_argument("--rows", type=Path, default=DEFAULT_ROWS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Flat Walk Palette Compressed Formula Probe",
    )
    args = parser.parse_args()

    rows = build_rows(read_csv(args.rows))
    group_rows = build_group_rows(rows)
    summary = build_summary(rows, group_rows)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "rows.csv", ROW_FIELDNAMES, rows)
    write_csv(args.output / "groups.csv", GROUP_FIELDNAMES, group_rows)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, rows, group_rows, args.title))

    print(f"Conflicted value rows: {summary['conflicted_value_rows']}")
    print(
        f"Transform formula exact: {summary['transform_formula_exact_rows']}/{summary['value_rows']} "
        f"({summary['transform_formula_exact_conflicted_rows']} conflicted)"
    )
    print(
        f"Pair formula exact: {summary['pair_formula_exact_rows']}/{summary['value_rows']} "
        f"({summary['pair_formula_exact_conflicted_rows']} conflicted)"
    )
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
