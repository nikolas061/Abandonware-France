#!/usr/bin/env python3
"""Probe custom op4 argument semantics for shared 0x2700302b large .tex bodies."""

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
from lolg_tex_large_body_control_grammar_probe import int_value, read_mix_entry, write_csv
from score_te_raw_layouts import row_score


DEFAULT_OUTPUT = Path("output/tex_large_shared_2700302b_op4_argument_semantics_probe")
DEFAULT_PAYLOAD_REPLAY_SUMMARY = Path("output/tex_large_shared_2700302b_payload_replay/summary.csv")
DEFAULT_RENDERER_GRAMMAR_SUMMARY = Path("output/tex_large_shared_2700302b_renderer_grammar_probe/summary.csv")
DEFAULT_SEGMENTS = Path("output/tex_large_rejected_decoder_profile/segments.csv")
DEFAULT_TRACE_CANDIDATES = Path("output/tex_large_body_control_grammar_probe/trace_candidates.csv")
DEFAULT_PALETTE = Path("extracted/LOCAL/7231c8f9.pal")
DEFAULT_MIX_ENTRY_INDEX = 2
TARGET_CONTROL_PATH = "shared_2700302b_header"
HIGH_ARG2_SIGNATURES = {0xE0, 0xFC, 0xFD, 0xFE, 0xFF}
KNOWN_MARKER_PAIRS = {
    (0x27, 0x30),
    (0x28, 0x30),
    (0x29, 0x30),
    (0x2A, 0x30),
    (0x2B, 0x30),
    (0x2B, 0x31),
}

SUMMARY_FIELDNAMES = [
    "scope",
    "segment_rows",
    "variant_rows",
    "semantic_rows",
    "offset",
    "baseline_mode",
    "baseline_avg_score",
    "baseline_max_score",
    "best_semantic",
    "best_avg_score",
    "best_max_score",
    "best_delta_vs_baseline",
    "best_min_filled_ratio",
    "improved_semantic_rows",
    "preview_rows",
    "sheet_path",
    "issue_rows",
    "semantic_verdict",
    "next_action",
]

VARIANT_FIELDNAMES = [
    "variant_id",
    "segment_id",
    "archive",
    "archive_tag",
    "pcx_name",
    "offset",
    "semantic",
    "op4_skip_args",
    "op4_emit_arg1",
    "op4_advance_code",
    "op4_advance_arg",
    "width",
    "height",
    "payload_bytes",
    "score",
    "score_delta_vs_baseline",
    "filled_ratio",
    "visible_pixels",
    "unique_colors",
    "emitted",
    "overdraw",
    "final_x",
    "final_y",
    "op4_events",
    "op4_emit_arg1_events",
    "op4_advance_code_events",
    "op4_advance_arg_events",
    "cmd20_sig_skips",
    "cmd20_sig_noops",
    "markerknown_skips",
    "preview_path",
    "preview_exists",
    "issues",
]

SEMANTIC_FIELDNAMES = [
    "rank",
    "semantic",
    "rows",
    "avg_score",
    "max_score",
    "min_score",
    "avg_delta_vs_baseline",
    "max_delta_vs_baseline",
    "min_filled_ratio",
    "total_op4_events",
    "total_op4_emit_arg1_events",
    "total_op4_advance_code_events",
    "total_op4_advance_arg_events",
    "total_cmd20_sig_skips",
    "total_markerknown_skips",
    "verdict",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_summary(path: Path) -> dict[str, str]:
    rows = read_csv(path)
    return rows[0] if rows else {}


def float_text(value: object, default: float = 0.0) -> float:
    try:
        return float(str(value)) if value not in (None, "") else default
    except ValueError:
        return default


def safe_name(value: str) -> str:
    clean = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in value)
    return clean.strip("._") or "unnamed"


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    try:
        return os.path.relpath(Path(path_text), base_dir)
    except ValueError:
        return str(path_text)


def advance(x: int, y: int, width: int, amount: int) -> tuple[int, int]:
    x += amount
    while x >= width:
        x -= width
        y += 1
    return x, y


def put_pixel(pixels: bytearray, width: int, height: int, x: int, y: int, value: int) -> None:
    if 0 <= x < width and 0 <= y < height:
        pixels[y * width + x] = value


def is_op4_candidate(value: int) -> bool:
    return 0x40 <= value <= 0x68 and value % 4 == 0


def is_cmd20_signature(arg1: int | None, arg2: int | None, arg3: int | None) -> bool:
    return (arg1, arg2, arg3) == (0, 0, 0) or (
        arg1 is not None and arg2 in HIGH_ARG2_SIGNATURES and arg3 is not None
    )


def visible_ratio(pixels: bytes) -> float:
    return sum(1 for pixel in pixels if pixel) / max(1, len(pixels))


def trace_dimensions(
    trace_rows: list[dict[str, str]],
    segment_id: str,
    offset: int,
) -> tuple[int, int]:
    matches = [
        row
        for row in trace_rows
        if row.get("segment_id") == segment_id and int_value(row, "offset") == offset
    ]
    if not matches:
        return 64, 512
    row = matches[0]
    return int_value(row, "width", 64), int_value(row, "height", 512)


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


def semantic_specs() -> list[dict[str, object]]:
    specs: list[dict[str, object]] = []
    for skip_args in range(0, 9):
        specs.append(
            {
                "semantic": f"skipargs{skip_args}",
                "op4_skip_args": skip_args,
                "op4_emit_arg1": False,
                "op4_advance_code": False,
                "op4_advance_arg": False,
            }
        )
    for skip_args in range(0, 6):
        for name, emit_arg1, advance_code, advance_arg in (
            ("emitarg1", True, False, False),
            ("advancecode", False, True, False),
            ("advancearg", False, False, True),
        ):
            specs.append(
                {
                    "semantic": f"{name}_skipargs{skip_args}",
                    "op4_skip_args": skip_args,
                    "op4_emit_arg1": emit_arg1,
                    "op4_advance_code": advance_code,
                    "op4_advance_arg": advance_arg,
                }
            )
    return specs


def decode_custom(
    payload: bytes,
    width: int,
    height: int,
    low: int,
    high: int,
    op4_skip_args: int,
    op4_emit_arg1: bool,
    op4_advance_code: bool,
    op4_advance_arg: bool,
) -> tuple[bytes, dict[str, int | float]]:
    pixels = bytearray(width * height)
    x = y = pos = 0
    emitted = 0
    op4_events = 0
    op4_emit_arg1_events = 0
    op4_advance_code_events = 0
    op4_advance_arg_events = 0
    cmd20_sig_skips = 0
    cmd20_sig_noops = 0
    markerknown_skips = 0
    while pos < len(payload) and y < height:
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
            if op4_emit_arg1 and pos < len(payload) and low <= payload[pos] <= high:
                put_pixel(pixels, width, height, x, y, payload[pos])
                x, y = advance(x, y, width, 1)
                emitted += 1
                op4_emit_arg1_events += 1
            elif op4_advance_code:
                x, y = advance(x, y, width, (byte - 0x40) // 4)
                op4_advance_code_events += 1
            elif op4_advance_arg and pos < len(payload):
                x, y = advance(x, y, width, payload[pos])
                op4_advance_arg_events += 1
            pos = min(len(payload), pos + op4_skip_args)
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
        "op4_events": op4_events,
        "op4_emit_arg1_events": op4_emit_arg1_events,
        "op4_advance_code_events": op4_advance_code_events,
        "op4_advance_arg_events": op4_advance_arg_events,
        "cmd20_sig_skips": cmd20_sig_skips,
        "cmd20_sig_noops": cmd20_sig_noops,
        "markerknown_skips": markerknown_skips,
    }


def variant_id(row: dict[str, str], semantic: str, offset: int) -> str:
    return f"{safe_name(row.get('archive_tag', ''))}__{safe_name(row.get('pcx_name', ''))}__off{offset}__{safe_name(semantic)}"


def evaluate_variant(
    source: dict[str, str],
    body: bytes,
    body_issues: list[str],
    width: int,
    height: int,
    offset: int,
    spec: dict[str, object],
    low: int,
    high: int,
    output_dir: Path,
    palette: list[tuple[int, int, int]],
) -> tuple[dict[str, str], Image.Image | None]:
    issues = list(body_issues)
    if not body:
        issues.append("empty_body")
    if offset < 0 or offset >= len(body):
        issues.append("offset_out_of_body")
    payload = body[offset:] if not issues else b""
    semantic = str(spec["semantic"])
    pixels = b""
    stats: dict[str, int | float] = {}
    image: Image.Image | None = None
    preview_path = output_dir / "previews" / safe_name(semantic)
    preview_file = preview_path / f"{safe_name(source.get('archive_tag', ''))}_{safe_name(source.get('pcx_name', ''))}.png"
    if not issues:
        pixels, stats = decode_custom(
            payload,
            width,
            height,
            low,
            high,
            int(spec["op4_skip_args"]),
            bool(spec["op4_emit_arg1"]),
            bool(spec["op4_advance_code"]),
            bool(spec["op4_advance_arg"]),
        )
        image = render_indexed(pixels, width, height, palette)
        preview_path.mkdir(parents=True, exist_ok=True)
        image.save(preview_file)
    if image is None:
        issues.append("missing_preview")
    elif sum(1 for pixel in pixels if pixel) <= 0:
        issues.append("blank_preview")
    score = row_score(pixels, width, height) if pixels else 0.0
    return (
        {
            "variant_id": variant_id(source, semantic, offset),
            "segment_id": source.get("segment_id", ""),
            "archive": source.get("archive", ""),
            "archive_tag": source.get("archive_tag", ""),
            "pcx_name": source.get("pcx_name", ""),
            "offset": str(offset),
            "semantic": semantic,
            "op4_skip_args": str(spec["op4_skip_args"]),
            "op4_emit_arg1": "yes" if spec["op4_emit_arg1"] else "no",
            "op4_advance_code": "yes" if spec["op4_advance_code"] else "no",
            "op4_advance_arg": "yes" if spec["op4_advance_arg"] else "no",
            "width": str(width),
            "height": str(height),
            "payload_bytes": str(len(payload)),
            "score": f"{score:.4f}",
            "score_delta_vs_baseline": "",
            "filled_ratio": f"{visible_ratio(pixels):.6f}" if pixels else "0.000000",
            "visible_pixels": str(sum(1 for pixel in pixels if pixel)),
            "unique_colors": str(len(set(pixels)) if pixels else 0),
            "emitted": str(stats.get("emitted", "")),
            "overdraw": f"{float_text(stats.get('overdraw')):.6f}" if stats else "",
            "final_x": str(stats.get("final_x", "")),
            "final_y": str(stats.get("final_y", "")),
            "op4_events": str(stats.get("op4_events", "")),
            "op4_emit_arg1_events": str(stats.get("op4_emit_arg1_events", "")),
            "op4_advance_code_events": str(stats.get("op4_advance_code_events", "")),
            "op4_advance_arg_events": str(stats.get("op4_advance_arg_events", "")),
            "cmd20_sig_skips": str(stats.get("cmd20_sig_skips", "")),
            "cmd20_sig_noops": str(stats.get("cmd20_sig_noops", "")),
            "markerknown_skips": str(stats.get("markerknown_skips", "")),
            "preview_path": preview_file.as_posix(),
            "preview_exists": "yes" if preview_file.exists() else "no",
            "issues": ";".join(sorted(set(issues))),
        },
        image,
    )


def add_baseline_deltas(rows: list[dict[str, str]], baseline_semantic: str) -> None:
    baseline_by_segment = {
        row.get("segment_id", ""): float_text(row.get("score"))
        for row in rows
        if row.get("semantic") == baseline_semantic and not row.get("issues")
    }
    for row in rows:
        baseline = baseline_by_segment.get(row.get("segment_id", ""))
        if baseline is None or row.get("issues"):
            row["score_delta_vs_baseline"] = ""
        else:
            row["score_delta_vs_baseline"] = f"{float_text(row.get('score')) - baseline:.4f}"


def semantic_rows(rows: list[dict[str, str]], baseline_semantic: str) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        if row.get("issues"):
            continue
        grouped.setdefault(row.get("semantic", ""), []).append(row)
    output: list[dict[str, str]] = []
    for semantic, group in grouped.items():
        scores = [float_text(row.get("score")) for row in group]
        deltas = [float_text(row.get("score_delta_vs_baseline")) for row in group]
        fills = [float_text(row.get("filled_ratio")) for row in group]
        avg_delta = sum(deltas) / max(1, len(deltas))
        verdict = "baseline" if semantic == baseline_semantic else "candidate"
        if semantic != baseline_semantic and avg_delta < 0:
            verdict = "improves_baseline"
        elif semantic != baseline_semantic:
            verdict = "no_improvement"
        output.append(
            {
                "rank": "",
                "semantic": semantic,
                "rows": str(len(group)),
                "avg_score": f"{sum(scores) / max(1, len(scores)):.4f}",
                "max_score": f"{max(scores) if scores else 0.0:.4f}",
                "min_score": f"{min(scores) if scores else 0.0:.4f}",
                "avg_delta_vs_baseline": f"{avg_delta:.4f}",
                "max_delta_vs_baseline": f"{max(deltas) if deltas else 0.0:.4f}",
                "min_filled_ratio": f"{min(fills) if fills else 0.0:.6f}",
                "total_op4_events": str(sum(int_value(row, "op4_events") for row in group)),
                "total_op4_emit_arg1_events": str(sum(int_value(row, "op4_emit_arg1_events") for row in group)),
                "total_op4_advance_code_events": str(sum(int_value(row, "op4_advance_code_events") for row in group)),
                "total_op4_advance_arg_events": str(sum(int_value(row, "op4_advance_arg_events") for row in group)),
                "total_cmd20_sig_skips": str(sum(int_value(row, "cmd20_sig_skips") for row in group)),
                "total_markerknown_skips": str(sum(int_value(row, "markerknown_skips") for row in group)),
                "verdict": verdict,
            }
        )
    output.sort(key=lambda row: (float_text(row.get("avg_score")), float_text(row.get("max_score")), row.get("semantic", "")))
    for rank, row in enumerate(output, 1):
        row["rank"] = str(rank)
    return output


def build_summary(
    variant_rows: list[dict[str, str]],
    semantic_rows_out: list[dict[str, str]],
    segment_count: int,
    offset: int,
    baseline_mode: str,
    baseline_semantic: str,
    sheet_path: Path,
    max_non_noisy_score: float,
) -> dict[str, str]:
    baseline = next((row for row in semantic_rows_out if row.get("semantic") == baseline_semantic), {})
    best = semantic_rows_out[0] if semantic_rows_out else {}
    issue_rows = sum(1 for row in variant_rows if row.get("issues"))
    preview_rows = sum(1 for row in variant_rows if row.get("preview_exists") == "yes")
    improved = [
        row
        for row in semantic_rows_out
        if row.get("semantic") != baseline_semantic and float_text(row.get("avg_delta_vs_baseline")) < 0
    ]
    best_max = float_text(best.get("max_score"))
    if issue_rows:
        verdict = "shared_2700302b_op4_argument_semantics_probe_issues"
        next_action = "fix shared 0x2700302b op4 argument semantics probe inputs"
    elif best_max <= max_non_noisy_score:
        verdict = "shared_2700302b_op4_argument_semantics_candidate_ready"
        next_action = (
            "review shared 0x2700302b op4 argument semantic "
            f"{best.get('semantic', '')} previews before decoder promotion"
        )
    elif improved:
        verdict = "shared_2700302b_op4_argument_semantics_improves_but_noisy"
        next_action = (
            "inspect shared 0x2700302b op4 semantic "
            f"{best.get('semantic', '')}; avg score {float_text(best.get('avg_score')):.4f} "
            f"improves baseline by {float_text(best.get('avg_delta_vs_baseline')):.4f} but remains noisy"
        )
    else:
        verdict = "shared_2700302b_op4_argument_semantics_no_improvement"
        next_action = "broaden shared 0x2700302b op4 argument semantics beyond skip/emit/advance variants"
    return {
        "scope": "total",
        "segment_rows": str(segment_count),
        "variant_rows": str(len(variant_rows)),
        "semantic_rows": str(len(semantic_rows_out)),
        "offset": str(offset),
        "baseline_mode": baseline_mode,
        "baseline_avg_score": baseline.get("avg_score", ""),
        "baseline_max_score": baseline.get("max_score", ""),
        "best_semantic": best.get("semantic", ""),
        "best_avg_score": best.get("avg_score", ""),
        "best_max_score": best.get("max_score", ""),
        "best_delta_vs_baseline": best.get("avg_delta_vs_baseline", ""),
        "best_min_filled_ratio": best.get("min_filled_ratio", ""),
        "improved_semantic_rows": str(len(improved)),
        "preview_rows": str(preview_rows),
        "sheet_path": sheet_path.as_posix(),
        "issue_rows": str(issue_rows),
        "semantic_verdict": verdict,
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
    for row in sorted(rows, key=lambda item: float_text(item.get("score")))[:limit]:
        preview = html.escape(relative_href(row.get("preview_path", ""), output_dir))
        cards.append(
            "<figure>"
            f"<img src=\"{preview}\" loading=\"lazy\" decoding=\"async\" alt=\"\">"
            f"<figcaption>{html.escape(row.get('archive_tag', ''))} / {html.escape(row.get('pcx_name', ''))}<br>"
            f"{html.escape(row.get('semantic', ''))}<br>"
            f"score {html.escape(row.get('score', ''))} delta {html.escape(row.get('score_delta_vs_baseline', ''))}</figcaption>"
            "</figure>"
        )
    return "\n".join(cards)


def build_html(
    summary: dict[str, str],
    semantics: list[dict[str, str]],
    variants: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "semantics": semantics, "variants": variants}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f"<a href=\"{html.escape(relative_href(path, output_dir))}\">{html.escape(label)}</a>"
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("semantics.csv", output_dir / "semantics.csv"),
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
  <div class="muted">Custom op4 skip, emit, and advance semantics for shared 0x2700302b large .tex payloads.</div>
  <p>{links}</p>
</header>
<main>
  <section class="grid">
    <div class="stat"><div class="label">Semantics</div><div class="value">{html.escape(summary['semantic_rows'])}</div></div>
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
    <h2>Semantics</h2>
    {render_table(semantics, SEMANTIC_FIELDNAMES)}
  </section>
  <section class="panel">
    <h2>Variants</h2>
    {render_table(variants, VARIANT_FIELDNAMES)}
  </section>
</main>
<script type="application/json" id="op4-semantics-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> tuple[dict[str, str], list[dict[str, str]]]:
    args.output.mkdir(parents=True, exist_ok=True)
    replay_summary = read_summary(args.payload_replay_summary)
    renderer_summary = read_summary(args.renderer_grammar_summary)
    offset = int_value(replay_summary, "offset", int_value(renderer_summary, "offset", 4))
    baseline_mode = replay_summary.get("mode") or renderer_summary.get("baseline_mode", "")
    baseline_semantic = "skipargs3"
    palette = read_palette(args.palette)
    trace_rows = read_csv(args.trace_candidates)
    segment_rows = [row for row in read_csv(args.segments) if row.get("control_path") == TARGET_CONTROL_PATH]
    payload_cache: dict[Path, bytes] = {}
    rows: list[dict[str, str]] = []
    sheet_entries: list[tuple[str, Image.Image]] = []
    for source in segment_rows:
        body, issues = load_body(source, payload_cache, args.mix_entry_index)
        width, height = trace_dimensions(trace_rows, source.get("segment_id", ""), offset)
        for spec in semantic_specs():
            row, image = evaluate_variant(
                source,
                body,
                issues,
                width,
                height,
                offset,
                spec,
                args.low,
                args.high,
                args.output,
                palette,
            )
            rows.append(row)
            if image is not None:
                sheet_entries.append((f"{row['archive_tag']} {row['pcx_name']} {row['semantic']}", image))
    add_baseline_deltas(rows, baseline_semantic)
    semantics = semantic_rows(rows, baseline_semantic)
    top_ids = {
        row.get("variant_id", "")
        for row in sorted(rows, key=lambda item: float_text(item.get("score")))[: args.sheet_limit]
    }
    sheet_path = args.output / "sheet.png"
    make_sheet(
        [
            (label, image)
            for label, image in sheet_entries
            if any(label == f"{row['archive_tag']} {row['pcx_name']} {row['semantic']}" and row["variant_id"] in top_ids for row in rows)
        ],
        sheet_path,
        4,
        180,
    )
    summary = build_summary(
        rows,
        semantics,
        len(segment_rows),
        offset,
        baseline_mode,
        baseline_semantic,
        sheet_path,
        args.max_non_noisy_score,
    )
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "semantics.csv", SEMANTIC_FIELDNAMES, semantics)
    write_csv(args.output / "variants.csv", VARIANT_FIELDNAMES, rows)
    (args.output / "index.html").write_text(
        build_html(summary, semantics, rows, args.output, args.title),
        encoding="utf-8",
    )
    return summary, semantics


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe shared 0x2700302b op4 argument semantics.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--payload-replay-summary", type=Path, default=DEFAULT_PAYLOAD_REPLAY_SUMMARY)
    parser.add_argument("--renderer-grammar-summary", type=Path, default=DEFAULT_RENDERER_GRAMMAR_SUMMARY)
    parser.add_argument("--segments", type=Path, default=DEFAULT_SEGMENTS)
    parser.add_argument("--trace-candidates", type=Path, default=DEFAULT_TRACE_CANDIDATES)
    parser.add_argument("-p", "--palette", type=Path, default=DEFAULT_PALETTE)
    parser.add_argument("--mix-entry-index", type=int, default=DEFAULT_MIX_ENTRY_INDEX)
    parser.add_argument("--low", type=lambda value: int(value, 0), default=0x30)
    parser.add_argument("--high", type=lambda value: int(value, 0), default=0xBF)
    parser.add_argument("--max-non-noisy-score", type=float, default=40.0)
    parser.add_argument("--sheet-limit", type=int, default=24)
    parser.add_argument("--title", default="Lands of Lore II .tex Shared 0x2700302b OP4 Argument Semantics Probe")
    args = parser.parse_args()

    summary, _semantics = write_report(args)
    print(f"Segments: {summary['segment_rows']}")
    print(f"Variant rows: {summary['variant_rows']}")
    print(f"Best semantic: {summary['best_semantic']}")
    print(f"Best avg score: {summary['best_avg_score']}")
    print(f"Baseline avg score: {summary['baseline_avg_score']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"Semantic verdict: {summary['semantic_verdict']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
