#!/usr/bin/env python3
"""Probe false-positive splits for the support-only high-row start guard."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import defaultdict
from pathlib import Path
from typing import Callable

from lolg_tex_gap_decoder_frontier80_clean_prior_high_row_byte_local_start_selector_probe import ratio
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_frontier80_clean_prior_high_row_byte_local_start_false_positive_split_probe")
DEFAULT_OPERATIONS = Path(
    "output/tex_gap_decoder_frontier80_clean_prior_high_row_byte_local_start_non_oracle_guard_probe/guard_operations.csv"
)
DEFAULT_OBSERVATIONS = Path(
    "output/tex_gap_decoder_frontier80_clean_prior_high_row_byte_local_start_non_oracle_guard_probe/byte_observations.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "switch_rows",
    "target_switch_rows",
    "false_switch_rows",
    "false_delta_rows",
    "best_support_only_split",
    "best_support_only_kept_target",
    "best_support_only_kept_false",
    "best_support_only_kept_false_delta",
    "best_support_only_dropped_target",
    "support_only_false_free_splits",
    "ambiguous_support_only_groups",
    "best_source_dependent_split",
    "best_source_dependent_kept_target",
    "best_source_dependent_kept_false",
    "best_target_specific_split",
    "best_target_specific_kept_target",
    "best_target_specific_kept_false",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

SPLIT_FIELDNAMES = [
    "split_name",
    "input_class",
    "feature_name",
    "key_count",
    "target_rows",
    "false_rows",
    "false_delta_rows",
    "kept_target",
    "dropped_target",
    "kept_false",
    "dropped_false",
    "kept_false_delta",
    "dropped_false_delta",
    "kept_rows",
    "kept_ratio",
    "false_free",
    "keep_table",
]

SWITCH_FIELDNAMES = [
    "pair_id",
    "source_id",
    "byte_index",
    "selector_key",
    "selected_start",
    "selected_support_value_hex",
    "source_value_hex",
    "selected_delta",
    "chosen_start",
    "chosen_support_value_hex",
    "chosen_delta",
    "selected_outlier",
    "false_switch",
    "false_delta",
    "support_context_r1",
    "support_context_r2",
    "support_context_r4",
]

AMBIGUOUS_FIELDNAMES = [
    "feature_name",
    "feature_value",
    "target_rows",
    "false_rows",
    "false_delta_rows",
    "pairs",
]


SwitchRow = dict[str, str]
Feature = tuple[str, str, Callable[[SwitchRow], str]]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def is_false_delta(row: dict[str, str]) -> bool:
    return row.get("false_switch") == "1" and abs(int_value(row, "chosen_delta")) > 2


def support_context(
    support_by_pair: dict[str, dict[int, str]],
    pair_id: str,
    byte_index: int,
    radius: int,
) -> str:
    values = support_by_pair.get(pair_id, {})
    return ";".join(values.get(index, "xx") for index in range(byte_index - radius, byte_index + radius + 1))


def build_switch_rows(operation_rows: list[dict[str, str]], observation_rows: list[dict[str, str]]) -> list[SwitchRow]:
    support_by_pair: dict[str, dict[int, str]] = defaultdict(dict)
    for row in observation_rows:
        support_by_pair[row.get("pair_id", "")][int_value(row, "byte_index")] = row.get("selected_support_value_hex", "")

    rows: list[SwitchRow] = []
    for operation in operation_rows:
        pair_id = operation.get("pair_id", "")
        byte_index = int_value(operation, "byte_index")
        rows.append(
            {
                "pair_id": pair_id,
                "source_id": operation.get("source_id", ""),
                "byte_index": operation.get("byte_index", ""),
                "selector_key": operation.get("selector_key", ""),
                "selected_start": operation.get("selected_start", ""),
                "selected_support_value_hex": operation.get("selected_support_value_hex", ""),
                "source_value_hex": operation.get("source_value_hex", ""),
                "selected_delta": operation.get("selected_delta", ""),
                "chosen_start": operation.get("chosen_start", ""),
                "chosen_support_value_hex": operation.get("chosen_support_value_hex", ""),
                "chosen_delta": operation.get("chosen_delta", ""),
                "selected_outlier": operation.get("selected_outlier", ""),
                "false_switch": operation.get("false_switch", ""),
                "false_delta": "1" if is_false_delta(operation) else "0",
                "support_context_r1": support_context(support_by_pair, pair_id, byte_index, 1),
                "support_context_r2": support_context(support_by_pair, pair_id, byte_index, 2),
                "support_context_r4": support_context(support_by_pair, pair_id, byte_index, 4),
            }
        )
    return rows


def feature_specs() -> list[Feature]:
    return [
        ("support_only", "selector_key", lambda row: row.get("selector_key", "")),
        ("support_only", "byte_index", lambda row: row.get("byte_index", "")),
        ("support_only", "selected_support_value", lambda row: row.get("selected_support_value_hex", "")),
        ("support_only", "selected_start", lambda row: row.get("selected_start", "")),
        ("support_only", "chosen_start", lambda row: row.get("chosen_start", "")),
        (
            "support_only",
            "selected_start_selector_key",
            lambda row: f"{row.get('selected_start', '')}|{row.get('selector_key', '')}",
        ),
        ("support_only", "support_context_r1", lambda row: row.get("support_context_r1", "")),
        ("support_only", "support_context_r2", lambda row: row.get("support_context_r2", "")),
        ("support_only", "support_context_r4", lambda row: row.get("support_context_r4", "")),
        ("source_dependent", "source_value", lambda row: row.get("source_value_hex", "")),
        ("source_dependent", "selected_delta", lambda row: row.get("selected_delta", "")),
        (
            "source_dependent",
            "selected_delta_abs_gt2",
            lambda row: "1" if abs(int_value(row, "selected_delta")) > 2 else "0",
        ),
        ("source_dependent", "chosen_delta", lambda row: row.get("chosen_delta", "")),
        (
            "source_dependent",
            "selector_key_source_value",
            lambda row: f"{row.get('selector_key', '')}|v={row.get('source_value_hex', '')}",
        ),
        ("target_specific", "source_id", lambda row: row.get("source_id", "")),
        (
            "target_specific",
            "source_id_byte_index",
            lambda row: f"{row.get('source_id', '')}|p{row.get('byte_index', '')}",
        ),
        (
            "target_specific",
            "pair_id_byte_index",
            lambda row: f"{row.get('pair_id', '')}|p{row.get('byte_index', '')}",
        ),
    ]


def build_split_rows(switch_rows: list[SwitchRow]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    target_rows = [row for row in switch_rows if row.get("selected_outlier") == "1"]
    false_rows = [row for row in switch_rows if row.get("false_switch") == "1"]
    false_delta_rows = [row for row in switch_rows if row.get("false_delta") == "1"]
    split_rows: list[dict[str, str]] = []
    ambiguous_rows: list[dict[str, str]] = []

    for input_class, feature_name, feature in feature_specs():
        keep_values = sorted({feature(row) for row in target_rows})
        keep_set = set(keep_values)
        kept = [row for row in switch_rows if feature(row) in keep_set]
        kept_target = [row for row in kept if row.get("selected_outlier") == "1"]
        kept_false = [row for row in kept if row.get("false_switch") == "1"]
        kept_false_delta = [row for row in kept if row.get("false_delta") == "1"]
        split_rows.append(
            {
                "split_name": f"{input_class}/{feature_name}",
                "input_class": input_class,
                "feature_name": feature_name,
                "key_count": str(len(keep_values)),
                "target_rows": str(len(target_rows)),
                "false_rows": str(len(false_rows)),
                "false_delta_rows": str(len(false_delta_rows)),
                "kept_target": str(len(kept_target)),
                "dropped_target": str(len(target_rows) - len(kept_target)),
                "kept_false": str(len(kept_false)),
                "dropped_false": str(len(false_rows) - len(kept_false)),
                "kept_false_delta": str(len(kept_false_delta)),
                "dropped_false_delta": str(len(false_delta_rows) - len(kept_false_delta)),
                "kept_rows": str(len(kept)),
                "kept_ratio": ratio(len(kept), len(switch_rows)),
                "false_free": "1" if len(kept_target) == len(target_rows) and not kept_false else "0",
                "keep_table": ";".join(keep_values),
            }
        )

        if input_class == "support_only":
            grouped: dict[str, list[SwitchRow]] = defaultdict(list)
            for row in switch_rows:
                grouped[feature(row)].append(row)
            for value, group in grouped.items():
                group_targets = [row for row in group if row.get("selected_outlier") == "1"]
                group_false = [row for row in group if row.get("false_switch") == "1"]
                group_false_delta = [row for row in group if row.get("false_delta") == "1"]
                if group_targets and group_false:
                    ambiguous_rows.append(
                        {
                            "feature_name": feature_name,
                            "feature_value": value,
                            "target_rows": str(len(group_targets)),
                            "false_rows": str(len(group_false)),
                            "false_delta_rows": str(len(group_false_delta)),
                            "pairs": ";".join(
                                f"{row.get('pair_id', '')}:p{row.get('byte_index', '')}" for row in group
                            ),
                        }
                    )

    split_rows.sort(
        key=lambda row: (
            row.get("input_class", ""),
            -int_value(row, "kept_target"),
            int_value(row, "kept_false_delta"),
            int_value(row, "kept_false"),
            int_value(row, "key_count"),
            row.get("feature_name", ""),
        )
    )
    ambiguous_rows.sort(key=lambda row: (row.get("feature_name", ""), row.get("feature_value", "")))
    return split_rows, ambiguous_rows


def best_for_class(split_rows: list[dict[str, str]], class_name: str) -> dict[str, str]:
    scoped = [row for row in split_rows if row.get("input_class") == class_name]
    if not scoped:
        return {}
    return sorted(
        scoped,
        key=lambda row: (
            -int_value(row, "kept_target"),
            int_value(row, "kept_false_delta"),
            int_value(row, "kept_false"),
            int_value(row, "dropped_target"),
            int_value(row, "key_count"),
            row.get("feature_name", ""),
        ),
    )[0]


def build_summary(
    switch_rows: list[SwitchRow],
    split_rows: list[dict[str, str]],
    ambiguous_rows: list[dict[str, str]],
    *,
    issue_count: int,
) -> dict[str, str]:
    target_rows = [row for row in switch_rows if row.get("selected_outlier") == "1"]
    false_rows = [row for row in switch_rows if row.get("false_switch") == "1"]
    false_delta_rows = [row for row in switch_rows if row.get("false_delta") == "1"]
    support = best_for_class(split_rows, "support_only")
    source = best_for_class(split_rows, "source_dependent")
    target = best_for_class(split_rows, "target_specific")
    support_false_free = [
        row
        for row in split_rows
        if row.get("input_class") == "support_only" and row.get("false_free") == "1"
    ]
    if support_false_free:
        verdict = "frontier80_prior_high_row_support_only_split_ready"
        next_probe = "promote support-only split for byte-local high-row start guard"
    elif source and int_value(source, "kept_target") == len(target_rows) and int_value(source, "kept_false") == 0:
        verdict = "frontier80_prior_high_row_support_only_split_blocked_source_split_ready"
        next_probe = "validate source-dependent false-positive split for byte-local high-row guard"
    else:
        verdict = "frontier80_prior_high_row_false_positive_split_weak"
        next_probe = "expand false-positive split context for byte-local high-row guard"
    return {
        "scope": "total",
        "switch_rows": str(len(switch_rows)),
        "target_switch_rows": str(len(target_rows)),
        "false_switch_rows": str(len(false_rows)),
        "false_delta_rows": str(len(false_delta_rows)),
        "best_support_only_split": support.get("split_name", ""),
        "best_support_only_kept_target": support.get("kept_target", "0"),
        "best_support_only_kept_false": support.get("kept_false", "0"),
        "best_support_only_kept_false_delta": support.get("kept_false_delta", "0"),
        "best_support_only_dropped_target": support.get("dropped_target", "0"),
        "support_only_false_free_splits": str(len(support_false_free)),
        "ambiguous_support_only_groups": str(len(ambiguous_rows)),
        "best_source_dependent_split": source.get("split_name", ""),
        "best_source_dependent_kept_target": source.get("kept_target", "0"),
        "best_source_dependent_kept_false": source.get("kept_false", "0"),
        "best_target_specific_split": target.get("split_name", ""),
        "best_target_specific_kept_target": target.get("kept_target", "0"),
        "best_target_specific_kept_false": target.get("kept_false", "0"),
        "issue_rows": str(issue_count),
        "review_verdict": verdict,
        "next_probe": next_probe,
    }


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 240) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    split_rows: list[dict[str, str]],
    switch_rows: list[SwitchRow],
    ambiguous_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "splits": split_rows,
        "switches": switch_rows,
        "ambiguous": ambiguous_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("split_candidates.csv", output_dir / "split_candidates.csv"),
            ("switch_rows.csv", output_dir / "switch_rows.csv"),
            ("ambiguous_support_contexts.csv", output_dir / "ambiguous_support_contexts.csv"),
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
    <div class="sub">Tests whether support-only context can split the byte-local start false positives.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Support-only split</div><div class="value">{html.escape(summary['best_support_only_split'])}</div></div>
    <div class="stat"><div class="label">Kept target</div><div class="value">{html.escape(summary['best_support_only_kept_target'])}/{html.escape(summary['target_switch_rows'])}</div></div>
    <div class="stat"><div class="label">Kept false</div><div class="value">{html.escape(summary['best_support_only_kept_false'])}</div></div>
    <div class="stat"><div class="label">Ambiguous groups</div><div class="value">{html.escape(summary['ambiguous_support_only_groups'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div><div class="sub">{html.escape(summary['review_verdict'])}: {html.escape(summary['next_probe'])}</div></section>
  <section class="panel"><h2>Split candidates</h2>{render_table(split_rows, SPLIT_FIELDNAMES)}</section>
  <section class="panel"><h2>Switch rows</h2>{render_table(switch_rows, SWITCH_FIELDNAMES)}</section>
  <section class="panel"><h2>Ambiguous support contexts</h2>{render_table(ambiguous_rows, AMBIGUOUS_FIELDNAMES)}</section>
</main>
<script type="application/json" id="false-positive-split-data">{data_json}</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    operations_path: Path,
    observations_path: Path,
    *,
    title: str,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    switch_rows = build_switch_rows(read_csv(operations_path), read_csv(observations_path))
    if not switch_rows:
        issues.append("missing_switch_rows")
    split_rows, ambiguous_rows = build_split_rows(switch_rows)
    summary = build_summary(switch_rows, split_rows, ambiguous_rows, issue_count=len(issues))

    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "split_candidates.csv", SPLIT_FIELDNAMES, split_rows)
    write_csv(output_dir / "switch_rows.csv", SWITCH_FIELDNAMES, switch_rows)
    write_csv(output_dir / "ambiguous_support_contexts.csv", AMBIGUOUS_FIELDNAMES, ambiguous_rows)
    (output_dir / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""))
    (output_dir / "index.html").write_text(
        build_html(summary, split_rows, switch_rows, ambiguous_rows, output_dir, title)
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe false-positive splits for high-row byte-local start guards.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--operations", type=Path, default=DEFAULT_OPERATIONS)
    parser.add_argument("--observations", type=Path, default=DEFAULT_OBSERVATIONS)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Prior High Row Byte Local Start False Positive Split Probe",
    )
    args = parser.parse_args()

    summary = write_report(args.output, args.operations, args.observations, title=args.title)
    print(f"Support-only split: {summary['best_support_only_split']}")
    print(f"Support-only false-free splits: {summary['support_only_false_free_splits']}")
    print(f"Best source split: {summary['best_source_dependent_split']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
