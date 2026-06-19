#!/usr/bin/env python3
"""Probe renderer candidates for LLSE-signature large .tex bodies."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image

from export_shp import read_palette
from export_te_span_previews import make_sheet, render_indexed
from lolg_tex_large_body_control_grammar_probe import int_value, read_mix_entry, write_csv
from probe_te_span_decode import decode_span
from score_te_raw_layouts import row_score
from trace_te_stream import trace_payload


DEFAULT_OUTPUT = Path("output/tex_large_llse_signature_control_probe")
DEFAULT_SEGMENTS = Path("output/tex_large_rejected_decoder_profile/segments.csv")
DEFAULT_BODY_CONTROL_SEGMENTS = Path("output/tex_large_body_control_grammar_probe/segments.csv")
DEFAULT_TRACE_CANDIDATES = Path("output/tex_large_body_control_grammar_probe/trace_candidates.csv")
DEFAULT_MODE_CHOICES = Path("reports/te_guarded_cmd20_v10_riskaware_markerknownsymadv_plus_puddle.tsv")
DEFAULT_PALETTE = Path("extracted/LOCAL/7231c8f9.pal")
DEFAULT_MIX_ENTRY_INDEX = 2
TARGET_CONTROL_PATH = "llse_signature"
TARGET_SIZE = (1920, 1080)
HIGH_ARG2_SIGNATURES = {0xE0, 0xFC, 0xFD, 0xFE, 0xFF}

FALLBACK_MODES = [
    "filter",
    "low_skip",
    "zero_skip",
    "cmd20_skip4_markerknown",
    "cmd20_sig_skip4_markerknown",
    "op4_skip1",
    "op4_skip2",
    "op4_cmd20_skip4",
    "op4_cmd20_skip4_markerknown",
    "op4_cmd20_sig_skip4",
    "op4_cmd20_sig_skip4_markerknown",
    "cmd20_arg2_f8_safe_dy_skip4",
    "cmd20_arg2_f8_safe_dy_skip4_markerknown",
    "cmd20_arg2_fc_safe_dy_skip4",
    "op4_cmd20_arg2_f8_safe_dy_skip4",
    "op4_cmd20_arg2_f8_safe_dy_skip4_markerknown",
    "op4_cmd20_arg2_fc_safe_dy_skip4",
    "op4_cmd20_arg2_fc_safe_dy_skip4_markerknown",
    "op4lo13_cmd20_arg2_fc_safe_dy_skip4_markerknown",
]

SUMMARY_FIELDNAMES = [
    "scope",
    "segment_rows",
    "offset_rows",
    "mode_rows",
    "candidate_rows",
    "native_previews",
    "fullhd_previews",
    "nonblank_previews",
    "sheet_path",
    "best_offset",
    "best_offset_reason",
    "best_mode",
    "best_score",
    "best_filled_ratio",
    "best_final_y",
    "best_trace_fingerprint",
    "max_non_noisy_score",
    "issue_rows",
    "probe_verdict",
    "next_action",
]

CANDIDATE_FIELDNAMES = [
    "rank",
    "candidate_id",
    "segment_id",
    "archive",
    "archive_tag",
    "pcx_name",
    "control_path",
    "offset",
    "offset_reason",
    "mode",
    "mode_source",
    "width",
    "height",
    "payload_bytes",
    "score",
    "filled_ratio",
    "visible_pixels",
    "unique_colors",
    "emitted",
    "overdraw",
    "final_x",
    "final_y",
    "markerknown_skips",
    "high_arg2_skips",
    "zero_signature_seen",
    "zero_signature_skipped",
    "trace_events",
    "cmd20_events",
    "op4_events",
    "control_events",
    "pixel_events",
    "sig_skip",
    "sig_noop",
    "sig_high_arg2_skip",
    "sig_zero_skip",
    "op4_skip",
    "markerknown_control",
    "trace_fingerprint",
    "top_op4_bytes",
    "top_cmd20_arg2",
    "native_preview_path",
    "native_preview_exists",
    "fullhd_preview_path",
    "fullhd_preview_exists",
    "issues",
]

MODE_FIELDNAMES = [
    "rank",
    "mode",
    "rows",
    "best_score",
    "avg_score",
    "max_score",
    "best_offset",
    "best_offset_reason",
    "min_filled_ratio",
    "total_cmd20_events",
    "total_op4_events",
    "total_sig_skip",
    "total_sig_noop",
    "total_sig_high_arg2_skip",
    "total_sig_zero_skip",
    "total_op4_skip",
    "top_op4_bytes",
    "top_cmd20_arg2",
    "verdict",
]

OFFSET_FIELDNAMES = [
    "rank",
    "offset",
    "offset_reason",
    "rows",
    "best_mode",
    "best_score",
    "avg_score",
    "min_filled_ratio",
    "best_trace_fingerprint",
    "verdict",
]


def read_csv(path: Path, *, delimiter: str = ",") -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter=delimiter))


def safe_name(value: str) -> str:
    clean = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in value)
    return clean.strip("._") or "unnamed"


def float_text(value: object, default: float = 0.0) -> float:
    try:
        return float(str(value)) if value not in (None, "") else default
    except ValueError:
        return default


def visible_ratio(pixels: bytes) -> float:
    return sum(1 for pixel in pixels if pixel) / max(1, len(pixels))


def compact_counter(counter: Counter[str], *, limit: int = 8) -> str:
    return "|".join(f"{key}:{count}" for key, count in counter.most_common(limit))


def merge_counter_text(rows: list[dict[str, str]], field: str) -> Counter[str]:
    counter: Counter[str] = Counter()
    for row in rows:
        for item in row.get(field, "").split("|"):
            if not item or ":" not in item:
                continue
            key, value = item.rsplit(":", 1)
            try:
                counter[key] += int(value)
            except ValueError:
                continue
    return counter


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    try:
        return os.path.relpath(Path(path_text), base_dir)
    except ValueError:
        return str(path_text)


def fullhd_image(image: Image.Image) -> Image.Image:
    source = image.convert("RGBA")
    scale = min(TARGET_SIZE[0] // source.width, TARGET_SIZE[1] // source.height)
    scale = max(1, scale)
    scaled = source.resize((source.width * scale, source.height * scale), Image.Resampling.NEAREST)
    canvas = Image.new("RGBA", TARGET_SIZE, (0, 0, 0, 255))
    x = (TARGET_SIZE[0] - scaled.width) // 2
    y = (TARGET_SIZE[1] - scaled.height) // 2
    canvas.alpha_composite(scaled, (x, y))
    return canvas


def segment_key(row: dict[str, str]) -> str:
    return row.get("segment_id", "")


def parse_offsets(text: str) -> list[tuple[int, str]]:
    output: list[tuple[int, str]] = []
    seen: set[int] = set()
    for item in text.split("|"):
        if ":" not in item:
            continue
        raw_offset, reason = item.split(":", 1)
        try:
            offset = int(raw_offset, 0)
        except ValueError:
            continue
        if offset in seen:
            continue
        seen.add(offset)
        output.append((offset, reason))
    return output


def load_modes(mode_choices: Path) -> tuple[list[str], dict[str, str]]:
    sources: dict[str, str] = {}
    for mode in FALLBACK_MODES:
        sources[mode] = "fallback"
    if mode_choices.exists():
        for row in read_csv(mode_choices, delimiter="\t"):
            mode = row.get("mode", "")
            if not mode:
                continue
            if mode in sources:
                if "choice_report" not in sources[mode]:
                    sources[mode] = f"{sources[mode]}+choice_report"
            else:
                sources[mode] = "choice_report"
    return sorted(sources), sources


def offsets_for_segment(
    source: dict[str, str],
    body_control_rows: list[dict[str, str]],
    trace_rows: list[dict[str, str]],
    max_offsets: int,
) -> list[tuple[int, str]]:
    segment_id = segment_key(source)
    candidates: dict[int, list[str]] = defaultdict(list)
    for row in body_control_rows:
        if row.get("segment_id") != segment_id:
            continue
        for offset, reason in parse_offsets(row.get("candidate_offsets", "")):
            candidates[offset].append(reason)
    for row in trace_rows:
        if row.get("segment_id") != segment_id:
            continue
        offset = int_value(row, "offset")
        reason = row.get("offset_reason", "")
        candidates[offset].append(reason or "trace_candidate")
    if not candidates:
        for offset, reason in [
            (0, "body_start"),
            (4, "after_llse"),
            (6, "after_marker_2730"),
            (8, "after_marker4_2730"),
            (12, "after_head12"),
            (16, "after_head16"),
        ]:
            candidates[offset].append(reason)
    output = [(offset, "+".join(dict.fromkeys(reasons))) for offset, reasons in sorted(candidates.items())]
    return output[:max_offsets]


def trace_dimensions(
    source: dict[str, str],
    trace_rows: list[dict[str, str]],
    offset: int,
    mode: str,
) -> tuple[int, int]:
    segment_id = segment_key(source)
    exact = [
        row
        for row in trace_rows
        if row.get("segment_id") == segment_id
        and int_value(row, "offset") == offset
        and row.get("mode") == mode
    ]
    if not exact:
        exact = [row for row in trace_rows if row.get("segment_id") == segment_id and int_value(row, "offset") == offset]
    if exact:
        row = exact[0]
        return int_value(row, "width", 64), int_value(row, "height", 512)
    return int_value(source, "width", 64), 512


def load_body(row: dict[str, str], payload_cache: dict[Path, bytes], mix_entry_index: int) -> tuple[bytes, list[str]]:
    issues: list[str] = []
    archive = Path(row.get("archive", ""))
    offset = int_value(row, "body_offset")
    size = int_value(row, "body_size")
    try:
        if archive not in payload_cache:
            payload_cache[archive] = read_mix_entry(archive, mix_entry_index)
        payload = payload_cache[archive]
        body = payload[offset : offset + size]
        if len(body) != size:
            issues.append("short_body_read")
        return body, issues
    except Exception as exc:
        return b"", [f"read_failed:{exc}"]


def cmd20_class(event: dict[str, object]) -> str:
    action = str(event.get("action", ""))
    arg1 = event.get("arg1")
    arg2 = event.get("arg2")
    arg3 = event.get("arg3")
    if action == "sig_skip":
        if (arg1, arg2, arg3) == (0, 0, 0):
            return "sig_zero_skip"
        if isinstance(arg2, int) and arg2 in HIGH_ARG2_SIGNATURES:
            return "sig_high_arg2_skip"
        return "sig_other_skip"
    if action == "sig_noop":
        return "sig_noop"
    return action or "cmd20_other"


def trace_counts(
    payload: bytes,
    width: int,
    height: int,
    mode: str,
    low: int,
    high: int,
    max_events: int,
) -> dict[str, str]:
    kind_counts: Counter[str] = Counter()
    action_counts: Counter[str] = Counter()
    op4_bytes: Counter[str] = Counter()
    cmd20_arg2: Counter[str] = Counter()
    for event in trace_payload(payload, width, height, mode, low, high, max_events):
        kind = str(event.get("kind", ""))
        action = str(event.get("action", ""))
        kind_counts[kind] += 1
        action_counts[f"{kind}:{action}"] += 1
        if kind == "cmd20":
            action_counts[f"cmd20_class:{cmd20_class(event)}"] += 1
            arg2 = event.get("arg2")
            if isinstance(arg2, int):
                cmd20_arg2[f"{arg2:02x}"] += 1
        if kind == "op4":
            byte = event.get("byte")
            if isinstance(byte, int):
                op4_bytes[f"{byte:02x}"] += 1
    trace_events = sum(kind_counts.values())
    fingerprint = "filter_like"
    if trace_events and kind_counts.get("op4", 0) / max(1, trace_events) >= 0.02:
        fingerprint = "op4_heavy"
    elif action_counts.get("cmd20_class:sig_high_arg2_skip", 0) or action_counts.get(
        "cmd20_class:sig_zero_skip", 0
    ):
        fingerprint = "cmd20_signature"
    elif kind_counts.get("cmd20", 0):
        fingerprint = "cmd20_control"
    elif kind_counts.get("control", 0):
        fingerprint = "low_control"
    elif trace_events and kind_counts.get("pixel", 0) / max(1, trace_events) >= 0.8:
        fingerprint = "pixel_dense"
    return {
        "trace_events": str(trace_events),
        "cmd20_events": str(kind_counts.get("cmd20", 0)),
        "op4_events": str(kind_counts.get("op4", 0)),
        "control_events": str(kind_counts.get("control", 0)),
        "pixel_events": str(kind_counts.get("pixel", 0)),
        "sig_skip": str(
            action_counts.get("cmd20_class:sig_high_arg2_skip", 0)
            + action_counts.get("cmd20_class:sig_zero_skip", 0)
            + action_counts.get("cmd20_class:sig_other_skip", 0)
        ),
        "sig_noop": str(action_counts.get("cmd20_class:sig_noop", 0)),
        "sig_high_arg2_skip": str(action_counts.get("cmd20_class:sig_high_arg2_skip", 0)),
        "sig_zero_skip": str(action_counts.get("cmd20_class:sig_zero_skip", 0)),
        "op4_skip": str(
            action_counts.get("op4:skip", 0)
            + action_counts.get("op4:sig_skip", 0)
            + action_counts.get("op4:small_skip", 0)
            + action_counts.get("op4:zero_skip", 0)
        ),
        "markerknown_control": str(
            action_counts.get("control:markerknown_skip", 0)
            + action_counts.get("control:markerknownadv_skip", 0)
            + action_counts.get("control:markerknownsymadv_skip", 0)
        ),
        "trace_fingerprint": fingerprint,
        "top_op4_bytes": compact_counter(op4_bytes),
        "top_cmd20_arg2": compact_counter(cmd20_arg2),
    }


def candidate_id(source: dict[str, str], offset: int, mode: str) -> str:
    return (
        f"{safe_name(source.get('archive_tag', ''))}__{safe_name(source.get('pcx_name', ''))}"
        f"__off{offset}__{safe_name(mode)}"
    )


def evaluate_candidate(
    source: dict[str, str],
    body: bytes,
    body_issues: list[str],
    offset: int,
    offset_reason: str,
    mode: str,
    mode_source: str,
    width: int,
    height: int,
    low: int,
    high: int,
    max_trace_events: int,
    output_dir: Path,
    palette: list[tuple[int, int, int]],
) -> tuple[dict[str, str], Image.Image | None]:
    issues = list(body_issues)
    if not body:
        issues.append("empty_body")
    if offset < 0 or offset >= len(body):
        issues.append("offset_out_of_body")
    if width <= 0 or height <= 0:
        issues.append("invalid_dimensions")

    cid = candidate_id(source, offset, mode)
    payload = body[offset:] if not issues else b""
    pixels = b""
    stats: dict[str, object] = {}
    image: Image.Image | None = None
    native_dir = output_dir / "native" / safe_name(mode)
    fullhd_dir = output_dir / "fullhd" / safe_name(mode)
    native_file = native_dir / f"{cid}.png"
    fullhd_file = fullhd_dir / f"{cid}_fullhd.png"

    if not issues:
        pixels, stats = decode_span(payload, width, height, mode, low, high, return_stats=True)
        image = render_indexed(pixels, width, height, palette)
        native_dir.mkdir(parents=True, exist_ok=True)
        fullhd_dir.mkdir(parents=True, exist_ok=True)
        image.save(native_file)
        fullhd_image(image).save(fullhd_file)

    score = row_score(pixels, width, height) if pixels else 0.0
    trace = (
        trace_counts(payload, width, height, mode, low, high, max_trace_events)
        if payload and width > 0 and height > 0
        else {}
    )
    visible_pixels = sum(1 for pixel in pixels if pixel)
    if image is None:
        issues.append("missing_preview")
    elif visible_pixels <= 0:
        issues.append("blank_preview")

    row = {
        "rank": "",
        "candidate_id": cid,
        "segment_id": source.get("segment_id", ""),
        "archive": source.get("archive", ""),
        "archive_tag": source.get("archive_tag", ""),
        "pcx_name": source.get("pcx_name", ""),
        "control_path": source.get("control_path", ""),
        "offset": str(offset),
        "offset_reason": offset_reason,
        "mode": mode,
        "mode_source": mode_source,
        "width": str(width),
        "height": str(height),
        "payload_bytes": str(len(payload)),
        "score": f"{score:.4f}",
        "filled_ratio": f"{visible_ratio(pixels):.6f}" if pixels else "0.000000",
        "visible_pixels": str(visible_pixels),
        "unique_colors": str(len(set(pixels)) if pixels else 0),
        "emitted": str(stats.get("emitted", "")),
        "overdraw": f"{float_text(stats.get('overdraw')):.6f}" if stats else "",
        "final_x": str(stats.get("final_x", "")),
        "final_y": str(stats.get("final_y", "")),
        "markerknown_skips": str(stats.get("markerknown_skips", "")),
        "high_arg2_skips": str(stats.get("high_arg2_skips", "")),
        "zero_signature_seen": str(stats.get("zero_signature_seen", "")),
        "zero_signature_skipped": str(stats.get("zero_signature_skipped", "")),
        "trace_events": trace.get("trace_events", "0"),
        "cmd20_events": trace.get("cmd20_events", "0"),
        "op4_events": trace.get("op4_events", "0"),
        "control_events": trace.get("control_events", "0"),
        "pixel_events": trace.get("pixel_events", "0"),
        "sig_skip": trace.get("sig_skip", "0"),
        "sig_noop": trace.get("sig_noop", "0"),
        "sig_high_arg2_skip": trace.get("sig_high_arg2_skip", "0"),
        "sig_zero_skip": trace.get("sig_zero_skip", "0"),
        "op4_skip": trace.get("op4_skip", "0"),
        "markerknown_control": trace.get("markerknown_control", "0"),
        "trace_fingerprint": trace.get("trace_fingerprint", ""),
        "top_op4_bytes": trace.get("top_op4_bytes", ""),
        "top_cmd20_arg2": trace.get("top_cmd20_arg2", ""),
        "native_preview_path": native_file.as_posix(),
        "native_preview_exists": "yes" if native_file.exists() else "no",
        "fullhd_preview_path": fullhd_file.as_posix(),
        "fullhd_preview_exists": "yes" if fullhd_file.exists() else "no",
        "issues": ";".join(sorted(set(issues))),
    }
    return row, image


def mode_rows(candidate_rows: list[dict[str, str]], max_non_noisy_score: float) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in candidate_rows:
        if not row.get("issues"):
            grouped[row.get("mode", "")].append(row)
    output: list[dict[str, str]] = []
    for mode, rows in grouped.items():
        scores = [float_text(row.get("score")) for row in rows]
        fills = [float_text(row.get("filled_ratio")) for row in rows]
        best = min(rows, key=lambda row: float_text(row.get("score")))
        max_score = max(scores) if scores else 0.0
        verdict = "non_noisy_candidate" if max_score <= max_non_noisy_score else "noisy_candidate"
        output.append(
            {
                "rank": "",
                "mode": mode,
                "rows": str(len(rows)),
                "best_score": f"{min(scores) if scores else 0.0:.4f}",
                "avg_score": f"{sum(scores) / max(1, len(scores)):.4f}",
                "max_score": f"{max_score:.4f}",
                "best_offset": best.get("offset", ""),
                "best_offset_reason": best.get("offset_reason", ""),
                "min_filled_ratio": f"{min(fills) if fills else 0.0:.6f}",
                "total_cmd20_events": str(sum(int_value(row, "cmd20_events") for row in rows)),
                "total_op4_events": str(sum(int_value(row, "op4_events") for row in rows)),
                "total_sig_skip": str(sum(int_value(row, "sig_skip") for row in rows)),
                "total_sig_noop": str(sum(int_value(row, "sig_noop") for row in rows)),
                "total_sig_high_arg2_skip": str(sum(int_value(row, "sig_high_arg2_skip") for row in rows)),
                "total_sig_zero_skip": str(sum(int_value(row, "sig_zero_skip") for row in rows)),
                "total_op4_skip": str(sum(int_value(row, "op4_skip") for row in rows)),
                "top_op4_bytes": compact_counter(merge_counter_text(rows, "top_op4_bytes")),
                "top_cmd20_arg2": compact_counter(merge_counter_text(rows, "top_cmd20_arg2")),
                "verdict": verdict,
            }
        )
    output.sort(key=lambda row: (float_text(row.get("avg_score")), float_text(row.get("max_score")), row.get("mode", "")))
    for rank, row in enumerate(output, 1):
        row["rank"] = str(rank)
    return output


def offset_rows(candidate_rows: list[dict[str, str]], max_non_noisy_score: float) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in candidate_rows:
        if not row.get("issues"):
            grouped[(row.get("offset", ""), row.get("offset_reason", ""))].append(row)
    output: list[dict[str, str]] = []
    for (offset, reason), rows in grouped.items():
        scores = [float_text(row.get("score")) for row in rows]
        fills = [float_text(row.get("filled_ratio")) for row in rows]
        best = min(rows, key=lambda row: float_text(row.get("score")))
        max_score = max(scores) if scores else 0.0
        verdict = "non_noisy_offset" if max_score <= max_non_noisy_score else "noisy_offset"
        output.append(
            {
                "rank": "",
                "offset": offset,
                "offset_reason": reason,
                "rows": str(len(rows)),
                "best_mode": best.get("mode", ""),
                "best_score": f"{min(scores) if scores else 0.0:.4f}",
                "avg_score": f"{sum(scores) / max(1, len(scores)):.4f}",
                "min_filled_ratio": f"{min(fills) if fills else 0.0:.6f}",
                "best_trace_fingerprint": best.get("trace_fingerprint", ""),
                "verdict": verdict,
            }
        )
    output.sort(key=lambda row: (float_text(row.get("best_score")), int_value(row, "offset"), row.get("best_mode", "")))
    for rank, row in enumerate(output, 1):
        row["rank"] = str(rank)
    return output


def summary_row(
    candidate_rows: list[dict[str, str]],
    modes: list[dict[str, str]],
    offsets: list[dict[str, str]],
    segment_count: int,
    sheet_path: Path,
    max_non_noisy_score: float,
) -> dict[str, str]:
    clean_rows = [row for row in candidate_rows if not row.get("issues")]
    best = min(clean_rows, key=lambda row: float_text(row.get("score"))) if clean_rows else {}
    issue_rows = sum(1 for row in candidate_rows if row.get("issues"))
    native_previews = sum(1 for row in candidate_rows if row.get("native_preview_exists") == "yes")
    fullhd_previews = sum(1 for row in candidate_rows if row.get("fullhd_preview_exists") == "yes")
    nonblank = sum(1 for row in candidate_rows if int_value(row, "visible_pixels") > 0)
    best_score = float_text(best.get("score"))
    if issue_rows:
        verdict = "llse_signature_probe_issues"
        next_action = "fix LLSE signature probe inputs"
    elif best and best_score <= max_non_noisy_score:
        verdict = "llse_signature_candidate_ready"
        next_action = (
            "review LLSE signature candidate "
            f"offset {best.get('offset', '')} {best.get('mode', '')} previews before decoder promotion"
        )
    elif best:
        verdict = "llse_signature_existing_modes_noisy"
        next_action = (
            "derive LLSE signature renderer grammar beyond "
            f"offset {best.get('offset', '')} {best.get('mode', '')}; "
            f"best score {best_score:.4f} remains noisy"
        )
    else:
        verdict = "llse_signature_no_candidates"
        next_action = "derive LLSE signature large .tex body control path"
    return {
        "scope": "total",
        "segment_rows": str(segment_count),
        "offset_rows": str(len(offsets)),
        "mode_rows": str(len(modes)),
        "candidate_rows": str(len(candidate_rows)),
        "native_previews": str(native_previews),
        "fullhd_previews": str(fullhd_previews),
        "nonblank_previews": str(nonblank),
        "sheet_path": sheet_path.as_posix(),
        "best_offset": best.get("offset", ""),
        "best_offset_reason": best.get("offset_reason", ""),
        "best_mode": best.get("mode", ""),
        "best_score": f"{best_score:.4f}",
        "best_filled_ratio": best.get("filled_ratio", ""),
        "best_final_y": best.get("final_y", ""),
        "best_trace_fingerprint": best.get("trace_fingerprint", ""),
        "max_non_noisy_score": f"{max_non_noisy_score:.4f}",
        "issue_rows": str(issue_rows),
        "probe_verdict": verdict,
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
    for row in rows[:limit]:
        native = html.escape(relative_href(row.get("native_preview_path", ""), output_dir))
        fullhd = html.escape(relative_href(row.get("fullhd_preview_path", ""), output_dir))
        cards.append(
            "<figure>"
            f"<a href=\"{fullhd}\"><img src=\"{native}\" loading=\"lazy\" decoding=\"async\" alt=\"\"></a>"
            f"<figcaption>{html.escape(row.get('archive_tag', ''))} / {html.escape(row.get('pcx_name', ''))}<br>"
            f"off {html.escape(row.get('offset', ''))} {html.escape(row.get('mode', ''))}<br>"
            f"score {html.escape(row.get('score', ''))} fill {html.escape(row.get('filled_ratio', ''))}<br>"
            f"<a href=\"{native}\">native</a><a href=\"{fullhd}\">fullhd</a></figcaption>"
            "</figure>"
        )
    return "\n".join(cards)


def build_html(
    summary: dict[str, str],
    modes: list[dict[str, str]],
    offsets: list[dict[str, str]],
    candidates: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "modes": modes, "offsets": offsets, "candidates": candidates}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f"<a href=\"{html.escape(relative_href(path, output_dir))}\">{html.escape(label)}</a>"
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("offsets.csv", output_dir / "offsets.csv"),
            ("modes.csv", output_dir / "modes.csv"),
            ("candidates.csv", output_dir / "candidates.csv"),
            ("sheet.png", output_dir / "sheet.png"),
        )
    )
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
:root {{ color-scheme: dark; --bg: #101317; --panel: #181d23; --text: #e8edf2; --muted: #98a4b3; --accent: #74b8ff; --ok: #6fd08c; --warn: #f0b35a; }}
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
figure img {{ width: 100%; height: 240px; object-fit: contain; image-rendering: pixelated; background: #050607; }}
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
  <div class="muted">Renderer candidate sweep for LLSE-signature large .tex bodies.</div>
  <p>{links}</p>
</header>
<main>
  <section class="grid">
    <div class="stat"><div class="label">Candidates</div><div class="value">{html.escape(summary['candidate_rows'])}</div></div>
    <div class="stat"><div class="label">Full HD</div><div class="value ok">{html.escape(summary['fullhd_previews'])}</div></div>
    <div class="stat"><div class="label">Best Score</div><div class="value warn">{html.escape(summary['best_score'])}</div></div>
    <div class="stat"><div class="label">Issues</div><div class="value ok">{html.escape(summary['issue_rows'])}</div></div>
  </section>
  <section class="grid">{render_cards(candidates, output_dir)}</section>
  <section class="panel">
    <h2>Summary</h2>
    {render_table([summary], SUMMARY_FIELDNAMES)}
  </section>
  <section class="panel">
    <h2>Offsets</h2>
    {render_table(offsets, OFFSET_FIELDNAMES)}
  </section>
  <section class="panel">
    <h2>Modes</h2>
    {render_table(modes, MODE_FIELDNAMES)}
  </section>
  <section class="panel">
    <h2>Candidates</h2>
    {render_table(candidates, CANDIDATE_FIELDNAMES)}
  </section>
</main>
<script type="application/json" id="llse-probe-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> tuple[dict[str, str], list[dict[str, str]]]:
    args.output.mkdir(parents=True, exist_ok=True)
    segment_rows = [row for row in read_csv(args.segments) if row.get("control_path") == TARGET_CONTROL_PATH]
    body_control_rows = [row for row in read_csv(args.body_control_segments) if row.get("control_path") == TARGET_CONTROL_PATH]
    trace_rows = [row for row in read_csv(args.trace_candidates) if row.get("control_path") == TARGET_CONTROL_PATH]
    modes, mode_sources = load_modes(args.mode_choices)
    palette = read_palette(args.palette)
    payload_cache: dict[Path, bytes] = {}
    candidate_rows: list[dict[str, str]] = []
    images_by_id: dict[str, Image.Image] = {}

    for source in segment_rows:
        body, body_issues = load_body(source, payload_cache, args.mix_entry_index)
        for offset, reason in offsets_for_segment(source, body_control_rows, trace_rows, args.max_offsets):
            for mode in modes:
                width, height = trace_dimensions(source, trace_rows, offset, mode)
                row, image = evaluate_candidate(
                    source,
                    body,
                    body_issues,
                    offset,
                    reason,
                    mode,
                    mode_sources.get(mode, "choice_report"),
                    width,
                    height,
                    args.low,
                    args.high,
                    args.max_trace_events,
                    args.output,
                    palette,
                )
                candidate_rows.append(row)
                if image is not None:
                    images_by_id[row["candidate_id"]] = image

    candidate_rows.sort(key=lambda row: (bool(row.get("issues")), float_text(row.get("score")), row.get("candidate_id", "")))
    for rank, row in enumerate(candidate_rows, 1):
        row["rank"] = str(rank)
    modes_out = mode_rows(candidate_rows, args.max_non_noisy_score)
    offsets_out = offset_rows(candidate_rows, args.max_non_noisy_score)
    sheet_path = args.output / "sheet.png"
    sheet_entries = [
        (f"{row['archive_tag']} {row['pcx_name']} off{row['offset']} {row['mode']}", images_by_id[row["candidate_id"]])
        for row in candidate_rows[: args.sheet_limit]
        if row["candidate_id"] in images_by_id
    ]
    make_sheet(sheet_entries, sheet_path, 4, 180)
    summary = summary_row(
        candidate_rows,
        modes_out,
        offsets_out,
        len(segment_rows),
        sheet_path,
        args.max_non_noisy_score,
    )
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "offsets.csv", OFFSET_FIELDNAMES, offsets_out)
    write_csv(args.output / "modes.csv", MODE_FIELDNAMES, modes_out)
    write_csv(args.output / "candidates.csv", CANDIDATE_FIELDNAMES, candidate_rows)
    (args.output / "index.html").write_text(
        build_html(summary, modes_out, offsets_out, candidate_rows, args.output, args.title),
        encoding="utf-8",
    )
    return summary, candidate_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe LLSE-signature large .tex renderer candidates.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--segments", type=Path, default=DEFAULT_SEGMENTS)
    parser.add_argument("--body-control-segments", type=Path, default=DEFAULT_BODY_CONTROL_SEGMENTS)
    parser.add_argument("--trace-candidates", type=Path, default=DEFAULT_TRACE_CANDIDATES)
    parser.add_argument("--mode-choices", type=Path, default=DEFAULT_MODE_CHOICES)
    parser.add_argument("-p", "--palette", type=Path, default=DEFAULT_PALETTE)
    parser.add_argument("--mix-entry-index", type=int, default=DEFAULT_MIX_ENTRY_INDEX)
    parser.add_argument("--low", type=lambda value: int(value, 0), default=0x30)
    parser.add_argument("--high", type=lambda value: int(value, 0), default=0xBF)
    parser.add_argument("--max-trace-events", type=int, default=20000)
    parser.add_argument("--max-offsets", type=int, default=8)
    parser.add_argument("--max-non-noisy-score", type=float, default=40.0)
    parser.add_argument("--sheet-limit", type=int, default=24)
    parser.add_argument("--title", default="Lands of Lore II .tex LLSE Signature Control Probe")
    args = parser.parse_args()

    summary, _rows = write_report(args)
    print(f"Segments: {summary['segment_rows']}")
    print(f"Candidate rows: {summary['candidate_rows']}")
    print(f"Best offset: {summary['best_offset']}")
    print(f"Best mode: {summary['best_mode']}")
    print(f"Best score: {summary['best_score']}")
    print(f"Full HD previews: {summary['fullhd_previews']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"Probe verdict: {summary['probe_verdict']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
