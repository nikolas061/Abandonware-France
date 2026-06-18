#!/usr/bin/env python3
"""Derive a cross-PCX guard for stride-320 outlier target values."""

from __future__ import annotations

import argparse
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_decoder_frontier80_context_split_residual_low_payload_neighborhood_probe import read_csv
from lolg_tex_gap_opcode_probe import int_value, write_csv


DEFAULT_OUTPUT = Path(
    "output/tex_gap_decoder_frontier80_single_row_non_oracle_selector_promoted_stride320_outlier_target_cross_pcx_guard_probe"
)
DEFAULT_TARGET_VALUE_DEPENDENCY = Path(
    "output/tex_gap_decoder_frontier80_single_row_non_oracle_selector_promoted_stride320_outlier_target_value_dependency_probe"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "cross_pcx_candidate_bytes",
    "guard_ready_bytes",
    "cross_pcx_values",
    "cross_pcx_target_offsets",
    "distinct_cross_pcx_values",
    "exact_cross_pcx_values",
    "same_pcx_le4_bridge_values",
    "same_fixture_le4_bridge_values",
    "exact_cross_pcx_support_rows",
    "same_pcx_le4_bridge_rows",
    "same_fixture_le4_bridge_rows",
    "bridge_support_values",
    "bridge_deltas",
    "promotion_ready_bytes",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

GUARD_FIELDNAMES = [
    "guard_ready",
    "byte_index",
    "source_offset",
    "target_offset",
    "source_value",
    "target_value",
    "target_delta",
    "target_value_class",
    "local_note",
    "predicted_byte",
    "best_formula",
    "best_guard_key",
    "exact_cross_pcx_support_rows",
    "same_pcx_le4_bridge_rows",
    "same_fixture_le4_bridge_rows",
    "best_exact_rank",
    "best_exact_archive_tag",
    "best_exact_pcx_name",
    "best_exact_frontier_id",
    "best_exact_offset",
    "bridge_rank",
    "bridge_archive_tag",
    "bridge_pcx_name",
    "bridge_frontier_id",
    "bridge_offset",
    "bridge_support_value",
    "bridge_delta",
    "bridge_abs_delta",
    "support_basis",
]

SUPPORT_DETAIL_FIELDNAMES = [
    "target_value",
    "support_rank",
    "support_archive_tag",
    "support_pcx_name",
    "support_frontier_id",
    "support_offset",
    "support_value",
    "delta",
    "abs_delta",
    "support_kind",
    "same_fixture",
    "same_pcx",
    "guard_role",
]


def byte_hex(value: int) -> str:
    return f"{value & 0xFF:02x}"


def support_groups(support_rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in support_rows:
        grouped[row.get("target_value", "")].append(row)
    for rows in grouped.values():
        rows.sort(
            key=lambda row: (
                0 if row.get("same_fixture") == "1" else 1,
                0 if row.get("same_pcx") == "1" else 1,
                int_value(row, "abs_delta"),
                int_value(row, "support_rank"),
                int_value(row, "support_frontier_id"),
                int_value(row, "support_offset"),
            )
        )
    return grouped


def select_best_exact(rows: list[dict[str, str]]) -> dict[str, str]:
    exact = [row for row in rows if row.get("support_kind") == "exact" and row.get("same_pcx") != "1"]
    exact.sort(
        key=lambda row: (
            int_value(row, "support_rank"),
            int_value(row, "support_frontier_id"),
            int_value(row, "support_offset"),
        )
    )
    return exact[0] if exact else {}


def select_best_bridge(rows: list[dict[str, str]]) -> dict[str, str]:
    same_pcx_le4 = [
        row
        for row in rows
        if row.get("same_pcx") == "1" and row.get("support_kind") == "le4" and int_value(row, "abs_delta") <= 4
    ]
    same_pcx_le4.sort(
        key=lambda row: (
            0 if row.get("same_fixture") == "1" else 1,
            int_value(row, "abs_delta"),
            int_value(row, "support_rank"),
            int_value(row, "support_frontier_id"),
            int_value(row, "support_offset"),
        )
    )
    return same_pcx_le4[0] if same_pcx_le4 else {}


def support_details_for_value(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    details: list[dict[str, str]] = []
    for row in rows:
        exact_cross = row.get("support_kind") == "exact" and row.get("same_pcx") != "1"
        same_pcx_bridge = row.get("same_pcx") == "1" and row.get("support_kind") == "le4"
        if not (exact_cross or same_pcx_bridge):
            continue
        output = {field: row.get(field, "") for field in SUPPORT_DETAIL_FIELDNAMES if field != "guard_role"}
        if exact_cross:
            output["guard_role"] = "cross_pcx_exact"
        else:
            output["guard_role"] = "same_pcx_le4_bridge"
        details.append(output)
    details.sort(
        key=lambda row: (
            int_value(row, "target_value"),
            0 if row.get("guard_role") == "same_pcx_le4_bridge" else 1,
            int_value(row, "abs_delta"),
            int_value(row, "support_rank"),
            int_value(row, "support_offset"),
        )
    )
    return details


def build_guard_rows(
    candidate_rows: list[dict[str, str]],
    support_rows: list[dict[str, str]],
    issues: list[str],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    by_value = support_groups(support_rows)
    rows: list[dict[str, str]] = []
    support_details: list[dict[str, str]] = []
    detailed_values: set[str] = set()
    for candidate in candidate_rows:
        if candidate.get("blocker_reason") != "cross_pcx_exact_support_only":
            continue
        target_value = candidate.get("target_value", "")
        supports = by_value.get(target_value, [])
        exact_cross = [
            row for row in supports if row.get("support_kind") == "exact" and row.get("same_pcx") != "1"
        ]
        same_pcx_le4 = [
            row
            for row in supports
            if row.get("same_pcx") == "1" and row.get("support_kind") == "le4" and int_value(row, "abs_delta") <= 4
        ]
        same_fixture_le4 = [row for row in same_pcx_le4 if row.get("same_fixture") == "1"]
        best_exact = select_best_exact(supports)
        bridge = select_best_bridge(supports)
        bridge_value = int_value(bridge, "support_value") if bridge else 0
        bridge_delta = int_value(bridge, "delta") if bridge else 0
        predicted = (bridge_value + bridge_delta) & 0xFF if bridge else -1
        ready = bool(exact_cross and same_pcx_le4 and predicted == int_value(candidate, "target_value"))
        if not exact_cross:
            issues.append(f"{target_value}:missing_cross_pcx_exact_support")
        if not same_pcx_le4:
            issues.append(f"{target_value}:missing_same_pcx_le4_bridge")
        if bridge and predicted != int_value(candidate, "target_value"):
            issues.append(f"{target_value}:bridge_prediction_mismatch:{predicted}")
        rows.append(
            {
                "guard_ready": "1" if ready else "0",
                "byte_index": candidate.get("byte_index", ""),
                "source_offset": candidate.get("source_offset", ""),
                "target_offset": candidate.get("target_offset", ""),
                "source_value": candidate.get("source_value", ""),
                "target_value": candidate.get("target_value", ""),
                "target_delta": candidate.get("delta", ""),
                "target_value_class": candidate.get("target_value_class", ""),
                "local_note": candidate.get("local_note", ""),
                "predicted_byte": byte_hex(predicted) if ready else "",
                "best_formula": "stride320_outlier_target_cross_pcx_exact_with_same_pcx_le4_bridge",
                "best_guard_key": (
                    f"target_value={target_value}:"
                    f"exact_cross_pcx={len(exact_cross)}:"
                    f"same_pcx_le4={len(same_pcx_le4)}:"
                    f"same_fixture_le4={len(same_fixture_le4)}:"
                    f"bridge_value={bridge.get('support_value', '')}:"
                    f"bridge_delta={bridge.get('delta', '')}"
                ),
                "exact_cross_pcx_support_rows": str(len(exact_cross)),
                "same_pcx_le4_bridge_rows": str(len(same_pcx_le4)),
                "same_fixture_le4_bridge_rows": str(len(same_fixture_le4)),
                "best_exact_rank": best_exact.get("support_rank", ""),
                "best_exact_archive_tag": best_exact.get("support_archive_tag", ""),
                "best_exact_pcx_name": best_exact.get("support_pcx_name", ""),
                "best_exact_frontier_id": best_exact.get("support_frontier_id", ""),
                "best_exact_offset": best_exact.get("support_offset", ""),
                "bridge_rank": bridge.get("support_rank", ""),
                "bridge_archive_tag": bridge.get("support_archive_tag", ""),
                "bridge_pcx_name": bridge.get("support_pcx_name", ""),
                "bridge_frontier_id": bridge.get("support_frontier_id", ""),
                "bridge_offset": bridge.get("support_offset", ""),
                "bridge_support_value": bridge.get("support_value", ""),
                "bridge_delta": bridge.get("delta", ""),
                "bridge_abs_delta": bridge.get("abs_delta", ""),
                "support_basis": "cross_pcx_exact_plus_same_pcx_le4_bridge" if ready else "incomplete",
            }
        )
        if target_value not in detailed_values:
            support_details.extend(support_details_for_value(supports))
            detailed_values.add(target_value)
    rows.sort(key=lambda row: int_value(row, "target_offset"))
    support_details.sort(
        key=lambda row: (
            int_value(row, "target_value"),
            0 if row.get("guard_role") == "same_pcx_le4_bridge" else 1,
            int_value(row, "abs_delta"),
            int_value(row, "support_rank"),
            int_value(row, "support_offset"),
        )
    )
    return rows, support_details


def build_summary(guard_rows: list[dict[str, str]], issues: list[str]) -> dict[str, str]:
    ready = [row for row in guard_rows if row.get("guard_ready") == "1"]
    values = sorted({row.get("target_value", "") for row in guard_rows if row.get("target_value")}, key=int)
    exact_rows = Counter(
        row.get("target_value", "") for row in guard_rows if int_value(row, "exact_cross_pcx_support_rows") > 0
    )
    bridge_rows = Counter(
        row.get("target_value", "") for row in guard_rows if int_value(row, "same_pcx_le4_bridge_rows") > 0
    )
    same_fixture_rows = Counter(
        row.get("target_value", "") for row in guard_rows if int_value(row, "same_fixture_le4_bridge_rows") > 0
    )
    support_values = Counter(row.get("bridge_support_value", "") for row in guard_rows if row.get("bridge_support_value"))
    support_deltas = Counter(row.get("bridge_delta", "") for row in guard_rows if row.get("bridge_delta"))
    if issues:
        verdict = "frontier80_stride320_outlier_target_cross_pcx_guard_issues"
        next_probe = "review stride-320 outlier target cross-PCX guard input issues"
    elif ready and len(ready) == len(guard_rows):
        verdict = "frontier80_stride320_outlier_target_cross_pcx_guard_ready"
        next_probe = "build guarded target-value replay for stride-320 outliers"
    elif ready:
        verdict = "frontier80_stride320_outlier_target_cross_pcx_guard_partial"
        next_probe = "derive additional cross-PCX guard support for stride-320 target outliers"
    else:
        verdict = "frontier80_stride320_outlier_target_cross_pcx_guard_missing"
        next_probe = "return to target-value dependency search for stride-320 outliers"

    return {
        "scope": "frontier80_stride320_outlier_target_cross_pcx_guard",
        "cross_pcx_candidate_bytes": str(len(guard_rows)),
        "guard_ready_bytes": str(len(ready)),
        "cross_pcx_values": ";".join(values),
        "cross_pcx_target_offsets": ";".join(row.get("target_offset", "") for row in guard_rows),
        "distinct_cross_pcx_values": str(len(values)),
        "exact_cross_pcx_values": ";".join(sorted(exact_rows, key=int)),
        "same_pcx_le4_bridge_values": ";".join(sorted(bridge_rows, key=int)),
        "same_fixture_le4_bridge_values": ";".join(sorted(same_fixture_rows, key=int)),
        "exact_cross_pcx_support_rows": str(max((int_value(row, "exact_cross_pcx_support_rows") for row in guard_rows), default=0)),
        "same_pcx_le4_bridge_rows": str(max((int_value(row, "same_pcx_le4_bridge_rows") for row in guard_rows), default=0)),
        "same_fixture_le4_bridge_rows": str(max((int_value(row, "same_fixture_le4_bridge_rows") for row in guard_rows), default=0)),
        "bridge_support_values": json.dumps(support_values, sort_keys=True, separators=(",", ":")),
        "bridge_deltas": json.dumps(support_deltas, sort_keys=True, separators=(",", ":")),
        "promotion_ready_bytes": "0",
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
    guard_rows: list[dict[str, str]],
    support_details: list[dict[str, str]],
    title: str,
) -> str:
    summary_json = html.escape(json.dumps(summary, indent=2))
    stats = "".join(
        f"<div class=\"stat\"><div class=\"label\">{html.escape(key)}</div>"
        f"<div class=\"value\">{html.escape(summary.get(key, ''))}</div></div>"
        for key in (
            "cross_pcx_candidate_bytes",
            "guard_ready_bytes",
            "cross_pcx_values",
            "same_pcx_le4_bridge_rows",
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
    .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; }}
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
  {table_html("Cross-PCX guard rows", "guard_rows.csv", guard_rows, GUARD_FIELDNAMES)}
  {table_html("Support details", "support_details.csv", support_details, SUPPORT_DETAIL_FIELDNAMES)}
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--target-value-dependency", type=Path, default=DEFAULT_TARGET_VALUE_DEPENDENCY)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Stride-320 Outlier Target Cross-PCX Guard Probe",
    )
    args = parser.parse_args()

    issues: list[str] = []
    candidate_rows = read_csv(args.target_value_dependency / "candidate_outlier_rows.csv")
    support_rows = read_csv(args.target_value_dependency / "support_examples.csv")
    if not candidate_rows:
        issues.append(f"missing_candidate_rows:{args.target_value_dependency / 'candidate_outlier_rows.csv'}")
    if not support_rows:
        issues.append(f"missing_support_examples:{args.target_value_dependency / 'support_examples.csv'}")
    guard_rows, support_details = build_guard_rows(candidate_rows, support_rows, issues)
    summary = build_summary(guard_rows, issues)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "guard_rows.csv", GUARD_FIELDNAMES, guard_rows)
    write_csv(args.output / "support_details.csv", SUPPORT_DETAIL_FIELDNAMES, support_details)
    (args.output / "issues.txt").write_text("\n".join(issues))
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, guard_rows, support_details, args.title), encoding="utf-8")

    print(f"Cross-PCX candidate bytes: {summary['cross_pcx_candidate_bytes']}")
    print(f"Guard-ready bytes: {summary['guard_ready_bytes']}")
    print(f"Cross-PCX values: {summary['cross_pcx_values']}")
    print(f"Bridge deltas: {summary['bridge_deltas']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
