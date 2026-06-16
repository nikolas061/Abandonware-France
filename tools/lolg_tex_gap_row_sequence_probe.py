#!/usr/bin/env python3
"""Probe row-to-row source-start sequences for .tex gap candidates."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_row_sequence_probe")
DEFAULT_CANDIDATES = Path("output/tex_gap_row_delta_probe/candidates.csv")
DEFAULT_ROW_CONTROLS = Path("output/tex_gap_row_control_probe/row_controls.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "selected_candidates",
    "row_sequence_rows",
    "fixtures",
    "valid_sequence_rows",
    "source_step_groups",
    "valid_source_step_groups",
    "dominant_source_step",
    "dominant_source_step_rows",
    "dominant_valid_source_step",
    "dominant_valid_source_step_rows",
    "stride_step_rows",
    "prev_nonzero_step_rows",
    "current_nonzero_step_rows",
    "repeat_start_rows",
    "rewind_rows",
    "monotonic_candidates",
    "strict_monotonic_candidates",
    "issue_rows",
]

CANDIDATE_FIELDNAMES = [
    "selection_id",
    "rank",
    "rule_type",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "frontier_type",
    "payload_offset",
    "source_mode",
    "row_stride",
    "row_prefix_skip",
    "row_control_rows",
    "row_sequence_rows",
    "valid_sequence_rows",
    "unique_source_steps",
    "dominant_source_step",
    "dominant_source_step_rows",
    "source_step_min",
    "source_step_max",
    "stride_step_rows",
    "prev_nonzero_step_rows",
    "current_nonzero_step_rows",
    "repeat_start_rows",
    "rewind_rows",
    "monotonic",
    "strict_monotonic",
    "adjusted_nonzero_exact_slots",
    "adjusted_nonzero_exact_ratio",
    "issue_notes",
    "issues",
]

TRANSITION_FIELDNAMES = [
    "selection_id",
    "rank",
    "pcx_name",
    "frontier_id",
    "source_mode",
    "row_stride",
    "row_prefix_skip",
    "prev_row_index",
    "row_index",
    "prev_best_source_start",
    "best_source_start",
    "source_step",
    "prev_best_delta",
    "best_delta",
    "delta_step",
    "prev_nonzero_slots",
    "nonzero_slots",
    "prev_adjusted_nonzero_exact_slots",
    "adjusted_nonzero_exact_slots",
    "adjusted_exact_step",
    "step_class",
    "step_matches",
    "valid_transition",
    "issues",
]

STEP_FIELDNAMES = [
    "source_step",
    "rows",
    "valid_rows",
    "candidates",
    "fixtures",
    "step_classes",
    "match_types",
    "min_delta_step",
    "max_delta_step",
    "avg_delta_step",
    "nonzero_slots",
    "adjusted_nonzero_exact_slots",
    "adjusted_nonzero_exact_ratio",
    "sample_pcx",
    "sample_frontier_id",
    "sample_selection_id",
    "sample_row_index",
]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def fixture_key(row: dict[str, str]) -> tuple[str, str, str]:
    return (row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", ""))


def split_values(value: str) -> list[str]:
    return [part for part in value.split(";") if part]


def has_range_issue(row: dict[str, str]) -> bool:
    issues = set(split_values(row.get("issues", "")))
    return bool({"negative_best_source_start", "best_source_start_out_of_range"} & issues)


def row_control_lookup(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    output: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        output[row.get("selection_id", "")].append(row)
    for grouped in output.values():
        grouped.sort(key=lambda row: int_value(row, "row_index"))
    return output


def step_match_values(
    source_step: int,
    *,
    row_stride: int,
    prev_nonzero_slots: int,
    nonzero_slots: int,
) -> list[str]:
    matches: list[str] = []
    if row_stride and source_step == row_stride:
        matches.append("row_stride")
    if prev_nonzero_slots and source_step == prev_nonzero_slots:
        matches.append("prev_nonzero_slots")
    if nonzero_slots and source_step == nonzero_slots:
        matches.append("current_nonzero_slots")
    return matches


def classify_step(
    source_step: int,
    *,
    row_stride: int,
    prev_nonzero_slots: int,
    nonzero_slots: int,
) -> str:
    matches = step_match_values(
        source_step,
        row_stride=row_stride,
        prev_nonzero_slots=prev_nonzero_slots,
        nonzero_slots=nonzero_slots,
    )
    if matches:
        return matches[0]
    if source_step < 0:
        return "rewind"
    if source_step == 0:
        return "repeat_start"
    if row_stride and source_step > row_stride:
        return "forward_over_stride"
    return "forward_variable"


def analyze_candidate(
    candidate: dict[str, str],
    row_controls: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]]]:
    notes: list[str] = []
    issues: list[str] = []
    transition_rows: list[dict[str, str]] = []
    row_stride = int_value(candidate, "row_stride")
    step_counts: Counter[int] = Counter()
    valid_count = 0
    stride_step_rows = 0
    prev_nonzero_step_rows = 0
    current_nonzero_step_rows = 0
    repeat_start_rows = 0
    rewind_rows = 0
    adjusted_total = sum(int_value(row, "adjusted_nonzero_exact_slots") for row in row_controls)
    nonzero_total = sum(int_value(row, "nonzero_slots") for row in row_controls)

    if len(row_controls) < 2:
        notes.append("not_enough_rows")

    for previous, current in zip(row_controls, row_controls[1:]):
        prev_start = int_value(previous, "best_source_start")
        current_start = int_value(current, "best_source_start")
        source_step = current_start - prev_start
        prev_delta = int_value(previous, "best_delta")
        current_delta = int_value(current, "best_delta")
        prev_nonzero = int_value(previous, "nonzero_slots")
        current_nonzero = int_value(current, "nonzero_slots")
        matches = step_match_values(
            source_step,
            row_stride=row_stride,
            prev_nonzero_slots=prev_nonzero,
            nonzero_slots=current_nonzero,
        )
        step_class = classify_step(
            source_step,
            row_stride=row_stride,
            prev_nonzero_slots=prev_nonzero,
            nonzero_slots=current_nonzero,
        )
        row_issues: list[str] = []
        if has_range_issue(previous):
            row_issues.append("prev_start_range_issue")
        if has_range_issue(current):
            row_issues.append("current_start_range_issue")
        valid_transition = not row_issues

        step_counts[source_step] += 1
        if valid_transition:
            valid_count += 1
        if "row_stride" in matches:
            stride_step_rows += 1
        if "prev_nonzero_slots" in matches:
            prev_nonzero_step_rows += 1
        if "current_nonzero_slots" in matches:
            current_nonzero_step_rows += 1
        if source_step == 0:
            repeat_start_rows += 1
        if source_step < 0:
            rewind_rows += 1

        transition_rows.append(
            {
                "selection_id": candidate.get("selection_id", ""),
                "rank": candidate.get("rank", ""),
                "pcx_name": candidate.get("pcx_name", ""),
                "frontier_id": candidate.get("frontier_id", ""),
                "source_mode": candidate.get("source_mode", ""),
                "row_stride": candidate.get("row_stride", ""),
                "row_prefix_skip": candidate.get("row_prefix_skip", ""),
                "prev_row_index": previous.get("row_index", ""),
                "row_index": current.get("row_index", ""),
                "prev_best_source_start": previous.get("best_source_start", ""),
                "best_source_start": current.get("best_source_start", ""),
                "source_step": str(source_step),
                "prev_best_delta": previous.get("best_delta", ""),
                "best_delta": current.get("best_delta", ""),
                "delta_step": str(current_delta - prev_delta),
                "prev_nonzero_slots": previous.get("nonzero_slots", ""),
                "nonzero_slots": current.get("nonzero_slots", ""),
                "prev_adjusted_nonzero_exact_slots": previous.get("adjusted_nonzero_exact_slots", ""),
                "adjusted_nonzero_exact_slots": current.get("adjusted_nonzero_exact_slots", ""),
                "adjusted_exact_step": str(
                    int_value(current, "adjusted_nonzero_exact_slots")
                    - int_value(previous, "adjusted_nonzero_exact_slots")
                ),
                "step_class": step_class,
                "step_matches": ";".join(matches),
                "valid_transition": "1" if valid_transition else "0",
                "issues": ";".join(row_issues),
            }
        )

    if step_counts:
        dominant_step, dominant_rows = step_counts.most_common(1)[0]
        step_min = min(step_counts)
        step_max = max(step_counts)
    else:
        dominant_step, dominant_rows, step_min, step_max = 0, 0, 0, 0
    monotonic = "1" if transition_rows and rewind_rows == 0 else "0"
    strict_monotonic = "1" if transition_rows and rewind_rows == 0 and repeat_start_rows == 0 else "0"
    if len(step_counts) > 16:
        notes.append("many_source_steps")
    if rewind_rows:
        notes.append("has_rewinds")

    candidate_row = {
        "selection_id": candidate.get("selection_id", ""),
        "rank": candidate.get("rank", ""),
        "rule_type": candidate.get("rule_type", ""),
        "archive": candidate.get("archive", ""),
        "archive_tag": candidate.get("archive_tag", ""),
        "pcx_name": candidate.get("pcx_name", ""),
        "frontier_id": candidate.get("frontier_id", ""),
        "frontier_type": candidate.get("frontier_type", ""),
        "payload_offset": candidate.get("payload_offset", ""),
        "source_mode": candidate.get("source_mode", ""),
        "row_stride": candidate.get("row_stride", ""),
        "row_prefix_skip": candidate.get("row_prefix_skip", ""),
        "row_control_rows": str(len(row_controls)),
        "row_sequence_rows": str(len(transition_rows)),
        "valid_sequence_rows": str(valid_count),
        "unique_source_steps": str(len(step_counts)),
        "dominant_source_step": str(dominant_step),
        "dominant_source_step_rows": str(dominant_rows),
        "source_step_min": str(step_min),
        "source_step_max": str(step_max),
        "stride_step_rows": str(stride_step_rows),
        "prev_nonzero_step_rows": str(prev_nonzero_step_rows),
        "current_nonzero_step_rows": str(current_nonzero_step_rows),
        "repeat_start_rows": str(repeat_start_rows),
        "rewind_rows": str(rewind_rows),
        "monotonic": monotonic,
        "strict_monotonic": strict_monotonic,
        "adjusted_nonzero_exact_slots": str(adjusted_total),
        "adjusted_nonzero_exact_ratio": f"{(adjusted_total / nonzero_total) if nonzero_total else 0.0:.6f}",
        "issue_notes": ";".join(sorted(set(notes))),
        "issues": ";".join(issues),
    }
    return candidate_row, transition_rows


def build_step_rows(transition_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in transition_rows:
        grouped[row.get("source_step", "")].append(row)

    step_rows: list[dict[str, str]] = []
    for source_step, rows in grouped.items():
        sample = rows[0]
        delta_steps = [int_value(row, "delta_step") for row in rows]
        nonzero_slots = sum(int_value(row, "nonzero_slots") for row in rows)
        adjusted = sum(int_value(row, "adjusted_nonzero_exact_slots") for row in rows)
        step_rows.append(
            {
                "source_step": source_step,
                "rows": str(len(rows)),
                "valid_rows": str(sum(int_value(row, "valid_transition") for row in rows)),
                "candidates": str(len({row.get("selection_id", "") for row in rows})),
                "fixtures": str(len({fixture_key(row) for row in rows})),
                "step_classes": ";".join(sorted({row.get("step_class", "") for row in rows if row.get("step_class", "")})),
                "match_types": ";".join(
                    sorted({match for row in rows for match in split_values(row.get("step_matches", ""))})
                ),
                "min_delta_step": str(min(delta_steps) if delta_steps else 0),
                "max_delta_step": str(max(delta_steps) if delta_steps else 0),
                "avg_delta_step": f"{(sum(delta_steps) / len(delta_steps)) if delta_steps else 0.0:.3f}",
                "nonzero_slots": str(nonzero_slots),
                "adjusted_nonzero_exact_slots": str(adjusted),
                "adjusted_nonzero_exact_ratio": f"{(adjusted / nonzero_slots) if nonzero_slots else 0.0:.6f}",
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
                "sample_selection_id": sample.get("selection_id", ""),
                "sample_row_index": sample.get("row_index", ""),
            }
        )
    return sorted(step_rows, key=lambda row: (int_value(row, "rows"), int_value(row, "valid_rows")), reverse=True)


def build_rows(
    candidates: Path,
    row_controls: Path,
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    controls_by_selection = row_control_lookup(read_rows(row_controls))
    candidate_rows: list[dict[str, str]] = []
    transition_rows: list[dict[str, str]] = []
    for candidate in read_rows(candidates):
        analyzed, rows = analyze_candidate(candidate, controls_by_selection.get(candidate.get("selection_id", ""), []))
        candidate_rows.append(analyzed)
        transition_rows.extend(rows)
    step_rows = build_step_rows(transition_rows)
    return candidate_rows, transition_rows, step_rows


def summary_row(
    candidate_rows: list[dict[str, str]],
    transition_rows: list[dict[str, str]],
    step_rows: list[dict[str, str]],
) -> dict[str, str]:
    valid_step_values = {
        row.get("source_step", "")
        for row in transition_rows
        if row.get("valid_transition") == "1" and row.get("source_step", "")
    }
    valid_step_counts: Counter[str] = Counter(
        row.get("source_step", "")
        for row in transition_rows
        if row.get("valid_transition") == "1" and row.get("source_step", "")
    )
    dominant_valid_step, dominant_valid_rows = (
        valid_step_counts.most_common(1)[0] if valid_step_counts else ("", 0)
    )
    best_step = step_rows[0] if step_rows else {}
    return {
        "scope": "total",
        "selected_candidates": str(len(candidate_rows)),
        "row_sequence_rows": str(len(transition_rows)),
        "fixtures": str(len({fixture_key(row) for row in candidate_rows})),
        "valid_sequence_rows": str(sum(int_value(row, "valid_transition") for row in transition_rows)),
        "source_step_groups": str(len(step_rows)),
        "valid_source_step_groups": str(len(valid_step_values)),
        "dominant_source_step": best_step.get("source_step", ""),
        "dominant_source_step_rows": best_step.get("rows", "0"),
        "dominant_valid_source_step": dominant_valid_step,
        "dominant_valid_source_step_rows": str(dominant_valid_rows),
        "stride_step_rows": str(sum(int_value(row, "stride_step_rows") for row in candidate_rows)),
        "prev_nonzero_step_rows": str(sum(int_value(row, "prev_nonzero_step_rows") for row in candidate_rows)),
        "current_nonzero_step_rows": str(sum(int_value(row, "current_nonzero_step_rows") for row in candidate_rows)),
        "repeat_start_rows": str(sum(int_value(row, "repeat_start_rows") for row in candidate_rows)),
        "rewind_rows": str(sum(int_value(row, "rewind_rows") for row in candidate_rows)),
        "monotonic_candidates": str(sum(int_value(row, "monotonic") for row in candidate_rows)),
        "strict_monotonic_candidates": str(sum(int_value(row, "strict_monotonic") for row in candidate_rows)),
        "issue_rows": str(sum(1 for row in candidate_rows if row.get("issues"))),
    }


def render_candidate_row(row: dict[str, str]) -> str:
    return (
        "<tr>"
        f"<td>{html.escape(row.get('selection_id', ''))}</td>"
        f"<td>{html.escape(row.get('pcx_name', ''))}</td>"
        f"<td>{html.escape(row.get('frontier_id', ''))}</td>"
        f"<td>{html.escape(row.get('source_mode', ''))}</td>"
        f"<td>{html.escape(row.get('row_stride', ''))}</td>"
        f"<td>{html.escape(row.get('row_sequence_rows', ''))}</td>"
        f"<td>{html.escape(row.get('valid_sequence_rows', ''))}</td>"
        f"<td>{html.escape(row.get('unique_source_steps', ''))}</td>"
        f"<td>{html.escape(row.get('dominant_source_step', ''))}</td>"
        f"<td>{html.escape(row.get('dominant_source_step_rows', ''))}</td>"
        f"<td>{html.escape(row.get('rewind_rows', ''))}</td>"
        f"<td>{html.escape(row.get('strict_monotonic', ''))}</td>"
        f"<td>{html.escape(row.get('adjusted_nonzero_exact_slots', ''))}</td>"
        f"<td>{html.escape(row.get('issue_notes', ''))}</td>"
        f"<td>{html.escape(row.get('issues', ''))}</td>"
        "</tr>"
    )


def render_step_row(row: dict[str, str]) -> str:
    return (
        "<tr>"
        f"<td>{html.escape(row.get('source_step', ''))}</td>"
        f"<td>{html.escape(row.get('rows', ''))}</td>"
        f"<td>{html.escape(row.get('valid_rows', ''))}</td>"
        f"<td>{html.escape(row.get('candidates', ''))}</td>"
        f"<td>{html.escape(row.get('fixtures', ''))}</td>"
        f"<td>{html.escape(row.get('step_classes', ''))}</td>"
        f"<td>{html.escape(row.get('match_types', ''))}</td>"
        f"<td>{html.escape(row.get('min_delta_step', ''))}</td>"
        f"<td>{html.escape(row.get('max_delta_step', ''))}</td>"
        f"<td>{html.escape(row.get('adjusted_nonzero_exact_ratio', ''))}</td>"
        f"<td>{html.escape(row.get('sample_pcx', ''))}</td>"
        f"<td>{html.escape(row.get('sample_row_index', ''))}</td>"
        "</tr>"
    )


def render_transition_row(row: dict[str, str]) -> str:
    return (
        "<tr>"
        f"<td>{html.escape(row.get('selection_id', ''))}</td>"
        f"<td>{html.escape(row.get('prev_row_index', ''))}</td>"
        f"<td>{html.escape(row.get('row_index', ''))}</td>"
        f"<td>{html.escape(row.get('prev_best_source_start', ''))}</td>"
        f"<td>{html.escape(row.get('best_source_start', ''))}</td>"
        f"<td>{html.escape(row.get('source_step', ''))}</td>"
        f"<td>{html.escape(row.get('delta_step', ''))}</td>"
        f"<td>{html.escape(row.get('step_class', ''))}</td>"
        f"<td>{html.escape(row.get('step_matches', ''))}</td>"
        f"<td>{html.escape(row.get('valid_transition', ''))}</td>"
        f"<td>{html.escape(row.get('issues', ''))}</td>"
        "</tr>"
    )


def build_html(
    summary: dict[str, str],
    candidate_rows: list[dict[str, str]],
    transition_rows: list[dict[str, str]],
    step_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "candidates": candidate_rows,
        "transitions": transition_rows,
        "steps": step_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("candidates.csv", output_dir / "candidates.csv"),
            ("transitions.csv", output_dir / "transitions.csv"),
            ("by_step.csv", output_dir / "by_step.csv"),
        )
    )
    candidate_markup = "\n".join(
        render_candidate_row(row)
        for row in sorted(candidate_rows, key=lambda row: int_value(row, "adjusted_nonzero_exact_slots"), reverse=True)
    )
    step_markup = "\n".join(render_step_row(row) for row in step_rows[:180])
    top_transitions = sorted(
        transition_rows,
        key=lambda row: (abs(int_value(row, "source_step")), int_value(row, "adjusted_nonzero_exact_slots")),
        reverse=True,
    )[:180]
    transition_markup = "\n".join(render_transition_row(row) for row in top_transitions)
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root {{
  color-scheme: dark;
  --bg: #101316;
  --panel: #171d22;
  --line: #2f3942;
  --text: #edf3f6;
  --muted: #9caab3;
  --accent: #74d3ae;
  --ok: #78d98f;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  min-height: 100vh;
  background: var(--bg);
  color: var(--text);
  font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}}
.wrap {{ width: min(1600px, calc(100vw - 28px)); margin: 0 auto; }}
header {{ border-bottom: 1px solid var(--line); background: #12171b; padding: 18px 0 14px; }}
h1 {{ margin: 0; font-size: 21px; font-weight: 700; letter-spacing: 0; }}
h2 {{ margin: 0 0 10px; font-size: 16px; }}
.sub {{ color: var(--muted); margin-top: 4px; }}
main {{ padding: 16px 0 28px; display: grid; gap: 16px; }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; }}
.stat, .panel {{ border: 1px solid var(--line); border-radius: 8px; background: var(--panel); padding: 10px; }}
.label, .muted {{ color: var(--muted); }}
.value {{ font-size: 24px; font-weight: 750; line-height: 1.05; margin-top: 4px; }}
.ok {{ color: var(--ok); }}
.panel {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; min-width: 1320px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Transitions source entre lignes apres alignement delta.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Candidates</div><div class="value">{html.escape(summary['selected_candidates'])}</div></div>
    <div class="stat"><div class="label">Transitions</div><div class="value">{html.escape(summary['row_sequence_rows'])}</div></div>
    <div class="stat"><div class="label">Step groups</div><div class="value">{html.escape(summary['source_step_groups'])}</div></div>
    <div class="stat"><div class="label">Dominant step</div><div class="value ok">{html.escape(summary['dominant_source_step'])}</div></div>
    <div class="stat"><div class="label">Rewinds</div><div class="value">{html.escape(summary['rewind_rows'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div></section>
  <section class="panel">
    <h2>Candidates</h2>
    <table>
      <thead><tr><th>ID</th><th>PCX</th><th>Frontier</th><th>Mode</th><th>Stride</th><th>Transitions</th><th>Valid</th><th>Steps</th><th>Top step</th><th>Top rows</th><th>Rewinds</th><th>Strict mono</th><th>Exact</th><th>Notes</th><th>Issues</th></tr></thead>
      <tbody>{candidate_markup}</tbody>
    </table>
  </section>
  <section class="panel">
    <h2>Source steps</h2>
    <table>
      <thead><tr><th>Step</th><th>Rows</th><th>Valid</th><th>Candidates</th><th>Fixtures</th><th>Classes</th><th>Matches</th><th>Min delta step</th><th>Max delta step</th><th>Exact ratio</th><th>Sample PCX</th><th>Sample row</th></tr></thead>
      <tbody>{step_markup}</tbody>
    </table>
  </section>
  <section class="panel">
    <h2>Largest transitions</h2>
    <table>
      <thead><tr><th>ID</th><th>Prev row</th><th>Row</th><th>Prev start</th><th>Start</th><th>Step</th><th>Delta step</th><th>Class</th><th>Matches</th><th>Valid</th><th>Issues</th></tr></thead>
      <tbody>{transition_markup}</tbody>
    </table>
  </section>
</main>
<script>
const TEX_GAP_ROW_SEQUENCE_PROBE = {data_json};
</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    candidates: Path,
    row_controls: Path,
    *,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    candidate_rows, transition_rows, step_rows = build_rows(candidates, row_controls)
    summary = summary_row(candidate_rows, transition_rows, step_rows)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "candidates.csv", CANDIDATE_FIELDNAMES, candidate_rows)
    write_csv(output_dir / "transitions.csv", TRANSITION_FIELDNAMES, transition_rows)
    write_csv(output_dir / "by_step.csv", STEP_FIELDNAMES, step_rows)
    (output_dir / "index.html").write_text(
        build_html(summary, candidate_rows, transition_rows, step_rows, output_dir, title)
    )
    return summary, candidate_rows, transition_rows, step_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe row-to-row source start sequences for .tex candidates.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--row-controls", type=Path, default=DEFAULT_ROW_CONTROLS)
    parser.add_argument("--title", default="Lands of Lore II .tex Gap Row Sequence Probe")
    args = parser.parse_args()

    summary, _candidate_rows, _transition_rows, _step_rows = write_report(
        args.output,
        args.candidates,
        args.row_controls,
        title=args.title,
    )
    print(f"Selected candidates: {summary['selected_candidates']}")
    print(f"Row sequence rows: {summary['row_sequence_rows']}")
    print(f"Source step groups: {summary['source_step_groups']}")
    print(f"Dominant source step: {summary['dominant_source_step']} ({summary['dominant_source_step_rows']})")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
