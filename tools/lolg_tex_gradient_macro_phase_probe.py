#!/usr/bin/env python3
"""Probe phase-bin selectors across all gradient macro-opcode rows."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_micro_mixed_value_payload_state_opcode_probe import int_value, ratio


DEFAULT_INPUT_ROWS = Path("output/tex_gradient_macro_opcode/rows.csv")
DEFAULT_OUTPUT = Path("output/tex_gradient_macro_phase")

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
    "coarse_deterministic_evidence_bytes",
    "coarse_conflicted_evidence_bytes",
    "payload_deterministic_evidence_bytes",
    "payload_conflicted_evidence_bytes",
    "best_coarse_target_kind",
    "best_coarse_selector_family",
    "best_coarse_deterministic_bytes",
    "best_coarse_conflicted_bytes",
    "best_coarse_singleton_bytes",
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
    "dominant_delta",
    "top_nibble",
    "gradient_class",
    "fixture_rule_key",
    "control_anchor_class_key",
    "start_anchor_class_key",
    "control_window_class_key",
    "phase_signature",
    "payload_signature",
    "band_shape_key",
    "step_shape_key",
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
SIZE_ONLY_SELECTORS = {"length_band8", "length_band16", "length_bucket_phase"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def band(value: int, step: int) -> str:
    base = (value // step) * step
    return f"{base}-{base + step - 1}"


def key_part(text: str, name: str) -> str:
    prefix = f"{name}="
    for part in text.split("|"):
        if part.startswith(prefix):
            return part[len(prefix) :]
    return "missing"


def row_phase_signature(row: dict[str, str]) -> str:
    return (
        f"span4={band(int_value(row, 'span_index'), 4)}|"
        f"op8={band(int_value(row, 'op_index'), 8)}|"
        f"start128={band(int_value(row, 'start'), 128)}|"
        f"len8={band(int_value(row, 'length'), 8)}"
    )


def build_rows(input_rows: list[dict[str, str]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for input_row in input_rows:
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
                "dominant_delta": input_row.get("dominant_delta", ""),
                "top_nibble": input_row.get("top_nibble", ""),
                "gradient_class": input_row.get("gradient_class", ""),
                "fixture_rule_key": input_row.get("fixture_rule_key", ""),
                "control_anchor_class_key": input_row.get("control_anchor_class_key", ""),
                "start_anchor_class_key": input_row.get("start_anchor_class_key", ""),
                "control_window_class_key": input_row.get("control_window_class_key", ""),
                "phase_signature": row_phase_signature(input_row),
                "payload_signature": input_row.get("payload_signature", ""),
                "band_shape_key": input_row.get("band_shape_key", ""),
                "step_shape_key": input_row.get("step_shape_key", ""),
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
    span = int_value(row, "span_index")
    op = int_value(row, "op_index")
    start = int_value(row, "start")
    end = int_value(row, "end")
    length = int_value(row, "length")
    control_mod = key_part(str(row["control_anchor_class_key"]), "mod64")
    start_mod = key_part(str(row["start_anchor_class_key"]), "start_mod64")
    fixture = str(row["fixture_rule_key"])
    length_bucket = str(row["length_bucket"])
    span4 = band(span, 4)
    span8 = band(span, 8)
    op4 = band(op, 4)
    op8 = band(op, 8)
    op16 = band(op, 16)
    start128 = band(start, 128)
    start256 = band(start, 256)
    length8 = band(length, 8)
    return {
        "span_index_band4": ("phase", f"span4={span4}"),
        "span_index_band8": ("phase", f"span8={span8}"),
        "op_index_band4": ("phase", f"op4={op4}"),
        "op_index_band8": ("phase", f"op8={op8}"),
        "op_index_band16": ("phase", f"op16={op16}"),
        "op_index_mod4": ("phase", f"op_mod4={op % 4}"),
        "span_index_mod4": ("phase", f"span_mod4={span % 4}"),
        "span_op_band": ("phase", f"span4={span4}|op8={op8}"),
        "op_start_band": ("phase", f"op8={op8}|start128={start128}"),
        "span_start_band": ("phase", f"span4={span4}|start128={start128}"),
        "start_offset_band128": ("phase", f"start128={start128}"),
        "start_offset_band256": ("phase", f"start256={start256}"),
        "end_offset_band256": ("phase", f"end256={band(end, 256)}"),
        "length_band8": ("phase", f"len8={length8}"),
        "length_band16": ("phase", f"len16={band(length, 16)}"),
        "length_bucket_phase": ("phase", f"len_bucket={length_bucket}"),
        "control_start_mod": ("source_phase", f"ctrl_mod64={control_mod}|start_mod64={start_mod}"),
        "control_op_phase": ("source_phase", f"ctrl_mod64={control_mod}|op8={op8}"),
        "start_op_phase": ("source_phase", f"start_mod64={start_mod}|op8={op8}"),
        "fixture_op_phase": ("macro_phase", f"{fixture}|op8={op8}"),
        "fixture_span_phase": ("macro_phase", f"{fixture}|span4={span4}"),
        "fixture_length_op_phase": ("macro_phase", f"{fixture}|len={length_bucket}|op8={op8}"),
        "fixture_control_op_phase": ("macro_phase", f"{fixture}|ctrl_mod64={control_mod}|op8={op8}"),
        "fixture_span_op_phase": ("macro_phase", f"{fixture}|span4={span4}|op8={op8}"),
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
                            "phase_deterministic_repeat"
                            if deterministic and repeated
                            else "phase_conflicted_repeat"
                            if repeated
                            else "phase_singleton"
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
                    "phase_selector_candidate"
                    if deterministic_bytes and deterministic_bytes >= conflicted_bytes
                    else "phase_selector_conflicted"
                    if conflicted_bytes
                    else "phase_selector_singleton_only"
                ),
            }
        )

    output.sort(
        key=lambda row: (
            str(row["target_kind"]) not in COARSE_TARGETS,
            -int_value(row, "deterministic_repeated_evidence_bytes"),
            int_value(row, "conflicted_evidence_bytes"),
            int_value(row, "singleton_evidence_bytes"),
            str(row["target_kind"]),
            str(row["selector_family"]),
        )
    )
    for index, row in enumerate(output, start=1):
        row["rank"] = index
    return output


def sum_family(family_rows: list[dict[str, object]], targets: set[str], field: str) -> int:
    return sum(int_value(row, field) for row in family_rows if str(row.get("target_kind", "")) in targets)


def best_family(
    family_rows: list[dict[str, object]],
    targets: set[str],
    excluded_selectors: set[str] | None = None,
) -> dict[str, object]:
    excluded = excluded_selectors or set()
    candidates = [
        row
        for row in family_rows
        if str(row.get("target_kind", "")) in targets and str(row.get("selector_family", "")) not in excluded
    ]
    return max(
        candidates,
        key=lambda row: (
            int_value(row, "deterministic_repeated_evidence_bytes"),
            -int_value(row, "conflicted_evidence_bytes"),
            -int_value(row, "singleton_evidence_bytes"),
            str(row["selector_type"]) == "macro_phase",
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
    best_coarse = best_family(family_rows, COARSE_TARGETS, SIZE_ONLY_SELECTORS)
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
        "coarse_deterministic_evidence_bytes": sum_family(
            family_rows, COARSE_TARGETS, "deterministic_repeated_evidence_bytes"
        ),
        "coarse_conflicted_evidence_bytes": sum_family(family_rows, COARSE_TARGETS, "conflicted_evidence_bytes"),
        "payload_deterministic_evidence_bytes": sum_family(
            family_rows, PAYLOAD_TARGETS, "deterministic_repeated_evidence_bytes"
        ),
        "payload_conflicted_evidence_bytes": sum_family(family_rows, PAYLOAD_TARGETS, "conflicted_evidence_bytes"),
        "best_coarse_target_kind": best_coarse.get("target_kind", ""),
        "best_coarse_selector_family": best_coarse.get("selector_family", ""),
        "best_coarse_deterministic_bytes": best_coarse.get("deterministic_repeated_evidence_bytes", 0),
        "best_coarse_conflicted_bytes": best_coarse.get("conflicted_evidence_bytes", 0),
        "best_coarse_singleton_bytes": best_coarse.get("singleton_evidence_bytes", 0),
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
  <div class="box"><div class="num">{summary['best_coarse_selector_family']}</div><div class="muted">best coarse selector</div></div>
  <div class="box"><div class="num">{summary['best_coarse_deterministic_bytes']}</div><div class="muted">coarse deterministic</div></div>
  <div class="box"><div class="num">{summary['best_coarse_conflicted_bytes']}</div><div class="muted">coarse conflicted</div></div>
  <div class="box"><div class="num">{summary['best_payload_deterministic_bytes']}</div><div class="muted">payload deterministic</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Rows</h2>{render_table(rows, ROW_FIELDNAMES)}</div>
<div class="panel"><h2>Families</h2>{render_table(family_rows, FAMILY_FIELDNAMES)}</div>
<div class="panel"><h2>Groups</h2>{render_table(group_rows, GROUP_FIELDNAMES)}</div>
<script type="application/json" id="gradient-macro-phase-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe phase-bin selectors across gradient macro-opcode rows.")
    parser.add_argument("--input-rows", type=Path, default=DEFAULT_INPUT_ROWS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Gradient Macro Phase")
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
        f"Best coarse phase: {summary['best_coarse_target_kind']} / "
        f"{summary['best_coarse_selector_family']} "
        f"{summary['best_coarse_deterministic_bytes']} deterministic, "
        f"{summary['best_coarse_conflicted_bytes']} conflicted"
    )
    print(
        f"Best payload phase: {summary['best_payload_target_kind']} / "
        f"{summary['best_payload_selector_family']} "
        f"{summary['best_payload_deterministic_bytes']} deterministic, "
        f"{summary['best_payload_conflicted_bytes']} conflicted"
    )
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
