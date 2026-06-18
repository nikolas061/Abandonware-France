#!/usr/bin/env python3
"""Derive byte-local support-start selectors for prior high-row outliers."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Callable

from lolg_tex_gap_decoder_frontier80_clean_prior_high_row_signed_delta_selector_probe import hex_byte, ratio
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_frontier80_clean_prior_high_row_byte_local_start_selector_probe")
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
    "best_selector",
    "best_selector_scope",
    "best_selector_guard",
    "best_selector_feature",
    "best_selector_keys",
    "best_selector_resolved_outliers",
    "best_selector_unresolved_outliers",
    "best_selector_switched_bytes",
    "best_selector_false_switch_bytes",
    "best_selector_false_delta_bytes",
    "best_selector_total_le2_bytes",
    "best_selector_total_le2_ratio",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

SELECTOR_FIELDNAMES = [
    "selector_name",
    "selector_scope",
    "guard_name",
    "feature_name",
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

OPERATION_FIELDNAMES = [
    "selector_name",
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
    "resolved_outlier",
    "false_switch",
]

OBSERVATION_FIELDNAMES = [
    "pair_id",
    "source_id",
    "byte_index",
    "selected_start",
    "selected_support_value_hex",
    "source_value_hex",
    "selected_delta",
    "selected_in_le2",
    "selected_outlier",
    "alt_starts_le2",
    "best_alt_start",
]


Observation = dict[str, object]
Feature = tuple[str, str, Callable[[Observation], str]]
Guard = tuple[str, str, Callable[[Observation], bool]]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def parse_int_list(text: str) -> list[int]:
    return [int(part) for part in text.split(";") if part != ""]


def parse_hex_bytes(text: str) -> list[int]:
    if not text:
        return []
    return [int(text[index : index + 2], 16) for index in range(0, len(text), 2)]


def source_value(support_value: int, delta: int) -> int:
    return (support_value + delta) & 0xFF


def start_text(value: object) -> str:
    return str(value) if value not in (None, "") else ""


def candidate_sort_key(item: dict[str, object], byte_index: int) -> tuple[int, int, int]:
    deltas = item.get("deltas", [])
    delta = int(deltas[byte_index]) if isinstance(deltas, list) and byte_index < len(deltas) else 255
    row = item.get("row", {})
    row_le2 = int_value(row, "small_delta_le2_bytes") if isinstance(row, dict) else 0
    start = int_value(row, "start") if isinstance(row, dict) else 999999
    return abs(delta), -row_le2, start


def build_observations(
    pair_rows: list[dict[str, str]],
    candidate_rows: list[dict[str, str]],
    outlier_rows: list[dict[str, str]],
    issues: list[str],
) -> tuple[list[Observation], dict[tuple[str, int], dict[str, str]]]:
    outliers_by_key = {
        (row.get("pair_id", ""), int_value(row, "byte_index")): row
        for row in outlier_rows
    }
    candidates_by_pair: dict[str, dict[int, dict[str, object]]] = defaultdict(dict)
    for row in candidate_rows:
        pair_id = row.get("pair_id", "")
        start = int_value(row, "start")
        deltas = parse_int_list(row.get("delta_values", ""))
        support = parse_hex_bytes(row.get("support_hex", ""))
        if len(deltas) != 32 or len(support) != 32:
            issues.append(f"{pair_id}:candidate_start_{start}:bad_delta_or_support_length")
            continue
        candidates_by_pair[pair_id][start] = {
            "row": row,
            "deltas": deltas,
            "support": support,
        }

    observations: list[Observation] = []
    for pair in pair_rows:
        pair_id = pair.get("pair_id", "")
        selected_start = int_value(pair, "selected_start")
        selected = candidates_by_pair.get(pair_id, {}).get(selected_start)
        if not selected:
            issues.append(f"{pair_id}:missing_selected_candidate_start_{selected_start}")
            continue
        selected_deltas = selected.get("deltas", [])
        selected_support = selected.get("support", [])
        if not isinstance(selected_deltas, list) or not isinstance(selected_support, list):
            issues.append(f"{pair_id}:bad_selected_candidate_payload")
            continue
        for byte_index in range(32):
            selected_delta = int(selected_deltas[byte_index])
            selected_support_value = int(selected_support[byte_index])
            alternatives = []
            for start, candidate in candidates_by_pair.get(pair_id, {}).items():
                if start == selected_start:
                    continue
                deltas = candidate.get("deltas", [])
                if isinstance(deltas, list) and byte_index < len(deltas) and abs(int(deltas[byte_index])) <= 2:
                    alternatives.append(candidate)
            alternatives.sort(key=lambda item: candidate_sort_key(item, byte_index))
            outlier = outliers_by_key.get((pair_id, byte_index), {})
            best_alt_start = int_value(outlier, "best_alt_start") if outlier else 0
            if not best_alt_start and alternatives:
                row = alternatives[0].get("row", {})
                best_alt_start = int_value(row, "start") if isinstance(row, dict) else 0
            observations.append(
                {
                    "pair_id": pair_id,
                    "source_id": pair.get("source_id", ""),
                    "byte_index": byte_index,
                    "selected_start": selected_start,
                    "selected_support_value": selected_support_value,
                    "source_value": source_value(selected_support_value, selected_delta),
                    "selected_delta": selected_delta,
                    "selected_in_le2": abs(selected_delta) <= 2,
                    "selected_outlier": abs(selected_delta) > 2,
                    "alt_starts_le2": [
                        int_value(item.get("row", {}), "start")
                        for item in alternatives
                        if isinstance(item.get("row", {}), dict)
                    ],
                    "best_alt_start": best_alt_start,
                    "candidates": candidates_by_pair.get(pair_id, {}),
                }
            )
    return observations, outliers_by_key


def guard_specs(outlier_positions: set[int], outlier_support_values: set[int]) -> list[Guard]:
    return [
        ("all_bytes", "broad", lambda row: True),
        ("selected_delta_abs_gt2", "guarded", lambda row: bool(row["selected_outlier"])),
        ("outlier_byte_index", "position_guarded", lambda row: int(row["byte_index"]) in outlier_positions),
        (
            "outlier_support_value",
            "value_guarded",
            lambda row: int(row["selected_support_value"]) in outlier_support_values,
        ),
    ]


def feature_specs() -> list[Feature]:
    return [
        ("constant_start", "compact", lambda row: "all"),
        ("byte_index", "compact", lambda row: f"p{int(row['byte_index']):02d}"),
        ("selected_support_value", "compact", lambda row: hex_byte(int(row["selected_support_value"]))),
        ("source_value", "compact", lambda row: hex_byte(int(row["source_value"]))),
        ("selected_delta", "delta_guarded", lambda row: str(row["selected_delta"])),
        (
            "byte_index_selected_support_value",
            "compact",
            lambda row: f"p{int(row['byte_index']):02d}|s={hex_byte(int(row['selected_support_value']))}",
        ),
        (
            "byte_index_source_value",
            "compact",
            lambda row: f"p{int(row['byte_index']):02d}|v={hex_byte(int(row['source_value']))}",
        ),
        (
            "byte_index_selected_delta",
            "delta_guarded",
            lambda row: f"p{int(row['byte_index']):02d}|d={row['selected_delta']}",
        ),
        (
            "support_source_value",
            "compact",
            lambda row: (
                f"s={hex_byte(int(row['selected_support_value']))}|v={hex_byte(int(row['source_value']))}"
            ),
        ),
        (
            "source_id_byte_index",
            "source_specific",
            lambda row: f"{row['source_id']}|p{int(row['byte_index']):02d}",
        ),
        (
            "pair_id_byte_index",
            "pair_specific",
            lambda row: f"{row['pair_id']}|p{int(row['byte_index']):02d}",
        ),
    ]


def build_selector_table(
    outlier_observations: list[Observation],
    feature: Callable[[Observation], str],
) -> tuple[dict[str, int], int, str]:
    grouped: dict[str, list[int]] = defaultdict(list)
    for observation in outlier_observations:
        best_alt_start = int(observation["best_alt_start"])
        if best_alt_start:
            grouped[feature(observation)].append(best_alt_start)

    table: dict[str, int] = {}
    conflicts = 0
    preview: list[str] = []
    for key in sorted(grouped):
        counts = Counter(grouped[key])
        selected_start, selected_count = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0]
        table[key] = selected_start
        if len(counts) > 1:
            conflicts += 1
        if len(preview) < 24:
            hist = ";".join(f"{start}:{counts[start]}" for start in sorted(counts))
            preview.append(f"{key}->{selected_start}/{selected_count}/{hist}")
    return table, conflicts, " | ".join(preview)


def chosen_candidate(observation: Observation, chosen_start: int) -> dict[str, object] | None:
    candidates = observation.get("candidates", {})
    if not isinstance(candidates, dict):
        return None
    return candidates.get(chosen_start)


def apply_selector(
    observations: list[Observation],
    selector_name: str,
    guard: Callable[[Observation], bool],
    feature: Callable[[Observation], str],
    selector_table: dict[str, int],
) -> tuple[dict[str, str], list[dict[str, str]]]:
    total = len(observations)
    outlier_count = sum(1 for row in observations if row["selected_outlier"])
    resolved = 0
    unresolved = 0
    switched = 0
    outlier_switches = 0
    false_switches = 0
    false_delta = 0
    total_le2 = 0
    operation_rows: list[dict[str, str]] = []

    for observation in observations:
        selected_start = int(observation["selected_start"])
        selected_delta = int(observation["selected_delta"])
        selected_outlier = bool(observation["selected_outlier"])
        key = feature(observation)
        chosen_start = selected_start
        chosen_delta = selected_delta
        chosen_support = int(observation["selected_support_value"])
        if guard(observation) and key in selector_table:
            chosen_start = selector_table[key]
            candidate = chosen_candidate(observation, chosen_start)
            if candidate:
                deltas = candidate.get("deltas", [])
                support = candidate.get("support", [])
                byte_index = int(observation["byte_index"])
                if isinstance(deltas, list) and byte_index < len(deltas):
                    chosen_delta = int(deltas[byte_index])
                if isinstance(support, list) and byte_index < len(support):
                    chosen_support = int(support[byte_index])
        did_switch = chosen_start != selected_start
        if did_switch:
            switched += 1
            if selected_outlier:
                outlier_switches += 1
            else:
                false_switches += 1
        if abs(chosen_delta) <= 2:
            total_le2 += 1
            if selected_outlier:
                resolved += 1
        elif selected_outlier:
            unresolved += 1
        if not selected_outlier and did_switch and abs(chosen_delta) > 2:
            false_delta += 1
        if did_switch or selected_outlier:
            operation_rows.append(
                {
                    "selector_name": selector_name,
                    "pair_id": str(observation["pair_id"]),
                    "source_id": str(observation["source_id"]),
                    "byte_index": str(observation["byte_index"]),
                    "selector_key": key,
                    "selected_start": str(selected_start),
                    "selected_support_value_hex": hex_byte(int(observation["selected_support_value"])),
                    "source_value_hex": hex_byte(int(observation["source_value"])),
                    "selected_delta": str(selected_delta),
                    "chosen_start": str(chosen_start),
                    "chosen_support_value_hex": hex_byte(chosen_support),
                    "chosen_delta": str(chosen_delta),
                    "selected_outlier": "1" if selected_outlier else "0",
                    "resolved_outlier": "1" if selected_outlier and abs(chosen_delta) <= 2 else "0",
                    "false_switch": "1" if did_switch and not selected_outlier else "0",
                }
            )

    row = {
        "target_outlier_rows": str(outlier_count),
        "resolved_outliers": str(resolved),
        "unresolved_outliers": str(unresolved),
        "switched_bytes": str(switched),
        "outlier_switch_bytes": str(outlier_switches),
        "false_switch_bytes": str(false_switches),
        "false_delta_bytes": str(false_delta),
        "total_le2_bytes": str(total_le2),
        "total_le2_ratio": ratio(total_le2, total),
    }
    return row, operation_rows


def build_selector_rows(observations: list[Observation]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    outlier_observations = [row for row in observations if row["selected_outlier"]]
    outlier_positions = {int(row["byte_index"]) for row in outlier_observations}
    outlier_support_values = {int(row["selected_support_value"]) for row in outlier_observations}
    selector_rows: list[dict[str, str]] = []
    operation_rows: list[dict[str, str]] = []

    for guard_name, guard_scope, guard in guard_specs(outlier_positions, outlier_support_values):
        for feature_name, feature_scope, feature in feature_specs():
            table, conflicts, table_preview = build_selector_table(outlier_observations, feature)
            selector_name = f"{guard_name}/{feature_name}"
            result, operations = apply_selector(observations, selector_name, guard, feature, table)
            selector_rows.append(
                {
                    "selector_name": selector_name,
                    "selector_scope": f"{guard_scope}:{feature_scope}",
                    "guard_name": guard_name,
                    "feature_name": feature_name,
                    "key_count": str(len(table)),
                    **result,
                    "training_conflicts": str(conflicts),
                    "selector_table": table_preview,
                }
            )
            operation_rows.extend(operations)

    selector_rows.sort(
        key=lambda row: (
            -int_value(row, "resolved_outliers"),
            int_value(row, "false_switch_bytes"),
            int_value(row, "false_delta_bytes"),
            -int_value(row, "total_le2_bytes"),
            int_value(row, "training_conflicts"),
            int_value(row, "key_count"),
            row.get("selector_scope", ""),
            row.get("selector_name", ""),
        )
    )
    return selector_rows, operation_rows


def best_selector(selector_rows: list[dict[str, str]]) -> dict[str, str]:
    false_free = [
        row
        for row in selector_rows
        if int_value(row, "unresolved_outliers") == 0
        and int_value(row, "false_switch_bytes") == 0
        and int_value(row, "false_delta_bytes") == 0
    ]
    if false_free:
        scope_priority = {
            "guarded:compact": 0,
            "guarded:delta_guarded": 1,
            "guarded:source_specific": 2,
            "guarded:pair_specific": 3,
        }
        feature_priority = {
            "selected_support_value": 0,
            "byte_index_selected_support_value": 1,
            "support_source_value": 2,
            "byte_index_source_value": 3,
            "source_value": 4,
            "byte_index_selected_delta": 5,
            "selected_delta": 6,
            "source_id_byte_index": 7,
            "pair_id_byte_index": 8,
        }
        return sorted(
            false_free,
            key=lambda row: (
                scope_priority.get(row.get("selector_scope", ""), 10),
                feature_priority.get(row.get("feature_name", ""), 20),
                int_value(row, "key_count"),
                row.get("selector_name", ""),
            ),
        )[0]
    return selector_rows[0] if selector_rows else {}


def build_observation_rows(observations: list[Observation]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for observation in observations:
        rows.append(
            {
                "pair_id": str(observation["pair_id"]),
                "source_id": str(observation["source_id"]),
                "byte_index": str(observation["byte_index"]),
                "selected_start": str(observation["selected_start"]),
                "selected_support_value_hex": hex_byte(int(observation["selected_support_value"])),
                "source_value_hex": hex_byte(int(observation["source_value"])),
                "selected_delta": str(observation["selected_delta"]),
                "selected_in_le2": "1" if observation["selected_in_le2"] else "0",
                "selected_outlier": "1" if observation["selected_outlier"] else "0",
                "alt_starts_le2": ";".join(str(start) for start in observation["alt_starts_le2"]),
                "best_alt_start": start_text(observation["best_alt_start"]),
            }
        )
    return rows


def build_summary(
    observations: list[Observation],
    selector_rows: list[dict[str, str]],
    best: dict[str, str],
    *,
    issue_count: int,
) -> dict[str, str]:
    total = len(observations)
    outliers = sum(1 for row in observations if row["selected_outlier"])
    ready = (
        best
        and int_value(best, "resolved_outliers") == outliers
        and int_value(best, "unresolved_outliers") == 0
        and int_value(best, "false_switch_bytes") == 0
        and int_value(best, "false_delta_bytes") == 0
        and int_value(best, "total_le2_bytes") == total
    )
    verdict = (
        "frontier80_prior_high_row_byte_local_start_selector_ready"
        if ready
        else "frontier80_prior_high_row_byte_local_start_selector_needs_guard"
    )
    next_probe = (
        "validate non-oracle inputs for guarded byte-local support-start selector"
        if ready
        else "tighten byte-local support-start selector guards before promotion"
    )
    return {
        "scope": "total",
        "total_bytes": str(total),
        "outlier_bytes": str(outliers),
        "selector_candidate_rows": str(len(selector_rows)),
        "best_selector": best.get("selector_name", ""),
        "best_selector_scope": best.get("selector_scope", ""),
        "best_selector_guard": best.get("guard_name", ""),
        "best_selector_feature": best.get("feature_name", ""),
        "best_selector_keys": best.get("key_count", "0"),
        "best_selector_resolved_outliers": best.get("resolved_outliers", "0"),
        "best_selector_unresolved_outliers": best.get("unresolved_outliers", "0"),
        "best_selector_switched_bytes": best.get("switched_bytes", "0"),
        "best_selector_false_switch_bytes": best.get("false_switch_bytes", "0"),
        "best_selector_false_delta_bytes": best.get("false_delta_bytes", "0"),
        "best_selector_total_le2_bytes": best.get("total_le2_bytes", "0"),
        "best_selector_total_le2_ratio": best.get("total_le2_ratio", "0.000000"),
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
    selector_rows: list[dict[str, str]],
    operation_rows: list[dict[str, str]],
    observation_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "selectors": selector_rows,
        "operations": operation_rows,
        "observations": observation_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("selector_candidates.csv", output_dir / "selector_candidates.csv"),
            ("selector_operations.csv", output_dir / "selector_operations.csv"),
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
    <div class="sub">Scores byte-local start-switch selectors over the high-row outlier fallback set.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Best selector</div><div class="value">{html.escape(summary['best_selector'])}</div></div>
    <div class="stat"><div class="label">Resolved outliers</div><div class="value">{html.escape(summary['best_selector_resolved_outliers'])}/{html.escape(summary['outlier_bytes'])}</div></div>
    <div class="stat"><div class="label">False switches</div><div class="value">{html.escape(summary['best_selector_false_switch_bytes'])}</div></div>
    <div class="stat"><div class="label">Total &lt;=2</div><div class="value">{html.escape(summary['best_selector_total_le2_bytes'])}/{html.escape(summary['total_bytes'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div><div class="sub">{html.escape(summary['review_verdict'])}: {html.escape(summary['next_probe'])}</div></section>
  <section class="panel"><h2>Selector candidates</h2>{render_table(selector_rows, SELECTOR_FIELDNAMES)}</section>
  <section class="panel"><h2>Selector operations</h2>{render_table(operation_rows, OPERATION_FIELDNAMES)}</section>
  <section class="panel"><h2>Byte observations</h2>{render_table(observation_rows, OBSERVATION_FIELDNAMES)}</section>
</main>
<script type="application/json" id="byte-local-start-selector-data">{data_json}</script>
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
    selector_rows, operation_rows = build_selector_rows(observations)
    best = best_selector(selector_rows)
    summary = build_summary(observations, selector_rows, best, issue_count=len(issues))
    best_operation_rows = [row for row in operation_rows if row.get("selector_name") == summary["best_selector"]]
    observation_rows = build_observation_rows(observations)

    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "selector_candidates.csv", SELECTOR_FIELDNAMES, selector_rows)
    write_csv(output_dir / "selector_operations.csv", OPERATION_FIELDNAMES, best_operation_rows)
    write_csv(output_dir / "byte_observations.csv", OBSERVATION_FIELDNAMES, observation_rows)
    (output_dir / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""))
    (output_dir / "index.html").write_text(
        build_html(summary, selector_rows, best_operation_rows, observation_rows, output_dir, title)
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe byte-local support-start selectors for frontier80 high-row outliers.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--pairs", type=Path, default=DEFAULT_PAIRS)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--outliers", type=Path, default=DEFAULT_OUTLIERS)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Prior High Row Byte Local Start Selector Probe",
    )
    args = parser.parse_args()

    summary = write_report(
        args.output,
        args.pairs,
        args.candidates,
        args.outliers,
        title=args.title,
    )
    print(f"Best selector: {summary['best_selector']}")
    print(f"Resolved outliers: {summary['best_selector_resolved_outliers']}/{summary['outlier_bytes']}")
    print(f"False switches: {summary['best_selector_false_switch_bytes']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
