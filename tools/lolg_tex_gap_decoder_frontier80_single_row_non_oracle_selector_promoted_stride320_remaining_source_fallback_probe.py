#!/usr/bin/env python3
"""Select fallback supports for remaining stride-320 source values without exact support."""

from __future__ import annotations

import argparse
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_decoder_frontier80_context_split_residual_low_payload_neighborhood_probe import read_csv
from lolg_tex_gap_opcode_probe import int_value, write_csv


DEFAULT_OUTPUT = Path(
    "output/tex_gap_decoder_frontier80_single_row_non_oracle_selector_promoted_stride320_remaining_source_fallback_probe"
)
DEFAULT_REMAINING_SOURCE_DEPENDENCY = Path(
    "output/tex_gap_decoder_frontier80_single_row_non_oracle_selector_promoted_stride320_remaining_source_dependency_probe"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "unsupported_source_bytes",
    "fallback_candidate_bytes",
    "fallback_ready_bytes",
    "fallback_values",
    "fallback_source_offsets",
    "best_support_values",
    "best_support_deltas",
    "best_same_pcx_support_rows",
    "best_same_fixture_support_rows",
    "promotion_ready_bytes",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

FALLBACK_FIELDNAMES = [
    "fallback_ready",
    "byte_index",
    "source_offset",
    "target_offset",
    "source_value",
    "target_value",
    "target_delta",
    "predicted_byte",
    "best_formula",
    "best_guard_key",
    "support_rank",
    "support_archive_tag",
    "support_pcx_name",
    "support_frontier_id",
    "support_offset",
    "support_value",
    "support_delta",
    "support_abs_delta",
    "same_pcx_delta_support_rows",
    "same_fixture_delta_support_rows",
]


def byte_hex(value: int) -> str:
    return f"{value & 0xFF:02x}"


def support_groups(support_rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in support_rows:
        grouped[row.get("source_value", "")].append(row)
    for rows in grouped.values():
        rows.sort(
            key=lambda row: (
                int_value(row, "abs_delta"),
                0 if row.get("same_pcx") == "1" else 1,
                0 if row.get("same_fixture") == "1" else 1,
                int_value(row, "support_rank"),
                int_value(row, "support_frontier_id"),
                int_value(row, "support_offset"),
            )
        )
    return grouped


def build_fallback_rows(
    candidate_rows: list[dict[str, str]],
    support_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    by_value = support_groups(support_rows)
    rows: list[dict[str, str]] = []
    for candidate in candidate_rows:
        if int_value(candidate, "exact_support_rows") > 0:
            continue
        supports = by_value.get(candidate.get("source_value", ""), [])
        if not supports:
            continue
        best = supports[0]
        support_delta = int_value(best, "delta")
        support_value = int_value(best, "support_value")
        predicted = (support_value + support_delta) & 0xFF
        same_pcx_delta_rows = [
            row
            for row in supports
            if row.get("same_pcx") == "1" and row.get("delta") == best.get("delta")
        ]
        same_fixture_delta_rows = [
            row
            for row in supports
            if row.get("same_fixture") == "1" and row.get("delta") == best.get("delta")
        ]
        ready = predicted == int_value(candidate, "source_value") and bool(same_pcx_delta_rows)
        rows.append(
            {
                "fallback_ready": "1" if ready else "0",
                "byte_index": candidate.get("byte_index", ""),
                "source_offset": candidate.get("source_offset", ""),
                "target_offset": candidate.get("target_offset", ""),
                "source_value": candidate.get("source_value", ""),
                "target_value": candidate.get("target_value", ""),
                "target_delta": candidate.get("target_delta", ""),
                "predicted_byte": byte_hex(predicted),
                "best_formula": "stride320_remaining_source_same_pcx_le4_delta_fallback",
                "best_guard_key": (
                    f"source_value={candidate.get('source_value', '')}:"
                    f"support_value={best.get('support_value', '')}:"
                    f"delta={best.get('delta', '')}:"
                    f"same_pcx_delta_support={len(same_pcx_delta_rows)}"
                ),
                "support_rank": best.get("support_rank", ""),
                "support_archive_tag": best.get("support_archive_tag", ""),
                "support_pcx_name": best.get("support_pcx_name", ""),
                "support_frontier_id": best.get("support_frontier_id", ""),
                "support_offset": best.get("support_offset", ""),
                "support_value": best.get("support_value", ""),
                "support_delta": best.get("delta", ""),
                "support_abs_delta": best.get("abs_delta", ""),
                "same_pcx_delta_support_rows": str(len(same_pcx_delta_rows)),
                "same_fixture_delta_support_rows": str(len(same_fixture_delta_rows)),
            }
        )
    rows.sort(key=lambda row: int_value(row, "source_offset"))
    return rows


def build_summary(fallback_rows: list[dict[str, str]], candidate_rows: list[dict[str, str]]) -> dict[str, str]:
    unsupported = [row for row in candidate_rows if int_value(row, "exact_support_rows") == 0]
    ready = [row for row in fallback_rows if row.get("fallback_ready") == "1"]
    support_values = Counter(row.get("support_value", "") for row in fallback_rows)
    support_deltas = Counter(row.get("support_delta", "") for row in fallback_rows)
    if ready and len(ready) == len(unsupported):
        verdict = "frontier80_stride320_remaining_source_fallback_ready"
        next_probe = "build guarded value selector replay for 39 remaining stride-320 source bytes"
    elif ready:
        verdict = "frontier80_stride320_remaining_source_fallback_partial"
        next_probe = "derive additional fallback for remaining unsupported stride-320 source bytes"
    else:
        verdict = "frontier80_stride320_remaining_source_fallback_missing"
        next_probe = "return to corpus support search for unsupported stride-320 source values"

    return {
        "scope": "frontier80_stride320_remaining_source_fallback",
        "unsupported_source_bytes": str(len(unsupported)),
        "fallback_candidate_bytes": str(len(fallback_rows)),
        "fallback_ready_bytes": str(len(ready)),
        "fallback_values": ";".join(row.get("source_value", "") for row in fallback_rows),
        "fallback_source_offsets": ";".join(row.get("source_offset", "") for row in fallback_rows),
        "best_support_values": json.dumps(support_values, sort_keys=True, separators=(",", ":")),
        "best_support_deltas": json.dumps(support_deltas, sort_keys=True, separators=(",", ":")),
        "best_same_pcx_support_rows": str(
            max((int_value(row, "same_pcx_delta_support_rows") for row in fallback_rows), default=0)
        ),
        "best_same_fixture_support_rows": str(
            max((int_value(row, "same_fixture_delta_support_rows") for row in fallback_rows), default=0)
        ),
        "promotion_ready_bytes": "0",
        "issue_rows": "0",
        "review_verdict": verdict,
        "next_probe": next_probe,
    }


def build_html(summary: dict[str, str], fallback_rows: list[dict[str, str]], title: str) -> str:
    summary_json = html.escape(json.dumps(summary, indent=2))
    headers = "".join(f"<th>{html.escape(field)}</th>" for field in FALLBACK_FIELDNAMES)
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in FALLBACK_FIELDNAMES) + "</tr>"
        for row in fallback_rows
    )
    stats = "".join(
        f"<div class=\"stat\"><div class=\"label\">{html.escape(key)}</div>"
        f"<div class=\"value\">{html.escape(summary.get(key, ''))}</div></div>"
        for key in (
            "unsupported_source_bytes",
            "fallback_ready_bytes",
            "fallback_values",
            "best_support_deltas",
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
  <h2>Fallback rows</h2>
  <p><a href="fallback_rows.csv">fallback_rows.csv</a></p>
  <table><thead><tr>{headers}</tr></thead><tbody>{body}</tbody></table>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--remaining-source-dependency", type=Path, default=DEFAULT_REMAINING_SOURCE_DEPENDENCY)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Stride-320 Remaining Source Fallback Probe",
    )
    args = parser.parse_args()

    candidate_rows = read_csv(args.remaining_source_dependency / "candidate_source_rows.csv")
    support_rows = read_csv(args.remaining_source_dependency / "support_examples.csv")
    fallback_rows = build_fallback_rows(candidate_rows, support_rows)
    summary = build_summary(fallback_rows, candidate_rows)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "fallback_rows.csv", FALLBACK_FIELDNAMES, fallback_rows)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, fallback_rows, args.title))

    print(f"Unsupported source bytes: {summary['unsupported_source_bytes']}")
    print(f"Fallback-ready bytes: {summary['fallback_ready_bytes']}")
    print(f"Fallback values: {summary['fallback_values']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
