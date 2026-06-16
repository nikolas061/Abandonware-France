#!/usr/bin/env python3
"""Probe run-to-run state transitions for stable micro-token sources."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import defaultdict
from pathlib import Path


DEFAULT_CONTEXTS = Path("output/tex_micro_stable_value_context/contexts.csv")
DEFAULT_OUTPUT = Path("output/tex_micro_stable_sequences")

SUMMARY_FIELDNAMES = [
    "scope",
    "source_rows",
    "transition_rows",
    "transition_bytes",
    "rule_rows",
    "deterministic_next_pair_rows",
    "deterministic_next_pair_bytes",
    "deterministic_shape_offset_step_rows",
    "deterministic_shape_offset_step_bytes",
    "deterministic_value_offset_step_rows",
    "deterministic_value_offset_step_bytes",
    "deterministic_next_value_rows",
    "deterministic_next_value_bytes",
    "deterministic_next_length_rows",
    "deterministic_next_length_bytes",
    "best_rule_family",
    "best_rule_rows",
    "best_rule_bytes",
    "best_rule_next_pairs",
    "promotion_ready_bytes",
    "issue_rows",
]

TRANSITION_FIELDNAMES = [
    "rank",
    "source_rank",
    "group_rank",
    "archive",
    "pcx_name",
    "frontier_id",
    "run_index",
    "value_hex",
    "length",
    "offset",
    "offset_delta",
    "next_value_hex",
    "next_length",
    "next_offset",
    "next_offset_step",
    "value_delta",
    "length_delta",
    "shape_key",
    "next_shape_key",
]

RULE_FIELDNAMES = [
    "rank",
    "rule_family",
    "rule_key",
    "rows",
    "bytes",
    "next_values",
    "next_lengths",
    "next_pairs",
    "deterministic_next_value",
    "deterministic_next_length",
    "deterministic_next_pair",
    "sample_pcx",
    "sample_frontier_id",
    "verdict",
]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def int_value(row: dict[str, str], field: str) -> int:
    try:
        return int(row.get(field, "") or 0)
    except ValueError:
        return 0


def value_int(text: str) -> int:
    try:
        return int(text, 16)
    except ValueError:
        return 0


def source_key(row: dict[str, str]) -> tuple[str, str, str, str]:
    return row.get("archive", ""), row.get("pcx_name", ""), row.get("frontier_id", ""), row.get("source_rank", "")


def transition_rule_keys(row: dict[str, object]) -> list[tuple[str, str]]:
    return [
        ("value", str(row["value_hex"])),
        ("value_length", f"{row['value_hex']}:{row['length']}"),
        ("value_offset_step", f"{row['value_hex']}|step={row['next_offset_step']}"),
        ("value_length_offset_step", f"{row['value_hex']}:{row['length']}|step={row['next_offset_step']}"),
        ("shape", str(row["shape_key"])),
        ("shape_offset_step", f"{row['shape_key']}|step={row['next_offset_step']}"),
        ("value_delta", f"{row['value_hex']}|vdelta={row['value_delta']}"),
        ("length_delta", f"{row['value_hex']}|ldelta={row['length_delta']}"),
    ]


def build_transitions(context_rows: list[dict[str, str]]) -> list[dict[str, object]]:
    rows_by_source: dict[tuple[str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in context_rows:
        rows_by_source[source_key(row)].append(row)

    transitions: list[dict[str, object]] = []
    for rows in rows_by_source.values():
        rows.sort(key=lambda row: int_value(row, "run_index"))
        for current, nxt in zip(rows, rows[1:]):
            value = value_int(current.get("run_value_hex", "0x00"))
            next_value = value_int(nxt.get("run_value_hex", "0x00"))
            length = int_value(current, "run_length")
            next_length = int_value(nxt, "run_length")
            offset = int_value(current, "nearest_value_offset")
            next_offset = int_value(nxt, "nearest_value_offset")
            transitions.append(
                {
                    "rank": 0,
                    "source_rank": current.get("source_rank", ""),
                    "group_rank": current.get("group_rank", ""),
                    "archive": current.get("archive", ""),
                    "pcx_name": current.get("pcx_name", ""),
                    "frontier_id": current.get("frontier_id", ""),
                    "run_index": current.get("run_index", ""),
                    "value_hex": current.get("run_value_hex", ""),
                    "length": length,
                    "offset": offset,
                    "offset_delta": current.get("offset_delta", ""),
                    "next_value_hex": nxt.get("run_value_hex", ""),
                    "next_length": next_length,
                    "next_offset": next_offset,
                    "next_offset_step": next_offset - offset,
                    "value_delta": next_value - value,
                    "length_delta": next_length - length,
                    "shape_key": current.get("shape_key", ""),
                    "next_shape_key": nxt.get("shape_key", ""),
                }
            )
    for index, row in enumerate(transitions, start=1):
        row["rank"] = index
    return transitions


def build_rules(transitions: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for row in transitions:
        for family, key in transition_rule_keys(row):
            grouped[(family, key)].append(row)

    rules: list[dict[str, object]] = []
    for (family, key), rows in grouped.items():
        next_values = sorted({str(row["next_value_hex"]) for row in rows})
        next_lengths = sorted({int(row["next_length"]) for row in rows})
        next_pairs = sorted({(str(row["next_value_hex"]), int(row["next_length"])) for row in rows})
        deterministic_pair = len(next_pairs) == 1
        deterministic_value = len(next_values) == 1
        deterministic_length = len(next_lengths) == 1
        rules.append(
            {
                "rank": 0,
                "rule_family": family,
                "rule_key": key,
                "rows": len(rows),
                "bytes": sum(int(row["next_length"]) for row in rows),
                "next_values": ";".join(next_values),
                "next_lengths": ";".join(str(value) for value in next_lengths),
                "next_pairs": ";".join(f"{value}:{length}" for value, length in next_pairs),
                "deterministic_next_value": 1 if deterministic_value else 0,
                "deterministic_next_length": 1 if deterministic_length else 0,
                "deterministic_next_pair": 1 if deterministic_pair else 0,
                "sample_pcx": rows[0]["pcx_name"],
                "sample_frontier_id": rows[0]["frontier_id"],
                "verdict": "deterministic_transition_review" if deterministic_pair and len(rows) > 1 else "transition_review",
            }
        )
    rules.sort(
        key=lambda row: (
            -int(row["deterministic_next_pair"]),
            -int(row["rows"]),
            -int(row["bytes"]),
            str(row["rule_family"]),
            str(row["rule_key"]),
        )
    )
    for index, row in enumerate(rules, start=1):
        row["rank"] = index
    return rules


def build(context_rows: list[dict[str, str]]) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    transitions = build_transitions(context_rows)
    rules = build_rules(transitions)
    deterministic_pair = [row for row in rules if int(row["deterministic_next_pair"]) and int(row["rows"]) > 1]
    deterministic_shape_step = [row for row in deterministic_pair if row["rule_family"] == "shape_offset_step"]
    deterministic_value_step = [row for row in deterministic_pair if row["rule_family"] == "value_offset_step"]
    deterministic_value = [row for row in rules if int(row["deterministic_next_value"]) and int(row["rows"]) > 1]
    deterministic_length = [row for row in rules if int(row["deterministic_next_length"]) and int(row["rows"]) > 1]
    best = deterministic_pair[0] if deterministic_pair else (rules[0] if rules else {})
    summary = {
        "scope": "total",
        "source_rows": len({source_key(row) for row in context_rows}),
        "transition_rows": len(transitions),
        "transition_bytes": sum(int(row["next_length"]) for row in transitions),
        "rule_rows": len(rules),
        "deterministic_next_pair_rows": len(deterministic_pair),
        "deterministic_next_pair_bytes": sum(int(row["bytes"]) for row in deterministic_pair),
        "deterministic_shape_offset_step_rows": len(deterministic_shape_step),
        "deterministic_shape_offset_step_bytes": sum(int(row["bytes"]) for row in deterministic_shape_step),
        "deterministic_value_offset_step_rows": len(deterministic_value_step),
        "deterministic_value_offset_step_bytes": sum(int(row["bytes"]) for row in deterministic_value_step),
        "deterministic_next_value_rows": len(deterministic_value),
        "deterministic_next_value_bytes": sum(int(row["bytes"]) for row in deterministic_value),
        "deterministic_next_length_rows": len(deterministic_length),
        "deterministic_next_length_bytes": sum(int(row["bytes"]) for row in deterministic_length),
        "best_rule_family": best.get("rule_family", ""),
        "best_rule_rows": best.get("rows", 0),
        "best_rule_bytes": best.get("bytes", 0),
        "best_rule_next_pairs": best.get("next_pairs", ""),
        "promotion_ready_bytes": 0,
        "issue_rows": 0,
    }
    return summary, transitions, rules


def render_table(rows: list[dict[str, object]], fields: list[str], limit: int = 220) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, object],
    transitions: list[dict[str, object]],
    rules: list[dict[str, object]],
    title: str,
) -> str:
    data_json = json.dumps({"summary": summary, "transitions": transitions, "rules": rules}, indent=2, sort_keys=True)
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body {{ margin: 2rem; background: #111416; color: #edf5f4; font: 14px/1.45 system-ui, sans-serif; }}
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
  <div class="box"><div class="num">{summary['transition_rows']}</div><div class="muted">transition rows</div></div>
  <div class="box"><div class="num">{summary['deterministic_next_pair_rows']}</div><div class="muted">deterministic pair rules</div></div>
  <div class="box"><div class="num">{summary['deterministic_shape_offset_step_bytes']}</div><div class="muted">shape-step pair bytes</div></div>
  <div class="box"><div class="num">{summary['best_rule_family']}</div><div class="muted">best rule family</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Rules</h2>{render_table(rules, RULE_FIELDNAMES)}</div>
<div class="panel"><h2>Transitions</h2>{render_table(transitions, TRANSITION_FIELDNAMES)}</div>
<script type="application/json" id="stable-sequence-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe stable .tex source run-to-run transitions.")
    parser.add_argument("--contexts", type=Path, default=DEFAULT_CONTEXTS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Micro Stable Sequences")
    args = parser.parse_args()

    summary, transitions, rules = build(read_rows(args.contexts))
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "transitions.csv", TRANSITION_FIELDNAMES, transitions)
    write_csv(args.output / "rules.csv", RULE_FIELDNAMES, rules)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, transitions, rules, args.title))

    print(f"Transition rows: {summary['transition_rows']}")
    print(f"Deterministic next-pair bytes: {summary['deterministic_next_pair_bytes']}")
    print(f"Best rule family: {summary['best_rule_family']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
