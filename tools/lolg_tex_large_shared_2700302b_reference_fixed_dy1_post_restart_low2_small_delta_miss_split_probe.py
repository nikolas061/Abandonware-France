#!/usr/bin/env python3
"""Split post-restart-low2 small-delta misses for shared 0x2700302b."""

from __future__ import annotations

import argparse
import csv
import html
import json
import sys
from pathlib import Path

import lolg_tex_large_shared_2700302b_reference_fixed_dy1_post_low2_small_delta_miss_split_probe as post_low2_split


DEFAULT_OUTPUT = Path("output/tex_large_shared_2700302b_reference_fixed_dy1_post_restart_low2_small_delta_miss_split_probe")
DEFAULT_FRONTIERS = post_low2_split.DEFAULT_FRONTIERS
DEFAULT_COMPARISONS = post_low2_split.DEFAULT_COMPARISONS
DEFAULT_POST_RESTART_SUMMARY = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_post_restart_low2_residual_profile_probe/summary.csv"
)
DEFAULT_REMAINING_PIXELS = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_post_restart_low2_residual_profile_probe/remaining_pixels.csv"
)
DEFAULT_SELECTED_PIXELS = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_post_low2_restart_low2_guarded_replay_probe/selected_pixels.csv"
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
    "remaining_small_delta_pixels",
    "low2_representable_pixels",
    "low2_representable_ratio",
    "low2_impossible_pixels",
    "low2_impossible_ratio",
    "low2_impossible_positive_pixels",
    "low2_impossible_negative_pixels",
    "used_low2_source_bytes",
    "unused_low2_source_bytes",
    "unused_low2_source_lcs_pixels",
    "unused_low2_source_lcs_ratio",
    "unused_low2_source_match_ratio",
    "compatible_after_unused_source_pixels",
    "small_delta_token_rows",
    "low2_representable_token_rows",
    "low2_impossible_token_rows",
    "mixed_token_rows",
    "max_low2_representable_run_pixels",
    "max_low2_impossible_run_pixels",
    "post_restart_summary_gap_pixels",
    "issue_rows",
    "post_restart_small_delta_miss_split_verdict",
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


def float_text(value: float) -> str:
    return f"{value:.6f}"


def build_summary(
    post_summary: dict[str, str],
    small_rows: list[dict[str, str]],
    token_rows: list[dict[str, str]],
    used_source_indexes: set[int],
    unused_values: list[int],
    *,
    issues: list[str],
) -> dict[str, str]:
    representable = [row for row in small_rows if post_low2_split.miss_kind(row) == "low2_representable"]
    impossible = [row for row in small_rows if post_low2_split.miss_kind(row) == "low2_impossible"]
    compatible_target = [int_value(row, "delta_signed") & 0xFF for row in representable]
    unused_lcs = post_low2_split.lcs_len(unused_values, compatible_target)
    impossible_positive = sum(1 for row in impossible if int_value(row, "delta_signed") > 0)
    impossible_negative = len(impossible) - impossible_positive
    post_gap = len(small_rows) - int_value(post_summary, "remaining_small_delta_pixels")
    issue_rows = len(issues) + (1 if post_gap else 0)
    mixed_tokens = [row for row in token_rows if row.get("token_kind") == "mixed"]
    representable_tokens = [row for row in token_rows if row.get("token_kind") == "low2_representable"]
    impossible_tokens = [row for row in token_rows if row.get("token_kind") == "low2_impossible"]

    if issue_rows:
        verdict = "shared_2700302b_reference_fixed_dy1_post_restart_low2_small_delta_miss_split_issues"
        next_action = "fix shared 0x2700302b post-restart-low2 small-delta miss split inputs"
    elif len(impossible) >= len(representable):
        verdict = "shared_2700302b_reference_fixed_dy1_post_restart_low2_non_low2_small_delta_focus"
        next_action = (
            "derive non-low2 +2/+3/-3 small-delta producer after restart low2 for shared 0x2700302b; "
            f"{len(impossible)} low2-impossible pixels remain"
        )
    else:
        verdict = "shared_2700302b_reference_fixed_dy1_post_restart_low2_low2_compatible_misses_remain"
        next_action = (
            "derive another low2-compatible selector after restart low2 for shared 0x2700302b; "
            f"unused low2 source explains {unused_lcs}/{len(representable)} compatible misses"
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
        "remaining_small_delta_pixels": str(len(small_rows)),
        "low2_representable_pixels": str(len(representable)),
        "low2_representable_ratio": float_text(len(representable) / len(small_rows) if small_rows else 0.0),
        "low2_impossible_pixels": str(len(impossible)),
        "low2_impossible_ratio": float_text(len(impossible) / len(small_rows) if small_rows else 0.0),
        "low2_impossible_positive_pixels": str(impossible_positive),
        "low2_impossible_negative_pixels": str(impossible_negative),
        "used_low2_source_bytes": str(len(used_source_indexes)),
        "unused_low2_source_bytes": str(len(unused_values)),
        "unused_low2_source_lcs_pixels": str(unused_lcs),
        "unused_low2_source_lcs_ratio": float_text(unused_lcs / len(representable) if representable else 0.0),
        "unused_low2_source_match_ratio": float_text(unused_lcs / len(unused_values) if unused_values else 0.0),
        "compatible_after_unused_source_pixels": str(max(0, len(representable) - unused_lcs)),
        "small_delta_token_rows": str(len(token_rows)),
        "low2_representable_token_rows": str(len(representable_tokens)),
        "low2_impossible_token_rows": str(len(impossible_tokens)),
        "mixed_token_rows": str(len(mixed_tokens)),
        "max_low2_representable_run_pixels": str(
            max(post_low2_split.run_lengths(small_rows, "low2_representable"), default=0)
        ),
        "max_low2_impossible_run_pixels": str(
            max(post_low2_split.run_lengths(small_rows, "low2_impossible"), default=0)
        ),
        "post_restart_summary_gap_pixels": str(post_gap),
        "issue_rows": str(issue_rows),
        "post_restart_small_delta_miss_split_verdict": verdict,
        "next_action": next_action,
    }


def render_table(rows: list[dict[str, str]], fieldnames: list[str]) -> str:
    return post_low2_split.render_table(rows, fieldnames)


def build_html(
    summary: dict[str, str],
    tokens: list[dict[str, str]],
    rows: list[dict[str, str]],
    deltas: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "tokens": tokens, "rows": rows, "deltas": deltas}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(post_low2_split.relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary", output_dir / "summary.csv"),
            ("tokens", output_dir / "tokens.csv"),
            ("rows", output_dir / "rows.csv"),
            ("delta_split", output_dir / "delta_split.csv"),
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
  <div class="stat"><div class="label">Representable</div><div class="value">{html.escape(summary['low2_representable_pixels'])}</div></div>
  <div class="stat"><div class="label">Impossible</div><div class="value">{html.escape(summary['low2_impossible_pixels'])}</div></div>
  <div class="stat"><div class="label">Unused LCS</div><div class="value">{html.escape(summary['unused_low2_source_lcs_pixels'])}</div></div>
  <div class="stat"><div class="label">Mixed Tokens</div><div class="value">{html.escape(summary['mixed_token_rows'])}</div></div>
</div>
<p>{html.escape(summary['next_action'])}</p>
<h2>Summary</h2>{render_table([summary], SUMMARY_FIELDNAMES)}
<h2>Rows</h2>{render_table(rows, post_low2_split.ROW_FIELDNAMES)}
<h2>Delta Split</h2>{render_table(deltas, post_low2_split.DELTA_FIELDNAMES)}
<h2>Tokens</h2>{render_table(tokens[:160], post_low2_split.TOKEN_FIELDNAMES)}
<script type="application/json" id="data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> tuple[dict[str, str], list[dict[str, str]]]:
    args.output.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    post_summary = read_summary(args.post_restart_summary)
    if not post_summary:
        issues.append("missing_post_restart_summary")
    remaining_rows = read_csv(args.remaining_pixels)
    if not remaining_rows:
        issues.append("missing_remaining_pixels")
    selected_rows = read_csv(args.selected_pixels)
    if not selected_rows:
        issues.append("missing_selected_pixels")
    small_rows = post_low2_split.small_delta_rows(remaining_rows)
    used_indexes = post_low2_split.used_source_indexes(selected_rows)
    unused_values = post_low2_split.unused_low2_values(args, used_indexes)
    token_rows = post_low2_split.build_tokens(small_rows)
    row_rows = post_low2_split.build_row_rows(small_rows, unused_values)
    delta_rows = post_low2_split.build_delta_rows(small_rows)
    summary = build_summary(post_summary, small_rows, token_rows, used_indexes, unused_values, issues=issues)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "tokens.csv", post_low2_split.TOKEN_FIELDNAMES, token_rows)
    write_csv(args.output / "rows.csv", post_low2_split.ROW_FIELDNAMES, row_rows)
    write_csv(args.output / "delta_split.csv", post_low2_split.DELTA_FIELDNAMES, delta_rows)
    (args.output / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""), encoding="utf-8")
    (args.output / "index.html").write_text(
        build_html(summary, token_rows, row_rows, delta_rows, args.output, args.title),
        encoding="utf-8",
    )
    return summary, token_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Split post-restart-low2 small-delta misses for shared 0x2700302b.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--frontiers", type=Path, default=DEFAULT_FRONTIERS)
    parser.add_argument("--comparisons", type=Path, default=DEFAULT_COMPARISONS)
    parser.add_argument("--post-restart-summary", type=Path, default=DEFAULT_POST_RESTART_SUMMARY)
    parser.add_argument("--remaining-pixels", type=Path, default=DEFAULT_REMAINING_PIXELS)
    parser.add_argument("--selected-pixels", type=Path, default=DEFAULT_SELECTED_PIXELS)
    parser.add_argument("--archive-tag", default="L4_HJ")
    parser.add_argument("--pcx-name", default="dinodead.pcx")
    parser.add_argument("--frontier-id", type=int, default=6)
    parser.add_argument("--mix-entry-index", type=int, default=2)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Shared 0x2700302b Post-restart-low2 Small-Delta Miss Split",
    )
    args = parser.parse_args()
    summary, _tokens = write_report(args)
    print(f"Low2-representable pixels: {summary['low2_representable_pixels']}")
    print(f"Low2-impossible pixels: {summary['low2_impossible_pixels']}")
    print(f"Unused low2 LCS pixels: {summary['unused_low2_source_lcs_pixels']}")
    print(f"Verdict: {summary['post_restart_small_delta_miss_split_verdict']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
