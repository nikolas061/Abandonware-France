#!/usr/bin/env python3
"""Replay fixed dy1/shift0 support for shared 0x2700302b reference frontier 6."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
from pathlib import Path

import lolg_tex_large_shared_2700302b_reference_frontier_probe as frontier_probe
import lolg_tex_large_shared_2700302b_reference_spatial_backref_probe as spatial_probe


DEFAULT_OUTPUT = Path("output/tex_large_shared_2700302b_reference_fixed_dy1_replay_probe")
DEFAULT_FRONTIERS = frontier_probe.DEFAULT_FRONTIERS
DEFAULT_COMPARISONS = frontier_probe.DEFAULT_COMPARISONS
DEFAULT_SPATIAL_SUMMARY = Path("output/tex_large_shared_2700302b_reference_spatial_backref_probe/summary.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "target_pixels",
    "target_zero_pixels",
    "target_nonzero_pixels",
    "row_rows",
    "dy",
    "shift",
    "raw_copy_matches",
    "raw_copy_match_ratio",
    "raw_copy_nonzero_matches",
    "raw_copy_nonzero_ratio",
    "zero_source_zero_pixels",
    "zero_source_nonzero_pixels",
    "zero_plus_dy1_matches",
    "zero_plus_dy1_ratio",
    "residual_nonzero_pixels",
    "residual_nonzero_ratio",
    "residual_run_rows",
    "max_residual_run_pixels",
    "spatial_expected_zero_plus_pixels",
    "spatial_expected_gap_pixels",
    "issue_rows",
    "fixed_dy1_replay_verdict",
    "next_action",
]

ROW_FIELDNAMES = [
    "target_y",
    "x_start",
    "x_end",
    "pixels",
    "zero_pixels",
    "nonzero_pixels",
    "source_y",
    "source_x_start",
    "source_x_end",
    "raw_copy_matches",
    "raw_copy_match_ratio",
    "raw_copy_nonzero_matches",
    "raw_copy_nonzero_ratio",
    "zero_source_zero_pixels",
    "zero_source_nonzero_pixels",
    "zero_plus_dy1_matches",
    "zero_plus_dy1_ratio",
    "residual_nonzero_pixels",
    "residual_nonzero_ratio",
    "residual_runs",
]

RESIDUAL_FIELDNAMES = [
    "target_y",
    "x_start",
    "x_end",
    "pixels",
    "target_absolute_start",
    "target_absolute_end",
    "source_y",
    "source_x_start",
    "source_x_end",
    "target_hex_head",
    "source_hex_head",
    "delta_hex_head",
]


def read_summary(path: Path) -> dict[str, str]:
    rows = frontier_probe.read_csv(path)
    return rows[0] if rows else {}


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def int_value(row: dict[str, str], field: str) -> int:
    return frontier_probe.int_value(row, field)


def float_text(value: float) -> str:
    return f"{value:.6f}"


def hex_head(values: bytes, limit: int = 16) -> str:
    return values[:limit].hex()


def delta_head(target: bytes, source: bytes, limit: int = 16) -> str:
    return bytes((left - right) & 0xFF for left, right in zip(target[:limit], source[:limit])).hex()


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    try:
        return os.path.relpath(Path(path_text), base_dir)
    except ValueError:
        return str(path_text)


def build_residual_runs(
    *,
    y: int,
    x_start: int,
    target: bytes,
    source: bytes,
    width: int,
    dy: int,
    shift: int,
) -> list[dict[str, str]]:
    runs: list[dict[str, str]] = []
    run_start: int | None = None
    for index, (target_value, source_value) in enumerate(zip(target, source)):
        is_residual = target_value != 0 and target_value != source_value
        if is_residual and run_start is None:
            run_start = index
        if (not is_residual or index == len(target) - 1) and run_start is not None:
            run_end = index if is_residual and index == len(target) - 1 else index - 1
            target_slice = target[run_start : run_end + 1]
            source_slice = source[run_start : run_end + 1]
            run_x_start = x_start + run_start
            run_x_end = x_start + run_end
            source_x_start = run_x_start + shift
            source_x_end = run_x_end + shift
            runs.append(
                {
                    "target_y": str(y),
                    "x_start": str(run_x_start),
                    "x_end": str(run_x_end),
                    "pixels": str(run_end - run_start + 1),
                    "target_absolute_start": str(y * width + run_x_start),
                    "target_absolute_end": str(y * width + run_x_end),
                    "source_y": str(y - dy),
                    "source_x_start": str(source_x_start),
                    "source_x_end": str(source_x_end),
                    "target_hex_head": hex_head(target_slice),
                    "source_hex_head": hex_head(source_slice),
                    "delta_hex_head": delta_head(target_slice, source_slice),
                }
            )
            run_start = None
    return runs


def analyze_rows(
    pixels: bytes,
    *,
    gap_start: int,
    gap_end: int,
    width: int,
    dy: int,
    shift: int,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    row_rows: list[dict[str, str]] = []
    residual_rows: list[dict[str, str]] = []
    for y, x_start, x_end, target in spatial_probe.row_slices(
        pixels,
        gap_start=gap_start,
        gap_end=gap_end,
        width=width,
    ):
        source = spatial_probe.source_row_window(pixels, width, y - dy, x_start, len(target), shift)
        zero_pixels = target.count(0)
        nonzero_pixels = len(target) - zero_pixels
        raw_copy_matches = sum(1 for left, right in zip(target, source) if left == right)
        raw_copy_nonzero = sum(1 for left, right in zip(target, source) if left != 0 and left == right)
        zero_source_zero = sum(1 for left, right in zip(target, source) if left == 0 and right == 0)
        zero_source_nonzero = sum(1 for left, right in zip(target, source) if left == 0 and right != 0)
        zero_plus = zero_pixels + raw_copy_nonzero
        residual_nonzero = nonzero_pixels - raw_copy_nonzero
        runs = build_residual_runs(
            y=y,
            x_start=x_start,
            target=target,
            source=source,
            width=width,
            dy=dy,
            shift=shift,
        )
        residual_rows.extend(runs)
        row_rows.append(
            {
                "target_y": str(y),
                "x_start": str(x_start),
                "x_end": str(x_end),
                "pixels": str(len(target)),
                "zero_pixels": str(zero_pixels),
                "nonzero_pixels": str(nonzero_pixels),
                "source_y": str(y - dy),
                "source_x_start": str(x_start + shift),
                "source_x_end": str(x_end + shift),
                "raw_copy_matches": str(raw_copy_matches),
                "raw_copy_match_ratio": float_text(raw_copy_matches / len(target) if target else 0.0),
                "raw_copy_nonzero_matches": str(raw_copy_nonzero),
                "raw_copy_nonzero_ratio": float_text(raw_copy_nonzero / nonzero_pixels if nonzero_pixels else 0.0),
                "zero_source_zero_pixels": str(zero_source_zero),
                "zero_source_nonzero_pixels": str(zero_source_nonzero),
                "zero_plus_dy1_matches": str(zero_plus),
                "zero_plus_dy1_ratio": float_text(zero_plus / len(target) if target else 0.0),
                "residual_nonzero_pixels": str(residual_nonzero),
                "residual_nonzero_ratio": float_text(residual_nonzero / nonzero_pixels if nonzero_pixels else 0.0),
                "residual_runs": str(len(runs)),
            }
        )
    return row_rows, residual_rows


def build_summary(
    frontier: dict[str, str],
    row_rows: list[dict[str, str]],
    residual_rows: list[dict[str, str]],
    spatial_summary: dict[str, str],
    *,
    dy: int,
    shift: int,
    issues: list[str],
) -> dict[str, str]:
    target_pixels = sum(int_value(row, "pixels") for row in row_rows)
    target_zero = sum(int_value(row, "zero_pixels") for row in row_rows)
    target_nonzero = sum(int_value(row, "nonzero_pixels") for row in row_rows)
    raw_copy = sum(int_value(row, "raw_copy_matches") for row in row_rows)
    raw_copy_nonzero = sum(int_value(row, "raw_copy_nonzero_matches") for row in row_rows)
    zero_source_zero = sum(int_value(row, "zero_source_zero_pixels") for row in row_rows)
    zero_source_nonzero = sum(int_value(row, "zero_source_nonzero_pixels") for row in row_rows)
    zero_plus = sum(int_value(row, "zero_plus_dy1_matches") for row in row_rows)
    residual_nonzero = sum(int_value(row, "residual_nonzero_pixels") for row in row_rows)
    expected_zero_plus = int_value(spatial_summary, "dy1_shift0_zero_plus_copy_pixels")
    expected_gap = zero_plus - expected_zero_plus
    issue_rows = len(issues)
    max_residual_run = max((int_value(row, "pixels") for row in residual_rows), default=0)
    zero_plus_ratio = zero_plus / target_pixels if target_pixels else 0.0

    if issue_rows:
        verdict = "shared_2700302b_reference_fixed_dy1_replay_probe_issues"
        next_action = "fix shared 0x2700302b fixed dy1 replay probe inputs"
    elif expected_zero_plus and expected_gap != 0:
        verdict = "shared_2700302b_reference_fixed_dy1_replay_spatial_mismatch"
        next_action = "align fixed dy1 replay accounting with spatial backref probe"
    elif residual_nonzero == 0:
        verdict = "shared_2700302b_reference_fixed_dy1_replay_complete"
        next_action = "promote fixed dy1/shift0 replay for shared 0x2700302b frontier"
    elif zero_plus_ratio >= 0.60:
        verdict = "shared_2700302b_reference_fixed_dy1_replay_validated_partial"
        next_action = (
            "profile fixed dy1/shift0 residual nonzero producer for shared 0x2700302b frontier "
            f"{frontier.get('frontier_id', '')}; {residual_nonzero} nonzero pixels remain across "
            f"{len(residual_rows)} residual runs"
        )
    else:
        verdict = "shared_2700302b_reference_fixed_dy1_replay_weak"
        next_action = (
            "seek alternate row-copy replay for shared 0x2700302b frontier "
            f"{frontier.get('frontier_id', '')}; fixed dy1/shift0 covers only {zero_plus}/{target_pixels} pixels"
        )

    return {
        "scope": "total",
        "archive": frontier.get("archive", ""),
        "archive_tag": frontier.get("archive_tag", ""),
        "pcx_name": frontier.get("pcx_name", ""),
        "frontier_id": frontier.get("frontier_id", ""),
        "target_pixels": str(target_pixels),
        "target_zero_pixels": str(target_zero),
        "target_nonzero_pixels": str(target_nonzero),
        "row_rows": str(len(row_rows)),
        "dy": str(dy),
        "shift": str(shift),
        "raw_copy_matches": str(raw_copy),
        "raw_copy_match_ratio": float_text(raw_copy / target_pixels if target_pixels else 0.0),
        "raw_copy_nonzero_matches": str(raw_copy_nonzero),
        "raw_copy_nonzero_ratio": float_text(raw_copy_nonzero / target_nonzero if target_nonzero else 0.0),
        "zero_source_zero_pixels": str(zero_source_zero),
        "zero_source_nonzero_pixels": str(zero_source_nonzero),
        "zero_plus_dy1_matches": str(zero_plus),
        "zero_plus_dy1_ratio": float_text(zero_plus_ratio),
        "residual_nonzero_pixels": str(residual_nonzero),
        "residual_nonzero_ratio": float_text(residual_nonzero / target_nonzero if target_nonzero else 0.0),
        "residual_run_rows": str(len(residual_rows)),
        "max_residual_run_pixels": str(max_residual_run),
        "spatial_expected_zero_plus_pixels": str(expected_zero_plus),
        "spatial_expected_gap_pixels": str(expected_gap),
        "issue_rows": str(issue_rows),
        "fixed_dy1_replay_verdict": verdict,
        "next_action": next_action,
    }


def render_table(rows: list[dict[str, str]], fieldnames: list[str]) -> str:
    if not rows:
        return "<p>No rows.</p>"
    head = "".join(f"<th>{html.escape(field)}</th>" for field in fieldnames)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fieldnames) + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    rows: list[dict[str, str]],
    residuals: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "rows": rows, "residuals": residuals}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary", output_dir / "summary.csv"),
            ("rows", output_dir / "rows.csv"),
            ("residual_runs", output_dir / "residual_runs.csv"),
        )
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body {{ margin: 24px; font-family: system-ui, sans-serif; background: #101114; color: #eceff4; }}
a {{ color: #8ec5ff; margin-right: 12px; }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin: 18px 0; }}
.stat {{ background: #1b1d22; border: 1px solid #343842; padding: 12px; border-radius: 6px; }}
.label {{ color: #a9b0bd; font-size: 12px; text-transform: uppercase; }}
.value {{ font-size: 20px; font-weight: 700; }}
table {{ border-collapse: collapse; width: 100%; margin: 18px 0 28px; background: #17191e; }}
th, td {{ border-bottom: 1px solid #343842; padding: 7px 9px; text-align: left; font-size: 12px; vertical-align: top; }}
th {{ color: #cfd6e4; background: #22252c; position: sticky; top: 0; }}
td {{ max-width: 340px; overflow-wrap: anywhere; }}
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<p>{links}</p>
<div class="stats">
  <div class="stat"><div class="label">Zero + dy1</div><div class="value">{html.escape(summary['zero_plus_dy1_matches'])}</div></div>
  <div class="stat"><div class="label">Zero + dy1 Ratio</div><div class="value">{html.escape(summary['zero_plus_dy1_ratio'])}</div></div>
  <div class="stat"><div class="label">Residual Nonzero</div><div class="value">{html.escape(summary['residual_nonzero_pixels'])}</div></div>
  <div class="stat"><div class="label">Residual Runs</div><div class="value">{html.escape(summary['residual_run_rows'])}</div></div>
</div>
<p>{html.escape(summary['next_action'])}</p>
<h2>Summary</h2>
{render_table([summary], SUMMARY_FIELDNAMES)}
<h2>Rows</h2>
{render_table(rows, ROW_FIELDNAMES)}
<h2>Residual Runs</h2>
{render_table(residuals[:80], RESIDUAL_FIELDNAMES)}
<script type="application/json" id="data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    args.output.mkdir(parents=True, exist_ok=True)
    frontier, _comparison, pixels, width, _height, issues = spatial_probe.load_reference(args)
    rows, residuals = analyze_rows(
        pixels,
        gap_start=int_value(frontier, "gap_start"),
        gap_end=int_value(frontier, "gap_end"),
        width=width,
        dy=args.dy,
        shift=args.shift,
    )
    summary = build_summary(
        frontier,
        rows,
        residuals,
        read_summary(args.spatial_summary),
        dy=args.dy,
        shift=args.shift,
        issues=issues,
    )
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "rows.csv", ROW_FIELDNAMES, rows)
    write_csv(args.output / "residual_runs.csv", RESIDUAL_FIELDNAMES, residuals)
    (args.output / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""), encoding="utf-8")
    (args.output / "index.html").write_text(build_html(summary, rows, residuals, args.output, args.title), encoding="utf-8")
    return summary, rows, residuals


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay fixed dy1/shift0 for shared 0x2700302b frontier 6.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--frontiers", type=Path, default=DEFAULT_FRONTIERS)
    parser.add_argument("--comparisons", type=Path, default=DEFAULT_COMPARISONS)
    parser.add_argument("--spatial-summary", type=Path, default=DEFAULT_SPATIAL_SUMMARY)
    parser.add_argument("--archive-tag", default="L4_HJ")
    parser.add_argument("--pcx-name", default="dinodead.pcx")
    parser.add_argument("--frontier-id", type=int, default=6)
    parser.add_argument("--dy", type=int, default=1)
    parser.add_argument("--shift", type=int, default=0)
    parser.add_argument("--title", default="Lands of Lore II .tex Shared 0x2700302b Fixed dy1 Replay Probe")
    args = parser.parse_args()
    summary, _rows, _residuals = write_report(args)
    print(f"Zero plus dy1 pixels: {summary['zero_plus_dy1_matches']}")
    print(f"Zero plus dy1 ratio: {summary['zero_plus_dy1_ratio']}")
    print(f"Residual nonzero pixels: {summary['residual_nonzero_pixels']}")
    print(f"Spatial expected gap: {summary['spatial_expected_gap_pixels']}")
    print(f"Verdict: {summary['fixed_dy1_replay_verdict']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
