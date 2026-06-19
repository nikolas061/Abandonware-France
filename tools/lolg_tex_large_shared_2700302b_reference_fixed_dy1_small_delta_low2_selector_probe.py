#!/usr/bin/env python3
"""Derive a monotone low2 selector for fixed-dy1 small-delta tokens in shared 0x2700302b."""

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
import lolg_tex_large_shared_2700302b_reference_fixed_dy1_small_delta_mapping_probe as mapping_probe
import lolg_tex_large_shared_2700302b_reference_frontier_probe as frontier_probe


DEFAULT_OUTPUT = Path("output/tex_large_shared_2700302b_reference_fixed_dy1_small_delta_low2_selector_probe")
DEFAULT_FRONTIERS = frontier_probe.DEFAULT_FRONTIERS
DEFAULT_COMPARISONS = frontier_probe.DEFAULT_COMPARISONS
DEFAULT_GRAMMAR_SUMMARY = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_small_delta_grammar_probe/summary.csv"
)
DEFAULT_RESIDUAL_PIXELS = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_residual_profile_probe/residual_pixels.csv"
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
    "small_delta_pixels",
    "small_delta_token_rows",
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
    "issue_rows",
    "low2_selector_verdict",
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
    "delta_signature_head",
    "verdict",
]

ALIGNMENT_FIELDNAMES = [
    "rank",
    "source_index",
    "segment_offset",
    "source_value_signed",
    "target_index",
    "token_index",
    "target_y",
    "target_x",
    "delta_signed",
    "token_pixels",
    "token_aligned_pixels",
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


def signed_byte(value: int) -> int:
    return ((value + 128) & 0xFF) - 128


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    try:
        return os.path.relpath(Path(path_text), base_dir)
    except ValueError:
        return str(path_text)


def is_small_delta(row: dict[str, str], max_abs_delta: int) -> bool:
    value = abs(int_value(row, "delta_signed"))
    return 1 <= value <= max_abs_delta


def low2_nonzero_source(segment: bytes) -> list[dict[str, int]]:
    rows: list[dict[str, int]] = []
    source_index = 0
    for segment_offset, value in enumerate(segment):
        transformed = mapping_probe.signed_bits(value, 2)
        if transformed == 0:
            continue
        rows.append(
            {
                "source_index": source_index,
                "segment_offset": segment_offset,
                "value": transformed,
                "value_signed": signed_byte(transformed),
            }
        )
        source_index += 1
    return rows


def build_targets(
    pixel_rows: list[dict[str, str]],
    *,
    max_abs_delta: int,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
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

    for row in pixel_rows:
        y = int_value(row, "target_y")
        x = int_value(row, "target_x")
        small = is_small_delta(row, max_abs_delta)
        contiguous = y == previous_y and x == previous_x + 1
        if current and (not small or not contiguous):
            flush()
        if small:
            current.append(row)
        previous_y = y
        previous_x = x
    flush()
    return targets, tokens


def lcs_alignment(source: list[int], target: list[int]) -> list[tuple[int, int]]:
    if not source or not target:
        return []
    width = len(target) + 1
    table = [[0] * width for _ in range(len(source) + 1)]
    for left_index, left_value in enumerate(source, 1):
        previous = table[left_index - 1]
        current = table[left_index]
        for right_index, right_value in enumerate(target, 1):
            if left_value == right_value:
                current[right_index] = previous[right_index - 1] + 1
            else:
                current[right_index] = max(previous[right_index], current[right_index - 1])

    pairs: list[tuple[int, int]] = []
    left_index = len(source)
    right_index = len(target)
    while left_index > 0 and right_index > 0:
        if source[left_index - 1] == target[right_index - 1]:
            pairs.append((left_index - 1, right_index - 1))
            left_index -= 1
            right_index -= 1
        elif table[left_index - 1][right_index] >= table[left_index][right_index - 1]:
            left_index -= 1
        else:
            right_index -= 1
    pairs.reverse()
    return pairs


def build_alignment_rows(
    source_rows: list[dict[str, int]],
    targets: list[dict[str, str]],
    pairs: list[tuple[int, int]],
) -> list[dict[str, str]]:
    token_counts: dict[str, int] = defaultdict(int)
    for _source_index, target_index in pairs:
        token_counts[targets[target_index].get("token_index", "")] += 1
    token_pixels = {
        target.get("token_index", ""): int_value(target, "token_pixel_index") + 1
        for target in targets
    }
    rows: list[dict[str, str]] = []
    for rank, (source_index, target_index) in enumerate(pairs, 1):
        source = source_rows[source_index]
        target = targets[target_index]
        rows.append(
            {
                "rank": str(rank),
                "source_index": str(source["source_index"]),
                "segment_offset": str(source["segment_offset"]),
                "source_value_signed": str(source["value_signed"]),
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
                "delta_signature_head": token.get("delta_signature_head", ""),
                "verdict": verdict,
            }
        )
    return rows


def build_summary(
    grammar_summary: dict[str, str],
    segment: bytes,
    source_rows: list[dict[str, int]],
    target_rows: list[dict[str, str]],
    token_rows: list[dict[str, str]],
    alignment_rows: list[dict[str, str]],
    *,
    issues: list[str],
) -> dict[str, str]:
    aligned_pixels = len(alignment_rows)
    target_pixels = len(target_rows)
    source_bytes = len(source_rows)
    full_tokens = [row for row in token_rows if row.get("verdict") == "full"]
    partial_tokens = [row for row in token_rows if row.get("verdict") == "partial"]
    uncovered_tokens = [row for row in token_rows if row.get("verdict") == "uncovered"]
    full_pixels = sum(int_value(row, "pixels") for row in full_tokens)
    partial_pixels = sum(int_value(row, "aligned_pixels") for row in partial_tokens)
    uncovered_pixels = target_pixels - aligned_pixels
    issue_rows = len(issues)
    aligned_ratio = aligned_pixels / target_pixels if target_pixels else 0.0
    source_ratio = aligned_pixels / source_bytes if source_bytes else 0.0
    if issue_rows:
        verdict = "shared_2700302b_reference_fixed_dy1_small_delta_low2_selector_issues"
        next_action = "fix shared 0x2700302b low2 selector inputs"
    elif aligned_ratio >= 0.30 and source_ratio >= 0.75:
        verdict = "shared_2700302b_reference_fixed_dy1_small_delta_low2_selector_ready"
        next_action = (
            "derive guarded low2 signed replay for shared 0x2700302b small-delta stream; "
            f"monotone selector covers {aligned_pixels}/{target_pixels} small-delta pixels"
        )
    else:
        verdict = "shared_2700302b_reference_fixed_dy1_small_delta_low2_selector_weak"
        next_action = (
            "search alternate selector for shared 0x2700302b small-delta stream; "
            f"low2 monotone selector covers {aligned_pixels}/{target_pixels}"
        )
    segment_offsets = [int_value(row, "segment_offset") for row in alignment_rows]
    return {
        "scope": "total",
        "archive": grammar_summary.get("archive", ""),
        "archive_tag": grammar_summary.get("archive_tag", ""),
        "pcx_name": grammar_summary.get("pcx_name", ""),
        "frontier_id": grammar_summary.get("frontier_id", ""),
        "dy": grammar_summary.get("dy", ""),
        "shift": grammar_summary.get("shift", ""),
        "source_transform": "low2_nonzero",
        "segment_bytes": str(len(segment)),
        "source_bytes": str(source_bytes),
        "small_delta_pixels": str(target_pixels),
        "small_delta_token_rows": str(len(token_rows)),
        "aligned_pixels": str(aligned_pixels),
        "aligned_ratio": float_text(aligned_ratio),
        "source_used_ratio": float_text(source_ratio),
        "full_token_rows": str(len(full_tokens)),
        "full_token_pixels": str(full_pixels),
        "partial_token_rows": str(len(partial_tokens)),
        "partial_token_pixels": str(partial_pixels),
        "uncovered_token_rows": str(len(uncovered_tokens)),
        "uncovered_pixels": str(uncovered_pixels),
        "first_segment_offset": str(min(segment_offsets) if segment_offsets else 0),
        "last_segment_offset": str(max(segment_offsets) if segment_offsets else 0),
        "issue_rows": str(issue_rows),
        "low2_selector_verdict": verdict,
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
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "tokens": token_rows, "alignments": alignment_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary", output_dir / "summary.csv"),
            ("tokens", output_dir / "tokens.csv"),
            ("alignments", output_dir / "alignments.csv"),
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
  <div class="stat"><div class="label">Aligned Pixels</div><div class="value">{html.escape(summary['aligned_pixels'])}</div></div>
  <div class="stat"><div class="label">Aligned Ratio</div><div class="value">{html.escape(summary['aligned_ratio'])}</div></div>
  <div class="stat"><div class="label">Source Used</div><div class="value">{html.escape(summary['source_used_ratio'])}</div></div>
  <div class="stat"><div class="label">Full Tokens</div><div class="value">{html.escape(summary['full_token_rows'])}</div></div>
</div>
<p>{html.escape(summary['next_action'])}</p>
<h2>Summary</h2>{render_table([summary], SUMMARY_FIELDNAMES)}
<h2>Tokens</h2>{render_table(token_rows, TOKEN_FIELDNAMES)}
<h2>Alignments</h2>{render_table(alignment_rows[:180], ALIGNMENT_FIELDNAMES)}
<script type="application/json" id="data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    args.output.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    grammar_summary = read_summary(args.grammar_summary)
    if not grammar_summary:
        issues.append("missing_grammar_summary")
    residual_rows = read_csv(args.residual_pixels)
    if not residual_rows:
        issues.append("missing_residual_pixels")
    load_args = argparse.Namespace(
        frontiers=args.frontiers,
        comparisons=args.comparisons,
        archive_tag=args.archive_tag,
        pcx_name=args.pcx_name,
        frontier_id=args.frontier_id,
        mix_entry_index=args.mix_entry_index,
    )
    _frontier, _comparison, _pixels, _width, segment, load_issues = residual_profile.load_reference(load_args)
    issues.extend(load_issues)
    source_rows = low2_nonzero_source(segment)
    target_rows, token_source_rows = build_targets(residual_rows, max_abs_delta=args.max_abs_delta)
    source_values = [row["value"] for row in source_rows]
    target_values = [int_value(row, "delta") for row in target_rows]
    pairs = lcs_alignment(source_values, target_values)
    alignment_rows = build_alignment_rows(source_rows, target_rows, pairs)
    token_rows = build_token_rows(token_source_rows, alignment_rows)
    summary = build_summary(
        grammar_summary,
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
    (args.output / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""), encoding="utf-8")
    (args.output / "index.html").write_text(
        build_html(summary, token_rows, alignment_rows, args.output, args.title),
        encoding="utf-8",
    )
    return summary, token_rows, alignment_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Derive a low2 selector for shared 0x2700302b small deltas.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--frontiers", type=Path, default=DEFAULT_FRONTIERS)
    parser.add_argument("--comparisons", type=Path, default=DEFAULT_COMPARISONS)
    parser.add_argument("--grammar-summary", type=Path, default=DEFAULT_GRAMMAR_SUMMARY)
    parser.add_argument("--residual-pixels", type=Path, default=DEFAULT_RESIDUAL_PIXELS)
    parser.add_argument("--archive-tag", default="L4_HJ")
    parser.add_argument("--pcx-name", default="dinodead.pcx")
    parser.add_argument("--frontier-id", type=int, default=6)
    parser.add_argument("--mix-entry-index", type=int, default=2)
    parser.add_argument("--max-abs-delta", type=int, default=3)
    parser.add_argument("--title", default="Lands of Lore II .tex Shared 0x2700302b Fixed dy1 Low2 Selector")
    args = parser.parse_args()
    summary, _tokens, _alignments = write_report(args)
    print(f"Aligned pixels: {summary['aligned_pixels']}")
    print(f"Aligned ratio: {summary['aligned_ratio']}")
    print(f"Source used ratio: {summary['source_used_ratio']}")
    print(f"Verdict: {summary['low2_selector_verdict']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
