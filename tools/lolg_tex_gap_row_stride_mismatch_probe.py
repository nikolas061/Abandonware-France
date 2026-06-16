#!/usr/bin/env python3
"""Analyze row-level mismatches for top .tex row-stride gap candidates."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import defaultdict
from pathlib import Path

from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv
from lolg_tex_gap_row_stride_probe import row_stride_replay, source_bytes


DEFAULT_OUTPUT = Path("output/tex_gap_row_stride_mismatch_probe")
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_ZERO_RUN_FIXTURES = Path("output/tex_gap_zero_run_probe/fixtures.csv")
DEFAULT_CANDIDATES = Path("output/tex_gap_row_stride_probe/candidates.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "selected_candidates",
    "row_score_rows",
    "fixtures",
    "full_nonzero_rows",
    "best_nonzero_exact_slots",
    "best_nonzero_exact_ratio",
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
    "prefix_bytes",
    "exact_bytes",
    "row_count",
    "nonzero_slots",
    "nonzero_exact_slots",
    "nonzero_exact_ratio",
    "full_nonzero_rows",
    "best_row_nonzero_exact",
    "worst_row_nonzero_exact",
    "first_mismatch_row",
    "first_mismatch_x",
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
    "row_bytes",
    "row_exact_bytes",
    "nonzero_slots",
    "nonzero_exact_slots",
    "nonzero_exact_ratio",
    "first_mismatch_at",
    "first_mismatch_x",
    "expected_nonzero_head_hex",
    "output_nonzero_head_hex",
]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def fixture_key(row: dict[str, str]) -> tuple[str, str, str]:
    return (row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", ""))


def zero_key(row: dict[str, str]) -> tuple[str, str, str]:
    return (row.get("archive", ""), row.get("pcx_name", ""), row.get("frontier_id", ""))


def candidate_key(row: dict[str, str]) -> tuple[str, str, str, str, str, str, str]:
    return (
        row.get("rank", ""),
        row.get("pcx_name", ""),
        row.get("frontier_id", ""),
        row.get("payload_offset", ""),
        row.get("source_mode", ""),
        row.get("row_stride", ""),
        row.get("row_prefix_skip", ""),
    )


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


def select_candidates(rows: list[dict[str, str]], per_fixture: int) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[fixture_key(row)].append(row)

    selected: dict[tuple[str, str, str, str, str, str, str], dict[str, str]] = {}
    reasons: dict[tuple[str, str, str, str, str, str, str], set[str]] = defaultdict(set)
    for candidates in grouped.values():
        by_prefix = sorted(
            candidates,
            key=lambda row: (
                int_value(row, "prefix_bytes"),
                int_value(row, "exact_bytes"),
                -int_value(row, "payload_offset"),
                -int_value(row, "row_stride"),
                -int_value(row, "row_prefix_skip"),
            ),
            reverse=True,
        )[:per_fixture]
        by_exact = sorted(
            candidates,
            key=lambda row: (
                int_value(row, "exact_bytes"),
                int_value(row, "prefix_bytes"),
                -int_value(row, "payload_offset"),
                -int_value(row, "row_stride"),
                -int_value(row, "row_prefix_skip"),
            ),
            reverse=True,
        )[:per_fixture]
        for index, row in enumerate(by_prefix, start=1):
            key = candidate_key(row)
            selected[key] = row
            reasons[key].add(f"top_prefix_{index}")
        for index, row in enumerate(by_exact, start=1):
            key = candidate_key(row)
            selected[key] = row
            reasons[key].add(f"top_exact_{index}")

    output = []
    for key, row in selected.items():
        copied = dict(row)
        copied["selection_reasons"] = ";".join(sorted(reasons[key]))
        output.append(copied)
    return sorted(
        output,
        key=lambda row: (
            int_value(row, "rank"),
            -int_value(row, "exact_bytes"),
            -int_value(row, "prefix_bytes"),
            int_value(row, "payload_offset"),
        ),
    )


def analyze_candidate(
    candidate: dict[str, str],
    fixture: dict[str, str],
    zero_fixture: dict[str, str],
    *,
    context_bytes: int,
) -> tuple[dict[str, str], list[dict[str, str]]]:
    issues: list[str] = []
    segment = load_bytes(fixture.get("segment_gap_path", ""), issues, "segment")
    expected = load_bytes(fixture.get("expected_gap_path", ""), issues, "expected")
    width = int_value(zero_fixture, "cdcache_width")
    zero_columns = int_value(zero_fixture, "leading_zero_bytes")
    geometry = build_row_geometry(
        len(expected),
        gap_start=int_value(zero_fixture, "gap_start"),
        width=width,
        zero_columns=zero_columns,
    )
    row_slots = [
        [(offset, slot_index) for offset, slot_index, _x in row["nonzero"]]  # type: ignore[index]
        for row in geometry
    ]
    payload_offset = int_value(candidate, "payload_offset")
    source = source_bytes(segment, payload_offset, candidate.get("source_mode", "raw"))
    output, nonzero_slots, _stream_short = row_stride_replay(
        len(expected),
        row_slots,
        source,
        row_stride=int_value(candidate, "row_stride"),
        row_prefix_skip=int_value(candidate, "row_prefix_skip"),
    )

    row_rows: list[dict[str, str]] = []
    full_nonzero_rows = 0
    best_row_nonzero = 0
    worst_row_nonzero: int | None = None
    first_mismatch_row = ""
    first_mismatch_x = ""
    nonzero_exact_slots = 0
    selection_id = (
        f"r{candidate.get('rank', '')}_f{candidate.get('frontier_id', '')}_"
        f"o{candidate.get('payload_offset', '')}_{candidate.get('source_mode', '')}_"
        f"s{candidate.get('row_stride', '')}_p{candidate.get('row_prefix_skip', '')}"
    )

    for row_index, row in enumerate(geometry):
        row_start = int(row["row_start"])
        row_end = int(row["row_end"])
        nonzero = row["nonzero"]  # type: ignore[assignment]
        row_exact = sum(1 for offset in range(row_start, row_end) if output[offset] == expected[offset])
        row_nonzero_exact = sum(1 for offset, _slot, _x in nonzero if output[offset] == expected[offset])
        nonzero_count = len(nonzero)
        nonzero_exact_slots += row_nonzero_exact
        if nonzero_count and row_nonzero_exact == nonzero_count:
            full_nonzero_rows += 1
        best_row_nonzero = max(best_row_nonzero, row_nonzero_exact)
        worst_row_nonzero = (
            row_nonzero_exact
            if worst_row_nonzero is None
            else min(worst_row_nonzero, row_nonzero_exact)
        )
        mismatch_at = ""
        mismatch_x = ""
        for offset in range(row_start, row_end):
            if output[offset] != expected[offset]:
                mismatch_at = str(offset)
                absolute = int_value(zero_fixture, "gap_start") + offset
                mismatch_x = str(absolute % width if width else 0)
                if not first_mismatch_row:
                    first_mismatch_row = str(row_index)
                    first_mismatch_x = mismatch_x
                break
        nonzero_offsets = [offset for offset, _slot, _x in nonzero]
        expected_head = bytes(expected[offset] for offset in nonzero_offsets[:context_bytes])
        output_head = bytes(output[offset] for offset in nonzero_offsets[:context_bytes])
        row_rows.append(
            {
                "selection_id": selection_id,
                "rank": candidate.get("rank", ""),
                "pcx_name": candidate.get("pcx_name", ""),
                "frontier_id": candidate.get("frontier_id", ""),
                "row_index": str(row_index),
                "absolute_row": str(row["absolute_row"]),
                "row_start": str(row_start),
                "row_end": str(row_end),
                "source_start": str(row_index * int_value(candidate, "row_stride") + int_value(candidate, "row_prefix_skip")),
                "row_bytes": str(row_end - row_start),
                "row_exact_bytes": str(row_exact),
                "nonzero_slots": str(nonzero_count),
                "nonzero_exact_slots": str(row_nonzero_exact),
                "nonzero_exact_ratio": f"{(row_nonzero_exact / nonzero_count) if nonzero_count else 0.0:.6f}",
                "first_mismatch_at": mismatch_at,
                "first_mismatch_x": mismatch_x,
                "expected_nonzero_head_hex": expected_head.hex(),
                "output_nonzero_head_hex": output_head.hex(),
            }
        )

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
        "prefix_bytes": candidate.get("prefix_bytes", ""),
        "exact_bytes": candidate.get("exact_bytes", ""),
        "row_count": str(len(geometry)),
        "nonzero_slots": str(nonzero_slots),
        "nonzero_exact_slots": str(nonzero_exact_slots),
        "nonzero_exact_ratio": f"{(nonzero_exact_slots / nonzero_slots) if nonzero_slots else 0.0:.6f}",
        "full_nonzero_rows": str(full_nonzero_rows),
        "best_row_nonzero_exact": str(best_row_nonzero),
        "worst_row_nonzero_exact": str(worst_row_nonzero or 0),
        "first_mismatch_row": first_mismatch_row,
        "first_mismatch_x": first_mismatch_x,
        "issues": ";".join(issues),
    }
    return candidate_row, row_rows


def build_rows(
    fixtures: Path,
    zero_run_fixtures: Path,
    candidates: Path,
    *,
    per_fixture: int,
    context_bytes: int,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    fixtures_by_key = {fixture_key(row): row for row in read_rows(fixtures)}
    zero_by_key = {zero_key(row): row for row in read_rows(zero_run_fixtures)}
    selected = select_candidates(read_rows(candidates), per_fixture)
    candidate_rows: list[dict[str, str]] = []
    row_rows: list[dict[str, str]] = []
    for candidate in selected:
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
                int_value(row, "nonzero_exact_slots"),
                int_value(row, "exact_bytes"),
                int_value(row, "prefix_bytes"),
            ),
        )
        if candidate_rows
        else {}
    )
    nonzero_slots = int_value(best, "nonzero_slots")
    best_nonzero = int_value(best, "nonzero_exact_slots")
    return {
        "scope": "total",
        "selected_candidates": str(len(candidate_rows)),
        "row_score_rows": str(len(row_rows)),
        "fixtures": str(len({fixture_key(row) for row in candidate_rows})),
        "full_nonzero_rows": str(sum(int_value(row, "full_nonzero_rows") for row in candidate_rows)),
        "best_nonzero_exact_slots": str(best_nonzero),
        "best_nonzero_exact_ratio": f"{(best_nonzero / nonzero_slots) if nonzero_slots else 0.0:.6f}",
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
        f"<td>{html.escape(row.get('selection_reasons', ''))}</td>"
        f"<td>{html.escape(row.get('pcx_name', ''))}</td>"
        f"<td>{html.escape(row.get('frontier_id', ''))}</td>"
        f"<td>{html.escape(row.get('payload_offset', ''))}</td>"
        f"<td>{html.escape(row.get('source_mode', ''))}</td>"
        f"<td>{html.escape(row.get('row_stride', ''))}</td>"
        f"<td>{html.escape(row.get('row_prefix_skip', ''))}</td>"
        f"<td>{html.escape(row.get('nonzero_exact_slots', ''))}/{html.escape(row.get('nonzero_slots', ''))}</td>"
        f"<td>{html.escape(row.get('full_nonzero_rows', ''))}</td>"
        f"<td>{html.escape(row.get('first_mismatch_row', ''))}</td>"
        f"<td>{html.escape(row.get('issues', ''))}</td>"
        "</tr>"
    )


def render_row_score(row: dict[str, str]) -> str:
    return (
        "<tr>"
        f"<td>{html.escape(row.get('selection_id', ''))}</td>"
        f"<td>{html.escape(row.get('row_index', ''))}</td>"
        f"<td>{html.escape(row.get('row_start', ''))}-{html.escape(row.get('row_end', ''))}</td>"
        f"<td>{html.escape(row.get('source_start', ''))}</td>"
        f"<td>{html.escape(row.get('nonzero_exact_slots', ''))}/{html.escape(row.get('nonzero_slots', ''))}</td>"
        f"<td>{html.escape(row.get('first_mismatch_x', ''))}</td>"
        f"<td><code>{html.escape(row.get('expected_nonzero_head_hex', ''))}</code></td>"
        f"<td><code>{html.escape(row.get('output_nonzero_head_hex', ''))}</code></td>"
        "</tr>"
    )


def build_html(
    summary: dict[str, str],
    candidate_rows: list[dict[str, str]],
    row_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "candidates": candidate_rows, "rows": row_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("candidates.csv", output_dir / "candidates.csv"),
            ("row_scores.csv", output_dir / "row_scores.csv"),
        )
    )
    candidate_markup = "\n".join(render_candidate_row(row) for row in candidate_rows)
    top_rows = sorted(row_rows, key=lambda row: int_value(row, "nonzero_exact_slots"), reverse=True)[:180]
    row_markup = "\n".join(render_row_score(row) for row in top_rows)
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
table {{ width: 100%; border-collapse: collapse; min-width: 1260px; }}
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
    <div class="sub">Scores par ligne pour les meilleurs candidats row-stride .tex.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Candidates</div><div class="value">{html.escape(summary['selected_candidates'])}</div></div>
    <div class="stat"><div class="label">Row scores</div><div class="value">{html.escape(summary['row_score_rows'])}</div></div>
    <div class="stat"><div class="label">Full nonzero rows</div><div class="value ok">{html.escape(summary['full_nonzero_rows'])}</div></div>
    <div class="stat"><div class="label">Best nonzero slots</div><div class="value ok">{html.escape(summary['best_nonzero_exact_slots'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div></section>
  <section class="panel">
    <h2>Selected candidates</h2>
    <table>
      <thead><tr><th>ID</th><th>Reason</th><th>PCX</th><th>Frontier</th><th>Offset</th><th>Mode</th><th>Stride</th><th>Prefix skip</th><th>Nonzero exact</th><th>Full rows</th><th>First mismatch row</th><th>Issues</th></tr></thead>
      <tbody>{candidate_markup}</tbody>
    </table>
  </section>
  <section class="panel">
    <h2>Top row scores</h2>
    <table>
      <thead><tr><th>ID</th><th>Row</th><th>Output range</th><th>Source start</th><th>Nonzero exact</th><th>Mismatch x</th><th>Expected</th><th>Output</th></tr></thead>
      <tbody>{row_markup}</tbody>
    </table>
  </section>
</main>
<script>
const TEX_GAP_ROW_STRIDE_MISMATCH_PROBE = {data_json};
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
    per_fixture: int,
    context_bytes: int,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    candidate_rows, row_rows = build_rows(
        fixtures,
        zero_run_fixtures,
        candidates,
        per_fixture=per_fixture,
        context_bytes=context_bytes,
    )
    summary = summary_row(candidate_rows, row_rows)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "candidates.csv", CANDIDATE_FIELDNAMES, candidate_rows)
    write_csv(output_dir / "row_scores.csv", ROW_FIELDNAMES, row_rows)
    (output_dir / "index.html").write_text(build_html(summary, candidate_rows, row_rows, output_dir, title))
    return summary, candidate_rows, row_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze row-level mismatches for top .tex row-stride candidates.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--zero-run-fixtures", type=Path, default=DEFAULT_ZERO_RUN_FIXTURES)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--per-fixture", type=int, default=2)
    parser.add_argument("--context-bytes", type=int, default=24)
    parser.add_argument("--title", default="Lands of Lore II .tex Gap Row Stride Mismatch Probe")
    args = parser.parse_args()

    summary, _candidate_rows, _row_rows = write_report(
        args.output,
        args.fixtures,
        args.zero_run_fixtures,
        args.candidates,
        per_fixture=args.per_fixture,
        context_bytes=args.context_bytes,
        title=args.title,
    )
    print(f"Selected candidates: {summary['selected_candidates']}")
    print(f"Row score rows: {summary['row_score_rows']}")
    print(f"Full nonzero rows: {summary['full_nonzero_rows']}")
    print(f"Best nonzero exact slots: {summary['best_nonzero_exact_slots']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
