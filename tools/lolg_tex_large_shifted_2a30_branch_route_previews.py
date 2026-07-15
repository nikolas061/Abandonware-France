#!/usr/bin/env python3
"""Materialize Full HD previews for routed shifted 0x2a30 branch renderer rows."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import re
from pathlib import Path

from PIL import Image

try:
    from export_shp import read_palette
    from export_te_span_previews import render_indexed
    from score_te_raw_layouts import row_score
except ModuleNotFoundError as exc:
    OPTIONAL_IMPORT_ERROR = exc
    read_palette = None
    render_indexed = None
    row_score = None
else:
    OPTIONAL_IMPORT_ERROR = None
from lolg_tex_large_shifted_2a30_branch_bounded_family_probe import catalog_payloads, key_for
from probe_te_span_decode import decode_span


TARGET_SIZE = (1920, 1080)
ROUTED_STATUS = "routed_branch_start_guard_renderer"
DEFAULT_OUTPUT = Path("output/tex_large_shifted_2a30_branch_route_previews")
DEFAULT_ROUTES = Path("output/tex_large_shifted_2a30_branch_high_arg2_renderer_route_promoted_replay/routes.csv")
DEFAULT_RENDERER_TRACE = Path("output/tex_large_shifted_2a30_branch_selector_probe/renderer_trace.csv")
DEFAULT_FAMILY = Path("output/tex_large_shifted_2a30_branch_bounded_family_probe/family.csv")
DEFAULT_VALIDATION_SUMMARY = Path("output/tex_large_shifted_2a30_branch_high_arg2_skip_validation_probe/summary.csv")
DEFAULT_CATALOG = Path("reports/te_resources.tsv")
DEFAULT_PALETTE = Path("extracted/LOCAL/7231c8f9.pal")
VALIDATION_VERDICT = "high_arg2_skip_only_integrated_for_guarded_extra64"

SUMMARY_FIELDNAMES = [
    "scope",
    "route_rows",
    "routed_rows",
    "manifest_rows",
    "native_previews",
    "fullhd_previews",
    "decoded_rows",
    "validation_verdict",
    "target_archive_tag",
    "target_pcx_name",
    "target_decoder_extra",
    "target_high_arg2_skips",
    "fullhd_width",
    "fullhd_height",
    "issue_rows",
    "review_verdict",
    "next_action",
]

MANIFEST_FIELDNAMES = [
    "archive",
    "archive_tag",
    "texture_path",
    "pcx_name",
    "segment_index",
    "body_offset_hex",
    "segment_size",
    "decoder_rule",
    "decoder_extra",
    "renderer_mode",
    "renderer_start",
    "renderer_width",
    "renderer_height",
    "renderer_score",
    "filled_ratio",
    "unique_colors",
    "high_arg2_skips",
    "zero_signature_seen",
    "zero_signature_skipped",
    "markerknown_skips",
    "final_x",
    "final_y",
    "native_preview_path",
    "native_preview_exists",
    "native_width",
    "native_height",
    "fullhd_preview_path",
    "fullhd_preview_exists",
    "fullhd_width",
    "fullhd_height",
    "issues",
]


def read_csv(path: Path, *, delimiter: str = ",") -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter=delimiter))


def read_summary(path: Path) -> dict[str, str]:
    rows = read_csv(path)
    return rows[0] if rows else {}


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def int_text(value: str | int | None, default: int = 0) -> int:
    try:
        return int(str(value), 0) if value not in (None, "") else default
    except ValueError:
        return default


def float_text(value: str | float | None, default: float = 0.0) -> float:
    try:
        return float(str(value)) if value not in (None, "") else default
    except ValueError:
        return default


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._") or "unnamed"


def route_key(row: dict[str, str]) -> tuple[str, str]:
    return key_for(row.get("archive_tag", ""), row.get("pcx_name", ""))


def marker_lookup(family_rows: list[dict[str, str]]) -> dict[tuple[str, str], int]:
    return {
        key_for(row.get("archive_tag", ""), row.get("pcx_name", "")): int_text(row.get("marker_pos"), -1)
        for row in family_rows
    }


def trace_lookup(trace_rows: list[dict[str, str]]) -> dict[tuple[str, str, str], dict[str, str]]:
    rows: dict[tuple[str, str, str], dict[str, str]] = {}
    for row in sorted(trace_rows, key=lambda item: int_text(item.get("rank"), 999999)):
        if row.get("mode") != "cmd20_high_arg2_skip4_markerknown":
            continue
        key = (row.get("archive_tag", ""), row.get("pcx_name", "").lower(), row.get("extra", ""))
        rows.setdefault(key, row)
    return rows


def visible_ratio(pixels: bytes) -> float:
    return sum(1 for pixel in pixels if pixel) / max(1, len(pixels))


def score_pixels(pixels: bytes, width: int, height: int) -> float:
    score = row_score(pixels, width, height)
    return float(score) if score is not None else 999999.0


def make_fullhd(image: Image.Image) -> Image.Image:
    source = image.convert("RGBA")
    scale = min(TARGET_SIZE[0] / source.width, TARGET_SIZE[1] / source.height)
    scaled_size = (max(1, round(source.width * scale)), max(1, round(source.height * scale)))
    scaled = source.resize(scaled_size, Image.Resampling.NEAREST)
    canvas = Image.new("RGBA", TARGET_SIZE, (0, 0, 0, 0))
    origin = ((TARGET_SIZE[0] - scaled.width) // 2, (TARGET_SIZE[1] - scaled.height) // 2)
    canvas.paste(scaled, origin)
    return canvas


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    if not path_text:
        return ""
    path = Path(path_text)
    try:
        relative = path.relative_to(base_dir)
    except ValueError:
        relative = Path(os.path.relpath(path, base_dir))
    return relative.as_posix()


def validation_issues(route: dict[str, str], summary: dict[str, str]) -> list[str]:
    issues: list[str] = []
    if summary.get("validation_verdict") != VALIDATION_VERDICT:
        issues.append("validation_not_integrated")
    if summary.get("target_archive_tag") and summary.get("target_archive_tag") != route.get("archive_tag"):
        issues.append("validation_target_archive_mismatch")
    if summary.get("target_pcx_name") and summary.get("target_pcx_name", "").lower() != route.get("pcx_name", "").lower():
        issues.append("validation_target_pcx_mismatch")
    if summary.get("target_proposed_mode") and summary.get("target_proposed_mode") != "cmd20_high_arg2_skip4_markerknown":
        issues.append("validation_mode_mismatch")
    if int_text(summary.get("target_high_arg2_skips")) <= 0:
        issues.append("validation_missing_high_arg2")
    return issues


def build_manifest(
    output_dir: Path,
    route_rows: list[dict[str, str]],
    trace_rows: list[dict[str, str]],
    family_rows: list[dict[str, str]],
    validation_summary: dict[str, str],
    catalog: Path,
    palette_path: Path,
    low: int,
    high: int,
) -> list[dict[str, str]]:
    native_dir = output_dir / "native"
    fullhd_dir = output_dir / "fullhd"
    native_dir.mkdir(parents=True, exist_ok=True)
    fullhd_dir.mkdir(parents=True, exist_ok=True)

    trace_by_key = trace_lookup(trace_rows)
    markers = marker_lookup(family_rows)
    routed_rows = [row for row in route_rows if row.get("route_status") == ROUTED_STATUS]
    payloads = catalog_payloads(
        catalog,
        [{"level": row.get("archive_tag", ""), "name": row.get("pcx_name", "")} for row in routed_rows],
    )
    palette = read_palette(palette_path)

    rows: list[dict[str, str]] = []
    for route in routed_rows:
        issues = validation_issues(route, validation_summary)
        key = route_key(route)
        extra = route.get("decoder_extra", "")
        trace = trace_by_key.get((key[0], key[1], extra), {})
        payload = payloads.get(key, b"")
        marker = markers.get(key, -1)
        mode = trace.get("mode", "cmd20_high_arg2_skip4_markerknown")
        width = int_text(trace.get("width"), 48)
        height = int_text(trace.get("height"), 128)
        start = marker + int_text(extra) if marker >= 0 and extra else -1

        if not trace:
            issues.append("missing_renderer_trace")
        if marker < 0:
            issues.append("missing_family_marker")
        if not payload:
            issues.append("missing_payload")
        if start < 0 or start >= len(payload) or width <= 0 or height <= 0:
            issues.append("invalid_renderer_input")

        pixels = b""
        stats: dict[str, int | float] = {}
        native_width = native_height = fullhd_width = fullhd_height = ""
        stem = (
            f"{safe_name(route.get('archive_tag', ''))}__{safe_name(route.get('pcx_name', ''))}"
            f"__seg{safe_name(route.get('segment_index', ''))}_{safe_name(route.get('body_offset_hex', ''))}"
            f"__{safe_name(route.get('decoder_rule', ''))}_extra{safe_name(extra)}"
        )
        native_path = native_dir / f"{stem}.png"
        fullhd_path = fullhd_dir / f"{stem}_fullhd.png"

        if not issues:
            pixels, stats = decode_span(
                payload[start:],
                width,
                height,
                mode,
                low,
                high,
                return_stats=True,
            )
            native = render_indexed(pixels, width, height, palette)
            native.save(native_path, "PNG")
            native_width, native_height = str(native.width), str(native.height)
            fullhd = make_fullhd(native)
            fullhd.save(fullhd_path, "PNG")
            fullhd_width, fullhd_height = str(fullhd.width), str(fullhd.height)

        native_exists = native_path.exists()
        fullhd_exists = fullhd_path.exists()
        if not native_exists:
            issues.append("missing_native_preview")
        if not fullhd_exists:
            issues.append("missing_fullhd_preview")
        if fullhd_exists and (fullhd_width, fullhd_height) != (str(TARGET_SIZE[0]), str(TARGET_SIZE[1])):
            issues.append("fullhd_size_mismatch")

        rows.append(
            {
                "archive": route.get("archive", ""),
                "archive_tag": route.get("archive_tag", ""),
                "texture_path": route.get("texture_path", ""),
                "pcx_name": route.get("pcx_name", ""),
                "segment_index": route.get("segment_index", ""),
                "body_offset_hex": route.get("body_offset_hex", ""),
                "segment_size": route.get("segment_size", ""),
                "decoder_rule": route.get("decoder_rule", ""),
                "decoder_extra": extra,
                "renderer_mode": mode,
                "renderer_start": str(start) if start >= 0 else "",
                "renderer_width": str(width),
                "renderer_height": str(height),
                "renderer_score": f"{score_pixels(pixels, width, height):.4f}" if pixels else "",
                "filled_ratio": f"{visible_ratio(pixels):.4f}" if pixels else "",
                "unique_colors": str(len(set(pixels))) if pixels else "",
                "high_arg2_skips": str(stats.get("high_arg2_skips", "")),
                "zero_signature_seen": str(stats.get("zero_signature_seen", "")),
                "zero_signature_skipped": str(stats.get("zero_signature_skipped", "")),
                "markerknown_skips": str(stats.get("markerknown_skips", "")),
                "final_x": str(stats.get("final_x", "")),
                "final_y": str(stats.get("final_y", "")),
                "native_preview_path": native_path.as_posix(),
                "native_preview_exists": "yes" if native_exists else "no",
                "native_width": native_width,
                "native_height": native_height,
                "fullhd_preview_path": fullhd_path.as_posix(),
                "fullhd_preview_exists": "yes" if fullhd_exists else "no",
                "fullhd_width": fullhd_width,
                "fullhd_height": fullhd_height,
                "issues": "|".join(dict.fromkeys(issues)),
            }
        )
    return sorted(rows, key=lambda row: (row["archive_tag"], row["pcx_name"].lower()))


def build_summary(
    route_rows: list[dict[str, str]],
    manifest_rows: list[dict[str, str]],
    validation_summary: dict[str, str],
) -> dict[str, str]:
    routed_rows = [row for row in route_rows if row.get("route_status") == ROUTED_STATUS]
    native_previews = [row for row in manifest_rows if row.get("native_preview_exists") == "yes"]
    fullhd_previews = [row for row in manifest_rows if row.get("fullhd_preview_exists") == "yes"]
    decoded_rows = [row for row in manifest_rows if int_text(row.get("high_arg2_skips")) > 0]
    issue_rows = [row for row in manifest_rows if row.get("issues")]
    fullhd_good = [
        row
        for row in fullhd_previews
        if (row.get("fullhd_width"), row.get("fullhd_height")) == (str(TARGET_SIZE[0]), str(TARGET_SIZE[1]))
    ]
    clean = (
        len(routed_rows) == 1
        and len(manifest_rows) == 1
        and len(native_previews) == 1
        and len(fullhd_good) == 1
        and len(decoded_rows) == 1
        and not issue_rows
    )
    target = manifest_rows[0] if manifest_rows else {}
    if clean:
        verdict = "branch_route_previews_ready"
        next_action = "review routed shifted 0x2a30 branch high-arg2 preview before promotion into .tex coverage"
    elif issue_rows:
        verdict = "branch_route_previews_issues"
        next_action = "fix routed shifted 0x2a30 branch high-arg2 preview issues"
    else:
        verdict = "branch_route_previews_incomplete"
        next_action = "complete routed shifted 0x2a30 branch high-arg2 previews"
    return {
        "scope": "total",
        "route_rows": str(len(route_rows)),
        "routed_rows": str(len(routed_rows)),
        "manifest_rows": str(len(manifest_rows)),
        "native_previews": str(len(native_previews)),
        "fullhd_previews": str(len(fullhd_good)),
        "decoded_rows": str(len(decoded_rows)),
        "validation_verdict": validation_summary.get("validation_verdict", ""),
        "target_archive_tag": target.get("archive_tag", ""),
        "target_pcx_name": target.get("pcx_name", ""),
        "target_decoder_extra": target.get("decoder_extra", ""),
        "target_high_arg2_skips": target.get("high_arg2_skips", ""),
        "fullhd_width": str(TARGET_SIZE[0]),
        "fullhd_height": str(TARGET_SIZE[1]),
        "issue_rows": str(len(issue_rows)),
        "review_verdict": verdict,
        "next_action": next_action,
    }


def render_table(rows: list[dict[str, str]], columns: list[str]) -> str:
    head = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    body = []
    for row in rows:
        cells = "".join(f"<td>{html.escape(row.get(column, ''))}</td>" for column in columns)
        body.append(f"<tr>{cells}</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def render_cards(rows: list[dict[str, str]], output_dir: Path) -> str:
    cards = []
    for row in rows:
        image = html.escape(relative_href(row.get("fullhd_preview_path", ""), output_dir))
        native = html.escape(relative_href(row.get("native_preview_path", ""), output_dir))
        cards.append(
            f"""<article>
  <a href="{image}"><img src="{image}" alt=""></a>
  <div class="meta"><strong>{html.escape(row.get('archive_tag', ''))} {html.escape(row.get('pcx_name', ''))}</strong></div>
  <div class="meta">{html.escape(row.get('renderer_mode', ''))} extra {html.escape(row.get('decoder_extra', ''))}</div>
  <div class="meta">high-arg2 skips {html.escape(row.get('high_arg2_skips', ''))}</div>
  <div class="meta"><a href="{native}">native</a></div>
</article>"""
        )
    return "\n".join(cards)


def build_html(summary: dict[str, str], manifest_rows: list[dict[str, str]], output_dir: Path, title: str) -> str:
    payload = {"summary": summary, "manifest": manifest_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("manifest.csv", output_dir / "manifest.csv"),
        )
    )
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root {{ color-scheme: dark; --bg: #101214; --panel: #171b1f; --line: #2b3339; --text: #edf2f4; --muted: #aab5ba; --accent: #7cc7ff; }}
body {{ margin: 0; background: var(--bg); color: var(--text); font: 14px/1.45 system-ui, -apple-system, Segoe UI, sans-serif; }}
main {{ max-width: 1500px; margin: 0 auto; padding: 28px; }}
h1 {{ font-size: 24px; margin: 0 0 8px; }}
h2 {{ font-size: 18px; margin: 26px 0 10px; }}
.muted, .meta {{ color: var(--muted); }}
a {{ color: var(--accent); text-decoration: none; margin-right: 10px; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }}
article {{ border: 1px solid var(--line); border-radius: 8px; background: var(--panel); padding: 10px; }}
img {{ width: 100%; aspect-ratio: 16 / 9; object-fit: contain; image-rendering: pixelated; background: #050607; border: 1px solid var(--line); }}
table {{ width: 100%; border-collapse: collapse; background: var(--panel); border: 1px solid var(--line); margin-top: 10px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; font-size: 12px; }}
th {{ color: var(--muted); background: #20262b; }}
td {{ max-width: 420px; overflow-wrap: anywhere; }}
</style>
</head>
<body>
<main>
<h1>{html.escape(title)}</h1>
<p class="muted">Materializes routed shifted 0x2a30 branch high-arg2 renderer previews as native and Full HD PNGs.</p>
<p>{links}</p>
<h2>Previews</h2>
<section class="grid">{render_cards(manifest_rows, output_dir)}</section>
<h2>Summary</h2>
{render_table([summary], SUMMARY_FIELDNAMES)}
<h2>Manifest</h2>
{render_table(manifest_rows, MANIFEST_FIELDNAMES)}
</main>
<script>const TEX_LARGE_SHIFTED_2A30_BRANCH_ROUTE_PREVIEWS = {data_json};</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    routes_path: Path,
    trace_path: Path,
    family_path: Path,
    validation_summary_path: Path,
    catalog: Path,
    palette_path: Path,
    title: str,
    low: int,
    high: int,
) -> tuple[dict[str, str], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    route_rows = read_csv(routes_path)
    validation_summary = read_summary(validation_summary_path)
    if not any(row.get("route_status") == ROUTED_STATUS for row in route_rows):
        manifest_rows: list[dict[str, str]] = []
        summary = build_summary(route_rows, manifest_rows, validation_summary)
        write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
        write_csv(output_dir / "manifest.csv", MANIFEST_FIELDNAMES, manifest_rows)
        (output_dir / "index.html").write_text(build_html(summary, manifest_rows, output_dir, title), encoding="utf-8")
        return summary, manifest_rows
    if OPTIONAL_IMPORT_ERROR is not None:
        raise OPTIONAL_IMPORT_ERROR
    manifest_rows = build_manifest(
        output_dir,
        route_rows,
        read_csv(trace_path),
        read_csv(family_path),
        read_summary(validation_summary_path),
        catalog,
        palette_path,
        low,
        high,
    )
    summary = build_summary(route_rows, manifest_rows, validation_summary)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "manifest.csv", MANIFEST_FIELDNAMES, manifest_rows)
    (output_dir / "index.html").write_text(build_html(summary, manifest_rows, output_dir, title), encoding="utf-8")
    return summary, manifest_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Materialize routed shifted 0x2a30 branch high-arg2 previews.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--routes", type=Path, default=DEFAULT_ROUTES)
    parser.add_argument("--renderer-trace", type=Path, default=DEFAULT_RENDERER_TRACE)
    parser.add_argument("--family", type=Path, default=DEFAULT_FAMILY)
    parser.add_argument("--validation-summary", type=Path, default=DEFAULT_VALIDATION_SUMMARY)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("-p", "--palette", type=Path, default=DEFAULT_PALETTE)
    parser.add_argument("--low", type=lambda value: int(value, 0), default=0x30)
    parser.add_argument("--high", type=lambda value: int(value, 0), default=0xBF)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Large Shifted 2a30 Branch Route Previews",
    )
    args = parser.parse_args()

    summary, _manifest = write_report(
        args.output,
        args.routes,
        args.renderer_trace,
        args.family,
        args.validation_summary,
        args.catalog,
        args.palette,
        args.title,
        args.low,
        args.high,
    )
    print(f"Routed rows: {summary['routed_rows']}")
    print(f"Native previews: {summary['native_previews']}")
    print(f"Full HD previews: {summary['fullhd_previews']}")
    print(f"High-arg2 skips: {summary['target_high_arg2_skips']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
