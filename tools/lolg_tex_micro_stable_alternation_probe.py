#!/usr/bin/env python3
"""Probe alternating palette-run motifs in stable micro-token sources."""

from __future__ import annotations

import argparse
import csv
import html
import json
from pathlib import Path


DEFAULT_RUNS = Path("output/tex_micro_stable_source_grammar/runs.csv")
DEFAULT_OUTPUT = Path("output/tex_micro_stable_alternation")

SUMMARY_FIELDNAMES = [
    "scope",
    "source_rows",
    "run_rows",
    "run_bytes",
    "alternating_segment_rows",
    "alternating_segment_bytes",
    "longest_alternating_runs",
    "longest_alternating_bytes",
    "longest_source_rank",
    "longest_values",
    "suffix_alternating_rows",
    "suffix_alternating_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

SEGMENT_FIELDNAMES = [
    "rank",
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
    "run_indexes",
    "verdict",
]

SOURCE_FIELDNAMES = [
    "rank",
    "source_rank",
    "group_rank",
    "archive",
    "pcx_name",
    "frontier_id",
    "runs",
    "bytes",
    "unique_values",
    "longest_segment_runs",
    "longest_segment_bytes",
    "longest_segment_values",
    "suffix_segment_runs",
    "suffix_segment_bytes",
    "suffix_segment_values",
    "verdict",
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


def source_key(row: dict[str, str]) -> tuple[str, str, str, str]:
    return row.get("archive", ""), row.get("pcx_name", ""), row.get("frontier_id", ""), row.get("source_rank", "")


def is_alternating(rows: list[dict[str, str]]) -> bool:
    values = [row.get("run_value_hex", "") for row in rows]
    if len(values) < 2 or len(set(values)) != 2:
        return False
    return all(values[index] != values[index - 1] for index in range(1, len(values)))


def find_segments(rows: list[dict[str, str]], min_runs: int) -> list[list[dict[str, str]]]:
    segments: list[list[dict[str, str]]] = []
    for start in range(len(rows)):
        for end in range(start + min_runs, len(rows) + 1):
            segment = rows[start:end]
            if is_alternating(segment):
                segments.append(segment)
    maximal: list[list[dict[str, str]]] = []
    for segment in segments:
        start = int_value(segment[0], "run_index")
        end = int_value(segment[-1], "run_index")
        contained = False
        for other in segments:
            if other is segment:
                continue
            other_start = int_value(other[0], "run_index")
            other_end = int_value(other[-1], "run_index")
            if other_start <= start and end <= other_end and len(other) > len(segment):
                contained = True
                break
        if not contained:
            maximal.append(segment)
    maximal.sort(key=lambda rows: (-sum(int_value(row, "run_length") for row in rows), int_value(rows[0], "run_index")))
    return maximal


def segment_row(segment: list[dict[str, str]], source_runs: list[dict[str, str]], rank: int) -> dict[str, object]:
    values = sorted({row.get("run_value_hex", "") for row in segment})
    lengths = [int_value(row, "run_length") for row in segment]
    is_suffix = int_value(segment[-1], "run_index") == int_value(source_runs[-1], "run_index")
    return {
        "rank": rank,
        "source_rank": segment[0].get("source_rank", ""),
        "group_rank": segment[0].get("group_rank", ""),
        "archive": segment[0].get("archive", ""),
        "pcx_name": segment[0].get("pcx_name", ""),
        "frontier_id": segment[0].get("frontier_id", ""),
        "segment_start_run": segment[0].get("run_index", ""),
        "segment_end_run": segment[-1].get("run_index", ""),
        "segment_runs": len(segment),
        "segment_bytes": sum(lengths),
        "values": ";".join(values),
        "lengths": ";".join(str(length) for length in lengths),
        "is_suffix": 1 if is_suffix else 0,
        "run_indexes": ";".join(row.get("run_index", "") for row in segment),
        "verdict": "alternating_suffix_review" if is_suffix else "alternating_segment_review",
    }


def build(run_rows: list[dict[str, str]], min_runs: int) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    by_source: dict[tuple[str, str, str, str], list[dict[str, str]]] = {}
    for row in run_rows:
        by_source.setdefault(source_key(row), []).append(row)

    source_outputs: list[dict[str, object]] = []
    segment_outputs: list[dict[str, object]] = []
    rank = 1
    for rows in by_source.values():
        rows.sort(key=lambda row: int_value(row, "run_index"))
        segments = find_segments(rows, min_runs)
        for segment in segments:
            segment_outputs.append(segment_row(segment, rows, rank))
            rank += 1
        longest = segments[0] if segments else []
        suffixes = [segment for segment in segments if int_value(segment[-1], "run_index") == int_value(rows[-1], "run_index")]
        suffix = suffixes[0] if suffixes else []
        source_outputs.append(
            {
                "rank": len(source_outputs) + 1,
                "source_rank": rows[0].get("source_rank", ""),
                "group_rank": rows[0].get("group_rank", ""),
                "archive": rows[0].get("archive", ""),
                "pcx_name": rows[0].get("pcx_name", ""),
                "frontier_id": rows[0].get("frontier_id", ""),
                "runs": len(rows),
                "bytes": sum(int_value(row, "run_length") for row in rows),
                "unique_values": ";".join(sorted({row.get("run_value_hex", "") for row in rows})),
                "longest_segment_runs": len(longest),
                "longest_segment_bytes": sum(int_value(row, "run_length") for row in longest),
                "longest_segment_values": ";".join(sorted({row.get("run_value_hex", "") for row in longest})),
                "suffix_segment_runs": len(suffix),
                "suffix_segment_bytes": sum(int_value(row, "run_length") for row in suffix),
                "suffix_segment_values": ";".join(sorted({row.get("run_value_hex", "") for row in suffix})),
                "verdict": "alternating_suffix_review" if suffix else "alternating_segment_review" if longest else "no_alternation",
            }
        )

    longest_segment = max(segment_outputs, key=lambda row: int(row["segment_bytes"]), default={})
    suffix_segments = [row for row in segment_outputs if int(row["is_suffix"])]
    summary = {
        "scope": "total",
        "source_rows": len(source_outputs),
        "run_rows": len(run_rows),
        "run_bytes": sum(int_value(row, "run_length") for row in run_rows),
        "alternating_segment_rows": len(segment_outputs),
        "alternating_segment_bytes": sum(int(row["segment_bytes"]) for row in segment_outputs),
        "longest_alternating_runs": longest_segment.get("segment_runs", 0),
        "longest_alternating_bytes": longest_segment.get("segment_bytes", 0),
        "longest_source_rank": longest_segment.get("source_rank", ""),
        "longest_values": longest_segment.get("values", ""),
        "suffix_alternating_rows": len(suffix_segments),
        "suffix_alternating_bytes": sum(int(row["segment_bytes"]) for row in suffix_segments),
        "promotion_ready_bytes": 0,
        "issue_rows": 0,
    }
    return summary, source_outputs, segment_outputs


def render_table(rows: list[dict[str, object]], fields: list[str], limit: int = 220) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, object],
    sources: list[dict[str, object]],
    segments: list[dict[str, object]],
    title: str,
) -> str:
    data_json = json.dumps({"summary": summary, "sources": sources, "segments": segments}, indent=2, sort_keys=True)
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
  <div class="box"><div class="num">{summary['alternating_segment_rows']}</div><div class="muted">alternating segments</div></div>
  <div class="box"><div class="num">{summary['longest_alternating_bytes']}</div><div class="muted">longest alternating bytes</div></div>
  <div class="box"><div class="num">{summary['suffix_alternating_bytes']}</div><div class="muted">suffix alternating bytes</div></div>
  <div class="box"><div class="num">{summary['longest_values']}</div><div class="muted">longest values</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Sources</h2>{render_table(sources, SOURCE_FIELDNAMES)}</div>
<div class="panel"><h2>Segments</h2>{render_table(segments, SEGMENT_FIELDNAMES)}</div>
<script type="application/json" id="stable-alternation-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe alternating palette-run motifs in stable .tex sources.")
    parser.add_argument("--runs", type=Path, default=DEFAULT_RUNS)
    parser.add_argument("--min-runs", type=int, default=4)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Micro Stable Alternation")
    args = parser.parse_args()

    summary, sources, segments = build(read_rows(args.runs), args.min_runs)
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "sources.csv", SOURCE_FIELDNAMES, sources)
    write_csv(args.output / "segments.csv", SEGMENT_FIELDNAMES, segments)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, sources, segments, args.title))

    print(f"Alternating segments: {summary['alternating_segment_rows']}")
    print(f"Longest alternating bytes: {summary['longest_alternating_bytes']}")
    print(f"Suffix alternating bytes: {summary['suffix_alternating_bytes']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
