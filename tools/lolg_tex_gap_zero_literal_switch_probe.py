#!/usr/bin/env python3
"""Probe zero-prefix then literal-source switches for .tex gap fixtures."""

from __future__ import annotations

import argparse
import csv
import html
import json
from pathlib import Path

from lolg_tex_gap_control_grammar_probe import fixture_key, header_offset_lookup
from lolg_tex_gap_fixture_replay import common_prefix, exact_byte_count, first_mismatch
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_zero_literal_switch_probe")
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_HEADER_BLOCKS = Path("output/tex_gap_header_schema_probe/blocks.csv")
DEFAULT_MISMATCH_TRACE = Path("output/tex_gap_mismatch_trace_probe/mismatches.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "fixture_rows",
    "candidate_rows",
    "zero_prefix_values",
    "source_offsets",
    "stream_modes",
    "exact_match_rows",
    "exact_match_fixtures",
    "best_prefix_bytes",
    "best_prefix_rank",
    "best_prefix_pcx",
    "best_prefix_frontier_id",
    "best_exact_bytes",
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
    "zero_prefix",
    "zero_prefix_reason",
    "source_offset",
    "source_offset_reason",
    "stream_mode",
    "pixel_gap",
    "segment_gap_bytes",
    "source_bytes",
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
    "best_zero_prefix",
    "best_zero_prefix_reason",
    "best_source_offset",
    "best_source_offset_reason",
    "best_stream_mode",
    "best_prefix_bytes",
    "best_prefix_ratio",
    "best_exact_bytes",
    "best_exact_ratio",
    "full_match",
    "first_mismatch_at",
    "notes",
    "issues",
]


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


def leading_zero_run(data: bytes) -> int:
    count = 0
    while count < len(data) and data[count] == 0:
        count += 1
    return count


def drop_zero_source(data: bytes) -> bytes:
    return bytes(value for value in data if value != 0)


def switch_output(segment: bytes, expected_len: int, zero_prefix: int, source_offset: int, mode: str) -> bytes:
    if source_offset < 0 or source_offset > len(segment):
        source = b""
    else:
        source = segment[source_offset:]
    if mode == "drop_zero_source":
        source = drop_zero_source(source)
    elif mode != "raw":
        raise ValueError(f"unknown stream mode: {mode}")
    return ((b"\x00" * max(0, zero_prefix)) + source)[:expected_len]


def mismatch_lookup(rows: list[dict[str, str]]) -> dict[tuple[str, str, str], dict[str, dict[str, str]]]:
    lookup: dict[tuple[str, str, str], dict[str, dict[str, str]]] = {}
    for row in rows:
        lookup.setdefault(fixture_key(row), {})[row.get("source", "")] = row
    return lookup


def collect_offsets(
    fixture: dict[str, str],
    expected: bytes,
    segment: bytes,
    header_offsets: dict[tuple[str, str, str], dict[int, set[str]]],
    trace_rows: dict[str, dict[str, str]],
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
        if value >= 0:
            offsets.setdefault(value, set()).add(reason)
    for offset, reasons in header_offsets.get(fixture_key(fixture), {}).items():
        offsets.setdefault(offset, set()).update(reasons)

    for source, trace in trace_rows.items():
        for field in ("segment_window8_match_offset", "payload_window8_match_offset"):
            value = int_value(trace, field)
            if value >= 0 and trace.get(field, ""):
                if field.startswith("payload"):
                    value += int_value(trace, "payload_offset")
                offsets.setdefault(value, set()).add(f"{source}_{field}")

    for start in range(0, min(len(expected), 128)):
        window = expected[start : start + 8]
        if len(window) < 4 or not any(window):
            continue
        index = segment.find(window)
        if index >= 0:
            offsets.setdefault(index, set()).add(f"expected_window_at_{start}")

    return {
        offset: reasons
        for offset, reasons in sorted(offsets.items())
        if 0 <= offset <= len(segment) and offset <= max_offset
    }


def collect_zero_prefixes(
    fixture: dict[str, str],
    expected: bytes,
    trace_rows: dict[str, dict[str, str]],
) -> dict[int, set[str]]:
    values: dict[int, set[str]] = {0: {"zero"}}
    leading = leading_zero_run(expected)
    values.setdefault(leading, set()).add("expected_leading_zero_run")
    best_raw_prefix = int_value(fixture, "best_raw_prefix_bytes")
    values.setdefault(best_raw_prefix, set()).add("best_raw_prefix")
    for source, trace in trace_rows.items():
        mismatch = int_value(trace, "prefix_bytes")
        values.setdefault(mismatch, set()).add(f"{source}_first_mismatch")
        expected_run = int_value(trace, "expected_run_length")
        if trace.get("expected_byte_hex") == "00":
            values.setdefault(mismatch + expected_run, set()).add(f"{source}_expected_zero_run_end")
    return {value: reasons for value, reasons in sorted(values.items()) if 0 <= value <= len(expected)}


def candidate_row(
    fixture: dict[str, str],
    expected: bytes,
    segment: bytes,
    *,
    zero_prefix: int,
    zero_reason: str,
    source_offset: int,
    source_reason: str,
    stream_mode: str,
    max_head: int,
    issues: list[str],
) -> dict[str, str]:
    output = switch_output(segment, len(expected), zero_prefix, source_offset, stream_mode)
    prefix = common_prefix(output, expected)
    exact = exact_byte_count(output, expected)
    full = bool(expected and output == expected)
    source_bytes = max(0, len(segment) - source_offset)
    return {
        "rank": fixture.get("rank", ""),
        "rule_type": fixture.get("rule_type", ""),
        "archive": fixture.get("archive", ""),
        "archive_tag": fixture.get("archive_tag", ""),
        "pcx_name": fixture.get("pcx_name", ""),
        "frontier_id": fixture.get("frontier_id", ""),
        "frontier_type": fixture.get("frontier_type", ""),
        "zero_prefix": str(zero_prefix),
        "zero_prefix_reason": zero_reason,
        "source_offset": str(source_offset),
        "source_offset_reason": source_reason,
        "stream_mode": stream_mode,
        "pixel_gap": str(len(expected)),
        "segment_gap_bytes": str(len(segment)),
        "source_bytes": str(source_bytes),
        "produced_bytes": str(len(output)),
        "prefix_bytes": str(prefix),
        "prefix_ratio": f"{(prefix / len(expected)) if expected else 0.0:.6f}",
        "exact_bytes": str(exact),
        "exact_ratio": f"{(exact / len(expected)) if expected else 0.0:.6f}",
        "full_match": "1" if full else "0",
        "first_mismatch_at": first_mismatch(prefix, output, expected),
        "output_head_hex": output[:max_head].hex(),
        "expected_head_hex": expected[:max_head].hex(),
        "notes": "",
        "issues": ";".join(issues),
    }


def best_by_fixture(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = {}
    for row in rows:
        grouped.setdefault(fixture_key(row), []).append(row)
    best_rows: list[dict[str, str]] = []
    for candidates in grouped.values():
        best = max(
            candidates,
            key=lambda row: (
                int_value(row, "prefix_bytes"),
                int_value(row, "exact_bytes"),
                int(row.get("full_match", "0") or 0),
                -int_value(row, "source_offset"),
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
                "best_zero_prefix": best.get("zero_prefix", ""),
                "best_zero_prefix_reason": best.get("zero_prefix_reason", ""),
                "best_source_offset": best.get("source_offset", ""),
                "best_source_offset_reason": best.get("source_offset_reason", ""),
                "best_stream_mode": best.get("stream_mode", ""),
                "best_prefix_bytes": best.get("prefix_bytes", ""),
                "best_prefix_ratio": best.get("prefix_ratio", ""),
                "best_exact_bytes": best.get("exact_bytes", ""),
                "best_exact_ratio": best.get("exact_ratio", ""),
                "full_match": best.get("full_match", ""),
                "first_mismatch_at": best.get("first_mismatch_at", ""),
                "notes": best.get("notes", ""),
                "issues": best.get("issues", ""),
            }
        )
    return sorted(best_rows, key=lambda row: int_value(row, "rank"))


def build_rows(
    fixtures_path: Path,
    header_blocks_path: Path,
    mismatch_trace_path: Path,
    *,
    limit: int,
    max_offset: int,
    max_head: int,
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    fixtures = sorted(read_rows(fixtures_path), key=lambda row: int_value(row, "rank"))
    if limit > 0:
        fixtures = fixtures[:limit]
    header_offsets = header_offset_lookup(read_rows(header_blocks_path)) if header_blocks_path.exists() else {}
    traces = mismatch_lookup(read_rows(mismatch_trace_path)) if mismatch_trace_path.exists() else {}

    rows: list[dict[str, str]] = []
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
        trace_rows = traces.get(fixture_key(fixture), {})
        offsets = collect_offsets(fixture, expected, segment, header_offsets, trace_rows, max_offset=max_offset)
        zero_prefixes = collect_zero_prefixes(fixture, expected, trace_rows)
        for zero_prefix, zero_reasons in zero_prefixes.items():
            for offset, offset_reasons in offsets.items():
                for mode in ("raw", "drop_zero_source"):
                    rows.append(
                        candidate_row(
                            fixture,
                            expected,
                            segment,
                            zero_prefix=zero_prefix,
                            zero_reason=";".join(sorted(zero_reasons)),
                            source_offset=offset,
                            source_reason=";".join(sorted(offset_reasons)),
                            stream_mode=mode,
                            max_head=max_head,
                            issues=issues,
                        )
                    )

    best_rows = best_by_fixture(rows)
    return fixtures, rows, best_rows


def summary_row(
    fixture_rows: list[dict[str, str]],
    candidate_rows: list[dict[str, str]],
    best_rows: list[dict[str, str]],
) -> dict[str, str]:
    best_prefix = max(
        candidate_rows,
        key=lambda row: (
            int_value(row, "prefix_bytes"),
            int_value(row, "exact_bytes"),
            int(row.get("full_match", "0") or 0),
        ),
    ) if candidate_rows else {}
    best_exact = max(
        candidate_rows,
        key=lambda row: (
            int_value(row, "exact_bytes"),
            int_value(row, "prefix_bytes"),
            int(row.get("full_match", "0") or 0),
        ),
    ) if candidate_rows else {}
    full_rows = [row for row in candidate_rows if row.get("full_match") == "1"]
    return {
        "scope": "total",
        "fixture_rows": str(len(fixture_rows)),
        "candidate_rows": str(len(candidate_rows)),
        "zero_prefix_values": str(len({row.get("zero_prefix", "") for row in candidate_rows})),
        "source_offsets": str(len({row.get("source_offset", "") for row in candidate_rows})),
        "stream_modes": str(len({row.get("stream_mode", "") for row in candidate_rows})),
        "exact_match_rows": str(len(full_rows)),
        "exact_match_fixtures": str(len({fixture_key(row) for row in full_rows})),
        "best_prefix_bytes": str(int_value(best_prefix, "prefix_bytes")),
        "best_prefix_rank": best_prefix.get("rank", ""),
        "best_prefix_pcx": best_prefix.get("pcx_name", ""),
        "best_prefix_frontier_id": best_prefix.get("frontier_id", ""),
        "best_exact_bytes": str(int_value(best_exact, "exact_bytes")),
        "best_exact_rank": best_exact.get("rank", ""),
        "best_exact_pcx": best_exact.get("pcx_name", ""),
        "best_exact_frontier_id": best_exact.get("frontier_id", ""),
        "issue_rows": str(sum(1 for row in best_rows if row.get("issues"))),
    }


def render_best_row(row: dict[str, str]) -> str:
    return (
        "<tr>"
        f"<td>{html.escape(row.get('rank', ''))}</td>"
        f"<td>{html.escape(row.get('pcx_name', ''))}</td>"
        f"<td>{html.escape(row.get('frontier_id', ''))}</td>"
        f"<td>{html.escape(row.get('best_zero_prefix', ''))}</td>"
        f"<td>{html.escape(row.get('best_zero_prefix_reason', ''))}</td>"
        f"<td>{html.escape(row.get('best_source_offset', ''))}</td>"
        f"<td>{html.escape(row.get('best_source_offset_reason', ''))}</td>"
        f"<td>{html.escape(row.get('best_stream_mode', ''))}</td>"
        f"<td>{html.escape(row.get('best_prefix_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('best_exact_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('first_mismatch_at', ''))}</td>"
        f"<td>{html.escape(row.get('issues', ''))}</td>"
        "</tr>"
    )


def render_candidate_row(row: dict[str, str]) -> str:
    return (
        "<tr>"
        f"<td>{html.escape(row.get('rank', ''))}</td>"
        f"<td>{html.escape(row.get('pcx_name', ''))}</td>"
        f"<td>{html.escape(row.get('frontier_id', ''))}</td>"
        f"<td>{html.escape(row.get('zero_prefix', ''))}</td>"
        f"<td>{html.escape(row.get('source_offset', ''))}</td>"
        f"<td>{html.escape(row.get('stream_mode', ''))}</td>"
        f"<td>{html.escape(row.get('prefix_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('exact_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('first_mismatch_at', ''))}</td>"
        f"<td><code>{html.escape(row.get('output_head_hex', ''))}</code></td>"
        f"<td><code>{html.escape(row.get('expected_head_hex', ''))}</code></td>"
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
    best_markup = "\n".join(render_best_row(row) for row in best_rows)
    top_candidates = sorted(
        candidate_rows,
        key=lambda row: (int_value(row, "prefix_bytes"), int_value(row, "exact_bytes")),
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
table {{ width: 100%; border-collapse: collapse; min-width: 1450px; }}
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
    <div class="sub">Zero-prefix puis bascule vers un flux source literal, derive des traces de mismatch.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Fixtures</div><div class="value">{html.escape(summary['fixture_rows'])}</div></div>
    <div class="stat"><div class="label">Candidates</div><div class="value">{html.escape(summary['candidate_rows'])}</div></div>
    <div class="stat"><div class="label">Best prefix</div><div class="value ok">{html.escape(summary['best_prefix_bytes'])}</div></div>
    <div class="stat"><div class="label">Best exact</div><div class="value ok">{html.escape(summary['best_exact_bytes'])}</div></div>
    <div class="stat"><div class="label">Exact matches</div><div class="value">{html.escape(summary['exact_match_rows'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div></section>
  <section class="panel">
    <h2>Best by fixture</h2>
    <table>
      <thead><tr><th>Rank</th><th>PCX</th><th>Frontier</th><th>Zero prefix</th><th>Zero reason</th><th>Source offset</th><th>Offset reason</th><th>Mode</th><th>Prefix</th><th>Exact</th><th>Mismatch</th><th>Issues</th></tr></thead>
      <tbody>{best_markup}</tbody>
    </table>
  </section>
  <section class="panel">
    <h2>Top candidates</h2>
    <table>
      <thead><tr><th>Rank</th><th>PCX</th><th>Frontier</th><th>Zero prefix</th><th>Source offset</th><th>Mode</th><th>Prefix</th><th>Exact</th><th>Mismatch</th><th>Output head</th><th>Expected head</th><th>Issues</th></tr></thead>
      <tbody>{candidate_markup}</tbody>
    </table>
  </section>
</main>
<script>
const TEX_GAP_ZERO_LITERAL_SWITCH_PROBE = {data_json};
</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    fixtures: Path,
    header_blocks: Path,
    mismatch_trace: Path,
    *,
    limit: int,
    max_offset: int,
    max_head: int,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    fixture_rows, candidate_rows, best_rows = build_rows(
        fixtures,
        header_blocks,
        mismatch_trace,
        limit=limit,
        max_offset=max_offset,
        max_head=max_head,
    )
    summary = summary_row(fixture_rows, candidate_rows, best_rows)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "candidates.csv", CANDIDATE_FIELDNAMES, candidate_rows)
    write_csv(output_dir / "best_by_fixture.csv", BEST_FIELDNAMES, best_rows)
    (output_dir / "index.html").write_text(build_html(summary, candidate_rows, best_rows, output_dir, title))
    return summary, candidate_rows, best_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe zero-prefix/literal-source switches for .tex gap fixtures.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--header-blocks", type=Path, default=DEFAULT_HEADER_BLOCKS)
    parser.add_argument("--mismatch-trace", type=Path, default=DEFAULT_MISMATCH_TRACE)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--max-offset", type=int, default=192)
    parser.add_argument("--max-head", type=int, default=32)
    parser.add_argument("--title", default="Lands of Lore II .tex Gap Zero Literal Switch Probe")
    args = parser.parse_args()

    summary, _candidate_rows, _best_rows = write_report(
        args.output,
        args.fixtures,
        args.header_blocks,
        args.mismatch_trace,
        limit=args.limit,
        max_offset=args.max_offset,
        max_head=args.max_head,
        title=args.title,
    )
    print(f"Fixture rows: {summary['fixture_rows']}")
    print(f"Candidate rows: {summary['candidate_rows']}")
    print(f"Best prefix bytes: {summary['best_prefix_bytes']}")
    print(f"Best exact bytes: {summary['best_exact_bytes']}")
    print(f"Issue rows: {summary['issue_rows']}")


if __name__ == "__main__":
    main()
