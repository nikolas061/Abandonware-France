#!/usr/bin/env python3
"""Derive compact-control seed grammar for structural Frontier80 RLE/delta token gaps."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

from lolg_tex_gap_opcode_probe import relative_href, write_csv
from lolg_tex_gap_decoder_frontier80_clean_structural_nonzero_producer_probe import (
    DEFAULT_CLEAN_FIXTURES,
    DEFAULT_MANIFEST,
    DEFAULT_RUNS,
    load_target_payloads,
    ratio,
    read_csv,
    select_largest_targets,
)


DEFAULT_TOKENS = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_rle_delta_parser_probe/tokens.csv"
)
DEFAULT_CONTROL_GAPS = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_control_bridge_probe/control_gaps.csv"
)
DEFAULT_OUTPUT = Path(
    "output/tex_gap_decoder_frontier80_clean_structural_nonzero_compact_control_grammar_probe"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "target_runs",
    "control_gap_rows",
    "control_gap_bytes",
    "target_gap_bytes",
    "token_rows",
    "token_bytes",
    "covered_token_rows",
    "covered_token_bytes",
    "exact_seed_token_rows",
    "plus1_seed_token_rows",
    "minus1_seed_token_rows",
    "exact_chunk_token_rows",
    "unresolved_token_rows",
    "unresolved_token_bytes",
    "replay_exact_bytes",
    "replay_exact_ratio",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

GAP_FIELDNAMES = [
    "target_id",
    "gap_index",
    "previous_token_index",
    "next_token_index",
    "previous_run_offset_end",
    "next_run_offset_start",
    "target_gap_bytes",
    "previous_segment_end",
    "next_segment_offset",
    "control_gap_bytes",
    "token_rows",
    "covered_token_rows",
    "covered_token_bytes",
    "exact_seed_token_rows",
    "plus1_seed_token_rows",
    "unresolved_token_rows",
    "replay_exact_bytes",
    "verdict",
]

TOKEN_GRAMMAR_FIELDNAMES = [
    "target_id",
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


def int_field(row: dict[str, str], field: str, default: int = 0) -> int:
    raw = row.get(field, "")
    if raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def hex_byte(value: int | None) -> str:
    return "" if value is None else f"0x{value:02x}"


def group_rows(rows: list[dict[str, str]], key: str) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        grouped.setdefault(row.get(key, ""), []).append(row)
    return grouped


def target_id(payload: dict[str, object]) -> str:
    target = payload.get("target", {})
    return target.get("target_id", "") if isinstance(target, dict) else ""


def token_chunk(payload: dict[str, object], token: dict[str, str]) -> bytes:
    data = payload.get("data", b"")
    if not isinstance(data, bytes):
        return b""
    start = int_field(token, "run_offset_start", -1)
    end = int_field(token, "run_offset_end", -1)
    if start < 0 or end < start or end > len(data):
        return b""
    return data[start:end]


def byte_offsets(data: bytes, value: int) -> list[int]:
    return [offset for offset, current in enumerate(data) if current == value]


def parse_delta_signature(text: str) -> list[int]:
    deltas: list[int] = []
    for item in text.split():
        try:
            deltas.append(int(item))
        except ValueError:
            continue
    return deltas


def replay_from_seed(token: dict[str, str], seed: int, length: int) -> bytes:
    token_type = token.get("token_type", "")
    if length <= 0:
        return b""
    if token_type == "repeat":
        return bytes([seed]) * length
    if token_type == "delta":
        output = bytearray([seed])
        for delta in parse_delta_signature(token.get("delta_signature", "")):
            output.append((output[-1] + delta) & 0xFF)
        return bytes(output[:length])
    if length == 1:
        return bytes([seed])
    return b""


def source_candidates(gap: bytes, seed: int) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    for transform, source_delta, source_value in [
        ("exact_seed", 0, seed),
        ("plus1_seed", 1, (seed - 1) & 0xFF),
        ("minus1_seed", -1, (seed + 1) & 0xFF),
    ]:
        offsets = byte_offsets(gap, source_value)
        if offsets:
            candidates.append(
                {
                    "transform": transform,
                    "source_delta": source_delta,
                    "source_value": source_value,
                    "source_gap_offset": offsets[0],
                    "source_occurrences": len(offsets),
                }
            )
    return candidates


def exact_chunk_candidate(gap: bytes, chunk: bytes) -> dict[str, object] | None:
    if len(chunk) < 2:
        return None
    offset = gap.find(chunk)
    if offset < 0:
        return None
    return {
        "transform": "exact_chunk",
        "source_delta": 0,
        "source_value": chunk[0],
        "source_gap_offset": offset,
        "source_occurrences": 1,
    }


def choose_candidate(gap: bytes, chunk: bytes, token: dict[str, str]) -> tuple[dict[str, object] | None, bytes]:
    if not chunk:
        return None, b""
    exact = exact_chunk_candidate(gap, chunk)
    if exact is not None:
        return exact, chunk
    seed = chunk[0]
    for candidate in source_candidates(gap, seed):
        source_value = int(candidate["source_value"])
        transformed_seed = (source_value + int(candidate["source_delta"])) & 0xFF
        replay = replay_from_seed(token, transformed_seed, len(chunk))
        if replay == chunk:
            return candidate, replay
    return None, b""


def grammar_rule(token: dict[str, str], candidate: dict[str, object] | None) -> str:
    if candidate is None:
        return "unresolved"
    transform = str(candidate["transform"])
    token_type = token.get("token_type", "")
    if transform == "exact_chunk":
        return "exact_control_chunk"
    return f"{transform}_{token_type}"


def build_token_rows_for_gap(
    payload: dict[str, object],
    gap_row: dict[str, str],
    tokens: list[dict[str, str]],
) -> list[dict[str, str]]:
    segment = payload.get("segment", b"")
    if not isinstance(segment, bytes):
        segment = b""
    segment_start = int_field(gap_row, "previous_segment_end", -1)
    segment_end = int_field(gap_row, "next_segment_offset", -1)
    run_start = int_field(gap_row, "previous_run_offset_end", -1)
    run_end = int_field(gap_row, "next_run_offset_start", -1)
    if segment_start < 0 or segment_end < segment_start or run_start < 0 or run_end < run_start:
        return []
    gap = segment[segment_start:segment_end]
    selected_tokens = [
        row
        for row in tokens
        if int_field(row, "run_offset_start", -1) >= run_start
        and int_field(row, "run_offset_end", -1) <= run_end
    ]
    rows: list[dict[str, str]] = []
    for token in selected_tokens:
        chunk = token_chunk(payload, token)
        candidate, replay = choose_candidate(gap, chunk, token)
        source_gap_offset = int(candidate["source_gap_offset"]) if candidate else -1
        source_segment_offset = segment_start + source_gap_offset if source_gap_offset >= 0 else -1
        source_value = int(candidate["source_value"]) if candidate else None
        source_context = (
            gap[max(0, source_gap_offset - 8) : min(len(gap), source_gap_offset + 9)].hex()
            if source_gap_offset >= 0
            else ""
        )
        exact = sum(1 for left, right in zip(replay, chunk) if left == right)
        covered = len(chunk) if replay == chunk else 0
        rows.append(
            {
                "target_id": token.get("target_id", ""),
                "gap_index": gap_row.get("gap_index", ""),
                "token_index": token.get("token_index", ""),
                "token_type": token.get("token_type", ""),
                "run_offset_start": token.get("run_offset_start", ""),
                "run_offset_end": token.get("run_offset_end", ""),
                "length": str(len(chunk)),
                "target_hex": chunk.hex(),
                "seed_hex": hex_byte(chunk[0] if chunk else None),
                "source_transform": str(candidate["transform"]) if candidate else "",
                "source_delta": str(candidate["source_delta"]) if candidate else "",
                "source_value_hex": hex_byte(source_value),
                "source_gap_offset": "" if source_gap_offset < 0 else str(source_gap_offset),
                "source_segment_offset": "" if source_segment_offset < 0 else str(source_segment_offset),
                "source_occurrences": str(candidate["source_occurrences"]) if candidate else "0",
                "source_context_hex": source_context,
                "grammar_rule": grammar_rule(token, candidate),
                "covered_bytes": str(covered),
                "replay_hex": replay.hex(),
                "replay_exact_bytes": str(exact),
                "verdict": "covered" if replay == chunk else "unresolved",
            }
        )
    return rows


def build_gap_summary(
    payload: dict[str, object],
    gap_row: dict[str, str],
    token_rows: list[dict[str, str]],
) -> dict[str, str]:
    data = payload.get("data", b"")
    segment = payload.get("segment", b"")
    if not isinstance(data, bytes):
        data = b""
    if not isinstance(segment, bytes):
        segment = b""
    run_start = int_field(gap_row, "previous_run_offset_end", -1)
    run_end = int_field(gap_row, "next_run_offset_start", -1)
    segment_start = int_field(gap_row, "previous_segment_end", -1)
    segment_end = int_field(gap_row, "next_segment_offset", -1)
    target_gap = data[run_start:run_end] if 0 <= run_start <= run_end else b""
    control_gap = segment[segment_start:segment_end] if 0 <= segment_start <= segment_end else b""
    covered = [row for row in token_rows if row.get("verdict") == "covered"]
    exact_seed = [row for row in token_rows if row.get("source_transform") == "exact_seed"]
    plus1_seed = [row for row in token_rows if row.get("source_transform") == "plus1_seed"]
    unresolved = [row for row in token_rows if row.get("verdict") != "covered"]
    replay_exact = sum(int_field(row, "replay_exact_bytes") for row in token_rows)
    verdict = "frontier80_structural_nonzero_compact_control_seed_grammar_ready"
    if unresolved:
        verdict = "frontier80_structural_nonzero_compact_control_seed_grammar_partial"
    return {
        "target_id": gap_row.get("target_id", ""),
        "gap_index": gap_row.get("gap_index", ""),
        "previous_token_index": gap_row.get("previous_token_index", ""),
        "next_token_index": gap_row.get("next_token_index", ""),
        "previous_run_offset_end": gap_row.get("previous_run_offset_end", ""),
        "next_run_offset_start": gap_row.get("next_run_offset_start", ""),
        "target_gap_bytes": str(len(target_gap)),
        "previous_segment_end": gap_row.get("previous_segment_end", ""),
        "next_segment_offset": gap_row.get("next_segment_offset", ""),
        "control_gap_bytes": str(len(control_gap)),
        "token_rows": str(len(token_rows)),
        "covered_token_rows": str(len(covered)),
        "covered_token_bytes": str(sum(int_field(row, "covered_bytes") for row in covered)),
        "exact_seed_token_rows": str(len(exact_seed)),
        "plus1_seed_token_rows": str(len(plus1_seed)),
        "unresolved_token_rows": str(len(unresolved)),
        "replay_exact_bytes": str(replay_exact),
        "verdict": verdict,
    }


def total_summary(gap_rows: list[dict[str, str]], token_rows: list[dict[str, str]], issue_count: int) -> dict[str, str]:
    token_bytes = sum(int_field(row, "length") for row in token_rows)
    covered = [row for row in token_rows if row.get("verdict") == "covered"]
    unresolved = [row for row in token_rows if row.get("verdict") != "covered"]
    exact_seed = [row for row in token_rows if row.get("source_transform") == "exact_seed"]
    plus1_seed = [row for row in token_rows if row.get("source_transform") == "plus1_seed"]
    minus1_seed = [row for row in token_rows if row.get("source_transform") == "minus1_seed"]
    exact_chunk = [row for row in token_rows if row.get("source_transform") == "exact_chunk"]
    replay_exact = sum(int_field(row, "replay_exact_bytes") for row in token_rows)
    verdict = "frontier80_structural_nonzero_compact_control_seed_grammar_ready"
    if unresolved:
        verdict = "frontier80_structural_nonzero_compact_control_seed_grammar_partial"
    return {
        "scope": "total",
        "target_runs": str(len({row.get("target_id", "") for row in gap_rows})),
        "control_gap_rows": str(len(gap_rows)),
        "control_gap_bytes": str(sum(int_field(row, "control_gap_bytes") for row in gap_rows)),
        "target_gap_bytes": str(sum(int_field(row, "target_gap_bytes") for row in gap_rows)),
        "token_rows": str(len(token_rows)),
        "token_bytes": str(token_bytes),
        "covered_token_rows": str(len(covered)),
        "covered_token_bytes": str(sum(int_field(row, "covered_bytes") for row in covered)),
        "exact_seed_token_rows": str(len(exact_seed)),
        "plus1_seed_token_rows": str(len(plus1_seed)),
        "minus1_seed_token_rows": str(len(minus1_seed)),
        "exact_chunk_token_rows": str(len(exact_chunk)),
        "unresolved_token_rows": str(len(unresolved)),
        "unresolved_token_bytes": str(sum(int_field(row, "length") for row in unresolved)),
        "replay_exact_bytes": str(replay_exact),
        "replay_exact_ratio": ratio(replay_exact, token_bytes),
        "issue_rows": str(issue_count),
        "review_verdict": verdict,
        "next_probe": "validate compact-control seed grammar on structural residual runs",
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
    token_rows: list[dict[str, str]],
) -> str:
    payload = {"summary": summary, "gaps": gap_rows, "tokens": token_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    cards = [
        ("Target gap bytes", summary.get("target_gap_bytes", "0")),
        ("Token rows", summary.get("token_rows", "0")),
        ("Covered bytes", summary.get("covered_token_bytes", "0")),
        ("Exact seed tokens", summary.get("exact_seed_token_rows", "0")),
        ("Plus1 seed tokens", summary.get("plus1_seed_token_rows", "0")),
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
  <div class="muted">Tests exact and +1 seed rules inside structural RLE/delta control gaps.</div>
  <div class="grid">{card_html}</div>
  <section><h2>Outputs</h2>
    <p><a href="{relative_href(output / 'summary.csv', output / 'index.html')}">summary.csv</a> ·
    <a href="{relative_href(output / 'gaps.csv', output / 'index.html')}">gaps.csv</a> ·
    <a href="{relative_href(output / 'token_grammar.csv', output / 'index.html')}">token_grammar.csv</a></p>
  </section>
  <section><h2>Control Gaps</h2>{render_table(gap_rows, GAP_FIELDNAMES)}</section>
  <section><h2>Token Grammar</h2>{render_table(token_rows, TOKEN_GRAMMAR_FIELDNAMES)}</section>
</main>
<script type="application/json" id="compact-control-grammar-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> dict[str, str]:
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    run_rows = read_csv(args.runs)
    manifest_rows = read_csv(args.manifest)
    clean_rows = read_csv(args.clean_fixtures)
    token_rows_by_target = group_rows(read_csv(args.tokens), "target_id")
    control_gaps_by_target = group_rows(read_csv(args.control_gaps), "target_id")
    payloads = load_target_payloads(select_largest_targets(run_rows, issues), manifest_rows, clean_rows, issues)

    output_gap_rows: list[dict[str, str]] = []
    output_token_rows: list[dict[str, str]] = []
    for payload in payloads:
        payload_target_id = target_id(payload)
        tokens = token_rows_by_target.get(payload_target_id, [])
        tokens.sort(key=lambda row: int_field(row, "token_index"))
        control_gaps = control_gaps_by_target.get(payload_target_id, [])
        if not control_gaps:
            issues.append(f"{payload_target_id}:missing_control_gap_rows")
        for gap_row in control_gaps:
            gap_token_rows = build_token_rows_for_gap(payload, gap_row, tokens)
            output_token_rows.extend(gap_token_rows)
            output_gap_rows.append(build_gap_summary(payload, gap_row, gap_token_rows))

    summary = total_summary(output_gap_rows, output_token_rows, len(issues))
    write_csv(output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output / "gaps.csv", GAP_FIELDNAMES, output_gap_rows)
    write_csv(output / "token_grammar.csv", TOKEN_GRAMMAR_FIELDNAMES, output_token_rows)
    (output / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""))
    (output / "index.html").write_text(build_html(output, args.title, summary, output_gap_rows, output_token_rows))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Probe compact-control seed grammar for structural Frontier80 token gaps."
    )
    parser.add_argument("--runs", type=Path, default=DEFAULT_RUNS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--clean-fixtures", type=Path, default=DEFAULT_CLEAN_FIXTURES)
    parser.add_argument("--tokens", type=Path, default=DEFAULT_TOKENS)
    parser.add_argument("--control-gaps", type=Path, default=DEFAULT_CONTROL_GAPS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Structural Compact-Control Grammar Probe",
    )
    args = parser.parse_args()
    summary = write_report(args)
    print(f"Target gap bytes: {summary['target_gap_bytes']}")
    print(f"Token rows: {summary['token_rows']}")
    print(f"Covered bytes: {summary['covered_token_bytes']}")
    print(f"Replay exact bytes: {summary['replay_exact_bytes']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
