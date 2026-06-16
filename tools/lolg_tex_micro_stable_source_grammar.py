#!/usr/bin/env python3
"""Characterize run grammar for encoded stable micro-token sources."""

from __future__ import annotations

import argparse
import csv
import html
import json
from pathlib import Path


DEFAULT_SOURCES = Path("output/tex_micro_stable_sources/sources.csv")
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_OUTPUT = Path("output/tex_micro_stable_source_grammar")

SUMMARY_FIELDNAMES = [
    "scope",
    "source_rows",
    "source_bytes",
    "run_rows",
    "run_bytes",
    "local_value_hit_rows",
    "local_value_hit_bytes",
    "global_value_hit_rows",
    "global_value_hit_bytes",
    "local_length_hit_rows",
    "local_length_hit_bytes",
    "local_len_value_pair_rows",
    "local_len_value_pair_bytes",
    "local_value_len_pair_rows",
    "local_value_len_pair_bytes",
    "local_repeated_literal_rows",
    "local_repeated_literal_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

RUN_FIELDNAMES = [
    "rank",
    "source_rank",
    "group_rank",
    "archive",
    "pcx_name",
    "frontier_id",
    "source_start",
    "source_end",
    "run_index",
    "run_value_hex",
    "run_length",
    "run_start",
    "run_end",
    "segment_local_start",
    "segment_local_end",
    "local_value_offsets",
    "global_value_offsets",
    "local_length_offsets",
    "local_len_value_pair_offsets",
    "local_value_len_pair_offsets",
    "local_repeated_literal_offsets",
    "verdict",
]

SOURCE_FIELDNAMES = [
    "rank",
    "group_rank",
    "archive",
    "pcx_name",
    "frontier_id",
    "start",
    "end",
    "length",
    "runs",
    "unique_values",
    "local_value_hit_runs",
    "local_pair_hit_runs",
    "local_repeated_literal_runs",
    "verdict",
    "issues",
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


def load_fixture_bytes(fixture_rows: list[dict[str, str]]) -> tuple[dict[tuple[str, str, str], dict[str, bytes]], list[str]]:
    fixtures: dict[tuple[str, str, str], dict[str, bytes]] = {}
    issues: list[str] = []
    for fixture in fixture_rows:
        key = locator_key(fixture)
        local_issues: list[str] = []
        fixtures[key] = {
            "expected": load_bytes(fixture.get("expected_gap_path", ""), local_issues, "expected"),
            "segment": load_bytes(fixture.get("segment_gap_path", ""), local_issues, "segment"),
        }
        issues.extend(f"{key}:{issue}" for issue in local_issues)
    return fixtures, issues


def runs(data: bytes) -> list[tuple[int, int, int, int]]:
    if not data:
        return []
    output: list[tuple[int, int, int, int]] = []
    start = 0
    value = data[0]
    for index, current in enumerate(data[1:], start=1):
        if current == value:
            continue
        output.append((value, index - start, start, index))
        start = index
        value = current
    output.append((value, len(data) - start, start, len(data)))
    return output


def find_offsets(haystack: bytes, needle: bytes, *, limit: int = 12) -> list[int]:
    if not needle or len(haystack) < len(needle):
        return []
    offsets: list[int] = []
    start = 0
    while len(offsets) < limit:
        found = haystack.find(needle, start)
        if found < 0:
            break
        offsets.append(found)
        start = found + 1
    return offsets


def offset_text(offsets: list[int], base: int = 0) -> str:
    return ";".join(str(base + offset) for offset in offsets)


def build(
    source_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    *,
    local_radius: int,
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    fixtures, fixture_issues = load_fixture_bytes(fixture_rows)
    run_rows: list[dict[str, object]] = []
    source_outputs: list[dict[str, object]] = []
    issues: list[str] = list(fixture_issues)

    for source in source_rows:
        local_issues = [issue for issue in source.get("issues", "").split(";") if issue]
        fixture = fixtures.get(locator_key(source), {})
        expected_all = fixture.get("expected", b"")
        segment = fixture.get("segment", b"")
        start = int_value(source, "start")
        end = int_value(source, "end")
        expected = expected_all[start:end]
        if not expected:
            local_issues.append("missing_expected_chunk")
            issues.extend(local_issues)
            continue

        local_start = max(0, start - local_radius)
        local_end = min(len(segment), end + local_radius)
        local_segment = segment[local_start:local_end]
        source_run_rows: list[dict[str, object]] = []

        for index, (value, length, run_start, run_end) in enumerate(runs(expected), start=1):
            value_needle = bytes([value])
            length_needle = bytes([length & 0xFF])
            len_value = bytes([length & 0xFF, value])
            value_len = bytes([value, length & 0xFF])
            repeated = bytes([value]) * length
            local_value_offsets = find_offsets(local_segment, value_needle)
            global_value_offsets = find_offsets(segment, value_needle)
            local_length_offsets = find_offsets(local_segment, length_needle)
            local_len_value_offsets = find_offsets(local_segment, len_value)
            local_value_len_offsets = find_offsets(local_segment, value_len)
            local_repeated_offsets = find_offsets(local_segment, repeated)
            verdict = "encoded_run_review"
            if local_repeated_offsets:
                verdict = "literal_run_present"
            elif local_len_value_offsets or local_value_len_offsets:
                verdict = "length_value_pair_present"
            elif local_value_offsets:
                verdict = "value_literal_present"

            row = {
                "rank": 0,
                "source_rank": source.get("rank", ""),
                "group_rank": source.get("group_rank", ""),
                "archive": source.get("archive", ""),
                "pcx_name": source.get("pcx_name", ""),
                "frontier_id": source.get("frontier_id", ""),
                "source_start": start,
                "source_end": end,
                "run_index": index,
                "run_value_hex": f"0x{value:02x}",
                "run_length": length,
                "run_start": start + run_start,
                "run_end": start + run_end,
                "segment_local_start": local_start,
                "segment_local_end": local_end,
                "local_value_offsets": offset_text(local_value_offsets, local_start),
                "global_value_offsets": offset_text(global_value_offsets),
                "local_length_offsets": offset_text(local_length_offsets, local_start),
                "local_len_value_pair_offsets": offset_text(local_len_value_offsets, local_start),
                "local_value_len_pair_offsets": offset_text(local_value_len_offsets, local_start),
                "local_repeated_literal_offsets": offset_text(local_repeated_offsets, local_start),
                "verdict": verdict,
            }
            run_rows.append(row)
            source_run_rows.append(row)

        source_outputs.append(
            {
                "rank": source.get("rank", ""),
                "group_rank": source.get("group_rank", ""),
                "archive": source.get("archive", ""),
                "pcx_name": source.get("pcx_name", ""),
                "frontier_id": source.get("frontier_id", ""),
                "start": start,
                "end": end,
                "length": len(expected),
                "runs": len(source_run_rows),
                "unique_values": ";".join(f"0x{value:02x}" for value in sorted(set(expected))),
                "local_value_hit_runs": sum(1 for row in source_run_rows if row["local_value_offsets"]),
                "local_pair_hit_runs": sum(
                    1
                    for row in source_run_rows
                    if row["local_len_value_pair_offsets"] or row["local_value_len_pair_offsets"]
                ),
                "local_repeated_literal_runs": sum(1 for row in source_run_rows if row["local_repeated_literal_offsets"]),
                "verdict": "literal_source_review"
                if any(row["local_repeated_literal_offsets"] for row in source_run_rows)
                else "encoded_source_review",
                "issues": ";".join(local_issues),
            }
        )
        issues.extend(local_issues)

    for index, row in enumerate(run_rows, start=1):
        row["rank"] = index

    def hit_bytes(field: str) -> int:
        return sum(int(row["run_length"]) for row in run_rows if row[field])

    summary = {
        "scope": "total",
        "source_rows": len(source_outputs),
        "source_bytes": sum(int(row["length"]) for row in source_outputs),
        "run_rows": len(run_rows),
        "run_bytes": sum(int(row["run_length"]) for row in run_rows),
        "local_value_hit_rows": sum(1 for row in run_rows if row["local_value_offsets"]),
        "local_value_hit_bytes": hit_bytes("local_value_offsets"),
        "global_value_hit_rows": sum(1 for row in run_rows if row["global_value_offsets"]),
        "global_value_hit_bytes": hit_bytes("global_value_offsets"),
        "local_length_hit_rows": sum(1 for row in run_rows if row["local_length_offsets"]),
        "local_length_hit_bytes": hit_bytes("local_length_offsets"),
        "local_len_value_pair_rows": sum(1 for row in run_rows if row["local_len_value_pair_offsets"]),
        "local_len_value_pair_bytes": hit_bytes("local_len_value_pair_offsets"),
        "local_value_len_pair_rows": sum(1 for row in run_rows if row["local_value_len_pair_offsets"]),
        "local_value_len_pair_bytes": hit_bytes("local_value_len_pair_offsets"),
        "local_repeated_literal_rows": sum(1 for row in run_rows if row["local_repeated_literal_offsets"]),
        "local_repeated_literal_bytes": hit_bytes("local_repeated_literal_offsets"),
        "promotion_ready_bytes": 0,
        "issue_rows": len(issues),
    }
    return summary, source_outputs, run_rows


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
    runs_out: list[dict[str, object]],
    title: str,
) -> str:
    data_json = json.dumps({"summary": summary, "sources": sources, "runs": runs_out}, indent=2, sort_keys=True)
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body {{ margin: 2rem; background: #111416; color: #edf5f4; font: 14px/1.45 system-ui, sans-serif; }}
table {{ border-collapse: collapse; width: 100%; min-width: 1800px; }}
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
  <div class="box"><div class="num">{summary['run_rows']}</div><div class="muted">run rows</div></div>
  <div class="box"><div class="num">{summary['local_value_hit_bytes']}</div><div class="muted">local value-hit bytes</div></div>
  <div class="box"><div class="num">{summary['local_len_value_pair_bytes']}</div><div class="muted">local len/value bytes</div></div>
  <div class="box"><div class="num">{summary['local_repeated_literal_bytes']}</div><div class="muted">local literal-run bytes</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Sources</h2>{render_table(sources, SOURCE_FIELDNAMES)}</div>
<div class="panel"><h2>Runs</h2>{render_table(runs_out, RUN_FIELDNAMES)}</div>
<script type="application/json" id="stable-source-grammar-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Characterize stable .tex source run grammar.")
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--local-radius", type=int, default=512)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Micro Stable Source Grammar")
    args = parser.parse_args()

    summary, sources, runs_out = build(read_rows(args.sources), read_rows(args.fixtures), local_radius=args.local_radius)
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "sources.csv", SOURCE_FIELDNAMES, sources)
    write_csv(args.output / "runs.csv", RUN_FIELDNAMES, runs_out)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, sources, runs_out, args.title))

    print(f"Run rows: {summary['run_rows']}")
    print(f"Local value-hit bytes: {summary['local_value_hit_bytes']}")
    print(f"Local len/value bytes: {summary['local_len_value_pair_bytes']}")
    print(f"Local literal-run bytes: {summary['local_repeated_literal_bytes']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
