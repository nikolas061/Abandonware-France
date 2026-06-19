#!/usr/bin/env python3
"""Derive near-anchor source rules for remaining compact-control residuals."""

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


DEFAULT_REMAINING_TOKENS = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_compact_control_extended_local_seed_transform_validation_probe/remaining_tokens.csv"
)
DEFAULT_SOURCE_CANDIDATES = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_compact_control_residual_value_family_probe/source_candidates.csv"
)
DEFAULT_OUTPUT = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_compact_control_near_anchor_source_rule_probe"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "remaining_token_rows",
    "remaining_bytes",
    "near_candidate_token_rows",
    "near_candidate_bytes",
    "guard_rule_rows",
    "guarded_gap_rows",
    "guarded_token_rows",
    "guarded_bytes",
    "exact_seed_rows",
    "replay_exact_bytes",
    "replay_exact_ratio",
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
    "control_gap_bytes",
    "token_signature",
    "value_families",
    "source_scope",
    "source_transform",
    "source_plan",
    "distance_plan",
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
    "token_signature",
    "value_families",
    "control_gap_bytes",
    "source_plan",
    "distance_plan",
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
    "source_scope",
    "source_transform",
    "source_delta",
    "source_value_hex",
    "source_segment_offset",
    "distance_to_gap",
    "source_context_hex",
    "replay_hex",
    "replay_exact_bytes",
    "replay_rule",
    "verdict",
]


def row_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("target_id", ""), row.get("gap_index", ""), row.get("token_index", "")


def group_key(row: dict[str, str]) -> tuple[str, str]:
    return row.get("target_id", ""), row.get("gap_index", "")


def parse_hex_bytes(text: str) -> bytes:
    try:
        return bytes.fromhex(text)
    except ValueError:
        return b""


def parse_hex_byte(text: str) -> int | None:
    if not text:
        return None
    try:
        return int(text, 16)
    except ValueError:
        return None


def token_letter(row: dict[str, str]) -> str:
    token_type = row.get("token_type", "")
    if token_type == "delta":
        return "D"
    if token_type == "repeat":
        return "R"
    return "L"


def token_signature(rows: list[dict[str, str]]) -> str:
    return ".".join(f"{token_letter(row)}{int_field(row, 'length')}" for row in rows)


def replay_from_seed(token_type: str, length: int, seed: int) -> bytes:
    if length <= 0:
        return b""
    if token_type == "literal" and length == 1:
        return bytes([seed])
    if token_type == "repeat":
        return bytes([seed]) * length
    return b""


def choose_near_candidate(rows: list[dict[str, str]]) -> dict[str, str] | None:
    candidates = [
        row
        for row in rows
        if row.get("scope") == "near_anchor_window" and row.get("source_transform") == "exact_seed"
    ]
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda row: (
            int_field(row, "distance_to_gap"),
            int_field(row, "source_segment_offset"),
        ),
    )


def source_plan(rows: list[dict[str, str]], candidates: list[dict[str, str] | None]) -> str:
    parts = []
    for order, (row, candidate) in enumerate(zip(rows, candidates), start=1):
        offset = "" if candidate is None else candidate.get("source_segment_offset", "")
        parts.append(f"{order}:{token_letter(row)}{int_field(row, 'length')}@{offset}")
    return " ".join(parts)


def distance_plan(candidates: list[dict[str, str] | None]) -> str:
    parts = []
    for order, candidate in enumerate(candidates, start=1):
        distance = "" if candidate is None else candidate.get("distance_to_gap", "")
        parts.append(f"{order}:d{distance}")
    return " ".join(parts)


def guard_conditions(control_gap_bytes: int, signature: str, families: str, scope: str, transform: str) -> str:
    return (
        f"control_gap_bytes={control_gap_bytes};"
        f"token_signature={signature};"
        f"value_families={families};"
        f"source_scope={scope};"
        f"source_transform={transform}"
    )


def rule_id(signature: str, plan: str) -> str:
    compact_plan = plan.replace(" ", "_").replace(":", "").replace("@", "s")
    return f"near_anchor_{signature.replace('.', '_')}_{compact_plan}"


def replay_row(
    row: dict[str, str],
    candidate: dict[str, str] | None,
    order: int,
) -> dict[str, str]:
    target = parse_hex_bytes(row.get("target_hex", ""))
    length = int_field(row, "length", len(target))
    source_value = None if candidate is None else parse_hex_byte(candidate.get("source_value_hex", ""))
    replay = b""
    if source_value is not None:
        replay = replay_from_seed(row.get("token_type", ""), length, source_value)
    exact = sum(1 for left, right in zip(replay, target) if left == right)
    verdict = "replay_exact" if replay == target else "replay_partial"
    return {
        "target_id": row.get("target_id", ""),
        "pcx_name": row.get("pcx_name", ""),
        "gap_index": row.get("gap_index", ""),
        "token_order": str(order),
        "token_index": row.get("token_index", ""),
        "token_type": row.get("token_type", ""),
        "length": str(length),
        "target_hex": row.get("target_hex", ""),
        "value_family": row.get("value_family", ""),
        "source_scope": "" if candidate is None else candidate.get("scope", ""),
        "source_transform": "" if candidate is None else candidate.get("source_transform", ""),
        "source_delta": "" if candidate is None else candidate.get("source_delta", ""),
        "source_value_hex": "" if candidate is None else candidate.get("source_value_hex", ""),
        "source_segment_offset": "" if candidate is None else candidate.get("source_segment_offset", ""),
        "distance_to_gap": "" if candidate is None else candidate.get("distance_to_gap", ""),
        "source_context_hex": "" if candidate is None else candidate.get("source_context_hex", ""),
        "replay_hex": replay.hex(),
        "replay_exact_bytes": str(exact),
        "replay_rule": "emit_from_near_anchor_exact_seed" if candidate is not None else "",
        "verdict": verdict,
    }


def build_reports(
    remaining_rows: list[dict[str, str]],
    candidates_by_key: dict[tuple[str, str, str], list[dict[str, str]]],
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], list[str]]:
    issues: list[str] = []
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in remaining_rows:
        grouped[group_key(row)].append(row)

    guard_rows: list[dict[str, str]] = []
    replay_rows: list[dict[str, str]] = []
    rule_groups: dict[str, dict[str, object]] = {}
    for key, rows in sorted(grouped.items()):
        rows = sorted(rows, key=lambda row: int_field(row, "token_index"))
        candidates = [choose_near_candidate(candidates_by_key.get(row_key(row), [])) for row in rows]
        current_signature = token_signature(rows)
        families = "+".join(sorted({row.get("value_family", "") for row in rows if row.get("value_family", "")}))
        control_gap_values = {int_field(row, "control_gap_bytes", -1) for row in rows}
        control_gap_bytes = control_gap_values.pop() if len(control_gap_values) == 1 else -1
        current_source_plan = source_plan(rows, candidates)
        current_distance_plan = distance_plan(candidates)
        conditions = guard_conditions(
            control_gap_bytes,
            current_signature,
            families,
            "near_anchor_window",
            "exact_seed",
        )
        current_rule_id = rule_id(current_signature, current_source_plan)
        current_replay_rows = [
            replay_row(row, candidate, order)
            for order, (row, candidate) in enumerate(zip(rows, candidates), start=1)
        ]
        replay_rows.extend(current_replay_rows)
        token_bytes = sum(int_field(row, "length") for row in rows)
        replay_exact = sum(int_field(row, "replay_exact_bytes") for row in current_replay_rows)
        guard_matched = bool(rows) and all(candidate is not None for candidate in candidates) and replay_exact == token_bytes
        false_guard_rows = 0 if guard_matched else 1
        guard_rows.append(
            {
                "target_id": key[0],
                "pcx_name": rows[0].get("pcx_name", "") if rows else "",
                "gap_index": key[1],
                "rule_id": current_rule_id,
                "token_signature": current_signature,
                "value_families": families,
                "control_gap_bytes": str(control_gap_bytes),
                "source_plan": current_source_plan,
                "distance_plan": current_distance_plan,
                "guard_conditions": conditions,
                "guard_matched": "1" if guard_matched else "0",
                "guarded_bytes": str(token_bytes if guard_matched else 0),
                "replay_exact_bytes": str(replay_exact),
                "false_guard_rows": str(false_guard_rows),
                "verdict": "near_anchor_source_rule_ready" if guard_matched else "near_anchor_source_rule_rejected",
            }
        )
        group = rule_groups.setdefault(
            current_rule_id,
            {
                "control_gap_bytes": control_gap_bytes,
                "token_signature": current_signature,
                "value_families": families,
                "source_scope": "near_anchor_window",
                "source_transform": "exact_seed",
                "source_plan": current_source_plan,
                "distance_plan": current_distance_plan,
                "guard_conditions": conditions,
                "gap_rows": 0,
                "token_rows": 0,
                "token_bytes": 0,
                "replay_exact_bytes": 0,
                "false_guard_rows": 0,
            },
        )
        group["gap_rows"] = int(group["gap_rows"]) + 1
        group["token_rows"] = int(group["token_rows"]) + len(rows)
        group["token_bytes"] = int(group["token_bytes"]) + token_bytes
        group["replay_exact_bytes"] = int(group["replay_exact_bytes"]) + replay_exact
        group["false_guard_rows"] = int(group["false_guard_rows"]) + false_guard_rows

    rule_rows: list[dict[str, str]] = []
    for current_rule_id, group in sorted(rule_groups.items()):
        token_bytes = int(group["token_bytes"])
        replay_exact = int(group["replay_exact_bytes"])
        false_guard_rows = int(group["false_guard_rows"])
        verdict = "guarded_near_anchor_source_rule_ready"
        next_probe = "promote near-anchor compact-control source rule into structural grammar"
        if false_guard_rows or replay_exact != token_bytes:
            verdict = "guarded_near_anchor_source_rule_partial"
            next_probe = "split near-anchor compact-control source misses"
        rule_rows.append(
            {
                "rule_id": current_rule_id,
                "gap_rows": str(group["gap_rows"]),
                "token_rows": str(group["token_rows"]),
                "token_bytes": str(token_bytes),
                "control_gap_bytes": str(group["control_gap_bytes"]),
                "token_signature": str(group["token_signature"]),
                "value_families": str(group["value_families"]),
                "source_scope": str(group["source_scope"]),
                "source_transform": str(group["source_transform"]),
                "source_plan": str(group["source_plan"]),
                "distance_plan": str(group["distance_plan"]),
                "guard_conditions": str(group["guard_conditions"]),
                "replay_exact_bytes": str(replay_exact),
                "false_guard_rows": str(false_guard_rows),
                "verdict": verdict,
                "next_probe": next_probe,
            }
        )
    return rule_rows, guard_rows, replay_rows, issues


def total_summary(
    remaining_rows: list[dict[str, str]],
    rule_rows: list[dict[str, str]],
    guard_rows: list[dict[str, str]],
    replay_rows: list[dict[str, str]],
    issue_count: int,
) -> dict[str, str]:
    remaining_bytes = sum(int_field(row, "length") for row in remaining_rows)
    near_candidate_rows = [row for row in replay_rows if row.get("source_scope") == "near_anchor_window"]
    replay_exact = sum(int_field(row, "replay_exact_bytes") for row in replay_rows)
    guarded_rows = [row for row in guard_rows if row.get("guard_matched") == "1"]
    false_guard_rows = sum(int_field(row, "false_guard_rows") for row in guard_rows)
    verdict = "frontier80_structural_near_anchor_source_rule_ready"
    next_probe = "promote near-anchor compact-control source rule into structural grammar"
    if issue_count or false_guard_rows or replay_exact != remaining_bytes:
        verdict = "frontier80_structural_near_anchor_source_rule_partial"
        next_probe = "split near-anchor compact-control source misses"
    return {
        "scope": "total",
        "remaining_token_rows": str(len(remaining_rows)),
        "remaining_bytes": str(remaining_bytes),
        "near_candidate_token_rows": str(len(near_candidate_rows)),
        "near_candidate_bytes": str(sum(int_field(row, "length") for row in near_candidate_rows)),
        "guard_rule_rows": str(len(rule_rows)),
        "guarded_gap_rows": str(len(guarded_rows)),
        "guarded_token_rows": str(sum(int_field(row, "token_rows") for row in rule_rows)),
        "guarded_bytes": str(sum(int_field(row, "guarded_bytes") for row in guarded_rows)),
        "exact_seed_rows": str(sum(1 for row in replay_rows if row.get("source_transform") == "exact_seed")),
        "replay_exact_bytes": str(replay_exact),
        "replay_exact_ratio": ratio(replay_exact, remaining_bytes),
        "false_guard_rows": str(false_guard_rows),
        "unresolved_guard_rows": str(len(guard_rows) - len(guarded_rows)),
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
        ("Remaining bytes", summary.get("remaining_bytes", "0")),
        ("Near bytes", summary.get("near_candidate_bytes", "0")),
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
  <div class="muted">Derives exact-seed near-anchor replay guards for remaining compact-control residual tokens.</div>
  <div class="grid">{card_html}</div>
  <section><h2>Outputs</h2>
    <p><a href="{relative_href(output / 'summary.csv', output / 'index.html')}">summary.csv</a> ·
    <a href="{relative_href(output / 'near_anchor_rules.csv', output / 'index.html')}">near_anchor_rules.csv</a> ·
    <a href="{relative_href(output / 'guard_rows.csv', output / 'index.html')}">guard_rows.csv</a> ·
    <a href="{relative_href(output / 'replay_rows.csv', output / 'index.html')}">replay_rows.csv</a></p>
  </section>
  <section><h2>Near-Anchor Rules</h2>{render_table(rule_rows, RULE_FIELDNAMES)}</section>
  <section><h2>Guard Rows</h2>{render_table(guard_rows, GUARD_FIELDNAMES)}</section>
  <section><h2>Replay Rows</h2>{render_table(replay_rows, REPLAY_FIELDNAMES)}</section>
</main>
<script type="application/json" id="near-anchor-source-rule-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> dict[str, str]:
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    remaining_rows = read_csv(args.remaining_tokens)
    candidates_by_key: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in read_csv(args.source_candidates):
        candidates_by_key[row_key(row)].append(row)
    rule_rows, guard_rows, replay_rows, issues = build_reports(remaining_rows, candidates_by_key)
    summary = total_summary(remaining_rows, rule_rows, guard_rows, replay_rows, len(issues))
    write_csv(output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output / "near_anchor_rules.csv", RULE_FIELDNAMES, rule_rows)
    write_csv(output / "guard_rows.csv", GUARD_FIELDNAMES, guard_rows)
    write_csv(output / "replay_rows.csv", REPLAY_FIELDNAMES, replay_rows)
    (output / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""))
    (output / "index.html").write_text(build_html(output, args.title, summary, rule_rows, guard_rows, replay_rows))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Derive near-anchor source rules for remaining compact-control residuals."
    )
    parser.add_argument("--remaining-tokens", type=Path, default=DEFAULT_REMAINING_TOKENS)
    parser.add_argument("--source-candidates", type=Path, default=DEFAULT_SOURCE_CANDIDATES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Structural Near-Anchor Source Rule Probe",
    )
    args = parser.parse_args()
    summary = write_report(args)
    print(f"Remaining bytes: {summary['remaining_bytes']}")
    print(f"Near-anchor bytes: {summary['near_candidate_bytes']}")
    print(f"Replay exact ratio: {summary['replay_exact_ratio']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
