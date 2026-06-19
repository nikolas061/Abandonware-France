#!/usr/bin/env python3
"""Derive a sparse terminal residual guard after horizontal replay for shared 0x2700302b."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import sys
from pathlib import Path


DEFAULT_OUTPUT = Path("output/tex_large_shared_2700302b_reference_fixed_dy1_post_horizontal_terminal_guard_probe")
DEFAULT_TERMINAL_SUMMARY = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_post_horizontal_terminal_residual_inspection_probe/summary.csv"
)
DEFAULT_TERMINAL_PIXELS = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_post_horizontal_terminal_residual_inspection_probe/pixels.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "dy",
    "shift",
    "terminal_pixels",
    "local_supported_pixels",
    "selected_pixels",
    "selected_exact_pixels",
    "selected_small_only_pixels",
    "unsupported_pixels",
    "source_zero_selected_pixels",
    "issue_rows",
    "terminal_guard_verdict",
    "next_action",
]

SELECTED_FIELDNAMES = [
    "rank",
    "target_y",
    "target_x",
    "target_value_hex",
    "dy1_source_value_hex",
    "dy1_delta_signed",
    "source_zero",
    "local_dy",
    "local_dx",
    "local_source_value_hex",
    "local_delta_signed",
    "match_kind",
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
    return int(raw, 0) if raw else 0


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    try:
        return os.path.relpath(Path(path_text), base_dir)
    except ValueError:
        return str(path_text)


def build_selected_rows(pixel_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in pixel_rows:
        if row.get("best_match_kind") == "unsupported":
            continue
        rows.append(
            {
                "rank": str(len(rows) + 1),
                "target_y": row.get("target_y", ""),
                "target_x": row.get("target_x", ""),
                "target_value_hex": row.get("target_value_hex", ""),
                "dy1_source_value_hex": row.get("dy1_source_value_hex", ""),
                "dy1_delta_signed": row.get("dy1_delta_signed", ""),
                "source_zero": row.get("source_zero", "0"),
                "local_dy": row.get("best_local_dy", ""),
                "local_dx": row.get("best_local_dx", ""),
                "local_source_value_hex": row.get("best_source_value_hex", ""),
                "local_delta_signed": row.get("best_delta_signed", ""),
                "match_kind": row.get("best_match_kind", ""),
            }
        )
    return rows


def build_summary(
    terminal_summary: dict[str, str],
    pixel_rows: list[dict[str, str]],
    selected_rows: list[dict[str, str]],
    issues: list[str],
) -> dict[str, str]:
    terminal = len(pixel_rows)
    supported = int_value(terminal_summary, "local_supported_pixels")
    selected = len(selected_rows)
    unsupported = terminal - selected
    exact = sum(1 for row in selected_rows if row.get("match_kind") == "exact")
    small = sum(1 for row in selected_rows if row.get("match_kind") == "small_delta")
    source_zero = sum(int_value(row, "source_zero") for row in selected_rows)
    issue_rows = len(issues)
    if supported and selected != supported:
        issue_rows += 1

    if issue_rows:
        verdict = "shared_2700302b_reference_fixed_dy1_post_horizontal_terminal_guard_issues"
        next_action = "fix shared 0x2700302b terminal guard inputs"
    elif selected:
        verdict = "shared_2700302b_reference_fixed_dy1_post_horizontal_terminal_guard_ready"
        next_action = (
            "measure guarded sparse terminal replay after horizontal replay for shared 0x2700302b; "
            f"guard selects {selected}/{terminal} pixels"
        )
    else:
        verdict = "shared_2700302b_reference_fixed_dy1_post_horizontal_terminal_guard_empty"
        next_action = "search terminal residual source before sparse guard replay"

    return {
        "scope": "total",
        "archive": terminal_summary.get("archive", ""),
        "archive_tag": terminal_summary.get("archive_tag", ""),
        "pcx_name": terminal_summary.get("pcx_name", ""),
        "frontier_id": terminal_summary.get("frontier_id", ""),
        "dy": terminal_summary.get("dy", ""),
        "shift": terminal_summary.get("shift", ""),
        "terminal_pixels": str(terminal),
        "local_supported_pixels": str(supported),
        "selected_pixels": str(selected),
        "selected_exact_pixels": str(exact),
        "selected_small_only_pixels": str(small),
        "unsupported_pixels": str(unsupported),
        "source_zero_selected_pixels": str(source_zero),
        "issue_rows": str(issue_rows),
        "terminal_guard_verdict": verdict,
        "next_action": next_action,
    }


def render_table(rows: list[dict[str, str]], fields: list[str]) -> str:
    if not rows:
        return "<p>No rows.</p>"
    head = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"
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
            ("selected pixels", output_dir / "selected_pixels.csv"),
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
  <div class="stat"><div class="label">Selected</div><div class="value">{html.escape(summary['selected_pixels'])}</div></div>
  <div class="stat"><div class="label">Exact</div><div class="value">{html.escape(summary['selected_exact_pixels'])}</div></div>
  <div class="stat"><div class="label">Small Only</div><div class="value">{html.escape(summary['selected_small_only_pixels'])}</div></div>
  <div class="stat"><div class="label">Unsupported</div><div class="value">{html.escape(summary['unsupported_pixels'])}</div></div>
</div>
<p>{html.escape(summary['next_action'])}</p>
<h2>Summary</h2>{render_table([summary], SUMMARY_FIELDNAMES)}
<h2>Selected Pixels</h2>{render_table(selected_rows, SELECTED_FIELDNAMES)}
<script type="application/json" id="data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> tuple[dict[str, str], list[dict[str, str]]]:
    args.output.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    terminal_summary_rows = read_csv(args.terminal_summary)
    terminal_summary = terminal_summary_rows[0] if terminal_summary_rows else {}
    if not terminal_summary:
        issues.append("missing_terminal_summary")
    pixel_rows = read_csv(args.terminal_pixels)
    if not pixel_rows:
        issues.append("missing_terminal_pixels")
    if len(pixel_rows) != int_value(terminal_summary, "terminal_pixels"):
        issues.append("terminal_summary_gap")
    selected_rows = build_selected_rows(pixel_rows)
    summary = build_summary(terminal_summary, pixel_rows, selected_rows, issues)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "selected_pixels.csv", SELECTED_FIELDNAMES, selected_rows)
    (args.output / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""), encoding="utf-8")
    (args.output / "index.html").write_text(
        build_html(summary, selected_rows, args.output, args.title),
        encoding="utf-8",
    )
    return summary, selected_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Derive a sparse terminal residual guard after horizontal replay.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--terminal-summary", type=Path, default=DEFAULT_TERMINAL_SUMMARY)
    parser.add_argument("--terminal-pixels", type=Path, default=DEFAULT_TERMINAL_PIXELS)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Shared 0x2700302b Post-horizontal Terminal Guard",
    )
    args = parser.parse_args()
    summary, _selected = write_report(args)
    print(f"Selected pixels: {summary['selected_pixels']}/{summary['terminal_pixels']}")
    print(f"Exact pixels: {summary['selected_exact_pixels']}")
    print(f"Unsupported pixels: {summary['unsupported_pixels']}")
    print(f"Verdict: {summary['terminal_guard_verdict']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
