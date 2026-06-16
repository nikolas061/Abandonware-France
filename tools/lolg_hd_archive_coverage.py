#!/usr/bin/env python3
"""Report Full HD export coverage for visual entries in game MIX archives."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import struct
from collections import Counter, defaultdict
from pathlib import Path


DEFAULT_OUTPUT = Path("output/fullhd_archive_coverage")
DEFAULT_VQA_MANIFEST = Path("output/vqa_batch_window_lcw_transparent0_allframes/manifest.csv")
DEFAULT_STILL_MANIFEST = Path("output/fullhd_images/manifest.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "archives",
    "entries",
    "visual_entries",
    "vqa_entries",
    "vqa_fullhd_entries",
    "vqa_fullhd_frames",
    "missing_vqa_fullhd_entries",
    "pcx_entries",
    "pcx_fullhd_entries",
    "missing_pcx_fullhd_entries",
    "other_entries",
    "issue_rows",
]

ARCHIVE_FIELDNAMES = [
    "archive",
    "archive_path",
    "entries",
    "visual_entries",
    "vqa_entries",
    "vqa_fullhd_entries",
    "vqa_fullhd_frames",
    "missing_vqa_fullhd_entries",
    "pcx_entries",
    "pcx_fullhd_entries",
    "missing_pcx_fullhd_entries",
    "other_entries",
    "entry_types",
    "issues",
]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def read_mix(path: Path) -> tuple[int, list[tuple[int, int, int]], bytes]:
    data = path.read_bytes()
    if len(data) < 6:
        raise ValueError("MIX header too short")
    count, _body_size = struct.unpack_from("<HI", data, 0)
    table_end = 6 + count * 12
    if len(data) < table_end:
        raise ValueError("MIX entry table truncated")
    entries = [struct.unpack_from("<III", data, 6 + index * 12) for index in range(count)]
    return table_end, entries, data


def classify_payload(payload: bytes) -> str:
    if len(payload) >= 12 and payload.startswith(b"FORM"):
        form_type = payload[8:12]
        if form_type == b"WVQA":
            return "VQA"
        if form_type == b"XDIR":
            return "XDIR"
        return f"FORM_{form_type.decode('ascii', errors='replace') or 'unknown'}"
    if payload[:4] in {b"\x0a\x05\x01\x08", b"\x0a\x00\x01\x08"}:
        return "PCX"
    if payload.startswith(b"HMI-MIDI"):
        return "HMI"
    if payload.startswith(b"This is a linear executable dll"):
        return "DLL"
    return "BIN"


def archive_key(path_text: str) -> str:
    return Path(path_text).name.upper() if path_text else ""


def index_key(value: str | int) -> str:
    if isinstance(value, int):
        return f"{value:04d}"
    if value.isdigit():
        return f"{int(value):04d}"
    return value


def load_vqa_coverage(path: Path) -> dict[tuple[str, str, str], dict[str, str]]:
    coverage: dict[tuple[str, str, str], dict[str, str]] = {}
    if not path.exists():
        return coverage
    for row in read_rows(path):
        key = (
            archive_key(row.get("archive", "")),
            index_key(row.get("index", "")),
            row.get("file_id", "").lower(),
        )
        coverage[key] = row
    return coverage


def load_pcx_coverage(path: Path) -> dict[tuple[str, str, str], dict[str, str]]:
    coverage: dict[tuple[str, str, str], dict[str, str]] = {}
    if not path.exists():
        return coverage
    for row in read_rows(path):
        if row.get("source_type") != "mix_pcx":
            continue
        key = (
            archive_key(row.get("source_path", "")),
            index_key(row.get("index", "")),
            row.get("file_id", "").lower(),
        )
        coverage[key] = row
    return coverage


def count_text(counter: Counter[str]) -> str:
    return ";".join(f"{key}:{value}" for key, value in sorted(counter.items()))


def coverage_rows(
    archives: list[Path],
    vqa_coverage: dict[tuple[str, str, str], dict[str, str]],
    pcx_coverage: dict[tuple[str, str, str], dict[str, str]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for archive in sorted(archives, key=lambda path: path.name.lower()):
        issues: list[str] = []
        try:
            table_end, entries, data = read_mix(archive)
        except Exception as exc:
            rows.append(
                {
                    "archive": archive.name,
                    "archive_path": str(archive),
                    "entries": "0",
                    "visual_entries": "0",
                    "vqa_entries": "0",
                    "vqa_fullhd_entries": "0",
                    "vqa_fullhd_frames": "0",
                    "missing_vqa_fullhd_entries": "0",
                    "pcx_entries": "0",
                    "pcx_fullhd_entries": "0",
                    "missing_pcx_fullhd_entries": "0",
                    "other_entries": "0",
                    "entry_types": "",
                    "issues": f"read_failed:{exc}",
                }
            )
            continue

        type_counts: Counter[str] = Counter()
        vqa_entries = 0
        vqa_fullhd_entries = 0
        vqa_fullhd_frames = 0
        pcx_entries = 0
        pcx_fullhd_entries = 0

        for index, (file_id, offset, size) in enumerate(entries):
            payload = data[table_end + offset : table_end + offset + size]
            kind = classify_payload(payload)
            type_counts[kind] += 1
            key = (archive.name.upper(), f"{index:04d}", f"{file_id:08x}")
            if kind == "VQA":
                vqa_entries += 1
                vqa_row = vqa_coverage.get(key)
                if vqa_row:
                    vqa_fullhd_entries += 1
                    vqa_fullhd_frames += int(vqa_row.get("fullhd_frames") or 0)
            elif kind == "PCX":
                pcx_entries += 1
                if key in pcx_coverage:
                    pcx_fullhd_entries += 1

        missing_vqa = vqa_entries - vqa_fullhd_entries
        missing_pcx = pcx_entries - pcx_fullhd_entries
        if missing_vqa:
            issues.append(f"missing_vqa_fullhd_entries:{missing_vqa}")
        if missing_pcx:
            issues.append(f"missing_pcx_fullhd_entries:{missing_pcx}")
        visual_entries = vqa_entries + pcx_entries
        rows.append(
            {
                "archive": archive.name,
                "archive_path": str(archive),
                "entries": str(len(entries)),
                "visual_entries": str(visual_entries),
                "vqa_entries": str(vqa_entries),
                "vqa_fullhd_entries": str(vqa_fullhd_entries),
                "vqa_fullhd_frames": str(vqa_fullhd_frames),
                "missing_vqa_fullhd_entries": str(missing_vqa),
                "pcx_entries": str(pcx_entries),
                "pcx_fullhd_entries": str(pcx_fullhd_entries),
                "missing_pcx_fullhd_entries": str(missing_pcx),
                "other_entries": str(len(entries) - visual_entries),
                "entry_types": count_text(type_counts),
                "issues": ";".join(issues),
            }
        )
    return rows


def int_value(row: dict[str, str], field: str) -> int:
    raw = row.get(field, "")
    return int(raw) if raw else 0


def summary_row(rows: list[dict[str, str]]) -> dict[str, str]:
    totals = defaultdict(int)
    for row in rows:
        for field in SUMMARY_FIELDNAMES:
            if field in {"scope", "archives"}:
                continue
            totals[field] += int_value(row, field)
        if row.get("issues"):
            totals["issue_rows"] += 1
    return {
        "scope": "total",
        "archives": str(len(rows)),
        "entries": str(totals["entries"]),
        "visual_entries": str(totals["visual_entries"]),
        "vqa_entries": str(totals["vqa_entries"]),
        "vqa_fullhd_entries": str(totals["vqa_fullhd_entries"]),
        "vqa_fullhd_frames": str(totals["vqa_fullhd_frames"]),
        "missing_vqa_fullhd_entries": str(totals["missing_vqa_fullhd_entries"]),
        "pcx_entries": str(totals["pcx_entries"]),
        "pcx_fullhd_entries": str(totals["pcx_fullhd_entries"]),
        "missing_pcx_fullhd_entries": str(totals["missing_pcx_fullhd_entries"]),
        "other_entries": str(totals["other_entries"]),
        "issue_rows": str(totals["issue_rows"]),
    }


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    if not path_text:
        return ""
    path = Path(path_text)
    try:
        relative = path.relative_to(base_dir)
    except ValueError:
        relative = Path(os.path.relpath(path, base_dir))
    return relative.as_posix()


def render_table(rows: list[dict[str, str]], columns: list[str]) -> str:
    head = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    body = []
    for row in rows:
        cells = "".join(f"<td>{html.escape(row.get(column, ''))}</td>" for column in columns)
        body.append(f"<tr>{cells}</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def build_html(summary: dict[str, str], rows: list[dict[str, str]], output_dir: Path, title: str) -> str:
    payload = {
        "summary": summary,
        "archives": rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    visual_rows = [row for row in rows if int_value(row, "visual_entries")]
    top_visual = sorted(
        visual_rows,
        key=lambda row: int_value(row, "vqa_fullhd_frames"),
        reverse=True,
    )
    summary_links = [
        ("archives.csv", output_dir / "archives.csv"),
        ("summary.csv", output_dir / "summary.csv"),
    ]
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in summary_links
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
table {{ width: 100%; min-width: 900px; border-collapse: collapse; }}
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
    <div class="stat"><div class="label">Archives</div><div class="value">{html.escape(summary['archives'])}</div></div>
    <div class="stat"><div class="label">Entrees visuelles</div><div class="value">{html.escape(summary['visual_entries'])}</div></div>
    <div class="stat"><div class="label">Frames VQA Full HD</div><div class="value">{html.escape(summary['vqa_fullhd_frames'])}</div></div>
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
    <h2>Archives avec assets visuels</h2>
    {render_table(top_visual, ARCHIVE_FIELDNAMES)}
  </section>
</main>
<script>
const COVERAGE = {data_json};
const archives = COVERAGE.archives;
</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    archives: list[Path],
    vqa_manifest: Path,
    still_manifest: Path,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    vqa_coverage = load_vqa_coverage(vqa_manifest)
    pcx_coverage = load_pcx_coverage(still_manifest)
    rows = coverage_rows(archives, vqa_coverage, pcx_coverage)
    summary = summary_row(rows)
    write_csv(output_dir / "archives.csv", ARCHIVE_FIELDNAMES, rows)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    (output_dir / "index.html").write_text(build_html(summary, rows, output_dir, title))
    return summary, rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Report Full HD coverage of visual MIX entries.")
    parser.add_argument("archives", nargs="+", type=Path)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--vqa-manifest", type=Path, default=DEFAULT_VQA_MANIFEST)
    parser.add_argument("--still-manifest", type=Path, default=DEFAULT_STILL_MANIFEST)
    parser.add_argument("--title", default="Lands of Lore II Full HD Archive Coverage")
    args = parser.parse_args()

    summary, _rows = write_report(
        args.output,
        args.archives,
        args.vqa_manifest,
        args.still_manifest,
        args.title,
    )
    print(f"Archives: {summary['archives']}")
    print(f"Visual entries: {summary['visual_entries']}")
    print(
        "Missing visual Full HD entries: "
        f"VQA={summary['missing_vqa_fullhd_entries']} PCX={summary['missing_pcx_fullhd_entries']}"
    )
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"HTML: {args.output / 'index.html'}")
    if summary["issue_rows"] != "0":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
