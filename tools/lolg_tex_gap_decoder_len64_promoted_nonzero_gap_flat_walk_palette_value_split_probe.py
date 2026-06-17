#!/usr/bin/env python3
"""Split repeated flat-walk palette signatures by per-value producer deltas."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_flat_walk_palette_normalized_context_probe import (
    DEFAULT_MIX_TARGETS,
    DEFAULT_SIGNATURES,
    int_value,
    parse_plan,
    read_csv,
    signature_rows,
    write_csv,
)


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_value_split_probe")

SUMMARY_FIELDNAMES = [
    "scope",
    "signature_groups",
    "value_rows",
    "palette_value_count",
    "transform_delta_groups",
    "best_transform_delta",
    "best_transform_delta_values",
    "best_transform_delta_signature_groups",
    "offset_delta_groups",
    "best_offset_delta",
    "best_offset_delta_values",
    "delta_pair_groups",
    "best_delta_pair",
    "best_delta_pair_values",
    "best_delta_pair_signature_groups",
    "promotion_ready_bytes",
    "issue_rows",
]

VALUE_FIELDNAMES = [
    "rank",
    "signature_id",
    "palette_size",
    "value_hex",
    "source_start",
    "copy_start",
    "copy_distance",
    "source_pool",
    "copy_pool",
    "source_shift",
    "copy_shift",
    "transform_delta",
    "source_offset",
    "copy_offset",
    "offset_delta",
    "delta_pair",
    "verdict",
]

DELTA_FIELDNAMES = [
    "group_type",
    "key",
    "values",
    "signature_groups",
    "sample_signature_id",
    "sample_value_hex",
    "verdict",
]


def grouped_targets(mix_targets: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in mix_targets:
        key = row.get("unique_values_hex", "")
        if key:
            groups[key].append(row)
    return groups


def build_value_rows(mix_targets: list[dict[str, str]], signatures: list[dict[str, str]]) -> list[dict[str, object]]:
    targets_by_signature = grouped_targets(mix_targets)
    rows: list[dict[str, object]] = []
    for signature in signature_rows(signatures):
        key = signature.get("unique_values_hex", "")
        candidates = [
            row
            for row in sorted(targets_by_signature.get(key, []), key=lambda item: int_value(item, "start"))
            if row.get("candidate_plan")
        ]
        if len(candidates) < 2:
            continue
        source = next((row for row in candidates if int_value(row, "copy_unlock_rows") > 0), candidates[0])
        copies = [row for row in candidates if row is not source]
        copy = next((row for row in copies if int_value(row, "start") > int_value(source, "start")), copies[0])
        source_plan = parse_plan(source.get("candidate_plan", ""))
        copy_plan = parse_plan(copy.get("candidate_plan", ""))
        for value_hex in sorted(set(source_plan) & set(copy_plan)):
            source_shift, source_offset = source_plan[value_hex]
            copy_shift, copy_offset = copy_plan[value_hex]
            transform_delta = copy_shift - source_shift
            offset_delta = copy_offset - source_offset
            rows.append(
                {
                    "rank": len(rows) + 1,
                    "signature_id": signature.get("signature_id", ""),
                    "palette_size": signature.get("palette_size", ""),
                    "value_hex": value_hex,
                    "source_start": source.get("start", ""),
                    "copy_start": copy.get("start", ""),
                    "copy_distance": int_value(copy, "start") - int_value(source, "start"),
                    "source_pool": source.get("candidate_pool", ""),
                    "copy_pool": copy.get("candidate_pool", ""),
                    "source_shift": source_shift,
                    "copy_shift": copy_shift,
                    "transform_delta": transform_delta,
                    "source_offset": source_offset,
                    "copy_offset": copy_offset,
                    "offset_delta": offset_delta,
                    "delta_pair": f"shift={transform_delta}|offset={offset_delta}",
                    "verdict": "value_delta_review",
                }
            )
    return rows


def build_delta_rows(value_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    counters: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    signatures: dict[tuple[str, str], set[str]] = defaultdict(set)
    samples: dict[tuple[str, str], dict[str, object]] = {}
    for row in value_rows:
        keys = [
            ("transform_delta", str(row.get("transform_delta", ""))),
            ("offset_delta", str(row.get("offset_delta", ""))),
            ("delta_pair", str(row.get("delta_pair", ""))),
        ]
        for group_type, key in keys:
            counter_key = (group_type, key)
            counters[counter_key]["values"] += 1
            signatures[counter_key].add(str(row.get("signature_id", "")))
            samples.setdefault(counter_key, row)

    rows: list[dict[str, object]] = []
    for (group_type, key), counter in counters.items():
        sample = samples[(group_type, key)]
        values = int(counter["values"])
        signature_count = len(signatures[(group_type, key)])
        verdict = (
            "multi_signature_value_delta_review"
            if signature_count > 1 and values >= 2
            else "single_signature_value_delta_review"
        )
        rows.append(
            {
                "group_type": group_type,
                "key": key,
                "values": values,
                "signature_groups": signature_count,
                "sample_signature_id": sample.get("signature_id", ""),
                "sample_value_hex": sample.get("value_hex", ""),
                "verdict": verdict,
            }
        )
    rows.sort(
        key=lambda row: (
            str(row.get("group_type", "")) != "transform_delta",
            -int_value(row, "values"),
            -int_value(row, "signature_groups"),
            str(row.get("key", "")),
        )
    )
    return rows


def best_group(delta_rows: list[dict[str, object]], group_type: str) -> dict[str, object]:
    rows = [row for row in delta_rows if row.get("group_type") == group_type]
    return max(
        rows,
        key=lambda row: (int_value(row, "values"), int_value(row, "signature_groups")),
        default={},
    )


def build_summary(value_rows: list[dict[str, object]], delta_rows: list[dict[str, object]]) -> dict[str, object]:
    best_transform = best_group(delta_rows, "transform_delta")
    best_offset = best_group(delta_rows, "offset_delta")
    best_pair = best_group(delta_rows, "delta_pair")
    signatures = {str(row.get("signature_id", "")) for row in value_rows}
    return {
        "scope": "total",
        "signature_groups": len(signatures),
        "value_rows": len(value_rows),
        "palette_value_count": len(value_rows),
        "transform_delta_groups": sum(1 for row in delta_rows if row.get("group_type") == "transform_delta"),
        "best_transform_delta": best_transform.get("key", ""),
        "best_transform_delta_values": best_transform.get("values", 0),
        "best_transform_delta_signature_groups": best_transform.get("signature_groups", 0),
        "offset_delta_groups": sum(1 for row in delta_rows if row.get("group_type") == "offset_delta"),
        "best_offset_delta": best_offset.get("key", ""),
        "best_offset_delta_values": best_offset.get("values", 0),
        "delta_pair_groups": sum(1 for row in delta_rows if row.get("group_type") == "delta_pair"),
        "best_delta_pair": best_pair.get("key", ""),
        "best_delta_pair_values": best_pair.get("values", 0),
        "best_delta_pair_signature_groups": best_pair.get("signature_groups", 0),
        "promotion_ready_bytes": 0,
        "issue_rows": 0,
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
    value_rows: list[dict[str, object]],
    delta_rows: list[dict[str, object]],
    title: str,
) -> str:
    data_json = json.dumps({"summary": summary, "values": value_rows, "deltas": delta_rows}, indent=2, sort_keys=True)
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body {{ margin: 2rem; background: #101214; color: #edf5f4; font: 14px/1.45 system-ui, sans-serif; }}
table {{ border-collapse: collapse; width: 100%; min-width: 1350px; }}
th, td {{ border: 1px solid #31424a; padding: .45rem .55rem; vertical-align: top; }}
th {{ color: #9dafb5; background: #172023; text-align: left; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: .75rem; margin: 1rem 0; }}
.box {{ border: 1px solid #31424a; background: #172023; padding: .75rem; }}
.num {{ font-size: 1.35rem; font-weight: 750; }}
.muted {{ color: #9dafb5; }}
.panel {{ overflow-x: auto; margin-top: 1rem; }}
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<div class="grid">
  <div class="box"><div class="num">{summary['signature_groups']}</div><div class="muted">signature groups</div></div>
  <div class="box"><div class="num">{summary['value_rows']}</div><div class="muted">palette value rows</div></div>
  <div class="box"><div class="num">{html.escape(str(summary['best_transform_delta']))}</div><div class="muted">best transform delta</div></div>
  <div class="box"><div class="num">{summary['best_transform_delta_values']}</div><div class="muted">best transform values</div></div>
  <div class="box"><div class="num">{summary['best_delta_pair_values']}</div><div class="muted">best pair values</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Deltas</h2>{render_table(delta_rows, DELTA_FIELDNAMES)}</div>
<div class="panel"><h2>Values</h2>{render_table(value_rows, VALUE_FIELDNAMES)}</div>
<script type="application/json" id="flat-walk-palette-value-split-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Split repeated flat-walk palette signatures by value deltas.")
    parser.add_argument("--mix-targets", type=Path, default=DEFAULT_MIX_TARGETS)
    parser.add_argument("--signatures", type=Path, default=DEFAULT_SIGNATURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Flat Walk Palette Value Split Probe",
    )
    args = parser.parse_args()

    value_rows = build_value_rows(read_csv(args.mix_targets), read_csv(args.signatures))
    delta_rows = build_delta_rows(value_rows)
    summary = build_summary(value_rows, delta_rows)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "values.csv", VALUE_FIELDNAMES, value_rows)
    write_csv(args.output / "by_delta.csv", DELTA_FIELDNAMES, delta_rows)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, value_rows, delta_rows, args.title))

    print(f"Palette value rows: {summary['value_rows']}")
    print(
        f"Best transform delta: {summary['best_transform_delta']} "
        f"{summary['best_transform_delta_values']} values"
    )
    print(f"Best delta pair: {summary['best_delta_pair']} {summary['best_delta_pair_values']} values")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
