#!/usr/bin/env python3
"""Correlate .tex zero/literal segmentation ops with nearby control bytes."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter
from pathlib import Path

from lolg_tex_gap_control_grammar_probe import fixture_key
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv
from lolg_tex_gap_zero_literal_segmentation_probe import load_bytes, read_rows, segment_fixture


DEFAULT_OUTPUT = Path("output/tex_gap_segmentation_control_correlation_probe")
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_SEGMENTATION_BEST = Path("output/tex_gap_zero_literal_segmentation_probe/best_by_fixture.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "fixture_rows",
    "operation_rows",
    "literal_ops",
    "zero_ops",
    "gap_ops",
    "literal_ops_with_prev_literal",
    "literal_forward_steps",
    "literal_backward_steps",
    "literal_reuse_steps",
    "length_u8_hit_rows",
    "length_u16le_hit_rows",
    "source_delta_u8_hit_rows",
    "source_delta_u16le_hit_rows",
    "zero_len64_ops",
    "zero_len93_ops",
    "top_literal_pre2",
    "top_literal_delta",
    "issue_rows",
]

OP_FIELDNAMES = [
    "rank",
    "rule_type",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "frontier_type",
    "strategy",
    "op_index",
    "op_kind",
    "expected_start",
    "expected_end",
    "length",
    "expected_mod64",
    "source_offset",
    "source_end",
    "source_delta_from_prev_literal_end",
    "source_delta_from_prev_literal_start",
    "source_direction",
    "control_ref_offset",
    "control_window_hex",
    "pre1_hex",
    "pre2_hex",
    "pre4_hex",
    "next2_hex",
    "length_u8_hit_offsets",
    "length_u16le_hit_offsets",
    "source_delta_u8_hit_offsets",
    "source_delta_u16le_hit_offsets",
    "expected_hex",
    "source_hex",
    "issues",
]

PRE_CONTEXT_FIELDNAMES = [
    "context_type",
    "value",
    "rows",
    "literal_ops",
    "pcx_names",
    "sample_rank",
    "sample_frontier_id",
]

DELTA_FIELDNAMES = [
    "delta_type",
    "value",
    "rows",
    "forward_rows",
    "backward_rows",
    "literal_ops",
    "pcx_names",
    "sample_rank",
    "sample_frontier_id",
]


def read_best(path: Path) -> dict[tuple[str, str, str], dict[str, str]]:
    return {fixture_key(row): row for row in read_rows(path)}


def hex_slice(data: bytes, start: int, end: int) -> str:
    if start < 0 or end < start:
        return ""
    return data[start:end].hex()


def hit_offsets_u8(window: bytes, base: int, value: int) -> list[int]:
    if not 0 <= value <= 0xFF:
        return []
    return [base + index for index, byte in enumerate(window) if byte == value]


def hit_offsets_u16le(window: bytes, base: int, value: int) -> list[int]:
    if not 0 <= value <= 0xFFFF:
        return []
    needle = value.to_bytes(2, "little")
    return [base + index for index in range(0, max(0, len(window) - 1)) if window[index : index + 2] == needle]


def signed_direction(delta: int | None) -> str:
    if delta is None:
        return ""
    if delta > 0:
        return "forward"
    if delta < 0:
        return "backward"
    return "reuse"


def next_literal_sources(ops) -> dict[int, int]:
    next_offsets: dict[int, int] = {}
    next_source = -1
    for index in range(len(ops) - 1, -1, -1):
        next_offsets[index] = next_source
        op = ops[index]
        if op.kind == "literal" and op.source_offset >= 0:
            next_source = op.source_offset
    return next_offsets


def operation_rows_for_fixture(
    fixture: dict[str, str],
    best: dict[str, str],
    *,
    min_zero: int,
    min_literal: int,
    max_literal: int,
    control_window: int,
    max_hex: int,
) -> list[dict[str, str]]:
    issues: list[str] = []
    if fixture.get("issues"):
        issues.append("source_fixture_has_issues")
    segment = load_bytes(fixture.get("segment_gap_path", ""), issues, "segment")
    expected = load_bytes(fixture.get("expected_gap_path", ""), issues, "expected")
    if len(segment) != int_value(fixture, "segment_gap_bytes"):
        issues.append("segment_size_mismatch")
    if len(expected) != int_value(fixture, "pixel_gap"):
        issues.append("expected_size_mismatch")

    strategy = best.get("best_strategy", "zero_first") or "zero_first"
    ops = segment_fixture(
        expected,
        segment,
        strategy=strategy,
        min_zero=min_zero,
        min_literal=min_literal,
        max_literal=max_literal,
    )
    next_sources = next_literal_sources(ops)
    rows: list[dict[str, str]] = []
    prev_literal_start: int | None = None
    prev_literal_end: int | None = None
    for index, op in enumerate(ops):
        source_offset = op.source_offset if op.kind == "literal" else -1
        source_end = source_offset + op.length if source_offset >= 0 else -1
        delta_end = source_offset - prev_literal_end if source_offset >= 0 and prev_literal_end is not None else None
        delta_start = source_offset - prev_literal_start if source_offset >= 0 and prev_literal_start is not None else None
        control_ref = source_offset if source_offset >= 0 else next_sources.get(index, -1)
        if control_ref < 0 and prev_literal_end is not None:
            control_ref = prev_literal_end
        window_start = max(0, control_ref - control_window) if control_ref >= 0 else 0
        window = segment[window_start:control_ref] if control_ref >= 0 else b""
        length_u8_hits = hit_offsets_u8(window, window_start, op.length)
        length_u16_hits = hit_offsets_u16le(window, window_start, op.length)
        if delta_end is not None:
            delta_u8_hits = hit_offsets_u8(window, window_start, abs(delta_end))
            delta_u16_hits = hit_offsets_u16le(window, window_start, abs(delta_end))
        else:
            delta_u8_hits = []
            delta_u16_hits = []

        source = segment[source_offset:source_end] if source_offset >= 0 else b""
        rows.append(
            {
                "rank": fixture.get("rank", ""),
                "rule_type": fixture.get("rule_type", ""),
                "archive": fixture.get("archive", ""),
                "archive_tag": fixture.get("archive_tag", ""),
                "pcx_name": fixture.get("pcx_name", ""),
                "frontier_id": fixture.get("frontier_id", ""),
                "frontier_type": fixture.get("frontier_type", ""),
                "strategy": strategy,
                "op_index": str(index),
                "op_kind": op.kind,
                "expected_start": str(op.expected_start),
                "expected_end": str(op.expected_end),
                "length": str(op.length),
                "expected_mod64": str(op.expected_start % 64),
                "source_offset": "" if source_offset < 0 else str(source_offset),
                "source_end": "" if source_end < 0 else str(source_end),
                "source_delta_from_prev_literal_end": "" if delta_end is None else str(delta_end),
                "source_delta_from_prev_literal_start": "" if delta_start is None else str(delta_start),
                "source_direction": signed_direction(delta_end),
                "control_ref_offset": "" if control_ref < 0 else str(control_ref),
                "control_window_hex": window.hex(),
                "pre1_hex": hex_slice(segment, source_offset - 1, source_offset) if source_offset >= 1 else "",
                "pre2_hex": hex_slice(segment, source_offset - 2, source_offset) if source_offset >= 2 else "",
                "pre4_hex": hex_slice(segment, source_offset - 4, source_offset) if source_offset >= 4 else "",
                "next2_hex": hex_slice(segment, source_end, source_end + 2) if source_end >= 0 else "",
                "length_u8_hit_offsets": ";".join(str(value) for value in length_u8_hits),
                "length_u16le_hit_offsets": ";".join(str(value) for value in length_u16_hits),
                "source_delta_u8_hit_offsets": ";".join(str(value) for value in delta_u8_hits),
                "source_delta_u16le_hit_offsets": ";".join(str(value) for value in delta_u16_hits),
                "expected_hex": expected[op.expected_start : op.expected_end][:max_hex].hex(),
                "source_hex": source[:max_hex].hex(),
                "issues": ";".join(issues),
            }
        )
        if source_offset >= 0:
            prev_literal_start = source_offset
            prev_literal_end = source_end
    return rows


def build_rows(
    fixtures_path: Path,
    best_path: Path,
    *,
    limit: int,
    min_zero: int,
    min_literal: int,
    max_literal: int,
    control_window: int,
    max_hex: int,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    fixtures = sorted(read_rows(fixtures_path), key=lambda row: int_value(row, "rank"))
    if limit > 0:
        fixtures = fixtures[:limit]
    best_rows = read_best(best_path)
    op_rows: list[dict[str, str]] = []
    for fixture in fixtures:
        best = best_rows.get(fixture_key(fixture), {})
        op_rows.extend(
            operation_rows_for_fixture(
                fixture,
                best,
                min_zero=min_zero,
                min_literal=min_literal,
                max_literal=max_literal,
                control_window=control_window,
                max_hex=max_hex,
            )
        )
    return fixtures, op_rows


def context_rows(op_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    literal_rows = [row for row in op_rows if row.get("op_kind") == "literal"]
    for context_type in ("pre1_hex", "pre2_hex", "pre4_hex", "next2_hex"):
        counter = Counter(row.get(context_type, "") for row in literal_rows if row.get(context_type, ""))
        for value, count in counter.most_common(80):
            matching = [row for row in literal_rows if row.get(context_type) == value]
            sample = matching[0]
            rows.append(
                {
                    "context_type": context_type,
                    "value": value,
                    "rows": str(count),
                    "literal_ops": str(len(matching)),
                    "pcx_names": ";".join(sorted({row.get("pcx_name", "") for row in matching})),
                    "sample_rank": sample.get("rank", ""),
                    "sample_frontier_id": sample.get("frontier_id", ""),
                }
            )
    return rows


def delta_rows(op_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    literal_rows = [row for row in op_rows if row.get("op_kind") == "literal"]
    for delta_type in ("source_delta_from_prev_literal_end", "source_delta_from_prev_literal_start"):
        counter = Counter(row.get(delta_type, "") for row in literal_rows if row.get(delta_type, ""))
        for value, count in counter.most_common(120):
            matching = [row for row in literal_rows if row.get(delta_type) == value]
            sample = matching[0]
            rows.append(
                {
                    "delta_type": delta_type,
                    "value": value,
                    "rows": str(count),
                    "forward_rows": str(sum(1 for row in matching if row.get("source_direction") == "forward")),
                    "backward_rows": str(sum(1 for row in matching if row.get("source_direction") == "backward")),
                    "literal_ops": str(len(matching)),
                    "pcx_names": ";".join(sorted({row.get("pcx_name", "") for row in matching})),
                    "sample_rank": sample.get("rank", ""),
                    "sample_frontier_id": sample.get("frontier_id", ""),
                }
            )
    return rows


def summary_row(fixtures: list[dict[str, str]], op_rows: list[dict[str, str]]) -> dict[str, str]:
    literal_rows = [row for row in op_rows if row.get("op_kind") == "literal"]
    zero_rows = [row for row in op_rows if row.get("op_kind") == "zero"]
    gap_rows = [row for row in op_rows if row.get("op_kind") == "gap"]
    with_prev = [row for row in literal_rows if row.get("source_delta_from_prev_literal_end")]
    deltas = Counter(row.get("source_delta_from_prev_literal_end", "") for row in with_prev)
    pre2 = Counter(row.get("pre2_hex", "") for row in literal_rows if row.get("pre2_hex"))
    return {
        "scope": "total",
        "fixture_rows": str(len(fixtures)),
        "operation_rows": str(len(op_rows)),
        "literal_ops": str(len(literal_rows)),
        "zero_ops": str(len(zero_rows)),
        "gap_ops": str(len(gap_rows)),
        "literal_ops_with_prev_literal": str(len(with_prev)),
        "literal_forward_steps": str(sum(1 for row in with_prev if row.get("source_direction") == "forward")),
        "literal_backward_steps": str(sum(1 for row in with_prev if row.get("source_direction") == "backward")),
        "literal_reuse_steps": str(sum(1 for row in with_prev if row.get("source_direction") == "reuse")),
        "length_u8_hit_rows": str(sum(1 for row in op_rows if row.get("length_u8_hit_offsets"))),
        "length_u16le_hit_rows": str(sum(1 for row in op_rows if row.get("length_u16le_hit_offsets"))),
        "source_delta_u8_hit_rows": str(sum(1 for row in literal_rows if row.get("source_delta_u8_hit_offsets"))),
        "source_delta_u16le_hit_rows": str(sum(1 for row in literal_rows if row.get("source_delta_u16le_hit_offsets"))),
        "zero_len64_ops": str(sum(1 for row in zero_rows if int_value(row, "length") == 64)),
        "zero_len93_ops": str(sum(1 for row in zero_rows if int_value(row, "length") == 93)),
        "top_literal_pre2": pre2.most_common(1)[0][0] if pre2 else "",
        "top_literal_delta": deltas.most_common(1)[0][0] if deltas else "",
        "issue_rows": str(sum(1 for row in op_rows if row.get("issues"))),
    }


def render_op_row(row: dict[str, str]) -> str:
    return (
        "<tr>"
        f"<td>{html.escape(row.get('rank', ''))}</td>"
        f"<td>{html.escape(row.get('pcx_name', ''))}</td>"
        f"<td>{html.escape(row.get('frontier_id', ''))}</td>"
        f"<td>{html.escape(row.get('op_index', ''))}</td>"
        f"<td>{html.escape(row.get('op_kind', ''))}</td>"
        f"<td>{html.escape(row.get('expected_start', ''))}</td>"
        f"<td>{html.escape(row.get('length', ''))}</td>"
        f"<td>{html.escape(row.get('source_offset', ''))}</td>"
        f"<td>{html.escape(row.get('source_delta_from_prev_literal_end', ''))}</td>"
        f"<td>{html.escape(row.get('source_direction', ''))}</td>"
        f"<td><code>{html.escape(row.get('pre2_hex', ''))}</code></td>"
        f"<td>{html.escape(row.get('length_u8_hit_offsets', ''))}</td>"
        f"<td>{html.escape(row.get('source_delta_u8_hit_offsets', ''))}</td>"
        f"<td><code>{html.escape(row.get('expected_hex', ''))}</code></td>"
        "</tr>"
    )


def render_context_row(row: dict[str, str]) -> str:
    return (
        "<tr>"
        f"<td>{html.escape(row.get('context_type', ''))}</td>"
        f"<td><code>{html.escape(row.get('value', ''))}</code></td>"
        f"<td>{html.escape(row.get('rows', ''))}</td>"
        f"<td>{html.escape(row.get('pcx_names', ''))}</td>"
        f"<td>{html.escape(row.get('sample_rank', ''))}</td>"
        f"<td>{html.escape(row.get('sample_frontier_id', ''))}</td>"
        "</tr>"
    )


def render_delta_row(row: dict[str, str]) -> str:
    return (
        "<tr>"
        f"<td>{html.escape(row.get('delta_type', ''))}</td>"
        f"<td>{html.escape(row.get('value', ''))}</td>"
        f"<td>{html.escape(row.get('rows', ''))}</td>"
        f"<td>{html.escape(row.get('forward_rows', ''))}</td>"
        f"<td>{html.escape(row.get('backward_rows', ''))}</td>"
        f"<td>{html.escape(row.get('pcx_names', ''))}</td>"
        f"<td>{html.escape(row.get('sample_rank', ''))}</td>"
        f"<td>{html.escape(row.get('sample_frontier_id', ''))}</td>"
        "</tr>"
    )


def build_html(
    summary: dict[str, str],
    op_rows: list[dict[str, str]],
    context_rows_out: list[dict[str, str]],
    delta_rows_out: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "operations": op_rows,
        "contexts": context_rows_out,
        "deltas": delta_rows_out,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("operations.csv", output_dir / "operations.csv"),
            ("by_pre_context.csv", output_dir / "by_pre_context.csv"),
            ("by_source_delta.csv", output_dir / "by_source_delta.csv"),
        )
    )
    interesting = [
        row
        for row in op_rows
        if row.get("op_kind") == "literal" or row.get("length_u8_hit_offsets") or row.get("length_u16le_hit_offsets")
    ][:260]
    op_markup = "\n".join(render_op_row(row) for row in interesting)
    context_markup = "\n".join(render_context_row(row) for row in context_rows_out[:160])
    delta_markup = "\n".join(render_delta_row(row) for row in delta_rows_out[:160])
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
.wrap {{ width: min(1700px, calc(100vw - 28px)); margin: 0 auto; }}
header {{ border-bottom: 1px solid var(--line); background: #12171b; padding: 18px 0 14px; }}
h1 {{ margin: 0; font-size: 21px; font-weight: 700; letter-spacing: 0; }}
h2 {{ margin: 0 0 10px; font-size: 16px; }}
.sub {{ color: var(--muted); margin-top: 4px; }}
main {{ padding: 16px 0 28px; display: grid; gap: 16px; }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 10px; }}
.stat, .panel {{ border: 1px solid var(--line); border-radius: 8px; background: var(--panel); padding: 10px; }}
.label, .muted {{ color: var(--muted); }}
.value {{ font-size: 24px; font-weight: 750; line-height: 1.05; margin-top: 4px; }}
.ok {{ color: var(--ok); }}
.panel {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; min-width: 1350px; }}
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
    <div class="sub">Deltas source, octets precedant les copies et hits de longueurs autour du squelette zero/literal.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Operations</div><div class="value">{html.escape(summary['operation_rows'])}</div></div>
    <div class="stat"><div class="label">Literal ops</div><div class="value ok">{html.escape(summary['literal_ops'])}</div></div>
    <div class="stat"><div class="label">Forward steps</div><div class="value ok">{html.escape(summary['literal_forward_steps'])}</div></div>
    <div class="stat"><div class="label">Length u8 hits</div><div class="value">{html.escape(summary['length_u8_hit_rows'])}</div></div>
    <div class="stat"><div class="label">Zero len 64</div><div class="value">{html.escape(summary['zero_len64_ops'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div></section>
  <section class="panel">
    <h2>Operation samples</h2>
    <table>
      <thead><tr><th>Rank</th><th>PCX</th><th>Frontier</th><th>Op</th><th>Kind</th><th>Expected</th><th>Length</th><th>Source</th><th>Delta end</th><th>Direction</th><th>Pre2</th><th>Len u8 hits</th><th>Delta u8 hits</th><th>Expected</th></tr></thead>
      <tbody>{op_markup}</tbody>
    </table>
  </section>
  <section class="panel">
    <h2>Literal byte contexts</h2>
    <table>
      <thead><tr><th>Type</th><th>Value</th><th>Rows</th><th>PCX</th><th>Sample rank</th><th>Frontier</th></tr></thead>
      <tbody>{context_markup}</tbody>
    </table>
  </section>
  <section class="panel">
    <h2>Source deltas</h2>
    <table>
      <thead><tr><th>Type</th><th>Value</th><th>Rows</th><th>Forward</th><th>Backward</th><th>PCX</th><th>Sample rank</th><th>Frontier</th></tr></thead>
      <tbody>{delta_markup}</tbody>
    </table>
  </section>
</main>
<script>
const TEX_GAP_SEGMENTATION_CONTROL_CORRELATION_PROBE = {data_json};
</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    fixtures: Path,
    best: Path,
    *,
    limit: int,
    min_zero: int,
    min_literal: int,
    max_literal: int,
    control_window: int,
    max_hex: int,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    fixtures_rows, op_rows = build_rows(
        fixtures,
        best,
        limit=limit,
        min_zero=min_zero,
        min_literal=min_literal,
        max_literal=max_literal,
        control_window=control_window,
        max_hex=max_hex,
    )
    pre_rows = context_rows(op_rows)
    source_delta_rows = delta_rows(op_rows)
    summary = summary_row(fixtures_rows, op_rows)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "operations.csv", OP_FIELDNAMES, op_rows)
    write_csv(output_dir / "by_pre_context.csv", PRE_CONTEXT_FIELDNAMES, pre_rows)
    write_csv(output_dir / "by_source_delta.csv", DELTA_FIELDNAMES, source_delta_rows)
    (output_dir / "index.html").write_text(build_html(summary, op_rows, pre_rows, source_delta_rows, output_dir, title))
    return summary, op_rows, pre_rows, source_delta_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Correlate zero/literal segmentation ops with nearby bytes.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--best", type=Path, default=DEFAULT_SEGMENTATION_BEST)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--min-zero", type=int, default=2)
    parser.add_argument("--min-literal", type=int, default=4)
    parser.add_argument("--max-literal", type=int, default=256)
    parser.add_argument("--control-window", type=int, default=24)
    parser.add_argument("--max-hex", type=int, default=32)
    parser.add_argument("--title", default="Lands of Lore II .tex Gap Segmentation Control Correlation Probe")
    args = parser.parse_args()

    summary, _op_rows, _pre_rows, _delta_rows = write_report(
        args.output,
        args.fixtures,
        args.best,
        limit=args.limit,
        min_zero=args.min_zero,
        min_literal=args.min_literal,
        max_literal=args.max_literal,
        control_window=args.control_window,
        max_hex=args.max_hex,
        title=args.title,
    )
    print(f"Fixture rows: {summary['fixture_rows']}")
    print(f"Operation rows: {summary['operation_rows']}")
    print(f"Literal ops: {summary['literal_ops']}")
    print(f"Forward literal steps: {summary['literal_forward_steps']}")
    print(f"Length u8 hit rows: {summary['length_u8_hit_rows']}")
    print(f"Issue rows: {summary['issue_rows']}")


if __name__ == "__main__":
    main()
