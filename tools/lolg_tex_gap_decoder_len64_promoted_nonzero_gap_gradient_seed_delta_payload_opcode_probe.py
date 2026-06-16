#!/usr/bin/env python3
"""Probe payload opcode-token candidates for gradient seed delta selectors."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import defaultdict
from pathlib import Path

from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_delta_payload_opcode_probe"
)
DEFAULT_PHASE_VALUES = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_delta_phase_probe/phase_values.csv"
)
DEFAULT_SEQUENCE_ROWS = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_delta_opcode_sequence_probe/sequence_rows.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "seed_rows",
    "mapping_rows",
    "mapping_value_bytes",
    "payload_window_bytes",
    "token_scopes",
    "token_families",
    "token_groups",
    "deterministic_groups",
    "deterministic_bytes",
    "repeated_deterministic_groups",
    "repeated_deterministic_bytes",
    "singleton_deterministic_groups",
    "singleton_deterministic_bytes",
    "conflicted_groups",
    "conflicted_bytes",
    "raw_byte_repeated_bytes",
    "bitfield_repeated_bytes",
    "local_ngram_repeated_bytes",
    "offset_token_repeated_bytes",
    "sequence_role_repeated_bytes",
    "payload_combo_repeated_bytes",
    "best_token_family",
    "best_token_repeated_bytes",
    "best_token_conflicted_bytes",
    "window_signatures",
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
    "span_index",
    "run_index",
    "op_index",
    "start",
    "end",
    "length",
    "candidate_kind",
    "palette_size",
    "mapping_rows",
    "mapping_value_bytes",
    "copy_unlock_bytes",
    "control_window_len",
    "control_window_hex",
    "source_offsets",
    "source_values_hex",
    "target_values_hex",
    "deltas",
    "value_bytes",
    "offset_steps",
    "offset_direction_pattern",
    "source_value_steps",
    "delta_steps",
    "unique_source_offsets",
    "reused_source_offsets",
    "offset_reuse_bytes",
    "payload_signature",
    "issues",
]

TOKEN_VALUE_FIELDNAMES = [
    "seed_id",
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "span_index",
    "run_index",
    "op_index",
    "start",
    "end",
    "length",
    "candidate_kind",
    "palette_index",
    "source_offset",
    "source_value_hex",
    "target_value_hex",
    "delta",
    "value_bytes",
    "copy_unlock_bytes",
    "control_window_len",
    "prev2_byte_hex",
    "prev_byte_hex",
    "source_byte_hex",
    "next_byte_hex",
    "next2_byte_hex",
    "pair_prev_cur_hex",
    "pair_cur_next_hex",
    "triple_prev_cur_next_hex",
    "centered_5_hex",
    "rel_window_r4_hex",
    "rel_window_r8_hex",
    "source_high_nibble",
    "source_low_nibble",
    "source_top2",
    "source_low2",
    "source_parity",
    "source_byte_class",
    "neighbor_high_pattern",
    "neighbor_low_pattern",
    "source_offset_mod2",
    "source_offset_mod4",
    "source_offset_bucket4",
    "source_offset_zone",
    "palette_index_mod2",
    "palette_index_mod4",
    "prev_source_offset",
    "next_source_offset",
    "prev_source_value_hex",
    "next_source_value_hex",
    "prev_offset_step",
    "next_offset_step",
    "prev_offset_step_bucket",
    "next_offset_step_bucket",
    "prev_source_value_step",
    "next_source_value_step",
    "prev_source_value_step_bucket",
    "next_source_value_step_bucket",
    "token_entries",
    "issues",
]

SELECTOR_FIELDNAMES = [
    "token_scope",
    "token_family",
    "token_key",
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
    "token_scope",
    "token_family",
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
    "token_scope",
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


def byte_at(window: bytes, offset: int) -> int | None:
    if offset < 0 or offset >= len(window):
        return None
    return window[offset]


def byte_hex(value: int | None) -> str:
    return "" if value is None else f"0x{value:02x}"


def bytes_hex(window: bytes, start: int, end: int) -> str:
    start = max(0, start)
    end = min(len(window), end)
    if start >= end:
        return ""
    return window[start:end].hex()


def low_nibble_bucket(low: int) -> str:
    if low <= 3:
        return "0-3"
    if low <= 7:
        return "4-7"
    if low <= 11:
        return "8-b"
    return "c-f"


def byte_class(value: int | None) -> str:
    if value is None:
        return ""
    if value == 0:
        return "zero"
    high = value >> 4
    low = value & 0x0F
    if high == low:
        return f"same_nibble_{high:x}"
    return f"hi{high:x}_lo{low_nibble_bucket(low)}"


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


def signed_byte_step(current: int | None, previous: int | None) -> int | None:
    if current is None or previous is None:
        return None
    step = current - previous
    if step > 127:
        step -= 256
    if step < -128:
        step += 256
    return step


def maybe_str(value: int | None) -> str:
    return "" if value is None else str(value)


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


def build_seed_streams(phase_rows: list[dict[str, str]], sequence_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    sequence_by_seed = {row.get("seed_id", ""): row for row in sequence_rows}
    output: list[dict[str, str]] = []
    for rows in seed_groups(phase_rows):
        first = rows[0]
        sequence = sequence_by_seed.get(first.get("seed_id", ""), {})
        window = safe_bytes_fromhex(first.get("control_window_hex", ""))
        source_offsets = [row.get("source_offset", "") for row in rows]
        source_values = [row.get("source_value_hex", "") for row in rows]
        target_values = [row.get("target_value_hex", "") for row in rows]
        deltas = [row.get("delta", "") for row in rows]
        value_bytes = [row.get("value_bytes", "0") for row in rows]
        source_offset_counts: dict[str, int] = defaultdict(int)
        for offset in source_offsets:
            source_offset_counts[offset] += 1
        reused_offsets = [offset for offset, count in source_offset_counts.items() if count > 1 and offset]
        row = {
            "seed_id": first.get("seed_id", ""),
            "rank": first.get("rank", ""),
            "archive": first.get("archive", ""),
            "archive_tag": first.get("archive_tag", ""),
            "pcx_name": first.get("pcx_name", ""),
            "frontier_id": first.get("frontier_id", ""),
            "span_index": first.get("span_index", ""),
            "run_index": first.get("run_index", ""),
            "op_index": first.get("op_index", ""),
            "start": first.get("start", ""),
            "end": first.get("end", ""),
            "length": first.get("length", ""),
            "candidate_kind": first.get("candidate_kind", ""),
            "palette_size": str(len(rows)),
            "mapping_rows": str(len(rows)),
            "mapping_value_bytes": str(sum(int_value(row, "value_bytes") for row in rows)),
            "copy_unlock_bytes": first.get("copy_unlock_bytes", "0"),
            "control_window_len": str(len(window)),
            "control_window_hex": first.get("control_window_hex", ""),
            "source_offsets": sequence.get("source_offsets", "|".join(source_offsets)),
            "source_values_hex": sequence.get("source_values_hex", "|".join(source_values)),
            "target_values_hex": sequence.get("target_values_hex", "|".join(target_values)),
            "deltas": sequence.get("deltas", "|".join(deltas)),
            "value_bytes": sequence.get("value_bytes", "|".join(value_bytes)),
            "offset_steps": sequence.get("offset_steps", ""),
            "offset_direction_pattern": sequence.get("offset_direction_pattern", ""),
            "source_value_steps": sequence.get("source_value_steps", ""),
            "delta_steps": sequence.get("delta_steps", ""),
            "unique_source_offsets": sequence.get("unique_source_offsets", str(len(source_offset_counts))),
            "reused_source_offsets": sequence.get("reused_source_offsets", str(len(reused_offsets))),
            "offset_reuse_bytes": sequence.get(
                "offset_reuse_bytes",
                str(sum(int_value(row, "value_bytes") for row in rows if row.get("source_offset") in reused_offsets)),
            ),
            "payload_signature": (
                f"offsets={'|'.join(source_offsets)};"
                f"sources={'|'.join(source_values)};"
                f"deltas={'|'.join(deltas)}"
            ),
            "issues": ";".join(
                dict.fromkeys(issue for row in rows for issue in row.get("issues", "").split(";") if issue)
            ),
        }
        output.append(row)
    return output


def build_token_values(phase_rows: list[dict[str, str]], seed_streams: list[dict[str, str]]) -> list[dict[str, str]]:
    seed_by_id = {row.get("seed_id", ""): row for row in seed_streams}
    by_seed: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in phase_rows:
        by_seed[row.get("seed_id", "")].append(row)
    for rows in by_seed.values():
        rows.sort(key=lambda row: int_value(row, "palette_index"))

    output: list[dict[str, str]] = []
    for seed_id, rows in by_seed.items():
        seed = seed_by_id.get(seed_id, {})
        for index, row in enumerate(rows):
            window = safe_bytes_fromhex(row.get("control_window_hex", ""))
            offset = int_value(row, "source_offset")
            source_value = byte_at(window, offset)
            if source_value is None and row.get("source_value_hex"):
                source_value = int(row.get("source_value_hex", "0x00"), 16)
            prev_row = rows[index - 1] if index > 0 else {}
            next_row = rows[index + 1] if index + 1 < len(rows) else {}
            prev_offset = int_value(prev_row, "source_offset") if prev_row else None
            next_offset = int_value(next_row, "source_offset") if next_row else None
            prev_value = int(prev_row.get("source_value_hex", "0x00"), 16) if prev_row else None
            next_value = int(next_row.get("source_value_hex", "0x00"), 16) if next_row else None
            prev_offset_step = offset - prev_offset if prev_offset is not None else None
            next_offset_step = next_offset - offset if next_offset is not None else None
            prev_source_step = signed_byte_step(source_value, prev_value)
            next_source_step = signed_byte_step(next_value, source_value)
            b_prev2 = byte_at(window, offset - 2)
            b_prev = byte_at(window, offset - 1)
            b_cur = byte_at(window, offset)
            b_next = byte_at(window, offset + 1)
            b_next2 = byte_at(window, offset + 2)
            high_values = [
                "" if value is None else f"{value >> 4:x}" for value in [b_prev, b_cur, b_next]
            ]
            low_values = [
                "" if value is None else f"{value & 0x0F:x}" for value in [b_prev, b_cur, b_next]
            ]
            token_row = {
                "seed_id": row.get("seed_id", ""),
                "rank": row.get("rank", ""),
                "archive": row.get("archive", ""),
                "archive_tag": row.get("archive_tag", ""),
                "pcx_name": row.get("pcx_name", ""),
                "frontier_id": row.get("frontier_id", ""),
                "span_index": row.get("span_index", ""),
                "run_index": row.get("run_index", ""),
                "op_index": row.get("op_index", ""),
                "start": row.get("start", ""),
                "end": row.get("end", ""),
                "length": row.get("length", ""),
                "candidate_kind": row.get("candidate_kind", ""),
                "palette_index": row.get("palette_index", ""),
                "source_offset": row.get("source_offset", ""),
                "source_value_hex": row.get("source_value_hex", byte_hex(source_value)),
                "target_value_hex": row.get("target_value_hex", ""),
                "delta": row.get("delta", ""),
                "value_bytes": row.get("value_bytes", "0"),
                "copy_unlock_bytes": row.get("copy_unlock_bytes", "0"),
                "control_window_len": str(len(window)),
                "prev2_byte_hex": byte_hex(b_prev2),
                "prev_byte_hex": byte_hex(b_prev),
                "source_byte_hex": byte_hex(b_cur),
                "next_byte_hex": byte_hex(b_next),
                "next2_byte_hex": byte_hex(b_next2),
                "pair_prev_cur_hex": bytes_hex(window, offset - 1, offset + 1),
                "pair_cur_next_hex": bytes_hex(window, offset, offset + 2),
                "triple_prev_cur_next_hex": bytes_hex(window, offset - 1, offset + 2),
                "centered_5_hex": bytes_hex(window, offset - 2, offset + 3),
                "rel_window_r4_hex": row.get("rel_window_r4_hex", bytes_hex(window, offset - 4, offset + 5)),
                "rel_window_r8_hex": row.get("rel_window_r8_hex", bytes_hex(window, offset - 8, offset + 9)),
                "source_high_nibble": "" if source_value is None else f"{source_value >> 4:x}",
                "source_low_nibble": "" if source_value is None else f"{source_value & 0x0F:x}",
                "source_top2": "" if source_value is None else str(source_value >> 6),
                "source_low2": "" if source_value is None else str(source_value & 0x03),
                "source_parity": "" if source_value is None else str(source_value & 1),
                "source_byte_class": byte_class(source_value),
                "neighbor_high_pattern": "|".join(high_values),
                "neighbor_low_pattern": "|".join(low_values),
                "source_offset_mod2": str(offset % 2),
                "source_offset_mod4": str(offset % 4),
                "source_offset_bucket4": f"{(offset // 4) * 4}-{((offset // 4) * 4) + 3}" if offset >= 0 else "",
                "source_offset_zone": source_offset_zone(offset, len(window)),
                "palette_index_mod2": str(int_value(row, "palette_index") % 2),
                "palette_index_mod4": str(int_value(row, "palette_index") % 4),
                "prev_source_offset": maybe_str(prev_offset),
                "next_source_offset": maybe_str(next_offset),
                "prev_source_value_hex": byte_hex(prev_value),
                "next_source_value_hex": byte_hex(next_value),
                "prev_offset_step": maybe_str(prev_offset_step),
                "next_offset_step": maybe_str(next_offset_step),
                "prev_offset_step_bucket": "" if prev_offset_step is None else signed_bucket(prev_offset_step),
                "next_offset_step_bucket": "" if next_offset_step is None else signed_bucket(next_offset_step),
                "prev_source_value_step": maybe_str(prev_source_step),
                "next_source_value_step": maybe_str(next_source_step),
                "prev_source_value_step_bucket": "" if prev_source_step is None else signed_bucket(prev_source_step),
                "next_source_value_step_bucket": "" if next_source_step is None else signed_bucket(next_source_step),
                "token_entries": "0",
                "issues": ";".join(
                    dict.fromkeys(
                        [issue for issue in row.get("issues", "").split(";") if issue]
                        + [issue for issue in seed.get("issues", "").split(";") if issue]
                    )
                ),
            }
            token_row["token_entries"] = str(len(token_entries(token_row)))
            output.append(token_row)
    output.sort(key=lambda row: (row.get("pcx_name", ""), int_value(row, "frontier_id"), int_value(row, "palette_index")))
    return output


def token_entries(row: dict[str, str]) -> list[tuple[str, str, str]]:
    entries = [
        ("raw_byte", "source_byte", row.get("source_byte_hex", "")),
        ("raw_byte", "prev_byte", row.get("prev_byte_hex", "")),
        ("raw_byte", "next_byte", row.get("next_byte_hex", "")),
        ("raw_byte", "prev2_byte", row.get("prev2_byte_hex", "")),
        ("raw_byte", "next2_byte", row.get("next2_byte_hex", "")),
        ("raw_byte", "pair_prev_cur", row.get("pair_prev_cur_hex", "")),
        ("raw_byte", "pair_cur_next", row.get("pair_cur_next_hex", "")),
        ("raw_byte", "triple_prev_cur_next", row.get("triple_prev_cur_next_hex", "")),
        ("bitfield", "source_high_nibble", row.get("source_high_nibble", "")),
        ("bitfield", "source_low_nibble", row.get("source_low_nibble", "")),
        ("bitfield", "source_top2", row.get("source_top2", "")),
        ("bitfield", "source_low2", row.get("source_low2", "")),
        ("bitfield", "source_parity", row.get("source_parity", "")),
        ("bitfield", "source_byte_class", row.get("source_byte_class", "")),
        ("bitfield", "neighbor_high_pattern", row.get("neighbor_high_pattern", "")),
        ("bitfield", "neighbor_low_pattern", row.get("neighbor_low_pattern", "")),
        ("local_ngram", "centered_5", row.get("centered_5_hex", "")),
        ("local_ngram", "rel_window_r4", row.get("rel_window_r4_hex", "")),
        ("local_ngram", "rel_window_r8", row.get("rel_window_r8_hex", "")),
        ("offset_token", "source_offset", row.get("source_offset", "")),
        ("offset_token", "source_offset_mod2", row.get("source_offset_mod2", "")),
        ("offset_token", "source_offset_mod4", row.get("source_offset_mod4", "")),
        ("offset_token", "source_offset_bucket4", row.get("source_offset_bucket4", "")),
        ("offset_token", "source_offset_zone", row.get("source_offset_zone", "")),
        ("offset_token", "offset_mod4_source_high", f"{row.get('source_offset_mod4', '')}|{row.get('source_high_nibble', '')}"),
        ("offset_token", "offset_bucket_source_byte", f"{row.get('source_offset_bucket4', '')}|{row.get('source_byte_hex', '')}"),
        ("sequence_role", "palette_index", row.get("palette_index", "")),
        ("sequence_role", "palette_index_mod2", row.get("palette_index_mod2", "")),
        ("sequence_role", "palette_index_mod4", row.get("palette_index_mod4", "")),
        ("sequence_role", "prev_offset_step", row.get("prev_offset_step", "")),
        ("sequence_role", "next_offset_step", row.get("next_offset_step", "")),
        ("sequence_role", "prev_offset_step_bucket", row.get("prev_offset_step_bucket", "")),
        ("sequence_role", "next_offset_step_bucket", row.get("next_offset_step_bucket", "")),
        ("sequence_role", "prev_source_value_step", row.get("prev_source_value_step", "")),
        ("sequence_role", "next_source_value_step", row.get("next_source_value_step", "")),
        ("sequence_role", "prev_source_value_step_bucket", row.get("prev_source_value_step_bucket", "")),
        ("sequence_role", "next_source_value_step_bucket", row.get("next_source_value_step_bucket", "")),
        (
            "sequence_role",
            "offset_walk_bucket",
            f"{row.get('prev_offset_step_bucket', '')}|{row.get('next_offset_step_bucket', '')}",
        ),
        (
            "sequence_role",
            "source_walk_bucket",
            f"{row.get('prev_source_value_step_bucket', '')}|{row.get('next_source_value_step_bucket', '')}",
        ),
        ("payload_combo", "source_byte_offset_mod4", f"{row.get('source_byte_hex', '')}|{row.get('source_offset_mod4', '')}"),
        ("payload_combo", "source_byte_palette_mod4", f"{row.get('source_byte_hex', '')}|{row.get('palette_index_mod4', '')}"),
        ("payload_combo", "source_class_offset_mod4", f"{row.get('source_byte_class', '')}|{row.get('source_offset_mod4', '')}"),
        ("payload_combo", "source_class_palette_mod4", f"{row.get('source_byte_class', '')}|{row.get('palette_index_mod4', '')}"),
        ("payload_combo", "pair_prev_cur_offset_mod4", f"{row.get('pair_prev_cur_hex', '')}|{row.get('source_offset_mod4', '')}"),
        ("payload_combo", "pair_cur_next_offset_mod4", f"{row.get('pair_cur_next_hex', '')}|{row.get('source_offset_mod4', '')}"),
        ("payload_combo", "neighbor_high_offset_mod4", f"{row.get('neighbor_high_pattern', '')}|{row.get('source_offset_mod4', '')}"),
        ("payload_combo", "neighbor_low_offset_mod4", f"{row.get('neighbor_low_pattern', '')}|{row.get('source_offset_mod4', '')}"),
    ]
    return [(scope, family, key) for scope, family, key in entries if key and "||" not in key]


def build_selector_rows(token_values: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in token_values:
        for scope, family, key in token_entries(row):
            grouped[scope, family, key].append(row)

    output: list[dict[str, str]] = []
    for (scope, family, key), rows in grouped.items():
        deltas = {int_value(row, "delta") for row in rows}
        seed_rows = {row.get("seed_id", "") for row in rows}
        deterministic = len(deltas) == 1
        repeated_deterministic = deterministic and len(seed_rows) > 1
        if repeated_deterministic:
            verdict = "payload_opcode_repeated_delta_candidate"
        elif deterministic:
            verdict = "payload_opcode_singleton_delta_review"
        else:
            verdict = "payload_opcode_delta_conflict"
        sample = rows[0]
        output.append(
            {
                "token_scope": scope,
                "token_family": family,
                "token_key": key,
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
            row.get("token_scope", ""),
            row.get("token_family", ""),
            -int_value(row, "repeated_deterministic"),
            -int_value(row, "value_bytes"),
            row.get("token_key", ""),
        )
    )
    return output


def build_family_rows(selector_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in selector_rows:
        grouped[row.get("token_scope", ""), row.get("token_family", "")].append(row)

    output: list[dict[str, str]] = []
    for (scope, family), rows in grouped.items():
        deterministic = [row for row in rows if row.get("deterministic") == "1"]
        repeated = [row for row in rows if row.get("repeated_deterministic") == "1"]
        singleton = [row for row in deterministic if row.get("repeated_deterministic") != "1"]
        conflicted = [row for row in rows if row.get("deterministic") != "1"]
        if repeated:
            verdict = "payload_opcode_candidate"
        elif deterministic:
            verdict = "payload_opcode_singleton_only"
        else:
            verdict = "payload_opcode_blocked"
        output.append(
            {
                "token_scope": scope,
                "token_family": family,
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
            row.get("token_scope", ""),
            row.get("token_family", ""),
        )
    )
    return output


def build_scope_rows(family_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in family_rows:
        grouped[row.get("token_scope", "")].append(row)

    output: list[dict[str, str]] = []
    for scope, rows in grouped.items():
        repeated_groups = sum(int_value(row, "repeated_deterministic_groups") for row in rows)
        deterministic_groups = sum(int_value(row, "deterministic_groups") for row in rows)
        if repeated_groups:
            verdict = "payload_opcode_scope_candidate"
        elif deterministic_groups:
            verdict = "payload_opcode_scope_singleton_only"
        else:
            verdict = "payload_opcode_scope_blocked"
        output.append(
            {
                "token_scope": scope,
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
            row.get("token_scope", ""),
        )
    )
    return output


def repeated_bytes_for_scope(scope_rows: list[dict[str, str]], scope: str) -> str:
    return str(
        sum(
            int_value(row, "repeated_deterministic_bytes")
            for row in scope_rows
            if row.get("token_scope", "") == scope
        )
    )


def build_summary(
    seed_streams: list[dict[str, str]],
    token_values: list[dict[str, str]],
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
        "mapping_rows": str(len(token_values)),
        "mapping_value_bytes": str(sum(int_value(row, "value_bytes") for row in token_values)),
        "payload_window_bytes": str(sum(int_value(row, "control_window_len") for row in seed_streams)),
        "token_scopes": str(len(scope_rows)),
        "token_families": str(len(family_rows)),
        "token_groups": str(len(selector_rows)),
        "deterministic_groups": str(len(deterministic)),
        "deterministic_bytes": str(sum(int_value(row, "value_bytes") for row in deterministic)),
        "repeated_deterministic_groups": str(len(repeated)),
        "repeated_deterministic_bytes": str(sum(int_value(row, "value_bytes") for row in repeated)),
        "singleton_deterministic_groups": str(len(singleton)),
        "singleton_deterministic_bytes": str(sum(int_value(row, "value_bytes") for row in singleton)),
        "conflicted_groups": str(len(conflicted)),
        "conflicted_bytes": str(sum(int_value(row, "value_bytes") for row in conflicted)),
        "raw_byte_repeated_bytes": repeated_bytes_for_scope(scope_rows, "raw_byte"),
        "bitfield_repeated_bytes": repeated_bytes_for_scope(scope_rows, "bitfield"),
        "local_ngram_repeated_bytes": repeated_bytes_for_scope(scope_rows, "local_ngram"),
        "offset_token_repeated_bytes": repeated_bytes_for_scope(scope_rows, "offset_token"),
        "sequence_role_repeated_bytes": repeated_bytes_for_scope(scope_rows, "sequence_role"),
        "payload_combo_repeated_bytes": repeated_bytes_for_scope(scope_rows, "payload_combo"),
        "best_token_family": best_family.get("token_family", ""),
        "best_token_repeated_bytes": best_family.get("repeated_deterministic_bytes", "0"),
        "best_token_conflicted_bytes": best_conflicted.get("conflicted_bytes", "0"),
        "window_signatures": str(len({row.get("control_window_hex", "") for row in seed_streams})),
        "copy_unlock_rows": str(sum(1 for row in seed_streams if int_value(row, "copy_unlock_bytes"))),
        "copy_unlock_bytes": str(sum(int_value(row, "copy_unlock_bytes") for row in seed_streams)),
        "total_potential_bytes": str(
            sum(int_value(row, "value_bytes") for row in token_values)
            + sum(int_value(row, "copy_unlock_bytes") for row in seed_streams)
        ),
        "promotion_ready_bytes": "0",
        "issue_rows": str(
            sum(1 for row in seed_streams if row.get("issues"))
            + sum(1 for row in token_values if row.get("issues"))
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
    token_values: list[dict[str, str]],
    selector_rows: list[dict[str, str]],
    family_rows: list[dict[str, str]],
    scope_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    files = [
        ("summary.csv", output_dir / "summary.csv"),
        ("seed_streams.csv", output_dir / "seed_streams.csv"),
        ("token_values.csv", output_dir / "token_values.csv"),
        ("by_token_selector.csv", output_dir / "by_token_selector.csv"),
        ("by_token_family.csv", output_dir / "by_token_family.csv"),
        ("by_token_scope.csv", output_dir / "by_token_scope.csv"),
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
            "selectorRows": selector_rows[:180],
            "seedStreams": seed_streams,
            "tokenValues": token_values,
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
    <div class="sub">Tests raw payload bytes, bitfields, local n-grams, offsets, and sequence roles for the gradient seed delta selector.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Seed rows</div><div class="value">{summary['seed_rows']}</div></div>
    <div class="stat"><div class="label">Mapping bytes</div><div class="value warn">{summary['mapping_value_bytes']}</div></div>
    <div class="stat"><div class="label">Token groups</div><div class="value">{summary['token_groups']}</div></div>
    <div class="stat"><div class="label">Repeated bytes</div><div class="value">{summary['repeated_deterministic_bytes']}</div></div>
    <div class="stat"><div class="label">Conflicted bytes</div><div class="value warn">{summary['conflicted_bytes']}</div></div>
    <div class="stat"><div class="label">Promotion-ready bytes</div><div class="value ok">{summary['promotion_ready_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2><div>{links}</div></section>
  <section class="panel"><h2>Token scopes</h2>{render_table(scope_rows, SCOPE_FIELDNAMES)}</section>
  <section class="panel"><h2>Token families</h2>{render_table(family_rows, FAMILY_FIELDNAMES)}</section>
  <section class="panel"><h2>Token selectors</h2>{render_table(selector_rows, SELECTOR_FIELDNAMES)}</section>
  <section class="panel"><h2>Seed streams</h2>{render_table(seed_streams, SEED_STREAM_FIELDNAMES)}</section>
  <section class="panel"><h2>Token values</h2>{render_table(token_values, TOKEN_VALUE_FIELDNAMES)}</section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_GRADIENT_SEED_DELTA_PAYLOAD_OPCODE_PROBE = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe payload opcode-token candidates for .tex gradient seed deltas.")
    parser.add_argument("--phase-values", type=Path, default=DEFAULT_PHASE_VALUES)
    parser.add_argument("--sequence-rows", type=Path, default=DEFAULT_SEQUENCE_ROWS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Tiny Nonzero Gap Gradient Seed Delta Payload Opcode Probe",
    )
    args = parser.parse_args()

    phase_rows = read_csv(args.phase_values)
    sequence_rows = read_csv(args.sequence_rows)
    seed_streams = build_seed_streams(phase_rows, sequence_rows)
    token_values = build_token_values(phase_rows, seed_streams)
    selector_rows = build_selector_rows(token_values)
    family_rows = build_family_rows(selector_rows)
    scope_rows = build_scope_rows(family_rows)
    summary = build_summary(seed_streams, token_values, selector_rows, family_rows, scope_rows)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "seed_streams.csv", SEED_STREAM_FIELDNAMES, seed_streams)
    write_csv(args.output / "token_values.csv", TOKEN_VALUE_FIELDNAMES, token_values)
    write_csv(args.output / "by_token_selector.csv", SELECTOR_FIELDNAMES, selector_rows)
    write_csv(args.output / "by_token_family.csv", FAMILY_FIELDNAMES, family_rows)
    write_csv(args.output / "by_token_scope.csv", SCOPE_FIELDNAMES, scope_rows)
    html_path = args.output / "index.html"
    html_path.write_text(
        build_html(summary, seed_streams, token_values, selector_rows, family_rows, scope_rows, args.output, args.title)
    )

    print(f"Seed rows: {summary['seed_rows']}")
    print(f"Mapping bytes: {summary['mapping_value_bytes']}")
    print(f"Token groups: {summary['token_groups']}")
    print(f"Repeated deterministic bytes: {summary['repeated_deterministic_bytes']}")
    print(f"Conflicted bytes: {summary['conflicted_bytes']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
