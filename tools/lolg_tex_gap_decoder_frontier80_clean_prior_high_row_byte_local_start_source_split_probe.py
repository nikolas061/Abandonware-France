#!/usr/bin/env python3
"""Validate source-dependent false-positive splits for the high-row byte-local guard."""

from __future__ import annotations

import argparse
import csv
import html
import json
from pathlib import Path
from typing import Callable

from lolg_tex_gap_decoder_frontier80_clean_prior_high_row_byte_local_start_selector_probe import ratio
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_frontier80_clean_prior_high_row_byte_local_start_source_split_probe")
DEFAULT_SWITCHES = Path(
    "output/tex_gap_decoder_frontier80_clean_prior_high_row_byte_local_start_false_positive_split_probe/switch_rows.csv"
)
DEFAULT_BYTE_DELTAS = Path(
    "output/tex_gap_decoder_frontier80_clean_prior_high_row_signed_delta_selector_probe/byte_deltas.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "switch_rows",
    "target_switch_rows",
    "false_switch_rows",
    "best_split",
    "best_split_kept_target",
    "best_split_kept_false",
    "best_split_kept_target_source_known",
    "best_split_kept_target_source_unknown",
    "best_split_kept_false_source_known",
    "best_split_kept_false_source_unknown",
    "clean_source_splits",
    "source_unknown_switch_rows",
    "source_unknown_target_rows",
    "source_unknown_false_rows",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

SPLIT_FIELDNAMES = [
    "split_name",
    "feature_name",
    "key_count",
    "target_rows",
    "false_rows",
    "kept_target",
    "dropped_target",
    "kept_false",
    "dropped_false",
    "kept_target_source_known",
    "kept_target_source_unknown",
    "kept_false_source_known",
    "kept_false_source_unknown",
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
    "selected_delta_abs_gt2",
    "source_known",
    "support_known",
    "chosen_start",
    "chosen_support_value_hex",
    "chosen_delta",
    "selected_outlier",
    "false_switch",
    "false_delta",
]

DEPENDENCY_FIELDNAMES = [
    "dependency_kind",
    "rows",
    "target_rows",
    "false_rows",
    "pairs",
]


SwitchRow = dict[str, str]
Feature = tuple[str, Callable[[SwitchRow], str]]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def signed_abs_gt2(row: dict[str, str]) -> str:
    return "1" if abs(int_value(row, "selected_delta")) > 2 else "0"


def build_switch_rows(switch_rows: list[dict[str, str]], byte_rows: list[dict[str, str]], issues: list[str]) -> list[SwitchRow]:
    byte_by_key = {
        (row.get("pair_id", ""), row.get("byte_index", "")): row
        for row in byte_rows
    }
    rows: list[SwitchRow] = []
    for row in switch_rows:
        key = (row.get("pair_id", ""), row.get("byte_index", ""))
        byte = byte_by_key.get(key)
        if not byte:
            issues.append(f"{key[0]}:p{key[1]}:missing_byte_delta")
            byte = {}
        source_known = byte.get("source_known", "")
        support_known = byte.get("support_known", "")
        rows.append(
            {
                "pair_id": row.get("pair_id", ""),
                "source_id": row.get("source_id", ""),
                "byte_index": row.get("byte_index", ""),
                "selector_key": row.get("selector_key", ""),
                "selected_start": row.get("selected_start", ""),
                "selected_support_value_hex": row.get("selected_support_value_hex", ""),
                "source_value_hex": row.get("source_value_hex", ""),
                "selected_delta": row.get("selected_delta", ""),
                "selected_delta_abs_gt2": signed_abs_gt2(row),
                "source_known": source_known,
                "support_known": support_known,
                "chosen_start": row.get("chosen_start", ""),
                "chosen_support_value_hex": row.get("chosen_support_value_hex", ""),
                "chosen_delta": row.get("chosen_delta", ""),
                "selected_outlier": row.get("selected_outlier", ""),
                "false_switch": row.get("false_switch", ""),
                "false_delta": row.get("false_delta", ""),
            }
        )
    return rows


def feature_specs() -> list[Feature]:
    return [
        ("selected_delta_abs_gt2", lambda row: row.get("selected_delta_abs_gt2", "")),
        ("selected_delta", lambda row: row.get("selected_delta", "")),
        ("source_value", lambda row: row.get("source_value_hex", "")),
        (
            "selector_key_source_value",
            lambda row: f"{row.get('selector_key', '')}|v={row.get('source_value_hex', '')}",
        ),
        (
            "support_source_delta",
            lambda row: (
                f"s={row.get('selected_support_value_hex', '')}|v={row.get('source_value_hex', '')}|"
                f"d={row.get('selected_delta', '')}"
            ),
        ),
    ]


def build_split_rows(switch_rows: list[SwitchRow]) -> list[dict[str, str]]:
    target_rows = [row for row in switch_rows if row.get("selected_outlier") == "1"]
    false_rows = [row for row in switch_rows if row.get("false_switch") == "1"]
    rows: list[dict[str, str]] = []
    for feature_name, feature in feature_specs():
        keep_values = sorted({feature(row) for row in target_rows})
        keep_set = set(keep_values)
        kept = [row for row in switch_rows if feature(row) in keep_set]
        kept_target = [row for row in kept if row.get("selected_outlier") == "1"]
        kept_false = [row for row in kept if row.get("false_switch") == "1"]
        rows.append(
            {
                "split_name": f"source_dependent/{feature_name}",
                "feature_name": feature_name,
                "key_count": str(len(keep_values)),
                "target_rows": str(len(target_rows)),
                "false_rows": str(len(false_rows)),
                "kept_target": str(len(kept_target)),
                "dropped_target": str(len(target_rows) - len(kept_target)),
                "kept_false": str(len(kept_false)),
                "dropped_false": str(len(false_rows) - len(kept_false)),
                "kept_target_source_known": str(sum(1 for row in kept_target if row.get("source_known") == "1")),
                "kept_target_source_unknown": str(sum(1 for row in kept_target if row.get("source_known") != "1")),
                "kept_false_source_known": str(sum(1 for row in kept_false if row.get("source_known") == "1")),
                "kept_false_source_unknown": str(sum(1 for row in kept_false if row.get("source_known") != "1")),
                "false_free": "1" if len(kept_target) == len(target_rows) and not kept_false else "0",
                "keep_table": ";".join(keep_values),
            }
        )
    rows.sort(
        key=lambda row: (
            -int_value(row, "kept_target"),
            int_value(row, "kept_false"),
            int_value(row, "kept_target_source_unknown"),
            int_value(row, "key_count"),
            row.get("feature_name", ""),
        )
    )
    return rows


def build_dependency_rows(switch_rows: list[SwitchRow]) -> list[dict[str, str]]:
    groups = {
        "source_known": [row for row in switch_rows if row.get("source_known") == "1"],
        "source_unknown": [row for row in switch_rows if row.get("source_known") != "1"],
        "support_known": [row for row in switch_rows if row.get("support_known") == "1"],
        "support_unknown": [row for row in switch_rows if row.get("support_known") != "1"],
    }
    rows: list[dict[str, str]] = []
    for name, group in groups.items():
        rows.append(
            {
                "dependency_kind": name,
                "rows": str(len(group)),
                "target_rows": str(sum(1 for row in group if row.get("selected_outlier") == "1")),
                "false_rows": str(sum(1 for row in group if row.get("false_switch") == "1")),
                "pairs": ";".join(f"{row.get('pair_id', '')}:p{row.get('byte_index', '')}" for row in group),
            }
        )
    return rows


def best_split(split_rows: list[dict[str, str]]) -> dict[str, str]:
    clean = [row for row in split_rows if row.get("false_free") == "1"]
    if clean:
        priority = {
            "selected_delta_abs_gt2": 0,
            "selected_delta": 1,
            "source_value": 2,
            "selector_key_source_value": 3,
            "support_source_delta": 4,
        }
        return sorted(
            clean,
            key=lambda row: (
                int_value(row, "kept_target_source_unknown"),
                priority.get(row.get("feature_name", ""), 10),
                int_value(row, "key_count"),
            ),
        )[0]
    return split_rows[0] if split_rows else {}


def build_summary(
    switch_rows: list[SwitchRow],
    split_rows: list[dict[str, str]],
    best: dict[str, str],
    *,
    issue_count: int,
) -> dict[str, str]:
    target_rows = [row for row in switch_rows if row.get("selected_outlier") == "1"]
    false_rows = [row for row in switch_rows if row.get("false_switch") == "1"]
    unknown = [row for row in switch_rows if row.get("source_known") != "1"]
    unknown_target = [row for row in unknown if row.get("selected_outlier") == "1"]
    unknown_false = [row for row in unknown if row.get("false_switch") == "1"]
    clean_splits = [row for row in split_rows if row.get("false_free") == "1"]
    clean = bool(best) and best.get("false_free") == "1"
    unknown_prereq = int_value(best, "kept_target_source_unknown") > 0 if best else False
    if clean and not unknown_prereq:
        verdict = "frontier80_prior_high_row_source_split_ready"
        next_probe = "promote source-dependent split for byte-local high-row guard"
    elif clean and unknown_prereq:
        verdict = "frontier80_prior_high_row_source_split_clean_prereq_needed"
        next_probe = "derive source-byte prerequisites for selected-delta high-row split"
    else:
        verdict = "frontier80_prior_high_row_source_split_weak"
        next_probe = "expand source-dependent split features for byte-local high-row guard"
    return {
        "scope": "total",
        "switch_rows": str(len(switch_rows)),
        "target_switch_rows": str(len(target_rows)),
        "false_switch_rows": str(len(false_rows)),
        "best_split": best.get("split_name", ""),
        "best_split_kept_target": best.get("kept_target", "0"),
        "best_split_kept_false": best.get("kept_false", "0"),
        "best_split_kept_target_source_known": best.get("kept_target_source_known", "0"),
        "best_split_kept_target_source_unknown": best.get("kept_target_source_unknown", "0"),
        "best_split_kept_false_source_known": best.get("kept_false_source_known", "0"),
        "best_split_kept_false_source_unknown": best.get("kept_false_source_unknown", "0"),
        "clean_source_splits": str(len(clean_splits)),
        "source_unknown_switch_rows": str(len(unknown)),
        "source_unknown_target_rows": str(len(unknown_target)),
        "source_unknown_false_rows": str(len(unknown_false)),
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
    dependency_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "splits": split_rows,
        "switches": switch_rows,
        "dependencies": dependency_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("source_split_candidates.csv", output_dir / "source_split_candidates.csv"),
            ("source_split_switch_rows.csv", output_dir / "source_split_switch_rows.csv"),
            ("source_dependencies.csv", output_dir / "source_dependencies.csv"),
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
    <div class="sub">Validates clean source-dependent splits and reports source-known prerequisites.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Best split</div><div class="value">{html.escape(summary['best_split'])}</div></div>
    <div class="stat"><div class="label">Kept target</div><div class="value">{html.escape(summary['best_split_kept_target'])}/{html.escape(summary['target_switch_rows'])}</div></div>
    <div class="stat"><div class="label">Kept false</div><div class="value">{html.escape(summary['best_split_kept_false'])}</div></div>
    <div class="stat"><div class="label">Unknown target source</div><div class="value">{html.escape(summary['best_split_kept_target_source_unknown'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div><div class="sub">{html.escape(summary['review_verdict'])}: {html.escape(summary['next_probe'])}</div></section>
  <section class="panel"><h2>Source splits</h2>{render_table(split_rows, SPLIT_FIELDNAMES)}</section>
  <section class="panel"><h2>Switch rows</h2>{render_table(switch_rows, SWITCH_FIELDNAMES)}</section>
  <section class="panel"><h2>Source dependencies</h2>{render_table(dependency_rows, DEPENDENCY_FIELDNAMES)}</section>
</main>
<script type="application/json" id="source-split-data">{data_json}</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    switches_path: Path,
    byte_deltas_path: Path,
    *,
    title: str,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    switch_rows = build_switch_rows(read_csv(switches_path), read_csv(byte_deltas_path), issues)
    if not switch_rows:
        issues.append("missing_switch_rows")
    split_rows = build_split_rows(switch_rows)
    dependency_rows = build_dependency_rows(switch_rows)
    best = best_split(split_rows)
    summary = build_summary(switch_rows, split_rows, best, issue_count=len(issues))

    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "source_split_candidates.csv", SPLIT_FIELDNAMES, split_rows)
    write_csv(output_dir / "source_split_switch_rows.csv", SWITCH_FIELDNAMES, switch_rows)
    write_csv(output_dir / "source_dependencies.csv", DEPENDENCY_FIELDNAMES, dependency_rows)
    (output_dir / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""))
    (output_dir / "index.html").write_text(
        build_html(summary, split_rows, switch_rows, dependency_rows, output_dir, title)
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate source-dependent splits for high-row byte-local guards.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--switches", type=Path, default=DEFAULT_SWITCHES)
    parser.add_argument("--byte-deltas", type=Path, default=DEFAULT_BYTE_DELTAS)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Prior High Row Byte Local Start Source Split Probe",
    )
    args = parser.parse_args()

    summary = write_report(args.output, args.switches, args.byte_deltas, title=args.title)
    print(f"Best split: {summary['best_split']}")
    print(f"Kept target: {summary['best_split_kept_target']}/{summary['target_switch_rows']}")
    print(f"Kept false: {summary['best_split_kept_false']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
