#!/usr/bin/env python3
"""Combine exact .tex coverage with CDCACHE alias candidates."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
from collections import defaultdict
from pathlib import Path


DEFAULT_OUTPUT = Path("output/tex_augmented_coverage")
DEFAULT_REFERENCES = Path("output/tex_reference_coverage/references.csv")
DEFAULT_ALIAS_PACK = Path("output/cdcache_tex_alias_pack/manifest.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "reference_rows",
    "unique_likely_pcx",
    "exact_covered_reference_rows",
    "exact_covered_unique_pcx",
    "alias_reference_rows",
    "alias_unique_pcx",
    "alias_assets",
    "exact_or_alias_unique_pcx",
    "unresolved_reference_rows",
    "unresolved_unique_pcx",
    "issue_rows",
]

ROW_FIELDNAMES = [
    "texture_path",
    "archive",
    "archive_tag",
    "pcx_name",
    "normalized_pcx_name",
    "coverage_status",
    "exact_covered",
    "exact_descriptor_count",
    "alias_assets",
    "alias_kinds",
    "alias_candidate_base_names",
    "alias_pack_paths",
    "issues",
]

ALIAS_FIELDNAMES = [
    "archive",
    "archive_tag",
    "missing_pcx_name",
    "alias_kind",
    "candidate_pcx_name",
    "candidate_base_name",
    "cache_index",
    "width",
    "height",
    "alias_pack_path",
    "issues",
]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def normalize_pcx(name: str) -> str:
    return Path(name.replace("\\", "/")).name.lower()


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    if not path_text:
        return ""
    path = Path(path_text)
    try:
        relative = path.relative_to(base_dir)
    except ValueError:
        relative = Path(os.path.relpath(path, base_dir))
    return relative.as_posix()


def aliases_by_archive_name(rows: list[dict[str, str]]) -> dict[tuple[str, str], list[dict[str, str]]]:
    output: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        key = (row.get("archive", ""), normalize_pcx(row.get("missing_pcx_name", "")))
        if key[0] and key[1]:
            output[key].append(row)
    return output


def build_rows(
    references: list[dict[str, str]],
    aliases: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    alias_lookup = aliases_by_archive_name(aliases)
    rows: list[dict[str, str]] = []
    alias_rows: list[dict[str, str]] = []
    for reference in references:
        archive = reference.get("archive", "")
        name = normalize_pcx(reference.get("normalized_pcx_name", "") or reference.get("pcx_name", ""))
        exact_covered = reference.get("covered") == "yes"
        matching_aliases = alias_lookup.get((archive, name), [])
        issues = []
        for alias in matching_aliases:
            if alias.get("issues"):
                issues.append("alias_has_issues")
            if alias.get("alias_exists") != "yes" or not Path(alias.get("alias_pack_path", "")).exists():
                issues.append("missing_alias_pack_path")
        if exact_covered:
            status = "exact"
        elif matching_aliases:
            status = "alias"
        else:
            status = "unresolved"
        rows.append(
            {
                "texture_path": reference.get("texture_path", ""),
                "archive": archive,
                "archive_tag": reference.get("archive_tag", ""),
                "pcx_name": reference.get("pcx_name", ""),
                "normalized_pcx_name": name,
                "coverage_status": status,
                "exact_covered": "yes" if exact_covered else "no",
                "exact_descriptor_count": reference.get("descriptor_count", ""),
                "alias_assets": str(len(matching_aliases)),
                "alias_kinds": ";".join(sorted({row.get("alias_kind", "") for row in matching_aliases if row.get("alias_kind")})),
                "alias_candidate_base_names": ";".join(
                    sorted({row.get("candidate_base_name", "") for row in matching_aliases if row.get("candidate_base_name")})
                ),
                "alias_pack_paths": ";".join(row.get("alias_pack_path", "") for row in matching_aliases),
                "issues": ";".join(sorted(set(issues))),
            }
        )

    for alias in aliases:
        alias_rows.append(
            {
                "archive": alias.get("archive", ""),
                "archive_tag": alias.get("archive_tag", ""),
                "missing_pcx_name": alias.get("missing_pcx_name", ""),
                "alias_kind": alias.get("alias_kind", ""),
                "candidate_pcx_name": alias.get("candidate_pcx_name", ""),
                "candidate_base_name": alias.get("candidate_base_name", ""),
                "cache_index": alias.get("cache_index", ""),
                "width": alias.get("width", ""),
                "height": alias.get("height", ""),
                "alias_pack_path": alias.get("alias_pack_path", ""),
                "issues": alias.get("issues", ""),
            }
        )
    return rows, alias_rows


def summary_row(rows: list[dict[str, str]], aliases: list[dict[str, str]]) -> dict[str, str]:
    unique_names = {row["normalized_pcx_name"] for row in rows}
    exact_names = {row["normalized_pcx_name"] for row in rows if row["coverage_status"] == "exact"}
    alias_names = {row["normalized_pcx_name"] for row in rows if row["coverage_status"] == "alias"}
    unresolved_names = {row["normalized_pcx_name"] for row in rows if row["coverage_status"] == "unresolved"}
    return {
        "scope": "total",
        "reference_rows": str(len(rows)),
        "unique_likely_pcx": str(len(unique_names)),
        "exact_covered_reference_rows": str(sum(1 for row in rows if row["coverage_status"] == "exact")),
        "exact_covered_unique_pcx": str(len(exact_names)),
        "alias_reference_rows": str(sum(1 for row in rows if row["coverage_status"] == "alias")),
        "alias_unique_pcx": str(len(alias_names)),
        "alias_assets": str(len(aliases)),
        "exact_or_alias_unique_pcx": str(len(exact_names | alias_names)),
        "unresolved_reference_rows": str(sum(1 for row in rows if row["coverage_status"] == "unresolved")),
        "unresolved_unique_pcx": str(len(unresolved_names)),
        "issue_rows": str(sum(1 for row in rows if row["issues"]) + sum(1 for row in aliases if row["issues"])),
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
    rows: list[dict[str, str]],
    aliases: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "references": rows, "aliases": aliases}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("references.csv", output_dir / "references.csv"),
            ("aliases.csv", output_dir / "aliases.csv"),
        )
    )
    alias_rows = [row for row in rows if row["coverage_status"] == "alias"]
    unresolved_rows = [row for row in rows if row["coverage_status"] == "unresolved"]
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
.warn {{ color: var(--warn); }}
.panel {{
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--panel);
  padding: 12px;
  overflow-x: auto;
}}
h2 {{ margin: 0 0 10px; font-size: 16px; }}
table {{ width: 100%; min-width: 1200px; border-collapse: collapse; }}
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
    <div class="stat"><div class="label">Exact unique</div><div class="value ok">{html.escape(summary['exact_covered_unique_pcx'])}</div></div>
    <div class="stat"><div class="label">Alias unique</div><div class="value">{html.escape(summary['alias_unique_pcx'])}</div></div>
    <div class="stat"><div class="label">Exact ou alias</div><div class="value">{html.escape(summary['exact_or_alias_unique_pcx'])}</div></div>
    <div class="stat"><div class="label">Restants</div><div class="value warn">{html.escape(summary['unresolved_unique_pcx'])}</div></div>
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
    <h2>References avec alias</h2>
    {render_table(alias_rows, ROW_FIELDNAMES)}
  </section>
  <section class="panel">
    <h2>References restantes</h2>
    {render_table(unresolved_rows, ROW_FIELDNAMES)}
  </section>
</main>
<script>
const TEX_AUGMENTED_COVERAGE = {data_json};
</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    references_path: Path,
    alias_pack_path: Path,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows, aliases = build_rows(read_rows(references_path), read_rows(alias_pack_path))
    summary = summary_row(rows, aliases)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "references.csv", ROW_FIELDNAMES, rows)
    write_csv(output_dir / "aliases.csv", ALIAS_FIELDNAMES, aliases)
    (output_dir / "index.html").write_text(build_html(summary, rows, aliases, output_dir, title))
    return summary, rows, aliases


def main() -> None:
    parser = argparse.ArgumentParser(description="Combine exact .tex reference coverage with alias candidates.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--references", type=Path, default=DEFAULT_REFERENCES)
    parser.add_argument("--alias-pack", type=Path, default=DEFAULT_ALIAS_PACK)
    parser.add_argument("--title", default="Lands of Lore II .tex Augmented Coverage")
    args = parser.parse_args()

    summary, _rows, _aliases = write_report(
        args.output,
        args.references,
        args.alias_pack,
        args.title,
    )
    print(f"Unique likely PCX: {summary['unique_likely_pcx']}")
    print(
        "Exact/alias/unresolved unique: "
        f"{summary['exact_covered_unique_pcx']}/"
        f"{summary['alias_unique_pcx']}/"
        f"{summary['unresolved_unique_pcx']}"
    )
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"HTML: {args.output / 'index.html'}")
    if summary["issue_rows"] != "0":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
