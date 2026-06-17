#!/usr/bin/env python3
"""Probe broader relative evidence for final small nonzero external source bytes."""

from __future__ import annotations

import argparse
import csv
import html
import itertools
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from lolg_tex_gap_opcode_probe import relative_href, write_csv
from lolg_tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_selector_probe import (
    int_value,
)


DEFAULT_TARGETS = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_selector/targets.csv"
)
DEFAULT_SMALL_GAPS = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_selector/small_gaps.csv"
)
DEFAULT_OUTPUT = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_broader_evidence"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "target_spans",
    "target_bytes",
    "small_gap_rows",
    "known_small_gap_rows",
    "formula_rows",
    "target_exact_formula_rows",
    "known_supported_formula_rows",
    "guard_rows",
    "false_free_known_guard_rows",
    "best_target_span",
    "best_formula",
    "best_formula_source",
    "best_formula_transform",
    "best_known_exact_rows",
    "best_known_false_rows",
    "best_guard_family",
    "best_guard_key",
    "best_guard_target_rows",
    "best_guard_known_exact_rows",
    "best_guard_known_false_rows",
    "best_guard_reference_exact_rows",
    "best_guard_reference_false_rows",
    "review_verdict",
    "next_probe",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

FORMULA_FIELDNAMES = [
    "rank",
    "target_span",
    "formula",
    "source_family",
    "source_position",
    "transform",
    "parameter",
    "target_output_hex",
    "target_expected_hex",
    "target_exact",
    "known_eval_rows",
    "known_exact_rows",
    "known_false_rows",
    "reference_eval_rows",
    "reference_exact_rows",
    "reference_false_rows",
    "best_guard_key",
    "best_guard_known_exact_rows",
    "best_guard_known_false_rows",
    "best_guard_reference_exact_rows",
    "best_guard_reference_false_rows",
    "review_verdict",
]

GUARD_FIELDNAMES = [
    "rank",
    "target_span",
    "formula",
    "guard_family",
    "guard_key",
    "target_rows",
    "known_rows",
    "known_exact_rows",
    "known_false_rows",
    "reference_rows",
    "reference_exact_rows",
    "reference_false_rows",
    "verdict",
    "sample_exact_spans",
    "sample_false_spans",
]

EVALUATION_FIELDNAMES = [
    "rank",
    "target_span",
    "formula",
    "span_key",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "known_in_replay",
    "expected_hex",
    "output_hex",
    "formula_exact",
    "gap_role",
    "prev_op_length",
    "next_op_length",
    "control_ref_mod64",
    "expected_start",
]

EQUALITY_FEATURES = [
    "gap_role",
    "frontier_type",
    "strategy",
    "pcx_name",
    "archive_tag",
    "prev_op_length",
    "next_op_length",
    "control_ref_mod64",
]

NUMERIC_FEATURES = [
    "control_ref_mod64",
    "expected_mod64",
    "expected_start",
    "op_index",
    "prev_op_length",
    "next_op_length",
]


@dataclass(frozen=True)
class FormulaSpec:
    formula: str
    source_family: str
    source_position: str
    transform: str
    parameter: str
    compute: Callable[[dict[str, str]], int | None]


@dataclass(frozen=True)
class GuardCondition:
    key: str
    family: str
    match: Callable[[dict[str, str]], bool]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def bytes_value(text: str) -> bytes:
    return bytes.fromhex(text) if text else b""


def one_byte_expected(row: dict[str, str]) -> int | None:
    expected = bytes_value(row.get("expected_hex", ""))
    if len(expected) != 1:
        return None
    return expected[0]


def source_atoms(row: dict[str, str]) -> dict[tuple[str, str], int]:
    atoms: dict[tuple[str, str], int] = {}
    prev = bytes_value(row.get("prev_expected_hex", ""))
    next_expected = bytes_value(row.get("next_expected_hex", ""))
    head = bytes_value(row.get("control_head4", ""))
    tail = bytes_value(row.get("control_tail4", ""))
    for offset in range(1, 9):
        if len(prev) >= offset:
            atoms[("prev_byte", f"-{offset}")] = prev[-offset]
    for offset, value in enumerate(prev[:8]):
        atoms[("prev_byte", f"+{offset}")] = value
    for offset, value in enumerate(next_expected[:8]):
        atoms[("next_byte", f"+{offset}")] = value
    for offset, value in enumerate(head):
        atoms[("control_head4", f"+{offset}")] = value
    for offset, value in enumerate(tail):
        atoms[("control_tail4", f"+{offset}")] = value
    return atoms


def transformed_values(value: int) -> list[tuple[str, str, int]]:
    output = [("identity", "", value)]
    for delta in [-4, -3, -2, -1, 1, 2, 3, 4, 0x20, -0x20]:
        output.append(("add_const", f"{delta:+d}", (value + delta) & 0xFF))
    for constant in [0x01, 0x02, 0x03, 0x04, 0x20, 0x40, 0x55, 0x6A, 0x80, 0xFF]:
        output.append(("xor_const", f"{constant:02x}", value ^ constant))
    return output


def formula_specs_for_target(target: dict[str, str]) -> list[FormulaSpec]:
    expected = one_byte_expected(target)
    if expected is None:
        return []
    specs: list[FormulaSpec] = []
    seen: set[str] = set()
    for (family, position), source in source_atoms(target).items():
        for transform, parameter, output in transformed_values(source):
            if output != expected:
                continue
            formula = f"{family}{position}:{transform}{'=' + parameter if parameter else ''}"
            if formula in seen:
                continue
            seen.add(formula)

            def compute(
                row: dict[str, str],
                family: str = family,
                position: str = position,
                transform: str = transform,
                parameter: str = parameter,
            ) -> int | None:
                atoms = source_atoms(row)
                value = atoms.get((family, position))
                if value is None:
                    return None
                for candidate_transform, candidate_parameter, output_value in transformed_values(value):
                    if candidate_transform == transform and candidate_parameter == parameter:
                        return output_value
                return None

            specs.append(
                FormulaSpec(
                    formula=formula,
                    source_family=family,
                    source_position=position,
                    transform=transform,
                    parameter=parameter,
                    compute=compute,
                )
            )
    return specs


def evaluation_row(target_span: str, spec: FormulaSpec, row: dict[str, str]) -> dict[str, str] | None:
    expected = one_byte_expected(row)
    output = spec.compute(row)
    if expected is None or output is None:
        return None
    return {
        "rank": "",
        "target_span": target_span,
        "formula": spec.formula,
        "span_key": row.get("span_key", ""),
        "archive_tag": row.get("archive_tag", ""),
        "pcx_name": row.get("pcx_name", ""),
        "frontier_id": row.get("frontier_id", ""),
        "known_in_replay": row.get("known_in_replay", ""),
        "expected_hex": f"{expected:02x}",
        "output_hex": f"{output:02x}",
        "formula_exact": "1" if output == expected else "0",
        "gap_role": row.get("gap_role", ""),
        "prev_op_length": row.get("prev_op_length", ""),
        "next_op_length": row.get("next_op_length", ""),
        "control_ref_mod64": row.get("control_ref_mod64", ""),
        "expected_start": row.get("expected_start", ""),
    }


def target_row_for(evaluation: dict[str, str], target_span: str) -> bool:
    return evaluation.get("span_key", "") == target_span


def known_rows(evaluations: list[dict[str, str]]) -> list[dict[str, str]]:
    return [row for row in evaluations if row.get("known_in_replay") == "1"]


def exact_rows(evaluations: list[dict[str, str]]) -> list[dict[str, str]]:
    return [row for row in evaluations if row.get("formula_exact") == "1"]


def false_rows(evaluations: list[dict[str, str]]) -> list[dict[str, str]]:
    return [row for row in evaluations if row.get("formula_exact") != "1"]


def non_target_rows(evaluations: list[dict[str, str]], target_span: str) -> list[dict[str, str]]:
    return [row for row in evaluations if not target_row_for(row, target_span)]


def numeric_value(row: dict[str, str], field: str) -> int | None:
    try:
        return int(row.get(field, ""))
    except (TypeError, ValueError):
        return None


def build_conditions(
    target: dict[str, str],
    gap_rows: list[dict[str, str]],
    formula_evaluations: list[dict[str, str]],
    target_span: str,
) -> list[GuardCondition]:
    exact_known_spans = {
        row.get("span_key", "")
        for row in formula_evaluations
        if row.get("known_in_replay") == "1" and row.get("formula_exact") == "1"
    }
    source_by_span = {row.get("span_key", ""): row for row in gap_rows}
    exact_known_source_rows = [source_by_span[span] for span in exact_known_spans if span in source_by_span]
    if not exact_known_source_rows:
        return []

    conditions: list[GuardCondition] = []
    for field in EQUALITY_FEATURES:
        target_value = target.get(field, "")
        if not target_value:
            continue
        if not any(row.get(field, "") == target_value for row in exact_known_source_rows):
            continue
        conditions.append(
            GuardCondition(
                key=f"{field}={target_value}",
                family=field,
                match=lambda row, field=field, target_value=target_value: row.get(field, "") == target_value,
            )
        )

    values_by_field: dict[str, set[int]] = {field: set() for field in NUMERIC_FEATURES}
    target_values = {field: numeric_value(target, field) for field in NUMERIC_FEATURES}
    for row in gap_rows:
        for field in NUMERIC_FEATURES:
            value = numeric_value(row, field)
            if value is not None:
                values_by_field[field].add(value)
    for field, values in values_by_field.items():
        target_value = target_values.get(field)
        if target_value is None:
            continue
        for threshold in sorted(values):
            for direction in ("gte", "lte"):
                if direction == "gte" and target_value < threshold:
                    continue
                if direction == "lte" and target_value > threshold:
                    continue

                def match(
                    row: dict[str, str],
                    field: str = field,
                    threshold: int = threshold,
                    direction: str = direction,
                ) -> bool:
                    value = numeric_value(row, field)
                    if value is None:
                        return False
                    return value >= threshold if direction == "gte" else value <= threshold

                if not any(match(row) for row in exact_known_source_rows):
                    continue
                conditions.append(
                    GuardCondition(
                        key=f"{field}{'>=' if direction == 'gte' else '<='}{threshold}",
                        family=f"{field}_{direction}",
                        match=match,
                    )
                )

    deduped: dict[str, GuardCondition] = {}
    for condition in conditions:
        deduped[condition.key] = condition
    return list(deduped.values())


def guard_verdict(
    known_exact: int,
    known_false: int,
    reference_exact: int,
    reference_false: int,
    target_rows_count: int,
) -> str:
    if known_exact > 0 and known_false == 0 and reference_false == 0 and reference_exact > target_rows_count:
        return "promotion_ready_guard"
    if known_exact > 0 and known_false == 0 and reference_false == 0:
        return "target_and_known_only_guard"
    if known_exact > 0 and known_false == 0:
        return "known_support_reference_false"
    if known_false > 0:
        return "known_false_guard"
    return "target_only_guard"


def guard_rows_for(
    target: dict[str, str],
    gap_rows: list[dict[str, str]],
    formula_rows: list[dict[str, str]],
    target_span: str,
    formula: str,
) -> list[dict[str, str]]:
    source_by_span = {row.get("span_key", ""): row for row in gap_rows}
    conditions = build_conditions(target, gap_rows, formula_rows, target_span)
    output: list[dict[str, str]] = []
    guard_sets: list[tuple[GuardCondition, ...]] = []
    guard_sets.extend((condition,) for condition in conditions)
    guard_sets.extend(itertools.combinations(conditions, 2))

    seen: set[str] = set()
    for guard_set in guard_sets:
        key = "+".join(condition.key for condition in guard_set)
        if key in seen:
            continue
        seen.add(key)
        matched = [
            row
            for row in formula_rows
            if row.get("span_key", "") in source_by_span
            and all(condition.match(source_by_span[row.get("span_key", "")]) for condition in guard_set)
        ]
        if not matched or not any(target_row_for(row, target_span) for row in matched):
            continue
        known = known_rows(matched)
        known_exact = len(exact_rows(known))
        known_false = len(false_rows(known))
        reference = non_target_rows(matched, target_span)
        reference_exact = len(exact_rows(reference))
        reference_false = len(false_rows(reference))
        target_rows_count = sum(1 for row in matched if target_row_for(row, target_span))
        output.append(
            {
                "rank": "",
                "target_span": target_span,
                "formula": formula,
                "guard_family": "+".join(condition.family for condition in guard_set),
                "guard_key": key,
                "target_rows": str(target_rows_count),
                "known_rows": str(len(known)),
                "known_exact_rows": str(known_exact),
                "known_false_rows": str(known_false),
                "reference_rows": str(len(reference)),
                "reference_exact_rows": str(reference_exact),
                "reference_false_rows": str(reference_false),
                "verdict": guard_verdict(
                    known_exact,
                    known_false,
                    reference_exact,
                    reference_false,
                    target_rows_count,
                ),
                "sample_exact_spans": ",".join(row.get("span_key", "") for row in exact_rows(reference)[:8]),
                "sample_false_spans": ",".join(row.get("span_key", "") for row in false_rows(reference)[:8]),
            }
        )
    return output


def sort_guard_key(row: dict[str, str]) -> tuple[object, ...]:
    verdict_rank = {
        "promotion_ready_guard": 0,
        "target_and_known_only_guard": 1,
        "known_support_reference_false": 2,
        "known_false_guard": 3,
        "target_only_guard": 4,
    }.get(row.get("verdict", ""), 5)
    return (
        verdict_rank,
        int_value(row, "reference_false_rows"),
        -int_value(row, "known_exact_rows"),
        -int_value(row, "reference_exact_rows"),
        int_value(row, "reference_rows"),
        row.get("guard_key", ""),
    )


def sort_formula_key(row: dict[str, str]) -> tuple[object, ...]:
    verdict_rank = {
        "promotion_ready_guard": 0,
        "target_and_known_only_guard": 1,
        "known_support_reference_false": 2,
        "known_supported_overall_conflicted": 3,
        "known_false_without_support": 4,
        "target_only_no_known_support": 5,
    }.get(row.get("review_verdict", ""), 6)
    return (
        verdict_rank,
        int_value(row, "best_guard_reference_false_rows"),
        int_value(row, "known_false_rows"),
        -int_value(row, "known_exact_rows"),
        row.get("formula", ""),
    )


def formula_verdict(known_exact: int, known_false: int, best_guard: dict[str, str]) -> str:
    if best_guard:
        return best_guard.get("verdict", "")
    if known_exact > 0 and known_false > 0:
        return "known_supported_overall_conflicted"
    if known_exact > 0:
        return "known_supported_no_guard"
    if known_false > 0:
        return "known_false_without_support"
    return "target_only_no_known_support"


def next_probe_for(best: dict[str, str]) -> str:
    if not best:
        return "derive alternate source family for final small-nonzero external terminal source"
    verdict = best.get("review_verdict", "")
    if verdict == "promotion_ready_guard":
        return "promote final guarded relative small-nonzero external terminal source byte"
    if verdict in {"target_and_known_only_guard", "known_support_reference_false"}:
        return "derive guard separating relative previous-literal repeat reference-false rows"
    if verdict == "known_supported_overall_conflicted":
        return "split relative previous-literal repeat by control and position context"
    return "derive alternate non-oracle source family for final small-nonzero external terminal source"


def build(
    target_rows: list[dict[str, str]],
    gap_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    gap_rows = [row for row in gap_rows if int_value(row, "length") == 1]
    formula_output_rows: list[dict[str, str]] = []
    all_guard_rows: list[dict[str, str]] = []
    all_evaluation_rows: list[dict[str, str]] = []
    issue_rows = 0

    for target in target_rows:
        target_span = target.get("span_key", "")
        target_expected = one_byte_expected(target)
        if target_expected is None:
            issue_rows += 1
            continue
        specs = formula_specs_for_target(target)
        for spec in specs:
            evaluations = [
                evaluation
                for row in gap_rows
                if (evaluation := evaluation_row(target_span, spec, row)) is not None
            ]
            all_evaluation_rows.extend(evaluations)
            known = known_rows(evaluations)
            known_exact = len(exact_rows(known))
            known_false = len(false_rows(known))
            reference = non_target_rows(evaluations, target_span)
            reference_exact = len(exact_rows(reference))
            reference_false = len(false_rows(reference))
            guards = guard_rows_for(target, gap_rows, evaluations, target_span, spec.formula)
            guards.sort(key=sort_guard_key)
            best_guard = guards[0] if guards else {}
            all_guard_rows.extend(guards[:120])
            formula_output_rows.append(
                {
                    "rank": "",
                    "target_span": target_span,
                    "formula": spec.formula,
                    "source_family": spec.source_family,
                    "source_position": spec.source_position,
                    "transform": spec.transform,
                    "parameter": spec.parameter,
                    "target_output_hex": f"{target_expected:02x}",
                    "target_expected_hex": f"{target_expected:02x}",
                    "target_exact": "1",
                    "known_eval_rows": str(len(known)),
                    "known_exact_rows": str(known_exact),
                    "known_false_rows": str(known_false),
                    "reference_eval_rows": str(len(reference)),
                    "reference_exact_rows": str(reference_exact),
                    "reference_false_rows": str(reference_false),
                    "best_guard_key": best_guard.get("guard_key", ""),
                    "best_guard_known_exact_rows": best_guard.get("known_exact_rows", "0"),
                    "best_guard_known_false_rows": best_guard.get("known_false_rows", "0"),
                    "best_guard_reference_exact_rows": best_guard.get("reference_exact_rows", "0"),
                    "best_guard_reference_false_rows": best_guard.get("reference_false_rows", "0"),
                    "review_verdict": formula_verdict(known_exact, known_false, best_guard),
                }
            )

    formula_output_rows.sort(key=sort_formula_key)
    for index, row in enumerate(formula_output_rows, start=1):
        row["rank"] = str(index)
    all_guard_rows.sort(key=sort_guard_key)
    for index, row in enumerate(all_guard_rows, start=1):
        row["rank"] = str(index)
    for index, row in enumerate(all_evaluation_rows, start=1):
        row["rank"] = str(index)

    best = formula_output_rows[0] if formula_output_rows else {}
    promotion_ready = (
        sum(int_value(row, "span_length") for row in target_rows)
        if best.get("review_verdict") == "promotion_ready_guard"
        else 0
    )
    summary = {
        "scope": "total",
        "candidate_mode": "external_terminal_small_nonzero_broader_evidence_probe",
        "target_spans": str(len(target_rows)),
        "target_bytes": str(sum(int_value(row, "span_length") for row in target_rows)),
        "small_gap_rows": str(len(gap_rows)),
        "known_small_gap_rows": str(sum(1 for row in gap_rows if row.get("known_in_replay") == "1")),
        "formula_rows": str(len(formula_output_rows)),
        "target_exact_formula_rows": str(sum(1 for row in formula_output_rows if row.get("target_exact") == "1")),
        "known_supported_formula_rows": str(sum(1 for row in formula_output_rows if int_value(row, "known_exact_rows") > 0)),
        "guard_rows": str(len(all_guard_rows)),
        "false_free_known_guard_rows": str(
            sum(
                1
                for row in all_guard_rows
                if int_value(row, "known_exact_rows") > 0 and int_value(row, "known_false_rows") == 0
            )
        ),
        "best_target_span": best.get("target_span", ""),
        "best_formula": best.get("formula", ""),
        "best_formula_source": best.get("source_family", ""),
        "best_formula_transform": best.get("transform", ""),
        "best_known_exact_rows": best.get("known_exact_rows", "0"),
        "best_known_false_rows": best.get("known_false_rows", "0"),
        "best_guard_family": next(
            (row.get("guard_family", "") for row in all_guard_rows if row.get("guard_key", "") == best.get("best_guard_key", "")),
            "",
        ),
        "best_guard_key": best.get("best_guard_key", ""),
        "best_guard_target_rows": next(
            (row.get("target_rows", "0") for row in all_guard_rows if row.get("guard_key", "") == best.get("best_guard_key", "")),
            "0",
        ),
        "best_guard_known_exact_rows": best.get("best_guard_known_exact_rows", "0"),
        "best_guard_known_false_rows": best.get("best_guard_known_false_rows", "0"),
        "best_guard_reference_exact_rows": best.get("best_guard_reference_exact_rows", "0"),
        "best_guard_reference_false_rows": best.get("best_guard_reference_false_rows", "0"),
        "review_verdict": best.get("review_verdict", ""),
        "next_probe": next_probe_for(best),
        "promotion_candidate_bytes": "0",
        "promotion_ready_bytes": str(promotion_ready),
        "issue_rows": str(issue_rows),
    }
    return summary, formula_output_rows, all_guard_rows, all_evaluation_rows


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 260) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    formula_rows: list[dict[str, str]],
    guard_rows: list[dict[str, str]],
    evaluation_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "formulas": formula_rows,
        "guards": guard_rows,
        "evaluations": evaluation_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("formulas.csv", output_dir / "formulas.csv"),
            ("guards.csv", output_dir / "guards.csv"),
            ("evaluations.csv", output_dir / "evaluations.csv"),
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
  --warn: #f0b36c;
}}
body {{ margin: 0; background: var(--bg); color: var(--text); font: 14px/1.45 system-ui, sans-serif; }}
main {{ width: min(1680px, calc(100vw - 28px)); margin: 0 auto; padding: 22px 0 32px; display: grid; gap: 16px; }}
h1 {{ margin: 0; font-size: 22px; }}
h2 {{ margin: 0 0 10px; font-size: 16px; }}
.muted {{ color: var(--muted); }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 10px; }}
.stat, .panel {{ border: 1px solid var(--line); border-radius: 8px; background: var(--panel); padding: 10px; }}
.value {{ font-size: 22px; font-weight: 760; color: var(--accent); }}
.warn {{ color: var(--warn); }}
.panel {{ overflow-x: auto; }}
table {{ width: 100%; min-width: 1350px; border-collapse: collapse; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
code {{ color: var(--accent); }}
</style>
</head>
<body>
<main>
  <header>
    <h1>{html.escape(title)}</h1>
    <div class="muted">Tests relative neighbor formulas and non-oracle guards for the final small nonzero source byte.</div>
  </header>
  <section class="stats">
    <div class="stat"><div class="muted">Formula rows</div><div class="value">{summary['formula_rows']}</div></div>
    <div class="stat"><div class="muted">Known-supported formulas</div><div class="value">{summary['known_supported_formula_rows']}</div></div>
    <div class="stat"><div class="muted">False-free known guards</div><div class="value warn">{summary['false_free_known_guard_rows']}</div></div>
    <div class="stat"><div class="muted">Best guard false refs</div><div class="value warn">{summary['best_guard_reference_false_rows']}</div></div>
    <div class="stat"><div class="muted">Promotion-ready</div><div class="value warn">{summary['promotion_ready_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2>{links}</section>
  <section class="panel">
    <h2>Verdict</h2>
    <p><code>{html.escape(summary['review_verdict'])}</code></p>
    <p class="muted">Best: <code>{html.escape(summary['best_formula'])}</code> with guard <code>{html.escape(summary['best_guard_key'])}</code>. Next: <code>{html.escape(summary['next_probe'])}</code>.</p>
  </section>
  <section class="panel"><h2>Formulas</h2>{render_table(formula_rows, FORMULA_FIELDNAMES)}</section>
  <section class="panel"><h2>Guards</h2>{render_table(guard_rows, GUARD_FIELDNAMES)}</section>
  <section class="panel"><h2>Evaluations</h2>{render_table(evaluation_rows, EVALUATION_FIELDNAMES)}</section>
  <script type="application/json" id="external-terminal-small-nonzero-broader-evidence-data">{html.escape(data_json)}</script>
</main>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Probe broader relative evidence for final small nonzero external terminal source bytes."
    )
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("--small-gaps", type=Path, default=DEFAULT_SMALL_GAPS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex External Terminal Small Nonzero Broader Evidence Probe",
    )
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    summary, formula_rows, guard_rows, evaluation_rows = build(read_csv(args.targets), read_csv(args.small_gaps))
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "formulas.csv", FORMULA_FIELDNAMES, formula_rows)
    write_csv(args.output / "guards.csv", GUARD_FIELDNAMES, guard_rows)
    write_csv(args.output / "evaluations.csv", EVALUATION_FIELDNAMES, evaluation_rows)
    html_path = args.output / "index.html"
    html_path.write_text(
        build_html(summary, formula_rows, guard_rows, evaluation_rows, args.output, args.title),
        encoding="utf-8",
    )
    print(
        "Small-nonzero broader evidence: "
        f"formulas={summary['formula_rows']} "
        f"best={summary['best_formula']} "
        f"verdict={summary['review_verdict']} "
        f"guard_false={summary['best_guard_reference_false_rows']} "
        f"promotion_ready={summary['promotion_ready_bytes']} "
        f"issues={summary['issue_rows']}"
    )
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
