#!/usr/bin/env python3
"""Correlate dense jump-weave rows with nearby control/source byte signals."""

from __future__ import annotations

import argparse
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_fill_selector_probe import (
    DEFAULT_FIXTURES,
    DEFAULT_OPERATIONS,
    fixture_key,
    op_key,
    read_bytes,
    read_csv,
    safe_bytes_fromhex,
)
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_dense_control_probe")
DEFAULT_TARGETS = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_dense_jump_probe/targets.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "target_bytes",
    "operation_rows",
    "missing_operation_rows",
    "jump_delta_count",
    "candidate_windows",
    "direction_exact_total",
    "direction_best_single",
    "direction_ge50_rows",
    "direction_ge75_rows",
    "magnitude_exact_total",
    "magnitude_best_single",
    "magnitude_ge50_rows",
    "magnitude_ge75_rows",
    "nibble_pair_exact_total",
    "nibble_pair_best_single",
    "nibble_pair_ge50_rows",
    "nibble_pair_ge75_rows",
    "phase_exact_total",
    "phase_best_single",
    "phase_ge50_rows",
    "phase_ge75_rows",
    "phase_ge75_long_rows",
    "phase_ge75_long_bytes",
    "best_overall_signal",
    "best_overall_exact",
    "best_overall_ratio",
    "source_like_rows",
    "source_like_bytes",
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
    "operation_present",
    "candidate_windows",
    "best_direction_pool",
    "best_direction_transform",
    "best_direction_offset",
    "best_direction_exact",
    "best_direction_ratio",
    "best_magnitude_pool",
    "best_magnitude_transform",
    "best_magnitude_offset",
    "best_magnitude_exact",
    "best_magnitude_ratio",
    "best_nibble_pair_pool",
    "best_nibble_pair_transform",
    "best_nibble_pair_offset",
    "best_nibble_pair_exact",
    "best_nibble_pair_ratio",
    "best_phase_pool",
    "best_phase_transform",
    "best_phase_offset",
    "best_phase_exact",
    "best_phase_ratio",
    "best_signal_kind",
    "best_signal_pool",
    "best_signal_transform",
    "best_signal_exact",
    "best_signal_ratio",
    "dense_class",
    "head_hex",
    "tail_hex",
    "issues",
]

GROUP_FIELDNAMES = [
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


def deltas(data: bytes) -> list[int]:
    return [signed_delta(data[index - 1], data[index]) for index in range(1, len(data))]


def jump_pairs(data: bytes) -> list[tuple[int, int, int]]:
    pairs: list[tuple[int, int, int]] = []
    for index, delta in enumerate(deltas(data), start=1):
        if abs(delta) > 31:
            pairs.append((data[index - 1], data[index], delta))
    return pairs


def direction_label(delta: int) -> str:
    return "+" if delta > 0 else "-"


def magnitude_label(delta: int) -> str:
    magnitude = abs(delta)
    if magnitude <= 63:
        return "32_63"
    if magnitude <= 95:
        return "64_95"
    return "96_128"


def byte_bucket(value: int) -> str:
    if value <= 63:
        return "32_63"
    if value <= 95:
        return "64_95"
    return "96_128"


def nibble_bucket(value: int) -> str:
    if value <= 3:
        return "32_63"
    if value <= 7:
        return "64_95"
    return "96_128"


def ratio(numerator: int, denominator: int) -> str:
    return f"{(numerator / denominator) if denominator else 0.0:.6f}"


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


def direction_label_sets(data: bytes) -> list[tuple[str, list[str]]]:
    if not data:
        return []
    bit7 = ["+" if value & 0x80 else "-" for value in data]
    bit0 = ["+" if value & 1 else "-" for value in data]
    high_ge8 = ["+" if (value >> 4) >= 8 else "-" for value in data]
    delta_sign = [direction_label(signed_delta(data[index - 1], data[index])) for index in range(1, len(data))]
    return [
        ("bit7", bit7),
        ("bit7_inv", ["-" if value == "+" else "+" for value in bit7]),
        ("bit0", bit0),
        ("bit0_inv", ["-" if value == "+" else "+" for value in bit0]),
        ("high_ge8", high_ge8),
        ("high_ge8_inv", ["-" if value == "+" else "+" for value in high_ge8]),
        ("adjacent_delta_sign", delta_sign),
        ("adjacent_delta_sign_inv", ["-" if value == "+" else "+" for value in delta_sign]),
    ]


def magnitude_label_sets(data: bytes) -> list[tuple[str, list[str]]]:
    if not data:
        return []
    adjacent = [magnitude_label(signed_delta(data[index - 1], data[index])) for index in range(1, len(data))]
    return [
        ("byte_bucket", [byte_bucket(value) for value in data]),
        ("high_nibble_bucket", [nibble_bucket(value >> 4) for value in data]),
        ("low_nibble_bucket", [nibble_bucket(value & 0x0F) for value in data]),
        ("adjacent_delta_bucket", adjacent),
    ]


def nibble_pair_label_sets(data: bytes) -> list[tuple[str, list[str]]]:
    if len(data) < 2:
        return []
    high_pairs = [f"{data[index - 1] >> 4:x}>{data[index] >> 4:x}" for index in range(1, len(data))]
    high_pairs_inv = [f"{data[index] >> 4:x}>{data[index - 1] >> 4:x}" for index in range(1, len(data))]
    low_pairs = [f"{data[index - 1] & 0x0F:x}>{data[index] & 0x0F:x}" for index in range(1, len(data))]
    mixed_pairs = [f"{data[index - 1] >> 4:x}>{data[index] & 0x0F:x}" for index in range(1, len(data))]
    return [
        ("adjacent_high_nibbles", high_pairs),
        ("adjacent_high_nibbles_inv", high_pairs_inv),
        ("adjacent_low_nibbles", low_pairs),
        ("mixed_high_low_nibbles", mixed_pairs),
    ]


def phase_label_sets(data: bytes) -> list[tuple[str, list[str]]]:
    if len(data) < 2:
        return []
    labels: list[str] = []
    labels_inv: list[str] = []
    for index in range(1, len(data)):
        delta = signed_delta(data[index - 1], data[index])
        pair = f"{data[index - 1] >> 4:x}>{data[index] >> 4:x}"
        pair_inv = f"{data[index] >> 4:x}>{data[index - 1] >> 4:x}"
        labels.append(f"{direction_label(delta)}{magnitude_label(delta)}:{pair}")
        labels_inv.append(f"{direction_label(-delta)}{magnitude_label(delta)}:{pair_inv}")
    return [
        ("adjacent_phase", labels),
        ("adjacent_phase_inv", labels_inv),
    ]


def score_pools(
    target: list[str],
    pools: dict[str, bytes],
    label_builder,
) -> tuple[dict[str, str], int]:
    best = {
        "pool": "",
        "transform": "",
        "offset": "0",
        "exact": "0",
        "ratio": "0.000000",
    }
    candidate_windows = 0
    for pool_name, data in pools.items():
        for transform, labels in label_builder(data):
            exact, offset, windows = score_sequence(target, labels)
            candidate_windows += windows
            if exact > int_value(best, "exact"):
                best = {
                    "pool": pool_name,
                    "transform": transform,
                    "offset": str(offset),
                    "exact": str(exact),
                    "ratio": ratio(exact, len(target)),
                }
    return best, candidate_windows


def load_fixture_pools(fixtures: list[dict[str, str]]) -> dict[tuple[str, str, str], dict[str, bytes]]:
    pools: dict[tuple[str, str, str], dict[str, bytes]] = {}
    for fixture in fixtures:
        issues: list[str] = []
        pools[fixture_key(fixture)] = {
            "control_prefix": read_bytes(fixture.get("control_prefix_path", ""), issues, "control_prefix"),
            "fragment": read_bytes(fixture.get("fragment_path", ""), issues, "fragment"),
            "segment_gap": read_bytes(fixture.get("segment_gap_path", ""), issues, "segment_gap"),
        }
    return pools


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


def build_target_rows(
    target_rows: list[dict[str, str]],
    operation_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    operations = {op_key(row): row for row in operation_rows}
    fixture_pools = load_fixture_pools(fixture_rows)
    output: list[dict[str, str]] = []
    for target in target_rows:
        issues = [issue for issue in target.get("issues", "").split(";") if issue]
        pairs = jump_pairs(bytes.fromhex(target.get("head_hex", "") + target.get("tail_hex", "")))
        # Re-read the exact span from fixture when head+tail is truncated by short rows.
        fixture_pool = fixture_pools.get(fixture_key(target), {})
        expected = b""
        expected_path = next(
            (
                fixture.get("expected_gap_path", "")
                for fixture in fixture_rows
                if fixture_key(fixture) == fixture_key(target)
            ),
            "",
        )
        if expected_path:
            local_issues: list[str] = []
            expected_all = read_bytes(expected_path, local_issues, "expected")
            expected = expected_all[int_value(target, "start") : int_value(target, "end")]
            issues.extend(local_issues)
            pairs = jump_pairs(expected)
        if not pairs:
            issues.append("missing_jump_pairs")
        directions = [direction_label(delta) for _left, _right, delta in pairs]
        magnitudes = [magnitude_label(delta) for _left, _right, delta in pairs]
        nibble_pairs = [f"{left >> 4:x}>{right >> 4:x}" for left, right, _delta in pairs]
        phases = [f"{direction_label(delta)}{magnitude_label(delta)}:{left >> 4:x}>{right >> 4:x}" for left, right, delta in pairs]
        operation = operations.get(target_op_key(target), {})
        if not operation:
            issues.append("missing_operation")
        pools = {**fixture_pool, **operation_pools(operation)}
        pools = {name: data for name, data in pools.items() if data}

        direction_best, direction_windows = score_pools(directions, pools, direction_label_sets)
        magnitude_best, magnitude_windows = score_pools(magnitudes, pools, magnitude_label_sets)
        nibble_best, nibble_windows = score_pools(nibble_pairs, pools, nibble_pair_label_sets)
        phase_best, phase_windows = score_pools(phases, pools, phase_label_sets)
        scored = [
            ("direction", direction_best),
            ("magnitude", magnitude_best),
            ("nibble_pair", nibble_best),
            ("phase", phase_best),
        ]
        best_kind, best_signal = max(
            scored,
            key=lambda item: (
                float(item[1].get("ratio", "0") or 0),
                int_value(item[1], "exact"),
                item[0] == "phase",
            ),
        )
        output.append(
            {
                "rank": target.get("rank", ""),
                "archive": target.get("archive", ""),
                "archive_tag": target.get("archive_tag", ""),
                "pcx_name": target.get("pcx_name", ""),
                "frontier_id": target.get("frontier_id", ""),
                "span_index": target.get("span_index", ""),
                "run_index": target.get("run_index", ""),
                "op_index": target.get("op_index", ""),
                "length": target.get("length", ""),
                "start": target.get("start", ""),
                "end": target.get("end", ""),
                "jump_delta_count": str(len(pairs)),
                "operation_present": "1" if operation else "0",
                "candidate_windows": str(direction_windows + magnitude_windows + nibble_windows + phase_windows),
                "best_direction_pool": direction_best["pool"],
                "best_direction_transform": direction_best["transform"],
                "best_direction_offset": direction_best["offset"],
                "best_direction_exact": direction_best["exact"],
                "best_direction_ratio": direction_best["ratio"],
                "best_magnitude_pool": magnitude_best["pool"],
                "best_magnitude_transform": magnitude_best["transform"],
                "best_magnitude_offset": magnitude_best["offset"],
                "best_magnitude_exact": magnitude_best["exact"],
                "best_magnitude_ratio": magnitude_best["ratio"],
                "best_nibble_pair_pool": nibble_best["pool"],
                "best_nibble_pair_transform": nibble_best["transform"],
                "best_nibble_pair_offset": nibble_best["offset"],
                "best_nibble_pair_exact": nibble_best["exact"],
                "best_nibble_pair_ratio": nibble_best["ratio"],
                "best_phase_pool": phase_best["pool"],
                "best_phase_transform": phase_best["transform"],
                "best_phase_offset": phase_best["offset"],
                "best_phase_exact": phase_best["exact"],
                "best_phase_ratio": phase_best["ratio"],
                "best_signal_kind": best_kind,
                "best_signal_pool": best_signal["pool"],
                "best_signal_transform": best_signal["transform"],
                "best_signal_exact": best_signal["exact"],
                "best_signal_ratio": best_signal["ratio"],
                "dense_class": target.get("dense_class", ""),
                "head_hex": (expected or b"")[:16].hex(),
                "tail_hex": (expected or b"")[-16:].hex(),
                "issues": ";".join(issues),
            }
        )
    return output


def build_group_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
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
        ratio_value = float(row.get("best_signal_ratio", "0") or 0)
        if ratio_value >= 0.50:
            counters[key]["ge50_rows"] += 1
        if ratio_value >= 0.75:
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


def best_signal_summary(rows: list[dict[str, str]]) -> tuple[str, int, str]:
    if not rows:
        return "", 0, "0.000000"
    best = max(
        rows,
        key=lambda row: (
            float(row.get("best_signal_ratio", "0") or 0),
            int_value(row, "best_signal_exact"),
        ),
    )
    return (
        f"{best.get('best_signal_kind', '')}:{best.get('best_signal_pool', '')}:{best.get('best_signal_transform', '')}",
        int_value(best, "best_signal_exact"),
        best.get("best_signal_ratio", "0.000000"),
    )


def build_summary(rows: list[dict[str, str]]) -> dict[str, str]:
    jump_count = sum(int_value(row, "jump_delta_count") for row in rows)
    best_signal, best_exact, best_ratio = best_signal_summary(rows)
    source_like = [row for row in rows if float(row.get("best_phase_ratio", "0") or 0) >= 0.75]
    long_source_like = [row for row in source_like if int_value(row, "jump_delta_count") >= 8]
    return {
        "scope": "total",
        "target_rows": str(len(rows)),
        "target_bytes": str(sum(int_value(row, "length") for row in rows)),
        "operation_rows": str(sum(1 for row in rows if row.get("operation_present") == "1")),
        "missing_operation_rows": str(sum(1 for row in rows if row.get("operation_present") != "1")),
        "jump_delta_count": str(jump_count),
        "candidate_windows": str(sum(int_value(row, "candidate_windows") for row in rows)),
        "direction_exact_total": str(sum(int_value(row, "best_direction_exact") for row in rows)),
        "direction_best_single": str(max((int_value(row, "best_direction_exact") for row in rows), default=0)),
        "direction_ge50_rows": str(sum(1 for row in rows if float(row.get("best_direction_ratio", "0") or 0) >= 0.50)),
        "direction_ge75_rows": str(sum(1 for row in rows if float(row.get("best_direction_ratio", "0") or 0) >= 0.75)),
        "magnitude_exact_total": str(sum(int_value(row, "best_magnitude_exact") for row in rows)),
        "magnitude_best_single": str(max((int_value(row, "best_magnitude_exact") for row in rows), default=0)),
        "magnitude_ge50_rows": str(sum(1 for row in rows if float(row.get("best_magnitude_ratio", "0") or 0) >= 0.50)),
        "magnitude_ge75_rows": str(sum(1 for row in rows if float(row.get("best_magnitude_ratio", "0") or 0) >= 0.75)),
        "nibble_pair_exact_total": str(sum(int_value(row, "best_nibble_pair_exact") for row in rows)),
        "nibble_pair_best_single": str(max((int_value(row, "best_nibble_pair_exact") for row in rows), default=0)),
        "nibble_pair_ge50_rows": str(sum(1 for row in rows if float(row.get("best_nibble_pair_ratio", "0") or 0) >= 0.50)),
        "nibble_pair_ge75_rows": str(sum(1 for row in rows if float(row.get("best_nibble_pair_ratio", "0") or 0) >= 0.75)),
        "phase_exact_total": str(sum(int_value(row, "best_phase_exact") for row in rows)),
        "phase_best_single": str(max((int_value(row, "best_phase_exact") for row in rows), default=0)),
        "phase_ge50_rows": str(sum(1 for row in rows if float(row.get("best_phase_ratio", "0") or 0) >= 0.50)),
        "phase_ge75_rows": str(sum(1 for row in rows if float(row.get("best_phase_ratio", "0") or 0) >= 0.75)),
        "phase_ge75_long_rows": str(len(long_source_like)),
        "phase_ge75_long_bytes": str(sum(int_value(row, "length") for row in long_source_like)),
        "best_overall_signal": best_signal,
        "best_overall_exact": str(best_exact),
        "best_overall_ratio": best_ratio,
        "source_like_rows": str(len(source_like)),
        "source_like_bytes": str(sum(int_value(row, "length") for row in source_like)),
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
    groups: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "targets": rows, "groups": groups}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("targets.csv", output_dir / "targets.csv"),
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
    <div class="sub">Scores dense jump directions, magnitudes, nibble pairs, and phases against nearby control/source bytes.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Dense rows</div><div class="value">{summary['target_rows']}</div></div>
    <div class="stat"><div class="label">Candidate windows</div><div class="value">{summary['candidate_windows']}</div></div>
    <div class="stat"><div class="label">Best phase rows >= 75%</div><div class="value warn">{summary['phase_ge75_rows']}</div></div>
    <div class="stat"><div class="label">Best signal</div><div class="value ok">{html.escape(summary['best_overall_ratio'])}</div></div>
    <div class="stat"><div class="label">Promotion-ready bytes</div><div class="value warn">{summary['promotion_ready_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2><div>{links}</div></section>
  <section class="panel"><h2>Best signal groups</h2>{render_table(groups, GROUP_FIELDNAMES, 120)}</section>
  <section class="panel"><h2>Targets</h2>{render_table(rows, TARGET_FIELDNAMES, 120)}</section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_DENSE_CONTROL_PROBE = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe dense jump rows against control/source signals.")
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("--operations", type=Path, default=DEFAULT_OPERATIONS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Tiny Nonzero Gap Dense Control Probe",
    )
    args = parser.parse_args()

    rows = build_target_rows(read_csv(args.targets), read_csv(args.operations), read_csv(args.fixtures))
    groups = build_group_rows(rows)
    summary = build_summary(rows)
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, rows)
    write_csv(args.output / "by_best_signal.csv", GROUP_FIELDNAMES, groups)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, rows, groups, args.output, args.title))

    print(f"Dense-control targets: {summary['target_rows']}")
    print(f"Candidate windows: {summary['candidate_windows']}")
    print(f"Phase >= 75 rows: {summary['phase_ge75_rows']}")
    print(f"Best overall ratio: {summary['best_overall_ratio']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
