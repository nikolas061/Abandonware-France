#!/usr/bin/env python3
"""Trace cursor state around LLSE 2730 marker-field hypotheses."""

from __future__ import annotations

import argparse
import html
import json
from collections import Counter
from pathlib import Path

from lolg_tex_large_body_control_grammar_probe import int_value, write_csv
from lolg_tex_large_llse_higharg2_refinement_probe import (
    advance,
    apply_x_policy,
    float_text,
    is_known_marker_pair,
    marker_payload_start,
    marker_symmetric_header,
    relative_href,
    signed_byte,
)
from lolg_tex_large_llse_marker_field_semantics_probe import (
    DEFAULT_FIELD_PROFILE_SUMMARY,
    DEFAULT_OUTPUT as _FIELD_SEMANTICS_OUTPUT,
    DEFAULT_PAIR_LENGTH_SUMMARY,
    apply_field_action,
    build_variants,
    load_body,
    read_summary,
    skip_total,
)
from lolg_tex_large_llse_marker_semantics_probe import (
    DEFAULT_HIGHARG2_SUMMARY,
    DEFAULT_MIX_ENTRY_INDEX,
    DEFAULT_SEGMENTS,
    TARGET_CONTROL_PATH,
    read_csv,
)


DEFAULT_OUTPUT = Path("output/tex_large_llse_marker_field_state_probe")
DEFAULT_FIELD_SEMANTICS_SUMMARY = _FIELD_SEMANTICS_OUTPUT / "summary.csv"
DEFAULT_RECORDS = Path("output/tex_large_llse_marker_record_profile/records.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "segment_rows",
    "event_rows",
    "sample_rows",
    "candidate_action",
    "candidate_variant",
    "candidate_score",
    "candidate_delta",
    "target_pair",
    "target_record_len",
    "actions_applied",
    "tuple2000_seen",
    "f1_mod4_zero",
    "f1_mod4_zero_ratio",
    "x_delta_zero",
    "x_delta_zero_ratio",
    "x_delta_abs_le4",
    "x_delta_abs_le4_ratio",
    "y_delta_zero",
    "y_delta_zero_ratio",
    "y_delta_abs_le4",
    "y_delta_abs_le4_ratio",
    "y_forward",
    "y_backward",
    "y_same",
    "target_y_forward",
    "target_y_backward",
    "target_y_same",
    "candidate_y_min",
    "candidate_y_max",
    "f0_zero",
    "f0_low",
    "f0_high",
    "record_target_rows",
    "record_static_guard_rows",
    "trace_static_guard_rows",
    "record_static_guard_untraced_rows",
    "validation_height",
    "validation_event_rows",
    "validation_actions_applied",
    "validation_static_guard_rows",
    "validation_static_guard_untraced_rows",
    "record_static_guard_sample_offsets",
    "final_x",
    "final_y",
    "emitted",
    "issue_rows",
    "state_verdict",
    "next_action",
]

EVENT_FIELDNAMES = [
    "rank",
    "event_index",
    "segment_id",
    "archive",
    "archive_tag",
    "pcx_name",
    "record_offset",
    "record_hex",
    "fields_hex",
    "field0",
    "field1",
    "field2",
    "field3",
    "field4",
    "f1_mod4",
    "f1_div4",
    "tuple2000",
    "target_x",
    "target_y",
    "target_x_delta",
    "target_x_delta_abs",
    "target_y_delta",
    "target_y_delta_abs",
    "target_y_direction",
    "applied",
    "x_before",
    "y_before",
    "x_after",
    "y_after",
    "x_delta",
    "x_delta_abs",
    "y_delta",
    "y_delta_abs",
    "before4_hex",
    "after4_hex",
    "next_byte",
]

BUCKET_FIELDNAMES = [
    "rank",
    "bucket",
    "value",
    "count",
    "ratio",
]

GUARD_FIELDNAMES = [
    "rank",
    "guard",
    "clauses",
    "matched",
    "applied_matched",
    "nonapplied_matched",
    "precision",
    "recall",
    "false_positive_ratio",
    "missed_applied",
    "example_events",
]

RECORD_GUARD_FIELDNAMES = [
    "rank",
    "guard",
    "guard_scope",
    "clauses",
    "matched",
    "trace_matched",
    "late_matched",
    "precision",
    "recall",
    "false_positive_ratio",
    "missed_trace",
    "example_offsets",
]


def ratio(count: int, total: int) -> str:
    return f"{count / max(1, total):.6f}"


def choose_variant(
    higharg2_summary: dict[str, str],
    pair_summary: dict[str, str],
    field_summary: dict[str, str],
    action: str,
):
    variants = build_variants(higharg2_summary, pair_summary, field_summary)
    selected = next((variant for variant in variants if variant.action == action), None)
    if selected is not None:
        return selected
    return next((variant for variant in variants if variant.action == "baseline"), variants[0])


def context_hex(body: bytes, start: int, total: int) -> tuple[str, str, str]:
    before = body[max(0, start - 4) : start].hex()
    end = min(len(body), start + total)
    after = body[end : min(len(body), end + 4)].hex()
    next_byte = f"{body[end]:02x}" if end < len(body) else ""
    return before, after, next_byte


def add_bucket(counters: dict[str, Counter[str]], bucket: str, value: str) -> None:
    counters.setdefault(bucket, Counter())[value] += 1


def byte_value(row: dict[str, str], field: str) -> int:
    try:
        return int(row.get(field, "0"), 16)
    except ValueError:
        return 0


def first_hex_byte(value: str) -> str:
    return value[:2] if len(value) >= 2 else "00"


def record_static_guard_profile(records_path: Path, target_pair: str, target_record_len: int) -> dict[str, str]:
    target_rows = 0
    guard_rows = 0
    offsets: list[str] = []
    for row in read_csv(records_path):
        if (
            row.get("kind") != "pair"
            or row.get("pair") != target_pair
            or int_value(row, "record_len") != target_record_len
        ):
            continue
        record_hex = row.get("record_hex", "")
        if len(record_hex) < 14:
            continue
        target_rows += 1
        try:
            f0 = int(record_hex[4:6], 16)
            f1 = int(record_hex[6:8], 16)
        except ValueError:
            continue
        if f0 >= 0x40 and f1 % 4 == 0:
            guard_rows += 1
            if len(offsets) < 16:
                offsets.append(row.get("record_offset", ""))
    return {
        "record_target_rows": str(target_rows),
        "record_static_guard_rows": str(guard_rows),
        "record_static_guard_sample_offsets": "|".join(offsets),
    }


def trace_body(
    source: dict[str, str],
    body: bytes,
    body_issues: list[str],
    variant,
    width: int,
    height: int,
    low: int,
    high: int,
) -> tuple[list[dict[str, str]], dict[str, int], dict[str, Counter[str]], list[str]]:
    if body_issues:
        return [], {}, {}, body_issues
    payload_base = marker_payload_start(body)
    payload = body[payload_base:]
    x = y = 0
    pos = 0
    emitted = 0
    event_index = 0
    events: list[dict[str, str]] = []
    counters: dict[str, Counter[str]] = {}
    stats = {
        "actions_applied": 0,
        "tuple2000_seen": 0,
        "target_seen": 0,
        "final_x": 0,
        "final_y": 0,
        "emitted": 0,
    }
    while pos < len(payload) and y < height:
        start = pos
        byte = payload[pos]
        pos += 1
        if marker_symmetric_header(payload, byte, pos):
            pos = min(len(payload), start + 2)
            continue
        if pos < len(payload) and is_known_marker_pair(byte, payload[pos]):
            pair = f"{byte:02x}{payload[pos]:02x}"
            total = skip_total(variant.policy_for_pair(pair))
            fields = payload[start + 2 : min(len(payload), start + total)]
            pos = min(len(payload), start + total)
            if pair == variant.target_pair and total == variant.target_record_len:
                stats["target_seen"] += 1
                if len(fields) >= 5:
                    event_index += 1
                    f0, f1, f2, f3, f4 = fields[:5]
                    before_x, before_y = x, y
                    action_stats = {"actions_applied": 0, "tuple2000_seen": 0}
                    after_x, after_y = apply_field_action(
                        x,
                        y,
                        width,
                        height,
                        fields,
                        variant.action,
                        action_stats,
                    )
                    stats["actions_applied"] += action_stats["actions_applied"]
                    stats["tuple2000_seen"] += action_stats["tuple2000_seen"]
                    applied = action_stats["actions_applied"] > 0
                    target_x = (f1 // 4) % max(1, width)
                    target_y = max(0, min(height, f0))
                    target_dx = target_x - before_x
                    target_dy = target_y - before_y
                    dx = after_x - before_x
                    dy = after_y - before_y
                    absolute_start = payload_base + start
                    before4, after4, next_byte = context_hex(body, absolute_start, total)
                    tuple2000 = f2 == 0x20 and f3 == 0
                    add_bucket(counters, "f1_mod4", str(f1 % 4))
                    add_bucket(counters, "f0", f"{f0:02x}")
                    add_bucket(counters, "field2", f"{f2:02x}")
                    add_bucket(counters, "field3", f"{f3:02x}")
                    add_bucket(counters, "applied", "yes" if applied else "no")
                    add_bucket(
                        counters,
                        "target_y_direction",
                        "forward" if target_dy > 0 else "backward" if target_dy < 0 else "same",
                    )
                    add_bucket(counters, "y_direction", "forward" if dy > 0 else "backward" if dy < 0 else "same")
                    add_bucket(counters, "x_delta_abs", "<=4" if abs(dx) <= 4 else ">4")
                    add_bucket(counters, "y_delta_abs", "<=4" if abs(dy) <= 4 else ">4")
                    events.append(
                        {
                            "rank": "",
                            "event_index": str(event_index),
                            "segment_id": source.get("segment_id", ""),
                            "archive": source.get("archive", ""),
                            "archive_tag": source.get("archive_tag", ""),
                            "pcx_name": source.get("pcx_name", ""),
                            "record_offset": str(absolute_start),
                            "record_hex": body[absolute_start : absolute_start + total].hex(),
                            "fields_hex": fields[:5].hex(),
                            "field0": f"{f0:02x}",
                            "field1": f"{f1:02x}",
                            "field2": f"{f2:02x}",
                            "field3": f"{f3:02x}",
                            "field4": f"{f4:02x}",
                            "f1_mod4": str(f1 % 4),
                            "f1_div4": str(f1 // 4),
                            "tuple2000": "yes" if tuple2000 else "no",
                            "target_x": str(target_x),
                            "target_y": str(target_y),
                            "target_x_delta": str(target_dx),
                            "target_x_delta_abs": str(abs(target_dx)),
                            "target_y_delta": str(target_dy),
                            "target_y_delta_abs": str(abs(target_dy)),
                            "target_y_direction": (
                                "forward" if target_dy > 0 else "backward" if target_dy < 0 else "same"
                            ),
                            "applied": "yes" if applied else "no",
                            "x_before": str(before_x),
                            "y_before": str(before_y),
                            "x_after": str(after_x),
                            "y_after": str(after_y),
                            "x_delta": str(dx),
                            "x_delta_abs": str(abs(dx)),
                            "y_delta": str(dy),
                            "y_delta_abs": str(abs(dy)),
                            "before4_hex": before4,
                            "after4_hex": after4,
                            "next_byte": next_byte,
                        }
                    )
                    x, y = after_x, after_y
            continue
        if byte == 0x20:
            arg1 = payload[pos] if pos < len(payload) else 0
            arg2 = payload[pos + 1] if pos + 1 < len(payload) else 0
            arg3 = payload[pos + 2] if pos + 2 < len(payload) else 0
            if (arg1, arg2, arg3) == (0, 0, 0):
                if variant.zero_policy == "line":
                    x = 0
                    y = min(height, y + 1)
                    pos = min(len(payload), pos + variant.skip)
                    continue
                if variant.zero_policy == "skip":
                    pos = min(len(payload), pos + variant.skip)
                    continue
                continue
            if arg2 >= variant.threshold:
                dy = signed_byte(arg2)
                next_y = y + dy if variant.dy_policy == "add" else y - dy
                if 0 <= next_y < height:
                    x = apply_x_policy(x, width, arg1, variant.x_policy)
                    y = next_y
                    pos = min(len(payload), pos + variant.skip)
                    continue
            pos = min(len(payload), pos + variant.skip)
            continue
        if low <= byte <= high:
            x, y = advance(x, y, width, 1)
            emitted += 1
    stats["final_x"] = x
    stats["final_y"] = y
    stats["emitted"] = emitted
    return events, stats, counters, []


def bucket_rows(counters: dict[str, Counter[str]], event_count: int) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for bucket, counter in sorted(counters.items()):
        for value, count in counter.most_common(32):
            rows.append(
                {
                    "rank": "",
                    "bucket": bucket,
                    "value": value,
                    "count": str(count),
                    "ratio": ratio(count, event_count),
                }
            )
    for rank, row in enumerate(rows, 1):
        row["rank"] = str(rank)
    return rows


def row_num(row: dict[str, str], field: str) -> int:
    return int_value(row, field)


def build_guard_atoms(events: list[dict[str, str]]) -> list[tuple[str, object]]:
    applied_events = [row for row in events if row.get("applied") == "yes"]
    atoms: list[tuple[str, object]] = []
    for field in ("field0", "field1", "field2", "field3", "field4"):
        values = sorted({byte_value(row, field) for row in applied_events})
        for value in values:
            atoms.append((f"{field}==0x{value:02x}", lambda row, field=field, value=value: byte_value(row, field) == value))
        for threshold in (0x10, 0x20, 0x30, 0x40, 0x60, 0x80, 0xC0):
            atoms.append((f"{field}>=0x{threshold:02x}", lambda row, field=field, threshold=threshold: byte_value(row, field) >= threshold))
            atoms.append((f"{field}<0x{threshold:02x}", lambda row, field=field, threshold=threshold: byte_value(row, field) < threshold))
    for mod in range(4):
        atoms.append((f"f1_mod4=={mod}", lambda row, mod=mod: row_num(row, "f1_mod4") == mod))
    atoms.extend(
        [
            ("field1==0", lambda row: byte_value(row, "field1") == 0),
            ("field1!=0", lambda row: byte_value(row, "field1") != 0),
            ("tuple2000", lambda row: row.get("tuple2000") == "yes"),
            ("not_tuple2000", lambda row: row.get("tuple2000") != "yes"),
            ("target_y_forward", lambda row: row.get("target_y_direction") == "forward"),
            ("target_y_backward", lambda row: row.get("target_y_direction") == "backward"),
            ("target_y_same", lambda row: row.get("target_y_direction") == "same"),
            ("target_x_delta_abs<=4", lambda row: row_num(row, "target_x_delta_abs") <= 4),
            ("target_x_delta_abs>4", lambda row: row_num(row, "target_x_delta_abs") > 4),
            ("target_y_delta_abs<=4", lambda row: row_num(row, "target_y_delta_abs") <= 4),
            ("target_y_delta_abs>4", lambda row: row_num(row, "target_y_delta_abs") > 4),
            ("target_y_delta_abs>=16", lambda row: row_num(row, "target_y_delta_abs") >= 16),
            ("target_y_delta_abs>=32", lambda row: row_num(row, "target_y_delta_abs") >= 32),
            ("target_y_delta_abs>=64", lambda row: row_num(row, "target_y_delta_abs") >= 64),
            ("target_y_delta_abs>=128", lambda row: row_num(row, "target_y_delta_abs") >= 128),
        ]
    )
    for field in ("x_before", "y_before", "target_x", "target_y"):
        for threshold in (4, 8, 16, 32, 64, 128, 192):
            atoms.append((f"{field}>={threshold}", lambda row, field=field, threshold=threshold: row_num(row, field) >= threshold))
            atoms.append((f"{field}<{threshold}", lambda row, field=field, threshold=threshold: row_num(row, field) < threshold))
    for field in ("next_byte",):
        values = sorted({byte_value(row, field) for row in applied_events})
        for value in values:
            atoms.append((f"{field}==0x{value:02x}", lambda row, field=field, value=value: byte_value(row, field) == value))
        for threshold in (0x10, 0x20, 0x30, 0x40, 0x80, 0xC0):
            atoms.append((f"{field}>=0x{threshold:02x}", lambda row, field=field, threshold=threshold: byte_value(row, field) >= threshold))
            atoms.append((f"{field}<0x{threshold:02x}", lambda row, field=field, threshold=threshold: byte_value(row, field) < threshold))
    return atoms


def guard_candidate_rows(events: list[dict[str, str]], limit: int) -> list[dict[str, str]]:
    total_applied = sum(1 for row in events if row.get("applied") == "yes")
    total_nonapplied = max(0, len(events) - total_applied)
    atoms = build_guard_atoms(events)
    candidates: list[tuple[float, float, int, str, list[str], list[dict[str, str]]]] = []
    seen: set[str] = set()

    def add_candidate(clauses: list[tuple[str, object]]) -> None:
        guard = " && ".join(name for name, _predicate in clauses)
        if guard in seen:
            return
        seen.add(guard)
        matched = [
            row
            for row in events
            if all(predicate(row) for _name, predicate in clauses)  # type: ignore[misc]
        ]
        applied_matched = sum(1 for row in matched if row.get("applied") == "yes")
        if applied_matched <= 0 or len(matched) <= 1:
            return
        precision = applied_matched / max(1, len(matched))
        recall = applied_matched / max(1, total_applied)
        false_positive_ratio = (len(matched) - applied_matched) / max(1, total_nonapplied)
        score = (precision * 4.0) + (recall * 2.0) - false_positive_ratio
        candidates.append((score, precision, applied_matched, guard, [name for name, _predicate in clauses], matched))

    for atom in atoms:
        add_candidate([atom])
    for left_index, left in enumerate(atoms):
        for right in atoms[left_index + 1 :]:
            add_candidate([left, right])

    candidates.sort(key=lambda item: (-item[0], -item[1], -item[2], item[3]))
    rows: list[dict[str, str]] = []
    for rank, (_score, precision, applied_matched, guard, clauses, matched) in enumerate(candidates[:limit], 1):
        nonapplied_matched = len(matched) - applied_matched
        recall = applied_matched / max(1, total_applied)
        false_positive_ratio = nonapplied_matched / max(1, total_nonapplied)
        examples = [row.get("event_index", "") for row in matched if row.get("applied") == "yes"]
        rows.append(
            {
                "rank": str(rank),
                "guard": guard,
                "clauses": str(len(clauses)),
                "matched": str(len(matched)),
                "applied_matched": str(applied_matched),
                "nonapplied_matched": str(nonapplied_matched),
                "precision": f"{precision:.6f}",
                "recall": f"{recall:.6f}",
                "false_positive_ratio": f"{false_positive_ratio:.6f}",
                "missed_applied": str(total_applied - applied_matched),
                "example_events": "|".join(examples[:16]),
            }
        )
    return rows


def trace_record_offsets(events: list[dict[str, str]]) -> set[int]:
    offsets: set[int] = set()
    for row in events:
        if row.get("applied") != "yes":
            continue
        offset = int_value(row, "record_offset")
        offsets.add(offset)
        if offset >= 4:
            offsets.add(offset - 4)
    return offsets


def record_guard_rows(
    records_path: Path,
    target_pair: str,
    target_record_len: int,
    trace_offsets: set[int],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in read_csv(records_path):
        if (
            row.get("kind") != "pair"
            or row.get("pair") != target_pair
            or int_value(row, "record_len") != target_record_len
        ):
            continue
        record_hex = row.get("record_hex", "")
        if len(record_hex) < 14:
            continue
        try:
            f0, f1, f2, f3, f4 = (int(record_hex[index : index + 2], 16) for index in range(4, 14, 2))
        except ValueError:
            continue
        if f0 < 0x40 or f1 % 4 != 0:
            continue
        record_offset = int_value(row, "record_offset")
        rows.append(
            {
                "record_offset": str(record_offset),
                "record_hex": record_hex,
                "field0": f"{f0:02x}",
                "field1": f"{f1:02x}",
                "field2": f"{f2:02x}",
                "field3": f"{f3:02x}",
                "field4": f"{f4:02x}",
                "f1_mod4": str(f1 % 4),
                "f1_div4": str(f1 // 4),
                "target_x": str(f1 // 4),
                "target_y": str(f0),
                "before0": first_hex_byte(row.get("before4_hex", "")),
                "after0": first_hex_byte(row.get("after4_hex", "")),
                "next_byte": first_hex_byte(row.get("next_byte", "")),
                "trace_label": "trace" if record_offset in trace_offsets else "late",
            }
        )
    return rows


def build_record_guard_atoms(rows: list[dict[str, str]]) -> list[tuple[str, str, object]]:
    trace_rows = [row for row in rows if row.get("trace_label") == "trace"]
    atoms: list[tuple[str, str, object]] = []
    for field in ("field0", "field1", "field2", "field3", "field4"):
        values = sorted({byte_value(row, field) for row in trace_rows})
        for value in values:
            atoms.append(
                (
                    f"{field}==0x{value:02x}",
                    "field",
                    lambda row, field=field, value=value: byte_value(row, field) == value,
                )
            )
        for threshold in (0x10, 0x20, 0x30, 0x40, 0x60, 0x80, 0xC0, 0xE0, 0xF0):
            atoms.append(
                (
                    f"{field}>=0x{threshold:02x}",
                    "field",
                    lambda row, field=field, threshold=threshold: byte_value(row, field) >= threshold,
                )
            )
            atoms.append(
                (
                    f"{field}<0x{threshold:02x}",
                    "field",
                    lambda row, field=field, threshold=threshold: byte_value(row, field) < threshold,
                )
            )
    for mod in range(4):
        atoms.append(("f1_mod4=={mod}".format(mod=mod), "field", lambda row, mod=mod: row_num(row, "f1_mod4") == mod))
    atoms.extend(
        [
            ("field1==0", "field", lambda row: byte_value(row, "field1") == 0),
            ("field1!=0", "field", lambda row: byte_value(row, "field1") != 0),
        ]
    )
    for field in ("target_x", "target_y"):
        values = sorted({row_num(row, field) for row in trace_rows})
        for value in values:
            atoms.append((f"{field}=={value}", "field", lambda row, field=field, value=value: row_num(row, field) == value))
        for threshold in (4, 8, 16, 32, 64, 80, 96, 128, 160, 192, 224):
            atoms.append(
                (
                    f"{field}>={threshold}",
                    "field",
                    lambda row, field=field, threshold=threshold: row_num(row, field) >= threshold,
                )
            )
            atoms.append(
                (
                    f"{field}<{threshold}",
                    "field",
                    lambda row, field=field, threshold=threshold: row_num(row, field) < threshold,
                )
            )
    for field in ("before0", "after0", "next_byte"):
        values = sorted({byte_value(row, field) for row in trace_rows})
        for value in values:
            atoms.append(
                (
                    f"{field}==0x{value:02x}",
                    "byte_context",
                    lambda row, field=field, value=value: byte_value(row, field) == value,
                )
            )
        for threshold in (0x10, 0x20, 0x30, 0x40, 0x60, 0x80, 0xC0, 0xE0, 0xF0):
            atoms.append(
                (
                    f"{field}>=0x{threshold:02x}",
                    "byte_context",
                    lambda row, field=field, threshold=threshold: byte_value(row, field) >= threshold,
                )
            )
            atoms.append(
                (
                    f"{field}<0x{threshold:02x}",
                    "byte_context",
                    lambda row, field=field, threshold=threshold: byte_value(row, field) < threshold,
                )
            )
    return atoms


def record_guard_scope(scopes: list[str]) -> str:
    unique = sorted(set(scopes))
    if len(unique) == 1:
        return unique[0]
    return "+".join(unique)


def record_guard_candidate_rows(
    events: list[dict[str, str]],
    records_path: Path,
    target_pair: str,
    target_record_len: int,
    limit: int,
) -> list[dict[str, str]]:
    rows = record_guard_rows(records_path, target_pair, target_record_len, trace_record_offsets(events))
    total_trace = sum(1 for row in rows if row.get("trace_label") == "trace")
    total_late = max(0, len(rows) - total_trace)
    atoms = build_record_guard_atoms(rows)
    candidates: list[tuple[float, float, int, str, list[str], list[str], list[dict[str, str]]]] = []
    seen: set[str] = set()

    def add_candidate(clauses: list[tuple[str, str, object]]) -> None:
        guard = " && ".join(name for name, _scope, _predicate in clauses)
        if guard in seen:
            return
        seen.add(guard)
        matched = [
            row
            for row in rows
            if all(predicate(row) for _name, _scope, predicate in clauses)  # type: ignore[misc]
        ]
        trace_matched = sum(1 for row in matched if row.get("trace_label") == "trace")
        if trace_matched <= 0 or len(matched) <= 1:
            return
        late_matched = len(matched) - trace_matched
        precision = trace_matched / max(1, len(matched))
        recall = trace_matched / max(1, total_trace)
        false_positive_ratio = late_matched / max(1, total_late)
        score = (precision * 4.0) + (recall * 2.0) - false_positive_ratio
        candidates.append(
            (
                score,
                precision,
                trace_matched,
                guard,
                [scope for _name, scope, _predicate in clauses],
                [name for name, _scope, _predicate in clauses],
                matched,
            )
        )

    for atom in atoms:
        add_candidate([atom])
    for left_index, left in enumerate(atoms):
        for right in atoms[left_index + 1 :]:
            add_candidate([left, right])

    candidates.sort(key=lambda item: (-item[0], -item[1], -item[2], item[3]))
    candidate_rows: list[dict[str, str]] = []
    for rank, (_score, precision, trace_matched, guard, scopes, _clauses, matched) in enumerate(candidates[:limit], 1):
        late_matched = len(matched) - trace_matched
        recall = trace_matched / max(1, total_trace)
        false_positive_ratio = late_matched / max(1, total_late)
        examples = [row.get("record_offset", "") for row in matched if row.get("trace_label") == "trace"]
        candidate_rows.append(
            {
                "rank": str(rank),
                "guard": guard,
                "guard_scope": record_guard_scope(scopes),
                "clauses": str(len(scopes)),
                "matched": str(len(matched)),
                "trace_matched": str(trace_matched),
                "late_matched": str(late_matched),
                "precision": f"{precision:.6f}",
                "recall": f"{recall:.6f}",
                "false_positive_ratio": f"{false_positive_ratio:.6f}",
                "missed_trace": str(total_trace - trace_matched),
                "example_offsets": "|".join(examples[:16]),
            }
        )
    return candidate_rows


def summary_row(
    events: list[dict[str, str]],
    validation_events: list[dict[str, str]],
    validation_stats: dict[str, int],
    stats: dict[str, int],
    semantics_summary: dict[str, str],
    variant,
    issue_rows: int,
    sample_limit: int,
    segment_count: int,
    record_guard: dict[str, str],
    validation_height: int,
) -> dict[str, str]:
    total = len(events)
    f1_mod4_zero = sum(1 for row in events if row.get("f1_mod4") == "0")
    x_delta_zero = sum(1 for row in events if int_value(row, "x_delta_abs") == 0)
    y_delta_zero = sum(1 for row in events if int_value(row, "y_delta_abs") == 0)
    x_delta_abs_le4 = sum(1 for row in events if int_value(row, "x_delta_abs") <= 4)
    y_delta_abs_le4 = sum(1 for row in events if int_value(row, "y_delta_abs") <= 4)
    y_forward = sum(1 for row in events if int_value(row, "y_delta") > 0)
    y_backward = sum(1 for row in events if int_value(row, "y_delta") < 0)
    y_same = total - y_forward - y_backward
    target_y_forward = sum(1 for row in events if row.get("target_y_direction") == "forward")
    target_y_backward = sum(1 for row in events if row.get("target_y_direction") == "backward")
    target_y_same = total - target_y_forward - target_y_backward
    y_values = [int_value(row, "y_after") for row in events]
    f0_values = [int(row.get("field0", "0"), 16) for row in events]
    trace_static_guard_rows = sum(
        1
        for row in events
        if byte_value(row, "field0") >= 0x40 and row_num(row, "f1_mod4") == 0
    )
    validation_static_guard_rows = sum(
        1
        for row in validation_events
        if byte_value(row, "field0") >= 0x40 and row_num(row, "f1_mod4") == 0
    )
    record_static_guard_rows = int_value(record_guard, "record_static_guard_rows")
    best_delta = semantics_summary.get("best_delta_vs_pair", "")
    if issue_rows:
        verdict = "llse_marker_field_state_probe_issues"
        next_action = "fix LLSE marker field state probe inputs"
    elif total and f1_mod4_zero / max(1, total) >= 0.5 and float_text(best_delta) < 0:
        verdict = "llse_marker_field_state_guard_signal"
        if "f0ge40" in variant.action:
            validation_untraced = max(0, record_static_guard_rows - validation_static_guard_rows)
            if validation_untraced:
                validation_text = f"validate {validation_untraced} off-trace records"
            else:
                validation_text = "compare validated static guard replay impact"
            next_action = (
                f"{validation_text} for LLSE 2730 field1 mod4 and field0>=0x40 "
                "before decoder promotion; "
                f"candidate {variant.action}"
            )
        elif "_yforward" in variant.action:
            next_action = (
                "isolate LLSE 2730 yforward field/context guard "
                f"for {stats.get('actions_applied', 0)} events before decoder promotion; "
                f"candidate {variant.action}"
            )
        else:
            next_action = (
                "split LLSE 2730 field semantics by f1 mod4 and cursor jump direction; "
                f"candidate {variant.action}"
            )
    elif total:
        verdict = "llse_marker_field_state_weak_signal"
        next_action = (
            "derive alternate LLSE 2730 state fields; current candidate "
            f"{variant.action} has weak cursor correlation"
        )
    else:
        verdict = "llse_marker_field_state_no_events"
        next_action = "review LLSE marker field state probe inputs"
    return {
        "scope": "total",
        "segment_rows": str(segment_count),
        "event_rows": str(total),
        "sample_rows": str(min(sample_limit, total)),
        "candidate_action": variant.action,
        "candidate_variant": semantics_summary.get("best_variant", ""),
        "candidate_score": semantics_summary.get("best_score", ""),
        "candidate_delta": best_delta,
        "target_pair": variant.target_pair,
        "target_record_len": str(variant.target_record_len),
        "actions_applied": str(stats.get("actions_applied", 0)),
        "tuple2000_seen": str(stats.get("tuple2000_seen", 0)),
        "f1_mod4_zero": str(f1_mod4_zero),
        "f1_mod4_zero_ratio": ratio(f1_mod4_zero, total),
        "x_delta_zero": str(x_delta_zero),
        "x_delta_zero_ratio": ratio(x_delta_zero, total),
        "x_delta_abs_le4": str(x_delta_abs_le4),
        "x_delta_abs_le4_ratio": ratio(x_delta_abs_le4, total),
        "y_delta_zero": str(y_delta_zero),
        "y_delta_zero_ratio": ratio(y_delta_zero, total),
        "y_delta_abs_le4": str(y_delta_abs_le4),
        "y_delta_abs_le4_ratio": ratio(y_delta_abs_le4, total),
        "y_forward": str(y_forward),
        "y_backward": str(y_backward),
        "y_same": str(y_same),
        "target_y_forward": str(target_y_forward),
        "target_y_backward": str(target_y_backward),
        "target_y_same": str(target_y_same),
        "candidate_y_min": str(min(y_values)) if y_values else "",
        "candidate_y_max": str(max(y_values)) if y_values else "",
        "f0_zero": str(sum(1 for value in f0_values if value == 0)),
        "f0_low": str(sum(1 for value in f0_values if value < 0x30)),
        "f0_high": str(sum(1 for value in f0_values if value >= 0xC0)),
        "record_target_rows": record_guard.get("record_target_rows", ""),
        "record_static_guard_rows": str(record_static_guard_rows),
        "trace_static_guard_rows": str(trace_static_guard_rows),
        "record_static_guard_untraced_rows": str(max(0, record_static_guard_rows - trace_static_guard_rows)),
        "validation_height": str(validation_height),
        "validation_event_rows": str(len(validation_events)),
        "validation_actions_applied": str(validation_stats.get("actions_applied", 0)),
        "validation_static_guard_rows": str(validation_static_guard_rows),
        "validation_static_guard_untraced_rows": str(max(0, record_static_guard_rows - validation_static_guard_rows)),
        "record_static_guard_sample_offsets": record_guard.get("record_static_guard_sample_offsets", ""),
        "final_x": str(stats.get("final_x", "")),
        "final_y": str(stats.get("final_y", "")),
        "emitted": str(stats.get("emitted", "")),
        "issue_rows": str(issue_rows),
        "state_verdict": verdict,
        "next_action": next_action,
    }


def render_table(rows: list[dict[str, str]], fieldnames: list[str]) -> str:
    if not rows:
        return "<p class=\"muted\">No rows.</p>"
    head = "".join(f"<th>{html.escape(field)}</th>" for field in fieldnames)
    body = "\n".join(
        "<tr>"
        + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fieldnames)
        + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    events: list[dict[str, str]],
    buckets: list[dict[str, str]],
    guards: list[dict[str, str]],
    record_guards: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "events": events,
        "buckets": buckets,
        "guards": guards,
        "record_guards": record_guards,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f"<a href=\"{html.escape(relative_href(path, output_dir))}\">{html.escape(label)}</a>"
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("events.csv", output_dir / "events.csv"),
            ("buckets.csv", output_dir / "buckets.csv"),
            ("guard_candidates.csv", output_dir / "guard_candidates.csv"),
            ("record_guard_candidates.csv", output_dir / "record_guard_candidates.csv"),
        )
    )
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
:root {{ color-scheme: dark; --bg: #101317; --panel: #181d23; --text: #e8edf2; --muted: #98a4b3; --accent: #74b8ff; --ok: #6fd08c; --warn: #f0b35a; }}
body {{ margin: 0; font-family: system-ui, sans-serif; background: var(--bg); color: var(--text); }}
header, main {{ max-width: 1450px; margin: 0 auto; padding: 24px; }}
h1 {{ margin: 0 0 8px; font-size: 26px; }}
h2 {{ margin: 0 0 12px; font-size: 18px; }}
.muted {{ color: var(--muted); }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin: 20px 0; }}
.stat, .panel {{ background: var(--panel); border: 1px solid #29313b; border-radius: 8px; padding: 14px; }}
.label {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }}
.value {{ font-size: 24px; font-weight: 700; }}
.ok {{ color: var(--ok); }}
.warn {{ color: var(--warn); }}
a {{ color: var(--accent); text-decoration: none; margin-right: 10px; }}
table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
th, td {{ border-bottom: 1px solid #29313b; padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); position: sticky; top: 0; background: var(--panel); }}
td {{ max-width: 560px; overflow-wrap: anywhere; }}
section {{ margin-bottom: 20px; }}
</style>
</head>
<body>
<header>
  <h1>{html.escape(title)}</h1>
  <div class="muted">Cursor-state trace for LLSE 2730 marker field hypotheses.</div>
  <p>{links}</p>
</header>
<main>
  <section class="grid">
    <div class="stat"><div class="label">Events</div><div class="value">{html.escape(summary['event_rows'])}</div></div>
    <div class="stat"><div class="label">Action</div><div class="value">{html.escape(summary['candidate_action'])}</div></div>
    <div class="stat"><div class="label">f1 mod4=0</div><div class="value warn">{html.escape(summary['f1_mod4_zero_ratio'])}</div></div>
    <div class="stat"><div class="label">Issues</div><div class="value ok">{html.escape(summary['issue_rows'])}</div></div>
  </section>
  <section class="panel"><h2>Summary</h2>{render_table([summary], SUMMARY_FIELDNAMES)}</section>
  <section class="panel"><h2>Guard Candidates</h2>{render_table(guards, GUARD_FIELDNAMES)}</section>
  <section class="panel"><h2>Record Guard Candidates</h2>{render_table(record_guards, RECORD_GUARD_FIELDNAMES)}</section>
  <section class="panel"><h2>Buckets</h2>{render_table(buckets, BUCKET_FIELDNAMES)}</section>
  <section class="panel"><h2>Events</h2>{render_table(events, EVENT_FIELDNAMES)}</section>
</main>
<script type="application/json" id="llse-marker-field-state-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(
    args: argparse.Namespace,
) -> tuple[
    dict[str, str],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
]:
    args.output.mkdir(parents=True, exist_ok=True)
    higharg2_summary = read_summary(args.higharg2_summary)
    pair_summary = read_summary(args.pair_length_summary)
    field_summary = read_summary(args.field_profile_summary)
    semantics_summary = read_summary(args.field_semantics_summary)
    action = args.action if args.action != "best" else semantics_summary.get("best_action", "baseline")
    variant = choose_variant(higharg2_summary, pair_summary, field_summary, action)
    record_guard = record_static_guard_profile(args.records, variant.target_pair, variant.target_record_len)
    segment_rows = [row for row in read_csv(args.segments) if row.get("control_path") == TARGET_CONTROL_PATH]
    payload_cache: dict[Path, bytes] = {}
    all_events: list[dict[str, str]] = []
    validation_events: list[dict[str, str]] = []
    merged_stats: Counter[str] = Counter()
    validation_stats: Counter[str] = Counter()
    merged_counters: dict[str, Counter[str]] = {}
    issue_rows = 0
    for source in segment_rows:
        body, issues = load_body(source, payload_cache, args.mix_entry_index)
        events, stats, counters, trace_issues = trace_body(
            source,
            body,
            issues,
            variant,
            args.width,
            args.height,
            args.low,
            args.high,
        )
        if trace_issues:
            issue_rows += 1
        all_events.extend(events)
        merged_stats.update(stats)
        if args.validation_height > args.height:
            extra_events, extra_stats, _extra_counters, extra_issues = trace_body(
                source,
                body,
                issues,
                variant,
                args.width,
                args.validation_height,
                args.low,
                args.high,
            )
            if extra_issues:
                issue_rows += 1
            validation_events.extend(extra_events)
            validation_stats.update(extra_stats)
        else:
            validation_events.extend(events)
            validation_stats.update(stats)
        for bucket, counter in counters.items():
            merged_counters.setdefault(bucket, Counter()).update(counter)
    for rank, row in enumerate(all_events, 1):
        row["rank"] = str(rank)
    buckets = bucket_rows(merged_counters, len(all_events))
    summary = summary_row(
        all_events,
        validation_events,
        dict(validation_stats),
        dict(merged_stats),
        semantics_summary,
        variant,
        issue_rows,
        args.sample_limit,
        len(segment_rows),
        record_guard,
        args.validation_height,
    )
    sampled_events = all_events[: args.sample_limit]
    guards = guard_candidate_rows(all_events, args.guard_limit)
    record_guards = record_guard_candidate_rows(
        all_events,
        args.records,
        variant.target_pair,
        variant.target_record_len,
        args.guard_limit,
    )
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "events.csv", EVENT_FIELDNAMES, sampled_events)
    write_csv(args.output / "buckets.csv", BUCKET_FIELDNAMES, buckets)
    write_csv(args.output / "guard_candidates.csv", GUARD_FIELDNAMES, guards)
    write_csv(args.output / "record_guard_candidates.csv", RECORD_GUARD_FIELDNAMES, record_guards)
    (args.output / "index.html").write_text(
        build_html(summary, sampled_events, buckets, guards, record_guards, args.output, args.title),
        encoding="utf-8",
    )
    return summary, sampled_events, buckets, guards, record_guards


def main() -> None:
    parser = argparse.ArgumentParser(description="Trace LLSE 2730 marker-field cursor states.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--segments", type=Path, default=DEFAULT_SEGMENTS)
    parser.add_argument("--higharg2-summary", type=Path, default=DEFAULT_HIGHARG2_SUMMARY)
    parser.add_argument("--pair-length-summary", type=Path, default=DEFAULT_PAIR_LENGTH_SUMMARY)
    parser.add_argument("--field-profile-summary", type=Path, default=DEFAULT_FIELD_PROFILE_SUMMARY)
    parser.add_argument("--field-semantics-summary", type=Path, default=DEFAULT_FIELD_SEMANTICS_SUMMARY)
    parser.add_argument("--records", type=Path, default=DEFAULT_RECORDS)
    parser.add_argument("--mix-entry-index", type=int, default=DEFAULT_MIX_ENTRY_INDEX)
    parser.add_argument("--width", type=int, default=64)
    parser.add_argument("--height", type=int, default=512)
    parser.add_argument("--validation-height", type=int, default=2048)
    parser.add_argument("--low", type=lambda value: int(value, 0), default=0x30)
    parser.add_argument("--high", type=lambda value: int(value, 0), default=0xBF)
    parser.add_argument("--action", default="best")
    parser.add_argument("--sample-limit", type=int, default=240)
    parser.add_argument("--guard-limit", type=int, default=160)
    parser.add_argument("--title", default="Lands of Lore II .tex LLSE Marker Field State Probe")
    args = parser.parse_args()

    summary, _events, _buckets, guards, record_guards = write_report(args)
    print(f"Events: {summary['event_rows']}")
    print(f"Candidate action: {summary['candidate_action']}")
    print(f"Candidate delta: {summary['candidate_delta']}")
    print(f"Actions applied: {summary['actions_applied']}/{summary['event_rows']}")
    print(f"f1 mod4 zero: {summary['f1_mod4_zero']} ({summary['f1_mod4_zero_ratio']})")
    print(f"x delta <=4: {summary['x_delta_abs_le4']} ({summary['x_delta_abs_le4_ratio']})")
    print(f"y delta <=4: {summary['y_delta_abs_le4']} ({summary['y_delta_abs_le4_ratio']})")
    print(
        "Record static guard: "
        f"{summary['record_static_guard_rows']}/{summary['record_target_rows']} "
        f"(trace {summary['trace_static_guard_rows']})"
    )
    print(
        "Validation static guard: "
        f"{summary['validation_static_guard_rows']}/{summary['record_static_guard_rows']} "
        f"at height {summary['validation_height']}"
    )
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"State verdict: {summary['state_verdict']}")
    print(f"Next action: {summary['next_action']}")
    if guards:
        print(f"Top guard: {guards[0]['guard']} precision {guards[0]['precision']} recall {guards[0]['recall']}")
    if record_guards:
        print(
            "Top record guard: "
            f"{record_guards[0]['guard']} precision {record_guards[0]['precision']} "
            f"recall {record_guards[0]['recall']}"
        )
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
