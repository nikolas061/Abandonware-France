#!/usr/bin/env python3
"""Derive guarded zero-gap anchor-source replay rules for structural compact-control residuals."""

from __future__ import annotations

import argparse
import html
import json
from collections import defaultdict
from pathlib import Path

from lolg_tex_gap_opcode_probe import relative_href, write_csv
from lolg_tex_gap_decoder_frontier80_clean_structural_nonzero_producer_probe import (
    ratio,
    read_csv,
)
from lolg_tex_gap_decoder_frontier80_clean_structural_nonzero_compact_control_grammar_probe import (
    int_field,
)


DEFAULT_RESIDUALS = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_compact_control_residual_value_family_probe/residual_tokens.csv"
)
DEFAULT_ZERO_GAPS = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_compact_control_zero_gap_anchor_bridge_probe/zero_gap_rows.csv"
)
DEFAULT_ANCHOR_SOURCES = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_compact_control_zero_gap_anchor_bridge_probe/anchor_sources.csv"
)
DEFAULT_OUTPUT = Path(
    "output/tex_gap_decoder_frontier80_clean_structural_nonzero_compact_control_zero_gap_anchor_guard_rule_probe"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "zero_gap_rows",
    "zero_gap_token_rows",
    "zero_gap_bytes",
    "guard_rule_rows",
    "guarded_gap_rows",
    "guarded_token_rows",
    "guarded_bytes",
    "replay_exact_bytes",
    "replay_exact_ratio",
    "exact_seed_rows",
    "false_guard_rows",
    "unresolved_guard_rows",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

RULE_FIELDNAMES = [
    "rule_id",
    "gap_rows",
    "token_rows",
    "token_bytes",
    "target_gap_bytes",
    "control_gap_bytes",
    "token_signature",
    "value_family",
    "source_scope",
    "source_transform",
    "anchor_plan",
    "source_side_plan",
    "guard_conditions",
    "replay_exact_bytes",
    "false_guard_rows",
    "verdict",
    "next_probe",
]

GUARD_FIELDNAMES = [
    "target_id",
    "pcx_name",
    "gap_index",
    "rule_id",
    "target_gap_bytes",
    "control_gap_bytes",
    "token_signature",
    "value_family",
    "anchor_plan",
    "guard_conditions",
    "guard_matched",
    "guarded_bytes",
    "replay_exact_bytes",
    "false_guard_rows",
    "verdict",
]

REPLAY_FIELDNAMES = [
    "target_id",
    "pcx_name",
    "gap_index",
    "token_order",
    "token_index",
    "token_type",
    "length",
    "target_hex",
    "value_family",
    "source_anchor_delta",
    "anchor_side",
    "source_scope",
    "source_transform",
    "source_delta",
    "source_value_hex",
    "source_context_hex",
    "replay_exact_bytes",
    "replay_rule",
    "verdict",
]


def group_key(row: dict[str, str]) -> tuple[str, str]:
    return row.get("target_id", ""), row.get("gap_index", "")


def token_letter(row: dict[str, str]) -> str:
    token_type = row.get("token_type", "")
    if token_type == "delta":
        return "D"
    if token_type == "repeat":
        return "R"
    return "L"


def token_signature(rows: list[dict[str, str]]) -> str:
    return ".".join(f"{token_letter(row)}{int_field(row, 'length')}" for row in rows)


def value_family(rows: list[dict[str, str]]) -> str:
    families = sorted({row.get("value_family", "") for row in rows if row.get("value_family", "")})
    return "+".join(families)


def anchor_plan(rows: list[dict[str, str]]) -> str:
    parts = []
    for order, row in enumerate(rows, start=1):
        parts.append(
            f"{order}:{token_letter(row)}{int_field(row, 'length')}@{row.get('source_anchor_delta', '')}"
        )
    return " ".join(parts)


def source_side_plan(rows: list[dict[str, str]]) -> str:
    return " ".join(f"{index}:{row.get('anchor_side', '')}" for index, row in enumerate(rows, start=1))


def guard_conditions(
    *,
    target_gap_bytes: int,
    signature: str,
    family: str,
    scope: str,
    transform: str,
) -> str:
    return (
        "control_gap_bytes=0;"
        f"target_gap_bytes={target_gap_bytes};"
        f"token_signature={signature};"
        f"value_family={family};"
        f"source_scope={scope};"
        f"source_transform={transform}"
    )


def all_same(values: list[str]) -> str:
    present = sorted({value for value in values if value})
    return present[0] if len(present) == 1 else "+".join(present)


def replay_rows_for_group(anchor_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for order, row in enumerate(anchor_rows, start=1):
        length = int_field(row, "length")
        replay_exact = length if row.get("verdict") == "anchor_seed_ready" else 0
        replay_rule = (
            f"emit_{row.get('token_type', '')}_from_anchor"
            f"{row.get('source_anchor_delta', '')}_{row.get('source_transform', '')}"
        )
        rows.append(
            {
                "target_id": row.get("target_id", ""),
                "pcx_name": row.get("pcx_name", ""),
                "gap_index": row.get("gap_index", ""),
                "token_order": str(order),
                "token_index": row.get("token_index", ""),
                "token_type": row.get("token_type", ""),
                "length": row.get("length", ""),
                "target_hex": row.get("target_hex", ""),
                "value_family": row.get("value_family", ""),
                "source_anchor_delta": row.get("source_anchor_delta", ""),
                "anchor_side": row.get("anchor_side", ""),
                "source_scope": row.get("source_scope", ""),
                "source_transform": row.get("source_transform", ""),
                "source_delta": row.get("source_delta", ""),
                "source_value_hex": row.get("source_value_hex", ""),
                "source_context_hex": row.get("source_context_hex", ""),
                "replay_exact_bytes": str(replay_exact),
                "replay_rule": replay_rule,
                "verdict": "replay_exact" if replay_exact == length else "replay_partial",
            }
        )
    return rows


def rule_id(signature: str, plan: str) -> str:
    compact_plan = plan.replace(" ", "_").replace("+", "p").replace("-", "m").replace(":", "")
    return f"zero_gap_{signature.replace('.', '_')}_{compact_plan}"


def build_reports(
    zero_gaps: list[dict[str, str]],
    residuals_by_gap: dict[tuple[str, str], list[dict[str, str]]],
    anchors_by_gap: dict[tuple[str, str], list[dict[str, str]]],
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], list[str]]:
    issues: list[str] = []
    guard_rows: list[dict[str, str]] = []
    replay_rows: list[dict[str, str]] = []
    rule_groups: dict[str, dict[str, object]] = {}

    for gap in zero_gaps:
        key = group_key(gap)
        residual_rows = sorted(residuals_by_gap.get(key, []), key=lambda row: int_field(row, "token_index"))
        anchor_rows = sorted(anchors_by_gap.get(key, []), key=lambda row: int_field(row, "token_index"))
        if not residual_rows:
            issues.append(f"{key[0]}:g{key[1]}:missing_residual_rows")
            continue
        if len(anchor_rows) != len(residual_rows):
            issues.append(f"{key[0]}:g{key[1]}:anchor_residual_row_mismatch")
        signature = token_signature(anchor_rows or residual_rows)
        family = value_family(anchor_rows or residual_rows)
        scope = all_same([row.get("source_scope", "") for row in anchor_rows])
        transform = all_same([row.get("source_transform", "") for row in anchor_rows])
        target_gap_bytes = sum(int_field(row, "length") for row in residual_rows)
        plan = anchor_plan(anchor_rows)
        sides = source_side_plan(anchor_rows)
        conditions = guard_conditions(
            target_gap_bytes=target_gap_bytes,
            signature=signature,
            family=family,
            scope=scope,
            transform=transform,
        )
        current_rule_id = rule_id(signature, plan)
        current_replay_rows = replay_rows_for_group(anchor_rows)
        replay_rows.extend(current_replay_rows)
        replay_exact = sum(int_field(row, "replay_exact_bytes") for row in current_replay_rows)
        false_guard_rows = 0
        guard_matched = (
            int_field(gap, "control_gap_bytes") == 0
            and bool(anchor_rows)
            and replay_exact == target_gap_bytes
            and transform == "exact_seed"
            and scope == "near_anchor_window"
            and family == "zero_control_gap_low_delta"
        )
        if not guard_matched:
            false_guard_rows = 1
        guard_rows.append(
            {
                "target_id": gap.get("target_id", ""),
                "pcx_name": gap.get("pcx_name", ""),
                "gap_index": gap.get("gap_index", ""),
                "rule_id": current_rule_id,
                "target_gap_bytes": str(target_gap_bytes),
                "control_gap_bytes": gap.get("control_gap_bytes", ""),
                "token_signature": signature,
                "value_family": family,
                "anchor_plan": plan,
                "guard_conditions": conditions,
                "guard_matched": "1" if guard_matched else "0",
                "guarded_bytes": str(target_gap_bytes if guard_matched else 0),
                "replay_exact_bytes": str(replay_exact),
                "false_guard_rows": str(false_guard_rows),
                "verdict": "guarded_zero_gap_replay_ready" if guard_matched else "guard_rejected",
            }
        )
        group = rule_groups.setdefault(
            current_rule_id,
            {
                "target_gap_bytes": target_gap_bytes,
                "control_gap_bytes": 0,
                "token_signature": signature,
                "value_family": family,
                "source_scope": scope,
                "source_transform": transform,
                "anchor_plan": plan,
                "source_side_plan": sides,
                "guard_conditions": conditions,
                "gap_rows": 0,
                "token_rows": 0,
                "token_bytes": 0,
                "replay_exact_bytes": 0,
                "false_guard_rows": 0,
            },
        )
        group["gap_rows"] = int(group["gap_rows"]) + 1
        group["token_rows"] = int(group["token_rows"]) + len(anchor_rows)
        group["token_bytes"] = int(group["token_bytes"]) + target_gap_bytes
        group["replay_exact_bytes"] = int(group["replay_exact_bytes"]) + replay_exact
        group["false_guard_rows"] = int(group["false_guard_rows"]) + false_guard_rows

    rule_rows: list[dict[str, str]] = []
    for current_rule_id, group in sorted(rule_groups.items()):
        token_bytes = int(group["token_bytes"])
        replay_exact = int(group["replay_exact_bytes"])
        false_guard_rows = int(group["false_guard_rows"])
        verdict = "guarded_zero_gap_anchor_rule_ready"
        next_probe = "promote guarded zero-gap anchor-source replay into structural compact-control grammar"
        if false_guard_rows or replay_exact != token_bytes:
            verdict = "guarded_zero_gap_anchor_rule_partial"
            next_probe = "split guarded zero-gap anchor-source replay misses"
        rule_rows.append(
            {
                "rule_id": current_rule_id,
                "gap_rows": str(group["gap_rows"]),
                "token_rows": str(group["token_rows"]),
                "token_bytes": str(token_bytes),
                "target_gap_bytes": str(group["target_gap_bytes"]),
                "control_gap_bytes": str(group["control_gap_bytes"]),
                "token_signature": str(group["token_signature"]),
                "value_family": str(group["value_family"]),
                "source_scope": str(group["source_scope"]),
                "source_transform": str(group["source_transform"]),
                "anchor_plan": str(group["anchor_plan"]),
                "source_side_plan": str(group["source_side_plan"]),
                "guard_conditions": str(group["guard_conditions"]),
                "replay_exact_bytes": str(replay_exact),
                "false_guard_rows": str(false_guard_rows),
                "verdict": verdict,
                "next_probe": next_probe,
            }
        )
    return rule_rows, guard_rows, replay_rows, issues


def total_summary(
    zero_gaps: list[dict[str, str]],
    residual_rows: list[dict[str, str]],
    rule_rows: list[dict[str, str]],
    guard_rows: list[dict[str, str]],
    replay_rows: list[dict[str, str]],
    issue_count: int,
) -> dict[str, str]:
    zero_gap_bytes = sum(int_field(row, "length") for row in residual_rows)
    guarded_rows = [row for row in guard_rows if row.get("guard_matched") == "1"]
    guarded_bytes = sum(int_field(row, "guarded_bytes") for row in guarded_rows)
    replay_exact = sum(int_field(row, "replay_exact_bytes") for row in replay_rows)
    false_guard_rows = sum(int_field(row, "false_guard_rows") for row in guard_rows)
    unresolved = len(guard_rows) - len(guarded_rows)
    verdict = "frontier80_structural_zero_gap_anchor_guard_rule_ready"
    next_probe = "promote guarded zero-gap anchor-source replay into structural compact-control grammar"
    if false_guard_rows or replay_exact != zero_gap_bytes:
        verdict = "frontier80_structural_zero_gap_anchor_guard_rule_partial"
        next_probe = "split guarded zero-gap anchor-source replay misses"
    return {
        "scope": "total",
        "zero_gap_rows": str(len(zero_gaps)),
        "zero_gap_token_rows": str(len(residual_rows)),
        "zero_gap_bytes": str(zero_gap_bytes),
        "guard_rule_rows": str(len(rule_rows)),
        "guarded_gap_rows": str(len(guarded_rows)),
        "guarded_token_rows": str(sum(int_field(row, "token_rows") for row in rule_rows)),
        "guarded_bytes": str(guarded_bytes),
        "replay_exact_bytes": str(replay_exact),
        "replay_exact_ratio": ratio(replay_exact, zero_gap_bytes),
        "exact_seed_rows": str(sum(1 for row in replay_rows if row.get("source_transform") == "exact_seed")),
        "false_guard_rows": str(false_guard_rows),
        "unresolved_guard_rows": str(unresolved),
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
    rule_rows: list[dict[str, str]],
    guard_rows: list[dict[str, str]],
    replay_rows: list[dict[str, str]],
) -> str:
    payload = {"summary": summary, "rules": rule_rows, "guards": guard_rows, "replay": replay_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    cards = [
        ("Zero-gap bytes", summary.get("zero_gap_bytes", "0")),
        ("Guarded bytes", summary.get("guarded_bytes", "0")),
        ("Replay ratio", summary.get("replay_exact_ratio", "0")),
        ("Rules", summary.get("guard_rule_rows", "0")),
        ("False guards", summary.get("false_guard_rows", "0")),
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
  <div class="muted">Derives a guarded replay rule from zero-gap anchor-source seed evidence.</div>
  <div class="grid">{card_html}</div>
  <section><h2>Outputs</h2>
    <p><a href="{relative_href(output / 'summary.csv', output / 'index.html')}">summary.csv</a> ·
    <a href="{relative_href(output / 'guard_rules.csv', output / 'index.html')}">guard_rules.csv</a> ·
    <a href="{relative_href(output / 'guard_rows.csv', output / 'index.html')}">guard_rows.csv</a> ·
    <a href="{relative_href(output / 'replay_rows.csv', output / 'index.html')}">replay_rows.csv</a></p>
  </section>
  <section><h2>Guard Rules</h2>{render_table(rule_rows, RULE_FIELDNAMES)}</section>
  <section><h2>Guard Rows</h2>{render_table(guard_rows, GUARD_FIELDNAMES)}</section>
  <section><h2>Replay Rows</h2>{render_table(replay_rows, REPLAY_FIELDNAMES)}</section>
</main>
<script type="application/json" id="zero-gap-anchor-guard-rule-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> dict[str, str]:
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    residual_rows = [
        row for row in read_csv(args.residuals) if row.get("control_gap_status") == "zero_control_gap"
    ]
    zero_gaps = read_csv(args.zero_gaps)
    residuals_by_gap: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in residual_rows:
        residuals_by_gap[group_key(row)].append(row)
    anchors_by_gap: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in read_csv(args.anchor_sources):
        anchors_by_gap[group_key(row)].append(row)

    rule_rows, guard_rows, replay_rows, issues = build_reports(zero_gaps, residuals_by_gap, anchors_by_gap)
    summary = total_summary(zero_gaps, residual_rows, rule_rows, guard_rows, replay_rows, len(issues))
    write_csv(output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output / "guard_rules.csv", RULE_FIELDNAMES, rule_rows)
    write_csv(output / "guard_rows.csv", GUARD_FIELDNAMES, guard_rows)
    write_csv(output / "replay_rows.csv", REPLAY_FIELDNAMES, replay_rows)
    (output / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""))
    (output / "index.html").write_text(
        build_html(output, args.title, summary, rule_rows, guard_rows, replay_rows)
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Derive guarded zero-gap anchor-source replay rules for structural compact-control residuals."
    )
    parser.add_argument("--residuals", type=Path, default=DEFAULT_RESIDUALS)
    parser.add_argument("--zero-gaps", type=Path, default=DEFAULT_ZERO_GAPS)
    parser.add_argument("--anchor-sources", type=Path, default=DEFAULT_ANCHOR_SOURCES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Structural Zero-Gap Anchor Guard Rule Probe",
    )
    args = parser.parse_args()
    summary = write_report(args)
    print(f"Zero-gap bytes: {summary['zero_gap_bytes']}")
    print(f"Guarded bytes: {summary['guarded_bytes']}")
    print(f"Replay exact ratio: {summary['replay_exact_ratio']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
