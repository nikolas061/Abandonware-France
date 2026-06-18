#!/usr/bin/env python3
"""Test exact-byte selectors for Frontier80 low-payload role-pair candidates."""

from __future__ import annotations

import argparse
import html
import json
from collections import Counter
from pathlib import Path

from lolg_tex_gap_decoder_frontier80_context_split_residual_low_payload_neighborhood_probe import (
    TARGET_FIELDNAMES,
    load_target_runs,
    low_target_rows,
    read_csv,
    signed_delta,
    target_row_record,
)
from lolg_tex_gap_opcode_probe import int_value, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_frontier80_context_split_residual_low_payload_role_pair_selector_probe")
DEFAULT_RUNS = Path("output/tex_gap_decoder_unresolved_run_probe_frontier80_context_split_residual_second_replay/runs.csv")
DEFAULT_MANIFEST = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_CLEAN_FIXTURES = Path(
    "output/tex_gap_decoder_frontier80_context_split_residual_second_fixture_replay/fixtures.csv"
)
DEFAULT_CANDIDATES = Path(
    "output/tex_gap_decoder_frontier80_context_split_residual_low_payload_role_pair_transform_probe/candidates.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "target_runs",
    "target_rows",
    "target_bytes",
    "selected_rows",
    "low1_selected_rows",
    "low2_selected_rows",
    "identity_exact_bytes",
    "top_delta_exact_bytes",
    "role_position_consensus_exact_bytes",
    "role_position_consensus_leave_one_out_exact_bytes",
    "stable_position_rows",
    "low1_stable_positions",
    "low2_stable_positions",
    "low1_identity_exact_bytes",
    "low1_top_delta_exact_bytes",
    "low1_consensus_exact_bytes",
    "low1_leave_one_out_exact_bytes",
    "low2_identity_exact_bytes",
    "low2_top_delta_exact_bytes",
    "low2_consensus_exact_bytes",
    "low2_leave_one_out_exact_bytes",
    "source_known_min",
    "source_known_total",
    "promotion_ready_rows",
    "promotion_ready_bytes",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

SELECTED_FIELDNAMES = [
    "target_id",
    "row_role",
    "target_rank",
    "target_frontier_id",
    "target_start",
    "source_target_id",
    "source_row_role",
    "source_rank",
    "source_frontier_id",
    "source_start",
    "source_row_delta",
    "source_known_bytes",
    "identity_exact_bytes",
    "top_delta",
    "top_delta_exact_bytes",
    "role_position_consensus_exact_bytes",
    "role_position_consensus_leave_one_out_exact_bytes",
    "best_small_delta_le2_bytes",
    "best_small_delta_le4_bytes",
    "source_head_hex",
    "target_head_hex",
]

POSITION_FIELDNAMES = [
    "row_role",
    "position",
    "consensus_delta",
    "consensus_count",
    "sample_rows",
    "stable",
]


def row_target(row: dict[str, object]) -> dict[str, str]:
    target = row["target"]
    assert isinstance(target, dict)
    return target


def row_data(row: dict[str, object]) -> bytes:
    data = row["data"]
    assert isinstance(data, bytes)
    return data


def add_delta(value: int, delta: int) -> int:
    return (value + delta) & 0xFF


def load_rows(
    run_rows: list[dict[str, str]],
    manifest_rows: list[dict[str, str]],
    clean_rows: list[dict[str, str]],
    issues: list[str],
) -> tuple[list[tuple[dict[str, str], bytes, bytes]], list[dict[str, object]]]:
    target_runs = load_target_runs(run_rows, manifest_rows, clean_rows, issues)
    target_rows = low_target_rows(target_runs, issues)
    return target_runs, target_rows


def candidate_score(row: dict[str, str]) -> tuple[int, int, int, int]:
    return (
        int_value(row, "strong_pair"),
        int_value(row, "small_delta_le2_bytes"),
        int_value(row, "exact_bytes"),
        int_value(row, "small_delta_le4_bytes"),
    )


def select_best_candidates(candidate_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    best: dict[tuple[str, str], dict[str, str]] = {}
    for row in candidate_rows:
        key = row.get("target_id", ""), row.get("row_role", "")
        current = best.get(key)
        if current is None or candidate_score(row) > candidate_score(current):
            best[key] = row
    return sorted(best.values(), key=lambda row: (row.get("row_role", ""), row.get("target_id", "")))


def source_bytes_for_candidate(
    candidate: dict[str, str],
    row_by_key: dict[tuple[str, str], dict[str, object]],
) -> bytes:
    source_key = candidate.get("source_target_id", ""), candidate.get("source_row_role", "")
    source_row = row_by_key[source_key]
    expected = source_row["expected"]
    assert isinstance(expected, bytes)
    source_start = int_value(candidate, "source_start")
    return expected[source_start : source_start + 32]


def known_bytes_for_candidate(
    candidate: dict[str, str],
    row_by_key: dict[tuple[str, str], dict[str, object]],
) -> int:
    source_key = candidate.get("source_target_id", ""), candidate.get("source_row_role", "")
    source_row = row_by_key[source_key]
    known_mask = source_row["known_mask"]
    assert isinstance(known_mask, bytes)
    source_start = int_value(candidate, "source_start")
    return sum(1 for value in known_mask[source_start : source_start + 32] if value)


def build_samples(
    selected_candidates: list[dict[str, str]],
    target_rows: list[dict[str, object]],
    issues: list[str],
) -> list[dict[str, object]]:
    row_by_key = {(row_target(row).get("target_id", ""), str(row.get("row_role", ""))): row for row in target_rows}
    samples: list[dict[str, object]] = []
    for candidate in selected_candidates:
        key = candidate.get("target_id", ""), candidate.get("row_role", "")
        target_row = row_by_key.get(key)
        source_key = candidate.get("source_target_id", ""), candidate.get("source_row_role", "")
        if target_row is None:
            issues.append(f"{key}:missing_target_row")
            continue
        if source_key not in row_by_key:
            issues.append(f"{key}:missing_source_row:{source_key}")
            continue
        source = source_bytes_for_candidate(candidate, row_by_key)
        if len(source) != 32:
            issues.append(f"{key}:source_window_short")
            continue
        target = row_data(target_row)
        deltas = [signed_delta(source_value, target_value) for source_value, target_value in zip(source, target)]
        top_delta, top_delta_count = Counter(deltas).most_common(1)[0]
        samples.append(
            {
                "candidate": candidate,
                "target_row": target_row,
                "source": source,
                "target": target,
                "deltas": deltas,
                "top_delta": top_delta,
                "top_delta_count": top_delta_count,
                "source_known_bytes": known_bytes_for_candidate(candidate, row_by_key),
            }
        )
    return samples


def role_position_consensus(samples: list[dict[str, object]]) -> tuple[list[dict[str, str]], dict[str, list[int]]]:
    role_samples: dict[str, list[dict[str, object]]] = {}
    for sample in samples:
        candidate = sample["candidate"]
        assert isinstance(candidate, dict)
        role_samples.setdefault(candidate.get("row_role", ""), []).append(sample)
    position_rows: list[dict[str, str]] = []
    consensus_by_role: dict[str, list[int]] = {}
    for role, rows in sorted(role_samples.items()):
        consensus: list[int] = []
        for position in range(32):
            counter: Counter[int] = Counter()
            for row in rows:
                deltas = row["deltas"]
                assert isinstance(deltas, list)
                counter[int(deltas[position])] += 1
            delta, count = counter.most_common(1)[0]
            consensus.append(delta)
            position_rows.append(
                {
                    "row_role": role,
                    "position": str(position),
                    "consensus_delta": str(delta),
                    "consensus_count": str(count),
                    "sample_rows": str(len(rows)),
                    "stable": "1" if count == len(rows) else "0",
                }
            )
        consensus_by_role[role] = consensus
    return position_rows, consensus_by_role


def leave_one_out_consensus_delta(
    role_samples: list[dict[str, object]],
    held_out_index: int,
    position: int,
) -> int:
    counter: Counter[int] = Counter()
    for index, sample in enumerate(role_samples):
        if index == held_out_index:
            continue
        deltas = sample["deltas"]
        assert isinstance(deltas, list)
        counter[int(deltas[position])] += 1
    if not counter:
        return 0
    return counter.most_common(1)[0][0]


def exact_with_deltas(source: bytes, target: bytes, deltas: list[int]) -> int:
    return sum(1 for position, source_value in enumerate(source) if add_delta(source_value, deltas[position]) == target[position])


def build_selected_rows(
    samples: list[dict[str, object]],
    consensus_by_role: dict[str, list[int]],
) -> list[dict[str, str]]:
    samples_by_role: dict[str, list[dict[str, object]]] = {}
    for sample in samples:
        candidate = sample["candidate"]
        assert isinstance(candidate, dict)
        samples_by_role.setdefault(candidate.get("row_role", ""), []).append(sample)

    rows: list[dict[str, str]] = []
    for role, role_samples in samples_by_role.items():
        for index, sample in enumerate(role_samples):
            candidate = sample["candidate"]
            source = sample["source"]
            target = sample["target"]
            assert isinstance(candidate, dict)
            assert isinstance(source, bytes)
            assert isinstance(target, bytes)
            consensus = consensus_by_role.get(role, [0] * 32)
            loo_consensus = [
                leave_one_out_consensus_delta(role_samples, index, position) for position in range(len(source))
            ]
            identity_exact = sum(1 for source_value, target_value in zip(source, target) if source_value == target_value)
            rows.append(
                {
                    "target_id": candidate.get("target_id", ""),
                    "row_role": candidate.get("row_role", ""),
                    "target_rank": candidate.get("target_rank", ""),
                    "target_frontier_id": candidate.get("target_frontier_id", ""),
                    "target_start": candidate.get("target_start", ""),
                    "source_target_id": candidate.get("source_target_id", ""),
                    "source_row_role": candidate.get("source_row_role", ""),
                    "source_rank": candidate.get("source_rank", ""),
                    "source_frontier_id": candidate.get("source_frontier_id", ""),
                    "source_start": candidate.get("source_start", ""),
                    "source_row_delta": candidate.get("source_row_delta", ""),
                    "source_known_bytes": str(sample["source_known_bytes"]),
                    "identity_exact_bytes": str(identity_exact),
                    "top_delta": str(sample["top_delta"]),
                    "top_delta_exact_bytes": str(sample["top_delta_count"]),
                    "role_position_consensus_exact_bytes": str(exact_with_deltas(source, target, consensus)),
                    "role_position_consensus_leave_one_out_exact_bytes": str(
                        exact_with_deltas(source, target, loo_consensus)
                    ),
                    "best_small_delta_le2_bytes": candidate.get("small_delta_le2_bytes", "0"),
                    "best_small_delta_le4_bytes": candidate.get("small_delta_le4_bytes", "0"),
                    "source_head_hex": source[:16].hex(),
                    "target_head_hex": target[:16].hex(),
                }
            )
    rows.sort(key=lambda row: (row.get("row_role", ""), row.get("target_id", "")))
    return rows


def sum_field(rows: list[dict[str, str]], field: str) -> int:
    return sum(int_value(row, field) for row in rows)


def build_summary(
    *,
    target_runs: int,
    target_rows: list[dict[str, object]],
    selected_rows: list[dict[str, str]],
    position_rows: list[dict[str, str]],
    issues: list[str],
) -> dict[str, str]:
    low1_rows = [row for row in selected_rows if row.get("row_role") == "low1"]
    low2_rows = [row for row in selected_rows if row.get("row_role") == "low2"]
    low1_positions = [row for row in position_rows if row.get("row_role") == "low1"]
    low2_positions = [row for row in position_rows if row.get("row_role") == "low2"]
    known_values = [int_value(row, "source_known_bytes") for row in selected_rows]
    promotion_ready_rows = sum(
        1 for row in selected_rows if int_value(row, "role_position_consensus_leave_one_out_exact_bytes") == 32
    )
    promotion_ready_bytes = promotion_ready_rows * 32
    if promotion_ready_rows == len(selected_rows) and selected_rows:
        verdict = "frontier80_context_residual_low_payload_selector_ready"
        next_probe = "promote guarded low-payload row-role selector"
    else:
        verdict = "frontier80_context_residual_low_payload_selector_no_stable_transform"
        next_probe = "profile opcode/control context for low-payload residual rows"
    return {
        "scope": "total",
        "target_runs": str(target_runs),
        "target_rows": str(len(target_rows)),
        "target_bytes": str(len(target_rows) * 32),
        "selected_rows": str(len(selected_rows)),
        "low1_selected_rows": str(len(low1_rows)),
        "low2_selected_rows": str(len(low2_rows)),
        "identity_exact_bytes": str(sum_field(selected_rows, "identity_exact_bytes")),
        "top_delta_exact_bytes": str(sum_field(selected_rows, "top_delta_exact_bytes")),
        "role_position_consensus_exact_bytes": str(sum_field(selected_rows, "role_position_consensus_exact_bytes")),
        "role_position_consensus_leave_one_out_exact_bytes": str(
            sum_field(selected_rows, "role_position_consensus_leave_one_out_exact_bytes")
        ),
        "stable_position_rows": str(sum(int_value(row, "stable") for row in position_rows)),
        "low1_stable_positions": str(sum(int_value(row, "stable") for row in low1_positions)),
        "low2_stable_positions": str(sum(int_value(row, "stable") for row in low2_positions)),
        "low1_identity_exact_bytes": str(sum_field(low1_rows, "identity_exact_bytes")),
        "low1_top_delta_exact_bytes": str(sum_field(low1_rows, "top_delta_exact_bytes")),
        "low1_consensus_exact_bytes": str(sum_field(low1_rows, "role_position_consensus_exact_bytes")),
        "low1_leave_one_out_exact_bytes": str(sum_field(low1_rows, "role_position_consensus_leave_one_out_exact_bytes")),
        "low2_identity_exact_bytes": str(sum_field(low2_rows, "identity_exact_bytes")),
        "low2_top_delta_exact_bytes": str(sum_field(low2_rows, "top_delta_exact_bytes")),
        "low2_consensus_exact_bytes": str(sum_field(low2_rows, "role_position_consensus_exact_bytes")),
        "low2_leave_one_out_exact_bytes": str(sum_field(low2_rows, "role_position_consensus_leave_one_out_exact_bytes")),
        "source_known_min": str(min(known_values, default=0)),
        "source_known_total": str(sum(known_values)),
        "promotion_ready_rows": str(promotion_ready_rows),
        "promotion_ready_bytes": str(promotion_ready_bytes),
        "issue_rows": str(len(issues)),
        "review_verdict": verdict,
        "next_probe": next_probe,
    }


def table_html(title: str, filename: str, rows: list[dict[str, str]], fields: list[str], limit: int = 24) -> str:
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
    targets: list[dict[str, str]],
    selected_rows: list[dict[str, str]],
    position_rows: list[dict[str, str]],
    title: str,
) -> str:
    summary_json = html.escape(json.dumps(summary, indent=2))
    stats = "".join(
        f"<div class=\"stat\"><div class=\"label\">{html.escape(key)}</div>"
        f"<div class=\"value\">{html.escape(summary.get(key, ''))}</div></div>"
        for key in (
            "identity_exact_bytes",
            "top_delta_exact_bytes",
            "role_position_consensus_leave_one_out_exact_bytes",
            "stable_position_rows",
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
  {table_html("Selected candidates", "selected_candidates.csv", selected_rows, SELECTED_FIELDNAMES)}
  {table_html("Role-position consensus", "position_consensus.csv", position_rows, POSITION_FIELDNAMES)}
  {table_html("Targets", "targets.csv", targets, TARGET_FIELDNAMES)}
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Test exact-byte selector candidates for Frontier80 low-payload role-pair transforms."
    )
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--runs", type=Path, default=DEFAULT_RUNS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--clean-fixtures", type=Path, default=DEFAULT_CLEAN_FIXTURES)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Low Payload Role-Pair Selector Probe",
    )
    args = parser.parse_args()

    issues: list[str] = []
    run_rows = read_csv(args.runs)
    manifest_rows = read_csv(args.manifest)
    clean_rows = read_csv(args.clean_fixtures)
    candidate_rows = read_csv(args.candidates)
    target_runs, target_rows = load_rows(run_rows, manifest_rows, clean_rows, issues)
    selected_candidates = select_best_candidates(candidate_rows)
    samples = build_samples(selected_candidates, target_rows, issues)
    position_rows, consensus_by_role = role_position_consensus(samples)
    selected_rows = build_selected_rows(samples, consensus_by_role)
    targets = [target_row_record(row) for row in target_rows]
    summary = build_summary(
        target_runs=len(target_runs),
        target_rows=target_rows,
        selected_rows=selected_rows,
        position_rows=position_rows,
        issues=issues,
    )

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, targets)
    write_csv(args.output / "selected_candidates.csv", SELECTED_FIELDNAMES, selected_rows)
    write_csv(args.output / "position_consensus.csv", POSITION_FIELDNAMES, position_rows)
    (args.output / "issues.txt").write_text("\n".join(issues))
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, targets, selected_rows, position_rows, args.title))

    print(f"Selected rows: {summary['selected_rows']}")
    print(
        "Exact bytes: "
        f"identity={summary['identity_exact_bytes']}, "
        f"top_delta={summary['top_delta_exact_bytes']}, "
        f"loo_consensus={summary['role_position_consensus_leave_one_out_exact_bytes']}/"
        f"{summary['target_bytes']}"
    )
    print(f"Stable positions: {summary['stable_position_rows']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
