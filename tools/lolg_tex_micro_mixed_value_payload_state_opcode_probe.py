#!/usr/bin/env python3
"""Probe external state/opcode contexts for dominant mixed-value payloads."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path


DEFAULT_INPUT_ROWS = Path("output/tex_micro_mixed_value_dominant_control/rows.csv")
DEFAULT_CONTROL_ROWS = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_mixed_token_control_context_probe/targets.csv"
)
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_OUTPUT = Path("output/tex_micro_mixed_value_payload_state_opcode")

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "target_bytes",
    "entry_slots",
    "state_candidate_rows",
    "signal_anchor_rows",
    "control_anchor_rows",
    "signal_slot_bytes",
    "control_slot_bytes",
    "signal_raw_exact_bytes",
    "control_raw_exact_bytes",
    "signal_high_exact_bytes",
    "control_high_exact_bytes",
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
    "best_high_baseline_value",
    "best_high_baseline_precision",
    "best_band_context",
    "best_band_correct_slots",
    "best_band_false_slots",
    "best_band_precision",
    "best_band_coverage",
    "best_step_context",
    "best_step_correct_slots",
    "best_step_false_slots",
    "best_step_precision",
    "best_step_coverage",
    "source_state_rejected",
    "promotion_ready_bytes",
    "issue_rows",
]

ROW_FIELDNAMES = [
    "rank",
    "archive",
    "pcx_name",
    "frontier_id",
    "span_index",
    "op_index",
    "length",
    "start",
    "end",
    "control_ref_mod64",
    "best_signal_key",
    "best_signal_offset",
    "best_signal_offset_mod64",
    "control_anchor",
    "segment_gap_bytes",
    "control_prefix_bytes",
    "fragment_bytes",
    "signal_slot_bytes",
    "control_slot_bytes",
    "signal_raw_exact_bytes",
    "control_raw_exact_bytes",
    "signal_high_exact_bytes",
    "control_high_exact_bytes",
    "payload_head_hex",
    "payload_tail_hex",
    "verdict",
    "issues",
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


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def int_value(row: dict[str, str] | dict[str, object], field: str, default: int = 0) -> int:
    try:
        return int(row.get(field, "") or default)
    except (TypeError, ValueError):
        return default


def ratio(numerator: int, denominator: int) -> str:
    return f"{(numerator / denominator) if denominator else 0.0:.6f}"


def fixture_key(row: dict[str, str] | dict[str, object]) -> tuple[str, str, str]:
    return (
        str(row.get("archive", "")),
        str(row.get("pcx_name", "")),
        str(row.get("frontier_id", "")),
    )


def join_key(row: dict[str, str] | dict[str, object]) -> tuple[str, str, str, str, str, str, str, str]:
    return (
        str(row.get("archive", "")),
        str(row.get("pcx_name", "")),
        str(row.get("frontier_id", "")),
        str(row.get("span_index", "")),
        str(row.get("op_index", "")),
        str(row.get("length", "")),
        str(row.get("start", "")),
        str(row.get("end", "")),
    )


def read_bytes(path_text: str, issues: list[str], label: str) -> bytes:
    if not path_text:
        issues.append(f"missing_{label}_path")
        return b""
    try:
        return Path(path_text).read_bytes()
    except OSError as exc:
        issues.append(f"read_{label}_failed:{exc}")
        return b""


def load_sources(fixture_rows: list[dict[str, str]]) -> tuple[dict[tuple[str, str, str], dict[str, bytes]], list[str]]:
    sources: dict[tuple[str, str, str], dict[str, bytes]] = {}
    issues: list[str] = []
    for fixture in fixture_rows:
        key = fixture_key(fixture)
        local_issues: list[str] = []
        sources[key] = {
            "expected": read_bytes(fixture.get("expected_gap_path", ""), local_issues, "expected"),
            "segment_gap": read_bytes(fixture.get("segment_gap_path", ""), local_issues, "segment_gap"),
            "control_prefix": read_bytes(fixture.get("control_prefix_path", ""), local_issues, "control_prefix"),
            "fragment": read_bytes(fixture.get("fragment_path", ""), local_issues, "fragment"),
        }
        issues.extend(f"{key}:{issue}" for issue in local_issues)
    return sources, issues


def byte_at(data: bytes, index: int) -> int | None:
    if 0 <= index < len(data):
        return data[index]
    return None


def hex_value(value: int | None) -> str:
    return f"{value:02x}" if value is not None else "NA"


def high_value(value: int | None) -> str:
    return f"{value >> 4:x}" if value is not None else "NA"


def low_value(value: int | None) -> str:
    return f"{value & 0x0F:x}" if value is not None else "NA"


def band_token(value: int) -> str:
    high = value >> 4
    if high in {5, 6, 7, 10}:
        return f"{high:x}"
    return "x"


def source_class(value: int | None) -> str:
    if value is None:
        return "NA"
    high = value >> 4
    if value == 0:
        return "zero"
    if value >= 0xF0:
        return "ff"
    if value >= 0x80:
        return "opcode_hi"
    if high in {0, 3, 5, 6, 7, 10}:
        return f"h{high:x}"
    return "other"


def signed_delta(left: int, right: int) -> int:
    return ((right - left + 128) & 0xFF) - 128


def signed_bucket(delta: int | None) -> str:
    if delta is None:
        return "NA"
    if delta == 0:
        return "0"
    prefix = "+" if delta > 0 else "-"
    magnitude = abs(delta)
    if magnitude <= 4:
        suffix = "s"
    elif magnitude <= 31:
        suffix = "m"
    else:
        suffix = "j"
    return f"{prefix}{suffix}"


def delta_bucket(left: int | None, right: int | None) -> str:
    if left is None or right is None:
        return "NA"
    return signed_bucket(signed_delta(left, right))


def cyclic_byte(data: bytes, offset: int) -> int | None:
    if not data:
        return None
    return data[offset % len(data)]


def context_functions():
    return {
        "control_ref_pos16": lambda row: (row["control_ref"], row["pos16"]),
        "signal_key_pos16": lambda row: (row["signal_key"], row["pos16"]),
        "control_signal_pos16": lambda row: (row["control_ref"], row["signal_key"], row["pos16"]),
        "signal_byte_pos16": lambda row: (row["signal_byte"], row["pos16"]),
        "signal_high_pos16": lambda row: (row["signal_high"], row["pos16"]),
        "signal_low_pos16": lambda row: (row["signal_low"], row["pos16"]),
        "signal_class_pos16": lambda row: (row["signal_class"], row["pos16"]),
        "signal_delta_pos16": lambda row: (row["signal_delta"], row["pos16"]),
        "control_byte_pos16": lambda row: (row["control_byte"], row["pos16"]),
        "control_high_pos16": lambda row: (row["control_high"], row["pos16"]),
        "control_class_pos16": lambda row: (row["control_class"], row["pos16"]),
        "control_delta_pos16": lambda row: (row["control_delta"], row["pos16"]),
        "prefix_byte_pos16": lambda row: (row["prefix_byte"], row["pos16"]),
        "prefix_class_pos16": lambda row: (row["prefix_class"], row["pos16"]),
        "fragment_byte_pos16": lambda row: (row["fragment_byte"], row["pos16"]),
        "fragment_class_pos16": lambda row: (row["fragment_class"], row["pos16"]),
        "state_high_mix_pos16": lambda row: (
            row["signal_high"],
            row["control_high"],
            row["prefix_high"],
            row["pos16"],
        ),
        "state_class_mix_pos16": lambda row: (
            row["signal_class"],
            row["control_class"],
            row["prefix_class"],
            row["pos16"],
        ),
        "state_delta_mix_pos16": lambda row: (row["signal_delta"], row["control_delta"], row["pos16"]),
        "signal_byte_pos8": lambda row: (row["signal_byte"], row["pos8"]),
        "control_byte_pos8": lambda row: (row["control_byte"], row["pos8"]),
        "prefix_byte_pos8": lambda row: (row["prefix_byte"], row["pos8"]),
    }


def target_value(entry: dict[str, object], target_kind: str) -> str:
    return str(entry[target_kind])


def strict_prediction(counter: Counter[str]) -> str | None:
    values = [value for value, count in counter.items() if count > 0]
    return values[0] if len(values) == 1 else None


def baseline(entries: list[dict[str, object]], target_kind: str) -> tuple[str, int, str]:
    counts = Counter(target_value(entry, target_kind) for entry in entries)
    if not counts:
        return "", 0, "0.000000"
    value, count = counts.most_common(1)[0]
    return value, count, ratio(count, len(entries))


def evaluate_candidate(
    entries: list[dict[str, object]],
    target_kind: str,
    context_family: str,
    context_func,
) -> dict[str, object]:
    grouped: dict[tuple[object, ...], list[dict[str, object]]] = defaultdict(list)
    all_counts: dict[tuple[object, ...], Counter[str]] = defaultdict(Counter)
    row_counts: dict[tuple[int, tuple[object, ...]], Counter[str]] = defaultdict(Counter)
    for entry in entries:
        context = context_func(entry)
        value = target_value(entry, target_kind)
        grouped[context].append(entry)
        all_counts[context][value] += 1
        row_counts[(int(entry["row_index"]), context)][value] += 1

    deterministic_repeated = 0
    deterministic_singleton = 0
    conflicted = 0
    predicted_values: Counter[str] = Counter()
    for context, group in grouped.items():
        prediction = strict_prediction(all_counts[context])
        if prediction is None:
            conflicted += len(group)
            continue
        predicted_values[prediction] += len(group)
        if len(group) > 1:
            deterministic_repeated += len(group)
        else:
            deterministic_singleton += 1

    correct = 0
    false = 0
    unknown = 0
    sample_context = ""
    sample_prediction = ""
    for entry in entries:
        context = context_func(entry)
        train_counts = all_counts[context].copy()
        train_counts.subtract(row_counts[(int(entry["row_index"]), context)])
        train_counts += Counter()
        prediction = strict_prediction(train_counts)
        if prediction is None:
            unknown += 1
            continue
        if not sample_context:
            sample_context = "|".join(str(part) for part in context)
            sample_prediction = prediction
        if prediction == target_value(entry, target_kind):
            correct += 1
        else:
            false += 1

    base_value, base_correct, base_precision = baseline(entries, target_kind)
    predicted = correct + false
    precision = (correct / predicted) if predicted else 0.0
    baseline_float = float(base_precision)
    if predicted == 0:
        verdict = "no_cross_row_state"
    elif target_kind == "byte" and false >= correct:
        verdict = "byte_state_reject"
    elif false == 0 and correct >= 32:
        verdict = "false_free_state_review"
    elif target_kind in {"high", "band"} and correct > false and precision > baseline_float + 0.05:
        verdict = "partial_state_hint"
    elif target_kind == "step" and correct > false:
        verdict = "partial_step_hint"
    else:
        verdict = "conflicted_state_context"

    return {
        "rank": 0,
        "target_kind": target_kind,
        "context_family": context_family,
        "contexts": len(grouped),
        "deterministic_repeated_slots": deterministic_repeated,
        "deterministic_singleton_slots": deterministic_singleton,
        "conflicted_slots": conflicted,
        "loo_correct_slots": correct,
        "loo_false_slots": false,
        "loo_unknown_slots": unknown,
        "loo_precision": ratio(correct, predicted),
        "loo_coverage": ratio(predicted, len(entries)),
        "baseline_value": base_value,
        "baseline_correct_slots": base_correct,
        "baseline_precision": base_precision,
        "predicted_values": "|".join(f"{value}:{count}" for value, count in predicted_values.most_common(8)),
        "verdict": verdict,
        "sample_context": sample_context,
        "sample_prediction": sample_prediction,
    }


def best_candidate(rows: list[dict[str, object]], target_kind: str) -> dict[str, object]:
    target_rows = [
        row
        for row in rows
        if row.get("target_kind") == target_kind
        and int_value(row, "loo_correct_slots") + int_value(row, "loo_false_slots") > 0
    ]
    if not target_rows:
        return {}
    target_rows.sort(
        key=lambda row: (
            int_value(row, "loo_correct_slots"),
            -int_value(row, "loo_false_slots"),
            float(row.get("loo_precision", "0") or 0),
            float(row.get("loo_coverage", "0") or 0),
        ),
        reverse=True,
    )
    return target_rows[0]


def build_entries(
    input_rows: list[dict[str, str]],
    control_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]], list[str]]:
    sources_by_fixture, fixture_issues = load_sources(fixture_rows)
    control_by_key = {join_key(row): row for row in control_rows}
    rows: list[dict[str, object]] = []
    entries: list[dict[str, object]] = []
    issues = list(fixture_issues)

    for row_index, input_row in enumerate(input_rows):
        row_issues = [issue for issue in input_row.get("issues", "").split(";") if issue]
        sources = sources_by_fixture.get(fixture_key(input_row), {})
        expected = sources.get("expected", b"")
        segment = sources.get("segment_gap", b"")
        control_prefix = sources.get("control_prefix", b"")
        fragment = sources.get("fragment", b"")
        start = int_value(input_row, "start")
        end = int_value(input_row, "end")
        payload = expected[start:end]
        if not payload:
            row_issues.append("missing_payload")
        if input_row.get("length") and int_value(input_row, "length") != len(payload):
            row_issues.append(f"length_mismatch:{input_row.get('length')}:{len(payload)}")

        control = control_by_key.get(join_key(input_row))
        if control is None:
            row_issues.append("missing_control_context")
            signal_offset = -1
            signal_offset_mod64 = -1
        else:
            signal_offset = int_value(control, "best_signal_offset", -1)
            signal_offset_mod64 = int_value(control, "best_signal_offset_mod64", -1)

        control_ref_text = input_row.get("control_ref_mod64", "")
        if control_ref_text.isdigit() and signal_offset >= 0 and signal_offset_mod64 >= 0:
            control_anchor = signal_offset - signal_offset_mod64 + int(control_ref_text)
        else:
            control_anchor = -1

        signal_slot_bytes = 0
        control_slot_bytes = 0
        signal_raw_exact = 0
        control_raw_exact = 0
        signal_high_exact = 0
        control_high_exact = 0

        for offset, value in enumerate(payload):
            previous = payload[offset - 1] if offset else None
            signal_index = signal_offset + offset
            control_index = control_anchor + offset
            signal_byte = byte_at(segment, signal_index)
            signal_previous = byte_at(segment, signal_index - 1)
            control_byte = byte_at(segment, control_index)
            control_previous = byte_at(segment, control_index - 1)
            prefix_byte = cyclic_byte(control_prefix, offset)
            fragment_byte = cyclic_byte(fragment, offset)

            if signal_byte is not None:
                signal_slot_bytes += 1
                if signal_byte == value:
                    signal_raw_exact += 1
                if (signal_byte >> 4) == (value >> 4):
                    signal_high_exact += 1
            if control_byte is not None:
                control_slot_bytes += 1
                if control_byte == value:
                    control_raw_exact += 1
                if (control_byte >> 4) == (value >> 4):
                    control_high_exact += 1

            entries.append(
                {
                    "row_index": row_index,
                    "archive": input_row.get("archive", ""),
                    "pcx_name": input_row.get("pcx_name", ""),
                    "frontier_id": input_row.get("frontier_id", ""),
                    "offset": offset,
                    "length": len(payload),
                    "byte": f"{value:02x}",
                    "high": f"{value >> 4:x}",
                    "low": f"{value & 0x0F:x}",
                    "band": band_token(value),
                    "step": signed_bucket(signed_delta(previous, value)) if previous is not None else "START",
                    "pos4": str(offset % 4),
                    "pos8": str(offset % 8),
                    "pos16": str((offset * 16) // len(payload)) if payload else "0",
                    "tail8": str(len(payload) - 1 - offset) if len(payload) - 1 - offset < 8 else "body",
                    "control_ref": input_row.get("control_ref_mod64", ""),
                    "signal_key": input_row.get("best_signal_key", ""),
                    "signal_byte": hex_value(signal_byte),
                    "signal_high": high_value(signal_byte),
                    "signal_low": low_value(signal_byte),
                    "signal_class": source_class(signal_byte),
                    "signal_delta": delta_bucket(signal_previous, signal_byte),
                    "control_byte": hex_value(control_byte),
                    "control_high": high_value(control_byte),
                    "control_low": low_value(control_byte),
                    "control_class": source_class(control_byte),
                    "control_delta": delta_bucket(control_previous, control_byte),
                    "prefix_byte": hex_value(prefix_byte),
                    "prefix_high": high_value(prefix_byte),
                    "prefix_class": source_class(prefix_byte),
                    "fragment_byte": hex_value(fragment_byte),
                    "fragment_high": high_value(fragment_byte),
                    "fragment_class": source_class(fragment_byte),
                }
            )

        if signal_slot_bytes == 0:
            row_issues.append("missing_signal_slots")
        if control_slot_bytes == 0:
            row_issues.append("missing_control_slots")

        rows.append(
            {
                "rank": len(rows) + 1,
                "archive": input_row.get("archive", ""),
                "pcx_name": input_row.get("pcx_name", ""),
                "frontier_id": input_row.get("frontier_id", ""),
                "span_index": input_row.get("span_index", ""),
                "op_index": input_row.get("op_index", ""),
                "length": len(payload),
                "start": input_row.get("start", ""),
                "end": input_row.get("end", ""),
                "control_ref_mod64": input_row.get("control_ref_mod64", ""),
                "best_signal_key": input_row.get("best_signal_key", ""),
                "best_signal_offset": signal_offset if signal_offset >= 0 else "",
                "best_signal_offset_mod64": signal_offset_mod64 if signal_offset_mod64 >= 0 else "",
                "control_anchor": control_anchor if control_anchor >= 0 else "",
                "segment_gap_bytes": len(segment),
                "control_prefix_bytes": len(control_prefix),
                "fragment_bytes": len(fragment),
                "signal_slot_bytes": signal_slot_bytes,
                "control_slot_bytes": control_slot_bytes,
                "signal_raw_exact_bytes": signal_raw_exact,
                "control_raw_exact_bytes": control_raw_exact,
                "signal_high_exact_bytes": signal_high_exact,
                "control_high_exact_bytes": control_high_exact,
                "payload_head_hex": payload[:18].hex(),
                "payload_tail_hex": payload[-18:].hex() if payload else "",
                "verdict": "state_context_available" if signal_slot_bytes and control_slot_bytes else "state_context_incomplete",
                "issues": ";".join(row_issues),
            }
        )

    summary_seed = {
        "scope": "total",
        "target_rows": len(rows),
        "target_bytes": sum(int_value(row, "length") for row in rows),
        "entry_slots": len(entries),
        "signal_anchor_rows": sum(1 for row in rows if str(row.get("best_signal_offset", "")) != ""),
        "control_anchor_rows": sum(1 for row in rows if str(row.get("control_anchor", "")) != ""),
        "signal_slot_bytes": sum(int_value(row, "signal_slot_bytes") for row in rows),
        "control_slot_bytes": sum(int_value(row, "control_slot_bytes") for row in rows),
        "signal_raw_exact_bytes": sum(int_value(row, "signal_raw_exact_bytes") for row in rows),
        "control_raw_exact_bytes": sum(int_value(row, "control_raw_exact_bytes") for row in rows),
        "signal_high_exact_bytes": sum(int_value(row, "signal_high_exact_bytes") for row in rows),
        "control_high_exact_bytes": sum(int_value(row, "control_high_exact_bytes") for row in rows),
    }
    issue_rows = sum(1 for row in rows if row.get("issues"))
    issues.extend(f"row:{row.get('rank')}:{row.get('issues')}" for row in rows if row.get("issues"))
    summary_seed["issue_rows"] = issue_rows + len(fixture_issues)
    return summary_seed, rows, entries, issues


def build_context_rows(
    entries: list[dict[str, object]],
    candidates: list[dict[str, object]],
) -> list[dict[str, object]]:
    families_by_target: dict[str, set[str]] = defaultdict(set)
    for target_kind in ("byte", "high", "band", "step"):
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
        for row in ranked[:3]:
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
                        "target_values": "|".join(f"{value}:{count}" for value, count in values.most_common(8)),
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


def build(
    input_rows: list[dict[str, str]],
    control_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    summary_seed, rows, entries, issues = build_entries(input_rows, control_rows, fixture_rows)
    candidate_rows: list[dict[str, object]] = []
    for target_kind in ("byte", "high", "low", "band", "step"):
        for context_family, context_func in context_functions().items():
            candidate_rows.append(evaluate_candidate(entries, target_kind, context_family, context_func))

    candidate_rows.sort(
        key=lambda row: (
            str(row["target_kind"]),
            -int_value(row, "loo_correct_slots"),
            int_value(row, "loo_false_slots"),
            str(row["context_family"]),
        )
    )
    for index, row in enumerate(candidate_rows, start=1):
        row["rank"] = index

    best_byte = best_candidate(candidate_rows, "byte")
    best_high = best_candidate(candidate_rows, "high")
    best_band = best_candidate(candidate_rows, "band")
    best_step = best_candidate(candidate_rows, "step")
    byte_rejected = int_value(best_byte, "loo_false_slots") >= int_value(best_byte, "loo_correct_slots")
    high_baseline_precision = float(best_high.get("baseline_precision", "0") or 0)
    high_precision = float(best_high.get("loo_precision", "0") or 0)
    high_coverage = float(best_high.get("loo_coverage", "0") or 0)
    source_state_rejected = byte_rejected and (high_precision <= high_baseline_precision + 0.08 or high_coverage < 0.20)
    promotion_ready = 0

    summary = {
        **summary_seed,
        "state_candidate_rows": len(candidate_rows),
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
        "best_high_baseline_value": best_high.get("baseline_value", ""),
        "best_high_baseline_precision": best_high.get("baseline_precision", "0.000000"),
        "best_band_context": best_band.get("context_family", ""),
        "best_band_correct_slots": best_band.get("loo_correct_slots", 0),
        "best_band_false_slots": best_band.get("loo_false_slots", 0),
        "best_band_precision": best_band.get("loo_precision", "0.000000"),
        "best_band_coverage": best_band.get("loo_coverage", "0.000000"),
        "best_step_context": best_step.get("context_family", ""),
        "best_step_correct_slots": best_step.get("loo_correct_slots", 0),
        "best_step_false_slots": best_step.get("loo_false_slots", 0),
        "best_step_precision": best_step.get("loo_precision", "0.000000"),
        "best_step_coverage": best_step.get("loo_coverage", "0.000000"),
        "source_state_rejected": "1" if source_state_rejected else "0",
        "promotion_ready_bytes": promotion_ready,
        "issue_rows": summary_seed.get("issue_rows", len(issues)),
    }
    context_rows = build_context_rows(entries, candidate_rows)
    return summary, rows, candidate_rows, context_rows


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
        {"summary": summary, "rows": rows, "candidates": candidates, "contexts": contexts},
        indent=2,
        sort_keys=True,
    )
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body {{ margin: 2rem; background: #111416; color: #edf5f4; font: 14px/1.45 system-ui, sans-serif; }}
table {{ border-collapse: collapse; width: 100%; min-width: 1550px; }}
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
  <div class="box"><div class="num">{summary['signal_raw_exact_bytes']}/{summary['control_raw_exact_bytes']}</div><div class="muted">raw exact signal/control</div></div>
  <div class="box"><div class="num">{summary['best_byte_correct_slots']}/{summary['best_byte_false_slots']}</div><div class="muted">best byte correct/false</div></div>
  <div class="box"><div class="num">{summary['best_high_correct_slots']}/{summary['best_high_false_slots']}</div><div class="muted">best high correct/false</div></div>
  <div class="box"><div class="num">{summary['best_high_baseline_precision']}</div><div class="muted">high baseline precision</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Rows</h2>{render_table(rows, ROW_FIELDNAMES)}</div>
<div class="panel"><h2>Candidates</h2>{render_table(candidates, CANDIDATE_FIELDNAMES)}</div>
<div class="panel"><h2>Contexts</h2>{render_table(contexts, CONTEXT_FIELDNAMES)}</div>
<script type="application/json" id="payload-state-opcode-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe source state/opcode contexts for mixed-value payloads.")
    parser.add_argument("--input-rows", type=Path, default=DEFAULT_INPUT_ROWS)
    parser.add_argument("--control-rows", type=Path, default=DEFAULT_CONTROL_ROWS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Mixed Value Payload State Opcode")
    args = parser.parse_args()

    summary, rows, candidates, contexts = build(
        read_csv(args.input_rows),
        read_csv(args.control_rows),
        read_csv(args.fixtures),
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "rows.csv", ROW_FIELDNAMES, rows)
    write_csv(args.output / "candidates.csv", CANDIDATE_FIELDNAMES, candidates)
    write_csv(args.output / "contexts.csv", CONTEXT_FIELDNAMES, contexts)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, rows, candidates, contexts, args.title))

    print(f"Target bytes: {summary['target_bytes']}")
    print(f"Raw exact signal/control: {summary['signal_raw_exact_bytes']}/{summary['control_raw_exact_bytes']}")
    print(
        f"Best byte state: {summary['best_byte_context']} "
        f"{summary['best_byte_correct_slots']}/{summary['best_byte_false_slots']}"
    )
    print(
        f"Best high state: {summary['best_high_context']} "
        f"{summary['best_high_correct_slots']}/{summary['best_high_false_slots']}"
    )
    print(f"High baseline precision: {summary['best_high_baseline_precision']}")
    print(f"Source-state rejected: {summary['source_state_rejected']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
