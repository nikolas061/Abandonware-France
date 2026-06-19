#!/usr/bin/env python3
"""Render focused variants for shifted 0x2a30 branch decoder paths."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
from pathlib import Path

from export_shp import read_palette
from export_te_span_previews import make_sheet, render_indexed, source_payload
from probe_te_span_decode import decode_span
from score_te_raw_layouts import load_rows, row_score


DEFAULT_OUTPUT = Path("output/tex_large_shifted_2a30_branch_renderer_probe")
DEFAULT_DECODER_PATHS = Path("output/tex_large_shifted_2a30_branch_decoder_path_probe/paths.csv")
DEFAULT_ALIGNMENTS = Path("output/tex_large_shifted_2a30_branch_decoder_path_probe/alignments.csv")
DEFAULT_CATALOG = Path("reports/te_resources.tsv")
DEFAULT_PALETTE = Path("extracted/LOCAL/7231c8f9.pal")

DEFAULT_MODES = [
    "filter",
    "cmd20_skip4",
    "cmd20_skip4_markerpair",
    "cmd20_skip4_markerknown",
    "cmd20_skip4_markerknownadv",
    "cmd20_skip4_markerknownsymadv",
    "cmd20_skip4_markersymadv",
    "cmd20_high_arg2_skip4",
    "cmd20_high_arg2_skip4_markerknown",
    "cmd20_sig_skip4",
    "cmd20_sig_skip4_markerknown",
    "op4_cmd20_skip4",
    "op4_cmd20_skip4_markerknown",
    "op4_cmd20_sig_skip4",
    "op4_cmd20_sig_skip4_markerknown",
    "cmd20_arg2_f8_safe_dy_skip4",
    "cmd20_arg2_f8_safe_dy_skip4_markerknown",
    "cmd20_arg2_fc_safe_dy_skip4",
    "cmd20_arg2_fc_safe_dy_skip4_markerknown",
    "op4_cmd20_arg2_f8_safe_dy_skip4",
    "op4_cmd20_arg2_f8_safe_dy_skip4_markerknown",
    "op4_cmd20_arg2_fc_safe_dy_skip4",
    "op4_cmd20_arg2_fc_safe_dy_skip4_markerknown",
]

SUMMARY_FIELDNAMES = [
    "scope",
    "branch_rows",
    "candidate_rows",
    "mode_rows",
    "extra_rows",
    "preview_rows",
    "ranked_preview_rows",
    "issue_rows",
    "best_archive_tag",
    "best_pcx_name",
    "best_branch_key",
    "baseline_mode",
    "baseline_extra",
    "baseline_score",
    "best_mode",
    "best_extra",
    "best_score",
    "best_score_delta",
    "best_filled",
    "best_changed_ratio",
    "best_unique_colors",
    "best_preview_path",
    "sheet_path",
    "visual_status",
    "next_action",
]

CANDIDATE_FIELDNAMES = [
    "rank",
    "archive_tag",
    "pcx_name",
    "branch_key",
    "mode",
    "extra",
    "width",
    "height",
    "raw_score",
    "score",
    "score_delta",
    "filled_ratio",
    "changed_ratio",
    "unique_colors",
    "overdraw",
    "final_x",
    "final_y",
    "is_baseline",
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


def unique_ordered(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            output.append(value)
    return output


def candidate_modes(choice_mode: str, requested: list[str] | None = None) -> list[str]:
    modes = list(requested or DEFAULT_MODES)
    if choice_mode:
        modes.insert(0, choice_mode)
    return unique_ordered(modes)


def candidate_extras(
    choice_extra: int,
    oracle_extra: int,
    alignments: list[dict[str, str]],
    requested: list[int] | None = None,
) -> list[int]:
    extras = set(requested if requested is not None else range(20, 65, 4))
    extras.add(choice_extra)
    extras.add(oracle_extra)
    for row in alignments:
        low = int_text(row.get("field16_low_dec"))
        if low:
            extras.add(max(0, low // 2))
            extras.add(max(0, (low // 2) & ~3))
    return sorted(extra for extra in extras if 0 <= extra <= 96)


def visible_ratio(pixels: bytes) -> float:
    return sum(1 for pixel in pixels if pixel) / max(1, len(pixels))


def changed_ratio(pixels: bytes, baseline: bytes) -> float:
    if not pixels or not baseline:
        return 0.0
    total = min(len(pixels), len(baseline))
    return sum(1 for index in range(total) if pixels[index] != baseline[index]) / max(1, total)


def preview_path(output_dir: Path, row: dict[str, str], rank: int, mode: str, extra: int) -> Path:
    archive = row.get("archive_tag", "")
    name = row.get("pcx_name", "")
    out_dir = output_dir / "previews" / safe_name(archive)
    return out_dir / f"{rank:03d}_{safe_name(mode)}_extra{extra}_{safe_name(name)}.png"


def load_catalog_by_key(catalog: Path, path_rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    output: dict[tuple[str, str], dict[str, str]] = {}
    for path_row in path_rows:
        archive = path_row.get("archive_tag", "")
        name = path_row.get("pcx_name", "")
        rows = list(load_rows(catalog, archive, [name]))
        if rows:
            output[(archive, name.lower())] = rows[0]
    return output


def render_variant(
    catalog_row: dict[str, str],
    mode: str,
    extra: int,
    width: int,
    height: int,
    limit: int,
    marker_search: int,
    low: int,
    high: int,
) -> tuple[bytes, dict[str, float | int]]:
    payload = source_payload(catalog_row, 0, limit, True, extra, marker_search)
    decoded, stats = decode_span(payload, width, height, mode, low, high, return_stats=True)
    return decoded, stats


def score_pixels(pixels: bytes, width: int, height: int, min_filled: float) -> tuple[float, float]:
    raw = row_score(pixels, width, height)
    score = float(raw) if raw is not None else 999999.0
    filled = visible_ratio(pixels)
    if filled < min_filled:
        score += (min_filled - filled) * 250.0
    return float(raw) if raw is not None else score, score


def build_candidates(
    path_rows: list[dict[str, str]],
    alignments: list[dict[str, str]],
    catalog: Path,
    palette_path: Path,
    output_dir: Path,
    modes_arg: list[str] | None,
    extras_arg: list[int] | None,
    limit: int,
    marker_search: int,
    low: int,
    high: int,
    min_filled: float,
) -> tuple[list[dict[str, str]], list[tuple[str, object]], list[str]]:
    palette = read_palette(palette_path)
    catalog_rows = load_catalog_by_key(catalog, path_rows)
    issues: list[str] = []
    candidates: list[dict[str, object]] = []
    for path_row in path_rows:
        archive = path_row.get("archive_tag", "")
        name = path_row.get("pcx_name", "")
        key = (archive, name.lower())
        catalog_row = catalog_rows.get(key)
        if catalog_row is None:
            issues.append(f"missing_catalog_row:{archive}/{name}")
            continue
        width = int_text(path_row.get("choice_width"), 48)
        height = int_text(path_row.get("choice_height"), 128)
        choice_mode = path_row.get("choice_mode", "")
        choice_extra = int_text(path_row.get("choice_extra"), int_text(path_row.get("oracle_extra"), 32))
        oracle_extra = int_text(path_row.get("oracle_extra"), choice_extra)
        row_alignments = [
            row
            for row in alignments
            if row.get("archive_tag") == archive and row.get("pcx_name", "").lower() == name.lower()
        ]
        baseline_pixels, baseline_stats = render_variant(
            catalog_row, choice_mode, choice_extra, width, height, limit, marker_search, low, high
        )
        _, baseline_score = score_pixels(baseline_pixels, width, height, min_filled)
        extras = candidate_extras(choice_extra, oracle_extra, row_alignments, extras_arg)
        for mode in candidate_modes(choice_mode, modes_arg):
            for extra in extras:
                pixels, stats = render_variant(catalog_row, mode, extra, width, height, limit, marker_search, low, high)
                raw_score, score = score_pixels(pixels, width, height, min_filled)
                candidates.append(
                    {
                        "archive_tag": archive,
                        "pcx_name": name,
                        "branch_key": path_row.get("branch_key", ""),
                        "mode": mode,
                        "extra": extra,
                        "width": width,
                        "height": height,
                        "raw_score": raw_score,
                        "score": score,
                        "score_delta": score - baseline_score,
                        "filled_ratio": visible_ratio(pixels),
                        "changed_ratio": changed_ratio(pixels, baseline_pixels),
                        "unique_colors": len(set(pixels)),
                        "overdraw": float_text(stats.get("overdraw")),
                        "final_x": int_text(stats.get("final_x")),
                        "final_y": int_text(stats.get("final_y")),
                        "is_baseline": "yes" if mode == choice_mode and extra == choice_extra else "no",
                        "_pixels": pixels,
                    }
                )
        if not choice_mode:
            issues.append(f"missing_choice_mode:{archive}/{name}")
        if not path_row.get("choice_preview_exists"):
            issues.append(f"missing_choice_preview_state:{archive}/{name}")
        _ = baseline_stats

    candidates.sort(
        key=lambda row: (
            float(row["score"]),
            -float(row["filled_ratio"]),
            int(row["extra"]),
            str(row["mode"]),
        )
    )
    sheet_entries: list[tuple[str, object]] = []
    csv_rows: list[dict[str, str]] = []
    for rank, candidate in enumerate(candidates, start=1):
        out_path = preview_path(output_dir, candidate, rank, str(candidate["mode"]), int(candidate["extra"]))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        image = render_indexed(candidate["_pixels"], int(candidate["width"]), int(candidate["height"]), palette)
        image.save(out_path)
        if rank <= 32 or candidate["is_baseline"] == "yes":
            label = f"r{rank} e{candidate['extra']} {candidate['mode']}"
            sheet_entries.append((label, image))
        csv_rows.append(
            {
                "rank": str(rank),
                "archive_tag": str(candidate["archive_tag"]),
                "pcx_name": str(candidate["pcx_name"]),
                "branch_key": str(candidate["branch_key"]),
                "mode": str(candidate["mode"]),
                "extra": str(candidate["extra"]),
                "width": str(candidate["width"]),
                "height": str(candidate["height"]),
                "raw_score": f"{float(candidate['raw_score']):.4f}",
                "score": f"{float(candidate['score']):.4f}",
                "score_delta": f"{float(candidate['score_delta']):.4f}",
                "filled_ratio": f"{float(candidate['filled_ratio']):.4f}",
                "changed_ratio": f"{float(candidate['changed_ratio']):.4f}",
                "unique_colors": str(candidate["unique_colors"]),
                "overdraw": f"{float(candidate['overdraw']):.4f}",
                "final_x": str(candidate["final_x"]),
                "final_y": str(candidate["final_y"]),
                "is_baseline": str(candidate["is_baseline"]),
                "preview_path": str(out_path),
            }
        )
    return csv_rows, sheet_entries, issues


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
    candidates: list[dict[str, str]],
    sheet_path: Path,
    issues: list[str],
    min_clear_improvement: float,
) -> dict[str, str]:
    best = candidates[0] if candidates else {}
    baseline = next((row for row in candidates if row.get("is_baseline") == "yes"), {})
    score_delta = float_text(best.get("score_delta"))
    if issues:
        visual_status = "blocked_probe_issues"
        next_action = "fix shifted 0x2a30 branch renderer probe inputs"
    elif not candidates:
        visual_status = "blocked_no_candidates"
        next_action = "fix shifted 0x2a30 branch renderer candidate generation"
    elif score_delta <= -min_clear_improvement:
        visual_status = "candidate_review_ready"
        next_action = (
            f"review shifted 0x2a30 branch renderer candidate {best.get('mode', '')} "
            f"extra{best.get('extra', '')} before promotion"
        )
    else:
        visual_status = "blocked_no_clear_non_noisy_renderer"
        next_action = (
            "derive renderer grammar beyond tested shifted 0x2a30 branch variants; "
            f"best {best.get('mode', '')} extra{best.get('extra', '')} "
            f"only improves score by {abs(score_delta):.4f}"
        )
    return {
        "scope": "total",
        "branch_rows": str(len(path_rows)),
        "candidate_rows": str(len(candidates)),
        "mode_rows": str(len({row.get("mode", "") for row in candidates})),
        "extra_rows": str(len({row.get("extra", "") for row in candidates})),
        "preview_rows": str(sum(1 for row in candidates if row.get("preview_path"))),
        "ranked_preview_rows": str(min(32, len(candidates)) + (1 if baseline and int_text(baseline.get("rank")) > 32 else 0)),
        "issue_rows": str(len(issues)),
        "best_archive_tag": best.get("archive_tag", ""),
        "best_pcx_name": best.get("pcx_name", ""),
        "best_branch_key": best.get("branch_key", ""),
        "baseline_mode": baseline.get("mode", ""),
        "baseline_extra": baseline.get("extra", ""),
        "baseline_score": baseline.get("score", ""),
        "best_mode": best.get("mode", ""),
        "best_extra": best.get("extra", ""),
        "best_score": best.get("score", ""),
        "best_score_delta": best.get("score_delta", ""),
        "best_filled": best.get("filled_ratio", ""),
        "best_changed_ratio": best.get("changed_ratio", ""),
        "best_unique_colors": best.get("unique_colors", ""),
        "best_preview_path": best.get("preview_path", ""),
        "sheet_path": str(sheet_path),
        "visual_status": visual_status,
        "next_action": next_action,
    }


def build_html(
    summary: dict[str, str],
    candidates: list[dict[str, str]],
    issues: list[str],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "candidates": candidates[:64], "issues": issues}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("candidates.csv", output_dir / "candidates.csv"),
            ("sheet.png", output_dir / "sheet.png"),
        )
    )
    cards = []
    for row in candidates[:12]:
        href = relative_href(row.get("preview_path", ""), output_dir)
        cards.append(
            "<figure>"
            f'<a href="{html.escape(href)}"><img src="{html.escape(href)}" alt=""></a>'
            f"<figcaption>#{html.escape(row.get('rank', ''))} "
            f"{html.escape(row.get('mode', ''))} extra{html.escape(row.get('extra', ''))}<br>"
            f"score {html.escape(row.get('score', ''))} delta {html.escape(row.get('score_delta', ''))}</figcaption>"
            "</figure>"
        )
    issue_html = ""
    if issues:
        issue_items = "".join(f"<li>{html.escape(issue)}</li>" for issue in issues)
        issue_html = f"<h2>Issues</h2><ul>{issue_items}</ul>"
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
img {{ width: 100%; height: 160px; object-fit: contain; image-rendering: pixelated; background: #08090a; }}
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
<p class="muted">Focused render variants for shifted 0x2a30 branch rows. Outputs are review evidence, not promoted assets.</p>
<p>{links}</p>
<h2>Summary</h2>
{render_table([summary], SUMMARY_FIELDNAMES)}
{issue_html}
<h2>Top Previews</h2>
<div class="grid">{''.join(cards)}</div>
<h2>Candidates</h2>
{render_table(candidates[:64], CANDIDATE_FIELDNAMES)}
</main>
<script>const TEX_LARGE_SHIFTED_2A30_BRANCH_RENDERER_PROBE = {data_json};</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> tuple[dict[str, str], list[dict[str, str]], list[str]]:
    args.output.mkdir(parents=True, exist_ok=True)
    paths = read_csv(args.decoder_paths)
    alignments = read_csv(args.alignments)
    candidates, sheet_entries, issues = build_candidates(
        paths,
        alignments,
        args.catalog,
        args.palette,
        args.output,
        args.modes,
        args.extras,
        args.limit,
        args.marker_search,
        args.low,
        args.high,
        args.min_filled,
    )
    sheet_path = args.output / "sheet.png"
    make_sheet(sheet_entries, sheet_path, args.sheet_columns, args.thumb_size)
    summary = build_summary(paths, candidates, sheet_path, issues, args.min_clear_improvement)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "candidates.csv", CANDIDATE_FIELDNAMES, candidates)
    (args.output / "index.html").write_text(
        build_html(summary, candidates, issues, args.output, args.title),
        encoding="utf-8",
    )
    return summary, candidates, issues


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe renderer variants for shifted 0x2a30 branch rows.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--decoder-paths", type=Path, default=DEFAULT_DECODER_PATHS)
    parser.add_argument("--alignments", type=Path, default=DEFAULT_ALIGNMENTS)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("-p", "--palette", type=Path, default=DEFAULT_PALETTE)
    parser.add_argument("--modes", nargs="+")
    parser.add_argument("--extras", nargs="+", type=int)
    parser.add_argument("--limit", type=int, default=65536)
    parser.add_argument("--marker-search", type=int, default=512)
    parser.add_argument("--low", type=lambda value: int(value, 0), default=0x30)
    parser.add_argument("--high", type=lambda value: int(value, 0), default=0xBF)
    parser.add_argument("--min-filled", type=float, default=0.25)
    parser.add_argument("--min-clear-improvement", type=float, default=3.0)
    parser.add_argument("--sheet-columns", type=int, default=4)
    parser.add_argument("--thumb-size", type=int, default=160)
    parser.add_argument("--title", default="Lands of Lore II .tex Large Shifted 2a30 Branch Renderer Probe")
    args = parser.parse_args()

    summary, candidates, issues = write_report(args)
    print(f"Branch rows: {summary['branch_rows']}")
    print(f"Candidate rows: {summary['candidate_rows']}")
    print(f"Preview rows: {summary['preview_rows']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"Visual status: {summary['visual_status']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")
    if candidates:
        print(
            "Best: "
            f"{summary['best_archive_tag']}/{summary['best_pcx_name']} "
            f"{summary['best_mode']} extra{summary['best_extra']} score {summary['best_score']}"
        )
    if issues:
        print("Issues: " + "; ".join(issues))


if __name__ == "__main__":
    main()
