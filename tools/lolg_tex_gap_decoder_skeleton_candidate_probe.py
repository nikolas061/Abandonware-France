#!/usr/bin/env python3
"""Score candidate .tex decoder skeleton tiers from zero/literal evidence."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import defaultdict
from pathlib import Path

from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_skeleton_candidate_probe")
DEFAULT_OPERATIONS = Path("output/tex_gap_segmentation_control_correlation_probe/operations.csv")
DEFAULT_LITERALS = Path("output/tex_gap_literal_token_probe/literals.csv")
DEFAULT_ZERO_RUNS = Path("output/tex_gap_zero_run_alignment_probe/zero_runs.csv")

REPEATED_FALSE_PRE2 = {"020a", "0703", "0704", "0002", "2f08"}
REPEATED_FALSE_PRE4 = {"6edc020a", "5d5c0703", "6bfc0704", "17542f08"}
REPEATED_FALSE_NEXT2 = {"5a5c", "5d6d", "aa6c", "7b6a"}
REPEATED_FALSE_MOD64 = {5, 28, 34}

SUMMARY_FIELDNAMES = [
    "scope",
    "operation_rows",
    "fixture_rows",
    "total_expected_bytes",
    "skeleton_covered_bytes",
    "skeleton_gap_bytes",
    "candidate_rows",
    "best_nonoracle_candidate",
    "best_nonoracle_correct_bytes",
    "best_nonoracle_false_bytes",
    "best_nonoracle_coverage_ratio",
    "best_oracle_candidate",
    "best_oracle_correct_bytes",
    "best_oracle_false_bytes",
    "best_oracle_coverage_ratio",
    "issue_rows",
]

CANDIDATE_FIELDNAMES = [
    "candidate",
    "zero_rule",
    "literal_rule",
    "uses_oracle_filter",
    "total_expected_bytes",
    "selected_zero_ops",
    "selected_zero_bytes",
    "selected_literal_ops",
    "true_literal_ops",
    "false_literal_ops",
    "true_literal_bytes",
    "false_literal_bytes",
    "correct_bytes",
    "false_bytes",
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
    "selected_zero_bytes",
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
        enriched["pre2_hex"] = operation.get("pre2_hex", "")
        enriched["pre4_hex"] = operation.get("pre4_hex", "")
        enriched["next2_hex"] = operation.get("next2_hex", "")
        enriched["expected_mod64"] = operation.get("expected_mod64", "")
        rows.append(enriched)
    return rows


def literal_token(row: dict[str, str]) -> int:
    return int_value(row, "token_value") if row.get("token_value") else -1


def literal_delta(row: dict[str, str]) -> int:
    return int_value(row, "source_delta_from_prev_literal_end") if row.get("source_delta_from_prev_literal_end") else 0


def literal_expected_mod64(row: dict[str, str]) -> int:
    return int_value(row, "expected_mod64") if row.get("expected_mod64") else -1


def select_literal(rule: str, row: dict[str, str]) -> bool:
    token = literal_token(row)
    direction = row.get("source_direction", "")
    delta = abs(literal_delta(row))
    if rule == "none":
        return False
    if rule == "oracle_token_plus3":
        return row.get("token_plus3_match") == "1"
    if rule == "small_token":
        return 0 <= token <= 13
    if rule == "small_nonzero_next2_clean":
        return 1 <= token <= 13 and row.get("next2_hex") not in REPEATED_FALSE_NEXT2
    if rule == "small_nonzero_pre4_clean":
        return 1 <= token <= 13 and row.get("pre4_hex") not in REPEATED_FALSE_PRE4
    if rule == "small_nonzero_pre2_clean":
        return 1 <= token <= 13 and row.get("pre2_hex") not in REPEATED_FALSE_PRE2
    if rule == "small_not_backward":
        return 0 <= token <= 13 and direction != "backward"
    if rule == "small_not_backward_abs_delta_le512":
        return 0 <= token <= 13 and direction != "backward" and delta <= 512
    if rule == "small_not_backward_nonzero_pre4_mod_clean":
        return (
            1 <= token <= 13
            and direction != "backward"
            and row.get("pre4_hex") not in REPEATED_FALSE_PRE4
            and literal_expected_mod64(row) not in REPEATED_FALSE_MOD64
        )
    raise ValueError(f"unknown literal rule: {rule}")


def select_zero(rule: str, row: dict[str, str]) -> bool:
    if rule == "none":
        return False
    if rule == "len64":
        return int_value(row, "length") == 64
    if rule == "length_u8":
        return bool(row.get("length_u8_hit_offsets"))
    if rule == "len64_or_u8":
        return int_value(row, "length") == 64 or bool(row.get("length_u8_hit_offsets"))
    if rule == "all_zero_oracle":
        return True
    raise ValueError(f"unknown zero rule: {rule}")


def uses_oracle_filter(zero_rule: str, literal_rule: str) -> bool:
    return zero_rule == "all_zero_oracle" or literal_rule == "oracle_token_plus3"


def candidate_name(zero_rule: str, literal_rule: str) -> str:
    return f"zero={zero_rule}|literal={literal_rule}"


def fixture_totals(operation_rows: list[dict[str, str]]) -> dict[tuple[str, str, str], int]:
    totals: dict[tuple[str, str, str], int] = defaultdict(int)
    for row in operation_rows:
        totals[fixture_key(row)] += int_value(row, "length")
    return totals


def score_candidate(
    zero_rule: str,
    literal_rule: str,
    operation_rows: list[dict[str, str]],
    literal_rows: list[dict[str, str]],
    zero_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]]]:
    total_expected = sum(int_value(row, "length") for row in operation_rows)
    selected_zero = [row for row in zero_rows if select_zero(zero_rule, row)]
    selected_literal = [row for row in literal_rows if select_literal(literal_rule, row)]
    true_literal = [row for row in selected_literal if row.get("token_plus3_match") == "1"]
    false_literal = [row for row in selected_literal if row.get("token_plus3_match") != "1"]
    zero_bytes = sum(int_value(row, "length") for row in selected_zero)
    true_literal_bytes = sum(int_value(row, "length") for row in true_literal)
    false_literal_bytes = sum(int_value(row, "length") for row in false_literal)
    correct_bytes = zero_bytes + true_literal_bytes
    name = candidate_name(zero_rule, literal_rule)
    candidate = {
        "candidate": name,
        "zero_rule": zero_rule,
        "literal_rule": literal_rule,
        "uses_oracle_filter": "1" if uses_oracle_filter(zero_rule, literal_rule) else "0",
        "total_expected_bytes": str(total_expected),
        "selected_zero_ops": str(len(selected_zero)),
        "selected_zero_bytes": str(zero_bytes),
        "selected_literal_ops": str(len(selected_literal)),
        "true_literal_ops": str(len(true_literal)),
        "false_literal_ops": str(len(false_literal)),
        "true_literal_bytes": str(true_literal_bytes),
        "false_literal_bytes": str(false_literal_bytes),
        "correct_bytes": str(correct_bytes),
        "false_bytes": str(false_literal_bytes),
        "coverage_ratio": f"{(correct_bytes / total_expected if total_expected else 0.0):.6f}",
        "false_ratio": f"{(false_literal_bytes / total_expected if total_expected else 0.0):.6f}",
        "unselected_bytes": str(max(0, total_expected - correct_bytes - false_literal_bytes)),
    }

    totals = fixture_totals(operation_rows)
    by_fixture: dict[tuple[str, str, str], dict[str, int]] = defaultdict(
        lambda: {
            "correct_bytes": 0,
            "false_bytes": 0,
            "selected_zero_bytes": 0,
            "true_literal_bytes": 0,
            "false_literal_bytes": 0,
        }
    )
    for row in selected_zero:
        key = fixture_key(row)
        length = int_value(row, "length")
        by_fixture[key]["correct_bytes"] += length
        by_fixture[key]["selected_zero_bytes"] += length
    for row in true_literal:
        key = fixture_key(row)
        length = int_value(row, "length")
        by_fixture[key]["correct_bytes"] += length
        by_fixture[key]["true_literal_bytes"] += length
    for row in false_literal:
        key = fixture_key(row)
        length = int_value(row, "length")
        by_fixture[key]["false_bytes"] += length
        by_fixture[key]["false_literal_bytes"] += length

    fixture_rows = []
    for key, fixture_bytes in sorted(totals.items(), key=lambda item: int(item[0][0]) if item[0][0].isdigit() else 999999):
        values = by_fixture[key]
        fixture_rows.append(
            {
                "candidate": name,
                "rank": key[0],
                "pcx_name": key[1],
                "frontier_id": key[2],
                "fixture_bytes": str(fixture_bytes),
                "correct_bytes": str(values["correct_bytes"]),
                "false_bytes": str(values["false_bytes"]),
                "selected_zero_bytes": str(values["selected_zero_bytes"]),
                "true_literal_bytes": str(values["true_literal_bytes"]),
                "false_literal_bytes": str(values["false_literal_bytes"]),
                "coverage_ratio": f"{(values['correct_bytes'] / fixture_bytes if fixture_bytes else 0.0):.6f}",
            }
        )
    return candidate, fixture_rows


def build_candidates(
    operation_rows: list[dict[str, str]],
    literal_rows: list[dict[str, str]],
    zero_rows: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    zero_rules = ["none", "len64", "length_u8", "len64_or_u8", "all_zero_oracle"]
    literal_rules = [
        "none",
        "oracle_token_plus3",
        "small_token",
        "small_nonzero_next2_clean",
        "small_nonzero_pre4_clean",
        "small_nonzero_pre2_clean",
        "small_not_backward",
        "small_not_backward_abs_delta_le512",
        "small_not_backward_nonzero_pre4_mod_clean",
    ]
    candidates: list[dict[str, str]] = []
    fixtures: list[dict[str, str]] = []
    for zero_rule in zero_rules:
        for literal_rule in literal_rules:
            candidate, by_fixture = score_candidate(zero_rule, literal_rule, operation_rows, literal_rows, zero_rows)
            candidates.append(candidate)
            fixtures.extend(by_fixture)
    candidates.sort(
        key=lambda row: (
            int_value(row, "uses_oracle_filter"),
            -int_value(row, "correct_bytes"),
            int_value(row, "false_bytes"),
            row.get("candidate", ""),
        )
    )
    return candidates, fixtures


def summary_row(
    operation_rows: list[dict[str, str]],
    candidates: list[dict[str, str]],
) -> dict[str, str]:
    total_expected = sum(int_value(row, "length") for row in operation_rows)
    skeleton_covered = sum(
        int_value(row, "length") for row in operation_rows if row.get("op_kind") in {"zero", "literal"}
    )
    fixture_count = len({fixture_key(row) for row in operation_rows})
    nonoracle = [row for row in candidates if row.get("uses_oracle_filter") != "1"]
    oracle = [row for row in candidates if row.get("uses_oracle_filter") == "1"]
    best_nonoracle = max(nonoracle, key=lambda row: (int_value(row, "correct_bytes"), -int_value(row, "false_bytes")))
    best_oracle = max(oracle, key=lambda row: (int_value(row, "correct_bytes"), -int_value(row, "false_bytes")))
    return {
        "scope": "total",
        "operation_rows": str(len(operation_rows)),
        "fixture_rows": str(fixture_count),
        "total_expected_bytes": str(total_expected),
        "skeleton_covered_bytes": str(skeleton_covered),
        "skeleton_gap_bytes": str(total_expected - skeleton_covered),
        "candidate_rows": str(len(candidates)),
        "best_nonoracle_candidate": best_nonoracle.get("candidate", ""),
        "best_nonoracle_correct_bytes": best_nonoracle.get("correct_bytes", "0"),
        "best_nonoracle_false_bytes": best_nonoracle.get("false_bytes", "0"),
        "best_nonoracle_coverage_ratio": best_nonoracle.get("coverage_ratio", "0.000000"),
        "best_oracle_candidate": best_oracle.get("candidate", ""),
        "best_oracle_correct_bytes": best_oracle.get("correct_bytes", "0"),
        "best_oracle_false_bytes": best_oracle.get("false_bytes", "0"),
        "best_oracle_coverage_ratio": best_oracle.get("coverage_ratio", "0.000000"),
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
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; }}
.stat, .panel {{ border: 1px solid var(--line); border-radius: 8px; background: var(--panel); padding: 10px; }}
.label, .muted {{ color: var(--muted); }}
.value {{ font-size: 22px; font-weight: 760; line-height: 1.05; margin-top: 4px; }}
.ok {{ color: var(--ok); }}
.panel {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; min-width: 1180px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Scores decoder-skeleton tiers by combining literal token classifiers with zero-run evidence.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Total fixture bytes</div><div class="value">{html.escape(summary['total_expected_bytes'])}</div></div>
    <div class="stat"><div class="label">Skeleton covered</div><div class="value ok">{html.escape(summary['skeleton_covered_bytes'])}</div></div>
    <div class="stat"><div class="label">Best non-oracle bytes</div><div class="value">{html.escape(summary['best_nonoracle_correct_bytes'])}</div></div>
    <div class="stat"><div class="label">Best oracle bytes</div><div class="value">{html.escape(summary['best_oracle_correct_bytes'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div></section>
  <section class="panel"><h2>Candidates</h2>{render_table(candidates, CANDIDATE_FIELDNAMES)}</section>
  <section class="panel"><h2>Fixture scores</h2>{render_table(fixtures, FIXTURE_FIELDNAMES)}</section>
</main>
<script>
const TEX_GAP_DECODER_SKELETON_CANDIDATE_PROBE = {data_json};
</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    operations_path: Path,
    literals_path: Path,
    zero_runs_path: Path,
    *,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    operation_rows = read_csv(operations_path)
    literal_rows = enrich_literal_rows(read_csv(literals_path), operation_rows)
    zero_rows = read_csv(zero_runs_path)
    candidates, fixtures = build_candidates(operation_rows, literal_rows, zero_rows)
    summary = summary_row(operation_rows, candidates)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "candidates.csv", CANDIDATE_FIELDNAMES, candidates)
    write_csv(output_dir / "by_fixture.csv", FIXTURE_FIELDNAMES, fixtures)
    (output_dir / "index.html").write_text(build_html(summary, candidates, fixtures, output_dir, title))
    return summary, candidates


def main() -> None:
    parser = argparse.ArgumentParser(description="Score .tex decoder skeleton candidate tiers.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--operations", type=Path, default=DEFAULT_OPERATIONS)
    parser.add_argument("--literals", type=Path, default=DEFAULT_LITERALS)
    parser.add_argument("--zero-runs", type=Path, default=DEFAULT_ZERO_RUNS)
    parser.add_argument("--title", default="Lands of Lore II .tex Gap Decoder Skeleton Candidate Probe")
    args = parser.parse_args()

    summary, _candidates = write_report(
        args.output,
        args.operations,
        args.literals,
        args.zero_runs,
        title=args.title,
    )
    print(f"Operation rows: {summary['operation_rows']}")
    print(f"Total expected bytes: {summary['total_expected_bytes']}")
    print(f"Skeleton covered bytes: {summary['skeleton_covered_bytes']}")
    print(
        "Best non-oracle: "
        f"{summary['best_nonoracle_candidate']} "
        f"{summary['best_nonoracle_correct_bytes']} bytes "
        f"false={summary['best_nonoracle_false_bytes']}"
    )
    print(
        "Best oracle: "
        f"{summary['best_oracle_candidate']} "
        f"{summary['best_oracle_correct_bytes']} bytes "
        f"false={summary['best_oracle_false_bytes']}"
    )
    print(f"Issue rows: {summary['issue_rows']}")


if __name__ == "__main__":
    main()
