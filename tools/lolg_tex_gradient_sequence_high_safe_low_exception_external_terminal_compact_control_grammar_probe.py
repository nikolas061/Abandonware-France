#!/usr/bin/env python3
"""Probe compact-control grammars for external terminal small nonzero gaps."""

from __future__ import annotations

import argparse
import csv
import html
import json
from dataclasses import dataclass
from pathlib import Path

from lolg_tex_gap_opcode_probe import relative_href, write_csv


DEFAULT_TARGETS = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_selector/targets.csv"
)
DEFAULT_SMALL_GAPS = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_selector/small_gaps.csv"
)
DEFAULT_MANIFEST = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_OUTPUT = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_compact_control_grammar"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "target_spans",
    "target_bytes",
    "known_reference_rows",
    "grammar_group_rows",
    "grammar_candidate_rows",
    "target_full_match_spans",
    "target_full_match_bytes",
    "guarded_full_match_spans",
    "guarded_full_match_bytes",
    "unsupported_full_match_spans",
    "rejected_full_match_spans",
    "best_target_span",
    "best_selector",
    "best_family",
    "best_exact_bytes",
    "best_output_hex",
    "neighbor_value_cover_bytes",
    "neighbor_value_full_spans",
    "unresolved_target_bytes",
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
    "gap_role",
    "control_ref_offset",
    "best_selector",
    "best_family",
    "best_exact_bytes",
    "best_full_match",
    "best_verdict",
    "best_output_hex",
    "neighbor_value_cover_bytes",
    "neighbor_value_expanded_cover_bytes",
    "neighbor_value_missing_hex",
    "issues",
]

CANDIDATE_FIELDNAMES = [
    "rank",
    "target_span",
    "family",
    "selector",
    "exact_bytes",
    "prefix_bytes",
    "full_match",
    "known_exact_rows",
    "known_false_rows",
    "known_miss_rows",
    "target_full_spans",
    "target_full_bytes",
    "verdict",
    "output_hex",
    "expected_hex",
]

GROUP_FIELDNAMES = [
    "rank",
    "family",
    "selector",
    "target_exact_bytes",
    "target_full_spans",
    "target_full_bytes",
    "known_exact_rows",
    "known_false_rows",
    "known_miss_rows",
    "guard_verdict",
    "sample_targets",
]


@dataclass(frozen=True)
class CandidateSpec:
    family: str
    selector: str
    pool: str
    rel: int
    stride: int
    transform: str
    parameter: int
    rel_b: int | None = None


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def int_value(row: dict[str, str] | dict[str, object], field: str, default: int = 0) -> int:
    try:
        return int(str(row.get(field, "")))
    except (TypeError, ValueError):
        return default


def row_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("archive", ""), row.get("pcx_name", ""), row.get("frontier_id", "")


def byte_exact(left: bytes, right: bytes) -> int:
    return sum(1 for left_value, right_value in zip(left, right) if left_value == right_value)


def common_prefix(left: bytes, right: bytes) -> int:
    limit = min(len(left), len(right))
    for index in range(limit):
        if left[index] != right[index]:
            return index
    return limit


def load_segments(manifest_rows: list[dict[str, str]]) -> tuple[dict[tuple[str, str, str], bytes], list[str]]:
    segments: dict[tuple[str, str, str], bytes] = {}
    issues: list[str] = []
    for row in manifest_rows:
        key = row_key(row)
        path = row.get("segment_gap_path", "")
        if not path:
            issues.append(f"missing_segment:{key}")
            continue
        try:
            segments[key] = Path(path).read_bytes()
        except OSError as exc:
            issues.append(f"read_segment_failed:{key}:{exc}")
    return segments, issues


def transform_bytes(data: bytes, transform: str, parameter: int) -> bytes:
    if transform == "identity":
        return data
    if transform == "low7":
        return bytes(value & 0x7F for value in data)
    if transform == "bit_not":
        return bytes(value ^ 0xFF for value in data)
    if transform == "add_const":
        return bytes((value + parameter) & 0xFF for value in data)
    if transform == "sub_const":
        return bytes((value - parameter) & 0xFF for value in data)
    if transform == "xor_const":
        return bytes(value ^ parameter for value in data)
    raise ValueError(f"unknown transform: {transform}")


def source_index(row: dict[str, str], segment: bytes, pool: str, rel: int) -> int | None:
    if pool == "seg_abs":
        index = rel
    elif pool == "seg_ref":
        control_ref = int_value(row, "control_ref_offset", -1)
        if control_ref < 0:
            return None
        index = control_ref + rel
    else:
        raise ValueError(f"unknown pool: {pool}")
    if index < 0 or index >= len(segment):
        return None
    return index


def candidate_output(row: dict[str, str], segment: bytes, spec: CandidateSpec) -> bytes | None:
    length = int_value(row, "length", int_value(row, "span_length"))
    if length <= 0:
        return None
    if spec.family.endswith("_slice"):
        start = source_index(row, segment, spec.pool, spec.rel)
        if start is None:
            return None
        indexes = [start + offset * spec.stride for offset in range(length)]
        if any(index < 0 or index >= len(segment) for index in indexes):
            return None
        return transform_bytes(bytes(segment[index] for index in indexes), spec.transform, spec.parameter)
    if spec.family.endswith("_repeat"):
        index = source_index(row, segment, spec.pool, spec.rel)
        if index is None:
            return None
        return transform_bytes(bytes([segment[index]]) * length, spec.transform, spec.parameter)
    if spec.family.endswith("_aba"):
        if length != 3 or spec.rel_b is None:
            return None
        first_index = source_index(row, segment, spec.pool, spec.rel)
        second_index = source_index(row, segment, spec.pool, spec.rel_b)
        if first_index is None or second_index is None:
            return None
        return transform_bytes(
            bytes([segment[first_index], segment[second_index], segment[first_index]]),
            spec.transform,
            spec.parameter,
        )
    raise ValueError(f"unknown family: {spec.family}")


def transform_label(transform: str, parameter: int) -> str:
    if transform in {"identity", "low7", "bit_not"}:
        return transform
    return f"{transform}={parameter:02x}"


def spec_label(spec: CandidateSpec) -> str:
    if spec.family.endswith("_aba"):
        return (
            f"{spec.pool}@{spec.rel},{spec.rel_b}:aba:"
            f"{transform_label(spec.transform, spec.parameter)}"
        )
    return (
        f"{spec.pool}@{spec.rel}:stride={spec.stride}:"
        f"{transform_label(spec.transform, spec.parameter)}"
    )


def transforms() -> list[tuple[str, int]]:
    rows: list[tuple[str, int]] = [("identity", 0), ("low7", 0), ("bit_not", 0)]
    for constant in (1, 2, 3, 4, 5, 6, 7, 8, 0x10, 0x20, 0x30, 0x40, 0x55, 0x6A, 0x80, 0xFF):
        rows.append(("add_const", constant))
        rows.append(("sub_const", constant))
        rows.append(("xor_const", constant))
    return rows


def candidate_specs() -> list[CandidateSpec]:
    specs: list[CandidateSpec] = []
    rel_range = range(-24, 32)
    abs_range = range(0, 32)
    for pool, offsets in (("seg_ref", rel_range), ("seg_abs", abs_range)):
        for rel in offsets:
            for stride in (-2, -1, 1, 2):
                for transform, parameter in transforms():
                    specs.append(
                        CandidateSpec(
                            f"{pool}_slice",
                            "",
                            pool,
                            rel,
                            stride,
                            transform,
                            parameter,
                        )
                    )
            for transform, parameter in transforms():
                specs.append(
                    CandidateSpec(
                        f"{pool}_repeat",
                        "",
                        pool,
                        rel,
                        1,
                        transform,
                        parameter,
                    )
                )
    for pool, offsets in (("seg_ref", rel_range), ("seg_abs", abs_range)):
        for rel in offsets:
            for rel_b in offsets:
                for transform, parameter in (("identity", 0), ("low7", 0), ("bit_not", 0)):
                    specs.append(
                        CandidateSpec(
                            f"{pool}_aba",
                            "",
                            pool,
                            rel,
                            1,
                            transform,
                            parameter,
                            rel_b=rel_b,
                        )
                    )
    return specs


def value_cover(row: dict[str, str], segment: bytes) -> tuple[int, int, str]:
    expected = bytes.fromhex(row.get("expected_hex", ""))
    control_ref = int_value(row, "control_ref_offset", -1)
    values = set(bytes.fromhex(row.get("prev_expected_hex", "")))
    values.update(bytes.fromhex(row.get("prev_source_hex", "")))
    values.update(bytes.fromhex(row.get("next_expected_hex", "")))
    if control_ref >= 0:
        values.update(segment[max(0, control_ref - 12) : min(len(segment), control_ref + 12)])
    expanded = set(values)
    for value in values:
        expanded.add((value - 1) & 0xFF)
        expanded.add((value + 1) & 0xFF)
    strict_count = sum(1 for value in expected if value in values)
    expanded_count = sum(1 for value in expected if value in expanded)
    missing = bytes(value for value in expected if value not in expanded).hex()
    return strict_count, expanded_count, missing


def threshold(length: int) -> int:
    if length <= 1:
        return 1
    if length <= 3:
        return max(1, length - 1)
    return max(1, length - 2)


def verdict(known_exact: int, known_false: int, target_full_bytes: int) -> str:
    if target_full_bytes <= 0:
        return "partial_only"
    if known_exact > 0 and known_false == 0:
        return "guarded_full_match"
    if known_exact == 0 and known_false == 0:
        return "unsupported_full_match"
    return "rejected_full_match"


def build(
    target_rows_in: list[dict[str, str]],
    small_gap_rows: list[dict[str, str]],
    manifest_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    segments, segment_issues = load_segments(manifest_rows)
    target_keys = {row.get("span_key", "") for row in target_rows_in}
    work_rows = [
        row
        for row in small_gap_rows
        if row.get("known_in_replay") == "1" or row.get("span_key", "") in target_keys
    ]
    target_lookup = {row.get("span_key", ""): row for row in small_gap_rows if row.get("span_key", "") in target_keys}
    target_rows = [target_lookup.get(row.get("span_key", ""), row) for row in target_rows_in]

    best_by_target: dict[str, dict[str, str]] = {}
    candidate_rows: list[dict[str, str]] = []
    group_rows: list[dict[str, str]] = []
    full_targets: set[str] = set()
    guarded_targets: set[str] = set()
    unsupported_targets: set[str] = set()
    rejected_targets: set[str] = set()

    for spec in candidate_specs():
        selector = spec_label(spec)
        known_exact = known_false = known_miss = 0
        target_exact_bytes = 0
        target_full_spans: set[str] = set()
        target_full_bytes = 0
        target_samples: list[str] = []
        per_target: list[dict[str, str]] = []

        for row in work_rows:
            expected = bytes.fromhex(row.get("expected_hex", ""))
            segment = segments.get(row_key(row), b"")
            output = candidate_output(row, segment, spec) if segment else None
            if output is None:
                if row.get("known_in_replay") == "1":
                    known_miss += 1
                continue
            exact = byte_exact(output, expected)
            prefix = common_prefix(output, expected)
            full = output == expected
            if row.get("known_in_replay") == "1":
                if full:
                    known_exact += 1
                else:
                    known_false += 1
            if row.get("span_key", "") in target_keys:
                target_exact_bytes += exact
                if full:
                    target_full_spans.add(row.get("span_key", ""))
                    target_full_bytes += int_value(row, "length")
                    target_samples.append(row.get("span_key", ""))
                if exact >= threshold(len(expected)):
                    per_target.append(
                        {
                            "target_span": row.get("span_key", ""),
                            "family": spec.family,
                            "selector": selector,
                            "exact_bytes": str(exact),
                            "prefix_bytes": str(prefix),
                            "full_match": "1" if full else "0",
                            "known_exact_rows": str(known_exact),
                            "known_false_rows": str(known_false),
                            "known_miss_rows": str(known_miss),
                            "target_full_spans": "",
                            "target_full_bytes": "",
                            "verdict": "",
                            "output_hex": output.hex(),
                            "expected_hex": expected.hex(),
                        }
                    )

        if target_exact_bytes <= 0:
            continue
        guard_verdict = verdict(known_exact, known_false, target_full_bytes)
        if target_full_spans:
            full_targets.update(target_full_spans)
            if guard_verdict == "guarded_full_match":
                guarded_targets.update(target_full_spans)
            elif guard_verdict == "unsupported_full_match":
                unsupported_targets.update(target_full_spans)
            elif guard_verdict == "rejected_full_match":
                rejected_targets.update(target_full_spans)
        group_rows.append(
            {
                "rank": "",
                "family": spec.family,
                "selector": selector,
                "target_exact_bytes": str(target_exact_bytes),
                "target_full_spans": str(len(target_full_spans)),
                "target_full_bytes": str(target_full_bytes),
                "known_exact_rows": str(known_exact),
                "known_false_rows": str(known_false),
                "known_miss_rows": str(known_miss),
                "guard_verdict": guard_verdict,
                "sample_targets": ";".join(target_samples[:8]),
            }
        )
        for row in per_target:
            row["known_exact_rows"] = str(known_exact)
            row["known_false_rows"] = str(known_false)
            row["known_miss_rows"] = str(known_miss)
            row["target_full_spans"] = str(len(target_full_spans))
            row["target_full_bytes"] = str(target_full_bytes)
            row["verdict"] = guard_verdict
            candidate_rows.append(row)
            target_span = row.get("target_span", "")
            previous = best_by_target.get(target_span)
            if previous is None or (
                int_value(row, "exact_bytes"),
                row.get("full_match") == "1",
                -int_value(row, "known_false_rows"),
            ) > (
                int_value(previous, "exact_bytes"),
                previous.get("full_match") == "1",
                -int_value(previous, "known_false_rows"),
            ):
                best_by_target[target_span] = row

    candidate_rows.sort(
        key=lambda row: (
            row.get("verdict") != "guarded_full_match",
            row.get("verdict") != "unsupported_full_match",
            -int_value(row, "exact_bytes"),
            int_value(row, "known_false_rows"),
            -int_value(row, "known_exact_rows"),
            row.get("target_span", ""),
            row.get("selector", ""),
        )
    )
    for index, row in enumerate(candidate_rows[:2000], start=1):
        row["rank"] = str(index)
    candidate_rows = candidate_rows[:2000]

    group_rows.sort(
        key=lambda row: (
            row.get("guard_verdict") != "guarded_full_match",
            row.get("guard_verdict") != "unsupported_full_match",
            -int_value(row, "target_full_bytes"),
            -int_value(row, "target_exact_bytes"),
            int_value(row, "known_false_rows"),
            -int_value(row, "known_exact_rows"),
            row.get("selector", ""),
        )
    )
    for index, row in enumerate(group_rows[:1200], start=1):
        row["rank"] = str(index)
    group_rows = group_rows[:1200]

    target_output_rows: list[dict[str, str]] = []
    neighbor_cover_bytes = 0
    neighbor_full_spans = 0
    for index, row in enumerate(target_rows, start=1):
        span_key = row.get("span_key", "")
        segment = segments.get(row_key(row), b"")
        strict_cover, expanded_cover, missing = value_cover(row, segment) if segment else (0, 0, row.get("expected_hex", ""))
        length = int_value(row, "span_length", int_value(row, "length"))
        neighbor_cover_bytes += expanded_cover
        if expanded_cover == length:
            neighbor_full_spans += 1
        best = best_by_target.get(span_key, {})
        target_output_rows.append(
            {
                "rank": str(index),
                "archive": row.get("archive", ""),
                "archive_tag": row.get("archive_tag", ""),
                "pcx_name": row.get("pcx_name", ""),
                "frontier_id": row.get("frontier_id", ""),
                "span_key": span_key,
                "span_start": row.get("span_start", row.get("expected_start", "")),
                "span_end": row.get("span_end", row.get("expected_end", "")),
                "span_length": str(length),
                "expected_hex": row.get("expected_hex", ""),
                "gap_role": row.get("gap_role", ""),
                "control_ref_offset": row.get("control_ref_offset", ""),
                "best_selector": best.get("selector", ""),
                "best_family": best.get("family", ""),
                "best_exact_bytes": best.get("exact_bytes", "0"),
                "best_full_match": best.get("full_match", "0"),
                "best_verdict": best.get("verdict", "missing_candidate"),
                "best_output_hex": best.get("output_hex", ""),
                "neighbor_value_cover_bytes": str(strict_cover),
                "neighbor_value_expanded_cover_bytes": str(expanded_cover),
                "neighbor_value_missing_hex": missing,
                "issues": "" if segment else "missing_segment",
            }
        )

    best_candidate = max(candidate_rows, key=lambda row: int_value(row, "exact_bytes"), default={})
    target_bytes = sum(int_value(row, "span_length", int_value(row, "length")) for row in target_rows)
    guarded_bytes = sum(
        int_value(row, "span_length", int_value(row, "length"))
        for row in target_rows
        if row.get("span_key", "") in guarded_targets
    )
    next_probe = (
        "probe spatial gradient bridge ordering for external terminal compact-control values"
        if neighbor_cover_bytes >= target_bytes and guarded_bytes < target_bytes
        else "expand compact-control grammar for unresolved external terminal spans"
    )
    summary = {
        "scope": "total",
        "candidate_mode": "external_terminal_compact_control_grammar_probe",
        "target_spans": str(len(target_rows)),
        "target_bytes": str(target_bytes),
        "known_reference_rows": str(sum(1 for row in work_rows if row.get("known_in_replay") == "1")),
        "grammar_group_rows": str(len(group_rows)),
        "grammar_candidate_rows": str(len(candidate_rows)),
        "target_full_match_spans": str(len(full_targets)),
        "target_full_match_bytes": str(
            sum(
                int_value(row, "span_length", int_value(row, "length"))
                for row in target_rows
                if row.get("span_key", "") in full_targets
            )
        ),
        "guarded_full_match_spans": str(len(guarded_targets)),
        "guarded_full_match_bytes": str(guarded_bytes),
        "unsupported_full_match_spans": str(len(unsupported_targets)),
        "rejected_full_match_spans": str(len(rejected_targets)),
        "best_target_span": best_candidate.get("target_span", ""),
        "best_selector": best_candidate.get("selector", ""),
        "best_family": best_candidate.get("family", ""),
        "best_exact_bytes": best_candidate.get("exact_bytes", "0"),
        "best_output_hex": best_candidate.get("output_hex", ""),
        "neighbor_value_cover_bytes": str(neighbor_cover_bytes),
        "neighbor_value_full_spans": str(neighbor_full_spans),
        "unresolved_target_bytes": str(target_bytes - guarded_bytes),
        "next_probe": next_probe,
        "promotion_candidate_bytes": "0",
        "promotion_ready_bytes": "0",
        "issue_rows": str(len(segment_issues) + sum(1 for row in target_output_rows if row.get("issues"))),
    }
    return summary, target_output_rows, candidate_rows, group_rows


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 220) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    target_rows: list[dict[str, str]],
    candidate_rows: list[dict[str, str]],
    group_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "targets": target_rows,
        "candidates": candidate_rows,
        "groups": group_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("targets.csv", output_dir / "targets.csv"),
            ("candidates.csv", output_dir / "candidates.csv"),
            ("groups.csv", output_dir / "groups.csv"),
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
table {{ width: 100%; min-width: 1300px; border-collapse: collapse; }}
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
    <div class="muted">Tests deterministic compact-control windows around control_ref_offset for small external terminal gaps.</div>
  </header>
  <section class="stats">
    <div class="stat"><div class="muted">Target bytes</div><div class="value">{summary['target_bytes']}</div></div>
    <div class="stat"><div class="muted">Full target matches</div><div class="value warn">{summary['target_full_match_bytes']}</div></div>
    <div class="stat"><div class="muted">Guarded full matches</div><div class="value warn">{summary['guarded_full_match_bytes']}</div></div>
    <div class="stat"><div class="muted">Neighbor value cover</div><div class="value">{summary['neighbor_value_cover_bytes']}</div></div>
    <div class="stat"><div class="muted">Unresolved</div><div class="value warn">{summary['unresolved_target_bytes']}</div></div>
    <div class="stat"><div class="muted">Promotion-ready</div><div class="value warn">{summary['promotion_ready_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2>{links}</section>
  <section class="panel">
    <h2>Next</h2>
    <p><code>{html.escape(summary['next_probe'])}</code></p>
    <p class="muted">Best deterministic candidate: <code>{html.escape(summary['best_target_span'])}</code> via <code>{html.escape(summary['best_selector'])}</code> ({html.escape(summary['best_exact_bytes'])} exact bytes).</p>
  </section>
  <section class="panel"><h2>Targets</h2>{render_table(target_rows, TARGET_FIELDNAMES)}</section>
  <section class="panel"><h2>Candidate groups</h2>{render_table(group_rows, GROUP_FIELDNAMES)}</section>
  <section class="panel"><h2>Target candidates</h2>{render_table(candidate_rows, CANDIDATE_FIELDNAMES)}</section>
  <script type="application/json" id="external-terminal-compact-control-data">{html.escape(data_json)}</script>
</main>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe compact-control grammar for external terminal small gaps.")
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("--small-gaps", type=Path, default=DEFAULT_SMALL_GAPS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex External Terminal Compact-Control Grammar Probe",
    )
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    summary, target_rows, candidate_rows, group_rows = build(
        read_csv(args.targets),
        read_csv(args.small_gaps),
        read_csv(args.manifest),
    )
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, target_rows)
    write_csv(args.output / "candidates.csv", CANDIDATE_FIELDNAMES, candidate_rows)
    write_csv(args.output / "groups.csv", GROUP_FIELDNAMES, group_rows)
    html_path = args.output / "index.html"
    html_path.write_text(
        build_html(summary, target_rows, candidate_rows, group_rows, args.output, args.title),
        encoding="utf-8",
    )

    print(f"Target bytes: {summary['target_bytes']}")
    print(f"Full target matches: {summary['target_full_match_bytes']}")
    print(f"Guarded full matches: {summary['guarded_full_match_bytes']}")
    print(f"Neighbor value cover: {summary['neighbor_value_cover_bytes']}")
    print(f"Next probe: {summary['next_probe']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
