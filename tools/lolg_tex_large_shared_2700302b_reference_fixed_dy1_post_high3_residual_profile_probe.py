#!/usr/bin/env python3
"""Profile residual pixels after guarded high3 non-low2 replay for shared 0x2700302b."""

from __future__ import annotations

import argparse
import csv
import html
import json
import sys
from collections import Counter
from pathlib import Path

import lolg_tex_large_shared_2700302b_reference_fixed_dy1_post_low2_residual_profile_probe as post_low2_profile


DEFAULT_OUTPUT = Path("output/tex_large_shared_2700302b_reference_fixed_dy1_post_high3_residual_profile_probe")
DEFAULT_GUARDED_HIGH3_SUMMARY = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_post_restart_low2_non_low2_guarded_replay_probe/summary.csv"
)
DEFAULT_RESIDUAL_PIXELS = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_residual_profile_probe/residual_pixels.csv"
)
DEFAULT_SELECTED_PIXELS = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_post_restart_low2_non_low2_guarded_replay_probe/selected_pixels.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "dy",
    "shift",
    "input_residual_pixels",
    "selected_pixels",
    "initial_low2_aligned_pixels",
    "restart_low2_aligned_pixels",
    "high3_non_low2_aligned_pixels",
    "remaining_nonzero_pixels",
    "remaining_small_delta_pixels",
    "remaining_small_delta_ratio",
    "remaining_large_delta_pixels",
    "remaining_large_delta_ratio",
    "remaining_source_zero_pixels",
    "remaining_source_zero_ratio",
    "remaining_run_rows",
    "max_remaining_run_pixels",
    "row_rows",
    "rows_with_source_zero",
    "dominant_delta",
    "dominant_delta_pixels",
    "guarded_high3_remaining_nonzero_pixels",
    "guarded_high3_gap_pixels",
    "issue_rows",
    "post_high3_residual_verdict",
    "next_action",
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


def build_summary(
    guarded_summary: dict[str, str],
    residual_rows: list[dict[str, str]],
    selected_rows: list[dict[str, str]],
    remaining_rows: list[dict[str, str]],
    row_rows: list[dict[str, str]],
    issues: list[str],
) -> dict[str, str]:
    remaining = len(remaining_rows)
    small = [row for row in remaining_rows if row.get("residual_kind") == "small_delta"]
    large = [row for row in remaining_rows if row.get("residual_kind") == "large_delta"]
    source_zero = [row for row in remaining_rows if int(row.get("source_value_hex", "0"), 16) == 0]
    runs = post_low2_profile.run_lengths(remaining_rows)
    delta_counter = Counter(int_value(row, "delta_signed") for row in remaining_rows)
    dominant_delta, dominant_count = delta_counter.most_common(1)[0] if delta_counter else (0, 0)
    guarded_remaining = int_value(guarded_summary, "remaining_nonzero_pixels")
    guarded_gap = remaining - guarded_remaining if guarded_remaining else 0
    issue_rows = len(issues)
    if guarded_remaining and guarded_gap != 0:
        issue_rows += 1

    if issue_rows:
        verdict = "shared_2700302b_reference_fixed_dy1_post_high3_residual_profile_issues"
        next_action = "fix shared 0x2700302b post-high3 residual profile inputs"
    elif len(large) > len(small):
        verdict = "shared_2700302b_reference_fixed_dy1_post_high3_large_delta_focus"
        next_action = (
            "derive large-delta/source-zero producer after high3 replay for shared 0x2700302b frontier "
            f"{guarded_summary.get('frontier_id', '')}; {len(large)} large-delta pixels remain"
        )
    else:
        verdict = "shared_2700302b_reference_fixed_dy1_post_high3_small_delta_remaining"
        next_action = (
            "split post-high3 residual small-delta misses for shared 0x2700302b frontier "
            f"{guarded_summary.get('frontier_id', '')}; {len(small)} small-delta and {len(large)} large-delta pixels remain"
        )

    return {
        "scope": "total",
        "archive": guarded_summary.get("archive", ""),
        "archive_tag": guarded_summary.get("archive_tag", ""),
        "pcx_name": guarded_summary.get("pcx_name", ""),
        "frontier_id": guarded_summary.get("frontier_id", ""),
        "dy": guarded_summary.get("dy", ""),
        "shift": guarded_summary.get("shift", ""),
        "input_residual_pixels": str(len(residual_rows)),
        "selected_pixels": str(len(selected_rows)),
        "initial_low2_aligned_pixels": guarded_summary.get("initial_low2_aligned_pixels", "0"),
        "restart_low2_aligned_pixels": guarded_summary.get("restart_low2_aligned_pixels", "0"),
        "high3_non_low2_aligned_pixels": guarded_summary.get("high3_non_low2_aligned_pixels", "0"),
        "remaining_nonzero_pixels": str(remaining),
        "remaining_small_delta_pixels": str(len(small)),
        "remaining_small_delta_ratio": float_text(len(small) / remaining if remaining else 0.0),
        "remaining_large_delta_pixels": str(len(large)),
        "remaining_large_delta_ratio": float_text(len(large) / remaining if remaining else 0.0),
        "remaining_source_zero_pixels": str(len(source_zero)),
        "remaining_source_zero_ratio": float_text(len(source_zero) / remaining if remaining else 0.0),
        "remaining_run_rows": str(len(runs)),
        "max_remaining_run_pixels": str(max(runs, default=0)),
        "row_rows": str(len(row_rows)),
        "rows_with_source_zero": str(sum(1 for row in row_rows if int_value(row, "source_zero_pixels") > 0)),
        "dominant_delta": str(dominant_delta),
        "dominant_delta_pixels": str(dominant_count),
        "guarded_high3_remaining_nonzero_pixels": str(guarded_remaining),
        "guarded_high3_gap_pixels": str(guarded_gap),
        "issue_rows": str(issue_rows),
        "post_high3_residual_verdict": verdict,
        "next_action": next_action,
    }


def render_table(rows: list[dict[str, str]], fieldnames: list[str]) -> str:
    return post_low2_profile.render_table(rows, fieldnames)


def build_html(
    summary: dict[str, str],
    pixels: list[dict[str, str]],
    rows: list[dict[str, str]],
    deltas: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "rows": rows, "deltas": deltas}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(post_low2_profile.relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary", output_dir / "summary.csv"),
            ("remaining_pixels", output_dir / "remaining_pixels.csv"),
            ("rows", output_dir / "rows.csv"),
            ("delta_profile", output_dir / "delta_profile.csv"),
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
  <div class="stat"><div class="label">Remaining</div><div class="value">{html.escape(summary['remaining_nonzero_pixels'])}</div></div>
  <div class="stat"><div class="label">Small Delta</div><div class="value">{html.escape(summary['remaining_small_delta_pixels'])}</div></div>
  <div class="stat"><div class="label">Large Delta</div><div class="value">{html.escape(summary['remaining_large_delta_pixels'])}</div></div>
  <div class="stat"><div class="label">Source Zero</div><div class="value">{html.escape(summary['remaining_source_zero_pixels'])}</div></div>
</div>
<p>{html.escape(summary['next_action'])}</p>
<h2>Summary</h2>{render_table([summary], SUMMARY_FIELDNAMES)}
<h2>Rows</h2>{render_table(rows, post_low2_profile.ROW_FIELDNAMES)}
<h2>Delta Profile</h2>{render_table(deltas, post_low2_profile.DELTA_FIELDNAMES)}
<h2>Remaining Pixels</h2>{render_table(pixels[:160], post_low2_profile.PIXEL_FIELDNAMES)}
<script type="application/json" id="data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> tuple[dict[str, str], list[dict[str, str]]]:
    args.output.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    guarded_summary = read_summary(args.guarded_high3_summary)
    if not guarded_summary:
        issues.append("missing_guarded_high3_summary")
    residual_rows = read_csv(args.residual_pixels)
    if not residual_rows:
        issues.append("missing_residual_pixels")
    selected_rows = read_csv(args.selected_pixels)
    if not selected_rows:
        issues.append("missing_selected_pixels")
    pixels = post_low2_profile.remaining_pixels(residual_rows, selected_rows)
    row_rows = post_low2_profile.build_row_rows(pixels)
    delta_rows = post_low2_profile.build_delta_rows(pixels)
    summary = build_summary(guarded_summary, residual_rows, selected_rows, pixels, row_rows, issues)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "remaining_pixels.csv", post_low2_profile.PIXEL_FIELDNAMES, pixels)
    write_csv(args.output / "rows.csv", post_low2_profile.ROW_FIELDNAMES, row_rows)
    write_csv(args.output / "delta_profile.csv", post_low2_profile.DELTA_FIELDNAMES, delta_rows)
    (args.output / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""), encoding="utf-8")
    (args.output / "index.html").write_text(
        build_html(summary, pixels, row_rows, delta_rows, args.output, args.title),
        encoding="utf-8",
    )
    return summary, pixels


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile post-high3 residuals for shared 0x2700302b.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--guarded-high3-summary", type=Path, default=DEFAULT_GUARDED_HIGH3_SUMMARY)
    parser.add_argument("--residual-pixels", type=Path, default=DEFAULT_RESIDUAL_PIXELS)
    parser.add_argument("--selected-pixels", type=Path, default=DEFAULT_SELECTED_PIXELS)
    parser.add_argument("--title", default="Lands of Lore II .tex Shared 0x2700302b Post-high3 Residual Profile")
    args = parser.parse_args()
    summary, _pixels = write_report(args)
    print(f"Remaining nonzero pixels: {summary['remaining_nonzero_pixels']}")
    print(f"Remaining small-delta pixels: {summary['remaining_small_delta_pixels']}")
    print(f"Remaining large-delta pixels: {summary['remaining_large_delta_pixels']}")
    print(f"Verdict: {summary['post_high3_residual_verdict']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
