#!/usr/bin/env python3
"""Decode byte-exact raw-copy islands from .tex segments into partial textures."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import struct
from pathlib import Path

from PIL import Image


TARGET_SIZE = (1920, 1080)
DEFAULT_OUTPUT = Path("output/tex_partial_raw_decoder")
DEFAULT_CLUSTERS = Path("output/tex_exact_chunk_clusters/clusters.csv")
DEFAULT_COMPARISONS = Path("output/tex_exact_cdcache_compare/comparisons.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "decoded_textures",
    "fullhd_outputs",
    "raw_runs",
    "raw_bytes",
    "covered_pixels",
    "verified_pixels",
    "mismatched_pixels",
    "issue_rows",
]

MANIFEST_FIELDNAMES = [
    "archive",
    "archive_tag",
    "pcx_name",
    "native_width",
    "native_height",
    "raw_runs",
    "raw_bytes",
    "covered_pixels",
    "verified_pixels",
    "mismatched_pixels",
    "native_output_path",
    "fullhd_output_path",
    "fullhd_width",
    "fullhd_height",
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


def int_value(row: dict[str, str], field: str) -> int:
    raw = row.get(field, "")
    return int(raw) if raw else 0


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


def comparison_lookup(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    output = {}
    for row in rows:
        key = (row.get("archive", ""), row.get("pcx_name", ""))
        if key[0] and key[1]:
            output[key] = row
    return output


def grouped_clusters(rows: list[dict[str, str]]) -> dict[tuple[str, str], list[dict[str, str]]]:
    output: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in rows:
        if row.get("issues") or not row.get("pixel_start"):
            continue
        key = (row.get("archive", ""), row.get("pcx_name", ""))
        if key[0] and key[1]:
            output.setdefault(key, []).append(row)
    return output


def safe_stem(*parts: str) -> str:
    raw = "_".join(part for part in parts if part)
    return "".join(char if char.isalnum() or char in "-_." else "_" for char in raw).strip("_")


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    if not path_text:
        return ""
    path = Path(path_text)
    try:
        relative = path.relative_to(base_dir)
    except ValueError:
        relative = Path(os.path.relpath(path, base_dir))
    return relative.as_posix()


def load_indexed_source(path: Path) -> tuple[bytes, int, int, list[tuple[int, int, int]]]:
    with Image.open(path) as image:
        indexed = image if image.mode in {"1", "L", "P"} else image.convert("P")
        pixels = indexed.tobytes()
        palette_data = indexed.getpalette() or []
        palette: list[tuple[int, int, int]] = []
        for index in range(256):
            base = index * 3
            if base + 2 < len(palette_data):
                palette.append((palette_data[base], palette_data[base + 1], palette_data[base + 2]))
            else:
                palette.append((index, index, index))
        return pixels, indexed.width, indexed.height, palette


def to_fullhd(image: Image.Image) -> Image.Image:
    return image.resize(TARGET_SIZE, Image.Resampling.NEAREST)


def render_group(
    *,
    archive: Path,
    pcx_name: str,
    clusters: list[dict[str, str]],
    comparison: dict[str, str],
    payload_cache: dict[Path, bytes],
) -> tuple[Image.Image | None, dict[str, int], list[str]]:
    issues: list[str] = []
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

    native_path = Path(comparison.get("cdcache_native_path", ""))
    if not native_path.exists():
        issues.append("missing_cdcache_native_path")
        return None, {}, issues
    try:
        reference_pixels, width, height, palette = load_indexed_source(native_path)
    except Exception as exc:
        issues.append(f"cdcache_image_read_failed:{exc}")
        return None, {}, issues

    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    overlay_pixels = overlay.load()
    pixel_count = width * height
    covered: set[int] = set()
    verified = 0
    mismatched = 0
    raw_bytes = 0
    for cluster in clusters:
        pixel_start = int_value(cluster, "pixel_start")
        segment_start = int_value(cluster, "segment_start")
        run_bytes = int_value(cluster, "pixel_span_bytes")
        if run_bytes <= 0:
            run_bytes = int_value(cluster, "segment_span_bytes")
        segment_run = segment[segment_start : segment_start + run_bytes]
        raw_bytes += len(segment_run)
        if len(segment_run) != run_bytes:
            issues.append(f"cluster_{cluster.get('cluster_id', '')}_segment_run_truncated")
        for delta, value in enumerate(segment_run):
            offset = pixel_start + delta
            if offset < 0 or offset >= pixel_count:
                continue
            x = offset % width
            y = offset // width
            r, g, b = palette[value]
            overlay_pixels[x, y] = (r, g, b, 255)
            covered.add(offset)
            if offset < len(reference_pixels) and reference_pixels[offset] == value:
                verified += 1
            else:
                mismatched += 1

    stats = {
        "raw_runs": len(clusters),
        "raw_bytes": raw_bytes,
        "covered_pixels": len(covered),
        "verified_pixels": verified,
        "mismatched_pixels": mismatched,
    }
    if mismatched:
        issues.append(f"mismatched_pixels:{mismatched}")
    if not covered:
        issues.append("no_pixels_decoded")
    return overlay, stats, issues


def build_rows(clusters: Path, comparisons: Path, output_dir: Path) -> list[dict[str, str]]:
    cluster_rows = read_rows(clusters)
    comparison_rows = read_rows(comparisons)
    comparisons_by_key = comparison_lookup(comparison_rows)
    clusters_by_key = grouped_clusters(cluster_rows)
    payload_cache: dict[Path, bytes] = {}
    native_dir = output_dir / "native"
    fullhd_dir = output_dir / "fullhd"
    native_dir.mkdir(parents=True, exist_ok=True)
    fullhd_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, str]] = []

    for key, group in sorted(clusters_by_key.items()):
        archive_text, pcx_name = key
        archive = Path(archive_text)
        comparison = comparisons_by_key.get(key, {})
        overlay, stats, issues = render_group(
            archive=archive,
            pcx_name=pcx_name,
            clusters=group,
            comparison=comparison,
            payload_cache=payload_cache,
        )
        if overlay is None:
            width = 0
            height = 0
            native_output_path = ""
            fullhd_output_path = ""
            fullhd_width = 0
            fullhd_height = 0
        else:
            width, height = overlay.size
            stem = safe_stem(Path(archive_text).stem, pcx_name)
            native_output = native_dir / f"{stem}_partial_raw_decode.png"
            fullhd_output = fullhd_dir / f"{stem}_partial_raw_decode_fullhd.png"
            overlay.save(native_output)
            fullhd = to_fullhd(overlay)
            fullhd.save(fullhd_output)
            native_output_path = native_output.as_posix()
            fullhd_output_path = fullhd_output.as_posix()
            fullhd_width, fullhd_height = fullhd.size
            if fullhd.size != TARGET_SIZE:
                issues.append("fullhd_size_mismatch")

        rows.append(
            {
                "archive": archive_text,
                "archive_tag": Path(archive_text).stem.upper(),
                "pcx_name": pcx_name,
                "native_width": str(width),
                "native_height": str(height),
                "raw_runs": str(stats.get("raw_runs", 0)),
                "raw_bytes": str(stats.get("raw_bytes", 0)),
                "covered_pixels": str(stats.get("covered_pixels", 0)),
                "verified_pixels": str(stats.get("verified_pixels", 0)),
                "mismatched_pixels": str(stats.get("mismatched_pixels", 0)),
                "native_output_path": native_output_path,
                "fullhd_output_path": fullhd_output_path,
                "fullhd_width": str(fullhd_width),
                "fullhd_height": str(fullhd_height),
                "issues": ";".join(issues),
            }
        )
    return rows


def summary_row(rows: list[dict[str, str]]) -> dict[str, str]:
    fullhd_rows = [
        row
        for row in rows
        if (row.get("fullhd_width"), row.get("fullhd_height")) == (str(TARGET_SIZE[0]), str(TARGET_SIZE[1]))
    ]
    return {
        "scope": "total",
        "decoded_textures": str(len(rows)),
        "fullhd_outputs": str(len(fullhd_rows)),
        "raw_runs": str(sum(int_value(row, "raw_runs") for row in rows)),
        "raw_bytes": str(sum(int_value(row, "raw_bytes") for row in rows)),
        "covered_pixels": str(sum(int_value(row, "covered_pixels") for row in rows)),
        "verified_pixels": str(sum(int_value(row, "verified_pixels") for row in rows)),
        "mismatched_pixels": str(sum(int_value(row, "mismatched_pixels") for row in rows)),
        "issue_rows": str(sum(1 for row in rows if row.get("issues"))),
    }


def render_card(row: dict[str, str], output_dir: Path) -> str:
    image = html.escape(relative_href(row.get("fullhd_output_path", ""), output_dir))
    return f"""
<article class="card">
  <a class="preview" href="{image}"><img src="{image}" loading="lazy" decoding="async" alt=""></a>
  <div class="card-body">
    <div class="card-title">{html.escape(row.get('pcx_name', ''))}</div>
    <div class="muted">{html.escape(row.get('raw_runs', ''))} runs - {html.escape(row.get('raw_bytes', ''))} bytes - {html.escape(row.get('mismatched_pixels', ''))} mismatches</div>
    <a href="{image}">Full HD</a>
  </div>
</article>"""


def build_html(summary: dict[str, str], rows: list[dict[str, str]], output_dir: Path, title: str) -> str:
    payload = {"summary": summary, "textures": rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    cards = "\n".join(render_card(row, output_dir) for row in rows)
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("manifest.csv", output_dir / "manifest.csv"),
        )
    )
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
.sub {{ color: var(--muted); margin-top: 4px; }}
main {{ padding: 16px 0 28px; display: grid; gap: 16px; }}
.stats, .cards {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 10px;
}}
.stat, .card, .panel {{
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--panel);
}}
.stat, .panel {{ padding: 10px; }}
.label, .muted {{ color: var(--muted); }}
.value {{ font-size: 24px; font-weight: 750; line-height: 1.05; margin-top: 4px; }}
.ok {{ color: var(--ok); }}
.preview {{
  display: block;
  aspect-ratio: 16 / 9;
  background: #060708;
  border-bottom: 1px solid var(--line);
  overflow: hidden;
}}
.preview img {{ width: 100%; height: 100%; object-fit: contain; image-rendering: pixelated; }}
.card-body {{ padding: 10px; display: grid; gap: 6px; }}
.card-title {{ font-weight: 700; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 10px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Decodeur partiel raw-copy base sur les runs byte-exact du corpus .tex.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Textures</div><div class="value">{html.escape(summary['decoded_textures'])}</div></div>
    <div class="stat"><div class="label">Runs</div><div class="value">{html.escape(summary['raw_runs'])}</div></div>
    <div class="stat"><div class="label">Bytes</div><div class="value">{html.escape(summary['raw_bytes'])}</div></div>
    <div class="stat"><div class="label">Mismatches</div><div class="value ok">{html.escape(summary['mismatched_pixels'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div></section>
  <section class="cards">{cards}</section>
</main>
<script>
const TEX_PARTIAL_RAW_DECODER = {data_json};
</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    clusters: Path,
    comparisons: Path,
    *,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = build_rows(clusters, comparisons, output_dir)
    summary = summary_row(rows)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "manifest.csv", MANIFEST_FIELDNAMES, rows)
    (output_dir / "index.html").write_text(build_html(summary, rows, output_dir, title))
    return summary, rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Decode byte-exact raw-copy islands from .tex segments.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--clusters", type=Path, default=DEFAULT_CLUSTERS)
    parser.add_argument("--comparisons", type=Path, default=DEFAULT_COMPARISONS)
    parser.add_argument("--title", default="Lands of Lore II .tex Partial Raw Decoder")
    args = parser.parse_args()

    summary, _rows = write_report(
        args.output,
        args.clusters,
        args.comparisons,
        title=args.title,
    )
    print(f"Decoded textures: {summary['decoded_textures']}")
    print(f"Full HD outputs: {summary['fullhd_outputs']}")
    print(f"Raw runs: {summary['raw_runs']}")
    print(f"Raw bytes: {summary['raw_bytes']}")
    print(f"Mismatched pixels: {summary['mismatched_pixels']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
