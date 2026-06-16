#!/usr/bin/env python3
"""Split noisy .tex micro-token rows into conservative grammar families."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path


DEFAULT_TARGETS = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_micro_token_probe/targets.csv")
DEFAULT_OUTPUT = Path("output/tex_micro_token_family_split")

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "target_bytes",
    "family_rows",
    "clean_family_rows",
    "clean_family_bytes",
    "ambiguous_rows",
    "ambiguous_bytes",
    "existing_disagreement_rows",
    "existing_disagreement_bytes",
    "top_family",
    "top_family_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

ROW_FIELDNAMES = [
    "rank",
    "archive",
    "pcx_name",
    "frontier_id",
    "span_index",
    "op_index",
    "length",
    "start",
    "end",
    "source_classification",
    "micro_class",
    "split_family",
    "confidence",
    "reason",
    "small_delta_ratio",
    "jump_delta_ratio",
    "zero_delta_ratio",
    "step_delta_ratio",
    "top_nibble",
    "top_nibble_ratio",
    "dominant_byte_hex",
    "dominant_ratio",
    "control_ref_offset",
    "control_ref_mod64",
    "signed_shape_key",
    "transition_profile_key",
    "verdict",
]

FAMILY_FIELDNAMES = [
    "rank",
    "split_family",
    "rows",
    "bytes",
    "clean_rows",
    "clean_bytes",
    "ambiguous_rows",
    "ambiguous_bytes",
    "existing_classes",
    "source_classes",
    "top_nibbles",
    "sample_pcx",
    "sample_frontier_id",
    "verdict",
]

CONFLICT_FIELDNAMES = [
    "rank",
    "micro_class",
    "split_family",
    "rows",
    "bytes",
    "sample_pcx",
    "sample_frontier_id",
    "reason",
    "verdict",
]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def int_value(row: dict[str, str] | dict[str, object], field: str) -> int:
    try:
        return int(row.get(field, "") or 0)
    except (TypeError, ValueError):
        return 0


def float_value(row: dict[str, str], field: str) -> float:
    try:
        return float(row.get(field, "") or 0)
    except ValueError:
        return 0.0


def short_key(value: str) -> str:
    if "|" in value:
        return value.split("|", 1)[0]
    return value


def choose_family(row: dict[str, str]) -> tuple[str, int, str]:
    micro_class = row.get("micro_class", "")
    source_class = row.get("source_classification", "")
    small_ratio = float_value(row, "small_delta_ratio")
    jump_ratio = float_value(row, "jump_delta_ratio")
    zero_ratio = float_value(row, "zero_delta_ratio")
    top_nibble = row.get("top_nibble", "")
    top_nibble_ratio = float_value(row, "top_nibble_ratio")
    dominant_ratio = float_value(row, "dominant_ratio")
    control_known = row.get("control_ref_offset", "") != "missing"

    if micro_class == "plateau_walk" or (zero_ratio >= 0.65 and jump_ratio <= 0.15):
        return "flat_plateau", 3 if zero_ratio >= 0.65 else 2, "plateau_or_zero_dominant"
    if micro_class in {"small_signed_walk", "banded_small_signed_walk"} or (
        small_ratio >= 0.90 and jump_ratio <= 0.08
    ):
        return "small_delta", 3 if small_ratio >= 0.95 and jump_ratio <= 0.05 else 2, "small_delta_dominant"
    if micro_class == "jump_mixed_walk" or jump_ratio >= 0.32:
        return "jump_mixed", 3 if jump_ratio >= 0.40 else 2, "jump_delta_dominant"
    if micro_class == "mixed_token_walk" or (top_nibble == "0x6" and top_nibble_ratio >= 0.50 and small_ratio < 0.90):
        return "mixed_value", 2 if control_known or dominant_ratio >= 0.15 else 1, "mixed_value_band"
    if source_class == "gradient_like" and small_ratio >= 0.80:
        return "gradient_residual", 1, "gradient_like_low_confidence"
    return "ambiguous", 0, "no_conservative_family"


def expected_family(micro_class: str) -> str:
    return {
        "plateau_walk": "flat_plateau",
        "small_signed_walk": "small_delta",
        "banded_small_signed_walk": "small_delta",
        "jump_mixed_walk": "jump_mixed",
        "mixed_token_walk": "mixed_value",
    }.get(micro_class, "ambiguous")


def build(target_rows: list[dict[str, str]]) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    rows: list[dict[str, object]] = []
    for target in target_rows:
        family, confidence, reason = choose_family(target)
        expected = expected_family(target.get("micro_class", ""))
        ambiguous = family == "ambiguous" or confidence <= 1
        disagreement = expected != "ambiguous" and family != expected
        rows.append(
            {
                "rank": len(rows) + 1,
                "archive": target.get("archive", ""),
                "pcx_name": target.get("pcx_name", ""),
                "frontier_id": target.get("frontier_id", ""),
                "span_index": target.get("span_index", ""),
                "op_index": target.get("op_index", ""),
                "length": target.get("length", ""),
                "start": target.get("start", ""),
                "end": target.get("end", ""),
                "source_classification": target.get("source_classification", ""),
                "micro_class": target.get("micro_class", ""),
                "split_family": family,
                "confidence": confidence,
                "reason": reason,
                "small_delta_ratio": target.get("small_delta_ratio", ""),
                "jump_delta_ratio": target.get("jump_delta_ratio", ""),
                "zero_delta_ratio": target.get("zero_delta_ratio", ""),
                "step_delta_ratio": target.get("step_delta_ratio", ""),
                "top_nibble": target.get("top_nibble", ""),
                "top_nibble_ratio": target.get("top_nibble_ratio", ""),
                "dominant_byte_hex": target.get("dominant_byte_hex", ""),
                "dominant_ratio": target.get("dominant_ratio", ""),
                "control_ref_offset": target.get("control_ref_offset", ""),
                "control_ref_mod64": target.get("control_ref_mod64", ""),
                "signed_shape_key": short_key(target.get("signed_shape_key", "")),
                "transition_profile_key": short_key(target.get("transition_profile_key", "")),
                "verdict": "split_family_disagreement"
                if disagreement
                else "split_family_ambiguous"
                if ambiguous
                else "split_family_clean",
            }
        )

    by_family: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        by_family[str(row["split_family"])].append(row)
    family_rows: list[dict[str, object]] = []
    for family, group in by_family.items():
        clean = [row for row in group if row["verdict"] == "split_family_clean"]
        ambiguous = [row for row in group if row["verdict"] != "split_family_clean"]
        family_rows.append(
            {
                "rank": 0,
                "split_family": family,
                "rows": len(group),
                "bytes": sum(int_value(row, "length") for row in group),
                "clean_rows": len(clean),
                "clean_bytes": sum(int_value(row, "length") for row in clean),
                "ambiguous_rows": len(ambiguous),
                "ambiguous_bytes": sum(int_value(row, "length") for row in ambiguous),
                "existing_classes": ";".join(sorted({str(row["micro_class"]) for row in group})),
                "source_classes": ";".join(sorted({str(row["source_classification"]) for row in group})),
                "top_nibbles": ";".join(f"{key}:{value}" for key, value in Counter(str(row["top_nibble"]) for row in group).most_common()),
                "sample_pcx": group[0]["pcx_name"],
                "sample_frontier_id": group[0]["frontier_id"],
                "verdict": "split_family_clean" if not ambiguous else "split_family_review",
            }
        )
    family_rows.sort(key=lambda row: (-int_value(row, "bytes"), str(row["split_family"])))
    for index, row in enumerate(family_rows, start=1):
        row["rank"] = index

    conflict_groups: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        if row["verdict"] != "split_family_clean":
            conflict_groups[(str(row["micro_class"]), str(row["split_family"]))].append(row)
    conflict_rows: list[dict[str, object]] = []
    for (micro_class, family), group in conflict_groups.items():
        conflict_rows.append(
            {
                "rank": 0,
                "micro_class": micro_class,
                "split_family": family,
                "rows": len(group),
                "bytes": sum(int_value(row, "length") for row in group),
                "sample_pcx": group[0]["pcx_name"],
                "sample_frontier_id": group[0]["frontier_id"],
                "reason": ";".join(sorted({str(row["reason"]) for row in group})),
                "verdict": "split_family_review",
            }
        )
    conflict_rows.sort(key=lambda row: (-int_value(row, "bytes"), str(row["micro_class"]), str(row["split_family"])))
    for index, row in enumerate(conflict_rows, start=1):
        row["rank"] = index

    clean_rows = [row for row in rows if row["verdict"] == "split_family_clean"]
    ambiguous_rows = [row for row in rows if row["verdict"] != "split_family_clean"]
    disagreement_rows = [row for row in rows if row["verdict"] == "split_family_disagreement"]
    top_family = family_rows[0] if family_rows else {}
    summary = {
        "scope": "total",
        "target_rows": len(rows),
        "target_bytes": sum(int_value(row, "length") for row in rows),
        "family_rows": len(family_rows),
        "clean_family_rows": len(clean_rows),
        "clean_family_bytes": sum(int_value(row, "length") for row in clean_rows),
        "ambiguous_rows": len(ambiguous_rows),
        "ambiguous_bytes": sum(int_value(row, "length") for row in ambiguous_rows),
        "existing_disagreement_rows": len(disagreement_rows),
        "existing_disagreement_bytes": sum(int_value(row, "length") for row in disagreement_rows),
        "top_family": top_family.get("split_family", ""),
        "top_family_bytes": top_family.get("bytes", 0),
        "promotion_ready_bytes": 0,
        "issue_rows": 0,
    }
    return summary, rows, family_rows, conflict_rows


def render_table(rows: list[dict[str, object]], fields: list[str], limit: int = 220) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, object],
    rows: list[dict[str, object]],
    families: list[dict[str, object]],
    conflicts: list[dict[str, object]],
    title: str,
) -> str:
    data_json = json.dumps(
        {"summary": summary, "rows": rows, "families": families, "conflicts": conflicts},
        indent=2,
        sort_keys=True,
    )
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body {{ margin: 2rem; background: #111416; color: #edf5f4; font: 14px/1.45 system-ui, sans-serif; }}
table {{ border-collapse: collapse; width: 100%; min-width: 1600px; }}
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
  <div class="box"><div class="num">{summary['target_bytes']}</div><div class="muted">target bytes</div></div>
  <div class="box"><div class="num">{summary['clean_family_bytes']}</div><div class="muted">clean family bytes</div></div>
  <div class="box"><div class="num">{summary['ambiguous_bytes']}</div><div class="muted">ambiguous bytes</div></div>
  <div class="box"><div class="num">{summary['top_family']}</div><div class="muted">top family</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Families</h2>{render_table(families, FAMILY_FIELDNAMES)}</div>
<div class="panel"><h2>Conflicts</h2>{render_table(conflicts, CONFLICT_FIELDNAMES)}</div>
<div class="panel"><h2>Rows</h2>{render_table(rows, ROW_FIELDNAMES)}</div>
<script type="application/json" id="micro-token-family-split-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Split noisy .tex micro-token rows into grammar families.")
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Micro Token Family Split")
    args = parser.parse_args()

    summary, rows, families, conflicts = build(read_rows(args.targets))
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "rows.csv", ROW_FIELDNAMES, rows)
    write_csv(args.output / "families.csv", FAMILY_FIELDNAMES, families)
    write_csv(args.output / "conflicts.csv", CONFLICT_FIELDNAMES, conflicts)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, rows, families, conflicts, args.title))

    print(f"Target bytes: {summary['target_bytes']}")
    print(f"Clean family bytes: {summary['clean_family_bytes']}")
    print(f"Ambiguous bytes: {summary['ambiguous_bytes']}")
    print(f"Existing disagreement bytes: {summary['existing_disagreement_bytes']}")
    print(f"Top family: {summary['top_family']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
