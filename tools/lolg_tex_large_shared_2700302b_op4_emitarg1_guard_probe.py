#!/usr/bin/env python3
"""Probe simple guards for shared 0x2700302b op4 emit-arg1 semantics."""

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
from score_te_raw_layouts import row_score


DEFAULT_OUTPUT = Path("output/tex_large_shared_2700302b_op4_emitarg1_guard_probe")
DEFAULT_OP4_SEMANTICS_SUMMARY = Path("output/tex_large_shared_2700302b_op4_argument_semantics_probe/summary.csv")
DEFAULT_SEGMENTS = Path("output/tex_large_rejected_decoder_profile/segments.csv")
DEFAULT_TRACE_CANDIDATES = Path("output/tex_large_body_control_grammar_probe/trace_candidates.csv")
DEFAULT_PALETTE = Path("extracted/LOCAL/7231c8f9.pal")
DEFAULT_MIX_ENTRY_INDEX = 2
TARGET_CONTROL_PATH = "shared_2700302b_header"
OP4_VALUES = tuple(range(0x40, 0x69, 4))

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
    "best_delta_vs_baseline",
    "best_delta_vs_all_ops",
    "best_min_filled_ratio",
    "preview_rows",
    "sheet_path",
    "issue_rows",
    "guard_verdict",
    "next_action",
]

GUARD_FIELDNAMES = [
    "rank",
    "guard_id",
    "kind",
    "op4_values",
    "arg1_min_hex",
    "arg1_max_hex",
    "rows",
    "avg_score",
    "max_score",
    "min_score",
    "avg_delta_vs_baseline",
    "avg_delta_vs_all_ops",
    "max_delta_vs_baseline",
    "min_filled_ratio",
    "total_op4_events",
    "total_op4_emit_events",
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
    "op4_values",
    "arg1_min_hex",
    "arg1_max_hex",
    "width",
    "height",
    "payload_bytes",
    "score",
    "score_delta_vs_baseline",
    "score_delta_vs_all_ops",
    "filled_ratio",
    "visible_pixels",
    "unique_colors",
    "emitted",
    "overdraw",
    "final_x",
    "final_y",
    "op4_events",
    "op4_emit_events",
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


def read_summary(path: Path) -> dict[str, str]:
    rows = read_csv(path)
    return rows[0] if rows else {}


def float_text(value: object, default: float = 0.0) -> float:
    try:
        return float(str(value)) if value not in (None, "") else default
    except ValueError:
        return default


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    try:
        return os.path.relpath(Path(path_text), base_dir)
    except ValueError:
        return str(path_text)


def compact_op_values(values: set[int]) -> str:
    return "|".join(f"{value:02x}" for value in sorted(values))


def guard_specs() -> list[dict[str, object]]:
    specs: list[dict[str, object]] = [
        {"guard_id": "emit_none", "kind": "none", "op4_values": set(), "arg1_min": 0x30, "arg1_max": 0xBF},
        {
            "guard_id": "emit_all_ops_arg1_30_bf",
            "kind": "all_ops",
            "op4_values": set(OP4_VALUES),
            "arg1_min": 0x30,
            "arg1_max": 0xBF,
        },
    ]
    for value in OP4_VALUES:
        specs.append(
            {
                "guard_id": f"emit_op{value:02x}",
                "kind": "single_opcode",
                "op4_values": {value},
                "arg1_min": 0x30,
                "arg1_max": 0xBF,
            }
        )
    for start_index, start in enumerate(OP4_VALUES):
        for end in OP4_VALUES[start_index + 1 :]:
            values = {value for value in OP4_VALUES if start <= value <= end}
            specs.append(
                {
                    "guard_id": f"emit_op{start:02x}_{end:02x}",
                    "kind": "opcode_range",
                    "op4_values": values,
                    "arg1_min": 0x30,
                    "arg1_max": 0xBF,
                }
            )
    for arg1_min, arg1_max in (
        (0x30, 0x5F),
        (0x60, 0x8F),
        (0x90, 0xBF),
        (0x30, 0x7F),
        (0x80, 0xBF),
        (0x40, 0x68),
        (0x69, 0xBF),
    ):
        specs.append(
            {
                "guard_id": f"emit_all_ops_arg1_{arg1_min:02x}_{arg1_max:02x}",
                "kind": "arg1_range",
                "op4_values": set(OP4_VALUES),
                "arg1_min": arg1_min,
                "arg1_max": arg1_max,
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


def decode_guard(
    payload: bytes,
    width: int,
    height: int,
    low: int,
    high: int,
    op4_values: set[int],
    arg1_min: int,
    arg1_max: int,
) -> tuple[bytes, dict[str, int | float]]:
    pixels = bytearray(width * height)
    x = y = pos = 0
    emitted = 0
    op4_events = 0
    op4_emit_events = 0
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
            if byte in op4_values and pos < len(payload) and arg1_min <= payload[pos] <= arg1_max:
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
        "op4_events": op4_events,
        "op4_emit_events": op4_emit_events,
        "cmd20_sig_skips": cmd20_sig_skips,
        "cmd20_sig_noops": cmd20_sig_noops,
        "markerknown_skips": markerknown_skips,
    }


def baseline_pixels(payload: bytes, width: int, height: int, low: int, high: int) -> bytes:
    pixels, _stats = decode_custom(payload, width, height, low, high, 3, False, False, False)
    return pixels


def variant_id(row: dict[str, str], guard_id: str, offset: int) -> str:
    return f"{safe_name(row.get('archive_tag', ''))}__{safe_name(row.get('pcx_name', ''))}__off{offset}__{safe_name(guard_id)}"


def evaluate_guard(
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
    baseline_score: float,
    all_ops_score: float,
) -> tuple[dict[str, str], Image.Image | None]:
    issues = list(body_issues)
    if not body:
        issues.append("empty_body")
    if offset < 0 or offset >= len(body):
        issues.append("offset_out_of_body")
    payload = body[offset:] if not issues else b""
    guard_id = str(spec["guard_id"])
    op4_values = set(spec["op4_values"])  # type: ignore[arg-type]
    arg1_min = int(spec["arg1_min"])
    arg1_max = int(spec["arg1_max"])
    pixels = b""
    stats: dict[str, int | float] = {}
    image: Image.Image | None = None
    preview_path = output_dir / "previews" / safe_name(guard_id)
    preview_file = preview_path / f"{safe_name(source.get('archive_tag', ''))}_{safe_name(source.get('pcx_name', ''))}.png"
    if not issues:
        pixels, stats = decode_guard(payload, width, height, low, high, op4_values, arg1_min, arg1_max)
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
            "variant_id": variant_id(source, guard_id, offset),
            "segment_id": source.get("segment_id", ""),
            "archive": source.get("archive", ""),
            "archive_tag": source.get("archive_tag", ""),
            "pcx_name": source.get("pcx_name", ""),
            "offset": str(offset),
            "guard_id": guard_id,
            "kind": str(spec["kind"]),
            "op4_values": compact_op_values(op4_values),
            "arg1_min_hex": f"{arg1_min:02x}",
            "arg1_max_hex": f"{arg1_max:02x}",
            "width": str(width),
            "height": str(height),
            "payload_bytes": str(len(payload)),
            "score": f"{score:.4f}",
            "score_delta_vs_baseline": f"{score - baseline_score:.4f}",
            "score_delta_vs_all_ops": f"{score - all_ops_score:.4f}",
            "filled_ratio": f"{visible_ratio(pixels):.6f}" if pixels else "0.000000",
            "visible_pixels": str(sum(1 for pixel in pixels if pixel)),
            "unique_colors": str(len(set(pixels)) if pixels else 0),
            "emitted": str(stats.get("emitted", "")),
            "overdraw": f"{float_text(stats.get('overdraw')):.6f}" if stats else "",
            "final_x": str(stats.get("final_x", "")),
            "final_y": str(stats.get("final_y", "")),
            "op4_events": str(stats.get("op4_events", "")),
            "op4_emit_events": str(stats.get("op4_emit_events", "")),
            "cmd20_sig_skips": str(stats.get("cmd20_sig_skips", "")),
            "cmd20_sig_noops": str(stats.get("cmd20_sig_noops", "")),
            "markerknown_skips": str(stats.get("markerknown_skips", "")),
            "preview_path": preview_file.as_posix(),
            "preview_exists": "yes" if preview_file.exists() else "no",
            "issues": ";".join(sorted(set(issues))),
        },
        image,
    )


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
        deltas = [float_text(row.get("score_delta_vs_baseline")) for row in group]
        fills = [float_text(row.get("filled_ratio")) for row in group]
        avg_score = sum(scores) / max(1, len(scores))
        verdict = "all_ops_reference" if guard_id == all_ops_guard_id else "candidate"
        if guard_id != all_ops_guard_id and avg_score < all_ops_avg:
            verdict = "improves_all_ops"
        elif guard_id != all_ops_guard_id:
            verdict = "no_improvement"
        output.append(
            {
                "rank": "",
                "guard_id": guard_id,
                "kind": group[0].get("kind", ""),
                "op4_values": group[0].get("op4_values", ""),
                "arg1_min_hex": group[0].get("arg1_min_hex", ""),
                "arg1_max_hex": group[0].get("arg1_max_hex", ""),
                "rows": str(len(group)),
                "avg_score": f"{avg_score:.4f}",
                "max_score": f"{max(scores) if scores else 0.0:.4f}",
                "min_score": f"{min(scores) if scores else 0.0:.4f}",
                "avg_delta_vs_baseline": f"{sum(deltas) / max(1, len(deltas)):.4f}",
                "avg_delta_vs_all_ops": f"{avg_score - all_ops_avg:.4f}",
                "max_delta_vs_baseline": f"{max(deltas) if deltas else 0.0:.4f}",
                "min_filled_ratio": f"{min(fills) if fills else 0.0:.6f}",
                "total_op4_events": str(sum(int_value(row, "op4_events") for row in group)),
                "total_op4_emit_events": str(sum(int_value(row, "op4_emit_events") for row in group)),
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
    if issue_rows:
        verdict = "shared_2700302b_op4_emitarg1_guard_probe_issues"
        next_action = "fix shared 0x2700302b op4 emit-arg1 guard probe inputs"
    elif float_text(best.get("max_score")) <= max_non_noisy_score:
        verdict = "shared_2700302b_op4_emitarg1_guard_ready"
        next_action = (
            "review shared 0x2700302b op4 emit-arg1 guard "
            f"{best.get('guard_id', '')} previews before decoder promotion"
        )
    elif best.get("guard_id") == all_ops_guard_id:
        verdict = "shared_2700302b_op4_emitarg1_all_ops_best_simple_guard"
        next_action = (
            "derive row or stream-position guard for shared 0x2700302b emitarg1_skipargs0; "
            "opcode and arg1-range guards do not improve all-op emit"
        )
    else:
        verdict = "shared_2700302b_op4_emitarg1_simple_guard_improves"
        next_action = (
            "inspect shared 0x2700302b op4 emit-arg1 guard "
            f"{best.get('guard_id', '')}; avg score {float_text(best.get('avg_score')):.4f} remains noisy"
        )
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
        "best_delta_vs_baseline": best.get("avg_delta_vs_baseline", ""),
        "best_delta_vs_all_ops": best.get("avg_delta_vs_all_ops", ""),
        "best_min_filled_ratio": best.get("min_filled_ratio", ""),
        "preview_rows": str(preview_rows),
        "sheet_path": sheet_path.as_posix(),
        "issue_rows": str(issue_rows),
        "guard_verdict": verdict,
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
            f"{html.escape(row.get('guard_id', ''))}<br>"
            f"score {html.escape(row.get('score', ''))} delta {html.escape(row.get('score_delta_vs_baseline', ''))}</figcaption>"
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
  <div class="muted">Opcode and arg1-range guards for the shared 0x2700302b emit-arg1 op4 candidate.</div>
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
<script type="application/json" id="op4-emitarg1-guard-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> tuple[dict[str, str], list[dict[str, str]]]:
    args.output.mkdir(parents=True, exist_ok=True)
    op4_summary = read_summary(args.op4_semantics_summary)
    offset = int_value(op4_summary, "offset", 4)
    baseline_semantic = "skipargs3"
    all_ops_guard_id = "emit_all_ops_arg1_30_bf"
    palette = read_palette(args.palette)
    trace_rows = read_csv(args.trace_candidates)
    segment_rows = [row for row in read_csv(args.segments) if row.get("control_path") == TARGET_CONTROL_PATH]
    payload_cache: dict[Path, bytes] = {}
    variants: list[dict[str, str]] = []
    sheet_entries: list[tuple[str, Image.Image]] = []
    for source in segment_rows:
        body, issues = load_body(source, payload_cache, args.mix_entry_index)
        width, height = trace_dimensions(trace_rows, source.get("segment_id", ""), offset)
        payload = body[offset:] if body and 0 <= offset < len(body) else b""
        base_pixels = baseline_pixels(payload, width, height, args.low, args.high)
        baseline_score = float_text(row_score(base_pixels, width, height))
        all_pixels, _all_stats = decode_guard(
            payload,
            width,
            height,
            args.low,
            args.high,
            set(OP4_VALUES),
            0x30,
            0xBF,
        )
        all_ops_score = float_text(row_score(all_pixels, width, height))
        for spec in guard_specs():
            row, image = evaluate_guard(
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
                baseline_score,
                all_ops_score,
            )
            variants.append(row)
            if image is not None:
                sheet_entries.append((f"{row['archive_tag']} {row['pcx_name']} {row['guard_id']}", image))
    guards = guard_rows(variants, all_ops_guard_id)
    top_ids = {
        row.get("variant_id", "")
        for row in sorted(variants, key=lambda item: float_text(item.get("score")))[: args.sheet_limit]
    }
    sheet_path = args.output / "sheet.png"
    make_sheet(
        [
            (label, image)
            for label, image in sheet_entries
            if any(
                label == f"{row['archive_tag']} {row['pcx_name']} {row['guard_id']}"
                and row["variant_id"] in top_ids
                for row in variants
            )
        ],
        sheet_path,
        4,
        180,
    )
    summary = build_summary(
        variants,
        guards,
        len(segment_rows),
        offset,
        baseline_semantic,
        op4_summary.get("baseline_avg_score", ""),
        op4_summary.get("baseline_max_score", ""),
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
    parser = argparse.ArgumentParser(description="Probe shared 0x2700302b op4 emit-arg1 simple guards.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--op4-semantics-summary", type=Path, default=DEFAULT_OP4_SEMANTICS_SUMMARY)
    parser.add_argument("--segments", type=Path, default=DEFAULT_SEGMENTS)
    parser.add_argument("--trace-candidates", type=Path, default=DEFAULT_TRACE_CANDIDATES)
    parser.add_argument("-p", "--palette", type=Path, default=DEFAULT_PALETTE)
    parser.add_argument("--mix-entry-index", type=int, default=DEFAULT_MIX_ENTRY_INDEX)
    parser.add_argument("--low", type=lambda value: int(value, 0), default=0x30)
    parser.add_argument("--high", type=lambda value: int(value, 0), default=0xBF)
    parser.add_argument("--max-non-noisy-score", type=float, default=40.0)
    parser.add_argument("--sheet-limit", type=int, default=24)
    parser.add_argument("--title", default="Lands of Lore II .tex Shared 0x2700302b OP4 Emit-Arg1 Guard Probe")
    args = parser.parse_args()

    summary, _guards = write_report(args)
    print(f"Segments: {summary['segment_rows']}")
    print(f"Guard rows: {summary['guard_rows']}")
    print(f"Best guard: {summary['best_guard_id']}")
    print(f"Best avg score: {summary['best_avg_score']}")
    print(f"All ops avg score: {summary['all_ops_guard_avg_score']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"Guard verdict: {summary['guard_verdict']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
