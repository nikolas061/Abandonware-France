#!/usr/bin/env python3
"""Split conflicted gradient macro-opcode dominant-delta selector groups."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path


DEFAULT_INPUT_ROWS = Path("output/tex_gradient_macro_opcode/rows.csv")
DEFAULT_OUTPUT = Path("output/tex_gradient_macro_conflict_split")

SUMMARY_FIELDNAMES = [
    "scope",
    "source_rows",
    "source_bytes",
    "conflict_groups",
    "conflict_rows",
    "conflict_bytes",
    "split_families",
    "split_groups",
    "repeated_split_groups",
    "deterministic_repeated_groups",
    "deterministic_repeated_bytes",
    "conflicted_groups",
    "conflicted_bytes",
    "singleton_groups",
    "singleton_bytes",
    "best_split_family",
    "best_split_deterministic_bytes",
    "best_split_conflicted_bytes",
    "best_split_singleton_bytes",
    "best_split_conflict_reduction_bytes",
    "best_remaining_conflict_key",
    "low_conflict_split_family",
    "low_conflict_deterministic_bytes",
    "low_conflict_conflicted_bytes",
    "low_conflict_singleton_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

ROW_FIELDNAMES = [
    "rank",
    "conflict_group_key",
    "archive",
    "pcx_name",
    "frontier_id",
    "span_index",
    "op_index",
    "length",
    "length_bucket",
    "start",
    "end",
    "gradient_class",
    "top_nibble",
    "dominant_delta",
    "fixture_rule_key",
    "control_window_class_key",
    "control_anchor_class_key",
    "start_anchor_class_key",
    "prefix_class_key",
    "fragment_class_key",
    "payload_signature",
    "issues",
]

SPLIT_FIELDNAMES = [
    "rank",
    "conflict_group_key",
    "selector_family",
    "selector_key",
    "rows",
    "bytes",
    "dominant_delta_values",
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
    "selector_family",
    "conflict_groups",
    "split_groups",
    "repeated_groups",
    "deterministic_repeated_groups",
    "deterministic_repeated_bytes",
    "conflicted_groups",
    "conflicted_bytes",
    "singleton_groups",
    "singleton_bytes",
    "covered_bytes",
    "conflict_reduction_bytes",
    "best_remaining_conflict_key",
    "best_remaining_conflict_bytes",
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


def int_value(row: dict[str, object], field: str) -> int:
    raw = row.get(field, "")
    try:
        return int(raw) if raw != "" else 0
    except (TypeError, ValueError):
        return 0


def ratio(part: int, whole: int) -> str:
    return f"{part / whole:.6f}" if whole else "0"


def conflict_group_key(row: dict[str, str]) -> str:
    return f"{row.get('fixture_rule_key', '')}|len={row.get('length_bucket', '')}"


def key_part(text: str, name: str) -> str:
    prefix = f"{name}="
    for part in text.split("|"):
        if part.startswith(prefix):
            return part[len(prefix) :]
    return "missing"


def split_selector_values(row: dict[str, object]) -> dict[str, str]:
    control_anchor = str(row["control_anchor_class_key"])
    start_anchor = str(row["start_anchor_class_key"])
    control_window = str(row["control_window_class_key"])
    prefix = str(row["prefix_class_key"])
    fragment = str(row["fragment_class_key"])
    length = str(row["length"])
    control_mod = key_part(control_anchor, "mod64")
    start_mod = key_part(start_anchor, "start_mod64")
    return {
        "control_anchor_class": control_anchor,
        "control_window_class": control_window,
        "start_anchor_class": start_anchor,
        "anchor_pair": f"ctrl={control_anchor}|start={start_anchor}",
        "window_control_pair": f"cw={control_window}|ctrl={control_anchor}",
        "window_start_pair": f"cw={control_window}|start={start_anchor}",
        "control_start_mod": f"ctrl_mod64={control_mod}|start_mod64={start_mod}",
        "prefix_fragment": f"prefix={prefix}|fragment={fragment}",
        "operation_position": (
            f"frontier={row['frontier_id']}|span={row['span_index']}|op={row['op_index']}"
        ),
        "exact_length": f"length={length}",
        "length_control_anchor": f"length={length}|ctrl={control_anchor}",
        "length_window_control": f"length={length}|cw={control_window}|ctrl={control_anchor}",
    }


def conflict_members(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[conflict_group_key(row)].append(row)

    selected: list[dict[str, object]] = []
    rank = 1
    for group_key, members in grouped.items():
        values = {row.get("dominant_delta", "") for row in members}
        if len(members) <= 1 or len(values) <= 1:
            continue
        for member in members:
            selected.append(
                {
                    "rank": rank,
                    "conflict_group_key": group_key,
                    **{field: member.get(field, "") for field in ROW_FIELDNAMES if field not in {"rank", "conflict_group_key"}},
                }
            )
            rank += 1
    return selected


def build_split_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    by_conflict: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        by_conflict[str(row["conflict_group_key"])].append(row)

    output: list[dict[str, object]] = []
    families = split_selector_values(rows[0]).keys() if rows else []
    for group_key, members in by_conflict.items():
        for selector_family in families:
            grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
            for row in members:
                grouped[split_selector_values(row)[selector_family]].append(row)
            for selector_key, split_members in grouped.items():
                values = Counter(str(row["dominant_delta"]) for row in split_members)
                dominant_value, dominant_count = values.most_common(1)[0]
                rows_count = len(split_members)
                bytes_count = sum(int_value(row, "length") for row in split_members)
                deterministic = len(values) == 1
                repeated = rows_count > 1
                output.append(
                    {
                        "rank": 0,
                        "conflict_group_key": group_key,
                        "selector_family": selector_family,
                        "selector_key": selector_key,
                        "rows": rows_count,
                        "bytes": bytes_count,
                        "dominant_delta_values": "|".join(
                            f"{value}:{count}" for value, count in values.most_common()
                        ),
                        "dominant_value": dominant_value,
                        "dominant_ratio": ratio(dominant_count, rows_count),
                        "deterministic_bytes": bytes_count if deterministic and repeated else 0,
                        "conflicted_bytes": bytes_count if not deterministic and repeated else 0,
                        "singleton_bytes": bytes_count if rows_count == 1 else 0,
                        "sample_pcx": split_members[0].get("pcx_name", ""),
                        "sample_frontier_id": split_members[0].get("frontier_id", ""),
                        "verdict": (
                            "split_deterministic_repeat"
                            if deterministic and repeated
                            else "split_conflicted_repeat"
                            if repeated
                            else "split_singleton"
                        ),
                    }
                )

    output.sort(
        key=lambda row: (
            str(row["selector_family"]),
            str(row["conflict_group_key"]),
            -int_value(row, "rows"),
            -int_value(row, "bytes"),
            str(row["selector_key"]),
        )
    )
    for index, row in enumerate(output, start=1):
        row["rank"] = index
    return output


def build_family_rows(split_rows: list[dict[str, object]], conflict_bytes: int) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in split_rows:
        grouped[str(row["selector_family"])].append(row)

    output: list[dict[str, object]] = []
    for selector_family, members in grouped.items():
        repeated = [row for row in members if int_value(row, "rows") > 1]
        deterministic = [row for row in repeated if int_value(row, "deterministic_bytes") > 0]
        conflicted = [row for row in repeated if int_value(row, "conflicted_bytes") > 0]
        singleton = [row for row in members if int_value(row, "rows") == 1]
        conflicted_bytes = sum(int_value(row, "conflicted_bytes") for row in conflicted)
        deterministic_bytes = sum(int_value(row, "deterministic_bytes") for row in deterministic)
        singleton_bytes = sum(int_value(row, "singleton_bytes") for row in singleton)
        best_remaining = max(conflicted, key=lambda row: int_value(row, "conflicted_bytes"), default={})
        output.append(
            {
                "rank": 0,
                "selector_family": selector_family,
                "conflict_groups": len({str(row["conflict_group_key"]) for row in members}),
                "split_groups": len(members),
                "repeated_groups": len(repeated),
                "deterministic_repeated_groups": len(deterministic),
                "deterministic_repeated_bytes": deterministic_bytes,
                "conflicted_groups": len(conflicted),
                "conflicted_bytes": conflicted_bytes,
                "singleton_groups": len(singleton),
                "singleton_bytes": singleton_bytes,
                "covered_bytes": sum(int_value(row, "bytes") for row in members),
                "conflict_reduction_bytes": conflict_bytes - conflicted_bytes,
                "best_remaining_conflict_key": best_remaining.get("selector_key", ""),
                "best_remaining_conflict_bytes": best_remaining.get("conflicted_bytes", 0),
                "verdict": (
                    "split_low_conflict_singletons"
                    if conflicted_bytes == 0 and singleton_bytes
                    else "split_candidate_partial"
                    if deterministic_bytes > conflicted_bytes
                    else "split_still_conflicted"
                    if conflicted_bytes
                    else "split_singleton_only"
                ),
            }
        )

    output.sort(
        key=lambda row: (
            -int_value(row, "deterministic_repeated_bytes"),
            int_value(row, "conflicted_bytes"),
            int_value(row, "singleton_bytes"),
            str(row["selector_family"]),
        )
    )
    for index, row in enumerate(output, start=1):
        row["rank"] = index
    return output


def build_summary(
    source_rows: list[dict[str, str]],
    rows: list[dict[str, object]],
    split_rows: list[dict[str, object]],
    family_rows: list[dict[str, object]],
) -> dict[str, object]:
    conflict_bytes = sum(int_value(row, "length") for row in rows)
    repeated = [row for row in split_rows if int_value(row, "rows") > 1]
    deterministic = [row for row in repeated if int_value(row, "deterministic_bytes") > 0]
    conflicted = [row for row in repeated if int_value(row, "conflicted_bytes") > 0]
    singletons = [row for row in split_rows if int_value(row, "rows") == 1]
    best_split = max(
        family_rows,
        key=lambda row: (
            int_value(row, "deterministic_repeated_bytes"),
            -int_value(row, "conflicted_bytes"),
            -int_value(row, "singleton_bytes"),
        ),
        default={},
    )
    low_conflict = min(
        family_rows,
        key=lambda row: (
            int_value(row, "conflicted_bytes"),
            -int_value(row, "deterministic_repeated_bytes"),
            int_value(row, "singleton_bytes"),
        ),
        default={},
    )
    return {
        "scope": "total",
        "source_rows": len(source_rows),
        "source_bytes": sum(int_value(row, "length") for row in source_rows),
        "conflict_groups": len({str(row["conflict_group_key"]) for row in rows}),
        "conflict_rows": len(rows),
        "conflict_bytes": conflict_bytes,
        "split_families": len(family_rows),
        "split_groups": len(split_rows),
        "repeated_split_groups": len(repeated),
        "deterministic_repeated_groups": len(deterministic),
        "deterministic_repeated_bytes": sum(int_value(row, "deterministic_bytes") for row in deterministic),
        "conflicted_groups": len(conflicted),
        "conflicted_bytes": sum(int_value(row, "conflicted_bytes") for row in conflicted),
        "singleton_groups": len(singletons),
        "singleton_bytes": sum(int_value(row, "singleton_bytes") for row in singletons),
        "best_split_family": best_split.get("selector_family", ""),
        "best_split_deterministic_bytes": best_split.get("deterministic_repeated_bytes", 0),
        "best_split_conflicted_bytes": best_split.get("conflicted_bytes", 0),
        "best_split_singleton_bytes": best_split.get("singleton_bytes", 0),
        "best_split_conflict_reduction_bytes": best_split.get("conflict_reduction_bytes", 0),
        "best_remaining_conflict_key": best_split.get("best_remaining_conflict_key", ""),
        "low_conflict_split_family": low_conflict.get("selector_family", ""),
        "low_conflict_deterministic_bytes": low_conflict.get("deterministic_repeated_bytes", 0),
        "low_conflict_conflicted_bytes": low_conflict.get("conflicted_bytes", 0),
        "low_conflict_singleton_bytes": low_conflict.get("singleton_bytes", 0),
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
    split_rows: list[dict[str, object]],
    family_rows: list[dict[str, object]],
    title: str,
) -> str:
    data_json = json.dumps(
        {"summary": summary, "rows": rows, "splits": split_rows, "families": family_rows},
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
  <div class="box"><div class="num">{summary['conflict_bytes']}</div><div class="muted">conflict bytes</div></div>
  <div class="box"><div class="num">{summary['best_split_family']}</div><div class="muted">best repeated split</div></div>
  <div class="box"><div class="num">{summary['best_split_deterministic_bytes']}</div><div class="muted">deterministic bytes</div></div>
  <div class="box"><div class="num">{summary['best_split_conflicted_bytes']}</div><div class="muted">remaining conflict bytes</div></div>
  <div class="box"><div class="num">{summary['low_conflict_split_family']}</div><div class="muted">lowest conflict split</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Rows</h2>{render_table(rows, ROW_FIELDNAMES)}</div>
<div class="panel"><h2>Families</h2>{render_table(family_rows, FAMILY_FIELDNAMES)}</div>
<div class="panel"><h2>Splits</h2>{render_table(split_rows, SPLIT_FIELDNAMES)}</div>
<script type="application/json" id="gradient-macro-conflict-split-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Split conflicted gradient macro opcode selector groups.")
    parser.add_argument("--input-rows", type=Path, default=DEFAULT_INPUT_ROWS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Gradient Macro Conflict Split")
    args = parser.parse_args()

    source_rows = read_csv(args.input_rows)
    rows = conflict_members(source_rows)
    split_rows = build_split_rows(rows)
    conflict_bytes = sum(int_value(row, "length") for row in rows)
    family_rows = build_family_rows(split_rows, conflict_bytes)
    summary = build_summary(source_rows, rows, split_rows, family_rows)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "rows.csv", ROW_FIELDNAMES, rows)
    write_csv(args.output / "splits.csv", SPLIT_FIELDNAMES, split_rows)
    write_csv(args.output / "families.csv", FAMILY_FIELDNAMES, family_rows)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, rows, split_rows, family_rows, args.title))

    print(f"Conflict groups: {summary['conflict_groups']}")
    print(f"Conflict bytes: {summary['conflict_bytes']}")
    print(
        f"Best repeated split: {summary['best_split_family']} "
        f"{summary['best_split_deterministic_bytes']} deterministic, "
        f"{summary['best_split_conflicted_bytes']} conflicted"
    )
    print(
        f"Lowest conflict split: {summary['low_conflict_split_family']} "
        f"{summary['low_conflict_deterministic_bytes']} deterministic, "
        f"{summary['low_conflict_conflicted_bytes']} conflicted, "
        f"{summary['low_conflict_singleton_bytes']} singleton"
    )
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
