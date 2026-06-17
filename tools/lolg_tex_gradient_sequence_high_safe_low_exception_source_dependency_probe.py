#!/usr/bin/env python3
"""Probe source-profile dependencies for high-safe low exceptions."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gradient_sequence_high_safe_low_exception_probe import (
    SLOT_FIELDNAMES as LOW_EXCEPTION_SLOT_FIELDNAMES,
)
from lolg_tex_micro_mixed_value_payload_state_opcode_probe import int_value, ratio, write_csv


DEFAULT_SLOTS = Path("output/tex_gradient_sequence_high_safe_low_exception/slots.csv")
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_REPLAY_FIXTURES = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_formula_replay/fixtures.csv"
)
DEFAULT_OUTPUT = Path("output/tex_gradient_sequence_high_safe_low_exception_source_dependency")

BUCKET_ORDER = ("lo", "mid", "hi")

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "slots",
    "slot_rows",
    "exception_slots",
    "exception_targets",
    "decoded_formula_slots",
    "segment_gap_slots",
    "source_available_slots",
    "source_known_slots",
    "source_manifest_slots",
    "source_unknown_slots",
    "source_in_highsafe_slots",
    "source_outside_highsafe_slots",
    "source_unknown_in_highsafe_slots",
    "source_unknown_outside_highsafe_slots",
    "exception_source_unknown_slots",
    "exception_source_unknown_in_highsafe_slots",
    "exception_source_unknown_outside_highsafe_slots",
    "source_same_low_slots",
    "source_same_bucket_slots",
    "dependency_edges",
    "unknown_dependency_edges",
    "top_dependency_edge",
    "top_dependency_edge_slots",
    "top_unknown_dependency_edge",
    "top_unknown_dependency_edge_slots",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

SLOT_FIELDNAMES = [
    *LOW_EXCEPTION_SLOT_FIELDNAMES,
    "source_actual_offset",
    "source_availability",
    "source_location",
    "source_expected_byte",
    "source_decoded_byte",
    "source_slot_rank",
    "source_slot_frontier_id",
    "source_slot_start",
    "source_slot_target_low",
    "source_slot_low_bucket",
    "source_low_delta",
    "source_same_low",
    "source_same_bucket",
    "source_dependency_verdict",
]

EDGE_FIELDNAMES = [
    "rank",
    "edge_key",
    "target_frontier_id",
    "target_start",
    "source_frontier_id",
    "source_start",
    "slots",
    "exception_slots",
    "source_known_slots",
    "source_unknown_slots",
    "same_low_slots",
    "same_bucket_slots",
    "low_delta_histogram",
    "verdict",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def read_bytes(path_text: str, issues: list[str], label: str) -> bytes:
    if not path_text:
        issues.append(f"missing_{label}_path")
        return b""
    try:
        return Path(path_text).read_bytes()
    except OSError as exc:
        issues.append(f"read_{label}_failed:{exc}")
        return b""


def fixture_key(row: dict[str, str] | dict[str, object]) -> tuple[str, str, str]:
    return (
        str(row.get("archive", "")),
        str(row.get("pcx_name", "")),
        str(row.get("frontier_id", "")),
    )


def slot_abs_key(row: dict[str, str] | dict[str, object]) -> tuple[str, str, int]:
    return (
        str(row.get("archive", "")),
        str(row.get("pcx_name", "")),
        int_value(row, "target_offset", -1),
    )


def source_actual_offset(row: dict[str, str] | dict[str, object]) -> int:
    return int_value(row, "source_profile_offset", -1) + int_value(row, "relative_offset", 0)


def byte_text(buffer: bytes, offset: int) -> str:
    if 0 <= offset < len(buffer):
        return f"{buffer[offset]:02x}"
    return ""


def majority_by_bucket(rows: list[dict[str, str]]) -> dict[str, str]:
    output: dict[str, str] = {}
    for bucket in BUCKET_ORDER:
        counts = Counter(row.get("target_low", "") for row in rows if row.get("low_bucket", "") == bucket)
        output[bucket] = counts.most_common(1)[0][0] if counts else ""
    return output


def exception_target_keys(rows: list[dict[str, str]], majority: dict[str, str]) -> set[str]:
    targets: set[str] = set()
    for row in rows:
        bucket = row.get("low_bucket", "")
        low = row.get("target_low", "")
        if bucket and low and low != majority.get(bucket, ""):
            targets.add(f"{bucket}:{low}")
    return targets


def load_fixture_buffers(
    fixture_rows: list[dict[str, str]],
    replay_rows: list[dict[str, str]],
) -> tuple[dict[tuple[str, str, str], dict[str, bytes]], list[str]]:
    manifests = {fixture_key(row): row for row in fixture_rows}
    replays = {fixture_key(row): row for row in replay_rows}
    keys = set(manifests) | set(replays)
    issues: list[str] = []
    buffers: dict[tuple[str, str, str], dict[str, bytes]] = {}
    for key in sorted(keys):
        manifest = manifests.get(key, {})
        replay = replays.get(key, {})
        local_issues: list[str] = []
        buffers[key] = {
            "expected": read_bytes(manifest.get("expected_gap_path", ""), local_issues, "expected"),
            "decoded": read_bytes(replay.get("decoded_path", ""), local_issues, "decoded"),
            "known_mask": read_bytes(replay.get("known_mask_path", ""), local_issues, "known_mask"),
            "segment_gap": read_bytes(manifest.get("segment_gap_path", ""), local_issues, "segment_gap"),
        }
        issues.extend(f"{'|'.join(key)}:{issue}" for issue in local_issues)
    return buffers, issues


def source_state(
    row: dict[str, str],
    source_slot: dict[str, str] | None,
    buffers: dict[tuple[str, str, str], dict[str, bytes]],
) -> dict[str, str]:
    pool = row.get("pool", "")
    actual_offset = source_actual_offset(row)
    key = fixture_key(row)
    buffer = buffers.get(key, {})
    source_expected = ""
    source_decoded = ""
    source_availability = "missing_source"
    if pool == "decoded_formula":
        expected = buffer.get("expected", b"")
        decoded = buffer.get("decoded", b"")
        known_mask = buffer.get("known_mask", b"")
        source_expected = byte_text(expected, actual_offset)
        source_decoded = byte_text(decoded, actual_offset)
        if 0 <= actual_offset < len(known_mask) and known_mask[actual_offset]:
            source_availability = "known_source"
        elif 0 <= actual_offset < len(known_mask):
            source_availability = "unknown_source"
        else:
            source_availability = "out_of_range_source"
    elif pool == "segment_gap":
        segment_gap = buffer.get("segment_gap", b"")
        source_expected = byte_text(segment_gap, actual_offset)
        source_decoded = source_expected
        source_availability = "manifest_source" if source_expected else "out_of_range_source"

    source_location = "in_highsafe" if source_slot else "outside_highsafe"
    source_low_delta = ""
    source_same_low = ""
    source_same_bucket = ""
    if source_slot:
        source_low = source_slot.get("target_low", "")
        target_low = row.get("target_low", "")
        if source_low and target_low:
            source_low_delta = str((int(target_low, 16) - int(source_low, 16)) & 0x0F)
            source_same_low = "1" if source_low == target_low else "0"
        source_same_bucket = "1" if source_slot.get("low_bucket", "") == row.get("low_bucket", "") else "0"

    if source_availability in {"known_source", "manifest_source"}:
        verdict = "source_available"
    elif source_slot:
        verdict = "depends_on_highsafe_source"
    elif source_availability == "unknown_source":
        verdict = "depends_on_external_unknown_source"
    else:
        verdict = "source_unavailable"

    return {
        "source_actual_offset": str(actual_offset),
        "source_availability": source_availability,
        "source_location": source_location,
        "source_expected_byte": source_expected,
        "source_decoded_byte": source_decoded,
        "source_slot_rank": source_slot.get("rank", "") if source_slot else "",
        "source_slot_frontier_id": source_slot.get("frontier_id", "") if source_slot else "",
        "source_slot_start": source_slot.get("start", "") if source_slot else "",
        "source_slot_target_low": source_slot.get("target_low", "") if source_slot else "",
        "source_slot_low_bucket": source_slot.get("low_bucket", "") if source_slot else "",
        "source_low_delta": source_low_delta,
        "source_same_low": source_same_low,
        "source_same_bucket": source_same_bucket,
        "source_dependency_verdict": verdict,
    }


def build_edges(rows: list[dict[str, object]], exception_targets: set[str]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, str, str], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        if row.get("source_location") != "in_highsafe":
            continue
        key = (
            str(row.get("frontier_id", "")),
            str(row.get("start", "")),
            str(row.get("source_slot_frontier_id", "")),
            str(row.get("source_slot_start", "")),
        )
        grouped[key].append(row)

    output: list[dict[str, object]] = []
    for (target_frontier, target_start, source_frontier, source_start), members in grouped.items():
        low_deltas = Counter(str(row.get("source_low_delta", "")) for row in members if row.get("source_low_delta", ""))
        source_unknown = sum(1 for row in members if row.get("source_availability") == "unknown_source")
        target_exception_slots = sum(
            1
            for row in members
            if f"{row.get('low_bucket', '')}:{row.get('target_low', '')}" in exception_targets
        )
        output.append(
            {
                "rank": 0,
                "edge_key": f"{target_frontier}|{target_start}->{source_frontier}|{source_start}",
                "target_frontier_id": target_frontier,
                "target_start": target_start,
                "source_frontier_id": source_frontier,
                "source_start": source_start,
                "slots": len(members),
                "exception_slots": target_exception_slots,
                "source_known_slots": sum(1 for row in members if row.get("source_availability") == "known_source"),
                "source_unknown_slots": source_unknown,
                "same_low_slots": sum(int_value(row, "source_same_low") for row in members),
                "same_bucket_slots": sum(int_value(row, "source_same_bucket") for row in members),
                "low_delta_histogram": "|".join(
                    f"{delta}:{count}" for delta, count in sorted(low_deltas.items(), key=lambda item: item[0])
                ),
                "verdict": "unknown_highsafe_dependency" if source_unknown else "available_highsafe_dependency",
            }
        )
    output.sort(
        key=lambda row: (
            -int_value(row, "source_unknown_slots"),
            -int_value(row, "slots"),
            str(row["edge_key"]),
        )
    )
    for index, row in enumerate(output, start=1):
        row["rank"] = index
    return output


def build_summary(
    rows: list[dict[str, object]],
    edges: list[dict[str, object]],
    exception_targets: set[str],
    issue_rows: int,
) -> dict[str, object]:
    exception_slots = sum(
        1 for row in rows if f"{row.get('low_bucket', '')}:{row.get('target_low', '')}" in exception_targets
    )
    source_known = sum(1 for row in rows if row.get("source_availability") == "known_source")
    source_manifest = sum(1 for row in rows if row.get("source_availability") == "manifest_source")
    source_unknown = sum(1 for row in rows if row.get("source_availability") == "unknown_source")
    source_unknown_in_highsafe = sum(
        1
        for row in rows
        if row.get("source_availability") == "unknown_source"
        and row.get("source_location") == "in_highsafe"
    )
    source_unknown_outside = sum(
        1
        for row in rows
        if row.get("source_availability") == "unknown_source"
        and row.get("source_location") == "outside_highsafe"
    )
    exception_unknown = [
        row
        for row in rows
        if f"{row.get('low_bucket', '')}:{row.get('target_low', '')}" in exception_targets
        and row.get("source_availability") == "unknown_source"
    ]
    unknown_edges = [row for row in edges if int_value(row, "source_unknown_slots") > 0]
    top_edge = edges[0] if edges else {}
    top_unknown_edge = unknown_edges[0] if unknown_edges else {}
    return {
        "scope": "total",
        "candidate_mode": "high_safe_low_exception_source_dependency",
        "slots": len(rows),
        "slot_rows": len({row.get("row_id", "") for row in rows}),
        "exception_slots": exception_slots,
        "exception_targets": "|".join(
            key
            for bucket in BUCKET_ORDER
            for key in sorted(exception_targets)
            if key.startswith(f"{bucket}:")
        ),
        "decoded_formula_slots": sum(1 for row in rows if row.get("pool") == "decoded_formula"),
        "segment_gap_slots": sum(1 for row in rows if row.get("pool") == "segment_gap"),
        "source_available_slots": source_known + source_manifest,
        "source_known_slots": source_known,
        "source_manifest_slots": source_manifest,
        "source_unknown_slots": source_unknown,
        "source_in_highsafe_slots": sum(1 for row in rows if row.get("source_location") == "in_highsafe"),
        "source_outside_highsafe_slots": sum(1 for row in rows if row.get("source_location") == "outside_highsafe"),
        "source_unknown_in_highsafe_slots": source_unknown_in_highsafe,
        "source_unknown_outside_highsafe_slots": source_unknown_outside,
        "exception_source_unknown_slots": len(exception_unknown),
        "exception_source_unknown_in_highsafe_slots": sum(
            1 for row in exception_unknown if row.get("source_location") == "in_highsafe"
        ),
        "exception_source_unknown_outside_highsafe_slots": sum(
            1 for row in exception_unknown if row.get("source_location") == "outside_highsafe"
        ),
        "source_same_low_slots": sum(int_value(row, "source_same_low") for row in rows),
        "source_same_bucket_slots": sum(int_value(row, "source_same_bucket") for row in rows),
        "dependency_edges": len(edges),
        "unknown_dependency_edges": len(unknown_edges),
        "top_dependency_edge": top_edge.get("edge_key", ""),
        "top_dependency_edge_slots": top_edge.get("slots", 0),
        "top_unknown_dependency_edge": top_unknown_edge.get("edge_key", ""),
        "top_unknown_dependency_edge_slots": top_unknown_edge.get("source_unknown_slots", 0),
        "promotion_candidate_bytes": 0,
        "promotion_ready_bytes": 0,
        "issue_rows": issue_rows,
    }


def build(
    slot_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    replay_rows: list[dict[str, str]],
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    buffers, issues = load_fixture_buffers(fixture_rows, replay_rows)
    majority = majority_by_bucket(slot_rows)
    exceptions = exception_target_keys(slot_rows, majority)
    by_source_abs = {slot_abs_key(row): row for row in slot_rows}
    rows: list[dict[str, object]] = []
    for slot in slot_rows:
        actual_offset = source_actual_offset(slot)
        source_slot = None
        if slot.get("pool") == "decoded_formula":
            source_slot = by_source_abs.get((slot.get("archive", ""), slot.get("pcx_name", ""), actual_offset))
        rows.append({**slot, **source_state(slot, source_slot, buffers)})
    edges = build_edges(rows, exceptions)
    summary = build_summary(rows, edges, exceptions, len(issues))
    return summary, rows, edges


def render_table(rows: list[dict[str, object]], fields: list[str], limit: int = 220) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, object],
    rows: list[dict[str, object]],
    edges: list[dict[str, object]],
    title: str,
) -> str:
    data_json = json.dumps({"summary": summary, "slots": rows, "edges": edges}, indent=2, sort_keys=True)
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body {{ margin: 2rem; background: #101214; color: #edf5f4; font: 14px/1.45 system-ui, sans-serif; }}
table {{ border-collapse: collapse; width: 100%; min-width: 2300px; }}
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
  <div class="box"><div class="num">{summary['slots']}</div><div class="muted">slots</div></div>
  <div class="box"><div class="num">{summary['source_available_slots']}</div><div class="muted">source available slots</div></div>
  <div class="box"><div class="num">{summary['source_unknown_in_highsafe_slots']}</div><div class="muted">unknown in high-safe</div></div>
  <div class="box"><div class="num">{summary['source_unknown_outside_highsafe_slots']}</div><div class="muted">unknown outside</div></div>
  <div class="box"><div class="num">{summary['top_unknown_dependency_edge']}</div><div class="muted">top unknown edge</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Edges</h2>{render_table(edges, EDGE_FIELDNAMES)}</div>
<div class="panel"><h2>Slots</h2>{render_table(rows, SLOT_FIELDNAMES)}</div>
<script type="application/json" id="gradient-sequence-high-safe-low-exception-source-dependency-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe source dependencies for low exceptions.")
    parser.add_argument("--slots", type=Path, default=DEFAULT_SLOTS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--replay-fixtures", type=Path, default=DEFAULT_REPLAY_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Gradient Sequence High-Safe Low Exception Source-Dependency Probe",
    )
    args = parser.parse_args()

    summary, rows, edges = build(
        read_csv(args.slots),
        read_csv(args.fixtures),
        read_csv(args.replay_fixtures),
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "slots.csv", SLOT_FIELDNAMES, rows)
    write_csv(args.output / "edges.csv", EDGE_FIELDNAMES, edges)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, rows, edges, args.title))

    print(f"Slots: {summary['slots']}")
    print(f"Exception slots: {summary['exception_slots']}")
    print(f"Source available slots: {summary['source_available_slots']}")
    print(f"Source unknown slots: {summary['source_unknown_slots']}")
    print(f"Unknown high-safe source slots: {summary['source_unknown_in_highsafe_slots']}")
    print(f"Unknown outside source slots: {summary['source_unknown_outside_highsafe_slots']}")
    print(
        "Top unknown edge: "
        f"{summary['top_unknown_dependency_edge']} "
        f"({summary['top_unknown_dependency_edge_slots']} slots)"
    )
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
