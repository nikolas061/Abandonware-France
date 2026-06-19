#!/usr/bin/env python3
"""Derive guarded weak anchors for structural nonzero targets without bridge anchors."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

from lolg_tex_gap_opcode_probe import relative_href, write_csv
from lolg_tex_gap_decoder_frontier80_clean_structural_nonzero_producer_probe import (
    DEFAULT_CLEAN_FIXTURES,
    DEFAULT_MANIFEST,
    int_value,
    load_target_payloads,
    ratio,
    read_csv,
)
from lolg_tex_gap_decoder_frontier80_clean_structural_nonzero_rle_delta_parser_probe import (
    build_token_rows,
)
from lolg_tex_gap_decoder_frontier80_clean_structural_nonzero_control_bridge_probe import (
    build_token_bridge_rows,
    int_field,
)


DEFAULT_INTEGRATED_TARGETS = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_compact_control_integrated_replay_probe/targets.csv"
)
DEFAULT_OUTPUT = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_no_bridge_anchor_probe"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "no_bridge_target_runs",
    "no_bridge_target_bytes",
    "token_rows",
    "generated_bytes",
    "literal_bytes",
    "exact_single_anchor_rows",
    "exact_single_anchor_target_runs",
    "exact_single_anchor_target_bytes",
    "unique_single_anchor_rows",
    "unique_single_anchor_target_runs",
    "unique_single_anchor_target_bytes",
    "ordered_unique_anchor_rows",
    "ordered_unique_anchor_target_runs",
    "ordered_unique_anchor_target_bytes",
    "multi_anchor_target_runs",
    "multi_anchor_target_bytes",
    "weak_gap_rows",
    "weak_gap_target_bytes",
    "weak_envelope_bytes",
    "weak_envelope_ratio",
    "partial_window_rows",
    "partial_window_target_runs",
    "partial_window_target_bytes",
    "partial_window_exact_bytes",
    "control_hint_rows",
    "control_hint_target_runs",
    "control_hint_target_bytes",
    "fragment_hint_rows",
    "fragment_hint_target_runs",
    "fragment_hint_target_bytes",
    "remaining_no_anchor_target_runs",
    "remaining_no_anchor_target_bytes",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

TARGET_FIELDNAMES = [
    "target_id",
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "span_index",
    "run_index",
    "start",
    "end",
    "length",
    "token_rows",
    "generated_bytes",
    "literal_bytes",
    "exact_single_anchor_rows",
    "unique_single_anchor_rows",
    "ordered_unique_anchor_rows",
    "multi_anchor",
    "weak_gap_rows",
    "weak_gap_target_bytes",
    "weak_envelope_bytes",
    "partial_window_rows",
    "partial_window_exact_bytes",
    "control_hint_rows",
    "fragment_hint_rows",
    "verdict",
    "next_probe",
]

ANCHOR_FIELDNAMES = [
    "target_id",
    "rank",
    "pcx_name",
    "frontier_id",
    "span_index",
    "anchor_index",
    "token_index",
    "token_type",
    "run_offset_start",
    "run_offset_end",
    "segment_offset",
    "segment_end",
    "length",
    "byte_hex",
    "exact_segment_offset_count",
    "guard",
    "segment_context_before_hex",
    "segment_context_after_hex",
]

GAP_FIELDNAMES = [
    "target_id",
    "rank",
    "pcx_name",
    "frontier_id",
    "span_index",
    "gap_index",
    "previous_anchor_index",
    "next_anchor_index",
    "previous_token_index",
    "next_token_index",
    "previous_run_offset_end",
    "next_run_offset_start",
    "run_gap_bytes",
    "previous_segment_end",
    "next_segment_offset",
    "segment_gap_bytes",
    "segment_gap_head_hex",
    "segment_gap_tail_hex",
]

HINT_FIELDNAMES = [
    "target_id",
    "rank",
    "pcx_name",
    "frontier_id",
    "span_index",
    "hint_type",
    "token_index",
    "token_type",
    "run_offset_start",
    "run_offset_end",
    "length",
    "source_offset_count",
    "source_offsets",
    "best_segment_offset",
    "best_segment_exact_bytes",
    "best_segment_exact_ratio",
    "head_hex",
    "tail_hex",
    "guard",
]


def parse_first_offset(offsets_text: str) -> int:
    for part in offsets_text.split():
        try:
            return int(part)
        except ValueError:
            continue
    return -1


def select_no_bridge_targets(rows: list[dict[str, str]], *, limit: int) -> list[dict[str, str]]:
    targets = [row for row in rows if row.get("verdict") == "no_bridge_anchor"]
    targets.sort(
        key=lambda row: (
            -int_value(row, "length"),
            row.get("pcx_name", ""),
            int_value(row, "start"),
        )
    )
    return targets[:limit] if limit > 0 else targets


def ordered_unique_single_anchors(token_bridge_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    states: list[dict[str, object]] = []
    for row in token_bridge_rows:
        if row.get("exact_segment_token") != "1":
            continue
        if int_field(row, "length") != 1:
            continue
        if int_field(row, "exact_segment_offset_count") != 1:
            continue
        segment_offset = parse_first_offset(row.get("exact_segment_offsets", ""))
        if segment_offset < 0:
            continue
        states.append(
            {
                "token_order": int_field(row, "token_index"),
                "segment_offset": segment_offset,
                "row": row,
                "score": 1,
                "previous": None,
            }
        )

    states.sort(key=lambda state: (int(state["token_order"]), int(state["segment_offset"])))
    for index, state in enumerate(states):
        best_score = int(state["score"])
        best_previous: int | None = None
        token_order = int(state["token_order"])
        segment_offset = int(state["segment_offset"])
        for previous_index in range(index):
            previous = states[previous_index]
            if int(previous["token_order"]) >= token_order:
                continue
            if int(previous["segment_offset"]) + 1 > segment_offset:
                continue
            score = int(previous["score"]) + 1
            if score > best_score:
                best_score = score
                best_previous = previous_index
        state["score"] = best_score
        state["previous"] = best_previous

    if not states:
        return []
    best_index = max(range(len(states)), key=lambda state_index: int(states[state_index]["score"]))
    chain: list[dict[str, object]] = []
    while best_index is not None:
        chain.append(states[best_index])
        best_index = states[best_index]["previous"]  # type: ignore[assignment]
    chain.reverse()
    return [state["row"] for state in chain if isinstance(state.get("row"), dict)]


def build_anchor_rows(
    payload: dict[str, object],
    ordered_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    target = payload.get("target", {})
    segment = payload.get("segment", b"")
    if not isinstance(target, dict):
        target = {}
    if not isinstance(segment, bytes):
        segment = b""
    rows: list[dict[str, str]] = []
    for anchor_index, row in enumerate(ordered_rows, start=1):
        segment_offset = parse_first_offset(row.get("exact_segment_offsets", ""))
        segment_end = segment_offset + int_field(row, "length")
        rows.append(
            {
                "target_id": target.get("target_id", ""),
                "rank": target.get("rank", ""),
                "pcx_name": target.get("pcx_name", ""),
                "frontier_id": target.get("frontier_id", ""),
                "span_index": target.get("span_index", ""),
                "anchor_index": str(anchor_index),
                "token_index": row.get("token_index", ""),
                "token_type": row.get("token_type", ""),
                "run_offset_start": row.get("run_offset_start", ""),
                "run_offset_end": row.get("run_offset_end", ""),
                "segment_offset": str(segment_offset),
                "segment_end": str(segment_end),
                "length": row.get("length", ""),
                "byte_hex": row.get("head_hex", ""),
                "exact_segment_offset_count": row.get("exact_segment_offset_count", ""),
                "guard": "unique_single_byte_segment_anchor",
                "segment_context_before_hex": segment[max(0, segment_offset - 12) : segment_offset].hex(),
                "segment_context_after_hex": segment[segment_end : min(len(segment), segment_end + 12)].hex(),
            }
        )
    return rows


def build_gap_rows(payload: dict[str, object], anchor_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    target = payload.get("target", {})
    segment = payload.get("segment", b"")
    if not isinstance(target, dict):
        target = {}
    if not isinstance(segment, bytes):
        segment = b""
    rows: list[dict[str, str]] = []
    for gap_index, (previous, current) in enumerate(zip(anchor_rows, anchor_rows[1:]), start=1):
        previous_run_end = int_field(previous, "run_offset_end", -1)
        next_run_start = int_field(current, "run_offset_start", -1)
        previous_segment_end = int_field(previous, "segment_end", -1)
        next_segment_offset = int_field(current, "segment_offset", -1)
        segment_gap = (
            segment[previous_segment_end:next_segment_offset]
            if 0 <= previous_segment_end <= next_segment_offset
            else b""
        )
        rows.append(
            {
                "target_id": target.get("target_id", ""),
                "rank": target.get("rank", ""),
                "pcx_name": target.get("pcx_name", ""),
                "frontier_id": target.get("frontier_id", ""),
                "span_index": target.get("span_index", ""),
                "gap_index": str(gap_index),
                "previous_anchor_index": previous.get("anchor_index", ""),
                "next_anchor_index": current.get("anchor_index", ""),
                "previous_token_index": previous.get("token_index", ""),
                "next_token_index": current.get("token_index", ""),
                "previous_run_offset_end": previous.get("run_offset_end", ""),
                "next_run_offset_start": current.get("run_offset_start", ""),
                "run_gap_bytes": str(max(0, next_run_start - previous_run_end))
                if previous_run_end >= 0 and next_run_start >= 0
                else "",
                "previous_segment_end": previous.get("segment_end", ""),
                "next_segment_offset": current.get("segment_offset", ""),
                "segment_gap_bytes": str(len(segment_gap)),
                "segment_gap_head_hex": segment_gap[:32].hex(),
                "segment_gap_tail_hex": segment_gap[-32:].hex() if segment_gap else "",
            }
        )
    return rows


def build_hint_rows(
    payload: dict[str, object],
    token_bridge_rows: list[dict[str, str]],
    *,
    partial_min_exact: int,
    partial_min_ratio: float,
) -> list[dict[str, str]]:
    target = payload.get("target", {})
    if not isinstance(target, dict):
        target = {}
    rows: list[dict[str, str]] = []
    for row in token_bridge_rows:
        length = int_field(row, "length")
        best_exact = int_field(row, "best_segment_exact_bytes")
        best_ratio = (best_exact / length) if length else 0.0
        hint_type = ""
        source_offsets = ""
        source_count = 0
        guard = ""
        if best_exact >= partial_min_exact and best_ratio >= partial_min_ratio:
            hint_type = "partial_segment_window"
            source_offsets = row.get("best_segment_offset", "")
            source_count = 1 if source_offsets else 0
            guard = f"best_segment_exact_ge{partial_min_exact}_ratio_ge{partial_min_ratio:.2f}"
        elif int_field(row, "exact_control_prefix_offset_count") > 0:
            hint_type = "exact_control_prefix"
            source_offsets = row.get("exact_control_prefix_offsets", "")
            source_count = int_field(row, "exact_control_prefix_offset_count")
            guard = "exact_control_prefix_token"
        elif int_field(row, "exact_fragment_offset_count") > 0:
            hint_type = "exact_fragment"
            source_offsets = row.get("exact_fragment_offsets", "")
            source_count = int_field(row, "exact_fragment_offset_count")
            guard = "exact_fragment_token"
        if not hint_type:
            continue
        rows.append(
            {
                "target_id": target.get("target_id", ""),
                "rank": target.get("rank", ""),
                "pcx_name": target.get("pcx_name", ""),
                "frontier_id": target.get("frontier_id", ""),
                "span_index": target.get("span_index", ""),
                "hint_type": hint_type,
                "token_index": row.get("token_index", ""),
                "token_type": row.get("token_type", ""),
                "run_offset_start": row.get("run_offset_start", ""),
                "run_offset_end": row.get("run_offset_end", ""),
                "length": row.get("length", ""),
                "source_offset_count": str(source_count),
                "source_offsets": source_offsets,
                "best_segment_offset": row.get("best_segment_offset", ""),
                "best_segment_exact_bytes": row.get("best_segment_exact_bytes", ""),
                "best_segment_exact_ratio": row.get("best_segment_exact_ratio", ""),
                "head_hex": row.get("head_hex", ""),
                "tail_hex": row.get("tail_hex", ""),
                "guard": guard,
            }
        )
    return rows


def target_summary(
    payload: dict[str, object],
    token_rows: list[dict[str, str]],
    exact_single_rows: list[dict[str, str]],
    unique_single_rows: list[dict[str, str]],
    anchor_rows: list[dict[str, str]],
    gap_rows: list[dict[str, str]],
    hint_rows: list[dict[str, str]],
) -> dict[str, str]:
    target = payload.get("target", {})
    data = payload.get("data", b"")
    if not isinstance(target, dict) or not isinstance(data, bytes):
        return {}
    partial_rows = [row for row in hint_rows if row.get("hint_type") == "partial_segment_window"]
    control_rows = [row for row in hint_rows if row.get("hint_type") == "exact_control_prefix"]
    fragment_rows = [row for row in hint_rows if row.get("hint_type") == "exact_fragment"]
    generated = sum(int_field(row, "generated_bytes") for row in token_rows)
    literal = sum(int_field(row, "length") for row in token_rows if row.get("token_type") == "literal")
    weak_envelope = 0
    if anchor_rows:
        weak_envelope = int_field(anchor_rows[-1], "run_offset_end") - int_field(anchor_rows[0], "run_offset_start")
    if anchor_rows:
        verdict = "guarded_unique_single_byte_anchor_ready"
        next_probe = "promote guarded unique single-byte no-bridge anchors into structural bridge replay"
    elif partial_rows:
        verdict = "partial_window_anchor_candidate"
        next_probe = "review partial-window no-bridge anchors"
    elif control_rows or fragment_rows:
        verdict = "control_fragment_anchor_hint_only"
        next_probe = "derive segment bridge from control/fragment no-bridge hints"
    else:
        verdict = "no_bridge_anchor_source_gap"
        next_probe = "derive non-segment sources for remaining no-bridge runs"
    return {
        "target_id": target.get("target_id", ""),
        "rank": target.get("rank", ""),
        "archive": target.get("archive", ""),
        "archive_tag": target.get("archive_tag", ""),
        "pcx_name": target.get("pcx_name", ""),
        "frontier_id": target.get("frontier_id", ""),
        "span_index": target.get("span_index", ""),
        "run_index": target.get("run_index", ""),
        "start": target.get("start", ""),
        "end": target.get("end", ""),
        "length": str(len(data)),
        "token_rows": str(len(token_rows)),
        "generated_bytes": str(generated),
        "literal_bytes": str(literal),
        "exact_single_anchor_rows": str(len(exact_single_rows)),
        "unique_single_anchor_rows": str(len(unique_single_rows)),
        "ordered_unique_anchor_rows": str(len(anchor_rows)),
        "multi_anchor": "1" if len(anchor_rows) >= 2 else "0",
        "weak_gap_rows": str(len(gap_rows)),
        "weak_gap_target_bytes": str(sum(int_field(row, "run_gap_bytes") for row in gap_rows)),
        "weak_envelope_bytes": str(max(0, weak_envelope)),
        "partial_window_rows": str(len(partial_rows)),
        "partial_window_exact_bytes": str(sum(int_field(row, "best_segment_exact_bytes") for row in partial_rows)),
        "control_hint_rows": str(len(control_rows)),
        "fragment_hint_rows": str(len(fragment_rows)),
        "verdict": verdict,
        "next_probe": next_probe,
    }


def total_summary(
    target_rows: list[dict[str, str]],
    anchor_rows: list[dict[str, str]],
    gap_rows: list[dict[str, str]],
    hint_rows: list[dict[str, str]],
    issue_count: int,
) -> dict[str, str]:
    target_bytes = sum(int_field(row, "length") for row in target_rows)
    anchored_targets = [row for row in target_rows if int_field(row, "ordered_unique_anchor_rows") > 0]
    unique_targets = [row for row in target_rows if int_field(row, "unique_single_anchor_rows") > 0]
    exact_targets = [row for row in target_rows if int_field(row, "exact_single_anchor_rows") > 0]
    multi_targets = [row for row in target_rows if row.get("multi_anchor") == "1"]
    partial_targets = [row for row in target_rows if int_field(row, "partial_window_rows") > 0]
    control_targets = [row for row in target_rows if int_field(row, "control_hint_rows") > 0]
    fragment_targets = [row for row in target_rows if int_field(row, "fragment_hint_rows") > 0]
    remaining = [row for row in target_rows if int_field(row, "ordered_unique_anchor_rows") == 0]
    partial_rows = [row for row in hint_rows if row.get("hint_type") == "partial_segment_window"]
    control_rows = [row for row in hint_rows if row.get("hint_type") == "exact_control_prefix"]
    fragment_rows = [row for row in hint_rows if row.get("hint_type") == "exact_fragment"]
    verdict = "frontier80_structural_no_bridge_unique_anchor_candidates_ready"
    next_probe = "promote guarded unique single-byte no-bridge anchors into structural bridge replay"
    if issue_count:
        verdict = "frontier80_structural_no_bridge_anchor_probe_issues"
        next_probe = "review no-bridge anchor probe issues"
    elif not anchor_rows:
        verdict = "frontier80_structural_no_bridge_anchor_probe_needs_sources"
        next_probe = "derive non-segment sources for remaining no-bridge runs"
    return {
        "scope": "total",
        "no_bridge_target_runs": str(len(target_rows)),
        "no_bridge_target_bytes": str(target_bytes),
        "token_rows": str(sum(int_field(row, "token_rows") for row in target_rows)),
        "generated_bytes": str(sum(int_field(row, "generated_bytes") for row in target_rows)),
        "literal_bytes": str(sum(int_field(row, "literal_bytes") for row in target_rows)),
        "exact_single_anchor_rows": str(sum(int_field(row, "exact_single_anchor_rows") for row in target_rows)),
        "exact_single_anchor_target_runs": str(len(exact_targets)),
        "exact_single_anchor_target_bytes": str(sum(int_field(row, "length") for row in exact_targets)),
        "unique_single_anchor_rows": str(sum(int_field(row, "unique_single_anchor_rows") for row in target_rows)),
        "unique_single_anchor_target_runs": str(len(unique_targets)),
        "unique_single_anchor_target_bytes": str(sum(int_field(row, "length") for row in unique_targets)),
        "ordered_unique_anchor_rows": str(len(anchor_rows)),
        "ordered_unique_anchor_target_runs": str(len(anchored_targets)),
        "ordered_unique_anchor_target_bytes": str(sum(int_field(row, "length") for row in anchored_targets)),
        "multi_anchor_target_runs": str(len(multi_targets)),
        "multi_anchor_target_bytes": str(sum(int_field(row, "length") for row in multi_targets)),
        "weak_gap_rows": str(len(gap_rows)),
        "weak_gap_target_bytes": str(sum(int_field(row, "run_gap_bytes") for row in gap_rows)),
        "weak_envelope_bytes": str(sum(int_field(row, "weak_envelope_bytes") for row in target_rows)),
        "weak_envelope_ratio": ratio(sum(int_field(row, "weak_envelope_bytes") for row in target_rows), target_bytes),
        "partial_window_rows": str(len(partial_rows)),
        "partial_window_target_runs": str(len(partial_targets)),
        "partial_window_target_bytes": str(sum(int_field(row, "length") for row in partial_targets)),
        "partial_window_exact_bytes": str(sum(int_field(row, "best_segment_exact_bytes") for row in partial_rows)),
        "control_hint_rows": str(len(control_rows)),
        "control_hint_target_runs": str(len(control_targets)),
        "control_hint_target_bytes": str(sum(int_field(row, "length") for row in control_targets)),
        "fragment_hint_rows": str(len(fragment_rows)),
        "fragment_hint_target_runs": str(len(fragment_targets)),
        "fragment_hint_target_bytes": str(sum(int_field(row, "length") for row in fragment_targets)),
        "remaining_no_anchor_target_runs": str(len(remaining)),
        "remaining_no_anchor_target_bytes": str(sum(int_field(row, "length") for row in remaining)),
        "issue_rows": str(issue_count),
        "review_verdict": verdict,
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
    target_rows: list[dict[str, str]],
    anchor_rows: list[dict[str, str]],
    gap_rows: list[dict[str, str]],
    hint_rows: list[dict[str, str]],
) -> str:
    payload = {"summary": summary, "targets": target_rows, "anchors": anchor_rows, "gaps": gap_rows, "hints": hint_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    cards = [
        ("No-bridge bytes", summary.get("no_bridge_target_bytes", "0")),
        ("Anchor targets", summary.get("ordered_unique_anchor_target_runs", "0")),
        ("Weak envelope", summary.get("weak_envelope_bytes", "0")),
        ("Weak gaps", summary.get("weak_gap_target_bytes", "0")),
        ("Remaining bytes", summary.get("remaining_no_anchor_target_bytes", "0")),
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
  <div class="muted">Derives guarded weak anchors for structural nonzero runs left without bridge anchors.</div>
  <div class="grid">{card_html}</div>
  <section><h2>Outputs</h2>
    <p><a href="{relative_href(output / 'summary.csv', output / 'index.html')}">summary.csv</a> ·
    <a href="{relative_href(output / 'targets.csv', output / 'index.html')}">targets.csv</a> ·
    <a href="{relative_href(output / 'anchors.csv', output / 'index.html')}">anchors.csv</a> ·
    <a href="{relative_href(output / 'gaps.csv', output / 'index.html')}">gaps.csv</a> ·
    <a href="{relative_href(output / 'hints.csv', output / 'index.html')}">hints.csv</a></p>
  </section>
  <section><h2>Targets</h2>{render_table(target_rows, TARGET_FIELDNAMES)}</section>
  <section><h2>Anchors</h2>{render_table(anchor_rows, ANCHOR_FIELDNAMES)}</section>
  <section><h2>Weak Gaps</h2>{render_table(gap_rows, GAP_FIELDNAMES)}</section>
  <section><h2>Hints</h2>{render_table(hint_rows, HINT_FIELDNAMES)}</section>
</main>
<script type="application/json" id="no-bridge-anchor-probe-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> dict[str, str]:
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    targets = select_no_bridge_targets(read_csv(args.integrated_targets), limit=args.target_limit)
    payloads = load_target_payloads(targets, read_csv(args.manifest), read_csv(args.clean_fixtures), issues)
    target_rows: list[dict[str, str]] = []
    anchor_rows: list[dict[str, str]] = []
    gap_rows: list[dict[str, str]] = []
    hint_rows: list[dict[str, str]] = []

    for payload in payloads:
        token_rows = build_token_rows(
            payload,
            min_repeat=args.min_repeat,
            min_delta=args.min_delta,
            max_delta=args.max_delta,
        )
        token_bridge_rows = build_token_bridge_rows(payload, token_rows)
        exact_single_rows = [
            row
            for row in token_bridge_rows
            if row.get("exact_segment_token") == "1" and int_field(row, "length") == 1
        ]
        unique_single_rows = [
            row for row in exact_single_rows if int_field(row, "exact_segment_offset_count") == 1
        ]
        ordered_rows = ordered_unique_single_anchors(token_bridge_rows)
        payload_anchor_rows = build_anchor_rows(payload, ordered_rows)
        payload_gap_rows = build_gap_rows(payload, payload_anchor_rows)
        payload_hint_rows = build_hint_rows(
            payload,
            token_bridge_rows,
            partial_min_exact=args.partial_min_exact,
            partial_min_ratio=args.partial_min_ratio,
        )
        row = target_summary(
            payload,
            token_rows,
            exact_single_rows,
            unique_single_rows,
            payload_anchor_rows,
            payload_gap_rows,
            payload_hint_rows,
        )
        if row:
            target_rows.append(row)
        anchor_rows.extend(payload_anchor_rows)
        gap_rows.extend(payload_gap_rows)
        hint_rows.extend(payload_hint_rows)

    summary = total_summary(target_rows, anchor_rows, gap_rows, hint_rows, len(issues))
    write_csv(output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output / "targets.csv", TARGET_FIELDNAMES, target_rows)
    write_csv(output / "anchors.csv", ANCHOR_FIELDNAMES, anchor_rows)
    write_csv(output / "gaps.csv", GAP_FIELDNAMES, gap_rows)
    write_csv(output / "hints.csv", HINT_FIELDNAMES, hint_rows)
    (output / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""))
    (output / "index.html").write_text(
        build_html(output, args.title, summary, target_rows, anchor_rows, gap_rows, hint_rows)
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Derive guarded weak anchors for structural nonzero targets without bridge anchors."
    )
    parser.add_argument("--integrated-targets", type=Path, default=DEFAULT_INTEGRATED_TARGETS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--clean-fixtures", type=Path, default=DEFAULT_CLEAN_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--target-limit", type=int, default=0)
    parser.add_argument("--min-repeat", type=int, default=2)
    parser.add_argument("--min-delta", type=int, default=4)
    parser.add_argument("--max-delta", type=int, default=2)
    parser.add_argument("--partial-min-exact", type=int, default=3)
    parser.add_argument("--partial-min-ratio", type=float, default=0.5)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Structural No-Bridge Anchor Probe",
    )
    args = parser.parse_args()
    summary = write_report(args)
    print(f"No-bridge target bytes: {summary['no_bridge_target_bytes']}")
    print(f"Ordered unique anchor rows: {summary['ordered_unique_anchor_rows']}")
    print(f"Weak envelope bytes: {summary['weak_envelope_bytes']}")
    print(f"Remaining no-anchor bytes: {summary['remaining_no_anchor_target_bytes']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
