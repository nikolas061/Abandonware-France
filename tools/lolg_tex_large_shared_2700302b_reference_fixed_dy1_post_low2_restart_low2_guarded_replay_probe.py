#!/usr/bin/env python3
"""Measure guarded restart-low2 replay coverage for shared 0x2700302b."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import sys
from pathlib import Path


DEFAULT_OUTPUT = Path("output/tex_large_shared_2700302b_reference_fixed_dy1_post_low2_restart_low2_guarded_replay_probe")
DEFAULT_LOW2_GUARDED_SUMMARY = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_low2_guarded_replay_probe/summary.csv"
)
DEFAULT_LOW2_SELECTED_PIXELS = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_low2_guarded_replay_probe/selected_pixels.csv"
)
DEFAULT_RESTART_SELECTOR_SUMMARY = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_post_low2_restart_low2_selector_probe/summary.csv"
)
DEFAULT_RESTART_SELECTED_PIXELS = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_post_low2_restart_low2_selector_probe/selected_pixels.csv"
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
    "combined_low2_aligned_pixels",
    "combined_covered_pixels",
    "combined_covered_ratio",
    "remaining_nonzero_pixels",
    "remaining_nonzero_ratio",
    "initial_selected_pixel_rows",
    "restart_selected_pixel_rows",
    "selected_pixel_rows",
    "overlap_initial_restart_pixels",
    "restart_selector_gap_pixels",
    "accounting_gap_pixels",
    "issue_rows",
    "guarded_restart_replay_verdict",
    "next_action",
]

SELECTED_FIELDNAMES = [
    "rank",
    "phase",
    "target_y",
    "target_x",
    "delta_signed",
    "source_index",
    "segment_offset",
    "source_value_signed",
    "token_index",
    "previous_low2_source_reused",
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
    initial_rows: list[dict[str, str]],
    restart_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for phase, source_rows in (("initial_low2", initial_rows), ("restart_low2", restart_rows)):
        for row in source_rows:
            rows.append(
                {
                    "rank": str(len(rows) + 1),
                    "phase": phase,
                    "target_y": row.get("target_y", ""),
                    "target_x": row.get("target_x", ""),
                    "delta_signed": row.get("delta_signed", ""),
                    "source_index": row.get("source_index", ""),
                    "segment_offset": row.get("segment_offset", ""),
                    "source_value_signed": row.get("source_value_signed", ""),
                    "token_index": row.get("token_index", ""),
                    "previous_low2_source_reused": row.get("previous_low2_source_reused", "0"),
                }
            )
    return rows


def build_summary(
    low2_summary: dict[str, str],
    restart_summary: dict[str, str],
    initial_rows: list[dict[str, str]],
    restart_rows: list[dict[str, str]],
    issues: list[str],
) -> dict[str, str]:
    target_pixels = int_value(low2_summary, "target_pixels")
    target_nonzero = int_value(low2_summary, "target_nonzero_pixels")
    current_covered = int_value(low2_summary, "combined_covered_pixels")
    current_remaining = int_value(low2_summary, "remaining_nonzero_pixels")
    initial_aligned = int_value(low2_summary, "low2_aligned_pixels")
    restart_aligned = int_value(restart_summary, "restart_aligned_pixels")
    restart_selector_gap = restart_aligned - len(restart_rows)
    initial_coords = {coord(row) for row in initial_rows}
    restart_coords = {coord(row) for row in restart_rows}
    overlap = len(initial_coords & restart_coords)
    combined_low2 = initial_aligned + restart_aligned
    combined_covered = min(target_pixels, current_covered + restart_aligned)
    remaining = max(0, current_remaining - restart_aligned)
    selected_rows = len(initial_rows) + len(restart_rows)
    accounting_gap = selected_rows - combined_low2
    issue_rows = len(issues)
    if overlap:
        issue_rows += 1
    if restart_selector_gap:
        issue_rows += 1
    if accounting_gap:
        issue_rows += 1

    if issue_rows:
        verdict = "shared_2700302b_reference_fixed_dy1_post_low2_restart_low2_guarded_replay_issues"
        next_action = "fix shared 0x2700302b restart low2 guarded replay inputs"
    elif combined_covered / target_pixels >= 0.77 if target_pixels else False:
        verdict = "shared_2700302b_reference_fixed_dy1_post_low2_restart_low2_guarded_replay_ready"
        next_action = (
            "profile post-restart-low2 residual producer for shared 0x2700302b frontier "
            f"{low2_summary.get('frontier_id', '')}; {remaining} nonzero pixels remain"
        )
    else:
        verdict = "shared_2700302b_reference_fixed_dy1_post_low2_restart_low2_guarded_replay_partial"
        next_action = (
            "seek stronger restart low2 replay for shared 0x2700302b; "
            f"{remaining} nonzero pixels remain"
        )

    return {
        "scope": "total",
        "archive": low2_summary.get("archive", ""),
        "archive_tag": low2_summary.get("archive_tag", ""),
        "pcx_name": low2_summary.get("pcx_name", ""),
        "frontier_id": low2_summary.get("frontier_id", ""),
        "dy": low2_summary.get("dy", ""),
        "shift": low2_summary.get("shift", ""),
        "target_pixels": str(target_pixels),
        "target_zero_pixels": low2_summary.get("target_zero_pixels", "0"),
        "target_nonzero_pixels": str(target_nonzero),
        "dy1_zero_plus_pixels": low2_summary.get("dy1_zero_plus_pixels", "0"),
        "fixed_residual_nonzero_pixels": low2_summary.get("fixed_residual_nonzero_pixels", "0"),
        "initial_low2_aligned_pixels": str(initial_aligned),
        "restart_low2_aligned_pixels": str(restart_aligned),
        "combined_low2_aligned_pixels": str(combined_low2),
        "combined_covered_pixels": str(combined_covered),
        "combined_covered_ratio": float_text(combined_covered / target_pixels if target_pixels else 0.0),
        "remaining_nonzero_pixels": str(remaining),
        "remaining_nonzero_ratio": float_text(remaining / target_nonzero if target_nonzero else 0.0),
        "initial_selected_pixel_rows": str(len(initial_rows)),
        "restart_selected_pixel_rows": str(len(restart_rows)),
        "selected_pixel_rows": str(selected_rows),
        "overlap_initial_restart_pixels": str(overlap),
        "restart_selector_gap_pixels": str(restart_selector_gap),
        "accounting_gap_pixels": str(accounting_gap),
        "issue_rows": str(issue_rows),
        "guarded_restart_replay_verdict": verdict,
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
  <div class="stat"><div class="label">Restart Low2</div><div class="value">{html.escape(summary['restart_low2_aligned_pixels'])}</div></div>
  <div class="stat"><div class="label">Remaining NZ</div><div class="value">{html.escape(summary['remaining_nonzero_pixels'])}</div></div>
</div>
<p>{html.escape(summary['next_action'])}</p>
<h2>Summary</h2>{render_table([summary], SUMMARY_FIELDNAMES)}
<h2>Selected Pixels</h2>{render_table(selected_rows[:220], SELECTED_FIELDNAMES)}
<script type="application/json" id="data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> tuple[dict[str, str], list[dict[str, str]]]:
    args.output.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    low2_summary = read_summary(args.low2_guarded_summary)
    restart_summary = read_summary(args.restart_selector_summary)
    if not low2_summary:
        issues.append("missing_low2_guarded_summary")
    if not restart_summary:
        issues.append("missing_restart_selector_summary")
    initial_rows = read_csv(args.low2_selected_pixels)
    restart_rows = read_csv(args.restart_selected_pixels)
    if not initial_rows:
        issues.append("missing_low2_selected_pixels")
    if not restart_rows:
        issues.append("missing_restart_selected_pixels")
    selected_rows = build_selected_rows(initial_rows, restart_rows)
    summary = build_summary(low2_summary, restart_summary, initial_rows, restart_rows, issues)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "selected_pixels.csv", SELECTED_FIELDNAMES, selected_rows)
    (args.output / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""), encoding="utf-8")
    (args.output / "index.html").write_text(build_html(summary, selected_rows, args.output, args.title), encoding="utf-8")
    return summary, selected_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure guarded restart-low2 replay coverage for shared 0x2700302b.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--low2-guarded-summary", type=Path, default=DEFAULT_LOW2_GUARDED_SUMMARY)
    parser.add_argument("--low2-selected-pixels", type=Path, default=DEFAULT_LOW2_SELECTED_PIXELS)
    parser.add_argument("--restart-selector-summary", type=Path, default=DEFAULT_RESTART_SELECTOR_SUMMARY)
    parser.add_argument("--restart-selected-pixels", type=Path, default=DEFAULT_RESTART_SELECTED_PIXELS)
    parser.add_argument("--title", default="Lands of Lore II .tex Shared 0x2700302b Restart Low2 Guarded Replay")
    args = parser.parse_args()
    summary, _rows = write_report(args)
    print(f"Combined covered pixels: {summary['combined_covered_pixels']}")
    print(f"Combined covered ratio: {summary['combined_covered_ratio']}")
    print(f"Remaining nonzero pixels: {summary['remaining_nonzero_pixels']}")
    print(f"Verdict: {summary['guarded_restart_replay_verdict']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
