#!/usr/bin/env python3
"""Measure zero/nonzero runs inside unresolved .tex clean-gap spans."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_unresolved_run_probe")
DEFAULT_SPANS = Path("output/tex_gap_decoder_clean_gap_queue/spans.csv")
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "fixture_rows",
    "unresolved_span_rows",
    "run_rows",
    "zero_run_rows",
    "nonzero_run_rows",
    "unresolved_bytes",
    "zero_bytes",
    "nonzero_bytes",
    "pure_zero_span_bytes",
    "mixed_span_zero_bytes",
    "max_zero_run_bytes",
    "max_nonzero_run_bytes",
    "largest_run_bytes",
    "largest_run_class",
    "issue_rows",
]

SPAN_FIELDNAMES = [
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "span_index",
    "span_class",
    "start",
    "end",
    "length",
    "run_rows",
    "zero_runs",
    "nonzero_runs",
    "zero_bytes",
    "nonzero_bytes",
    "zero_ratio",
    "leading_run_class",
    "leading_run_length",
    "trailing_run_class",
    "trailing_run_length",
    "max_zero_run_bytes",
    "max_nonzero_run_bytes",
    "left_clean_distance",
    "right_clean_distance",
]

RUN_FIELDNAMES = [
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "span_index",
    "run_index",
    "run_class",
    "span_start",
    "span_end",
    "start",
    "end",
    "offset_in_span",
    "length",
    "head_hex",
    "tail_hex",
    "left_clean_distance",
    "right_clean_distance",
]

FIXTURE_FIELDNAMES = [
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "unresolved_span_rows",
    "run_rows",
    "zero_run_rows",
    "nonzero_run_rows",
    "unresolved_bytes",
    "zero_bytes",
    "nonzero_bytes",
    "max_zero_run_bytes",
    "max_nonzero_run_bytes",
]


@dataclass(frozen=True)
class Run:
    start: int
    end: int
    zero: bool

    @property
    def length(self) -> int:
        return self.end - self.start

    @property
    def run_class(self) -> str:
        return "zero" if self.zero else "nonzero"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def fixture_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", "")


def fixture_sort_key(key: tuple[str, str, str]) -> tuple[int, str, str]:
    rank, pcx_name, frontier_id = key
    return int(rank) if rank.isdigit() else 999999, pcx_name, frontier_id


def load_bytes(path_text: str, issues: list[str], label: str) -> bytes:
    if not path_text:
        issues.append(f"missing_{label}_path")
        return b""
    try:
        return Path(path_text).read_bytes()
    except OSError as exc:
        issues.append(f"read_{label}_failed:{exc}")
        return b""


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


def build_rows(
    span_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    fixtures = {fixture_key(row): row for row in fixture_rows}
    expected_by_fixture: dict[tuple[str, str, str], bytes] = {}
    issues: list[str] = []
    for key, fixture in fixtures.items():
        fixture_issues: list[str] = []
        expected_by_fixture[key] = load_bytes(fixture.get("expected_gap_path", ""), fixture_issues, "expected")
        issues.extend(f"{key}:{issue}" for issue in fixture_issues)

    unresolved_spans = [
        row for row in span_rows if row.get("span_class", "").startswith("unresolved")
    ]
    output_spans: list[dict[str, str]] = []
    output_runs: list[dict[str, str]] = []
    by_fixture: dict[tuple[str, str, str], dict[str, int | str]] = defaultdict(
        lambda: {
            "unresolved_span_rows": 0,
            "run_rows": 0,
            "zero_run_rows": 0,
            "nonzero_run_rows": 0,
            "unresolved_bytes": 0,
            "zero_bytes": 0,
            "nonzero_bytes": 0,
            "max_zero_run_bytes": 0,
            "max_nonzero_run_bytes": 0,
        }
    )
    fixture_meta: dict[tuple[str, str, str], dict[str, str]] = {}

    for span in sorted(
        unresolved_spans,
        key=lambda row: (
            fixture_sort_key(fixture_key(row)),
            int_value(row, "start"),
            int_value(row, "span_index"),
        ),
    ):
        key = fixture_key(span)
        expected = expected_by_fixture.get(key, b"")
        start = int_value(span, "start")
        end = int_value(span, "end")
        bounded_start = max(0, min(start, len(expected)))
        bounded_end = max(bounded_start, min(end, len(expected)))
        chunk = expected[bounded_start:bounded_end]
        runs = binary_runs(chunk)
        zero_runs = [run for run in runs if run.zero]
        nonzero_runs = [run for run in runs if not run.zero]
        zero_bytes = sum(run.length for run in zero_runs)
        nonzero_bytes = sum(run.length for run in nonzero_runs)
        max_zero = max([run.length for run in zero_runs] or [0])
        max_nonzero = max([run.length for run in nonzero_runs] or [0])
        leading = runs[0] if runs else Run(0, 0, False)
        trailing = runs[-1] if runs else Run(0, 0, False)
        zero_ratio = zero_bytes / len(chunk) if chunk else 0.0

        totals = by_fixture[key]
        fixture_meta[key] = span
        totals["unresolved_span_rows"] = int(totals["unresolved_span_rows"]) + 1
        totals["run_rows"] = int(totals["run_rows"]) + len(runs)
        totals["zero_run_rows"] = int(totals["zero_run_rows"]) + len(zero_runs)
        totals["nonzero_run_rows"] = int(totals["nonzero_run_rows"]) + len(nonzero_runs)
        totals["unresolved_bytes"] = int(totals["unresolved_bytes"]) + len(chunk)
        totals["zero_bytes"] = int(totals["zero_bytes"]) + zero_bytes
        totals["nonzero_bytes"] = int(totals["nonzero_bytes"]) + nonzero_bytes
        totals["max_zero_run_bytes"] = max(int(totals["max_zero_run_bytes"]), max_zero)
        totals["max_nonzero_run_bytes"] = max(int(totals["max_nonzero_run_bytes"]), max_nonzero)

        output_spans.append(
            {
                "rank": span.get("rank", ""),
                "archive": span.get("archive", ""),
                "archive_tag": span.get("archive_tag", ""),
                "pcx_name": span.get("pcx_name", ""),
                "frontier_id": span.get("frontier_id", ""),
                "span_index": span.get("span_index", ""),
                "span_class": span.get("span_class", ""),
                "start": str(bounded_start),
                "end": str(bounded_end),
                "length": str(len(chunk)),
                "run_rows": str(len(runs)),
                "zero_runs": str(len(zero_runs)),
                "nonzero_runs": str(len(nonzero_runs)),
                "zero_bytes": str(zero_bytes),
                "nonzero_bytes": str(nonzero_bytes),
                "zero_ratio": f"{zero_ratio:.6f}",
                "leading_run_class": leading.run_class if runs else "",
                "leading_run_length": str(leading.length if runs else 0),
                "trailing_run_class": trailing.run_class if runs else "",
                "trailing_run_length": str(trailing.length if runs else 0),
                "max_zero_run_bytes": str(max_zero),
                "max_nonzero_run_bytes": str(max_nonzero),
                "left_clean_distance": span.get("left_clean_distance", ""),
                "right_clean_distance": span.get("right_clean_distance", ""),
            }
        )
        for run_index, run in enumerate(runs):
            run_start = bounded_start + run.start
            run_end = bounded_start + run.end
            run_bytes = expected[run_start:run_end]
            output_runs.append(
                {
                    "rank": span.get("rank", ""),
                    "archive": span.get("archive", ""),
                    "archive_tag": span.get("archive_tag", ""),
                    "pcx_name": span.get("pcx_name", ""),
                    "frontier_id": span.get("frontier_id", ""),
                    "span_index": span.get("span_index", ""),
                    "run_index": str(run_index),
                    "run_class": run.run_class,
                    "span_start": str(bounded_start),
                    "span_end": str(bounded_end),
                    "start": str(run_start),
                    "end": str(run_end),
                    "offset_in_span": str(run.start),
                    "length": str(run.length),
                    "head_hex": run_bytes[:16].hex(),
                    "tail_hex": run_bytes[-16:].hex(),
                    "left_clean_distance": span.get("left_clean_distance", ""),
                    "right_clean_distance": span.get("right_clean_distance", ""),
                }
            )

    fixture_output: list[dict[str, str]] = []
    for key in sorted(by_fixture, key=fixture_sort_key):
        totals = by_fixture[key]
        meta = fixture_meta[key]
        fixture_output.append(
            {
                "rank": key[0],
                "archive": meta.get("archive", ""),
                "archive_tag": meta.get("archive_tag", ""),
                "pcx_name": key[1],
                "frontier_id": key[2],
                **{field: str(totals[field]) for field in FIXTURE_FIELDNAMES[5:]},
            }
        )

    output_runs.sort(
        key=lambda row: (
            row.get("run_class") != "zero",
            -int_value(row, "length"),
            int_value(row, "rank"),
            int_value(row, "start"),
        )
    )
    output_spans.sort(
        key=lambda row: (
            -int_value(row, "length"),
            int_value(row, "rank"),
            int_value(row, "start"),
        )
    )
    zero_run_rows = [row for row in output_runs if row.get("run_class") == "zero"]
    nonzero_run_rows = [row for row in output_runs if row.get("run_class") == "nonzero"]
    largest_run = max(output_runs, key=lambda row: int_value(row, "length")) if output_runs else {}
    summary = {
        "scope": "total",
        "fixture_rows": str(len(fixture_output)),
        "unresolved_span_rows": str(len(output_spans)),
        "run_rows": str(len(output_runs)),
        "zero_run_rows": str(len(zero_run_rows)),
        "nonzero_run_rows": str(len(nonzero_run_rows)),
        "unresolved_bytes": str(sum(int_value(row, "length") for row in output_spans)),
        "zero_bytes": str(sum(int_value(row, "length") for row in zero_run_rows)),
        "nonzero_bytes": str(sum(int_value(row, "length") for row in nonzero_run_rows)),
        "pure_zero_span_bytes": str(
            sum(
                int_value(row, "length")
                for row in output_spans
                if row.get("span_class") == "unresolved_zero"
            )
        ),
        "mixed_span_zero_bytes": str(
            sum(
                int_value(row, "zero_bytes")
                for row in output_spans
                if row.get("span_class") == "unresolved_mixed"
            )
        ),
        "max_zero_run_bytes": str(max([int_value(row, "length") for row in zero_run_rows] or [0])),
        "max_nonzero_run_bytes": str(max([int_value(row, "length") for row in nonzero_run_rows] or [0])),
        "largest_run_bytes": str(int_value(largest_run, "length")),
        "largest_run_class": largest_run.get("run_class", ""),
        "issue_rows": str(len(issues)),
    }
    return summary, output_spans, output_runs, fixture_output


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 240) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    span_rows: list[dict[str, str]],
    run_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "spans": span_rows, "runs": run_rows, "fixtures": fixture_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("by_span.csv", output_dir / "by_span.csv"),
            ("runs.csv", output_dir / "runs.csv"),
            ("by_fixture.csv", output_dir / "by_fixture.csv"),
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
  --bg: #101417;
  --panel: #171f22;
  --line: #31424a;
  --text: #edf5f4;
  --muted: #9dafb5;
  --accent: #77d3b1;
  --ok: #80df94;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  min-height: 100vh;
  background: var(--bg);
  color: var(--text);
  font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}}
.wrap {{ width: min(1680px, calc(100vw - 28px)); margin: 0 auto; }}
header {{ border-bottom: 1px solid var(--line); background: #12191b; padding: 18px 0 14px; }}
h1 {{ margin: 0; font-size: 21px; font-weight: 720; letter-spacing: 0; }}
h2 {{ margin: 0 0 10px; font-size: 16px; }}
.sub {{ color: var(--muted); margin-top: 4px; }}
main {{ padding: 16px 0 28px; display: grid; gap: 16px; }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 10px; }}
.stat, .panel {{ border: 1px solid var(--line); border-radius: 8px; background: var(--panel); padding: 10px; }}
.label, .muted {{ color: var(--muted); }}
.value {{ font-size: 22px; font-weight: 760; line-height: 1.05; margin-top: 4px; }}
.ok {{ color: var(--ok); }}
.panel {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; min-width: 1320px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Splits unresolved clean-gap spans into internal zero and nonzero runs.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Unresolved bytes</div><div class="value">{html.escape(summary['unresolved_bytes'])}</div></div>
    <div class="stat"><div class="label">Zero bytes inside</div><div class="value ok">{html.escape(summary['zero_bytes'])}</div></div>
    <div class="stat"><div class="label">Run rows</div><div class="value">{html.escape(summary['run_rows'])}</div></div>
    <div class="stat"><div class="label">Max zero run</div><div class="value">{html.escape(summary['max_zero_run_bytes'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div></section>
  <section class="panel"><h2>Runs</h2>{render_table(run_rows, RUN_FIELDNAMES)}</section>
  <section class="panel"><h2>Spans</h2>{render_table(span_rows, SPAN_FIELDNAMES)}</section>
  <section class="panel"><h2>Fixtures</h2>{render_table(fixture_rows, FIXTURE_FIELDNAMES)}</section>
</main>
<script>
const TEX_GAP_DECODER_UNRESOLVED_RUN_PROBE = {data_json};
</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    spans_path: Path,
    fixtures_path: Path,
    *,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary, span_rows, run_rows, fixture_rows = build_rows(
        read_csv(spans_path),
        read_csv(fixtures_path),
    )
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "by_span.csv", SPAN_FIELDNAMES, span_rows)
    write_csv(output_dir / "runs.csv", RUN_FIELDNAMES, run_rows)
    write_csv(output_dir / "by_fixture.csv", FIXTURE_FIELDNAMES, fixture_rows)
    (output_dir / "index.html").write_text(
        build_html(summary, span_rows, run_rows, fixture_rows, output_dir, title)
    )
    return summary, run_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure internal runs in unresolved .tex clean-gap spans.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--spans", type=Path, default=DEFAULT_SPANS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--title", default="Lands of Lore II .tex Decoder Unresolved Run Probe")
    args = parser.parse_args()

    summary, _run_rows = write_report(
        args.output,
        args.spans,
        args.fixtures,
        title=args.title,
    )
    print(f"Unresolved bytes: {summary['unresolved_bytes']}")
    print(f"Zero bytes inside unresolved spans: {summary['zero_bytes']}")
    print(f"Run rows: {summary['run_rows']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
