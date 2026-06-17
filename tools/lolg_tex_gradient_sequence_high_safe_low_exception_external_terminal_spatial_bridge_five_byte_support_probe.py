#!/usr/bin/env python3
"""Probe corpus support for the frontier 80 five-byte bridge guard."""

from __future__ import annotations

import argparse
import csv
import html
import json
from pathlib import Path

from lolg_tex_gap_opcode_probe import relative_href, write_csv
from lolg_tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_gradient_bridge_probe import (
    DEFAULT_MAX_DELTA,
    DEFAULT_MAX_DISTANCE,
    anchor_signatures,
    int_value,
    load_buffers,
    read_csv,
    row_key,
)


DEFAULT_TARGETS = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_guard/targets.csv"
)
DEFAULT_OPERATIONS = Path("output/tex_gap_segmentation_control_correlation_probe/operations.csv")
DEFAULT_FIXTURES = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_cover_second_promoted_replay/fixtures.csv"
)
DEFAULT_MANIFEST = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_OUTPUT = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_support"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "target_spans",
    "target_bytes",
    "operation_rows",
    "length5_operation_rows",
    "length5_gap_rows",
    "anchor_candidate_rows",
    "guard_candidate_rows",
    "guard_candidate_spans",
    "same_guard_non_target_rows",
    "same_guard_non_target_spans",
    "guard_reference_exact_rows",
    "guard_reference_false_rows",
    "guard_known_full_rows",
    "guard_known_full_exact_rows",
    "target_only_reference_rows",
    "target_only_reference_bytes",
    "best_target_span",
    "best_guard_key",
    "next_probe",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

TARGET_FIELDNAMES = [
    "rank",
    "span_key",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "expected_hex",
    "guard_family",
    "guard_key",
    "support_rows",
    "support_known_full_rows",
    "support_non_target_rows",
    "support_reference_exact_rows",
    "support_reference_false_rows",
    "support_verdict",
    "promotion_ready",
    "issues",
]

SUPPORT_FIELDNAMES = [
    "rank",
    "span_key",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "op_index",
    "op_kind",
    "gap_role",
    "span_length",
    "expected_start",
    "expected_end",
    "expected_hex",
    "formula_output_hex",
    "formula_exact",
    "known_full",
    "control_ref_mod64",
    "segment_pair",
    "anchor_rel",
    "anchor_byte",
    "delta_signature",
    "matches_target_guard",
    "is_target",
]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def parse_guard_key(value: str) -> dict[str, str]:
    parts: dict[str, str] = {}
    for item in value.split("|"):
        if "=" not in item:
            continue
        key, item_value = item.split("=", 1)
        parts[key] = item_value
    return parts


def load_segments(manifest_rows: list[dict[str, str]]) -> tuple[dict[tuple[str, str, str], bytes], list[str]]:
    segments: dict[tuple[str, str, str], bytes] = {}
    issues: list[str] = []
    for row in manifest_rows:
        path = row.get("segment_gap_path", "")
        if not path:
            issues.append(f"{'|'.join(row_key(row))}:missing_segment_path")
            continue
        try:
            segments[row_key(row)] = Path(path).read_bytes()
        except OSError as exc:
            issues.append(f"{'|'.join(row_key(row))}:read_segment_failed:{exc}")
    return segments, issues


def group_operations(rows: list[dict[str, str]]) -> dict[tuple[str, str, str], list[dict[str, str]]]:
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = {}
    for row in rows:
        grouped.setdefault(row_key(row), []).append(row)
    for group in grouped.values():
        group.sort(key=lambda row: int_value(row, "op_index"))
    return grouped


def gap_role(previous: dict[str, str], following: dict[str, str]) -> str:
    if not previous and following.get("op_kind") == "literal":
        return "prefix_before_literal"
    if previous.get("op_kind") == "literal" and following.get("op_kind") == "zero":
        return "between_literal_zero"
    if previous.get("op_kind") == "zero" and following.get("op_kind") == "literal":
        return "between_zero_literal"
    return f"{previous.get('op_kind', 'start')}->{following.get('op_kind', 'end')}"


def known_full(row: dict[str, str], buffers: dict[tuple[str, str, str], tuple[bytes, bytes]]) -> bool:
    buffer = buffers.get(row_key(row))
    if buffer is None:
        return False
    _, mask = buffer
    start = int_value(row, "expected_start")
    end = int_value(row, "expected_end")
    return 0 <= start <= end <= len(mask) and all(mask[start:end])


def segment_pair(row: dict[str, str], segment: bytes | None) -> str:
    if segment is None:
        return "."
    ref = int_value(row, "control_ref_offset", -1)
    if ref < 0 or ref + 3 >= len(segment):
        return "."
    return f"{segment[ref + 2]:02x}{segment[ref + 3]:02x}"


def formula_output(row: dict[str, str], segment: bytes, anchor_hex: str) -> str:
    ref = int_value(row, "control_ref_offset", -1)
    if ref < 0 or ref + 3 >= len(segment):
        return ""
    try:
        anchor = int(anchor_hex, 16)
    except ValueError:
        return ""
    return bytes([(anchor - 1) & 0xFF, segment[ref + 3], (anchor - 1) & 0xFF, segment[ref + 2], anchor]).hex()


def support_rows(
    operations: list[dict[str, str]],
    segments: dict[tuple[str, str, str], bytes],
    buffers: dict[tuple[str, str, str], tuple[bytes, bytes]],
    target_spans: set[str],
    guard_parts: dict[str, str],
    *,
    max_distance: int,
    max_delta: int,
) -> list[dict[str, str]]:
    grouped = group_operations(operations)
    rows: list[dict[str, str]] = []
    for key, group in grouped.items():
        buffer = buffers.get(key)
        segment = segments.get(key)
        if buffer is None or segment is None:
            continue
        decoded, mask = buffer
        for index, operation in enumerate(group):
            if int_value(operation, "length") != 5:
                continue
            previous = group[index - 1] if index > 0 else {}
            following = group[index + 1] if index + 1 < len(group) else {}
            role = gap_role(previous, following)
            pair = segment_pair(operation, segment)
            control_mod = str(int_value(operation, "control_ref_offset") % 64)
            span_key = f"{operation.get('frontier_id', '')}:{operation.get('expected_start', '')}-{operation.get('expected_end', '')}"
            operation_for_signature = {**operation, "span_key": span_key}
            for signature in anchor_signatures(
                operation_for_signature,
                decoded,
                mask,
                max_distance=max_distance,
                max_delta=max_delta,
            ):
                output = formula_output(operation, segment, signature.get("anchor_byte", ""))
                matches_guard = (
                    role == guard_parts.get("gap_role")
                    and str(int_value(operation, "length")) == guard_parts.get("span_length")
                    and control_mod == guard_parts.get("control_ref_mod64")
                    and signature.get("anchor_rel") == guard_parts.get("anchor_rel")
                    and pair == guard_parts.get("segment_pair")
                )
                rows.append(
                    {
                        "rank": "",
                        "span_key": span_key,
                        "archive_tag": operation.get("archive_tag", ""),
                        "pcx_name": operation.get("pcx_name", ""),
                        "frontier_id": operation.get("frontier_id", ""),
                        "op_index": operation.get("op_index", ""),
                        "op_kind": operation.get("op_kind", ""),
                        "gap_role": role,
                        "span_length": operation.get("length", ""),
                        "expected_start": operation.get("expected_start", ""),
                        "expected_end": operation.get("expected_end", ""),
                        "expected_hex": operation.get("expected_hex", ""),
                        "formula_output_hex": output,
                        "formula_exact": "1" if output and output == operation.get("expected_hex", "") else "0",
                        "known_full": "1" if known_full(operation, buffers) else "0",
                        "control_ref_mod64": control_mod,
                        "segment_pair": pair,
                        "anchor_rel": signature.get("anchor_rel", ""),
                        "anchor_byte": signature.get("anchor_byte", ""),
                        "delta_signature": signature.get("delta_signature", ""),
                        "matches_target_guard": "1" if matches_guard else "0",
                        "is_target": "1" if span_key in target_spans else "0",
                    }
                )
    rows.sort(
        key=lambda row: (
            row.get("matches_target_guard") != "1",
            row.get("is_target") != "1",
            row.get("span_key", ""),
            row.get("anchor_rel", ""),
        )
    )
    for index, row in enumerate(rows, start=1):
        row["rank"] = str(index)
    return rows


def build(
    target_rows_in: list[dict[str, str]],
    operation_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    manifest_rows: list[dict[str, str]],
    *,
    max_distance: int,
    max_delta: int,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    buffers, buffer_issues = load_buffers(fixture_rows)
    segments, segment_issues = load_segments(manifest_rows)
    target_rows = [row for row in target_rows_in if row.get("guard_verdict") == "diagnostic_false_free"]
    target_spans = {row.get("span_key", "") for row in target_rows}
    guard_parts = parse_guard_key(target_rows[0].get("guard_key", "")) if target_rows else {}
    rows = support_rows(
        operation_rows,
        segments,
        buffers,
        target_spans,
        guard_parts,
        max_distance=max_distance,
        max_delta=max_delta,
    )
    guard_rows = [row for row in rows if row.get("matches_target_guard") == "1"]
    guard_spans = {row.get("span_key", "") for row in guard_rows}
    guard_exact = [row for row in guard_rows if row.get("formula_exact") == "1"]
    guard_false = [row for row in guard_rows if row.get("formula_exact") != "1"]
    guard_known = [row for row in guard_rows if row.get("known_full") == "1"]
    target_only = [row for row in guard_rows if row.get("is_target") == "1" and row.get("formula_exact") == "1"]
    non_target = [row for row in guard_rows if row.get("is_target") != "1"]
    length5_operations = [row for row in operation_rows if int_value(row, "length") == 5]
    length5_gaps = [row for row in length5_operations if row.get("op_kind") == "gap"]
    target_output_rows: list[dict[str, str]] = []
    for index, target in enumerate(target_rows, start=1):
        support_for_target = [row for row in guard_rows if row.get("span_key") == target.get("span_key")]
        known_for_target = [row for row in support_for_target if row.get("known_full") == "1"]
        false_for_target = [row for row in support_for_target if row.get("formula_exact") != "1"]
        verdict = "target_only_reference_support"
        if known_for_target and not false_for_target:
            verdict = "known_guard_support"
        elif false_for_target:
            verdict = "guard_false"
        target_output_rows.append(
            {
                "rank": str(index),
                "span_key": target.get("span_key", ""),
                "archive_tag": target.get("archive_tag", ""),
                "pcx_name": target.get("pcx_name", ""),
                "frontier_id": target.get("frontier_id", ""),
                "expected_hex": target.get("expected_hex", ""),
                "guard_family": target.get("guard_family", ""),
                "guard_key": target.get("guard_key", ""),
                "support_rows": str(len(support_for_target)),
                "support_known_full_rows": str(len(known_for_target)),
                "support_non_target_rows": str(len(non_target)),
                "support_reference_exact_rows": str(sum(1 for row in support_for_target if row.get("formula_exact") == "1")),
                "support_reference_false_rows": str(len(false_for_target)),
                "support_verdict": verdict,
                "promotion_ready": "0",
                "issues": "",
            }
        )
    target_bytes = sum(5 for _ in target_rows)
    summary = {
        "scope": "total",
        "candidate_mode": "external_terminal_spatial_bridge_five_byte_support_probe",
        "target_spans": str(len(target_rows)),
        "target_bytes": str(target_bytes),
        "operation_rows": str(len(operation_rows)),
        "length5_operation_rows": str(len(length5_operations)),
        "length5_gap_rows": str(len(length5_gaps)),
        "anchor_candidate_rows": str(len(rows)),
        "guard_candidate_rows": str(len(guard_rows)),
        "guard_candidate_spans": str(len(guard_spans)),
        "same_guard_non_target_rows": str(len(non_target)),
        "same_guard_non_target_spans": str(len({row.get("span_key", "") for row in non_target})),
        "guard_reference_exact_rows": str(len(guard_exact)),
        "guard_reference_false_rows": str(len(guard_false)),
        "guard_known_full_rows": str(len(guard_known)),
        "guard_known_full_exact_rows": str(sum(1 for row in guard_known if row.get("formula_exact") == "1")),
        "target_only_reference_rows": str(len(target_only)),
        "target_only_reference_bytes": str(5 * len({row.get("span_key", "") for row in target_only})),
        "best_target_span": target_rows[0].get("span_key", "") if target_rows else "",
        "best_guard_key": target_rows[0].get("guard_key", "") if target_rows else "",
        "next_probe": (
            "promote known-supported frontier 80 five-byte guard"
            if guard_known and not guard_false
            else (
                "review target-only reference support for frontier 80 five-byte guard"
                if target_only and not non_target and not guard_false
                else "expand five-byte guard support search outside current operation corpus"
            )
        ),
        "promotion_candidate_bytes": "0",
        "promotion_ready_bytes": "0",
        "issue_rows": str(len(buffer_issues) + len(segment_issues)),
    }
    return summary, target_output_rows, rows


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 260) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    target_rows: list[dict[str, str]],
    support_rows_out: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "targets": target_rows, "support": support_rows_out}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("targets.csv", output_dir / "targets.csv"),
            ("support.csv", output_dir / "support.csv"),
        )
    )
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root {{
  color-scheme: dark;
  --bg: #101417;
  --panel: #171f22;
  --line: #31424a;
  --text: #edf5f4;
  --muted: #9dafb5;
  --accent: #77d3b1;
  --warn: #f0b36c;
}}
body {{ margin: 0; background: var(--bg); color: var(--text); font: 14px/1.45 system-ui, sans-serif; }}
main {{ width: min(1680px, calc(100vw - 28px)); margin: 0 auto; padding: 22px 0 32px; display: grid; gap: 16px; }}
h1 {{ margin: 0; font-size: 22px; }}
h2 {{ margin: 0 0 10px; font-size: 16px; }}
.muted {{ color: var(--muted); }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 10px; }}
.stat, .panel {{ border: 1px solid var(--line); border-radius: 8px; background: var(--panel); padding: 10px; }}
.value {{ font-size: 22px; font-weight: 760; color: var(--accent); }}
.warn {{ color: var(--warn); }}
.panel {{ overflow-x: auto; }}
table {{ width: 100%; min-width: 1420px; border-collapse: collapse; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
code {{ color: var(--accent); }}
</style>
</head>
<body>
<main>
  <header>
    <h1>{html.escape(title)}</h1>
    <div class="muted">Searches the full operation corpus for known or reference support matching the frontier 80 five-byte guard.</div>
  </header>
  <section class="stats">
    <div class="stat"><div class="muted">Guard candidates</div><div class="value">{summary['guard_candidate_rows']}</div></div>
    <div class="stat"><div class="muted">Known support</div><div class="value warn">{summary['guard_known_full_rows']}</div></div>
    <div class="stat"><div class="muted">Non-target support</div><div class="value warn">{summary['same_guard_non_target_rows']}</div></div>
    <div class="stat"><div class="muted">Reference exact</div><div class="value">{summary['guard_reference_exact_rows']}</div></div>
    <div class="stat"><div class="muted">Promotion-ready</div><div class="value warn">{summary['promotion_ready_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2>{links}</section>
  <section class="panel">
    <h2>Next</h2>
    <p><code>{html.escape(summary['next_probe'])}</code></p>
    <p class="muted">Guard: <code>{html.escape(summary['best_guard_key'])}</code>.</p>
  </section>
  <section class="panel"><h2>Targets</h2>{render_table(target_rows, TARGET_FIELDNAMES)}</section>
  <section class="panel"><h2>Support</h2>{render_table(support_rows_out, SUPPORT_FIELDNAMES)}</section>
  <script type="application/json" id="external-terminal-spatial-bridge-five-byte-support-data">{html.escape(data_json)}</script>
</main>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe support for the frontier 80 five-byte bridge guard.")
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("--operations", type=Path, default=DEFAULT_OPERATIONS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--max-distance", type=int, default=DEFAULT_MAX_DISTANCE)
    parser.add_argument("--max-delta", type=int, default=DEFAULT_MAX_DELTA)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex External Terminal Spatial Bridge Five-Byte Support Probe",
    )
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    summary, target_rows, support_rows_out = build(
        read_csv(args.targets),
        read_rows(args.operations),
        read_rows(args.fixtures),
        read_rows(args.manifest),
        max_distance=args.max_distance,
        max_delta=args.max_delta,
    )
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, target_rows)
    write_csv(args.output / "support.csv", SUPPORT_FIELDNAMES, support_rows_out)
    (args.output / "index.html").write_text(
        build_html(summary, target_rows, support_rows_out, args.output, args.title),
        encoding="utf-8",
    )
    print(
        "External terminal spatial bridge five-byte support probe: "
        f"guard_candidates={summary['guard_candidate_rows']} "
        f"known={summary['guard_known_full_rows']} "
        f"non_target={summary['same_guard_non_target_rows']} "
        f"promotion_ready={summary['promotion_ready_bytes']} "
        f"issues={summary['issue_rows']}"
    )
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
