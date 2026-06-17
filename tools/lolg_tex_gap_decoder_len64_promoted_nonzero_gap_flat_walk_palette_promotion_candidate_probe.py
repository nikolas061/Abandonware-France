#!/usr/bin/env python3
"""Build a guarded promotion-candidate report for flat-walk palette formulas."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import defaultdict
from pathlib import Path

from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_fill_selector_probe import read_csv
from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_flat_walk_palette_corpus_formula_probe import (
    DEFAULT_OUTPUT as DEFAULT_CORPUS_FORMULA_OUTPUT,
)
from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_flat_walk_backref_probe import (
    DEFAULT_OUTPUT as DEFAULT_BACKREF_OUTPUT,
)
from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_flat_walk_palette_mix_probe import (
    DEFAULT_OUTPUT as DEFAULT_MIX_OUTPUT,
)
from lolg_tex_gap_opcode_probe import int_value, write_csv


DEFAULT_FORMULA_ROWS = DEFAULT_CORPUS_FORMULA_OUTPUT / "rows.csv"
DEFAULT_MIX_TARGETS = DEFAULT_MIX_OUTPUT / "targets.csv"
DEFAULT_BACKREF_TARGETS = DEFAULT_BACKREF_OUTPUT / "targets.csv"
DEFAULT_OUTPUT = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_promotion_candidate_probe"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "mix_target_rows",
    "candidate_target_rows",
    "formula_value_rows",
    "formula_exact_value_rows",
    "formula_mismatch_rows",
    "known_conflicted_value_rows",
    "candidate_ready_target_rows",
    "candidate_ready_bytes",
    "backref_unlock_bytes",
    "unique_backref_unlock_bytes",
    "backref_candidate_overlap_bytes",
    "raw_candidate_plus_unlock_bytes",
    "total_candidate_plus_unlock_bytes",
    "candidate_pools",
    "transform_sets",
    "promotion_ready_bytes",
    "issue_rows",
]

TARGET_FIELDNAMES = [
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "span_index",
    "op_index",
    "start",
    "end",
    "length",
    "palette_size",
    "candidate_pool",
    "candidate_transform_set",
    "candidate_kind",
    "formula_value_rows",
    "formula_exact_value_rows",
    "formula_mismatch_rows",
    "known_conflicted_value_rows",
    "candidate_ready_bytes",
    "backref_unlock_rows",
    "backref_unlock_bytes",
    "unique_backref_unlock_rows",
    "unique_backref_unlock_bytes",
    "backref_candidate_overlap_rows",
    "backref_candidate_overlap_bytes",
    "raw_candidate_plus_unlock_bytes",
    "total_candidate_plus_unlock_bytes",
    "promotion_selector",
    "replay_status",
    "verdict",
    "issues",
]

VALUE_FIELDNAMES = [
    "target_start",
    "value_hex",
    "value_status",
    "candidate_pool",
    "source_offset",
    "source_raw_hex",
    "plan_shift",
    "derived_shift",
    "shift_formula_exact",
    "issues",
]


def target_key(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    return (
        row.get("archive", ""),
        row.get("pcx_name", ""),
        row.get("frontier_id", ""),
        row.get("start", ""),
        row.get("end", ""),
    )


def backref_source_key(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    return (
        row.get("archive", ""),
        row.get("pcx_name", ""),
        row.get("frontier_id", ""),
        row.get("best_source_start", ""),
        row.get("best_source_end", ""),
    )


def backref_copy_key(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    return target_key(row)


def unlock_targets_by_source(
    backref_rows: list[dict[str, str]],
) -> dict[tuple[str, str, str, str, str], list[dict[str, str]]]:
    unlocks: dict[tuple[str, str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in backref_rows:
        if row.get("best_exact") != "1":
            continue
        unlocks[backref_source_key(row)].append(row)
    return unlocks


def formula_groups(rows: list[dict[str, str]]) -> dict[tuple[str, str, str, str, str], list[dict[str, str]]]:
    groups: dict[tuple[str, str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[target_key(row)].append(row)
    return groups


def selector_for(row: dict[str, str]) -> str:
    return (
        "flat_walk_palette_formula"
        f"|pool={row.get('candidate_pool', '')}"
        f"|transforms={row.get('candidate_transform_set', '')}"
        "|shift=signed_delta(raw,value)"
    )


def build_target_rows(
    mix_targets: list[dict[str, str]],
    formula_rows: list[dict[str, str]],
    backref_rows: list[dict[str, str]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    grouped_formula = formula_groups(formula_rows)
    unlocks = unlock_targets_by_source(backref_rows)
    target_rows: list[dict[str, object]] = []
    value_rows: list[dict[str, object]] = []
    for mix in mix_targets:
        if not mix.get("candidate_plan"):
            continue
        rows = grouped_formula.get(target_key(mix), [])
        issues = [issue for issue in mix.get("issues", "").split(";") if issue]
        if not rows:
            issues.append("missing_formula_rows")
        formula_value_rows = len(rows)
        formula_exact_rows = sum(int_value(row, "shift_formula_exact") for row in rows)
        formula_mismatch_rows = formula_value_rows - formula_exact_rows
        known_conflicted_rows = sum(
            1 for row in rows if row.get("value_status") == "conflicted_multi_signature_value"
        )
        if formula_mismatch_rows:
            issues.append("formula_mismatch")
        if any(row.get("issues") for row in rows):
            issues.append("formula_row_issues")
        candidate_ready = not issues and formula_value_rows > 0
        verdict = "formula_promotion_candidate_ready" if candidate_ready else "formula_promotion_candidate_review"
        target = {
            "rank": mix.get("rank", ""),
            "archive": mix.get("archive", ""),
            "archive_tag": mix.get("archive_tag", ""),
            "pcx_name": mix.get("pcx_name", ""),
            "frontier_id": mix.get("frontier_id", ""),
            "span_index": mix.get("span_index", ""),
            "op_index": mix.get("op_index", ""),
            "start": mix.get("start", ""),
            "end": mix.get("end", ""),
            "length": mix.get("length", ""),
            "palette_size": mix.get("palette_size", ""),
            "candidate_pool": mix.get("candidate_pool", ""),
            "candidate_transform_set": mix.get("candidate_transform_set", ""),
            "candidate_kind": mix.get("candidate_kind", ""),
            "formula_value_rows": formula_value_rows,
            "formula_exact_value_rows": formula_exact_rows,
            "formula_mismatch_rows": formula_mismatch_rows,
            "known_conflicted_value_rows": known_conflicted_rows,
            "candidate_ready_bytes": int_value(mix, "length") if candidate_ready else 0,
            "backref_unlock_rows": mix.get("copy_unlock_rows", "0"),
            "backref_unlock_bytes": mix.get("copy_unlock_bytes", "0"),
            "unique_backref_unlock_rows": 0,
            "unique_backref_unlock_bytes": 0,
            "backref_candidate_overlap_rows": 0,
            "backref_candidate_overlap_bytes": 0,
            "raw_candidate_plus_unlock_bytes": (
                int_value(mix, "length") + int_value(mix, "copy_unlock_bytes") if candidate_ready else 0
            ),
            "total_candidate_plus_unlock_bytes": int_value(mix, "length") if candidate_ready else 0,
            "promotion_selector": selector_for(mix) if candidate_ready else "",
            "replay_status": "needs_guarded_replay" if candidate_ready else "blocked_review",
            "verdict": verdict,
            "issues": ";".join(issues),
        }
        target_rows.append(target)
        for row in rows:
            value_rows.append(
                {
                    "target_start": mix.get("start", ""),
                    "value_hex": row.get("value_hex", ""),
                    "value_status": row.get("value_status", ""),
                    "candidate_pool": row.get("candidate_pool", ""),
                    "source_offset": row.get("source_offset", ""),
                    "source_raw_hex": row.get("source_raw_hex", ""),
                    "plan_shift": row.get("plan_shift", ""),
                    "derived_shift": row.get("derived_shift", ""),
                    "shift_formula_exact": row.get("shift_formula_exact", ""),
                    "issues": row.get("issues", ""),
                }
            )
    ready_keys = {target_key(row) for row in target_rows if row.get("verdict") == "formula_promotion_candidate_ready"}
    for target in target_rows:
        if target.get("verdict") != "formula_promotion_candidate_ready":
            continue
        unique_rows = 0
        unique_bytes = 0
        overlap_rows = 0
        overlap_bytes = 0
        for backref in unlocks.get(target_key(target), []):
            length = int_value(backref, "length")
            if backref_copy_key(backref) in ready_keys:
                overlap_rows += 1
                overlap_bytes += length
            else:
                unique_rows += 1
                unique_bytes += length
        target["unique_backref_unlock_rows"] = unique_rows
        target["unique_backref_unlock_bytes"] = unique_bytes
        target["backref_candidate_overlap_rows"] = overlap_rows
        target["backref_candidate_overlap_bytes"] = overlap_bytes
        target["total_candidate_plus_unlock_bytes"] = int_value(target, "candidate_ready_bytes") + unique_bytes
    target_rows.sort(key=lambda row: (str(row.get("pcx_name", "")), int_value(row, "start")))
    return target_rows, value_rows


def build_summary(
    mix_targets: list[dict[str, str]],
    target_rows: list[dict[str, object]],
    value_rows: list[dict[str, object]],
) -> dict[str, object]:
    ready_rows = [row for row in target_rows if row.get("verdict") == "formula_promotion_candidate_ready"]
    return {
        "scope": "total",
        "mix_target_rows": len(mix_targets),
        "candidate_target_rows": len(target_rows),
        "formula_value_rows": len(value_rows),
        "formula_exact_value_rows": sum(int_value(row, "shift_formula_exact") for row in value_rows),
        "formula_mismatch_rows": sum(1 for row in value_rows if not int_value(row, "shift_formula_exact")),
        "known_conflicted_value_rows": sum(
            1 for row in value_rows if row.get("value_status") == "conflicted_multi_signature_value"
        ),
        "candidate_ready_target_rows": len(ready_rows),
        "candidate_ready_bytes": sum(int_value(row, "candidate_ready_bytes") for row in ready_rows),
        "backref_unlock_bytes": sum(int_value(row, "backref_unlock_bytes") for row in ready_rows),
        "unique_backref_unlock_bytes": sum(int_value(row, "unique_backref_unlock_bytes") for row in ready_rows),
        "backref_candidate_overlap_bytes": sum(
            int_value(row, "backref_candidate_overlap_bytes") for row in ready_rows
        ),
        "raw_candidate_plus_unlock_bytes": sum(
            int_value(row, "raw_candidate_plus_unlock_bytes") for row in ready_rows
        ),
        "total_candidate_plus_unlock_bytes": sum(
            int_value(row, "total_candidate_plus_unlock_bytes") for row in ready_rows
        ),
        "candidate_pools": len({row.get("candidate_pool", "") for row in ready_rows}),
        "transform_sets": len({row.get("candidate_transform_set", "") for row in ready_rows}),
        "promotion_ready_bytes": 0,
        "issue_rows": sum(1 for row in target_rows if row.get("issues")),
    }


def render_table(rows: list[dict[str, object]], fields: list[str], limit: int = 240) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, object],
    target_rows: list[dict[str, object]],
    value_rows: list[dict[str, object]],
    title: str,
) -> str:
    data_json = json.dumps(
        {"summary": summary, "targets": target_rows, "values": value_rows},
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
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: .75rem; margin: 1rem 0; }}
.box {{ border: 1px solid #31424a; background: #172023; padding: .75rem; }}
.num {{ font-size: 1.35rem; font-weight: 750; }}
.muted {{ color: #9dafb5; }}
.panel {{ overflow-x: auto; margin-top: 1rem; }}
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<div class="grid">
  <div class="box"><div class="num">{summary['candidate_ready_target_rows']}</div><div class="muted">candidate-ready targets</div></div>
  <div class="box"><div class="num">{summary['candidate_ready_bytes']}</div><div class="muted">candidate-ready bytes</div></div>
  <div class="box"><div class="num">{summary['total_candidate_plus_unlock_bytes']}</div><div class="muted">candidate plus unlock bytes</div></div>
  <div class="box"><div class="num">{summary['backref_candidate_overlap_bytes']}</div><div class="muted">backref overlap bytes</div></div>
  <div class="box"><div class="num">{summary['formula_exact_value_rows']}</div><div class="muted">formula exact value rows</div></div>
  <div class="box"><div class="num">{summary['issue_rows']}</div><div class="muted">issue rows</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Targets</h2>{render_table(target_rows, TARGET_FIELDNAMES)}</div>
<div class="panel"><h2>Values</h2>{render_table(value_rows, VALUE_FIELDNAMES)}</div>
<script type="application/json" id="flat-walk-palette-promotion-candidate-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Build flat-walk palette formula promotion candidates.")
    parser.add_argument("--mix-targets", type=Path, default=DEFAULT_MIX_TARGETS)
    parser.add_argument("--formula-rows", type=Path, default=DEFAULT_FORMULA_ROWS)
    parser.add_argument("--backref-targets", type=Path, default=DEFAULT_BACKREF_TARGETS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Flat Walk Palette Promotion Candidate Probe",
    )
    args = parser.parse_args()

    mix_targets = read_csv(args.mix_targets)
    target_rows, value_rows = build_target_rows(
        mix_targets,
        read_csv(args.formula_rows),
        read_csv(args.backref_targets),
    )
    summary = build_summary(mix_targets, target_rows, value_rows)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, target_rows)
    write_csv(args.output / "values.csv", VALUE_FIELDNAMES, value_rows)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, target_rows, value_rows, args.title))

    print(f"Candidate-ready targets: {summary['candidate_ready_target_rows']}")
    print(f"Candidate-ready bytes: {summary['candidate_ready_bytes']}")
    print(f"Unique backref unlock bytes: {summary['unique_backref_unlock_bytes']}")
    print(f"Backref overlap bytes: {summary['backref_candidate_overlap_bytes']}")
    print(f"Candidate plus unlock bytes: {summary['total_candidate_plus_unlock_bytes']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
