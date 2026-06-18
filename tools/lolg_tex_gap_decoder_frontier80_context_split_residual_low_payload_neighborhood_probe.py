#!/usr/bin/env python3
"""Probe low-payload row producers after saturated Frontier80 residual replay."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter
from pathlib import Path

from lolg_tex_gap_opcode_probe import int_value, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_frontier80_context_split_residual_low_payload_neighborhood_probe")
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
    "best_shared_relative_offset",
    "best_shared_small_delta_le2_bytes",
    "best_shared_small_delta_le2_ratio",
    "best_shared_exact_bytes",
    "best_shared_source_known_min",
    "best_role",
    "best_role_relative_offset",
    "best_role_small_delta_le2_bytes",
    "best_role_small_delta_le2_ratio",
    "best_role_exact_bytes",
    "best_role_source_known_min",
    "best_per_row_small_delta_le2_min",
    "best_per_row_exact_min",
    "best_per_row_source_known_min",
    "candidate_rows",
    "shared_relative_rows",
    "role_relative_rows",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

CANDIDATE_FIELDNAMES = [
    "target_id",
    "row_role",
    "row_index",
    "rank",
    "pcx_name",
    "frontier_id",
    "target_start",
    "source_start",
    "relative_offset",
    "exact_bytes",
    "small_delta_le1_bytes",
    "small_delta_le2_bytes",
    "small_delta_le4_bytes",
    "mean_abs_delta",
    "top_delta",
    "top_delta_count",
    "source_known_bytes",
    "source_high_plateau_bytes",
    "source_low_payload_bytes",
    "source_control_high_bytes",
    "source_zero_bytes",
    "source_head_hex",
    "target_head_hex",
]

RELATIVE_FIELDNAMES = [
    "relative_offset",
    "target_rows",
    "small_delta_le2_bytes",
    "small_delta_le2_ratio",
    "exact_bytes",
    "source_known_min",
    "source_known_total",
    "top_delta_signature",
]

ROLE_RELATIVE_FIELDNAMES = [
    "row_role",
    "relative_offset",
    "target_rows",
    "small_delta_le2_bytes",
    "small_delta_le2_ratio",
    "exact_bytes",
    "source_known_min",
    "source_known_total",
    "top_delta_signature",
]

TARGET_FIELDNAMES = [
    "target_id",
    "row_role",
    "row_index",
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "span_index",
    "run_index",
    "run_start",
    "row_start",
    "row_end",
    "row_hex",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def fixture_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", "")


def target_id(row: dict[str, str]) -> str:
    return (
        f"r{int_value(row, 'rank'):03d}_f{row.get('frontier_id', '')}_"
        f"s{row.get('span_index', '')}_run{row.get('run_index', '')}"
    )


def signed_delta(source: int, target: int) -> int:
    value = (target - source) & 0xFF
    return value if value < 128 else value - 256


def byte_class(value: int) -> str:
    if 0x67 <= value <= 0x6E:
        return "high_plateau"
    if 0x4F <= value <= 0x5B:
        return "low_payload"
    if value >= 0x80:
        return "control_high"
    if value == 0:
        return "zero"
    return "other"


def load_target_runs(
    run_rows: list[dict[str, str]],
    manifest_rows: list[dict[str, str]],
    clean_rows: list[dict[str, str]],
    issues: list[str],
) -> list[tuple[dict[str, str], bytes, bytes]]:
    manifest_by_key = {fixture_key(row): row for row in manifest_rows}
    clean_by_key = {fixture_key(row): row for row in clean_rows}
    nonzero = [row for row in run_rows if row.get("run_class") == "nonzero"]
    if not nonzero:
        issues.append("missing_nonzero_run_rows")
        return []
    largest = max(int_value(row, "length") for row in nonzero)
    targets: list[tuple[dict[str, str], bytes, bytes]] = []
    for row in nonzero:
        if int_value(row, "length") != largest:
            continue
        key = fixture_key(row)
        manifest = manifest_by_key.get(key)
        clean = clean_by_key.get(key)
        if not manifest:
            issues.append(f"{target_id(row)}:missing_manifest_row")
            continue
        if not clean:
            issues.append(f"{target_id(row)}:missing_clean_fixture_row")
            continue
        try:
            expected = Path(manifest.get("expected_gap_path", "")).read_bytes()
            known_mask = Path(clean.get("known_mask_path", "")).read_bytes()
        except OSError as exc:
            issues.append(f"{target_id(row)}:read_fixture_failed:{exc}")
            continue
        targets.append(({**row, "target_id": target_id(row)}, expected, known_mask))
    return targets


def low_target_rows(targets: list[tuple[dict[str, str], bytes, bytes]], issues: list[str]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for target, expected, known_mask in targets:
        run_start = int_value(target, "start")
        run_end = int_value(target, "end")
        if run_end - run_start < 96:
            issues.append(f"{target.get('target_id', '')}:largest_run_shorter_than_96")
            continue
        for row_index, row_role in ((1, "low1"), (2, "low2")):
            row_start = run_start + row_index * 32
            row_end = row_start + 32
            data = expected[row_start:row_end]
            if len(data) != 32:
                issues.append(f"{target.get('target_id', '')}:{row_role}:row_out_of_bounds")
                continue
            rows.append(
                {
                    "target": target,
                    "expected": expected,
                    "known_mask": known_mask,
                    "row_role": row_role,
                    "row_index": row_index,
                    "row_start": row_start,
                    "row_end": row_end,
                    "data": data,
                }
            )
    return rows


def target_row_record(row: dict[str, object]) -> dict[str, str]:
    target = row["target"]
    assert isinstance(target, dict)
    data = row["data"]
    assert isinstance(data, bytes)
    return {
        "target_id": target.get("target_id", ""),
        "row_role": str(row["row_role"]),
        "row_index": str(row["row_index"]),
        "rank": target.get("rank", ""),
        "archive": target.get("archive", ""),
        "archive_tag": target.get("archive_tag", ""),
        "pcx_name": target.get("pcx_name", ""),
        "frontier_id": target.get("frontier_id", ""),
        "span_index": target.get("span_index", ""),
        "run_index": target.get("run_index", ""),
        "run_start": target.get("start", ""),
        "row_start": str(row["row_start"]),
        "row_end": str(row["row_end"]),
        "row_hex": data.hex(),
    }


def score_candidate(row: dict[str, object], relative_offset: int) -> dict[str, str] | None:
    target = row["target"]
    expected = row["expected"]
    known_mask = row["known_mask"]
    data = row["data"]
    assert isinstance(target, dict)
    assert isinstance(expected, bytes)
    assert isinstance(known_mask, bytes)
    assert isinstance(data, bytes)
    target_start = int(row["row_start"])
    source_start = target_start + relative_offset
    if source_start < 0 or source_start + 32 > len(expected):
        return None
    if max(source_start, target_start) < min(source_start + 32, target_start + 32):
        return None
    source = expected[source_start : source_start + 32]
    deltas = [signed_delta(source_value, target_value) for source_value, target_value in zip(source, data)]
    abs_deltas = [abs(delta) for delta in deltas]
    top_delta, top_delta_count = Counter(deltas).most_common(1)[0]
    source_classes = Counter(byte_class(value) for value in source)
    return {
        "target_id": target.get("target_id", ""),
        "row_role": str(row["row_role"]),
        "row_index": str(row["row_index"]),
        "rank": target.get("rank", ""),
        "pcx_name": target.get("pcx_name", ""),
        "frontier_id": target.get("frontier_id", ""),
        "target_start": str(target_start),
        "source_start": str(source_start),
        "relative_offset": str(relative_offset),
        "exact_bytes": str(sum(1 for delta in deltas if delta == 0)),
        "small_delta_le1_bytes": str(sum(1 for delta in abs_deltas if delta <= 1)),
        "small_delta_le2_bytes": str(sum(1 for delta in abs_deltas if delta <= 2)),
        "small_delta_le4_bytes": str(sum(1 for delta in abs_deltas if delta <= 4)),
        "mean_abs_delta": f"{sum(abs_deltas) / len(abs_deltas):.6f}",
        "top_delta": str(top_delta),
        "top_delta_count": str(top_delta_count),
        "source_known_bytes": str(sum(1 for value in known_mask[source_start : source_start + 32] if value)),
        "source_high_plateau_bytes": str(source_classes.get("high_plateau", 0)),
        "source_low_payload_bytes": str(source_classes.get("low_payload", 0)),
        "source_control_high_bytes": str(source_classes.get("control_high", 0)),
        "source_zero_bytes": str(source_classes.get("zero", 0)),
        "source_head_hex": source[:16].hex(),
        "target_head_hex": data[:16].hex(),
    }


def build_candidate_rows(
    target_rows: list[dict[str, object]],
    *,
    max_relative: int,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in target_rows:
        for relative_offset in range(-max_relative, max_relative + 1):
            candidate = score_candidate(row, relative_offset)
            if not candidate:
                continue
            if int_value(candidate, "small_delta_le2_bytes") >= 18 or int_value(candidate, "exact_bytes") >= 8:
                rows.append(candidate)
    rows.sort(
        key=lambda candidate: (
            -int_value(candidate, "small_delta_le2_bytes"),
            -int_value(candidate, "exact_bytes"),
            -int_value(candidate, "source_known_bytes"),
            abs(int_value(candidate, "relative_offset")),
            candidate.get("row_role", ""),
            candidate.get("target_id", ""),
        )
    )
    return rows


def aggregate_rows(candidate_rows: list[dict[str, str]], target_count: int) -> list[dict[str, str]]:
    by_relative: dict[int, list[dict[str, str]]] = {}
    for row in candidate_rows:
        by_relative.setdefault(int_value(row, "relative_offset"), []).append(row)
    rows: list[dict[str, str]] = []
    for relative_offset, rel_rows in by_relative.items():
        unique_targets = {f"{row.get('target_id', '')}:{row.get('row_role', '')}" for row in rel_rows}
        if len(unique_targets) != target_count:
            continue
        small_total = sum(int_value(row, "small_delta_le2_bytes") for row in rel_rows)
        exact_total = sum(int_value(row, "exact_bytes") for row in rel_rows)
        known_values = [int_value(row, "source_known_bytes") for row in rel_rows]
        rows.append(
            {
                "relative_offset": str(relative_offset),
                "target_rows": str(len(unique_targets)),
                "small_delta_le2_bytes": str(small_total),
                "small_delta_le2_ratio": f"{small_total / (target_count * 32):.6f}",
                "exact_bytes": str(exact_total),
                "source_known_min": str(min(known_values) if known_values else 0),
                "source_known_total": str(sum(known_values)),
                "top_delta_signature": "|".join(
                    f"{row.get('top_delta', '')}:{row.get('top_delta_count', '')}" for row in rel_rows
                ),
            }
        )
    rows.sort(
        key=lambda row: (
            -int_value(row, "small_delta_le2_bytes"),
            -int_value(row, "exact_bytes"),
            -int_value(row, "source_known_min"),
            abs(int_value(row, "relative_offset")),
        )
    )
    return rows


def aggregate_role_rows(
    candidate_rows: list[dict[str, str]],
    *,
    target_runs: int,
) -> list[dict[str, str]]:
    by_key: dict[tuple[str, int], list[dict[str, str]]] = {}
    for row in candidate_rows:
        by_key.setdefault((row.get("row_role", ""), int_value(row, "relative_offset")), []).append(row)
    rows: list[dict[str, str]] = []
    for (row_role, relative_offset), rel_rows in by_key.items():
        unique_targets = {row.get("target_id", "") for row in rel_rows}
        if len(unique_targets) != target_runs:
            continue
        small_total = sum(int_value(row, "small_delta_le2_bytes") for row in rel_rows)
        exact_total = sum(int_value(row, "exact_bytes") for row in rel_rows)
        known_values = [int_value(row, "source_known_bytes") for row in rel_rows]
        rows.append(
            {
                "row_role": row_role,
                "relative_offset": str(relative_offset),
                "target_rows": str(len(unique_targets)),
                "small_delta_le2_bytes": str(small_total),
                "small_delta_le2_ratio": f"{small_total / (target_runs * 32):.6f}",
                "exact_bytes": str(exact_total),
                "source_known_min": str(min(known_values) if known_values else 0),
                "source_known_total": str(sum(known_values)),
                "top_delta_signature": "|".join(
                    f"{row.get('top_delta', '')}:{row.get('top_delta_count', '')}" for row in rel_rows
                ),
            }
        )
    rows.sort(
        key=lambda row: (
            -int_value(row, "small_delta_le2_bytes"),
            -int_value(row, "exact_bytes"),
            -int_value(row, "source_known_min"),
            row.get("row_role", ""),
            abs(int_value(row, "relative_offset")),
        )
    )
    return rows


def best_per_target(candidate_rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    best: dict[str, dict[str, str]] = {}
    for row in candidate_rows:
        key = f"{row.get('target_id', '')}:{row.get('row_role', '')}"
        current = best.get(key)
        if current is None:
            best[key] = row
            continue
        if (
            int_value(row, "small_delta_le2_bytes"),
            int_value(row, "exact_bytes"),
            int_value(row, "source_known_bytes"),
        ) > (
            int_value(current, "small_delta_le2_bytes"),
            int_value(current, "exact_bytes"),
            int_value(current, "source_known_bytes"),
        ):
            best[key] = row
    return best


def build_summary(
    *,
    target_runs: int,
    target_low_rows: int,
    candidate_rows: list[dict[str, str]],
    relative_rows: list[dict[str, str]],
    role_relative_rows: list[dict[str, str]],
    issues: list[str],
) -> dict[str, str]:
    best_shared = relative_rows[0] if relative_rows else {}
    best_role = role_relative_rows[0] if role_relative_rows else {}
    per_target = best_per_target(candidate_rows)
    per_target_values = list(per_target.values())
    best_per_row_small_min = min((int_value(row, "small_delta_le2_bytes") for row in per_target_values), default=0)
    best_per_row_exact_min = min((int_value(row, "exact_bytes") for row in per_target_values), default=0)
    best_per_row_known_min = min((int_value(row, "source_known_bytes") for row in per_target_values), default=0)
    role_signal = (
        int_value(best_role, "target_rows") == target_runs
        and int_value(best_role, "small_delta_le2_bytes") >= target_runs * 24
        and int_value(best_role, "source_known_min") > 0
    )
    shared_signal = (
        int_value(best_shared, "target_rows") == target_low_rows
        and int_value(best_shared, "small_delta_le2_bytes") >= target_low_rows * 24
        and int_value(best_shared, "source_known_min") > 0
    )
    if role_signal:
        verdict = "frontier80_context_residual_low_payload_role_delta_signal"
        next_probe = "derive row-role low-payload producer for saturated context-split residual runs"
    elif shared_signal:
        verdict = "frontier80_context_residual_low_payload_shared_delta_signal"
        next_probe = "derive shared-offset low-payload producer for saturated context-split residual runs"
    else:
        verdict = "frontier80_context_residual_low_payload_neighborhood_profile"
        next_probe = "expand low-payload source search beyond local relative windows"
    return {
        "scope": "total",
        "target_runs": str(target_runs),
        "target_low_rows": str(target_low_rows),
        "target_low_bytes": str(target_low_rows * 32),
        "best_shared_relative_offset": best_shared.get("relative_offset", ""),
        "best_shared_small_delta_le2_bytes": best_shared.get("small_delta_le2_bytes", "0"),
        "best_shared_small_delta_le2_ratio": best_shared.get("small_delta_le2_ratio", "0.000000"),
        "best_shared_exact_bytes": best_shared.get("exact_bytes", "0"),
        "best_shared_source_known_min": best_shared.get("source_known_min", "0"),
        "best_role": best_role.get("row_role", ""),
        "best_role_relative_offset": best_role.get("relative_offset", ""),
        "best_role_small_delta_le2_bytes": best_role.get("small_delta_le2_bytes", "0"),
        "best_role_small_delta_le2_ratio": best_role.get("small_delta_le2_ratio", "0.000000"),
        "best_role_exact_bytes": best_role.get("exact_bytes", "0"),
        "best_role_source_known_min": best_role.get("source_known_min", "0"),
        "best_per_row_small_delta_le2_min": str(best_per_row_small_min),
        "best_per_row_exact_min": str(best_per_row_exact_min),
        "best_per_row_source_known_min": str(best_per_row_known_min),
        "candidate_rows": str(len(candidate_rows)),
        "shared_relative_rows": str(len(relative_rows)),
        "role_relative_rows": str(len(role_relative_rows)),
        "issue_rows": str(len(issues)),
        "review_verdict": verdict,
        "next_probe": next_probe,
    }


def table_html(title: str, path: Path, rows: list[dict[str, str]], fields: list[str], limit: int = 20) -> str:
    if not rows:
        return f"<section><h2>{html.escape(title)}</h2><p>No rows.</p></section>"
    headers = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = []
    for row in rows[:limit]:
        body.append("<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>")
    return (
        f"<section><h2>{html.escape(title)}</h2>"
        f"<p><a href=\"{html.escape(path.name)}\">{html.escape(path.name)}</a></p>"
        f"<table><thead><tr>{headers}</tr></thead><tbody>{''.join(body)}</tbody></table></section>"
    )


def build_html(
    summary: dict[str, str],
    target_rows: list[dict[str, str]],
    candidate_rows: list[dict[str, str]],
    relative_rows: list[dict[str, str]],
    role_relative_rows: list[dict[str, str]],
    title: str,
) -> str:
    summary_json = html.escape(json.dumps(summary, indent=2))
    stat_keys = [
        "target_runs",
        "target_low_rows",
        "best_role",
        "best_role_relative_offset",
        "best_role_small_delta_le2_bytes",
        "best_role_source_known_min",
        "review_verdict",
    ]
    stats = "".join(
        f"<div class=\"stat\"><div class=\"label\">{html.escape(key)}</div>"
        f"<div class=\"value\">{html.escape(summary.get(key, ''))}</div></div>"
        for key in stat_keys
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
  {table_html("Role-relative offsets", Path("role_relative_offsets.csv"), role_relative_rows, ROLE_RELATIVE_FIELDNAMES)}
  {table_html("Shared-relative offsets", Path("relative_offsets.csv"), relative_rows, RELATIVE_FIELDNAMES)}
  {table_html("Best candidates", Path("candidates.csv"), candidate_rows, CANDIDATE_FIELDNAMES)}
  {table_html("Targets", Path("targets.csv"), target_rows, TARGET_FIELDNAMES)}
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Probe low-payload row sources after saturated Frontier80 context-split residual replay."
    )
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--runs", type=Path, default=DEFAULT_RUNS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--clean-fixtures", type=Path, default=DEFAULT_CLEAN_FIXTURES)
    parser.add_argument("--max-relative", type=int, default=512)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Context Split Residual Low Payload Neighborhood Probe",
    )
    args = parser.parse_args()

    issues: list[str] = []
    run_rows = read_csv(args.runs)
    manifest_rows = read_csv(args.manifest)
    clean_rows = read_csv(args.clean_fixtures)
    target_runs = load_target_runs(run_rows, manifest_rows, clean_rows, issues)
    low_rows = low_target_rows(target_runs, issues)
    target_output_rows = [target_row_record(row) for row in low_rows]
    candidate_rows = build_candidate_rows(low_rows, max_relative=args.max_relative)
    relative_rows = aggregate_rows(candidate_rows, len(low_rows))
    role_relative_rows = aggregate_role_rows(candidate_rows, target_runs=len(target_runs))
    summary = build_summary(
        target_runs=len(target_runs),
        target_low_rows=len(low_rows),
        candidate_rows=candidate_rows,
        relative_rows=relative_rows,
        role_relative_rows=role_relative_rows,
        issues=issues,
    )

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, target_output_rows)
    write_csv(args.output / "candidates.csv", CANDIDATE_FIELDNAMES, candidate_rows)
    write_csv(args.output / "relative_offsets.csv", RELATIVE_FIELDNAMES, relative_rows)
    write_csv(args.output / "role_relative_offsets.csv", ROLE_RELATIVE_FIELDNAMES, role_relative_rows)
    (args.output / "issues.txt").write_text("\n".join(issues))
    html_path = args.output / "index.html"
    html_path.write_text(
        build_html(summary, target_output_rows, candidate_rows, relative_rows, role_relative_rows, args.title)
    )

    print(f"Target low rows: {summary['target_low_rows']}")
    print(
        "Best role offset: "
        f"{summary['best_role']} {summary['best_role_relative_offset']} "
        f"{summary['best_role_small_delta_le2_bytes']}/{int_value(summary, 'target_runs') * 32}"
    )
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
