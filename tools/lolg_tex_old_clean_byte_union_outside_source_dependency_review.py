#!/usr/bin/env python3
"""Review non-high-safe source dependencies after the old-clean post-union cascade."""

from __future__ import annotations

import argparse
import csv
import html
import itertools
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_opcode_probe import relative_href, write_csv
from lolg_tex_micro_mixed_value_payload_state_opcode_probe import int_value


DEFAULT_SLOTS = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_old_clean_byte_union_control_prefix_fill_guard_promoted_replay/slots.csv"
)
DEFAULT_OUTPUT = Path("output/tex_old_clean_byte_union_outside_source_dependency_review")

DIRECT_BYTE_FIELDS = (
    "target_byte",
    "prefix_byte",
    "fragment_byte",
    "window_head_byte",
    "window_tail_byte",
    "control_byte",
    "start_byte",
)

HIGH_SPECS = (
    "target_high",
    "prefix_byte",
    "fragment_byte",
    "control_byte",
    "start_byte",
    "5",
    "6",
    "a",
)

LOW_SPECS = (
    "target_low",
    "prev_low1",
    "prev_low2",
    "control_low",
    "start_low",
    "prefix_low",
    "fragment_low",
    "bucket_split_prediction",
    "target_delta",
    "target_byte",
    "prefix_byte",
    "fragment_byte",
    "control_byte",
    "start_byte",
)

GUARD_FEATURES = (
    "frontier_id",
    "start",
    "relative_offset",
    "rel_mod4",
    "rel_mod8",
    "target_mod32",
    "low_bucket",
    "target_low",
    "control_ref_mod64",
    "control_low",
    "start_low",
    "prefix_low",
    "fragment_low",
    "seq_index",
    "prev_low1",
    "target_delta",
    "target_step",
    "bucket_split_prediction",
    "span_index",
    "op_index",
    "source_actual_offset",
)

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "slot_rows",
    "outside_source_rows",
    "known_source_rows",
    "unknown_source_rows",
    "unknown_source_groups",
    "repeated_unknown_source_groups",
    "top_unknown_group_key",
    "top_unknown_group_rows",
    "top_unknown_group_expected",
    "supported_guard_rows",
    "target_only_guard_rows",
    "best_supported_unknown_exact_rows",
    "best_supported_known_exact_rows",
    "best_supported_formula",
    "best_supported_guard_family",
    "best_supported_guard_key",
    "best_target_only_unknown_exact_rows",
    "best_target_only_formula",
    "best_target_only_guard_family",
    "best_target_only_guard_key",
    "review_verdict",
    "next_probe",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

UNKNOWN_FIELDNAMES = [
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "source_actual_offset",
    "unknown_rows",
    "expected_values",
    "target_values",
    "target_rows",
    "starts",
    "target_offsets",
    "source_profile_offsets",
    "relative_offsets",
    "issue",
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
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def is_hex_byte(value: str) -> bool:
    return len(value) == 2 and all(char in "0123456789abcdefABCDEF" for char in value)


def low_nibble(value: str) -> int | None:
    if not value or value == "NA":
        return None
    try:
        return int(str(value)[-1], 16)
    except ValueError:
        return None


def high_nibble(row: dict[str, str], spec: str) -> str:
    if len(spec) == 1 and spec in "56a":
        return spec
    value = row.get(spec, "").lower()
    if len(value) == 1 and value in "0123456789abcdef":
        return value
    if is_hex_byte(value):
        return value[:1]
    return ""


def formula_rows() -> list[tuple[str, str, str, int]]:
    rows: list[tuple[str, str, str, int]] = []
    for field in DIRECT_BYTE_FIELDS:
        rows.append(("direct", field, "", 0))
    for high_spec in HIGH_SPECS:
        for low_spec in LOW_SPECS:
            for delta in range(-2, 3):
                rows.append((high_spec, low_spec, "", delta))
    return rows


def formula_name(formula: tuple[str, str, str, int]) -> str:
    high_spec, low_spec, _, delta = formula
    if high_spec == "direct":
        return low_spec
    return f"{high_spec}+{low_spec}{delta:+d}"


def predicted_byte(row: dict[str, str], formula: tuple[str, str, str, int]) -> str:
    high_spec, low_spec, _, delta = formula
    if high_spec == "direct":
        value = row.get(low_spec, "").lower()
        return value if is_hex_byte(value) else ""
    high = high_nibble(row, high_spec)
    low = low_nibble(row.get(low_spec, ""))
    if len(high) != 1 or low is None:
        return ""
    return f"{high}{(low + delta) & 15:x}"


def source_scope(row: dict[str, str]) -> bool:
    return row.get("source_location") == "outside_highsafe" and bool(row.get("source_expected_byte", ""))


def target_scope(row: dict[str, str]) -> bool:
    return source_scope(row) and row.get("source_availability") == "unknown_source"


def known_scope(row: dict[str, str]) -> bool:
    return source_scope(row) and row.get("source_availability") == "known_source"


def guard_family(fields: tuple[str, ...]) -> str:
    return "+".join(fields)


def guard_key(row: dict[str, str], fields: tuple[str, ...]) -> str:
    return "+".join(f"{field}={row.get(field, '')}" for field in fields)


def source_dependency_edge(row: dict[str, str]) -> str:
    return (
        f"{row.get('frontier_id', '')}|{row.get('start', '')}->"
        f"{row.get('source_slot_frontier_id', '')}|{row.get('source_slot_start', '')}"
    )


def compact_join(values: list[str]) -> str:
    return ";".join(sorted({value for value in values if value}))


def build_unknown_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if not target_scope(row):
            continue
        key = (
            row.get("archive", ""),
            row.get("pcx_name", ""),
            row.get("frontier_id", ""),
            row.get("source_actual_offset", ""),
            row.get("archive_tag", ""),
        )
        grouped[key].append(row)

    output: list[dict[str, str]] = []
    for (archive, pcx_name, frontier_id, source_actual_offset, archive_tag), members in sorted(
        grouped.items(),
        key=lambda item: (
            item[0][0],
            item[0][1],
            int(item[0][2] or "0"),
            int(item[0][3] or "0"),
        ),
    ):
        expected_values = compact_join([row.get("source_expected_byte", "") for row in members])
        issue = "" if len(expected_values.split(";")) == 1 else "conflicting_expected_values"
        output.append(
            {
                "rank": str(len(output) + 1),
                "archive": archive,
                "archive_tag": archive_tag,
                "pcx_name": pcx_name,
                "frontier_id": frontier_id,
                "source_actual_offset": source_actual_offset,
                "unknown_rows": str(len(members)),
                "expected_values": expected_values,
                "target_values": compact_join([row.get("target_byte", "") for row in members]),
                "target_rows": compact_join([row.get("rank", "") for row in members]),
                "starts": compact_join([row.get("start", "") for row in members]),
                "target_offsets": compact_join([row.get("target_offset", "") for row in members]),
                "source_profile_offsets": compact_join([row.get("source_profile_offset", "") for row in members]),
                "relative_offsets": compact_join([row.get("relative_offset", "") for row in members]),
                "issue": issue,
            }
        )
    output.sort(key=lambda row: (-int_value(row, "unknown_rows"), row["pcx_name"], int_value(row, "source_actual_offset")))
    for index, row in enumerate(output, start=1):
        row["rank"] = str(index)
    return output


def guard_feature_sets(max_features: int) -> list[tuple[str, ...]]:
    output: list[tuple[str, ...]] = []
    for size in range(1, max_features + 1):
        output.extend(itertools.combinations(GUARD_FEATURES, size))
    return output


def build_guard_rows(rows: list[dict[str, str]], max_features: int) -> list[dict[str, str]]:
    scoped = [row for row in rows if source_scope(row)]
    feature_sets = guard_feature_sets(max_features)
    output: list[dict[str, str]] = []
    for formula in formula_rows():
        name = formula_name(formula)
        predictions = [predicted_byte(row, formula) for row in scoped]
        if not any(predictions):
            continue
        for fields in feature_sets:
            groups: dict[str, Counter[str]] = defaultdict(Counter)
            for row, prediction in zip(scoped, predictions):
                if not prediction:
                    continue
                exact = prediction == row.get("source_expected_byte", "").lower()
                key = guard_key(row, fields)
                if target_scope(row):
                    groups[key]["unknown_exact_rows" if exact else "unknown_false_rows"] += 1
                elif known_scope(row):
                    groups[key]["known_exact_rows" if exact else "known_false_rows"] += 1
            for key, counts in groups.items():
                if counts["unknown_exact_rows"] <= 0 or counts["unknown_false_rows"] > 0:
                    continue
                verdict = "target_only_guard"
                if counts["known_exact_rows"] > 0 and counts["known_false_rows"] == 0:
                    verdict = "supported_guard"
                elif counts["known_false_rows"] > 0:
                    verdict = "known_false_guard"
                output.append(
                    {
                        "rank": "",
                        "formula": name,
                        "guard_family": guard_family(fields),
                        "guard_key": key,
                        "unknown_exact_rows": str(counts["unknown_exact_rows"]),
                        "unknown_false_rows": str(counts["unknown_false_rows"]),
                        "known_exact_rows": str(counts["known_exact_rows"]),
                        "known_false_rows": str(counts["known_false_rows"]),
                        "verdict": verdict,
                    }
                )
    output.sort(
        key=lambda row: (
            row.get("verdict") != "supported_guard",
            row.get("verdict") != "target_only_guard",
            -int_value(row, "unknown_exact_rows"),
            -int_value(row, "known_exact_rows"),
            len(row.get("guard_family", "").split("+")),
            row.get("formula", ""),
            row.get("guard_family", ""),
            row.get("guard_key", ""),
        )
    )
    for index, row in enumerate(output, start=1):
        row["rank"] = str(index)
    return output


def selected_supported_guard(guard_rows: list[dict[str, str]]) -> dict[str, str]:
    return next((row for row in guard_rows if row.get("verdict") == "supported_guard"), {})


def build_target_rows(slot_rows: list[dict[str, str]], guard: dict[str, str]) -> list[dict[str, str]]:
    if not guard:
        return []
    fields = tuple(field for field in guard.get("guard_family", "").split("+") if field)
    formula_name_to_row = {formula_name(row): row for row in formula_rows()}
    formula = formula_name_to_row.get(guard.get("formula", ""))
    if not fields or formula is None:
        return []
    output: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for row in slot_rows:
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
        output.append(
            {
                "rank": str(len(output) + 1),
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
                "best_formula": guard.get("formula", ""),
                "best_guard_family": guard.get("guard_family", ""),
                "best_guard_key": guard.get("guard_key", ""),
                "promotion_ready": "1" if not issues else "0",
                "issues": ";".join(issues),
            }
        )
    return output


def next_probe_for(verdict: str) -> str:
    if verdict == "outside_source_dependency_supported_guard_ready":
        return "promote supported non-high-safe source dependency guard"
    if verdict == "outside_source_dependency_target_only_no_known_support":
        return "derive known support for frontier18 source offsets 247-269 and frontier80 offsets 16-17"
    return "derive non-high-safe source producer for unresolved .tex dependencies"


def build_summary(
    slot_rows: list[dict[str, str]],
    unknown_rows: list[dict[str, str]],
    guard_rows: list[dict[str, str]],
    target_rows: list[dict[str, str]],
) -> dict[str, str]:
    outside_rows = [row for row in slot_rows if source_scope(row)]
    supported = [row for row in guard_rows if row.get("verdict") == "supported_guard"]
    target_only = [row for row in guard_rows if row.get("verdict") == "target_only_guard"]
    best_supported = supported[0] if supported else {}
    best_target_only = target_only[0] if target_only else {}
    top_unknown = unknown_rows[0] if unknown_rows else {}
    repeated_groups = sum(1 for row in unknown_rows if int_value(row, "unknown_rows") > 1)
    if supported:
        verdict = "outside_source_dependency_supported_guard_ready"
    elif target_only:
        verdict = "outside_source_dependency_target_only_no_known_support"
    else:
        verdict = "outside_source_dependency_missing_guard"
    return {
        "scope": "total",
        "candidate_mode": "old_clean_byte_union_outside_source_dependency_review",
        "slot_rows": str(len(slot_rows)),
        "outside_source_rows": str(len(outside_rows)),
        "known_source_rows": str(sum(1 for row in outside_rows if known_scope(row))),
        "unknown_source_rows": str(sum(1 for row in outside_rows if target_scope(row))),
        "unknown_source_groups": str(len(unknown_rows)),
        "repeated_unknown_source_groups": str(repeated_groups),
        "top_unknown_group_key": "|".join(
            [
                top_unknown.get("pcx_name", ""),
                top_unknown.get("frontier_id", ""),
                top_unknown.get("source_actual_offset", ""),
            ]
        ),
        "top_unknown_group_rows": top_unknown.get("unknown_rows", "0"),
        "top_unknown_group_expected": top_unknown.get("expected_values", ""),
        "supported_guard_rows": str(len(supported)),
        "target_only_guard_rows": str(len(target_only)),
        "best_supported_unknown_exact_rows": best_supported.get("unknown_exact_rows", "0"),
        "best_supported_known_exact_rows": best_supported.get("known_exact_rows", "0"),
        "best_supported_formula": best_supported.get("formula", ""),
        "best_supported_guard_family": best_supported.get("guard_family", ""),
        "best_supported_guard_key": best_supported.get("guard_key", ""),
        "best_target_only_unknown_exact_rows": best_target_only.get("unknown_exact_rows", "0"),
        "best_target_only_formula": best_target_only.get("formula", ""),
        "best_target_only_guard_family": best_target_only.get("guard_family", ""),
        "best_target_only_guard_key": best_target_only.get("guard_key", ""),
        "review_verdict": verdict,
        "next_probe": next_probe_for(verdict),
        "promotion_candidate_bytes": str(len(target_rows)),
        "promotion_ready_bytes": str(sum(1 for row in target_rows if row.get("promotion_ready") == "1")),
        "issue_rows": str(
            sum(1 for row in unknown_rows if row.get("issue"))
            + sum(1 for row in target_rows if row.get("issues"))
        ),
    }


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 180) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    unknown_rows: list[dict[str, str]],
    guard_rows: list[dict[str, str]],
    target_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "unknown_sources": unknown_rows, "guards": guard_rows, "targets": target_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    return f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <title>{html.escape(title)}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 24px; background: #f6f7f8; color: #202529; }}
    .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; margin: 18px 0; }}
    .stat {{ background: white; border: 1px solid #d5dbe0; padding: 10px; }}
    .label {{ color: #68737d; font-size: 12px; }}
    .value {{ font-size: 21px; font-weight: 750; overflow-wrap: anywhere; }}
    table {{ border-collapse: collapse; width: 100%; background: white; margin: 18px 0; }}
    th, td {{ border: 1px solid #d5dbe0; padding: 6px 8px; font-size: 13px; text-align: left; vertical-align: top; }}
    th {{ background: #e9edf0; }}
  </style>
</head>
<body>
  <h1>{html.escape(title)}</h1>
  <p><a href="{relative_href(output_dir / 'summary.csv', output_dir)}">summary.csv</a>
  <a href="{relative_href(output_dir / 'unknown_sources.csv', output_dir)}">unknown_sources.csv</a>
  <a href="{relative_href(output_dir / 'guards.csv', output_dir)}">guards.csv</a>
  <a href="{relative_href(output_dir / 'targets.csv', output_dir)}">targets.csv</a></p>
  <div class="stats">
    <div class="stat"><div class="label">Verdict</div><div class="value">{html.escape(summary['review_verdict'])}</div></div>
    <div class="stat"><div class="label">Unknown outside rows</div><div class="value">{html.escape(summary['unknown_source_rows'])}</div></div>
    <div class="stat"><div class="label">Unknown groups</div><div class="value">{html.escape(summary['unknown_source_groups'])}</div></div>
    <div class="stat"><div class="label">Supported guards</div><div class="value">{html.escape(summary['supported_guard_rows'])}</div></div>
    <div class="stat"><div class="label">Target-only guards</div><div class="value">{html.escape(summary['target_only_guard_rows'])}</div></div>
    <div class="stat"><div class="label">Promotion ready</div><div class="value">{html.escape(summary['promotion_ready_bytes'])}</div></div>
  </div>
  <h2>Unknown Sources</h2>
  {render_table(unknown_rows, UNKNOWN_FIELDNAMES)}
  <h2>Top Guards</h2>
  {render_table(guard_rows, GUARD_FIELDNAMES)}
  <h2>Targets</h2>
  {render_table(target_rows, TARGET_FIELDNAMES)}
  <script type="application/json" id="payload">{html.escape(data_json)}</script>
</body>
</html>
"""


def build(
    slot_rows: list[dict[str, str]], max_features: int
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    unknown_rows = build_unknown_rows(slot_rows)
    guard_rows = build_guard_rows(slot_rows, max_features)
    target_rows = build_target_rows(slot_rows, selected_supported_guard(guard_rows))
    summary = build_summary(slot_rows, unknown_rows, guard_rows, target_rows)
    return summary, unknown_rows, guard_rows, target_rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slots", type=Path, default=DEFAULT_SLOTS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-features", type=int, default=2)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Old Clean Union Outside Source Dependency Review",
    )
    args = parser.parse_args()

    summary, unknown_rows, guard_rows, target_rows = build(read_csv(args.slots), args.max_features)
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "unknown_sources.csv", UNKNOWN_FIELDNAMES, unknown_rows)
    write_csv(args.output / "guards.csv", GUARD_FIELDNAMES, guard_rows)
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, target_rows)
    (args.output / "index.html").write_text(
        build_html(summary, unknown_rows, guard_rows, target_rows, args.output, args.title)
    )

    print(
        "Outside source dependency review: "
        f"verdict={summary['review_verdict']} "
        f"outside={summary['outside_source_rows']} "
        f"unknown={summary['unknown_source_rows']} "
        f"groups={summary['unknown_source_groups']} "
        f"supported_guards={summary['supported_guard_rows']} "
        f"target_only_guards={summary['target_only_guard_rows']} "
        f"promotion_ready={summary['promotion_ready_bytes']}"
    )
    print(f"HTML: {args.output / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
