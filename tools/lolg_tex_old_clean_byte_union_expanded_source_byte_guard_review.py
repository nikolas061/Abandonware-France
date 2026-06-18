#!/usr/bin/env python3
"""Review narrow expanded source-byte guards after the old-clean byte union replay."""

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
    "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_old_clean_byte_union_promoted_replay/slots.csv"
)
DEFAULT_OUTPUT = Path("output/tex_old_clean_byte_union_expanded_source_byte_guard_review")

FORMULAS = {
    "prefix_high+source_prefix_low-5": ("prefix_high", "source_prefix_low", -5),
    "source_prefix_high+prefix_low+2": ("source_prefix_high", "prefix_low", 2),
}

FEATURE_SETS = [
    ("source_slot_frontier_id", "rel_mod8", "bucket_split_context"),
    ("source_slot_frontier_id", "source_rel_mod8", "bucket_split_context"),
    ("source_slot_frontier_id", "rel_mod8", "source_fragment_low"),
    ("source_target_low", "rel_mod4", "bucket_split_context"),
    ("source_target_low", "target_low", "rel_mod4"),
]

SOURCE_FIELDS = [
    "target_byte",
    "target_high",
    "target_low",
    "prev_low1",
    "prev_low2",
    "rel_mod4",
    "rel_mod8",
    "seq_index",
    "prefix_byte",
    "prefix_low",
    "fragment_byte",
    "fragment_low",
    "frontier_id",
    "start",
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
    if len(value) != 1:
        return None
    try:
        return int(value, 16)
    except ValueError:
        return None


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


def source_dependency_edge(row: dict[str, str]) -> str:
    return (
        f"{row.get('frontier_id', '')}|{row.get('start', '')}->"
        f"{row.get('source_slot_frontier_id', '')}|{row.get('source_slot_start', '')}"
    )


def guard_key(row: dict[str, str], fields: tuple[str, ...]) -> str:
    return "+".join(f"{field}={row.get(field, '')}" for field in fields)


def guard_family(fields: tuple[str, ...]) -> str:
    return "+".join(fields)


def high_value(row: dict[str, str], field: str) -> str:
    if len(field) == 1:
        return field
    if field == "prefix_high":
        value = row.get("prefix_byte", "")
        return value[:1].lower() if len(value) == 2 else ""
    if field == "source_prefix_high":
        value = row.get("source_prefix_byte", "")
        return value[:1].lower() if len(value) == 2 else ""
    return row.get(field, "")


def predicted_byte(row: dict[str, str], formula: str) -> str:
    high_field, low_field, delta = FORMULAS[formula]
    high = high_value(row, high_field)
    low = nibble(row.get(low_field, ""))
    if len(high) != 1 or low is None:
        return ""
    return f"{high}{(low + delta) & 0x0F:x}".lower()


def enrich_rows(slot_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    by_rank = {row.get("rank", ""): row for row in slot_rows}
    enriched: list[dict[str, str]] = []
    for row in slot_rows:
        output = dict(row)
        source_slot = by_rank.get(row.get("source_slot_rank", ""), {})
        for field in SOURCE_FIELDS:
            output[f"source_{field}"] = source_slot.get(field, "")
        enriched.append(output)
    return enriched


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
                exact = prediction == row.get("source_expected_byte", "").lower()
                key = guard_key(row, fields)
                if target_scope(row):
                    groups[key]["unknown_exact_rows" if exact else "unknown_false_rows"] += 1
                elif known_scope(row):
                    groups[key]["known_exact_rows" if exact else "known_false_rows"] += 1
            for key, counts in groups.items():
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
    for rank, row in enumerate(guard_rows, start=1):
        row["rank"] = str(rank)
    return guard_rows


def select_guard(guard_rows: list[dict[str, str]]) -> dict[str, str]:
    return next((row for row in guard_rows if row.get("verdict") == "promotion_ready_guard"), {})


def review_verdict(guard: dict[str, str]) -> str:
    if not guard:
        return "missing_expanded_source_byte_guard"
    if int_value(guard, "known_exact_rows") <= 0:
        return "expanded_source_byte_guard_missing_known_support"
    if int_value(guard, "known_false_rows") > 0:
        return "expanded_source_byte_guard_known_false"
    if int_value(guard, "unknown_false_rows") > 0:
        return "expanded_source_byte_guard_unknown_false"
    if int_value(guard, "unknown_exact_rows") <= 0:
        return "expanded_source_byte_guard_no_targets"
    return "expanded_source_byte_guard_promotion_ready"


def next_probe_for(verdict: str) -> str:
    if verdict == "expanded_source_byte_guard_promotion_ready":
        return "promote expanded source-byte guard after old-clean union"
    if verdict == "expanded_source_byte_guard_missing_known_support":
        return "seek broader known support for expanded source-byte guard"
    return "derive stronger expanded source-byte guard after old-clean union"


def build(slot_rows: list[dict[str, str]]) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    rows = enrich_rows(slot_rows)
    guard_rows = build_guard_rows(rows)
    guard = select_guard(guard_rows)
    verdict = review_verdict(guard)
    target_rows: list[dict[str, str]] = []
    if guard:
        fields = tuple(guard.get("guard_family", "").split("+"))
        formula = guard.get("formula", "")
        seen: set[tuple[str, str, str, str]] = set()
        for row in rows:
            if not target_scope(row):
                continue
            if guard_key(row, fields) != guard.get("guard_key", ""):
                continue
            prediction = predicted_byte(row, formula)
            if not prediction:
                continue
            issues: list[str] = []
            if prediction != row.get("source_expected_byte", "").lower():
                issues.append("prediction_false")
            source_offset = row.get("source_actual_offset", "")
            key = (row.get("archive", ""), row.get("pcx_name", ""), row.get("frontier_id", ""), source_offset)
            if key in seen:
                continue
            seen.add(key)
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
                    "promotion_ready": "1" if not issues and verdict == "expanded_source_byte_guard_promotion_ready" else "0",
                    "issues": ";".join(issues),
                }
            )
    promotion_ready = (
        len(target_rows)
        if verdict == "expanded_source_byte_guard_promotion_ready" and not any(row.get("issues") for row in target_rows)
        else 0
    )
    summary = {
        "scope": "total",
        "candidate_mode": "old_clean_byte_union_expanded_source_byte_guard_review",
        "slot_rows": str(len(slot_rows)),
        "source_rows": str(sum(1 for row in rows if source_scope(row))),
        "unknown_source_rows": str(sum(1 for row in rows if target_scope(row))),
        "known_source_rows": str(sum(1 for row in rows if known_scope(row))),
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


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 160) -> str:
    return (
        "<table><thead><tr>"
        + "".join(f"<th>{html.escape(field)}</th>" for field in fields)
        + "</tr></thead><tbody>"
        + "".join(
            "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"
            for row in rows[:limit]
        )
        + "</tbody></table>"
    )


def build_html(
    summary: dict[str, str],
    guard_rows: list[dict[str, str]],
    target_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "guards": guard_rows, "targets": target_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    return f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <title>{html.escape(title)}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 24px; background: #f7f7f4; color: #222; }}
    .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 10px; margin: 18px 0; }}
    .stat {{ background: #fff; border: 1px solid #ddd; padding: 10px; }}
    .label {{ color: #666; font-size: 12px; }}
    .value {{ font-size: 22px; font-weight: 700; }}
    table {{ border-collapse: collapse; width: 100%; background: white; margin: 18px 0; }}
    th, td {{ border: 1px solid #ddd; padding: 6px 8px; font-size: 13px; text-align: left; }}
    th {{ background: #ecebe4; }}
  </style>
</head>
<body>
  <h1>{html.escape(title)}</h1>
  <p><a href="{relative_href(output_dir / 'summary.csv', output_dir)}">summary.csv</a>
  <a href="{relative_href(output_dir / 'guards.csv', output_dir)}">guards.csv</a>
  <a href="{relative_href(output_dir / 'targets.csv', output_dir)}">targets.csv</a></p>
  <div class="stats">
    <div class="stat"><div class="label">Verdict</div><div class="value">{html.escape(summary['review_verdict'])}</div></div>
    <div class="stat"><div class="label">Ready bytes</div><div class="value">{html.escape(summary['promotion_ready_bytes'])}</div></div>
    <div class="stat"><div class="label">Unknown exact</div><div class="value">{html.escape(summary['best_unknown_exact_rows'])}</div></div>
    <div class="stat"><div class="label">Known exact</div><div class="value">{html.escape(summary['best_known_exact_rows'])}</div></div>
    <div class="stat"><div class="label">Issues</div><div class="value">{html.escape(summary['issue_rows'])}</div></div>
  </div>
  <h2>Best Guards</h2>
  {render_table(guard_rows, GUARD_FIELDNAMES)}
  <h2>Targets</h2>
  {render_table(target_rows, TARGET_FIELDNAMES)}
  <script type="application/json" id="payload">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slots", type=Path, default=DEFAULT_SLOTS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Old Clean Union Expanded Source Byte Guard Review")
    args = parser.parse_args()

    summary, guard_rows, target_rows = build(read_csv(args.slots))
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "guards.csv", GUARD_FIELDNAMES, guard_rows)
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, target_rows)
    (args.output / "index.html").write_text(build_html(summary, guard_rows, target_rows, args.output, args.title))

    print(
        "Expanded source-byte guard review: "
        f"verdict={summary['review_verdict']} "
        f"formula={summary['best_formula']} "
        f"guard={summary['best_guard_key']} "
        f"known={summary['best_known_exact_rows']}/{summary['best_known_false_rows']} "
        f"unknown={summary['best_unknown_exact_rows']}/{summary['best_unknown_false_rows']} "
        f"promotion_ready={summary['promotion_ready_bytes']} "
        f"issues={summary['issue_rows']}"
    )
    print(f"HTML: {args.output / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
