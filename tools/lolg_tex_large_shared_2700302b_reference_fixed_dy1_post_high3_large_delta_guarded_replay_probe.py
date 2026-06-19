#!/usr/bin/env python3
"""Measure guarded large-delta replay coverage after high3 for shared 0x2700302b."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import sys
from pathlib import Path


DEFAULT_OUTPUT = Path("output/tex_large_shared_2700302b_reference_fixed_dy1_post_high3_large_delta_guarded_replay_probe")
DEFAULT_GUARDED_HIGH3_SUMMARY = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_post_restart_low2_non_low2_guarded_replay_probe/summary.csv"
)
DEFAULT_GUARDED_HIGH3_SELECTED_PIXELS = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_post_restart_low2_non_low2_guarded_replay_probe/selected_pixels.csv"
)
DEFAULT_LARGE_DELTA_SELECTOR_SUMMARY = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_post_high3_large_delta_selector_probe/summary.csv"
)
DEFAULT_LARGE_DELTA_SELECTED_PIXELS = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_post_high3_large_delta_selector_probe/selected_pixels.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "dy",
    "shift",
    "target_pixels",
    "target_zero_pixels",
    "target_nonzero_pixels",
    "dy1_zero_plus_pixels",
    "fixed_residual_nonzero_pixels",
    "initial_low2_aligned_pixels",
    "restart_low2_aligned_pixels",
    "high3_non_low2_aligned_pixels",
    "large_delta_aligned_pixels",
    "combined_selected_pixels",
    "combined_covered_pixels",
    "combined_covered_ratio",
    "remaining_nonzero_pixels",
    "remaining_nonzero_ratio",
    "high3_selected_pixel_rows",
    "large_delta_selected_pixel_rows",
    "selected_pixel_rows",
    "overlap_high3_large_delta_pixels",
    "large_delta_selector_gap_pixels",
    "accounting_gap_pixels",
    "issue_rows",
    "guarded_large_delta_replay_verdict",
    "next_action",
]

SELECTED_FIELDNAMES = [
    "rank",
    "phase",
    "target_y",
    "target_x",
    "target_value_hex",
    "dy1_source_value_hex",
    "delta_signed",
    "source_index",
    "segment_offset",
    "source_value_hex",
    "token_index",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    csv.field_size_limit(sys.maxsize)
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_summary(path: Path) -> dict[str, str]:
    rows = read_csv(path)
    return rows[0] if rows else {}


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def int_value(row: dict[str, str], field: str) -> int:
    raw = row.get(field, "")
    return int(raw, 0) if raw else 0


def float_text(value: float) -> str:
    return f"{value:.6f}"


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    try:
        return os.path.relpath(Path(path_text), base_dir)
    except ValueError:
        return str(path_text)


def coord(row: dict[str, str]) -> tuple[int, int]:
    return int_value(row, "target_y"), int_value(row, "target_x")


def build_selected_rows(
    high3_rows: list[dict[str, str]],
    large_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in high3_rows:
        rows.append(
            {
                "rank": str(len(rows) + 1),
                "phase": row.get("phase", "pre_large_delta"),
                "target_y": row.get("target_y", ""),
                "target_x": row.get("target_x", ""),
                "target_value_hex": "",
                "dy1_source_value_hex": "",
                "delta_signed": row.get("delta_signed", ""),
                "source_index": row.get("source_index", ""),
                "segment_offset": row.get("segment_offset", ""),
                "source_value_hex": row.get("source_value_hex", ""),
                "token_index": row.get("token_index", ""),
            }
        )
    for row in large_rows:
        rows.append(
            {
                "rank": str(len(rows) + 1),
                "phase": "large_delta",
                "target_y": row.get("target_y", ""),
                "target_x": row.get("target_x", ""),
                "target_value_hex": row.get("target_value_hex", ""),
                "dy1_source_value_hex": row.get("dy1_source_value_hex", ""),
                "delta_signed": row.get("delta_signed", ""),
                "source_index": row.get("source_index", ""),
                "segment_offset": row.get("segment_offset", ""),
                "source_value_hex": row.get("source_value_hex", ""),
                "token_index": row.get("token_index", ""),
            }
        )
    return rows


def build_summary(
    high3_summary: dict[str, str],
    selector_summary: dict[str, str],
    high3_rows: list[dict[str, str]],
    large_rows: list[dict[str, str]],
    issues: list[str],
) -> dict[str, str]:
    target_pixels = int_value(high3_summary, "target_pixels")
    target_nonzero = int_value(high3_summary, "target_nonzero_pixels")
    current_covered = int_value(high3_summary, "combined_covered_pixels")
    current_remaining = int_value(high3_summary, "remaining_nonzero_pixels")
    large_aligned = int_value(selector_summary, "aligned_pixels")
    selector_gap = large_aligned - len(large_rows)
    high3_coords = {coord(row) for row in high3_rows}
    large_coords = {coord(row) for row in large_rows}
    overlap = len(high3_coords & large_coords)
    selected_rows = len(high3_rows) + len(large_rows)
    combined_covered = min(target_pixels, current_covered + large_aligned)
    remaining = max(0, current_remaining - large_aligned)
    accounting_gap = selected_rows - (int_value(high3_summary, "selected_pixel_rows") + large_aligned)
    issue_rows = len(issues)
    if overlap:
        issue_rows += 1
    if selector_gap:
        issue_rows += 1
    if accounting_gap:
        issue_rows += 1

    if issue_rows:
        verdict = "shared_2700302b_reference_fixed_dy1_post_high3_large_delta_guarded_replay_issues"
        next_action = "fix shared 0x2700302b large-delta guarded replay inputs"
    elif combined_covered / target_pixels >= 0.88 if target_pixels else False:
        verdict = "shared_2700302b_reference_fixed_dy1_post_high3_large_delta_guarded_replay_ready"
        next_action = (
            "profile post-large-delta residual producer for shared 0x2700302b frontier "
            f"{high3_summary.get('frontier_id', '')}; {remaining} nonzero pixels remain"
        )
    else:
        verdict = "shared_2700302b_reference_fixed_dy1_post_high3_large_delta_guarded_replay_partial"
        next_action = (
            "seek stronger large-delta replay for shared 0x2700302b; "
            f"{remaining} nonzero pixels remain"
        )

    return {
        "scope": "total",
        "archive": high3_summary.get("archive", ""),
        "archive_tag": high3_summary.get("archive_tag", ""),
        "pcx_name": high3_summary.get("pcx_name", ""),
        "frontier_id": high3_summary.get("frontier_id", ""),
        "dy": high3_summary.get("dy", ""),
        "shift": high3_summary.get("shift", ""),
        "target_pixels": str(target_pixels),
        "target_zero_pixels": high3_summary.get("target_zero_pixels", "0"),
        "target_nonzero_pixels": str(target_nonzero),
        "dy1_zero_plus_pixels": high3_summary.get("dy1_zero_plus_pixels", "0"),
        "fixed_residual_nonzero_pixels": high3_summary.get("fixed_residual_nonzero_pixels", "0"),
        "initial_low2_aligned_pixels": high3_summary.get("initial_low2_aligned_pixels", "0"),
        "restart_low2_aligned_pixels": high3_summary.get("restart_low2_aligned_pixels", "0"),
        "high3_non_low2_aligned_pixels": high3_summary.get("high3_non_low2_aligned_pixels", "0"),
        "large_delta_aligned_pixels": str(large_aligned),
        "combined_selected_pixels": str(selected_rows),
        "combined_covered_pixels": str(combined_covered),
        "combined_covered_ratio": float_text(combined_covered / target_pixels if target_pixels else 0.0),
        "remaining_nonzero_pixels": str(remaining),
        "remaining_nonzero_ratio": float_text(remaining / target_nonzero if target_nonzero else 0.0),
        "high3_selected_pixel_rows": str(len(high3_rows)),
        "large_delta_selected_pixel_rows": str(len(large_rows)),
        "selected_pixel_rows": str(selected_rows),
        "overlap_high3_large_delta_pixels": str(overlap),
        "large_delta_selector_gap_pixels": str(selector_gap),
        "accounting_gap_pixels": str(accounting_gap),
        "issue_rows": str(issue_rows),
        "guarded_large_delta_replay_verdict": verdict,
        "next_action": next_action,
    }


def render_table(rows: list[dict[str, str]], fieldnames: list[str]) -> str:
    if not rows:
        return "<p>No rows.</p>"
    head = "".join(f"<th>{html.escape(field)}</th>" for field in fieldnames)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fieldnames) + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    selected_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "selected": selected_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary", output_dir / "summary.csv"),
            ("selected_pixels", output_dir / "selected_pixels.csv"),
        )
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body {{ margin: 24px; font-family: system-ui, sans-serif; background: #101114; color: #eceff4; }}
a {{ color: #8ec5ff; margin-right: 12px; }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin: 18px 0; }}
.stat {{ background: #1b1d22; border: 1px solid #343842; padding: 12px; border-radius: 6px; }}
.label {{ color: #a9b0bd; font-size: 12px; text-transform: uppercase; }}
.value {{ font-size: 20px; font-weight: 700; }}
table {{ border-collapse: collapse; width: 100%; margin: 18px 0 28px; background: #17191e; }}
th, td {{ border-bottom: 1px solid #343842; padding: 7px 9px; text-align: left; font-size: 12px; vertical-align: top; }}
th {{ color: #cfd6e4; background: #22252c; position: sticky; top: 0; }}
td {{ max-width: 360px; overflow-wrap: anywhere; }}
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<p>{links}</p>
<div class="stats">
  <div class="stat"><div class="label">Combined Covered</div><div class="value">{html.escape(summary['combined_covered_pixels'])}</div></div>
  <div class="stat"><div class="label">Combined Ratio</div><div class="value">{html.escape(summary['combined_covered_ratio'])}</div></div>
  <div class="stat"><div class="label">Large Delta</div><div class="value">{html.escape(summary['large_delta_aligned_pixels'])}</div></div>
  <div class="stat"><div class="label">Remaining NZ</div><div class="value">{html.escape(summary['remaining_nonzero_pixels'])}</div></div>
</div>
<p>{html.escape(summary['next_action'])}</p>
<h2>Summary</h2>{render_table([summary], SUMMARY_FIELDNAMES)}
<h2>Selected Pixels</h2>{render_table(selected_rows[:260], SELECTED_FIELDNAMES)}
<script type="application/json" id="data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> tuple[dict[str, str], list[dict[str, str]]]:
    args.output.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    high3_summary = read_summary(args.guarded_high3_summary)
    selector_summary = read_summary(args.large_delta_selector_summary)
    if not high3_summary:
        issues.append("missing_guarded_high3_summary")
    if not selector_summary:
        issues.append("missing_large_delta_selector_summary")
    high3_rows = read_csv(args.guarded_high3_selected_pixels)
    large_rows = read_csv(args.large_delta_selected_pixels)
    if not high3_rows:
        issues.append("missing_guarded_high3_selected_pixels")
    if not large_rows:
        issues.append("missing_large_delta_selected_pixels")
    selected_rows = build_selected_rows(high3_rows, large_rows)
    summary = build_summary(high3_summary, selector_summary, high3_rows, large_rows, issues)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "selected_pixels.csv", SELECTED_FIELDNAMES, selected_rows)
    (args.output / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""), encoding="utf-8")
    (args.output / "index.html").write_text(build_html(summary, selected_rows, args.output, args.title), encoding="utf-8")
    return summary, selected_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure guarded large-delta replay coverage for shared 0x2700302b.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--guarded-high3-summary", type=Path, default=DEFAULT_GUARDED_HIGH3_SUMMARY)
    parser.add_argument(
        "--guarded-high3-selected-pixels",
        type=Path,
        default=DEFAULT_GUARDED_HIGH3_SELECTED_PIXELS,
    )
    parser.add_argument("--large-delta-selector-summary", type=Path, default=DEFAULT_LARGE_DELTA_SELECTOR_SUMMARY)
    parser.add_argument("--large-delta-selected-pixels", type=Path, default=DEFAULT_LARGE_DELTA_SELECTED_PIXELS)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Shared 0x2700302b Large-Delta Guarded Replay",
    )
    args = parser.parse_args()
    summary, _rows = write_report(args)
    print(f"Combined covered pixels: {summary['combined_covered_pixels']}")
    print(f"Combined covered ratio: {summary['combined_covered_ratio']}")
    print(f"Remaining nonzero pixels: {summary['remaining_nonzero_pixels']}")
    print(f"Verdict: {summary['guarded_large_delta_replay_verdict']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
