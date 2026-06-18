#!/usr/bin/env python3
"""Find source-byte prerequisites for compact-control row-state high rows."""

from __future__ import annotations

import argparse
import html
import json
from collections import Counter
from pathlib import Path

from lolg_tex_gap_decoder_frontier80_context_split_residual_low_payload_neighborhood_probe import (
    byte_class,
    fixture_key,
    load_target_runs,
    read_csv,
    signed_delta,
)
from lolg_tex_gap_opcode_probe import int_value, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_frontier80_context_split_residual_low_payload_row_state_source_prereq_probe")
DEFAULT_RUNS = Path("output/tex_gap_decoder_unresolved_run_probe_frontier80_context_split_residual_second_replay/runs.csv")
DEFAULT_MANIFEST = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_CLEAN_FIXTURES = Path(
    "output/tex_gap_decoder_frontier80_context_split_residual_second_fixture_replay/fixtures.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "target_source_rows",
    "source_bytes",
    "known_source_bytes",
    "missing_source_bytes",
    "support_windows",
    "candidate_rows",
    "target_rows_with_full_missing_support",
    "target_rows_without_full_missing_support",
    "best_missing_known_total",
    "best_missing_exact_total",
    "best_missing_small_delta_le2_total",
    "best_missing_small_delta_le4_total",
    "best_missing_exact_min",
    "best_missing_exact_ratio_min",
    "best_full_row_small_delta_le2_min",
    "best_full_row_small_delta_le4_min",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

TARGET_FIELDNAMES = [
    "target_id",
    "rank",
    "pcx_name",
    "frontier_id",
    "run_start",
    "pre_source_start",
    "known_source_bytes",
    "missing_source_bytes",
    "missing_positions",
    "pre_source_head_hex",
]

CANDIDATE_FIELDNAMES = [
    "target_id",
    "rank",
    "frontier_id",
    "pre_source_start",
    "missing_source_bytes",
    "support_rank",
    "support_pcx_name",
    "support_frontier_id",
    "support_start",
    "support_known_bytes",
    "support_high_plateau_bytes",
    "missing_known_bytes",
    "missing_exact_bytes",
    "missing_small_delta_le1_bytes",
    "missing_small_delta_le2_bytes",
    "missing_small_delta_le4_bytes",
    "full_exact_bytes",
    "full_small_delta_le2_bytes",
    "full_small_delta_le4_bytes",
    "top_delta",
    "top_delta_count",
    "same_fixture",
    "relative_offset",
    "support_head_hex",
    "target_head_hex",
]

COVERAGE_FIELDNAMES = [
    "target_id",
    "rank",
    "frontier_id",
    "pre_source_start",
    "known_source_bytes",
    "missing_source_bytes",
    "candidate_rows",
    "full_missing_support_candidate_rows",
    "best_support_rank",
    "best_support_frontier_id",
    "best_support_start",
    "best_missing_known_bytes",
    "best_missing_exact_bytes",
    "best_missing_small_delta_le2_bytes",
    "best_missing_small_delta_le4_bytes",
    "best_full_small_delta_le2_bytes",
    "best_full_small_delta_le4_bytes",
]


def load_bytes(path_text: str, issues: list[str], label: str, key: tuple[str, str, str]) -> bytes:
    try:
        return Path(path_text).read_bytes()
    except OSError as exc:
        issues.append(f"{key}:{label}:read_failed:{exc}")
        return b""


def count_high(data: bytes) -> int:
    return sum(1 for value in data if byte_class(value) == "high_plateau")


def target_source_rows(target_runs: list[tuple[dict[str, str], bytes, bytes]], issues: list[str]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for target, expected, known_mask in target_runs:
        run_start = int_value(target, "start")
        pre_start = run_start - 32
        if pre_start < 0:
            issues.append(f"{target.get('target_id', '')}:pre_source_out_of_bounds")
            continue
        source = expected[pre_start:run_start]
        mask = known_mask[pre_start:run_start]
        if len(source) != 32 or len(mask) != 32:
            issues.append(f"{target.get('target_id', '')}:pre_source_short")
            continue
        missing = [position for position, value in enumerate(mask) if not value]
        rows.append(
            {
                "target": target,
                "source": source,
                "mask": mask,
                "pre_start": pre_start,
                "missing": missing,
            }
        )
    return rows


def target_record(row: dict[str, object]) -> dict[str, str]:
    target = row["target"]
    source = row["source"]
    mask = row["mask"]
    missing = row["missing"]
    assert isinstance(target, dict)
    assert isinstance(source, bytes)
    assert isinstance(mask, bytes)
    assert isinstance(missing, list)
    return {
        "target_id": target.get("target_id", ""),
        "rank": target.get("rank", ""),
        "pcx_name": target.get("pcx_name", ""),
        "frontier_id": target.get("frontier_id", ""),
        "run_start": target.get("start", ""),
        "pre_source_start": str(row["pre_start"]),
        "known_source_bytes": str(sum(1 for value in mask if value)),
        "missing_source_bytes": str(len(missing)),
        "missing_positions": ";".join(str(position) for position in missing),
        "pre_source_head_hex": source[:16].hex(),
    }


def support_windows(
    manifest_rows: list[dict[str, str]],
    clean_rows: list[dict[str, str]],
    issues: list[str],
    *,
    min_known: int,
    min_high: int,
) -> list[dict[str, object]]:
    clean_by_key = {fixture_key(row): row for row in clean_rows}
    rows: list[dict[str, object]] = []
    for manifest in manifest_rows:
        key = fixture_key(manifest)
        clean = clean_by_key.get(key)
        if not clean:
            continue
        expected = load_bytes(manifest.get("expected_gap_path", ""), issues, "expected", key)
        known_mask = load_bytes(clean.get("known_mask_path", ""), issues, "known_mask", key)
        for start in range(0, max(0, len(expected) - 31)):
            data = expected[start : start + 32]
            mask = known_mask[start : start + 32]
            if len(data) != 32 or len(mask) != 32:
                continue
            known = sum(1 for value in mask if value)
            high = count_high(data)
            if known < min_known or high < min_high:
                continue
            rows.append(
                {
                    "manifest": manifest,
                    "start": start,
                    "data": data,
                    "mask": mask,
                    "known": known,
                    "high": high,
                }
            )
    return rows


def score_candidate(target_row: dict[str, object], support: dict[str, object]) -> dict[str, str] | None:
    target = target_row["target"]
    target_source = target_row["source"]
    missing = target_row["missing"]
    support_manifest = support["manifest"]
    support_data = support["data"]
    support_mask = support["mask"]
    assert isinstance(target, dict)
    assert isinstance(target_source, bytes)
    assert isinstance(missing, list)
    assert isinstance(support_manifest, dict)
    assert isinstance(support_data, bytes)
    assert isinstance(support_mask, bytes)
    pre_start = int(target_row["pre_start"])
    support_start = int(support["start"])
    same_fixture = fixture_key(target) == fixture_key(support_manifest)
    if same_fixture and max(support_start, pre_start) < min(support_start + 32, pre_start + 32):
        return None
    deltas = [signed_delta(source_value, target_value) for source_value, target_value in zip(support_data, target_source)]
    abs_deltas = [abs(delta) for delta in deltas]
    missing_known = sum(1 for position in missing if support_mask[position])
    if missing_known == 0:
        return None
    missing_exact = sum(1 for position in missing if support_mask[position] and deltas[position] == 0)
    missing_le1 = sum(1 for position in missing if support_mask[position] and abs_deltas[position] <= 1)
    missing_le2 = sum(1 for position in missing if support_mask[position] and abs_deltas[position] <= 2)
    missing_le4 = sum(1 for position in missing if support_mask[position] and abs_deltas[position] <= 4)
    full_exact = sum(1 for delta in deltas if delta == 0)
    full_le2 = sum(1 for delta in abs_deltas if delta <= 2)
    full_le4 = sum(1 for delta in abs_deltas if delta <= 4)
    top_delta, top_count = Counter(deltas).most_common(1)[0]
    return {
        "target_id": target.get("target_id", ""),
        "rank": target.get("rank", ""),
        "frontier_id": target.get("frontier_id", ""),
        "pre_source_start": str(pre_start),
        "missing_source_bytes": str(len(missing)),
        "support_rank": support_manifest.get("rank", ""),
        "support_pcx_name": support_manifest.get("pcx_name", ""),
        "support_frontier_id": support_manifest.get("frontier_id", ""),
        "support_start": str(support_start),
        "support_known_bytes": str(support["known"]),
        "support_high_plateau_bytes": str(support["high"]),
        "missing_known_bytes": str(missing_known),
        "missing_exact_bytes": str(missing_exact),
        "missing_small_delta_le1_bytes": str(missing_le1),
        "missing_small_delta_le2_bytes": str(missing_le2),
        "missing_small_delta_le4_bytes": str(missing_le4),
        "full_exact_bytes": str(full_exact),
        "full_small_delta_le2_bytes": str(full_le2),
        "full_small_delta_le4_bytes": str(full_le4),
        "top_delta": str(top_delta),
        "top_delta_count": str(top_count),
        "same_fixture": "1" if same_fixture else "0",
        "relative_offset": str(support_start - pre_start) if same_fixture else "",
        "support_head_hex": support_data[:16].hex(),
        "target_head_hex": target_source[:16].hex(),
    }


def build_candidates(
    targets: list[dict[str, object]],
    supports: list[dict[str, object]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for target in targets:
        for support in supports:
            row = score_candidate(target, support)
            if row:
                rows.append(row)
    rows.sort(
        key=lambda row: (
            row.get("target_id", ""),
            -int_value(row, "missing_known_bytes"),
            -int_value(row, "missing_exact_bytes"),
            -int_value(row, "missing_small_delta_le2_bytes"),
            -int_value(row, "full_small_delta_le2_bytes"),
            row.get("support_rank", ""),
            int_value(row, "support_start"),
        )
    )
    return rows


def best_candidate(rows: list[dict[str, str]]) -> dict[str, str]:
    return sorted(
        rows,
        key=lambda row: (
            -int_value(row, "missing_known_bytes"),
            -int_value(row, "missing_exact_bytes"),
            -int_value(row, "missing_small_delta_le2_bytes"),
            -int_value(row, "full_small_delta_le2_bytes"),
            row.get("support_rank", ""),
            int_value(row, "support_start"),
        ),
    )[0]


def build_coverage(
    targets: list[dict[str, object]],
    candidates: list[dict[str, str]],
) -> list[dict[str, str]]:
    by_target: dict[str, list[dict[str, str]]] = {}
    for row in candidates:
        by_target.setdefault(row.get("target_id", ""), []).append(row)
    rows: list[dict[str, str]] = []
    target_records = {target_record(row)["target_id"]: target_record(row) for row in targets}
    for target_id, record in sorted(target_records.items()):
        rows_for_target = by_target.get(target_id, [])
        full_support = [
            row
            for row in rows_for_target
            if int_value(row, "missing_known_bytes") == int_value(row, "missing_source_bytes")
        ]
        best = best_candidate(rows_for_target) if rows_for_target else {}
        rows.append(
            {
                "target_id": target_id,
                "rank": record.get("rank", ""),
                "frontier_id": record.get("frontier_id", ""),
                "pre_source_start": record.get("pre_source_start", ""),
                "known_source_bytes": record.get("known_source_bytes", "0"),
                "missing_source_bytes": record.get("missing_source_bytes", "0"),
                "candidate_rows": str(len(rows_for_target)),
                "full_missing_support_candidate_rows": str(len(full_support)),
                "best_support_rank": best.get("support_rank", ""),
                "best_support_frontier_id": best.get("support_frontier_id", ""),
                "best_support_start": best.get("support_start", ""),
                "best_missing_known_bytes": best.get("missing_known_bytes", "0"),
                "best_missing_exact_bytes": best.get("missing_exact_bytes", "0"),
                "best_missing_small_delta_le2_bytes": best.get("missing_small_delta_le2_bytes", "0"),
                "best_missing_small_delta_le4_bytes": best.get("missing_small_delta_le4_bytes", "0"),
                "best_full_small_delta_le2_bytes": best.get("full_small_delta_le2_bytes", "0"),
                "best_full_small_delta_le4_bytes": best.get("full_small_delta_le4_bytes", "0"),
            }
        )
    return rows


def ratio(numerator: int, denominator: int) -> str:
    return f"{numerator / denominator:.6f}" if denominator else "0.000000"


def build_summary(
    targets: list[dict[str, object]],
    supports: list[dict[str, object]],
    candidates: list[dict[str, str]],
    coverage: list[dict[str, str]],
    issues: list[str],
) -> dict[str, str]:
    known_source = sum(int_value(row, "known_source_bytes") for row in coverage)
    missing_source = sum(int_value(row, "missing_source_bytes") for row in coverage)
    rows_with_full = sum(1 for row in coverage if int_value(row, "best_missing_known_bytes") == int_value(row, "missing_source_bytes"))
    best_known_total = sum(int_value(row, "best_missing_known_bytes") for row in coverage)
    best_exact_total = sum(int_value(row, "best_missing_exact_bytes") for row in coverage)
    best_le2_total = sum(int_value(row, "best_missing_small_delta_le2_bytes") for row in coverage)
    best_le4_total = sum(int_value(row, "best_missing_small_delta_le4_bytes") for row in coverage)
    exact_ratios = [
        ratio(int_value(row, "best_missing_exact_bytes"), int_value(row, "missing_source_bytes"))
        for row in coverage
        if int_value(row, "missing_source_bytes")
    ]
    full_support = rows_with_full == len(coverage) and bool(coverage)
    exact_complete = best_exact_total == missing_source and missing_source > 0
    if full_support and not exact_complete:
        verdict = "frontier80_context_residual_low_payload_row_state_source_prereq_transform_needed"
        next_probe = "derive transformed high-row support for row-state source prerequisites"
    elif full_support and exact_complete:
        verdict = "frontier80_context_residual_low_payload_row_state_source_prereq_exact_ready"
        next_probe = "promote exact source prerequisites for compact-control row-state"
    else:
        verdict = "frontier80_context_residual_low_payload_row_state_source_prereq_uncovered"
        next_probe = "broaden high-row source prerequisite search"
    return {
        "scope": "total",
        "target_source_rows": str(len(targets)),
        "source_bytes": str(len(targets) * 32),
        "known_source_bytes": str(known_source),
        "missing_source_bytes": str(missing_source),
        "support_windows": str(len(supports)),
        "candidate_rows": str(len(candidates)),
        "target_rows_with_full_missing_support": str(rows_with_full),
        "target_rows_without_full_missing_support": str(len(coverage) - rows_with_full),
        "best_missing_known_total": str(best_known_total),
        "best_missing_exact_total": str(best_exact_total),
        "best_missing_small_delta_le2_total": str(best_le2_total),
        "best_missing_small_delta_le4_total": str(best_le4_total),
        "best_missing_exact_min": str(
            min((int_value(row, "best_missing_exact_bytes") for row in coverage), default=0)
        ),
        "best_missing_exact_ratio_min": min(exact_ratios, default="0.000000"),
        "best_full_row_small_delta_le2_min": str(
            min((int_value(row, "best_full_small_delta_le2_bytes") for row in coverage), default=0)
        ),
        "best_full_row_small_delta_le4_min": str(
            min((int_value(row, "best_full_small_delta_le4_bytes") for row in coverage), default=0)
        ),
        "issue_rows": str(len(issues)),
        "review_verdict": verdict,
        "next_probe": next_probe,
    }


def table_html(title: str, filename: str, rows: list[dict[str, str]], fields: list[str], limit: int = 36) -> str:
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
    coverage: list[dict[str, str]],
    candidates: list[dict[str, str]],
    title: str,
) -> str:
    summary_json = html.escape(json.dumps(summary, indent=2))
    stats = "".join(
        f"<div class=\"stat\"><div class=\"label\">{html.escape(key)}</div>"
        f"<div class=\"value\">{html.escape(summary.get(key, ''))}</div></div>"
        for key in (
            "missing_source_bytes",
            "best_missing_known_total",
            "best_missing_exact_total",
            "best_missing_exact_ratio_min",
            "support_windows",
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
  {table_html("Target pre-sources", "targets.csv", targets, TARGET_FIELDNAMES)}
  {table_html("Coverage", "target_coverage.csv", coverage, COVERAGE_FIELDNAMES)}
  {table_html("Candidates", "candidates.csv", candidates, CANDIDATE_FIELDNAMES)}
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Find source-byte prerequisites for compact-control row-state high rows."
    )
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--runs", type=Path, default=DEFAULT_RUNS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--clean-fixtures", type=Path, default=DEFAULT_CLEAN_FIXTURES)
    parser.add_argument("--min-known", type=int, default=24)
    parser.add_argument("--min-high", type=int, default=28)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Low Payload Row-State Source Prereq Probe",
    )
    args = parser.parse_args()

    issues: list[str] = []
    run_rows = read_csv(args.runs)
    manifest_rows = read_csv(args.manifest)
    clean_rows = read_csv(args.clean_fixtures)
    target_runs = load_target_runs(run_rows, manifest_rows, clean_rows, issues)
    targets = target_source_rows(target_runs, issues)
    supports = support_windows(manifest_rows, clean_rows, issues, min_known=args.min_known, min_high=args.min_high)
    candidates = build_candidates(targets, supports)
    coverage = build_coverage(targets, candidates)
    target_records = [target_record(row) for row in targets]
    summary = build_summary(targets, supports, candidates, coverage, issues)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, target_records)
    write_csv(args.output / "target_coverage.csv", COVERAGE_FIELDNAMES, coverage)
    write_csv(args.output / "candidates.csv", CANDIDATE_FIELDNAMES, candidates)
    (args.output / "issues.txt").write_text("\n".join(issues))
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, target_records, coverage, candidates, args.title))

    print(
        "Source prereqs: "
        f"missing={summary['missing_source_bytes']}, "
        f"best_known={summary['best_missing_known_total']}, "
        f"best_exact={summary['best_missing_exact_total']}"
    )
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
