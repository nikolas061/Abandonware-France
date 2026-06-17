#!/usr/bin/env python3
"""Probe higher-order macro opcode selectors for gradient-like payloads."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gradient_payload_state_opcode_probe import parse_window_signature, ratio_bin
from lolg_tex_micro_mixed_value_payload_state_opcode_probe import (
    byte_at,
    fixture_key,
    int_value,
    load_sources,
    ratio,
    signed_bucket,
    signed_delta,
    source_class,
)


DEFAULT_INPUT_ROWS = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_probe/targets.csv")
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_OUTPUT = Path("output/tex_gradient_macro_opcode")

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "target_bytes",
    "selector_families",
    "target_kinds",
    "selector_groups",
    "repeated_selector_groups",
    "repeated_selector_evidence_bytes",
    "deterministic_repeated_groups",
    "deterministic_repeated_evidence_bytes",
    "conflicted_groups",
    "conflicted_evidence_bytes",
    "exact_payload_repeated_evidence_bytes",
    "band_shape_repeated_evidence_bytes",
    "step_shape_repeated_evidence_bytes",
    "gradient_class_repeated_evidence_bytes",
    "top_nibble_repeated_evidence_bytes",
    "best_target_kind",
    "best_selector_family",
    "best_repeated_deterministic_bytes",
    "best_conflicted_bytes",
    "best_repeated_groups",
    "best_selector_groups",
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
    "gradient_class",
    "top_nibble",
    "dominant_delta",
    "small_delta_bin",
    "zero_delta_bin",
    "length_bucket",
    "fixture_rule_key",
    "control_window_class_key",
    "control_anchor_class_key",
    "start_anchor_class_key",
    "prefix_class_key",
    "fragment_class_key",
    "payload_signature",
    "band_shape_key",
    "step_shape_key",
    "payload_head_hex",
    "payload_tail_hex",
    "issues",
]

GROUP_FIELDNAMES = [
    "rank",
    "target_kind",
    "selector_family",
    "selector_key",
    "rows",
    "bytes",
    "target_values",
    "dominant_value",
    "dominant_ratio",
    "payload_signatures",
    "deterministic_bytes",
    "conflicted_bytes",
    "sample_pcx",
    "sample_frontier_id",
    "verdict",
]

FAMILY_FIELDNAMES = [
    "rank",
    "target_kind",
    "selector_family",
    "groups",
    "repeated_groups",
    "repeated_evidence_bytes",
    "deterministic_groups",
    "deterministic_repeated_evidence_bytes",
    "conflicted_groups",
    "conflicted_evidence_bytes",
    "best_group_key",
    "best_group_bytes",
    "best_group_values",
    "verdict",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def sha_key(prefix: str, values: list[str]) -> str:
    joined = ".".join(values)
    digest = hashlib.sha1(joined.encode("ascii")).hexdigest()[:14]
    return f"{prefix}=len{len(values)}|sha1={digest}"


def length_bucket(length: int) -> str:
    if length < 32:
        return "lt32"
    if length < 64:
        return "32-63"
    if length < 96:
        return "64-95"
    if length < 128:
        return "96-127"
    return "ge128"


def band_token(value: int) -> str:
    high = value >> 4
    if high in {5, 6, 7, 10}:
        return f"{high:x}"
    return "x"


def payload_signature(data: bytes) -> str:
    return f"len={len(data)}|sha1={hashlib.sha1(data).hexdigest()[:16]}"


def payload_shapes(data: bytes) -> tuple[str, str]:
    bands = [band_token(value) for value in data]
    steps = [
        signed_bucket(signed_delta(data[index - 1], data[index]))
        for index in range(1, len(data))
    ]
    return sha_key("band", bands), sha_key("step", steps)


def class_window(data: bytes, center: int, radius: int) -> str:
    if center < 0:
        return "missing"
    values: list[str] = []
    for offset in range(center - radius, center + radius + 1):
        values.append(source_class(byte_at(data, offset)))
    return ".".join(values)


def byte_window_hex(data: bytes, center: int, radius: int) -> str:
    if center < 0:
        return "missing"
    start = max(0, center - radius)
    end = min(len(data), center + radius + 1)
    return data[start:end].hex() or "empty"


def compact_classes(data: bytes, limit: int = 10) -> str:
    if not data:
        return "empty"
    return ".".join(source_class(value) for value in data[:limit])


def window_class_key(signature: str) -> str:
    head, tail = parse_window_signature(signature)
    return f"head={compact_classes(head, 6)}|tail={compact_classes(tail, 6)}"


def fixture_rule_key(fixture: dict[str, str]) -> str:
    return (
        f"rule={fixture.get('rule_type', '')}|frontier={fixture.get('frontier_type', '')}|"
        f"op0={fixture.get('opcode0_hex', '')}|op1={fixture.get('opcode1_hex', '')}|"
        f"skip={fixture.get('best_raw_skip', '')}"
    )


def target_values(row: dict[str, object]) -> dict[str, str]:
    return {
        "exact_payload": str(row["payload_signature"]),
        "band_shape": str(row["band_shape_key"]),
        "step_shape": str(row["step_shape_key"]),
        "gradient_class": str(row["gradient_class"]),
        "top_nibble": str(row["top_nibble"]),
        "dominant_delta": str(row["dominant_delta"]),
    }


def selector_values(row: dict[str, object]) -> dict[str, str]:
    return {
        "fixture_rule": str(row["fixture_rule_key"]),
        "fixture_rule_length": f"{row['fixture_rule_key']}|len={row['length_bucket']}",
        "control_window_class": str(row["control_window_class_key"]),
        "control_anchor_class": str(row["control_anchor_class_key"]),
        "start_anchor_class": str(row["start_anchor_class_key"]),
        "prefix_class": str(row["prefix_class_key"]),
        "fragment_class": str(row["fragment_class_key"]),
        "fixture_control_macro": (
            f"{row['fixture_rule_key']}|cw={row['control_window_class_key']}|"
            f"cp={row['prefix_class_key']}"
        ),
        "anchor_macro": (
            f"ctrl={row['control_anchor_class_key']}|start={row['start_anchor_class_key']}|"
            f"len={row['length_bucket']}"
        ),
        "window_anchor_macro": (
            f"cw={row['control_window_class_key']}|ctrl={row['control_anchor_class_key']}|"
            f"len={row['length_bucket']}"
        ),
    }


def build_rows(
    input_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
) -> tuple[list[dict[str, object]], list[str]]:
    sources_by_fixture, fixture_issues = load_sources(fixture_rows)
    fixtures_by_key = {fixture_key(row): row for row in fixture_rows}
    rows: list[dict[str, object]] = []
    issues = list(fixture_issues)

    for input_row in input_rows:
        local_issues = [issue for issue in input_row.get("issues", "").split(";") if issue]
        key = fixture_key(input_row)
        sources = sources_by_fixture.get(key, {})
        fixture = fixtures_by_key.get(key, {})
        expected = sources.get("expected", b"")
        segment = sources.get("segment_gap", b"")
        control_prefix = sources.get("control_prefix", b"")
        fragment = sources.get("fragment", b"")
        start = int_value(input_row, "start")
        end = int_value(input_row, "end")
        payload = expected[start:end]
        if not payload:
            local_issues.append("missing_payload")
        if int_value(input_row, "length") != len(payload):
            local_issues.append(f"length_mismatch:{input_row.get('length')}:{len(payload)}")

        control_ref_offset = int_value(input_row, "control_ref_offset", -1)
        control_ref_mod64 = int_value(input_row, "control_ref_mod64", -1)
        start_mod64 = int_value(input_row, "start_mod64", -1)
        start_anchor = (
            control_ref_offset - control_ref_mod64 + start_mod64
            if control_ref_offset >= 0 and control_ref_mod64 >= 0 and start_mod64 >= 0
            else -1
        )
        band_shape, step_shape = payload_shapes(payload)
        length_key = length_bucket(len(payload))
        row = {
            "rank": len(rows) + 1,
            "archive": input_row.get("archive", ""),
            "pcx_name": input_row.get("pcx_name", ""),
            "frontier_id": input_row.get("frontier_id", ""),
            "span_index": input_row.get("span_index", ""),
            "op_index": input_row.get("op_index", ""),
            "length": len(payload),
            "start": input_row.get("start", ""),
            "end": input_row.get("end", ""),
            "gradient_class": input_row.get("gradient_class", ""),
            "top_nibble": input_row.get("top_nibble", ""),
            "dominant_delta": input_row.get("dominant_delta", ""),
            "small_delta_bin": ratio_bin(input_row.get("small_delta_ratio", "")),
            "zero_delta_bin": ratio_bin(input_row.get("zero_delta_ratio", "")),
            "length_bucket": length_key,
            "fixture_rule_key": fixture_rule_key(fixture),
            "control_window_class_key": window_class_key(input_row.get("control_window_signature", "")),
            "control_anchor_class_key": (
                f"mod64={input_row.get('control_ref_mod64', '')}|"
                f"cls={class_window(segment, control_ref_offset, 3)}|"
                f"hex={byte_window_hex(segment, control_ref_offset, 2)}"
            ),
            "start_anchor_class_key": (
                f"start_mod64={input_row.get('start_mod64', '')}|"
                f"cls={class_window(segment, start_anchor, 3)}|"
                f"hex={byte_window_hex(segment, start_anchor, 2)}"
            ),
            "prefix_class_key": compact_classes(control_prefix, 12),
            "fragment_class_key": compact_classes(fragment, 12),
            "payload_signature": payload_signature(payload),
            "band_shape_key": band_shape,
            "step_shape_key": step_shape,
            "payload_head_hex": payload[:18].hex(),
            "payload_tail_hex": payload[-18:].hex() if payload else "",
            "issues": ";".join(local_issues),
        }
        rows.append(row)

    return rows, issues


def build_group_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for target_kind in target_values(rows[0]).keys() if rows else []:
        for selector_family in selector_values(rows[0]).keys() if rows else []:
            grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
            for row in rows:
                grouped[selector_values(row)[selector_family]].append(row)
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
                        "selector_family": selector_family,
                        "selector_key": selector_key,
                        "rows": rows_count,
                        "bytes": bytes_count,
                        "target_values": "|".join(f"{value}:{count}" for value, count in values.most_common(8)),
                        "dominant_value": dominant_value,
                        "dominant_ratio": ratio(dominant_count, rows_count),
                        "payload_signatures": len({str(row["payload_signature"]) for row in members}),
                        "deterministic_bytes": bytes_count if deterministic and repeated else 0,
                        "conflicted_bytes": bytes_count if not deterministic and repeated else 0,
                        "sample_pcx": members[0].get("pcx_name", ""),
                        "sample_frontier_id": members[0].get("frontier_id", ""),
                        "verdict": (
                            "macro_deterministic_repeat"
                            if deterministic and repeated
                            else "macro_conflicted_repeat"
                            if repeated
                            else "macro_singleton"
                        ),
                    }
                )

    output.sort(
        key=lambda row: (
            str(row["target_kind"]),
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
    grouped: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for row in group_rows:
        grouped[(str(row["target_kind"]), str(row["selector_family"]))].append(row)

    output: list[dict[str, object]] = []
    for (target_kind, selector_family), members in grouped.items():
        repeated = [row for row in members if int_value(row, "rows") > 1]
        deterministic = [row for row in repeated if int_value(row, "deterministic_bytes") > 0]
        conflicted = [row for row in repeated if int_value(row, "conflicted_bytes") > 0]
        best_group = max(repeated, key=lambda row: int_value(row, "bytes"), default={})
        deterministic_bytes = sum(int_value(row, "deterministic_bytes") for row in deterministic)
        conflicted_bytes = sum(int_value(row, "conflicted_bytes") for row in conflicted)
        output.append(
            {
                "rank": 0,
                "target_kind": target_kind,
                "selector_family": selector_family,
                "groups": len(members),
                "repeated_groups": len(repeated),
                "repeated_evidence_bytes": sum(int_value(row, "bytes") for row in repeated),
                "deterministic_groups": len(deterministic),
                "deterministic_repeated_evidence_bytes": deterministic_bytes,
                "conflicted_groups": len(conflicted),
                "conflicted_evidence_bytes": conflicted_bytes,
                "best_group_key": best_group.get("selector_key", ""),
                "best_group_bytes": best_group.get("bytes", 0),
                "best_group_values": best_group.get("target_values", ""),
                "verdict": (
                    "macro_selector_candidate"
                    if deterministic_bytes and deterministic_bytes >= conflicted_bytes
                    else "macro_selector_conflicted"
                    if conflicted_bytes
                    else "macro_selector_singleton_only"
                ),
            }
        )

    output.sort(
        key=lambda row: (
            -int_value(row, "deterministic_repeated_evidence_bytes"),
            int_value(row, "conflicted_evidence_bytes"),
            str(row["target_kind"]),
            str(row["selector_family"]),
        )
    )
    for index, row in enumerate(output, start=1):
        row["rank"] = index
    return output


def evidence_bytes(family_rows: list[dict[str, object]], target_kind: str) -> int:
    return sum(
        int_value(row, "deterministic_repeated_evidence_bytes")
        for row in family_rows
        if row.get("target_kind") == target_kind
    )


def build_summary(
    rows: list[dict[str, object]],
    group_rows: list[dict[str, object]],
    family_rows: list[dict[str, object]],
    issues: list[str],
) -> dict[str, object]:
    repeated_groups = [row for row in group_rows if int_value(row, "rows") > 1]
    deterministic_groups = [row for row in repeated_groups if int_value(row, "deterministic_bytes") > 0]
    conflicted_groups = [row for row in repeated_groups if int_value(row, "conflicted_bytes") > 0]
    best = max(
        family_rows,
        key=lambda row: (
            int_value(row, "deterministic_repeated_evidence_bytes"),
            -int_value(row, "conflicted_evidence_bytes"),
        ),
        default={},
    )
    return {
        "scope": "total",
        "target_rows": len(rows),
        "target_bytes": sum(int_value(row, "length") for row in rows),
        "selector_families": len(selector_values(rows[0])) if rows else 0,
        "target_kinds": len(target_values(rows[0])) if rows else 0,
        "selector_groups": len(group_rows),
        "repeated_selector_groups": len(repeated_groups),
        "repeated_selector_evidence_bytes": sum(int_value(row, "bytes") for row in repeated_groups),
        "deterministic_repeated_groups": len(deterministic_groups),
        "deterministic_repeated_evidence_bytes": sum(
            int_value(row, "deterministic_bytes") for row in deterministic_groups
        ),
        "conflicted_groups": len(conflicted_groups),
        "conflicted_evidence_bytes": sum(int_value(row, "conflicted_bytes") for row in conflicted_groups),
        "exact_payload_repeated_evidence_bytes": evidence_bytes(family_rows, "exact_payload"),
        "band_shape_repeated_evidence_bytes": evidence_bytes(family_rows, "band_shape"),
        "step_shape_repeated_evidence_bytes": evidence_bytes(family_rows, "step_shape"),
        "gradient_class_repeated_evidence_bytes": evidence_bytes(family_rows, "gradient_class"),
        "top_nibble_repeated_evidence_bytes": evidence_bytes(family_rows, "top_nibble"),
        "best_target_kind": best.get("target_kind", ""),
        "best_selector_family": best.get("selector_family", ""),
        "best_repeated_deterministic_bytes": best.get("deterministic_repeated_evidence_bytes", 0),
        "best_conflicted_bytes": best.get("conflicted_evidence_bytes", 0),
        "best_repeated_groups": best.get("repeated_groups", 0),
        "best_selector_groups": best.get("groups", 0),
        "promotion_ready_bytes": 0,
        "issue_rows": len(issues) + sum(1 for row in rows if row.get("issues")),
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
body {{ margin: 2rem; background: #111416; color: #edf5f4; font: 14px/1.45 system-ui, sans-serif; }}
table {{ border-collapse: collapse; width: 100%; min-width: 1500px; }}
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
  <div class="box"><div class="num">{summary['selector_groups']}</div><div class="muted">selector groups</div></div>
  <div class="box"><div class="num">{summary['deterministic_repeated_evidence_bytes']}</div><div class="muted">deterministic repeated evidence</div></div>
  <div class="box"><div class="num">{summary['conflicted_evidence_bytes']}</div><div class="muted">conflicted evidence</div></div>
  <div class="box"><div class="num">{summary['best_target_kind']}</div><div class="muted">best target kind</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Rows</h2>{render_table(rows, ROW_FIELDNAMES)}</div>
<div class="panel"><h2>Families</h2>{render_table(family_rows, FAMILY_FIELDNAMES)}</div>
<div class="panel"><h2>Groups</h2>{render_table(group_rows, GROUP_FIELDNAMES)}</div>
<script type="application/json" id="gradient-macro-opcode-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe higher-order macro opcode selectors for gradient payloads.")
    parser.add_argument("--input-rows", type=Path, default=DEFAULT_INPUT_ROWS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Gradient Macro Opcode")
    args = parser.parse_args()

    rows, issues = build_rows(read_csv(args.input_rows), read_csv(args.fixtures))
    group_rows = build_group_rows(rows)
    family_rows = build_family_rows(group_rows)
    summary = build_summary(rows, group_rows, family_rows, issues)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "rows.csv", ROW_FIELDNAMES, rows)
    write_csv(args.output / "groups.csv", GROUP_FIELDNAMES, group_rows)
    write_csv(args.output / "families.csv", FAMILY_FIELDNAMES, family_rows)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, rows, group_rows, family_rows, args.title))

    print(f"Target bytes: {summary['target_bytes']}")
    print(f"Selector groups: {summary['selector_groups']}")
    print(f"Deterministic repeated evidence bytes: {summary['deterministic_repeated_evidence_bytes']}")
    print(f"Conflicted evidence bytes: {summary['conflicted_evidence_bytes']}")
    print(
        f"Best macro selector: {summary['best_target_kind']} / {summary['best_selector_family']} "
        f"{summary['best_repeated_deterministic_bytes']} deterministic, "
        f"{summary['best_conflicted_bytes']} conflicted"
    )
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
