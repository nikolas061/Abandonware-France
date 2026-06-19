#!/usr/bin/env python3
"""Promote extended local and near-anchor compact-control replay rules."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

from lolg_tex_gap_opcode_probe import relative_href, write_csv
from lolg_tex_gap_decoder_frontier80_clean_structural_nonzero_producer_probe import (
    ratio,
    read_csv,
)
from lolg_tex_gap_decoder_frontier80_clean_structural_nonzero_compact_control_grammar_probe import (
    int_field,
)


DEFAULT_ZERO_GAP_TOKEN_VALIDATION = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_compact_control_zero_gap_anchor_promoted_grammar_probe/token_validation.csv"
)
DEFAULT_EXTENDED_LOCAL_VALIDATION = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_compact_control_extended_local_seed_transform_validation_probe/validation_rows.csv"
)
DEFAULT_NEAR_ANCHOR_REPLAY = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_compact_control_near_anchor_source_rule_probe/replay_rows.csv"
)
DEFAULT_NEAR_ANCHOR_RULES = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_compact_control_near_anchor_source_rule_probe/near_anchor_rules.csv"
)
DEFAULT_OUTPUT = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_compact_control_near_anchor_promoted_grammar_probe"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "grammar_token_rows",
    "grammar_token_bytes",
    "baseline_covered_token_bytes",
    "baseline_unresolved_token_bytes",
    "zero_gap_promoted_token_rows",
    "zero_gap_promoted_bytes",
    "extended_local_promoted_token_rows",
    "extended_local_promoted_bytes",
    "near_anchor_promoted_token_rows",
    "near_anchor_promoted_bytes",
    "promoted_token_rows",
    "promoted_bytes",
    "promotion_ready_bytes",
    "promoted_false_bytes",
    "final_covered_token_rows",
    "final_covered_token_bytes",
    "final_unresolved_token_rows",
    "final_unresolved_token_bytes",
    "final_covered_token_ratio",
    "issue_rows",
    "review_verdict",
    "next_probe",
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
    "token_type",
    "length",
    "target_hex",
    "promotion_source",
    "promotion_rule_id",
    "source_transform",
    "source_delta",
    "source_value_hex",
    "source_gap_offset",
    "source_segment_offset",
    "source_occurrences",
    "source_context_hex",
    "replay_hex",
    "replay_exact_bytes",
    "promoted_bytes",
    "false_bytes",
    "verdict",
]


def row_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("target_id", ""), row.get("gap_index", ""), row.get("token_index", "")


def promotion_row(
    row: dict[str, str],
    *,
    promotion_source: str,
    promotion_rule_id: str,
    source_gap_offset: str = "",
    false_bytes: int = 0,
) -> dict[str, str]:
    return {
        "target_id": row.get("target_id", ""),
        "rank": row.get("rank", ""),
        "pcx_name": row.get("pcx_name", ""),
        "frontier_id": row.get("frontier_id", ""),
        "span_index": row.get("span_index", ""),
        "gap_index": row.get("gap_index", ""),
        "token_index": row.get("token_index", ""),
        "token_type": row.get("token_type", ""),
        "length": row.get("length", ""),
        "target_hex": row.get("target_hex", ""),
        "promotion_source": promotion_source,
        "promotion_rule_id": promotion_rule_id,
        "source_transform": row.get("source_transform", ""),
        "source_delta": row.get("source_delta", ""),
        "source_value_hex": row.get("source_value_hex", ""),
        "source_gap_offset": source_gap_offset or row.get("source_gap_offset", ""),
        "source_segment_offset": row.get("source_segment_offset", ""),
        "source_occurrences": row.get("source_occurrences", ""),
        "source_context_hex": row.get("source_context_hex", ""),
        "replay_hex": row.get("replay_hex", ""),
        "replay_exact_bytes": row.get("replay_exact_bytes", ""),
        "promoted_bytes": row.get("covered_bytes", ""),
        "false_bytes": str(false_bytes),
        "verdict": "promoted_replay_exact" if false_bytes == 0 else "promoted_replay_false",
    }


def apply_extended_local(
    token_rows_by_key: dict[tuple[str, str, str], dict[str, str]],
    validation_rows: list[dict[str, str]],
    issues: list[str],
) -> list[dict[str, str]]:
    promotions: list[dict[str, str]] = []
    for validation in validation_rows:
        if validation.get("verdict") != "extended_local_seed_transform_validated":
            continue
        key = row_key(validation)
        target = token_rows_by_key.get(key)
        if target is None:
            issues.append(f"{':'.join(key)}:missing_token_for_extended_local_promotion")
            continue
        if target.get("verdict") == "covered":
            continue
        if validation.get("replay_hex", "") != target.get("target_hex", ""):
            issues.append(f"{':'.join(key)}:extended_local_replay_mismatch")
            continue
        covered = int_field(validation, "validated_bytes")
        target.update(
            {
                "source_transform": validation.get("source_transform", ""),
                "source_delta": validation.get("source_delta", ""),
                "source_value_hex": validation.get("source_value_hex", ""),
                "source_gap_offset": validation.get("source_offset", ""),
                "source_segment_offset": validation.get("source_segment_offset", ""),
                "source_occurrences": validation.get("source_occurrences", ""),
                "source_context_hex": validation.get("source_context_hex", ""),
                "grammar_rule": f"extended_local_seed_{target.get('token_type', '')}",
                "covered_bytes": str(covered),
                "replay_hex": validation.get("replay_hex", ""),
                "replay_exact_bytes": validation.get("replay_exact_bytes", ""),
                "verdict": "covered",
                "promotion_rule_id": f"extended_local_seed_{validation.get('source_transform', '')}",
                "promotion_anchor_delta": validation.get("source_offset", ""),
                "promotion_status": "extended_local_seed_promoted",
            }
        )
        promotions.append(
            promotion_row(
                target,
                promotion_source="extended_local_seed",
                promotion_rule_id=target.get("promotion_rule_id", ""),
                source_gap_offset=validation.get("source_offset", ""),
            )
        )
    return promotions


def apply_near_anchor(
    token_rows_by_key: dict[tuple[str, str, str], dict[str, str]],
    replay_rows: list[dict[str, str]],
    near_anchor_rules: list[dict[str, str]],
    issues: list[str],
) -> list[dict[str, str]]:
    promotions: list[dict[str, str]] = []
    ready_rules = [
        row
        for row in near_anchor_rules
        if row.get("verdict") == "guarded_near_anchor_source_rule_ready"
        and int_field(row, "false_guard_rows") == 0
    ]
    rule_id = ready_rules[0].get("rule_id", "") if ready_rules else ""
    if not rule_id and replay_rows:
        issues.append("missing_ready_near_anchor_rule")
    for replay in replay_rows:
        if replay.get("verdict") != "replay_exact":
            continue
        key = row_key(replay)
        target = token_rows_by_key.get(key)
        if target is None:
            issues.append(f"{':'.join(key)}:missing_token_for_near_anchor_promotion")
            continue
        if target.get("verdict") == "covered":
            continue
        if replay.get("replay_hex", "") != target.get("target_hex", ""):
            issues.append(f"{':'.join(key)}:near_anchor_replay_mismatch")
            continue
        covered = int_field(replay, "replay_exact_bytes")
        target.update(
            {
                "source_transform": replay.get("source_transform", ""),
                "source_delta": replay.get("source_delta", ""),
                "source_value_hex": replay.get("source_value_hex", ""),
                "source_gap_offset": replay.get("distance_to_gap", ""),
                "source_segment_offset": replay.get("source_segment_offset", ""),
                "source_occurrences": "1",
                "source_context_hex": replay.get("source_context_hex", ""),
                "grammar_rule": f"near_anchor_exact_seed_{target.get('token_type', '')}",
                "covered_bytes": str(covered),
                "replay_hex": replay.get("replay_hex", ""),
                "replay_exact_bytes": replay.get("replay_exact_bytes", ""),
                "verdict": "covered",
                "promotion_rule_id": rule_id or "near_anchor_exact_seed",
                "promotion_anchor_delta": replay.get("distance_to_gap", ""),
                "promotion_status": "near_anchor_source_promoted",
            }
        )
        promotions.append(
            promotion_row(
                target,
                promotion_source="near_anchor_source",
                promotion_rule_id=target.get("promotion_rule_id", ""),
                source_gap_offset=replay.get("distance_to_gap", ""),
            )
        )
    return promotions


def zero_gap_promotions(token_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in token_rows:
        if row.get("promotion_status") != "promoted":
            continue
        row["promotion_status"] = "zero_gap_anchor_promoted"
        rows.append(
            promotion_row(
                row,
                promotion_source="zero_gap_anchor",
                promotion_rule_id=row.get("promotion_rule_id", ""),
                source_gap_offset=row.get("promotion_anchor_delta", ""),
            )
        )
    return rows


def total_summary(token_rows: list[dict[str, str]], promotion_rows: list[dict[str, str]], issue_count: int) -> dict[str, str]:
    grammar_bytes = sum(int_field(row, "length") for row in token_rows)
    baseline_covered = sum(
        int_field(row, "length")
        for row in token_rows
        if row.get("baseline_verdict") == "covered"
    )
    final_covered_rows = [row for row in token_rows if row.get("verdict") == "covered"]
    final_covered = sum(int_field(row, "covered_bytes") for row in final_covered_rows)
    unresolved_rows = [row for row in token_rows if row.get("verdict") != "covered"]
    promoted_false = sum(int_field(row, "false_bytes") for row in promotion_rows)

    def promoted_bytes(source: str) -> int:
        return sum(int_field(row, "promoted_bytes") for row in promotion_rows if row.get("promotion_source") == source)

    def promoted_count(source: str) -> int:
        return sum(1 for row in promotion_rows if row.get("promotion_source") == source)

    promoted_total = sum(int_field(row, "promoted_bytes") for row in promotion_rows)
    verdict = "frontier80_structural_compact_control_near_anchor_promoted_grammar_ready"
    next_probe = "integrate promoted compact-control grammar into structural nonzero replay"
    if issue_count:
        verdict = "frontier80_structural_compact_control_near_anchor_promoted_grammar_issues"
        next_probe = "review compact-control near-anchor promotion issues"
    elif promoted_false:
        verdict = "frontier80_structural_compact_control_near_anchor_promoted_grammar_rejected"
        next_probe = "split compact-control near-anchor promotion false positives"
    elif unresolved_rows:
        verdict = "frontier80_structural_compact_control_near_anchor_promoted_grammar_partial"
        next_probe = "split remaining compact-control promoted grammar residuals"
    return {
        "scope": "total",
        "grammar_token_rows": str(len(token_rows)),
        "grammar_token_bytes": str(grammar_bytes),
        "baseline_covered_token_bytes": str(baseline_covered),
        "baseline_unresolved_token_bytes": str(grammar_bytes - baseline_covered),
        "zero_gap_promoted_token_rows": str(promoted_count("zero_gap_anchor")),
        "zero_gap_promoted_bytes": str(promoted_bytes("zero_gap_anchor")),
        "extended_local_promoted_token_rows": str(promoted_count("extended_local_seed")),
        "extended_local_promoted_bytes": str(promoted_bytes("extended_local_seed")),
        "near_anchor_promoted_token_rows": str(promoted_count("near_anchor_source")),
        "near_anchor_promoted_bytes": str(promoted_bytes("near_anchor_source")),
        "promoted_token_rows": str(len(promotion_rows)),
        "promoted_bytes": str(promoted_total),
        "promotion_ready_bytes": str(promoted_total if not promoted_false and not issue_count and not unresolved_rows else 0),
        "promoted_false_bytes": str(promoted_false),
        "final_covered_token_rows": str(len(final_covered_rows)),
        "final_covered_token_bytes": str(final_covered),
        "final_unresolved_token_rows": str(len(unresolved_rows)),
        "final_unresolved_token_bytes": str(sum(int_field(row, "length") for row in unresolved_rows)),
        "final_covered_token_ratio": ratio(final_covered, grammar_bytes),
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
    token_rows: list[dict[str, str]],
    promotion_rows: list[dict[str, str]],
    residual_rows: list[dict[str, str]],
) -> str:
    payload = {
        "summary": summary,
        "tokens": token_rows,
        "promotions": promotion_rows,
        "residuals": residual_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    cards = [
        ("Baseline unresolved", summary.get("baseline_unresolved_token_bytes", "0")),
        ("Promoted bytes", summary.get("promoted_bytes", "0")),
        ("Final unresolved", summary.get("final_unresolved_token_bytes", "0")),
        ("Final coverage", summary.get("final_covered_token_ratio", "0")),
        ("False bytes", summary.get("promoted_false_bytes", "0")),
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
  <div class="muted">Applies zero-gap, extended local seed, and near-anchor compact-control replay rules into one promoted grammar validation.</div>
  <div class="grid">{card_html}</div>
  <section><h2>Outputs</h2>
    <p><a href="{relative_href(output / 'summary.csv', output / 'index.html')}">summary.csv</a> ·
    <a href="{relative_href(output / 'token_validation.csv', output / 'index.html')}">token_validation.csv</a> ·
    <a href="{relative_href(output / 'promotions.csv', output / 'index.html')}">promotions.csv</a> ·
    <a href="{relative_href(output / 'residual_tokens.csv', output / 'index.html')}">residual_tokens.csv</a></p>
  </section>
  <section><h2>Promotions</h2>{render_table(promotion_rows, PROMOTION_FIELDNAMES)}</section>
  <section><h2>Residual Tokens</h2>{render_table(residual_rows, TOKEN_FIELDNAMES)}</section>
  <section><h2>Token Validation</h2>{render_table(token_rows, TOKEN_FIELDNAMES)}</section>
</main>
<script type="application/json" id="near-anchor-promoted-grammar-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> dict[str, str]:
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    token_rows = read_csv(args.zero_gap_token_validation)
    token_rows_by_key = {row_key(row): row for row in token_rows}
    promotion_rows = zero_gap_promotions(token_rows)
    promotion_rows.extend(
        apply_extended_local(token_rows_by_key, read_csv(args.extended_local_validation), issues)
    )
    promotion_rows.extend(
        apply_near_anchor(token_rows_by_key, read_csv(args.near_anchor_replay), read_csv(args.near_anchor_rules), issues)
    )
    residual_rows = [row for row in token_rows if row.get("verdict") != "covered"]
    summary = total_summary(token_rows, promotion_rows, len(issues))
    write_csv(output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output / "token_validation.csv", TOKEN_FIELDNAMES, token_rows)
    write_csv(output / "promotions.csv", PROMOTION_FIELDNAMES, promotion_rows)
    write_csv(output / "residual_tokens.csv", TOKEN_FIELDNAMES, residual_rows)
    (output / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""))
    (output / "index.html").write_text(build_html(output, args.title, summary, token_rows, promotion_rows, residual_rows))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Promote extended local and near-anchor compact-control replay rules."
    )
    parser.add_argument("--zero-gap-token-validation", type=Path, default=DEFAULT_ZERO_GAP_TOKEN_VALIDATION)
    parser.add_argument("--extended-local-validation", type=Path, default=DEFAULT_EXTENDED_LOCAL_VALIDATION)
    parser.add_argument("--near-anchor-replay", type=Path, default=DEFAULT_NEAR_ANCHOR_REPLAY)
    parser.add_argument("--near-anchor-rules", type=Path, default=DEFAULT_NEAR_ANCHOR_RULES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Structural Near-Anchor Promoted Grammar Probe",
    )
    args = parser.parse_args()
    summary = write_report(args)
    print(f"Grammar bytes: {summary['grammar_token_bytes']}")
    print(f"Promoted bytes: {summary['promoted_bytes']}")
    print(f"Final unresolved bytes: {summary['final_unresolved_token_bytes']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
