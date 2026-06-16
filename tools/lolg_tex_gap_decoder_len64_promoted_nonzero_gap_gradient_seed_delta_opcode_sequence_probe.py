#!/usr/bin/env python3
"""Probe opcode/source ordering for gradient seed delta sequences."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_delta_opcode_sequence_probe"
)
DEFAULT_PHASE_VALUES = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_delta_phase_probe/phase_values.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "seed_rows",
    "mapping_rows",
    "mapping_value_bytes",
    "control_window_bytes",
    "sequence_signatures",
    "constant_delta_seed_rows",
    "mixed_delta_seed_rows",
    "transition_rows",
    "transition_value_bytes",
    "transition_scopes",
    "transition_families",
    "transition_groups",
    "deterministic_transition_groups",
    "deterministic_transition_bytes",
    "repeated_transition_groups",
    "repeated_transition_bytes",
    "singleton_transition_groups",
    "singleton_transition_bytes",
    "conflicted_transition_groups",
    "conflicted_transition_bytes",
    "offset_reuse_bytes",
    "backward_offset_steps",
    "zero_offset_steps",
    "forward_offset_steps",
    "plus1_delta_bytes",
    "zero_delta_bytes",
    "negative_delta_bytes",
    "best_transition_family",
    "best_transition_repeated_bytes",
    "best_transition_conflicted_bytes",
    "copy_unlock_rows",
    "copy_unlock_bytes",
    "total_potential_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

SEQUENCE_FIELDNAMES = [
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
    "backward_offset_steps",
    "zero_offset_steps",
    "forward_offset_steps",
    "plus1_delta_bytes",
    "zero_delta_bytes",
    "negative_delta_bytes",
    "constant_delta",
    "sequence_signature",
    "issues",
]

TRANSITION_FIELDNAMES = [
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
    "transition_index",
    "from_palette_index",
    "to_palette_index",
    "from_source_offset",
    "to_source_offset",
    "source_offset_step",
    "source_offset_direction",
    "from_source_value_hex",
    "to_source_value_hex",
    "source_value_step",
    "from_delta",
    "to_delta",
    "delta_pair",
    "delta_step",
    "to_value_bytes",
    "control_between_len",
    "control_between_hex",
    "transition_entries",
    "issues",
]

SELECTOR_FIELDNAMES = [
    "transition_scope",
    "transition_family",
    "transition_key",
    "rows",
    "seed_rows",
    "transition_value_bytes",
    "delta_pairs_seen",
    "deterministic",
    "repeated_deterministic",
    "verdict",
    "sample_pcx",
    "sample_frontier_id",
]

FAMILY_FIELDNAMES = [
    "transition_scope",
    "transition_family",
    "groups",
    "rows",
    "transition_value_bytes",
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
    "transition_scope",
    "families",
    "groups",
    "rows",
    "transition_value_bytes",
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


def parse_hex_byte(value: str) -> int:
    if value.startswith("0x"):
        return int(value, 16)
    return int(value, 16) if value else 0


def signed_step(current: int, previous: int) -> int:
    return current - previous


def direction(step: int) -> str:
    if step < 0:
        return "backward"
    if step > 0:
        return "forward"
    return "reuse"


def direction_letter(step: int) -> str:
    if step < 0:
        return "B"
    if step > 0:
        return "F"
    return "R"


def join_ints(values: list[int]) -> str:
    return "|".join(str(value) for value in values)


def join_hex(values: list[str]) -> str:
    return "|".join(values)


def stable_delta_pairs(rows: list[dict[str, str]]) -> str:
    return "|".join(sorted({row.get("delta_pair", "") for row in rows}))


def group_phase_values(rows: list[dict[str, str]]) -> list[list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row.get("seed_id", "")].append(row)
    sequences = list(grouped.values())
    for sequence in sequences:
        sequence.sort(key=lambda row: int_value(row, "palette_index"))
    sequences.sort(
        key=lambda sequence: (
            sequence[0].get("pcx_name", "") if sequence else "",
            int_value(sequence[0], "frontier_id") if sequence else 0,
            int_value(sequence[0], "start") if sequence else 0,
        )
    )
    return sequences


def sequence_signature(source_offsets: list[int], deltas: list[int], source_values: list[str]) -> str:
    return (
        f"offsets={join_ints(source_offsets)};"
        f"deltas={join_ints(deltas)};"
        f"sources={join_hex(source_values)}"
    )


def build_sequence_rows(sequences: list[list[dict[str, str]]]) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for sequence in sequences:
        if not sequence:
            continue
        first = sequence[0]
        offsets = [int_value(row, "source_offset") for row in sequence]
        source_values = [row.get("source_value_hex", "") for row in sequence]
        target_values = [row.get("target_value_hex", "") for row in sequence]
        deltas = [int_value(row, "delta") for row in sequence]
        value_bytes = [int_value(row, "value_bytes") for row in sequence]
        offset_steps = [signed_step(offsets[index], offsets[index - 1]) for index in range(1, len(offsets))]
        source_value_steps = [
            signed_step(parse_hex_byte(source_values[index]), parse_hex_byte(source_values[index - 1]))
            for index in range(1, len(source_values))
        ]
        delta_steps = [signed_step(deltas[index], deltas[index - 1]) for index in range(1, len(deltas))]
        offset_counts = Counter(offsets)
        issues = [
            issue
            for row in sequence
            for issue in row.get("issues", "").split(";")
            if issue
        ]
        output.append(
            {
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
                "palette_size": str(len(sequence)),
                "mapping_rows": str(len(sequence)),
                "mapping_value_bytes": str(sum(value_bytes)),
                "copy_unlock_bytes": first.get("copy_unlock_bytes", "0"),
                "control_window_len": first.get("control_window_len", "0"),
                "source_offsets": join_ints(offsets),
                "source_values_hex": join_hex(source_values),
                "target_values_hex": join_hex(target_values),
                "deltas": join_ints(deltas),
                "value_bytes": join_ints(value_bytes),
                "offset_steps": join_ints(offset_steps),
                "offset_direction_pattern": "".join(direction_letter(step) for step in offset_steps),
                "source_value_steps": join_ints(source_value_steps),
                "delta_steps": join_ints(delta_steps),
                "unique_source_offsets": str(len(offset_counts)),
                "reused_source_offsets": str(sum(1 for count in offset_counts.values() if count > 1)),
                "offset_reuse_bytes": str(
                    sum(value_bytes[index] for index, offset in enumerate(offsets) if offset_counts[offset] > 1)
                ),
                "backward_offset_steps": str(sum(1 for step in offset_steps if step < 0)),
                "zero_offset_steps": str(sum(1 for step in offset_steps if step == 0)),
                "forward_offset_steps": str(sum(1 for step in offset_steps if step > 0)),
                "plus1_delta_bytes": str(sum(value_bytes[index] for index, delta in enumerate(deltas) if delta == 1)),
                "zero_delta_bytes": str(sum(value_bytes[index] for index, delta in enumerate(deltas) if delta == 0)),
                "negative_delta_bytes": str(sum(value_bytes[index] for index, delta in enumerate(deltas) if delta < 0)),
                "constant_delta": "1" if len(set(deltas)) == 1 else "0",
                "sequence_signature": sequence_signature(offsets, deltas, source_values),
                "issues": ";".join(dict.fromkeys(issues)),
            }
        )
    return output


def control_between_hex(window: bytes, left: int, right: int) -> str:
    if left < 0 or right < 0 or left >= len(window) or right >= len(window):
        return ""
    start = min(left, right)
    end = max(left, right) + 1
    return window[start:end].hex()


def build_transition_rows(sequences: list[list[dict[str, str]]]) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for sequence in sequences:
        if len(sequence) < 2:
            continue
        first = sequence[0]
        window = safe_bytes_fromhex(first.get("control_window_hex", ""))
        for index in range(1, len(sequence)):
            previous = sequence[index - 1]
            current = sequence[index]
            from_offset = int_value(previous, "source_offset")
            to_offset = int_value(current, "source_offset")
            offset_step = signed_step(to_offset, from_offset)
            from_source = previous.get("source_value_hex", "")
            to_source = current.get("source_value_hex", "")
            from_delta = int_value(previous, "delta")
            to_delta = int_value(current, "delta")
            between_hex = control_between_hex(window, from_offset, to_offset)
            issues = [
                issue
                for row in (previous, current)
                for issue in row.get("issues", "").split(";")
                if issue
            ]
            transition = {
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
                "transition_index": str(index - 1),
                "from_palette_index": previous.get("palette_index", ""),
                "to_palette_index": current.get("palette_index", ""),
                "from_source_offset": str(from_offset),
                "to_source_offset": str(to_offset),
                "source_offset_step": str(offset_step),
                "source_offset_direction": direction(offset_step),
                "from_source_value_hex": from_source,
                "to_source_value_hex": to_source,
                "source_value_step": str(signed_step(parse_hex_byte(to_source), parse_hex_byte(from_source))),
                "from_delta": str(from_delta),
                "to_delta": str(to_delta),
                "delta_pair": f"{from_delta}->{to_delta}",
                "delta_step": str(signed_step(to_delta, from_delta)),
                "to_value_bytes": current.get("value_bytes", "0"),
                "control_between_len": str(len(between_hex) // 2),
                "control_between_hex": between_hex,
                "transition_entries": "0",
                "issues": ";".join(dict.fromkeys(issues)),
            }
            transition["transition_entries"] = str(len(transition_entries(transition)))
            output.append(transition)
    output.sort(
        key=lambda row: (
            row.get("pcx_name", ""),
            int_value(row, "frontier_id"),
            int_value(row, "transition_index"),
        )
    )
    return output


def transition_entries(row: dict[str, str]) -> list[tuple[str, str, str]]:
    from_source = row.get("from_source_value_hex", "")
    to_source = row.get("to_source_value_hex", "")
    source_pair = f"{from_source}->{to_source}"
    offset_step = int_value(row, "source_offset_step")
    source_step = int_value(row, "source_value_step")
    from_offset = int_value(row, "from_source_offset")
    to_offset = int_value(row, "to_source_offset")
    between_hex = row.get("control_between_hex", "")
    entries = [
        ("sequence_order", "transition_index", row.get("transition_index", "")),
        ("sequence_order", "transition_index_mod2", str(int_value(row, "transition_index") % 2)),
        ("sequence_order", "palette_pair", f"{row.get('from_palette_index', '')}->{row.get('to_palette_index', '')}"),
        ("offset_walk", "offset_step", str(offset_step)),
        ("offset_walk", "offset_abs_step", str(abs(offset_step))),
        ("offset_walk", "offset_direction", row.get("source_offset_direction", "")),
        ("offset_walk", "offset_step_mod4", str(offset_step % 4)),
        ("offset_walk", "from_offset_mod4", str(from_offset % 4)),
        ("offset_walk", "to_offset_mod4", str(to_offset % 4)),
        ("offset_walk", "offset_mod4_pair", f"{from_offset % 4}->{to_offset % 4}"),
        ("source_value_walk", "from_source_value", from_source),
        ("source_value_walk", "to_source_value", to_source),
        ("source_value_walk", "source_pair", source_pair),
        ("source_value_walk", "source_value_step", str(source_step)),
        ("source_value_walk", "source_value_step_sign", direction(source_step)),
        ("source_value_walk", "source_high_nibble_pair", f"{from_source[2:3]}->{to_source[2:3]}"),
        ("source_value_walk", "source_low_nibble_pair", f"{from_source[3:4]}->{to_source[3:4]}"),
        ("source_offset_opcode", "from_source_offset_mod4", f"{from_source}|{from_offset % 4}"),
        ("source_offset_opcode", "to_source_offset_mod4", f"{to_source}|{to_offset % 4}"),
        ("source_offset_opcode", "source_pair_offset_direction", f"{source_pair}|{row.get('source_offset_direction', '')}"),
        ("source_offset_opcode", "source_pair_offset_step", f"{source_pair}|{offset_step}"),
        ("source_offset_opcode", "source_step_offset_step", f"{source_step}|{offset_step}"),
        ("control_between", "between_len", row.get("control_between_len", "")),
        ("control_between", "between_hex", between_hex),
        ("control_between", "between_len_direction", f"{row.get('control_between_len', '')}|{row.get('source_offset_direction', '')}"),
    ]
    return [(scope, family, key) for scope, family, key in entries if key]


def build_selector_rows(transition_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in transition_rows:
        for scope, family, key in transition_entries(row):
            grouped[scope, family, key].append(row)

    output: list[dict[str, str]] = []
    for (scope, family, key), rows in grouped.items():
        delta_pairs = {row.get("delta_pair", "") for row in rows}
        seed_rows = {row.get("seed_id", "") for row in rows}
        deterministic = len(delta_pairs) == 1
        repeated_deterministic = deterministic and len(seed_rows) > 1
        if repeated_deterministic:
            verdict = "opcode_sequence_repeated_delta_pair_candidate"
        elif deterministic:
            verdict = "opcode_sequence_singleton_delta_pair_review"
        else:
            verdict = "opcode_sequence_delta_pair_conflict"
        sample = rows[0]
        output.append(
            {
                "transition_scope": scope,
                "transition_family": family,
                "transition_key": key,
                "rows": str(len(rows)),
                "seed_rows": str(len(seed_rows)),
                "transition_value_bytes": str(sum(int_value(row, "to_value_bytes") for row in rows)),
                "delta_pairs_seen": stable_delta_pairs(rows),
                "deterministic": "1" if deterministic else "0",
                "repeated_deterministic": "1" if repeated_deterministic else "0",
                "verdict": verdict,
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
            }
        )
    output.sort(
        key=lambda row: (
            row.get("transition_scope", ""),
            row.get("transition_family", ""),
            -int_value(row, "repeated_deterministic"),
            -int_value(row, "transition_value_bytes"),
            row.get("transition_key", ""),
        )
    )
    return output


def build_family_rows(selector_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in selector_rows:
        grouped[row.get("transition_scope", ""), row.get("transition_family", "")].append(row)

    output: list[dict[str, str]] = []
    for (scope, family), rows in grouped.items():
        deterministic = [row for row in rows if row.get("deterministic") == "1"]
        repeated = [row for row in rows if row.get("repeated_deterministic") == "1"]
        singleton = [row for row in deterministic if row.get("repeated_deterministic") != "1"]
        conflicted = [row for row in rows if row.get("deterministic") != "1"]
        if repeated:
            verdict = "opcode_sequence_candidate"
        elif deterministic:
            verdict = "opcode_sequence_singleton_only"
        else:
            verdict = "opcode_sequence_blocked"
        output.append(
            {
                "transition_scope": scope,
                "transition_family": family,
                "groups": str(len(rows)),
                "rows": str(sum(int_value(row, "rows") for row in rows)),
                "transition_value_bytes": str(sum(int_value(row, "transition_value_bytes") for row in rows)),
                "deterministic_groups": str(len(deterministic)),
                "deterministic_bytes": str(sum(int_value(row, "transition_value_bytes") for row in deterministic)),
                "repeated_deterministic_groups": str(len(repeated)),
                "repeated_deterministic_bytes": str(
                    sum(int_value(row, "transition_value_bytes") for row in repeated)
                ),
                "singleton_deterministic_groups": str(len(singleton)),
                "singleton_deterministic_bytes": str(
                    sum(int_value(row, "transition_value_bytes") for row in singleton)
                ),
                "conflicted_groups": str(len(conflicted)),
                "conflicted_bytes": str(sum(int_value(row, "transition_value_bytes") for row in conflicted)),
                "verdict": verdict,
            }
        )
    output.sort(
        key=lambda row: (
            -int_value(row, "repeated_deterministic_bytes"),
            -int_value(row, "deterministic_bytes"),
            -int_value(row, "conflicted_bytes"),
            row.get("transition_scope", ""),
            row.get("transition_family", ""),
        )
    )
    return output


def build_scope_rows(family_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in family_rows:
        grouped[row.get("transition_scope", "")].append(row)

    output: list[dict[str, str]] = []
    for scope, rows in grouped.items():
        repeated_groups = sum(int_value(row, "repeated_deterministic_groups") for row in rows)
        deterministic_groups = sum(int_value(row, "deterministic_groups") for row in rows)
        if repeated_groups:
            verdict = "opcode_sequence_scope_candidate"
        elif deterministic_groups:
            verdict = "opcode_sequence_scope_singleton_only"
        else:
            verdict = "opcode_sequence_scope_blocked"
        output.append(
            {
                "transition_scope": scope,
                "families": str(len(rows)),
                "groups": str(sum(int_value(row, "groups") for row in rows)),
                "rows": str(sum(int_value(row, "rows") for row in rows)),
                "transition_value_bytes": str(sum(int_value(row, "transition_value_bytes") for row in rows)),
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
            row.get("transition_scope", ""),
        )
    )
    return output


def build_summary(
    sequence_rows: list[dict[str, str]],
    transition_rows: list[dict[str, str]],
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
        "seed_rows": str(len(sequence_rows)),
        "mapping_rows": str(sum(int_value(row, "mapping_rows") for row in sequence_rows)),
        "mapping_value_bytes": str(sum(int_value(row, "mapping_value_bytes") for row in sequence_rows)),
        "control_window_bytes": str(sum(int_value(row, "control_window_len") for row in sequence_rows)),
        "sequence_signatures": str(len({row.get("sequence_signature", "") for row in sequence_rows})),
        "constant_delta_seed_rows": str(sum(1 for row in sequence_rows if row.get("constant_delta") == "1")),
        "mixed_delta_seed_rows": str(sum(1 for row in sequence_rows if row.get("constant_delta") != "1")),
        "transition_rows": str(len(transition_rows)),
        "transition_value_bytes": str(sum(int_value(row, "to_value_bytes") for row in transition_rows)),
        "transition_scopes": str(len(scope_rows)),
        "transition_families": str(len(family_rows)),
        "transition_groups": str(len(selector_rows)),
        "deterministic_transition_groups": str(len(deterministic)),
        "deterministic_transition_bytes": str(sum(int_value(row, "transition_value_bytes") for row in deterministic)),
        "repeated_transition_groups": str(len(repeated)),
        "repeated_transition_bytes": str(sum(int_value(row, "transition_value_bytes") for row in repeated)),
        "singleton_transition_groups": str(len(singleton)),
        "singleton_transition_bytes": str(sum(int_value(row, "transition_value_bytes") for row in singleton)),
        "conflicted_transition_groups": str(len(conflicted)),
        "conflicted_transition_bytes": str(sum(int_value(row, "transition_value_bytes") for row in conflicted)),
        "offset_reuse_bytes": str(sum(int_value(row, "offset_reuse_bytes") for row in sequence_rows)),
        "backward_offset_steps": str(sum(int_value(row, "backward_offset_steps") for row in sequence_rows)),
        "zero_offset_steps": str(sum(int_value(row, "zero_offset_steps") for row in sequence_rows)),
        "forward_offset_steps": str(sum(int_value(row, "forward_offset_steps") for row in sequence_rows)),
        "plus1_delta_bytes": str(sum(int_value(row, "plus1_delta_bytes") for row in sequence_rows)),
        "zero_delta_bytes": str(sum(int_value(row, "zero_delta_bytes") for row in sequence_rows)),
        "negative_delta_bytes": str(sum(int_value(row, "negative_delta_bytes") for row in sequence_rows)),
        "best_transition_family": best_family.get("transition_family", ""),
        "best_transition_repeated_bytes": best_family.get("repeated_deterministic_bytes", "0"),
        "best_transition_conflicted_bytes": best_conflicted.get("conflicted_bytes", "0"),
        "copy_unlock_rows": str(sum(1 for row in sequence_rows if int_value(row, "copy_unlock_bytes"))),
        "copy_unlock_bytes": str(sum(int_value(row, "copy_unlock_bytes") for row in sequence_rows)),
        "total_potential_bytes": str(
            sum(int_value(row, "mapping_value_bytes") for row in sequence_rows)
            + sum(int_value(row, "copy_unlock_bytes") for row in sequence_rows)
        ),
        "promotion_ready_bytes": "0",
        "issue_rows": str(
            sum(1 for row in sequence_rows if row.get("issues"))
            + sum(1 for row in transition_rows if row.get("issues"))
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
    sequence_rows: list[dict[str, str]],
    transition_rows: list[dict[str, str]],
    selector_rows: list[dict[str, str]],
    family_rows: list[dict[str, str]],
    scope_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    files = [
        ("summary.csv", output_dir / "summary.csv"),
        ("sequence_rows.csv", output_dir / "sequence_rows.csv"),
        ("transition_rows.csv", output_dir / "transition_rows.csv"),
        ("by_transition_selector.csv", output_dir / "by_transition_selector.csv"),
        ("by_transition_family.csv", output_dir / "by_transition_family.csv"),
        ("by_transition_scope.csv", output_dir / "by_transition_scope.csv"),
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
            "sequenceRows": sequence_rows,
            "transitionRows": transition_rows,
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
    <div class="sub">Checks ordered source offsets and control bytes for the gradient seed delta sequence.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Seed rows</div><div class="value">{summary['seed_rows']}</div></div>
    <div class="stat"><div class="label">Mapping bytes</div><div class="value warn">{summary['mapping_value_bytes']}</div></div>
    <div class="stat"><div class="label">Transition rows</div><div class="value">{summary['transition_rows']}</div></div>
    <div class="stat"><div class="label">Repeated transition bytes</div><div class="value">{summary['repeated_transition_bytes']}</div></div>
    <div class="stat"><div class="label">Conflicted transition bytes</div><div class="value warn">{summary['conflicted_transition_bytes']}</div></div>
    <div class="stat"><div class="label">Promotion-ready bytes</div><div class="value ok">{summary['promotion_ready_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2><div>{links}</div></section>
  <section class="panel"><h2>Transition scopes</h2>{render_table(scope_rows, SCOPE_FIELDNAMES)}</section>
  <section class="panel"><h2>Transition families</h2>{render_table(family_rows, FAMILY_FIELDNAMES)}</section>
  <section class="panel"><h2>Transition selectors</h2>{render_table(selector_rows, SELECTOR_FIELDNAMES)}</section>
  <section class="panel"><h2>Seed sequences</h2>{render_table(sequence_rows, SEQUENCE_FIELDNAMES)}</section>
  <section class="panel"><h2>Adjacent transitions</h2>{render_table(transition_rows, TRANSITION_FIELDNAMES)}</section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_GRADIENT_SEED_DELTA_OPCODE_SEQUENCE_PROBE = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe ordered opcode/source sequences for .tex gradient seed deltas.")
    parser.add_argument("--phase-values", type=Path, default=DEFAULT_PHASE_VALUES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Tiny Nonzero Gap Gradient Seed Delta Opcode Sequence Probe",
    )
    args = parser.parse_args()

    phase_rows = read_csv(args.phase_values)
    sequences = group_phase_values(phase_rows)
    sequence_rows = build_sequence_rows(sequences)
    transition_rows = build_transition_rows(sequences)
    selector_rows = build_selector_rows(transition_rows)
    family_rows = build_family_rows(selector_rows)
    scope_rows = build_scope_rows(family_rows)
    summary = build_summary(sequence_rows, transition_rows, selector_rows, family_rows, scope_rows)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "sequence_rows.csv", SEQUENCE_FIELDNAMES, sequence_rows)
    write_csv(args.output / "transition_rows.csv", TRANSITION_FIELDNAMES, transition_rows)
    write_csv(args.output / "by_transition_selector.csv", SELECTOR_FIELDNAMES, selector_rows)
    write_csv(args.output / "by_transition_family.csv", FAMILY_FIELDNAMES, family_rows)
    write_csv(args.output / "by_transition_scope.csv", SCOPE_FIELDNAMES, scope_rows)
    html_path = args.output / "index.html"
    html_path.write_text(
        build_html(summary, sequence_rows, transition_rows, selector_rows, family_rows, scope_rows, args.output, args.title)
    )

    print(f"Seed rows: {summary['seed_rows']}")
    print(f"Mapping bytes: {summary['mapping_value_bytes']}")
    print(f"Transition groups: {summary['transition_groups']}")
    print(f"Repeated transition bytes: {summary['repeated_transition_bytes']}")
    print(f"Conflicted transition bytes: {summary['conflicted_transition_bytes']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
