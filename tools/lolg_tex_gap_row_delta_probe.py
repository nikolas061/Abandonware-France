#!/usr/bin/env python3
"""Probe per-row source deltas for top .tex row-stride candidates."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import defaultdict
from pathlib import Path

from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv
from lolg_tex_gap_row_stride_probe import source_bytes


DEFAULT_OUTPUT = Path("output/tex_gap_row_delta_probe")
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_ZERO_RUN_FIXTURES = Path("output/tex_gap_zero_run_probe/fixtures.csv")
DEFAULT_CANDIDATES = Path("output/tex_gap_row_stride_mismatch_probe/candidates.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "selected_candidates",
    "row_delta_rows",
    "fixtures",
    "max_abs_delta",
    "unique_delta_values",
    "full_nonzero_rows",
    "best_adjusted_nonzero_slots",
    "best_adjusted_nonzero_ratio",
    "best_gain_nonzero_slots",
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
    "selection_reasons",
    "payload_offset",
    "source_mode",
    "row_stride",
    "row_prefix_skip",
    "base_nonzero_exact_slots",
    "adjusted_nonzero_exact_slots",
    "adjusted_nonzero_exact_ratio",
    "adjusted_gain_nonzero_slots",
    "full_nonzero_rows",
    "best_row_nonzero_exact",
    "worst_row_nonzero_exact",
    "delta_values",
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
    "row_start",
    "row_end",
    "source_start",
    "best_delta",
    "best_source_start",
    "nonzero_slots",
    "base_nonzero_exact_slots",
    "adjusted_nonzero_exact_slots",
    "adjusted_gain_nonzero_slots",
    "full_nonzero_row",
    "first_mismatch_x",
    "expected_nonzero_head_hex",
    "adjusted_nonzero_head_hex",
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


def build_row_geometry(
    expected_len: int,
    *,
    gap_start: int,
    width: int,
    zero_columns: int,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    current_row: int | None = None
    row_start = 0
    nonzero: list[tuple[int, int, int]] = []
    for offset in range(expected_len):
        absolute = gap_start + offset
        row_index = absolute // width if width else 0
        x = absolute % width if width else 0
        if current_row is None:
            current_row = row_index
            row_start = offset
        if row_index != current_row:
            rows.append(
                {
                    "absolute_row": current_row,
                    "row_start": row_start,
                    "row_end": offset,
                    "nonzero": nonzero,
                }
            )
            current_row = row_index
            row_start = offset
            nonzero = []
        if x >= zero_columns:
            nonzero.append((offset, x - zero_columns, x))
    if current_row is not None:
        rows.append(
            {
                "absolute_row": current_row,
                "row_start": row_start,
                "row_end": expected_len,
                "nonzero": nonzero,
            }
        )
    return rows


def exact_for_delta(source: bytes, expected: bytes, nonzero: list[tuple[int, int, int]], base: int, delta: int) -> int:
    exact = 0
    for output_offset, slot_index, _x in nonzero:
        source_index = base + delta + slot_index
        value = source[source_index] if 0 <= source_index < len(source) else 0
        if value == expected[output_offset]:
            exact += 1
    return exact


def adjusted_head(source: bytes, nonzero: list[tuple[int, int, int]], base: int, delta: int, context_bytes: int) -> bytes:
    values = []
    for _output_offset, slot_index, _x in nonzero[:context_bytes]:
        source_index = base + delta + slot_index
        values.append(source[source_index] if 0 <= source_index < len(source) else 0)
    return bytes(values)


def analyze_candidate(
    candidate: dict[str, str],
    fixture: dict[str, str],
    zero_fixture: dict[str, str],
    *,
    max_abs_delta: int,
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
    source = source_bytes(segment, int_value(candidate, "payload_offset"), candidate.get("source_mode", "raw"))
    selection_id = candidate.get("selection_id", "")
    row_rows: list[dict[str, str]] = []
    adjusted_total = 0
    base_total = 0
    full_nonzero_rows = 0
    best_row_exact = 0
    worst_row_exact: int | None = None
    delta_values: set[int] = set()

    for row_index, row in enumerate(rows):
        nonzero = row["nonzero"]  # type: ignore[assignment]
        base = row_index * int_value(candidate, "row_stride") + int_value(candidate, "row_prefix_skip")
        base_exact = exact_for_delta(source, expected, nonzero, base, 0)
        best_exact = -1
        best_delta = 0
        for delta in range(-max_abs_delta, max_abs_delta + 1):
            exact = exact_for_delta(source, expected, nonzero, base, delta)
            if exact > best_exact:
                best_exact = exact
                best_delta = delta
        if best_exact < 0:
            best_exact = 0
        nonzero_count = len(nonzero)
        if nonzero_count and best_exact == nonzero_count:
            full_nonzero_rows += 1
        adjusted_total += best_exact
        base_total += base_exact
        best_row_exact = max(best_row_exact, best_exact)
        worst_row_exact = best_exact if worst_row_exact is None else min(worst_row_exact, best_exact)
        delta_values.add(best_delta)

        mismatch_x = ""
        for output_offset, slot_index, x in nonzero:
            source_index = base + best_delta + slot_index
            value = source[source_index] if 0 <= source_index < len(source) else None
            if value != expected[output_offset]:
                mismatch_x = str(x)
                break
        expected_head = bytes(expected[offset] for offset, _slot, _x in nonzero[:context_bytes])
        row_rows.append(
            {
                "selection_id": selection_id,
                "rank": candidate.get("rank", ""),
                "pcx_name": candidate.get("pcx_name", ""),
                "frontier_id": candidate.get("frontier_id", ""),
                "row_index": str(row_index),
                "absolute_row": str(row["absolute_row"]),
                "row_start": str(row["row_start"]),
                "row_end": str(row["row_end"]),
                "source_start": str(base),
                "best_delta": str(best_delta),
                "best_source_start": str(base + best_delta),
                "nonzero_slots": str(nonzero_count),
                "base_nonzero_exact_slots": str(base_exact),
                "adjusted_nonzero_exact_slots": str(best_exact),
                "adjusted_gain_nonzero_slots": str(best_exact - base_exact),
                "full_nonzero_row": "1" if nonzero_count and best_exact == nonzero_count else "0",
                "first_mismatch_x": mismatch_x,
                "expected_nonzero_head_hex": expected_head.hex(),
                "adjusted_nonzero_head_hex": adjusted_head(source, nonzero, base, best_delta, context_bytes).hex(),
            }
        )
    if adjusted_total <= base_total:
        notes.append("no_delta_gain")

    nonzero_slots = sum(int_value(row, "nonzero_slots") for row in row_rows)
    candidate_row = {
        "selection_id": selection_id,
        "rank": candidate.get("rank", ""),
        "rule_type": candidate.get("rule_type", ""),
        "archive": candidate.get("archive", ""),
        "archive_tag": candidate.get("archive_tag", ""),
        "pcx_name": candidate.get("pcx_name", ""),
        "frontier_id": candidate.get("frontier_id", ""),
        "frontier_type": candidate.get("frontier_type", ""),
        "selection_reasons": candidate.get("selection_reasons", ""),
        "payload_offset": candidate.get("payload_offset", ""),
        "source_mode": candidate.get("source_mode", ""),
        "row_stride": candidate.get("row_stride", ""),
        "row_prefix_skip": candidate.get("row_prefix_skip", ""),
        "base_nonzero_exact_slots": str(base_total),
        "adjusted_nonzero_exact_slots": str(adjusted_total),
        "adjusted_nonzero_exact_ratio": f"{(adjusted_total / nonzero_slots) if nonzero_slots else 0.0:.6f}",
        "adjusted_gain_nonzero_slots": str(adjusted_total - base_total),
        "full_nonzero_rows": str(full_nonzero_rows),
        "best_row_nonzero_exact": str(best_row_exact),
        "worst_row_nonzero_exact": str(worst_row_exact or 0),
        "delta_values": ";".join(str(value) for value in sorted(delta_values)),
        "issue_notes": ";".join(notes),
        "issues": ";".join(issues),
    }
    return candidate_row, row_rows


def build_rows(
    fixtures: Path,
    zero_run_fixtures: Path,
    candidates: Path,
    *,
    max_abs_delta: int,
    context_bytes: int,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    fixtures_by_key = {fixture_key(row): row for row in read_rows(fixtures)}
    zero_by_key = {zero_key(row): row for row in read_rows(zero_run_fixtures)}
    candidate_rows: list[dict[str, str]] = []
    row_rows: list[dict[str, str]] = []
    for candidate in read_rows(candidates):
        key = fixture_key(candidate)
        fixture = fixtures_by_key.get(key, {})
        zero_fixture = zero_by_key.get(
            (candidate.get("archive", ""), candidate.get("pcx_name", ""), candidate.get("frontier_id", "")),
            {},
        )
        analyzed, rows = analyze_candidate(
            candidate,
            fixture,
            zero_fixture,
            max_abs_delta=max_abs_delta,
            context_bytes=context_bytes,
        )
        candidate_rows.append(analyzed)
        row_rows.extend(rows)
    return candidate_rows, row_rows


def summary_row(
    candidate_rows: list[dict[str, str]],
    row_rows: list[dict[str, str]],
    *,
    max_abs_delta: int,
) -> dict[str, str]:
    best = (
        max(
            candidate_rows,
            key=lambda row: (
                int_value(row, "adjusted_nonzero_exact_slots"),
                int_value(row, "adjusted_gain_nonzero_slots"),
                int_value(row, "base_nonzero_exact_slots"),
            ),
        )
        if candidate_rows
        else {}
    )
    adjusted = int_value(best, "adjusted_nonzero_exact_slots")
    nonzero_slots = sum(
        int_value(row, "nonzero_slots")
        for row in row_rows
        if row.get("selection_id") == best.get("selection_id", "")
    )
    all_deltas = {
        int_value(row, "best_delta")
        for row in row_rows
        if row.get("best_delta", "").lstrip("-").isdigit()
    }
    return {
        "scope": "total",
        "selected_candidates": str(len(candidate_rows)),
        "row_delta_rows": str(len(row_rows)),
        "fixtures": str(len({fixture_key(row) for row in candidate_rows})),
        "max_abs_delta": str(max_abs_delta),
        "unique_delta_values": str(len(all_deltas)),
        "full_nonzero_rows": str(sum(int_value(row, "full_nonzero_rows") for row in candidate_rows)),
        "best_adjusted_nonzero_slots": str(adjusted),
        "best_adjusted_nonzero_ratio": f"{(adjusted / nonzero_slots) if nonzero_slots else 0.0:.6f}",
        "best_gain_nonzero_slots": str(max([int_value(row, "adjusted_gain_nonzero_slots") for row in candidate_rows] or [0])),
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
        f"<td>{html.escape(row.get('payload_offset', ''))}</td>"
        f"<td>{html.escape(row.get('source_mode', ''))}</td>"
        f"<td>{html.escape(row.get('row_stride', ''))}</td>"
        f"<td>{html.escape(row.get('row_prefix_skip', ''))}</td>"
        f"<td>{html.escape(row.get('base_nonzero_exact_slots', ''))}</td>"
        f"<td>{html.escape(row.get('adjusted_nonzero_exact_slots', ''))}</td>"
        f"<td>{html.escape(row.get('adjusted_gain_nonzero_slots', ''))}</td>"
        f"<td>{html.escape(row.get('full_nonzero_rows', ''))}</td>"
        f"<td>{html.escape(row.get('issue_notes', ''))}</td>"
        f"<td>{html.escape(row.get('issues', ''))}</td>"
        "</tr>"
    )


def render_delta_row(row: dict[str, str]) -> str:
    return (
        "<tr>"
        f"<td>{html.escape(row.get('selection_id', ''))}</td>"
        f"<td>{html.escape(row.get('row_index', ''))}</td>"
        f"<td>{html.escape(row.get('source_start', ''))}</td>"
        f"<td>{html.escape(row.get('best_delta', ''))}</td>"
        f"<td>{html.escape(row.get('base_nonzero_exact_slots', ''))}</td>"
        f"<td>{html.escape(row.get('adjusted_nonzero_exact_slots', ''))}</td>"
        f"<td>{html.escape(row.get('adjusted_gain_nonzero_slots', ''))}</td>"
        f"<td>{html.escape(row.get('first_mismatch_x', ''))}</td>"
        f"<td><code>{html.escape(row.get('expected_nonzero_head_hex', ''))}</code></td>"
        f"<td><code>{html.escape(row.get('adjusted_nonzero_head_hex', ''))}</code></td>"
        "</tr>"
    )


def build_html(
    summary: dict[str, str],
    candidate_rows: list[dict[str, str]],
    row_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "candidates": candidate_rows, "rowDeltas": row_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("candidates.csv", output_dir / "candidates.csv"),
            ("row_deltas.csv", output_dir / "row_deltas.csv"),
        )
    )
    candidate_markup = "\n".join(
        render_candidate_row(row)
        for row in sorted(candidate_rows, key=lambda row: int_value(row, "adjusted_nonzero_exact_slots"), reverse=True)
    )
    top_rows = sorted(row_rows, key=lambda row: int_value(row, "adjusted_gain_nonzero_slots"), reverse=True)[:180]
    row_markup = "\n".join(render_delta_row(row) for row in top_rows)
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
.sub {{ color: var(--muted); margin-top: 4px; }}
main {{ padding: 16px 0 28px; display: grid; gap: 16px; }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; }}
.stat, .panel {{ border: 1px solid var(--line); border-radius: 8px; background: var(--panel); padding: 10px; }}
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
    <div class="sub">Delta source local par ligne pour les meilleurs candidats row-stride .tex.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Candidates</div><div class="value">{html.escape(summary['selected_candidates'])}</div></div>
    <div class="stat"><div class="label">Row deltas</div><div class="value">{html.escape(summary['row_delta_rows'])}</div></div>
    <div class="stat"><div class="label">Best adjusted</div><div class="value ok">{html.escape(summary['best_adjusted_nonzero_slots'])}</div></div>
    <div class="stat"><div class="label">Best gain</div><div class="value ok">{html.escape(summary['best_gain_nonzero_slots'])}</div></div>
    <div class="stat"><div class="label">Full rows</div><div class="value">{html.escape(summary['full_nonzero_rows'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div></section>
  <section class="panel">
    <h2>Candidates</h2>
    <table>
      <thead><tr><th>ID</th><th>PCX</th><th>Frontier</th><th>Offset</th><th>Mode</th><th>Stride</th><th>Prefix skip</th><th>Base</th><th>Adjusted</th><th>Gain</th><th>Full rows</th><th>Notes</th><th>Issues</th></tr></thead>
      <tbody>{candidate_markup}</tbody>
    </table>
  </section>
  <section class="panel">
    <h2>Top row deltas</h2>
    <table>
      <thead><tr><th>ID</th><th>Row</th><th>Source start</th><th>Delta</th><th>Base</th><th>Adjusted</th><th>Gain</th><th>Mismatch x</th><th>Expected</th><th>Adjusted</th></tr></thead>
      <tbody>{row_markup}</tbody>
    </table>
  </section>
</main>
<script>
const TEX_GAP_ROW_DELTA_PROBE = {data_json};
</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    fixtures: Path,
    zero_run_fixtures: Path,
    candidates: Path,
    *,
    max_abs_delta: int,
    context_bytes: int,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    candidate_rows, row_rows = build_rows(
        fixtures,
        zero_run_fixtures,
        candidates,
        max_abs_delta=max_abs_delta,
        context_bytes=context_bytes,
    )
    summary = summary_row(candidate_rows, row_rows, max_abs_delta=max_abs_delta)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "candidates.csv", CANDIDATE_FIELDNAMES, candidate_rows)
    write_csv(output_dir / "row_deltas.csv", ROW_FIELDNAMES, row_rows)
    (output_dir / "index.html").write_text(build_html(summary, candidate_rows, row_rows, output_dir, title))
    return summary, candidate_rows, row_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe local per-row source deltas for .tex row-stride candidates.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--zero-run-fixtures", type=Path, default=DEFAULT_ZERO_RUN_FIXTURES)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--max-abs-delta", type=int, default=96)
    parser.add_argument("--context-bytes", type=int, default=24)
    parser.add_argument("--title", default="Lands of Lore II .tex Gap Row Delta Probe")
    args = parser.parse_args()

    summary, _candidate_rows, _row_rows = write_report(
        args.output,
        args.fixtures,
        args.zero_run_fixtures,
        args.candidates,
        max_abs_delta=args.max_abs_delta,
        context_bytes=args.context_bytes,
        title=args.title,
    )
    print(f"Selected candidates: {summary['selected_candidates']}")
    print(f"Row delta rows: {summary['row_delta_rows']}")
    print(f"Best adjusted nonzero slots: {summary['best_adjusted_nonzero_slots']}")
    print(f"Best gain nonzero slots: {summary['best_gain_nonzero_slots']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
