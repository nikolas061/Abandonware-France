#!/usr/bin/env python3
"""Split post-low2 small-delta selector misses for shared 0x2700302b."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

import lolg_tex_large_shared_2700302b_reference_fixed_dy1_residual_profile_probe as residual_profile
import lolg_tex_large_shared_2700302b_reference_fixed_dy1_small_delta_low2_selector_probe as low2_selector
import lolg_tex_large_shared_2700302b_reference_frontier_probe as frontier_probe
import lolg_tex_large_shared_2700302b_reference_literal_stream_probe as literal_probe


DEFAULT_OUTPUT = Path("output/tex_large_shared_2700302b_reference_fixed_dy1_post_low2_small_delta_miss_split_probe")
DEFAULT_FRONTIERS = frontier_probe.DEFAULT_FRONTIERS
DEFAULT_COMPARISONS = frontier_probe.DEFAULT_COMPARISONS
DEFAULT_POST_LOW2_SUMMARY = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_post_low2_residual_profile_probe/summary.csv"
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
    "remaining_nonzero_pixels",
    "remaining_small_delta_pixels",
    "low2_representable_pixels",
    "low2_representable_ratio",
    "low2_impossible_pixels",
    "low2_impossible_ratio",
    "low2_impossible_positive_pixels",
    "low2_impossible_negative_pixels",
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
    "post_low2_summary_gap_pixels",
    "issue_rows",
    "small_delta_miss_split_verdict",
    "next_action",
]

TOKEN_FIELDNAMES = [
    "token_index",
    "target_y",
    "x_start",
    "x_end",
    "pixels",
    "low2_representable_pixels",
    "low2_impossible_pixels",
    "token_kind",
    "delta_signature_head",
]

ROW_FIELDNAMES = [
    "target_y",
    "small_delta_pixels",
    "low2_representable_pixels",
    "low2_impossible_pixels",
    "unused_source_lcs_pixels",
    "top_representable_deltas",
    "top_impossible_deltas",
]

DELTA_FIELDNAMES = [
    "rank",
    "miss_kind",
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


def small_delta_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [row for row in rows if row.get("residual_kind") == "small_delta"]


def miss_kind(row: dict[str, str]) -> str:
    return "low2_representable" if int_value(row, "delta_signed") in LOW2_DELTAS else "low2_impossible"


def signed_byte(value: int) -> int:
    return ((value + 128) & 0xFF) - 128


def build_tokens(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    tokens: list[dict[str, str]] = []
    current: list[dict[str, str]] = []
    previous_y = -1
    previous_x = -2

    def flush() -> None:
        if not current:
            return
        token_index = len(tokens) + 1
        first = current[0]
        last = current[-1]
        representable = [row for row in current if miss_kind(row) == "low2_representable"]
        impossible = [row for row in current if miss_kind(row) == "low2_impossible"]
        if representable and impossible:
            token_kind = "mixed"
        elif representable:
            token_kind = "low2_representable"
        else:
            token_kind = "low2_impossible"
        tokens.append(
            {
                "token_index": str(token_index),
                "target_y": first.get("target_y", ""),
                "x_start": first.get("target_x", ""),
                "x_end": last.get("target_x", ""),
                "pixels": str(len(current)),
                "low2_representable_pixels": str(len(representable)),
                "low2_impossible_pixels": str(len(impossible)),
                "token_kind": token_kind,
                "delta_signature_head": "|".join(row.get("delta_signed", "") for row in current[:32]),
            }
        )
        current.clear()

    for row in rows:
        y = int_value(row, "target_y")
        x = int_value(row, "target_x")
        contiguous = y == previous_y and x == previous_x + 1
        if current and not contiguous:
            flush()
        current.append(row)
        previous_y = y
        previous_x = x
    flush()
    return tokens


def run_lengths(rows: list[dict[str, str]], kind: str) -> list[int]:
    lengths: list[int] = []
    current = 0
    previous_y = -1
    previous_x = -2
    for row in rows:
        if miss_kind(row) != kind:
            if current:
                lengths.append(current)
                current = 0
            previous_y = -1
            previous_x = -2
            continue
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


def lcs_len(source: list[int], target: list[int]) -> int:
    return literal_probe.lcs_len(bytes(value & 0xFF for value in source), bytes(value & 0xFF for value in target))


def build_row_rows(rows: list[dict[str, str]], unused_values: list[int]) -> list[dict[str, str]]:
    by_y: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_y[row.get("target_y", "")].append(row)
    output: list[dict[str, str]] = []
    for y in sorted(by_y, key=lambda value: int(value or 0)):
        row_pixels = by_y[y]
        representable = [row for row in row_pixels if miss_kind(row) == "low2_representable"]
        impossible = [row for row in row_pixels if miss_kind(row) == "low2_impossible"]
        target_values = [int_value(row, "delta_signed") & 0xFF for row in representable]
        rep_counts = Counter(int_value(row, "delta_signed") for row in representable)
        imp_counts = Counter(int_value(row, "delta_signed") for row in impossible)
        output.append(
            {
                "target_y": y,
                "small_delta_pixels": str(len(row_pixels)),
                "low2_representable_pixels": str(len(representable)),
                "low2_impossible_pixels": str(len(impossible)),
                "unused_source_lcs_pixels": str(lcs_len(unused_values, target_values)),
                "top_representable_deltas": "|".join(f"{delta}:{count}" for delta, count in rep_counts.most_common(8)),
                "top_impossible_deltas": "|".join(f"{delta}:{count}" for delta, count in imp_counts.most_common(8)),
            }
        )
    return output


def build_delta_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    counters: dict[str, Counter[int]] = {"low2_representable": Counter(), "low2_impossible": Counter()}
    totals = Counter()
    for row in rows:
        kind = miss_kind(row)
        delta = int_value(row, "delta_signed")
        counters[kind][delta] += 1
        totals[kind] += 1
    output: list[dict[str, str]] = []
    for kind in ("low2_representable", "low2_impossible"):
        total = totals[kind]
        for rank, (delta, count) in enumerate(counters[kind].most_common(), 1):
            output.append(
                {
                    "rank": str(rank),
                    "miss_kind": kind,
                    "delta_signed": str(delta),
                    "delta_hex": f"{delta & 0xFF:02x}",
                    "count": str(count),
                    "ratio": float_text(count / total if total else 0.0),
                }
            )
    return output


def unused_low2_values(args: argparse.Namespace, used_source_indexes: set[int]) -> list[int]:
    load_args = argparse.Namespace(
        frontiers=args.frontiers,
        comparisons=args.comparisons,
        archive_tag=args.archive_tag,
        pcx_name=args.pcx_name,
        frontier_id=args.frontier_id,
        mix_entry_index=args.mix_entry_index,
    )
    _frontier, _comparison, _pixels, _width, segment, _issues = residual_profile.load_reference(load_args)
    source_rows = low2_selector.low2_nonzero_source(segment)
    return [row["value"] for row in source_rows if row["source_index"] not in used_source_indexes]


def used_source_indexes(alignment_rows: list[dict[str, str]]) -> set[int]:
    return {int_value(row, "source_index") for row in alignment_rows}


def build_summary(
    post_summary: dict[str, str],
    small_rows: list[dict[str, str]],
    token_rows: list[dict[str, str]],
    unused_values: list[int],
    row_rows: list[dict[str, str]],
    *,
    issues: list[str],
) -> dict[str, str]:
    representable = [row for row in small_rows if miss_kind(row) == "low2_representable"]
    impossible = [row for row in small_rows if miss_kind(row) == "low2_impossible"]
    compatible_target = [int_value(row, "delta_signed") & 0xFF for row in representable]
    unused_lcs = lcs_len(unused_values, compatible_target)
    impossible_positive = sum(1 for row in impossible if int_value(row, "delta_signed") > 0)
    impossible_negative = len(impossible) - impossible_positive
    post_gap = len(small_rows) - int_value(post_summary, "remaining_small_delta_pixels")
    issue_rows = len(issues) + (1 if post_gap else 0)
    mixed_tokens = [row for row in token_rows if row.get("token_kind") == "mixed"]
    representable_tokens = [row for row in token_rows if row.get("token_kind") == "low2_representable"]
    impossible_tokens = [row for row in token_rows if row.get("token_kind") == "low2_impossible"]

    if issue_rows:
        verdict = "shared_2700302b_reference_fixed_dy1_post_low2_small_delta_miss_split_issues"
        next_action = "fix shared 0x2700302b post-low2 small-delta miss split inputs"
    elif len(representable) > len(impossible):
        verdict = "shared_2700302b_reference_fixed_dy1_post_low2_low2_compatible_misses_dominant"
        next_action = (
            "derive secondary selector/source for post-low2 low2-compatible misses in shared 0x2700302b; "
            f"unused low2 source explains only {unused_lcs}/{len(representable)} compatible misses"
        )
    else:
        verdict = "shared_2700302b_reference_fixed_dy1_post_low2_non_low2_small_delta_focus"
        next_action = (
            "derive non-low2 small-delta producer for shared 0x2700302b; "
            f"{len(impossible)} +2/+3/-3 pixels remain"
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
        "unused_low2_source_bytes": str(len(unused_values)),
        "unused_low2_source_lcs_pixels": str(unused_lcs),
        "unused_low2_source_lcs_ratio": float_text(unused_lcs / len(representable) if representable else 0.0),
        "unused_low2_source_match_ratio": float_text(unused_lcs / len(unused_values) if unused_values else 0.0),
        "compatible_after_unused_source_pixels": str(max(0, len(representable) - unused_lcs)),
        "small_delta_token_rows": str(len(token_rows)),
        "low2_representable_token_rows": str(len(representable_tokens)),
        "low2_impossible_token_rows": str(len(impossible_tokens)),
        "mixed_token_rows": str(len(mixed_tokens)),
        "max_low2_representable_run_pixels": str(max(run_lengths(small_rows, "low2_representable"), default=0)),
        "max_low2_impossible_run_pixels": str(max(run_lengths(small_rows, "low2_impossible"), default=0)),
        "post_low2_summary_gap_pixels": str(post_gap),
        "issue_rows": str(issue_rows),
        "small_delta_miss_split_verdict": verdict,
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
    tokens: list[dict[str, str]],
    rows: list[dict[str, str]],
    deltas: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "tokens": tokens, "rows": rows, "deltas": deltas}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
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
<h2>Rows</h2>{render_table(rows, ROW_FIELDNAMES)}
<h2>Delta Split</h2>{render_table(deltas, DELTA_FIELDNAMES)}
<h2>Tokens</h2>{render_table(tokens[:160], TOKEN_FIELDNAMES)}
<script type="application/json" id="data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> tuple[dict[str, str], list[dict[str, str]]]:
    args.output.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    post_summary = read_summary(args.post_low2_summary)
    if not post_summary:
        issues.append("missing_post_low2_summary")
    remaining_rows = read_csv(args.remaining_pixels)
    if not remaining_rows:
        issues.append("missing_remaining_pixels")
    alignment_rows = read_csv(args.low2_alignments)
    if not alignment_rows:
        issues.append("missing_low2_alignments")
    small_rows = small_delta_rows(remaining_rows)
    used_indexes = used_source_indexes(alignment_rows)
    unused_values = unused_low2_values(args, used_indexes)
    token_rows = build_tokens(small_rows)
    row_rows = build_row_rows(small_rows, unused_values)
    delta_rows = build_delta_rows(small_rows)
    summary = build_summary(post_summary, small_rows, token_rows, unused_values, row_rows, issues=issues)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "tokens.csv", TOKEN_FIELDNAMES, token_rows)
    write_csv(args.output / "rows.csv", ROW_FIELDNAMES, row_rows)
    write_csv(args.output / "delta_split.csv", DELTA_FIELDNAMES, delta_rows)
    (args.output / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""), encoding="utf-8")
    (args.output / "index.html").write_text(
        build_html(summary, token_rows, row_rows, delta_rows, args.output, args.title),
        encoding="utf-8",
    )
    return summary, token_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Split post-low2 small-delta misses for shared 0x2700302b.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--frontiers", type=Path, default=DEFAULT_FRONTIERS)
    parser.add_argument("--comparisons", type=Path, default=DEFAULT_COMPARISONS)
    parser.add_argument("--post-low2-summary", type=Path, default=DEFAULT_POST_LOW2_SUMMARY)
    parser.add_argument("--remaining-pixels", type=Path, default=DEFAULT_REMAINING_PIXELS)
    parser.add_argument("--low2-alignments", type=Path, default=DEFAULT_LOW2_ALIGNMENTS)
    parser.add_argument("--archive-tag", default="L4_HJ")
    parser.add_argument("--pcx-name", default="dinodead.pcx")
    parser.add_argument("--frontier-id", type=int, default=6)
    parser.add_argument("--mix-entry-index", type=int, default=2)
    parser.add_argument("--title", default="Lands of Lore II .tex Shared 0x2700302b Post-low2 Small-Delta Miss Split")
    args = parser.parse_args()
    summary, _tokens = write_report(args)
    print(f"Low2-representable pixels: {summary['low2_representable_pixels']}")
    print(f"Low2-impossible pixels: {summary['low2_impossible_pixels']}")
    print(f"Unused low2 LCS pixels: {summary['unused_low2_source_lcs_pixels']}")
    print(f"Verdict: {summary['small_delta_miss_split_verdict']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
