#!/usr/bin/env python3
"""Replay the selected shared 0x2700302b payload start for large .tex bodies."""

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
from probe_te_span_decode import decode_span
from score_te_raw_layouts import row_score


DEFAULT_OUTPUT = Path("output/tex_large_shared_2700302b_payload_replay")
DEFAULT_HEADER_SUMMARY = Path("output/tex_large_shared_2700302b_header_probe/summary.csv")
DEFAULT_SEGMENTS = Path("output/tex_large_rejected_decoder_profile/segments.csv")
DEFAULT_TRACE_CANDIDATES = Path("output/tex_large_body_control_grammar_probe/trace_candidates.csv")
DEFAULT_PALETTE = Path("extracted/LOCAL/7231c8f9.pal")
DEFAULT_MIX_ENTRY_INDEX = 2
TARGET_CONTROL_PATH = "shared_2700302b_header"
TARGET_SIZE = (1920, 1080)

SUMMARY_FIELDNAMES = [
    "scope",
    "replay_rows",
    "native_previews",
    "fullhd_previews",
    "nonblank_previews",
    "offset",
    "mode",
    "width_groups",
    "avg_score",
    "max_score",
    "avg_filled_ratio",
    "min_filled_ratio",
    "max_final_y",
    "max_non_noisy_score",
    "issue_rows",
    "verdict",
    "next_action",
]

REPLAY_FIELDNAMES = [
    "replay_id",
    "segment_id",
    "archive",
    "archive_tag",
    "pcx_name",
    "offset",
    "mode",
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
    "native_preview_path",
    "native_preview_exists",
    "fullhd_preview_path",
    "fullhd_preview_exists",
    "issues",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
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


def trace_dimensions(
    trace_rows: list[dict[str, str]],
    segment_id: str,
    offset: int,
    mode: str,
) -> tuple[int, int]:
    matches = [
        row
        for row in trace_rows
        if row.get("segment_id") == segment_id
        and int_value(row, "offset") == offset
        and row.get("mode") == mode
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


def replay_row(
    source: dict[str, str],
    body: bytes,
    body_issues: list[str],
    trace_rows: list[dict[str, str]],
    palette: list[tuple[int, int, int]],
    output_dir: Path,
    offset: int,
    mode: str,
    low: int,
    high: int,
) -> tuple[dict[str, str], Image.Image | None]:
    issues = list(body_issues)
    segment_id = source.get("segment_id", "")
    if not body:
        issues.append("empty_body")
    if offset < 0 or offset >= len(body):
        issues.append("offset_out_of_body")
    width, height = trace_dimensions(trace_rows, segment_id, offset, mode)
    if width <= 0 or height <= 0:
        issues.append("invalid_dimensions")

    payload = body[offset:] if not issues else b""
    pixels = b""
    stats: dict[str, object] = {}
    native_path = output_dir / "native" / safe_name(source.get("archive_tag", ""))
    native_file = native_path / f"{safe_name(source.get('pcx_name', ''))}_off{offset}_{safe_name(mode)}.png"
    fullhd_path = output_dir / "fullhd" / safe_name(source.get("archive_tag", ""))
    fullhd_file = fullhd_path / f"{safe_name(source.get('pcx_name', ''))}_off{offset}_{safe_name(mode)}_fullhd.png"
    image: Image.Image | None = None
    if not issues:
        pixels, stats = decode_span(payload, width, height, mode, low, high, return_stats=True)
        image = render_indexed(pixels, width, height, palette)
        native_path.mkdir(parents=True, exist_ok=True)
        fullhd_path.mkdir(parents=True, exist_ok=True)
        image.save(native_file)
        fullhd_image(image).save(fullhd_file)

    score = row_score(pixels, width, height) if pixels else None
    filled = visible_ratio(pixels) if pixels else 0.0
    visible_pixels = sum(1 for pixel in pixels if pixel)
    if image is None:
        issues.append("missing_preview")
    elif visible_pixels <= 0:
        issues.append("blank_preview")
    return (
        {
            "replay_id": f"{safe_name(source.get('archive_tag', ''))}__{safe_name(source.get('pcx_name', ''))}",
            "segment_id": segment_id,
            "archive": source.get("archive", ""),
            "archive_tag": source.get("archive_tag", ""),
            "pcx_name": source.get("pcx_name", ""),
            "offset": str(offset),
            "mode": mode,
            "width": str(width),
            "height": str(height),
            "payload_bytes": str(len(payload)),
            "score": f"{float(score) if score is not None else 0.0:.4f}",
            "filled_ratio": f"{filled:.6f}",
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
            "native_preview_path": native_file.as_posix(),
            "native_preview_exists": "yes" if native_file.exists() else "no",
            "fullhd_preview_path": fullhd_file.as_posix(),
            "fullhd_preview_exists": "yes" if fullhd_file.exists() else "no",
            "issues": ";".join(sorted(set(issues))),
        },
        image,
    )


def build_replay_rows(
    header_summary: dict[str, str],
    segment_rows: list[dict[str, str]],
    trace_rows: list[dict[str, str]],
    palette_path: Path,
    output_dir: Path,
    mix_entry_index: int,
    low: int,
    high: int,
) -> tuple[list[dict[str, str]], list[tuple[str, Image.Image]]]:
    offset = int_value(header_summary, "best_offset")
    mode = header_summary.get("best_mode", "")
    palette = read_palette(palette_path)
    payload_cache: dict[Path, bytes] = {}
    rows: list[dict[str, str]] = []
    sheet_entries: list[tuple[str, Image.Image]] = []
    for source in segment_rows:
        if source.get("control_path") != TARGET_CONTROL_PATH:
            continue
        body, issues = load_body(source, payload_cache, mix_entry_index)
        row, image = replay_row(source, body, issues, trace_rows, palette, output_dir, offset, mode, low, high)
        rows.append(row)
        if image is not None:
            sheet_entries.append((f"{row['archive_tag']} {row['pcx_name']}", image))
    return rows, sheet_entries


def summary_row(
    rows: list[dict[str, str]],
    header_summary: dict[str, str],
    max_non_noisy_score: float,
) -> dict[str, str]:
    scores = [float_text(row.get("score")) for row in rows if not row.get("issues")]
    filled = [float_text(row.get("filled_ratio")) for row in rows if not row.get("issues")]
    final_y = [int_value(row, "final_y") for row in rows if row.get("final_y")]
    issue_rows = sum(1 for row in rows if row.get("issues"))
    native_previews = sum(1 for row in rows if row.get("native_preview_exists") == "yes")
    fullhd_previews = sum(1 for row in rows if row.get("fullhd_preview_exists") == "yes")
    nonblank = sum(1 for row in rows if int_value(row, "visible_pixels") > 0)
    max_score = max(scores) if scores else 0.0
    if issue_rows:
        verdict = "shared_2700302b_payload_replay_issues"
        next_action = "fix shared 0x2700302b payload replay issues"
    elif max_score > max_non_noisy_score:
        verdict = "shared_2700302b_payload_replay_noisy"
        next_action = (
            "derive shared 0x2700302b renderer grammar beyond "
            f"offset {header_summary.get('best_offset', '')} {header_summary.get('best_mode', '')}; "
            f"max score {max_score:.4f} remains noisy"
        )
    elif rows and native_previews == len(rows) and fullhd_previews == len(rows) and nonblank == len(rows):
        verdict = "shared_2700302b_payload_replay_ready"
        next_action = "review shared 0x2700302b payload replay previews before decoder promotion"
    else:
        verdict = "shared_2700302b_payload_replay_incomplete"
        next_action = "complete shared 0x2700302b payload replay previews"
    return {
        "scope": "total",
        "replay_rows": str(len(rows)),
        "native_previews": str(native_previews),
        "fullhd_previews": str(fullhd_previews),
        "nonblank_previews": str(nonblank),
        "offset": header_summary.get("best_offset", ""),
        "mode": header_summary.get("best_mode", ""),
        "width_groups": str(len({row.get("width", "") for row in rows if row.get("width")})),
        "avg_score": f"{sum(scores) / max(1, len(scores)):.4f}" if scores else "0.0000",
        "max_score": f"{max_score:.4f}",
        "avg_filled_ratio": f"{sum(filled) / max(1, len(filled)):.6f}" if filled else "0.000000",
        "min_filled_ratio": f"{min(filled) if filled else 0.0:.6f}",
        "max_final_y": str(max(final_y) if final_y else 0),
        "max_non_noisy_score": f"{max_non_noisy_score:.4f}",
        "issue_rows": str(issue_rows),
        "verdict": verdict,
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


def render_cards(rows: list[dict[str, str]], output_dir: Path) -> str:
    cards = []
    for row in rows:
        native = html.escape(relative_href(row.get("native_preview_path", ""), output_dir))
        fullhd = html.escape(relative_href(row.get("fullhd_preview_path", ""), output_dir))
        cards.append(
            "<figure>"
            f"<a href=\"{fullhd}\"><img src=\"{native}\" loading=\"lazy\" decoding=\"async\" alt=\"\"></a>"
            f"<figcaption>{html.escape(row.get('archive_tag', ''))} / {html.escape(row.get('pcx_name', ''))}<br>"
            f"score {html.escape(row.get('score', ''))} fill {html.escape(row.get('filled_ratio', ''))}<br>"
            f"<a href=\"{native}\">native</a><a href=\"{fullhd}\">fullhd</a></figcaption>"
            "</figure>"
        )
    return "\n".join(cards)


def build_html(summary: dict[str, str], rows: list[dict[str, str]], output_dir: Path, title: str) -> str:
    payload = {"summary": summary, "replays": rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f"<a href=\"{html.escape(relative_href(path, output_dir))}\">{html.escape(label)}</a>"
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("replays.csv", output_dir / "replays.csv"),
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
figure img {{ width: 100%; height: 260px; object-fit: contain; image-rendering: pixelated; background: #050607; }}
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
  <div class="muted">Native and Full HD previews for the selected shared 0x2700302b replay.</div>
  <p>{links}</p>
</header>
<main>
  <section class="grid">
    <div class="stat"><div class="label">Replays</div><div class="value">{html.escape(summary['replay_rows'])}</div></div>
    <div class="stat"><div class="label">Full HD</div><div class="value ok">{html.escape(summary['fullhd_previews'])}</div></div>
    <div class="stat"><div class="label">Min fill</div><div class="value warn">{html.escape(summary['min_filled_ratio'])}</div></div>
    <div class="stat"><div class="label">Issues</div><div class="value ok">{html.escape(summary['issue_rows'])}</div></div>
  </section>
  <section class="grid">{render_cards(rows, output_dir)}</section>
  <section class="panel">
    <h2>Summary</h2>
    {render_table([summary], SUMMARY_FIELDNAMES)}
  </section>
  <section class="panel">
    <h2>Replays</h2>
    {render_table(rows, REPLAY_FIELDNAMES)}
  </section>
</main>
<script type="application/json" id="replay-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    header_summary_path: Path,
    segments_path: Path,
    trace_candidates_path: Path,
    palette_path: Path,
    mix_entry_index: int,
    low: int,
    high: int,
    max_non_noisy_score: float,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    header_summary = read_summary(header_summary_path)
    rows, sheet_entries = build_replay_rows(
        header_summary,
        read_csv(segments_path),
        read_csv(trace_candidates_path),
        palette_path,
        output_dir,
        mix_entry_index,
        low,
        high,
    )
    summary = summary_row(rows, header_summary, max_non_noisy_score)
    sheet_path = output_dir / "sheet.png"
    make_sheet(sheet_entries, sheet_path, 2, 240)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "replays.csv", REPLAY_FIELDNAMES, rows)
    (output_dir / "index.html").write_text(build_html(summary, rows, output_dir, title))
    return summary, rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay shared 0x2700302b payload start previews.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--header-summary", type=Path, default=DEFAULT_HEADER_SUMMARY)
    parser.add_argument("--segments", type=Path, default=DEFAULT_SEGMENTS)
    parser.add_argument("--trace-candidates", type=Path, default=DEFAULT_TRACE_CANDIDATES)
    parser.add_argument("-p", "--palette", type=Path, default=DEFAULT_PALETTE)
    parser.add_argument("--mix-entry-index", type=int, default=DEFAULT_MIX_ENTRY_INDEX)
    parser.add_argument("--low", type=lambda value: int(value, 0), default=0x30)
    parser.add_argument("--high", type=lambda value: int(value, 0), default=0xBF)
    parser.add_argument("--max-non-noisy-score", type=float, default=40.0)
    parser.add_argument("--title", default="Lands of Lore II .tex Shared 0x2700302b Payload Replay")
    args = parser.parse_args()

    summary, _rows = write_report(
        args.output,
        args.header_summary,
        args.segments,
        args.trace_candidates,
        args.palette,
        args.mix_entry_index,
        args.low,
        args.high,
        args.max_non_noisy_score,
        args.title,
    )
    print(f"Replay rows: {summary['replay_rows']}")
    print(f"Native previews: {summary['native_previews']}")
    print(f"Full HD previews: {summary['fullhd_previews']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"Verdict: {summary['verdict']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
