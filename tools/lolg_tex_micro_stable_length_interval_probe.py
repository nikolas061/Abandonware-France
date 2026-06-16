#!/usr/bin/env python3
"""Probe interval/state signatures between stable alternation length candidates."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path


DEFAULT_CANDIDATES = Path("output/tex_micro_stable_length_opcode/candidates.csv")
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_OUTPUT = Path("output/tex_micro_stable_length_interval")

MARKER_BYTES = (0xFC, 0xFF, 0x00, 0x20, 0x1F, 0xC0)

SUMMARY_FIELDNAMES = [
    "scope",
    "transition_rows",
    "transition_bytes",
    "compact_transition_rows",
    "compact_transition_bytes",
    "marker_transition_rows",
    "marker_transition_bytes",
    "repeated_signature_rows",
    "repeated_signature_bytes",
    "stable_signature_rows",
    "stable_signature_bytes",
    "conflicted_signature_rows",
    "conflicted_signature_bytes",
    "reused_offset_rows",
    "reused_offset_bytes",
    "conflicted_offset_rows",
    "conflicted_offset_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

TRANSITION_FIELDNAMES = [
    "rank",
    "segment_rank",
    "source_rank",
    "group_rank",
    "archive",
    "pcx_name",
    "frontier_id",
    "from_run_index",
    "to_run_index",
    "from_value_hex",
    "to_value_hex",
    "from_length",
    "to_length",
    "from_offset",
    "to_offset",
    "span",
    "gap_bytes",
    "marker_counts",
    "top_bytes",
    "interval_head_hex",
    "interval_tail_hex",
    "transition_key",
    "signature_key",
    "verdict",
]

SIGNATURE_FIELDNAMES = [
    "rank",
    "signature_key",
    "rows",
    "bytes",
    "transition_keys",
    "spans",
    "offsets",
    "verdict",
]

OFFSET_FIELDNAMES = [
    "rank",
    "pcx_name",
    "frontier_id",
    "offset",
    "rows",
    "bytes",
    "values",
    "lengths",
    "segment_ranks",
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


def int_value(row: dict[str, str] | dict[str, object], field: str) -> int:
    try:
        return int(row.get(field, "") or 0)
    except (TypeError, ValueError):
        return 0


def locator_key(row: dict[str, str] | dict[str, object]) -> tuple[str, str, str]:
    return str(row.get("archive", "")), str(row.get("pcx_name", "")), str(row.get("frontier_id", ""))


def load_bytes(path_text: str, issues: list[str], label: str) -> bytes:
    if not path_text:
        issues.append(f"missing_{label}_path")
        return b""
    try:
        return Path(path_text).read_bytes()
    except OSError as exc:
        issues.append(f"read_{label}_failed:{exc}")
        return b""


def build_fixture_map(fixture_rows: list[dict[str, str]]) -> tuple[dict[tuple[str, str, str], bytes], list[str]]:
    segments: dict[tuple[str, str, str], bytes] = {}
    issues: list[str] = []
    for fixture in fixture_rows:
        local_issues: list[str] = []
        segments[locator_key(fixture)] = load_bytes(fixture.get("segment_gap_path", ""), local_issues, "segment_gap")
        issues.extend(f"{locator_key(fixture)}:{issue}" for issue in local_issues)
    return segments, issues


def marker_counts(data: bytes) -> str:
    counts = Counter(data)
    return ";".join(f"{value:02x}:{counts.get(value, 0)}" for value in MARKER_BYTES)


def top_bytes(data: bytes, limit: int = 5) -> str:
    counts = Counter(data)
    return ";".join(f"{value:02x}:{count}" for value, count in counts.most_common(limit))


def short_hex(data: bytes, *, tail: bool = False, size: int = 12) -> str:
    chunk = data[-size:] if tail else data[:size]
    return chunk.hex()


def compact_signature(interval: bytes, span: int) -> str:
    counts = Counter(interval)
    marker_part = ",".join(str(counts.get(value, 0)) for value in MARKER_BYTES)
    return f"span={span}|markers={marker_part}|head={short_hex(interval, size=4)}|tail={short_hex(interval, tail=True, size=4)}"


def has_marker_counts(text: str) -> bool:
    for part in text.split(";"):
        if ":" not in part:
            continue
        _marker, count = part.split(":", 1)
        try:
            if int(count) > 0:
                return True
        except ValueError:
            continue
    return False


def build(
    candidate_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    *,
    compact_span: int,
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    segments, issues = build_fixture_map(fixture_rows)
    candidates_by_segment: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in candidate_rows:
        candidates_by_segment[row.get("segment_rank", "")].append(row)

    transitions: list[dict[str, object]] = []
    for segment_rank, rows in candidates_by_segment.items():
        rows.sort(key=lambda row: int_value(row, "run_index"))
        for left, right in zip(rows, rows[1:]):
            segment = segments.get(locator_key(left), b"")
            left_offset = int_value(left, "offset")
            right_offset = int_value(right, "offset")
            if right_offset < left_offset:
                issues.append(f"{locator_key(left)}:transition_order_reversed")
                continue
            interval = segment[left_offset + 1 : right_offset]
            span = right_offset - left_offset
            transition_key = (
                f"{left.get('value_hex', '')}/{left.get('length', '')}->"
                f"{right.get('value_hex', '')}/{right.get('length', '')}"
            )
            signature_key = compact_signature(interval, span)
            has_marker = any(value in interval for value in MARKER_BYTES)
            verdict = (
                "length_interval_compact_review"
                if span <= compact_span
                else "length_interval_marker_review"
                if has_marker
                else "length_interval_sparse_review"
            )
            transitions.append(
                {
                    "rank": len(transitions) + 1,
                    "segment_rank": segment_rank,
                    "source_rank": left.get("source_rank", ""),
                    "group_rank": left.get("group_rank", ""),
                    "archive": left.get("archive", ""),
                    "pcx_name": left.get("pcx_name", ""),
                    "frontier_id": left.get("frontier_id", ""),
                    "from_run_index": left.get("run_index", ""),
                    "to_run_index": right.get("run_index", ""),
                    "from_value_hex": left.get("value_hex", ""),
                    "to_value_hex": right.get("value_hex", ""),
                    "from_length": left.get("length", ""),
                    "to_length": right.get("length", ""),
                    "from_offset": left_offset,
                    "to_offset": right_offset,
                    "span": span,
                    "gap_bytes": len(interval),
                    "marker_counts": marker_counts(interval),
                    "top_bytes": top_bytes(interval),
                    "interval_head_hex": short_hex(interval),
                    "interval_tail_hex": short_hex(interval, tail=True),
                    "transition_key": transition_key,
                    "signature_key": signature_key,
                    "verdict": verdict,
                }
            )

    signature_groups: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in transitions:
        signature_groups[str(row["signature_key"])].append(row)
    signature_rows: list[dict[str, object]] = []
    for signature_key, group in signature_groups.items():
        if len(group) < 2:
            continue
        transition_keys = sorted({str(row["transition_key"]) for row in group})
        spans = sorted({str(row["span"]) for row in group})
        signature_rows.append(
            {
                "rank": 0,
                "signature_key": signature_key,
                "rows": len(group),
                "bytes": sum(int_value(row, "from_length") for row in group),
                "transition_keys": ";".join(transition_keys),
                "spans": ";".join(spans),
                "offsets": ";".join(f"{row['from_offset']}->{row['to_offset']}" for row in group),
                "verdict": "length_interval_stable_signature"
                if len(transition_keys) == 1
                else "length_interval_conflicted_signature",
            }
        )
    signature_rows.sort(key=lambda row: (-int_value(row, "bytes"), str(row["signature_key"])))
    for index, row in enumerate(signature_rows, start=1):
        row["rank"] = index

    offset_groups: dict[tuple[str, str, int], list[dict[str, str]]] = defaultdict(list)
    for row in candidate_rows:
        offset_groups[(row.get("pcx_name", ""), row.get("frontier_id", ""), int_value(row, "offset"))].append(row)
    offset_rows: list[dict[str, object]] = []
    for (pcx_name, frontier_id, offset), group in offset_groups.items():
        if len(group) < 2:
            continue
        values = sorted({row.get("value_hex", "") for row in group})
        lengths = sorted({row.get("length", "") for row in group})
        offset_rows.append(
            {
                "rank": 0,
                "pcx_name": pcx_name,
                "frontier_id": frontier_id,
                "offset": offset,
                "rows": len(group),
                "bytes": sum(int_value(row, "length") for row in group),
                "values": ";".join(values),
                "lengths": ";".join(lengths),
                "segment_ranks": ";".join(sorted({row.get("segment_rank", "") for row in group})),
                "verdict": "length_interval_stable_offset"
                if len(values) == 1 and len(lengths) == 1
                else "length_interval_conflicted_offset",
            }
        )
    offset_rows.sort(key=lambda row: (-int_value(row, "bytes"), int_value(row, "offset")))
    for index, row in enumerate(offset_rows, start=1):
        row["rank"] = index

    compact = [row for row in transitions if int_value(row, "span") <= compact_span]
    marker = [row for row in transitions if has_marker_counts(str(row["marker_counts"]))]
    stable_signatures = [row for row in signature_rows if row["verdict"] == "length_interval_stable_signature"]
    conflicted_signatures = [row for row in signature_rows if row["verdict"] == "length_interval_conflicted_signature"]
    conflicted_offsets = [row for row in offset_rows if row["verdict"] == "length_interval_conflicted_offset"]
    summary = {
        "scope": "total",
        "transition_rows": len(transitions),
        "transition_bytes": sum(int_value(row, "from_length") for row in transitions),
        "compact_transition_rows": len(compact),
        "compact_transition_bytes": sum(int_value(row, "from_length") for row in compact),
        "marker_transition_rows": len(marker),
        "marker_transition_bytes": sum(int_value(row, "from_length") for row in marker),
        "repeated_signature_rows": len(signature_rows),
        "repeated_signature_bytes": sum(int_value(row, "bytes") for row in signature_rows),
        "stable_signature_rows": len(stable_signatures),
        "stable_signature_bytes": sum(int_value(row, "bytes") for row in stable_signatures),
        "conflicted_signature_rows": len(conflicted_signatures),
        "conflicted_signature_bytes": sum(int_value(row, "bytes") for row in conflicted_signatures),
        "reused_offset_rows": len(offset_rows),
        "reused_offset_bytes": sum(int_value(row, "bytes") for row in offset_rows),
        "conflicted_offset_rows": len(conflicted_offsets),
        "conflicted_offset_bytes": sum(int_value(row, "bytes") for row in conflicted_offsets),
        "promotion_ready_bytes": 0,
        "issue_rows": len(issues),
    }
    return summary, transitions, signature_rows, offset_rows


def render_table(rows: list[dict[str, object]], fields: list[str], limit: int = 220) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, object],
    transitions: list[dict[str, object]],
    signatures: list[dict[str, object]],
    offsets: list[dict[str, object]],
    title: str,
) -> str:
    data_json = json.dumps(
        {"summary": summary, "transitions": transitions, "signatures": signatures, "offsets": offsets},
        indent=2,
        sort_keys=True,
    )
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body {{ margin: 2rem; background: #111416; color: #edf5f4; font: 14px/1.45 system-ui, sans-serif; }}
table {{ border-collapse: collapse; width: 100%; min-width: 1600px; }}
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
  <div class="box"><div class="num">{summary['transition_bytes']}</div><div class="muted">transition bytes</div></div>
  <div class="box"><div class="num">{summary['compact_transition_bytes']}</div><div class="muted">compact transition bytes</div></div>
  <div class="box"><div class="num">{summary['stable_signature_bytes']}</div><div class="muted">stable signature bytes</div></div>
  <div class="box"><div class="num">{summary['conflicted_offset_bytes']}</div><div class="muted">conflicted offset bytes</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Transitions</h2>{render_table(transitions, TRANSITION_FIELDNAMES)}</div>
<div class="panel"><h2>Repeated Signatures</h2>{render_table(signatures, SIGNATURE_FIELDNAMES)}</div>
<div class="panel"><h2>Reused Offsets</h2>{render_table(offsets, OFFSET_FIELDNAMES)}</div>
<script type="application/json" id="stable-length-interval-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe interval signatures between stable length candidates.")
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--compact-span", type=int, default=12)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Micro Stable Length Interval")
    args = parser.parse_args()

    summary, transitions, signatures, offsets = build(
        read_rows(args.candidates),
        read_rows(args.fixtures),
        compact_span=args.compact_span,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "transitions.csv", TRANSITION_FIELDNAMES, transitions)
    write_csv(args.output / "signature_groups.csv", SIGNATURE_FIELDNAMES, signatures)
    write_csv(args.output / "offset_groups.csv", OFFSET_FIELDNAMES, offsets)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, transitions, signatures, offsets, args.title))

    print(f"Transition bytes: {summary['transition_bytes']}")
    print(f"Compact transition bytes: {summary['compact_transition_bytes']}")
    print(f"Stable signature bytes: {summary['stable_signature_bytes']}")
    print(f"Conflicted offset bytes: {summary['conflicted_offset_bytes']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
