#!/usr/bin/env python3
"""Validate previews for shared 0x2700302b OP4 segment-specific residual rules."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

from export_shp import read_palette
from export_te_span_previews import render_indexed
import lolg_tex_large_shared_2700302b_op4_emitarg1_extended_split_residual_probe as residual_probe
import lolg_tex_large_shared_2700302b_op4_emitarg1_extended_split_residual_segment_rule_replay_probe as rule_replay
from score_te_raw_layouts import row_score


TARGET_SIZE = (1920, 1080)
SHEET_SIZE = (1700, 960)
DEFAULT_OUTPUT = Path(
    "output/tex_large_shared_2700302b_op4_emitarg1_extended_split_residual_segment_rule_previews_validation"
)
DEFAULT_ACTION_SUMMARY = residual_probe.DEFAULT_ACTION_SUMMARY
DEFAULT_REPLAY_SUMMARY = rule_replay.DEFAULT_OUTPUT / "summary.csv"
DEFAULT_REPLAY_SEGMENTS = rule_replay.DEFAULT_OUTPUT / "segments.csv"
DEFAULT_REJECTED_SEGMENTS = Path("output/tex_large_rejected_decoder_profile/segments.csv")
DEFAULT_PALETTE = Path("extracted/LOCAL/7231c8f9.pal")

SUMMARY_FIELDNAMES = [
    "scope",
    "segment_rows",
    "selected_segment_rows",
    "native_previews",
    "fullhd_previews",
    "review_sheet_rows",
    "fullhd_reconstructed_rows",
    "nonblank_fullhd_rows",
    "improved_segments",
    "degraded_segments",
    "replay_avg_score",
    "replay_delta_vs_base_avg",
    "replay_delta_vs_global_best_avg",
    "ready_rows",
    "decision_template_rows",
    "missing_native_rows",
    "missing_fullhd_rows",
    "missing_sheet_rows",
    "source_issue_rows",
    "issue_rows",
    "validation_verdict",
    "next_action",
]

MANIFEST_FIELDNAMES = [
    "promotion_id",
    "segment_id",
    "archive",
    "archive_tag",
    "texture_path",
    "pcx_name",
    "segment_index",
    "body_offset_hex",
    "segment_size",
    "width",
    "height",
    "selected_condition_id",
    "selected_action",
    "base_score",
    "replay_score",
    "delta_vs_base",
    "guard_events",
    "action_emit_events",
    "native_preview_path",
    "native_preview_exists",
    "native_width",
    "native_height",
    "fullhd_preview_path",
    "fullhd_preview_exists",
    "fullhd_width",
    "fullhd_height",
    "fullhd_reconstructed_match",
    "fullhd_nonblank",
    "fullhd_alpha_bbox",
    "review_sheet_path",
    "review_sheet_exists",
    "promotion_status",
    "promotion_reason",
    "issues",
]

DECISION_FIELDNAMES = [
    "promotion_id",
    "archive",
    "name",
    "segment_index",
    "body_offset_hex",
    "selected_condition_id",
    "selected_action",
    "delta_vs_base",
    "review_status",
    "review_note",
    "native_preview_path",
    "fullhd_preview_path",
    "review_sheet_path",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_summary(path: Path) -> dict[str, str]:
    rows = read_csv(path)
    return rows[0] if rows else {}


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_tsv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def int_value(row: dict[str, str], field: str) -> int:
    raw = row.get(field, "")
    try:
        return int(raw, 0) if raw else 0
    except ValueError:
        return 0


def float_value(row: dict[str, str], field: str) -> float:
    raw = row.get(field, "")
    try:
        return float(raw) if raw else 0.0
    except ValueError:
        return 0.0


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    if not path_text:
        return ""
    path = Path(path_text)
    try:
        relative = path.relative_to(base_dir)
    except ValueError:
        relative = Path(os.path.relpath(path, base_dir))
    return relative.as_posix()


def make_fullhd(image: Image.Image) -> Image.Image:
    source = image.convert("RGBA")
    scale = min(TARGET_SIZE[0] / source.width, TARGET_SIZE[1] / source.height)
    scaled_size = (max(1, round(source.width * scale)), max(1, round(source.height * scale)))
    scaled = source.resize(scaled_size, Image.Resampling.NEAREST)
    canvas = Image.new("RGBA", TARGET_SIZE, (0, 0, 0, 0))
    origin = ((TARGET_SIZE[0] - scaled.width) // 2, (TARGET_SIZE[1] - scaled.height) // 2)
    canvas.paste(scaled, origin)
    return canvas


def images_equal(left: Image.Image, right: Image.Image) -> bool:
    if left.size != right.size:
        return False
    return ImageChops.difference(left.convert("RGBA"), right.convert("RGBA")).getbbox() is None


def alpha_bbox_text(image: Image.Image) -> str:
    bbox = image.convert("RGBA").getchannel("A").getbbox()
    if not bbox:
        return ""
    return ",".join(str(value) for value in bbox)


def promotion_id(row: dict[str, str]) -> str:
    return "__".join(
        [
            row.get("archive_tag", ""),
            row.get("pcx_name", "").lower(),
            row.get("selected_condition_id", ""),
            row.get("selected_action", ""),
        ]
    )


def segment_metadata(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row.get("segment_id", ""): row for row in rows}


def replay_rules(rows: list[dict[str, str]]) -> dict[str, tuple[tuple[object, ...], str, str]]:
    rules: dict[str, tuple[tuple[object, ...], str, str]] = {}
    for row in rows:
        condition_id = row.get("selected_condition_id", "")
        action = row.get("selected_action", "")
        key = rule_replay.parse_condition_id(condition_id)
        if key and action:
            rules[row.get("segment_id", "")] = (key, action, condition_id)
    return rules


def image_on_panel(source: Image.Image, size: tuple[int, int]) -> Image.Image:
    image = source.convert("RGBA")
    background = Image.new("RGBA", image.size, (8, 10, 12, 255))
    background.alpha_composite(image)
    scale = min(size[0] / background.width, size[1] / background.height)
    scaled = background.resize(
        (max(1, round(background.width * scale)), max(1, round(background.height * scale))),
        Image.Resampling.NEAREST,
    )
    panel = Image.new("RGBA", size, (5, 7, 9, 255))
    panel.alpha_composite(scaled, ((size[0] - scaled.width) // 2, (size[1] - scaled.height) // 2))
    return panel


def draw_text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, fill: tuple[int, int, int]) -> None:
    draw.text(xy, text, fill=fill, font=ImageFont.load_default())


def write_review_sheet(row: dict[str, str], target: Path, issues: list[str]) -> None:
    native_path = Path(row.get("native_preview_path", ""))
    fullhd_path = Path(row.get("fullhd_preview_path", ""))
    target.parent.mkdir(parents=True, exist_ok=True)
    sheet = Image.new("RGBA", SHEET_SIZE, (16, 19, 22, 255))
    draw = ImageDraw.Draw(sheet)
    draw.rectangle((0, 0, SHEET_SIZE[0] - 1, SHEET_SIZE[1] - 1), outline=(67, 76, 85), width=1)
    draw_text(draw, (24, 20), f"{row.get('archive_tag', '')} / {row.get('pcx_name', '')}", (238, 243, 246))
    draw_text(
        draw,
        (24, 42),
        f"{row.get('selected_condition_id', '')} -> {row.get('selected_action', '')}",
        (174, 186, 196),
    )
    draw_text(draw, (24, 64), f"delta: {row.get('delta_vs_base', '')}", (174, 186, 196))
    draw_text(draw, (24, 86), f"promotion: {row.get('promotion_status', '')}", (174, 186, 196))

    panels = (
        ("native", native_path, (24, 140), (620, 700)),
        ("fullhd", fullhd_path, (704, 140), (940, 530)),
    )
    for label, path, origin, size in panels:
        x, y = origin
        draw_text(draw, (x, y - 24), label, (238, 243, 246))
        draw.rectangle((x, y, x + size[0] - 1, y + size[1] - 1), outline=(67, 76, 85), width=1)
        if not path.exists():
            draw_text(draw, (x + 18, y + 18), f"missing: {path}", (240, 176, 106))
            issues.append(f"missing_sheet_input:{label}")
            continue
        try:
            with Image.open(path) as image:
                image.load()
                panel = image_on_panel(image, size)
        except Exception as exc:
            draw_text(draw, (x + 18, y + 18), f"open failed: {exc}", (240, 176, 106))
            issues.append(f"sheet_input_open_failed:{label}")
            continue
        sheet.alpha_composite(panel, origin)

    note_y = 706
    draw_text(draw, (704, note_y), f"base score: {row.get('base_score', '')}", (174, 186, 196))
    draw_text(draw, (704, note_y + 22), f"replay score: {row.get('replay_score', '')}", (174, 186, 196))
    draw_text(draw, (704, note_y + 44), f"fullhd reconstructed: {row.get('fullhd_reconstructed_match', '')}", (174, 186, 196))
    draw_text(draw, (704, note_y + 66), f"alpha bbox: {row.get('fullhd_alpha_bbox', '')}", (174, 186, 196))
    draw_text(draw, (704, note_y + 88), f"guard/action events: {row.get('guard_events', '')}/{row.get('action_emit_events', '')}", (174, 186, 196))
    draw_text(draw, (704, note_y + 122), f"native: {row.get('native_preview_path', '')}", (137, 151, 162))
    draw_text(draw, (704, note_y + 144), f"fullhd: {row.get('fullhd_preview_path', '')}", (137, 151, 162))
    sheet.convert("RGB").save(target, "PNG", optimize=True)


def build_manifest(
    output_dir: Path,
    replay_rows: list[dict[str, str]],
    rejected_rows: list[dict[str, str]],
    action_summary: dict[str, str],
    palette_path: Path,
) -> list[dict[str, str]]:
    native_dir = output_dir / "native"
    fullhd_dir = output_dir / "fullhd"
    sheet_dir = output_dir / "sheets"
    native_dir.mkdir(parents=True, exist_ok=True)
    fullhd_dir.mkdir(parents=True, exist_ok=True)
    sheet_dir.mkdir(parents=True, exist_ok=True)

    metadata = segment_metadata(rejected_rows)
    rules = replay_rules(replay_rows)
    palette = read_palette(palette_path)
    base_action_id = rule_replay.read_summary(rule_replay.DEFAULT_SEGMENT_SPLIT_SUMMARY).get("base_action_id")
    if not base_action_id:
        base_action_id = f"extended_split_greedy_{len(residual_probe.action_probe.EXTENDED_SPLIT_RULES)}"
    offset = residual_probe.action_probe.int_value(action_summary, "offset", 4)

    replay_by_segment = {row.get("segment_id", ""): row for row in replay_rows}
    rows: list[dict[str, str]] = []
    for segment_id, payload, width, height, load_issues in residual_probe.load_segments(offset):
        source = metadata.get(segment_id, {})
        replay = replay_by_segment.get(segment_id, {})
        rule = rules.get(segment_id)
        issues = list(load_issues)
        if not source:
            issues.append("missing_segment_metadata")
        if not replay:
            issues.append("missing_replay_row")
        if not rule:
            issues.append("missing_selected_rule")

        native_path = native_dir / f"{segment_id}.png"
        fullhd_path = fullhd_dir / f"{segment_id}_fullhd.png"
        sheet_path = sheet_dir / f"{segment_id}.png"
        native_width = native_height = fullhd_width = fullhd_height = ""
        replay_score = base_score = 0.0
        stats = {"guard_events": 0, "action_emit_events": 0}

        if not issues and rule:
            base_pixels, _base_stats = residual_probe.decode_residual(payload, width, height, base_action_id)
            replay_pixels, stats = residual_probe.decode_residual(payload, width, height, base_action_id, rule)
            base_score = row_score(base_pixels, width, height)
            replay_score = row_score(replay_pixels, width, height)
            native = render_indexed(replay_pixels, width, height, palette)
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

        fullhd_reconstructed_match = "no"
        fullhd_nonblank = "no"
        fullhd_alpha_bbox = ""
        if native_exists and fullhd_exists:
            try:
                with Image.open(native_path) as native_image, Image.open(fullhd_path) as fullhd_image:
                    native_rgba = native_image.convert("RGBA")
                    fullhd_rgba = fullhd_image.convert("RGBA")
                    fullhd_alpha_bbox = alpha_bbox_text(fullhd_rgba)
                    fullhd_nonblank = "yes" if fullhd_alpha_bbox else "no"
                    fullhd_reconstructed_match = "yes" if images_equal(make_fullhd(native_rgba), fullhd_rgba) else "no"
            except Exception as exc:
                issues.append(f"preview_open_failed:{type(exc).__name__}")
        if fullhd_exists and (fullhd_width, fullhd_height) != (str(TARGET_SIZE[0]), str(TARGET_SIZE[1])):
            issues.append("fullhd_size_mismatch")
        if fullhd_reconstructed_match != "yes":
            issues.append("fullhd_reconstruction_mismatch")
        if fullhd_nonblank != "yes":
            issues.append("blank_fullhd_preview")
        if float_value(replay, "delta_vs_base") >= 0:
            issues.append("replay_not_improved")

        row = {
            "promotion_id": "",
            "segment_id": segment_id,
            "archive": source.get("archive", ""),
            "archive_tag": source.get("archive_tag", ""),
            "texture_path": source.get("texture_path", ""),
            "pcx_name": source.get("pcx_name", ""),
            "segment_index": source.get("segment_index", ""),
            "body_offset_hex": source.get("body_offset_hex", ""),
            "segment_size": source.get("segment_size", ""),
            "width": str(width),
            "height": str(height),
            "selected_condition_id": replay.get("selected_condition_id", ""),
            "selected_action": replay.get("selected_action", ""),
            "base_score": f"{base_score:.4f}" if base_score else replay.get("base_score", ""),
            "replay_score": f"{replay_score:.4f}" if replay_score else replay.get("replay_score", ""),
            "delta_vs_base": f"{(replay_score - base_score):.4f}" if base_score else replay.get("delta_vs_base", ""),
            "guard_events": str(stats.get("guard_events", "")) if stats else replay.get("guard_events", ""),
            "action_emit_events": str(stats.get("action_emit_events", "")) if stats else replay.get("action_emit_events", ""),
            "native_preview_path": native_path.as_posix(),
            "native_preview_exists": "yes" if native_exists else "no",
            "native_width": native_width,
            "native_height": native_height,
            "fullhd_preview_path": fullhd_path.as_posix(),
            "fullhd_preview_exists": "yes" if fullhd_exists else "no",
            "fullhd_width": fullhd_width,
            "fullhd_height": fullhd_height,
            "fullhd_reconstructed_match": fullhd_reconstructed_match,
            "fullhd_nonblank": fullhd_nonblank,
            "fullhd_alpha_bbox": fullhd_alpha_bbox,
            "review_sheet_path": "",
            "review_sheet_exists": "no",
            "promotion_status": "",
            "promotion_reason": "",
            "issues": "",
        }
        row["promotion_id"] = promotion_id(row)
        row["promotion_status"] = "ready" if not issues else "blocked"
        row["promotion_reason"] = "segment_rule_preview_validated" if not issues else "validation_blocked"
        write_review_sheet(row, sheet_path, issues)
        row["review_sheet_path"] = sheet_path.as_posix()
        row["review_sheet_exists"] = "yes" if sheet_path.exists() else "no"
        if row["review_sheet_exists"] != "yes":
            issues.append("missing_review_sheet")
        row["issues"] = "|".join(dict.fromkeys(issues))
        if row["issues"]:
            row["promotion_status"] = "blocked"
            row["promotion_reason"] = "validation_blocked"
        rows.append(row)

    return sorted(rows, key=lambda row: (row["archive_tag"], row["pcx_name"].lower()))


def build_decisions(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        {
            "promotion_id": row.get("promotion_id", ""),
            "archive": row.get("archive_tag", ""),
            "name": row.get("pcx_name", ""),
            "segment_index": row.get("segment_index", ""),
            "body_offset_hex": row.get("body_offset_hex", ""),
            "selected_condition_id": row.get("selected_condition_id", ""),
            "selected_action": row.get("selected_action", ""),
            "delta_vs_base": row.get("delta_vs_base", ""),
            "review_status": row.get("promotion_status", ""),
            "review_note": row.get("promotion_reason", ""),
            "native_preview_path": row.get("native_preview_path", ""),
            "fullhd_preview_path": row.get("fullhd_preview_path", ""),
            "review_sheet_path": row.get("review_sheet_path", ""),
        }
        for row in rows
    ]


def build_summary(
    replay_summary: dict[str, str],
    manifest_rows: list[dict[str, str]],
    decision_rows: list[dict[str, str]],
) -> dict[str, str]:
    issue_rows = [row for row in manifest_rows if row.get("issues")]
    ready_rows = [row for row in manifest_rows if row.get("promotion_status") == "ready" and not row.get("issues")]
    clean = (
        len(manifest_rows) == int_value(replay_summary, "segment_rows")
        and len(ready_rows) == len(manifest_rows)
        and len(decision_rows) == len(manifest_rows)
        and not issue_rows
        and int_value(replay_summary, "degraded_segments") == 0
    )
    if clean:
        verdict = "shared_2700302b_op4_segment_rule_previews_validation_ready"
        next_action = "promote shared 0x2700302b segment-specific op4 rules into .tex coverage"
    elif issue_rows:
        verdict = "shared_2700302b_op4_segment_rule_previews_validation_blocked"
        next_action = "fix shared 0x2700302b segment-specific op4 preview validation issues"
    else:
        verdict = "shared_2700302b_op4_segment_rule_previews_validation_incomplete"
        next_action = "complete shared 0x2700302b segment-specific op4 preview validation"
    return {
        "scope": "total",
        "segment_rows": str(len(manifest_rows)),
        "selected_segment_rows": replay_summary.get("selected_segment_rows", ""),
        "native_previews": str(sum(1 for row in manifest_rows if row.get("native_preview_exists") == "yes")),
        "fullhd_previews": str(sum(1 for row in manifest_rows if row.get("fullhd_preview_exists") == "yes")),
        "review_sheet_rows": str(sum(1 for row in manifest_rows if row.get("review_sheet_exists") == "yes")),
        "fullhd_reconstructed_rows": str(
            sum(1 for row in manifest_rows if row.get("fullhd_reconstructed_match") == "yes")
        ),
        "nonblank_fullhd_rows": str(sum(1 for row in manifest_rows if row.get("fullhd_nonblank") == "yes")),
        "improved_segments": replay_summary.get("improved_segments", ""),
        "degraded_segments": replay_summary.get("degraded_segments", ""),
        "replay_avg_score": replay_summary.get("replay_avg_score", ""),
        "replay_delta_vs_base_avg": replay_summary.get("replay_delta_vs_base_avg", ""),
        "replay_delta_vs_global_best_avg": replay_summary.get("replay_delta_vs_global_best_avg", ""),
        "ready_rows": str(len(ready_rows)),
        "decision_template_rows": str(len(decision_rows)),
        "missing_native_rows": str(sum(1 for row in manifest_rows if row.get("native_preview_exists") != "yes")),
        "missing_fullhd_rows": str(sum(1 for row in manifest_rows if row.get("fullhd_preview_exists") != "yes")),
        "missing_sheet_rows": str(sum(1 for row in manifest_rows if row.get("review_sheet_exists") != "yes")),
        "source_issue_rows": replay_summary.get("issue_rows", "0"),
        "issue_rows": str(len(issue_rows) + int_value(replay_summary, "issue_rows")),
        "validation_verdict": verdict,
        "next_action": next_action,
    }


def render_table(rows: list[dict[str, str]], columns: list[str]) -> str:
    head = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    body = []
    for row in rows:
        cells = "".join(f"<td>{html.escape(row.get(column, ''))}</td>" for column in columns)
        body.append(f"<tr>{cells}</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def render_card(row: dict[str, str], output_dir: Path) -> str:
    sheet = html.escape(relative_href(row.get("review_sheet_path", ""), output_dir))
    native = html.escape(relative_href(row.get("native_preview_path", ""), output_dir))
    fullhd = html.escape(relative_href(row.get("fullhd_preview_path", ""), output_dir))
    title = f"{row.get('archive_tag', '')} / {row.get('pcx_name', '')}"
    return f"""
<article>
  <a class="preview" href="{sheet}"><img src="{sheet}" loading="lazy" decoding="async" alt=""></a>
  <div class="body">
    <div class="title">{html.escape(title)}</div>
    <div>{html.escape(row.get('selected_condition_id', ''))} -> {html.escape(row.get('selected_action', ''))}</div>
    <div class="muted">delta {html.escape(row.get('delta_vs_base', ''))} / status {html.escape(row.get('promotion_status', ''))}</div>
    <div><a href="{native}">native</a><a href="{fullhd}">fullhd</a></div>
  </div>
</article>"""


def build_html(
    summary: dict[str, str],
    manifest_rows: list[dict[str, str]],
    decision_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "manifest": manifest_rows, "decisions": decision_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    cards = "\n".join(render_card(row, output_dir) for row in manifest_rows)
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("manifest.csv", output_dir / "manifest.csv"),
            ("decisions_template.tsv", output_dir / "decisions_template.tsv"),
        )
    )
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root {{ color-scheme: dark; --bg: #101316; --panel: #171d22; --line: #2f3942; --text: #edf3f6; --muted: #9caab3; --accent: #74d3ae; --ok: #78d98f; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; min-height: 100vh; background: var(--bg); color: var(--text); font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
.wrap {{ width: min(1700px, calc(100vw - 28px)); margin: 0 auto; }}
header {{ border-bottom: 1px solid var(--line); background: #12171b; padding: 18px 0 14px; }}
h1 {{ margin: 0; font-size: 21px; font-weight: 700; letter-spacing: 0; }}
main {{ padding: 16px 0 28px; display: grid; gap: 16px; }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; }}
.stat, .panel, article {{ border: 1px solid var(--line); border-radius: 8px; background: var(--panel); }}
.stat {{ padding: 10px; }}
.label, .muted {{ color: var(--muted); }}
.value {{ font-size: 24px; font-weight: 750; line-height: 1.05; margin-top: 4px; }}
.ok {{ color: var(--ok); }}
.panel {{ padding: 12px; overflow-x: auto; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(540px, 1fr)); gap: 12px; }}
article {{ overflow: hidden; background: #11171b; }}
.preview {{ display: block; aspect-ratio: 16 / 9; background: #050607; }}
.preview img {{ width: 100%; height: 100%; object-fit: contain; display: block; }}
.body {{ padding: 10px; display: grid; gap: 5px; }}
.title {{ font-weight: 700; }}
h2 {{ margin: 0 0 10px; font-size: 16px; }}
table {{ width: 100%; min-width: 1280px; border-collapse: collapse; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
td {{ overflow-wrap: anywhere; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 10px; }}
</style>
</head>
<body>
<header><div class="wrap"><h1>{html.escape(title)}</h1></div></header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Ready</div><div class="value ok">{html.escape(summary['ready_rows'])}</div></div>
    <div class="stat"><div class="label">Full HD</div><div class="value ok">{html.escape(summary['fullhd_previews'])}</div></div>
    <div class="stat"><div class="label">Sheets</div><div class="value ok">{html.escape(summary['review_sheet_rows'])}</div></div>
    <div class="stat"><div class="label">Issues</div><div class="value ok">{html.escape(summary['issue_rows'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div><div class="muted">{html.escape(summary['validation_verdict'])}: {html.escape(summary['next_action'])}</div></section>
  <section class="grid">{cards}</section>
  <section class="panel"><h2>Summary</h2>{render_table([summary], SUMMARY_FIELDNAMES)}</section>
  <section class="panel"><h2>Manifest</h2>{render_table(manifest_rows, MANIFEST_FIELDNAMES)}</section>
  <section class="panel"><h2>Decision Template</h2>{render_table(decision_rows, DECISION_FIELDNAMES)}</section>
</main>
<script>const TEX_LARGE_SHARED_2700302B_SEGMENT_RULE_PREVIEWS_VALIDATION = {data_json};</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    args.output.mkdir(parents=True, exist_ok=True)
    replay_summary = read_summary(args.replay_summary)
    manifest_rows = build_manifest(
        args.output,
        read_csv(args.replay_segments),
        read_csv(args.rejected_segments),
        residual_probe.action_probe.read_summary(args.action_summary),
        args.palette,
    )
    decision_rows = build_decisions(manifest_rows)
    summary = build_summary(replay_summary, manifest_rows, decision_rows)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "manifest.csv", MANIFEST_FIELDNAMES, manifest_rows)
    write_tsv(args.output / "decisions_template.tsv", DECISION_FIELDNAMES, decision_rows)
    (args.output / "index.html").write_text(
        build_html(summary, manifest_rows, decision_rows, args.output, args.title),
        encoding="utf-8",
    )
    return summary, manifest_rows, decision_rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate shared 0x2700302b OP4 segment-specific rule previews."
    )
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--action-summary", type=Path, default=DEFAULT_ACTION_SUMMARY)
    parser.add_argument("--replay-summary", type=Path, default=DEFAULT_REPLAY_SUMMARY)
    parser.add_argument("--replay-segments", type=Path, default=DEFAULT_REPLAY_SEGMENTS)
    parser.add_argument("--rejected-segments", type=Path, default=DEFAULT_REJECTED_SEGMENTS)
    parser.add_argument("-p", "--palette", type=Path, default=DEFAULT_PALETTE)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Shared 0x2700302b OP4 Segment Rule Previews Validation",
    )
    args = parser.parse_args()
    summary, _manifest_rows, _decision_rows = write_report(args)
    print(f"Segments: {summary['segment_rows']}")
    print(f"Ready rows: {summary['ready_rows']}")
    print(f"Native previews: {summary['native_previews']}")
    print(f"Full HD previews: {summary['fullhd_previews']}")
    print(f"Review sheets: {summary['review_sheet_rows']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"Validation verdict: {summary['validation_verdict']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
