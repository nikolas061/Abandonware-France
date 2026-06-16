#!/usr/bin/env python3
"""Build a static HTML gallery for the CDCACHE Full HD asset pack."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
from collections import Counter
from pathlib import Path


DEFAULT_PACK_DIR = Path("output/cdcache_hd_asset_pack")


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def relative_href(path_text: str, base_dir: Path) -> str:
    if not path_text:
        return ""
    path = Path(path_text)
    try:
        relative = path.relative_to(base_dir)
    except ValueError:
        relative = Path(os.path.relpath(path, base_dir))
    return relative.as_posix()


def split_values(value: str) -> list[str]:
    return [part for part in value.split(";") if part]


def asset_payload(row: dict[str, str], pack_dir: Path) -> dict[str, str | list[str]]:
    archives = split_values(row.get("archive_tags", ""))
    materials = split_values(row.get("material_names", ""))
    linked = row.get("linked_to_tex", "").lower() == "yes"
    image_path = row.get("all_pack_path", "")
    source_path = row.get("source_fullhd_path", "")
    linked_path = row.get("linked_pack_path", "")
    return {
        "id": row.get("asset_id", ""),
        "kind": row.get("asset_kind", ""),
        "linked": "yes" if linked else "no",
        "archives": archives,
        "archiveText": ";".join(archives) if archives else "UNLINKED",
        "pcx": row.get("pcx_name", ""),
        "base": row.get("base_name", ""),
        "materials": materials,
        "materialText": ";".join(materials),
        "cacheIndex": row.get("cache_index", ""),
        "tileIndex": row.get("tile_index", ""),
        "tileX": row.get("tile_x", ""),
        "tileY": row.get("tile_y", ""),
        "nativeWidth": row.get("native_width", ""),
        "nativeHeight": row.get("native_height", ""),
        "bbox": row.get("content_bbox", ""),
        "visibleRatio": row.get("visible_pixel_ratio", ""),
        "variant": row.get("selected_variant", ""),
        "image": relative_href(image_path, pack_dir),
        "source": relative_href(source_path, pack_dir),
        "linkedPath": relative_href(linked_path, pack_dir),
    }


def count_values(assets: list[dict[str, str | list[str]]], key: str) -> Counter[str]:
    counts: Counter[str] = Counter()
    for asset in assets:
        value = asset[key]
        if isinstance(value, list):
            for item in value:
                counts[item] += 1
        elif value:
            counts[str(value)] += 1
    return counts


def option_markup(values: Counter[str]) -> str:
    parts = ['<option value="">Tous</option>']
    for value, count in sorted(values.items(), key=lambda item: (item[0].lower(), item[0])):
        escaped = html.escape(value)
        parts.append(f'<option value="{escaped}">{escaped} ({count})</option>')
    return "\n".join(parts)


def build_html(
    assets: list[dict[str, str | list[str]]],
    *,
    pack_dir: Path,
    title: str,
) -> str:
    counts = Counter(str(asset["kind"]) for asset in assets)
    linked_count = sum(1 for asset in assets if asset["linked"] == "yes")
    archive_options = option_markup(count_values(assets, "archives"))
    material_options = option_markup(count_values(assets, "materials"))
    data_json = json.dumps(assets, ensure_ascii=True, separators=(",", ":"))
    total = len(assets)
    descriptors = counts.get("descriptor", 0)
    tiles = counts.get("tile", 0)
    contact_sheets = [
        ("Tous descriptors", "contact_sheet_all_descriptors.png"),
        ("Descriptors .tex", "contact_sheet_linked_descriptors.png"),
        ("Tuiles .tex", "contact_sheet_linked_tiles.png"),
    ]
    contact_links = "\n".join(
        f'<a class="sheet-link" href="{href}">{html.escape(label)}</a>'
        for label, href in contact_sheets
        if (pack_dir / href).exists()
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
  --focus: #e8c468;
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
.wrap {{
  width: min(1800px, calc(100vw - 28px));
  margin: 0 auto;
}}
.topbar {{
  display: grid;
  grid-template-columns: minmax(220px, 1fr) auto;
  gap: 16px;
  align-items: end;
  padding: 14px 0 10px;
}}
h1 {{
  margin: 0;
  font-size: 19px;
  font-weight: 650;
  letter-spacing: 0;
}}
.stats {{
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  justify-content: flex-end;
}}
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
  grid-template-columns: minmax(180px, 2fr) repeat(4, minmax(120px, 1fr));
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
select:focus {{
  outline: 2px solid var(--focus);
  outline-offset: 1px;
}}
.sheet-row {{
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 0 0 12px;
}}
.sheet-link {{
  color: var(--accent);
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 6px 9px;
  text-decoration: none;
}}
main {{
  padding: 16px 0 28px;
}}
.grid {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(190px, 1fr));
  gap: 12px;
}}
.asset {{
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
  background:
    linear-gradient(45deg, #c4c4c4 25%, transparent 25%),
    linear-gradient(-45deg, #c4c4c4 25%, transparent 25%),
    linear-gradient(45deg, transparent 75%, #c4c4c4 75%),
    linear-gradient(-45deg, transparent 75%, #c4c4c4 75%);
  background-color: #e8e8e8;
  background-position: 0 0, 0 8px, 8px -8px, -8px 0;
  background-size: 16px 16px;
}}
.preview img {{
  width: 100%;
  height: 100%;
  object-fit: contain;
}}
.meta {{
  padding: 8px;
  display: grid;
  gap: 5px;
}}
.name {{
  font-weight: 650;
  overflow-wrap: anywhere;
}}
.detail {{
  color: var(--muted);
  font-size: 12px;
  overflow-wrap: anywhere;
}}
.links {{
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 12px;
}}
.links a {{
  color: var(--accent);
  text-decoration: none;
}}
.empty {{
  display: none;
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 18px;
  color: var(--muted);
}}
@media (max-width: 860px) {{
  .topbar {{ grid-template-columns: 1fr; }}
  .stats {{ justify-content: flex-start; }}
  .filters {{ grid-template-columns: 1fr 1fr; }}
}}
@media (max-width: 540px) {{
  .filters {{ grid-template-columns: 1fr; }}
  .grid {{ grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); }}
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
        <span class="stat"><strong>{total}</strong> assets</span>
        <span class="stat"><strong>{descriptors}</strong> descriptors</span>
        <span class="stat"><strong>{tiles}</strong> tuiles</span>
        <span class="stat"><strong>{linked_count}</strong> .tex</span>
      </div>
    </div>
    <div class="filters">
      <input id="search" type="search" placeholder="Rechercher nom, PCX, materiau, index">
      <select id="kind">
        <option value="">Types</option>
        <option value="descriptor">Descriptors</option>
        <option value="tile">Tuiles</option>
      </select>
      <select id="linked">
        <option value="">Tous liens</option>
        <option value="yes">Lie .tex</option>
        <option value="no">Sans lien .tex</option>
      </select>
      <select id="archive">{archive_options}</select>
      <select id="material">{material_options}</select>
    </div>
    <div class="sheet-row">{contact_links}</div>
  </div>
</header>
<main class="wrap">
  <div id="grid" class="grid"></div>
  <div id="empty" class="empty">Aucun asset ne correspond aux filtres.</div>
</main>
<script>
const ASSETS = {data_json};
const grid = document.getElementById('grid');
const empty = document.getElementById('empty');
const shownCount = document.getElementById('shownCount');
const search = document.getElementById('search');
const kind = document.getElementById('kind');
const linked = document.getElementById('linked');
const archive = document.getElementById('archive');
const material = document.getElementById('material');
const controls = [search, kind, linked, archive, material];

function textFor(asset) {{
  return [
    asset.id, asset.kind, asset.archiveText, asset.pcx, asset.base,
    asset.materialText, asset.cacheIndex, asset.tileIndex,
    asset.nativeWidth, asset.nativeHeight, asset.bbox, asset.visibleRatio
  ].join(' ').toLowerCase();
}}

function escapeHtml(value) {{
  return String(value ?? '').replace(/[&<>"']/g, char => ({{
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
  }}[char]));
}}

function matches(asset) {{
  const query = search.value.trim().toLowerCase();
  if (query && !textFor(asset).includes(query)) return false;
  if (kind.value && asset.kind !== kind.value) return false;
  if (linked.value && asset.linked !== linked.value) return false;
  if (archive.value && !asset.archives.includes(archive.value)) return false;
  if (material.value && !asset.materials.includes(material.value)) return false;
  return true;
}}

function card(asset) {{
  const el = document.createElement('article');
  el.className = 'asset';
  const image = escapeHtml(asset.image);
  const source = escapeHtml(asset.source);
  const linkedPath = escapeHtml(asset.linkedPath);
  const base = escapeHtml(asset.base || asset.pcx);
  const kindText = escapeHtml(asset.kind);
  const archiveText = escapeHtml(asset.archiveText);
  const nativeWidth = escapeHtml(asset.nativeWidth);
  const nativeHeight = escapeHtml(asset.nativeHeight);
  const tileIndex = escapeHtml(asset.tileIndex);
  const tileX = escapeHtml(asset.tileX);
  const tileY = escapeHtml(asset.tileY);
  const bbox = escapeHtml(asset.bbox || 'none');
  const visibleRatio = escapeHtml(asset.visibleRatio || 'n/a');
  const materialLine = asset.materialText ? `<div class="detail">${{escapeHtml(asset.materialText)}}</div>` : '';
  const tileLine = asset.kind === 'tile'
    ? `<div class="detail">tile ${{tileIndex}} x${{tileX}} y${{tileY}}</div>`
    : '';
  const linkedLink = asset.linkedPath ? `<a href="${{linkedPath}}">linked</a>` : '';
  el.innerHTML = `
    <a class="preview" href="${{image}}">
      <img src="${{image}}" loading="lazy" decoding="async" alt="">
    </a>
    <div class="meta">
      <div class="name">${{base}}</div>
      <div class="detail">${{kindText}} · ${{archiveText}} · ${{nativeWidth}}x${{nativeHeight}}</div>
      ${{tileLine}}
      ${{materialLine}}
      <div class="detail">bbox ${{bbox}} · visible ${{visibleRatio}}</div>
      <div class="links"><a href="${{image}}">pack</a><a href="${{source}}">source</a>${{linkedLink}}</div>
    </div>`;
  return el;
}}

function render() {{
  const filtered = ASSETS.filter(matches);
  shownCount.textContent = filtered.length;
  grid.replaceChildren(...filtered.map(card));
  empty.style.display = filtered.length ? 'none' : 'block';
}}

for (const control of controls) control.addEventListener('input', render);
render();
</script>
</body>
</html>
"""


def write_gallery(pack_dir: Path, output: Path, title: str) -> tuple[Path, int]:
    manifest = pack_dir / "manifest.csv"
    rows = read_rows(manifest)
    assets = [asset_payload(row, pack_dir) for row in rows]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_html(assets, pack_dir=pack_dir, title=title))
    return output, len(assets)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a static CDCACHE HD asset gallery.")
    parser.add_argument("--pack-dir", type=Path, default=DEFAULT_PACK_DIR)
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="HTML file to write. Defaults to PACK_DIR/index.html.",
    )
    parser.add_argument("--title", default="CDCACHE Full HD Assets")
    args = parser.parse_args()

    output = args.output or args.pack_dir / "index.html"
    html_path, count = write_gallery(args.pack_dir, output, args.title)
    print(f"Gallery assets: {count}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
