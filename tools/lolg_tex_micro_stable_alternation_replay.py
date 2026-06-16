#!/usr/bin/env python3
"""Replay alternating stable-source suffixes and score length evidence."""

from __future__ import annotations

import argparse
import csv
import html
import json
from pathlib import Path


DEFAULT_SEGMENTS = Path("output/tex_micro_stable_alternation/segments.csv")
DEFAULT_RUNS = Path("output/tex_micro_stable_source_grammar/runs.csv")
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_OUTPUT = Path("output/tex_micro_stable_alternation_replay")

SUMMARY_FIELDNAMES = [
    "scope",
    "segment_rows",
    "segment_bytes",
    "exact_oracle_rows",
    "exact_oracle_bytes",
    "length_local_hit_rows",
    "length_local_hit_bytes",
    "length_sequence_repeated_rows",
    "length_sequence_repeated_bytes",
    "alternating_suffix_rows",
    "alternating_suffix_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

REPLAY_FIELDNAMES = [
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
    "length_sequence_key",
    "is_suffix",
    "oracle_exact",
    "oracle_output_head_hex",
    "expected_head_hex",
    "length_local_hit_runs",
    "length_local_hit_bytes",
    "missing_length_local_runs",
    "verdict",
]

LENGTH_FIELDNAMES = [
    "rank",
    "segment_rank",
    "run_index",
    "value_hex",
    "length",
    "local_length_offsets",
    "local_value_length_offsets",
    "local_length_value_offsets",
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


def locator_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("archive", ""), row.get("pcx_name", ""), row.get("frontier_id", "")


def source_key(row: dict[str, str]) -> tuple[str, str, str, str]:
    return row.get("archive", ""), row.get("pcx_name", ""), row.get("frontier_id", ""), row.get("source_rank", "")


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
        local_issues: list[str] = []
        fixtures[locator_key(fixture)] = {
            "expected": load_bytes(fixture.get("expected_gap_path", ""), local_issues, "expected"),
            "segment": load_bytes(fixture.get("segment_gap_path", ""), local_issues, "segment"),
        }
        issues.extend(f"{locator_key(fixture)}:{issue}" for issue in local_issues)
    return fixtures, issues


def parse_int_list(text: str) -> list[int]:
    values: list[int] = []
    for part in text.split(";"):
        if part.lstrip("-").isdigit():
            values.append(int(part))
    return values


def parse_hex_values(text: str) -> list[int]:
    values: list[int] = []
    for part in text.split(";"):
        try:
            values.append(int(part, 16))
        except ValueError:
            continue
    return values


def find_offsets(haystack: bytes, needle: bytes, limit: int = 12) -> list[int]:
    offsets: list[int] = []
    if not needle or len(haystack) < len(needle):
        return offsets
    start = 0
    while len(offsets) < limit:
        found = haystack.find(needle, start)
        if found < 0:
            break
        offsets.append(found)
        start = found + 1
    return offsets


def offset_text(offsets: list[int]) -> str:
    return ";".join(str(value) for value in offsets)


def build_run_lookup(run_rows: list[dict[str, str]]) -> dict[tuple[str, str, str, str, str], dict[str, str]]:
    return {
        (*source_key(row), row.get("run_index", "")): row
        for row in run_rows
    }


def replay_alternating(values: list[int], lengths: list[int]) -> bytes:
    if len(values) != 2:
        return b""
    output = bytearray()
    for index, length in enumerate(lengths):
        output.extend([values[index % 2]] * length)
    return bytes(output)


def build(
    segment_rows: list[dict[str, str]],
    run_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    *,
    local_radius: int,
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    fixtures, fixture_issues = load_fixture_bytes(fixture_rows)
    run_lookup = build_run_lookup(run_rows)
    replays: list[dict[str, object]] = []
    length_rows: list[dict[str, object]] = []
    issues = list(fixture_issues)

    for segment in segment_rows:
        values = parse_hex_values(segment.get("values", ""))
        lengths = parse_int_list(segment.get("lengths", ""))
        run_indexes = [str(value) for value in parse_int_list(segment.get("run_indexes", ""))]
        fixture = fixtures.get(locator_key(segment), {})
        expected_all = fixture.get("expected", b"")
        segment_bytes = fixture.get("segment", b"")
        key_base = source_key(segment)
        run_start = run_lookup.get((*key_base, run_indexes[0]), {}) if run_indexes else {}
        run_end = run_lookup.get((*key_base, run_indexes[-1]), {}) if run_indexes else {}
        expected_start = int_value(run_start, "run_start")
        expected_end = int_value(run_end, "run_end")
        expected = expected_all[expected_start:expected_end] if expected_end >= expected_start else b""
        oracle = replay_alternating(values, lengths)
        local_start = max(0, expected_start - local_radius)
        local_end = min(len(segment_bytes), expected_end + local_radius)
        local_segment = segment_bytes[local_start:local_end]
        length_hit_runs = 0
        length_hit_bytes = 0

        segment_rank = int_value(segment, "rank")
        for run_index, length in zip(run_indexes, lengths):
            run = run_lookup.get((*key_base, run_index), {})
            value = int(run.get("run_value_hex", "0x00"), 16) if run.get("run_value_hex") else 0
            length_offsets = find_offsets(local_segment, bytes([length & 0xFF]))
            value_length_offsets = find_offsets(local_segment, bytes([value, length & 0xFF]))
            length_value_offsets = find_offsets(local_segment, bytes([length & 0xFF, value]))
            has_hit = bool(length_offsets or value_length_offsets or length_value_offsets)
            if has_hit:
                length_hit_runs += 1
                length_hit_bytes += length
            length_rows.append(
                {
                    "rank": len(length_rows) + 1,
                    "segment_rank": segment_rank,
                    "run_index": run_index,
                    "value_hex": run.get("run_value_hex", ""),
                    "length": length,
                    "local_length_offsets": offset_text([local_start + value for value in length_offsets]),
                    "local_value_length_offsets": offset_text([local_start + value for value in value_length_offsets]),
                    "local_length_value_offsets": offset_text([local_start + value for value in length_value_offsets]),
                    "verdict": "length_local_evidence" if has_hit else "length_oracle_only",
                }
            )

        exact = bool(expected) and oracle == expected
        replays.append(
            {
                "rank": segment_rank,
                "source_rank": segment.get("source_rank", ""),
                "group_rank": segment.get("group_rank", ""),
                "archive": segment.get("archive", ""),
                "pcx_name": segment.get("pcx_name", ""),
                "frontier_id": segment.get("frontier_id", ""),
                "segment_start_run": segment.get("segment_start_run", ""),
                "segment_end_run": segment.get("segment_end_run", ""),
                "segment_runs": segment.get("segment_runs", ""),
                "segment_bytes": len(expected),
                "values": segment.get("values", ""),
                "lengths": segment.get("lengths", ""),
                "length_sequence_key": "lenseq=" + ",".join(str(value) for value in lengths),
                "is_suffix": segment.get("is_suffix", ""),
                "oracle_exact": 1 if exact else 0,
                "oracle_output_head_hex": oracle[:24].hex(),
                "expected_head_hex": expected[:24].hex(),
                "length_local_hit_runs": length_hit_runs,
                "length_local_hit_bytes": length_hit_bytes,
                "missing_length_local_runs": len(lengths) - length_hit_runs,
                "verdict": "alternation_oracle_exact_review" if exact else "alternation_oracle_failed",
            }
        )

    length_sequences: dict[str, list[dict[str, object]]] = {}
    for row in replays:
        length_sequences.setdefault(str(row["length_sequence_key"]), []).append(row)
    repeated_sequence_rows = [
        row for rows in length_sequences.values() if len(rows) > 1 for row in rows
    ]
    suffix_rows = [row for row in replays if str(row["is_suffix"]) == "1"]
    summary = {
        "scope": "total",
        "segment_rows": len(replays),
        "segment_bytes": sum(int(row["segment_bytes"]) for row in replays),
        "exact_oracle_rows": sum(int(row["oracle_exact"]) for row in replays),
        "exact_oracle_bytes": sum(int(row["segment_bytes"]) for row in replays if int(row["oracle_exact"])),
        "length_local_hit_rows": sum(int(row["length_local_hit_runs"]) for row in replays),
        "length_local_hit_bytes": sum(int(row["length_local_hit_bytes"]) for row in replays),
        "length_sequence_repeated_rows": len(repeated_sequence_rows),
        "length_sequence_repeated_bytes": sum(int(row["segment_bytes"]) for row in repeated_sequence_rows),
        "alternating_suffix_rows": len(suffix_rows),
        "alternating_suffix_bytes": sum(int(row["segment_bytes"]) for row in suffix_rows),
        "promotion_ready_bytes": 0,
        "issue_rows": len(issues),
    }
    return summary, replays, length_rows


def render_table(rows: list[dict[str, object]], fields: list[str], limit: int = 220) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, object],
    replays: list[dict[str, object]],
    lengths: list[dict[str, object]],
    title: str,
) -> str:
    data_json = json.dumps({"summary": summary, "replays": replays, "lengths": lengths}, indent=2, sort_keys=True)
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
  <div class="box"><div class="num">{summary['exact_oracle_bytes']}</div><div class="muted">oracle exact bytes</div></div>
  <div class="box"><div class="num">{summary['length_local_hit_bytes']}</div><div class="muted">length local-hit bytes</div></div>
  <div class="box"><div class="num">{summary['alternating_suffix_bytes']}</div><div class="muted">alternating suffix bytes</div></div>
  <div class="box"><div class="num">{summary['length_sequence_repeated_bytes']}</div><div class="muted">repeated length-sequence bytes</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Replays</h2>{render_table(replays, REPLAY_FIELDNAMES)}</div>
<div class="panel"><h2>Length Evidence</h2>{render_table(lengths, LENGTH_FIELDNAMES)}</div>
<script type="application/json" id="stable-alternation-replay-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay alternating .tex stable-source segments.")
    parser.add_argument("--segments", type=Path, default=DEFAULT_SEGMENTS)
    parser.add_argument("--runs", type=Path, default=DEFAULT_RUNS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--local-radius", type=int, default=512)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Micro Stable Alternation Replay")
    args = parser.parse_args()

    summary, replays, lengths = build(
        read_rows(args.segments),
        read_rows(args.runs),
        read_rows(args.fixtures),
        local_radius=args.local_radius,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "replays.csv", REPLAY_FIELDNAMES, replays)
    write_csv(args.output / "length_evidence.csv", LENGTH_FIELDNAMES, lengths)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, replays, lengths, args.title))

    print(f"Oracle exact bytes: {summary['exact_oracle_bytes']}")
    print(f"Length local-hit bytes: {summary['length_local_hit_bytes']}")
    print(f"Alternating suffix bytes: {summary['alternating_suffix_bytes']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
