#!/usr/bin/env python3
"""Score .tex decoder skeleton candidates with zero/literal false-positive risk."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import defaultdict
from pathlib import Path

from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_risk_adjusted_probe")
DEFAULT_OPERATIONS = Path("output/tex_gap_segmentation_control_correlation_probe/operations.csv")
DEFAULT_LITERALS = Path("output/tex_gap_literal_token_probe/literals.csv")

REPEATED_FALSE_PRE4 = {"6edc020a", "5d5c0703", "6bfc0704", "17542f08"}
REPEATED_FALSE_NEXT2 = {"5a5c", "5d6d", "aa6c", "7b6a"}
REPEATED_FALSE_MOD64 = {5, 28, 34}

SUMMARY_FIELDNAMES = [
    "scope",
    "operation_rows",
    "fixture_rows",
    "total_expected_bytes",
    "candidate_rows",
    "best_nonoracle_by_correct",
    "best_nonoracle_correct_bytes",
    "best_nonoracle_false_bytes",
    "best_nonoracle_net_bytes",
    "best_nonoracle_by_net",
    "best_net_correct_bytes",
    "best_net_false_bytes",
    "best_net_bytes",
    "best_low_false_candidate",
    "best_low_false_correct_bytes",
    "best_low_false_false_bytes",
    "best_oracle_candidate",
    "best_oracle_correct_bytes",
    "best_oracle_false_bytes",
    "issue_rows",
]

CANDIDATE_FIELDNAMES = [
    "candidate",
    "priority",
    "zero_rule",
    "literal_rule",
    "uses_oracle_filter",
    "total_expected_bytes",
    "selected_zero_ops",
    "true_zero_ops",
    "false_zero_ops",
    "selected_literal_ops",
    "true_literal_ops",
    "false_literal_ops",
    "conflict_ops",
    "true_zero_bytes",
    "false_zero_bytes",
    "true_literal_bytes",
    "false_literal_bytes",
    "correct_bytes",
    "false_bytes",
    "net_bytes",
    "coverage_ratio",
    "false_ratio",
    "unselected_bytes",
]

FIXTURE_FIELDNAMES = [
    "candidate",
    "rank",
    "pcx_name",
    "frontier_id",
    "fixture_bytes",
    "correct_bytes",
    "false_bytes",
    "net_bytes",
    "true_zero_bytes",
    "false_zero_bytes",
    "true_literal_bytes",
    "false_literal_bytes",
    "coverage_ratio",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def fixture_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", "")


def op_key(row: dict[str, str]) -> tuple[str, str, str, str]:
    return (*fixture_key(row), row.get("op_index", ""))


def enrich_literal_rows(
    literal_rows: list[dict[str, str]],
    operation_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    operations = {op_key(row): row for row in operation_rows}
    rows: list[dict[str, str]] = []
    for row in literal_rows:
        operation = operations.get(op_key(row), {})
        enriched = dict(row)
        enriched["pre4_hex"] = operation.get("pre4_hex", "")
        enriched["next2_hex"] = operation.get("next2_hex", "")
        enriched["expected_mod64"] = operation.get("expected_mod64", "")
        rows.append(enriched)
    return rows


def length(row: dict[str, str]) -> int:
    return int_value(row, "length")


def expected_mod64(row: dict[str, str]) -> int:
    return int_value(row, "expected_mod64") if row.get("expected_mod64") else -1


def literal_token(row: dict[str, str]) -> int:
    return int_value(row, "token_value") if row.get("token_value") else -1


def literal_delta(row: dict[str, str]) -> int:
    return int_value(row, "source_delta_from_prev_literal_end") if row.get("source_delta_from_prev_literal_end") else 0


def select_zero(rule: str, row: dict[str, str]) -> bool:
    row_length = length(row)
    has_u8 = bool(row.get("length_u8_hit_offsets"))
    if rule == "none":
        return False
    if rule == "len64":
        return row_length == 64
    if rule == "length_u8":
        return has_u8
    if rule == "len64_or_u8":
        return row_length == 64 or has_u8
    if rule == "len64_and_u8":
        return row_length == 64 and has_u8
    if rule == "u8_len32_64":
        return has_u8 and 32 <= row_length <= 64
    if rule == "oracle_zero":
        return row.get("op_kind") == "zero"
    raise ValueError(f"unknown zero rule: {rule}")


def select_literal(rule: str, row: dict[str, str] | None) -> bool:
    if row is None:
        return False
    token = literal_token(row)
    direction = row.get("source_direction", "")
    delta = abs(literal_delta(row))
    mod64 = expected_mod64(row)
    if rule == "none":
        return False
    if rule == "oracle_token_plus3":
        return row.get("token_plus3_match") == "1"
    if rule == "small_token":
        return 0 <= token <= 13
    if rule == "small_nonzero_next2_clean":
        return 1 <= token <= 13 and row.get("next2_hex") not in REPEATED_FALSE_NEXT2
    if rule == "small_not_backward":
        return 0 <= token <= 13 and direction != "backward"
    if rule == "small_not_backward_abs_delta_le512":
        return 0 <= token <= 13 and direction != "backward" and delta <= 512
    if rule == "small_not_backward_nonzero_pre4_mod_clean":
        return (
            1 <= token <= 13
            and direction != "backward"
            and row.get("pre4_hex") not in REPEATED_FALSE_PRE4
            and mod64 not in REPEATED_FALSE_MOD64
        )
    raise ValueError(f"unknown literal rule: {rule}")


def uses_oracle_filter(zero_rule: str, literal_rule: str) -> bool:
    return zero_rule == "oracle_zero" or literal_rule == "oracle_token_plus3"


def candidate_name(priority: str, zero_rule: str, literal_rule: str) -> str:
    return f"priority={priority}|zero={zero_rule}|literal={literal_rule}"


def fixture_totals(operation_rows: list[dict[str, str]]) -> dict[tuple[str, str, str], int]:
    totals: dict[tuple[str, str, str], int] = defaultdict(int)
    for row in operation_rows:
        totals[fixture_key(row)] += length(row)
    return totals


def score_candidate(
    priority: str,
    zero_rule: str,
    literal_rule: str,
    operation_rows: list[dict[str, str]],
    literal_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]]]:
    total_expected = sum(length(row) for row in operation_rows)
    literals = {op_key(row): row for row in literal_rows}
    name = candidate_name(priority, zero_rule, literal_rule)
    totals = {
        "selected_zero_ops": 0,
        "true_zero_ops": 0,
        "false_zero_ops": 0,
        "selected_literal_ops": 0,
        "true_literal_ops": 0,
        "false_literal_ops": 0,
        "conflict_ops": 0,
        "true_zero_bytes": 0,
        "false_zero_bytes": 0,
        "true_literal_bytes": 0,
        "false_literal_bytes": 0,
    }
    by_fixture: dict[tuple[str, str, str], dict[str, int]] = defaultdict(
        lambda: {
            "correct_bytes": 0,
            "false_bytes": 0,
            "true_zero_bytes": 0,
            "false_zero_bytes": 0,
            "true_literal_bytes": 0,
            "false_literal_bytes": 0,
        }
    )

    for operation in operation_rows:
        literal = literals.get(op_key(operation))
        zero_selected = select_zero(zero_rule, operation)
        literal_selected = select_literal(literal_rule, literal)
        if zero_selected and literal_selected:
            totals["conflict_ops"] += 1
        decision = ""
        if priority == "zero_first":
            if zero_selected:
                decision = "zero"
            elif literal_selected:
                decision = "literal"
        elif priority == "literal_first":
            if literal_selected:
                decision = "literal"
            elif zero_selected:
                decision = "zero"
        else:
            raise ValueError(f"unknown priority: {priority}")

        row_length = length(operation)
        key = fixture_key(operation)
        if decision == "zero":
            totals["selected_zero_ops"] += 1
            if operation.get("op_kind") == "zero":
                totals["true_zero_ops"] += 1
                totals["true_zero_bytes"] += row_length
                by_fixture[key]["correct_bytes"] += row_length
                by_fixture[key]["true_zero_bytes"] += row_length
            else:
                totals["false_zero_ops"] += 1
                totals["false_zero_bytes"] += row_length
                by_fixture[key]["false_bytes"] += row_length
                by_fixture[key]["false_zero_bytes"] += row_length
        elif decision == "literal":
            totals["selected_literal_ops"] += 1
            if literal and literal.get("token_plus3_match") == "1":
                totals["true_literal_ops"] += 1
                totals["true_literal_bytes"] += row_length
                by_fixture[key]["correct_bytes"] += row_length
                by_fixture[key]["true_literal_bytes"] += row_length
            else:
                totals["false_literal_ops"] += 1
                totals["false_literal_bytes"] += row_length
                by_fixture[key]["false_bytes"] += row_length
                by_fixture[key]["false_literal_bytes"] += row_length

    correct_bytes = totals["true_zero_bytes"] + totals["true_literal_bytes"]
    false_bytes = totals["false_zero_bytes"] + totals["false_literal_bytes"]
    candidate = {
        "candidate": name,
        "priority": priority,
        "zero_rule": zero_rule,
        "literal_rule": literal_rule,
        "uses_oracle_filter": "1" if uses_oracle_filter(zero_rule, literal_rule) else "0",
        "total_expected_bytes": str(total_expected),
        "selected_zero_ops": str(totals["selected_zero_ops"]),
        "true_zero_ops": str(totals["true_zero_ops"]),
        "false_zero_ops": str(totals["false_zero_ops"]),
        "selected_literal_ops": str(totals["selected_literal_ops"]),
        "true_literal_ops": str(totals["true_literal_ops"]),
        "false_literal_ops": str(totals["false_literal_ops"]),
        "conflict_ops": str(totals["conflict_ops"]),
        "true_zero_bytes": str(totals["true_zero_bytes"]),
        "false_zero_bytes": str(totals["false_zero_bytes"]),
        "true_literal_bytes": str(totals["true_literal_bytes"]),
        "false_literal_bytes": str(totals["false_literal_bytes"]),
        "correct_bytes": str(correct_bytes),
        "false_bytes": str(false_bytes),
        "net_bytes": str(correct_bytes - false_bytes),
        "coverage_ratio": f"{(correct_bytes / total_expected if total_expected else 0.0):.6f}",
        "false_ratio": f"{(false_bytes / total_expected if total_expected else 0.0):.6f}",
        "unselected_bytes": str(max(0, total_expected - correct_bytes - false_bytes)),
    }

    fixture_rows: list[dict[str, str]] = []
    for key, fixture_bytes in sorted(fixture_totals(operation_rows).items(), key=lambda item: int(item[0][0]) if item[0][0].isdigit() else 999999):
        values = by_fixture[key]
        correct = values["correct_bytes"]
        false = values["false_bytes"]
        fixture_rows.append(
            {
                "candidate": name,
                "rank": key[0],
                "pcx_name": key[1],
                "frontier_id": key[2],
                "fixture_bytes": str(fixture_bytes),
                "correct_bytes": str(correct),
                "false_bytes": str(false),
                "net_bytes": str(correct - false),
                "true_zero_bytes": str(values["true_zero_bytes"]),
                "false_zero_bytes": str(values["false_zero_bytes"]),
                "true_literal_bytes": str(values["true_literal_bytes"]),
                "false_literal_bytes": str(values["false_literal_bytes"]),
                "coverage_ratio": f"{(correct / fixture_bytes if fixture_bytes else 0.0):.6f}",
            }
        )
    return candidate, fixture_rows


def build_candidates(
    operation_rows: list[dict[str, str]],
    literal_rows: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    priorities = ["zero_first", "literal_first"]
    zero_rules = ["none", "len64", "length_u8", "len64_or_u8", "len64_and_u8", "u8_len32_64", "oracle_zero"]
    literal_rules = [
        "none",
        "oracle_token_plus3",
        "small_token",
        "small_nonzero_next2_clean",
        "small_not_backward",
        "small_not_backward_abs_delta_le512",
        "small_not_backward_nonzero_pre4_mod_clean",
    ]
    candidates: list[dict[str, str]] = []
    fixtures: list[dict[str, str]] = []
    for priority in priorities:
        for zero_rule in zero_rules:
            for literal_rule in literal_rules:
                candidate, by_fixture = score_candidate(priority, zero_rule, literal_rule, operation_rows, literal_rows)
                candidates.append(candidate)
                fixtures.extend(by_fixture)
    candidates.sort(
        key=lambda row: (
            int_value(row, "uses_oracle_filter"),
            -int_value(row, "net_bytes"),
            -int_value(row, "correct_bytes"),
            int_value(row, "false_bytes"),
            row.get("candidate", ""),
        )
    )
    return candidates, fixtures


def summary_row(operation_rows: list[dict[str, str]], candidates: list[dict[str, str]]) -> dict[str, str]:
    total_expected = sum(length(row) for row in operation_rows)
    fixture_count = len({fixture_key(row) for row in operation_rows})
    nonoracle = [row for row in candidates if row.get("uses_oracle_filter") != "1"]
    oracle = [row for row in candidates if row.get("uses_oracle_filter") == "1"]
    best_correct = max(nonoracle, key=lambda row: (int_value(row, "correct_bytes"), -int_value(row, "false_bytes")))
    best_net = max(nonoracle, key=lambda row: (int_value(row, "net_bytes"), int_value(row, "correct_bytes"), -int_value(row, "false_bytes")))
    low_false = [
        row
        for row in nonoracle
        if int_value(row, "false_bytes") <= 64 and int_value(row, "correct_bytes") > 0
    ]
    best_low_false = max(
        low_false,
        key=lambda row: (int_value(row, "correct_bytes"), -int_value(row, "false_bytes"), row.get("candidate", "")),
    )
    best_oracle = max(oracle, key=lambda row: (int_value(row, "correct_bytes"), -int_value(row, "false_bytes")))
    return {
        "scope": "total",
        "operation_rows": str(len(operation_rows)),
        "fixture_rows": str(fixture_count),
        "total_expected_bytes": str(total_expected),
        "candidate_rows": str(len(candidates)),
        "best_nonoracle_by_correct": best_correct.get("candidate", ""),
        "best_nonoracle_correct_bytes": best_correct.get("correct_bytes", "0"),
        "best_nonoracle_false_bytes": best_correct.get("false_bytes", "0"),
        "best_nonoracle_net_bytes": best_correct.get("net_bytes", "0"),
        "best_nonoracle_by_net": best_net.get("candidate", ""),
        "best_net_correct_bytes": best_net.get("correct_bytes", "0"),
        "best_net_false_bytes": best_net.get("false_bytes", "0"),
        "best_net_bytes": best_net.get("net_bytes", "0"),
        "best_low_false_candidate": best_low_false.get("candidate", ""),
        "best_low_false_correct_bytes": best_low_false.get("correct_bytes", "0"),
        "best_low_false_false_bytes": best_low_false.get("false_bytes", "0"),
        "best_oracle_candidate": best_oracle.get("candidate", ""),
        "best_oracle_correct_bytes": best_oracle.get("correct_bytes", "0"),
        "best_oracle_false_bytes": best_oracle.get("false_bytes", "0"),
        "issue_rows": str(sum(1 for row in operation_rows if row.get("issues"))),
    }


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 300) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    candidates: list[dict[str, str]],
    fixtures: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "candidates": candidates, "fixtures": fixtures}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("candidates.csv", output_dir / "candidates.csv"),
            ("by_fixture.csv", output_dir / "by_fixture.csv"),
        )
    )
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root {{
  color-scheme: dark;
  --bg: #101417;
  --panel: #171f22;
  --line: #31424a;
  --text: #edf5f4;
  --muted: #9dafb5;
  --accent: #77d3b1;
  --ok: #80df94;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  min-height: 100vh;
  background: var(--bg);
  color: var(--text);
  font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}}
.wrap {{ width: min(1680px, calc(100vw - 28px)); margin: 0 auto; }}
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
.panel {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; min-width: 1320px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Scores zero and literal rules as competing decoder decisions, including false-zero risk.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Best correct</div><div class="value ok">{html.escape(summary['best_nonoracle_correct_bytes'])}</div></div>
    <div class="stat"><div class="label">Best correct false</div><div class="value">{html.escape(summary['best_nonoracle_false_bytes'])}</div></div>
    <div class="stat"><div class="label">Best net</div><div class="value">{html.escape(summary['best_net_bytes'])}</div></div>
    <div class="stat"><div class="label">Best low-false</div><div class="value">{html.escape(summary['best_low_false_correct_bytes'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div></section>
  <section class="panel"><h2>Candidates</h2>{render_table(candidates, CANDIDATE_FIELDNAMES)}</section>
  <section class="panel"><h2>Fixture scores</h2>{render_table(fixtures, FIXTURE_FIELDNAMES)}</section>
</main>
<script>
const TEX_GAP_DECODER_RISK_ADJUSTED_PROBE = {data_json};
</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    operations_path: Path,
    literals_path: Path,
    *,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    operation_rows = read_csv(operations_path)
    literal_rows = enrich_literal_rows(read_csv(literals_path), operation_rows)
    candidates, fixtures = build_candidates(operation_rows, literal_rows)
    summary = summary_row(operation_rows, candidates)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "candidates.csv", CANDIDATE_FIELDNAMES, candidates)
    write_csv(output_dir / "by_fixture.csv", FIXTURE_FIELDNAMES, fixtures)
    (output_dir / "index.html").write_text(build_html(summary, candidates, fixtures, output_dir, title))
    return summary, candidates


def main() -> None:
    parser = argparse.ArgumentParser(description="Score .tex decoder skeleton candidates with false-positive risk.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--operations", type=Path, default=DEFAULT_OPERATIONS)
    parser.add_argument("--literals", type=Path, default=DEFAULT_LITERALS)
    parser.add_argument("--title", default="Lands of Lore II .tex Gap Decoder Risk-Adjusted Probe")
    args = parser.parse_args()

    summary, _candidates = write_report(args.output, args.operations, args.literals, title=args.title)
    print(f"Operation rows: {summary['operation_rows']}")
    print(
        "Best by correct: "
        f"{summary['best_nonoracle_by_correct']} "
        f"{summary['best_nonoracle_correct_bytes']}/{summary['best_nonoracle_false_bytes']}"
    )
    print(
        "Best by net: "
        f"{summary['best_nonoracle_by_net']} "
        f"{summary['best_net_correct_bytes']}/{summary['best_net_false_bytes']} "
        f"net={summary['best_net_bytes']}"
    )
    print(
        "Best low-false: "
        f"{summary['best_low_false_candidate']} "
        f"{summary['best_low_false_correct_bytes']}/{summary['best_low_false_false_bytes']}"
    )
    print(f"Issue rows: {summary['issue_rows']}")


if __name__ == "__main__":
    main()
