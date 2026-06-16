#!/usr/bin/env python3
"""Report .tex-linked CDCACHE Full HD asset coverage."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
from collections import Counter, defaultdict
from pathlib import Path


DEFAULT_OUTPUT = Path("output/tex_hd_coverage")
DEFAULT_MATERIAL_LINKS = Path("output/texture_report/cdcache_material_texture_links.csv")
DEFAULT_PACK_MANIFEST = Path("output/cdcache_hd_asset_pack/manifest.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "material_link_rows",
    "material_link_archives",
    "material_link_descriptors",
    "tex_linked_pack_assets",
    "tex_linked_descriptors",
    "tex_linked_tiles",
    "tex_linked_archives",
    "descriptor_assets_with_material_links",
    "descriptor_assets_without_material_links",
    "missing_all_pack_paths",
    "missing_linked_pack_paths",
    "missing_source_paths",
    "issue_rows",
]

CACHE_FIELDNAMES = [
    "cache_index",
    "pcx_name",
    "base_name",
    "archive_tags",
    "matched_texture_archives",
    "material_names",
    "material_link_rows",
    "descriptor_assets",
    "tile_assets",
    "linked_pack_assets",
    "native_width",
    "native_height",
    "descriptor_all_pack_path",
    "descriptor_linked_pack_path",
    "missing_all_pack_paths",
    "missing_linked_pack_paths",
    "missing_source_paths",
    "issues",
]

MATERIAL_FIELDNAMES = [
    "archive",
    "archive_tag",
    "material_clean_text",
    "material_offset_hex",
    "material_range_label",
    "pcx_name",
    "cache_index",
    "cache_width",
    "cache_height",
    "descriptor_all_pack_path",
    "descriptor_linked_pack_path",
    "tile_assets",
    "issues",
]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def split_values(value: str) -> list[str]:
    return [part for part in value.split(";") if part]


def archive_tag(path_text: str) -> str:
    return Path(path_text).stem.upper() if path_text else "UNKNOWN"


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    if not path_text:
        return ""
    path = Path(path_text)
    try:
        relative = path.relative_to(base_dir)
    except ValueError:
        relative = Path(os.path.relpath(path, base_dir))
    return relative.as_posix()


def count_text(values: list[str]) -> str:
    counts = Counter(values)
    return ";".join(f"{key}:{count}" for key, count in sorted(counts.items()))


def path_exists(path_text: str) -> bool:
    return bool(path_text) and Path(path_text).exists()


def pack_linked_rows(pack_manifest: Path) -> list[dict[str, str]]:
    return [row for row in read_rows(pack_manifest) if row.get("linked_to_tex") == "yes"]


def material_links_by_cache(material_links: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    by_cache: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in material_links:
        by_cache[row.get("cache_index", "")].append(row)
    return by_cache


def pack_rows_by_cache(pack_rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    by_cache: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in pack_rows:
        by_cache[row.get("cache_index", "")].append(row)
    return by_cache


def cache_report_rows(
    material_links: list[dict[str, str]],
    pack_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    links_by_cache = material_links_by_cache(material_links)
    pack_by_cache = pack_rows_by_cache(pack_rows)
    rows: list[dict[str, str]] = []
    for cache_index in sorted(pack_by_cache, key=lambda value: int(value) if value.isdigit() else 999999):
        assets = pack_by_cache[cache_index]
        descriptors = [row for row in assets if row.get("asset_kind") == "descriptor"]
        tiles = [row for row in assets if row.get("asset_kind") == "tile"]
        descriptor = descriptors[0] if descriptors else {}
        links = links_by_cache.get(cache_index, [])
        material_names = sorted(
            {
                row.get("material_clean_text", "")
                for row in links
                if row.get("material_clean_text", "")
            }
            | {
                name
                for row in assets
                for name in split_values(row.get("material_names", ""))
            }
        )
        archive_tags = sorted(
            {
                tag
                for row in assets
                for tag in split_values(row.get("archive_tags", ""))
            }
        )
        matched_archives = sorted(
            {
                archive
                for row in assets
                for archive in split_values(row.get("matched_texture_archives", ""))
            }
        )
        missing_all = sum(1 for row in assets if not path_exists(row.get("all_pack_path", "")))
        missing_linked = sum(1 for row in assets if not path_exists(row.get("linked_pack_path", "")))
        missing_source = sum(1 for row in assets if not path_exists(row.get("source_fullhd_path", "")))
        issues: list[str] = []
        if not descriptors:
            issues.append("missing_descriptor_asset")
        if not tiles:
            issues.append("missing_tile_assets")
        if missing_all:
            issues.append(f"missing_all_pack_paths:{missing_all}")
        if missing_linked:
            issues.append(f"missing_linked_pack_paths:{missing_linked}")
        if missing_source:
            issues.append(f"missing_source_paths:{missing_source}")
        rows.append(
            {
                "cache_index": cache_index,
                "pcx_name": descriptor.get("pcx_name", assets[0].get("pcx_name", "")),
                "base_name": descriptor.get("base_name", assets[0].get("base_name", "")),
                "archive_tags": ";".join(archive_tags),
                "matched_texture_archives": ";".join(matched_archives),
                "material_names": ";".join(material_names),
                "material_link_rows": str(len(links)),
                "descriptor_assets": str(len(descriptors)),
                "tile_assets": str(len(tiles)),
                "linked_pack_assets": str(len(assets)),
                "native_width": descriptor.get("native_width", assets[0].get("native_width", "")),
                "native_height": descriptor.get("native_height", assets[0].get("native_height", "")),
                "descriptor_all_pack_path": descriptor.get("all_pack_path", ""),
                "descriptor_linked_pack_path": descriptor.get("linked_pack_path", ""),
                "missing_all_pack_paths": str(missing_all),
                "missing_linked_pack_paths": str(missing_linked),
                "missing_source_paths": str(missing_source),
                "issues": ";".join(issues),
            }
        )
    return rows


def material_report_rows(
    material_links: list[dict[str, str]],
    cache_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    cache_by_index = {row["cache_index"]: row for row in cache_rows}
    rows: list[dict[str, str]] = []
    for link in material_links:
        cache_index = link.get("cache_index", "")
        cache = cache_by_index.get(cache_index, {})
        issues: list[str] = []
        if not cache:
            issues.append("missing_cache_asset_row")
        elif cache.get("issues"):
            issues.append(cache["issues"])
        rows.append(
            {
                "archive": link.get("archive", ""),
                "archive_tag": archive_tag(link.get("archive", "")),
                "material_clean_text": link.get("material_clean_text", ""),
                "material_offset_hex": link.get("material_offset_hex", ""),
                "material_range_label": link.get("material_range_label", ""),
                "pcx_name": link.get("pcx_name", ""),
                "cache_index": cache_index,
                "cache_width": link.get("cache_width", ""),
                "cache_height": link.get("cache_height", ""),
                "descriptor_all_pack_path": cache.get("descriptor_all_pack_path", ""),
                "descriptor_linked_pack_path": cache.get("descriptor_linked_pack_path", ""),
                "tile_assets": cache.get("tile_assets", ""),
                "issues": ";".join(issues),
            }
        )
    return rows


def summary_row(
    material_links: list[dict[str, str]],
    pack_rows: list[dict[str, str]],
    cache_rows: list[dict[str, str]],
    material_rows: list[dict[str, str]],
) -> dict[str, str]:
    descriptors = [row for row in pack_rows if row.get("asset_kind") == "descriptor"]
    tiles = [row for row in pack_rows if row.get("asset_kind") == "tile"]
    material_cache_indexes = {row.get("cache_index", "") for row in material_links}
    missing_all = sum(int(row["missing_all_pack_paths"]) for row in cache_rows)
    missing_linked = sum(int(row["missing_linked_pack_paths"]) for row in cache_rows)
    missing_source = sum(int(row["missing_source_paths"]) for row in cache_rows)
    issue_rows = sum(1 for row in cache_rows if row["issues"]) + sum(
        1 for row in material_rows if row["issues"]
    )
    return {
        "scope": "total",
        "material_link_rows": str(len(material_links)),
        "material_link_archives": str(len({row.get("archive", "") for row in material_links})),
        "material_link_descriptors": str(len(material_cache_indexes)),
        "tex_linked_pack_assets": str(len(pack_rows)),
        "tex_linked_descriptors": str(len(descriptors)),
        "tex_linked_tiles": str(len(tiles)),
        "tex_linked_archives": str(
            len(
                {
                    tag
                    for row in pack_rows
                    for tag in split_values(row.get("archive_tags", ""))
                }
            )
        ),
        "descriptor_assets_with_material_links": str(
            sum(1 for row in cache_rows if int(row["material_link_rows"]) > 0)
        ),
        "descriptor_assets_without_material_links": str(
            sum(1 for row in cache_rows if int(row["material_link_rows"]) == 0)
        ),
        "missing_all_pack_paths": str(missing_all),
        "missing_linked_pack_paths": str(missing_linked),
        "missing_source_paths": str(missing_source),
        "issue_rows": str(issue_rows),
    }


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def render_table(rows: list[dict[str, str]], columns: list[str]) -> str:
    head = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    body = []
    for row in rows:
        cells = "".join(f"<td>{html.escape(row.get(column, ''))}</td>" for column in columns)
        body.append(f"<tr>{cells}</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def build_html(
    summary: dict[str, str],
    cache_rows: list[dict[str, str]],
    material_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "caches": cache_rows,
        "materials": material_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("cache_assets.csv", output_dir / "cache_assets.csv"),
            ("material_links.csv", output_dir / "material_links.csv"),
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
main {{ padding: 16px 0 28px; display: grid; gap: 16px; }}
.stats {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 10px;
}}
.stat {{
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--panel);
  padding: 10px;
}}
.label {{ color: var(--muted); }}
.value {{ font-size: 24px; font-weight: 750; line-height: 1.05; margin-top: 4px; }}
.ok {{ color: var(--ok); }}
.panel {{
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--panel);
  padding: 12px;
  overflow-x: auto;
}}
h2 {{ margin: 0 0 10px; font-size: 16px; }}
table {{ width: 100%; min-width: 980px; border-collapse: collapse; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
td {{ overflow-wrap: anywhere; }}
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
    <div class="stat"><div class="label">Assets .tex Full HD</div><div class="value">{html.escape(summary['tex_linked_pack_assets'])}</div></div>
    <div class="stat"><div class="label">Descriptors</div><div class="value">{html.escape(summary['tex_linked_descriptors'])}</div></div>
    <div class="stat"><div class="label">Liens materiaux</div><div class="value">{html.escape(summary['material_link_rows'])}</div></div>
    <div class="stat"><div class="label">Issues</div><div class="value ok">{html.escape(summary['issue_rows'])}</div></div>
  </section>
  <section class="panel">
    <h2>Fichiers</h2>
    <div>{links}</div>
  </section>
  <section class="panel">
    <h2>Synthese</h2>
    {render_table([summary], SUMMARY_FIELDNAMES)}
  </section>
  <section class="panel">
    <h2>Descriptors et tuiles .tex</h2>
    {render_table(cache_rows, CACHE_FIELDNAMES)}
  </section>
  <section class="panel">
    <h2>Liens materiaux .tex</h2>
    {render_table(material_rows, MATERIAL_FIELDNAMES)}
  </section>
</main>
<script>
const TEX_COVERAGE = {data_json};
const caches = TEX_COVERAGE.caches;
</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    material_links_path: Path,
    pack_manifest: Path,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    material_links = read_rows(material_links_path)
    pack_rows = pack_linked_rows(pack_manifest)
    cache_rows = cache_report_rows(material_links, pack_rows)
    material_rows = material_report_rows(material_links, cache_rows)
    summary = summary_row(material_links, pack_rows, cache_rows, material_rows)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "cache_assets.csv", CACHE_FIELDNAMES, cache_rows)
    write_csv(output_dir / "material_links.csv", MATERIAL_FIELDNAMES, material_rows)
    (output_dir / "index.html").write_text(
        build_html(summary, cache_rows, material_rows, output_dir, title)
    )
    return summary, cache_rows, material_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Report .tex-linked CDCACHE Full HD coverage.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--material-links", type=Path, default=DEFAULT_MATERIAL_LINKS)
    parser.add_argument("--pack-manifest", type=Path, default=DEFAULT_PACK_MANIFEST)
    parser.add_argument("--title", default="Lands of Lore II .tex Full HD Coverage")
    args = parser.parse_args()

    summary, _cache_rows, _material_rows = write_report(
        args.output,
        args.material_links,
        args.pack_manifest,
        args.title,
    )
    print(f".tex-linked pack assets: {summary['tex_linked_pack_assets']}")
    print(
        "Descriptors/tiles: "
        f"{summary['tex_linked_descriptors']}/{summary['tex_linked_tiles']}"
    )
    print(f"Material links: {summary['material_link_rows']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"HTML: {args.output / 'index.html'}")
    if summary["issue_rows"] != "0":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
