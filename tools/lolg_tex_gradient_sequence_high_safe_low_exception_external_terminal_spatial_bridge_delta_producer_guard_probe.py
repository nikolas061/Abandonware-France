#!/usr/bin/env python3
"""Probe non-oracle guards for compact/control spatial bridge delta producers."""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
from collections import defaultdict
from pathlib import Path

from lolg_tex_gap_opcode_probe import relative_href, write_csv
from lolg_tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_delta_producer_probe import (
    ProducerSpec,
    load_segments,
    producer_output,
    row_key,
)
from lolg_tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_selector_probe import (
    span_length,
)
from lolg_tex_micro_mixed_value_payload_state_opcode_probe import int_value


DEFAULT_TARGETS = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_delta_producer/targets.csv"
)
DEFAULT_PRODUCERS = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_delta_producer/producers.csv"
)
DEFAULT_CANDIDATES = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_delta_producer/candidates.csv"
)
DEFAULT_SMALL_GAPS = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_selector/small_gaps.csv"
)
DEFAULT_MANIFEST = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_OUTPUT = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_delta_producer_guard"
)

SELECTOR_RE = re.compile(
    r"^(?P<pool>seg_(?:abs|ref))@(?P<rel>-?\d+)"
    r"(?:(?:,(?P<rel_b>-?\d+):aba)|(?::stride=(?P<stride>-?\d+)))"
    r":(?P<transform>[a-z0-9_]+)(?:=(?P<parameter>[0-9a-fA-F]+))?$"
)

KEY_FIELD_SETS = [
    ("gap_role", "span_length", "control_ref_mod64", "anchor_side"),
    ("gap_role", "span_length", "op_pair", "anchor_side"),
    ("gap_role", "span_length", "next_op_length", "anchor_side"),
    ("gap_role", "span_length", "anchor_side"),
    ("span_length", "anchor_side"),
]

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "target_spans",
    "target_bytes",
    "rejected_target_spans",
    "rejected_target_bytes",
    "producer_rows",
    "known_candidate_rows",
    "guard_rows",
    "false_free_guard_rows",
    "best_target_span",
    "best_selector",
    "best_guard_family",
    "best_guard_key",
    "best_guard_direction",
    "best_guard_threshold",
    "best_known_exact_rows",
    "best_known_false_rows",
    "best_rejected_false_rows",
    "target_guarded_bytes",
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
    "best_family",
    "best_selector",
    "best_output_hex",
    "producer_verdict",
    "guard_family",
    "guard_key",
    "guard_direction",
    "guard_threshold",
    "guard_verdict",
    "known_exact_rows",
    "known_false_rows",
    "rejected_false_rows",
    "promotion_ready",
    "issues",
]

GUARD_FIELDNAMES = [
    "rank",
    "target_span",
    "producer_family",
    "producer_selector",
    "guard_family",
    "guard_key",
    "guard_direction",
    "guard_threshold",
    "target_matches",
    "known_exact_rows",
    "known_exact_spans",
    "known_false_rows",
    "known_false_spans",
    "rejected_false_rows",
    "rejected_false_spans",
    "verdict",
    "sample_known_exact",
    "sample_rejected_false",
]

EVAL_FIELDNAMES = [
    "rank",
    "target_span",
    "producer_selector",
    "scope",
    "span_key",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "expected_hex",
    "output_hex",
    "exact_match",
    "gap_role",
    "span_length",
    "prev_op_length",
    "next_op_length",
    "op_pair",
    "prev_tail2",
    "next_head2",
    "control_ref_mod64",
    "control_head4",
    "control_tail4",
    "anchor_side",
    "anchor_rel",
    "anchor_byte",
    "delta_signature",
]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def parse_selector(family: str, selector: str) -> ProducerSpec | None:
    match = SELECTOR_RE.match(selector)
    if not match:
        return None
    parameter_text = match.group("parameter")
    return ProducerSpec(
        family=family,
        pool=match.group("pool"),
        rel=int(match.group("rel")),
        stride=int(match.group("stride") or "1"),
        transform=match.group("transform"),
        parameter=int(parameter_text, 16) if parameter_text else 0,
        rel_b=int(match.group("rel_b")) if match.group("rel_b") is not None else None,
    )


def hex_head(value: str, byte_count: int) -> str:
    return value[: byte_count * 2] if value else "."


def hex_tail(value: str, byte_count: int) -> str:
    return value[-byte_count * 2 :] if value else "."


def feature_row(
    gap: dict[str, str],
    candidate: dict[str, str],
    *,
    scope: str,
    output: bytes,
    target_span: str,
    producer_selector: str,
) -> dict[str, str]:
    previous_kind = gap.get("prev_op_kind", "") or "."
    next_kind = gap.get("next_op_kind", "") or "."
    expected_hex = gap.get("expected_hex", candidate.get("expected_hex", ""))
    return {
        "rank": "",
        "target_span": target_span,
        "producer_selector": producer_selector,
        "scope": scope,
        "span_key": gap.get("span_key", candidate.get("span_key", "")),
        "archive": gap.get("archive", candidate.get("archive", "")),
        "archive_tag": gap.get("archive_tag", candidate.get("archive_tag", "")),
        "pcx_name": gap.get("pcx_name", candidate.get("pcx_name", "")),
        "frontier_id": gap.get("frontier_id", candidate.get("frontier_id", "")),
        "expected_hex": expected_hex,
        "output_hex": output.hex(),
        "exact_match": "1" if output.hex() == expected_hex else "0",
        "gap_role": gap.get("gap_role", ""),
        "span_length": str(span_length(gap)),
        "prev_op_length": gap.get("prev_op_length", "") or ".",
        "next_op_length": gap.get("next_op_length", "") or ".",
        "op_pair": f"{previous_kind}->{next_kind}",
        "prev_tail2": hex_tail(gap.get("prev_expected_hex", ""), 2),
        "next_head2": hex_head(gap.get("next_expected_hex", ""), 2),
        "control_ref_mod64": gap.get("control_ref_mod64", ""),
        "control_head4": gap.get("control_head4", ""),
        "control_tail4": gap.get("control_tail4", ""),
        "anchor_side": candidate.get("anchor_side", ""),
        "anchor_rel": candidate.get("anchor_rel", ""),
        "anchor_byte": candidate.get("anchor_byte", ""),
        "delta_signature": candidate.get("delta_signature", ""),
    }


def guard_key(row: dict[str, str], fields: tuple[str, ...]) -> str:
    return "|".join(f"{field}={row.get(field, '.') or '.'}" for field in fields)


def threshold_match(row: dict[str, str], direction: str, threshold: int) -> bool:
    value = int_value(row, "anchor_rel", 999999)
    if direction == "lte":
        return value <= threshold
    if direction == "gte":
        return value >= threshold
    return False


def build_guard_rows(
    target_eval: dict[str, str],
    known_eval_rows: list[dict[str, str]],
    producer: dict[str, str],
) -> list[dict[str, str]]:
    output_rows: list[dict[str, str]] = []
    known_exact_all = [row for row in known_eval_rows if row.get("exact_match") == "1"]
    known_false_all = [row for row in known_eval_rows if row.get("exact_match") != "1"]
    for fields in KEY_FIELD_SETS:
        family = "+".join(fields) + "+anchor_rel_threshold"
        key = guard_key(target_eval, fields)
        same_key_rows = [row for row in known_eval_rows if guard_key(row, fields) == key]
        exact_rows = [row for row in same_key_rows if row.get("exact_match") == "1"]
        false_rows = [row for row in same_key_rows if row.get("exact_match") != "1"]
        thresholds = sorted({int_value(row, "anchor_rel") for row in exact_rows})
        for direction in ("lte", "gte"):
            for threshold in thresholds:
                if not threshold_match(target_eval, direction, threshold):
                    continue
                guarded_exact = [row for row in exact_rows if threshold_match(row, direction, threshold)]
                guarded_false = [row for row in false_rows if threshold_match(row, direction, threshold)]
                rejected_false = [row for row in known_false_all if row not in guarded_false]
                if guarded_false:
                    verdict = "known_false_conflict"
                elif guarded_exact:
                    verdict = "known_false_free_threshold"
                else:
                    verdict = "target_only_threshold"
                exact_spans = sorted({row.get("span_key", "") for row in guarded_exact})
                false_spans = sorted({row.get("span_key", "") for row in guarded_false})
                rejected_false_spans = sorted({row.get("span_key", "") for row in rejected_false})
                output_rows.append(
                    {
                        "rank": "",
                        "target_span": target_eval.get("target_span", ""),
                        "producer_family": producer.get("family", ""),
                        "producer_selector": producer.get("selector", ""),
                        "guard_family": family,
                        "guard_key": key,
                        "guard_direction": direction,
                        "guard_threshold": str(threshold),
                        "target_matches": "1",
                        "known_exact_rows": str(len(guarded_exact)),
                        "known_exact_spans": str(len(exact_spans)),
                        "known_false_rows": str(len(guarded_false)),
                        "known_false_spans": str(len(false_spans)),
                        "rejected_false_rows": str(len(rejected_false)),
                        "rejected_false_spans": str(len(rejected_false_spans)),
                        "verdict": verdict,
                        "sample_known_exact": ";".join(exact_spans[:8]),
                        "sample_rejected_false": ";".join(rejected_false_spans[:8]),
                    }
                )
    output_rows.sort(
        key=lambda row: (
            row.get("verdict") != "known_false_free_threshold",
            -int_value(row, "known_exact_rows"),
            -int_value(row, "rejected_false_rows"),
            len(row.get("guard_family", "").split("+")),
            row.get("guard_family", ""),
            int_value(row, "guard_threshold"),
        )
    )
    return output_rows


def evaluate_producer(
    producer: dict[str, str],
    target: dict[str, str],
    target_candidate: dict[str, str],
    known_candidates: list[dict[str, str]],
    small_by_span: dict[str, dict[str, str]],
    segments: dict[tuple[str, str, str], bytes],
) -> tuple[dict[str, str] | None, list[dict[str, str]], list[str]]:
    issues: list[str] = []
    spec = parse_selector(producer.get("family", ""), producer.get("selector", ""))
    if spec is None:
        return None, [], ["unsupported_producer_selector"]
    target_segment = segments.get(row_key(target))
    if target_segment is None:
        return None, [], ["missing_target_segment"]
    target_output = producer_output(target, target_candidate, target_segment, spec)
    if target_output is None:
        return None, [], ["target_producer_output_failed"]
    target_eval = feature_row(
        target,
        target_candidate,
        scope="target",
        output=target_output,
        target_span=target.get("span_key", ""),
        producer_selector=producer.get("selector", ""),
    )

    known_eval_rows: list[dict[str, str]] = []
    for candidate in known_candidates:
        gap = small_by_span.get(candidate.get("span_key", ""))
        if not gap:
            continue
        segment = segments.get(row_key(gap))
        if segment is None:
            continue
        output = producer_output(gap, candidate, segment, spec)
        if output is None:
            continue
        known_eval_rows.append(
            feature_row(
                gap,
                candidate,
                scope="known",
                output=output,
                target_span=target.get("span_key", ""),
                producer_selector=producer.get("selector", ""),
            )
        )
    return target_eval, known_eval_rows, issues


def build(
    target_rows_in: list[dict[str, str]],
    producer_rows_in: list[dict[str, str]],
    candidate_rows: list[dict[str, str]],
    small_gap_rows: list[dict[str, str]],
    manifest_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    segments, segment_issues = load_segments(manifest_rows)
    small_by_span = {row.get("span_key", ""): row for row in small_gap_rows}
    target_candidates = {row.get("span_key", ""): row for row in candidate_rows if row.get("scope") == "target"}
    known_candidates = [row for row in candidate_rows if row.get("scope") == "known"]
    producers_by_span: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in producer_rows_in:
        if row.get("guard") != "compact_control":
            continue
        if int_value(row, "exact_bytes") <= 0:
            continue
        producers_by_span[row.get("target_span", "")].append(row)

    rejected_targets = [
        row
        for row in target_rows_in
        if row.get("verdict") == "rejected_known_false"
        and int_value(row, "best_exact_bytes") == span_length(row)
    ]

    all_target_rows: list[dict[str, str]] = []
    all_guard_rows: list[dict[str, str]] = []
    all_eval_rows: list[dict[str, str]] = []
    issue_rows = len(segment_issues)

    for index, target_row in enumerate(rejected_targets, start=1):
        span_key = target_row.get("span_key", "")
        target = small_by_span.get(span_key, target_row)
        target_candidate = target_candidates.get(span_key, {})
        target_issues: list[str] = []
        best_guard: dict[str, str] = {}
        best_producer: dict[str, str] = {}
        best_target_eval: dict[str, str] | None = None
        for producer in producers_by_span.get(span_key, []):
            target_eval, known_eval_rows, issues = evaluate_producer(
                producer,
                target,
                target_candidate,
                known_candidates,
                small_by_span,
                segments,
            )
            target_issues.extend(issues)
            if target_eval is None:
                continue
            all_eval_rows.append(target_eval)
            all_eval_rows.extend(known_eval_rows)
            guard_rows = build_guard_rows(target_eval, known_eval_rows, producer)
            all_guard_rows.extend(guard_rows)
            candidate_guard = guard_rows[0] if guard_rows else {}
            if not candidate_guard:
                continue
            if not best_guard or (
                candidate_guard.get("verdict") == "known_false_free_threshold",
                int_value(candidate_guard, "known_exact_rows"),
                int_value(candidate_guard, "rejected_false_rows"),
                -len(candidate_guard.get("guard_family", "").split("+")),
            ) > (
                best_guard.get("verdict") == "known_false_free_threshold",
                int_value(best_guard, "known_exact_rows"),
                int_value(best_guard, "rejected_false_rows"),
                -len(best_guard.get("guard_family", "").split("+")),
            ):
                best_guard = candidate_guard
                best_producer = producer
                best_target_eval = target_eval

        ready = best_guard.get("verdict") == "known_false_free_threshold"
        if target_issues:
            issue_rows += 1
        all_target_rows.append(
            {
                "rank": str(index),
                "archive": target.get("archive", target_row.get("archive", "")),
                "archive_tag": target.get("archive_tag", target_row.get("archive_tag", "")),
                "pcx_name": target.get("pcx_name", target_row.get("pcx_name", "")),
                "frontier_id": target.get("frontier_id", target_row.get("frontier_id", "")),
                "span_key": span_key,
                "span_start": target_row.get("span_start", target.get("span_start", "")),
                "span_end": target_row.get("span_end", target.get("span_end", "")),
                "span_length": target_row.get("span_length", str(span_length(target))),
                "expected_hex": target.get("expected_hex", target_row.get("expected_hex", "")),
                "best_family": best_producer.get("family", target_row.get("best_family", "")),
                "best_selector": best_producer.get("selector", target_row.get("best_selector", "")),
                "best_output_hex": best_target_eval.get("output_hex", "") if best_target_eval else "",
                "producer_verdict": best_producer.get("verdict", target_row.get("verdict", "")),
                "guard_family": best_guard.get("guard_family", ""),
                "guard_key": best_guard.get("guard_key", ""),
                "guard_direction": best_guard.get("guard_direction", ""),
                "guard_threshold": best_guard.get("guard_threshold", ""),
                "guard_verdict": best_guard.get("verdict", "missing_guard"),
                "known_exact_rows": best_guard.get("known_exact_rows", "0"),
                "known_false_rows": best_guard.get("known_false_rows", "0"),
                "rejected_false_rows": best_guard.get("rejected_false_rows", "0"),
                "promotion_ready": "1" if ready else "0",
                "issues": ";".join(sorted(set(target_issues))),
            }
        )

    all_guard_rows.sort(
        key=lambda row: (
            row.get("verdict") != "known_false_free_threshold",
            -int_value(row, "known_exact_rows"),
            -int_value(row, "rejected_false_rows"),
            len(row.get("guard_family", "").split("+")),
            row.get("target_span", ""),
            row.get("guard_family", ""),
        )
    )
    for index, row in enumerate(all_guard_rows, start=1):
        row["rank"] = str(index)
    for index, row in enumerate(all_eval_rows, start=1):
        row["rank"] = str(index)

    ready_bytes = sum(int_value(row, "span_length") for row in all_target_rows if row.get("promotion_ready") == "1")
    target_bytes = sum(int_value(row, "span_length") for row in all_target_rows)
    best_target = next((row for row in all_target_rows if row.get("promotion_ready") == "1"), all_target_rows[0] if all_target_rows else {})
    false_free_guards = [row for row in all_guard_rows if row.get("verdict") == "known_false_free_threshold"]
    summary = {
        "scope": "total",
        "candidate_mode": "external_terminal_spatial_bridge_delta_producer_guard_probe",
        "target_spans": str(len(target_rows_in)),
        "target_bytes": str(sum(int_value(row, "span_length") for row in target_rows_in)),
        "rejected_target_spans": str(len(all_target_rows)),
        "rejected_target_bytes": str(target_bytes),
        "producer_rows": str(len(producer_rows_in)),
        "known_candidate_rows": str(len(known_candidates)),
        "guard_rows": str(len(all_guard_rows)),
        "false_free_guard_rows": str(len(false_free_guards)),
        "best_target_span": best_target.get("span_key", ""),
        "best_selector": best_target.get("best_selector", ""),
        "best_guard_family": best_target.get("guard_family", ""),
        "best_guard_key": best_target.get("guard_key", ""),
        "best_guard_direction": best_target.get("guard_direction", ""),
        "best_guard_threshold": best_target.get("guard_threshold", ""),
        "best_known_exact_rows": best_target.get("known_exact_rows", "0"),
        "best_known_false_rows": best_target.get("known_false_rows", "0"),
        "best_rejected_false_rows": best_target.get("rejected_false_rows", "0"),
        "target_guarded_bytes": str(ready_bytes),
        "next_probe": (
            "promote guarded compact/control bridge delta producer bytes"
            if ready_bytes > 0
            else "expand non-oracle guard thresholds for compact/control bridge delta producers"
        ),
        "promotion_candidate_bytes": str(ready_bytes),
        "promotion_ready_bytes": str(ready_bytes),
        "issue_rows": str(issue_rows),
    }
    return summary, all_target_rows, all_guard_rows, all_eval_rows


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
    eval_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "targets": target_rows,
        "guards": guard_rows,
        "evaluations": eval_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("targets.csv", output_dir / "targets.csv"),
            ("guards.csv", output_dir / "guards.csv"),
            ("evaluations.csv", output_dir / "evaluations.csv"),
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
    <div class="muted">Tests threshold guards derived from known exact/false compact-control bridge producer rows.</div>
  </header>
  <section class="stats">
    <div class="stat"><div class="muted">Rejected target bytes</div><div class="value">{summary['rejected_target_bytes']}</div></div>
    <div class="stat"><div class="muted">False-free guards</div><div class="value">{summary['false_free_guard_rows']}</div></div>
    <div class="stat"><div class="muted">Guarded bytes</div><div class="value">{summary['target_guarded_bytes']}</div></div>
    <div class="stat"><div class="muted">Promotion-ready</div><div class="value warn">{summary['promotion_ready_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2>{links}</section>
  <section class="panel">
    <h2>Next</h2>
    <p><code>{html.escape(summary['next_probe'])}</code></p>
    <p class="muted">Best guard: <code>{html.escape(summary['best_guard_family'])}</code> / <code>{html.escape(summary['best_guard_direction'])}:{html.escape(summary['best_guard_threshold'])}</code>.</p>
  </section>
  <section class="panel"><h2>Targets</h2>{render_table(target_rows, TARGET_FIELDNAMES)}</section>
  <section class="panel"><h2>Guards</h2>{render_table(guard_rows, GUARD_FIELDNAMES)}</section>
  <section class="panel"><h2>Evaluations</h2>{render_table(eval_rows, EVAL_FIELDNAMES)}</section>
  <script type="application/json" id="external-terminal-spatial-bridge-delta-producer-guard-data">{html.escape(data_json)}</script>
</main>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe guards for compact/control bridge delta producers.")
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("--producers", type=Path, default=DEFAULT_PRODUCERS)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--small-gaps", type=Path, default=DEFAULT_SMALL_GAPS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex External Terminal Spatial Bridge Delta Producer Guard Probe",
    )
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    summary, target_rows, guard_rows, eval_rows = build(
        read_rows(args.targets),
        read_rows(args.producers),
        read_rows(args.candidates),
        read_rows(args.small_gaps),
        read_rows(args.manifest),
    )
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, target_rows)
    write_csv(args.output / "guards.csv", GUARD_FIELDNAMES, guard_rows)
    write_csv(args.output / "evaluations.csv", EVAL_FIELDNAMES, eval_rows)
    (args.output / "index.html").write_text(
        build_html(summary, target_rows, guard_rows, eval_rows, args.output, args.title),
        encoding="utf-8",
    )
    print(
        "External terminal spatial bridge delta producer guard probe: "
        f"guarded={summary['target_guarded_bytes']}/{summary['rejected_target_bytes']} "
        f"false_free_guards={summary['false_free_guard_rows']} "
        f"promotion_ready={summary['promotion_ready_bytes']} "
        f"issues={summary['issue_rows']}"
    )
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
