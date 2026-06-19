#!/usr/bin/env python3
"""Pack reviewed shifted 0x2a30 field16 decoder previews as coverage assets."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import re
import shutil
from pathlib import Path

from PIL import Image


TARGET_SIZE = (1920, 1080)
DEFAULT_OUTPUT = Path("output/tex_large_shifted_2a30_field16_decoder_promoted_pack")
DEFAULT_PREVIEW_REVIEW = Path("output/tex_large_shifted_2a30_field16_decoder_previews_review/review.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "review_rows",
    "ready_rows",
    "coverage_eligible_rows",
    "coverage_eligible_unique_pcx",
    "native_assets",
    "fullhd_assets",
    "missing_native_paths",
    "missing_fullhd_paths",
    "issue_rows",
    "review_verdict",
    "next_action",
]

MANIFEST_FIELDNAMES = [
    "asset_id",
    "archive",
    "archive_tag",
    "texture_path",
    "pcx_name",
    "normalized_pcx_name",
    "segment_index",
    "body_offset_hex",
    "decoder_rule",
    "decoder_extra",
    "review_status",
    "coverage_eligible",
    "source_native_path",
    "source_native_exists",
    "source_fullhd_path",
    "source_fullhd_exists",
    "promoted_native_path",
    "promoted_native_exists",
    "promoted_fullhd_path",
    "promoted_fullhd_exists",
    "promoted_fullhd_width",
    "promoted_fullhd_height",
    "review_sheet_path",
    "issues",
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


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._") or "unnamed"


def normalize_pcx(name: str) -> str:
    return Path(name.replace("\\", "/")).name.lower()


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    if not path_text:
        return ""
    path = Path(path_text)
    try:
        relative = path.relative_to(base_dir)
    except ValueError:
        relative = Path(os.path.relpath(path, base_dir))
    return relative.as_posix()


def asset_id_for(row: dict[str, str]) -> str:
    return "__".join(
        [
            safe_name(row.get("archive_tag", "")),
            safe_name(normalize_pcx(row.get("pcx_name", ""))),
            "field16_decoder",
        ]
    )


def copy_asset(source: Path, target: Path, issues: list[str], issue_name: str) -> bool:
    if not source.exists():
        issues.append(issue_name)
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.is_symlink():
        target.unlink()
    shutil.copy2(source, target)
    if not target.exists():
        issues.append(f"missing_target:{issue_name}")
        return False
    return True


def image_size(path: Path, issues: list[str], issue_name: str) -> tuple[str, str]:
    if not path.exists():
        issues.append(issue_name)
        return "", ""
    try:
        with Image.open(path) as image:
            image.load()
            width, height = image.size
    except Exception as exc:
        issues.append(f"open_failed:{exc}")
        return "", ""
    return str(width), str(height)


def build_manifest(output_dir: Path, review_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for review in sorted(review_rows, key=lambda row: (row.get("archive_tag", ""), row.get("pcx_name", "").lower())):
        issues: list[str] = []
        if review.get("promotion_status") != "ready":
            issues.append(f"review_status:{review.get('promotion_status', '')}")
        if review.get("issues"):
            issues.append(f"review_issues:{review.get('issues', '')}")

        asset_id = asset_id_for(review)
        tag = safe_name(review.get("archive_tag", ""))
        native_source = Path(review.get("native_preview_path", ""))
        fullhd_source = Path(review.get("fullhd_preview_path", ""))
        promoted_native = output_dir / "native" / tag / f"{asset_id}_native.png"
        promoted_fullhd = output_dir / "descriptors" / tag / f"{asset_id}.png"
        native_ok = copy_asset(native_source, promoted_native, issues, "missing_source_native_path")
        fullhd_ok = copy_asset(fullhd_source, promoted_fullhd, issues, "missing_source_fullhd_path")
        fullhd_width, fullhd_height = image_size(
            promoted_fullhd,
            issues,
            "missing_promoted_fullhd_path",
        )
        if fullhd_ok and (fullhd_width, fullhd_height) != (str(TARGET_SIZE[0]), str(TARGET_SIZE[1])):
            issues.append("promoted_fullhd_not_fullhd")

        coverage_eligible = not issues
        rows.append(
            {
                "asset_id": asset_id,
                "archive": review.get("archive", ""),
                "archive_tag": review.get("archive_tag", ""),
                "texture_path": review.get("texture_path", ""),
                "pcx_name": review.get("pcx_name", ""),
                "normalized_pcx_name": normalize_pcx(review.get("pcx_name", "")),
                "segment_index": review.get("segment_index", ""),
                "body_offset_hex": review.get("body_offset_hex", ""),
                "decoder_rule": review.get("decoder_rule", ""),
                "decoder_extra": review.get("decoder_extra", ""),
                "review_status": review.get("promotion_status", ""),
                "coverage_eligible": "yes" if coverage_eligible else "no",
                "source_native_path": review.get("native_preview_path", ""),
                "source_native_exists": "yes" if native_source.exists() else "no",
                "source_fullhd_path": review.get("fullhd_preview_path", ""),
                "source_fullhd_exists": "yes" if fullhd_source.exists() else "no",
                "promoted_native_path": promoted_native.as_posix(),
                "promoted_native_exists": "yes" if native_ok else "no",
                "promoted_fullhd_path": promoted_fullhd.as_posix(),
                "promoted_fullhd_exists": "yes" if promoted_fullhd.exists() else "no",
                "promoted_fullhd_width": fullhd_width,
                "promoted_fullhd_height": fullhd_height,
                "review_sheet_path": review.get("review_sheet_path", ""),
                "issues": ";".join(dict.fromkeys(issues)),
            }
        )
    return rows


def build_summary(review_rows: list[dict[str, str]], manifest_rows: list[dict[str, str]]) -> dict[str, str]:
    ready_rows = [row for row in review_rows if row.get("promotion_status") == "ready" and not row.get("issues")]
    eligible_rows = [row for row in manifest_rows if row.get("coverage_eligible") == "yes"]
    issue_rows = [row for row in manifest_rows if row.get("issues")]
    clean = len(review_rows) == 4 and len(ready_rows) == 4 and len(eligible_rows) == 4 and not issue_rows
    if clean:
        verdict = "field16_decoder_promoted_pack_ready"
        next_action = "refresh .tex augmented coverage with 4 field16 decoder promotions"
    elif issue_rows:
        verdict = "field16_decoder_promoted_pack_blocked"
        next_action = "fix field16 decoder promoted pack issues"
    else:
        verdict = "field16_decoder_promoted_pack_incomplete"
        next_action = "complete field16 decoder promoted pack"
    return {
        "scope": "total",
        "review_rows": str(len(review_rows)),
        "ready_rows": str(len(ready_rows)),
        "coverage_eligible_rows": str(len(eligible_rows)),
        "coverage_eligible_unique_pcx": str(len({row["normalized_pcx_name"] for row in eligible_rows})),
        "native_assets": str(sum(1 for row in manifest_rows if row.get("promoted_native_exists") == "yes")),
        "fullhd_assets": str(sum(1 for row in manifest_rows if row.get("promoted_fullhd_exists") == "yes")),
        "missing_native_paths": str(sum(1 for row in manifest_rows if row.get("promoted_native_exists") != "yes")),
        "missing_fullhd_paths": str(sum(1 for row in manifest_rows if row.get("promoted_fullhd_exists") != "yes")),
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
    image = html.escape(relative_href(row.get("promoted_fullhd_path", ""), output_dir))
    native = html.escape(relative_href(row.get("promoted_native_path", ""), output_dir))
    title = f"{row.get('archive_tag', '')} / {row.get('pcx_name', '')}"
    return f"""
<article>
  <a class="preview" href="{image}"><img src="{image}" loading="lazy" decoding="async" alt=""></a>
  <div class="body">
    <div class="title">{html.escape(title)}</div>
    <div>{html.escape(row.get('decoder_rule', ''))} extra {html.escape(row.get('decoder_extra', ''))}</div>
    <div class="muted">coverage {html.escape(row.get('coverage_eligible', ''))}</div>
    <div><a href="{native}">native</a><a href="{image}">fullhd</a></div>
  </div>
</article>"""


def build_html(
    summary: dict[str, str],
    manifest_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "manifest": manifest_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    cards = "\n".join(render_card(row, output_dir) for row in manifest_rows)
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
    <div class="stat"><div class="label">Coverage eligible</div><div class="value ok">{html.escape(summary['coverage_eligible_rows'])}</div></div>
    <div class="stat"><div class="label">Full HD assets</div><div class="value ok">{html.escape(summary['fullhd_assets'])}</div></div>
    <div class="stat"><div class="label">Native assets</div><div class="value">{html.escape(summary['native_assets'])}</div></div>
    <div class="stat"><div class="label">Issues</div><div class="value ok">{html.escape(summary['issue_rows'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div><div class="muted">{html.escape(summary['review_verdict'])}: {html.escape(summary['next_action'])}</div></section>
  <section class="grid">{cards}</section>
  <section class="panel"><h2>Summary</h2>{render_table([summary], SUMMARY_FIELDNAMES)}</section>
  <section class="panel"><h2>Manifest</h2>{render_table(manifest_rows, MANIFEST_FIELDNAMES)}</section>
</main>
<script>const TEX_LARGE_SHIFTED_2A30_FIELD16_DECODER_PROMOTED_PACK = {data_json};</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    preview_review: Path,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    review_rows = read_csv(preview_review)
    manifest_rows = build_manifest(output_dir, review_rows)
    summary = build_summary(review_rows, manifest_rows)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "manifest.csv", MANIFEST_FIELDNAMES, manifest_rows)
    (output_dir / "index.html").write_text(
        build_html(summary, manifest_rows, output_dir, title),
        encoding="utf-8",
    )
    return summary, manifest_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Pack reviewed shifted 0x2a30 field16 decoder previews.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--preview-review", type=Path, default=DEFAULT_PREVIEW_REVIEW)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Large Shifted 2a30 Field16 Decoder Promoted Pack",
    )
    args = parser.parse_args()

    summary, _manifest = write_report(args.output, args.preview_review, args.title)
    print(f"Review rows: {summary['review_rows']}")
    print(f"Coverage eligible rows: {summary['coverage_eligible_rows']}")
    print(f"Full HD assets: {summary['fullhd_assets']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")
    if summary["issue_rows"] != "0":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
