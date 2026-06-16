#!/usr/bin/env python3
"""Probe .tex gap control windows for embedded geometry/count words."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_nonzero_stream_probe import expected_nonzero_stream
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_control_word_probe")
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_ZERO_RUN_FIXTURES = Path("output/tex_gap_zero_run_probe/fixtures.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "fixture_rows",
    "hit_rows",
    "fixtures_with_hits",
    "metric_names",
    "u16le_hits",
    "u16be_hits",
    "byte_hits",
    "top_metric",
    "top_metric_hits",
    "top_fixture_rank",
    "top_fixture_pcx",
    "top_fixture_hits",
    "issue_rows",
]

FIXTURE_FIELDNAMES = [
    "rank",
    "rule_type",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "frontier_type",
    "pixel_gap",
    "segment_gap_bytes",
    "cdcache_width",
    "cdcache_height",
    "zero_columns",
    "nonzero_columns",
    "nonzero_slots",
    "leading_row_prefix_zero_runs",
    "hit_count",
    "u16le_hit_count",
    "u16be_hit_count",
    "byte_hit_count",
    "hit_metrics",
    "segment_head_hex",
    "issues",
]

HIT_FIELDNAMES = [
    "rank",
    "pcx_name",
    "frontier_id",
    "encoding",
    "offset",
    "offset_hex",
    "value",
    "value_hex",
    "metric",
    "metric_value",
    "context_hex",
]

BY_METRIC_FIELDNAMES = [
    "metric",
    "metric_value",
    "hits",
    "fixtures",
    "encodings",
    "sample_rank",
    "sample_pcx",
    "sample_offset",
]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def load_bytes(path_text: str, issues: list[str], label: str) -> bytes:
    if not path_text:
        issues.append(f"missing_{label}_path")
        return b""
    try:
        return Path(path_text).read_bytes()
    except OSError as exc:
        issues.append(f"read_{label}_failed:{exc}")
        return b""


def zero_fixture_lookup(rows: list[dict[str, str]]) -> dict[tuple[str, str, str], dict[str, str]]:
    return {
        (row.get("archive", ""), row.get("pcx_name", ""), row.get("frontier_id", "")): row
        for row in rows
    }


def metric_values(fixture: dict[str, str], zero_fixture: dict[str, str], expected: bytes) -> dict[str, int]:
    width = int_value(zero_fixture, "cdcache_width")
    zero_columns = int_value(zero_fixture, "leading_zero_bytes")
    gap_start = int_value(zero_fixture, "gap_start")
    nonzero_slots = len(
        expected_nonzero_stream(
            expected,
            gap_start=gap_start,
            width=width,
            zero_columns=zero_columns,
        )
    )
    metrics = {
        "width": width,
        "height": int_value(zero_fixture, "cdcache_height"),
        "zero_columns": zero_columns,
        "nonzero_columns": max(0, width - zero_columns),
        "pixel_gap": int_value(fixture, "pixel_gap"),
        "segment_gap_bytes": int_value(fixture, "segment_gap_bytes"),
        "nonzero_slots": nonzero_slots,
        "gap_start": gap_start,
        "gap_start_x": int_value(zero_fixture, "gap_start_x"),
        "gap_start_y": int_value(zero_fixture, "gap_start_y"),
        "zero_bytes": int_value(zero_fixture, "zero_bytes"),
        "zero_runs": int_value(zero_fixture, "zero_runs"),
        "nonzero_runs": int_value(zero_fixture, "nonzero_runs"),
        "leading_zero_bytes": int_value(zero_fixture, "leading_zero_bytes"),
        "trailing_zero_bytes": int_value(zero_fixture, "trailing_zero_bytes"),
        "max_zero_run_bytes": int_value(zero_fixture, "max_zero_run_bytes"),
        "max_nonzero_run_bytes": int_value(zero_fixture, "max_nonzero_run_bytes"),
        "row_prefix_zero_runs": int_value(zero_fixture, "row_prefix_zero_runs"),
        "row_prefix_zero_bytes": int_value(zero_fixture, "row_prefix_zero_bytes"),
        "leading_row_prefix_zero_runs": int_value(zero_fixture, "leading_row_prefix_zero_runs"),
        "zero_run_period_guess": int_value(zero_fixture, "zero_run_period_guess"),
        "best_raw_skip": int_value(fixture, "best_raw_skip"),
        "best_raw_prefix_bytes": int_value(fixture, "best_raw_prefix_bytes"),
    }
    return {key: value for key, value in metrics.items() if value > 0}


def metric_lookup(metrics: dict[str, int]) -> dict[int, list[str]]:
    lookup: dict[int, list[str]] = defaultdict(list)
    for metric, value in metrics.items():
        lookup[value].append(metric)
    return lookup


def context_hex(data: bytes, offset: int, size: int, radius: int) -> str:
    start = max(0, offset - radius)
    end = min(len(data), offset + size + radius)
    return data[start:end].hex()


def emit_hit_rows(
    fixture: dict[str, str],
    segment: bytes,
    metrics: dict[str, int],
    *,
    window_bytes: int,
    context_radius: int,
) -> list[dict[str, str]]:
    lookup = metric_lookup(metrics)
    scan = segment[:window_bytes]
    rows: list[dict[str, str]] = []

    def add_hits(encoding: str, offset: int, value: int, size: int) -> None:
        for metric in lookup.get(value, []):
            rows.append(
                {
                    "rank": fixture.get("rank", ""),
                    "pcx_name": fixture.get("pcx_name", ""),
                    "frontier_id": fixture.get("frontier_id", ""),
                    "encoding": encoding,
                    "offset": str(offset),
                    "offset_hex": f"0x{offset:04x}",
                    "value": str(value),
                    "value_hex": f"0x{value:04x}",
                    "metric": metric,
                    "metric_value": str(metrics[metric]),
                    "context_hex": context_hex(segment, offset, size, context_radius),
                }
            )

    for offset, value in enumerate(scan):
        add_hits("byte", offset, value, 1)
    for offset in range(max(0, len(scan) - 1)):
        add_hits("u16le", offset, int.from_bytes(scan[offset : offset + 2], "little"), 2)
        add_hits("u16be", offset, int.from_bytes(scan[offset : offset + 2], "big"), 2)
    return rows


def build_rows(
    fixtures: Path,
    zero_run_fixtures: Path,
    *,
    limit: int,
    window_bytes: int,
    context_radius: int,
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    fixture_rows = sorted(read_rows(fixtures), key=lambda row: int_value(row, "rank"))
    if limit > 0:
        fixture_rows = fixture_rows[:limit]
    zero_rows = zero_fixture_lookup(read_rows(zero_run_fixtures))
    output_fixtures: list[dict[str, str]] = []
    hit_rows: list[dict[str, str]] = []

    for fixture in fixture_rows:
        issues: list[str] = []
        key = (fixture.get("archive", ""), fixture.get("pcx_name", ""), fixture.get("frontier_id", ""))
        zero_fixture = zero_rows.get(key, {})
        if not zero_fixture:
            issues.append("missing_zero_run_fixture")
        segment = load_bytes(fixture.get("segment_gap_path", ""), issues, "segment")
        expected = load_bytes(fixture.get("expected_gap_path", ""), issues, "expected")
        if len(segment) != int_value(fixture, "segment_gap_bytes"):
            issues.append("segment_size_mismatch")
        if len(expected) != int_value(fixture, "pixel_gap"):
            issues.append("expected_size_mismatch")
        metrics = metric_values(fixture, zero_fixture, expected)
        fixture_hits = emit_hit_rows(
            fixture,
            segment,
            metrics,
            window_bytes=window_bytes,
            context_radius=context_radius,
        )
        hit_rows.extend(fixture_hits)
        encodings = Counter(row["encoding"] for row in fixture_hits)
        hit_metrics = sorted({row["metric"] for row in fixture_hits})
        width = int_value(zero_fixture, "cdcache_width")
        zero_columns = int_value(zero_fixture, "leading_zero_bytes")
        output_fixtures.append(
            {
                "rank": fixture.get("rank", ""),
                "rule_type": fixture.get("rule_type", ""),
                "archive": fixture.get("archive", ""),
                "archive_tag": fixture.get("archive_tag", ""),
                "pcx_name": fixture.get("pcx_name", ""),
                "frontier_id": fixture.get("frontier_id", ""),
                "frontier_type": fixture.get("frontier_type", ""),
                "pixel_gap": fixture.get("pixel_gap", ""),
                "segment_gap_bytes": fixture.get("segment_gap_bytes", ""),
                "cdcache_width": str(width),
                "cdcache_height": zero_fixture.get("cdcache_height", ""),
                "zero_columns": str(zero_columns),
                "nonzero_columns": str(max(0, width - zero_columns)),
                "nonzero_slots": str(metrics.get("nonzero_slots", 0)),
                "leading_row_prefix_zero_runs": zero_fixture.get("leading_row_prefix_zero_runs", ""),
                "hit_count": str(len(fixture_hits)),
                "u16le_hit_count": str(encodings.get("u16le", 0)),
                "u16be_hit_count": str(encodings.get("u16be", 0)),
                "byte_hit_count": str(encodings.get("byte", 0)),
                "hit_metrics": ";".join(hit_metrics),
                "segment_head_hex": segment[:32].hex(),
                "issues": ";".join(issues),
            }
        )

    by_metric: list[dict[str, str]] = []
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in hit_rows:
        grouped[(row.get("metric", ""), row.get("metric_value", ""))].append(row)
    for (metric, value), rows in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0])):
        sample = rows[0]
        by_metric.append(
            {
                "metric": metric,
                "metric_value": value,
                "hits": str(len(rows)),
                "fixtures": str(len({(row.get("rank", ""), row.get("pcx_name", "")) for row in rows})),
                "encodings": ";".join(sorted({row.get("encoding", "") for row in rows})),
                "sample_rank": sample.get("rank", ""),
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_offset": sample.get("offset", ""),
            }
        )
    return output_fixtures, hit_rows, by_metric


def summary_row(
    fixture_rows: list[dict[str, str]],
    hit_rows: list[dict[str, str]],
    by_metric: list[dict[str, str]],
) -> dict[str, str]:
    top_metric = by_metric[0] if by_metric else {}
    top_fixture = max(fixture_rows, key=lambda row: int_value(row, "hit_count")) if fixture_rows else {}
    encoding_counts = Counter(row.get("encoding", "") for row in hit_rows)
    issue_rows = sum(1 for row in fixture_rows if row.get("issues"))
    return {
        "scope": "total",
        "fixture_rows": str(len(fixture_rows)),
        "hit_rows": str(len(hit_rows)),
        "fixtures_with_hits": str(sum(1 for row in fixture_rows if int_value(row, "hit_count"))),
        "metric_names": str(len({row.get("metric", "") for row in hit_rows if row.get("metric")})),
        "u16le_hits": str(encoding_counts.get("u16le", 0)),
        "u16be_hits": str(encoding_counts.get("u16be", 0)),
        "byte_hits": str(encoding_counts.get("byte", 0)),
        "top_metric": top_metric.get("metric", ""),
        "top_metric_hits": top_metric.get("hits", "0"),
        "top_fixture_rank": top_fixture.get("rank", ""),
        "top_fixture_pcx": top_fixture.get("pcx_name", ""),
        "top_fixture_hits": top_fixture.get("hit_count", "0"),
        "issue_rows": str(issue_rows),
    }


def render_fixture_row(row: dict[str, str]) -> str:
    return (
        "<tr>"
        f"<td>{html.escape(row.get('rank', ''))}</td>"
        f"<td>{html.escape(row.get('rule_type', ''))}</td>"
        f"<td>{html.escape(row.get('pcx_name', ''))}</td>"
        f"<td>{html.escape(row.get('frontier_id', ''))}</td>"
        f"<td>{html.escape(row.get('cdcache_width', ''))}x{html.escape(row.get('cdcache_height', ''))}</td>"
        f"<td>{html.escape(row.get('zero_columns', ''))}</td>"
        f"<td>{html.escape(row.get('nonzero_slots', ''))}</td>"
        f"<td>{html.escape(row.get('hit_count', ''))}</td>"
        f"<td>{html.escape(row.get('u16le_hit_count', ''))}</td>"
        f"<td>{html.escape(row.get('byte_hit_count', ''))}</td>"
        f"<td>{html.escape(row.get('hit_metrics', ''))}</td>"
        f"<td><code>{html.escape(row.get('segment_head_hex', ''))}</code></td>"
        f"<td>{html.escape(row.get('issues', ''))}</td>"
        "</tr>"
    )


def render_hit_row(row: dict[str, str]) -> str:
    return (
        "<tr>"
        f"<td>{html.escape(row.get('rank', ''))}</td>"
        f"<td>{html.escape(row.get('pcx_name', ''))}</td>"
        f"<td>{html.escape(row.get('frontier_id', ''))}</td>"
        f"<td>{html.escape(row.get('encoding', ''))}</td>"
        f"<td>{html.escape(row.get('offset', ''))}</td>"
        f"<td>{html.escape(row.get('value', ''))}</td>"
        f"<td>{html.escape(row.get('metric', ''))}</td>"
        f"<td><code>{html.escape(row.get('context_hex', ''))}</code></td>"
        "</tr>"
    )


def render_metric_row(row: dict[str, str]) -> str:
    return (
        "<tr>"
        f"<td>{html.escape(row.get('metric', ''))}</td>"
        f"<td>{html.escape(row.get('metric_value', ''))}</td>"
        f"<td>{html.escape(row.get('hits', ''))}</td>"
        f"<td>{html.escape(row.get('fixtures', ''))}</td>"
        f"<td>{html.escape(row.get('encodings', ''))}</td>"
        f"<td>{html.escape(row.get('sample_rank', ''))} {html.escape(row.get('sample_pcx', ''))}</td>"
        f"<td>{html.escape(row.get('sample_offset', ''))}</td>"
        "</tr>"
    )


def build_html(
    summary: dict[str, str],
    fixture_rows: list[dict[str, str]],
    hit_rows: list[dict[str, str]],
    by_metric: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "fixtures": fixture_rows, "hits": hit_rows, "byMetric": by_metric}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("fixtures.csv", output_dir / "fixtures.csv"),
            ("hits.csv", output_dir / "hits.csv"),
            ("by_metric.csv", output_dir / "by_metric.csv"),
        )
    )
    fixture_markup = "\n".join(render_fixture_row(row) for row in fixture_rows)
    hit_markup = "\n".join(render_hit_row(row) for row in hit_rows[:160])
    metric_markup = "\n".join(render_metric_row(row) for row in by_metric)
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
table {{ width: 100%; border-collapse: collapse; min-width: 1240px; }}
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
    <div class="sub">Mots de controle .tex compares aux dimensions, offsets et longueurs de gaps connues.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Fixtures</div><div class="value">{html.escape(summary['fixture_rows'])}</div></div>
    <div class="stat"><div class="label">Hits</div><div class="value">{html.escape(summary['hit_rows'])}</div></div>
    <div class="stat"><div class="label">Metrics</div><div class="value">{html.escape(summary['metric_names'])}</div></div>
    <div class="stat"><div class="label">u16le hits</div><div class="value ok">{html.escape(summary['u16le_hits'])}</div></div>
    <div class="stat"><div class="label">Issues</div><div class="value ok">{html.escape(summary['issue_rows'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div></section>
  <section class="panel">
    <h2>Fixtures</h2>
    <table>
      <thead><tr><th>Rank</th><th>Rule</th><th>PCX</th><th>Frontier</th><th>Size</th><th>Zero columns</th><th>Nonzero slots</th><th>Hits</th><th>u16le</th><th>Byte</th><th>Metrics</th><th>Segment head</th><th>Issues</th></tr></thead>
      <tbody>{fixture_markup}</tbody>
    </table>
  </section>
  <section class="panel">
    <h2>By metric</h2>
    <table>
      <thead><tr><th>Metric</th><th>Value</th><th>Hits</th><th>Fixtures</th><th>Encodings</th><th>Sample</th><th>Offset</th></tr></thead>
      <tbody>{metric_markup}</tbody>
    </table>
  </section>
  <section class="panel">
    <h2>Hits</h2>
    <table>
      <thead><tr><th>Rank</th><th>PCX</th><th>Frontier</th><th>Encoding</th><th>Offset</th><th>Value</th><th>Metric</th><th>Context</th></tr></thead>
      <tbody>{hit_markup}</tbody>
    </table>
  </section>
</main>
<script>
const TEX_GAP_CONTROL_WORD_PROBE = {data_json};
</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    fixtures: Path,
    zero_run_fixtures: Path,
    *,
    limit: int,
    window_bytes: int,
    context_radius: int,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    fixture_rows, hit_rows, by_metric = build_rows(
        fixtures,
        zero_run_fixtures,
        limit=limit,
        window_bytes=window_bytes,
        context_radius=context_radius,
    )
    summary = summary_row(fixture_rows, hit_rows, by_metric)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "fixtures.csv", FIXTURE_FIELDNAMES, fixture_rows)
    write_csv(output_dir / "hits.csv", HIT_FIELDNAMES, hit_rows)
    write_csv(output_dir / "by_metric.csv", BY_METRIC_FIELDNAMES, by_metric)
    (output_dir / "index.html").write_text(
        build_html(summary, fixture_rows, hit_rows, by_metric, output_dir, title)
    )
    return summary, fixture_rows, hit_rows, by_metric


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe .tex gap control windows for known count words.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--zero-run-fixtures", type=Path, default=DEFAULT_ZERO_RUN_FIXTURES)
    parser.add_argument("--limit", type=int, default=32)
    parser.add_argument("--window-bytes", type=int, default=128)
    parser.add_argument("--context-radius", type=int, default=6)
    parser.add_argument("--title", default="Lands of Lore II .tex Gap Control Word Probe")
    args = parser.parse_args()

    summary, _fixture_rows, _hit_rows, _by_metric = write_report(
        args.output,
        args.fixtures,
        args.zero_run_fixtures,
        limit=args.limit,
        window_bytes=args.window_bytes,
        context_radius=args.context_radius,
        title=args.title,
    )
    print(f"Fixture rows: {summary['fixture_rows']}")
    print(f"Hit rows: {summary['hit_rows']}")
    print(f"Metric names: {summary['metric_names']}")
    print(f"u16le hits: {summary['u16le_hits']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
