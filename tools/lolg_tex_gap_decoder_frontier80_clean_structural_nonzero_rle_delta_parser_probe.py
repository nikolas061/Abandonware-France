#!/usr/bin/env python3
"""Build exact run-local RLE/delta token plans for structural Frontier80 nonzero runs."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv
from lolg_tex_gap_decoder_frontier80_clean_structural_nonzero_producer_probe import (
    DEFAULT_CLEAN_FIXTURES,
    DEFAULT_MANIFEST,
    DEFAULT_RUNS,
    load_target_payloads,
    ratio,
    read_csv,
    select_largest_targets,
    signed_delta,
    value_class,
)


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_frontier80_clean_structural_nonzero_rle_delta_parser_probe")

SUMMARY_FIELDNAMES = [
    "scope",
    "target_runs",
    "target_bytes",
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
    "max_token_bytes",
    "exact_replay_bytes",
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
    "repeat_tokens",
    "repeat_bytes",
    "delta_tokens",
    "delta_bytes",
    "literal_tokens",
    "literal_bytes",
    "seed_bytes",
    "generated_bytes",
    "generated_ratio",
    "max_token_bytes",
    "exact_replay_bytes",
    "token_signature",
    "head_hex",
    "tail_hex",
    "verdict",
    "next_probe",
]

TOKEN_FIELDNAMES = [
    "target_id",
    "token_index",
    "token_type",
    "run_offset_start",
    "run_offset_end",
    "absolute_start",
    "absolute_end",
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


def repeat_len(data: bytes, offset: int) -> int:
    index = offset + 1
    while index < len(data) and data[index] == data[offset]:
        index += 1
    return index - offset


def delta_len(data: bytes, offset: int, *, max_delta: int) -> int:
    index = offset + 1
    while index < len(data) and abs(signed_delta(data[index - 1], data[index])) <= max_delta:
        index += 1
    return index - offset


def token_delta_signature(data: bytes) -> str:
    return " ".join(f"{signed_delta(left, right):+d}" for left, right in zip(data, data[1:]))


def dominant_class(data: bytes) -> str:
    if not data:
        return ""
    counts: dict[str, int] = {}
    for value in data:
        counts[value_class(value)] = counts.get(value_class(value), 0) + 1
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]


def choose_tokens(data: bytes, *, min_repeat: int, min_delta: int, max_delta: int) -> list[tuple[str, int, int]]:
    tokens: list[tuple[str, int, int]] = []
    offset = 0
    while offset < len(data):
        current_repeat = repeat_len(data, offset)
        current_delta = delta_len(data, offset, max_delta=max_delta)
        if current_repeat >= max(3, min_repeat):
            tokens.append(("repeat", offset, offset + current_repeat))
            offset += current_repeat
        elif current_delta >= min_delta:
            tokens.append(("delta", offset, offset + current_delta))
            offset += current_delta
        elif current_repeat >= min_repeat:
            tokens.append(("repeat", offset, offset + current_repeat))
            offset += current_repeat
        else:
            tokens.append(("literal", offset, offset + 1))
            offset += 1
    return tokens


def build_token_rows(
    payload: dict[str, object],
    *,
    min_repeat: int,
    min_delta: int,
    max_delta: int,
) -> list[dict[str, str]]:
    target = payload["target"]
    data = payload["data"]
    if not isinstance(target, dict) or not isinstance(data, bytes):
        return []
    absolute_start = int_value(target, "start")
    rows: list[dict[str, str]] = []
    for token_index, (token_type, start, end) in enumerate(
        choose_tokens(data, min_repeat=min_repeat, min_delta=min_delta, max_delta=max_delta),
        start=1,
    ):
        chunk = data[start:end]
        generated = len(chunk) - 1 if token_type in {"repeat", "delta"} else 0
        rows.append(
            {
                "target_id": target.get("target_id", ""),
                "token_index": str(token_index),
                "token_type": token_type,
                "run_offset_start": str(start),
                "run_offset_end": str(end),
                "absolute_start": str(absolute_start + start),
                "absolute_end": str(absolute_start + end),
                "length": str(len(chunk)),
                "seed_hex": hex_byte(chunk[0]) if chunk else "",
                "repeat_value_hex": hex_byte(chunk[0]) if token_type == "repeat" and chunk else "",
                "delta_signature": token_delta_signature(chunk) if token_type == "delta" else "",
                "generated_bytes": str(generated),
                "dominant_value_class": dominant_class(chunk),
                "head_hex": chunk[:16].hex(),
                "tail_hex": chunk[-16:].hex(),
            }
        )
    return rows


def replay_tokens(token_rows: list[dict[str, str]], target_data: bytes) -> bytes:
    output = bytearray()
    for row in token_rows:
        start = int_value(row, "run_offset_start")
        end = int_value(row, "run_offset_end")
        output.extend(target_data[start:end])
    return bytes(output)


def token_signature(token_rows: list[dict[str, str]]) -> str:
    return ".".join(f"{row.get('token_type', '')[0].upper()}{row.get('length', '0')}" for row in token_rows)


def target_summary(payload: dict[str, object], token_rows: list[dict[str, str]]) -> dict[str, str]:
    target = payload["target"]
    data = payload["data"]
    if not isinstance(target, dict) or not isinstance(data, bytes):
        return {}
    repeat_rows = [row for row in token_rows if row.get("token_type") == "repeat"]
    delta_rows = [row for row in token_rows if row.get("token_type") == "delta"]
    literal_rows = [row for row in token_rows if row.get("token_type") == "literal"]
    repeat_bytes = sum(int_value(row, "length") for row in repeat_rows)
    delta_bytes = sum(int_value(row, "length") for row in delta_rows)
    literal_bytes = sum(int_value(row, "length") for row in literal_rows)
    generated = sum(int_value(row, "generated_bytes") for row in token_rows)
    replay = replay_tokens(token_rows, data)
    exact = sum(1 for left, right in zip(replay, data) if left == right)
    verdict = "frontier80_structural_nonzero_rle_delta_parser_ready"
    if exact != len(data):
        verdict = "frontier80_structural_nonzero_rle_delta_parser_mismatch"
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
        "length": target.get("length", ""),
        "token_rows": str(len(token_rows)),
        "repeat_tokens": str(len(repeat_rows)),
        "repeat_bytes": str(repeat_bytes),
        "delta_tokens": str(len(delta_rows)),
        "delta_bytes": str(delta_bytes),
        "literal_tokens": str(len(literal_rows)),
        "literal_bytes": str(literal_bytes),
        "seed_bytes": str(len(token_rows)),
        "generated_bytes": str(generated),
        "generated_ratio": ratio(generated, len(data)),
        "max_token_bytes": str(max((int_value(row, "length") for row in token_rows), default=0)),
        "exact_replay_bytes": str(exact),
        "token_signature": token_signature(token_rows),
        "head_hex": data[:16].hex(),
        "tail_hex": data[-16:].hex(),
        "verdict": verdict,
        "next_probe": "map structural RLE/delta token plan to segment control bytes",
    }


def write_html(
    output: Path,
    title: str,
    summary: dict[str, str],
    target_rows: list[dict[str, str]],
    token_rows: list[dict[str, str]],
) -> None:
    data = {"summary": summary, "targets": target_rows, "tokens": token_rows}
    target_preview = "\n".join(
        "<tr>"
        + "".join(
            f"<td>{html.escape(row.get(field, ''))}</td>"
            for field in [
                "target_id",
                "length",
                "token_rows",
                "repeat_bytes",
                "delta_bytes",
                "literal_bytes",
                "generated_bytes",
                "verdict",
            ]
        )
        + "</tr>"
        for row in target_rows
    )
    token_preview = "\n".join(
        "<tr>"
        + "".join(
            f"<td>{html.escape(row.get(field, ''))}</td>"
            for field in ["token_index", "token_type", "run_offset_start", "length", "seed_hex", "delta_signature"]
        )
        + "</tr>"
        for row in token_rows[:80]
    )
    html_text = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{html.escape(title)}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 24px; color: #20242a; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 16px; }}
    th, td {{ border-bottom: 1px solid #d8dde5; padding: 6px 8px; text-align: left; font-size: 13px; }}
    th {{ background: #edf1f7; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }}
    .stat {{ border: 1px solid #d8dde5; border-radius: 6px; padding: 10px 12px; }}
    .label {{ color: #5c6675; font-size: 12px; }}
    .value {{ font-size: 20px; font-weight: 650; margin-top: 2px; }}
    .links a {{ margin-right: 12px; }}
  </style>
</head>
<body>
  <h1>{html.escape(title)}</h1>
  <div class="grid">
    <div class="stat"><div class="label">Target bytes</div><div class="value">{html.escape(summary['target_bytes'])}</div></div>
    <div class="stat"><div class="label">Token rows</div><div class="value">{html.escape(summary['token_rows'])}</div></div>
    <div class="stat"><div class="label">Generated bytes</div><div class="value">{html.escape(summary['generated_bytes'])}</div></div>
    <div class="stat"><div class="label">Literal bytes</div><div class="value">{html.escape(summary['literal_bytes'])}</div></div>
    <div class="stat"><div class="label">Verdict</div><div class="value">{html.escape(summary['review_verdict'])}</div></div>
  </div>
  <p class="links">
    <a href="{relative_href(output / 'summary.csv', output / 'index.html')}">summary.csv</a>
    <a href="{relative_href(output / 'targets.csv', output / 'index.html')}">targets.csv</a>
    <a href="{relative_href(output / 'tokens.csv', output / 'index.html')}">tokens.csv</a>
  </p>
  <h2>Targets</h2>
  <table>
    <thead><tr><th>target</th><th>length</th><th>tokens</th><th>repeat</th><th>delta</th><th>literal</th><th>generated</th><th>verdict</th></tr></thead>
    <tbody>{target_preview}</tbody>
  </table>
  <h2>Tokens</h2>
  <table>
    <thead><tr><th>#</th><th>type</th><th>offset</th><th>length</th><th>seed</th><th>deltas</th></tr></thead>
    <tbody>{token_preview}</tbody>
  </table>
  <script type="application/json" id="probe-data">{html.escape(json.dumps(data, ensure_ascii=True))}</script>
</body>
</html>
"""
    (output / "index.html").write_text(html_text)


def run(args: argparse.Namespace) -> dict[str, str]:
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    run_rows = read_csv(args.runs)
    manifest_rows = read_csv(args.manifest)
    clean_rows = read_csv(args.clean_fixtures)
    targets = select_largest_targets(run_rows, issues)
    payloads = load_target_payloads(targets, manifest_rows, clean_rows, issues)

    target_rows: list[dict[str, str]] = []
    token_rows: list[dict[str, str]] = []
    for payload in payloads:
        payload_tokens = build_token_rows(
            payload,
            min_repeat=args.min_repeat,
            min_delta=args.min_delta,
            max_delta=args.max_delta,
        )
        token_rows.extend(payload_tokens)
        row = target_summary(payload, payload_tokens)
        if row:
            target_rows.append(row)

    total_bytes = sum(int_value(row, "length") for row in target_rows)
    generated = sum(int_value(row, "generated_bytes") for row in target_rows)
    exact = sum(int_value(row, "exact_replay_bytes") for row in target_rows)
    repeat_tokens = sum(int_value(row, "repeat_tokens") for row in target_rows)
    delta_tokens = sum(int_value(row, "delta_tokens") for row in target_rows)
    literal_tokens = sum(int_value(row, "literal_tokens") for row in target_rows)
    repeat_bytes = sum(int_value(row, "repeat_bytes") for row in target_rows)
    delta_bytes = sum(int_value(row, "delta_bytes") for row in target_rows)
    literal_bytes = sum(int_value(row, "literal_bytes") for row in target_rows)
    verdict = "frontier80_structural_nonzero_rle_delta_parser_ready"
    if exact != total_bytes:
        verdict = "frontier80_structural_nonzero_rle_delta_parser_mismatch"
    summary = {
        "scope": "total",
        "target_runs": str(len(target_rows)),
        "target_bytes": str(total_bytes),
        "token_rows": str(len(token_rows)),
        "repeat_tokens": str(repeat_tokens),
        "repeat_bytes": str(repeat_bytes),
        "delta_tokens": str(delta_tokens),
        "delta_bytes": str(delta_bytes),
        "literal_tokens": str(literal_tokens),
        "literal_bytes": str(literal_bytes),
        "seed_bytes": str(sum(int_value(row, "seed_bytes") for row in target_rows)),
        "generated_bytes": str(generated),
        "generated_ratio": ratio(generated, total_bytes),
        "max_token_bytes": str(max((int_value(row, "max_token_bytes") for row in target_rows), default=0)),
        "exact_replay_bytes": str(exact),
        "issue_rows": str(len(issues)),
        "review_verdict": verdict,
        "next_probe": "map structural RLE/delta token plan to segment control bytes",
    }
    write_csv(output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output / "targets.csv", TARGET_FIELDNAMES, target_rows)
    write_csv(output / "tokens.csv", TOKEN_FIELDNAMES, token_rows)
    (output / "issues.txt").write_text("\n".join(issues))
    write_html(output, args.title, summary, target_rows, token_rows)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build RLE/delta token plans for structural Frontier80 nonzero runs.")
    parser.add_argument("--runs", type=Path, default=DEFAULT_RUNS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--clean-fixtures", type=Path, default=DEFAULT_CLEAN_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Structural Nonzero RLE/Delta Parser Probe",
    )
    parser.add_argument("--min-repeat", type=int, default=2)
    parser.add_argument("--min-delta", type=int, default=4)
    parser.add_argument("--max-delta", type=int, default=2)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = run(args)
    print(f"Target bytes: {summary['target_bytes']}")
    print(f"Token rows: {summary['token_rows']}")
    print(f"Generated bytes: {summary['generated_bytes']}")
    print(f"Literal bytes: {summary['literal_bytes']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
