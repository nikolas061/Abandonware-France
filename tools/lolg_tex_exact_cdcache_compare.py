#!/usr/bin/env python3
"""Compare exact .tex material segments with decoded CDCACHE pixel exports."""

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


DEFAULT_OUTPUT = Path("output/tex_exact_cdcache_compare")
DEFAULT_QUEUE = Path("output/tex_material_decoder_queue/queue.csv")
DEFAULT_CDCACHE_MANIFEST = Path("output/cdcache_textures_all_tiled_tiles/manifest.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "exact_segments",
    "segments_with_32_byte_match",
    "segments_with_16_byte_match",
    "avg_histogram_intersection",
    "issue_rows",
]

COMPARISON_FIELDNAMES = [
    "archive",
    "archive_tag",
    "pcx_name",
    "texture_segment_index",
    "texture_body_offset",
    "texture_body_offset_hex",
    "texture_body_first_word",
    "texture_segment_size",
    "segment_entropy",
    "cdcache_width",
    "cdcache_height",
    "cdcache_pixels",
    "cdcache_cache_index",
    "cdcache_data_offset_hex",
    "cdcache_native_path",
    "cdcache_entropy",
    "histogram_intersection",
    "best_prefix_match_offset",
    "best_prefix_match_len",
    "sampled_chunks",
    "chunks_64_found",
    "chunks_32_found",
    "chunks_16_found",
    "chunks_8_found",
    "first_64_match_offset",
    "first_32_match_offset",
    "first_16_match_offset",
    "segment_first_32_hex",
    "cdcache_first_32_hex",
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


def normalize_name(value: str) -> str:
    return value.rsplit("\\", 1)[-1].rsplit("/", 1)[-1].lower()


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    if not path_text:
        return ""
    path = Path(path_text)
    try:
        relative = path.relative_to(base_dir)
    except ValueError:
        relative = Path(os.path.relpath(path, base_dir))
    return relative.as_posix()


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


def histogram_intersection(left: bytes, right: bytes) -> float:
    if not left or not right:
        return 0.0
    left_counts = Counter(left)
    right_counts = Counter(right)
    left_total = len(left)
    right_total = len(right)
    keys = set(left_counts) | set(right_counts)
    return sum(min(left_counts[key] / left_total, right_counts[key] / right_total) for key in keys)


def longest_prefix_at(segment: bytes, pixels: bytes, max_offset: int = 256) -> tuple[int, int]:
    best_offset = 0
    best_len = 0
    limit = min(max_offset, max(0, len(segment) - 1))
    for offset in range(limit + 1):
        match_len = 0
        max_len = min(len(segment) - offset, len(pixels), 512)
        while match_len < max_len and segment[offset + match_len] == pixels[match_len]:
            match_len += 1
        if match_len > best_len:
            best_offset = offset
            best_len = match_len
    return best_offset, best_len


def sampled_chunk_matches(segment: bytes, pixels: bytes, chunk_size: int, step: int = 64) -> tuple[int, int]:
    found = 0
    first_offset = -1
    if len(pixels) < chunk_size:
        return 0, -1
    for start in range(0, len(pixels) - chunk_size + 1, step):
        chunk = pixels[start : start + chunk_size]
        if len(set(chunk)) <= 1:
            continue
        match = segment.find(chunk)
        if match >= 0:
            found += 1
            if first_offset < 0:
                first_offset = match
    return found, first_offset


def load_pixels(path: Path) -> tuple[bytes, int, int, str]:
    with Image.open(path) as image:
        if image.mode not in {"1", "L", "P"}:
            image = image.convert("L")
        return image.tobytes(), image.width, image.height, image.mode


def cdcache_lookup(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    lookup = {}
    for row in rows:
        key = (row.get("matched_texture_archives", ""), row.get("base_name", "").lower())
        if key[0] and key[1]:
            lookup[key] = row
    return lookup


def exact_segment_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str, str, str]] = set()
    output = []
    for row in rows:
        if row.get("coverage_status") != "exact":
            continue
        key = (
            row.get("archive", ""),
            row.get("normalized_pcx_name", ""),
            row.get("texture_segment_index", ""),
            row.get("texture_body_offset", ""),
        )
        if key in seen:
            continue
        seen.add(key)
        output.append(row)
    return output


def compare_rows(queue_rows: list[dict[str, str]], cdcache_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    cache = cdcache_lookup(cdcache_rows)
    payload_cache: dict[Path, bytes] = {}
    rows: list[dict[str, str]] = []
    for row in exact_segment_rows(queue_rows):
        issues: list[str] = []
        archive = Path(row.get("archive", ""))
        if archive not in payload_cache:
            try:
                _file_id, payload_cache[archive] = read_mix_entry(archive, 2)
            except Exception as exc:
                payload_cache[archive] = b""
                issues.append(f"archive_read_failed:{exc}")
        payload = payload_cache[archive]
        body_offset = int(row.get("texture_body_offset") or 0)
        segment_size = int(row.get("texture_segment_size") or 0)
        segment = payload[body_offset : body_offset + segment_size]
        if len(segment) != segment_size:
            issues.append("segment_size_mismatch")

        cdcache_row = cache.get((row.get("archive", ""), normalize_name(row.get("pcx_name", ""))), {})
        pixels = b""
        image_width = 0
        image_height = 0
        if not cdcache_row:
            issues.append("missing_cdcache_manifest_row")
        else:
            native_path = Path(cdcache_row.get("native_path", ""))
            if not native_path.exists():
                issues.append("missing_cdcache_native_path")
            else:
                try:
                    pixels, image_width, image_height, _mode = load_pixels(native_path)
                except Exception as exc:
                    issues.append(f"cdcache_image_read_failed:{exc}")

        best_offset, best_len = longest_prefix_at(segment, pixels)
        chunks_64, first_64 = sampled_chunk_matches(segment, pixels, 64)
        chunks_32, first_32 = sampled_chunk_matches(segment, pixels, 32)
        chunks_16, first_16 = sampled_chunk_matches(segment, pixels, 16)
        chunks_8, _first_8 = sampled_chunk_matches(segment, pixels, 8)
        sampled_chunks = len(range(0, max(0, len(pixels) - 64 + 1), 64)) if len(pixels) >= 64 else 0

        rows.append(
            {
                "archive": row.get("archive", ""),
                "archive_tag": row.get("archive_tag", ""),
                "pcx_name": row.get("normalized_pcx_name", ""),
                "texture_segment_index": row.get("texture_segment_index", ""),
                "texture_body_offset": row.get("texture_body_offset", ""),
                "texture_body_offset_hex": row.get("texture_body_offset_hex", ""),
                "texture_body_first_word": row.get("texture_body_first_word", ""),
                "texture_segment_size": str(segment_size),
                "segment_entropy": f"{entropy(segment):.4f}",
                "cdcache_width": str(image_width or cdcache_row.get("width", "")),
                "cdcache_height": str(image_height or cdcache_row.get("height", "")),
                "cdcache_pixels": str(len(pixels)),
                "cdcache_cache_index": cdcache_row.get("cache_index", ""),
                "cdcache_data_offset_hex": cdcache_row.get("data_offset_hex", ""),
                "cdcache_native_path": cdcache_row.get("native_path", ""),
                "cdcache_entropy": f"{entropy(pixels):.4f}",
                "histogram_intersection": f"{histogram_intersection(segment, pixels):.6f}",
                "best_prefix_match_offset": str(best_offset),
                "best_prefix_match_len": str(best_len),
                "sampled_chunks": str(sampled_chunks),
                "chunks_64_found": str(chunks_64),
                "chunks_32_found": str(chunks_32),
                "chunks_16_found": str(chunks_16),
                "chunks_8_found": str(chunks_8),
                "first_64_match_offset": str(first_64 if first_64 >= 0 else ""),
                "first_32_match_offset": str(first_32 if first_32 >= 0 else ""),
                "first_16_match_offset": str(first_16 if first_16 >= 0 else ""),
                "segment_first_32_hex": segment[:32].hex(),
                "cdcache_first_32_hex": pixels[:32].hex(),
                "issues": ";".join(issues),
            }
        )
    return rows


def summary_row(rows: list[dict[str, str]]) -> dict[str, str]:
    intersections = [float(row["histogram_intersection"]) for row in rows if row["histogram_intersection"]]
    return {
        "scope": "total",
        "exact_segments": str(len(rows)),
        "segments_with_32_byte_match": str(sum(1 for row in rows if int(row["chunks_32_found"]) > 0)),
        "segments_with_16_byte_match": str(sum(1 for row in rows if int(row["chunks_16_found"]) > 0)),
        "avg_histogram_intersection": f"{sum(intersections) / len(intersections):.6f}" if intersections else "0.000000",
        "issue_rows": str(sum(1 for row in rows if row["issues"])),
    }


def render_row(row: dict[str, str], output_dir: Path) -> str:
    native = row.get("cdcache_native_path", "")
    native_link = ""
    if native:
        href = html.escape(relative_href(native, output_dir))
        native_link = f'<a href="{href}">native</a>'
    return (
        "<tr>"
        f"<td>{html.escape(row['pcx_name'])}</td>"
        f"<td>{html.escape(row['archive_tag'])}</td>"
        f"<td>{html.escape(row['texture_body_first_word'])}</td>"
        f"<td>{html.escape(row['texture_segment_size'])}</td>"
        f"<td>{html.escape(row['cdcache_width'])}x{html.escape(row['cdcache_height'])}</td>"
        f"<td>{html.escape(row['histogram_intersection'])}</td>"
        f"<td>{html.escape(row['chunks_64_found'])}/{html.escape(row['chunks_32_found'])}/{html.escape(row['chunks_16_found'])}</td>"
        f"<td>{html.escape(row['best_prefix_match_len'])}@{html.escape(row['best_prefix_match_offset'])}</td>"
        f"<td>{native_link}</td>"
        "</tr>"
    )


def build_html(summary: dict[str, str], rows: list[dict[str, str]], output_dir: Path, title: str) -> str:
    payload = {"summary": summary, "comparisons": rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("comparisons.csv", output_dir / "comparisons.csv"),
        )
    )
    table_rows = "\n".join(render_row(row, output_dir) for row in rows)
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
table {{ width: 100%; border-collapse: collapse; min-width: 920px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
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
    <div class="stat"><div class="label">Segments exacts</div><div class="value">{html.escape(summary['exact_segments'])}</div></div>
    <div class="stat"><div class="label">Chunks 32B directs</div><div class="value">{html.escape(summary['segments_with_32_byte_match'])}</div></div>
    <div class="stat"><div class="label">Histogramme moyen</div><div class="value">{html.escape(summary['avg_histogram_intersection'])}</div></div>
    <div class="stat"><div class="label">Issues</div><div class="value ok">{html.escape(summary['issue_rows'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div></section>
  <section class="panel">
    <table>
      <thead><tr><th>PCX</th><th>Archive</th><th>Prefixe</th><th>Segment</th><th>CDCACHE</th><th>Hist.</th><th>Chunks 64/32/16</th><th>Prefix match</th><th>Lien</th></tr></thead>
      <tbody>{table_rows}</tbody>
    </table>
  </section>
</main>
<script>
const TEX_EXACT_CDCACHE_COMPARE = {data_json};
</script>
</body>
</html>
"""


def write_report(output_dir: Path, queue: Path, cdcache_manifest: Path, title: str) -> tuple[dict[str, str], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = compare_rows(read_rows(queue), read_rows(cdcache_manifest))
    summary = summary_row(rows)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "comparisons.csv", COMPARISON_FIELDNAMES, rows)
    (output_dir / "index.html").write_text(build_html(summary, rows, output_dir, title))
    return summary, rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare exact .tex segments to CDCACHE decoded pixels.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--queue", type=Path, default=DEFAULT_QUEUE)
    parser.add_argument("--cdcache-manifest", type=Path, default=DEFAULT_CDCACHE_MANIFEST)
    parser.add_argument("--title", default="Lands of Lore II .tex / CDCACHE Exact Compare")
    args = parser.parse_args()

    summary, _rows = write_report(args.output, args.queue, args.cdcache_manifest, args.title)
    print(f"Exact segments: {summary['exact_segments']}")
    print(f"32-byte direct matches: {summary['segments_with_32_byte_match']}")
    print(f"16-byte direct matches: {summary['segments_with_16_byte_match']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"HTML: {args.output / 'index.html'}")
    if summary["issue_rows"] != "0":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
