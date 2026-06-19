#!/usr/bin/env python3
"""Derive a segment-nonzero large-delta selector after high3 replay for shared 0x2700302b."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

import lolg_tex_large_shared_2700302b_reference_fixed_dy1_residual_profile_probe as residual_profile
import lolg_tex_large_shared_2700302b_reference_fixed_dy1_small_delta_low2_selector_probe as low2_selector
import lolg_tex_large_shared_2700302b_reference_frontier_probe as frontier_probe


DEFAULT_OUTPUT = Path("output/tex_large_shared_2700302b_reference_fixed_dy1_post_high3_large_delta_selector_probe")
DEFAULT_FRONTIERS = frontier_probe.DEFAULT_FRONTIERS
DEFAULT_COMPARISONS = frontier_probe.DEFAULT_COMPARISONS
DEFAULT_POST_HIGH3_SUMMARY = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_post_high3_residual_profile_probe/summary.csv"
)
DEFAULT_SOURCE_SUMMARY = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_post_high3_large_delta_source_probe/summary.csv"
)
DEFAULT_REMAINING_PIXELS = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_post_high3_residual_profile_probe/remaining_pixels.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "dy",
    "shift",
    "source_transform",
    "segment_bytes",
    "source_bytes",
    "remaining_nonzero_pixels",
    "large_delta_pixels",
    "source_zero_large_delta_pixels",
    "source_nonzero_large_delta_pixels",
    "aligned_pixels",
    "aligned_ratio",
    "source_used_ratio",
    "full_token_rows",
    "full_token_pixels",
    "partial_token_rows",
    "partial_token_pixels",
    "uncovered_token_rows",
    "uncovered_pixels",
    "first_segment_offset",
    "last_segment_offset",
    "source_best_lcs_pixels",
    "source_best_id",
    "source_alignment_gap_pixels",
    "potential_remaining_nonzero_pixels",
    "selected_pixel_rows",
    "issue_rows",
    "large_delta_selector_verdict",
    "next_action",
]

TOKEN_FIELDNAMES = [
    "token_index",
    "target_y",
    "x_start",
    "x_end",
    "pixels",
    "aligned_pixels",
    "aligned_ratio",
    "first_source_index",
    "last_source_index",
    "first_segment_offset",
    "last_segment_offset",
    "target_value_signature_head",
    "verdict",
]

ALIGNMENT_FIELDNAMES = [
    "rank",
    "source_index",
    "segment_offset",
    "source_value_hex",
    "target_index",
    "token_index",
    "target_y",
    "target_x",
    "target_value_hex",
    "dy1_source_value_hex",
    "delta_signed",
    "token_pixels",
    "token_aligned_pixels",
]

SELECTED_FIELDNAMES = [
    "rank",
    "target_y",
    "target_x",
    "target_value_hex",
    "dy1_source_value_hex",
    "delta_signed",
    "source_index",
    "segment_offset",
    "source_value_hex",
    "token_index",
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


def hex_value(row: dict[str, str], field: str) -> int:
    raw = row.get(field, "0")
    return int(raw, 16) if raw else 0


def float_text(value: float) -> str:
    return f"{value:.6f}"


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    try:
        return os.path.relpath(Path(path_text), base_dir)
    except ValueError:
        return str(path_text)


def load_segment(args: argparse.Namespace) -> tuple[bytes, list[str]]:
    load_args = argparse.Namespace(
        frontiers=args.frontiers,
        comparisons=args.comparisons,
        archive_tag=args.archive_tag,
        pcx_name=args.pcx_name,
        frontier_id=args.frontier_id,
        mix_entry_index=args.mix_entry_index,
    )
    _frontier, _comparison, _pixels, _width, segment, issues = residual_profile.load_reference(load_args)
    return segment, issues


def segment_nonzero_source(segment: bytes) -> list[dict[str, int]]:
    rows: list[dict[str, int]] = []
    source_index = 0
    for segment_offset, value in enumerate(segment):
        if value == 0:
            continue
        rows.append({"source_index": source_index, "segment_offset": segment_offset, "value": value})
        source_index += 1
    return rows


def large_delta_target(row: dict[str, str]) -> bool:
    return row.get("residual_kind") == "large_delta"


def build_targets(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    targets: list[dict[str, str]] = []
    tokens: list[dict[str, str]] = []
    current: list[dict[str, str]] = []
    previous_y = -1
    previous_x = -2
    token_index = 0

    def flush() -> None:
        nonlocal token_index
        if not current:
            return
        token_index += 1
        first = current[0]
        last = current[-1]
        tokens.append(
            {
                "token_index": str(token_index),
                "target_y": first.get("target_y", ""),
                "x_start": first.get("target_x", ""),
                "x_end": last.get("target_x", ""),
                "pixels": str(len(current)),
                "target_value_signature_head": "|".join(row.get("target_value_hex", "") for row in current[:32]),
            }
        )
        for pixel_index, row in enumerate(current):
            targets.append(
                {
                    "target_index": str(len(targets)),
                    "token_index": str(token_index),
                    "token_pixel_index": str(pixel_index),
                    "target_y": row.get("target_y", ""),
                    "target_x": row.get("target_x", ""),
                    "target_value": str(hex_value(row, "target_value_hex")),
                    "target_value_hex": row.get("target_value_hex", ""),
                    "dy1_source_value_hex": row.get("source_value_hex", ""),
                    "delta_signed": row.get("delta_signed", ""),
                }
            )
        current.clear()

    for row in rows:
        y = int_value(row, "target_y")
        x = int_value(row, "target_x")
        target = large_delta_target(row)
        contiguous = y == previous_y and x == previous_x + 1
        if current and (not target or not contiguous):
            flush()
        if target:
            current.append(row)
        previous_y = y
        previous_x = x
    flush()
    return targets, tokens


def build_alignment_rows(
    source_rows: list[dict[str, int]],
    target_rows: list[dict[str, str]],
    pairs: list[tuple[int, int]],
) -> list[dict[str, str]]:
    token_counts: dict[str, int] = defaultdict(int)
    for _source_index, target_index in pairs:
        token_counts[target_rows[target_index].get("token_index", "")] += 1
    token_pixels = {
        target.get("token_index", ""): int_value(target, "token_pixel_index") + 1
        for target in target_rows
    }
    rows: list[dict[str, str]] = []
    for rank, (source_index, target_index) in enumerate(pairs, 1):
        source = source_rows[source_index]
        target = target_rows[target_index]
        rows.append(
            {
                "rank": str(rank),
                "source_index": str(source["source_index"]),
                "segment_offset": str(source["segment_offset"]),
                "source_value_hex": f"{source['value']:02x}",
                "target_index": target.get("target_index", ""),
                "token_index": target.get("token_index", ""),
                "target_y": target.get("target_y", ""),
                "target_x": target.get("target_x", ""),
                "target_value_hex": target.get("target_value_hex", ""),
                "dy1_source_value_hex": target.get("dy1_source_value_hex", ""),
                "delta_signed": target.get("delta_signed", ""),
                "token_pixels": str(token_pixels.get(target.get("token_index", ""), 0)),
                "token_aligned_pixels": str(token_counts.get(target.get("token_index", ""), 0)),
            }
        )
    return rows


def build_token_rows(
    token_source_rows: list[dict[str, str]],
    alignment_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    aligned_by_token: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in alignment_rows:
        aligned_by_token[row.get("token_index", "")].append(row)

    rows: list[dict[str, str]] = []
    for token in token_source_rows:
        token_index = token.get("token_index", "")
        aligned = aligned_by_token.get(token_index, [])
        pixels = int_value(token, "pixels")
        aligned_pixels = len(aligned)
        if aligned_pixels == 0:
            verdict = "uncovered"
        elif aligned_pixels == pixels:
            verdict = "full"
        else:
            verdict = "partial"
        rows.append(
            {
                "token_index": token_index,
                "target_y": token.get("target_y", ""),
                "x_start": token.get("x_start", ""),
                "x_end": token.get("x_end", ""),
                "pixels": str(pixels),
                "aligned_pixels": str(aligned_pixels),
                "aligned_ratio": float_text(aligned_pixels / pixels if pixels else 0.0),
                "first_source_index": aligned[0].get("source_index", "") if aligned else "",
                "last_source_index": aligned[-1].get("source_index", "") if aligned else "",
                "first_segment_offset": aligned[0].get("segment_offset", "") if aligned else "",
                "last_segment_offset": aligned[-1].get("segment_offset", "") if aligned else "",
                "target_value_signature_head": token.get("target_value_signature_head", ""),
                "verdict": verdict,
            }
        )
    return rows


def build_selected_rows(alignment_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for rank, row in enumerate(alignment_rows, 1):
        rows.append(
            {
                "rank": str(rank),
                "target_y": row.get("target_y", ""),
                "target_x": row.get("target_x", ""),
                "target_value_hex": row.get("target_value_hex", ""),
                "dy1_source_value_hex": row.get("dy1_source_value_hex", ""),
                "delta_signed": row.get("delta_signed", ""),
                "source_index": row.get("source_index", ""),
                "segment_offset": row.get("segment_offset", ""),
                "source_value_hex": row.get("source_value_hex", ""),
                "token_index": row.get("token_index", ""),
            }
        )
    return rows


def build_summary(
    post_summary: dict[str, str],
    source_summary: dict[str, str],
    segment: bytes,
    source_rows: list[dict[str, int]],
    target_rows: list[dict[str, str]],
    token_rows: list[dict[str, str]],
    alignment_rows: list[dict[str, str]],
    *,
    issues: list[str],
) -> dict[str, str]:
    remaining = int_value(post_summary, "remaining_nonzero_pixels")
    large_delta = int_value(post_summary, "remaining_large_delta_pixels")
    source_zero = int_value(post_summary, "remaining_source_zero_pixels")
    source_nonzero = large_delta - source_zero
    source_best_lcs = int_value(source_summary, "best_large_value_lcs_pixels")
    source_gap = source_best_lcs - len(alignment_rows)
    target_gap = len(target_rows) - large_delta
    full_tokens = [row for row in token_rows if row.get("verdict") == "full"]
    partial_tokens = [row for row in token_rows if row.get("verdict") == "partial"]
    uncovered_tokens = [row for row in token_rows if row.get("verdict") == "uncovered"]
    full_pixels = sum(int_value(row, "pixels") for row in full_tokens)
    partial_pixels = sum(int_value(row, "aligned_pixels") for row in partial_tokens)
    uncovered_pixels = len(target_rows) - len(alignment_rows)
    potential_remaining = max(0, remaining - len(alignment_rows))
    issue_rows = len(issues) + (1 if source_gap else 0) + (1 if target_gap else 0)
    segment_offsets = [int_value(row, "segment_offset") for row in alignment_rows]

    if issue_rows:
        verdict = "shared_2700302b_reference_fixed_dy1_post_high3_large_delta_selector_issues"
        next_action = "fix shared 0x2700302b post-high3 large-delta selector inputs"
    elif len(alignment_rows) / large_delta >= 0.45 if large_delta else False:
        verdict = "shared_2700302b_reference_fixed_dy1_post_high3_large_delta_selector_ready"
        next_action = (
            "measure guarded large-delta replay after high3 for shared 0x2700302b; "
            f"selector adds {len(alignment_rows)} pixels"
        )
    else:
        verdict = "shared_2700302b_reference_fixed_dy1_post_high3_large_delta_selector_weak"
        next_action = (
            "search alternate large-delta selector after high3 for shared 0x2700302b; "
            f"selector covers {len(alignment_rows)}/{large_delta}"
        )

    return {
        "scope": "total",
        "archive": post_summary.get("archive", ""),
        "archive_tag": post_summary.get("archive_tag", ""),
        "pcx_name": post_summary.get("pcx_name", ""),
        "frontier_id": post_summary.get("frontier_id", ""),
        "dy": post_summary.get("dy", ""),
        "shift": post_summary.get("shift", ""),
        "source_transform": "segment_nonzero_to_large_target_value",
        "segment_bytes": str(len(segment)),
        "source_bytes": str(len(source_rows)),
        "remaining_nonzero_pixels": str(remaining),
        "large_delta_pixels": str(large_delta),
        "source_zero_large_delta_pixels": str(source_zero),
        "source_nonzero_large_delta_pixels": str(source_nonzero),
        "aligned_pixels": str(len(alignment_rows)),
        "aligned_ratio": float_text(len(alignment_rows) / large_delta if large_delta else 0.0),
        "source_used_ratio": float_text(len(alignment_rows) / len(source_rows) if source_rows else 0.0),
        "full_token_rows": str(len(full_tokens)),
        "full_token_pixels": str(full_pixels),
        "partial_token_rows": str(len(partial_tokens)),
        "partial_token_pixels": str(partial_pixels),
        "uncovered_token_rows": str(len(uncovered_tokens)),
        "uncovered_pixels": str(uncovered_pixels),
        "first_segment_offset": str(min(segment_offsets) if segment_offsets else 0),
        "last_segment_offset": str(max(segment_offsets) if segment_offsets else 0),
        "source_best_lcs_pixels": str(source_best_lcs),
        "source_best_id": source_summary.get("best_large_value_source_id", ""),
        "source_alignment_gap_pixels": str(source_gap),
        "potential_remaining_nonzero_pixels": str(potential_remaining),
        "selected_pixel_rows": str(len(alignment_rows)),
        "issue_rows": str(issue_rows),
        "large_delta_selector_verdict": verdict,
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
    token_rows: list[dict[str, str]],
    alignment_rows: list[dict[str, str]],
    selected_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "tokens": token_rows,
        "alignments": alignment_rows,
        "selected": selected_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary", output_dir / "summary.csv"),
            ("tokens", output_dir / "tokens.csv"),
            ("alignments", output_dir / "alignments.csv"),
            ("selected_pixels", output_dir / "selected_pixels.csv"),
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
td {{ max-width: 380px; overflow-wrap: anywhere; }}
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<p>{links}</p>
<div class="stats">
  <div class="stat"><div class="label">Aligned</div><div class="value">{html.escape(summary['aligned_pixels'])}</div></div>
  <div class="stat"><div class="label">Aligned Ratio</div><div class="value">{html.escape(summary['aligned_ratio'])}</div></div>
  <div class="stat"><div class="label">Large Delta</div><div class="value">{html.escape(summary['large_delta_pixels'])}</div></div>
  <div class="stat"><div class="label">Potential Remaining</div><div class="value">{html.escape(summary['potential_remaining_nonzero_pixels'])}</div></div>
</div>
<p>{html.escape(summary['next_action'])}</p>
<h2>Summary</h2>{render_table([summary], SUMMARY_FIELDNAMES)}
<h2>Tokens</h2>{render_table(token_rows[:180], TOKEN_FIELDNAMES)}
<h2>Alignments</h2>{render_table(alignment_rows[:180], ALIGNMENT_FIELDNAMES)}
<h2>Selected Pixels</h2>{render_table(selected_rows[:180], SELECTED_FIELDNAMES)}
<script type="application/json" id="data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(
    args: argparse.Namespace,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    args.output.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    post_summary = read_summary(args.post_high3_summary)
    source_summary = read_summary(args.source_summary)
    if not post_summary:
        issues.append("missing_post_high3_summary")
    if not source_summary:
        issues.append("missing_source_summary")
    remaining_rows = read_csv(args.remaining_pixels)
    if not remaining_rows:
        issues.append("missing_remaining_pixels")
    segment, load_issues = load_segment(args)
    issues.extend(load_issues)
    source_rows = segment_nonzero_source(segment)
    target_rows, token_source_rows = build_targets(remaining_rows)
    pairs = low2_selector.lcs_alignment(
        [row["value"] for row in source_rows],
        [int_value(row, "target_value") for row in target_rows],
    )
    alignment_rows = build_alignment_rows(source_rows, target_rows, pairs)
    token_rows = build_token_rows(token_source_rows, alignment_rows)
    selected_rows = build_selected_rows(alignment_rows)
    summary = build_summary(
        post_summary,
        source_summary,
        segment,
        source_rows,
        target_rows,
        token_rows,
        alignment_rows,
        issues=issues,
    )
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "tokens.csv", TOKEN_FIELDNAMES, token_rows)
    write_csv(args.output / "alignments.csv", ALIGNMENT_FIELDNAMES, alignment_rows)
    write_csv(args.output / "selected_pixels.csv", SELECTED_FIELDNAMES, selected_rows)
    (args.output / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""), encoding="utf-8")
    (args.output / "index.html").write_text(
        build_html(summary, token_rows, alignment_rows, selected_rows, args.output, args.title),
        encoding="utf-8",
    )
    return summary, token_rows, alignment_rows, selected_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Derive a post-high3 large-delta selector for shared 0x2700302b.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--frontiers", type=Path, default=DEFAULT_FRONTIERS)
    parser.add_argument("--comparisons", type=Path, default=DEFAULT_COMPARISONS)
    parser.add_argument("--post-high3-summary", type=Path, default=DEFAULT_POST_HIGH3_SUMMARY)
    parser.add_argument("--source-summary", type=Path, default=DEFAULT_SOURCE_SUMMARY)
    parser.add_argument("--remaining-pixels", type=Path, default=DEFAULT_REMAINING_PIXELS)
    parser.add_argument("--archive-tag", default="L4_HJ")
    parser.add_argument("--pcx-name", default="dinodead.pcx")
    parser.add_argument("--frontier-id", type=int, default=6)
    parser.add_argument("--mix-entry-index", type=int, default=2)
    parser.add_argument("--title", default="Lands of Lore II .tex Shared 0x2700302b Post-high3 Large-Delta Selector")
    args = parser.parse_args()
    summary, _tokens, _alignments, _selected = write_report(args)
    print(f"Aligned pixels: {summary['aligned_pixels']}")
    print(f"Aligned ratio: {summary['aligned_ratio']}")
    print(f"Potential remaining nonzero pixels: {summary['potential_remaining_nonzero_pixels']}")
    print(f"Verdict: {summary['large_delta_selector_verdict']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
