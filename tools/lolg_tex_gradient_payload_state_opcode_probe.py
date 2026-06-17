#!/usr/bin/env python3
"""Probe external state/opcode contexts for gradient-like payloads."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_micro_mixed_value_payload_state_opcode_probe import (
    band_token,
    best_candidate,
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
    signed_bucket,
    signed_delta,
    source_class,
    target_value,
)


DEFAULT_INPUT_ROWS = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_probe/targets.csv")
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_OUTPUT = Path("output/tex_gradient_payload_state_opcode")

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "target_bytes",
    "entry_slots",
    "state_candidate_rows",
    "gradient_classes",
    "control_anchor_rows",
    "start_anchor_rows",
    "control_slot_bytes",
    "start_slot_bytes",
    "control_raw_exact_bytes",
    "start_raw_exact_bytes",
    "control_high_exact_bytes",
    "start_high_exact_bytes",
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
    "gradient_class",
    "control_ref_offset",
    "control_ref_mod64",
    "start_anchor",
    "segment_gap_bytes",
    "control_prefix_bytes",
    "fragment_bytes",
    "control_slot_bytes",
    "start_slot_bytes",
    "control_raw_exact_bytes",
    "start_raw_exact_bytes",
    "control_high_exact_bytes",
    "start_high_exact_bytes",
    "small_delta_ratio",
    "zero_delta_ratio",
    "step_delta_ratio",
    "dominant_delta",
    "linear_exact_bytes",
    "top_nibble",
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

GROUP_FIELDNAMES = [
    "rank",
    "group_kind",
    "group_key",
    "rows",
    "bytes",
    "control_anchor_rows",
    "control_slot_bytes",
    "control_raw_exact_bytes",
    "control_high_exact_bytes",
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


def parse_window_signature(text: str) -> tuple[bytes, bytes]:
    head = b""
    tail = b""
    for part in text.split("|"):
        if part.startswith("head="):
            try:
                head = bytes.fromhex(part.split("=", 1)[1])
            except ValueError:
                head = b""
        elif part.startswith("tail="):
            try:
                tail = bytes.fromhex(part.split("=", 1)[1])
            except ValueError:
                tail = b""
    return head, tail


def ratio_bin(text: str) -> str:
    try:
        value = float(text or 0)
    except ValueError:
        value = 0.0
    if value >= 0.90:
        return "ge90"
    if value >= 0.75:
        return "ge75"
    if value >= 0.50:
        return "ge50"
    if value > 0:
        return "lt50"
    return "zero"


def context_functions():
    return {
        "control_ref_pos16": lambda row: (row["control_ref_mod64"], row["pos16"]),
        "control_byte_pos16": lambda row: (row["control_byte"], row["pos16"]),
        "control_high_pos16": lambda row: (row["control_high"], row["pos16"]),
        "control_class_pos16": lambda row: (row["control_class"], row["pos16"]),
        "control_delta_pos16": lambda row: (row["control_delta"], row["pos16"]),
        "start_byte_pos16": lambda row: (row["start_byte"], row["pos16"]),
        "start_high_pos16": lambda row: (row["start_high"], row["pos16"]),
        "start_class_pos16": lambda row: (row["start_class"], row["pos16"]),
        "start_delta_pos16": lambda row: (row["start_delta"], row["pos16"]),
        "window_head_pos16": lambda row: (row["window_head_byte"], row["pos16"]),
        "window_tail_pos16": lambda row: (row["window_tail_byte"], row["pos16"]),
        "prefix_byte_pos16": lambda row: (row["prefix_byte"], row["pos16"]),
        "prefix_class_pos16": lambda row: (row["prefix_class"], row["pos16"]),
        "fragment_byte_pos16": lambda row: (row["fragment_byte"], row["pos16"]),
        "fragment_class_pos16": lambda row: (row["fragment_class"], row["pos16"]),
        "state_high_mix_pos16": lambda row: (
            row["control_high"],
            row["start_high"],
            row["window_head_high"],
            row["pos16"],
        ),
        "state_class_mix_pos16": lambda row: (
            row["control_class"],
            row["start_class"],
            row["window_head_class"],
            row["pos16"],
        ),
        "state_delta_mix_pos16": lambda row: (row["control_delta"], row["start_delta"], row["pos16"]),
        "control_byte_pos8": lambda row: (row["control_byte"], row["pos8"]),
        "start_byte_pos8": lambda row: (row["start_byte"], row["pos8"]),
        "window_head_pos8": lambda row: (row["window_head_byte"], row["pos8"]),
    }


def build_entries(
    input_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    sources_by_fixture, fixture_issues = load_sources(fixture_rows)
    rows: list[dict[str, object]] = []
    entries: list[dict[str, object]] = []

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

        control_ref_offset = int_value(input_row, "control_ref_offset", -1)
        control_ref_mod64 = int_value(input_row, "control_ref_mod64", -1)
        start_mod64 = int_value(input_row, "start_mod64", -1)
        if control_ref_offset >= 0 and control_ref_mod64 >= 0 and start_mod64 >= 0:
            start_anchor = control_ref_offset - control_ref_mod64 + start_mod64
        else:
            start_anchor = -1
        window_head, window_tail = parse_window_signature(input_row.get("control_window_signature", ""))

        control_slot_bytes = 0
        start_slot_bytes = 0
        control_raw_exact = 0
        start_raw_exact = 0
        control_high_exact = 0
        start_high_exact = 0

        for offset, value in enumerate(payload):
            previous = payload[offset - 1] if offset else None
            control_index = control_ref_offset + offset if control_ref_offset >= 0 else -1
            start_index = start_anchor + offset if start_anchor >= 0 else -1
            control_byte = byte_at(segment, control_index)
            control_previous = byte_at(segment, control_index - 1)
            start_byte = byte_at(segment, start_index)
            start_previous = byte_at(segment, start_index - 1)
            prefix_byte = cyclic_byte(control_prefix, offset)
            fragment_byte = cyclic_byte(fragment, offset)
            window_head_byte = cyclic_byte(window_head, offset)
            window_tail_byte = cyclic_byte(window_tail, offset)

            if control_byte is not None:
                control_slot_bytes += 1
                if control_byte == value:
                    control_raw_exact += 1
                if (control_byte >> 4) == (value >> 4):
                    control_high_exact += 1
            if start_byte is not None:
                start_slot_bytes += 1
                if start_byte == value:
                    start_raw_exact += 1
                if (start_byte >> 4) == (value >> 4):
                    start_high_exact += 1

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
                    "gradient_class": input_row.get("gradient_class", ""),
                    "dominant_delta": input_row.get("dominant_delta", ""),
                    "top_nibble": input_row.get("top_nibble", ""),
                    "small_delta_bin": ratio_bin(input_row.get("small_delta_ratio", "")),
                    "zero_delta_bin": ratio_bin(input_row.get("zero_delta_ratio", "")),
                    "step_delta_bin": ratio_bin(input_row.get("step_delta_ratio", "")),
                    "control_ref_mod64": input_row.get("control_ref_mod64", ""),
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
                    "window_head_byte": hex_value(window_head_byte),
                    "window_head_high": high_value(window_head_byte),
                    "window_head_class": source_class(window_head_byte),
                    "window_tail_byte": hex_value(window_tail_byte),
                    "window_tail_high": high_value(window_tail_byte),
                    "window_tail_class": source_class(window_tail_byte),
                    "prefix_byte": hex_value(prefix_byte),
                    "prefix_high": high_value(prefix_byte),
                    "prefix_class": source_class(prefix_byte),
                    "fragment_byte": hex_value(fragment_byte),
                    "fragment_high": high_value(fragment_byte),
                    "fragment_class": source_class(fragment_byte),
                }
            )

        if control_ref_offset < 0:
            row_issues.append("missing_control_ref_offset")
        if control_slot_bytes == 0:
            row_issues.append("missing_control_slots")
        if start_slot_bytes == 0:
            row_issues.append("missing_start_slots")

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
                "gradient_class": input_row.get("gradient_class", ""),
                "control_ref_offset": control_ref_offset if control_ref_offset >= 0 else "",
                "control_ref_mod64": input_row.get("control_ref_mod64", ""),
                "start_anchor": start_anchor if start_anchor >= 0 else "",
                "segment_gap_bytes": len(segment),
                "control_prefix_bytes": len(control_prefix),
                "fragment_bytes": len(fragment),
                "control_slot_bytes": control_slot_bytes,
                "start_slot_bytes": start_slot_bytes,
                "control_raw_exact_bytes": control_raw_exact,
                "start_raw_exact_bytes": start_raw_exact,
                "control_high_exact_bytes": control_high_exact,
                "start_high_exact_bytes": start_high_exact,
                "small_delta_ratio": input_row.get("small_delta_ratio", ""),
                "zero_delta_ratio": input_row.get("zero_delta_ratio", ""),
                "step_delta_ratio": input_row.get("step_delta_ratio", ""),
                "dominant_delta": input_row.get("dominant_delta", ""),
                "linear_exact_bytes": input_row.get("linear_exact_bytes", ""),
                "top_nibble": input_row.get("top_nibble", ""),
                "payload_head_hex": payload[:18].hex(),
                "payload_tail_hex": payload[-18:].hex() if payload else "",
                "verdict": "state_context_available" if control_slot_bytes else "state_context_incomplete",
                "issues": ";".join(row_issues),
            }
        )

    issue_rows = sum(1 for row in rows if row.get("issues"))
    summary_seed = {
        "scope": "total",
        "target_rows": len(rows),
        "target_bytes": sum(int_value(row, "length") for row in rows),
        "entry_slots": len(entries),
        "gradient_classes": len({str(row.get("gradient_class", "")) for row in rows}),
        "control_anchor_rows": sum(1 for row in rows if str(row.get("control_ref_offset", "")) != ""),
        "start_anchor_rows": sum(1 for row in rows if str(row.get("start_anchor", "")) != ""),
        "control_slot_bytes": sum(int_value(row, "control_slot_bytes") for row in rows),
        "start_slot_bytes": sum(int_value(row, "start_slot_bytes") for row in rows),
        "control_raw_exact_bytes": sum(int_value(row, "control_raw_exact_bytes") for row in rows),
        "start_raw_exact_bytes": sum(int_value(row, "start_raw_exact_bytes") for row in rows),
        "control_high_exact_bytes": sum(int_value(row, "control_high_exact_bytes") for row in rows),
        "start_high_exact_bytes": sum(int_value(row, "start_high_exact_bytes") for row in rows),
        "issue_rows": issue_rows + len(fixture_issues),
    }
    return summary_seed, rows, entries


def build_groups(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("gradient_class", ""))].append(row)
    output: list[dict[str, object]] = []
    for key, group in grouped.items():
        output.append(
            {
                "rank": 0,
                "group_kind": "gradient_class",
                "group_key": key,
                "rows": len(group),
                "bytes": sum(int_value(row, "length") for row in group),
                "control_anchor_rows": sum(1 for row in group if str(row.get("control_ref_offset", "")) != ""),
                "control_slot_bytes": sum(int_value(row, "control_slot_bytes") for row in group),
                "control_raw_exact_bytes": sum(int_value(row, "control_raw_exact_bytes") for row in group),
                "control_high_exact_bytes": sum(int_value(row, "control_high_exact_bytes") for row in group),
                "sample_pcx": group[0].get("pcx_name", ""),
                "sample_frontier_id": group[0].get("frontier_id", ""),
                "verdict": "state_slots_present" if sum(int_value(row, "control_slot_bytes") for row in group) else "missing_state_slots",
            }
        )
    output.sort(key=lambda row: (-int_value(row, "bytes"), str(row["group_key"])))
    for index, row in enumerate(output, start=1):
        row["rank"] = index
    return output


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
    fixture_rows: list[dict[str, str]],
) -> tuple[
    dict[str, object],
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
]:
    summary_seed, rows, entries = build_entries(input_rows, fixture_rows)
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
        "promotion_ready_bytes": 0,
    }
    groups = build_groups(rows)
    contexts = build_context_rows(entries, candidate_rows)
    return summary, rows, candidate_rows, contexts, groups


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
    groups: list[dict[str, object]],
    title: str,
) -> str:
    data_json = json.dumps(
        {"summary": summary, "rows": rows, "candidates": candidates, "contexts": contexts, "groups": groups},
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
  <div class="box"><div class="num">{summary['control_anchor_rows']}</div><div class="muted">control anchor rows</div></div>
  <div class="box"><div class="num">{summary['control_raw_exact_bytes']}/{summary['start_raw_exact_bytes']}</div><div class="muted">raw exact control/start</div></div>
  <div class="box"><div class="num">{summary['best_byte_correct_slots']}/{summary['best_byte_false_slots']}</div><div class="muted">best byte correct/false</div></div>
  <div class="box"><div class="num">{summary['best_step_correct_slots']}/{summary['best_step_false_slots']}</div><div class="muted">best step correct/false</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Rows</h2>{render_table(rows, ROW_FIELDNAMES)}</div>
<div class="panel"><h2>Groups</h2>{render_table(groups, GROUP_FIELDNAMES)}</div>
<div class="panel"><h2>Candidates</h2>{render_table(candidates, CANDIDATE_FIELDNAMES)}</div>
<div class="panel"><h2>Contexts</h2>{render_table(contexts, CONTEXT_FIELDNAMES)}</div>
<script type="application/json" id="gradient-state-opcode-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe source state/opcode contexts for gradient-like payloads.")
    parser.add_argument("--input-rows", type=Path, default=DEFAULT_INPUT_ROWS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Gradient Payload State Opcode")
    args = parser.parse_args()

    summary, rows, candidates, contexts, groups = build(read_csv(args.input_rows), read_csv(args.fixtures))
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "rows.csv", ROW_FIELDNAMES, rows)
    write_csv(args.output / "groups.csv", GROUP_FIELDNAMES, groups)
    write_csv(args.output / "candidates.csv", CANDIDATE_FIELDNAMES, candidates)
    write_csv(args.output / "contexts.csv", CONTEXT_FIELDNAMES, contexts)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, rows, candidates, contexts, groups, args.title))

    print(f"Target bytes: {summary['target_bytes']}")
    print(f"Control anchor rows: {summary['control_anchor_rows']}")
    print(f"Raw exact control/start: {summary['control_raw_exact_bytes']}/{summary['start_raw_exact_bytes']}")
    print(
        f"Best byte state: {summary['best_byte_context']} "
        f"{summary['best_byte_correct_slots']}/{summary['best_byte_false_slots']}"
    )
    print(
        f"Best step state: {summary['best_step_context']} "
        f"{summary['best_step_correct_slots']}/{summary['best_step_false_slots']}"
    )
    print(f"High baseline precision: {summary['best_high_baseline_precision']}")
    print(f"Source-state rejected: {summary['source_state_rejected']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
