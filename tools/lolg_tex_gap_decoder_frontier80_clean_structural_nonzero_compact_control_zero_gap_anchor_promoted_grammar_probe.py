#!/usr/bin/env python3
"""Validate promoted zero-gap anchor replay inside the structural compact-control grammar."""

from __future__ import annotations

import argparse
import html
import json
import re
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
    value_class,
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
    replay_from_seed,
    token_chunk,
)


DEFAULT_GUARD_RULES = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_compact_control_zero_gap_anchor_guard_rule_probe/guard_rules.csv"
)
DEFAULT_OUTPUT = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_compact_control_zero_gap_anchor_promoted_grammar_probe"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "selected_target_runs",
    "selected_target_bytes",
    "token_rows",
    "ordered_bridge_rows",
    "control_gap_rows",
    "baseline_grammar_token_rows",
    "baseline_grammar_token_bytes",
    "baseline_covered_token_bytes",
    "baseline_unresolved_token_bytes",
    "promoted_gap_rows",
    "promoted_token_rows",
    "promoted_bytes",
    "promotion_ready_bytes",
    "promoted_false_bytes",
    "promotion_exact_ratio",
    "final_covered_token_bytes",
    "final_unresolved_token_rows",
    "final_unresolved_token_bytes",
    "final_covered_token_ratio",
    "rule_rows",
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
    "baseline_grammar_token_rows",
    "baseline_grammar_token_bytes",
    "baseline_covered_token_bytes",
    "baseline_unresolved_token_bytes",
    "promoted_token_rows",
    "promoted_bytes",
    "promoted_false_bytes",
    "final_unresolved_token_bytes",
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
    "baseline_token_rows",
    "baseline_token_bytes",
    "baseline_covered_bytes",
    "baseline_unresolved_bytes",
    "promotion_rule_id",
    "promoted_token_rows",
    "promoted_bytes",
    "promoted_false_bytes",
    "final_covered_bytes",
    "final_unresolved_bytes",
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
    "baseline_verdict",
    "promotion_rule_id",
    "promotion_anchor_delta",
    "promotion_status",
]

PROMOTION_FIELDNAMES = [
    "target_id",
    "rank",
    "pcx_name",
    "frontier_id",
    "span_index",
    "gap_index",
    "token_index",
    "token_order",
    "token_type",
    "length",
    "target_hex",
    "rule_id",
    "anchor_delta",
    "source_segment_offset",
    "source_value_hex",
    "source_context_hex",
    "replay_hex",
    "replay_exact_bytes",
    "verdict",
]

ANCHOR_PLAN_RE = re.compile(r"(?P<order>\d+):(?P<kind>[DRL])(?P<length>\d+)@(?P<delta>[+-]?\d+)")


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


def hex_byte(value: int | None) -> str:
    return "" if value is None else f"0x{value:02x}"


def signed_delta(value: int) -> str:
    return f"{value:+d}"


def source_context(segment: bytes, offset: int, length: int) -> str:
    start = max(0, offset - 8)
    end = min(len(segment), offset + max(1, length) + 8)
    return segment[start:end].hex()


def token_letter(token: dict[str, str]) -> str:
    token_type = token.get("token_type", "")
    if token_type == "delta":
        return "D"
    if token_type == "repeat":
        return "R"
    return "L"


def token_signature(tokens: list[dict[str, str]], chunks: list[bytes]) -> str:
    return ".".join(f"{token_letter(token)}{len(chunk)}" for token, chunk in zip(tokens, chunks))


def token_value_family(token: dict[str, str], chunk: bytes, control_gap_bytes: int) -> str:
    classes = {value_class(value) for value in chunk}
    if control_gap_bytes == 0:
        if token.get("token_type") == "delta" or classes <= {"dark_low", "other"}:
            return "zero_control_gap_low_delta"
        return "zero_control_gap_mixed"
    return "local_control_gap"


def group_value_family(tokens: list[dict[str, str]], chunks: list[bytes], control_gap_bytes: int) -> str:
    families = sorted(
        {
            token_value_family(token, chunk, control_gap_bytes)
            for token, chunk in zip(tokens, chunks)
            if chunk
        }
    )
    return "+".join(families)


def parse_anchor_plan(text: str) -> list[dict[str, int | str]]:
    plan: list[dict[str, int | str]] = []
    for match in ANCHOR_PLAN_RE.finditer(text):
        plan.append(
            {
                "order": int(match.group("order")),
                "kind": match.group("kind"),
                "length": int(match.group("length")),
                "delta": int(match.group("delta")),
            }
        )
    return sorted(plan, key=lambda row: int(row["order"]))


def ready_rules(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    rules: list[dict[str, str]] = []
    for row in rows:
        if row.get("verdict") != "guarded_zero_gap_anchor_rule_ready":
            continue
        if int_field(row, "false_guard_rows") != 0:
            continue
        if int_field(row, "replay_exact_bytes") != int_field(row, "token_bytes"):
            continue
        parsed = parse_anchor_plan(row.get("anchor_plan", ""))
        if not parsed:
            continue
        rules.append({**row, "_parsed_anchor_plan": json.dumps(parsed, separators=(",", ":"))})
    return rules


def selected_gap_tokens(tokens: list[dict[str, str]], gap_row: dict[str, str]) -> list[dict[str, str]]:
    run_start = int_field(gap_row, "previous_run_offset_end", -1)
    run_end = int_field(gap_row, "next_run_offset_start", -1)
    return sorted(
        [
            row
            for row in tokens
            if int_field(row, "run_offset_start", -1) >= run_start
            and int_field(row, "run_offset_end", -1) <= run_end
        ],
        key=lambda row: int_field(row, "token_index"),
    )


def enrich(row: dict[str, str], target: dict[str, str]) -> dict[str, str]:
    return {
        "rank": target.get("rank", ""),
        "pcx_name": target.get("pcx_name", ""),
        "frontier_id": target.get("frontier_id", ""),
        "span_index": target.get("span_index", ""),
        **row,
    }


def extend_baseline_row(row: dict[str, str]) -> dict[str, str]:
    return {
        **row,
        "baseline_verdict": row.get("verdict", ""),
        "promotion_rule_id": "",
        "promotion_anchor_delta": "",
        "promotion_status": "baseline_covered" if row.get("verdict") == "covered" else "residual",
    }


def promotion_candidate_rows(
    payload: dict[str, object],
    gap_row: dict[str, str],
    tokens: list[dict[str, str]],
    baseline_rows: list[dict[str, str]],
    rules: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, str]], int, str]:
    segment = payload.get("segment", b"")
    if not isinstance(segment, bytes):
        return [], [], 0, ""
    segment_start = int_field(gap_row, "previous_segment_end", -1)
    segment_end = int_field(gap_row, "next_segment_offset", -1)
    run_start = int_field(gap_row, "previous_run_offset_end", -1)
    run_end = int_field(gap_row, "next_run_offset_start", -1)
    if segment_start < 0 or segment_end < segment_start or run_start < 0 or run_end < run_start:
        return [], [], 0, ""

    control_gap_bytes = segment_end - segment_start
    target_gap_bytes = run_end - run_start
    if control_gap_bytes != 0:
        return [], [], 0, ""

    selected_tokens = selected_gap_tokens(tokens, gap_row)
    chunks = [token_chunk(payload, token) for token in selected_tokens]
    signature = token_signature(selected_tokens, chunks)
    family = group_value_family(selected_tokens, chunks, control_gap_bytes)
    baseline_by_token = {row.get("token_index", ""): row for row in baseline_rows}

    for rule in rules:
        if int_field(rule, "control_gap_bytes") != control_gap_bytes:
            continue
        if int_field(rule, "target_gap_bytes") != target_gap_bytes:
            continue
        if rule.get("token_signature", "") != signature:
            continue
        if rule.get("value_family", "") != family:
            continue
        plan = json.loads(rule.get("_parsed_anchor_plan", "[]"))
        if len(plan) != len(selected_tokens):
            continue

        promoted_rows: list[dict[str, str]] = []
        promotion_rows: list[dict[str, str]] = []
        false_bytes = 0
        for order, (token, chunk, plan_row) in enumerate(zip(selected_tokens, chunks, plan), start=1):
            kind = str(plan_row["kind"])
            length = int(plan_row["length"])
            anchor_delta = int(plan_row["delta"])
            if kind != token_letter(token) or length != len(chunk):
                false_bytes += len(chunk)
                continue
            source_segment_offset = segment_start + anchor_delta
            if source_segment_offset < 0 or source_segment_offset >= len(segment):
                false_bytes += len(chunk)
                continue
            source_value = segment[source_segment_offset]
            replay = replay_from_seed(token, source_value, len(chunk))
            exact = sum(1 for left, right in zip(replay, chunk) if left == right)
            if replay != chunk:
                false_bytes += len(chunk) - exact
                continue
            base = baseline_by_token.get(token.get("token_index", ""), {})
            source_text = source_context(segment, source_segment_offset, len(chunk))
            rule_id = rule.get("rule_id", "")
            promoted_rows.append(
                {
                    **base,
                    "source_transform": "exact_seed",
                    "source_delta": "0",
                    "source_value_hex": hex_byte(source_value),
                    "source_gap_offset": signed_delta(anchor_delta),
                    "source_segment_offset": str(source_segment_offset),
                    "source_occurrences": "1",
                    "source_context_hex": source_text,
                    "grammar_rule": f"zero_gap_anchor_exact_seed_{token.get('token_type', '')}",
                    "covered_bytes": str(len(chunk)),
                    "replay_hex": replay.hex(),
                    "replay_exact_bytes": str(exact),
                    "verdict": "covered",
                    "baseline_verdict": base.get("verdict", ""),
                    "promotion_rule_id": rule_id,
                    "promotion_anchor_delta": signed_delta(anchor_delta),
                    "promotion_status": "promoted",
                }
            )
            promotion_rows.append(
                {
                    "target_id": base.get("target_id", ""),
                    "rank": base.get("rank", ""),
                    "pcx_name": base.get("pcx_name", ""),
                    "frontier_id": base.get("frontier_id", ""),
                    "span_index": base.get("span_index", ""),
                    "gap_index": base.get("gap_index", ""),
                    "token_index": token.get("token_index", ""),
                    "token_order": str(order),
                    "token_type": token.get("token_type", ""),
                    "length": str(len(chunk)),
                    "target_hex": chunk.hex(),
                    "rule_id": rule_id,
                    "anchor_delta": signed_delta(anchor_delta),
                    "source_segment_offset": str(source_segment_offset),
                    "source_value_hex": hex_byte(source_value),
                    "source_context_hex": source_text,
                    "replay_hex": replay.hex(),
                    "replay_exact_bytes": str(exact),
                    "verdict": "promoted_replay_exact",
                }
            )
        if false_bytes == 0 and len(promoted_rows) == len(selected_tokens):
            return promoted_rows, promotion_rows, 0, rule.get("rule_id", "")
        if false_bytes:
            return [], [], false_bytes, rule.get("rule_id", "")
    return [], [], 0, ""


def promoted_gap_rows(
    payload: dict[str, object],
    target: dict[str, str],
    gap_row: dict[str, str],
    token_rows: list[dict[str, str]],
    baseline_rows: list[dict[str, str]],
    rules: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    enriched_baseline = [extend_baseline_row(enrich(row, target)) for row in baseline_rows]
    promoted_rows, promotion_rows, false_bytes, rule_id = promotion_candidate_rows(
        payload,
        gap_row,
        token_rows,
        enriched_baseline,
        rules,
    )
    promoted_by_token = {row.get("token_index", ""): row for row in promoted_rows}
    final_rows = [
        promoted_by_token.get(row.get("token_index", ""), row)
        for row in enriched_baseline
    ]

    baseline_bytes = sum(int_field(row, "length") for row in enriched_baseline)
    baseline_covered = sum(
        int_field(row, "covered_bytes")
        for row in enriched_baseline
        if row.get("baseline_verdict") == "covered"
    )
    promoted_bytes = sum(int_field(row, "covered_bytes") for row in promoted_rows)
    final_covered = sum(int_field(row, "covered_bytes") for row in final_rows)
    final_unresolved = baseline_bytes - final_covered
    target_gap_bytes = max(
        0,
        int_field(gap_row, "next_run_offset_start") - int_field(gap_row, "previous_run_offset_end"),
    )
    verdict = "covered" if final_unresolved == 0 else "partial"
    if promoted_bytes and final_unresolved == 0:
        verdict = "promoted_covered"
    elif promoted_bytes:
        verdict = "promoted_partial"
    if false_bytes:
        verdict = "promotion_false"

    gap_summary = {
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
        "target_gap_bytes": str(target_gap_bytes),
        "previous_segment_end": gap_row.get("previous_segment_end", ""),
        "next_segment_offset": gap_row.get("next_segment_offset", ""),
        "control_gap_bytes": str(
            max(0, int_field(gap_row, "next_segment_offset") - int_field(gap_row, "previous_segment_end"))
        ),
        "baseline_token_rows": str(len(enriched_baseline)),
        "baseline_token_bytes": str(baseline_bytes),
        "baseline_covered_bytes": str(baseline_covered),
        "baseline_unresolved_bytes": str(baseline_bytes - baseline_covered),
        "promotion_rule_id": rule_id,
        "promoted_token_rows": str(len(promoted_rows)),
        "promoted_bytes": str(promoted_bytes),
        "promoted_false_bytes": str(false_bytes),
        "final_covered_bytes": str(final_covered),
        "final_unresolved_bytes": str(final_unresolved),
        "verdict": verdict,
    }
    return gap_summary, final_rows, promotion_rows


def target_summary(
    payload: dict[str, object],
    target: dict[str, str],
    token_rows: list[dict[str, str]],
    ordered_rows: list[dict[str, str]],
    gap_rows: list[dict[str, str]],
    grammar_rows: list[dict[str, str]],
) -> dict[str, str]:
    data = payload.get("data", b"")
    if not isinstance(data, bytes):
        data = b""
    baseline_bytes = sum(int_field(row, "length") for row in grammar_rows)
    baseline_covered = sum(
        int_field(row, "covered_bytes")
        for row in grammar_rows
        if row.get("baseline_verdict") == "covered"
    )
    final_covered = sum(int_field(row, "covered_bytes") for row in grammar_rows)
    promoted_bytes = sum(int_field(row, "covered_bytes") for row in grammar_rows if row.get("promotion_status") == "promoted")
    false_bytes = sum(int_field(row, "promoted_false_bytes") for row in gap_rows)
    final_unresolved = baseline_bytes - final_covered
    verdict = "covered" if baseline_bytes and final_unresolved == 0 else "partial" if baseline_bytes else "no_bridge_gap"
    if promoted_bytes and final_unresolved == 0:
        verdict = "promoted_covered"
    elif promoted_bytes:
        verdict = "promoted_partial"
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
        "baseline_grammar_token_rows": str(len(grammar_rows)),
        "baseline_grammar_token_bytes": str(baseline_bytes),
        "baseline_covered_token_bytes": str(baseline_covered),
        "baseline_unresolved_token_bytes": str(baseline_bytes - baseline_covered),
        "promoted_token_rows": str(sum(1 for row in grammar_rows if row.get("promotion_status") == "promoted")),
        "promoted_bytes": str(promoted_bytes),
        "promoted_false_bytes": str(false_bytes),
        "final_unresolved_token_bytes": str(final_unresolved),
        "verdict": verdict,
    }


def total_summary(
    target_rows: list[dict[str, str]],
    gap_rows: list[dict[str, str]],
    grammar_rows: list[dict[str, str]],
    rule_rows: list[dict[str, str]],
    issue_count: int,
) -> dict[str, str]:
    baseline_bytes = sum(int_field(row, "length") for row in grammar_rows)
    baseline_covered = sum(
        int_field(row, "covered_bytes")
        for row in grammar_rows
        if row.get("baseline_verdict") == "covered"
    )
    final_covered = sum(int_field(row, "covered_bytes") for row in grammar_rows)
    promoted_rows = [row for row in grammar_rows if row.get("promotion_status") == "promoted"]
    promoted_bytes = sum(int_field(row, "covered_bytes") for row in promoted_rows)
    promoted_false = sum(int_field(row, "promoted_false_bytes") for row in gap_rows)
    final_unresolved_rows = [row for row in grammar_rows if row.get("verdict") != "covered"]
    final_unresolved = baseline_bytes - final_covered
    verdict = "frontier80_structural_zero_gap_anchor_promoted_grammar_ready"
    next_probe = "validate extended compact-control seed transforms by family"
    if issue_count:
        verdict = "frontier80_structural_zero_gap_anchor_promoted_grammar_issues"
        next_probe = "review promoted zero-gap anchor grammar input issues"
    elif promoted_false:
        verdict = "frontier80_structural_zero_gap_anchor_promoted_grammar_rejected"
        next_probe = "split promoted zero-gap anchor replay false positives"
    elif promoted_bytes == 0:
        verdict = "frontier80_structural_zero_gap_anchor_promoted_grammar_empty"
        next_probe = "review zero-gap anchor guard promotion inputs"
    return {
        "scope": "total",
        "selected_target_runs": str(len(target_rows)),
        "selected_target_bytes": str(sum(int_field(row, "length") for row in target_rows)),
        "token_rows": str(sum(int_field(row, "token_rows") for row in target_rows)),
        "ordered_bridge_rows": str(sum(int_field(row, "ordered_bridge_rows") for row in target_rows)),
        "control_gap_rows": str(len(gap_rows)),
        "baseline_grammar_token_rows": str(len(grammar_rows)),
        "baseline_grammar_token_bytes": str(baseline_bytes),
        "baseline_covered_token_bytes": str(baseline_covered),
        "baseline_unresolved_token_bytes": str(baseline_bytes - baseline_covered),
        "promoted_gap_rows": str(sum(1 for row in gap_rows if int_field(row, "promoted_bytes") > 0)),
        "promoted_token_rows": str(len(promoted_rows)),
        "promoted_bytes": str(promoted_bytes),
        "promotion_ready_bytes": str(promoted_bytes if promoted_false == 0 and issue_count == 0 else 0),
        "promoted_false_bytes": str(promoted_false),
        "promotion_exact_ratio": ratio(promoted_bytes, promoted_bytes + promoted_false),
        "final_covered_token_bytes": str(final_covered),
        "final_unresolved_token_rows": str(len(final_unresolved_rows)),
        "final_unresolved_token_bytes": str(final_unresolved),
        "final_covered_token_ratio": ratio(final_covered, baseline_bytes),
        "rule_rows": str(len(rule_rows)),
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
    promotion_rows: list[dict[str, str]],
    residual_rows: list[dict[str, str]],
) -> str:
    payload = {
        "summary": summary,
        "targets": target_rows,
        "gaps": gap_rows,
        "tokens": grammar_rows,
        "promotions": promotion_rows,
        "residuals": residual_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    cards = [
        ("Baseline unresolved", summary.get("baseline_unresolved_token_bytes", "0")),
        ("Promoted bytes", summary.get("promoted_bytes", "0")),
        ("False bytes", summary.get("promoted_false_bytes", "0")),
        ("Final unresolved", summary.get("final_unresolved_token_bytes", "0")),
        ("Final coverage", summary.get("final_covered_token_ratio", "0")),
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
  <div class="muted">Applies ready zero-gap anchor replay guards as a promoted compact-control grammar extension.</div>
  <div class="grid">{card_html}</div>
  <section><h2>Outputs</h2>
    <p><a href="{relative_href(output / 'summary.csv', output / 'index.html')}">summary.csv</a> ·
    <a href="{relative_href(output / 'targets.csv', output / 'index.html')}">targets.csv</a> ·
    <a href="{relative_href(output / 'gaps.csv', output / 'index.html')}">gaps.csv</a> ·
    <a href="{relative_href(output / 'token_validation.csv', output / 'index.html')}">token_validation.csv</a> ·
    <a href="{relative_href(output / 'promotions.csv', output / 'index.html')}">promotions.csv</a> ·
    <a href="{relative_href(output / 'residual_tokens.csv', output / 'index.html')}">residual_tokens.csv</a></p>
  </section>
  <section><h2>Promotions</h2>{render_table(promotion_rows, PROMOTION_FIELDNAMES)}</section>
  <section><h2>Final Residual Tokens</h2>{render_table(residual_rows, TOKEN_FIELDNAMES)}</section>
  <section><h2>Targets</h2>{render_table(target_rows, TARGET_FIELDNAMES)}</section>
  <section><h2>Gaps</h2>{render_table(gap_rows, GAP_FIELDNAMES)}</section>
  <section><h2>Token Validation</h2>{render_table(grammar_rows, TOKEN_FIELDNAMES)}</section>
</main>
<script type="application/json" id="zero-gap-anchor-promoted-grammar-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> dict[str, str]:
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    rules = ready_rules(read_csv(args.guard_rules))
    if not rules:
        issues.append("missing_ready_zero_gap_anchor_guard_rule")

    targets = select_targets(read_csv(args.runs), min_length=args.min_run_length, limit=args.target_limit)
    payloads = load_target_payloads(targets, read_csv(args.manifest), read_csv(args.clean_fixtures), issues)
    target_rows: list[dict[str, str]] = []
    gap_rows: list[dict[str, str]] = []
    grammar_rows: list[dict[str, str]] = []
    promotion_rows: list[dict[str, str]] = []

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
        payload_grammar_rows: list[dict[str, str]] = []
        for control_gap in control_gap_rows:
            baseline_rows = build_token_rows_for_gap(payload, control_gap, token_rows)
            gap_summary, final_rows, gap_promotion_rows = promoted_gap_rows(
                payload,
                target,
                control_gap,
                token_rows,
                baseline_rows,
                rules,
            )
            payload_gap_rows.append(gap_summary)
            payload_grammar_rows.extend(final_rows)
            promotion_rows.extend(gap_promotion_rows)
        target_rows.append(target_summary(payload, target, token_rows, ordered_rows, payload_gap_rows, payload_grammar_rows))
        gap_rows.extend(payload_gap_rows)
        grammar_rows.extend(payload_grammar_rows)

    residual_rows = [row for row in grammar_rows if row.get("verdict") != "covered"]
    summary = total_summary(target_rows, gap_rows, grammar_rows, rules, len(issues))
    write_csv(output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output / "targets.csv", TARGET_FIELDNAMES, target_rows)
    write_csv(output / "gaps.csv", GAP_FIELDNAMES, gap_rows)
    write_csv(output / "token_validation.csv", TOKEN_FIELDNAMES, grammar_rows)
    write_csv(output / "promotions.csv", PROMOTION_FIELDNAMES, promotion_rows)
    write_csv(output / "residual_tokens.csv", TOKEN_FIELDNAMES, residual_rows)
    (output / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""))
    (output / "index.html").write_text(
        build_html(output, args.title, summary, target_rows, gap_rows, grammar_rows, promotion_rows, residual_rows)
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate promoted zero-gap anchor replay inside the structural compact-control grammar."
    )
    parser.add_argument("--runs", type=Path, default=DEFAULT_RUNS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--clean-fixtures", type=Path, default=DEFAULT_CLEAN_FIXTURES)
    parser.add_argument("--guard-rules", type=Path, default=DEFAULT_GUARD_RULES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--target-limit", type=int, default=0)
    parser.add_argument("--min-run-length", type=int, default=1)
    parser.add_argument("--min-repeat", type=int, default=2)
    parser.add_argument("--min-delta", type=int, default=4)
    parser.add_argument("--max-delta", type=int, default=2)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Structural Zero-Gap Anchor Promoted Grammar Probe",
    )
    args = parser.parse_args()
    summary = write_report(args)
    print(f"Selected targets: {summary['selected_target_runs']}")
    print(f"Baseline unresolved bytes: {summary['baseline_unresolved_token_bytes']}")
    print(f"Promoted bytes: {summary['promoted_bytes']}")
    print(f"Final unresolved bytes: {summary['final_unresolved_token_bytes']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
