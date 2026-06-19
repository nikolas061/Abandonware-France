#!/usr/bin/env python3
"""Build focused review sheets for large unresolved .tex probe candidates."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


DEFAULT_OUTPUT = Path("output/tex_large_unresolved_probe_review")
DEFAULT_BEST_CANDIDATES = Path("output/tex_large_unresolved_probe_render/best_candidates.csv")
DEFAULT_REMAINING_PROFILE = Path("output/tex_remaining_reference_profile/profile.csv")
DEFAULT_REVIEW_DECISIONS = Path("review_decisions/tex_large_unresolved_probe_decisions.tsv")
SHEET_SIZE = (1800, 1000)
ALLOWED_REVIEW_STATUSES = {"accepted", "rejected", "deferred"}

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_rows",
    "segment_rows",
    "unique_pcx",
    "review_ready_rows",
    "decision_template_rows",
    "sheet_rows",
    "missing_native_paths",
    "missing_fullhd_paths",
    "missing_sheet_paths",
    "decision_file_rows",
    "accepted_rows",
    "rejected_rows",
    "deferred_rows",
    "undecided_rows",
    "decision_issue_rows",
    "issue_rows",
    "next_action",
]

CANDIDATE_FIELDNAMES = [
    "review_id",
    "review_status",
    "review_note",
    "rank",
    "archive",
    "archive_tag",
    "texture_path",
    "pcx_name",
    "segment_index",
    "body_offset",
    "body_offset_hex",
    "body_first_word",
    "segment_size",
    "skip",
    "width",
    "height",
    "entropy",
    "dominant_ratio",
    "zero_ratio",
    "horizontal_equal_ratio",
    "vertical_equal_ratio",
    "row_repeat_ratio",
    "structure_score",
    "native_path",
    "native_exists",
    "fullhd_path",
    "fullhd_exists",
    "review_sheet_path",
    "review_sheet_exists",
    "decision_template_line",
    "issues",
]

SEGMENT_FIELDNAMES = [
    "segment_id",
    "archive",
    "archive_tag",
    "texture_path",
    "pcx_name",
    "segment_index",
    "body_offset",
    "body_offset_hex",
    "body_first_word",
    "segment_size",
    "candidate_rows",
    "best_rank",
    "best_score",
    "review_sheet_path",
    "review_sheet_exists",
    "issues",
]

DECISION_FIELDNAMES = [
    "archive",
    "name",
    "segment_index",
    "body_offset_hex",
    "rank",
    "review_status",
    "review_note",
    "review_id",
    "candidate_native_path",
    "candidate_fullhd_path",
    "review_sheet_path",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def read_tsv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


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


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._") or "unnamed"


def normalize_name(value: str) -> str:
    return Path(value.replace("\\", "/")).name.lower()


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    if not path_text:
        return ""
    path = Path(path_text)
    try:
        relative = path.relative_to(base_dir)
    except ValueError:
        relative = Path(os.path.relpath(path, base_dir))
    return relative.as_posix()


def int_value(row: dict[str, str], field: str) -> int:
    raw = row.get(field, "")
    try:
        return int(raw, 0) if raw else 0
    except ValueError:
        return 0


def score_value(row: dict[str, str]) -> float:
    try:
        return float(row.get("structure_score") or 0)
    except ValueError:
        return 0.0


def profile_lookup(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    lookup: dict[tuple[str, str], dict[str, str]] = {}
    for row in rows:
        archive_tag = row.get("archive_tag", "") or Path(row.get("archive", "")).stem.upper()
        name = normalize_name(row.get("normalized_pcx_name") or row.get("pcx_name", ""))
        if archive_tag and name:
            lookup[(archive_tag, name)] = row
    return lookup


def decision_lookup(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    lookup: dict[str, dict[str, str]] = {}
    for row in rows:
        rid = row.get("review_id", "")
        if rid:
            lookup[rid] = row
    return lookup


def segment_key(row: dict[str, str]) -> tuple[str, str, str, str]:
    return (
        row.get("archive", ""),
        normalize_name(row.get("pcx_name", "")),
        row.get("segment_index", ""),
        row.get("body_offset_hex", "") or row.get("body_offset", ""),
    )


def review_id(row: dict[str, str]) -> str:
    return "__".join(
        [
            safe_name(row.get("archive_tag", "")),
            safe_name(normalize_name(row.get("pcx_name", ""))),
            f"seg{safe_name(row.get('segment_index', ''))}",
            safe_name(row.get("body_offset_hex", "") or row.get("body_offset", "")),
            f"rank{safe_name(row.get('rank', ''))}",
        ]
    )


def segment_id(row: dict[str, str]) -> str:
    return "__".join(
        [
            safe_name(row.get("archive_tag", "")),
            safe_name(normalize_name(row.get("pcx_name", ""))),
            f"seg{safe_name(row.get('segment_index', ''))}",
            safe_name(row.get("body_offset_hex", "") or row.get("body_offset", "")),
        ]
    )


def draw_text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, fill: tuple[int, int, int]) -> None:
    font = ImageFont.load_default()
    draw.text(xy, text, fill=fill, font=font)


def image_on_panel(source: Image.Image, size: tuple[int, int]) -> Image.Image:
    image = source.convert("RGB")
    scale = min(size[0] / image.width, size[1] / image.height)
    scaled = image.resize(
        (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
        Image.Resampling.NEAREST,
    )
    panel = Image.new("RGB", size, (8, 10, 12))
    panel.paste(scaled, ((size[0] - scaled.width) // 2, (size[1] - scaled.height) // 2))
    return panel


def write_review_sheet(segment: dict[str, str], candidates: list[dict[str, str]], target: Path) -> list[str]:
    issues: list[str] = []
    target.parent.mkdir(parents=True, exist_ok=True)
    sheet = Image.new("RGB", SHEET_SIZE, (16, 19, 22))
    draw = ImageDraw.Draw(sheet)
    draw.rectangle((0, 0, SHEET_SIZE[0] - 1, SHEET_SIZE[1] - 1), outline=(67, 76, 85), width=1)

    title = f"{segment.get('archive_tag', '')} / {segment.get('pcx_name', '')}"
    meta = (
        f"segment {segment.get('segment_index', '')} | {segment.get('body_offset_hex', '')} | "
        f"prefix {segment.get('body_first_word', '')} | size {segment.get('segment_size', '')}"
    )
    draw_text(draw, (24, 20), title, (238, 243, 246))
    draw_text(draw, (24, 42), meta, (174, 186, 196))
    draw_text(draw, (24, 64), f"texture: {segment.get('texture_path', '')}", (137, 151, 162))

    panel_y = 120
    panel_size = (548, 650)
    gap = 24
    for index, row in enumerate(candidates[:3]):
        x = 24 + index * (panel_size[0] + gap)
        label = (
            f"rank {row.get('rank', '')} | w{row.get('width', '')} skip {row.get('skip', '')} | "
            f"score {row.get('structure_score', '')}"
        )
        draw_text(draw, (x, panel_y - 24), label, (238, 243, 246))
        draw.rectangle((x, panel_y, x + panel_size[0] - 1, panel_y + panel_size[1] - 1), outline=(67, 76, 85), width=1)
        native_path = Path(row.get("native_path", ""))
        if not native_path.exists():
            draw_text(draw, (x + 20, panel_y + 20), f"missing: {native_path}", (240, 176, 106))
            issues.append(f"missing_native_rank{row.get('rank', '')}")
            continue
        try:
            with Image.open(native_path) as image:
                image.load()
                panel = image_on_panel(image, panel_size)
        except Exception as exc:
            draw_text(draw, (x + 20, panel_y + 20), f"open failed: {exc}", (240, 176, 106))
            issues.append(f"open_failed_rank{row.get('rank', '')}")
            continue
        sheet.paste(panel, (x, panel_y))

    note_y = 810
    draw_text(draw, (24, note_y), "Decision lines:", (238, 243, 246))
    for offset, row in enumerate(candidates[:3], start=1):
        decision = (
            f"{row.get('archive_tag', '')}\t{row.get('pcx_name', '')}\t"
            f"{row.get('segment_index', '')}\t{row.get('body_offset_hex', '')}\t"
            f"{row.get('rank', '')}\taccepted|rejected|deferred\t"
        )
        draw_text(draw, (24, note_y + 22 * offset), decision, (174, 186, 196))
    sheet.save(target, "PNG", optimize=True)
    return issues


def build_rows(
    output_dir: Path,
    best_rows: list[dict[str, str]],
    profiles: dict[tuple[str, str], dict[str, str]],
    decisions_by_id: dict[str, dict[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    grouped: dict[tuple[str, str, str, str], list[dict[str, str]]] = {}
    for row in best_rows:
        grouped.setdefault(segment_key(row), []).append(row)

    candidate_rows: list[dict[str, str]] = []
    segment_rows: list[dict[str, str]] = []
    decision_rows: list[dict[str, str]] = []
    for key in sorted(grouped):
        group = sorted(grouped[key], key=lambda row: (int_value(row, "rank"), -score_value(row)))
        first = group[0]
        profile = profiles.get((first.get("archive_tag", ""), normalize_name(first.get("pcx_name", ""))), {})
        sheet_path = output_dir / "sheets" / f"{segment_id(first)}.png"
        sheet_issues = write_review_sheet({**first, "texture_path": profile.get("texture_path", "")}, group, sheet_path)
        segment_issues = list(sheet_issues)
        if not sheet_path.exists():
            segment_issues.append("missing_review_sheet")

        segment_rows.append(
            {
                "segment_id": segment_id(first),
                "archive": first.get("archive", ""),
                "archive_tag": first.get("archive_tag", ""),
                "texture_path": profile.get("texture_path", ""),
                "pcx_name": first.get("pcx_name", ""),
                "segment_index": first.get("segment_index", ""),
                "body_offset": first.get("body_offset", ""),
                "body_offset_hex": first.get("body_offset_hex", ""),
                "body_first_word": first.get("body_first_word", ""),
                "segment_size": first.get("segment_size", ""),
                "candidate_rows": str(len(group)),
                "best_rank": first.get("rank", ""),
                "best_score": first.get("structure_score", ""),
                "review_sheet_path": str(sheet_path),
                "review_sheet_exists": "yes" if sheet_path.exists() else "no",
                "issues": ";".join(dict.fromkeys(segment_issues)),
            }
        )

        for row in group:
            issues: list[str] = []
            native_path = Path(row.get("native_path", ""))
            fullhd_path = Path(row.get("fullhd_path", ""))
            if not native_path.exists():
                issues.append("missing_native_path")
            if not fullhd_path.exists():
                issues.append("missing_fullhd_path")
            if not sheet_path.exists():
                issues.append("missing_review_sheet")
            rid = review_id(row)
            decision = decisions_by_id.get(rid, {})
            review_status = decision.get("review_status", "")
            review_note = decision.get("review_note", "")
            if review_status and review_status not in ALLOWED_REVIEW_STATUSES:
                issues.append(f"review_status:{review_status}")
            decision_line = (
                f"{row.get('archive_tag', '')}\t{row.get('pcx_name', '')}\t"
                f"{row.get('segment_index', '')}\t{row.get('body_offset_hex', '')}\t"
                f"{row.get('rank', '')}\taccepted|rejected|deferred\t"
            )
            candidate_rows.append(
                {
                    "review_id": rid,
                    "review_status": review_status,
                    "review_note": review_note,
                    "rank": row.get("rank", ""),
                    "archive": row.get("archive", ""),
                    "archive_tag": row.get("archive_tag", ""),
                    "texture_path": profile.get("texture_path", ""),
                    "pcx_name": row.get("pcx_name", ""),
                    "segment_index": row.get("segment_index", ""),
                    "body_offset": row.get("body_offset", ""),
                    "body_offset_hex": row.get("body_offset_hex", ""),
                    "body_first_word": row.get("body_first_word", ""),
                    "segment_size": row.get("segment_size", ""),
                    "skip": row.get("skip", ""),
                    "width": row.get("width", ""),
                    "height": row.get("height", ""),
                    "entropy": row.get("entropy", ""),
                    "dominant_ratio": row.get("dominant_ratio", ""),
                    "zero_ratio": row.get("zero_ratio", ""),
                    "horizontal_equal_ratio": row.get("horizontal_equal_ratio", ""),
                    "vertical_equal_ratio": row.get("vertical_equal_ratio", ""),
                    "row_repeat_ratio": row.get("row_repeat_ratio", ""),
                    "structure_score": row.get("structure_score", ""),
                    "native_path": row.get("native_path", ""),
                    "native_exists": "yes" if native_path.exists() else "no",
                    "fullhd_path": row.get("fullhd_path", ""),
                    "fullhd_exists": "yes" if fullhd_path.exists() else "no",
                    "review_sheet_path": str(sheet_path),
                    "review_sheet_exists": "yes" if sheet_path.exists() else "no",
                    "decision_template_line": decision_line,
                    "issues": ";".join(dict.fromkeys(issues)),
                }
            )
            decision_rows.append(
                {
                    "archive": row.get("archive_tag", ""),
                    "name": row.get("pcx_name", ""),
                    "segment_index": row.get("segment_index", ""),
                    "body_offset_hex": row.get("body_offset_hex", ""),
                    "rank": row.get("rank", ""),
                    "review_status": "",
                    "review_note": "",
                    "review_id": rid,
                    "candidate_native_path": row.get("native_path", ""),
                    "candidate_fullhd_path": row.get("fullhd_path", ""),
                    "review_sheet_path": str(sheet_path),
                }
            )
    return candidate_rows, segment_rows, decision_rows


def summary_row(
    candidate_rows: list[dict[str, str]],
    segment_rows: list[dict[str, str]],
    decision_rows: list[dict[str, str]],
    review_decision_rows: list[dict[str, str]],
) -> dict[str, str]:
    issue_rows = sum(1 for row in candidate_rows if row.get("issues")) + sum(
        1 for row in segment_rows if row.get("issues")
    )
    accepted_rows = sum(1 for row in candidate_rows if row.get("review_status") == "accepted")
    rejected_rows = sum(1 for row in candidate_rows if row.get("review_status") == "rejected")
    deferred_rows = sum(1 for row in candidate_rows if row.get("review_status") == "deferred")
    undecided_rows = sum(1 for row in candidate_rows if not row.get("review_status"))
    decision_issue_rows = sum(
        1
        for row in candidate_rows
        if row.get("review_status") and row.get("review_status") not in ALLOWED_REVIEW_STATUSES
    )
    if accepted_rows:
        next_action = f"integrate {accepted_rows} accepted large unresolved .tex probe candidates"
    elif undecided_rows:
        next_action = f"complete decisions_template.tsv for {len(candidate_rows)} large unresolved .tex probe candidates"
    elif rejected_rows and not deferred_rows:
        next_action = f"derive decoder path after rejecting {rejected_rows} large unresolved .tex probe candidates"
    elif rejected_rows or deferred_rows:
        next_action = (
            f"derive decoder path after {rejected_rows} rejected and {deferred_rows} deferred "
            "large unresolved .tex probe candidates"
        )
    elif candidate_rows:
        next_action = "derive decoder path after large unresolved .tex probe review"
    else:
        next_action = "no large unresolved .tex probe candidates"
    return {
        "scope": "total",
        "candidate_rows": str(len(candidate_rows)),
        "segment_rows": str(len(segment_rows)),
        "unique_pcx": str(len({row.get("pcx_name", "").lower() for row in candidate_rows if row.get("pcx_name")})),
        "review_ready_rows": str(sum(1 for row in candidate_rows if not row.get("issues"))),
        "decision_template_rows": str(len(decision_rows)),
        "sheet_rows": str(sum(1 for row in segment_rows if row.get("review_sheet_exists") == "yes")),
        "missing_native_paths": str(sum(1 for row in candidate_rows if row.get("native_exists") != "yes")),
        "missing_fullhd_paths": str(sum(1 for row in candidate_rows if row.get("fullhd_exists") != "yes")),
        "missing_sheet_paths": str(sum(1 for row in segment_rows if row.get("review_sheet_exists") != "yes")),
        "decision_file_rows": str(len(review_decision_rows)),
        "accepted_rows": str(accepted_rows),
        "rejected_rows": str(rejected_rows),
        "deferred_rows": str(deferred_rows),
        "undecided_rows": str(undecided_rows),
        "decision_issue_rows": str(decision_issue_rows),
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
    title = f"{row.get('archive_tag', '')} / {row.get('pcx_name', '')}"
    details = (
        f"seg {row.get('segment_index', '')} | {row.get('body_offset_hex', '')} | "
        f"{row.get('candidate_rows', '')} candidates"
    )
    return f"""
<article class="card">
  <a class="preview" href="{sheet}"><img src="{sheet}" loading="lazy" decoding="async" alt=""></a>
  <div class="body">
    <div class="title">{html.escape(title)}</div>
    <div class="muted">{html.escape(details)}</div>
    <div class="muted">best score {html.escape(row.get('best_score', ''))}</div>
  </div>
</article>"""


def build_html(
    summary: dict[str, str],
    candidates: list[dict[str, str]],
    segments: list[dict[str, str]],
    decisions: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "candidates": candidates, "segments": segments, "decisions": decisions}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    cards = "\n".join(render_card(row, output_dir) for row in segments)
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("candidates.csv", output_dir / "candidates.csv"),
            ("segments.csv", output_dir / "segments.csv"),
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
  --ok: #78d98f;
  --warn: #f0b06a;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  min-height: 100vh;
  background: var(--bg);
  color: var(--text);
  font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}}
.wrap {{ width: min(1760px, calc(100vw - 28px)); margin: 0 auto; }}
header {{ border-bottom: 1px solid var(--line); background: #12171b; padding: 18px 0 14px; }}
h1 {{ margin: 0; font-size: 21px; font-weight: 700; letter-spacing: 0; }}
main {{ padding: 16px 0 28px; display: grid; gap: 16px; }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; }}
.stat {{ border: 1px solid var(--line); border-radius: 8px; background: var(--panel); padding: 10px; }}
.label, .muted {{ color: var(--muted); }}
.value {{ font-size: 24px; font-weight: 750; line-height: 1.05; margin-top: 4px; }}
.ok {{ color: var(--ok); }}
.warn {{ color: var(--warn); }}
.panel {{ border: 1px solid var(--line); border-radius: 8px; background: var(--panel); padding: 12px; overflow-x: auto; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(460px, 1fr)); gap: 12px; }}
.card {{ border: 1px solid var(--line); border-radius: 8px; overflow: hidden; background: #11171b; }}
.preview {{ display: block; aspect-ratio: 16 / 9; background: #050607; }}
.preview img {{ width: 100%; height: 100%; object-fit: contain; display: block; }}
.body {{ padding: 10px; display: grid; gap: 5px; }}
.title {{ font-weight: 700; overflow-wrap: anywhere; }}
h2 {{ margin: 0 0 10px; font-size: 16px; }}
table {{ width: 100%; min-width: 1500px; border-collapse: collapse; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
td {{ overflow-wrap: anywhere; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 10px; }}
</style>
</head>
<body>
<header>
  <div class="wrap"><h1>{html.escape(title)}</h1></div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Candidates</div><div class="value warn">{html.escape(summary['candidate_rows'])}</div></div>
    <div class="stat"><div class="label">Segments</div><div class="value">{html.escape(summary['segment_rows'])}</div></div>
    <div class="stat"><div class="label">Ready</div><div class="value ok">{html.escape(summary['review_ready_rows'])}</div></div>
    <div class="stat"><div class="label">Issues</div><div class="value ok">{html.escape(summary['issue_rows'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div></section>
  <section class="grid">{cards}</section>
  <section class="panel">
    <h2>Synthese</h2>
    {render_table([summary], SUMMARY_FIELDNAMES)}
  </section>
  <section class="panel">
    <h2>Segments</h2>
    {render_table(segments, SEGMENT_FIELDNAMES)}
  </section>
  <section class="panel">
    <h2>Candidats</h2>
    {render_table(candidates, CANDIDATE_FIELDNAMES)}
  </section>
</main>
<script>
const TEX_LARGE_UNRESOLVED_PROBE_REVIEW = {data_json};
</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    best_candidates: Path,
    remaining_profile: Path,
    review_decisions: Path,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    profiles = profile_lookup(read_csv(remaining_profile)) if remaining_profile.exists() else {}
    review_decision_rows = read_tsv(review_decisions)
    candidates, segments, decisions = build_rows(
        output_dir,
        read_csv(best_candidates),
        profiles,
        decision_lookup(review_decision_rows),
    )
    summary = summary_row(candidates, segments, decisions, review_decision_rows)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "candidates.csv", CANDIDATE_FIELDNAMES, candidates)
    write_csv(output_dir / "segments.csv", SEGMENT_FIELDNAMES, segments)
    write_tsv(output_dir / "decisions_template.tsv", DECISION_FIELDNAMES, decisions)
    (output_dir / "index.html").write_text(
        build_html(summary, candidates, segments, decisions, output_dir, title)
    )
    return summary, candidates, segments


def main() -> None:
    parser = argparse.ArgumentParser(description="Build review sheets for large unresolved .tex probe candidates.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--best-candidates", type=Path, default=DEFAULT_BEST_CANDIDATES)
    parser.add_argument("--remaining-profile", type=Path, default=DEFAULT_REMAINING_PROFILE)
    parser.add_argument("--review-decisions", type=Path, default=DEFAULT_REVIEW_DECISIONS)
    parser.add_argument("--title", default="Lands of Lore II .tex Large Unresolved Probe Review")
    args = parser.parse_args()

    summary, _candidates, _segments = write_report(
        args.output,
        args.best_candidates,
        args.remaining_profile,
        args.review_decisions,
        args.title,
    )
    print(f"Large probe candidates: {summary['candidate_rows']}")
    print(f"Segments: {summary['segment_rows']}")
    print(f"Review ready rows: {summary['review_ready_rows']}")
    print(f"Decision template rows: {summary['decision_template_rows']}")
    print(f"Rejected rows: {summary['rejected_rows']}")
    print(f"Undecided rows: {summary['undecided_rows']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")
    if summary["issue_rows"] != "0":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
