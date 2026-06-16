#!/usr/bin/env python3
"""Probe ordered length sequences for alternating stable micro-token segments."""

from __future__ import annotations

import argparse
import csv
import html
import json
from pathlib import Path


DEFAULT_REPLAYS = Path("output/tex_micro_stable_alternation_replay/replays.csv")
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_OUTPUT = Path("output/tex_micro_stable_length_sequences")

SUMMARY_FIELDNAMES = [
    "scope",
    "segment_rows",
    "segment_bytes",
    "ordered_sequence_rows",
    "ordered_sequence_bytes",
    "compact_sequence_rows",
    "compact_sequence_bytes",
    "unique_ordered_sequence_rows",
    "unique_ordered_sequence_bytes",
    "suffix_ordered_rows",
    "suffix_ordered_bytes",
    "suffix_compact_rows",
    "suffix_compact_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

SEQUENCE_FIELDNAMES = [
    "rank",
    "segment_rank",
    "source_rank",
    "group_rank",
    "archive",
    "pcx_name",
    "frontier_id",
    "segment_start_run",
    "segment_end_run",
    "segment_runs",
    "segment_bytes",
    "values",
    "lengths",
    "is_suffix",
    "ordered_match_count",
    "best_offsets",
    "best_span",
    "best_gap_total",
    "compact_match",
    "unique_ordered_match",
    "verdict",
]

MATCH_FIELDNAMES = [
    "rank",
    "segment_rank",
    "match_rank",
    "offsets",
    "span",
    "gap_total",
    "compact_match",
]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def int_value(row: dict[str, str], field: str) -> int:
    try:
        return int(row.get(field, "") or 0)
    except ValueError:
        return 0


def locator_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("archive", ""), row.get("pcx_name", ""), row.get("frontier_id", "")


def load_bytes(path_text: str, issues: list[str], label: str) -> bytes:
    if not path_text:
        issues.append(f"missing_{label}_path")
        return b""
    try:
        return Path(path_text).read_bytes()
    except OSError as exc:
        issues.append(f"read_{label}_failed:{exc}")
        return b""


def load_segments(fixture_rows: list[dict[str, str]]) -> tuple[dict[tuple[str, str, str], bytes], list[str]]:
    segments: dict[tuple[str, str, str], bytes] = {}
    issues: list[str] = []
    for fixture in fixture_rows:
        local_issues: list[str] = []
        segments[locator_key(fixture)] = load_bytes(fixture.get("segment_gap_path", ""), local_issues, "segment")
        issues.extend(f"{locator_key(fixture)}:{issue}" for issue in local_issues)
    return segments, issues


def parse_lengths(text: str) -> list[int]:
    output: list[int] = []
    for part in text.split(";"):
        if part.isdigit():
            output.append(int(part))
    return output


def format_offsets(offsets: list[int]) -> str:
    return ";".join(str(value) for value in offsets)


def find_ordered_matches(segment: bytes, lengths: list[int], *, max_matches: int, max_span: int) -> list[list[int]]:
    if not lengths:
        return []
    matches: list[list[int]] = []

    positions_by_length: list[list[int]] = [
        [index for index, value in enumerate(segment) if value == (length & 0xFF)]
        for length in lengths
    ]
    if any(not positions for positions in positions_by_length):
        return []

    def visit(depth: int, previous: int, offsets: list[int]) -> None:
        if len(matches) >= max_matches:
            return
        if depth == len(lengths):
            matches.append(offsets.copy())
            return
        first = offsets[0] if offsets else None
        for position in positions_by_length[depth]:
            if position <= previous:
                continue
            if first is not None and position - first + 1 > max_span:
                continue
            offsets.append(position)
            visit(depth + 1, position, offsets)
            offsets.pop()

    visit(0, -1, [])
    matches.sort(key=lambda offsets: (offsets[-1] - offsets[0], sum(b - a - 1 for a, b in zip(offsets, offsets[1:])), offsets))
    return matches[:max_matches]


def match_metrics(offsets: list[int], length_count: int) -> tuple[int, int, bool]:
    if not offsets:
        return 0, 0, False
    span = offsets[-1] - offsets[0] + 1
    gap_total = sum(right - left - 1 for left, right in zip(offsets, offsets[1:]))
    return span, gap_total, span == length_count


def build(
    replay_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    *,
    max_matches: int,
    max_span: int,
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    segments_by_fixture, segment_issues = load_segments(fixture_rows)
    sequence_rows: list[dict[str, object]] = []
    match_rows: list[dict[str, object]] = []

    for replay in replay_rows:
        segment = segments_by_fixture.get(locator_key(replay), b"")
        lengths = parse_lengths(replay.get("lengths", ""))
        matches = find_ordered_matches(segment, lengths, max_matches=max_matches, max_span=max_span)
        best = matches[0] if matches else []
        span, gap_total, compact = match_metrics(best, len(lengths))
        segment_rank = int_value(replay, "rank")
        unique_ordered = len(matches) == 1
        verdict = "length_sequence_compact_candidate" if compact else "length_sequence_ordered_review" if best else "length_sequence_missing"
        sequence_rows.append(
            {
                "rank": len(sequence_rows) + 1,
                "segment_rank": segment_rank,
                "source_rank": replay.get("source_rank", ""),
                "group_rank": replay.get("group_rank", ""),
                "archive": replay.get("archive", ""),
                "pcx_name": replay.get("pcx_name", ""),
                "frontier_id": replay.get("frontier_id", ""),
                "segment_start_run": replay.get("segment_start_run", ""),
                "segment_end_run": replay.get("segment_end_run", ""),
                "segment_runs": replay.get("segment_runs", ""),
                "segment_bytes": replay.get("segment_bytes", ""),
                "values": replay.get("values", ""),
                "lengths": replay.get("lengths", ""),
                "is_suffix": replay.get("is_suffix", ""),
                "ordered_match_count": len(matches),
                "best_offsets": format_offsets(best),
                "best_span": span,
                "best_gap_total": gap_total,
                "compact_match": 1 if compact else 0,
                "unique_ordered_match": 1 if unique_ordered and best else 0,
                "verdict": verdict,
            }
        )
        for match_rank, offsets in enumerate(matches, start=1):
            local_span, local_gap_total, local_compact = match_metrics(offsets, len(lengths))
            match_rows.append(
                {
                    "rank": len(match_rows) + 1,
                    "segment_rank": segment_rank,
                    "match_rank": match_rank,
                    "offsets": format_offsets(offsets),
                    "span": local_span,
                    "gap_total": local_gap_total,
                    "compact_match": 1 if local_compact else 0,
                }
            )

    ordered = [row for row in sequence_rows if int(row["ordered_match_count"]) > 0]
    compact_rows = [row for row in sequence_rows if int(row["compact_match"]) > 0]
    unique_rows = [row for row in sequence_rows if int(row["unique_ordered_match"]) > 0]
    suffix_ordered = [row for row in ordered if str(row["is_suffix"]) == "1"]
    suffix_compact = [row for row in compact_rows if str(row["is_suffix"]) == "1"]
    summary = {
        "scope": "total",
        "segment_rows": len(sequence_rows),
        "segment_bytes": sum(int_value(row, "segment_bytes") for row in sequence_rows),
        "ordered_sequence_rows": len(ordered),
        "ordered_sequence_bytes": sum(int_value(row, "segment_bytes") for row in ordered),
        "compact_sequence_rows": len(compact_rows),
        "compact_sequence_bytes": sum(int_value(row, "segment_bytes") for row in compact_rows),
        "unique_ordered_sequence_rows": len(unique_rows),
        "unique_ordered_sequence_bytes": sum(int_value(row, "segment_bytes") for row in unique_rows),
        "suffix_ordered_rows": len(suffix_ordered),
        "suffix_ordered_bytes": sum(int_value(row, "segment_bytes") for row in suffix_ordered),
        "suffix_compact_rows": len(suffix_compact),
        "suffix_compact_bytes": sum(int_value(row, "segment_bytes") for row in suffix_compact),
        "promotion_ready_bytes": 0,
        "issue_rows": len(segment_issues),
    }
    return summary, sequence_rows, match_rows


def render_table(rows: list[dict[str, object]], fields: list[str], limit: int = 220) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, object],
    sequences: list[dict[str, object]],
    matches: list[dict[str, object]],
    title: str,
) -> str:
    data_json = json.dumps({"summary": summary, "sequences": sequences, "matches": matches}, indent=2, sort_keys=True)
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body {{ margin: 2rem; background: #111416; color: #edf5f4; font: 14px/1.45 system-ui, sans-serif; }}
table {{ border-collapse: collapse; width: 100%; min-width: 1500px; }}
th, td {{ border: 1px solid #31424a; padding: .45rem .55rem; vertical-align: top; }}
th {{ color: #9dafb5; background: #172023; text-align: left; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: .75rem; margin: 1rem 0; }}
.box {{ border: 1px solid #31424a; background: #172023; padding: .75rem; }}
.num {{ font-size: 1.35rem; font-weight: 750; }}
.muted {{ color: #9dafb5; }}
.panel {{ overflow-x: auto; margin-top: 1rem; }}
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<div class="grid">
  <div class="box"><div class="num">{summary['ordered_sequence_bytes']}</div><div class="muted">ordered sequence bytes</div></div>
  <div class="box"><div class="num">{summary['compact_sequence_bytes']}</div><div class="muted">compact sequence bytes</div></div>
  <div class="box"><div class="num">{summary['suffix_ordered_bytes']}</div><div class="muted">suffix ordered bytes</div></div>
  <div class="box"><div class="num">{summary['suffix_compact_bytes']}</div><div class="muted">suffix compact bytes</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Sequences</h2>{render_table(sequences, SEQUENCE_FIELDNAMES)}</div>
<div class="panel"><h2>Matches</h2>{render_table(matches, MATCH_FIELDNAMES)}</div>
<script type="application/json" id="stable-length-sequence-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe ordered length sequences for stable .tex alternating segments.")
    parser.add_argument("--replays", type=Path, default=DEFAULT_REPLAYS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--max-matches", type=int, default=20)
    parser.add_argument("--max-span", type=int, default=512)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Micro Stable Length Sequences")
    args = parser.parse_args()

    summary, sequences, matches = build(
        read_rows(args.replays),
        read_rows(args.fixtures),
        max_matches=args.max_matches,
        max_span=args.max_span,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "sequences.csv", SEQUENCE_FIELDNAMES, sequences)
    write_csv(args.output / "matches.csv", MATCH_FIELDNAMES, matches)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, sequences, matches, args.title))

    print(f"Ordered sequence bytes: {summary['ordered_sequence_bytes']}")
    print(f"Compact sequence bytes: {summary['compact_sequence_bytes']}")
    print(f"Suffix ordered bytes: {summary['suffix_ordered_bytes']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
