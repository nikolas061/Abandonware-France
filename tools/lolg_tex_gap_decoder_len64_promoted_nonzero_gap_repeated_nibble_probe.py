#!/usr/bin/env python3
"""Probe repeated-nibble jump rows for two-band ping-pong grammar."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_fill_selector_probe import (
    DEFAULT_FIXTURES,
    DEFAULT_OPERATIONS,
    fixture_key,
    load_expected_by_fixture,
    op_key,
    read_bytes,
    read_csv,
    safe_bytes_fromhex,
)
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_repeated_nibble_probe")
DEFAULT_TARGETS = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_jump_token_probe/targets.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "target_bytes",
    "operation_rows",
    "missing_operation_rows",
    "jump_delta_count",
    "positive_jump_count",
    "negative_jump_count",
    "two_band_rows",
    "two_band_bytes",
    "pingpong_rows",
    "pingpong_bytes",
    "dominant_band_rows",
    "dominant_band_bytes",
    "total_nibble_pair_count",
    "band_pair_groups",
    "repeated_band_pair_groups",
    "repeated_band_pair_rows",
    "repeated_band_pair_bytes",
    "band_phase_shape_groups",
    "band_phase_repeated_groups",
    "band_phase_repeated_rows",
    "band_phase_repeated_bytes",
    "exact_pair_shape_groups",
    "exact_pair_repeated_groups",
    "exact_pair_repeated_rows",
    "exact_pair_repeated_bytes",
    "candidate_windows",
    "nibble_source_exact_total",
    "nibble_source_best_single",
    "nibble_source_ge50_rows",
    "nibble_source_ge75_rows",
    "exact_source_exact_total",
    "exact_source_best_single",
    "exact_source_ge50_rows",
    "exact_source_ge75_rows",
    "best_overall_signal",
    "best_overall_exact",
    "best_overall_ratio",
    "promotion_ready_bytes",
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
    "length",
    "start",
    "end",
    "jump_delta_count",
    "positive_jump_count",
    "negative_jump_count",
    "band_pair_key",
    "band_pair_count",
    "band_pair_ratio",
    "two_band",
    "pingpong",
    "dominant_nibble_pair",
    "dominant_nibble_pair_count",
    "dominant_nibble_pair_ratio",
    "band_phase_shape_key",
    "band_phase_shape_preview",
    "exact_pair_shape_key",
    "exact_pair_shape_preview",
    "operation_present",
    "candidate_windows",
    "best_nibble_pool",
    "best_nibble_transform",
    "best_nibble_offset",
    "best_nibble_exact",
    "best_nibble_ratio",
    "best_exact_pool",
    "best_exact_transform",
    "best_exact_offset",
    "best_exact_exact",
    "best_exact_ratio",
    "best_signal_kind",
    "best_signal_pool",
    "best_signal_transform",
    "best_signal_exact",
    "best_signal_ratio",
    "head_hex",
    "tail_hex",
    "issues",
]

BAND_GROUP_FIELDNAMES = [
    "band_pair_key",
    "rows",
    "bytes",
    "jump_delta_count",
    "dominant_nibble_pairs",
    "pingpong_rows",
    "fixtures",
    "sample_pcx",
    "sample_frontier_id",
]

SIGNAL_GROUP_FIELDNAMES = [
    "signal_kind",
    "pool",
    "transform",
    "rows",
    "bytes",
    "jump_delta_count",
    "exact_total",
    "best_single",
    "ge50_rows",
    "ge75_rows",
    "fixtures",
    "sample_pcx",
    "sample_frontier_id",
]


def target_op_key(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    return (
        row.get("rank", ""),
        row.get("pcx_name", ""),
        row.get("frontier_id", ""),
        row.get("start", ""),
        row.get("end", ""),
    )


def signed_delta(left: int, right: int) -> int:
    return ((right - left + 128) & 0xFF) - 128


def jump_pairs(data: bytes) -> list[tuple[int, int, int]]:
    pairs: list[tuple[int, int, int]] = []
    for index in range(1, len(data)):
        delta = signed_delta(data[index - 1], data[index])
        if abs(delta) > 31:
            pairs.append((data[index - 1], data[index], delta))
    return pairs


def shape_key(shape: str) -> str:
    digest = hashlib.sha1(shape.encode("ascii")).hexdigest()[:14]
    return f"len={len(shape)}|sha1={digest}"


def preview_text(value: str, limit: int = 140) -> str:
    if len(value) <= limit:
        return value
    return f"{value[:limit]}..."


def ratio(numerator: int, denominator: int) -> str:
    return f"{(numerator / denominator) if denominator else 0.0:.6f}"


def magnitude_label(delta: int) -> str:
    magnitude = abs(delta)
    if magnitude <= 63:
        return "32_63"
    if magnitude <= 95:
        return "64_95"
    return "96_128"


def nibble_pairs_for(data: bytes) -> list[str]:
    return [f"{data[index - 1] >> 4:x}>{data[index] >> 4:x}" for index in range(1, len(data))]


def exact_pairs_for(data: bytes) -> list[str]:
    return [f"{data[index - 1]:02x}>{data[index]:02x}" for index in range(1, len(data))]


def low_nibble_pairs_for(data: bytes) -> list[str]:
    return [f"{data[index - 1] & 0x0F:x}>{data[index] & 0x0F:x}" for index in range(1, len(data))]


def operation_pools(operation: dict[str, str]) -> dict[str, bytes]:
    return {
        "control_window": safe_bytes_fromhex(operation.get("control_window_hex", "")),
        "operation_source": safe_bytes_fromhex(operation.get("source_hex", "")),
        "neighbor": b"".join(
            safe_bytes_fromhex(operation.get(field, ""))
            for field in ("pre1_hex", "pre2_hex", "pre4_hex", "next2_hex")
        ),
        "pre4": safe_bytes_fromhex(operation.get("pre4_hex", "")),
        "next2": safe_bytes_fromhex(operation.get("next2_hex", "")),
    }


def load_fixture_pools(fixture_rows: list[dict[str, str]]) -> dict[tuple[str, str, str], dict[str, bytes]]:
    pools: dict[tuple[str, str, str], dict[str, bytes]] = {}
    for fixture in fixture_rows:
        issues: list[str] = []
        pools[fixture_key(fixture)] = {
            "control_prefix": read_bytes(fixture.get("control_prefix_path", ""), issues, "control_prefix"),
            "fragment": read_bytes(fixture.get("fragment_path", ""), issues, "fragment"),
            "segment_gap": read_bytes(fixture.get("segment_gap_path", ""), issues, "segment_gap"),
        }
    return pools


def score_sequence(target: list[str], labels: list[str]) -> tuple[int, int, int]:
    if not target or not labels:
        return 0, 0, 0
    if len(labels) < len(target):
        exact = sum(1 for left, right in zip(target, labels) if left == right)
        return exact, 0, 1
    best_exact = 0
    best_offset = 0
    windows = 0
    for offset in range(0, len(labels) - len(target) + 1):
        windows += 1
        exact = sum(1 for left, right in zip(target, labels[offset : offset + len(target)]) if left == right)
        if exact > best_exact:
            best_exact = exact
            best_offset = offset
    return best_exact, best_offset, windows


def nibble_label_sets(data: bytes) -> list[tuple[str, list[str]]]:
    if len(data) < 2:
        return []
    high = nibble_pairs_for(data)
    high_inv = [f"{data[index] >> 4:x}>{data[index - 1] >> 4:x}" for index in range(1, len(data))]
    return [
        ("adjacent_high_nibbles", high),
        ("adjacent_high_nibbles_inv", high_inv),
        ("adjacent_low_nibbles", low_nibble_pairs_for(data)),
        ("mixed_high_low_nibbles", [f"{data[index - 1] >> 4:x}>{data[index] & 0x0F:x}" for index in range(1, len(data))]),
    ]


def exact_label_sets(data: bytes) -> list[tuple[str, list[str]]]:
    if len(data) < 2:
        return []
    exact = exact_pairs_for(data)
    exact_inv = [f"{data[index]:02x}>{data[index - 1]:02x}" for index in range(1, len(data))]
    return [
        ("adjacent_exact_pairs", exact),
        ("adjacent_exact_pairs_inv", exact_inv),
    ]


def score_pools(target: list[str], pools: dict[str, bytes], label_builder) -> tuple[dict[str, str], int]:
    best = {"pool": "", "transform": "", "offset": "0", "exact": "0", "ratio": "0.000000"}
    windows_total = 0
    for pool_name, data in pools.items():
        for transform, labels in label_builder(data):
            exact, offset, windows = score_sequence(target, labels)
            windows_total += windows
            if exact > int_value(best, "exact"):
                best = {
                    "pool": pool_name,
                    "transform": transform,
                    "offset": str(offset),
                    "exact": str(exact),
                    "ratio": ratio(exact, len(target)),
                }
    return best, windows_total


def band_phase_shape(pairs: list[tuple[int, int, int]], band_pair: tuple[int, int]) -> str:
    if len(band_pair) != 2:
        return ""
    low, high = band_pair
    labels: list[str] = []
    for left, right, delta in pairs:
        left_nibble = left >> 4
        right_nibble = right >> 4
        if left_nibble == low and right_nibble == high:
            direction = "lo_hi"
        elif left_nibble == high and right_nibble == low:
            direction = "hi_lo"
        else:
            direction = f"{left_nibble:x}>{right_nibble:x}"
        labels.append(f"{direction}:{magnitude_label(delta)}")
    return ".".join(labels)


def build_target_rows(
    target_rows: list[dict[str, str]],
    operation_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    operations = {op_key(row): row for row in operation_rows}
    expected_by_fixture, fixture_issues = load_expected_by_fixture(fixture_rows)
    fixture_pools = load_fixture_pools(fixture_rows)
    rows: list[dict[str, str]] = []
    for target in target_rows:
        if target.get("jump_structure_class") != "repeated_nibble_jump":
            continue
        issues = [issue for issue in target.get("issues", "").split(";") if issue]
        issues.extend(issue for issue in fixture_issues if str(fixture_key(target)) in issue)
        expected_all = expected_by_fixture.get(fixture_key(target), b"")
        expected = expected_all[int_value(target, "start") : int_value(target, "end")]
        if not expected:
            issues.append("missing_expected_chunk")
            continue
        pairs = jump_pairs(expected)
        nibble_pairs = [f"{left >> 4:x}>{right >> 4:x}" for left, right, _delta in pairs]
        exact_pairs = [f"{left:02x}>{right:02x}" for left, right, _delta in pairs]
        band_pairs = [tuple(sorted((left >> 4, right >> 4))) for left, right, _delta in pairs]
        band_pair, band_count = Counter(band_pairs).most_common(1)[0] if band_pairs else ((), 0)
        band_pair_key = ">".join(f"{value:x}" for value in band_pair)
        dominant_pair, dominant_count = Counter(nibble_pairs).most_common(1)[0] if nibble_pairs else ("", 0)
        forward = f"{band_pair[0]:x}>{band_pair[1]:x}" if len(band_pair) == 2 else ""
        reverse = f"{band_pair[1]:x}>{band_pair[0]:x}" if len(band_pair) == 2 else ""
        pair_set = {value for value in nibble_pairs if value in {forward, reverse}}
        two_band = len(band_pair) == 2 and band_count == len(pairs)
        pingpong = two_band and forward in pair_set and reverse in pair_set
        band_shape = band_phase_shape(pairs, band_pair)
        exact_shape = ".".join(exact_pairs)
        operation = operations.get(target_op_key(target), {})
        if not operation:
            issues.append("missing_operation")
        pools = {**fixture_pools.get(fixture_key(target), {}), **operation_pools(operation)}
        pools = {name: data for name, data in pools.items() if data}
        nibble_best, nibble_windows = score_pools(nibble_pairs, pools, nibble_label_sets)
        exact_best, exact_windows = score_pools(exact_pairs, pools, exact_label_sets)
        if float(nibble_best.get("ratio", "0") or 0) >= float(exact_best.get("ratio", "0") or 0):
            best_kind = "nibble_pair"
            best_signal = nibble_best
        else:
            best_kind = "exact_pair"
            best_signal = exact_best
        rows.append(
            {
                "rank": target.get("rank", ""),
                "archive": target.get("archive", ""),
                "archive_tag": target.get("archive_tag", ""),
                "pcx_name": target.get("pcx_name", ""),
                "frontier_id": target.get("frontier_id", ""),
                "span_index": target.get("span_index", ""),
                "run_index": target.get("run_index", ""),
                "op_index": target.get("op_index", ""),
                "length": str(len(expected)),
                "start": target.get("start", ""),
                "end": target.get("end", ""),
                "jump_delta_count": str(len(pairs)),
                "positive_jump_count": str(sum(1 for _left, _right, delta in pairs if delta > 0)),
                "negative_jump_count": str(sum(1 for _left, _right, delta in pairs if delta < 0)),
                "band_pair_key": band_pair_key,
                "band_pair_count": str(band_count),
                "band_pair_ratio": ratio(band_count, len(pairs)),
                "two_band": "1" if two_band else "0",
                "pingpong": "1" if pingpong else "0",
                "dominant_nibble_pair": dominant_pair,
                "dominant_nibble_pair_count": str(dominant_count),
                "dominant_nibble_pair_ratio": ratio(dominant_count, len(pairs)),
                "band_phase_shape_key": shape_key(band_shape),
                "band_phase_shape_preview": preview_text(band_shape),
                "exact_pair_shape_key": shape_key(exact_shape),
                "exact_pair_shape_preview": preview_text(exact_shape),
                "operation_present": "1" if operation else "0",
                "candidate_windows": str(nibble_windows + exact_windows),
                "best_nibble_pool": nibble_best["pool"],
                "best_nibble_transform": nibble_best["transform"],
                "best_nibble_offset": nibble_best["offset"],
                "best_nibble_exact": nibble_best["exact"],
                "best_nibble_ratio": nibble_best["ratio"],
                "best_exact_pool": exact_best["pool"],
                "best_exact_transform": exact_best["transform"],
                "best_exact_offset": exact_best["offset"],
                "best_exact_exact": exact_best["exact"],
                "best_exact_ratio": exact_best["ratio"],
                "best_signal_kind": best_kind,
                "best_signal_pool": best_signal["pool"],
                "best_signal_transform": best_signal["transform"],
                "best_signal_exact": best_signal["exact"],
                "best_signal_ratio": best_signal["ratio"],
                "head_hex": expected[:16].hex(),
                "tail_hex": expected[-16:].hex(),
                "issues": ";".join(issues),
            }
        )
    return rows


def repeated_stats(groups: list[dict[str, str]]) -> tuple[int, int, int]:
    repeated = [row for row in groups if int_value(row, "rows") > 1]
    return len(repeated), sum(int_value(row, "rows") for row in repeated), sum(int_value(row, "bytes") for row in repeated)


def build_band_groups(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    counters: dict[str, Counter[str]] = defaultdict(Counter)
    dominant: dict[str, Counter[str]] = defaultdict(Counter)
    fixtures: dict[str, set[tuple[str, str, str]]] = defaultdict(set)
    samples: dict[str, dict[str, str]] = {}
    for row in rows:
        key = row.get("band_pair_key", "")
        counters[key]["rows"] += 1
        counters[key]["bytes"] += int_value(row, "length")
        counters[key]["jump_delta_count"] += int_value(row, "jump_delta_count")
        counters[key]["pingpong_rows"] += int_value(row, "pingpong")
        dominant[key][row.get("dominant_nibble_pair", "")] += 1
        fixtures[key].add(fixture_key(row))
        samples.setdefault(key, row)
    output: list[dict[str, str]] = []
    for key, counter in counters.items():
        sample = samples[key]
        output.append(
            {
                "band_pair_key": key,
                "rows": str(counter["rows"]),
                "bytes": str(counter["bytes"]),
                "jump_delta_count": str(counter["jump_delta_count"]),
                "dominant_nibble_pairs": ";".join(f"{pair}:{count}" for pair, count in dominant[key].most_common()),
                "pingpong_rows": str(counter["pingpong_rows"]),
                "fixtures": str(len(fixtures[key])),
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
            }
        )
    output.sort(key=lambda row: (-int_value(row, "rows"), -int_value(row, "bytes"), row.get("band_pair_key", "")))
    return output


def build_signal_groups(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    counters: dict[tuple[str, str, str], Counter[str]] = defaultdict(Counter)
    fixtures: dict[tuple[str, str, str], set[tuple[str, str, str]]] = defaultdict(set)
    samples: dict[tuple[str, str, str], dict[str, str]] = {}
    for row in rows:
        key = (row.get("best_signal_kind", ""), row.get("best_signal_pool", ""), row.get("best_signal_transform", ""))
        counters[key]["rows"] += 1
        counters[key]["bytes"] += int_value(row, "length")
        counters[key]["jump_delta_count"] += int_value(row, "jump_delta_count")
        counters[key]["exact_total"] += int_value(row, "best_signal_exact")
        counters[key]["best_single"] = max(counters[key]["best_single"], int_value(row, "best_signal_exact"))
        if float(row.get("best_signal_ratio", "0") or 0) >= 0.50:
            counters[key]["ge50_rows"] += 1
        if float(row.get("best_signal_ratio", "0") or 0) >= 0.75:
            counters[key]["ge75_rows"] += 1
        fixtures[key].add(fixture_key(row))
        samples.setdefault(key, row)
    output: list[dict[str, str]] = []
    for key, counter in counters.items():
        sample = samples[key]
        output.append(
            {
                "signal_kind": key[0],
                "pool": key[1],
                "transform": key[2],
                "rows": str(counter["rows"]),
                "bytes": str(counter["bytes"]),
                "jump_delta_count": str(counter["jump_delta_count"]),
                "exact_total": str(counter["exact_total"]),
                "best_single": str(counter["best_single"]),
                "ge50_rows": str(counter["ge50_rows"]),
                "ge75_rows": str(counter["ge75_rows"]),
                "fixtures": str(len(fixtures[key])),
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
            }
        )
    output.sort(key=lambda row: (-int_value(row, "rows"), -int_value(row, "exact_total"), row.get("pool", "")))
    return output


def shape_group_stats(rows: list[dict[str, str]], key_field: str) -> tuple[int, int, int, int]:
    groups: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        key = row.get(key_field, "")
        groups[key]["rows"] += 1
        groups[key]["bytes"] += int_value(row, "length")
    group_rows = [{"rows": str(counter["rows"]), "bytes": str(counter["bytes"])} for counter in groups.values()]
    repeated = repeated_stats(group_rows)
    return len(groups), repeated[0], repeated[1], repeated[2]


def best_signal_summary(rows: list[dict[str, str]]) -> tuple[str, int, str]:
    if not rows:
        return "", 0, "0.000000"
    best = max(rows, key=lambda row: (float(row.get("best_signal_ratio", "0") or 0), int_value(row, "best_signal_exact")))
    return (
        f"{best.get('best_signal_kind', '')}:{best.get('best_signal_pool', '')}:{best.get('best_signal_transform', '')}",
        int_value(best, "best_signal_exact"),
        best.get("best_signal_ratio", "0.000000"),
    )


def build_summary(rows: list[dict[str, str]], band_groups: list[dict[str, str]]) -> dict[str, str]:
    band_repeated = repeated_stats(band_groups)
    band_phase_stats = shape_group_stats(rows, "band_phase_shape_key")
    exact_pair_stats = shape_group_stats(rows, "exact_pair_shape_key")
    best_signal, best_exact, best_ratio = best_signal_summary(rows)
    return {
        "scope": "total",
        "target_rows": str(len(rows)),
        "target_bytes": str(sum(int_value(row, "length") for row in rows)),
        "operation_rows": str(sum(1 for row in rows if row.get("operation_present") == "1")),
        "missing_operation_rows": str(sum(1 for row in rows if row.get("operation_present") != "1")),
        "jump_delta_count": str(sum(int_value(row, "jump_delta_count") for row in rows)),
        "positive_jump_count": str(sum(int_value(row, "positive_jump_count") for row in rows)),
        "negative_jump_count": str(sum(int_value(row, "negative_jump_count") for row in rows)),
        "two_band_rows": str(sum(1 for row in rows if row.get("two_band") == "1")),
        "two_band_bytes": str(sum(int_value(row, "length") for row in rows if row.get("two_band") == "1")),
        "pingpong_rows": str(sum(1 for row in rows if row.get("pingpong") == "1")),
        "pingpong_bytes": str(sum(int_value(row, "length") for row in rows if row.get("pingpong") == "1")),
        "dominant_band_rows": str(sum(1 for row in rows if float(row.get("band_pair_ratio", "0") or 0) >= 0.75)),
        "dominant_band_bytes": str(sum(int_value(row, "length") for row in rows if float(row.get("band_pair_ratio", "0") or 0) >= 0.75)),
        "total_nibble_pair_count": str(sum(int_value(row, "jump_delta_count") for row in rows)),
        "band_pair_groups": str(len(band_groups)),
        "repeated_band_pair_groups": str(band_repeated[0]),
        "repeated_band_pair_rows": str(band_repeated[1]),
        "repeated_band_pair_bytes": str(band_repeated[2]),
        "band_phase_shape_groups": str(band_phase_stats[0]),
        "band_phase_repeated_groups": str(band_phase_stats[1]),
        "band_phase_repeated_rows": str(band_phase_stats[2]),
        "band_phase_repeated_bytes": str(band_phase_stats[3]),
        "exact_pair_shape_groups": str(exact_pair_stats[0]),
        "exact_pair_repeated_groups": str(exact_pair_stats[1]),
        "exact_pair_repeated_rows": str(exact_pair_stats[2]),
        "exact_pair_repeated_bytes": str(exact_pair_stats[3]),
        "candidate_windows": str(sum(int_value(row, "candidate_windows") for row in rows)),
        "nibble_source_exact_total": str(sum(int_value(row, "best_nibble_exact") for row in rows)),
        "nibble_source_best_single": str(max((int_value(row, "best_nibble_exact") for row in rows), default=0)),
        "nibble_source_ge50_rows": str(sum(1 for row in rows if float(row.get("best_nibble_ratio", "0") or 0) >= 0.50)),
        "nibble_source_ge75_rows": str(sum(1 for row in rows if float(row.get("best_nibble_ratio", "0") or 0) >= 0.75)),
        "exact_source_exact_total": str(sum(int_value(row, "best_exact_exact") for row in rows)),
        "exact_source_best_single": str(max((int_value(row, "best_exact_exact") for row in rows), default=0)),
        "exact_source_ge50_rows": str(sum(1 for row in rows if float(row.get("best_exact_ratio", "0") or 0) >= 0.50)),
        "exact_source_ge75_rows": str(sum(1 for row in rows if float(row.get("best_exact_ratio", "0") or 0) >= 0.75)),
        "best_overall_signal": best_signal,
        "best_overall_exact": str(best_exact),
        "best_overall_ratio": best_ratio,
        "promotion_ready_bytes": "0",
        "issue_rows": str(sum(1 for row in rows if row.get("issues"))),
    }


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 240) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    rows: list[dict[str, str]],
    band_groups: list[dict[str, str]],
    signal_groups: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "targets": rows, "bandGroups": band_groups, "signalGroups": signal_groups}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("targets.csv", output_dir / "targets.csv"),
            ("by_band_pair.csv", output_dir / "by_band_pair.csv"),
            ("by_best_signal.csv", output_dir / "by_best_signal.csv"),
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
    <div class="sub">Tests whether repeated-nibble jumps are two-band ping-pong rows or control-derived pairs.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Repeated-nibble bytes</div><div class="value">{summary['target_bytes']}</div></div>
    <div class="stat"><div class="label">Ping-pong rows</div><div class="value ok">{summary['pingpong_rows']}</div></div>
    <div class="stat"><div class="label">Band groups</div><div class="value">{summary['band_pair_groups']}</div></div>
    <div class="stat"><div class="label">Best signal ratio</div><div class="value warn">{summary['best_overall_ratio']}</div></div>
    <div class="stat"><div class="label">Promotion-ready bytes</div><div class="value warn">{summary['promotion_ready_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2><div>{links}</div></section>
  <section class="panel"><h2>Band pairs</h2>{render_table(band_groups, BAND_GROUP_FIELDNAMES, 120)}</section>
  <section class="panel"><h2>Best signals</h2>{render_table(signal_groups, SIGNAL_GROUP_FIELDNAMES, 120)}</section>
  <section class="panel"><h2>Targets</h2>{render_table(rows, TARGET_FIELDNAMES, 120)}</section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_REPEATED_NIBBLE_PROBE = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe repeated-nibble jump rows for .tex nonzero gaps.")
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("--operations", type=Path, default=DEFAULT_OPERATIONS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Tiny Nonzero Gap Repeated Nibble Probe",
    )
    args = parser.parse_args()

    rows = build_target_rows(read_csv(args.targets), read_csv(args.operations), read_csv(args.fixtures))
    band_groups = build_band_groups(rows)
    signal_groups = build_signal_groups(rows)
    summary = build_summary(rows, band_groups)
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, rows)
    write_csv(args.output / "by_band_pair.csv", BAND_GROUP_FIELDNAMES, band_groups)
    write_csv(args.output / "by_best_signal.csv", SIGNAL_GROUP_FIELDNAMES, signal_groups)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, rows, band_groups, signal_groups, args.output, args.title))

    print(f"Repeated-nibble targets: {summary['target_rows']}")
    print(f"Repeated-nibble bytes: {summary['target_bytes']}")
    print(f"Ping-pong rows: {summary['pingpong_rows']}")
    print(f"Best overall ratio: {summary['best_overall_ratio']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
