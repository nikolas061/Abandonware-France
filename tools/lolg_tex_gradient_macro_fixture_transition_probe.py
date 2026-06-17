#!/usr/bin/env python3
"""Probe abstract fixture/op transition selectors across gradient macro rows."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_micro_mixed_value_payload_state_opcode_probe import int_value, ratio


DEFAULT_INPUT_ROWS = Path("output/tex_gradient_macro_phase_sequence/rows.csv")
DEFAULT_OUTPUT = Path("output/tex_gradient_macro_fixture_transition")

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "target_bytes",
    "target_kinds",
    "selector_families",
    "selector_groups",
    "repeated_selector_groups",
    "deterministic_repeated_groups",
    "deterministic_repeated_evidence_bytes",
    "conflicted_groups",
    "conflicted_evidence_bytes",
    "singleton_groups",
    "singleton_evidence_bytes",
    "transition_deterministic_evidence_bytes",
    "transition_conflicted_evidence_bytes",
    "payload_deterministic_evidence_bytes",
    "payload_conflicted_evidence_bytes",
    "best_transition_target_kind",
    "best_transition_selector_family",
    "best_transition_deterministic_bytes",
    "best_transition_conflicted_bytes",
    "best_transition_singleton_bytes",
    "low_conflict_transition_target_kind",
    "low_conflict_transition_selector_family",
    "low_conflict_transition_deterministic_bytes",
    "low_conflict_transition_conflicted_bytes",
    "low_conflict_transition_singleton_bytes",
    "best_payload_target_kind",
    "best_payload_selector_family",
    "best_payload_deterministic_bytes",
    "best_payload_conflicted_bytes",
    "best_payload_singleton_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

ROW_FIELDNAMES = [
    "rank",
    "archive",
    "pcx_name",
    "frontier_id",
    "span_index",
    "op_index",
    "length",
    "start",
    "end",
    "length_bucket",
    "length_band8",
    "span_phase4",
    "op_phase4",
    "op_phase8",
    "frontier_count_bucket",
    "frontier_position",
    "prev_op_gap",
    "next_op_gap",
    "prev_span_gap",
    "next_span_gap",
    "prev_start_gap",
    "next_start_gap",
    "fixture_rule",
    "fixture_frontier",
    "fixture_op0",
    "fixture_op1",
    "fixture_opcode_pair",
    "fixture_op0_hi",
    "fixture_op1_hi",
    "fixture_hi_pair",
    "fixture_lo_pair",
    "fixture_opcode_delta",
    "fixture_opcode_order",
    "fixture_skip",
    "fixture_skip_bucket",
    "control_anchor_mod64",
    "start_anchor_mod64",
    "payload_signature",
    "band_shape_key",
    "step_shape_key",
    "dominant_delta",
    "top_nibble",
    "gradient_class",
    "issues",
]

GROUP_FIELDNAMES = [
    "rank",
    "target_kind",
    "selector_type",
    "selector_family",
    "selector_key",
    "rows",
    "bytes",
    "target_values",
    "dominant_value",
    "dominant_ratio",
    "deterministic_bytes",
    "conflicted_bytes",
    "singleton_bytes",
    "sample_pcx",
    "sample_frontier_id",
    "verdict",
]

FAMILY_FIELDNAMES = [
    "rank",
    "target_kind",
    "selector_type",
    "selector_family",
    "groups",
    "repeated_groups",
    "repeated_evidence_bytes",
    "deterministic_repeated_groups",
    "deterministic_repeated_evidence_bytes",
    "conflicted_groups",
    "conflicted_evidence_bytes",
    "singleton_groups",
    "singleton_evidence_bytes",
    "best_group_key",
    "best_group_bytes",
    "best_group_values",
    "verdict",
]

COARSE_TARGETS = {"dominant_delta", "top_nibble", "gradient_class"}
PAYLOAD_TARGETS = {"exact_payload", "band_shape", "step_shape"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def bucket(value: int) -> str:
    if value <= 1:
        return str(value)
    if value <= 4:
        return "2-4"
    if value <= 8:
        return "5-8"
    if value <= 16:
        return "9-16"
    return "17+"


def parse_fixture(text: str) -> dict[str, str]:
    parts: dict[str, str] = {}
    for part in text.split("|"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        parts[key] = value
    return parts


def hex_value(text: str) -> int | None:
    try:
        return int(text, 16)
    except ValueError:
        return None


def fixture_features(fixture: str) -> dict[str, str]:
    parts = parse_fixture(fixture)
    op0_text = parts.get("op0", "")
    op1_text = parts.get("op1", "")
    op0 = hex_value(op0_text)
    op1 = hex_value(op1_text)
    try:
        skip = int(parts.get("skip", "0") or 0)
    except ValueError:
        skip = 0

    if op0 is None or op1 is None:
        op0_hi = op1_hi = hi_pair = lo_pair = opcode_delta = opcode_order = "missing"
        opcode_pair = "missing"
    else:
        op0_hi = f"0x{op0 >> 4:x}"
        op1_hi = f"0x{op1 >> 4:x}"
        hi_pair = f"{op0_hi}/{op1_hi}"
        lo_pair = f"0x{op0 & 15:x}/0x{op1 & 15:x}"
        opcode_delta = bucket(abs(op1 - op0))
        opcode_order = "up" if op1 > op0 else "down" if op1 < op0 else "same"
        opcode_pair = f"{op0_text}/{op1_text}"

    return {
        "fixture_rule": parts.get("rule", ""),
        "fixture_frontier": parts.get("frontier", ""),
        "fixture_op0": op0_text,
        "fixture_op1": op1_text,
        "fixture_opcode_pair": opcode_pair,
        "fixture_op0_hi": op0_hi,
        "fixture_op1_hi": op1_hi,
        "fixture_hi_pair": hi_pair,
        "fixture_lo_pair": lo_pair,
        "fixture_opcode_delta": opcode_delta,
        "fixture_opcode_order": opcode_order,
        "fixture_skip": str(skip),
        "fixture_skip_bucket": bucket(skip),
    }


def build_rows(input_rows: list[dict[str, str]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for input_row in input_rows:
        features = fixture_features(input_row.get("fixture_rule_key", ""))
        rows.append(
            {
                "rank": len(rows) + 1,
                "archive": input_row.get("archive", ""),
                "pcx_name": input_row.get("pcx_name", ""),
                "frontier_id": input_row.get("frontier_id", ""),
                "span_index": input_row.get("span_index", ""),
                "op_index": input_row.get("op_index", ""),
                "length": input_row.get("length", ""),
                "start": input_row.get("start", ""),
                "end": input_row.get("end", ""),
                "length_bucket": input_row.get("length_bucket", ""),
                "length_band8": input_row.get("length_band8", ""),
                "span_phase4": input_row.get("span_phase4", ""),
                "op_phase4": input_row.get("op_phase4", ""),
                "op_phase8": input_row.get("op_phase8", ""),
                "frontier_count_bucket": input_row.get("frontier_count_bucket", ""),
                "frontier_position": input_row.get("frontier_position", ""),
                "prev_op_gap": input_row.get("prev_op_gap", ""),
                "next_op_gap": input_row.get("next_op_gap", ""),
                "prev_span_gap": input_row.get("prev_span_gap", ""),
                "next_span_gap": input_row.get("next_span_gap", ""),
                "prev_start_gap": input_row.get("prev_start_gap", ""),
                "next_start_gap": input_row.get("next_start_gap", ""),
                **features,
                "control_anchor_mod64": input_row.get("control_anchor_mod64", ""),
                "start_anchor_mod64": input_row.get("start_anchor_mod64", ""),
                "payload_signature": input_row.get("payload_signature", ""),
                "band_shape_key": input_row.get("band_shape_key", ""),
                "step_shape_key": input_row.get("step_shape_key", ""),
                "dominant_delta": input_row.get("dominant_delta", ""),
                "top_nibble": input_row.get("top_nibble", ""),
                "gradient_class": input_row.get("gradient_class", ""),
                "issues": input_row.get("issues", ""),
            }
        )
    return rows


def target_values(row: dict[str, object]) -> dict[str, str]:
    return {
        "dominant_delta": str(row["dominant_delta"]),
        "top_nibble": str(row["top_nibble"]),
        "gradient_class": str(row["gradient_class"]),
        "exact_payload": str(row["payload_signature"]),
        "band_shape": str(row["band_shape_key"]),
        "step_shape": str(row["step_shape_key"]),
    }


def selector_values(row: dict[str, object]) -> dict[str, tuple[str, str]]:
    rule = str(row["fixture_rule"])
    frontier = str(row["fixture_frontier"])
    pair = str(row["fixture_opcode_pair"])
    hi_pair = str(row["fixture_hi_pair"])
    lo_pair = str(row["fixture_lo_pair"])
    delta = str(row["fixture_opcode_delta"])
    order = str(row["fixture_opcode_order"])
    skip = str(row["fixture_skip_bucket"])
    op4 = str(row["op_phase4"])
    op8 = str(row["op_phase8"])
    span4 = str(row["span_phase4"])
    length8 = str(row["length_band8"])
    pos = str(row["frontier_position"])
    count = str(row["frontier_count_bucket"])
    prev_op = str(row["prev_op_gap"])
    next_op = str(row["next_op_gap"])
    prev_span = str(row["prev_span_gap"])
    next_span = str(row["next_span_gap"])
    prev_start = str(row["prev_start_gap"])
    next_start = str(row["next_start_gap"])
    control_mod = str(row["control_anchor_mod64"])
    start_mod = str(row["start_anchor_mod64"])
    return {
        "fixture_rule": ("fixture", f"rule={rule}"),
        "fixture_rule_frontier": ("fixture", f"rule={rule}|frontier={frontier}"),
        "fixture_opcode_pair": ("fixture", f"pair={pair}"),
        "fixture_opcode_hi_pair": ("fixture", f"hi={hi_pair}"),
        "fixture_opcode_lo_pair": ("fixture", f"lo={lo_pair}"),
        "fixture_opcode_delta": ("fixture", f"delta={delta}"),
        "fixture_opcode_order_skip": ("fixture", f"order={order}|skip={skip}"),
        "fixture_rule_opcode_delta": ("fixture", f"rule={rule}|hi={hi_pair}|delta={delta}"),
        "fixture_rule_delta_skip": ("fixture", f"rule={rule}|delta={delta}|skip={skip}"),
        "fixture_pair_skip": ("fixture", f"pair={pair}|skip={skip}"),
        "fixture_hi_delta_phase": ("fixture_phase", f"hi={hi_pair}|delta={delta}|op4={op4}"),
        "fixture_rule_delta_phase": ("fixture_phase", f"rule={rule}|delta={delta}|op4={op4}"),
        "fixture_rule_hi_phase": ("fixture_phase", f"rule={rule}|hi={hi_pair}|op4={op4}"),
        "fixture_pair_phase": ("fixture_phase", f"pair={pair}|op4={op4}"),
        "fixture_pair_skip_phase": ("fixture_phase", f"pair={pair}|skip={skip}|op4={op4}"),
        "fixture_len_phase": ("fixture_phase", f"rule={rule}|delta={delta}|op8={op8}|len8={length8}"),
        "phase_transition": (
            "transition",
            f"op4={op4}|pos={pos}|prev_op={prev_op}|next_op={next_op}",
        ),
        "span_phase_transition": (
            "transition",
            f"span4={span4}|pos={pos}|prev_span={prev_span}|next_span={next_span}",
        ),
        "start_phase_transition": (
            "transition",
            f"pos={pos}|prev_start={prev_start}|next_start={next_start}",
        ),
        "fixture_hi_sequence": (
            "fixture_sequence",
            f"hi={hi_pair}|delta={delta}|prev_op={prev_op}|next_op={next_op}",
        ),
        "fixture_rule_sequence": (
            "fixture_sequence",
            f"rule={rule}|hi={hi_pair}|prev_op={prev_op}|next_op={next_op}",
        ),
        "fixture_pair_sequence": (
            "fixture_sequence",
            f"pair={pair}|prev_op={prev_op}|next_op={next_op}",
        ),
        "fixture_count_position": (
            "fixture_sequence",
            f"rule={rule}|delta={delta}|count={count}|pos={pos}",
        ),
        "control_pair_phase": (
            "fixture_source",
            f"ctrl_mod64={control_mod}|pair={pair}|op4={op4}",
        ),
        "control_hi_phase": (
            "fixture_source",
            f"ctrl_mod64={control_mod}|hi={hi_pair}|delta={delta}|op4={op4}",
        ),
        "start_pair_phase": (
            "fixture_source",
            f"start_mod64={start_mod}|pair={pair}|op4={op4}",
        ),
    }


def build_group_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    target_kinds = target_values(rows[0]).keys() if rows else []
    selector_families = selector_values(rows[0]).keys() if rows else []
    for target_kind in target_kinds:
        for selector_family in selector_families:
            selector_type = selector_values(rows[0])[selector_family][0]
            grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
            for row in rows:
                grouped[selector_values(row)[selector_family][1]].append(row)
            for selector_key, members in grouped.items():
                values = Counter(target_values(row)[target_kind] for row in members)
                dominant_value, dominant_count = values.most_common(1)[0]
                rows_count = len(members)
                bytes_count = sum(int_value(row, "length") for row in members)
                deterministic = len(values) == 1
                repeated = rows_count > 1
                output.append(
                    {
                        "rank": 0,
                        "target_kind": target_kind,
                        "selector_type": selector_type,
                        "selector_family": selector_family,
                        "selector_key": selector_key,
                        "rows": rows_count,
                        "bytes": bytes_count,
                        "target_values": "|".join(f"{value}:{count}" for value, count in values.most_common(8)),
                        "dominant_value": dominant_value,
                        "dominant_ratio": ratio(dominant_count, rows_count),
                        "deterministic_bytes": bytes_count if deterministic and repeated else 0,
                        "conflicted_bytes": bytes_count if not deterministic and repeated else 0,
                        "singleton_bytes": bytes_count if rows_count == 1 else 0,
                        "sample_pcx": members[0].get("pcx_name", ""),
                        "sample_frontier_id": members[0].get("frontier_id", ""),
                        "verdict": (
                            "fixture_transition_deterministic_repeat"
                            if deterministic and repeated
                            else "fixture_transition_conflicted_repeat"
                            if repeated
                            else "fixture_transition_singleton"
                        ),
                    }
                )

    output.sort(
        key=lambda row: (
            str(row["target_kind"]),
            str(row["selector_type"]),
            str(row["selector_family"]),
            -int_value(row, "rows"),
            -int_value(row, "bytes"),
            str(row["selector_key"]),
        )
    )
    for index, row in enumerate(output, start=1):
        row["rank"] = index
    return output


def build_family_rows(group_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, str], list[dict[str, object]]] = defaultdict(list)
    for row in group_rows:
        grouped[(str(row["target_kind"]), str(row["selector_type"]), str(row["selector_family"]))].append(row)

    output: list[dict[str, object]] = []
    for (target_kind, selector_type, selector_family), members in grouped.items():
        repeated = [row for row in members if int_value(row, "rows") > 1]
        deterministic = [row for row in repeated if int_value(row, "deterministic_bytes") > 0]
        conflicted = [row for row in repeated if int_value(row, "conflicted_bytes") > 0]
        singletons = [row for row in members if int_value(row, "rows") == 1]
        deterministic_bytes = sum(int_value(row, "deterministic_bytes") for row in deterministic)
        conflicted_bytes = sum(int_value(row, "conflicted_bytes") for row in conflicted)
        singleton_bytes = sum(int_value(row, "singleton_bytes") for row in singletons)
        best_group = max(repeated, key=lambda row: int_value(row, "bytes"), default={})
        output.append(
            {
                "rank": 0,
                "target_kind": target_kind,
                "selector_type": selector_type,
                "selector_family": selector_family,
                "groups": len(members),
                "repeated_groups": len(repeated),
                "repeated_evidence_bytes": sum(int_value(row, "bytes") for row in repeated),
                "deterministic_repeated_groups": len(deterministic),
                "deterministic_repeated_evidence_bytes": deterministic_bytes,
                "conflicted_groups": len(conflicted),
                "conflicted_evidence_bytes": conflicted_bytes,
                "singleton_groups": len(singletons),
                "singleton_evidence_bytes": singleton_bytes,
                "best_group_key": best_group.get("selector_key", ""),
                "best_group_bytes": best_group.get("bytes", 0),
                "best_group_values": best_group.get("target_values", ""),
                "verdict": (
                    "fixture_transition_candidate"
                    if deterministic_bytes and deterministic_bytes >= conflicted_bytes
                    else "fixture_transition_conflicted"
                    if conflicted_bytes
                    else "fixture_transition_singleton_only"
                ),
            }
        )

    output.sort(
        key=lambda row: (
            str(row["target_kind"]) not in COARSE_TARGETS,
            -int_value(row, "deterministic_repeated_evidence_bytes"),
            int_value(row, "conflicted_evidence_bytes"),
            int_value(row, "singleton_evidence_bytes"),
            str(row["selector_type"]),
            str(row["selector_family"]),
        )
    )
    for index, row in enumerate(output, start=1):
        row["rank"] = index
    return output


def sum_family(family_rows: list[dict[str, object]], targets: set[str], field: str) -> int:
    return sum(int_value(row, field) for row in family_rows if str(row.get("target_kind", "")) in targets)


def best_family(family_rows: list[dict[str, object]], targets: set[str]) -> dict[str, object]:
    candidates = [row for row in family_rows if str(row.get("target_kind", "")) in targets]
    return max(
        candidates,
        key=lambda row: (
            int_value(row, "deterministic_repeated_evidence_bytes"),
            -int_value(row, "conflicted_evidence_bytes"),
            -int_value(row, "singleton_evidence_bytes"),
            str(row["selector_type"]) == "fixture_phase",
        ),
        default={},
    )


def low_conflict_family(family_rows: list[dict[str, object]], targets: set[str]) -> dict[str, object]:
    candidates = [
        row
        for row in family_rows
        if str(row.get("target_kind", "")) in targets
        and int_value(row, "deterministic_repeated_evidence_bytes") > 0
    ]
    return min(
        candidates,
        key=lambda row: (
            int_value(row, "conflicted_evidence_bytes"),
            -int_value(row, "deterministic_repeated_evidence_bytes"),
            int_value(row, "singleton_evidence_bytes"),
        ),
        default={},
    )


def build_summary(
    rows: list[dict[str, object]],
    group_rows: list[dict[str, object]],
    family_rows: list[dict[str, object]],
) -> dict[str, object]:
    repeated = [row for row in group_rows if int_value(row, "rows") > 1]
    deterministic = [row for row in repeated if int_value(row, "deterministic_bytes") > 0]
    conflicted = [row for row in repeated if int_value(row, "conflicted_bytes") > 0]
    singletons = [row for row in group_rows if int_value(row, "rows") == 1]
    best_transition = best_family(family_rows, COARSE_TARGETS)
    low_conflict_transition = low_conflict_family(family_rows, COARSE_TARGETS)
    best_payload = best_family(family_rows, PAYLOAD_TARGETS)
    return {
        "scope": "total",
        "target_rows": len(rows),
        "target_bytes": sum(int_value(row, "length") for row in rows),
        "target_kinds": len(target_values(rows[0])) if rows else 0,
        "selector_families": len(selector_values(rows[0])) if rows else 0,
        "selector_groups": len(group_rows),
        "repeated_selector_groups": len(repeated),
        "deterministic_repeated_groups": len(deterministic),
        "deterministic_repeated_evidence_bytes": sum(
            int_value(row, "deterministic_bytes") for row in deterministic
        ),
        "conflicted_groups": len(conflicted),
        "conflicted_evidence_bytes": sum(int_value(row, "conflicted_bytes") for row in conflicted),
        "singleton_groups": len(singletons),
        "singleton_evidence_bytes": sum(int_value(row, "singleton_bytes") for row in singletons),
        "transition_deterministic_evidence_bytes": sum_family(
            family_rows, COARSE_TARGETS, "deterministic_repeated_evidence_bytes"
        ),
        "transition_conflicted_evidence_bytes": sum_family(family_rows, COARSE_TARGETS, "conflicted_evidence_bytes"),
        "payload_deterministic_evidence_bytes": sum_family(
            family_rows, PAYLOAD_TARGETS, "deterministic_repeated_evidence_bytes"
        ),
        "payload_conflicted_evidence_bytes": sum_family(family_rows, PAYLOAD_TARGETS, "conflicted_evidence_bytes"),
        "best_transition_target_kind": best_transition.get("target_kind", ""),
        "best_transition_selector_family": best_transition.get("selector_family", ""),
        "best_transition_deterministic_bytes": best_transition.get("deterministic_repeated_evidence_bytes", 0),
        "best_transition_conflicted_bytes": best_transition.get("conflicted_evidence_bytes", 0),
        "best_transition_singleton_bytes": best_transition.get("singleton_evidence_bytes", 0),
        "low_conflict_transition_target_kind": low_conflict_transition.get("target_kind", ""),
        "low_conflict_transition_selector_family": low_conflict_transition.get("selector_family", ""),
        "low_conflict_transition_deterministic_bytes": low_conflict_transition.get(
            "deterministic_repeated_evidence_bytes", 0
        ),
        "low_conflict_transition_conflicted_bytes": low_conflict_transition.get("conflicted_evidence_bytes", 0),
        "low_conflict_transition_singleton_bytes": low_conflict_transition.get("singleton_evidence_bytes", 0),
        "best_payload_target_kind": best_payload.get("target_kind", ""),
        "best_payload_selector_family": best_payload.get("selector_family", ""),
        "best_payload_deterministic_bytes": best_payload.get("deterministic_repeated_evidence_bytes", 0),
        "best_payload_conflicted_bytes": best_payload.get("conflicted_evidence_bytes", 0),
        "best_payload_singleton_bytes": best_payload.get("singleton_evidence_bytes", 0),
        "promotion_ready_bytes": 0,
        "issue_rows": sum(1 for row in rows if row.get("issues")),
    }


def render_table(rows: list[dict[str, object]], fields: list[str], limit: int = 220) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, object],
    rows: list[dict[str, object]],
    group_rows: list[dict[str, object]],
    family_rows: list[dict[str, object]],
    title: str,
) -> str:
    data_json = json.dumps(
        {"summary": summary, "rows": rows, "groups": group_rows, "families": family_rows},
        indent=2,
        sort_keys=True,
    )
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body {{ margin: 2rem; background: #101214; color: #edf5f4; font: 14px/1.45 system-ui, sans-serif; }}
table {{ border-collapse: collapse; width: 100%; min-width: 1700px; }}
th, td {{ border: 1px solid #31424a; padding: .45rem .55rem; vertical-align: top; }}
th {{ color: #9dafb5; background: #172023; text-align: left; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: .75rem; margin: 1rem 0; }}
.box {{ border: 1px solid #31424a; background: #172023; padding: .75rem; }}
.num {{ font-size: 1.35rem; font-weight: 750; }}
.muted {{ color: #9dafb5; }}
.panel {{ overflow-x: auto; margin-top: 1rem; }}
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<div class="grid">
  <div class="box"><div class="num">{summary['target_bytes']}</div><div class="muted">target bytes</div></div>
  <div class="box"><div class="num">{summary['best_transition_selector_family']}</div><div class="muted">best transition selector</div></div>
  <div class="box"><div class="num">{summary['best_transition_deterministic_bytes']}</div><div class="muted">transition deterministic</div></div>
  <div class="box"><div class="num">{summary['best_transition_conflicted_bytes']}</div><div class="muted">transition conflicted</div></div>
  <div class="box"><div class="num">{summary['low_conflict_transition_selector_family']}</div><div class="muted">lowest conflict transition</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Rows</h2>{render_table(rows, ROW_FIELDNAMES)}</div>
<div class="panel"><h2>Families</h2>{render_table(family_rows, FAMILY_FIELDNAMES)}</div>
<div class="panel"><h2>Groups</h2>{render_table(group_rows, GROUP_FIELDNAMES)}</div>
<script type="application/json" id="gradient-macro-fixture-transition-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe abstract fixture/op transitions across gradient macros.")
    parser.add_argument("--input-rows", type=Path, default=DEFAULT_INPUT_ROWS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Gradient Macro Fixture Transition")
    args = parser.parse_args()

    rows = build_rows(read_csv(args.input_rows))
    group_rows = build_group_rows(rows)
    family_rows = build_family_rows(group_rows)
    summary = build_summary(rows, group_rows, family_rows)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "rows.csv", ROW_FIELDNAMES, rows)
    write_csv(args.output / "groups.csv", GROUP_FIELDNAMES, group_rows)
    write_csv(args.output / "families.csv", FAMILY_FIELDNAMES, family_rows)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, rows, group_rows, family_rows, args.title))

    print(f"Target bytes: {summary['target_bytes']}")
    print(f"Selector families: {summary['selector_families']}")
    print(
        f"Best fixture transition: {summary['best_transition_target_kind']} / "
        f"{summary['best_transition_selector_family']} "
        f"{summary['best_transition_deterministic_bytes']} deterministic, "
        f"{summary['best_transition_conflicted_bytes']} conflicted, "
        f"{summary['best_transition_singleton_bytes']} singleton"
    )
    print(
        f"Lowest conflict transition: {summary['low_conflict_transition_target_kind']} / "
        f"{summary['low_conflict_transition_selector_family']} "
        f"{summary['low_conflict_transition_deterministic_bytes']} deterministic, "
        f"{summary['low_conflict_transition_conflicted_bytes']} conflicted, "
        f"{summary['low_conflict_transition_singleton_bytes']} singleton"
    )
    print(
        f"Best payload transition: {summary['best_payload_target_kind']} / "
        f"{summary['best_payload_selector_family']} "
        f"{summary['best_payload_deterministic_bytes']} deterministic, "
        f"{summary['best_payload_conflicted_bytes']} conflicted, "
        f"{summary['best_payload_singleton_bytes']} singleton"
    )
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
