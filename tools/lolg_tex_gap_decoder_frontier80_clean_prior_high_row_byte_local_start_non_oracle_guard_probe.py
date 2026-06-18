#!/usr/bin/env python3
"""Validate non-oracle guard inputs for high-row byte-local start selectors."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Callable

from lolg_tex_gap_decoder_frontier80_clean_prior_high_row_byte_local_start_selector_probe import (
    OBSERVATION_FIELDNAMES,
    OPERATION_FIELDNAMES,
    build_observation_rows,
    build_observations,
    build_selector_table,
    feature_specs,
    guard_specs,
    read_csv,
    ratio,
    render_table,
)
from lolg_tex_gap_decoder_frontier80_clean_prior_high_row_byte_local_start_selector_probe import (
    apply_selector as apply_start_selector,
)
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_frontier80_clean_prior_high_row_byte_local_start_non_oracle_guard_probe")
DEFAULT_PAIRS = Path("output/tex_gap_decoder_frontier80_clean_prior_high_row_outlier_fallback_probe/pairs.csv")
DEFAULT_CANDIDATES = Path(
    "output/tex_gap_decoder_frontier80_clean_prior_high_row_outlier_fallback_probe/cluster_candidates.csv"
)
DEFAULT_OUTLIERS = Path(
    "output/tex_gap_decoder_frontier80_clean_prior_high_row_outlier_fallback_probe/outlier_alternatives.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "total_bytes",
    "outlier_bytes",
    "selector_candidate_rows",
    "best_support_only_selector",
    "best_support_only_resolved_outliers",
    "best_support_only_false_switch_bytes",
    "best_support_only_false_delta_bytes",
    "best_support_only_total_le2_bytes",
    "best_support_only_total_le2_ratio",
    "best_source_dependent_selector",
    "best_source_dependent_total_le2_bytes",
    "best_target_specific_selector",
    "best_target_specific_total_le2_bytes",
    "false_switch_rows",
    "false_delta_rows",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

GUARD_FIELDNAMES = [
    "selector_name",
    "input_class",
    "guard_name",
    "guard_availability",
    "feature_name",
    "feature_availability",
    "key_count",
    "target_outlier_rows",
    "resolved_outliers",
    "unresolved_outliers",
    "switched_bytes",
    "outlier_switch_bytes",
    "false_switch_bytes",
    "false_delta_bytes",
    "total_le2_bytes",
    "total_le2_ratio",
    "training_conflicts",
    "selector_table",
]


Observation = dict[str, object]
Feature = tuple[str, str, Callable[[Observation], str]]
Guard = tuple[str, str, Callable[[Observation], bool]]


SUPPORT_ONLY_FEATURES = {
    "constant_start",
    "byte_index",
    "selected_support_value",
    "byte_index_selected_support_value",
}
SOURCE_DEPENDENT_FEATURES = {
    "source_value",
    "selected_delta",
    "byte_index_source_value",
    "byte_index_selected_delta",
    "support_source_value",
}
TARGET_SPECIFIC_FEATURES = {
    "source_id_byte_index",
    "pair_id_byte_index",
}
SUPPORT_ONLY_GUARDS = {
    "all_bytes",
    "outlier_byte_index",
    "outlier_support_value",
}
SOURCE_DEPENDENT_GUARDS = {
    "selected_delta_abs_gt2",
}


def availability(name: str, *, features: bool) -> str:
    if features:
        if name in SUPPORT_ONLY_FEATURES:
            return "support_only"
        if name in SOURCE_DEPENDENT_FEATURES:
            return "source_dependent"
        if name in TARGET_SPECIFIC_FEATURES:
            return "target_specific"
    else:
        if name in SUPPORT_ONLY_GUARDS:
            return "support_only"
        if name in SOURCE_DEPENDENT_GUARDS:
            return "source_dependent"
    return "unknown"


def input_class(guard_availability: str, feature_availability: str) -> str:
    if guard_availability == "source_dependent" or feature_availability == "source_dependent":
        return "source_dependent"
    if feature_availability == "target_specific":
        return "target_specific"
    if guard_availability == "support_only" and feature_availability == "support_only":
        return "support_only"
    return "unknown"


def sort_selector_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    class_priority = {
        "support_only": 0,
        "source_dependent": 1,
        "target_specific": 2,
        "unknown": 3,
    }
    guard_priority = {
        "all_bytes": 0,
        "outlier_byte_index": 1,
        "outlier_support_value": 2,
        "selected_delta_abs_gt2": 3,
    }
    feature_priority = {
        "byte_index_selected_support_value": 0,
        "selected_support_value": 1,
        "byte_index": 2,
        "constant_start": 3,
        "source_value": 4,
        "byte_index_source_value": 5,
        "support_source_value": 6,
        "byte_index_selected_delta": 7,
        "selected_delta": 8,
        "source_id_byte_index": 9,
        "pair_id_byte_index": 10,
    }
    return sorted(
        rows,
        key=lambda row: (
            class_priority.get(row.get("input_class", ""), 9),
            -int_value(row, "resolved_outliers"),
            int_value(row, "false_delta_bytes"),
            int_value(row, "false_switch_bytes"),
            -int_value(row, "total_le2_bytes"),
            guard_priority.get(row.get("guard_name", ""), 9),
            feature_priority.get(row.get("feature_name", ""), 99),
            int_value(row, "key_count"),
            row.get("selector_name", ""),
        ),
    )


def best_for_class(rows: list[dict[str, str]], class_name: str) -> dict[str, str]:
    scoped = [row for row in rows if row.get("input_class", "") == class_name]
    return sort_selector_rows(scoped)[0] if scoped else {}


def build_guard_rows(observations: list[Observation]) -> tuple[list[dict[str, str]], dict[str, list[dict[str, str]]]]:
    outlier_observations = [row for row in observations if row["selected_outlier"]]
    outlier_positions = {int(row["byte_index"]) for row in outlier_observations}
    outlier_support_values = {int(row["selected_support_value"]) for row in outlier_observations}
    rows: list[dict[str, str]] = []
    operations_by_selector: dict[str, list[dict[str, str]]] = {}

    for guard_name, _guard_scope, guard in guard_specs(outlier_positions, outlier_support_values):
        guard_availability = availability(guard_name, features=False)
        for feature_name, _feature_scope, feature in feature_specs():
            feature_availability = availability(feature_name, features=True)
            table, conflicts, table_preview = build_selector_table(outlier_observations, feature)
            selector_name = f"{guard_name}/{feature_name}"
            result, operations = apply_start_selector(observations, selector_name, guard, feature, table)
            rows.append(
                {
                    "selector_name": selector_name,
                    "input_class": input_class(guard_availability, feature_availability),
                    "guard_name": guard_name,
                    "guard_availability": guard_availability,
                    "feature_name": feature_name,
                    "feature_availability": feature_availability,
                    "key_count": str(len(table)),
                    **result,
                    "training_conflicts": str(conflicts),
                    "selector_table": table_preview,
                }
            )
            operations_by_selector[selector_name] = operations
    return sort_selector_rows(rows), operations_by_selector


def build_summary(
    observations: list[Observation],
    guard_rows: list[dict[str, str]],
    operations: list[dict[str, str]],
    *,
    issue_count: int,
) -> dict[str, str]:
    total = len(observations)
    outliers = sum(1 for row in observations if row["selected_outlier"])
    support_only = best_for_class(guard_rows, "support_only")
    source_dependent = best_for_class(guard_rows, "source_dependent")
    target_specific = best_for_class(guard_rows, "target_specific")
    false_switches = [row for row in operations if row.get("false_switch") == "1"]
    false_delta = [
        row
        for row in false_switches
        if abs(int(row.get("chosen_delta", "0") or 0)) > 2
    ]
    support_ready = (
        support_only
        and int_value(support_only, "resolved_outliers") == outliers
        and int_value(support_only, "false_switch_bytes") == 0
        and int_value(support_only, "false_delta_bytes") == 0
        and int_value(support_only, "total_le2_bytes") == total
    )
    support_near = (
        support_only
        and int_value(support_only, "resolved_outliers") == outliers
        and int_value(support_only, "false_delta_bytes") > 0
    )
    if support_ready:
        verdict = "frontier80_prior_high_row_non_oracle_guard_ready"
        next_probe = "promote support-only byte-local start guard for high-row outliers"
    elif support_near:
        verdict = "frontier80_prior_high_row_non_oracle_guard_false_positive_split_needed"
        next_probe = "derive false-positive split for support-only byte-local start guard"
    else:
        verdict = "frontier80_prior_high_row_non_oracle_guard_weak"
        next_probe = "expand non-oracle guard features for byte-local high-row selector"
    return {
        "scope": "total",
        "total_bytes": str(total),
        "outlier_bytes": str(outliers),
        "selector_candidate_rows": str(len(guard_rows)),
        "best_support_only_selector": support_only.get("selector_name", ""),
        "best_support_only_resolved_outliers": support_only.get("resolved_outliers", "0"),
        "best_support_only_false_switch_bytes": support_only.get("false_switch_bytes", "0"),
        "best_support_only_false_delta_bytes": support_only.get("false_delta_bytes", "0"),
        "best_support_only_total_le2_bytes": support_only.get("total_le2_bytes", "0"),
        "best_support_only_total_le2_ratio": support_only.get("total_le2_ratio", "0.000000"),
        "best_source_dependent_selector": source_dependent.get("selector_name", ""),
        "best_source_dependent_total_le2_bytes": source_dependent.get("total_le2_bytes", "0"),
        "best_target_specific_selector": target_specific.get("selector_name", ""),
        "best_target_specific_total_le2_bytes": target_specific.get("total_le2_bytes", "0"),
        "false_switch_rows": str(len(false_switches)),
        "false_delta_rows": str(len(false_delta)),
        "issue_rows": str(issue_count),
        "review_verdict": verdict,
        "next_probe": next_probe,
    }


def build_html(
    summary: dict[str, str],
    guard_rows: list[dict[str, str]],
    operation_rows: list[dict[str, str]],
    observation_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "guards": guard_rows,
        "operations": operation_rows,
        "observations": observation_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("guard_candidates.csv", output_dir / "guard_candidates.csv"),
            ("guard_operations.csv", output_dir / "guard_operations.csv"),
            ("byte_observations.csv", output_dir / "byte_observations.csv"),
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
    <div class="sub">Separates support-only, source-dependent, and target-specific guard inputs for the byte-local high-row selector.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Support-only selector</div><div class="value">{html.escape(summary['best_support_only_selector'])}</div></div>
    <div class="stat"><div class="label">Resolved outliers</div><div class="value">{html.escape(summary['best_support_only_resolved_outliers'])}/{html.escape(summary['outlier_bytes'])}</div></div>
    <div class="stat"><div class="label">False delta</div><div class="value">{html.escape(summary['best_support_only_false_delta_bytes'])}</div></div>
    <div class="stat"><div class="label">Support-only &lt;=2</div><div class="value">{html.escape(summary['best_support_only_total_le2_bytes'])}/{html.escape(summary['total_bytes'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div><div class="sub">{html.escape(summary['review_verdict'])}: {html.escape(summary['next_probe'])}</div></section>
  <section class="panel"><h2>Guard candidates</h2>{render_table(guard_rows, GUARD_FIELDNAMES)}</section>
  <section class="panel"><h2>Guard operations</h2>{render_table(operation_rows, OPERATION_FIELDNAMES)}</section>
  <section class="panel"><h2>Byte observations</h2>{render_table(observation_rows, OBSERVATION_FIELDNAMES)}</section>
</main>
<script type="application/json" id="non-oracle-guard-data">{data_json}</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    pairs_path: Path,
    candidates_path: Path,
    outliers_path: Path,
    *,
    title: str,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    observations, _outliers_by_key = build_observations(
        read_csv(pairs_path),
        read_csv(candidates_path),
        read_csv(outliers_path),
        issues,
    )
    guard_rows, operations_by_selector = build_guard_rows(observations)
    support_only = best_for_class(guard_rows, "support_only")
    selected_operations = operations_by_selector.get(support_only.get("selector_name", ""), [])
    operation_rows = [
        row
        for row in selected_operations
        if row.get("false_switch") == "1" or row.get("selected_outlier") == "1"
    ]
    summary = build_summary(observations, guard_rows, selected_operations, issue_count=len(issues))
    observation_rows = build_observation_rows(observations)

    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "guard_candidates.csv", GUARD_FIELDNAMES, guard_rows)
    write_csv(output_dir / "guard_operations.csv", OPERATION_FIELDNAMES, operation_rows)
    write_csv(output_dir / "byte_observations.csv", OBSERVATION_FIELDNAMES, observation_rows)
    (output_dir / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""))
    (output_dir / "index.html").write_text(
        build_html(summary, guard_rows, operation_rows, observation_rows, output_dir, title)
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate non-oracle guard inputs for high-row byte-local starts.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--pairs", type=Path, default=DEFAULT_PAIRS)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--outliers", type=Path, default=DEFAULT_OUTLIERS)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Prior High Row Byte Local Start Non Oracle Guard Probe",
    )
    args = parser.parse_args()

    summary = write_report(
        args.output,
        args.pairs,
        args.candidates,
        args.outliers,
        title=args.title,
    )
    print(f"Support-only selector: {summary['best_support_only_selector']}")
    print(f"Resolved outliers: {summary['best_support_only_resolved_outliers']}/{summary['outlier_bytes']}")
    print(f"False delta rows: {summary['best_support_only_false_delta_bytes']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
