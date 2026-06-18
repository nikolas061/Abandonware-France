#!/usr/bin/env python3
"""Profile a selector for the remaining stride-320 tail source byte."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

from lolg_tex_gap_decoder_frontier80_context_split_residual_low_payload_neighborhood_probe import read_csv
from lolg_tex_gap_opcode_probe import int_value, write_csv


DEFAULT_OUTPUT = Path(
    "output/tex_gap_decoder_frontier80_single_row_non_oracle_selector_promoted_stride320_tail_source_selector_probe"
)
DEFAULT_SOURCE_DEPENDENCY = Path(
    "output/tex_gap_decoder_frontier80_single_row_non_oracle_selector_promoted_stride320_source_dependency_probe"
)
DEFAULT_PAIR_ROWS = Path(
    "output/tex_gap_decoder_frontier80_single_row_non_oracle_selector_promoted_stride320_pair_selector_probe/pair_rows.csv"
)
DEFAULT_MANIFEST = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_CLEAN_FIXTURES = Path(
    "output/tex_gap_decoder_frontier80_context_split_residual_low_payload_row_state_source_single_row_delta_non_oracle_selector_promoted_replay/fixtures.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "tail_source_offset",
    "tail_source_value",
    "source_prefix_bytes",
    "prefix_ready_bytes",
    "remaining_source_bytes",
    "exact_support_rows",
    "le4_support_rows",
    "same_fixture_exact_support_rows",
    "best_selector",
    "best_selector_exact_bytes",
    "best_selector_total_bytes",
    "guard_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

SELECTOR_FIELDNAMES = [
    "selector",
    "target_bytes",
    "exact_bytes",
    "coverage_bytes",
    "false_bytes",
    "support_rows",
    "notes",
]

TAIL_CONTEXT_FIELDNAMES = [
    "source_offset",
    "source_value",
    "source_known",
    "prefix_ready_bytes",
    "prefix_blocker_positions",
    "prev32_support_start",
    "prev32_delta_min",
    "prev32_delta_max",
    "prev16_values_hex",
    "next16_values_hex",
    "next16_known_mask",
]

SUPPORT_CONTEXT_FIELDNAMES = [
    "candidate_rank",
    "candidate_archive_tag",
    "candidate_pcx_name",
    "candidate_frontier_id",
    "candidate_offset",
    "candidate_value",
    "delta",
    "abs_delta",
    "same_fixture",
    "offset_mod32",
    "offset_mod320",
    "prev16_values_hex",
    "next16_values_hex",
    "prev16_known_bytes",
    "next16_known_bytes",
]


def fixture_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", "")


def signed_delta(source: int, target: int) -> int:
    delta = (target - source) & 0xFF
    return delta - 256 if delta >= 128 else delta


def load_bytes(path_text: str, issues: list[str], label: str) -> bytes:
    try:
        return Path(path_text).read_bytes()
    except OSError as exc:
        issues.append(f"{label}:read_failed:{exc}")
        return b""


def hex_window(data: bytes, start: int, end: int) -> str:
    return data[max(0, start) : max(0, end)].hex()


def known_count(mask: bytes, start: int, end: int) -> int:
    return sum(1 for value in mask[max(0, start) : max(0, end)] if value)


def known_mask_text(mask: bytes, start: int, end: int) -> str:
    return "".join("1" if value else "0" for value in mask[max(0, start) : max(0, end)])


def load_fixture_maps(
    manifest_rows: list[dict[str, str]],
    clean_rows: list[dict[str, str]],
    issues: list[str],
) -> tuple[dict[tuple[str, str, str], dict[str, str]], dict[tuple[str, str, str], tuple[bytes, bytes]]]:
    clean_by_key = {fixture_key(row): row for row in clean_rows}
    manifest_by_key: dict[tuple[str, str, str], dict[str, str]] = {}
    fixture_data: dict[tuple[str, str, str], tuple[bytes, bytes]] = {}
    for manifest in manifest_rows:
        key = fixture_key(manifest)
        clean = clean_by_key.get(key)
        if not clean:
            continue
        manifest_by_key[key] = manifest
        expected = load_bytes(manifest.get("expected_gap_path", ""), issues, f"{key}:expected")
        mask = load_bytes(clean.get("known_mask_path", ""), issues, f"{key}:known_mask")
        if expected and mask:
            fixture_data[key] = expected, mask
    return manifest_by_key, fixture_data


def build_tail_context_rows(
    source_summary: dict[str, str],
    byte_rows: list[dict[str, str]],
    top_expected: bytes,
    top_mask: bytes,
) -> list[dict[str, str]]:
    remaining = [row for row in byte_rows if row.get("dependency_ready") != "1" and row.get("source_missing") == "1"]
    if not remaining:
        return []
    tail = remaining[0]
    source_offset = int_value(tail, "source_offset")
    prefix_ready_rows = [row for row in byte_rows if row.get("dependency_ready") == "1"]
    deltas = [int_value(row, "delta") for row in prefix_ready_rows]
    return [
        {
            "source_offset": str(source_offset),
            "source_value": tail.get("source_value", "0"),
            "source_known": tail.get("source_known", "0"),
            "prefix_ready_bytes": source_summary.get("best_support_ready_source_bytes", "0"),
            "prefix_blocker_positions": source_summary.get("best_support_blocker_positions", ""),
            "prev32_support_start": source_summary.get("best_support_start", "0"),
            "prev32_delta_min": str(min(deltas) if deltas else 0),
            "prev32_delta_max": str(max(deltas) if deltas else 0),
            "prev16_values_hex": hex_window(top_expected, source_offset - 16, source_offset),
            "next16_values_hex": hex_window(top_expected, source_offset, source_offset + 16),
            "next16_known_mask": known_mask_text(top_mask, source_offset, source_offset + 16),
        }
    ]


def build_support_context_rows(
    tail_support_rows: list[dict[str, str]],
    fixture_data: dict[tuple[str, str, str], tuple[bytes, bytes]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for support in tail_support_rows:
        key = (
            support.get("candidate_rank", ""),
            support.get("candidate_pcx_name", ""),
            support.get("candidate_frontier_id", ""),
        )
        fixture = fixture_data.get(key)
        if not fixture:
            continue
        expected, mask = fixture
        offset = int_value(support, "candidate_offset")
        rows.append(
            {
                "candidate_rank": support.get("candidate_rank", ""),
                "candidate_archive_tag": support.get("candidate_archive_tag", ""),
                "candidate_pcx_name": support.get("candidate_pcx_name", ""),
                "candidate_frontier_id": support.get("candidate_frontier_id", ""),
                "candidate_offset": str(offset),
                "candidate_value": support.get("candidate_value", "0"),
                "delta": support.get("delta", "0"),
                "abs_delta": support.get("abs_delta", "0"),
                "same_fixture": support.get("same_fixture", "0"),
                "offset_mod32": str(offset % 32),
                "offset_mod320": str(offset % 320),
                "prev16_values_hex": hex_window(expected, offset - 16, offset),
                "next16_values_hex": hex_window(expected, offset, offset + 16),
                "prev16_known_bytes": str(known_count(mask, offset - 16, offset)),
                "next16_known_bytes": str(known_count(mask, offset, offset + 16)),
            }
        )
    return rows


def build_selector_rows(source_summary: dict[str, str], tail_context_rows: list[dict[str, str]], tail_support_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    exact_support = [row for row in tail_support_rows if row.get("delta") == "0"]
    le4_support = [row for row in tail_support_rows if int_value(row, "abs_delta") <= 4]
    target_bytes = "1" if tail_context_rows else "0"
    tail_value = tail_context_rows[0].get("source_value", "0") if tail_context_rows else "0"
    return [
        {
            "selector": f"constant_tail_value_{tail_value}",
            "target_bytes": target_bytes,
            "exact_bytes": target_bytes,
            "coverage_bytes": target_bytes,
            "false_bytes": "0",
            "support_rows": str(len(exact_support)),
            "notes": "target-specific remaining source byte after 32-byte prefix support",
        },
        {
            "selector": "external_exact_support_value",
            "target_bytes": target_bytes,
            "exact_bytes": target_bytes if exact_support else "0",
            "coverage_bytes": target_bytes if exact_support else "0",
            "false_bytes": "0",
            "support_rows": str(len(exact_support)),
            "notes": "known corpus bytes exactly match the remaining source value",
        },
        {
            "selector": "external_le4_support_value",
            "target_bytes": target_bytes,
            "exact_bytes": target_bytes if le4_support else "0",
            "coverage_bytes": target_bytes if le4_support else "0",
            "false_bytes": "0",
            "support_rows": str(len(le4_support)),
            "notes": "analysis only; nearby known corpus bytes require a signed-delta guard",
        },
        {
            "selector": "local_prefix_transition_guard",
            "target_bytes": target_bytes,
            "exact_bytes": "0",
            "coverage_bytes": "0",
            "false_bytes": "0",
            "support_rows": source_summary.get("best_support_ready_source_bytes", "0"),
            "notes": "guard context: 32-byte source prefix is ready, tail is the only blocker",
        },
    ]


def build_summary(
    source_summary: dict[str, str],
    tail_context_rows: list[dict[str, str]],
    tail_support_rows: list[dict[str, str]],
    issues: list[str],
) -> dict[str, str]:
    tail = tail_context_rows[0] if tail_context_rows else {}
    exact_support = [row for row in tail_support_rows if row.get("delta") == "0"]
    le4_support = [row for row in tail_support_rows if int_value(row, "abs_delta") <= 4]
    same_fixture_exact = [row for row in exact_support if row.get("same_fixture") == "1"]
    best_selector = f"constant_tail_value_{tail.get('source_value', '0')}" if tail else ""
    if tail and exact_support and int_value(source_summary, "best_support_ready_source_bytes") >= 32:
        verdict = "frontier80_stride320_tail_source_selector_guard_candidate_ready"
        next_probe = "build guarded source-prefix plus tail-byte replay candidate for stride-320 pair"
    elif tail and exact_support:
        verdict = "frontier80_stride320_tail_source_selector_prefix_guard_needed"
        next_probe = "finish source prefix guard before tail-byte replay candidate"
    elif tail:
        verdict = "frontier80_stride320_tail_source_selector_external_support_needed"
        next_probe = "derive external support selector for remaining stride-320 source byte"
    else:
        verdict = "frontier80_stride320_tail_source_selector_no_tail"
        next_probe = "return to stride-320 source dependency review"

    return {
        "scope": "top_pair_tail_source_byte",
        "tail_source_offset": tail.get("source_offset", source_summary.get("remaining_source_offsets", "")),
        "tail_source_value": tail.get("source_value", "0"),
        "source_prefix_bytes": source_summary.get("source_prefix_bytes", "0"),
        "prefix_ready_bytes": source_summary.get("best_support_ready_source_bytes", "0"),
        "remaining_source_bytes": source_summary.get("remaining_source_bytes", "0"),
        "exact_support_rows": str(len(exact_support)),
        "le4_support_rows": str(len(le4_support)),
        "same_fixture_exact_support_rows": str(len(same_fixture_exact)),
        "best_selector": best_selector,
        "best_selector_exact_bytes": "1" if tail and exact_support else "0",
        "best_selector_total_bytes": "1" if tail else "0",
        "guard_candidate_bytes": "1" if tail and exact_support else "0",
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
    selector_rows: list[dict[str, str]],
    tail_context_rows: list[dict[str, str]],
    support_context_rows: list[dict[str, str]],
    title: str,
) -> str:
    summary_json = html.escape(json.dumps(summary, indent=2))
    stats = "".join(
        f"<div class=\"stat\"><div class=\"label\">{html.escape(key)}</div>"
        f"<div class=\"value\">{html.escape(summary.get(key, ''))}</div></div>"
        for key in (
            "tail_source_offset",
            "tail_source_value",
            "exact_support_rows",
            "prefix_ready_bytes",
            "best_selector",
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
  {table_html("Selector rows", "selector_rows.csv", selector_rows, SELECTOR_FIELDNAMES)}
  {table_html("Tail context rows", "tail_context_rows.csv", tail_context_rows, TAIL_CONTEXT_FIELDNAMES)}
  {table_html("Support context rows", "support_context_rows.csv", support_context_rows, SUPPORT_CONTEXT_FIELDNAMES)}
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--source-dependency", type=Path, default=DEFAULT_SOURCE_DEPENDENCY)
    parser.add_argument("--pair-rows", type=Path, default=DEFAULT_PAIR_ROWS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--clean-fixtures", type=Path, default=DEFAULT_CLEAN_FIXTURES)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Stride-320 Tail Source Selector Probe",
    )
    args = parser.parse_args()

    issues: list[str] = []
    source_summary_rows = read_csv(args.source_dependency / "summary.csv")
    byte_rows = read_csv(args.source_dependency / "byte_dependency_rows.csv")
    tail_support_rows = read_csv(args.source_dependency / "tail_support_rows.csv")
    pair_rows = read_csv(args.pair_rows)
    source_summary = source_summary_rows[0] if source_summary_rows else {}
    if not source_summary:
        issues.append(f"missing_source_dependency_summary:{args.source_dependency / 'summary.csv'}")
    if not pair_rows:
        issues.append(f"missing_pair_rows:{args.pair_rows}")
    manifest_rows = read_csv(args.manifest)
    clean_rows = read_csv(args.clean_fixtures)
    manifest_by_key, fixture_data = load_fixture_maps(manifest_rows, clean_rows, issues)

    top_key = fixture_key(pair_rows[0]) if pair_rows else ("", "", "")
    top_manifest = manifest_by_key.get(top_key)
    top_fixture = fixture_data.get(top_key)
    if not top_manifest or not top_fixture:
        issues.append(f"{top_key}:missing_top_fixture")
        top_expected, top_mask = b"", b""
    else:
        top_expected, top_mask = top_fixture

    tail_context_rows = build_tail_context_rows(source_summary, byte_rows, top_expected, top_mask)
    support_context_rows = build_support_context_rows(tail_support_rows, fixture_data)
    selector_rows = build_selector_rows(source_summary, tail_context_rows, tail_support_rows)
    summary = build_summary(source_summary, tail_context_rows, tail_support_rows, issues)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "selector_rows.csv", SELECTOR_FIELDNAMES, selector_rows)
    write_csv(args.output / "tail_context_rows.csv", TAIL_CONTEXT_FIELDNAMES, tail_context_rows)
    write_csv(args.output / "support_context_rows.csv", SUPPORT_CONTEXT_FIELDNAMES, support_context_rows)
    (args.output / "issues.txt").write_text("\n".join(issues))
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, selector_rows, tail_context_rows, support_context_rows, args.title))

    print(
        "Stride-320 tail source selector: "
        f"offset={summary['tail_source_offset']}, "
        f"value={summary['tail_source_value']}, "
        f"exact_support={summary['exact_support_rows']}"
    )
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
