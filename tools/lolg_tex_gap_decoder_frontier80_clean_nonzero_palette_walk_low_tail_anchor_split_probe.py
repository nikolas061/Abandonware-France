#!/usr/bin/env python3
"""Split low-tail large-delta anchors for Frontier80 palette-walk runs."""

from __future__ import annotations

import argparse
import csv
import html
import json
from pathlib import Path
from typing import Callable

from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_frontier80_clean_nonzero_palette_walk_low_tail_anchor_split_probe")
DEFAULT_DELTAS = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_generated_sequence_probe/deltas.csv"
)
DEFAULT_LARGE_DELTAS = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_delta_state_probe/large_deltas.csv"
)
DEFAULT_TERMINALS = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_generated_sequence_probe/terminal_contexts.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "target_runs",
    "delta_pairs",
    "large_delta_pairs",
    "low_tail_anchor_rows",
    "high_high_large_delta_pairs",
    "terminal_adjacent_anchors",
    "guard_candidates",
    "false_free_guard_candidates",
    "best_guard",
    "best_guard_class",
    "best_guard_keys",
    "best_guard_anchor_hits",
    "best_guard_false_hits",
    "best_guard_total_hits",
    "best_context_guard",
    "best_context_guard_keys",
    "best_context_guard_anchor_hits",
    "best_context_guard_false_hits",
    "best_target_guard",
    "best_target_guard_keys",
    "best_target_guard_anchor_hits",
    "best_target_guard_false_hits",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

ANCHOR_FIELDNAMES = [
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
    "from_value_hex",
    "to_value_hex",
    "delta",
    "abs_delta",
    "mode_pair",
    "tail_state",
    "near_terminal",
    "terminal_distance",
    "context_guard_key",
    "target_guard_key",
]

GUARD_FIELDNAMES = [
    "guard_name",
    "guard_class",
    "uses_target_id",
    "key_count",
    "selected_keys",
    "anchor_hits",
    "false_hits",
    "total_hits",
    "missed_anchors",
    "exact_ratio",
    "false_free",
    "verdict",
    "next_probe",
]

TRANSITION_FIELDNAMES = [
    "target_id",
    "transition_index",
    "from_run_offset",
    "to_run_offset",
    "from_row",
    "to_row",
    "from_col",
    "to_col",
    "from_mode",
    "to_mode",
    "from_value_hex",
    "to_value_hex",
    "delta",
    "abs_delta",
    "large_delta",
    "matched_best_context_guard",
    "matched_best_target_guard",
]

GuardFunc = Callable[[dict[str, str]], tuple[object, ...]]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def guard_key_text(key: tuple[object, ...]) -> str:
    return "|".join(str(part) for part in key)


def mode_pair(row: dict[str, str]) -> str:
    return f"{row.get('from_mode', '')}->{row.get('to_mode', '')}"


def large_identity(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("target_id", ""), row.get("from_run_offset", ""), row.get("to_run_offset", "")


def terminal_ranges(rows: list[dict[str, str]]) -> dict[str, list[tuple[int, int]]]:
    output: dict[str, list[tuple[int, int]]] = {}
    for row in rows:
        output.setdefault(row.get("target_id", ""), []).append(
            (int_value(row, "run_offset_start"), int_value(row, "run_offset_end"))
        )
    return output


def terminal_distance(row: dict[str, str], terminals: dict[str, list[tuple[int, int]]]) -> int:
    ranges = terminals.get(row.get("target_id", ""), [])
    if not ranges:
        return -1
    from_offset = int_value(row, "from_run_offset")
    to_offset = int_value(row, "to_run_offset")
    distances = []
    for start, end in ranges:
        distances.extend([abs(from_offset - start), abs(from_offset - end), abs(to_offset - start), abs(to_offset - end)])
    return min(distances) if distances else -1


def guard_specs() -> list[tuple[str, str, bool, GuardFunc]]:
    return [
        ("context_mode_pair_prev_value_col_mod32", "context", False, lambda row: (mode_pair(row), row.get("from_value_hex", ""), int_value(row, "to_col") % 32)),
        ("context_mode_pair_col_mod32", "context", False, lambda row: (mode_pair(row), int_value(row, "to_col") % 32)),
        ("context_prev_value_to_col", "context", False, lambda row: (row.get("from_value_hex", ""), row.get("to_col", ""))),
        ("context_prev_value_row_col_mod32", "context", False, lambda row: (row.get("from_value_hex", ""), row.get("to_row", ""), int_value(row, "to_col") % 32)),
        ("context_row_to_col", "context", False, lambda row: (row.get("to_row", ""), row.get("to_col", ""))),
        ("context_col_exact", "context", False, lambda row: (row.get("to_col", ""),)),
        ("target_rel_offset", "target", True, lambda row: (row.get("target_id", ""), row.get("from_run_offset", ""), row.get("to_run_offset", ""))),
        ("target_to_col", "target", True, lambda row: (row.get("target_id", ""), row.get("to_col", ""))),
        ("target_col_mod32", "target", True, lambda row: (row.get("target_id", ""), int_value(row, "to_col") % 32)),
    ]


def score_guard(
    name: str,
    guard_class: str,
    uses_target_id: bool,
    guard: GuardFunc,
    delta_rows: list[dict[str, str]],
    large_rows: list[dict[str, str]],
) -> dict[str, str]:
    large_keys = {guard(row) for row in large_rows}
    large_ids = {large_identity(row) for row in large_rows}
    matched = [row for row in delta_rows if guard(row) in large_keys]
    anchor_hits = sum(1 for row in matched if large_identity(row) in large_ids)
    false_hits = len(matched) - anchor_hits
    missed_anchors = len(large_rows) - anchor_hits
    if anchor_hits == len(large_rows) and false_hits == 0:
        verdict = "low_tail_anchor_guard_false_free"
        next_probe = "validate false-free low-tail anchor guard with exact palette-walk replay"
    elif anchor_hits == len(large_rows):
        verdict = "low_tail_anchor_guard_covers_with_false_hits"
        next_probe = "split low-tail anchor guard false positives before replay validation"
    else:
        verdict = "low_tail_anchor_guard_partial"
        next_probe = "expand low-tail anchor guard context"
    return {
        "guard_name": name,
        "guard_class": guard_class,
        "uses_target_id": "1" if uses_target_id else "0",
        "key_count": str(len(large_keys)),
        "selected_keys": ";".join(guard_key_text(key) for key in sorted(large_keys, key=guard_key_text)),
        "anchor_hits": str(anchor_hits),
        "false_hits": str(false_hits),
        "total_hits": str(len(matched)),
        "missed_anchors": str(missed_anchors),
        "exact_ratio": f"{anchor_hits / len(matched):.6f}" if matched else "0.000000",
        "false_free": "1" if anchor_hits == len(large_rows) and false_hits == 0 else "0",
        "verdict": verdict,
        "next_probe": next_probe,
    }


def best_guard(rows: list[dict[str, str]], *, include_target: bool) -> dict[str, str]:
    choices = [
        row
        for row in rows
        if include_target or row.get("uses_target_id") == "0"
    ]
    if not choices:
        return {}
    return min(
        choices,
        key=lambda row: (
            int_value(row, "missed_anchors"),
            int_value(row, "false_hits"),
            int_value(row, "key_count"),
            int_value(row, "uses_target_id"),
            row.get("guard_name", ""),
        ),
    )


def anchor_rows(
    large_rows: list[dict[str, str]],
    terminals: dict[str, list[tuple[int, int]]],
    context_guard: GuardFunc,
    target_guard: GuardFunc,
) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for row in large_rows:
        output.append(
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
                "from_value_hex": row.get("from_value_hex", ""),
                "to_value_hex": row.get("to_value_hex", ""),
                "delta": row.get("delta", ""),
                "abs_delta": row.get("abs_delta", ""),
                "mode_pair": row.get("mode_pair", mode_pair(row)),
                "tail_state": row.get("tail_state", ""),
                "near_terminal": row.get("near_terminal", ""),
                "terminal_distance": str(terminal_distance(row, terminals)),
                "context_guard_key": guard_key_text(context_guard(row)),
                "target_guard_key": guard_key_text(target_guard(row)),
            }
        )
    return output


def transition_rows(
    delta_rows: list[dict[str, str]],
    large_rows: list[dict[str, str]],
    context_guard: GuardFunc,
    target_guard: GuardFunc,
) -> list[dict[str, str]]:
    large_ids = {large_identity(row) for row in large_rows}
    context_keys = {context_guard(row) for row in large_rows}
    target_keys = {target_guard(row) for row in large_rows}
    output: list[dict[str, str]] = []
    for row in delta_rows:
        output.append(
            {
                "target_id": row.get("target_id", ""),
                "transition_index": row.get("transition_index", ""),
                "from_run_offset": row.get("from_run_offset", ""),
                "to_run_offset": row.get("to_run_offset", ""),
                "from_row": row.get("from_row", ""),
                "to_row": row.get("to_row", ""),
                "from_col": row.get("from_col", ""),
                "to_col": row.get("to_col", ""),
                "from_mode": row.get("from_mode", ""),
                "to_mode": row.get("to_mode", ""),
                "from_value_hex": row.get("from_value_hex", ""),
                "to_value_hex": row.get("to_value_hex", ""),
                "delta": row.get("delta", ""),
                "abs_delta": row.get("abs_delta", ""),
                "large_delta": "1" if large_identity(row) in large_ids else "0",
                "matched_best_context_guard": "1" if context_guard(row) in context_keys else "0",
                "matched_best_target_guard": "1" if target_guard(row) in target_keys else "0",
            }
        )
    return output


def build_summary(
    delta_rows: list[dict[str, str]],
    large_rows: list[dict[str, str]],
    guard_rows: list[dict[str, str]],
    anchor_rows_list: list[dict[str, str]],
    *,
    issue_count: int,
) -> dict[str, str]:
    best_context = best_guard(guard_rows, include_target=False)
    best_any = best_guard(guard_rows, include_target=True)
    target_guards = [row for row in guard_rows if row.get("uses_target_id") == "1"]
    best_target = best_guard(target_guards, include_target=True)
    false_free = [row for row in guard_rows if row.get("false_free") == "1"]
    high_high_large = sum(1 for row in large_rows if row.get("tail_state") == "high_prefix")
    terminal_adjacent = sum(1 for row in anchor_rows_list if int_value(row, "near_terminal"))
    if best_context and best_context.get("false_free") == "1":
        verdict = "frontier80_clean_nonzero_palette_walk_low_tail_anchor_context_guard_ready"
        next_probe = "validate false-free low-tail anchor guard with exact palette-walk replay"
    elif best_any and best_any.get("false_free") == "1":
        verdict = "frontier80_clean_nonzero_palette_walk_low_tail_anchor_target_guard_only"
        next_probe = "replace target-specific low-tail anchor guard with context guard before replay"
    elif large_rows:
        verdict = "frontier80_clean_nonzero_palette_walk_low_tail_anchor_split_partial"
        next_probe = "split low-tail anchor guard false positives before replay validation"
    else:
        verdict = "frontier80_clean_nonzero_palette_walk_low_tail_anchor_no_large_deltas"
        next_probe = "promote exact small-delta palette-walk state"
    return {
        "scope": "total",
        "target_runs": str(len({row.get("target_id", "") for row in delta_rows})),
        "delta_pairs": str(len(delta_rows)),
        "large_delta_pairs": str(len(large_rows)),
        "low_tail_anchor_rows": str(len(anchor_rows_list)),
        "high_high_large_delta_pairs": str(high_high_large),
        "terminal_adjacent_anchors": str(terminal_adjacent),
        "guard_candidates": str(len(guard_rows)),
        "false_free_guard_candidates": str(len(false_free)),
        "best_guard": best_any.get("guard_name", ""),
        "best_guard_class": best_any.get("guard_class", ""),
        "best_guard_keys": best_any.get("key_count", "0"),
        "best_guard_anchor_hits": best_any.get("anchor_hits", "0"),
        "best_guard_false_hits": best_any.get("false_hits", "0"),
        "best_guard_total_hits": best_any.get("total_hits", "0"),
        "best_context_guard": best_context.get("guard_name", ""),
        "best_context_guard_keys": best_context.get("key_count", "0"),
        "best_context_guard_anchor_hits": best_context.get("anchor_hits", "0"),
        "best_context_guard_false_hits": best_context.get("false_hits", "0"),
        "best_target_guard": best_target.get("guard_name", ""),
        "best_target_guard_keys": best_target.get("key_count", "0"),
        "best_target_guard_anchor_hits": best_target.get("anchor_hits", "0"),
        "best_target_guard_false_hits": best_target.get("false_hits", "0"),
        "issue_rows": str(issue_count),
        "review_verdict": verdict,
        "next_probe": next_probe,
    }


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 140) -> str:
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
    anchor_rows_list: list[dict[str, str]],
    guard_rows: list[dict[str, str]],
    transition_rows_list: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "anchors": anchor_rows_list,
        "guards": guard_rows,
        "transitions": transition_rows_list,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("anchors.csv", output_dir / "anchors.csv"),
            ("guard_candidates.csv", output_dir / "guard_candidates.csv"),
            ("transitions.csv", output_dir / "transitions.csv"),
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
table {{ width: 100%; border-collapse: collapse; min-width: 1260px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Tests low-tail anchor guards for the palette-walk large-delta split.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Anchors</div><div class="value">{html.escape(summary['low_tail_anchor_rows'])}</div></div>
    <div class="stat"><div class="label">Best context guard</div><div class="value">{html.escape(summary['best_context_guard'])}</div></div>
    <div class="stat"><div class="label">Context false hits</div><div class="value warn">{html.escape(summary['best_context_guard_false_hits'])}</div></div>
    <div class="stat"><div class="label">False-free guards</div><div class="value">{html.escape(summary['false_free_guard_candidates'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div><div class="sub">{html.escape(summary['review_verdict'])}: {html.escape(summary['next_probe'])}</div></section>
  <section class="panel"><h2>Anchors</h2>{render_table(anchor_rows_list, ANCHOR_FIELDNAMES)}</section>
  <section class="panel"><h2>Guard Candidates</h2>{render_table(guard_rows, GUARD_FIELDNAMES)}</section>
  <section class="panel"><h2>Transitions</h2>{render_table(transition_rows_list, TRANSITION_FIELDNAMES)}</section>
</main>
<script type="application/json" id="palette-walk-low-tail-anchor-split-data">{data_json}</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    deltas_path: Path,
    large_deltas_path: Path,
    terminals_path: Path,
    *,
    title: str,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    try:
        delta_rows = read_csv(deltas_path)
    except OSError as exc:
        issues.append(f"read_deltas_failed:{exc}")
        delta_rows = []
    try:
        large_rows = read_csv(large_deltas_path)
    except OSError as exc:
        issues.append(f"read_large_deltas_failed:{exc}")
        large_rows = []
    try:
        terminal_rows = read_csv(terminals_path)
    except OSError as exc:
        issues.append(f"read_terminals_failed:{exc}")
        terminal_rows = []
    terminals = terminal_ranges(terminal_rows)
    guard_rows = [
        score_guard(name, guard_class, uses_target_id, guard, delta_rows, large_rows)
        for name, guard_class, uses_target_id, guard in guard_specs()
    ]
    guard_rows.sort(
        key=lambda row: (
            int_value(row, "missed_anchors"),
            int_value(row, "false_hits"),
            int_value(row, "uses_target_id"),
            int_value(row, "key_count"),
            row.get("guard_name", ""),
        )
    )
    guard_funcs = {name: guard for name, _guard_class, _uses_target_id, guard in guard_specs()}
    best_context = best_guard(guard_rows, include_target=False)
    best_target = best_guard([row for row in guard_rows if row.get("uses_target_id") == "1"], include_target=True)
    context_guard_func = guard_funcs.get(best_context.get("guard_name", ""), guard_specs()[0][3])
    target_guard_func = guard_funcs.get(best_target.get("guard_name", ""), guard_specs()[-2][3])
    anchor_rows_list = anchor_rows(large_rows, terminals, context_guard_func, target_guard_func)
    transition_rows_list = transition_rows(delta_rows, large_rows, context_guard_func, target_guard_func)
    summary = build_summary(
        delta_rows,
        large_rows,
        guard_rows,
        anchor_rows_list,
        issue_count=len(issues),
    )
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "anchors.csv", ANCHOR_FIELDNAMES, anchor_rows_list)
    write_csv(output_dir / "guard_candidates.csv", GUARD_FIELDNAMES, guard_rows)
    write_csv(output_dir / "transitions.csv", TRANSITION_FIELDNAMES, transition_rows_list)
    (output_dir / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""))
    (output_dir / "index.html").write_text(
        build_html(summary, anchor_rows_list, guard_rows, transition_rows_list, output_dir, title)
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Split low-tail large-delta palette-walk anchors.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--deltas", type=Path, default=DEFAULT_DELTAS)
    parser.add_argument("--large-deltas", type=Path, default=DEFAULT_LARGE_DELTAS)
    parser.add_argument("--terminals", type=Path, default=DEFAULT_TERMINALS)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Clean Nonzero Palette Walk Low-Tail Anchor Split Probe",
    )
    args = parser.parse_args()

    summary = write_report(args.output, args.deltas, args.large_deltas, args.terminals, title=args.title)
    print(f"Anchors: {summary['low_tail_anchor_rows']}")
    print(f"Best context guard: {summary['best_context_guard']} false={summary['best_context_guard_false_hits']}")
    print(f"Best target guard: {summary['best_target_guard']} false={summary['best_target_guard_false_hits']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
