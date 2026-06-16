#!/usr/bin/env python3
"""Measure zero/nonzero run structure in prioritized .tex gap fixtures."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from lolg_tex_gap_opcode_probe import comparison_lookup, int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_zero_run_probe")
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_FRONTIERS = Path("output/tex_gap_frontier_report/frontiers.csv")
DEFAULT_COMPARISONS = Path("output/tex_exact_cdcache_compare/comparisons.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "fixture_rows",
    "run_rows",
    "zero_run_rows",
    "nonzero_run_rows",
    "fixtures_with_leading_zero",
    "fixtures_with_row_prefix_zero_runs",
    "total_zero_bytes",
    "max_leading_zero_bytes",
    "max_zero_run_bytes",
    "best_zero_rank",
    "best_zero_pcx",
    "best_zero_frontier_id",
    "best_period_guess",
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
    "gap_start",
    "gap_start_x",
    "gap_start_y",
    "zero_bytes",
    "zero_ratio",
    "zero_runs",
    "nonzero_runs",
    "leading_zero_bytes",
    "trailing_zero_bytes",
    "max_zero_run_bytes",
    "max_nonzero_run_bytes",
    "row_prefix_zero_runs",
    "row_prefix_zero_bytes",
    "leading_row_prefix_zero_runs",
    "zero_run_period_guess",
    "zero_run_period_hits",
    "expected_head_hex",
    "segment_head_hex",
    "issues",
]

RUN_FIELDNAMES = [
    "rank",
    "pcx_name",
    "frontier_id",
    "run_index",
    "run_class",
    "start",
    "end",
    "length",
    "start_x",
    "start_y",
    "end_x",
    "end_y",
    "head_hex",
]


@dataclass(frozen=True)
class Run:
    start: int
    end: int
    zero: bool

    @property
    def length(self) -> int:
        return self.end - self.start


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def load_bytes(path_text: str, issues: list[str]) -> bytes:
    if not path_text:
        issues.append("missing_expected_path")
        return b""
    try:
        return Path(path_text).read_bytes()
    except OSError as exc:
        issues.append(f"read_expected_failed:{exc}")
        return b""


def frontier_lookup(rows: list[dict[str, str]]) -> dict[tuple[str, str, str], dict[str, str]]:
    return {
        (row.get("archive", ""), row.get("pcx_name", ""), row.get("frontier_id", "")): row
        for row in rows
    }


def binary_runs(data: bytes) -> list[Run]:
    if not data:
        return []
    runs: list[Run] = []
    start = 0
    current_zero = data[0] == 0
    for index, value in enumerate(data[1:], start=1):
        value_zero = value == 0
        if value_zero != current_zero:
            runs.append(Run(start, index, current_zero))
            start = index
            current_zero = value_zero
    runs.append(Run(start, len(data), current_zero))
    return runs


def leading_zero_bytes(runs: list[Run]) -> int:
    return runs[0].length if runs and runs[0].zero else 0


def trailing_zero_bytes(runs: list[Run]) -> int:
    return runs[-1].length if runs and runs[-1].zero else 0


def period_guess(zero_runs: list[Run]) -> tuple[int, int]:
    starts = [run.start for run in zero_runs]
    deltas = [right - left for left, right in zip(starts, starts[1:]) if right > left]
    if not deltas:
        return 0, 0
    counts = Counter(deltas)
    best_delta, hits = max(counts.items(), key=lambda item: (item[1], -item[0]))
    return best_delta, hits


def row_prefix_zero_stats(zero_runs: list[Run], width: int, leading_zero: int) -> tuple[int, int, int]:
    if width <= 0:
        return 0, 0, 0
    row_prefix = [run for run in zero_runs if run.start % width == 0]
    row_prefix_bytes = sum(run.length for run in row_prefix)
    leading_rows = 0
    if leading_zero > 0:
        by_start = {run.start: run for run in row_prefix}
        while True:
            run = by_start.get(leading_rows * width)
            if not run or run.length != leading_zero:
                break
            leading_rows += 1
    return len(row_prefix), row_prefix_bytes, leading_rows


def xy(position: int, width: int) -> tuple[str, str]:
    if width <= 0:
        return "", ""
    return str(position % width), str(position // width)


def build_rows(
    fixtures: Path,
    frontiers: Path,
    comparisons: Path,
    *,
    limit: int,
    context_bytes: int,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    fixture_rows = sorted(read_rows(fixtures), key=lambda row: int_value(row, "rank"))
    if limit > 0:
        fixture_rows = fixture_rows[:limit]
    frontiers_by_key = frontier_lookup(read_rows(frontiers))
    comparisons_by_key = comparison_lookup(read_rows(comparisons))

    output_fixtures: list[dict[str, str]] = []
    output_runs: list[dict[str, str]] = []

    for fixture in fixture_rows:
        issues: list[str] = []
        expected = load_bytes(fixture.get("expected_gap_path", ""), issues)
        if len(expected) != int_value(fixture, "pixel_gap"):
            issues.append("expected_size_mismatch")
        key = (fixture.get("archive", ""), fixture.get("pcx_name", ""), fixture.get("frontier_id", ""))
        frontier = frontiers_by_key.get(key, {})
        comparison = comparisons_by_key.get((fixture.get("archive", ""), fixture.get("pcx_name", "")), {})
        width = int_value(comparison, "cdcache_width")
        height = int_value(comparison, "cdcache_height")
        gap_start = int_value(frontier, "gap_start")
        runs = binary_runs(expected)
        zero_runs = [run for run in runs if run.zero]
        nonzero_runs = [run for run in runs if not run.zero]
        leading_zero = leading_zero_bytes(runs)
        row_prefix_runs, row_prefix_bytes, leading_row_prefix_runs = row_prefix_zero_stats(
            zero_runs,
            width,
            leading_zero,
        )
        period, period_hits = period_guess(zero_runs)
        zero_bytes = sum(run.length for run in zero_runs)
        pixel_gap = len(expected)

        start_x, start_y = xy(gap_start, width)
        output_fixtures.append(
            {
                "rank": fixture.get("rank", ""),
                "rule_type": fixture.get("rule_type", ""),
                "archive": fixture.get("archive", ""),
                "archive_tag": fixture.get("archive_tag", ""),
                "pcx_name": fixture.get("pcx_name", ""),
                "frontier_id": fixture.get("frontier_id", ""),
                "frontier_type": fixture.get("frontier_type", ""),
                "pixel_gap": str(pixel_gap),
                "segment_gap_bytes": fixture.get("segment_gap_bytes", ""),
                "cdcache_width": str(width),
                "cdcache_height": str(height),
                "gap_start": str(gap_start),
                "gap_start_x": start_x,
                "gap_start_y": start_y,
                "zero_bytes": str(zero_bytes),
                "zero_ratio": f"{(zero_bytes / pixel_gap) if pixel_gap else 0.0:.6f}",
                "zero_runs": str(len(zero_runs)),
                "nonzero_runs": str(len(nonzero_runs)),
                "leading_zero_bytes": str(leading_zero),
                "trailing_zero_bytes": str(trailing_zero_bytes(runs)),
                "max_zero_run_bytes": str(max([run.length for run in zero_runs] or [0])),
                "max_nonzero_run_bytes": str(max([run.length for run in nonzero_runs] or [0])),
                "row_prefix_zero_runs": str(row_prefix_runs),
                "row_prefix_zero_bytes": str(row_prefix_bytes),
                "leading_row_prefix_zero_runs": str(leading_row_prefix_runs),
                "zero_run_period_guess": str(period),
                "zero_run_period_hits": str(period_hits),
                "expected_head_hex": expected[:context_bytes].hex(),
                "segment_head_hex": fixture.get("segment_head_hex", ""),
                "issues": ";".join(issues),
            }
        )

        for run_index, run in enumerate(runs, start=1):
            absolute_start = gap_start + run.start
            absolute_end = gap_start + max(run.end - 1, run.start)
            start_x, start_y = xy(absolute_start, width)
            end_x, end_y = xy(absolute_end, width)
            output_runs.append(
                {
                    "rank": fixture.get("rank", ""),
                    "pcx_name": fixture.get("pcx_name", ""),
                    "frontier_id": fixture.get("frontier_id", ""),
                    "run_index": str(run_index),
                    "run_class": "zero" if run.zero else "nonzero",
                    "start": str(run.start),
                    "end": str(run.end),
                    "length": str(run.length),
                    "start_x": start_x,
                    "start_y": start_y,
                    "end_x": end_x,
                    "end_y": end_y,
                    "head_hex": expected[run.start : min(run.end, run.start + context_bytes)].hex(),
                }
            )

    return output_fixtures, output_runs


def summary_row(fixture_rows: list[dict[str, str]], run_rows: list[dict[str, str]]) -> dict[str, str]:
    best_zero = max(fixture_rows, key=lambda row: int_value(row, "max_zero_run_bytes")) if fixture_rows else {}
    zero_run_rows = [row for row in run_rows if row.get("run_class") == "zero"]
    nonzero_run_rows = [row for row in run_rows if row.get("run_class") == "nonzero"]
    issue_rows = sum(1 for row in fixture_rows if row.get("issues"))
    return {
        "scope": "total",
        "fixture_rows": str(len(fixture_rows)),
        "run_rows": str(len(run_rows)),
        "zero_run_rows": str(len(zero_run_rows)),
        "nonzero_run_rows": str(len(nonzero_run_rows)),
        "fixtures_with_leading_zero": str(sum(1 for row in fixture_rows if int_value(row, "leading_zero_bytes"))),
        "fixtures_with_row_prefix_zero_runs": str(
            sum(1 for row in fixture_rows if int_value(row, "row_prefix_zero_runs"))
        ),
        "total_zero_bytes": str(sum(int_value(row, "zero_bytes") for row in fixture_rows)),
        "max_leading_zero_bytes": str(max([int_value(row, "leading_zero_bytes") for row in fixture_rows] or [0])),
        "max_zero_run_bytes": str(int_value(best_zero, "max_zero_run_bytes")),
        "best_zero_rank": best_zero.get("rank", ""),
        "best_zero_pcx": best_zero.get("pcx_name", ""),
        "best_zero_frontier_id": best_zero.get("frontier_id", ""),
        "best_period_guess": best_zero.get("zero_run_period_guess", ""),
        "issue_rows": str(issue_rows),
    }


def render_fixture_row(row: dict[str, str]) -> str:
    return (
        "<tr>"
        f"<td>{html.escape(row.get('rank', ''))}</td>"
        f"<td>{html.escape(row.get('rule_type', ''))}</td>"
        f"<td>{html.escape(row.get('pcx_name', ''))}</td>"
        f"<td>{html.escape(row.get('frontier_id', ''))}</td>"
        f"<td>{html.escape(row.get('pixel_gap', ''))}</td>"
        f"<td>{html.escape(row.get('cdcache_width', ''))}x{html.escape(row.get('cdcache_height', ''))}</td>"
        f"<td>{html.escape(row.get('zero_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('zero_ratio', ''))}</td>"
        f"<td>{html.escape(row.get('leading_zero_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('max_zero_run_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('row_prefix_zero_runs', ''))}</td>"
        f"<td>{html.escape(row.get('leading_row_prefix_zero_runs', ''))}</td>"
        f"<td>{html.escape(row.get('zero_run_period_guess', ''))}</td>"
        f"<td>{html.escape(row.get('issues', ''))}</td>"
        "</tr>"
    )


def render_run_row(row: dict[str, str]) -> str:
    return (
        "<tr>"
        f"<td>{html.escape(row.get('rank', ''))}</td>"
        f"<td>{html.escape(row.get('pcx_name', ''))}</td>"
        f"<td>{html.escape(row.get('frontier_id', ''))}</td>"
        f"<td>{html.escape(row.get('run_index', ''))}</td>"
        f"<td>{html.escape(row.get('run_class', ''))}</td>"
        f"<td>{html.escape(row.get('start', ''))}</td>"
        f"<td>{html.escape(row.get('length', ''))}</td>"
        f"<td>{html.escape(row.get('start_x', ''))},{html.escape(row.get('start_y', ''))}</td>"
        f"<td>{html.escape(row.get('end_x', ''))},{html.escape(row.get('end_y', ''))}</td>"
        f"<td><code>{html.escape(row.get('head_hex', ''))}</code></td>"
        "</tr>"
    )


def build_html(
    summary: dict[str, str],
    fixture_rows: list[dict[str, str]],
    run_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "fixtures": fixture_rows, "runs": run_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("fixtures.csv", output_dir / "fixtures.csv"),
            ("runs.csv", output_dir / "runs.csv"),
        )
    )
    fixture_markup = "\n".join(render_fixture_row(row) for row in fixture_rows)
    top_runs = sorted(
        [row for row in run_rows if row.get("run_class") == "zero"],
        key=lambda row: int_value(row, "length"),
        reverse=True,
    )[:128]
    run_markup = "\n".join(render_run_row(row) for row in top_runs)
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
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
code {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; overflow-wrap: anywhere; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Structure zero/nonzero des gaps .tex attendus par fixture.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Fixtures</div><div class="value">{html.escape(summary['fixture_rows'])}</div></div>
    <div class="stat"><div class="label">Runs</div><div class="value">{html.escape(summary['run_rows'])}</div></div>
    <div class="stat"><div class="label">Zero bytes</div><div class="value">{html.escape(summary['total_zero_bytes'])}</div></div>
    <div class="stat"><div class="label">Max zero run</div><div class="value ok">{html.escape(summary['max_zero_run_bytes'])}</div></div>
    <div class="stat"><div class="label">Issues</div><div class="value ok">{html.escape(summary['issue_rows'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div></section>
  <section class="panel">
    <h2>Fixtures</h2>
    <table>
      <thead><tr><th>Rank</th><th>Rule</th><th>PCX</th><th>Frontier</th><th>Pixels</th><th>Size</th><th>Zero bytes</th><th>Zero ratio</th><th>Leading zero</th><th>Max zero</th><th>Row-prefix runs</th><th>Leading rows</th><th>Period</th><th>Issues</th></tr></thead>
      <tbody>{fixture_markup}</tbody>
    </table>
  </section>
  <section class="panel">
    <h2>Largest zero runs</h2>
    <table>
      <thead><tr><th>Rank</th><th>PCX</th><th>Frontier</th><th>Run</th><th>Class</th><th>Start</th><th>Length</th><th>Start xy</th><th>End xy</th><th>Head</th></tr></thead>
      <tbody>{run_markup}</tbody>
    </table>
  </section>
</main>
<script>
const TEX_GAP_ZERO_RUN_PROBE = {data_json};
</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    fixtures: Path,
    frontiers: Path,
    comparisons: Path,
    *,
    limit: int,
    context_bytes: int,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    fixture_rows, run_rows = build_rows(
        fixtures,
        frontiers,
        comparisons,
        limit=limit,
        context_bytes=context_bytes,
    )
    summary = summary_row(fixture_rows, run_rows)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "fixtures.csv", FIXTURE_FIELDNAMES, fixture_rows)
    write_csv(output_dir / "runs.csv", RUN_FIELDNAMES, run_rows)
    (output_dir / "index.html").write_text(build_html(summary, fixture_rows, run_rows, output_dir, title))
    return summary, fixture_rows, run_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe zero/nonzero run structure in .tex gap fixtures.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--frontiers", type=Path, default=DEFAULT_FRONTIERS)
    parser.add_argument("--comparisons", type=Path, default=DEFAULT_COMPARISONS)
    parser.add_argument("--limit", type=int, default=32)
    parser.add_argument("--context-bytes", type=int, default=32)
    parser.add_argument("--title", default="Lands of Lore II .tex Gap Zero Run Probe")
    args = parser.parse_args()

    summary, _fixture_rows, _run_rows = write_report(
        args.output,
        args.fixtures,
        args.frontiers,
        args.comparisons,
        limit=args.limit,
        context_bytes=args.context_bytes,
        title=args.title,
    )
    print(f"Fixture rows: {summary['fixture_rows']}")
    print(f"Run rows: {summary['run_rows']}")
    print(f"Zero run rows: {summary['zero_run_rows']}")
    print(f"Max zero run bytes: {summary['max_zero_run_bytes']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
