#!/usr/bin/env python3
"""Review guarded source-byte predictions for known-terminal high-safe chains."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_opcode_probe import relative_href, write_csv
from lolg_tex_micro_mixed_value_payload_state_opcode_probe import int_value


DEFAULT_SLOTS = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_bucket_split_guard_final_known_guard_promoted_replay/slots.csv"
)
DEFAULT_OUTPUT = Path("output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard")

FORMULAS = {
    "target_high+bucket_split_prediction": ("target_high", "bucket_split_prediction", 0),
    "target_high+source_slot_target_low": ("target_high", "source_slot_target_low", 0),
    "target_high+target_low": ("target_high", "target_low", 0),
    "6+best_fixed_low_predicted_low": ("6", "best_fixed_low_predicted_low", 0),
    "6+bucket_split_prediction": ("6", "bucket_split_prediction", 0),
    "6+source_slot_target_low": ("6", "source_slot_target_low", 0),
    "6+target_low": ("6", "target_low", 0),
}

FEATURE_SETS = [
    ("start", "rel_mod4"),
    ("frontier_id", "rel_mod4"),
    ("rel_mod16", "target_mod32"),
    ("rel_mod4", "target_mod32"),
    ("rel_mod8", "target_mod32"),
    ("seq_index", "target_mod32"),
    ("source_slot_frontier_id",),
    ("source_slot_start",),
    ("source_slot_frontier_id", "source_slot_start"),
    ("source_slot_frontier_id", "source_slot_target_low"),
    ("source_same_bucket", "gradient_class", "prev_low2"),
    ("source_same_low", "bucket_split_prediction", "gradient_class"),
    ("target_low", "bucket_split_prediction", "gradient_class"),
]

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "slot_rows",
    "source_rows",
    "unknown_source_rows",
    "known_source_rows",
    "guard_rows",
    "best_formula",
    "best_guard_family",
    "best_guard_key",
    "best_unknown_exact_rows",
    "best_unknown_false_rows",
    "best_known_exact_rows",
    "best_known_false_rows",
    "review_verdict",
    "next_probe",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

GUARD_FIELDNAMES = [
    "rank",
    "formula",
    "guard_family",
    "guard_key",
    "unknown_exact_rows",
    "unknown_false_rows",
    "known_exact_rows",
    "known_false_rows",
    "verdict",
]

TARGET_FIELDNAMES = [
    "rank",
    "slot_rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "span_index",
    "op_index",
    "target_offset",
    "source_offset",
    "relative_offset",
    "expected_byte",
    "predicted_byte",
    "root_target_byte",
    "root_target_low",
    "source_slot_rank",
    "source_slot_frontier_id",
    "source_slot_start",
    "source_dependency_edge",
    "best_formula",
    "best_guard_family",
    "best_guard_key",
    "promotion_ready",
    "issues",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def nibble(value: str) -> int | None:
    if len(value) != 1 or value == "NA":
        return None
    try:
        return int(value, 16)
    except ValueError:
        return None


def predicted_byte(row: dict[str, str], formula: str) -> str:
    high_spec, low_field, delta = FORMULAS[formula]
    high = high_spec if len(high_spec) == 1 else row.get(high_spec, "")
    low_value = nibble(row.get(low_field, ""))
    if len(high) != 1 or low_value is None:
        return ""
    return f"{high}{(low_value + delta) & 0x0F:x}".lower()


def source_dependency_edge(row: dict[str, str]) -> str:
    return (
        f"{row.get('frontier_id', '')}|{row.get('start', '')}->"
        f"{row.get('source_slot_frontier_id', '')}|{row.get('source_slot_start', '')}"
    )


def source_scope(row: dict[str, str]) -> bool:
    return (
        row.get("source_location") == "in_highsafe"
        and bool(row.get("source_slot_rank", ""))
        and bool(row.get("source_expected_byte", ""))
    )


def target_scope(row: dict[str, str]) -> bool:
    return source_scope(row) and row.get("source_availability") == "unknown_source"


def known_scope(row: dict[str, str]) -> bool:
    return source_scope(row) and row.get("source_availability") == "known_source"


def guard_key(row: dict[str, str], fields: tuple[str, ...]) -> str:
    return "+".join(f"{field}={row.get(field, '')}" for field in fields)


def guard_family(fields: tuple[str, ...]) -> str:
    return "+".join(fields)


def build_guard_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    guard_rows: list[dict[str, str]] = []
    for formula in FORMULAS:
        for fields in FEATURE_SETS:
            groups: dict[str, Counter[str]] = defaultdict(Counter)
            for row in rows:
                if not source_scope(row):
                    continue
                prediction = predicted_byte(row, formula)
                if not prediction:
                    continue
                key = guard_key(row, fields)
                exact = prediction == row.get("source_expected_byte", "").lower()
                if target_scope(row):
                    groups[key]["unknown_exact_rows" if exact else "unknown_false_rows"] += 1
                elif known_scope(row):
                    groups[key]["known_exact_rows" if exact else "known_false_rows"] += 1
            for key, counts in groups.items():
                if not counts:
                    continue
                verdict = "rejected_guard"
                if counts["unknown_exact_rows"] > 0 and counts["unknown_false_rows"] == 0 and counts["known_false_rows"] == 0:
                    verdict = "false_free_target_only_guard"
                    if counts["known_exact_rows"] > 0:
                        verdict = "promotion_ready_guard"
                guard_rows.append(
                    {
                        "rank": "",
                        "formula": formula,
                        "guard_family": guard_family(fields),
                        "guard_key": key,
                        "unknown_exact_rows": str(counts["unknown_exact_rows"]),
                        "unknown_false_rows": str(counts["unknown_false_rows"]),
                        "known_exact_rows": str(counts["known_exact_rows"]),
                        "known_false_rows": str(counts["known_false_rows"]),
                        "verdict": verdict,
                    }
                )
    guard_rows.sort(
        key=lambda row: (
            row.get("verdict") != "promotion_ready_guard",
            -int_value(row, "unknown_exact_rows"),
            -int_value(row, "known_exact_rows"),
            len(row.get("guard_family", "").split("+")),
            row.get("formula", ""),
            row.get("guard_key", ""),
        )
    )
    for index, row in enumerate(guard_rows, start=1):
        row["rank"] = str(index)
    return guard_rows


def select_guard(guard_rows: list[dict[str, str]]) -> dict[str, str]:
    for row in guard_rows:
        if row.get("verdict") == "promotion_ready_guard":
            return row
    return {}


def matches_guard(row: dict[str, str], guard: dict[str, str]) -> bool:
    fields = tuple(guard.get("guard_family", "").split("+"))
    return guard_key(row, fields) == guard.get("guard_key", "")


def review_verdict(guard: dict[str, str]) -> str:
    if not guard:
        return "missing_source_byte_guard"
    if int_value(guard, "known_exact_rows") <= 0:
        return "source_byte_guard_missing_known_support"
    if int_value(guard, "known_false_rows") > 0:
        return "source_byte_guard_known_false"
    if int_value(guard, "unknown_false_rows") > 0:
        return "source_byte_guard_unknown_false"
    if int_value(guard, "unknown_exact_rows") <= 0:
        return "source_byte_guard_no_targets"
    return "source_byte_guard_promotion_ready"


def next_probe_for(verdict: str) -> str:
    if verdict == "source_byte_guard_promotion_ready":
        return "promote guarded source bytes for known-terminal high-safe chains"
    if verdict == "source_byte_guard_missing_known_support":
        return "seek known support for guarded source-byte prediction"
    return "derive safer source-byte guard for known-terminal high-safe chains"


def build(slot_rows: list[dict[str, str]]) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    guard_rows = build_guard_rows(slot_rows)
    guard = select_guard(guard_rows)
    verdict = review_verdict(guard)
    target_rows: list[dict[str, str]] = []
    seen_target_keys: set[tuple[str, str, str, str]] = set()
    if guard:
        formula = guard.get("formula", "")
        for row in slot_rows:
            if not target_scope(row) or not matches_guard(row, guard):
                continue
            prediction = predicted_byte(row, formula)
            if not prediction:
                continue
            issues: list[str] = []
            if prediction != row.get("source_expected_byte", "").lower():
                issues.append("prediction_false")
            source_offset = row.get("source_actual_offset", "")
            target_key = (
                row.get("archive", ""),
                row.get("pcx_name", ""),
                row.get("frontier_id", ""),
                source_offset,
            )
            if target_key in seen_target_keys:
                continue
            seen_target_keys.add(target_key)
            target_rows.append(
                {
                    "rank": str(len(target_rows) + 1),
                    "slot_rank": row.get("rank", ""),
                    "archive": row.get("archive", ""),
                    "archive_tag": row.get("archive_tag", ""),
                    "pcx_name": row.get("pcx_name", ""),
                    "frontier_id": row.get("frontier_id", ""),
                    "span_index": row.get("span_index", ""),
                    "op_index": row.get("op_index", ""),
                    "target_offset": source_offset,
                    "source_offset": source_offset,
                    "relative_offset": row.get("relative_offset", ""),
                    "expected_byte": row.get("source_expected_byte", "").lower(),
                    "predicted_byte": prediction,
                    "root_target_byte": row.get("target_byte", ""),
                    "root_target_low": row.get("target_low", ""),
                    "source_slot_rank": row.get("source_slot_rank", ""),
                    "source_slot_frontier_id": row.get("source_slot_frontier_id", ""),
                    "source_slot_start": row.get("source_slot_start", ""),
                    "source_dependency_edge": source_dependency_edge(row),
                    "best_formula": formula,
                    "best_guard_family": guard.get("guard_family", ""),
                    "best_guard_key": guard.get("guard_key", ""),
                    "promotion_ready": "1" if verdict == "source_byte_guard_promotion_ready" and not issues else "0",
                    "issues": ";".join(issues),
                }
            )
    promotion_ready = (
        len(target_rows)
        if verdict == "source_byte_guard_promotion_ready" and not any(row.get("issues") for row in target_rows)
        else 0
    )
    summary = {
        "scope": "total",
        "candidate_mode": "high_safe_low_exception_source_byte_guard_review",
        "slot_rows": str(len(slot_rows)),
        "source_rows": str(sum(1 for row in slot_rows if source_scope(row))),
        "unknown_source_rows": str(sum(1 for row in slot_rows if target_scope(row))),
        "known_source_rows": str(sum(1 for row in slot_rows if known_scope(row))),
        "guard_rows": str(len(guard_rows)),
        "best_formula": guard.get("formula", ""),
        "best_guard_family": guard.get("guard_family", ""),
        "best_guard_key": guard.get("guard_key", ""),
        "best_unknown_exact_rows": guard.get("unknown_exact_rows", "0"),
        "best_unknown_false_rows": guard.get("unknown_false_rows", "0"),
        "best_known_exact_rows": guard.get("known_exact_rows", "0"),
        "best_known_false_rows": guard.get("known_false_rows", "0"),
        "review_verdict": verdict,
        "next_probe": next_probe_for(verdict),
        "promotion_candidate_bytes": str(len(target_rows)),
        "promotion_ready_bytes": str(promotion_ready),
        "issue_rows": str(sum(1 for row in target_rows if row.get("issues"))),
    }
    return summary, guard_rows, target_rows


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 200) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    guard_rows: list[dict[str, str]],
    target_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "guards": guard_rows, "targets": target_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("guards.csv", output_dir / "guards.csv"),
            ("targets.csv", output_dir / "targets.csv"),
        )
    )
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body {{ margin: 2rem; background: #111416; color: #edf5f4; font: 14px/1.45 system-ui, sans-serif; }}
table {{ border-collapse: collapse; width: 100%; min-width: 1500px; }}
th, td {{ border: 1px solid #31424a; padding: .45rem .55rem; vertical-align: top; }}
th {{ color: #9dafb5; background: #172023; text-align: left; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: .75rem; margin: 1rem 0; }}
.box {{ border: 1px solid #31424a; background: #172023; padding: .75rem; }}
.num {{ font-size: 1.35rem; font-weight: 750; }}
.muted {{ color: #9dafb5; }}
.panel {{ overflow-x: auto; margin-top: 1rem; }}
a {{ color: #77d3b1; text-decoration: none; margin-right: .75rem; }}
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<div class="grid">
  <div class="box"><div class="num">{summary['review_verdict']}</div><div class="muted">verdict</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready source bytes</div></div>
  <div class="box"><div class="num">{summary['best_unknown_exact_rows']}/{summary['best_unknown_false_rows']}</div><div class="muted">unknown exact/false</div></div>
  <div class="box"><div class="num">{summary['best_known_exact_rows']}/{summary['best_known_false_rows']}</div><div class="muted">known support exact/false</div></div>
</div>
<p>{links}</p>
<div class="panel"><h2>Targets</h2>{render_table(target_rows, TARGET_FIELDNAMES)}</div>
<div class="panel"><h2>Guards</h2>{render_table(guard_rows, GUARD_FIELDNAMES)}</div>
<script type="application/json" id="source-byte-guard-review-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slots", type=Path, default=DEFAULT_SLOTS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Source Byte Guard Review")
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    summary, guard_rows, target_rows = build(read_csv(args.slots))
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "guards.csv", GUARD_FIELDNAMES, guard_rows)
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, target_rows)
    (args.output / "index.html").write_text(
        build_html(summary, guard_rows, target_rows, args.output, args.title),
        encoding="utf-8",
    )
    print(
        "Source-byte guard review: "
        f"verdict={summary['review_verdict']} "
        f"formula={summary['best_formula']} "
        f"guard={summary['best_guard_key']} "
        f"known={summary['best_known_exact_rows']}/{summary['best_known_false_rows']} "
        f"unknown={summary['best_unknown_exact_rows']}/{summary['best_unknown_false_rows']} "
        f"promotion_ready={summary['promotion_ready_bytes']} "
        f"issues={summary['issue_rows']}"
    )
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
