#!/usr/bin/env python3
"""Map bridge residual intervals after no-bridge run-local residual replay."""

from __future__ import annotations

import argparse
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_opcode_probe import relative_href, write_csv
from lolg_tex_gap_decoder_frontier80_clean_structural_nonzero_producer_probe import (
    DEFAULT_CLEAN_FIXTURES,
    DEFAULT_MANIFEST,
    load_target_payloads,
    ratio,
    read_csv,
)
from lolg_tex_gap_decoder_frontier80_clean_structural_nonzero_rle_delta_parser_probe import (
    build_token_rows,
)
from lolg_tex_gap_decoder_frontier80_clean_structural_nonzero_control_bridge_probe import (
    ordered_strong_bridge,
)
from lolg_tex_gap_decoder_frontier80_clean_structural_nonzero_compact_control_grammar_probe import (
    int_field,
)


DEFAULT_COMPACT_INTEGRATED_SUMMARY = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_compact_control_integrated_replay_probe/summary.csv"
)
DEFAULT_COMPACT_INTEGRATED_TARGETS = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_compact_control_integrated_replay_probe/targets.csv"
)
DEFAULT_COMPACT_INTEGRATED_GAPS = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_compact_control_integrated_replay_probe/gaps.csv"
)
DEFAULT_RUN_LOCAL_PROMOTED_SUMMARY = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_no_bridge_run_local_residual_promoted_replay_probe/summary.csv"
)
DEFAULT_RUN_LOCAL_PROMOTED_TARGETS = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_no_bridge_run_local_residual_promoted_replay_probe/targets.csv"
)
DEFAULT_REMAINING_PROFILE_SUMMARY = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_no_bridge_run_local_residual_remaining_profile_probe/summary.csv"
)
DEFAULT_OUTPUT = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_no_bridge_bridge_residual_interval_map_probe"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "selected_target_runs",
    "selected_target_bytes",
    "post_promoted_integrated_target_bytes",
    "post_promoted_integrated_target_ratio",
    "post_promoted_unintegrated_target_bytes",
    "coverage_intervals",
    "coverage_bytes",
    "coverage_no_bridge_bytes",
    "coverage_ordered_bridge_bytes",
    "coverage_compact_gap_bytes",
    "residual_target_runs",
    "residual_intervals",
    "residual_bytes",
    "residual_bridge_bytes",
    "residual_no_bridge_bytes",
    "prefix_residual_bytes",
    "middle_residual_bytes",
    "suffix_residual_bytes",
    "top_residual_pcx",
    "top_residual_frontiers",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

COVERAGE_FIELDNAMES = [
    "target_id",
    "rank",
    "pcx_name",
    "frontier_id",
    "span_index",
    "run_index",
    "coverage_index",
    "coverage_kind",
    "run_offset_start",
    "run_offset_end",
    "length",
    "source_index",
    "source_detail",
    "verdict",
]

RESIDUAL_FIELDNAMES = [
    "target_id",
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "span_index",
    "run_index",
    "residual_index",
    "run_offset_start",
    "run_offset_end",
    "absolute_start",
    "absolute_end",
    "length",
    "position_class",
    "previous_coverage_kind",
    "next_coverage_kind",
    "head_hex",
    "tail_hex",
    "verdict",
    "next_probe",
]


def group_rows(rows: list[dict[str, str]], *fields: str) -> dict[tuple[str, ...], list[dict[str, str]]]:
    grouped: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[tuple(row.get(field, "") for field in fields)].append(row)
    return grouped


def counter_text(counter: Counter[str]) -> str:
    return "|".join(f"{key}:{count}" for key, count in counter.most_common(10))


def merge_intervals(intervals: list[dict[str, str]], length: int, issues: list[str]) -> list[dict[str, str]]:
    merged: list[dict[str, str]] = []
    sorted_rows = sorted(intervals, key=lambda row: (int_field(row, "run_offset_start"), int_field(row, "run_offset_end")))
    for row in sorted_rows:
        start = int_field(row, "run_offset_start", -1)
        end = int_field(row, "run_offset_end", -1)
        if start < 0 or end < start or end > length:
            issues.append(f"{row.get('target_id', '')}:bad_coverage_interval:{start}:{end}:{length}")
            continue
        if not merged or start > int_field(merged[-1], "run_offset_end"):
            merged.append(dict(row))
            continue
        if end > int_field(merged[-1], "run_offset_end"):
            merged[-1]["run_offset_end"] = str(end)
            merged[-1]["length"] = str(end - int_field(merged[-1], "run_offset_start"))
            merged[-1]["coverage_kind"] = f"{merged[-1].get('coverage_kind', '')}+{row.get('coverage_kind', '')}"
    return merged


def coverage_rows_for_payload(
    payload: dict[str, object],
    target: dict[str, str],
    run_local_target: dict[str, str] | None,
    compact_gaps: list[dict[str, str]],
    args: argparse.Namespace,
) -> list[dict[str, str]]:
    data = payload.get("data", b"")
    if not isinstance(data, bytes):
        data = b""
    target_id = target.get("target_id", "")
    rows: list[dict[str, str]] = []
    if run_local_target:
        rows.append(
            {
                "target_id": target_id,
                "rank": target.get("rank", ""),
                "pcx_name": target.get("pcx_name", ""),
                "frontier_id": target.get("frontier_id", ""),
                "span_index": target.get("span_index", ""),
                "run_index": target.get("run_index", ""),
                "coverage_index": "1",
                "coverage_kind": "no_bridge_run_local_promoted",
                "run_offset_start": "0",
                "run_offset_end": str(len(data)),
                "length": str(len(data)),
                "source_index": run_local_target.get("target_id", ""),
                "source_detail": "run_local_residual_promoted_target",
                "verdict": "coverage_interval_ready",
            }
        )
        return rows

    token_rows = build_token_rows(
        payload,
        min_repeat=args.min_repeat,
        min_delta=args.min_delta,
        max_delta=args.max_delta,
    )
    ordered_rows = ordered_strong_bridge(payload, token_rows)
    for bridge_index, bridge in enumerate(ordered_rows, start=1):
        start = int_field(bridge, "run_offset_start")
        end = int_field(bridge, "run_offset_end")
        rows.append(
            {
                "target_id": target_id,
                "rank": target.get("rank", ""),
                "pcx_name": target.get("pcx_name", ""),
                "frontier_id": target.get("frontier_id", ""),
                "span_index": target.get("span_index", ""),
                "run_index": target.get("run_index", ""),
                "coverage_index": str(bridge_index),
                "coverage_kind": "ordered_bridge",
                "run_offset_start": str(start),
                "run_offset_end": str(end),
                "length": str(max(0, end - start)),
                "source_index": bridge.get("bridge_index", ""),
                "source_detail": f"token={bridge.get('token_index', '')};segment={bridge.get('segment_offset', '')}",
                "verdict": "coverage_interval_ready",
            }
        )
    coverage_index = len(rows)
    for gap in compact_gaps:
        target_gap_bytes = int_field(gap, "target_gap_bytes")
        covered = int_field(gap, "promoted_covered_bytes")
        if covered <= 0 or target_gap_bytes <= 0:
            continue
        start = int_field(gap, "previous_run_offset_end")
        end = int_field(gap, "next_run_offset_start")
        if covered < target_gap_bytes:
            end = min(end, start + covered)
            verdict = "coverage_interval_partial"
        else:
            verdict = "coverage_interval_ready"
        coverage_index += 1
        rows.append(
            {
                "target_id": target_id,
                "rank": target.get("rank", ""),
                "pcx_name": target.get("pcx_name", ""),
                "frontier_id": target.get("frontier_id", ""),
                "span_index": target.get("span_index", ""),
                "run_index": target.get("run_index", ""),
                "coverage_index": str(coverage_index),
                "coverage_kind": "compact_control_gap_promoted",
                "run_offset_start": str(start),
                "run_offset_end": str(end),
                "length": str(max(0, end - start)),
                "source_index": gap.get("gap_index", ""),
                "source_detail": f"tokens={gap.get('promoted_token_rows', '0')};covered={covered}",
                "verdict": verdict,
            }
        )
    return rows


def residual_rows_for_target(
    payload: dict[str, object],
    target: dict[str, str],
    merged_coverage: list[dict[str, str]],
) -> list[dict[str, str]]:
    data = payload.get("data", b"")
    if not isinstance(data, bytes):
        data = b""
    base_start = int_field(target, "start")
    rows: list[dict[str, str]] = []
    cursor = 0
    previous_kind = ""
    residual_index = 0
    length = len(data)
    for coverage in merged_coverage:
        start = int_field(coverage, "run_offset_start")
        end = int_field(coverage, "run_offset_end")
        if cursor < start:
            residual_index += 1
            rows.append(build_residual_row(target, data, base_start, residual_index, cursor, start, previous_kind, coverage.get("coverage_kind", "")))
        cursor = max(cursor, end)
        previous_kind = coverage.get("coverage_kind", "")
    if cursor < length:
        residual_index += 1
        rows.append(build_residual_row(target, data, base_start, residual_index, cursor, length, previous_kind, ""))
    return rows


def build_residual_row(
    target: dict[str, str],
    data: bytes,
    base_start: int,
    residual_index: int,
    start: int,
    end: int,
    previous_kind: str,
    next_kind: str,
) -> dict[str, str]:
    chunk = data[start:end]
    if start == 0:
        position_class = "prefix"
    elif end == len(data):
        position_class = "suffix"
    else:
        position_class = "middle"
    return {
        "target_id": target.get("target_id", ""),
        "rank": target.get("rank", ""),
        "archive": target.get("archive", ""),
        "archive_tag": target.get("archive_tag", ""),
        "pcx_name": target.get("pcx_name", ""),
        "frontier_id": target.get("frontier_id", ""),
        "span_index": target.get("span_index", ""),
        "run_index": target.get("run_index", ""),
        "residual_index": str(residual_index),
        "run_offset_start": str(start),
        "run_offset_end": str(end),
        "absolute_start": str(base_start + start),
        "absolute_end": str(base_start + end),
        "length": str(len(chunk)),
        "position_class": position_class,
        "previous_coverage_kind": previous_kind,
        "next_coverage_kind": next_kind,
        "head_hex": chunk[:16].hex(),
        "tail_hex": chunk[-16:].hex() if chunk else "",
        "verdict": "bridge_residual_interval_mapped",
        "next_probe": "derive source grammar for bridge residual intervals",
    }


def build_summary(
    compact_summary: dict[str, str],
    run_local_summary: dict[str, str],
    coverage_rows: list[dict[str, str]],
    residual_rows: list[dict[str, str]],
    issue_count: int,
) -> dict[str, str]:
    coverage_bytes = sum(int_field(row, "length") for row in coverage_rows)
    residual_bytes = sum(int_field(row, "length") for row in residual_rows)
    coverage_kind_bytes = Counter()
    residual_position_bytes = Counter()
    by_pcx = Counter()
    by_frontier = Counter()
    for row in coverage_rows:
        coverage_kind_bytes[row.get("coverage_kind", "")] += int_field(row, "length")
    for row in residual_rows:
        value = int_field(row, "length")
        residual_position_bytes[row.get("position_class", "")] += value
        by_pcx[row.get("pcx_name", "")] += value
        by_frontier[row.get("frontier_id", "")] += value
    verdict = "frontier80_structural_no_bridge_bridge_residual_interval_map_ready"
    next_probe = "derive source grammar for bridge residual intervals"
    expected_integrated = int_field(run_local_summary, "post_promoted_integrated_target_bytes")
    expected_remaining = int_field(run_local_summary, "post_promoted_unintegrated_target_bytes")
    if issue_count or coverage_bytes != expected_integrated or residual_bytes != expected_remaining:
        verdict = "frontier80_structural_no_bridge_bridge_residual_interval_map_issues"
        next_probe = "review bridge residual interval map issues"
    return {
        "scope": "total",
        "selected_target_runs": compact_summary.get("selected_target_runs", "0"),
        "selected_target_bytes": compact_summary.get("selected_target_bytes", "0"),
        "post_promoted_integrated_target_bytes": run_local_summary.get("post_promoted_integrated_target_bytes", "0"),
        "post_promoted_integrated_target_ratio": run_local_summary.get(
            "post_promoted_integrated_target_ratio", "0"
        ),
        "post_promoted_unintegrated_target_bytes": run_local_summary.get(
            "post_promoted_unintegrated_target_bytes", "0"
        ),
        "coverage_intervals": str(len(coverage_rows)),
        "coverage_bytes": str(coverage_bytes),
        "coverage_no_bridge_bytes": str(coverage_kind_bytes.get("no_bridge_run_local_promoted", 0)),
        "coverage_ordered_bridge_bytes": str(coverage_kind_bytes.get("ordered_bridge", 0)),
        "coverage_compact_gap_bytes": str(coverage_kind_bytes.get("compact_control_gap_promoted", 0)),
        "residual_target_runs": str(len({row.get("target_id", "") for row in residual_rows})),
        "residual_intervals": str(len(residual_rows)),
        "residual_bytes": str(residual_bytes),
        "residual_bridge_bytes": str(residual_bytes),
        "residual_no_bridge_bytes": "0",
        "prefix_residual_bytes": str(residual_position_bytes.get("prefix", 0)),
        "middle_residual_bytes": str(residual_position_bytes.get("middle", 0)),
        "suffix_residual_bytes": str(residual_position_bytes.get("suffix", 0)),
        "top_residual_pcx": counter_text(by_pcx),
        "top_residual_frontiers": counter_text(by_frontier),
        "issue_rows": str(issue_count),
        "review_verdict": verdict,
        "next_probe": next_probe,
    }


def render_table(rows: list[dict[str, str]], fieldnames: list[str], *, limit: int = 100) -> str:
    if not rows:
        return "<p class=\"muted\">No rows.</p>"
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fieldnames)
    body = []
    for row in rows[:limit]:
        body.append(
            "<tr>"
            + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fieldnames)
            + "</tr>"
        )
    note = "" if len(rows) <= limit else f"<p class=\"muted\">Showing {limit} of {len(rows)} rows.</p>"
    return f"{note}<table><thead><tr>{header}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def build_html(
    output: Path,
    title: str,
    summary: dict[str, str],
    coverage_rows: list[dict[str, str]],
    residual_rows: list[dict[str, str]],
) -> str:
    payload = {"summary": summary, "coverage": coverage_rows, "residuals": residual_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    cards = [
        ("Coverage", summary.get("coverage_bytes", "0")),
        ("Residual", summary.get("residual_bytes", "0")),
        ("Residual spans", summary.get("residual_intervals", "0")),
        ("Targets", summary.get("residual_target_runs", "0")),
        ("Verdict", summary.get("review_verdict", "")),
    ]
    card_html = "".join(
        f"<div class=\"card\"><div class=\"value\">{html.escape(value)}</div>"
        f"<div class=\"label\">{html.escape(label)}</div></div>"
        for label, value in cards
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{html.escape(title)}</title>
  <style>
    body {{ margin: 0; font: 14px/1.45 system-ui, sans-serif; color: #20242a; background: #f6f7f9; }}
    main {{ max-width: 1320px; margin: 0 auto; padding: 24px; }}
    h1 {{ margin: 0 0 8px; font-size: 24px; }}
    h2 {{ margin: 0 0 12px; font-size: 17px; }}
    .muted {{ color: #68717d; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; margin: 18px 0; }}
    .card, section {{ background: #fff; border: 1px solid #d8dde5; border-radius: 8px; }}
    .card {{ padding: 14px; }}
    .value {{ font-size: 20px; font-weight: 700; overflow-wrap: anywhere; }}
    .label {{ margin-top: 4px; color: #68717d; }}
    section {{ padding: 16px; margin: 16px 0; overflow: auto; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
    th, td {{ padding: 6px 8px; border-bottom: 1px solid #e3e7ed; text-align: left; vertical-align: top; }}
    th {{ position: sticky; top: 0; background: #eef2f6; }}
    td {{ max-width: 360px; overflow-wrap: anywhere; }}
    a {{ color: #1f5aa6; }}
  </style>
</head>
<body>
<main>
  <h1>{html.escape(title)}</h1>
  <div class="muted">Maps exact residual intervals left by bridge coverage after no-bridge run-local replay.</div>
  <div class="grid">{card_html}</div>
  <section><h2>Outputs</h2>
    <p><a href="{relative_href(output / 'summary.csv', output / 'index.html')}">summary.csv</a> ·
    <a href="{relative_href(output / 'coverage_intervals.csv', output / 'index.html')}">coverage_intervals.csv</a> ·
    <a href="{relative_href(output / 'residual_intervals.csv', output / 'index.html')}">residual_intervals.csv</a></p>
  </section>
  <section><h2>Residual Intervals</h2>{render_table(residual_rows, RESIDUAL_FIELDNAMES)}</section>
  <section><h2>Coverage Intervals</h2>{render_table(coverage_rows, COVERAGE_FIELDNAMES)}</section>
</main>
<script type="application/json" id="bridge-residual-interval-map-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> dict[str, str]:
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    compact_summary_rows = read_csv(args.compact_integrated_summary)
    compact_summary = compact_summary_rows[0] if compact_summary_rows else {}
    run_local_summary_rows = read_csv(args.run_local_promoted_summary)
    run_local_summary = run_local_summary_rows[0] if run_local_summary_rows else {}
    remaining_summary_rows = read_csv(args.remaining_profile_summary)
    remaining_summary = remaining_summary_rows[0] if remaining_summary_rows else {}
    targets = read_csv(args.compact_integrated_targets)
    run_local_targets = {
        row.get("target_id", ""): row for row in read_csv(args.run_local_promoted_targets)
    }
    compact_gaps_by_target = group_rows(read_csv(args.compact_integrated_gaps), "target_id")
    payloads = load_target_payloads(targets, read_csv(args.manifest), read_csv(args.clean_fixtures), issues)
    coverage_rows: list[dict[str, str]] = []
    residual_rows: list[dict[str, str]] = []
    for payload in payloads:
        target = payload.get("target", {})
        data = payload.get("data", b"")
        if not isinstance(target, dict) or not isinstance(data, bytes):
            continue
        target_id = target.get("target_id", "")
        target_coverage = coverage_rows_for_payload(
            payload,
            target,
            run_local_targets.get(target_id),
            compact_gaps_by_target.get((target_id,), []),
            args,
        )
        merged_coverage = merge_intervals(target_coverage, len(data), issues)
        expected_integrated = (
            int_field(run_local_targets[target_id], "post_promoted_integrated_target_bytes")
            if target_id in run_local_targets
            else int_field(target, "integrated_target_bytes")
        )
        measured_integrated = sum(int_field(row, "length") for row in merged_coverage)
        if measured_integrated != expected_integrated:
            issues.append(f"{target_id}:integrated_interval_mismatch:{measured_integrated}!={expected_integrated}")
        target_residuals = residual_rows_for_target(payload, target, merged_coverage)
        coverage_rows.extend(target_coverage)
        residual_rows.extend(target_residuals)

    measured_residual = sum(int_field(row, "length") for row in residual_rows)
    expected_residual = int_field(remaining_summary, "remaining_bytes")
    if expected_residual and measured_residual != expected_residual:
        issues.append(f"residual_total_mismatch:{measured_residual}!={expected_residual}")
    summary = build_summary(compact_summary, run_local_summary, coverage_rows, residual_rows, len(issues))
    write_csv(output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output / "coverage_intervals.csv", COVERAGE_FIELDNAMES, coverage_rows)
    write_csv(output / "residual_intervals.csv", RESIDUAL_FIELDNAMES, residual_rows)
    (output / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""))
    (output / "index.html").write_text(build_html(output, args.title, summary, coverage_rows, residual_rows))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Map bridge residual intervals after no-bridge run-local replay.")
    parser.add_argument("--compact-integrated-summary", type=Path, default=DEFAULT_COMPACT_INTEGRATED_SUMMARY)
    parser.add_argument("--compact-integrated-targets", type=Path, default=DEFAULT_COMPACT_INTEGRATED_TARGETS)
    parser.add_argument("--compact-integrated-gaps", type=Path, default=DEFAULT_COMPACT_INTEGRATED_GAPS)
    parser.add_argument("--run-local-promoted-summary", type=Path, default=DEFAULT_RUN_LOCAL_PROMOTED_SUMMARY)
    parser.add_argument("--run-local-promoted-targets", type=Path, default=DEFAULT_RUN_LOCAL_PROMOTED_TARGETS)
    parser.add_argument("--remaining-profile-summary", type=Path, default=DEFAULT_REMAINING_PROFILE_SUMMARY)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--clean-fixtures", type=Path, default=DEFAULT_CLEAN_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--min-repeat", type=int, default=2)
    parser.add_argument("--min-delta", type=int, default=4)
    parser.add_argument("--max-delta", type=int, default=2)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Structural No-Bridge Bridge Residual Interval Map",
    )
    args = parser.parse_args()
    summary = write_report(args)
    print(f"Coverage bytes: {summary['coverage_bytes']}")
    print(f"Residual bytes: {summary['residual_bytes']}")
    print(f"Residual intervals: {summary['residual_intervals']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
