#!/usr/bin/env python3
"""Review compact-control token producers for the final frontier 80 pre-run pair."""

from __future__ import annotations

import argparse
import csv
import html
import json
from dataclasses import dataclass
from pathlib import Path

from lolg_tex_gap_opcode_probe import relative_href, write_csv
from lolg_tex_micro_mixed_value_payload_state_opcode_probe import int_value


DEFAULT_SLOTS = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_old_clean_byte_union_thirteenth_outside_source_dependency_promoted_replay/slots.csv"
)
DEFAULT_BASE_FIXTURES = Path("output/tex_old_clean_byte_union_thirteenth_outside_source_dependency_promoted_replay/fixtures.csv")
DEFAULT_MANIFEST = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_DELTA_TARGETS = Path("output/tex_old_clean_byte_union_frontier80_tail_prerun_delta_review/targets.csv")
DEFAULT_OUTPUT = Path("output/tex_old_clean_byte_union_frontier80_tail_compact_token_review")

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "target_key",
    "target_pair_offset",
    "target_pair_hex",
    "target_run_value",
    "target_run_start",
    "target_run_end",
    "target_delta",
    "pair_rows",
    "known_pair_rows",
    "same_delta_rows",
    "selector_rows",
    "target_full_selector_rows",
    "guarded_selector_rows",
    "weak_guarded_selector_rows",
    "unsupported_selector_rows",
    "rejected_selector_rows",
    "best_selector",
    "best_family",
    "best_source_pool",
    "best_target_output_hex",
    "best_known_exact_rows",
    "best_known_false_rows",
    "best_verdict",
    "best_known_exact_samples",
    "best_known_false_samples",
    "review_verdict",
    "next_probe",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

CANDIDATE_FIELDNAMES = [
    "rank",
    "selector",
    "family",
    "source_pool",
    "source_ref",
    "stride",
    "transform",
    "parameter",
    "target_output_hex",
    "target_expected_hex",
    "target_exact_bytes",
    "target_full_match",
    "known_exact_rows",
    "known_false_rows",
    "known_miss_rows",
    "same_delta_full_rows",
    "same_delta_known_exact_rows",
    "same_delta_unknown_full_rows",
    "verdict",
    "known_exact_samples",
    "known_false_samples",
    "target_samples",
]

PAIR_FIELDNAMES = [
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "pair_offset",
    "pair_hex",
    "known_pair_bits",
    "decoded_pair_hex",
    "run_start",
    "run_end",
    "run_length",
    "run_value",
    "delta",
    "delta_hex",
    "control_prefix_bytes",
    "fragment_bytes",
    "segment_gap_bytes",
    "control_prefix_hex",
    "fragment_hex",
    "segment_head_hex",
    "is_target",
    "issues",
]

TARGET_FIELDNAMES = [
    "rank",
    "slot_rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "target_offset",
    "source_offset",
    "expected_byte",
    "predicted_byte",
    "best_selector",
    "best_formula",
    "best_guard_family",
    "best_guard_key",
    "promotion_ready",
    "issues",
]

SMALL_CONSTANTS = (1, 2, 3, 4, 5, 6, 7, 8, 0x10, 0x20, 0x30, 0x40, 0x55, 0x6A, 0x80, 0xFF)
SIMPLE_TRANSFORMS = (("identity", 0), ("low7", 0), ("bit_not", 0))
DELTA_TRANSFORMS = ("low_nibble", "high_nibble", "low2", "high2", "low3", "signed_low_nibble")


@dataclass(frozen=True)
class PairContext:
    row: dict[str, str]
    expected: bytes
    decoded: bytes
    known_mask: bytes
    segment: bytes
    control_prefix: bytes
    fragment: bytes
    pair_start: int
    pair_len: int
    run_start: int
    run_end: int
    run_value: int
    is_target: bool
    issues: tuple[str, ...]


@dataclass(frozen=True)
class SelectorSpec:
    family: str
    source_pool: str
    source_ref: int
    stride: int
    transform: str
    parameter: int = 0

    def label(self) -> str:
        suffix = self.transform if self.parameter == 0 else f"{self.transform}={self.parameter:02x}"
        if self.family == "source_slice":
            return f"{self.source_pool}@{self.source_ref}:slice:{self.stride}:{suffix}"
        if self.family == "source_repeat":
            return f"{self.source_pool}@{self.source_ref}:repeat:{suffix}"
        if self.family == "run_plus_source_delta":
            return f"run+{self.source_pool}@{self.source_ref}:{suffix}"
        return f"{self.family}:{self.source_pool}@{self.source_ref}:{suffix}"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8", errors="replace") as handle:
        return list(csv.DictReader(handle))


def load_bytes(path_text: str, issues: list[str], label: str) -> bytes:
    if not path_text:
        issues.append(f"missing_{label}_path")
        return b""
    try:
        return Path(path_text).read_bytes()
    except OSError as exc:
        issues.append(f"read_{label}_failed:{exc.__class__.__name__}")
        return b""


def fixture_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("archive", ""), row.get("pcx_name", ""), row.get("frontier_id", "")


def unknown_source_rows(slot_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        row
        for row in slot_rows
        if row.get("source_location") == "outside_highsafe"
        and row.get("source_availability") == "unknown_source"
        and row.get("source_expected_byte")
    ]


def target_group(rows: list[dict[str, str]]) -> tuple[tuple[str, str, str], list[dict[str, str]]]:
    groups: dict[tuple[str, str, str], list[dict[str, str]]] = {}
    for row in rows:
        groups.setdefault(fixture_key(row), []).append(row)
    if not groups:
        return ("", "", ""), []
    return max(groups.items(), key=lambda item: len(item[1]))


def byte_runs(data: bytes) -> list[tuple[int, int, int]]:
    if not data:
        return []
    runs: list[tuple[int, int, int]] = []
    start = 0
    current = data[0]
    for index, value in enumerate(data[1:], start=1):
        if value == current:
            continue
        runs.append((start, index, current))
        start = index
        current = value
    runs.append((start, len(data), current))
    return runs


def mask_bits(mask: bytes, start: int, end: int) -> str:
    return "".join("1" if 0 <= offset < len(mask) and mask[offset] else "0" for offset in range(start, end))


def pair_known(context: PairContext) -> bool:
    return all(0 <= offset < len(context.known_mask) and context.known_mask[offset] for offset in range(context.pair_start, context.run_start))


def pair_exact(context: PairContext) -> bool:
    return all(
        0 <= offset < len(context.decoded) and context.decoded[offset] == context.expected[offset]
        for offset in range(context.pair_start, context.run_start)
    )


def pair_bytes(context: PairContext) -> bytes:
    return context.expected[context.pair_start : context.run_start]


def pair_delta(context: PairContext) -> int | None:
    data = pair_bytes(context)
    if not data or len(set(data)) != 1 or context.run_value < 0:
        return None
    return (data[0] - context.run_value) & 0xFF


def transform_value(value: int, transform: str, parameter: int) -> int:
    if transform == "identity":
        return value
    if transform == "low7":
        return value & 0x7F
    if transform == "bit_not":
        return value ^ 0xFF
    if transform == "add_const":
        return (value + parameter) & 0xFF
    if transform == "sub_const":
        return (value - parameter) & 0xFF
    if transform == "xor_const":
        return value ^ parameter
    raise ValueError(f"unknown transform: {transform}")


def delta_value(value: int, transform: str) -> int:
    if transform == "low_nibble":
        return value & 0x0F
    if transform == "high_nibble":
        return value >> 4
    if transform == "low2":
        return value & 0x03
    if transform == "high2":
        return value >> 6
    if transform == "low3":
        return value & 0x07
    if transform == "signed_low_nibble":
        low = value & 0x0F
        return low - 16 if low >= 8 else low
    raise ValueError(f"unknown delta transform: {transform}")


def source_buffer(context: PairContext, pool: str) -> tuple[bytes, int]:
    if pool == "segment_abs":
        return context.segment, 0
    if pool == "control_abs":
        return context.control_prefix, 0
    if pool == "fragment_abs":
        return context.fragment, 0
    if pool == "segment_after_control":
        return context.segment, len(context.control_prefix)
    if pool == "segment_after_fragment":
        return context.segment, len(context.control_prefix) + len(context.fragment)
    if pool == "segment_pair_abs":
        return context.segment, context.pair_start
    if pool == "segment_run_abs":
        return context.segment, context.run_start
    raise ValueError(f"unknown source pool: {pool}")


def source_indexes(context: PairContext, spec: SelectorSpec, count: int) -> list[int] | None:
    data, base = source_buffer(context, spec.source_pool)
    start = base + spec.source_ref
    indexes = [start + index * spec.stride for index in range(count)]
    if any(index < 0 or index >= len(data) for index in indexes):
        return None
    return indexes


def selector_output(context: PairContext, spec: SelectorSpec) -> bytes | None:
    if context.pair_len <= 0:
        return None
    data, _base = source_buffer(context, spec.source_pool)
    if spec.family == "source_repeat":
        indexes = source_indexes(context, spec, 1)
        if indexes is None:
            return None
        value = transform_value(data[indexes[0]], spec.transform, spec.parameter)
        return bytes([value] * context.pair_len)
    if spec.family == "source_slice":
        indexes = source_indexes(context, spec, context.pair_len)
        if indexes is None:
            return None
        return bytes(transform_value(data[index], spec.transform, spec.parameter) for index in indexes)
    if spec.family == "run_plus_source_delta":
        indexes = source_indexes(context, spec, 1)
        if indexes is None or context.run_value < 0:
            return None
        delta = delta_value(data[indexes[0]], spec.transform)
        value = (context.run_value + delta) & 0xFF
        return bytes([value] * context.pair_len)
    raise ValueError(f"unknown selector family: {spec.family}")


def transforms() -> list[tuple[str, int]]:
    rows = list(SIMPLE_TRANSFORMS)
    for constant in SMALL_CONSTANTS:
        rows.append(("add_const", constant))
        rows.append(("sub_const", constant))
        rows.append(("xor_const", constant))
    return rows


def selector_specs() -> list[SelectorSpec]:
    specs: list[SelectorSpec] = []
    pools = [
        ("segment_abs", range(0, 40)),
        ("control_abs", range(0, 16)),
        ("fragment_abs", range(0, 8)),
        ("segment_after_control", range(-8, 32)),
        ("segment_after_fragment", range(-8, 32)),
        ("segment_pair_abs", range(-8, 9)),
        ("segment_run_abs", range(-8, 9)),
    ]
    for pool, offsets in pools:
        for offset in offsets:
            for transform, parameter in transforms():
                specs.append(SelectorSpec("source_repeat", pool, offset, 1, transform, parameter))
            for stride in (-2, -1, 1, 2):
                for transform, parameter in transforms():
                    specs.append(SelectorSpec("source_slice", pool, offset, stride, transform, parameter))
            for transform in DELTA_TRANSFORMS:
                specs.append(SelectorSpec("run_plus_source_delta", pool, offset, 1, transform, 0))
    return specs


def load_pair_contexts(
    *,
    manifest_rows: list[dict[str, str]],
    base_rows: list[dict[str, str]],
    target_key_value: tuple[str, str, str],
    target_pair_start: int,
    target_pair_len: int,
    min_run_length: int,
) -> tuple[list[PairContext], list[str]]:
    manifests = {fixture_key(row): row for row in manifest_rows}
    contexts: list[PairContext] = []
    issues: list[str] = []
    for base_row in base_rows:
        key = fixture_key(base_row)
        manifest = manifests.get(key, {})
        if manifest.get("rule_type") != "compact_control_stream":
            continue
        local_issues: list[str] = []
        expected = load_bytes(manifest.get("expected_gap_path", ""), local_issues, "expected")
        decoded = load_bytes(base_row.get("decoded_path", ""), local_issues, "decoded")
        known_mask = load_bytes(base_row.get("known_mask_path", ""), local_issues, "known_mask")
        segment = load_bytes(manifest.get("segment_gap_path", ""), local_issues, "segment")
        control_prefix = load_bytes(manifest.get("control_prefix_path", ""), local_issues, "control_prefix")
        fragment = load_bytes(manifest.get("fragment_path", ""), local_issues, "fragment")
        if local_issues:
            issues.extend(f"{'|'.join(key)}:{issue}" for issue in local_issues)
        if not expected or not decoded or not known_mask or not segment:
            continue
        for run_start, run_end, run_value in byte_runs(expected):
            run_length = run_end - run_start
            if run_length < min_run_length or run_start < target_pair_len:
                continue
            pair_start = run_start - target_pair_len
            pair = expected[pair_start:run_start]
            if len(pair) != target_pair_len or len(set(pair)) != 1:
                continue
            contexts.append(
                PairContext(
                    row=base_row,
                    expected=expected,
                    decoded=decoded,
                    known_mask=known_mask,
                    segment=segment,
                    control_prefix=control_prefix,
                    fragment=fragment,
                    pair_start=pair_start,
                    pair_len=target_pair_len,
                    run_start=run_start,
                    run_end=run_end,
                    run_value=run_value,
                    is_target=key == target_key_value and pair_start == target_pair_start,
                    issues=tuple(local_issues),
                )
            )
    return contexts, issues


def context_id(context: PairContext) -> str:
    key = fixture_key(context.row)
    return f"{key[1]}:{key[2]}:{context.pair_start}"


def build_pair_rows(contexts: list[PairContext], target_delta: int | None) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for rank, context in enumerate(contexts, start=1):
        data = pair_bytes(context)
        delta = pair_delta(context)
        rows.append(
            {
                "rank": str(rank),
                "archive": context.row.get("archive", ""),
                "archive_tag": context.row.get("archive_tag", ""),
                "pcx_name": context.row.get("pcx_name", ""),
                "frontier_id": context.row.get("frontier_id", ""),
                "pair_offset": str(context.pair_start),
                "pair_hex": data.hex(),
                "known_pair_bits": mask_bits(context.known_mask, context.pair_start, context.run_start),
                "decoded_pair_hex": context.decoded[context.pair_start : context.run_start].hex(),
                "run_start": str(context.run_start),
                "run_end": str(context.run_end),
                "run_length": str(context.run_end - context.run_start),
                "run_value": f"{context.run_value:02x}",
                "delta": "" if delta is None else str(delta),
                "delta_hex": "" if delta is None else f"{delta:02x}",
                "control_prefix_bytes": str(len(context.control_prefix)),
                "fragment_bytes": str(len(context.fragment)),
                "segment_gap_bytes": str(len(context.segment)),
                "control_prefix_hex": context.control_prefix[:32].hex(),
                "fragment_hex": context.fragment[:32].hex(),
                "segment_head_hex": context.segment[:48].hex(),
                "is_target": "1" if context.is_target else "0",
                "issues": "" if delta == target_delta or target_delta is None else "other_delta",
            }
        )
    rows.sort(
        key=lambda row: (
            row.get("is_target") != "1",
            row.get("delta") != ("" if target_delta is None else str(target_delta)),
            row.get("pcx_name", ""),
            int_value(row, "frontier_id"),
            int_value(row, "pair_offset"),
        )
    )
    for rank, row in enumerate(rows, start=1):
        row["rank"] = str(rank)
    return rows


def byte_exact(left: bytes, right: bytes) -> int:
    return sum(1 for left_value, right_value in zip(left, right) if left_value == right_value)


def selector_verdict(target_full: bool, known_exact: int, known_false: int) -> str:
    if not target_full:
        return "partial_target_match"
    if known_exact >= 2 and known_false == 0:
        return "guarded_token_support"
    if known_exact == 1 and known_false == 0:
        return "weak_guarded_token_support"
    if known_exact == 0 and known_false == 0:
        return "unsupported_target_token"
    return "rejected_known_false"


def evaluate_selectors(contexts: list[PairContext], target_delta: int | None) -> list[dict[str, str]]:
    target_contexts = [context for context in contexts if context.is_target]
    if not target_contexts:
        return []
    rows: list[dict[str, str]] = []
    for spec in selector_specs():
        target_outputs: list[bytes] = []
        target_exact = 0
        target_full = True
        target_samples: list[str] = []
        known_exact_samples: list[str] = []
        known_false_samples: list[str] = []
        known_exact = known_false = known_miss = 0
        same_delta_full = same_delta_known_exact = same_delta_unknown_full = 0

        for context in contexts:
            expected = pair_bytes(context)
            output = selector_output(context, spec)
            if output is None:
                if pair_known(context):
                    known_miss += 1
                continue
            full = output == expected
            delta = pair_delta(context)
            if context.is_target:
                target_outputs.append(output)
                target_exact += byte_exact(output, expected)
                target_full = target_full and full
                target_samples.append(context_id(context))
            elif pair_known(context):
                if full and pair_exact(context):
                    known_exact += 1
                    if len(known_exact_samples) < 8:
                        known_exact_samples.append(context_id(context))
                else:
                    known_false += 1
                    if len(known_false_samples) < 8:
                        known_false_samples.append(context_id(context))
            if target_delta is not None and delta == target_delta and full:
                same_delta_full += 1
                if pair_known(context):
                    same_delta_known_exact += 1
                else:
                    same_delta_unknown_full += 1

        if not target_outputs or target_exact <= 0:
            continue
        expected_hex = ";".join(pair_bytes(context).hex() for context in target_contexts)
        output_hex = ";".join(output.hex() for output in target_outputs)
        verdict = selector_verdict(target_full, known_exact, known_false)
        rows.append(
            {
                "rank": "",
                "selector": spec.label(),
                "family": spec.family,
                "source_pool": spec.source_pool,
                "source_ref": str(spec.source_ref),
                "stride": str(spec.stride),
                "transform": spec.transform,
                "parameter": "" if spec.parameter == 0 else f"{spec.parameter:02x}",
                "target_output_hex": output_hex,
                "target_expected_hex": expected_hex,
                "target_exact_bytes": str(target_exact),
                "target_full_match": "1" if target_full else "0",
                "known_exact_rows": str(known_exact),
                "known_false_rows": str(known_false),
                "known_miss_rows": str(known_miss),
                "same_delta_full_rows": str(same_delta_full),
                "same_delta_known_exact_rows": str(same_delta_known_exact),
                "same_delta_unknown_full_rows": str(same_delta_unknown_full),
                "verdict": verdict,
                "known_exact_samples": ";".join(known_exact_samples),
                "known_false_samples": ";".join(known_false_samples),
                "target_samples": ";".join(target_samples),
            }
        )
    rows.sort(
        key=lambda row: (
            row.get("verdict") != "guarded_token_support",
            row.get("verdict") != "weak_guarded_token_support",
            row.get("verdict") != "unsupported_target_token",
            row.get("target_full_match") != "1",
            -int_value(row, "target_exact_bytes"),
            int_value(row, "known_false_rows"),
            -int_value(row, "known_exact_rows"),
            row.get("selector", ""),
        )
    )
    rows = rows[:2000]
    for rank, row in enumerate(rows, start=1):
        row["rank"] = str(rank)
    return rows


def best_selector(candidate_rows: list[dict[str, str]]) -> dict[str, str]:
    return candidate_rows[0] if candidate_rows else {}


def build_target_rows(delta_targets: list[dict[str, str]], best: dict[str, str]) -> list[dict[str, str]]:
    verdict = best.get("verdict", "")
    promotion_ready = "1" if verdict == "guarded_token_support" else "0"
    issue = "" if promotion_ready == "1" else (verdict or "missing_compact_token_selector")
    rows: list[dict[str, str]] = []
    for target in delta_targets:
        rows.append(
            {
                "rank": target.get("rank", str(len(rows) + 1)),
                "slot_rank": target.get("slot_rank", ""),
                "archive": target.get("archive", ""),
                "archive_tag": target.get("archive_tag", ""),
                "pcx_name": target.get("pcx_name", ""),
                "frontier_id": target.get("frontier_id", ""),
                "target_offset": target.get("target_offset", ""),
                "source_offset": target.get("source_offset", ""),
                "expected_byte": target.get("expected_byte", ""),
                "predicted_byte": target.get("expected_byte", ""),
                "best_selector": best.get("selector", ""),
                "best_formula": "compact_control_token_selector",
                "best_guard_family": best.get("family", ""),
                "best_guard_key": best.get("selector", ""),
                "promotion_ready": promotion_ready,
                "issues": issue,
            }
        )
    return rows


def build_summary(
    *,
    contexts: list[PairContext],
    candidates: list[dict[str, str]],
    target_rows: list[dict[str, str]],
    target_key_value: tuple[str, str, str],
    issue_rows: int,
) -> dict[str, str]:
    target_context = next((context for context in contexts if context.is_target), None)
    target_delta = pair_delta(target_context) if target_context else None
    target_pair_hex = pair_bytes(target_context).hex() if target_context else ""
    same_delta_rows = sum(1 for context in contexts if target_delta is not None and pair_delta(context) == target_delta)
    known_pair_rows = sum(1 for context in contexts if pair_known(context))
    target_full = [row for row in candidates if row.get("target_full_match") == "1"]
    guarded = [row for row in candidates if row.get("verdict") == "guarded_token_support"]
    weak_guarded = [row for row in candidates if row.get("verdict") == "weak_guarded_token_support"]
    unsupported = [row for row in candidates if row.get("verdict") == "unsupported_target_token"]
    rejected = [row for row in candidates if row.get("verdict") == "rejected_known_false"]
    best = best_selector(candidates)
    ready = sum(1 for row in target_rows if row.get("promotion_ready") == "1")
    if ready:
        verdict = "frontier80_tail_compact_token_support_ready"
        next_probe = "promote compact-control token selector for frontier80 offsets 16-17"
    elif weak_guarded:
        verdict = "frontier80_tail_compact_token_weak_support"
        next_probe = "seek second independent compact-control token support row for frontier80 pre-run pair"
    elif unsupported:
        verdict = "frontier80_tail_compact_token_target_only"
        next_probe = "inspect bit-level compact-control token producer for frontier80 pre-run pair"
    else:
        verdict = "frontier80_tail_compact_token_rejected"
        next_probe = "expand compact-control token selector families beyond segment/control windows"
    return {
        "scope": "total",
        "candidate_mode": "old_clean_byte_union_frontier80_tail_compact_token_review",
        "target_key": "|".join(target_key_value),
        "target_pair_offset": str(target_context.pair_start) if target_context else "",
        "target_pair_hex": target_pair_hex,
        "target_run_value": f"{target_context.run_value:02x}" if target_context else "",
        "target_run_start": str(target_context.run_start) if target_context else "",
        "target_run_end": str(target_context.run_end) if target_context else "",
        "target_delta": "" if target_delta is None else str(target_delta),
        "pair_rows": str(len(contexts)),
        "known_pair_rows": str(known_pair_rows),
        "same_delta_rows": str(same_delta_rows),
        "selector_rows": str(len(candidates)),
        "target_full_selector_rows": str(len(target_full)),
        "guarded_selector_rows": str(len(guarded)),
        "weak_guarded_selector_rows": str(len(weak_guarded)),
        "unsupported_selector_rows": str(len(unsupported)),
        "rejected_selector_rows": str(len(rejected)),
        "best_selector": best.get("selector", ""),
        "best_family": best.get("family", ""),
        "best_source_pool": best.get("source_pool", ""),
        "best_target_output_hex": best.get("target_output_hex", ""),
        "best_known_exact_rows": best.get("known_exact_rows", "0"),
        "best_known_false_rows": best.get("known_false_rows", "0"),
        "best_verdict": best.get("verdict", ""),
        "best_known_exact_samples": best.get("known_exact_samples", ""),
        "best_known_false_samples": best.get("known_false_samples", ""),
        "review_verdict": verdict,
        "next_probe": next_probe,
        "promotion_candidate_bytes": str(len(target_rows)),
        "promotion_ready_bytes": str(ready),
        "issue_rows": str(issue_rows),
    }


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 160) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    candidates: list[dict[str, str]],
    pairs: list[dict[str, str]],
    targets: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "candidates": candidates, "pairs": pairs, "targets": targets}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("candidates.csv", output_dir / "candidates.csv"),
            ("pairs.csv", output_dir / "pairs.csv"),
            ("targets.csv", output_dir / "targets.csv"),
        )
    )
    return f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <title>{html.escape(title)}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 24px; background: #f6f7f8; color: #202529; }}
    .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 10px; margin: 18px 0; }}
    .stat {{ background: white; border: 1px solid #d5dbe0; padding: 10px; }}
    .label {{ color: #68737d; font-size: 12px; }}
    .value {{ font-size: 20px; font-weight: 750; overflow-wrap: anywhere; }}
    table {{ border-collapse: collapse; width: 100%; background: white; margin: 18px 0; }}
    th, td {{ border: 1px solid #d5dbe0; padding: 6px 8px; font-size: 13px; text-align: left; vertical-align: top; }}
    th {{ background: #e9edf0; }}
  </style>
</head>
<body>
  <h1>{html.escape(title)}</h1>
  <p>{links}</p>
  <div class="stats">
    <div class="stat"><div class="label">Verdict</div><div class="value">{html.escape(summary['review_verdict'])}</div></div>
    <div class="stat"><div class="label">Best selector</div><div class="value">{html.escape(summary['best_selector'])}</div></div>
    <div class="stat"><div class="label">Known exact/false</div><div class="value">{html.escape(summary['best_known_exact_rows'])}/{html.escape(summary['best_known_false_rows'])}</div></div>
    <div class="stat"><div class="label">Promotion ready</div><div class="value">{html.escape(summary['promotion_ready_bytes'])}</div></div>
  </div>
  <h2>Targets</h2>
  {render_table(targets, TARGET_FIELDNAMES)}
  <h2>Selectors</h2>
  {render_table(candidates, CANDIDATE_FIELDNAMES)}
  <h2>Pairs</h2>
  {render_table(pairs, PAIR_FIELDNAMES)}
  <script type="application/json" id="payload">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slots", type=Path, default=DEFAULT_SLOTS)
    parser.add_argument("--base-fixtures", type=Path, default=DEFAULT_BASE_FIXTURES)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--delta-targets", type=Path, default=DEFAULT_DELTA_TARGETS)
    parser.add_argument("--min-run-length", type=int, default=4)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Frontier80 Tail Compact Token Review")
    args = parser.parse_args()

    slot_rows = read_csv(args.slots)
    unknown_rows = unknown_source_rows(slot_rows)
    target_key_value, target_members = target_group(unknown_rows)
    target_offsets = sorted({int_value(row, "source_actual_offset", -1) for row in target_members})
    target_offsets = [offset for offset in target_offsets if offset >= 0]
    target_pair_start = min(target_offsets) if target_offsets else -1
    target_pair_len = len(target_offsets)
    contexts, issues = load_pair_contexts(
        manifest_rows=read_csv(args.manifest),
        base_rows=read_csv(args.base_fixtures),
        target_key_value=target_key_value,
        target_pair_start=target_pair_start,
        target_pair_len=target_pair_len,
        min_run_length=args.min_run_length,
    )
    target_context = next((context for context in contexts if context.is_target), None)
    target_delta = pair_delta(target_context) if target_context else None
    pairs = build_pair_rows(contexts, target_delta)
    candidates = evaluate_selectors(contexts, target_delta)
    targets = build_target_rows(read_csv(args.delta_targets), best_selector(candidates))
    summary = build_summary(
        contexts=contexts,
        candidates=candidates,
        target_rows=targets,
        target_key_value=target_key_value,
        issue_rows=len(issues),
    )

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "candidates.csv", CANDIDATE_FIELDNAMES, candidates)
    write_csv(args.output / "pairs.csv", PAIR_FIELDNAMES, pairs)
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, targets)
    (args.output / "index.html").write_text(
        build_html(summary, candidates, pairs, targets, args.output, args.title),
        encoding="utf-8",
    )

    print(
        "Frontier80 compact token review: "
        f"verdict={summary['review_verdict']} "
        f"best={summary['best_selector']} "
        f"known={summary['best_known_exact_rows']}/{summary['best_known_false_rows']} "
        f"promotion_ready={summary['promotion_ready_bytes']}"
    )
    print(f"HTML: {args.output / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
