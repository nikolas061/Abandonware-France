#!/usr/bin/env python3
"""Probe control/opcode contexts for high-safe gradient residual slots."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gradient_payload_state_opcode_probe import parse_window_signature
from lolg_tex_gradient_sequence_high_safe_source_window_probe import (
    SLOT_FIELDNAMES as SOURCE_WINDOW_SLOT_FIELDNAMES,
)
from lolg_tex_micro_mixed_value_payload_state_opcode_probe import (
    band_token,
    byte_at,
    cyclic_byte,
    delta_bucket,
    evaluate_candidate,
    fixture_key,
    hex_value,
    high_value,
    int_value,
    load_sources,
    low_value,
    ratio,
    source_class,
    target_value,
    write_csv,
)


DEFAULT_SLOTS = Path("output/tex_gradient_sequence_high_safe_source_window/slots.csv")
DEFAULT_TARGET_ROWS = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_probe/targets.csv")
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_OUTPUT = Path("output/tex_gradient_sequence_high_safe_control_opcode")

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "slots",
    "slot_rows",
    "joined_target_rows",
    "entry_slots",
    "context_families",
    "candidate_rows",
    "control_anchor_rows",
    "start_anchor_rows",
    "control_slot_bytes",
    "start_slot_bytes",
    "control_raw_exact_slots",
    "start_raw_exact_slots",
    "control_low_exact_slots",
    "start_low_exact_slots",
    "prefix_low_exact_slots",
    "fragment_low_exact_slots",
    "best_low_context",
    "best_low_correct_slots",
    "best_low_false_slots",
    "best_low_precision",
    "best_low_coverage",
    "best_byte_context",
    "best_byte_correct_slots",
    "best_byte_false_slots",
    "best_byte_precision",
    "best_byte_coverage",
    "best_high_context",
    "best_high_correct_slots",
    "best_high_false_slots",
    "best_high_precision",
    "best_high_coverage",
    "best_low_false_free_context",
    "best_low_false_free_slots",
    "best_byte_false_free_context",
    "best_byte_false_free_slots",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

CANDIDATE_FIELDNAMES = [
    "rank",
    "target_kind",
    "context_family",
    "contexts",
    "deterministic_repeated_slots",
    "deterministic_singleton_slots",
    "conflicted_slots",
    "loo_correct_slots",
    "loo_false_slots",
    "loo_unknown_slots",
    "loo_precision",
    "loo_coverage",
    "baseline_value",
    "baseline_correct_slots",
    "baseline_precision",
    "predicted_values",
    "verdict",
    "sample_context",
    "sample_prediction",
]

CONTEXT_FIELDNAMES = [
    "rank",
    "target_kind",
    "context_family",
    "context_key",
    "slots",
    "rows",
    "target_values",
    "dominant_value",
    "dominant_ratio",
    "sample_pcx",
    "sample_frontier_id",
    "verdict",
]

SLOT_FIELDNAMES = [
    *SOURCE_WINDOW_SLOT_FIELDNAMES,
    "span_index",
    "run_index",
    "op_index",
    "control_ref_offset",
    "control_ref_mod64",
    "start_anchor",
    "control_byte",
    "control_low",
    "control_class",
    "control_delta",
    "start_byte",
    "start_low",
    "start_class",
    "start_delta",
    "prefix_byte",
    "prefix_low",
    "fragment_byte",
    "fragment_low",
    "window_head_byte",
    "window_tail_byte",
    "opcode_state_key",
    "best_low_opcode_context",
    "best_low_opcode_prediction",
    "best_low_opcode_verdict",
    "best_byte_opcode_context",
    "best_byte_opcode_prediction",
    "best_byte_opcode_verdict",
    "issues",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def parse_hex(text: object) -> int | None:
    value = str(text)
    if not value or value in {"unk", "none", "NA"}:
        return None
    try:
        return int(value, 16)
    except ValueError:
        return None


def target_key(row: dict[str, object]) -> tuple[str, str, str, str, str]:
    return (
        str(row.get("archive", "")),
        str(row.get("pcx_name", "")),
        str(row.get("frontier_id", "")),
        str(row.get("start", "")),
        str(row.get("end", "")),
    )


def band(value: int, step: int) -> str:
    base = (value // step) * step
    return f"{base}-{base + step - 1}"


def state_band(value: object, step: int) -> str:
    parsed = int_value({"value": value}, "value", -1)
    return "NA" if parsed < 0 else band(parsed, step)


def control_start_anchor(target: dict[str, str]) -> int:
    control_ref_offset = int_value(target, "control_ref_offset", -1)
    control_ref_mod64 = int_value(target, "control_ref_mod64", -1)
    start_mod64 = int_value(target, "start_mod64", -1)
    if control_ref_offset < 0 or control_ref_mod64 < 0 or start_mod64 < 0:
        return -1
    return control_ref_offset - control_ref_mod64 + start_mod64


def context_functions():
    return {
        "opcode_pos16": lambda row: (row["op_index_band8"], row["payload_pos16"]),
        "span_pos16": lambda row: (row["span_index_band4"], row["payload_pos16"]),
        "span_opcode_pos16": lambda row: (
            row["span_index_band4"],
            row["op_index_band8"],
            row["payload_pos16"],
        ),
        "gradient_opcode_pos16": lambda row: (
            row["gradient_class"],
            row["top_nibble"],
            row["op_index_band8"],
            row["payload_pos16"],
        ),
        "delta_opcode_pos16": lambda row: (
            row["dominant_delta"],
            row["op_index_band8"],
            row["payload_pos16"],
        ),
        "control_ref_pos16": lambda row: (row["control_ref_mod64"], row["payload_pos16"]),
        "control_byte_pos16": lambda row: (row["control_byte"], row["payload_pos16"]),
        "control_low_pos16": lambda row: (row["control_low"], row["payload_pos16"]),
        "control_high_pos16": lambda row: (row["control_high"], row["payload_pos16"]),
        "control_class_pos16": lambda row: (row["control_class"], row["payload_pos16"]),
        "control_delta_pos16": lambda row: (row["control_delta"], row["payload_pos16"]),
        "start_byte_pos16": lambda row: (row["start_byte"], row["payload_pos16"]),
        "start_low_pos16": lambda row: (row["start_low"], row["payload_pos16"]),
        "start_class_pos16": lambda row: (row["start_class"], row["payload_pos16"]),
        "start_delta_pos16": lambda row: (row["start_delta"], row["payload_pos16"]),
        "control_class_opcode": lambda row: (
            row["control_class"],
            row["op_index_band8"],
            row["rel_mod16"],
        ),
        "control_delta_opcode": lambda row: (
            row["control_delta"],
            row["op_index_band8"],
            row["rel_mod16"],
        ),
        "start_class_opcode": lambda row: (
            row["start_class"],
            row["op_index_band8"],
            row["rel_mod16"],
        ),
        "prefix_byte_opcode": lambda row: (
            row["prefix_byte"],
            row["op_index_band8"],
            row["rel_mod16"],
        ),
        "prefix_low_opcode": lambda row: (
            row["prefix_low"],
            row["op_index_band8"],
            row["rel_mod16"],
        ),
        "fragment_byte_opcode": lambda row: (
            row["fragment_byte"],
            row["op_index_band8"],
            row["rel_mod16"],
        ),
        "fragment_low_opcode": lambda row: (
            row["fragment_low"],
            row["op_index_band8"],
            row["rel_mod16"],
        ),
        "window_head_opcode": lambda row: (
            row["window_head_byte"],
            row["op_index_band8"],
            row["rel_mod16"],
        ),
        "window_tail_opcode": lambda row: (
            row["window_tail_byte"],
            row["op_index_band8"],
            row["rel_mod16"],
        ),
        "predicted_high_opcode": lambda row: (
            row["predicted_high"],
            row["op_index_band8"],
            row["rel_mod16"],
        ),
        "shape_opcode_target_x": lambda row: (
            row["shape_len_key"],
            row["op_index_band8"],
            row["target_x_mod32"],
        ),
        "control_prefix_mix": lambda row: (
            row["control_high"],
            row["prefix_high"],
            row["op_index_band8"],
            row["target_x_mod32"],
        ),
        "state_source_mix": lambda row: (
            row["pool"],
            row["offset_delta_bucket"],
            row["op_index_band8"],
            row["target_x_mod32"],
        ),
    }


def strict_prediction(counter: Counter[str]) -> str | None:
    values = [value for value, count in counter.items() if count > 0]
    return values[0] if len(values) == 1 else None


def best_candidate(rows: list[dict[str, object]], target_kind: str) -> dict[str, object]:
    candidates = [
        row
        for row in rows
        if row.get("target_kind") == target_kind
        and int_value(row, "loo_correct_slots") + int_value(row, "loo_false_slots") > 0
    ]
    return max(
        candidates,
        key=lambda row: (
            int_value(row, "loo_correct_slots"),
            -int_value(row, "loo_false_slots"),
            float(row.get("loo_precision", "0") or 0),
            float(row.get("loo_coverage", "0") or 0),
            str(row.get("context_family", "")),
        ),
        default={},
    )


def best_false_free_candidate(rows: list[dict[str, object]], target_kind: str) -> dict[str, object]:
    candidates = [
        row
        for row in rows
        if row.get("target_kind") == target_kind
        and int_value(row, "loo_correct_slots") > 0
        and int_value(row, "loo_false_slots") == 0
    ]
    return max(
        candidates,
        key=lambda row: (
            int_value(row, "loo_correct_slots"),
            -int_value(row, "loo_unknown_slots"),
            str(row.get("context_family", "")),
        ),
        default={},
    )


def evaluate_candidates(entries: list[dict[str, object]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for target_kind in ("byte", "high", "low", "band"):
        for context_family, context_func in context_functions().items():
            rows.append(evaluate_candidate(entries, target_kind, context_family, context_func))
    rows.sort(
        key=lambda row: (
            str(row["target_kind"]),
            -int_value(row, "loo_correct_slots"),
            int_value(row, "loo_false_slots"),
            str(row["context_family"]),
        )
    )
    for index, row in enumerate(rows, start=1):
        row["rank"] = index
    return rows


def loo_predictions(
    entries: list[dict[str, object]],
    target_kind: str,
    context_family: str,
) -> dict[str, str]:
    if not context_family:
        return {}
    context_func = context_functions()[context_family]
    all_counts: dict[tuple[object, ...], Counter[str]] = defaultdict(Counter)
    row_counts: dict[tuple[int, tuple[object, ...]], Counter[str]] = defaultdict(Counter)
    entry_by_slot: dict[str, dict[str, object]] = {}
    for entry in entries:
        context = context_func(entry)
        all_counts[context][target_value(entry, target_kind)] += 1
        row_counts[(int(entry["row_index"]), context)][target_value(entry, target_kind)] += 1
        entry_by_slot[str(entry["slot_rank"])] = entry

    output: dict[str, str] = {}
    for slot_rank, entry in entry_by_slot.items():
        context = context_func(entry)
        train_counts = all_counts[context].copy()
        train_counts.subtract(row_counts[(int(entry["row_index"]), context)])
        train_counts += Counter()
        prediction = strict_prediction(train_counts)
        if prediction is not None:
            output[slot_rank] = prediction
    return output


def build_context_rows(
    entries: list[dict[str, object]],
    candidates: list[dict[str, object]],
) -> list[dict[str, object]]:
    families_by_target: dict[str, set[str]] = defaultdict(set)
    for target_kind in ("byte", "low", "high"):
        ranked = [
            row
            for row in candidates
            if row.get("target_kind") == target_kind
            and int_value(row, "loo_correct_slots") + int_value(row, "loo_false_slots") > 0
        ]
        ranked.sort(
            key=lambda row: (
                int_value(row, "loo_correct_slots"),
                -int_value(row, "loo_false_slots"),
                str(row.get("context_family", "")),
            ),
            reverse=True,
        )
        for row in ranked[:4]:
            families_by_target[target_kind].add(str(row.get("context_family", "")))

    functions = context_functions()
    output: list[dict[str, object]] = []
    for target_kind, families in families_by_target.items():
        for family in sorted(families):
            context_func = functions[family]
            grouped: dict[tuple[object, ...], list[dict[str, object]]] = defaultdict(list)
            for entry in entries:
                grouped[context_func(entry)].append(entry)
            for context, group in grouped.items():
                if len(group) < 2:
                    continue
                values = Counter(target_value(entry, target_kind) for entry in group)
                dominant_value, dominant_count = values.most_common(1)[0]
                output.append(
                    {
                        "rank": 0,
                        "target_kind": target_kind,
                        "context_family": family,
                        "context_key": "|".join(str(part) for part in context),
                        "slots": len(group),
                        "rows": len({int(entry["row_index"]) for entry in group}),
                        "target_values": "|".join(
                            f"{value}:{count}" for value, count in values.most_common(10)
                        ),
                        "dominant_value": dominant_value,
                        "dominant_ratio": ratio(dominant_count, len(group)),
                        "sample_pcx": group[0].get("pcx_name", ""),
                        "sample_frontier_id": group[0].get("frontier_id", ""),
                        "verdict": "deterministic_context" if len(values) == 1 else "conflicted_context",
                    }
                )
    output.sort(
        key=lambda row: (
            str(row["target_kind"]),
            str(row["context_family"]),
            -int_value(row, "slots"),
            str(row["context_key"]),
        )
    )
    for index, row in enumerate(output, start=1):
        row["rank"] = index
    return output


def build_entries(
    slot_rows: list[dict[str, str]],
    target_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[str]]:
    target_by_key = {target_key(row): row for row in target_rows}
    sources_by_fixture, fixture_issues = load_sources(fixture_rows)
    row_indexes = {row_id: index for index, row_id in enumerate(sorted({row.get("row_id", "") for row in slot_rows}))}
    rows: list[dict[str, object]] = []
    entries: list[dict[str, object]] = []
    issues = list(fixture_issues)

    for slot in slot_rows:
        target = target_by_key.get(target_key(slot), {})
        local_issues = []
        if not target:
            local_issues.append("missing_gradient_target_join")

        sources = sources_by_fixture.get(fixture_key(slot), {})
        expected = sources.get("expected", b"")
        segment = sources.get("segment_gap", b"")
        control_prefix = sources.get("control_prefix", b"")
        fragment = sources.get("fragment", b"")
        target_byte = parse_hex(slot.get("target_byte", ""))
        if target_byte is None:
            local_issues.append("missing_target_byte")

        target_offset = int_value(slot, "target_offset", -1)
        if target_byte is not None and expected and byte_at(expected, target_offset) != target_byte:
            local_issues.append("expected_target_mismatch")

        relative_offset = int_value(slot, "relative_offset", -1)
        length = int_value(target, "length", int_value(slot, "end") - int_value(slot, "start"))
        control_ref_offset = int_value(target, "control_ref_offset", -1)
        control_ref_mod64 = int_value(target, "control_ref_mod64", -1)
        start_anchor = control_start_anchor(target)
        control_index = control_ref_offset + relative_offset if control_ref_offset >= 0 else -1
        start_index = start_anchor + relative_offset if start_anchor >= 0 else -1

        control_byte = byte_at(segment, control_index)
        control_previous = byte_at(segment, control_index - 1)
        start_byte = byte_at(segment, start_index)
        start_previous = byte_at(segment, start_index - 1)
        prefix_byte = cyclic_byte(control_prefix, relative_offset)
        fragment_byte = cyclic_byte(fragment, relative_offset)
        window_head, window_tail = parse_window_signature(target.get("control_window_signature", ""))
        window_head_byte = cyclic_byte(window_head, relative_offset)
        window_tail_byte = cyclic_byte(window_tail, relative_offset)

        if control_ref_offset < 0:
            local_issues.append("missing_control_ref_offset")

        row_index = row_indexes.get(slot.get("row_id", ""), 0)
        high = (target_byte >> 4) if target_byte is not None else parse_hex(slot.get("target_high", ""))
        low = (target_byte & 0x0F) if target_byte is not None else parse_hex(slot.get("target_low", ""))
        entry = {
            "row_index": row_index,
            "slot_rank": slot.get("rank", ""),
            "archive": slot.get("archive", ""),
            "pcx_name": slot.get("pcx_name", ""),
            "frontier_id": slot.get("frontier_id", ""),
            "relative_offset": relative_offset,
            "length": length,
            "byte": "" if target_byte is None else f"{target_byte:02x}",
            "high": "" if high is None else f"{high:x}",
            "low": "" if low is None else f"{low:x}",
            "band": "NA" if target_byte is None else band_token(target_byte),
            "payload_pos16": str((relative_offset * 16) // length) if length > 0 and relative_offset >= 0 else "NA",
            "rel_mod4": slot.get("rel_mod4", ""),
            "rel_mod8": slot.get("rel_mod8", ""),
            "rel_mod16": slot.get("rel_mod16", ""),
            "target_x_mod32": slot.get("target_x_mod32", ""),
            "shape_len_key": slot.get("shape_len_key", ""),
            "pool": slot.get("pool", ""),
            "offset_delta_bucket": slot.get("offset_delta_bucket", ""),
            "predicted_high": slot.get("predicted_high", ""),
            "gradient_class": slot.get("gradient_class", ""),
            "top_nibble": slot.get("top_nibble", ""),
            "span_index": target.get("span_index", ""),
            "run_index": target.get("run_index", ""),
            "op_index": target.get("op_index", ""),
            "span_index_band4": state_band(target.get("span_index", ""), 4),
            "op_index_band8": state_band(target.get("op_index", ""), 8),
            "length_band8": state_band(length, 8),
            "start_mod64": target.get("start_mod64", ""),
            "control_ref_mod64": "" if control_ref_mod64 < 0 else str(control_ref_mod64),
            "dominant_delta": target.get("dominant_delta", ""),
            "control_byte": hex_value(control_byte),
            "control_high": high_value(control_byte),
            "control_low": low_value(control_byte),
            "control_class": source_class(control_byte),
            "control_delta": delta_bucket(control_previous, control_byte),
            "start_byte": hex_value(start_byte),
            "start_high": high_value(start_byte),
            "start_low": low_value(start_byte),
            "start_class": source_class(start_byte),
            "start_delta": delta_bucket(start_previous, start_byte),
            "prefix_byte": hex_value(prefix_byte),
            "prefix_high": high_value(prefix_byte),
            "prefix_low": low_value(prefix_byte),
            "prefix_class": source_class(prefix_byte),
            "fragment_byte": hex_value(fragment_byte),
            "fragment_high": high_value(fragment_byte),
            "fragment_low": low_value(fragment_byte),
            "fragment_class": source_class(fragment_byte),
            "window_head_byte": hex_value(window_head_byte),
            "window_tail_byte": hex_value(window_tail_byte),
        }
        entries.append(entry)

        row = {
            **slot,
            "span_index": target.get("span_index", ""),
            "run_index": target.get("run_index", ""),
            "op_index": target.get("op_index", ""),
            "control_ref_offset": "" if control_ref_offset < 0 else control_ref_offset,
            "control_ref_mod64": "" if control_ref_mod64 < 0 else control_ref_mod64,
            "start_anchor": "" if start_anchor < 0 else start_anchor,
            "control_byte": entry["control_byte"],
            "control_low": entry["control_low"],
            "control_class": entry["control_class"],
            "control_delta": entry["control_delta"],
            "start_byte": entry["start_byte"],
            "start_low": entry["start_low"],
            "start_class": entry["start_class"],
            "start_delta": entry["start_delta"],
            "prefix_byte": entry["prefix_byte"],
            "prefix_low": entry["prefix_low"],
            "fragment_byte": entry["fragment_byte"],
            "fragment_low": entry["fragment_low"],
            "window_head_byte": entry["window_head_byte"],
            "window_tail_byte": entry["window_tail_byte"],
            "opcode_state_key": (
                f"span={entry['span_index_band4']}|op={entry['op_index_band8']}|"
                f"delta={entry['dominant_delta']}"
            ),
            "issues": ";".join(local_issues),
        }
        rows.append(row)

    return rows, entries, issues


def annotate_rows(
    rows: list[dict[str, object]],
    entries: list[dict[str, object]],
    best_low: dict[str, object],
    best_byte: dict[str, object],
) -> list[dict[str, object]]:
    low_context = str(best_low.get("context_family", ""))
    byte_context = str(best_byte.get("context_family", ""))
    low_predictions = loo_predictions(entries, "low", low_context)
    byte_predictions = loo_predictions(entries, "byte", byte_context)
    output: list[dict[str, object]] = []
    for row in rows:
        annotated = dict(row)
        slot_rank = str(row.get("rank", ""))
        low_prediction = low_predictions.get(slot_rank, "")
        byte_prediction = byte_predictions.get(slot_rank, "")
        target_low = str(row.get("target_low", ""))
        target_byte = str(row.get("target_byte", ""))
        annotated.update(
            {
                "best_low_opcode_context": low_context,
                "best_low_opcode_prediction": low_prediction,
                "best_low_opcode_verdict": (
                    "unknown"
                    if not low_prediction
                    else "correct"
                    if low_prediction == target_low
                    else "false"
                ),
                "best_byte_opcode_context": byte_context,
                "best_byte_opcode_prediction": byte_prediction,
                "best_byte_opcode_verdict": (
                    "unknown"
                    if not byte_prediction
                    else "correct"
                    if byte_prediction == target_byte
                    else "false"
                ),
            }
        )
        output.append(annotated)
    return output


def build_summary(
    rows: list[dict[str, object]],
    entries: list[dict[str, object]],
    candidates: list[dict[str, object]],
    issues: list[str],
) -> dict[str, object]:
    best_low = best_candidate(candidates, "low")
    best_byte = best_candidate(candidates, "byte")
    best_high = best_candidate(candidates, "high")
    best_low_false_free = best_false_free_candidate(candidates, "low")
    best_byte_false_free = best_false_free_candidate(candidates, "byte")
    low_candidate_bytes = max(
        int_value(best_low_false_free, "loo_correct_slots"),
        int_value(best_byte_false_free, "loo_correct_slots"),
    )
    return {
        "scope": "total",
        "candidate_mode": "control_opcode_loo_context",
        "slots": len(rows),
        "slot_rows": len({row.get("row_id", "") for row in rows}),
        "joined_target_rows": len({target_key(row) for row in rows}),
        "entry_slots": len(entries),
        "context_families": len(context_functions()),
        "candidate_rows": len(candidates),
        "control_anchor_rows": len({row.get("row_id", "") for row in rows if row.get("control_ref_offset") != ""}),
        "start_anchor_rows": len({row.get("row_id", "") for row in rows if row.get("start_anchor") != ""}),
        "control_slot_bytes": sum(1 for entry in entries if entry.get("control_byte") != "NA"),
        "start_slot_bytes": sum(1 for entry in entries if entry.get("start_byte") != "NA"),
        "control_raw_exact_slots": sum(1 for entry in entries if entry.get("control_byte") == entry.get("byte")),
        "start_raw_exact_slots": sum(1 for entry in entries if entry.get("start_byte") == entry.get("byte")),
        "control_low_exact_slots": sum(1 for entry in entries if entry.get("control_low") == entry.get("low")),
        "start_low_exact_slots": sum(1 for entry in entries if entry.get("start_low") == entry.get("low")),
        "prefix_low_exact_slots": sum(1 for entry in entries if entry.get("prefix_low") == entry.get("low")),
        "fragment_low_exact_slots": sum(1 for entry in entries if entry.get("fragment_low") == entry.get("low")),
        "best_low_context": best_low.get("context_family", ""),
        "best_low_correct_slots": best_low.get("loo_correct_slots", 0),
        "best_low_false_slots": best_low.get("loo_false_slots", 0),
        "best_low_precision": best_low.get("loo_precision", "0.000000"),
        "best_low_coverage": best_low.get("loo_coverage", "0.000000"),
        "best_byte_context": best_byte.get("context_family", ""),
        "best_byte_correct_slots": best_byte.get("loo_correct_slots", 0),
        "best_byte_false_slots": best_byte.get("loo_false_slots", 0),
        "best_byte_precision": best_byte.get("loo_precision", "0.000000"),
        "best_byte_coverage": best_byte.get("loo_coverage", "0.000000"),
        "best_high_context": best_high.get("context_family", ""),
        "best_high_correct_slots": best_high.get("loo_correct_slots", 0),
        "best_high_false_slots": best_high.get("loo_false_slots", 0),
        "best_high_precision": best_high.get("loo_precision", "0.000000"),
        "best_high_coverage": best_high.get("loo_coverage", "0.000000"),
        "best_low_false_free_context": best_low_false_free.get("context_family", ""),
        "best_low_false_free_slots": best_low_false_free.get("loo_correct_slots", 0),
        "best_byte_false_free_context": best_byte_false_free.get("context_family", ""),
        "best_byte_false_free_slots": best_byte_false_free.get("loo_correct_slots", 0),
        "promotion_candidate_bytes": low_candidate_bytes,
        "promotion_ready_bytes": 0,
        "issue_rows": len(issues) + sum(1 for row in rows if row.get("issues")),
    }


def build(
    slot_rows: list[dict[str, str]],
    target_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    rows, entries, issues = build_entries(slot_rows, target_rows, fixture_rows)
    candidates = evaluate_candidates(entries)
    summary = build_summary(rows, entries, candidates, issues)
    rows = annotate_rows(rows, entries, best_candidate(candidates, "low"), best_candidate(candidates, "byte"))
    contexts = build_context_rows(entries, candidates)
    return summary, rows, candidates, contexts


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
    candidates: list[dict[str, object]],
    contexts: list[dict[str, object]],
    title: str,
) -> str:
    data_json = json.dumps(
        {"summary": summary, "slots": rows, "candidates": candidates, "contexts": contexts},
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
table {{ border-collapse: collapse; width: 100%; min-width: 2100px; }}
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
  <div class="box"><div class="num">{summary['control_low_exact_slots']}/{summary['start_low_exact_slots']}</div><div class="muted">raw low control/start</div></div>
  <div class="box"><div class="num">{summary['best_low_correct_slots']}/{summary['best_low_false_slots']}</div><div class="muted">best low LOO correct/false</div></div>
  <div class="box"><div class="num">{summary['best_byte_correct_slots']}/{summary['best_byte_false_slots']}</div><div class="muted">best byte LOO correct/false</div></div>
  <div class="box"><div class="num">{summary['best_low_false_free_slots']}</div><div class="muted">best low false-free slots</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Slots</h2>{render_table(rows, SLOT_FIELDNAMES)}</div>
<div class="panel"><h2>Candidates</h2>{render_table(candidates, CANDIDATE_FIELDNAMES)}</div>
<div class="panel"><h2>Contexts</h2>{render_table(contexts, CONTEXT_FIELDNAMES)}</div>
<script type="application/json" id="gradient-sequence-high-safe-control-opcode-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe control/opcode contexts for gradient high-safe residual slots.")
    parser.add_argument("--slots", type=Path, default=DEFAULT_SLOTS)
    parser.add_argument("--target-rows", type=Path, default=DEFAULT_TARGET_ROWS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Gradient Sequence High-Safe Control Opcode Probe",
    )
    args = parser.parse_args()

    summary, rows, candidates, contexts = build(
        read_csv(args.slots),
        read_csv(args.target_rows),
        read_csv(args.fixtures),
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "slots.csv", SLOT_FIELDNAMES, rows)
    write_csv(args.output / "candidates.csv", CANDIDATE_FIELDNAMES, candidates)
    write_csv(args.output / "contexts.csv", CONTEXT_FIELDNAMES, contexts)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, rows, candidates, contexts, args.title))

    print(f"Slots: {summary['slots']}")
    print(
        "Raw low control/start: "
        f"{summary['control_low_exact_slots']} / {summary['start_low_exact_slots']}"
    )
    print(
        "Best low opcode context: "
        f"{summary['best_low_context']} = "
        f"{summary['best_low_correct_slots']} correct / {summary['best_low_false_slots']} false"
    )
    print(
        "Best byte opcode context: "
        f"{summary['best_byte_context']} = "
        f"{summary['best_byte_correct_slots']} correct / {summary['best_byte_false_slots']} false"
    )
    print(f"Best low false-free slots: {summary['best_low_false_free_slots']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
