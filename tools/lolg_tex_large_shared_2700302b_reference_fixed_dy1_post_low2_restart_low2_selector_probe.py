#!/usr/bin/env python3
"""Derive a restart low2 selector for post-low2 compatible misses in shared 0x2700302b."""

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


DEFAULT_OUTPUT = Path("output/tex_large_shared_2700302b_reference_fixed_dy1_post_low2_restart_low2_selector_probe")
DEFAULT_FRONTIERS = frontier_probe.DEFAULT_FRONTIERS
DEFAULT_COMPARISONS = frontier_probe.DEFAULT_COMPARISONS
DEFAULT_GUARDED_SUMMARY = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_low2_guarded_replay_probe/summary.csv"
)
DEFAULT_MISS_SPLIT_SUMMARY = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_post_low2_small_delta_miss_split_probe/summary.csv"
)
DEFAULT_COMPATIBLE_SOURCE_SUMMARY = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_post_low2_compatible_source_probe/summary.csv"
)
DEFAULT_REMAINING_PIXELS = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_post_low2_residual_profile_probe/remaining_pixels.csv"
)
DEFAULT_PREVIOUS_LOW2_ALIGNMENTS = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_small_delta_low2_selector_probe/alignments.csv"
)

LOW2_DELTAS = {-2, -1, 1}

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
    "previous_low2_aligned_pixels",
    "previous_low2_used_source_bytes",
    "target_pixels",
    "current_combined_covered_pixels",
    "current_combined_covered_ratio",
    "remaining_nonzero_pixels",
    "compatible_miss_pixels",
    "low2_impossible_pixels",
    "restart_aligned_pixels",
    "restart_aligned_ratio",
    "restart_source_used_ratio",
    "restart_reused_source_pixels",
    "restart_new_source_pixels",
    "full_token_rows",
    "full_token_pixels",
    "partial_token_rows",
    "partial_token_pixels",
    "uncovered_token_rows",
    "uncovered_pixels",
    "first_segment_offset",
    "last_segment_offset",
    "compatible_best_lcs_pixels",
    "compatible_best_source_id",
    "source_alignment_gap_pixels",
    "potential_combined_covered_pixels",
    "potential_combined_covered_ratio",
    "potential_remaining_nonzero_pixels",
    "selected_pixel_rows",
    "issue_rows",
    "restart_low2_selector_verdict",
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
    "source_reuse_pixels",
    "delta_signature_head",
    "verdict",
]

ALIGNMENT_FIELDNAMES = [
    "rank",
    "source_index",
    "segment_offset",
    "source_value_signed",
    "previous_low2_source_reused",
    "target_index",
    "token_index",
    "target_y",
    "target_x",
    "delta_signed",
    "token_pixels",
    "token_aligned_pixels",
]

SELECTED_FIELDNAMES = [
    "rank",
    "target_y",
    "target_x",
    "delta_signed",
    "source_index",
    "segment_offset",
    "source_value_signed",
    "token_index",
    "previous_low2_source_reused",
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


def low2_compatible(row: dict[str, str]) -> bool:
    return row.get("residual_kind") == "small_delta" and int_value(row, "delta_signed") in LOW2_DELTAS


def used_source_indexes(rows: list[dict[str, str]]) -> set[int]:
    return {int_value(row, "source_index") for row in rows}


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
                "delta_signature_head": "|".join(row.get("delta_signed", "") for row in current[:32]),
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
                    "delta": str(int_value(row, "delta_signed") & 0xFF),
                    "delta_signed": row.get("delta_signed", ""),
                }
            )
        current.clear()

    for row in rows:
        y = int_value(row, "target_y")
        x = int_value(row, "target_x")
        compatible = low2_compatible(row)
        contiguous = y == previous_y and x == previous_x + 1
        if current and (not compatible or not contiguous):
            flush()
        if compatible:
            current.append(row)
        previous_y = y
        previous_x = x
    flush()
    return targets, tokens


def build_alignment_rows(
    source_rows: list[dict[str, int]],
    target_rows: list[dict[str, str]],
    pairs: list[tuple[int, int]],
    previous_sources: set[int],
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
        reused = source["source_index"] in previous_sources
        rows.append(
            {
                "rank": str(rank),
                "source_index": str(source["source_index"]),
                "segment_offset": str(source["segment_offset"]),
                "source_value_signed": str(source["value_signed"]),
                "previous_low2_source_reused": "1" if reused else "0",
                "target_index": target.get("target_index", ""),
                "token_index": target.get("token_index", ""),
                "target_y": target.get("target_y", ""),
                "target_x": target.get("target_x", ""),
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
                "source_reuse_pixels": str(
                    sum(1 for row in aligned if int_value(row, "previous_low2_source_reused"))
                ),
                "delta_signature_head": token.get("delta_signature_head", ""),
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
                "delta_signed": row.get("delta_signed", ""),
                "source_index": row.get("source_index", ""),
                "segment_offset": row.get("segment_offset", ""),
                "source_value_signed": row.get("source_value_signed", ""),
                "token_index": row.get("token_index", ""),
                "previous_low2_source_reused": row.get("previous_low2_source_reused", ""),
            }
        )
    return rows


def build_summary(
    guarded_summary: dict[str, str],
    miss_summary: dict[str, str],
    compatible_summary: dict[str, str],
    segment: bytes,
    source_rows: list[dict[str, int]],
    target_rows: list[dict[str, str]],
    token_rows: list[dict[str, str]],
    alignment_rows: list[dict[str, str]],
    previous_alignment_rows: list[dict[str, str]],
    *,
    issues: list[str],
) -> dict[str, str]:
    target_pixels = int_value(guarded_summary, "target_pixels")
    current_covered = int_value(guarded_summary, "combined_covered_pixels")
    remaining = int_value(guarded_summary, "remaining_nonzero_pixels")
    compatible = int_value(miss_summary, "low2_representable_pixels")
    impossible = int_value(miss_summary, "low2_impossible_pixels")
    compatible_best_lcs = int_value(compatible_summary, "best_lcs_pixels")
    source_gap = compatible_best_lcs - len(alignment_rows)
    previous_sources = used_source_indexes(previous_alignment_rows)
    reused_pixels = sum(1 for row in alignment_rows if int_value(row, "previous_low2_source_reused"))
    new_source_pixels = len(alignment_rows) - reused_pixels
    full_tokens = [row for row in token_rows if row.get("verdict") == "full"]
    partial_tokens = [row for row in token_rows if row.get("verdict") == "partial"]
    uncovered_tokens = [row for row in token_rows if row.get("verdict") == "uncovered"]
    full_pixels = sum(int_value(row, "pixels") for row in full_tokens)
    partial_pixels = sum(int_value(row, "aligned_pixels") for row in partial_tokens)
    uncovered_pixels = len(target_rows) - len(alignment_rows)
    potential_covered = min(target_pixels, current_covered + len(alignment_rows))
    potential_remaining = max(0, remaining - len(alignment_rows))
    target_gap = len(target_rows) - compatible
    source_alignment_gap_issue = 1 if source_gap else 0
    issue_rows = len(issues) + (1 if target_gap else 0) + source_alignment_gap_issue
    segment_offsets = [int_value(row, "segment_offset") for row in alignment_rows]

    if issue_rows:
        verdict = "shared_2700302b_reference_fixed_dy1_post_low2_restart_low2_selector_issues"
        next_action = "fix shared 0x2700302b post-low2 restart low2 selector inputs"
    elif len(alignment_rows) / compatible >= 0.50 if compatible else False:
        verdict = "shared_2700302b_reference_fixed_dy1_post_low2_restart_low2_selector_ready"
        next_action = (
            "measure guarded restart low2 replay for shared 0x2700302b; "
            f"restart selector adds {len(alignment_rows)} compatible pixels"
        )
    else:
        verdict = "shared_2700302b_reference_fixed_dy1_post_low2_restart_low2_selector_weak"
        next_action = (
            "seek alternate post-low2 selector for shared 0x2700302b; "
            f"restart low2 covers {len(alignment_rows)}/{compatible}"
        )

    return {
        "scope": "total",
        "archive": guarded_summary.get("archive", ""),
        "archive_tag": guarded_summary.get("archive_tag", ""),
        "pcx_name": guarded_summary.get("pcx_name", ""),
        "frontier_id": guarded_summary.get("frontier_id", ""),
        "dy": guarded_summary.get("dy", ""),
        "shift": guarded_summary.get("shift", ""),
        "source_transform": "low2_nonzero_restart_all",
        "segment_bytes": str(len(segment)),
        "source_bytes": str(len(source_rows)),
        "previous_low2_aligned_pixels": guarded_summary.get("low2_aligned_pixels", "0"),
        "previous_low2_used_source_bytes": str(len(previous_sources)),
        "target_pixels": str(target_pixels),
        "current_combined_covered_pixels": str(current_covered),
        "current_combined_covered_ratio": guarded_summary.get("combined_covered_ratio", "0"),
        "remaining_nonzero_pixels": str(remaining),
        "compatible_miss_pixels": str(compatible),
        "low2_impossible_pixels": str(impossible),
        "restart_aligned_pixels": str(len(alignment_rows)),
        "restart_aligned_ratio": float_text(len(alignment_rows) / compatible if compatible else 0.0),
        "restart_source_used_ratio": float_text(len(alignment_rows) / len(source_rows) if source_rows else 0.0),
        "restart_reused_source_pixels": str(reused_pixels),
        "restart_new_source_pixels": str(new_source_pixels),
        "full_token_rows": str(len(full_tokens)),
        "full_token_pixels": str(full_pixels),
        "partial_token_rows": str(len(partial_tokens)),
        "partial_token_pixels": str(partial_pixels),
        "uncovered_token_rows": str(len(uncovered_tokens)),
        "uncovered_pixels": str(uncovered_pixels),
        "first_segment_offset": str(min(segment_offsets) if segment_offsets else 0),
        "last_segment_offset": str(max(segment_offsets) if segment_offsets else 0),
        "compatible_best_lcs_pixels": str(compatible_best_lcs),
        "compatible_best_source_id": compatible_summary.get("best_source_id", ""),
        "source_alignment_gap_pixels": str(source_gap),
        "potential_combined_covered_pixels": str(potential_covered),
        "potential_combined_covered_ratio": float_text(potential_covered / target_pixels if target_pixels else 0.0),
        "potential_remaining_nonzero_pixels": str(potential_remaining),
        "selected_pixel_rows": str(len(alignment_rows)),
        "issue_rows": str(issue_rows),
        "restart_low2_selector_verdict": verdict,
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
  <div class="stat"><div class="label">Restart Aligned</div><div class="value">{html.escape(summary['restart_aligned_pixels'])}</div></div>
  <div class="stat"><div class="label">Aligned Ratio</div><div class="value">{html.escape(summary['restart_aligned_ratio'])}</div></div>
  <div class="stat"><div class="label">Potential Covered</div><div class="value">{html.escape(summary['potential_combined_covered_pixels'])}</div></div>
  <div class="stat"><div class="label">Remaining NZ</div><div class="value">{html.escape(summary['potential_remaining_nonzero_pixels'])}</div></div>
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
    guarded_summary = read_summary(args.guarded_summary)
    miss_summary = read_summary(args.miss_split_summary)
    compatible_summary = read_summary(args.compatible_source_summary)
    if not guarded_summary:
        issues.append("missing_guarded_summary")
    if not miss_summary:
        issues.append("missing_miss_split_summary")
    if not compatible_summary:
        issues.append("missing_compatible_source_summary")
    remaining_rows = read_csv(args.remaining_pixels)
    if not remaining_rows:
        issues.append("missing_remaining_pixels")
    previous_alignment_rows = read_csv(args.previous_low2_alignments)
    if not previous_alignment_rows:
        issues.append("missing_previous_low2_alignments")

    segment, load_issues = load_segment(args)
    issues.extend(load_issues)
    source_rows = low2_selector.low2_nonzero_source(segment)
    target_rows, token_source_rows = build_targets(remaining_rows)
    pairs = low2_selector.lcs_alignment(
        [row["value"] for row in source_rows],
        [int_value(row, "delta") for row in target_rows],
    )
    alignment_rows = build_alignment_rows(
        source_rows,
        target_rows,
        pairs,
        used_source_indexes(previous_alignment_rows),
    )
    token_rows = build_token_rows(token_source_rows, alignment_rows)
    selected_rows = build_selected_rows(alignment_rows)
    summary = build_summary(
        guarded_summary,
        miss_summary,
        compatible_summary,
        segment,
        source_rows,
        target_rows,
        token_rows,
        alignment_rows,
        previous_alignment_rows,
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
    parser = argparse.ArgumentParser(description="Derive a restart low2 selector for post-low2 compatible misses.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--frontiers", type=Path, default=DEFAULT_FRONTIERS)
    parser.add_argument("--comparisons", type=Path, default=DEFAULT_COMPARISONS)
    parser.add_argument("--guarded-summary", type=Path, default=DEFAULT_GUARDED_SUMMARY)
    parser.add_argument("--miss-split-summary", type=Path, default=DEFAULT_MISS_SPLIT_SUMMARY)
    parser.add_argument("--compatible-source-summary", type=Path, default=DEFAULT_COMPATIBLE_SOURCE_SUMMARY)
    parser.add_argument("--remaining-pixels", type=Path, default=DEFAULT_REMAINING_PIXELS)
    parser.add_argument("--previous-low2-alignments", type=Path, default=DEFAULT_PREVIOUS_LOW2_ALIGNMENTS)
    parser.add_argument("--archive-tag", default="L4_HJ")
    parser.add_argument("--pcx-name", default="dinodead.pcx")
    parser.add_argument("--frontier-id", type=int, default=6)
    parser.add_argument("--mix-entry-index", type=int, default=2)
    parser.add_argument("--title", default="Lands of Lore II .tex Shared 0x2700302b Post-low2 Restart Low2 Selector")
    args = parser.parse_args()
    summary, _tokens, _alignments, _selected = write_report(args)
    print(f"Restart aligned pixels: {summary['restart_aligned_pixels']}")
    print(f"Restart aligned ratio: {summary['restart_aligned_ratio']}")
    print(f"Potential covered pixels: {summary['potential_combined_covered_pixels']}")
    print(f"Verdict: {summary['restart_low2_selector_verdict']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
