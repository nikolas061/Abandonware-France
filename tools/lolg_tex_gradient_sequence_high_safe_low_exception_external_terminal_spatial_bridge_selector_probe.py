#!/usr/bin/env python3
"""Probe non-oracle selectors for external terminal spatial bridge signatures."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
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


DEFAULT_TARGETS = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_selector/targets.csv"
)
DEFAULT_SMALL_GAPS = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_selector/small_gaps.csv"
)
DEFAULT_FIXTURES = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_cover_second_promoted_replay/fixtures.csv"
)
DEFAULT_OUTPUT = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_selector"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "target_spans",
    "target_bytes",
    "known_reference_rows",
    "target_candidate_rows",
    "known_candidate_rows",
    "selector_group_rows",
    "non_oracle_group_rows",
    "guarded_selector_rows",
    "target_guarded_exact_bytes",
    "target_guarded_weak_bytes",
    "frontier80_guarded_exact_bytes",
    "frontier80_target_only_unique_bytes",
    "target_only_unique_bytes",
    "best_target_span",
    "best_selector_family",
    "best_selector_key",
    "best_selector_verdict",
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
    "anchor_side",
    "anchor_rel",
    "anchor_edge",
    "anchor_byte",
    "delta_signature",
    "selector_family",
    "selector_guard",
    "selector_key",
    "known_rows",
    "known_spans",
    "known_signatures",
    "predicted_delta_signature",
    "predicted_output_hex",
    "exact_bytes",
    "selector_verdict",
    "promotion_candidate",
    "promotion_ready",
    "issues",
]

SELECTOR_FIELDNAMES = [
    "rank",
    "selector_family",
    "selector_guard",
    "promotion_guard",
    "selector_key",
    "target_spans",
    "target_bytes",
    "target_signatures",
    "known_rows",
    "known_spans",
    "known_bytes",
    "known_signatures",
    "predicted_delta_signature",
    "exact_target_spans",
    "exact_target_bytes",
    "weak_exact_target_bytes",
    "frontier80_exact_bytes",
    "verdict",
    "sample_targets",
    "sample_known_spans",
]

CANDIDATE_FIELDNAMES = [
    "rank",
    "scope",
    "archive",
    "span_key",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "span_start",
    "span_end",
    "span_length",
    "gap_role",
    "op_pair",
    "prev_op_kind",
    "prev_op_length",
    "next_op_kind",
    "next_op_length",
    "prev_tail1",
    "prev_tail2",
    "next_head1",
    "next_head2",
    "control_ref_mod64",
    "control_head4",
    "control_tail4",
    "anchor_side",
    "anchor_rel",
    "anchor_abs_mod64",
    "anchor_edge",
    "anchor_byte",
    "delta_signature",
    "output_hex",
    "expected_hex",
]


@dataclass(frozen=True)
class SelectorSpec:
    name: str
    fields: tuple[str, ...]
    guard: str
    promotion_guard: bool


SELECTOR_SPECS = [
    SelectorSpec(
        "literal_edge_anchor",
        ("gap_role", "span_length", "op_pair", "anchor_edge", "anchor_byte"),
        "non_oracle",
        True,
    ),
    SelectorSpec(
        "literal_edge_control_mod_anchor",
        ("gap_role", "span_length", "op_pair", "control_ref_mod64", "anchor_edge", "anchor_byte"),
        "non_oracle",
        True,
    ),
    SelectorSpec(
        "op_length_anchor",
        (
            "gap_role",
            "span_length",
            "prev_op_kind",
            "prev_op_length",
            "next_op_kind",
            "next_op_length",
            "anchor_side",
            "anchor_rel",
            "anchor_byte",
        ),
        "non_oracle",
        True,
    ),
    SelectorSpec(
        "literal_neighbor_anchor",
        ("gap_role", "span_length", "prev_tail2", "next_head2", "anchor_edge", "anchor_byte"),
        "non_oracle",
        True,
    ),
    SelectorSpec(
        "control_mod_anchor",
        ("gap_role", "span_length", "control_ref_mod64", "anchor_side", "anchor_rel", "anchor_byte"),
        "non_oracle",
        True,
    ),
    SelectorSpec(
        "control_window_anchor",
        ("gap_role", "span_length", "control_head4", "control_tail4", "anchor_side", "anchor_rel", "anchor_byte"),
        "stream_exact",
        False,
    ),
    SelectorSpec(
        "frontier_literal_edge_anchor",
        ("archive_tag", "pcx_name", "frontier_id", "gap_role", "span_length", "anchor_edge", "anchor_byte"),
        "identity_diagnostic",
        False,
    ),
]


def hex_head(value: str, byte_count: int) -> str:
    if not value:
        return "."
    return value[: byte_count * 2] or "."


def hex_tail(value: str, byte_count: int) -> str:
    if not value:
        return "."
    return value[-byte_count * 2 :] or "."


def span_start(row: dict[str, str]) -> int:
    return int_value(row, "expected_start", int_value(row, "span_start"))


def span_end(row: dict[str, str]) -> int:
    return int_value(row, "expected_end", int_value(row, "span_end"))


def span_length(row: dict[str, str]) -> int:
    length = int_value(row, "length", int_value(row, "span_length"))
    if length > 0:
        return length
    return max(0, span_end(row) - span_start(row))


def bridge_output_hex(anchor_hex: str, delta_signature: str) -> str:
    if not anchor_hex or not delta_signature:
        return ""
    try:
        anchor = int(anchor_hex, 16)
        deltas = [int(part) for part in delta_signature.split(",") if part != ""]
    except ValueError:
        return ""
    return bytes((anchor + delta) & 0xFF for delta in deltas).hex()


def anchor_edge(row: dict[str, str], signature: dict[str, str]) -> str:
    start = span_start(row)
    end = span_end(row)
    offset = int_value(signature, "anchor_offset", -1)
    if offset < 0:
        return "."
    prev_length = int_value(row, "prev_op_length")
    next_length = int_value(row, "next_op_length")
    prev_kind = row.get("prev_op_kind", "")
    next_kind = row.get("next_op_kind", "")
    if prev_kind == "literal" and start - prev_length <= offset < start:
        return f"prev_literal:{offset - (start - prev_length)}"
    if next_kind == "literal" and end <= offset < end + next_length:
        return f"next_literal:{offset - end}"
    rel = offset - start
    return f"{'left' if rel < 0 else 'right'}_rel:{rel}"


def enrich_candidate(row: dict[str, str], signature: dict[str, str], scope: str) -> dict[str, str]:
    start = span_start(row)
    end = span_end(row)
    length = span_length(row)
    delta_signature = signature.get("delta_signature", "")
    anchor_hex = signature.get("anchor_byte", "")
    output_hex = bridge_output_hex(anchor_hex, delta_signature)
    prev_kind = row.get("prev_op_kind", "")
    next_kind = row.get("next_op_kind", "")
    candidate = {
        "scope": scope,
        "archive": row.get("archive", ""),
        "archive_tag": row.get("archive_tag", ""),
        "pcx_name": row.get("pcx_name", ""),
        "frontier_id": row.get("frontier_id", ""),
        "span_key": row.get("span_key", ""),
        "span_start": str(start),
        "span_end": str(end),
        "span_length": str(length),
        "expected_hex": row.get("expected_hex", ""),
        "gap_role": row.get("gap_role", ""),
        "prev_op_kind": prev_kind or ".",
        "prev_op_length": row.get("prev_op_length", "") or ".",
        "next_op_kind": next_kind or ".",
        "next_op_length": row.get("next_op_length", "") or ".",
        "op_pair": f"{prev_kind or '.'}->{next_kind or '.'}",
        "prev_tail1": hex_tail(row.get("prev_expected_hex", ""), 1),
        "prev_tail2": hex_tail(row.get("prev_expected_hex", ""), 2),
        "next_head1": hex_head(row.get("next_expected_hex", ""), 1),
        "next_head2": hex_head(row.get("next_expected_hex", ""), 2),
        "control_ref_mod64": row.get("control_ref_mod64", "") or str(int_value(row, "control_ref_offset") % 64),
        "control_head4": row.get("control_head4", "") or ".",
        "control_tail4": row.get("control_tail4", "") or ".",
        "anchor_side": signature.get("anchor_side", ""),
        "anchor_rel": signature.get("anchor_rel", ""),
        "anchor_abs_mod64": str(int_value(signature, "anchor_offset") % 64),
        "anchor_edge": anchor_edge(row, signature),
        "anchor_byte": anchor_hex,
        "delta_signature": delta_signature,
        "output_hex": output_hex,
    }
    return candidate


def selector_key(candidate: dict[str, str], spec: SelectorSpec) -> str:
    return "|".join(f"{field}={candidate.get(field, '.') or '.'}" for field in spec.fields)


def unique_span_bytes(candidates: list[dict[str, str]]) -> int:
    seen: set[str] = set()
    total = 0
    for candidate in candidates:
        span_key = candidate.get("span_key", "")
        if span_key in seen:
            continue
        seen.add(span_key)
        total += int_value(candidate, "span_length")
    return total


def unique_span_count(candidates: list[dict[str, str]]) -> int:
    return len({candidate.get("span_key", "") for candidate in candidates})


def signature_summary(candidates: list[dict[str, str]]) -> str:
    counts = Counter(candidate.get("delta_signature", "") for candidate in candidates)
    return ";".join(f"{signature}:{count}" for signature, count in sorted(counts.items()))


def target_signature_summary(candidates: list[dict[str, str]]) -> str:
    spans: dict[str, set[str]] = defaultdict(set)
    for candidate in candidates:
        spans[candidate.get("delta_signature", "")].add(candidate.get("span_key", ""))
    return ";".join(f"{signature}:{len(keys)}" for signature, keys in sorted(spans.items()))


def build_candidates(
    rows: list[dict[str, str]],
    buffers: dict[tuple[str, str, str], tuple[bytes, bytes]],
    *,
    scope: str,
    max_distance: int,
    max_delta: int,
) -> tuple[list[dict[str, str]], list[str]]:
    candidates: list[dict[str, str]] = []
    issues: list[str] = []
    for row in rows:
        buffer = buffers.get(row_key(row))
        if buffer is None:
            issues.append(f"{row.get('span_key', '')}:missing_replay_buffer")
            continue
        decoded, known_mask = buffer
        signatures = anchor_signatures(row, decoded, known_mask, max_distance=max_distance, max_delta=max_delta)
        if not signatures:
            issues.append(f"{row.get('span_key', '')}:missing_anchor_signature")
        for signature in signatures:
            candidates.append(enrich_candidate(row, signature, scope))
    return candidates, issues


def selector_rows_for(
    target_candidates: list[dict[str, str]],
    known_candidates: list[dict[str, str]],
) -> tuple[list[dict[str, str]], dict[tuple[str, str], dict[str, str]]]:
    rows: list[dict[str, str]] = []
    lookup: dict[tuple[str, str], dict[str, str]] = {}
    all_candidates = known_candidates + target_candidates
    for spec in SELECTOR_SPECS:
        grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
        for candidate in all_candidates:
            grouped[selector_key(candidate, spec)].append(candidate)
        for key, group_candidates in grouped.items():
            known = [candidate for candidate in group_candidates if candidate.get("scope") == "known"]
            targets = [candidate for candidate in group_candidates if candidate.get("scope") == "target"]
            if not known and not targets:
                continue
            known_signatures = Counter(candidate.get("delta_signature", "") for candidate in known)
            predicted = next(iter(known_signatures)) if len(known_signatures) == 1 else ""
            exact_targets = [
                candidate for candidate in targets if predicted and candidate.get("delta_signature", "") == predicted
            ]
            weak_exact_targets = [
                candidate for candidate in exact_targets if int_value(candidate, "span_length") <= 1
            ]
            target_signatures = {candidate.get("delta_signature", "") for candidate in targets}
            if len(known_signatures) > 1:
                verdict = "known_conflict"
            elif exact_targets:
                verdict = "guarded_exact"
            elif known and targets:
                verdict = "known_prediction_mismatch"
            elif not known and targets and len(target_signatures) == 1:
                verdict = "target_only_unique"
            elif not known and targets:
                verdict = "target_only_conflict"
            else:
                verdict = "known_only"
            row = {
                "rank": "",
                "selector_family": spec.name,
                "selector_guard": spec.guard,
                "promotion_guard": "1" if spec.promotion_guard else "0",
                "selector_key": key,
                "target_spans": str(unique_span_count(targets)),
                "target_bytes": str(unique_span_bytes(targets)),
                "target_signatures": target_signature_summary(targets),
                "known_rows": str(len(known)),
                "known_spans": str(unique_span_count(known)),
                "known_bytes": str(unique_span_bytes(known)),
                "known_signatures": signature_summary(known),
                "predicted_delta_signature": predicted,
                "exact_target_spans": str(unique_span_count(exact_targets)),
                "exact_target_bytes": str(unique_span_bytes(exact_targets)),
                "weak_exact_target_bytes": str(unique_span_bytes(weak_exact_targets)),
                "frontier80_exact_bytes": str(
                    unique_span_bytes([candidate for candidate in exact_targets if candidate.get("frontier_id") == "80"])
                ),
                "verdict": verdict,
                "sample_targets": ";".join(sorted({candidate.get("span_key", "") for candidate in targets})[:8]),
                "sample_known_spans": ";".join(sorted({candidate.get("span_key", "") for candidate in known})[:8]),
            }
            rows.append(row)
            lookup[(spec.name, key)] = row
    rows.sort(
        key=lambda row: (
            row.get("verdict") not in {"guarded_exact", "target_only_unique"},
            -int_value(row, "exact_target_bytes"),
            -int_value(row, "target_bytes"),
            -int_value(row, "known_spans"),
            row.get("selector_guard", ""),
            row.get("selector_family", ""),
            row.get("selector_key", ""),
        )
    )
    for index, row in enumerate(rows, start=1):
        row["rank"] = str(index)
    return rows, lookup


def target_best_rows(
    target_rows: list[dict[str, str]],
    target_candidates: list[dict[str, str]],
    selector_lookup: dict[tuple[str, str], dict[str, str]],
) -> list[dict[str, str]]:
    candidates_by_span: dict[str, list[dict[str, str]]] = defaultdict(list)
    for candidate in target_candidates:
        candidates_by_span[candidate.get("span_key", "")].append(candidate)

    output_rows: list[dict[str, str]] = []
    for index, row in enumerate(target_rows, start=1):
        span_key = row.get("span_key", "")
        ranked_rows: list[tuple[tuple[int, ...], dict[str, str]]] = []
        for candidate in candidates_by_span.get(span_key, []):
            for spec_index, spec in enumerate(SELECTOR_SPECS):
                key = selector_key(candidate, spec)
                selector = selector_lookup.get((spec.name, key))
                if not selector:
                    continue
                predicted = selector.get("predicted_delta_signature", "")
                exact = bool(predicted and predicted == candidate.get("delta_signature", ""))
                weak = int_value(candidate, "span_length") <= 1
                target_only = selector.get("verdict") == "target_only_unique"
                promotion_candidate = (
                    spec.promotion_guard
                    and exact
                    and int_value(selector, "known_spans") > 0
                    and selector.get("verdict") == "guarded_exact"
                )
                promotion_ready = promotion_candidate and not weak
                score = (
                    1 if promotion_ready else 0,
                    1 if promotion_candidate else 0,
                    1 if exact else 0,
                    1 if target_only and candidate.get("frontier_id") == "80" else 0,
                    1 if target_only else 0,
                    1 if spec.guard == "non_oracle" else 0,
                    int_value(selector, "known_spans"),
                    -spec_index,
                )
                ranked_rows.append((score, {**candidate, "selector": selector, "spec": spec, "selector_key": key}))
        if ranked_rows:
            _, best = max(ranked_rows, key=lambda item: item[0])
            selector = best["selector"]
            spec = best["spec"]
            predicted = selector.get("predicted_delta_signature", "")
            exact = bool(predicted and predicted == best.get("delta_signature", ""))
            weak = int_value(best, "span_length") <= 1
            promotion_candidate = (
                spec.promotion_guard
                and exact
                and int_value(selector, "known_spans") > 0
                and selector.get("verdict") == "guarded_exact"
            )
            promotion_ready = promotion_candidate and not weak
            issues = ""
            if selector.get("verdict") == "target_only_unique":
                issues = "target_only_no_known_guard"
            elif weak and promotion_candidate:
                issues = "weak_single_byte_guard"
            output_rows.append(
                {
                    "rank": str(index),
                    "archive": row.get("archive", ""),
                    "archive_tag": row.get("archive_tag", ""),
                    "pcx_name": row.get("pcx_name", ""),
                    "frontier_id": row.get("frontier_id", ""),
                    "span_key": span_key,
                    "span_start": str(span_start(row)),
                    "span_end": str(span_end(row)),
                    "span_length": str(span_length(row)),
                    "expected_hex": row.get("expected_hex", ""),
                    "gap_role": row.get("gap_role", ""),
                    "anchor_side": best.get("anchor_side", ""),
                    "anchor_rel": best.get("anchor_rel", ""),
                    "anchor_edge": best.get("anchor_edge", ""),
                    "anchor_byte": best.get("anchor_byte", ""),
                    "delta_signature": best.get("delta_signature", ""),
                    "selector_family": spec.name,
                    "selector_guard": spec.guard,
                    "selector_key": best.get("selector_key", ""),
                    "known_rows": selector.get("known_rows", "0"),
                    "known_spans": selector.get("known_spans", "0"),
                    "known_signatures": selector.get("known_signatures", ""),
                    "predicted_delta_signature": predicted,
                    "predicted_output_hex": bridge_output_hex(best.get("anchor_byte", ""), predicted),
                    "exact_bytes": str(int_value(best, "span_length") if exact else 0),
                    "selector_verdict": selector.get("verdict", ""),
                    "promotion_candidate": "1" if promotion_candidate else "0",
                    "promotion_ready": "1" if promotion_ready else "0",
                    "issues": issues,
                }
            )
            continue
        output_rows.append(
            {
                "rank": str(index),
                "archive": row.get("archive", ""),
                "archive_tag": row.get("archive_tag", ""),
                "pcx_name": row.get("pcx_name", ""),
                "frontier_id": row.get("frontier_id", ""),
                "span_key": span_key,
                "span_start": str(span_start(row)),
                "span_end": str(span_end(row)),
                "span_length": str(span_length(row)),
                "expected_hex": row.get("expected_hex", ""),
                "gap_role": row.get("gap_role", ""),
                "anchor_side": "",
                "anchor_rel": "",
                "anchor_edge": "",
                "anchor_byte": "",
                "delta_signature": "",
                "selector_family": "",
                "selector_guard": "",
                "selector_key": "",
                "known_rows": "0",
                "known_spans": "0",
                "known_signatures": "",
                "predicted_delta_signature": "",
                "predicted_output_hex": "",
                "exact_bytes": "0",
                "selector_verdict": "missing_selector_candidate",
                "promotion_candidate": "0",
                "promotion_ready": "0",
                "issues": "missing_selector_candidate",
            }
        )
    return output_rows


def build(
    target_rows_in: list[dict[str, str]],
    small_gap_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    *,
    max_distance: int,
    max_delta: int,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    buffers, buffer_issues = load_buffers(fixture_rows)
    target_keys = {row.get("span_key", "") for row in target_rows_in}
    target_lookup = {row.get("span_key", ""): row for row in small_gap_rows if row.get("span_key", "") in target_keys}
    target_rows = [target_lookup.get(row.get("span_key", ""), row) for row in target_rows_in]
    known_rows = [row for row in small_gap_rows if row.get("known_in_replay") == "1"]

    known_candidates, _known_issues = build_candidates(
        known_rows,
        buffers,
        scope="known",
        max_distance=max_distance,
        max_delta=max_delta,
    )
    target_candidates, target_issues = build_candidates(
        target_rows,
        buffers,
        scope="target",
        max_distance=max_distance,
        max_delta=max_delta,
    )
    selector_rows, selector_lookup = selector_rows_for(target_candidates, known_candidates)
    target_output_rows = target_best_rows(target_rows, target_candidates, selector_lookup)

    guarded_selector_rows = [
        row
        for row in selector_rows
        if row.get("selector_guard") == "non_oracle"
        and row.get("promotion_guard") == "1"
        and row.get("verdict") == "guarded_exact"
    ]
    target_guarded_exact_bytes = sum(int_value(row, "exact_bytes") for row in target_output_rows)
    target_guarded_weak_bytes = sum(
        int_value(row, "exact_bytes")
        for row in target_output_rows
        if row.get("promotion_candidate") == "1" and row.get("promotion_ready") == "0"
    )
    frontier80_target_only_unique_bytes = sum(
        int_value(row, "span_length")
        for row in target_output_rows
        if row.get("frontier_id") == "80" and row.get("selector_verdict") == "target_only_unique"
    )
    target_only_unique_bytes = sum(
        int_value(row, "span_length") for row in target_output_rows if row.get("selector_verdict") == "target_only_unique"
    )
    promotion_candidate_bytes = sum(
        int_value(row, "span_length") for row in target_output_rows if row.get("promotion_candidate") == "1"
    )
    promotion_ready_bytes = sum(
        int_value(row, "span_length") for row in target_output_rows if row.get("promotion_ready") == "1"
    )
    best_target = max(
        target_output_rows,
        key=lambda row: (
            int_value(row, "promotion_ready"),
            int_value(row, "promotion_candidate"),
            row.get("selector_verdict") == "target_only_unique",
            int_value(row, "span_length"),
        ),
        default={},
    )
    target_bytes = sum(span_length(row) for row in target_rows)
    summary = {
        "scope": "total",
        "candidate_mode": "external_terminal_spatial_bridge_selector_probe",
        "target_spans": str(len(target_rows)),
        "target_bytes": str(target_bytes),
        "known_reference_rows": str(len(known_rows)),
        "target_candidate_rows": str(len(target_candidates)),
        "known_candidate_rows": str(len(known_candidates)),
        "selector_group_rows": str(len(selector_rows)),
        "non_oracle_group_rows": str(sum(1 for row in selector_rows if row.get("selector_guard") == "non_oracle")),
        "guarded_selector_rows": str(len(guarded_selector_rows)),
        "target_guarded_exact_bytes": str(target_guarded_exact_bytes),
        "target_guarded_weak_bytes": str(target_guarded_weak_bytes),
        "frontier80_guarded_exact_bytes": str(
            sum(
                int_value(row, "exact_bytes")
                for row in target_output_rows
                if row.get("frontier_id") == "80" and row.get("promotion_candidate") == "1"
            )
        ),
        "frontier80_target_only_unique_bytes": str(frontier80_target_only_unique_bytes),
        "target_only_unique_bytes": str(target_only_unique_bytes),
        "best_target_span": best_target.get("span_key", ""),
        "best_selector_family": best_target.get("selector_family", ""),
        "best_selector_key": best_target.get("selector_key", ""),
        "best_selector_verdict": best_target.get("selector_verdict", ""),
        "next_probe": (
            "derive compressed/control delta producer for target-only frontier 80 bridge selectors"
            if promotion_ready_bytes == 0 and frontier80_target_only_unique_bytes > 0
            else (
                "promote guarded non-oracle spatial bridge selectors"
                if promotion_ready_bytes > 0
                else "expand non-oracle spatial bridge selector families"
            )
        ),
        "promotion_candidate_bytes": str(promotion_candidate_bytes),
        "promotion_ready_bytes": str(promotion_ready_bytes),
        "issue_rows": str(
            len(buffer_issues)
            + len(target_issues)
            + sum(1 for row in target_output_rows if row.get("issues") and row.get("issues") != "target_only_no_known_guard")
        ),
    }

    candidate_rows = known_candidates + target_candidates
    candidate_rows.sort(
        key=lambda row: (
            row.get("scope", ""),
            row.get("span_key", ""),
            int_value(row, "span_start"),
            int_value(row, "anchor_rel", 9999),
            row.get("delta_signature", ""),
        )
    )
    for index, row in enumerate(candidate_rows, start=1):
        row["rank"] = str(index)
    return summary, target_output_rows, selector_rows, candidate_rows


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
    selector_rows: list[dict[str, str]],
    candidate_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "targets": target_rows,
        "selectors": selector_rows,
        "candidates": candidate_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("targets.csv", output_dir / "targets.csv"),
            ("selectors.csv", output_dir / "selectors.csv"),
            ("candidates.csv", output_dir / "candidates.csv"),
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
    <div class="muted">Tests whether non-oracle row and anchor features seen on known spans can select spatial bridge delta signatures.</div>
  </header>
  <section class="stats">
    <div class="stat"><div class="muted">Target bytes</div><div class="value">{summary['target_bytes']}</div></div>
    <div class="stat"><div class="muted">Guarded exact</div><div class="value warn">{summary['target_guarded_exact_bytes']}</div></div>
    <div class="stat"><div class="muted">Frontier 80 target-only</div><div class="value warn">{summary['frontier80_target_only_unique_bytes']}</div></div>
    <div class="stat"><div class="muted">Selector groups</div><div class="value">{summary['selector_group_rows']}</div></div>
    <div class="stat"><div class="muted">Promotion-ready</div><div class="value warn">{summary['promotion_ready_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2>{links}</section>
  <section class="panel">
    <h2>Next</h2>
    <p><code>{html.escape(summary['next_probe'])}</code></p>
    <p class="muted">Best selector: <code>{html.escape(summary['best_target_span'])}</code> / <code>{html.escape(summary['best_selector_family'])}</code>.</p>
  </section>
  <section class="panel"><h2>Targets</h2>{render_table(target_rows, TARGET_FIELDNAMES)}</section>
  <section class="panel"><h2>Selectors</h2>{render_table(selector_rows, SELECTOR_FIELDNAMES)}</section>
  <section class="panel"><h2>Candidates</h2>{render_table(candidate_rows, CANDIDATE_FIELDNAMES)}</section>
  <script type="application/json" id="external-terminal-spatial-bridge-selector-data">{html.escape(data_json)}</script>
</main>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe non-oracle selectors for external terminal spatial bridges.")
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("--small-gaps", type=Path, default=DEFAULT_SMALL_GAPS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--max-distance", type=int, default=DEFAULT_MAX_DISTANCE)
    parser.add_argument("--max-delta", type=int, default=DEFAULT_MAX_DELTA)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex External Terminal Spatial Bridge Selector Probe",
    )
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    summary, target_rows, selector_rows, candidate_rows = build(
        read_csv(args.targets),
        read_csv(args.small_gaps),
        read_csv(args.fixtures),
        max_distance=args.max_distance,
        max_delta=args.max_delta,
    )
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, target_rows)
    write_csv(args.output / "selectors.csv", SELECTOR_FIELDNAMES, selector_rows)
    write_csv(args.output / "candidates.csv", CANDIDATE_FIELDNAMES, candidate_rows)
    (args.output / "index.html").write_text(
        build_html(summary, target_rows, selector_rows, candidate_rows, args.output, args.title),
        encoding="utf-8",
    )
    print(
        "External terminal spatial bridge selector probe: "
        f"guarded_exact={summary['target_guarded_exact_bytes']}/{summary['target_bytes']} "
        f"frontier80_target_only={summary['frontier80_target_only_unique_bytes']} "
        f"promotion_ready={summary['promotion_ready_bytes']} "
        f"issues={summary['issue_rows']}"
    )
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
