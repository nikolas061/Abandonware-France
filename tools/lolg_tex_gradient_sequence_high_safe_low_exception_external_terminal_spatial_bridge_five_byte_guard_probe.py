#!/usr/bin/env python3
"""Probe non-oracle guards for the frontier 80 five-byte bridge combinator."""

from __future__ import annotations

import argparse
import csv
import html
import json
from dataclasses import dataclass
from pathlib import Path

from lolg_tex_gap_opcode_probe import relative_href, write_csv
from lolg_tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_gradient_bridge_probe import (
    int_value,
    read_csv,
    row_key,
)
from lolg_tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_selector_probe import (
    span_length,
)


DEFAULT_TARGETS = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_combinator/targets.csv"
)
DEFAULT_DIAGNOSTICS = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_combinator/diagnostics.csv"
)
DEFAULT_SMALL_GAPS = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_selector/small_gaps.csv"
)
DEFAULT_MANIFEST = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_OUTPUT = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_guard"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "target_spans",
    "target_bytes",
    "diagnostic_rows",
    "diagnostic_false_rows",
    "diagnostic_false_spans",
    "guard_rows",
    "diagnostic_false_free_guard_rows",
    "compact_guard_rows",
    "best_guard_family",
    "best_guard_key",
    "best_rejected_false_rows",
    "best_same_key_false_rows",
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
    "best_family",
    "best_selector",
    "guard_family",
    "guard_key",
    "guard_verdict",
    "same_key_false_rows",
    "rejected_false_rows",
    "promotion_ready",
    "issues",
]

GUARD_FIELDNAMES = [
    "rank",
    "guard_family",
    "guard_key",
    "guard_scope",
    "target_spans",
    "target_bytes",
    "same_key_diagnostic_rows",
    "same_key_false_rows",
    "same_key_false_spans",
    "rejected_false_rows",
    "rejected_false_spans",
    "verdict",
    "sample_same_key_false",
    "sample_rejected_false",
]

DIAGNOSTIC_FIELDNAMES = [
    "rank",
    "span_key",
    "template_family",
    "exact_match",
    "guard_family",
    "guard_key",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "known_in_replay",
    "expected_hex",
    "output_hex",
    "anchor_byte",
    "anchor_rel",
    "control_ref_mod64",
    "segment_pair",
    "op_lengths",
]


@dataclass(frozen=True)
class GuardSpec:
    family: str
    fields: tuple[str, ...]
    scope: str


GUARD_SPECS = [
    GuardSpec("control_ref_mod64", ("control_ref_mod64",), "position_control"),
    GuardSpec("op_lengths", ("prev_op_length", "next_op_length"), "opcode_shape"),
    GuardSpec("anchor_rel", ("anchor_rel",), "spatial_anchor"),
    GuardSpec("anchor_byte", ("anchor_byte",), "spatial_anchor"),
    GuardSpec("segment_pair", ("segment_pair",), "compact_control"),
    GuardSpec("segment_pair_high", ("segment_pair_high",), "compact_control"),
    GuardSpec("control_tail4", ("control_tail4",), "stream_context"),
    GuardSpec("prev_tail2_next_len", ("prev_tail2", "next_op_length"), "literal_context"),
    GuardSpec(
        "compact_shape_anchor",
        ("gap_role", "span_length", "prev_op_length", "next_op_length", "anchor_rel", "segment_pair_high"),
        "compact_control",
    ),
    GuardSpec(
        "compact_pair_control",
        ("gap_role", "span_length", "control_ref_mod64", "anchor_rel", "segment_pair"),
        "compact_control",
    ),
]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


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


def hex_tail(value: str, byte_count: int) -> str:
    return value[-byte_count * 2 :] if value else "."


def segment_pair(row: dict[str, str], segment: bytes | None) -> tuple[str, str]:
    if segment is None:
        return ".", "."
    ref = int_value(row, "control_ref_offset", -1)
    if ref < 0 or ref + 3 >= len(segment):
        return ".", "."
    pair = f"{segment[ref + 2]:02x}{segment[ref + 3]:02x}"
    return pair, f"{segment[ref + 2] >> 4:x}{segment[ref + 3] >> 4:x}"


def feature_row(
    base_row: dict[str, str],
    candidate_row: dict[str, str],
    segments: dict[tuple[str, str, str], bytes],
) -> dict[str, str]:
    pair, pair_high = segment_pair(base_row, segments.get(row_key(base_row)))
    prev_op_length = base_row.get("prev_op_length", "") or "."
    next_op_length = base_row.get("next_op_length", "") or "."
    return {
        "span_key": base_row.get("span_key", ""),
        "archive": base_row.get("archive", ""),
        "archive_tag": base_row.get("archive_tag", ""),
        "pcx_name": base_row.get("pcx_name", ""),
        "frontier_id": base_row.get("frontier_id", ""),
        "expected_hex": base_row.get("expected_hex", candidate_row.get("expected_hex", "")),
        "gap_role": base_row.get("gap_role", ""),
        "span_length": str(span_length(base_row)),
        "prev_op_length": prev_op_length,
        "next_op_length": next_op_length,
        "op_lengths": f"{prev_op_length}->{next_op_length}",
        "prev_tail2": hex_tail(base_row.get("prev_expected_hex", ""), 2),
        "next_head2": base_row.get("next_expected_hex", "")[:4] if base_row.get("next_expected_hex") else ".",
        "control_ref_mod64": base_row.get("control_ref_mod64", ""),
        "control_tail4": base_row.get("control_tail4", ""),
        "anchor_byte": candidate_row.get("anchor_byte", ""),
        "anchor_rel": candidate_row.get("anchor_rel", ""),
        "delta_signature": candidate_row.get("delta_signature", ""),
        "segment_pair": pair,
        "segment_pair_high": pair_high,
    }


def guard_key(row: dict[str, str], spec: GuardSpec) -> str:
    return "|".join(f"{field}={row.get(field, '.') or '.'}" for field in spec.fields)


def build(
    target_rows_in: list[dict[str, str]],
    diagnostic_rows_in: list[dict[str, str]],
    small_gap_rows: list[dict[str, str]],
    manifest_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    segments, segment_issues = load_segments(manifest_rows)
    small_by_span = {row.get("span_key", ""): row for row in small_gap_rows}
    target_rows = [row for row in target_rows_in if row.get("verdict") == "diagnostic_false_needs_guard"]
    target_features: list[dict[str, str]] = []
    for row in target_rows:
        base = small_by_span.get(row.get("span_key", ""))
        if base:
            target_features.append(feature_row(base, row, segments))

    diagnostic_features: list[dict[str, str]] = []
    for row in diagnostic_rows_in:
        if row.get("template_family") == "target_delta_template":
            continue
        base = small_by_span.get(row.get("span_key", ""))
        if not base:
            continue
        feature = feature_row(base, row, segments)
        feature.update(
            {
                "template_family": row.get("template_family", ""),
                "exact_match": row.get("exact_match", ""),
                "known_in_replay": row.get("known_in_replay", ""),
                "output_hex": row.get("output_hex", ""),
            }
        )
        diagnostic_features.append(feature)

    guard_rows: list[dict[str, str]] = []
    target_output_rows: list[dict[str, str]] = []
    best_by_span: dict[str, dict[str, str]] = {}
    diagnostic_false = [row for row in diagnostic_features if row.get("exact_match") != "1"]
    diagnostic_false_spans = {row.get("span_key", "") for row in diagnostic_false}
    for spec in GUARD_SPECS:
        for target in target_features:
            key = guard_key(target, spec)
            same_key = [row for row in diagnostic_features if guard_key(row, spec) == key]
            same_key_false = [row for row in same_key if row.get("exact_match") != "1"]
            rejected_false = [row for row in diagnostic_false if guard_key(row, spec) != key]
            same_key_false_spans = sorted({row.get("span_key", "") for row in same_key_false})
            rejected_false_spans = sorted({row.get("span_key", "") for row in rejected_false})
            verdict = "diagnostic_false_free" if not same_key_false else "diagnostic_conflict"
            guard = {
                "rank": "",
                "guard_family": spec.family,
                "guard_key": key,
                "guard_scope": spec.scope,
                "target_spans": "1",
                "target_bytes": str(span_length(target)),
                "same_key_diagnostic_rows": str(len(same_key)),
                "same_key_false_rows": str(len(same_key_false)),
                "same_key_false_spans": str(len(same_key_false_spans)),
                "rejected_false_rows": str(len(rejected_false)),
                "rejected_false_spans": str(len(rejected_false_spans)),
                "verdict": verdict,
                "sample_same_key_false": ";".join(same_key_false_spans[:8]),
                "sample_rejected_false": ";".join(rejected_false_spans[:8]),
            }
            guard_rows.append(guard)
            current = best_by_span.get(target.get("span_key", ""))
            if current is None or (
                guard.get("verdict") == "diagnostic_false_free",
                spec.scope == "compact_control",
                int_value(guard, "rejected_false_rows"),
                len(spec.fields),
            ) > (
                current.get("verdict") == "diagnostic_false_free",
                current.get("guard_scope") == "compact_control",
                int_value(current, "rejected_false_rows"),
                current.get("_field_count", 0),
            ):
                best_by_span[target.get("span_key", "")] = {**guard, "_field_count": len(spec.fields)}

    for index, target in enumerate(target_features, start=1):
        best = best_by_span.get(target.get("span_key", ""), {})
        target_source = next((row for row in target_rows if row.get("span_key") == target.get("span_key")), {})
        target_output_rows.append(
            {
                "rank": str(index),
                "span_key": target.get("span_key", ""),
                "archive_tag": target.get("archive_tag", ""),
                "pcx_name": target.get("pcx_name", ""),
                "frontier_id": target.get("frontier_id", ""),
                "expected_hex": target.get("expected_hex", ""),
                "best_family": target_source.get("best_family", ""),
                "best_selector": target_source.get("best_selector", ""),
                "guard_family": best.get("guard_family", ""),
                "guard_key": best.get("guard_key", ""),
                "guard_verdict": best.get("verdict", ""),
                "same_key_false_rows": best.get("same_key_false_rows", "0"),
                "rejected_false_rows": best.get("rejected_false_rows", "0"),
                "promotion_ready": "0",
                "issues": "" if best else "missing_guard",
            }
        )

    guard_rows.sort(
        key=lambda row: (
            row.get("verdict") != "diagnostic_false_free",
            row.get("guard_scope") != "compact_control",
            -int_value(row, "rejected_false_rows"),
            int_value(row, "same_key_false_rows"),
            row.get("guard_family", ""),
        )
    )
    for index, row in enumerate(guard_rows, start=1):
        row["rank"] = str(index)
    if guard_rows and len(target_output_rows) == 1:
        best = guard_rows[0]
        target_output_rows[0].update(
            {
                "guard_family": best.get("guard_family", ""),
                "guard_key": best.get("guard_key", ""),
                "guard_verdict": best.get("verdict", ""),
                "same_key_false_rows": best.get("same_key_false_rows", "0"),
                "rejected_false_rows": best.get("rejected_false_rows", "0"),
            }
        )

    diagnostic_output_rows: list[dict[str, str]] = []
    for spec in GUARD_SPECS:
        for row in diagnostic_features:
            diagnostic_output_rows.append(
                {
                    "rank": "",
                    "span_key": row.get("span_key", ""),
                    "template_family": row.get("template_family", ""),
                    "exact_match": row.get("exact_match", ""),
                    "guard_family": spec.family,
                    "guard_key": guard_key(row, spec),
                    "archive_tag": row.get("archive_tag", ""),
                    "pcx_name": row.get("pcx_name", ""),
                    "frontier_id": row.get("frontier_id", ""),
                    "known_in_replay": row.get("known_in_replay", ""),
                    "expected_hex": row.get("expected_hex", ""),
                    "output_hex": row.get("output_hex", ""),
                    "anchor_byte": row.get("anchor_byte", ""),
                    "anchor_rel": row.get("anchor_rel", ""),
                    "control_ref_mod64": row.get("control_ref_mod64", ""),
                    "segment_pair": row.get("segment_pair", ""),
                    "op_lengths": row.get("op_lengths", ""),
                }
            )
    diagnostic_output_rows.sort(
        key=lambda row: (row.get("guard_family", ""), row.get("span_key", ""), row.get("template_family", ""))
    )
    for index, row in enumerate(diagnostic_output_rows, start=1):
        row["rank"] = str(index)

    false_free_guard_rows = [row for row in guard_rows if row.get("verdict") == "diagnostic_false_free"]
    compact_guard_rows = [row for row in false_free_guard_rows if row.get("guard_scope") == "compact_control"]
    best_guard = guard_rows[0] if guard_rows else {}
    target_bytes = sum(span_length(row) for row in target_features)
    summary = {
        "scope": "total",
        "candidate_mode": "external_terminal_spatial_bridge_five_byte_guard_probe",
        "target_spans": str(len(target_features)),
        "target_bytes": str(target_bytes),
        "diagnostic_rows": str(len(diagnostic_features)),
        "diagnostic_false_rows": str(len(diagnostic_false)),
        "diagnostic_false_spans": str(len(diagnostic_false_spans)),
        "guard_rows": str(len(guard_rows)),
        "diagnostic_false_free_guard_rows": str(len(false_free_guard_rows)),
        "compact_guard_rows": str(len(compact_guard_rows)),
        "best_guard_family": best_guard.get("guard_family", ""),
        "best_guard_key": best_guard.get("guard_key", ""),
        "best_rejected_false_rows": best_guard.get("rejected_false_rows", "0"),
        "best_same_key_false_rows": best_guard.get("same_key_false_rows", "0"),
        "next_probe": (
            "find known/reference support for frontier 80 five-byte guard"
            if false_free_guard_rows
            else "expand non-oracle guard features for frontier 80 five-byte combinator"
        ),
        "promotion_candidate_bytes": "0",
        "promotion_ready_bytes": "0",
        "issue_rows": str(len(segment_issues)),
    }
    return summary, target_output_rows, guard_rows, diagnostic_output_rows


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 240) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    target_rows: list[dict[str, str]],
    guard_rows: list[dict[str, str]],
    diagnostic_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "targets": target_rows,
        "guards": guard_rows,
        "diagnostics": diagnostic_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("targets.csv", output_dir / "targets.csv"),
            ("guards.csv", output_dir / "guards.csv"),
            ("diagnostics.csv", output_dir / "diagnostics.csv"),
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
    <div class="muted">Ranks non-oracle guard features that keep the frontier 80 five-byte bridge and reject diagnostic false spans.</div>
  </header>
  <section class="stats">
    <div class="stat"><div class="muted">Target bytes</div><div class="value">{summary['target_bytes']}</div></div>
    <div class="stat"><div class="muted">False-free guards</div><div class="value">{summary['diagnostic_false_free_guard_rows']}</div></div>
    <div class="stat"><div class="muted">Compact guards</div><div class="value">{summary['compact_guard_rows']}</div></div>
    <div class="stat"><div class="muted">Diagnostic false</div><div class="value warn">{summary['diagnostic_false_rows']}</div></div>
    <div class="stat"><div class="muted">Promotion-ready</div><div class="value warn">{summary['promotion_ready_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2>{links}</section>
  <section class="panel">
    <h2>Next</h2>
    <p><code>{html.escape(summary['next_probe'])}</code></p>
    <p class="muted">Best guard: <code>{html.escape(summary['best_guard_family'])}</code> / <code>{html.escape(summary['best_guard_key'])}</code>.</p>
  </section>
  <section class="panel"><h2>Targets</h2>{render_table(target_rows, TARGET_FIELDNAMES)}</section>
  <section class="panel"><h2>Guards</h2>{render_table(guard_rows, GUARD_FIELDNAMES)}</section>
  <section class="panel"><h2>Diagnostics</h2>{render_table(diagnostic_rows, DIAGNOSTIC_FIELDNAMES)}</section>
  <script type="application/json" id="external-terminal-spatial-bridge-five-byte-guard-data">{html.escape(data_json)}</script>
</main>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe guards for the frontier 80 five-byte bridge combinator.")
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("--diagnostics", type=Path, default=DEFAULT_DIAGNOSTICS)
    parser.add_argument("--small-gaps", type=Path, default=DEFAULT_SMALL_GAPS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex External Terminal Spatial Bridge Five-Byte Guard Probe",
    )
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    summary, target_rows, guard_rows, diagnostic_rows = build(
        read_csv(args.targets),
        read_csv(args.diagnostics),
        read_csv(args.small_gaps),
        read_rows(args.manifest),
    )
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, target_rows)
    write_csv(args.output / "guards.csv", GUARD_FIELDNAMES, guard_rows)
    write_csv(args.output / "diagnostics.csv", DIAGNOSTIC_FIELDNAMES, diagnostic_rows)
    (args.output / "index.html").write_text(
        build_html(summary, target_rows, guard_rows, diagnostic_rows, args.output, args.title),
        encoding="utf-8",
    )
    print(
        "External terminal spatial bridge five-byte guard probe: "
        f"false_free_guards={summary['diagnostic_false_free_guard_rows']} "
        f"compact_guards={summary['compact_guard_rows']} "
        f"best={summary['best_guard_family']} "
        f"promotion_ready={summary['promotion_ready_bytes']} "
        f"issues={summary['issue_rows']}"
    )
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
