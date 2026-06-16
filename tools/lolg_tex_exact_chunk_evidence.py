#!/usr/bin/env python3
"""Extract direct chunk-match evidence between exact .tex segments and CDCACHE pixels."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import struct
from pathlib import Path

from PIL import Image


DEFAULT_OUTPUT = Path("output/tex_exact_chunk_evidence")
DEFAULT_COMPARISONS = Path("output/tex_exact_cdcache_compare/comparisons.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "segments",
    "matched_segments",
    "match_rows",
    "chunks_32_rows",
    "chunks_16_rows",
    "chunks_8_rows",
    "issue_rows",
]

MATCH_FIELDNAMES = [
    "archive",
    "archive_tag",
    "pcx_name",
    "chunk_size",
    "match_index",
    "pixel_offset",
    "pixel_offset_hex",
    "pixel_x",
    "pixel_y",
    "segment_offset",
    "segment_offset_hex",
    "extra_segment_occurrences",
    "pixel_hex",
    "segment_context_start",
    "segment_context_start_hex",
    "segment_context_hex",
    "pixel_context_start",
    "pixel_context_start_hex",
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


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    if not path_text:
        return ""
    path = Path(path_text)
    try:
        relative = path.relative_to(base_dir)
    except ValueError:
        relative = Path(os.path.relpath(path, base_dir))
    return relative.as_posix()


def context(data: bytes, offset: int, chunk_size: int, radius: int) -> tuple[int, bytes]:
    start = max(0, offset - radius)
    end = min(len(data), offset + chunk_size + radius)
    return start, data[start:end]


def count_extra_occurrences(data: bytes, chunk: bytes, first_offset: int, limit: int = 8) -> int:
    count = 0
    offset = first_offset + 1
    while count < limit:
        found = data.find(chunk, offset)
        if found < 0:
            return count
        count += 1
        offset = found + 1
    return count


def sampled_matches(
    *,
    archive: str,
    archive_tag: str,
    pcx_name: str,
    segment: bytes,
    pixels: bytes,
    width: int,
    chunk_size: int,
    step: int,
    context_radius: int,
    max_matches: int,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if len(pixels) < chunk_size or len(segment) < chunk_size:
        return rows

    match_index = 0
    for pixel_offset in range(0, len(pixels) - chunk_size + 1, step):
        chunk = pixels[pixel_offset : pixel_offset + chunk_size]
        if len(set(chunk)) <= 1:
            continue
        segment_offset = segment.find(chunk)
        if segment_offset < 0:
            continue

        segment_context_start, segment_context = context(
            segment,
            segment_offset,
            chunk_size,
            context_radius,
        )
        pixel_context_start, pixel_context = context(
            pixels,
            pixel_offset,
            chunk_size,
            context_radius,
        )
        x = pixel_offset % width if width else 0
        y = pixel_offset // width if width else 0
        rows.append(
            {
                "archive": archive,
                "archive_tag": archive_tag,
                "pcx_name": pcx_name,
                "chunk_size": str(chunk_size),
                "match_index": str(match_index),
                "pixel_offset": str(pixel_offset),
                "pixel_offset_hex": f"0x{pixel_offset:08x}",
                "pixel_x": str(x),
                "pixel_y": str(y),
                "segment_offset": str(segment_offset),
                "segment_offset_hex": f"0x{segment_offset:08x}",
                "extra_segment_occurrences": str(count_extra_occurrences(segment, chunk, segment_offset)),
                "pixel_hex": chunk.hex(),
                "segment_context_start": str(segment_context_start),
                "segment_context_start_hex": f"0x{segment_context_start:08x}",
                "segment_context_hex": segment_context.hex(),
                "pixel_context_start": str(pixel_context_start),
                "pixel_context_start_hex": f"0x{pixel_context_start:08x}",
                "pixel_context_hex": pixel_context.hex(),
                "issues": "",
            }
        )
        match_index += 1
        if match_index >= max_matches:
            break
    return rows


def build_rows(
    comparison_rows: list[dict[str, str]],
    *,
    chunk_sizes: list[int],
    step: int,
    context_radius: int,
    max_matches_per_size: int,
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
        height = 0
        native_path = Path(comparison.get("cdcache_native_path", ""))
        if not native_path.exists():
            issues.append("missing_cdcache_native_path")
        else:
            try:
                pixels, width, height = load_pixels(native_path)
            except Exception as exc:
                issues.append(f"cdcache_image_read_failed:{exc}")
        if issues:
            rows.append(
                {
                    "archive": comparison.get("archive", ""),
                    "archive_tag": comparison.get("archive_tag", ""),
                    "pcx_name": comparison.get("pcx_name", ""),
                    "chunk_size": "",
                    "match_index": "",
                    "pixel_offset": "",
                    "pixel_offset_hex": "",
                    "pixel_x": "",
                    "pixel_y": "",
                    "segment_offset": "",
                    "segment_offset_hex": "",
                    "extra_segment_occurrences": "",
                    "pixel_hex": "",
                    "segment_context_start": "",
                    "segment_context_start_hex": "",
                    "segment_context_hex": "",
                    "pixel_context_start": "",
                    "pixel_context_start_hex": "",
                    "pixel_context_hex": "",
                    "issues": ";".join(issues),
                }
            )
            continue

        for chunk_size in chunk_sizes:
            rows.extend(
                sampled_matches(
                    archive=comparison.get("archive", ""),
                    archive_tag=comparison.get("archive_tag", ""),
                    pcx_name=comparison.get("pcx_name", ""),
                    segment=segment,
                    pixels=pixels,
                    width=width,
                    chunk_size=chunk_size,
                    step=step,
                    context_radius=context_radius,
                    max_matches=max_matches_per_size,
                )
            )
    return rows


def summary_row(comparison_rows: list[dict[str, str]], match_rows: list[dict[str, str]]) -> dict[str, str]:
    issue_rows = sum(1 for row in match_rows if row.get("issues"))
    matched_segments = {
        (row["archive"], row["pcx_name"])
        for row in match_rows
        if row.get("segment_offset") and not row.get("issues")
    }
    return {
        "scope": "total",
        "segments": str(len(comparison_rows)),
        "matched_segments": str(len(matched_segments)),
        "match_rows": str(sum(1 for row in match_rows if row.get("segment_offset"))),
        "chunks_32_rows": str(sum(1 for row in match_rows if row.get("chunk_size") == "32")),
        "chunks_16_rows": str(sum(1 for row in match_rows if row.get("chunk_size") == "16")),
        "chunks_8_rows": str(sum(1 for row in match_rows if row.get("chunk_size") == "8")),
        "issue_rows": str(issue_rows),
    }


def render_match(row: dict[str, str]) -> str:
    return (
        "<tr>"
        f"<td>{html.escape(row.get('pcx_name', ''))}</td>"
        f"<td>{html.escape(row.get('archive_tag', ''))}</td>"
        f"<td>{html.escape(row.get('chunk_size', ''))}</td>"
        f"<td>{html.escape(row.get('pixel_offset_hex', ''))}</td>"
        f"<td>{html.escape(row.get('pixel_x', ''))},{html.escape(row.get('pixel_y', ''))}</td>"
        f"<td>{html.escape(row.get('segment_offset_hex', ''))}</td>"
        f"<td>{html.escape(row.get('extra_segment_occurrences', ''))}</td>"
        f"<td><code>{html.escape(row.get('pixel_hex', ''))}</code></td>"
        f"<td>{html.escape(row.get('issues', ''))}</td>"
        "</tr>"
    )


def build_html(summary: dict[str, str], rows: list[dict[str, str]], output_dir: Path, title: str) -> str:
    payload = {"summary": summary, "matches": rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("matches.csv", output_dir / "matches.csv"),
        )
    )
    table_rows = "\n".join(render_match(row) for row in rows if row.get("segment_offset") or row.get("issues"))
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
.stat {{
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--panel);
  padding: 10px;
}}
.label, .muted {{ color: var(--muted); }}
.value {{ font-size: 24px; font-weight: 750; line-height: 1.05; margin-top: 4px; }}
.ok {{ color: var(--ok); }}
.panel {{
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--panel);
  padding: 12px;
  overflow-x: auto;
}}
table {{ width: 100%; border-collapse: collapse; min-width: 1180px; }}
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
    <div class="stat"><div class="label">Segments avec chunk</div><div class="value">{html.escape(summary['matched_segments'])}</div></div>
    <div class="stat"><div class="label">Rows match</div><div class="value">{html.escape(summary['match_rows'])}</div></div>
    <div class="stat"><div class="label">Issues</div><div class="value ok">{html.escape(summary['issue_rows'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div></section>
  <section class="panel">
    <table>
      <thead><tr><th>PCX</th><th>Archive</th><th>Chunk</th><th>Pixel offset</th><th>X,Y</th><th>Segment offset</th><th>Extra occ.</th><th>Hex</th><th>Issues</th></tr></thead>
      <tbody>{table_rows}</tbody>
    </table>
  </section>
</main>
<script>
const TEX_EXACT_CHUNK_EVIDENCE = {data_json};
</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    comparisons_path: Path,
    *,
    chunk_sizes: list[int],
    step: int,
    context_radius: int,
    max_matches_per_size: int,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    comparison_rows = read_rows(comparisons_path)
    rows = build_rows(
        comparison_rows,
        chunk_sizes=chunk_sizes,
        step=step,
        context_radius=context_radius,
        max_matches_per_size=max_matches_per_size,
    )
    summary = summary_row(comparison_rows, rows)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "matches.csv", MATCH_FIELDNAMES, rows)
    (output_dir / "index.html").write_text(build_html(summary, rows, output_dir, title))
    return summary, rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract exact .tex/CDCACHE direct chunk evidence.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--comparisons", type=Path, default=DEFAULT_COMPARISONS)
    parser.add_argument("--chunk-sizes", default="32,16,8")
    parser.add_argument("--step", type=int, default=64)
    parser.add_argument("--context-radius", type=int, default=16)
    parser.add_argument("--max-matches-per-size", type=int, default=128)
    parser.add_argument("--title", default="Lands of Lore II .tex Exact Chunk Evidence")
    args = parser.parse_args()

    chunk_sizes = [int(value) for value in args.chunk_sizes.split(",") if value.strip()]
    summary, _rows = write_report(
        args.output,
        args.comparisons,
        chunk_sizes=chunk_sizes,
        step=args.step,
        context_radius=args.context_radius,
        max_matches_per_size=args.max_matches_per_size,
        title=args.title,
    )
    print(f"Segments: {summary['segments']}")
    print(f"Matched segments: {summary['matched_segments']}")
    print(f"Match rows: {summary['match_rows']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
