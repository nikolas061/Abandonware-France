#!/usr/bin/env python3
"""Probe local sequence/phase grammar across gradient macro-opcode rows."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_micro_mixed_value_payload_state_opcode_probe import int_value, ratio


DEFAULT_INPUT_ROWS = Path("output/tex_gradient_macro_opcode/rows.csv")
DEFAULT_OUTPUT = Path("output/tex_gradient_macro_phase_sequence")

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "target_bytes",
    "target_kinds",
    "selector_families",
    "selector_groups",
    "repeated_selector_groups",
    "deterministic_repeated_groups",
    "deterministic_repeated_evidence_bytes",
    "conflicted_groups",
    "conflicted_evidence_bytes",
    "singleton_groups",
    "singleton_evidence_bytes",
    "sequence_deterministic_evidence_bytes",
    "sequence_conflicted_evidence_bytes",
    "payload_deterministic_evidence_bytes",
    "payload_conflicted_evidence_bytes",
    "best_sequence_target_kind",
    "best_sequence_selector_family",
    "best_sequence_deterministic_bytes",
    "best_sequence_conflicted_bytes",
    "best_sequence_singleton_bytes",
    "low_conflict_sequence_target_kind",
    "low_conflict_sequence_selector_family",
    "low_conflict_sequence_deterministic_bytes",
    "low_conflict_sequence_conflicted_bytes",
    "low_conflict_sequence_singleton_bytes",
    "best_payload_target_kind",
    "best_payload_selector_family",
    "best_payload_deterministic_bytes",
    "best_payload_conflicted_bytes",
    "best_payload_singleton_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

ROW_FIELDNAMES = [
    "rank",
    "archive",
    "pcx_name",
    "frontier_id",
    "frontier_row_index",
    "frontier_row_count",
    "frontier_count_bucket",
    "frontier_position",
    "span_index",
    "op_index",
    "length",
    "start",
    "end",
    "length_bucket",
    "length_band8",
    "span_phase4",
    "op_phase4",
    "op_phase8",
    "start_band128",
    "frontier_length_profile",
    "frontier_op_gap_profile",
    "prev_op_gap",
    "next_op_gap",
    "prev_span_gap",
    "next_span_gap",
    "prev_start_gap",
    "next_start_gap",
    "prev_length_band8",
    "next_length_band8",
    "prev_fixture_relation",
    "next_fixture_relation",
    "prev_control_relation",
    "next_control_relation",
    "prev_control_mod64",
    "next_control_mod64",
    "fixture_rule_key",
    "control_anchor_mod64",
    "start_anchor_mod64",
    "control_anchor_class_key",
    "start_anchor_class_key",
    "control_window_class_key",
    "sequence_signature",
    "payload_signature",
    "band_shape_key",
    "step_shape_key",
    "dominant_delta",
    "top_nibble",
    "gradient_class",
    "issues",
]

GROUP_FIELDNAMES = [
    "rank",
    "target_kind",
    "selector_type",
    "selector_family",
    "selector_key",
    "rows",
    "bytes",
    "target_values",
    "dominant_value",
    "dominant_ratio",
    "deterministic_bytes",
    "conflicted_bytes",
    "singleton_bytes",
    "sample_pcx",
    "sample_frontier_id",
    "verdict",
]

FAMILY_FIELDNAMES = [
    "rank",
    "target_kind",
    "selector_type",
    "selector_family",
    "groups",
    "repeated_groups",
    "repeated_evidence_bytes",
    "deterministic_repeated_groups",
    "deterministic_repeated_evidence_bytes",
    "conflicted_groups",
    "conflicted_evidence_bytes",
    "singleton_groups",
    "singleton_evidence_bytes",
    "best_group_key",
    "best_group_bytes",
    "best_group_values",
    "verdict",
]

COARSE_TARGETS = {"dominant_delta", "top_nibble", "gradient_class"}
PAYLOAD_TARGETS = {"exact_payload", "band_shape", "step_shape"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def band(value: int, step: int) -> str:
    base = (value // step) * step
    return f"{base}-{base + step - 1}"


def gap_bucket(value: int | None) -> str:
    if value is None:
        return "edge"
    sign = "-" if value < 0 else ""
    magnitude = abs(value)
    if magnitude <= 2:
        bucket = str(magnitude)
    elif magnitude <= 4:
        bucket = "3-4"
    elif magnitude <= 8:
        bucket = "5-8"
    elif magnitude <= 16:
        bucket = "9-16"
    elif magnitude <= 32:
        bucket = "17-32"
    elif magnitude <= 64:
        bucket = "33-64"
    elif magnitude <= 128:
        bucket = "65-128"
    else:
        bucket = "129+"
    return f"{sign}{bucket}"


def count_bucket(count: int) -> str:
    if count <= 1:
        return "single"
    if count <= 3:
        return str(count)
    if count <= 6:
        return "4-6"
    return "7+"


def key_part(text: str, name: str) -> str:
    prefix = f"{name}="
    for part in text.split("|"):
        if part.startswith(prefix):
            return part[len(prefix) :]
    return "missing"


def relation(current: str, other: str | None) -> str:
    if other is None:
        return "edge"
    return "same" if current == other else "diff"


def position_class(index: int, count: int) -> str:
    if count == 1:
        return "single"
    if index == 0:
        return "first"
    if index == count - 1:
        return "last"
    if count > 4 and index == 1:
        return "early"
    if count > 4 and index == count - 2:
        return "late"
    return "middle"


def sort_key(row: dict[str, str]) -> tuple[str, str, int, int, int, int, int]:
    return (
        row.get("archive", ""),
        row.get("pcx_name", ""),
        int_value(row, "frontier_id"),
        int_value(row, "span_index"),
        int_value(row, "op_index"),
        int_value(row, "start"),
        int_value(row, "rank"),
    )


def length_profile(members: list[dict[str, str]]) -> str:
    bands = [band(int_value(row, "length"), 16) for row in members]
    compact = "-".join(bands)
    if len(compact) > 96:
        counts = Counter(bands)
        compact = "|".join(f"{value}:{count}" for value, count in counts.most_common())
    return compact


def op_gap_profile(members: list[dict[str, str]]) -> str:
    gaps: list[str] = []
    for prev, current in zip(members, members[1:]):
        gaps.append(gap_bucket(int_value(current, "op_index") - int_value(prev, "op_index")))
    return "-".join(gaps) if gaps else "single"


def build_rows(input_rows: list[dict[str, str]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for input_row in sorted(input_rows, key=sort_key):
        grouped[
            (
                input_row.get("archive", ""),
                input_row.get("pcx_name", ""),
                input_row.get("frontier_id", ""),
            )
        ].append(input_row)

    rows: list[dict[str, object]] = []
    for (_, _, _), members in grouped.items():
        members = sorted(members, key=sort_key)
        count = len(members)
        count_bin = count_bucket(count)
        frontier_lengths = length_profile(members)
        frontier_op_gaps = op_gap_profile(members)
        for index, input_row in enumerate(members):
            previous = members[index - 1] if index else None
            following = members[index + 1] if index + 1 < count else None
            span = int_value(input_row, "span_index")
            op = int_value(input_row, "op_index")
            start = int_value(input_row, "start")
            length = int_value(input_row, "length")
            fixture = input_row.get("fixture_rule_key", "")
            control_anchor = input_row.get("control_anchor_class_key", "")
            control_mod = key_part(control_anchor, "mod64")
            prev_control = previous.get("control_anchor_class_key", "") if previous else None
            next_control = following.get("control_anchor_class_key", "") if following else None
            prev_fixture = previous.get("fixture_rule_key", "") if previous else None
            next_fixture = following.get("fixture_rule_key", "") if following else None
            prev_op_gap = gap_bucket(op - int_value(previous, "op_index")) if previous else "edge"
            next_op_gap = gap_bucket(int_value(following, "op_index") - op) if following else "edge"
            prev_span_gap = gap_bucket(span - int_value(previous, "span_index")) if previous else "edge"
            next_span_gap = gap_bucket(int_value(following, "span_index") - span) if following else "edge"
            prev_start_gap = gap_bucket(start - int_value(previous, "start")) if previous else "edge"
            next_start_gap = gap_bucket(int_value(following, "start") - start) if following else "edge"
            prev_length = band(int_value(previous, "length"), 8) if previous else "edge"
            next_length = band(int_value(following, "length"), 8) if following else "edge"
            position = position_class(index, count)
            sequence_signature = (
                f"count={count_bin}|pos={position}|"
                f"prev_op={prev_op_gap}|next_op={next_op_gap}|"
                f"prev_len={prev_length}|len8={band(length, 8)}|next_len={next_length}"
            )
            rows.append(
                {
                    "rank": len(rows) + 1,
                    "archive": input_row.get("archive", ""),
                    "pcx_name": input_row.get("pcx_name", ""),
                    "frontier_id": input_row.get("frontier_id", ""),
                    "frontier_row_index": index,
                    "frontier_row_count": count,
                    "frontier_count_bucket": count_bin,
                    "frontier_position": position,
                    "span_index": input_row.get("span_index", ""),
                    "op_index": input_row.get("op_index", ""),
                    "length": input_row.get("length", ""),
                    "start": input_row.get("start", ""),
                    "end": input_row.get("end", ""),
                    "length_bucket": input_row.get("length_bucket", ""),
                    "length_band8": band(length, 8),
                    "span_phase4": band(span, 4),
                    "op_phase4": band(op, 4),
                    "op_phase8": band(op, 8),
                    "start_band128": band(start, 128),
                    "frontier_length_profile": frontier_lengths,
                    "frontier_op_gap_profile": frontier_op_gaps,
                    "prev_op_gap": prev_op_gap,
                    "next_op_gap": next_op_gap,
                    "prev_span_gap": prev_span_gap,
                    "next_span_gap": next_span_gap,
                    "prev_start_gap": prev_start_gap,
                    "next_start_gap": next_start_gap,
                    "prev_length_band8": prev_length,
                    "next_length_band8": next_length,
                    "prev_fixture_relation": relation(fixture, prev_fixture),
                    "next_fixture_relation": relation(fixture, next_fixture),
                    "prev_control_relation": relation(control_anchor, prev_control),
                    "next_control_relation": relation(control_anchor, next_control),
                    "prev_control_mod64": key_part(prev_control or "", "mod64") if previous else "edge",
                    "next_control_mod64": key_part(next_control or "", "mod64") if following else "edge",
                    "fixture_rule_key": fixture,
                    "control_anchor_mod64": control_mod,
                    "start_anchor_mod64": key_part(input_row.get("start_anchor_class_key", ""), "start_mod64"),
                    "control_anchor_class_key": control_anchor,
                    "start_anchor_class_key": input_row.get("start_anchor_class_key", ""),
                    "control_window_class_key": input_row.get("control_window_class_key", ""),
                    "sequence_signature": sequence_signature,
                    "payload_signature": input_row.get("payload_signature", ""),
                    "band_shape_key": input_row.get("band_shape_key", ""),
                    "step_shape_key": input_row.get("step_shape_key", ""),
                    "dominant_delta": input_row.get("dominant_delta", ""),
                    "top_nibble": input_row.get("top_nibble", ""),
                    "gradient_class": input_row.get("gradient_class", ""),
                    "issues": input_row.get("issues", ""),
                }
            )
    return rows


def target_values(row: dict[str, object]) -> dict[str, str]:
    return {
        "dominant_delta": str(row["dominant_delta"]),
        "top_nibble": str(row["top_nibble"]),
        "gradient_class": str(row["gradient_class"]),
        "exact_payload": str(row["payload_signature"]),
        "band_shape": str(row["band_shape_key"]),
        "step_shape": str(row["step_shape_key"]),
    }


def selector_values(row: dict[str, object]) -> dict[str, tuple[str, str]]:
    pos = str(row["frontier_position"])
    count = str(row["frontier_count_bucket"])
    op4 = str(row["op_phase4"])
    op8 = str(row["op_phase8"])
    span4 = str(row["span_phase4"])
    start128 = str(row["start_band128"])
    length8 = str(row["length_band8"])
    prev_op = str(row["prev_op_gap"])
    next_op = str(row["next_op_gap"])
    prev_span = str(row["prev_span_gap"])
    next_span = str(row["next_span_gap"])
    prev_start = str(row["prev_start_gap"])
    next_start = str(row["next_start_gap"])
    prev_len = str(row["prev_length_band8"])
    next_len = str(row["next_length_band8"])
    prev_fixture = str(row["prev_fixture_relation"])
    next_fixture = str(row["next_fixture_relation"])
    prev_control = str(row["prev_control_relation"])
    next_control = str(row["next_control_relation"])
    fixture = str(row["fixture_rule_key"])
    control_mod = str(row["control_anchor_mod64"])
    start_mod = str(row["start_anchor_mod64"])
    return {
        "frontier_position": ("sequence", f"pos={pos}"),
        "frontier_size_position": ("sequence", f"count={count}|pos={pos}"),
        "frontier_length_profile": ("sequence", f"count={count}|lens={row['frontier_length_profile']}"),
        "frontier_op_gap_profile": ("sequence", f"count={count}|gaps={row['frontier_op_gap_profile']}"),
        "neighbor_op_gap": ("sequence", f"prev_op={prev_op}|next_op={next_op}"),
        "neighbor_span_gap": ("sequence", f"prev_span={prev_span}|next_span={next_span}"),
        "neighbor_start_gap": ("sequence", f"prev_start={prev_start}|next_start={next_start}"),
        "neighbor_length_band": ("sequence", f"prev_len={prev_len}|len8={length8}|next_len={next_len}"),
        "neighbor_fixture_relation": ("sequence_source", f"prev_fixture={prev_fixture}|next_fixture={next_fixture}"),
        "neighbor_control_relation": ("sequence_source", f"prev_ctrl={prev_control}|next_ctrl={next_control}"),
        "op_sequence_context": (
            "sequence_phase",
            f"op4={op4}|count={count}|pos={pos}|prev_op={prev_op}|next_op={next_op}",
        ),
        "op_gap_length_context": (
            "sequence_phase",
            f"op4={op4}|prev_op={prev_op}|next_op={next_op}|len8={length8}",
        ),
        "span_sequence_context": (
            "sequence_phase",
            f"span4={span4}|pos={pos}|prev_span={prev_span}|next_span={next_span}",
        ),
        "start_sequence_context": (
            "sequence_phase",
            f"start128={start128}|pos={pos}|prev_start={prev_start}|next_start={next_start}",
        ),
        "frontier_op_position": ("sequence_phase", f"count={count}|pos={pos}|op4={op4}"),
        "frontier_span_position": ("sequence_phase", f"count={count}|pos={pos}|span4={span4}"),
        "phase_neighbor_signature": (
            "sequence_phase",
            f"op4={op4}|span4={span4}|prev_op={prev_op}|next_op={next_op}",
        ),
        "sequence_signature": ("sequence_phase", str(row["sequence_signature"])),
        "fixture_sequence_context": (
            "macro_sequence",
            f"{fixture}|count={count}|pos={pos}|prev_fixture={prev_fixture}|next_fixture={next_fixture}",
        ),
        "fixture_op_sequence_context": (
            "macro_sequence",
            f"{fixture}|op4={op4}|prev_op={prev_op}|next_op={next_op}",
        ),
        "fixture_length_sequence_context": (
            "macro_sequence",
            f"{fixture}|len8={length8}|prev_len={prev_len}|next_len={next_len}",
        ),
        "control_sequence_context": (
            "macro_sequence",
            f"ctrl_mod64={control_mod}|pos={pos}|prev_ctrl={prev_control}|next_ctrl={next_control}",
        ),
        "control_op_sequence_context": (
            "macro_sequence",
            f"ctrl_mod64={control_mod}|op4={op4}|prev_op={prev_op}|next_op={next_op}",
        ),
        "anchor_sequence_context": (
            "macro_sequence",
            f"start_mod64={start_mod}|pos={pos}|prev_start={prev_start}|next_start={next_start}",
        ),
    }


def build_group_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    target_kinds = target_values(rows[0]).keys() if rows else []
    selector_families = selector_values(rows[0]).keys() if rows else []
    for target_kind in target_kinds:
        for selector_family in selector_families:
            selector_type = selector_values(rows[0])[selector_family][0]
            grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
            for row in rows:
                grouped[selector_values(row)[selector_family][1]].append(row)
            for selector_key, members in grouped.items():
                values = Counter(target_values(row)[target_kind] for row in members)
                dominant_value, dominant_count = values.most_common(1)[0]
                rows_count = len(members)
                bytes_count = sum(int_value(row, "length") for row in members)
                deterministic = len(values) == 1
                repeated = rows_count > 1
                output.append(
                    {
                        "rank": 0,
                        "target_kind": target_kind,
                        "selector_type": selector_type,
                        "selector_family": selector_family,
                        "selector_key": selector_key,
                        "rows": rows_count,
                        "bytes": bytes_count,
                        "target_values": "|".join(f"{value}:{count}" for value, count in values.most_common(8)),
                        "dominant_value": dominant_value,
                        "dominant_ratio": ratio(dominant_count, rows_count),
                        "deterministic_bytes": bytes_count if deterministic and repeated else 0,
                        "conflicted_bytes": bytes_count if not deterministic and repeated else 0,
                        "singleton_bytes": bytes_count if rows_count == 1 else 0,
                        "sample_pcx": members[0].get("pcx_name", ""),
                        "sample_frontier_id": members[0].get("frontier_id", ""),
                        "verdict": (
                            "sequence_deterministic_repeat"
                            if deterministic and repeated
                            else "sequence_conflicted_repeat"
                            if repeated
                            else "sequence_singleton"
                        ),
                    }
                )

    output.sort(
        key=lambda row: (
            str(row["target_kind"]),
            str(row["selector_type"]),
            str(row["selector_family"]),
            -int_value(row, "rows"),
            -int_value(row, "bytes"),
            str(row["selector_key"]),
        )
    )
    for index, row in enumerate(output, start=1):
        row["rank"] = index
    return output


def build_family_rows(group_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, str], list[dict[str, object]]] = defaultdict(list)
    for row in group_rows:
        grouped[(str(row["target_kind"]), str(row["selector_type"]), str(row["selector_family"]))].append(row)

    output: list[dict[str, object]] = []
    for (target_kind, selector_type, selector_family), members in grouped.items():
        repeated = [row for row in members if int_value(row, "rows") > 1]
        deterministic = [row for row in repeated if int_value(row, "deterministic_bytes") > 0]
        conflicted = [row for row in repeated if int_value(row, "conflicted_bytes") > 0]
        singletons = [row for row in members if int_value(row, "rows") == 1]
        deterministic_bytes = sum(int_value(row, "deterministic_bytes") for row in deterministic)
        conflicted_bytes = sum(int_value(row, "conflicted_bytes") for row in conflicted)
        singleton_bytes = sum(int_value(row, "singleton_bytes") for row in singletons)
        best_group = max(repeated, key=lambda row: int_value(row, "bytes"), default={})
        output.append(
            {
                "rank": 0,
                "target_kind": target_kind,
                "selector_type": selector_type,
                "selector_family": selector_family,
                "groups": len(members),
                "repeated_groups": len(repeated),
                "repeated_evidence_bytes": sum(int_value(row, "bytes") for row in repeated),
                "deterministic_repeated_groups": len(deterministic),
                "deterministic_repeated_evidence_bytes": deterministic_bytes,
                "conflicted_groups": len(conflicted),
                "conflicted_evidence_bytes": conflicted_bytes,
                "singleton_groups": len(singletons),
                "singleton_evidence_bytes": singleton_bytes,
                "best_group_key": best_group.get("selector_key", ""),
                "best_group_bytes": best_group.get("bytes", 0),
                "best_group_values": best_group.get("target_values", ""),
                "verdict": (
                    "sequence_selector_candidate"
                    if deterministic_bytes and deterministic_bytes >= conflicted_bytes
                    else "sequence_selector_conflicted"
                    if conflicted_bytes
                    else "sequence_selector_singleton_only"
                ),
            }
        )

    output.sort(
        key=lambda row: (
            str(row["target_kind"]) not in COARSE_TARGETS,
            -int_value(row, "deterministic_repeated_evidence_bytes"),
            int_value(row, "conflicted_evidence_bytes"),
            int_value(row, "singleton_evidence_bytes"),
            str(row["selector_type"]),
            str(row["selector_family"]),
        )
    )
    for index, row in enumerate(output, start=1):
        row["rank"] = index
    return output


def sum_family(family_rows: list[dict[str, object]], targets: set[str], field: str) -> int:
    return sum(int_value(row, field) for row in family_rows if str(row.get("target_kind", "")) in targets)


def best_family(family_rows: list[dict[str, object]], targets: set[str]) -> dict[str, object]:
    candidates = [row for row in family_rows if str(row.get("target_kind", "")) in targets]
    return max(
        candidates,
        key=lambda row: (
            int_value(row, "deterministic_repeated_evidence_bytes"),
            -int_value(row, "conflicted_evidence_bytes"),
            -int_value(row, "singleton_evidence_bytes"),
            str(row["selector_type"]) == "sequence_phase",
        ),
        default={},
    )


def low_conflict_family(family_rows: list[dict[str, object]], targets: set[str]) -> dict[str, object]:
    candidates = [
        row
        for row in family_rows
        if str(row.get("target_kind", "")) in targets
        and int_value(row, "deterministic_repeated_evidence_bytes") > 0
    ]
    return min(
        candidates,
        key=lambda row: (
            int_value(row, "conflicted_evidence_bytes"),
            -int_value(row, "deterministic_repeated_evidence_bytes"),
            int_value(row, "singleton_evidence_bytes"),
        ),
        default={},
    )


def build_summary(
    rows: list[dict[str, object]],
    group_rows: list[dict[str, object]],
    family_rows: list[dict[str, object]],
) -> dict[str, object]:
    repeated = [row for row in group_rows if int_value(row, "rows") > 1]
    deterministic = [row for row in repeated if int_value(row, "deterministic_bytes") > 0]
    conflicted = [row for row in repeated if int_value(row, "conflicted_bytes") > 0]
    singletons = [row for row in group_rows if int_value(row, "rows") == 1]
    best_sequence = best_family(family_rows, COARSE_TARGETS)
    low_conflict_sequence = low_conflict_family(family_rows, COARSE_TARGETS)
    best_payload = best_family(family_rows, PAYLOAD_TARGETS)
    return {
        "scope": "total",
        "target_rows": len(rows),
        "target_bytes": sum(int_value(row, "length") for row in rows),
        "target_kinds": len(target_values(rows[0])) if rows else 0,
        "selector_families": len(selector_values(rows[0])) if rows else 0,
        "selector_groups": len(group_rows),
        "repeated_selector_groups": len(repeated),
        "deterministic_repeated_groups": len(deterministic),
        "deterministic_repeated_evidence_bytes": sum(
            int_value(row, "deterministic_bytes") for row in deterministic
        ),
        "conflicted_groups": len(conflicted),
        "conflicted_evidence_bytes": sum(int_value(row, "conflicted_bytes") for row in conflicted),
        "singleton_groups": len(singletons),
        "singleton_evidence_bytes": sum(int_value(row, "singleton_bytes") for row in singletons),
        "sequence_deterministic_evidence_bytes": sum_family(
            family_rows, COARSE_TARGETS, "deterministic_repeated_evidence_bytes"
        ),
        "sequence_conflicted_evidence_bytes": sum_family(family_rows, COARSE_TARGETS, "conflicted_evidence_bytes"),
        "payload_deterministic_evidence_bytes": sum_family(
            family_rows, PAYLOAD_TARGETS, "deterministic_repeated_evidence_bytes"
        ),
        "payload_conflicted_evidence_bytes": sum_family(family_rows, PAYLOAD_TARGETS, "conflicted_evidence_bytes"),
        "best_sequence_target_kind": best_sequence.get("target_kind", ""),
        "best_sequence_selector_family": best_sequence.get("selector_family", ""),
        "best_sequence_deterministic_bytes": best_sequence.get("deterministic_repeated_evidence_bytes", 0),
        "best_sequence_conflicted_bytes": best_sequence.get("conflicted_evidence_bytes", 0),
        "best_sequence_singleton_bytes": best_sequence.get("singleton_evidence_bytes", 0),
        "low_conflict_sequence_target_kind": low_conflict_sequence.get("target_kind", ""),
        "low_conflict_sequence_selector_family": low_conflict_sequence.get("selector_family", ""),
        "low_conflict_sequence_deterministic_bytes": low_conflict_sequence.get(
            "deterministic_repeated_evidence_bytes", 0
        ),
        "low_conflict_sequence_conflicted_bytes": low_conflict_sequence.get("conflicted_evidence_bytes", 0),
        "low_conflict_sequence_singleton_bytes": low_conflict_sequence.get("singleton_evidence_bytes", 0),
        "best_payload_target_kind": best_payload.get("target_kind", ""),
        "best_payload_selector_family": best_payload.get("selector_family", ""),
        "best_payload_deterministic_bytes": best_payload.get("deterministic_repeated_evidence_bytes", 0),
        "best_payload_conflicted_bytes": best_payload.get("conflicted_evidence_bytes", 0),
        "best_payload_singleton_bytes": best_payload.get("singleton_evidence_bytes", 0),
        "promotion_ready_bytes": 0,
        "issue_rows": sum(1 for row in rows if row.get("issues")),
    }


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
    group_rows: list[dict[str, object]],
    family_rows: list[dict[str, object]],
    title: str,
) -> str:
    data_json = json.dumps(
        {"summary": summary, "rows": rows, "groups": group_rows, "families": family_rows},
        indent=2,
        sort_keys=True,
    )
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body {{ margin: 2rem; background: #101214; color: #edf5f4; font: 14px/1.45 system-ui, sans-serif; }}
table {{ border-collapse: collapse; width: 100%; min-width: 1700px; }}
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
  <div class="box"><div class="num">{summary['target_bytes']}</div><div class="muted">target bytes</div></div>
  <div class="box"><div class="num">{summary['best_sequence_selector_family']}</div><div class="muted">best sequence selector</div></div>
  <div class="box"><div class="num">{summary['best_sequence_deterministic_bytes']}</div><div class="muted">sequence deterministic</div></div>
  <div class="box"><div class="num">{summary['best_sequence_conflicted_bytes']}</div><div class="muted">sequence conflicted</div></div>
  <div class="box"><div class="num">{summary['low_conflict_sequence_selector_family']}</div><div class="muted">lowest conflict sequence</div></div>
  <div class="box"><div class="num">{summary['best_payload_deterministic_bytes']}</div><div class="muted">payload deterministic</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Rows</h2>{render_table(rows, ROW_FIELDNAMES)}</div>
<div class="panel"><h2>Families</h2>{render_table(family_rows, FAMILY_FIELDNAMES)}</div>
<div class="panel"><h2>Groups</h2>{render_table(group_rows, GROUP_FIELDNAMES)}</div>
<script type="application/json" id="gradient-macro-phase-sequence-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe local sequence/phase grammar across gradient macros.")
    parser.add_argument("--input-rows", type=Path, default=DEFAULT_INPUT_ROWS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Gradient Macro Phase Sequence")
    args = parser.parse_args()

    rows = build_rows(read_csv(args.input_rows))
    group_rows = build_group_rows(rows)
    family_rows = build_family_rows(group_rows)
    summary = build_summary(rows, group_rows, family_rows)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "rows.csv", ROW_FIELDNAMES, rows)
    write_csv(args.output / "groups.csv", GROUP_FIELDNAMES, group_rows)
    write_csv(args.output / "families.csv", FAMILY_FIELDNAMES, family_rows)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, rows, group_rows, family_rows, args.title))

    print(f"Target bytes: {summary['target_bytes']}")
    print(f"Selector families: {summary['selector_families']}")
    print(
        f"Best sequence phase: {summary['best_sequence_target_kind']} / "
        f"{summary['best_sequence_selector_family']} "
        f"{summary['best_sequence_deterministic_bytes']} deterministic, "
        f"{summary['best_sequence_conflicted_bytes']} conflicted, "
        f"{summary['best_sequence_singleton_bytes']} singleton"
    )
    print(
        f"Best payload sequence: {summary['best_payload_target_kind']} / "
        f"{summary['best_payload_selector_family']} "
        f"{summary['best_payload_deterministic_bytes']} deterministic, "
        f"{summary['best_payload_conflicted_bytes']} conflicted, "
        f"{summary['best_payload_singleton_bytes']} singleton"
    )
    print(
        f"Lowest conflict sequence: {summary['low_conflict_sequence_target_kind']} / "
        f"{summary['low_conflict_sequence_selector_family']} "
        f"{summary['low_conflict_sequence_deterministic_bytes']} deterministic, "
        f"{summary['low_conflict_sequence_conflicted_bytes']} conflicted, "
        f"{summary['low_conflict_sequence_singleton_bytes']} singleton"
    )
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
