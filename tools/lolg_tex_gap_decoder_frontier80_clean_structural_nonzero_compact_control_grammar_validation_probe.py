#!/usr/bin/env python3
"""Validate structural compact-control seed grammar on residual nonzero runs."""

from __future__ import annotations

import argparse
import html
import json
from collections import Counter
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
    build_token_rows_for_gap,
    int_field,
)


DEFAULT_OUTPUT = Path(
    "output/tex_gap_decoder_frontier80_clean_structural_nonzero_compact_control_grammar_validation_probe"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "selected_target_runs",
    "selected_target_bytes",
    "token_rows",
    "ordered_bridge_rows",
    "control_gap_rows",
    "full_control_gap_rows",
    "partial_control_gap_rows",
    "control_gap_target_bytes",
    "grammar_token_rows",
    "grammar_token_bytes",
    "covered_token_rows",
    "covered_token_bytes",
    "covered_token_ratio",
    "unresolved_token_rows",
    "unresolved_token_bytes",
    "exact_seed_token_rows",
    "plus1_seed_token_rows",
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
    "ordered_bridge_rows",
    "control_gap_rows",
    "full_control_gap_rows",
    "control_gap_target_bytes",
    "grammar_token_rows",
    "grammar_token_bytes",
    "covered_token_bytes",
    "unresolved_token_bytes",
    "verdict",
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
    "control_gap_bytes",
    "grammar_token_rows",
    "grammar_token_bytes",
    "covered_token_bytes",
    "unresolved_token_bytes",
    "verdict",
]

TOKEN_FIELDNAMES = [
    "target_id",
    "rank",
    "pcx_name",
    "frontier_id",
    "span_index",
    "gap_index",
    "token_index",
    "token_type",
    "run_offset_start",
    "run_offset_end",
    "length",
    "target_hex",
    "seed_hex",
    "source_transform",
    "source_delta",
    "source_value_hex",
    "source_gap_offset",
    "source_segment_offset",
    "source_occurrences",
    "source_context_hex",
    "grammar_rule",
    "covered_bytes",
    "replay_hex",
    "replay_exact_bytes",
    "verdict",
]

UNRESOLVED_FIELDNAMES = [
    "target_id",
    "rank",
    "pcx_name",
    "frontier_id",
    "span_index",
    "gap_index",
    "token_index",
    "token_type",
    "run_offset_start",
    "run_offset_end",
    "length",
    "target_hex",
    "seed_hex",
    "source_context_hex",
]

UNRESOLVED_VALUE_FIELDNAMES = [
    "value_hex",
    "bytes",
    "token_rows",
    "sample_target_id",
    "sample_token_index",
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


def enrich(row: dict[str, str], target: dict[str, str]) -> dict[str, str]:
    return {
        "rank": target.get("rank", ""),
        "pcx_name": target.get("pcx_name", ""),
        "frontier_id": target.get("frontier_id", ""),
        "span_index": target.get("span_index", ""),
        **row,
    }


def target_summary(
    payload: dict[str, object],
    token_rows: list[dict[str, str]],
    ordered_rows: list[dict[str, str]],
    gap_rows: list[dict[str, str]],
    grammar_rows: list[dict[str, str]],
) -> dict[str, str]:
    target = payload.get("target", {})
    data = payload.get("data", b"")
    if not isinstance(target, dict) or not isinstance(data, bytes):
        return {}
    covered = sum(int_field(row, "covered_bytes") for row in grammar_rows)
    grammar_bytes = sum(int_field(row, "length") for row in grammar_rows)
    unresolved = grammar_bytes - covered
    full_gaps = sum(1 for row in gap_rows if row.get("verdict") == "covered")
    verdict = "covered" if grammar_bytes > 0 and unresolved == 0 else "partial" if grammar_bytes else "no_bridge_gap"
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
        "ordered_bridge_rows": str(len(ordered_rows)),
        "control_gap_rows": str(len(gap_rows)),
        "full_control_gap_rows": str(full_gaps),
        "control_gap_target_bytes": str(sum(int_field(row, "target_gap_bytes") for row in gap_rows)),
        "grammar_token_rows": str(len(grammar_rows)),
        "grammar_token_bytes": str(grammar_bytes),
        "covered_token_bytes": str(covered),
        "unresolved_token_bytes": str(unresolved),
        "verdict": verdict,
    }


def gap_summary(
    payload: dict[str, object],
    gap_row: dict[str, str],
    grammar_rows: list[dict[str, str]],
) -> dict[str, str]:
    target = payload.get("target", {})
    if not isinstance(target, dict):
        target = {}
    grammar_bytes = sum(int_field(row, "length") for row in grammar_rows)
    covered = sum(int_field(row, "covered_bytes") for row in grammar_rows)
    verdict = "covered" if grammar_bytes and covered == grammar_bytes else "partial" if grammar_bytes else "empty"
    row = {
        "target_id": gap_row.get("target_id", ""),
        "rank": target.get("rank", ""),
        "pcx_name": target.get("pcx_name", ""),
        "frontier_id": target.get("frontier_id", ""),
        "span_index": target.get("span_index", ""),
        "gap_index": gap_row.get("gap_index", ""),
        "previous_token_index": gap_row.get("previous_token_index", ""),
        "next_token_index": gap_row.get("next_token_index", ""),
        "previous_run_offset_end": gap_row.get("previous_run_offset_end", ""),
        "next_run_offset_start": gap_row.get("next_run_offset_start", ""),
        "target_gap_bytes": str(max(0, int_field(gap_row, "next_run_offset_start") - int_field(gap_row, "previous_run_offset_end"))),
        "previous_segment_end": gap_row.get("previous_segment_end", ""),
        "next_segment_offset": gap_row.get("next_segment_offset", ""),
        "control_gap_bytes": gap_row.get("segment_gap_bytes", ""),
        "grammar_token_rows": str(len(grammar_rows)),
        "grammar_token_bytes": str(grammar_bytes),
        "covered_token_bytes": str(covered),
        "unresolved_token_bytes": str(grammar_bytes - covered),
        "verdict": verdict,
    }
    return row


def unresolved_value_rows(unresolved_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    value_bytes: Counter[int] = Counter()
    value_tokens: Counter[int] = Counter()
    samples: dict[int, tuple[str, str]] = {}
    for row in unresolved_rows:
        values = bytes.fromhex(row.get("target_hex", ""))
        for value in values:
            value_bytes[value] += 1
            samples.setdefault(value, (row.get("target_id", ""), row.get("token_index", "")))
        for value in set(values):
            value_tokens[value] += 1
    rows = []
    for value, count in value_bytes.most_common():
        sample_target, sample_token = samples[value]
        rows.append(
            {
                "value_hex": f"0x{value:02x}",
                "bytes": str(count),
                "token_rows": str(value_tokens[value]),
                "sample_target_id": sample_target,
                "sample_token_index": sample_token,
            }
        )
    return rows


def total_summary(
    target_rows: list[dict[str, str]],
    gap_rows: list[dict[str, str]],
    grammar_rows: list[dict[str, str]],
    issue_count: int,
) -> dict[str, str]:
    grammar_bytes = sum(int_field(row, "length") for row in grammar_rows)
    covered = sum(int_field(row, "covered_bytes") for row in grammar_rows)
    unresolved = grammar_bytes - covered
    verdict = "frontier80_structural_nonzero_compact_control_validation_partial"
    next_probe = "split structural compact-control seed grammar residuals by value family"
    if grammar_bytes > 0 and unresolved == 0:
        verdict = "frontier80_structural_nonzero_compact_control_validation_ready"
        next_probe = "promote compact-control seed grammar behind structural bridge guard"
    return {
        "scope": "total",
        "selected_target_runs": str(len(target_rows)),
        "selected_target_bytes": str(sum(int_field(row, "length") for row in target_rows)),
        "token_rows": str(sum(int_field(row, "token_rows") for row in target_rows)),
        "ordered_bridge_rows": str(sum(int_field(row, "ordered_bridge_rows") for row in target_rows)),
        "control_gap_rows": str(len(gap_rows)),
        "full_control_gap_rows": str(sum(1 for row in gap_rows if row.get("verdict") == "covered")),
        "partial_control_gap_rows": str(sum(1 for row in gap_rows if row.get("verdict") == "partial")),
        "control_gap_target_bytes": str(sum(int_field(row, "target_gap_bytes") for row in gap_rows)),
        "grammar_token_rows": str(len(grammar_rows)),
        "grammar_token_bytes": str(grammar_bytes),
        "covered_token_rows": str(sum(1 for row in grammar_rows if row.get("verdict") == "covered")),
        "covered_token_bytes": str(covered),
        "covered_token_ratio": ratio(covered, grammar_bytes),
        "unresolved_token_rows": str(sum(1 for row in grammar_rows if row.get("verdict") != "covered")),
        "unresolved_token_bytes": str(unresolved),
        "exact_seed_token_rows": str(sum(1 for row in grammar_rows if row.get("source_transform") == "exact_seed")),
        "plus1_seed_token_rows": str(sum(1 for row in grammar_rows if row.get("source_transform") == "plus1_seed")),
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
    grammar_rows: list[dict[str, str]],
    unresolved_rows: list[dict[str, str]],
    value_rows: list[dict[str, str]],
) -> str:
    payload = {
        "summary": summary,
        "targets": target_rows,
        "gaps": gap_rows,
        "tokens": grammar_rows,
        "unresolved": unresolved_rows,
        "values": value_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    cards = [
        ("Targets", summary.get("selected_target_runs", "0")),
        ("Gap bytes", summary.get("grammar_token_bytes", "0")),
        ("Covered bytes", summary.get("covered_token_bytes", "0")),
        ("Unresolved bytes", summary.get("unresolved_token_bytes", "0")),
        ("Full gaps", summary.get("full_control_gap_rows", "0")),
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
  <div class="muted">Validates exact/+1 compact-control seed rules against the largest residual nonzero runs.</div>
  <div class="grid">{card_html}</div>
  <section><h2>Outputs</h2>
    <p><a href="{relative_href(output / 'summary.csv', output / 'index.html')}">summary.csv</a> ·
    <a href="{relative_href(output / 'targets.csv', output / 'index.html')}">targets.csv</a> ·
    <a href="{relative_href(output / 'gaps.csv', output / 'index.html')}">gaps.csv</a> ·
    <a href="{relative_href(output / 'token_validation.csv', output / 'index.html')}">token_validation.csv</a> ·
    <a href="{relative_href(output / 'unresolved_tokens.csv', output / 'index.html')}">unresolved_tokens.csv</a></p>
  </section>
  <section><h2>Unresolved Values</h2>{render_table(value_rows, UNRESOLVED_VALUE_FIELDNAMES)}</section>
  <section><h2>Targets</h2>{render_table(target_rows, TARGET_FIELDNAMES)}</section>
  <section><h2>Gaps</h2>{render_table(gap_rows, GAP_FIELDNAMES)}</section>
  <section><h2>Unresolved Tokens</h2>{render_table(unresolved_rows, UNRESOLVED_FIELDNAMES)}</section>
  <section><h2>Token Validation</h2>{render_table(grammar_rows, TOKEN_FIELDNAMES)}</section>
</main>
<script type="application/json" id="compact-control-validation-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> dict[str, str]:
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    targets = select_targets(read_csv(args.runs), min_length=args.min_run_length, limit=args.target_limit)
    payloads = load_target_payloads(targets, read_csv(args.manifest), read_csv(args.clean_fixtures), issues)
    target_rows: list[dict[str, str]] = []
    gap_rows: list[dict[str, str]] = []
    grammar_rows: list[dict[str, str]] = []
    unresolved_rows: list[dict[str, str]] = []

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
        payload_grammar_rows: list[dict[str, str]] = []
        payload_gap_rows: list[dict[str, str]] = []
        for control_gap in control_gap_rows:
            gap_token_rows = [
                enrich(row, target)
                for row in build_token_rows_for_gap(payload, control_gap, token_rows)
            ]
            gap_summary_row = gap_summary(payload, control_gap, gap_token_rows)
            payload_gap_rows.append(gap_summary_row)
            payload_grammar_rows.extend(gap_token_rows)
        target_rows.append(target_summary(payload, token_rows, ordered_rows, payload_gap_rows, payload_grammar_rows))
        gap_rows.extend(payload_gap_rows)
        grammar_rows.extend(payload_grammar_rows)
        unresolved_rows.extend(
            {field: row.get(field, "") for field in UNRESOLVED_FIELDNAMES}
            for row in payload_grammar_rows
            if row.get("verdict") != "covered"
        )

    value_rows = unresolved_value_rows(unresolved_rows)
    summary = total_summary(target_rows, gap_rows, grammar_rows, len(issues))
    write_csv(output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output / "targets.csv", TARGET_FIELDNAMES, target_rows)
    write_csv(output / "gaps.csv", GAP_FIELDNAMES, gap_rows)
    write_csv(output / "token_validation.csv", TOKEN_FIELDNAMES, grammar_rows)
    write_csv(output / "unresolved_tokens.csv", UNRESOLVED_FIELDNAMES, unresolved_rows)
    write_csv(output / "unresolved_values.csv", UNRESOLVED_VALUE_FIELDNAMES, value_rows)
    (output / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""))
    (output / "index.html").write_text(
        build_html(output, args.title, summary, target_rows, gap_rows, grammar_rows, unresolved_rows, value_rows)
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate structural compact-control seed grammar on residual nonzero runs."
    )
    parser.add_argument("--runs", type=Path, default=DEFAULT_RUNS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--clean-fixtures", type=Path, default=DEFAULT_CLEAN_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--target-limit", type=int, default=64)
    parser.add_argument("--min-run-length", type=int, default=16)
    parser.add_argument("--min-repeat", type=int, default=2)
    parser.add_argument("--min-delta", type=int, default=4)
    parser.add_argument("--max-delta", type=int, default=2)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Structural Compact-Control Grammar Validation",
    )
    args = parser.parse_args()
    summary = write_report(args)
    print(f"Selected targets: {summary['selected_target_runs']}")
    print(f"Grammar bytes: {summary['grammar_token_bytes']}")
    print(f"Covered bytes: {summary['covered_token_bytes']}")
    print(f"Unresolved bytes: {summary['unresolved_token_bytes']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
