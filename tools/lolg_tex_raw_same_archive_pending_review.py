#!/usr/bin/env python3
"""Build focused review sheets for pending raw same-archive .tex promotions."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


DEFAULT_OUTPUT = Path("output/tex_raw_same_archive_pending_review")
DEFAULT_RAW_PACK_MANIFEST = Path("output/tex_raw_same_archive_promoted_pack/manifest.csv")
TARGET_SIZE = (1920, 1080)
SHEET_SIZE = (1600, 900)

SUMMARY_FIELDNAMES = [
    "scope",
    "pending_rows",
    "pending_unique_pcx",
    "review_ready_rows",
    "decision_template_rows",
    "sheet_rows",
    "missing_source_paths",
    "missing_fullhd_paths",
    "missing_sheet_paths",
    "issue_rows",
    "next_action",
]

PENDING_FIELDNAMES = [
    "asset_id",
    "archive",
    "archive_tag",
    "pcx_name",
    "normalized_pcx_name",
    "texture_path",
    "review_status",
    "decision",
    "risk",
    "focus",
    "base_mode",
    "candidate_mode",
    "changed_ratio",
    "changed_pixels",
    "source_native_path",
    "source_native_exists",
    "source_width",
    "source_height",
    "promoted_fullhd_path",
    "promoted_fullhd_exists",
    "promoted_fullhd_width",
    "promoted_fullhd_height",
    "review_sheet_path",
    "review_sheet_exists",
    "decision_template_line",
    "issues",
]

DECISION_FIELDNAMES = [
    "archive",
    "name",
    "review_status",
    "review_note",
    "asset_id",
    "candidate_preview",
    "promoted_fullhd_path",
    "review_sheet_path",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_tsv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as handle:
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


def pending_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        row
        for row in rows
        if row.get("review_status") != "accepted" or row.get("coverage_eligible") != "yes"
    ]


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
    font = ImageFont.load_default()
    draw.text(xy, text, fill=fill, font=font)


def write_review_sheet(row: dict[str, str], target: Path, issues: list[str]) -> None:
    source_path = Path(row.get("source_native_path", ""))
    fullhd_path = Path(row.get("promoted_fullhd_path", ""))
    target.parent.mkdir(parents=True, exist_ok=True)
    sheet = Image.new("RGBA", SHEET_SIZE, (16, 19, 22, 255))
    draw = ImageDraw.Draw(sheet)
    draw.rectangle((0, 0, SHEET_SIZE[0] - 1, SHEET_SIZE[1] - 1), outline=(67, 76, 85), width=1)
    draw_text(draw, (24, 20), f"{row.get('archive_tag', '')} / {row.get('pcx_name', '')}", (238, 243, 246))
    draw_text(draw, (24, 42), f"{row.get('risk', '')} | {row.get('focus', '')}", (174, 186, 196))
    draw_text(
        draw,
        (24, 64),
        f"{row.get('base_mode', '')} -> {row.get('candidate_mode', '')} | changed {row.get('changed_ratio', '')}",
        (174, 186, 196),
    )

    panel_y = 112
    panel_size = (744, 540)
    for label, path, x in (
        ("native candidate", source_path, 24),
        ("Full HD promotion", fullhd_path, 832),
    ):
        draw_text(draw, (x, panel_y - 24), label, (238, 243, 246))
        draw.rectangle((x, panel_y, x + panel_size[0] - 1, panel_y + panel_size[1] - 1), outline=(67, 76, 85), width=1)
        if not path.exists():
            draw_text(draw, (x + 20, panel_y + 20), f"missing: {path}", (240, 176, 106))
            issues.append(f"missing_sheet_input:{label}")
            continue
        try:
            with Image.open(path) as image:
                image.load()
                panel = image_on_panel(image, panel_size)
        except Exception as exc:
            draw_text(draw, (x + 20, panel_y + 20), f"open failed: {exc}", (240, 176, 106))
            issues.append(f"sheet_input_open_failed:{label}")
            continue
        sheet.alpha_composite(panel, (x, panel_y))

    note_y = 700
    draw_text(draw, (24, note_y), "Decision line:", (238, 243, 246))
    draw_text(
        draw,
        (24, note_y + 24),
        f"{row.get('archive_tag', '')}\t{row.get('pcx_name', '')}\taccepted|rejected|deferred\t",
        (174, 186, 196),
    )
    draw_text(draw, (24, note_y + 58), f"source: {row.get('source_native_path', '')}", (137, 151, 162))
    draw_text(draw, (24, note_y + 80), f"fullhd: {row.get('promoted_fullhd_path', '')}", (137, 151, 162))
    sheet.convert("RGB").save(target, "PNG", optimize=True)


def build_rows(output_dir: Path, manifest_rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    rows: list[dict[str, str]] = []
    decisions: list[dict[str, str]] = []
    for source in pending_rows(manifest_rows):
        issues: list[str] = []
        source_path = Path(source.get("source_native_path", ""))
        fullhd_path = Path(source.get("promoted_fullhd_path", ""))
        if source.get("source_native_exists") != "yes" or not source_path.exists():
            issues.append("missing_source_path")
        if source.get("promoted_fullhd_exists") != "yes" or not fullhd_path.exists():
            issues.append("missing_fullhd_path")
        if (source.get("promoted_fullhd_width"), source.get("promoted_fullhd_height")) != (
            str(TARGET_SIZE[0]),
            str(TARGET_SIZE[1]),
        ):
            issues.append("fullhd_size_mismatch")

        sheet_path = output_dir / "sheets" / f"{source.get('asset_id', 'unnamed')}.png"
        write_review_sheet(source, sheet_path, issues)
        if not sheet_path.exists():
            issues.append("missing_review_sheet")

        decision_line = (
            f"{source.get('archive_tag', '')}\t"
            f"{source.get('pcx_name', '')}\t"
            "accepted|rejected|deferred\t"
        )
        rows.append(
            {
                "asset_id": source.get("asset_id", ""),
                "archive": source.get("archive", ""),
                "archive_tag": source.get("archive_tag", ""),
                "pcx_name": source.get("pcx_name", ""),
                "normalized_pcx_name": source.get("normalized_pcx_name", ""),
                "texture_path": source.get("texture_path", ""),
                "review_status": source.get("review_status", ""),
                "decision": source.get("decision", ""),
                "risk": source.get("risk", ""),
                "focus": source.get("focus", ""),
                "base_mode": source.get("base_mode", ""),
                "candidate_mode": source.get("candidate_mode", ""),
                "changed_ratio": source.get("changed_ratio", ""),
                "changed_pixels": source.get("changed_pixels", ""),
                "source_native_path": source.get("source_native_path", ""),
                "source_native_exists": source.get("source_native_exists", ""),
                "source_width": source.get("source_width", ""),
                "source_height": source.get("source_height", ""),
                "promoted_fullhd_path": source.get("promoted_fullhd_path", ""),
                "promoted_fullhd_exists": source.get("promoted_fullhd_exists", ""),
                "promoted_fullhd_width": source.get("promoted_fullhd_width", ""),
                "promoted_fullhd_height": source.get("promoted_fullhd_height", ""),
                "review_sheet_path": str(sheet_path),
                "review_sheet_exists": "yes" if sheet_path.exists() else "no",
                "decision_template_line": decision_line,
                "issues": ";".join(dict.fromkeys(issues)),
            }
        )
        decisions.append(
            {
                "archive": source.get("archive_tag", ""),
                "name": source.get("pcx_name", ""),
                "review_status": "",
                "review_note": "",
                "asset_id": source.get("asset_id", ""),
                "candidate_preview": source.get("source_native_path", ""),
                "promoted_fullhd_path": source.get("promoted_fullhd_path", ""),
                "review_sheet_path": str(sheet_path),
            }
        )
    return rows, decisions


def summary_row(rows: list[dict[str, str]], decisions: list[dict[str, str]]) -> dict[str, str]:
    issue_rows = sum(1 for row in rows if row.get("issues"))
    missing_source = sum(1 for row in rows if row.get("source_native_exists") != "yes")
    missing_fullhd = sum(1 for row in rows if row.get("promoted_fullhd_exists") != "yes")
    missing_sheets = sum(1 for row in rows if row.get("review_sheet_exists") != "yes")
    if rows:
        next_action = f"complete decisions_template.tsv for {len(rows)} pending raw same-archive .tex promotions"
    else:
        next_action = "no pending raw same-archive .tex promotions"
    return {
        "scope": "total",
        "pending_rows": str(len(rows)),
        "pending_unique_pcx": str(len({row.get("normalized_pcx_name", "") for row in rows if row.get("normalized_pcx_name")})),
        "review_ready_rows": str(sum(1 for row in rows if not row.get("issues"))),
        "decision_template_rows": str(len(decisions)),
        "sheet_rows": str(sum(1 for row in rows if row.get("review_sheet_exists") == "yes")),
        "missing_source_paths": str(missing_source),
        "missing_fullhd_paths": str(missing_fullhd),
        "missing_sheet_paths": str(missing_sheets),
        "issue_rows": str(issue_rows),
        "next_action": next_action,
    }


def render_table(rows: list[dict[str, str]], columns: list[str]) -> str:
    head = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    body = []
    for row in rows:
        cells = "".join(f"<td>{html.escape(row.get(column, ''))}</td>" for column in columns)
        body.append(f"<tr>{cells}</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def render_card(row: dict[str, str], base_dir: Path) -> str:
    sheet = html.escape(relative_href(row.get("review_sheet_path", ""), base_dir))
    fullhd = html.escape(relative_href(row.get("promoted_fullhd_path", ""), base_dir))
    native = html.escape(relative_href(row.get("source_native_path", ""), base_dir))
    title = f"{row.get('archive_tag', '')} / {row.get('pcx_name', '')}"
    return f"""
<article class="card">
  <a class="preview" href="{sheet}"><img src="{sheet}" loading="lazy" decoding="async" alt=""></a>
  <div class="body">
    <div class="title">{html.escape(title)}</div>
    <div class="warn">{html.escape(row.get('risk', ''))}</div>
    <div class="muted">{html.escape(row.get('base_mode', ''))} -> {html.escape(row.get('candidate_mode', ''))}</div>
    <div class="muted">changed {html.escape(row.get('changed_ratio', ''))} / {html.escape(row.get('changed_pixels', ''))} px</div>
    <code>{html.escape(row.get('decision_template_line', ''))}</code>
    <div><a href="{native}">native</a><a href="{fullhd}">fullhd</a></div>
  </div>
</article>"""


def build_html(
    summary: dict[str, str],
    rows: list[dict[str, str]],
    decisions: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "pending": rows, "decisions": decisions}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    cards = "\n".join(render_card(row, output_dir) for row in rows)
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("pending.csv", output_dir / "pending.csv"),
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
:root {{
  color-scheme: dark;
  --bg: #101316;
  --panel: #171d22;
  --line: #2f3942;
  --text: #edf3f6;
  --muted: #9caab3;
  --accent: #74d3ae;
  --warn: #f0b06a;
  --ok: #78d98f;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  min-height: 100vh;
  background: var(--bg);
  color: var(--text);
  font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}}
.wrap {{ width: min(1700px, calc(100vw - 28px)); margin: 0 auto; }}
header {{ border-bottom: 1px solid var(--line); background: #12171b; padding: 18px 0 14px; }}
h1 {{ margin: 0; font-size: 21px; font-weight: 700; letter-spacing: 0; }}
main {{ padding: 16px 0 28px; display: grid; gap: 16px; }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; }}
.stat {{ border: 1px solid var(--line); border-radius: 8px; background: var(--panel); padding: 10px; }}
.label {{ color: var(--muted); }}
.value {{ font-size: 24px; font-weight: 750; line-height: 1.05; margin-top: 4px; }}
.panel {{ border: 1px solid var(--line); border-radius: 8px; background: var(--panel); padding: 12px; overflow-x: auto; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(520px, 1fr)); gap: 12px; }}
.card {{ border: 1px solid var(--line); border-radius: 8px; overflow: hidden; background: #11171b; }}
.preview {{ display: block; aspect-ratio: 16 / 9; background: #050607; }}
.preview img {{ width: 100%; height: 100%; object-fit: contain; display: block; }}
.body {{ padding: 10px; display: grid; gap: 5px; }}
.title {{ font-weight: 700; }}
.muted {{ color: var(--muted); }}
.warn {{ color: var(--warn); font-weight: 700; }}
.ok {{ color: var(--ok); }}
h2 {{ margin: 0 0 10px; font-size: 16px; }}
table {{ width: 100%; min-width: 1280px; border-collapse: collapse; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
td {{ overflow-wrap: anywhere; }}
code {{ display: block; overflow-x: auto; padding: 6px; border: 1px solid var(--line); border-radius: 4px; background: #0d1013; white-space: pre; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 10px; }}
</style>
</head>
<body>
<header>
  <div class="wrap"><h1>{html.escape(title)}</h1></div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Pending</div><div class="value warn">{html.escape(summary['pending_rows'])}</div></div>
    <div class="stat"><div class="label">Ready</div><div class="value ok">{html.escape(summary['review_ready_rows'])}</div></div>
    <div class="stat"><div class="label">Sheets</div><div class="value">{html.escape(summary['sheet_rows'])}</div></div>
    <div class="stat"><div class="label">Issues</div><div class="value ok">{html.escape(summary['issue_rows'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div></section>
  <section class="grid">{cards}</section>
  <section class="panel">
    <h2>Synthese</h2>
    {render_table([summary], SUMMARY_FIELDNAMES)}
  </section>
  <section class="panel">
    <h2>Pending</h2>
    {render_table(rows, PENDING_FIELDNAMES)}
  </section>
</main>
<script>
const TEX_RAW_SAME_ARCHIVE_PENDING_REVIEW = {data_json};
</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    raw_pack_manifest: Path,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows, decisions = build_rows(output_dir, read_csv(raw_pack_manifest))
    summary = summary_row(rows, decisions)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "pending.csv", PENDING_FIELDNAMES, rows)
    write_tsv(output_dir / "decisions_template.tsv", DECISION_FIELDNAMES, decisions)
    (output_dir / "index.html").write_text(build_html(summary, rows, decisions, output_dir, title))
    return summary, rows, decisions


def main() -> None:
    parser = argparse.ArgumentParser(description="Build focused review sheets for pending raw same-archive .tex promotions.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--raw-pack-manifest", type=Path, default=DEFAULT_RAW_PACK_MANIFEST)
    parser.add_argument("--title", default="Lands of Lore II .tex Raw Same-Archive Pending Review")
    args = parser.parse_args()

    summary, _rows, _decisions = write_report(args.output, args.raw_pack_manifest, args.title)
    print(f"Pending raw same-archive promotions: {summary['pending_rows']}")
    print(f"Review ready rows: {summary['review_ready_rows']}")
    print(f"Decision template rows: {summary['decision_template_rows']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")
    if summary["issue_rows"] != "0":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
