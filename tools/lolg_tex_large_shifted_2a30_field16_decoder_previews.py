#!/usr/bin/env python3
"""Materialize Full HD previews for routed shifted 0x2a30 field16 decoder rows."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import re
from pathlib import Path

from PIL import Image


TARGET_SIZE = (1920, 1080)
DEFAULT_OUTPUT = Path("output/tex_large_shifted_2a30_field16_decoder_previews")
DEFAULT_ROUTES = Path("output/tex_large_shifted_2a30_field16_decoder_route/routes.csv")
DEFAULT_CHOICES = Path("reports/te_guarded_cmd20_v10_riskaware_markerknownsymadv_plus_puddle.tsv")

SUMMARY_FIELDNAMES = [
    "scope",
    "route_rows",
    "routed_rows",
    "manifest_rows",
    "native_previews",
    "fullhd_previews",
    "source_previews",
    "missing_source_previews",
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
    "choice_mode",
    "choice_width",
    "choice_height",
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
    "issues",
]


def read_csv(path: Path, *, delimiter: str = ",") -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter=delimiter))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._") or "unnamed"


def route_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("archive_tag", ""), row.get("pcx_name", "").lower(), row.get("decoder_extra", "")


def choice_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("level", ""), row.get("name", "").lower(), row.get("extra", "")


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


def build_manifest(
    output_dir: Path,
    route_rows: list[dict[str, str]],
    choice_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    choices = {choice_key(row): row for row in choice_rows if row.get("source") == "marker" and row.get("extra")}
    native_dir = output_dir / "native"
    fullhd_dir = output_dir / "fullhd"
    native_dir.mkdir(parents=True, exist_ok=True)
    fullhd_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, str]] = []
    for route in route_rows:
        if route.get("route_status") != "routed_field16_decoder":
            continue
        issues: list[str] = []
        choice = choices.get(route_key(route), {})
        if not choice:
            issues.append("missing_choice_row")
        source_preview = Path(choice.get("out", ""))
        source_exists = bool(choice.get("out")) and source_preview.exists()
        if not source_exists:
            issues.append("missing_source_preview")

        stem = (
            f"{safe_name(route.get('archive_tag', ''))}__{safe_name(route.get('pcx_name', ''))}"
            f"__seg{safe_name(route.get('segment_index', ''))}_{safe_name(route.get('body_offset_hex', ''))}"
            f"__{safe_name(route.get('decoder_rule', ''))}_extra{safe_name(route.get('decoder_extra', ''))}"
        )
        native_path = native_dir / f"{stem}.png"
        fullhd_path = fullhd_dir / f"{stem}_fullhd.png"
        native_width = native_height = fullhd_width = fullhd_height = ""

        if source_exists:
            with Image.open(source_preview) as image:
                native = image.convert("RGBA")
                native.save(native_path, "PNG")
                native_width, native_height = str(native.width), str(native.height)
                fullhd = make_fullhd(native)
                fullhd.save(fullhd_path, "PNG")
                fullhd_width, fullhd_height = str(fullhd.width), str(fullhd.height)

        native_exists = native_path.exists()
        fullhd_exists = fullhd_path.exists()
        if source_exists and not native_exists:
            issues.append("missing_native_preview")
        if source_exists and not fullhd_exists:
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
                "decoder_extra": route.get("decoder_extra", ""),
                "choice_mode": choice.get("mode", ""),
                "choice_width": choice.get("width", ""),
                "choice_height": choice.get("height", ""),
                "choice_score": choice.get("score", ""),
                "source_preview_path": choice.get("out", ""),
                "source_preview_exists": "yes" if source_exists else "no",
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


def build_summary(route_rows: list[dict[str, str]], manifest_rows: list[dict[str, str]]) -> dict[str, str]:
    routed_rows = [row for row in route_rows if row.get("route_status") == "routed_field16_decoder"]
    native_previews = [row for row in manifest_rows if row.get("native_preview_exists") == "yes"]
    fullhd_previews = [row for row in manifest_rows if row.get("fullhd_preview_exists") == "yes"]
    source_previews = [row for row in manifest_rows if row.get("source_preview_exists") == "yes"]
    missing_source = [row for row in manifest_rows if row.get("source_preview_exists") != "yes"]
    issue_rows = [row for row in manifest_rows if row.get("issues")]
    fullhd_good = [
        row
        for row in fullhd_previews
        if (row.get("fullhd_width"), row.get("fullhd_height")) == (str(TARGET_SIZE[0]), str(TARGET_SIZE[1]))
    ]
    clean = (
        len(routed_rows) == 4
        and len(manifest_rows) == 4
        and len(native_previews) == 4
        and len(fullhd_good) == 4
        and len(source_previews) == 4
        and not missing_source
        and not issue_rows
    )
    if clean:
        verdict = "field16_decoder_previews_ready"
        next_action = "review routed shifted 0x2a30 field16 decoder previews before promotion into .tex coverage"
    elif issue_rows:
        verdict = "field16_decoder_previews_issues"
        next_action = "fix routed shifted 0x2a30 field16 decoder preview issues"
    else:
        verdict = "field16_decoder_previews_incomplete"
        next_action = "complete routed shifted 0x2a30 field16 decoder previews"
    return {
        "scope": "total",
        "route_rows": str(len(route_rows)),
        "routed_rows": str(len(routed_rows)),
        "manifest_rows": str(len(manifest_rows)),
        "native_previews": str(len(native_previews)),
        "fullhd_previews": str(len(fullhd_good)),
        "source_previews": str(len(source_previews)),
        "missing_source_previews": str(len(missing_source)),
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
  <div class="meta">{html.escape(row.get('decoder_rule', ''))} extra {html.escape(row.get('decoder_extra', ''))}</div>
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
img {{ width: 100%; aspect-ratio: 16 / 9; object-fit: contain; background: #050607; border: 1px solid var(--line); }}
table {{ width: 100%; border-collapse: collapse; background: var(--panel); border: 1px solid var(--line); margin-top: 10px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; font-size: 12px; }}
th {{ color: var(--muted); background: #20262b; }}
td {{ max-width: 420px; overflow-wrap: anywhere; }}
</style>
</head>
<body>
<main>
<h1>{html.escape(title)}</h1>
<p class="muted">Materializes routed shifted 0x2a30 field16 decoder previews as native and Full HD PNGs.</p>
<p>{links}</p>
<h2>Previews</h2>
<section class="grid">{render_cards(manifest_rows, output_dir)}</section>
<h2>Summary</h2>
{render_table([summary], SUMMARY_FIELDNAMES)}
<h2>Manifest</h2>
{render_table(manifest_rows, MANIFEST_FIELDNAMES)}
</main>
<script>const TEX_LARGE_SHIFTED_2A30_FIELD16_DECODER_PREVIEWS = {data_json};</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    routes_path: Path,
    choices_path: Path,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    route_rows = read_csv(routes_path)
    choice_rows = read_csv(choices_path, delimiter="\t")
    manifest_rows = build_manifest(output_dir, route_rows, choice_rows)
    summary = build_summary(route_rows, manifest_rows)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "manifest.csv", MANIFEST_FIELDNAMES, manifest_rows)
    (output_dir / "index.html").write_text(
        build_html(summary, manifest_rows, output_dir, title),
        encoding="utf-8",
    )
    return summary, manifest_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Materialize routed shifted 0x2a30 field16 decoder previews.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--routes", type=Path, default=DEFAULT_ROUTES)
    parser.add_argument("--choices", type=Path, default=DEFAULT_CHOICES)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Large Shifted 2a30 Field16 Decoder Previews",
    )
    args = parser.parse_args()

    summary, _manifest = write_report(args.output, args.routes, args.choices, args.title)
    print(f"Routed rows: {summary['routed_rows']}")
    print(f"Native previews: {summary['native_previews']}")
    print(f"Full HD previews: {summary['fullhd_previews']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
