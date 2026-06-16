#!/usr/bin/env python3
"""Measure zero/nonzero runs after the promoted large32 gap queue."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

from lolg_tex_gap_decoder_unresolved_run_probe import (
    FIXTURE_FIELDNAMES,
    RUN_FIELDNAMES,
    SPAN_FIELDNAMES,
    SUMMARY_FIELDNAMES,
    build_rows,
    read_csv,
    render_table,
)
from lolg_tex_gap_opcode_probe import relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_len64_promoted_large32_run_probe")
DEFAULT_SPANS = Path("output/tex_gap_decoder_len64_promoted_large32_gap_queue/spans.csv")
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")


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
    <div class="sub">Splits remaining spans after len64 plus large32 promotion into internal zero and nonzero runs.</div>
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
const TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_RUN_PROBE = {data_json};
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
    parser = argparse.ArgumentParser(description="Measure internal runs after the .tex large32 promoted replay.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--spans", type=Path, default=DEFAULT_SPANS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--title", default="Lands of Lore II .tex Len64 Promoted Large32 Run Probe")
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
