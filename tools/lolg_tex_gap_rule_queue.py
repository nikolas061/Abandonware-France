#!/usr/bin/env python3
"""Build a prioritized decoder-rule queue from .tex gap probes."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
from collections import Counter
from pathlib import Path

from lolg_tex_gap_opcode_probe import float_value, int_value, read_rows, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_rule_queue")
DEFAULT_OPCODE_PROBE = Path("output/tex_gap_opcode_probe/probe.csv")
DEFAULT_RLE_BEST = Path("output/tex_gap_rle_probe/best_by_frontier.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "queue_rows",
    "rule_types",
    "top_priority",
    "top_rule_type",
    "top_frontier_id",
    "top_pcx",
    "compact_rows",
    "expanded_rows",
    "literal_rows",
    "short_echo_rows",
    "balanced_rows",
    "issue_rows",
]

QUEUE_FIELDNAMES = [
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
    "rle_best_variant",
    "rle_best_prefix_bytes",
    "expected_zero_ratio",
    "segment_gap_entropy",
    "expected_gap_entropy",
    "evidence_summary",
    "next_action",
    "issues",
]

RULE_FIELDNAMES = [
    "rule_type",
    "rows",
    "pixel_gap_total",
    "segment_gap_bytes_total",
    "best_prefix_max",
    "rle_prefix_max",
    "unique_opcodes",
    "top_priority",
    "top_pcx",
    "top_frontier_id",
    "suggested_action",
]


def rle_lookup(rows: list[dict[str, str]]) -> dict[tuple[str, str, str], dict[str, str]]:
    return {
        (row.get("archive", ""), row.get("pcx_name", ""), row.get("frontier_id", "")): row
        for row in rows
    }


def classify_rule(row: dict[str, str], rle_row: dict[str, str]) -> str:
    best_prefix = int_value(row, "best_raw_prefix_bytes")
    rle_prefix = int_value(rle_row, "best_prefix_bytes")
    ratio = float_value(row, "segment_gap_ratio")
    if int_value(row, "raw_exact_pixels") > 0:
        return "exact_raw_replay"
    if best_prefix >= 8:
        return "literal_fragment_probe"
    if best_prefix >= 3 or rle_prefix >= 3:
        return "short_echo_probe"
    if ratio and ratio < 0.25:
        return "compact_control_stream"
    if ratio > 4.0:
        return "expanded_control_stream"
    if 0.75 <= ratio <= 1.25:
        return "balanced_transform_stream"
    return "mixed_control_stream"


def suggested_action(rule_type: str) -> str:
    if rule_type == "exact_raw_replay":
        return "Promote as a verified raw-copy rule."
    if rule_type == "literal_fragment_probe":
        return "Inspect skipped bytes before the literal fragment and model the control prefix."
    if rule_type == "short_echo_probe":
        return "Use the echo to align the local stream and test a neighboring control-byte rule."
    if rule_type == "compact_control_stream":
        return "Prioritize compressed-run or skip/fill opcodes; segment bytes are much smaller than pixels."
    if rule_type == "expanded_control_stream":
        return "Prioritize stream-window trimming and jump/overlap analysis; segment bytes greatly exceed pixels."
    if rule_type == "balanced_transform_stream":
        return "Test palette/delta transforms around a near-1:1 stream window."
    return "Compare neighboring runs and opcode groups before adding a decoder rule."


def priority_score(row: dict[str, str], rle_row: dict[str, str], rule_type: str) -> int:
    pixel_gap = int_value(row, "pixel_gap")
    segment_gap_bytes = int_value(row, "segment_gap_bytes")
    best_prefix = int_value(row, "best_raw_prefix_bytes")
    rle_prefix = int_value(rle_row, "best_prefix_bytes")
    zero_ratio = float_value(row, "expected_zero_ratio")
    score = best_prefix * 12 + rle_prefix * 8
    if rule_type == "literal_fragment_probe":
        score += 90
    elif rule_type == "short_echo_probe":
        score += 70
    elif rule_type == "compact_control_stream":
        score += 55
    elif rule_type == "expanded_control_stream":
        score += 45
    elif rule_type == "balanced_transform_stream":
        score += 35
    if pixel_gap <= 64:
        score += 18
    elif pixel_gap <= 256:
        score += 10
    if zero_ratio >= 0.5:
        score += 8
    if segment_gap_bytes and pixel_gap and segment_gap_bytes <= pixel_gap // 8:
        score += 12
    return score


def evidence_summary(row: dict[str, str], rle_row: dict[str, str]) -> str:
    parts = [
        f"opcode0={row.get('opcode0_hex', '')}",
        f"ratio={row.get('segment_gap_ratio', '')}",
        f"raw_prefix={row.get('best_raw_prefix_bytes', '')}@skip{row.get('best_raw_skip', '')}",
    ]
    if rle_row:
        parts.append(f"rle={rle_row.get('best_variant', '')}:{rle_row.get('best_prefix_bytes', '')}")
    parts.append(f"zero={row.get('expected_zero_ratio', '')}")
    return ", ".join(parts)


def build_queue(
    opcode_probe: Path,
    rle_best: Path,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    probe_rows = read_rows(opcode_probe)
    rle_rows = read_rows(rle_best)
    rle_by_key = rle_lookup(rle_rows)
    queue_rows: list[dict[str, str]] = []

    for probe in probe_rows:
        issues: list[str] = []
        key = (probe.get("archive", ""), probe.get("pcx_name", ""), probe.get("frontier_id", ""))
        rle_row = rle_by_key.get(key, {})
        if not rle_row:
            issues.append("missing_rle_best_row")
        rule_type = classify_rule(probe, rle_row)
        score = priority_score(probe, rle_row, rule_type)
        queue_rows.append(
            {
                "rank": "0",
                "rule_type": rule_type,
                "priority_score": str(score),
                "archive": probe.get("archive", ""),
                "archive_tag": probe.get("archive_tag", ""),
                "pcx_name": probe.get("pcx_name", ""),
                "frontier_id": probe.get("frontier_id", ""),
                "frontier_type": probe.get("frontier_type", ""),
                "pixel_gap": probe.get("pixel_gap", ""),
                "segment_gap_bytes": probe.get("segment_gap_bytes", ""),
                "segment_gap_ratio": probe.get("segment_gap_ratio", ""),
                "opcode0_hex": probe.get("opcode0_hex", ""),
                "opcode1_hex": probe.get("opcode1_hex", ""),
                "best_raw_skip": probe.get("best_raw_skip", ""),
                "best_raw_prefix_bytes": probe.get("best_raw_prefix_bytes", ""),
                "rle_best_variant": rle_row.get("best_variant", ""),
                "rle_best_prefix_bytes": rle_row.get("best_prefix_bytes", ""),
                "expected_zero_ratio": probe.get("expected_zero_ratio", ""),
                "segment_gap_entropy": probe.get("segment_gap_entropy", ""),
                "expected_gap_entropy": probe.get("expected_gap_entropy", ""),
                "evidence_summary": evidence_summary(probe, rle_row),
                "next_action": suggested_action(rule_type),
                "issues": ";".join(issues),
            }
        )

    queue_rows.sort(
        key=lambda row: (
            -int_value(row, "priority_score"),
            int_value(row, "pixel_gap"),
            row.get("pcx_name", ""),
            int_value(row, "frontier_id"),
        )
    )
    for rank, row in enumerate(queue_rows, start=1):
        row["rank"] = str(rank)
    return queue_rows, build_rule_rows(queue_rows)


def build_rule_rows(queue_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    groups: dict[str, list[dict[str, str]]] = {}
    for row in queue_rows:
        groups.setdefault(row.get("rule_type", ""), []).append(row)

    rule_rows: list[dict[str, str]] = []
    for rule_type, group in groups.items():
        top = max(group, key=lambda row: int_value(row, "priority_score"))
        opcodes = {row.get("opcode0_hex", "") for row in group if row.get("opcode0_hex")}
        rule_rows.append(
            {
                "rule_type": rule_type,
                "rows": str(len(group)),
                "pixel_gap_total": str(sum(int_value(row, "pixel_gap") for row in group)),
                "segment_gap_bytes_total": str(sum(int_value(row, "segment_gap_bytes") for row in group)),
                "best_prefix_max": str(max((int_value(row, "best_raw_prefix_bytes") for row in group), default=0)),
                "rle_prefix_max": str(max((int_value(row, "rle_best_prefix_bytes") for row in group), default=0)),
                "unique_opcodes": str(len(opcodes)),
                "top_priority": top.get("priority_score", ""),
                "top_pcx": top.get("pcx_name", ""),
                "top_frontier_id": top.get("frontier_id", ""),
                "suggested_action": suggested_action(rule_type),
            }
        )
    rule_rows.sort(key=lambda row: (-int_value(row, "top_priority"), row.get("rule_type", "")))
    return rule_rows


def summary_row(queue_rows: list[dict[str, str]], rule_rows: list[dict[str, str]]) -> dict[str, str]:
    top = queue_rows[0] if queue_rows else {}
    counts = Counter(row.get("rule_type", "") for row in queue_rows)
    issue_rows = sum(1 for row in queue_rows if row.get("issues"))
    return {
        "scope": "total",
        "queue_rows": str(len(queue_rows)),
        "rule_types": str(len(rule_rows)),
        "top_priority": top.get("priority_score", ""),
        "top_rule_type": top.get("rule_type", ""),
        "top_frontier_id": top.get("frontier_id", ""),
        "top_pcx": top.get("pcx_name", ""),
        "compact_rows": str(counts.get("compact_control_stream", 0)),
        "expanded_rows": str(counts.get("expanded_control_stream", 0)),
        "literal_rows": str(counts.get("literal_fragment_probe", 0)),
        "short_echo_rows": str(counts.get("short_echo_probe", 0)),
        "balanced_rows": str(counts.get("balanced_transform_stream", 0)),
        "issue_rows": str(issue_rows),
    }


def render_queue_row(row: dict[str, str]) -> str:
    return (
        "<tr>"
        f"<td>{html.escape(row.get('rank', ''))}</td>"
        f"<td>{html.escape(row.get('rule_type', ''))}</td>"
        f"<td>{html.escape(row.get('priority_score', ''))}</td>"
        f"<td>{html.escape(row.get('pcx_name', ''))}</td>"
        f"<td>{html.escape(row.get('frontier_id', ''))}</td>"
        f"<td>{html.escape(row.get('pixel_gap', ''))}</td>"
        f"<td>{html.escape(row.get('segment_gap_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('opcode0_hex', ''))}</td>"
        f"<td>{html.escape(row.get('best_raw_prefix_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('rle_best_prefix_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('evidence_summary', ''))}</td>"
        f"<td>{html.escape(row.get('next_action', ''))}</td>"
        f"<td>{html.escape(row.get('issues', ''))}</td>"
        "</tr>"
    )


def render_rule_row(row: dict[str, str]) -> str:
    return (
        "<tr>"
        f"<td>{html.escape(row.get('rule_type', ''))}</td>"
        f"<td>{html.escape(row.get('rows', ''))}</td>"
        f"<td>{html.escape(row.get('pixel_gap_total', ''))}</td>"
        f"<td>{html.escape(row.get('segment_gap_bytes_total', ''))}</td>"
        f"<td>{html.escape(row.get('best_prefix_max', ''))}</td>"
        f"<td>{html.escape(row.get('rle_prefix_max', ''))}</td>"
        f"<td>{html.escape(row.get('unique_opcodes', ''))}</td>"
        f"<td>{html.escape(row.get('top_pcx', ''))} #{html.escape(row.get('top_frontier_id', ''))}</td>"
        f"<td>{html.escape(row.get('suggested_action', ''))}</td>"
        "</tr>"
    )


def build_html(
    summary: dict[str, str],
    queue_rows: list[dict[str, str]],
    rule_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "queue": queue_rows, "rules": rule_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("queue.csv", output_dir / "queue.csv"),
            ("by_rule.csv", output_dir / "by_rule.csv"),
        )
    )
    queue_table = "\n".join(render_queue_row(row) for row in queue_rows)
    rule_table = "\n".join(render_rule_row(row) for row in rule_rows)
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
h2 {{ margin: 0 0 10px; font-size: 16px; }}
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
    <div class="sub">Priorites de reverse-engineering pour transformer les preuves de gaps en regles de decodeur .tex.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Queue rows</div><div class="value">{html.escape(summary['queue_rows'])}</div></div>
    <div class="stat"><div class="label">Rule types</div><div class="value">{html.escape(summary['rule_types'])}</div></div>
    <div class="stat"><div class="label">Top priority</div><div class="value">{html.escape(summary['top_priority'])}</div></div>
    <div class="stat"><div class="label">Top rule</div><div class="value">{html.escape(summary['top_rule_type'])}</div></div>
    <div class="stat"><div class="label">Issues</div><div class="value ok">{html.escape(summary['issue_rows'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div></section>
  <section class="panel">
    <h2>By rule</h2>
    <table>
      <thead><tr><th>Rule</th><th>Rows</th><th>Pixel total</th><th>Segment total</th><th>Raw prefix max</th><th>RLE prefix max</th><th>Opcodes</th><th>Top</th><th>Action</th></tr></thead>
      <tbody>{rule_table}</tbody>
    </table>
  </section>
  <section class="panel">
    <h2>Queue</h2>
    <table>
      <thead><tr><th>Rank</th><th>Rule</th><th>Score</th><th>PCX</th><th>Frontier</th><th>Pixel gap</th><th>Segment bytes</th><th>Opcode0</th><th>Raw prefix</th><th>RLE prefix</th><th>Evidence</th><th>Next action</th><th>Issues</th></tr></thead>
      <tbody>{queue_table}</tbody>
    </table>
  </section>
</main>
<script>
const TEX_GAP_RULE_QUEUE = {data_json};
</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    opcode_probe: Path,
    rle_best: Path,
    *,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    queue_rows, rule_rows = build_queue(opcode_probe, rle_best)
    summary = summary_row(queue_rows, rule_rows)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "queue.csv", QUEUE_FIELDNAMES, queue_rows)
    write_csv(output_dir / "by_rule.csv", RULE_FIELDNAMES, rule_rows)
    (output_dir / "index.html").write_text(build_html(summary, queue_rows, rule_rows, output_dir, title))
    return summary, queue_rows, rule_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a prioritized .tex gap decoder-rule queue.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--opcode-probe", type=Path, default=DEFAULT_OPCODE_PROBE)
    parser.add_argument("--rle-best", type=Path, default=DEFAULT_RLE_BEST)
    parser.add_argument("--title", default="Lands of Lore II .tex Gap Rule Queue")
    args = parser.parse_args()

    summary, _queue_rows, _rule_rows = write_report(
        args.output,
        args.opcode_probe,
        args.rle_best,
        title=args.title,
    )
    print(f"Queue rows: {summary['queue_rows']}")
    print(f"Rule types: {summary['rule_types']}")
    print(f"Top rule: {summary['top_rule_type']} ({summary['top_priority']})")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
