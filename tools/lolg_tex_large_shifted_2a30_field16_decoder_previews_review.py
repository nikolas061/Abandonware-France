#!/usr/bin/env python3
"""Review routed shifted 0x2a30 field16 decoder previews before .tex promotion."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont


TARGET_SIZE = (1920, 1080)
SHEET_SIZE = (1600, 900)
DEFAULT_OUTPUT = Path("output/tex_large_shifted_2a30_field16_decoder_previews_review")
DEFAULT_PREVIEWS_MANIFEST = Path("output/tex_large_shifted_2a30_field16_decoder_previews/manifest.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "manifest_rows",
    "review_rows",
    "review_ready_rows",
    "decision_template_rows",
    "sheet_rows",
    "source_native_match_rows",
    "fullhd_reconstructed_rows",
    "nonblank_fullhd_rows",
    "missing_source_rows",
    "missing_native_rows",
    "missing_fullhd_rows",
    "missing_sheet_rows",
    "issue_rows",
    "review_verdict",
    "next_action",
]

REVIEW_FIELDNAMES = [
    "promotion_id",
    "archive",
    "archive_tag",
    "texture_path",
    "pcx_name",
    "segment_index",
    "body_offset_hex",
    "segment_size",
    "decoder_rule",
    "decoder_extra",
    "choice_mode",
    "choice_score",
    "source_preview_path",
    "source_preview_exists",
    "native_preview_path",
    "native_preview_exists",
    "native_width",
    "native_height",
    "fullhd_preview_path",
    "fullhd_preview_exists",
    "fullhd_width",
    "fullhd_height",
    "source_native_match",
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
    "decoder_rule",
    "decoder_extra",
    "review_status",
    "review_note",
    "source_preview_path",
    "native_preview_path",
    "fullhd_preview_path",
    "review_sheet_path",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_tsv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    if not path_text:
        return ""
    path = Path(path_text)
    try:
        relative = path.relative_to(base_dir)
    except ValueError:
        relative = Path(os.path.relpath(path, base_dir))
    return relative.as_posix()


def promotion_id(row: dict[str, str]) -> str:
    return "__".join(
        [
            row.get("archive_tag", ""),
            row.get("pcx_name", "").lower(),
            row.get("decoder_rule", ""),
            row.get("decoder_extra", ""),
        ]
    )


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
    alpha = image.convert("RGBA").getchannel("A")
    bbox = alpha.getbbox()
    if not bbox:
        return ""
    return ",".join(str(value) for value in bbox)


def image_on_panel(source: Image.Image, size: tuple[int, int]) -> Image.Image:
    image = source.convert("RGBA")
    if image.getchannel("A").getextrema()[0] < 255:
        background = Image.new("RGBA", image.size, (10, 12, 14, 255))
        background.alpha_composite(image)
        image = background
    scale = min(size[0] / image.width, size[1] / image.height)
    scaled = image.resize(
        (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
        Image.Resampling.NEAREST,
    )
    panel = Image.new("RGBA", size, (8, 10, 12, 255))
    panel.alpha_composite(scaled, ((size[0] - scaled.width) // 2, (size[1] - scaled.height) // 2))
    return panel


def draw_text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, fill: tuple[int, int, int]) -> None:
    draw.text(xy, text, fill=fill, font=ImageFont.load_default())


def write_review_sheet(row: dict[str, str], target: Path, issues: list[str]) -> None:
    source_path = Path(row.get("source_preview_path", ""))
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
        f"{row.get('decoder_rule', '')} extra {row.get('decoder_extra', '')}",
        (174, 186, 196),
    )
    draw_text(draw, (24, 64), f"promotion: {row.get('promotion_status', '')}", (174, 186, 196))

    panel_y = 116
    native_panel = (492, 520)
    fullhd_panel = (540, 304)
    panels = (
        ("source", source_path, (24, panel_y), native_panel),
        ("native", native_path, (554, panel_y), native_panel),
        ("fullhd", fullhd_path, (1084, panel_y), fullhd_panel),
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

    note_y = 680
    draw_text(draw, (24, note_y), "Checks:", (238, 243, 246))
    draw_text(draw, (24, note_y + 24), f"source/native match: {row.get('source_native_match', '')}", (174, 186, 196))
    draw_text(
        draw,
        (24, note_y + 46),
        f"fullhd reconstructed: {row.get('fullhd_reconstructed_match', '')}",
        (174, 186, 196),
    )
    draw_text(draw, (24, note_y + 68), f"alpha bbox: {row.get('fullhd_alpha_bbox', '')}", (174, 186, 196))
    draw_text(draw, (24, note_y + 100), f"source: {row.get('source_preview_path', '')}", (137, 151, 162))
    draw_text(draw, (24, note_y + 122), f"fullhd: {row.get('fullhd_preview_path', '')}", (137, 151, 162))
    sheet.convert("RGB").save(target, "PNG", optimize=True)


def review_manifest_row(output_dir: Path, source: dict[str, str]) -> dict[str, str]:
    issues: list[str] = []
    source_path = Path(source.get("source_preview_path", ""))
    native_path = Path(source.get("native_preview_path", ""))
    fullhd_path = Path(source.get("fullhd_preview_path", ""))

    source_exists = source.get("source_preview_exists") == "yes" and source_path.exists()
    native_exists = source.get("native_preview_exists") == "yes" and native_path.exists()
    fullhd_exists = source.get("fullhd_preview_exists") == "yes" and fullhd_path.exists()
    if not source_exists:
        issues.append("missing_source_preview")
    if not native_exists:
        issues.append("missing_native_preview")
    if not fullhd_exists:
        issues.append("missing_fullhd_preview")
    if source.get("issues"):
        issues.append(f"source_manifest_issues:{source.get('issues')}")

    source_native_match = "no"
    fullhd_reconstructed_match = "no"
    fullhd_nonblank = "no"
    fullhd_alpha_bbox = ""
    if source_exists and native_exists:
        with Image.open(source_path) as source_image, Image.open(native_path) as native_image:
            source_native_match = "yes" if images_equal(source_image, native_image) else "no"
        if source_native_match != "yes":
            issues.append("source_native_pixel_mismatch")

    if native_exists and fullhd_exists:
        with Image.open(native_path) as native_image, Image.open(fullhd_path) as fullhd_image:
            native_rgba = native_image.convert("RGBA")
            fullhd_rgba = fullhd_image.convert("RGBA")
            fullhd_alpha_bbox = alpha_bbox_text(fullhd_rgba)
            fullhd_nonblank = "yes" if fullhd_alpha_bbox else "no"
            fullhd_reconstructed_match = "yes" if images_equal(make_fullhd(native_rgba), fullhd_rgba) else "no"
        if fullhd_reconstructed_match != "yes":
            issues.append("fullhd_reconstruction_mismatch")
        if fullhd_nonblank != "yes":
            issues.append("blank_fullhd_preview")

    if (source.get("native_width"), source.get("native_height")) != ("48", "128"):
        issues.append("native_size_mismatch")
    if (source.get("fullhd_width"), source.get("fullhd_height")) != (str(TARGET_SIZE[0]), str(TARGET_SIZE[1])):
        issues.append("fullhd_size_mismatch")

    row = {
        "promotion_id": promotion_id(source),
        "archive": source.get("archive", ""),
        "archive_tag": source.get("archive_tag", ""),
        "texture_path": source.get("texture_path", ""),
        "pcx_name": source.get("pcx_name", ""),
        "segment_index": source.get("segment_index", ""),
        "body_offset_hex": source.get("body_offset_hex", ""),
        "segment_size": source.get("segment_size", ""),
        "decoder_rule": source.get("decoder_rule", ""),
        "decoder_extra": source.get("decoder_extra", ""),
        "choice_mode": source.get("choice_mode", ""),
        "choice_score": source.get("choice_score", ""),
        "source_preview_path": source.get("source_preview_path", ""),
        "source_preview_exists": "yes" if source_exists else "no",
        "native_preview_path": source.get("native_preview_path", ""),
        "native_preview_exists": "yes" if native_exists else "no",
        "native_width": source.get("native_width", ""),
        "native_height": source.get("native_height", ""),
        "fullhd_preview_path": source.get("fullhd_preview_path", ""),
        "fullhd_preview_exists": "yes" if fullhd_exists else "no",
        "fullhd_width": source.get("fullhd_width", ""),
        "fullhd_height": source.get("fullhd_height", ""),
        "source_native_match": source_native_match,
        "fullhd_reconstructed_match": fullhd_reconstructed_match,
        "fullhd_nonblank": fullhd_nonblank,
        "fullhd_alpha_bbox": fullhd_alpha_bbox,
        "review_sheet_path": "",
        "review_sheet_exists": "no",
        "promotion_status": "",
        "promotion_reason": "",
        "issues": "",
    }
    row["promotion_status"] = "ready" if not issues else "blocked"
    row["promotion_reason"] = "preview_consistent" if not issues else "review_blocked"
    sheet_path = output_dir / "sheets" / f"{row['promotion_id']}.png"
    write_review_sheet(row, sheet_path, issues)
    row["review_sheet_path"] = sheet_path.as_posix()
    row["review_sheet_exists"] = "yes" if sheet_path.exists() else "no"
    if row["review_sheet_exists"] != "yes":
        issues.append("missing_review_sheet")
    row["issues"] = "|".join(dict.fromkeys(issues))
    if row["issues"]:
        row["promotion_status"] = "blocked"
        row["promotion_reason"] = "review_blocked"
    return row


def build_review_rows(output_dir: Path, manifest_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    rows = [review_manifest_row(output_dir, row) for row in manifest_rows]
    return sorted(rows, key=lambda row: (row["archive_tag"], row["pcx_name"].lower()))


def build_decision_rows(review_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        {
            "promotion_id": row.get("promotion_id", ""),
            "archive": row.get("archive_tag", ""),
            "name": row.get("pcx_name", ""),
            "decoder_rule": row.get("decoder_rule", ""),
            "decoder_extra": row.get("decoder_extra", ""),
            "review_status": row.get("promotion_status", ""),
            "review_note": row.get("promotion_reason", ""),
            "source_preview_path": row.get("source_preview_path", ""),
            "native_preview_path": row.get("native_preview_path", ""),
            "fullhd_preview_path": row.get("fullhd_preview_path", ""),
            "review_sheet_path": row.get("review_sheet_path", ""),
        }
        for row in review_rows
    ]


def build_summary(
    manifest_rows: list[dict[str, str]],
    review_rows: list[dict[str, str]],
    decision_rows: list[dict[str, str]],
) -> dict[str, str]:
    issue_rows = [row for row in review_rows if row.get("issues")]
    ready_rows = [row for row in review_rows if row.get("promotion_status") == "ready" and not row.get("issues")]
    clean = len(manifest_rows) == 4 and len(ready_rows) == 4 and len(decision_rows) == 4 and not issue_rows
    if clean:
        verdict = "field16_decoder_previews_review_ready"
        next_action = "promote routed shifted 0x2a30 field16 decoder previews into .tex coverage"
    elif issue_rows:
        verdict = "field16_decoder_previews_review_blocked"
        next_action = "fix routed shifted 0x2a30 field16 decoder preview review issues"
    else:
        verdict = "field16_decoder_previews_review_incomplete"
        next_action = "complete routed shifted 0x2a30 field16 decoder preview review"
    return {
        "scope": "total",
        "manifest_rows": str(len(manifest_rows)),
        "review_rows": str(len(review_rows)),
        "review_ready_rows": str(len(ready_rows)),
        "decision_template_rows": str(len(decision_rows)),
        "sheet_rows": str(sum(1 for row in review_rows if row.get("review_sheet_exists") == "yes")),
        "source_native_match_rows": str(sum(1 for row in review_rows if row.get("source_native_match") == "yes")),
        "fullhd_reconstructed_rows": str(
            sum(1 for row in review_rows if row.get("fullhd_reconstructed_match") == "yes")
        ),
        "nonblank_fullhd_rows": str(sum(1 for row in review_rows if row.get("fullhd_nonblank") == "yes")),
        "missing_source_rows": str(sum(1 for row in review_rows if row.get("source_preview_exists") != "yes")),
        "missing_native_rows": str(sum(1 for row in review_rows if row.get("native_preview_exists") != "yes")),
        "missing_fullhd_rows": str(sum(1 for row in review_rows if row.get("fullhd_preview_exists") != "yes")),
        "missing_sheet_rows": str(sum(1 for row in review_rows if row.get("review_sheet_exists") != "yes")),
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
    <div>{html.escape(row.get('decoder_rule', ''))} extra {html.escape(row.get('decoder_extra', ''))}</div>
    <div class="muted">status {html.escape(row.get('promotion_status', ''))} / {html.escape(row.get('promotion_reason', ''))}</div>
    <div><a href="{native}">native</a><a href="{fullhd}">fullhd</a></div>
  </div>
</article>"""


def build_html(
    summary: dict[str, str],
    review_rows: list[dict[str, str]],
    decision_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "review": review_rows, "decisions": decision_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    cards = "\n".join(render_card(row, output_dir) for row in review_rows)
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("review.csv", output_dir / "review.csv"),
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
:root {{ color-scheme: dark; --bg: #101316; --panel: #171d22; --line: #2f3942; --text: #edf3f6; --muted: #9caab3; --accent: #74d3ae; --ok: #78d98f; --warn: #f0b06a; }}
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
.warn {{ color: var(--warn); }}
.panel {{ padding: 12px; overflow-x: auto; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(520px, 1fr)); gap: 12px; }}
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
    <div class="stat"><div class="label">Review ready</div><div class="value ok">{html.escape(summary['review_ready_rows'])}</div></div>
    <div class="stat"><div class="label">Sheets</div><div class="value">{html.escape(summary['sheet_rows'])}</div></div>
    <div class="stat"><div class="label">Full HD checked</div><div class="value ok">{html.escape(summary['fullhd_reconstructed_rows'])}</div></div>
    <div class="stat"><div class="label">Issues</div><div class="value ok">{html.escape(summary['issue_rows'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div><div class="muted">{html.escape(summary['review_verdict'])}: {html.escape(summary['next_action'])}</div></section>
  <section class="grid">{cards}</section>
  <section class="panel"><h2>Summary</h2>{render_table([summary], SUMMARY_FIELDNAMES)}</section>
  <section class="panel"><h2>Review Rows</h2>{render_table(review_rows, REVIEW_FIELDNAMES)}</section>
  <section class="panel"><h2>Decision Template</h2>{render_table(decision_rows, DECISION_FIELDNAMES)}</section>
</main>
<script>const TEX_LARGE_SHIFTED_2A30_FIELD16_DECODER_PREVIEWS_REVIEW = {data_json};</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    previews_manifest: Path,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_rows = read_csv(previews_manifest)
    review_rows = build_review_rows(output_dir, manifest_rows)
    decision_rows = build_decision_rows(review_rows)
    summary = build_summary(manifest_rows, review_rows, decision_rows)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "review.csv", REVIEW_FIELDNAMES, review_rows)
    write_tsv(output_dir / "decisions_template.tsv", DECISION_FIELDNAMES, decision_rows)
    (output_dir / "index.html").write_text(
        build_html(summary, review_rows, decision_rows, output_dir, title),
        encoding="utf-8",
    )
    return summary, review_rows, decision_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Review routed shifted 0x2a30 field16 decoder previews.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--previews-manifest", type=Path, default=DEFAULT_PREVIEWS_MANIFEST)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Large Shifted 2a30 Field16 Decoder Previews Review",
    )
    args = parser.parse_args()

    summary, _review_rows, _decision_rows = write_report(args.output, args.previews_manifest, args.title)
    print(f"Manifest rows: {summary['manifest_rows']}")
    print(f"Review ready rows: {summary['review_ready_rows']}")
    print(f"Sheet rows: {summary['sheet_rows']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")
    if summary["issue_rows"] != "0":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
