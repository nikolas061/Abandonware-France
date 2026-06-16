#!/usr/bin/env python3
"""Exhaustively scan exact .tex segments for high-signal CDCACHE pixel chunks."""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
import os
import struct
from collections import Counter
from pathlib import Path

from PIL import Image


DEFAULT_OUTPUT = Path("output/tex_exact_chunk_scan")
DEFAULT_COMPARISONS = Path("output/tex_exact_cdcache_compare/comparisons.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "segments",
    "matched_segments",
    "scan_rows",
    "chunk_sizes",
    "min_entropy",
    "max_zero_ratio",
    "max_rows_per_segment_size",
    "capped_segment_size_groups",
    "issue_rows",
]

SCAN_FIELDNAMES = [
    "archive",
    "archive_tag",
    "pcx_name",
    "chunk_size",
    "pixel_offset",
    "pixel_offset_hex",
    "pixel_x",
    "pixel_y",
    "segment_offset",
    "segment_offset_hex",
    "entropy",
    "zero_ratio",
    "unique_values",
    "pixel_occurrences",
    "chunk_hex",
    "segment_context_hex",
    "pixel_context_hex",
    "issues",
]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


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


def load_pixels(path: Path) -> tuple[bytes, int, int]:
    with Image.open(path) as image:
        if image.mode not in {"1", "L", "P"}:
            image = image.convert("L")
        return image.tobytes(), image.width, image.height


def entropy(data: bytes) -> float:
    if not data:
        return 0.0
    counts = Counter(data)
    total = len(data)
    value = 0.0
    for count in counts.values():
        p = count / total
        value -= p * math.log2(p)
    return value


def chunk_stats(chunk: bytes) -> tuple[float, float, int]:
    if not chunk:
        return 0.0, 0.0, 0
    return entropy(chunk), chunk.count(0) / len(chunk), len(set(chunk))


def context(data: bytes, offset: int, chunk_size: int, radius: int) -> bytes:
    start = max(0, offset - radius)
    end = min(len(data), offset + chunk_size + radius)
    return data[start:end]


def pixel_chunk_index(
    pixels: bytes,
    chunk_size: int,
    *,
    min_entropy: float,
    max_zero_ratio: float,
    max_positions_per_chunk: int,
) -> dict[bytes, list[int]]:
    index: dict[bytes, list[int]] = {}
    for pixel_offset in range(0, len(pixels) - chunk_size + 1):
        chunk = pixels[pixel_offset : pixel_offset + chunk_size]
        value_entropy, zero_ratio, _unique = chunk_stats(chunk)
        if value_entropy < min_entropy or zero_ratio > max_zero_ratio:
            continue
        positions = index.setdefault(chunk, [])
        if len(positions) < max_positions_per_chunk:
            positions.append(pixel_offset)
    return index


def scan_segment(
    *,
    archive: str,
    archive_tag: str,
    pcx_name: str,
    segment: bytes,
    pixels: bytes,
    width: int,
    chunk_size: int,
    min_entropy: float,
    max_zero_ratio: float,
    max_rows: int,
    context_radius: int,
    max_positions_per_chunk: int,
) -> list[dict[str, str]]:
    pixel_index = pixel_chunk_index(
        pixels,
        chunk_size,
        min_entropy=min_entropy,
        max_zero_ratio=max_zero_ratio,
        max_positions_per_chunk=max_positions_per_chunk,
    )
    rows: list[dict[str, str]] = []
    seen: set[tuple[int, int]] = set()
    if not pixel_index:
        return rows
    for segment_offset in range(0, len(segment) - chunk_size + 1):
        chunk = segment[segment_offset : segment_offset + chunk_size]
        pixel_offsets = pixel_index.get(chunk)
        if not pixel_offsets:
            continue
        value_entropy, zero_ratio, unique_values = chunk_stats(chunk)
        for pixel_offset in pixel_offsets:
            key = (segment_offset, pixel_offset)
            if key in seen:
                continue
            seen.add(key)
            x = pixel_offset % width if width else 0
            y = pixel_offset // width if width else 0
            rows.append(
                {
                    "archive": archive,
                    "archive_tag": archive_tag,
                    "pcx_name": pcx_name,
                    "chunk_size": str(chunk_size),
                    "pixel_offset": str(pixel_offset),
                    "pixel_offset_hex": f"0x{pixel_offset:08x}",
                    "pixel_x": str(x),
                    "pixel_y": str(y),
                    "segment_offset": str(segment_offset),
                    "segment_offset_hex": f"0x{segment_offset:08x}",
                    "entropy": f"{value_entropy:.4f}",
                    "zero_ratio": f"{zero_ratio:.4f}",
                    "unique_values": str(unique_values),
                    "pixel_occurrences": str(len(pixel_offsets)),
                    "chunk_hex": chunk.hex(),
                    "segment_context_hex": context(segment, segment_offset, chunk_size, context_radius).hex(),
                    "pixel_context_hex": context(pixels, pixel_offset, chunk_size, context_radius).hex(),
                    "issues": "",
                }
            )
            if len(rows) >= max_rows:
                return rows
    return rows


def build_scan_rows(
    comparison_rows: list[dict[str, str]],
    *,
    chunk_sizes: list[int],
    min_entropy: float,
    max_zero_ratio: float,
    max_rows_per_segment_size: int,
    context_radius: int,
    max_positions_per_chunk: int,
) -> list[dict[str, str]]:
    payload_cache: dict[Path, bytes] = {}
    rows: list[dict[str, str]] = []
    for comparison in comparison_rows:
        issues: list[str] = []
        archive = Path(comparison.get("archive", ""))
        if archive not in payload_cache:
            try:
                _file_id, payload_cache[archive] = read_mix_entry(archive, 2)
            except Exception as exc:
                payload_cache[archive] = b""
                issues.append(f"archive_read_failed:{exc}")
        payload = payload_cache[archive]
        body_offset = int(comparison.get("texture_body_offset") or 0)
        segment_size = int(comparison.get("texture_segment_size") or 0)
        segment = payload[body_offset : body_offset + segment_size]
        if len(segment) != segment_size:
            issues.append("segment_size_mismatch")

        pixels = b""
        width = 0
        native_path = Path(comparison.get("cdcache_native_path", ""))
        if not native_path.exists():
            issues.append("missing_cdcache_native_path")
        else:
            try:
                pixels, width, _height = load_pixels(native_path)
            except Exception as exc:
                issues.append(f"cdcache_image_read_failed:{exc}")

        if issues:
            rows.append(
                {
                    "archive": comparison.get("archive", ""),
                    "archive_tag": comparison.get("archive_tag", ""),
                    "pcx_name": comparison.get("pcx_name", ""),
                    "chunk_size": "",
                    "pixel_offset": "",
                    "pixel_offset_hex": "",
                    "pixel_x": "",
                    "pixel_y": "",
                    "segment_offset": "",
                    "segment_offset_hex": "",
                    "entropy": "",
                    "zero_ratio": "",
                    "unique_values": "",
                    "pixel_occurrences": "",
                    "chunk_hex": "",
                    "segment_context_hex": "",
                    "pixel_context_hex": "",
                    "issues": ";".join(issues),
                }
            )
            continue

        for chunk_size in chunk_sizes:
            rows.extend(
                scan_segment(
                    archive=comparison.get("archive", ""),
                    archive_tag=comparison.get("archive_tag", ""),
                    pcx_name=comparison.get("pcx_name", ""),
                    segment=segment,
                    pixels=pixels,
                    width=width,
                    chunk_size=chunk_size,
                    min_entropy=min_entropy,
                    max_zero_ratio=max_zero_ratio,
                    max_rows=max_rows_per_segment_size,
                    context_radius=context_radius,
                    max_positions_per_chunk=max_positions_per_chunk,
                )
            )
    rows.sort(
        key=lambda row: (
            row.get("pcx_name", ""),
            -int(row.get("chunk_size") or 0),
            int(row.get("segment_offset") or 0),
            int(row.get("pixel_offset") or 0),
        )
    )
    return rows


def summary_row(
    comparison_rows: list[dict[str, str]],
    scan_rows: list[dict[str, str]],
    *,
    chunk_sizes: list[int],
    min_entropy: float,
    max_zero_ratio: float,
    max_rows_per_segment_size: int,
) -> dict[str, str]:
    matched_segments = {
        (row["archive"], row["pcx_name"])
        for row in scan_rows
        if row.get("segment_offset") and not row.get("issues")
    }
    grouped_counts = Counter(
        (row.get("archive", ""), row.get("pcx_name", ""), row.get("chunk_size", ""))
        for row in scan_rows
        if row.get("segment_offset") and not row.get("issues")
    )
    return {
        "scope": "total",
        "segments": str(len(comparison_rows)),
        "matched_segments": str(len(matched_segments)),
        "scan_rows": str(sum(1 for row in scan_rows if row.get("segment_offset"))),
        "chunk_sizes": ";".join(str(size) for size in chunk_sizes),
        "min_entropy": f"{min_entropy:.4f}",
        "max_zero_ratio": f"{max_zero_ratio:.4f}",
        "max_rows_per_segment_size": str(max_rows_per_segment_size),
        "capped_segment_size_groups": str(
            sum(1 for count in grouped_counts.values() if count >= max_rows_per_segment_size)
        ),
        "issue_rows": str(sum(1 for row in scan_rows if row.get("issues"))),
    }


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    if not path_text:
        return ""
    path = Path(path_text)
    try:
        relative = path.relative_to(base_dir)
    except ValueError:
        relative = Path(os.path.relpath(path, base_dir))
    return relative.as_posix()


def render_row(row: dict[str, str]) -> str:
    return (
        "<tr>"
        f"<td>{html.escape(row.get('pcx_name', ''))}</td>"
        f"<td>{html.escape(row.get('chunk_size', ''))}</td>"
        f"<td>{html.escape(row.get('entropy', ''))}</td>"
        f"<td>{html.escape(row.get('zero_ratio', ''))}</td>"
        f"<td>{html.escape(row.get('pixel_offset_hex', ''))} ({html.escape(row.get('pixel_x', ''))},{html.escape(row.get('pixel_y', ''))})</td>"
        f"<td>{html.escape(row.get('segment_offset_hex', ''))}</td>"
        f"<td><code>{html.escape(row.get('chunk_hex', ''))}</code></td>"
        f"<td>{html.escape(row.get('issues', ''))}</td>"
        "</tr>"
    )


def build_html(summary: dict[str, str], rows: list[dict[str, str]], output_dir: Path, title: str) -> str:
    payload = {"summary": summary, "scanRows": rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("scan.csv", output_dir / "scan.csv"),
        )
    )
    table_rows = "\n".join(render_row(row) for row in rows)
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root {{
  color-scheme: dark;
  --bg: #101316;
  --panel: #171d22;
  --line: #2f3942;
  --text: #edf3f6;
  --muted: #9caab3;
  --accent: #74d3ae;
  --ok: #78d98f;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  min-height: 100vh;
  background: var(--bg);
  color: var(--text);
  font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}}
.wrap {{ width: min(1600px, calc(100vw - 28px)); margin: 0 auto; }}
header {{
  border-bottom: 1px solid var(--line);
  background: #12171b;
  padding: 18px 0 14px;
}}
h1 {{ margin: 0; font-size: 21px; font-weight: 700; letter-spacing: 0; }}
main {{ padding: 16px 0 28px; display: grid; gap: 16px; }}
.stats {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 10px;
}}
.stat, .panel {{
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--panel);
  padding: 10px;
}}
.label, .muted {{ color: var(--muted); }}
.value {{ font-size: 24px; font-weight: 750; line-height: 1.05; margin-top: 4px; }}
.ok {{ color: var(--ok); }}
.panel {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; min-width: 1100px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
code {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; overflow-wrap: anywhere; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 10px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Segments</div><div class="value">{html.escape(summary['segments'])}</div></div>
    <div class="stat"><div class="label">Segments match</div><div class="value">{html.escape(summary['matched_segments'])}</div></div>
    <div class="stat"><div class="label">Rows scan</div><div class="value">{html.escape(summary['scan_rows'])}</div></div>
    <div class="stat"><div class="label">Issues</div><div class="value ok">{html.escape(summary['issue_rows'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div></section>
  <section class="panel">
    <table>
      <thead><tr><th>PCX</th><th>Size</th><th>Entropy</th><th>Zero</th><th>Pixel</th><th>Segment</th><th>Chunk</th><th>Issues</th></tr></thead>
      <tbody>{table_rows}</tbody>
    </table>
  </section>
</main>
<script>
const TEX_EXACT_CHUNK_SCAN = {data_json};
</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    comparisons: Path,
    *,
    chunk_sizes: list[int],
    min_entropy: float,
    max_zero_ratio: float,
    max_rows_per_segment_size: int,
    context_radius: int,
    max_positions_per_chunk: int,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    comparison_rows = read_rows(comparisons)
    scan_rows = build_scan_rows(
        comparison_rows,
        chunk_sizes=chunk_sizes,
        min_entropy=min_entropy,
        max_zero_ratio=max_zero_ratio,
        max_rows_per_segment_size=max_rows_per_segment_size,
        context_radius=context_radius,
        max_positions_per_chunk=max_positions_per_chunk,
    )
    summary = summary_row(
        comparison_rows,
        scan_rows,
        chunk_sizes=chunk_sizes,
        min_entropy=min_entropy,
        max_zero_ratio=max_zero_ratio,
        max_rows_per_segment_size=max_rows_per_segment_size,
    )
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "scan.csv", SCAN_FIELDNAMES, scan_rows)
    (output_dir / "index.html").write_text(build_html(summary, scan_rows, output_dir, title))
    return summary, scan_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Exhaustively scan exact .tex segments for high-signal pixel chunks.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--comparisons", type=Path, default=DEFAULT_COMPARISONS)
    parser.add_argument("--chunk-sizes", default="32,16")
    parser.add_argument("--min-entropy", type=float, default=2.5)
    parser.add_argument("--max-zero-ratio", type=float, default=0.25)
    parser.add_argument("--max-rows-per-segment-size", type=int, default=2048)
    parser.add_argument("--context-radius", type=int, default=16)
    parser.add_argument("--max-positions-per-chunk", type=int, default=8)
    parser.add_argument("--title", default="Lands of Lore II .tex Exact Chunk Scan")
    args = parser.parse_args()

    chunk_sizes = [int(value) for value in args.chunk_sizes.split(",") if value.strip()]
    summary, _rows = write_report(
        args.output,
        args.comparisons,
        chunk_sizes=chunk_sizes,
        min_entropy=args.min_entropy,
        max_zero_ratio=args.max_zero_ratio,
        max_rows_per_segment_size=args.max_rows_per_segment_size,
        context_radius=args.context_radius,
        max_positions_per_chunk=args.max_positions_per_chunk,
        title=args.title,
    )
    print(f"Segments: {summary['segments']}")
    print(f"Matched segments: {summary['matched_segments']}")
    print(f"Scan rows: {summary['scan_rows']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
