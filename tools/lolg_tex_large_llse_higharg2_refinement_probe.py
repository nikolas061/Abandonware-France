#!/usr/bin/env python3
"""Refine LLSE high-arg2 cmd20 semantics after the broad semantic probe."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from export_shp import read_palette
from export_te_span_previews import make_sheet, render_indexed
from lolg_tex_large_body_control_grammar_probe import int_value, read_mix_entry, write_csv
from score_te_raw_layouts import row_score


DEFAULT_OUTPUT = Path("output/tex_large_llse_higharg2_refinement_probe")
DEFAULT_SEGMENTS = Path("output/tex_large_rejected_decoder_profile/segments.csv")
DEFAULT_SEMANTIC_SUMMARY = Path("output/tex_large_llse_cmd20_semantic_probe/summary.csv")
DEFAULT_PALETTE = Path("extracted/LOCAL/7231c8f9.pal")
DEFAULT_MIX_ENTRY_INDEX = 2
TARGET_CONTROL_PATH = "llse_signature"
TARGET_SIZE = (1920, 1080)
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
    "preview_rows",
    "native_previews",
    "fullhd_previews",
    "nonblank_previews",
    "semantic_baseline_mode",
    "semantic_baseline_score",
    "best_variant",
    "best_score",
    "best_delta_vs_semantic",
    "best_zero_policy",
    "best_dy_policy",
    "best_threshold",
    "best_x_policy",
    "best_skip",
    "best_filled_ratio",
    "best_final_y",
    "issue_rows",
    "refinement_verdict",
    "next_action",
]

VARIANT_FIELDNAMES = [
    "rank",
    "variant_id",
    "segment_id",
    "archive",
    "archive_tag",
    "pcx_name",
    "zero_policy",
    "dy_policy",
    "threshold",
    "x_policy",
    "skip",
    "offset",
    "width",
    "height",
    "payload_bytes",
    "score",
    "delta_vs_semantic",
    "filled_ratio",
    "visible_pixels",
    "unique_colors",
    "emitted",
    "final_x",
    "final_y",
    "cmd20_seen",
    "cmd20_skipped",
    "cmd20_zero_seen",
    "cmd20_zero_drop",
    "cmd20_zero_line",
    "cmd20_zero_advance1",
    "cmd20_higharg2_seen",
    "cmd20_higharg2_applied",
    "marker_skips",
    "marker_advances",
    "native_preview_path",
    "native_preview_exists",
    "fullhd_preview_path",
    "fullhd_preview_exists",
    "issues",
]


@dataclass(frozen=True)
class Variant:
    zero_policy: str
    dy_policy: str
    threshold: int
    x_policy: str
    skip: int

    @property
    def variant_id(self) -> str:
        return (
            f"z{self.zero_policy}_dy{self.dy_policy}_thr{self.threshold:02x}_"
            f"x{self.x_policy}_skip{self.skip}"
        )


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_summary(path: Path) -> dict[str, str]:
    rows = read_csv(path)
    return rows[0] if rows else {}


def safe_name(value: str) -> str:
    clean = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in value)
    return clean.strip("._") or "unnamed"


def float_text(value: object, default: float = 0.0) -> float:
    try:
        return float(str(value)) if value not in (None, "") else default
    except ValueError:
        return default


def signed_byte(value: int) -> int:
    return value - 256 if value >= 128 else value


def is_known_marker_pair(first: int, second: int) -> bool:
    return (first, second) in KNOWN_MARKER_PAIRS


def marker_symmetric_header(payload: bytes, first: int, pos: int) -> bool:
    return (
        pos + 2 < len(payload)
        and is_known_marker_pair(first, payload[pos])
        and payload[pos + 1] == 0
        and payload[pos + 2] == 0x52 - first
    )


def advance(x: int, y: int, width: int, amount: int) -> tuple[int, int]:
    x += amount
    while x >= width:
        x -= width
        y += 1
    return x, y


def put_pixel(pixels: bytearray, width: int, height: int, x: int, y: int, value: int) -> None:
    if 0 <= x < width and 0 <= y < height:
        pixels[y * width + x] = value


def visible_ratio(pixels: bytes) -> float:
    return sum(1 for pixel in pixels if pixel) / max(1, len(pixels))


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


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    try:
        return os.path.relpath(Path(path_text), base_dir)
    except ValueError:
        return str(path_text)


def marker_payload_start(body: bytes) -> int:
    if body.startswith(b"LLSE"):
        marker = body.find(b"\x27\x30", 4, 256)
        if marker >= 0:
            return marker
        return 4
    marker = body.find(b"\x27\x30", 0, 256)
    return marker if marker >= 0 else 0


def build_variants() -> list[Variant]:
    variants: list[Variant] = []
    for zero_policy in ("skip", "drop", "line"):
        for dy_policy in ("add", "sub"):
            for threshold in (0xC0, 0xE0, 0xF0, 0xF8, 0xFC):
                for x_policy in ("arg1_mod", "arg1_clamp", "keep"):
                    for skip in (3, 4):
                        variants.append(Variant(zero_policy, dy_policy, threshold, x_policy, skip))
    return variants


def apply_x_policy(x: int, width: int, arg1: int, policy: str) -> int:
    if policy == "arg1_mod":
        return arg1 % max(1, width)
    if policy == "arg1_clamp":
        return min(width - 1, arg1)
    return x


def decode_refined(payload: bytes, width: int, height: int, variant: Variant, low: int, high: int) -> tuple[bytes, dict[str, int]]:
    pixels = bytearray(width * height)
    x = y = 0
    pos = 0
    emitted = 0
    stats = {
        "cmd20_seen": 0,
        "cmd20_skipped": 0,
        "cmd20_zero_seen": 0,
        "cmd20_zero_drop": 0,
        "cmd20_zero_line": 0,
        "cmd20_zero_advance1": 0,
        "cmd20_higharg2_seen": 0,
        "cmd20_higharg2_applied": 0,
        "marker_skips": 0,
        "marker_advances": 0,
    }
    while pos < len(payload) and y < height:
        byte = payload[pos]
        pos += 1
        if marker_symmetric_header(payload, byte, pos):
            pos += 1
            x, y = advance(x, y, width, 1)
            stats["marker_advances"] += 1
            continue
        if pos < len(payload) and is_known_marker_pair(byte, payload[pos]):
            pos += 1
            stats["marker_skips"] += 1
            continue
        if byte == 0x20:
            stats["cmd20_seen"] += 1
            arg1 = payload[pos] if pos < len(payload) else 0
            arg2 = payload[pos + 1] if pos + 1 < len(payload) else 0
            arg3 = payload[pos + 2] if pos + 2 < len(payload) else 0
            if (arg1, arg2, arg3) == (0, 0, 0):
                stats["cmd20_zero_seen"] += 1
                if variant.zero_policy == "drop":
                    stats["cmd20_zero_drop"] += 1
                    continue
                if variant.zero_policy == "line":
                    x = 0
                    y = min(height, y + 1)
                    pos = min(len(payload), pos + variant.skip)
                    stats["cmd20_skipped"] += 1
                    stats["cmd20_zero_line"] += 1
                    continue
                pos = min(len(payload), pos + variant.skip)
                stats["cmd20_skipped"] += 1
                continue
            if arg2 >= variant.threshold:
                stats["cmd20_higharg2_seen"] += 1
                dy = signed_byte(arg2)
                next_y = y + dy if variant.dy_policy == "add" else y - dy
                if 0 <= next_y < height:
                    x = apply_x_policy(x, width, arg1, variant.x_policy)
                    y = next_y
                    pos = min(len(payload), pos + variant.skip)
                    stats["cmd20_skipped"] += 1
                    stats["cmd20_higharg2_applied"] += 1
                    continue
            pos = min(len(payload), pos + variant.skip)
            stats["cmd20_skipped"] += 1
            continue
        if low <= byte <= high:
            put_pixel(pixels, width, height, x, y, byte)
            x, y = advance(x, y, width, 1)
            emitted += 1
    stats["emitted"] = emitted
    stats["final_x"] = x
    stats["final_y"] = y
    return bytes(pixels), stats


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


def evaluate_variant(
    source: dict[str, str],
    body: bytes,
    body_issues: list[str],
    variant: Variant,
    width: int,
    height: int,
    low: int,
    high: int,
    semantic_baseline: float,
) -> tuple[dict[str, str], bytes]:
    issues = list(body_issues)
    if not body:
        issues.append("empty_body")
    offset = marker_payload_start(body)
    payload = body[offset:] if not issues else b""
    pixels = b""
    stats: dict[str, int] = {}
    if not issues:
        pixels, stats = decode_refined(payload, width, height, variant, low, high)
    visible = sum(1 for pixel in pixels if pixel)
    if not pixels:
        issues.append("missing_pixels")
    elif visible <= 0:
        issues.append("blank_preview")
    score = row_score(pixels, width, height) if pixels else 0.0
    return (
        {
            "rank": "",
            "variant_id": variant.variant_id,
            "segment_id": source.get("segment_id", ""),
            "archive": source.get("archive", ""),
            "archive_tag": source.get("archive_tag", ""),
            "pcx_name": source.get("pcx_name", ""),
            "zero_policy": variant.zero_policy,
            "dy_policy": variant.dy_policy,
            "threshold": f"0x{variant.threshold:02x}",
            "x_policy": variant.x_policy,
            "skip": str(variant.skip),
            "offset": str(offset),
            "width": str(width),
            "height": str(height),
            "payload_bytes": str(len(payload)),
            "score": f"{score:.4f}",
            "delta_vs_semantic": f"{score - semantic_baseline:.4f}",
            "filled_ratio": f"{visible_ratio(pixels):.6f}" if pixels else "0.000000",
            "visible_pixels": str(visible),
            "unique_colors": str(len(set(pixels)) if pixels else 0),
            "emitted": str(stats.get("emitted", "")),
            "final_x": str(stats.get("final_x", "")),
            "final_y": str(stats.get("final_y", "")),
            "cmd20_seen": str(stats.get("cmd20_seen", "")),
            "cmd20_skipped": str(stats.get("cmd20_skipped", "")),
            "cmd20_zero_seen": str(stats.get("cmd20_zero_seen", "")),
            "cmd20_zero_drop": str(stats.get("cmd20_zero_drop", "")),
            "cmd20_zero_line": str(stats.get("cmd20_zero_line", "")),
            "cmd20_zero_advance1": str(stats.get("cmd20_zero_advance1", "")),
            "cmd20_higharg2_seen": str(stats.get("cmd20_higharg2_seen", "")),
            "cmd20_higharg2_applied": str(stats.get("cmd20_higharg2_applied", "")),
            "marker_skips": str(stats.get("marker_skips", "")),
            "marker_advances": str(stats.get("marker_advances", "")),
            "native_preview_path": "",
            "native_preview_exists": "no",
            "fullhd_preview_path": "",
            "fullhd_preview_exists": "no",
            "issues": ";".join(sorted(set(issues))),
        },
        pixels,
    )


def write_previews(
    rows: list[dict[str, str]],
    pixels_by_id: dict[str, bytes],
    palette: list[tuple[int, int, int]],
    output_dir: Path,
    limit: int,
) -> list[tuple[str, Image.Image]]:
    sheet_entries: list[tuple[str, Image.Image]] = []
    for row in rows[:limit]:
        pixels = pixels_by_id.get(row["variant_id"])
        if not pixels:
            continue
        width = int_value(row, "width")
        height = int_value(row, "height")
        image = render_indexed(pixels, width, height, palette)
        native_dir = output_dir / "native"
        fullhd_dir = output_dir / "fullhd"
        native_dir.mkdir(parents=True, exist_ok=True)
        fullhd_dir.mkdir(parents=True, exist_ok=True)
        native_file = native_dir / f"{safe_name(row['variant_id'])}.png"
        fullhd_file = fullhd_dir / f"{safe_name(row['variant_id'])}_fullhd.png"
        image.save(native_file)
        fullhd_image(image).save(fullhd_file)
        row["native_preview_path"] = native_file.as_posix()
        row["native_preview_exists"] = "yes"
        row["fullhd_preview_path"] = fullhd_file.as_posix()
        row["fullhd_preview_exists"] = "yes"
        sheet_entries.append((f"{row['rank']} {row['score']} {row['variant_id']}", image))
    return sheet_entries


def summary_row(rows: list[dict[str, str]], semantic_summary: dict[str, str], preview_limit: int) -> dict[str, str]:
    clean_rows = [row for row in rows if not row.get("issues")]
    best = clean_rows[0] if clean_rows else {}
    issue_rows = sum(1 for row in rows if row.get("issues"))
    native_previews = sum(1 for row in rows if row.get("native_preview_exists") == "yes")
    fullhd_previews = sum(1 for row in rows if row.get("fullhd_preview_exists") == "yes")
    nonblank = sum(1 for row in rows if int_value(row, "visible_pixels") > 0)
    best_delta = float_text(best.get("delta_vs_semantic"))
    if issue_rows:
        verdict = "llse_higharg2_refinement_probe_issues"
        next_action = "fix LLSE high-arg2 refinement probe inputs"
    elif best and best_delta < 0:
        verdict = "llse_higharg2_refinement_improves"
        next_action = (
            "inspect LLSE high-arg2 refined candidate "
            f"{best.get('variant_id', '')}; score delta {best_delta:.4f}"
        )
    elif best:
        verdict = "llse_higharg2_refinement_no_improvement"
        next_action = (
            "derive LLSE semantics beyond high-arg2 threshold/direction/x-policy variants; "
            f"best remains {semantic_summary.get('best_mode', '')}"
        )
    else:
        verdict = "llse_higharg2_refinement_no_rows"
        next_action = "review LLSE high-arg2 refinement probe inputs"
    return {
        "scope": "total",
        "segment_rows": str(len({row.get("segment_id", "") for row in rows if row.get("segment_id")})),
        "variant_rows": str(len(rows)),
        "preview_rows": str(min(preview_limit, len(rows))),
        "native_previews": str(native_previews),
        "fullhd_previews": str(fullhd_previews),
        "nonblank_previews": str(nonblank),
        "semantic_baseline_mode": semantic_summary.get("best_mode", ""),
        "semantic_baseline_score": semantic_summary.get("best_score", ""),
        "best_variant": best.get("variant_id", ""),
        "best_score": best.get("score", ""),
        "best_delta_vs_semantic": best.get("delta_vs_semantic", ""),
        "best_zero_policy": best.get("zero_policy", ""),
        "best_dy_policy": best.get("dy_policy", ""),
        "best_threshold": best.get("threshold", ""),
        "best_x_policy": best.get("x_policy", ""),
        "best_skip": best.get("skip", ""),
        "best_filled_ratio": best.get("filled_ratio", ""),
        "best_final_y": best.get("final_y", ""),
        "issue_rows": str(issue_rows),
        "refinement_verdict": verdict,
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
        native_path = row.get("native_preview_path", "")
        if not native_path:
            continue
        native = html.escape(relative_href(native_path, output_dir))
        fullhd = html.escape(relative_href(row.get("fullhd_preview_path", ""), output_dir))
        cards.append(
            "<figure>"
            f"<a href=\"{fullhd}\"><img src=\"{native}\" loading=\"lazy\" decoding=\"async\" alt=\"\"></a>"
            f"<figcaption>{html.escape(row.get('variant_id', ''))}<br>"
            f"score {html.escape(row.get('score', ''))} delta {html.escape(row.get('delta_vs_semantic', ''))}<br>"
            f"<a href=\"{native}\">native</a><a href=\"{fullhd}\">fullhd</a></figcaption>"
            "</figure>"
        )
    return "\n".join(cards)


def build_html(summary: dict[str, str], rows: list[dict[str, str]], output_dir: Path, title: str) -> str:
    payload = {"summary": summary, "variants": rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f"<a href=\"{html.escape(relative_href(path, output_dir))}\">{html.escape(label)}</a>"
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
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
td {{ max-width: 560px; overflow-wrap: anywhere; }}
section {{ margin-bottom: 20px; }}
</style>
</head>
<body>
<header>
  <h1>{html.escape(title)}</h1>
  <div class="muted">Focused LLSE high-arg2 cmd20 threshold, direction, x-policy, zero-policy, and skip sweep.</div>
  <p>{links}</p>
</header>
<main>
  <section class="grid">
    <div class="stat"><div class="label">Variants</div><div class="value">{html.escape(summary['variant_rows'])}</div></div>
    <div class="stat"><div class="label">Best Score</div><div class="value warn">{html.escape(summary['best_score'])}</div></div>
    <div class="stat"><div class="label">Delta</div><div class="value">{html.escape(summary['best_delta_vs_semantic'])}</div></div>
    <div class="stat"><div class="label">Issues</div><div class="value ok">{html.escape(summary['issue_rows'])}</div></div>
  </section>
  <section class="grid">{render_cards(rows, output_dir)}</section>
  <section class="panel"><h2>Summary</h2>{render_table([summary], SUMMARY_FIELDNAMES)}</section>
  <section class="panel"><h2>Variants</h2>{render_table(rows, VARIANT_FIELDNAMES)}</section>
</main>
<script type="application/json" id="llse-higharg2-refinement-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> tuple[dict[str, str], list[dict[str, str]]]:
    args.output.mkdir(parents=True, exist_ok=True)
    semantic_summary = read_summary(args.semantic_summary)
    semantic_baseline = float_text(semantic_summary.get("best_score"))
    palette = read_palette(args.palette)
    segment_rows = [row for row in read_csv(args.segments) if row.get("control_path") == TARGET_CONTROL_PATH]
    payload_cache: dict[Path, bytes] = {}
    rows: list[dict[str, str]] = []
    pixels_by_id: dict[str, bytes] = {}
    for source in segment_rows:
        body, issues = load_body(source, payload_cache, args.mix_entry_index)
        for variant in build_variants():
            row, pixels = evaluate_variant(
                source,
                body,
                issues,
                variant,
                args.width,
                args.height,
                args.low,
                args.high,
                semantic_baseline,
            )
            rows.append(row)
            if pixels:
                pixels_by_id[row["variant_id"]] = pixels
    rows.sort(key=lambda row: (bool(row.get("issues")), float_text(row.get("score")), row.get("variant_id", "")))
    for rank, row in enumerate(rows, 1):
        row["rank"] = str(rank)
    sheet_entries = write_previews(rows, pixels_by_id, palette, args.output, args.preview_limit)
    make_sheet(sheet_entries, args.output / "sheet.png", 4, 180)
    summary = summary_row(rows, semantic_summary, args.preview_limit)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "variants.csv", VARIANT_FIELDNAMES, rows)
    (args.output / "index.html").write_text(build_html(summary, rows, args.output, args.title), encoding="utf-8")
    return summary, rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Refine LLSE high-arg2 cmd20 semantics.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--segments", type=Path, default=DEFAULT_SEGMENTS)
    parser.add_argument("--semantic-summary", type=Path, default=DEFAULT_SEMANTIC_SUMMARY)
    parser.add_argument("-p", "--palette", type=Path, default=DEFAULT_PALETTE)
    parser.add_argument("--mix-entry-index", type=int, default=DEFAULT_MIX_ENTRY_INDEX)
    parser.add_argument("--width", type=int, default=64)
    parser.add_argument("--height", type=int, default=512)
    parser.add_argument("--low", type=lambda value: int(value, 0), default=0x30)
    parser.add_argument("--high", type=lambda value: int(value, 0), default=0xBF)
    parser.add_argument("--preview-limit", type=int, default=32)
    parser.add_argument("--title", default="Lands of Lore II .tex LLSE High-arg2 Refinement Probe")
    args = parser.parse_args()

    summary, _rows = write_report(args)
    print(f"Segments: {summary['segment_rows']}")
    print(f"Variant rows: {summary['variant_rows']}")
    print(f"Semantic baseline: {summary['semantic_baseline_score']}")
    print(f"Best variant: {summary['best_variant']}")
    print(f"Best score: {summary['best_score']}")
    print(f"Best delta: {summary['best_delta_vs_semantic']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"Refinement verdict: {summary['refinement_verdict']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
