#!/usr/bin/env python3
"""Probe payload reuse inside deterministic skip/op8 gradient macro clusters."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_micro_mixed_value_payload_state_opcode_probe import int_value, ratio


DEFAULT_INPUT_ROWS = Path("output/tex_gradient_macro_state_cluster/rows.csv")
DEFAULT_OUTPUT = Path("output/tex_gradient_macro_state_cluster_payload")

SUMMARY_FIELDNAMES = [
    "scope",
    "source_rows",
    "source_bytes",
    "cluster_groups",
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
    "exact_payload_deterministic_bytes",
    "exact_payload_conflicted_bytes",
    "shape_payload_deterministic_bytes",
    "shape_payload_conflicted_bytes",
    "coarse_deterministic_bytes",
    "coarse_conflicted_bytes",
    "best_payload_target_kind",
    "best_payload_selector_family",
    "best_payload_deterministic_bytes",
    "best_payload_conflicted_bytes",
    "best_payload_singleton_bytes",
    "low_conflict_payload_target_kind",
    "low_conflict_payload_selector_family",
    "low_conflict_payload_deterministic_bytes",
    "low_conflict_payload_conflicted_bytes",
    "low_conflict_payload_singleton_bytes",
    "best_coarse_target_kind",
    "best_coarse_selector_family",
    "best_coarse_deterministic_bytes",
    "best_coarse_conflicted_bytes",
    "best_coarse_singleton_bytes",
    "promotion_ready_bytes",
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
    "fixture_rule",
    "fixture_opcode_pair",
    "fixture_hi_pair",
    "fixture_opcode_delta",
    "fixture_skip_bucket",
    "control_anchor_mod64",
    "start_anchor_mod64",
    "payload_signature",
    "band_shape_key",
    "step_shape_key",
    "top_nibble",
    "gradient_class",
    "dominant_delta",
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

PAYLOAD_TARGETS = {"exact_payload", "band_shape", "step_shape"}
SHAPE_TARGETS = {"band_shape", "step_shape"}
COARSE_TARGETS = {"top_nibble", "gradient_class"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def cluster_key(row: dict[str, str]) -> str:
    return f"skip={row.get('fixture_skip_bucket', '')}|op8={row.get('op_phase8', '')}"


def frontier_band(frontier_id: str) -> str:
    value = int(frontier_id) if frontier_id else 0
    base = (value // 8) * 8
    return f"{base}-{base + 7}"


def deterministic_cluster_rows(input_rows: list[dict[str, str]]) -> list[dict[str, object]]:
    clusters: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in input_rows:
        clusters[cluster_key(row)].append(row)

    rows: list[dict[str, object]] = []
    for key, members in sorted(clusters.items()):
        values = {row.get("dominant_delta", "") for row in members}
        if len(members) <= 1 or len(values) != 1:
            continue
        for input_row in members:
            rows.append(
                {
                    "rank": len(rows) + 1,
                    "cluster_key": key,
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
                    "fixture_rule": input_row.get("fixture_rule", ""),
                    "fixture_opcode_pair": input_row.get("fixture_opcode_pair", ""),
                    "fixture_hi_pair": input_row.get("fixture_hi_pair", ""),
                    "fixture_opcode_delta": input_row.get("fixture_opcode_delta", ""),
                    "fixture_skip_bucket": input_row.get("fixture_skip_bucket", ""),
                    "control_anchor_mod64": input_row.get("control_anchor_mod64", ""),
                    "start_anchor_mod64": input_row.get("start_anchor_mod64", ""),
                    "payload_signature": input_row.get("payload_signature", ""),
                    "band_shape_key": input_row.get("band_shape_key", ""),
                    "step_shape_key": input_row.get("step_shape_key", ""),
                    "top_nibble": input_row.get("top_nibble", ""),
                    "gradient_class": input_row.get("gradient_class", ""),
                    "dominant_delta": input_row.get("dominant_delta", ""),
                    "issues": input_row.get("issues", ""),
                }
            )
    return rows


def target_values(row: dict[str, object]) -> dict[str, str]:
    return {
        "exact_payload": str(row["payload_signature"]),
        "band_shape": str(row["band_shape_key"]),
        "step_shape": str(row["step_shape_key"]),
        "top_nibble": str(row["top_nibble"]),
        "gradient_class": str(row["gradient_class"]),
    }


def selector_values(row: dict[str, object]) -> dict[str, tuple[str, str]]:
    cluster = str(row["cluster_key"])
    rule = str(row["fixture_rule"])
    pair = str(row["fixture_opcode_pair"])
    hi_pair = str(row["fixture_hi_pair"])
    delta = str(row["fixture_opcode_delta"])
    length8 = str(row["length_band8"])
    span4 = str(row["span_phase4"])
    pos = str(row["frontier_position"])
    prev_op = str(row["prev_op_gap"])
    next_op = str(row["next_op_gap"])
    control_mod = str(row["control_anchor_mod64"])
    start_mod = str(row["start_anchor_mod64"])
    frontier8 = frontier_band(str(row["frontier_id"]))
    return {
        "cluster": ("cluster", cluster),
        "cluster_rule": ("cluster_fixture", f"{cluster}|rule={rule}"),
        "cluster_pair": ("cluster_fixture", f"{cluster}|pair={pair}"),
        "cluster_hi": ("cluster_fixture", f"{cluster}|hi={hi_pair}|delta={delta}"),
        "cluster_length": ("cluster_shape", f"{cluster}|len8={length8}"),
        "cluster_rule_length": ("cluster_shape", f"{cluster}|rule={rule}|len8={length8}"),
        "cluster_span_length": ("cluster_shape", f"{cluster}|span4={span4}|len8={length8}"),
        "cluster_position": ("cluster_sequence", f"{cluster}|pos={pos}"),
        "cluster_next_op": ("cluster_sequence", f"{cluster}|next_op={next_op}"),
        "cluster_prev_next": ("cluster_sequence", f"{cluster}|prev_op={prev_op}|next_op={next_op}"),
        "cluster_frontier_band": ("cluster_sequence", f"{cluster}|frontier8={frontier8}"),
        "cluster_start_anchor": ("cluster_source", f"{cluster}|start_mod64={start_mod}"),
        "cluster_control_anchor": ("cluster_source", f"{cluster}|ctrl_mod64={control_mod}"),
        "cluster_length_start": ("cluster_source", f"{cluster}|len8={length8}|start_mod64={start_mod}"),
        "cluster_rule_length_start": (
            "cluster_source",
            f"{cluster}|rule={rule}|len8={length8}|start_mod64={start_mod}",
        ),
        "cluster_length_control": ("cluster_source", f"{cluster}|len8={length8}|ctrl_mod64={control_mod}"),
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
                            "cluster_payload_deterministic_repeat"
                            if deterministic and repeated
                            else "cluster_payload_conflicted_repeat"
                            if repeated
                            else "cluster_payload_singleton"
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
                    "cluster_payload_candidate"
                    if deterministic_bytes and deterministic_bytes >= conflicted_bytes
                    else "cluster_payload_conflicted"
                    if conflicted_bytes
                    else "cluster_payload_singleton_only"
                ),
            }
        )

    output.sort(
        key=lambda row: (
            str(row["target_kind"]) not in PAYLOAD_TARGETS,
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
    source_rows: list[dict[str, str]],
    rows: list[dict[str, object]],
    group_rows: list[dict[str, object]],
    family_rows: list[dict[str, object]],
) -> dict[str, object]:
    repeated = [row for row in group_rows if int_value(row, "rows") > 1]
    deterministic = [row for row in repeated if int_value(row, "deterministic_bytes") > 0]
    conflicted = [row for row in repeated if int_value(row, "conflicted_bytes") > 0]
    singletons = [row for row in group_rows if int_value(row, "rows") == 1]
    best_payload = best_family(family_rows, PAYLOAD_TARGETS)
    low_conflict_payload = low_conflict_family(family_rows, PAYLOAD_TARGETS)
    best_coarse = best_family(family_rows, COARSE_TARGETS)
    return {
        "scope": "total",
        "source_rows": len(source_rows),
        "source_bytes": sum(int_value(row, "length") for row in source_rows),
        "cluster_groups": len({str(row["cluster_key"]) for row in rows}),
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
        "exact_payload_deterministic_bytes": sum_family(
            family_rows, {"exact_payload"}, "deterministic_repeated_evidence_bytes"
        ),
        "exact_payload_conflicted_bytes": sum_family(family_rows, {"exact_payload"}, "conflicted_evidence_bytes"),
        "shape_payload_deterministic_bytes": sum_family(
            family_rows, SHAPE_TARGETS, "deterministic_repeated_evidence_bytes"
        ),
        "shape_payload_conflicted_bytes": sum_family(family_rows, SHAPE_TARGETS, "conflicted_evidence_bytes"),
        "coarse_deterministic_bytes": sum_family(
            family_rows, COARSE_TARGETS, "deterministic_repeated_evidence_bytes"
        ),
        "coarse_conflicted_bytes": sum_family(family_rows, COARSE_TARGETS, "conflicted_evidence_bytes"),
        "best_payload_target_kind": best_payload.get("target_kind", ""),
        "best_payload_selector_family": best_payload.get("selector_family", ""),
        "best_payload_deterministic_bytes": best_payload.get("deterministic_repeated_evidence_bytes", 0),
        "best_payload_conflicted_bytes": best_payload.get("conflicted_evidence_bytes", 0),
        "best_payload_singleton_bytes": best_payload.get("singleton_evidence_bytes", 0),
        "low_conflict_payload_target_kind": low_conflict_payload.get("target_kind", ""),
        "low_conflict_payload_selector_family": low_conflict_payload.get("selector_family", ""),
        "low_conflict_payload_deterministic_bytes": low_conflict_payload.get(
            "deterministic_repeated_evidence_bytes", 0
        ),
        "low_conflict_payload_conflicted_bytes": low_conflict_payload.get("conflicted_evidence_bytes", 0),
        "low_conflict_payload_singleton_bytes": low_conflict_payload.get("singleton_evidence_bytes", 0),
        "best_coarse_target_kind": best_coarse.get("target_kind", ""),
        "best_coarse_selector_family": best_coarse.get("selector_family", ""),
        "best_coarse_deterministic_bytes": best_coarse.get("deterministic_repeated_evidence_bytes", 0),
        "best_coarse_conflicted_bytes": best_coarse.get("conflicted_evidence_bytes", 0),
        "best_coarse_singleton_bytes": best_coarse.get("singleton_evidence_bytes", 0),
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
  <div class="box"><div class="num">{summary['best_payload_selector_family']}</div><div class="muted">best payload selector</div></div>
  <div class="box"><div class="num">{summary['best_payload_deterministic_bytes']}</div><div class="muted">payload deterministic</div></div>
  <div class="box"><div class="num">{summary['exact_payload_deterministic_bytes']}</div><div class="muted">exact payload deterministic</div></div>
  <div class="box"><div class="num">{summary['best_coarse_deterministic_bytes']}</div><div class="muted">coarse deterministic</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Rows</h2>{render_table(rows, ROW_FIELDNAMES)}</div>
<div class="panel"><h2>Families</h2>{render_table(family_rows, FAMILY_FIELDNAMES)}</div>
<div class="panel"><h2>Groups</h2>{render_table(group_rows, GROUP_FIELDNAMES)}</div>
<script type="application/json" id="gradient-macro-state-cluster-payload-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe payload reuse inside deterministic skip/op8 macro clusters.")
    parser.add_argument("--input-rows", type=Path, default=DEFAULT_INPUT_ROWS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Gradient Macro State Cluster Payload")
    args = parser.parse_args()

    source_rows = read_csv(args.input_rows)
    rows = deterministic_cluster_rows(source_rows)
    group_rows = build_group_rows(rows)
    family_rows = build_family_rows(group_rows)
    summary = build_summary(source_rows, rows, group_rows, family_rows)

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
        f"Best payload: {summary['best_payload_target_kind']} / "
        f"{summary['best_payload_selector_family']} "
        f"{summary['best_payload_deterministic_bytes']} deterministic, "
        f"{summary['best_payload_conflicted_bytes']} conflicted, "
        f"{summary['best_payload_singleton_bytes']} singleton"
    )
    print(
        f"Exact payload: {summary['exact_payload_deterministic_bytes']} deterministic, "
        f"{summary['exact_payload_conflicted_bytes']} conflicted"
    )
    print(
        f"Best coarse: {summary['best_coarse_target_kind']} / "
        f"{summary['best_coarse_selector_family']} "
        f"{summary['best_coarse_deterministic_bytes']} deterministic, "
        f"{summary['best_coarse_conflicted_bytes']} conflicted, "
        f"{summary['best_coarse_singleton_bytes']} singleton"
    )
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
