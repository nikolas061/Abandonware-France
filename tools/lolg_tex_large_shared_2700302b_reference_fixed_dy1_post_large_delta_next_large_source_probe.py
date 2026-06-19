#!/usr/bin/env python3
"""Probe next large-delta sources after large-delta replay for shared 0x2700302b."""

from __future__ import annotations

import argparse
import csv
import html
import json
import sys
from pathlib import Path

import lolg_tex_large_shared_2700302b_reference_fixed_dy1_post_high3_large_delta_source_probe as source_probe


DEFAULT_OUTPUT = Path("output/tex_large_shared_2700302b_reference_fixed_dy1_post_large_delta_next_large_source_probe")
DEFAULT_FRONTIERS = source_probe.DEFAULT_FRONTIERS
DEFAULT_COMPARISONS = source_probe.DEFAULT_COMPARISONS
DEFAULT_POST_LARGE_DELTA_SUMMARY = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_post_large_delta_residual_profile_probe/summary.csv"
)
DEFAULT_REMAINING_PIXELS = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_post_large_delta_residual_profile_probe/remaining_pixels.csv"
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
    "issue_rows",
    "next_large_source_verdict",
    "next_action",
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


def build_summary(
    post_summary: dict[str, str],
    large_rows: list[dict[str, str]],
    candidate_rows: list[dict[str, str]],
    issues: list[str],
) -> dict[str, str]:
    best = candidate_rows[0] if candidate_rows else {}
    large_value = source_probe.best_for(candidate_rows, "large_target_value")
    source_zero_value = source_probe.best_for(candidate_rows, "source_zero_target_value")
    source_zero_rows = [row for row in large_rows if source_probe.source_zero(row)]
    source_nonzero_rows = [row for row in large_rows if not source_probe.source_zero(row)]
    large_value_lcs = int_value(large_value, "lcs_pixels")
    issue_rows = len(issues)

    if issue_rows:
        verdict = "shared_2700302b_reference_fixed_dy1_post_large_delta_next_large_source_issues"
        next_action = "fix shared 0x2700302b post-large-delta source inputs"
    elif large_rows and large_value_lcs / len(large_rows) >= 0.40:
        verdict = "shared_2700302b_reference_fixed_dy1_post_large_delta_next_large_source_promising"
        next_action = (
            "derive second large-delta selector after large-delta replay for shared 0x2700302b; "
            f"{large_value.get('source_id', '')} covers {large_value_lcs}/{len(large_rows)}"
        )
    else:
        verdict = "shared_2700302b_reference_fixed_dy1_post_large_delta_next_large_source_weak"
        next_action = (
            "search alternate residual producer after large-delta replay for shared 0x2700302b; "
            f"best large target source covers {large_value_lcs}/{len(large_rows)}"
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
        "best_large_value_lcs_pixels": str(large_value_lcs),
        "best_large_value_lcs_ratio": large_value.get("lcs_ratio", "0"),
        "best_source_zero_source_id": source_zero_value.get("source_id", ""),
        "best_source_zero_lcs_pixels": source_zero_value.get("lcs_pixels", "0"),
        "best_source_zero_lcs_ratio": source_zero_value.get("lcs_ratio", "0"),
        "issue_rows": str(issue_rows),
        "next_large_source_verdict": verdict,
        "next_action": next_action,
    }


def build_html(
    summary: dict[str, str],
    candidate_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "candidates": candidate_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(source_probe.relative_href(path, output_dir))}">{html.escape(label)}</a>'
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
  <div class="stat"><div class="label">Best LCS</div><div class="value">{html.escape(summary['best_large_value_lcs_pixels'])}</div></div>
  <div class="stat"><div class="label">Best Source</div><div class="value">{html.escape(summary['best_large_value_source_id'])}</div></div>
</div>
<p>{html.escape(summary['next_action'])}</p>
<h2>Summary</h2>{source_probe.render_table([summary], SUMMARY_FIELDNAMES)}
<h2>Candidates</h2>{source_probe.render_table(candidate_rows[:120], source_probe.CANDIDATE_FIELDNAMES)}
<script type="application/json" id="data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> tuple[dict[str, str], list[dict[str, str]]]:
    args.output.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    post_summary = read_summary(args.post_large_delta_summary)
    if not post_summary:
        issues.append("missing_post_large_delta_summary")
    remaining_rows = read_csv(args.remaining_pixels)
    if not remaining_rows:
        issues.append("missing_remaining_pixels")
    large_rows = source_probe.large_delta_rows(remaining_rows)
    if len(large_rows) != int_value(post_summary, "remaining_large_delta_pixels"):
        issues.append("large_delta_summary_gap")
    segment = source_probe.load_segment(args)
    candidates = source_probe.build_candidate_rows(source_probe.source_pools(segment), source_probe.target_streams(large_rows))
    summary = build_summary(post_summary, large_rows, candidates, issues)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "candidates.csv", source_probe.CANDIDATE_FIELDNAMES, candidates)
    (args.output / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""), encoding="utf-8")
    (args.output / "index.html").write_text(build_html(summary, candidates, args.output, args.title), encoding="utf-8")
    return summary, candidates


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe next large-delta sources after large-delta replay.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--frontiers", type=Path, default=DEFAULT_FRONTIERS)
    parser.add_argument("--comparisons", type=Path, default=DEFAULT_COMPARISONS)
    parser.add_argument("--post-large-delta-summary", type=Path, default=DEFAULT_POST_LARGE_DELTA_SUMMARY)
    parser.add_argument("--remaining-pixels", type=Path, default=DEFAULT_REMAINING_PIXELS)
    parser.add_argument("--archive-tag", default="L4_HJ")
    parser.add_argument("--pcx-name", default="dinodead.pcx")
    parser.add_argument("--frontier-id", type=int, default=6)
    parser.add_argument("--mix-entry-index", type=int, default=2)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Shared 0x2700302b Post-large-delta Next Large Source Probe",
    )
    args = parser.parse_args()
    summary, _candidates = write_report(args)
    print(f"Large-delta pixels: {summary['large_delta_pixels']}")
    print(f"Best large-value source: {summary['best_large_value_source_id']}")
    print(f"Best large-value LCS: {summary['best_large_value_lcs_pixels']}")
    print(f"Verdict: {summary['next_large_source_verdict']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
