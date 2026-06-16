#!/usr/bin/env python3
"""Queue zero runs after len64 plus large32 plus medium8 promotion."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

from lolg_tex_gap_decoder_unresolved_zero_queue import (
    FIXTURE_FIELDNAMES,
    QUEUE_FIELDNAMES,
    SIGNATURE_FIELDNAMES,
    SUMMARY_FIELDNAMES,
    build_rows,
    read_csv,
    render_table,
)
from lolg_tex_gap_opcode_probe import relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_len64_promoted_medium8_zero_queue")
DEFAULT_SPANS = Path("output/tex_gap_decoder_len64_promoted_medium8_run_probe/by_span.csv")
DEFAULT_RUNS = Path("output/tex_gap_decoder_len64_promoted_medium8_run_probe/runs.csv")
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")


def build_html(
    summary: dict[str, str],
    queue_rows: list[dict[str, str]],
    signature_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "queue": queue_rows,
        "signatures": signature_rows,
        "fixtures": fixture_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("queue.csv", output_dir / "queue.csv"),
            ("by_signature.csv", output_dir / "by_signature.csv"),
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
    <div class="sub">Ranks remaining zero runs after len64 plus large32 plus medium8 promotion by position and neighbor context.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Zero runs</div><div class="value">{summary['zero_run_rows']}</div></div>
    <div class="stat"><div class="label">Zero bytes</div><div class="value">{summary['zero_bytes']}</div></div>
    <div class="stat"><div class="label">Internal bytes</div><div class="value">{summary['internal_zero_bytes']}</div></div>
    <div class="stat"><div class="label">Max run</div><div class="value">{summary['max_zero_run_bytes']}</div></div>
    <div class="stat"><div class="label">Issues</div><div class="value ok">{summary['issue_rows']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2><div>{links}</div></section>
  <section class="panel"><h2>Top signatures</h2>{render_table(signature_rows, SIGNATURE_FIELDNAMES, 120)}</section>
  <section class="panel"><h2>Queue</h2>{render_table(queue_rows, QUEUE_FIELDNAMES, 260)}</section>
  <section class="panel"><h2>By fixture</h2>{render_table(fixture_rows, FIXTURE_FIELDNAMES, 80)}</section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_ZERO_QUEUE = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Queue .tex zero runs after len64 plus large32 plus medium8 promotion."
    )
    parser.add_argument("--spans", type=Path, default=DEFAULT_SPANS)
    parser.add_argument("--runs", type=Path, default=DEFAULT_RUNS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Len64 Promoted Medium8 Zero Queue",
    )
    args = parser.parse_args()

    summary, queue_rows, signature_rows, by_fixture_rows = build_rows(
        read_csv(args.spans),
        read_csv(args.runs),
        read_csv(args.fixtures),
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "queue.csv", QUEUE_FIELDNAMES, queue_rows)
    write_csv(args.output / "by_signature.csv", SIGNATURE_FIELDNAMES, signature_rows)
    write_csv(args.output / "by_fixture.csv", FIXTURE_FIELDNAMES, by_fixture_rows)
    html_path = args.output / "index.html"
    html_path.write_text(
        build_html(summary, queue_rows, signature_rows, by_fixture_rows, args.output, args.title)
    )

    print(f"Zero runs queued: {summary['zero_run_rows']}")
    print(f"Zero bytes queued: {summary['zero_bytes']}")
    print(f"Internal zero bytes: {summary['internal_zero_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
