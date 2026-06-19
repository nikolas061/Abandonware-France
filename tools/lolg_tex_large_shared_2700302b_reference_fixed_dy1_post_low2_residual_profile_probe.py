#!/usr/bin/env python3
"""Profile residual pixels after fixed-dy1 plus guarded low2 replay for shared 0x2700302b."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path


DEFAULT_OUTPUT = Path("output/tex_large_shared_2700302b_reference_fixed_dy1_post_low2_residual_profile_probe")
DEFAULT_GUARDED_SUMMARY = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_low2_guarded_replay_probe/summary.csv"
)
DEFAULT_RESIDUAL_PIXELS = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_residual_profile_probe/residual_pixels.csv"
)
DEFAULT_SELECTED_PIXELS = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_low2_guarded_replay_probe/selected_pixels.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "dy",
    "shift",
    "input_residual_pixels",
    "selected_low2_pixels",
    "remaining_nonzero_pixels",
    "remaining_small_delta_pixels",
    "remaining_small_delta_ratio",
    "remaining_large_delta_pixels",
    "remaining_large_delta_ratio",
    "remaining_source_zero_pixels",
    "remaining_source_zero_ratio",
    "remaining_run_rows",
    "max_remaining_run_pixels",
    "row_rows",
    "rows_with_source_zero",
    "dominant_delta",
    "dominant_delta_pixels",
    "guarded_remaining_nonzero_pixels",
    "guarded_gap_pixels",
    "issue_rows",
    "post_low2_residual_verdict",
    "next_action",
]

PIXEL_FIELDNAMES = [
    "target_y",
    "target_x",
    "target_absolute",
    "source_y",
    "source_x",
    "target_value_hex",
    "source_value_hex",
    "delta_hex",
    "delta_signed",
    "abs_delta",
    "residual_kind",
]

ROW_FIELDNAMES = [
    "target_y",
    "remaining_pixels",
    "small_delta_pixels",
    "large_delta_pixels",
    "source_zero_pixels",
    "run_rows",
    "max_run_pixels",
    "top_deltas",
]

DELTA_FIELDNAMES = [
    "rank",
    "residual_kind",
    "delta_signed",
    "delta_hex",
    "count",
    "ratio",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    csv.field_size_limit(sys.maxsize)
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_summary(path: Path) -> dict[str, str]:
    rows = read_csv(path)
    return rows[0] if rows else {}


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def int_value(row: dict[str, str], field: str) -> int:
    raw = row.get(field, "")
    return int(raw, 0) if raw else 0


def float_text(value: float) -> str:
    return f"{value:.6f}"


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    try:
        return os.path.relpath(Path(path_text), base_dir)
    except ValueError:
        return str(path_text)


def residual_kind(row: dict[str, str]) -> str:
    return "small_delta" if 1 <= abs(int_value(row, "delta_signed")) <= 3 else "large_delta"


def selected_keys(rows: list[dict[str, str]]) -> set[tuple[str, str]]:
    return {(row.get("target_y", ""), row.get("target_x", "")) for row in rows}


def remaining_pixels(residual_rows: list[dict[str, str]], selected_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    selected = selected_keys(selected_rows)
    rows: list[dict[str, str]] = []
    for row in residual_rows:
        if (row.get("target_y", ""), row.get("target_x", "")) in selected:
            continue
        output = dict(row)
        output["residual_kind"] = residual_kind(row)
        rows.append(output)
    return rows


def run_lengths(rows: list[dict[str, str]]) -> list[int]:
    lengths: list[int] = []
    current = 0
    previous_y = -1
    previous_x = -2
    for row in rows:
        y = int_value(row, "target_y")
        x = int_value(row, "target_x")
        if current and y == previous_y and x == previous_x + 1:
            current += 1
        else:
            if current:
                lengths.append(current)
            current = 1
        previous_y = y
        previous_x = x
    if current:
        lengths.append(current)
    return lengths


def build_row_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    by_y: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_y[row.get("target_y", "")].append(row)
    output: list[dict[str, str]] = []
    for y in sorted(by_y, key=lambda value: int(value or 0)):
        row_pixels = by_y[y]
        runs = run_lengths(row_pixels)
        small = [row for row in row_pixels if row.get("residual_kind") == "small_delta"]
        large = [row for row in row_pixels if row.get("residual_kind") == "large_delta"]
        source_zero = [row for row in row_pixels if int(row.get("source_value_hex", "0"), 16) == 0]
        deltas = Counter(int_value(row, "delta_signed") for row in row_pixels)
        output.append(
            {
                "target_y": y,
                "remaining_pixels": str(len(row_pixels)),
                "small_delta_pixels": str(len(small)),
                "large_delta_pixels": str(len(large)),
                "source_zero_pixels": str(len(source_zero)),
                "run_rows": str(len(runs)),
                "max_run_pixels": str(max(runs, default=0)),
                "top_deltas": "|".join(f"{delta}:{count}" for delta, count in deltas.most_common(8)),
            }
        )
    return output


def build_delta_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    totals = Counter(row.get("residual_kind", "") for row in rows)
    counters: dict[str, Counter[int]] = {"small_delta": Counter(), "large_delta": Counter()}
    for row in rows:
        counters[row.get("residual_kind", "")][int_value(row, "delta_signed")] += 1
    output: list[dict[str, str]] = []
    for kind in ("small_delta", "large_delta"):
        total = totals[kind]
        for rank, (delta, count) in enumerate(counters[kind].most_common(), 1):
            output.append(
                {
                    "rank": str(rank),
                    "residual_kind": kind,
                    "delta_signed": str(delta),
                    "delta_hex": f"{delta & 0xFF:02x}",
                    "count": str(count),
                    "ratio": float_text(count / total if total else 0.0),
                }
            )
    return output


def build_summary(
    guarded_summary: dict[str, str],
    residual_rows: list[dict[str, str]],
    selected_rows: list[dict[str, str]],
    remaining_rows: list[dict[str, str]],
    row_rows: list[dict[str, str]],
    issues: list[str],
) -> dict[str, str]:
    remaining = len(remaining_rows)
    small = [row for row in remaining_rows if row.get("residual_kind") == "small_delta"]
    large = [row for row in remaining_rows if row.get("residual_kind") == "large_delta"]
    source_zero = [row for row in remaining_rows if int(row.get("source_value_hex", "0"), 16) == 0]
    runs = run_lengths(remaining_rows)
    delta_counter = Counter(int_value(row, "delta_signed") for row in remaining_rows)
    dominant_delta, dominant_count = delta_counter.most_common(1)[0] if delta_counter else (0, 0)
    guarded_remaining = int_value(guarded_summary, "remaining_nonzero_pixels")
    guarded_gap = remaining - guarded_remaining if guarded_remaining else 0
    issue_rows = len(issues)
    if guarded_remaining and guarded_gap != 0:
        issue_rows += 1

    if issue_rows:
        verdict = "shared_2700302b_reference_fixed_dy1_post_low2_residual_profile_issues"
        next_action = "fix shared 0x2700302b post-low2 residual profile inputs"
    elif len(small) > len(large):
        verdict = "shared_2700302b_reference_fixed_dy1_post_low2_small_delta_remaining"
        next_action = (
            "split post-low2 residual small-delta selector misses for shared 0x2700302b frontier "
            f"{guarded_summary.get('frontier_id', '')}; {len(small)} small-delta and {len(large)} large-delta pixels remain"
        )
    else:
        verdict = "shared_2700302b_reference_fixed_dy1_post_low2_large_delta_focus"
        next_action = (
            "derive large-delta/source-zero producer for shared 0x2700302b frontier "
            f"{guarded_summary.get('frontier_id', '')}; {len(large)} large-delta pixels remain"
        )

    return {
        "scope": "total",
        "archive": guarded_summary.get("archive", ""),
        "archive_tag": guarded_summary.get("archive_tag", ""),
        "pcx_name": guarded_summary.get("pcx_name", ""),
        "frontier_id": guarded_summary.get("frontier_id", ""),
        "dy": guarded_summary.get("dy", ""),
        "shift": guarded_summary.get("shift", ""),
        "input_residual_pixels": str(len(residual_rows)),
        "selected_low2_pixels": str(len(selected_rows)),
        "remaining_nonzero_pixels": str(remaining),
        "remaining_small_delta_pixels": str(len(small)),
        "remaining_small_delta_ratio": float_text(len(small) / remaining if remaining else 0.0),
        "remaining_large_delta_pixels": str(len(large)),
        "remaining_large_delta_ratio": float_text(len(large) / remaining if remaining else 0.0),
        "remaining_source_zero_pixels": str(len(source_zero)),
        "remaining_source_zero_ratio": float_text(len(source_zero) / remaining if remaining else 0.0),
        "remaining_run_rows": str(len(runs)),
        "max_remaining_run_pixels": str(max(runs, default=0)),
        "row_rows": str(len(row_rows)),
        "rows_with_source_zero": str(sum(1 for row in row_rows if int_value(row, "source_zero_pixels") > 0)),
        "dominant_delta": str(dominant_delta),
        "dominant_delta_pixels": str(dominant_count),
        "guarded_remaining_nonzero_pixels": str(guarded_remaining),
        "guarded_gap_pixels": str(guarded_gap),
        "issue_rows": str(issue_rows),
        "post_low2_residual_verdict": verdict,
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
    pixels: list[dict[str, str]],
    rows: list[dict[str, str]],
    deltas: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "rows": rows, "deltas": deltas}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary", output_dir / "summary.csv"),
            ("remaining_pixels", output_dir / "remaining_pixels.csv"),
            ("rows", output_dir / "rows.csv"),
            ("delta_profile", output_dir / "delta_profile.csv"),
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
td {{ max-width: 360px; overflow-wrap: anywhere; }}
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<p>{links}</p>
<div class="stats">
  <div class="stat"><div class="label">Remaining</div><div class="value">{html.escape(summary['remaining_nonzero_pixels'])}</div></div>
  <div class="stat"><div class="label">Small Delta</div><div class="value">{html.escape(summary['remaining_small_delta_pixels'])}</div></div>
  <div class="stat"><div class="label">Large Delta</div><div class="value">{html.escape(summary['remaining_large_delta_pixels'])}</div></div>
  <div class="stat"><div class="label">Source Zero</div><div class="value">{html.escape(summary['remaining_source_zero_pixels'])}</div></div>
</div>
<p>{html.escape(summary['next_action'])}</p>
<h2>Summary</h2>{render_table([summary], SUMMARY_FIELDNAMES)}
<h2>Rows</h2>{render_table(rows, ROW_FIELDNAMES)}
<h2>Delta Profile</h2>{render_table(deltas, DELTA_FIELDNAMES)}
<h2>Remaining Pixels</h2>{render_table(pixels[:160], PIXEL_FIELDNAMES)}
<script type="application/json" id="data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> tuple[dict[str, str], list[dict[str, str]]]:
    args.output.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    guarded_summary = read_summary(args.guarded_summary)
    if not guarded_summary:
        issues.append("missing_guarded_summary")
    residual_rows = read_csv(args.residual_pixels)
    if not residual_rows:
        issues.append("missing_residual_pixels")
    selected_rows = read_csv(args.selected_pixels)
    if not selected_rows:
        issues.append("missing_selected_pixels")
    pixels = remaining_pixels(residual_rows, selected_rows)
    row_rows = build_row_rows(pixels)
    delta_rows = build_delta_rows(pixels)
    summary = build_summary(guarded_summary, residual_rows, selected_rows, pixels, row_rows, issues)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "remaining_pixels.csv", PIXEL_FIELDNAMES, pixels)
    write_csv(args.output / "rows.csv", ROW_FIELDNAMES, row_rows)
    write_csv(args.output / "delta_profile.csv", DELTA_FIELDNAMES, delta_rows)
    (args.output / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""), encoding="utf-8")
    (args.output / "index.html").write_text(
        build_html(summary, pixels, row_rows, delta_rows, args.output, args.title),
        encoding="utf-8",
    )
    return summary, pixels


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile post-low2 residuals for shared 0x2700302b.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--guarded-summary", type=Path, default=DEFAULT_GUARDED_SUMMARY)
    parser.add_argument("--residual-pixels", type=Path, default=DEFAULT_RESIDUAL_PIXELS)
    parser.add_argument("--selected-pixels", type=Path, default=DEFAULT_SELECTED_PIXELS)
    parser.add_argument("--title", default="Lands of Lore II .tex Shared 0x2700302b Post-low2 Residual Profile")
    args = parser.parse_args()
    summary, _pixels = write_report(args)
    print(f"Remaining nonzero pixels: {summary['remaining_nonzero_pixels']}")
    print(f"Remaining small-delta pixels: {summary['remaining_small_delta_pixels']}")
    print(f"Remaining large-delta pixels: {summary['remaining_large_delta_pixels']}")
    print(f"Verdict: {summary['post_low2_residual_verdict']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
