#!/usr/bin/env python3
"""Probe raw CDCACHE references that match still-missing .tex PCX names."""

from __future__ import annotations

import argparse
import bisect
import csv
import html
import json
import math
import os
import struct
from collections import Counter, defaultdict
from pathlib import Path


DEFAULT_OUTPUT = Path("output/cdcache_raw_reference_probe")
DEFAULT_CACHE = Path("C/LOLG/CDCACHE.MIX")
DEFAULT_EVIDENCE = Path("output/tex_missing_reference_evidence/evidence.csv")
DEFAULT_RAW_REFERENCES = Path("output/texture_report/cdcache_raw_references.csv")
DEFAULT_DESCRIPTORS = Path("output/texture_report/cdcache_descriptors.csv")
DEFAULT_PROBE_BYTES = 256
DEFAULT_MARKER_SCAN_BYTES = 512

MARKER_WORDS = {0x028E, 0x828E, 0x008F, 0x808F, 0x00A9, 0x80A9}
PRINTABLE = set(range(32, 127))

SUMMARY_FIELDNAMES = [
    "scope",
    "probe_rows",
    "unique_pcx",
    "archive_contexts",
    "source_path_rows",
    "rows_with_any_marker",
    "rows_with_zero_padded_marker",
    "rows_with_descriptor_candidates",
    "rows_with_next_descriptor_within_stride",
    "issue_rows",
]

PROBE_FIELDNAMES = [
    "archive",
    "archive_tag",
    "normalized_pcx_name",
    "raw_pcx_name",
    "raw_role",
    "name_offset",
    "name_offset_hex",
    "name_end_offset",
    "search_start_offset",
    "search_start_hex",
    "zero_padding_len",
    "first_marker_offset_hex",
    "first_marker_delta",
    "first_marker_word",
    "first_zero_padded_marker_offset_hex",
    "first_zero_padded_marker_delta",
    "first_zero_padded_marker_word",
    "descriptor_candidate_count",
    "descriptor_candidates",
    "previous_descriptor_offset_hex",
    "distance_from_previous_descriptor",
    "next_descriptor_offset_hex",
    "distance_to_next_descriptor",
    "window_entropy",
    "window_zero_ratio",
    "window_printable_ratio",
    "after_hex",
    "after_ascii",
    "issues",
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


def entropy(data: bytes) -> str:
    if not data:
        return ""
    counts = Counter(data)
    total = len(data)
    value = -sum((count / total) * math.log2(count / total) for count in counts.values())
    return f"{value:.4f}"


def ratio(count: int, total: int) -> str:
    return f"{count / total:.6f}" if total else ""


def ascii_preview(data: bytes) -> str:
    return "".join(chr(value) if value in PRINTABLE else "." for value in data)


def rows_by_name(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        name = normalize_pcx(row.get("base_name", "") or row.get("pcx_name", ""))
        if name:
            grouped[name].append(row)
    return grouped


def descriptor_offsets(rows: list[dict[str, str]]) -> list[int]:
    offsets = []
    for row in rows:
        try:
            offsets.append(int(row.get("descriptor_offset", "")))
        except ValueError:
            continue
    return sorted(offsets)


def nearest_descriptor_offsets(offsets: list[int], offset: int) -> tuple[int | None, int | None]:
    index = bisect.bisect_left(offsets, offset)
    previous = offsets[index - 1] if index > 0 else None
    following = offsets[index] if index < len(offsets) else None
    return previous, following


def marker_at(data: bytes, offset: int) -> int | None:
    if offset < 0 or offset + 2 > len(data):
        return None
    value = struct.unpack_from("<H", data, offset)[0]
    return value if value in MARKER_WORDS else None


def find_first_marker(data: bytes, start: int, end: int, *, zero_padded: bool) -> tuple[int, int] | None:
    limit = min(len(data), end)
    for offset in range(start, max(start, limit - 1)):
        marker = marker_at(data, offset)
        if marker is None:
            continue
        if zero_padded and any(data[index] != 0 for index in range(start, offset)):
            continue
        return offset, marker
    return None


def descriptor_candidates(data: bytes, start: int, end: int) -> list[str]:
    output: list[str] = []
    limit = min(len(data), end)
    for offset in range(start, max(start, limit - 21)):
        marker = marker_at(data, offset)
        if marker is None:
            continue
        (
            _marker,
            origin_x,
            origin_y,
            width,
            height,
            scale,
            cache_index,
        ) = struct.unpack_from("<HHHHHHH", data, offset)
        size = width * height
        data_offset = offset + 22
        plausible = (
            0 <= origin_x <= 1024
            and 0 <= origin_y <= 1024
            and 1 <= width <= 1024
            and 1 <= height <= 1024
            and scale in {1, 256}
            and data_offset + size <= len(data)
        )
        if plausible:
            output.append(
                (
                    f"0x{offset:08x}:{marker:04x}:{origin_x},{origin_y}:"
                    f"{width}x{height}:scale{scale}:idx{cache_index}:pad{offset - start}"
                )
            )
    return output


def raw_role(pcx_name: str) -> str:
    if ":" in pcx_name or "\\" in pcx_name or "/" in pcx_name:
        return "source_path"
    return "basename"


def build_probe_rows(
    cache: Path,
    evidence_rows: list[dict[str, str]],
    raw_rows_by_name: dict[str, list[dict[str, str]]],
    known_descriptor_offsets: list[int],
    probe_bytes: int,
    marker_scan_bytes: int,
) -> list[dict[str, str]]:
    data = cache.read_bytes()
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str, int]] = set()
    for evidence in evidence_rows:
        if int(evidence.get("raw_cache_same_archive_refs") or 0) <= 0:
            continue
        archive = evidence.get("archive", "")
        normalized = evidence.get("normalized_pcx_name", "")
        for raw in raw_rows_by_name.get(normalized, []):
            if archive not in split_values(raw.get("matched_texture_archives", "")):
                continue
            try:
                name_offset = int(raw["name_offset"])
            except ValueError:
                continue
            key = (archive, normalized, name_offset)
            if key in seen:
                continue
            seen.add(key)
            pcx_name = raw.get("pcx_name", "")
            name_bytes = pcx_name.encode("ascii", errors="replace")
            name_end = name_offset + len(name_bytes)
            issues: list[str] = []
            if name_offset < 0 or name_end > len(data):
                issues.append("name_offset_out_of_range")
                continue
            search_start = name_end + 1 if data[name_end : name_end + 1] == b"\0" else name_end
            window = data[search_start : min(len(data), search_start + probe_bytes)]
            zero_padding = 0
            for value in data[search_start : min(len(data), search_start + marker_scan_bytes)]:
                if value != 0:
                    break
                zero_padding += 1
            scan_end = search_start + marker_scan_bytes
            any_marker = find_first_marker(data, search_start, scan_end, zero_padded=False)
            zero_marker = find_first_marker(data, search_start, scan_end, zero_padded=True)
            candidates = descriptor_candidates(data, search_start, scan_end)
            previous_descriptor, next_descriptor = nearest_descriptor_offsets(
                known_descriptor_offsets,
                search_start,
            )
            rows.append(
                {
                    "archive": archive,
                    "archive_tag": archive_tag(archive),
                    "normalized_pcx_name": normalized,
                    "raw_pcx_name": pcx_name,
                    "raw_role": raw_role(pcx_name),
                    "name_offset": str(name_offset),
                    "name_offset_hex": f"0x{name_offset:08x}",
                    "name_end_offset": str(name_end),
                    "search_start_offset": str(search_start),
                    "search_start_hex": f"0x{search_start:08x}",
                    "zero_padding_len": str(zero_padding),
                    "first_marker_offset_hex": f"0x{any_marker[0]:08x}" if any_marker else "",
                    "first_marker_delta": str(any_marker[0] - search_start) if any_marker else "",
                    "first_marker_word": f"{any_marker[1]:04x}" if any_marker else "",
                    "first_zero_padded_marker_offset_hex": (
                        f"0x{zero_marker[0]:08x}" if zero_marker else ""
                    ),
                    "first_zero_padded_marker_delta": (
                        str(zero_marker[0] - search_start) if zero_marker else ""
                    ),
                    "first_zero_padded_marker_word": f"{zero_marker[1]:04x}" if zero_marker else "",
                    "descriptor_candidate_count": str(len(candidates)),
                    "descriptor_candidates": ";".join(candidates[:8]),
                    "previous_descriptor_offset_hex": (
                        f"0x{previous_descriptor:08x}" if previous_descriptor is not None else ""
                    ),
                    "distance_from_previous_descriptor": (
                        str(search_start - previous_descriptor) if previous_descriptor is not None else ""
                    ),
                    "next_descriptor_offset_hex": (
                        f"0x{next_descriptor:08x}" if next_descriptor is not None else ""
                    ),
                    "distance_to_next_descriptor": (
                        str(next_descriptor - search_start) if next_descriptor is not None else ""
                    ),
                    "window_entropy": entropy(window),
                    "window_zero_ratio": ratio(window.count(0), len(window)),
                    "window_printable_ratio": ratio(sum(1 for value in window if value in PRINTABLE), len(window)),
                    "after_hex": window[:128].hex(),
                    "after_ascii": ascii_preview(window[:128]),
                    "issues": ";".join(issues),
                }
            )
    return sorted(rows, key=lambda row: (row["archive"], row["normalized_pcx_name"], int(row["name_offset"])))


def summary_row(rows: list[dict[str, str]]) -> dict[str, str]:
    archive_contexts = {(row["archive"], row["normalized_pcx_name"]) for row in rows}
    return {
        "scope": "total",
        "probe_rows": str(len(rows)),
        "unique_pcx": str(len({row["normalized_pcx_name"] for row in rows})),
        "archive_contexts": str(len(archive_contexts)),
        "source_path_rows": str(sum(1 for row in rows if row["raw_role"] == "source_path")),
        "rows_with_any_marker": str(sum(1 for row in rows if row["first_marker_offset_hex"])),
        "rows_with_zero_padded_marker": str(
            sum(1 for row in rows if row["first_zero_padded_marker_offset_hex"])
        ),
        "rows_with_descriptor_candidates": str(
            sum(1 for row in rows if int(row["descriptor_candidate_count"]) > 0)
        ),
        "rows_with_next_descriptor_within_stride": str(
            sum(
                1
                for row in rows
                if row["distance_to_next_descriptor"]
                and int(row["distance_to_next_descriptor"]) <= 0x1039
            )
        ),
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
    rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "probes": rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("raw_reference_probe.csv", output_dir / "raw_reference_probe.csv"),
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
h2 {{ margin: 0 0 10px; font-size: 16px; }}
table {{ width: 100%; min-width: 1280px; border-collapse: collapse; }}
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
    <div class="stat"><div class="label">Sondes</div><div class="value">{html.escape(summary['probe_rows'])}</div></div>
    <div class="stat"><div class="label">Noms uniques</div><div class="value">{html.escape(summary['unique_pcx'])}</div></div>
    <div class="stat"><div class="label">Marqueurs proches</div><div class="value">{html.escape(summary['rows_with_any_marker'])}</div></div>
    <div class="stat"><div class="label">Candidats descriptor</div><div class="value">{html.escape(summary['rows_with_descriptor_candidates'])}</div></div>
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
    <h2>Sondes brutes CDCACHE</h2>
    {render_table(rows, PROBE_FIELDNAMES)}
  </section>
</main>
<script>
const CDCACHE_RAW_REFERENCE_PROBE = {data_json};
</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    cache: Path,
    evidence: Path,
    raw_references: Path,
    descriptors: Path,
    probe_bytes: int,
    marker_scan_bytes: int,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = build_probe_rows(
        cache,
        read_rows(evidence),
        rows_by_name(read_rows(raw_references)),
        descriptor_offsets(read_rows(descriptors)),
        probe_bytes,
        marker_scan_bytes,
    )
    summary = summary_row(rows)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "raw_reference_probe.csv", PROBE_FIELDNAMES, rows)
    (output_dir / "index.html").write_text(build_html(summary, rows, output_dir, title))
    return summary, rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe raw CDCACHE references for missing .tex names.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--raw-references", type=Path, default=DEFAULT_RAW_REFERENCES)
    parser.add_argument("--descriptors", type=Path, default=DEFAULT_DESCRIPTORS)
    parser.add_argument("--probe-bytes", type=int, default=DEFAULT_PROBE_BYTES)
    parser.add_argument("--marker-scan-bytes", type=int, default=DEFAULT_MARKER_SCAN_BYTES)
    parser.add_argument("--title", default="Lands of Lore II CDCACHE Raw Reference Probe")
    args = parser.parse_args()

    summary, _rows = write_report(
        args.output,
        args.cache,
        args.evidence,
        args.raw_references,
        args.descriptors,
        args.probe_bytes,
        args.marker_scan_bytes,
        args.title,
    )
    print(f"Probe rows: {summary['probe_rows']}")
    print(f"Unique PCX: {summary['unique_pcx']}")
    print(f"Rows with descriptor candidates: {summary['rows_with_descriptor_candidates']}")
    print(f"Rows with any marker: {summary['rows_with_any_marker']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"HTML: {args.output / 'index.html'}")
    if summary["issue_rows"] != "0":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
