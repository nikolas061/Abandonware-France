#!/usr/bin/env python3
"""Correlate normalized small-palette shapes with fixed control selectors."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_palette_selector_probe import (
    DEFAULT_OPERATIONS,
    safe_bytes_fromhex,
    transform_bytes,
)
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_palette_shape_control_probe")
DEFAULT_SHAPES = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_palette_shape_probe/targets.csv")

FIXED_TRANSFORMS = ("identity", "low7")

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "target_bytes",
    "selector_rows",
    "pure_selector_rows",
    "repeated_pure_selector_rows",
    "repeated_pure_covered_rows",
    "repeated_pure_covered_bytes",
    "best_pure_rows",
    "best_pure_bytes",
    "best_pure_selector",
    "best_repeated_pure_rows",
    "best_repeated_pure_bytes",
    "best_repeated_pure_selector",
    "selector_families",
    "issue_rows",
]

SELECTOR_FIELDNAMES = [
    "shape_kind",
    "selector_family",
    "selector_key",
    "rows",
    "bytes",
    "shape_groups",
    "dominant_shape",
    "dominant_rows",
    "dominant_bytes",
    "purity_rows",
    "purity_bytes",
    "is_pure",
    "is_repeated_pure",
    "sample_pcx",
    "sample_frontier_id",
]

FAMILY_FIELDNAMES = [
    "shape_kind",
    "selector_family",
    "selectors",
    "pure_selectors",
    "repeated_pure_selectors",
    "best_pure_rows",
    "best_pure_bytes",
    "best_selector",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def op_key(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    return (
        row.get("rank", ""),
        row.get("pcx_name", ""),
        row.get("frontier_id", ""),
        row.get("expected_start", ""),
        row.get("expected_end", ""),
    )


def target_op_key(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    return (
        row.get("rank", ""),
        row.get("pcx_name", ""),
        row.get("frontier_id", ""),
        row.get("start", ""),
        row.get("end", ""),
    )


def target_id(row: dict[str, str]) -> str:
    return "|".join(
        (
            row.get("rank", ""),
            row.get("pcx_name", ""),
            row.get("frontier_id", ""),
            row.get("start", ""),
            row.get("end", ""),
        )
    )


def add_selector(
    selectors: list[tuple[str, str]],
    family: str,
    key: str,
) -> None:
    if key and "missing" not in key:
        selectors.append((family, key))


def build_selector_keys(target: dict[str, str], operation: dict[str, str]) -> list[tuple[str, str]]:
    selectors: list[tuple[str, str]] = []
    add_selector(selectors, "palette_size", f"palette_size={target.get('palette_size', '')}")
    add_selector(selectors, "length", f"length={target.get('length', '')}")
    add_selector(selectors, "length_bucket", f"length_bucket={target.get('length_bucket', '')}")
    add_selector(selectors, "start_mod64", f"start_mod64={target.get('start_mod64', '')}")
    add_selector(selectors, "control_ref_mod64", f"control_ref_mod64={target.get('control_ref_mod64', '')}")
    add_selector(
        selectors,
        "palette_length_bucket",
        f"palette_size={target.get('palette_size', '')}|length_bucket={target.get('length_bucket', '')}",
    )
    add_selector(
        selectors,
        "length_start_mod64",
        f"length={target.get('length', '')}|start_mod64={target.get('start_mod64', '')}",
    )

    control_window = safe_bytes_fromhex(operation.get("control_window_hex", ""))
    for transform in FIXED_TRANSFORMS:
        transformed = transform_bytes(control_window, transform)
        for offset, value in enumerate(transformed):
            add_selector(
                selectors,
                "control_byte",
                f"{transform}|offset={offset}|value=0x{value:02x}",
            )
    return selectors


def selector_label(row: dict[str, str]) -> str:
    return f"{row.get('shape_kind')}|{row.get('selector_family')}|{row.get('selector_key')}"


def build_rows(
    shape_rows: list[dict[str, str]],
    operation_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    operations = {op_key(row): row for row in operation_rows}
    counters: dict[tuple[str, str, str], Counter[str]] = defaultdict(Counter)
    shape_counts: dict[tuple[str, str, str], Counter[str]] = defaultdict(Counter)
    shape_bytes: dict[tuple[str, str, str], Counter[str]] = defaultdict(Counter)
    covered_targets: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    covered_bytes: dict[tuple[str, str, str], dict[str, int]] = defaultdict(dict)
    samples: dict[tuple[str, str, str], dict[str, str]] = {}
    issue_rows = 0

    for target in shape_rows:
        operation = operations.get(target_op_key(target), {})
        if not operation:
            issue_rows += 1
            continue
        length = int_value(target, "length")
        selectors = build_selector_keys(target, operation)
        for shape_kind, shape_field in (("first_use_shape", "first_use_shape"), ("run_length_shape", "run_length_shape")):
            shape = target.get(shape_field, "")
            if not shape:
                continue
            for family, selector_key in selectors:
                key = shape_kind, family, selector_key
                counters[key]["rows"] += 1
                counters[key]["bytes"] += length
                shape_counts[key][shape] += 1
                shape_bytes[key][shape] += length
                item_id = target_id(target)
                covered_targets[key].add(item_id)
                covered_bytes[key][item_id] = length
                samples.setdefault(key, target)

    selector_rows = build_selector_rows(counters, shape_counts, shape_bytes, samples)
    family_rows = build_family_rows(selector_rows)
    summary = build_summary(shape_rows, selector_rows, covered_targets, covered_bytes, issue_rows)
    return summary, selector_rows, family_rows


def build_selector_rows(
    counters: dict[tuple[str, str, str], Counter[str]],
    shape_counts: dict[tuple[str, str, str], Counter[str]],
    shape_bytes: dict[tuple[str, str, str], Counter[str]],
    samples: dict[tuple[str, str, str], dict[str, str]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for key, counter in counters.items():
        shape_kind, family, selector_key = key
        rows_total = int(counter["rows"])
        bytes_total = int(counter["bytes"])
        dominant_shape, dominant_rows = shape_counts[key].most_common(1)[0]
        dominant_bytes = shape_bytes[key][dominant_shape]
        shape_group_count = len(shape_counts[key])
        pure = shape_group_count == 1
        sample = samples[key]
        rows.append(
            {
                "shape_kind": shape_kind,
                "selector_family": family,
                "selector_key": selector_key,
                "rows": str(rows_total),
                "bytes": str(bytes_total),
                "shape_groups": str(shape_group_count),
                "dominant_shape": dominant_shape,
                "dominant_rows": str(dominant_rows),
                "dominant_bytes": str(dominant_bytes),
                "purity_rows": f"{(dominant_rows / rows_total) if rows_total else 0.0:.6f}",
                "purity_bytes": f"{(dominant_bytes / bytes_total) if bytes_total else 0.0:.6f}",
                "is_pure": "1" if pure else "0",
                "is_repeated_pure": "1" if pure and rows_total > 1 else "0",
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
            }
        )
    rows.sort(
        key=lambda row: (
            -int_value(row, "is_repeated_pure"),
            -int_value(row, "is_pure"),
            -int_value(row, "rows"),
            -int_value(row, "bytes"),
            row.get("shape_kind", ""),
            row.get("selector_family", ""),
            row.get("selector_key", ""),
        )
    )
    return rows


def build_family_rows(selector_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    by_family: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in selector_rows:
        by_family[row.get("shape_kind", ""), row.get("selector_family", "")].append(row)
    output: list[dict[str, str]] = []
    for key, rows in by_family.items():
        shape_kind, family = key
        pure_rows = [row for row in rows if row.get("is_pure") == "1"]
        repeated_pure = [row for row in rows if row.get("is_repeated_pure") == "1"]
        best = max(pure_rows or rows, key=lambda row: (int_value(row, "rows"), int_value(row, "bytes")))
        output.append(
            {
                "shape_kind": shape_kind,
                "selector_family": family,
                "selectors": str(len(rows)),
                "pure_selectors": str(len(pure_rows)),
                "repeated_pure_selectors": str(len(repeated_pure)),
                "best_pure_rows": best.get("rows", "0") if pure_rows else "0",
                "best_pure_bytes": best.get("bytes", "0") if pure_rows else "0",
                "best_selector": selector_label(best) if pure_rows else "",
            }
        )
    output.sort(
        key=lambda row: (
            -int_value(row, "repeated_pure_selectors"),
            -int_value(row, "pure_selectors"),
            row.get("shape_kind", ""),
            row.get("selector_family", ""),
        )
    )
    return output


def build_summary(
    shape_rows: list[dict[str, str]],
    selector_rows: list[dict[str, str]],
    covered_targets: dict[tuple[str, str, str], set[str]],
    covered_bytes: dict[tuple[str, str, str], dict[str, int]],
    issue_rows: int,
) -> dict[str, str]:
    pure = [row for row in selector_rows if row.get("is_pure") == "1"]
    repeated_pure = [row for row in pure if row.get("is_repeated_pure") == "1"]
    best_pure = max(pure, key=lambda row: (int_value(row, "rows"), int_value(row, "bytes")), default={})
    best_repeated = max(repeated_pure, key=lambda row: (int_value(row, "rows"), int_value(row, "bytes")), default={})
    covered_ids: dict[str, int] = {}
    for row in repeated_pure:
        key = row.get("shape_kind", ""), row.get("selector_family", ""), row.get("selector_key", "")
        for item_id in covered_targets.get(key, set()):
            covered_ids[item_id] = covered_bytes[key].get(item_id, 0)
    return {
        "scope": "total",
        "target_rows": str(len(shape_rows)),
        "target_bytes": str(sum(int_value(row, "length") for row in shape_rows)),
        "selector_rows": str(len(selector_rows)),
        "pure_selector_rows": str(len(pure)),
        "repeated_pure_selector_rows": str(len(repeated_pure)),
        "repeated_pure_covered_rows": str(len(covered_ids)),
        "repeated_pure_covered_bytes": str(sum(covered_ids.values())),
        "best_pure_rows": best_pure.get("rows", "0"),
        "best_pure_bytes": best_pure.get("bytes", "0"),
        "best_pure_selector": selector_label(best_pure) if best_pure else "",
        "best_repeated_pure_rows": best_repeated.get("rows", "0"),
        "best_repeated_pure_bytes": best_repeated.get("bytes", "0"),
        "best_repeated_pure_selector": selector_label(best_repeated) if best_repeated else "",
        "selector_families": str(len({row.get("selector_family", "") for row in selector_rows})),
        "issue_rows": str(issue_rows),
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
    selectors: list[dict[str, str]],
    families: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "selectors": selectors, "families": families}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("selector_candidates.csv", output_dir / "selector_candidates.csv"),
            ("by_selector_family.csv", output_dir / "by_selector_family.csv"),
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
    <div class="sub">Scores whether fixed metadata or control-byte selectors isolate normalized palette shapes.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Targets</div><div class="value">{summary['target_rows']}</div></div>
    <div class="stat"><div class="label">Selectors</div><div class="value">{summary['selector_rows']}</div></div>
    <div class="stat"><div class="label">Pure selectors</div><div class="value ok">{summary['pure_selector_rows']}</div></div>
    <div class="stat"><div class="label">Repeated pure</div><div class="value ok">{summary['repeated_pure_selector_rows']}</div></div>
    <div class="stat"><div class="label">Covered bytes</div><div class="value warn">{summary['repeated_pure_covered_bytes']}</div></div>
    <div class="stat"><div class="label">Best repeated bytes</div><div class="value">{summary['best_repeated_pure_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2><div>{links}</div></section>
  <section class="panel"><h2>Selector families</h2>{render_table(families, FAMILY_FIELDNAMES, 100)}</section>
  <section class="panel"><h2>Selector candidates</h2>{render_table(selectors, SELECTOR_FIELDNAMES, 360)}</section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_PALETTE_SHAPE_CONTROL_PROBE = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Correlate .tex nonzero small-palette shapes with controls.")
    parser.add_argument("--shapes", type=Path, default=DEFAULT_SHAPES)
    parser.add_argument("--operations", type=Path, default=DEFAULT_OPERATIONS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Tiny Nonzero Gap Palette Shape Control Probe",
    )
    args = parser.parse_args()

    summary, selectors, families = build_rows(read_csv(args.shapes), read_csv(args.operations))
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "selector_candidates.csv", SELECTOR_FIELDNAMES, selectors)
    write_csv(args.output / "by_selector_family.csv", FAMILY_FIELDNAMES, families)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, selectors, families, args.output, args.title))

    print(f"Shape targets: {summary['target_rows']}")
    print(f"Selector rows: {summary['selector_rows']}")
    print(f"Repeated pure selectors: {summary['repeated_pure_selector_rows']}")
    print(f"Repeated pure covered bytes: {summary['repeated_pure_covered_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
