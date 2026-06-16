#!/usr/bin/env python3
"""Build a static HTML gallery for Full HD still-image exports."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
from collections import Counter
from pathlib import Path


DEFAULT_IMAGE_DIR = Path("output/fullhd_images")

GALLERY_FIELDNAMES = [
    "source_type",
    "source_path",
    "source_label",
    "archive",
    "archive_tag",
    "index",
    "file_id",
    "source_width",
    "source_height",
    "output_width",
    "output_height",
    "fit",
    "output_path",
    "issues",
]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    if not path_text:
        return ""
    path = Path(path_text)
    try:
        relative = path.relative_to(base_dir)
    except ValueError:
        relative = Path(os.path.relpath(path, base_dir))
    return relative.as_posix()


def source_label(row: dict[str, str]) -> str:
    archive = row.get("archive", "")
    if archive:
        return archive
    source_path = row.get("source_path", "")
    return Path(source_path).name if source_path else "UNKNOWN"


def archive_tag(row: dict[str, str]) -> str:
    archive = row.get("archive", "")
    if archive:
        return Path(archive).stem.upper()
    source_type = row.get("source_type", "")
    return source_type.upper() if source_type else "UNKNOWN"


def verification_lookup(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    return {row.get("output_path", ""): row for row in read_rows(path)}


def build_gallery_rows(image_dir: Path) -> list[dict[str, str]]:
    manifest = image_dir / "manifest.csv"
    verification = verification_lookup(image_dir / "verification.csv")
    rows: list[dict[str, str]] = []
    for row in read_rows(manifest):
        issues: list[str] = []
        output_path = Path(row.get("output_path", ""))
        verify_row = verification.get(row.get("output_path", ""), {})
        verify_issues = verify_row.get("issues", "")
        if verify_issues:
            issues.append(f"verification:{verify_issues}")
        if not output_path.exists():
            issues.append("missing_output_path")
        rows.append(
            {
                "source_type": row.get("source_type", ""),
                "source_path": row.get("source_path", ""),
                "source_label": source_label(row),
                "archive": row.get("archive", ""),
                "archive_tag": archive_tag(row),
                "index": row.get("index", ""),
                "file_id": row.get("file_id", ""),
                "source_width": row.get("source_width", ""),
                "source_height": row.get("source_height", ""),
                "output_width": row.get("output_width", ""),
                "output_height": row.get("output_height", ""),
                "fit": row.get("fit", ""),
                "output_path": str(output_path),
                "issues": ";".join(issues),
            }
        )
    return rows


def write_gallery_manifest(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=GALLERY_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def asset_payload(row: dict[str, str], base_dir: Path) -> dict[str, str]:
    return {
        "type": row["source_type"],
        "source": row["source_path"],
        "sourceLabel": row["source_label"],
        "archive": row["archive"],
        "archiveTag": row["archive_tag"],
        "index": row["index"],
        "fileId": row["file_id"],
        "nativeWidth": row["source_width"],
        "nativeHeight": row["source_height"],
        "outputWidth": row["output_width"],
        "outputHeight": row["output_height"],
        "fit": row["fit"],
        "image": relative_href(row["output_path"], base_dir),
        "issues": row["issues"],
    }


def option_markup(values: Counter[str], default_label: str) -> str:
    parts = [f'<option value="">{html.escape(default_label)}</option>']
    for value, count in sorted(values.items(), key=lambda item: (item[0].lower(), item[0])):
        escaped = html.escape(value)
        parts.append(f'<option value="{escaped}">{escaped} ({count})</option>')
    return "\n".join(parts)


def size_bucket(row: dict[str, str]) -> str:
    width = int(row.get("source_width") or 0)
    height = int(row.get("source_height") or 0)
    pixels = width * height
    if pixels >= 640 * 350:
        return "large"
    if pixels >= 160 * 120:
        return "medium"
    return "small"


def build_html(rows: list[dict[str, str]], image_dir: Path, title: str) -> str:
    assets = [asset_payload(row, image_dir) | {"sizeBucket": size_bucket(row)} for row in rows]
    data_json = json.dumps(assets, ensure_ascii=True, separators=(",", ":"))
    type_counts = Counter(row["source_type"] for row in rows)
    archive_counts = Counter(row["archive_tag"] for row in rows)
    source_counts = Counter(row["source_label"] for row in rows)
    issue_count = sum(1 for row in rows if row["issues"])
    total = len(rows)
    type_options = option_markup(type_counts, "Tous types")
    archive_options = option_markup(archive_counts, "Toutes categories")
    source_options = option_markup(source_counts, "Toutes sources")
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
  --focus: #e8c468;
  --warn: #f0b06a;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  min-height: 100vh;
  background: var(--bg);
  color: var(--text);
  font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}}
header {{
  position: sticky;
  top: 0;
  z-index: 2;
  background: rgba(16, 19, 22, 0.96);
  border-bottom: 1px solid var(--line);
}}
.wrap {{ width: min(1800px, calc(100vw - 28px)); margin: 0 auto; }}
.topbar {{
  display: grid;
  grid-template-columns: minmax(220px, 1fr) auto;
  gap: 16px;
  align-items: end;
  padding: 14px 0 10px;
}}
h1 {{ margin: 0; font-size: 19px; font-weight: 650; letter-spacing: 0; }}
.stats {{ display: flex; flex-wrap: wrap; gap: 6px; justify-content: flex-end; }}
.stat {{
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 4px 8px;
  color: var(--muted);
  white-space: nowrap;
}}
.stat strong {{ color: var(--text); font-weight: 650; }}
.filters {{
  display: grid;
  grid-template-columns: minmax(200px, 2fr) repeat(4, minmax(130px, 1fr));
  gap: 8px;
  padding: 0 0 12px;
}}
input,
select {{
  width: 100%;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: var(--panel);
  color: var(--text);
  padding: 8px 9px;
  font: inherit;
}}
input:focus,
select:focus {{ outline: 2px solid var(--focus); outline-offset: 1px; }}
main {{ padding: 16px 0 28px; }}
.grid {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px;
}}
.entry {{
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--panel);
  overflow: hidden;
  min-width: 0;
}}
.preview {{
  aspect-ratio: 16 / 9;
  display: grid;
  place-items: center;
  background: #050607;
}}
.preview img {{ width: 100%; height: 100%; object-fit: contain; }}
.meta {{ padding: 8px; display: grid; gap: 5px; }}
.name {{ font-weight: 650; overflow-wrap: anywhere; }}
.detail {{ color: var(--muted); font-size: 12px; overflow-wrap: anywhere; }}
.issue {{ color: var(--warn); }}
.links {{ display: flex; gap: 8px; flex-wrap: wrap; font-size: 12px; }}
.links a {{ color: var(--accent); text-decoration: none; }}
.empty {{
  display: none;
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 18px;
  color: var(--muted);
}}
@media (max-width: 880px) {{
  .topbar {{ grid-template-columns: 1fr; }}
  .stats {{ justify-content: flex-start; }}
  .filters {{ grid-template-columns: 1fr; }}
  .grid {{ grid-template-columns: repeat(auto-fill, minmax(170px, 1fr)); }}
}}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <div class="topbar">
      <h1>{html.escape(title)}</h1>
      <div class="stats">
        <span class="stat"><strong id="shownCount">{total}</strong> affiches</span>
        <span class="stat"><strong>{total}</strong> images</span>
        <span class="stat"><strong>{len(type_counts)}</strong> types</span>
        <span class="stat"><strong>{issue_count}</strong> issues</span>
      </div>
    </div>
    <div class="filters">
      <input id="search" type="search" placeholder="Rechercher source, archive, index, file id">
      <select id="type">{type_options}</select>
      <select id="archive">{archive_options}</select>
      <select id="source">{source_options}</select>
      <select id="size">
        <option value="">Toutes tailles natives</option>
        <option value="small">Petites</option>
        <option value="medium">Moyennes</option>
        <option value="large">Grandes</option>
      </select>
    </div>
  </div>
</header>
<main class="wrap">
  <div id="grid" class="grid"></div>
  <div id="empty" class="empty">Aucune image ne correspond aux filtres.</div>
</main>
<script>
const ASSETS = {data_json};
const grid = document.getElementById('grid');
const empty = document.getElementById('empty');
const shownCount = document.getElementById('shownCount');
const search = document.getElementById('search');
const typeFilter = document.getElementById('type');
const archiveFilter = document.getElementById('archive');
const sourceFilter = document.getElementById('source');
const sizeFilter = document.getElementById('size');

function escapeHtml(value) {{
  return String(value ?? '').replace(/[&<>"']/g, character => ({{
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
  }}[character]));
}}

function searchable(asset) {{
  return [
    asset.type,
    asset.source,
    asset.sourceLabel,
    asset.archive,
    asset.archiveTag,
    asset.index,
    asset.fileId,
    asset.fit
  ].join(' ').toLowerCase();
}}

function matches(asset) {{
  const query = search.value.trim().toLowerCase();
  return (!query || searchable(asset).includes(query))
    && (!typeFilter.value || asset.type === typeFilter.value)
    && (!archiveFilter.value || asset.archiveTag === archiveFilter.value)
    && (!sourceFilter.value || asset.sourceLabel === sourceFilter.value)
    && (!sizeFilter.value || asset.sizeBucket === sizeFilter.value);
}}

function render(asset) {{
  const issue = asset.issues
    ? `<div class="detail issue">${{escapeHtml(asset.issues)}}</div>`
    : '';
  return `<article class="entry">
    <a class="preview" href="${{escapeHtml(asset.image)}}">
      <img src="${{escapeHtml(asset.image)}}" loading="lazy" decoding="async" alt="">
    </a>
    <div class="meta">
      <div class="name">${{escapeHtml(asset.sourceLabel)}} #${{escapeHtml(asset.index)}}</div>
      <div class="detail">${{escapeHtml(asset.type)}} - ${{escapeHtml(asset.nativeWidth)}}x${{escapeHtml(asset.nativeHeight)}} vers ${{escapeHtml(asset.outputWidth)}}x${{escapeHtml(asset.outputHeight)}}</div>
      <div class="detail">${{escapeHtml(asset.source)}}</div>
      ${{issue}}
      <div class="links"><a href="${{escapeHtml(asset.image)}}">PNG Full HD</a></div>
    </div>
  </article>`;
}}

function update() {{
  const visible = ASSETS.filter(matches);
  grid.innerHTML = visible.map(render).join('');
  shownCount.textContent = visible.length;
  empty.style.display = visible.length ? 'none' : 'block';
}}

[search, typeFilter, archiveFilter, sourceFilter, sizeFilter].forEach(control => {{
  control.addEventListener('input', update);
  control.addEventListener('change', update);
}});

update();
</script>
</body>
</html>
"""


def write_gallery(image_dir: Path, title: str) -> tuple[Path, Path, list[dict[str, str]]]:
    rows = build_gallery_rows(image_dir)
    image_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = image_dir / "gallery_manifest.csv"
    html_path = image_dir / "index.html"
    write_gallery_manifest(manifest_path, rows)
    html_path.write_text(build_html(rows, image_dir, title))
    return html_path, manifest_path, rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a static Full HD still-image gallery.")
    parser.add_argument("image_dir", nargs="?", type=Path, default=DEFAULT_IMAGE_DIR)
    parser.add_argument("--title", default="Lands of Lore II Full HD Still Images")
    args = parser.parse_args()

    html_path, manifest_path, rows = write_gallery(args.image_dir, args.title)
    issue_rows = sum(1 for row in rows if row["issues"])
    print(f"Still gallery assets: {len(rows)}")
    print(f"Issue rows: {issue_rows}")
    print(f"HTML: {html_path}")
    print(f"Manifest: {manifest_path}")
    if issue_rows:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
