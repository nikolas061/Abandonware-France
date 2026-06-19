#!/usr/bin/env python3
"""Derive a same-row horizontal selector after large-delta replay for shared 0x2700302b."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import sys
from pathlib import Path

import lolg_tex_large_shared_2700302b_reference_fixed_dy1_post_large_delta_horizontal_residual_probe as horizontal_probe


DEFAULT_OUTPUT = Path("output/tex_large_shared_2700302b_reference_fixed_dy1_post_large_delta_horizontal_selector_probe")
DEFAULT_FRONTIERS = horizontal_probe.DEFAULT_FRONTIERS
DEFAULT_COMPARISONS = horizontal_probe.DEFAULT_COMPARISONS
DEFAULT_POST_LARGE_DELTA_SUMMARY = horizontal_probe.DEFAULT_POST_LARGE_DELTA_SUMMARY
DEFAULT_HORIZONTAL_SUMMARY = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_post_large_delta_horizontal_residual_probe/summary.csv"
)
DEFAULT_REMAINING_PIXELS = horizontal_probe.DEFAULT_REMAINING_PIXELS

SUMMARY_FIELDNAMES = [
    "scope",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "dy",
    "shift",
    "source_shift_set",
    "remaining_nonzero_pixels",
    "small_delta_pixels",
    "large_delta_pixels",
    "horizontal_best_candidate_id",
    "horizontal_best_covered_pixels",
    "selected_pixels",
    "selected_ratio",
    "selected_exact_pixels",
    "selected_small_only_pixels",
    "selected_small_delta_pixels",
    "selected_large_delta_pixels",
    "token_rows",
    "max_token_pixels",
    "potential_remaining_nonzero_pixels",
    "horizontal_selection_gap_pixels",
    "issue_rows",
    "horizontal_selector_verdict",
    "next_action",
]

SELECTED_FIELDNAMES = [
    "rank",
    "target_y",
    "target_x",
    "target_value_hex",
    "dy1_source_value_hex",
    "dy1_delta_signed",
    "residual_kind",
    "same_row_source_y",
    "same_row_source_x",
    "source_shift",
    "same_row_source_value_hex",
    "same_row_delta_signed",
    "match_kind",
    "token_index",
]

TOKEN_FIELDNAMES = [
    "token_index",
    "target_y",
    "x_start",
    "x_end",
    "pixels",
    "exact_pixels",
    "small_only_pixels",
    "small_delta_pixels",
    "large_delta_pixels",
    "shift_signature",
    "target_value_signature_head",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    csv.field_size_limit(sys.maxsize)
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def int_value(row: dict[str, str], field: str) -> int:
    return horizontal_probe.int_value(row, field)


def hex_value(row: dict[str, str], field: str) -> int:
    return horizontal_probe.hex_value(row, field)


def float_text(value: float) -> str:
    return horizontal_probe.float_text(value)


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    try:
        return os.path.relpath(Path(path_text), base_dir)
    except ValueError:
        return str(path_text)


def parse_shifts(text: str) -> tuple[int, ...]:
    values = []
    for part in text.split(","):
        part = part.strip()
        if part:
            values.append(int(part, 0))
    return tuple(values)


def signed_delta(target: int, source: int) -> int:
    return horizontal_probe.signed_delta(target, source)


def annotate_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    annotated = horizontal_probe.annotate_rows(rows)
    for rank, row in enumerate(annotated, 1):
        row["_rank"] = str(rank)
    return annotated


def choose_match(
    row: dict[str, str],
    pixels: bytes,
    width: int,
    height: int,
    shifts: tuple[int, ...],
) -> dict[str, str] | None:
    target_y = int(row["_target_y"])
    target_x = int(row["_target_x"])
    target_value = int(row["_target_value"])
    candidates: list[tuple[int, int, int]] = []
    for source_shift in shifts:
        source = horizontal_probe.source_value(pixels, width, height, target_y, target_x, source_shift)
        if source is None:
            continue
        delta = signed_delta(target_value, source)
        if abs(delta) <= 3:
            candidates.append((source_shift, source, delta))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (abs(item[2]), 0 if item[0] < 0 else 1, abs(item[0]), item[0]))
    source_shift, source, delta = candidates[0]
    return {
        "same_row_source_y": str(target_y),
        "same_row_source_x": str(target_x + source_shift),
        "source_shift": str(source_shift),
        "same_row_source_value_hex": f"{source:02x}",
        "same_row_delta_signed": str(delta),
        "match_kind": "exact" if delta == 0 else "small_delta",
    }


def build_selected_rows(
    rows: list[dict[str, str]],
    pixels: bytes,
    width: int,
    height: int,
    shifts: tuple[int, ...],
) -> list[dict[str, str]]:
    selected: list[dict[str, str]] = []
    token_index = 0
    previous_y = -1
    previous_x = -2

    for row in rows:
        match = choose_match(row, pixels, width, height, shifts)
        if match is None:
            continue
        y = int(row["_target_y"])
        x = int(row["_target_x"])
        if y != previous_y or x != previous_x + 1:
            token_index += 1
        previous_y = y
        previous_x = x
        selected.append(
            {
                "rank": str(len(selected) + 1),
                "target_y": row.get("target_y", ""),
                "target_x": row.get("target_x", ""),
                "target_value_hex": row.get("target_value_hex", ""),
                "dy1_source_value_hex": row.get("source_value_hex", ""),
                "dy1_delta_signed": row.get("delta_signed", ""),
                "residual_kind": row.get("residual_kind", ""),
                "same_row_source_y": match["same_row_source_y"],
                "same_row_source_x": match["same_row_source_x"],
                "source_shift": match["source_shift"],
                "same_row_source_value_hex": match["same_row_source_value_hex"],
                "same_row_delta_signed": match["same_row_delta_signed"],
                "match_kind": match["match_kind"],
                "token_index": str(token_index),
            }
        )
    return selected


def build_token_rows(selected_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    by_token: dict[str, list[dict[str, str]]] = {}
    for row in selected_rows:
        by_token.setdefault(row.get("token_index", ""), []).append(row)

    rows: list[dict[str, str]] = []
    for token_index, token in sorted(by_token.items(), key=lambda item: int(item[0] or 0)):
        values = [row.get("target_value_hex", "") for row in token]
        shifts = [row.get("source_shift", "") for row in token]
        rows.append(
            {
                "token_index": token_index,
                "target_y": token[0].get("target_y", ""),
                "x_start": token[0].get("target_x", ""),
                "x_end": token[-1].get("target_x", ""),
                "pixels": str(len(token)),
                "exact_pixels": str(sum(1 for row in token if row.get("match_kind") == "exact")),
                "small_only_pixels": str(sum(1 for row in token if row.get("match_kind") == "small_delta")),
                "small_delta_pixels": str(sum(1 for row in token if row.get("residual_kind") == "small_delta")),
                "large_delta_pixels": str(sum(1 for row in token if row.get("residual_kind") == "large_delta")),
                "shift_signature": " ".join(shifts[:48]),
                "target_value_signature_head": " ".join(values[:48]),
            }
        )
    return rows


def build_summary(
    post_summary: dict[str, str],
    horizontal_summary: dict[str, str],
    rows: list[dict[str, str]],
    selected_rows: list[dict[str, str]],
    token_rows: list[dict[str, str]],
    shifts: tuple[int, ...],
    issues: list[str],
) -> dict[str, str]:
    remaining = len(rows)
    selected = len(selected_rows)
    horizontal_best = int_value(horizontal_summary, "best_covered_pixels")
    selection_gap = horizontal_best - selected
    issue_rows = len(issues) + (1 if selection_gap else 0)
    small_delta = sum(1 for row in rows if row.get("residual_kind") == "small_delta")
    large_delta = sum(1 for row in rows if row.get("residual_kind") == "large_delta")
    selected_small = sum(1 for row in selected_rows if row.get("residual_kind") == "small_delta")
    selected_large = sum(1 for row in selected_rows if row.get("residual_kind") == "large_delta")
    exact = sum(1 for row in selected_rows if row.get("match_kind") == "exact")
    small_only = selected - exact
    potential_remaining = max(0, remaining - selected)
    max_token = max((int_value(row, "pixels") for row in token_rows), default=0)

    if issue_rows:
        verdict = "shared_2700302b_reference_fixed_dy1_post_large_delta_horizontal_selector_issues"
        next_action = "fix shared 0x2700302b horizontal selector inputs"
    elif remaining and selected / remaining >= 0.90:
        verdict = "shared_2700302b_reference_fixed_dy1_post_large_delta_horizontal_selector_ready"
        next_action = (
            "measure guarded same-row plateau replay after large-delta replay for shared 0x2700302b; "
            f"selector adds {selected}/{remaining} pixels"
        )
    else:
        verdict = "shared_2700302b_reference_fixed_dy1_post_large_delta_horizontal_selector_partial"
        next_action = (
            "refine same-row plateau selector for shared 0x2700302b; "
            f"selector covers {selected}/{remaining}"
        )

    return {
        "scope": "total",
        "archive": post_summary.get("archive", ""),
        "archive_tag": post_summary.get("archive_tag", ""),
        "pcx_name": post_summary.get("pcx_name", ""),
        "frontier_id": post_summary.get("frontier_id", ""),
        "dy": post_summary.get("dy", ""),
        "shift": post_summary.get("shift", ""),
        "source_shift_set": ",".join(str(shift) for shift in shifts),
        "remaining_nonzero_pixels": str(remaining),
        "small_delta_pixels": str(small_delta),
        "large_delta_pixels": str(large_delta),
        "horizontal_best_candidate_id": horizontal_summary.get("best_candidate_id", ""),
        "horizontal_best_covered_pixels": str(horizontal_best),
        "selected_pixels": str(selected),
        "selected_ratio": float_text(selected / remaining if remaining else 0.0),
        "selected_exact_pixels": str(exact),
        "selected_small_only_pixels": str(small_only),
        "selected_small_delta_pixels": str(selected_small),
        "selected_large_delta_pixels": str(selected_large),
        "token_rows": str(len(token_rows)),
        "max_token_pixels": str(max_token),
        "potential_remaining_nonzero_pixels": str(potential_remaining),
        "horizontal_selection_gap_pixels": str(selection_gap),
        "issue_rows": str(issue_rows),
        "horizontal_selector_verdict": verdict,
        "next_action": next_action,
    }


def render_table(rows: list[dict[str, str]], fields: list[str]) -> str:
    if not rows:
        return "<p>No rows.</p>"
    head = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    token_rows: list[dict[str, str]],
    selected_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "tokens": token_rows, "selected": selected_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary", output_dir / "summary.csv"),
            ("tokens", output_dir / "tokens.csv"),
            ("selected pixels", output_dir / "selected_pixels.csv"),
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
td {{ max-width: 420px; overflow-wrap: anywhere; }}
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<p>{links}</p>
<div class="stats">
  <div class="stat"><div class="label">Selected</div><div class="value">{html.escape(summary['selected_pixels'])}</div></div>
  <div class="stat"><div class="label">Exact</div><div class="value">{html.escape(summary['selected_exact_pixels'])}</div></div>
  <div class="stat"><div class="label">Small Only</div><div class="value">{html.escape(summary['selected_small_only_pixels'])}</div></div>
  <div class="stat"><div class="label">Remaining</div><div class="value">{html.escape(summary['potential_remaining_nonzero_pixels'])}</div></div>
</div>
<p>{html.escape(summary['next_action'])}</p>
<h2>Summary</h2>{render_table([summary], SUMMARY_FIELDNAMES)}
<h2>Tokens</h2>{render_table(token_rows[:180], TOKEN_FIELDNAMES)}
<h2>Selected Pixels</h2>{render_table(selected_rows[:220], SELECTED_FIELDNAMES)}
<script type="application/json" id="data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    args.output.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    post_rows = read_csv(args.post_large_delta_summary)
    post_summary = post_rows[0] if post_rows else {}
    if not post_summary:
        issues.append("missing_post_large_delta_summary")
    horizontal_rows = read_csv(args.horizontal_summary)
    horizontal_summary = horizontal_rows[0] if horizontal_rows else {}
    if not horizontal_summary:
        issues.append("missing_horizontal_summary")
    shifts = parse_shifts(horizontal_summary.get("best_candidate_shifts", ""))
    if not shifts:
        issues.append("missing_horizontal_shifts")
    rows = annotate_rows(read_csv(args.remaining_pixels))
    if not rows:
        issues.append("missing_remaining_pixels")
    if len(rows) != int_value(post_summary, "remaining_nonzero_pixels"):
        issues.append("remaining_summary_gap")
    pixels, width, height, load_issues = horizontal_probe.load_reference_pixels(args)
    issues.extend(load_issues)
    selected_rows = build_selected_rows(rows, pixels, width, height, shifts)
    token_rows = build_token_rows(selected_rows)
    summary = build_summary(post_summary, horizontal_summary, rows, selected_rows, token_rows, shifts, issues)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "tokens.csv", TOKEN_FIELDNAMES, token_rows)
    write_csv(args.output / "selected_pixels.csv", SELECTED_FIELDNAMES, selected_rows)
    (args.output / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""), encoding="utf-8")
    (args.output / "index.html").write_text(
        build_html(summary, token_rows, selected_rows, args.output, args.title),
        encoding="utf-8",
    )
    return summary, token_rows, selected_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Derive a same-row horizontal selector after large-delta replay.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--frontiers", type=Path, default=DEFAULT_FRONTIERS)
    parser.add_argument("--comparisons", type=Path, default=DEFAULT_COMPARISONS)
    parser.add_argument("--post-large-delta-summary", type=Path, default=DEFAULT_POST_LARGE_DELTA_SUMMARY)
    parser.add_argument("--horizontal-summary", type=Path, default=DEFAULT_HORIZONTAL_SUMMARY)
    parser.add_argument("--remaining-pixels", type=Path, default=DEFAULT_REMAINING_PIXELS)
    parser.add_argument("--archive-tag", default="L4_HJ")
    parser.add_argument("--pcx-name", default="dinodead.pcx")
    parser.add_argument("--frontier-id", type=int, default=6)
    parser.add_argument("--mix-entry-index", type=int, default=2)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Shared 0x2700302b Post-large-delta Horizontal Selector",
    )
    args = parser.parse_args()
    summary, _tokens, _selected = write_report(args)
    print(f"Selected pixels: {summary['selected_pixels']}/{summary['remaining_nonzero_pixels']}")
    print(f"Exact pixels: {summary['selected_exact_pixels']}")
    print(f"Small-only pixels: {summary['selected_small_only_pixels']}")
    print(f"Potential remaining nonzero pixels: {summary['potential_remaining_nonzero_pixels']}")
    print(f"Verdict: {summary['horizontal_selector_verdict']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
