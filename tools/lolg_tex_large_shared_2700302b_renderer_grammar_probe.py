#!/usr/bin/env python3
"""Probe existing renderer grammar modes for shared 0x2700302b large .tex bodies."""

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


DEFAULT_OUTPUT = Path("output/tex_large_shared_2700302b_renderer_grammar_probe")
DEFAULT_HEADER_SUMMARY = Path("output/tex_large_shared_2700302b_header_probe/summary.csv")
DEFAULT_PAYLOAD_REPLAY_SUMMARY = Path("output/tex_large_shared_2700302b_payload_replay/summary.csv")
DEFAULT_SEGMENTS = Path("output/tex_large_rejected_decoder_profile/segments.csv")
DEFAULT_TRACE_CANDIDATES = Path("output/tex_large_body_control_grammar_probe/trace_candidates.csv")
DEFAULT_MODE_CHOICES = Path("reports/te_guarded_cmd20_v10_riskaware_markerknownsymadv_plus_puddle.tsv")
DEFAULT_PALETTE = Path("extracted/LOCAL/7231c8f9.pal")
DEFAULT_MIX_ENTRY_INDEX = 2
TARGET_CONTROL_PATH = "shared_2700302b_header"
HIGH_ARG2_SIGNATURES = {0xE0, 0xFC, 0xFD, 0xFE, 0xFF}

FALLBACK_MODES = [
    "filter",
    "cmd20_skip4",
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
    "variant_rows",
    "mode_rows",
    "offset",
    "baseline_mode",
    "baseline_avg_score",
    "baseline_max_score",
    "best_mode",
    "best_avg_score",
    "best_max_score",
    "best_delta_vs_baseline",
    "best_min_filled_ratio",
    "existing_choice_modes",
    "preview_rows",
    "sheet_path",
    "issue_rows",
    "grammar_verdict",
    "next_action",
]

VARIANT_FIELDNAMES = [
    "variant_id",
    "segment_id",
    "archive",
    "archive_tag",
    "pcx_name",
    "offset",
    "mode",
    "mode_source",
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
    "markerknown_skips",
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
    "top_op4_bytes",
    "top_cmd20_arg2",
    "preview_path",
    "preview_exists",
    "issues",
]

MODE_FIELDNAMES = [
    "rank",
    "mode",
    "rows",
    "avg_score",
    "max_score",
    "min_score",
    "avg_delta_vs_baseline",
    "max_delta_vs_baseline",
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


def read_csv(path: Path, *, delimiter: str = ",") -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter=delimiter))


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


def compact_counter(counter: Counter[str], *, limit: int = 8) -> str:
    return "|".join(f"{key}:{count}" for key, count in counter.most_common(limit))


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    try:
        return os.path.relpath(Path(path_text), base_dir)
    except ValueError:
        return str(path_text)


def load_modes(mode_choices: Path, baseline_mode: str) -> tuple[list[str], dict[str, str]]:
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
    if baseline_mode:
        if baseline_mode in sources:
            if "baseline" not in sources[baseline_mode]:
                sources[baseline_mode] = f"{sources[baseline_mode]}+baseline"
        else:
            sources[baseline_mode] = "baseline"
    return sorted(sources), sources


def trace_dimensions(
    trace_rows: list[dict[str, str]],
    segment_id: str,
    offset: int,
    mode: str,
) -> tuple[int, int]:
    exact = [
        row
        for row in trace_rows
        if row.get("segment_id") == segment_id
        and int_value(row, "offset") == offset
        and row.get("mode") == mode
    ]
    if not exact:
        exact = [
            row
            for row in trace_rows
            if row.get("segment_id") == segment_id and int_value(row, "offset") == offset
        ]
    if not exact:
        return 64, 512
    row = exact[0]
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


def visible_ratio(pixels: bytes) -> float:
    return sum(1 for pixel in pixels if pixel) / max(1, len(pixels))


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
    return {
        "trace_events": str(sum(kind_counts.values())),
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
        "top_op4_bytes": compact_counter(op4_bytes),
        "top_cmd20_arg2": compact_counter(cmd20_arg2),
    }


def variant_id(row: dict[str, str], mode: str, offset: int) -> str:
    return f"{safe_name(row.get('archive_tag', ''))}__{safe_name(row.get('pcx_name', ''))}__off{offset}__{safe_name(mode)}"


def evaluate_variant(
    source: dict[str, str],
    body: bytes,
    body_issues: list[str],
    width: int,
    height: int,
    offset: int,
    mode: str,
    mode_source: str,
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
    payload = body[offset:] if not issues else b""
    pixels = b""
    stats: dict[str, object] = {}
    image: Image.Image | None = None
    preview_path = output_dir / "previews" / safe_name(mode)
    preview_file = preview_path / f"{safe_name(source.get('archive_tag', ''))}_{safe_name(source.get('pcx_name', ''))}.png"
    if not issues:
        pixels, stats = decode_span(payload, width, height, mode, low, high, return_stats=True)
        image = render_indexed(pixels, width, height, palette)
        preview_path.mkdir(parents=True, exist_ok=True)
        image.save(preview_file)
    score = row_score(pixels, width, height) if pixels else 0.0
    trace = (
        trace_counts(payload, width, height, mode, low, high, max_trace_events)
        if payload and width > 0 and height > 0
        else {}
    )
    if image is None:
        issues.append("missing_preview")
    elif sum(1 for pixel in pixels if pixel) <= 0:
        issues.append("blank_preview")
    row = {
        "variant_id": variant_id(source, mode, offset),
        "segment_id": source.get("segment_id", ""),
        "archive": source.get("archive", ""),
        "archive_tag": source.get("archive_tag", ""),
        "pcx_name": source.get("pcx_name", ""),
        "offset": str(offset),
        "mode": mode,
        "mode_source": mode_source,
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
        "markerknown_skips": str(stats.get("markerknown_skips", "")),
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
        "top_op4_bytes": trace.get("top_op4_bytes", ""),
        "top_cmd20_arg2": trace.get("top_cmd20_arg2", ""),
        "preview_path": preview_file.as_posix(),
        "preview_exists": "yes" if preview_file.exists() else "no",
        "issues": ";".join(sorted(set(issues))),
    }
    return row, image


def add_baseline_deltas(rows: list[dict[str, str]], baseline_mode: str) -> None:
    baseline_by_segment = {
        row.get("segment_id", ""): float_text(row.get("score"))
        for row in rows
        if row.get("mode") == baseline_mode and not row.get("issues")
    }
    for row in rows:
        baseline = baseline_by_segment.get(row.get("segment_id", ""))
        if baseline is None or row.get("issues"):
            row["score_delta_vs_baseline"] = ""
        else:
            row["score_delta_vs_baseline"] = f"{float_text(row.get('score')) - baseline:.4f}"


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


def mode_rows(variant_rows: list[dict[str, str]], baseline_mode: str) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in variant_rows:
        if not row.get("issues"):
            grouped[row.get("mode", "")].append(row)
    output: list[dict[str, str]] = []
    for mode, rows in grouped.items():
        scores = [float_text(row.get("score")) for row in rows]
        deltas = [float_text(row.get("score_delta_vs_baseline")) for row in rows]
        fills = [float_text(row.get("filled_ratio")) for row in rows]
        avg_delta = sum(deltas) / max(1, len(deltas))
        verdict = "baseline" if mode == baseline_mode else "candidate"
        if mode != baseline_mode and avg_delta >= 0:
            verdict = "no_improvement"
        elif mode != baseline_mode:
            verdict = "improves_baseline"
        output.append(
            {
                "rank": "",
                "mode": mode,
                "rows": str(len(rows)),
                "avg_score": f"{sum(scores) / max(1, len(scores)):.4f}",
                "max_score": f"{max(scores) if scores else 0.0:.4f}",
                "min_score": f"{min(scores) if scores else 0.0:.4f}",
                "avg_delta_vs_baseline": f"{avg_delta:.4f}",
                "max_delta_vs_baseline": f"{max(deltas) if deltas else 0.0:.4f}",
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


def summary_row(
    variant_rows: list[dict[str, str]],
    modes: list[dict[str, str]],
    segment_count: int,
    offset: int,
    baseline_mode: str,
    existing_choice_modes: int,
    sheet_path: Path,
    max_non_noisy_score: float,
) -> dict[str, str]:
    baseline = next((row for row in modes if row.get("mode") == baseline_mode), {})
    best = modes[0] if modes else {}
    issue_rows = sum(1 for row in variant_rows if row.get("issues"))
    preview_rows = sum(1 for row in variant_rows if row.get("preview_exists") == "yes")
    best_delta = float_text(best.get("avg_delta_vs_baseline")) if best else 0.0
    best_max = float_text(best.get("max_score")) if best else 0.0
    improved_rows = [row for row in modes if row.get("mode") != baseline_mode and float_text(row.get("avg_delta_vs_baseline")) < 0]
    if issue_rows:
        verdict = "shared_2700302b_renderer_grammar_probe_issues"
        next_action = "fix shared 0x2700302b renderer grammar probe inputs"
    elif best_max <= max_non_noisy_score:
        verdict = "shared_2700302b_existing_renderer_mode_ready"
        next_action = (
            "review shared 0x2700302b existing renderer mode "
            f"{best.get('mode', '')} previews before decoder promotion"
        )
    elif improved_rows:
        verdict = "shared_2700302b_existing_renderer_mode_improves_but_noisy"
        next_action = (
            "inspect shared 0x2700302b improved renderer candidate "
            f"{best.get('mode', '')}; max score {best_max:.4f} remains noisy"
        )
    else:
        verdict = "shared_2700302b_existing_renderer_modes_do_not_improve"
        next_action = (
            "derive new shared 0x2700302b op4 argument semantics; "
            f"best existing mode remains {best.get('mode', '')} "
            f"avg score {float_text(best.get('avg_score')):.4f}"
        )
    return {
        "scope": "total",
        "segment_rows": str(segment_count),
        "variant_rows": str(len(variant_rows)),
        "mode_rows": str(len(modes)),
        "offset": str(offset),
        "baseline_mode": baseline_mode,
        "baseline_avg_score": baseline.get("avg_score", ""),
        "baseline_max_score": baseline.get("max_score", ""),
        "best_mode": best.get("mode", ""),
        "best_avg_score": best.get("avg_score", ""),
        "best_max_score": best.get("max_score", ""),
        "best_delta_vs_baseline": f"{best_delta:.4f}",
        "best_min_filled_ratio": best.get("min_filled_ratio", ""),
        "existing_choice_modes": str(existing_choice_modes),
        "preview_rows": str(preview_rows),
        "sheet_path": sheet_path.as_posix(),
        "issue_rows": str(issue_rows),
        "grammar_verdict": verdict,
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
            f"{html.escape(row.get('mode', ''))}<br>"
            f"score {html.escape(row.get('score', ''))} delta {html.escape(row.get('score_delta_vs_baseline', ''))}</figcaption>"
            "</figure>"
        )
    return "\n".join(cards)


def build_html(
    summary: dict[str, str],
    modes: list[dict[str, str]],
    variants: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "modes": modes, "variants": variants}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f"<a href=\"{html.escape(relative_href(path, output_dir))}\">{html.escape(label)}</a>"
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("modes.csv", output_dir / "modes.csv"),
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
  <div class="muted">Existing renderer grammar sweep for shared 0x2700302b large .tex payloads.</div>
  <p>{links}</p>
</header>
<main>
  <section class="grid">
    <div class="stat"><div class="label">Modes</div><div class="value">{html.escape(summary['mode_rows'])}</div></div>
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
    <h2>Modes</h2>
    {render_table(modes, MODE_FIELDNAMES)}
  </section>
  <section class="panel">
    <h2>Variants</h2>
    {render_table(variants, VARIANT_FIELDNAMES)}
  </section>
</main>
<script type="application/json" id="renderer-grammar-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> tuple[dict[str, str], list[dict[str, str]]]:
    args.output.mkdir(parents=True, exist_ok=True)
    header_summary = read_summary(args.header_summary)
    replay_summary = read_summary(args.payload_replay_summary)
    offset = int_value(replay_summary, "offset", int_value(header_summary, "best_offset"))
    baseline_mode = replay_summary.get("mode") or header_summary.get("best_mode", "")
    modes, mode_sources = load_modes(args.mode_choices, baseline_mode)
    palette = read_palette(args.palette)
    trace_rows = read_csv(args.trace_candidates)
    segment_rows = [row for row in read_csv(args.segments) if row.get("control_path") == TARGET_CONTROL_PATH]
    payload_cache: dict[Path, bytes] = {}
    variant_rows: list[dict[str, str]] = []
    sheet_entries: list[tuple[str, Image.Image]] = []
    for source in segment_rows:
        body, body_issues = load_body(source, payload_cache, args.mix_entry_index)
        width, height = trace_dimensions(trace_rows, source.get("segment_id", ""), offset, baseline_mode)
        for mode in modes:
            row, image = evaluate_variant(
                source,
                body,
                body_issues,
                width,
                height,
                offset,
                mode,
                mode_sources.get(mode, "choice_report"),
                args.low,
                args.high,
                args.max_trace_events,
                args.output,
                palette,
            )
            variant_rows.append(row)
            if image is not None:
                sheet_entries.append((f"{row['archive_tag']} {row['pcx_name']} {mode}", image))
    add_baseline_deltas(variant_rows, baseline_mode)
    modes_out = mode_rows(variant_rows, baseline_mode)
    top_variant_ids = {
        row.get("variant_id", "")
        for row in sorted(variant_rows, key=lambda item: float_text(item.get("score")))[: args.sheet_limit]
    }
    sheet_path = args.output / "sheet.png"
    make_sheet(
        [(label, image) for label, image in sheet_entries if variant_id_from_label(label, variant_rows) in top_variant_ids],
        sheet_path,
        4,
        180,
    )
    summary = summary_row(
        variant_rows,
        modes_out,
        len(segment_rows),
        offset,
        baseline_mode,
        sum(1 for source in mode_sources.values() if "choice_report" in source),
        sheet_path,
        args.max_non_noisy_score,
    )
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "modes.csv", MODE_FIELDNAMES, modes_out)
    write_csv(args.output / "variants.csv", VARIANT_FIELDNAMES, variant_rows)
    (args.output / "index.html").write_text(
        build_html(summary, modes_out, variant_rows, args.output, args.title),
        encoding="utf-8",
    )
    return summary, modes_out


def variant_id_from_label(label: str, rows: list[dict[str, str]]) -> str:
    for row in rows:
        if label == f"{row['archive_tag']} {row['pcx_name']} {row['mode']}":
            return row.get("variant_id", "")
    return ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe shared 0x2700302b renderer grammar candidates.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--header-summary", type=Path, default=DEFAULT_HEADER_SUMMARY)
    parser.add_argument("--payload-replay-summary", type=Path, default=DEFAULT_PAYLOAD_REPLAY_SUMMARY)
    parser.add_argument("--segments", type=Path, default=DEFAULT_SEGMENTS)
    parser.add_argument("--trace-candidates", type=Path, default=DEFAULT_TRACE_CANDIDATES)
    parser.add_argument("--mode-choices", type=Path, default=DEFAULT_MODE_CHOICES)
    parser.add_argument("-p", "--palette", type=Path, default=DEFAULT_PALETTE)
    parser.add_argument("--mix-entry-index", type=int, default=DEFAULT_MIX_ENTRY_INDEX)
    parser.add_argument("--low", type=lambda value: int(value, 0), default=0x30)
    parser.add_argument("--high", type=lambda value: int(value, 0), default=0xBF)
    parser.add_argument("--max-trace-events", type=int, default=20000)
    parser.add_argument("--max-non-noisy-score", type=float, default=40.0)
    parser.add_argument("--sheet-limit", type=int, default=24)
    parser.add_argument("--title", default="Lands of Lore II .tex Shared 0x2700302b Renderer Grammar Probe")
    args = parser.parse_args()

    summary, _modes = write_report(args)
    print(f"Segments: {summary['segment_rows']}")
    print(f"Variant rows: {summary['variant_rows']}")
    print(f"Best mode: {summary['best_mode']}")
    print(f"Best avg score: {summary['best_avg_score']}")
    print(f"Baseline avg score: {summary['baseline_avg_score']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"Grammar verdict: {summary['grammar_verdict']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
