#!/usr/bin/env python3
"""Probe small skip/copy control grammars for .tex gap fixtures."""

from __future__ import annotations

import argparse
import csv
import html
import json
from dataclasses import dataclass
from pathlib import Path

from lolg_tex_gap_fixture_replay import common_prefix, exact_byte_count, first_mismatch
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_control_grammar_probe")
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_HEADER_BLOCKS = Path("output/tex_gap_header_schema_probe/blocks.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "fixture_rows",
    "candidate_rows",
    "grammar_variants",
    "payload_offsets",
    "exact_match_rows",
    "exact_match_fixtures",
    "best_prefix_bytes",
    "best_prefix_variant",
    "best_prefix_rank",
    "best_prefix_pcx",
    "best_prefix_frontier_id",
    "best_exact_bytes",
    "best_exact_variant",
    "best_exact_rank",
    "best_exact_pcx",
    "best_exact_frontier_id",
    "issue_rows",
]

CANDIDATE_FIELDNAMES = [
    "rank",
    "rule_type",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "frontier_type",
    "variant",
    "parameter",
    "payload_offset",
    "offset_reasons",
    "pixel_gap",
    "segment_gap_bytes",
    "input_bytes",
    "consumed_bytes",
    "produced_bytes",
    "prefix_bytes",
    "prefix_ratio",
    "exact_bytes",
    "exact_ratio",
    "full_match",
    "first_mismatch_at",
    "output_head_hex",
    "expected_head_hex",
    "notes",
    "issues",
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
    "best_variant",
    "best_parameter",
    "best_payload_offset",
    "best_offset_reasons",
    "best_prefix_bytes",
    "best_prefix_ratio",
    "best_exact_bytes",
    "best_exact_ratio",
    "full_match",
    "first_mismatch_at",
    "notes",
    "issues",
]


@dataclass(frozen=True)
class GrammarOutput:
    variant: str
    parameter: str
    output: bytes
    consumed: int
    notes: str = ""


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def fixture_key(row: dict[str, str]) -> tuple[str, str, str]:
    return (row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", ""))


def load_bytes(path_text: str, issues: list[str], label: str) -> bytes:
    if not path_text:
        issues.append(f"missing_{label}_path")
        return b""
    try:
        return Path(path_text).read_bytes()
    except OSError as exc:
        issues.append(f"read_{label}_failed:{exc}")
        return b""


def header_offset_lookup(rows: list[dict[str, str]]) -> dict[tuple[str, str, str], dict[int, set[str]]]:
    offsets: dict[tuple[str, str, str], dict[int, set[str]]] = {}
    for row in rows:
        key = fixture_key(row)
        offset = int_value(row, "suggested_payload_offset")
        if offset <= 0:
            continue
        offsets.setdefault(key, {}).setdefault(offset, set()).add(
            f"header_{row.get('block_type', 'block')}_{row.get('block_index', '')}"
        )
    return offsets


def candidate_offsets(
    fixture: dict[str, str],
    header_offsets: dict[tuple[str, str, str], dict[int, set[str]]],
    segment_len: int,
    *,
    max_offset: int,
) -> dict[int, set[str]]:
    offsets: dict[int, set[str]] = {0: {"segment_start"}}
    for field, reason in (
        ("best_raw_skip", "best_raw_skip"),
        ("control_prefix_bytes", "control_prefix_bytes"),
        ("fragment_bytes", "fragment_bytes"),
    ):
        value = int_value(fixture, field)
        if value > 0:
            offsets.setdefault(value, set()).add(reason)
    for offset, reasons in header_offsets.get(fixture_key(fixture), {}).items():
        offsets.setdefault(offset, set()).update(reasons)
    return {
        offset: reasons
        for offset, reasons in sorted(offsets.items())
        if 0 <= offset < segment_len and offset <= max_offset
    }


def append_copy(output: bytearray, data: bytes, cursor: int, count: int, limit: int) -> int:
    if count <= 0 or len(output) >= limit:
        return cursor
    available = max(0, min(count, len(data) - cursor, limit - len(output)))
    if available:
        output.extend(data[cursor : cursor + available])
    return cursor + max(0, count)


def append_zero(output: bytearray, count: int, limit: int) -> None:
    if count <= 0 or len(output) >= limit:
        return
    output.extend(b"\x00" * min(count, limit - len(output)))


def decode_nibble(data: bytes, limit: int, *, mode: str, zero_bias: int, copy_bias: int) -> GrammarOutput:
    output = bytearray()
    cursor = 0
    truncated = False
    while cursor < len(data) and len(output) < limit:
        control = data[cursor]
        cursor += 1
        hi = control >> 4
        lo = control & 0x0F
        if mode == "hi_zero_lo_copy":
            zero_count, copy_count = hi + zero_bias, lo + copy_bias
            append_zero(output, zero_count, limit)
            cursor = append_copy(output, data, cursor, copy_count, limit)
        elif mode == "lo_zero_hi_copy":
            zero_count, copy_count = lo + zero_bias, hi + copy_bias
            append_zero(output, zero_count, limit)
            cursor = append_copy(output, data, cursor, copy_count, limit)
        elif mode == "hi_copy_lo_zero":
            copy_count, zero_count = hi + copy_bias, lo + zero_bias
            cursor = append_copy(output, data, cursor, copy_count, limit)
            append_zero(output, zero_count, limit)
        elif mode == "lo_copy_hi_zero":
            copy_count, zero_count = lo + copy_bias, hi + zero_bias
            cursor = append_copy(output, data, cursor, copy_count, limit)
            append_zero(output, zero_count, limit)
        else:
            raise ValueError(f"unknown nibble mode: {mode}")
        if cursor > len(data):
            truncated = True
            break
    notes = "literal_read_past_input" if truncated else ""
    return GrammarOutput(
        f"nibble_{mode}",
        f"z_bias={zero_bias};c_bias={copy_bias}",
        bytes(output[:limit]),
        min(cursor, len(data)),
        notes,
    )


def decode_pair(data: bytes, limit: int, *, mode: str, zero_bias: int, copy_bias: int) -> GrammarOutput:
    output = bytearray()
    cursor = 0
    truncated = False
    while cursor + 1 < len(data) and len(output) < limit:
        first = data[cursor]
        second = data[cursor + 1]
        cursor += 2
        if mode == "zero_copy":
            zero_count, copy_count = first + zero_bias, second + copy_bias
            append_zero(output, zero_count, limit)
            cursor = append_copy(output, data, cursor, copy_count, limit)
        elif mode == "copy_zero":
            copy_count, zero_count = first + copy_bias, second + zero_bias
            cursor = append_copy(output, data, cursor, copy_count, limit)
            append_zero(output, zero_count, limit)
        else:
            raise ValueError(f"unknown pair mode: {mode}")
        if cursor > len(data):
            truncated = True
            break
    notes = "literal_read_past_input" if truncated else ""
    return GrammarOutput(
        f"pair_{mode}",
        f"z_bias={zero_bias};c_bias={copy_bias}",
        bytes(output[:limit]),
        min(cursor, len(data)),
        notes,
    )


def decode_flag(data: bytes, limit: int, *, high_mode: str, bias: int) -> GrammarOutput:
    output = bytearray()
    cursor = 0
    truncated = False
    while cursor < len(data) and len(output) < limit:
        control = data[cursor]
        cursor += 1
        count = (control & 0x7F) + bias
        high = bool(control & 0x80)
        copy = high if high_mode == "copy" else not high
        if copy:
            cursor = append_copy(output, data, cursor, count, limit)
        else:
            append_zero(output, count, limit)
        if cursor > len(data):
            truncated = True
            break
    notes = "literal_read_past_input" if truncated else ""
    return GrammarOutput(
        f"flag_high_{high_mode}",
        f"bias={bias}",
        bytes(output[:limit]),
        min(cursor, len(data)),
        notes,
    )


def grammar_outputs(data: bytes, limit: int) -> list[GrammarOutput]:
    outputs: list[GrammarOutput] = []
    for mode in ("hi_zero_lo_copy", "lo_zero_hi_copy", "hi_copy_lo_zero", "lo_copy_hi_zero"):
        for zero_bias in (0, 1):
            for copy_bias in (0, 1):
                outputs.append(decode_nibble(data, limit, mode=mode, zero_bias=zero_bias, copy_bias=copy_bias))
    for mode in ("zero_copy", "copy_zero"):
        for zero_bias in (0, 1):
            for copy_bias in (0, 1):
                outputs.append(decode_pair(data, limit, mode=mode, zero_bias=zero_bias, copy_bias=copy_bias))
    for high_mode in ("copy", "zero"):
        for bias in (0, 1):
            outputs.append(decode_flag(data, limit, high_mode=high_mode, bias=bias))
    return outputs


def analyze_fixture(
    fixture: dict[str, str],
    offset_reasons: dict[int, set[str]],
    *,
    max_head: int,
) -> tuple[list[dict[str, str]], dict[str, str]]:
    issues: list[str] = []
    segment = load_bytes(fixture.get("segment_gap_path", ""), issues, "segment")
    expected = load_bytes(fixture.get("expected_gap_path", ""), issues, "expected")
    if len(segment) != int_value(fixture, "segment_gap_bytes"):
        issues.append("segment_size_mismatch")
    if len(expected) != int_value(fixture, "pixel_gap"):
        issues.append("expected_size_mismatch")

    rows: list[dict[str, str]] = []
    for offset, reasons in offset_reasons.items():
        data = segment[offset:] if 0 <= offset < len(segment) else b""
        for candidate in grammar_outputs(data, len(expected)):
            prefix = common_prefix(candidate.output, expected)
            exact = exact_byte_count(candidate.output, expected)
            rows.append(
                {
                    "rank": fixture.get("rank", ""),
                    "rule_type": fixture.get("rule_type", ""),
                    "archive": fixture.get("archive", ""),
                    "archive_tag": fixture.get("archive_tag", ""),
                    "pcx_name": fixture.get("pcx_name", ""),
                    "frontier_id": fixture.get("frontier_id", ""),
                    "frontier_type": fixture.get("frontier_type", ""),
                    "variant": candidate.variant,
                    "parameter": candidate.parameter,
                    "payload_offset": str(offset),
                    "offset_reasons": ";".join(sorted(reasons)),
                    "pixel_gap": fixture.get("pixel_gap", ""),
                    "segment_gap_bytes": fixture.get("segment_gap_bytes", ""),
                    "input_bytes": str(len(data)),
                    "consumed_bytes": str(candidate.consumed),
                    "produced_bytes": str(len(candidate.output)),
                    "prefix_bytes": str(prefix),
                    "prefix_ratio": f"{(prefix / len(expected)) if expected else 0.0:.6f}",
                    "exact_bytes": str(exact),
                    "exact_ratio": f"{(exact / len(expected)) if expected else 0.0:.6f}",
                    "full_match": "1" if candidate.output == expected else "0",
                    "first_mismatch_at": first_mismatch(prefix, candidate.output, expected),
                    "output_head_hex": candidate.output[:max_head].hex(),
                    "expected_head_hex": expected[:max_head].hex(),
                    "notes": candidate.notes,
                    "issues": ";".join(issues),
                }
            )
    best = max(
        rows,
        key=lambda row: (int_value(row, "exact_bytes"), int_value(row, "prefix_bytes"), int_value(row, "produced_bytes")),
    )
    best_row = {
        "rank": fixture.get("rank", ""),
        "rule_type": fixture.get("rule_type", ""),
        "archive": fixture.get("archive", ""),
        "archive_tag": fixture.get("archive_tag", ""),
        "pcx_name": fixture.get("pcx_name", ""),
        "frontier_id": fixture.get("frontier_id", ""),
        "frontier_type": fixture.get("frontier_type", ""),
        "pixel_gap": fixture.get("pixel_gap", ""),
        "segment_gap_bytes": fixture.get("segment_gap_bytes", ""),
        "best_variant": best.get("variant", ""),
        "best_parameter": best.get("parameter", ""),
        "best_payload_offset": best.get("payload_offset", ""),
        "best_offset_reasons": best.get("offset_reasons", ""),
        "best_prefix_bytes": best.get("prefix_bytes", ""),
        "best_prefix_ratio": best.get("prefix_ratio", ""),
        "best_exact_bytes": best.get("exact_bytes", ""),
        "best_exact_ratio": best.get("exact_ratio", ""),
        "full_match": best.get("full_match", ""),
        "first_mismatch_at": best.get("first_mismatch_at", ""),
        "notes": best.get("notes", ""),
        "issues": ";".join(issues),
    }
    return rows, best_row


def build_rows(
    fixtures: Path,
    header_blocks: Path,
    *,
    limit: int,
    max_offset: int,
    max_head: int,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    fixture_rows = sorted(read_rows(fixtures), key=lambda row: int_value(row, "rank"))
    if limit > 0:
        fixture_rows = fixture_rows[:limit]
    header_offsets = header_offset_lookup(read_rows(header_blocks)) if header_blocks.exists() else {}
    rows: list[dict[str, str]] = []
    best_rows: list[dict[str, str]] = []
    for fixture in fixture_rows:
        segment_len = int_value(fixture, "segment_gap_bytes")
        offsets = candidate_offsets(fixture, header_offsets, segment_len, max_offset=max_offset)
        fixture_rows_out, best = analyze_fixture(fixture, offsets, max_head=max_head)
        rows.extend(fixture_rows_out)
        best_rows.append(best)
    return rows, best_rows


def summary_row(candidate_rows: list[dict[str, str]], best_rows: list[dict[str, str]]) -> dict[str, str]:
    best_prefix = max(
        candidate_rows,
        key=lambda row: (int_value(row, "prefix_bytes"), int_value(row, "exact_bytes"), int_value(row, "produced_bytes")),
    )
    best_exact = max(
        candidate_rows,
        key=lambda row: (int_value(row, "exact_bytes"), int_value(row, "prefix_bytes"), int_value(row, "produced_bytes")),
    )
    variants = {f"{row.get('variant', '')}:{row.get('parameter', '')}" for row in candidate_rows}
    offsets = {row.get("payload_offset", "") for row in candidate_rows}
    full_rows = [row for row in candidate_rows if row.get("full_match") == "1"]
    return {
        "scope": "total",
        "fixture_rows": str(len(best_rows)),
        "candidate_rows": str(len(candidate_rows)),
        "grammar_variants": str(len(variants)),
        "payload_offsets": str(len(offsets)),
        "exact_match_rows": str(len(full_rows)),
        "exact_match_fixtures": str(len({fixture_key(row) for row in full_rows})),
        "best_prefix_bytes": best_prefix.get("prefix_bytes", "0"),
        "best_prefix_variant": best_prefix.get("variant", ""),
        "best_prefix_rank": best_prefix.get("rank", ""),
        "best_prefix_pcx": best_prefix.get("pcx_name", ""),
        "best_prefix_frontier_id": best_prefix.get("frontier_id", ""),
        "best_exact_bytes": best_exact.get("exact_bytes", "0"),
        "best_exact_variant": best_exact.get("variant", ""),
        "best_exact_rank": best_exact.get("rank", ""),
        "best_exact_pcx": best_exact.get("pcx_name", ""),
        "best_exact_frontier_id": best_exact.get("frontier_id", ""),
        "issue_rows": str(sum(1 for row in best_rows if row.get("issues"))),
    }


def render_candidate_row(row: dict[str, str]) -> str:
    return (
        "<tr>"
        f"<td>{html.escape(row.get('rank', ''))}</td>"
        f"<td>{html.escape(row.get('pcx_name', ''))}</td>"
        f"<td>{html.escape(row.get('frontier_id', ''))}</td>"
        f"<td>{html.escape(row.get('variant', ''))}</td>"
        f"<td>{html.escape(row.get('parameter', ''))}</td>"
        f"<td>{html.escape(row.get('payload_offset', ''))}</td>"
        f"<td>{html.escape(row.get('offset_reasons', ''))}</td>"
        f"<td>{html.escape(row.get('produced_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('consumed_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('prefix_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('exact_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('first_mismatch_at', ''))}</td>"
        f"<td>{html.escape(row.get('notes', ''))}</td>"
        f"<td>{html.escape(row.get('issues', ''))}</td>"
        "</tr>"
    )


def render_best_row(row: dict[str, str]) -> str:
    return (
        "<tr>"
        f"<td>{html.escape(row.get('rank', ''))}</td>"
        f"<td>{html.escape(row.get('pcx_name', ''))}</td>"
        f"<td>{html.escape(row.get('frontier_id', ''))}</td>"
        f"<td>{html.escape(row.get('best_variant', ''))}</td>"
        f"<td>{html.escape(row.get('best_parameter', ''))}</td>"
        f"<td>{html.escape(row.get('best_payload_offset', ''))}</td>"
        f"<td>{html.escape(row.get('best_prefix_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('best_exact_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('first_mismatch_at', ''))}</td>"
        f"<td>{html.escape(row.get('notes', ''))}</td>"
        f"<td>{html.escape(row.get('issues', ''))}</td>"
        "</tr>"
    )


def build_html(
    summary: dict[str, str],
    candidate_rows: list[dict[str, str]],
    best_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "candidates": candidate_rows, "bestByFixture": best_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("candidates.csv", output_dir / "candidates.csv"),
            ("best_by_fixture.csv", output_dir / "best_by_fixture.csv"),
        )
    )
    best_markup = "\n".join(
        render_best_row(row)
        for row in sorted(best_rows, key=lambda row: int_value(row, "best_exact_bytes"), reverse=True)
    )
    top_candidates = sorted(
        candidate_rows,
        key=lambda row: (int_value(row, "exact_bytes"), int_value(row, "prefix_bytes"), int_value(row, "produced_bytes")),
        reverse=True,
    )[:220]
    candidate_markup = "\n".join(render_candidate_row(row) for row in top_candidates)
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
header {{ border-bottom: 1px solid var(--line); background: #12171b; padding: 18px 0 14px; }}
h1 {{ margin: 0; font-size: 21px; font-weight: 700; letter-spacing: 0; }}
h2 {{ margin: 0 0 10px; font-size: 16px; }}
.sub {{ color: var(--muted); margin-top: 4px; }}
main {{ padding: 16px 0 28px; display: grid; gap: 16px; }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; }}
.stat, .panel {{ border: 1px solid var(--line); border-radius: 8px; background: var(--panel); padding: 10px; }}
.label, .muted {{ color: var(--muted); }}
.value {{ font-size: 24px; font-weight: 750; line-height: 1.05; margin-top: 4px; }}
.ok {{ color: var(--ok); }}
.panel {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; min-width: 1380px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Mini-grammaires skip/copy/fill sur offsets de payload candidats.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Fixtures</div><div class="value">{html.escape(summary['fixture_rows'])}</div></div>
    <div class="stat"><div class="label">Candidates</div><div class="value">{html.escape(summary['candidate_rows'])}</div></div>
    <div class="stat"><div class="label">Variants</div><div class="value">{html.escape(summary['grammar_variants'])}</div></div>
    <div class="stat"><div class="label">Best prefix</div><div class="value ok">{html.escape(summary['best_prefix_bytes'])}</div></div>
    <div class="stat"><div class="label">Best exact</div><div class="value ok">{html.escape(summary['best_exact_bytes'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div></section>
  <section class="panel">
    <h2>Best by fixture</h2>
    <table>
      <thead><tr><th>Rank</th><th>PCX</th><th>Frontier</th><th>Variant</th><th>Parameter</th><th>Offset</th><th>Prefix</th><th>Exact</th><th>Mismatch</th><th>Notes</th><th>Issues</th></tr></thead>
      <tbody>{best_markup}</tbody>
    </table>
  </section>
  <section class="panel">
    <h2>Top candidates</h2>
    <table>
      <thead><tr><th>Rank</th><th>PCX</th><th>Frontier</th><th>Variant</th><th>Parameter</th><th>Offset</th><th>Reasons</th><th>Produced</th><th>Consumed</th><th>Prefix</th><th>Exact</th><th>Mismatch</th><th>Notes</th><th>Issues</th></tr></thead>
      <tbody>{candidate_markup}</tbody>
    </table>
  </section>
</main>
<script>
const TEX_GAP_CONTROL_GRAMMAR_PROBE = {data_json};
</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    fixtures: Path,
    header_blocks: Path,
    *,
    limit: int,
    max_offset: int,
    max_head: int,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    candidate_rows, best_rows = build_rows(
        fixtures,
        header_blocks,
        limit=limit,
        max_offset=max_offset,
        max_head=max_head,
    )
    summary = summary_row(candidate_rows, best_rows)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "candidates.csv", CANDIDATE_FIELDNAMES, candidate_rows)
    write_csv(output_dir / "best_by_fixture.csv", BEST_FIELDNAMES, best_rows)
    (output_dir / "index.html").write_text(build_html(summary, candidate_rows, best_rows, output_dir, title))
    return summary, candidate_rows, best_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe skip/copy control grammars for .tex gap fixtures.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--header-blocks", type=Path, default=DEFAULT_HEADER_BLOCKS)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--max-offset", type=int, default=160)
    parser.add_argument("--max-head", type=int, default=32)
    parser.add_argument("--title", default="Lands of Lore II .tex Gap Control Grammar Probe")
    args = parser.parse_args()

    summary, _candidate_rows, _best_rows = write_report(
        args.output,
        args.fixtures,
        args.header_blocks,
        limit=args.limit,
        max_offset=args.max_offset,
        max_head=args.max_head,
        title=args.title,
    )
    print(f"Fixture rows: {summary['fixture_rows']}")
    print(f"Candidate rows: {summary['candidate_rows']}")
    print(f"Grammar variants: {summary['grammar_variants']}")
    print(f"Best prefix bytes: {summary['best_prefix_bytes']}")
    print(f"Best exact bytes: {summary['best_exact_bytes']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
