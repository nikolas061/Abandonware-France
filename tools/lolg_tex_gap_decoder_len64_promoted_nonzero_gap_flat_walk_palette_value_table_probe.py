#!/usr/bin/env python3
"""Probe compact value-to-delta tables for flat-walk palette producers."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path


DEFAULT_VALUES = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_value_split_probe/values.csv"
)
DEFAULT_OUTPUT = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_value_table_probe")

SUMMARY_FIELDNAMES = [
    "scope",
    "value_rows",
    "unique_values",
    "multi_signature_values",
    "stable_transform_multi_values",
    "conflicted_transform_multi_values",
    "stable_offset_multi_values",
    "stable_pair_multi_values",
    "stable_transform_value_rows",
    "conflicted_transform_value_rows",
    "best_value_transform",
    "best_value_transform_rows",
    "promotion_ready_bytes",
    "issue_rows",
]

VALUE_FIELDNAMES = [
    "value_hex",
    "rows",
    "signature_groups",
    "transform_deltas",
    "offset_deltas",
    "delta_pairs",
    "stable_transform_delta",
    "stable_offset_delta",
    "stable_delta_pair",
    "verdict",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def int_value(row: dict[str, object], field: str) -> int:
    raw = row.get(field, "")
    try:
        return int(raw) if raw != "" else 0
    except (TypeError, ValueError):
        return 0


def build_value_table(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    by_value: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_value[row.get("value_hex", "")].append(row)

    table: list[dict[str, object]] = []
    for value_hex, items in sorted(by_value.items()):
        transform_counter = Counter(row.get("transform_delta", "") for row in items)
        offset_counter = Counter(row.get("offset_delta", "") for row in items)
        pair_counter = Counter(row.get("delta_pair", "") for row in items)
        signature_groups = len({row.get("signature_id", "") for row in items})
        stable_transform = len(transform_counter) == 1
        stable_offset = len(offset_counter) == 1
        stable_pair = len(pair_counter) == 1
        if signature_groups > 1 and stable_pair:
            verdict = "stable_multi_signature_pair"
        elif signature_groups > 1 and stable_transform:
            verdict = "stable_multi_signature_transform"
        elif signature_groups > 1:
            verdict = "conflicted_multi_signature_value"
        else:
            verdict = "singleton_value"
        table.append(
            {
                "value_hex": value_hex,
                "rows": len(items),
                "signature_groups": signature_groups,
                "transform_deltas": json.dumps(dict(sorted(transform_counter.items())), sort_keys=True),
                "offset_deltas": json.dumps(dict(sorted(offset_counter.items())), sort_keys=True),
                "delta_pairs": json.dumps(dict(sorted(pair_counter.items())), sort_keys=True),
                "stable_transform_delta": next(iter(transform_counter)) if stable_transform else "",
                "stable_offset_delta": next(iter(offset_counter)) if stable_offset else "",
                "stable_delta_pair": next(iter(pair_counter)) if stable_pair else "",
                "verdict": verdict,
            }
        )
    table.sort(
        key=lambda row: (
            str(row.get("verdict", "")) != "conflicted_multi_signature_value",
            -int_value(row, "signature_groups"),
            str(row.get("value_hex", "")),
        )
    )
    return table


def build_summary(source_rows: list[dict[str, str]], table: list[dict[str, object]]) -> dict[str, object]:
    multi = [row for row in table if int_value(row, "signature_groups") > 1]
    stable_transform_multi = [row for row in multi if row.get("stable_transform_delta")]
    conflicted_transform_multi = [row for row in multi if not row.get("stable_transform_delta")]
    stable_offset_multi = [row for row in multi if row.get("stable_offset_delta")]
    stable_pair_multi = [row for row in multi if row.get("stable_delta_pair")]
    transform_counts = Counter(row.get("stable_transform_delta", "") for row in table if row.get("stable_transform_delta"))
    best_transform, best_transform_rows = transform_counts.most_common(1)[0] if transform_counts else ("", 0)
    return {
        "scope": "total",
        "value_rows": len(source_rows),
        "unique_values": len(table),
        "multi_signature_values": len(multi),
        "stable_transform_multi_values": len(stable_transform_multi),
        "conflicted_transform_multi_values": len(conflicted_transform_multi),
        "stable_offset_multi_values": len(stable_offset_multi),
        "stable_pair_multi_values": len(stable_pair_multi),
        "stable_transform_value_rows": sum(int_value(row, "rows") for row in stable_transform_multi),
        "conflicted_transform_value_rows": sum(int_value(row, "rows") for row in conflicted_transform_multi),
        "best_value_transform": best_transform,
        "best_value_transform_rows": best_transform_rows,
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


def build_html(summary: dict[str, object], table: list[dict[str, object]], title: str) -> str:
    data_json = json.dumps({"summary": summary, "values": table}, indent=2, sort_keys=True)
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body {{ margin: 2rem; background: #101214; color: #edf5f4; font: 14px/1.45 system-ui, sans-serif; }}
table {{ border-collapse: collapse; width: 100%; min-width: 1250px; }}
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
  <div class="box"><div class="num">{summary['multi_signature_values']}</div><div class="muted">multi-signature values</div></div>
  <div class="box"><div class="num">{summary['stable_transform_multi_values']}</div><div class="muted">stable transform values</div></div>
  <div class="box"><div class="num">{summary['conflicted_transform_multi_values']}</div><div class="muted">conflicted transform values</div></div>
  <div class="box"><div class="num">{summary['stable_pair_multi_values']}</div><div class="muted">stable pair values</div></div>
  <div class="box"><div class="num">{summary['best_value_transform']}</div><div class="muted">best value transform</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Value Table</h2>{render_table(table, VALUE_FIELDNAMES)}</div>
<script type="application/json" id="flat-walk-palette-value-table-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe compact value-to-delta tables for flat-walk palettes.")
    parser.add_argument("--values", type=Path, default=DEFAULT_VALUES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Flat Walk Palette Value Table Probe")
    args = parser.parse_args()

    source_rows = read_csv(args.values)
    table = build_value_table(source_rows)
    summary = build_summary(source_rows, table)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "values.csv", VALUE_FIELDNAMES, table)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, table, args.title))

    print(f"Multi-signature values: {summary['multi_signature_values']}")
    print(f"Stable transform multi-values: {summary['stable_transform_multi_values']}")
    print(f"Conflicted transform multi-values: {summary['conflicted_transform_multi_values']}")
    print(f"Stable pair multi-values: {summary['stable_pair_multi_values']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
