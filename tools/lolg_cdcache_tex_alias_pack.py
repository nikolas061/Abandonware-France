#!/usr/bin/env python3
"""Create a focused pack of CDCACHE alias candidates for missing .tex names."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import re
from pathlib import Path


DEFAULT_OUTPUT = Path("output/cdcache_tex_alias_pack")
DEFAULT_ALIASES = Path("output/cdcache_alias_candidates/alias_candidates.csv")
DEFAULT_SYNTHETIC_MANIFEST = Path("output/cdcache_alias_candidate_textures/manifest.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "alias_assets",
    "unique_missing_pcx",
    "existing_descriptor_aliases",
    "synthetic_descriptor_aliases",
    "missing_source_paths",
    "missing_alias_paths",
    "target_mismatch_rows",
    "issue_rows",
]

MANIFEST_FIELDNAMES = [
    "asset_id",
    "archive",
    "archive_tag",
    "missing_pcx_name",
    "alias_kind",
    "candidate_pcx_name",
    "candidate_base_name",
    "cache_index",
    "width",
    "height",
    "source_fullhd_path",
    "alias_pack_path",
    "source_exists",
    "alias_exists",
    "alias_target_matches_source",
    "issues",
]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._") or "unnamed"


def relative_symlink(source: Path, target: Path) -> str:
    return os.path.relpath(source, target.parent)


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    if not path_text:
        return ""
    path = Path(path_text)
    try:
        relative = path.relative_to(base_dir)
    except ValueError:
        relative = Path(os.path.relpath(path, base_dir))
    return relative.as_posix()


def synthetic_by_key(rows: list[dict[str, str]]) -> dict[tuple[str, str, str, str], dict[str, str]]:
    output = {}
    for row in rows:
        key = (
            row.get("base_name", "").lower(),
            row.get("cache_index", ""),
            row.get("width", ""),
            row.get("height", ""),
        )
        output[key] = row
    return output


def choose_synthetic_source(row: dict[str, str]) -> str:
    return row.get("crop_fullhd_path", "") or row.get("fullhd_path", "")


def build_manifest(
    output_dir: Path,
    aliases: list[dict[str, str]],
    synthetic_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    by_synthetic = synthetic_by_key(synthetic_rows)
    descriptor_dir = output_dir / "descriptors"
    descriptor_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, str]] = []
    for alias in aliases:
        key = (
            alias.get("candidate_base_name", "").lower(),
            alias.get("cache_index", ""),
            alias.get("width", ""),
            alias.get("height", ""),
        )
        source_path_text = alias.get("pack_fullhd_path", "")
        if alias.get("alias_kind") == "synthetic_descriptor":
            source_path_text = choose_synthetic_source(by_synthetic.get(key, {}))

        source_path = Path(source_path_text) if source_path_text else Path()
        archive_tag = alias.get("archive_tag", "")
        asset_id = (
            f"{safe_name(archive_tag)}__{safe_name(alias.get('missing_pcx_name', ''))}"
            f"__alias_{safe_name(alias.get('candidate_base_name', ''))}"
            f"_idx{int(alias.get('cache_index') or 0):04d}_{alias.get('width')}x{alias.get('height')}"
        )
        target_dir = descriptor_dir / safe_name(archive_tag)
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / f"{asset_id}.png"
        issues: list[str] = []
        if not source_path_text or not source_path.exists():
            issues.append("missing_source_path")
        else:
            if target_path.exists() or target_path.is_symlink():
                target_path.unlink()
            target_path.symlink_to(relative_symlink(source_path, target_path))

        alias_exists = target_path.exists()
        target_matches = False
        if source_path_text and alias_exists:
            target_matches = os.path.realpath(target_path) == os.path.realpath(source_path)
        if source_path_text and not target_matches:
            issues.append("alias_target_mismatch")
        if not alias_exists:
            issues.append("missing_alias_path")

        rows.append(
            {
                "asset_id": asset_id,
                "archive": alias.get("archive", ""),
                "archive_tag": archive_tag,
                "missing_pcx_name": alias.get("missing_pcx_name", ""),
                "alias_kind": alias.get("alias_kind", ""),
                "candidate_pcx_name": alias.get("candidate_pcx_name", ""),
                "candidate_base_name": alias.get("candidate_base_name", ""),
                "cache_index": alias.get("cache_index", ""),
                "width": alias.get("width", ""),
                "height": alias.get("height", ""),
                "source_fullhd_path": source_path_text,
                "alias_pack_path": str(target_path),
                "source_exists": "yes" if source_path_text and source_path.exists() else "no",
                "alias_exists": "yes" if alias_exists else "no",
                "alias_target_matches_source": "yes" if target_matches else "no",
                "issues": ";".join(issues),
            }
        )
    return rows


def summary_row(rows: list[dict[str, str]]) -> dict[str, str]:
    return {
        "scope": "total",
        "alias_assets": str(len(rows)),
        "unique_missing_pcx": str(len({row["missing_pcx_name"] for row in rows})),
        "existing_descriptor_aliases": str(
            sum(1 for row in rows if row["alias_kind"] == "existing_descriptor")
        ),
        "synthetic_descriptor_aliases": str(
            sum(1 for row in rows if row["alias_kind"] == "synthetic_descriptor")
        ),
        "missing_source_paths": str(sum(1 for row in rows if row["source_exists"] != "yes")),
        "missing_alias_paths": str(sum(1 for row in rows if row["alias_exists"] != "yes")),
        "target_mismatch_rows": str(
            sum(1 for row in rows if row["alias_target_matches_source"] != "yes")
        ),
        "issue_rows": str(sum(1 for row in rows if row["issues"])),
    }


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def render_card(row: dict[str, str], base_dir: Path) -> str:
    image = html.escape(relative_href(row.get("alias_pack_path", ""), base_dir))
    title = f"{row.get('missing_pcx_name', '')} -> {row.get('candidate_base_name', '')}"
    return f"""
<article class="card">
  <a class="preview" href="{image}"><img src="{image}" loading="lazy" decoding="async" alt=""></a>
  <div class="body">
    <div class="title">{html.escape(title)}</div>
    <div class="muted">{html.escape(row.get('archive_tag', ''))} / {html.escape(row.get('alias_kind', ''))}</div>
    <div class="muted">{html.escape(row.get('width', ''))}x{html.escape(row.get('height', ''))} idx {html.escape(row.get('cache_index', ''))}</div>
  </div>
</article>"""


def build_html(summary: dict[str, str], rows: list[dict[str, str]], output_dir: Path, title: str) -> str:
    payload = {"summary": summary, "assets": rows}
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
.grid {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px;
}}
.card {{
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--panel);
  overflow: hidden;
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
h2 {{ margin: 0 0 10px; font-size: 16px; }}
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
    <div class="stat"><div class="label">Assets alias</div><div class="value">{html.escape(summary['alias_assets'])}</div></div>
    <div class="stat"><div class="label">Noms uniques</div><div class="value">{html.escape(summary['unique_missing_pcx'])}</div></div>
    <div class="stat"><div class="label">Synthetiques</div><div class="value">{html.escape(summary['synthetic_descriptor_aliases'])}</div></div>
    <div class="stat"><div class="label">Issues</div><div class="value ok">{html.escape(summary['issue_rows'])}</div></div>
  </section>
  <section class="panel">
    <h2>Fichiers</h2>
    <div>{links}</div>
  </section>
  <section class="grid">{cards}</section>
</main>
<script>
const CDCACHE_TEX_ALIAS_PACK = {data_json};
</script>
</body>
</html>
"""


def write_pack(
    output_dir: Path,
    aliases: Path,
    synthetic_manifest: Path,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = build_manifest(output_dir, read_rows(aliases), read_rows(synthetic_manifest))
    summary = summary_row(rows)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "manifest.csv", MANIFEST_FIELDNAMES, rows)
    (output_dir / "index.html").write_text(build_html(summary, rows, output_dir, title))
    return summary, rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a CDCACHE alias candidate pack for .tex references.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--aliases", type=Path, default=DEFAULT_ALIASES)
    parser.add_argument("--synthetic-manifest", type=Path, default=DEFAULT_SYNTHETIC_MANIFEST)
    parser.add_argument("--title", default="Lands of Lore II CDCACHE .tex Alias Pack")
    args = parser.parse_args()

    summary, _rows = write_pack(args.output, args.aliases, args.synthetic_manifest, args.title)
    print(f"Alias assets: {summary['alias_assets']}")
    print(f"Existing/synthetic: {summary['existing_descriptor_aliases']}/{summary['synthetic_descriptor_aliases']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"HTML: {args.output / 'index.html'}")
    if summary["issue_rows"] != "0":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
