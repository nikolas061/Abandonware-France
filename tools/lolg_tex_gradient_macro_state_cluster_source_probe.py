#!/usr/bin/env python3
"""Probe source-window reuse inside deterministic skip/op8 gradient macro clusters."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_micro_mixed_value_payload_state_opcode_probe import int_value, ratio


DEFAULT_INPUT_ROWS = Path("output/tex_gradient_macro_state_cluster_payload/rows.csv")
DEFAULT_STATE_ROWS = Path("output/tex_gradient_payload_state_opcode/rows.csv")
DEFAULT_OUTPUT = Path("output/tex_gradient_macro_state_cluster_source")

SUMMARY_FIELDNAMES = [
    "scope",
    "source_rows",
    "target_rows",
    "target_bytes",
    "cluster_groups",
    "selector_families",
    "selector_groups",
    "repeated_selector_groups",
    "deterministic_repeated_groups",
    "deterministic_repeated_evidence_bytes",
    "conflicted_groups",
    "conflicted_evidence_bytes",
    "singleton_groups",
    "singleton_evidence_bytes",
    "control_raw_exact_bytes",
    "start_raw_exact_bytes",
    "control_high_exact_bytes",
    "start_high_exact_bytes",
    "linear_exact_bytes",
    "control_slot_bytes",
    "start_slot_bytes",
    "control_prefix_bytes",
    "fragment_bytes",
    "best_source_target_kind",
    "best_source_selector_family",
    "best_source_deterministic_bytes",
    "best_source_conflicted_bytes",
    "best_source_singleton_bytes",
    "best_high_target_kind",
    "best_high_selector_family",
    "best_high_deterministic_bytes",
    "best_high_conflicted_bytes",
    "best_high_singleton_bytes",
    "promotion_ready_bytes",
    "missing_state_rows",
    "issue_rows",
]

ROW_FIELDNAMES = [
    "rank",
    "cluster_key",
    "archive",
    "pcx_name",
    "frontier_id",
    "span_index",
    "op_index",
    "length",
    "start",
    "length_band8",
    "op_phase8",
    "frontier_position",
    "fixture_rule",
    "fixture_opcode_pair",
    "fixture_hi_pair",
    "fixture_skip_bucket",
    "control_anchor_mod64",
    "start_anchor_mod64",
    "control_ref_offset",
    "control_prefix_bytes",
    "fragment_bytes",
    "control_slot_bytes",
    "start_slot_bytes",
    "control_raw_exact_bytes",
    "start_raw_exact_bytes",
    "control_high_exact_bytes",
    "start_high_exact_bytes",
    "linear_exact_bytes",
    "control_raw_bucket",
    "start_raw_bucket",
    "control_high_bucket",
    "start_high_bucket",
    "linear_exact_bucket",
    "source_profile",
    "payload_signature",
    "band_shape_key",
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

HIGH_TARGETS = {"control_high_bucket", "start_high_bucket"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def state_key(row: dict[str, str]) -> tuple[str, str, str, str, str, str, str]:
    return (
        row.get("archive", ""),
        row.get("pcx_name", ""),
        row.get("frontier_id", ""),
        row.get("span_index", ""),
        row.get("op_index", ""),
        row.get("start", ""),
        row.get("length", ""),
    )


def exact_bucket(value: int) -> str:
    if value == 0:
        return "0"
    if value <= 2:
        return "1-2"
    if value <= 8:
        return "3-8"
    return "9+"


def build_rows(input_rows: list[dict[str, str]], state_rows: list[dict[str, str]]) -> tuple[list[dict[str, object]], int]:
    state_by_key = {state_key(row): row for row in state_rows}
    rows: list[dict[str, object]] = []
    missing = 0
    for input_row in input_rows:
        state_row = state_by_key.get(state_key(input_row))
        if not state_row:
            missing += 1
            continue
        control_raw = int_value(state_row, "control_raw_exact_bytes")
        start_raw = int_value(state_row, "start_raw_exact_bytes")
        control_high = int_value(state_row, "control_high_exact_bytes")
        start_high = int_value(state_row, "start_high_exact_bytes")
        linear = int_value(state_row, "linear_exact_bytes")
        source_profile = (
            f"ctrl_raw={exact_bucket(control_raw)}|start_raw={exact_bucket(start_raw)}|"
            f"ctrl_high={exact_bucket(control_high)}|start_high={exact_bucket(start_high)}|"
            f"linear={exact_bucket(linear)}"
        )
        rows.append(
            {
                "rank": len(rows) + 1,
                "cluster_key": input_row.get("cluster_key", ""),
                "archive": input_row.get("archive", ""),
                "pcx_name": input_row.get("pcx_name", ""),
                "frontier_id": input_row.get("frontier_id", ""),
                "span_index": input_row.get("span_index", ""),
                "op_index": input_row.get("op_index", ""),
                "length": input_row.get("length", ""),
                "start": input_row.get("start", ""),
                "length_band8": input_row.get("length_band8", ""),
                "op_phase8": input_row.get("op_phase8", ""),
                "frontier_position": input_row.get("frontier_position", ""),
                "fixture_rule": input_row.get("fixture_rule", ""),
                "fixture_opcode_pair": input_row.get("fixture_opcode_pair", ""),
                "fixture_hi_pair": input_row.get("fixture_hi_pair", ""),
                "fixture_skip_bucket": input_row.get("fixture_skip_bucket", ""),
                "control_anchor_mod64": input_row.get("control_anchor_mod64", ""),
                "start_anchor_mod64": input_row.get("start_anchor_mod64", ""),
                "control_ref_offset": state_row.get("control_ref_offset", ""),
                "control_prefix_bytes": state_row.get("control_prefix_bytes", ""),
                "fragment_bytes": state_row.get("fragment_bytes", ""),
                "control_slot_bytes": state_row.get("control_slot_bytes", ""),
                "start_slot_bytes": state_row.get("start_slot_bytes", ""),
                "control_raw_exact_bytes": control_raw,
                "start_raw_exact_bytes": start_raw,
                "control_high_exact_bytes": control_high,
                "start_high_exact_bytes": start_high,
                "linear_exact_bytes": linear,
                "control_raw_bucket": exact_bucket(control_raw),
                "start_raw_bucket": exact_bucket(start_raw),
                "control_high_bucket": exact_bucket(control_high),
                "start_high_bucket": exact_bucket(start_high),
                "linear_exact_bucket": exact_bucket(linear),
                "source_profile": source_profile,
                "payload_signature": input_row.get("payload_signature", ""),
                "band_shape_key": input_row.get("band_shape_key", ""),
                "top_nibble": input_row.get("top_nibble", ""),
                "gradient_class": input_row.get("gradient_class", ""),
                "issues": input_row.get("issues", ""),
            }
        )
    return rows, missing


def target_values(row: dict[str, object]) -> dict[str, str]:
    return {
        "control_raw_bucket": str(row["control_raw_bucket"]),
        "start_raw_bucket": str(row["start_raw_bucket"]),
        "control_high_bucket": str(row["control_high_bucket"]),
        "start_high_bucket": str(row["start_high_bucket"]),
        "linear_exact_bucket": str(row["linear_exact_bucket"]),
        "source_profile": str(row["source_profile"]),
    }


def selector_values(row: dict[str, object]) -> dict[str, tuple[str, str]]:
    cluster = str(row["cluster_key"])
    rule = str(row["fixture_rule"])
    hi = str(row["fixture_hi_pair"])
    pair = str(row["fixture_opcode_pair"])
    length8 = str(row["length_band8"])
    pos = str(row["frontier_position"])
    control_mod = str(row["control_anchor_mod64"])
    start_mod = str(row["start_anchor_mod64"])
    return {
        "cluster": ("cluster", cluster),
        "cluster_rule": ("cluster_fixture", f"{cluster}|rule={rule}"),
        "cluster_hi": ("cluster_fixture", f"{cluster}|hi={hi}"),
        "cluster_pair": ("cluster_fixture", f"{cluster}|pair={pair}"),
        "cluster_length": ("cluster_shape", f"{cluster}|len8={length8}"),
        "cluster_rule_length": ("cluster_shape", f"{cluster}|rule={rule}|len8={length8}"),
        "cluster_position": ("cluster_sequence", f"{cluster}|pos={pos}"),
        "cluster_control": ("cluster_source", f"{cluster}|ctrl_mod64={control_mod}"),
        "cluster_start": ("cluster_source", f"{cluster}|start_mod64={start_mod}"),
        "cluster_length_start": ("cluster_source", f"{cluster}|len8={length8}|start_mod64={start_mod}"),
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
                            "cluster_source_deterministic_repeat"
                            if deterministic and repeated
                            else "cluster_source_conflicted_repeat"
                            if repeated
                            else "cluster_source_singleton"
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
                    "cluster_source_candidate"
                    if deterministic_bytes and deterministic_bytes >= conflicted_bytes
                    else "cluster_source_conflicted"
                    if conflicted_bytes
                    else "cluster_source_singleton_only"
                ),
            }
        )

    output.sort(
        key=lambda row: (
            str(row["target_kind"]) not in HIGH_TARGETS,
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


def best_family(family_rows: list[dict[str, object]], targets: set[str] | None = None) -> dict[str, object]:
    candidates = [
        row
        for row in family_rows
        if targets is None or str(row.get("target_kind", "")) in targets
    ]
    return max(
        candidates,
        key=lambda row: (
            int_value(row, "deterministic_repeated_evidence_bytes"),
            -int_value(row, "conflicted_evidence_bytes"),
            -int_value(row, "singleton_evidence_bytes"),
        ),
        default={},
    )


def build_summary(
    source_rows: list[dict[str, str]],
    rows: list[dict[str, object]],
    missing: int,
    group_rows: list[dict[str, object]],
    family_rows: list[dict[str, object]],
) -> dict[str, object]:
    repeated = [row for row in group_rows if int_value(row, "rows") > 1]
    deterministic = [row for row in repeated if int_value(row, "deterministic_bytes") > 0]
    conflicted = [row for row in repeated if int_value(row, "conflicted_bytes") > 0]
    singletons = [row for row in group_rows if int_value(row, "rows") == 1]
    best_source = best_family(family_rows)
    best_high = best_family(family_rows, HIGH_TARGETS)
    return {
        "scope": "total",
        "source_rows": len(source_rows),
        "target_rows": len(rows),
        "target_bytes": sum(int_value(row, "length") for row in rows),
        "cluster_groups": len({str(row["cluster_key"]) for row in rows}),
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
        "control_raw_exact_bytes": sum(int_value(row, "control_raw_exact_bytes") for row in rows),
        "start_raw_exact_bytes": sum(int_value(row, "start_raw_exact_bytes") for row in rows),
        "control_high_exact_bytes": sum(int_value(row, "control_high_exact_bytes") for row in rows),
        "start_high_exact_bytes": sum(int_value(row, "start_high_exact_bytes") for row in rows),
        "linear_exact_bytes": sum(int_value(row, "linear_exact_bytes") for row in rows),
        "control_slot_bytes": sum(int_value(row, "control_slot_bytes") for row in rows),
        "start_slot_bytes": sum(int_value(row, "start_slot_bytes") for row in rows),
        "control_prefix_bytes": sum(int_value(row, "control_prefix_bytes") for row in rows),
        "fragment_bytes": sum(int_value(row, "fragment_bytes") for row in rows),
        "best_source_target_kind": best_source.get("target_kind", ""),
        "best_source_selector_family": best_source.get("selector_family", ""),
        "best_source_deterministic_bytes": best_source.get("deterministic_repeated_evidence_bytes", 0),
        "best_source_conflicted_bytes": best_source.get("conflicted_evidence_bytes", 0),
        "best_source_singleton_bytes": best_source.get("singleton_evidence_bytes", 0),
        "best_high_target_kind": best_high.get("target_kind", ""),
        "best_high_selector_family": best_high.get("selector_family", ""),
        "best_high_deterministic_bytes": best_high.get("deterministic_repeated_evidence_bytes", 0),
        "best_high_conflicted_bytes": best_high.get("conflicted_evidence_bytes", 0),
        "best_high_singleton_bytes": best_high.get("singleton_evidence_bytes", 0),
        "promotion_ready_bytes": 0,
        "missing_state_rows": missing,
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
  <div class="box"><div class="num">{summary['control_raw_exact_bytes']}</div><div class="muted">control raw exact</div></div>
  <div class="box"><div class="num">{summary['start_raw_exact_bytes']}</div><div class="muted">start raw exact</div></div>
  <div class="box"><div class="num">{summary['control_high_exact_bytes']}</div><div class="muted">control high exact</div></div>
  <div class="box"><div class="num">{summary['linear_exact_bytes']}</div><div class="muted">linear exact</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Rows</h2>{render_table(rows, ROW_FIELDNAMES)}</div>
<div class="panel"><h2>Families</h2>{render_table(family_rows, FAMILY_FIELDNAMES)}</div>
<div class="panel"><h2>Groups</h2>{render_table(group_rows, GROUP_FIELDNAMES)}</div>
<script type="application/json" id="gradient-macro-state-cluster-source-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe source-window reuse inside skip/op8 macro clusters.")
    parser.add_argument("--input-rows", type=Path, default=DEFAULT_INPUT_ROWS)
    parser.add_argument("--state-rows", type=Path, default=DEFAULT_STATE_ROWS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Gradient Macro State Cluster Source")
    args = parser.parse_args()

    source_rows = read_csv(args.input_rows)
    rows, missing = build_rows(source_rows, read_csv(args.state_rows))
    group_rows = build_group_rows(rows)
    family_rows = build_family_rows(group_rows)
    summary = build_summary(source_rows, rows, missing, group_rows, family_rows)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "rows.csv", ROW_FIELDNAMES, rows)
    write_csv(args.output / "groups.csv", GROUP_FIELDNAMES, group_rows)
    write_csv(args.output / "families.csv", FAMILY_FIELDNAMES, family_rows)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, rows, group_rows, family_rows, args.title))

    print(f"Target bytes: {summary['target_bytes']}")
    print(f"Cluster groups: {summary['cluster_groups']}")
    print(
        f"Raw exact: control {summary['control_raw_exact_bytes']}, "
        f"start {summary['start_raw_exact_bytes']}"
    )
    print(
        f"High exact: control {summary['control_high_exact_bytes']}, "
        f"start {summary['start_high_exact_bytes']}"
    )
    print(f"Linear exact bytes: {summary['linear_exact_bytes']}")
    print(
        f"Best source bucket: {summary['best_source_target_kind']} / "
        f"{summary['best_source_selector_family']} "
        f"{summary['best_source_deterministic_bytes']} deterministic, "
        f"{summary['best_source_conflicted_bytes']} conflicted"
    )
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
