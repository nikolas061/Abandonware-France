#!/usr/bin/env python3
"""Validate threshold support guards for high-row source-byte prerequisites."""

from __future__ import annotations

import argparse
import csv
import html
import json
from pathlib import Path
from typing import Callable

from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_frontier80_clean_prior_high_row_threshold_source_guard_probe")
DEFAULT_PREREQUISITES = Path(
    "output/tex_gap_decoder_frontier80_clean_prior_high_row_source_byte_prereq_probe/source_prerequisites.csv"
)
DEFAULT_CANDIDATES = Path(
    "output/tex_gap_decoder_frontier80_clean_prior_high_row_source_byte_prereq_probe/support_candidates.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "prerequisite_rows",
    "target_rows",
    "false_rows",
    "best_guard",
    "best_guard_correct_rows",
    "best_guard_false_positive_rows",
    "best_guard_false_negative_rows",
    "best_guard_target_hits",
    "best_guard_false_rejects",
    "clean_guards",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

GUARD_FIELDNAMES = [
    "guard_name",
    "feature_family",
    "threshold_hex",
    "correct_rows",
    "false_positive_rows",
    "false_negative_rows",
    "target_hits",
    "false_rejects",
    "predicted_true_rows",
    "predicted_false_rows",
    "clean",
    "notes",
]

PREDICTION_FIELDNAMES = [
    "pair_id",
    "source_id",
    "byte_index",
    "selected_support_value_hex",
    "expected_source_value_hex",
    "selected_delta_abs_gt2",
    "selected_outlier",
    "false_switch",
    "guard_name",
    "predicted_abs_gt2",
    "correct",
    "high_marker_candidate_count",
    "high_marker_support_ids",
    "high_marker_values",
    "selected_candidate_support_id",
    "selected_candidate_value_hex",
    "selected_candidate_delta",
]


PrereqRow = dict[str, str]
CandidateRow = dict[str, str]
Predictor = Callable[[PrereqRow, list[CandidateRow]], tuple[bool, str]]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def hex_value(text: str) -> int:
    return int(text, 16) if text else 0


def hex_byte(value: int) -> str:
    return f"0x{value:02x}"


def row_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("pair_id", ""), row.get("source_id", ""), row.get("byte_index", "")


def grouped_candidates(candidate_rows: list[CandidateRow]) -> dict[tuple[str, str, str], list[CandidateRow]]:
    groups: dict[tuple[str, str, str], list[CandidateRow]] = {}
    for row in candidate_rows:
        groups.setdefault(row_key(row), []).append(row)
    return groups


def candidate_value(row: CandidateRow) -> int:
    return hex_value(row.get("candidate_value_hex", ""))


def candidate_abs_gt2(row: CandidateRow) -> bool:
    return row.get("candidate_abs_gt2", "") == "1"


def select_candidate(candidates: list[CandidateRow], key_name: str) -> CandidateRow | None:
    if not candidates:
        return None
    if key_name == "small_delta_le2":
        return sorted(
            candidates,
            key=lambda row: (-int_value(row, "small_delta_le2_bytes"), -int_value(row, "exact_bytes"), int_value(row, "support_id")),
        )[0]
    if key_name == "exact_bytes":
        return sorted(
            candidates,
            key=lambda row: (-int_value(row, "exact_bytes"), -int_value(row, "small_delta_le2_bytes"), int_value(row, "support_id")),
        )[0]
    if key_name == "known_bytes":
        return sorted(
            candidates,
            key=lambda row: (-int_value(row, "known_bytes"), -int_value(row, "small_delta_le2_bytes"), int_value(row, "support_id")),
        )[0]
    return sorted(candidates, key=lambda row: int_value(row, "support_id"))[0]


def high_marker_predictor(threshold: int) -> Predictor:
    def predict(_row: PrereqRow, candidates: list[CandidateRow]) -> tuple[bool, str]:
        hits = [candidate for candidate in candidates if candidate_value(candidate) >= threshold]
        return bool(hits), ";".join(candidate.get("support_id", "") for candidate in hits[:12])

    return predict


def any_candidate_abs_gt2(_row: PrereqRow, candidates: list[CandidateRow]) -> tuple[bool, str]:
    hits = [candidate for candidate in candidates if candidate_abs_gt2(candidate)]
    return bool(hits), ";".join(candidate.get("support_id", "") for candidate in hits[:12])


def selected_candidate_predictor(key_name: str) -> Predictor:
    def predict(_row: PrereqRow, candidates: list[CandidateRow]) -> tuple[bool, str]:
        selected = select_candidate(candidates, key_name)
        if not selected:
            return False, ""
        return candidate_abs_gt2(selected), selected.get("support_id", "")

    return predict


def guard_specs(candidate_rows: list[CandidateRow]) -> list[tuple[str, str, str, Predictor]]:
    values = sorted({candidate_value(row) for row in candidate_rows if candidate_value(row) >= 0x80})
    thresholds = sorted(set([0x80, 0x90, 0xA0, 0xA8, 0xAA, *values]))
    specs: list[tuple[str, str, str, Predictor]] = []
    for threshold in thresholds:
        specs.append(
            (
                f"has_high_marker_ge_{threshold:02x}",
                "high_marker",
                hex_byte(threshold),
                high_marker_predictor(threshold),
            )
        )
    specs.extend(
        [
            ("has_any_candidate_abs_gt2", "candidate_delta", "", any_candidate_abs_gt2),
            ("select_best_small_delta_le2", "single_candidate", "", selected_candidate_predictor("small_delta_le2")),
            ("select_best_exact_bytes", "single_candidate", "", selected_candidate_predictor("exact_bytes")),
            ("select_best_known_bytes", "single_candidate", "", selected_candidate_predictor("known_bytes")),
            ("select_first_support_id", "single_candidate", "", selected_candidate_predictor("support_id")),
        ]
    )
    return specs


def evaluate_guard(
    prereq_rows: list[PrereqRow],
    candidate_groups: dict[tuple[str, str, str], list[CandidateRow]],
    guard_name: str,
    feature_family: str,
    threshold_hex: str,
    predictor: Predictor,
) -> tuple[dict[str, str], list[dict[str, str]]]:
    predictions: list[dict[str, str]] = []
    false_positive = 0
    false_negative = 0
    target_hits = 0
    false_rejects = 0
    predicted_true = 0
    for row in prereq_rows:
        candidates = candidate_groups.get(row_key(row), [])
        expected = row.get("selected_delta_abs_gt2", "") == "1"
        predicted, selected_id = predictor(row, candidates)
        high_hits = [candidate for candidate in candidates if candidate_value(candidate) >= 0xA0]
        selected = next((candidate for candidate in candidates if candidate.get("support_id", "") == selected_id), {})
        if predicted:
            predicted_true += 1
        if predicted and not expected:
            false_positive += 1
        if expected and not predicted:
            false_negative += 1
        if expected and predicted:
            target_hits += 1
        if row.get("false_switch", "") == "1" and not predicted:
            false_rejects += 1
        predictions.append(
            {
                "pair_id": row.get("pair_id", ""),
                "source_id": row.get("source_id", ""),
                "byte_index": row.get("byte_index", ""),
                "selected_support_value_hex": row.get("selected_support_value_hex", ""),
                "expected_source_value_hex": row.get("expected_source_value_hex", ""),
                "selected_delta_abs_gt2": row.get("selected_delta_abs_gt2", ""),
                "selected_outlier": row.get("selected_outlier", ""),
                "false_switch": row.get("false_switch", ""),
                "guard_name": guard_name,
                "predicted_abs_gt2": "1" if predicted else "0",
                "correct": "1" if predicted == expected else "0",
                "high_marker_candidate_count": str(len(high_hits)),
                "high_marker_support_ids": ";".join(candidate.get("support_id", "") for candidate in high_hits[:12]),
                "high_marker_values": ";".join(sorted({candidate.get("candidate_value_hex", "") for candidate in high_hits})),
                "selected_candidate_support_id": selected.get("support_id", selected_id),
                "selected_candidate_value_hex": selected.get("candidate_value_hex", ""),
                "selected_candidate_delta": selected.get("candidate_delta", ""),
            }
        )
    correct_rows = len(prereq_rows) - false_positive - false_negative
    guard = {
        "guard_name": guard_name,
        "feature_family": feature_family,
        "threshold_hex": threshold_hex,
        "correct_rows": str(correct_rows),
        "false_positive_rows": str(false_positive),
        "false_negative_rows": str(false_negative),
        "target_hits": str(target_hits),
        "false_rejects": str(false_rejects),
        "predicted_true_rows": str(predicted_true),
        "predicted_false_rows": str(len(prereq_rows) - predicted_true),
        "clean": "1" if false_positive == 0 and false_negative == 0 else "0",
        "notes": selected_id if len(prereq_rows) == 1 else "",
    }
    return guard, predictions


def build_reports(
    prereq_rows: list[PrereqRow],
    candidate_rows: list[CandidateRow],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    candidate_groups = grouped_candidates(candidate_rows)
    guard_rows: list[dict[str, str]] = []
    prediction_by_guard: dict[str, list[dict[str, str]]] = {}
    for guard_name, feature_family, threshold_hex, predictor in guard_specs(candidate_rows):
        guard, predictions = evaluate_guard(
            prereq_rows,
            candidate_groups,
            guard_name,
            feature_family,
            threshold_hex,
            predictor,
        )
        guard_rows.append(guard)
        prediction_by_guard[guard_name] = predictions
    family_priority = {"high_marker": 0, "candidate_delta": 1, "single_candidate": 2}
    def threshold_priority(row: dict[str, str]) -> int:
        if row.get("feature_family") != "high_marker" or not row.get("threshold_hex"):
            return 0
        return abs(hex_value(row.get("threshold_hex", "")) - 0xA0)

    guard_rows.sort(
        key=lambda row: (
            row.get("clean", "") != "1",
            -int_value(row, "correct_rows"),
            int_value(row, "false_positive_rows"),
            int_value(row, "false_negative_rows"),
            family_priority.get(row.get("feature_family", ""), 10),
            threshold_priority(row),
            row.get("guard_name", ""),
        )
    )
    best = guard_rows[0] if guard_rows else {}
    best_predictions = prediction_by_guard.get(best.get("guard_name", ""), [])
    clean_guards = [row for row in guard_rows if row.get("clean") == "1"]
    target_rows = [row for row in prereq_rows if row.get("selected_delta_abs_gt2") == "1"]
    false_rows = [row for row in prereq_rows if row.get("false_switch") == "1"]
    if best.get("clean") == "1" and best.get("feature_family") == "high_marker":
        verdict = "frontier80_prior_high_row_threshold_source_guard_ready"
        next_probe = "promote threshold source guard into byte-local high-row selector replay"
    elif best.get("clean") == "1":
        verdict = "frontier80_prior_high_row_threshold_source_guard_clean_but_weak"
        next_probe = "validate stronger high-marker source guard for selected-delta high-row split"
    else:
        verdict = "frontier80_prior_high_row_threshold_source_guard_weak"
        next_probe = "derive stronger source-byte threshold guard for selected-delta high-row split"
    summary = {
        "scope": "total",
        "prerequisite_rows": str(len(prereq_rows)),
        "target_rows": str(len(target_rows)),
        "false_rows": str(len(false_rows)),
        "best_guard": best.get("guard_name", ""),
        "best_guard_correct_rows": best.get("correct_rows", "0"),
        "best_guard_false_positive_rows": best.get("false_positive_rows", "0"),
        "best_guard_false_negative_rows": best.get("false_negative_rows", "0"),
        "best_guard_target_hits": best.get("target_hits", "0"),
        "best_guard_false_rejects": best.get("false_rejects", "0"),
        "clean_guards": str(len(clean_guards)),
        "issue_rows": "0",
        "review_verdict": verdict,
        "next_probe": next_probe,
    }
    return summary, guard_rows, best_predictions


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 240) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    guard_rows: list[dict[str, str]],
    prediction_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "guards": guard_rows, "predictions": prediction_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("guard_candidates.csv", output_dir / "guard_candidates.csv"),
            ("guard_predictions.csv", output_dir / "guard_predictions.csv"),
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
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  min-height: 100vh;
  background: var(--bg);
  color: var(--text);
  font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}}
.wrap {{ width: min(1680px, calc(100vw - 28px)); margin: 0 auto; }}
header {{ border-bottom: 1px solid var(--line); background: #12191b; padding: 18px 0 14px; }}
h1 {{ margin: 0; font-size: 21px; font-weight: 720; letter-spacing: 0; }}
h2 {{ margin: 0 0 10px; font-size: 16px; }}
.sub {{ color: var(--muted); margin-top: 4px; }}
main {{ padding: 16px 0 28px; display: grid; gap: 16px; }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 10px; }}
.stat, .panel {{ border: 1px solid var(--line); border-radius: 8px; background: var(--panel); padding: 10px; }}
.label, .muted {{ color: var(--muted); }}
.value {{ font-size: 22px; font-weight: 760; line-height: 1.05; margin-top: 4px; }}
.panel {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; min-width: 1180px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Validates non-oracle high-marker guards for source-byte threshold selection.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Best guard</div><div class="value">{html.escape(summary['best_guard'])}</div></div>
    <div class="stat"><div class="label">Correct</div><div class="value">{html.escape(summary['best_guard_correct_rows'])}/{html.escape(summary['prerequisite_rows'])}</div></div>
    <div class="stat"><div class="label">False positive</div><div class="value">{html.escape(summary['best_guard_false_positive_rows'])}</div></div>
    <div class="stat"><div class="label">False negative</div><div class="value">{html.escape(summary['best_guard_false_negative_rows'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div><div class="sub">{html.escape(summary['review_verdict'])}: {html.escape(summary['next_probe'])}</div></section>
  <section class="panel"><h2>Guard candidates</h2>{render_table(guard_rows, GUARD_FIELDNAMES)}</section>
  <section class="panel"><h2>Best guard predictions</h2>{render_table(prediction_rows, PREDICTION_FIELDNAMES)}</section>
</main>
<script type="application/json" id="threshold-source-guard-data">{data_json}</script>
</body>
</html>
"""


def write_report(output_dir: Path, prerequisites_path: Path, candidates_path: Path, *, title: str) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    prereq_rows = read_csv(prerequisites_path)
    candidate_rows = read_csv(candidates_path)
    summary, guard_rows, prediction_rows = build_reports(prereq_rows, candidate_rows)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "guard_candidates.csv", GUARD_FIELDNAMES, guard_rows)
    write_csv(output_dir / "guard_predictions.csv", PREDICTION_FIELDNAMES, prediction_rows)
    (output_dir / "issues.txt").write_text("")
    (output_dir / "index.html").write_text(build_html(summary, guard_rows, prediction_rows, output_dir, title))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate high-row threshold source guards.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--prerequisites", type=Path, default=DEFAULT_PREREQUISITES)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Prior High Row Threshold Source Guard Probe",
    )
    args = parser.parse_args()

    summary = write_report(args.output, args.prerequisites, args.candidates, title=args.title)
    print(f"Best guard: {summary['best_guard']}")
    print(f"Correct: {summary['best_guard_correct_rows']}/{summary['prerequisite_rows']}")
    print(f"False positive: {summary['best_guard_false_positive_rows']}")
    print(f"False negative: {summary['best_guard_false_negative_rows']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
