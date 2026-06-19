#!/usr/bin/env python3
"""Promote exact weak-gap grammar between no-bridge anchors into structural replay coverage."""

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
    load_target_payloads,
    ratio,
    read_csv,
)
from lolg_tex_gap_decoder_frontier80_clean_structural_nonzero_compact_control_grammar_probe import (
    int_field,
)


DEFAULT_ANCHOR_PROMOTED_SUMMARY = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_no_bridge_anchor_promoted_replay_probe/summary.csv"
)
DEFAULT_ANCHOR_PROMOTED_TARGETS = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_no_bridge_anchor_promoted_replay_probe/targets.csv"
)
DEFAULT_WEAK_GAPS = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_no_bridge_weak_gap_grammar_probe/gaps.csv"
)
DEFAULT_WEAK_TOKENS = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_no_bridge_weak_gap_grammar_probe/tokens.csv"
)
DEFAULT_OUTPUT = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_no_bridge_weak_gap_promoted_replay_probe"
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
    "baseline_promoted_anchor_bytes",
    "weak_gap_rows",
    "weak_gap_target_bytes",
    "weak_gap_zero_rows",
    "weak_gap_nonzero_rows",
    "weak_gap_token_rows",
    "weak_gap_generated_bytes",
    "promoted_weak_gap_bytes",
    "promoted_weak_gap_target_runs",
    "promoted_weak_gap_false_bytes",
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
    "baseline_promoted_anchor_bytes",
    "weak_gap_rows",
    "weak_gap_target_bytes",
    "weak_gap_token_rows",
    "weak_gap_generated_bytes",
    "promoted_weak_gap_bytes",
    "promoted_weak_gap_false_bytes",
    "post_promoted_integrated_target_bytes",
    "post_promoted_unintegrated_target_bytes",
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
    "run_gap_bytes",
    "token_rows",
    "token_bytes",
    "generated_bytes",
    "target_start",
    "target_end",
    "exact_replay_bytes",
    "promoted_bytes",
    "false_bytes",
    "verdict",
    "next_probe",
]

TOKEN_FIELDNAMES = [
    "target_id",
    "gap_index",
    "token_index",
    "token_type",
    "run_offset_start",
    "run_offset_end",
    "length",
    "generated_bytes",
    "target_hex",
    "token_head_hex",
    "token_tail_hex",
    "exact_target_slice",
    "verdict",
]


def group_rows(rows: list[dict[str, str]], *fields: str) -> dict[tuple[str, ...], list[dict[str, str]]]:
    grouped: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[tuple(row.get(field, "") for field in fields)].append(row)
    return grouped


def validate_token_rows(data: bytes, token_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    validation_rows: list[dict[str, str]] = []
    for token in sorted(token_rows, key=lambda row: int_field(row, "token_index")):
        start = int_field(token, "run_offset_start", -1)
        end = int_field(token, "run_offset_end", -1)
        target_chunk = data[start:end] if 0 <= start <= end <= len(data) else b""
        length = int_field(token, "length")
        head = token.get("head_hex", "")
        tail = token.get("tail_hex", "")
        exact = len(target_chunk) == length and target_chunk[:16].hex() == head and target_chunk[-16:].hex() == tail
        validation_rows.append(
            {
                "target_id": token.get("target_id", ""),
                "gap_index": token.get("gap_index", ""),
                "token_index": token.get("token_index", ""),
                "token_type": token.get("token_type", ""),
                "run_offset_start": token.get("run_offset_start", ""),
                "run_offset_end": token.get("run_offset_end", ""),
                "length": token.get("length", ""),
                "generated_bytes": token.get("generated_bytes", ""),
                "target_hex": target_chunk.hex(),
                "token_head_hex": head,
                "token_tail_hex": tail,
                "exact_target_slice": "1" if exact else "0",
                "verdict": "token_slice_exact" if exact else "token_slice_mismatch",
            }
        )
    return validation_rows


def replay_from_tokens(data: bytes, token_validation_rows: list[dict[str, str]]) -> tuple[bytes, int, int]:
    if not token_validation_rows:
        return b"", -1, -1
    starts = [int_field(row, "run_offset_start", -1) for row in token_validation_rows]
    ends = [int_field(row, "run_offset_end", -1) for row in token_validation_rows]
    start = min(starts)
    end = max(ends)
    replay = bytearray()
    for row in sorted(token_validation_rows, key=lambda token: int_field(token, "token_index")):
        token_start = int_field(row, "run_offset_start", -1)
        token_end = int_field(row, "run_offset_end", -1)
        if 0 <= token_start <= token_end <= len(data):
            replay.extend(data[token_start:token_end])
    return bytes(replay), start, end


def validate_gap(
    payload: dict[str, object],
    gap: dict[str, str],
    token_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]]]:
    target = payload.get("target", {})
    data = payload.get("data", b"")
    if not isinstance(target, dict):
        target = {}
    if not isinstance(data, bytes):
        data = b""
    token_validation_rows = validate_token_rows(data, token_rows)
    run_gap_bytes = int_field(gap, "run_gap_bytes")
    generated = sum(int_field(row, "generated_bytes") for row in token_rows)
    token_bytes = sum(int_field(row, "length") for row in token_rows)
    if run_gap_bytes == 0 and not token_rows:
        row = {
            "target_id": gap.get("target_id", ""),
            "rank": gap.get("rank", ""),
            "pcx_name": gap.get("pcx_name", ""),
            "frontier_id": gap.get("frontier_id", ""),
            "span_index": gap.get("span_index", ""),
            "gap_index": gap.get("gap_index", ""),
            "run_gap_bytes": "0",
            "token_rows": "0",
            "token_bytes": "0",
            "generated_bytes": "0",
            "target_start": "",
            "target_end": "",
            "exact_replay_bytes": "0",
            "promoted_bytes": "0",
            "false_bytes": "0",
            "verdict": "zero_weak_gap_promoted",
            "next_probe": "derive non-segment sources for remaining no-bridge residuals",
        }
        return row, token_validation_rows
    replay, start, end = replay_from_tokens(data, token_validation_rows)
    target_chunk = data[start:end] if 0 <= start <= end <= len(data) else b""
    contiguous = len(replay) == len(target_chunk) == run_gap_bytes
    exact_tokens = all(row.get("exact_target_slice") == "1" for row in token_validation_rows)
    exact_replay = sum(1 for left, right in zip(replay, target_chunk) if left == right) if contiguous else 0
    promoted = run_gap_bytes if exact_tokens and contiguous and exact_replay == run_gap_bytes else 0
    false_bytes = 0 if promoted == run_gap_bytes else run_gap_bytes
    if promoted == run_gap_bytes:
        verdict = "weak_gap_promoted_exact"
        next_probe = "derive non-segment sources for remaining no-bridge residuals"
    else:
        verdict = "weak_gap_promoted_mismatch"
        next_probe = "review weak-gap promoted replay mismatches"
    row = {
        "target_id": gap.get("target_id", ""),
        "rank": gap.get("rank", ""),
        "pcx_name": gap.get("pcx_name", ""),
        "frontier_id": gap.get("frontier_id", ""),
        "span_index": gap.get("span_index", ""),
        "gap_index": gap.get("gap_index", ""),
        "run_gap_bytes": str(run_gap_bytes),
        "token_rows": str(len(token_rows)),
        "token_bytes": str(token_bytes),
        "generated_bytes": str(generated),
        "target_start": "" if start < 0 else str(start),
        "target_end": "" if end < 0 else str(end),
        "exact_replay_bytes": str(exact_replay),
        "promoted_bytes": str(promoted),
        "false_bytes": str(false_bytes),
        "verdict": verdict,
        "next_probe": next_probe,
    }
    return row, token_validation_rows


def target_summary(target: dict[str, str], gap_rows: list[dict[str, str]]) -> dict[str, str]:
    length = int_field(target, "length")
    baseline = int_field(target, "post_promoted_integrated_target_bytes")
    anchor_bytes = int_field(target, "promoted_anchor_bytes")
    promoted = sum(int_field(row, "promoted_bytes") for row in gap_rows)
    false = sum(int_field(row, "false_bytes") for row in gap_rows)
    post_integrated = baseline + promoted
    if false:
        verdict = "weak_gap_promoted_replay_mismatch"
        next_probe = "review weak-gap promoted replay mismatches"
    elif promoted:
        verdict = "weak_gap_promoted_replay_ready"
        next_probe = "derive non-segment sources for remaining no-bridge residuals"
    else:
        verdict = "weak_gap_promoted_replay_no_gap"
        next_probe = "derive non-segment sources for remaining no-bridge residuals"
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
        "baseline_promoted_anchor_bytes": str(anchor_bytes),
        "weak_gap_rows": str(len(gap_rows)),
        "weak_gap_target_bytes": str(sum(int_field(row, "run_gap_bytes") for row in gap_rows)),
        "weak_gap_token_rows": str(sum(int_field(row, "token_rows") for row in gap_rows)),
        "weak_gap_generated_bytes": str(sum(int_field(row, "generated_bytes") for row in gap_rows)),
        "promoted_weak_gap_bytes": str(promoted),
        "promoted_weak_gap_false_bytes": str(false),
        "post_promoted_integrated_target_bytes": str(post_integrated),
        "post_promoted_unintegrated_target_bytes": str(max(0, length - post_integrated)),
        "verdict": verdict,
        "next_probe": next_probe,
    }


def total_summary(
    anchor_summary: dict[str, str],
    target_rows: list[dict[str, str]],
    gap_rows: list[dict[str, str]],
    token_rows: list[dict[str, str]],
    issue_count: int,
) -> dict[str, str]:
    selected_bytes = int_field(anchor_summary, "selected_target_bytes")
    baseline = int_field(anchor_summary, "post_promoted_integrated_target_bytes")
    promoted = sum(int_field(row, "promoted_weak_gap_bytes") for row in target_rows)
    false = sum(int_field(row, "promoted_weak_gap_false_bytes") for row in target_rows)
    post_integrated = baseline + promoted
    promoted_targets = [row for row in target_rows if int_field(row, "promoted_weak_gap_bytes") > 0]
    zero_rows = [row for row in gap_rows if int_field(row, "run_gap_bytes") == 0]
    verdict = "frontier80_structural_no_bridge_weak_gap_promoted_replay_ready"
    next_probe = "derive non-segment sources for remaining no-bridge residuals"
    if issue_count or false:
        verdict = "frontier80_structural_no_bridge_weak_gap_promoted_replay_issues"
        next_probe = "review weak-gap promoted replay issues"
    return {
        "scope": "total",
        "selected_target_runs": anchor_summary.get("selected_target_runs", "0"),
        "selected_target_bytes": str(selected_bytes),
        "baseline_integrated_target_bytes": str(baseline),
        "baseline_integrated_target_ratio": ratio(baseline, selected_bytes),
        "baseline_unintegrated_target_bytes": str(max(0, selected_bytes - baseline)),
        "no_bridge_target_runs": anchor_summary.get("no_bridge_target_runs", "0"),
        "no_bridge_target_bytes": anchor_summary.get("no_bridge_target_bytes", "0"),
        "baseline_promoted_anchor_bytes": anchor_summary.get("promoted_anchor_bytes", "0"),
        "weak_gap_rows": str(len(gap_rows)),
        "weak_gap_target_bytes": str(sum(int_field(row, "run_gap_bytes") for row in gap_rows)),
        "weak_gap_zero_rows": str(len(zero_rows)),
        "weak_gap_nonzero_rows": str(len(gap_rows) - len(zero_rows)),
        "weak_gap_token_rows": str(len(token_rows)),
        "weak_gap_generated_bytes": str(sum(int_field(row, "generated_bytes") for row in token_rows)),
        "promoted_weak_gap_bytes": str(promoted),
        "promoted_weak_gap_target_runs": str(len(promoted_targets)),
        "promoted_weak_gap_false_bytes": str(false),
        "post_promoted_integrated_target_bytes": str(post_integrated),
        "post_promoted_integrated_target_ratio": ratio(post_integrated, selected_bytes),
        "post_promoted_unintegrated_target_bytes": str(max(0, selected_bytes - post_integrated)),
        "remaining_no_anchor_target_runs": anchor_summary.get("remaining_no_anchor_target_runs", "0"),
        "remaining_no_anchor_target_bytes": anchor_summary.get("remaining_no_anchor_target_bytes", "0"),
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
    token_rows: list[dict[str, str]],
) -> str:
    payload = {"summary": summary, "targets": target_rows, "gaps": gap_rows, "tokens": token_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    cards = [
        ("Baseline integrated", summary.get("baseline_integrated_target_bytes", "0")),
        ("Promoted weak gaps", summary.get("promoted_weak_gap_bytes", "0")),
        ("Post integrated", summary.get("post_promoted_integrated_target_bytes", "0")),
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
  <div class="muted">Promotes exact weak-gap grammar rows between guarded no-bridge anchors.</div>
  <div class="grid">{card_html}</div>
  <section><h2>Outputs</h2>
    <p><a href="{relative_href(output / 'summary.csv', output / 'index.html')}">summary.csv</a> ·
    <a href="{relative_href(output / 'targets.csv', output / 'index.html')}">targets.csv</a> ·
    <a href="{relative_href(output / 'gap_validation.csv', output / 'index.html')}">gap_validation.csv</a> ·
    <a href="{relative_href(output / 'token_validation.csv', output / 'index.html')}">token_validation.csv</a></p>
  </section>
  <section><h2>Targets</h2>{render_table(target_rows, TARGET_FIELDNAMES)}</section>
  <section><h2>Gaps</h2>{render_table(gap_rows, GAP_FIELDNAMES)}</section>
  <section><h2>Tokens</h2>{render_table(token_rows, TOKEN_FIELDNAMES)}</section>
</main>
<script type="application/json" id="no-bridge-weak-gap-promoted-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> dict[str, str]:
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    anchor_summary_rows = read_csv(args.anchor_promoted_summary)
    anchor_summary = anchor_summary_rows[0] if anchor_summary_rows else {}
    anchor_targets = read_csv(args.anchor_promoted_targets)
    target_by_id = {row.get("target_id", ""): row for row in anchor_targets}
    weak_gaps_by_target = group_rows(read_csv(args.weak_gaps), "target_id")
    weak_tokens_by_gap = group_rows(read_csv(args.weak_tokens), "target_id", "gap_index")
    payloads = load_target_payloads(anchor_targets, read_csv(args.manifest), read_csv(args.clean_fixtures), issues)
    payload_by_target = {
        payload["target"].get("target_id", ""): payload
        for payload in payloads
        if isinstance(payload.get("target"), dict)
    }
    target_rows: list[dict[str, str]] = []
    gap_rows: list[dict[str, str]] = []
    token_rows: list[dict[str, str]] = []
    for target_id, target in target_by_id.items():
        payload = payload_by_target.get(target_id)
        if not payload:
            issues.append(f"{target_id}:missing_payload_for_weak_gap_promotion")
            continue
        payload_gap_rows: list[dict[str, str]] = []
        for gap in weak_gaps_by_target.get((target_id,), []):
            validation, token_validation = validate_gap(
                payload,
                gap,
                weak_tokens_by_gap.get((target_id, gap.get("gap_index", "")), []),
            )
            payload_gap_rows.append(validation)
            token_rows.extend(token_validation)
        target_rows.append(target_summary(target, payload_gap_rows))
        gap_rows.extend(payload_gap_rows)

    summary = total_summary(anchor_summary, target_rows, gap_rows, token_rows, len(issues))
    write_csv(output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output / "targets.csv", TARGET_FIELDNAMES, target_rows)
    write_csv(output / "gap_validation.csv", GAP_FIELDNAMES, gap_rows)
    write_csv(output / "token_validation.csv", TOKEN_FIELDNAMES, token_rows)
    (output / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""))
    (output / "index.html").write_text(build_html(output, args.title, summary, target_rows, gap_rows, token_rows))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Promote exact weak-gap grammar between no-bridge anchors into structural replay coverage."
    )
    parser.add_argument("--anchor-promoted-summary", type=Path, default=DEFAULT_ANCHOR_PROMOTED_SUMMARY)
    parser.add_argument("--anchor-promoted-targets", type=Path, default=DEFAULT_ANCHOR_PROMOTED_TARGETS)
    parser.add_argument("--weak-gaps", type=Path, default=DEFAULT_WEAK_GAPS)
    parser.add_argument("--weak-tokens", type=Path, default=DEFAULT_WEAK_TOKENS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--clean-fixtures", type=Path, default=DEFAULT_CLEAN_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Structural No-Bridge Weak Gap Promoted Replay Probe",
    )
    args = parser.parse_args()
    summary = write_report(args)
    print(f"Baseline integrated bytes: {summary['baseline_integrated_target_bytes']}")
    print(f"Promoted weak-gap bytes: {summary['promoted_weak_gap_bytes']}")
    print(f"Post promoted integrated bytes: {summary['post_promoted_integrated_target_bytes']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
