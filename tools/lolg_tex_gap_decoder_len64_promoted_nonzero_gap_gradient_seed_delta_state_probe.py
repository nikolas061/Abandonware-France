#!/usr/bin/env python3
"""Probe stateful source/control delta selectors for gradient seeds."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import defaultdict
from pathlib import Path

from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_delta_state_probe")
DEFAULT_PHASE_VALUES = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_delta_phase_probe/phase_values.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "mapping_rows",
    "mapping_value_bytes",
    "state_scopes",
    "state_families",
    "state_groups",
    "deterministic_groups",
    "deterministic_bytes",
    "repeated_deterministic_groups",
    "repeated_deterministic_bytes",
    "singleton_deterministic_groups",
    "singleton_deterministic_bytes",
    "conflicted_groups",
    "conflicted_bytes",
    "prefix_accumulator_repeated_bytes",
    "fsm_repeated_bytes",
    "nibble_counter_repeated_bytes",
    "parser_counter_repeated_bytes",
    "best_state_family",
    "best_state_repeated_deterministic_bytes",
    "best_state_conflicted_bytes",
    "delta_values",
    "copy_unlock_rows",
    "copy_unlock_bytes",
    "total_potential_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

STATE_VALUE_FIELDNAMES = [
    "seed_id",
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "span_index",
    "run_index",
    "op_index",
    "start",
    "end",
    "length",
    "candidate_kind",
    "palette_index",
    "target_value_hex",
    "source_value_hex",
    "delta",
    "source_offset",
    "value_bytes",
    "copy_unlock_bytes",
    "control_window_len",
    "prefix_len_before",
    "prefix_len_through",
    "prefix_sum_before",
    "prefix_sum_through",
    "prefix_xor_before",
    "prefix_xor_through",
    "prefix_hi_lo_balance_before",
    "prefix_hi_lo_balance_through",
    "fsm_hilo_mod16",
    "fsm_shift_xor_mod16",
    "parser_hi_zero_lo_copy_zc_mod16",
    "state_entries",
    "issues",
]

SELECTOR_FIELDNAMES = [
    "state_scope",
    "state_family",
    "state_key",
    "rows",
    "seed_rows",
    "value_bytes",
    "deltas_seen",
    "deterministic",
    "repeated_deterministic",
    "verdict",
    "sample_pcx",
    "sample_frontier_id",
]

FAMILY_FIELDNAMES = [
    "state_scope",
    "state_family",
    "groups",
    "rows",
    "value_bytes",
    "deterministic_groups",
    "deterministic_bytes",
    "repeated_deterministic_groups",
    "repeated_deterministic_bytes",
    "singleton_deterministic_groups",
    "singleton_deterministic_bytes",
    "conflicted_groups",
    "conflicted_bytes",
    "verdict",
]

SCOPE_FIELDNAMES = [
    "state_scope",
    "families",
    "groups",
    "rows",
    "value_bytes",
    "deterministic_groups",
    "deterministic_bytes",
    "repeated_deterministic_groups",
    "repeated_deterministic_bytes",
    "singleton_deterministic_groups",
    "singleton_deterministic_bytes",
    "conflicted_groups",
    "conflicted_bytes",
    "verdict",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def safe_bytes_fromhex(value: str) -> bytes:
    try:
        return bytes.fromhex(value)
    except ValueError:
        return b""


def xor_bytes(data: bytes) -> int:
    value = 0
    for byte in data:
        value ^= byte
    return value


def hi_lo_balance(data: bytes) -> int:
    return sum((byte >> 4) - (byte & 0x0F) for byte in data)


def weighted_sum(data: bytes) -> int:
    return sum((index + 1) * byte for index, byte in enumerate(data))


def nibble_counts(data: bytes) -> tuple[int, int, int, int]:
    hi_total = 0
    lo_total = 0
    hi_gt_lo = 0
    hi_lt_lo = 0
    for byte in data:
        hi = byte >> 4
        lo = byte & 0x0F
        hi_total += hi
        lo_total += lo
        hi_gt_lo += int(hi > lo)
        hi_lt_lo += int(hi < lo)
    return hi_total, lo_total, hi_gt_lo, hi_lt_lo


def fsm_hilo_i(data: bytes, modulus: int, seed: int) -> int:
    state = seed
    for index, byte in enumerate(data):
        state = (state + (byte >> 4) - (byte & 0x0F) + index) % modulus
    return state


def fsm_mul_hilo_i(data: bytes, modulus: int, seed: int) -> int:
    state = seed
    for index, byte in enumerate(data):
        state = (state * 2 + (byte >> 4) + 3 * (byte & 0x0F) + index) % modulus
    return state


def fsm_shift_xor_i(data: bytes, modulus: int, seed: int) -> int:
    state = seed
    for index, byte in enumerate(data):
        state = ((state << 1) ^ byte ^ index) % modulus
    return state


def parser_counts(data: bytes, mode: str) -> tuple[int, int]:
    zero_count = 0
    copy_count = 0
    for byte in data:
        hi = byte >> 4
        lo = byte & 0x0F
        if mode == "hi_zero_lo_copy":
            zero_step, copy_step = hi, lo
        elif mode == "lo_zero_hi_copy":
            zero_step, copy_step = lo, hi
        elif mode == "hi_copy_lo_zero":
            copy_step, zero_step = hi, lo
        elif mode == "lo_copy_hi_zero":
            copy_step, zero_step = lo, hi
        else:
            raise ValueError(f"unknown mode: {mode}")
        zero_count += zero_step
        copy_count += copy_step
    return zero_count, copy_count


def state_entries(row: dict[str, str]) -> list[tuple[str, str, str]]:
    window = safe_bytes_fromhex(row.get("control_window_hex", ""))
    offset = int_value(row, "source_offset")
    before = window[:offset] if offset >= 0 else b""
    through = window[: offset + 1] if offset >= 0 else b""
    entries: list[tuple[str, str, str]] = []

    for label, data in (("before", before), ("through", through)):
        byte_sum = sum(data)
        byte_xor = xor_bytes(data)
        byte_weighted = weighted_sum(data)
        balance = hi_lo_balance(data)
        hi_total, lo_total, hi_gt_lo, hi_lt_lo = nibble_counts(data)
        for modulus in (2, 3, 4, 5, 7, 8, 11, 16, 32):
            entries.extend(
                [
                    ("prefix_accumulator", f"{label}_sum_mod{modulus}", str(byte_sum % modulus)),
                    ("prefix_accumulator", f"{label}_xor_mod{modulus}", str(byte_xor % modulus)),
                    ("prefix_accumulator", f"{label}_weighted_mod{modulus}", str(byte_weighted % modulus)),
                    ("prefix_accumulator", f"{label}_hi_lo_balance_mod{modulus}", str(balance % modulus)),
                    ("nibble_counter", f"{label}_hi_total_mod{modulus}", str(hi_total % modulus)),
                    ("nibble_counter", f"{label}_lo_total_mod{modulus}", str(lo_total % modulus)),
                    ("nibble_counter", f"{label}_hi_gt_lo_mod{modulus}", str(hi_gt_lo % modulus)),
                    ("nibble_counter", f"{label}_hi_lt_lo_mod{modulus}", str(hi_lt_lo % modulus)),
                ]
            )
        entries.extend(
            [
                ("prefix_accumulator", f"{label}_sum_xor_mod16", f"{byte_sum % 16}|{byte_xor % 16}"),
                ("nibble_counter", f"{label}_balance_counts_mod16", f"{balance % 16}|{hi_gt_lo % 8}|{hi_lt_lo % 8}"),
                ("nibble_counter", f"{label}_hi_lo_totals_mod16", f"{hi_total % 16}|{lo_total % 16}"),
            ]
        )

    for label, data in (("before", before), ("through", through)):
        for modulus in (3, 4, 5, 7, 8, 16):
            for seed in (0, 1, 2, 3):
                entries.extend(
                    [
                        ("fsm", f"{label}_hilo_i_mod{modulus}", f"seed{seed}:{fsm_hilo_i(data, modulus, seed)}"),
                        (
                            "fsm",
                            f"{label}_mul_hilo_i_mod{modulus}",
                            f"seed{seed}:{fsm_mul_hilo_i(data, modulus, seed)}",
                        ),
                        (
                            "fsm",
                            f"{label}_shift_xor_i_mod{modulus}",
                            f"seed{seed}:{fsm_shift_xor_i(data, modulus, seed)}",
                        ),
                    ]
                )

    for label, data in (("before", before), ("through", through)):
        for mode in ("hi_zero_lo_copy", "lo_zero_hi_copy", "hi_copy_lo_zero", "lo_copy_hi_zero"):
            zero_count, copy_count = parser_counts(data, mode)
            for modulus in (4, 8, 16, 32):
                entries.extend(
                    [
                        ("parser_counter", f"{label}_{mode}_z_minus_c_mod{modulus}", str((zero_count - copy_count) % modulus)),
                        ("parser_counter", f"{label}_{mode}_z_copy_mod{modulus}", f"{zero_count % modulus}|{copy_count % modulus}"),
                    ]
                )
    return entries


def build_state_values(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for row in rows:
        window = safe_bytes_fromhex(row.get("control_window_hex", ""))
        offset = int_value(row, "source_offset")
        before = window[:offset] if offset >= 0 else b""
        through = window[: offset + 1] if offset >= 0 else b""
        issues = [issue for issue in row.get("issues", "").split(";") if issue]
        if not window:
            issues.append("missing_control_window")
        if offset < 0 or offset >= len(window):
            issues.append("source_offset_out_of_window")
        zero_count, copy_count = parser_counts(through, "hi_zero_lo_copy")
        state_row = {
            "seed_id": row.get("seed_id", ""),
            "rank": row.get("rank", ""),
            "archive": row.get("archive", ""),
            "archive_tag": row.get("archive_tag", ""),
            "pcx_name": row.get("pcx_name", ""),
            "frontier_id": row.get("frontier_id", ""),
            "span_index": row.get("span_index", ""),
            "run_index": row.get("run_index", ""),
            "op_index": row.get("op_index", ""),
            "start": row.get("start", ""),
            "end": row.get("end", ""),
            "length": row.get("length", ""),
            "candidate_kind": row.get("candidate_kind", ""),
            "palette_index": row.get("palette_index", ""),
            "target_value_hex": row.get("target_value_hex", ""),
            "source_value_hex": row.get("source_value_hex", ""),
            "delta": row.get("delta", ""),
            "source_offset": row.get("source_offset", ""),
            "value_bytes": row.get("value_bytes", "0"),
            "copy_unlock_bytes": row.get("copy_unlock_bytes", "0"),
            "control_window_len": str(len(window)),
            "prefix_len_before": str(len(before)),
            "prefix_len_through": str(len(through)),
            "prefix_sum_before": str(sum(before)),
            "prefix_sum_through": str(sum(through)),
            "prefix_xor_before": str(xor_bytes(before)),
            "prefix_xor_through": str(xor_bytes(through)),
            "prefix_hi_lo_balance_before": str(hi_lo_balance(before)),
            "prefix_hi_lo_balance_through": str(hi_lo_balance(through)),
            "fsm_hilo_mod16": str(fsm_hilo_i(through, 16, 0)),
            "fsm_shift_xor_mod16": str(fsm_shift_xor_i(through, 16, 0)),
            "parser_hi_zero_lo_copy_zc_mod16": f"{zero_count % 16}|{copy_count % 16}",
            "state_entries": "0",
            "issues": ";".join(dict.fromkeys(issue for issue in issues if issue)),
        }
        state_row["state_entries"] = str(len(state_entries(row)))
        output.append(state_row)
    output.sort(
        key=lambda row: (
            row.get("pcx_name", ""),
            int_value(row, "frontier_id"),
            int_value(row, "palette_index"),
            int_value(row, "source_offset"),
        )
    )
    return output


def stable_deltas(rows: list[dict[str, str]]) -> str:
    return "|".join(str(delta) for delta in sorted({int_value(row, "delta") for row in rows}))


def build_selector_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        for scope, family, key in state_entries(row):
            grouped[scope, family, key].append(row)

    output: list[dict[str, str]] = []
    for (scope, family, key), grouped_rows in grouped.items():
        deltas = {int_value(row, "delta") for row in grouped_rows}
        seed_rows = {row.get("seed_id", "") for row in grouped_rows}
        deterministic = len(deltas) == 1
        repeated_deterministic = deterministic and len(seed_rows) > 1
        if repeated_deterministic:
            verdict = "state_repeated_delta_candidate"
        elif deterministic:
            verdict = "state_singleton_delta_review"
        else:
            verdict = "state_delta_conflict"
        sample = grouped_rows[0]
        output.append(
            {
                "state_scope": scope,
                "state_family": family,
                "state_key": key,
                "rows": str(len(grouped_rows)),
                "seed_rows": str(len(seed_rows)),
                "value_bytes": str(sum(int_value(row, "value_bytes") for row in grouped_rows)),
                "deltas_seen": stable_deltas(grouped_rows),
                "deterministic": "1" if deterministic else "0",
                "repeated_deterministic": "1" if repeated_deterministic else "0",
                "verdict": verdict,
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
            }
        )
    output.sort(
        key=lambda row: (
            row.get("state_scope", ""),
            row.get("state_family", ""),
            -int_value(row, "repeated_deterministic"),
            -int_value(row, "value_bytes"),
            row.get("state_key", ""),
        )
    )
    return output


def build_family_rows(selector_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in selector_rows:
        grouped[row.get("state_scope", ""), row.get("state_family", "")].append(row)

    output: list[dict[str, str]] = []
    for (scope, family), rows in grouped.items():
        deterministic = [row for row in rows if row.get("deterministic") == "1"]
        repeated = [row for row in rows if row.get("repeated_deterministic") == "1"]
        singleton = [row for row in deterministic if row.get("repeated_deterministic") != "1"]
        conflicted = [row for row in rows if row.get("deterministic") != "1"]
        if repeated:
            verdict = "state_delta_candidate"
        elif deterministic:
            verdict = "state_singleton_only"
        else:
            verdict = "state_delta_blocked"
        output.append(
            {
                "state_scope": scope,
                "state_family": family,
                "groups": str(len(rows)),
                "rows": str(sum(int_value(row, "rows") for row in rows)),
                "value_bytes": str(sum(int_value(row, "value_bytes") for row in rows)),
                "deterministic_groups": str(len(deterministic)),
                "deterministic_bytes": str(sum(int_value(row, "value_bytes") for row in deterministic)),
                "repeated_deterministic_groups": str(len(repeated)),
                "repeated_deterministic_bytes": str(sum(int_value(row, "value_bytes") for row in repeated)),
                "singleton_deterministic_groups": str(len(singleton)),
                "singleton_deterministic_bytes": str(sum(int_value(row, "value_bytes") for row in singleton)),
                "conflicted_groups": str(len(conflicted)),
                "conflicted_bytes": str(sum(int_value(row, "value_bytes") for row in conflicted)),
                "verdict": verdict,
            }
        )
    output.sort(
        key=lambda row: (
            -int_value(row, "repeated_deterministic_bytes"),
            -int_value(row, "deterministic_bytes"),
            -int_value(row, "conflicted_bytes"),
            row.get("state_scope", ""),
            row.get("state_family", ""),
        )
    )
    return output


def build_scope_rows(family_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in family_rows:
        grouped[row.get("state_scope", "")].append(row)

    output: list[dict[str, str]] = []
    for scope, rows in grouped.items():
        repeated_groups = sum(int_value(row, "repeated_deterministic_groups") for row in rows)
        deterministic_groups = sum(int_value(row, "deterministic_groups") for row in rows)
        if repeated_groups:
            verdict = "state_scope_candidate"
        elif deterministic_groups:
            verdict = "state_scope_singleton_only"
        else:
            verdict = "state_scope_blocked"
        output.append(
            {
                "state_scope": scope,
                "families": str(len(rows)),
                "groups": str(sum(int_value(row, "groups") for row in rows)),
                "rows": str(sum(int_value(row, "rows") for row in rows)),
                "value_bytes": str(sum(int_value(row, "value_bytes") for row in rows)),
                "deterministic_groups": str(deterministic_groups),
                "deterministic_bytes": str(sum(int_value(row, "deterministic_bytes") for row in rows)),
                "repeated_deterministic_groups": str(repeated_groups),
                "repeated_deterministic_bytes": str(
                    sum(int_value(row, "repeated_deterministic_bytes") for row in rows)
                ),
                "singleton_deterministic_groups": str(
                    sum(int_value(row, "singleton_deterministic_groups") for row in rows)
                ),
                "singleton_deterministic_bytes": str(
                    sum(int_value(row, "singleton_deterministic_bytes") for row in rows)
                ),
                "conflicted_groups": str(sum(int_value(row, "conflicted_groups") for row in rows)),
                "conflicted_bytes": str(sum(int_value(row, "conflicted_bytes") for row in rows)),
                "verdict": verdict,
            }
        )
    output.sort(
        key=lambda row: (
            -int_value(row, "repeated_deterministic_bytes"),
            -int_value(row, "deterministic_bytes"),
            row.get("state_scope", ""),
        )
    )
    return output


def repeated_bytes_for_scope(scope_rows: list[dict[str, str]], scope: str) -> str:
    return str(
        sum(
            int_value(row, "repeated_deterministic_bytes")
            for row in scope_rows
            if row.get("state_scope", "") == scope
        )
    )


def build_summary(
    state_values: list[dict[str, str]],
    selector_rows: list[dict[str, str]],
    family_rows: list[dict[str, str]],
    scope_rows: list[dict[str, str]],
) -> dict[str, str]:
    deterministic = [row for row in selector_rows if row.get("deterministic") == "1"]
    repeated = [row for row in selector_rows if row.get("repeated_deterministic") == "1"]
    singleton = [row for row in deterministic if row.get("repeated_deterministic") != "1"]
    conflicted = [row for row in selector_rows if row.get("deterministic") != "1"]
    best_family = max(
        family_rows,
        key=lambda row: (
            int_value(row, "repeated_deterministic_bytes"),
            int_value(row, "deterministic_bytes"),
            -int_value(row, "conflicted_bytes"),
        ),
        default={},
    )
    best_conflicted = max(family_rows, key=lambda row: int_value(row, "conflicted_bytes"), default={})
    copy_unlock_by_seed: dict[str, int] = {}
    seed_bytes_by_seed: dict[str, int] = {}
    for row in state_values:
        copy_unlock_by_seed.setdefault(row.get("seed_id", ""), int_value(row, "copy_unlock_bytes"))
        seed_bytes_by_seed.setdefault(row.get("seed_id", ""), int_value(row, "length"))
    return {
        "scope": "total",
        "mapping_rows": str(len(state_values)),
        "mapping_value_bytes": str(sum(int_value(row, "value_bytes") for row in state_values)),
        "state_scopes": str(len(scope_rows)),
        "state_families": str(len(family_rows)),
        "state_groups": str(len(selector_rows)),
        "deterministic_groups": str(len(deterministic)),
        "deterministic_bytes": str(sum(int_value(row, "value_bytes") for row in deterministic)),
        "repeated_deterministic_groups": str(len(repeated)),
        "repeated_deterministic_bytes": str(sum(int_value(row, "value_bytes") for row in repeated)),
        "singleton_deterministic_groups": str(len(singleton)),
        "singleton_deterministic_bytes": str(sum(int_value(row, "value_bytes") for row in singleton)),
        "conflicted_groups": str(len(conflicted)),
        "conflicted_bytes": str(sum(int_value(row, "value_bytes") for row in conflicted)),
        "prefix_accumulator_repeated_bytes": repeated_bytes_for_scope(scope_rows, "prefix_accumulator"),
        "fsm_repeated_bytes": repeated_bytes_for_scope(scope_rows, "fsm"),
        "nibble_counter_repeated_bytes": repeated_bytes_for_scope(scope_rows, "nibble_counter"),
        "parser_counter_repeated_bytes": repeated_bytes_for_scope(scope_rows, "parser_counter"),
        "best_state_family": best_family.get("state_family", ""),
        "best_state_repeated_deterministic_bytes": best_family.get("repeated_deterministic_bytes", "0"),
        "best_state_conflicted_bytes": best_conflicted.get("conflicted_bytes", "0"),
        "delta_values": str(len({row.get("delta", "") for row in state_values})),
        "copy_unlock_rows": str(sum(1 for value in copy_unlock_by_seed.values() if value)),
        "copy_unlock_bytes": str(sum(copy_unlock_by_seed.values())),
        "total_potential_bytes": str(sum(seed_bytes_by_seed.values()) + sum(copy_unlock_by_seed.values())),
        "promotion_ready_bytes": "0",
        "issue_rows": str(sum(1 for row in state_values if row.get("issues"))),
    }


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 220) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    state_values: list[dict[str, str]],
    selector_rows: list[dict[str, str]],
    family_rows: list[dict[str, str]],
    scope_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    files = [
        ("summary.csv", output_dir / "summary.csv"),
        ("state_values.csv", output_dir / "state_values.csv"),
        ("by_state_selector.csv", output_dir / "by_state_selector.csv"),
        ("by_state_family.csv", output_dir / "by_state_family.csv"),
        ("by_state_scope.csv", output_dir / "by_state_scope.csv"),
    ]
    links = " ".join(
        f'<a href="{html.escape(relative_href(output_dir / "index.html", path))}">{html.escape(label)}</a>'
        for label, path in files
    )
    data_json = json.dumps(
        {
            "summary": summary,
            "scopeRows": scope_rows,
            "familyRows": family_rows[:80],
            "selectorRows": selector_rows[:140],
            "stateValues": state_values,
        },
        ensure_ascii=True,
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
:root {{ color-scheme: dark; --bg: #0d1113; --panel: #151b1e; --line: #2b3438; --text: #e7ecef; --muted: #9aa8ae; --accent: #7cc7ff; --ok: #7bd88f; --warn: #f6c177; }}
body {{ margin: 0; background: var(--bg); color: var(--text); font: 14px/1.45 system-ui, -apple-system, Segoe UI, sans-serif; }}
.wrap {{ max-width: 1480px; margin: 0 auto; padding: 0 16px; }}
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
table {{ width: 100%; border-collapse: collapse; min-width: 1520px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Checks stateful prefix accumulators and small finite-state machines for the gradient seed delta.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Mapping bytes</div><div class="value warn">{summary['mapping_value_bytes']}</div></div>
    <div class="stat"><div class="label">State groups</div><div class="value">{summary['state_groups']}</div></div>
    <div class="stat"><div class="label">Repeated deterministic bytes</div><div class="value">{summary['repeated_deterministic_bytes']}</div></div>
    <div class="stat"><div class="label">Conflicted bytes</div><div class="value warn">{summary['conflicted_bytes']}</div></div>
    <div class="stat"><div class="label">Potential bytes</div><div class="value">{summary['total_potential_bytes']}</div></div>
    <div class="stat"><div class="label">Promotion-ready bytes</div><div class="value ok">{summary['promotion_ready_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2><div>{links}</div></section>
  <section class="panel"><h2>State scopes</h2>{render_table(scope_rows, SCOPE_FIELDNAMES)}</section>
  <section class="panel"><h2>State families</h2>{render_table(family_rows, FAMILY_FIELDNAMES)}</section>
  <section class="panel"><h2>State selectors</h2>{render_table(selector_rows, SELECTOR_FIELDNAMES)}</section>
  <section class="panel"><h2>Mappings</h2>{render_table(state_values, STATE_VALUE_FIELDNAMES)}</section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_GRADIENT_SEED_DELTA_STATE_PROBE = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe stateful source/control selectors for .tex gradient seed deltas.")
    parser.add_argument("--phase-values", type=Path, default=DEFAULT_PHASE_VALUES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Tiny Nonzero Gap Gradient Seed Delta State Probe",
    )
    args = parser.parse_args()

    phase_rows = read_csv(args.phase_values)
    state_values = build_state_values(phase_rows)
    selector_rows = build_selector_rows(phase_rows)
    family_rows = build_family_rows(selector_rows)
    scope_rows = build_scope_rows(family_rows)
    summary = build_summary(state_values, selector_rows, family_rows, scope_rows)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "state_values.csv", STATE_VALUE_FIELDNAMES, state_values)
    write_csv(args.output / "by_state_selector.csv", SELECTOR_FIELDNAMES, selector_rows)
    write_csv(args.output / "by_state_family.csv", FAMILY_FIELDNAMES, family_rows)
    write_csv(args.output / "by_state_scope.csv", SCOPE_FIELDNAMES, scope_rows)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, state_values, selector_rows, family_rows, scope_rows, args.output, args.title))

    print(f"Mapping bytes: {summary['mapping_value_bytes']}")
    print(f"State groups: {summary['state_groups']}")
    print(f"Repeated deterministic bytes: {summary['repeated_deterministic_bytes']}")
    print(f"Conflicted bytes: {summary['conflicted_bytes']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
