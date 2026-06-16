#!/usr/bin/env python3
"""Classify unresolved noisy promoted nonzero gap rows."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_fill_selector_probe import (
    DEFAULT_FIXTURES,
    DEFAULT_OPERATIONS,
    DEFAULT_PATTERNS,
    control_signature,
    fixture_key,
    length_bucket,
    load_expected_by_fixture,
    op_key,
    pattern_op_key,
    read_bytes,
    read_csv,
    safe_bytes_fromhex,
)
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_noisy_shape_probe")
FIXED_TRANSFORMS = ("identity", "low7", "highbit_set", "bit_not", "nibble_swap")

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "target_bytes",
    "length_bucket_groups",
    "first_use_shape_groups",
    "first_use_repeated_groups",
    "first_use_repeated_rows",
    "first_use_repeated_bytes",
    "delta_class_shape_groups",
    "delta_class_repeated_groups",
    "delta_class_repeated_rows",
    "delta_class_repeated_bytes",
    "run_length_shape_groups",
    "run_length_repeated_groups",
    "run_length_repeated_rows",
    "run_length_repeated_bytes",
    "source_like_rows",
    "source_like_bytes",
    "periodic_rows",
    "periodic_bytes",
    "gradient_like_rows",
    "gradient_like_bytes",
    "high_entropy_rows",
    "high_entropy_bytes",
    "best_exact_bytes_total",
    "best_prefix_bytes_total",
    "best_single_exact_bytes",
    "best_single_prefix_bytes",
    "full_match_rows",
    "control_selector_groups",
    "repeated_control_selector_groups",
    "best_control_selector_rows",
    "best_control_selector_bytes",
    "issue_rows",
]

TARGET_FIELDNAMES = [
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "span_index",
    "run_index",
    "op_index",
    "pattern_class",
    "length",
    "length_bucket",
    "start",
    "end",
    "start_mod64",
    "control_ref_offset",
    "control_ref_mod64",
    "control_window_signature",
    "unique_bytes",
    "unique_ratio",
    "dominant_byte_hex",
    "dominant_ratio",
    "entropy_bits",
    "entropy_ratio",
    "run_count",
    "max_same_run_bytes",
    "equal_adjacent_ratio",
    "monotonic_step_ratio",
    "small_delta_ratio",
    "best_period",
    "best_period_ratio",
    "first_use_shape_key",
    "first_use_shape_preview",
    "delta_class_shape_key",
    "delta_class_shape_preview",
    "run_length_shape_key",
    "run_length_shape_preview",
    "top_nibbles",
    "local_best_pool",
    "local_best_transform",
    "local_best_offset",
    "local_best_exact_bytes",
    "local_best_exact_ratio",
    "local_best_prefix_bytes",
    "local_best_full_match",
    "classification",
    "head_hex",
    "tail_hex",
    "issues",
]

SHAPE_FIELDNAMES = [
    "shape_kind",
    "shape_key",
    "shape_preview",
    "rows",
    "bytes",
    "classifications",
    "length_buckets",
    "fixtures",
    "sample_pcx",
    "sample_frontier_id",
]

SOURCE_FIELDNAMES = [
    "pool",
    "transform",
    "rows",
    "bytes",
    "exact_bytes",
    "prefix_bytes",
    "full_match_rows",
    "best_single_exact_bytes",
    "best_single_prefix_bytes",
    "classifications",
    "fixtures",
    "sample_pcx",
    "sample_frontier_id",
]

CONTROL_FIELDNAMES = [
    "selector_family",
    "selector_key",
    "rows",
    "bytes",
    "source_like_bytes",
    "periodic_bytes",
    "gradient_like_bytes",
    "high_entropy_bytes",
    "best_exact_bytes",
    "classifications",
    "fixtures",
    "sample_pcx",
    "sample_frontier_id",
]


def common_prefix(left: bytes, right: bytes) -> int:
    limit = min(len(left), len(right))
    for index in range(limit):
        if left[index] != right[index]:
            return index
    return limit


def exact_count(left: bytes, right: bytes) -> int:
    return sum(1 for left_value, right_value in zip(left, right) if left_value == right_value)


def nibble_swap(data: bytes) -> bytes:
    return bytes((((value & 0x0F) << 4) | ((value & 0xF0) >> 4)) for value in data)


def transform_bytes(data: bytes, transform: str) -> bytes:
    if transform == "identity":
        return data
    if transform == "low7":
        return bytes(value & 0x7F for value in data)
    if transform == "highbit_set":
        return bytes(value | 0x80 for value in data)
    if transform == "bit_not":
        return bytes(value ^ 0xFF for value in data)
    if transform == "nibble_swap":
        return nibble_swap(data)
    return b""


def shape_key(shape: str) -> str:
    digest = hashlib.sha1(shape.encode("ascii")).hexdigest()[:14]
    return f"len={len(shape)}|sha1={digest}"


def preview_text(value: str, limit: int = 96) -> str:
    if len(value) <= limit:
        return value
    return f"{value[:limit]}..."


def first_use_shape(data: bytes) -> str:
    rank_by_value: dict[int, int] = {}
    output: list[str] = []
    for value in data:
        if value not in rank_by_value:
            rank_by_value[value] = len(rank_by_value)
        output.append(f"{rank_by_value[value]:x}")
    return ".".join(output)


def delta_class(value: int) -> str:
    signed = ((value + 128) & 0xFF) - 128
    if signed == 0:
        return "0"
    prefix = "+" if signed > 0 else "-"
    magnitude = abs(signed)
    if magnitude <= 2:
        return f"{prefix}{magnitude}"
    if magnitude <= 7:
        return f"{prefix}s"
    if magnitude <= 31:
        return f"{prefix}m"
    return f"{prefix}l"


def delta_class_shape(data: bytes) -> str:
    if len(data) < 2:
        return ""
    return ".".join(delta_class((data[index] - data[index - 1]) & 0xFF) for index in range(1, len(data)))


def run_lengths(data: bytes) -> list[int]:
    if not data:
        return []
    lengths: list[int] = []
    current = data[0]
    count = 1
    for value in data[1:]:
        if value == current:
            count += 1
            continue
        lengths.append(count)
        current = value
        count = 1
    lengths.append(count)
    return lengths


def run_length_shape(data: bytes) -> str:
    return ".".join(str(length) for length in run_lengths(data))


def entropy_bits(data: bytes) -> float:
    if not data:
        return 0.0
    counts = Counter(data)
    total = len(data)
    return -sum((count / total) * math.log2(count / total) for count in counts.values())


def adjacent_stats(data: bytes) -> tuple[float, float, float]:
    if len(data) < 2:
        return 0.0, 0.0, 0.0
    deltas = [((data[index] - data[index - 1] + 128) & 0xFF) - 128 for index in range(1, len(data))]
    equal = sum(1 for delta in deltas if delta == 0)
    step = sum(1 for delta in deltas if abs(delta) == 1)
    small = sum(1 for delta in deltas if abs(delta) <= 4)
    total = len(deltas)
    return equal / total, step / total, small / total


def best_period(data: bytes) -> tuple[int, float]:
    best_period_value = 0
    best_ratio = 0.0
    for period in (2, 3, 4, 5, 6, 7, 8, 16, 32, 64):
        if len(data) <= period:
            continue
        matches = sum(1 for index in range(period, len(data)) if data[index] == data[index - period])
        ratio = matches / (len(data) - period)
        if ratio > best_ratio:
            best_period_value = period
            best_ratio = ratio
    return best_period_value, best_ratio


def top_nibbles(data: bytes) -> str:
    counts = Counter(value >> 4 for value in data)
    total = len(data) or 1
    return ";".join(
        f"0x{nibble:x}:{count}:{count / total:.3f}"
        for nibble, count in counts.most_common(4)
    )


def source_offsets(pool: bytes, target_length: int) -> list[int]:
    if not pool:
        return []
    if len(pool) <= target_length:
        return [0]
    return list(range(0, len(pool) - target_length + 1))


def score_source(expected: bytes, pool: bytes, pool_name: str, transform: str, offset: int) -> dict[str, str]:
    source = pool[offset : offset + len(expected)] if len(pool) >= len(expected) else pool
    output = transform_bytes(source, transform)
    exact = exact_count(expected, output)
    prefix = common_prefix(expected, output)
    full = len(output) == len(expected) and exact == len(expected)
    return {
        "pool": pool_name,
        "transform": transform,
        "offset": str(offset),
        "exact_bytes": str(exact),
        "prefix_bytes": str(prefix),
        "full_match": "1" if full else "0",
    }


def best_source(expected: bytes, pools: dict[str, bytes]) -> dict[str, str]:
    pool_rank = {
        "control_window": 0,
        "neighbor": 1,
        "control_prefix": 2,
        "fragment": 3,
        "segment_gap": 4,
    }
    transform_rank = {name: index for index, name in enumerate(FIXED_TRANSFORMS)}
    candidates: list[dict[str, str]] = []
    for pool_name, pool in pools.items():
        for offset in source_offsets(pool, len(expected)):
            for transform in FIXED_TRANSFORMS:
                candidates.append(score_source(expected, pool, pool_name, transform, offset))
    if not candidates:
        return {
            "pool": "",
            "transform": "",
            "offset": "",
            "exact_bytes": "0",
            "prefix_bytes": "0",
            "full_match": "0",
        }
    return max(
        candidates,
        key=lambda row: (
            int_value(row, "full_match"),
            int_value(row, "exact_bytes"),
            int_value(row, "prefix_bytes"),
            -pool_rank.get(row.get("pool", ""), 99),
            -transform_rank.get(row.get("transform", ""), 99),
            -int_value(row, "offset"),
        ),
    )


def classify_row(row: dict[str, str]) -> str:
    exact_ratio = float(row.get("local_best_exact_ratio", "0") or 0)
    period_ratio = float(row.get("best_period_ratio", "0") or 0)
    step_ratio = float(row.get("monotonic_step_ratio", "0") or 0)
    small_delta_ratio = float(row.get("small_delta_ratio", "0") or 0)
    entropy_ratio = float(row.get("entropy_ratio", "0") or 0)
    unique_ratio = float(row.get("unique_ratio", "0") or 0)
    dominant_ratio = float(row.get("dominant_ratio", "0") or 0)
    if row.get("local_best_full_match") == "1" or exact_ratio >= 0.75:
        return "source_like"
    if period_ratio >= 0.70:
        return "periodic"
    if step_ratio >= 0.45 or small_delta_ratio >= 0.75:
        return "gradient_like"
    if dominant_ratio >= 0.40:
        return "dominant_residual"
    if entropy_ratio >= 0.65 and unique_ratio >= 0.45:
        return "high_entropy"
    return "mixed_unresolved"


def build_targets(
    pattern_rows: list[dict[str, str]],
    operation_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[str]]:
    operations = {op_key(row): row for row in operation_rows}
    fixtures = {fixture_key(row): row for row in fixture_rows}
    expected_by_fixture, fixture_issues = load_expected_by_fixture(fixture_rows)
    rows: list[dict[str, str]] = []

    for pattern in pattern_rows:
        if pattern.get("pattern_class") != "noisy":
            continue
        issues: list[str] = []
        key = fixture_key(pattern)
        expected_all = expected_by_fixture.get(key, b"")
        start = int_value(pattern, "start")
        end = int_value(pattern, "end")
        expected = expected_all[start:end]
        if not expected:
            issues.append("missing_expected_chunk")
            continue

        operation = operations.get(pattern_op_key(pattern), {})
        if not operation:
            issues.append("missing_operation")
        fixture = fixtures.get(key, {})
        segment_gap = read_bytes(fixture.get("segment_gap_path", ""), issues, "segment_gap") if fixture else b""
        fragment = read_bytes(fixture.get("fragment_path", ""), issues, "fragment") if fixture else b""
        control_prefix = read_bytes(fixture.get("control_prefix_path", ""), issues, "control_prefix") if fixture else b""
        control_window_hex = operation.get("control_window_hex", "")
        control_window = safe_bytes_fromhex(control_window_hex)
        neighbor = b"".join(
            safe_bytes_fromhex(operation.get(field, ""))
            for field in ("pre1_hex", "pre2_hex", "pre4_hex", "next2_hex")
        )
        pools = {
            "segment_gap": segment_gap,
            "fragment": fragment,
            "control_prefix": control_prefix,
            "control_window": control_window,
            "neighbor": neighbor,
        }
        source = best_source(expected, pools)
        counts = Counter(expected)
        dominant, dominant_count = counts.most_common(1)[0]
        entropy = entropy_bits(expected)
        unique_ratio = len(counts) / len(expected)
        equal_ratio, step_ratio, small_delta_ratio = adjacent_stats(expected)
        period_value, period_ratio = best_period(expected)
        first_shape = first_use_shape(expected)
        delta_shape = delta_class_shape(expected)
        run_shape = run_length_shape(expected)
        control_ref = operation.get("control_ref_offset", "") or "missing"
        control_ref_mod64 = str(int(control_ref) % 64) if control_ref.isdigit() else "missing"
        source_exact = int_value(source, "exact_bytes")
        row = {
            "rank": pattern.get("rank", ""),
            "archive": pattern.get("archive", ""),
            "archive_tag": pattern.get("archive_tag", ""),
            "pcx_name": pattern.get("pcx_name", ""),
            "frontier_id": pattern.get("frontier_id", ""),
            "span_index": pattern.get("span_index", ""),
            "run_index": pattern.get("run_index", ""),
            "op_index": pattern.get("op_index", ""),
            "pattern_class": pattern.get("pattern_class", ""),
            "length": str(len(expected)),
            "length_bucket": length_bucket(len(expected)),
            "start": pattern.get("start", ""),
            "end": pattern.get("end", ""),
            "start_mod64": str(start % 64),
            "control_ref_offset": control_ref,
            "control_ref_mod64": control_ref_mod64,
            "control_window_signature": control_signature(control_window_hex),
            "unique_bytes": str(len(counts)),
            "unique_ratio": f"{unique_ratio:.6f}",
            "dominant_byte_hex": f"0x{dominant:02x}",
            "dominant_ratio": f"{dominant_count / len(expected):.6f}",
            "entropy_bits": f"{entropy:.6f}",
            "entropy_ratio": f"{entropy / 8.0:.6f}",
            "run_count": str(len(run_lengths(expected))),
            "max_same_run_bytes": str(max(run_lengths(expected), default=0)),
            "equal_adjacent_ratio": f"{equal_ratio:.6f}",
            "monotonic_step_ratio": f"{step_ratio:.6f}",
            "small_delta_ratio": f"{small_delta_ratio:.6f}",
            "best_period": str(period_value),
            "best_period_ratio": f"{period_ratio:.6f}",
            "first_use_shape_key": shape_key(first_shape),
            "first_use_shape_preview": preview_text(first_shape),
            "delta_class_shape_key": shape_key(delta_shape),
            "delta_class_shape_preview": preview_text(delta_shape),
            "run_length_shape_key": shape_key(run_shape),
            "run_length_shape_preview": preview_text(run_shape),
            "top_nibbles": top_nibbles(expected),
            "local_best_pool": source.get("pool", ""),
            "local_best_transform": source.get("transform", ""),
            "local_best_offset": source.get("offset", ""),
            "local_best_exact_bytes": source.get("exact_bytes", "0"),
            "local_best_exact_ratio": f"{source_exact / len(expected):.6f}",
            "local_best_prefix_bytes": source.get("prefix_bytes", "0"),
            "local_best_full_match": source.get("full_match", "0"),
            "classification": "",
            "head_hex": expected[:16].hex(),
            "tail_hex": expected[-16:].hex(),
            "issues": ";".join(issues),
        }
        row["classification"] = classify_row(row)
        rows.append(row)
    return rows, fixture_issues


def repeated_stats(groups: list[dict[str, str]]) -> tuple[int, int, int]:
    repeated = [row for row in groups if int_value(row, "rows") > 1]
    return (
        len(repeated),
        sum(int_value(row, "rows") for row in repeated),
        sum(int_value(row, "bytes") for row in repeated),
    )


def build_shape_rows(rows: list[dict[str, str]], key_field: str, preview_field: str, kind: str) -> list[dict[str, str]]:
    counters: dict[str, Counter[str]] = defaultdict(Counter)
    classifications: dict[str, set[str]] = defaultdict(set)
    buckets: dict[str, set[str]] = defaultdict(set)
    fixtures: dict[str, set[tuple[str, str, str]]] = defaultdict(set)
    previews: dict[str, str] = {}
    samples: dict[str, dict[str, str]] = {}
    for row in rows:
        key = row.get(key_field, "")
        counters[key]["rows"] += 1
        counters[key]["bytes"] += int_value(row, "length")
        classifications[key].add(row.get("classification", ""))
        buckets[key].add(row.get("length_bucket", ""))
        fixtures[key].add(fixture_key(row))
        previews.setdefault(key, row.get(preview_field, ""))
        samples.setdefault(key, row)

    output: list[dict[str, str]] = []
    for key, counter in counters.items():
        sample = samples[key]
        output.append(
            {
                "shape_kind": kind,
                "shape_key": key,
                "shape_preview": previews.get(key, ""),
                "rows": str(counter["rows"]),
                "bytes": str(counter["bytes"]),
                "classifications": ";".join(sorted(classifications[key])),
                "length_buckets": ";".join(sorted(buckets[key])),
                "fixtures": str(len(fixtures[key])),
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
            }
        )
    output.sort(
        key=lambda row: (
            -int_value(row, "rows"),
            -int_value(row, "bytes"),
            row.get("shape_kind", ""),
            row.get("shape_key", ""),
        )
    )
    return output


def build_source_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    counters: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    classifications: dict[tuple[str, str], set[str]] = defaultdict(set)
    fixtures: dict[tuple[str, str], set[tuple[str, str, str]]] = defaultdict(set)
    samples: dict[tuple[str, str], dict[str, str]] = {}
    for row in rows:
        key = row.get("local_best_pool", ""), row.get("local_best_transform", "")
        length = int_value(row, "length")
        counters[key]["rows"] += 1
        counters[key]["bytes"] += length
        counters[key]["exact_bytes"] += int_value(row, "local_best_exact_bytes")
        counters[key]["prefix_bytes"] += int_value(row, "local_best_prefix_bytes")
        counters[key]["full_match_rows"] += 1 if row.get("local_best_full_match") == "1" else 0
        counters[key]["best_single_exact_bytes"] = max(
            counters[key]["best_single_exact_bytes"],
            int_value(row, "local_best_exact_bytes"),
        )
        counters[key]["best_single_prefix_bytes"] = max(
            counters[key]["best_single_prefix_bytes"],
            int_value(row, "local_best_prefix_bytes"),
        )
        classifications[key].add(row.get("classification", ""))
        fixtures[key].add(fixture_key(row))
        samples.setdefault(key, row)

    output: list[dict[str, str]] = []
    for key, counter in counters.items():
        pool, transform = key
        sample = samples[key]
        output.append(
            {
                "pool": pool,
                "transform": transform,
                "rows": str(counter["rows"]),
                "bytes": str(counter["bytes"]),
                "exact_bytes": str(counter["exact_bytes"]),
                "prefix_bytes": str(counter["prefix_bytes"]),
                "full_match_rows": str(counter["full_match_rows"]),
                "best_single_exact_bytes": str(counter["best_single_exact_bytes"]),
                "best_single_prefix_bytes": str(counter["best_single_prefix_bytes"]),
                "classifications": ";".join(sorted(classifications[key])),
                "fixtures": str(len(fixtures[key])),
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
            }
        )
    output.sort(
        key=lambda row: (
            -int_value(row, "exact_bytes"),
            -int_value(row, "prefix_bytes"),
            -int_value(row, "bytes"),
            row.get("pool", ""),
            row.get("transform", ""),
        )
    )
    return output


def selector_values(row: dict[str, str]) -> list[tuple[str, str]]:
    signature = row.get("control_window_signature", "") or "missing"
    ref_mod = row.get("control_ref_mod64", "") or "missing"
    start_mod64 = row.get("start_mod64", "") or "missing"
    bucket = row.get("length_bucket", "") or "missing"
    classification = row.get("classification", "") or "missing"
    return [
        ("control_signature", signature),
        ("control_ref_mod64", f"control_ref_mod64={ref_mod}"),
        ("start_mod64", f"start_mod64={start_mod64}"),
        ("length_bucket", f"length_bucket={bucket}"),
        ("classification", classification),
        ("signature_start_mod64", f"{signature}|start_mod64={start_mod64}"),
        ("signature_ref_mod64", f"{signature}|control_ref_mod64={ref_mod}"),
        ("signature_classification", f"{signature}|classification={classification}"),
        ("ref_mod64_classification", f"control_ref_mod64={ref_mod}|classification={classification}"),
        ("bucket_classification", f"length_bucket={bucket}|classification={classification}"),
    ]


def build_control_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    counters: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    classifications: dict[tuple[str, str], set[str]] = defaultdict(set)
    fixtures: dict[tuple[str, str], set[tuple[str, str, str]]] = defaultdict(set)
    samples: dict[tuple[str, str], dict[str, str]] = {}
    for row in rows:
        length = int_value(row, "length")
        classification = row.get("classification", "")
        for family, value in selector_values(row):
            key = family, value
            counters[key]["rows"] += 1
            counters[key]["bytes"] += length
            counters[key]["source_like_bytes"] += length if classification == "source_like" else 0
            counters[key]["periodic_bytes"] += length if classification == "periodic" else 0
            counters[key]["gradient_like_bytes"] += length if classification == "gradient_like" else 0
            counters[key]["high_entropy_bytes"] += length if classification == "high_entropy" else 0
            counters[key]["best_exact_bytes"] += int_value(row, "local_best_exact_bytes")
            classifications[key].add(classification)
            fixtures[key].add(fixture_key(row))
            samples.setdefault(key, row)

    output: list[dict[str, str]] = []
    for key, counter in counters.items():
        family, value = key
        sample = samples[key]
        output.append(
            {
                "selector_family": family,
                "selector_key": value,
                "rows": str(counter["rows"]),
                "bytes": str(counter["bytes"]),
                "source_like_bytes": str(counter["source_like_bytes"]),
                "periodic_bytes": str(counter["periodic_bytes"]),
                "gradient_like_bytes": str(counter["gradient_like_bytes"]),
                "high_entropy_bytes": str(counter["high_entropy_bytes"]),
                "best_exact_bytes": str(counter["best_exact_bytes"]),
                "classifications": ";".join(sorted(classifications[key])),
                "fixtures": str(len(fixtures[key])),
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
            }
        )
    output.sort(
        key=lambda row: (
            -int_value(row, "bytes"),
            -int_value(row, "rows"),
            row.get("selector_family", ""),
            row.get("selector_key", ""),
        )
    )
    return output


def sum_bytes(rows: list[dict[str, str]]) -> int:
    return sum(int_value(row, "length") for row in rows)


def build_summary(
    rows: list[dict[str, str]],
    first_groups: list[dict[str, str]],
    delta_groups: list[dict[str, str]],
    run_groups: list[dict[str, str]],
    control_rows: list[dict[str, str]],
    fixture_issue_count: int,
) -> dict[str, str]:
    first_repeated = repeated_stats(first_groups)
    delta_repeated = repeated_stats(delta_groups)
    run_repeated = repeated_stats(run_groups)
    source_like = [row for row in rows if row.get("classification") == "source_like"]
    periodic = [row for row in rows if row.get("classification") == "periodic"]
    gradient_like = [row for row in rows if row.get("classification") == "gradient_like"]
    high_entropy = [row for row in rows if row.get("classification") == "high_entropy"]
    repeated_control = [row for row in control_rows if int_value(row, "rows") > 1]
    best_control = max(control_rows, key=lambda row: int_value(row, "bytes"), default={})
    return {
        "scope": "total",
        "target_rows": str(len(rows)),
        "target_bytes": str(sum_bytes(rows)),
        "length_bucket_groups": str(len({row.get("length_bucket", "") for row in rows})),
        "first_use_shape_groups": str(len(first_groups)),
        "first_use_repeated_groups": str(first_repeated[0]),
        "first_use_repeated_rows": str(first_repeated[1]),
        "first_use_repeated_bytes": str(first_repeated[2]),
        "delta_class_shape_groups": str(len(delta_groups)),
        "delta_class_repeated_groups": str(delta_repeated[0]),
        "delta_class_repeated_rows": str(delta_repeated[1]),
        "delta_class_repeated_bytes": str(delta_repeated[2]),
        "run_length_shape_groups": str(len(run_groups)),
        "run_length_repeated_groups": str(run_repeated[0]),
        "run_length_repeated_rows": str(run_repeated[1]),
        "run_length_repeated_bytes": str(run_repeated[2]),
        "source_like_rows": str(len(source_like)),
        "source_like_bytes": str(sum_bytes(source_like)),
        "periodic_rows": str(len(periodic)),
        "periodic_bytes": str(sum_bytes(periodic)),
        "gradient_like_rows": str(len(gradient_like)),
        "gradient_like_bytes": str(sum_bytes(gradient_like)),
        "high_entropy_rows": str(len(high_entropy)),
        "high_entropy_bytes": str(sum_bytes(high_entropy)),
        "best_exact_bytes_total": str(sum(int_value(row, "local_best_exact_bytes") for row in rows)),
        "best_prefix_bytes_total": str(sum(int_value(row, "local_best_prefix_bytes") for row in rows)),
        "best_single_exact_bytes": str(max((int_value(row, "local_best_exact_bytes") for row in rows), default=0)),
        "best_single_prefix_bytes": str(max((int_value(row, "local_best_prefix_bytes") for row in rows), default=0)),
        "full_match_rows": str(sum(1 for row in rows if row.get("local_best_full_match") == "1")),
        "control_selector_groups": str(len(control_rows)),
        "repeated_control_selector_groups": str(len(repeated_control)),
        "best_control_selector_rows": best_control.get("rows", "0"),
        "best_control_selector_bytes": best_control.get("bytes", "0"),
        "issue_rows": str(sum(1 for row in rows if row.get("issues")) + fixture_issue_count),
    }


def build_rows(
    pattern_rows: list[dict[str, str]],
    operation_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
) -> tuple[
    dict[str, str],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
]:
    targets, fixture_issues = build_targets(pattern_rows, operation_rows, fixture_rows)
    first_groups = build_shape_rows(targets, "first_use_shape_key", "first_use_shape_preview", "first_use_shape")
    delta_groups = build_shape_rows(targets, "delta_class_shape_key", "delta_class_shape_preview", "delta_class_shape")
    run_groups = build_shape_rows(targets, "run_length_shape_key", "run_length_shape_preview", "run_length_shape")
    source_rows = build_source_rows(targets)
    control_rows = build_control_rows(targets)
    summary = build_summary(targets, first_groups, delta_groups, run_groups, control_rows, len(fixture_issues))
    return summary, targets, first_groups, delta_groups, run_groups, source_rows, control_rows


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 240) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    targets: list[dict[str, str]],
    first_groups: list[dict[str, str]],
    delta_groups: list[dict[str, str]],
    run_groups: list[dict[str, str]],
    source_rows: list[dict[str, str]],
    control_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "targets": targets,
        "firstGroups": first_groups,
        "deltaGroups": delta_groups,
        "runGroups": run_groups,
        "sourceRows": source_rows,
        "controlRows": control_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("targets.csv", output_dir / "targets.csv"),
            ("by_first_use_shape.csv", output_dir / "by_first_use_shape.csv"),
            ("by_delta_class_shape.csv", output_dir / "by_delta_class_shape.csv"),
            ("by_run_length_shape.csv", output_dir / "by_run_length_shape.csv"),
            ("by_source.csv", output_dir / "by_source.csv"),
            ("by_control_selector.csv", output_dir / "by_control_selector.csv"),
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
  --bg: #111416;
  --panel: #172023;
  --line: #31424a;
  --text: #edf5f4;
  --muted: #9dafb5;
  --accent: #77d3b1;
  --ok: #80df94;
  --warn: #f0c36a;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  min-height: 100vh;
  background: var(--bg);
  color: var(--text);
  font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}}
.wrap {{ width: min(1740px, calc(100vw - 28px)); margin: 0 auto; }}
header {{ border-bottom: 1px solid var(--line); background: #12191b; padding: 18px 0 14px; }}
h1 {{ margin: 0; font-size: 21px; font-weight: 720; letter-spacing: 0; }}
h2 {{ margin: 0 0 10px; font-size: 16px; }}
.sub {{ color: var(--muted); margin-top: 4px; }}
main {{ padding: 16px 0 28px; display: grid; gap: 16px; }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 10px; }}
.stat, .panel {{ border: 1px solid var(--line); border-radius: 8px; background: var(--panel); padding: 10px; }}
.label, .muted {{ color: var(--muted); }}
.value {{ font-size: 22px; font-weight: 760; line-height: 1.05; margin-top: 4px; }}
.ok {{ color: var(--ok); }}
.warn {{ color: var(--warn); }}
.panel {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; min-width: 1700px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Classifies noisy nonzero gap rows by reusable shapes, local sources, and control selectors.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Noisy bytes</div><div class="value">{summary['target_bytes']}</div></div>
    <div class="stat"><div class="label">Source-like bytes</div><div class="value ok">{summary['source_like_bytes']}</div></div>
    <div class="stat"><div class="label">High entropy bytes</div><div class="value warn">{summary['high_entropy_bytes']}</div></div>
    <div class="stat"><div class="label">Delta repeated bytes</div><div class="value">{summary['delta_class_repeated_bytes']}</div></div>
    <div class="stat"><div class="label">Best exact total</div><div class="value">{summary['best_exact_bytes_total']}</div></div>
    <div class="stat"><div class="label">Control selectors</div><div class="value">{summary['control_selector_groups']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2><div>{links}</div></section>
  <section class="panel"><h2>Source groups</h2>{render_table(source_rows, SOURCE_FIELDNAMES, 80)}</section>
  <section class="panel"><h2>Control selectors</h2>{render_table(control_rows, CONTROL_FIELDNAMES, 160)}</section>
  <section class="panel"><h2>Delta class shapes</h2>{render_table(delta_groups, SHAPE_FIELDNAMES, 160)}</section>
  <section class="panel"><h2>First-use shapes</h2>{render_table(first_groups, SHAPE_FIELDNAMES, 160)}</section>
  <section class="panel"><h2>Run-length shapes</h2>{render_table(run_groups, SHAPE_FIELDNAMES, 160)}</section>
  <section class="panel"><h2>Targets</h2>{render_table(targets, TARGET_FIELDNAMES, 220)}</section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_NOISY_SHAPE_PROBE = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Classify noisy .tex nonzero gap rows.")
    parser.add_argument("--patterns", type=Path, default=DEFAULT_PATTERNS)
    parser.add_argument("--operations", type=Path, default=DEFAULT_OPERATIONS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Tiny Nonzero Gap Noisy Shape Probe",
    )
    args = parser.parse_args()

    summary, targets, first_groups, delta_groups, run_groups, source_rows, control_rows = build_rows(
        read_csv(args.patterns),
        read_csv(args.operations),
        read_csv(args.fixtures),
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, targets)
    write_csv(args.output / "by_first_use_shape.csv", SHAPE_FIELDNAMES, first_groups)
    write_csv(args.output / "by_delta_class_shape.csv", SHAPE_FIELDNAMES, delta_groups)
    write_csv(args.output / "by_run_length_shape.csv", SHAPE_FIELDNAMES, run_groups)
    write_csv(args.output / "by_source.csv", SOURCE_FIELDNAMES, source_rows)
    write_csv(args.output / "by_control_selector.csv", CONTROL_FIELDNAMES, control_rows)
    html_path = args.output / "index.html"
    html_path.write_text(
        build_html(
            summary,
            targets,
            first_groups,
            delta_groups,
            run_groups,
            source_rows,
            control_rows,
            args.output,
            args.title,
        )
    )

    print(f"Noisy targets: {summary['target_rows']}")
    print(f"Noisy bytes: {summary['target_bytes']}")
    print(f"Source-like bytes: {summary['source_like_bytes']}")
    print(f"High entropy bytes: {summary['high_entropy_bytes']}")
    print(f"Best exact bytes total: {summary['best_exact_bytes_total']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
