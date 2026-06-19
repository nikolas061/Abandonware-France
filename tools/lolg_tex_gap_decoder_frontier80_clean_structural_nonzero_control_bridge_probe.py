#!/usr/bin/env python3
"""Map structural Frontier80 RLE/delta token plans back to segment-control evidence."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv
from lolg_tex_gap_decoder_frontier80_clean_structural_nonzero_producer_probe import (
    DEFAULT_CLEAN_FIXTURES,
    DEFAULT_MANIFEST,
    DEFAULT_RUNS,
    load_target_payloads,
    ratio,
    read_csv,
    select_largest_targets,
)


DEFAULT_TOKENS = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_rle_delta_parser_probe/tokens.csv"
)
DEFAULT_OUTPUT = Path("output/tex_gap_decoder_frontier80_clean_structural_nonzero_control_bridge_probe")

SUMMARY_FIELDNAMES = [
    "scope",
    "target_runs",
    "target_bytes",
    "token_rows",
    "segment_gap_bytes",
    "control_prefix_bytes",
    "fragment_bytes",
    "generated_bytes",
    "literal_bytes",
    "exact_segment_token_rows",
    "exact_segment_token_bytes",
    "strong_exact_segment_token_rows",
    "strong_exact_segment_token_bytes",
    "best_segment_token_exact_bytes",
    "best_segment_token_exact_ratio",
    "ordered_strong_bridge_tokens",
    "ordered_strong_bridge_bytes",
    "ordered_strong_bridge_ratio",
    "control_gap_rows",
    "control_gap_bytes",
    "control_prefix_token_rows",
    "fragment_token_rows",
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
    "segment_gap_bytes",
    "control_prefix_bytes",
    "fragment_bytes",
    "generated_bytes",
    "literal_bytes",
    "exact_segment_token_rows",
    "exact_segment_token_bytes",
    "strong_exact_segment_token_rows",
    "strong_exact_segment_token_bytes",
    "best_segment_token_exact_bytes",
    "ordered_strong_bridge_tokens",
    "ordered_strong_bridge_bytes",
    "control_gap_rows",
    "control_gap_bytes",
    "verdict",
    "next_probe",
]

TOKEN_BRIDGE_FIELDNAMES = [
    "target_id",
    "token_index",
    "token_type",
    "run_offset_start",
    "run_offset_end",
    "absolute_start",
    "absolute_end",
    "length",
    "generated_bytes",
    "head_hex",
    "tail_hex",
    "exact_segment_token",
    "exact_segment_offsets",
    "exact_segment_offset_count",
    "exact_control_prefix_offsets",
    "exact_control_prefix_offset_count",
    "exact_fragment_offsets",
    "exact_fragment_offset_count",
    "best_segment_offset",
    "best_segment_exact_bytes",
    "best_segment_exact_ratio",
    "best_segment_head_hex",
    "best_segment_tail_hex",
    "segment_context_before_hex",
    "segment_context_after_hex",
    "candidate_control_before_hex",
    "candidate_control_after_hex",
    "bridge_class",
]

ORDERED_BRIDGE_FIELDNAMES = [
    "target_id",
    "bridge_index",
    "token_index",
    "token_type",
    "run_offset_start",
    "run_offset_end",
    "segment_offset",
    "segment_end",
    "length",
    "matched_hex",
    "pre_control_hex",
    "post_control_hex",
    "run_gap_from_previous",
    "segment_gap_from_previous",
]

CONTROL_GAP_FIELDNAMES = [
    "target_id",
    "gap_index",
    "previous_token_index",
    "next_token_index",
    "previous_run_offset_end",
    "next_run_offset_start",
    "run_gap_bytes",
    "previous_segment_end",
    "next_segment_offset",
    "segment_gap_bytes",
    "control_gap_head_hex",
    "control_gap_tail_hex",
]


def int_field(row: dict[str, str], field: str, default: int = 0) -> int:
    raw = row.get(field, "")
    if raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def offsets_text(offsets: list[int]) -> str:
    return " ".join(str(offset) for offset in offsets)


def find_offsets(source: bytes, chunk: bytes, *, limit: int = 16) -> tuple[list[int], int]:
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


def exact_bytes(left: bytes, right: bytes) -> int:
    return sum(1 for source, target in zip(left, right) if source == target)


def best_segment_window(source: bytes, chunk: bytes) -> tuple[int, int]:
    if not source or not chunk or len(chunk) > len(source):
        return -1, 0
    best_offset = 0
    best_exact = -1
    limit = len(source) - len(chunk) + 1
    for offset in range(limit):
        current = exact_bytes(source[offset : offset + len(chunk)], chunk)
        if current > best_exact:
            best_offset = offset
            best_exact = current
    return best_offset, max(0, best_exact)


def bridge_class(
    token_type: str,
    length: int,
    generated: int,
    exact_segment: bool,
    best_exact: int,
) -> str:
    if exact_segment and length >= 2:
        return "strong_exact_segment"
    if exact_segment:
        return "single_byte_segment"
    if generated > 0:
        return f"generated_{token_type}"
    if best_exact > 0:
        return "partial_segment"
    return "unmapped"


def token_chunk(payload: dict[str, object], token: dict[str, str]) -> bytes:
    data = payload.get("data", b"")
    if not isinstance(data, bytes):
        return b""
    start = int_field(token, "run_offset_start", -1)
    end = int_field(token, "run_offset_end", -1)
    if start < 0 or end < start or end > len(data):
        return b""
    return data[start:end]


def build_token_bridge_rows(
    payload: dict[str, object],
    token_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    segment = payload.get("segment", b"")
    control = payload.get("control", b"")
    fragment = payload.get("fragment", b"")
    target = payload.get("target", {})
    if not isinstance(segment, bytes):
        segment = b""
    if not isinstance(control, bytes):
        control = b""
    if not isinstance(fragment, bytes):
        fragment = b""
    if not isinstance(target, dict):
        target = {}

    rows: list[dict[str, str]] = []
    for token in token_rows:
        chunk = token_chunk(payload, token)
        exact_segment_offsets, exact_segment_count = find_offsets(segment, chunk)
        exact_control_offsets, exact_control_count = find_offsets(control, chunk)
        exact_fragment_offsets, exact_fragment_count = find_offsets(fragment, chunk)
        best_offset, best_exact = best_segment_window(segment, chunk)
        selected = segment[best_offset : best_offset + len(chunk)] if best_offset >= 0 else b""
        generated = int_field(token, "generated_bytes")
        exact_segment = bool(exact_segment_offsets)
        rows.append(
            {
                "target_id": token.get("target_id", ""),
                "token_index": token.get("token_index", ""),
                "token_type": token.get("token_type", ""),
                "run_offset_start": token.get("run_offset_start", ""),
                "run_offset_end": token.get("run_offset_end", ""),
                "absolute_start": token.get("absolute_start", ""),
                "absolute_end": token.get("absolute_end", ""),
                "length": token.get("length", ""),
                "generated_bytes": token.get("generated_bytes", ""),
                "head_hex": token.get("head_hex", ""),
                "tail_hex": token.get("tail_hex", ""),
                "exact_segment_token": "1" if exact_segment else "0",
                "exact_segment_offsets": offsets_text(exact_segment_offsets),
                "exact_segment_offset_count": str(exact_segment_count),
                "exact_control_prefix_offsets": offsets_text(exact_control_offsets),
                "exact_control_prefix_offset_count": str(exact_control_count),
                "exact_fragment_offsets": offsets_text(exact_fragment_offsets),
                "exact_fragment_offset_count": str(exact_fragment_count),
                "best_segment_offset": "" if best_offset < 0 else str(best_offset),
                "best_segment_exact_bytes": str(best_exact),
                "best_segment_exact_ratio": ratio(best_exact, len(chunk)),
                "best_segment_head_hex": selected[:16].hex(),
                "best_segment_tail_hex": selected[-16:].hex() if selected else "",
                "segment_context_before_hex": (
                    segment[max(0, best_offset - 12) : best_offset].hex() if best_offset >= 0 else ""
                ),
                "segment_context_after_hex": (
                    segment[
                        best_offset + len(chunk) : min(len(segment), best_offset + len(chunk) + 12)
                    ].hex()
                    if best_offset >= 0
                    else ""
                ),
                "candidate_control_before_hex": (
                    segment[max(0, best_offset - 8) : best_offset].hex() if best_offset >= 0 else ""
                ),
                "candidate_control_after_hex": (
                    segment[
                        best_offset + len(chunk) : min(len(segment), best_offset + len(chunk) + 8)
                    ].hex()
                    if best_offset >= 0
                    else ""
                ),
                "bridge_class": bridge_class(
                    token.get("token_type", ""),
                    len(chunk),
                    generated,
                    exact_segment,
                    best_exact,
                ),
            }
        )
    return rows


def ordered_strong_bridge(
    payload: dict[str, object],
    token_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    segment = payload.get("segment", b"")
    if not isinstance(segment, bytes):
        segment = b""
    states: list[dict[str, object]] = []
    for token_order, token in enumerate(token_rows):
        chunk = token_chunk(payload, token)
        if len(chunk) < 2:
            continue
        offsets, _count = find_offsets(segment, chunk, limit=256)
        for offset in offsets:
            states.append(
                {
                    "token_order": token_order,
                    "token": token,
                    "chunk": chunk,
                    "segment_offset": offset,
                    "score": len(chunk),
                    "previous": None,
                }
            )

    states.sort(key=lambda row: (int(row["token_order"]), int(row["segment_offset"])))
    for index, state in enumerate(states):
        best_score = int(state["score"])
        best_previous: int | None = None
        token_order = int(state["token_order"])
        segment_offset = int(state["segment_offset"])
        chunk = state["chunk"]
        assert isinstance(chunk, bytes)
        for previous_index in range(index):
            previous = states[previous_index]
            previous_chunk = previous["chunk"]
            assert isinstance(previous_chunk, bytes)
            previous_end = int(previous["segment_offset"]) + len(previous_chunk)
            if int(previous["token_order"]) >= token_order or previous_end > segment_offset:
                continue
            score = int(previous["score"]) + len(chunk)
            if score > best_score:
                best_score = score
                best_previous = previous_index
        state["score"] = best_score
        state["previous"] = best_previous

    if not states:
        return []
    best_index = max(range(len(states)), key=lambda index: int(states[index]["score"]))
    chain: list[dict[str, object]] = []
    while best_index is not None:
        chain.append(states[best_index])
        best_index = states[best_index]["previous"]  # type: ignore[assignment]
    chain.reverse()

    rows: list[dict[str, str]] = []
    previous_segment_end = -1
    previous_run_end = -1
    for bridge_index, state in enumerate(chain, start=1):
        token = state["token"]
        chunk = state["chunk"]
        segment_offset = int(state["segment_offset"])
        assert isinstance(token, dict)
        assert isinstance(chunk, bytes)
        segment_end = segment_offset + len(chunk)
        run_start = int_field(token, "run_offset_start", -1)
        run_end = int_field(token, "run_offset_end", -1)
        rows.append(
            {
                "target_id": token.get("target_id", ""),
                "bridge_index": str(bridge_index),
                "token_index": token.get("token_index", ""),
                "token_type": token.get("token_type", ""),
                "run_offset_start": token.get("run_offset_start", ""),
                "run_offset_end": token.get("run_offset_end", ""),
                "segment_offset": str(segment_offset),
                "segment_end": str(segment_end),
                "length": str(len(chunk)),
                "matched_hex": chunk.hex(),
                "pre_control_hex": segment[max(0, segment_offset - 12) : segment_offset].hex(),
                "post_control_hex": segment[segment_end : min(len(segment), segment_end + 12)].hex(),
                "run_gap_from_previous": "" if previous_run_end < 0 else str(max(0, run_start - previous_run_end)),
                "segment_gap_from_previous": (
                    "" if previous_segment_end < 0 else str(max(0, segment_offset - previous_segment_end))
                ),
            }
        )
        previous_segment_end = segment_end
        previous_run_end = run_end
    return rows


def build_control_gap_rows(
    payload: dict[str, object],
    ordered_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    segment = payload.get("segment", b"")
    if not isinstance(segment, bytes):
        segment = b""
    rows: list[dict[str, str]] = []
    for gap_index, (previous, current) in enumerate(zip(ordered_rows, ordered_rows[1:]), start=1):
        previous_segment_end = int_field(previous, "segment_end", -1)
        next_segment_offset = int_field(current, "segment_offset", -1)
        previous_run_end = int_field(previous, "run_offset_end", -1)
        next_run_start = int_field(current, "run_offset_start", -1)
        gap = segment[previous_segment_end:next_segment_offset] if 0 <= previous_segment_end <= next_segment_offset else b""
        rows.append(
            {
                "target_id": current.get("target_id", ""),
                "gap_index": str(gap_index),
                "previous_token_index": previous.get("token_index", ""),
                "next_token_index": current.get("token_index", ""),
                "previous_run_offset_end": previous.get("run_offset_end", ""),
                "next_run_offset_start": current.get("run_offset_start", ""),
                "run_gap_bytes": str(max(0, next_run_start - previous_run_end))
                if previous_run_end >= 0 and next_run_start >= 0
                else "",
                "previous_segment_end": previous.get("segment_end", ""),
                "next_segment_offset": current.get("segment_offset", ""),
                "segment_gap_bytes": str(len(gap)),
                "control_gap_head_hex": gap[:32].hex(),
                "control_gap_tail_hex": gap[-32:].hex() if gap else "",
            }
        )
    return rows


def target_summary(
    payload: dict[str, object],
    tokens: list[dict[str, str]],
    token_bridge_rows: list[dict[str, str]],
    ordered_rows: list[dict[str, str]],
    control_gap_rows: list[dict[str, str]],
) -> dict[str, str]:
    target = payload.get("target", {})
    data = payload.get("data", b"")
    segment = payload.get("segment", b"")
    control = payload.get("control", b"")
    fragment = payload.get("fragment", b"")
    if not isinstance(target, dict) or not isinstance(data, bytes):
        return {}
    if not isinstance(segment, bytes):
        segment = b""
    if not isinstance(control, bytes):
        control = b""
    if not isinstance(fragment, bytes):
        fragment = b""

    exact_rows = [row for row in token_bridge_rows if row.get("exact_segment_token") == "1"]
    strong_rows = [row for row in exact_rows if int_field(row, "length") >= 2]
    generated = sum(int_field(row, "generated_bytes") for row in tokens)
    literal = sum(int_field(row, "length") for row in tokens if row.get("token_type") == "literal")
    best_exact = sum(int_field(row, "best_segment_exact_bytes") for row in token_bridge_rows)
    ordered_bytes = sum(int_field(row, "length") for row in ordered_rows)
    control_gap_bytes = sum(int_field(row, "segment_gap_bytes") for row in control_gap_rows)
    verdict = "frontier80_structural_nonzero_control_bridge_seeded"
    if not strong_rows:
        verdict = "frontier80_structural_nonzero_control_bridge_needs_anchor"
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
        "token_rows": str(len(tokens)),
        "segment_gap_bytes": str(len(segment)),
        "control_prefix_bytes": str(len(control)),
        "fragment_bytes": str(len(fragment)),
        "generated_bytes": str(generated),
        "literal_bytes": str(literal),
        "exact_segment_token_rows": str(len(exact_rows)),
        "exact_segment_token_bytes": str(sum(int_field(row, "length") for row in exact_rows)),
        "strong_exact_segment_token_rows": str(len(strong_rows)),
        "strong_exact_segment_token_bytes": str(sum(int_field(row, "length") for row in strong_rows)),
        "best_segment_token_exact_bytes": str(best_exact),
        "ordered_strong_bridge_tokens": str(len(ordered_rows)),
        "ordered_strong_bridge_bytes": str(ordered_bytes),
        "control_gap_rows": str(len(control_gap_rows)),
        "control_gap_bytes": str(control_gap_bytes),
        "verdict": verdict,
        "next_probe": "derive compact-control grammar for structural RLE/delta token gaps",
    }


def total_summary(target_rows: list[dict[str, str]], issue_count: int) -> dict[str, str]:
    target_bytes = sum(int_field(row, "length") for row in target_rows)
    best_exact = sum(int_field(row, "best_segment_token_exact_bytes") for row in target_rows)
    ordered_bytes = sum(int_field(row, "ordered_strong_bridge_bytes") for row in target_rows)
    exact_segment_bytes = sum(int_field(row, "exact_segment_token_bytes") for row in target_rows)
    strong_exact_bytes = sum(int_field(row, "strong_exact_segment_token_bytes") for row in target_rows)
    verdict = "frontier80_structural_nonzero_control_bridge_seeded"
    if strong_exact_bytes == 0:
        verdict = "frontier80_structural_nonzero_control_bridge_needs_anchor"
    return {
        "scope": "total",
        "target_runs": str(len(target_rows)),
        "target_bytes": str(target_bytes),
        "token_rows": str(sum(int_field(row, "token_rows") for row in target_rows)),
        "segment_gap_bytes": str(sum(int_field(row, "segment_gap_bytes") for row in target_rows)),
        "control_prefix_bytes": str(sum(int_field(row, "control_prefix_bytes") for row in target_rows)),
        "fragment_bytes": str(sum(int_field(row, "fragment_bytes") for row in target_rows)),
        "generated_bytes": str(sum(int_field(row, "generated_bytes") for row in target_rows)),
        "literal_bytes": str(sum(int_field(row, "literal_bytes") for row in target_rows)),
        "exact_segment_token_rows": str(sum(int_field(row, "exact_segment_token_rows") for row in target_rows)),
        "exact_segment_token_bytes": str(exact_segment_bytes),
        "strong_exact_segment_token_rows": str(
            sum(int_field(row, "strong_exact_segment_token_rows") for row in target_rows)
        ),
        "strong_exact_segment_token_bytes": str(strong_exact_bytes),
        "best_segment_token_exact_bytes": str(best_exact),
        "best_segment_token_exact_ratio": ratio(best_exact, target_bytes),
        "ordered_strong_bridge_tokens": str(
            sum(int_field(row, "ordered_strong_bridge_tokens") for row in target_rows)
        ),
        "ordered_strong_bridge_bytes": str(ordered_bytes),
        "ordered_strong_bridge_ratio": ratio(ordered_bytes, target_bytes),
        "control_gap_rows": str(sum(int_field(row, "control_gap_rows") for row in target_rows)),
        "control_gap_bytes": str(sum(int_field(row, "control_gap_bytes") for row in target_rows)),
        "control_prefix_token_rows": "0",
        "fragment_token_rows": "0",
        "issue_rows": str(issue_count),
        "review_verdict": verdict,
        "next_probe": "derive compact-control grammar for structural RLE/delta token gaps",
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
    token_bridge_rows: list[dict[str, str]],
    ordered_rows: list[dict[str, str]],
    control_gap_rows: list[dict[str, str]],
) -> str:
    payload = {
        "summary": summary,
        "targets": target_rows,
        "tokens": token_bridge_rows,
        "ordered_bridge": ordered_rows,
        "control_gaps": control_gap_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    cards = [
        ("Target bytes", summary.get("target_bytes", "0")),
        ("Token rows", summary.get("token_rows", "0")),
        ("Exact segment token bytes", summary.get("exact_segment_token_bytes", "0")),
        ("Ordered strong bridge bytes", summary.get("ordered_strong_bridge_bytes", "0")),
        ("Control gap bytes", summary.get("control_gap_bytes", "0")),
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
    body {{ margin: 0; font: 14px/1.45 system-ui, sans-serif; color: #1e2329; background: #f6f7f9; }}
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
  <div class="muted">Maps exact and generated RLE/delta tokens back to compressed segment evidence.</div>
  <div class="grid">{card_html}</div>
  <section><h2>Outputs</h2>
    <p><a href="{relative_href(output / 'summary.csv', output / 'index.html')}">summary.csv</a> ·
    <a href="{relative_href(output / 'targets.csv', output / 'index.html')}">targets.csv</a> ·
    <a href="{relative_href(output / 'token_bridge.csv', output / 'index.html')}">token_bridge.csv</a> ·
    <a href="{relative_href(output / 'ordered_bridge.csv', output / 'index.html')}">ordered_bridge.csv</a> ·
    <a href="{relative_href(output / 'control_gaps.csv', output / 'index.html')}">control_gaps.csv</a></p>
  </section>
  <section><h2>Targets</h2>{render_table(target_rows, TARGET_FIELDNAMES)}</section>
  <section><h2>Ordered Strong Bridge</h2>{render_table(ordered_rows, ORDERED_BRIDGE_FIELDNAMES)}</section>
  <section><h2>Control Gaps</h2>{render_table(control_gap_rows, CONTROL_GAP_FIELDNAMES)}</section>
  <section><h2>Token Bridge</h2>{render_table(token_bridge_rows, TOKEN_BRIDGE_FIELDNAMES)}</section>
</main>
<script type="application/json" id="control-bridge-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def group_tokens(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        grouped.setdefault(row.get("target_id", ""), []).append(row)
    for token_rows in grouped.values():
        token_rows.sort(key=lambda row: int_field(row, "token_index"))
    return grouped


def write_report(args: argparse.Namespace) -> dict[str, str]:
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    run_rows = read_csv(args.runs)
    manifest_rows = read_csv(args.manifest)
    clean_rows = read_csv(args.clean_fixtures)
    tokens_by_target = group_tokens(read_csv(args.tokens))
    payloads = load_target_payloads(select_largest_targets(run_rows, issues), manifest_rows, clean_rows, issues)

    target_rows: list[dict[str, str]] = []
    token_bridge_rows: list[dict[str, str]] = []
    ordered_rows: list[dict[str, str]] = []
    control_gap_rows: list[dict[str, str]] = []
    for payload in payloads:
        target = payload.get("target", {})
        if not isinstance(target, dict):
            continue
        target_id = target.get("target_id", "")
        token_rows = tokens_by_target.get(target_id, [])
        if not token_rows:
            issues.append(f"{target_id}:missing_token_rows")
        bridge_rows = build_token_bridge_rows(payload, token_rows)
        ordered = ordered_strong_bridge(payload, token_rows)
        gaps = build_control_gap_rows(payload, ordered)
        summary_row = target_summary(payload, token_rows, bridge_rows, ordered, gaps)
        if summary_row:
            target_rows.append(summary_row)
        token_bridge_rows.extend(bridge_rows)
        ordered_rows.extend(ordered)
        control_gap_rows.extend(gaps)

    summary = total_summary(target_rows, len(issues))
    write_csv(output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output / "targets.csv", TARGET_FIELDNAMES, target_rows)
    write_csv(output / "token_bridge.csv", TOKEN_BRIDGE_FIELDNAMES, token_bridge_rows)
    write_csv(output / "ordered_bridge.csv", ORDERED_BRIDGE_FIELDNAMES, ordered_rows)
    write_csv(output / "control_gaps.csv", CONTROL_GAP_FIELDNAMES, control_gap_rows)
    (output / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""))
    (output / "index.html").write_text(
        build_html(output, args.title, summary, target_rows, token_bridge_rows, ordered_rows, control_gap_rows)
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Map structural Frontier80 RLE/delta token plans to segment-control evidence."
    )
    parser.add_argument("--runs", type=Path, default=DEFAULT_RUNS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--clean-fixtures", type=Path, default=DEFAULT_CLEAN_FIXTURES)
    parser.add_argument("--tokens", type=Path, default=DEFAULT_TOKENS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Structural Nonzero Control Bridge Probe",
    )
    args = parser.parse_args()
    summary = write_report(args)
    print(f"Target bytes: {summary['target_bytes']}")
    print(f"Token rows: {summary['token_rows']}")
    print(f"Exact segment token bytes: {summary['exact_segment_token_bytes']}")
    print(f"Ordered strong bridge bytes: {summary['ordered_strong_bridge_bytes']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
