#!/usr/bin/env python3
"""Probe single-row delta guards for residual row-state source bytes."""

from __future__ import annotations

import argparse
import html
import json
import statistics
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


DEFAULT_OUTPUT = Path(
    "output/tex_gap_decoder_frontier80_context_split_residual_low_payload_row_state_source_single_row_delta_guard_probe"
)
DEFAULT_RUNS = Path("output/tex_gap_decoder_unresolved_run_probe_frontier80_context_split_residual_second_replay/runs.csv")
DEFAULT_MANIFEST = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_CLEAN_FIXTURES = Path(
    "output/tex_gap_decoder_frontier80_context_split_residual_low_payload_row_state_source_delta_guard_promoted_replay/fixtures.csv"
)
DEFAULT_RESIDUAL_REVIEW = Path(
    "output/tex_gap_decoder_frontier80_context_split_residual_low_payload_row_state_source_delta_guard_residual_review/summary.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "residual_target_rows",
    "residual_target_ids",
    "missing_source_bytes",
    "bounded_candidate_rows",
    "bounded_family_groups",
    "best_raw_exact_total",
    "best_known_anchor_exact_total",
    "best_family_mode_exact_total",
    "best_family_mode_leave_one_out_total",
    "best_band32_mode_exact_total",
    "best_band32_mode_leave_one_out_total",
    "best_same_fixture_mode_exact_total",
    "oracle_position_delta_exact_total",
    "promotion_ready_rows",
    "promotion_ready_bytes",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

STRATEGY_FIELDNAMES = [
    "target_id",
    "strategy",
    "group_key",
    "group_rows",
    "support_rank",
    "support_frontier_id",
    "support_start",
    "same_fixture",
    "relative_offset",
    "missing_source_bytes",
    "raw_exact_bytes",
    "exact_bytes",
    "leave_one_out_exact_bytes",
    "mode_delta_head",
    "leave_one_out_delta_head",
    "known_anchor_deltas",
    "support_head_hex",
    "target_head_hex",
]

CANDIDATE_FIELDNAMES = [
    "target_id",
    "support_rank",
    "support_frontier_id",
    "support_start",
    "same_fixture",
    "relative_offset",
    "support_known_bytes",
    "support_high_plateau_bytes",
    "raw_exact_bytes",
    "small_delta_le2_bytes",
    "small_delta_le4_bytes",
    "known_anchor_delta_head",
    "missing_delta_head",
    "support_head_hex",
    "target_head_hex",
]


def add_delta(value: int, delta: int) -> int:
    return (value + delta) & 0xFF


def exact_with_deltas(source: bytes, target: bytes, positions: list[int], deltas: dict[int, int]) -> int:
    return sum(1 for position in positions if add_delta(source[position], deltas.get(position, 0)) == target[position])


def target_id(target_row: dict[str, object]) -> str:
    target = target_row["target"]
    assert isinstance(target, dict)
    return target.get("target_id", "")


def residual_targets(targets: list[dict[str, object]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for target in targets:
        missing = target["missing"]
        assert isinstance(missing, list)
        if missing:
            rows.append(target)
    return rows


def bounded_candidates(
    target: dict[str, object],
    supports: list[dict[str, object]],
) -> list[dict[str, object]]:
    missing = target["missing"]
    source = target["source"]
    assert isinstance(missing, list)
    assert isinstance(source, bytes)
    rows: list[dict[str, object]] = []
    for support in supports:
        base = score_candidate(target, support)
        if not base or int_value(base, "missing_known_bytes") != len(missing):
            continue
        support_data = support["data"]
        assert isinstance(support_data, bytes)
        deltas = [signed_delta(source_value, target_value) for source_value, target_value in zip(support_data, source)]
        if not all(abs(deltas[position]) <= 4 for position in missing):
            continue
        rows.append({"target": target, "support": support, "base": base, "deltas": deltas})
    return rows


def group_key(base: dict[str, str], strategy: str) -> str:
    support_rank = base.get("support_rank", "")
    support_frontier = base.get("support_frontier_id", "")
    support_start = int_value(base, "support_start")
    if strategy == "family_mode":
        return f"{support_rank}:{support_frontier}"
    if strategy == "band32_mode":
        return f"{support_rank}:{support_frontier}:band32:{support_start // 32}"
    if strategy == "same_fixture_mode":
        return f"same_fixture:{base.get('same_fixture', '0')}"
    return "single"


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


def known_anchor_maps(target: dict[str, object], deltas: list[int]) -> dict[str, dict[int, int]]:
    mask = target["mask"]
    missing = target["missing"]
    assert isinstance(mask, bytes)
    assert isinstance(missing, list)
    known = [position for position, value in enumerate(mask) if value]
    known_deltas = [deltas[position] for position in known]
    if not known_deltas:
        return {}
    top_delta = Counter(known_deltas).most_common(1)[0][0]
    median_delta = int(statistics.median_low(known_deltas))
    nearest: dict[int, int] = {}
    left: dict[int, int] = {}
    right: dict[int, int] = {}
    linear: dict[int, int] = {}
    for position in missing:
        nearest_position = min(known, key=lambda known_position: abs(known_position - position))
        nearest[position] = deltas[nearest_position]
        left_positions = [known_position for known_position in known if known_position < position]
        right_positions = [known_position for known_position in known if known_position > position]
        left_anchor = max(left_positions) if left_positions else min(right_positions)
        right_anchor = min(right_positions) if right_positions else max(left_positions)
        left[position] = deltas[left_anchor]
        right[position] = deltas[right_anchor]
        if left_positions and right_positions:
            left_anchor = max(left_positions)
            right_anchor = min(right_positions)
            fraction = (position - left_anchor) / (right_anchor - left_anchor)
            linear[position] = round(deltas[left_anchor] * (1 - fraction) + deltas[right_anchor] * fraction)
        else:
            linear[position] = nearest[position]
    return {
        "known_top_delta": {position: top_delta for position in missing},
        "known_median_delta": {position: median_delta for position in missing},
        "known_nearest_delta": nearest,
        "known_left_delta": left,
        "known_right_delta": right,
        "known_linear_delta": linear,
    }


def selector_row(
    record: dict[str, object],
    strategy: str,
    key: str,
    group_rows: int,
    exact: int,
    leave_one_out: int,
    modes: dict[int, int],
    leave_one_out_modes: dict[int, int],
) -> dict[str, str]:
    target = record["target"]
    base = record["base"]
    deltas = record["deltas"]
    assert isinstance(target, dict)
    assert isinstance(base, dict)
    assert isinstance(deltas, list)
    missing = target["missing"]
    mask = target["mask"]
    assert isinstance(missing, list)
    assert isinstance(mask, bytes)
    known = [position for position, value in enumerate(mask) if value]
    return {
        "target_id": target_id(target),
        "strategy": strategy,
        "group_key": key,
        "group_rows": str(group_rows),
        "support_rank": base.get("support_rank", ""),
        "support_frontier_id": base.get("support_frontier_id", ""),
        "support_start": base.get("support_start", ""),
        "same_fixture": base.get("same_fixture", "0"),
        "relative_offset": base.get("relative_offset", ""),
        "missing_source_bytes": str(len(missing)),
        "raw_exact_bytes": base.get("missing_exact_bytes", "0"),
        "exact_bytes": str(exact),
        "leave_one_out_exact_bytes": str(leave_one_out),
        "mode_delta_head": " ".join(str(modes.get(position, 0)) for position in missing[:12]),
        "leave_one_out_delta_head": " ".join(str(leave_one_out_modes.get(position, 0)) for position in missing[:12]),
        "known_anchor_deltas": " ".join(f"{position}:{deltas[position]}" for position in known),
        "support_head_hex": base.get("support_head_hex", ""),
        "target_head_hex": base.get("target_head_hex", ""),
    }


def build_strategy_rows(residual: list[dict[str, object]], supports: list[dict[str, object]]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    strategy_rows: list[dict[str, str]] = []
    candidate_rows: list[dict[str, str]] = []
    for target in residual:
        source = target["source"]
        missing = target["missing"]
        mask = target["mask"]
        assert isinstance(source, bytes)
        assert isinstance(missing, list)
        assert isinstance(mask, bytes)
        candidates = bounded_candidates(target, supports)
        for record in candidates:
            base = record["base"]
            deltas = record["deltas"]
            assert isinstance(base, dict)
            assert isinstance(deltas, list)
            known = [position for position, value in enumerate(mask) if value]
            candidate_rows.append(
                {
                    "target_id": target_id(target),
                    "support_rank": base.get("support_rank", ""),
                    "support_frontier_id": base.get("support_frontier_id", ""),
                    "support_start": base.get("support_start", ""),
                    "same_fixture": base.get("same_fixture", "0"),
                    "relative_offset": base.get("relative_offset", ""),
                    "support_known_bytes": base.get("support_known_bytes", "0"),
                    "support_high_plateau_bytes": base.get("support_high_plateau_bytes", "0"),
                    "raw_exact_bytes": base.get("missing_exact_bytes", "0"),
                    "small_delta_le2_bytes": base.get("missing_small_delta_le2_bytes", "0"),
                    "small_delta_le4_bytes": base.get("missing_small_delta_le4_bytes", "0"),
                    "known_anchor_delta_head": " ".join(f"{position}:{deltas[position]}" for position in known),
                    "missing_delta_head": " ".join(str(deltas[position]) for position in missing[:12]),
                    "support_head_hex": base.get("support_head_hex", ""),
                    "target_head_hex": base.get("target_head_hex", ""),
                }
            )

        for record in candidates:
            support = record["support"]
            base = record["base"]
            deltas = record["deltas"]
            assert isinstance(support, dict)
            assert isinstance(base, dict)
            assert isinstance(deltas, list)
            support_data = support["data"]
            assert isinstance(support_data, bytes)
            raw_modes = {position: 0 for position in missing}
            raw_exact = exact_with_deltas(support_data, source, missing, raw_modes)
            strategy_rows.append(selector_row(record, "raw_copy", "single", 1, raw_exact, raw_exact, raw_modes, raw_modes))
            for strategy, modes in known_anchor_maps(target, deltas).items():
                exact = exact_with_deltas(support_data, source, missing, modes)
                strategy_rows.append(selector_row(record, strategy, "known_anchors", 1, exact, exact, modes, modes))

        for strategy in ("family_mode", "band32_mode", "same_fixture_mode"):
            groups: dict[str, list[dict[str, object]]] = defaultdict(list)
            for record in candidates:
                base = record["base"]
                assert isinstance(base, dict)
                groups[group_key(base, strategy)].append(record)
            for key, group in groups.items():
                modes = mode_deltas(group, missing)
                for record in group:
                    support = record["support"]
                    assert isinstance(support, dict)
                    support_data = support["data"]
                    assert isinstance(support_data, bytes)
                    exact = exact_with_deltas(support_data, source, missing, modes)
                    leave_one_out_group = [other for other in group if other is not record]
                    leave_one_out_modes = mode_deltas(leave_one_out_group, missing)
                    leave_one_out = exact_with_deltas(support_data, source, missing, leave_one_out_modes)
                    strategy_rows.append(
                        selector_row(
                            record,
                            strategy,
                            key,
                            len(group),
                            exact,
                            leave_one_out,
                            modes,
                            leave_one_out_modes,
                        )
                    )

        for record in candidates:
            support = record["support"]
            deltas = record["deltas"]
            assert isinstance(support, dict)
            assert isinstance(deltas, list)
            support_data = support["data"]
            assert isinstance(support_data, bytes)
            oracle_modes = {position: int(deltas[position]) for position in missing}
            exact = exact_with_deltas(support_data, source, missing, oracle_modes)
            strategy_rows.append(
                selector_row(record, "oracle_position_delta", "oracle", 1, exact, exact, oracle_modes, oracle_modes)
            )

    strategy_rows.sort(
        key=lambda row: (
            row.get("target_id", ""),
            row.get("strategy", ""),
            -int_value(row, "exact_bytes"),
            -int_value(row, "leave_one_out_exact_bytes"),
            -int_value(row, "group_rows"),
            row.get("support_rank", ""),
            int_value(row, "support_start"),
        )
    )
    candidate_rows.sort(
        key=lambda row: (
            row.get("target_id", ""),
            -int_value(row, "small_delta_le4_bytes"),
            -int_value(row, "small_delta_le2_bytes"),
            -int_value(row, "raw_exact_bytes"),
            row.get("support_rank", ""),
            int_value(row, "support_start"),
        )
    )
    return strategy_rows, candidate_rows


def best(strategy_rows: list[dict[str, str]], strategy: str, field: str) -> int:
    return max((int_value(row, field) for row in strategy_rows if row.get("strategy") == strategy), default=0)


def build_summary(
    residual: list[dict[str, object]],
    strategy_rows: list[dict[str, str]],
    candidate_rows: list[dict[str, str]],
    issues: list[str],
) -> dict[str, str]:
    missing_total = sum(len(target["missing"]) for target in residual if isinstance(target["missing"], list))
    family_exact = best(strategy_rows, "family_mode", "exact_bytes")
    family_loo = best(strategy_rows, "family_mode", "leave_one_out_exact_bytes")
    band_exact = best(strategy_rows, "band32_mode", "exact_bytes")
    band_loo = best(strategy_rows, "band32_mode", "leave_one_out_exact_bytes")
    oracle_exact = best(strategy_rows, "oracle_position_delta", "exact_bytes")
    if max(family_exact, band_exact) == missing_total and max(family_loo, band_loo) < missing_total:
        verdict = "frontier80_context_residual_low_payload_row_state_source_single_row_delta_guard_non_oracle_needed"
        next_probe = "derive non-oracle selector for single-row residual delta guard"
    elif max(family_loo, band_loo) == missing_total and missing_total > 0:
        verdict = "frontier80_context_residual_low_payload_row_state_source_single_row_delta_guard_ready"
        next_probe = "promote single-row residual delta guard"
    else:
        verdict = "frontier80_context_residual_low_payload_row_state_source_single_row_delta_guard_split_needed"
        next_probe = "split single-row residual delta support"
    return {
        "scope": "total",
        "residual_target_rows": str(len(residual)),
        "residual_target_ids": ";".join(target_id(target) for target in residual),
        "missing_source_bytes": str(missing_total),
        "bounded_candidate_rows": str(len(candidate_rows)),
        "bounded_family_groups": str(len({(row.get("support_rank", ""), row.get("support_frontier_id", "")) for row in candidate_rows})),
        "best_raw_exact_total": str(best(strategy_rows, "raw_copy", "exact_bytes")),
        "best_known_anchor_exact_total": str(
            max(
                best(strategy_rows, "known_top_delta", "exact_bytes"),
                best(strategy_rows, "known_median_delta", "exact_bytes"),
                best(strategy_rows, "known_nearest_delta", "exact_bytes"),
                best(strategy_rows, "known_left_delta", "exact_bytes"),
                best(strategy_rows, "known_right_delta", "exact_bytes"),
                best(strategy_rows, "known_linear_delta", "exact_bytes"),
            )
        ),
        "best_family_mode_exact_total": str(family_exact),
        "best_family_mode_leave_one_out_total": str(family_loo),
        "best_band32_mode_exact_total": str(band_exact),
        "best_band32_mode_leave_one_out_total": str(band_loo),
        "best_same_fixture_mode_exact_total": str(best(strategy_rows, "same_fixture_mode", "exact_bytes")),
        "oracle_position_delta_exact_total": str(oracle_exact),
        "promotion_ready_rows": "1" if max(family_loo, band_loo) == missing_total and missing_total > 0 else "0",
        "promotion_ready_bytes": str(missing_total if max(family_loo, band_loo) == missing_total else 0),
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
    strategy_rows: list[dict[str, str]],
    candidate_rows: list[dict[str, str]],
    title: str,
) -> str:
    summary_json = html.escape(json.dumps(summary, indent=2))
    stats = "".join(
        f"<div class=\"stat\"><div class=\"label\">{html.escape(key)}</div>"
        f"<div class=\"value\">{html.escape(summary.get(key, ''))}</div></div>"
        for key in (
            "missing_source_bytes",
            "bounded_candidate_rows",
            "best_family_mode_exact_total",
            "best_family_mode_leave_one_out_total",
            "oracle_position_delta_exact_total",
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
  {table_html("Strategy rows", "strategy_rows.csv", strategy_rows, STRATEGY_FIELDNAMES)}
  {table_html("Bounded candidates", "bounded_candidates.csv", candidate_rows, CANDIDATE_FIELDNAMES)}
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Probe single-row delta guards for residual row-state source bytes."
    )
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--runs", type=Path, default=DEFAULT_RUNS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--clean-fixtures", type=Path, default=DEFAULT_CLEAN_FIXTURES)
    parser.add_argument("--residual-review", type=Path, default=DEFAULT_RESIDUAL_REVIEW)
    parser.add_argument("--min-known", type=int, default=24)
    parser.add_argument("--min-high", type=int, default=28)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Low Payload Row-State Source Single-Row Delta Guard Probe",
    )
    args = parser.parse_args()

    issues: list[str] = []
    run_rows = read_csv(args.runs)
    manifest_rows = read_csv(args.manifest)
    clean_rows = read_csv(args.clean_fixtures)
    target_runs = load_target_runs(run_rows, manifest_rows, clean_rows, issues)
    targets = target_source_rows(target_runs, issues)
    residual = residual_targets(targets)
    supports = support_windows(manifest_rows, clean_rows, issues, min_known=args.min_known, min_high=args.min_high)
    strategy_rows, candidate_rows = build_strategy_rows(residual, supports)
    summary = build_summary(residual, strategy_rows, candidate_rows, issues)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "strategy_rows.csv", STRATEGY_FIELDNAMES, strategy_rows)
    write_csv(args.output / "bounded_candidates.csv", CANDIDATE_FIELDNAMES, candidate_rows)
    (args.output / "issues.txt").write_text("\n".join(issues))
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, strategy_rows, candidate_rows, args.title))

    print(
        "Single-row delta guard: "
        f"family={summary['best_family_mode_exact_total']}/"
        f"{summary['best_family_mode_leave_one_out_total']}, "
        f"oracle={summary['oracle_position_delta_exact_total']}"
    )
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
