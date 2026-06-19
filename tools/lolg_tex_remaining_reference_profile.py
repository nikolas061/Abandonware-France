#!/usr/bin/env python3
"""Profile remaining unresolved .tex references after augmented coverage."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
from collections import Counter, defaultdict
from pathlib import Path


DEFAULT_OUTPUT = Path("output/tex_remaining_reference_profile")
DEFAULT_AUGMENTED_REFERENCES = Path("output/tex_augmented_coverage/references.csv")
DEFAULT_MISSING_EVIDENCE = Path("output/tex_missing_reference_evidence/evidence.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "unresolved_reference_rows",
    "unresolved_unique_pcx",
    "archives",
    "evidence_classes",
    "raw_same_archive_unique",
    "tex_segment_only_unique",
    "material_record_link_unique",
    "large_segment_unique",
    "top_archive",
    "top_body_first_word",
    "total_segment_size",
    "issue_rows",
    "next_action",
]

PROFILE_FIELDNAMES = [
    "archive",
    "archive_tag",
    "texture_path",
    "pcx_name",
    "normalized_pcx_name",
    "evidence_class",
    "raw_cache_refs",
    "raw_cache_same_archive_refs",
    "raw_cache_source_paths",
    "texture_segment_rows",
    "texture_segment_size_total",
    "body_first_words",
    "material_record_links",
    "material_labels",
    "priority",
    "issues",
]

ARCHIVE_FIELDNAMES = [
    "archive",
    "archive_tag",
    "unresolved_reference_rows",
    "unresolved_unique_pcx",
    "evidence_classes",
    "total_segment_size",
    "top_body_first_word",
]

PREFIX_FIELDNAMES = [
    "body_first_word",
    "unresolved_reference_rows",
    "unresolved_unique_pcx",
    "archives",
    "total_segment_size",
    "sample_pcx",
]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def normalize_pcx(name: str) -> str:
    return Path(name.replace("\\", "/")).name.lower()


def int_value(row: dict[str, str], field: str) -> int:
    raw = row.get(field, "")
    try:
        return int(raw, 0) if raw else 0
    except ValueError:
        return 0


def split_values(value: str) -> list[str]:
    return [part for part in value.split(";") if part]


def evidence_lookup(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    lookup: dict[tuple[str, str], dict[str, str]] = {}
    for row in rows:
        key = (row.get("archive", ""), normalize_pcx(row.get("normalized_pcx_name", "") or row.get("pcx_name", "")))
        if key[0] and key[1]:
            lookup[key] = row
    return lookup


def priority_for(row: dict[str, str]) -> str:
    if int_value(row, "raw_cache_same_archive_refs") > 0:
        return "promote_raw_same_archive"
    if int_value(row, "material_record_links") > 0:
        return "review_material_link"
    if int_value(row, "texture_segment_size_total") >= 1_000_000:
        return "probe_large_tex_segment"
    if row.get("body_first_words"):
        return "probe_tex_segment_prefix"
    return "profile_reference"


def build_profile_rows(
    augmented_rows: list[dict[str, str]],
    evidence_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    evidence = evidence_lookup(evidence_rows)
    rows: list[dict[str, str]] = []
    for reference in augmented_rows:
        if reference.get("coverage_status") != "unresolved":
            continue
        archive = reference.get("archive", "")
        name = normalize_pcx(reference.get("normalized_pcx_name", "") or reference.get("pcx_name", ""))
        evidence_row = evidence.get((archive, name), {})
        issues: list[str] = []
        if not evidence_row:
            issues.append("missing_evidence_row")
        row = {
            "archive": archive,
            "archive_tag": reference.get("archive_tag", ""),
            "texture_path": reference.get("texture_path", ""),
            "pcx_name": reference.get("pcx_name", ""),
            "normalized_pcx_name": name,
            "evidence_class": evidence_row.get("evidence_class", "unknown"),
            "raw_cache_refs": evidence_row.get("raw_cache_refs", "0"),
            "raw_cache_same_archive_refs": evidence_row.get("raw_cache_same_archive_refs", "0"),
            "raw_cache_source_paths": evidence_row.get("raw_cache_source_paths", "0"),
            "texture_segment_rows": evidence_row.get("texture_segment_rows", "0"),
            "texture_segment_size_total": evidence_row.get("texture_segment_size_total", "0"),
            "body_first_words": evidence_row.get("body_first_words", ""),
            "material_record_links": evidence_row.get("material_record_links", "0"),
            "material_labels": evidence_row.get("material_labels", ""),
            "priority": "",
            "issues": ";".join(issues),
        }
        row["priority"] = priority_for(row)
        rows.append(row)
    return sorted(
        rows,
        key=lambda row: (
            {"promote_raw_same_archive": 0, "review_material_link": 1, "probe_large_tex_segment": 2}.get(
                row["priority"],
                3,
            ),
            row["archive_tag"],
            row["normalized_pcx_name"],
        ),
    )


def count_text(values: list[str]) -> str:
    counts = Counter(values)
    return ";".join(f"{key}:{count}" for key, count in sorted(counts.items()))


def top_counter_value(counter: Counter[str]) -> str:
    if not counter:
        return ""
    value, count = counter.most_common(1)[0]
    return f"{value}:{count}"


def summary_row(rows: list[dict[str, str]]) -> dict[str, str]:
    names = {row["normalized_pcx_name"] for row in rows}
    raw_same = {
        row["normalized_pcx_name"]
        for row in rows
        if int_value(row, "raw_cache_same_archive_refs") > 0
    }
    segment_only = {
        row["normalized_pcx_name"]
        for row in rows
        if row["evidence_class"] == "tex_segment_only"
    }
    material_link = {
        row["normalized_pcx_name"]
        for row in rows
        if int_value(row, "material_record_links") > 0
    }
    large_segment = {
        row["normalized_pcx_name"]
        for row in rows
        if int_value(row, "texture_segment_size_total") >= 1_000_000
    }
    top_archive = top_counter_value(Counter(row["archive_tag"] for row in rows))
    prefix_counter: Counter[str] = Counter()
    for row in rows:
        for prefix in split_values(row["body_first_words"]):
            prefix_counter[prefix] += 1

    if raw_same:
        next_action = f"promote {len(raw_same)} raw same-archive .tex candidates"
    elif large_segment:
        next_action = f"render probes for {len(large_segment)} large unresolved .tex segments"
    elif segment_only:
        next_action = f"profile {len(segment_only)} tex-segment-only unresolved .tex references"
    else:
        next_action = "review unresolved .tex references without evidence class"

    return {
        "scope": "total",
        "unresolved_reference_rows": str(len(rows)),
        "unresolved_unique_pcx": str(len(names)),
        "archives": str(len({row["archive"] for row in rows})),
        "evidence_classes": count_text([row["evidence_class"] for row in rows]),
        "raw_same_archive_unique": str(len(raw_same)),
        "tex_segment_only_unique": str(len(segment_only)),
        "material_record_link_unique": str(len(material_link)),
        "large_segment_unique": str(len(large_segment)),
        "top_archive": top_archive,
        "top_body_first_word": top_counter_value(prefix_counter),
        "total_segment_size": str(sum(int_value(row, "texture_segment_size_total") for row in rows)),
        "issue_rows": str(sum(1 for row in rows if row["issues"])),
        "next_action": next_action,
    }


def archive_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["archive"]].append(row)
    output: list[dict[str, str]] = []
    for archive, group in sorted(grouped.items()):
        prefix_counter: Counter[str] = Counter()
        for row in group:
            for prefix in split_values(row["body_first_words"]):
                prefix_counter[prefix] += 1
        output.append(
            {
                "archive": archive,
                "archive_tag": group[0]["archive_tag"],
                "unresolved_reference_rows": str(len(group)),
                "unresolved_unique_pcx": str(len({row["normalized_pcx_name"] for row in group})),
                "evidence_classes": count_text([row["evidence_class"] for row in group]),
                "total_segment_size": str(sum(int_value(row, "texture_segment_size_total") for row in group)),
                "top_body_first_word": top_counter_value(prefix_counter),
            }
        )
    return output


def prefix_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        prefixes = split_values(row["body_first_words"]) or [""]
        for prefix in prefixes:
            grouped[prefix].append(row)
    output: list[dict[str, str]] = []
    for prefix, group in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0])):
        output.append(
            {
                "body_first_word": prefix,
                "unresolved_reference_rows": str(len(group)),
                "unresolved_unique_pcx": str(len({row["normalized_pcx_name"] for row in group})),
                "archives": ";".join(sorted({row["archive_tag"] for row in group})),
                "total_segment_size": str(sum(int_value(row, "texture_segment_size_total") for row in group)),
                "sample_pcx": ";".join(sorted({row["normalized_pcx_name"] for row in group})[:8]),
            }
        )
    return output


def render_table(rows: list[dict[str, str]], columns: list[str]) -> str:
    head = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    body = []
    for row in rows:
        cells = "".join(f"<td>{html.escape(row.get(column, ''))}</td>" for column in columns)
        body.append(f"<tr>{cells}</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    path = Path(path_text)
    try:
        relative = path.relative_to(base_dir)
    except ValueError:
        relative = Path(os.path.relpath(path, base_dir))
    return relative.as_posix()


def build_html(
    summary: dict[str, str],
    profiles: list[dict[str, str]],
    archives: list[dict[str, str]],
    prefixes: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "profiles": profiles, "archives": archives, "prefixes": prefixes}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("profile.csv", output_dir / "profile.csv"),
            ("by_archive.csv", output_dir / "by_archive.csv"),
            ("by_prefix.csv", output_dir / "by_prefix.csv"),
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
.wrap {{ width: min(1700px, calc(100vw - 28px)); margin: 0 auto; }}
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
table {{ width: 100%; min-width: 1180px; border-collapse: collapse; }}
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
    <div class="stat"><div class="label">References restantes</div><div class="value warn">{html.escape(summary['unresolved_reference_rows'])}</div></div>
    <div class="stat"><div class="label">PCX uniques</div><div class="value warn">{html.escape(summary['unresolved_unique_pcx'])}</div></div>
    <div class="stat"><div class="label">Raw meme archive</div><div class="value">{html.escape(summary['raw_same_archive_unique'])}</div></div>
    <div class="stat"><div class="label">Large segments</div><div class="value">{html.escape(summary['large_segment_unique'])}</div></div>
    <div class="stat"><div class="label">Issues</div><div class="value ok">{html.escape(summary['issue_rows'])}</div></div>
  </section>
  <section class="panel">
    <div>{links}</div>
  </section>
  <section class="panel">
    <h2>Synthese</h2>
    {render_table([summary], SUMMARY_FIELDNAMES)}
  </section>
  <section class="panel">
    <h2>Par archive</h2>
    {render_table(archives, ARCHIVE_FIELDNAMES)}
  </section>
  <section class="panel">
    <h2>Par prefixe segment</h2>
    {render_table(prefixes, PREFIX_FIELDNAMES)}
  </section>
  <section class="panel">
    <h2>References restantes</h2>
    {render_table(profiles, PROFILE_FIELDNAMES)}
  </section>
</main>
<script>
const TEX_REMAINING_REFERENCE_PROFILE = {data_json};
</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    augmented_references: Path,
    missing_evidence: Path,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    profiles = build_profile_rows(read_rows(augmented_references), read_rows(missing_evidence))
    archives = archive_rows(profiles)
    prefixes = prefix_rows(profiles)
    summary = summary_row(profiles)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "profile.csv", PROFILE_FIELDNAMES, profiles)
    write_csv(output_dir / "by_archive.csv", ARCHIVE_FIELDNAMES, archives)
    write_csv(output_dir / "by_prefix.csv", PREFIX_FIELDNAMES, prefixes)
    (output_dir / "index.html").write_text(build_html(summary, profiles, archives, prefixes, output_dir, title))
    return summary, profiles


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile remaining unresolved .tex references.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--augmented-references", type=Path, default=DEFAULT_AUGMENTED_REFERENCES)
    parser.add_argument("--missing-evidence", type=Path, default=DEFAULT_MISSING_EVIDENCE)
    parser.add_argument("--title", default="Lands of Lore II .tex Remaining Reference Profile")
    args = parser.parse_args()

    summary, _profiles = write_report(args.output, args.augmented_references, args.missing_evidence, args.title)
    print(f"Remaining reference rows: {summary['unresolved_reference_rows']}")
    print(f"Remaining unique PCX: {summary['unresolved_unique_pcx']}")
    print(f"Next action: {summary['next_action']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"HTML: {args.output / 'index.html'}")
    if summary["issue_rows"] != "0":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
