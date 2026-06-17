#!/usr/bin/env python3
"""Probe compact/control producers for target-only frontier 80 bridge deltas."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from lolg_tex_gap_opcode_probe import relative_href, write_csv
from lolg_tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_gradient_bridge_probe import (
    DEFAULT_MAX_DELTA,
    DEFAULT_MAX_DISTANCE,
    anchor_signatures,
    int_value,
    load_buffers,
    read_csv,
    row_key,
)
from lolg_tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_selector_probe import (
    bridge_output_hex,
    span_end,
    span_length,
    span_start,
)


DEFAULT_TARGETS = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_selector/targets.csv"
)
DEFAULT_SMALL_GAPS = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_selector/small_gaps.csv"
)
DEFAULT_FIXTURES = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_cover_second_promoted_replay/fixtures.csv"
)
DEFAULT_MANIFEST = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_OUTPUT = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_delta_producer"
)

DEFAULT_MAX_REL = 24
SLICE_STRIDES = (-3, -2, -1, 1, 2, 3)

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "target_spans",
    "target_bytes",
    "known_reference_rows",
    "target_anchor_candidates",
    "known_anchor_candidates",
    "producer_candidate_rows",
    "compact_exact_spans",
    "compact_exact_bytes",
    "compact_guarded_exact_spans",
    "compact_guarded_exact_bytes",
    "compact_rejected_spans",
    "compact_rejected_bytes",
    "compact_missing_spans",
    "compact_missing_bytes",
    "target_only_template_spans",
    "target_only_template_bytes",
    "best_target_span",
    "best_producer",
    "best_verdict",
    "next_probe",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

TARGET_FIELDNAMES = [
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "span_key",
    "span_start",
    "span_end",
    "span_length",
    "expected_hex",
    "anchor_side",
    "anchor_rel",
    "anchor_byte",
    "delta_signature",
    "best_family",
    "best_selector",
    "best_guard",
    "best_output_hex",
    "best_exact_bytes",
    "known_eval_rows",
    "known_exact_rows",
    "known_false_rows",
    "verdict",
    "promotion_candidate",
    "promotion_ready",
    "issues",
]

PRODUCER_FIELDNAMES = [
    "rank",
    "target_span",
    "family",
    "selector",
    "guard",
    "output_hex",
    "expected_hex",
    "exact_bytes",
    "known_eval_rows",
    "known_exact_rows",
    "known_false_rows",
    "known_exact_spans",
    "known_false_spans",
    "verdict",
    "sample_known_exact",
    "sample_known_false",
]

CANDIDATE_FIELDNAMES = [
    "rank",
    "scope",
    "archive",
    "span_key",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "span_start",
    "span_end",
    "span_length",
    "anchor_side",
    "anchor_rel",
    "anchor_byte",
    "delta_signature",
    "expected_hex",
]


@dataclass(frozen=True)
class ProducerSpec:
    family: str
    pool: str
    rel: int
    stride: int
    transform: str
    parameter: int = 0
    rel_b: int | None = None


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def load_segments(manifest_rows: list[dict[str, str]]) -> tuple[dict[tuple[str, str, str], bytes], list[str]]:
    segments: dict[tuple[str, str, str], bytes] = {}
    issues: list[str] = []
    for row in manifest_rows:
        key = row_key(row)
        path = row.get("segment_gap_path", "")
        if not path:
            issues.append(f"{'|'.join(key)}:missing_segment_path")
            continue
        try:
            segments[key] = Path(path).read_bytes()
        except OSError as exc:
            issues.append(f"{'|'.join(key)}:read_segment_failed:{exc}")
    return segments, issues


def signed_byte(value: int) -> int:
    return ((value + 128) & 0xFF) - 128


def transform_values(data: bytes, transform: str, parameter: int) -> bytes:
    if transform == "identity":
        return data
    if transform == "low7":
        return bytes(value & 0x7F for value in data)
    if transform == "bit_not":
        return bytes(value ^ 0xFF for value in data)
    if transform == "add_const":
        return bytes((value + parameter) & 0xFF for value in data)
    if transform == "sub_const":
        return bytes((value - parameter) & 0xFF for value in data)
    if transform == "xor_const":
        return bytes(value ^ parameter for value in data)
    raise ValueError(f"unknown value transform: {transform}")


def transform_deltas(data: bytes, transform: str) -> list[int]:
    if transform == "byte_signed":
        return [signed_byte(value) for value in data]
    if transform == "low_nibble_signed":
        return [nibble - 16 if nibble >= 8 else nibble for nibble in (value & 0x0F for value in data)]
    if transform == "high_nibble_signed":
        return [nibble - 16 if nibble >= 8 else nibble for nibble in (value >> 4 for value in data)]
    if transform == "low2_signed":
        return [((value & 0x03) - 4 if (value & 0x03) >= 2 else (value & 0x03)) for value in data]
    raise ValueError(f"unknown delta transform: {transform}")


def source_index(row: dict[str, str], segment: bytes, pool: str, rel: int) -> int | None:
    if pool == "seg_ref":
        control_ref = int_value(row, "control_ref_offset", -1)
        if control_ref < 0:
            return None
        index = control_ref + rel
    elif pool == "seg_abs":
        index = rel
    else:
        raise ValueError(f"unknown pool: {pool}")
    if index < 0 or index >= len(segment):
        return None
    return index


def source_bytes(row: dict[str, str], segment: bytes, spec: ProducerSpec, length: int) -> bytes | None:
    if spec.family.endswith("_slice") or spec.family.endswith("_delta_slice"):
        start = source_index(row, segment, spec.pool, spec.rel)
        if start is None:
            return None
        indexes = [start + offset * spec.stride for offset in range(length)]
    elif spec.family.endswith("_aba") or spec.family.endswith("_delta_aba"):
        if length != 3 or spec.rel_b is None:
            return None
        first = source_index(row, segment, spec.pool, spec.rel)
        second = source_index(row, segment, spec.pool, spec.rel_b)
        if first is None or second is None:
            return None
        indexes = [first, second, first]
    else:
        raise ValueError(f"unknown producer family: {spec.family}")
    if any(index < 0 or index >= len(segment) for index in indexes):
        return None
    return bytes(segment[index] for index in indexes)


def producer_output(row: dict[str, str], candidate: dict[str, str], segment: bytes, spec: ProducerSpec) -> bytes | None:
    length = span_length(row)
    raw = source_bytes(row, segment, spec, length)
    if raw is None:
        return None
    if spec.family.startswith("value_"):
        return transform_values(raw, spec.transform, spec.parameter)
    if spec.family.startswith("delta_"):
        anchor_hex = candidate.get("anchor_byte", "")
        if not anchor_hex:
            return None
        try:
            anchor = int(anchor_hex, 16)
        except ValueError:
            return None
        deltas = transform_deltas(raw, spec.transform)
        return bytes((anchor + delta) & 0xFF for delta in deltas)
    raise ValueError(f"unknown producer family: {spec.family}")


def transform_label(transform: str, parameter: int) -> str:
    if transform in {"identity", "low7", "bit_not", "byte_signed", "low_nibble_signed", "high_nibble_signed", "low2_signed"}:
        return transform
    return f"{transform}={parameter:02x}"


def spec_label(spec: ProducerSpec) -> str:
    if spec.family.endswith("_aba") or spec.family.endswith("_delta_aba"):
        return (
            f"{spec.pool}@{spec.rel},{spec.rel_b}:aba:"
            f"{transform_label(spec.transform, spec.parameter)}"
        )
    return (
        f"{spec.pool}@{spec.rel}:stride={spec.stride}:"
        f"{transform_label(spec.transform, spec.parameter)}"
    )


def single_constant(left: bytes, right: bytes, mode: str) -> int | None:
    constants: set[int] = set()
    for raw, expected in zip(left, right):
        if mode == "add_const":
            constants.add((expected - raw) & 0xFF)
        elif mode == "sub_const":
            constants.add((raw - expected) & 0xFF)
        elif mode == "xor_const":
            constants.add(raw ^ expected)
        else:
            raise ValueError(f"unknown constant mode: {mode}")
    if len(constants) != 1:
        return None
    return next(iter(constants))


def candidate_from_selector(row: dict[str, str], selector_row: dict[str, str], scope: str) -> dict[str, str]:
    return {
        "scope": scope,
        "archive": row.get("archive", ""),
        "archive_tag": row.get("archive_tag", ""),
        "pcx_name": row.get("pcx_name", ""),
        "frontier_id": row.get("frontier_id", ""),
        "span_key": row.get("span_key", ""),
        "span_start": str(span_start(row)),
        "span_end": str(span_end(row)),
        "span_length": str(span_length(row)),
        "expected_hex": row.get("expected_hex", ""),
        "anchor_side": selector_row.get("anchor_side", ""),
        "anchor_rel": selector_row.get("anchor_rel", ""),
        "anchor_byte": selector_row.get("anchor_byte", ""),
        "delta_signature": selector_row.get("delta_signature", ""),
    }


def candidate_from_signature(row: dict[str, str], signature: dict[str, str], scope: str) -> dict[str, str]:
    return {
        "scope": scope,
        "archive": row.get("archive", ""),
        "archive_tag": row.get("archive_tag", ""),
        "pcx_name": row.get("pcx_name", ""),
        "frontier_id": row.get("frontier_id", ""),
        "span_key": row.get("span_key", ""),
        "span_start": str(span_start(row)),
        "span_end": str(span_end(row)),
        "span_length": str(span_length(row)),
        "expected_hex": row.get("expected_hex", ""),
        "anchor_side": signature.get("anchor_side", ""),
        "anchor_rel": signature.get("anchor_rel", ""),
        "anchor_byte": signature.get("anchor_byte", ""),
        "delta_signature": signature.get("delta_signature", ""),
    }


def exact_specs_for(row: dict[str, str], candidate: dict[str, str], segment: bytes, *, max_rel: int) -> list[ProducerSpec]:
    expected = bytes.fromhex(row.get("expected_hex", ""))
    length = len(expected)
    desired_deltas = [int(part) for part in candidate.get("delta_signature", "").split(",") if part != ""]
    specs: list[ProducerSpec] = []
    seen: set[ProducerSpec] = set()

    def add_spec(spec: ProducerSpec, output: bytes | None) -> None:
        if output == expected and spec not in seen:
            specs.append(spec)
            seen.add(spec)

    for pool in ("seg_ref", "seg_abs"):
        for rel in range(-max_rel, max_rel + 1):
            for stride in SLICE_STRIDES:
                base = ProducerSpec("value_slice", pool, rel, stride, "identity")
                raw = source_bytes(row, segment, base, length)
                if raw is None:
                    continue
                for transform in ("identity", "low7", "bit_not"):
                    spec = ProducerSpec("value_slice", pool, rel, stride, transform)
                    add_spec(spec, producer_output(row, candidate, segment, spec))
                for transform in ("add_const", "sub_const", "xor_const"):
                    parameter = single_constant(raw, expected, transform)
                    if parameter is not None:
                        spec = ProducerSpec("value_slice", pool, rel, stride, transform, parameter)
                        add_spec(spec, producer_output(row, candidate, segment, spec))
                for transform in ("byte_signed", "low_nibble_signed", "high_nibble_signed", "low2_signed"):
                    try:
                        deltas = transform_deltas(raw, transform)
                    except ValueError:
                        continue
                    if deltas == desired_deltas:
                        spec = ProducerSpec("delta_slice", pool, rel, stride, transform)
                        add_spec(spec, producer_output(row, candidate, segment, spec))
        if length == 3:
            for rel_a in range(-max_rel, max_rel + 1):
                for rel_b in range(-max_rel, max_rel + 1):
                    base = ProducerSpec("value_aba", pool, rel_a, 1, "identity", rel_b=rel_b)
                    raw = source_bytes(row, segment, base, length)
                    if raw is None:
                        continue
                    for transform in ("identity", "low7", "bit_not"):
                        spec = ProducerSpec("value_aba", pool, rel_a, 1, transform, rel_b=rel_b)
                        add_spec(spec, producer_output(row, candidate, segment, spec))
                    for transform in ("add_const", "sub_const", "xor_const"):
                        parameter = single_constant(raw, expected, transform)
                        if parameter is not None:
                            spec = ProducerSpec("value_aba", pool, rel_a, 1, transform, parameter, rel_b)
                            add_spec(spec, producer_output(row, candidate, segment, spec))
                    for transform in ("byte_signed", "low_nibble_signed", "high_nibble_signed", "low2_signed"):
                        if transform_deltas(raw, transform) == desired_deltas:
                            spec = ProducerSpec("delta_aba", pool, rel_a, 1, transform, rel_b=rel_b)
                            add_spec(spec, producer_output(row, candidate, segment, spec))
    specs.sort(key=lambda spec: (spec.family, spec.pool, abs(spec.rel), abs(spec.rel_b or 0), spec.transform, spec.parameter))
    return specs


def evaluate_spec(
    spec: ProducerSpec,
    known_rows_by_span: dict[str, dict[str, str]],
    known_candidates: list[dict[str, str]],
    segments: dict[tuple[str, str, str], bytes],
) -> dict[str, object]:
    eval_rows = 0
    exact: list[str] = []
    false: list[str] = []
    for candidate in known_candidates:
        row = known_rows_by_span.get(candidate.get("span_key", ""))
        if row is None:
            continue
        segment = segments.get(row_key(row))
        if segment is None:
            continue
        output = producer_output(row, candidate, segment, spec)
        if output is None:
            continue
        eval_rows += 1
        if output == bytes.fromhex(row.get("expected_hex", "")):
            exact.append(candidate.get("span_key", ""))
        else:
            false.append(candidate.get("span_key", ""))
    return {
        "eval_rows": eval_rows,
        "exact": exact,
        "false": false,
    }


def producer_rows_for_target(
    row: dict[str, str],
    candidate: dict[str, str],
    segment: bytes,
    known_rows_by_span: dict[str, dict[str, str]],
    known_candidates: list[dict[str, str]],
    segments: dict[tuple[str, str, str], bytes],
    *,
    max_rel: int,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    expected = bytes.fromhex(row.get("expected_hex", ""))
    for spec in exact_specs_for(row, candidate, segment, max_rel=max_rel):
        output = producer_output(row, candidate, segment, spec)
        if output is None:
            continue
        evaluation = evaluate_spec(spec, known_rows_by_span, known_candidates, segments)
        known_exact = sorted(set(evaluation["exact"]))
        known_false = sorted(set(evaluation["false"]))
        if known_false:
            verdict = "rejected_known_false"
        elif known_exact:
            verdict = "guarded_exact"
        else:
            verdict = "target_only_no_known_eval"
        rows.append(
            {
                "rank": "",
                "target_span": row.get("span_key", ""),
                "family": spec.family,
                "selector": spec_label(spec),
                "guard": "compact_control",
                "output_hex": output.hex(),
                "expected_hex": expected.hex(),
                "exact_bytes": str(len(expected)),
                "known_eval_rows": str(evaluation["eval_rows"]),
                "known_exact_rows": str(len(evaluation["exact"])),
                "known_false_rows": str(len(evaluation["false"])),
                "known_exact_spans": str(len(known_exact)),
                "known_false_spans": str(len(known_false)),
                "verdict": verdict,
                "sample_known_exact": ";".join(known_exact[:8]),
                "sample_known_false": ";".join(known_false[:8]),
            }
        )
    template_output = bridge_output_hex(candidate.get("anchor_byte", ""), candidate.get("delta_signature", ""))
    rows.append(
        {
            "rank": "",
            "target_span": row.get("span_key", ""),
            "family": "anchor_delta_template",
            "selector": f"anchor={candidate.get('anchor_byte', '')}:delta={candidate.get('delta_signature', '')}",
            "guard": "target_signature_only",
            "output_hex": template_output,
            "expected_hex": expected.hex(),
            "exact_bytes": str(len(expected) if template_output == expected.hex() else 0),
            "known_eval_rows": "0",
            "known_exact_rows": "0",
            "known_false_rows": "0",
            "known_exact_spans": "0",
            "known_false_spans": "0",
            "verdict": "target_only_delta_template",
            "sample_known_exact": "",
            "sample_known_false": "",
        }
    )
    return rows


def unique_target_bytes(rows: list[dict[str, str]], verdicts: set[str] | None = None) -> int:
    seen: set[str] = set()
    total = 0
    for row in rows:
        if verdicts is not None and row.get("verdict") not in verdicts:
            continue
        span_key = row.get("target_span", row.get("span_key", ""))
        if span_key in seen:
            continue
        seen.add(span_key)
        total += int_value(row, "exact_bytes", int_value(row, "span_length"))
    return total


def build(
    selector_target_rows: list[dict[str, str]],
    small_gap_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    manifest_rows: list[dict[str, str]],
    *,
    max_distance: int,
    max_delta: int,
    max_rel: int,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    buffers, buffer_issues = load_buffers(fixture_rows)
    segments, segment_issues = load_segments(manifest_rows)
    small_by_span = {row.get("span_key", ""): row for row in small_gap_rows}
    target_selector_rows = [
        row
        for row in selector_target_rows
        if row.get("frontier_id") == "80" and row.get("selector_verdict") == "target_only_unique"
    ]
    target_rows = [small_by_span[row.get("span_key", "")] for row in target_selector_rows if row.get("span_key", "") in small_by_span]
    target_selector_by_span = {row.get("span_key", ""): row for row in target_selector_rows}
    target_candidates = [
        candidate_from_selector(row, target_selector_by_span[row.get("span_key", "")], "target") for row in target_rows
    ]

    known_rows = [row for row in small_gap_rows if row.get("known_in_replay") == "1"]
    known_rows_by_span = {row.get("span_key", ""): row for row in known_rows}
    known_candidates: list[dict[str, str]] = []
    for row in known_rows:
        buffer = buffers.get(row_key(row))
        if buffer is None:
            continue
        decoded, known_mask = buffer
        for signature in anchor_signatures(row, decoded, known_mask, max_distance=max_distance, max_delta=max_delta):
            known_candidates.append(candidate_from_signature(row, signature, "known"))

    all_producer_rows: list[dict[str, str]] = []
    target_output_rows: list[dict[str, str]] = []
    target_issues: list[str] = []
    producers_by_span: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row, candidate in zip(target_rows, target_candidates, strict=True):
        segment = segments.get(row_key(row))
        if segment is None:
            target_issues.append(f"{row.get('span_key', '')}:missing_segment")
            continue
        producer_rows = producer_rows_for_target(
            row,
            candidate,
            segment,
            known_rows_by_span,
            known_candidates,
            segments,
            max_rel=max_rel,
        )
        producers_by_span[row.get("span_key", "")].extend(producer_rows)
        all_producer_rows.extend(producer_rows)

    all_producer_rows.sort(
        key=lambda row: (
            row.get("target_span", ""),
            row.get("verdict") == "target_only_delta_template",
            row.get("verdict") == "rejected_known_false",
            -int_value(row, "exact_bytes"),
            int_value(row, "known_false_rows"),
            -int_value(row, "known_exact_rows"),
            row.get("family", ""),
            row.get("selector", ""),
        )
    )
    for index, row in enumerate(all_producer_rows, start=1):
        row["rank"] = str(index)

    for index, (row, candidate) in enumerate(zip(target_rows, target_candidates, strict=True), start=1):
        rows = producers_by_span.get(row.get("span_key", ""), [])
        compact_rows = [producer for producer in rows if producer.get("guard") == "compact_control"]
        best = max(
            rows,
            key=lambda producer: (
                producer.get("verdict") == "guarded_exact",
                producer.get("guard") == "compact_control",
                producer.get("verdict") != "target_only_delta_template",
                -int_value(producer, "known_false_rows"),
                int_value(producer, "known_exact_rows"),
                int_value(producer, "exact_bytes"),
            ),
            default={},
        )
        issues = ""
        if not compact_rows:
            issues = "missing_compact_control_producer"
        elif best.get("verdict") == "rejected_known_false":
            issues = "compact_control_known_false"
        target_output_rows.append(
            {
                "rank": str(index),
                "archive": row.get("archive", ""),
                "archive_tag": row.get("archive_tag", ""),
                "pcx_name": row.get("pcx_name", ""),
                "frontier_id": row.get("frontier_id", ""),
                "span_key": row.get("span_key", ""),
                "span_start": str(span_start(row)),
                "span_end": str(span_end(row)),
                "span_length": str(span_length(row)),
                "expected_hex": row.get("expected_hex", ""),
                "anchor_side": candidate.get("anchor_side", ""),
                "anchor_rel": candidate.get("anchor_rel", ""),
                "anchor_byte": candidate.get("anchor_byte", ""),
                "delta_signature": candidate.get("delta_signature", ""),
                "best_family": best.get("family", ""),
                "best_selector": best.get("selector", ""),
                "best_guard": best.get("guard", ""),
                "best_output_hex": best.get("output_hex", ""),
                "best_exact_bytes": best.get("exact_bytes", "0"),
                "known_eval_rows": best.get("known_eval_rows", "0"),
                "known_exact_rows": best.get("known_exact_rows", "0"),
                "known_false_rows": best.get("known_false_rows", "0"),
                "verdict": best.get("verdict", "missing_producer"),
                "promotion_candidate": "1" if best.get("verdict") == "guarded_exact" else "0",
                "promotion_ready": "1" if best.get("verdict") == "guarded_exact" else "0",
                "issues": issues,
            }
        )

    compact_rows = [row for row in all_producer_rows if row.get("guard") == "compact_control"]
    compact_exact_spans = {row.get("target_span", "") for row in compact_rows if int_value(row, "exact_bytes") > 0}
    compact_guarded_spans = {row.get("target_span", "") for row in compact_rows if row.get("verdict") == "guarded_exact"}
    compact_rejected_spans = {row.get("target_span", "") for row in compact_rows if row.get("verdict") == "rejected_known_false"}
    compact_missing_rows = [row for row in target_output_rows if row.get("issues") == "missing_compact_control_producer"]
    compact_missing_bytes = sum(int_value(row, "span_length") for row in compact_missing_rows)
    target_only_template_spans = {
        row.get("target_span", "") for row in all_producer_rows if row.get("verdict") == "target_only_delta_template"
    }
    target_only_template_bytes = sum(
        span_length(row) for row in target_rows if row.get("span_key", "") in target_only_template_spans
    )
    target_bytes = sum(span_length(row) for row in target_rows)
    best_target = max(
        target_output_rows,
        key=lambda row: (
            row.get("promotion_ready") == "1",
            row.get("verdict") == "rejected_known_false",
            row.get("issues") == "missing_compact_control_producer",
            int_value(row, "span_length"),
        ),
        default={},
    )
    promotion_ready_bytes = sum(int_value(row, "span_length") for row in target_output_rows if row.get("promotion_ready") == "1")
    summary = {
        "scope": "total",
        "candidate_mode": "external_terminal_spatial_bridge_delta_producer_probe",
        "target_spans": str(len(target_rows)),
        "target_bytes": str(target_bytes),
        "known_reference_rows": str(len(known_rows)),
        "target_anchor_candidates": str(len(target_candidates)),
        "known_anchor_candidates": str(len(known_candidates)),
        "producer_candidate_rows": str(len(all_producer_rows)),
        "compact_exact_spans": str(len(compact_exact_spans)),
        "compact_exact_bytes": str(
            sum(span_length(row) for row in target_rows if row.get("span_key", "") in compact_exact_spans)
        ),
        "compact_guarded_exact_spans": str(len(compact_guarded_spans)),
        "compact_guarded_exact_bytes": str(
            sum(span_length(row) for row in target_rows if row.get("span_key", "") in compact_guarded_spans)
        ),
        "compact_rejected_spans": str(len(compact_rejected_spans)),
        "compact_rejected_bytes": str(
            sum(span_length(row) for row in target_rows if row.get("span_key", "") in compact_rejected_spans)
        ),
        "compact_missing_spans": str(len(compact_missing_rows)),
        "compact_missing_bytes": str(compact_missing_bytes),
        "target_only_template_spans": str(len(target_only_template_spans)),
        "target_only_template_bytes": str(target_only_template_bytes),
        "best_target_span": best_target.get("span_key", ""),
        "best_producer": best_target.get("best_selector", ""),
        "best_verdict": best_target.get("verdict", ""),
        "next_probe": (
            "expand compact/control producer for frontier 80 five-byte bridge"
            if compact_missing_bytes > 0
            else (
                "split compact/control bridge producers with non-oracle guards"
                if compact_rejected_spans
                else "promote guarded compact/control bridge producers"
                if promotion_ready_bytes > 0
                else "review target-only frontier 80 delta templates"
            )
        ),
        "promotion_candidate_bytes": str(promotion_ready_bytes),
        "promotion_ready_bytes": str(promotion_ready_bytes),
        "issue_rows": str(len(buffer_issues) + len(segment_issues) + len(target_issues)),
    }

    candidate_rows = known_candidates + target_candidates
    candidate_rows.sort(
        key=lambda row: (
            row.get("scope", ""),
            row.get("span_key", ""),
            int_value(row, "span_start"),
            int_value(row, "anchor_rel", 9999),
        )
    )
    for index, row in enumerate(candidate_rows, start=1):
        row["rank"] = str(index)
    return summary, target_output_rows, all_producer_rows, candidate_rows


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 240) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    target_rows: list[dict[str, str]],
    producer_rows: list[dict[str, str]],
    candidate_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "targets": target_rows,
        "producers": producer_rows,
        "candidates": candidate_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("targets.csv", output_dir / "targets.csv"),
            ("producers.csv", output_dir / "producers.csv"),
            ("candidates.csv", output_dir / "candidates.csv"),
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
  --bg: #101417;
  --panel: #171f22;
  --line: #31424a;
  --text: #edf5f4;
  --muted: #9dafb5;
  --accent: #77d3b1;
  --warn: #f0b36c;
}}
body {{ margin: 0; background: var(--bg); color: var(--text); font: 14px/1.45 system-ui, sans-serif; }}
main {{ width: min(1680px, calc(100vw - 28px)); margin: 0 auto; padding: 22px 0 32px; display: grid; gap: 16px; }}
h1 {{ margin: 0; font-size: 22px; }}
h2 {{ margin: 0 0 10px; font-size: 16px; }}
.muted {{ color: var(--muted); }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 10px; }}
.stat, .panel {{ border: 1px solid var(--line); border-radius: 8px; background: var(--panel); padding: 10px; }}
.value {{ font-size: 22px; font-weight: 760; color: var(--accent); }}
.warn {{ color: var(--warn); }}
.panel {{ overflow-x: auto; }}
table {{ width: 100%; min-width: 1420px; border-collapse: collapse; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
code {{ color: var(--accent); }}
</style>
</head>
<body>
<main>
  <header>
    <h1>{html.escape(title)}</h1>
    <div class="muted">Tests compact/control slices and motifs as producers for target-only frontier 80 spatial bridge values.</div>
  </header>
  <section class="stats">
    <div class="stat"><div class="muted">Target bytes</div><div class="value">{summary['target_bytes']}</div></div>
    <div class="stat"><div class="muted">Compact exact</div><div class="value warn">{summary['compact_exact_bytes']}</div></div>
    <div class="stat"><div class="muted">Compact missing</div><div class="value warn">{summary['compact_missing_bytes']}</div></div>
    <div class="stat"><div class="muted">Rejected compact</div><div class="value warn">{summary['compact_rejected_bytes']}</div></div>
    <div class="stat"><div class="muted">Promotion-ready</div><div class="value warn">{summary['promotion_ready_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2>{links}</section>
  <section class="panel">
    <h2>Next</h2>
    <p><code>{html.escape(summary['next_probe'])}</code></p>
    <p class="muted">Best producer: <code>{html.escape(summary['best_target_span'])}</code> / <code>{html.escape(summary['best_producer'])}</code>.</p>
  </section>
  <section class="panel"><h2>Targets</h2>{render_table(target_rows, TARGET_FIELDNAMES)}</section>
  <section class="panel"><h2>Producers</h2>{render_table(producer_rows, PRODUCER_FIELDNAMES)}</section>
  <section class="panel"><h2>Candidates</h2>{render_table(candidate_rows, CANDIDATE_FIELDNAMES)}</section>
  <script type="application/json" id="external-terminal-spatial-bridge-delta-producer-data">{html.escape(data_json)}</script>
</main>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe compact/control producers for frontier 80 spatial bridge deltas.")
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("--small-gaps", type=Path, default=DEFAULT_SMALL_GAPS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--max-distance", type=int, default=DEFAULT_MAX_DISTANCE)
    parser.add_argument("--max-delta", type=int, default=DEFAULT_MAX_DELTA)
    parser.add_argument("--max-rel", type=int, default=DEFAULT_MAX_REL)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex External Terminal Spatial Bridge Delta Producer Probe",
    )
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    summary, target_rows, producer_rows, candidate_rows = build(
        read_csv(args.targets),
        read_csv(args.small_gaps),
        read_csv(args.fixtures),
        read_rows(args.manifest),
        max_distance=args.max_distance,
        max_delta=args.max_delta,
        max_rel=args.max_rel,
    )
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, target_rows)
    write_csv(args.output / "producers.csv", PRODUCER_FIELDNAMES, producer_rows)
    write_csv(args.output / "candidates.csv", CANDIDATE_FIELDNAMES, candidate_rows)
    (args.output / "index.html").write_text(
        build_html(summary, target_rows, producer_rows, candidate_rows, args.output, args.title),
        encoding="utf-8",
    )
    print(
        "External terminal spatial bridge delta producer probe: "
        f"compact_exact={summary['compact_exact_bytes']}/{summary['target_bytes']} "
        f"compact_guarded={summary['compact_guarded_exact_bytes']} "
        f"compact_missing={summary['compact_missing_bytes']} "
        f"promotion_ready={summary['promotion_ready_bytes']} "
        f"issues={summary['issue_rows']}"
    )
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
