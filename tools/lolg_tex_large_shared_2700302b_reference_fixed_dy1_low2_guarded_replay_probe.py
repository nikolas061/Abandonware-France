#!/usr/bin/env python3
"""Measure guarded low2 replay coverage after fixed-dy1 replay for shared 0x2700302b."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import sys
from pathlib import Path


DEFAULT_OUTPUT = Path("output/tex_large_shared_2700302b_reference_fixed_dy1_low2_guarded_replay_probe")
DEFAULT_FIXED_REPLAY_SUMMARY = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_replay_probe/summary.csv"
)
DEFAULT_SMALL_DELTA_GRAMMAR_SUMMARY = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_small_delta_grammar_probe/summary.csv"
)
DEFAULT_LOW2_SELECTOR_SUMMARY = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_small_delta_low2_selector_probe/summary.csv"
)
DEFAULT_LOW2_ALIGNMENTS = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_small_delta_low2_selector_probe/alignments.csv"
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
    "dy1_nonzero_pixels",
    "dy1_zero_plus_pixels",
    "fixed_residual_nonzero_pixels",
    "small_delta_pixels",
    "large_delta_pixels",
    "low2_aligned_pixels",
    "low2_aligned_ratio",
    "low2_source_used_ratio",
    "low2_full_token_rows",
    "low2_partial_token_rows",
    "low2_uncovered_small_delta_pixels",
    "combined_covered_pixels",
    "combined_covered_ratio",
    "remaining_nonzero_pixels",
    "remaining_nonzero_ratio",
    "accounting_gap_pixels",
    "selected_pixel_rows",
    "issue_rows",
    "guarded_replay_verdict",
    "next_action",
]

SELECTED_FIELDNAMES = [
    "rank",
    "target_y",
    "target_x",
    "delta_signed",
    "source_index",
    "segment_offset",
    "source_value_signed",
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


def build_selected_rows(alignment_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for rank, row in enumerate(alignment_rows, 1):
        rows.append(
            {
                "rank": str(rank),
                "target_y": row.get("target_y", ""),
                "target_x": row.get("target_x", ""),
                "delta_signed": row.get("delta_signed", ""),
                "source_index": row.get("source_index", ""),
                "segment_offset": row.get("segment_offset", ""),
                "source_value_signed": row.get("source_value_signed", ""),
                "token_index": row.get("token_index", ""),
            }
        )
    return rows


def build_summary(
    fixed_summary: dict[str, str],
    grammar_summary: dict[str, str],
    selector_summary: dict[str, str],
    selected_rows: list[dict[str, str]],
    issues: list[str],
) -> dict[str, str]:
    target_pixels = int_value(fixed_summary, "target_pixels")
    target_zero = int_value(fixed_summary, "target_zero_pixels")
    target_nonzero = int_value(fixed_summary, "target_nonzero_pixels")
    dy1_nonzero = int_value(fixed_summary, "raw_copy_nonzero_matches")
    dy1_zero_plus = int_value(fixed_summary, "zero_plus_dy1_matches")
    fixed_residual = int_value(fixed_summary, "residual_nonzero_pixels")
    small_delta = int_value(grammar_summary, "small_delta_pixels")
    large_delta = int_value(grammar_summary, "large_delta_pixels")
    low2_aligned = int_value(selector_summary, "aligned_pixels")
    selected_pixels = len(selected_rows)
    combined = min(target_pixels, dy1_zero_plus + low2_aligned)
    remaining_nonzero = max(0, fixed_residual - low2_aligned)
    accounting_gap = (small_delta + large_delta) - fixed_residual
    issue_rows = len(issues)
    if selected_pixels != low2_aligned:
        issue_rows += 1

    if issue_rows:
        verdict = "shared_2700302b_reference_fixed_dy1_low2_guarded_replay_issues"
        next_action = "fix shared 0x2700302b guarded low2 replay inputs"
    elif accounting_gap != 0:
        verdict = "shared_2700302b_reference_fixed_dy1_low2_guarded_replay_accounting_mismatch"
        next_action = "align shared 0x2700302b guarded low2 replay accounting"
    elif combined / target_pixels >= 0.70 if target_pixels else False:
        verdict = "shared_2700302b_reference_fixed_dy1_low2_guarded_replay_partial_ready"
        next_action = (
            "profile post-low2 residual producer for shared 0x2700302b frontier "
            f"{fixed_summary.get('frontier_id', '')}; {remaining_nonzero} nonzero pixels remain"
        )
    else:
        verdict = "shared_2700302b_reference_fixed_dy1_low2_guarded_replay_weak"
        next_action = (
            "seek stronger selector before low2 replay promotion for shared 0x2700302b frontier "
            f"{fixed_summary.get('frontier_id', '')}"
        )

    return {
        "scope": "total",
        "archive": fixed_summary.get("archive", ""),
        "archive_tag": fixed_summary.get("archive_tag", ""),
        "pcx_name": fixed_summary.get("pcx_name", ""),
        "frontier_id": fixed_summary.get("frontier_id", ""),
        "dy": fixed_summary.get("dy", ""),
        "shift": fixed_summary.get("shift", ""),
        "target_pixels": str(target_pixels),
        "target_zero_pixels": str(target_zero),
        "target_nonzero_pixels": str(target_nonzero),
        "dy1_nonzero_pixels": str(dy1_nonzero),
        "dy1_zero_plus_pixels": str(dy1_zero_plus),
        "fixed_residual_nonzero_pixels": str(fixed_residual),
        "small_delta_pixels": str(small_delta),
        "large_delta_pixels": str(large_delta),
        "low2_aligned_pixels": str(low2_aligned),
        "low2_aligned_ratio": selector_summary.get("aligned_ratio", "0"),
        "low2_source_used_ratio": selector_summary.get("source_used_ratio", "0"),
        "low2_full_token_rows": selector_summary.get("full_token_rows", "0"),
        "low2_partial_token_rows": selector_summary.get("partial_token_rows", "0"),
        "low2_uncovered_small_delta_pixels": selector_summary.get("uncovered_pixels", "0"),
        "combined_covered_pixels": str(combined),
        "combined_covered_ratio": float_text(combined / target_pixels if target_pixels else 0.0),
        "remaining_nonzero_pixels": str(remaining_nonzero),
        "remaining_nonzero_ratio": float_text(remaining_nonzero / target_nonzero if target_nonzero else 0.0),
        "accounting_gap_pixels": str(accounting_gap),
        "selected_pixel_rows": str(selected_pixels),
        "issue_rows": str(issue_rows),
        "guarded_replay_verdict": verdict,
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
  <div class="stat"><div class="label">Low2 Aligned</div><div class="value">{html.escape(summary['low2_aligned_pixels'])}</div></div>
  <div class="stat"><div class="label">Remaining NZ</div><div class="value">{html.escape(summary['remaining_nonzero_pixels'])}</div></div>
</div>
<p>{html.escape(summary['next_action'])}</p>
<h2>Summary</h2>{render_table([summary], SUMMARY_FIELDNAMES)}
<h2>Selected Pixels</h2>{render_table(selected_rows[:160], SELECTED_FIELDNAMES)}
<script type="application/json" id="data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> tuple[dict[str, str], list[dict[str, str]]]:
    args.output.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    fixed_summary = read_summary(args.fixed_replay_summary)
    grammar_summary = read_summary(args.small_delta_grammar_summary)
    selector_summary = read_summary(args.low2_selector_summary)
    if not fixed_summary:
        issues.append("missing_fixed_replay_summary")
    if not grammar_summary:
        issues.append("missing_small_delta_grammar_summary")
    if not selector_summary:
        issues.append("missing_low2_selector_summary")
    alignment_rows = read_csv(args.low2_alignments)
    if not alignment_rows:
        issues.append("missing_low2_alignments")
    selected_rows = build_selected_rows(alignment_rows)
    summary = build_summary(fixed_summary, grammar_summary, selector_summary, selected_rows, issues)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "selected_pixels.csv", SELECTED_FIELDNAMES, selected_rows)
    (args.output / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""), encoding="utf-8")
    (args.output / "index.html").write_text(build_html(summary, selected_rows, args.output, args.title), encoding="utf-8")
    return summary, selected_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure guarded low2 replay coverage for shared 0x2700302b.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fixed-replay-summary", type=Path, default=DEFAULT_FIXED_REPLAY_SUMMARY)
    parser.add_argument("--small-delta-grammar-summary", type=Path, default=DEFAULT_SMALL_DELTA_GRAMMAR_SUMMARY)
    parser.add_argument("--low2-selector-summary", type=Path, default=DEFAULT_LOW2_SELECTOR_SUMMARY)
    parser.add_argument("--low2-alignments", type=Path, default=DEFAULT_LOW2_ALIGNMENTS)
    parser.add_argument("--title", default="Lands of Lore II .tex Shared 0x2700302b Fixed dy1 Low2 Guarded Replay")
    args = parser.parse_args()
    summary, _rows = write_report(args)
    print(f"Combined covered pixels: {summary['combined_covered_pixels']}")
    print(f"Combined covered ratio: {summary['combined_covered_ratio']}")
    print(f"Remaining nonzero pixels: {summary['remaining_nonzero_pixels']}")
    print(f"Verdict: {summary['guarded_replay_verdict']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
