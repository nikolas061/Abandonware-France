#!/usr/bin/env python3
"""Promote bridge residual source grammar into structural replay coverage."""

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


DEFAULT_INTEGRATED_TARGETS = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_compact_control_integrated_replay_probe/targets.csv"
)
DEFAULT_BRIDGE_RESIDUAL_INTERVAL_MAP_SUMMARY = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_no_bridge_bridge_residual_interval_map_probe/summary.csv"
)
DEFAULT_BRIDGE_RESIDUAL_SOURCE_GRAMMAR_SUMMARY = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_no_bridge_bridge_residual_source_grammar_probe/summary.csv"
)
DEFAULT_BRIDGE_RESIDUALS = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_no_bridge_bridge_residual_source_grammar_probe/residuals.csv"
)
DEFAULT_BRIDGE_RESIDUAL_TOKENS = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_no_bridge_bridge_residual_source_grammar_probe/tokens.csv"
)
DEFAULT_OUTPUT = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_no_bridge_bridge_residual_source_promoted_replay_probe"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "selected_target_runs",
    "selected_target_bytes",
    "baseline_integrated_target_bytes",
    "baseline_integrated_target_ratio",
    "baseline_unintegrated_target_bytes",
    "bridge_residual_intervals",
    "bridge_residual_bytes",
    "bridge_residual_token_rows",
    "bridge_residual_generated_bytes",
    "promoted_bridge_residual_bytes",
    "promoted_bridge_residual_target_runs",
    "promoted_bridge_residual_false_bytes",
    "post_promoted_integrated_target_bytes",
    "post_promoted_integrated_target_ratio",
    "post_promoted_unintegrated_target_bytes",
    "full_coverage_target_runs",
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
    "baseline_unintegrated_target_bytes",
    "bridge_residual_intervals",
    "bridge_residual_bytes",
    "bridge_residual_token_rows",
    "bridge_residual_generated_bytes",
    "promoted_bridge_residual_bytes",
    "promoted_bridge_residual_false_bytes",
    "post_promoted_integrated_target_bytes",
    "post_promoted_unintegrated_target_bytes",
    "verdict",
    "next_probe",
]

RESIDUAL_FIELDNAMES = [
    "target_id",
    "rank",
    "pcx_name",
    "frontier_id",
    "span_index",
    "residual_index",
    "position_class",
    "run_offset_start",
    "run_offset_end",
    "length",
    "token_rows",
    "token_bytes",
    "generated_bytes",
    "exact_replay_bytes",
    "promoted_bytes",
    "false_bytes",
    "verdict",
    "next_probe",
]

TOKEN_FIELDNAMES = [
    "target_id",
    "residual_index",
    "token_index",
    "token_type",
    "source_role",
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
        exact = (
            len(target_chunk) == length
            and target_chunk[:16].hex() == head
            and (target_chunk[-16:].hex() if target_chunk else "") == tail
        )
        validation_rows.append(
            {
                "target_id": token.get("target_id", ""),
                "residual_index": token.get("residual_index", ""),
                "token_index": token.get("token_index", ""),
                "token_type": token.get("token_type", ""),
                "source_role": token.get("source_role", ""),
                "run_offset_start": token.get("run_offset_start", ""),
                "run_offset_end": token.get("run_offset_end", ""),
                "length": token.get("length", ""),
                "generated_bytes": token.get("generated_bytes", ""),
                "target_hex": target_chunk.hex(),
                "token_head_hex": head,
                "token_tail_hex": tail,
                "exact_target_slice": "1" if exact else "0",
                "verdict": "bridge_residual_source_token_slice_exact"
                if exact
                else "bridge_residual_source_token_slice_mismatch",
            }
        )
    return validation_rows


def replay_from_tokens(data: bytes, token_validation_rows: list[dict[str, str]]) -> tuple[bytes, int, int, bool]:
    if not token_validation_rows:
        return b"", -1, -1, False
    starts = [int_field(row, "run_offset_start", -1) for row in token_validation_rows]
    ends = [int_field(row, "run_offset_end", -1) for row in token_validation_rows]
    start = min(starts)
    end = max(ends)
    replay = bytearray()
    contiguous = True
    previous_end = -1
    for row in sorted(token_validation_rows, key=lambda token: int_field(token, "token_index")):
        token_start = int_field(row, "run_offset_start", -1)
        token_end = int_field(row, "run_offset_end", -1)
        if previous_end >= 0 and token_start != previous_end:
            contiguous = False
        previous_end = token_end
        if 0 <= token_start <= token_end <= len(data):
            replay.extend(data[token_start:token_end])
        else:
            contiguous = False
    return bytes(replay), start, end, contiguous


def validate_residual(
    payload: dict[str, object],
    residual: dict[str, str],
    token_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]]]:
    data = payload.get("data", b"")
    if not isinstance(data, bytes):
        data = b""
    token_validation_rows = validate_token_rows(data, token_rows)
    length = int_field(residual, "length")
    start = int_field(residual, "run_offset_start", -1)
    end = int_field(residual, "run_offset_end", -1)
    target_chunk = data[start:end] if 0 <= start <= end <= len(data) else b""
    replay, replay_start, replay_end, contiguous = replay_from_tokens(data, token_validation_rows)
    token_bytes = sum(int_field(row, "length") for row in token_validation_rows)
    generated = sum(int_field(row, "generated_bytes") for row in token_validation_rows)
    exact_tokens = all(row.get("exact_target_slice") == "1" for row in token_validation_rows)
    aligned = replay_start == start and replay_end == end
    exact_replay = sum(1 for left, right in zip(replay, target_chunk) if left == right) if aligned else 0
    promoted = length if exact_tokens and contiguous and aligned and exact_replay == length else 0
    false_bytes = 0 if promoted == length else length
    if promoted == length:
        verdict = "bridge_residual_source_promoted_exact"
        next_probe = "validate final structural nonzero replay coverage after bridge residual promotion"
    else:
        verdict = "bridge_residual_source_promoted_mismatch"
        next_probe = "review bridge residual source promoted replay mismatches"
    return (
        {
            "target_id": residual.get("target_id", ""),
            "rank": residual.get("rank", ""),
            "pcx_name": residual.get("pcx_name", ""),
            "frontier_id": residual.get("frontier_id", ""),
            "span_index": residual.get("span_index", ""),
            "residual_index": residual.get("residual_index", ""),
            "position_class": residual.get("position_class", ""),
            "run_offset_start": residual.get("run_offset_start", ""),
            "run_offset_end": residual.get("run_offset_end", ""),
            "length": str(length),
            "token_rows": str(len(token_validation_rows)),
            "token_bytes": str(token_bytes),
            "generated_bytes": str(generated),
            "exact_replay_bytes": str(exact_replay),
            "promoted_bytes": str(promoted),
            "false_bytes": str(false_bytes),
            "verdict": verdict,
            "next_probe": next_probe,
        },
        token_validation_rows,
    )


def target_summary(target: dict[str, str], residual_rows: list[dict[str, str]]) -> dict[str, str]:
    length = int_field(target, "length")
    residual_bytes = sum(int_field(row, "length") for row in residual_rows)
    baseline = max(0, length - residual_bytes)
    promoted = sum(int_field(row, "promoted_bytes") for row in residual_rows)
    false = sum(int_field(row, "false_bytes") for row in residual_rows)
    post_integrated = baseline + promoted
    if false:
        verdict = "bridge_residual_source_promoted_replay_mismatch"
        next_probe = "review bridge residual source promoted replay mismatches"
    elif post_integrated == length:
        verdict = "bridge_residual_source_promoted_replay_full"
        next_probe = "validate final structural nonzero replay coverage after bridge residual promotion"
    else:
        verdict = "bridge_residual_source_promoted_replay_partial"
        next_probe = "profile remaining bytes after bridge residual source promotion"
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
        "baseline_unintegrated_target_bytes": str(residual_bytes),
        "bridge_residual_intervals": str(len(residual_rows)),
        "bridge_residual_bytes": str(residual_bytes),
        "bridge_residual_token_rows": str(sum(int_field(row, "token_rows") for row in residual_rows)),
        "bridge_residual_generated_bytes": str(sum(int_field(row, "generated_bytes") for row in residual_rows)),
        "promoted_bridge_residual_bytes": str(promoted),
        "promoted_bridge_residual_false_bytes": str(false),
        "post_promoted_integrated_target_bytes": str(post_integrated),
        "post_promoted_unintegrated_target_bytes": str(max(0, length - post_integrated)),
        "verdict": verdict,
        "next_probe": next_probe,
    }


def total_summary(
    interval_map_summary: dict[str, str],
    grammar_summary: dict[str, str],
    target_rows: list[dict[str, str]],
    residual_rows: list[dict[str, str]],
    token_rows: list[dict[str, str]],
    issue_count: int,
) -> dict[str, str]:
    selected_bytes = int_field(interval_map_summary, "selected_target_bytes")
    baseline = int_field(interval_map_summary, "coverage_bytes")
    promoted = sum(int_field(row, "promoted_bridge_residual_bytes") for row in target_rows)
    false = sum(int_field(row, "promoted_bridge_residual_false_bytes") for row in target_rows)
    post_integrated = baseline + promoted
    promoted_targets = [row for row in target_rows if int_field(row, "promoted_bridge_residual_bytes") > 0]
    full_targets = [row for row in target_rows if int_field(row, "post_promoted_unintegrated_target_bytes") == 0]
    expected_residual = int_field(grammar_summary, "residual_bytes")
    verdict = "frontier80_structural_no_bridge_bridge_residual_source_promoted_replay_ready"
    next_probe = "validate final structural nonzero replay coverage after bridge residual promotion"
    if issue_count or false or (expected_residual and promoted != expected_residual):
        verdict = "frontier80_structural_no_bridge_bridge_residual_source_promoted_replay_issues"
        next_probe = "review bridge residual source promoted replay issues"
    return {
        "scope": "total",
        "selected_target_runs": interval_map_summary.get("selected_target_runs", "0"),
        "selected_target_bytes": str(selected_bytes),
        "baseline_integrated_target_bytes": str(baseline),
        "baseline_integrated_target_ratio": ratio(baseline, selected_bytes),
        "baseline_unintegrated_target_bytes": str(max(0, selected_bytes - baseline)),
        "bridge_residual_intervals": str(len(residual_rows)),
        "bridge_residual_bytes": str(sum(int_field(row, "length") for row in residual_rows)),
        "bridge_residual_token_rows": str(len(token_rows)),
        "bridge_residual_generated_bytes": str(sum(int_field(row, "generated_bytes") for row in token_rows)),
        "promoted_bridge_residual_bytes": str(promoted),
        "promoted_bridge_residual_target_runs": str(len(promoted_targets)),
        "promoted_bridge_residual_false_bytes": str(false),
        "post_promoted_integrated_target_bytes": str(post_integrated),
        "post_promoted_integrated_target_ratio": ratio(post_integrated, selected_bytes),
        "post_promoted_unintegrated_target_bytes": str(max(0, selected_bytes - post_integrated)),
        "full_coverage_target_runs": str(len(full_targets)),
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
    target_rows: list[dict[str, str]],
    residual_rows: list[dict[str, str]],
    token_rows: list[dict[str, str]],
) -> str:
    payload = {"summary": summary, "targets": target_rows, "residuals": residual_rows, "tokens": token_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    cards = [
        ("Baseline integrated", summary.get("baseline_integrated_target_bytes", "0")),
        ("Promoted bridge residuals", summary.get("promoted_bridge_residual_bytes", "0")),
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
  <div class="muted">Promotes exact bridge residual source grammar into structural replay coverage.</div>
  <div class="grid">{card_html}</div>
  <section><h2>Outputs</h2>
    <p><a href="{relative_href(output / 'summary.csv', output / 'index.html')}">summary.csv</a> ·
    <a href="{relative_href(output / 'targets.csv', output / 'index.html')}">targets.csv</a> ·
    <a href="{relative_href(output / 'residual_validation.csv', output / 'index.html')}">residual_validation.csv</a> ·
    <a href="{relative_href(output / 'token_validation.csv', output / 'index.html')}">token_validation.csv</a></p>
  </section>
  <section><h2>Targets</h2>{render_table(target_rows, TARGET_FIELDNAMES)}</section>
  <section><h2>Residuals</h2>{render_table(residual_rows, RESIDUAL_FIELDNAMES)}</section>
  <section><h2>Tokens</h2>{render_table(token_rows, TOKEN_FIELDNAMES)}</section>
</main>
<script type="application/json" id="bridge-residual-source-promoted-replay-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> dict[str, str]:
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    interval_map_summary_rows = read_csv(args.bridge_residual_interval_map_summary)
    interval_map_summary = interval_map_summary_rows[0] if interval_map_summary_rows else {}
    grammar_summary_rows = read_csv(args.bridge_residual_source_grammar_summary)
    grammar_summary = grammar_summary_rows[0] if grammar_summary_rows else {}
    targets = read_csv(args.integrated_targets)
    residuals_by_target = group_rows(read_csv(args.bridge_residuals), "target_id")
    tokens_by_residual = group_rows(read_csv(args.bridge_residual_tokens), "target_id", "residual_index")
    payloads = load_target_payloads(targets, read_csv(args.manifest), read_csv(args.clean_fixtures), issues)
    payload_by_target = {
        payload["target"].get("target_id", ""): payload
        for payload in payloads
        if isinstance(payload.get("target"), dict)
    }
    target_rows: list[dict[str, str]] = []
    residual_rows: list[dict[str, str]] = []
    token_rows: list[dict[str, str]] = []
    for target in targets:
        target_id = target.get("target_id", "")
        payload = payload_by_target.get(target_id)
        if not payload:
            issues.append(f"{target_id}:missing_payload_for_bridge_residual_source_promotion")
            continue
        target_residual_rows: list[dict[str, str]] = []
        for residual in residuals_by_target.get((target_id,), []):
            validation, token_validation = validate_residual(
                payload,
                residual,
                tokens_by_residual.get((target_id, residual.get("residual_index", "")), []),
            )
            target_residual_rows.append(validation)
            token_rows.extend(token_validation)
        target_rows.append(target_summary(target, target_residual_rows))
        residual_rows.extend(target_residual_rows)

    summary = total_summary(
        interval_map_summary,
        grammar_summary,
        target_rows,
        residual_rows,
        token_rows,
        len(issues),
    )
    write_csv(output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output / "targets.csv", TARGET_FIELDNAMES, target_rows)
    write_csv(output / "residual_validation.csv", RESIDUAL_FIELDNAMES, residual_rows)
    write_csv(output / "token_validation.csv", TOKEN_FIELDNAMES, token_rows)
    (output / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""))
    (output / "index.html").write_text(build_html(output, args.title, summary, target_rows, residual_rows, token_rows))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Promote bridge residual source grammar into structural replay coverage."
    )
    parser.add_argument("--integrated-targets", type=Path, default=DEFAULT_INTEGRATED_TARGETS)
    parser.add_argument(
        "--bridge-residual-interval-map-summary",
        type=Path,
        default=DEFAULT_BRIDGE_RESIDUAL_INTERVAL_MAP_SUMMARY,
    )
    parser.add_argument(
        "--bridge-residual-source-grammar-summary",
        type=Path,
        default=DEFAULT_BRIDGE_RESIDUAL_SOURCE_GRAMMAR_SUMMARY,
    )
    parser.add_argument("--bridge-residuals", type=Path, default=DEFAULT_BRIDGE_RESIDUALS)
    parser.add_argument("--bridge-residual-tokens", type=Path, default=DEFAULT_BRIDGE_RESIDUAL_TOKENS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--clean-fixtures", type=Path, default=DEFAULT_CLEAN_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Structural No-Bridge Bridge Residual Source Promoted Replay",
    )
    args = parser.parse_args()
    summary = write_report(args)
    print(f"Baseline integrated bytes: {summary['baseline_integrated_target_bytes']}")
    print(f"Promoted bridge residual bytes: {summary['promoted_bridge_residual_bytes']}")
    print(f"Post promoted integrated bytes: {summary['post_promoted_integrated_target_bytes']}")
    print(f"Remaining bytes: {summary['post_promoted_unintegrated_target_bytes']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
