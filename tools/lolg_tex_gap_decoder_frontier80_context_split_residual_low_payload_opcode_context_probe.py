#!/usr/bin/env python3
"""Profile opcode/control context for Frontier80 low-payload residual rows."""

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
    target_row_record,
)
from lolg_tex_gap_opcode_probe import int_value, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_frontier80_context_split_residual_low_payload_opcode_context_probe")
DEFAULT_RUNS = Path("output/tex_gap_decoder_unresolved_run_probe_frontier80_context_split_residual_second_replay/runs.csv")
DEFAULT_MANIFEST = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_CLEAN_FIXTURES = Path(
    "output/tex_gap_decoder_frontier80_context_split_residual_second_fixture_replay/fixtures.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "target_runs",
    "target_rows",
    "target_bytes",
    "compact_control_target_rows",
    "manifest_control_signatures",
    "manifest_control_signature_run_max",
    "role_manifest_control_signatures",
    "run_context_signatures",
    "run_context_signature_run_max",
    "role_run_context_signatures",
    "row0_unknown_runs",
    "row0_high_plateau_runs",
    "pre_context_known_min",
    "pre_context_known_max",
    "post_context_known_min",
    "post_zero_prefix_min",
    "segment_gap_bytes_min",
    "segment_gap_bytes_max",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

RUN_FIELDNAMES = [
    "target_id",
    "rank",
    "pcx_name",
    "frontier_id",
    "run_start",
    "run_end",
    "run_length",
    "rule_type",
    "opcode0_hex",
    "opcode1_hex",
    "control_prefix_bytes",
    "control_prefix_hex",
    "fragment_bytes",
    "fragment_hex",
    "segment_gap_bytes",
    "segment_control_high_bytes",
    "segment_high_plateau_bytes",
    "segment_low_payload_bytes",
    "segment_other_bytes",
    "manifest_control_signature",
    "run_context_signature",
    "pre32_known_bytes",
    "row0_known_bytes",
    "post32_known_bytes",
    "post_zero_prefix_bytes",
    "pre32_high_plateau_bytes",
    "row0_high_plateau_bytes",
    "low1_low_payload_bytes",
    "low1_control_high_bytes",
    "low2_low_payload_bytes",
    "low2_control_high_bytes",
    "pre32_head_hex",
    "row0_head_hex",
    "low1_head_hex",
    "low2_head_hex",
    "post32_head_hex",
]

ROW_FIELDNAMES = [
    "target_id",
    "row_role",
    "rank",
    "pcx_name",
    "frontier_id",
    "run_start",
    "row_start",
    "rule_type",
    "opcode0_hex",
    "opcode1_hex",
    "control_prefix_hex",
    "fragment_hex",
    "segment_gap_bytes",
    "manifest_control_signature",
    "role_manifest_control_signature",
    "run_context_signature",
    "role_run_context_signature",
    "manifest_signature_run_rows",
    "run_context_signature_run_rows",
    "role_manifest_signature_rows",
    "role_run_context_signature_rows",
    "pre32_known_bytes",
    "row0_known_bytes",
    "post32_known_bytes",
    "row0_high_plateau_bytes",
    "row_low_payload_bytes",
    "row_control_high_bytes",
    "row_head_hex",
]


def load_bytes(path_text: str, issues: list[str], label: str, key: tuple[str, str, str]) -> bytes:
    try:
        return Path(path_text).read_bytes()
    except OSError as exc:
        issues.append(f"{key}:{label}:read_failed:{exc}")
        return b""


def row_target(row: dict[str, object]) -> dict[str, str]:
    target = row["target"]
    assert isinstance(target, dict)
    return target


def row_data(row: dict[str, object]) -> bytes:
    data = row["data"]
    assert isinstance(data, bytes)
    return data


def class_counts(data: bytes) -> Counter[str]:
    return Counter(byte_class(value) for value in data)


def count_class(data: bytes, class_name: str) -> int:
    return class_counts(data).get(class_name, 0)


def zero_prefix(data: bytes) -> int:
    count = 0
    for value in data:
        if value != 0:
            break
        count += 1
    return count


def manifest_signature(manifest: dict[str, str], control_prefix: bytes, fragment: bytes) -> str:
    return "|".join(
        (
            manifest.get("rule_type", ""),
            manifest.get("opcode0_hex", ""),
            manifest.get("opcode1_hex", ""),
            control_prefix.hex(),
            fragment.hex(),
        )
    )


def context_signature(
    target: dict[str, str],
    pre32: bytes,
    row0: bytes,
    post32: bytes,
) -> str:
    return "|".join(
        (
            target.get("rank", ""),
            target.get("frontier_id", ""),
            target.get("start", ""),
            pre32[:8].hex(),
            row0[:8].hex(),
            post32[:8].hex(),
        )
    )


def run_record(
    target: dict[str, str],
    expected: bytes,
    known_mask: bytes,
    manifest: dict[str, str],
    issues: list[str],
) -> dict[str, str]:
    key = fixture_key(target)
    segment = load_bytes(manifest.get("segment_gap_path", ""), issues, "segment", key)
    control_prefix = load_bytes(manifest.get("control_prefix_path", ""), issues, "control_prefix", key)
    fragment = load_bytes(manifest.get("fragment_path", ""), issues, "fragment", key)
    run_start = int_value(target, "start")
    run_end = int_value(target, "end")
    pre32 = expected[max(0, run_start - 32) : run_start]
    row0 = expected[run_start : run_start + 32]
    low1 = expected[run_start + 32 : run_start + 64]
    low2 = expected[run_start + 64 : run_start + 96]
    post32 = expected[run_end : min(len(expected), run_end + 32)]
    pre_known = known_mask[max(0, run_start - 32) : run_start]
    row0_known = known_mask[run_start : run_start + 32]
    post_known = known_mask[run_end : min(len(known_mask), run_end + 32)]
    segment_counts = class_counts(segment)
    manifest_sig = manifest_signature(manifest, control_prefix, fragment)
    run_sig = context_signature(target, pre32, row0, post32)
    return {
        "target_id": target.get("target_id", ""),
        "rank": target.get("rank", ""),
        "pcx_name": target.get("pcx_name", ""),
        "frontier_id": target.get("frontier_id", ""),
        "run_start": str(run_start),
        "run_end": str(run_end),
        "run_length": str(run_end - run_start),
        "rule_type": manifest.get("rule_type", ""),
        "opcode0_hex": manifest.get("opcode0_hex", ""),
        "opcode1_hex": manifest.get("opcode1_hex", ""),
        "control_prefix_bytes": str(len(control_prefix)),
        "control_prefix_hex": control_prefix.hex(),
        "fragment_bytes": str(len(fragment)),
        "fragment_hex": fragment.hex(),
        "segment_gap_bytes": str(len(segment)),
        "segment_control_high_bytes": str(segment_counts.get("control_high", 0)),
        "segment_high_plateau_bytes": str(segment_counts.get("high_plateau", 0)),
        "segment_low_payload_bytes": str(segment_counts.get("low_payload", 0)),
        "segment_other_bytes": str(
            len(segment)
            - segment_counts.get("control_high", 0)
            - segment_counts.get("high_plateau", 0)
            - segment_counts.get("low_payload", 0)
        ),
        "manifest_control_signature": manifest_sig,
        "run_context_signature": run_sig,
        "pre32_known_bytes": str(sum(1 for value in pre_known if value)),
        "row0_known_bytes": str(sum(1 for value in row0_known if value)),
        "post32_known_bytes": str(sum(1 for value in post_known if value)),
        "post_zero_prefix_bytes": str(zero_prefix(post32)),
        "pre32_high_plateau_bytes": str(count_class(pre32, "high_plateau")),
        "row0_high_plateau_bytes": str(count_class(row0, "high_plateau")),
        "low1_low_payload_bytes": str(count_class(low1, "low_payload")),
        "low1_control_high_bytes": str(count_class(low1, "control_high")),
        "low2_low_payload_bytes": str(count_class(low2, "low_payload")),
        "low2_control_high_bytes": str(count_class(low2, "control_high")),
        "pre32_head_hex": pre32[:16].hex(),
        "row0_head_hex": row0[:16].hex(),
        "low1_head_hex": low1[:16].hex(),
        "low2_head_hex": low2[:16].hex(),
        "post32_head_hex": post32[:16].hex(),
    }


def build_run_rows(
    target_runs: list[tuple[dict[str, str], bytes, bytes]],
    manifest_rows: list[dict[str, str]],
    issues: list[str],
) -> list[dict[str, str]]:
    manifest_by_key = {fixture_key(row): row for row in manifest_rows}
    rows: list[dict[str, str]] = []
    for target, expected, known_mask in target_runs:
        manifest = manifest_by_key.get(fixture_key(target))
        if not manifest:
            issues.append(f"{target.get('target_id', '')}:missing_manifest_row")
            continue
        rows.append(run_record(target, expected, known_mask, manifest, issues))
    rows.sort(key=lambda row: (int_value(row, "rank"), int_value(row, "run_start")))
    return rows


def signature_counts(rows: list[dict[str, str]], field: str) -> Counter[str]:
    return Counter(row.get(field, "") for row in rows)


def build_context_rows(
    target_rows: list[dict[str, object]],
    run_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    run_by_id = {row.get("target_id", ""): row for row in run_rows}
    manifest_run_counts = signature_counts(run_rows, "manifest_control_signature")
    context_run_counts = signature_counts(run_rows, "run_context_signature")
    role_manifest_counts: Counter[str] = Counter()
    role_context_counts: Counter[str] = Counter()
    pending_rows: list[dict[str, str]] = []
    for target_row in target_rows:
        target = row_target(target_row)
        run = run_by_id.get(target.get("target_id", ""), {})
        role_manifest = f"{target_row.get('row_role', '')}|{run.get('manifest_control_signature', '')}"
        role_context = f"{target_row.get('row_role', '')}|{run.get('run_context_signature', '')}"
        role_manifest_counts[role_manifest] += 1
        role_context_counts[role_context] += 1
        pending_rows.append({"role_manifest": role_manifest, "role_context": role_context})

    rows: list[dict[str, str]] = []
    for target_row, pending in zip(target_rows, pending_rows):
        target = row_target(target_row)
        run = run_by_id.get(target.get("target_id", ""), {})
        data = row_data(target_row)
        counts = class_counts(data)
        rows.append(
            {
                "target_id": target.get("target_id", ""),
                "row_role": str(target_row.get("row_role", "")),
                "rank": target.get("rank", ""),
                "pcx_name": target.get("pcx_name", ""),
                "frontier_id": target.get("frontier_id", ""),
                "run_start": target.get("start", ""),
                "row_start": str(target_row.get("row_start", "")),
                "rule_type": run.get("rule_type", ""),
                "opcode0_hex": run.get("opcode0_hex", ""),
                "opcode1_hex": run.get("opcode1_hex", ""),
                "control_prefix_hex": run.get("control_prefix_hex", ""),
                "fragment_hex": run.get("fragment_hex", ""),
                "segment_gap_bytes": run.get("segment_gap_bytes", "0"),
                "manifest_control_signature": run.get("manifest_control_signature", ""),
                "role_manifest_control_signature": pending["role_manifest"],
                "run_context_signature": run.get("run_context_signature", ""),
                "role_run_context_signature": pending["role_context"],
                "manifest_signature_run_rows": str(manifest_run_counts.get(run.get("manifest_control_signature", ""), 0)),
                "run_context_signature_run_rows": str(context_run_counts.get(run.get("run_context_signature", ""), 0)),
                "role_manifest_signature_rows": str(role_manifest_counts.get(pending["role_manifest"], 0)),
                "role_run_context_signature_rows": str(role_context_counts.get(pending["role_context"], 0)),
                "pre32_known_bytes": run.get("pre32_known_bytes", "0"),
                "row0_known_bytes": run.get("row0_known_bytes", "0"),
                "post32_known_bytes": run.get("post32_known_bytes", "0"),
                "row0_high_plateau_bytes": run.get("row0_high_plateau_bytes", "0"),
                "row_low_payload_bytes": str(counts.get("low_payload", 0)),
                "row_control_high_bytes": str(counts.get("control_high", 0)),
                "row_head_hex": data[:16].hex(),
            }
        )
    rows.sort(key=lambda row: (row.get("row_role", ""), int_value(row, "rank"), int_value(row, "run_start")))
    return rows


def build_summary(run_rows: list[dict[str, str]], context_rows: list[dict[str, str]], issues: list[str]) -> dict[str, str]:
    manifest_counts = signature_counts(run_rows, "manifest_control_signature")
    context_counts = signature_counts(run_rows, "run_context_signature")
    role_manifest_counts = signature_counts(context_rows, "role_manifest_control_signature")
    role_context_counts = signature_counts(context_rows, "role_run_context_signature")
    pre_known_values = [int_value(row, "pre32_known_bytes") for row in run_rows]
    post_known_values = [int_value(row, "post32_known_bytes") for row in run_rows]
    post_zero_values = [int_value(row, "post_zero_prefix_bytes") for row in run_rows]
    segment_sizes = [int_value(row, "segment_gap_bytes") for row in run_rows]
    compact_rows = sum(1 for row in context_rows if row.get("rule_type") == "compact_control_stream")
    if len(manifest_counts) < len(run_rows) and len(context_counts) == len(run_rows):
        verdict = "frontier80_context_residual_low_payload_opcode_context_manifest_ambiguous_run_context_split"
        next_probe = "derive compact-control row-state decoder from run-local high-row context"
    elif len(manifest_counts) == len(run_rows):
        verdict = "frontier80_context_residual_low_payload_opcode_context_manifest_distinct"
        next_probe = "derive compact-control selector from manifest opcode signatures"
    else:
        verdict = "frontier80_context_residual_low_payload_opcode_context_ambiguous"
        next_probe = "broaden compact-control context features around residual low-payload rows"
    return {
        "scope": "total",
        "target_runs": str(len(run_rows)),
        "target_rows": str(len(context_rows)),
        "target_bytes": str(len(context_rows) * 32),
        "compact_control_target_rows": str(compact_rows),
        "manifest_control_signatures": str(len(manifest_counts)),
        "manifest_control_signature_run_max": str(max(manifest_counts.values(), default=0)),
        "role_manifest_control_signatures": str(len(role_manifest_counts)),
        "run_context_signatures": str(len(context_counts)),
        "run_context_signature_run_max": str(max(context_counts.values(), default=0)),
        "role_run_context_signatures": str(len(role_context_counts)),
        "row0_unknown_runs": str(sum(1 for row in run_rows if int_value(row, "row0_known_bytes") == 0)),
        "row0_high_plateau_runs": str(sum(1 for row in run_rows if int_value(row, "row0_high_plateau_bytes") == 32)),
        "pre_context_known_min": str(min(pre_known_values, default=0)),
        "pre_context_known_max": str(max(pre_known_values, default=0)),
        "post_context_known_min": str(min(post_known_values, default=0)),
        "post_zero_prefix_min": str(min(post_zero_values, default=0)),
        "segment_gap_bytes_min": str(min(segment_sizes, default=0)),
        "segment_gap_bytes_max": str(max(segment_sizes, default=0)),
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
    run_rows: list[dict[str, str]],
    context_rows: list[dict[str, str]],
    title: str,
) -> str:
    summary_json = html.escape(json.dumps(summary, indent=2))
    stats = "".join(
        f"<div class=\"stat\"><div class=\"label\">{html.escape(key)}</div>"
        f"<div class=\"value\">{html.escape(summary.get(key, ''))}</div></div>"
        for key in (
            "manifest_control_signatures",
            "run_context_signatures",
            "row0_unknown_runs",
            "row0_high_plateau_runs",
            "segment_gap_bytes_max",
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
  {table_html("Run opcode/context profile", "runs.csv", run_rows, RUN_FIELDNAMES)}
  {table_html("Target row context", "context_rows.csv", context_rows, ROW_FIELDNAMES)}
  {table_html("Targets", "targets.csv", targets, TARGET_FIELDNAMES)}
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Profile opcode/control context for Frontier80 low-payload residual rows."
    )
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--runs", type=Path, default=DEFAULT_RUNS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--clean-fixtures", type=Path, default=DEFAULT_CLEAN_FIXTURES)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Low Payload Opcode Context Probe",
    )
    args = parser.parse_args()

    issues: list[str] = []
    run_csv_rows = read_csv(args.runs)
    manifest_rows = read_csv(args.manifest)
    clean_rows = read_csv(args.clean_fixtures)
    target_runs = load_target_runs(run_csv_rows, manifest_rows, clean_rows, issues)
    target_rows = low_target_rows(target_runs, issues)
    targets = [target_row_record(row) for row in target_rows]
    run_rows = build_run_rows(target_runs, manifest_rows, issues)
    context_rows = build_context_rows(target_rows, run_rows)
    summary = build_summary(run_rows, context_rows, issues)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, targets)
    write_csv(args.output / "runs.csv", RUN_FIELDNAMES, run_rows)
    write_csv(args.output / "context_rows.csv", ROW_FIELDNAMES, context_rows)
    (args.output / "issues.txt").write_text("\n".join(issues))
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, targets, run_rows, context_rows, args.title))

    print(
        "Signatures: "
        f"manifest={summary['manifest_control_signatures']}, "
        f"run_context={summary['run_context_signatures']}"
    )
    print(
        "Row0: "
        f"unknown={summary['row0_unknown_runs']}/{summary['target_runs']}, "
        f"high_plateau={summary['row0_high_plateau_runs']}/{summary['target_runs']}"
    )
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
