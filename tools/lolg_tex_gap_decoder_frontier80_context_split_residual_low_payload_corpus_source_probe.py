#!/usr/bin/env python3
"""Search corpus-wide 32-byte sources for saturated Frontier80 low-payload rows."""

from __future__ import annotations

import argparse
import html
import json
from collections import Counter
from pathlib import Path

from lolg_tex_gap_decoder_frontier80_context_split_residual_low_payload_neighborhood_probe import (
    TARGET_FIELDNAMES,
    byte_class,
    fixture_key,
    load_target_runs,
    low_target_rows,
    read_csv,
    signed_delta,
    target_row_record,
)
from lolg_tex_gap_opcode_probe import int_value, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_frontier80_context_split_residual_low_payload_corpus_source_probe")
DEFAULT_RUNS = Path("output/tex_gap_decoder_unresolved_run_probe_frontier80_context_split_residual_second_replay/runs.csv")
DEFAULT_MANIFEST = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_CLEAN_FIXTURES = Path(
    "output/tex_gap_decoder_frontier80_context_split_residual_second_fixture_replay/fixtures.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "target_runs",
    "target_low_rows",
    "target_low_bytes",
    "source_windows",
    "candidate_rows",
    "known_source_candidate_rows",
    "unknown_source_candidate_rows",
    "target_rows_with_candidate",
    "target_rows_without_candidate",
    "low1_rows_with_candidate",
    "low2_rows_with_candidate",
    "best_candidate_target",
    "best_candidate_role",
    "best_candidate_source_rank",
    "best_candidate_source_frontier",
    "best_candidate_source_start",
    "best_candidate_exact_bytes",
    "best_candidate_small_delta_le2_bytes",
    "best_candidate_small_delta_le4_bytes",
    "best_candidate_source_known_bytes",
    "best_per_target_small_delta_le2_min",
    "best_per_target_exact_min",
    "best_per_target_source_known_min",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

CANDIDATE_FIELDNAMES = [
    "target_id",
    "row_role",
    "target_rank",
    "target_frontier_id",
    "target_start",
    "source_rank",
    "source_pcx_name",
    "source_frontier_id",
    "source_start",
    "same_fixture",
    "relative_offset",
    "source_known_bytes",
    "source_unknown_bytes",
    "source_high_plateau_bytes",
    "source_low_payload_bytes",
    "source_control_high_bytes",
    "source_zero_bytes",
    "exact_bytes",
    "small_delta_le1_bytes",
    "small_delta_le2_bytes",
    "small_delta_le4_bytes",
    "mean_abs_delta",
    "top_delta",
    "top_delta_count",
    "source_head_hex",
    "target_head_hex",
]

SOURCE_WINDOW_FIELDNAMES = [
    "rank",
    "pcx_name",
    "frontier_id",
    "source_start",
    "source_known_bytes",
    "source_high_plateau_bytes",
    "source_low_payload_bytes",
    "source_control_high_bytes",
    "source_zero_bytes",
    "source_head_hex",
]

TARGET_COVERAGE_FIELDNAMES = [
    "target_id",
    "row_role",
    "target_rank",
    "target_frontier_id",
    "target_start",
    "candidate_rows",
    "known_source_candidate_rows",
    "unknown_source_candidate_rows",
    "best_exact_bytes",
    "best_small_delta_le2_bytes",
    "best_small_delta_le4_bytes",
    "best_source_known_bytes",
    "best_source_rank",
    "best_source_frontier_id",
    "best_source_start",
]


def source_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", "")


def load_source_windows(
    manifest_rows: list[dict[str, str]],
    clean_rows: list[dict[str, str]],
    issues: list[str],
    *,
    limit: int,
) -> list[dict[str, object]]:
    clean_by_key = {fixture_key(row): row for row in clean_rows}
    windows: list[dict[str, object]] = []
    for manifest in manifest_rows:
        try:
            expected = Path(manifest.get("expected_gap_path", "")).read_bytes()
        except OSError as exc:
            issues.append(f"read_expected_failed:{source_key(manifest)}:{exc}")
            continue
        known_mask = b"\x00" * len(expected)
        clean = clean_by_key.get(fixture_key(manifest))
        if clean:
            try:
                known_mask = Path(clean.get("known_mask_path", "")).read_bytes()
            except OSError as exc:
                issues.append(f"read_known_failed:{source_key(manifest)}:{exc}")
        for source_start in range(0, max(0, len(expected) - 31)):
            source = expected[source_start : source_start + 32]
            known = known_mask[source_start : source_start + 32]
            if len(source) != 32:
                continue
            classes = Counter(byte_class(value) for value in source)
            windows.append(
                {
                    "manifest": manifest,
                    "source_start": source_start,
                    "source": source,
                    "known_mask": known,
                    "record": {
                        "rank": manifest.get("rank", ""),
                        "pcx_name": manifest.get("pcx_name", ""),
                        "frontier_id": manifest.get("frontier_id", ""),
                        "source_start": str(source_start),
                        "source_known_bytes": str(sum(1 for value in known if value)),
                        "source_high_plateau_bytes": str(classes.get("high_plateau", 0)),
                        "source_low_payload_bytes": str(classes.get("low_payload", 0)),
                        "source_control_high_bytes": str(classes.get("control_high", 0)),
                        "source_zero_bytes": str(classes.get("zero", 0)),
                        "source_head_hex": source[:16].hex(),
                    },
                }
            )
            if limit and len(windows) >= limit:
                return windows
    return windows


def candidate_score(target_row: dict[str, object], source_window: dict[str, object]) -> dict[str, str] | None:
    target = target_row["target"]
    target_data = target_row["data"]
    source_manifest = source_window["manifest"]
    source = source_window["source"]
    known_mask = source_window["known_mask"]
    assert isinstance(target, dict)
    assert isinstance(target_data, bytes)
    assert isinstance(source_manifest, dict)
    assert isinstance(source, bytes)
    assert isinstance(known_mask, bytes)
    target_start = int(target_row["row_start"])
    source_start = int(source_window["source_start"])
    same_fixture = fixture_key(target) == fixture_key(source_manifest)
    if same_fixture and max(source_start, target_start) < min(source_start + 32, target_start + 32):
        return None
    deltas = [signed_delta(source_value, target_value) for source_value, target_value in zip(source, target_data)]
    abs_deltas = [abs(delta) for delta in deltas]
    exact = sum(1 for delta in deltas if delta == 0)
    le1 = sum(1 for delta in abs_deltas if delta <= 1)
    le2 = sum(1 for delta in abs_deltas if delta <= 2)
    le4 = sum(1 for delta in abs_deltas if delta <= 4)
    if le2 < 18 and exact < 8:
        return None
    top_delta, top_delta_count = Counter(deltas).most_common(1)[0]
    classes = Counter(byte_class(value) for value in source)
    source_known = sum(1 for value in known_mask if value)
    return {
        "target_id": target.get("target_id", ""),
        "row_role": str(target_row["row_role"]),
        "target_rank": target.get("rank", ""),
        "target_frontier_id": target.get("frontier_id", ""),
        "target_start": str(target_start),
        "source_rank": source_manifest.get("rank", ""),
        "source_pcx_name": source_manifest.get("pcx_name", ""),
        "source_frontier_id": source_manifest.get("frontier_id", ""),
        "source_start": str(source_start),
        "same_fixture": "1" if same_fixture else "0",
        "relative_offset": str(source_start - target_start) if same_fixture else "",
        "source_known_bytes": str(source_known),
        "source_unknown_bytes": str(32 - source_known),
        "source_high_plateau_bytes": str(classes.get("high_plateau", 0)),
        "source_low_payload_bytes": str(classes.get("low_payload", 0)),
        "source_control_high_bytes": str(classes.get("control_high", 0)),
        "source_zero_bytes": str(classes.get("zero", 0)),
        "exact_bytes": str(exact),
        "small_delta_le1_bytes": str(le1),
        "small_delta_le2_bytes": str(le2),
        "small_delta_le4_bytes": str(le4),
        "mean_abs_delta": f"{sum(abs_deltas) / len(abs_deltas):.6f}",
        "top_delta": str(top_delta),
        "top_delta_count": str(top_delta_count),
        "source_head_hex": source[:16].hex(),
        "target_head_hex": target_data[:16].hex(),
    }


def build_candidates(
    target_rows: list[dict[str, object]],
    source_windows: list[dict[str, object]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for target_row in target_rows:
        for source_window in source_windows:
            candidate = candidate_score(target_row, source_window)
            if candidate:
                rows.append(candidate)
    rows.sort(
        key=lambda row: (
            -int_value(row, "small_delta_le2_bytes"),
            -int_value(row, "exact_bytes"),
            -int_value(row, "small_delta_le4_bytes"),
            -int_value(row, "source_known_bytes"),
            row.get("target_id", ""),
            row.get("row_role", ""),
        )
    )
    return rows


def best_by_target(candidate_rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    best: dict[tuple[str, str], dict[str, str]] = {}
    for row in candidate_rows:
        key = row.get("target_id", ""), row.get("row_role", "")
        current = best.get(key)
        if current is None:
            best[key] = row
            continue
        if (
            int_value(row, "small_delta_le2_bytes"),
            int_value(row, "exact_bytes"),
            int_value(row, "small_delta_le4_bytes"),
            int_value(row, "source_known_bytes"),
        ) > (
            int_value(current, "small_delta_le2_bytes"),
            int_value(current, "exact_bytes"),
            int_value(current, "small_delta_le4_bytes"),
            int_value(current, "source_known_bytes"),
        ):
            best[key] = row
    return best


def build_target_coverage(
    target_rows: list[dict[str, object]],
    candidate_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    by_key: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in candidate_rows:
        by_key.setdefault((row.get("target_id", ""), row.get("row_role", "")), []).append(row)
    best = best_by_target(candidate_rows)
    rows: list[dict[str, str]] = []
    for target_row in target_rows:
        target = target_row["target"]
        assert isinstance(target, dict)
        key = target.get("target_id", ""), str(target_row["row_role"])
        candidates = by_key.get(key, [])
        best_row = best.get(key, {})
        rows.append(
            {
                "target_id": key[0],
                "row_role": key[1],
                "target_rank": target.get("rank", ""),
                "target_frontier_id": target.get("frontier_id", ""),
                "target_start": str(target_row["row_start"]),
                "candidate_rows": str(len(candidates)),
                "known_source_candidate_rows": str(
                    sum(1 for row in candidates if int_value(row, "source_known_bytes") == 32)
                ),
                "unknown_source_candidate_rows": str(
                    sum(1 for row in candidates if int_value(row, "source_known_bytes") < 32)
                ),
                "best_exact_bytes": best_row.get("exact_bytes", "0"),
                "best_small_delta_le2_bytes": best_row.get("small_delta_le2_bytes", "0"),
                "best_small_delta_le4_bytes": best_row.get("small_delta_le4_bytes", "0"),
                "best_source_known_bytes": best_row.get("source_known_bytes", "0"),
                "best_source_rank": best_row.get("source_rank", ""),
                "best_source_frontier_id": best_row.get("source_frontier_id", ""),
                "best_source_start": best_row.get("source_start", ""),
            }
        )
    rows.sort(
        key=lambda row: (
            row.get("row_role", ""),
            -int_value(row, "best_small_delta_le2_bytes"),
            row.get("target_id", ""),
        )
    )
    return rows


def build_summary(
    *,
    target_runs: int,
    target_rows: list[dict[str, object]],
    source_windows: list[dict[str, object]],
    candidate_rows: list[dict[str, str]],
    issues: list[str],
) -> dict[str, str]:
    best = candidate_rows[0] if candidate_rows else {}
    coverage = build_target_coverage(target_rows, candidate_rows)
    rows_with_candidate = sum(1 for row in coverage if int_value(row, "candidate_rows") > 0)
    low1_rows = [row for row in coverage if row.get("row_role") == "low1"]
    low2_rows = [row for row in coverage if row.get("row_role") == "low2"]
    best_values = [row for row in coverage if int_value(row, "candidate_rows") > 0]
    known_source_candidate_rows = sum(1 for row in candidate_rows if int_value(row, "source_known_bytes") == 32)
    unknown_source_candidate_rows = sum(1 for row in candidate_rows if int_value(row, "source_known_bytes") < 32)
    low1_cover = sum(1 for row in low1_rows if int_value(row, "candidate_rows") > 0)
    low2_cover = sum(1 for row in low2_rows if int_value(row, "candidate_rows") > 0)
    if known_source_candidate_rows > 0:
        verdict = "frontier80_context_residual_low_payload_corpus_known_source_signal"
        next_probe = "promote known-source low-payload corpus candidates with guards"
    elif low1_cover and not low2_cover:
        verdict = "frontier80_context_residual_low_payload_corpus_low1_unknown_source_only"
        next_probe = "derive unknown low1 source windows and broaden low2 transform search"
    elif unknown_source_candidate_rows > 0:
        verdict = "frontier80_context_residual_low_payload_corpus_unknown_source_signal"
        next_probe = "resolve unknown low-payload corpus sources before promotion"
    else:
        verdict = "frontier80_context_residual_low_payload_corpus_no_source_signal"
        next_probe = "expand low-payload grammar beyond fixed 32-byte corpus windows"
    return {
        "scope": "total",
        "target_runs": str(target_runs),
        "target_low_rows": str(len(target_rows)),
        "target_low_bytes": str(len(target_rows) * 32),
        "source_windows": str(len(source_windows)),
        "candidate_rows": str(len(candidate_rows)),
        "known_source_candidate_rows": str(known_source_candidate_rows),
        "unknown_source_candidate_rows": str(unknown_source_candidate_rows),
        "target_rows_with_candidate": str(rows_with_candidate),
        "target_rows_without_candidate": str(len(target_rows) - rows_with_candidate),
        "low1_rows_with_candidate": str(low1_cover),
        "low2_rows_with_candidate": str(low2_cover),
        "best_candidate_target": best.get("target_id", ""),
        "best_candidate_role": best.get("row_role", ""),
        "best_candidate_source_rank": best.get("source_rank", ""),
        "best_candidate_source_frontier": best.get("source_frontier_id", ""),
        "best_candidate_source_start": best.get("source_start", ""),
        "best_candidate_exact_bytes": best.get("exact_bytes", "0"),
        "best_candidate_small_delta_le2_bytes": best.get("small_delta_le2_bytes", "0"),
        "best_candidate_small_delta_le4_bytes": best.get("small_delta_le4_bytes", "0"),
        "best_candidate_source_known_bytes": best.get("source_known_bytes", "0"),
        "best_per_target_small_delta_le2_min": str(
            min((int_value(row, "best_small_delta_le2_bytes") for row in best_values), default=0)
        ),
        "best_per_target_exact_min": str(min((int_value(row, "best_exact_bytes") for row in best_values), default=0)),
        "best_per_target_source_known_min": str(
            min((int_value(row, "best_source_known_bytes") for row in best_values), default=0)
        ),
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
    coverage: list[dict[str, str]],
    candidates: list[dict[str, str]],
    source_windows: list[dict[str, str]],
    title: str,
) -> str:
    summary_json = html.escape(json.dumps(summary, indent=2))
    stats = "".join(
        f"<div class=\"stat\"><div class=\"label\">{html.escape(key)}</div>"
        f"<div class=\"value\">{html.escape(summary.get(key, ''))}</div></div>"
        for key in (
            "target_low_rows",
            "candidate_rows",
            "target_rows_with_candidate",
            "low1_rows_with_candidate",
            "low2_rows_with_candidate",
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
  {table_html("Target coverage", "target_coverage.csv", coverage, TARGET_COVERAGE_FIELDNAMES)}
  {table_html("Best candidates", "candidates.csv", candidates, CANDIDATE_FIELDNAMES)}
  {table_html("Targets", "targets.csv", targets, TARGET_FIELDNAMES)}
  {table_html("Source windows sample", "source_windows.csv", source_windows, SOURCE_WINDOW_FIELDNAMES)}
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Search corpus-wide 32-byte source windows for saturated Frontier80 low-payload rows."
    )
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--runs", type=Path, default=DEFAULT_RUNS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--clean-fixtures", type=Path, default=DEFAULT_CLEAN_FIXTURES)
    parser.add_argument("--source-window-limit", type=int, default=0)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Context Split Residual Low Payload Corpus Source Probe",
    )
    args = parser.parse_args()

    issues: list[str] = []
    run_rows = read_csv(args.runs)
    manifest_rows = read_csv(args.manifest)
    clean_rows = read_csv(args.clean_fixtures)
    target_runs = load_target_runs(run_rows, manifest_rows, clean_rows, issues)
    target_rows = low_target_rows(target_runs, issues)
    target_output_rows = [target_row_record(row) for row in target_rows]
    source_windows = load_source_windows(manifest_rows, clean_rows, issues, limit=args.source_window_limit)
    candidate_rows = build_candidates(target_rows, source_windows)
    coverage_rows = build_target_coverage(target_rows, candidate_rows)
    source_window_rows = [window["record"] for window in source_windows]
    summary = build_summary(
        target_runs=len(target_runs),
        target_rows=target_rows,
        source_windows=source_windows,
        candidate_rows=candidate_rows,
        issues=issues,
    )

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, target_output_rows)
    write_csv(args.output / "target_coverage.csv", TARGET_COVERAGE_FIELDNAMES, coverage_rows)
    write_csv(args.output / "candidates.csv", CANDIDATE_FIELDNAMES, candidate_rows)
    write_csv(args.output / "source_windows.csv", SOURCE_WINDOW_FIELDNAMES, source_window_rows)
    (args.output / "issues.txt").write_text("\n".join(issues))
    html_path = args.output / "index.html"
    html_path.write_text(
        build_html(summary, target_output_rows, coverage_rows, candidate_rows, source_window_rows, args.title)
    )

    print(f"Source windows: {summary['source_windows']}")
    print(f"Candidate rows: {summary['candidate_rows']}")
    print(
        "Target coverage: "
        f"{summary['target_rows_with_candidate']}/{summary['target_low_rows']} "
        f"(low1={summary['low1_rows_with_candidate']}, low2={summary['low2_rows_with_candidate']})"
    )
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
