#!/usr/bin/env python3
"""Split structural compact-control residuals by value family and source evidence."""

from __future__ import annotations

import argparse
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_opcode_probe import relative_href, write_csv
from lolg_tex_gap_decoder_frontier80_clean_structural_nonzero_producer_probe import (
    DEFAULT_CLEAN_FIXTURES,
    DEFAULT_MANIFEST,
    DEFAULT_RUNS,
    int_value,
    load_target_payloads,
    ratio,
    read_csv,
    target_id as make_target_id,
    value_class,
)
from lolg_tex_gap_decoder_frontier80_clean_structural_nonzero_rle_delta_parser_probe import (
    build_token_rows,
)
from lolg_tex_gap_decoder_frontier80_clean_structural_nonzero_control_bridge_probe import (
    build_control_gap_rows,
    ordered_strong_bridge,
)
from lolg_tex_gap_decoder_frontier80_clean_structural_nonzero_compact_control_grammar_probe import (
    build_token_rows_for_gap,
    int_field,
    replay_from_seed,
)


DEFAULT_OUTPUT = Path(
    "output/tex_gap_decoder_frontier80_clean_structural_nonzero_compact_control_residual_value_family_probe"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "selected_target_runs",
    "selected_target_bytes",
    "grammar_token_rows",
    "grammar_token_bytes",
    "residual_token_rows",
    "residual_token_bytes",
    "family_rows",
    "no_control_gap_token_rows",
    "no_control_gap_bytes",
    "local_control_gap_token_rows",
    "local_control_gap_bytes",
    "local_extended_candidate_rows",
    "near_window_candidate_rows",
    "full_segment_candidate_rows",
    "low_delta_sequence_bytes",
    "control_high_bytes",
    "dark_low_bytes",
    "mid_payload_bytes",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

FAMILY_FIELDNAMES = [
    "value_family",
    "token_rows",
    "token_bytes",
    "target_ids",
    "pcx_names",
    "gaps",
    "no_control_gap_rows",
    "local_control_gap_rows",
    "local_extended_candidate_rows",
    "near_window_candidate_rows",
    "full_segment_candidate_rows",
    "value_classes",
    "values_hex",
    "sample_target_id",
    "sample_token_index",
    "verdict",
    "next_probe",
]

RESIDUAL_FIELDNAMES = [
    "target_id",
    "rank",
    "pcx_name",
    "frontier_id",
    "span_index",
    "gap_index",
    "token_index",
    "token_type",
    "run_offset_start",
    "run_offset_end",
    "length",
    "target_hex",
    "value_family",
    "value_classes",
    "values_hex",
    "control_gap_bytes",
    "control_gap_status",
    "local_transform",
    "local_source_delta",
    "local_source_value_hex",
    "local_source_gap_offset",
    "near_transform",
    "near_source_delta",
    "near_source_segment_offset",
    "near_distance_to_gap",
    "full_segment_transform",
    "full_segment_source_delta",
    "full_segment_offset",
    "full_segment_distance_to_gap",
    "full_segment_occurrences",
    "previous_covered_token_index",
    "previous_covered_transform",
    "next_covered_token_index",
    "next_covered_transform",
    "target_context_hex",
    "control_gap_head_hex",
    "control_gap_tail_hex",
    "verdict",
    "next_probe",
]

CANDIDATE_FIELDNAMES = [
    "target_id",
    "gap_index",
    "token_index",
    "scope",
    "source_transform",
    "source_delta",
    "source_value_hex",
    "source_offset",
    "source_segment_offset",
    "source_occurrences",
    "distance_to_gap",
    "source_context_hex",
]


def select_targets(run_rows: list[dict[str, str]], *, min_length: int, limit: int) -> list[dict[str, str]]:
    targets = [
        {**row, "target_id": make_target_id(row)}
        for row in run_rows
        if row.get("run_class") == "nonzero" and int_value(row, "length") >= min_length
    ]
    targets.sort(
        key=lambda row: (
            -int_value(row, "length"),
            row.get("pcx_name", ""),
            int_value(row, "start"),
        )
    )
    return targets[:limit] if limit > 0 else targets


def hex_byte(value: int | None) -> str:
    return "" if value is None else f"0x{value:02x}"


def token_chunk(payload: dict[str, object], token: dict[str, str]) -> bytes:
    data = payload.get("data", b"")
    if not isinstance(data, bytes):
        return b""
    start = int_field(token, "run_offset_start", -1)
    end = int_field(token, "run_offset_end", -1)
    if start < 0 or end < start or end > len(data):
        return b""
    return data[start:end]


def find_offsets(source: bytes, chunk: bytes, *, limit: int = 256) -> tuple[list[int], int]:
    if not source or not chunk or len(chunk) > len(source):
        return [], 0
    offsets: list[int] = []
    count = 0
    offset = source.find(chunk)
    while offset >= 0:
        count += 1
        if len(offsets) < limit:
            offsets.append(offset)
        offset = source.find(chunk, offset + 1)
    return offsets, count


def find_value_offsets(source: bytes, value: int, *, limit: int = 256) -> tuple[list[int], int]:
    offsets = [offset for offset, current in enumerate(source) if current == value]
    return offsets[:limit], len(offsets)


def distance_to_interval(offset: int, length: int, start: int, end: int) -> int:
    if offset + length <= start:
        return start - (offset + length)
    if offset >= end:
        return offset - end
    return 0


def transform_name(delta: int) -> str:
    if delta == 0:
        return "exact_seed"
    if delta > 0:
        return f"plus{delta}_seed"
    return f"minus{abs(delta)}_seed"


def sorted_deltas(max_delta: int) -> list[int]:
    return sorted(range(-max_delta, max_delta + 1), key=lambda value: (abs(value), value))


def best_offset(offsets: list[int], *, length: int, gap_start: int, gap_end: int, base_offset: int) -> int:
    return min(
        offsets,
        key=lambda offset: (
            distance_to_interval(base_offset + offset, length, gap_start, gap_end),
            base_offset + offset,
        ),
    )


def source_context(source: bytes, offset: int, length: int) -> str:
    start = max(0, offset - 8)
    end = min(len(source), offset + max(1, length) + 8)
    return source[start:end].hex()


def candidate_rows_for_source(
    source: bytes,
    token: dict[str, str],
    chunk: bytes,
    *,
    scope: str,
    base_offset: int,
    gap_start: int,
    gap_end: int,
    max_delta: int,
) -> list[dict[str, str]]:
    if not chunk:
        return []
    rows: list[dict[str, str]] = []
    exact_offsets, exact_count = find_offsets(source, chunk)
    if len(chunk) > 1 and exact_offsets:
        offset = best_offset(
            exact_offsets,
            length=len(chunk),
            gap_start=gap_start,
            gap_end=gap_end,
            base_offset=base_offset,
        )
        rows.append(
            {
                "scope": scope,
                "source_transform": "exact_chunk",
                "source_delta": "0",
                "source_value_hex": hex_byte(chunk[0]),
                "source_offset": str(offset),
                "source_segment_offset": str(base_offset + offset),
                "source_occurrences": str(exact_count),
                "distance_to_gap": str(distance_to_interval(base_offset + offset, len(chunk), gap_start, gap_end)),
                "source_context_hex": source_context(source, offset, len(chunk)),
            }
        )

    seed = chunk[0]
    for delta in sorted_deltas(max_delta):
        source_value = (seed - delta) & 0xFF
        value_offsets, value_count = find_value_offsets(source, source_value)
        if not value_offsets:
            continue
        transformed_seed = (source_value + delta) & 0xFF
        replay = replay_from_seed(token, transformed_seed, len(chunk))
        if replay != chunk:
            continue
        offset = best_offset(
            value_offsets,
            length=1,
            gap_start=gap_start,
            gap_end=gap_end,
            base_offset=base_offset,
        )
        rows.append(
            {
                "scope": scope,
                "source_transform": transform_name(delta),
                "source_delta": str(delta),
                "source_value_hex": hex_byte(source_value),
                "source_offset": str(offset),
                "source_segment_offset": str(base_offset + offset),
                "source_occurrences": str(value_count),
                "distance_to_gap": str(distance_to_interval(base_offset + offset, 1, gap_start, gap_end)),
                "source_context_hex": source_context(source, offset, 1),
            }
        )
    return rows


def choose_candidate(rows: list[dict[str, str]]) -> dict[str, str] | None:
    if not rows:
        return None
    return min(
        rows,
        key=lambda row: (
            0 if row.get("source_transform") == "exact_chunk" else 1,
            abs(int_field(row, "source_delta")),
            int_field(row, "distance_to_gap"),
            int_field(row, "source_segment_offset"),
        ),
    )


def value_family(token: dict[str, str], chunk: bytes, control_gap_bytes: int) -> str:
    classes = {value_class(value) for value in chunk}
    if control_gap_bytes == 0:
        if token.get("token_type") == "delta" or classes <= {"dark_low", "other"}:
            return "zero_control_gap_low_delta"
        return "zero_control_gap_mixed"
    if "control_high" in classes:
        return "control_high_missing_local_seed"
    if token.get("token_type") == "delta":
        return "low_delta_sequence_missing_local_seed"
    if classes <= {"dark_low", "other"}:
        return "dark_low_missing_local_seed"
    if "mid_payload" in classes or "high_plateau" in classes:
        return "mid_payload_missing_local_seed"
    return "other_missing_local_seed"


def value_classes_text(chunk: bytes) -> str:
    return " ".join(sorted({value_class(value) for value in chunk}))


def values_hex_text(chunk: bytes) -> str:
    return " ".join(f"0x{value:02x}" for value in sorted(set(chunk)))


def neighbor_rows(
    grammar_rows: list[dict[str, str]],
    token_index: int,
) -> tuple[dict[str, str] | None, dict[str, str] | None]:
    covered = [
        row
        for row in grammar_rows
        if row.get("verdict") == "covered" and int_field(row, "token_index", -1) >= 0
    ]
    previous = [
        row for row in covered if int_field(row, "token_index", -1) < token_index
    ]
    following = [
        row for row in covered if int_field(row, "token_index", -1) > token_index
    ]
    return (
        max(previous, key=lambda row: int_field(row, "token_index")) if previous else None,
        min(following, key=lambda row: int_field(row, "token_index")) if following else None,
    )


def row_verdict(
    family: str,
    control_gap_bytes: int,
    local_candidate: dict[str, str] | None,
    near_candidate: dict[str, str] | None,
    full_candidate: dict[str, str] | None,
) -> tuple[str, str]:
    if local_candidate:
        return "extended_local_transform_candidate", "validate extended compact-control seed transforms by family"
    if control_gap_bytes == 0 and full_candidate:
        return "zero_gap_external_or_anchor_source_candidate", "derive zero-gap structural bridge source"
    if near_candidate:
        return "near_anchor_source_candidate", "derive near-anchor compact-control source rule"
    if full_candidate:
        return "external_source_candidate", "derive external structural source gate"
    if family.startswith("control_high"):
        return "control_high_source_missing", "derive high-control residual source gate"
    return "unresolved_family", "inspect structural residual source dependency"


def candidate_value(row: dict[str, str] | None, field: str) -> str:
    return "" if row is None else row.get(field, "")


def residual_row(
    payload: dict[str, object],
    target: dict[str, str],
    gap_row: dict[str, str],
    token: dict[str, str],
    grammar_row: dict[str, str],
    grammar_rows: list[dict[str, str]],
    *,
    source_window: int,
    max_delta: int,
) -> tuple[dict[str, str], list[dict[str, str]]]:
    data = payload.get("data", b"")
    segment = payload.get("segment", b"")
    if not isinstance(data, bytes):
        data = b""
    if not isinstance(segment, bytes):
        segment = b""

    chunk = token_chunk(payload, token)
    segment_start = int_field(gap_row, "previous_segment_end", -1)
    segment_end = int_field(gap_row, "next_segment_offset", -1)
    run_start = int_field(gap_row, "previous_run_offset_end", -1)
    run_end = int_field(gap_row, "next_run_offset_start", -1)
    gap = segment[segment_start:segment_end] if 0 <= segment_start <= segment_end <= len(segment) else b""
    gap_start = max(0, segment_start)
    gap_end = max(gap_start, segment_end)
    near_start = max(0, gap_start - source_window)
    near_end = min(len(segment), gap_end + source_window)
    near = segment[near_start:near_end]

    local_candidates = candidate_rows_for_source(
        gap,
        token,
        chunk,
        scope="local_control_gap",
        base_offset=gap_start,
        gap_start=gap_start,
        gap_end=gap_end,
        max_delta=max_delta,
    )
    near_candidates = candidate_rows_for_source(
        near,
        token,
        chunk,
        scope="near_anchor_window",
        base_offset=near_start,
        gap_start=gap_start,
        gap_end=gap_end,
        max_delta=max_delta,
    )
    full_candidates = candidate_rows_for_source(
        segment,
        token,
        chunk,
        scope="full_segment",
        base_offset=0,
        gap_start=gap_start,
        gap_end=gap_end,
        max_delta=max_delta,
    )
    local_candidate = choose_candidate(local_candidates)
    near_candidate = choose_candidate(near_candidates)
    full_candidate = choose_candidate(full_candidates)

    token_index = int_field(grammar_row, "token_index")
    previous, following = neighbor_rows(grammar_rows, token_index)
    family = value_family(token, chunk, len(gap))
    verdict, next_probe = row_verdict(family, len(gap), local_candidate, near_candidate, full_candidate)
    target_start = int_field(token, "run_offset_start", 0)
    target_end = int_field(token, "run_offset_end", target_start)
    target_context = data[max(0, target_start - 8) : min(len(data), target_end + 8)]

    row = {
        "target_id": target.get("target_id", ""),
        "rank": target.get("rank", ""),
        "pcx_name": target.get("pcx_name", ""),
        "frontier_id": target.get("frontier_id", ""),
        "span_index": target.get("span_index", ""),
        "gap_index": gap_row.get("gap_index", ""),
        "token_index": token.get("token_index", ""),
        "token_type": token.get("token_type", ""),
        "run_offset_start": token.get("run_offset_start", ""),
        "run_offset_end": token.get("run_offset_end", ""),
        "length": str(len(chunk)),
        "target_hex": chunk.hex(),
        "value_family": family,
        "value_classes": value_classes_text(chunk),
        "values_hex": values_hex_text(chunk),
        "control_gap_bytes": str(len(gap)),
        "control_gap_status": "zero_control_gap" if len(gap) == 0 else "local_control_gap",
        "local_transform": candidate_value(local_candidate, "source_transform"),
        "local_source_delta": candidate_value(local_candidate, "source_delta"),
        "local_source_value_hex": candidate_value(local_candidate, "source_value_hex"),
        "local_source_gap_offset": candidate_value(local_candidate, "source_offset"),
        "near_transform": candidate_value(near_candidate, "source_transform"),
        "near_source_delta": candidate_value(near_candidate, "source_delta"),
        "near_source_segment_offset": candidate_value(near_candidate, "source_segment_offset"),
        "near_distance_to_gap": candidate_value(near_candidate, "distance_to_gap"),
        "full_segment_transform": candidate_value(full_candidate, "source_transform"),
        "full_segment_source_delta": candidate_value(full_candidate, "source_delta"),
        "full_segment_offset": candidate_value(full_candidate, "source_segment_offset"),
        "full_segment_distance_to_gap": candidate_value(full_candidate, "distance_to_gap"),
        "full_segment_occurrences": candidate_value(full_candidate, "source_occurrences"),
        "previous_covered_token_index": "" if previous is None else previous.get("token_index", ""),
        "previous_covered_transform": "" if previous is None else previous.get("source_transform", ""),
        "next_covered_token_index": "" if following is None else following.get("token_index", ""),
        "next_covered_transform": "" if following is None else following.get("source_transform", ""),
        "target_context_hex": target_context.hex(),
        "control_gap_head_hex": gap[:32].hex(),
        "control_gap_tail_hex": gap[-32:].hex() if gap else "",
        "verdict": verdict,
        "next_probe": next_probe,
    }

    candidate_rows: list[dict[str, str]] = []
    for candidate in [local_candidate, near_candidate, full_candidate]:
        if candidate is None:
            continue
        candidate_rows.append(
            {
                "target_id": target.get("target_id", ""),
                "gap_index": gap_row.get("gap_index", ""),
                "token_index": token.get("token_index", ""),
                **{field: candidate.get(field, "") for field in CANDIDATE_FIELDNAMES if field not in {"target_id", "gap_index", "token_index"}},
            }
        )
    return row, candidate_rows


def family_summary_rows(residual_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in residual_rows:
        grouped[row.get("value_family", "")].append(row)
    rows: list[dict[str, str]] = []
    for family, family_rows in sorted(
        grouped.items(),
        key=lambda item: (-sum(int_field(row, "length") for row in item[1]), item[0]),
    ):
        values: set[str] = set()
        classes: set[str] = set()
        gaps: set[str] = set()
        for row in family_rows:
            values.update(row.get("values_hex", "").split())
            classes.update(row.get("value_classes", "").split())
            gaps.add(f"{row.get('target_id', '')}:g{row.get('gap_index', '')}")
        sample = family_rows[0]
        local_candidates = [row for row in family_rows if row.get("local_transform")]
        near_candidates = [row for row in family_rows if row.get("near_transform")]
        full_candidates = [row for row in family_rows if row.get("full_segment_transform")]
        no_gap = [row for row in family_rows if row.get("control_gap_status") == "zero_control_gap"]
        next_probe = "inspect structural residual source dependency"
        verdict = "residual_family_unresolved"
        if no_gap:
            verdict = "zero_control_gap_family"
            next_probe = "derive zero-gap structural bridge source"
        elif local_candidates:
            verdict = "extended_local_transform_family"
            next_probe = "validate extended compact-control seed transforms by family"
        elif near_candidates:
            verdict = "near_anchor_source_family"
            next_probe = "derive near-anchor compact-control source rule"
        elif full_candidates:
            verdict = "external_source_family"
            next_probe = "derive external structural source gate"
        rows.append(
            {
                "value_family": family,
                "token_rows": str(len(family_rows)),
                "token_bytes": str(sum(int_field(row, "length") for row in family_rows)),
                "target_ids": " ".join(sorted({row.get("target_id", "") for row in family_rows})),
                "pcx_names": " ".join(sorted({row.get("pcx_name", "") for row in family_rows})),
                "gaps": " ".join(sorted(gaps)),
                "no_control_gap_rows": str(len(no_gap)),
                "local_control_gap_rows": str(len(family_rows) - len(no_gap)),
                "local_extended_candidate_rows": str(len(local_candidates)),
                "near_window_candidate_rows": str(len(near_candidates)),
                "full_segment_candidate_rows": str(len(full_candidates)),
                "value_classes": " ".join(sorted(classes)),
                "values_hex": " ".join(sorted(values)),
                "sample_target_id": sample.get("target_id", ""),
                "sample_token_index": sample.get("token_index", ""),
                "verdict": verdict,
                "next_probe": next_probe,
            }
        )
    return rows


def total_summary(
    targets: list[dict[str, str]],
    grammar_rows: list[dict[str, str]],
    residual_rows: list[dict[str, str]],
    family_rows: list[dict[str, str]],
    issue_count: int,
) -> dict[str, str]:
    class_bytes: Counter[str] = Counter()
    for row in residual_rows:
        length = int_field(row, "length")
        family = row.get("value_family", "")
        if "low_delta" in family:
            class_bytes["low_delta_sequence"] += length
        elif "control_high" in family:
            class_bytes["control_high"] += length
        elif "dark_low" in family:
            class_bytes["dark_low"] += length
        elif "mid_payload" in family:
            class_bytes["mid_payload"] += length

    no_gap = [row for row in residual_rows if row.get("control_gap_status") == "zero_control_gap"]
    local_gap = [row for row in residual_rows if row.get("control_gap_status") == "local_control_gap"]
    next_probe = "derive high-control residual source gate"
    if no_gap:
        next_probe = "derive zero-gap external/anchor bridge for low-delta structural residuals"
    elif any(row.get("local_transform") for row in residual_rows):
        next_probe = "validate extended compact-control seed transforms by family"
    elif any(row.get("near_transform") for row in residual_rows):
        next_probe = "derive near-anchor compact-control source rule"
    elif any(row.get("full_segment_transform") for row in residual_rows):
        next_probe = "derive external structural source gate for residual families"
    return {
        "scope": "total",
        "selected_target_runs": str(len(targets)),
        "selected_target_bytes": str(sum(int_value(row, "length") for row in targets)),
        "grammar_token_rows": str(len(grammar_rows)),
        "grammar_token_bytes": str(sum(int_field(row, "length") for row in grammar_rows)),
        "residual_token_rows": str(len(residual_rows)),
        "residual_token_bytes": str(sum(int_field(row, "length") for row in residual_rows)),
        "family_rows": str(len(family_rows)),
        "no_control_gap_token_rows": str(len(no_gap)),
        "no_control_gap_bytes": str(sum(int_field(row, "length") for row in no_gap)),
        "local_control_gap_token_rows": str(len(local_gap)),
        "local_control_gap_bytes": str(sum(int_field(row, "length") for row in local_gap)),
        "local_extended_candidate_rows": str(sum(1 for row in residual_rows if row.get("local_transform"))),
        "near_window_candidate_rows": str(sum(1 for row in residual_rows if row.get("near_transform"))),
        "full_segment_candidate_rows": str(sum(1 for row in residual_rows if row.get("full_segment_transform"))),
        "low_delta_sequence_bytes": str(class_bytes["low_delta_sequence"]),
        "control_high_bytes": str(class_bytes["control_high"]),
        "dark_low_bytes": str(class_bytes["dark_low"]),
        "mid_payload_bytes": str(class_bytes["mid_payload"]),
        "issue_rows": str(issue_count),
        "review_verdict": "frontier80_structural_nonzero_compact_control_residual_value_families_split",
        "next_probe": next_probe,
    }


def render_table(rows: list[dict[str, str]], fieldnames: list[str], *, limit: int = 80) -> str:
    if not rows:
        return "<p class=\"muted\">No rows.</p>"
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fieldnames)
    body = []
    for row in rows[:limit]:
        body.append(
            "<tr>"
            + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fieldnames)
            + "</tr>"
        )
    note = "" if len(rows) <= limit else f"<p class=\"muted\">Showing {limit} of {len(rows)} rows.</p>"
    return f"{note}<table><thead><tr>{header}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def build_html(
    output: Path,
    title: str,
    summary: dict[str, str],
    family_rows: list[dict[str, str]],
    residual_rows: list[dict[str, str]],
    candidate_rows: list[dict[str, str]],
) -> str:
    payload = {
        "summary": summary,
        "families": family_rows,
        "residuals": residual_rows,
        "candidates": candidate_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    cards = [
        ("Residual bytes", summary.get("residual_token_bytes", "0")),
        ("Families", summary.get("family_rows", "0")),
        ("Zero-gap bytes", summary.get("no_control_gap_bytes", "0")),
        ("Local-gap bytes", summary.get("local_control_gap_bytes", "0")),
        ("Full candidates", summary.get("full_segment_candidate_rows", "0")),
        ("Verdict", summary.get("review_verdict", "")),
    ]
    card_html = "".join(
        f"<div class=\"card\"><div class=\"value\">{html.escape(value)}</div>"
        f"<div class=\"label\">{html.escape(label)}</div></div>"
        for label, value in cards
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{html.escape(title)}</title>
  <style>
    body {{ margin: 0; font: 14px/1.45 system-ui, sans-serif; color: #20242a; background: #f6f7f9; }}
    main {{ max-width: 1320px; margin: 0 auto; padding: 24px; }}
    h1 {{ margin: 0 0 8px; font-size: 24px; }}
    h2 {{ margin: 0 0 12px; font-size: 17px; }}
    .muted {{ color: #68717d; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; margin: 18px 0; }}
    .card, section {{ background: #fff; border: 1px solid #d8dde5; border-radius: 8px; }}
    .card {{ padding: 14px; }}
    .value {{ font-size: 20px; font-weight: 700; overflow-wrap: anywhere; }}
    .label {{ margin-top: 4px; color: #68717d; }}
    section {{ padding: 16px; margin: 16px 0; overflow: auto; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
    th, td {{ padding: 6px 8px; border-bottom: 1px solid #e3e7ed; text-align: left; vertical-align: top; }}
    th {{ position: sticky; top: 0; background: #eef2f6; }}
    td {{ max-width: 360px; overflow-wrap: anywhere; }}
    a {{ color: #1f5aa6; }}
  </style>
</head>
<body>
<main>
  <h1>{html.escape(title)}</h1>
  <div class="muted">Splits unresolved compact-control grammar tokens by value family and nearby source evidence.</div>
  <div class="grid">{card_html}</div>
  <section><h2>Outputs</h2>
    <p><a href="{relative_href(output / 'summary.csv', output / 'index.html')}">summary.csv</a> ·
    <a href="{relative_href(output / 'families.csv', output / 'index.html')}">families.csv</a> ·
    <a href="{relative_href(output / 'residual_tokens.csv', output / 'index.html')}">residual_tokens.csv</a> ·
    <a href="{relative_href(output / 'source_candidates.csv', output / 'index.html')}">source_candidates.csv</a></p>
  </section>
  <section><h2>Families</h2>{render_table(family_rows, FAMILY_FIELDNAMES)}</section>
  <section><h2>Residual Tokens</h2>{render_table(residual_rows, RESIDUAL_FIELDNAMES)}</section>
  <section><h2>Source Candidates</h2>{render_table(candidate_rows, CANDIDATE_FIELDNAMES)}</section>
</main>
<script type="application/json" id="compact-control-residual-family-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> dict[str, str]:
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    targets = select_targets(read_csv(args.runs), min_length=args.min_run_length, limit=args.target_limit)
    payloads = load_target_payloads(targets, read_csv(args.manifest), read_csv(args.clean_fixtures), issues)
    grammar_rows: list[dict[str, str]] = []
    residual_rows: list[dict[str, str]] = []
    candidate_rows: list[dict[str, str]] = []

    for payload in payloads:
        target = payload.get("target", {})
        if not isinstance(target, dict):
            continue
        token_rows = build_token_rows(
            payload,
            min_repeat=args.min_repeat,
            min_delta=args.min_delta,
            max_delta=args.max_delta,
        )
        token_by_index = {row.get("token_index", ""): row for row in token_rows}
        ordered_rows = ordered_strong_bridge(payload, token_rows)
        control_gap_rows = build_control_gap_rows(payload, ordered_rows)
        for control_gap in control_gap_rows:
            gap_token_rows = build_token_rows_for_gap(payload, control_gap, token_rows)
            enriched_rows = [
                {
                    "rank": target.get("rank", ""),
                    "pcx_name": target.get("pcx_name", ""),
                    "frontier_id": target.get("frontier_id", ""),
                    "span_index": target.get("span_index", ""),
                    **row,
                }
                for row in gap_token_rows
            ]
            grammar_rows.extend(enriched_rows)
            for grammar_row in enriched_rows:
                if grammar_row.get("verdict") == "covered":
                    continue
                token = token_by_index.get(grammar_row.get("token_index", ""))
                if token is None:
                    issues.append(
                        f"{target.get('target_id', '')}:g{control_gap.get('gap_index', '')}:"
                        f"token{grammar_row.get('token_index', '')}:missing_token"
                    )
                    continue
                row, rows = residual_row(
                    payload,
                    target,
                    control_gap,
                    token,
                    grammar_row,
                    enriched_rows,
                    source_window=args.source_window,
                    max_delta=args.seed_delta_window,
                )
                residual_rows.append(row)
                candidate_rows.extend(rows)

    family_rows = family_summary_rows(residual_rows)
    summary = total_summary(targets, grammar_rows, residual_rows, family_rows, len(issues))
    write_csv(output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output / "families.csv", FAMILY_FIELDNAMES, family_rows)
    write_csv(output / "residual_tokens.csv", RESIDUAL_FIELDNAMES, residual_rows)
    write_csv(output / "source_candidates.csv", CANDIDATE_FIELDNAMES, candidate_rows)
    (output / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""))
    (output / "index.html").write_text(
        build_html(output, args.title, summary, family_rows, residual_rows, candidate_rows)
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Split unresolved structural compact-control residuals by value family."
    )
    parser.add_argument("--runs", type=Path, default=DEFAULT_RUNS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--clean-fixtures", type=Path, default=DEFAULT_CLEAN_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--target-limit", type=int, default=64)
    parser.add_argument("--min-run-length", type=int, default=16)
    parser.add_argument("--min-repeat", type=int, default=2)
    parser.add_argument("--min-delta", type=int, default=4)
    parser.add_argument("--max-delta", type=int, default=2)
    parser.add_argument("--seed-delta-window", type=int, default=8)
    parser.add_argument("--source-window", type=int, default=48)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Structural Compact-Control Residual Value Families",
    )
    args = parser.parse_args()
    summary = write_report(args)
    print(f"Residual bytes: {summary['residual_token_bytes']}")
    print(f"Families: {summary['family_rows']}")
    print(f"Zero-gap bytes: {summary['no_control_gap_bytes']}")
    print(f"Local-gap bytes: {summary['local_control_gap_bytes']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
