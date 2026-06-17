#!/usr/bin/env python3
"""Probe five-byte combinators for frontier 80 spatial bridge output."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import defaultdict
from dataclasses import dataclass
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
from lolg_tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_selector_probe import (
    bridge_output_hex,
    span_end,
    span_length,
    span_start,
)


DEFAULT_TARGETS = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_delta_producer/targets.csv"
)
DEFAULT_SMALL_GAPS = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_selector/small_gaps.csv"
)
DEFAULT_FIXTURES = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_cover_second_promoted_replay/fixtures.csv"
)
DEFAULT_MANIFEST = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_OUTPUT = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_combinator"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "target_spans",
    "target_bytes",
    "known_reference_rows",
    "known_reference_len5_rows",
    "diagnostic_len5_rows",
    "target_template_rows",
    "compact_exact_spans",
    "compact_exact_bytes",
    "target_only_combinator_spans",
    "target_only_combinator_bytes",
    "known_eval_rows",
    "known_exact_rows",
    "known_false_rows",
    "diagnostic_eval_rows",
    "diagnostic_exact_rows",
    "diagnostic_false_rows",
    "diagnostic_false_spans",
    "top_diagnostic_false_span",
    "best_target_span",
    "best_template",
    "best_verdict",
    "next_probe",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

TARGET_FIELDNAMES = [
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "span_key",
    "span_start",
    "span_end",
    "span_length",
    "expected_hex",
    "anchor_side",
    "anchor_rel",
    "anchor_byte",
    "delta_signature",
    "best_family",
    "best_selector",
    "best_output_hex",
    "best_exact_bytes",
    "known_eval_rows",
    "known_false_rows",
    "diagnostic_eval_rows",
    "diagnostic_false_rows",
    "diagnostic_false_spans",
    "verdict",
    "promotion_ready",
    "issues",
]

TEMPLATE_FIELDNAMES = [
    "rank",
    "target_span",
    "family",
    "selector",
    "guard",
    "components",
    "output_hex",
    "expected_hex",
    "exact_bytes",
    "known_eval_rows",
    "known_exact_rows",
    "known_false_rows",
    "known_false_spans",
    "diagnostic_eval_rows",
    "diagnostic_exact_rows",
    "diagnostic_false_rows",
    "diagnostic_false_spans",
    "sample_diagnostic_false",
    "verdict",
]

DIAGNOSTIC_FIELDNAMES = [
    "rank",
    "template_family",
    "template_selector",
    "span_key",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "known_in_replay",
    "span_start",
    "span_end",
    "expected_hex",
    "output_hex",
    "exact_match",
    "anchor_byte",
    "anchor_rel",
    "delta_signature",
    "control_ref_offset",
    "control_ref_mod64",
]


@dataclass(frozen=True)
class FormulaSpec:
    family: str
    selector: str
    guard: str


FORMULAS = [
    FormulaSpec(
        "anchor_segment_pair",
        "anchor-1,seg_ref+3,anchor-1,seg_ref+2,anchor",
        "compact_control",
    ),
    FormulaSpec(
        "segment_high_low_anchor",
        "seg_ref+3+1,seg_ref+3,seg_ref+3+1,seg_ref+2,anchor",
        "compact_control",
    ),
    FormulaSpec(
        "segment_low_lift_anchor",
        "seg_ref+2+2,seg_ref+3,seg_ref+2+2,seg_ref+2,anchor",
        "compact_control",
    ),
    FormulaSpec(
        "target_delta_template",
        "anchor+target_delta_signature",
        "target_signature_only",
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


def clamp_byte(value: int) -> int:
    return value & 0xFF


def formula_output(row: dict[str, str], candidate: dict[str, str], segment: bytes, formula: FormulaSpec) -> bytes | None:
    length = span_length(row)
    if length != 5:
        return None
    try:
        anchor = int(candidate.get("anchor_byte", ""), 16)
    except ValueError:
        return None
    if formula.family == "target_delta_template":
        output = bridge_output_hex(candidate.get("anchor_byte", ""), candidate.get("delta_signature", ""))
        return bytes.fromhex(output) if output else None
    ref = int_value(row, "control_ref_offset", -1)
    if ref < 0 or ref + 3 >= len(segment):
        return None
    low = segment[ref + 2]
    high = segment[ref + 3]
    if formula.family == "anchor_segment_pair":
        return bytes([clamp_byte(anchor - 1), high, clamp_byte(anchor - 1), low, anchor])
    if formula.family == "segment_high_low_anchor":
        return bytes([clamp_byte(high + 1), high, clamp_byte(high + 1), low, anchor])
    if formula.family == "segment_low_lift_anchor":
        return bytes([clamp_byte(low + 2), high, clamp_byte(low + 2), low, anchor])
    raise ValueError(f"unknown formula family: {formula.family}")


def components(row: dict[str, str], candidate: dict[str, str], segment: bytes, formula: FormulaSpec) -> str:
    ref = int_value(row, "control_ref_offset", -1)
    anchor = candidate.get("anchor_byte", "")
    if formula.family == "target_delta_template":
        return f"anchor={anchor};delta={candidate.get('delta_signature', '')}"
    if ref < 0 or ref + 3 >= len(segment):
        return f"anchor={anchor};seg_ref+2=.;seg_ref+3=."
    return f"anchor={anchor};seg_ref+2={segment[ref + 2]:02x};seg_ref+3={segment[ref + 3]:02x}"


def candidate_from_target(row: dict[str, str]) -> dict[str, str]:
    return {
        "span_key": row.get("span_key", ""),
        "anchor_side": row.get("anchor_side", ""),
        "anchor_rel": row.get("anchor_rel", ""),
        "anchor_byte": row.get("anchor_byte", ""),
        "delta_signature": row.get("delta_signature", ""),
    }


def candidate_from_signature(row: dict[str, str], signature: dict[str, str]) -> dict[str, str]:
    return {
        "span_key": row.get("span_key", ""),
        "anchor_side": signature.get("anchor_side", ""),
        "anchor_rel": signature.get("anchor_rel", ""),
        "anchor_byte": signature.get("anchor_byte", ""),
        "delta_signature": signature.get("delta_signature", ""),
    }


def evaluate_formula(
    formula: FormulaSpec,
    rows: list[dict[str, str]],
    buffers: dict[tuple[str, str, str], tuple[bytes, bytes]],
    segments: dict[tuple[str, str, str], bytes],
    *,
    max_distance: int,
    max_delta: int,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    known_rows: list[dict[str, str]] = []
    diagnostic_rows: list[dict[str, str]] = []
    for row in rows:
        if span_length(row) != 5:
            continue
        buffer = buffers.get(row_key(row))
        segment = segments.get(row_key(row))
        if buffer is None or segment is None:
            continue
        decoded, known_mask = buffer
        for signature in anchor_signatures(row, decoded, known_mask, max_distance=max_distance, max_delta=max_delta):
            candidate = candidate_from_signature(row, signature)
            output = formula_output(row, candidate, segment, formula)
            if output is None:
                continue
            expected = bytes.fromhex(row.get("expected_hex", ""))
            result = {
                "rank": "",
                "template_family": formula.family,
                "template_selector": formula.selector,
                "span_key": row.get("span_key", ""),
                "archive_tag": row.get("archive_tag", ""),
                "pcx_name": row.get("pcx_name", ""),
                "frontier_id": row.get("frontier_id", ""),
                "known_in_replay": row.get("known_in_replay", ""),
                "span_start": str(span_start(row)),
                "span_end": str(span_end(row)),
                "expected_hex": expected.hex(),
                "output_hex": output.hex(),
                "exact_match": "1" if output == expected else "0",
                "anchor_byte": candidate.get("anchor_byte", ""),
                "anchor_rel": candidate.get("anchor_rel", ""),
                "delta_signature": candidate.get("delta_signature", ""),
                "control_ref_offset": row.get("control_ref_offset", ""),
                "control_ref_mod64": row.get("control_ref_mod64", ""),
            }
            diagnostic_rows.append(result)
            if row.get("known_in_replay") == "1":
                known_rows.append(result)
    return known_rows, diagnostic_rows


def build(
    delta_target_rows: list[dict[str, str]],
    small_gap_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    manifest_rows: list[dict[str, str]],
    *,
    max_distance: int,
    max_delta: int,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    buffers, buffer_issues = load_buffers(fixture_rows)
    segments, segment_issues = load_segments(manifest_rows)
    small_by_span = {row.get("span_key", ""): row for row in small_gap_rows}
    target_delta_rows = [
        row
        for row in delta_target_rows
        if int_value(row, "span_length") == 5 and row.get("verdict") == "target_only_delta_template"
    ]
    target_rows = [small_by_span[row.get("span_key", "")] for row in target_delta_rows if row.get("span_key", "") in small_by_span]
    target_candidate_by_span = {row.get("span_key", ""): candidate_from_target(row) for row in target_delta_rows}

    template_rows: list[dict[str, str]] = []
    diagnostics: list[dict[str, str]] = []
    diagnostics_by_formula: dict[str, list[dict[str, str]]] = {}
    known_by_formula: dict[str, list[dict[str, str]]] = {}
    for formula in FORMULAS:
        known_eval, diagnostic_eval = evaluate_formula(
            formula,
            small_gap_rows,
            buffers,
            segments,
            max_distance=max_distance,
            max_delta=max_delta,
        )
        diagnostics_by_formula[formula.family] = diagnostic_eval
        known_by_formula[formula.family] = known_eval
        diagnostics.extend(diagnostic_eval)

    target_output_rows: list[dict[str, str]] = []
    target_issues: list[str] = []
    for index, row in enumerate(target_rows, start=1):
        segment = segments.get(row_key(row))
        candidate = target_candidate_by_span.get(row.get("span_key", ""))
        if segment is None or candidate is None:
            target_issues.append(f"{row.get('span_key', '')}:missing_segment_or_candidate")
            continue
        expected = bytes.fromhex(row.get("expected_hex", ""))
        local_templates: list[dict[str, str]] = []
        for formula in FORMULAS:
            output = formula_output(row, candidate, segment, formula)
            if output is None:
                continue
            known_eval = known_by_formula[formula.family]
            diagnostic_eval = [
                item for item in diagnostics_by_formula[formula.family] if item.get("span_key") != row.get("span_key")
            ]
            known_false = [item for item in known_eval if item.get("exact_match") != "1"]
            known_exact = [item for item in known_eval if item.get("exact_match") == "1"]
            diagnostic_false = [item for item in diagnostic_eval if item.get("exact_match") != "1"]
            diagnostic_exact = [item for item in diagnostic_eval if item.get("exact_match") == "1"]
            exact_bytes = len(expected) if output == expected else 0
            if formula.guard == "target_signature_only":
                verdict = "target_only_delta_template"
            elif exact_bytes == 0:
                verdict = "target_miss"
            elif known_false:
                verdict = "rejected_known_false"
            elif known_exact:
                verdict = "guarded_exact"
            elif diagnostic_false:
                verdict = "diagnostic_false_needs_guard"
            else:
                verdict = "target_only_no_reference"
            template = {
                "rank": "",
                "target_span": row.get("span_key", ""),
                "family": formula.family,
                "selector": formula.selector,
                "guard": formula.guard,
                "components": components(row, candidate, segment, formula),
                "output_hex": output.hex(),
                "expected_hex": expected.hex(),
                "exact_bytes": str(exact_bytes),
                "known_eval_rows": str(len(known_eval)),
                "known_exact_rows": str(len(known_exact)),
                "known_false_rows": str(len(known_false)),
                "known_false_spans": str(len({item.get("span_key", "") for item in known_false})),
                "diagnostic_eval_rows": str(len(diagnostic_eval)),
                "diagnostic_exact_rows": str(len(diagnostic_exact)),
                "diagnostic_false_rows": str(len(diagnostic_false)),
                "diagnostic_false_spans": str(len({item.get("span_key", "") for item in diagnostic_false})),
                "sample_diagnostic_false": ";".join(sorted({item.get("span_key", "") for item in diagnostic_false})[:8]),
                "verdict": verdict,
            }
            template_rows.append(template)
            local_templates.append(template)
        best = max(
            local_templates,
            key=lambda item: (
                item.get("verdict") == "guarded_exact",
                item.get("verdict") == "target_only_no_reference",
                item.get("verdict") == "diagnostic_false_needs_guard",
                item.get("guard") == "compact_control",
                int_value(item, "exact_bytes"),
                -int_value(item, "diagnostic_false_spans"),
            ),
            default={},
        )
        issues = ""
        if best.get("verdict") == "diagnostic_false_needs_guard":
            issues = "diagnostic_false_needs_guard"
        elif best.get("verdict") == "target_only_delta_template":
            issues = "target_signature_only"
        target_output_rows.append(
            {
                "rank": str(index),
                "archive": row.get("archive", ""),
                "archive_tag": row.get("archive_tag", ""),
                "pcx_name": row.get("pcx_name", ""),
                "frontier_id": row.get("frontier_id", ""),
                "span_key": row.get("span_key", ""),
                "span_start": str(span_start(row)),
                "span_end": str(span_end(row)),
                "span_length": str(span_length(row)),
                "expected_hex": row.get("expected_hex", ""),
                "anchor_side": candidate.get("anchor_side", ""),
                "anchor_rel": candidate.get("anchor_rel", ""),
                "anchor_byte": candidate.get("anchor_byte", ""),
                "delta_signature": candidate.get("delta_signature", ""),
                "best_family": best.get("family", ""),
                "best_selector": best.get("selector", ""),
                "best_output_hex": best.get("output_hex", ""),
                "best_exact_bytes": best.get("exact_bytes", "0"),
                "known_eval_rows": best.get("known_eval_rows", "0"),
                "known_false_rows": best.get("known_false_rows", "0"),
                "diagnostic_eval_rows": best.get("diagnostic_eval_rows", "0"),
                "diagnostic_false_rows": best.get("diagnostic_false_rows", "0"),
                "diagnostic_false_spans": best.get("diagnostic_false_spans", "0"),
                "verdict": best.get("verdict", "missing_template"),
                "promotion_ready": "1" if best.get("verdict") == "guarded_exact" else "0",
                "issues": issues,
            }
        )

    template_rows.sort(
        key=lambda row: (
            row.get("target_span", ""),
            row.get("verdict") != "guarded_exact",
            row.get("verdict") != "target_only_no_reference",
            row.get("verdict") != "diagnostic_false_needs_guard",
            -int_value(row, "exact_bytes"),
            int_value(row, "diagnostic_false_spans"),
            row.get("family", ""),
        )
    )
    for index, row in enumerate(template_rows, start=1):
        row["rank"] = str(index)
    diagnostics.sort(
        key=lambda row: (
            row.get("template_family", ""),
            row.get("span_key", ""),
            row.get("exact_match", ""),
            row.get("anchor_rel", ""),
        )
    )
    for index, row in enumerate(diagnostics, start=1):
        row["rank"] = str(index)

    compact_exact_spans = {
        row.get("target_span", "")
        for row in template_rows
        if row.get("guard") == "compact_control" and int_value(row, "exact_bytes") > 0
    }
    target_only_combinator_spans = {
        row.get("target_span", "")
        for row in template_rows
        if row.get("guard") == "compact_control" and row.get("verdict") in {"target_only_no_reference", "diagnostic_false_needs_guard"}
    }
    best_target = max(
        target_output_rows,
        key=lambda row: (
            row.get("promotion_ready") == "1",
            row.get("verdict") == "target_only_no_reference",
            row.get("verdict") == "diagnostic_false_needs_guard",
            int_value(row, "best_exact_bytes"),
        ),
        default={},
    )
    diagnostic_false = [row for row in diagnostics if row.get("exact_match") != "1"]
    diagnostic_false_spans = sorted({row.get("span_key", "") for row in diagnostic_false})
    target_bytes = sum(span_length(row) for row in target_rows)
    promotion_ready_bytes = sum(int_value(row, "span_length") for row in target_output_rows if row.get("promotion_ready") == "1")
    summary = {
        "scope": "total",
        "candidate_mode": "external_terminal_spatial_bridge_five_byte_combinator_probe",
        "target_spans": str(len(target_rows)),
        "target_bytes": str(target_bytes),
        "known_reference_rows": str(sum(1 for row in small_gap_rows if row.get("known_in_replay") == "1")),
        "known_reference_len5_rows": str(
            sum(1 for row in small_gap_rows if row.get("known_in_replay") == "1" and span_length(row) == 5)
        ),
        "diagnostic_len5_rows": str(sum(1 for row in small_gap_rows if span_length(row) == 5)),
        "target_template_rows": str(len(template_rows)),
        "compact_exact_spans": str(len(compact_exact_spans)),
        "compact_exact_bytes": str(
            sum(span_length(row) for row in target_rows if row.get("span_key", "") in compact_exact_spans)
        ),
        "target_only_combinator_spans": str(len(target_only_combinator_spans)),
        "target_only_combinator_bytes": str(
            sum(span_length(row) for row in target_rows if row.get("span_key", "") in target_only_combinator_spans)
        ),
        "known_eval_rows": str(sum(int_value(row, "known_eval_rows") for row in template_rows)),
        "known_exact_rows": str(sum(int_value(row, "known_exact_rows") for row in template_rows)),
        "known_false_rows": str(sum(int_value(row, "known_false_rows") for row in template_rows)),
        "diagnostic_eval_rows": str(sum(int_value(row, "diagnostic_eval_rows") for row in template_rows)),
        "diagnostic_exact_rows": str(sum(int_value(row, "diagnostic_exact_rows") for row in template_rows)),
        "diagnostic_false_rows": str(sum(int_value(row, "diagnostic_false_rows") for row in template_rows)),
        "diagnostic_false_spans": str(len(diagnostic_false_spans)),
        "top_diagnostic_false_span": diagnostic_false_spans[0] if diagnostic_false_spans else "",
        "best_target_span": best_target.get("span_key", ""),
        "best_template": best_target.get("best_selector", ""),
        "best_verdict": best_target.get("verdict", ""),
        "next_probe": (
            "derive non-oracle guard separating frontier 80 five-byte bridge combinator"
            if diagnostic_false_spans
            else (
                "find reference rows for frontier 80 five-byte bridge combinator"
                if promotion_ready_bytes == 0
                else "promote guarded frontier 80 five-byte bridge combinator"
            )
        ),
        "promotion_candidate_bytes": str(promotion_ready_bytes),
        "promotion_ready_bytes": str(promotion_ready_bytes),
        "issue_rows": str(len(buffer_issues) + len(segment_issues) + len(target_issues)),
    }
    return summary, target_output_rows, template_rows, diagnostics


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
    template_rows: list[dict[str, str]],
    diagnostic_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "targets": target_rows,
        "templates": template_rows,
        "diagnostics": diagnostic_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("targets.csv", output_dir / "targets.csv"),
            ("templates.csv", output_dir / "templates.csv"),
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
    <div class="muted">Tests local anchor/segment combinators for the five-byte frontier 80 bridge span.</div>
  </header>
  <section class="stats">
    <div class="stat"><div class="muted">Target bytes</div><div class="value">{summary['target_bytes']}</div></div>
    <div class="stat"><div class="muted">Compact exact</div><div class="value">{summary['compact_exact_bytes']}</div></div>
    <div class="stat"><div class="muted">Diagnostic false spans</div><div class="value warn">{summary['diagnostic_false_spans']}</div></div>
    <div class="stat"><div class="muted">Known len5 refs</div><div class="value warn">{summary['known_reference_len5_rows']}</div></div>
    <div class="stat"><div class="muted">Promotion-ready</div><div class="value warn">{summary['promotion_ready_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2>{links}</section>
  <section class="panel">
    <h2>Next</h2>
    <p><code>{html.escape(summary['next_probe'])}</code></p>
    <p class="muted">Best template: <code>{html.escape(summary['best_target_span'])}</code> / <code>{html.escape(summary['best_template'])}</code>.</p>
  </section>
  <section class="panel"><h2>Targets</h2>{render_table(target_rows, TARGET_FIELDNAMES)}</section>
  <section class="panel"><h2>Templates</h2>{render_table(template_rows, TEMPLATE_FIELDNAMES)}</section>
  <section class="panel"><h2>Diagnostics</h2>{render_table(diagnostic_rows, DIAGNOSTIC_FIELDNAMES)}</section>
  <script type="application/json" id="external-terminal-spatial-bridge-five-byte-combinator-data">{html.escape(data_json)}</script>
</main>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe five-byte combinators for frontier 80 spatial bridge output.")
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("--small-gaps", type=Path, default=DEFAULT_SMALL_GAPS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--max-distance", type=int, default=DEFAULT_MAX_DISTANCE)
    parser.add_argument("--max-delta", type=int, default=DEFAULT_MAX_DELTA)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex External Terminal Spatial Bridge Five-Byte Combinator Probe",
    )
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    summary, target_rows, template_rows, diagnostic_rows = build(
        read_csv(args.targets),
        read_csv(args.small_gaps),
        read_rows(args.fixtures),
        read_rows(args.manifest),
        max_distance=args.max_distance,
        max_delta=args.max_delta,
    )
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, target_rows)
    write_csv(args.output / "templates.csv", TEMPLATE_FIELDNAMES, template_rows)
    write_csv(args.output / "diagnostics.csv", DIAGNOSTIC_FIELDNAMES, diagnostic_rows)
    (args.output / "index.html").write_text(
        build_html(summary, target_rows, template_rows, diagnostic_rows, args.output, args.title),
        encoding="utf-8",
    )
    print(
        "External terminal spatial bridge five-byte combinator probe: "
        f"compact_exact={summary['compact_exact_bytes']}/{summary['target_bytes']} "
        f"diagnostic_false_spans={summary['diagnostic_false_spans']} "
        f"known_len5={summary['known_reference_len5_rows']} "
        f"promotion_ready={summary['promotion_ready_bytes']} "
        f"issues={summary['issue_rows']}"
    )
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
