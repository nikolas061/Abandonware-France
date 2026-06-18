#!/usr/bin/env python3
"""Profile local delta transforms for the stride-320 pair after single-row promotion."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

from lolg_tex_gap_decoder_frontier80_context_split_residual_low_payload_neighborhood_probe import read_csv
from lolg_tex_gap_opcode_probe import int_value, write_csv


DEFAULT_OUTPUT = Path(
    "output/tex_gap_decoder_frontier80_single_row_non_oracle_selector_promoted_stride320_local_delta_transform_probe"
)
DEFAULT_PAIR_ROWS = Path(
    "output/tex_gap_decoder_frontier80_single_row_non_oracle_selector_promoted_stride320_pair_selector_probe/pair_rows.csv"
)
DEFAULT_BYTE_ROWS = Path(
    "output/tex_gap_decoder_frontier80_single_row_non_oracle_selector_promoted_stride320_pair_selector_probe/top_pair_byte_rows.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "top_pair_targets",
    "pair_length",
    "source_known_bytes",
    "target_known_bytes",
    "raw_exact_bytes",
    "best_constant_delta",
    "best_constant_exact_bytes",
    "small_delta_le2_bytes",
    "small_delta_le4_bytes",
    "bounded_prefix_bytes",
    "bounded_prefix_delta_min",
    "bounded_prefix_delta_max",
    "outlier_bytes",
    "outlier_positions",
    "same_band_small_delta_le4_bytes",
    "plateau_same_band_small_delta_bytes",
    "token_transition_outlier_bytes",
    "promotion_ready_bytes",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

STRATEGY_FIELDNAMES = [
    "strategy",
    "scope",
    "scope_bytes",
    "exact_bytes",
    "coverage_bytes",
    "false_bytes",
    "delta_min",
    "delta_max",
    "notes",
]

BYTE_PROFILE_FIELDNAMES = [
    "byte_index",
    "source_offset",
    "target_offset",
    "source_value",
    "target_value",
    "source_value_class",
    "target_value_class",
    "value_band",
    "band16",
    "delta",
    "abs_delta",
    "delta_class",
    "raw_exact",
    "small_delta_le2",
    "small_delta_le4",
    "bounded_prefix",
    "token_transition",
    "local_note",
]

OUTLIER_FIELDNAMES = [
    "byte_index",
    "source_offset",
    "target_offset",
    "source_value",
    "target_value",
    "source_value_class",
    "target_value_class",
    "value_band",
    "band16",
    "delta",
    "transition_type",
    "local_note",
]


def int_field(row: dict[str, str], field: str, default: int = 0) -> int:
    try:
        return int(row.get(field, ""))
    except (TypeError, ValueError):
        return default


def value_class(value: int) -> str:
    if value == 0:
        return "zero"
    if value < 80:
        return "low"
    if value <= 112:
        return "plateau"
    if value < 160:
        return "mid"
    return "token"


def delta_class(delta: int) -> str:
    abs_delta = abs(delta)
    if delta == 0:
        return "raw"
    if abs_delta <= 2:
        return "small_le2"
    if abs_delta <= 4:
        return "small_le4"
    return "outlier"


def best_constant_delta(deltas: list[int], *, delta_min: int = -8, delta_max: int = 8) -> tuple[int, int]:
    if not deltas:
        return 0, 0
    best_delta = 0
    best_exact = -1
    for delta in range(delta_min, delta_max + 1):
        exact = sum(1 for value in deltas if value == delta)
        if exact > best_exact:
            best_delta = delta
            best_exact = exact
    return best_delta, max(best_exact, 0)


def longest_bounded_prefix(profile_rows: list[dict[str, str]], max_abs_delta: int) -> int:
    count = 0
    for row in profile_rows:
        if int_field(row, "abs_delta") > max_abs_delta:
            break
        count += 1
    return count


def transition_note(source_class: str, target_class: str, outlier: bool, bounded_prefix: bool, small_delta: bool) -> str:
    if bounded_prefix:
        return "bounded_prefix_le4"
    if outlier and (source_class == "token" or target_class == "token") and source_class != target_class:
        return "token_transition_outlier"
    if outlier and source_class == target_class:
        return "same_class_outlier"
    if outlier:
        return "class_transition_outlier"
    if small_delta and source_class == target_class:
        return "same_class_small_delta"
    return "small_delta"


def build_profile_rows(byte_rows: list[dict[str, str]], issues: list[str]) -> list[dict[str, str]]:
    rows = sorted(byte_rows, key=lambda row: int_field(row, "byte_index"))
    profile_rows: list[dict[str, str]] = []
    expected_index = 0
    for row in rows:
        byte_index = int_field(row, "byte_index", -1)
        if byte_index != expected_index:
            issues.append(f"byte_index_gap:expected_{expected_index}:got_{byte_index}")
            expected_index = byte_index
        source_value = int_field(row, "source_value")
        target_value = int_field(row, "target_value")
        delta = int_field(row, "delta")
        source_class = value_class(source_value)
        target_class = value_class(target_value)
        abs_delta = abs(delta)
        profile_rows.append(
            {
                "byte_index": str(byte_index),
                "source_offset": row.get("source_offset", ""),
                "target_offset": row.get("target_offset", ""),
                "source_value": str(source_value),
                "target_value": str(target_value),
                "source_value_class": source_class,
                "target_value_class": target_class,
                "value_band": f"{source_value // 16}:{target_value // 16}",
                "band16": str(byte_index // 16),
                "delta": str(delta),
                "abs_delta": str(abs_delta),
                "delta_class": delta_class(delta),
                "raw_exact": "1" if delta == 0 else "0",
                "small_delta_le2": "1" if abs_delta <= 2 else "0",
                "small_delta_le4": "1" if abs_delta <= 4 else "0",
                "bounded_prefix": "0",
                "token_transition": "1"
                if (source_class == "token" or target_class == "token") and source_class != target_class
                else "0",
                "local_note": "",
            }
        )
        expected_index += 1

    prefix = longest_bounded_prefix(profile_rows, 4)
    for row in profile_rows:
        bounded = int_field(row, "byte_index") < prefix
        outlier = int_field(row, "abs_delta") > 4
        small_delta = int_field(row, "abs_delta") <= 4
        row["bounded_prefix"] = "1" if bounded else "0"
        row["local_note"] = transition_note(
            row.get("source_value_class", ""),
            row.get("target_value_class", ""),
            outlier,
            bounded,
            small_delta,
        )
    return profile_rows


def build_outlier_rows(profile_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in profile_rows:
        if int_field(row, "abs_delta") <= 4:
            continue
        rows.append(
            {
                "byte_index": row.get("byte_index", ""),
                "source_offset": row.get("source_offset", ""),
                "target_offset": row.get("target_offset", ""),
                "source_value": row.get("source_value", ""),
                "target_value": row.get("target_value", ""),
                "source_value_class": row.get("source_value_class", ""),
                "target_value_class": row.get("target_value_class", ""),
                "value_band": row.get("value_band", ""),
                "band16": row.get("band16", ""),
                "delta": row.get("delta", ""),
                "transition_type": f"{row.get('source_value_class', '')}->{row.get('target_value_class', '')}",
                "local_note": row.get("local_note", ""),
            }
        )
    return rows


def build_strategy_rows(profile_rows: list[dict[str, str]], prefix: int, best_delta: int, best_exact: int) -> list[dict[str, str]]:
    length = len(profile_rows)
    deltas = [int_field(row, "delta") for row in profile_rows]
    raw_exact = sum(1 for delta in deltas if delta == 0)
    le2 = sum(1 for delta in deltas if abs(delta) <= 2)
    le4 = sum(1 for delta in deltas if abs(delta) <= 4)
    same_band_le4 = sum(
        1
        for row in profile_rows
        if int_field(row, "abs_delta") <= 4
        and int_field(row, "source_value") // 16 == int_field(row, "target_value") // 16
    )
    prefix_deltas = deltas[:prefix]
    outliers = [delta for delta in deltas if abs(delta) > 4]
    return [
        {
            "strategy": "raw_copy",
            "scope": "top_pair",
            "scope_bytes": str(length),
            "exact_bytes": str(raw_exact),
            "coverage_bytes": str(raw_exact),
            "false_bytes": str(max(0, length - raw_exact)),
            "delta_min": "0",
            "delta_max": "0",
            "notes": "direct stride-320 copy",
        },
        {
            "strategy": "best_constant_delta",
            "scope": "top_pair",
            "scope_bytes": str(length),
            "exact_bytes": str(best_exact),
            "coverage_bytes": str(best_exact),
            "false_bytes": str(max(0, length - best_exact)),
            "delta_min": str(best_delta),
            "delta_max": str(best_delta),
            "notes": "single signed delta applied to every byte",
        },
        {
            "strategy": "small_delta_oracle_le2",
            "scope": "top_pair",
            "scope_bytes": str(length),
            "exact_bytes": str(le2),
            "coverage_bytes": str(le2),
            "false_bytes": "0",
            "delta_min": "-2",
            "delta_max": "2",
            "notes": "analysis only; needs a non-oracle selector",
        },
        {
            "strategy": "small_delta_oracle_le4",
            "scope": "top_pair",
            "scope_bytes": str(length),
            "exact_bytes": str(le4),
            "coverage_bytes": str(le4),
            "false_bytes": "0",
            "delta_min": "-4",
            "delta_max": "4",
            "notes": "analysis only; separates bounded bytes from outliers",
        },
        {
            "strategy": "bounded_prefix_le4",
            "scope": "top_pair_prefix",
            "scope_bytes": str(prefix),
            "exact_bytes": str(prefix),
            "coverage_bytes": str(prefix),
            "false_bytes": "0",
            "delta_min": str(min(prefix_deltas) if prefix_deltas else 0),
            "delta_max": str(max(prefix_deltas) if prefix_deltas else 0),
            "notes": "longest leading window with abs(delta) <= 4",
        },
        {
            "strategy": "same_band_small_delta_le4",
            "scope": "top_pair",
            "scope_bytes": str(length),
            "exact_bytes": str(same_band_le4),
            "coverage_bytes": str(same_band_le4),
            "false_bytes": "0",
            "delta_min": "-4",
            "delta_max": "4",
            "notes": "bounded bytes stay in the same 16-value band",
        },
        {
            "strategy": "outlier_split",
            "scope": "top_pair_outliers",
            "scope_bytes": str(len(outliers)),
            "exact_bytes": "0",
            "coverage_bytes": str(len(outliers)),
            "false_bytes": "0",
            "delta_min": str(min(outliers) if outliers else 0),
            "delta_max": str(max(outliers) if outliers else 0),
            "notes": "requires token/class transition handling before replay",
        },
    ]


def build_summary(
    pair_rows: list[dict[str, str]],
    profile_rows: list[dict[str, str]],
    outlier_rows: list[dict[str, str]],
    issues: list[str],
) -> dict[str, str]:
    top = pair_rows[0] if pair_rows else {}
    deltas = [int_field(row, "delta") for row in profile_rows]
    prefix = longest_bounded_prefix(profile_rows, 4)
    prefix_deltas = deltas[:prefix]
    best_delta, best_exact = best_constant_delta(deltas)
    le2 = sum(1 for delta in deltas if abs(delta) <= 2)
    le4 = sum(1 for delta in deltas if abs(delta) <= 4)
    raw_exact = sum(1 for delta in deltas if delta == 0)
    same_band_le4 = sum(
        1
        for row in profile_rows
        if int_field(row, "abs_delta") <= 4
        and int_field(row, "source_value") // 16 == int_field(row, "target_value") // 16
    )
    plateau_same_band = sum(
        1
        for row in profile_rows
        if int_field(row, "abs_delta") <= 4
        and row.get("source_value_class") == "plateau"
        and row.get("target_value_class") == "plateau"
        and int_field(row, "source_value") // 16 == int_field(row, "target_value") // 16
    )
    token_outliers = sum(1 for row in outlier_rows if row.get("local_note") == "token_transition_outlier")
    source_known = int_value(top, "source_known_bytes")
    target_known = int_value(top, "target_known_bytes")
    promotion_ready = 0

    if source_known == 0 and prefix >= 32:
        verdict = "frontier80_stride320_local_delta_transform_source_dependency_needed"
        next_probe = f"derive source dependencies for {prefix}-byte bounded prefix of stride-320 pair"
    elif prefix >= 32 and token_outliers:
        verdict = "frontier80_stride320_local_delta_transform_outlier_split_needed"
        next_probe = "split token-transition outliers for stride-320 local delta transform"
    elif le4:
        verdict = "frontier80_stride320_local_delta_transform_guard_needed"
        next_probe = "derive non-oracle guard for stride-320 small-delta bytes"
    else:
        verdict = "frontier80_stride320_local_delta_transform_no_progress"
        next_probe = "return to residual run selector for stride-320 pair"

    return {
        "scope": "top_pair",
        "top_pair_targets": ";".join(value for value in (top.get("target_a", ""), top.get("target_b", "")) if value),
        "pair_length": str(len(profile_rows)),
        "source_known_bytes": str(source_known),
        "target_known_bytes": str(target_known),
        "raw_exact_bytes": str(raw_exact),
        "best_constant_delta": str(best_delta),
        "best_constant_exact_bytes": str(best_exact),
        "small_delta_le2_bytes": str(le2),
        "small_delta_le4_bytes": str(le4),
        "bounded_prefix_bytes": str(prefix),
        "bounded_prefix_delta_min": str(min(prefix_deltas) if prefix_deltas else 0),
        "bounded_prefix_delta_max": str(max(prefix_deltas) if prefix_deltas else 0),
        "outlier_bytes": str(len(outlier_rows)),
        "outlier_positions": ";".join(row.get("byte_index", "") for row in outlier_rows),
        "same_band_small_delta_le4_bytes": str(same_band_le4),
        "plateau_same_band_small_delta_bytes": str(plateau_same_band),
        "token_transition_outlier_bytes": str(token_outliers),
        "promotion_ready_bytes": str(promotion_ready),
        "issue_rows": str(len(issues)),
        "review_verdict": verdict,
        "next_probe": next_probe,
    }


def table_html(title: str, filename: str, rows: list[dict[str, str]], fields: list[str], limit: int = 96) -> str:
    if not rows:
        return f"<section><h2>{html.escape(title)}</h2><p>No rows.</p></section>"
    headers = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = []
    for row in rows[:limit]:
        body.append("<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>")
    return (
        f"<section><h2>{html.escape(title)}</h2><p><a href=\"{html.escape(filename)}\">"
        f"{html.escape(filename)}</a></p><table><thead><tr>{headers}</tr></thead>"
        f"<tbody>{''.join(body)}</tbody></table></section>"
    )


def build_html(
    summary: dict[str, str],
    strategy_rows: list[dict[str, str]],
    profile_rows: list[dict[str, str]],
    outlier_rows: list[dict[str, str]],
    title: str,
) -> str:
    summary_json = html.escape(json.dumps(summary, indent=2))
    stats = "".join(
        f"<div class=\"stat\"><div class=\"label\">{html.escape(key)}</div>"
        f"<div class=\"value\">{html.escape(summary.get(key, ''))}</div></div>"
        for key in (
            "pair_length",
            "small_delta_le4_bytes",
            "bounded_prefix_bytes",
            "outlier_bytes",
            "source_known_bytes",
            "review_verdict",
        )
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{html.escape(title)}</title>
  <style>
    body {{ font-family: sans-serif; margin: 24px; color: #1f2933; }}
    .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }}
    .stat {{ border: 1px solid #d8dee4; border-radius: 6px; padding: 10px; background: #f8fafc; }}
    .label {{ font-size: 12px; color: #52606d; }}
    .value {{ font-weight: 700; overflow-wrap: anywhere; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 12px; margin-top: 8px; }}
    th, td {{ border: 1px solid #d8dee4; padding: 4px 6px; text-align: left; vertical-align: top; }}
    th {{ background: #eef2f7; }}
    pre {{ background: #f6f8fa; padding: 12px; overflow: auto; }}
  </style>
</head>
<body>
  <h1>{html.escape(title)}</h1>
  <div class="stats">{stats}</div>
  <h2>Summary</h2>
  <pre>{summary_json}</pre>
  {table_html("Strategy rows", "strategy_rows.csv", strategy_rows, STRATEGY_FIELDNAMES)}
  {table_html("Outlier rows", "outlier_rows.csv", outlier_rows, OUTLIER_FIELDNAMES)}
  {table_html("Byte profile", "byte_profile.csv", profile_rows, BYTE_PROFILE_FIELDNAMES)}
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--pair-rows", type=Path, default=DEFAULT_PAIR_ROWS)
    parser.add_argument("--byte-rows", type=Path, default=DEFAULT_BYTE_ROWS)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Stride-320 Local Delta Transform Probe",
    )
    args = parser.parse_args()

    issues: list[str] = []
    pair_rows = read_csv(args.pair_rows)
    byte_rows = read_csv(args.byte_rows)
    if not pair_rows:
        issues.append(f"missing_pair_rows:{args.pair_rows}")
    if not byte_rows:
        issues.append(f"missing_byte_rows:{args.byte_rows}")

    profile_rows = build_profile_rows(byte_rows, issues)
    outlier_rows = build_outlier_rows(profile_rows)
    prefix = longest_bounded_prefix(profile_rows, 4)
    best_delta, best_exact = best_constant_delta([int_field(row, "delta") for row in profile_rows])
    strategy_rows = build_strategy_rows(profile_rows, prefix, best_delta, best_exact)
    summary = build_summary(pair_rows, profile_rows, outlier_rows, issues)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "strategy_rows.csv", STRATEGY_FIELDNAMES, strategy_rows)
    write_csv(args.output / "byte_profile.csv", BYTE_PROFILE_FIELDNAMES, profile_rows)
    write_csv(args.output / "outlier_rows.csv", OUTLIER_FIELDNAMES, outlier_rows)
    (args.output / "issues.txt").write_text("\n".join(issues))
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, strategy_rows, profile_rows, outlier_rows, args.title))

    print(
        "Stride-320 local delta transform: "
        f"prefix={summary['bounded_prefix_bytes']}, "
        f"le4={summary['small_delta_le4_bytes']}/{summary['pair_length']}, "
        f"outliers={summary['outlier_bytes']}"
    )
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
