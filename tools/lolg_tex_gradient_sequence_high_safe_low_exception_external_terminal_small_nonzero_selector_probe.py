#!/usr/bin/env python3
"""Probe small nonzero selectors for external terminal source blocker spans."""

from __future__ import annotations

import argparse
import csv
import html
import itertools
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_opcode_probe import relative_href, write_csv


DEFAULT_BLOCKER_SPANS = Path("output/tex_gradient_sequence_high_safe_low_exception_external_terminal_source/spans.csv")
DEFAULT_OPERATIONS = Path("output/tex_gap_segmentation_control_correlation_probe/operations.csv")
DEFAULT_FIXTURES = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_cover_second_promoted_replay/fixtures.csv"
)
DEFAULT_MANIFEST = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_OUTPUT = Path("output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_selector")

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "target_spans",
    "target_bytes",
    "joined_target_spans",
    "small_gap_rows",
    "known_small_gap_rows",
    "unknown_small_gap_rows",
    "context_candidate_rows",
    "false_free_context_rows",
    "best_context",
    "best_context_correct_spans",
    "best_context_correct_bytes",
    "best_context_false_spans",
    "best_context_ambiguous_spans",
    "source_candidate_rows",
    "full_source_candidate_spans",
    "best_source_exact_bytes",
    "best_source_target_span",
    "best_source_selector",
    "covered_target_spans",
    "covered_target_bytes",
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
    "length",
    "expected_start",
    "expected_mod64",
    "expected_hex",
    "op_index",
    "op_kind",
    "operation_joined",
    "known_in_replay",
    "prev_op_kind",
    "prev_op_length",
    "prev_source_hex",
    "prev_expected_hex",
    "next_op_kind",
    "next_op_length",
    "next_expected_hex",
    "gap_role",
    "control_ref_offset",
    "control_ref_mod64",
    "control_head4",
    "control_tail4",
    "frontier_type",
    "strategy",
    "best_source_selector",
    "best_source_exact_bytes",
    "best_source_output_hex",
    "best_source_input_hex",
    "best_context",
    "best_context_prediction",
    "best_context_verdict",
    "issues",
]

SOURCE_CANDIDATE_FIELDNAMES = [
    "rank",
    "target_span",
    "selector",
    "pool",
    "offset",
    "transform",
    "parameter",
    "exact_bytes",
    "prefix_bytes",
    "full_match",
    "source_hex",
    "output_hex",
    "expected_hex",
]

CONTEXT_CANDIDATE_FIELDNAMES = [
    "rank",
    "context_family",
    "feature_count",
    "known_contexts",
    "known_rows",
    "target_correct_spans",
    "target_false_spans",
    "target_ambiguous_spans",
    "target_miss_spans",
    "target_correct_bytes",
    "verdict",
    "sample_prediction",
]

GAP_FIELDNAMES = [
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "op_index",
    "span_key",
    "expected_start",
    "expected_end",
    "length",
    "expected_mod64",
    "expected_hex",
    "known_in_replay",
    "prev_op_kind",
    "prev_op_length",
    "prev_source_hex",
    "prev_expected_hex",
    "next_op_kind",
    "next_op_length",
    "next_expected_hex",
    "gap_role",
    "control_ref_offset",
    "control_ref_mod64",
    "control_head4",
    "control_tail4",
    "frontier_type",
    "strategy",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def int_value(row: dict[str, str] | dict[str, object], field: str, default: int = 0) -> int:
    try:
        return int(str(row.get(field, "")))
    except (TypeError, ValueError):
        return default


def asset_key(row: dict[str, str] | dict[str, object]) -> tuple[str, str, str]:
    return str(row.get("archive", "")), str(row.get("pcx_name", "")), str(row.get("frontier_id", ""))


def load_bytes(path_text: str, issues: list[str], label: str) -> bytes:
    if not path_text:
        issues.append(f"missing_{label}_path")
        return b""
    try:
        return Path(path_text).read_bytes()
    except OSError as exc:
        issues.append(f"read_{label}_failed:{exc}")
        return b""


def byte_exact(left: bytes, right: bytes) -> int:
    return sum(1 for left_value, right_value in zip(left, right) if left_value == right_value)


def common_prefix(left: bytes, right: bytes) -> int:
    limit = min(len(left), len(right))
    for index in range(limit):
        if left[index] != right[index]:
            return index
    return limit


def fixed_outputs(source: bytes) -> list[tuple[str, str, bytes]]:
    rows: list[tuple[str, str, bytes]] = [
        ("identity", "", source),
        ("low7", "", bytes(value & 0x7F for value in source)),
        ("highbit_set", "", bytes(value | 0x80 for value in source)),
        ("bit_not", "", bytes(value ^ 0xFF for value in source)),
        ("nibble_swap", "", bytes(((value & 0x0F) << 4) | (value >> 4) for value in source)),
    ]
    constants = list(range(16)) + [0x20, 0x30, 0x40, 0x55, 0x6A, 0x80, 0x90, 0xA0, 0xFF]
    for constant in constants:
        rows.append(("xor_const", f"{constant:02x}", bytes(value ^ constant for value in source)))
        rows.append(("add_const", f"{constant:02x}", bytes((value + constant) & 0xFF for value in source)))
        rows.append(("sub_const", f"{constant:02x}", bytes((value - constant) & 0xFF for value in source)))
    return rows


def neighbor_ops(ops: list[dict[str, str]], index: int) -> tuple[dict[str, str], dict[str, str]]:
    previous = ops[index - 1] if index > 0 else {}
    following = ops[index + 1] if index + 1 < len(ops) else {}
    return previous, following


def control_features(operation: dict[str, str]) -> tuple[str, str, str]:
    control_ref = operation.get("control_ref_offset", "")
    control_mod = str(int(control_ref) % 64) if control_ref.isdigit() else ""
    control_window = operation.get("control_window_hex", "")
    return control_mod, control_window[:8], control_window[-8:]


def gap_role(previous: dict[str, str], following: dict[str, str], operation: dict[str, str]) -> str:
    if not previous and following.get("op_kind") == "literal":
        return "prefix_before_literal"
    if previous.get("op_kind") == "literal" and following.get("op_kind") == "zero":
        return "between_literal_zero"
    if previous.get("op_kind") == "zero" and following.get("op_kind") == "literal":
        return "between_zero_literal"
    return f"{previous.get('op_kind', 'start')}->{following.get('op_kind', 'end')}"


def operation_features(operation: dict[str, str], previous: dict[str, str], following: dict[str, str]) -> dict[str, str]:
    control_mod, control_head4, control_tail4 = control_features(operation)
    return {
        "length": operation.get("length", ""),
        "op_index": operation.get("op_index", ""),
        "expected_start": operation.get("expected_start", ""),
        "expected_mod64": operation.get("expected_mod64", ""),
        "control_ref_offset": operation.get("control_ref_offset", ""),
        "control_ref_mod64": control_mod,
        "control_head4": control_head4,
        "control_tail4": control_tail4,
        "prev_op_kind": previous.get("op_kind", ""),
        "prev_op_length": previous.get("length", ""),
        "prev_source_hex": previous.get("source_hex", ""),
        "prev_expected_hex": previous.get("expected_hex", ""),
        "next_op_kind": following.get("op_kind", ""),
        "next_op_length": following.get("length", ""),
        "next_expected_hex": following.get("expected_hex", ""),
        "gap_role": gap_role(previous, following, operation),
        "frontier_type": operation.get("frontier_type", ""),
        "strategy": operation.get("strategy", ""),
    }


def known_mask_slice(fixture: dict[str, str], start: int, end: int, issues: list[str]) -> tuple[bool, bytes, bytes]:
    decoded = load_bytes(fixture.get("decoded_path", ""), issues, "decoded")
    known_mask = load_bytes(fixture.get("known_mask_path", ""), issues, "known_mask")
    if end > len(known_mask) or end > len(decoded):
        issues.append("target_slice_out_of_replay_range")
        return False, decoded[start:end], known_mask[start:end]
    return all(known_mask[start:end]), decoded[start:end], known_mask[start:end]


def best_source_candidates(
    span: dict[str, str],
    fixture: dict[str, str],
    manifest: dict[str, str],
    *,
    top_per_target: int,
) -> list[dict[str, str]]:
    issues: list[str] = []
    expected = bytes.fromhex(span.get("expected_hex", ""))
    length = len(expected)
    decoded = load_bytes(fixture.get("decoded_path", ""), issues, "decoded")
    known_mask = load_bytes(fixture.get("known_mask_path", ""), issues, "known_mask")
    pools = {
        "segment_gap": load_bytes(manifest.get("segment_gap_path", ""), issues, "segment_gap"),
        "control_prefix": load_bytes(manifest.get("control_prefix_path", ""), issues, "control_prefix"),
        "fragment": load_bytes(manifest.get("fragment_path", ""), issues, "fragment"),
    }
    known_windows: list[tuple[int, bytes]] = []
    if length > 0 and len(decoded) >= length and len(known_mask) >= length:
        for offset in range(0, len(decoded) - length + 1):
            if all(known_mask[offset : offset + length]):
                known_windows.append((offset, decoded[offset : offset + length]))

    rows: list[dict[str, str]] = []
    for pool, data in pools.items():
        if length <= 0 or len(data) < length:
            continue
        for offset in range(0, len(data) - length + 1):
            source = data[offset : offset + length]
            for transform, parameter, output in fixed_outputs(source):
                selector = f"{pool}@{offset}:{transform}{'=' + parameter if parameter else ''}"
                rows.append(
                    source_candidate_row(span, selector, pool, offset, transform, parameter, source, output, expected)
                )
    for offset, source in known_windows:
        for transform, parameter, output in fixed_outputs(source):
            selector = f"known_decoded@{offset}:{transform}{'=' + parameter if parameter else ''}"
            rows.append(
                source_candidate_row(span, selector, "known_decoded", offset, transform, parameter, source, output, expected)
            )

    rows.sort(
        key=lambda row: (
            -int_value(row, "exact_bytes"),
            -int_value(row, "prefix_bytes"),
            row.get("pool", ""),
            int_value(row, "offset"),
            row.get("transform", ""),
            row.get("parameter", ""),
        )
    )
    return rows[:top_per_target]


def source_candidate_row(
    span: dict[str, str],
    selector: str,
    pool: str,
    offset: int,
    transform: str,
    parameter: str,
    source: bytes,
    output: bytes,
    expected: bytes,
) -> dict[str, str]:
    exact = byte_exact(output, expected)
    prefix = common_prefix(output, expected)
    return {
        "rank": "",
        "target_span": span.get("span_key", ""),
        "selector": selector,
        "pool": pool,
        "offset": str(offset),
        "transform": transform,
        "parameter": parameter,
        "exact_bytes": str(exact),
        "prefix_bytes": str(prefix),
        "full_match": "1" if expected and exact == len(expected) else "0",
        "source_hex": source.hex(),
        "output_hex": output.hex(),
        "expected_hex": expected.hex(),
    }


def feature_names() -> list[str]:
    return [
        "length",
        "op_index",
        "expected_start",
        "expected_mod64",
        "control_ref_offset",
        "control_ref_mod64",
        "control_head4",
        "control_tail4",
        "prev_op_kind",
        "prev_op_length",
        "prev_source_hex",
        "prev_expected_hex",
        "next_op_kind",
        "next_op_length",
        "next_expected_hex",
        "gap_role",
        "frontier_type",
        "strategy",
    ]


def context_key(row: dict[str, str], fields: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(row.get(field, "") for field in fields)


def build_context_candidates(gap_rows: list[dict[str, str]], target_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    known_rows = [row for row in gap_rows if row.get("known_in_replay") == "1"]
    output: list[dict[str, str]] = []
    names = feature_names()
    for feature_count in (1, 2, 3):
        for fields in itertools.combinations(names, feature_count):
            grouped: dict[tuple[str, ...], set[str]] = defaultdict(set)
            grouped_rows: Counter[tuple[str, ...]] = Counter()
            for row in known_rows:
                key = context_key(row, fields)
                grouped[key].add(row.get("expected_hex", ""))
                grouped_rows[key] += 1
            correct = false = ambiguous = miss = correct_bytes = 0
            predictions: list[str] = []
            for target in target_rows:
                values = grouped.get(context_key(target, fields), set())
                if not values:
                    miss += 1
                    continue
                if len(values) > 1:
                    ambiguous += 1
                    continue
                prediction = next(iter(values))
                if prediction == target.get("expected_hex", ""):
                    correct += 1
                    correct_bytes += int_value(target, "span_length")
                    predictions.append(f"{target.get('span_key', '')}={prediction}")
                else:
                    false += 1
                    predictions.append(f"{target.get('span_key', '')}!={prediction}")
            if correct == 0 and false == 0 and ambiguous == 0:
                continue
            verdict = "false_free_context" if correct > 0 and false == 0 and ambiguous == 0 else "rejected_context"
            output.append(
                {
                    "rank": "",
                    "context_family": "+".join(fields),
                    "feature_count": str(feature_count),
                    "known_contexts": str(len(grouped)),
                    "known_rows": str(sum(grouped_rows.values())),
                    "target_correct_spans": str(correct),
                    "target_false_spans": str(false),
                    "target_ambiguous_spans": str(ambiguous),
                    "target_miss_spans": str(miss),
                    "target_correct_bytes": str(correct_bytes),
                    "verdict": verdict,
                    "sample_prediction": ";".join(predictions[:6]),
                }
            )
    output.sort(
        key=lambda row: (
            row.get("verdict") != "false_free_context",
            -int_value(row, "target_correct_bytes"),
            int_value(row, "target_false_spans"),
            int_value(row, "target_ambiguous_spans"),
            int_value(row, "feature_count"),
            row.get("context_family", ""),
        )
    )
    for index, row in enumerate(output, start=1):
        row["rank"] = str(index)
    return output


def build(
    blocker_spans: list[dict[str, str]],
    operation_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    manifest_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    operations_by_key: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for operation in operation_rows:
        operations_by_key[asset_key(operation)].append(operation)
    for rows in operations_by_key.values():
        rows.sort(key=lambda row: int_value(row, "op_index"))

    fixtures_by_key = {asset_key(row): row for row in fixture_rows}
    manifest_by_key = {asset_key(row): row for row in manifest_rows}
    issue_rows = 0

    gap_rows: list[dict[str, str]] = []
    target_rows: list[dict[str, str]] = []
    source_candidates: list[dict[str, str]] = []

    target_span_keys = {row.get("span_key", "") for row in blocker_spans}
    blocker_by_span = {row.get("span_key", ""): row for row in blocker_spans}

    for key, operations in operations_by_key.items():
        fixture = fixtures_by_key.get(key, {})
        replay_issues: list[str] = []
        for index, operation in enumerate(operations):
            if operation.get("op_kind") != "gap" or int_value(operation, "length") > 5:
                continue
            previous, following = neighbor_ops(operations, index)
            features = operation_features(operation, previous, following)
            start = int_value(operation, "expected_start")
            end = int_value(operation, "expected_end")
            known, _decoded, _mask = known_mask_slice(fixture, start, end, replay_issues) if fixture else (False, b"", b"")
            span_key = f"{operation.get('frontier_id', '')}:{start}-{end}"
            row = {
                "rank": operation.get("rank", ""),
                "archive": operation.get("archive", ""),
                "archive_tag": operation.get("archive_tag", ""),
                "pcx_name": operation.get("pcx_name", ""),
                "frontier_id": operation.get("frontier_id", ""),
                "op_index": operation.get("op_index", ""),
                "expected_start": operation.get("expected_start", ""),
                "expected_end": operation.get("expected_end", ""),
                "length": operation.get("length", ""),
                "expected_hex": operation.get("expected_hex", ""),
                "known_in_replay": "1" if known else "0",
                "span_key": span_key,
                **features,
            }
            gap_rows.append(row)
            if span_key not in target_span_keys:
                continue
            blocker = blocker_by_span[span_key]
            target_issues: list[str] = []
            if operation.get("expected_hex", "") != blocker.get("expected_hex", ""):
                target_issues.append("span_operation_expected_mismatch")
            if operation.get("op_kind") != "gap":
                target_issues.append("target_operation_not_gap")
            manifest = manifest_by_key.get(key, {})
            best_sources = best_source_candidates(blocker, fixture, manifest, top_per_target=8)
            source_candidates.extend(best_sources)
            best_source = best_sources[0] if best_sources else {}
            target_rows.append(
                {
                    "rank": str(len(target_rows) + 1),
                    "archive": operation.get("archive", ""),
                    "archive_tag": operation.get("archive_tag", ""),
                    "pcx_name": operation.get("pcx_name", ""),
                    "frontier_id": operation.get("frontier_id", ""),
                    "span_key": span_key,
                    "span_start": blocker.get("start", ""),
                    "span_end": blocker.get("end", ""),
                    "span_length": blocker.get("length", ""),
                    "expected_hex": blocker.get("expected_hex", ""),
                    "op_index": operation.get("op_index", ""),
                    "op_kind": operation.get("op_kind", ""),
                    "operation_joined": "1",
                    "known_in_replay": "1" if known else "0",
                    "prev_op_kind": features["prev_op_kind"],
                    "prev_op_length": features["prev_op_length"],
                    "prev_source_hex": features["prev_source_hex"],
                    "prev_expected_hex": features["prev_expected_hex"],
                    "next_op_kind": features["next_op_kind"],
                    "next_op_length": features["next_op_length"],
                    "next_expected_hex": features["next_expected_hex"],
                    "gap_role": features["gap_role"],
                    "control_ref_offset": features["control_ref_offset"],
                    "control_ref_mod64": features["control_ref_mod64"],
                    "control_head4": features["control_head4"],
                    "control_tail4": features["control_tail4"],
                    "best_source_selector": best_source.get("selector", ""),
                    "best_source_exact_bytes": best_source.get("exact_bytes", "0"),
                    "best_source_output_hex": best_source.get("output_hex", ""),
                    "best_source_input_hex": best_source.get("source_hex", ""),
                    "best_context": "",
                    "best_context_prediction": "",
                    "best_context_verdict": "unknown",
                    "issues": ";".join(target_issues),
                    **features,
                }
            )
        if replay_issues:
            issue_rows += 1

    joined = {row.get("span_key", "") for row in target_rows}
    for span in blocker_spans:
        if span.get("span_key", "") in joined:
            continue
        issue_rows += 1
        target_rows.append(
            {
                "rank": str(len(target_rows) + 1),
                "archive": span.get("archive", ""),
                "archive_tag": span.get("archive_tag", ""),
                "pcx_name": span.get("pcx_name", ""),
                "frontier_id": span.get("frontier_id", ""),
                "span_key": span.get("span_key", ""),
                "span_start": span.get("start", ""),
                "span_end": span.get("end", ""),
                "span_length": span.get("length", ""),
                "expected_hex": span.get("expected_hex", ""),
                "op_index": "",
                "op_kind": "",
                "operation_joined": "0",
                "known_in_replay": "0",
                "prev_op_kind": "",
                "prev_op_length": "",
                "prev_source_hex": "",
                "prev_expected_hex": "",
                "next_op_kind": "",
                "next_op_length": "",
                "next_expected_hex": "",
                "gap_role": "",
                "control_ref_offset": "",
                "control_ref_mod64": "",
                "control_head4": "",
                "control_tail4": "",
                "best_source_selector": "",
                "best_source_exact_bytes": "0",
                "best_source_output_hex": "",
                "best_source_input_hex": "",
                "best_context": "",
                "best_context_prediction": "",
                "best_context_verdict": "unknown",
                "issues": "missing_matching_gap_operation",
            }
        )

    context_candidates = build_context_candidates(gap_rows, target_rows)
    false_free_contexts = [row for row in context_candidates if row.get("verdict") == "false_free_context"]
    best_context = false_free_contexts[0] if false_free_contexts else (context_candidates[0] if context_candidates else {})
    if best_context:
        predictions = dict(
            item.split("=", 1)
            for item in best_context.get("sample_prediction", "").split(";")
            if "=" in item and "!=" not in item
        )
        for row in target_rows:
            if row.get("span_key", "") in predictions:
                row["best_context"] = best_context.get("context_family", "")
                row["best_context_prediction"] = predictions[row.get("span_key", "")]
                row["best_context_verdict"] = (
                    "correct" if predictions[row.get("span_key", "")] == row.get("expected_hex", "") else "false"
                )

    for index, row in enumerate(source_candidates, start=1):
        row["rank"] = str(index)

    full_source_targets = {row.get("target_span", "") for row in source_candidates if row.get("full_match") == "1"}
    best_source = max(source_candidates, key=lambda row: int_value(row, "exact_bytes"), default={})
    covered_target_spans = sum(1 for row in target_rows if int_value(row, "best_source_exact_bytes") == int_value(row, "span_length"))
    covered_target_bytes = sum(
        int_value(row, "span_length")
        for row in target_rows
        if int_value(row, "best_source_exact_bytes") == int_value(row, "span_length")
    )
    next_probe = (
        "derive compact-control gap grammar for remaining external terminal small nonzero spans"
        if covered_target_bytes < sum(int_value(row, "span_length") for row in target_rows)
        else "review source candidates before guarded promotion"
    )
    summary = {
        "scope": "total",
        "candidate_mode": "external_terminal_small_nonzero_selector_probe",
        "target_spans": str(len(target_rows)),
        "target_bytes": str(sum(int_value(row, "span_length") for row in target_rows)),
        "joined_target_spans": str(sum(1 for row in target_rows if row.get("operation_joined") == "1")),
        "small_gap_rows": str(len(gap_rows)),
        "known_small_gap_rows": str(sum(1 for row in gap_rows if row.get("known_in_replay") == "1")),
        "unknown_small_gap_rows": str(sum(1 for row in gap_rows if row.get("known_in_replay") != "1")),
        "context_candidate_rows": str(len(context_candidates)),
        "false_free_context_rows": str(len(false_free_contexts)),
        "best_context": best_context.get("context_family", ""),
        "best_context_correct_spans": best_context.get("target_correct_spans", "0"),
        "best_context_correct_bytes": best_context.get("target_correct_bytes", "0"),
        "best_context_false_spans": best_context.get("target_false_spans", "0"),
        "best_context_ambiguous_spans": best_context.get("target_ambiguous_spans", "0"),
        "source_candidate_rows": str(len(source_candidates)),
        "full_source_candidate_spans": str(len(full_source_targets)),
        "best_source_exact_bytes": best_source.get("exact_bytes", "0"),
        "best_source_target_span": best_source.get("target_span", ""),
        "best_source_selector": best_source.get("selector", ""),
        "covered_target_spans": str(covered_target_spans),
        "covered_target_bytes": str(covered_target_bytes),
        "next_probe": next_probe,
        "promotion_candidate_bytes": "0",
        "promotion_ready_bytes": "0",
        "issue_rows": str(
            issue_rows
            + sum(1 for row in target_rows if row.get("issues"))
            + sum(1 for row in gap_rows if not row.get("expected_hex"))
        ),
    }
    return summary, target_rows, source_candidates, context_candidates, gap_rows


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
    source_rows: list[dict[str, str]],
    context_rows: list[dict[str, str]],
    gap_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "targets": target_rows,
        "source_candidates": source_rows,
        "context_candidates": context_rows,
        "small_gaps": gap_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("targets.csv", output_dir / "targets.csv"),
            ("source_candidates.csv", output_dir / "source_candidates.csv"),
            ("context_candidates.csv", output_dir / "context_candidates.csv"),
            ("small_gaps.csv", output_dir / "small_gaps.csv"),
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
    <div class="muted">Tests strict context predictions and non-oracle source windows for external terminal blocker gaps.</div>
  </header>
  <section class="stats">
    <div class="stat"><div class="muted">Target spans</div><div class="value">{summary['target_spans']}</div></div>
    <div class="stat"><div class="muted">Target bytes</div><div class="value">{summary['target_bytes']}</div></div>
    <div class="stat"><div class="muted">Known small gaps</div><div class="value">{summary['known_small_gap_rows']}</div></div>
    <div class="stat"><div class="muted">False-free contexts</div><div class="value warn">{summary['false_free_context_rows']}</div></div>
    <div class="stat"><div class="muted">Covered bytes</div><div class="value warn">{summary['covered_target_bytes']}</div></div>
    <div class="stat"><div class="muted">Promotion-ready</div><div class="value warn">{summary['promotion_ready_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2>{links}</section>
  <section class="panel">
    <h2>Next</h2>
    <p><code>{html.escape(summary['next_probe'])}</code></p>
    <p class="muted">Best source: <code>{html.escape(summary['best_source_target_span'])}</code> via <code>{html.escape(summary['best_source_selector'])}</code> ({html.escape(summary['best_source_exact_bytes'])} exact bytes).</p>
  </section>
  <section class="panel"><h2>Targets</h2>{render_table(target_rows, TARGET_FIELDNAMES)}</section>
  <section class="panel"><h2>Source candidates</h2>{render_table(source_rows, SOURCE_CANDIDATE_FIELDNAMES)}</section>
  <section class="panel"><h2>Context candidates</h2>{render_table(context_rows, CONTEXT_CANDIDATE_FIELDNAMES)}</section>
  <section class="panel"><h2>Small gaps corpus</h2>{render_table(gap_rows, GAP_FIELDNAMES)}</section>
  <script type="application/json" id="external-terminal-small-nonzero-selector-data">{html.escape(data_json)}</script>
</main>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe small nonzero selectors for external terminal source spans.")
    parser.add_argument("--blocker-spans", type=Path, default=DEFAULT_BLOCKER_SPANS)
    parser.add_argument("--operations", type=Path, default=DEFAULT_OPERATIONS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex External Terminal Small Nonzero Selector Probe",
    )
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    summary, target_rows, source_rows, context_rows, gap_rows = build(
        read_csv(args.blocker_spans),
        read_csv(args.operations),
        read_csv(args.fixtures),
        read_csv(args.manifest),
    )
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, target_rows)
    write_csv(args.output / "source_candidates.csv", SOURCE_CANDIDATE_FIELDNAMES, source_rows)
    write_csv(args.output / "context_candidates.csv", CONTEXT_CANDIDATE_FIELDNAMES, context_rows)
    write_csv(args.output / "small_gaps.csv", GAP_FIELDNAMES, gap_rows)
    html_path = args.output / "index.html"
    html_path.write_text(
        build_html(summary, target_rows, source_rows, context_rows, gap_rows, args.output, args.title),
        encoding="utf-8",
    )

    print(f"Target spans: {summary['target_spans']}")
    print(f"Target bytes: {summary['target_bytes']}")
    print(f"Known small gaps: {summary['known_small_gap_rows']}/{summary['small_gap_rows']}")
    print(f"False-free contexts: {summary['false_free_context_rows']}")
    print(f"Covered target bytes: {summary['covered_target_bytes']}")
    print(f"Next probe: {summary['next_probe']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
