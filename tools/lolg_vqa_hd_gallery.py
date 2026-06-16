#!/usr/bin/env python3
"""Build a static HTML gallery for Full HD VQA entry exports."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
from collections import Counter
from pathlib import Path


DEFAULT_BATCH_DIR = Path("output/vqa_batch_window_lcw_transparent0_allframes")

GALLERY_FIELDNAMES = [
    "archive",
    "archive_tag",
    "index",
    "file_id",
    "declared_frames",
    "native_width",
    "native_height",
    "fullhd_frames",
    "render_status_counts",
    "representative_frame",
    "representative_fullhd_path",
    "frames_fullhd_dir",
    "output_dir",
    "issues",
]


def read_csv(path: Path) -> list[dict[str, str]]:
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


def archive_tag(path_text: str) -> str:
    return Path(path_text).stem.upper() if path_text else "UNKNOWN"


def representative_frame(output_dir: Path) -> tuple[str, str, list[str]]:
    issues: list[str] = []
    rendered_manifest = output_dir / "rendered_frames.csv"
    if not rendered_manifest.exists():
        return "", "", ["missing_rendered_frames_manifest"]
    for row in read_csv(rendered_manifest):
        fullhd = row.get("fullhd_output", "")
        if not fullhd:
            continue
        path = Path(fullhd)
        if path.exists():
            return row.get("frame", ""), str(path), []
        issues.append(f"representative_fullhd_missing:{fullhd}")
    if not issues:
        issues.append("no_fullhd_frame_rows")
    return "", "", issues


def build_gallery_rows(batch_dir: Path) -> list[dict[str, str]]:
    manifest = batch_dir / "manifest.csv"
    rows: list[dict[str, str]] = []
    for row in read_csv(manifest):
        issues: list[str] = []
        output_dir = Path(row.get("output_dir", ""))
        if not output_dir.exists():
            issues.append("missing_output_dir")
        frame, representative, frame_issues = representative_frame(output_dir)
        issues.extend(frame_issues)
        frames_fullhd_dir = output_dir / "frames_fullhd"
        if not frames_fullhd_dir.exists():
            issues.append("missing_frames_fullhd_dir")
        rows.append(
            {
                "archive": row.get("archive", ""),
                "archive_tag": archive_tag(row.get("archive", "")),
                "index": row.get("index", ""),
                "file_id": row.get("file_id", ""),
                "declared_frames": row.get("declared_frames", ""),
                "native_width": row.get("width", ""),
                "native_height": row.get("height", ""),
                "fullhd_frames": row.get("fullhd_frames", ""),
                "render_status_counts": row.get("render_frame_status_counts", ""),
                "representative_frame": frame,
                "representative_fullhd_path": representative,
                "frames_fullhd_dir": str(frames_fullhd_dir),
                "output_dir": str(output_dir),
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
        "archive": row["archive"],
        "archiveTag": row["archive_tag"],
        "index": row["index"],
        "fileId": row["file_id"],
        "declaredFrames": row["declared_frames"],
        "nativeWidth": row["native_width"],
        "nativeHeight": row["native_height"],
        "fullhdFrames": row["fullhd_frames"],
        "renderStatusCounts": row["render_status_counts"],
        "representativeFrame": row["representative_frame"],
        "image": relative_href(row["representative_fullhd_path"], base_dir),
        "framesDir": relative_href(row["frames_fullhd_dir"], base_dir),
        "outputDir": relative_href(row["output_dir"], base_dir),
    }


def option_markup(values: Counter[str]) -> str:
    parts = ['<option value="">Toutes archives</option>']
    for value, count in sorted(values.items(), key=lambda item: (item[0].lower(), item[0])):
        escaped = html.escape(value)
        parts.append(f'<option value="{escaped}">{escaped} ({count})</option>')
    return "\n".join(parts)


def build_html(rows: list[dict[str, str]], batch_dir: Path, title: str) -> str:
    assets = [asset_payload(row, batch_dir) for row in rows]
    data_json = json.dumps(assets, ensure_ascii=True, separators=(",", ":"))
    archive_counts = Counter(row["archive_tag"] for row in rows)
    total_frames = sum(int(row["fullhd_frames"] or 0) for row in rows)
    archive_options = option_markup(archive_counts)
    total = len(rows)
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
  grid-template-columns: minmax(220px, 2fr) minmax(150px, 1fr) minmax(150px, 1fr);
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
  background: #060708;
}}
.preview img {{ width: 100%; height: 100%; object-fit: contain; }}
.meta {{ padding: 8px; display: grid; gap: 5px; }}
.name {{ font-weight: 650; overflow-wrap: anywhere; }}
.detail {{ color: var(--muted); font-size: 12px; overflow-wrap: anywhere; }}
.links {{ display: flex; gap: 8px; flex-wrap: wrap; font-size: 12px; }}
.links a {{ color: var(--accent); text-decoration: none; }}
.empty {{
  display: none;
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 18px;
  color: var(--muted);
}}
@media (max-width: 760px) {{
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
        <span class="stat"><strong>{total}</strong> entrees</span>
        <span class="stat"><strong>{total_frames}</strong> frames Full HD</span>
        <span class="stat"><strong>{len(archive_counts)}</strong> archives</span>
      </div>
    </div>
    <div class="filters">
      <input id="search" type="search" placeholder="Rechercher archive, index, file id">
      <select id="archive">{archive_options}</select>
      <select id="frameRange">
        <option value="">Toutes longueurs</option>
        <option value="short">1-30 frames</option>
        <option value="medium">31-120 frames</option>
        <option value="long">121+ frames</option>
      </select>
    </div>
  </div>
</header>
<main class="wrap">
  <div id="grid" class="grid"></div>
  <div id="empty" class="empty">Aucune entree ne correspond aux filtres.</div>
</main>
<script>
const ASSETS = {data_json};
const grid = document.getElementById('grid');
const empty = document.getElementById('empty');
const shownCount = document.getElementById('shownCount');
const search = document.getElementById('search');
const archive = document.getElementById('archive');
const frameRange = document.getElementById('frameRange');
const controls = [search, archive, frameRange];

function escapeHtml(value) {{
  return String(value ?? '').replace(/[&<>"']/g, char => ({{
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
  }}[char]));
}}

function frameRangeMatches(asset) {{
  if (!frameRange.value) return true;
  const count = Number(asset.fullhdFrames || 0);
  if (frameRange.value === 'short') return count <= 30;
  if (frameRange.value === 'medium') return count > 30 && count <= 120;
  return count > 120;
}}

function textFor(asset) {{
  return [
    asset.archive, asset.archiveTag, asset.index, asset.fileId,
    asset.declaredFrames, asset.fullhdFrames, asset.renderStatusCounts
  ].join(' ').toLowerCase();
}}

function matches(asset) {{
  const query = search.value.trim().toLowerCase();
  if (query && !textFor(asset).includes(query)) return false;
  if (archive.value && asset.archiveTag !== archive.value) return false;
  return frameRangeMatches(asset);
}}

function card(asset) {{
  const el = document.createElement('article');
  el.className = 'entry';
  const image = escapeHtml(asset.image);
  const framesDir = escapeHtml(asset.framesDir);
  const outputDir = escapeHtml(asset.outputDir);
  const archiveText = escapeHtml(asset.archiveTag);
  const index = escapeHtml(asset.index);
  const fileId = escapeHtml(asset.fileId);
  const nativeWidth = escapeHtml(asset.nativeWidth);
  const nativeHeight = escapeHtml(asset.nativeHeight);
  const representativeFrame = escapeHtml(asset.representativeFrame);
  const fullhdFrames = escapeHtml(asset.fullhdFrames);
  const renderStatusCounts = escapeHtml(asset.renderStatusCounts);
  el.innerHTML = `
    <a class="preview" href="${{image}}">
      <img src="${{image}}" loading="lazy" decoding="async" alt="">
    </a>
    <div class="meta">
      <div class="name">${{archiveText}} #${{index}}</div>
      <div class="detail">${{fileId}} · ${{nativeWidth}}x${{nativeHeight}} · ${{fullhdFrames}} frames</div>
      <div class="detail">representative frame ${{representativeFrame}} · ${{renderStatusCounts}}</div>
      <div class="links"><a href="${{image}}">image</a><a href="${{framesDir}}">frames</a><a href="${{outputDir}}">dossier</a></div>
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


def write_gallery(batch_dir: Path, output: Path, title: str) -> tuple[Path, Path, int]:
    rows = build_gallery_rows(batch_dir)
    manifest = batch_dir / "gallery_manifest.csv"
    write_gallery_manifest(manifest, rows)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_html(rows, batch_dir, title))
    return output, manifest, len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a static VQA Full HD gallery.")
    parser.add_argument("--batch-dir", type=Path, default=DEFAULT_BATCH_DIR)
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="HTML file to write. Defaults to BATCH_DIR/index.html.",
    )
    parser.add_argument("--title", default="VQA Full HD Entries")
    args = parser.parse_args()

    output = args.output or args.batch_dir / "index.html"
    html_path, manifest, count = write_gallery(args.batch_dir, output, args.title)
    issue_rows = sum(1 for row in read_csv(manifest) if row["issues"])
    print(f"Gallery entries: {count}")
    print(f"Issue rows: {issue_rows}")
    print(f"Manifest: {manifest}")
    print(f"HTML: {html_path}")
    if issue_rows:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
