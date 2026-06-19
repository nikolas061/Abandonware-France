#!/usr/bin/env python3
"""Probe spatial backref support for shared 0x2700302b reference frontier 6."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
from collections import Counter
from pathlib import Path

import lolg_tex_large_shared_2700302b_reference_frontier_probe as frontier_probe


DEFAULT_OUTPUT = Path("output/tex_large_shared_2700302b_reference_spatial_backref_probe")
DEFAULT_FRONTIERS = frontier_probe.DEFAULT_FRONTIERS
DEFAULT_COMPARISONS = frontier_probe.DEFAULT_COMPARISONS

SUMMARY_FIELDNAMES = [
    "scope",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "target_pixels",
    "target_zero_pixels",
    "target_nonzero_pixels",
    "row_rows",
    "max_dy",
    "shift_min",
    "shift_max",
    "best_nonzero_copy_pixels",
    "best_nonzero_copy_ratio",
    "best_all_copy_pixels",
    "best_all_copy_ratio",
    "zero_plus_copy_pixels",
    "zero_plus_copy_ratio",
    "dominant_copy_key",
    "dominant_copy_rows",
    "dominant_copy_nonzero_pixels",
    "dy1_shift0_rows",
    "dy1_shift0_nonzero_pixels",
    "issue_rows",
    "spatial_backref_verdict",
    "next_action",
]

ROW_FIELDNAMES = [
    "target_y",
    "x_start",
    "x_end",
    "pixels",
    "zero_pixels",
    "nonzero_pixels",
    "best_dy",
    "best_shift",
    "best_nonzero_matches",
    "best_nonzero_ratio",
    "best_all_matches",
    "best_all_ratio",
    "best_copy_key",
    "dy1_shift0_nonzero_matches",
    "dy1_shift0_nonzero_ratio",
    "dy1_shift0_all_matches",
    "dy1_shift0_all_ratio",
    "top_copy_keys",
]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def int_value(row: dict[str, str], field: str) -> int:
    return frontier_probe.int_value(row, field)


def float_text(value: float) -> str:
    return f"{value:.6f}"


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    try:
        return os.path.relpath(Path(path_text), base_dir)
    except ValueError:
        return str(path_text)


def load_reference(args: argparse.Namespace) -> tuple[dict[str, str], dict[str, str], bytes, int, int, list[str]]:
    issues: list[str] = []
    frontier = frontier_probe.select_frontier(
        frontier_probe.read_csv(args.frontiers),
        args.archive_tag,
        args.pcx_name,
        args.frontier_id,
    )
    if not frontier:
        issues.append("missing_frontier")
    comparison = frontier_probe.select_comparison(
        frontier_probe.read_csv(args.comparisons),
        frontier.get("archive", ""),
        args.pcx_name,
    )
    if not comparison:
        issues.append("missing_comparison")
    if issues:
        return frontier, comparison, b"", 0, 0, issues
    try:
        pixels, width, height = frontier_probe.load_indexed_pixels(Path(comparison.get("cdcache_native_path", "")))
    except Exception as exc:
        issues.append(f"reference_read_failed:{exc}")
        return frontier, comparison, b"", 0, 0, issues
    return frontier, comparison, pixels, width, height, issues


def row_slices(
    pixels: bytes,
    *,
    gap_start: int,
    gap_end: int,
    width: int,
) -> list[tuple[int, int, int, bytes]]:
    rows: list[tuple[int, int, int, bytes]] = []
    if not pixels or not width or gap_end < gap_start:
        return rows
    for y in range(gap_start // width, gap_end // width + 1):
        row_start = max(gap_start, y * width)
        row_end = min(gap_end, y * width + width - 1)
        rows.append((y, row_start % width, row_end % width, pixels[row_start : row_end + 1]))
    return rows


def source_row_window(pixels: bytes, width: int, source_y: int, x_start: int, length: int, shift: int) -> bytes:
    if source_y < 0 or not width:
        return b""
    values = bytearray()
    base = source_y * width
    for index in range(length):
        source_x = x_start + index + shift
        if 0 <= source_x < width:
            source_offset = base + source_x
            values.append(pixels[source_offset] if 0 <= source_offset < len(pixels) else 0xFF)
        else:
            values.append(0xFF)
    return bytes(values)


def match_counts(target: bytes, source: bytes) -> tuple[int, int]:
    nonzero = 0
    all_matches = 0
    for left, right in zip(target, source):
        if left == right:
            all_matches += 1
            if left:
                nonzero += 1
    return nonzero, all_matches


def analyze_rows(
    pixels: bytes,
    rows: list[tuple[int, int, int, bytes]],
    *,
    width: int,
    max_dy: int,
    shift_min: int,
    shift_max: int,
) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for y, x_start, x_end, target in rows:
        candidates: list[tuple[int, int, int, int]] = []
        for dy in range(1, max_dy + 1):
            source_y = y - dy
            for shift in range(shift_min, shift_max + 1):
                source = source_row_window(pixels, width, source_y, x_start, len(target), shift)
                nonzero_matches, all_matches = match_counts(target, source)
                candidates.append((nonzero_matches, all_matches, dy, shift))
        candidates.sort(reverse=True)
        best = candidates[0] if candidates else (0, 0, 0, 0)
        dy1_shift0 = next(
            (candidate for candidate in candidates if candidate[2] == 1 and candidate[3] == 0),
            (0, 0, 1, 0),
        )
        zero_pixels = target.count(0)
        nonzero_pixels = len(target) - zero_pixels
        top_keys = Counter(f"dy{dy}_sh{shift}" for _nz, _all, dy, shift in candidates[:8])
        output.append(
            {
                "target_y": str(y),
                "x_start": str(x_start),
                "x_end": str(x_end),
                "pixels": str(len(target)),
                "zero_pixels": str(zero_pixels),
                "nonzero_pixels": str(nonzero_pixels),
                "best_dy": str(best[2]),
                "best_shift": str(best[3]),
                "best_nonzero_matches": str(best[0]),
                "best_nonzero_ratio": float_text(best[0] / nonzero_pixels if nonzero_pixels else 0.0),
                "best_all_matches": str(best[1]),
                "best_all_ratio": float_text(best[1] / len(target) if target else 0.0),
                "best_copy_key": f"dy{best[2]}_sh{best[3]}",
                "dy1_shift0_nonzero_matches": str(dy1_shift0[0]),
                "dy1_shift0_nonzero_ratio": float_text(dy1_shift0[0] / nonzero_pixels if nonzero_pixels else 0.0),
                "dy1_shift0_all_matches": str(dy1_shift0[1]),
                "dy1_shift0_all_ratio": float_text(dy1_shift0[1] / len(target) if target else 0.0),
                "top_copy_keys": "|".join(f"{key}:{count}" for key, count in top_keys.most_common(8)),
            }
        )
    return output


def build_summary(
    frontier: dict[str, str],
    row_rows: list[dict[str, str]],
    *,
    max_dy: int,
    shift_min: int,
    shift_max: int,
    issues: list[str],
) -> dict[str, str]:
    target_pixels = sum(int_value(row, "pixels") for row in row_rows)
    target_zero = sum(int_value(row, "zero_pixels") for row in row_rows)
    target_nonzero = sum(int_value(row, "nonzero_pixels") for row in row_rows)
    best_nonzero = sum(int_value(row, "best_nonzero_matches") for row in row_rows)
    best_all = sum(int_value(row, "best_all_matches") for row in row_rows)
    zero_plus_copy = min(target_pixels, target_zero + best_nonzero)
    key_counter = Counter(row.get("best_copy_key", "") for row in row_rows if row.get("best_copy_key"))
    dominant_key, dominant_rows = key_counter.most_common(1)[0] if key_counter else ("", 0)
    dominant_nonzero = sum(
        int_value(row, "best_nonzero_matches") for row in row_rows if row.get("best_copy_key") == dominant_key
    )
    dy1_rows = sum(1 for row in row_rows if row.get("best_copy_key") == "dy1_sh0")
    dy1_nonzero = sum(int_value(row, "dy1_shift0_nonzero_matches") for row in row_rows)
    issue_rows = len(issues)
    zero_plus_ratio = zero_plus_copy / target_pixels if target_pixels else 0.0
    if issue_rows:
        verdict = "shared_2700302b_reference_spatial_backref_probe_issues"
        next_action = "fix shared 0x2700302b reference spatial backref probe inputs"
    elif zero_plus_ratio >= 0.55:
        verdict = "shared_2700302b_reference_spatial_backref_promising"
        next_action = (
            "derive row-copy/backref selector for shared 0x2700302b frontier "
            f"{frontier.get('frontier_id', '')}; zero-fill plus best spatial copy covers "
            f"{zero_plus_copy}/{target_pixels} pixels"
        )
    else:
        verdict = "shared_2700302b_reference_spatial_backref_weak"
        next_action = (
            "seek non-spatial producer for shared 0x2700302b frontier "
            f"{frontier.get('frontier_id', '')}; spatial copy covers only {zero_plus_copy}/{target_pixels} pixels"
        )
    return {
        "scope": "total",
        "archive": frontier.get("archive", ""),
        "archive_tag": frontier.get("archive_tag", ""),
        "pcx_name": frontier.get("pcx_name", ""),
        "frontier_id": frontier.get("frontier_id", ""),
        "target_pixels": str(target_pixels),
        "target_zero_pixels": str(target_zero),
        "target_nonzero_pixels": str(target_nonzero),
        "row_rows": str(len(row_rows)),
        "max_dy": str(max_dy),
        "shift_min": str(shift_min),
        "shift_max": str(shift_max),
        "best_nonzero_copy_pixels": str(best_nonzero),
        "best_nonzero_copy_ratio": float_text(best_nonzero / target_nonzero if target_nonzero else 0.0),
        "best_all_copy_pixels": str(best_all),
        "best_all_copy_ratio": float_text(best_all / target_pixels if target_pixels else 0.0),
        "zero_plus_copy_pixels": str(zero_plus_copy),
        "zero_plus_copy_ratio": float_text(zero_plus_ratio),
        "dominant_copy_key": dominant_key,
        "dominant_copy_rows": str(dominant_rows),
        "dominant_copy_nonzero_pixels": str(dominant_nonzero),
        "dy1_shift0_rows": str(dy1_rows),
        "dy1_shift0_nonzero_pixels": str(dy1_nonzero),
        "issue_rows": str(issue_rows),
        "spatial_backref_verdict": verdict,
        "next_action": next_action,
    }


def build_html(summary: dict[str, str], rows: list[dict[str, str]], output_dir: Path, title: str) -> str:
    payload = {"summary": summary, "rows": rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (("summary", output_dir / "summary.csv"), ("row_copies", output_dir / "row_copies.csv"))
    )
    row_markup = "\n".join(
        "<tr>"
        f"<td>{html.escape(row['target_y'])}</td>"
        f"<td>{html.escape(row['x_start'])}-{html.escape(row['x_end'])}</td>"
        f"<td>{html.escape(row['nonzero_pixels'])}</td>"
        f"<td>{html.escape(row['best_copy_key'])}</td>"
        f"<td>{html.escape(row['best_nonzero_matches'])}</td>"
        f"<td>{html.escape(row['best_nonzero_ratio'])}</td>"
        f"<td>{html.escape(row['best_all_matches'])}</td>"
        f"<td>{html.escape(row['best_all_ratio'])}</td>"
        f"<td>{html.escape(row['dy1_shift0_nonzero_matches'])}</td>"
        "</tr>"
        for row in rows
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
th, td {{ border-bottom: 1px solid #343842; padding: 7px 9px; text-align: left; font-size: 13px; }}
th {{ color: #cfd6e4; background: #22252c; }}
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<p>{links}</p>
<div class="stats">
  <div class="stat"><div class="label">Best Nonzero Copy</div><div class="value">{html.escape(summary['best_nonzero_copy_pixels'])}</div></div>
  <div class="stat"><div class="label">Zero + Copy</div><div class="value">{html.escape(summary['zero_plus_copy_pixels'])}</div></div>
  <div class="stat"><div class="label">Zero + Copy Ratio</div><div class="value">{html.escape(summary['zero_plus_copy_ratio'])}</div></div>
  <div class="stat"><div class="label">Dominant</div><div class="value">{html.escape(summary['dominant_copy_key'])}</div></div>
</div>
<p>{html.escape(summary['next_action'])}</p>
<table>
<thead><tr><th>Y</th><th>X</th><th>Nonzero</th><th>Best Copy</th><th>NZ Match</th><th>NZ Ratio</th><th>All Match</th><th>All Ratio</th><th>dy1/sh0 NZ</th></tr></thead>
<tbody>{row_markup}</tbody>
</table>
<script type="application/json" id="data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> tuple[dict[str, str], list[dict[str, str]]]:
    args.output.mkdir(parents=True, exist_ok=True)
    frontier, _comparison, pixels, width, _height, issues = load_reference(args)
    slices = row_slices(
        pixels,
        gap_start=int_value(frontier, "gap_start"),
        gap_end=int_value(frontier, "gap_end"),
        width=width,
    )
    rows = analyze_rows(
        pixels,
        slices,
        width=width,
        max_dy=args.max_dy,
        shift_min=args.shift_min,
        shift_max=args.shift_max,
    )
    summary = build_summary(
        frontier,
        rows,
        max_dy=args.max_dy,
        shift_min=args.shift_min,
        shift_max=args.shift_max,
        issues=issues,
    )
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "row_copies.csv", ROW_FIELDNAMES, rows)
    (args.output / "index.html").write_text(build_html(summary, rows, args.output, args.title), encoding="utf-8")
    return summary, rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe spatial backrefs for shared 0x2700302b frontier 6.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--frontiers", type=Path, default=DEFAULT_FRONTIERS)
    parser.add_argument("--comparisons", type=Path, default=DEFAULT_COMPARISONS)
    parser.add_argument("--archive-tag", default="L4_HJ")
    parser.add_argument("--pcx-name", default="dinodead.pcx")
    parser.add_argument("--frontier-id", type=int, default=6)
    parser.add_argument("--max-dy", type=int, default=8)
    parser.add_argument("--shift-min", type=int, default=-16)
    parser.add_argument("--shift-max", type=int, default=16)
    parser.add_argument("--title", default="Lands of Lore II .tex Shared 0x2700302b Reference Spatial Backref Probe")
    args = parser.parse_args()
    summary, _rows = write_report(args)
    print(f"Best nonzero copy pixels: {summary['best_nonzero_copy_pixels']}")
    print(f"Best nonzero copy ratio: {summary['best_nonzero_copy_ratio']}")
    print(f"Zero plus copy ratio: {summary['zero_plus_copy_ratio']}")
    print(f"Spatial backref verdict: {summary['spatial_backref_verdict']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
