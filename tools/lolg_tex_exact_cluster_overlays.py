#!/usr/bin/env python3
"""Render Full HD overlays from clustered exact .tex/CDCACHE decoder runs."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
from collections import Counter
from pathlib import Path

from PIL import Image


TARGET_SIZE = (1920, 1080)
DEFAULT_OUTPUT = Path("output/tex_exact_cluster_overlays")
DEFAULT_CLUSTERS = Path("output/tex_exact_chunk_clusters/clusters.csv")
DEFAULT_COMPARISONS = Path("output/tex_exact_cdcache_compare/comparisons.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "overlays",
    "fullhd_overlays",
    "matched_segments",
    "clusters",
    "strong_clusters",
    "covered_pixels",
    "longest_span",
    "issue_rows",
]

OVERLAY_FIELDNAMES = [
    "archive",
    "archive_tag",
    "pcx_name",
    "native_width",
    "native_height",
    "clusters",
    "strong_clusters",
    "covered_pixels",
    "covered_ratio",
    "longest_span",
    "native_overlay_path",
    "fullhd_overlay_path",
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


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    if not path_text:
        return ""
    path = Path(path_text)
    try:
        relative = path.relative_to(base_dir)
    except ValueError:
        relative = Path(os.path.relpath(path, base_dir))
    return relative.as_posix()


def safe_stem(*parts: str) -> str:
    raw = "_".join(part for part in parts if part)
    return "".join(char if char.isalnum() or char in "-_." else "_" for char in raw).strip("_")


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


def cluster_offsets(cluster: dict[str, str], pixel_count: int) -> range:
    start = int_value(cluster, "pixel_start")
    span = int_value(cluster, "pixel_span_bytes")
    if span <= 0:
        chunk_size = int_value(cluster, "chunk_size")
        end = int_value(cluster, "pixel_end")
        span = end - start + chunk_size
    bounded_start = max(0, start)
    bounded_end = min(pixel_count, start + max(0, span))
    return range(bounded_start, bounded_end)


def render_overlay(
    *,
    image: Image.Image,
    clusters: list[dict[str, str]],
) -> tuple[Image.Image, int]:
    source = image.convert("RGBA")
    overlay = Image.new("RGBA", source.size, (0, 0, 0, 0))
    source_pixels = source.load()
    overlay_pixels = overlay.load()
    covered: set[int] = set()
    width, height = source.size
    pixel_count = width * height
    for cluster in clusters:
        for offset in cluster_offsets(cluster, pixel_count):
            x = offset % width
            y = offset // width
            r, g, b, _a = source_pixels[x, y]
            overlay_pixels[x, y] = (r, g, b, 255)
            covered.add(offset)
    return overlay, len(covered)


def to_fullhd(image: Image.Image) -> Image.Image:
    return image.resize(TARGET_SIZE, Image.Resampling.NEAREST)


def build_rows(clusters: Path, comparisons: Path, output_dir: Path) -> list[dict[str, str]]:
    cluster_rows = read_rows(clusters)
    comparison_rows = read_rows(comparisons)
    comparisons_by_key = comparison_lookup(comparison_rows)
    clusters_by_key = grouped_clusters(cluster_rows)
    rows: list[dict[str, str]] = []
    native_dir = output_dir / "native"
    fullhd_dir = output_dir / "fullhd"
    native_dir.mkdir(parents=True, exist_ok=True)
    fullhd_dir.mkdir(parents=True, exist_ok=True)

    for key, group in sorted(clusters_by_key.items()):
        archive, pcx_name = key
        issues: list[str] = []
        comparison = comparisons_by_key.get(key, {})
        native_path = Path(comparison.get("cdcache_native_path", ""))
        if not native_path.exists():
            issues.append("missing_cdcache_native_path")
            width = 0
            height = 0
            covered = 0
            native_overlay_path = ""
            fullhd_overlay_path = ""
            fullhd_width = 0
            fullhd_height = 0
        else:
            with Image.open(native_path) as source:
                overlay, covered = render_overlay(image=source, clusters=group)
            width, height = overlay.size
            stem = safe_stem(Path(archive).stem, pcx_name)
            native_output = native_dir / f"{stem}_cluster_overlay.png"
            fullhd_output = fullhd_dir / f"{stem}_cluster_overlay_fullhd.png"
            overlay.save(native_output)
            fullhd = to_fullhd(overlay)
            fullhd.save(fullhd_output)
            native_overlay_path = native_output.as_posix()
            fullhd_overlay_path = fullhd_output.as_posix()
            fullhd_width, fullhd_height = fullhd.size
            if fullhd.size != TARGET_SIZE:
                issues.append("fullhd_size_mismatch")

        class_counts = Counter(row.get("cluster_class", "") for row in group)
        longest_span = max((int_value(row, "pixel_span_bytes") for row in group), default=0)
        rows.append(
            {
                "archive": archive,
                "archive_tag": Path(archive).stem.upper(),
                "pcx_name": pcx_name,
                "native_width": str(width),
                "native_height": str(height),
                "clusters": str(len(group)),
                "strong_clusters": str(class_counts.get("strong", 0)),
                "covered_pixels": str(covered),
                "covered_ratio": f"{covered / (width * height):.6f}" if width and height else "0.000000",
                "longest_span": str(longest_span),
                "native_overlay_path": native_overlay_path,
                "fullhd_overlay_path": fullhd_overlay_path,
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
        "overlays": str(len(rows)),
        "fullhd_overlays": str(len(fullhd_rows)),
        "matched_segments": str(len({(row["archive"], row["pcx_name"]) for row in rows})),
        "clusters": str(sum(int_value(row, "clusters") for row in rows)),
        "strong_clusters": str(sum(int_value(row, "strong_clusters") for row in rows)),
        "covered_pixels": str(sum(int_value(row, "covered_pixels") for row in rows)),
        "longest_span": str(max((int_value(row, "longest_span") for row in rows), default=0)),
        "issue_rows": str(sum(1 for row in rows if row.get("issues"))),
    }


def render_card(row: dict[str, str], output_dir: Path) -> str:
    image = html.escape(relative_href(row.get("fullhd_overlay_path", ""), output_dir))
    return f"""
<article class="card">
  <a class="preview" href="{image}"><img src="{image}" loading="lazy" decoding="async" alt=""></a>
  <div class="card-body">
    <div class="card-title">{html.escape(row.get('pcx_name', ''))}</div>
    <div class="muted">{html.escape(row.get('archive_tag', ''))} - {html.escape(row.get('clusters', ''))} runs - {html.escape(row.get('covered_pixels', ''))} pixels</div>
    <a href="{image}">Full HD</a>
  </div>
</article>"""


def build_html(summary: dict[str, str], rows: list[dict[str, str]], output_dir: Path, title: str) -> str:
    payload = {"summary": summary, "overlays": rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    cards = "\n".join(render_card(row, output_dir) for row in rows)
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("overlays.csv", output_dir / "overlays.csv"),
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
    <div class="sub">Runs .tex directement alignes sur les pixels CDCACHE, rendus en overlays Full HD.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Overlays</div><div class="value">{html.escape(summary['overlays'])}</div></div>
    <div class="stat"><div class="label">Clusters</div><div class="value">{html.escape(summary['clusters'])}</div></div>
    <div class="stat"><div class="label">Strong</div><div class="value">{html.escape(summary['strong_clusters'])}</div></div>
    <div class="stat"><div class="label">Pixels couverts</div><div class="value">{html.escape(summary['covered_pixels'])}</div></div>
    <div class="stat"><div class="label">Issues</div><div class="value ok">{html.escape(summary['issue_rows'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div></section>
  <section class="cards">{cards}</section>
</main>
<script>
const TEX_EXACT_CLUSTER_OVERLAYS = {data_json};
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
    write_csv(output_dir / "overlays.csv", OVERLAY_FIELDNAMES, rows)
    (output_dir / "index.html").write_text(build_html(summary, rows, output_dir, title))
    return summary, rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Render Full HD overlays from exact .tex chunk clusters.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--clusters", type=Path, default=DEFAULT_CLUSTERS)
    parser.add_argument("--comparisons", type=Path, default=DEFAULT_COMPARISONS)
    parser.add_argument("--title", default="Lands of Lore II .tex Exact Cluster Overlays")
    args = parser.parse_args()

    summary, _rows = write_report(
        args.output,
        args.clusters,
        args.comparisons,
        title=args.title,
    )
    print(f"Overlays: {summary['overlays']}")
    print(f"Full HD overlays: {summary['fullhd_overlays']}")
    print(f"Clusters: {summary['clusters']}")
    print(f"Covered pixels: {summary['covered_pixels']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
