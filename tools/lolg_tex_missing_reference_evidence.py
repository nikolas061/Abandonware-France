#!/usr/bin/env python3
"""Map missing .tex PCX references to raw cache and material evidence."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import re
from collections import defaultdict
from pathlib import Path


DEFAULT_OUTPUT = Path("output/tex_missing_reference_evidence")
DEFAULT_MISSING_REFERENCES = Path("output/tex_reference_coverage/missing_references.csv")
DEFAULT_RAW_REFERENCES = Path("output/texture_report/cdcache_raw_references.csv")
DEFAULT_DESCRIPTORS = Path("output/texture_report/cdcache_descriptors.csv")
DEFAULT_TEX_REFERENCES = Path("output/texture_report/references.csv")
DEFAULT_TEX_SEGMENTS = Path("output/texture_report/texture_segments.csv")
DEFAULT_MATERIAL_MATCHES = Path("output/texture_report/material_texture_name_matches.csv")
DEFAULT_MATERIAL_LINKS = Path("output/texture_report/material_texture_record_links.csv")
DEFAULT_MATERIAL_STRINGS = Path("output/texture_report/material_strings.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "missing_reference_rows",
    "unique_missing_pcx",
    "rows_with_raw_cdcache",
    "unique_with_raw_cdcache",
    "rows_with_raw_same_archive",
    "unique_with_raw_same_archive",
    "rows_with_material_match",
    "unique_with_material_match",
    "rows_with_material_record_link",
    "unique_with_material_record_link",
    "rows_with_texture_segment",
    "unique_with_texture_segment",
    "unexpected_descriptor_rows",
    "issue_rows",
]

EVIDENCE_FIELDNAMES = [
    "texture_path",
    "archive",
    "archive_tag",
    "pcx_name",
    "normalized_pcx_name",
    "pcx_stem",
    "evidence_class",
    "raw_cache_refs",
    "raw_cache_same_archive_refs",
    "raw_cache_source_paths",
    "raw_cache_offsets",
    "descriptor_rows",
    "texture_reference_rows",
    "texture_segment_rows",
    "texture_segment_size_total",
    "body_first_words",
    "material_name_matches",
    "material_record_links",
    "material_string_matches",
    "material_labels",
    "issues",
]

UNIQUE_FIELDNAMES = [
    "normalized_pcx_name",
    "pcx_stem",
    "missing_occurrences",
    "archives",
    "evidence_class",
    "raw_cache_refs",
    "raw_cache_same_archive_refs",
    "raw_cache_source_paths",
    "descriptor_rows",
    "texture_reference_rows",
    "texture_segment_rows",
    "texture_segment_size_total",
    "body_first_words",
    "material_name_matches",
    "material_record_links",
    "material_string_matches",
    "material_labels",
    "issues",
]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def split_values(value: str) -> list[str]:
    return [part for part in value.split(";") if part]


def normalize_pcx(name: str) -> str:
    return Path(name.replace("\\", "/")).name.lower()


def stem_key(name: str) -> str:
    return Path(normalize_pcx(name)).stem


def label_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


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


def rows_by_name(rows: list[dict[str, str]], name_field: str = "pcx_name") -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        name = normalize_pcx(row.get(name_field, ""))
        if name:
            grouped[name].append(row)
    return grouped


def rows_by_archive_name(
    rows: list[dict[str, str]],
    name_field: str = "pcx_name",
) -> dict[tuple[str, str], list[dict[str, str]]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        archive = row.get("archive", "")
        name = normalize_pcx(row.get(name_field, ""))
        if archive and name:
            grouped[(archive, name)].append(row)
    return grouped


def material_strings_by_archive_label(rows: list[dict[str, str]]) -> dict[tuple[str, str], list[dict[str, str]]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        archive = row.get("archive", "")
        clean = label_key(row.get("clean_text", ""))
        if archive and clean:
            grouped[(archive, clean)].append(row)
    return grouped


def raw_same_archive_rows(rows: list[dict[str, str]], archive: str) -> list[dict[str, str]]:
    matched = []
    for row in rows:
        archives = split_values(row.get("matched_texture_archives", ""))
        if archive in archives:
            matched.append(row)
    return matched


def evidence_class(
    descriptor_count: int,
    raw_count: int,
    raw_same_archive_count: int,
    material_match_count: int,
    material_link_count: int,
    segment_count: int,
) -> str:
    if descriptor_count:
        return "unexpected_descriptor"
    if raw_same_archive_count:
        return "raw_cache_same_archive"
    if raw_count:
        return "raw_cache_other_archive"
    if material_link_count:
        return "material_record_link"
    if material_match_count:
        return "material_name_match"
    if segment_count:
        return "tex_segment_only"
    return "no_extra_evidence"


def build_evidence_rows(
    missing_rows: list[dict[str, str]],
    raw_by_name: dict[str, list[dict[str, str]]],
    descriptors_by_name: dict[str, list[dict[str, str]]],
    tex_refs_by_archive_name: dict[tuple[str, str], list[dict[str, str]]],
    segments_by_archive_name: dict[tuple[str, str], list[dict[str, str]]],
    material_matches_by_archive_name: dict[tuple[str, str], list[dict[str, str]]],
    material_links_by_archive_name: dict[tuple[str, str], list[dict[str, str]]],
    material_strings_by_label: dict[tuple[str, str], list[dict[str, str]]],
) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for row in missing_rows:
        archive = row.get("archive", "")
        normalized = normalize_pcx(row.get("pcx_name", ""))
        stem = stem_key(normalized)
        raw_rows = raw_by_name.get(normalized, [])
        raw_same = raw_same_archive_rows(raw_rows, archive)
        descriptor_rows = descriptors_by_name.get(normalized, [])
        tex_ref_rows = tex_refs_by_archive_name.get((archive, normalized), [])
        segment_rows = segments_by_archive_name.get((archive, normalized), [])
        material_match_rows = material_matches_by_archive_name.get((archive, normalized), [])
        material_link_rows = material_links_by_archive_name.get((archive, normalized), [])
        material_string_rows = material_strings_by_label.get((archive, label_key(stem)), [])
        raw_source_paths = [
            source.get("pcx_name", "")
            for source in raw_rows
            if "\\" in source.get("pcx_name", "") or "/" in source.get("pcx_name", "")
        ]
        segment_sizes = [
            int(source.get("segment_size") or 0)
            for source in segment_rows
            if source.get("segment_size", "").isdigit()
        ]
        body_words = sorted(
            {
                source.get("body_first_word", "")
                for source in segment_rows
                if source.get("body_first_word", "")
            }
        )
        material_labels = sorted(
            {
                source.get("material_clean_text", "") or source.get("clean_text", "")
                for source in material_match_rows + material_link_rows + material_string_rows
                if source.get("material_clean_text", "") or source.get("clean_text", "")
            }
        )
        issues: list[str] = []
        if descriptor_rows:
            issues.append(f"unexpected_descriptor_rows:{len(descriptor_rows)}")
        if not segment_rows:
            issues.append("missing_texture_segment_row")
        kind = evidence_class(
            len(descriptor_rows),
            len(raw_rows),
            len(raw_same),
            len(material_match_rows),
            len(material_link_rows),
            len(segment_rows),
        )
        output.append(
            {
                "texture_path": row.get("texture_path", ""),
                "archive": archive,
                "archive_tag": row.get("archive_tag", "") or archive_tag(archive),
                "pcx_name": row.get("pcx_name", ""),
                "normalized_pcx_name": normalized,
                "pcx_stem": stem,
                "evidence_class": kind,
                "raw_cache_refs": str(len(raw_rows)),
                "raw_cache_same_archive_refs": str(len(raw_same)),
                "raw_cache_source_paths": str(len(raw_source_paths)),
                "raw_cache_offsets": ";".join(source.get("name_offset_hex", "") for source in raw_rows[:8]),
                "descriptor_rows": str(len(descriptor_rows)),
                "texture_reference_rows": str(len(tex_ref_rows)),
                "texture_segment_rows": str(len(segment_rows)),
                "texture_segment_size_total": str(sum(segment_sizes)),
                "body_first_words": ";".join(body_words),
                "material_name_matches": str(len(material_match_rows)),
                "material_record_links": str(len(material_link_rows)),
                "material_string_matches": str(len(material_string_rows)),
                "material_labels": ";".join(material_labels[:12]),
                "issues": ";".join(issues),
            }
        )
    return output


def build_unique_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["normalized_pcx_name"]].append(row)

    output: list[dict[str, str]] = []
    for name, group in sorted(grouped.items()):
        issues = sorted({issue for row in group for issue in split_values(row.get("issues", ""))})
        class_counts = defaultdict(int)
        for row in group:
            class_counts[row["evidence_class"]] += 1
        dominant_class = sorted(class_counts.items(), key=lambda item: (-item[1], item[0]))[0][0]
        output.append(
            {
                "normalized_pcx_name": name,
                "pcx_stem": group[0]["pcx_stem"],
                "missing_occurrences": str(len(group)),
                "archives": ";".join(sorted({row["archive"] for row in group})),
                "evidence_class": dominant_class,
                "raw_cache_refs": str(sum(int(row["raw_cache_refs"]) for row in group)),
                "raw_cache_same_archive_refs": str(
                    sum(int(row["raw_cache_same_archive_refs"]) for row in group)
                ),
                "raw_cache_source_paths": str(sum(int(row["raw_cache_source_paths"]) for row in group)),
                "descriptor_rows": str(sum(int(row["descriptor_rows"]) for row in group)),
                "texture_reference_rows": str(sum(int(row["texture_reference_rows"]) for row in group)),
                "texture_segment_rows": str(sum(int(row["texture_segment_rows"]) for row in group)),
                "texture_segment_size_total": str(
                    sum(int(row["texture_segment_size_total"]) for row in group)
                ),
                "body_first_words": ";".join(
                    sorted({word for row in group for word in split_values(row["body_first_words"])})
                ),
                "material_name_matches": str(sum(int(row["material_name_matches"]) for row in group)),
                "material_record_links": str(sum(int(row["material_record_links"]) for row in group)),
                "material_string_matches": str(sum(int(row["material_string_matches"]) for row in group)),
                "material_labels": ";".join(
                    sorted({label for row in group for label in split_values(row["material_labels"])})[:12]
                ),
                "issues": ";".join(issues),
            }
        )
    return output


def summary_row(rows: list[dict[str, str]], unique_rows: list[dict[str, str]]) -> dict[str, str]:
    unique_with_raw = {row["normalized_pcx_name"] for row in rows if int(row["raw_cache_refs"]) > 0}
    unique_with_raw_same = {
        row["normalized_pcx_name"] for row in rows if int(row["raw_cache_same_archive_refs"]) > 0
    }
    unique_with_material = {
        row["normalized_pcx_name"] for row in rows if int(row["material_name_matches"]) > 0
    }
    unique_with_links = {
        row["normalized_pcx_name"] for row in rows if int(row["material_record_links"]) > 0
    }
    unique_with_segments = {
        row["normalized_pcx_name"] for row in rows if int(row["texture_segment_rows"]) > 0
    }
    return {
        "scope": "total",
        "missing_reference_rows": str(len(rows)),
        "unique_missing_pcx": str(len(unique_rows)),
        "rows_with_raw_cdcache": str(sum(1 for row in rows if int(row["raw_cache_refs"]) > 0)),
        "unique_with_raw_cdcache": str(len(unique_with_raw)),
        "rows_with_raw_same_archive": str(sum(1 for row in rows if int(row["raw_cache_same_archive_refs"]) > 0)),
        "unique_with_raw_same_archive": str(len(unique_with_raw_same)),
        "rows_with_material_match": str(sum(1 for row in rows if int(row["material_name_matches"]) > 0)),
        "unique_with_material_match": str(len(unique_with_material)),
        "rows_with_material_record_link": str(sum(1 for row in rows if int(row["material_record_links"]) > 0)),
        "unique_with_material_record_link": str(len(unique_with_links)),
        "rows_with_texture_segment": str(sum(1 for row in rows if int(row["texture_segment_rows"]) > 0)),
        "unique_with_texture_segment": str(len(unique_with_segments)),
        "unexpected_descriptor_rows": str(sum(int(row["descriptor_rows"]) for row in rows)),
        "issue_rows": str(sum(1 for row in rows if row["issues"])),
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
    unique_rows: list[dict[str, str]],
    evidence_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "unique": unique_rows,
        "evidence": evidence_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("unique_missing.csv", output_dir / "unique_missing.csv"),
            ("evidence.csv", output_dir / "evidence.csv"),
        )
    )
    interesting_unique = [
        row for row in unique_rows if row["evidence_class"] != "tex_segment_only"
    ]
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
table {{ width: 100%; min-width: 1120px; border-collapse: collapse; }}
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
    <div class="stat"><div class="label">Noms manquants uniques</div><div class="value warn">{html.escape(summary['unique_missing_pcx'])}</div></div>
    <div class="stat"><div class="label">Presents en brut CDCACHE</div><div class="value">{html.escape(summary['unique_with_raw_cdcache'])}</div></div>
    <div class="stat"><div class="label">Brut meme archive</div><div class="value">{html.escape(summary['unique_with_raw_same_archive'])}</div></div>
    <div class="stat"><div class="label">Liens materiaux</div><div class="value">{html.escape(summary['unique_with_material_match'])}</div></div>
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
    <h2>Noms avec preuves hors segment .tex</h2>
    {render_table(interesting_unique, UNIQUE_FIELDNAMES)}
  </section>
  <section class="panel">
    <h2>Tous les noms uniques manquants</h2>
    {render_table(unique_rows, UNIQUE_FIELDNAMES)}
  </section>
</main>
<script>
const TEX_MISSING_REFERENCE_EVIDENCE = {data_json};
</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    missing_references: Path,
    raw_references: Path,
    descriptors: Path,
    tex_references: Path,
    tex_segments: Path,
    material_matches: Path,
    material_links: Path,
    material_strings: Path,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    missing_rows = read_rows(missing_references)
    evidence_rows = build_evidence_rows(
        missing_rows,
        rows_by_name(read_rows(raw_references), "pcx_name"),
        rows_by_name(read_rows(descriptors), "pcx_name"),
        rows_by_archive_name(read_rows(tex_references), "pcx_name"),
        rows_by_archive_name(read_rows(tex_segments), "pcx_name"),
        rows_by_archive_name(read_rows(material_matches), "pcx_name"),
        rows_by_archive_name(read_rows(material_links), "pcx_name"),
        material_strings_by_archive_label(read_rows(material_strings)),
    )
    unique_rows = build_unique_rows(evidence_rows)
    summary = summary_row(evidence_rows, unique_rows)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "evidence.csv", EVIDENCE_FIELDNAMES, evidence_rows)
    write_csv(output_dir / "unique_missing.csv", UNIQUE_FIELDNAMES, unique_rows)
    (output_dir / "index.html").write_text(
        build_html(summary, unique_rows, evidence_rows, output_dir, title)
    )
    return summary, evidence_rows, unique_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Map missing .tex PCX references to supporting evidence.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--missing-references", type=Path, default=DEFAULT_MISSING_REFERENCES)
    parser.add_argument("--raw-references", type=Path, default=DEFAULT_RAW_REFERENCES)
    parser.add_argument("--descriptors", type=Path, default=DEFAULT_DESCRIPTORS)
    parser.add_argument("--tex-references", type=Path, default=DEFAULT_TEX_REFERENCES)
    parser.add_argument("--tex-segments", type=Path, default=DEFAULT_TEX_SEGMENTS)
    parser.add_argument("--material-matches", type=Path, default=DEFAULT_MATERIAL_MATCHES)
    parser.add_argument("--material-links", type=Path, default=DEFAULT_MATERIAL_LINKS)
    parser.add_argument("--material-strings", type=Path, default=DEFAULT_MATERIAL_STRINGS)
    parser.add_argument("--title", default="Lands of Lore II .tex Missing Reference Evidence")
    args = parser.parse_args()

    summary, _rows, _unique = write_report(
        args.output,
        args.missing_references,
        args.raw_references,
        args.descriptors,
        args.tex_references,
        args.tex_segments,
        args.material_matches,
        args.material_links,
        args.material_strings,
        args.title,
    )
    print(f"Missing reference rows: {summary['missing_reference_rows']}")
    print(f"Unique missing PCX: {summary['unique_missing_pcx']}")
    print(
        "Raw CDCACHE unique names: "
        f"{summary['unique_with_raw_cdcache']} "
        f"(same archive {summary['unique_with_raw_same_archive']})"
    )
    print(f"Material-match unique names: {summary['unique_with_material_match']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"HTML: {args.output / 'index.html'}")
    if summary["issue_rows"] != "0":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
