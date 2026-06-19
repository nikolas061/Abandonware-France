#!/usr/bin/env python3
"""Summarize reference-guided gaps for exact shared 0x2700302b .tex matches."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import sys
from collections import Counter
from pathlib import Path


DEFAULT_OUTPUT = Path("output/tex_large_shared_2700302b_reference_gap_probe")
DEFAULT_COMPARISONS = Path("output/tex_exact_cdcache_compare/comparisons.csv")
DEFAULT_PARTIAL_RAW = Path("output/tex_partial_raw_decoder/manifest.csv")
DEFAULT_FRONTIERS = Path("output/tex_gap_frontier_report/frontiers.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "reference_rows",
    "partial_rows",
    "native_pixels",
    "covered_pixels",
    "coverage_ratio",
    "raw_runs",
    "raw_bytes",
    "verified_pixels",
    "mismatched_pixels",
    "frontier_rows",
    "internal_frontiers",
    "leading_frontiers",
    "trailing_frontiers",
    "actionable_internal_frontiers",
    "largest_pixel_gap",
    "largest_segment_gap",
    "top_frontier_id",
    "top_frontier_type",
    "top_pcx_name",
    "top_pixel_gap",
    "top_segment_gap_bytes",
    "top_segment_gap_ratio",
    "issue_rows",
    "reference_gap_verdict",
    "next_action",
]

FRONTIER_FIELDNAMES = [
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "frontier_type",
    "gap_start",
    "gap_start_x",
    "gap_start_y",
    "gap_end",
    "gap_end_x",
    "gap_end_y",
    "pixel_gap",
    "left_cluster_id",
    "right_cluster_id",
    "delta_change",
    "segment_gap_start",
    "segment_gap_end",
    "segment_gap_bytes",
    "segment_gap_ratio",
    "segment_relation",
    "actionability",
    "issues",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    csv.field_size_limit(sys.maxsize)
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def int_value(row: dict[str, str], field: str) -> int:
    raw = row.get(field, "")
    if not raw:
        return 0
    return int(raw, 0)


def float_value(row: dict[str, str], field: str) -> float:
    raw = row.get(field, "")
    if not raw:
        return 0.0
    return float(raw)


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    try:
        return os.path.relpath(Path(path_text), base_dir)
    except ValueError:
        return str(path_text)


def reference_keys(comparisons: list[dict[str, str]]) -> set[tuple[str, str]]:
    return {
        (row.get("archive", ""), row.get("pcx_name", ""))
        for row in comparisons
        if row.get("texture_body_first_word", "").lower() == "2700302b"
    }


def actionability(row: dict[str, str]) -> str:
    if row.get("issues"):
        return "issue"
    if row.get("frontier_type") != "internal":
        return "edge_gap"
    if row.get("segment_relation") != "forward":
        return "non_forward"
    if int_value(row, "segment_gap_bytes") <= 0:
        return "missing_segment_window"
    ratio = float_value(row, "segment_gap_ratio")
    if ratio and ratio <= 2.0:
        return "actionable_compact_window"
    return "large_segment_window"


def filtered_frontiers(frontiers: list[dict[str, str]], keys: set[tuple[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in frontiers:
        if (row.get("archive", ""), row.get("pcx_name", "")) not in keys:
            continue
        output = {field: row.get(field, "") for field in FRONTIER_FIELDNAMES if field not in {"actionability"}}
        output["actionability"] = actionability(row)
        rows.append(output)
    rows.sort(
        key=lambda row: (
            0 if row.get("actionability") == "actionable_compact_window" else 1,
            -int_value(row, "pixel_gap"),
            row.get("pcx_name", ""),
            int_value(row, "frontier_id"),
        )
    )
    return rows


def build_summary(
    comparisons: list[dict[str, str]],
    partial_rows: list[dict[str, str]],
    frontier_rows: list[dict[str, str]],
    keys: set[tuple[str, str]],
) -> dict[str, str]:
    reference_rows = [row for row in comparisons if (row.get("archive", ""), row.get("pcx_name", "")) in keys]
    partial = [row for row in partial_rows if (row.get("archive", ""), row.get("pcx_name", "")) in keys]
    type_counts = Counter(row.get("frontier_type", "") for row in frontier_rows)
    actionable = [row for row in frontier_rows if row.get("actionability") == "actionable_compact_window"]
    top = actionable[0] if actionable else (frontier_rows[0] if frontier_rows else {})
    native_pixels = sum(int_value(row, "cdcache_pixels") for row in reference_rows)
    covered_pixels = sum(int_value(row, "covered_pixels") for row in partial)
    coverage_ratio = covered_pixels / native_pixels if native_pixels else 0.0
    issue_rows = sum(1 for row in [*reference_rows, *partial, *frontier_rows] if row.get("issues"))
    if issue_rows:
        verdict = "shared_2700302b_reference_gap_probe_issues"
        next_action = "fix shared 0x2700302b reference gap probe inputs"
    elif actionable:
        verdict = "shared_2700302b_reference_gap_has_actionable_frontier"
        next_action = (
            "probe shared 0x2700302b reference-guided gap frontier "
            f"{top.get('frontier_id', '')} for {top.get('pcx_name', '')}; "
            f"pixel_gap {top.get('pixel_gap', '')} segment_gap {top.get('segment_gap_bytes', '')}"
        )
    else:
        verdict = "shared_2700302b_reference_gap_no_compact_frontier"
        next_action = "broaden shared 0x2700302b reference-guided gap search beyond compact forward windows"
    return {
        "scope": "total",
        "reference_rows": str(len(reference_rows)),
        "partial_rows": str(len(partial)),
        "native_pixels": str(native_pixels),
        "covered_pixels": str(covered_pixels),
        "coverage_ratio": f"{coverage_ratio:.6f}",
        "raw_runs": str(sum(int_value(row, "raw_runs") for row in partial)),
        "raw_bytes": str(sum(int_value(row, "raw_bytes") for row in partial)),
        "verified_pixels": str(sum(int_value(row, "verified_pixels") for row in partial)),
        "mismatched_pixels": str(sum(int_value(row, "mismatched_pixels") for row in partial)),
        "frontier_rows": str(len(frontier_rows)),
        "internal_frontiers": str(type_counts.get("internal", 0)),
        "leading_frontiers": str(type_counts.get("leading", 0)),
        "trailing_frontiers": str(type_counts.get("trailing", 0)),
        "actionable_internal_frontiers": str(len(actionable)),
        "largest_pixel_gap": str(max((int_value(row, "pixel_gap") for row in frontier_rows), default=0)),
        "largest_segment_gap": str(max((int_value(row, "segment_gap_bytes") for row in frontier_rows), default=0)),
        "top_frontier_id": top.get("frontier_id", ""),
        "top_frontier_type": top.get("frontier_type", ""),
        "top_pcx_name": top.get("pcx_name", ""),
        "top_pixel_gap": top.get("pixel_gap", ""),
        "top_segment_gap_bytes": top.get("segment_gap_bytes", ""),
        "top_segment_gap_ratio": top.get("segment_gap_ratio", ""),
        "issue_rows": str(issue_rows),
        "reference_gap_verdict": verdict,
        "next_action": next_action,
    }


def build_html(summary: dict[str, str], frontiers: list[dict[str, str]], output_dir: Path, title: str) -> str:
    payload = {"summary": summary, "frontiers": frontiers}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    rows = "\n".join(
        "<tr>"
        f"<td>{html.escape(row.get('frontier_id', ''))}</td>"
        f"<td>{html.escape(row.get('pcx_name', ''))}</td>"
        f"<td>{html.escape(row.get('frontier_type', ''))}</td>"
        f"<td>{html.escape(row.get('pixel_gap', ''))}</td>"
        f"<td>{html.escape(row.get('segment_gap_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('segment_gap_ratio', ''))}</td>"
        f"<td>{html.escape(row.get('actionability', ''))}</td>"
        "</tr>"
        for row in frontiers[:100]
    )
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (("summary", output_dir / "summary.csv"), ("frontiers", output_dir / "frontiers.csv"))
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body {{ margin: 24px; font-family: system-ui, sans-serif; background: #111; color: #eee; }}
a {{ color: #8ec5ff; margin-right: 12px; }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin: 18px 0; }}
.stat {{ background: #1d1d1d; border: 1px solid #333; padding: 12px; border-radius: 6px; }}
.label {{ color: #aaa; font-size: 12px; text-transform: uppercase; }}
.value {{ font-size: 20px; font-weight: 700; }}
table {{ border-collapse: collapse; width: 100%; background: #181818; }}
th, td {{ border-bottom: 1px solid #333; padding: 7px 9px; text-align: left; font-size: 13px; }}
th {{ color: #ccc; background: #222; }}
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<p>{links}</p>
<div class="stats">
  <div class="stat"><div class="label">References</div><div class="value">{html.escape(summary['reference_rows'])}</div></div>
  <div class="stat"><div class="label">Coverage</div><div class="value">{html.escape(summary['coverage_ratio'])}</div></div>
  <div class="stat"><div class="label">Actionable</div><div class="value">{html.escape(summary['actionable_internal_frontiers'])}</div></div>
  <div class="stat"><div class="label">Verdict</div><div class="value">{html.escape(summary['reference_gap_verdict'])}</div></div>
</div>
<p>{html.escape(summary['next_action'])}</p>
<table>
<thead><tr><th>ID</th><th>PCX</th><th>Type</th><th>Pixel Gap</th><th>Segment Gap</th><th>Ratio</th><th>Actionability</th></tr></thead>
<tbody>{rows}</tbody>
</table>
<script type="application/json" id="data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> tuple[dict[str, str], list[dict[str, str]]]:
    args.output.mkdir(parents=True, exist_ok=True)
    comparisons = read_csv(args.comparisons)
    partial = read_csv(args.partial_raw)
    frontiers = read_csv(args.frontiers)
    keys = reference_keys(comparisons)
    filtered = filtered_frontiers(frontiers, keys)
    summary = build_summary(comparisons, partial, filtered, keys)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "frontiers.csv", FRONTIER_FIELDNAMES, filtered)
    (args.output / "index.html").write_text(build_html(summary, filtered, args.output, args.title), encoding="utf-8")
    return summary, filtered


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe reference-guided gaps for shared 0x2700302b exact matches.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--comparisons", type=Path, default=DEFAULT_COMPARISONS)
    parser.add_argument("--partial-raw", type=Path, default=DEFAULT_PARTIAL_RAW)
    parser.add_argument("--frontiers", type=Path, default=DEFAULT_FRONTIERS)
    parser.add_argument("--title", default="Lands of Lore II .tex Shared 0x2700302b Reference Gap Probe")
    args = parser.parse_args()
    summary, _frontiers = write_report(args)
    print(f"References: {summary['reference_rows']}")
    print(f"Coverage ratio: {summary['coverage_ratio']}")
    print(f"Frontiers: {summary['frontier_rows']}")
    print(f"Actionable internal frontiers: {summary['actionable_internal_frontiers']}")
    print(f"Top frontier: {summary['top_frontier_id']} {summary['top_pcx_name']}")
    print(f"Reference gap verdict: {summary['reference_gap_verdict']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
