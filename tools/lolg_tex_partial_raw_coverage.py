#!/usr/bin/env python3
"""Report coverage and remaining gaps for the partial .tex raw-copy decoder."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
from pathlib import Path


DEFAULT_OUTPUT = Path("output/tex_partial_raw_coverage")
DEFAULT_CLUSTERS = Path("output/tex_exact_chunk_clusters/clusters.csv")
DEFAULT_COMPARISONS = Path("output/tex_exact_cdcache_compare/comparisons.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "textures",
    "raw_runs",
    "total_pixels",
    "covered_pixels",
    "coverage_ratio",
    "gaps",
    "largest_gap",
    "issue_rows",
]

COVERAGE_FIELDNAMES = [
    "archive",
    "archive_tag",
    "pcx_name",
    "native_width",
    "native_height",
    "total_pixels",
    "raw_runs",
    "covered_pixels",
    "coverage_ratio",
    "gaps",
    "largest_gap",
    "issues",
]

GAP_FIELDNAMES = [
    "archive",
    "archive_tag",
    "pcx_name",
    "gap_rank",
    "gap_start",
    "gap_start_hex",
    "gap_start_x",
    "gap_start_y",
    "gap_end",
    "gap_end_hex",
    "gap_end_x",
    "gap_end_y",
    "gap_pixels",
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


def build_reports(
    clusters: Path,
    comparisons: Path,
    *,
    max_gaps_per_texture: int,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    cluster_rows = read_rows(clusters)
    comparison_rows = read_rows(comparisons)
    comparisons_by_key = comparison_lookup(comparison_rows)
    clusters_by_key = grouped_clusters(cluster_rows)
    coverage_rows: list[dict[str, str]] = []
    gap_rows: list[dict[str, str]] = []

    for key, group in sorted(clusters_by_key.items()):
        archive, pcx_name = key
        comparison = comparisons_by_key.get(key, {})
        issues: list[str] = []
        width = int(comparison.get("cdcache_width") or 0)
        height = int(comparison.get("cdcache_height") or 0)
        pixel_count = width * height
        if not pixel_count:
            issues.append("missing_cdcache_dimensions")
        covered = covered_offsets(group, pixel_count) if pixel_count else set()
        gaps = find_gaps(covered, pixel_count) if pixel_count else []
        largest_gap = max((end - start + 1 for start, end in gaps), default=0)
        coverage_rows.append(
            {
                "archive": archive,
                "archive_tag": Path(archive).stem.upper(),
                "pcx_name": pcx_name,
                "native_width": str(width),
                "native_height": str(height),
                "total_pixels": str(pixel_count),
                "raw_runs": str(len(group)),
                "covered_pixels": str(len(covered)),
                "coverage_ratio": f"{(len(covered) / pixel_count):.6f}" if pixel_count else "0.000000",
                "gaps": str(len(gaps)),
                "largest_gap": str(largest_gap),
                "issues": ";".join(issues),
            }
        )
        ranked_gaps = sorted(gaps, key=lambda item: item[1] - item[0] + 1, reverse=True)
        for rank, (start, end) in enumerate(ranked_gaps[:max_gaps_per_texture], start=1):
            gap_rows.append(
                {
                    "archive": archive,
                    "archive_tag": Path(archive).stem.upper(),
                    "pcx_name": pcx_name,
                    "gap_rank": str(rank),
                    "gap_start": str(start),
                    "gap_start_hex": f"0x{start:08x}",
                    "gap_start_x": str(start % width if width else 0),
                    "gap_start_y": str(start // width if width else 0),
                    "gap_end": str(end),
                    "gap_end_hex": f"0x{end:08x}",
                    "gap_end_x": str(end % width if width else 0),
                    "gap_end_y": str(end // width if width else 0),
                    "gap_pixels": str(end - start + 1),
                    "issues": "",
                }
            )
    return coverage_rows, gap_rows


def summary_row(coverage_rows: list[dict[str, str]]) -> dict[str, str]:
    total_pixels = sum(int_value(row, "total_pixels") for row in coverage_rows)
    covered_pixels = sum(int_value(row, "covered_pixels") for row in coverage_rows)
    return {
        "scope": "total",
        "textures": str(len(coverage_rows)),
        "raw_runs": str(sum(int_value(row, "raw_runs") for row in coverage_rows)),
        "total_pixels": str(total_pixels),
        "covered_pixels": str(covered_pixels),
        "coverage_ratio": f"{(covered_pixels / total_pixels):.6f}" if total_pixels else "0.000000",
        "gaps": str(sum(int_value(row, "gaps") for row in coverage_rows)),
        "largest_gap": str(max((int_value(row, "largest_gap") for row in coverage_rows), default=0)),
        "issue_rows": str(sum(1 for row in coverage_rows if row.get("issues"))),
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


def render_coverage_row(row: dict[str, str]) -> str:
    return (
        "<tr>"
        f"<td>{html.escape(row.get('pcx_name', ''))}</td>"
        f"<td>{html.escape(row.get('native_width', ''))}x{html.escape(row.get('native_height', ''))}</td>"
        f"<td>{html.escape(row.get('raw_runs', ''))}</td>"
        f"<td>{html.escape(row.get('covered_pixels', ''))}</td>"
        f"<td>{html.escape(row.get('coverage_ratio', ''))}</td>"
        f"<td>{html.escape(row.get('gaps', ''))}</td>"
        f"<td>{html.escape(row.get('largest_gap', ''))}</td>"
        f"<td>{html.escape(row.get('issues', ''))}</td>"
        "</tr>"
    )


def render_gap_row(row: dict[str, str]) -> str:
    return (
        "<tr>"
        f"<td>{html.escape(row.get('pcx_name', ''))}</td>"
        f"<td>{html.escape(row.get('gap_rank', ''))}</td>"
        f"<td>{html.escape(row.get('gap_pixels', ''))}</td>"
        f"<td>{html.escape(row.get('gap_start_hex', ''))} ({html.escape(row.get('gap_start_x', ''))},{html.escape(row.get('gap_start_y', ''))})</td>"
        f"<td>{html.escape(row.get('gap_end_hex', ''))} ({html.escape(row.get('gap_end_x', ''))},{html.escape(row.get('gap_end_y', ''))})</td>"
        "</tr>"
    )


def build_html(
    summary: dict[str, str],
    coverage_rows: list[dict[str, str]],
    gap_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "coverage": coverage_rows, "gaps": gap_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("coverage.csv", output_dir / "coverage.csv"),
            ("gaps.csv", output_dir / "gaps.csv"),
        )
    )
    coverage_markup = "\n".join(render_coverage_row(row) for row in coverage_rows)
    gap_markup = "\n".join(render_gap_row(row) for row in gap_rows)
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
table {{ width: 100%; border-collapse: collapse; min-width: 900px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 10px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Couverture actuelle du decodeur raw-copy partiel et plus grands trous restants.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Textures</div><div class="value">{html.escape(summary['textures'])}</div></div>
    <div class="stat"><div class="label">Runs</div><div class="value">{html.escape(summary['raw_runs'])}</div></div>
    <div class="stat"><div class="label">Pixels couverts</div><div class="value">{html.escape(summary['covered_pixels'])}</div></div>
    <div class="stat"><div class="label">Coverage</div><div class="value">{html.escape(summary['coverage_ratio'])}</div></div>
    <div class="stat"><div class="label">Issues</div><div class="value ok">{html.escape(summary['issue_rows'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div></section>
  <section class="panel">
    <table>
      <thead><tr><th>PCX</th><th>Size</th><th>Runs</th><th>Covered</th><th>Ratio</th><th>Gaps</th><th>Largest gap</th><th>Issues</th></tr></thead>
      <tbody>{coverage_markup}</tbody>
    </table>
  </section>
  <section class="panel">
    <table>
      <thead><tr><th>PCX</th><th>Rank</th><th>Pixels</th><th>Start</th><th>End</th></tr></thead>
      <tbody>{gap_markup}</tbody>
    </table>
  </section>
</main>
<script>
const TEX_PARTIAL_RAW_COVERAGE = {data_json};
</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    clusters: Path,
    comparisons: Path,
    *,
    max_gaps_per_texture: int,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    coverage_rows, gap_rows = build_reports(
        clusters,
        comparisons,
        max_gaps_per_texture=max_gaps_per_texture,
    )
    summary = summary_row(coverage_rows)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "coverage.csv", COVERAGE_FIELDNAMES, coverage_rows)
    write_csv(output_dir / "gaps.csv", GAP_FIELDNAMES, gap_rows)
    (output_dir / "index.html").write_text(
        build_html(summary, coverage_rows, gap_rows, output_dir, title)
    )
    return summary, coverage_rows, gap_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Report partial .tex raw decoder coverage.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--clusters", type=Path, default=DEFAULT_CLUSTERS)
    parser.add_argument("--comparisons", type=Path, default=DEFAULT_COMPARISONS)
    parser.add_argument("--max-gaps-per-texture", type=int, default=20)
    parser.add_argument("--title", default="Lands of Lore II .tex Partial Raw Coverage")
    args = parser.parse_args()

    summary, _coverage_rows, _gap_rows = write_report(
        args.output,
        args.clusters,
        args.comparisons,
        max_gaps_per_texture=args.max_gaps_per_texture,
        title=args.title,
    )
    print(f"Textures: {summary['textures']}")
    print(f"Raw runs: {summary['raw_runs']}")
    print(f"Covered pixels: {summary['covered_pixels']}")
    print(f"Coverage ratio: {summary['coverage_ratio']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
