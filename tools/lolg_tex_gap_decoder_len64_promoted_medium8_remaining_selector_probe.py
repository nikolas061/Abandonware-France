#!/usr/bin/env python3
"""Score selectors for remaining post-medium8 medium8 internal zero targets."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

from lolg_tex_gap_decoder_len64_promoted_medium8_selector_probe import (
    CANDIDATE_FIELDNAMES,
    GREEDY_FIELDNAMES,
    SUMMARY_FIELDNAMES,
    TARGET_FIELDNAMES,
    build_rows,
    read_csv,
    render_table,
)
from lolg_tex_gap_opcode_probe import relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_len64_promoted_medium8_remaining_selector_probe")
DEFAULT_TARGETS = Path("output/tex_gap_decoder_len64_promoted_medium8_zero_source_probe/targets.csv")
DEFAULT_OPERATIONS = Path("output/tex_gap_segmentation_control_correlation_probe/operations.csv")


def build_html(
    summary: dict[str, str],
    candidates: list[dict[str, str]],
    greedy: list[dict[str, str]],
    targets: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "candidates": candidates,
        "greedy": greedy,
        "targets": targets,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("candidates.csv", output_dir / "candidates.csv"),
            ("greedy.csv", output_dir / "greedy.csv"),
            ("targets.csv", output_dir / "targets.csv"),
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
    <div class="sub">Scores source-side selectors for remaining post-medium8 medium8 internal zero targets.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Target bytes</div><div class="value">{summary['target_bytes']}</div></div>
    <div class="stat"><div class="label">Best target bytes</div><div class="value">{summary['best_selector_target_bytes']}</div></div>
    <div class="stat"><div class="label">Best false bytes</div><div class="value ok">{summary['best_selector_false_bytes']}</div></div>
    <div class="stat"><div class="label">Greedy target bytes</div><div class="value">{summary['greedy_target_bytes']}</div></div>
    <div class="stat"><div class="label">Greedy selectors</div><div class="value">{summary['greedy_selector_rows']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2><div>{links}</div></section>
  <section class="panel"><h2>Greedy false-free union</h2>{render_table(greedy, GREEDY_FIELDNAMES, 120)}</section>
  <section class="panel"><h2>Candidates</h2>{render_table(candidates, CANDIDATE_FIELDNAMES, 180)}</section>
  <section class="panel"><h2>Targets</h2>{render_table(targets, TARGET_FIELDNAMES, 120)}</section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_REMAINING_SELECTOR_PROBE = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Score source-side selectors for remaining post-medium8 medium8 internal zero targets."
    )
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("--operations", type=Path, default=DEFAULT_OPERATIONS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Len64 Promoted Medium8 Remaining Selector Probe",
    )
    args = parser.parse_args()

    summary, candidates, greedy, targets = build_rows(read_csv(args.targets), read_csv(args.operations))
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "candidates.csv", CANDIDATE_FIELDNAMES, candidates)
    write_csv(args.output / "greedy.csv", GREEDY_FIELDNAMES, greedy)
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, targets)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, candidates, greedy, targets, args.output, args.title))

    print(f"Target rows: {summary['target_rows']}")
    print(f"Best selector: {summary['best_selector']}")
    print(f"Best target bytes: {summary['best_selector_target_bytes']}")
    print(f"Greedy target bytes: {summary['greedy_target_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
