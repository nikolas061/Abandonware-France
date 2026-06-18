#!/usr/bin/env python3
"""Probe bounded-delta selectors for row-state source prerequisites."""

from __future__ import annotations

import argparse
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_decoder_frontier80_context_split_residual_low_payload_neighborhood_probe import (
    load_target_runs,
    read_csv,
    signed_delta,
)
from lolg_tex_gap_decoder_frontier80_context_split_residual_low_payload_row_state_source_prereq_probe import (
    score_candidate,
    support_windows,
    target_source_rows,
)
from lolg_tex_gap_opcode_probe import int_value, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_frontier80_context_split_residual_low_payload_row_state_source_delta_selector_probe")
DEFAULT_RUNS = Path("output/tex_gap_decoder_unresolved_run_probe_frontier80_context_split_residual_second_replay/runs.csv")
DEFAULT_MANIFEST = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_CLEAN_FIXTURES = Path(
    "output/tex_gap_decoder_frontier80_context_split_residual_second_fixture_replay/fixtures.csv"
)

TARGET_STRATEGIES = [
    "target_family",
    "target_start_band16",
    "target_start_band32",
    "target_start_band64",
    "target_start_mod320",
]
GLOBAL_STRATEGIES = [
    "global_family",
    "global_start_band32",
]

SUMMARY_FIELDNAMES = [
    "scope",
    "target_source_rows",
    "missing_source_bytes",
    "bounded_candidate_rows",
    "best_target_family_exact_total",
    "best_target_family_leave_one_out_total",
    "best_target_start_band32_exact_total",
    "best_target_start_band32_leave_one_out_total",
    "best_global_start_band32_exact_total",
    "best_global_start_band32_leave_one_out_total",
    "target_start_band32_exact_rows",
    "target_start_band32_leave_one_out_exact_rows",
    "promotion_ready_rows",
    "promotion_ready_bytes",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

COVERAGE_FIELDNAMES = [
    "target_id",
    "strategy",
    "rank",
    "frontier_id",
    "pre_source_start",
    "missing_source_bytes",
    "candidate_rows",
    "best_group_key",
    "best_group_rows",
    "best_support_rank",
    "best_support_frontier_id",
    "best_support_start",
    "best_exact_bytes",
    "best_leave_one_out_exact_bytes",
    "best_raw_exact_bytes",
    "exact_ready",
    "leave_one_out_ready",
]

SELECTOR_FIELDNAMES = [
    "target_id",
    "strategy",
    "group_key",
    "group_rows",
    "rank",
    "frontier_id",
    "pre_source_start",
    "missing_source_bytes",
    "support_rank",
    "support_frontier_id",
    "support_start",
    "raw_exact_bytes",
    "exact_bytes",
    "leave_one_out_exact_bytes",
    "mode_delta_head",
    "leave_one_out_delta_head",
    "support_head_hex",
    "target_head_hex",
]


def add_delta(value: int, delta: int) -> int:
    return (value + delta) & 0xFF


def group_key(row: dict[str, str], strategy: str) -> str:
    support_rank = row.get("support_rank", "")
    support_frontier = row.get("support_frontier_id", "")
    support_start = int_value(row, "support_start")
    if strategy.endswith("family"):
        return f"{support_rank}:{support_frontier}"
    if strategy.endswith("start_band16"):
        return f"{support_rank}:{support_frontier}:band16:{support_start // 16}"
    if strategy.endswith("start_band32"):
        return f"{support_rank}:{support_frontier}:band32:{support_start // 32}"
    if strategy.endswith("start_band64"):
        return f"{support_rank}:{support_frontier}:band64:{support_start // 64}"
    if strategy.endswith("start_mod320"):
        return f"{support_rank}:{support_frontier}:mod320:{support_start % 320}"
    return f"{support_rank}:{support_frontier}:{support_start}"


def bounded_records(
    targets: list[dict[str, object]],
    supports: list[dict[str, object]],
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for target_index, target in enumerate(targets):
        target_row = target["target"]
        target_source = target["source"]
        missing = target["missing"]
        assert isinstance(target_row, dict)
        assert isinstance(target_source, bytes)
        assert isinstance(missing, list)
        for support in supports:
            base = score_candidate(target, support)
            if not base or int_value(base, "missing_known_bytes") != len(missing):
                continue
            support_data = support["data"]
            assert isinstance(support_data, bytes)
            deltas = [signed_delta(source_value, target_value) for source_value, target_value in zip(support_data, target_source)]
            if not all(abs(deltas[position]) <= 4 for position in missing):
                continue
            records.append(
                {
                    "target_index": target_index,
                    "target": target,
                    "support": support,
                    "base": base,
                    "deltas": deltas,
                }
            )
    return records


def mode_deltas(records: list[dict[str, object]], positions: list[int]) -> dict[int, int]:
    modes: dict[int, int] = {}
    for position in positions:
        counter: Counter[int] = Counter()
        for record in records:
            deltas = record["deltas"]
            assert isinstance(deltas, list)
            counter[int(deltas[position])] += 1
        modes[position] = counter.most_common(1)[0][0] if counter else 0
    return modes


def exact_with_modes(record: dict[str, object], positions: list[int], modes: dict[int, int]) -> int:
    support = record["support"]
    target = record["target"]
    assert isinstance(support, dict)
    assert isinstance(target, dict)
    support_data = support["data"]
    target_source = target["source"]
    assert isinstance(support_data, bytes)
    assert isinstance(target_source, bytes)
    return sum(1 for position in positions if add_delta(support_data[position], modes.get(position, 0)) == target_source[position])


def selector_row(
    record: dict[str, object],
    strategy: str,
    key: str,
    group_rows: int,
    positions: list[int],
    modes: dict[int, int],
    leave_one_out_modes: dict[int, int],
) -> dict[str, str]:
    target = record["target"]
    base = record["base"]
    assert isinstance(target, dict)
    assert isinstance(base, dict)
    target_row = target["target"]
    target_source = target["source"]
    support = record["support"]
    assert isinstance(target_row, dict)
    assert isinstance(target_source, bytes)
    assert isinstance(support, dict)
    support_data = support["data"]
    assert isinstance(support_data, bytes)
    return {
        "target_id": target_row.get("target_id", ""),
        "strategy": strategy,
        "group_key": key,
        "group_rows": str(group_rows),
        "rank": target_row.get("rank", ""),
        "frontier_id": target_row.get("frontier_id", ""),
        "pre_source_start": str(target["pre_start"]),
        "missing_source_bytes": str(len(positions)),
        "support_rank": base.get("support_rank", ""),
        "support_frontier_id": base.get("support_frontier_id", ""),
        "support_start": base.get("support_start", ""),
        "raw_exact_bytes": base.get("missing_exact_bytes", "0"),
        "exact_bytes": str(exact_with_modes(record, positions, modes)),
        "leave_one_out_exact_bytes": str(exact_with_modes(record, positions, leave_one_out_modes)),
        "mode_delta_head": " ".join(str(modes.get(position, 0)) for position in positions[:12]),
        "leave_one_out_delta_head": " ".join(str(leave_one_out_modes.get(position, 0)) for position in positions[:12]),
        "support_head_hex": base.get("support_head_hex", ""),
        "target_head_hex": base.get("target_head_hex", ""),
    }


def build_selector_rows(
    targets: list[dict[str, object]],
    records: list[dict[str, object]],
    *,
    min_group_rows: int,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    by_target: dict[int, list[dict[str, object]]] = defaultdict(list)
    for record in records:
        by_target[int(record["target_index"])].append(record)

    for target_index, target_records in by_target.items():
        target = targets[target_index]
        positions = target["missing"]
        assert isinstance(positions, list)
        for strategy in TARGET_STRATEGIES:
            groups: dict[str, list[dict[str, object]]] = defaultdict(list)
            for record in target_records:
                base = record["base"]
                assert isinstance(base, dict)
                groups[group_key(base, strategy)].append(record)
            for key, group in groups.items():
                if len(group) < min_group_rows:
                    continue
                modes = mode_deltas(group, positions)
                for record in group:
                    leave_one_out_group = [other for other in group if other is not record]
                    leave_one_out_modes = mode_deltas(leave_one_out_group, positions)
                    rows.append(selector_row(record, strategy, key, len(group), positions, modes, leave_one_out_modes))

    for strategy in GLOBAL_STRATEGIES:
        groups = defaultdict(list)
        for record in records:
            base = record["base"]
            assert isinstance(base, dict)
            groups[group_key(base, strategy)].append(record)
        for key, group in groups.items():
            if len(group) < min_group_rows:
                continue
            modes = mode_deltas(group, list(range(32)))
            for record in group:
                target = record["target"]
                assert isinstance(target, dict)
                positions = target["missing"]
                assert isinstance(positions, list)
                leave_one_out_group = [other for other in group if other is not record]
                leave_one_out_modes = mode_deltas(leave_one_out_group, list(range(32)))
                rows.append(selector_row(record, strategy, key, len(group), positions, modes, leave_one_out_modes))

    rows.sort(
        key=lambda row: (
            row.get("target_id", ""),
            row.get("strategy", ""),
            -int_value(row, "exact_bytes"),
            -int_value(row, "leave_one_out_exact_bytes"),
            row.get("group_key", ""),
            int_value(row, "support_start"),
        )
    )
    return rows


def best_selector(rows: list[dict[str, str]]) -> dict[str, str]:
    return sorted(
        rows,
        key=lambda row: (
            -int_value(row, "exact_bytes"),
            -int_value(row, "leave_one_out_exact_bytes"),
            -int_value(row, "group_rows"),
            -int_value(row, "raw_exact_bytes"),
            row.get("group_key", ""),
            int_value(row, "support_start"),
        ),
    )[0]


def build_coverage(
    targets: list[dict[str, object]],
    records: list[dict[str, object]],
    selector_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    candidate_counts: Counter[str] = Counter()
    for record in records:
        target = record["target"]
        assert isinstance(target, dict)
        target_row = target["target"]
        assert isinstance(target_row, dict)
        candidate_counts[target_row.get("target_id", "")] += 1

    by_target_strategy: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in selector_rows:
        by_target_strategy[(row.get("target_id", ""), row.get("strategy", ""))].append(row)

    rows: list[dict[str, str]] = []
    for target in targets:
        target_row = target["target"]
        missing = target["missing"]
        assert isinstance(target_row, dict)
        assert isinstance(missing, list)
        target_id = target_row.get("target_id", "")
        for strategy in TARGET_STRATEGIES + GLOBAL_STRATEGIES:
            options = by_target_strategy.get((target_id, strategy), [])
            best = best_selector(options) if options else {}
            rows.append(
                {
                    "target_id": target_id,
                    "strategy": strategy,
                    "rank": target_row.get("rank", ""),
                    "frontier_id": target_row.get("frontier_id", ""),
                    "pre_source_start": str(target["pre_start"]),
                    "missing_source_bytes": str(len(missing)),
                    "candidate_rows": str(candidate_counts[target_id]),
                    "best_group_key": best.get("group_key", ""),
                    "best_group_rows": best.get("group_rows", "0"),
                    "best_support_rank": best.get("support_rank", ""),
                    "best_support_frontier_id": best.get("support_frontier_id", ""),
                    "best_support_start": best.get("support_start", ""),
                    "best_exact_bytes": best.get("exact_bytes", "0"),
                    "best_leave_one_out_exact_bytes": best.get("leave_one_out_exact_bytes", "0"),
                    "best_raw_exact_bytes": best.get("raw_exact_bytes", "0"),
                    "exact_ready": "1" if int_value(best, "exact_bytes") == len(missing) else "0",
                    "leave_one_out_ready": "1" if int_value(best, "leave_one_out_exact_bytes") == len(missing) else "0",
                }
            )
    rows.sort(key=lambda row: (int_value(row, "rank"), int_value(row, "pre_source_start"), row.get("strategy", "")))
    return rows


def strategy_total(coverage: list[dict[str, str]], strategy: str, field: str) -> int:
    return sum(int_value(row, field) for row in coverage if row.get("strategy") == strategy)


def strategy_ready_rows(coverage: list[dict[str, str]], strategy: str, field: str) -> int:
    return sum(1 for row in coverage if row.get("strategy") == strategy and row.get(field) == "1")


def build_summary(
    targets: list[dict[str, object]],
    records: list[dict[str, object]],
    coverage: list[dict[str, str]],
    issues: list[str],
) -> dict[str, str]:
    missing_total = sum(len(target["missing"]) for target in targets if isinstance(target["missing"], list))
    target_rows = len(targets)
    target_band32_exact = strategy_total(coverage, "target_start_band32", "best_exact_bytes")
    target_band32_loo = strategy_total(coverage, "target_start_band32", "best_leave_one_out_exact_bytes")
    promotion_rows = strategy_ready_rows(coverage, "target_start_band32", "leave_one_out_ready")
    promotion_bytes = sum(
        int_value(row, "best_leave_one_out_exact_bytes")
        for row in coverage
        if row.get("strategy") == "target_start_band32" and row.get("leave_one_out_ready") == "1"
    )
    if target_band32_exact == missing_total and target_band32_loo < missing_total:
        verdict = "frontier80_context_residual_low_payload_row_state_source_delta_selector_guard_needed"
        next_probe = "derive guards for target-local bounded-delta selector residuals"
    elif target_band32_loo == missing_total and missing_total > 0:
        verdict = "frontier80_context_residual_low_payload_row_state_source_delta_selector_ready"
        next_probe = "promote guarded bounded-delta row-state source selector"
    else:
        verdict = "frontier80_context_residual_low_payload_row_state_source_delta_selector_split_needed"
        next_probe = "split bounded-delta selector by support bucket and target context"
    return {
        "scope": "total",
        "target_source_rows": str(target_rows),
        "missing_source_bytes": str(missing_total),
        "bounded_candidate_rows": str(len(records)),
        "best_target_family_exact_total": str(strategy_total(coverage, "target_family", "best_exact_bytes")),
        "best_target_family_leave_one_out_total": str(
            strategy_total(coverage, "target_family", "best_leave_one_out_exact_bytes")
        ),
        "best_target_start_band32_exact_total": str(target_band32_exact),
        "best_target_start_band32_leave_one_out_total": str(target_band32_loo),
        "best_global_start_band32_exact_total": str(strategy_total(coverage, "global_start_band32", "best_exact_bytes")),
        "best_global_start_band32_leave_one_out_total": str(
            strategy_total(coverage, "global_start_band32", "best_leave_one_out_exact_bytes")
        ),
        "target_start_band32_exact_rows": str(strategy_ready_rows(coverage, "target_start_band32", "exact_ready")),
        "target_start_band32_leave_one_out_exact_rows": str(
            strategy_ready_rows(coverage, "target_start_band32", "leave_one_out_ready")
        ),
        "promotion_ready_rows": str(promotion_rows),
        "promotion_ready_bytes": str(promotion_bytes),
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
    coverage: list[dict[str, str]],
    selector_rows: list[dict[str, str]],
    title: str,
) -> str:
    summary_json = html.escape(json.dumps(summary, indent=2))
    stats = "".join(
        f"<div class=\"stat\"><div class=\"label\">{html.escape(key)}</div>"
        f"<div class=\"value\">{html.escape(summary.get(key, ''))}</div></div>"
        for key in (
            "missing_source_bytes",
            "best_target_start_band32_exact_total",
            "best_target_start_band32_leave_one_out_total",
            "target_start_band32_exact_rows",
            "target_start_band32_leave_one_out_exact_rows",
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
  {table_html("Coverage", "selector_coverage.csv", coverage, COVERAGE_FIELDNAMES)}
  {table_html("Selector rows", "selector_rows.csv", selector_rows, SELECTOR_FIELDNAMES)}
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Probe bounded-delta selectors for row-state source prerequisites."
    )
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--runs", type=Path, default=DEFAULT_RUNS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--clean-fixtures", type=Path, default=DEFAULT_CLEAN_FIXTURES)
    parser.add_argument("--min-known", type=int, default=24)
    parser.add_argument("--min-high", type=int, default=28)
    parser.add_argument("--min-group-rows", type=int, default=2)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Low Payload Row-State Source Delta Selector Probe",
    )
    args = parser.parse_args()

    issues: list[str] = []
    run_rows = read_csv(args.runs)
    manifest_rows = read_csv(args.manifest)
    clean_rows = read_csv(args.clean_fixtures)
    target_runs = load_target_runs(run_rows, manifest_rows, clean_rows, issues)
    targets = target_source_rows(target_runs, issues)
    supports = support_windows(manifest_rows, clean_rows, issues, min_known=args.min_known, min_high=args.min_high)
    records = bounded_records(targets, supports)
    selector_rows = build_selector_rows(targets, records, min_group_rows=args.min_group_rows)
    coverage = build_coverage(targets, records, selector_rows)
    summary = build_summary(targets, records, coverage, issues)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "selector_coverage.csv", COVERAGE_FIELDNAMES, coverage)
    write_csv(args.output / "selector_rows.csv", SELECTOR_FIELDNAMES, selector_rows)
    (args.output / "issues.txt").write_text("\n".join(issues))
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, coverage, selector_rows, args.title))

    print(
        "Delta selectors: "
        f"band32={summary['best_target_start_band32_exact_total']}/"
        f"{summary['best_target_start_band32_leave_one_out_total']}, "
        f"ready={summary['promotion_ready_bytes']}"
    )
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
