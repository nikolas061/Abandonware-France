#!/usr/bin/env python3
"""Probe large-delta/source-zero sources after high3 replay for shared 0x2700302b."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import sys
from pathlib import Path

import lolg_tex_large_shared_2700302b_reference_fixed_dy1_residual_profile_probe as residual_profile
import lolg_tex_large_shared_2700302b_reference_fixed_dy1_small_delta_mapping_probe as mapping_probe
import lolg_tex_large_shared_2700302b_reference_frontier_probe as frontier_probe
import lolg_tex_large_shared_2700302b_reference_literal_stream_probe as literal_probe


DEFAULT_OUTPUT = Path("output/tex_large_shared_2700302b_reference_fixed_dy1_post_high3_large_delta_source_probe")
DEFAULT_FRONTIERS = frontier_probe.DEFAULT_FRONTIERS
DEFAULT_COMPARISONS = frontier_probe.DEFAULT_COMPARISONS
DEFAULT_POST_HIGH3_SUMMARY = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_post_high3_residual_profile_probe/summary.csv"
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
    "remaining_nonzero_pixels",
    "large_delta_pixels",
    "source_zero_large_delta_pixels",
    "source_nonzero_large_delta_pixels",
    "candidate_rows",
    "best_target_id",
    "best_source_id",
    "best_source_bytes",
    "best_target_pixels",
    "best_lcs_pixels",
    "best_lcs_ratio",
    "best_source_match_ratio",
    "best_large_value_source_id",
    "best_large_value_lcs_pixels",
    "best_large_value_lcs_ratio",
    "best_source_zero_source_id",
    "best_source_zero_lcs_pixels",
    "best_source_zero_lcs_ratio",
    "potential_source_zero_covered_pixels",
    "issue_rows",
    "large_delta_source_verdict",
    "next_action",
]

CANDIDATE_FIELDNAMES = [
    "rank",
    "target_id",
    "source_id",
    "target_pixels",
    "source_bytes",
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


def hex_value(row: dict[str, str], field: str) -> int:
    raw = row.get(field, "0")
    return int(raw, 16) if raw else 0


def float_text(value: float) -> str:
    return f"{value:.6f}"


def signed_byte(value: int) -> int:
    return ((value + 128) & 0xFF) - 128


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    try:
        return os.path.relpath(Path(path_text), base_dir)
    except ValueError:
        return str(path_text)


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


def large_delta_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [row for row in rows if row.get("residual_kind") == "large_delta"]


def source_zero(row: dict[str, str]) -> bool:
    return hex_value(row, "source_value_hex") == 0


def stream(rows: list[dict[str, str]], kind: str) -> bytes:
    if kind == "delta":
        return bytes(int_value(row, "delta_signed") & 0xFF for row in rows)
    if kind == "target_value":
        return bytes(hex_value(row, "target_value_hex") for row in rows)
    if kind == "source_value":
        return bytes(hex_value(row, "source_value_hex") for row in rows)
    raise ValueError(f"unknown target stream kind: {kind}")


def range_filtered(segment: bytes, low: int, high: int) -> bytes:
    return bytes(value for value in segment if low <= value <= high)


def source_pools(segment: bytes) -> dict[str, bytes]:
    return {
        "segment_identity": segment,
        "segment_nonzero": bytes(value for value in segment if value != 0),
        "segment_30_bf": range_filtered(segment, 0x30, 0xBF),
        "segment_40_bf": range_filtered(segment, 0x40, 0xBF),
        "segment_50_bf": range_filtered(segment, 0x50, 0xBF),
        "segment_54_bf": range_filtered(segment, 0x54, 0xBF),
        "segment_58_bf": range_filtered(segment, 0x58, 0xBF),
        "segment_50_af": range_filtered(segment, 0x50, 0xAF),
        "segment_50_7f": range_filtered(segment, 0x50, 0x7F),
        "high_nibble_signed": mapping_probe.transform_segment(segment, "high_nibble_signed"),
        "low_nibble_signed": mapping_probe.transform_segment(segment, "low_nibble_signed"),
        "high3_signed": mapping_probe.transform_segment(segment, "high3_signed"),
        "low3_signed": mapping_probe.transform_segment(segment, "low3_signed"),
    }


def target_streams(large_rows: list[dict[str, str]]) -> dict[str, bytes]:
    zero_rows = [row for row in large_rows if source_zero(row)]
    nonzero_rows = [row for row in large_rows if not source_zero(row)]
    return {
        "large_delta_signed": stream(large_rows, "delta"),
        "large_target_value": stream(large_rows, "target_value"),
        "large_source_value": stream(large_rows, "source_value"),
        "source_zero_delta_signed": stream(zero_rows, "delta"),
        "source_zero_target_value": stream(zero_rows, "target_value"),
        "source_nonzero_delta_signed": stream(nonzero_rows, "delta"),
        "source_nonzero_target_value": stream(nonzero_rows, "target_value"),
    }


def build_candidate_rows(sources: dict[str, bytes], targets: dict[str, bytes]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for target_id, target in targets.items():
        for source_id, source in sources.items():
            lcs = literal_probe.lcs_len(source, target)
            rows.append(
                {
                    "rank": "0",
                    "target_id": target_id,
                    "source_id": source_id,
                    "target_pixels": str(len(target)),
                    "source_bytes": str(len(source)),
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


def best_for(rows: list[dict[str, str]], target_id: str) -> dict[str, str]:
    matches = [row for row in rows if row.get("target_id") == target_id]
    return matches[0] if matches else {}


def build_summary(
    post_summary: dict[str, str],
    large_rows: list[dict[str, str]],
    candidate_rows: list[dict[str, str]],
    issues: list[str],
) -> dict[str, str]:
    best = candidate_rows[0] if candidate_rows else {}
    large_value = best_for(candidate_rows, "large_target_value")
    source_zero_value = best_for(candidate_rows, "source_zero_target_value")
    source_zero_rows = [row for row in large_rows if source_zero(row)]
    source_nonzero_rows = [row for row in large_rows if not source_zero(row)]
    source_zero_lcs = int_value(source_zero_value, "lcs_pixels")
    issue_rows = len(issues)

    if issue_rows:
        verdict = "shared_2700302b_reference_fixed_dy1_post_high3_large_delta_source_issues"
        next_action = "fix shared 0x2700302b post-high3 large-delta source inputs"
    elif source_zero_lcs == len(source_zero_rows) and source_zero_rows:
        verdict = "shared_2700302b_reference_fixed_dy1_post_high3_source_zero_literal_ready"
        next_action = (
            "derive guarded source-zero literal replay after high3 for shared 0x2700302b; "
            f"{source_zero_lcs}/{len(source_zero_rows)} source-zero large deltas match"
        )
    else:
        verdict = "shared_2700302b_reference_fixed_dy1_post_high3_large_delta_source_profiled"
        next_action = (
            "derive large-delta selector after high3 for shared 0x2700302b; "
            f"best large target source covers {large_value.get('lcs_pixels', '0')}/{len(large_rows)}"
        )

    return {
        "scope": "total",
        "archive": post_summary.get("archive", ""),
        "archive_tag": post_summary.get("archive_tag", ""),
        "pcx_name": post_summary.get("pcx_name", ""),
        "frontier_id": post_summary.get("frontier_id", ""),
        "dy": post_summary.get("dy", ""),
        "shift": post_summary.get("shift", ""),
        "remaining_nonzero_pixels": post_summary.get("remaining_nonzero_pixels", "0"),
        "large_delta_pixels": str(len(large_rows)),
        "source_zero_large_delta_pixels": str(len(source_zero_rows)),
        "source_nonzero_large_delta_pixels": str(len(source_nonzero_rows)),
        "candidate_rows": str(len(candidate_rows)),
        "best_target_id": best.get("target_id", ""),
        "best_source_id": best.get("source_id", ""),
        "best_source_bytes": best.get("source_bytes", "0"),
        "best_target_pixels": best.get("target_pixels", "0"),
        "best_lcs_pixels": best.get("lcs_pixels", "0"),
        "best_lcs_ratio": best.get("lcs_ratio", "0"),
        "best_source_match_ratio": best.get("source_match_ratio", "0"),
        "best_large_value_source_id": large_value.get("source_id", ""),
        "best_large_value_lcs_pixels": large_value.get("lcs_pixels", "0"),
        "best_large_value_lcs_ratio": large_value.get("lcs_ratio", "0"),
        "best_source_zero_source_id": source_zero_value.get("source_id", ""),
        "best_source_zero_lcs_pixels": str(source_zero_lcs),
        "best_source_zero_lcs_ratio": source_zero_value.get("lcs_ratio", "0"),
        "potential_source_zero_covered_pixels": str(source_zero_lcs),
        "issue_rows": str(issue_rows),
        "large_delta_source_verdict": verdict,
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
    candidate_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "candidates": candidate_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (("summary", output_dir / "summary.csv"), ("candidates", output_dir / "candidates.csv"))
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
  <div class="stat"><div class="label">Large Delta</div><div class="value">{html.escape(summary['large_delta_pixels'])}</div></div>
  <div class="stat"><div class="label">Source Zero</div><div class="value">{html.escape(summary['source_zero_large_delta_pixels'])}</div></div>
  <div class="stat"><div class="label">Zero LCS</div><div class="value">{html.escape(summary['best_source_zero_lcs_pixels'])}</div></div>
  <div class="stat"><div class="label">Best Source</div><div class="value">{html.escape(summary['best_source_id'])}</div></div>
</div>
<p>{html.escape(summary['next_action'])}</p>
<h2>Summary</h2>{render_table([summary], SUMMARY_FIELDNAMES)}
<h2>Candidates</h2>{render_table(candidate_rows[:120], CANDIDATE_FIELDNAMES)}
<script type="application/json" id="data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> tuple[dict[str, str], list[dict[str, str]]]:
    args.output.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    post_summary = read_summary(args.post_high3_summary)
    if not post_summary:
        issues.append("missing_post_high3_summary")
    remaining_rows = read_csv(args.remaining_pixels)
    if not remaining_rows:
        issues.append("missing_remaining_pixels")
    large_rows = large_delta_rows(remaining_rows)
    if len(large_rows) != int_value(post_summary, "remaining_large_delta_pixels"):
        issues.append("large_delta_summary_gap")
    segment = load_segment(args)
    candidates = build_candidate_rows(source_pools(segment), target_streams(large_rows))
    summary = build_summary(post_summary, large_rows, candidates, issues)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "candidates.csv", CANDIDATE_FIELDNAMES, candidates)
    (args.output / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""), encoding="utf-8")
    (args.output / "index.html").write_text(build_html(summary, candidates, args.output, args.title), encoding="utf-8")
    return summary, candidates


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe post-high3 large-delta sources for shared 0x2700302b.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--frontiers", type=Path, default=DEFAULT_FRONTIERS)
    parser.add_argument("--comparisons", type=Path, default=DEFAULT_COMPARISONS)
    parser.add_argument("--post-high3-summary", type=Path, default=DEFAULT_POST_HIGH3_SUMMARY)
    parser.add_argument("--remaining-pixels", type=Path, default=DEFAULT_REMAINING_PIXELS)
    parser.add_argument("--archive-tag", default="L4_HJ")
    parser.add_argument("--pcx-name", default="dinodead.pcx")
    parser.add_argument("--frontier-id", type=int, default=6)
    parser.add_argument("--mix-entry-index", type=int, default=2)
    parser.add_argument("--title", default="Lands of Lore II .tex Shared 0x2700302b Post-high3 Large-Delta Source Probe")
    args = parser.parse_args()
    summary, _candidates = write_report(args)
    print(f"Large-delta pixels: {summary['large_delta_pixels']}")
    print(f"Source-zero large deltas: {summary['source_zero_large_delta_pixels']}")
    print(f"Best source-zero LCS: {summary['best_source_zero_lcs_pixels']}")
    print(f"Verdict: {summary['large_delta_source_verdict']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
