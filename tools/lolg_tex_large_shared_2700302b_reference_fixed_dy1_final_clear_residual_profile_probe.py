#!/usr/bin/env python3
"""Profile the cleared residual after final literal replay for shared 0x2700302b."""

from __future__ import annotations

import argparse
import csv
import html
import json
import sys
from pathlib import Path

import lolg_tex_large_shared_2700302b_reference_fixed_dy1_post_low2_residual_profile_probe as post_low2_profile


DEFAULT_OUTPUT = Path("output/tex_large_shared_2700302b_reference_fixed_dy1_final_clear_residual_profile_probe")
DEFAULT_LITERAL_REPLAY_SUMMARY = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_final_orphan_literal_guarded_replay_probe/summary.csv"
)
DEFAULT_RESIDUAL_PIXELS = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_residual_profile_probe/residual_pixels.csv"
)
DEFAULT_SELECTED_PIXELS = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_final_orphan_literal_guarded_replay_probe/selected_pixels.csv"
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
    "combined_covered_pixels",
    "target_pixels",
    "combined_covered_ratio",
    "remaining_nonzero_pixels",
    "literal_replay_remaining_nonzero_pixels",
    "literal_replay_gap_pixels",
    "full_coverage",
    "issue_rows",
    "final_clear_verdict",
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
    literal_summary: dict[str, str],
    residual_rows: list[dict[str, str]],
    selected_rows: list[dict[str, str]],
    remaining_rows: list[dict[str, str]],
    issues: list[str],
) -> dict[str, str]:
    remaining = len(remaining_rows)
    replay_remaining = int_value(literal_summary, "remaining_nonzero_pixels")
    replay_gap = remaining - replay_remaining
    covered = int_value(literal_summary, "combined_covered_pixels")
    target = int_value(literal_summary, "target_pixels")
    full_coverage = remaining == 0 and target > 0 and covered == target
    issue_rows = len(issues)
    if replay_gap != 0:
        issue_rows += 1

    if issue_rows:
        verdict = "shared_2700302b_reference_fixed_dy1_final_clear_residual_profile_issues"
        next_action = "fix shared 0x2700302b final clear residual profile inputs"
    elif full_coverage:
        verdict = "shared_2700302b_reference_fixed_dy1_final_clear_residual_profile_complete"
        next_action = "promote shared 0x2700302b full replay coverage"
    else:
        verdict = "shared_2700302b_reference_fixed_dy1_final_clear_residual_profile_partial"
        next_action = f"inspect {remaining} residual pixels before promotion"

    return {
        "scope": "total",
        "archive": literal_summary.get("archive", ""),
        "archive_tag": literal_summary.get("archive_tag", ""),
        "pcx_name": literal_summary.get("pcx_name", ""),
        "frontier_id": literal_summary.get("frontier_id", ""),
        "dy": literal_summary.get("dy", ""),
        "shift": literal_summary.get("shift", ""),
        "input_residual_pixels": str(len(residual_rows)),
        "selected_pixels": str(len(selected_rows)),
        "combined_covered_pixels": str(covered),
        "target_pixels": str(target),
        "combined_covered_ratio": float_text(covered / target if target else 0.0),
        "remaining_nonzero_pixels": str(remaining),
        "literal_replay_remaining_nonzero_pixels": str(replay_remaining),
        "literal_replay_gap_pixels": str(replay_gap),
        "full_coverage": "1" if full_coverage else "0",
        "issue_rows": str(issue_rows),
        "final_clear_verdict": verdict,
        "next_action": next_action,
    }


def render_table(rows: list[dict[str, str]], fieldnames: list[str]) -> str:
    return post_low2_profile.render_table(rows, fieldnames)


def build_html(
    summary: dict[str, str],
    pixels: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "pixels": pixels}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(post_low2_profile.relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (("summary", output_dir / "summary.csv"), ("remaining_pixels", output_dir / "remaining_pixels.csv"))
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
  <div class="stat"><div class="label">Covered</div><div class="value">{html.escape(summary['combined_covered_pixels'])}/{html.escape(summary['target_pixels'])}</div></div>
  <div class="stat"><div class="label">Coverage Ratio</div><div class="value">{html.escape(summary['combined_covered_ratio'])}</div></div>
  <div class="stat"><div class="label">Remaining</div><div class="value">{html.escape(summary['remaining_nonzero_pixels'])}</div></div>
  <div class="stat"><div class="label">Full Coverage</div><div class="value">{html.escape(summary['full_coverage'])}</div></div>
</div>
<p>{html.escape(summary['next_action'])}</p>
<h2>Summary</h2>{render_table([summary], SUMMARY_FIELDNAMES)}
<h2>Remaining Pixels</h2>{render_table(pixels, post_low2_profile.PIXEL_FIELDNAMES)}
<script type="application/json" id="data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> tuple[dict[str, str], list[dict[str, str]]]:
    args.output.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    literal_summary = read_summary(args.literal_replay_summary)
    if not literal_summary:
        issues.append("missing_literal_replay_summary")
    residual_rows = read_csv(args.residual_pixels)
    if not residual_rows:
        issues.append("missing_residual_pixels")
    selected_rows = read_csv(args.selected_pixels)
    if not selected_rows:
        issues.append("missing_selected_pixels")
    pixels = post_low2_profile.remaining_pixels(residual_rows, selected_rows)
    summary = build_summary(literal_summary, residual_rows, selected_rows, pixels, issues)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "remaining_pixels.csv", post_low2_profile.PIXEL_FIELDNAMES, pixels)
    (args.output / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""), encoding="utf-8")
    (args.output / "index.html").write_text(build_html(summary, pixels, args.output, args.title), encoding="utf-8")
    return summary, pixels


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile final cleared residual after source-zero literal replay.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--literal-replay-summary", type=Path, default=DEFAULT_LITERAL_REPLAY_SUMMARY)
    parser.add_argument("--residual-pixels", type=Path, default=DEFAULT_RESIDUAL_PIXELS)
    parser.add_argument("--selected-pixels", type=Path, default=DEFAULT_SELECTED_PIXELS)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Shared 0x2700302b Final Clear Residual Profile",
    )
    args = parser.parse_args()
    summary, _pixels = write_report(args)
    print(f"Combined covered pixels: {summary['combined_covered_pixels']}/{summary['target_pixels']}")
    print(f"Remaining nonzero pixels: {summary['remaining_nonzero_pixels']}")
    print(f"Full coverage: {summary['full_coverage']}")
    print(f"Verdict: {summary['final_clear_verdict']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
