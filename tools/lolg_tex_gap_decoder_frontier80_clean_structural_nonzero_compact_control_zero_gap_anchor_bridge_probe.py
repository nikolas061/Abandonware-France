#!/usr/bin/env python3
"""Profile zero-control-gap residual seeds around structural compact-control anchors."""

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
DEFAULT_CANDIDATES = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_compact_control_residual_value_family_probe/source_candidates.csv"
)
DEFAULT_GAPS = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_compact_control_grammar_validation_probe/gaps.csv"
)
DEFAULT_OUTPUT = Path(
    "output/tex_gap_decoder_frontier80_clean_structural_nonzero_compact_control_zero_gap_anchor_bridge_probe"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "zero_gap_rows",
    "zero_gap_residual_token_rows",
    "zero_gap_residual_bytes",
    "anchor_source_token_rows",
    "anchor_source_bytes",
    "anchor_source_ratio",
    "exact_anchor_seed_rows",
    "before_anchor_rows",
    "after_anchor_rows",
    "unique_anchor_offsets",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

GAP_FIELDNAMES = [
    "target_id",
    "pcx_name",
    "gap_index",
    "previous_token_index",
    "next_token_index",
    "target_gap_bytes",
    "control_gap_bytes",
    "anchor_segment_offset",
    "residual_token_rows",
    "residual_token_bytes",
    "anchor_source_token_rows",
    "anchor_source_bytes",
    "before_anchor_rows",
    "after_anchor_rows",
    "anchor_relative_offsets",
    "source_order_token_indices",
    "verdict",
    "next_probe",
]

ANCHOR_SOURCE_FIELDNAMES = [
    "target_id",
    "pcx_name",
    "gap_index",
    "token_index",
    "token_type",
    "length",
    "target_hex",
    "value_family",
    "anchor_segment_offset",
    "source_scope",
    "source_transform",
    "source_delta",
    "source_value_hex",
    "source_segment_offset",
    "source_anchor_delta",
    "anchor_side",
    "distance_to_gap",
    "source_context_hex",
    "replay_seed_bytes",
    "verdict",
]


def row_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("target_id", ""), row.get("gap_index", ""), row.get("token_index", "")


def gap_key(row: dict[str, str]) -> tuple[str, str]:
    return row.get("target_id", ""), row.get("gap_index", "")


def choose_anchor_candidate(candidates: list[dict[str, str]]) -> dict[str, str] | None:
    if not candidates:
        return None
    scoped = [row for row in candidates if row.get("scope") == "near_anchor_window"]
    if not scoped:
        scoped = [row for row in candidates if row.get("scope") == "full_segment"]
    if not scoped:
        scoped = candidates
    return min(
        scoped,
        key=lambda row: (
            0 if row.get("source_scope", row.get("scope", "")) == "near_anchor_window" else 1,
            0 if row.get("source_transform") in {"exact_seed", "exact_chunk"} else 1,
            abs(int_field(row, "source_delta")),
            int_field(row, "distance_to_gap"),
            int_field(row, "source_segment_offset"),
        ),
    )


def anchor_side(delta: int) -> str:
    if delta < 0:
        return "before_anchor"
    if delta > 0:
        return "after_anchor"
    return "at_anchor"


def make_anchor_source_row(
    residual: dict[str, str],
    gap: dict[str, str],
    candidate: dict[str, str] | None,
) -> dict[str, str]:
    anchor = int_field(gap, "previous_segment_end", -1)
    source_offset = int_field(candidate or {}, "source_segment_offset", -1)
    relative = source_offset - anchor if source_offset >= 0 and anchor >= 0 else 0
    length = int_field(residual, "length")
    source_scope = "" if candidate is None else candidate.get("scope", "")
    transform = "" if candidate is None else candidate.get("source_transform", "")
    verdict = "anchor_seed_ready" if candidate is not None else "missing_anchor_seed"
    return {
        "target_id": residual.get("target_id", ""),
        "pcx_name": residual.get("pcx_name", ""),
        "gap_index": residual.get("gap_index", ""),
        "token_index": residual.get("token_index", ""),
        "token_type": residual.get("token_type", ""),
        "length": residual.get("length", ""),
        "target_hex": residual.get("target_hex", ""),
        "value_family": residual.get("value_family", ""),
        "anchor_segment_offset": "" if anchor < 0 else str(anchor),
        "source_scope": source_scope,
        "source_transform": transform,
        "source_delta": "" if candidate is None else candidate.get("source_delta", ""),
        "source_value_hex": "" if candidate is None else candidate.get("source_value_hex", ""),
        "source_segment_offset": "" if source_offset < 0 else str(source_offset),
        "source_anchor_delta": "" if candidate is None else f"{relative:+d}",
        "anchor_side": "" if candidate is None else anchor_side(relative),
        "distance_to_gap": "" if candidate is None else candidate.get("distance_to_gap", ""),
        "source_context_hex": "" if candidate is None else candidate.get("source_context_hex", ""),
        "replay_seed_bytes": str(length if candidate is not None else 0),
        "verdict": verdict,
    }


def gap_summary_row(
    gap: dict[str, str],
    residual_rows: list[dict[str, str]],
    anchor_rows: list[dict[str, str]],
) -> dict[str, str]:
    ready_rows = [row for row in anchor_rows if row.get("verdict") == "anchor_seed_ready"]
    ready_bytes = sum(int_field(row, "replay_seed_bytes") for row in ready_rows)
    residual_bytes = sum(int_field(row, "length") for row in residual_rows)
    before_rows = [row for row in ready_rows if row.get("anchor_side") == "before_anchor"]
    after_rows = [row for row in ready_rows if row.get("anchor_side") == "after_anchor"]
    source_order = sorted(
        ready_rows,
        key=lambda row: int_field(row, "source_segment_offset"),
    )
    verdict = "zero_gap_anchor_seed_bridge_validated" if ready_bytes == residual_bytes else "zero_gap_anchor_seed_bridge_partial"
    return {
        "target_id": gap.get("target_id", ""),
        "pcx_name": gap.get("pcx_name", ""),
        "gap_index": gap.get("gap_index", ""),
        "previous_token_index": gap.get("previous_token_index", ""),
        "next_token_index": gap.get("next_token_index", ""),
        "target_gap_bytes": gap.get("target_gap_bytes", ""),
        "control_gap_bytes": gap.get("control_gap_bytes", ""),
        "anchor_segment_offset": gap.get("previous_segment_end", ""),
        "residual_token_rows": str(len(residual_rows)),
        "residual_token_bytes": str(residual_bytes),
        "anchor_source_token_rows": str(len(ready_rows)),
        "anchor_source_bytes": str(ready_bytes),
        "before_anchor_rows": str(len(before_rows)),
        "after_anchor_rows": str(len(after_rows)),
        "anchor_relative_offsets": " ".join(row.get("source_anchor_delta", "") for row in ready_rows),
        "source_order_token_indices": " ".join(row.get("token_index", "") for row in source_order),
        "verdict": verdict,
        "next_probe": "derive guarded zero-gap anchor-source replay rule",
    }


def total_summary(gap_rows: list[dict[str, str]], anchor_rows: list[dict[str, str]], issue_count: int) -> dict[str, str]:
    ready_rows = [row for row in anchor_rows if row.get("verdict") == "anchor_seed_ready"]
    residual_bytes = sum(int_field(row, "residual_token_bytes") for row in gap_rows)
    ready_bytes = sum(int_field(row, "replay_seed_bytes") for row in ready_rows)
    offsets = sorted({row.get("source_anchor_delta", "") for row in ready_rows if row.get("source_anchor_delta")})
    verdict = "frontier80_structural_zero_gap_anchor_seed_bridge_validated"
    next_probe = "derive guarded zero-gap anchor-source replay rule"
    if ready_bytes < residual_bytes:
        verdict = "frontier80_structural_zero_gap_anchor_seed_bridge_partial"
        next_probe = "split zero-gap anchor seed misses by source side"
    return {
        "scope": "total",
        "zero_gap_rows": str(len(gap_rows)),
        "zero_gap_residual_token_rows": str(sum(int_field(row, "residual_token_rows") for row in gap_rows)),
        "zero_gap_residual_bytes": str(residual_bytes),
        "anchor_source_token_rows": str(len(ready_rows)),
        "anchor_source_bytes": str(ready_bytes),
        "anchor_source_ratio": ratio(ready_bytes, residual_bytes),
        "exact_anchor_seed_rows": str(
            sum(1 for row in ready_rows if row.get("source_transform") in {"exact_seed", "exact_chunk"})
        ),
        "before_anchor_rows": str(sum(1 for row in ready_rows if row.get("anchor_side") == "before_anchor")),
        "after_anchor_rows": str(sum(1 for row in ready_rows if row.get("anchor_side") == "after_anchor")),
        "unique_anchor_offsets": " ".join(offsets),
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
    gap_rows: list[dict[str, str]],
    anchor_rows: list[dict[str, str]],
) -> str:
    payload = {"summary": summary, "gaps": gap_rows, "anchor_sources": anchor_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    cards = [
        ("Zero-gap bytes", summary.get("zero_gap_residual_bytes", "0")),
        ("Anchor bytes", summary.get("anchor_source_bytes", "0")),
        ("Ratio", summary.get("anchor_source_ratio", "0")),
        ("Offsets", summary.get("unique_anchor_offsets", "")),
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
  <div class="muted">Profiles seed sources around zero-byte compact-control gaps.</div>
  <div class="grid">{card_html}</div>
  <section><h2>Outputs</h2>
    <p><a href="{relative_href(output / 'summary.csv', output / 'index.html')}">summary.csv</a> ·
    <a href="{relative_href(output / 'zero_gap_rows.csv', output / 'index.html')}">zero_gap_rows.csv</a> ·
    <a href="{relative_href(output / 'anchor_sources.csv', output / 'index.html')}">anchor_sources.csv</a></p>
  </section>
  <section><h2>Zero Gaps</h2>{render_table(gap_rows, GAP_FIELDNAMES)}</section>
  <section><h2>Anchor Sources</h2>{render_table(anchor_rows, ANCHOR_SOURCE_FIELDNAMES)}</section>
</main>
<script type="application/json" id="zero-gap-anchor-bridge-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> dict[str, str]:
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    residual_rows = [
        row for row in read_csv(args.residuals) if row.get("control_gap_status") == "zero_control_gap"
    ]
    candidate_groups: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in read_csv(args.candidates):
        candidate_groups[row_key(row)].append(row)
    gaps_by_key = {gap_key(row): row for row in read_csv(args.gaps)}
    residuals_by_gap: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in residual_rows:
        residuals_by_gap[gap_key(row)].append(row)

    anchor_rows: list[dict[str, str]] = []
    gap_rows: list[dict[str, str]] = []
    for key, rows in sorted(residuals_by_gap.items()):
        gap = gaps_by_key.get(key)
        if gap is None:
            issues.append(f"{key[0]}:g{key[1]}:missing_gap_row")
            continue
        current_anchor_rows: list[dict[str, str]] = []
        for residual in sorted(rows, key=lambda row: int_field(row, "token_index")):
            candidate = choose_anchor_candidate(candidate_groups.get(row_key(residual), []))
            anchor_row = make_anchor_source_row(residual, gap, candidate)
            current_anchor_rows.append(anchor_row)
            anchor_rows.append(anchor_row)
            if candidate is None:
                issues.append(
                    f"{residual.get('target_id', '')}:g{residual.get('gap_index', '')}:"
                    f"token{residual.get('token_index', '')}:missing_anchor_candidate"
                )
        gap_rows.append(gap_summary_row(gap, rows, current_anchor_rows))

    summary = total_summary(gap_rows, anchor_rows, len(issues))
    write_csv(output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output / "zero_gap_rows.csv", GAP_FIELDNAMES, gap_rows)
    write_csv(output / "anchor_sources.csv", ANCHOR_SOURCE_FIELDNAMES, anchor_rows)
    (output / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""))
    (output / "index.html").write_text(build_html(output, args.title, summary, gap_rows, anchor_rows))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Profile structural compact-control zero-gap residual anchor sources."
    )
    parser.add_argument("--residuals", type=Path, default=DEFAULT_RESIDUALS)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--gaps", type=Path, default=DEFAULT_GAPS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Structural Zero-Gap Anchor Bridge Probe",
    )
    args = parser.parse_args()
    summary = write_report(args)
    print(f"Zero-gap bytes: {summary['zero_gap_residual_bytes']}")
    print(f"Anchor source bytes: {summary['anchor_source_bytes']}")
    print(f"Anchor source ratio: {summary['anchor_source_ratio']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
