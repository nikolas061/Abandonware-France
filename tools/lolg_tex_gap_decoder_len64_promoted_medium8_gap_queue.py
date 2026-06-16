#!/usr/bin/env python3
"""Rank remaining .tex gap spans after the promoted medium8 replay."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

from lolg_tex_gap_decoder_len64_promoted_gap_queue import (
    FIXTURE_FIELDNAMES,
    SPAN_FIELDNAMES,
    SUMMARY_FIELDNAMES,
    build_rows,
    read_csv,
    render_table,
)
from lolg_tex_gap_opcode_probe import relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_len64_promoted_medium8_gap_queue")
DEFAULT_FIXTURE_MANIFEST = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_PROMOTED_FIXTURES = Path("output/tex_gap_decoder_len64_promoted_medium8_replay/fixtures.csv")
DEFAULT_CLEAN_DECISIONS = Path("output/tex_gap_decoder_clean_replay/decisions.csv")


def build_html(
    summary: dict[str, str],
    span_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "spans": span_rows, "fixtures": fixture_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("spans.csv", output_dir / "spans.csv"),
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
  --risk: #f0a064;
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
.risk {{ color: var(--risk); }}
.panel {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; min-width: 1440px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Remaining spans after len64 plus large32 plus medium8 promoted replay.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Clean bytes</div><div class="value ok">{html.escape(summary['clean_bytes'])}</div></div>
    <div class="stat"><div class="label">Medium8 added</div><div class="value ok">{html.escape(summary['selector_added_bytes'])}</div></div>
    <div class="stat"><div class="label">Rejected false-risk</div><div class="value risk">{html.escape(summary['rejected_false_bytes'])}</div></div>
    <div class="stat"><div class="label">Unresolved bytes</div><div class="value">{html.escape(summary['unresolved_bytes'])}</div></div>
    <div class="stat"><div class="label">Largest unresolved</div><div class="value">{html.escape(summary['largest_unresolved_span'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div></section>
  <section class="panel"><h2>Spans</h2>{render_table(span_rows, SPAN_FIELDNAMES)}</section>
  <section class="panel"><h2>Fixtures</h2>{render_table(fixture_rows, FIXTURE_FIELDNAMES)}</section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_GAP_QUEUE = {data_json};
</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    manifest_path: Path,
    promoted_fixtures_path: Path,
    clean_decisions_path: Path,
    *,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary, span_rows, fixture_rows = build_rows(
        read_csv(manifest_path),
        read_csv(promoted_fixtures_path),
        read_csv(clean_decisions_path),
    )
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "spans.csv", SPAN_FIELDNAMES, span_rows)
    write_csv(output_dir / "by_fixture.csv", FIXTURE_FIELDNAMES, fixture_rows)
    (output_dir / "index.html").write_text(build_html(summary, span_rows, fixture_rows, output_dir, title))
    return summary, span_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Rank .tex gaps after the promoted medium8 replay.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fixture-manifest", type=Path, default=DEFAULT_FIXTURE_MANIFEST)
    parser.add_argument("--promoted-fixtures", type=Path, default=DEFAULT_PROMOTED_FIXTURES)
    parser.add_argument("--clean-decisions", type=Path, default=DEFAULT_CLEAN_DECISIONS)
    parser.add_argument("--title", default="Lands of Lore II .tex Len64 Promoted Medium8 Gap Queue")
    args = parser.parse_args()

    summary, _span_rows = write_report(
        args.output,
        args.fixture_manifest,
        args.promoted_fixtures,
        args.clean_decisions,
        title=args.title,
    )
    print(f"Clean bytes: {summary['clean_bytes']}")
    print(f"Medium8 added bytes: {summary['selector_added_bytes']}")
    print(f"Rejected false-risk bytes: {summary['rejected_false_bytes']}")
    print(f"Unresolved bytes: {summary['unresolved_bytes']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
