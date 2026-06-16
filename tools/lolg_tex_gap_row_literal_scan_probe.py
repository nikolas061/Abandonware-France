#!/usr/bin/env python3
"""Scan whole candidate streams for literal per-row .tex gap matches."""

from __future__ import annotations

import argparse
import csv
import html
import json
from pathlib import Path

from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv
from lolg_tex_gap_row_delta_probe import build_row_geometry
from lolg_tex_gap_row_stride_probe import source_bytes


DEFAULT_OUTPUT = Path("output/tex_gap_row_literal_scan_probe")
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_ZERO_RUN_FIXTURES = Path("output/tex_gap_zero_run_probe/fixtures.csv")
DEFAULT_CANDIDATES = Path("output/tex_gap_row_delta_probe/candidates.csv")
DEFAULT_ROW_DELTAS = Path("output/tex_gap_row_delta_probe/row_deltas.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "selected_candidates",
    "literal_scan_rows",
    "fixtures",
    "full_nonzero_rows",
    "rows_with_literal_gain",
    "unique_best_source_starts",
    "best_literal_nonzero_slots",
    "best_literal_nonzero_ratio",
    "best_gain_over_delta",
    "best_rank",
    "best_pcx",
    "best_frontier_id",
    "best_payload_offset",
    "best_source_mode",
    "best_row_stride",
    "best_row_prefix_skip",
    "issue_rows",
]

CANDIDATE_FIELDNAMES = [
    "selection_id",
    "rank",
    "rule_type",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "frontier_type",
    "payload_offset",
    "source_mode",
    "row_stride",
    "row_prefix_skip",
    "row_scan_rows",
    "nonzero_slots",
    "delta_nonzero_exact_slots",
    "literal_nonzero_exact_slots",
    "literal_nonzero_exact_ratio",
    "gain_over_delta",
    "full_nonzero_rows",
    "rows_with_literal_gain",
    "best_row_nonzero_exact",
    "worst_row_nonzero_exact",
    "unique_best_source_starts",
    "issue_notes",
    "issues",
]

ROW_FIELDNAMES = [
    "selection_id",
    "rank",
    "pcx_name",
    "frontier_id",
    "row_index",
    "absolute_row",
    "payload_offset",
    "source_mode",
    "source_len",
    "nonzero_slots",
    "delta_best_source_start",
    "delta_nonzero_exact_slots",
    "literal_best_source_start",
    "literal_nonzero_exact_slots",
    "gain_over_delta",
    "full_nonzero_row",
    "source_distance_from_delta",
    "expected_nonzero_head_hex",
    "literal_nonzero_head_hex",
    "issues",
]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def fixture_key(row: dict[str, str]) -> tuple[str, str, str]:
    return (row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", ""))


def zero_key(row: dict[str, str]) -> tuple[str, str, str]:
    return (row.get("archive", ""), row.get("pcx_name", ""), row.get("frontier_id", ""))


def load_bytes(path_text: str, issues: list[str], label: str) -> bytes:
    if not path_text:
        issues.append(f"missing_{label}_path")
        return b""
    try:
        return Path(path_text).read_bytes()
    except OSError as exc:
        issues.append(f"read_{label}_failed:{exc}")
        return b""


def row_delta_lookup(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    return {
        (row.get("selection_id", ""), row.get("row_index", "")): row
        for row in rows
    }


def expected_values_for_row(expected: bytes, nonzero: list[tuple[int, int, int]]) -> bytes:
    return bytes(expected[output_offset] for output_offset, _slot_index, _x in nonzero)


def literal_head(source: bytes, start: int, count: int) -> bytes:
    if start < 0 or start >= len(source):
        return b""
    return source[start : min(len(source), start + count)]


def best_literal_scan(source: bytes, expected: bytes, anchor: int) -> tuple[int, int]:
    if not expected or len(source) < len(expected):
        return 0, 0
    best_start = 0
    best_exact = -1
    best_distance = len(source) + abs(anchor)
    limit = len(source) - len(expected)
    expected_len = len(expected)
    for start in range(limit + 1):
        exact = 0
        window = source[start : start + expected_len]
        for value, wanted in zip(window, expected):
            if value == wanted:
                exact += 1
        distance = abs(start - anchor)
        if exact > best_exact or (exact == best_exact and distance < best_distance):
            best_exact = exact
            best_start = start
            best_distance = distance
    return best_start, max(0, best_exact)


def analyze_candidate(
    candidate: dict[str, str],
    fixture: dict[str, str],
    zero_fixture: dict[str, str],
    row_deltas: dict[tuple[str, str], dict[str, str]],
    *,
    context_bytes: int,
) -> tuple[dict[str, str], list[dict[str, str]]]:
    issues: list[str] = []
    notes: list[str] = []
    segment = load_bytes(fixture.get("segment_gap_path", ""), issues, "segment")
    expected = load_bytes(fixture.get("expected_gap_path", ""), issues, "expected")
    width = int_value(zero_fixture, "cdcache_width")
    zero_columns = int_value(zero_fixture, "leading_zero_bytes")
    rows = build_row_geometry(
        len(expected),
        gap_start=int_value(zero_fixture, "gap_start"),
        width=width,
        zero_columns=zero_columns,
    )
    try:
        source = source_bytes(segment, int_value(candidate, "payload_offset"), candidate.get("source_mode", "raw"))
    except ValueError as exc:
        source = b""
        issues.append(str(exc))

    selection_id = candidate.get("selection_id", "")
    row_rows: list[dict[str, str]] = []
    nonzero_total = 0
    delta_total = 0
    literal_total = 0
    full_nonzero_rows = 0
    rows_with_gain = 0
    best_row_exact = 0
    worst_row_exact: int | None = None
    best_starts: set[int] = set()

    for row_index, row in enumerate(rows):
        nonzero = row["nonzero"]  # type: ignore[assignment]
        expected_values = expected_values_for_row(expected, nonzero)
        delta_row = row_deltas.get((selection_id, str(row_index)), {})
        if not delta_row:
            notes.append("missing_row_delta")
        delta_start = int_value(delta_row, "best_source_start")
        delta_exact = int_value(delta_row, "adjusted_nonzero_exact_slots")
        literal_start, literal_exact = best_literal_scan(source, expected_values, delta_start)
        nonzero_count = len(nonzero)
        gain = literal_exact - delta_exact
        if gain > 0:
            rows_with_gain += 1
        if nonzero_count and literal_exact == nonzero_count:
            full_nonzero_rows += 1
        if expected_values:
            best_starts.add(literal_start)
        nonzero_total += nonzero_count
        delta_total += delta_exact
        literal_total += literal_exact
        best_row_exact = max(best_row_exact, literal_exact)
        worst_row_exact = literal_exact if worst_row_exact is None else min(worst_row_exact, literal_exact)
        row_rows.append(
            {
                "selection_id": selection_id,
                "rank": candidate.get("rank", ""),
                "pcx_name": candidate.get("pcx_name", ""),
                "frontier_id": candidate.get("frontier_id", ""),
                "row_index": str(row_index),
                "absolute_row": str(row["absolute_row"]),
                "payload_offset": candidate.get("payload_offset", ""),
                "source_mode": candidate.get("source_mode", ""),
                "source_len": str(len(source)),
                "nonzero_slots": str(nonzero_count),
                "delta_best_source_start": str(delta_start),
                "delta_nonzero_exact_slots": str(delta_exact),
                "literal_best_source_start": str(literal_start),
                "literal_nonzero_exact_slots": str(literal_exact),
                "gain_over_delta": str(gain),
                "full_nonzero_row": "1" if nonzero_count and literal_exact == nonzero_count else "0",
                "source_distance_from_delta": str(abs(literal_start - delta_start)),
                "expected_nonzero_head_hex": expected_values[:context_bytes].hex(),
                "literal_nonzero_head_hex": literal_head(source, literal_start, context_bytes).hex(),
                "issues": "",
            }
        )

    if literal_total <= delta_total:
        notes.append("no_literal_scan_gain")
    candidate_row = {
        "selection_id": selection_id,
        "rank": candidate.get("rank", ""),
        "rule_type": candidate.get("rule_type", ""),
        "archive": candidate.get("archive", ""),
        "archive_tag": candidate.get("archive_tag", ""),
        "pcx_name": candidate.get("pcx_name", ""),
        "frontier_id": candidate.get("frontier_id", ""),
        "frontier_type": candidate.get("frontier_type", ""),
        "payload_offset": candidate.get("payload_offset", ""),
        "source_mode": candidate.get("source_mode", ""),
        "row_stride": candidate.get("row_stride", ""),
        "row_prefix_skip": candidate.get("row_prefix_skip", ""),
        "row_scan_rows": str(len(row_rows)),
        "nonzero_slots": str(nonzero_total),
        "delta_nonzero_exact_slots": str(delta_total),
        "literal_nonzero_exact_slots": str(literal_total),
        "literal_nonzero_exact_ratio": f"{(literal_total / nonzero_total) if nonzero_total else 0.0:.6f}",
        "gain_over_delta": str(literal_total - delta_total),
        "full_nonzero_rows": str(full_nonzero_rows),
        "rows_with_literal_gain": str(rows_with_gain),
        "best_row_nonzero_exact": str(best_row_exact),
        "worst_row_nonzero_exact": str(worst_row_exact or 0),
        "unique_best_source_starts": str(len(best_starts)),
        "issue_notes": ";".join(sorted(set(notes))),
        "issues": ";".join(issues),
    }
    return candidate_row, row_rows


def build_rows(
    fixtures: Path,
    zero_run_fixtures: Path,
    candidates: Path,
    row_deltas: Path,
    *,
    context_bytes: int,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    fixtures_by_key = {fixture_key(row): row for row in read_rows(fixtures)}
    zero_by_key = {zero_key(row): row for row in read_rows(zero_run_fixtures)}
    deltas = row_delta_lookup(read_rows(row_deltas))
    candidate_rows: list[dict[str, str]] = []
    row_rows: list[dict[str, str]] = []
    for candidate in read_rows(candidates):
        key = fixture_key(candidate)
        zero_fixture = zero_by_key.get(
            (candidate.get("archive", ""), candidate.get("pcx_name", ""), candidate.get("frontier_id", "")),
            {},
        )
        analyzed, rows = analyze_candidate(
            candidate,
            fixtures_by_key.get(key, {}),
            zero_fixture,
            deltas,
            context_bytes=context_bytes,
        )
        candidate_rows.append(analyzed)
        row_rows.extend(rows)
    return candidate_rows, row_rows


def summary_row(candidate_rows: list[dict[str, str]], row_rows: list[dict[str, str]]) -> dict[str, str]:
    best = (
        max(
            candidate_rows,
            key=lambda row: (
                int_value(row, "literal_nonzero_exact_slots"),
                int_value(row, "gain_over_delta"),
                int_value(row, "delta_nonzero_exact_slots"),
            ),
        )
        if candidate_rows
        else {}
    )
    literal = int_value(best, "literal_nonzero_exact_slots")
    nonzero_slots = int_value(best, "nonzero_slots")
    return {
        "scope": "total",
        "selected_candidates": str(len(candidate_rows)),
        "literal_scan_rows": str(len(row_rows)),
        "fixtures": str(len({fixture_key(row) for row in candidate_rows})),
        "full_nonzero_rows": str(sum(int_value(row, "full_nonzero_rows") for row in candidate_rows)),
        "rows_with_literal_gain": str(sum(int_value(row, "rows_with_literal_gain") for row in candidate_rows)),
        "unique_best_source_starts": str(
            len({row.get("literal_best_source_start", "") for row in row_rows if row.get("literal_best_source_start", "")})
        ),
        "best_literal_nonzero_slots": str(literal),
        "best_literal_nonzero_ratio": f"{(literal / nonzero_slots) if nonzero_slots else 0.0:.6f}",
        "best_gain_over_delta": str(max([int_value(row, "gain_over_delta") for row in candidate_rows] or [0])),
        "best_rank": best.get("rank", ""),
        "best_pcx": best.get("pcx_name", ""),
        "best_frontier_id": best.get("frontier_id", ""),
        "best_payload_offset": best.get("payload_offset", ""),
        "best_source_mode": best.get("source_mode", ""),
        "best_row_stride": best.get("row_stride", ""),
        "best_row_prefix_skip": best.get("row_prefix_skip", ""),
        "issue_rows": str(sum(1 for row in candidate_rows if row.get("issues"))),
    }


def render_candidate_row(row: dict[str, str]) -> str:
    return (
        "<tr>"
        f"<td>{html.escape(row.get('selection_id', ''))}</td>"
        f"<td>{html.escape(row.get('pcx_name', ''))}</td>"
        f"<td>{html.escape(row.get('frontier_id', ''))}</td>"
        f"<td>{html.escape(row.get('source_mode', ''))}</td>"
        f"<td>{html.escape(row.get('delta_nonzero_exact_slots', ''))}</td>"
        f"<td>{html.escape(row.get('literal_nonzero_exact_slots', ''))}</td>"
        f"<td>{html.escape(row.get('gain_over_delta', ''))}</td>"
        f"<td>{html.escape(row.get('full_nonzero_rows', ''))}</td>"
        f"<td>{html.escape(row.get('rows_with_literal_gain', ''))}</td>"
        f"<td>{html.escape(row.get('unique_best_source_starts', ''))}</td>"
        f"<td>{html.escape(row.get('issue_notes', ''))}</td>"
        f"<td>{html.escape(row.get('issues', ''))}</td>"
        "</tr>"
    )


def render_scan_row(row: dict[str, str]) -> str:
    return (
        "<tr>"
        f"<td>{html.escape(row.get('selection_id', ''))}</td>"
        f"<td>{html.escape(row.get('row_index', ''))}</td>"
        f"<td>{html.escape(row.get('delta_best_source_start', ''))}</td>"
        f"<td>{html.escape(row.get('literal_best_source_start', ''))}</td>"
        f"<td>{html.escape(row.get('nonzero_slots', ''))}</td>"
        f"<td>{html.escape(row.get('delta_nonzero_exact_slots', ''))}</td>"
        f"<td>{html.escape(row.get('literal_nonzero_exact_slots', ''))}</td>"
        f"<td>{html.escape(row.get('gain_over_delta', ''))}</td>"
        f"<td>{html.escape(row.get('source_distance_from_delta', ''))}</td>"
        f"<td><code>{html.escape(row.get('expected_nonzero_head_hex', ''))}</code></td>"
        f"<td><code>{html.escape(row.get('literal_nonzero_head_hex', ''))}</code></td>"
        "</tr>"
    )


def build_html(
    summary: dict[str, str],
    candidate_rows: list[dict[str, str]],
    row_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "candidates": candidate_rows, "rowScans": row_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("candidates.csv", output_dir / "candidates.csv"),
            ("row_scans.csv", output_dir / "row_scans.csv"),
        )
    )
    candidate_markup = "\n".join(
        render_candidate_row(row)
        for row in sorted(candidate_rows, key=lambda row: int_value(row, "literal_nonzero_exact_slots"), reverse=True)
    )
    top_rows = sorted(
        row_rows,
        key=lambda row: (int_value(row, "gain_over_delta"), int_value(row, "literal_nonzero_exact_slots")),
        reverse=True,
    )[:180]
    row_markup = "\n".join(render_scan_row(row) for row in top_rows)
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
table {{ width: 100%; border-collapse: collapse; min-width: 1320px; }}
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
    <div class="sub">Scan literal de chaque ligne nonzero dans tout le flux candidat.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Candidates</div><div class="value">{html.escape(summary['selected_candidates'])}</div></div>
    <div class="stat"><div class="label">Row scans</div><div class="value">{html.escape(summary['literal_scan_rows'])}</div></div>
    <div class="stat"><div class="label">Best literal</div><div class="value ok">{html.escape(summary['best_literal_nonzero_slots'])}</div></div>
    <div class="stat"><div class="label">Gain over delta</div><div class="value ok">{html.escape(summary['best_gain_over_delta'])}</div></div>
    <div class="stat"><div class="label">Full rows</div><div class="value">{html.escape(summary['full_nonzero_rows'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div></section>
  <section class="panel">
    <h2>Candidates</h2>
    <table>
      <thead><tr><th>ID</th><th>PCX</th><th>Frontier</th><th>Mode</th><th>Delta</th><th>Literal</th><th>Gain</th><th>Full rows</th><th>Gain rows</th><th>Starts</th><th>Notes</th><th>Issues</th></tr></thead>
      <tbody>{candidate_markup}</tbody>
    </table>
  </section>
  <section class="panel">
    <h2>Top row literal scans</h2>
    <table>
      <thead><tr><th>ID</th><th>Row</th><th>Delta start</th><th>Literal start</th><th>Slots</th><th>Delta exact</th><th>Literal exact</th><th>Gain</th><th>Distance</th><th>Expected</th><th>Literal</th></tr></thead>
      <tbody>{row_markup}</tbody>
    </table>
  </section>
</main>
<script>
const TEX_GAP_ROW_LITERAL_SCAN_PROBE = {data_json};
</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    fixtures: Path,
    zero_run_fixtures: Path,
    candidates: Path,
    row_deltas: Path,
    *,
    context_bytes: int,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    candidate_rows, row_rows = build_rows(
        fixtures,
        zero_run_fixtures,
        candidates,
        row_deltas,
        context_bytes=context_bytes,
    )
    summary = summary_row(candidate_rows, row_rows)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "candidates.csv", CANDIDATE_FIELDNAMES, candidate_rows)
    write_csv(output_dir / "row_scans.csv", ROW_FIELDNAMES, row_rows)
    (output_dir / "index.html").write_text(build_html(summary, candidate_rows, row_rows, output_dir, title))
    return summary, candidate_rows, row_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan candidate streams for literal per-row .tex gap matches.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--zero-run-fixtures", type=Path, default=DEFAULT_ZERO_RUN_FIXTURES)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--row-deltas", type=Path, default=DEFAULT_ROW_DELTAS)
    parser.add_argument("--context-bytes", type=int, default=24)
    parser.add_argument("--title", default="Lands of Lore II .tex Gap Row Literal Scan Probe")
    args = parser.parse_args()

    summary, _candidate_rows, _row_rows = write_report(
        args.output,
        args.fixtures,
        args.zero_run_fixtures,
        args.candidates,
        args.row_deltas,
        context_bytes=args.context_bytes,
        title=args.title,
    )
    print(f"Selected candidates: {summary['selected_candidates']}")
    print(f"Literal scan rows: {summary['literal_scan_rows']}")
    print(f"Best literal nonzero slots: {summary['best_literal_nonzero_slots']}")
    print(f"Best gain over delta: {summary['best_gain_over_delta']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
