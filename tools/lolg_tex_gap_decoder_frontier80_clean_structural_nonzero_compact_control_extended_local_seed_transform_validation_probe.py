#!/usr/bin/env python3
"""Validate extended local seed transforms for promoted compact-control residuals."""

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
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_compact_control_zero_gap_anchor_promoted_grammar_probe/residual_tokens.csv"
)
DEFAULT_RESIDUAL_FAMILY_TOKENS = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_compact_control_residual_value_family_probe/residual_tokens.csv"
)
DEFAULT_SOURCE_CANDIDATES = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_compact_control_residual_value_family_probe/source_candidates.csv"
)
DEFAULT_OUTPUT = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_compact_control_extended_local_seed_transform_validation_probe"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "post_zero_gap_residual_token_rows",
    "post_zero_gap_residual_bytes",
    "local_candidate_token_rows",
    "local_candidate_bytes",
    "validated_token_rows",
    "validated_bytes",
    "promotion_ready_bytes",
    "validated_exact_ratio",
    "validated_false_bytes",
    "remaining_token_rows",
    "remaining_bytes",
    "family_rows",
    "transform_rows",
    "max_abs_delta",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

VALIDATION_FIELDNAMES = [
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
    "value_family",
    "value_classes",
    "values_hex",
    "control_gap_bytes",
    "source_transform",
    "source_delta",
    "source_value_hex",
    "source_offset",
    "source_segment_offset",
    "source_occurrences",
    "distance_to_gap",
    "source_context_hex",
    "replay_hex",
    "replay_exact_bytes",
    "validated_bytes",
    "verdict",
    "next_probe",
]

FAMILY_FIELDNAMES = [
    "value_family",
    "token_rows",
    "token_bytes",
    "local_candidate_rows",
    "local_candidate_bytes",
    "validated_rows",
    "validated_bytes",
    "remaining_rows",
    "remaining_bytes",
    "transforms",
    "values_hex",
    "sample_target_id",
    "sample_token_index",
    "verdict",
    "next_probe",
]

TRANSFORM_FIELDNAMES = [
    "source_transform",
    "source_delta",
    "token_rows",
    "token_bytes",
    "validated_rows",
    "validated_bytes",
    "false_bytes",
    "families",
    "sample_target_id",
    "sample_token_index",
    "verdict",
]


def row_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("target_id", ""), row.get("gap_index", ""), row.get("token_index", "")


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


def transform_name(delta: int) -> str:
    if delta == 0:
        return "exact_seed"
    if delta > 0:
        return f"plus{delta}_seed"
    return f"minus{abs(delta)}_seed"


def replay_from_candidate(
    token_type: str,
    length: int,
    source_value: int,
    source_delta: int,
    target: bytes,
    source_transform: str,
) -> bytes:
    if length <= 0:
        return b""
    if source_transform == "exact_chunk":
        return target
    seed = (source_value + source_delta) & 0xFF
    if token_type == "literal" and length == 1:
        return bytes([seed])
    if token_type == "repeat":
        return bytes([seed]) * length
    return b""


def choose_local_candidate(rows: list[dict[str, str]]) -> dict[str, str] | None:
    local_rows = [row for row in rows if row.get("scope") == "local_control_gap"]
    if not local_rows:
        return None
    return min(
        local_rows,
        key=lambda row: (
            0 if row.get("source_transform") == "exact_chunk" else 1,
            abs(int_field(row, "source_delta")),
            int_field(row, "distance_to_gap"),
            int_field(row, "source_segment_offset"),
        ),
    )


def metadata_for(row: dict[str, str], metadata: dict[tuple[str, str, str], dict[str, str]]) -> dict[str, str]:
    return metadata.get(row_key(row), {})


def validation_row(
    row: dict[str, str],
    candidate: dict[str, str] | None,
    metadata: dict[str, str],
) -> dict[str, str]:
    target = parse_hex_bytes(row.get("target_hex", ""))
    length = int_field(row, "length", len(target))
    token_type = row.get("token_type", "")
    replay = b""
    exact = 0
    validated = 0
    verdict = "no_local_candidate"
    next_probe = "derive near-anchor compact-control source rule"
    source_value = None
    source_delta = 0
    if candidate is not None:
        source_value = parse_hex_byte(candidate.get("source_value_hex", ""))
        source_delta = int_field(candidate, "source_delta")
        if source_value is not None:
            replay = replay_from_candidate(
                token_type,
                length,
                source_value,
                source_delta,
                target,
                candidate.get("source_transform", ""),
            )
            exact = sum(1 for left, right in zip(replay, target) if left == right)
            if replay == target:
                validated = len(target)
                verdict = "extended_local_seed_transform_validated"
                next_probe = "promote extended local seed transforms behind compact-control guard"
            else:
                verdict = "extended_local_seed_transform_false"
                next_probe = "split extended local seed transform false positives"
    return {
        "target_id": row.get("target_id", ""),
        "rank": row.get("rank", ""),
        "pcx_name": row.get("pcx_name", ""),
        "frontier_id": row.get("frontier_id", ""),
        "span_index": row.get("span_index", ""),
        "gap_index": row.get("gap_index", ""),
        "token_index": row.get("token_index", ""),
        "token_type": token_type,
        "run_offset_start": row.get("run_offset_start", ""),
        "run_offset_end": row.get("run_offset_end", ""),
        "length": str(length),
        "target_hex": row.get("target_hex", ""),
        "value_family": metadata.get("value_family", ""),
        "value_classes": metadata.get("value_classes", ""),
        "values_hex": metadata.get("values_hex", ""),
        "control_gap_bytes": metadata.get("control_gap_bytes", ""),
        "source_transform": "" if candidate is None else candidate.get("source_transform", ""),
        "source_delta": "" if candidate is None else candidate.get("source_delta", ""),
        "source_value_hex": "" if source_value is None else f"0x{source_value:02x}",
        "source_offset": "" if candidate is None else candidate.get("source_offset", ""),
        "source_segment_offset": "" if candidate is None else candidate.get("source_segment_offset", ""),
        "source_occurrences": "" if candidate is None else candidate.get("source_occurrences", ""),
        "distance_to_gap": "" if candidate is None else candidate.get("distance_to_gap", ""),
        "source_context_hex": "" if candidate is None else candidate.get("source_context_hex", ""),
        "replay_hex": replay.hex(),
        "replay_exact_bytes": str(exact),
        "validated_bytes": str(validated),
        "verdict": verdict,
        "next_probe": next_probe,
    }


def family_rows(validation_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in validation_rows:
        grouped[row.get("value_family", "")].append(row)
    rows: list[dict[str, str]] = []
    for family, group in sorted(grouped.items()):
        token_bytes = sum(int_field(row, "length") for row in group)
        candidate_rows = [row for row in group if row.get("source_transform")]
        validated_rows = [row for row in group if row.get("verdict") == "extended_local_seed_transform_validated"]
        validated_bytes = sum(int_field(row, "validated_bytes") for row in validated_rows)
        remaining_bytes = token_bytes - validated_bytes
        verdict = "extended_local_seed_transform_family_validated" if remaining_bytes == 0 else "extended_local_seed_transform_family_partial"
        next_probe = (
            "promote extended local seed transforms behind compact-control guard"
            if remaining_bytes == 0
            else "derive near-anchor compact-control source rule"
        )
        sample = group[0]
        rows.append(
            {
                "value_family": family,
                "token_rows": str(len(group)),
                "token_bytes": str(token_bytes),
                "local_candidate_rows": str(len(candidate_rows)),
                "local_candidate_bytes": str(sum(int_field(row, "length") for row in candidate_rows)),
                "validated_rows": str(len(validated_rows)),
                "validated_bytes": str(validated_bytes),
                "remaining_rows": str(sum(1 for row in group if row.get("verdict") != "extended_local_seed_transform_validated")),
                "remaining_bytes": str(remaining_bytes),
                "transforms": " ".join(
                    sorted(
                        {
                            f"{row.get('source_transform', '')}:{row.get('source_delta', '')}"
                            for row in validated_rows
                            if row.get("source_transform")
                        }
                    )
                ),
                "values_hex": " ".join(sorted({row.get("values_hex", "") for row in group if row.get("values_hex")})),
                "sample_target_id": sample.get("target_id", ""),
                "sample_token_index": sample.get("token_index", ""),
                "verdict": verdict,
                "next_probe": next_probe,
            }
        )
    return rows


def transform_rows(validation_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in validation_rows:
        if row.get("source_transform"):
            grouped[(row.get("source_transform", ""), row.get("source_delta", ""))].append(row)
    rows: list[dict[str, str]] = []
    for (transform, delta), group in sorted(grouped.items(), key=lambda item: (int_field({"d": item[0][1]}, "d"), item[0][0])):
        token_bytes = sum(int_field(row, "length") for row in group)
        validated = [row for row in group if row.get("verdict") == "extended_local_seed_transform_validated"]
        validated_bytes = sum(int_field(row, "validated_bytes") for row in validated)
        false_bytes = token_bytes - validated_bytes
        sample = group[0]
        rows.append(
            {
                "source_transform": transform,
                "source_delta": delta,
                "token_rows": str(len(group)),
                "token_bytes": str(token_bytes),
                "validated_rows": str(len(validated)),
                "validated_bytes": str(validated_bytes),
                "false_bytes": str(false_bytes),
                "families": " ".join(sorted({row.get("value_family", "") for row in group})),
                "sample_target_id": sample.get("target_id", ""),
                "sample_token_index": sample.get("token_index", ""),
                "verdict": "extended_local_seed_transform_ready" if false_bytes == 0 else "extended_local_seed_transform_rejected",
            }
        )
    return rows


def total_summary(
    validation_rows: list[dict[str, str]],
    family_summary_rows: list[dict[str, str]],
    transform_summary_rows: list[dict[str, str]],
    issue_count: int,
) -> dict[str, str]:
    token_bytes = sum(int_field(row, "length") for row in validation_rows)
    candidate_rows = [row for row in validation_rows if row.get("source_transform")]
    validated_rows = [row for row in validation_rows if row.get("verdict") == "extended_local_seed_transform_validated"]
    validated_bytes = sum(int_field(row, "validated_bytes") for row in validated_rows)
    candidate_bytes = sum(int_field(row, "length") for row in candidate_rows)
    false_bytes = candidate_bytes - validated_bytes
    remaining_rows = [row for row in validation_rows if row.get("verdict") != "extended_local_seed_transform_validated"]
    remaining_bytes = token_bytes - validated_bytes
    max_abs_delta = max([abs(int_field(row, "source_delta")) for row in candidate_rows] or [0])
    verdict = "frontier80_structural_extended_local_seed_transforms_validated"
    next_probe = "derive near-anchor compact-control source rule"
    if issue_count:
        verdict = "frontier80_structural_extended_local_seed_transforms_issues"
        next_probe = "review extended local seed transform inputs"
    elif false_bytes:
        verdict = "frontier80_structural_extended_local_seed_transforms_rejected"
        next_probe = "split extended local seed transform false positives"
    elif validated_bytes == 0:
        verdict = "frontier80_structural_extended_local_seed_transforms_empty"
        next_probe = "derive near-anchor compact-control source rule"
    return {
        "scope": "total",
        "post_zero_gap_residual_token_rows": str(len(validation_rows)),
        "post_zero_gap_residual_bytes": str(token_bytes),
        "local_candidate_token_rows": str(len(candidate_rows)),
        "local_candidate_bytes": str(candidate_bytes),
        "validated_token_rows": str(len(validated_rows)),
        "validated_bytes": str(validated_bytes),
        "promotion_ready_bytes": str(validated_bytes if false_bytes == 0 and issue_count == 0 else 0),
        "validated_exact_ratio": ratio(validated_bytes, candidate_bytes),
        "validated_false_bytes": str(false_bytes),
        "remaining_token_rows": str(len(remaining_rows)),
        "remaining_bytes": str(remaining_bytes),
        "family_rows": str(len(family_summary_rows)),
        "transform_rows": str(len(transform_summary_rows)),
        "max_abs_delta": str(max_abs_delta),
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
    validation_rows: list[dict[str, str]],
    family_summary_rows: list[dict[str, str]],
    transform_summary_rows: list[dict[str, str]],
    remaining_rows: list[dict[str, str]],
) -> str:
    payload = {
        "summary": summary,
        "validation": validation_rows,
        "families": family_summary_rows,
        "transforms": transform_summary_rows,
        "remaining": remaining_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    cards = [
        ("Residual bytes", summary.get("post_zero_gap_residual_bytes", "0")),
        ("Validated bytes", summary.get("validated_bytes", "0")),
        ("False bytes", summary.get("validated_false_bytes", "0")),
        ("Remaining bytes", summary.get("remaining_bytes", "0")),
        ("Max delta", summary.get("max_abs_delta", "0")),
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
  <div class="muted">Validates local compact-control seed transforms beyond exact/+1/-1 after zero-gap anchor promotion.</div>
  <div class="grid">{card_html}</div>
  <section><h2>Outputs</h2>
    <p><a href="{relative_href(output / 'summary.csv', output / 'index.html')}">summary.csv</a> ·
    <a href="{relative_href(output / 'validation_rows.csv', output / 'index.html')}">validation_rows.csv</a> ·
    <a href="{relative_href(output / 'families.csv', output / 'index.html')}">families.csv</a> ·
    <a href="{relative_href(output / 'transforms.csv', output / 'index.html')}">transforms.csv</a> ·
    <a href="{relative_href(output / 'remaining_tokens.csv', output / 'index.html')}">remaining_tokens.csv</a></p>
  </section>
  <section><h2>Transforms</h2>{render_table(transform_summary_rows, TRANSFORM_FIELDNAMES)}</section>
  <section><h2>Families</h2>{render_table(family_summary_rows, FAMILY_FIELDNAMES)}</section>
  <section><h2>Remaining Tokens</h2>{render_table(remaining_rows, VALIDATION_FIELDNAMES)}</section>
  <section><h2>Validation Rows</h2>{render_table(validation_rows, VALIDATION_FIELDNAMES)}</section>
</main>
<script type="application/json" id="extended-local-seed-transform-validation-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> dict[str, str]:
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    residual_rows = read_csv(args.residuals)
    metadata = {row_key(row): row for row in read_csv(args.residual_family_tokens)}
    candidates_by_key: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in read_csv(args.source_candidates):
        candidates_by_key[row_key(row)].append(row)

    validation_rows: list[dict[str, str]] = []
    for row in residual_rows:
        key = row_key(row)
        candidate = choose_local_candidate(candidates_by_key.get(key, []))
        validation_rows.append(validation_row(row, candidate, metadata_for(row, metadata)))

    family_summary_rows = family_rows(validation_rows)
    transform_summary_rows = transform_rows(validation_rows)
    remaining_rows = [row for row in validation_rows if row.get("verdict") != "extended_local_seed_transform_validated"]
    summary = total_summary(validation_rows, family_summary_rows, transform_summary_rows, len(issues))
    write_csv(output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output / "validation_rows.csv", VALIDATION_FIELDNAMES, validation_rows)
    write_csv(output / "families.csv", FAMILY_FIELDNAMES, family_summary_rows)
    write_csv(output / "transforms.csv", TRANSFORM_FIELDNAMES, transform_summary_rows)
    write_csv(output / "remaining_tokens.csv", VALIDATION_FIELDNAMES, remaining_rows)
    (output / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""))
    (output / "index.html").write_text(
        build_html(output, args.title, summary, validation_rows, family_summary_rows, transform_summary_rows, remaining_rows)
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate extended local seed transforms for promoted compact-control residuals."
    )
    parser.add_argument("--residuals", type=Path, default=DEFAULT_RESIDUALS)
    parser.add_argument("--residual-family-tokens", type=Path, default=DEFAULT_RESIDUAL_FAMILY_TOKENS)
    parser.add_argument("--source-candidates", type=Path, default=DEFAULT_SOURCE_CANDIDATES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Structural Extended Local Seed Transform Validation",
    )
    args = parser.parse_args()
    summary = write_report(args)
    print(f"Post zero-gap residual bytes: {summary['post_zero_gap_residual_bytes']}")
    print(f"Validated bytes: {summary['validated_bytes']}")
    print(f"Remaining bytes: {summary['remaining_bytes']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
