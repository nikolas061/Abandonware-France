#!/usr/bin/env python3
"""Probe vertical backrefs between gradient macro-state cluster rows."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections.abc import Callable
from pathlib import Path


DEFAULT_CLUSTER_ROWS = Path("output/tex_gradient_macro_state_cluster/rows.csv")
DEFAULT_LITERAL_ROWS = Path("output/tex_gradient_macro_state_cluster_literal/rows.csv")
DEFAULT_OUTPUT = Path("output/tex_gradient_macro_state_cluster_backref")
DEFAULT_ROW_WIDTH = 320

SUMMARY_FIELDNAMES = [
    "scope",
    "cluster_rows",
    "cluster_bytes",
    "same_length_back320_rows",
    "same_length_back320_bytes",
    "exact_back320_rows",
    "exact_back320_bytes",
    "false_back320_rows",
    "false_back320_bytes",
    "literal_target_exact_rows",
    "literal_target_exact_bytes",
    "best_rule",
    "best_rule_rows",
    "best_rule_bytes",
    "best_rule_exact_rows",
    "best_rule_exact_bytes",
    "best_rule_false_rows",
    "best_rule_false_bytes",
    "candidate_review_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

PAIR_FIELDNAMES = [
    "rank",
    "archive",
    "pcx_name",
    "frontier_id",
    "source_rank",
    "target_rank",
    "source_start",
    "target_start",
    "source_y",
    "target_y",
    "x",
    "length",
    "start_delta",
    "span_delta",
    "op_delta",
    "source_op_phase8",
    "target_op_phase8",
    "source_skip_bucket",
    "target_skip_bucket",
    "source_top_nibble",
    "target_top_nibble",
    "source_gradient_class",
    "target_gradient_class",
    "source_frontier_position",
    "target_frontier_position",
    "source_payload_signature",
    "target_payload_signature",
    "same_payload_signature",
    "correct_bytes",
    "false_bytes",
    "literal_target_row",
    "verdict",
]

RULE_FIELDNAMES = [
    "rule",
    "rows",
    "bytes",
    "exact_rows",
    "exact_bytes",
    "false_rows",
    "false_bytes",
    "literal_target_exact_rows",
    "literal_target_exact_bytes",
    "precision",
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


def ratio(numerator: int, denominator: int) -> str:
    return f"{numerator / denominator:.6f}" if denominator else "0.000000"


def literal_keys(rows: list[dict[str, str]]) -> set[tuple[str, str, str, int, int, int]]:
    keys: set[tuple[str, str, str, int, int, int]] = set()
    for row in rows:
        keys.add(
            (
                row.get("archive", ""),
                row.get("pcx_name", ""),
                row.get("frontier_id", ""),
                int_value(row, "start"),
                int_value(row, "end"),
                int_value(row, "length"),
            )
        )
    return keys


def build_pairs(
    cluster_rows: list[dict[str, str]],
    literal_rows: list[dict[str, str]],
    *,
    row_width: int,
) -> list[dict[str, object]]:
    by_start = {
        (
            row.get("archive", ""),
            row.get("pcx_name", ""),
            row.get("frontier_id", ""),
            int_value(row, "start"),
        ): row
        for row in cluster_rows
    }
    literal_targets = literal_keys(literal_rows)
    pairs: list[dict[str, object]] = []

    for target in cluster_rows:
        target_start = int_value(target, "start")
        source_start = target_start - row_width
        source = by_start.get(
            (
                target.get("archive", ""),
                target.get("pcx_name", ""),
                target.get("frontier_id", ""),
                source_start,
            )
        )
        if not source or int_value(source, "length") != int_value(target, "length"):
            continue

        length = int_value(target, "length")
        exact = source.get("payload_signature", "") == target.get("payload_signature", "")
        literal_target = (
            target.get("archive", ""),
            target.get("pcx_name", ""),
            target.get("frontier_id", ""),
            target_start,
            int_value(target, "end"),
            length,
        ) in literal_targets
        correct = length if exact else 0
        pair = {
            "rank": len(pairs) + 1,
            "archive": target.get("archive", ""),
            "pcx_name": target.get("pcx_name", ""),
            "frontier_id": target.get("frontier_id", ""),
            "source_rank": source.get("rank", ""),
            "target_rank": target.get("rank", ""),
            "source_start": source_start,
            "target_start": target_start,
            "source_y": source_start // row_width,
            "target_y": target_start // row_width,
            "x": target_start % row_width,
            "length": length,
            "start_delta": target_start - source_start,
            "span_delta": int_value(target, "span_index") - int_value(source, "span_index"),
            "op_delta": int_value(target, "op_index") - int_value(source, "op_index"),
            "source_op_phase8": source.get("op_phase8", ""),
            "target_op_phase8": target.get("op_phase8", ""),
            "source_skip_bucket": source.get("fixture_skip_bucket", ""),
            "target_skip_bucket": target.get("fixture_skip_bucket", ""),
            "source_top_nibble": source.get("top_nibble", ""),
            "target_top_nibble": target.get("top_nibble", ""),
            "source_gradient_class": source.get("gradient_class", ""),
            "target_gradient_class": target.get("gradient_class", ""),
            "source_frontier_position": source.get("frontier_position", ""),
            "target_frontier_position": target.get("frontier_position", ""),
            "source_payload_signature": source.get("payload_signature", ""),
            "target_payload_signature": target.get("payload_signature", ""),
            "same_payload_signature": 1 if exact else 0,
            "correct_bytes": correct,
            "false_bytes": length - correct,
            "literal_target_row": 1 if literal_target else 0,
            "verdict": "exact_vertical_backref_candidate" if exact else "vertical_backref_false",
        }
        pairs.append(pair)

    return pairs


RulePredicate = Callable[[dict[str, object]], bool]


def candidate_rules() -> list[tuple[str, RulePredicate]]:
    return [
        ("same_length_back320", lambda row: True),
        (
            "same_length_back320_flat_walk",
            lambda row: row.get("target_gradient_class") == "flat_run_walk",
        ),
        (
            "same_length_back320_top6_flat_walk",
            lambda row: row.get("target_top_nibble") == "0x6"
            and row.get("target_gradient_class") == "flat_run_walk",
        ),
        (
            "same_length_back320_same_skip_flat_walk",
            lambda row: row.get("source_skip_bucket") == row.get("target_skip_bucket")
            and row.get("target_gradient_class") == "flat_run_walk",
        ),
        (
            "same_length_back320_op_delta15_17",
            lambda row: 15 <= int_value(row, "op_delta") <= 17,
        ),
        (
            "same_length_back320_op_delta15_17_flat_walk",
            lambda row: 15 <= int_value(row, "op_delta") <= 17
            and row.get("target_gradient_class") == "flat_run_walk",
        ),
    ]


def build_rules(pairs: list[dict[str, object]]) -> list[dict[str, object]]:
    rules: list[dict[str, object]] = []
    for name, predicate in candidate_rules():
        selected = [row for row in pairs if predicate(row)]
        exact_rows = [row for row in selected if int_value(row, "same_payload_signature") == 1]
        false_rows = [row for row in selected if int_value(row, "same_payload_signature") == 0]
        literal_exact = [row for row in exact_rows if int_value(row, "literal_target_row") == 1]
        exact_bytes = sum(int_value(row, "length") for row in exact_rows)
        false_bytes = sum(int_value(row, "length") for row in false_rows)
        total_bytes = exact_bytes + false_bytes
        verdict = (
            "exact_candidate_review"
            if exact_rows and not false_rows
            else "mixed_exact_false"
            if exact_rows
            else "reject"
        )
        rules.append(
            {
                "rule": name,
                "rows": len(selected),
                "bytes": total_bytes,
                "exact_rows": len(exact_rows),
                "exact_bytes": exact_bytes,
                "false_rows": len(false_rows),
                "false_bytes": false_bytes,
                "literal_target_exact_rows": len(literal_exact),
                "literal_target_exact_bytes": sum(int_value(row, "length") for row in literal_exact),
                "precision": ratio(exact_bytes, total_bytes),
                "verdict": verdict,
            }
        )
    rules.sort(
        key=lambda row: (
            int_value(row, "false_bytes") == 0,
            int_value(row, "exact_bytes"),
            -int_value(row, "false_bytes"),
        ),
        reverse=True,
    )
    return rules


def build_summary(
    cluster_rows: list[dict[str, str]],
    pairs: list[dict[str, object]],
    rules: list[dict[str, object]],
) -> dict[str, object]:
    exact_pairs = [row for row in pairs if int_value(row, "same_payload_signature") == 1]
    false_pairs = [row for row in pairs if int_value(row, "same_payload_signature") == 0]
    literal_exact = [row for row in exact_pairs if int_value(row, "literal_target_row") == 1]
    best_rule = rules[0] if rules else {}
    candidate_review_bytes = (
        int_value(best_rule, "exact_bytes") if int_value(best_rule, "false_bytes") == 0 else 0
    )
    return {
        "scope": "total",
        "cluster_rows": len(cluster_rows),
        "cluster_bytes": sum(int_value(row, "length") for row in cluster_rows),
        "same_length_back320_rows": len(pairs),
        "same_length_back320_bytes": sum(int_value(row, "length") for row in pairs),
        "exact_back320_rows": len(exact_pairs),
        "exact_back320_bytes": sum(int_value(row, "length") for row in exact_pairs),
        "false_back320_rows": len(false_pairs),
        "false_back320_bytes": sum(int_value(row, "length") for row in false_pairs),
        "literal_target_exact_rows": len(literal_exact),
        "literal_target_exact_bytes": sum(int_value(row, "length") for row in literal_exact),
        "best_rule": best_rule.get("rule", ""),
        "best_rule_rows": best_rule.get("rows", 0),
        "best_rule_bytes": best_rule.get("bytes", 0),
        "best_rule_exact_rows": best_rule.get("exact_rows", 0),
        "best_rule_exact_bytes": best_rule.get("exact_bytes", 0),
        "best_rule_false_rows": best_rule.get("false_rows", 0),
        "best_rule_false_bytes": best_rule.get("false_bytes", 0),
        "candidate_review_bytes": candidate_review_bytes,
        "promotion_ready_bytes": 0,
        "issue_rows": 0,
    }


def render_table(rows: list[dict[str, object]], fields: list[str]) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, object],
    pairs: list[dict[str, object]],
    rules: list[dict[str, object]],
    title: str,
) -> str:
    data_json = json.dumps({"summary": summary, "pairs": pairs, "rules": rules}, indent=2, sort_keys=True)
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
  <div class="box"><div class="num">{summary['same_length_back320_rows']}</div><div class="muted">paires -320</div></div>
  <div class="box"><div class="num">{summary['exact_back320_bytes']}</div><div class="muted">bytes exacts</div></div>
  <div class="box"><div class="num">{summary['false_back320_bytes']}</div><div class="muted">bytes faux</div></div>
  <div class="box"><div class="num">{html.escape(str(summary['best_rule']))}</div><div class="muted">meilleure regle</div></div>
  <div class="box"><div class="num">{summary['candidate_review_bytes']}</div><div class="muted">bytes candidats</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Rules</h2>{render_table(rules, RULE_FIELDNAMES)}</div>
<div class="panel"><h2>Pairs</h2>{render_table(pairs, PAIR_FIELDNAMES)}</div>
<script type="application/json" id="gradient-macro-state-cluster-backref-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe -320 vertical backrefs in gradient macro-state clusters.")
    parser.add_argument("--cluster-rows", type=Path, default=DEFAULT_CLUSTER_ROWS)
    parser.add_argument("--literal-rows", type=Path, default=DEFAULT_LITERAL_ROWS)
    parser.add_argument("--row-width", type=int, default=DEFAULT_ROW_WIDTH)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Gradient Macro State Cluster Backrefs")
    args = parser.parse_args()

    cluster_rows = read_csv(args.cluster_rows)
    literal_rows = read_csv(args.literal_rows) if args.literal_rows.exists() else []
    pairs = build_pairs(cluster_rows, literal_rows, row_width=args.row_width)
    rules = build_rules(pairs)
    summary = build_summary(cluster_rows, pairs, rules)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "pairs.csv", PAIR_FIELDNAMES, pairs)
    write_csv(args.output / "rules.csv", RULE_FIELDNAMES, rules)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, pairs, rules, args.title))

    print(f"Back320 same-length rows: {summary['same_length_back320_rows']}")
    print(f"Exact back320 bytes: {summary['exact_back320_bytes']}")
    print(f"False back320 bytes: {summary['false_back320_bytes']}")
    print(
        f"Best rule: {summary['best_rule']} "
        f"exact={summary['best_rule_exact_bytes']} false={summary['best_rule_false_bytes']}"
    )
    print(f"Candidate review bytes: {summary['candidate_review_bytes']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
