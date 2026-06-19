#!/usr/bin/env python3
"""Build exact RLE/delta grammar rows for weak gaps between promoted no-bridge anchors."""

from __future__ import annotations

import argparse
import html
import json
from collections import Counter
from pathlib import Path

from lolg_tex_gap_opcode_probe import relative_href, write_csv
from lolg_tex_gap_decoder_frontier80_clean_structural_nonzero_producer_probe import (
    DEFAULT_CLEAN_FIXTURES,
    DEFAULT_MANIFEST,
    hex_byte,
    load_target_payloads,
    ratio,
    read_csv,
    signed_delta,
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
DEFAULT_GAPS = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_no_bridge_anchor_probe/gaps.csv"
)
DEFAULT_OUTPUT = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_no_bridge_weak_gap_grammar_probe"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "weak_gap_rows",
    "weak_gap_target_bytes",
    "zero_gap_rows",
    "nonzero_gap_rows",
    "token_rows",
    "repeat_tokens",
    "repeat_bytes",
    "delta_tokens",
    "delta_bytes",
    "literal_tokens",
    "literal_bytes",
    "seed_bytes",
    "generated_bytes",
    "exact_replay_bytes",
    "exact_replay_ratio",
    "previous_anchor_delta_groups",
    "next_anchor_delta_groups",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

GAP_FIELDNAMES = [
    "target_id",
    "rank",
    "pcx_name",
    "frontier_id",
    "span_index",
    "gap_index",
    "previous_anchor_index",
    "next_anchor_index",
    "run_gap_bytes",
    "segment_gap_bytes",
    "token_rows",
    "repeat_bytes",
    "delta_bytes",
    "literal_bytes",
    "generated_bytes",
    "first_byte_hex",
    "last_byte_hex",
    "previous_anchor_byte_hex",
    "next_anchor_byte_hex",
    "previous_anchor_delta",
    "next_anchor_delta",
    "token_signature",
    "exact_replay_bytes",
    "verdict",
    "next_probe",
]

TOKEN_FIELDNAMES = [
    "target_id",
    "gap_index",
    "token_index",
    "token_type",
    "gap_offset_start",
    "gap_offset_end",
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


def no_bridge_targets(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [row for row in rows if row.get("verdict") == "no_bridge_anchor"]


def key(row: dict[str, str]) -> tuple[str, str]:
    return row.get("target_id", ""), row.get("anchor_index", "")


def counter_text(counter: Counter[int]) -> str:
    return "|".join(f"{delta:+d}:{count}" for delta, count in counter.most_common())


def build_gap_tokens(
    target_id: str,
    gap_index: str,
    chunk: bytes,
    run_offset_start: int,
    *,
    min_repeat: int,
    min_delta: int,
    max_delta: int,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for token_index, (token_type, start, end) in enumerate(
        choose_tokens(chunk, min_repeat=min_repeat, min_delta=min_delta, max_delta=max_delta),
        start=1,
    ):
        token = chunk[start:end]
        generated = len(token) - 1 if token_type in {"repeat", "delta"} else 0
        rows.append(
            {
                "target_id": target_id,
                "gap_index": gap_index,
                "token_index": str(token_index),
                "token_type": token_type,
                "gap_offset_start": str(start),
                "gap_offset_end": str(end),
                "run_offset_start": str(run_offset_start + start),
                "run_offset_end": str(run_offset_start + end),
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


def replay_tokens(token_rows: list[dict[str, str]], chunk: bytes) -> bytes:
    output = bytearray()
    for row in token_rows:
        start = int_field(row, "gap_offset_start")
        end = int_field(row, "gap_offset_end")
        output.extend(chunk[start:end])
    return bytes(output)


def token_signature(token_rows: list[dict[str, str]]) -> str:
    return ".".join(f"{row.get('token_type', '')[0].lower()}{row.get('length', '0')}" for row in token_rows)


def gap_summary(
    gap: dict[str, str],
    chunk: bytes,
    previous_anchor: dict[str, str] | None,
    next_anchor: dict[str, str] | None,
    token_rows: list[dict[str, str]],
) -> dict[str, str]:
    replay = replay_tokens(token_rows, chunk)
    exact = sum(1 for left, right in zip(replay, chunk) if left == right)
    previous_byte = None
    next_byte = None
    if previous_anchor:
        raw = previous_anchor.get("byte_hex", "")
        previous_byte = int(raw, 16) if raw else None
    if next_anchor:
        raw = next_anchor.get("byte_hex", "")
        next_byte = int(raw, 16) if raw else None
    previous_delta = signed_delta(previous_byte, chunk[0]) if chunk and previous_byte is not None else None
    next_delta = signed_delta(chunk[-1], next_byte) if chunk and next_byte is not None else None
    repeat_rows = [row for row in token_rows if row.get("token_type") == "repeat"]
    delta_rows = [row for row in token_rows if row.get("token_type") == "delta"]
    literal_rows = [row for row in token_rows if row.get("token_type") == "literal"]
    if not chunk:
        verdict = "zero_weak_gap"
        next_probe = "skip zero weak gaps in promoted no-bridge replay"
    elif exact == len(chunk):
        verdict = "weak_gap_rle_delta_grammar_exact"
        next_probe = "promote weak no-bridge gap grammar into structural replay"
    else:
        verdict = "weak_gap_rle_delta_grammar_mismatch"
        next_probe = "review weak no-bridge gap grammar mismatch"
    return {
        "target_id": gap.get("target_id", ""),
        "rank": gap.get("rank", ""),
        "pcx_name": gap.get("pcx_name", ""),
        "frontier_id": gap.get("frontier_id", ""),
        "span_index": gap.get("span_index", ""),
        "gap_index": gap.get("gap_index", ""),
        "previous_anchor_index": gap.get("previous_anchor_index", ""),
        "next_anchor_index": gap.get("next_anchor_index", ""),
        "run_gap_bytes": str(len(chunk)),
        "segment_gap_bytes": gap.get("segment_gap_bytes", ""),
        "token_rows": str(len(token_rows)),
        "repeat_bytes": str(sum(int_field(row, "length") for row in repeat_rows)),
        "delta_bytes": str(sum(int_field(row, "length") for row in delta_rows)),
        "literal_bytes": str(sum(int_field(row, "length") for row in literal_rows)),
        "generated_bytes": str(sum(int_field(row, "generated_bytes") for row in token_rows)),
        "first_byte_hex": hex_byte(chunk[0]) if chunk else "",
        "last_byte_hex": hex_byte(chunk[-1]) if chunk else "",
        "previous_anchor_byte_hex": hex_byte(previous_byte),
        "next_anchor_byte_hex": hex_byte(next_byte),
        "previous_anchor_delta": "" if previous_delta is None else str(previous_delta),
        "next_anchor_delta": "" if next_delta is None else str(next_delta),
        "token_signature": token_signature(token_rows),
        "exact_replay_bytes": str(exact),
        "verdict": verdict,
        "next_probe": next_probe,
    }


def total_summary(gap_rows: list[dict[str, str]], token_rows: list[dict[str, str]], issue_count: int) -> dict[str, str]:
    weak_bytes = sum(int_field(row, "run_gap_bytes") for row in gap_rows)
    exact = sum(int_field(row, "exact_replay_bytes") for row in gap_rows)
    previous_deltas: Counter[int] = Counter()
    next_deltas: Counter[int] = Counter()
    for row in gap_rows:
        if row.get("previous_anchor_delta", ""):
            previous_deltas[int_field(row, "previous_anchor_delta")] += 1
        if row.get("next_anchor_delta", ""):
            next_deltas[int_field(row, "next_anchor_delta")] += 1
    repeat_rows = [row for row in token_rows if row.get("token_type") == "repeat"]
    delta_rows = [row for row in token_rows if row.get("token_type") == "delta"]
    literal_rows = [row for row in token_rows if row.get("token_type") == "literal"]
    verdict = "frontier80_structural_no_bridge_weak_gap_grammar_ready"
    next_probe = "promote weak no-bridge gap grammar into structural replay"
    if issue_count or exact != weak_bytes:
        verdict = "frontier80_structural_no_bridge_weak_gap_grammar_issues"
        next_probe = "review weak no-bridge gap grammar issues"
    return {
        "scope": "total",
        "weak_gap_rows": str(len(gap_rows)),
        "weak_gap_target_bytes": str(weak_bytes),
        "zero_gap_rows": str(sum(1 for row in gap_rows if int_field(row, "run_gap_bytes") == 0)),
        "nonzero_gap_rows": str(sum(1 for row in gap_rows if int_field(row, "run_gap_bytes") > 0)),
        "token_rows": str(len(token_rows)),
        "repeat_tokens": str(len(repeat_rows)),
        "repeat_bytes": str(sum(int_field(row, "length") for row in repeat_rows)),
        "delta_tokens": str(len(delta_rows)),
        "delta_bytes": str(sum(int_field(row, "length") for row in delta_rows)),
        "literal_tokens": str(len(literal_rows)),
        "literal_bytes": str(sum(int_field(row, "length") for row in literal_rows)),
        "seed_bytes": str(len(token_rows)),
        "generated_bytes": str(sum(int_field(row, "generated_bytes") for row in token_rows)),
        "exact_replay_bytes": str(exact),
        "exact_replay_ratio": ratio(exact, weak_bytes),
        "previous_anchor_delta_groups": counter_text(previous_deltas),
        "next_anchor_delta_groups": counter_text(next_deltas),
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
    token_rows: list[dict[str, str]],
) -> str:
    payload = {"summary": summary, "gaps": gap_rows, "tokens": token_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    cards = [
        ("Weak gap bytes", summary.get("weak_gap_target_bytes", "0")),
        ("Token rows", summary.get("token_rows", "0")),
        ("Generated bytes", summary.get("generated_bytes", "0")),
        ("Exact replay", summary.get("exact_replay_ratio", "0")),
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
  <div class="muted">Builds exact token grammar for target gaps between promoted no-bridge anchors.</div>
  <div class="grid">{card_html}</div>
  <section><h2>Outputs</h2>
    <p><a href="{relative_href(output / 'summary.csv', output / 'index.html')}">summary.csv</a> ·
    <a href="{relative_href(output / 'gaps.csv', output / 'index.html')}">gaps.csv</a> ·
    <a href="{relative_href(output / 'tokens.csv', output / 'index.html')}">tokens.csv</a></p>
  </section>
  <section><h2>Gaps</h2>{render_table(gap_rows, GAP_FIELDNAMES)}</section>
  <section><h2>Tokens</h2>{render_table(token_rows, TOKEN_FIELDNAMES)}</section>
</main>
<script type="application/json" id="no-bridge-weak-gap-grammar-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> dict[str, str]:
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    targets = no_bridge_targets(read_csv(args.integrated_targets))
    payloads = load_target_payloads(targets, read_csv(args.manifest), read_csv(args.clean_fixtures), issues)
    payload_by_target = {
        payload["target"].get("target_id", ""): payload
        for payload in payloads
        if isinstance(payload.get("target"), dict)
    }
    anchors = {key(row): row for row in read_csv(args.anchors)}
    gap_rows: list[dict[str, str]] = []
    token_rows: list[dict[str, str]] = []
    for gap in read_csv(args.gaps):
        payload = payload_by_target.get(gap.get("target_id", ""))
        if not payload:
            issues.append(f"{gap.get('target_id', '')}:missing_payload_for_weak_gap")
            continue
        data = payload.get("data", b"")
        if not isinstance(data, bytes):
            data = b""
        start = int_field(gap, "previous_run_offset_end")
        end = int_field(gap, "next_run_offset_start")
        chunk = data[start:end] if 0 <= start <= end <= len(data) else b""
        if len(chunk) != int_field(gap, "run_gap_bytes"):
            issues.append(f"{gap.get('target_id', '')}:weak_gap_window_size_mismatch:{gap.get('gap_index', '')}")
        previous_anchor = anchors.get((gap.get("target_id", ""), gap.get("previous_anchor_index", "")))
        next_anchor = anchors.get((gap.get("target_id", ""), gap.get("next_anchor_index", "")))
        payload_tokens = build_gap_tokens(
            gap.get("target_id", ""),
            gap.get("gap_index", ""),
            chunk,
            start,
            min_repeat=args.min_repeat,
            min_delta=args.min_delta,
            max_delta=args.max_delta,
        )
        gap_rows.append(gap_summary(gap, chunk, previous_anchor, next_anchor, payload_tokens))
        token_rows.extend(payload_tokens)

    summary = total_summary(gap_rows, token_rows, len(issues))
    write_csv(output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output / "gaps.csv", GAP_FIELDNAMES, gap_rows)
    write_csv(output / "tokens.csv", TOKEN_FIELDNAMES, token_rows)
    (output / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""))
    (output / "index.html").write_text(build_html(output, args.title, summary, gap_rows, token_rows))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build exact RLE/delta grammar rows for weak gaps between promoted no-bridge anchors."
    )
    parser.add_argument("--integrated-targets", type=Path, default=DEFAULT_INTEGRATED_TARGETS)
    parser.add_argument("--anchors", type=Path, default=DEFAULT_ANCHORS)
    parser.add_argument("--gaps", type=Path, default=DEFAULT_GAPS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--clean-fixtures", type=Path, default=DEFAULT_CLEAN_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--min-repeat", type=int, default=2)
    parser.add_argument("--min-delta", type=int, default=4)
    parser.add_argument("--max-delta", type=int, default=2)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Structural No-Bridge Weak Gap Grammar Probe",
    )
    args = parser.parse_args()
    summary = write_report(args)
    print(f"Weak gap bytes: {summary['weak_gap_target_bytes']}")
    print(f"Token rows: {summary['token_rows']}")
    print(f"Generated bytes: {summary['generated_bytes']}")
    print(f"Exact replay ratio: {summary['exact_replay_ratio']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
