#!/usr/bin/env python3
"""Profile a reference-guided shared 0x2700302b frontier window."""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
import os
import struct
import sys
from collections import Counter
from pathlib import Path

from PIL import Image


DEFAULT_OUTPUT = Path("output/tex_large_shared_2700302b_reference_frontier_probe")
DEFAULT_FRONTIERS = Path("output/tex_gap_frontier_report/frontiers.csv")
DEFAULT_COMPARISONS = Path("output/tex_exact_cdcache_compare/comparisons.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "width",
    "height",
    "gap_start",
    "gap_end",
    "gap_start_x",
    "gap_start_y",
    "gap_end_x",
    "gap_end_y",
    "pixel_gap",
    "segment_gap_start",
    "segment_gap_end",
    "segment_gap_bytes",
    "segment_gap_ratio",
    "segment_entropy",
    "target_entropy",
    "segment_unique_values",
    "target_unique_values",
    "segment_zero_bytes",
    "segment_zero_ratio",
    "target_zero_pixels",
    "target_zero_ratio",
    "literal_match_rows",
    "longest_literal_match",
    "longest_literal_segment_offset",
    "longest_literal_target_offset",
    "greedy_literal_matches",
    "greedy_literal_pixels",
    "greedy_literal_ratio",
    "uncovered_pixels_after_literals",
    "row_rows",
    "row_min_entropy",
    "row_max_entropy",
    "row_avg_entropy",
    "issue_rows",
    "frontier_probe_verdict",
    "next_action",
]

LITERAL_FIELDNAMES = [
    "rank",
    "length",
    "segment_offset",
    "segment_absolute_offset",
    "target_offset",
    "target_absolute_offset",
    "target_x",
    "target_y",
    "hex_head",
]

ROW_FIELDNAMES = [
    "target_y",
    "x_start",
    "x_end",
    "pixels",
    "unique_values",
    "zero_pixels",
    "zero_ratio",
    "entropy",
    "top_values",
]

BYTE_FIELDNAMES = [
    "kind",
    "value_hex",
    "value",
    "count",
    "ratio",
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
    if not raw:
        return 0
    return int(raw, 0)


def float_text(value: float) -> str:
    return f"{value:.6f}"


def entropy(data: bytes) -> float:
    if not data:
        return 0.0
    counts = Counter(data)
    total = len(data)
    return -sum((count / total) * math.log2(count / total) for count in counts.values())


def compact_counter(counter: Counter[int], limit: int = 8) -> str:
    return "|".join(f"{value:02x}:{count}" for value, count in counter.most_common(limit))


def read_mix_entry(path: Path, index: int) -> tuple[int, bytes]:
    data = path.read_bytes()
    if len(data) < 6:
        raise ValueError(f"{path}: too small to be a MIX archive")
    count, body_size = struct.unpack_from("<HI", data, 0)
    table_end = 6 + count * 12
    if index < 0 or index >= count or table_end > len(data):
        raise ValueError(f"{path}: invalid MIX entry index {index}")
    file_id, offset, size = struct.unpack_from("<III", data, 6 + index * 12)
    if offset + size > body_size:
        raise ValueError(f"{path}: entry {index} exceeds declared body size")
    return file_id, data[table_end + offset : table_end + offset + size]


def load_indexed_pixels(path: Path) -> tuple[bytes, int, int]:
    with Image.open(path) as image:
        indexed = image if image.mode in {"1", "L", "P"} else image.convert("P")
        return indexed.tobytes(), indexed.width, indexed.height


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    try:
        return os.path.relpath(Path(path_text), base_dir)
    except ValueError:
        return str(path_text)


def select_frontier(rows: list[dict[str, str]], archive_tag: str, pcx_name: str, frontier_id: int) -> dict[str, str]:
    for row in rows:
        if (
            row.get("archive_tag") == archive_tag
            and row.get("pcx_name") == pcx_name
            and int_value(row, "frontier_id") == frontier_id
        ):
            return row
    return {}


def select_comparison(rows: list[dict[str, str]], archive: str, pcx_name: str) -> dict[str, str]:
    for row in rows:
        if row.get("archive") == archive and row.get("pcx_name") == pcx_name:
            return row
    return {}


def byte_profile(kind: str, data: bytes) -> list[dict[str, str]]:
    total = len(data)
    rows: list[dict[str, str]] = []
    for value, count in Counter(data).most_common():
        rows.append(
            {
                "kind": kind,
                "value_hex": f"{value:02x}",
                "value": str(value),
                "count": str(count),
                "ratio": float_text(count / total if total else 0.0),
            }
        )
    return rows


def literal_matches(segment_window: bytes, target_window: bytes, minimum: int) -> list[dict[str, str]]:
    target_positions: dict[int, list[int]] = {}
    for offset, value in enumerate(target_window):
        target_positions.setdefault(value, []).append(offset)
    rows: list[tuple[int, int, int]] = []
    for segment_offset, value in enumerate(segment_window):
        for target_offset in target_positions.get(value, []):
            length = 0
            while (
                segment_offset + length < len(segment_window)
                and target_offset + length < len(target_window)
                and segment_window[segment_offset + length] == target_window[target_offset + length]
            ):
                length += 1
            if length >= minimum:
                rows.append((length, segment_offset, target_offset))
    rows.sort(key=lambda row: (-row[0], row[1], row[2]))
    return [
        {
            "rank": str(index),
            "length": str(length),
            "segment_offset": str(segment_offset),
            "segment_absolute_offset": "",
            "target_offset": str(target_offset),
            "target_absolute_offset": "",
            "target_x": "",
            "target_y": "",
            "hex_head": segment_window[segment_offset : segment_offset + min(length, 24)].hex(),
        }
        for index, (length, segment_offset, target_offset) in enumerate(rows, 1)
    ]


def enrich_literal_rows(
    rows: list[dict[str, str]],
    *,
    segment_gap_start: int,
    gap_start: int,
    width: int,
) -> None:
    for row in rows:
        segment_absolute = segment_gap_start + int_value(row, "segment_offset")
        target_absolute = gap_start + int_value(row, "target_offset")
        row["segment_absolute_offset"] = str(segment_absolute)
        row["target_absolute_offset"] = str(target_absolute)
        row["target_x"] = str(target_absolute % width if width else 0)
        row["target_y"] = str(target_absolute // width if width else 0)


def greedy_literal_coverage(rows: list[dict[str, str]], target_len: int) -> tuple[int, int]:
    covered = [False] * target_len
    matches = 0
    for row in rows:
        length = int_value(row, "length")
        target_offset = int_value(row, "target_offset")
        if length <= 0 or target_offset + length > target_len:
            continue
        if any(covered[target_offset : target_offset + length]):
            continue
        for offset in range(target_offset, target_offset + length):
            covered[offset] = True
        matches += 1
    return matches, sum(covered)


def row_profiles(target_pixels: bytes, gap_start: int, gap_end: int, width: int) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if not width or gap_end < gap_start:
        return rows
    first_y = gap_start // width
    last_y = gap_end // width
    for y in range(first_y, last_y + 1):
        row_start = max(gap_start, y * width)
        row_end = min(gap_end, y * width + width - 1)
        data = target_pixels[row_start : row_end + 1]
        zero_pixels = data.count(0)
        rows.append(
            {
                "target_y": str(y),
                "x_start": str(row_start % width),
                "x_end": str(row_end % width),
                "pixels": str(len(data)),
                "unique_values": str(len(set(data))),
                "zero_pixels": str(zero_pixels),
                "zero_ratio": float_text(zero_pixels / len(data) if data else 0.0),
                "entropy": f"{entropy(data):.4f}",
                "top_values": compact_counter(Counter(data)),
            }
        )
    return rows


def build_summary(
    frontier: dict[str, str],
    comparison: dict[str, str],
    segment_window: bytes,
    target_window: bytes,
    literal_rows: list[dict[str, str]],
    row_rows: list[dict[str, str]],
    issues: list[str],
) -> dict[str, str]:
    width = int_value(comparison, "cdcache_width")
    height = int_value(comparison, "cdcache_height")
    segment_zero = segment_window.count(0)
    target_zero = target_window.count(0)
    greedy_matches, greedy_pixels = greedy_literal_coverage(literal_rows, len(target_window))
    longest = literal_rows[0] if literal_rows else {}
    row_entropies = [float(row.get("entropy", "0") or 0.0) for row in row_rows]
    issue_rows = len(issues)
    greedy_ratio = greedy_pixels / len(target_window) if target_window else 0.0
    if issue_rows:
        verdict = "shared_2700302b_reference_frontier_probe_issues"
        next_action = "fix shared 0x2700302b reference frontier probe inputs"
    elif greedy_ratio < 0.15 and target_zero / max(1, len(target_window)) > 0.25:
        verdict = "shared_2700302b_reference_frontier_zero_skip_literal_grammar_needed"
        next_action = (
            "derive row-aware zero-skip/literal-run grammar for shared 0x2700302b frontier "
            f"{frontier.get('frontier_id', '')}; segment {len(segment_window)} bytes for {len(target_window)} pixels"
        )
    else:
        verdict = "shared_2700302b_reference_frontier_literal_support_ready"
        next_action = (
            "promote strongest literal windows for shared 0x2700302b frontier "
            f"{frontier.get('frontier_id', '')} before probing residual controls"
        )
    return {
        "scope": "total",
        "archive": frontier.get("archive", ""),
        "archive_tag": frontier.get("archive_tag", ""),
        "pcx_name": frontier.get("pcx_name", ""),
        "frontier_id": frontier.get("frontier_id", ""),
        "width": str(width),
        "height": str(height),
        "gap_start": frontier.get("gap_start", ""),
        "gap_end": frontier.get("gap_end", ""),
        "gap_start_x": frontier.get("gap_start_x", ""),
        "gap_start_y": frontier.get("gap_start_y", ""),
        "gap_end_x": frontier.get("gap_end_x", ""),
        "gap_end_y": frontier.get("gap_end_y", ""),
        "pixel_gap": str(len(target_window)),
        "segment_gap_start": frontier.get("segment_gap_start", ""),
        "segment_gap_end": frontier.get("segment_gap_end", ""),
        "segment_gap_bytes": str(len(segment_window)),
        "segment_gap_ratio": float_text(len(segment_window) / len(target_window) if target_window else 0.0),
        "segment_entropy": f"{entropy(segment_window):.4f}",
        "target_entropy": f"{entropy(target_window):.4f}",
        "segment_unique_values": str(len(set(segment_window))),
        "target_unique_values": str(len(set(target_window))),
        "segment_zero_bytes": str(segment_zero),
        "segment_zero_ratio": float_text(segment_zero / len(segment_window) if segment_window else 0.0),
        "target_zero_pixels": str(target_zero),
        "target_zero_ratio": float_text(target_zero / len(target_window) if target_window else 0.0),
        "literal_match_rows": str(len(literal_rows)),
        "longest_literal_match": longest.get("length", "0"),
        "longest_literal_segment_offset": longest.get("segment_offset", ""),
        "longest_literal_target_offset": longest.get("target_offset", ""),
        "greedy_literal_matches": str(greedy_matches),
        "greedy_literal_pixels": str(greedy_pixels),
        "greedy_literal_ratio": float_text(greedy_ratio),
        "uncovered_pixels_after_literals": str(max(0, len(target_window) - greedy_pixels)),
        "row_rows": str(len(row_rows)),
        "row_min_entropy": f"{min(row_entropies) if row_entropies else 0.0:.4f}",
        "row_max_entropy": f"{max(row_entropies) if row_entropies else 0.0:.4f}",
        "row_avg_entropy": f"{sum(row_entropies) / len(row_entropies) if row_entropies else 0.0:.4f}",
        "issue_rows": str(issue_rows),
        "frontier_probe_verdict": verdict,
        "next_action": next_action,
    }


def build_html(
    summary: dict[str, str],
    literal_rows: list[dict[str, str]],
    row_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "literal_matches": literal_rows[:100], "row_profile": row_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary", output_dir / "summary.csv"),
            ("literal_matches", output_dir / "literal_matches.csv"),
            ("row_profile", output_dir / "row_profile.csv"),
            ("byte_profile", output_dir / "byte_profile.csv"),
        )
    )
    literal_html = "\n".join(
        "<tr>"
        f"<td>{html.escape(row['rank'])}</td>"
        f"<td>{html.escape(row['length'])}</td>"
        f"<td>{html.escape(row['segment_absolute_offset'])}</td>"
        f"<td>{html.escape(row['target_absolute_offset'])}</td>"
        f"<td>{html.escape(row['target_x'])},{html.escape(row['target_y'])}</td>"
        f"<td><code>{html.escape(row['hex_head'])}</code></td>"
        "</tr>"
        for row in literal_rows[:50]
    )
    row_html = "\n".join(
        "<tr>"
        f"<td>{html.escape(row['target_y'])}</td>"
        f"<td>{html.escape(row['x_start'])}-{html.escape(row['x_end'])}</td>"
        f"<td>{html.escape(row['pixels'])}</td>"
        f"<td>{html.escape(row['zero_ratio'])}</td>"
        f"<td>{html.escape(row['entropy'])}</td>"
        f"<td><code>{html.escape(row['top_values'])}</code></td>"
        "</tr>"
        for row in row_rows
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
th, td {{ border-bottom: 1px solid #343842; padding: 7px 9px; text-align: left; font-size: 13px; vertical-align: top; }}
th {{ color: #cfd6e4; background: #22252c; }}
code {{ overflow-wrap: anywhere; }}
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<p>{links}</p>
<div class="stats">
  <div class="stat"><div class="label">Segment Bytes</div><div class="value">{html.escape(summary['segment_gap_bytes'])}</div></div>
  <div class="stat"><div class="label">Target Pixels</div><div class="value">{html.escape(summary['pixel_gap'])}</div></div>
  <div class="stat"><div class="label">Target Zero Ratio</div><div class="value">{html.escape(summary['target_zero_ratio'])}</div></div>
  <div class="stat"><div class="label">Greedy Literal Ratio</div><div class="value">{html.escape(summary['greedy_literal_ratio'])}</div></div>
</div>
<p>{html.escape(summary['next_action'])}</p>
<h2>Literal Matches</h2>
<table>
<thead><tr><th>Rank</th><th>Length</th><th>Segment Abs</th><th>Target Abs</th><th>XY</th><th>Head</th></tr></thead>
<tbody>{literal_html}</tbody>
</table>
<h2>Rows</h2>
<table>
<thead><tr><th>Y</th><th>X</th><th>Pixels</th><th>Zero Ratio</th><th>Entropy</th><th>Top Values</th></tr></thead>
<tbody>{row_html}</tbody>
</table>
<script type="application/json" id="data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> tuple[dict[str, str], list[dict[str, str]]]:
    args.output.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    frontier = select_frontier(read_csv(args.frontiers), args.archive_tag, args.pcx_name, args.frontier_id)
    if not frontier:
        issues.append("missing_frontier")
    comparison = select_comparison(read_csv(args.comparisons), frontier.get("archive", ""), args.pcx_name)
    if not comparison:
        issues.append("missing_comparison")

    segment_window = b""
    target_window = b""
    if frontier and comparison:
        try:
            _file_id, payload = read_mix_entry(Path(frontier["archive"]), args.mix_entry_index)
            body_offset = int_value(comparison, "texture_body_offset")
            segment_size = int_value(comparison, "texture_segment_size")
            segment = payload[body_offset : body_offset + segment_size]
            start = int_value(frontier, "segment_gap_start")
            end = int_value(frontier, "segment_gap_end")
            segment_window = segment[start : end + 1]
            if len(segment_window) != int_value(frontier, "segment_gap_bytes"):
                issues.append("segment_window_size_mismatch")
        except Exception as exc:
            issues.append(f"segment_read_failed:{exc}")
        try:
            pixels, width, height = load_indexed_pixels(Path(comparison.get("cdcache_native_path", "")))
            expected_width = int_value(comparison, "cdcache_width")
            expected_height = int_value(comparison, "cdcache_height")
            if width != expected_width or height != expected_height:
                issues.append("reference_dimensions_mismatch")
            target_window = pixels[int_value(frontier, "gap_start") : int_value(frontier, "gap_end") + 1]
            if len(target_window) != int_value(frontier, "pixel_gap"):
                issues.append("target_window_size_mismatch")
        except Exception as exc:
            issues.append(f"reference_read_failed:{exc}")

    literal_rows = literal_matches(segment_window, target_window, args.min_literal)
    enrich_literal_rows(
        literal_rows,
        segment_gap_start=int_value(frontier, "segment_gap_start"),
        gap_start=int_value(frontier, "gap_start"),
        width=int_value(comparison, "cdcache_width"),
    )
    row_rows = row_profiles(
        load_indexed_pixels(Path(comparison.get("cdcache_native_path", "")))[0] if comparison else b"",
        int_value(frontier, "gap_start"),
        int_value(frontier, "gap_end"),
        int_value(comparison, "cdcache_width"),
    )
    summary = build_summary(frontier, comparison, segment_window, target_window, literal_rows, row_rows, issues)
    byte_rows = [*byte_profile("segment_window", segment_window), *byte_profile("target_window", target_window)]
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "literal_matches.csv", LITERAL_FIELDNAMES, literal_rows)
    write_csv(args.output / "row_profile.csv", ROW_FIELDNAMES, row_rows)
    write_csv(args.output / "byte_profile.csv", BYTE_FIELDNAMES, byte_rows)
    (args.output / "index.html").write_text(
        build_html(summary, literal_rows, row_rows, args.output, args.title),
        encoding="utf-8",
    )
    return summary, literal_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile one shared 0x2700302b reference-guided frontier.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--frontiers", type=Path, default=DEFAULT_FRONTIERS)
    parser.add_argument("--comparisons", type=Path, default=DEFAULT_COMPARISONS)
    parser.add_argument("--archive-tag", default="L4_HJ")
    parser.add_argument("--pcx-name", default="dinodead.pcx")
    parser.add_argument("--frontier-id", type=int, default=6)
    parser.add_argument("--mix-entry-index", type=int, default=2)
    parser.add_argument("--min-literal", type=int, default=4)
    parser.add_argument("--title", default="Lands of Lore II .tex Shared 0x2700302b Reference Frontier Probe")
    args = parser.parse_args()
    summary, _literal_rows = write_report(args)
    print(f"Frontier: {summary['pcx_name']} #{summary['frontier_id']}")
    print(f"Segment bytes: {summary['segment_gap_bytes']}")
    print(f"Target pixels: {summary['pixel_gap']}")
    print(f"Target zero ratio: {summary['target_zero_ratio']}")
    print(f"Greedy literal ratio: {summary['greedy_literal_ratio']}")
    print(f"Frontier verdict: {summary['frontier_probe_verdict']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
