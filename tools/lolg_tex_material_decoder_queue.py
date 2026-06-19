#!/usr/bin/env python3
"""Build a prioritized decoder queue for material-linked .tex texture segments."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
from collections import Counter, defaultdict
from pathlib import Path


DEFAULT_OUTPUT = Path("output/tex_material_decoder_queue")
DEFAULT_MATERIAL_LINKS = Path("output/texture_report/material_texture_record_links.csv")
DEFAULT_AUGMENTED_REFERENCES = Path("output/tex_augmented_coverage/references.csv")
DEFAULT_BEST_PROBES = Path("output/tex_unresolved_material_probe_render/best_candidates.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "material_link_rows",
    "unique_pcx",
    "exact_rows",
    "alias_rows",
    "decoded_material_rows",
    "decoded_material_segments",
    "unresolved_rows",
    "unresolved_unique_pcx",
    "unresolved_segments",
    "queued_probe_rows",
    "queued_probe_segments",
    "coverage_missing_rows",
    "issue_rows",
]

QUEUE_FIELDNAMES = [
    "archive",
    "archive_tag",
    "pcx_name",
    "normalized_pcx_name",
    "coverage_status",
    "material_clean_text",
    "match_type",
    "material_range_label",
    "material_name_class",
    "material_name_confidence",
    "texture_segment_index",
    "texture_body_offset",
    "texture_body_offset_hex",
    "texture_body_first_word",
    "texture_segment_size",
    "texture_entropy",
    "record_range_label",
    "record_index",
    "record_size",
    "record_start_hex",
    "next_distance",
    "matches_stride",
    "prefix_delta",
    "alias_assets",
    "alias_candidate_base_names",
    "decoded_material_assets",
    "decoded_material_pack_paths",
    "best_probe_rank",
    "best_probe_width",
    "best_probe_skip",
    "best_probe_score",
    "best_probe_fullhd_path",
    "priority",
    "issues",
]

PREFIX_FIELDNAMES = [
    "texture_body_first_word",
    "coverage_status",
    "rows",
    "unique_pcx",
    "total_segment_size",
    "avg_entropy",
    "sample_pcx",
]


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def normalize_name(value: str) -> str:
    return value.rsplit("\\", 1)[-1].rsplit("/", 1)[-1].lower()


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


def int_value(row: dict[str, str], field: str) -> int:
    raw = row.get(field, "")
    try:
        return int(raw, 0) if raw else 0
    except ValueError:
        return 0


def float_value(row: dict[str, str], field: str) -> float:
    raw = row.get(field, "")
    try:
        return float(raw) if raw else 0.0
    except ValueError:
        return 0.0


def build_coverage_lookup(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    lookup: dict[tuple[str, str], dict[str, str]] = {}
    for row in rows:
        key = (row.get("archive", ""), row.get("normalized_pcx_name", ""))
        lookup[key] = row
    return lookup


def build_best_probe_lookup(rows: list[dict[str, str]]) -> dict[tuple[str, str, str, str], dict[str, str]]:
    lookup: dict[tuple[str, str, str, str], dict[str, str]] = {}
    for row in rows:
        if row.get("rank") != "1":
            continue
        key = (
            row.get("archive", ""),
            normalize_name(row.get("pcx_name", "")),
            row.get("segment_index", ""),
            row.get("body_offset", ""),
        )
        lookup[key] = row
    return lookup


def priority_for(status: str, row: dict[str, str], best_probe: dict[str, str]) -> str:
    if status == "unresolved" and best_probe:
        return "decode_probe"
    if status == "unresolved":
        return "map_segment"
    if status == "alias":
        return "verify_alias"
    if status == "decoded_material":
        return "decoded"
    if status == "exact":
        return "covered"
    return "classify"


def build_queue_rows(
    material_rows: list[dict[str, str]],
    coverage_rows: list[dict[str, str]],
    best_probe_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    coverage = build_coverage_lookup(coverage_rows)
    best_probes = build_best_probe_lookup(best_probe_rows)
    rows: list[dict[str, str]] = []
    for row in material_rows:
        archive = row.get("archive", "")
        pcx_name = row.get("pcx_name", "")
        normalized = normalize_name(pcx_name)
        key = (archive, normalized)
        coverage_row = coverage.get(key, {})
        status = coverage_row.get("coverage_status", "missing_coverage")
        probe_key = (
            archive,
            normalized,
            row.get("texture_segment_index", ""),
            row.get("texture_body_offset", ""),
        )
        best_probe = best_probes.get(probe_key, {})
        issues: list[str] = []
        if not coverage_row:
            issues.append("missing_coverage_row")
        if status == "unresolved" and not best_probe:
            issues.append("missing_best_probe")
        best_probe_path = best_probe.get("fullhd_path", "")
        if best_probe_path and not Path(best_probe_path).exists():
            issues.append("missing_best_probe_path")

        rows.append(
            {
                "archive": archive,
                "archive_tag": archive_tag(archive),
                "pcx_name": pcx_name,
                "normalized_pcx_name": normalized,
                "coverage_status": status,
                "material_clean_text": row.get("material_clean_text", ""),
                "match_type": row.get("match_type", ""),
                "material_range_label": row.get("material_range_label", ""),
                "material_name_class": row.get("material_name_class", ""),
                "material_name_confidence": row.get("material_name_confidence", ""),
                "texture_segment_index": row.get("texture_segment_index", ""),
                "texture_body_offset": row.get("texture_body_offset", ""),
                "texture_body_offset_hex": row.get("texture_body_offset_hex", ""),
                "texture_body_first_word": row.get("texture_body_first_word", ""),
                "texture_segment_size": row.get("texture_segment_size", ""),
                "texture_entropy": row.get("texture_entropy", ""),
                "record_range_label": row.get("record_range_label", ""),
                "record_index": row.get("record_index", ""),
                "record_size": row.get("record_size", ""),
                "record_start_hex": row.get("record_start_hex", ""),
                "next_distance": row.get("next_distance", ""),
                "matches_stride": row.get("matches_stride", ""),
                "prefix_delta": row.get("prefix_delta", ""),
                "alias_assets": coverage_row.get("alias_assets", ""),
                "alias_candidate_base_names": coverage_row.get("alias_candidate_base_names", ""),
                "decoded_material_assets": coverage_row.get("decoded_material_assets", ""),
                "decoded_material_pack_paths": coverage_row.get("decoded_material_pack_paths", ""),
                "best_probe_rank": best_probe.get("rank", ""),
                "best_probe_width": best_probe.get("width", ""),
                "best_probe_skip": best_probe.get("skip", ""),
                "best_probe_score": best_probe.get("structure_score", ""),
                "best_probe_fullhd_path": best_probe_path,
                "priority": priority_for(status, row, best_probe),
                "issues": ";".join(issues),
            }
        )
    return sorted(
        rows,
        key=lambda item: (
            {"decode_probe": 0, "map_segment": 1, "verify_alias": 2, "decoded": 3, "covered": 4}.get(
                item["priority"],
                4,
            ),
            item["archive_tag"],
            item["normalized_pcx_name"],
            item["material_clean_text"],
        ),
    )


def build_prefix_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[(row["texture_body_first_word"], row["coverage_status"])].append(row)

    prefix_rows: list[dict[str, str]] = []
    for (prefix, status), group in sorted(grouped.items()):
        total_size = sum(int_value(row, "texture_segment_size") for row in group)
        entropy_values = [float_value(row, "texture_entropy") for row in group if row.get("texture_entropy")]
        avg_entropy = sum(entropy_values) / len(entropy_values) if entropy_values else 0.0
        samples = sorted({row["normalized_pcx_name"] for row in group})
        prefix_rows.append(
            {
                "texture_body_first_word": prefix,
                "coverage_status": status,
                "rows": str(len(group)),
                "unique_pcx": str(len(samples)),
                "total_segment_size": str(total_size),
                "avg_entropy": f"{avg_entropy:.4f}",
                "sample_pcx": ";".join(samples[:8]),
            }
        )
    return prefix_rows


def summary_row(rows: list[dict[str, str]]) -> dict[str, str]:
    statuses = Counter(row["coverage_status"] for row in rows)
    decoded_material_segments = {
        (row["archive"], row["normalized_pcx_name"], row["texture_segment_index"], row["texture_body_offset"])
        for row in rows
        if row["coverage_status"] == "decoded_material"
    }
    unresolved_names = {
        row["normalized_pcx_name"]
        for row in rows
        if row["coverage_status"] == "unresolved"
    }
    unresolved_segments = {
        (row["archive"], row["normalized_pcx_name"], row["texture_segment_index"], row["texture_body_offset"])
        for row in rows
        if row["coverage_status"] == "unresolved"
    }
    queued_probe_segments = {
        (row["archive"], row["normalized_pcx_name"], row["texture_segment_index"], row["texture_body_offset"])
        for row in rows
        if row["priority"] == "decode_probe"
    }
    return {
        "scope": "total",
        "material_link_rows": str(len(rows)),
        "unique_pcx": str(len({row["normalized_pcx_name"] for row in rows})),
        "exact_rows": str(statuses.get("exact", 0)),
        "alias_rows": str(statuses.get("alias", 0)),
        "decoded_material_rows": str(statuses.get("decoded_material", 0)),
        "decoded_material_segments": str(len(decoded_material_segments)),
        "unresolved_rows": str(statuses.get("unresolved", 0)),
        "unresolved_unique_pcx": str(len(unresolved_names)),
        "unresolved_segments": str(len(unresolved_segments)),
        "queued_probe_rows": str(sum(1 for row in rows if row["priority"] == "decode_probe")),
        "queued_probe_segments": str(len(queued_probe_segments)),
        "coverage_missing_rows": str(statuses.get("missing_coverage", 0)),
        "issue_rows": str(sum(1 for row in rows if row["issues"])),
    }


def render_row(row: dict[str, str], output_dir: Path) -> str:
    probe = row.get("best_probe_fullhd_path", "")
    probe_link = ""
    if probe:
        href = html.escape(relative_href(probe, output_dir))
        probe_link = f'<a href="{href}">probe</a>'
    return (
        "<tr>"
        f"<td>{html.escape(row['priority'])}</td>"
        f"<td>{html.escape(row['coverage_status'])}</td>"
        f"<td>{html.escape(row['archive_tag'])}</td>"
        f"<td>{html.escape(row['normalized_pcx_name'])}</td>"
        f"<td>{html.escape(row['material_clean_text'])}</td>"
        f"<td>{html.escape(row['texture_body_first_word'])}</td>"
        f"<td>{html.escape(row['texture_segment_size'])}</td>"
        f"<td>{html.escape(row['best_probe_width'])}/{html.escape(row['best_probe_skip'])}</td>"
        f"<td>{html.escape(row['best_probe_score'])}</td>"
        f"<td>{probe_link}</td>"
        "</tr>"
    )


def build_html(
    summary: dict[str, str],
    queue_rows: list[dict[str, str]],
    prefix_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "queue": queue_rows, "prefixes": prefix_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("queue.csv", output_dir / "queue.csv"),
            ("by_prefix.csv", output_dir / "by_prefix.csv"),
        )
    )
    table_rows = "\n".join(render_row(row, output_dir) for row in queue_rows)
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
  grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 10px;
}}
.stat {{
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--panel);
  padding: 10px;
}}
.label, .muted {{ color: var(--muted); }}
.value {{ font-size: 24px; font-weight: 750; line-height: 1.05; margin-top: 4px; }}
.ok {{ color: var(--ok); }}
.panel {{
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--panel);
  padding: 12px;
  overflow-x: auto;
}}
table {{ width: 100%; border-collapse: collapse; min-width: 980px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
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
    <div class="stat"><div class="label">Liens materiau</div><div class="value">{html.escape(summary['material_link_rows'])}</div></div>
    <div class="stat"><div class="label">Segments a decoder</div><div class="value">{html.escape(summary['queued_probe_segments'])}</div></div>
    <div class="stat"><div class="label">Segments decodes</div><div class="value">{html.escape(summary['decoded_material_segments'])}</div></div>
    <div class="stat"><div class="label">Unresolved uniques</div><div class="value">{html.escape(summary['unresolved_unique_pcx'])}</div></div>
    <div class="stat"><div class="label">Issues</div><div class="value ok">{html.escape(summary['issue_rows'])}</div></div>
  </section>
  <section class="panel">
    <div>{links}</div>
  </section>
  <section class="panel">
    <table>
      <thead><tr><th>Priorite</th><th>Status</th><th>Archive</th><th>PCX</th><th>Materiau</th><th>Prefixe</th><th>Taille</th><th>Probe w/skip</th><th>Score</th><th>Lien</th></tr></thead>
      <tbody>{table_rows}</tbody>
    </table>
  </section>
</main>
<script>
const TEX_MATERIAL_DECODER_QUEUE = {data_json};
</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    material_links: Path,
    augmented_references: Path,
    best_probes: Path,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    queue_rows = build_queue_rows(
        read_rows(material_links),
        read_rows(augmented_references),
        read_rows(best_probes),
    )
    prefix_rows = build_prefix_rows(queue_rows)
    summary = summary_row(queue_rows)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "queue.csv", QUEUE_FIELDNAMES, queue_rows)
    write_csv(output_dir / "by_prefix.csv", PREFIX_FIELDNAMES, prefix_rows)
    (output_dir / "index.html").write_text(build_html(summary, queue_rows, prefix_rows, output_dir, title))
    return summary, queue_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a prioritized .tex material decoder queue.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--material-links", type=Path, default=DEFAULT_MATERIAL_LINKS)
    parser.add_argument("--augmented-references", type=Path, default=DEFAULT_AUGMENTED_REFERENCES)
    parser.add_argument("--best-probes", type=Path, default=DEFAULT_BEST_PROBES)
    parser.add_argument("--title", default="Lands of Lore II .tex Material Decoder Queue")
    args = parser.parse_args()

    summary, _rows = write_report(
        args.output,
        args.material_links,
        args.augmented_references,
        args.best_probes,
        args.title,
    )
    print(f"Material link rows: {summary['material_link_rows']}")
    print(f"Queued probe rows: {summary['queued_probe_rows']}")
    print(f"Unresolved unique PCX: {summary['unresolved_unique_pcx']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"HTML: {args.output / 'index.html'}")
    if summary["issue_rows"] != "0" or summary["coverage_missing_rows"] != "0":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
