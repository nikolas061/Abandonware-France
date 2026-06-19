#!/usr/bin/env python3
"""Integrate promoted compact-control grammar with structural nonzero bridge coverage."""

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
    DEFAULT_RUNS,
    int_value,
    load_target_payloads,
    ratio,
    read_csv,
    target_id as make_target_id,
)
from lolg_tex_gap_decoder_frontier80_clean_structural_nonzero_rle_delta_parser_probe import (
    build_token_rows,
)
from lolg_tex_gap_decoder_frontier80_clean_structural_nonzero_control_bridge_probe import (
    build_control_gap_rows,
    ordered_strong_bridge,
)
from lolg_tex_gap_decoder_frontier80_clean_structural_nonzero_compact_control_grammar_probe import (
    int_field,
)


DEFAULT_PROMOTED_GRAMMAR_TOKENS = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_compact_control_near_anchor_promoted_grammar_probe/token_validation.csv"
)
DEFAULT_OUTPUT = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_compact_control_integrated_replay_probe"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "selected_target_runs",
    "selected_target_bytes",
    "token_rows",
    "token_bytes",
    "generated_bytes",
    "literal_bytes",
    "ordered_bridge_rows",
    "ordered_bridge_bytes",
    "control_gap_rows",
    "control_gap_target_bytes",
    "promoted_grammar_token_rows",
    "promoted_grammar_bytes",
    "promoted_grammar_unresolved_bytes",
    "integrated_target_bytes",
    "integrated_target_ratio",
    "unintegrated_target_bytes",
    "bridge_envelope_rows",
    "bridge_envelope_bytes",
    "bridge_envelope_ratio",
    "full_envelope_rows",
    "partial_envelope_rows",
    "no_bridge_target_runs",
    "no_bridge_target_bytes",
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
    "token_rows",
    "generated_bytes",
    "literal_bytes",
    "ordered_bridge_rows",
    "ordered_bridge_bytes",
    "control_gap_rows",
    "control_gap_target_bytes",
    "promoted_grammar_bytes",
    "promoted_grammar_unresolved_bytes",
    "integrated_target_bytes",
    "bridge_envelope_bytes",
    "verdict",
    "next_probe",
]

GAP_FIELDNAMES = [
    "target_id",
    "rank",
    "pcx_name",
    "frontier_id",
    "span_index",
    "gap_index",
    "previous_token_index",
    "next_token_index",
    "previous_run_offset_end",
    "next_run_offset_start",
    "target_gap_bytes",
    "previous_segment_end",
    "next_segment_offset",
    "segment_gap_bytes",
    "promoted_token_rows",
    "promoted_token_bytes",
    "promoted_covered_bytes",
    "promoted_unresolved_bytes",
    "verdict",
]


def select_targets(run_rows: list[dict[str, str]], *, min_length: int, limit: int) -> list[dict[str, str]]:
    targets = [
        {**row, "target_id": make_target_id(row)}
        for row in run_rows
        if row.get("run_class") == "nonzero" and int_value(row, "length") >= min_length
    ]
    targets.sort(
        key=lambda row: (
            -int_value(row, "length"),
            row.get("pcx_name", ""),
            int_value(row, "start"),
        )
    )
    return targets[:limit] if limit > 0 else targets


def group_rows(rows: list[dict[str, str]], *fields: str) -> dict[tuple[str, ...], list[dict[str, str]]]:
    grouped: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[tuple(row.get(field, "") for field in fields)].append(row)
    return grouped


def target_summary(
    payload: dict[str, object],
    token_rows: list[dict[str, str]],
    ordered_rows: list[dict[str, str]],
    gap_rows: list[dict[str, str]],
) -> dict[str, str]:
    target = payload.get("target", {})
    data = payload.get("data", b"")
    if not isinstance(target, dict) or not isinstance(data, bytes):
        return {}
    ordered_bytes = sum(int_field(row, "length") for row in ordered_rows)
    target_gap_bytes = sum(int_field(row, "target_gap_bytes") for row in gap_rows)
    promoted_bytes = sum(int_field(row, "promoted_covered_bytes") for row in gap_rows)
    promoted_unresolved = sum(int_field(row, "promoted_unresolved_bytes") for row in gap_rows)
    envelope_bytes = ordered_bytes + target_gap_bytes
    integrated_bytes = ordered_bytes + promoted_bytes
    if not ordered_rows:
        verdict = "no_bridge_anchor"
        next_probe = "derive bridge anchors for no-bridge structural nonzero runs"
    elif promoted_unresolved:
        verdict = "partial_promoted_compact_control_envelope"
        next_probe = "split promoted compact-control integration residuals"
    else:
        verdict = "promoted_compact_control_envelope_integrated"
        next_probe = "derive bridge anchors for no-bridge structural nonzero runs"
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
        "length": str(len(data)),
        "token_rows": str(len(token_rows)),
        "generated_bytes": str(sum(int_field(row, "generated_bytes") for row in token_rows)),
        "literal_bytes": str(sum(int_field(row, "length") for row in token_rows if row.get("token_type") == "literal")),
        "ordered_bridge_rows": str(len(ordered_rows)),
        "ordered_bridge_bytes": str(ordered_bytes),
        "control_gap_rows": str(len(gap_rows)),
        "control_gap_target_bytes": str(target_gap_bytes),
        "promoted_grammar_bytes": str(promoted_bytes),
        "promoted_grammar_unresolved_bytes": str(promoted_unresolved),
        "integrated_target_bytes": str(integrated_bytes),
        "bridge_envelope_bytes": str(envelope_bytes),
        "verdict": verdict,
        "next_probe": next_probe,
    }


def total_summary(target_rows: list[dict[str, str]], gap_rows: list[dict[str, str]], issue_count: int) -> dict[str, str]:
    target_bytes = sum(int_field(row, "length") for row in target_rows)
    integrated = sum(int_field(row, "integrated_target_bytes") for row in target_rows)
    envelope = sum(int_field(row, "bridge_envelope_bytes") for row in target_rows)
    promoted_unresolved = sum(int_field(row, "promoted_grammar_unresolved_bytes") for row in target_rows)
    no_bridge = [row for row in target_rows if row.get("verdict") == "no_bridge_anchor"]
    partial = [row for row in target_rows if row.get("verdict") == "partial_promoted_compact_control_envelope"]
    verdict = "frontier80_structural_nonzero_compact_control_integrated_replay_ready"
    next_probe = "derive bridge anchors for no-bridge structural nonzero runs"
    if issue_count:
        verdict = "frontier80_structural_nonzero_compact_control_integrated_replay_issues"
        next_probe = "review compact-control integration issues"
    elif promoted_unresolved:
        verdict = "frontier80_structural_nonzero_compact_control_integrated_replay_partial"
        next_probe = "split promoted compact-control integration residuals"
    return {
        "scope": "total",
        "selected_target_runs": str(len(target_rows)),
        "selected_target_bytes": str(target_bytes),
        "token_rows": str(sum(int_field(row, "token_rows") for row in target_rows)),
        "token_bytes": str(target_bytes),
        "generated_bytes": str(sum(int_field(row, "generated_bytes") for row in target_rows)),
        "literal_bytes": str(sum(int_field(row, "literal_bytes") for row in target_rows)),
        "ordered_bridge_rows": str(sum(int_field(row, "ordered_bridge_rows") for row in target_rows)),
        "ordered_bridge_bytes": str(sum(int_field(row, "ordered_bridge_bytes") for row in target_rows)),
        "control_gap_rows": str(len(gap_rows)),
        "control_gap_target_bytes": str(sum(int_field(row, "target_gap_bytes") for row in gap_rows)),
        "promoted_grammar_token_rows": str(sum(int_field(row, "promoted_token_rows") for row in gap_rows)),
        "promoted_grammar_bytes": str(sum(int_field(row, "promoted_covered_bytes") for row in gap_rows)),
        "promoted_grammar_unresolved_bytes": str(promoted_unresolved),
        "integrated_target_bytes": str(integrated),
        "integrated_target_ratio": ratio(integrated, target_bytes),
        "unintegrated_target_bytes": str(max(0, target_bytes - integrated)),
        "bridge_envelope_rows": str(sum(1 for row in target_rows if int_field(row, "bridge_envelope_bytes") > 0)),
        "bridge_envelope_bytes": str(envelope),
        "bridge_envelope_ratio": ratio(envelope, target_bytes),
        "full_envelope_rows": str(sum(1 for row in target_rows if row.get("verdict") == "promoted_compact_control_envelope_integrated")),
        "partial_envelope_rows": str(len(partial)),
        "no_bridge_target_runs": str(len(no_bridge)),
        "no_bridge_target_bytes": str(sum(int_field(row, "length") for row in no_bridge)),
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
    gap_rows: list[dict[str, str]],
) -> str:
    payload = {"summary": summary, "targets": target_rows, "gaps": gap_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    cards = [
        ("Target bytes", summary.get("selected_target_bytes", "0")),
        ("Integrated bytes", summary.get("integrated_target_bytes", "0")),
        ("Envelope bytes", summary.get("bridge_envelope_bytes", "0")),
        ("Promoted gaps", summary.get("promoted_grammar_bytes", "0")),
        ("No-bridge bytes", summary.get("no_bridge_target_bytes", "0")),
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
  <div class="muted">Measures structural nonzero replay coverage after compact-control promoted grammar integration.</div>
  <div class="grid">{card_html}</div>
  <section><h2>Outputs</h2>
    <p><a href="{relative_href(output / 'summary.csv', output / 'index.html')}">summary.csv</a> ·
    <a href="{relative_href(output / 'targets.csv', output / 'index.html')}">targets.csv</a> ·
    <a href="{relative_href(output / 'gaps.csv', output / 'index.html')}">gaps.csv</a></p>
  </section>
  <section><h2>Targets</h2>{render_table(target_rows, TARGET_FIELDNAMES)}</section>
  <section><h2>Gaps</h2>{render_table(gap_rows, GAP_FIELDNAMES)}</section>
</main>
<script type="application/json" id="compact-control-integrated-replay-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> dict[str, str]:
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    promoted_by_gap = group_rows(read_csv(args.promoted_grammar_tokens), "target_id", "gap_index")
    targets = select_targets(read_csv(args.runs), min_length=args.min_run_length, limit=args.target_limit)
    payloads = load_target_payloads(targets, read_csv(args.manifest), read_csv(args.clean_fixtures), issues)
    target_rows: list[dict[str, str]] = []
    gap_rows: list[dict[str, str]] = []

    for payload in payloads:
        target = payload.get("target", {})
        if not isinstance(target, dict):
            continue
        token_rows = build_token_rows(
            payload,
            min_repeat=args.min_repeat,
            min_delta=args.min_delta,
            max_delta=args.max_delta,
        )
        ordered_rows = ordered_strong_bridge(payload, token_rows)
        control_gap_rows = build_control_gap_rows(payload, ordered_rows)
        payload_gap_rows: list[dict[str, str]] = []
        for gap in control_gap_rows:
            promoted_rows = promoted_by_gap.get((gap.get("target_id", ""), gap.get("gap_index", "")), [])
            target_gap_bytes = int_field(gap, "run_gap_bytes")
            promoted_token_bytes = sum(int_field(row, "length") for row in promoted_rows)
            promoted_covered = sum(int_field(row, "covered_bytes") for row in promoted_rows)
            promoted_unresolved = max(0, target_gap_bytes - promoted_covered)
            verdict = "promoted_gap_covered" if promoted_unresolved == 0 else "promoted_gap_partial"
            row = {
                "target_id": gap.get("target_id", ""),
                "rank": target.get("rank", ""),
                "pcx_name": target.get("pcx_name", ""),
                "frontier_id": target.get("frontier_id", ""),
                "span_index": target.get("span_index", ""),
                "gap_index": gap.get("gap_index", ""),
                "previous_token_index": gap.get("previous_token_index", ""),
                "next_token_index": gap.get("next_token_index", ""),
                "previous_run_offset_end": gap.get("previous_run_offset_end", ""),
                "next_run_offset_start": gap.get("next_run_offset_start", ""),
                "target_gap_bytes": str(target_gap_bytes),
                "previous_segment_end": gap.get("previous_segment_end", ""),
                "next_segment_offset": gap.get("next_segment_offset", ""),
                "segment_gap_bytes": gap.get("segment_gap_bytes", ""),
                "promoted_token_rows": str(len(promoted_rows)),
                "promoted_token_bytes": str(promoted_token_bytes),
                "promoted_covered_bytes": str(promoted_covered),
                "promoted_unresolved_bytes": str(promoted_unresolved),
                "verdict": verdict,
            }
            payload_gap_rows.append(row)
        target_rows.append(target_summary(payload, token_rows, ordered_rows, payload_gap_rows))
        gap_rows.extend(payload_gap_rows)

    summary = total_summary(target_rows, gap_rows, len(issues))
    write_csv(output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output / "targets.csv", TARGET_FIELDNAMES, target_rows)
    write_csv(output / "gaps.csv", GAP_FIELDNAMES, gap_rows)
    (output / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""))
    (output / "index.html").write_text(build_html(output, args.title, summary, target_rows, gap_rows))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Integrate promoted compact-control grammar with structural nonzero bridge coverage."
    )
    parser.add_argument("--runs", type=Path, default=DEFAULT_RUNS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--clean-fixtures", type=Path, default=DEFAULT_CLEAN_FIXTURES)
    parser.add_argument("--promoted-grammar-tokens", type=Path, default=DEFAULT_PROMOTED_GRAMMAR_TOKENS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--target-limit", type=int, default=0)
    parser.add_argument("--min-run-length", type=int, default=1)
    parser.add_argument("--min-repeat", type=int, default=2)
    parser.add_argument("--min-delta", type=int, default=4)
    parser.add_argument("--max-delta", type=int, default=2)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Structural Compact-Control Integrated Replay Probe",
    )
    args = parser.parse_args()
    summary = write_report(args)
    print(f"Selected target bytes: {summary['selected_target_bytes']}")
    print(f"Integrated target bytes: {summary['integrated_target_bytes']}")
    print(f"Promoted grammar bytes: {summary['promoted_grammar_bytes']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
