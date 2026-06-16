#!/usr/bin/env python3
"""Trace first mismatches for the best .tex gap replay candidates."""

from __future__ import annotations

import argparse
import csv
import html
import json
from dataclasses import dataclass
from pathlib import Path

from lolg_tex_gap_fixture_replay import (
    build_candidates as build_fixture_candidates,
    common_prefix,
    exact_byte_count,
    first_mismatch,
)
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_mismatch_trace_probe")
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_CONTROL_BEST = Path("output/tex_gap_control_grammar_probe/best_by_fixture.csv")
DEFAULT_REPLAY_BEST = Path("output/tex_gap_fixture_replay/best_by_fixture.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "fixture_rows",
    "trace_rows",
    "control_trace_rows",
    "replay_trace_rows",
    "operation_rows",
    "full_match_rows",
    "first_mismatch_rows",
    "output_short_rows",
    "expected_zero_mismatch_rows",
    "output_zero_mismatch_rows",
    "best_control_prefix",
    "best_control_exact",
    "best_replay_prefix",
    "best_replay_exact",
    "issue_rows",
]

TRACE_FIELDNAMES = [
    "source",
    "rank",
    "rule_type",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "frontier_type",
    "variant",
    "parameter",
    "payload_offset",
    "pixel_gap",
    "segment_gap_bytes",
    "input_bytes",
    "consumed_bytes",
    "produced_bytes",
    "prefix_bytes",
    "prefix_ratio",
    "exact_bytes",
    "exact_ratio",
    "full_match",
    "first_mismatch_at",
    "mismatch_kind",
    "expected_byte_hex",
    "output_byte_hex",
    "expected_run_value_hex",
    "expected_run_length",
    "output_run_value_hex",
    "output_run_length",
    "expected_context_hex",
    "output_context_hex",
    "segment_context_hex",
    "expected_window8_hex",
    "segment_window8_match_offset",
    "payload_window8_match_offset",
    "op_index_at_mismatch",
    "op_kind_at_mismatch",
    "control_abs_offset_at_mismatch",
    "control_hex_at_mismatch",
    "input_abs_start_at_mismatch",
    "input_abs_end_at_mismatch",
    "output_start_at_mismatch",
    "output_end_at_mismatch",
    "next_input_hex",
    "notes",
    "issues",
]

OP_FIELDNAMES = [
    "source",
    "rank",
    "pcx_name",
    "frontier_id",
    "variant",
    "parameter",
    "payload_offset",
    "op_index",
    "op_kind",
    "control_abs_offset",
    "control_hex",
    "input_abs_start",
    "input_abs_end",
    "output_start",
    "output_end",
    "requested_count",
    "emitted_count",
    "overlaps_mismatch",
    "output_hex",
    "expected_hex",
    "notes",
]


@dataclass(frozen=True)
class TraceOp:
    op_index: int
    op_kind: str
    control_abs_offset: int
    control_hex: str
    input_abs_start: int
    input_abs_end: int
    output_start: int
    output_end: int
    requested_count: int
    emitted_count: int
    notes: str = ""


@dataclass(frozen=True)
class TraceResult:
    output: bytes
    consumed: int
    ops: list[TraceOp]
    notes: str = ""


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


def parse_params(parameter: str) -> dict[str, int]:
    params: dict[str, int] = {}
    for part in parameter.split(";"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        try:
            params[key.strip()] = int(value.strip(), 0)
        except ValueError:
            continue
    return params


def append_zero_trace(
    output: bytearray,
    ops: list[TraceOp],
    *,
    op_index: int,
    control_abs: int,
    control_hex: str,
    count: int,
    limit: int,
) -> None:
    if count <= 0 or len(output) >= limit:
        emitted = 0
    else:
        emitted = min(count, limit - len(output))
        output.extend(b"\x00" * emitted)
    start = len(output) - emitted
    ops.append(
        TraceOp(
            op_index=op_index,
            op_kind="zero",
            control_abs_offset=control_abs,
            control_hex=control_hex,
            input_abs_start=-1,
            input_abs_end=-1,
            output_start=start,
            output_end=start + emitted,
            requested_count=count,
            emitted_count=emitted,
        )
    )


def append_copy_trace(
    output: bytearray,
    data: bytes,
    cursor: int,
    ops: list[TraceOp],
    *,
    op_index: int,
    base_offset: int,
    control_abs: int,
    control_hex: str,
    count: int,
    limit: int,
) -> int:
    available = 0
    if count > 0 and len(output) < limit:
        available = max(0, min(count, len(data) - cursor, limit - len(output)))
        if available:
            output.extend(data[cursor : cursor + available])
    start = len(output) - available
    notes = "literal_read_past_input" if cursor + count > len(data) else ""
    ops.append(
        TraceOp(
            op_index=op_index,
            op_kind="copy",
            control_abs_offset=control_abs,
            control_hex=control_hex,
            input_abs_start=base_offset + cursor,
            input_abs_end=base_offset + min(cursor + count, len(data)),
            output_start=start,
            output_end=start + available,
            requested_count=count,
            emitted_count=available,
            notes=notes,
        )
    )
    return cursor + max(0, count)


def decode_flag_trace(data: bytes, limit: int, *, high_mode: str, bias: int, base_offset: int) -> TraceResult:
    output = bytearray()
    ops: list[TraceOp] = []
    cursor = 0
    op_index = 0
    truncated = False
    while cursor < len(data) and len(output) < limit:
        control_cursor = cursor
        control = data[cursor]
        cursor += 1
        count = (control & 0x7F) + bias
        high = bool(control & 0x80)
        copy = high if high_mode == "copy" else not high
        if copy:
            cursor = append_copy_trace(
                output,
                data,
                cursor,
                ops,
                op_index=op_index,
                base_offset=base_offset,
                control_abs=base_offset + control_cursor,
                control_hex=f"{control:02x}",
                count=count,
                limit=limit,
            )
        else:
            append_zero_trace(
                output,
                ops,
                op_index=op_index,
                control_abs=base_offset + control_cursor,
                control_hex=f"{control:02x}",
                count=count,
                limit=limit,
            )
        op_index += 1
        if cursor > len(data):
            truncated = True
            break
    return TraceResult(bytes(output[:limit]), min(cursor, len(data)), ops, "literal_read_past_input" if truncated else "")


def decode_nibble_trace(
    data: bytes,
    limit: int,
    *,
    mode: str,
    zero_bias: int,
    copy_bias: int,
    base_offset: int,
) -> TraceResult:
    output = bytearray()
    ops: list[TraceOp] = []
    cursor = 0
    op_index = 0
    truncated = False
    while cursor < len(data) and len(output) < limit:
        control_cursor = cursor
        control = data[cursor]
        cursor += 1
        hi = control >> 4
        lo = control & 0x0F
        control_abs = base_offset + control_cursor
        control_hex = f"{control:02x}"
        pairs: list[tuple[str, int]]
        if mode == "hi_zero_lo_copy":
            pairs = [("zero", hi + zero_bias), ("copy", lo + copy_bias)]
        elif mode == "lo_zero_hi_copy":
            pairs = [("zero", lo + zero_bias), ("copy", hi + copy_bias)]
        elif mode == "hi_copy_lo_zero":
            pairs = [("copy", hi + copy_bias), ("zero", lo + zero_bias)]
        elif mode == "lo_copy_hi_zero":
            pairs = [("copy", lo + copy_bias), ("zero", hi + zero_bias)]
        else:
            raise ValueError(f"unknown nibble mode: {mode}")
        for op_kind, count in pairs:
            if len(output) >= limit:
                break
            if op_kind == "copy":
                cursor = append_copy_trace(
                    output,
                    data,
                    cursor,
                    ops,
                    op_index=op_index,
                    base_offset=base_offset,
                    control_abs=control_abs,
                    control_hex=control_hex,
                    count=count,
                    limit=limit,
                )
            else:
                append_zero_trace(
                    output,
                    ops,
                    op_index=op_index,
                    control_abs=control_abs,
                    control_hex=control_hex,
                    count=count,
                    limit=limit,
                )
            op_index += 1
        if cursor > len(data):
            truncated = True
            break
    return TraceResult(bytes(output[:limit]), min(cursor, len(data)), ops, "literal_read_past_input" if truncated else "")


def decode_pair_trace(
    data: bytes,
    limit: int,
    *,
    mode: str,
    zero_bias: int,
    copy_bias: int,
    base_offset: int,
) -> TraceResult:
    output = bytearray()
    ops: list[TraceOp] = []
    cursor = 0
    op_index = 0
    truncated = False
    while cursor + 1 < len(data) and len(output) < limit:
        control_cursor = cursor
        first = data[cursor]
        second = data[cursor + 1]
        cursor += 2
        control_abs = base_offset + control_cursor
        control_hex = f"{first:02x}{second:02x}"
        if mode == "zero_copy":
            pairs = [("zero", first + zero_bias), ("copy", second + copy_bias)]
        elif mode == "copy_zero":
            pairs = [("copy", first + copy_bias), ("zero", second + zero_bias)]
        else:
            raise ValueError(f"unknown pair mode: {mode}")
        for op_kind, count in pairs:
            if len(output) >= limit:
                break
            if op_kind == "copy":
                cursor = append_copy_trace(
                    output,
                    data,
                    cursor,
                    ops,
                    op_index=op_index,
                    base_offset=base_offset,
                    control_abs=control_abs,
                    control_hex=control_hex,
                    count=count,
                    limit=limit,
                )
            else:
                append_zero_trace(
                    output,
                    ops,
                    op_index=op_index,
                    control_abs=control_abs,
                    control_hex=control_hex,
                    count=count,
                    limit=limit,
                )
            op_index += 1
        if cursor > len(data):
            truncated = True
            break
    return TraceResult(bytes(output[:limit]), min(cursor, len(data)), ops, "literal_read_past_input" if truncated else "")


def decode_control_best(segment: bytes, expected_len: int, best: dict[str, str]) -> TraceResult:
    variant = best.get("best_variant", "")
    params = parse_params(best.get("best_parameter", ""))
    offset = int_value(best, "best_payload_offset")
    data = segment[offset:] if 0 <= offset < len(segment) else b""
    if variant.startswith("flag_high_"):
        return decode_flag_trace(
            data,
            expected_len,
            high_mode=variant.removeprefix("flag_high_"),
            bias=params.get("bias", 0),
            base_offset=offset,
        )
    if variant.startswith("nibble_"):
        return decode_nibble_trace(
            data,
            expected_len,
            mode=variant.removeprefix("nibble_"),
            zero_bias=params.get("z_bias", 0),
            copy_bias=params.get("c_bias", 0),
            base_offset=offset,
        )
    if variant.startswith("pair_"):
        return decode_pair_trace(
            data,
            expected_len,
            mode=variant.removeprefix("pair_"),
            zero_bias=params.get("z_bias", 0),
            copy_bias=params.get("c_bias", 0),
            base_offset=offset,
        )
    return TraceResult(b"", 0, [], f"unsupported_control_variant:{variant}")


def same_run(data: bytes, offset: int) -> tuple[str, int]:
    if offset < 0 or offset >= len(data):
        return "", 0
    value = data[offset]
    end = offset
    while end < len(data) and data[end] == value:
        end += 1
    return f"{value:02x}", end - offset


def hex_at(data: bytes, offset: int) -> str:
    if offset < 0 or offset >= len(data):
        return ""
    return f"{data[offset]:02x}"


def context_hex(data: bytes, center: int, radius: int) -> str:
    if center < 0:
        return ""
    start = max(0, center - radius)
    end = min(len(data), center + radius)
    return data[start:end].hex()


def find_window(data: bytes, window: bytes) -> str:
    if not window:
        return ""
    index = data.find(window)
    return str(index) if index >= 0 else ""


def op_at_mismatch(ops: list[TraceOp], mismatch: int, produced_len: int) -> TraceOp | None:
    for op in ops:
        if op.output_start <= mismatch < op.output_end:
            return op
    if mismatch >= produced_len and ops:
        return ops[-1]
    return None


def op_rows_for_trace(
    *,
    fixture: dict[str, str],
    best: dict[str, str],
    result: TraceResult,
    expected: bytes,
    mismatch: int,
    radius: int,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if mismatch < 0:
        selected = result.ops[: min(6, len(result.ops))]
    else:
        selected = [
            op
            for op in result.ops
            if op.output_end >= max(0, mismatch - radius) and op.output_start <= mismatch + radius
        ]
    for op in selected:
        start = op.output_start
        end = op.output_end
        rows.append(
            {
                "source": "control_grammar",
                "rank": fixture.get("rank", ""),
                "pcx_name": fixture.get("pcx_name", ""),
                "frontier_id": fixture.get("frontier_id", ""),
                "variant": best.get("best_variant", ""),
                "parameter": best.get("best_parameter", ""),
                "payload_offset": best.get("best_payload_offset", ""),
                "op_index": str(op.op_index),
                "op_kind": op.op_kind,
                "control_abs_offset": str(op.control_abs_offset),
                "control_hex": op.control_hex,
                "input_abs_start": "" if op.input_abs_start < 0 else str(op.input_abs_start),
                "input_abs_end": "" if op.input_abs_end < 0 else str(op.input_abs_end),
                "output_start": str(start),
                "output_end": str(end),
                "requested_count": str(op.requested_count),
                "emitted_count": str(op.emitted_count),
                "overlaps_mismatch": "1" if start <= mismatch < end else "0",
                "output_hex": result.output[start:end].hex(),
                "expected_hex": expected[start:end].hex(),
                "notes": op.notes,
            }
        )
    return rows


def trace_row(
    *,
    source: str,
    fixture: dict[str, str],
    variant: str,
    parameter: str,
    payload_offset: str,
    segment: bytes,
    expected: bytes,
    output: bytes,
    consumed: int,
    ops: list[TraceOp],
    notes: list[str],
    issues: list[str],
    context: int,
) -> dict[str, str]:
    prefix = common_prefix(output, expected)
    exact = exact_byte_count(output, expected)
    full_match = bool(expected and prefix == len(expected) and len(output) >= len(expected))
    mismatch = -1 if full_match else prefix
    mismatch_text = first_mismatch(prefix, output, expected) if not full_match else ""
    if full_match:
        mismatch_kind = "full_match"
    elif prefix >= len(output):
        mismatch_kind = "output_short"
    else:
        mismatch_kind = "byte_diff"
    expected_run_value, expected_run_length = same_run(expected, mismatch)
    output_run_value, output_run_length = same_run(output, mismatch)
    op = op_at_mismatch(ops, mismatch, len(output))
    window8 = expected[mismatch : mismatch + 8] if 0 <= mismatch < len(expected) else b""
    offset = int(payload_offset or 0) if payload_offset else 0
    payload = segment[offset:] if 0 <= offset < len(segment) else b""
    next_input = b""
    if op and op.input_abs_end >= 0:
        next_input = segment[op.input_abs_end : op.input_abs_end + 16]
    elif op:
        next_input = segment[op.control_abs_offset + 1 : op.control_abs_offset + 17]
    return {
        "source": source,
        "rank": fixture.get("rank", ""),
        "rule_type": fixture.get("rule_type", ""),
        "archive": fixture.get("archive", ""),
        "archive_tag": fixture.get("archive_tag", ""),
        "pcx_name": fixture.get("pcx_name", ""),
        "frontier_id": fixture.get("frontier_id", ""),
        "frontier_type": fixture.get("frontier_type", ""),
        "variant": variant,
        "parameter": parameter,
        "payload_offset": payload_offset,
        "pixel_gap": str(len(expected)),
        "segment_gap_bytes": str(len(segment)),
        "input_bytes": str(len(payload) if source == "control_grammar" else len(segment)),
        "consumed_bytes": str(consumed),
        "produced_bytes": str(len(output)),
        "prefix_bytes": str(prefix),
        "prefix_ratio": f"{(prefix / len(expected)) if expected else 0.0:.6f}",
        "exact_bytes": str(exact),
        "exact_ratio": f"{(exact / len(expected)) if expected else 0.0:.6f}",
        "full_match": "1" if full_match else "0",
        "first_mismatch_at": mismatch_text,
        "mismatch_kind": mismatch_kind,
        "expected_byte_hex": hex_at(expected, mismatch),
        "output_byte_hex": hex_at(output, mismatch),
        "expected_run_value_hex": expected_run_value,
        "expected_run_length": str(expected_run_length),
        "output_run_value_hex": output_run_value,
        "output_run_length": str(output_run_length),
        "expected_context_hex": context_hex(expected, mismatch, context),
        "output_context_hex": context_hex(output, mismatch, context),
        "segment_context_hex": context_hex(segment, offset, context),
        "expected_window8_hex": window8.hex(),
        "segment_window8_match_offset": find_window(segment, window8),
        "payload_window8_match_offset": find_window(payload, window8),
        "op_index_at_mismatch": "" if op is None else str(op.op_index),
        "op_kind_at_mismatch": "" if op is None else op.op_kind,
        "control_abs_offset_at_mismatch": "" if op is None else str(op.control_abs_offset),
        "control_hex_at_mismatch": "" if op is None else op.control_hex,
        "input_abs_start_at_mismatch": "" if op is None or op.input_abs_start < 0 else str(op.input_abs_start),
        "input_abs_end_at_mismatch": "" if op is None or op.input_abs_end < 0 else str(op.input_abs_end),
        "output_start_at_mismatch": "" if op is None else str(op.output_start),
        "output_end_at_mismatch": "" if op is None else str(op.output_end),
        "next_input_hex": next_input.hex(),
        "notes": ";".join(note for note in notes if note),
        "issues": ";".join(issues),
    }


def replay_output_for_best(
    fixture: dict[str, str],
    best: dict[str, str],
    segment: bytes,
    expected: bytes,
    fragment: bytes,
    issues: list[str],
) -> tuple[bytes, int, list[str]]:
    candidates = build_fixture_candidates(
        segment,
        expected,
        fragment,
        best_skip=int_value(fixture, "best_raw_skip"),
    )
    variant = best.get("best_variant", "")
    parameter = best.get("best_parameter", "")
    for candidate in candidates:
        if candidate.variant == variant and candidate.parameter == parameter:
            return candidate.output, candidate.consumed, [candidate.notes]
    issues.append("missing_replay_best_candidate")
    return b"", 0, []


def build_rows(
    fixtures_path: Path,
    control_best_path: Path,
    replay_best_path: Path,
    *,
    limit: int,
    context: int,
    op_radius: int,
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    fixtures = sorted(read_rows(fixtures_path), key=lambda row: int_value(row, "rank"))
    if limit > 0:
        fixtures = fixtures[:limit]
    control_best = {fixture_key(row): row for row in read_rows(control_best_path)}
    replay_best = {fixture_key(row): row for row in read_rows(replay_best_path)}
    trace_rows: list[dict[str, str]] = []
    op_rows: list[dict[str, str]] = []

    for fixture in fixtures:
        issues: list[str] = []
        if fixture.get("issues"):
            issues.append("source_fixture_has_issues")
        segment = load_bytes(fixture.get("segment_gap_path", ""), issues, "segment")
        expected = load_bytes(fixture.get("expected_gap_path", ""), issues, "expected")
        fragment = load_bytes(fixture.get("fragment_path", ""), issues, "fragment")
        if len(segment) != int_value(fixture, "segment_gap_bytes"):
            issues.append("segment_size_mismatch")
        if len(expected) != int_value(fixture, "pixel_gap"):
            issues.append("expected_size_mismatch")
        if len(fragment) != int_value(fixture, "fragment_bytes"):
            issues.append("fragment_size_mismatch")

        key = fixture_key(fixture)
        control = control_best.get(key)
        if control is None:
            trace_rows.append(
                trace_row(
                    source="control_grammar",
                    fixture=fixture,
                    variant="",
                    parameter="",
                    payload_offset="",
                    segment=segment,
                    expected=expected,
                    output=b"",
                    consumed=0,
                    ops=[],
                    notes=[],
                    issues=issues + ["missing_control_best_row"],
                    context=context,
                )
            )
        else:
            result = decode_control_best(segment, len(expected), control)
            notes = [result.notes, control.get("notes", "")]
            row = trace_row(
                source="control_grammar",
                fixture=fixture,
                variant=control.get("best_variant", ""),
                parameter=control.get("best_parameter", ""),
                payload_offset=control.get("best_payload_offset", ""),
                segment=segment,
                expected=expected,
                output=result.output,
                consumed=result.consumed,
                ops=result.ops,
                notes=notes,
                issues=issues + ([result.notes] if result.notes.startswith("unsupported_") else []),
                context=context,
            )
            trace_rows.append(row)
            mismatch = int_value(row, "prefix_bytes") if row.get("full_match") != "1" else -1
            op_rows.extend(
                op_rows_for_trace(
                    fixture=fixture,
                    best=control,
                    result=result,
                    expected=expected,
                    mismatch=mismatch,
                    radius=op_radius,
                )
            )

        replay = replay_best.get(key)
        if replay is None:
            trace_rows.append(
                trace_row(
                    source="fixture_replay",
                    fixture=fixture,
                    variant="",
                    parameter="",
                    payload_offset="",
                    segment=segment,
                    expected=expected,
                    output=b"",
                    consumed=0,
                    ops=[],
                    notes=[],
                    issues=issues + ["missing_replay_best_row"],
                    context=context,
                )
            )
        else:
            replay_issues = list(issues)
            output, consumed, notes = replay_output_for_best(fixture, replay, segment, expected, fragment, replay_issues)
            trace_rows.append(
                trace_row(
                    source="fixture_replay",
                    fixture=fixture,
                    variant=replay.get("best_variant", ""),
                    parameter=replay.get("best_parameter", ""),
                    payload_offset="",
                    segment=segment,
                    expected=expected,
                    output=output,
                    consumed=consumed,
                    ops=[],
                    notes=notes + [replay.get("notes", "")],
                    issues=replay_issues,
                    context=context,
                )
            )

    return fixtures, trace_rows, op_rows


def summary_row(fixtures: list[dict[str, str]], trace_rows: list[dict[str, str]], op_rows: list[dict[str, str]]) -> dict[str, str]:
    control_rows = [row for row in trace_rows if row.get("source") == "control_grammar"]
    replay_rows = [row for row in trace_rows if row.get("source") == "fixture_replay"]
    return {
        "scope": "total",
        "fixture_rows": str(len(fixtures)),
        "trace_rows": str(len(trace_rows)),
        "control_trace_rows": str(len(control_rows)),
        "replay_trace_rows": str(len(replay_rows)),
        "operation_rows": str(len(op_rows)),
        "full_match_rows": str(sum(1 for row in trace_rows if row.get("full_match") == "1")),
        "first_mismatch_rows": str(sum(1 for row in trace_rows if row.get("first_mismatch_at"))),
        "output_short_rows": str(sum(1 for row in trace_rows if row.get("mismatch_kind") == "output_short")),
        "expected_zero_mismatch_rows": str(
            sum(1 for row in trace_rows if row.get("expected_byte_hex") == "00" and row.get("first_mismatch_at"))
        ),
        "output_zero_mismatch_rows": str(
            sum(1 for row in trace_rows if row.get("output_byte_hex") == "00" and row.get("first_mismatch_at"))
        ),
        "best_control_prefix": str(max([int_value(row, "prefix_bytes") for row in control_rows] or [0])),
        "best_control_exact": str(max([int_value(row, "exact_bytes") for row in control_rows] or [0])),
        "best_replay_prefix": str(max([int_value(row, "prefix_bytes") for row in replay_rows] or [0])),
        "best_replay_exact": str(max([int_value(row, "exact_bytes") for row in replay_rows] or [0])),
        "issue_rows": str(sum(1 for row in trace_rows if row.get("issues"))),
    }


def render_trace_row(row: dict[str, str]) -> str:
    return (
        "<tr>"
        f"<td>{html.escape(row.get('source', ''))}</td>"
        f"<td>{html.escape(row.get('rank', ''))}</td>"
        f"<td>{html.escape(row.get('pcx_name', ''))}</td>"
        f"<td>{html.escape(row.get('frontier_id', ''))}</td>"
        f"<td>{html.escape(row.get('variant', ''))}</td>"
        f"<td>{html.escape(row.get('parameter', ''))}</td>"
        f"<td>{html.escape(row.get('payload_offset', ''))}</td>"
        f"<td>{html.escape(row.get('prefix_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('exact_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('first_mismatch_at', ''))}</td>"
        f"<td>{html.escape(row.get('mismatch_kind', ''))}</td>"
        f"<td>{html.escape(row.get('expected_byte_hex', ''))}</td>"
        f"<td>{html.escape(row.get('output_byte_hex', ''))}</td>"
        f"<td>{html.escape(row.get('expected_run_length', ''))}</td>"
        f"<td>{html.escape(row.get('op_kind_at_mismatch', ''))}</td>"
        f"<td>{html.escape(row.get('control_abs_offset_at_mismatch', ''))}</td>"
        f"<td><code>{html.escape(row.get('control_hex_at_mismatch', ''))}</code></td>"
        f"<td><code>{html.escape(row.get('expected_context_hex', ''))}</code></td>"
        f"<td><code>{html.escape(row.get('output_context_hex', ''))}</code></td>"
        f"<td>{html.escape(row.get('issues', ''))}</td>"
        "</tr>"
    )


def render_op_row(row: dict[str, str]) -> str:
    return (
        "<tr>"
        f"<td>{html.escape(row.get('rank', ''))}</td>"
        f"<td>{html.escape(row.get('pcx_name', ''))}</td>"
        f"<td>{html.escape(row.get('frontier_id', ''))}</td>"
        f"<td>{html.escape(row.get('op_index', ''))}</td>"
        f"<td>{html.escape(row.get('op_kind', ''))}</td>"
        f"<td>{html.escape(row.get('control_abs_offset', ''))}</td>"
        f"<td><code>{html.escape(row.get('control_hex', ''))}</code></td>"
        f"<td>{html.escape(row.get('input_abs_start', ''))}</td>"
        f"<td>{html.escape(row.get('input_abs_end', ''))}</td>"
        f"<td>{html.escape(row.get('output_start', ''))}</td>"
        f"<td>{html.escape(row.get('output_end', ''))}</td>"
        f"<td>{html.escape(row.get('requested_count', ''))}</td>"
        f"<td>{html.escape(row.get('emitted_count', ''))}</td>"
        f"<td>{html.escape(row.get('overlaps_mismatch', ''))}</td>"
        f"<td><code>{html.escape(row.get('output_hex', ''))}</code></td>"
        f"<td><code>{html.escape(row.get('expected_hex', ''))}</code></td>"
        f"<td>{html.escape(row.get('notes', ''))}</td>"
        "</tr>"
    )


def build_html(
    summary: dict[str, str],
    trace_rows: list[dict[str, str]],
    op_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "traces": trace_rows, "operations": op_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("mismatches.csv", output_dir / "mismatches.csv"),
            ("control_operations.csv", output_dir / "control_operations.csv"),
        )
    )
    trace_markup = "\n".join(
        render_trace_row(row)
        for row in sorted(
            trace_rows,
            key=lambda row: (int_value(row, "rank"), row.get("source", "")),
        )
    )
    op_markup = "\n".join(
        render_op_row(row)
        for row in sorted(
            op_rows,
            key=lambda row: (int_value(row, "rank"), int_value(row, "op_index")),
        )
    )
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
.wrap {{ width: min(1700px, calc(100vw - 28px)); margin: 0 auto; }}
header {{ border-bottom: 1px solid var(--line); background: #12171b; padding: 18px 0 14px; }}
h1 {{ margin: 0; font-size: 21px; font-weight: 700; letter-spacing: 0; }}
h2 {{ margin: 0 0 10px; font-size: 16px; }}
.sub {{ color: var(--muted); margin-top: 4px; }}
main {{ padding: 16px 0 28px; display: grid; gap: 16px; }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 10px; }}
.stat, .panel {{ border: 1px solid var(--line); border-radius: 8px; background: var(--panel); padding: 10px; }}
.label, .muted {{ color: var(--muted); }}
.value {{ font-size: 24px; font-weight: 750; line-height: 1.05; margin-top: 4px; }}
.ok {{ color: var(--ok); }}
.panel {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; min-width: 1550px; }}
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
    <div class="sub">Premieres ruptures des meilleurs replays .tex, avec contexte bytes et operations controle.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Fixtures</div><div class="value">{html.escape(summary['fixture_rows'])}</div></div>
    <div class="stat"><div class="label">Trace rows</div><div class="value">{html.escape(summary['trace_rows'])}</div></div>
    <div class="stat"><div class="label">Operations</div><div class="value">{html.escape(summary['operation_rows'])}</div></div>
    <div class="stat"><div class="label">Best control prefix</div><div class="value ok">{html.escape(summary['best_control_prefix'])}</div></div>
    <div class="stat"><div class="label">Best replay prefix</div><div class="value ok">{html.escape(summary['best_replay_prefix'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div></section>
  <section class="panel">
    <h2>Mismatch traces</h2>
    <table>
      <thead><tr><th>Source</th><th>Rank</th><th>PCX</th><th>Frontier</th><th>Variant</th><th>Param</th><th>Offset</th><th>Prefix</th><th>Exact</th><th>Mismatch</th><th>Kind</th><th>Expected</th><th>Output</th><th>Expected run</th><th>Op</th><th>Control off</th><th>Control</th><th>Expected context</th><th>Output context</th><th>Issues</th></tr></thead>
      <tbody>{trace_markup}</tbody>
    </table>
  </section>
  <section class="panel">
    <h2>Control operations near mismatch</h2>
    <table>
      <thead><tr><th>Rank</th><th>PCX</th><th>Frontier</th><th>Op</th><th>Kind</th><th>Control off</th><th>Control</th><th>Input start</th><th>Input end</th><th>Out start</th><th>Out end</th><th>Requested</th><th>Emitted</th><th>Mismatch</th><th>Output</th><th>Expected</th><th>Notes</th></tr></thead>
      <tbody>{op_markup}</tbody>
    </table>
  </section>
</main>
<script>
const TEX_GAP_MISMATCH_TRACE_PROBE = {data_json};
</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    fixtures: Path,
    control_best: Path,
    replay_best: Path,
    *,
    limit: int,
    context: int,
    op_radius: int,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    fixture_rows, trace_rows, op_rows = build_rows(
        fixtures,
        control_best,
        replay_best,
        limit=limit,
        context=context,
        op_radius=op_radius,
    )
    summary = summary_row(fixture_rows, trace_rows, op_rows)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "mismatches.csv", TRACE_FIELDNAMES, trace_rows)
    write_csv(output_dir / "control_operations.csv", OP_FIELDNAMES, op_rows)
    (output_dir / "index.html").write_text(build_html(summary, trace_rows, op_rows, output_dir, title))
    return summary, trace_rows, op_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Trace first mismatches for .tex gap replay probes.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--control-best", type=Path, default=DEFAULT_CONTROL_BEST)
    parser.add_argument("--replay-best", type=Path, default=DEFAULT_REPLAY_BEST)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--context", type=int, default=16)
    parser.add_argument("--op-radius", type=int, default=24)
    parser.add_argument("--title", default="Lands of Lore II .tex Gap Mismatch Trace Probe")
    args = parser.parse_args()

    summary, _trace_rows, _op_rows = write_report(
        args.output,
        args.fixtures,
        args.control_best,
        args.replay_best,
        limit=args.limit,
        context=args.context,
        op_radius=args.op_radius,
        title=args.title,
    )
    print(f"Fixture rows: {summary['fixture_rows']}")
    print(f"Trace rows: {summary['trace_rows']}")
    print(f"Operation rows: {summary['operation_rows']}")
    print(f"Best control prefix: {summary['best_control_prefix']}")
    print(f"Best replay prefix: {summary['best_replay_prefix']}")
    print(f"Issue rows: {summary['issue_rows']}")


if __name__ == "__main__":
    main()
