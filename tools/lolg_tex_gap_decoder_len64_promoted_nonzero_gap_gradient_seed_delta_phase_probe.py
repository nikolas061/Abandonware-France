#!/usr/bin/env python3
"""Probe broad source/control phase selectors for gradient seed deltas."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import defaultdict
from pathlib import Path

from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_fill_selector_probe import (
    DEFAULT_OPERATIONS,
    safe_bytes_fromhex,
)
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_delta_phase_probe")
DEFAULT_VALUES = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_delta_selector_probe/values.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "mapping_rows",
    "mapping_value_bytes",
    "selector_scopes",
    "selector_families",
    "selector_groups",
    "deterministic_groups",
    "deterministic_bytes",
    "repeated_deterministic_groups",
    "repeated_deterministic_bytes",
    "singleton_deterministic_groups",
    "singleton_deterministic_bytes",
    "conflicted_groups",
    "conflicted_bytes",
    "source_value_phase_repeated_bytes",
    "broad_control_phase_repeated_bytes",
    "wide_relative_repeated_bytes",
    "best_phase_family",
    "best_phase_repeated_deterministic_bytes",
    "best_phase_conflicted_bytes",
    "delta_values",
    "copy_unlock_rows",
    "copy_unlock_bytes",
    "total_potential_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

PHASE_VALUE_FIELDNAMES = [
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
    "control_window_hex",
    "control_window_prefix8_hex",
    "control_window_suffix8_hex",
    "source_offset_mod2",
    "source_offset_mod4",
    "source_offset_bucket4",
    "source_value_offset_key",
    "source_value_mod4_key",
    "source_value_bucket4_key",
    "rel_window_r4_hex",
    "rel_window_r8_hex",
    "selector_entries",
    "issues",
]

SELECTOR_FIELDNAMES = [
    "selector_scope",
    "selector_family",
    "selector_key",
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
    "selector_scope",
    "selector_family",
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
    "selector_scope",
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


def operation_key(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    return (
        row.get("rank", ""),
        row.get("pcx_name", ""),
        row.get("frontier_id", ""),
        row.get("start", ""),
        row.get("end", ""),
    )


def operation_map(rows: list[dict[str, str]]) -> dict[tuple[str, str, str, str, str], bytes]:
    return {
        (
            row.get("rank", ""),
            row.get("pcx_name", ""),
            row.get("frontier_id", ""),
            row.get("expected_start", ""),
            row.get("expected_end", ""),
        ): safe_bytes_fromhex(row.get("control_window_hex", ""))
        for row in rows
    }


def byte_hex(window: bytes, offset: int) -> str:
    if offset < 0 or offset >= len(window):
        return ""
    return f"{window[offset]:02x}"


def slice_hex(window: bytes, start: int, end: int) -> str:
    return window[max(0, start) : min(len(window), end)].hex()


def offset_bucket4(offset: int) -> str:
    start = (offset // 4) * 4
    return f"{start}-{start + 3}"


def stable_deltas(rows: list[dict[str, str]]) -> str:
    return "|".join(str(delta) for delta in sorted({int_value(row, "delta") for row in rows}))


def selector_entries(row: dict[str, str]) -> list[tuple[str, str, str]]:
    window = safe_bytes_fromhex(row.get("control_window_hex", ""))
    offset = int_value(row, "source_offset")
    source_value = row.get("source_value_hex", "")
    length = int_value(row, "length")
    start = int_value(row, "start")
    entries: list[tuple[str, str, str]] = [
        ("source_phase", "source_value", source_value),
        ("source_phase", "source_offset", str(offset)),
        ("source_phase", "source_offset_mod2", str(offset % 2)),
        ("source_phase", "source_offset_mod4", str(offset % 4)),
        ("source_phase", "source_offset_bucket4", offset_bucket4(offset)),
        ("source_phase", "source_value_offset", f"{source_value}|{offset}"),
        ("source_phase", "source_value_mod2", f"{source_value}|{offset % 2}"),
        ("source_phase", "source_value_mod4", f"{source_value}|{offset % 4}"),
        ("source_phase", "source_value_bucket4", f"{source_value}|{offset_bucket4(offset)}"),
        ("source_phase", "source_value_window_len", f"{source_value}|{len(window)}"),
        ("source_phase", "source_offset_len_phase", f"{offset}|{length % 8}"),
        ("source_phase", "start_mod64_source_offset", f"{start % 64}|{offset}"),
        ("control_profile", "control_window_len", str(len(window))),
        ("control_profile", "control_prefix4", window[:4].hex()),
        ("control_profile", "control_prefix8", window[:8].hex()),
        ("control_profile", "control_suffix4", window[-4:].hex()),
        ("control_profile", "control_suffix8", window[-8:].hex()),
    ]

    for pos, value in enumerate(window):
        value_hex = f"{value:02x}"
        entries.append(("control_absolute", f"abs_byte_{pos}", value_hex))
        entries.append(("control_positionless", "byte_value", value_hex))
        entries.append(("control_positionless", "byte_value_mod4_pos", f"{value_hex}|{pos % 4}"))
    for pos in range(max(0, len(window) - 1)):
        pair_hex = window[pos : pos + 2].hex()
        entries.append(("control_absolute", f"abs_pair_{pos}", pair_hex))
        entries.append(("control_positionless", "pair_value", pair_hex))
        entries.append(("control_positionless", "pair_value_mod4_pos", f"{pair_hex}|{pos % 4}"))
    for pos in range(max(0, len(window) - 2)):
        tri_hex = window[pos : pos + 3].hex()
        entries.append(("control_absolute", f"abs_tri_{pos}", tri_hex))
        entries.append(("control_positionless", "tri_value", tri_hex))
        entries.append(("control_positionless", "tri_value_mod4_pos", f"{tri_hex}|{pos % 4}"))

    for rel in range(-10, 11):
        entries.append(("control_relative", f"rel_byte_{rel}", byte_hex(window, offset + rel)))
    for rel in range(-8, 9):
        start_pos = offset + rel
        if 0 <= start_pos < len(window) - 1:
            entries.append(("control_relative", f"rel_pair_{rel}", window[start_pos : start_pos + 2].hex()))
    for radius in (2, 3, 4, 5, 6, 8, 10):
        start_pos = max(0, offset - radius)
        end_pos = min(len(window), offset + radius + 1)
        anchored_offset = offset - start_pos
        entries.append(("control_relative", f"rel_window_r{radius}", f"{anchored_offset}:{window[start_pos:end_pos].hex()}"))
        entries.append(("control_relative", f"rel_window_r{radius}_unanchored", window[start_pos:end_pos].hex()))

    return [(scope, family, key) for scope, family, key in entries if key]


def build_phase_values(
    value_rows: list[dict[str, str]],
    operations: dict[tuple[str, str, str, str, str], bytes],
) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for row in value_rows:
        issues = [issue for issue in row.get("issues", "").split(";") if issue]
        window = operations.get(operation_key(row), b"")
        if not window:
            issues.append("missing_control_window")
        offset = int_value(row, "source_offset")
        if offset < 0 or offset >= len(window):
            issues.append("source_offset_out_of_window")
        source_value = row.get("source_value_hex", "")
        rel4 = slice_hex(window, offset - 4, offset + 5)
        rel8 = slice_hex(window, offset - 8, offset + 9)
        phase_row = {
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
            "source_value_hex": source_value,
            "delta": row.get("delta", ""),
            "source_offset": row.get("source_offset", ""),
            "value_bytes": row.get("value_bytes", "0"),
            "copy_unlock_bytes": row.get("copy_unlock_bytes", "0"),
            "control_window_len": str(len(window)),
            "control_window_prefix8_hex": window[:8].hex(),
            "control_window_suffix8_hex": window[-8:].hex(),
            "source_offset_mod2": str(offset % 2),
            "source_offset_mod4": str(offset % 4),
            "source_offset_bucket4": offset_bucket4(offset),
            "source_value_offset_key": f"{source_value}|{offset}",
            "source_value_mod4_key": f"{source_value}|{offset % 4}",
            "source_value_bucket4_key": f"{source_value}|{offset_bucket4(offset)}",
            "rel_window_r4_hex": rel4,
            "rel_window_r8_hex": rel8,
            "control_window_hex": window.hex(),
            "issues": ";".join(dict.fromkeys(issue for issue in issues if issue)),
        }
        phase_row["selector_entries"] = str(len(selector_entries(phase_row)))
        output.append(phase_row)
    output.sort(
        key=lambda row: (
            row.get("pcx_name", ""),
            int_value(row, "frontier_id"),
            int_value(row, "palette_index"),
            int_value(row, "source_offset"),
        )
    )
    return output


def build_selector_rows(phase_values: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in phase_values:
        for scope, family, key in selector_entries(row):
            grouped[scope, family, key].append(row)

    output: list[dict[str, str]] = []
    for (scope, family, key), rows in grouped.items():
        deltas = {int_value(row, "delta") for row in rows}
        seed_rows = {row.get("seed_id", "") for row in rows}
        deterministic = len(deltas) == 1
        repeated_deterministic = deterministic and len(seed_rows) > 1
        if repeated_deterministic:
            verdict = "phase_repeated_delta_candidate"
        elif deterministic:
            verdict = "phase_singleton_delta_review"
        else:
            verdict = "phase_delta_conflict"
        sample = rows[0]
        output.append(
            {
                "selector_scope": scope,
                "selector_family": family,
                "selector_key": key,
                "rows": str(len(rows)),
                "seed_rows": str(len(seed_rows)),
                "value_bytes": str(sum(int_value(row, "value_bytes") for row in rows)),
                "deltas_seen": stable_deltas(rows),
                "deterministic": "1" if deterministic else "0",
                "repeated_deterministic": "1" if repeated_deterministic else "0",
                "verdict": verdict,
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
            }
        )
    output.sort(
        key=lambda row: (
            row.get("selector_scope", ""),
            row.get("selector_family", ""),
            -int_value(row, "repeated_deterministic"),
            -int_value(row, "value_bytes"),
            row.get("selector_key", ""),
        )
    )
    return output


def build_family_rows(selector_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in selector_rows:
        grouped[row.get("selector_scope", ""), row.get("selector_family", "")].append(row)

    output: list[dict[str, str]] = []
    for (scope, family), rows in grouped.items():
        deterministic = [row for row in rows if row.get("deterministic") == "1"]
        repeated = [row for row in rows if row.get("repeated_deterministic") == "1"]
        singleton = [row for row in deterministic if row.get("repeated_deterministic") != "1"]
        conflicted = [row for row in rows if row.get("deterministic") != "1"]
        if repeated:
            verdict = "phase_delta_candidate"
        elif deterministic:
            verdict = "phase_singleton_only"
        else:
            verdict = "phase_delta_blocked"
        output.append(
            {
                "selector_scope": scope,
                "selector_family": family,
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
            row.get("selector_scope", ""),
            row.get("selector_family", ""),
        )
    )
    return output


def build_scope_rows(family_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in family_rows:
        grouped[row.get("selector_scope", "")].append(row)

    output: list[dict[str, str]] = []
    for scope, rows in grouped.items():
        repeated_groups = sum(int_value(row, "repeated_deterministic_groups") for row in rows)
        deterministic_groups = sum(int_value(row, "deterministic_groups") for row in rows)
        if repeated_groups:
            verdict = "phase_scope_candidate"
        elif deterministic_groups:
            verdict = "phase_scope_singleton_only"
        else:
            verdict = "phase_scope_blocked"
        output.append(
            {
                "selector_scope": scope,
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
            row.get("selector_scope", ""),
        )
    )
    return output


def repeated_bytes_for_scopes(scope_rows: list[dict[str, str]], scopes: set[str]) -> int:
    return sum(
        int_value(row, "repeated_deterministic_bytes")
        for row in scope_rows
        if row.get("selector_scope", "") in scopes
    )


def build_summary(
    phase_values: list[dict[str, str]],
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
    for row in phase_values:
        copy_unlock_by_seed.setdefault(row.get("seed_id", ""), int_value(row, "copy_unlock_bytes"))
        seed_bytes_by_seed.setdefault(row.get("seed_id", ""), int_value(row, "length"))
    return {
        "scope": "total",
        "mapping_rows": str(len(phase_values)),
        "mapping_value_bytes": str(sum(int_value(row, "value_bytes") for row in phase_values)),
        "selector_scopes": str(len(scope_rows)),
        "selector_families": str(len(family_rows)),
        "selector_groups": str(len(selector_rows)),
        "deterministic_groups": str(len(deterministic)),
        "deterministic_bytes": str(sum(int_value(row, "value_bytes") for row in deterministic)),
        "repeated_deterministic_groups": str(len(repeated)),
        "repeated_deterministic_bytes": str(sum(int_value(row, "value_bytes") for row in repeated)),
        "singleton_deterministic_groups": str(len(singleton)),
        "singleton_deterministic_bytes": str(sum(int_value(row, "value_bytes") for row in singleton)),
        "conflicted_groups": str(len(conflicted)),
        "conflicted_bytes": str(sum(int_value(row, "value_bytes") for row in conflicted)),
        "source_value_phase_repeated_bytes": str(repeated_bytes_for_scopes(scope_rows, {"source_phase"})),
        "broad_control_phase_repeated_bytes": str(
            repeated_bytes_for_scopes(scope_rows, {"control_absolute", "control_positionless", "control_profile"})
        ),
        "wide_relative_repeated_bytes": str(repeated_bytes_for_scopes(scope_rows, {"control_relative"})),
        "best_phase_family": best_family.get("selector_family", ""),
        "best_phase_repeated_deterministic_bytes": best_family.get("repeated_deterministic_bytes", "0"),
        "best_phase_conflicted_bytes": best_conflicted.get("conflicted_bytes", "0"),
        "delta_values": str(len({row.get("delta", "") for row in phase_values})),
        "copy_unlock_rows": str(sum(1 for value in copy_unlock_by_seed.values() if value)),
        "copy_unlock_bytes": str(sum(copy_unlock_by_seed.values())),
        "total_potential_bytes": str(sum(seed_bytes_by_seed.values()) + sum(copy_unlock_by_seed.values())),
        "promotion_ready_bytes": "0",
        "issue_rows": str(sum(1 for row in phase_values if row.get("issues"))),
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
    phase_values: list[dict[str, str]],
    selector_rows: list[dict[str, str]],
    family_rows: list[dict[str, str]],
    scope_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    files = [
        ("summary.csv", output_dir / "summary.csv"),
        ("phase_values.csv", output_dir / "phase_values.csv"),
        ("by_phase_selector.csv", output_dir / "by_phase_selector.csv"),
        ("by_phase_family.csv", output_dir / "by_phase_family.csv"),
        ("by_phase_scope.csv", output_dir / "by_phase_scope.csv"),
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
            "phaseValues": phase_values,
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
    <div class="sub">Checks broad source/control phase selectors for the per-value gradient seed delta.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Mapping bytes</div><div class="value warn">{summary['mapping_value_bytes']}</div></div>
    <div class="stat"><div class="label">Selector groups</div><div class="value">{summary['selector_groups']}</div></div>
    <div class="stat"><div class="label">Repeated deterministic bytes</div><div class="value">{summary['repeated_deterministic_bytes']}</div></div>
    <div class="stat"><div class="label">Conflicted bytes</div><div class="value warn">{summary['conflicted_bytes']}</div></div>
    <div class="stat"><div class="label">Potential bytes</div><div class="value">{summary['total_potential_bytes']}</div></div>
    <div class="stat"><div class="label">Promotion-ready bytes</div><div class="value ok">{summary['promotion_ready_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2><div>{links}</div></section>
  <section class="panel"><h2>Phase scopes</h2>{render_table(scope_rows, SCOPE_FIELDNAMES)}</section>
  <section class="panel"><h2>Phase families</h2>{render_table(family_rows, FAMILY_FIELDNAMES)}</section>
  <section class="panel"><h2>Phase selectors</h2>{render_table(selector_rows, SELECTOR_FIELDNAMES)}</section>
  <section class="panel"><h2>Mappings</h2>{render_table(phase_values, PHASE_VALUE_FIELDNAMES)}</section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_GRADIENT_SEED_DELTA_PHASE_PROBE = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe broad source/control phase selectors for .tex gradient seed deltas.")
    parser.add_argument("--values", type=Path, default=DEFAULT_VALUES)
    parser.add_argument("--operations", type=Path, default=DEFAULT_OPERATIONS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Tiny Nonzero Gap Gradient Seed Delta Phase Probe",
    )
    args = parser.parse_args()

    phase_values = build_phase_values(read_csv(args.values), operation_map(read_csv(args.operations)))
    selector_rows = build_selector_rows(phase_values)
    family_rows = build_family_rows(selector_rows)
    scope_rows = build_scope_rows(family_rows)
    summary = build_summary(phase_values, selector_rows, family_rows, scope_rows)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "phase_values.csv", PHASE_VALUE_FIELDNAMES, phase_values)
    write_csv(args.output / "by_phase_selector.csv", SELECTOR_FIELDNAMES, selector_rows)
    write_csv(args.output / "by_phase_family.csv", FAMILY_FIELDNAMES, family_rows)
    write_csv(args.output / "by_phase_scope.csv", SCOPE_FIELDNAMES, scope_rows)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, phase_values, selector_rows, family_rows, scope_rows, args.output, args.title))

    print(f"Mapping bytes: {summary['mapping_value_bytes']}")
    print(f"Selector groups: {summary['selector_groups']}")
    print(f"Repeated deterministic bytes: {summary['repeated_deterministic_bytes']}")
    print(f"Conflicted bytes: {summary['conflicted_bytes']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
