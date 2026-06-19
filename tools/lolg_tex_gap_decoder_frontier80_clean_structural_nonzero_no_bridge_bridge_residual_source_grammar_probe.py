#!/usr/bin/env python3
"""Build source grammar rows for bridge residual intervals after no-bridge replay."""

from __future__ import annotations

import argparse
import html
import json
from collections import Counter
from pathlib import Path

from lolg_tex_gap_opcode_probe import relative_href, write_csv
from lolg_tex_gap_decoder_frontier80_clean_structural_nonzero_producer_probe import (
    DEFAULT_CLEAN_FIXTURES,
    DEFAULT_MANIFEST,
    load_target_payloads,
    ratio,
    read_csv,
)
from lolg_tex_gap_decoder_frontier80_clean_structural_nonzero_rle_delta_parser_probe import (
    choose_tokens,
    dominant_class,
    token_delta_signature,
)
from lolg_tex_gap_decoder_frontier80_clean_structural_nonzero_compact_control_grammar_probe import (
    int_field,
)


DEFAULT_INTEGRATED_TARGETS = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_compact_control_integrated_replay_probe/targets.csv"
)
DEFAULT_BRIDGE_RESIDUAL_INTERVAL_MAP_SUMMARY = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_no_bridge_bridge_residual_interval_map_probe/summary.csv"
)
DEFAULT_BRIDGE_RESIDUAL_INTERVALS = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_no_bridge_bridge_residual_interval_map_probe/residual_intervals.csv"
)
DEFAULT_OUTPUT = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_no_bridge_bridge_residual_source_grammar_probe"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "selected_target_runs",
    "selected_target_bytes",
    "coverage_bytes",
    "residual_target_runs",
    "residual_intervals",
    "residual_bytes",
    "prefix_residual_bytes",
    "suffix_residual_bytes",
    "token_rows",
    "repeat_tokens",
    "repeat_bytes",
    "delta_tokens",
    "delta_bytes",
    "literal_tokens",
    "literal_bytes",
    "seed_bytes",
    "generated_bytes",
    "generated_ratio",
    "exact_replay_bytes",
    "exact_replay_ratio",
    "full_segment_residual_spans",
    "full_segment_residual_bytes",
    "full_control_residual_spans",
    "full_control_residual_bytes",
    "full_fragment_residual_spans",
    "full_fragment_residual_bytes",
    "best_segment_subspan_bytes",
    "best_control_subspan_bytes",
    "best_fragment_subspan_bytes",
    "token_full_segment_bytes",
    "source_candidate_rows",
    "source_candidate_bytes",
    "top_token_signatures",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

RESIDUAL_FIELDNAMES = [
    "target_id",
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "span_index",
    "run_index",
    "residual_index",
    "run_offset_start",
    "run_offset_end",
    "absolute_start",
    "absolute_end",
    "length",
    "position_class",
    "previous_coverage_kind",
    "next_coverage_kind",
    "token_rows",
    "token_bytes",
    "repeat_bytes",
    "delta_bytes",
    "literal_bytes",
    "seed_bytes",
    "generated_bytes",
    "generated_ratio",
    "exact_replay_bytes",
    "exact_replay_ratio",
    "segment_exact_offset",
    "control_exact_offset",
    "fragment_exact_offset",
    "best_segment_length",
    "best_segment_offset",
    "best_control_length",
    "best_control_offset",
    "best_fragment_length",
    "best_fragment_offset",
    "token_signature",
    "verdict",
    "next_probe",
]

TOKEN_FIELDNAMES = [
    "target_id",
    "residual_index",
    "token_index",
    "token_type",
    "residual_offset_start",
    "residual_offset_end",
    "run_offset_start",
    "run_offset_end",
    "absolute_start",
    "absolute_end",
    "length",
    "seed_hex",
    "repeat_value_hex",
    "delta_signature",
    "generated_bytes",
    "source_role",
    "dominant_value_class",
    "exact_segment_token",
    "exact_control_token",
    "exact_fragment_token",
    "head_hex",
    "tail_hex",
    "exact_target_slice",
    "verdict",
]

SOURCE_FIELDNAMES = [
    "target_id",
    "residual_index",
    "token_index",
    "source_scope",
    "source_name",
    "source_kind",
    "source_offset",
    "target_offset_start",
    "target_offset_end",
    "run_offset_start",
    "run_offset_end",
    "length",
    "source_hex",
    "guard",
]


def hex_byte(value: int) -> str:
    return f"0x{value:02x}"


def counter_text(counter: Counter[str]) -> str:
    return "|".join(f"{key}:{count}" for key, count in counter.most_common(16))


def indexed_targets(rows: list[dict[str, str]], target_ids: set[str]) -> list[dict[str, str]]:
    return [row for row in rows if row.get("target_id", "") in target_ids]


def longest_subchunk(source: bytes, chunk: bytes, *, min_length: int) -> tuple[int, int, int, int]:
    for length in range(len(chunk), min_length - 1, -1):
        for target_start in range(0, len(chunk) - length + 1):
            subchunk = chunk[target_start : target_start + length]
            source_offset = source.find(subchunk)
            if source_offset >= 0:
                return target_start, target_start + length, source_offset, length
    return -1, -1, -1, 0


def source_role(token_type: str, length: int) -> str:
    if token_type == "repeat":
        return "seed_plus_repeat_generated"
    if token_type == "delta":
        return "seed_plus_delta_generated"
    if length > 1:
        return "literal_seed_group"
    return "literal_seed"


def build_token_rows(
    interval: dict[str, str],
    chunk: bytes,
    base_start: int,
    args: argparse.Namespace,
) -> list[dict[str, str]]:
    target_id = interval.get("target_id", "")
    residual_index = int_field(interval, "residual_index")
    run_start = int_field(interval, "run_offset_start")
    absolute_start = int_field(interval, "absolute_start")
    rows: list[dict[str, str]] = []
    for token_index, (token_type, start, end) in enumerate(
        choose_tokens(
            chunk,
            min_repeat=args.min_repeat,
            min_delta=args.min_delta,
            max_delta=args.max_delta,
        ),
        start=1,
    ):
        token = chunk[start:end]
        generated = len(token) - 1 if token_type in {"repeat", "delta"} else 0
        rows.append(
            {
                "target_id": target_id,
                "residual_index": str(residual_index),
                "token_index": str(token_index),
                "token_type": token_type,
                "residual_offset_start": str(start),
                "residual_offset_end": str(end),
                "run_offset_start": str(run_start + start),
                "run_offset_end": str(run_start + end),
                "absolute_start": str(absolute_start + start),
                "absolute_end": str(absolute_start + end),
                "length": str(len(token)),
                "seed_hex": hex_byte(token[0]) if token else "",
                "repeat_value_hex": hex_byte(token[0]) if token_type == "repeat" and token else "",
                "delta_signature": token_delta_signature(token) if token_type == "delta" else "",
                "generated_bytes": str(generated),
                "source_role": source_role(token_type, len(token)),
                "dominant_value_class": dominant_class(token),
                "exact_segment_token": "0",
                "exact_control_token": "0",
                "exact_fragment_token": "0",
                "head_hex": token[:16].hex(),
                "tail_hex": token[-16:].hex() if token else "",
                "exact_target_slice": "0",
                "verdict": "bridge_residual_source_token_pending",
            }
        )
    return rows


def replay_from_tokens(data: bytes, token_rows: list[dict[str, str]]) -> tuple[bytes, bool]:
    replay = bytearray()
    previous_end = -1
    contiguous = True
    for row in sorted(token_rows, key=lambda token: int_field(token, "token_index")):
        start = int_field(row, "run_offset_start", -1)
        end = int_field(row, "run_offset_end", -1)
        if previous_end >= 0 and start != previous_end:
            contiguous = False
        previous_end = end
        if 0 <= start <= end <= len(data):
            replay.extend(data[start:end])
        else:
            contiguous = False
    return bytes(replay), contiguous


def validate_tokens(
    data: bytes,
    segment: bytes,
    control: bytes,
    fragment: bytes,
    token_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for token in token_rows:
        row = dict(token)
        start = int_field(row, "run_offset_start", -1)
        end = int_field(row, "run_offset_end", -1)
        expected_length = int_field(row, "length")
        chunk = data[start:end] if 0 <= start <= end <= len(data) else b""
        exact = (
            len(chunk) == expected_length
            and chunk[:16].hex() == row.get("head_hex", "")
            and (chunk[-16:].hex() if chunk else "") == row.get("tail_hex", "")
        )
        row["exact_segment_token"] = "1" if segment.find(chunk) >= 0 and chunk else "0"
        row["exact_control_token"] = "1" if control.find(chunk) >= 0 and chunk else "0"
        row["exact_fragment_token"] = "1" if fragment.find(chunk) >= 0 and chunk else "0"
        row["exact_target_slice"] = "1" if exact else "0"
        row["verdict"] = "bridge_residual_source_token_exact" if exact else "bridge_residual_source_token_mismatch"
        rows.append(row)
    return rows


def source_candidate_rows(
    interval: dict[str, str],
    token_rows: list[dict[str, str]],
    chunk: bytes,
    sources: list[tuple[str, bytes]],
    args: argparse.Namespace,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    run_start = int_field(interval, "run_offset_start")
    for source_name, source in sources:
        target_start, target_end, source_offset, length = longest_subchunk(
            source,
            chunk,
            min_length=args.min_source_length,
        )
        if length > 0:
            exact = target_start == 0 and length == len(chunk)
            rows.append(
                {
                    "target_id": interval.get("target_id", ""),
                    "residual_index": interval.get("residual_index", ""),
                    "token_index": "",
                    "source_scope": "residual",
                    "source_name": source_name,
                    "source_kind": "full_residual_exact" if exact else "partial_residual_exact",
                    "source_offset": str(source_offset),
                    "target_offset_start": str(target_start),
                    "target_offset_end": str(target_end),
                    "run_offset_start": str(run_start + target_start),
                    "run_offset_end": str(run_start + target_end),
                    "length": str(length),
                    "source_hex": chunk[target_start:target_end].hex(),
                    "guard": f"{source_name}_residual_longest_subchunk_ge{args.min_source_length}",
                }
            )
        for token in token_rows:
            token_start = int_field(token, "residual_offset_start")
            token_end = int_field(token, "residual_offset_end")
            token_chunk = chunk[token_start:token_end]
            token_offset = source.find(token_chunk)
            if token_offset < 0 or len(token_chunk) < args.min_source_length:
                continue
            rows.append(
                {
                    "target_id": interval.get("target_id", ""),
                    "residual_index": interval.get("residual_index", ""),
                    "token_index": token.get("token_index", ""),
                    "source_scope": "token",
                    "source_name": source_name,
                    "source_kind": "full_token_exact",
                    "source_offset": str(token_offset),
                    "target_offset_start": str(token_start),
                    "target_offset_end": str(token_end),
                    "run_offset_start": token.get("run_offset_start", ""),
                    "run_offset_end": token.get("run_offset_end", ""),
                    "length": str(len(token_chunk)),
                    "source_hex": token_chunk.hex(),
                    "guard": f"{source_name}_token_exact_ge{args.min_source_length}",
                }
            )
    return rows


def token_signature(token_rows: list[dict[str, str]]) -> str:
    return ".".join(
        f"{row.get('token_type', '')[0].lower()}{row.get('length', '0')}"
        for row in sorted(token_rows, key=lambda row: int_field(row, "token_index"))[:48]
    )


def residual_summary(
    interval: dict[str, str],
    data: bytes,
    segment: bytes,
    control: bytes,
    fragment: bytes,
    args: argparse.Namespace,
    issues: list[str],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    start = int_field(interval, "run_offset_start", -1)
    end = int_field(interval, "run_offset_end", -1)
    expected_length = int_field(interval, "length")
    chunk = data[start:end] if 0 <= start <= end <= len(data) else b""
    if len(chunk) != expected_length:
        issues.append(
            f"{interval.get('target_id', '')}:bridge_residual_window_size_mismatch:"
            f"{interval.get('residual_index', '')}"
        )
    if chunk[:16].hex() != interval.get("head_hex", ""):
        issues.append(
            f"{interval.get('target_id', '')}:bridge_residual_head_mismatch:"
            f"{interval.get('residual_index', '')}"
        )
    if (chunk[-16:].hex() if chunk else "") != interval.get("tail_hex", ""):
        issues.append(
            f"{interval.get('target_id', '')}:bridge_residual_tail_mismatch:"
            f"{interval.get('residual_index', '')}"
        )

    token_rows = validate_tokens(
        data,
        segment,
        control,
        fragment,
        build_token_rows(interval, chunk, start, args),
    )
    replay, contiguous = replay_from_tokens(data, token_rows)
    exact = sum(1 for left, right in zip(replay, chunk) if left == right) if len(replay) == len(chunk) else 0
    token_bytes = sum(int_field(row, "length") for row in token_rows)
    if token_bytes != expected_length:
        issues.append(
            f"{interval.get('target_id', '')}:bridge_residual_token_size_mismatch:"
            f"{interval.get('residual_index', '')}"
        )
    if not contiguous:
        issues.append(
            f"{interval.get('target_id', '')}:bridge_residual_token_contiguity_mismatch:"
            f"{interval.get('residual_index', '')}"
        )

    sources = [("segment", segment), ("control", control), ("fragment", fragment)]
    source_rows = source_candidate_rows(interval, token_rows, chunk, sources, args)
    best_by_source = {
        source_name: longest_subchunk(source, chunk, min_length=args.min_source_length)
        for source_name, source in sources
    }
    repeat_rows = [row for row in token_rows if row.get("token_type") == "repeat"]
    delta_rows = [row for row in token_rows if row.get("token_type") == "delta"]
    literal_rows = [row for row in token_rows if row.get("token_type") == "literal"]
    segment_exact = segment.find(chunk)
    control_exact = control.find(chunk)
    fragment_exact = fragment.find(chunk)
    verdict = "bridge_residual_source_grammar_exact"
    next_probe = "promote bridge residual source grammar into structural replay"
    if exact != expected_length or not contiguous:
        verdict = "bridge_residual_source_grammar_mismatch"
        next_probe = "review bridge residual source grammar mismatches"
    row = {
        "target_id": interval.get("target_id", ""),
        "rank": interval.get("rank", ""),
        "archive": interval.get("archive", ""),
        "archive_tag": interval.get("archive_tag", ""),
        "pcx_name": interval.get("pcx_name", ""),
        "frontier_id": interval.get("frontier_id", ""),
        "span_index": interval.get("span_index", ""),
        "run_index": interval.get("run_index", ""),
        "residual_index": interval.get("residual_index", ""),
        "run_offset_start": interval.get("run_offset_start", ""),
        "run_offset_end": interval.get("run_offset_end", ""),
        "absolute_start": interval.get("absolute_start", ""),
        "absolute_end": interval.get("absolute_end", ""),
        "length": str(expected_length),
        "position_class": interval.get("position_class", ""),
        "previous_coverage_kind": interval.get("previous_coverage_kind", ""),
        "next_coverage_kind": interval.get("next_coverage_kind", ""),
        "token_rows": str(len(token_rows)),
        "token_bytes": str(token_bytes),
        "repeat_bytes": str(sum(int_field(row, "length") for row in repeat_rows)),
        "delta_bytes": str(sum(int_field(row, "length") for row in delta_rows)),
        "literal_bytes": str(sum(int_field(row, "length") for row in literal_rows)),
        "seed_bytes": str(len(token_rows)),
        "generated_bytes": str(sum(int_field(row, "generated_bytes") for row in token_rows)),
        "generated_ratio": ratio(sum(int_field(row, "generated_bytes") for row in token_rows), expected_length),
        "exact_replay_bytes": str(exact),
        "exact_replay_ratio": ratio(exact, expected_length),
        "segment_exact_offset": "" if segment_exact < 0 else str(segment_exact),
        "control_exact_offset": "" if control_exact < 0 else str(control_exact),
        "fragment_exact_offset": "" if fragment_exact < 0 else str(fragment_exact),
        "best_segment_length": str(best_by_source["segment"][3]),
        "best_segment_offset": "" if best_by_source["segment"][2] < 0 else str(best_by_source["segment"][2]),
        "best_control_length": str(best_by_source["control"][3]),
        "best_control_offset": "" if best_by_source["control"][2] < 0 else str(best_by_source["control"][2]),
        "best_fragment_length": str(best_by_source["fragment"][3]),
        "best_fragment_offset": "" if best_by_source["fragment"][2] < 0 else str(best_by_source["fragment"][2]),
        "token_signature": token_signature(token_rows),
        "verdict": verdict,
        "next_probe": next_probe,
    }
    return row, token_rows, source_rows


def total_summary(
    interval_map_summary: dict[str, str],
    residual_rows: list[dict[str, str]],
    token_rows: list[dict[str, str]],
    source_rows: list[dict[str, str]],
    issue_count: int,
) -> dict[str, str]:
    residual_bytes = sum(int_field(row, "length") for row in residual_rows)
    exact = sum(int_field(row, "exact_replay_bytes") for row in residual_rows)
    repeat_rows = [row for row in token_rows if row.get("token_type") == "repeat"]
    delta_rows = [row for row in token_rows if row.get("token_type") == "delta"]
    literal_rows = [row for row in token_rows if row.get("token_type") == "literal"]
    full_segment = [row for row in residual_rows if row.get("segment_exact_offset", "") != ""]
    full_control = [row for row in residual_rows if row.get("control_exact_offset", "") != ""]
    full_fragment = [row for row in residual_rows if row.get("fragment_exact_offset", "") != ""]
    token_signatures = Counter(row.get("token_signature", "") for row in residual_rows if row.get("token_signature", ""))
    expected_residual = int_field(interval_map_summary, "residual_bytes")
    verdict = "frontier80_structural_no_bridge_bridge_residual_source_grammar_ready"
    next_probe = "promote bridge residual source grammar into structural replay"
    if issue_count or exact != residual_bytes or (expected_residual and residual_bytes != expected_residual):
        verdict = "frontier80_structural_no_bridge_bridge_residual_source_grammar_issues"
        next_probe = "review bridge residual source grammar issues"
    return {
        "scope": "total",
        "selected_target_runs": interval_map_summary.get("selected_target_runs", "0"),
        "selected_target_bytes": interval_map_summary.get("selected_target_bytes", "0"),
        "coverage_bytes": interval_map_summary.get("coverage_bytes", "0"),
        "residual_target_runs": str(
            len({row.get("target_id", "") for row in residual_rows if int_field(row, "length") > 0})
        ),
        "residual_intervals": str(len(residual_rows)),
        "residual_bytes": str(residual_bytes),
        "prefix_residual_bytes": str(
            sum(int_field(row, "length") for row in residual_rows if row.get("position_class") == "prefix")
        ),
        "suffix_residual_bytes": str(
            sum(int_field(row, "length") for row in residual_rows if row.get("position_class") == "suffix")
        ),
        "token_rows": str(len(token_rows)),
        "repeat_tokens": str(len(repeat_rows)),
        "repeat_bytes": str(sum(int_field(row, "length") for row in repeat_rows)),
        "delta_tokens": str(len(delta_rows)),
        "delta_bytes": str(sum(int_field(row, "length") for row in delta_rows)),
        "literal_tokens": str(len(literal_rows)),
        "literal_bytes": str(sum(int_field(row, "length") for row in literal_rows)),
        "seed_bytes": str(len(token_rows)),
        "generated_bytes": str(sum(int_field(row, "generated_bytes") for row in token_rows)),
        "generated_ratio": ratio(sum(int_field(row, "generated_bytes") for row in token_rows), residual_bytes),
        "exact_replay_bytes": str(exact),
        "exact_replay_ratio": ratio(exact, residual_bytes),
        "full_segment_residual_spans": str(len(full_segment)),
        "full_segment_residual_bytes": str(sum(int_field(row, "length") for row in full_segment)),
        "full_control_residual_spans": str(len(full_control)),
        "full_control_residual_bytes": str(sum(int_field(row, "length") for row in full_control)),
        "full_fragment_residual_spans": str(len(full_fragment)),
        "full_fragment_residual_bytes": str(sum(int_field(row, "length") for row in full_fragment)),
        "best_segment_subspan_bytes": str(sum(int_field(row, "best_segment_length") for row in residual_rows)),
        "best_control_subspan_bytes": str(sum(int_field(row, "best_control_length") for row in residual_rows)),
        "best_fragment_subspan_bytes": str(sum(int_field(row, "best_fragment_length") for row in residual_rows)),
        "token_full_segment_bytes": str(
            sum(int_field(row, "length") for row in token_rows if row.get("exact_segment_token") == "1")
        ),
        "source_candidate_rows": str(len(source_rows)),
        "source_candidate_bytes": str(sum(int_field(row, "length") for row in source_rows)),
        "top_token_signatures": counter_text(token_signatures),
        "issue_rows": str(issue_count),
        "review_verdict": verdict,
        "next_probe": next_probe,
    }


def render_table(rows: list[dict[str, str]], fieldnames: list[str], *, limit: int = 100) -> str:
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
    residual_rows: list[dict[str, str]],
    token_rows: list[dict[str, str]],
    source_rows: list[dict[str, str]],
) -> str:
    payload = {"summary": summary, "residuals": residual_rows, "tokens": token_rows, "sources": source_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    cards = [
        ("Residual bytes", summary.get("residual_bytes", "0")),
        ("Token rows", summary.get("token_rows", "0")),
        ("Generated bytes", summary.get("generated_bytes", "0")),
        ("Exact replay", summary.get("exact_replay_ratio", "0")),
        ("Segment full bytes", summary.get("full_segment_residual_bytes", "0")),
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
  <div class="muted">Builds exact token and source-candidate grammar for bridge residual intervals.</div>
  <div class="grid">{card_html}</div>
  <section><h2>Outputs</h2>
    <p><a href="{relative_href(output / 'summary.csv', output / 'index.html')}">summary.csv</a> ·
    <a href="{relative_href(output / 'residuals.csv', output / 'index.html')}">residuals.csv</a> ·
    <a href="{relative_href(output / 'tokens.csv', output / 'index.html')}">tokens.csv</a> ·
    <a href="{relative_href(output / 'source_candidates.csv', output / 'index.html')}">source_candidates.csv</a></p>
  </section>
  <section><h2>Residuals</h2>{render_table(residual_rows, RESIDUAL_FIELDNAMES)}</section>
  <section><h2>Tokens</h2>{render_table(token_rows, TOKEN_FIELDNAMES)}</section>
  <section><h2>Source Candidates</h2>{render_table(source_rows, SOURCE_FIELDNAMES)}</section>
</main>
<script type="application/json" id="bridge-residual-source-grammar-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> dict[str, str]:
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    interval_map_summary_rows = read_csv(args.bridge_residual_interval_map_summary)
    interval_map_summary = interval_map_summary_rows[0] if interval_map_summary_rows else {}
    intervals = read_csv(args.bridge_residual_intervals)
    target_ids = {row.get("target_id", "") for row in intervals}
    targets = indexed_targets(read_csv(args.integrated_targets), target_ids)
    payloads = load_target_payloads(targets, read_csv(args.manifest), read_csv(args.clean_fixtures), issues)
    payload_by_target = {
        payload["target"].get("target_id", ""): payload
        for payload in payloads
        if isinstance(payload.get("target"), dict)
    }

    residual_rows: list[dict[str, str]] = []
    token_rows: list[dict[str, str]] = []
    source_rows: list[dict[str, str]] = []
    for interval in intervals:
        target_id = interval.get("target_id", "")
        payload = payload_by_target.get(target_id)
        if not payload:
            issues.append(f"{target_id}:missing_payload_for_bridge_residual_source_grammar")
            continue
        data = payload.get("data", b"")
        segment = payload.get("segment", b"")
        control = payload.get("control", b"")
        fragment = payload.get("fragment", b"")
        if not isinstance(data, bytes):
            data = b""
        if not isinstance(segment, bytes):
            segment = b""
        if not isinstance(control, bytes):
            control = b""
        if not isinstance(fragment, bytes):
            fragment = b""
        residual_row, interval_tokens, interval_sources = residual_summary(
            interval,
            data,
            segment,
            control,
            fragment,
            args,
            issues,
        )
        residual_rows.append(residual_row)
        token_rows.extend(interval_tokens)
        source_rows.extend(interval_sources)

    summary = total_summary(interval_map_summary, residual_rows, token_rows, source_rows, len(issues))
    write_csv(output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output / "residuals.csv", RESIDUAL_FIELDNAMES, residual_rows)
    write_csv(output / "tokens.csv", TOKEN_FIELDNAMES, token_rows)
    write_csv(output / "source_candidates.csv", SOURCE_FIELDNAMES, source_rows)
    (output / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""))
    (output / "index.html").write_text(build_html(output, args.title, summary, residual_rows, token_rows, source_rows))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build source grammar rows for bridge residual intervals after no-bridge replay."
    )
    parser.add_argument("--integrated-targets", type=Path, default=DEFAULT_INTEGRATED_TARGETS)
    parser.add_argument(
        "--bridge-residual-interval-map-summary",
        type=Path,
        default=DEFAULT_BRIDGE_RESIDUAL_INTERVAL_MAP_SUMMARY,
    )
    parser.add_argument("--bridge-residual-intervals", type=Path, default=DEFAULT_BRIDGE_RESIDUAL_INTERVALS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--clean-fixtures", type=Path, default=DEFAULT_CLEAN_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--min-repeat", type=int, default=2)
    parser.add_argument("--min-delta", type=int, default=4)
    parser.add_argument("--max-delta", type=int, default=2)
    parser.add_argument("--min-source-length", type=int, default=2)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Structural No-Bridge Bridge Residual Source Grammar",
    )
    args = parser.parse_args()
    summary = write_report(args)
    print(f"Residual bytes: {summary['residual_bytes']}")
    print(f"Token rows: {summary['token_rows']}")
    print(f"Generated bytes: {summary['generated_bytes']}")
    print(f"Exact replay ratio: {summary['exact_replay_ratio']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
