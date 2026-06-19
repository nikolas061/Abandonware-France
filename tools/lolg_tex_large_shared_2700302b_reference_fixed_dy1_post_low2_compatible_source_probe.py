#!/usr/bin/env python3
"""Probe secondary sources for post-low2 low2-compatible misses in shared 0x2700302b."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import sys
from pathlib import Path

import lolg_tex_large_shared_2700302b_reference_fixed_dy1_residual_profile_probe as residual_profile
import lolg_tex_large_shared_2700302b_reference_fixed_dy1_small_delta_low2_selector_probe as low2_selector
import lolg_tex_large_shared_2700302b_reference_fixed_dy1_small_delta_mapping_probe as mapping_probe
import lolg_tex_large_shared_2700302b_reference_frontier_probe as frontier_probe
import lolg_tex_large_shared_2700302b_reference_literal_stream_probe as literal_probe


DEFAULT_OUTPUT = Path("output/tex_large_shared_2700302b_reference_fixed_dy1_post_low2_compatible_source_probe")
DEFAULT_FRONTIERS = frontier_probe.DEFAULT_FRONTIERS
DEFAULT_COMPARISONS = frontier_probe.DEFAULT_COMPARISONS
DEFAULT_GUARDED_SUMMARY = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_low2_guarded_replay_probe/summary.csv"
)
DEFAULT_MISS_SPLIT_SUMMARY = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_post_low2_small_delta_miss_split_probe/summary.csv"
)
DEFAULT_REMAINING_PIXELS = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_post_low2_residual_profile_probe/remaining_pixels.csv"
)
DEFAULT_LOW2_ALIGNMENTS = Path(
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
    "target_pixels",
    "current_combined_covered_pixels",
    "current_combined_covered_ratio",
    "remaining_nonzero_pixels",
    "compatible_miss_pixels",
    "low2_impossible_pixels",
    "source_rows",
    "best_source_id",
    "best_source_bytes",
    "best_lcs_pixels",
    "best_lcs_ratio",
    "best_source_match_ratio",
    "unused_low2_lcs_pixels",
    "best_gain_over_unused",
    "potential_combined_covered_pixels",
    "potential_combined_covered_ratio",
    "potential_remaining_nonzero_pixels",
    "issue_rows",
    "compatible_source_verdict",
    "next_action",
]

SOURCE_FIELDNAMES = [
    "rank",
    "source_id",
    "source_bytes",
    "target_pixels",
    "lcs_pixels",
    "lcs_ratio",
    "source_match_ratio",
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


def compatible_target(rows: list[dict[str, str]]) -> bytes:
    values: list[int] = []
    for row in rows:
        if row.get("residual_kind") != "small_delta":
            continue
        delta = int_value(row, "delta_signed")
        if delta in LOW2_DELTAS:
            values.append(delta & 0xFF)
    return bytes(values)


def used_source_indexes(rows: list[dict[str, str]]) -> set[int]:
    return {int_value(row, "source_index") for row in rows}


def load_segment(args: argparse.Namespace) -> bytes:
    load_args = argparse.Namespace(
        frontiers=args.frontiers,
        comparisons=args.comparisons,
        archive_tag=args.archive_tag,
        pcx_name=args.pcx_name,
        frontier_id=args.frontier_id,
        mix_entry_index=args.mix_entry_index,
    )
    _frontier, _comparison, _pixels, _width, segment, _issues = residual_profile.load_reference(load_args)
    return segment


def source_pools(segment: bytes, used_indexes: set[int]) -> dict[str, bytes]:
    low2_rows = low2_selector.low2_nonzero_source(segment)
    low3_nonzero = mapping_probe.transform_segment(segment, "low3_nonzero")
    low_nibble_small = mapping_probe.transform_segment(segment, "low_nibble_small")
    high3 = mapping_probe.transform_segment(segment, "high3_signed")
    return {
        "low2_nonzero_all": bytes(row["value"] for row in low2_rows),
        "low2_nonzero_unused": bytes(row["value"] for row in low2_rows if row["source_index"] not in used_indexes),
        "low2_signed_all": mapping_probe.transform_segment(segment, "low2_signed"),
        "low3_nonzero_all": low3_nonzero,
        "low3_representable_only": bytes(value for value in low3_nonzero if signed_byte(value) in LOW2_DELTAS),
        "low_nibble_small_representable": bytes(value for value in low_nibble_small if signed_byte(value) in LOW2_DELTAS),
        "high3_representable": bytes(value for value in high3 if signed_byte(value) in LOW2_DELTAS),
    }


def build_source_rows(pools: dict[str, bytes], target: bytes) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for source_id, source in pools.items():
        lcs = literal_probe.lcs_len(source, target)
        rows.append(
            {
                "rank": "0",
                "source_id": source_id,
                "source_bytes": str(len(source)),
                "target_pixels": str(len(target)),
                "lcs_pixels": str(lcs),
                "lcs_ratio": float_text(lcs / len(target) if target else 0.0),
                "source_match_ratio": float_text(lcs / len(source) if source else 0.0),
            }
        )
    rows.sort(
        key=lambda row: (
            float(row.get("lcs_ratio", "0") or 0),
            float(row.get("source_match_ratio", "0") or 0),
        ),
        reverse=True,
    )
    for rank, row in enumerate(rows, 1):
        row["rank"] = str(rank)
    return rows


def build_summary(
    guarded_summary: dict[str, str],
    miss_summary: dict[str, str],
    source_rows: list[dict[str, str]],
    issues: list[str],
) -> dict[str, str]:
    best = source_rows[0] if source_rows else {}
    target_pixels = int_value(guarded_summary, "target_pixels")
    current_covered = int_value(guarded_summary, "combined_covered_pixels")
    remaining = int_value(guarded_summary, "remaining_nonzero_pixels")
    compatible = int_value(miss_summary, "low2_representable_pixels")
    impossible = int_value(miss_summary, "low2_impossible_pixels")
    best_lcs = int_value(best, "lcs_pixels")
    unused = next((row for row in source_rows if row.get("source_id") == "low2_nonzero_unused"), {})
    unused_lcs = int_value(unused, "lcs_pixels")
    potential_covered = min(target_pixels, current_covered + best_lcs)
    potential_remaining = max(0, remaining - best_lcs)
    issue_rows = len(issues)

    if issue_rows:
        verdict = "shared_2700302b_reference_fixed_dy1_post_low2_compatible_source_issues"
        next_action = "fix shared 0x2700302b post-low2 compatible source inputs"
    elif best.get("source_id") == "low2_nonzero_all" and best_lcs > unused_lcs * 2:
        verdict = "shared_2700302b_reference_fixed_dy1_post_low2_low2_restart_promising"
        next_action = (
            "derive guarded restart/phase low2 selector for shared 0x2700302b compatible misses; "
            f"restart low2 covers {best_lcs}/{compatible} compatible pixels"
        )
    elif best_lcs > unused_lcs:
        verdict = "shared_2700302b_reference_fixed_dy1_post_low2_alternate_source_promising"
        next_action = (
            "derive alternate source selector for shared 0x2700302b compatible misses; "
            f"{best.get('source_id', '')} covers {best_lcs}/{compatible}"
        )
    else:
        verdict = "shared_2700302b_reference_fixed_dy1_post_low2_compatible_source_weak"
        next_action = (
            "prioritize non-low2 small-delta producer for shared 0x2700302b; "
            f"best compatible source covers only {best_lcs}/{compatible}"
        )

    return {
        "scope": "total",
        "archive": guarded_summary.get("archive", ""),
        "archive_tag": guarded_summary.get("archive_tag", ""),
        "pcx_name": guarded_summary.get("pcx_name", ""),
        "frontier_id": guarded_summary.get("frontier_id", ""),
        "dy": guarded_summary.get("dy", ""),
        "shift": guarded_summary.get("shift", ""),
        "target_pixels": str(target_pixels),
        "current_combined_covered_pixels": str(current_covered),
        "current_combined_covered_ratio": guarded_summary.get("combined_covered_ratio", "0"),
        "remaining_nonzero_pixels": str(remaining),
        "compatible_miss_pixels": str(compatible),
        "low2_impossible_pixels": str(impossible),
        "source_rows": str(len(source_rows)),
        "best_source_id": best.get("source_id", ""),
        "best_source_bytes": best.get("source_bytes", "0"),
        "best_lcs_pixels": str(best_lcs),
        "best_lcs_ratio": best.get("lcs_ratio", "0"),
        "best_source_match_ratio": best.get("source_match_ratio", "0"),
        "unused_low2_lcs_pixels": str(unused_lcs),
        "best_gain_over_unused": str(best_lcs - unused_lcs),
        "potential_combined_covered_pixels": str(potential_covered),
        "potential_combined_covered_ratio": float_text(potential_covered / target_pixels if target_pixels else 0.0),
        "potential_remaining_nonzero_pixels": str(potential_remaining),
        "issue_rows": str(issue_rows),
        "compatible_source_verdict": verdict,
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


def build_html(summary: dict[str, str], source_rows: list[dict[str, str]], output_dir: Path, title: str) -> str:
    payload = {"summary": summary, "sources": source_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (("summary", output_dir / "summary.csv"), ("sources", output_dir / "sources.csv"))
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
  <div class="stat"><div class="label">Best Source</div><div class="value">{html.escape(summary['best_source_id'])}</div></div>
  <div class="stat"><div class="label">Best LCS</div><div class="value">{html.escape(summary['best_lcs_pixels'])}</div></div>
  <div class="stat"><div class="label">Potential Covered</div><div class="value">{html.escape(summary['potential_combined_covered_pixels'])}</div></div>
  <div class="stat"><div class="label">Remaining NZ</div><div class="value">{html.escape(summary['potential_remaining_nonzero_pixels'])}</div></div>
</div>
<p>{html.escape(summary['next_action'])}</p>
<h2>Summary</h2>{render_table([summary], SUMMARY_FIELDNAMES)}
<h2>Sources</h2>{render_table(source_rows, SOURCE_FIELDNAMES)}
<script type="application/json" id="data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> tuple[dict[str, str], list[dict[str, str]]]:
    args.output.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    guarded_summary = read_summary(args.guarded_summary)
    miss_summary = read_summary(args.miss_split_summary)
    if not guarded_summary:
        issues.append("missing_guarded_summary")
    if not miss_summary:
        issues.append("missing_miss_split_summary")
    remaining_rows = read_csv(args.remaining_pixels)
    if not remaining_rows:
        issues.append("missing_remaining_pixels")
    alignment_rows = read_csv(args.low2_alignments)
    if not alignment_rows:
        issues.append("missing_low2_alignments")
    target = compatible_target(remaining_rows)
    segment = load_segment(args)
    pools = source_pools(segment, used_source_indexes(alignment_rows))
    source_rows = build_source_rows(pools, target)
    summary = build_summary(guarded_summary, miss_summary, source_rows, issues)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "sources.csv", SOURCE_FIELDNAMES, source_rows)
    (args.output / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""), encoding="utf-8")
    (args.output / "index.html").write_text(build_html(summary, source_rows, args.output, args.title), encoding="utf-8")
    return summary, source_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe compatible miss sources after guarded low2 replay.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--frontiers", type=Path, default=DEFAULT_FRONTIERS)
    parser.add_argument("--comparisons", type=Path, default=DEFAULT_COMPARISONS)
    parser.add_argument("--guarded-summary", type=Path, default=DEFAULT_GUARDED_SUMMARY)
    parser.add_argument("--miss-split-summary", type=Path, default=DEFAULT_MISS_SPLIT_SUMMARY)
    parser.add_argument("--remaining-pixels", type=Path, default=DEFAULT_REMAINING_PIXELS)
    parser.add_argument("--low2-alignments", type=Path, default=DEFAULT_LOW2_ALIGNMENTS)
    parser.add_argument("--archive-tag", default="L4_HJ")
    parser.add_argument("--pcx-name", default="dinodead.pcx")
    parser.add_argument("--frontier-id", type=int, default=6)
    parser.add_argument("--mix-entry-index", type=int, default=2)
    parser.add_argument("--title", default="Lands of Lore II .tex Shared 0x2700302b Post-low2 Compatible Source Probe")
    args = parser.parse_args()
    summary, _sources = write_report(args)
    print(f"Best source: {summary['best_source_id']}")
    print(f"Best LCS pixels: {summary['best_lcs_pixels']}")
    print(f"Potential covered pixels: {summary['potential_combined_covered_pixels']}")
    print(f"Verdict: {summary['compatible_source_verdict']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
