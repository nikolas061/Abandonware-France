#!/usr/bin/env python3
"""Build a verified gallery for exploratory .tex probe renders."""

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
DEFAULT_OUTPUT = Path("output/tex_unresolved_material_probe_render")

SUMMARY_FIELDNAMES = [
    "scope",
    "preview_rows",
    "fullhd_previews",
    "unique_pcx",
    "archives",
    "segments",
    "widths",
    "skips",
    "palette_sources",
    "missing_native_paths",
    "missing_fullhd_paths",
    "native_dimension_mismatch_rows",
    "non_fullhd_rows",
    "issue_rows",
]

GALLERY_FIELDNAMES = [
    "archive",
    "archive_tag",
    "pcx_name",
    "material_clean_text",
    "segment_index",
    "body_offset",
    "body_offset_hex",
    "body_first_word",
    "segment_size",
    "skip",
    "width",
    "height",
    "sample_size",
    "record_size",
    "palette_source",
    "source",
    "native_path",
    "fullhd_path",
    "native_exists",
    "fullhd_exists",
    "native_actual_width",
    "native_actual_height",
    "native_mode",
    "fullhd_actual_width",
    "fullhd_actual_height",
    "fullhd_mode",
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


def archive_tag(path_text: str) -> str:
    return Path(path_text).stem.upper() if path_text else ""


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    if not path_text:
        return ""
    path = Path(path_text)
    try:
        relative = path.relative_to(base_dir)
    except ValueError:
        relative = Path(os.path.relpath(path, base_dir))
    return relative.as_posix()


def image_info(path: Path) -> tuple[bool, int, int, str, str]:
    if not path.exists():
        return False, 0, 0, "", "missing"
    try:
        with Image.open(path) as image:
            return True, image.width, image.height, image.mode, ""
    except Exception as exc:
        return True, 0, 0, "", f"open_failed:{exc}"


def verify_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    gallery_rows: list[dict[str, str]] = []
    for row in rows:
        issues: list[str] = []
        native_path = Path(row.get("native_path", ""))
        fullhd_path = Path(row.get("fullhd_path", ""))
        native_exists, native_w, native_h, native_mode, native_issue = image_info(native_path)
        fullhd_exists, fullhd_w, fullhd_h, fullhd_mode, fullhd_issue = image_info(fullhd_path)

        expected_w = int(row.get("width") or 0)
        expected_h = int(row.get("height") or 0)
        if native_issue:
            issues.append(f"native_{native_issue}")
        if fullhd_issue:
            issues.append(f"fullhd_{fullhd_issue}")
        if native_exists and (native_w, native_h) != (expected_w, expected_h):
            issues.append("native_dimensions_mismatch")
        if fullhd_exists and (fullhd_w, fullhd_h) != TARGET_SIZE:
            issues.append("fullhd_dimensions_mismatch")

        gallery_rows.append(
            {
                "archive": row.get("archive", ""),
                "archive_tag": archive_tag(row.get("archive", "")),
                "pcx_name": row.get("pcx_name", ""),
                "material_clean_text": row.get("material_clean_text", ""),
                "segment_index": row.get("segment_index", ""),
                "body_offset": row.get("body_offset", ""),
                "body_offset_hex": row.get("body_offset_hex", ""),
                "body_first_word": row.get("body_first_word", ""),
                "segment_size": row.get("segment_size", ""),
                "skip": row.get("skip", ""),
                "width": row.get("width", ""),
                "height": row.get("height", ""),
                "sample_size": row.get("sample_size", ""),
                "record_size": row.get("record_size", ""),
                "palette_source": row.get("palette_source", ""),
                "source": row.get("source", ""),
                "native_path": row.get("native_path", ""),
                "fullhd_path": row.get("fullhd_path", ""),
                "native_exists": "yes" if native_exists else "no",
                "fullhd_exists": "yes" if fullhd_exists else "no",
                "native_actual_width": str(native_w),
                "native_actual_height": str(native_h),
                "native_mode": native_mode,
                "fullhd_actual_width": str(fullhd_w),
                "fullhd_actual_height": str(fullhd_h),
                "fullhd_mode": fullhd_mode,
                "issues": ";".join(issues),
            }
        )
    return gallery_rows


def summary_row(rows: list[dict[str, str]]) -> dict[str, str]:
    unique_segments = {
        (row["archive"], row["pcx_name"], row["segment_index"], row["body_offset"])
        for row in rows
    }
    return {
        "scope": "total",
        "preview_rows": str(len(rows)),
        "fullhd_previews": str(sum(1 for row in rows if row["fullhd_exists"] == "yes")),
        "unique_pcx": str(len({row["pcx_name"].lower() for row in rows if row["pcx_name"]})),
        "archives": str(len({row["archive"] for row in rows if row["archive"]})),
        "segments": str(len(unique_segments)),
        "widths": ";".join(sorted({row["width"] for row in rows if row["width"]}, key=int)),
        "skips": ";".join(sorted({row["skip"] for row in rows if row["skip"]}, key=int)),
        "palette_sources": str(len({row["palette_source"] for row in rows if row["palette_source"]})),
        "missing_native_paths": str(sum(1 for row in rows if row["native_exists"] != "yes")),
        "missing_fullhd_paths": str(sum(1 for row in rows if row["fullhd_exists"] != "yes")),
        "native_dimension_mismatch_rows": str(
            sum(1 for row in rows if "native_dimensions_mismatch" in row["issues"].split(";"))
        ),
        "non_fullhd_rows": str(
            sum(1 for row in rows if "fullhd_dimensions_mismatch" in row["issues"].split(";"))
        ),
        "issue_rows": str(sum(1 for row in rows if row["issues"])),
    }


def asset_payload(row: dict[str, str], base_dir: Path) -> dict[str, str]:
    return {
        "archive": row["archive"],
        "archiveTag": row["archive_tag"],
        "pcx": row["pcx_name"],
        "material": row["material_clean_text"],
        "segment": row["segment_index"],
        "offset": row["body_offset_hex"],
        "prefix": row["body_first_word"],
        "segmentSize": row["segment_size"],
        "skip": row["skip"],
        "width": row["width"],
        "height": row["height"],
        "palette": row["palette_source"],
        "image": relative_href(row["fullhd_path"], base_dir),
        "native": relative_href(row["native_path"], base_dir),
        "issues": row["issues"],
    }


def option_markup(values: Counter[str], default_label: str) -> str:
    parts = [f'<option value="">{html.escape(default_label)}</option>']
    for value, count in sorted(values.items(), key=lambda item: (item[0].lower(), item[0])):
        escaped = html.escape(value)
        parts.append(f'<option value="{escaped}">{escaped} ({count})</option>')
    return "\n".join(parts)


def build_html(summary: dict[str, str], rows: list[dict[str, str]], output_dir: Path, title: str) -> str:
    assets = [asset_payload(row, output_dir) for row in rows]
    data_json = json.dumps(
        {"summary": summary, "assets": assets},
        ensure_ascii=True,
        separators=(",", ":"),
    )
    pcx_options = option_markup(Counter(row["pcx_name"] for row in rows), "Tous les noms")
    archive_options = option_markup(Counter(row["archive_tag"] for row in rows), "Toutes archives")
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("gallery_manifest.csv", output_dir / "gallery_manifest.csv"),
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
h1 {{ margin: 0; font-size: 19px; font-weight: 700; letter-spacing: 0; }}
.stats {{ display: flex; flex-wrap: wrap; gap: 6px; justify-content: flex-end; }}
.stat {{
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 4px 8px;
  color: var(--muted);
  white-space: nowrap;
}}
.stat strong {{ color: var(--text); }}
.ok {{ color: var(--ok); }}
.filters {{
  display: grid;
  grid-template-columns: minmax(200px, 2fr) repeat(4, minmax(120px, 1fr));
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
main {{ padding: 16px 0 28px; display: grid; gap: 14px; }}
.panel {{
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--panel);
  padding: 12px;
}}
.grid {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 12px;
}}
.card {{
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--panel);
  overflow: hidden;
  min-width: 0;
}}
.preview {{
  display: block;
  aspect-ratio: 16 / 9;
  background: #060708;
  border-bottom: 1px solid var(--line);
}}
.preview img {{ width: 100%; height: 100%; object-fit: contain; }}
.body {{ padding: 10px; display: grid; gap: 5px; }}
.title {{ font-weight: 700; overflow-wrap: anywhere; }}
.muted {{ color: var(--muted); }}
a {{ color: var(--accent); text-decoration: none; margin-right: 10px; }}
@media (max-width: 760px) {{
  .topbar {{ grid-template-columns: 1fr; }}
  .stats {{ justify-content: flex-start; }}
  .filters {{ grid-template-columns: 1fr; }}
}}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <div class="topbar">
      <h1>{html.escape(title)}</h1>
      <div class="stats">
        <div class="stat"><strong>{html.escape(summary['fullhd_previews'])}</strong> Full HD</div>
        <div class="stat"><strong>{html.escape(summary['unique_pcx'])}</strong> noms</div>
        <div class="stat"><strong>{html.escape(summary['segments'])}</strong> segments</div>
        <div class="stat"><strong class="ok">{html.escape(summary['issue_rows'])}</strong> issues</div>
      </div>
    </div>
    <div class="filters">
      <input id="query" type="search" placeholder="Filtrer">
      <select id="pcx">{pcx_options}</select>
      <select id="archive">{archive_options}</select>
      <select id="width"><option value="">Toutes largeurs</option></select>
      <select id="skip"><option value="">Tous skips</option></select>
    </div>
  </div>
</header>
<main class="wrap">
  <section class="panel">
    <div>{links}</div>
  </section>
  <section id="grid" class="grid"></section>
</main>
<script>
const TEX_UNRESOLVED_MATERIAL_PROBES = {data_json};
const assets = TEX_UNRESOLVED_MATERIAL_PROBES.assets;
const grid = document.getElementById("grid");
const query = document.getElementById("query");
const pcx = document.getElementById("pcx");
const archive = document.getElementById("archive");
const width = document.getElementById("width");
const skip = document.getElementById("skip");
function escapeHtml(value) {{
  return String(value ?? "").replace(/[&<>"']/g, char => ({{
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;"
  }}[char]));
}}
function fillSelect(select, values, label) {{
  const current = select.value;
  select.innerHTML = `<option value="">${{label}}</option>`;
  [...new Set(values.filter(Boolean))].sort((a, b) => Number(a) - Number(b)).forEach(value => {{
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    select.appendChild(option);
  }});
  select.value = current;
}}
fillSelect(width, assets.map(asset => asset.width), "Toutes largeurs");
fillSelect(skip, assets.map(asset => asset.skip), "Tous skips");
function matches(asset) {{
  const haystack = [
    asset.archiveTag,
    asset.pcx,
    asset.material,
    asset.segment,
    asset.offset,
    asset.prefix,
    asset.width,
    asset.skip
  ].join(" ").toLowerCase();
  const text = query.value.trim().toLowerCase();
  return (!text || haystack.includes(text))
    && (!pcx.value || asset.pcx === pcx.value)
    && (!archive.value || asset.archiveTag === archive.value)
    && (!width.value || asset.width === width.value)
    && (!skip.value || asset.skip === skip.value);
}}
function render() {{
  const visible = assets.filter(matches);
  grid.innerHTML = visible.map(asset => `
    <article class="card">
      <a class="preview" href="${{escapeHtml(asset.image)}}"><img src="${{escapeHtml(asset.image)}}" loading="lazy" decoding="async" alt=""></a>
      <div class="body">
        <div class="title">${{escapeHtml(asset.pcx)}} / w${{escapeHtml(asset.width)}} skip ${{escapeHtml(asset.skip)}}</div>
        <div class="muted">${{escapeHtml(asset.archiveTag)}} seg ${{escapeHtml(asset.segment)}} ${{escapeHtml(asset.offset)}}</div>
        <div class="muted">${{escapeHtml(asset.material || asset.prefix)}} / ${{escapeHtml(asset.height)}} rows</div>
      </div>
    </article>`).join("");
}}
[query, pcx, archive, width, skip].forEach(control => control.addEventListener("input", render));
render();
</script>
</body>
</html>
"""


def write_gallery(output_dir: Path, title: str) -> tuple[dict[str, str], list[dict[str, str]]]:
    manifest = output_dir / "manifest.csv"
    rows = verify_rows(read_rows(manifest))
    summary = summary_row(rows)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "gallery_manifest.csv", GALLERY_FIELDNAMES, rows)
    (output_dir / "index.html").write_text(build_html(summary, rows, output_dir, title))
    return summary, rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a verified gallery for .tex probe renders.")
    parser.add_argument("output", nargs="?", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Material Probe Gallery")
    args = parser.parse_args()

    summary, _rows = write_gallery(args.output, args.title)
    print(f"Probe previews: {summary['preview_rows']}")
    print(f"Full HD previews: {summary['fullhd_previews']}")
    print(f"Unique PCX names: {summary['unique_pcx']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"HTML: {args.output / 'index.html'}")
    if summary["issue_rows"] != "0":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
