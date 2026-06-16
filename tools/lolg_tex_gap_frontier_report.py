#!/usr/bin/env python3
"""Analyze the frontiers between decoded .tex raw-copy runs and remaining gaps."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import struct
from pathlib import Path


DEFAULT_OUTPUT = Path("output/tex_gap_frontier_report")
DEFAULT_CLUSTERS = Path("output/tex_exact_chunk_clusters/clusters.csv")
DEFAULT_COMPARISONS = Path("output/tex_exact_cdcache_compare/comparisons.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "textures",
    "gaps",
    "internal_gaps",
    "leading_gaps",
    "trailing_gaps",
    "gaps_with_segment_window",
    "largest_pixel_gap",
    "largest_segment_gap",
    "issue_rows",
]

FRONTIER_FIELDNAMES = [
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "frontier_type",
    "gap_start",
    "gap_start_hex",
    "gap_start_x",
    "gap_start_y",
    "gap_end",
    "gap_end_hex",
    "gap_end_x",
    "gap_end_y",
    "pixel_gap",
    "left_cluster_id",
    "left_cluster_class",
    "left_pixel_end",
    "left_segment_end",
    "left_delta",
    "right_cluster_id",
    "right_cluster_class",
    "right_pixel_start",
    "right_segment_start",
    "right_delta",
    "delta_change",
    "segment_gap_start",
    "segment_gap_end",
    "segment_gap_bytes",
    "segment_gap_ratio",
    "segment_relation",
    "left_segment_tail_hex",
    "segment_gap_head_hex",
    "segment_gap_tail_hex",
    "right_segment_head_hex",
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


def int_value(row: dict[str, str], field: str) -> int:
    raw = row.get(field, "")
    return int(raw) if raw else 0


def read_mix_entry(path: Path, index: int) -> tuple[int, bytes]:
    data = path.read_bytes()
    if len(data) < 6:
        raise ValueError(f"{path}: too small to be a MIX archive")
    count, body_size = struct.unpack_from("<HI", data, 0)
    table_end = 6 + count * 12
    if index < 0 or index >= count or table_end > len(data):
        raise ValueError(f"{path}: invalid MIX entry index {index}")
    file_id, offset, size = struct.unpack_from("<III", data, 6 + index * 12)
    if offset + size > body_size:
        raise ValueError(f"{path}: entry {index} exceeds declared body size")
    return file_id, data[table_end + offset : table_end + offset + size]


def comparison_lookup(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    output = {}
    for row in rows:
        key = (row.get("archive", ""), row.get("pcx_name", ""))
        if key[0] and key[1]:
            output[key] = row
    return output


def grouped_clusters(rows: list[dict[str, str]]) -> dict[tuple[str, str], list[dict[str, str]]]:
    output: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in rows:
        if row.get("issues") or not row.get("pixel_start"):
            continue
        key = (row.get("archive", ""), row.get("pcx_name", ""))
        if key[0] and key[1]:
            output.setdefault(key, []).append(row)
    for group in output.values():
        group.sort(key=lambda row: (int_value(row, "pixel_start"), int_value(row, "segment_start")))
    return output


def covered_offsets(clusters: list[dict[str, str]], pixel_count: int) -> set[int]:
    covered: set[int] = set()
    for cluster in clusters:
        start = int_value(cluster, "pixel_start")
        span = int_value(cluster, "pixel_span_bytes")
        if span <= 0:
            span = int_value(cluster, "segment_span_bytes")
        for offset in range(max(0, start), min(pixel_count, start + span)):
            covered.add(offset)
    return covered


def find_gaps(covered: set[int], pixel_count: int) -> list[tuple[int, int]]:
    gaps: list[tuple[int, int]] = []
    start = -1
    for offset in range(pixel_count):
        if offset not in covered:
            if start < 0:
                start = offset
        elif start >= 0:
            gaps.append((start, offset - 1))
            start = -1
    if start >= 0:
        gaps.append((start, pixel_count - 1))
    return gaps


def segment_slice(data: bytes, start: int, end: int, limit: int) -> bytes:
    if not data or end < start:
        return b""
    start = max(0, start)
    end = min(len(data) - 1, end)
    if end < start:
        return b""
    if end - start + 1 <= limit:
        return data[start : end + 1]
    return data[start : start + limit]


def segment_tail(data: bytes, end: int, limit: int) -> bytes:
    if not data or end < 0:
        return b""
    end = min(end, len(data) - 1)
    start = max(0, end - limit + 1)
    return data[start : end + 1]


def segment_head(data: bytes, start: int, limit: int) -> bytes:
    if not data or start >= len(data):
        return b""
    start = max(0, start)
    return data[start : min(len(data), start + limit)]


def load_segment(
    archive_text: str,
    comparison: dict[str, str],
    payload_cache: dict[Path, bytes],
) -> tuple[bytes, list[str]]:
    issues: list[str] = []
    archive = Path(archive_text)
    if archive not in payload_cache:
        try:
            _file_id, payload_cache[archive] = read_mix_entry(archive, 2)
        except Exception as exc:
            payload_cache[archive] = b""
            issues.append(f"archive_read_failed:{exc}")
    payload = payload_cache[archive]
    body_offset = int(comparison.get("texture_body_offset") or 0)
    segment_size = int(comparison.get("texture_segment_size") or 0)
    segment = payload[body_offset : body_offset + segment_size]
    if len(segment) != segment_size:
        issues.append("segment_size_mismatch")
    return segment, issues


def nearest_left(clusters: list[dict[str, str]], gap_start: int) -> dict[str, str] | None:
    candidates = [row for row in clusters if int_value(row, "pixel_end") < gap_start]
    if not candidates:
        return None
    return max(candidates, key=lambda row: int_value(row, "pixel_end"))


def nearest_right(clusters: list[dict[str, str]], gap_end: int) -> dict[str, str] | None:
    candidates = [row for row in clusters if int_value(row, "pixel_start") > gap_end]
    if not candidates:
        return None
    return min(candidates, key=lambda row: int_value(row, "pixel_start"))


def build_frontiers(
    clusters: Path,
    comparisons: Path,
    *,
    context_bytes: int,
) -> list[dict[str, str]]:
    cluster_rows = read_rows(clusters)
    comparison_rows = read_rows(comparisons)
    comparisons_by_key = comparison_lookup(comparison_rows)
    clusters_by_key = grouped_clusters(cluster_rows)
    payload_cache: dict[Path, bytes] = {}
    rows: list[dict[str, str]] = []
    frontier_id = 1

    for key, group in sorted(clusters_by_key.items()):
        archive, pcx_name = key
        comparison = comparisons_by_key.get(key, {})
        width = int(comparison.get("cdcache_width") or 0)
        height = int(comparison.get("cdcache_height") or 0)
        pixel_count = width * height
        segment, segment_issues = load_segment(archive, comparison, payload_cache)
        covered = covered_offsets(group, pixel_count) if pixel_count else set()
        gaps = find_gaps(covered, pixel_count) if pixel_count else []
        for gap_start, gap_end in gaps:
            issues = list(segment_issues)
            left = nearest_left(group, gap_start)
            right = nearest_right(group, gap_end)
            if left and right:
                frontier_type = "internal"
                segment_gap_start = int_value(left, "segment_end") + 1
                segment_gap_end = int_value(right, "segment_start") - 1
            elif right:
                frontier_type = "leading"
                segment_gap_start = 0
                segment_gap_end = int_value(right, "segment_start") - 1
            elif left:
                frontier_type = "trailing"
                segment_gap_start = int_value(left, "segment_end") + 1
                segment_gap_end = len(segment) - 1
            else:
                frontier_type = "unbounded"
                segment_gap_start = 0
                segment_gap_end = len(segment) - 1
                issues.append("missing_frontier_clusters")

            segment_gap_bytes = segment_gap_end - segment_gap_start + 1
            if segment_gap_bytes < 0:
                segment_relation = "overlap"
            elif segment_gap_bytes == 0:
                segment_relation = "touching"
            else:
                segment_relation = "forward"
            pixel_gap = gap_end - gap_start + 1
            left_delta = int_value(left, "delta") if left else 0
            right_delta = int_value(right, "delta") if right else 0
            delta_change = right_delta - left_delta if left and right else 0
            rows.append(
                {
                    "archive": archive,
                    "archive_tag": Path(archive).stem.upper(),
                    "pcx_name": pcx_name,
                    "frontier_id": str(frontier_id),
                    "frontier_type": frontier_type,
                    "gap_start": str(gap_start),
                    "gap_start_hex": f"0x{gap_start:08x}",
                    "gap_start_x": str(gap_start % width if width else 0),
                    "gap_start_y": str(gap_start // width if width else 0),
                    "gap_end": str(gap_end),
                    "gap_end_hex": f"0x{gap_end:08x}",
                    "gap_end_x": str(gap_end % width if width else 0),
                    "gap_end_y": str(gap_end // width if width else 0),
                    "pixel_gap": str(pixel_gap),
                    "left_cluster_id": left.get("cluster_id", "") if left else "",
                    "left_cluster_class": left.get("cluster_class", "") if left else "",
                    "left_pixel_end": left.get("pixel_end", "") if left else "",
                    "left_segment_end": left.get("segment_end", "") if left else "",
                    "left_delta": left.get("delta", "") if left else "",
                    "right_cluster_id": right.get("cluster_id", "") if right else "",
                    "right_cluster_class": right.get("cluster_class", "") if right else "",
                    "right_pixel_start": right.get("pixel_start", "") if right else "",
                    "right_segment_start": right.get("segment_start", "") if right else "",
                    "right_delta": right.get("delta", "") if right else "",
                    "delta_change": str(delta_change),
                    "segment_gap_start": str(segment_gap_start),
                    "segment_gap_end": str(segment_gap_end),
                    "segment_gap_bytes": str(segment_gap_bytes),
                    "segment_gap_ratio": (
                        f"{(segment_gap_bytes / pixel_gap):.6f}"
                        if pixel_gap and segment_gap_bytes >= 0
                        else ""
                    ),
                    "segment_relation": segment_relation,
                    "left_segment_tail_hex": (
                        segment_tail(segment, int_value(left, "segment_end"), context_bytes).hex()
                        if left
                        else ""
                    ),
                    "segment_gap_head_hex": (
                        segment_head(segment, segment_gap_start, context_bytes).hex()
                        if segment_gap_bytes > 0
                        else ""
                    ),
                    "segment_gap_tail_hex": (
                        segment_tail(segment, segment_gap_end, context_bytes).hex()
                        if segment_gap_bytes > 0
                        else ""
                    ),
                    "right_segment_head_hex": (
                        segment_head(segment, int_value(right, "segment_start"), context_bytes).hex()
                        if right
                        else ""
                    ),
                    "issues": ";".join(issues),
                }
            )
            frontier_id += 1

    rows.sort(
        key=lambda row: (
            row.get("pcx_name", ""),
            -int_value(row, "pixel_gap"),
            int_value(row, "gap_start"),
        )
    )
    for index, row in enumerate(rows, start=1):
        row["frontier_id"] = str(index)
    return rows


def summary_row(rows: list[dict[str, str]]) -> dict[str, str]:
    valid_rows = [row for row in rows if not row.get("issues")]
    return {
        "scope": "total",
        "textures": str(len({(row.get("archive", ""), row.get("pcx_name", "")) for row in rows})),
        "gaps": str(len(rows)),
        "internal_gaps": str(sum(1 for row in rows if row.get("frontier_type") == "internal")),
        "leading_gaps": str(sum(1 for row in rows if row.get("frontier_type") == "leading")),
        "trailing_gaps": str(sum(1 for row in rows if row.get("frontier_type") == "trailing")),
        "gaps_with_segment_window": str(
            sum(1 for row in valid_rows if int_value(row, "segment_gap_bytes") > 0)
        ),
        "largest_pixel_gap": str(max((int_value(row, "pixel_gap") for row in rows), default=0)),
        "largest_segment_gap": str(max((int_value(row, "segment_gap_bytes") for row in valid_rows), default=0)),
        "issue_rows": str(sum(1 for row in rows if row.get("issues"))),
    }


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    if not path_text:
        return ""
    path = Path(path_text)
    try:
        relative = path.relative_to(base_dir)
    except ValueError:
        relative = Path(os.path.relpath(path, base_dir))
    return relative.as_posix()


def render_frontier_row(row: dict[str, str]) -> str:
    return (
        "<tr>"
        f"<td>{html.escape(row.get('pcx_name', ''))}</td>"
        f"<td>{html.escape(row.get('frontier_type', ''))}</td>"
        f"<td>{html.escape(row.get('pixel_gap', ''))}</td>"
        f"<td>{html.escape(row.get('segment_gap_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('segment_gap_ratio', ''))}</td>"
        f"<td>{html.escape(row.get('segment_relation', ''))}</td>"
        f"<td>{html.escape(row.get('delta_change', ''))}</td>"
        f"<td>{html.escape(row.get('gap_start_hex', ''))} ({html.escape(row.get('gap_start_x', ''))},{html.escape(row.get('gap_start_y', ''))})</td>"
        f"<td>{html.escape(row.get('gap_end_hex', ''))} ({html.escape(row.get('gap_end_x', ''))},{html.escape(row.get('gap_end_y', ''))})</td>"
        f"<td>{html.escape(row.get('left_cluster_id', ''))}/{html.escape(row.get('right_cluster_id', ''))}</td>"
        f"<td><code>{html.escape(row.get('segment_gap_head_hex', ''))}</code></td>"
        f"<td>{html.escape(row.get('issues', ''))}</td>"
        "</tr>"
    )


def build_html(summary: dict[str, str], rows: list[dict[str, str]], output_dir: Path, title: str) -> str:
    payload = {"summary": summary, "frontiers": rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("frontiers.csv", output_dir / "frontiers.csv"),
        )
    )
    table_rows = "\n".join(render_frontier_row(row) for row in rows)
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
.sub {{ color: var(--muted); margin-top: 4px; }}
main {{ padding: 16px 0 28px; display: grid; gap: 16px; }}
.stats {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 10px;
}}
.stat, .panel {{
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--panel);
  padding: 10px;
}}
.label, .muted {{ color: var(--muted); }}
.value {{ font-size: 24px; font-weight: 750; line-height: 1.05; margin-top: 4px; }}
.ok {{ color: var(--ok); }}
.panel {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; min-width: 1180px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 10px; }}
code {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; overflow-wrap: anywhere; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Frontieres entre runs raw-copy deja verifies et trous restants du decodeur .tex.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Gaps</div><div class="value">{html.escape(summary['gaps'])}</div></div>
    <div class="stat"><div class="label">Internes</div><div class="value">{html.escape(summary['internal_gaps'])}</div></div>
    <div class="stat"><div class="label">Largest pixel</div><div class="value">{html.escape(summary['largest_pixel_gap'])}</div></div>
    <div class="stat"><div class="label">Largest segment</div><div class="value">{html.escape(summary['largest_segment_gap'])}</div></div>
    <div class="stat"><div class="label">Issues</div><div class="value ok">{html.escape(summary['issue_rows'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div></section>
  <section class="panel">
    <table>
      <thead><tr><th>PCX</th><th>Type</th><th>Pixel gap</th><th>Segment gap</th><th>Ratio</th><th>Relation</th><th>Delta change</th><th>Start</th><th>End</th><th>L/R</th><th>Segment head</th><th>Issues</th></tr></thead>
      <tbody>{table_rows}</tbody>
    </table>
  </section>
</main>
<script>
const TEX_GAP_FRONTIER_REPORT = {data_json};
</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    clusters: Path,
    comparisons: Path,
    *,
    context_bytes: int,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = build_frontiers(clusters, comparisons, context_bytes=context_bytes)
    summary = summary_row(rows)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "frontiers.csv", FRONTIER_FIELDNAMES, rows)
    (output_dir / "index.html").write_text(build_html(summary, rows, output_dir, title))
    return summary, rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze partial .tex decoder gap frontiers.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--clusters", type=Path, default=DEFAULT_CLUSTERS)
    parser.add_argument("--comparisons", type=Path, default=DEFAULT_COMPARISONS)
    parser.add_argument("--context-bytes", type=int, default=32)
    parser.add_argument("--title", default="Lands of Lore II .tex Gap Frontier Report")
    args = parser.parse_args()

    summary, _rows = write_report(
        args.output,
        args.clusters,
        args.comparisons,
        context_bytes=args.context_bytes,
        title=args.title,
    )
    print(f"Gaps: {summary['gaps']}")
    print(f"Internal gaps: {summary['internal_gaps']}")
    print(f"Gaps with segment window: {summary['gaps_with_segment_window']}")
    print(f"Largest pixel gap: {summary['largest_pixel_gap']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
