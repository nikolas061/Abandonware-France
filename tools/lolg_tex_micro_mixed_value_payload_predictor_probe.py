#!/usr/bin/env python3
"""Validate short-context payload predictors for dominant mixed-value rows."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path


DEFAULT_INPUT_ROWS = Path("output/tex_micro_mixed_value_dominant_control/rows.csv")
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_OUTPUT = Path("output/tex_micro_mixed_value_payload_predictor")

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "target_bytes",
    "candidate_rows",
    "best_byte_context",
    "best_byte_correct_slots",
    "best_byte_false_slots",
    "best_byte_precision",
    "best_byte_coverage",
    "best_high_context",
    "best_high_correct_slots",
    "best_high_false_slots",
    "best_high_precision",
    "best_high_coverage",
    "best_low_context",
    "best_low_correct_slots",
    "best_low_false_slots",
    "best_low_precision",
    "best_low_coverage",
    "best_band_context",
    "best_band_correct_slots",
    "best_band_false_slots",
    "best_band_precision",
    "best_band_coverage",
    "high6_baseline_correct_slots",
    "high6_baseline_false_slots",
    "high6_baseline_precision",
    "byte_predictor_rejected",
    "promotion_ready_bytes",
    "issue_rows",
]

CANDIDATE_FIELDNAMES = [
    "rank",
    "target_kind",
    "context_family",
    "contexts",
    "deterministic_repeated_slots",
    "deterministic_singleton_slots",
    "conflicted_slots",
    "loo_correct_slots",
    "loo_false_slots",
    "loo_unknown_slots",
    "loo_precision",
    "loo_coverage",
    "predicted_values",
    "verdict",
    "sample_context",
    "sample_prediction",
]


def read_csv(path: Path) -> list[dict[str, str]]:
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


def ratio(numerator: int, denominator: int) -> str:
    return f"{(numerator / denominator) if denominator else 0.0:.6f}"


def fixture_key(row: dict[str, str] | dict[str, object]) -> tuple[str, str, str]:
    return (
        str(row.get("archive", "")),
        str(row.get("pcx_name", "")),
        str(row.get("frontier_id", "")),
    )


def load_expected_by_fixture(fixture_rows: list[dict[str, str]]) -> tuple[dict[tuple[str, str, str], bytes], list[str]]:
    expected: dict[tuple[str, str, str], bytes] = {}
    issues: list[str] = []
    for fixture in fixture_rows:
        key = fixture_key(fixture)
        if key in expected:
            issues.append(f"duplicate_fixture:{key[0]}:{key[1]}:{key[2]}")
            continue
        path_text = fixture.get("expected_gap_path", "")
        if not path_text:
            issues.append(f"missing_expected_path:{key[0]}:{key[1]}:{key[2]}")
            expected[key] = b""
            continue
        try:
            expected[key] = Path(path_text).read_bytes()
        except OSError as exc:
            issues.append(f"read_expected_failed:{key[0]}:{key[1]}:{key[2]}:{exc}")
            expected[key] = b""
    return expected, issues


def signed_delta(left: int, right: int) -> int:
    return ((right - left + 128) & 0xFF) - 128


def delta_bucket(delta: int | None) -> str:
    if delta is None:
        return "NA"
    magnitude = abs(delta)
    if delta == 0:
        return "Z"
    if magnitude <= 4:
        return "S"
    if magnitude <= 31:
        return "M"
    return "J"


def band_token(value: int) -> str:
    high = value >> 4
    if high in {5, 6, 7, 10}:
        return f"{high:x}"
    return "x"


def build_payloads(
    input_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
) -> tuple[list[tuple[dict[str, str], bytes]], list[str]]:
    expected_by_fixture, fixture_issues = load_expected_by_fixture(fixture_rows)
    output: list[tuple[dict[str, str], bytes]] = []
    issues = list(fixture_issues)
    for row in input_rows:
        expected = expected_by_fixture.get(fixture_key(row), b"")
        if not expected:
            issues.append(f"missing_expected_fixture:{fixture_key(row)}")
        start = int_value(row, "start")
        end = int_value(row, "end")
        payload = expected[start:end]
        if not payload:
            issues.append(f"missing_payload:{fixture_key(row)}:{start}:{end}")
        if row.get("length") and int_value(row, "length") != len(payload):
            issues.append(f"length_mismatch:{fixture_key(row)}:{row.get('length')}:{len(payload)}")
        output.append((row, payload))
    return output, issues


def build_entries(payloads: list[tuple[dict[str, str], bytes]]) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for row_index, (row, payload) in enumerate(payloads):
        control_signal = f"{row.get('control_ref_mod64', '')}|{row.get('best_signal_key', '')}"
        for offset, value in enumerate(payload):
            previous = payload[offset - 1] if offset >= 1 else None
            previous2 = payload[offset - 2] if offset >= 2 else None
            previous_delta = signed_delta(previous2, previous) if previous is not None and previous2 is not None else None
            entries.append(
                {
                    "row_index": row_index,
                    "offset": offset,
                    "length": len(payload),
                    "byte": f"{value:02x}",
                    "high": f"{value >> 4:x}",
                    "low": f"{value & 0x0F:x}",
                    "band": band_token(value),
                    "prev1": f"{previous:02x}" if previous is not None else "START",
                    "prev2": f"{previous2:02x}" if previous2 is not None else "START",
                    "prev1_high": f"{previous >> 4:x}" if previous is not None else "START",
                    "prev1_low": f"{previous & 0x0F:x}" if previous is not None else "START",
                    "prev_delta": delta_bucket(previous_delta),
                    "pos4": str(offset % 4),
                    "pos8": str(offset % 8),
                    "pos16": str((offset * 16) // len(payload)) if payload else "0",
                    "tail8": str(len(payload) - 1 - offset) if len(payload) - 1 - offset < 8 else "body",
                    "signal": row.get("best_signal_key", ""),
                    "control": row.get("control_ref_mod64", ""),
                    "control_signal": control_signal,
                }
            )
    return entries


def context_functions():
    return {
        "prev1": lambda row: (row["prev1"],),
        "prev2": lambda row: (row["prev2"], row["prev1"]),
        "prev1_pos8": lambda row: (row["prev1"], row["pos8"]),
        "prev1_pos16": lambda row: (row["prev1"], row["pos16"]),
        "prev1_delta": lambda row: (row["prev1"], row["prev_delta"]),
        "prev1_signal": lambda row: (row["prev1"], row["signal"]),
        "prev1_control": lambda row: (row["prev1"], row["control"]),
        "prev1_control_signal": lambda row: (row["prev1"], row["control_signal"]),
        "prev2_pos4": lambda row: (row["prev2"], row["prev1"], row["pos4"]),
        "prev2_pos8": lambda row: (row["prev2"], row["prev1"], row["pos8"]),
        "prev2_signal": lambda row: (row["prev2"], row["prev1"], row["signal"]),
        "prev2_control_signal": lambda row: (row["prev2"], row["prev1"], row["control_signal"]),
        "prev1_high_pos16": lambda row: (row["prev1_high"], row["pos16"]),
        "prev1_high_pos8": lambda row: (row["prev1_high"], row["pos8"]),
        "signal_pos8": lambda row: (row["signal"], row["pos8"]),
        "control_pos8": lambda row: (row["control"], row["pos8"]),
        "signal_pos16": lambda row: (row["signal"], row["pos16"]),
        "control_pos16": lambda row: (row["control"], row["pos16"]),
    }


def target_value(entry: dict[str, object], target_kind: str) -> str:
    return str(entry[target_kind])


def strict_prediction(counter: Counter[str]) -> str | None:
    values = [value for value, count in counter.items() if count > 0]
    return values[0] if len(values) == 1 else None


def evaluate_candidate(
    entries: list[dict[str, object]],
    target_kind: str,
    context_family: str,
    context_func,
) -> dict[str, object]:
    grouped: dict[tuple[object, ...], list[dict[str, object]]] = defaultdict(list)
    all_counts: dict[tuple[object, ...], Counter[str]] = defaultdict(Counter)
    row_counts: dict[tuple[int, tuple[object, ...]], Counter[str]] = defaultdict(Counter)
    for entry in entries:
        context = context_func(entry)
        value = target_value(entry, target_kind)
        grouped[context].append(entry)
        all_counts[context][value] += 1
        row_counts[(int(entry["row_index"]), context)][value] += 1

    deterministic_repeated = 0
    deterministic_singleton = 0
    conflicted = 0
    predicted_values: Counter[str] = Counter()
    for context, group in grouped.items():
        prediction = strict_prediction(all_counts[context])
        if prediction is None:
            conflicted += len(group)
            continue
        predicted_values[prediction] += len(group)
        if len(group) > 1:
            deterministic_repeated += len(group)
        else:
            deterministic_singleton += 1

    correct = 0
    false = 0
    unknown = 0
    sample_context = ""
    sample_prediction = ""
    for entry in entries:
        context = context_func(entry)
        train_counts = all_counts[context].copy()
        train_counts.subtract(row_counts[(int(entry["row_index"]), context)])
        train_counts += Counter()
        prediction = strict_prediction(train_counts)
        if prediction is None:
            unknown += 1
            continue
        if not sample_context:
            sample_context = "|".join(str(part) for part in context)
            sample_prediction = prediction
        if prediction == target_value(entry, target_kind):
            correct += 1
        else:
            false += 1

    predicted = correct + false
    if predicted == 0:
        verdict = "no_cross_row_prediction"
    elif target_kind == "byte" and false >= correct:
        verdict = "byte_predictor_reject"
    elif false == 0 and correct > 0:
        verdict = "false_free_review"
    elif target_kind in {"high", "band"} and correct > false:
        verdict = "partial_nibble_hint"
    else:
        verdict = "conflicted_predictor"

    return {
        "rank": 0,
        "target_kind": target_kind,
        "context_family": context_family,
        "contexts": len(grouped),
        "deterministic_repeated_slots": deterministic_repeated,
        "deterministic_singleton_slots": deterministic_singleton,
        "conflicted_slots": conflicted,
        "loo_correct_slots": correct,
        "loo_false_slots": false,
        "loo_unknown_slots": unknown,
        "loo_precision": ratio(correct, predicted),
        "loo_coverage": ratio(predicted, len(entries)),
        "predicted_values": "|".join(
            f"{value}:{count}" for value, count in predicted_values.most_common(8)
        ),
        "verdict": verdict,
        "sample_context": sample_context,
        "sample_prediction": sample_prediction,
    }


def best_candidate(rows: list[dict[str, object]], target_kind: str) -> dict[str, object]:
    target_rows = [
        row
        for row in rows
        if row.get("target_kind") == target_kind and int_value(row, "loo_correct_slots") + int_value(row, "loo_false_slots") > 0
    ]
    if not target_rows:
        return {}
    target_rows.sort(
        key=lambda row: (
            int_value(row, "loo_correct_slots"),
            -int_value(row, "loo_false_slots"),
            float(row.get("loo_precision", "0") or 0),
        ),
        reverse=True,
    )
    return target_rows[0]


def build(
    input_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
) -> tuple[dict[str, object], list[dict[str, object]]]:
    payloads, issues = build_payloads(input_rows, fixture_rows)
    entries = build_entries(payloads)
    candidate_rows: list[dict[str, object]] = []
    for target_kind in ("byte", "high", "low", "band"):
        for context_family, context_func in context_functions().items():
            candidate_rows.append(evaluate_candidate(entries, target_kind, context_family, context_func))

    candidate_rows.sort(
        key=lambda row: (
            str(row["target_kind"]),
            -int_value(row, "loo_correct_slots"),
            int_value(row, "loo_false_slots"),
            str(row["context_family"]),
        )
    )
    for index, row in enumerate(candidate_rows, start=1):
        row["rank"] = index

    best_byte = best_candidate(candidate_rows, "byte")
    best_high = best_candidate(candidate_rows, "high")
    best_low = best_candidate(candidate_rows, "low")
    best_band = best_candidate(candidate_rows, "band")
    high6_correct = sum(1 for entry in entries if entry.get("high") == "6")
    high6_false = len(entries) - high6_correct
    total_bytes = sum(len(payload) for _row, payload in payloads)
    summary = {
        "scope": "total",
        "target_rows": len(payloads),
        "target_bytes": total_bytes,
        "candidate_rows": len(candidate_rows),
        "best_byte_context": best_byte.get("context_family", ""),
        "best_byte_correct_slots": best_byte.get("loo_correct_slots", 0),
        "best_byte_false_slots": best_byte.get("loo_false_slots", 0),
        "best_byte_precision": best_byte.get("loo_precision", "0.000000"),
        "best_byte_coverage": best_byte.get("loo_coverage", "0.000000"),
        "best_high_context": best_high.get("context_family", ""),
        "best_high_correct_slots": best_high.get("loo_correct_slots", 0),
        "best_high_false_slots": best_high.get("loo_false_slots", 0),
        "best_high_precision": best_high.get("loo_precision", "0.000000"),
        "best_high_coverage": best_high.get("loo_coverage", "0.000000"),
        "best_low_context": best_low.get("context_family", ""),
        "best_low_correct_slots": best_low.get("loo_correct_slots", 0),
        "best_low_false_slots": best_low.get("loo_false_slots", 0),
        "best_low_precision": best_low.get("loo_precision", "0.000000"),
        "best_low_coverage": best_low.get("loo_coverage", "0.000000"),
        "best_band_context": best_band.get("context_family", ""),
        "best_band_correct_slots": best_band.get("loo_correct_slots", 0),
        "best_band_false_slots": best_band.get("loo_false_slots", 0),
        "best_band_precision": best_band.get("loo_precision", "0.000000"),
        "best_band_coverage": best_band.get("loo_coverage", "0.000000"),
        "high6_baseline_correct_slots": high6_correct,
        "high6_baseline_false_slots": high6_false,
        "high6_baseline_precision": ratio(high6_correct, len(entries)),
        "byte_predictor_rejected": "1" if int_value(best_byte, "loo_false_slots") >= int_value(best_byte, "loo_correct_slots") else "0",
        "promotion_ready_bytes": 0,
        "issue_rows": len(issues),
    }
    return summary, candidate_rows


def render_table(rows: list[dict[str, object]], fields: list[str], limit: int = 220) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(summary: dict[str, object], candidates: list[dict[str, object]], title: str) -> str:
    data_json = json.dumps({"summary": summary, "candidates": candidates}, indent=2, sort_keys=True)
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body {{ margin: 2rem; background: #111416; color: #edf5f4; font: 14px/1.45 system-ui, sans-serif; }}
table {{ border-collapse: collapse; width: 100%; min-width: 1450px; }}
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
  <div class="box"><div class="num">{summary['best_byte_correct_slots']}/{summary['best_byte_false_slots']}</div><div class="muted">best byte correct/false</div></div>
  <div class="box"><div class="num">{summary['best_high_correct_slots']}/{summary['best_high_false_slots']}</div><div class="muted">best high correct/false</div></div>
  <div class="box"><div class="num">{summary['high6_baseline_precision']}</div><div class="muted">high6 baseline precision</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Candidates</h2>{render_table(candidates, CANDIDATE_FIELDNAMES)}</div>
<script type="application/json" id="payload-predictor-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate short-context predictors for mixed-value payloads.")
    parser.add_argument("--input-rows", type=Path, default=DEFAULT_INPUT_ROWS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Mixed Value Payload Predictor")
    args = parser.parse_args()

    summary, candidates = build(read_csv(args.input_rows), read_csv(args.fixtures))
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "candidates.csv", CANDIDATE_FIELDNAMES, candidates)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, candidates, args.title))

    print(f"Target bytes: {summary['target_bytes']}")
    print(
        f"Best byte predictor: {summary['best_byte_context']} "
        f"{summary['best_byte_correct_slots']}/{summary['best_byte_false_slots']}"
    )
    print(
        f"Best high predictor: {summary['best_high_context']} "
        f"{summary['best_high_correct_slots']}/{summary['best_high_false_slots']}"
    )
    print(f"High6 baseline precision: {summary['high6_baseline_precision']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
