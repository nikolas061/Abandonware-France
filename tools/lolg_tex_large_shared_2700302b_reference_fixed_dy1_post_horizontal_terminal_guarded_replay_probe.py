#!/usr/bin/env python3
"""Measure guarded sparse terminal replay after horizontal replay for shared 0x2700302b."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import sys
from pathlib import Path


DEFAULT_OUTPUT = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_post_horizontal_terminal_guarded_replay_probe"
)
DEFAULT_HORIZONTAL_REPLAY_SUMMARY = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_post_large_delta_horizontal_guarded_replay_probe/summary.csv"
)
DEFAULT_HORIZONTAL_SELECTED_PIXELS = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_post_large_delta_horizontal_guarded_replay_probe/selected_pixels.csv"
)
DEFAULT_TERMINAL_GUARD_SUMMARY = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_post_horizontal_terminal_guard_probe/summary.csv"
)
DEFAULT_TERMINAL_SELECTED_PIXELS = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_post_horizontal_terminal_guard_probe/selected_pixels.csv"
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
    "horizontal_selected_pixels",
    "terminal_selected_pixels",
    "terminal_exact_pixels",
    "terminal_small_only_pixels",
    "combined_selected_pixels",
    "combined_covered_pixels",
    "combined_covered_ratio",
    "remaining_nonzero_pixels",
    "remaining_nonzero_ratio",
    "pre_terminal_selected_pixel_rows",
    "terminal_selected_pixel_rows",
    "selected_pixel_rows",
    "overlap_pre_terminal_pixels",
    "terminal_guard_gap_pixels",
    "accounting_gap_pixels",
    "issue_rows",
    "guarded_terminal_replay_verdict",
    "next_action",
]

SELECTED_FIELDNAMES = [
    "rank",
    "phase",
    "target_y",
    "target_x",
    "target_value_hex",
    "dy1_source_value_hex",
    "dy1_delta_signed",
    "source_index",
    "segment_offset",
    "source_value_hex",
    "token_index",
    "same_row_source_y",
    "same_row_source_x",
    "source_shift",
    "same_row_source_value_hex",
    "same_row_delta_signed",
    "terminal_local_dy",
    "terminal_local_dx",
    "terminal_local_source_value_hex",
    "terminal_local_delta_signed",
    "match_kind",
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
    pre_rows: list[dict[str, str]],
    terminal_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in pre_rows:
        rows.append(
            {
                "rank": str(len(rows) + 1),
                "phase": row.get("phase", "pre_terminal"),
                "target_y": row.get("target_y", ""),
                "target_x": row.get("target_x", ""),
                "target_value_hex": row.get("target_value_hex", ""),
                "dy1_source_value_hex": row.get("dy1_source_value_hex", ""),
                "dy1_delta_signed": row.get("dy1_delta_signed", ""),
                "source_index": row.get("source_index", ""),
                "segment_offset": row.get("segment_offset", ""),
                "source_value_hex": row.get("source_value_hex", ""),
                "token_index": row.get("token_index", ""),
                "same_row_source_y": row.get("same_row_source_y", ""),
                "same_row_source_x": row.get("same_row_source_x", ""),
                "source_shift": row.get("source_shift", ""),
                "same_row_source_value_hex": row.get("same_row_source_value_hex", ""),
                "same_row_delta_signed": row.get("same_row_delta_signed", ""),
                "terminal_local_dy": "",
                "terminal_local_dx": "",
                "terminal_local_source_value_hex": "",
                "terminal_local_delta_signed": "",
                "match_kind": row.get("match_kind", ""),
            }
        )
    for row in terminal_rows:
        rows.append(
            {
                "rank": str(len(rows) + 1),
                "phase": "terminal_sparse",
                "target_y": row.get("target_y", ""),
                "target_x": row.get("target_x", ""),
                "target_value_hex": row.get("target_value_hex", ""),
                "dy1_source_value_hex": row.get("dy1_source_value_hex", ""),
                "dy1_delta_signed": row.get("dy1_delta_signed", ""),
                "source_index": "",
                "segment_offset": "",
                "source_value_hex": "",
                "token_index": "",
                "same_row_source_y": "",
                "same_row_source_x": "",
                "source_shift": "",
                "same_row_source_value_hex": "",
                "same_row_delta_signed": "",
                "terminal_local_dy": row.get("local_dy", ""),
                "terminal_local_dx": row.get("local_dx", ""),
                "terminal_local_source_value_hex": row.get("local_source_value_hex", ""),
                "terminal_local_delta_signed": row.get("local_delta_signed", ""),
                "match_kind": row.get("match_kind", ""),
            }
        )
    return rows


def build_summary(
    horizontal_summary: dict[str, str],
    terminal_summary: dict[str, str],
    pre_rows: list[dict[str, str]],
    terminal_rows: list[dict[str, str]],
    issues: list[str],
) -> dict[str, str]:
    target_pixels = int_value(horizontal_summary, "target_pixels")
    target_nonzero = int_value(horizontal_summary, "target_nonzero_pixels")
    current_covered = int_value(horizontal_summary, "combined_covered_pixels")
    current_remaining = int_value(horizontal_summary, "remaining_nonzero_pixels")
    terminal_selected = int_value(terminal_summary, "selected_pixels")
    terminal_gap = terminal_selected - len(terminal_rows)
    pre_coords = {coord(row) for row in pre_rows}
    terminal_coords = {coord(row) for row in terminal_rows}
    overlap = len(pre_coords & terminal_coords)
    selected_rows = len(pre_rows) + len(terminal_rows)
    combined_covered = min(target_pixels, current_covered + terminal_selected)
    remaining = max(0, current_remaining - terminal_selected)
    accounting_gap = selected_rows - (int_value(horizontal_summary, "selected_pixel_rows") + terminal_selected)
    issue_rows = len(issues)
    if overlap:
        issue_rows += 1
    if terminal_gap:
        issue_rows += 1
    if accounting_gap:
        issue_rows += 1

    if issue_rows:
        verdict = "shared_2700302b_reference_fixed_dy1_post_horizontal_terminal_guarded_replay_issues"
        next_action = "fix shared 0x2700302b sparse terminal replay inputs"
    elif remaining <= 1:
        verdict = "shared_2700302b_reference_fixed_dy1_post_horizontal_terminal_guarded_replay_ready"
        next_action = (
            "profile final orphan residual after sparse terminal replay for shared 0x2700302b frontier "
            f"{horizontal_summary.get('frontier_id', '')}; {remaining} nonzero pixel remains"
        )
    else:
        verdict = "shared_2700302b_reference_fixed_dy1_post_horizontal_terminal_guarded_replay_partial"
        next_action = (
            "refine sparse terminal replay for shared 0x2700302b; "
            f"{remaining} nonzero pixels remain"
        )

    return {
        "scope": "total",
        "archive": horizontal_summary.get("archive", ""),
        "archive_tag": horizontal_summary.get("archive_tag", ""),
        "pcx_name": horizontal_summary.get("pcx_name", ""),
        "frontier_id": horizontal_summary.get("frontier_id", ""),
        "dy": horizontal_summary.get("dy", ""),
        "shift": horizontal_summary.get("shift", ""),
        "target_pixels": str(target_pixels),
        "target_zero_pixels": horizontal_summary.get("target_zero_pixels", "0"),
        "target_nonzero_pixels": str(target_nonzero),
        "dy1_zero_plus_pixels": horizontal_summary.get("dy1_zero_plus_pixels", "0"),
        "fixed_residual_nonzero_pixels": horizontal_summary.get("fixed_residual_nonzero_pixels", "0"),
        "initial_low2_aligned_pixels": horizontal_summary.get("initial_low2_aligned_pixels", "0"),
        "restart_low2_aligned_pixels": horizontal_summary.get("restart_low2_aligned_pixels", "0"),
        "high3_non_low2_aligned_pixels": horizontal_summary.get("high3_non_low2_aligned_pixels", "0"),
        "large_delta_aligned_pixels": horizontal_summary.get("large_delta_aligned_pixels", "0"),
        "horizontal_selected_pixels": horizontal_summary.get("horizontal_selected_pixels", "0"),
        "terminal_selected_pixels": str(terminal_selected),
        "terminal_exact_pixels": terminal_summary.get("selected_exact_pixels", "0"),
        "terminal_small_only_pixels": terminal_summary.get("selected_small_only_pixels", "0"),
        "combined_selected_pixels": str(selected_rows),
        "combined_covered_pixels": str(combined_covered),
        "combined_covered_ratio": float_text(combined_covered / target_pixels if target_pixels else 0.0),
        "remaining_nonzero_pixels": str(remaining),
        "remaining_nonzero_ratio": float_text(remaining / target_nonzero if target_nonzero else 0.0),
        "pre_terminal_selected_pixel_rows": str(len(pre_rows)),
        "terminal_selected_pixel_rows": str(len(terminal_rows)),
        "selected_pixel_rows": str(selected_rows),
        "overlap_pre_terminal_pixels": str(overlap),
        "terminal_guard_gap_pixels": str(terminal_gap),
        "accounting_gap_pixels": str(accounting_gap),
        "issue_rows": str(issue_rows),
        "guarded_terminal_replay_verdict": verdict,
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
        for label, path in (("summary", output_dir / "summary.csv"), ("selected pixels", output_dir / "selected_pixels.csv"))
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
td {{ max-width: 420px; overflow-wrap: anywhere; }}
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<p>{links}</p>
<div class="stats">
  <div class="stat"><div class="label">Covered</div><div class="value">{html.escape(summary['combined_covered_pixels'])}</div></div>
  <div class="stat"><div class="label">Coverage Ratio</div><div class="value">{html.escape(summary['combined_covered_ratio'])}</div></div>
  <div class="stat"><div class="label">Terminal</div><div class="value">{html.escape(summary['terminal_selected_pixels'])}</div></div>
  <div class="stat"><div class="label">Remaining</div><div class="value">{html.escape(summary['remaining_nonzero_pixels'])}</div></div>
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
    horizontal_summary = read_summary(args.horizontal_replay_summary)
    if not horizontal_summary:
        issues.append("missing_horizontal_replay_summary")
    terminal_summary = read_summary(args.terminal_guard_summary)
    if not terminal_summary:
        issues.append("missing_terminal_guard_summary")
    pre_rows = read_csv(args.horizontal_selected_pixels)
    if not pre_rows:
        issues.append("missing_horizontal_selected_pixels")
    terminal_rows = read_csv(args.terminal_selected_pixels)
    if not terminal_rows:
        issues.append("missing_terminal_selected_pixels")
    selected_rows = build_selected_rows(pre_rows, terminal_rows)
    summary = build_summary(horizontal_summary, terminal_summary, pre_rows, terminal_rows, issues)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "selected_pixels.csv", SELECTED_FIELDNAMES, selected_rows)
    (args.output / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""), encoding="utf-8")
    (args.output / "index.html").write_text(build_html(summary, selected_rows, args.output, args.title), encoding="utf-8")
    return summary, selected_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure guarded sparse terminal replay after horizontal replay.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--horizontal-replay-summary", type=Path, default=DEFAULT_HORIZONTAL_REPLAY_SUMMARY)
    parser.add_argument("--horizontal-selected-pixels", type=Path, default=DEFAULT_HORIZONTAL_SELECTED_PIXELS)
    parser.add_argument("--terminal-guard-summary", type=Path, default=DEFAULT_TERMINAL_GUARD_SUMMARY)
    parser.add_argument("--terminal-selected-pixels", type=Path, default=DEFAULT_TERMINAL_SELECTED_PIXELS)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Shared 0x2700302b Post-horizontal Terminal Guarded Replay",
    )
    args = parser.parse_args()
    summary, _selected = write_report(args)
    print(f"Terminal selected pixels: {summary['terminal_selected_pixels']}")
    print(f"Combined covered pixels: {summary['combined_covered_pixels']}/{summary['target_pixels']}")
    print(f"Remaining nonzero pixels: {summary['remaining_nonzero_pixels']}")
    print(f"Verdict: {summary['guarded_terminal_replay_verdict']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
