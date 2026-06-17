#!/usr/bin/env python3
"""Review tiny sequence-state mixed-value high/low candidates before promotion."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_micro_mixed_value_payload_predictor_probe import int_value, read_csv, strict_prediction, write_csv
from lolg_tex_micro_mixed_value_payload_sequence_state_probe import DEFAULT_OUTPUT as DEFAULT_SEQUENCE_OUTPUT


DEFAULT_INPUT_ROWS = Path("output/tex_micro_mixed_value_dominant_control/rows.csv")
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_REPLAY_FIXTURES = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_fill_replay/fixtures.csv")
DEFAULT_SEQUENCE_SUMMARY = DEFAULT_SEQUENCE_OUTPUT / "summary.csv"
DEFAULT_SELECTED_ROWS = DEFAULT_SEQUENCE_OUTPUT / "selected_rows.csv"
DEFAULT_SELECTED_LOW_CANDIDATES = DEFAULT_SEQUENCE_OUTPUT / "selected_low_candidates.csv"
DEFAULT_OUTPUT = Path("output/tex_micro_mixed_value_payload_sequence_candidate_review")

SUMMARY_FIELDNAMES = [
    "scope",
    "high_feature_set",
    "low_feature_set",
    "selected_high_slots",
    "candidate_bytes",
    "candidate_contexts",
    "candidate_source_rows",
    "predicted_bytes",
    "correct_bytes",
    "false_bytes",
    "prerequisite_bytes",
    "known_prerequisite_bytes",
    "unknown_prerequisite_bytes",
    "oracle_dependency_bytes",
    "replay_ready_bytes",
    "promotion_ready_bytes",
    "verdict",
    "issue_rows",
]

ROW_FIELDNAMES = [
    "rank",
    "row_index",
    "archive",
    "pcx_name",
    "frontier_id",
    "span_index",
    "op_index",
    "start",
    "end",
    "offset",
    "byte",
    "high_prediction",
    "low_prediction",
    "predicted_byte",
    "matched",
    "high_context",
    "low_context",
    "training_rows",
    "training_slots",
    "training_lows",
    "prerequisite_offsets",
    "known_prerequisites",
    "unknown_prerequisites",
    "decoded_prerequisites",
    "actual_prerequisites",
    "verdict",
    "issues",
]


def fixture_key(row: dict[str, str]) -> tuple[str, str, str]:
    return (row.get("archive", ""), row.get("pcx_name", ""), row.get("frontier_id", ""))


def read_summary(path: Path) -> dict[str, str]:
    rows = read_csv(path)
    return rows[0] if rows else {}


def read_bytes(path_text: str, issues: list[str], label: str) -> bytes:
    if not path_text:
        issues.append(f"missing_{label}_path")
        return b""
    try:
        return Path(path_text).read_bytes()
    except OSError as exc:
        issues.append(f"read_{label}_failed:{exc}")
        return b""


def enriched_selected_rows(
    selected_rows: list[dict[str, str]],
    input_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for row in selected_rows:
        enriched = dict(row)
        source = input_rows[int_value(row, "row_index")] if row.get("row_index", "").isdigit() else {}
        offset = int_value(row, "offset")
        length = int_value(row, "end") - int_value(row, "start")
        enriched["signal"] = source.get("best_signal_key", "")
        enriched["control"] = source.get("control_ref_mod64", "")
        enriched["dominant"] = source.get("dominant_byte_hex", "")
        enriched["pos4"] = str(offset % 4)
        enriched["pos8"] = str(offset % 8)
        enriched["tail4"] = str(length - 1 - offset) if length - 1 - offset < 4 else "body"
        output.append(enriched)
    return output


def context_for(row: dict[str, str], feature_set: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(row.get(feature, "") for feature in feature_set)


def training_counts(
    selected_rows: list[dict[str, str]],
    feature_set: tuple[str, ...],
) -> tuple[dict[tuple[str, ...], Counter[str]], dict[tuple[int, tuple[str, ...]], Counter[str]]]:
    all_counts: dict[tuple[str, ...], Counter[str]] = defaultdict(Counter)
    row_counts: dict[tuple[int, tuple[str, ...]], Counter[str]] = defaultdict(Counter)
    for row in selected_rows:
        context = context_for(row, feature_set)
        value = row.get("low", "")
        all_counts[context][value] += 1
        row_counts[(int_value(row, "row_index"), context)][value] += 1
    return all_counts, row_counts


def prerequisite_offsets(row: dict[str, str]) -> list[int]:
    offset = int_value(row, "offset")
    if offset < 2:
        return []
    return [int_value(row, "start") + offset - 2, int_value(row, "start") + offset - 1]


def byte_at(data: bytes, offset: int) -> str:
    if 0 <= offset < len(data):
        return f"{data[offset]:02x}"
    return "NA"


def review_candidates(
    selected_rows: list[dict[str, str]],
    input_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    replay_rows: list[dict[str, str]],
    sequence_summary: dict[str, str],
) -> tuple[dict[str, object], list[dict[str, object]]]:
    low_feature_set = tuple(
        part for part in sequence_summary.get("best_false_free_selected_low_feature_set", "").split("+") if part
    )
    high_feature_set = sequence_summary.get("best_false_free_high_feature_set", "")
    enriched_rows = enriched_selected_rows(selected_rows, input_rows)
    all_counts, row_counts = training_counts(enriched_rows, low_feature_set)
    fixtures = {fixture_key(row): row for row in fixture_rows}
    replays = {fixture_key(row): row for row in replay_rows}

    reviewed: list[dict[str, object]] = []
    issue_rows = 0
    for row in enriched_rows:
        context = context_for(row, low_feature_set)
        counts = all_counts[context].copy()
        counts.subtract(row_counts[(int_value(row, "row_index"), context)])
        counts += Counter()
        prediction = strict_prediction(counts)
        if prediction is None:
            continue

        predicted_byte = f"{row.get('high_prediction', '')}{prediction}"
        matched = predicted_byte == row.get("byte", "")
        key = fixture_key(row)
        local_issues: list[str] = []
        expected = read_bytes(fixtures.get(key, {}).get("expected_gap_path", ""), local_issues, "expected")
        known_mask = read_bytes(replays.get(key, {}).get("known_mask_path", ""), local_issues, "known_mask")
        decoded = read_bytes(replays.get(key, {}).get("decoded_path", ""), local_issues, "decoded")

        prereq_offsets = prerequisite_offsets(row)
        known_values: list[str] = []
        decoded_values: list[str] = []
        actual_values: list[str] = []
        known_count = 0
        for offset in prereq_offsets:
            known = 1 if 0 <= offset < len(known_mask) and known_mask[offset] else 0
            known_count += known
            known_values.append(str(known))
            decoded_values.append(byte_at(decoded, offset))
            actual_values.append(byte_at(expected, offset))
        unknown_count = len(prereq_offsets) - known_count
        if local_issues:
            issue_rows += 1
        if not matched:
            verdict = "candidate_false"
        elif unknown_count:
            verdict = "oracle_previous_bytes_unavailable"
        else:
            verdict = "replay_ready_candidate"

        reviewed.append(
            {
                "rank": len(reviewed) + 1,
                "row_index": row.get("row_index", ""),
                "archive": row.get("archive", ""),
                "pcx_name": row.get("pcx_name", ""),
                "frontier_id": row.get("frontier_id", ""),
                "span_index": row.get("span_index", ""),
                "op_index": row.get("op_index", ""),
                "start": row.get("start", ""),
                "end": row.get("end", ""),
                "offset": row.get("offset", ""),
                "byte": row.get("byte", ""),
                "high_prediction": row.get("high_prediction", ""),
                "low_prediction": prediction,
                "predicted_byte": predicted_byte,
                "matched": 1 if matched else 0,
                "high_context": row.get("high_context", ""),
                "low_context": "|".join(context),
                "training_rows": len(
                    {
                        candidate.get("row_index", "")
                        for candidate in enriched_rows
                        if context_for(candidate, low_feature_set) == context
                        and candidate.get("row_index", "") != row.get("row_index", "")
                    }
                ),
                "training_slots": sum(counts.values()),
                "training_lows": "|".join(f"{value}:{count}" for value, count in counts.most_common()),
                "prerequisite_offsets": "|".join(str(offset) for offset in prereq_offsets),
                "known_prerequisites": "|".join(known_values),
                "unknown_prerequisites": unknown_count,
                "decoded_prerequisites": "|".join(decoded_values),
                "actual_prerequisites": "|".join(actual_values),
                "verdict": verdict,
                "issues": ";".join(local_issues),
            }
        )

    predicted_bytes = Counter(str(row["predicted_byte"]) for row in reviewed)
    prerequisite_bytes = sum(
        1 for row in reviewed for value in str(row.get("known_prerequisites", "")).split("|") if value
    )
    known_prerequisite_bytes = sum(
        1 for row in reviewed for value in str(row.get("known_prerequisites", "")).split("|") if value == "1"
    )
    unknown_prerequisite_bytes = sum(int_value(row, "unknown_prerequisites") for row in reviewed)
    replay_ready = [row for row in reviewed if row.get("verdict") == "replay_ready_candidate"]
    false_rows = [row for row in reviewed if row.get("matched") != 1]
    if false_rows:
        verdict = "candidate_false_reject"
    elif unknown_prerequisite_bytes:
        verdict = "oracle_sequence_dependency_reject"
    elif replay_ready:
        verdict = "replay_ready_review"
    else:
        verdict = "no_review_candidates"

    summary = {
        "scope": "total",
        "high_feature_set": high_feature_set,
        "low_feature_set": "+".join(low_feature_set),
        "selected_high_slots": sequence_summary.get("selected_high_slots", "0"),
        "candidate_bytes": len(reviewed),
        "candidate_contexts": len({row.get("low_context", "") for row in reviewed}),
        "candidate_source_rows": len({row.get("row_index", "") for row in reviewed}),
        "predicted_bytes": "|".join(f"{value}:{count}" for value, count in predicted_bytes.most_common()),
        "correct_bytes": sum(1 for row in reviewed if row.get("matched") == 1),
        "false_bytes": len(false_rows),
        "prerequisite_bytes": prerequisite_bytes,
        "known_prerequisite_bytes": known_prerequisite_bytes,
        "unknown_prerequisite_bytes": unknown_prerequisite_bytes,
        "oracle_dependency_bytes": sum(1 for row in reviewed if int_value(row, "unknown_prerequisites") > 0),
        "replay_ready_bytes": len(replay_ready),
        "promotion_ready_bytes": 0,
        "verdict": verdict,
        "issue_rows": issue_rows,
    }
    return summary, reviewed


def render_table(rows: list[dict[str, object]], fields: list[str], limit: int = 160) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(summary: dict[str, object], rows: list[dict[str, object]], title: str) -> str:
    data_json = json.dumps({"summary": summary, "rows": rows}, indent=2, sort_keys=True)
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
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<div class="grid">
  <div class="box"><div class="num">{summary['candidate_bytes']}</div><div class="muted">candidate bytes</div></div>
  <div class="box"><div class="num">{summary['correct_bytes']}/{summary['false_bytes']}</div><div class="muted">correct/false oracle bytes</div></div>
  <div class="box"><div class="num">{summary['known_prerequisite_bytes']}/{summary['prerequisite_bytes']}</div><div class="muted">known prerequisites</div></div>
  <div class="box"><div class="num">{summary['replay_ready_bytes']}</div><div class="muted">replay-ready bytes</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Reviewed candidates</h2>{render_table(rows, ROW_FIELDNAMES)}</div>
<script type="application/json" id="mixed-value-sequence-candidate-review-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Review tiny mixed-value sequence candidates.")
    parser.add_argument("--input-rows", type=Path, default=DEFAULT_INPUT_ROWS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--replay-fixtures", type=Path, default=DEFAULT_REPLAY_FIXTURES)
    parser.add_argument("--sequence-summary", type=Path, default=DEFAULT_SEQUENCE_SUMMARY)
    parser.add_argument("--selected-rows", type=Path, default=DEFAULT_SELECTED_ROWS)
    parser.add_argument("--selected-low-candidates", type=Path, default=DEFAULT_SELECTED_LOW_CANDIDATES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Mixed Value Sequence Candidate Review")
    args = parser.parse_args()

    summary, rows = review_candidates(
        read_csv(args.selected_rows),
        read_csv(args.input_rows),
        read_csv(args.fixtures),
        read_csv(args.replay_fixtures),
        read_summary(args.sequence_summary),
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "rows.csv", ROW_FIELDNAMES, rows)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, rows, args.title))

    print(f"Candidate bytes: {summary['candidate_bytes']}")
    print(f"Correct/false oracle bytes: {summary['correct_bytes']}/{summary['false_bytes']}")
    print(f"Known prerequisites: {summary['known_prerequisite_bytes']}/{summary['prerequisite_bytes']}")
    print(f"Replay-ready bytes: {summary['replay_ready_bytes']}")
    print(f"Verdict: {summary['verdict']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
