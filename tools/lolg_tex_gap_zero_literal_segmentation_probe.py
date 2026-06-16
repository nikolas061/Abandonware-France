#!/usr/bin/env python3
"""Segment .tex gap fixtures into zero and literal-copy spans."""

from __future__ import annotations

import argparse
import csv
import html
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from lolg_tex_gap_control_grammar_probe import fixture_key
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_zero_literal_segmentation_probe")
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "fixture_rows",
    "strategy_rows",
    "operation_rows",
    "strategies",
    "total_expected_bytes",
    "best_total_covered_bytes",
    "best_total_gap_bytes",
    "best_total_literal_bytes",
    "best_total_zero_bytes",
    "best_total_ops",
    "full_cover_fixtures",
    "best_fixture_coverage_ratio",
    "best_fixture_rank",
    "best_fixture_pcx",
    "issue_rows",
]

STRATEGY_FIELDNAMES = [
    "rank",
    "rule_type",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "frontier_type",
    "strategy",
    "pixel_gap",
    "segment_gap_bytes",
    "covered_bytes",
    "coverage_ratio",
    "gap_bytes",
    "zero_bytes",
    "literal_bytes",
    "gap_ops",
    "zero_ops",
    "literal_ops",
    "total_ops",
    "first_gap_at",
    "longest_zero",
    "longest_literal",
    "best_literal_source_offset",
    "notes",
    "issues",
]

OP_FIELDNAMES = [
    "rank",
    "pcx_name",
    "frontier_id",
    "strategy",
    "op_index",
    "op_kind",
    "expected_start",
    "expected_end",
    "length",
    "source_offset",
    "source_end",
    "expected_hex",
    "source_hex",
]

BEST_FIELDNAMES = [
    "rank",
    "rule_type",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "frontier_type",
    "pixel_gap",
    "segment_gap_bytes",
    "best_strategy",
    "best_covered_bytes",
    "best_coverage_ratio",
    "best_gap_bytes",
    "best_zero_bytes",
    "best_literal_bytes",
    "best_total_ops",
    "first_gap_at",
    "longest_zero",
    "longest_literal",
    "best_literal_source_offset",
    "issues",
]


@dataclass(frozen=True)
class LiteralMatch:
    length: int
    source_offset: int


@dataclass(frozen=True)
class SegOp:
    kind: str
    expected_start: int
    expected_end: int
    source_offset: int = -1

    @property
    def length(self) -> int:
        return self.expected_end - self.expected_start


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


def zero_run_at(data: bytes, pos: int) -> int:
    if pos < 0 or pos >= len(data) or data[pos] != 0:
        return 0
    end = pos
    while end < len(data) and data[end] == 0:
        end += 1
    return end - pos


def common_prefix_limited(left: bytes, right: bytes, limit: int) -> int:
    count = 0
    max_count = min(len(left), len(right), limit)
    while count < max_count and left[count] == right[count]:
        count += 1
    return count


def segment_fixture(
    expected: bytes,
    segment: bytes,
    *,
    strategy: str,
    min_zero: int,
    min_literal: int,
    max_literal: int,
) -> list[SegOp]:
    @lru_cache(maxsize=None)
    def literal_at(pos: int) -> LiteralMatch:
        if pos < 0 or pos + min_literal > len(expected):
            return LiteralMatch(0, -1)
        needle = expected[pos : pos + min_literal]
        if not needle or not any(needle):
            return LiteralMatch(0, -1)
        best = LiteralMatch(0, -1)
        start = 0
        while True:
            found = segment.find(needle, start)
            if found < 0:
                break
            length = common_prefix_limited(segment[found:], expected[pos:], max_literal)
            if length > best.length:
                best = LiteralMatch(length, found)
            start = found + 1
        if best.length < min_literal:
            return LiteralMatch(0, -1)
        return best

    ops: list[SegOp] = []
    pos = 0
    while pos < len(expected):
        zero_len = zero_run_at(expected, pos)
        literal = literal_at(pos)
        use_literal = literal.length >= min_literal
        use_zero = zero_len >= min_zero

        if strategy == "literal_first":
            if use_literal:
                ops.append(SegOp("literal", pos, pos + literal.length, literal.source_offset))
                pos += literal.length
            elif use_zero:
                ops.append(SegOp("zero", pos, pos + zero_len))
                pos += zero_len
            else:
                ops.append(SegOp("gap", pos, pos + 1))
                pos += 1
        elif strategy == "zero_first":
            if use_zero:
                ops.append(SegOp("zero", pos, pos + zero_len))
                pos += zero_len
            elif use_literal:
                ops.append(SegOp("literal", pos, pos + literal.length, literal.source_offset))
                pos += literal.length
            else:
                ops.append(SegOp("gap", pos, pos + 1))
                pos += 1
        elif strategy == "longest_first":
            if use_zero or use_literal:
                if zero_len >= literal.length:
                    ops.append(SegOp("zero", pos, pos + zero_len))
                    pos += zero_len
                else:
                    ops.append(SegOp("literal", pos, pos + literal.length, literal.source_offset))
                    pos += literal.length
            else:
                ops.append(SegOp("gap", pos, pos + 1))
                pos += 1
        else:
            raise ValueError(f"unknown strategy: {strategy}")
    return merge_adjacent_ops(ops)


def merge_adjacent_ops(ops: list[SegOp]) -> list[SegOp]:
    merged: list[SegOp] = []
    for op in ops:
        if (
            merged
            and op.kind == merged[-1].kind
            and op.kind != "literal"
            and op.expected_start == merged[-1].expected_end
        ):
            previous = merged[-1]
            merged[-1] = SegOp(previous.kind, previous.expected_start, op.expected_end, previous.source_offset)
        else:
            merged.append(op)
    return merged


def summarize_ops(
    fixture: dict[str, str],
    expected: bytes,
    segment: bytes,
    strategy: str,
    ops: list[SegOp],
    issues: list[str],
) -> dict[str, str]:
    zero_ops = [op for op in ops if op.kind == "zero"]
    literal_ops = [op for op in ops if op.kind == "literal"]
    gap_ops = [op for op in ops if op.kind == "gap"]
    zero_bytes = sum(op.length for op in zero_ops)
    literal_bytes = sum(op.length for op in literal_ops)
    gap_bytes = sum(op.length for op in gap_ops)
    covered = zero_bytes + literal_bytes
    longest_literal = max([op.length for op in literal_ops] or [0])
    best_literal = max(literal_ops, key=lambda op: op.length, default=None)
    first_gap = min([op.expected_start for op in gap_ops] or [-1])
    return {
        "rank": fixture.get("rank", ""),
        "rule_type": fixture.get("rule_type", ""),
        "archive": fixture.get("archive", ""),
        "archive_tag": fixture.get("archive_tag", ""),
        "pcx_name": fixture.get("pcx_name", ""),
        "frontier_id": fixture.get("frontier_id", ""),
        "frontier_type": fixture.get("frontier_type", ""),
        "strategy": strategy,
        "pixel_gap": str(len(expected)),
        "segment_gap_bytes": str(len(segment)),
        "covered_bytes": str(covered),
        "coverage_ratio": f"{(covered / len(expected)) if expected else 0.0:.6f}",
        "gap_bytes": str(gap_bytes),
        "zero_bytes": str(zero_bytes),
        "literal_bytes": str(literal_bytes),
        "gap_ops": str(len(gap_ops)),
        "zero_ops": str(len(zero_ops)),
        "literal_ops": str(len(literal_ops)),
        "total_ops": str(len(ops)),
        "first_gap_at": "" if first_gap < 0 else str(first_gap),
        "longest_zero": str(max([op.length for op in zero_ops] or [0])),
        "longest_literal": str(longest_literal),
        "best_literal_source_offset": "" if best_literal is None else str(best_literal.source_offset),
        "notes": "",
        "issues": ";".join(issues),
    }


def op_rows_for_fixture(
    fixture: dict[str, str],
    expected: bytes,
    segment: bytes,
    strategy: str,
    ops: list[SegOp],
    *,
    max_op_rows: int,
    max_hex: int,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for index, op in enumerate(ops[:max_op_rows]):
        source = b""
        if op.source_offset >= 0:
            source = segment[op.source_offset : op.source_offset + op.length]
        rows.append(
            {
                "rank": fixture.get("rank", ""),
                "pcx_name": fixture.get("pcx_name", ""),
                "frontier_id": fixture.get("frontier_id", ""),
                "strategy": strategy,
                "op_index": str(index),
                "op_kind": op.kind,
                "expected_start": str(op.expected_start),
                "expected_end": str(op.expected_end),
                "length": str(op.length),
                "source_offset": "" if op.source_offset < 0 else str(op.source_offset),
                "source_end": "" if op.source_offset < 0 else str(op.source_offset + op.length),
                "expected_hex": expected[op.expected_start : op.expected_end][:max_hex].hex(),
                "source_hex": source[:max_hex].hex(),
            }
        )
    return rows


def best_by_fixture(strategy_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = {}
    for row in strategy_rows:
        grouped.setdefault(fixture_key(row), []).append(row)
    best_rows: list[dict[str, str]] = []
    for rows in grouped.values():
        best = max(
            rows,
            key=lambda row: (
                int_value(row, "covered_bytes"),
                -int_value(row, "gap_bytes"),
                -int_value(row, "total_ops"),
                int_value(row, "literal_bytes"),
            ),
        )
        best_rows.append(
            {
                "rank": best.get("rank", ""),
                "rule_type": best.get("rule_type", ""),
                "archive": best.get("archive", ""),
                "archive_tag": best.get("archive_tag", ""),
                "pcx_name": best.get("pcx_name", ""),
                "frontier_id": best.get("frontier_id", ""),
                "frontier_type": best.get("frontier_type", ""),
                "pixel_gap": best.get("pixel_gap", ""),
                "segment_gap_bytes": best.get("segment_gap_bytes", ""),
                "best_strategy": best.get("strategy", ""),
                "best_covered_bytes": best.get("covered_bytes", ""),
                "best_coverage_ratio": best.get("coverage_ratio", ""),
                "best_gap_bytes": best.get("gap_bytes", ""),
                "best_zero_bytes": best.get("zero_bytes", ""),
                "best_literal_bytes": best.get("literal_bytes", ""),
                "best_total_ops": best.get("total_ops", ""),
                "first_gap_at": best.get("first_gap_at", ""),
                "longest_zero": best.get("longest_zero", ""),
                "longest_literal": best.get("longest_literal", ""),
                "best_literal_source_offset": best.get("best_literal_source_offset", ""),
                "issues": best.get("issues", ""),
            }
        )
    return sorted(best_rows, key=lambda row: int_value(row, "rank"))


def build_rows(
    fixtures_path: Path,
    *,
    limit: int,
    min_zero: int,
    min_literal: int,
    max_literal: int,
    max_op_rows: int,
    max_hex: int,
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    fixtures = sorted(read_rows(fixtures_path), key=lambda row: int_value(row, "rank"))
    if limit > 0:
        fixtures = fixtures[:limit]
    strategy_rows: list[dict[str, str]] = []
    op_rows: list[dict[str, str]] = []
    for fixture in fixtures:
        issues: list[str] = []
        if fixture.get("issues"):
            issues.append("source_fixture_has_issues")
        segment = load_bytes(fixture.get("segment_gap_path", ""), issues, "segment")
        expected = load_bytes(fixture.get("expected_gap_path", ""), issues, "expected")
        if len(segment) != int_value(fixture, "segment_gap_bytes"):
            issues.append("segment_size_mismatch")
        if len(expected) != int_value(fixture, "pixel_gap"):
            issues.append("expected_size_mismatch")
        for strategy in ("zero_first", "literal_first", "longest_first"):
            ops = segment_fixture(
                expected,
                segment,
                strategy=strategy,
                min_zero=min_zero,
                min_literal=min_literal,
                max_literal=max_literal,
            )
            strategy_rows.append(summarize_ops(fixture, expected, segment, strategy, ops, issues))
            op_rows.extend(
                op_rows_for_fixture(
                    fixture,
                    expected,
                    segment,
                    strategy,
                    ops,
                    max_op_rows=max_op_rows,
                    max_hex=max_hex,
                )
            )
    best_rows = best_by_fixture(strategy_rows)
    return fixtures, strategy_rows, op_rows, best_rows


def summary_row(
    fixtures: list[dict[str, str]],
    strategy_rows: list[dict[str, str]],
    op_rows: list[dict[str, str]],
    best_rows: list[dict[str, str]],
) -> dict[str, str]:
    total_expected = sum(int_value(row, "pixel_gap") for row in best_rows)
    best_total_covered = sum(int_value(row, "best_covered_bytes") for row in best_rows)
    best_total_gap = sum(int_value(row, "best_gap_bytes") for row in best_rows)
    best_fixture = max(best_rows, key=lambda row: float(row.get("best_coverage_ratio", "0") or 0), default={})
    return {
        "scope": "total",
        "fixture_rows": str(len(fixtures)),
        "strategy_rows": str(len(strategy_rows)),
        "operation_rows": str(len(op_rows)),
        "strategies": str(len({row.get("strategy", "") for row in strategy_rows})),
        "total_expected_bytes": str(total_expected),
        "best_total_covered_bytes": str(best_total_covered),
        "best_total_gap_bytes": str(best_total_gap),
        "best_total_literal_bytes": str(sum(int_value(row, "best_literal_bytes") for row in best_rows)),
        "best_total_zero_bytes": str(sum(int_value(row, "best_zero_bytes") for row in best_rows)),
        "best_total_ops": str(sum(int_value(row, "best_total_ops") for row in best_rows)),
        "full_cover_fixtures": str(sum(1 for row in best_rows if int_value(row, "best_gap_bytes") == 0)),
        "best_fixture_coverage_ratio": best_fixture.get("best_coverage_ratio", "0.000000"),
        "best_fixture_rank": best_fixture.get("rank", ""),
        "best_fixture_pcx": best_fixture.get("pcx_name", ""),
        "issue_rows": str(sum(1 for row in best_rows if row.get("issues"))),
    }


def render_best_row(row: dict[str, str]) -> str:
    return (
        "<tr>"
        f"<td>{html.escape(row.get('rank', ''))}</td>"
        f"<td>{html.escape(row.get('pcx_name', ''))}</td>"
        f"<td>{html.escape(row.get('frontier_id', ''))}</td>"
        f"<td>{html.escape(row.get('best_strategy', ''))}</td>"
        f"<td>{html.escape(row.get('best_covered_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('best_gap_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('best_zero_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('best_literal_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('best_total_ops', ''))}</td>"
        f"<td>{html.escape(row.get('first_gap_at', ''))}</td>"
        f"<td>{html.escape(row.get('longest_literal', ''))}</td>"
        f"<td>{html.escape(row.get('best_literal_source_offset', ''))}</td>"
        f"<td>{html.escape(row.get('issues', ''))}</td>"
        "</tr>"
    )


def render_strategy_row(row: dict[str, str]) -> str:
    return (
        "<tr>"
        f"<td>{html.escape(row.get('rank', ''))}</td>"
        f"<td>{html.escape(row.get('pcx_name', ''))}</td>"
        f"<td>{html.escape(row.get('frontier_id', ''))}</td>"
        f"<td>{html.escape(row.get('strategy', ''))}</td>"
        f"<td>{html.escape(row.get('covered_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('coverage_ratio', ''))}</td>"
        f"<td>{html.escape(row.get('gap_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('zero_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('literal_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('total_ops', ''))}</td>"
        f"<td>{html.escape(row.get('longest_zero', ''))}</td>"
        f"<td>{html.escape(row.get('longest_literal', ''))}</td>"
        f"<td>{html.escape(row.get('issues', ''))}</td>"
        "</tr>"
    )


def render_op_row(row: dict[str, str]) -> str:
    return (
        "<tr>"
        f"<td>{html.escape(row.get('rank', ''))}</td>"
        f"<td>{html.escape(row.get('pcx_name', ''))}</td>"
        f"<td>{html.escape(row.get('frontier_id', ''))}</td>"
        f"<td>{html.escape(row.get('strategy', ''))}</td>"
        f"<td>{html.escape(row.get('op_index', ''))}</td>"
        f"<td>{html.escape(row.get('op_kind', ''))}</td>"
        f"<td>{html.escape(row.get('expected_start', ''))}</td>"
        f"<td>{html.escape(row.get('length', ''))}</td>"
        f"<td>{html.escape(row.get('source_offset', ''))}</td>"
        f"<td><code>{html.escape(row.get('expected_hex', ''))}</code></td>"
        f"<td><code>{html.escape(row.get('source_hex', ''))}</code></td>"
        "</tr>"
    )


def build_html(
    summary: dict[str, str],
    strategy_rows: list[dict[str, str]],
    op_rows: list[dict[str, str]],
    best_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "strategies": strategy_rows, "operations": op_rows, "bestByFixture": best_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("strategies.csv", output_dir / "strategies.csv"),
            ("operations.csv", output_dir / "operations.csv"),
            ("best_by_fixture.csv", output_dir / "best_by_fixture.csv"),
        )
    )
    best_markup = "\n".join(render_best_row(row) for row in best_rows)
    strategy_markup = "\n".join(
        render_strategy_row(row)
        for row in sorted(
            strategy_rows,
            key=lambda row: (int_value(row, "rank"), -int_value(row, "covered_bytes")),
        )
    )
    top_ops = [row for row in op_rows if row.get("op_kind") != "gap"][:260]
    op_markup = "\n".join(render_op_row(row) for row in top_ops)
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
table {{ width: 100%; border-collapse: collapse; min-width: 1400px; }}
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
    <div class="sub">Segmentation des gaps en spans zero, literal-copy et non couverts.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Fixtures</div><div class="value">{html.escape(summary['fixture_rows'])}</div></div>
    <div class="stat"><div class="label">Covered bytes</div><div class="value ok">{html.escape(summary['best_total_covered_bytes'])}</div></div>
    <div class="stat"><div class="label">Gap bytes</div><div class="value">{html.escape(summary['best_total_gap_bytes'])}</div></div>
    <div class="stat"><div class="label">Literal bytes</div><div class="value ok">{html.escape(summary['best_total_literal_bytes'])}</div></div>
    <div class="stat"><div class="label">Full fixtures</div><div class="value">{html.escape(summary['full_cover_fixtures'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div></section>
  <section class="panel">
    <h2>Best by fixture</h2>
    <table>
      <thead><tr><th>Rank</th><th>PCX</th><th>Frontier</th><th>Strategy</th><th>Covered</th><th>Gap</th><th>Zero</th><th>Literal</th><th>Ops</th><th>First gap</th><th>Longest literal</th><th>Literal source</th><th>Issues</th></tr></thead>
      <tbody>{best_markup}</tbody>
    </table>
  </section>
  <section class="panel">
    <h2>Strategies</h2>
    <table>
      <thead><tr><th>Rank</th><th>PCX</th><th>Frontier</th><th>Strategy</th><th>Covered</th><th>Ratio</th><th>Gap</th><th>Zero</th><th>Literal</th><th>Ops</th><th>Longest zero</th><th>Longest literal</th><th>Issues</th></tr></thead>
      <tbody>{strategy_markup}</tbody>
    </table>
  </section>
  <section class="panel">
    <h2>Operation samples</h2>
    <table>
      <thead><tr><th>Rank</th><th>PCX</th><th>Frontier</th><th>Strategy</th><th>Op</th><th>Kind</th><th>Start</th><th>Length</th><th>Source</th><th>Expected</th><th>Source bytes</th></tr></thead>
      <tbody>{op_markup}</tbody>
    </table>
  </section>
</main>
<script>
const TEX_GAP_ZERO_LITERAL_SEGMENTATION_PROBE = {data_json};
</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    fixtures: Path,
    *,
    limit: int,
    min_zero: int,
    min_literal: int,
    max_literal: int,
    max_op_rows: int,
    max_hex: int,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    fixture_rows, strategy_rows, op_rows, best_rows = build_rows(
        fixtures,
        limit=limit,
        min_zero=min_zero,
        min_literal=min_literal,
        max_literal=max_literal,
        max_op_rows=max_op_rows,
        max_hex=max_hex,
    )
    summary = summary_row(fixture_rows, strategy_rows, op_rows, best_rows)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "strategies.csv", STRATEGY_FIELDNAMES, strategy_rows)
    write_csv(output_dir / "operations.csv", OP_FIELDNAMES, op_rows)
    write_csv(output_dir / "best_by_fixture.csv", BEST_FIELDNAMES, best_rows)
    (output_dir / "index.html").write_text(build_html(summary, strategy_rows, op_rows, best_rows, output_dir, title))
    return summary, strategy_rows, op_rows, best_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Segment .tex gap fixtures into zero/literal-copy spans.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--min-zero", type=int, default=2)
    parser.add_argument("--min-literal", type=int, default=4)
    parser.add_argument("--max-literal", type=int, default=256)
    parser.add_argument("--max-op-rows", type=int, default=80)
    parser.add_argument("--max-hex", type=int, default=32)
    parser.add_argument("--title", default="Lands of Lore II .tex Gap Zero Literal Segmentation Probe")
    args = parser.parse_args()

    summary, _strategy_rows, _op_rows, _best_rows = write_report(
        args.output,
        args.fixtures,
        limit=args.limit,
        min_zero=args.min_zero,
        min_literal=args.min_literal,
        max_literal=args.max_literal,
        max_op_rows=args.max_op_rows,
        max_hex=args.max_hex,
        title=args.title,
    )
    print(f"Fixture rows: {summary['fixture_rows']}")
    print(f"Strategy rows: {summary['strategy_rows']}")
    print(f"Operation rows: {summary['operation_rows']}")
    print(f"Best total covered bytes: {summary['best_total_covered_bytes']}")
    print(f"Best total gap bytes: {summary['best_total_gap_bytes']}")
    print(f"Full cover fixtures: {summary['full_cover_fixtures']}")
    print(f"Issue rows: {summary['issue_rows']}")


if __name__ == "__main__":
    main()
