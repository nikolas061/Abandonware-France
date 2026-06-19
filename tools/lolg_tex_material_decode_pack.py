#!/usr/bin/env python3
"""Pack rank-1 material .tex probe previews as decoded Full HD candidates."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import re
from collections import Counter
from pathlib import Path


DEFAULT_OUTPUT = Path("output/tex_material_decode_pack")
DEFAULT_BEST_PROBES = Path("output/tex_unresolved_material_probe_render/best_candidates.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "decoded_assets",
    "unique_pcx",
    "segments",
    "fullhd_assets",
    "native_assets",
    "missing_source_fullhd_paths",
    "missing_source_native_paths",
    "missing_decoded_fullhd_paths",
    "missing_decoded_native_paths",
    "target_mismatch_rows",
    "issue_rows",
    "best_score",
    "median_score",
]

MANIFEST_FIELDNAMES = [
    "asset_id",
    "archive",
    "archive_tag",
    "pcx_name",
    "normalized_pcx_name",
    "material_clean_text",
    "segment_index",
    "body_offset",
    "body_offset_hex",
    "body_first_word",
    "segment_size",
    "skip",
    "width",
    "height",
    "source_native_path",
    "source_fullhd_path",
    "decoded_native_path",
    "decoded_fullhd_path",
    "source_native_exists",
    "source_fullhd_exists",
    "decoded_native_exists",
    "decoded_fullhd_exists",
    "native_target_matches_source",
    "fullhd_target_matches_source",
    "structure_score",
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


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._") or "unnamed"


def normalize_pcx(name: str) -> str:
    return Path(name.replace("\\", "/")).name.lower()


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


def float_value(row: dict[str, str], field: str) -> float:
    raw = row.get(field, "")
    try:
        return float(raw) if raw else 0.0
    except ValueError:
        return 0.0


def rank1_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    selected: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for row in rows:
        if row.get("rank") != "1":
            continue
        key = (
            row.get("archive", ""),
            normalize_pcx(row.get("pcx_name", "")),
            row.get("segment_index", ""),
            row.get("body_offset", ""),
        )
        if key in seen:
            continue
        seen.add(key)
        selected.append(row)
    return sorted(
        selected,
        key=lambda row: (
            row.get("archive_tag", ""),
            normalize_pcx(row.get("pcx_name", "")),
            int(row.get("segment_index") or 0),
            int(row.get("body_offset") or 0),
        ),
    )


def link_source(source_path_text: str, target_path: Path, issues: list[str], label: str) -> tuple[str, str]:
    if not source_path_text:
        issues.append(f"missing_source_{label}_path")
        return "no", "no"

    source_path = Path(source_path_text)
    if not source_path.exists():
        issues.append(f"missing_source_{label}_path")
        return "no", "no"

    target_path.parent.mkdir(parents=True, exist_ok=True)
    if target_path.exists() or target_path.is_symlink():
        target_path.unlink()
    target_path.symlink_to(relative_symlink(source_path, target_path))

    target_exists = target_path.exists()
    target_matches = target_exists and os.path.realpath(target_path) == os.path.realpath(source_path)
    if not target_exists:
        issues.append(f"missing_decoded_{label}_path")
    if not target_matches:
        issues.append(f"{label}_target_mismatch")
    return "yes" if target_exists else "no", "yes" if target_matches else "no"


def asset_id_for(row: dict[str, str]) -> str:
    archive_tag = row.get("archive_tag", "") or Path(row.get("archive", "")).stem.upper()
    offset = row.get("body_offset_hex", "") or f"off{int(row.get('body_offset') or 0):08x}"
    normalized = normalize_pcx(row.get("pcx_name", ""))
    return (
        f"{safe_name(archive_tag)}__{safe_name(normalized)}"
        f"__seg{safe_name(row.get('segment_index', ''))}_{safe_name(offset)}"
        f"_w{safe_name(row.get('width', ''))}_skip{safe_name(row.get('skip', ''))}"
    )


def build_manifest(output_dir: Path, best_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in rank1_rows(best_rows):
        archive_tag = row.get("archive_tag", "") or Path(row.get("archive", "")).stem.upper()
        asset_id = asset_id_for(row)
        target_dir = output_dir / "descriptors" / safe_name(archive_tag)
        native_dir = output_dir / "native" / safe_name(archive_tag)
        decoded_fullhd_path = target_dir / f"{asset_id}.png"
        decoded_native_path = native_dir / f"{asset_id}_native.png"
        issues: list[str] = []

        source_fullhd_path = row.get("fullhd_path", "")
        source_native_path = row.get("native_path", "")
        decoded_fullhd_exists, fullhd_matches = link_source(
            source_fullhd_path,
            decoded_fullhd_path,
            issues,
            "fullhd",
        )
        decoded_native_exists, native_matches = link_source(
            source_native_path,
            decoded_native_path,
            issues,
            "native",
        )

        rows.append(
            {
                "asset_id": asset_id,
                "archive": row.get("archive", ""),
                "archive_tag": archive_tag,
                "pcx_name": row.get("pcx_name", ""),
                "normalized_pcx_name": normalize_pcx(row.get("pcx_name", "")),
                "material_clean_text": row.get("material_clean_text", ""),
                "segment_index": row.get("segment_index", ""),
                "body_offset": row.get("body_offset", ""),
                "body_offset_hex": row.get("body_offset_hex", ""),
                "body_first_word": row.get("body_first_word", ""),
                "segment_size": row.get("segment_size", ""),
                "skip": row.get("skip", ""),
                "width": row.get("width", ""),
                "height": row.get("height", ""),
                "source_native_path": source_native_path,
                "source_fullhd_path": source_fullhd_path,
                "decoded_native_path": str(decoded_native_path),
                "decoded_fullhd_path": str(decoded_fullhd_path),
                "source_native_exists": "yes" if source_native_path and Path(source_native_path).exists() else "no",
                "source_fullhd_exists": "yes" if source_fullhd_path and Path(source_fullhd_path).exists() else "no",
                "decoded_native_exists": decoded_native_exists,
                "decoded_fullhd_exists": decoded_fullhd_exists,
                "native_target_matches_source": native_matches,
                "fullhd_target_matches_source": fullhd_matches,
                "structure_score": row.get("structure_score", ""),
                "issues": ";".join(issues),
            }
        )
    return rows


def summary_row(rows: list[dict[str, str]]) -> dict[str, str]:
    scores = sorted(float_value(row, "structure_score") for row in rows if not row.get("issues"))
    best = max(scores) if scores else 0.0
    median = scores[len(scores) // 2] if scores else 0.0
    segments = {
        (row["archive"], row["normalized_pcx_name"], row["segment_index"], row["body_offset"])
        for row in rows
    }
    issue_counts = Counter(issue for row in rows for issue in row["issues"].split(";") if issue)
    return {
        "scope": "total",
        "decoded_assets": str(len(rows)),
        "unique_pcx": str(len({row["normalized_pcx_name"] for row in rows})),
        "segments": str(len(segments)),
        "fullhd_assets": str(sum(1 for row in rows if row["decoded_fullhd_exists"] == "yes")),
        "native_assets": str(sum(1 for row in rows if row["decoded_native_exists"] == "yes")),
        "missing_source_fullhd_paths": str(issue_counts.get("missing_source_fullhd_path", 0)),
        "missing_source_native_paths": str(issue_counts.get("missing_source_native_path", 0)),
        "missing_decoded_fullhd_paths": str(issue_counts.get("missing_decoded_fullhd_path", 0)),
        "missing_decoded_native_paths": str(issue_counts.get("missing_decoded_native_path", 0)),
        "target_mismatch_rows": str(
            sum(
                1
                for row in rows
                if row["fullhd_target_matches_source"] != "yes" or row["native_target_matches_source"] != "yes"
            )
        ),
        "issue_rows": str(sum(1 for row in rows if row["issues"])),
        "best_score": f"{best:.6f}",
        "median_score": f"{median:.6f}",
    }


def render_card(row: dict[str, str], output_dir: Path) -> str:
    image = html.escape(relative_href(row.get("decoded_fullhd_path", ""), output_dir))
    native = html.escape(relative_href(row.get("decoded_native_path", ""), output_dir))
    title = f"{row.get('normalized_pcx_name', '')} / {row.get('archive_tag', '')}"
    return f"""
<article class="card">
  <a class="preview" href="{image}"><img src="{image}" loading="lazy" decoding="async" alt=""></a>
  <div class="body">
    <div class="title">{html.escape(title)}</div>
    <div class="muted">seg {html.escape(row.get('segment_index', ''))} off {html.escape(row.get('body_offset_hex', ''))}</div>
    <div class="muted">w {html.escape(row.get('width', ''))} / skip {html.escape(row.get('skip', ''))} / score {html.escape(row.get('structure_score', ''))}</div>
    <div><a href="{native}">native</a></div>
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
.label, .muted {{ color: var(--muted); }}
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
.grid {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
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
  background: #050607;
}}
.preview img {{ width: 100%; height: 100%; object-fit: contain; display: block; }}
.body {{ padding: 10px; display: grid; gap: 4px; }}
.title {{ font-weight: 700; }}
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
    <div class="stat"><div class="label">Assets decodes</div><div class="value ok">{html.escape(summary['decoded_assets'])}</div></div>
    <div class="stat"><div class="label">PCX uniques</div><div class="value">{html.escape(summary['unique_pcx'])}</div></div>
    <div class="stat"><div class="label">Segments</div><div class="value">{html.escape(summary['segments'])}</div></div>
    <div class="stat"><div class="label">Issues</div><div class="value warn">{html.escape(summary['issue_rows'])}</div></div>
  </section>
  <section class="panel">
    <div>{links}</div>
  </section>
  <section class="grid">
    {cards}
  </section>
</main>
<script>
const TEX_MATERIAL_DECODE_PACK = {data_json};
</script>
</body>
</html>
"""


def write_report(output_dir: Path, best_probes: Path, title: str) -> tuple[dict[str, str], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = build_manifest(output_dir, read_rows(best_probes))
    summary = summary_row(rows)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "manifest.csv", MANIFEST_FIELDNAMES, rows)
    (output_dir / "index.html").write_text(build_html(summary, rows, output_dir, title))
    return summary, rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Pack decoded .tex material probe candidates.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--best-probes", type=Path, default=DEFAULT_BEST_PROBES)
    parser.add_argument("--title", default="Lands of Lore II .tex Material Decode Pack")
    args = parser.parse_args()

    summary, _rows = write_report(args.output, args.best_probes, args.title)
    print(f"Decoded material assets: {summary['decoded_assets']}")
    print(f"Unique PCX: {summary['unique_pcx']}")
    print(f"Segments: {summary['segments']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"HTML: {args.output / 'index.html'}")
    if summary["issue_rows"] != "0":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
