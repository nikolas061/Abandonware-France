#!/usr/bin/env python3
"""Promote guarded no-bridge weak anchors into structural replay coverage."""

from __future__ import annotations

import argparse
import html
import json
from collections import defaultdict
from pathlib import Path

from lolg_tex_gap_opcode_probe import relative_href, write_csv
from lolg_tex_gap_decoder_frontier80_clean_structural_nonzero_producer_probe import (
    DEFAULT_CLEAN_FIXTURES,
    DEFAULT_MANIFEST,
    int_value,
    load_target_payloads,
    ratio,
    read_csv,
)
from lolg_tex_gap_decoder_frontier80_clean_structural_nonzero_compact_control_grammar_probe import (
    int_field,
)


DEFAULT_INTEGRATED_SUMMARY = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_compact_control_integrated_replay_probe/summary.csv"
)
DEFAULT_INTEGRATED_TARGETS = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_compact_control_integrated_replay_probe/targets.csv"
)
DEFAULT_ANCHORS = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_no_bridge_anchor_probe/anchors.csv"
)
DEFAULT_GAPS = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_no_bridge_anchor_probe/gaps.csv"
)
DEFAULT_OUTPUT = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_no_bridge_anchor_promoted_replay_probe"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "selected_target_runs",
    "selected_target_bytes",
    "baseline_integrated_target_bytes",
    "baseline_integrated_target_ratio",
    "baseline_unintegrated_target_bytes",
    "no_bridge_target_runs",
    "no_bridge_target_bytes",
    "promoted_anchor_rows",
    "promoted_anchor_bytes",
    "promoted_anchor_target_runs",
    "promoted_anchor_target_bytes",
    "promoted_anchor_false_bytes",
    "weak_gap_rows",
    "weak_gap_target_bytes",
    "weak_gap_segment_bytes",
    "weak_envelope_bytes",
    "post_promoted_integrated_target_bytes",
    "post_promoted_integrated_target_ratio",
    "post_promoted_unintegrated_target_bytes",
    "remaining_no_anchor_target_runs",
    "remaining_no_anchor_target_bytes",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

TARGET_FIELDNAMES = [
    "target_id",
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "span_index",
    "run_index",
    "start",
    "end",
    "length",
    "baseline_integrated_target_bytes",
    "promoted_anchor_rows",
    "promoted_anchor_bytes",
    "promoted_anchor_false_bytes",
    "weak_gap_rows",
    "weak_gap_target_bytes",
    "weak_gap_segment_bytes",
    "weak_envelope_bytes",
    "post_promoted_integrated_target_bytes",
    "post_promoted_unintegrated_target_bytes",
    "verdict",
    "next_probe",
]

ANCHOR_FIELDNAMES = [
    "target_id",
    "rank",
    "pcx_name",
    "frontier_id",
    "span_index",
    "anchor_index",
    "token_index",
    "run_offset_start",
    "run_offset_end",
    "segment_offset",
    "segment_end",
    "length",
    "guard",
    "target_hex",
    "segment_hex",
    "exact_replay",
    "verdict",
]

GAP_FIELDNAMES = [
    "target_id",
    "rank",
    "pcx_name",
    "frontier_id",
    "span_index",
    "gap_index",
    "previous_anchor_index",
    "next_anchor_index",
    "run_gap_bytes",
    "segment_gap_bytes",
    "verdict",
    "next_probe",
]


def group_rows(rows: list[dict[str, str]], field: str) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row.get(field, "")].append(row)
    return grouped


def no_bridge_targets(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [row for row in rows if row.get("verdict") == "no_bridge_anchor"]


def validate_anchor_rows(payload: dict[str, object], anchor_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    target = payload.get("target", {})
    data = payload.get("data", b"")
    segment = payload.get("segment", b"")
    if not isinstance(target, dict):
        target = {}
    if not isinstance(data, bytes):
        data = b""
    if not isinstance(segment, bytes):
        segment = b""
    rows: list[dict[str, str]] = []
    for anchor in anchor_rows:
        run_start = int_field(anchor, "run_offset_start", -1)
        run_end = int_field(anchor, "run_offset_end", -1)
        segment_offset = int_field(anchor, "segment_offset", -1)
        segment_end = int_field(anchor, "segment_end", -1)
        target_chunk = data[run_start:run_end] if 0 <= run_start <= run_end <= len(data) else b""
        segment_chunk = (
            segment[segment_offset:segment_end] if 0 <= segment_offset <= segment_end <= len(segment) else b""
        )
        exact = bool(target_chunk and target_chunk == segment_chunk)
        rows.append(
            {
                "target_id": target.get("target_id", ""),
                "rank": target.get("rank", ""),
                "pcx_name": target.get("pcx_name", ""),
                "frontier_id": target.get("frontier_id", ""),
                "span_index": target.get("span_index", ""),
                "anchor_index": anchor.get("anchor_index", ""),
                "token_index": anchor.get("token_index", ""),
                "run_offset_start": anchor.get("run_offset_start", ""),
                "run_offset_end": anchor.get("run_offset_end", ""),
                "segment_offset": anchor.get("segment_offset", ""),
                "segment_end": anchor.get("segment_end", ""),
                "length": anchor.get("length", ""),
                "guard": anchor.get("guard", ""),
                "target_hex": target_chunk.hex(),
                "segment_hex": segment_chunk.hex(),
                "exact_replay": "1" if exact else "0",
                "verdict": "promoted_anchor_exact" if exact else "promoted_anchor_mismatch",
            }
        )
    return rows


def gap_rows_for_target(target: dict[str, str], rows: list[dict[str, str]]) -> list[dict[str, str]]:
    gap_rows: list[dict[str, str]] = []
    for row in rows:
        gap_rows.append(
            {
                "target_id": target.get("target_id", ""),
                "rank": target.get("rank", ""),
                "pcx_name": target.get("pcx_name", ""),
                "frontier_id": target.get("frontier_id", ""),
                "span_index": target.get("span_index", ""),
                "gap_index": row.get("gap_index", ""),
                "previous_anchor_index": row.get("previous_anchor_index", ""),
                "next_anchor_index": row.get("next_anchor_index", ""),
                "run_gap_bytes": row.get("run_gap_bytes", ""),
                "segment_gap_bytes": row.get("segment_gap_bytes", ""),
                "verdict": "weak_anchor_gap_unresolved",
                "next_probe": "derive compact-control grammar for weak no-bridge anchor gaps",
            }
        )
    return gap_rows


def target_summary(
    target: dict[str, str],
    anchor_rows: list[dict[str, str]],
    gap_rows: list[dict[str, str]],
) -> dict[str, str]:
    length = int_field(target, "length")
    baseline = int_field(target, "integrated_target_bytes")
    exact_anchor_rows = [row for row in anchor_rows if row.get("exact_replay") == "1"]
    false_anchor_bytes = sum(int_field(row, "length") for row in anchor_rows if row.get("exact_replay") != "1")
    promoted_anchor_bytes = sum(int_field(row, "length") for row in exact_anchor_rows)
    weak_gap_target_bytes = sum(int_field(row, "run_gap_bytes") for row in gap_rows)
    weak_gap_segment_bytes = sum(int_field(row, "segment_gap_bytes") for row in gap_rows)
    weak_envelope = promoted_anchor_bytes + weak_gap_target_bytes
    post_integrated = baseline + promoted_anchor_bytes
    if false_anchor_bytes:
        verdict = "promoted_no_bridge_anchor_mismatch"
        next_probe = "review promoted no-bridge anchor mismatches"
    elif promoted_anchor_bytes:
        verdict = "promoted_no_bridge_anchor_replay_ready"
        next_probe = "derive compact-control grammar for weak no-bridge anchor gaps"
    else:
        verdict = "no_bridge_anchor_not_promoted"
        next_probe = "derive non-segment sources for remaining no-bridge runs"
    return {
        "target_id": target.get("target_id", ""),
        "rank": target.get("rank", ""),
        "archive": target.get("archive", ""),
        "archive_tag": target.get("archive_tag", ""),
        "pcx_name": target.get("pcx_name", ""),
        "frontier_id": target.get("frontier_id", ""),
        "span_index": target.get("span_index", ""),
        "run_index": target.get("run_index", ""),
        "start": target.get("start", ""),
        "end": target.get("end", ""),
        "length": str(length),
        "baseline_integrated_target_bytes": str(baseline),
        "promoted_anchor_rows": str(len(exact_anchor_rows)),
        "promoted_anchor_bytes": str(promoted_anchor_bytes),
        "promoted_anchor_false_bytes": str(false_anchor_bytes),
        "weak_gap_rows": str(len(gap_rows)),
        "weak_gap_target_bytes": str(weak_gap_target_bytes),
        "weak_gap_segment_bytes": str(weak_gap_segment_bytes),
        "weak_envelope_bytes": str(weak_envelope),
        "post_promoted_integrated_target_bytes": str(post_integrated),
        "post_promoted_unintegrated_target_bytes": str(max(0, length - post_integrated)),
        "verdict": verdict,
        "next_probe": next_probe,
    }


def total_summary(
    integrated_summary: dict[str, str],
    no_bridge_rows: list[dict[str, str]],
    target_rows: list[dict[str, str]],
    anchor_rows: list[dict[str, str]],
    gap_rows: list[dict[str, str]],
    issue_count: int,
) -> dict[str, str]:
    selected_target_runs = int_field(integrated_summary, "selected_target_runs")
    selected_target_bytes = int_field(integrated_summary, "selected_target_bytes")
    baseline_integrated = int_field(integrated_summary, "integrated_target_bytes")
    promoted_anchor_bytes = sum(int_field(row, "promoted_anchor_bytes") for row in target_rows)
    false_anchor_bytes = sum(int_field(row, "promoted_anchor_false_bytes") for row in target_rows)
    post_integrated = baseline_integrated + promoted_anchor_bytes
    promoted_targets = [row for row in target_rows if int_field(row, "promoted_anchor_bytes") > 0]
    remaining_no_anchor = [row for row in target_rows if int_field(row, "promoted_anchor_bytes") == 0]
    verdict = "frontier80_structural_no_bridge_anchor_promoted_replay_ready"
    next_probe = "derive compact-control grammar for weak no-bridge anchor gaps"
    if issue_count or false_anchor_bytes:
        verdict = "frontier80_structural_no_bridge_anchor_promoted_replay_issues"
        next_probe = "review promoted no-bridge anchor replay issues"
    elif promoted_anchor_bytes == 0:
        verdict = "frontier80_structural_no_bridge_anchor_promoted_replay_empty"
        next_probe = "derive non-segment sources for remaining no-bridge runs"
    return {
        "scope": "total",
        "selected_target_runs": str(selected_target_runs),
        "selected_target_bytes": str(selected_target_bytes),
        "baseline_integrated_target_bytes": str(baseline_integrated),
        "baseline_integrated_target_ratio": ratio(baseline_integrated, selected_target_bytes),
        "baseline_unintegrated_target_bytes": str(max(0, selected_target_bytes - baseline_integrated)),
        "no_bridge_target_runs": str(len(no_bridge_rows)),
        "no_bridge_target_bytes": str(sum(int_field(row, "length") for row in no_bridge_rows)),
        "promoted_anchor_rows": str(sum(int_field(row, "promoted_anchor_rows") for row in target_rows)),
        "promoted_anchor_bytes": str(promoted_anchor_bytes),
        "promoted_anchor_target_runs": str(len(promoted_targets)),
        "promoted_anchor_target_bytes": str(sum(int_field(row, "length") for row in promoted_targets)),
        "promoted_anchor_false_bytes": str(false_anchor_bytes),
        "weak_gap_rows": str(len(gap_rows)),
        "weak_gap_target_bytes": str(sum(int_field(row, "run_gap_bytes") for row in gap_rows)),
        "weak_gap_segment_bytes": str(sum(int_field(row, "segment_gap_bytes") for row in gap_rows)),
        "weak_envelope_bytes": str(sum(int_field(row, "weak_envelope_bytes") for row in target_rows)),
        "post_promoted_integrated_target_bytes": str(post_integrated),
        "post_promoted_integrated_target_ratio": ratio(post_integrated, selected_target_bytes),
        "post_promoted_unintegrated_target_bytes": str(max(0, selected_target_bytes - post_integrated)),
        "remaining_no_anchor_target_runs": str(len(remaining_no_anchor)),
        "remaining_no_anchor_target_bytes": str(sum(int_field(row, "length") for row in remaining_no_anchor)),
        "issue_rows": str(issue_count),
        "review_verdict": verdict,
        "next_probe": next_probe,
    }


def render_table(rows: list[dict[str, str]], fieldnames: list[str], *, limit: int = 80) -> str:
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
    target_rows: list[dict[str, str]],
    anchor_rows: list[dict[str, str]],
    gap_rows: list[dict[str, str]],
) -> str:
    payload = {"summary": summary, "targets": target_rows, "anchors": anchor_rows, "gaps": gap_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    cards = [
        ("Baseline integrated", summary.get("baseline_integrated_target_bytes", "0")),
        ("Promoted anchors", summary.get("promoted_anchor_bytes", "0")),
        ("Post integrated", summary.get("post_promoted_integrated_target_bytes", "0")),
        ("Weak gaps", summary.get("weak_gap_target_bytes", "0")),
        ("Remaining", summary.get("post_promoted_unintegrated_target_bytes", "0")),
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
  <div class="muted">Promotes exact guarded no-bridge anchors while leaving weak gaps unresolved for the next grammar pass.</div>
  <div class="grid">{card_html}</div>
  <section><h2>Outputs</h2>
    <p><a href="{relative_href(output / 'summary.csv', output / 'index.html')}">summary.csv</a> ·
    <a href="{relative_href(output / 'targets.csv', output / 'index.html')}">targets.csv</a> ·
    <a href="{relative_href(output / 'anchor_validation.csv', output / 'index.html')}">anchor_validation.csv</a> ·
    <a href="{relative_href(output / 'weak_gaps.csv', output / 'index.html')}">weak_gaps.csv</a></p>
  </section>
  <section><h2>Targets</h2>{render_table(target_rows, TARGET_FIELDNAMES)}</section>
  <section><h2>Anchor Validation</h2>{render_table(anchor_rows, ANCHOR_FIELDNAMES)}</section>
  <section><h2>Weak Gaps</h2>{render_table(gap_rows, GAP_FIELDNAMES)}</section>
</main>
<script type="application/json" id="no-bridge-anchor-promoted-replay-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> dict[str, str]:
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    integrated_rows = read_csv(args.integrated_targets)
    integrated_summary_rows = read_csv(args.integrated_summary)
    integrated_summary = integrated_summary_rows[0] if integrated_summary_rows else {}
    no_bridge_rows = no_bridge_targets(integrated_rows)
    no_bridge_by_target = {row.get("target_id", ""): row for row in no_bridge_rows}
    anchors_by_target = group_rows(read_csv(args.anchors), "target_id")
    gaps_by_target = group_rows(read_csv(args.gaps), "target_id")
    payloads = load_target_payloads(
        no_bridge_rows,
        read_csv(args.manifest),
        read_csv(args.clean_fixtures),
        issues,
    )

    target_rows: list[dict[str, str]] = []
    anchor_rows: list[dict[str, str]] = []
    gap_rows: list[dict[str, str]] = []
    seen_targets: set[str] = set()
    for payload in payloads:
        target = payload.get("target", {})
        if not isinstance(target, dict):
            continue
        target_id = target.get("target_id", "")
        seen_targets.add(target_id)
        payload_anchor_rows = validate_anchor_rows(payload, anchors_by_target.get(target_id, []))
        payload_gap_rows = gap_rows_for_target(target, gaps_by_target.get(target_id, []))
        target_rows.append(target_summary(no_bridge_by_target.get(target_id, target), payload_anchor_rows, payload_gap_rows))
        anchor_rows.extend(payload_anchor_rows)
        gap_rows.extend(payload_gap_rows)

    for target_id, rows in anchors_by_target.items():
        if target_id not in seen_targets and rows:
            issues.append(f"{target_id}:anchor_without_no_bridge_target_payload")

    summary = total_summary(integrated_summary, no_bridge_rows, target_rows, anchor_rows, gap_rows, len(issues))
    write_csv(output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output / "targets.csv", TARGET_FIELDNAMES, target_rows)
    write_csv(output / "anchor_validation.csv", ANCHOR_FIELDNAMES, anchor_rows)
    write_csv(output / "weak_gaps.csv", GAP_FIELDNAMES, gap_rows)
    (output / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""))
    (output / "index.html").write_text(build_html(output, args.title, summary, target_rows, anchor_rows, gap_rows))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Promote guarded no-bridge weak anchors into structural replay coverage."
    )
    parser.add_argument("--integrated-summary", type=Path, default=DEFAULT_INTEGRATED_SUMMARY)
    parser.add_argument("--integrated-targets", type=Path, default=DEFAULT_INTEGRATED_TARGETS)
    parser.add_argument("--anchors", type=Path, default=DEFAULT_ANCHORS)
    parser.add_argument("--gaps", type=Path, default=DEFAULT_GAPS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--clean-fixtures", type=Path, default=DEFAULT_CLEAN_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Structural No-Bridge Anchor Promoted Replay Probe",
    )
    args = parser.parse_args()
    summary = write_report(args)
    print(f"Baseline integrated bytes: {summary['baseline_integrated_target_bytes']}")
    print(f"Promoted anchor bytes: {summary['promoted_anchor_bytes']}")
    print(f"Post promoted integrated bytes: {summary['post_promoted_integrated_target_bytes']}")
    print(f"Weak gap bytes: {summary['weak_gap_target_bytes']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
