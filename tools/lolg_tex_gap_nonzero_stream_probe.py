#!/usr/bin/env python3
"""Probe nonzero-slot streams from geometry-aware .tex gap fixtures."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter
from pathlib import Path

from lolg_tex_gap_fixture_replay import common_prefix, exact_byte_count, first_mismatch
from lolg_tex_gap_geometry_replay import stream_bytes
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_nonzero_stream_probe")
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_ZERO_RUN_FIXTURES = Path("output/tex_gap_zero_run_probe/fixtures.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "fixture_rows",
    "candidate_rows",
    "stream_modes",
    "transform_modes",
    "exact_match_rows",
    "exact_match_fixtures",
    "best_prefix_bytes",
    "best_exact_bytes",
    "best_rank",
    "best_pcx",
    "best_frontier_id",
    "best_stream_mode",
    "best_transform",
    "best_skip",
    "best_parameter",
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
    "stream_mode",
    "transform",
    "parameter",
    "skip",
    "zero_columns",
    "cdcache_width",
    "gap_start",
    "pixel_gap",
    "nonzero_slots",
    "segment_gap_bytes",
    "source_bytes",
    "produced_bytes",
    "prefix_bytes",
    "prefix_ratio",
    "exact_bytes",
    "exact_ratio",
    "full_match",
    "first_mismatch_at",
    "source_head_hex",
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
    "nonzero_slots",
    "segment_gap_bytes",
    "best_stream_mode",
    "best_transform",
    "best_parameter",
    "best_skip",
    "zero_columns",
    "cdcache_width",
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


def zero_fixture_lookup(rows: list[dict[str, str]]) -> dict[tuple[str, str, str], dict[str, str]]:
    return {
        (row.get("archive", ""), row.get("pcx_name", ""), row.get("frontier_id", "")): row
        for row in rows
    }


def expected_nonzero_stream(expected: bytes, *, gap_start: int, width: int, zero_columns: int) -> bytes:
    if width <= 0:
        return expected
    return bytes(
        value
        for offset, value in enumerate(expected)
        if (gap_start + offset) % width >= zero_columns
    )


def transform_identity(source: bytes) -> tuple[str, bytes]:
    return "", source


def transform_bit_not(source: bytes) -> tuple[str, bytes]:
    return "", bytes(value ^ 0xFF for value in source)


def transform_nibble_swap(source: bytes) -> tuple[str, bytes]:
    return "", bytes(((value & 0x0F) << 4) | (value >> 4) for value in source)


def transform_low7(source: bytes) -> tuple[str, bytes]:
    return "", bytes(value & 0x7F for value in source)


def transform_highbit_set(source: bytes) -> tuple[str, bytes]:
    return "", bytes(value | 0x80 for value in source)


def transform_xor_const(source: bytes, constant: int) -> bytes:
    return bytes(value ^ constant for value in source)


def transform_add_const(source: bytes, constant: int) -> bytes:
    return bytes((value + constant) & 0xFF for value in source)


def best_xor_constant(source: bytes, expected: bytes) -> int:
    counts: Counter[int] = Counter()
    for left, right in zip(source, expected):
        counts[left ^ right] += 1
    if not counts:
        return 0
    return max(counts.items(), key=lambda item: (item[1], -item[0]))[0]


def best_add_constant(source: bytes, expected: bytes) -> int:
    counts: Counter[int] = Counter()
    for left, right in zip(source, expected):
        counts[(right - left) & 0xFF] += 1
    if not counts:
        return 0
    return max(counts.items(), key=lambda item: (item[1], -item[0]))[0]


def transformed_sources(source: bytes, expected: bytes) -> list[tuple[str, str, bytes]]:
    rows: list[tuple[str, str, bytes]] = [
        ("identity", "", transform_identity(source)[1]),
        ("bit_not", "", transform_bit_not(source)[1]),
        ("nibble_swap", "", transform_nibble_swap(source)[1]),
        ("low7", "", transform_low7(source)[1]),
        ("highbit_set", "", transform_highbit_set(source)[1]),
    ]
    if source and expected:
        prefix_xor = source[0] ^ expected[0]
        prefix_add = (expected[0] - source[0]) & 0xFF
        exact_xor = best_xor_constant(source, expected)
        exact_add = best_add_constant(source, expected)
        rows.extend(
            [
                (f"xor_prefix", f"0x{prefix_xor:02x}", transform_xor_const(source, prefix_xor)),
                (f"add_prefix", f"0x{prefix_add:02x}", transform_add_const(source, prefix_add)),
                (f"xor_best_exact", f"0x{exact_xor:02x}", transform_xor_const(source, exact_xor)),
                (f"add_best_exact", f"0x{exact_add:02x}", transform_add_const(source, exact_add)),
            ]
        )
    return rows


def candidate_row(
    fixture: dict[str, str],
    zero_fixture: dict[str, str],
    *,
    stream_mode: str,
    transform: str,
    parameter: str,
    skip: int,
    source: bytes,
    output: bytes,
    expected_stream: bytes,
    expected_pixels: bytes,
    context_bytes: int,
    source_issues: list[str],
) -> dict[str, str]:
    prefix = common_prefix(output, expected_stream)
    exact = exact_byte_count(output, expected_stream)
    full_match = bool(expected_stream and prefix == len(expected_stream))
    notes: list[str] = []
    if len(output) < len(expected_stream):
        notes.append("stream_short")
    return {
        "rank": fixture.get("rank", ""),
        "rule_type": fixture.get("rule_type", ""),
        "archive": fixture.get("archive", ""),
        "archive_tag": fixture.get("archive_tag", ""),
        "pcx_name": fixture.get("pcx_name", ""),
        "frontier_id": fixture.get("frontier_id", ""),
        "frontier_type": fixture.get("frontier_type", ""),
        "stream_mode": stream_mode,
        "transform": transform,
        "parameter": parameter,
        "skip": str(skip),
        "zero_columns": zero_fixture.get("leading_zero_bytes", ""),
        "cdcache_width": zero_fixture.get("cdcache_width", ""),
        "gap_start": zero_fixture.get("gap_start", ""),
        "pixel_gap": str(len(expected_pixels)),
        "nonzero_slots": str(len(expected_stream)),
        "segment_gap_bytes": str(int_value(fixture, "segment_gap_bytes")),
        "source_bytes": str(len(source)),
        "produced_bytes": str(len(output)),
        "prefix_bytes": str(prefix),
        "prefix_ratio": f"{(prefix / len(expected_stream)) if expected_stream else 0.0:.6f}",
        "exact_bytes": str(exact),
        "exact_ratio": f"{(exact / len(expected_stream)) if expected_stream else 0.0:.6f}",
        "full_match": "1" if full_match else "0",
        "first_mismatch_at": first_mismatch(prefix, output, expected_stream),
        "source_head_hex": source[:context_bytes].hex(),
        "output_head_hex": output[:context_bytes].hex(),
        "expected_head_hex": expected_stream[:context_bytes].hex(),
        "notes": ";".join(notes),
        "issues": ";".join(source_issues),
    }


def sort_key(row: dict[str, str]) -> tuple[int, int, int, int, str]:
    return (
        int_value(row, "prefix_bytes"),
        int_value(row, "exact_bytes"),
        int(row.get("full_match", "0") or 0),
        -int_value(row, "skip"),
        row.get("transform", ""),
    )


def best_by_fixture(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = {}
    for row in rows:
        key = (row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", ""))
        grouped.setdefault(key, []).append(row)

    best_rows: list[dict[str, str]] = []
    for candidates in grouped.values():
        best = max(candidates, key=sort_key)
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
                "nonzero_slots": best.get("nonzero_slots", ""),
                "segment_gap_bytes": best.get("segment_gap_bytes", ""),
                "best_stream_mode": best.get("stream_mode", ""),
                "best_transform": best.get("transform", ""),
                "best_parameter": best.get("parameter", ""),
                "best_skip": best.get("skip", ""),
                "zero_columns": best.get("zero_columns", ""),
                "cdcache_width": best.get("cdcache_width", ""),
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
    fixtures: Path,
    zero_run_fixtures: Path,
    *,
    limit: int,
    max_skip: int,
    context_bytes: int,
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    fixture_rows = sorted(read_rows(fixtures), key=lambda row: int_value(row, "rank"))
    if limit > 0:
        fixture_rows = fixture_rows[:limit]
    zero_rows = zero_fixture_lookup(read_rows(zero_run_fixtures))
    tested_fixtures: list[dict[str, str]] = []
    candidate_rows: list[dict[str, str]] = []

    for fixture in fixture_rows:
        key = (fixture.get("archive", ""), fixture.get("pcx_name", ""), fixture.get("frontier_id", ""))
        zero_fixture = zero_rows.get(key, {})
        if int_value(zero_fixture, "row_prefix_zero_runs") <= 0:
            continue
        issues: list[str] = []
        if fixture.get("issues"):
            issues.append("source_fixture_has_issues")
        if zero_fixture.get("issues"):
            issues.append("source_zero_probe_has_issues")
        segment = load_bytes(fixture.get("segment_gap_path", ""), issues, "segment")
        expected_pixels = load_bytes(fixture.get("expected_gap_path", ""), issues, "expected")
        if len(segment) != int_value(fixture, "segment_gap_bytes"):
            issues.append("segment_size_mismatch")
        if len(expected_pixels) != int_value(fixture, "pixel_gap"):
            issues.append("expected_size_mismatch")
        expected_stream = expected_nonzero_stream(
            expected_pixels,
            gap_start=int_value(zero_fixture, "gap_start"),
            width=int_value(zero_fixture, "cdcache_width"),
            zero_columns=int_value(zero_fixture, "leading_zero_bytes"),
        )
        tested_fixtures.append(fixture)
        skip_limit = min(max_skip, max(0, len(segment) - 1))
        for skip in range(skip_limit + 1):
            for stream_mode in ("raw", "drop_zero_source"):
                source = stream_bytes(segment, skip, stream_mode)
                for transform, parameter, output in transformed_sources(source, expected_stream):
                    candidate_rows.append(
                        candidate_row(
                            fixture,
                            zero_fixture,
                            stream_mode=stream_mode,
                            transform=transform,
                            parameter=parameter,
                            skip=skip,
                            source=source,
                            output=output,
                            expected_stream=expected_stream,
                            expected_pixels=expected_pixels,
                            context_bytes=context_bytes,
                            source_issues=issues,
                        )
                    )

    best_rows = best_by_fixture(candidate_rows)
    return tested_fixtures, candidate_rows, best_rows


def summary_row(
    fixture_rows: list[dict[str, str]],
    candidate_rows: list[dict[str, str]],
    best_rows: list[dict[str, str]],
) -> dict[str, str]:
    best = max(candidate_rows, key=sort_key) if candidate_rows else {}
    best_exact = (
        max(
            candidate_rows,
            key=lambda row: (
                int_value(row, "exact_bytes"),
                int_value(row, "prefix_bytes"),
                int(row.get("full_match", "0") or 0),
                -int_value(row, "skip"),
                row.get("transform", ""),
            ),
        )
        if candidate_rows
        else {}
    )
    exact_match_rows = sum(1 for row in candidate_rows if row.get("full_match") == "1")
    exact_match_fixtures = sum(1 for row in best_rows if row.get("full_match") == "1")
    issue_rows = sum(1 for row in candidate_rows if row.get("issues"))
    return {
        "scope": "total",
        "fixture_rows": str(len(fixture_rows)),
        "candidate_rows": str(len(candidate_rows)),
        "stream_modes": str(len({row.get("stream_mode", "") for row in candidate_rows if row.get("stream_mode")})),
        "transform_modes": str(len({row.get("transform", "") for row in candidate_rows if row.get("transform")})),
        "exact_match_rows": str(exact_match_rows),
        "exact_match_fixtures": str(exact_match_fixtures),
        "best_prefix_bytes": str(int_value(best, "prefix_bytes")),
        "best_exact_bytes": str(int_value(best_exact, "exact_bytes")),
        "best_rank": best.get("rank", ""),
        "best_pcx": best.get("pcx_name", ""),
        "best_frontier_id": best.get("frontier_id", ""),
        "best_stream_mode": best.get("stream_mode", ""),
        "best_transform": best.get("transform", ""),
        "best_skip": best.get("skip", ""),
        "best_parameter": best.get("parameter", ""),
        "issue_rows": str(issue_rows),
    }


def render_best_row(row: dict[str, str]) -> str:
    return (
        "<tr>"
        f"<td>{html.escape(row.get('rank', ''))}</td>"
        f"<td>{html.escape(row.get('rule_type', ''))}</td>"
        f"<td>{html.escape(row.get('pcx_name', ''))}</td>"
        f"<td>{html.escape(row.get('frontier_id', ''))}</td>"
        f"<td>{html.escape(row.get('nonzero_slots', ''))}</td>"
        f"<td>{html.escape(row.get('best_stream_mode', ''))}</td>"
        f"<td>{html.escape(row.get('best_transform', ''))}</td>"
        f"<td>{html.escape(row.get('best_parameter', ''))}</td>"
        f"<td>{html.escape(row.get('best_skip', ''))}</td>"
        f"<td>{html.escape(row.get('best_prefix_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('best_exact_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('full_match', ''))}</td>"
        f"<td>{html.escape(row.get('first_mismatch_at', ''))}</td>"
        f"<td>{html.escape(row.get('notes', ''))}</td>"
        f"<td>{html.escape(row.get('issues', ''))}</td>"
        "</tr>"
    )


def render_candidate_row(row: dict[str, str]) -> str:
    return (
        "<tr>"
        f"<td>{html.escape(row.get('rank', ''))}</td>"
        f"<td>{html.escape(row.get('pcx_name', ''))}</td>"
        f"<td>{html.escape(row.get('frontier_id', ''))}</td>"
        f"<td>{html.escape(row.get('stream_mode', ''))}</td>"
        f"<td>{html.escape(row.get('transform', ''))}</td>"
        f"<td>{html.escape(row.get('parameter', ''))}</td>"
        f"<td>{html.escape(row.get('skip', ''))}</td>"
        f"<td>{html.escape(row.get('prefix_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('exact_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('full_match', ''))}</td>"
        f"<td><code>{html.escape(row.get('output_head_hex', ''))}</code></td>"
        f"<td><code>{html.escape(row.get('expected_head_hex', ''))}</code></td>"
        f"<td>{html.escape(row.get('notes', ''))}</td>"
        "</tr>"
    )


def build_html(
    summary: dict[str, str],
    candidate_rows: list[dict[str, str]],
    best_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "best": best_rows, "candidates": candidate_rows}
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
    top_candidates = sorted(candidate_rows, key=sort_key, reverse=True)[:128]
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
header {{
  border-bottom: 1px solid var(--line);
  background: #12171b;
  padding: 18px 0 14px;
}}
h1 {{ margin: 0; font-size: 21px; font-weight: 700; letter-spacing: 0; }}
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
table {{ width: 100%; border-collapse: collapse; min-width: 1280px; }}
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
    <div class="sub">Transformations simples du flux non-zero extrait des gaps geometriques .tex.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Fixtures</div><div class="value">{html.escape(summary['fixture_rows'])}</div></div>
    <div class="stat"><div class="label">Candidates</div><div class="value">{html.escape(summary['candidate_rows'])}</div></div>
    <div class="stat"><div class="label">Transforms</div><div class="value">{html.escape(summary['transform_modes'])}</div></div>
    <div class="stat"><div class="label">Best prefix</div><div class="value ok">{html.escape(summary['best_prefix_bytes'])}</div></div>
    <div class="stat"><div class="label">Best exact</div><div class="value ok">{html.escape(summary['best_exact_bytes'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div></section>
  <section class="panel">
    <h2>Best by fixture</h2>
    <table>
      <thead><tr><th>Rank</th><th>Rule</th><th>PCX</th><th>Frontier</th><th>Slots</th><th>Stream</th><th>Transform</th><th>Param</th><th>Skip</th><th>Prefix</th><th>Exact</th><th>Full</th><th>Mismatch</th><th>Notes</th><th>Issues</th></tr></thead>
      <tbody>{best_markup}</tbody>
    </table>
  </section>
  <section class="panel">
    <h2>Top candidates</h2>
    <table>
      <thead><tr><th>Rank</th><th>PCX</th><th>Frontier</th><th>Stream</th><th>Transform</th><th>Param</th><th>Skip</th><th>Prefix</th><th>Exact</th><th>Full</th><th>Output head</th><th>Expected head</th><th>Notes</th></tr></thead>
      <tbody>{candidate_markup}</tbody>
    </table>
  </section>
</main>
<script>
const TEX_GAP_NONZERO_STREAM_PROBE = {data_json};
</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    fixtures: Path,
    zero_run_fixtures: Path,
    *,
    limit: int,
    max_skip: int,
    context_bytes: int,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    fixture_rows, candidate_rows, best_rows = build_rows(
        fixtures,
        zero_run_fixtures,
        limit=limit,
        max_skip=max_skip,
        context_bytes=context_bytes,
    )
    summary = summary_row(fixture_rows, candidate_rows, best_rows)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "candidates.csv", CANDIDATE_FIELDNAMES, candidate_rows)
    write_csv(output_dir / "best_by_fixture.csv", BEST_FIELDNAMES, best_rows)
    (output_dir / "index.html").write_text(build_html(summary, candidate_rows, best_rows, output_dir, title))
    return summary, candidate_rows, best_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe nonzero-slot streams from .tex gap fixtures.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--zero-run-fixtures", type=Path, default=DEFAULT_ZERO_RUN_FIXTURES)
    parser.add_argument("--limit", type=int, default=32)
    parser.add_argument("--max-skip", type=int, default=128)
    parser.add_argument("--context-bytes", type=int, default=32)
    parser.add_argument("--title", default="Lands of Lore II .tex Gap Nonzero Stream Probe")
    args = parser.parse_args()

    summary, _candidate_rows, _best_rows = write_report(
        args.output,
        args.fixtures,
        args.zero_run_fixtures,
        limit=args.limit,
        max_skip=args.max_skip,
        context_bytes=args.context_bytes,
        title=args.title,
    )
    print(f"Fixture rows: {summary['fixture_rows']}")
    print(f"Candidate rows: {summary['candidate_rows']}")
    print(f"Transform modes: {summary['transform_modes']}")
    print(f"Exact match rows: {summary['exact_match_rows']}")
    print(f"Best prefix bytes: {summary['best_prefix_bytes']}")
    print(f"Best exact bytes: {summary['best_exact_bytes']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
