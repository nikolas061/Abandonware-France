#!/usr/bin/env python3
"""Compare .tex PCX name references with decoded CDCACHE Full HD descriptors."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
from collections import Counter, defaultdict
from pathlib import Path


DEFAULT_OUTPUT = Path("output/tex_reference_coverage")
DEFAULT_REFERENCES = Path("output/texture_report/reference_summary.csv")
DEFAULT_DESCRIPTOR_MANIFEST = Path("output/cdcache_textures_all_tiled_tiles_rgba/manifest.csv")
DEFAULT_PACK_MANIFEST = Path("output/cdcache_hd_asset_pack/manifest.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "texture_archives",
    "reference_rows",
    "likely_references",
    "unique_likely_pcx",
    "covered_references",
    "missing_references",
    "covered_unique_pcx",
    "missing_unique_pcx",
    "covered_descriptors",
    "covered_pack_descriptors",
    "missing_covered_fullhd_paths",
    "issue_rows",
]

REFERENCE_FIELDNAMES = [
    "texture_path",
    "archive",
    "archive_tag",
    "pcx_name",
    "normalized_pcx_name",
    "reference_kind",
    "covered",
    "cache_indexes",
    "descriptor_count",
    "pack_descriptor_count",
    "descriptor_fullhd_paths",
    "descriptor_pack_paths",
    "issues",
]

ARCHIVE_FIELDNAMES = [
    "archive",
    "archive_tag",
    "texture_path",
    "likely_references",
    "unique_likely_pcx",
    "covered_references",
    "missing_references",
    "covered_unique_pcx",
    "missing_unique_pcx",
    "missing_names",
]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def split_values(value: str) -> list[str]:
    return [part for part in value.split(";") if part]


def normalize_pcx(name: str) -> str:
    return Path(name.replace("\\", "/")).name.lower()


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


def descriptors_by_name(path: Path) -> dict[str, list[dict[str, str]]]:
    by_name: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in read_rows(path):
        by_name[normalize_pcx(row.get("base_name", "") or row.get("pcx_name", ""))].append(row)
    return by_name


def pack_descriptors_by_name(path: Path) -> dict[str, list[dict[str, str]]]:
    by_name: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in read_rows(path):
        if row.get("asset_kind") != "descriptor":
            continue
        by_name[normalize_pcx(row.get("base_name", "") or row.get("pcx_name", ""))].append(row)
    return by_name


def reference_rows(
    references: Path,
    descriptors: dict[str, list[dict[str, str]]],
    pack_descriptors: dict[str, list[dict[str, str]]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for source in read_rows(references):
        for pcx_name in split_values(source.get("likely_texture_names", "")):
            normalized = normalize_pcx(pcx_name)
            descriptor_rows = descriptors.get(normalized, [])
            pack_rows = pack_descriptors.get(normalized, [])
            issues: list[str] = []
            fullhd_paths = [row.get("crop_fullhd_path") or row.get("fullhd_path", "") for row in descriptor_rows]
            pack_paths = [row.get("all_pack_path", "") for row in pack_rows]
            missing_fullhd = [path for path in fullhd_paths if not path or not Path(path).exists()]
            missing_pack = [path for path in pack_paths if not path or not Path(path).exists()]
            if descriptor_rows and missing_fullhd:
                issues.append(f"missing_descriptor_fullhd_paths:{len(missing_fullhd)}")
            if pack_rows and missing_pack:
                issues.append(f"missing_pack_descriptor_paths:{len(missing_pack)}")
            rows.append(
                {
                    "texture_path": source.get("texture_path", ""),
                    "archive": source.get("archive", ""),
                    "archive_tag": archive_tag(source.get("archive", "")),
                    "pcx_name": pcx_name,
                    "normalized_pcx_name": normalized,
                    "reference_kind": "likely",
                    "covered": "yes" if descriptor_rows else "no",
                    "cache_indexes": ";".join(sorted({row.get("cache_index", "") for row in descriptor_rows})),
                    "descriptor_count": str(len(descriptor_rows)),
                    "pack_descriptor_count": str(len(pack_rows)),
                    "descriptor_fullhd_paths": ";".join(fullhd_paths),
                    "descriptor_pack_paths": ";".join(pack_paths),
                    "issues": ";".join(issues),
                }
            )
    return rows


def archive_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    texture_paths: dict[tuple[str, str], str] = {}
    for row in rows:
        key = (row["archive"], row["archive_tag"])
        grouped[key].append(row)
        texture_paths[key] = row["texture_path"]

    output: list[dict[str, str]] = []
    for (archive, tag), group in sorted(grouped.items(), key=lambda item: item[0][1].lower()):
        names = [row["normalized_pcx_name"] for row in group]
        covered_names = [row["normalized_pcx_name"] for row in group if row["covered"] == "yes"]
        missing_names = [row["normalized_pcx_name"] for row in group if row["covered"] != "yes"]
        output.append(
            {
                "archive": archive,
                "archive_tag": tag,
                "texture_path": texture_paths[(archive, tag)],
                "likely_references": str(len(group)),
                "unique_likely_pcx": str(len(set(names))),
                "covered_references": str(len(covered_names)),
                "missing_references": str(len(missing_names)),
                "covered_unique_pcx": str(len(set(covered_names))),
                "missing_unique_pcx": str(len(set(missing_names))),
                "missing_names": ";".join(sorted(set(missing_names))),
            }
        )
    return output


def summary_row(rows: list[dict[str, str]], archives: list[dict[str, str]]) -> dict[str, str]:
    names = [row["normalized_pcx_name"] for row in rows]
    covered = [row["normalized_pcx_name"] for row in rows if row["covered"] == "yes"]
    missing = [row["normalized_pcx_name"] for row in rows if row["covered"] != "yes"]
    covered_descriptors = {
        cache_index
        for row in rows
        for cache_index in split_values(row["cache_indexes"])
    }
    covered_pack = sum(int(row["pack_descriptor_count"]) for row in rows if row["covered"] == "yes")
    missing_covered_paths = sum(
        1
        for row in rows
        if row["covered"] == "yes" and ("missing_descriptor_fullhd_paths" in row["issues"] or "missing_pack_descriptor_paths" in row["issues"])
    )
    issue_rows = sum(1 for row in rows if row["issues"])
    return {
        "scope": "total",
        "texture_archives": str(len(archives)),
        "reference_rows": str(len(rows)),
        "likely_references": str(len(rows)),
        "unique_likely_pcx": str(len(set(names))),
        "covered_references": str(len(covered)),
        "missing_references": str(len(missing)),
        "covered_unique_pcx": str(len(set(covered))),
        "missing_unique_pcx": str(len(set(missing))),
        "covered_descriptors": str(len(covered_descriptors)),
        "covered_pack_descriptors": str(covered_pack),
        "missing_covered_fullhd_paths": str(missing_covered_paths),
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
    archives: list[dict[str, str]],
    references: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    missing_rows = [row for row in references if row["covered"] != "yes"]
    payload = {
        "summary": summary,
        "archives": archives,
        "references": references,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("by_archive.csv", output_dir / "by_archive.csv"),
            ("references.csv", output_dir / "references.csv"),
            ("missing_references.csv", output_dir / "missing_references.csv"),
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
  --warn: #f0b06a;
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
.warn {{ color: var(--warn); }}
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
    <div class="stat"><div class="label">Noms PCX probables</div><div class="value">{html.escape(summary['unique_likely_pcx'])}</div></div>
    <div class="stat"><div class="label">Couverts</div><div class="value ok">{html.escape(summary['covered_unique_pcx'])}</div></div>
    <div class="stat"><div class="label">Non rattaches</div><div class="value warn">{html.escape(summary['missing_unique_pcx'])}</div></div>
    <div class="stat"><div class="label">Issues chemins</div><div class="value ok">{html.escape(summary['issue_rows'])}</div></div>
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
    <h2>Par archive .tex</h2>
    {render_table(archives, ARCHIVE_FIELDNAMES)}
  </section>
  <section class="panel">
    <h2>References non rattachees</h2>
    {render_table(missing_rows, REFERENCE_FIELDNAMES)}
  </section>
</main>
<script>
const TEX_REFERENCE_COVERAGE = {data_json};
const references = TEX_REFERENCE_COVERAGE.references;
</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    references_path: Path,
    descriptor_manifest: Path,
    pack_manifest: Path,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    descriptors = descriptors_by_name(descriptor_manifest)
    pack_descriptors = pack_descriptors_by_name(pack_manifest)
    rows = reference_rows(references_path, descriptors, pack_descriptors)
    archives = archive_rows(rows)
    summary = summary_row(rows, archives)
    missing_rows = [row for row in rows if row["covered"] != "yes"]
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "references.csv", REFERENCE_FIELDNAMES, rows)
    write_csv(output_dir / "missing_references.csv", REFERENCE_FIELDNAMES, missing_rows)
    write_csv(output_dir / "by_archive.csv", ARCHIVE_FIELDNAMES, archives)
    (output_dir / "index.html").write_text(
        build_html(summary, archives, rows, output_dir, title)
    )
    return summary, rows, archives


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare .tex PCX references with Full HD CDCACHE descriptors.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--references", type=Path, default=DEFAULT_REFERENCES)
    parser.add_argument("--descriptor-manifest", type=Path, default=DEFAULT_DESCRIPTOR_MANIFEST)
    parser.add_argument("--pack-manifest", type=Path, default=DEFAULT_PACK_MANIFEST)
    parser.add_argument("--title", default="Lands of Lore II .tex Reference Coverage")
    args = parser.parse_args()

    summary, _rows, _archives = write_report(
        args.output,
        args.references,
        args.descriptor_manifest,
        args.pack_manifest,
        args.title,
    )
    print(f"Unique likely PCX references: {summary['unique_likely_pcx']}")
    print(
        "Covered/missing unique PCX: "
        f"{summary['covered_unique_pcx']}/{summary['missing_unique_pcx']}"
    )
    print(f"Covered reference rows: {summary['covered_references']}/{summary['likely_references']}")
    print(f"Path issue rows: {summary['issue_rows']}")
    print(f"HTML: {args.output / 'index.html'}")
    if summary["issue_rows"] != "0":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
