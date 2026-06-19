#!/usr/bin/env python3
"""Probe literal-stream support inside shared 0x2700302b reference frontier 6."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
from pathlib import Path

import lolg_tex_large_shared_2700302b_reference_frontier_probe as frontier_probe


DEFAULT_OUTPUT = Path("output/tex_large_shared_2700302b_reference_literal_stream_probe")
DEFAULT_FRONTIERS = frontier_probe.DEFAULT_FRONTIERS
DEFAULT_COMPARISONS = frontier_probe.DEFAULT_COMPARISONS

RANGES = (
    ("all", 0x00, 0xFF),
    ("30_bf", 0x30, 0xBF),
    ("40_bf", 0x40, 0xBF),
    ("50_bf", 0x50, 0xBF),
    ("54_bf", 0x54, 0xBF),
    ("58_bf", 0x58, 0xBF),
    ("50_af", 0x50, 0xAF),
    ("50_7f", 0x50, 0x7F),
)

SUMMARY_FIELDNAMES = [
    "scope",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "segment_bytes",
    "target_pixels",
    "target_nonzero_pixels",
    "range_rows",
    "best_range_id",
    "best_low_hex",
    "best_high_hex",
    "best_stream_bytes",
    "best_excluded_bytes",
    "best_lcs_bytes",
    "best_source_match_ratio",
    "best_nonzero_coverage",
    "row_window_rows",
    "row_window_monotonic_pairs",
    "row_window_lcs_bytes",
    "row_window_nonzero_coverage",
    "issue_rows",
    "literal_stream_verdict",
    "next_action",
]

RANGE_FIELDNAMES = [
    "rank",
    "range_id",
    "low_hex",
    "high_hex",
    "stream_bytes",
    "excluded_bytes",
    "lcs_bytes",
    "source_match_ratio",
    "nonzero_coverage",
]

ROW_WINDOW_FIELDNAMES = [
    "target_y",
    "source_start",
    "source_length",
    "filtered_source_bytes",
    "row_nonzero_pixels",
    "lcs_bytes",
    "source_match_ratio",
    "row_nonzero_coverage",
]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def float_text(value: float) -> str:
    return f"{value:.6f}"


def int_value(row: dict[str, str], field: str) -> int:
    return frontier_probe.int_value(row, field)


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    try:
        return os.path.relpath(Path(path_text), base_dir)
    except ValueError:
        return str(path_text)


def lcs_len(left: bytes, right: bytes) -> int:
    if not left or not right:
        return 0
    previous = [0] * (len(right) + 1)
    for left_value in left:
        current = [0]
        for index, right_value in enumerate(right, 1):
            if left_value == right_value:
                current.append(previous[index - 1] + 1)
            else:
                current.append(max(previous[index], current[-1]))
        previous = current
    return previous[-1]


def filtered(data: bytes, low: int, high: int) -> bytes:
    return bytes(value for value in data if low <= value <= high)


def load_windows(args: argparse.Namespace) -> tuple[dict[str, str], dict[str, str], bytes, bytes, bytes, list[str]]:
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
        return frontier, comparison, b"", b"", b"", issues

    try:
        _file_id, payload = frontier_probe.read_mix_entry(Path(frontier["archive"]), args.mix_entry_index)
        body_offset = int_value(comparison, "texture_body_offset")
        segment_size = int_value(comparison, "texture_segment_size")
        segment = payload[body_offset : body_offset + segment_size]
        segment_window = segment[int_value(frontier, "segment_gap_start") : int_value(frontier, "segment_gap_end") + 1]
    except Exception as exc:
        issues.append(f"segment_read_failed:{exc}")
        segment_window = b""

    try:
        pixels, _width, _height = frontier_probe.load_indexed_pixels(Path(comparison.get("cdcache_native_path", "")))
        target_window = pixels[int_value(frontier, "gap_start") : int_value(frontier, "gap_end") + 1]
    except Exception as exc:
        issues.append(f"reference_read_failed:{exc}")
        pixels = b""
        target_window = b""
    return frontier, comparison, segment_window, target_window, pixels, issues


def build_range_rows(segment_window: bytes, target_nonzero: bytes, *, min_stream_bytes: int) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for range_id, low, high in RANGES:
        stream = filtered(segment_window, low, high)
        lcs = lcs_len(stream, target_nonzero)
        rows.append(
            {
                "rank": "0",
                "range_id": range_id,
                "low_hex": f"{low:02x}",
                "high_hex": f"{high:02x}",
                "stream_bytes": str(len(stream)),
                "excluded_bytes": str(max(0, len(segment_window) - len(stream))),
                "lcs_bytes": str(lcs),
                "source_match_ratio": float_text(lcs / len(stream) if stream else 0.0),
                "nonzero_coverage": float_text(lcs / len(target_nonzero) if target_nonzero else 0.0),
            }
        )
    rows.sort(
        key=lambda row: (
            int(int_value(row, "stream_bytes") >= min_stream_bytes),
            float(row.get("source_match_ratio", "0") or 0),
            int_value(row, "lcs_bytes"),
        ),
        reverse=True,
    )
    for index, row in enumerate(rows, 1):
        row["rank"] = str(index)
    return rows


def row_target_slices(
    pixels: bytes,
    *,
    gap_start: int,
    gap_end: int,
    width: int,
) -> list[tuple[int, bytes]]:
    rows: list[tuple[int, bytes]] = []
    if not pixels or not width or gap_end < gap_start:
        return rows
    for y in range(gap_start // width, gap_end // width + 1):
        row_start = max(gap_start, y * width)
        row_end = min(gap_end, y * width + width - 1)
        nonzero = bytes(value for value in pixels[row_start : row_end + 1] if value)
        rows.append((y, nonzero))
    return rows


def build_row_windows(
    segment_window: bytes,
    row_slices: list[tuple[int, bytes]],
    *,
    low: int,
    high: int,
    start_step: int,
    min_length: int,
    max_length: int,
    length_step: int,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    lengths = list(range(min_length, max_length + 1, length_step))
    for y, row_nonzero in row_slices:
        best = (0, 0.0, 0, 0, 0)
        for source_start in range(0, len(segment_window), start_step):
            for source_length in lengths:
                raw = segment_window[source_start : source_start + source_length]
                stream = filtered(raw, low, high)
                if not stream:
                    continue
                lcs = lcs_len(stream, row_nonzero)
                source_ratio = lcs / len(stream) if stream else 0.0
                candidate = (lcs, source_ratio, source_start, source_length, len(stream))
                if candidate[:2] > best[:2]:
                    best = candidate
        lcs, source_ratio, source_start, source_length, stream_len = best
        rows.append(
            {
                "target_y": str(y),
                "source_start": str(source_start),
                "source_length": str(source_length),
                "filtered_source_bytes": str(stream_len),
                "row_nonzero_pixels": str(len(row_nonzero)),
                "lcs_bytes": str(lcs),
                "source_match_ratio": float_text(source_ratio),
                "row_nonzero_coverage": float_text(lcs / len(row_nonzero) if row_nonzero else 0.0),
            }
        )
    return rows


def best_range(rows: list[dict[str, str]], min_stream_bytes: int) -> dict[str, str]:
    eligible = [row for row in rows if int_value(row, "stream_bytes") >= min_stream_bytes]
    if not eligible:
        eligible = rows
    return eligible[0] if eligible else {}


def build_summary(
    frontier: dict[str, str],
    comparison: dict[str, str],
    segment_window: bytes,
    target_window: bytes,
    range_rows: list[dict[str, str]],
    row_windows: list[dict[str, str]],
    issues: list[str],
    min_stream_bytes: int,
) -> dict[str, str]:
    nonzero = bytes(value for value in target_window if value)
    best = best_range(range_rows, min_stream_bytes)
    monotonic_pairs = sum(
        1
        for left, right in zip(row_windows, row_windows[1:])
        if int_value(left, "source_start") <= int_value(right, "source_start")
    )
    row_lcs = sum(int_value(row, "lcs_bytes") for row in row_windows)
    issue_rows = len(issues)
    row_coverage = row_lcs / len(nonzero) if nonzero else 0.0
    if issue_rows:
        verdict = "shared_2700302b_reference_literal_stream_probe_issues"
        next_action = "fix shared 0x2700302b reference literal stream probe inputs"
    elif row_coverage < 0.25:
        verdict = "shared_2700302b_reference_literal_stream_partial_row_windows"
        next_action = (
            "derive control/backref producer for shared 0x2700302b frontier "
            f"{frontier.get('frontier_id', '')}; best literal stream "
            f"0x{best.get('low_hex', '')}-0x{best.get('high_hex', '')} covers "
            f"{best.get('lcs_bytes', '0')}/{len(nonzero)} nonzero pixels"
        )
    else:
        verdict = "shared_2700302b_reference_literal_stream_row_windows_ready"
        next_action = (
            "promote row-local literal source windows for shared 0x2700302b frontier "
            f"{frontier.get('frontier_id', '')}"
        )
    return {
        "scope": "total",
        "archive": frontier.get("archive", ""),
        "archive_tag": frontier.get("archive_tag", ""),
        "pcx_name": frontier.get("pcx_name", ""),
        "frontier_id": frontier.get("frontier_id", ""),
        "segment_bytes": str(len(segment_window)),
        "target_pixels": str(len(target_window)),
        "target_nonzero_pixels": str(len(nonzero)),
        "range_rows": str(len(range_rows)),
        "best_range_id": best.get("range_id", ""),
        "best_low_hex": best.get("low_hex", ""),
        "best_high_hex": best.get("high_hex", ""),
        "best_stream_bytes": best.get("stream_bytes", "0"),
        "best_excluded_bytes": best.get("excluded_bytes", "0"),
        "best_lcs_bytes": best.get("lcs_bytes", "0"),
        "best_source_match_ratio": best.get("source_match_ratio", "0"),
        "best_nonzero_coverage": best.get("nonzero_coverage", "0"),
        "row_window_rows": str(len(row_windows)),
        "row_window_monotonic_pairs": str(monotonic_pairs),
        "row_window_lcs_bytes": str(row_lcs),
        "row_window_nonzero_coverage": float_text(row_coverage),
        "issue_rows": str(issue_rows),
        "literal_stream_verdict": verdict,
        "next_action": next_action,
    }


def build_html(
    summary: dict[str, str],
    range_rows: list[dict[str, str]],
    row_windows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "ranges": range_rows, "rowWindows": row_windows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary", output_dir / "summary.csv"),
            ("literal_ranges", output_dir / "literal_ranges.csv"),
            ("row_windows", output_dir / "row_windows.csv"),
        )
    )
    range_markup = "\n".join(
        "<tr>"
        f"<td>{html.escape(row['rank'])}</td>"
        f"<td>{html.escape(row['range_id'])}</td>"
        f"<td>{html.escape(row['stream_bytes'])}</td>"
        f"<td>{html.escape(row['lcs_bytes'])}</td>"
        f"<td>{html.escape(row['source_match_ratio'])}</td>"
        f"<td>{html.escape(row['nonzero_coverage'])}</td>"
        "</tr>"
        for row in range_rows
    )
    row_markup = "\n".join(
        "<tr>"
        f"<td>{html.escape(row['target_y'])}</td>"
        f"<td>{html.escape(row['source_start'])}</td>"
        f"<td>{html.escape(row['source_length'])}</td>"
        f"<td>{html.escape(row['filtered_source_bytes'])}</td>"
        f"<td>{html.escape(row['row_nonzero_pixels'])}</td>"
        f"<td>{html.escape(row['lcs_bytes'])}</td>"
        f"<td>{html.escape(row['source_match_ratio'])}</td>"
        f"<td>{html.escape(row['row_nonzero_coverage'])}</td>"
        "</tr>"
        for row in row_windows
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
  <div class="stat"><div class="label">Best Range</div><div class="value">{html.escape(summary['best_range_id'])}</div></div>
  <div class="stat"><div class="label">Best LCS</div><div class="value">{html.escape(summary['best_lcs_bytes'])}</div></div>
  <div class="stat"><div class="label">Best Coverage</div><div class="value">{html.escape(summary['best_nonzero_coverage'])}</div></div>
  <div class="stat"><div class="label">Row Coverage</div><div class="value">{html.escape(summary['row_window_nonzero_coverage'])}</div></div>
</div>
<p>{html.escape(summary['next_action'])}</p>
<h2>Literal Ranges</h2>
<table>
<thead><tr><th>Rank</th><th>Range</th><th>Stream Bytes</th><th>LCS</th><th>Source Ratio</th><th>Nonzero Coverage</th></tr></thead>
<tbody>{range_markup}</tbody>
</table>
<h2>Row Windows</h2>
<table>
<thead><tr><th>Y</th><th>Start</th><th>Length</th><th>Filtered</th><th>Nonzero</th><th>LCS</th><th>Source Ratio</th><th>Coverage</th></tr></thead>
<tbody>{row_markup}</tbody>
</table>
<script type="application/json" id="data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    args.output.mkdir(parents=True, exist_ok=True)
    frontier, comparison, segment_window, target_window, pixels, issues = load_windows(args)
    target_nonzero = bytes(value for value in target_window if value)
    range_rows = build_range_rows(segment_window, target_nonzero, min_stream_bytes=args.min_stream_bytes)
    best = best_range(range_rows, args.min_stream_bytes)
    low = int(best.get("low_hex", "50") or "50", 16)
    high = int(best.get("high_hex", "bf") or "bf", 16)
    row_slices = row_target_slices(
        pixels,
        gap_start=int_value(frontier, "gap_start"),
        gap_end=int_value(frontier, "gap_end"),
        width=int_value(comparison, "cdcache_width"),
    )
    row_windows = build_row_windows(
        segment_window,
        row_slices,
        low=low,
        high=high,
        start_step=args.row_start_step,
        min_length=args.row_min_length,
        max_length=args.row_max_length,
        length_step=args.row_length_step,
    )
    summary = build_summary(
        frontier,
        comparison,
        segment_window,
        target_window,
        range_rows,
        row_windows,
        issues,
        args.min_stream_bytes,
    )
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "literal_ranges.csv", RANGE_FIELDNAMES, range_rows)
    write_csv(args.output / "row_windows.csv", ROW_WINDOW_FIELDNAMES, row_windows)
    (args.output / "index.html").write_text(
        build_html(summary, range_rows, row_windows, args.output, args.title),
        encoding="utf-8",
    )
    return summary, range_rows, row_windows


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe literal-stream support for shared 0x2700302b frontier 6.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--frontiers", type=Path, default=DEFAULT_FRONTIERS)
    parser.add_argument("--comparisons", type=Path, default=DEFAULT_COMPARISONS)
    parser.add_argument("--archive-tag", default="L4_HJ")
    parser.add_argument("--pcx-name", default="dinodead.pcx")
    parser.add_argument("--frontier-id", type=int, default=6)
    parser.add_argument("--mix-entry-index", type=int, default=2)
    parser.add_argument("--min-stream-bytes", type=int, default=128)
    parser.add_argument("--row-start-step", type=int, default=4)
    parser.add_argument("--row-min-length", type=int, default=16)
    parser.add_argument("--row-max-length", type=int, default=96)
    parser.add_argument("--row-length-step", type=int, default=8)
    parser.add_argument("--title", default="Lands of Lore II .tex Shared 0x2700302b Reference Literal Stream Probe")
    args = parser.parse_args()
    summary, _range_rows, _row_windows = write_report(args)
    print(f"Best range: {summary['best_range_id']}")
    print(f"Best LCS bytes: {summary['best_lcs_bytes']}")
    print(f"Best nonzero coverage: {summary['best_nonzero_coverage']}")
    print(f"Row window nonzero coverage: {summary['row_window_nonzero_coverage']}")
    print(f"Literal stream verdict: {summary['literal_stream_verdict']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
