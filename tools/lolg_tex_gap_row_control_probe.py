#!/usr/bin/env python3
"""Probe control-byte context around best per-row .tex gap starts."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv
from lolg_tex_gap_row_stride_probe import source_bytes


DEFAULT_OUTPUT = Path("output/tex_gap_row_control_probe")
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_CANDIDATES = Path("output/tex_gap_row_delta_probe/candidates.csv")
DEFAULT_ROW_DELTAS = Path("output/tex_gap_row_delta_probe/row_deltas.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "selected_candidates",
    "row_control_rows",
    "fixtures",
    "context_before",
    "context_after",
    "control_groups",
    "repeated_control_groups",
    "unique_before2",
    "unique_at2",
    "unique_delta_values",
    "metric_rows",
    "best_metric",
    "best_metric_hits",
    "best_group_key",
    "best_group_rows",
    "best_group_exact_ratio",
    "negative_start_rows",
    "out_of_range_start_rows",
    "full_nonzero_rows",
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
    "row_control_rows",
    "unique_control_keys",
    "unique_before2",
    "unique_at2",
    "unique_delta_values",
    "most_common_control_key",
    "most_common_control_rows",
    "metric_hit_rows",
    "negative_start_rows",
    "out_of_range_start_rows",
    "full_nonzero_rows",
    "adjusted_nonzero_exact_slots",
    "adjusted_nonzero_exact_ratio",
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
    "source_start",
    "best_delta",
    "best_source_start",
    "payload_offset",
    "source_mode",
    "source_len",
    "raw_segment_index",
    "nonzero_slots",
    "adjusted_nonzero_exact_slots",
    "adjusted_gain_nonzero_slots",
    "full_nonzero_row",
    "control_key",
    "source_before4_hex",
    "source_before2_hex",
    "source_at2_hex",
    "source_at4_hex",
    "source_window_hex",
    "raw_window_hex",
    "byte_rel_m4",
    "byte_rel_m3",
    "byte_rel_m2",
    "byte_rel_m1",
    "byte_rel_p0",
    "byte_rel_p1",
    "byte_rel_p2",
    "byte_rel_p3",
    "u16le_rel_m2",
    "u16le_rel_p0",
    "metric_matches",
    "issues",
]

CONTROL_GROUP_FIELDNAMES = [
    "control_key",
    "source_mode",
    "rows",
    "candidates",
    "fixtures",
    "unique_delta_values",
    "delta_values",
    "min_delta",
    "max_delta",
    "avg_delta",
    "nonzero_slots",
    "adjusted_nonzero_exact_slots",
    "adjusted_nonzero_exact_ratio",
    "full_nonzero_rows",
    "metric_hit_rows",
    "sample_pcx",
    "sample_frontier_id",
    "sample_selection_id",
    "sample_row_index",
    "sample_window_hex",
]

METRIC_FIELDNAMES = [
    "metric",
    "hits",
    "row_control_rows",
    "hit_ratio",
    "candidates",
    "fixtures",
    "sample_pcx",
    "sample_frontier_id",
    "sample_selection_id",
    "sample_row_index",
    "sample_delta",
    "sample_control_key",
]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def fixture_key(row: dict[str, str]) -> tuple[str, str, str]:
    return (row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", ""))


def load_bytes(path_text: str, issues: list[str], label: str) -> bytes:
    if not path_text:
        issues.append(f"missing_{label}_path")
        return b""
    try:
        return Path(path_text).read_bytes()
    except OSError as exc:
        issues.append(f"read_{label}_failed:{exc}")
        return b""


def byte_at(data: bytes, index: int) -> int | None:
    if 0 <= index < len(data):
        return data[index]
    return None


def byte_text(value: int | None) -> str:
    return str(value) if value is not None else ""


def signed_u8(value: int) -> int:
    return value - 256 if value >= 128 else value


def u16le_at(data: bytes, index: int) -> int | None:
    if 0 <= index and index + 1 < len(data):
        return data[index] | (data[index + 1] << 8)
    return None


def slice_hex(data: bytes, start: int, end: int) -> str:
    start = max(0, start)
    end = min(len(data), end)
    if end <= start:
        return ""
    return data[start:end].hex()


def window_hex(data: bytes, center: int, before: int, after: int) -> str:
    return slice_hex(data, center - before, center + after)


def raw_index_for_source_index(segment: bytes, payload_offset: int, mode: str, source_index: int) -> int | None:
    if source_index < 0 or payload_offset < 0 or payload_offset > len(segment):
        return None
    if mode == "raw":
        raw_index = payload_offset + source_index
        return raw_index if raw_index < len(segment) else None
    if mode != "drop_zero_source":
        return None
    seen = 0
    for raw_index in range(payload_offset, len(segment)):
        if segment[raw_index] == 0:
            continue
        if seen == source_index:
            return raw_index
        seen += 1
    return None


def row_delta_lookup(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    output: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        output[row.get("selection_id", "")].append(row)
    for delta_rows in output.values():
        delta_rows.sort(key=lambda row: int_value(row, "row_index"))
    return output


def relation_metrics(row: dict[str, str], source: bytes, best_source_start: int) -> list[str]:
    delta = int_value(row, "best_delta")
    source_start = int_value(row, "source_start")
    nonzero_slots = int_value(row, "nonzero_slots")
    row_index = int_value(row, "row_index")
    absolute_row = int_value(row, "absolute_row")
    matches: list[str] = []

    for rel in range(-4, 5):
        value = byte_at(source, best_source_start + rel)
        if value is None:
            continue
        rel_name = f"rel{rel:+d}"
        signed = signed_u8(value)
        if delta and delta == signed:
            matches.append(f"delta_eq_i8_{rel_name}")
        if delta and delta == -signed:
            matches.append(f"delta_eq_neg_i8_{rel_name}")
        if delta and delta == value:
            matches.append(f"delta_eq_u8_{rel_name}")
        if delta and abs(delta) == value:
            matches.append(f"abs_delta_eq_u8_{rel_name}")
        if nonzero_slots == value:
            matches.append(f"nonzero_slots_eq_u8_{rel_name}")
        if row_index == value:
            matches.append(f"row_index_eq_u8_{rel_name}")
        if absolute_row == value:
            matches.append(f"absolute_row_eq_u8_{rel_name}")

    for rel in range(-4, 4):
        value = u16le_at(source, best_source_start + rel)
        if value is None:
            continue
        rel_name = f"rel{rel:+d}"
        if source_start == value:
            matches.append(f"source_start_eq_u16le_{rel_name}")
        if best_source_start == value:
            matches.append(f"best_source_start_eq_u16le_{rel_name}")
        if nonzero_slots == value:
            matches.append(f"nonzero_slots_eq_u16le_{rel_name}")

    return sorted(set(matches))


def analyze_candidate(
    candidate: dict[str, str],
    fixture: dict[str, str],
    delta_rows: list[dict[str, str]],
    *,
    context_before: int,
    context_after: int,
) -> tuple[dict[str, str], list[dict[str, str]]]:
    issues: list[str] = []
    notes: list[str] = []
    segment = load_bytes(fixture.get("segment_gap_path", ""), issues, "segment")
    payload_offset = int_value(candidate, "payload_offset")
    mode = candidate.get("source_mode", "raw")
    try:
        source = source_bytes(segment, payload_offset, mode)
    except ValueError as exc:
        source = b""
        issues.append(str(exc))

    row_rows: list[dict[str, str]] = []
    control_counts: Counter[str] = Counter()
    before2_values: set[str] = set()
    at2_values: set[str] = set()
    delta_values: set[str] = set()
    metric_hit_rows = 0
    negative_start_rows = 0
    out_of_range_rows = 0
    full_nonzero_rows = 0
    adjusted_total = 0
    nonzero_total = 0

    for delta_row in delta_rows:
        best_source_start = int_value(delta_row, "best_source_start")
        row_issues: list[str] = []
        if best_source_start < 0:
            negative_start_rows += 1
            row_issues.append("negative_best_source_start")
        if not 0 <= best_source_start < len(source):
            out_of_range_rows += 1
            row_issues.append("best_source_start_out_of_range")

        raw_index = raw_index_for_source_index(segment, payload_offset, mode, best_source_start)
        before2 = slice_hex(source, best_source_start - 2, best_source_start)
        at2 = slice_hex(source, best_source_start, best_source_start + 2)
        control_key = f"{before2 or 'NA'}|{at2 or 'NA'}"
        metrics = relation_metrics(delta_row, source, best_source_start)
        if metrics:
            metric_hit_rows += 1
        if before2:
            before2_values.add(before2)
        if at2:
            at2_values.add(at2)
        if delta_row.get("best_delta", ""):
            delta_values.add(delta_row["best_delta"])
        control_counts[control_key] += 1
        full_nonzero_rows += int_value(delta_row, "full_nonzero_row")
        adjusted_total += int_value(delta_row, "adjusted_nonzero_exact_slots")
        nonzero_total += int_value(delta_row, "nonzero_slots")

        row_rows.append(
            {
                "selection_id": candidate.get("selection_id", ""),
                "rank": candidate.get("rank", ""),
                "pcx_name": candidate.get("pcx_name", ""),
                "frontier_id": candidate.get("frontier_id", ""),
                "row_index": delta_row.get("row_index", ""),
                "absolute_row": delta_row.get("absolute_row", ""),
                "source_start": delta_row.get("source_start", ""),
                "best_delta": delta_row.get("best_delta", ""),
                "best_source_start": delta_row.get("best_source_start", ""),
                "payload_offset": candidate.get("payload_offset", ""),
                "source_mode": mode,
                "source_len": str(len(source)),
                "raw_segment_index": "" if raw_index is None else str(raw_index),
                "nonzero_slots": delta_row.get("nonzero_slots", ""),
                "adjusted_nonzero_exact_slots": delta_row.get("adjusted_nonzero_exact_slots", ""),
                "adjusted_gain_nonzero_slots": delta_row.get("adjusted_gain_nonzero_slots", ""),
                "full_nonzero_row": delta_row.get("full_nonzero_row", ""),
                "control_key": control_key,
                "source_before4_hex": slice_hex(source, best_source_start - 4, best_source_start),
                "source_before2_hex": before2,
                "source_at2_hex": at2,
                "source_at4_hex": slice_hex(source, best_source_start, best_source_start + 4),
                "source_window_hex": window_hex(source, best_source_start, context_before, context_after),
                "raw_window_hex": ""
                if raw_index is None
                else window_hex(segment, raw_index, context_before, context_after),
                "byte_rel_m4": byte_text(byte_at(source, best_source_start - 4)),
                "byte_rel_m3": byte_text(byte_at(source, best_source_start - 3)),
                "byte_rel_m2": byte_text(byte_at(source, best_source_start - 2)),
                "byte_rel_m1": byte_text(byte_at(source, best_source_start - 1)),
                "byte_rel_p0": byte_text(byte_at(source, best_source_start)),
                "byte_rel_p1": byte_text(byte_at(source, best_source_start + 1)),
                "byte_rel_p2": byte_text(byte_at(source, best_source_start + 2)),
                "byte_rel_p3": byte_text(byte_at(source, best_source_start + 3)),
                "u16le_rel_m2": "" if u16le_at(source, best_source_start - 2) is None else str(u16le_at(source, best_source_start - 2)),
                "u16le_rel_p0": "" if u16le_at(source, best_source_start) is None else str(u16le_at(source, best_source_start)),
                "metric_matches": ";".join(metrics),
                "issues": ";".join(row_issues),
            }
        )

    if not delta_rows:
        notes.append("missing_row_deltas")
    if control_counts:
        most_common_control_key, most_common_rows = control_counts.most_common(1)[0]
    else:
        most_common_control_key, most_common_rows = "", 0
    if most_common_rows <= 1:
        notes.append("no_repeated_control_key")

    candidate_row = {
        "selection_id": candidate.get("selection_id", ""),
        "rank": candidate.get("rank", ""),
        "rule_type": candidate.get("rule_type", ""),
        "archive": candidate.get("archive", ""),
        "archive_tag": candidate.get("archive_tag", ""),
        "pcx_name": candidate.get("pcx_name", ""),
        "frontier_id": candidate.get("frontier_id", ""),
        "frontier_type": candidate.get("frontier_type", ""),
        "payload_offset": candidate.get("payload_offset", ""),
        "source_mode": mode,
        "row_stride": candidate.get("row_stride", ""),
        "row_prefix_skip": candidate.get("row_prefix_skip", ""),
        "row_control_rows": str(len(row_rows)),
        "unique_control_keys": str(len(control_counts)),
        "unique_before2": str(len(before2_values)),
        "unique_at2": str(len(at2_values)),
        "unique_delta_values": str(len(delta_values)),
        "most_common_control_key": most_common_control_key,
        "most_common_control_rows": str(most_common_rows),
        "metric_hit_rows": str(metric_hit_rows),
        "negative_start_rows": str(negative_start_rows),
        "out_of_range_start_rows": str(out_of_range_rows),
        "full_nonzero_rows": str(full_nonzero_rows),
        "adjusted_nonzero_exact_slots": str(adjusted_total),
        "adjusted_nonzero_exact_ratio": f"{(adjusted_total / nonzero_total) if nonzero_total else 0.0:.6f}",
        "issue_notes": ";".join(sorted(set(notes))),
        "issues": ";".join(issues),
    }
    return candidate_row, row_rows


def build_control_groups(row_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in row_rows:
        grouped[(row.get("source_mode", ""), row.get("control_key", ""))].append(row)

    group_rows: list[dict[str, str]] = []
    for (source_mode, control_key), rows in grouped.items():
        deltas = [int_value(row, "best_delta") for row in rows]
        delta_values = sorted({row.get("best_delta", "") for row in rows if row.get("best_delta", "")}, key=int)
        nonzero_slots = sum(int_value(row, "nonzero_slots") for row in rows)
        adjusted = sum(int_value(row, "adjusted_nonzero_exact_slots") for row in rows)
        sample = rows[0]
        group_rows.append(
            {
                "control_key": control_key,
                "source_mode": source_mode,
                "rows": str(len(rows)),
                "candidates": str(len({row.get("selection_id", "") for row in rows})),
                "fixtures": str(len({fixture_key(row) for row in rows})),
                "unique_delta_values": str(len(delta_values)),
                "delta_values": ";".join(delta_values[:32]),
                "min_delta": str(min(deltas) if deltas else 0),
                "max_delta": str(max(deltas) if deltas else 0),
                "avg_delta": f"{(sum(deltas) / len(deltas)) if deltas else 0.0:.3f}",
                "nonzero_slots": str(nonzero_slots),
                "adjusted_nonzero_exact_slots": str(adjusted),
                "adjusted_nonzero_exact_ratio": f"{(adjusted / nonzero_slots) if nonzero_slots else 0.0:.6f}",
                "full_nonzero_rows": str(sum(int_value(row, "full_nonzero_row") for row in rows)),
                "metric_hit_rows": str(sum(1 for row in rows if row.get("metric_matches"))),
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
                "sample_selection_id": sample.get("selection_id", ""),
                "sample_row_index": sample.get("row_index", ""),
                "sample_window_hex": sample.get("source_window_hex", ""),
            }
        )
    return sorted(
        group_rows,
        key=lambda row: (
            int_value(row, "rows"),
            int_value(row, "adjusted_nonzero_exact_slots"),
            row.get("control_key", ""),
        ),
        reverse=True,
    )


def build_metric_rows(row_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in row_rows:
        for metric in row.get("metric_matches", "").split(";"):
            if metric:
                grouped[metric].append(row)

    metric_rows: list[dict[str, str]] = []
    for metric, rows in grouped.items():
        sample = rows[0]
        metric_rows.append(
            {
                "metric": metric,
                "hits": str(len(rows)),
                "row_control_rows": str(len(row_rows)),
                "hit_ratio": f"{(len(rows) / len(row_rows)) if row_rows else 0.0:.6f}",
                "candidates": str(len({row.get("selection_id", "") for row in rows})),
                "fixtures": str(len({fixture_key(row) for row in rows})),
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
                "sample_selection_id": sample.get("selection_id", ""),
                "sample_row_index": sample.get("row_index", ""),
                "sample_delta": sample.get("best_delta", ""),
                "sample_control_key": sample.get("control_key", ""),
            }
        )
    return sorted(metric_rows, key=lambda row: (int_value(row, "hits"), row.get("metric", "")), reverse=True)


def build_rows(
    fixtures: Path,
    candidates: Path,
    row_deltas: Path,
    *,
    context_before: int,
    context_after: int,
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    fixtures_by_key = {fixture_key(row): row for row in read_rows(fixtures)}
    deltas_by_selection = row_delta_lookup(read_rows(row_deltas))
    candidate_rows: list[dict[str, str]] = []
    row_rows: list[dict[str, str]] = []
    for candidate in read_rows(candidates):
        key = fixture_key(candidate)
        analyzed, rows = analyze_candidate(
            candidate,
            fixtures_by_key.get(key, {}),
            deltas_by_selection.get(candidate.get("selection_id", ""), []),
            context_before=context_before,
            context_after=context_after,
        )
        candidate_rows.append(analyzed)
        row_rows.extend(rows)
    control_groups = build_control_groups(row_rows)
    metric_rows = build_metric_rows(row_rows)
    return candidate_rows, row_rows, control_groups, metric_rows


def summary_row(
    candidate_rows: list[dict[str, str]],
    row_rows: list[dict[str, str]],
    control_groups: list[dict[str, str]],
    metric_rows: list[dict[str, str]],
    *,
    context_before: int,
    context_after: int,
) -> dict[str, str]:
    best_group = next((row for row in control_groups if row.get("control_key") != "NA|NA"), {})
    if not best_group and control_groups:
        best_group = control_groups[0]
    best_metric = metric_rows[0] if metric_rows else {}
    before2_values = {row.get("source_before2_hex", "") for row in row_rows if row.get("source_before2_hex", "")}
    at2_values = {row.get("source_at2_hex", "") for row in row_rows if row.get("source_at2_hex", "")}
    delta_values = {row.get("best_delta", "") for row in row_rows if row.get("best_delta", "")}
    return {
        "scope": "total",
        "selected_candidates": str(len(candidate_rows)),
        "row_control_rows": str(len(row_rows)),
        "fixtures": str(len({fixture_key(row) for row in candidate_rows})),
        "context_before": str(context_before),
        "context_after": str(context_after),
        "control_groups": str(len(control_groups)),
        "repeated_control_groups": str(sum(1 for row in control_groups if int_value(row, "rows") > 1)),
        "unique_before2": str(len(before2_values)),
        "unique_at2": str(len(at2_values)),
        "unique_delta_values": str(len(delta_values)),
        "metric_rows": str(len(metric_rows)),
        "best_metric": best_metric.get("metric", ""),
        "best_metric_hits": best_metric.get("hits", "0"),
        "best_group_key": best_group.get("control_key", ""),
        "best_group_rows": best_group.get("rows", "0"),
        "best_group_exact_ratio": best_group.get("adjusted_nonzero_exact_ratio", "0.000000"),
        "negative_start_rows": str(sum(int_value(row, "negative_start_rows") for row in candidate_rows)),
        "out_of_range_start_rows": str(sum(int_value(row, "out_of_range_start_rows") for row in candidate_rows)),
        "full_nonzero_rows": str(sum(int_value(row, "full_nonzero_rows") for row in candidate_rows)),
        "issue_rows": str(sum(1 for row in candidate_rows if row.get("issues"))),
    }


def render_candidate_row(row: dict[str, str]) -> str:
    return (
        "<tr>"
        f"<td>{html.escape(row.get('selection_id', ''))}</td>"
        f"<td>{html.escape(row.get('pcx_name', ''))}</td>"
        f"<td>{html.escape(row.get('frontier_id', ''))}</td>"
        f"<td>{html.escape(row.get('source_mode', ''))}</td>"
        f"<td>{html.escape(row.get('row_stride', ''))}</td>"
        f"<td>{html.escape(row.get('row_prefix_skip', ''))}</td>"
        f"<td>{html.escape(row.get('row_control_rows', ''))}</td>"
        f"<td>{html.escape(row.get('unique_control_keys', ''))}</td>"
        f"<td>{html.escape(row.get('most_common_control_key', ''))}</td>"
        f"<td>{html.escape(row.get('most_common_control_rows', ''))}</td>"
        f"<td>{html.escape(row.get('metric_hit_rows', ''))}</td>"
        f"<td>{html.escape(row.get('adjusted_nonzero_exact_slots', ''))}</td>"
        f"<td>{html.escape(row.get('issue_notes', ''))}</td>"
        f"<td>{html.escape(row.get('issues', ''))}</td>"
        "</tr>"
    )


def render_control_group_row(row: dict[str, str]) -> str:
    return (
        "<tr>"
        f"<td><code>{html.escape(row.get('control_key', ''))}</code></td>"
        f"<td>{html.escape(row.get('source_mode', ''))}</td>"
        f"<td>{html.escape(row.get('rows', ''))}</td>"
        f"<td>{html.escape(row.get('candidates', ''))}</td>"
        f"<td>{html.escape(row.get('fixtures', ''))}</td>"
        f"<td>{html.escape(row.get('unique_delta_values', ''))}</td>"
        f"<td>{html.escape(row.get('min_delta', ''))}</td>"
        f"<td>{html.escape(row.get('max_delta', ''))}</td>"
        f"<td>{html.escape(row.get('adjusted_nonzero_exact_ratio', ''))}</td>"
        f"<td>{html.escape(row.get('metric_hit_rows', ''))}</td>"
        f"<td>{html.escape(row.get('sample_pcx', ''))}</td>"
        f"<td><code>{html.escape(row.get('sample_window_hex', ''))}</code></td>"
        "</tr>"
    )


def render_metric_row(row: dict[str, str]) -> str:
    return (
        "<tr>"
        f"<td>{html.escape(row.get('metric', ''))}</td>"
        f"<td>{html.escape(row.get('hits', ''))}</td>"
        f"<td>{html.escape(row.get('hit_ratio', ''))}</td>"
        f"<td>{html.escape(row.get('candidates', ''))}</td>"
        f"<td>{html.escape(row.get('fixtures', ''))}</td>"
        f"<td>{html.escape(row.get('sample_pcx', ''))}</td>"
        f"<td>{html.escape(row.get('sample_row_index', ''))}</td>"
        f"<td>{html.escape(row.get('sample_delta', ''))}</td>"
        f"<td><code>{html.escape(row.get('sample_control_key', ''))}</code></td>"
        "</tr>"
    )


def render_row_control(row: dict[str, str]) -> str:
    return (
        "<tr>"
        f"<td>{html.escape(row.get('selection_id', ''))}</td>"
        f"<td>{html.escape(row.get('row_index', ''))}</td>"
        f"<td>{html.escape(row.get('best_source_start', ''))}</td>"
        f"<td>{html.escape(row.get('best_delta', ''))}</td>"
        f"<td>{html.escape(row.get('adjusted_nonzero_exact_slots', ''))}</td>"
        f"<td><code>{html.escape(row.get('control_key', ''))}</code></td>"
        f"<td><code>{html.escape(row.get('source_window_hex', ''))}</code></td>"
        f"<td>{html.escape(row.get('metric_matches', ''))}</td>"
        f"<td>{html.escape(row.get('issues', ''))}</td>"
        "</tr>"
    )


def build_html(
    summary: dict[str, str],
    candidate_rows: list[dict[str, str]],
    row_rows: list[dict[str, str]],
    control_groups: list[dict[str, str]],
    metric_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "candidates": candidate_rows,
        "rowControls": row_rows,
        "controlGroups": control_groups,
        "metrics": metric_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("candidates.csv", output_dir / "candidates.csv"),
            ("row_controls.csv", output_dir / "row_controls.csv"),
            ("by_control.csv", output_dir / "by_control.csv"),
            ("by_metric.csv", output_dir / "by_metric.csv"),
        )
    )
    candidate_markup = "\n".join(
        render_candidate_row(row)
        for row in sorted(candidate_rows, key=lambda row: int_value(row, "adjusted_nonzero_exact_slots"), reverse=True)
    )
    control_markup = "\n".join(render_control_group_row(row) for row in control_groups[:160])
    metric_markup = "\n".join(render_metric_row(row) for row in metric_rows[:160])
    top_rows = sorted(
        row_rows,
        key=lambda row: (int_value(row, "adjusted_gain_nonzero_slots"), int_value(row, "adjusted_nonzero_exact_slots")),
        reverse=True,
    )[:180]
    row_markup = "\n".join(render_row_control(row) for row in top_rows)
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
table {{ width: 100%; border-collapse: collapse; min-width: 1380px; }}
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
    <div class="sub">Contextes d'octets autour des departs de lignes alignes par delta.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Candidates</div><div class="value">{html.escape(summary['selected_candidates'])}</div></div>
    <div class="stat"><div class="label">Row controls</div><div class="value">{html.escape(summary['row_control_rows'])}</div></div>
    <div class="stat"><div class="label">Control groups</div><div class="value">{html.escape(summary['control_groups'])}</div></div>
    <div class="stat"><div class="label">Best metric hits</div><div class="value ok">{html.escape(summary['best_metric_hits'])}</div></div>
    <div class="stat"><div class="label">Repeated groups</div><div class="value">{html.escape(summary['repeated_control_groups'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div></section>
  <section class="panel">
    <h2>Candidates</h2>
    <table>
      <thead><tr><th>ID</th><th>PCX</th><th>Frontier</th><th>Mode</th><th>Stride</th><th>Prefix</th><th>Rows</th><th>Keys</th><th>Top key</th><th>Top rows</th><th>Metric rows</th><th>Exact</th><th>Notes</th><th>Issues</th></tr></thead>
      <tbody>{candidate_markup}</tbody>
    </table>
  </section>
  <section class="panel">
    <h2>Top control groups</h2>
    <table>
      <thead><tr><th>Key</th><th>Mode</th><th>Rows</th><th>Candidates</th><th>Fixtures</th><th>Deltas</th><th>Min</th><th>Max</th><th>Exact ratio</th><th>Metric rows</th><th>Sample PCX</th><th>Window</th></tr></thead>
      <tbody>{control_markup}</tbody>
    </table>
  </section>
  <section class="panel">
    <h2>Metric hits</h2>
    <table>
      <thead><tr><th>Metric</th><th>Hits</th><th>Ratio</th><th>Candidates</th><th>Fixtures</th><th>Sample PCX</th><th>Row</th><th>Delta</th><th>Key</th></tr></thead>
      <tbody>{metric_markup}</tbody>
    </table>
  </section>
  <section class="panel">
    <h2>Top row controls</h2>
    <table>
      <thead><tr><th>ID</th><th>Row</th><th>Best source start</th><th>Delta</th><th>Exact</th><th>Key</th><th>Window</th><th>Metrics</th><th>Issues</th></tr></thead>
      <tbody>{row_markup}</tbody>
    </table>
  </section>
</main>
<script>
const TEX_GAP_ROW_CONTROL_PROBE = {data_json};
</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    fixtures: Path,
    candidates: Path,
    row_deltas: Path,
    *,
    context_before: int,
    context_after: int,
    title: str,
) -> tuple[
    dict[str, str],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
]:
    output_dir.mkdir(parents=True, exist_ok=True)
    candidate_rows, row_rows, control_groups, metric_rows = build_rows(
        fixtures,
        candidates,
        row_deltas,
        context_before=context_before,
        context_after=context_after,
    )
    summary = summary_row(
        candidate_rows,
        row_rows,
        control_groups,
        metric_rows,
        context_before=context_before,
        context_after=context_after,
    )
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "candidates.csv", CANDIDATE_FIELDNAMES, candidate_rows)
    write_csv(output_dir / "row_controls.csv", ROW_FIELDNAMES, row_rows)
    write_csv(output_dir / "by_control.csv", CONTROL_GROUP_FIELDNAMES, control_groups)
    write_csv(output_dir / "by_metric.csv", METRIC_FIELDNAMES, metric_rows)
    (output_dir / "index.html").write_text(
        build_html(summary, candidate_rows, row_rows, control_groups, metric_rows, output_dir, title)
    )
    return summary, candidate_rows, row_rows, control_groups, metric_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe row-local control bytes for .tex row-delta candidates.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--row-deltas", type=Path, default=DEFAULT_ROW_DELTAS)
    parser.add_argument("--context-before", type=int, default=8)
    parser.add_argument("--context-after", type=int, default=24)
    parser.add_argument("--title", default="Lands of Lore II .tex Gap Row Control Probe")
    args = parser.parse_args()

    summary, _candidate_rows, _row_rows, _control_groups, _metric_rows = write_report(
        args.output,
        args.fixtures,
        args.candidates,
        args.row_deltas,
        context_before=args.context_before,
        context_after=args.context_after,
        title=args.title,
    )
    print(f"Selected candidates: {summary['selected_candidates']}")
    print(f"Row control rows: {summary['row_control_rows']}")
    print(f"Control groups: {summary['control_groups']}")
    print(f"Best metric: {summary['best_metric']} ({summary['best_metric_hits']})")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
