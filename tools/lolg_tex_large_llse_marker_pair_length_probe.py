#!/usr/bin/env python3
"""Refine LLSE marker-pair lengths around the best global marker policy."""

from __future__ import annotations

import argparse
import csv
import html
import json
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from export_shp import read_palette
from export_te_span_previews import make_sheet, render_indexed
from lolg_tex_large_body_control_grammar_probe import int_value, write_csv
from lolg_tex_large_llse_higharg2_refinement_probe import (
    advance,
    apply_x_policy,
    float_text,
    fullhd_image,
    is_known_marker_pair,
    marker_payload_start,
    marker_symmetric_header,
    put_pixel,
    relative_href,
    safe_name,
    signed_byte,
    visible_ratio,
)
from lolg_tex_large_llse_marker_semantics_probe import (
    DEFAULT_HIGHARG2_SUMMARY,
    DEFAULT_MIX_ENTRY_INDEX,
    DEFAULT_PALETTE,
    DEFAULT_SEGMENTS,
    TARGET_CONTROL_PATH,
    apply_marker_skip_policy,
    apply_symmetric_policy,
    load_body,
    parse_threshold,
    read_csv,
    read_summary,
    render_table,
)
from score_te_raw_layouts import row_score


DEFAULT_OUTPUT = Path("output/tex_large_llse_marker_pair_length_probe")
DEFAULT_MARKER_SUMMARY = Path("output/tex_large_llse_marker_semantics_probe/summary.csv")
MARKER_PAIRS = ("2730", "2830", "2930", "2a30", "2b30", "2b31")

SUMMARY_FIELDNAMES = [
    "scope",
    "segment_rows",
    "variant_rows",
    "preview_rows",
    "native_previews",
    "fullhd_previews",
    "nonblank_variants",
    "marker_baseline_variant",
    "marker_baseline_score",
    "best_variant",
    "best_score",
    "best_delta_vs_marker",
    "best_base_pair_policy",
    "best_symmetric_policy",
    "best_override_pair",
    "best_override_policy",
    "best_marker_pair_seen",
    "best_marker_bytes_skipped",
    "issue_rows",
    "pair_length_verdict",
    "next_action",
]

VARIANT_FIELDNAMES = [
    "rank",
    "variant_id",
    "segment_id",
    "archive",
    "archive_tag",
    "pcx_name",
    "base_pair_policy",
    "symmetric_policy",
    "override_pair",
    "override_policy",
    "policy_2730",
    "policy_2830",
    "policy_2930",
    "policy_2a30",
    "policy_2b30",
    "policy_2b31",
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
    "delta_vs_marker",
    "filled_ratio",
    "visible_pixels",
    "unique_colors",
    "emitted",
    "final_x",
    "final_y",
    "cmd20_seen",
    "cmd20_skipped",
    "cmd20_zero_seen",
    "cmd20_higharg2_applied",
    "cmd20_generic_skipped",
    "symmetric_seen",
    "marker_pair_seen",
    "marker_2730_seen",
    "marker_2830_seen",
    "marker_2930_seen",
    "marker_2a30_seen",
    "marker_2b30_seen",
    "marker_2b31_seen",
    "marker_advances",
    "marker_lines",
    "marker_bytes_skipped",
    "native_preview_path",
    "native_preview_exists",
    "fullhd_preview_path",
    "fullhd_preview_exists",
    "issues",
]


@dataclass(frozen=True)
class PairLengthVariant:
    base_pair_policy: str
    symmetric_policy: str
    override_pair: str
    override_policy: str
    zero_policy: str
    dy_policy: str
    threshold: int
    x_policy: str
    skip: int

    @property
    def variant_id(self) -> str:
        suffix = (
            "baseline"
            if not self.override_pair
            else f"{self.override_pair}-{self.override_policy}"
        )
        return f"base-{self.base_pair_policy}_sym-{self.symmetric_policy}_{suffix}"

    def policy_for_pair(self, pair: str) -> str:
        if pair == self.override_pair:
            return self.override_policy
        return self.base_pair_policy


def build_variants(
    higharg2_summary: dict[str, str],
    marker_summary: dict[str, str],
    max_pair_skip: int,
) -> list[PairLengthVariant]:
    zero_policy = higharg2_summary.get("best_zero_policy", "drop") or "drop"
    dy_policy = higharg2_summary.get("best_dy_policy", "add") or "add"
    threshold = parse_threshold(higharg2_summary.get("best_threshold", "0xc0"))
    x_policy = higharg2_summary.get("best_x_policy", "keep") or "keep"
    skip = int_value(higharg2_summary, "best_skip") or 3
    base_pair_policy = marker_summary.get("best_pair_policy", "skip7") or "skip7"
    symmetric_policy = marker_summary.get("best_symmetric_policy", "skip2") or "skip2"
    variants = [
        PairLengthVariant(
            base_pair_policy=base_pair_policy,
            symmetric_policy=symmetric_policy,
            override_pair="",
            override_policy="",
            zero_policy=zero_policy,
            dy_policy=dy_policy,
            threshold=threshold,
            x_policy=x_policy,
            skip=skip,
        )
    ]
    for pair in MARKER_PAIRS:
        for length in range(2, max_pair_skip + 1):
            policy = f"skip{length}"
            if policy == base_pair_policy:
                continue
            variants.append(
                PairLengthVariant(
                    base_pair_policy=base_pair_policy,
                    symmetric_policy=symmetric_policy,
                    override_pair=pair,
                    override_policy=policy,
                    zero_policy=zero_policy,
                    dy_policy=dy_policy,
                    threshold=threshold,
                    x_policy=x_policy,
                    skip=skip,
                )
            )
    return variants


def decode_pair_lengths(
    payload: bytes,
    width: int,
    height: int,
    variant: PairLengthVariant,
    low: int,
    high: int,
) -> tuple[bytes, dict[str, int]]:
    pixels = bytearray(width * height)
    x = y = 0
    pos = 0
    emitted = 0
    stats = {
        "cmd20_seen": 0,
        "cmd20_skipped": 0,
        "cmd20_zero_seen": 0,
        "cmd20_higharg2_applied": 0,
        "cmd20_generic_skipped": 0,
        "symmetric_seen": 0,
        "marker_pair_seen": 0,
        "marker_advances": 0,
        "marker_lines": 0,
        "marker_bytes_skipped": 0,
        **{f"marker_{pair}_seen": 0 for pair in MARKER_PAIRS},
    }
    while pos < len(payload) and y < height:
        byte = payload[pos]
        pos += 1
        if marker_symmetric_header(payload, byte, pos):
            stats["symmetric_seen"] += 1
            x, y, pos = apply_symmetric_policy(
                x, y, width, height, pos, len(payload), variant.symmetric_policy, stats
            )
            continue
        if pos < len(payload) and is_known_marker_pair(byte, payload[pos]):
            pair = f"{byte:02x}{payload[pos]:02x}"
            stats["marker_pair_seen"] += 1
            stats[f"marker_{pair}_seen"] += 1
            x, y, pos = apply_marker_skip_policy(
                x,
                y,
                width,
                height,
                pos,
                len(payload),
                variant.policy_for_pair(pair),
                stats,
            )
            continue
        if byte == 0x20:
            stats["cmd20_seen"] += 1
            arg1 = payload[pos] if pos < len(payload) else 0
            arg2 = payload[pos + 1] if pos + 1 < len(payload) else 0
            arg3 = payload[pos + 2] if pos + 2 < len(payload) else 0
            if (arg1, arg2, arg3) == (0, 0, 0):
                stats["cmd20_zero_seen"] += 1
                if variant.zero_policy == "line":
                    x = 0
                    y = min(height, y + 1)
                    pos = min(len(payload), pos + variant.skip)
                    stats["cmd20_skipped"] += 1
                    continue
                if variant.zero_policy == "skip":
                    pos = min(len(payload), pos + variant.skip)
                    stats["cmd20_skipped"] += 1
                    continue
                continue
            if arg2 >= variant.threshold:
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
            stats["cmd20_generic_skipped"] += 1
            continue
        if low <= byte <= high:
            put_pixel(pixels, width, height, x, y, byte)
            x, y = advance(x, y, width, 1)
            emitted += 1
    stats["emitted"] = emitted
    stats["final_x"] = x
    stats["final_y"] = y
    return bytes(pixels), stats


def evaluate_variant(
    source: dict[str, str],
    body: bytes,
    body_issues: list[str],
    variant: PairLengthVariant,
    width: int,
    height: int,
    low: int,
    high: int,
    marker_baseline: float,
) -> tuple[dict[str, str], bytes]:
    issues = list(body_issues)
    if not body:
        issues.append("empty_body")
    offset = marker_payload_start(body)
    payload = body[offset:] if not issues else b""
    pixels = b""
    stats: dict[str, int] = {}
    if not issues:
        pixels, stats = decode_pair_lengths(payload, width, height, variant, low, high)
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
            "base_pair_policy": variant.base_pair_policy,
            "symmetric_policy": variant.symmetric_policy,
            "override_pair": variant.override_pair,
            "override_policy": variant.override_policy,
            **{f"policy_{pair}": variant.policy_for_pair(pair) for pair in MARKER_PAIRS},
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
            "delta_vs_marker": f"{score - marker_baseline:.4f}",
            "filled_ratio": f"{visible_ratio(pixels):.6f}" if pixels else "0.000000",
            "visible_pixels": str(visible),
            "unique_colors": str(len(set(pixels)) if pixels else 0),
            "emitted": str(stats.get("emitted", "")),
            "final_x": str(stats.get("final_x", "")),
            "final_y": str(stats.get("final_y", "")),
            "cmd20_seen": str(stats.get("cmd20_seen", "")),
            "cmd20_skipped": str(stats.get("cmd20_skipped", "")),
            "cmd20_zero_seen": str(stats.get("cmd20_zero_seen", "")),
            "cmd20_higharg2_applied": str(stats.get("cmd20_higharg2_applied", "")),
            "cmd20_generic_skipped": str(stats.get("cmd20_generic_skipped", "")),
            "symmetric_seen": str(stats.get("symmetric_seen", "")),
            "marker_pair_seen": str(stats.get("marker_pair_seen", "")),
            **{f"marker_{pair}_seen": str(stats.get(f"marker_{pair}_seen", "")) for pair in MARKER_PAIRS},
            "marker_advances": str(stats.get("marker_advances", "")),
            "marker_lines": str(stats.get("marker_lines", "")),
            "marker_bytes_skipped": str(stats.get("marker_bytes_skipped", "")),
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
        label = row.get("override_pair") or "baseline"
        sheet_entries.append((f"{row['rank']} {row['score']} {label}", image))
    return sheet_entries


def summary_row(rows: list[dict[str, str]], marker_summary: dict[str, str], preview_limit: int) -> dict[str, str]:
    clean_rows = [row for row in rows if not row.get("issues")]
    best = clean_rows[0] if clean_rows else {}
    issue_rows = sum(1 for row in rows if row.get("issues"))
    native_previews = sum(1 for row in rows if row.get("native_preview_exists") == "yes")
    fullhd_previews = sum(1 for row in rows if row.get("fullhd_preview_exists") == "yes")
    nonblank = sum(1 for row in rows if int_value(row, "visible_pixels") > 0)
    best_delta = float_text(best.get("delta_vs_marker"))
    if issue_rows:
        verdict = "llse_marker_pair_length_probe_issues"
        next_action = "fix LLSE marker pair length probe inputs"
    elif best and best_delta < 0:
        verdict = "llse_marker_pair_length_candidate_improves"
        next_action = (
            "inspect LLSE marker pair length candidate "
            f"{best.get('variant_id', '')}; score delta {best_delta:.4f}"
        )
    elif best:
        verdict = "llse_marker_pair_length_no_improvement"
        next_action = (
            "derive LLSE marker records beyond one-pair length overrides; "
            f"baseline {marker_summary.get('best_variant', '')}"
        )
    else:
        verdict = "llse_marker_pair_length_no_rows"
        next_action = "review LLSE marker pair length probe inputs"
    return {
        "scope": "total",
        "segment_rows": str(len({row.get("segment_id", "") for row in rows if row.get("segment_id")})),
        "variant_rows": str(len(rows)),
        "preview_rows": str(min(preview_limit, len(rows))),
        "native_previews": str(native_previews),
        "fullhd_previews": str(fullhd_previews),
        "nonblank_variants": str(nonblank),
        "marker_baseline_variant": marker_summary.get("best_variant", ""),
        "marker_baseline_score": marker_summary.get("best_score", ""),
        "best_variant": best.get("variant_id", ""),
        "best_score": best.get("score", ""),
        "best_delta_vs_marker": best.get("delta_vs_marker", ""),
        "best_base_pair_policy": best.get("base_pair_policy", ""),
        "best_symmetric_policy": best.get("symmetric_policy", ""),
        "best_override_pair": best.get("override_pair", ""),
        "best_override_policy": best.get("override_policy", ""),
        "best_marker_pair_seen": best.get("marker_pair_seen", ""),
        "best_marker_bytes_skipped": best.get("marker_bytes_skipped", ""),
        "issue_rows": str(issue_rows),
        "pair_length_verdict": verdict,
        "next_action": next_action,
    }


def render_cards(rows: list[dict[str, str]], output_dir: Path, limit: int = 24) -> str:
    cards = []
    for row in rows[:limit]:
        native_path = row.get("native_preview_path", "")
        if not native_path:
            continue
        native = html.escape(relative_href(native_path, output_dir))
        fullhd = html.escape(relative_href(row.get("fullhd_preview_path", ""), output_dir))
        title = row.get("override_pair") or "baseline"
        policy = row.get("override_policy") or row.get("base_pair_policy", "")
        cards.append(
            "<figure>"
            f"<a href=\"{fullhd}\"><img src=\"{native}\" loading=\"lazy\" decoding=\"async\" alt=\"\"></a>"
            f"<figcaption>{html.escape(title)} {html.escape(policy)}<br>"
            f"score {html.escape(row.get('score', ''))} delta {html.escape(row.get('delta_vs_marker', ''))}<br>"
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
  <div class="muted">One-pair marker length overrides around the best LLSE global marker policy.</div>
  <p>{links}</p>
</header>
<main>
  <section class="grid">
    <div class="stat"><div class="label">Variants</div><div class="value">{html.escape(summary['variant_rows'])}</div></div>
    <div class="stat"><div class="label">Best Pair</div><div class="value">{html.escape(summary['best_override_pair'] or 'baseline')}</div></div>
    <div class="stat"><div class="label">Delta</div><div class="value warn">{html.escape(summary['best_delta_vs_marker'])}</div></div>
    <div class="stat"><div class="label">Issues</div><div class="value ok">{html.escape(summary['issue_rows'])}</div></div>
  </section>
  <section class="grid">{render_cards(rows, output_dir)}</section>
  <section class="panel"><h2>Summary</h2>{render_table([summary], SUMMARY_FIELDNAMES)}</section>
  <section class="panel"><h2>Variants</h2>{render_table(rows, VARIANT_FIELDNAMES)}</section>
</main>
<script type="application/json" id="llse-marker-pair-length-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> tuple[dict[str, str], list[dict[str, str]]]:
    args.output.mkdir(parents=True, exist_ok=True)
    higharg2_summary = read_summary(args.higharg2_summary)
    marker_summary = read_summary(args.marker_summary)
    marker_baseline = float_text(marker_summary.get("best_score"))
    palette = read_palette(args.palette)
    segment_rows = [row for row in read_csv(args.segments) if row.get("control_path") == TARGET_CONTROL_PATH]
    payload_cache: dict[Path, bytes] = {}
    rows: list[dict[str, str]] = []
    pixels_by_id: dict[str, bytes] = {}
    for source in segment_rows:
        body, issues = load_body(source, payload_cache, args.mix_entry_index)
        for variant in build_variants(higharg2_summary, marker_summary, args.max_pair_skip):
            row, pixels = evaluate_variant(
                source,
                body,
                issues,
                variant,
                args.width,
                args.height,
                args.low,
                args.high,
                marker_baseline,
            )
            rows.append(row)
            if pixels:
                pixels_by_id[row["variant_id"]] = pixels
    rows.sort(key=lambda row: (bool(row.get("issues")), float_text(row.get("score")), row.get("variant_id", "")))
    for rank, row in enumerate(rows, 1):
        row["rank"] = str(rank)
    sheet_entries = write_previews(rows, pixels_by_id, palette, args.output, args.preview_limit)
    make_sheet(sheet_entries, args.output / "sheet.png", 4, 180)
    summary = summary_row(rows, marker_summary, args.preview_limit)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "variants.csv", VARIANT_FIELDNAMES, rows)
    (args.output / "index.html").write_text(build_html(summary, rows, args.output, args.title), encoding="utf-8")
    return summary, rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Refine LLSE marker-pair lengths.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--segments", type=Path, default=DEFAULT_SEGMENTS)
    parser.add_argument("--higharg2-summary", type=Path, default=DEFAULT_HIGHARG2_SUMMARY)
    parser.add_argument("--marker-summary", type=Path, default=DEFAULT_MARKER_SUMMARY)
    parser.add_argument("-p", "--palette", type=Path, default=DEFAULT_PALETTE)
    parser.add_argument("--mix-entry-index", type=int, default=DEFAULT_MIX_ENTRY_INDEX)
    parser.add_argument("--width", type=int, default=64)
    parser.add_argument("--height", type=int, default=512)
    parser.add_argument("--low", type=lambda value: int(value, 0), default=0x30)
    parser.add_argument("--high", type=lambda value: int(value, 0), default=0xBF)
    parser.add_argument("--preview-limit", type=int, default=32)
    parser.add_argument("--max-pair-skip", type=int, default=10)
    parser.add_argument("--title", default="Lands of Lore II .tex LLSE Marker Pair Length Probe")
    args = parser.parse_args()

    summary, _rows = write_report(args)
    print(f"Segments: {summary['segment_rows']}")
    print(f"Variant rows: {summary['variant_rows']}")
    print(f"Marker baseline: {summary['marker_baseline_score']}")
    print(f"Best variant: {summary['best_variant']}")
    print(f"Best score: {summary['best_score']}")
    print(f"Best delta: {summary['best_delta_vs_marker']}")
    print(f"Best override: {summary['best_override_pair']} {summary['best_override_policy']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"Pair-length verdict: {summary['pair_length_verdict']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
