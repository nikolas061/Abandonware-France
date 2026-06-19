#!/usr/bin/env python3
"""Validate the low-tail anchor guard as a palette-walk replay split."""

from __future__ import annotations

import argparse
import csv
import html
import json
from pathlib import Path
from typing import Callable

from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_frontier80_clean_nonzero_palette_walk_low_tail_anchor_guard_replay_probe")
DEFAULT_DELTAS = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_generated_sequence_probe/deltas.csv"
)
DEFAULT_ANCHORS = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_split_probe/anchors.csv"
)
DEFAULT_GUARDS = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_split_probe/guard_candidates.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "target_runs",
    "total_transition_rows",
    "small_delta_rows",
    "base_small_delta_replay_rows",
    "large_delta_rows",
    "anchor_rows",
    "guard_name",
    "guard_class",
    "guard_keys",
    "guard_transition_hits",
    "guard_anchor_hits",
    "guard_anchor_exact_rows",
    "guard_false_positive_rows",
    "guard_missed_anchor_rows",
    "guard_delta_conflict_keys",
    "stream_split_covered_rows",
    "unresolved_large_delta_rows",
    "replay_exact_rows",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

REPLAY_FIELDNAMES = [
    "target_id",
    "transition_index",
    "from_run_offset",
    "to_run_offset",
    "from_abs",
    "to_abs",
    "from_row",
    "to_row",
    "from_col",
    "to_col",
    "from_mode",
    "to_mode",
    "mode_pair",
    "from_value_hex",
    "to_value_hex",
    "expected_delta",
    "abs_delta",
    "small_delta_le3",
    "large_delta",
    "anchor_row",
    "guard_name",
    "guard_key",
    "matched_guard",
    "selected_class",
    "replay_delta",
    "replay_exact",
    "issue",
]

OPERATION_FIELDNAMES = [
    "guard_name",
    "guard_key",
    "exact_delta",
    "anchor_hits",
    "transition_hits",
    "false_positive_rows",
    "exact_anchor_hits",
    "conflict",
    "source_transitions",
    "verdict",
]

GuardFunc = Callable[[dict[str, str]], tuple[object, ...]]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def mode_pair(row: dict[str, str]) -> str:
    return f"{row.get('from_mode', '')}->{row.get('to_mode', '')}"


def transition_identity(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("target_id", ""), row.get("from_run_offset", ""), row.get("to_run_offset", "")


def guard_key_text(key: tuple[object, ...]) -> str:
    return "|".join(str(part) for part in key)


def split_selected_keys(text: str) -> set[str]:
    return {part for part in text.split(";") if part}


def guard_specs() -> list[tuple[str, str, bool, GuardFunc]]:
    return [
        (
            "context_mode_pair_prev_value_col_mod32",
            "context",
            False,
            lambda row: (mode_pair(row), row.get("from_value_hex", ""), int_value(row, "to_col") % 32),
        ),
        ("context_mode_pair_col_mod32", "context", False, lambda row: (mode_pair(row), int_value(row, "to_col") % 32)),
        ("context_prev_value_to_col", "context", False, lambda row: (row.get("from_value_hex", ""), row.get("to_col", ""))),
        (
            "context_prev_value_row_col_mod32",
            "context",
            False,
            lambda row: (row.get("from_value_hex", ""), row.get("to_row", ""), int_value(row, "to_col") % 32),
        ),
        ("context_row_to_col", "context", False, lambda row: (row.get("to_row", ""), row.get("to_col", ""))),
        ("context_col_exact", "context", False, lambda row: (row.get("to_col", ""),)),
    ]


def select_context_guard(guard_rows: list[dict[str, str]]) -> dict[str, str]:
    context_rows = [row for row in guard_rows if row.get("guard_class") == "context" and row.get("uses_target_id") != "1"]
    false_free = [row for row in context_rows if row.get("false_free") == "1"]
    choices = false_free or context_rows
    if not choices:
        return {}
    return min(
        choices,
        key=lambda row: (
            int_value(row, "missed_anchors"),
            int_value(row, "false_hits"),
            int_value(row, "key_count"),
            row.get("guard_name", ""),
        ),
    )


def guard_delta_sets(
    anchor_rows: list[dict[str, str]],
    guard: GuardFunc,
) -> dict[str, set[int]]:
    deltas: dict[str, set[int]] = {}
    for row in anchor_rows:
        key = guard_key_text(guard(row))
        deltas.setdefault(key, set()).add(int_value(row, "delta"))
    return deltas


def build_replay(
    delta_rows: list[dict[str, str]],
    anchor_rows: list[dict[str, str]],
    guard_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[str]]:
    issues: list[str] = []
    selected_guard = select_context_guard(guard_rows)
    guard_funcs = {name: func for name, _guard_class, _uses_target_id, func in guard_specs()}
    guard_name = selected_guard.get("guard_name", "")
    guard_func = guard_funcs.get(guard_name)
    if not selected_guard:
        issues.append("missing_context_guard_candidate")
    elif guard_func is None:
        issues.append(f"unknown_context_guard:{guard_name}")
    if guard_func is None:
        guard_name = ""
        guard_func = guard_specs()[0][3]

    selected_keys = split_selected_keys(selected_guard.get("selected_keys", ""))
    anchor_keys = {guard_key_text(guard_func(row)) for row in anchor_rows}
    if not selected_keys:
        selected_keys = set(anchor_keys)
    missing_selected_anchor_keys = anchor_keys - selected_keys
    extra_selected_keys = selected_keys - anchor_keys
    if missing_selected_anchor_keys:
        issues.append("selected_guard_missing_anchor_keys:" + ";".join(sorted(missing_selected_anchor_keys)))
    if extra_selected_keys:
        issues.append("selected_guard_extra_keys:" + ";".join(sorted(extra_selected_keys)))

    anchor_ids = {transition_identity(row) for row in anchor_rows}
    guard_deltas = guard_delta_sets(anchor_rows, guard_func)
    conflict_keys = {key for key, values in guard_deltas.items() if len(values) > 1}

    replay_rows: list[dict[str, str]] = []
    for row in delta_rows:
        row_issues: list[str] = []
        identity = transition_identity(row)
        guard_key = guard_key_text(guard_func(row))
        matched_guard = guard_key in selected_keys
        is_anchor = identity in anchor_ids
        expected_delta = int_value(row, "delta")
        abs_delta = abs(expected_delta)
        small_delta = abs_delta <= 3
        large_delta = not small_delta
        replay_delta: int | None = None

        if matched_guard:
            selected_class = "low_tail_anchor_guard"
            values = guard_deltas.get(guard_key, set())
            if len(values) == 1:
                replay_delta = next(iter(values))
            elif len(values) > 1:
                row_issues.append("guard_delta_conflict")
            else:
                row_issues.append("missing_guard_delta")
            if not is_anchor:
                row_issues.append("guard_false_positive")
        elif small_delta:
            selected_class = "base_small_delta"
            replay_delta = expected_delta
        else:
            selected_class = "unresolved_large_delta"
            row_issues.append("unresolved_large_delta")

        if is_anchor and not matched_guard:
            row_issues.append("missed_anchor")
        replay_exact = replay_delta is not None and replay_delta == expected_delta
        if replay_delta is not None and replay_delta != expected_delta:
            row_issues.append("replay_delta_mismatch")

        replay_rows.append(
            {
                "target_id": row.get("target_id", ""),
                "transition_index": row.get("transition_index", ""),
                "from_run_offset": row.get("from_run_offset", ""),
                "to_run_offset": row.get("to_run_offset", ""),
                "from_abs": row.get("from_abs", ""),
                "to_abs": row.get("to_abs", ""),
                "from_row": row.get("from_row", ""),
                "to_row": row.get("to_row", ""),
                "from_col": row.get("from_col", ""),
                "to_col": row.get("to_col", ""),
                "from_mode": row.get("from_mode", ""),
                "to_mode": row.get("to_mode", ""),
                "mode_pair": mode_pair(row),
                "from_value_hex": row.get("from_value_hex", ""),
                "to_value_hex": row.get("to_value_hex", ""),
                "expected_delta": str(expected_delta),
                "abs_delta": str(abs_delta),
                "small_delta_le3": "1" if small_delta else "0",
                "large_delta": "1" if large_delta else "0",
                "anchor_row": "1" if is_anchor else "0",
                "guard_name": guard_name,
                "guard_key": guard_key,
                "matched_guard": "1" if matched_guard else "0",
                "selected_class": selected_class,
                "replay_delta": "" if replay_delta is None else str(replay_delta),
                "replay_exact": "1" if replay_exact else "0",
                "issue": ";".join(row_issues),
            }
        )

    operation_rows = build_operations(guard_name, selected_keys, guard_deltas, replay_rows)
    summary = build_summary(delta_rows, anchor_rows, selected_guard, replay_rows, operation_rows, len(issues))
    return summary, replay_rows, operation_rows, issues


def build_operations(
    guard_name: str,
    selected_keys: set[str],
    guard_deltas: dict[str, set[int]],
    replay_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for key in sorted(selected_keys):
        matches = [row for row in replay_rows if row.get("guard_key") == key and row.get("matched_guard") == "1"]
        anchor_hits = [row for row in matches if row.get("anchor_row") == "1"]
        false_hits = [row for row in matches if row.get("anchor_row") != "1"]
        exact_hits = [row for row in anchor_hits if row.get("replay_exact") == "1"]
        delta_values = sorted(guard_deltas.get(key, set()))
        conflict = len(delta_values) > 1
        if conflict:
            verdict = "guard_delta_conflict"
        elif false_hits:
            verdict = "guard_false_positive"
        elif not anchor_hits:
            verdict = "guard_unused"
        elif len(exact_hits) == len(anchor_hits):
            verdict = "exact_guard_delta"
        else:
            verdict = "guard_delta_mismatch"
        rows.append(
            {
                "guard_name": guard_name,
                "guard_key": key,
                "exact_delta": ";".join(str(value) for value in delta_values),
                "anchor_hits": str(len(anchor_hits)),
                "transition_hits": str(len(matches)),
                "false_positive_rows": str(len(false_hits)),
                "exact_anchor_hits": str(len(exact_hits)),
                "conflict": "1" if conflict else "0",
                "source_transitions": ";".join(
                    f"{row.get('target_id', '')}:{row.get('transition_index', '')}" for row in anchor_hits
                ),
                "verdict": verdict,
            }
        )
    return rows


def build_summary(
    delta_rows: list[dict[str, str]],
    anchor_rows: list[dict[str, str]],
    selected_guard: dict[str, str],
    replay_rows: list[dict[str, str]],
    operation_rows: list[dict[str, str]],
    upfront_issue_count: int,
) -> dict[str, str]:
    small_delta_rows = sum(1 for row in replay_rows if row.get("small_delta_le3") == "1")
    base_small_delta_rows = sum(1 for row in replay_rows if row.get("selected_class") == "base_small_delta")
    large_delta_rows = len(replay_rows) - small_delta_rows
    guard_transition_hits = sum(1 for row in replay_rows if row.get("matched_guard") == "1")
    guard_anchor_hits = sum(1 for row in replay_rows if row.get("matched_guard") == "1" and row.get("anchor_row") == "1")
    guard_anchor_exact = sum(
        1
        for row in replay_rows
        if row.get("matched_guard") == "1" and row.get("anchor_row") == "1" and row.get("replay_exact") == "1"
    )
    guard_false_positive = sum(
        1 for row in replay_rows if row.get("matched_guard") == "1" and row.get("anchor_row") != "1"
    )
    guard_missed_anchor = sum(1 for row in replay_rows if row.get("anchor_row") == "1" and row.get("matched_guard") != "1")
    guard_conflicts = sum(1 for row in operation_rows if row.get("conflict") == "1")
    unresolved_large = sum(1 for row in replay_rows if row.get("selected_class") == "unresolved_large_delta")
    covered = sum(1 for row in replay_rows if row.get("selected_class") != "unresolved_large_delta")
    exact = sum(1 for row in replay_rows if row.get("replay_exact") == "1")
    row_issue_count = sum(1 for row in replay_rows if row.get("issue", ""))
    issue_count = upfront_issue_count + row_issue_count

    if (
        issue_count == 0
        and guard_anchor_hits == len(anchor_rows)
        and guard_anchor_exact == len(anchor_rows)
        and guard_false_positive == 0
        and guard_missed_anchor == 0
        and guard_conflicts == 0
        and unresolved_large == 0
        and exact == len(replay_rows)
    ):
        verdict = "frontier80_clean_nonzero_palette_walk_low_tail_anchor_guard_replay_ready"
        next_probe = "integrate low-tail anchor guard with small-delta palette-walk value producer"
    elif guard_false_positive or guard_missed_anchor:
        verdict = "frontier80_clean_nonzero_palette_walk_low_tail_anchor_guard_replay_guard_issues"
        next_probe = "split low-tail anchor guard false positives before replay promotion"
    elif unresolved_large:
        verdict = "frontier80_clean_nonzero_palette_walk_low_tail_anchor_guard_replay_unresolved_large_delta"
        next_probe = "expand low-tail anchor guard replay coverage"
    else:
        verdict = "frontier80_clean_nonzero_palette_walk_low_tail_anchor_guard_replay_weak"
        next_probe = "review low-tail anchor guard replay issues"

    return {
        "scope": "total",
        "target_runs": str(len({row.get("target_id", "") for row in delta_rows})),
        "total_transition_rows": str(len(replay_rows)),
        "small_delta_rows": str(small_delta_rows),
        "base_small_delta_replay_rows": str(base_small_delta_rows),
        "large_delta_rows": str(large_delta_rows),
        "anchor_rows": str(len(anchor_rows)),
        "guard_name": selected_guard.get("guard_name", ""),
        "guard_class": selected_guard.get("guard_class", ""),
        "guard_keys": selected_guard.get("key_count", str(len(operation_rows))),
        "guard_transition_hits": str(guard_transition_hits),
        "guard_anchor_hits": str(guard_anchor_hits),
        "guard_anchor_exact_rows": str(guard_anchor_exact),
        "guard_false_positive_rows": str(guard_false_positive),
        "guard_missed_anchor_rows": str(guard_missed_anchor),
        "guard_delta_conflict_keys": str(guard_conflicts),
        "stream_split_covered_rows": str(covered),
        "unresolved_large_delta_rows": str(unresolved_large),
        "replay_exact_rows": str(exact),
        "issue_rows": str(issue_count),
        "review_verdict": verdict,
        "next_probe": next_probe,
    }


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 160) -> str:
    if not rows:
        return "<p>No rows.</p>"
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    replay_rows: list[dict[str, str]],
    operation_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "operations": operation_rows, "replay_rows": replay_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("guard_operations.csv", output_dir / "guard_operations.csv"),
            ("replay_rows.csv", output_dir / "replay_rows.csv"),
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
  --warn: #f0c36a;
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; min-height: 100vh; background: var(--bg); color: var(--text); font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
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
.warn {{ color: var(--warn); }}
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
    <div class="sub">Validates the false-free low-tail guard against every palette-walk transition.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Replay exact</div><div class="value">{html.escape(summary['replay_exact_rows'])}/{html.escape(summary['total_transition_rows'])}</div></div>
    <div class="stat"><div class="label">Anchor guard hits</div><div class="value">{html.escape(summary['guard_anchor_hits'])}/{html.escape(summary['anchor_rows'])}</div></div>
    <div class="stat"><div class="label">False positives</div><div class="value warn">{html.escape(summary['guard_false_positive_rows'])}</div></div>
    <div class="stat"><div class="label">Unresolved large deltas</div><div class="value warn">{html.escape(summary['unresolved_large_delta_rows'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div><div class="sub">{html.escape(summary['review_verdict'])}: {html.escape(summary['next_probe'])}</div></section>
  <section class="panel"><h2>Guard Operations</h2>{render_table(operation_rows, OPERATION_FIELDNAMES)}</section>
  <section class="panel"><h2>Replay Rows</h2>{render_table(replay_rows, REPLAY_FIELDNAMES)}</section>
</main>
<script type="application/json" id="palette-walk-low-tail-anchor-guard-replay-data">{data_json}</script>
</body>
</html>
"""


def write_report(output_dir: Path, deltas_path: Path, anchors_path: Path, guards_path: Path, *, title: str) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    try:
        delta_rows = read_csv(deltas_path)
    except OSError as exc:
        issues.append(f"read_deltas_failed:{exc}")
        delta_rows = []
    try:
        anchor_rows = read_csv(anchors_path)
    except OSError as exc:
        issues.append(f"read_anchors_failed:{exc}")
        anchor_rows = []
    try:
        guard_rows = read_csv(guards_path)
    except OSError as exc:
        issues.append(f"read_guards_failed:{exc}")
        guard_rows = []

    summary, replay_rows, operation_rows, replay_issues = build_replay(delta_rows, anchor_rows, guard_rows)
    all_issues = issues + replay_issues
    if all_issues:
        summary["issue_rows"] = str(int_value(summary, "issue_rows") + len(issues))
        if summary["review_verdict"] == "frontier80_clean_nonzero_palette_walk_low_tail_anchor_guard_replay_ready":
            summary["review_verdict"] = "frontier80_clean_nonzero_palette_walk_low_tail_anchor_guard_replay_weak"
            summary["next_probe"] = "review low-tail anchor guard replay input issues"

    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "guard_operations.csv", OPERATION_FIELDNAMES, operation_rows)
    write_csv(output_dir / "replay_rows.csv", REPLAY_FIELDNAMES, replay_rows)
    (output_dir / "issues.txt").write_text("\n".join(all_issues) + ("\n" if all_issues else ""))
    (output_dir / "index.html").write_text(build_html(summary, replay_rows, operation_rows, output_dir, title))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate low-tail anchor guard palette-walk replay.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--deltas", type=Path, default=DEFAULT_DELTAS)
    parser.add_argument("--anchors", type=Path, default=DEFAULT_ANCHORS)
    parser.add_argument("--guards", type=Path, default=DEFAULT_GUARDS)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Clean Nonzero Palette Walk Low-Tail Anchor Guard Replay Probe",
    )
    args = parser.parse_args()

    summary = write_report(args.output, args.deltas, args.anchors, args.guards, title=args.title)
    print(f"Replay exact: {summary['replay_exact_rows']}/{summary['total_transition_rows']}")
    print(f"Anchor guard hits: {summary['guard_anchor_hits']}/{summary['anchor_rows']}")
    print(f"False positives: {summary['guard_false_positive_rows']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
