#!/usr/bin/env python3
"""Review false-free low-exception alignments for reusable selector families."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_micro_mixed_value_payload_state_opcode_probe import int_value, ratio, write_csv


DEFAULT_ALIGNMENTS = Path("output/tex_gradient_sequence_high_safe_low_exception_alignment/alignments.csv")
DEFAULT_OUTPUT = Path("output/tex_gradient_sequence_high_safe_low_exception_alignment_review")

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "same_bucket_alignments",
    "same_bucket_false_free_alignments",
    "same_bucket_false_free_slots",
    "selector_families",
    "selector_rows",
    "nonrow_selector_rows",
    "best_selector_family",
    "best_selector_key",
    "best_selector_correct_slots",
    "best_selector_false_slots",
    "best_selector_precision",
    "best_false_free_family",
    "best_false_free_key",
    "best_false_free_correct_slots",
    "best_false_free_alignments",
    "best_nonrow_false_free_family",
    "best_nonrow_false_free_key",
    "best_nonrow_false_free_correct_slots",
    "best_nonrow_false_free_alignments",
    "best_nonrow_false_free_target_rows",
    "best_nonrow_false_free_source_rows",
    "broad_false_free_selector_rows",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

SELECTOR_FIELDNAMES = [
    "rank",
    "selector_family",
    "selector_key",
    "is_row_keyed",
    "alignments",
    "target_rows",
    "source_rows",
    "predicted_slots",
    "correct_slots",
    "false_slots",
    "unknown_slots",
    "precision",
    "false_free_alignments",
    "false_free_slots",
    "best_alignment_rank",
    "best_alignment_correct_slots",
    "predicted_lows",
    "sample_alignment",
    "sample_false",
    "verdict",
]

FALSE_FREE_FIELDNAMES = [
    "rank",
    "selector_family",
    "selector_key",
    "is_row_keyed",
    "alignments",
    "target_rows",
    "source_rows",
    "correct_slots",
    "predicted_lows",
    "sample_alignment",
    "verdict",
]

ROW_KEYED_FAMILIES = {"exact_alignment", "row_pair", "row_pair_shift"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def band(value: int, step: int) -> str:
    base = (value // step) * step
    return f"{base}-{base + step - 1}"


def predicted_low_set(row: dict[str, str]) -> str:
    lows = sorted(part.split(":", 1)[0] for part in row.get("predicted_lows", "").split("|") if part)
    return "|".join(lows)


def selector_values(row: dict[str, str]) -> dict[str, str]:
    target_frontier = int_value(row, "target_frontier_id")
    source_frontier = int_value(row, "source_frontier_id")
    target_start = int_value(row, "target_start")
    source_start = int_value(row, "source_start")
    shift = int_value(row, "shift")
    predicted = predicted_low_set(row)
    return {
        "exact_alignment": f"{row.get('target_row_id', '')}|{row.get('source_row_id', '')}|sh={shift}",
        "row_pair": f"{row.get('target_row_id', '')}|{row.get('source_row_id', '')}",
        "row_pair_shift": f"{row.get('target_row_id', '')}|{row.get('source_row_id', '')}|sh={shift}",
        "shift": str(shift),
        "frontier_pair": f"{target_frontier}->{source_frontier}",
        "frontier_pair_shift": f"{target_frontier}->{source_frontier}|sh={shift}",
        "frontier_delta_shift": f"{target_frontier - source_frontier}|sh={shift}",
        "start_delta_shift": f"{target_start - source_start}|sh={shift}",
        "start_delta_band64_shift": f"{band(target_start - source_start, 64)}|sh={shift}",
        "target_start_mod320_shift": f"{target_start % 320}|sh={shift}",
        "source_start_mod320_shift": f"{source_start % 320}|sh={shift}",
        "start_mod_pair_shift": f"{target_start % 320}->{source_start % 320}|sh={shift}",
        "target_frontier_start_shift": f"{target_frontier}|{target_start % 320}|sh={shift}",
        "source_frontier_start_shift": f"{source_frontier}|{source_start % 320}|sh={shift}",
        "pred_low_shift": f"{predicted}|sh={shift}",
        "pred_low_frontier_pair_shift": f"{predicted}|{target_frontier}->{source_frontier}|sh={shift}",
        "pred_low_start_mod_pair_shift": f"{predicted}|{target_start % 320}->{source_start % 320}|sh={shift}",
    }


def same_bucket_alignments(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [row for row in rows if row.get("mode") == "same_bucket"]


def false_free_alignment(row: dict[str, str]) -> bool:
    return int_value(row, "correct_slots") > 0 and int_value(row, "false_slots") == 0


def sample_alignment(row: dict[str, str]) -> str:
    return (
        f"rank={row.get('rank', '')};shift={row.get('shift', '')};"
        f"target={row.get('target_frontier_id', '')}:{row.get('target_start', '')};"
        f"source={row.get('source_frontier_id', '')}:{row.get('source_start', '')}"
    )


def selector_verdict(row: dict[str, object]) -> str:
    correct = int_value(row, "correct_slots")
    false = int_value(row, "false_slots")
    alignments = int_value(row, "alignments")
    target_rows = int_value(row, "target_rows")
    source_rows = int_value(row, "source_rows")
    is_row_keyed = str(row.get("is_row_keyed", "")) == "1"
    if false == 0 and correct >= 8 and not is_row_keyed and target_rows >= 3 and source_rows >= 3:
        return "broad_false_free_selector_review"
    if false == 0 and correct > 0 and not is_row_keyed:
        return "narrow_false_free_selector"
    if false == 0 and correct > 0:
        return "row_keyed_false_free_selector"
    if correct > false:
        return "partial_selector_hint"
    if alignments > 0:
        return "conflicted_selector"
    return "empty_selector"


def build_selectors(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    false_free_rows = [row for row in rows if false_free_alignment(row)]
    candidate_keys: dict[str, set[str]] = defaultdict(set)
    for row in false_free_rows:
        for family, key in selector_values(row).items():
            candidate_keys[family].add(key)

    rows_by_selector: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        values = selector_values(row)
        for family, keys in candidate_keys.items():
            key = values[family]
            if key in keys:
                rows_by_selector[(family, key)].append(row)

    output: list[dict[str, object]] = []
    for (family, key), members in rows_by_selector.items():
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
        selector_row = {
            "rank": 0,
            "selector_family": family,
            "selector_key": key,
            "is_row_keyed": "1" if family in ROW_KEYED_FAMILIES else "0",
            "alignments": len(members),
            "target_rows": len({row.get("target_row_id", "") for row in members}),
            "source_rows": len({row.get("source_row_id", "") for row in members}),
            "predicted_slots": predicted,
            "correct_slots": correct,
            "false_slots": false,
            "unknown_slots": unknown,
            "precision": ratio(correct, correct + false),
            "false_free_alignments": len(false_free_members),
            "false_free_slots": sum(int_value(row, "correct_slots") for row in false_free_members),
            "best_alignment_rank": best_alignment.get("rank", ""),
            "best_alignment_correct_slots": best_alignment.get("correct_slots", ""),
            "predicted_lows": "|".join(f"{low}:{count}" for low, count in lows.most_common()),
            "sample_alignment": sample_alignment(best_alignment) if best_alignment else "",
            "sample_false": next((row.get("sample_false", "") for row in members if row.get("sample_false", "")), ""),
        }
        selector_row["verdict"] = selector_verdict(selector_row)
        output.append(selector_row)

    output.sort(
        key=lambda row: (
            int_value(row, "false_slots") != 0,
            str(row.get("is_row_keyed", "")) == "1",
            -int_value(row, "correct_slots"),
            -int_value(row, "alignments"),
            str(row.get("selector_family", "")),
            str(row.get("selector_key", "")),
        )
    )
    for index, row in enumerate(output, start=1):
        row["rank"] = index
    return output


def best_selector(rows: list[dict[str, object]]) -> dict[str, object]:
    return max(
        rows,
        key=lambda row: (
            int_value(row, "correct_slots"),
            -int_value(row, "false_slots"),
            int_value(row, "target_rows"),
            int_value(row, "source_rows"),
            str(row.get("is_row_keyed", "")) == "0",
        ),
        default={},
    )


def best_false_free_selector(rows: list[dict[str, object]], *, nonrow_only: bool = False) -> dict[str, object]:
    candidates = [
        row
        for row in rows
        if int_value(row, "correct_slots") > 0
        and int_value(row, "false_slots") == 0
        and (not nonrow_only or row.get("is_row_keyed") == "0")
    ]
    return max(
        candidates,
        key=lambda row: (
            int_value(row, "correct_slots"),
            int_value(row, "alignments"),
            int_value(row, "target_rows"),
            int_value(row, "source_rows"),
            -int_value(row, "rank"),
        ),
        default={},
    )


def build_false_free_rows(selectors: list[dict[str, object]]) -> list[dict[str, object]]:
    rows = [
        {
            "rank": selector["rank"],
            "selector_family": selector["selector_family"],
            "selector_key": selector["selector_key"],
            "is_row_keyed": selector["is_row_keyed"],
            "alignments": selector["alignments"],
            "target_rows": selector["target_rows"],
            "source_rows": selector["source_rows"],
            "correct_slots": selector["correct_slots"],
            "predicted_lows": selector["predicted_lows"],
            "sample_alignment": selector["sample_alignment"],
            "verdict": selector["verdict"],
        }
        for selector in selectors
        if int_value(selector, "correct_slots") > 0 and int_value(selector, "false_slots") == 0
    ]
    rows.sort(
        key=lambda row: (
            str(row.get("is_row_keyed", "")) == "1",
            -int_value(row, "correct_slots"),
            -int_value(row, "alignments"),
            str(row.get("selector_family", "")),
        )
    )
    for index, row in enumerate(rows, start=1):
        row["rank"] = index
    return rows


def build_summary(alignments: list[dict[str, str]], selectors: list[dict[str, object]]) -> dict[str, object]:
    false_free_alignments = [row for row in alignments if false_free_alignment(row)]
    best = best_selector(selectors)
    false_free = best_false_free_selector(selectors)
    nonrow_false_free = best_false_free_selector(selectors, nonrow_only=True)
    broad_false_free = [
        row
        for row in selectors
        if row.get("verdict") == "broad_false_free_selector_review"
    ]
    return {
        "scope": "total",
        "candidate_mode": "same_bucket_false_free_selector_review",
        "same_bucket_alignments": len(alignments),
        "same_bucket_false_free_alignments": len(false_free_alignments),
        "same_bucket_false_free_slots": sum(int_value(row, "correct_slots") for row in false_free_alignments),
        "selector_families": len({row.get("selector_family", "") for row in selectors}),
        "selector_rows": len(selectors),
        "nonrow_selector_rows": sum(1 for row in selectors if row.get("is_row_keyed") == "0"),
        "best_selector_family": best.get("selector_family", ""),
        "best_selector_key": best.get("selector_key", ""),
        "best_selector_correct_slots": best.get("correct_slots", 0),
        "best_selector_false_slots": best.get("false_slots", 0),
        "best_selector_precision": best.get("precision", "0.000000"),
        "best_false_free_family": false_free.get("selector_family", ""),
        "best_false_free_key": false_free.get("selector_key", ""),
        "best_false_free_correct_slots": false_free.get("correct_slots", 0),
        "best_false_free_alignments": false_free.get("alignments", 0),
        "best_nonrow_false_free_family": nonrow_false_free.get("selector_family", ""),
        "best_nonrow_false_free_key": nonrow_false_free.get("selector_key", ""),
        "best_nonrow_false_free_correct_slots": nonrow_false_free.get("correct_slots", 0),
        "best_nonrow_false_free_alignments": nonrow_false_free.get("alignments", 0),
        "best_nonrow_false_free_target_rows": nonrow_false_free.get("target_rows", 0),
        "best_nonrow_false_free_source_rows": nonrow_false_free.get("source_rows", 0),
        "broad_false_free_selector_rows": len(broad_false_free),
        "promotion_candidate_bytes": nonrow_false_free.get("correct_slots", 0),
        "promotion_ready_bytes": 0,
        "issue_rows": 0,
    }


def build(alignment_rows: list[dict[str, str]]) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    alignments = same_bucket_alignments(alignment_rows)
    selectors = build_selectors(alignments)
    false_free = build_false_free_rows(selectors)
    summary = build_summary(alignments, selectors)
    return summary, selectors, false_free


def render_table(rows: list[dict[str, object]], fields: list[str], limit: int = 240) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, object],
    selectors: list[dict[str, object]],
    false_free: list[dict[str, object]],
    title: str,
) -> str:
    data_json = json.dumps(
        {"summary": summary, "selectors": selectors, "false_free_selectors": false_free},
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
  <div class="box"><div class="num">{summary['same_bucket_false_free_slots']}</div><div class="muted">false-free alignment slots</div></div>
  <div class="box"><div class="num">{summary['best_nonrow_false_free_correct_slots']}</div><div class="muted">best non-row false-free slots</div></div>
  <div class="box"><div class="num">{summary['broad_false_free_selector_rows']}</div><div class="muted">broad false-free selectors</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>False-free selectors</h2>{render_table(false_free, FALSE_FREE_FIELDNAMES)}</div>
<div class="panel"><h2>Selectors</h2>{render_table(selectors, SELECTOR_FIELDNAMES)}</div>
<script type="application/json" id="gradient-sequence-high-safe-low-exception-alignment-review-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Review false-free low-exception alignment selectors.")
    parser.add_argument("--alignments", type=Path, default=DEFAULT_ALIGNMENTS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Gradient Sequence High-Safe Low Exception Alignment Review",
    )
    args = parser.parse_args()

    summary, selectors, false_free = build(read_csv(args.alignments))
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "selectors.csv", SELECTOR_FIELDNAMES, selectors)
    write_csv(args.output / "false_free_selectors.csv", FALSE_FREE_FIELDNAMES, false_free)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, selectors, false_free, args.title))

    print(f"Same-bucket alignments: {summary['same_bucket_alignments']}")
    print(f"False-free alignments: {summary['same_bucket_false_free_alignments']}")
    print(
        "Best non-row false-free selector: "
        f"{summary['best_nonrow_false_free_family']} / {summary['best_nonrow_false_free_key']} = "
        f"{summary['best_nonrow_false_free_correct_slots']} slots"
    )
    print(f"Broad false-free selectors: {summary['broad_false_free_selector_rows']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
