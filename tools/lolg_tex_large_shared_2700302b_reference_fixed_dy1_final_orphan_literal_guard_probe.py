#!/usr/bin/env python3
"""Derive the final source-zero literal guard for shared 0x2700302b."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import sys
from pathlib import Path


DEFAULT_OUTPUT = Path("output/tex_large_shared_2700302b_reference_fixed_dy1_final_orphan_literal_guard_probe")
DEFAULT_ORPHAN_SUMMARY = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_final_orphan_residual_profile_probe/summary.csv"
)
DEFAULT_REMAINING_PIXELS = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_final_orphan_residual_profile_probe/remaining_pixels.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "dy",
    "shift",
    "orphan_pixels",
    "selected_pixels",
    "selected_target_y",
    "selected_target_x",
    "selected_target_value_hex",
    "selected_source_zero",
    "issue_rows",
    "final_literal_guard_verdict",
    "next_action",
]

SELECTED_FIELDNAMES = [
    "rank",
    "target_y",
    "target_x",
    "target_value_hex",
    "dy1_source_value_hex",
    "dy1_delta_signed",
    "literal_value_hex",
    "guard_kind",
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


def build_selected_rows(orphan_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in orphan_rows:
        if row.get("source_value_hex", "").lower() != "00":
            continue
        rows.append(
            {
                "rank": str(len(rows) + 1),
                "target_y": row.get("target_y", ""),
                "target_x": row.get("target_x", ""),
                "target_value_hex": row.get("target_value_hex", ""),
                "dy1_source_value_hex": row.get("source_value_hex", ""),
                "dy1_delta_signed": row.get("delta_signed", ""),
                "literal_value_hex": row.get("target_value_hex", ""),
                "guard_kind": "source_zero_literal",
            }
        )
    return rows


def build_summary(
    orphan_summary: dict[str, str],
    orphan_rows: list[dict[str, str]],
    selected_rows: list[dict[str, str]],
    issues: list[str],
) -> dict[str, str]:
    selected = selected_rows[0] if selected_rows else {}
    issue_rows = len(issues)
    if int_value(orphan_summary, "remaining_nonzero_pixels") != len(orphan_rows):
        issue_rows += 1

    if issue_rows:
        verdict = "shared_2700302b_reference_fixed_dy1_final_orphan_literal_guard_issues"
        next_action = "fix shared 0x2700302b final literal guard inputs"
    elif len(selected_rows) == len(orphan_rows) == 1:
        verdict = "shared_2700302b_reference_fixed_dy1_final_orphan_literal_guard_ready"
        next_action = "measure final source-zero literal replay for shared 0x2700302b"
    else:
        verdict = "shared_2700302b_reference_fixed_dy1_final_orphan_literal_guard_partial"
        next_action = "inspect final orphan rows before source-zero literal replay"

    return {
        "scope": "total",
        "archive": orphan_summary.get("archive", ""),
        "archive_tag": orphan_summary.get("archive_tag", ""),
        "pcx_name": orphan_summary.get("pcx_name", ""),
        "frontier_id": orphan_summary.get("frontier_id", ""),
        "dy": orphan_summary.get("dy", ""),
        "shift": orphan_summary.get("shift", ""),
        "orphan_pixels": str(len(orphan_rows)),
        "selected_pixels": str(len(selected_rows)),
        "selected_target_y": selected.get("target_y", ""),
        "selected_target_x": selected.get("target_x", ""),
        "selected_target_value_hex": selected.get("target_value_hex", ""),
        "selected_source_zero": selected.get("dy1_source_value_hex", ""),
        "issue_rows": str(issue_rows),
        "final_literal_guard_verdict": verdict,
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


def build_html(summary: dict[str, str], selected_rows: list[dict[str, str]], output_dir: Path, title: str) -> str:
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
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<p>{links}</p>
<div class="stats">
  <div class="stat"><div class="label">Selected</div><div class="value">{html.escape(summary['selected_pixels'])}</div></div>
  <div class="stat"><div class="label">Target</div><div class="value">{html.escape(summary['selected_target_y'])}:{html.escape(summary['selected_target_x'])}</div></div>
  <div class="stat"><div class="label">Value</div><div class="value">{html.escape(summary['selected_target_value_hex'])}</div></div>
  <div class="stat"><div class="label">Source</div><div class="value">{html.escape(summary['selected_source_zero'])}</div></div>
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
    orphan_summary_rows = read_csv(args.orphan_summary)
    orphan_summary = orphan_summary_rows[0] if orphan_summary_rows else {}
    if not orphan_summary:
        issues.append("missing_orphan_summary")
    orphan_rows = read_csv(args.remaining_pixels)
    if not orphan_rows:
        issues.append("missing_remaining_pixels")
    selected_rows = build_selected_rows(orphan_rows)
    summary = build_summary(orphan_summary, orphan_rows, selected_rows, issues)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "selected_pixels.csv", SELECTED_FIELDNAMES, selected_rows)
    (args.output / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""), encoding="utf-8")
    (args.output / "index.html").write_text(build_html(summary, selected_rows, args.output, args.title), encoding="utf-8")
    return summary, selected_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Derive final source-zero literal guard.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--orphan-summary", type=Path, default=DEFAULT_ORPHAN_SUMMARY)
    parser.add_argument("--remaining-pixels", type=Path, default=DEFAULT_REMAINING_PIXELS)
    parser.add_argument("--title", default="Lands of Lore II .tex Shared 0x2700302b Final Orphan Literal Guard")
    args = parser.parse_args()
    summary, _selected = write_report(args)
    print(f"Selected pixels: {summary['selected_pixels']}/{summary['orphan_pixels']}")
    print(f"Selected target: y={summary['selected_target_y']} x={summary['selected_target_x']}")
    print(f"Selected value: {summary['selected_target_value_hex']}")
    print(f"Verdict: {summary['final_literal_guard_verdict']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
