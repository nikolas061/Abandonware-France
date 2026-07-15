#!/usr/bin/env python3
"""Compare bounded 0x2a30/0x5c family payload starts for the branch target."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import re
from collections import defaultdict
from pathlib import Path

from probe_te_span_decode import decode_span

try:
    from analyze_te_pcx_payloads import MARKERS, bounded_payload, load_rows
    from export_shp import read_palette
    from export_te_span_previews import render_indexed
    from score_te_raw_layouts import row_score
except ModuleNotFoundError as exc:
    OPTIONAL_IMPORT_ERROR = exc
    MARKERS = []
    bounded_payload = None
    load_rows = None
    read_palette = None
    render_indexed = None
    row_score = None
else:
    OPTIONAL_IMPORT_ERROR = None


DEFAULT_OUTPUT = Path("output/tex_large_shifted_2a30_branch_bounded_family_probe")
DEFAULT_DECODER_PATHS = Path("output/tex_large_shifted_2a30_branch_decoder_path_probe/paths.csv")
DEFAULT_RENDERER_SUMMARY = Path("output/tex_large_shifted_2a30_branch_renderer_probe/summary.csv")
DEFAULT_CATALOG = Path("reports/te_resources.tsv")
DEFAULT_FEATURES = Path("reports/te_decoder_features.tsv")
DEFAULT_PROLOGUE_FAMILIES = Path("reports/te_prologue_families.tsv")
DEFAULT_CHOICES = Path("reports/te_guarded_cmd20_v10_riskaware_markerknownsymadv_plus_puddle.tsv")
DEFAULT_PALETTE = Path("extracted/LOCAL/7231c8f9.pal")

SUMMARY_FIELDNAMES = [
    "scope",
    "target_branch_rows",
    "family_rows",
    "family_target_rows",
    "family_support_rows",
    "candidate_rows",
    "target_candidate_rows",
    "preview_rows",
    "ranked_preview_rows",
    "issue_rows",
    "family_marker",
    "family_b3",
    "target_archive_tag",
    "target_pcx_name",
    "target_branch_key",
    "renderer_best_mode",
    "renderer_best_extra",
    "renderer_best_score",
    "target_best_source",
    "target_best_start",
    "target_best_mode",
    "target_best_score",
    "target_best_filled",
    "target_best_final_y_128",
    "target_best_final_y_160",
    "target_best_score_delta_vs_renderer",
    "target_best_preview_path",
    "sheet_path",
    "visual_status",
    "next_action",
]

FAMILY_FIELDNAMES = [
    "archive_tag",
    "pcx_name",
    "is_target",
    "payload_len",
    "marker_pos",
    "prologue_family",
    "prologue_source",
    "prologue_mode",
    "prologue_width",
    "prologue_start",
    "prologue_start_minus_marker",
    "choice_source",
    "choice_mode",
    "choice_extra",
    "choice_start",
    "choice_score",
    "head16_hex",
    "u16_0",
    "u16_2",
    "u16_4",
    "u16_6",
    "u16_8",
    "u16_10",
    "u16_12",
    "u16_14",
]

CANDIDATE_FIELDNAMES = [
    "rank",
    "archive_tag",
    "pcx_name",
    "is_target",
    "source",
    "start",
    "marker_extra",
    "mode",
    "width",
    "height",
    "score",
    "score_delta_vs_row_baseline",
    "filled_ratio",
    "unique_colors",
    "final_x",
    "final_y",
    "preview_path",
]


def read_csv(path: Path, *, delimiter: str = ",") -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter=delimiter))


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
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in value)


def first_marker_offset(payload: bytes, search: int) -> int | None:
    best = None
    for marker in MARKERS:
        pos = payload[:search].find(marker)
        if pos >= 0 and (best is None or pos < best):
            best = pos
    return best


def word_at(payload: bytes, offset: int) -> int:
    if 0 <= offset <= len(payload) - 2:
        return int.from_bytes(payload[offset : offset + 2], "little")
    return 0


def parse_family_b3(path_rows: list[dict[str, str]]) -> tuple[str, int]:
    first = path_rows[0] if path_rows else {}
    family = first.get("prologue_family", "")
    match = re.search(r"marker_([0-9a-fA-F]{4})_b3_(\d+)_", family)
    if match:
        return match.group(1).lower(), int(match.group(2))
    key = first.get("branch_key", "")
    match = re.search(r"0x[0-9a-fA-F]+_0x([0-9a-fA-F]+)", key)
    return "2a30", int(match.group(1), 16) if match else 0


def key_for(level: str, name: str) -> tuple[str, str]:
    return level, name.lower()


def read_tsv_lookup(path: Path, level_field: str, name_field: str) -> dict[tuple[str, str], dict[str, str]]:
    rows = {}
    for row in read_csv(path, delimiter="\t"):
        rows[key_for(row.get(level_field, ""), row.get(name_field, ""))] = row
    return rows


def target_keys(path_rows: list[dict[str, str]]) -> set[tuple[str, str]]:
    return {key_for(row.get("archive_tag", ""), row.get("pcx_name", "")) for row in path_rows}


def family_feature_rows(features_path: Path, marker: str, b3: int) -> list[dict[str, str]]:
    rows = []
    for row in read_csv(features_path, delimiter="\t"):
        if row.get("marker", "").lower() == marker.lower() and int_text(row.get("b3")) == b3:
            rows.append(row)
    return rows


def catalog_payloads(catalog: Path, family_rows: list[dict[str, str]]) -> dict[tuple[str, str], bytes]:
    wanted = {key_for(row.get("level", ""), row.get("name", "")) for row in family_rows}
    output: dict[tuple[str, str], bytes] = {}
    for row in load_rows(catalog):
        if row.get("ext") != ".pcx" or row.get("name", "").lower() == "palette.pcx":
            continue
        key = key_for(row["source_path"].parent.name, row.get("name", ""))
        if key in wanted:
            output[key] = bounded_payload(row)
    return output


def build_family_rows(
    feature_rows: list[dict[str, str]],
    payloads: dict[tuple[str, str], bytes],
    prologues: dict[tuple[str, str], dict[str, str]],
    choices: dict[tuple[str, str], dict[str, str]],
    targets: set[tuple[str, str]],
    marker_search: int,
) -> list[dict[str, str]]:
    rows = []
    for feature in sorted(feature_rows, key=lambda row: (row.get("level", ""), row.get("name", ""))):
        key = key_for(feature.get("level", ""), feature.get("name", ""))
        payload = payloads.get(key, b"")
        marker = first_marker_offset(payload, marker_search)
        prologue = prologues.get(key, {})
        choice = choices.get(key, {})
        rows.append(
            {
                "archive_tag": key[0],
                "pcx_name": feature.get("name", ""),
                "is_target": "yes" if key in targets else "no",
                "payload_len": str(len(payload)),
                "marker_pos": "" if marker is None else str(marker),
                "prologue_family": prologue.get("family", ""),
                "prologue_source": prologue.get("source", ""),
                "prologue_mode": prologue.get("mode", ""),
                "prologue_width": prologue.get("width", ""),
                "prologue_start": prologue.get("start", ""),
                "prologue_start_minus_marker": prologue.get("start_minus_marker", ""),
                "choice_source": choice.get("source", ""),
                "choice_mode": choice.get("mode", ""),
                "choice_extra": choice.get("extra", ""),
                "choice_start": choice.get("start", ""),
                "choice_score": choice.get("score", ""),
                "head16_hex": payload[:16].hex(" "),
                "u16_0": str(word_at(payload, 0)),
                "u16_2": str(word_at(payload, 2)),
                "u16_4": str(word_at(payload, 4)),
                "u16_6": str(word_at(payload, 6)),
                "u16_8": str(word_at(payload, 8)),
                "u16_10": str(word_at(payload, 10)),
                "u16_12": str(word_at(payload, 12)),
                "u16_14": str(word_at(payload, 14)),
            }
        )
    return rows


def candidate_starts(row: dict[str, str], payload_len: int) -> list[tuple[str, int, str]]:
    marker = int_text(row.get("marker_pos"), -1)
    starts: list[tuple[str, int, str]] = []
    for field, label in (("prologue_start", "prologue_start"), ("choice_start", "choice_start")):
        value = row.get(field, "")
        if value:
            starts.append((label, int_text(value), ""))
    if marker >= 0:
        for extra in (13, 17, 20, 24, 28, 32, 36, 40, 44, 48, 52, 60, 64):
            starts.append(("marker_extra_probe", marker + extra, str(extra)))
        if row.get("choice_extra"):
            extra = int_text(row.get("choice_extra"))
            starts.append(("choice_extra", marker + extra, str(extra)))
    for value in (16, 17, 20, 23, 24, 28, 30, 32, 35, 40, 44, 48, 52, 64, 67):
        starts.append(("absolute_probe", value, ""))
    seen: set[tuple[str, int, str]] = set()
    output = []
    for source, start, extra in starts:
        item = (source, start, extra)
        if item in seen or not (0 <= start < payload_len):
            continue
        seen.add(item)
        output.append(item)
    return output


def candidate_modes(row: dict[str, str]) -> list[str]:
    modes = [
        row.get("choice_mode", ""),
        row.get("prologue_mode", ""),
        "filter",
        "cmd20_skip4_markerknown",
        "cmd20_sig_skip4_markerknown",
        "op4_small_skip2",
        "op4_cmd20_skip4_markerknown",
    ]
    seen: set[str] = set()
    output = []
    for mode in modes:
        if mode and mode not in seen:
            seen.add(mode)
            output.append(mode)
    return output


def score_pixels(pixels: bytes, width: int, height: int) -> tuple[float, float]:
    score = row_score(pixels, width, height)
    filled = sum(1 for value in pixels if value) / max(1, len(pixels))
    return float(score) if score is not None else 999999.0, filled


def build_candidates(
    family_rows: list[dict[str, str]],
    payloads: dict[tuple[str, str], bytes],
    palette_path: Path,
    output_dir: Path,
    width: int,
    height: int,
    low: int,
    high: int,
    top_per_row: int,
) -> tuple[list[dict[str, str]], list[tuple[str, object]]]:
    palette = read_palette(palette_path)
    all_rows: list[dict[str, str]] = []
    preview_entries: list[tuple[str, object]] = []
    by_row_candidates: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)

    for row in family_rows:
        key = key_for(row.get("archive_tag", ""), row.get("pcx_name", ""))
        payload = payloads.get(key, b"")
        if not payload:
            continue
        row_baseline = None
        for source, start, marker_extra in candidate_starts(row, len(payload)):
            for mode in candidate_modes(row):
                pixels, stats = decode_span(
                    payload[start:],
                    width,
                    height,
                    mode,
                    low,
                    high,
                    return_stats=True,
                )
                score, filled = score_pixels(pixels, width, height)
                candidate = {
                    "archive_tag": key[0],
                    "pcx_name": row.get("pcx_name", ""),
                    "is_target": row.get("is_target", ""),
                    "source": source,
                    "start": start,
                    "marker_extra": marker_extra,
                    "mode": mode,
                    "width": width,
                    "height": height,
                    "score": score,
                    "filled_ratio": filled,
                    "unique_colors": len(set(pixels)),
                    "final_x": int_text(stats.get("final_x")),
                    "final_y": int_text(stats.get("final_y")),
                    "_pixels": pixels,
                }
                if row_baseline is None:
                    row_baseline = score
                if source in {"choice_start", "choice_extra"} and row.get("choice_mode") == mode:
                    row_baseline = score
                by_row_candidates[key].append(candidate)

        baseline = row_baseline if row_baseline is not None else 0.0
        ranked = sorted(
            by_row_candidates[key],
            key=lambda candidate: (
                float(candidate["score"]),
                -float(candidate["filled_ratio"]),
                int(candidate["start"]),
                str(candidate["mode"]),
            ),
        )[:top_per_row]
        for rank, candidate in enumerate(ranked, start=1):
            out_dir = output_dir / "previews" / safe_name(str(candidate["archive_tag"]))
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = (
                out_dir
                / f"{rank:02d}_{safe_name(str(candidate['pcx_name']))}_s{candidate['start']}_{safe_name(str(candidate['mode']))}.png"
            )
            image = render_indexed(candidate["_pixels"], width, height, palette)
            image.save(out_path)
            preview_entries.append(
                (
                    f"{candidate['archive_tag']}/{candidate['pcx_name']} r{rank} s{candidate['start']} {candidate['mode']}",
                    image,
                )
            )
            all_rows.append(
                {
                    "rank": str(rank),
                    "archive_tag": str(candidate["archive_tag"]),
                    "pcx_name": str(candidate["pcx_name"]),
                    "is_target": str(candidate["is_target"]),
                    "source": str(candidate["source"]),
                    "start": str(candidate["start"]),
                    "marker_extra": str(candidate["marker_extra"]),
                    "mode": str(candidate["mode"]),
                    "width": str(width),
                    "height": str(height),
                    "score": f"{float(candidate['score']):.4f}",
                    "score_delta_vs_row_baseline": f"{float(candidate['score']) - baseline:.4f}",
                    "filled_ratio": f"{float(candidate['filled_ratio']):.4f}",
                    "unique_colors": str(candidate["unique_colors"]),
                    "final_x": str(candidate["final_x"]),
                    "final_y": str(candidate["final_y"]),
                    "preview_path": str(out_path),
                }
            )
    all_rows.sort(
        key=lambda row: (
            row.get("is_target") != "yes",
            row.get("archive_tag", ""),
            row.get("pcx_name", ""),
            int_text(row.get("rank")),
        )
    )
    return all_rows, preview_entries


def make_sheet(entries: list[tuple[str, object]], out_path: Path, columns: int, thumb_size: int) -> None:
    from PIL import Image, ImageDraw

    label_h = 20
    rows = (len(entries) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * thumb_size, max(1, rows) * (thumb_size + label_h)), (18, 18, 18))
    draw = ImageDraw.Draw(sheet)
    for index, (label, image) in enumerate(entries):
        x = (index % columns) * thumb_size
        y = (index // columns) * (thumb_size + label_h)
        thumb = image.copy()
        thumb.thumbnail((thumb_size, thumb_size), Image.Resampling.NEAREST)
        sheet.paste(thumb.convert("RGB"), (x + (thumb_size - thumb.width) // 2, y))
        draw.text((x + 2, y + thumb_size), label[:30], fill=(230, 230, 230))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    path = Path(path_text)
    try:
        relative = path.relative_to(base_dir)
    except ValueError:
        relative = Path(os.path.relpath(path, base_dir))
    return relative.as_posix()


def render_table(rows: list[dict[str, str]], columns: list[str]) -> str:
    head = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    body = []
    for row in rows:
        cells = "".join(f"<td>{html.escape(row.get(column, ''))}</td>" for column in columns)
        body.append(f"<tr>{cells}</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def build_summary(
    path_rows: list[dict[str, str]],
    family_rows: list[dict[str, str]],
    candidates: list[dict[str, str]],
    payloads: dict[tuple[str, str], bytes],
    renderer_summary: dict[str, str],
    marker: str,
    b3: int,
    sheet_path: Path,
    issues: list[str],
    width: int,
    height_probe: int,
    low: int,
    high: int,
) -> dict[str, str]:
    target_candidates = [row for row in candidates if row.get("is_target") == "yes"]
    best = min(target_candidates, key=lambda row: float_text(row.get("score")), default={})
    target_row = next((row for row in family_rows if row.get("is_target") == "yes"), {})
    best_final_y_160 = ""
    if best and target_row:
        payload_key = key_for(best.get("archive_tag", ""), best.get("pcx_name", ""))
        payload = payloads.get(payload_key, b"")
        if payload:
            _pixels, stats = decode_span(
                payload[int_text(best.get("start")) :],
                width,
                height_probe,
                best.get("mode", ""),
                low,
                high,
                return_stats=True,
            )
            best_final_y_160 = str(int_text(stats.get("final_y")))
    renderer_best_score = float_text(renderer_summary.get("best_score"))
    best_score = float_text(best.get("score"))
    delta = best_score - renderer_best_score if best and renderer_summary else 0.0
    if issues:
        visual_status = "blocked_probe_issues"
        next_action = "fix bounded 0x2a30 branch family probe inputs"
    elif not target_candidates:
        visual_status = "blocked_no_target_candidates"
        next_action = "fix bounded 0x2a30 branch family candidate generation"
    else:
        visual_status = "blocked_bounded_family_support_still_noisy"
        next_action = (
            f"derive guarded bounded-family renderer grammar for {marker}/b3={b3}; "
            f"target best {best.get('source', '')} start{best.get('start', '')} "
            f"{best.get('mode', '')} remains review-blocked"
        )
    target_keys_count = sum(1 for row in family_rows if row.get("is_target") == "yes")
    return {
        "scope": "total",
        "target_branch_rows": str(len(path_rows)),
        "family_rows": str(len(family_rows)),
        "family_target_rows": str(target_keys_count),
        "family_support_rows": str(len(family_rows) - target_keys_count),
        "candidate_rows": str(len(candidates)),
        "target_candidate_rows": str(len(target_candidates)),
        "preview_rows": str(sum(1 for row in candidates if row.get("preview_path"))),
        "ranked_preview_rows": str(len(candidates)),
        "issue_rows": str(len(issues)),
        "family_marker": marker,
        "family_b3": str(b3),
        "target_archive_tag": best.get("archive_tag", ""),
        "target_pcx_name": best.get("pcx_name", ""),
        "target_branch_key": path_rows[0].get("branch_key", "") if path_rows else "",
        "renderer_best_mode": renderer_summary.get("best_mode", ""),
        "renderer_best_extra": renderer_summary.get("best_extra", ""),
        "renderer_best_score": renderer_summary.get("best_score", ""),
        "target_best_source": best.get("source", ""),
        "target_best_start": best.get("start", ""),
        "target_best_mode": best.get("mode", ""),
        "target_best_score": best.get("score", ""),
        "target_best_filled": best.get("filled_ratio", ""),
        "target_best_final_y_128": best.get("final_y", ""),
        "target_best_final_y_160": best_final_y_160,
        "target_best_score_delta_vs_renderer": f"{delta:.4f}",
        "target_best_preview_path": best.get("preview_path", ""),
        "sheet_path": str(sheet_path),
        "visual_status": visual_status,
        "next_action": next_action,
    }


def build_html(
    summary: dict[str, str],
    family_rows: list[dict[str, str]],
    candidates: list[dict[str, str]],
    issues: list[str],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "family": family_rows, "candidates": candidates, "issues": issues}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("family.csv", output_dir / "family.csv"),
            ("candidates.csv", output_dir / "candidates.csv"),
            ("sheet.png", output_dir / "sheet.png"),
        )
    )
    cards = []
    for row in candidates[:24]:
        href = relative_href(row.get("preview_path", ""), output_dir)
        cards.append(
            "<figure>"
            f'<a href="{html.escape(href)}"><img src="{html.escape(href)}" alt=""></a>'
            f"<figcaption>{html.escape(row.get('archive_tag', ''))}/{html.escape(row.get('pcx_name', ''))} "
            f"s{html.escape(row.get('start', ''))} {html.escape(row.get('mode', ''))}<br>"
            f"score {html.escape(row.get('score', ''))}</figcaption>"
            "</figure>"
        )
    issue_html = ""
    if issues:
        issue_html = "<h2>Issues</h2><ul>" + "".join(f"<li>{html.escape(issue)}</li>" for issue in issues) + "</ul>"
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
.muted {{ color: var(--muted); }}
a {{ color: var(--accent); text-decoration: none; margin-right: 10px; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(170px, 1fr)); gap: 12px; margin-top: 12px; }}
figure {{ margin: 0; background: var(--panel); border: 1px solid var(--line); padding: 8px; }}
img {{ width: 100%; height: 150px; object-fit: contain; image-rendering: pixelated; background: #08090a; }}
figcaption {{ color: var(--muted); font-size: 12px; overflow-wrap: anywhere; }}
table {{ width: 100%; border-collapse: collapse; background: var(--panel); border: 1px solid var(--line); margin-top: 10px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; font-size: 12px; }}
th {{ color: var(--muted); background: #20262b; }}
td {{ max-width: 520px; overflow-wrap: anywhere; }}
</style>
</head>
<body>
<main>
<h1>{html.escape(title)}</h1>
<p class="muted">Bounded-payload comparison for the current shifted 0x2a30 branch family. Outputs are evidence, not promoted assets.</p>
<p>{links}</p>
<h2>Summary</h2>
{render_table([summary], SUMMARY_FIELDNAMES)}
{issue_html}
<h2>Top Previews</h2>
<div class="grid">{''.join(cards)}</div>
<h2>Family Rows</h2>
{render_table(family_rows, FAMILY_FIELDNAMES)}
<h2>Candidates</h2>
{render_table(candidates, CANDIDATE_FIELDNAMES)}
</main>
<script>const TEX_LARGE_SHIFTED_2A30_BRANCH_BOUNDED_FAMILY_PROBE = {data_json};</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[str]]:
    args.output.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    path_rows = read_csv(args.decoder_paths)
    if not path_rows:
        family_rows: list[dict[str, str]] = []
        candidates: list[dict[str, str]] = []
        marker = ""
        b3 = 0
        renderer_summary = (read_csv(args.renderer_summary) or [{}])[0]
        sheet_path = args.output / "sheet.png"
        summary = build_summary(
            path_rows,
            family_rows,
            candidates,
            {},
            renderer_summary,
            marker,
            b3,
            sheet_path,
            issues,
            args.width,
            args.height_probe,
            args.low,
            args.high,
        )
        write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
        write_csv(args.output / "family.csv", FAMILY_FIELDNAMES, family_rows)
        write_csv(args.output / "candidates.csv", CANDIDATE_FIELDNAMES, candidates)
        (args.output / "index.html").write_text(
            build_html(summary, family_rows, candidates, issues, args.output, args.title),
            encoding="utf-8",
        )
        return summary, family_rows, candidates, issues
    if OPTIONAL_IMPORT_ERROR is not None:
        raise OPTIONAL_IMPORT_ERROR
    if not path_rows:
        issues.append("missing_decoder_path_rows")
    marker, b3 = parse_family_b3(path_rows)
    features = family_feature_rows(args.features, marker, b3)
    if not features:
        issues.append(f"missing_family_feature_rows:{marker}/b3={b3}")
    targets = target_keys(path_rows)
    payloads = catalog_payloads(args.catalog, features)
    prologues = read_tsv_lookup(args.prologue_families, "level", "name")
    choices = read_tsv_lookup(args.choices, "level", "name")
    family_rows = build_family_rows(features, payloads, prologues, choices, targets, args.marker_search)
    renderer_summary = (read_csv(args.renderer_summary) or [{}])[0]
    candidates, preview_entries = build_candidates(
        family_rows,
        payloads,
        args.palette,
        args.output,
        args.width,
        args.height,
        args.low,
        args.high,
        args.top_per_row,
    )
    sheet_path = args.output / "sheet.png"
    make_sheet(preview_entries, sheet_path, args.sheet_columns, args.thumb_size)
    summary = build_summary(
        path_rows,
        family_rows,
        candidates,
        payloads,
        renderer_summary,
        marker,
        b3,
        sheet_path,
        issues,
        args.width,
        args.height_probe,
        args.low,
        args.high,
    )
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "family.csv", FAMILY_FIELDNAMES, family_rows)
    write_csv(args.output / "candidates.csv", CANDIDATE_FIELDNAMES, candidates)
    (args.output / "index.html").write_text(
        build_html(summary, family_rows, candidates, issues, args.output, args.title),
        encoding="utf-8",
    )
    return summary, family_rows, candidates, issues


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe bounded payload support for shifted 0x2a30 branch family.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--decoder-paths", type=Path, default=DEFAULT_DECODER_PATHS)
    parser.add_argument("--renderer-summary", type=Path, default=DEFAULT_RENDERER_SUMMARY)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--features", type=Path, default=DEFAULT_FEATURES)
    parser.add_argument("--prologue-families", type=Path, default=DEFAULT_PROLOGUE_FAMILIES)
    parser.add_argument("--choices", type=Path, default=DEFAULT_CHOICES)
    parser.add_argument("-p", "--palette", type=Path, default=DEFAULT_PALETTE)
    parser.add_argument("--marker-search", type=int, default=512)
    parser.add_argument("--width", type=int, default=48)
    parser.add_argument("--height", type=int, default=128)
    parser.add_argument("--height-probe", type=int, default=160)
    parser.add_argument("--low", type=lambda value: int(value, 0), default=0x30)
    parser.add_argument("--high", type=lambda value: int(value, 0), default=0xBF)
    parser.add_argument("--top-per-row", type=int, default=8)
    parser.add_argument("--sheet-columns", type=int, default=4)
    parser.add_argument("--thumb-size", type=int, default=160)
    parser.add_argument("--title", default="Lands of Lore II .tex Large Shifted 2a30 Branch Bounded Family Probe")
    args = parser.parse_args()

    summary, family_rows, candidates, issues = write_report(args)
    print(f"Family rows: {summary['family_rows']}")
    print(f"Support rows: {summary['family_support_rows']}")
    print(f"Candidate rows: {summary['candidate_rows']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"Visual status: {summary['visual_status']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")
    if candidates:
        print(
            "Target best: "
            f"{summary['target_archive_tag']}/{summary['target_pcx_name']} "
            f"{summary['target_best_source']} start{summary['target_best_start']} "
            f"{summary['target_best_mode']} score {summary['target_best_score']}"
        )
    if issues:
        print("Issues: " + "; ".join(issues))
    _ = family_rows


if __name__ == "__main__":
    main()
