#!/usr/bin/env python3
"""Cluster exact .tex/CDCACHE chunk scan rows into contiguous decoder runs."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
from collections import Counter
from pathlib import Path


DEFAULT_OUTPUT = Path("output/tex_exact_chunk_clusters")
DEFAULT_SCAN = Path("output/tex_exact_chunk_scan/scan.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "scan_rows",
    "clusters",
    "matched_segments",
    "unique_pcx",
    "chunk_sizes",
    "max_gap",
    "min_rows",
    "strong_clusters",
    "medium_clusters",
    "weak_clusters",
    "longest_pixel_span",
    "longest_segment_span",
    "issue_rows",
]

CLUSTER_FIELDNAMES = [
    "archive",
    "archive_tag",
    "pcx_name",
    "chunk_size",
    "cluster_id",
    "cluster_class",
    "delta",
    "delta_hex",
    "rows",
    "pixel_start",
    "pixel_end",
    "pixel_start_hex",
    "pixel_end_hex",
    "pixel_start_x",
    "pixel_start_y",
    "pixel_end_x",
    "pixel_end_y",
    "segment_start",
    "segment_end",
    "segment_start_hex",
    "segment_end_hex",
    "pixel_span_bytes",
    "segment_span_bytes",
    "avg_entropy",
    "max_entropy",
    "min_zero_ratio",
    "max_zero_ratio",
    "first_chunk_hex",
    "last_chunk_hex",
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


def float_value(row: dict[str, str], field: str) -> float:
    raw = row.get(field, "")
    return float(raw) if raw else 0.0


def signed_hex(value: int) -> str:
    sign = "-" if value < 0 else ""
    return f"{sign}0x{abs(value):08x}"


def classify_cluster(rows: int, pixel_span: int) -> str:
    if rows >= 16 or pixel_span >= 32:
        return "strong"
    if rows >= 5 or pixel_span >= 20:
        return "medium"
    return "weak"


def valid_scan_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        row
        for row in rows
        if row.get("segment_offset")
        and row.get("pixel_offset")
        and row.get("chunk_size")
        and not row.get("issues")
    ]


def cluster_key(row: dict[str, str]) -> tuple[str, str, str, int, int]:
    pixel_offset = int_value(row, "pixel_offset")
    segment_offset = int_value(row, "segment_offset")
    return (
        row.get("archive", ""),
        row.get("archive_tag", ""),
        row.get("pcx_name", ""),
        int_value(row, "chunk_size"),
        pixel_offset - segment_offset,
    )


def summarize_cluster(
    rows: list[dict[str, str]],
    *,
    cluster_id: int,
) -> dict[str, str]:
    first = rows[0]
    last = rows[-1]
    chunk_size = int_value(first, "chunk_size")
    pixel_start = int_value(first, "pixel_offset")
    pixel_end = int_value(last, "pixel_offset")
    segment_start = int_value(first, "segment_offset")
    segment_end = int_value(last, "segment_offset")
    pixel_span = pixel_end - pixel_start + chunk_size
    segment_span = segment_end - segment_start + chunk_size
    entropies = [float_value(row, "entropy") for row in rows]
    zero_ratios = [float_value(row, "zero_ratio") for row in rows]
    delta = pixel_start - segment_start
    return {
        "archive": first.get("archive", ""),
        "archive_tag": first.get("archive_tag", ""),
        "pcx_name": first.get("pcx_name", ""),
        "chunk_size": str(chunk_size),
        "cluster_id": str(cluster_id),
        "cluster_class": classify_cluster(len(rows), pixel_span),
        "delta": str(delta),
        "delta_hex": signed_hex(delta),
        "rows": str(len(rows)),
        "pixel_start": str(pixel_start),
        "pixel_end": str(pixel_end),
        "pixel_start_hex": f"0x{pixel_start:08x}",
        "pixel_end_hex": f"0x{pixel_end:08x}",
        "pixel_start_x": first.get("pixel_x", ""),
        "pixel_start_y": first.get("pixel_y", ""),
        "pixel_end_x": last.get("pixel_x", ""),
        "pixel_end_y": last.get("pixel_y", ""),
        "segment_start": str(segment_start),
        "segment_end": str(segment_end),
        "segment_start_hex": f"0x{segment_start:08x}",
        "segment_end_hex": f"0x{segment_end:08x}",
        "pixel_span_bytes": str(pixel_span),
        "segment_span_bytes": str(segment_span),
        "avg_entropy": f"{(sum(entropies) / len(entropies)):.4f}" if entropies else "0.0000",
        "max_entropy": f"{max(entropies):.4f}" if entropies else "0.0000",
        "min_zero_ratio": f"{min(zero_ratios):.4f}" if zero_ratios else "0.0000",
        "max_zero_ratio": f"{max(zero_ratios):.4f}" if zero_ratios else "0.0000",
        "first_chunk_hex": first.get("chunk_hex", ""),
        "last_chunk_hex": last.get("chunk_hex", ""),
        "issues": "",
    }


def build_clusters(
    scan_rows: list[dict[str, str]],
    *,
    max_gap: int,
    min_rows: int,
) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str, str, int, int], list[dict[str, str]]] = {}
    for row in valid_scan_rows(scan_rows):
        grouped.setdefault(cluster_key(row), []).append(row)

    clusters: list[dict[str, str]] = []
    cluster_id = 1
    for _key, rows in sorted(
        grouped.items(),
        key=lambda item: (
            item[0][2],
            -item[0][3],
            item[0][4],
            min(int_value(row, "segment_offset") for row in item[1]),
        ),
    ):
        rows.sort(key=lambda row: (int_value(row, "segment_offset"), int_value(row, "pixel_offset")))
        current: list[dict[str, str]] = []
        last_segment = -1
        last_pixel = -1
        for row in rows:
            segment_offset = int_value(row, "segment_offset")
            pixel_offset = int_value(row, "pixel_offset")
            continues = (
                current
                and 0 < segment_offset - last_segment <= max_gap
                and 0 < pixel_offset - last_pixel <= max_gap
            )
            if current and not continues:
                if len(current) >= min_rows:
                    clusters.append(summarize_cluster(current, cluster_id=cluster_id))
                    cluster_id += 1
                current = []
            current.append(row)
            last_segment = segment_offset
            last_pixel = pixel_offset
        if len(current) >= min_rows:
            clusters.append(summarize_cluster(current, cluster_id=cluster_id))
            cluster_id += 1

    clusters.sort(
        key=lambda row: (
            row.get("pcx_name", ""),
            -int_value(row, "chunk_size"),
            -int_value(row, "pixel_span_bytes"),
            int_value(row, "segment_start"),
        )
    )
    for index, row in enumerate(clusters, start=1):
        row["cluster_id"] = str(index)
    return clusters


def summary_row(
    scan_rows: list[dict[str, str]],
    clusters: list[dict[str, str]],
    *,
    max_gap: int,
    min_rows: int,
) -> dict[str, str]:
    valid_rows = valid_scan_rows(scan_rows)
    class_counts = Counter(row.get("cluster_class", "") for row in clusters)
    matched_segments = {
        (row.get("archive", ""), row.get("pcx_name", ""))
        for row in clusters
        if row.get("archive") and row.get("pcx_name")
    }
    chunk_sizes = sorted({int_value(row, "chunk_size") for row in clusters if row.get("chunk_size")})
    return {
        "scope": "total",
        "scan_rows": str(len(valid_rows)),
        "clusters": str(len(clusters)),
        "matched_segments": str(len(matched_segments)),
        "unique_pcx": str(len({row.get("pcx_name", "") for row in clusters if row.get("pcx_name")})),
        "chunk_sizes": ";".join(str(size) for size in chunk_sizes),
        "max_gap": str(max_gap),
        "min_rows": str(min_rows),
        "strong_clusters": str(class_counts.get("strong", 0)),
        "medium_clusters": str(class_counts.get("medium", 0)),
        "weak_clusters": str(class_counts.get("weak", 0)),
        "longest_pixel_span": str(max((int_value(row, "pixel_span_bytes") for row in clusters), default=0)),
        "longest_segment_span": str(max((int_value(row, "segment_span_bytes") for row in clusters), default=0)),
        "issue_rows": str(sum(1 for row in scan_rows if row.get("issues"))),
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


def render_cluster(row: dict[str, str]) -> str:
    return (
        "<tr>"
        f"<td>{html.escape(row.get('pcx_name', ''))}</td>"
        f"<td>{html.escape(row.get('chunk_size', ''))}</td>"
        f"<td>{html.escape(row.get('cluster_class', ''))}</td>"
        f"<td>{html.escape(row.get('rows', ''))}</td>"
        f"<td>{html.escape(row.get('pixel_span_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('pixel_start_hex', ''))} ({html.escape(row.get('pixel_start_x', ''))},{html.escape(row.get('pixel_start_y', ''))})</td>"
        f"<td>{html.escape(row.get('pixel_end_hex', ''))} ({html.escape(row.get('pixel_end_x', ''))},{html.escape(row.get('pixel_end_y', ''))})</td>"
        f"<td>{html.escape(row.get('segment_start_hex', ''))}</td>"
        f"<td>{html.escape(row.get('segment_end_hex', ''))}</td>"
        f"<td>{html.escape(row.get('delta_hex', ''))}</td>"
        f"<td>{html.escape(row.get('avg_entropy', ''))}</td>"
        f"<td>{html.escape(row.get('issues', ''))}</td>"
        "</tr>"
    )


def build_html(
    summary: dict[str, str],
    clusters: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "clusters": clusters}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("clusters.csv", output_dir / "clusters.csv"),
        )
    )
    table_rows = "\n".join(render_cluster(row) for row in clusters)
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
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Regroupement des fenetres directes .tex/CDCACHE par continuite lineaire.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Rows scan</div><div class="value">{html.escape(summary['scan_rows'])}</div></div>
    <div class="stat"><div class="label">Clusters</div><div class="value">{html.escape(summary['clusters'])}</div></div>
    <div class="stat"><div class="label">Strong</div><div class="value">{html.escape(summary['strong_clusters'])}</div></div>
    <div class="stat"><div class="label">Issues</div><div class="value ok">{html.escape(summary['issue_rows'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div></section>
  <section class="panel">
    <table>
      <thead><tr><th>PCX</th><th>Size</th><th>Class</th><th>Rows</th><th>Span</th><th>Pixel start</th><th>Pixel end</th><th>Segment start</th><th>Segment end</th><th>Delta</th><th>Entropy</th><th>Issues</th></tr></thead>
      <tbody>{table_rows}</tbody>
    </table>
  </section>
</main>
<script>
const TEX_EXACT_CHUNK_CLUSTERS = {data_json};
</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    scan: Path,
    *,
    max_gap: int,
    min_rows: int,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    scan_rows = read_rows(scan)
    clusters = build_clusters(scan_rows, max_gap=max_gap, min_rows=min_rows)
    summary = summary_row(scan_rows, clusters, max_gap=max_gap, min_rows=min_rows)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "clusters.csv", CLUSTER_FIELDNAMES, clusters)
    (output_dir / "index.html").write_text(build_html(summary, clusters, output_dir, title))
    return summary, clusters


def main() -> None:
    parser = argparse.ArgumentParser(description="Cluster exact .tex/CDCACHE chunk scan rows.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--scan", type=Path, default=DEFAULT_SCAN)
    parser.add_argument("--max-gap", type=int, default=1)
    parser.add_argument("--min-rows", type=int, default=2)
    parser.add_argument("--title", default="Lands of Lore II .tex Exact Chunk Clusters")
    args = parser.parse_args()

    summary, _clusters = write_report(
        args.output,
        args.scan,
        max_gap=args.max_gap,
        min_rows=args.min_rows,
        title=args.title,
    )
    print(f"Scan rows: {summary['scan_rows']}")
    print(f"Clusters: {summary['clusters']}")
    print(f"Strong clusters: {summary['strong_clusters']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
