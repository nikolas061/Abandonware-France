#!/usr/bin/env python3
"""Score context-to-run rule candidates for stable micro-token sources."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path


DEFAULT_CONTEXTS = Path("output/tex_micro_stable_value_context/contexts.csv")
DEFAULT_OUTPUT = Path("output/tex_micro_stable_context_rules")

SUMMARY_FIELDNAMES = [
    "scope",
    "context_rows",
    "context_bytes",
    "rule_rows",
    "deterministic_rule_rows",
    "deterministic_rule_bytes",
    "deterministic_context_exact_rows",
    "deterministic_context_exact_bytes",
    "deterministic_shape_rows",
    "deterministic_shape_bytes",
    "conflicted_rule_rows",
    "conflicted_rule_bytes",
    "best_rule_family",
    "best_rule_key",
    "best_rule_rows",
    "best_rule_bytes",
    "best_rule_values",
    "best_rule_lengths",
    "promotion_ready_bytes",
    "issue_rows",
]

RULE_FIELDNAMES = [
    "rank",
    "rule_family",
    "rule_key",
    "rows",
    "bytes",
    "values",
    "lengths",
    "value_length_pairs",
    "fixtures",
    "deterministic_value",
    "deterministic_length",
    "deterministic_pair",
    "sample_pcx",
    "sample_frontier_id",
    "verdict",
]

TARGET_FIELDNAMES = [
    "rank",
    "rule_rank",
    "rule_family",
    "rule_key",
    "source_rank",
    "group_rank",
    "pcx_name",
    "frontier_id",
    "run_index",
    "run_value_hex",
    "run_length",
    "context_hex",
    "shape_key",
    "offset_delta",
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


def rule_keys(row: dict[str, str]) -> list[tuple[str, str]]:
    return [
        ("context_exact", row.get("context_key", "")),
        ("context_shape", row.get("shape_key", "")),
        ("context_exact_offset_delta", f"{row.get('context_key', '')}|delta={row.get('offset_delta', '')}"),
        ("context_shape_offset_delta", f"{row.get('shape_key', '')}|delta={row.get('offset_delta', '')}"),
        ("context_exact_value", f"{row.get('context_key', '')}|value={row.get('run_value_hex', '')}"),
        ("context_shape_value", f"{row.get('shape_key', '')}|value={row.get('run_value_hex', '')}"),
    ]


def build(context_rows: list[dict[str, str]]) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in context_rows:
        for family, key in rule_keys(row):
            if key:
                grouped[(family, key)].append(row)

    rule_rows: list[dict[str, object]] = []
    target_rows: list[dict[str, object]] = []
    for (family, key), rows in grouped.items():
        values = sorted({row.get("run_value_hex", "") for row in rows})
        lengths = sorted({int_value(row, "run_length") for row in rows})
        pairs = sorted({(row.get("run_value_hex", ""), int_value(row, "run_length")) for row in rows})
        deterministic_pair = len(pairs) == 1
        deterministic_value = len(values) == 1
        deterministic_length = len(lengths) == 1
        verdict = "deterministic_pair_review" if deterministic_pair and len(rows) > 1 else "conflicted_or_singleton_review"
        rule_rows.append(
            {
                "rank": 0,
                "rule_family": family,
                "rule_key": key,
                "rows": len(rows),
                "bytes": sum(int_value(row, "run_length") for row in rows),
                "values": ";".join(values),
                "lengths": ";".join(str(value) for value in lengths),
                "value_length_pairs": ";".join(f"{value}:{length}" for value, length in pairs),
                "fixtures": len({(row.get("archive", ""), row.get("pcx_name", ""), row.get("frontier_id", "")) for row in rows}),
                "deterministic_value": 1 if deterministic_value else 0,
                "deterministic_length": 1 if deterministic_length else 0,
                "deterministic_pair": 1 if deterministic_pair else 0,
                "sample_pcx": rows[0].get("pcx_name", ""),
                "sample_frontier_id": rows[0].get("frontier_id", ""),
                "verdict": verdict,
            }
        )

    rule_rows.sort(
        key=lambda row: (
            -int(row["deterministic_pair"]),
            -int(row["rows"]),
            -int(row["bytes"]),
            str(row["rule_family"]),
            str(row["rule_key"]),
        )
    )
    rule_rank = {(str(row["rule_family"]), str(row["rule_key"])): index for index, row in enumerate(rule_rows, start=1)}
    for index, row in enumerate(rule_rows, start=1):
        row["rank"] = index

    for source in context_rows:
        for family, key in rule_keys(source):
            if not key:
                continue
            target_rows.append(
                {
                    "rank": 0,
                    "rule_rank": rule_rank[(family, key)],
                    "rule_family": family,
                    "rule_key": key,
                    "source_rank": source.get("source_rank", ""),
                    "group_rank": source.get("group_rank", ""),
                    "pcx_name": source.get("pcx_name", ""),
                    "frontier_id": source.get("frontier_id", ""),
                    "run_index": source.get("run_index", ""),
                    "run_value_hex": source.get("run_value_hex", ""),
                    "run_length": source.get("run_length", ""),
                    "context_hex": source.get("context_hex", ""),
                    "shape_key": source.get("shape_key", ""),
                    "offset_delta": source.get("offset_delta", ""),
                }
            )
    target_rows.sort(key=lambda row: (int(row["rule_rank"]), int(row["source_rank"]), int(row["run_index"])))
    for index, row in enumerate(target_rows, start=1):
        row["rank"] = index

    deterministic = [row for row in rule_rows if int(row["deterministic_pair"]) and int(row["rows"]) > 1]
    deterministic_exact = [row for row in deterministic if row["rule_family"] == "context_exact"]
    deterministic_shape = [row for row in deterministic if row["rule_family"] == "context_shape"]
    conflicted = [row for row in rule_rows if not int(row["deterministic_pair"]) and int(row["rows"]) > 1]
    best = deterministic[0] if deterministic else (rule_rows[0] if rule_rows else {})
    summary = {
        "scope": "total",
        "context_rows": len(context_rows),
        "context_bytes": sum(int_value(row, "run_length") for row in context_rows),
        "rule_rows": len(rule_rows),
        "deterministic_rule_rows": len(deterministic),
        "deterministic_rule_bytes": sum(int(row["bytes"]) for row in deterministic),
        "deterministic_context_exact_rows": len(deterministic_exact),
        "deterministic_context_exact_bytes": sum(int(row["bytes"]) for row in deterministic_exact),
        "deterministic_shape_rows": len(deterministic_shape),
        "deterministic_shape_bytes": sum(int(row["bytes"]) for row in deterministic_shape),
        "conflicted_rule_rows": len(conflicted),
        "conflicted_rule_bytes": sum(int(row["bytes"]) for row in conflicted),
        "best_rule_family": best.get("rule_family", ""),
        "best_rule_key": best.get("rule_key", ""),
        "best_rule_rows": best.get("rows", 0),
        "best_rule_bytes": best.get("bytes", 0),
        "best_rule_values": best.get("values", ""),
        "best_rule_lengths": best.get("lengths", ""),
        "promotion_ready_bytes": 0,
        "issue_rows": 0,
    }
    return summary, rule_rows, target_rows


def render_table(rows: list[dict[str, object]], fields: list[str], limit: int = 220) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, object],
    rules: list[dict[str, object]],
    targets: list[dict[str, object]],
    title: str,
) -> str:
    data_json = json.dumps({"summary": summary, "rules": rules, "targets": targets}, indent=2, sort_keys=True)
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
  <div class="box"><div class="num">{summary['rule_rows']}</div><div class="muted">rule rows</div></div>
  <div class="box"><div class="num">{summary['deterministic_rule_rows']}</div><div class="muted">deterministic rules</div></div>
  <div class="box"><div class="num">{summary['deterministic_context_exact_bytes']}</div><div class="muted">deterministic exact bytes</div></div>
  <div class="box"><div class="num">{summary['conflicted_rule_bytes']}</div><div class="muted">conflicted bytes</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Rules</h2>{render_table(rules, RULE_FIELDNAMES)}</div>
<div class="panel"><h2>Targets</h2>{render_table(targets, TARGET_FIELDNAMES)}</div>
<script type="application/json" id="stable-context-rule-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Score context-to-run rules for stable .tex micro-token sources.")
    parser.add_argument("--contexts", type=Path, default=DEFAULT_CONTEXTS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Micro Stable Context Rules")
    args = parser.parse_args()

    summary, rules, targets = build(read_rows(args.contexts))
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "rules.csv", RULE_FIELDNAMES, rules)
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, targets)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, rules, targets, args.title))

    print(f"Rule rows: {summary['rule_rows']}")
    print(f"Deterministic rule bytes: {summary['deterministic_rule_bytes']}")
    print(f"Deterministic exact bytes: {summary['deterministic_context_exact_bytes']}")
    print(f"Conflicted rule bytes: {summary['conflicted_rule_bytes']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
