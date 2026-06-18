#!/usr/bin/env python3
"""Probe compact-control row-state deltas from local high-row context."""

from __future__ import annotations

import argparse
import html
import json
from collections import Counter
from pathlib import Path

from lolg_tex_gap_decoder_frontier80_context_split_residual_low_payload_neighborhood_probe import (
    byte_class,
    load_target_runs,
    read_csv,
    signed_delta,
)
from lolg_tex_gap_opcode_probe import int_value, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_frontier80_context_split_residual_low_payload_row_state_probe")
DEFAULT_RUNS = Path("output/tex_gap_decoder_unresolved_run_probe_frontier80_context_split_residual_second_replay/runs.csv")
DEFAULT_MANIFEST = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_CLEAN_FIXTURES = Path(
    "output/tex_gap_decoder_frontier80_context_split_residual_second_fixture_replay/fixtures.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "target_runs",
    "row0_rows",
    "row0_bytes",
    "pre_source_known_min",
    "pre_source_known_total",
    "row0_known_total",
    "local_exact_bytes",
    "local_small_delta_le1_bytes",
    "local_small_delta_le2_bytes",
    "local_small_delta_le4_bytes",
    "local_small_delta_le2_min",
    "local_small_delta_le4_min",
    "known_source_exact_bytes",
    "known_source_small_delta_le2_bytes",
    "known_source_small_delta_le4_bytes",
    "dominant_delta_exact_bytes",
    "position_consensus_exact_bytes",
    "position_consensus_leave_one_out_exact_bytes",
    "stable_position_rows",
    "promotion_ready_rows",
    "promotion_ready_bytes",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

ROW_FIELDNAMES = [
    "target_id",
    "rank",
    "pcx_name",
    "frontier_id",
    "run_start",
    "row0_start",
    "pre_source_start",
    "pre_source_known_bytes",
    "row0_known_bytes",
    "pre_source_high_plateau_bytes",
    "row0_high_plateau_bytes",
    "exact_bytes",
    "small_delta_le1_bytes",
    "small_delta_le2_bytes",
    "small_delta_le4_bytes",
    "known_source_exact_bytes",
    "known_source_small_delta_le2_bytes",
    "known_source_small_delta_le4_bytes",
    "top_delta",
    "top_delta_count",
    "position_consensus_exact_bytes",
    "position_consensus_leave_one_out_exact_bytes",
    "pre_source_head_hex",
    "row0_head_hex",
]

POSITION_FIELDNAMES = [
    "position",
    "consensus_delta",
    "consensus_count",
    "sample_rows",
    "stable",
]


def count_high(data: bytes) -> int:
    return sum(1 for value in data if byte_class(value) == "high_plateau")


def add_delta(value: int, delta: int) -> int:
    return (value + delta) & 0xFF


def sample_rows(target_runs: list[tuple[dict[str, str], bytes, bytes]], issues: list[str]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for target, expected, known_mask in target_runs:
        run_start = int_value(target, "start")
        run_end = int_value(target, "end")
        if run_end - run_start < 96:
            issues.append(f"{target.get('target_id', '')}:run_shorter_than_96")
            continue
        pre_start = run_start - 32
        if pre_start < 0:
            issues.append(f"{target.get('target_id', '')}:pre_source_out_of_bounds")
            continue
        pre_source = expected[pre_start:run_start]
        row0 = expected[run_start : run_start + 32]
        pre_known = known_mask[pre_start:run_start]
        row0_known = known_mask[run_start : run_start + 32]
        if len(pre_source) != 32 or len(row0) != 32:
            issues.append(f"{target.get('target_id', '')}:row0_or_pre_source_short")
            continue
        deltas = [signed_delta(source_value, target_value) for source_value, target_value in zip(pre_source, row0)]
        rows.append(
            {
                "target": target,
                "pre_start": pre_start,
                "row0_start": run_start,
                "pre_source": pre_source,
                "row0": row0,
                "pre_known": pre_known,
                "row0_known": row0_known,
                "deltas": deltas,
            }
        )
    return rows


def consensus_rows(samples: list[dict[str, object]]) -> tuple[list[dict[str, str]], list[int]]:
    rows: list[dict[str, str]] = []
    consensus: list[int] = []
    for position in range(32):
        counter: Counter[int] = Counter()
        for sample in samples:
            deltas = sample["deltas"]
            assert isinstance(deltas, list)
            counter[int(deltas[position])] += 1
        delta, count = counter.most_common(1)[0] if counter else (0, 0)
        consensus.append(delta)
        rows.append(
            {
                "position": str(position),
                "consensus_delta": str(delta),
                "consensus_count": str(count),
                "sample_rows": str(len(samples)),
                "stable": "1" if count == len(samples) and samples else "0",
            }
        )
    return rows, consensus


def leave_one_out_delta(samples: list[dict[str, object]], held_out_index: int, position: int) -> int:
    counter: Counter[int] = Counter()
    for index, sample in enumerate(samples):
        if index == held_out_index:
            continue
        deltas = sample["deltas"]
        assert isinstance(deltas, list)
        counter[int(deltas[position])] += 1
    return counter.most_common(1)[0][0] if counter else 0


def exact_with_deltas(source: bytes, target: bytes, deltas: list[int]) -> int:
    return sum(1 for position, value in enumerate(source) if add_delta(value, deltas[position]) == target[position])


def build_row_records(samples: list[dict[str, object]], consensus: list[int]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for index, sample in enumerate(samples):
        target = sample["target"]
        pre_source = sample["pre_source"]
        row0 = sample["row0"]
        pre_known = sample["pre_known"]
        row0_known = sample["row0_known"]
        deltas = sample["deltas"]
        assert isinstance(target, dict)
        assert isinstance(pre_source, bytes)
        assert isinstance(row0, bytes)
        assert isinstance(pre_known, bytes)
        assert isinstance(row0_known, bytes)
        assert isinstance(deltas, list)
        abs_deltas = [abs(int(delta)) for delta in deltas]
        known_positions = [position for position, value in enumerate(pre_known) if value]
        top_delta, top_delta_count = Counter(int(delta) for delta in deltas).most_common(1)[0]
        loo_consensus = [leave_one_out_delta(samples, index, position) for position in range(32)]
        rows.append(
            {
                "target_id": target.get("target_id", ""),
                "rank": target.get("rank", ""),
                "pcx_name": target.get("pcx_name", ""),
                "frontier_id": target.get("frontier_id", ""),
                "run_start": target.get("start", ""),
                "row0_start": str(sample["row0_start"]),
                "pre_source_start": str(sample["pre_start"]),
                "pre_source_known_bytes": str(sum(1 for value in pre_known if value)),
                "row0_known_bytes": str(sum(1 for value in row0_known if value)),
                "pre_source_high_plateau_bytes": str(count_high(pre_source)),
                "row0_high_plateau_bytes": str(count_high(row0)),
                "exact_bytes": str(sum(1 for delta in deltas if delta == 0)),
                "small_delta_le1_bytes": str(sum(1 for delta in abs_deltas if delta <= 1)),
                "small_delta_le2_bytes": str(sum(1 for delta in abs_deltas if delta <= 2)),
                "small_delta_le4_bytes": str(sum(1 for delta in abs_deltas if delta <= 4)),
                "known_source_exact_bytes": str(sum(1 for position in known_positions if deltas[position] == 0)),
                "known_source_small_delta_le2_bytes": str(
                    sum(1 for position in known_positions if abs_deltas[position] <= 2)
                ),
                "known_source_small_delta_le4_bytes": str(
                    sum(1 for position in known_positions if abs_deltas[position] <= 4)
                ),
                "top_delta": str(top_delta),
                "top_delta_count": str(top_delta_count),
                "position_consensus_exact_bytes": str(exact_with_deltas(pre_source, row0, consensus)),
                "position_consensus_leave_one_out_exact_bytes": str(
                    exact_with_deltas(pre_source, row0, loo_consensus)
                ),
                "pre_source_head_hex": pre_source[:16].hex(),
                "row0_head_hex": row0[:16].hex(),
            }
        )
    rows.sort(key=lambda row: (int_value(row, "rank"), int_value(row, "run_start")))
    return rows


def sum_field(rows: list[dict[str, str]], field: str) -> int:
    return sum(int_value(row, field) for row in rows)


def build_summary(
    row_records: list[dict[str, str]],
    position_rows: list[dict[str, str]],
    issues: list[str],
) -> dict[str, str]:
    source_known_values = [int_value(row, "pre_source_known_bytes") for row in row_records]
    le2_values = [int_value(row, "small_delta_le2_bytes") for row in row_records]
    le4_values = [int_value(row, "small_delta_le4_bytes") for row in row_records]
    promotion_ready_rows = sum(
        1 for row in row_records if int_value(row, "position_consensus_leave_one_out_exact_bytes") == 32
    )
    local_signal = min(le2_values, default=0) >= 30 and min(le4_values, default=0) == 32
    source_complete = min(source_known_values, default=0) == 32
    if local_signal and not source_complete:
        verdict = "frontier80_context_residual_low_payload_row_state_source_prereq_needed"
        next_probe = "derive source-byte prerequisites for compact-control row-state high-row context"
    elif local_signal and promotion_ready_rows == len(row_records) and row_records:
        verdict = "frontier80_context_residual_low_payload_row_state_selector_ready"
        next_probe = "promote guarded compact-control row-state high-row decoder"
    elif local_signal:
        verdict = "frontier80_context_residual_low_payload_row_state_delta_signal"
        next_probe = "derive exact delta selector for compact-control row-state high-row context"
    else:
        verdict = "frontier80_context_residual_low_payload_row_state_weak"
        next_probe = "broaden compact-control row-state source search"
    return {
        "scope": "total",
        "target_runs": str(len(row_records)),
        "row0_rows": str(len(row_records)),
        "row0_bytes": str(len(row_records) * 32),
        "pre_source_known_min": str(min(source_known_values, default=0)),
        "pre_source_known_total": str(sum(source_known_values)),
        "row0_known_total": str(sum_field(row_records, "row0_known_bytes")),
        "local_exact_bytes": str(sum_field(row_records, "exact_bytes")),
        "local_small_delta_le1_bytes": str(sum_field(row_records, "small_delta_le1_bytes")),
        "local_small_delta_le2_bytes": str(sum_field(row_records, "small_delta_le2_bytes")),
        "local_small_delta_le4_bytes": str(sum_field(row_records, "small_delta_le4_bytes")),
        "local_small_delta_le2_min": str(min(le2_values, default=0)),
        "local_small_delta_le4_min": str(min(le4_values, default=0)),
        "known_source_exact_bytes": str(sum_field(row_records, "known_source_exact_bytes")),
        "known_source_small_delta_le2_bytes": str(sum_field(row_records, "known_source_small_delta_le2_bytes")),
        "known_source_small_delta_le4_bytes": str(sum_field(row_records, "known_source_small_delta_le4_bytes")),
        "dominant_delta_exact_bytes": str(sum_field(row_records, "top_delta_count")),
        "position_consensus_exact_bytes": str(sum_field(row_records, "position_consensus_exact_bytes")),
        "position_consensus_leave_one_out_exact_bytes": str(
            sum_field(row_records, "position_consensus_leave_one_out_exact_bytes")
        ),
        "stable_position_rows": str(sum(int_value(row, "stable") for row in position_rows)),
        "promotion_ready_rows": str(promotion_ready_rows),
        "promotion_ready_bytes": str(promotion_ready_rows * 32),
        "issue_rows": str(len(issues)),
        "review_verdict": verdict,
        "next_probe": next_probe,
    }


def table_html(title: str, filename: str, rows: list[dict[str, str]], fields: list[str], limit: int = 48) -> str:
    if not rows:
        return f"<section><h2>{html.escape(title)}</h2><p>No rows.</p></section>"
    headers = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = []
    for row in rows[:limit]:
        body.append("<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>")
    return (
        f"<section><h2>{html.escape(title)}</h2><p><a href=\"{html.escape(filename)}\">"
        f"{html.escape(filename)}</a></p><table><thead><tr>{headers}</tr></thead>"
        f"<tbody>{''.join(body)}</tbody></table></section>"
    )


def build_html(
    summary: dict[str, str],
    row_records: list[dict[str, str]],
    position_rows: list[dict[str, str]],
    title: str,
) -> str:
    summary_json = html.escape(json.dumps(summary, indent=2))
    stats = "".join(
        f"<div class=\"stat\"><div class=\"label\">{html.escape(key)}</div>"
        f"<div class=\"value\">{html.escape(summary.get(key, ''))}</div></div>"
        for key in (
            "pre_source_known_min",
            "local_small_delta_le2_min",
            "local_small_delta_le4_min",
            "position_consensus_leave_one_out_exact_bytes",
            "promotion_ready_bytes",
            "review_verdict",
        )
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{html.escape(title)}</title>
  <style>
    body {{ font-family: sans-serif; margin: 24px; color: #1f2933; }}
    .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }}
    .stat {{ border: 1px solid #d8dee4; border-radius: 6px; padding: 10px; background: #f8fafc; }}
    .label {{ font-size: 12px; color: #52606d; }}
    .value {{ font-weight: 700; overflow-wrap: anywhere; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 12px; margin-top: 8px; }}
    th, td {{ border: 1px solid #d8dee4; padding: 4px 6px; text-align: left; vertical-align: top; }}
    th {{ background: #eef2f7; }}
    pre {{ background: #f6f8fa; padding: 12px; overflow: auto; }}
  </style>
</head>
<body>
  <h1>{html.escape(title)}</h1>
  <div class="stats">{stats}</div>
  <h2>Summary</h2>
  <pre>{summary_json}</pre>
  {table_html("Row-state candidates", "row_state_rows.csv", row_records, ROW_FIELDNAMES)}
  {table_html("Position consensus", "position_consensus.csv", position_rows, POSITION_FIELDNAMES)}
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Probe compact-control row-state deltas from local high-row context."
    )
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--runs", type=Path, default=DEFAULT_RUNS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--clean-fixtures", type=Path, default=DEFAULT_CLEAN_FIXTURES)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Low Payload Row-State Probe",
    )
    args = parser.parse_args()

    issues: list[str] = []
    run_rows = read_csv(args.runs)
    manifest_rows = read_csv(args.manifest)
    clean_rows = read_csv(args.clean_fixtures)
    target_runs = load_target_runs(run_rows, manifest_rows, clean_rows, issues)
    samples = sample_rows(target_runs, issues)
    position_rows, consensus = consensus_rows(samples)
    row_records = build_row_records(samples, consensus)
    summary = build_summary(row_records, position_rows, issues)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "row_state_rows.csv", ROW_FIELDNAMES, row_records)
    write_csv(args.output / "position_consensus.csv", POSITION_FIELDNAMES, position_rows)
    (args.output / "issues.txt").write_text("\n".join(issues))
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, row_records, position_rows, args.title))

    print(
        "Local delta: "
        f"le2_min={summary['local_small_delta_le2_min']}, "
        f"le4_min={summary['local_small_delta_le4_min']}, "
        f"source_known_min={summary['pre_source_known_min']}"
    )
    print(
        "Exact selectors: "
        f"dominant={summary['dominant_delta_exact_bytes']}, "
        f"loo={summary['position_consensus_leave_one_out_exact_bytes']}/"
        f"{summary['row0_bytes']}"
    )
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
