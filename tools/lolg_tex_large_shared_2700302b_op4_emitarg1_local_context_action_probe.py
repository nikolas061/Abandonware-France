#!/usr/bin/env python3
"""Probe actions for generalized shared 0x2700302b op4 emit-arg1 guards."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
from pathlib import Path

from PIL import Image

from export_shp import read_palette
from export_te_span_previews import make_sheet, render_indexed
from lolg_tex_large_body_control_grammar_probe import int_value, write_csv
from lolg_tex_large_shared_2700302b_op4_argument_semantics_probe import (
    KNOWN_MARKER_PAIRS,
    advance,
    decode_custom,
    is_cmd20_signature,
    is_op4_candidate,
    put_pixel,
    safe_name,
    trace_dimensions,
    visible_ratio,
)
from lolg_tex_large_shared_2700302b_op4_emitarg1_guard_probe import (
    DEFAULT_MIX_ENTRY_INDEX,
    DEFAULT_OP4_SEMANTICS_SUMMARY,
    DEFAULT_PALETTE,
    DEFAULT_SEGMENTS,
    DEFAULT_TRACE_CANDIDATES,
    TARGET_CONTROL_PATH,
    float_text,
    load_body,
    read_summary,
)
from lolg_tex_large_shared_2700302b_op4_emitarg1_local_context_guard_probe import (
    DEFAULT_OUTPUT as DEFAULT_LOCAL_CONTEXT_GUARD_OUTPUT,
)
from score_te_raw_layouts import row_score


DEFAULT_OUTPUT = Path("output/tex_large_shared_2700302b_op4_emitarg1_local_context_action_probe")
DEFAULT_OP4_EMITARG1_LOCAL_CONTEXT_GUARD_SUMMARY = DEFAULT_LOCAL_CONTEXT_GUARD_OUTPUT / "summary.csv"

SUMMARY_FIELDNAMES = [
    "scope",
    "segment_rows",
    "action_rows",
    "variant_rows",
    "offset",
    "baseline_semantic",
    "baseline_avg_score",
    "baseline_max_score",
    "all_ops_guard_avg_score",
    "all_ops_guard_max_score",
    "local_context_guard_avg_score",
    "local_context_guard_max_score",
    "best_action_id",
    "best_condition_id",
    "best_action",
    "best_avg_score",
    "best_max_score",
    "best_delta_vs_all_ops",
    "best_delta_vs_local_context",
    "best_total_guard_events",
    "best_total_action_emit_events",
    "best_min_filled_ratio",
    "preview_rows",
    "sheet_path",
    "issue_rows",
    "action_verdict",
    "next_action",
]

ACTION_FIELDNAMES = [
    "rank",
    "action_id",
    "condition_id",
    "action",
    "rows",
    "avg_score",
    "max_score",
    "min_score",
    "avg_delta_vs_all_ops",
    "avg_delta_vs_local_context",
    "max_delta_vs_all_ops",
    "min_filled_ratio",
    "total_op4_events",
    "total_op4_emit_events",
    "total_guard_events",
    "total_action_emit_events",
    "total_cmd20_sig_skips",
    "total_markerknown_skips",
    "verdict",
]

VARIANT_FIELDNAMES = [
    "variant_id",
    "segment_id",
    "archive",
    "archive_tag",
    "pcx_name",
    "offset",
    "action_id",
    "condition_id",
    "action",
    "width",
    "height",
    "payload_bytes",
    "score",
    "score_delta_vs_all_ops",
    "score_delta_vs_local_context",
    "filled_ratio",
    "visible_pixels",
    "unique_colors",
    "emitted",
    "overdraw",
    "final_x",
    "final_y",
    "final_pos",
    "op4_events",
    "op4_emit_events",
    "guard_events",
    "action_emit_events",
    "cmd20_sig_skips",
    "cmd20_sig_noops",
    "markerknown_skips",
    "preview_path",
    "preview_exists",
    "issues",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    try:
        return os.path.relpath(Path(path_text), base_dir)
    except ValueError:
        return str(path_text)


def byte_at(payload: bytes, index: int) -> int:
    return payload[index] if 0 <= index < len(payload) else -1


def event_context(payload: bytes, pos_after_opcode: int, stream_pos: int, opcode: int) -> dict[str, int]:
    return {
        "opcode": opcode,
        "prev2": byte_at(payload, stream_pos - 2),
        "prev1": byte_at(payload, stream_pos - 1),
        "arg1": byte_at(payload, pos_after_opcode),
        "arg2": byte_at(payload, pos_after_opcode + 1),
        "arg3": byte_at(payload, pos_after_opcode + 2),
        "arg4": byte_at(payload, pos_after_opcode + 3),
    }


def exact6_condition(context: dict[str, int]) -> bool:
    return (
        context["arg2"] == 0x03
        or context["prev1"] == 0x22
        or context["arg3"] == 0x0A
        or context["arg4"] == 0x7E
        or (context["prev2"], context["prev1"]) == (0x26, 0xE1)
        or (context["arg1"], context["arg2"]) == (0x53, 0x00)
    )


EXTENDED_SPLIT_RULES: tuple[tuple[str, str], ...] = (
    ("arg2_03", "deny_skip1"),
    ("arg2_05", "deny_skip1"),
    ("prev1_22", "emit_arg2_skip1"),
    ("prev1_7d", "deny_skip6"),
    ("arg2_arg3_37_c7", "deny_skip4"),
    ("prev2_prev1_26_e1", "deny_skip6"),
    ("arg2_arg3_00_02", "deny_skip6"),
    ("arg1_38", "deny_skip4"),
    ("arg1_43", "deny_skip6"),
    ("arg4_43", "deny_skip6"),
    ("arg1_30", "deny_skip2"),
    ("arg1_32", "deny_skip1"),
)


def generalized_condition(context: dict[str, int]) -> bool:
    return is_op4_candidate(context["arg1"]) or context["arg3"] == 0x0A


def extra_condition_passes(condition_id: str, context: dict[str, int]) -> bool:
    if condition_id == "arg2_03":
        return context["arg2"] == 0x03
    if condition_id == "arg2_05":
        return context["arg2"] == 0x05
    if condition_id == "prev1_22":
        return context["prev1"] == 0x22
    if condition_id == "prev1_7d":
        return context["prev1"] == 0x7D
    if condition_id == "arg2_arg3_37_c7":
        return (context["arg2"], context["arg3"]) == (0x37, 0xC7)
    if condition_id == "prev2_prev1_26_e1":
        return (context["prev2"], context["prev1"]) == (0x26, 0xE1)
    if condition_id == "arg2_arg3_00_02":
        return (context["arg2"], context["arg3"]) == (0x00, 0x02)
    if condition_id == "arg1_38":
        return context["arg1"] == 0x38
    if condition_id == "arg1_43":
        return context["arg1"] == 0x43
    if condition_id == "arg4_43":
        return context["arg4"] == 0x43
    if condition_id == "arg1_30":
        return context["arg1"] == 0x30
    if condition_id == "arg1_32":
        return context["arg1"] == 0x32
    return False


def extended_split_count(condition_id: str) -> int:
    if not condition_id.startswith("extended_split_greedy_"):
        return 0
    try:
        return int(condition_id.rsplit("_", 1)[1])
    except ValueError:
        return 0


def extended_split_action(condition_id: str, context: dict[str, int]) -> str:
    if context["arg3"] == 0x0A:
        return "deny_skip5"
    if is_op4_candidate(context["arg1"]):
        return "emit_arg2_reprocess"
    for extra_condition_id, action in EXTENDED_SPLIT_RULES[: extended_split_count(condition_id)]:
        if extra_condition_passes(extra_condition_id, context):
            return action
    return ""


def condition_passes(condition_id: str, context: dict[str, int]) -> bool:
    if condition_id == "none":
        return False
    if condition_id == "arg1_op4":
        return is_op4_candidate(context["arg1"])
    if condition_id == "arg3_0a":
        return context["arg3"] == 0x0A
    if condition_id == "arg1_op4_or_arg3_0a":
        return generalized_condition(context)
    if condition_id == "exact6":
        return exact6_condition(context)
    if condition_id == "split_arg1_op4_arg3_0a":
        return is_op4_candidate(context["arg1"]) or context["arg3"] == 0x0A
    if condition_id.startswith("extended_split_greedy_"):
        return bool(extended_split_action(condition_id, context))
    return False


def action_specs() -> list[dict[str, object]]:
    specs: list[dict[str, object]] = [{"action_id": "all_ops", "condition_id": "none", "action": "all_ops"}]
    conditions = ("arg1_op4_or_arg3_0a", "arg1_op4", "arg3_0a", "exact6")
    actions = (
        "deny_reprocess",
        "deny_skip1",
        "deny_skip2",
        "deny_skip3",
        "deny_skip4",
        "deny_skip5",
        "deny_skip6",
        "emit_arg2_reprocess",
        "emit_arg2_skip1",
        "emit_arg3_reprocess",
        "advance_code",
        "advance_arg2",
    )
    for condition_id in conditions:
        for action in actions:
            specs.append(
                {
                    "action_id": f"{condition_id}__{action}",
                    "condition_id": condition_id,
                    "action": action,
                }
            )
    split_actions = (
        "deny_reprocess",
        "deny_skip1",
        "deny_skip2",
        "deny_skip3",
        "deny_skip4",
        "deny_skip5",
        "deny_skip6",
        "emit_arg2_reprocess",
        "emit_arg2_skip1",
        "emit_arg3_reprocess",
    )
    for arg1_action in split_actions:
        for arg3_action in split_actions:
            for priority in ("arg1", "arg3"):
                specs.append(
                    {
                        "action_id": f"split_arg1_{arg1_action}__arg3_{arg3_action}__both_{priority}",
                        "condition_id": "split_arg1_op4_arg3_0a",
                        "action": f"split|{arg1_action}|{arg3_action}|{priority}",
                    }
                )
    for index in range(1, len(EXTENDED_SPLIT_RULES) + 1):
        specs.append(
            {
                "action_id": f"extended_split_greedy_{index}",
                "condition_id": f"extended_split_greedy_{index}",
                "action": "extended_split",
            }
        )
    return specs


def decode_action(
    payload: bytes,
    width: int,
    height: int,
    low: int,
    high: int,
    spec: dict[str, object],
) -> tuple[bytes, dict[str, int | float]]:
    pixels = bytearray(width * height)
    x = y = pos = 0
    emitted = 0
    op4_events = 0
    op4_emit_events = 0
    guard_events = 0
    action_emit_events = 0
    cmd20_sig_skips = 0
    cmd20_sig_noops = 0
    markerknown_skips = 0
    condition_id = str(spec["condition_id"])
    base_action = str(spec["action"])
    while pos < len(payload) and y < height:
        stream_pos = pos
        byte = payload[pos]
        pos += 1
        if pos < len(payload) and (byte, payload[pos]) in KNOWN_MARKER_PAIRS:
            markerknown_skips += 1
            pos += 1
            continue
        if byte == 0x20:
            arg1 = payload[pos] if pos < len(payload) else None
            arg2 = payload[pos + 1] if pos + 1 < len(payload) else None
            arg3 = payload[pos + 2] if pos + 2 < len(payload) else None
            if is_cmd20_signature(arg1, arg2, arg3):
                cmd20_sig_skips += 1
                pos = min(len(payload), pos + 4)
            else:
                cmd20_sig_noops += 1
            continue
        if is_op4_candidate(byte):
            op4_events += 1
            if pos < len(payload) and low <= payload[pos] <= high:
                context = event_context(payload, pos, stream_pos, byte)
                selected_action = base_action
                if base_action == "extended_split":
                    selected_action = extended_split_action(condition_id, context)
                    guarded = bool(selected_action)
                else:
                    guarded = base_action != "all_ops" and condition_passes(condition_id, context)
                if guarded:
                    guard_events += 1
                    if selected_action.startswith("split|"):
                        _split, arg1_action, arg3_action, priority = selected_action.split("|", 3)
                        arg1_match = is_op4_candidate(context["arg1"])
                        arg3_match = context["arg3"] == 0x0A
                        if arg1_match and arg3_match:
                            selected_action = arg1_action if priority == "arg1" else arg3_action
                        elif arg1_match:
                            selected_action = arg1_action
                        elif arg3_match:
                            selected_action = arg3_action
                    if selected_action.startswith("deny_skip"):
                        pos = min(len(payload), pos + int(selected_action.replace("deny_skip", "")))
                    elif selected_action == "emit_arg2_reprocess" and pos + 1 < len(payload) and low <= payload[pos + 1] <= high:
                        put_pixel(pixels, width, height, x, y, payload[pos + 1])
                        x, y = advance(x, y, width, 1)
                        emitted += 1
                        action_emit_events += 1
                    elif selected_action == "emit_arg2_skip1" and pos + 1 < len(payload) and low <= payload[pos + 1] <= high:
                        put_pixel(pixels, width, height, x, y, payload[pos + 1])
                        x, y = advance(x, y, width, 1)
                        emitted += 1
                        action_emit_events += 1
                        pos = min(len(payload), pos + 1)
                    elif selected_action == "emit_arg3_reprocess" and pos + 2 < len(payload) and low <= payload[pos + 2] <= high:
                        put_pixel(pixels, width, height, x, y, payload[pos + 2])
                        x, y = advance(x, y, width, 1)
                        emitted += 1
                        action_emit_events += 1
                    elif selected_action == "advance_code":
                        x, y = advance(x, y, width, (byte - 0x40) // 4)
                    elif selected_action == "advance_arg2" and pos + 1 < len(payload):
                        x, y = advance(x, y, width, payload[pos + 1])
                else:
                    put_pixel(pixels, width, height, x, y, payload[pos])
                    x, y = advance(x, y, width, 1)
                    emitted += 1
                    op4_emit_events += 1
            continue
        if low <= byte <= high:
            put_pixel(pixels, width, height, x, y, byte)
            x, y = advance(x, y, width, 1)
            emitted += 1
    return bytes(pixels), {
        "emitted": emitted,
        "overdraw": emitted / max(1, width * height),
        "final_x": x,
        "final_y": y,
        "final_pos": pos,
        "op4_events": op4_events,
        "op4_emit_events": op4_emit_events,
        "guard_events": guard_events,
        "action_emit_events": action_emit_events,
        "cmd20_sig_skips": cmd20_sig_skips,
        "cmd20_sig_noops": cmd20_sig_noops,
        "markerknown_skips": markerknown_skips,
    }


def baseline_pixels(payload: bytes, width: int, height: int, low: int, high: int) -> bytes:
    pixels, _stats = decode_custom(payload, width, height, low, high, 3, False, False, False)
    return pixels


def variant_id(row: dict[str, str], action_id: str, offset: int) -> str:
    return f"{safe_name(row.get('archive_tag', ''))}__{safe_name(row.get('pcx_name', ''))}__off{offset}__{safe_name(action_id)}"


def evaluate_variant(
    source: dict[str, str],
    payload: bytes,
    body_issues: list[str],
    width: int,
    height: int,
    offset: int,
    spec: dict[str, object],
    low: int,
    high: int,
    all_ops_score: float,
    local_context_score: float,
) -> dict[str, str]:
    issues = list(body_issues)
    action_id = str(spec["action_id"])
    pixels = b""
    stats: dict[str, int | float] = {}
    if not payload:
        issues.append("empty_payload")
    if not issues:
        pixels, stats = decode_action(payload, width, height, low, high, spec)
        if sum(1 for pixel in pixels if pixel) <= 0:
            issues.append("blank_preview")
    score = row_score(pixels, width, height) if pixels else 0.0
    return {
        "variant_id": variant_id(source, action_id, offset),
        "segment_id": source.get("segment_id", ""),
        "archive": source.get("archive", ""),
        "archive_tag": source.get("archive_tag", ""),
        "pcx_name": source.get("pcx_name", ""),
        "offset": str(offset),
        "action_id": action_id,
        "condition_id": str(spec["condition_id"]),
        "action": str(spec["action"]),
        "width": str(width),
        "height": str(height),
        "payload_bytes": str(len(payload)),
        "score": f"{score:.4f}",
        "score_delta_vs_all_ops": f"{score - all_ops_score:.4f}" if pixels else "",
        "score_delta_vs_local_context": f"{score - local_context_score:.4f}" if pixels else "",
        "filled_ratio": f"{visible_ratio(pixels):.6f}" if pixels else "0.000000",
        "visible_pixels": str(sum(1 for pixel in pixels if pixel)),
        "unique_colors": str(len(set(pixels)) if pixels else 0),
        "emitted": str(stats.get("emitted", "")),
        "overdraw": f"{float_text(stats.get('overdraw')):.6f}" if stats else "",
        "final_x": str(stats.get("final_x", "")),
        "final_y": str(stats.get("final_y", "")),
        "final_pos": str(stats.get("final_pos", "")),
        "op4_events": str(stats.get("op4_events", "")),
        "op4_emit_events": str(stats.get("op4_emit_events", "")),
        "guard_events": str(stats.get("guard_events", "")),
        "action_emit_events": str(stats.get("action_emit_events", "")),
        "cmd20_sig_skips": str(stats.get("cmd20_sig_skips", "")),
        "cmd20_sig_noops": str(stats.get("cmd20_sig_noops", "")),
        "markerknown_skips": str(stats.get("markerknown_skips", "")),
        "preview_path": "",
        "preview_exists": "no",
        "issues": ";".join(sorted(set(issues))),
    }


def action_rows(rows: list[dict[str, str]], all_ops_action_id: str, local_context_action_id: str) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        if row.get("issues"):
            continue
        grouped.setdefault(row.get("action_id", ""), []).append(row)
    all_ops_group = grouped.get(all_ops_action_id, [])
    local_context_group = grouped.get(local_context_action_id, [])
    all_ops_avg = sum(float_text(row.get("score")) for row in all_ops_group) / max(1, len(all_ops_group))
    local_context_avg = sum(float_text(row.get("score")) for row in local_context_group) / max(1, len(local_context_group))
    output: list[dict[str, str]] = []
    for action_id, group in grouped.items():
        scores = [float_text(row.get("score")) for row in group]
        all_deltas = [float_text(row.get("score_delta_vs_all_ops")) for row in group]
        local_deltas = [float_text(row.get("score_delta_vs_local_context")) for row in group]
        fills = [float_text(row.get("filled_ratio")) for row in group]
        avg_score = sum(scores) / max(1, len(scores))
        verdict = "all_ops_reference" if action_id == all_ops_action_id else "candidate"
        if action_id == local_context_action_id:
            verdict = "local_context_reference"
        elif action_id != all_ops_action_id and avg_score < local_context_avg - 0.00005:
            verdict = "improves_local_context"
        elif action_id != all_ops_action_id and avg_score < all_ops_avg - 0.00005:
            verdict = "improves_all_ops"
        elif action_id != all_ops_action_id:
            verdict = "no_improvement"
        output.append(
            {
                "rank": "",
                "action_id": action_id,
                "condition_id": group[0].get("condition_id", ""),
                "action": group[0].get("action", ""),
                "rows": str(len(group)),
                "avg_score": f"{avg_score:.4f}",
                "max_score": f"{max(scores) if scores else 0.0:.4f}",
                "min_score": f"{min(scores) if scores else 0.0:.4f}",
                "avg_delta_vs_all_ops": f"{sum(all_deltas) / max(1, len(all_deltas)):.4f}",
                "avg_delta_vs_local_context": f"{sum(local_deltas) / max(1, len(local_deltas)):.4f}",
                "max_delta_vs_all_ops": f"{max(all_deltas) if all_deltas else 0.0:.4f}",
                "min_filled_ratio": f"{min(fills) if fills else 0.0:.6f}",
                "total_op4_events": str(sum(int_value(row, "op4_events") for row in group)),
                "total_op4_emit_events": str(sum(int_value(row, "op4_emit_events") for row in group)),
                "total_guard_events": str(sum(int_value(row, "guard_events") for row in group)),
                "total_action_emit_events": str(sum(int_value(row, "action_emit_events") for row in group)),
                "total_cmd20_sig_skips": str(sum(int_value(row, "cmd20_sig_skips") for row in group)),
                "total_markerknown_skips": str(sum(int_value(row, "markerknown_skips") for row in group)),
                "verdict": verdict,
            }
        )
    output.sort(key=lambda row: (float_text(row.get("avg_score")), float_text(row.get("max_score")), row.get("action_id", "")))
    for rank, row in enumerate(output, 1):
        row["rank"] = str(rank)
    return output


def build_summary(
    variants: list[dict[str, str]],
    actions: list[dict[str, str]],
    segment_count: int,
    offset: int,
    baseline_semantic: str,
    baseline_avg_score: str,
    baseline_max_score: str,
    all_ops_action_id: str,
    local_context_action_id: str,
    sheet_path: Path,
    max_non_noisy_score: float,
) -> dict[str, str]:
    best = actions[0] if actions else {}
    all_ops = next((row for row in actions if row.get("action_id") == all_ops_action_id), {})
    local_context = next((row for row in actions if row.get("action_id") == local_context_action_id), {})
    issue_rows = sum(1 for row in variants if row.get("issues"))
    preview_rows = sum(1 for row in variants if row.get("preview_exists") == "yes")
    improved = [row for row in actions if row.get("verdict") == "improves_local_context"]
    if issue_rows:
        verdict = "shared_2700302b_op4_emitarg1_local_context_action_probe_issues"
        next_action = "fix shared 0x2700302b op4 emit-arg1 local-context action probe inputs"
    elif float_text(best.get("max_score")) <= max_non_noisy_score:
        verdict = "shared_2700302b_op4_emitarg1_local_context_action_ready"
        next_action = (
            "review shared 0x2700302b op4 emit-arg1 local-context action "
            f"{best.get('action_id', '')} previews before decoder promotion"
        )
    elif improved:
        if best.get("condition_id") == "split_arg1_op4_arg3_0a":
            verdict = "shared_2700302b_op4_emitarg1_local_context_split_action_improves"
            next_action = (
                "broaden shared 0x2700302b op4 split action semantics beyond arg1_op4/arg3_0a; "
                f"best action {best.get('action_id', '')} avg score "
                f"{float_text(best.get('avg_score')):.4f} remains noisy"
            )
        elif best.get("condition_id", "").startswith("extended_split_greedy_"):
            verdict = "shared_2700302b_op4_emitarg1_local_context_extended_split_action_improves"
            next_action = (
                "continue shared 0x2700302b op4 extended split context sweep; "
                f"best action {best.get('action_id', '')} avg score "
                f"{float_text(best.get('avg_score')):.4f} remains noisy"
            )
        else:
            verdict = "shared_2700302b_op4_emitarg1_local_context_action_improves"
            next_action = (
                "inspect shared 0x2700302b op4 emit-arg1 local-context action "
                f"{best.get('action_id', '')}; avg score {float_text(best.get('avg_score')):.4f} remains noisy"
            )
    else:
        verdict = "shared_2700302b_op4_emitarg1_local_context_action_no_improvement"
        next_action = "broaden shared 0x2700302b op4 emit-arg1 action semantics beyond local context"
    return {
        "scope": "total",
        "segment_rows": str(segment_count),
        "action_rows": str(len(actions)),
        "variant_rows": str(len(variants)),
        "offset": str(offset),
        "baseline_semantic": baseline_semantic,
        "baseline_avg_score": baseline_avg_score,
        "baseline_max_score": baseline_max_score,
        "all_ops_guard_avg_score": all_ops.get("avg_score", ""),
        "all_ops_guard_max_score": all_ops.get("max_score", ""),
        "local_context_guard_avg_score": local_context.get("avg_score", ""),
        "local_context_guard_max_score": local_context.get("max_score", ""),
        "best_action_id": best.get("action_id", ""),
        "best_condition_id": best.get("condition_id", ""),
        "best_action": best.get("action", ""),
        "best_avg_score": best.get("avg_score", ""),
        "best_max_score": best.get("max_score", ""),
        "best_delta_vs_all_ops": best.get("avg_delta_vs_all_ops", ""),
        "best_delta_vs_local_context": best.get("avg_delta_vs_local_context", ""),
        "best_total_guard_events": best.get("total_guard_events", ""),
        "best_total_action_emit_events": best.get("total_action_emit_events", ""),
        "best_min_filled_ratio": best.get("min_filled_ratio", ""),
        "preview_rows": str(preview_rows),
        "sheet_path": sheet_path.as_posix(),
        "issue_rows": str(issue_rows),
        "action_verdict": verdict,
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


def render_cards(rows: list[dict[str, str]], output_dir: Path, limit: int = 24) -> str:
    cards = []
    preview_rows = [row for row in rows if row.get("preview_exists") == "yes"]
    for row in sorted(preview_rows, key=lambda item: float_text(item.get("score")))[:limit]:
        preview = html.escape(relative_href(row.get("preview_path", ""), output_dir))
        cards.append(
            "<figure>"
            f"<img src=\"{preview}\" loading=\"lazy\" decoding=\"async\" alt=\"\">"
            f"<figcaption>{html.escape(row.get('archive_tag', ''))} / {html.escape(row.get('pcx_name', ''))}<br>"
            f"{html.escape(row.get('action_id', ''))}<br>"
            f"score {html.escape(row.get('score', ''))} delta {html.escape(row.get('score_delta_vs_local_context', ''))}</figcaption>"
            "</figure>"
        )
    return "\n".join(cards)


def build_html(
    summary: dict[str, str],
    actions: list[dict[str, str]],
    variants: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "actions": actions, "variants": variants}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f"<a href=\"{html.escape(relative_href(path, output_dir))}\">{html.escape(label)}</a>"
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("actions.csv", output_dir / "actions.csv"),
            ("variants.csv", output_dir / "variants.csv"),
            ("sheet.png", output_dir / "sheet.png"),
        )
    )
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
:root {{ color-scheme: dark; --bg: #101317; --panel: #181d23; --text: #e8edf2; --muted: #98a4b3; --accent: #74b8ff; --warn: #f0b35a; --ok: #6fd08c; }}
body {{ margin: 0; font-family: system-ui, sans-serif; background: var(--bg); color: var(--text); }}
header, main {{ max-width: 1450px; margin: 0 auto; padding: 24px; }}
h1 {{ margin: 0 0 8px; font-size: 26px; }}
h2 {{ margin: 0 0 12px; font-size: 18px; }}
.muted {{ color: var(--muted); }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin: 20px 0; }}
.stat, .panel, figure {{ background: var(--panel); border: 1px solid #29313b; border-radius: 8px; padding: 14px; }}
.label {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }}
.value {{ font-size: 24px; font-weight: 700; }}
.ok {{ color: var(--ok); }}
.warn {{ color: var(--warn); }}
a {{ color: var(--accent); text-decoration: none; margin-right: 10px; }}
figure {{ margin: 0; }}
figure img {{ width: 100%; height: 220px; object-fit: contain; image-rendering: pixelated; background: #050607; }}
figcaption {{ margin-top: 8px; color: var(--muted); font-size: 12px; overflow-wrap: anywhere; }}
table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
th, td {{ border-bottom: 1px solid #29313b; padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); position: sticky; top: 0; background: var(--panel); }}
td {{ max-width: 520px; overflow-wrap: anywhere; }}
section {{ margin-bottom: 20px; }}
</style>
</head>
<body>
<header>
  <h1>{html.escape(title)}</h1>
  <div class="muted">Alternative actions for generalized local-context op4 emit-arg1 guards.</div>
  <p>{links}</p>
</header>
<main>
  <section class="grid">
    <div class="stat"><div class="label">Actions</div><div class="value">{html.escape(summary['action_rows'])}</div></div>
    <div class="stat"><div class="label">Variants</div><div class="value">{html.escape(summary['variant_rows'])}</div></div>
    <div class="stat"><div class="label">Best Avg</div><div class="value warn">{html.escape(summary['best_avg_score'])}</div></div>
    <div class="stat"><div class="label">Issues</div><div class="value ok">{html.escape(summary['issue_rows'])}</div></div>
  </section>
  <section class="grid">{render_cards(variants, output_dir)}</section>
  <section class="panel">
    <h2>Summary</h2>
    {render_table([summary], SUMMARY_FIELDNAMES)}
  </section>
  <section class="panel">
    <h2>Actions</h2>
    {render_table(actions, ACTION_FIELDNAMES)}
  </section>
  <section class="panel">
    <h2>Variants</h2>
    {render_table(variants, VARIANT_FIELDNAMES)}
  </section>
</main>
<script type="application/json" id="op4-emitarg1-local-context-action-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def save_previews(
    variants: list[dict[str, str]],
    specs_by_id: dict[str, dict[str, object]],
    segment_payloads: dict[str, tuple[dict[str, str], bytes, int, int]],
    offset: int,
    low: int,
    high: int,
    output_dir: Path,
    palette: list[tuple[int, int, int]],
    preview_limit: int,
) -> list[tuple[str, Image.Image]]:
    preview_dir = output_dir / "previews"
    top_rows = [
        row
        for row in sorted(variants, key=lambda item: (float_text(item.get("score")), item.get("variant_id", "")))
        if not row.get("issues")
    ][:preview_limit]
    sheet_entries: list[tuple[str, Image.Image]] = []
    for row in top_rows:
        spec = specs_by_id[row["action_id"]]
        source, payload, width, height = segment_payloads[row["segment_id"]]
        pixels, _stats = decode_action(payload, width, height, low, high, spec)
        image = render_indexed(pixels, width, height, palette)
        action_dir = preview_dir / safe_name(row["action_id"])
        action_dir.mkdir(parents=True, exist_ok=True)
        preview_file = action_dir / f"{safe_name(source.get('archive_tag', ''))}_{safe_name(source.get('pcx_name', ''))}.png"
        image.save(preview_file)
        row["preview_path"] = preview_file.as_posix()
        row["preview_exists"] = "yes"
        sheet_entries.append((f"{row['archive_tag']} {row['pcx_name']} off{offset} {row['action_id']}", image))
    return sheet_entries


def write_report(args: argparse.Namespace) -> tuple[dict[str, str], list[dict[str, str]]]:
    args.output.mkdir(parents=True, exist_ok=True)
    op4_summary = read_summary(args.op4_semantics_summary)
    local_context_summary = read_summary(args.op4_emitarg1_local_context_guard_summary)
    offset = int_value(op4_summary, "offset", 4)
    baseline_semantic = "skipargs3"
    all_ops_action_id = "all_ops"
    local_context_action_id = "arg1_op4_or_arg3_0a__deny_reprocess"
    palette = read_palette(args.palette)
    trace_rows = read_csv(args.trace_candidates)
    segment_rows = [row for row in read_csv(args.segments) if row.get("control_path") == TARGET_CONTROL_PATH]
    payload_cache: dict[Path, bytes] = {}
    segment_payloads: dict[str, tuple[dict[str, str], bytes, int, int]] = {}
    all_ops_scores: dict[str, float] = {}
    local_context_scores: dict[str, float] = {}
    variants: list[dict[str, str]] = []
    specs = action_specs()
    specs_by_id = {str(spec["action_id"]): spec for spec in specs}

    for source in segment_rows:
        body, issues = load_body(source, payload_cache, args.mix_entry_index)
        width, height = trace_dimensions(trace_rows, source.get("segment_id", ""), offset)
        if offset < 0 or offset >= len(body):
            issues = [*issues, "offset_out_of_body"]
            payload = b""
        else:
            payload = body[offset:]
        segment_payloads[source.get("segment_id", "")] = (source, payload, width, height)
        all_ops_pixels, _all_stats = decode_action(payload, width, height, args.low, args.high, specs_by_id[all_ops_action_id])
        local_context_pixels, _local_stats = decode_action(
            payload,
            width,
            height,
            args.low,
            args.high,
            specs_by_id[local_context_action_id],
        )
        all_ops_scores[source.get("segment_id", "")] = float_text(row_score(all_ops_pixels, width, height))
        local_context_scores[source.get("segment_id", "")] = float_text(row_score(local_context_pixels, width, height))
        for spec in specs:
            variants.append(
                evaluate_variant(
                    source,
                    payload,
                    issues,
                    width,
                    height,
                    offset,
                    spec,
                    args.low,
                    args.high,
                    all_ops_scores[source.get("segment_id", "")],
                    local_context_scores[source.get("segment_id", "")],
                )
            )

    sheet_entries = save_previews(
        variants,
        specs_by_id,
        segment_payloads,
        offset,
        args.low,
        args.high,
        args.output,
        palette,
        args.preview_limit,
    )
    sheet_path = args.output / "sheet.png"
    make_sheet(sheet_entries, sheet_path, 4, 180)
    actions = action_rows(variants, all_ops_action_id, local_context_action_id)
    summary = build_summary(
        variants,
        actions,
        len(segment_rows),
        offset,
        baseline_semantic,
        local_context_summary.get("baseline_avg_score", op4_summary.get("baseline_avg_score", "")),
        local_context_summary.get("baseline_max_score", op4_summary.get("baseline_max_score", "")),
        all_ops_action_id,
        local_context_action_id,
        sheet_path,
        args.max_non_noisy_score,
    )
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "actions.csv", ACTION_FIELDNAMES, actions)
    write_csv(args.output / "variants.csv", VARIANT_FIELDNAMES, variants)
    (args.output / "index.html").write_text(
        build_html(summary, actions, variants, args.output, args.title),
        encoding="utf-8",
    )
    return summary, actions


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe shared 0x2700302b op4 emit-arg1 local-context actions.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--op4-semantics-summary", type=Path, default=DEFAULT_OP4_SEMANTICS_SUMMARY)
    parser.add_argument(
        "--op4-emitarg1-local-context-guard-summary",
        type=Path,
        default=DEFAULT_OP4_EMITARG1_LOCAL_CONTEXT_GUARD_SUMMARY,
    )
    parser.add_argument("--segments", type=Path, default=DEFAULT_SEGMENTS)
    parser.add_argument("--trace-candidates", type=Path, default=DEFAULT_TRACE_CANDIDATES)
    parser.add_argument("-p", "--palette", type=Path, default=DEFAULT_PALETTE)
    parser.add_argument("--mix-entry-index", type=int, default=DEFAULT_MIX_ENTRY_INDEX)
    parser.add_argument("--low", type=lambda value: int(value, 0), default=0x30)
    parser.add_argument("--high", type=lambda value: int(value, 0), default=0xBF)
    parser.add_argument("--max-non-noisy-score", type=float, default=40.0)
    parser.add_argument("--preview-limit", type=int, default=32)
    parser.add_argument("--title", default="Lands of Lore II .tex Shared 0x2700302b OP4 Emit-Arg1 Local Context Action Probe")
    args = parser.parse_args()

    summary, _actions = write_report(args)
    print(f"Segments: {summary['segment_rows']}")
    print(f"Action rows: {summary['action_rows']}")
    print(f"Best action: {summary['best_action_id']}")
    print(f"Best avg score: {summary['best_avg_score']}")
    print(f"Local context avg score: {summary['local_context_guard_avg_score']}")
    print(f"All ops avg score: {summary['all_ops_guard_avg_score']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"Action verdict: {summary['action_verdict']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
