#!/usr/bin/env python3
"""Probe row-family support for low-exception peer alignments."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gradient_sequence_high_safe_low_exception_alignment_review import (
    DEFAULT_ALIGNMENTS,
    band,
    predicted_low_set,
    sample_alignment,
)
from lolg_tex_micro_mixed_value_payload_state_opcode_probe import int_value, ratio, write_csv


DEFAULT_OUTPUT = Path("output/tex_gradient_sequence_high_safe_low_exception_row_family")

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "same_bucket_alignments",
    "same_bucket_false_free_alignments",
    "family_kinds",
    "family_rows",
    "best_family_kind",
    "best_family_key",
    "best_correct_slots",
    "best_false_slots",
    "best_precision",
    "best_false_free_family_kind",
    "best_false_free_family_key",
    "best_false_free_correct_slots",
    "best_false_free_alignments",
    "best_false_free_target_rows",
    "best_false_free_source_rows",
    "robust_family_rows",
    "narrow_family_rows",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

FAMILY_FIELDNAMES = [
    "rank",
    "family_kind",
    "family_key",
    "alignments",
    "target_rows",
    "source_rows",
    "predicted_slots",
    "correct_slots",
    "false_slots",
    "unknown_slots",
    "precision",
    "coverage",
    "false_free_alignments",
    "false_free_slots",
    "predicted_lows",
    "sample_alignment",
    "sample_false",
    "verdict",
]

FALSE_FREE_FIELDNAMES = [
    "rank",
    "family_kind",
    "family_key",
    "alignments",
    "target_rows",
    "source_rows",
    "correct_slots",
    "predicted_lows",
    "sample_alignment",
    "verdict",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def same_bucket_alignments(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [row for row in rows if row.get("mode") == "same_bucket"]


def false_free_alignment(row: dict[str, str]) -> bool:
    return int_value(row, "correct_slots") > 0 and int_value(row, "false_slots") == 0


def row_family_values(row: dict[str, str]) -> dict[str, str]:
    target_frontier = int_value(row, "target_frontier_id")
    source_frontier = int_value(row, "source_frontier_id")
    target_start = int_value(row, "target_start")
    source_start = int_value(row, "source_start")
    shift = int_value(row, "shift")
    target_mod = target_start % 320
    source_mod = source_start % 320
    target_band = band(target_start, 320)
    source_band = band(source_start, 320)
    predicted = predicted_low_set(row)
    return {
        "target_profile_shift": f"{target_frontier}|m{target_mod}|sh={shift}",
        "source_profile_shift": f"{source_frontier}|m{source_mod}|sh={shift}",
        "profile_pair": f"{target_frontier}|m{target_mod}->{source_frontier}|m{source_mod}",
        "profile_pair_shift": f"{target_frontier}|m{target_mod}->{source_frontier}|m{source_mod}|sh={shift}",
        "frontier_band_pair_shift": f"{target_frontier}|{target_band}->{source_frontier}|{source_band}|sh={shift}",
        "mod_pair_shift": f"{target_mod}->{source_mod}|sh={shift}",
        "target_profile_source_frontier_shift": f"{target_frontier}|m{target_mod}->{source_frontier}|sh={shift}",
        "source_profile_target_frontier_shift": f"{target_frontier}->{source_frontier}|m{source_mod}|sh={shift}",
        "pred_profile_pair_shift": (
            f"{predicted}|{target_frontier}|m{target_mod}->{source_frontier}|m{source_mod}|sh={shift}"
        ),
        "pred_mod_pair_shift": f"{predicted}|{target_mod}->{source_mod}|sh={shift}",
    }


def family_verdict(row: dict[str, object]) -> str:
    correct = int_value(row, "correct_slots")
    false = int_value(row, "false_slots")
    target_rows = int_value(row, "target_rows")
    source_rows = int_value(row, "source_rows")
    if false == 0 and correct >= 8 and target_rows >= 3 and source_rows >= 2:
        return "robust_row_family_review"
    if false == 0 and correct > 0:
        return "narrow_row_family"
    if correct > false:
        return "partial_row_family_hint"
    if correct > 0:
        return "conflicted_row_family"
    return "empty_row_family"


def build_family_rows(alignments: list[dict[str, str]]) -> list[dict[str, object]]:
    candidate_keys: dict[str, set[str]] = defaultdict(set)
    for alignment in alignments:
        if not false_free_alignment(alignment):
            continue
        for kind, key in row_family_values(alignment).items():
            candidate_keys[kind].add(key)

    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for alignment in alignments:
        values = row_family_values(alignment)
        for kind, keys in candidate_keys.items():
            key = values[kind]
            if key in keys:
                grouped[(kind, key)].append(alignment)

    rows: list[dict[str, object]] = []
    for (kind, key), members in grouped.items():
        correct = sum(int_value(row, "correct_slots") for row in members)
        false = sum(int_value(row, "false_slots") for row in members)
        predicted = sum(int_value(row, "predicted_slots") for row in members)
        unknown = sum(int_value(row, "unknown_slots") for row in members)
        false_free_members = [row for row in members if false_free_alignment(row)]
        lows = Counter()
        for row in members:
            for part in row.get("predicted_lows", "").split("|"):
                if not part:
                    continue
                low, _, count = part.partition(":")
                lows[low] += int(count or 0)
        best_alignment = max(members, key=lambda row: int_value(row, "correct_slots"), default={})
        family_row = {
            "rank": 0,
            "family_kind": kind,
            "family_key": key,
            "alignments": len(members),
            "target_rows": len({row.get("target_row_id", "") for row in members}),
            "source_rows": len({row.get("source_row_id", "") for row in members}),
            "predicted_slots": predicted,
            "correct_slots": correct,
            "false_slots": false,
            "unknown_slots": unknown,
            "precision": ratio(correct, correct + false),
            "coverage": ratio(predicted, predicted + unknown),
            "false_free_alignments": len(false_free_members),
            "false_free_slots": sum(int_value(row, "correct_slots") for row in false_free_members),
            "predicted_lows": "|".join(f"{low}:{count}" for low, count in lows.most_common()),
            "sample_alignment": sample_alignment(best_alignment) if best_alignment else "",
            "sample_false": next((row.get("sample_false", "") for row in members if row.get("sample_false", "")), ""),
        }
        family_row["verdict"] = family_verdict(family_row)
        rows.append(family_row)

    rows.sort(
        key=lambda row: (
            int_value(row, "false_slots") != 0,
            -int_value(row, "correct_slots"),
            -int_value(row, "target_rows"),
            -int_value(row, "source_rows"),
            str(row.get("family_kind", "")),
            str(row.get("family_key", "")),
        )
    )
    for index, row in enumerate(rows, start=1):
        row["rank"] = index
    return rows


def best_family(rows: list[dict[str, object]]) -> dict[str, object]:
    return max(
        rows,
        key=lambda row: (
            int_value(row, "correct_slots"),
            -int_value(row, "false_slots"),
            int_value(row, "target_rows"),
            int_value(row, "source_rows"),
        ),
        default={},
    )


def best_false_free_family(rows: list[dict[str, object]]) -> dict[str, object]:
    candidates = [
        row
        for row in rows
        if int_value(row, "correct_slots") > 0 and int_value(row, "false_slots") == 0
    ]
    return max(
        candidates,
        key=lambda row: (
            int_value(row, "correct_slots"),
            int_value(row, "alignments"),
            int_value(row, "target_rows"),
            int_value(row, "source_rows"),
        ),
        default={},
    )


def build_false_free_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    output = [
        {
            "rank": row["rank"],
            "family_kind": row["family_kind"],
            "family_key": row["family_key"],
            "alignments": row["alignments"],
            "target_rows": row["target_rows"],
            "source_rows": row["source_rows"],
            "correct_slots": row["correct_slots"],
            "predicted_lows": row["predicted_lows"],
            "sample_alignment": row["sample_alignment"],
            "verdict": row["verdict"],
        }
        for row in rows
        if int_value(row, "correct_slots") > 0 and int_value(row, "false_slots") == 0
    ]
    output.sort(
        key=lambda row: (
            -int_value(row, "correct_slots"),
            -int_value(row, "alignments"),
            str(row.get("family_kind", "")),
        )
    )
    for index, row in enumerate(output, start=1):
        row["rank"] = index
    return output


def build_summary(alignments: list[dict[str, str]], families: list[dict[str, object]]) -> dict[str, object]:
    false_free = [row for row in alignments if false_free_alignment(row)]
    best = best_family(families)
    best_ff = best_false_free_family(families)
    robust = [row for row in families if row.get("verdict") == "robust_row_family_review"]
    narrow = [row for row in families if row.get("verdict") == "narrow_row_family"]
    return {
        "scope": "total",
        "candidate_mode": "low_exception_row_family_support",
        "same_bucket_alignments": len(alignments),
        "same_bucket_false_free_alignments": len(false_free),
        "family_kinds": len({row.get("family_kind", "") for row in families}),
        "family_rows": len(families),
        "best_family_kind": best.get("family_kind", ""),
        "best_family_key": best.get("family_key", ""),
        "best_correct_slots": best.get("correct_slots", 0),
        "best_false_slots": best.get("false_slots", 0),
        "best_precision": best.get("precision", "0.000000"),
        "best_false_free_family_kind": best_ff.get("family_kind", ""),
        "best_false_free_family_key": best_ff.get("family_key", ""),
        "best_false_free_correct_slots": best_ff.get("correct_slots", 0),
        "best_false_free_alignments": best_ff.get("alignments", 0),
        "best_false_free_target_rows": best_ff.get("target_rows", 0),
        "best_false_free_source_rows": best_ff.get("source_rows", 0),
        "robust_family_rows": len(robust),
        "narrow_family_rows": len(narrow),
        "promotion_candidate_bytes": best_ff.get("correct_slots", 0),
        "promotion_ready_bytes": 0,
        "issue_rows": 0,
    }


def build(alignment_rows: list[dict[str, str]]) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    alignments = same_bucket_alignments(alignment_rows)
    families = build_family_rows(alignments)
    false_free = build_false_free_rows(families)
    summary = build_summary(alignments, families)
    return summary, families, false_free


def render_table(rows: list[dict[str, object]], fields: list[str], limit: int = 240) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, object],
    families: list[dict[str, object]],
    false_free: list[dict[str, object]],
    title: str,
) -> str:
    data_json = json.dumps(
        {"summary": summary, "families": families, "false_free_families": false_free},
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
table {{ border-collapse: collapse; width: 100%; min-width: 2100px; }}
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
  <div class="box"><div class="num">{summary['same_bucket_false_free_alignments']}</div><div class="muted">false-free alignments</div></div>
  <div class="box"><div class="num">{summary['best_false_free_correct_slots']}</div><div class="muted">best family false-free slots</div></div>
  <div class="box"><div class="num">{summary['robust_family_rows']}</div><div class="muted">robust row families</div></div>
  <div class="box"><div class="num">{summary['narrow_family_rows']}</div><div class="muted">narrow row families</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>False-free families</h2>{render_table(false_free, FALSE_FREE_FIELDNAMES)}</div>
<div class="panel"><h2>Families</h2>{render_table(families, FAMILY_FIELDNAMES)}</div>
<script type="application/json" id="gradient-sequence-high-safe-low-exception-row-family-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe row-family support for low-exception alignments.")
    parser.add_argument("--alignments", type=Path, default=DEFAULT_ALIGNMENTS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Gradient Sequence High-Safe Low Exception Row-Family Probe",
    )
    args = parser.parse_args()

    summary, families, false_free = build(read_csv(args.alignments))
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "families.csv", FAMILY_FIELDNAMES, families)
    write_csv(args.output / "false_free_families.csv", FALSE_FREE_FIELDNAMES, false_free)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, families, false_free, args.title))

    print(f"Same-bucket alignments: {summary['same_bucket_alignments']}")
    print(f"False-free alignments: {summary['same_bucket_false_free_alignments']}")
    print(
        "Best row-family false-free: "
        f"{summary['best_false_free_family_kind']} / {summary['best_false_free_family_key']} = "
        f"{summary['best_false_free_correct_slots']} slots"
    )
    print(f"Robust row families: {summary['robust_family_rows']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
