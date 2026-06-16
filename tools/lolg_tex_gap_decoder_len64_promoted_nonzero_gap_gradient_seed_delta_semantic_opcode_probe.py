#!/usr/bin/env python3
"""Probe semantic operation context for gradient seed delta selectors."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_delta_semantic_opcode_probe"
)
DEFAULT_PHASE_VALUES = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_delta_phase_probe/phase_values.csv"
)
DEFAULT_OPERATIONS = Path("output/tex_gap_segmentation_control_correlation_probe/operations.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "seed_rows",
    "mapping_rows",
    "mapping_value_bytes",
    "operation_context_rows",
    "semantic_scopes",
    "semantic_families",
    "semantic_groups",
    "deterministic_groups",
    "deterministic_bytes",
    "repeated_deterministic_groups",
    "repeated_deterministic_bytes",
    "singleton_deterministic_groups",
    "singleton_deterministic_bytes",
    "conflicted_groups",
    "conflicted_bytes",
    "op_context_repeated_bytes",
    "op_neighborhood_repeated_bytes",
    "source_role_repeated_bytes",
    "control_token_repeated_bytes",
    "semantic_combo_repeated_bytes",
    "best_semantic_family",
    "best_semantic_repeated_bytes",
    "best_semantic_conflicted_bytes",
    "kind_patterns",
    "length_patterns",
    "copy_unlock_rows",
    "copy_unlock_bytes",
    "total_potential_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

SEED_STREAM_FIELDNAMES = [
    "seed_id",
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "op_index",
    "start",
    "end",
    "length",
    "candidate_kind",
    "mapping_rows",
    "mapping_value_bytes",
    "copy_unlock_bytes",
    "frontier_type",
    "strategy",
    "current_op_kind",
    "current_length_bucket",
    "current_expected_mod64",
    "current_control_ref_mod64",
    "control_window_len",
    "prev_kind",
    "prev_length_bucket",
    "next_kind",
    "next_length_bucket",
    "kind_pattern_r2",
    "kind_pattern_r4",
    "length_bucket_pattern_r2",
    "length_bucket_pattern_r4",
    "kind_length_pattern_r2",
    "gap_count_before",
    "zero_count_before",
    "literal_count_before",
    "gap_count_radius4",
    "zero_count_radius4",
    "literal_count_radius4",
    "prev_literal_distance_bucket",
    "next_literal_distance_bucket",
    "prev_zero_length_bucket",
    "next_zero_length_bucket",
    "semantic_signature",
    "issues",
]

SEMANTIC_VALUE_FIELDNAMES = [
    "seed_id",
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "op_index",
    "start",
    "end",
    "length",
    "candidate_kind",
    "palette_index",
    "source_value_hex",
    "target_value_hex",
    "delta",
    "source_offset",
    "value_bytes",
    "copy_unlock_bytes",
    "frontier_type",
    "strategy",
    "current_op_kind",
    "current_length_bucket",
    "current_expected_mod64",
    "current_control_ref_mod64",
    "control_window_len",
    "kind_pattern_r2",
    "kind_pattern_r4",
    "length_bucket_pattern_r2",
    "length_bucket_pattern_r4",
    "source_offset_zone",
    "source_offset_bucket4",
    "source_offset_vs_prev_zero_bucket",
    "source_offset_vs_next_zero_bucket",
    "source_offset_vs_expected_mod64_bucket",
    "source_token_class",
    "prev_token_class",
    "next_token_class",
    "semantic_entries",
    "issues",
]

SELECTOR_FIELDNAMES = [
    "semantic_scope",
    "semantic_family",
    "semantic_key",
    "rows",
    "seed_rows",
    "value_bytes",
    "deltas_seen",
    "deterministic",
    "repeated_deterministic",
    "verdict",
    "sample_pcx",
    "sample_frontier_id",
]

FAMILY_FIELDNAMES = [
    "semantic_scope",
    "semantic_family",
    "groups",
    "rows",
    "value_bytes",
    "deterministic_groups",
    "deterministic_bytes",
    "repeated_deterministic_groups",
    "repeated_deterministic_bytes",
    "singleton_deterministic_groups",
    "singleton_deterministic_bytes",
    "conflicted_groups",
    "conflicted_bytes",
    "verdict",
]

SCOPE_FIELDNAMES = [
    "semantic_scope",
    "families",
    "groups",
    "rows",
    "value_bytes",
    "deterministic_groups",
    "deterministic_bytes",
    "repeated_deterministic_groups",
    "repeated_deterministic_bytes",
    "singleton_deterministic_groups",
    "singleton_deterministic_bytes",
    "conflicted_groups",
    "conflicted_bytes",
    "verdict",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def safe_bytes_fromhex(value: str) -> bytes:
    try:
        return bytes.fromhex(value)
    except ValueError:
        return b""


def length_bucket(length: int) -> str:
    if length <= 0:
        return "0"
    if length == 1:
        return "1"
    if length <= 3:
        return "2-3"
    if length <= 7:
        return "4-7"
    if length <= 15:
        return "8-15"
    if length <= 31:
        return "16-31"
    if length <= 63:
        return "32-63"
    if length <= 127:
        return "64-127"
    return "128+"


def signed_bucket(value: int) -> str:
    if value <= -64:
        return "<=-64"
    if value <= -16:
        return "-63..-16"
    if value <= -8:
        return "-15..-8"
    if value <= -4:
        return "-7..-4"
    if value <= -1:
        return "-3..-1"
    if value == 0:
        return "0"
    if value <= 3:
        return "1..3"
    if value <= 7:
        return "4..7"
    if value <= 15:
        return "8..15"
    if value <= 63:
        return "16..63"
    return ">=64"


def low_nibble_bucket(low: int) -> str:
    if low <= 3:
        return "0-3"
    if low <= 7:
        return "4-7"
    if low <= 11:
        return "8-b"
    return "c-f"


def byte_class(window: bytes, offset: int) -> str:
    if offset < 0 or offset >= len(window):
        return ""
    value = window[offset]
    if value == 0:
        return "zero"
    high = value >> 4
    low = value & 0x0F
    if high == low:
        return f"same_nibble_{high:x}"
    return f"hi{high:x}_lo{low_nibble_bucket(low)}"


def operation_key(row: dict[str, str]) -> tuple[str, str, str, str, str, str, str]:
    return (
        row.get("rank", ""),
        row.get("archive", ""),
        row.get("pcx_name", ""),
        row.get("frontier_id", ""),
        row.get("op_index", ""),
        row.get("expected_start", row.get("start", "")),
        row.get("expected_end", row.get("end", "")),
    )


def phase_key(row: dict[str, str]) -> tuple[str, str, str, str, str, str, str]:
    return (
        row.get("rank", ""),
        row.get("archive", ""),
        row.get("pcx_name", ""),
        row.get("frontier_id", ""),
        row.get("op_index", ""),
        row.get("start", ""),
        row.get("end", ""),
    )


def group_key(row: dict[str, str]) -> tuple[str, str, str, str]:
    return (
        row.get("rank", ""),
        row.get("archive", ""),
        row.get("pcx_name", ""),
        row.get("frontier_id", ""),
    )


def build_operation_indexes(
    operations: list[dict[str, str]],
) -> tuple[dict[tuple[str, str, str, str, str, str, str], dict[str, str]], dict[tuple[str, str, str, str], list[dict[str, str]]]]:
    by_key = {operation_key(row): row for row in operations}
    by_group: dict[tuple[str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in operations:
        by_group[group_key(row)].append(row)
    for rows in by_group.values():
        rows.sort(key=lambda row: int_value(row, "op_index"))
    return by_key, by_group


def local_ops(
    operation: dict[str, str],
    operations_by_group: dict[tuple[str, str, str, str], list[dict[str, str]]],
    radius: int,
) -> list[dict[str, str]]:
    rows = operations_by_group.get(group_key(operation), [])
    op_index = int_value(operation, "op_index")
    position = next((index for index, row in enumerate(rows) if int_value(row, "op_index") == op_index), -1)
    if position < 0:
        return []
    return rows[max(0, position - radius) : min(len(rows), position + radius + 1)]


def neighbor_op(
    operation: dict[str, str],
    operations_by_group: dict[tuple[str, str, str, str], list[dict[str, str]]],
    delta: int,
) -> dict[str, str]:
    rows = operations_by_group.get(group_key(operation), [])
    op_index = int_value(operation, "op_index")
    position = next((index for index, row in enumerate(rows) if int_value(row, "op_index") == op_index), -1)
    target = position + delta
    if position < 0 or target < 0 or target >= len(rows):
        return {}
    return rows[target]


def kind_pattern(rows: list[dict[str, str]]) -> str:
    return "|".join(row.get("op_kind", "") for row in rows)


def length_pattern(rows: list[dict[str, str]]) -> str:
    return "|".join(length_bucket(int_value(row, "length")) for row in rows)


def kind_length_pattern(rows: list[dict[str, str]]) -> str:
    return "|".join(f"{row.get('op_kind', '')}:{length_bucket(int_value(row, 'length'))}" for row in rows)


def count_kind_before(operation: dict[str, str], operations_by_group: dict[tuple[str, str, str, str], list[dict[str, str]]], kind: str) -> int:
    rows = operations_by_group.get(group_key(operation), [])
    op_index = int_value(operation, "op_index")
    return sum(1 for row in rows if int_value(row, "op_index") < op_index and row.get("op_kind", "") == kind)


def closest_kind_distance_bucket(
    operation: dict[str, str],
    operations_by_group: dict[tuple[str, str, str, str], list[dict[str, str]]],
    kind: str,
    direction: int,
) -> str:
    rows = operations_by_group.get(group_key(operation), [])
    op_index = int_value(operation, "op_index")
    candidates = [
        abs(int_value(row, "op_index") - op_index)
        for row in rows
        if row.get("op_kind", "") == kind and (int_value(row, "op_index") - op_index) * direction > 0
    ]
    if not candidates:
        return ""
    return length_bucket(min(candidates))


def source_offset_zone(offset: int, window_len: int) -> str:
    if window_len <= 0 or offset < 0:
        return ""
    third = window_len / 3.0
    if offset < third:
        return "head"
    if offset < third * 2:
        return "middle"
    return "tail"


def stable_deltas(rows: list[dict[str, str]]) -> str:
    return "|".join(str(delta) for delta in sorted({int_value(row, "delta") for row in rows}))


def seed_groups(phase_rows: list[dict[str, str]]) -> list[list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in phase_rows:
        grouped[row.get("seed_id", "")].append(row)
    groups = list(grouped.values())
    for rows in groups:
        rows.sort(key=lambda row: int_value(row, "palette_index"))
    groups.sort(key=lambda rows: (rows[0].get("pcx_name", ""), int_value(rows[0], "frontier_id")))
    return groups


def seed_context(
    seed_rows: list[dict[str, str]],
    operations_by_key: dict[tuple[str, str, str, str, str, str, str], dict[str, str]],
    operations_by_group: dict[tuple[str, str, str, str], list[dict[str, str]]],
) -> dict[str, str]:
    first = seed_rows[0]
    operation = operations_by_key.get(phase_key(first), {})
    issues = [issue for row in seed_rows for issue in row.get("issues", "").split(";") if issue]
    if not operation:
        issues.append("missing_operation_context")
    prev_op = neighbor_op(operation, operations_by_group, -1) if operation else {}
    next_op = neighbor_op(operation, operations_by_group, 1) if operation else {}
    radius2 = local_ops(operation, operations_by_group, 2) if operation else []
    radius4 = local_ops(operation, operations_by_group, 4) if operation else []
    radius4_counts = Counter(row.get("op_kind", "") for row in radius4)
    mapping_value_bytes = sum(int_value(row, "value_bytes") for row in seed_rows)
    semantic_signature = ";".join(
        [
            f"frontier_type={operation.get('frontier_type', '')}",
            f"strategy={operation.get('strategy', '')}",
            f"kind_r4={kind_pattern(radius4)}",
            f"len_r4={length_pattern(radius4)}",
            f"expected_mod64={operation.get('expected_mod64', '')}",
            f"control_ref_mod64={str(int_value(operation, 'control_ref_offset') % 64) if operation.get('control_ref_offset') else ''}",
        ]
    )
    return {
        "seed_id": first.get("seed_id", ""),
        "rank": first.get("rank", ""),
        "archive": first.get("archive", ""),
        "archive_tag": first.get("archive_tag", ""),
        "pcx_name": first.get("pcx_name", ""),
        "frontier_id": first.get("frontier_id", ""),
        "op_index": first.get("op_index", ""),
        "start": first.get("start", ""),
        "end": first.get("end", ""),
        "length": first.get("length", ""),
        "candidate_kind": first.get("candidate_kind", ""),
        "mapping_rows": str(len(seed_rows)),
        "mapping_value_bytes": str(mapping_value_bytes),
        "copy_unlock_bytes": first.get("copy_unlock_bytes", "0"),
        "frontier_type": operation.get("frontier_type", ""),
        "strategy": operation.get("strategy", ""),
        "current_op_kind": operation.get("op_kind", ""),
        "current_length_bucket": length_bucket(int_value(operation, "length")),
        "current_expected_mod64": operation.get("expected_mod64", ""),
        "current_control_ref_mod64": str(int_value(operation, "control_ref_offset") % 64) if operation.get("control_ref_offset") else "",
        "control_window_len": str(len(safe_bytes_fromhex(operation.get("control_window_hex", "")))),
        "prev_kind": prev_op.get("op_kind", ""),
        "prev_length_bucket": length_bucket(int_value(prev_op, "length")),
        "next_kind": next_op.get("op_kind", ""),
        "next_length_bucket": length_bucket(int_value(next_op, "length")),
        "kind_pattern_r2": kind_pattern(radius2),
        "kind_pattern_r4": kind_pattern(radius4),
        "length_bucket_pattern_r2": length_pattern(radius2),
        "length_bucket_pattern_r4": length_pattern(radius4),
        "kind_length_pattern_r2": kind_length_pattern(radius2),
        "gap_count_before": str(count_kind_before(operation, operations_by_group, "gap")) if operation else "0",
        "zero_count_before": str(count_kind_before(operation, operations_by_group, "zero")) if operation else "0",
        "literal_count_before": str(count_kind_before(operation, operations_by_group, "literal")) if operation else "0",
        "gap_count_radius4": str(radius4_counts.get("gap", 0)),
        "zero_count_radius4": str(radius4_counts.get("zero", 0)),
        "literal_count_radius4": str(radius4_counts.get("literal", 0)),
        "prev_literal_distance_bucket": closest_kind_distance_bucket(operation, operations_by_group, "literal", -1) if operation else "",
        "next_literal_distance_bucket": closest_kind_distance_bucket(operation, operations_by_group, "literal", 1) if operation else "",
        "prev_zero_length_bucket": length_bucket(int_value(prev_op, "length")) if prev_op.get("op_kind") == "zero" else "",
        "next_zero_length_bucket": length_bucket(int_value(next_op, "length")) if next_op.get("op_kind") == "zero" else "",
        "semantic_signature": semantic_signature,
        "issues": ";".join(dict.fromkeys(issues)),
    }


def build_seed_streams(
    phase_rows: list[dict[str, str]],
    operations_by_key: dict[tuple[str, str, str, str, str, str, str], dict[str, str]],
    operations_by_group: dict[tuple[str, str, str, str], list[dict[str, str]]],
) -> list[dict[str, str]]:
    return [seed_context(rows, operations_by_key, operations_by_group) for rows in seed_groups(phase_rows)]


def build_semantic_values(
    phase_rows: list[dict[str, str]],
    seed_streams: list[dict[str, str]],
    operations_by_key: dict[tuple[str, str, str, str, str, str, str], dict[str, str]],
) -> list[dict[str, str]]:
    seed_by_id = {row.get("seed_id", ""): row for row in seed_streams}
    output: list[dict[str, str]] = []
    for row in phase_rows:
        seed = seed_by_id.get(row.get("seed_id", ""), {})
        operation = operations_by_key.get(phase_key(row), {})
        window = safe_bytes_fromhex(operation.get("control_window_hex", row.get("control_window_hex", "")))
        offset = int_value(row, "source_offset")
        expected_mod64 = int_value(operation, "expected_mod64")
        prev_zero_bucket = seed.get("prev_zero_length_bucket", "")
        next_zero_bucket = seed.get("next_zero_length_bucket", "")
        prev_zero_len = int_value({"value": prev_zero_bucket.split("-")[0] if prev_zero_bucket[:1].isdigit() else ""}, "value")
        next_zero_len = int_value({"value": next_zero_bucket.split("-")[0] if next_zero_bucket[:1].isdigit() else ""}, "value")
        value_row = {
            "seed_id": row.get("seed_id", ""),
            "rank": row.get("rank", ""),
            "archive": row.get("archive", ""),
            "archive_tag": row.get("archive_tag", ""),
            "pcx_name": row.get("pcx_name", ""),
            "frontier_id": row.get("frontier_id", ""),
            "op_index": row.get("op_index", ""),
            "start": row.get("start", ""),
            "end": row.get("end", ""),
            "length": row.get("length", ""),
            "candidate_kind": row.get("candidate_kind", ""),
            "palette_index": row.get("palette_index", ""),
            "source_value_hex": row.get("source_value_hex", ""),
            "target_value_hex": row.get("target_value_hex", ""),
            "delta": row.get("delta", ""),
            "source_offset": row.get("source_offset", ""),
            "value_bytes": row.get("value_bytes", "0"),
            "copy_unlock_bytes": row.get("copy_unlock_bytes", "0"),
            "frontier_type": seed.get("frontier_type", ""),
            "strategy": seed.get("strategy", ""),
            "current_op_kind": seed.get("current_op_kind", ""),
            "current_length_bucket": seed.get("current_length_bucket", ""),
            "current_expected_mod64": seed.get("current_expected_mod64", ""),
            "current_control_ref_mod64": seed.get("current_control_ref_mod64", ""),
            "control_window_len": str(len(window)),
            "kind_pattern_r2": seed.get("kind_pattern_r2", ""),
            "kind_pattern_r4": seed.get("kind_pattern_r4", ""),
            "length_bucket_pattern_r2": seed.get("length_bucket_pattern_r2", ""),
            "length_bucket_pattern_r4": seed.get("length_bucket_pattern_r4", ""),
            "source_offset_zone": source_offset_zone(offset, len(window)),
            "source_offset_bucket4": f"{(offset // 4) * 4}-{((offset // 4) * 4) + 3}" if offset >= 0 else "",
            "source_offset_vs_prev_zero_bucket": signed_bucket(offset - prev_zero_len) if prev_zero_len else "",
            "source_offset_vs_next_zero_bucket": signed_bucket(offset - next_zero_len) if next_zero_len else "",
            "source_offset_vs_expected_mod64_bucket": signed_bucket(offset - expected_mod64),
            "source_token_class": byte_class(window, offset),
            "prev_token_class": byte_class(window, offset - 1),
            "next_token_class": byte_class(window, offset + 1),
            "semantic_entries": "0",
            "issues": ";".join(
                dict.fromkeys(
                    [issue for issue in row.get("issues", "").split(";") if issue]
                    + [issue for issue in seed.get("issues", "").split(";") if issue]
                )
            ),
        }
        value_row["semantic_entries"] = str(len(semantic_entries(value_row)))
        output.append(value_row)
    output.sort(key=lambda row: (row.get("pcx_name", ""), int_value(row, "frontier_id"), int_value(row, "palette_index")))
    return output


def semantic_entries(row: dict[str, str]) -> list[tuple[str, str, str]]:
    entries = [
        ("op_context", "frontier_type", row.get("frontier_type", "")),
        ("op_context", "strategy", row.get("strategy", "")),
        ("op_context", "current_op_kind", row.get("current_op_kind", "")),
        ("op_context", "current_length_bucket", row.get("current_length_bucket", "")),
        ("op_context", "current_expected_mod64", row.get("current_expected_mod64", "")),
        ("op_context", "current_control_ref_mod64", row.get("current_control_ref_mod64", "")),
        ("op_context", "kind_length", f"{row.get('current_op_kind', '')}|{row.get('current_length_bucket', '')}"),
        ("op_neighborhood", "kind_pattern_r2", row.get("kind_pattern_r2", "")),
        ("op_neighborhood", "kind_pattern_r4", row.get("kind_pattern_r4", "")),
        ("op_neighborhood", "length_bucket_pattern_r2", row.get("length_bucket_pattern_r2", "")),
        ("op_neighborhood", "length_bucket_pattern_r4", row.get("length_bucket_pattern_r4", "")),
        ("op_neighborhood", "kind_len_r2", f"{row.get('kind_pattern_r2', '')}|{row.get('length_bucket_pattern_r2', '')}"),
        ("source_role", "source_offset_zone", row.get("source_offset_zone", "")),
        ("source_role", "source_offset_bucket4", row.get("source_offset_bucket4", "")),
        ("source_role", "source_offset_vs_prev_zero", row.get("source_offset_vs_prev_zero_bucket", "")),
        ("source_role", "source_offset_vs_next_zero", row.get("source_offset_vs_next_zero_bucket", "")),
        ("source_role", "source_offset_vs_expected_mod64", row.get("source_offset_vs_expected_mod64_bucket", "")),
        ("control_token", "source_token_class", row.get("source_token_class", "")),
        ("control_token", "prev_token_class", row.get("prev_token_class", "")),
        ("control_token", "next_token_class", row.get("next_token_class", "")),
        ("control_token", "token_triplet_class", f"{row.get('prev_token_class', '')}|{row.get('source_token_class', '')}|{row.get('next_token_class', '')}"),
        ("semantic_combo", "kind_pattern_source_zone", f"{row.get('kind_pattern_r2', '')}|{row.get('source_offset_zone', '')}"),
        ("semantic_combo", "kind_length_token", f"{row.get('current_length_bucket', '')}|{row.get('source_token_class', '')}"),
        ("semantic_combo", "strategy_source_zone", f"{row.get('strategy', '')}|{row.get('source_offset_zone', '')}"),
        ("semantic_combo", "expected_mod64_source_zone", f"{row.get('current_expected_mod64', '')}|{row.get('source_offset_zone', '')}"),
    ]
    return [(scope, family, key) for scope, family, key in entries if key]


def build_selector_rows(semantic_values: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in semantic_values:
        for scope, family, key in semantic_entries(row):
            grouped[scope, family, key].append(row)

    output: list[dict[str, str]] = []
    for (scope, family, key), rows in grouped.items():
        deltas = {int_value(row, "delta") for row in rows}
        seed_rows = {row.get("seed_id", "") for row in rows}
        deterministic = len(deltas) == 1
        repeated_deterministic = deterministic and len(seed_rows) > 1
        if repeated_deterministic:
            verdict = "semantic_opcode_repeated_delta_candidate"
        elif deterministic:
            verdict = "semantic_opcode_singleton_delta_review"
        else:
            verdict = "semantic_opcode_delta_conflict"
        sample = rows[0]
        output.append(
            {
                "semantic_scope": scope,
                "semantic_family": family,
                "semantic_key": key,
                "rows": str(len(rows)),
                "seed_rows": str(len(seed_rows)),
                "value_bytes": str(sum(int_value(row, "value_bytes") for row in rows)),
                "deltas_seen": stable_deltas(rows),
                "deterministic": "1" if deterministic else "0",
                "repeated_deterministic": "1" if repeated_deterministic else "0",
                "verdict": verdict,
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
            }
        )
    output.sort(
        key=lambda row: (
            row.get("semantic_scope", ""),
            row.get("semantic_family", ""),
            -int_value(row, "repeated_deterministic"),
            -int_value(row, "value_bytes"),
            row.get("semantic_key", ""),
        )
    )
    return output


def build_family_rows(selector_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in selector_rows:
        grouped[row.get("semantic_scope", ""), row.get("semantic_family", "")].append(row)

    output: list[dict[str, str]] = []
    for (scope, family), rows in grouped.items():
        deterministic = [row for row in rows if row.get("deterministic") == "1"]
        repeated = [row for row in rows if row.get("repeated_deterministic") == "1"]
        singleton = [row for row in deterministic if row.get("repeated_deterministic") != "1"]
        conflicted = [row for row in rows if row.get("deterministic") != "1"]
        if repeated:
            verdict = "semantic_opcode_candidate"
        elif deterministic:
            verdict = "semantic_opcode_singleton_only"
        else:
            verdict = "semantic_opcode_blocked"
        output.append(
            {
                "semantic_scope": scope,
                "semantic_family": family,
                "groups": str(len(rows)),
                "rows": str(sum(int_value(row, "rows") for row in rows)),
                "value_bytes": str(sum(int_value(row, "value_bytes") for row in rows)),
                "deterministic_groups": str(len(deterministic)),
                "deterministic_bytes": str(sum(int_value(row, "value_bytes") for row in deterministic)),
                "repeated_deterministic_groups": str(len(repeated)),
                "repeated_deterministic_bytes": str(sum(int_value(row, "value_bytes") for row in repeated)),
                "singleton_deterministic_groups": str(len(singleton)),
                "singleton_deterministic_bytes": str(sum(int_value(row, "value_bytes") for row in singleton)),
                "conflicted_groups": str(len(conflicted)),
                "conflicted_bytes": str(sum(int_value(row, "value_bytes") for row in conflicted)),
                "verdict": verdict,
            }
        )
    output.sort(
        key=lambda row: (
            -int_value(row, "repeated_deterministic_bytes"),
            -int_value(row, "deterministic_bytes"),
            -int_value(row, "conflicted_bytes"),
            row.get("semantic_scope", ""),
            row.get("semantic_family", ""),
        )
    )
    return output


def build_scope_rows(family_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in family_rows:
        grouped[row.get("semantic_scope", "")].append(row)

    output: list[dict[str, str]] = []
    for scope, rows in grouped.items():
        repeated_groups = sum(int_value(row, "repeated_deterministic_groups") for row in rows)
        deterministic_groups = sum(int_value(row, "deterministic_groups") for row in rows)
        if repeated_groups:
            verdict = "semantic_opcode_scope_candidate"
        elif deterministic_groups:
            verdict = "semantic_opcode_scope_singleton_only"
        else:
            verdict = "semantic_opcode_scope_blocked"
        output.append(
            {
                "semantic_scope": scope,
                "families": str(len(rows)),
                "groups": str(sum(int_value(row, "groups") for row in rows)),
                "rows": str(sum(int_value(row, "rows") for row in rows)),
                "value_bytes": str(sum(int_value(row, "value_bytes") for row in rows)),
                "deterministic_groups": str(deterministic_groups),
                "deterministic_bytes": str(sum(int_value(row, "deterministic_bytes") for row in rows)),
                "repeated_deterministic_groups": str(repeated_groups),
                "repeated_deterministic_bytes": str(
                    sum(int_value(row, "repeated_deterministic_bytes") for row in rows)
                ),
                "singleton_deterministic_groups": str(
                    sum(int_value(row, "singleton_deterministic_groups") for row in rows)
                ),
                "singleton_deterministic_bytes": str(
                    sum(int_value(row, "singleton_deterministic_bytes") for row in rows)
                ),
                "conflicted_groups": str(sum(int_value(row, "conflicted_groups") for row in rows)),
                "conflicted_bytes": str(sum(int_value(row, "conflicted_bytes") for row in rows)),
                "verdict": verdict,
            }
        )
    output.sort(
        key=lambda row: (
            -int_value(row, "repeated_deterministic_bytes"),
            -int_value(row, "deterministic_bytes"),
            row.get("semantic_scope", ""),
        )
    )
    return output


def repeated_bytes_for_scope(scope_rows: list[dict[str, str]], scope: str) -> str:
    return str(
        sum(
            int_value(row, "repeated_deterministic_bytes")
            for row in scope_rows
            if row.get("semantic_scope", "") == scope
        )
    )


def build_summary(
    seed_streams: list[dict[str, str]],
    semantic_values: list[dict[str, str]],
    selector_rows: list[dict[str, str]],
    family_rows: list[dict[str, str]],
    scope_rows: list[dict[str, str]],
) -> dict[str, str]:
    deterministic = [row for row in selector_rows if row.get("deterministic") == "1"]
    repeated = [row for row in selector_rows if row.get("repeated_deterministic") == "1"]
    singleton = [row for row in deterministic if row.get("repeated_deterministic") != "1"]
    conflicted = [row for row in selector_rows if row.get("deterministic") != "1"]
    best_family = max(
        family_rows,
        key=lambda row: (
            int_value(row, "repeated_deterministic_bytes"),
            int_value(row, "deterministic_bytes"),
            -int_value(row, "conflicted_bytes"),
        ),
        default={},
    )
    best_conflicted = max(family_rows, key=lambda row: int_value(row, "conflicted_bytes"), default={})
    return {
        "scope": "total",
        "seed_rows": str(len(seed_streams)),
        "mapping_rows": str(len(semantic_values)),
        "mapping_value_bytes": str(sum(int_value(row, "value_bytes") for row in semantic_values)),
        "operation_context_rows": str(sum(1 for row in seed_streams if row.get("current_op_kind"))),
        "semantic_scopes": str(len(scope_rows)),
        "semantic_families": str(len(family_rows)),
        "semantic_groups": str(len(selector_rows)),
        "deterministic_groups": str(len(deterministic)),
        "deterministic_bytes": str(sum(int_value(row, "value_bytes") for row in deterministic)),
        "repeated_deterministic_groups": str(len(repeated)),
        "repeated_deterministic_bytes": str(sum(int_value(row, "value_bytes") for row in repeated)),
        "singleton_deterministic_groups": str(len(singleton)),
        "singleton_deterministic_bytes": str(sum(int_value(row, "value_bytes") for row in singleton)),
        "conflicted_groups": str(len(conflicted)),
        "conflicted_bytes": str(sum(int_value(row, "value_bytes") for row in conflicted)),
        "op_context_repeated_bytes": repeated_bytes_for_scope(scope_rows, "op_context"),
        "op_neighborhood_repeated_bytes": repeated_bytes_for_scope(scope_rows, "op_neighborhood"),
        "source_role_repeated_bytes": repeated_bytes_for_scope(scope_rows, "source_role"),
        "control_token_repeated_bytes": repeated_bytes_for_scope(scope_rows, "control_token"),
        "semantic_combo_repeated_bytes": repeated_bytes_for_scope(scope_rows, "semantic_combo"),
        "best_semantic_family": best_family.get("semantic_family", ""),
        "best_semantic_repeated_bytes": best_family.get("repeated_deterministic_bytes", "0"),
        "best_semantic_conflicted_bytes": best_conflicted.get("conflicted_bytes", "0"),
        "kind_patterns": str(len({row.get("kind_pattern_r4", "") for row in seed_streams})),
        "length_patterns": str(len({row.get("length_bucket_pattern_r4", "") for row in seed_streams})),
        "copy_unlock_rows": str(sum(1 for row in seed_streams if int_value(row, "copy_unlock_bytes"))),
        "copy_unlock_bytes": str(sum(int_value(row, "copy_unlock_bytes") for row in seed_streams)),
        "total_potential_bytes": str(
            sum(int_value(row, "value_bytes") for row in semantic_values)
            + sum(int_value(row, "copy_unlock_bytes") for row in seed_streams)
        ),
        "promotion_ready_bytes": "0",
        "issue_rows": str(
            sum(1 for row in seed_streams if row.get("issues"))
            + sum(1 for row in semantic_values if row.get("issues"))
        ),
    }


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 220) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    seed_streams: list[dict[str, str]],
    semantic_values: list[dict[str, str]],
    selector_rows: list[dict[str, str]],
    family_rows: list[dict[str, str]],
    scope_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    files = [
        ("summary.csv", output_dir / "summary.csv"),
        ("seed_streams.csv", output_dir / "seed_streams.csv"),
        ("semantic_values.csv", output_dir / "semantic_values.csv"),
        ("by_semantic_selector.csv", output_dir / "by_semantic_selector.csv"),
        ("by_semantic_family.csv", output_dir / "by_semantic_family.csv"),
        ("by_semantic_scope.csv", output_dir / "by_semantic_scope.csv"),
    ]
    links = " ".join(
        f'<a href="{html.escape(relative_href(output_dir / "index.html", path))}">{html.escape(label)}</a>'
        for label, path in files
    )
    data_json = json.dumps(
        {
            "summary": summary,
            "scopeRows": scope_rows,
            "familyRows": family_rows,
            "selectorRows": selector_rows[:160],
            "seedStreams": seed_streams,
            "semanticValues": semantic_values,
        },
        ensure_ascii=True,
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
:root {{ color-scheme: dark; --bg: #0d1113; --panel: #151b1e; --line: #2b3438; --text: #e7ecef; --muted: #9aa8ae; --accent: #7cc7ff; --ok: #7bd88f; --warn: #f6c177; }}
body {{ margin: 0; background: var(--bg); color: var(--text); font: 14px/1.45 system-ui, -apple-system, Segoe UI, sans-serif; }}
.wrap {{ max-width: 1480px; margin: 0 auto; padding: 0 16px; }}
header {{ border-bottom: 1px solid var(--line); background: #12191b; padding: 18px 0 14px; }}
h1 {{ margin: 0; font-size: 21px; font-weight: 720; letter-spacing: 0; }}
h2 {{ margin: 0 0 10px; font-size: 16px; }}
.sub {{ color: var(--muted); margin-top: 4px; }}
main {{ padding: 16px 0 28px; display: grid; gap: 16px; }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 10px; }}
.stat, .panel {{ border: 1px solid var(--line); border-radius: 8px; background: var(--panel); padding: 10px; }}
.label, .muted {{ color: var(--muted); }}
.value {{ font-size: 22px; font-weight: 760; line-height: 1.05; margin-top: 4px; }}
.ok {{ color: var(--ok); }}
.warn {{ color: var(--warn); }}
.panel {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; min-width: 1500px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Checks semantic operation neighborhoods for the gradient seed delta selector.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Seed rows</div><div class="value">{summary['seed_rows']}</div></div>
    <div class="stat"><div class="label">Mapping bytes</div><div class="value warn">{summary['mapping_value_bytes']}</div></div>
    <div class="stat"><div class="label">Semantic groups</div><div class="value">{summary['semantic_groups']}</div></div>
    <div class="stat"><div class="label">Repeated bytes</div><div class="value">{summary['repeated_deterministic_bytes']}</div></div>
    <div class="stat"><div class="label">Conflicted bytes</div><div class="value warn">{summary['conflicted_bytes']}</div></div>
    <div class="stat"><div class="label">Promotion-ready bytes</div><div class="value ok">{summary['promotion_ready_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2><div>{links}</div></section>
  <section class="panel"><h2>Semantic scopes</h2>{render_table(scope_rows, SCOPE_FIELDNAMES)}</section>
  <section class="panel"><h2>Semantic families</h2>{render_table(family_rows, FAMILY_FIELDNAMES)}</section>
  <section class="panel"><h2>Semantic selectors</h2>{render_table(selector_rows, SELECTOR_FIELDNAMES)}</section>
  <section class="panel"><h2>Seed streams</h2>{render_table(seed_streams, SEED_STREAM_FIELDNAMES)}</section>
  <section class="panel"><h2>Semantic values</h2>{render_table(semantic_values, SEMANTIC_VALUE_FIELDNAMES)}</section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_GRADIENT_SEED_DELTA_SEMANTIC_OPCODE_PROBE = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe semantic opcode context for .tex gradient seed deltas.")
    parser.add_argument("--phase-values", type=Path, default=DEFAULT_PHASE_VALUES)
    parser.add_argument("--operations", type=Path, default=DEFAULT_OPERATIONS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Tiny Nonzero Gap Gradient Seed Delta Semantic Opcode Probe",
    )
    args = parser.parse_args()

    phase_rows = read_csv(args.phase_values)
    operations = read_csv(args.operations)
    operations_by_key, operations_by_group = build_operation_indexes(operations)
    seed_streams = build_seed_streams(phase_rows, operations_by_key, operations_by_group)
    semantic_values = build_semantic_values(phase_rows, seed_streams, operations_by_key)
    selector_rows = build_selector_rows(semantic_values)
    family_rows = build_family_rows(selector_rows)
    scope_rows = build_scope_rows(family_rows)
    summary = build_summary(seed_streams, semantic_values, selector_rows, family_rows, scope_rows)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "seed_streams.csv", SEED_STREAM_FIELDNAMES, seed_streams)
    write_csv(args.output / "semantic_values.csv", SEMANTIC_VALUE_FIELDNAMES, semantic_values)
    write_csv(args.output / "by_semantic_selector.csv", SELECTOR_FIELDNAMES, selector_rows)
    write_csv(args.output / "by_semantic_family.csv", FAMILY_FIELDNAMES, family_rows)
    write_csv(args.output / "by_semantic_scope.csv", SCOPE_FIELDNAMES, scope_rows)
    html_path = args.output / "index.html"
    html_path.write_text(
        build_html(summary, seed_streams, semantic_values, selector_rows, family_rows, scope_rows, args.output, args.title)
    )

    print(f"Seed rows: {summary['seed_rows']}")
    print(f"Mapping bytes: {summary['mapping_value_bytes']}")
    print(f"Semantic groups: {summary['semantic_groups']}")
    print(f"Repeated deterministic bytes: {summary['repeated_deterministic_bytes']}")
    print(f"Conflicted bytes: {summary['conflicted_bytes']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
