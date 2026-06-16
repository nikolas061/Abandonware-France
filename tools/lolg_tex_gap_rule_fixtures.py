#!/usr/bin/env python3
"""Extract binary fixtures for prioritized .tex gap decoder-rule candidates."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
from pathlib import Path

from lolg_tex_gap_opcode_probe import (
    comparison_lookup,
    int_value,
    load_indexed_pixels,
    read_mix_entry,
    read_rows,
    relative_href,
    write_csv,
)


DEFAULT_OUTPUT = Path("output/tex_gap_rule_fixtures")
DEFAULT_QUEUE = Path("output/tex_gap_rule_queue/queue.csv")
DEFAULT_FRONTIERS = Path("output/tex_gap_frontier_report/frontiers.csv")
DEFAULT_COMPARISONS = Path("output/tex_exact_cdcache_compare/comparisons.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "fixture_rows",
    "binary_files",
    "rule_types",
    "top_rank",
    "top_rule_type",
    "top_frontier_id",
    "top_pcx",
    "total_expected_pixels",
    "total_segment_bytes",
    "total_control_prefix_bytes",
    "total_fragment_bytes",
    "issue_rows",
]

MANIFEST_FIELDNAMES = [
    "rank",
    "rule_type",
    "priority_score",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "frontier_type",
    "pixel_gap",
    "segment_gap_bytes",
    "segment_gap_ratio",
    "opcode0_hex",
    "opcode1_hex",
    "best_raw_skip",
    "best_raw_prefix_bytes",
    "control_prefix_bytes",
    "fragment_bytes",
    "segment_gap_path",
    "expected_gap_path",
    "control_prefix_path",
    "fragment_path",
    "expected_head_hex",
    "segment_head_hex",
    "fragment_head_hex",
    "issues",
]


def safe_stem(*parts: str) -> str:
    raw = "_".join(part for part in parts if part)
    return "".join(char if char.isalnum() or char in "-_." else "_" for char in raw).strip("_")


def write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def frontier_lookup(rows: list[dict[str, str]]) -> dict[tuple[str, str, str], dict[str, str]]:
    return {
        (row.get("archive", ""), row.get("pcx_name", ""), row.get("frontier_id", "")): row
        for row in rows
    }


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


def select_queue_rows(rows: list[dict[str, str]], limit: int) -> list[dict[str, str]]:
    ranked = sorted(rows, key=lambda row: int_value(row, "rank") or 999999)
    return ranked[:limit] if limit > 0 else ranked


def build_manifest(
    queue: Path,
    frontiers: Path,
    comparisons: Path,
    output_dir: Path,
    *,
    limit: int,
    context_bytes: int,
) -> list[dict[str, str]]:
    queue_rows = select_queue_rows(read_rows(queue), limit)
    frontier_rows = read_rows(frontiers)
    comparison_rows = read_rows(comparisons)
    frontiers_by_key = frontier_lookup(frontier_rows)
    comparisons_by_key = comparison_lookup(comparison_rows)
    payload_cache: dict[Path, bytes] = {}
    reference_cache: dict[tuple[str, str], bytes] = {}
    fixture_dir = output_dir / "fixtures"
    manifest: list[dict[str, str]] = []

    for queue_row in queue_rows:
        issues: list[str] = []
        key = (
            queue_row.get("archive", ""),
            queue_row.get("pcx_name", ""),
            queue_row.get("frontier_id", ""),
        )
        frontier = frontiers_by_key.get(key, {})
        if not frontier:
            issues.append("missing_frontier_row")
        comparison_key = (queue_row.get("archive", ""), queue_row.get("pcx_name", ""))
        comparison = comparisons_by_key.get(comparison_key, {})
        if not comparison:
            issues.append("missing_comparison_row")
            segment = b""
            reference_pixels = b""
        else:
            segment, segment_issues = load_segment(
                queue_row.get("archive", ""),
                comparison,
                payload_cache,
            )
            issues.extend(segment_issues)
            if comparison_key not in reference_cache:
                native_path = Path(comparison.get("cdcache_native_path", ""))
                try:
                    pixels, _width, _height = load_indexed_pixels(native_path)
                    reference_cache[comparison_key] = pixels
                except Exception as exc:
                    reference_cache[comparison_key] = b""
                    issues.append(f"reference_read_failed:{exc}")
            reference_pixels = reference_cache[comparison_key]

        segment_start = int_value(frontier, "segment_gap_start")
        segment_bytes = int_value(queue_row, "segment_gap_bytes")
        gap_start = int_value(frontier, "gap_start")
        pixel_gap = int_value(queue_row, "pixel_gap")
        best_skip = int_value(queue_row, "best_raw_skip")
        best_prefix = int_value(queue_row, "best_raw_prefix_bytes")

        segment_gap = segment[segment_start : segment_start + segment_bytes]
        expected_gap = reference_pixels[gap_start : gap_start + pixel_gap]
        if len(segment_gap) != segment_bytes:
            issues.append("segment_gap_truncated")
        if len(expected_gap) != pixel_gap:
            issues.append("expected_gap_truncated")
        control_prefix = segment_gap[:best_skip]
        fragment = segment_gap[best_skip : best_skip + best_prefix] if best_prefix else b""

        stem = safe_stem(
            f"rank{int_value(queue_row, 'rank'):03d}",
            queue_row.get("archive_tag", ""),
            queue_row.get("pcx_name", ""),
            f"frontier{queue_row.get('frontier_id', '')}",
            queue_row.get("rule_type", ""),
        )
        segment_path = fixture_dir / f"{stem}_segment_gap.bin"
        expected_path = fixture_dir / f"{stem}_expected_gap.bin"
        prefix_path = fixture_dir / f"{stem}_control_prefix.bin"
        fragment_path = fixture_dir / f"{stem}_fragment.bin"
        write_bytes(segment_path, segment_gap)
        write_bytes(expected_path, expected_gap)
        write_bytes(prefix_path, control_prefix)
        write_bytes(fragment_path, fragment)

        manifest.append(
            {
                "rank": queue_row.get("rank", ""),
                "rule_type": queue_row.get("rule_type", ""),
                "priority_score": queue_row.get("priority_score", ""),
                "archive": queue_row.get("archive", ""),
                "archive_tag": queue_row.get("archive_tag", ""),
                "pcx_name": queue_row.get("pcx_name", ""),
                "frontier_id": queue_row.get("frontier_id", ""),
                "frontier_type": queue_row.get("frontier_type", ""),
                "pixel_gap": str(pixel_gap),
                "segment_gap_bytes": str(segment_bytes),
                "segment_gap_ratio": queue_row.get("segment_gap_ratio", ""),
                "opcode0_hex": queue_row.get("opcode0_hex", ""),
                "opcode1_hex": queue_row.get("opcode1_hex", ""),
                "best_raw_skip": str(best_skip),
                "best_raw_prefix_bytes": str(best_prefix),
                "control_prefix_bytes": str(len(control_prefix)),
                "fragment_bytes": str(len(fragment)),
                "segment_gap_path": segment_path.as_posix(),
                "expected_gap_path": expected_path.as_posix(),
                "control_prefix_path": prefix_path.as_posix(),
                "fragment_path": fragment_path.as_posix(),
                "expected_head_hex": expected_gap[:context_bytes].hex(),
                "segment_head_hex": segment_gap[:context_bytes].hex(),
                "fragment_head_hex": fragment[:context_bytes].hex(),
                "issues": ";".join(issues),
            }
        )
    return manifest


def summary_row(rows: list[dict[str, str]]) -> dict[str, str]:
    top = min(rows, key=lambda row: int_value(row, "rank")) if rows else {}
    issue_rows = sum(1 for row in rows if row.get("issues"))
    return {
        "scope": "total",
        "fixture_rows": str(len(rows)),
        "binary_files": str(len(rows) * 4),
        "rule_types": str(len({row.get("rule_type", "") for row in rows if row.get("rule_type")})),
        "top_rank": top.get("rank", ""),
        "top_rule_type": top.get("rule_type", ""),
        "top_frontier_id": top.get("frontier_id", ""),
        "top_pcx": top.get("pcx_name", ""),
        "total_expected_pixels": str(sum(int_value(row, "pixel_gap") for row in rows)),
        "total_segment_bytes": str(sum(int_value(row, "segment_gap_bytes") for row in rows)),
        "total_control_prefix_bytes": str(sum(int_value(row, "control_prefix_bytes") for row in rows)),
        "total_fragment_bytes": str(sum(int_value(row, "fragment_bytes") for row in rows)),
        "issue_rows": str(issue_rows),
    }


def render_manifest_row(row: dict[str, str], output_dir: Path) -> str:
    segment_href = html.escape(relative_href(row.get("segment_gap_path", ""), output_dir))
    expected_href = html.escape(relative_href(row.get("expected_gap_path", ""), output_dir))
    prefix_href = html.escape(relative_href(row.get("control_prefix_path", ""), output_dir))
    fragment_href = html.escape(relative_href(row.get("fragment_path", ""), output_dir))
    return (
        "<tr>"
        f"<td>{html.escape(row.get('rank', ''))}</td>"
        f"<td>{html.escape(row.get('rule_type', ''))}</td>"
        f"<td>{html.escape(row.get('pcx_name', ''))}</td>"
        f"<td>{html.escape(row.get('frontier_id', ''))}</td>"
        f"<td>{html.escape(row.get('pixel_gap', ''))}</td>"
        f"<td>{html.escape(row.get('segment_gap_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('control_prefix_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('fragment_bytes', ''))}</td>"
        f"<td><a href=\"{segment_href}\">segment</a> <a href=\"{expected_href}\">expected</a> "
        f"<a href=\"{prefix_href}\">prefix</a> <a href=\"{fragment_href}\">fragment</a></td>"
        f"<td><code>{html.escape(row.get('fragment_head_hex', ''))}</code></td>"
        f"<td>{html.escape(row.get('issues', ''))}</td>"
        "</tr>"
    )


def build_html(summary: dict[str, str], rows: list[dict[str, str]], output_dir: Path, title: str) -> str:
    payload = {"summary": summary, "fixtures": rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("manifest.csv", output_dir / "manifest.csv"),
            ("fixtures/", output_dir / "fixtures"),
        )
    )
    table_rows = "\n".join(render_manifest_row(row, output_dir) for row in rows)
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
table {{ width: 100%; border-collapse: collapse; min-width: 1120px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
code {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; overflow-wrap: anywhere; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Fixtures binaires pour tester les regles candidates du decodeur .tex.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Fixtures</div><div class="value">{html.escape(summary['fixture_rows'])}</div></div>
    <div class="stat"><div class="label">Binary files</div><div class="value">{html.escape(summary['binary_files'])}</div></div>
    <div class="stat"><div class="label">Rule types</div><div class="value">{html.escape(summary['rule_types'])}</div></div>
    <div class="stat"><div class="label">Fragment bytes</div><div class="value">{html.escape(summary['total_fragment_bytes'])}</div></div>
    <div class="stat"><div class="label">Issues</div><div class="value ok">{html.escape(summary['issue_rows'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div></section>
  <section class="panel">
    <table>
      <thead><tr><th>Rank</th><th>Rule</th><th>PCX</th><th>Frontier</th><th>Pixel gap</th><th>Segment bytes</th><th>Prefix bytes</th><th>Fragment bytes</th><th>Files</th><th>Fragment head</th><th>Issues</th></tr></thead>
      <tbody>{table_rows}</tbody>
    </table>
  </section>
</main>
<script>
const TEX_GAP_RULE_FIXTURES = {data_json};
</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    queue: Path,
    frontiers: Path,
    comparisons: Path,
    *,
    limit: int,
    context_bytes: int,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = build_manifest(
        queue,
        frontiers,
        comparisons,
        output_dir,
        limit=limit,
        context_bytes=context_bytes,
    )
    summary = summary_row(rows)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "manifest.csv", MANIFEST_FIELDNAMES, rows)
    (output_dir / "index.html").write_text(build_html(summary, rows, output_dir, title))
    return summary, rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract .tex gap decoder-rule binary fixtures.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--queue", type=Path, default=DEFAULT_QUEUE)
    parser.add_argument("--frontiers", type=Path, default=DEFAULT_FRONTIERS)
    parser.add_argument("--comparisons", type=Path, default=DEFAULT_COMPARISONS)
    parser.add_argument("--limit", type=int, default=32)
    parser.add_argument("--context-bytes", type=int, default=32)
    parser.add_argument("--title", default="Lands of Lore II .tex Gap Rule Fixtures")
    args = parser.parse_args()

    summary, _rows = write_report(
        args.output,
        args.queue,
        args.frontiers,
        args.comparisons,
        limit=args.limit,
        context_bytes=args.context_bytes,
        title=args.title,
    )
    print(f"Fixture rows: {summary['fixture_rows']}")
    print(f"Binary files: {summary['binary_files']}")
    print(f"Rule types: {summary['rule_types']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
