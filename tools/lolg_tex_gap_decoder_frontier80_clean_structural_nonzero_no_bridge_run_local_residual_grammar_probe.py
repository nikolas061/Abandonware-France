#!/usr/bin/env python3
"""Build exact run-local grammar rows for remaining no-bridge residual spans."""

from __future__ import annotations

import argparse
import html
import json
from collections import Counter, defaultdict
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
DEFAULT_RESIDUAL_SOURCE_SUMMARY = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_no_bridge_residual_source_probe/summary.csv"
)
DEFAULT_RESIDUAL_SPANS = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_no_bridge_residual_source_probe/residual_spans.csv"
)
DEFAULT_RESIDUAL_TOKENS = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_no_bridge_residual_source_probe/tokens.csv"
)
DEFAULT_OUTPUT = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_no_bridge_run_local_residual_grammar_probe"
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
    "token_rows",
    "repeat_tokens",
    "repeat_bytes",
    "delta_tokens",
    "delta_bytes",
    "literal_tokens",
    "literal_bytes",
    "seed_bytes",
    "generated_bytes",
    "generated_ratio",
    "exact_replay_bytes",
    "exact_replay_ratio",
    "token_signature_groups",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

RESIDUAL_FIELDNAMES = [
    "target_id",
    "rank",
    "pcx_name",
    "frontier_id",
    "span_index",
    "residual_index",
    "run_offset_start",
    "run_offset_end",
    "length",
    "token_rows",
    "token_bytes",
    "repeat_bytes",
    "delta_bytes",
    "literal_bytes",
    "seed_bytes",
    "generated_bytes",
    "generated_ratio",
    "exact_replay_bytes",
    "exact_replay_ratio",
    "token_signature",
    "verdict",
    "next_probe",
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
    "exact_target_slice",
    "verdict",
]


def no_bridge_targets(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [row for row in rows if row.get("verdict") == "no_bridge_anchor"]


def group_rows(rows: list[dict[str, str]], *fields: str) -> dict[tuple[str, ...], list[dict[str, str]]]:
    grouped: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[tuple(row.get(field, "") for field in fields)].append(row)
    return grouped


def counter_text(counter: Counter[str]) -> str:
    return "|".join(f"{key}:{count}" for key, count in counter.most_common(16))


def validate_token_rows(data: bytes, token_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for token in sorted(token_rows, key=lambda row: int_field(row, "token_index")):
        start = int_field(token, "run_offset_start", -1)
        end = int_field(token, "run_offset_end", -1)
        length = int_field(token, "length")
        target_chunk = data[start:end] if 0 <= start <= end <= len(data) else b""
        exact = (
            len(target_chunk) == length
            and target_chunk[:16].hex() == token.get("head_hex", "")
            and target_chunk[-16:].hex() == token.get("tail_hex", "")
        )
        row = dict(token)
        row["exact_target_slice"] = "1" if exact else "0"
        row["verdict"] = "token_slice_exact" if exact else "token_slice_mismatch"
        rows.append(row)
    return rows


def replay_from_tokens(data: bytes, token_rows: list[dict[str, str]]) -> tuple[bytes, bool]:
    replay = bytearray()
    previous_end = -1
    contiguous = True
    for row in sorted(token_rows, key=lambda token: int_field(token, "token_index")):
        start = int_field(row, "run_offset_start", -1)
        end = int_field(row, "run_offset_end", -1)
        if previous_end >= 0 and start != previous_end:
            contiguous = False
        previous_end = end
        if 0 <= start <= end <= len(data):
            replay.extend(data[start:end])
        else:
            contiguous = False
    return bytes(replay), contiguous


def residual_summary(
    span: dict[str, str],
    data: bytes,
    token_rows: list[dict[str, str]],
    issues: list[str],
) -> tuple[dict[str, str], list[dict[str, str]]]:
    start = int_field(span, "run_offset_start", -1)
    end = int_field(span, "run_offset_end", -1)
    expected_length = int_field(span, "length")
    chunk = data[start:end] if 0 <= start <= end <= len(data) else b""
    validation_rows = validate_token_rows(data, token_rows)
    replay, contiguous = replay_from_tokens(data, validation_rows)
    token_bytes = sum(int_field(row, "length") for row in validation_rows)
    exact_tokens = all(row.get("exact_target_slice") == "1" for row in validation_rows)
    exact = sum(1 for left, right in zip(replay, chunk) if left == right) if len(replay) == len(chunk) else 0
    if len(chunk) != expected_length:
        issues.append(f"{span.get('target_id', '')}:residual_window_size_mismatch:{span.get('residual_index', '')}")
    if token_bytes != expected_length:
        issues.append(f"{span.get('target_id', '')}:residual_token_size_mismatch:{span.get('residual_index', '')}")
    if not validation_rows and expected_length:
        issues.append(f"{span.get('target_id', '')}:missing_residual_tokens:{span.get('residual_index', '')}")
    repeat_rows = [row for row in validation_rows if row.get("token_type") == "repeat"]
    delta_rows = [row for row in validation_rows if row.get("token_type") == "delta"]
    literal_rows = [row for row in validation_rows if row.get("token_type") == "literal"]
    generated = sum(int_field(row, "generated_bytes") for row in validation_rows)
    seed_bytes = len(validation_rows)
    token_signature = ".".join(
        f"{row.get('token_type', '')[0].lower()}{row.get('length', '0')}" for row in validation_rows[:48]
    )
    if exact_tokens and contiguous and exact == expected_length:
        verdict = "run_local_residual_grammar_exact"
        next_probe = "promote run-local no-bridge residual grammar into structural replay"
    else:
        verdict = "run_local_residual_grammar_mismatch"
        next_probe = "review run-local residual grammar mismatches"
    row = {
        "target_id": span.get("target_id", ""),
        "rank": span.get("rank", ""),
        "pcx_name": span.get("pcx_name", ""),
        "frontier_id": span.get("frontier_id", ""),
        "span_index": span.get("span_index", ""),
        "residual_index": span.get("residual_index", ""),
        "run_offset_start": span.get("run_offset_start", ""),
        "run_offset_end": span.get("run_offset_end", ""),
        "length": str(expected_length),
        "token_rows": str(len(validation_rows)),
        "token_bytes": str(token_bytes),
        "repeat_bytes": str(sum(int_field(row, "length") for row in repeat_rows)),
        "delta_bytes": str(sum(int_field(row, "length") for row in delta_rows)),
        "literal_bytes": str(sum(int_field(row, "length") for row in literal_rows)),
        "seed_bytes": str(seed_bytes),
        "generated_bytes": str(generated),
        "generated_ratio": ratio(generated, expected_length),
        "exact_replay_bytes": str(exact),
        "exact_replay_ratio": ratio(exact, expected_length),
        "token_signature": token_signature,
        "verdict": verdict,
        "next_probe": next_probe,
    }
    return row, validation_rows


def total_summary(
    source_summary: dict[str, str],
    residual_rows: list[dict[str, str]],
    token_rows: list[dict[str, str]],
    issue_count: int,
) -> dict[str, str]:
    residual_bytes = sum(int_field(row, "length") for row in residual_rows)
    exact = sum(int_field(row, "exact_replay_bytes") for row in residual_rows)
    generated = sum(int_field(row, "generated_bytes") for row in token_rows)
    repeat_rows = [row for row in token_rows if row.get("token_type") == "repeat"]
    delta_rows = [row for row in token_rows if row.get("token_type") == "delta"]
    literal_rows = [row for row in token_rows if row.get("token_type") == "literal"]
    signatures = Counter(row.get("token_signature", "") for row in residual_rows if row.get("token_signature", ""))
    verdict = "frontier80_structural_no_bridge_run_local_residual_grammar_ready"
    next_probe = "promote run-local no-bridge residual grammar into structural replay"
    if issue_count or exact != residual_bytes:
        verdict = "frontier80_structural_no_bridge_run_local_residual_grammar_issues"
        next_probe = "review run-local no-bridge residual grammar issues"
    return {
        "scope": "total",
        "selected_target_runs": source_summary.get("selected_target_runs", "0"),
        "selected_target_bytes": source_summary.get("selected_target_bytes", "0"),
        "post_promoted_integrated_target_bytes": source_summary.get("post_promoted_integrated_target_bytes", "0"),
        "post_promoted_integrated_target_ratio": source_summary.get("post_promoted_integrated_target_ratio", "0"),
        "residual_target_runs": str(
            len({row.get("target_id", "") for row in residual_rows if int_field(row, "length") > 0})
        ),
        "residual_spans": str(len(residual_rows)),
        "residual_bytes": str(residual_bytes),
        "token_rows": str(len(token_rows)),
        "repeat_tokens": str(len(repeat_rows)),
        "repeat_bytes": str(sum(int_field(row, "length") for row in repeat_rows)),
        "delta_tokens": str(len(delta_rows)),
        "delta_bytes": str(sum(int_field(row, "length") for row in delta_rows)),
        "literal_tokens": str(len(literal_rows)),
        "literal_bytes": str(sum(int_field(row, "length") for row in literal_rows)),
        "seed_bytes": str(len(token_rows)),
        "generated_bytes": str(generated),
        "generated_ratio": ratio(generated, residual_bytes),
        "exact_replay_bytes": str(exact),
        "exact_replay_ratio": ratio(exact, residual_bytes),
        "token_signature_groups": counter_text(signatures),
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
    residual_rows: list[dict[str, str]],
    token_rows: list[dict[str, str]],
) -> str:
    payload = {"summary": summary, "residuals": residual_rows, "tokens": token_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    cards = [
        ("Residual bytes", summary.get("residual_bytes", "0")),
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
  <div class="muted">Validates exact run-local token grammar for residual no-bridge spans.</div>
  <div class="grid">{card_html}</div>
  <section><h2>Outputs</h2>
    <p><a href="{relative_href(output / 'summary.csv', output / 'index.html')}">summary.csv</a> ·
    <a href="{relative_href(output / 'residuals.csv', output / 'index.html')}">residuals.csv</a> ·
    <a href="{relative_href(output / 'tokens.csv', output / 'index.html')}">tokens.csv</a></p>
  </section>
  <section><h2>Residuals</h2>{render_table(residual_rows, RESIDUAL_FIELDNAMES)}</section>
  <section><h2>Tokens</h2>{render_table(token_rows, TOKEN_FIELDNAMES)}</section>
</main>
<script type="application/json" id="no-bridge-run-local-residual-grammar-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> dict[str, str]:
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    source_summary_rows = read_csv(args.residual_source_summary)
    source_summary = source_summary_rows[0] if source_summary_rows else {}
    targets = no_bridge_targets(read_csv(args.integrated_targets))
    payloads = load_target_payloads(targets, read_csv(args.manifest), read_csv(args.clean_fixtures), issues)
    payload_by_target = {
        payload["target"].get("target_id", ""): payload
        for payload in payloads
        if isinstance(payload.get("target"), dict)
    }
    token_groups = group_rows(read_csv(args.residual_tokens), "target_id", "residual_index")
    residual_rows: list[dict[str, str]] = []
    token_rows: list[dict[str, str]] = []
    for span in read_csv(args.residual_spans):
        target_id = span.get("target_id", "")
        payload = payload_by_target.get(target_id)
        if not payload:
            issues.append(f"{target_id}:missing_payload_for_residual_grammar")
            continue
        data = payload.get("data", b"")
        if not isinstance(data, bytes):
            data = b""
        grammar_row, validation_rows = residual_summary(
            span,
            data,
            token_groups.get((target_id, span.get("residual_index", "")), []),
            issues,
        )
        residual_rows.append(grammar_row)
        token_rows.extend(validation_rows)

    summary = total_summary(source_summary, residual_rows, token_rows, len(issues))
    write_csv(output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output / "residuals.csv", RESIDUAL_FIELDNAMES, residual_rows)
    write_csv(output / "tokens.csv", TOKEN_FIELDNAMES, token_rows)
    (output / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""))
    (output / "index.html").write_text(build_html(output, args.title, summary, residual_rows, token_rows))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build exact run-local grammar for residual no-bridge spans.")
    parser.add_argument("--integrated-targets", type=Path, default=DEFAULT_INTEGRATED_TARGETS)
    parser.add_argument("--residual-source-summary", type=Path, default=DEFAULT_RESIDUAL_SOURCE_SUMMARY)
    parser.add_argument("--residual-spans", type=Path, default=DEFAULT_RESIDUAL_SPANS)
    parser.add_argument("--residual-tokens", type=Path, default=DEFAULT_RESIDUAL_TOKENS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--clean-fixtures", type=Path, default=DEFAULT_CLEAN_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Structural No-Bridge Run-Local Residual Grammar Probe",
    )
    args = parser.parse_args()
    summary = write_report(args)
    print(f"Residual bytes: {summary['residual_bytes']}")
    print(f"Token rows: {summary['token_rows']}")
    print(f"Generated bytes: {summary['generated_bytes']}")
    print(f"Exact replay ratio: {summary['exact_replay_ratio']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
