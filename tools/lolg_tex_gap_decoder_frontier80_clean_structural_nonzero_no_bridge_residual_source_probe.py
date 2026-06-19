#!/usr/bin/env python3
"""Profile non-segment and run-local sources for residual no-bridge spans."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

from lolg_tex_gap_opcode_probe import relative_href, write_csv
from lolg_tex_gap_decoder_frontier80_clean_structural_nonzero_producer_probe import (
    DEFAULT_CLEAN_FIXTURES,
    DEFAULT_MANIFEST,
    load_target_payloads,
    ratio,
    read_csv,
)
from lolg_tex_gap_decoder_frontier80_clean_structural_nonzero_rle_delta_parser_probe import (
    choose_tokens,
    dominant_class,
    token_delta_signature,
)
from lolg_tex_gap_decoder_frontier80_clean_structural_nonzero_compact_control_grammar_probe import (
    int_field,
)


DEFAULT_INTEGRATED_TARGETS = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_compact_control_integrated_replay_probe/targets.csv"
)
DEFAULT_ANCHORS = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_no_bridge_anchor_probe/anchors.csv"
)
DEFAULT_WEAK_GAPS = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_no_bridge_anchor_probe/gaps.csv"
)
DEFAULT_WEAK_GAP_PROMOTED_SUMMARY = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_no_bridge_weak_gap_promoted_replay_probe/summary.csv"
)
DEFAULT_OUTPUT = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_no_bridge_residual_source_probe"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "selected_target_runs",
    "selected_target_bytes",
    "post_promoted_integrated_target_bytes",
    "post_promoted_integrated_target_ratio",
    "residual_target_runs",
    "residual_spans",
    "residual_bytes",
    "segment_exact_spans",
    "segment_exact_bytes",
    "control_exact_spans",
    "control_exact_bytes",
    "fragment_exact_spans",
    "fragment_exact_bytes",
    "best_segment_subspan_bytes",
    "best_control_subspan_bytes",
    "best_fragment_subspan_bytes",
    "source_candidate_rows",
    "source_candidate_bytes",
    "token_rows",
    "repeat_tokens",
    "repeat_bytes",
    "delta_tokens",
    "delta_bytes",
    "literal_tokens",
    "literal_bytes",
    "generated_bytes",
    "generated_ratio",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

SPAN_FIELDNAMES = [
    "target_id",
    "rank",
    "pcx_name",
    "frontier_id",
    "span_index",
    "residual_index",
    "run_offset_start",
    "run_offset_end",
    "length",
    "head_hex",
    "tail_hex",
    "segment_exact_offset",
    "control_exact_offset",
    "fragment_exact_offset",
    "best_segment_length",
    "best_segment_offset",
    "best_control_length",
    "best_control_offset",
    "best_fragment_length",
    "best_fragment_offset",
    "token_rows",
    "repeat_bytes",
    "delta_bytes",
    "literal_bytes",
    "generated_bytes",
    "token_signature",
    "verdict",
    "next_probe",
]

SOURCE_FIELDNAMES = [
    "target_id",
    "residual_index",
    "source_name",
    "source_offset",
    "target_offset_start",
    "target_offset_end",
    "length",
    "source_kind",
    "source_hex",
    "guard",
]

TOKEN_FIELDNAMES = [
    "target_id",
    "residual_index",
    "token_index",
    "token_type",
    "residual_offset_start",
    "residual_offset_end",
    "run_offset_start",
    "run_offset_end",
    "length",
    "seed_hex",
    "repeat_value_hex",
    "delta_signature",
    "generated_bytes",
    "dominant_value_class",
    "head_hex",
    "tail_hex",
]


def hex_byte(value: int) -> str:
    return f"0x{value:02x}"


def no_bridge_targets(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [row for row in rows if row.get("verdict") == "no_bridge_anchor"]


def covered_intervals(
    anchors: list[dict[str, str]],
    weak_gaps: list[dict[str, str]],
) -> dict[str, list[tuple[int, int]]]:
    covered: dict[str, list[tuple[int, int]]] = {}
    for row in anchors:
        start = int_field(row, "run_offset_start", -1)
        end = int_field(row, "run_offset_end", -1)
        if 0 <= start < end:
            covered.setdefault(row.get("target_id", ""), []).append((start, end))
    for row in weak_gaps:
        start = int_field(row, "previous_run_offset_end", -1)
        end = int_field(row, "next_run_offset_start", -1)
        if 0 <= start < end and int_field(row, "run_gap_bytes") > 0:
            covered.setdefault(row.get("target_id", ""), []).append((start, end))
    return covered


def residual_ranges(length: int, intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    cursor = 0
    for start, end in sorted(intervals):
        if cursor < start:
            ranges.append((cursor, start))
        cursor = max(cursor, end)
    if cursor < length:
        ranges.append((cursor, length))
    return ranges


def longest_subchunk(source: bytes, chunk: bytes, *, min_length: int) -> tuple[int, int, int, int]:
    for length in range(len(chunk), min_length - 1, -1):
        for target_start in range(0, len(chunk) - length + 1):
            sub = chunk[target_start : target_start + length]
            source_offset = source.find(sub)
            if source_offset >= 0:
                return target_start, target_start + length, source_offset, length
    return -1, -1, -1, 0


def build_tokens(target_id: str, residual_index: int, chunk: bytes, run_start: int, args: argparse.Namespace) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for token_index, (token_type, start, end) in enumerate(
        choose_tokens(chunk, min_repeat=args.min_repeat, min_delta=args.min_delta, max_delta=args.max_delta),
        start=1,
    ):
        token = chunk[start:end]
        generated = len(token) - 1 if token_type in {"repeat", "delta"} else 0
        rows.append(
            {
                "target_id": target_id,
                "residual_index": str(residual_index),
                "token_index": str(token_index),
                "token_type": token_type,
                "residual_offset_start": str(start),
                "residual_offset_end": str(end),
                "run_offset_start": str(run_start + start),
                "run_offset_end": str(run_start + end),
                "length": str(len(token)),
                "seed_hex": hex_byte(token[0]) if token else "",
                "repeat_value_hex": hex_byte(token[0]) if token_type == "repeat" and token else "",
                "delta_signature": token_delta_signature(token) if token_type == "delta" else "",
                "generated_bytes": str(generated),
                "dominant_value_class": dominant_class(token),
                "head_hex": token[:16].hex(),
                "tail_hex": token[-16:].hex(),
            }
        )
    return rows


def token_signature(token_rows: list[dict[str, str]]) -> str:
    return ".".join(f"{row.get('token_type', '')[0].lower()}{row.get('length', '0')}" for row in token_rows[:24])


def source_candidate_rows(
    target_id: str,
    residual_index: int,
    chunk: bytes,
    candidates: list[tuple[str, tuple[int, int, int, int]]],
    *,
    min_length: int,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for source_name, (target_start, target_end, source_offset, length) in candidates:
        if length < min_length:
            continue
        source_kind = "full_residual_exact" if length == len(chunk) and target_start == 0 else "partial_residual_exact"
        rows.append(
            {
                "target_id": target_id,
                "residual_index": str(residual_index),
                "source_name": source_name,
                "source_offset": str(source_offset),
                "target_offset_start": str(target_start),
                "target_offset_end": str(target_end),
                "length": str(length),
                "source_kind": source_kind,
                "source_hex": chunk[target_start:target_end].hex(),
                "guard": f"{source_name}_longest_subchunk_ge{min_length}",
            }
        )
    return rows


def build_report(args: argparse.Namespace) -> dict[str, str]:
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    integrated_targets = no_bridge_targets(read_csv(args.integrated_targets))
    payloads = load_target_payloads(integrated_targets, read_csv(args.manifest), read_csv(args.clean_fixtures), issues)
    weak_summary_rows = read_csv(args.weak_gap_promoted_summary)
    weak_summary = weak_summary_rows[0] if weak_summary_rows else {}
    covered = covered_intervals(read_csv(args.anchors), read_csv(args.weak_gaps))

    span_rows: list[dict[str, str]] = []
    source_rows: list[dict[str, str]] = []
    token_rows: list[dict[str, str]] = []
    for payload in payloads:
        target = payload.get("target", {})
        data = payload.get("data", b"")
        segment = payload.get("segment", b"")
        control = payload.get("control", b"")
        fragment = payload.get("fragment", b"")
        if not isinstance(target, dict) or not isinstance(data, bytes):
            continue
        if not isinstance(segment, bytes):
            segment = b""
        if not isinstance(control, bytes):
            control = b""
        if not isinstance(fragment, bytes):
            fragment = b""
        target_id = target.get("target_id", "")
        for residual_index, (start, end) in enumerate(residual_ranges(len(data), covered.get(target_id, [])), start=1):
            chunk = data[start:end]
            segment_match = segment.find(chunk)
            control_match = control.find(chunk)
            fragment_match = fragment.find(chunk)
            best_segment = longest_subchunk(segment, chunk, min_length=args.min_source_length)
            best_control = longest_subchunk(control, chunk, min_length=args.min_source_length)
            best_fragment = longest_subchunk(fragment, chunk, min_length=args.min_source_length)
            span_tokens = build_tokens(target_id, residual_index, chunk, start, args)
            repeat_bytes = sum(int_field(row, "length") for row in span_tokens if row.get("token_type") == "repeat")
            delta_bytes = sum(int_field(row, "length") for row in span_tokens if row.get("token_type") == "delta")
            literal_bytes = sum(int_field(row, "length") for row in span_tokens if row.get("token_type") == "literal")
            generated = sum(int_field(row, "generated_bytes") for row in span_tokens)
            if control_match >= 0 or fragment_match >= 0:
                verdict = "non_segment_full_source_candidate"
                next_probe = "promote exact non-segment residual sources"
            elif best_control[3] >= args.min_source_length or best_fragment[3] >= args.min_source_length:
                verdict = "non_segment_partial_source_candidate"
                next_probe = "review partial non-segment residual source candidates"
            else:
                verdict = "run_local_residual_grammar_candidate"
                next_probe = "derive run-local residual grammar for remaining no-bridge spans"
            span_rows.append(
                {
                    "target_id": target_id,
                    "rank": target.get("rank", ""),
                    "pcx_name": target.get("pcx_name", ""),
                    "frontier_id": target.get("frontier_id", ""),
                    "span_index": target.get("span_index", ""),
                    "residual_index": str(residual_index),
                    "run_offset_start": str(start),
                    "run_offset_end": str(end),
                    "length": str(len(chunk)),
                    "head_hex": chunk[:16].hex(),
                    "tail_hex": chunk[-16:].hex(),
                    "segment_exact_offset": "" if segment_match < 0 else str(segment_match),
                    "control_exact_offset": "" if control_match < 0 else str(control_match),
                    "fragment_exact_offset": "" if fragment_match < 0 else str(fragment_match),
                    "best_segment_length": str(best_segment[3]),
                    "best_segment_offset": "" if best_segment[2] < 0 else str(best_segment[2]),
                    "best_control_length": str(best_control[3]),
                    "best_control_offset": "" if best_control[2] < 0 else str(best_control[2]),
                    "best_fragment_length": str(best_fragment[3]),
                    "best_fragment_offset": "" if best_fragment[2] < 0 else str(best_fragment[2]),
                    "token_rows": str(len(span_tokens)),
                    "repeat_bytes": str(repeat_bytes),
                    "delta_bytes": str(delta_bytes),
                    "literal_bytes": str(literal_bytes),
                    "generated_bytes": str(generated),
                    "token_signature": token_signature(span_tokens),
                    "verdict": verdict,
                    "next_probe": next_probe,
                }
            )
            source_rows.extend(
                source_candidate_rows(
                    target_id,
                    residual_index,
                    chunk,
                    [("segment", best_segment), ("control", best_control), ("fragment", best_fragment)],
                    min_length=args.min_source_length,
                )
            )
            token_rows.extend(span_tokens)

    residual_bytes = sum(int_field(row, "length") for row in span_rows)
    repeat_rows = [row for row in token_rows if row.get("token_type") == "repeat"]
    delta_rows = [row for row in token_rows if row.get("token_type") == "delta"]
    literal_rows = [row for row in token_rows if row.get("token_type") == "literal"]
    control_exact = [row for row in span_rows if row.get("control_exact_offset", "") != ""]
    fragment_exact = [row for row in span_rows if row.get("fragment_exact_offset", "") != ""]
    segment_exact = [row for row in span_rows if row.get("segment_exact_offset", "") != ""]
    nonsegment_exact_bytes = sum(int_field(row, "length") for row in control_exact) + sum(
        int_field(row, "length") for row in fragment_exact
    )
    verdict = "frontier80_structural_no_bridge_residual_sources_profiled"
    next_probe = "derive run-local residual grammar for remaining no-bridge spans"
    if nonsegment_exact_bytes >= max(1, residual_bytes // 10):
        next_probe = "promote exact non-segment residual sources"
    summary = {
        "scope": "total",
        "selected_target_runs": weak_summary.get("selected_target_runs", "0"),
        "selected_target_bytes": weak_summary.get("selected_target_bytes", "0"),
        "post_promoted_integrated_target_bytes": weak_summary.get("post_promoted_integrated_target_bytes", "0"),
        "post_promoted_integrated_target_ratio": weak_summary.get("post_promoted_integrated_target_ratio", "0"),
        "residual_target_runs": str(
            len({row.get("target_id", "") for row in span_rows if int_field(row, "length") > 0})
        ),
        "residual_spans": str(len(span_rows)),
        "residual_bytes": str(residual_bytes),
        "segment_exact_spans": str(len(segment_exact)),
        "segment_exact_bytes": str(sum(int_field(row, "length") for row in segment_exact)),
        "control_exact_spans": str(len(control_exact)),
        "control_exact_bytes": str(sum(int_field(row, "length") for row in control_exact)),
        "fragment_exact_spans": str(len(fragment_exact)),
        "fragment_exact_bytes": str(sum(int_field(row, "length") for row in fragment_exact)),
        "best_segment_subspan_bytes": str(sum(int_field(row, "best_segment_length") for row in span_rows)),
        "best_control_subspan_bytes": str(sum(int_field(row, "best_control_length") for row in span_rows)),
        "best_fragment_subspan_bytes": str(sum(int_field(row, "best_fragment_length") for row in span_rows)),
        "source_candidate_rows": str(len(source_rows)),
        "source_candidate_bytes": str(sum(int_field(row, "length") for row in source_rows)),
        "token_rows": str(len(token_rows)),
        "repeat_tokens": str(len(repeat_rows)),
        "repeat_bytes": str(sum(int_field(row, "length") for row in repeat_rows)),
        "delta_tokens": str(len(delta_rows)),
        "delta_bytes": str(sum(int_field(row, "length") for row in delta_rows)),
        "literal_tokens": str(len(literal_rows)),
        "literal_bytes": str(sum(int_field(row, "length") for row in literal_rows)),
        "generated_bytes": str(sum(int_field(row, "generated_bytes") for row in token_rows)),
        "generated_ratio": ratio(sum(int_field(row, "generated_bytes") for row in token_rows), residual_bytes),
        "issue_rows": str(len(issues)),
        "review_verdict": verdict,
        "next_probe": next_probe,
    }
    write_csv(output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output / "residual_spans.csv", SPAN_FIELDNAMES, span_rows)
    write_csv(output / "source_candidates.csv", SOURCE_FIELDNAMES, source_rows)
    write_csv(output / "tokens.csv", TOKEN_FIELDNAMES, token_rows)
    (output / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""))
    (output / "index.html").write_text(build_html(output, args.title, summary, span_rows, source_rows, token_rows))
    return summary


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
    span_rows: list[dict[str, str]],
    source_rows: list[dict[str, str]],
    token_rows: list[dict[str, str]],
) -> str:
    payload = {"summary": summary, "spans": span_rows, "sources": source_rows, "tokens": token_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    cards = [
        ("Residual bytes", summary.get("residual_bytes", "0")),
        ("Control exact", summary.get("control_exact_bytes", "0")),
        ("Fragment exact", summary.get("fragment_exact_bytes", "0")),
        ("Generated", summary.get("generated_bytes", "0")),
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
  <div class="muted">Profiles residual no-bridge spans after anchor and weak-gap promotion.</div>
  <div class="grid">{card_html}</div>
  <section><h2>Outputs</h2>
    <p><a href="{relative_href(output / 'summary.csv', output / 'index.html')}">summary.csv</a> ·
    <a href="{relative_href(output / 'residual_spans.csv', output / 'index.html')}">residual_spans.csv</a> ·
    <a href="{relative_href(output / 'source_candidates.csv', output / 'index.html')}">source_candidates.csv</a> ·
    <a href="{relative_href(output / 'tokens.csv', output / 'index.html')}">tokens.csv</a></p>
  </section>
  <section><h2>Residual Spans</h2>{render_table(span_rows, SPAN_FIELDNAMES)}</section>
  <section><h2>Source Candidates</h2>{render_table(source_rows, SOURCE_FIELDNAMES)}</section>
  <section><h2>Tokens</h2>{render_table(token_rows, TOKEN_FIELDNAMES)}</section>
</main>
<script type="application/json" id="no-bridge-residual-source-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile non-segment and run-local sources for residual no-bridge spans.")
    parser.add_argument("--integrated-targets", type=Path, default=DEFAULT_INTEGRATED_TARGETS)
    parser.add_argument("--anchors", type=Path, default=DEFAULT_ANCHORS)
    parser.add_argument("--weak-gaps", type=Path, default=DEFAULT_WEAK_GAPS)
    parser.add_argument("--weak-gap-promoted-summary", type=Path, default=DEFAULT_WEAK_GAP_PROMOTED_SUMMARY)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--clean-fixtures", type=Path, default=DEFAULT_CLEAN_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--min-source-length", type=int, default=2)
    parser.add_argument("--min-repeat", type=int, default=2)
    parser.add_argument("--min-delta", type=int, default=4)
    parser.add_argument("--max-delta", type=int, default=2)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Structural No-Bridge Residual Source Probe",
    )
    args = parser.parse_args()
    summary = build_report(args)
    print(f"Residual bytes: {summary['residual_bytes']}")
    print(f"Control exact bytes: {summary['control_exact_bytes']}")
    print(f"Fragment exact bytes: {summary['fragment_exact_bytes']}")
    print(f"Generated bytes: {summary['generated_bytes']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
