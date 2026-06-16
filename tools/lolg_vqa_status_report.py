#!/usr/bin/env python3
"""Summarize frame-by-frame VQA render/export coverage."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
from collections import Counter, defaultdict
from pathlib import Path


DEFAULT_BATCH_DIR = Path("output/vqa_batch_window_lcw_transparent0_allframes")

SUMMARY_FIELDNAMES = [
    "scope",
    "entries",
    "archives",
    "declared_frames",
    "expected_frames",
    "render_rows",
    "rendered_rows",
    "held_frame_rows",
    "non_output_rows",
    "native_frames",
    "fullhd_frames",
    "missing_native_output_files",
    "missing_fullhd_output_files",
    "missing_frame_rows",
    "duplicate_frame_rows",
    "issue_rows",
    "render_status_counts",
    "pointer_chunks",
    "pointer_decode_statuses",
    "render_notes",
]

ARCHIVE_FIELDNAMES = [
    "archive_tag",
    "archive",
    "entries",
    "declared_frames",
    "expected_frames",
    "rendered_rows",
    "held_frame_rows",
    "non_output_rows",
    "native_frames",
    "fullhd_frames",
    "issue_rows",
    "resolutions",
    "pointer_chunks",
    "pointer_decode_statuses",
]

RESOLUTION_FIELDNAMES = [
    "resolution",
    "entries",
    "declared_frames",
    "fullhd_frames",
    "archives",
    "pointer_chunks",
]

POINTER_FIELDNAMES = [
    "pointer_chunk",
    "pointer_decode_status",
    "entries",
    "declared_frames",
    "fullhd_frames",
    "archives",
    "resolutions",
]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def int_value(row: dict[str, str], field: str) -> int:
    raw = row.get(field, "")
    return int(raw) if raw else 0


def archive_tag(path_text: str) -> str:
    return Path(path_text).stem.upper() if path_text else "UNKNOWN"


def count_text(counter: Counter[str]) -> str:
    return ";".join(f"{key}:{count}" for key, count in sorted(counter.items()))


def split_counts(text: str) -> Counter[str]:
    counts: Counter[str] = Counter()
    for part in text.split(";"):
        if not part:
            continue
        key, _, raw_count = part.partition(":")
        if not key:
            continue
        try:
            counts[key] += int(raw_count)
        except ValueError:
            counts[key] += 1
    return counts


def note_category(note: str) -> str:
    if note.startswith("CBP appended"):
        return "CBP appended vectors"
    return note


class Totals:
    def __init__(self) -> None:
        self.entries = 0
        self.archives: set[str] = set()
        self.declared_frames = 0
        self.expected_frames = 0
        self.render_rows = 0
        self.rendered_rows = 0
        self.held_frame_rows = 0
        self.non_output_rows = 0
        self.native_frames = 0
        self.fullhd_frames = 0
        self.missing_native_output_files = 0
        self.missing_fullhd_output_files = 0
        self.missing_frame_rows = 0
        self.duplicate_frame_rows = 0
        self.issue_rows = 0
        self.render_status_counts: Counter[str] = Counter()
        self.pointer_chunks: Counter[str] = Counter()
        self.pointer_decode_statuses: Counter[str] = Counter()
        self.render_notes: Counter[str] = Counter()
        self.resolutions: Counter[str] = Counter()

    def add(self, verify_row: dict[str, str], manifest_row: dict[str, str]) -> None:
        archive = verify_row.get("archive", "")
        self.entries += 1
        if archive:
            self.archives.add(archive)
        self.declared_frames += int_value(verify_row, "declared_frames")
        self.expected_frames += int_value(verify_row, "expected_frames")
        self.render_rows += int_value(verify_row, "render_rows")
        self.rendered_rows += int_value(verify_row, "rendered_rows")
        self.held_frame_rows += int_value(verify_row, "held_frame_rows")
        self.non_output_rows += int_value(verify_row, "non_output_rows")
        self.native_frames += int_value(verify_row, "native_frames")
        self.fullhd_frames += int_value(verify_row, "fullhd_frames")
        self.missing_native_output_files += int_value(verify_row, "missing_native_output_files")
        self.missing_fullhd_output_files += int_value(verify_row, "missing_fullhd_output_files")
        self.missing_frame_rows += int_value(verify_row, "missing_frame_rows")
        self.duplicate_frame_rows += int_value(verify_row, "duplicate_frame_rows")
        if verify_row.get("issues"):
            self.issue_rows += 1
        self.render_status_counts.update(split_counts(verify_row.get("render_status_counts", "")))
        pointer_chunk = manifest_row.get("pointer_chunk", "") or "unknown"
        pointer_status = manifest_row.get("pointer_decode_status", "") or "unknown"
        self.pointer_chunks[pointer_chunk] += 1
        self.pointer_decode_statuses[pointer_status] += 1
        width = manifest_row.get("width", "")
        height = manifest_row.get("height", "")
        if width and height:
            self.resolutions[f"{width}x{height}"] += 1
        note = manifest_row.get("render_note", "")
        if note:
            for part in note.split(";"):
                clean = part.strip()
                if clean:
                    self.render_notes[note_category(clean)] += 1

    def summary_row(self, scope: str) -> dict[str, str]:
        return {
            "scope": scope,
            "entries": str(self.entries),
            "archives": str(len(self.archives)),
            "declared_frames": str(self.declared_frames),
            "expected_frames": str(self.expected_frames),
            "render_rows": str(self.render_rows),
            "rendered_rows": str(self.rendered_rows),
            "held_frame_rows": str(self.held_frame_rows),
            "non_output_rows": str(self.non_output_rows),
            "native_frames": str(self.native_frames),
            "fullhd_frames": str(self.fullhd_frames),
            "missing_native_output_files": str(self.missing_native_output_files),
            "missing_fullhd_output_files": str(self.missing_fullhd_output_files),
            "missing_frame_rows": str(self.missing_frame_rows),
            "duplicate_frame_rows": str(self.duplicate_frame_rows),
            "issue_rows": str(self.issue_rows),
            "render_status_counts": count_text(self.render_status_counts),
            "pointer_chunks": count_text(self.pointer_chunks),
            "pointer_decode_statuses": count_text(self.pointer_decode_statuses),
            "render_notes": count_text(self.render_notes),
        }


def key_for(row: dict[str, str]) -> tuple[str, str, str]:
    return (row.get("archive", ""), row.get("index", ""), row.get("file_id", ""))


def build_reports(batch_dir: Path) -> tuple[
    dict[str, str],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
]:
    manifest_rows = read_rows(batch_dir / "manifest.csv")
    verify_rows = read_rows(batch_dir / "verification.csv")
    manifest_by_key = {key_for(row): row for row in manifest_rows}

    total = Totals()
    by_archive: dict[str, Totals] = defaultdict(Totals)
    archive_paths: dict[str, str] = {}
    by_resolution: dict[str, Totals] = defaultdict(Totals)
    by_pointer: dict[tuple[str, str], Totals] = defaultdict(Totals)

    for verify_row in verify_rows:
        manifest_row = manifest_by_key.get(key_for(verify_row), {})
        total.add(verify_row, manifest_row)

        tag = archive_tag(verify_row.get("archive", ""))
        archive_paths[tag] = verify_row.get("archive", "")
        by_archive[tag].add(verify_row, manifest_row)

        resolution = f"{manifest_row.get('width', '')}x{manifest_row.get('height', '')}"
        if resolution != "x":
            by_resolution[resolution].add(verify_row, manifest_row)

        pointer_key = (
            manifest_row.get("pointer_chunk", "") or "unknown",
            manifest_row.get("pointer_decode_status", "") or "unknown",
        )
        by_pointer[pointer_key].add(verify_row, manifest_row)

    archive_rows = []
    for tag, stats in sorted(by_archive.items(), key=lambda item: item[0].lower()):
        row = stats.summary_row(tag)
        archive_rows.append(
            {
                "archive_tag": tag,
                "archive": archive_paths.get(tag, ""),
                "entries": row["entries"],
                "declared_frames": row["declared_frames"],
                "expected_frames": row["expected_frames"],
                "rendered_rows": row["rendered_rows"],
                "held_frame_rows": row["held_frame_rows"],
                "non_output_rows": row["non_output_rows"],
                "native_frames": row["native_frames"],
                "fullhd_frames": row["fullhd_frames"],
                "issue_rows": row["issue_rows"],
                "resolutions": count_text(stats.resolutions),
                "pointer_chunks": row["pointer_chunks"],
                "pointer_decode_statuses": row["pointer_decode_statuses"],
            }
        )

    resolution_rows = []
    for resolution, stats in sorted(
        by_resolution.items(),
        key=lambda item: (-item[1].fullhd_frames, item[0]),
    ):
        resolution_rows.append(
            {
                "resolution": resolution,
                "entries": str(stats.entries),
                "declared_frames": str(stats.declared_frames),
                "fullhd_frames": str(stats.fullhd_frames),
                "archives": str(len(stats.archives)),
                "pointer_chunks": count_text(stats.pointer_chunks),
            }
        )

    pointer_rows = []
    for (pointer_chunk, pointer_status), stats in sorted(
        by_pointer.items(),
        key=lambda item: (-item[1].fullhd_frames, item[0][0], item[0][1]),
    ):
        pointer_rows.append(
            {
                "pointer_chunk": pointer_chunk,
                "pointer_decode_status": pointer_status,
                "entries": str(stats.entries),
                "declared_frames": str(stats.declared_frames),
                "fullhd_frames": str(stats.fullhd_frames),
                "archives": str(len(stats.archives)),
                "resolutions": count_text(stats.resolutions),
            }
        )

    return total.summary_row("total"), archive_rows, resolution_rows, pointer_rows


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
    archive_rows: list[dict[str, str]],
    resolution_rows: list[dict[str, str]],
    pointer_rows: list[dict[str, str]],
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "archives": archive_rows,
        "resolutions": resolution_rows,
        "pointers": pointer_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    top_archives = sorted(
        archive_rows,
        key=lambda row: int(row["fullhd_frames"]),
        reverse=True,
    )[:24]
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
table {{ width: 100%; min-width: 860px; border-collapse: collapse; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
td {{ overflow-wrap: anywhere; }}
script {{ display: none; }}
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
    <div class="stat"><div class="label">Entrees VQA</div><div class="value">{html.escape(summary['entries'])}</div></div>
    <div class="stat"><div class="label">Archives</div><div class="value">{html.escape(summary['archives'])}</div></div>
    <div class="stat"><div class="label">Frames Full HD</div><div class="value">{html.escape(summary['fullhd_frames'])}</div></div>
    <div class="stat"><div class="label">Issues</div><div class="value ok">{html.escape(summary['issue_rows'])}</div></div>
  </section>
  <section class="panel">
    <h2>Synthese</h2>
    {render_table([summary], SUMMARY_FIELDNAMES)}
  </section>
  <section class="panel">
    <h2>Archives principales</h2>
    {render_table(top_archives, ARCHIVE_FIELDNAMES)}
  </section>
  <section class="panel">
    <h2>Resolutions natives</h2>
    {render_table(resolution_rows, RESOLUTION_FIELDNAMES)}
  </section>
  <section class="panel">
    <h2>Pointeurs VQA</h2>
    {render_table(pointer_rows, POINTER_FIELDNAMES)}
  </section>
</main>
<script>
const REPORT = {data_json};
const byArchive = REPORT.archives;
</script>
</body>
</html>
"""


def write_reports(batch_dir: Path, title: str) -> tuple[dict[str, str], int, int, int]:
    summary, archive_rows, resolution_rows, pointer_rows = build_reports(batch_dir)
    write_csv(batch_dir / "status_summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(batch_dir / "status_by_archive.csv", ARCHIVE_FIELDNAMES, archive_rows)
    write_csv(batch_dir / "status_by_resolution.csv", RESOLUTION_FIELDNAMES, resolution_rows)
    write_csv(batch_dir / "status_by_pointer.csv", POINTER_FIELDNAMES, pointer_rows)
    (batch_dir / "status.html").write_text(
        build_html(summary, archive_rows, resolution_rows, pointer_rows, title)
    )
    return summary, len(archive_rows), len(resolution_rows), len(pointer_rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize VQA frame-by-frame Full HD coverage.")
    parser.add_argument("batch_dir", nargs="?", type=Path, default=DEFAULT_BATCH_DIR)
    parser.add_argument("--title", default="Lands of Lore II VQA Full HD Status")
    args = parser.parse_args()

    summary, archives, resolutions, pointers = write_reports(args.batch_dir, args.title)
    print(f"VQA entries: {summary['entries']}")
    print(f"Full HD frames: {summary['fullhd_frames']}")
    print(f"Archives: {archives}; resolutions: {resolutions}; pointer groups: {pointers}")
    print(f"Issue rows: {summary['issue_rows']}")
    if summary["issue_rows"] != "0":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
