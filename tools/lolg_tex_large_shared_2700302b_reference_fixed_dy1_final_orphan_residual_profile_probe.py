#!/usr/bin/env python3
"""Profile the final orphan residual after terminal replay for shared 0x2700302b."""

from __future__ import annotations

import argparse
import csv
import html
import json
import sys
from pathlib import Path

import lolg_tex_large_shared_2700302b_reference_fixed_dy1_post_low2_residual_profile_probe as post_low2_profile


DEFAULT_OUTPUT = Path("output/tex_large_shared_2700302b_reference_fixed_dy1_final_orphan_residual_profile_probe")
DEFAULT_TERMINAL_REPLAY_SUMMARY = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_post_horizontal_terminal_guarded_replay_probe/summary.csv"
)
DEFAULT_RESIDUAL_PIXELS = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_residual_profile_probe/residual_pixels.csv"
)
DEFAULT_SELECTED_PIXELS = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_post_horizontal_terminal_guarded_replay_probe/selected_pixels.csv"
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
    "remaining_nonzero_pixels",
    "remaining_target_y",
    "remaining_target_x",
    "remaining_target_value_hex",
    "remaining_source_value_hex",
    "remaining_delta_signed",
    "remaining_source_zero",
    "terminal_replay_remaining_nonzero_pixels",
    "terminal_replay_gap_pixels",
    "issue_rows",
    "final_orphan_verdict",
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


def build_summary(
    terminal_summary: dict[str, str],
    residual_rows: list[dict[str, str]],
    selected_rows: list[dict[str, str]],
    remaining_rows: list[dict[str, str]],
    issues: list[str],
) -> dict[str, str]:
    remaining = len(remaining_rows)
    orphan = remaining_rows[0] if remaining_rows else {}
    replay_remaining = int_value(terminal_summary, "remaining_nonzero_pixels")
    replay_gap = remaining - replay_remaining if replay_remaining else 0
    issue_rows = len(issues)
    if replay_remaining and replay_gap != 0:
        issue_rows += 1

    if issue_rows:
        verdict = "shared_2700302b_reference_fixed_dy1_final_orphan_residual_profile_issues"
        next_action = "fix shared 0x2700302b final orphan residual profile inputs"
    elif remaining == 1:
        verdict = "shared_2700302b_reference_fixed_dy1_final_orphan_source_zero_literal"
        next_action = (
            "derive final source-zero literal guard for shared 0x2700302b; "
            f"pixel y={orphan.get('target_y', '')} x={orphan.get('target_x', '')} "
            f"value={orphan.get('target_value_hex', '')}"
        )
    elif remaining == 0:
        verdict = "shared_2700302b_reference_fixed_dy1_final_orphan_clear"
        next_action = "promote shared 0x2700302b full replay coverage"
    else:
        verdict = "shared_2700302b_reference_fixed_dy1_final_orphan_multiple_pixels"
        next_action = f"inspect {remaining} final residual pixels for shared 0x2700302b"

    return {
        "scope": "total",
        "archive": terminal_summary.get("archive", ""),
        "archive_tag": terminal_summary.get("archive_tag", ""),
        "pcx_name": terminal_summary.get("pcx_name", ""),
        "frontier_id": terminal_summary.get("frontier_id", ""),
        "dy": terminal_summary.get("dy", ""),
        "shift": terminal_summary.get("shift", ""),
        "input_residual_pixels": str(len(residual_rows)),
        "selected_pixels": str(len(selected_rows)),
        "combined_covered_pixels": terminal_summary.get("combined_covered_pixels", "0"),
        "target_pixels": terminal_summary.get("target_pixels", "0"),
        "remaining_nonzero_pixels": str(remaining),
        "remaining_target_y": orphan.get("target_y", ""),
        "remaining_target_x": orphan.get("target_x", ""),
        "remaining_target_value_hex": orphan.get("target_value_hex", ""),
        "remaining_source_value_hex": orphan.get("source_value_hex", ""),
        "remaining_delta_signed": orphan.get("delta_signed", ""),
        "remaining_source_zero": "1" if orphan.get("source_value_hex") == "00" else "0",
        "terminal_replay_remaining_nonzero_pixels": str(replay_remaining),
        "terminal_replay_gap_pixels": str(replay_gap),
        "issue_rows": str(issue_rows),
        "final_orphan_verdict": verdict,
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
  <div class="stat"><div class="label">Remaining</div><div class="value">{html.escape(summary['remaining_nonzero_pixels'])}</div></div>
  <div class="stat"><div class="label">Target</div><div class="value">{html.escape(summary['remaining_target_y'])}:{html.escape(summary['remaining_target_x'])}</div></div>
  <div class="stat"><div class="label">Value</div><div class="value">{html.escape(summary['remaining_target_value_hex'])}</div></div>
  <div class="stat"><div class="label">Source Zero</div><div class="value">{html.escape(summary['remaining_source_zero'])}</div></div>
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
    terminal_summary = read_summary(args.terminal_replay_summary)
    if not terminal_summary:
        issues.append("missing_terminal_replay_summary")
    residual_rows = read_csv(args.residual_pixels)
    if not residual_rows:
        issues.append("missing_residual_pixels")
    selected_rows = read_csv(args.selected_pixels)
    if not selected_rows:
        issues.append("missing_selected_pixels")
    pixels = post_low2_profile.remaining_pixels(residual_rows, selected_rows)
    summary = build_summary(terminal_summary, residual_rows, selected_rows, pixels, issues)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "remaining_pixels.csv", post_low2_profile.PIXEL_FIELDNAMES, pixels)
    (args.output / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""), encoding="utf-8")
    (args.output / "index.html").write_text(build_html(summary, pixels, args.output, args.title), encoding="utf-8")
    return summary, pixels


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile final orphan residual after sparse terminal replay.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--terminal-replay-summary", type=Path, default=DEFAULT_TERMINAL_REPLAY_SUMMARY)
    parser.add_argument("--residual-pixels", type=Path, default=DEFAULT_RESIDUAL_PIXELS)
    parser.add_argument("--selected-pixels", type=Path, default=DEFAULT_SELECTED_PIXELS)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Shared 0x2700302b Final Orphan Residual Profile",
    )
    args = parser.parse_args()
    summary, _pixels = write_report(args)
    print(f"Remaining nonzero pixels: {summary['remaining_nonzero_pixels']}")
    print(f"Remaining target: y={summary['remaining_target_y']} x={summary['remaining_target_x']}")
    print(f"Remaining value: {summary['remaining_target_value_hex']}")
    print(f"Verdict: {summary['final_orphan_verdict']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
