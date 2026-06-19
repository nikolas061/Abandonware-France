#!/usr/bin/env python3
"""Probe local byte-context deny guards for shared 0x2700302b op4 emit-arg1."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
from itertools import combinations
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
from lolg_tex_large_shared_2700302b_op4_emitarg1_position_guard_probe import (
    DEFAULT_OUTPUT as DEFAULT_POSITION_GUARD_OUTPUT,
)
from score_te_raw_layouts import row_score


DEFAULT_OUTPUT = Path("output/tex_large_shared_2700302b_op4_emitarg1_local_context_guard_probe")
DEFAULT_OP4_EMITARG1_POSITION_GUARD_SUMMARY = DEFAULT_POSITION_GUARD_OUTPUT / "summary.csv"

SUMMARY_FIELDNAMES = [
    "scope",
    "segment_rows",
    "guard_rows",
    "variant_rows",
    "offset",
    "baseline_semantic",
    "baseline_avg_score",
    "baseline_max_score",
    "all_ops_guard_avg_score",
    "all_ops_guard_max_score",
    "best_guard_id",
    "best_avg_score",
    "best_max_score",
    "best_delta_vs_all_ops",
    "best_denied_atoms",
    "best_total_denied_events",
    "best_min_filled_ratio",
    "preview_rows",
    "sheet_path",
    "issue_rows",
    "local_context_guard_verdict",
    "next_action",
]

GUARD_FIELDNAMES = [
    "rank",
    "guard_id",
    "kind",
    "denied_atoms",
    "atom_count",
    "rows",
    "avg_score",
    "max_score",
    "min_score",
    "avg_delta_vs_all_ops",
    "max_delta_vs_all_ops",
    "min_filled_ratio",
    "total_op4_events",
    "total_op4_emit_events",
    "total_denied_events",
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
    "guard_id",
    "kind",
    "denied_atoms",
    "atom_count",
    "width",
    "height",
    "payload_bytes",
    "score",
    "score_delta_vs_all_ops",
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
    "denied_events",
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


def atom_specs() -> list[dict[str, object]]:
    specs = [
        {"atom_id": "arg2_03", "kind": "eq", "field": "arg2", "value": 0x03},
        {"atom_id": "arg2_arg3_20_00", "kind": "pair", "field_a": "arg2", "field_b": "arg3", "value_a": 0x20, "value_b": 0x00},
        {"atom_id": "arg2_arg3_20_1c", "kind": "pair", "field_a": "arg2", "field_b": "arg3", "value_a": 0x20, "value_b": 0x1C},
        {"atom_id": "arg2_arg3_37_c7", "kind": "pair", "field_a": "arg2", "field_b": "arg3", "value_a": 0x37, "value_b": 0xC7},
        {"atom_id": "arg2_arg3_00_02", "kind": "pair", "field_a": "arg2", "field_b": "arg3", "value_a": 0x00, "value_b": 0x02},
        {"atom_id": "arg2_05", "kind": "eq", "field": "arg2", "value": 0x05},
        {"atom_id": "prev1_22", "kind": "eq", "field": "prev1", "value": 0x22},
        {"atom_id": "arg3_0a", "kind": "eq", "field": "arg3", "value": 0x0A},
        {"atom_id": "prev1_7d", "kind": "eq", "field": "prev1", "value": 0x7D},
        {"atom_id": "arg4_7e", "kind": "eq", "field": "arg4", "value": 0x7E},
        {"atom_id": "prev1_arg1_00_58", "kind": "pair", "field_a": "prev1", "field_b": "arg1", "value_a": 0x00, "value_b": 0x58},
        {"atom_id": "prev1_arg1_12_85", "kind": "pair", "field_a": "prev1", "field_b": "arg1", "value_a": 0x12, "value_b": 0x85},
        {"atom_id": "arg1_arg2_68_69", "kind": "pair", "field_a": "arg1", "field_b": "arg2", "value_a": 0x68, "value_b": 0x69},
        {"atom_id": "arg4_48", "kind": "eq", "field": "arg4", "value": 0x48},
        {"atom_id": "arg2_arg3_00_20", "kind": "pair", "field_a": "arg2", "field_b": "arg3", "value_a": 0x00, "value_b": 0x20},
        {"atom_id": "arg1_arg2_32_00", "kind": "pair", "field_a": "arg1", "field_b": "arg2", "value_a": 0x32, "value_b": 0x00},
        {"atom_id": "arg1_arg2_40_20", "kind": "pair", "field_a": "arg1", "field_b": "arg2", "value_a": 0x40, "value_b": 0x20},
        {"atom_id": "arg1_arg2_53_00", "kind": "pair", "field_a": "arg1", "field_b": "arg2", "value_a": 0x53, "value_b": 0x00},
        {"atom_id": "arg1_op4", "kind": "class", "field": "arg1", "class": "op4"},
        {"atom_id": "arg2_arg3_22_e0", "kind": "pair", "field_a": "arg2", "field_b": "arg3", "value_a": 0x22, "value_b": 0xE0},
        {"atom_id": "prev1_arg1_e0_5c", "kind": "pair", "field_a": "prev1", "field_b": "arg1", "value_a": 0xE0, "value_b": 0x5C},
        {"atom_id": "prev1_arg1_01_81", "kind": "pair", "field_a": "prev1", "field_b": "arg1", "value_a": 0x01, "value_b": 0x81},
        {"atom_id": "prev1_arg1_00_50", "kind": "pair", "field_a": "prev1", "field_b": "arg1", "value_a": 0x00, "value_b": 0x50},
        {"atom_id": "prev2_prev1_22_e3", "kind": "pair", "field_a": "prev2", "field_b": "prev1", "value_a": 0x22, "value_b": 0xE3},
        {"atom_id": "prev2_prev1_26_e1", "kind": "pair", "field_a": "prev2", "field_b": "prev1", "value_a": 0x26, "value_b": 0xE1},
        {"atom_id": "arg2_arg3_20_18", "kind": "pair", "field_a": "arg2", "field_b": "arg3", "value_a": 0x20, "value_b": 0x18},
        {"atom_id": "prev2_prev1_22_e0", "kind": "pair", "field_a": "prev2", "field_b": "prev1", "value_a": 0x22, "value_b": 0xE0},
        {"atom_id": "prev2_prev1_00_00", "kind": "pair", "field_a": "prev2", "field_b": "prev1", "value_a": 0x00, "value_b": 0x00},
        {"atom_id": "arg2_arg3_00_00", "kind": "pair", "field_a": "arg2", "field_b": "arg3", "value_a": 0x00, "value_b": 0x00},
        {"atom_id": "arg2_arg3_known_marker", "kind": "known_pair", "field_a": "arg2", "field_b": "arg3"},
        {"atom_id": "arg1_arg2_50_20", "kind": "pair", "field_a": "arg1", "field_b": "arg2", "value_a": 0x50, "value_b": 0x20},
    ]
    seen: set[str] = set()
    unique: list[dict[str, object]] = []
    for spec in specs:
        atom_id = str(spec["atom_id"])
        if atom_id in seen:
            continue
        seen.add(atom_id)
        unique.append(spec)
    return unique


def class_matches(class_name: str, value: int) -> bool:
    if value < 0:
        return False
    if class_name == "op4":
        return is_op4_candidate(value)
    return False


def atom_matches(atom: dict[str, object], context: dict[str, int]) -> bool:
    kind = str(atom["kind"])
    if kind == "eq":
        return context[str(atom["field"])] == int(atom["value"])
    if kind == "pair":
        return (
            context[str(atom["field_a"])],
            context[str(atom["field_b"])],
        ) == (int(atom["value_a"]), int(atom["value_b"]))
    if kind == "known_pair":
        return (context[str(atom["field_a"])], context[str(atom["field_b"])]) in KNOWN_MARKER_PAIRS
    if kind == "class":
        return class_matches(str(atom["class"]), context[str(atom["field"])])
    return False


def guard_specs(atoms: list[dict[str, object]]) -> list[dict[str, object]]:
    specs: list[dict[str, object]] = [
        {"guard_id": "all_ops", "kind": "all_ops", "atoms": []},
        {"guard_id": "emit_none", "kind": "none", "atoms": []},
    ]
    atom_ids = [str(atom["atom_id"]) for atom in atoms]
    for atom_id in atom_ids:
        specs.append({"guard_id": f"deny_{atom_id}", "kind": "deny_single", "atoms": [atom_id]})
    for left, right in combinations(atom_ids, 2):
        specs.append({"guard_id": f"deny_{left}__{right}", "kind": "deny_pair", "atoms": [left, right]})
    greedy_sequences = [
        ("seed", ["arg2_03", "prev1_7d", "arg1_arg2_40_20", "prev1_arg1_01_81"]),
        (
            "broad",
            ["arg2_03", "prev1_22", "arg3_0a", "arg4_7e", "prev2_prev1_26_e1", "arg1_arg2_53_00"],
        ),
        ("general", ["arg1_op4", "arg3_0a"]),
    ]
    for sequence_name, greedy_atoms in greedy_sequences:
        for index in range(1, len(greedy_atoms) + 1):
            selected = greedy_atoms[:index]
            specs.append(
                {
                    "guard_id": "deny_" + "__".join(selected),
                    "kind": f"deny_greedy_{sequence_name}_{index}",
                    "atoms": selected,
                }
            )
    seen: set[str] = set()
    unique: list[dict[str, object]] = []
    for spec in specs:
        guard_id = str(spec["guard_id"])
        if guard_id in seen:
            continue
        seen.add(guard_id)
        unique.append(spec)
    return unique


def should_emit(
    spec: dict[str, object],
    atoms_by_id: dict[str, dict[str, object]],
    context: dict[str, int],
) -> tuple[bool, bool]:
    kind = str(spec["kind"])
    if kind == "all_ops":
        return True, False
    if kind == "none":
        return False, True
    for atom_id in spec["atoms"]:  # type: ignore[union-attr]
        if atom_matches(atoms_by_id[str(atom_id)], context):
            return False, True
    return True, False


def decode_local_context_guard(
    payload: bytes,
    width: int,
    height: int,
    low: int,
    high: int,
    spec: dict[str, object],
    atoms_by_id: dict[str, dict[str, object]],
) -> tuple[bytes, dict[str, int | float]]:
    pixels = bytearray(width * height)
    x = y = pos = 0
    emitted = 0
    op4_events = 0
    op4_emit_events = 0
    denied_events = 0
    cmd20_sig_skips = 0
    cmd20_sig_noops = 0
    markerknown_skips = 0
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
                emit, denied = should_emit(spec, atoms_by_id, context)
                if denied:
                    denied_events += 1
                if emit:
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
        "denied_events": denied_events,
        "cmd20_sig_skips": cmd20_sig_skips,
        "cmd20_sig_noops": cmd20_sig_noops,
        "markerknown_skips": markerknown_skips,
    }


def baseline_pixels(payload: bytes, width: int, height: int, low: int, high: int) -> bytes:
    pixels, _stats = decode_custom(payload, width, height, low, high, 3, False, False, False)
    return pixels


def atom_list_text(spec: dict[str, object]) -> str:
    return "|".join(str(atom_id) for atom_id in spec["atoms"])  # type: ignore[union-attr]


def variant_id(row: dict[str, str], guard_id: str, offset: int) -> str:
    return f"{safe_name(row.get('archive_tag', ''))}__{safe_name(row.get('pcx_name', ''))}__off{offset}__{safe_name(guard_id)}"


def evaluate_variant(
    source: dict[str, str],
    payload: bytes,
    body_issues: list[str],
    width: int,
    height: int,
    offset: int,
    spec: dict[str, object],
    atoms_by_id: dict[str, dict[str, object]],
    low: int,
    high: int,
    all_ops_score: float,
) -> dict[str, str]:
    issues = list(body_issues)
    guard_id = str(spec["guard_id"])
    pixels = b""
    stats: dict[str, int | float] = {}
    if not payload:
        issues.append("empty_payload")
    if not issues:
        pixels, stats = decode_local_context_guard(payload, width, height, low, high, spec, atoms_by_id)
        if sum(1 for pixel in pixels if pixel) <= 0:
            issues.append("blank_preview")
    score = row_score(pixels, width, height) if pixels else 0.0
    return {
        "variant_id": variant_id(source, guard_id, offset),
        "segment_id": source.get("segment_id", ""),
        "archive": source.get("archive", ""),
        "archive_tag": source.get("archive_tag", ""),
        "pcx_name": source.get("pcx_name", ""),
        "offset": str(offset),
        "guard_id": guard_id,
        "kind": str(spec["kind"]),
        "denied_atoms": atom_list_text(spec),
        "atom_count": str(len(spec["atoms"])),  # type: ignore[arg-type]
        "width": str(width),
        "height": str(height),
        "payload_bytes": str(len(payload)),
        "score": f"{score:.4f}",
        "score_delta_vs_all_ops": f"{score - all_ops_score:.4f}" if pixels else "",
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
        "denied_events": str(stats.get("denied_events", "")),
        "cmd20_sig_skips": str(stats.get("cmd20_sig_skips", "")),
        "cmd20_sig_noops": str(stats.get("cmd20_sig_noops", "")),
        "markerknown_skips": str(stats.get("markerknown_skips", "")),
        "preview_path": "",
        "preview_exists": "no",
        "issues": ";".join(sorted(set(issues))),
    }


def guard_rows(rows: list[dict[str, str]], all_ops_guard_id: str) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        if row.get("issues"):
            continue
        grouped.setdefault(row.get("guard_id", ""), []).append(row)
    all_ops_group = grouped.get(all_ops_guard_id, [])
    all_ops_avg = (
        sum(float_text(row.get("score")) for row in all_ops_group) / max(1, len(all_ops_group))
        if all_ops_group
        else 0.0
    )
    output: list[dict[str, str]] = []
    for guard_id, group in grouped.items():
        scores = [float_text(row.get("score")) for row in group]
        all_deltas = [float_text(row.get("score_delta_vs_all_ops")) for row in group]
        fills = [float_text(row.get("filled_ratio")) for row in group]
        avg_score = sum(scores) / max(1, len(scores))
        avg_delta = sum(all_deltas) / max(1, len(all_deltas))
        verdict = "all_ops_reference" if guard_id == all_ops_guard_id else "candidate"
        if guard_id != all_ops_guard_id and avg_score < all_ops_avg - 0.00005:
            verdict = "improves_all_ops"
        elif guard_id != all_ops_guard_id and abs(avg_score - all_ops_avg) <= 0.00005:
            verdict = "matches_all_ops"
        elif guard_id != all_ops_guard_id:
            verdict = "no_improvement"
        output.append(
            {
                "rank": "",
                "guard_id": guard_id,
                "kind": group[0].get("kind", ""),
                "denied_atoms": group[0].get("denied_atoms", ""),
                "atom_count": group[0].get("atom_count", ""),
                "rows": str(len(group)),
                "avg_score": f"{avg_score:.4f}",
                "max_score": f"{max(scores) if scores else 0.0:.4f}",
                "min_score": f"{min(scores) if scores else 0.0:.4f}",
                "avg_delta_vs_all_ops": f"{avg_delta:.4f}",
                "max_delta_vs_all_ops": f"{max(all_deltas) if all_deltas else 0.0:.4f}",
                "min_filled_ratio": f"{min(fills) if fills else 0.0:.6f}",
                "total_op4_events": str(sum(int_value(row, "op4_events") for row in group)),
                "total_op4_emit_events": str(sum(int_value(row, "op4_emit_events") for row in group)),
                "total_denied_events": str(sum(int_value(row, "denied_events") for row in group)),
                "total_cmd20_sig_skips": str(sum(int_value(row, "cmd20_sig_skips") for row in group)),
                "total_markerknown_skips": str(sum(int_value(row, "markerknown_skips") for row in group)),
                "verdict": verdict,
            }
        )
    output.sort(key=lambda row: (float_text(row.get("avg_score")), float_text(row.get("max_score")), row.get("guard_id", "")))
    for rank, row in enumerate(output, 1):
        row["rank"] = str(rank)
    return output


def build_summary(
    variants: list[dict[str, str]],
    guards: list[dict[str, str]],
    segment_count: int,
    offset: int,
    baseline_semantic: str,
    baseline_avg_score: str,
    baseline_max_score: str,
    all_ops_guard_id: str,
    sheet_path: Path,
    max_non_noisy_score: float,
) -> dict[str, str]:
    best = guards[0] if guards else {}
    all_ops = next((row for row in guards if row.get("guard_id") == all_ops_guard_id), {})
    issue_rows = sum(1 for row in variants if row.get("issues"))
    preview_rows = sum(1 for row in variants if row.get("preview_exists") == "yes")
    improved = [row for row in guards if row.get("verdict") == "improves_all_ops"]
    if issue_rows:
        verdict = "shared_2700302b_op4_emitarg1_local_context_guard_probe_issues"
        next_action = "fix shared 0x2700302b op4 emit-arg1 local-context guard probe inputs"
    elif float_text(best.get("max_score")) <= max_non_noisy_score:
        verdict = "shared_2700302b_op4_emitarg1_local_context_guard_ready"
        next_action = (
            "review shared 0x2700302b op4 emit-arg1 local-context guard "
            f"{best.get('guard_id', '')} previews before decoder promotion"
        )
    elif improved:
        if "arg1_op4" in best.get("denied_atoms", ""):
            verdict = "shared_2700302b_op4_emitarg1_generalized_local_context_guard_improves"
            next_action = (
                "inspect shared 0x2700302b op4 emit-arg1 generalized local-context guard "
                f"{best.get('guard_id', '')}; avg score "
                f"{float_text(best.get('avg_score')):.4f} remains noisy"
            )
        else:
            verdict = "shared_2700302b_op4_emitarg1_local_context_guard_improves"
            next_action = (
                "generalize shared 0x2700302b op4 emit-arg1 local-context denylist beyond exact atom matches; "
                f"best guard {best.get('guard_id', '')} avg score "
                f"{float_text(best.get('avg_score')):.4f} remains noisy"
            )
    else:
        verdict = "shared_2700302b_op4_emitarg1_local_context_guard_no_improvement"
        next_action = "broaden shared 0x2700302b emitarg1 guard beyond local byte context"
    return {
        "scope": "total",
        "segment_rows": str(segment_count),
        "guard_rows": str(len(guards)),
        "variant_rows": str(len(variants)),
        "offset": str(offset),
        "baseline_semantic": baseline_semantic,
        "baseline_avg_score": baseline_avg_score,
        "baseline_max_score": baseline_max_score,
        "all_ops_guard_avg_score": all_ops.get("avg_score", ""),
        "all_ops_guard_max_score": all_ops.get("max_score", ""),
        "best_guard_id": best.get("guard_id", ""),
        "best_avg_score": best.get("avg_score", ""),
        "best_max_score": best.get("max_score", ""),
        "best_delta_vs_all_ops": best.get("avg_delta_vs_all_ops", ""),
        "best_denied_atoms": best.get("denied_atoms", ""),
        "best_total_denied_events": best.get("total_denied_events", ""),
        "best_min_filled_ratio": best.get("min_filled_ratio", ""),
        "preview_rows": str(preview_rows),
        "sheet_path": sheet_path.as_posix(),
        "issue_rows": str(issue_rows),
        "local_context_guard_verdict": verdict,
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
            f"{html.escape(row.get('guard_id', ''))}<br>"
            f"score {html.escape(row.get('score', ''))} delta {html.escape(row.get('score_delta_vs_all_ops', ''))}</figcaption>"
            "</figure>"
        )
    return "\n".join(cards)


def build_html(
    summary: dict[str, str],
    guards: list[dict[str, str]],
    variants: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "guards": guards, "variants": variants}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f"<a href=\"{html.escape(relative_href(path, output_dir))}\">{html.escape(label)}</a>"
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("guards.csv", output_dir / "guards.csv"),
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
  <div class="muted">Local byte-context deny guards for the shared 0x2700302b emit-arg1 op4 candidate.</div>
  <p>{links}</p>
</header>
<main>
  <section class="grid">
    <div class="stat"><div class="label">Guards</div><div class="value">{html.escape(summary['guard_rows'])}</div></div>
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
    <h2>Guards</h2>
    {render_table(guards, GUARD_FIELDNAMES)}
  </section>
  <section class="panel">
    <h2>Variants</h2>
    {render_table(variants, VARIANT_FIELDNAMES)}
  </section>
</main>
<script type="application/json" id="op4-emitarg1-local-context-guard-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def save_previews(
    variants: list[dict[str, str]],
    specs_by_id: dict[str, dict[str, object]],
    atoms_by_id: dict[str, dict[str, object]],
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
        spec = specs_by_id[row["guard_id"]]
        source, payload, width, height = segment_payloads[row["segment_id"]]
        pixels, _stats = decode_local_context_guard(payload, width, height, low, high, spec, atoms_by_id)
        image = render_indexed(pixels, width, height, palette)
        guard_dir = preview_dir / safe_name(row["guard_id"])
        guard_dir.mkdir(parents=True, exist_ok=True)
        preview_file = guard_dir / f"{safe_name(source.get('archive_tag', ''))}_{safe_name(source.get('pcx_name', ''))}.png"
        image.save(preview_file)
        row["preview_path"] = preview_file.as_posix()
        row["preview_exists"] = "yes"
        sheet_entries.append((f"{row['archive_tag']} {row['pcx_name']} off{offset} {row['guard_id']}", image))
    return sheet_entries


def write_report(args: argparse.Namespace) -> tuple[dict[str, str], list[dict[str, str]]]:
    args.output.mkdir(parents=True, exist_ok=True)
    op4_summary = read_summary(args.op4_semantics_summary)
    position_guard_summary = read_summary(args.op4_emitarg1_position_guard_summary)
    offset = int_value(op4_summary, "offset", 4)
    baseline_semantic = "skipargs3"
    all_ops_guard_id = "all_ops"
    palette = read_palette(args.palette)
    trace_rows = read_csv(args.trace_candidates)
    segment_rows = [row for row in read_csv(args.segments) if row.get("control_path") == TARGET_CONTROL_PATH]
    payload_cache: dict[Path, bytes] = {}
    segment_payloads: dict[str, tuple[dict[str, str], bytes, int, int]] = {}
    all_ops_scores: dict[str, float] = {}
    variants: list[dict[str, str]] = []
    atoms = atom_specs()
    atoms_by_id = {str(atom["atom_id"]): atom for atom in atoms}
    specs = guard_specs(atoms)
    specs_by_id = {str(spec["guard_id"]): spec for spec in specs}

    for source in segment_rows:
        body, issues = load_body(source, payload_cache, args.mix_entry_index)
        width, height = trace_dimensions(trace_rows, source.get("segment_id", ""), offset)
        if offset < 0 or offset >= len(body):
            issues = [*issues, "offset_out_of_body"]
            payload = b""
        else:
            payload = body[offset:]
        segment_payloads[source.get("segment_id", "")] = (source, payload, width, height)
        all_ops_pixels, _all_stats = decode_local_context_guard(
            payload,
            width,
            height,
            args.low,
            args.high,
            specs_by_id[all_ops_guard_id],
            atoms_by_id,
        )
        all_ops_scores[source.get("segment_id", "")] = float_text(row_score(all_ops_pixels, width, height))
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
                    atoms_by_id,
                    args.low,
                    args.high,
                    all_ops_scores[source.get("segment_id", "")],
                )
            )

    sheet_entries = save_previews(
        variants,
        specs_by_id,
        atoms_by_id,
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
    guards = guard_rows(variants, all_ops_guard_id)
    summary = build_summary(
        variants,
        guards,
        len(segment_rows),
        offset,
        baseline_semantic,
        position_guard_summary.get("baseline_avg_score", op4_summary.get("baseline_avg_score", "")),
        position_guard_summary.get("baseline_max_score", op4_summary.get("baseline_max_score", "")),
        all_ops_guard_id,
        sheet_path,
        args.max_non_noisy_score,
    )
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "guards.csv", GUARD_FIELDNAMES, guards)
    write_csv(args.output / "variants.csv", VARIANT_FIELDNAMES, variants)
    (args.output / "index.html").write_text(
        build_html(summary, guards, variants, args.output, args.title),
        encoding="utf-8",
    )
    return summary, guards


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe shared 0x2700302b op4 emit-arg1 local-context guards.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--op4-semantics-summary", type=Path, default=DEFAULT_OP4_SEMANTICS_SUMMARY)
    parser.add_argument(
        "--op4-emitarg1-position-guard-summary",
        type=Path,
        default=DEFAULT_OP4_EMITARG1_POSITION_GUARD_SUMMARY,
    )
    parser.add_argument("--segments", type=Path, default=DEFAULT_SEGMENTS)
    parser.add_argument("--trace-candidates", type=Path, default=DEFAULT_TRACE_CANDIDATES)
    parser.add_argument("-p", "--palette", type=Path, default=DEFAULT_PALETTE)
    parser.add_argument("--mix-entry-index", type=int, default=DEFAULT_MIX_ENTRY_INDEX)
    parser.add_argument("--low", type=lambda value: int(value, 0), default=0x30)
    parser.add_argument("--high", type=lambda value: int(value, 0), default=0xBF)
    parser.add_argument("--max-non-noisy-score", type=float, default=40.0)
    parser.add_argument("--preview-limit", type=int, default=32)
    parser.add_argument("--title", default="Lands of Lore II .tex Shared 0x2700302b OP4 Emit-Arg1 Local Context Guard Probe")
    args = parser.parse_args()

    summary, _guards = write_report(args)
    print(f"Segments: {summary['segment_rows']}")
    print(f"Guard rows: {summary['guard_rows']}")
    print(f"Best guard: {summary['best_guard_id']}")
    print(f"Best avg score: {summary['best_avg_score']}")
    print(f"Best denied atoms: {summary['best_denied_atoms']}")
    print(f"All ops avg score: {summary['all_ops_guard_avg_score']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"Local context guard verdict: {summary['local_context_guard_verdict']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
