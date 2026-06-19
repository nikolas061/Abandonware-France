#!/usr/bin/env python3
"""Measure final source-zero literal replay for shared 0x2700302b."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import sys
from pathlib import Path

import lolg_tex_large_shared_2700302b_reference_fixed_dy1_post_low2_residual_profile_probe as post_low2_profile


DEFAULT_OUTPUT = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_final_orphan_literal_guarded_replay_probe"
)
DEFAULT_TERMINAL_REPLAY_SUMMARY = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_post_horizontal_terminal_guarded_replay_probe/summary.csv"
)
DEFAULT_TERMINAL_SELECTED_PIXELS = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_post_horizontal_terminal_guarded_replay_probe/selected_pixels.csv"
)
DEFAULT_LITERAL_GUARD_SUMMARY = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_final_orphan_literal_guard_probe/summary.csv"
)
DEFAULT_LITERAL_SELECTED_PIXELS = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_final_orphan_literal_guard_probe/selected_pixels.csv"
)
DEFAULT_RESIDUAL_PIXELS = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_residual_profile_probe/residual_pixels.csv"
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
    "final_literal_selected_pixels",
    "final_literal_source_zero_pixels",
    "combined_selected_pixels",
    "combined_covered_pixels",
    "combined_covered_ratio",
    "remaining_nonzero_pixels",
    "remaining_nonzero_ratio",
    "pre_literal_selected_pixel_rows",
    "final_literal_selected_pixel_rows",
    "selected_pixel_rows",
    "overlap_pre_literal_pixels",
    "literal_guard_gap_pixels",
    "accounting_gap_pixels",
    "arithmetic_remaining_nonzero_pixels",
    "residual_remaining_gap_pixels",
    "issue_rows",
    "guarded_literal_replay_verdict",
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
    "final_literal_value_hex",
    "final_literal_source_zero",
    "guard_kind",
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


def source_zero(row: dict[str, str]) -> bool:
    return row.get("dy1_source_value_hex", "").lower() == "00"


def build_selected_rows(
    pre_rows: list[dict[str, str]],
    literal_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in pre_rows:
        rows.append(
            {
                "rank": str(len(rows) + 1),
                "phase": row.get("phase", "pre_literal"),
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
                "terminal_local_dy": row.get("terminal_local_dy", ""),
                "terminal_local_dx": row.get("terminal_local_dx", ""),
                "terminal_local_source_value_hex": row.get("terminal_local_source_value_hex", ""),
                "terminal_local_delta_signed": row.get("terminal_local_delta_signed", ""),
                "final_literal_value_hex": "",
                "final_literal_source_zero": "",
                "guard_kind": "",
                "match_kind": row.get("match_kind", ""),
            }
        )
    for row in literal_rows:
        rows.append(
            {
                "rank": str(len(rows) + 1),
                "phase": "final_source_zero_literal",
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
                "terminal_local_dy": "",
                "terminal_local_dx": "",
                "terminal_local_source_value_hex": "",
                "terminal_local_delta_signed": "",
                "final_literal_value_hex": row.get("literal_value_hex", ""),
                "final_literal_source_zero": row.get("dy1_source_value_hex", ""),
                "guard_kind": row.get("guard_kind", ""),
                "match_kind": row.get("guard_kind", "source_zero_literal"),
            }
        )
    return rows


def build_summary(
    terminal_summary: dict[str, str],
    literal_summary: dict[str, str],
    pre_rows: list[dict[str, str]],
    literal_rows: list[dict[str, str]],
    selected_rows: list[dict[str, str]],
    remaining_rows: list[dict[str, str]],
    issues: list[str],
) -> dict[str, str]:
    target_pixels = int_value(terminal_summary, "target_pixels")
    target_nonzero = int_value(terminal_summary, "target_nonzero_pixels")
    current_covered = int_value(terminal_summary, "combined_covered_pixels")
    current_remaining = int_value(terminal_summary, "remaining_nonzero_pixels")
    literal_selected = int_value(literal_summary, "selected_pixels")
    literal_source_zero = sum(1 for row in literal_rows if source_zero(row))
    literal_gap = literal_selected - len(literal_rows)
    pre_coords = {coord(row) for row in pre_rows}
    literal_coords = {coord(row) for row in literal_rows}
    overlap = len(pre_coords & literal_coords)
    selected_row_count = len(selected_rows)
    arithmetic_remaining = max(0, current_remaining - literal_selected)
    remaining = len(remaining_rows)
    residual_gap = remaining - arithmetic_remaining
    combined_covered = target_pixels - remaining if target_pixels else current_covered + literal_selected
    accounting_gap = selected_row_count - (int_value(terminal_summary, "selected_pixel_rows") + literal_selected)
    literal_value_mismatches = sum(
        1
        for row in literal_rows
        if row.get("literal_value_hex", "").lower() != row.get("target_value_hex", "").lower()
    )
    issue_rows = len(issues)
    for gap in (overlap, literal_gap, accounting_gap, residual_gap, literal_value_mismatches):
        if gap:
            issue_rows += 1

    if issue_rows:
        verdict = "shared_2700302b_reference_fixed_dy1_final_orphan_literal_guarded_replay_issues"
        next_action = "fix shared 0x2700302b final source-zero literal replay inputs"
    elif remaining == 0:
        verdict = "shared_2700302b_reference_fixed_dy1_final_orphan_literal_guarded_replay_complete"
        next_action = "profile final clear residual after source-zero literal replay for shared 0x2700302b"
    else:
        verdict = "shared_2700302b_reference_fixed_dy1_final_orphan_literal_guarded_replay_partial"
        next_action = f"inspect {remaining} residual pixels after final source-zero literal replay"

    return {
        "scope": "total",
        "archive": terminal_summary.get("archive", ""),
        "archive_tag": terminal_summary.get("archive_tag", ""),
        "pcx_name": terminal_summary.get("pcx_name", ""),
        "frontier_id": terminal_summary.get("frontier_id", ""),
        "dy": terminal_summary.get("dy", ""),
        "shift": terminal_summary.get("shift", ""),
        "target_pixels": str(target_pixels),
        "target_zero_pixels": terminal_summary.get("target_zero_pixels", "0"),
        "target_nonzero_pixels": str(target_nonzero),
        "dy1_zero_plus_pixels": terminal_summary.get("dy1_zero_plus_pixels", "0"),
        "fixed_residual_nonzero_pixels": terminal_summary.get("fixed_residual_nonzero_pixels", "0"),
        "initial_low2_aligned_pixels": terminal_summary.get("initial_low2_aligned_pixels", "0"),
        "restart_low2_aligned_pixels": terminal_summary.get("restart_low2_aligned_pixels", "0"),
        "high3_non_low2_aligned_pixels": terminal_summary.get("high3_non_low2_aligned_pixels", "0"),
        "large_delta_aligned_pixels": terminal_summary.get("large_delta_aligned_pixels", "0"),
        "horizontal_selected_pixels": terminal_summary.get("horizontal_selected_pixels", "0"),
        "terminal_selected_pixels": terminal_summary.get("terminal_selected_pixels", "0"),
        "final_literal_selected_pixels": str(literal_selected),
        "final_literal_source_zero_pixels": str(literal_source_zero),
        "combined_selected_pixels": str(selected_row_count),
        "combined_covered_pixels": str(combined_covered),
        "combined_covered_ratio": float_text(combined_covered / target_pixels if target_pixels else 0.0),
        "remaining_nonzero_pixels": str(remaining),
        "remaining_nonzero_ratio": float_text(remaining / target_nonzero if target_nonzero else 0.0),
        "pre_literal_selected_pixel_rows": str(len(pre_rows)),
        "final_literal_selected_pixel_rows": str(len(literal_rows)),
        "selected_pixel_rows": str(selected_row_count),
        "overlap_pre_literal_pixels": str(overlap),
        "literal_guard_gap_pixels": str(literal_gap),
        "accounting_gap_pixels": str(accounting_gap),
        "arithmetic_remaining_nonzero_pixels": str(arithmetic_remaining),
        "residual_remaining_gap_pixels": str(residual_gap),
        "issue_rows": str(issue_rows),
        "guarded_literal_replay_verdict": verdict,
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
    remaining_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "selected": selected_rows, "remaining": remaining_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary", output_dir / "summary.csv"),
            ("selected pixels", output_dir / "selected_pixels.csv"),
            ("remaining pixels", output_dir / "remaining_pixels.csv"),
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
td {{ max-width: 420px; overflow-wrap: anywhere; }}
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<p>{links}</p>
<div class="stats">
  <div class="stat"><div class="label">Covered</div><div class="value">{html.escape(summary['combined_covered_pixels'])}</div></div>
  <div class="stat"><div class="label">Coverage Ratio</div><div class="value">{html.escape(summary['combined_covered_ratio'])}</div></div>
  <div class="stat"><div class="label">Literal</div><div class="value">{html.escape(summary['final_literal_selected_pixels'])}</div></div>
  <div class="stat"><div class="label">Remaining</div><div class="value">{html.escape(summary['remaining_nonzero_pixels'])}</div></div>
</div>
<p>{html.escape(summary['next_action'])}</p>
<h2>Summary</h2>{render_table([summary], SUMMARY_FIELDNAMES)}
<h2>Selected Pixels</h2>{render_table(selected_rows[-24:], SELECTED_FIELDNAMES)}
<h2>Remaining Pixels</h2>{render_table(remaining_rows[:80], post_low2_profile.PIXEL_FIELDNAMES)}
<script type="application/json" id="data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    args.output.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    terminal_summary = read_summary(args.terminal_replay_summary)
    if not terminal_summary:
        issues.append("missing_terminal_replay_summary")
    literal_summary = read_summary(args.literal_guard_summary)
    if not literal_summary:
        issues.append("missing_literal_guard_summary")
    pre_rows = read_csv(args.terminal_selected_pixels)
    if not pre_rows:
        issues.append("missing_terminal_selected_pixels")
    literal_rows = read_csv(args.literal_selected_pixels)
    if not literal_rows:
        issues.append("missing_literal_selected_pixels")
    residual_rows = read_csv(args.residual_pixels)
    if not residual_rows:
        issues.append("missing_residual_pixels")
    selected_rows = build_selected_rows(pre_rows, literal_rows)
    remaining_rows = post_low2_profile.remaining_pixels(residual_rows, selected_rows)
    summary = build_summary(terminal_summary, literal_summary, pre_rows, literal_rows, selected_rows, remaining_rows, issues)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "selected_pixels.csv", SELECTED_FIELDNAMES, selected_rows)
    write_csv(args.output / "remaining_pixels.csv", post_low2_profile.PIXEL_FIELDNAMES, remaining_rows)
    (args.output / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""), encoding="utf-8")
    (args.output / "index.html").write_text(
        build_html(summary, selected_rows, remaining_rows, args.output, args.title),
        encoding="utf-8",
    )
    return summary, selected_rows, remaining_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure final source-zero literal replay.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--terminal-replay-summary", type=Path, default=DEFAULT_TERMINAL_REPLAY_SUMMARY)
    parser.add_argument("--terminal-selected-pixels", type=Path, default=DEFAULT_TERMINAL_SELECTED_PIXELS)
    parser.add_argument("--literal-guard-summary", type=Path, default=DEFAULT_LITERAL_GUARD_SUMMARY)
    parser.add_argument("--literal-selected-pixels", type=Path, default=DEFAULT_LITERAL_SELECTED_PIXELS)
    parser.add_argument("--residual-pixels", type=Path, default=DEFAULT_RESIDUAL_PIXELS)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Shared 0x2700302b Final Orphan Literal Guarded Replay",
    )
    args = parser.parse_args()
    summary, _selected, _remaining = write_report(args)
    print(f"Final literal selected pixels: {summary['final_literal_selected_pixels']}")
    print(f"Combined covered pixels: {summary['combined_covered_pixels']}/{summary['target_pixels']}")
    print(f"Remaining nonzero pixels: {summary['remaining_nonzero_pixels']}")
    print(f"Verdict: {summary['guarded_literal_replay_verdict']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
