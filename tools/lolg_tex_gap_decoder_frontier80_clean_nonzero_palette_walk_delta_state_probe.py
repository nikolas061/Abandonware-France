#!/usr/bin/env python3
"""Profile compact delta-state evidence for Frontier80 palette-walk sequences."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Callable

from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_frontier80_clean_nonzero_palette_walk_delta_state_probe")
DEFAULT_DELTAS = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_generated_sequence_probe/deltas.csv"
)
DEFAULT_TERMINALS = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_generated_sequence_probe/terminal_contexts.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "target_runs",
    "delta_pairs",
    "small_delta_le3_pairs",
    "small_delta_le3_ratio",
    "large_delta_pairs",
    "high_high_large_delta_pairs",
    "tail_large_delta_pairs",
    "large_delta_mode_pairs",
    "best_delta_insample_context",
    "best_delta_insample_exact",
    "best_delta_loo_context",
    "best_delta_loo_exact",
    "best_delta_loo_missing",
    "best_delta_loo_conflicted",
    "state_bucket_rows",
    "terminal_contexts",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

CONTEXT_FIELDNAMES = [
    "train_mode",
    "context_name",
    "samples",
    "covered_samples",
    "exact_samples",
    "missing_samples",
    "conflicted_samples",
    "context_keys",
    "conflict_keys",
    "exact_ratio",
    "covered_exact_ratio",
    "verdict",
]

BUCKET_FIELDNAMES = [
    "context_name",
    "context_key",
    "delta_pairs",
    "small_delta_le3_pairs",
    "large_delta_pairs",
    "unique_deltas",
    "dominant_delta",
    "dominant_delta_pairs",
    "dominant_delta_ratio",
    "delta_histogram",
]

LARGE_FIELDNAMES = [
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
]

Item = dict[str, object]
ContextFunc = Callable[[list[Item], int], tuple[object, ...]]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def signed_delta(left: int, right: int) -> int:
    value = (right - left) & 0xFF
    return value if value < 128 else value - 256


def parse_hex(text: str) -> int:
    return int(text, 16) if text else 0


def delta_histogram(counter: Counter[int]) -> str:
    return " ".join(f"{delta}:{count}" for delta, count in sorted(counter.items()))


def context_key_text(key: tuple[object, ...]) -> str:
    return "|".join(str(part) for part in key)


def load_sequences(delta_rows: list[dict[str, str]]) -> dict[str, list[Item]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in delta_rows:
        grouped[row.get("target_id", "")].append(row)

    sequences: dict[str, list[Item]] = {}
    for target_id, rows in grouped.items():
        rows.sort(key=lambda row: int_value(row, "transition_index"))
        if not rows:
            continue
        first = rows[0]
        items: list[Item] = [
            {
                "target_id": target_id,
                "run_offset": int_value(first, "from_run_offset"),
                "absolute": int_value(first, "from_abs"),
                "row": int_value(first, "from_row"),
                "col": int_value(first, "from_col"),
                "mode": first.get("from_mode", ""),
                "value": parse_hex(first.get("from_value_hex", "")),
            }
        ]
        for row in rows:
            items.append(
                {
                    "target_id": target_id,
                    "run_offset": int_value(row, "to_run_offset"),
                    "absolute": int_value(row, "to_abs"),
                    "row": int_value(row, "to_row"),
                    "col": int_value(row, "to_col"),
                    "mode": row.get("to_mode", ""),
                    "value": parse_hex(row.get("to_value_hex", "")),
                }
            )
        sequences[target_id] = items
    return sequences


def transition_delta(items: list[Item], index: int) -> int:
    return signed_delta(int(items[index - 1]["value"]), int(items[index]["value"]))


def previous_delta(items: list[Item], index: int) -> int | None:
    if index < 2:
        return None
    return transition_delta(items, index - 1)


def context_specs() -> list[tuple[str, ContextFunc]]:
    return [
        ("prev_value", lambda items, index: (items[index - 1]["value"],)),
        ("prev_delta", lambda items, index: (previous_delta(items, index),)),
        (
            "prev_delta_value",
            lambda items, index: (
                previous_delta(items, index),
                items[index - 1]["value"],
            ),
        ),
        (
            "prev_delta2",
            lambda items, index: (
                previous_delta(items, index - 1) if index >= 2 else None,
                previous_delta(items, index),
            ),
        ),
        ("mode_pair", lambda items, index: (items[index - 1]["mode"], items[index]["mode"])),
        (
            "mode_pair_prev_value",
            lambda items, index: (
                items[index - 1]["mode"],
                items[index]["mode"],
                items[index - 1]["value"],
            ),
        ),
        ("col_mod8", lambda items, index: (int(items[index]["col"]) % 8,)),
        ("col_mod16", lambda items, index: (int(items[index]["col"]) % 16,)),
        ("col_mod32", lambda items, index: (int(items[index]["col"]) % 32,)),
        ("row_col_mod32", lambda items, index: (items[index]["row"], int(items[index]["col"]) % 32)),
        (
            "prev_delta_col_mod32",
            lambda items, index: (
                previous_delta(items, index),
                int(items[index]["col"]) % 32,
            ),
        ),
        (
            "prev_value_col_mod32",
            lambda items, index: (
                items[index - 1]["value"],
                int(items[index]["col"]) % 32,
            ),
        ),
        (
            "prev_value_row_col_mod32",
            lambda items, index: (
                items[index - 1]["value"],
                items[index]["row"],
                int(items[index]["col"]) % 32,
            ),
        ),
    ]


def build_context_table(
    sequences: list[tuple[str, list[Item]]],
    context: ContextFunc,
) -> dict[tuple[object, ...], Counter[int]]:
    table: dict[tuple[object, ...], Counter[int]] = defaultdict(Counter)
    for _target_id, items in sequences:
        for index in range(1, len(items)):
            table[context(items, index)][transition_delta(items, index)] += 1
    return table


def score_context(
    context_name: str,
    context: ContextFunc,
    all_sequences: list[tuple[str, list[Item]]],
    *,
    train_mode: str,
) -> dict[str, str]:
    exact = 0
    missing = 0
    conflicted_samples = 0
    samples = 0
    context_keys = 0
    conflict_keys = 0
    if train_mode == "insample":
        table = build_context_table(all_sequences, context)
        context_keys = len(table)
        conflict_keys = sum(1 for counter in table.values() if len(counter) > 1)
        holdouts = [(table, all_sequences)]
    else:
        holdouts = []
        for target_id, items in all_sequences:
            train = [(other_id, other_items) for other_id, other_items in all_sequences if other_id != target_id]
            table = build_context_table(train, context)
            context_keys += len(table)
            conflict_keys += sum(1 for counter in table.values() if len(counter) > 1)
            holdouts.append((table, [(target_id, items)]))
    for table, held in holdouts:
        for _target_id, items in held:
            for index in range(1, len(items)):
                samples += 1
                key = context(items, index)
                counter = table.get(key)
                if not counter:
                    missing += 1
                    continue
                if len(counter) > 1:
                    conflicted_samples += 1
                predicted = counter.most_common(1)[0][0]
                if predicted == transition_delta(items, index):
                    exact += 1
    covered = samples - missing
    if exact == samples and samples:
        verdict = "delta_context_deterministic"
    elif train_mode == "leave_one_run_out" and exact >= int(samples * 0.9) and missing == 0:
        verdict = "delta_context_strong"
    elif train_mode == "leave_one_run_out" and exact < int(samples * 0.5):
        verdict = "delta_context_not_predictive"
    else:
        verdict = "delta_context_partial"
    return {
        "train_mode": train_mode,
        "context_name": context_name,
        "samples": str(samples),
        "covered_samples": str(covered),
        "exact_samples": str(exact),
        "missing_samples": str(missing),
        "conflicted_samples": str(conflicted_samples),
        "context_keys": str(context_keys),
        "conflict_keys": str(conflict_keys),
        "exact_ratio": f"{exact / samples:.6f}" if samples else "0.000000",
        "covered_exact_ratio": f"{exact / covered:.6f}" if covered else "0.000000",
        "verdict": verdict,
    }


def context_rows(sequences: dict[str, list[Item]]) -> list[dict[str, str]]:
    all_sequences = sorted(sequences.items())
    rows: list[dict[str, str]] = []
    for context_name, context in context_specs():
        rows.append(score_context(context_name, context, all_sequences, train_mode="insample"))
        rows.append(score_context(context_name, context, all_sequences, train_mode="leave_one_run_out"))
    rows.sort(
        key=lambda row: (
            row.get("train_mode", ""),
            -int_value(row, "exact_samples"),
            int_value(row, "missing_samples"),
            row.get("context_name", ""),
        )
    )
    return rows


def bucket_rows(sequences: dict[str, list[Item]]) -> list[dict[str, str]]:
    selected = {
        "mode_pair": lambda items, index: (items[index - 1]["mode"], items[index]["mode"]),
        "from_value": lambda items, index: (f"{int(items[index - 1]['value']):02x}",),
        "col_mod8": lambda items, index: (int(items[index]["col"]) % 8,),
        "row_col_mod32": lambda items, index: (items[index]["row"], int(items[index]["col"]) % 32),
        "prev_delta": lambda items, index: (previous_delta(items, index),),
    }
    buckets: list[dict[str, str]] = []
    for context_name, context in selected.items():
        counters: dict[tuple[object, ...], Counter[int]] = defaultdict(Counter)
        for items in sequences.values():
            for index in range(1, len(items)):
                counters[context(items, index)][transition_delta(items, index)] += 1
        for key, counter in counters.items():
            total = sum(counter.values())
            small = sum(count for delta, count in counter.items() if abs(delta) <= 3)
            dominant_delta, dominant_count = counter.most_common(1)[0]
            buckets.append(
                {
                    "context_name": context_name,
                    "context_key": context_key_text(key),
                    "delta_pairs": str(total),
                    "small_delta_le3_pairs": str(small),
                    "large_delta_pairs": str(total - small),
                    "unique_deltas": str(len(counter)),
                    "dominant_delta": str(dominant_delta),
                    "dominant_delta_pairs": str(dominant_count),
                    "dominant_delta_ratio": f"{dominant_count / total:.6f}" if total else "0.000000",
                    "delta_histogram": delta_histogram(counter),
                }
            )
    buckets.sort(
        key=lambda row: (
            -int_value(row, "large_delta_pairs"),
            row.get("context_name", ""),
            row.get("context_key", ""),
        )
    )
    return buckets


def terminal_offsets(terminal_rows: list[dict[str, str]]) -> dict[str, list[tuple[int, int]]]:
    offsets: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for row in terminal_rows:
        offsets[row.get("target_id", "")].append((int_value(row, "run_offset_start"), int_value(row, "run_offset_end")))
    return offsets


def large_delta_rows(
    delta_rows: list[dict[str, str]],
    terminal_rows_list: list[dict[str, str]],
) -> list[dict[str, str]]:
    terminals = terminal_offsets(terminal_rows_list)
    rows: list[dict[str, str]] = []
    for row in delta_rows:
        if int_value(row, "abs_delta") <= 3:
            continue
        target_id = row.get("target_id", "")
        from_mode = row.get("from_mode", "")
        to_mode = row.get("to_mode", "")
        mode_pair = f"{from_mode}->{to_mode}"
        tail_state = "high_prefix" if from_mode == "high_add_0x11" and to_mode == "high_add_0x11" else "tail_or_mixed"
        from_offset = int_value(row, "from_run_offset")
        to_offset = int_value(row, "to_run_offset")
        near_terminal = any(abs(from_offset - start) <= 2 or abs(to_offset - end) <= 2 for start, end in terminals[target_id])
        rows.append(
            {
                "target_id": target_id,
                "transition_index": row.get("transition_index", ""),
                "from_run_offset": row.get("from_run_offset", ""),
                "to_run_offset": row.get("to_run_offset", ""),
                "from_abs": row.get("from_abs", ""),
                "to_abs": row.get("to_abs", ""),
                "from_row": row.get("from_row", ""),
                "to_row": row.get("to_row", ""),
                "from_col": row.get("from_col", ""),
                "to_col": row.get("to_col", ""),
                "from_mode": from_mode,
                "to_mode": to_mode,
                "from_value_hex": row.get("from_value_hex", ""),
                "to_value_hex": row.get("to_value_hex", ""),
                "delta": row.get("delta", ""),
                "abs_delta": row.get("abs_delta", ""),
                "mode_pair": mode_pair,
                "tail_state": tail_state,
                "near_terminal": "1" if near_terminal else "0",
            }
        )
    return rows


def best_context(rows: list[dict[str, str]], train_mode: str) -> dict[str, str]:
    choices = [row for row in rows if row.get("train_mode") == train_mode]
    if not choices:
        return {}
    return max(
        choices,
        key=lambda row: (
            int_value(row, "exact_samples"),
            -int_value(row, "missing_samples"),
            -int_value(row, "conflicted_samples"),
            row.get("context_name", ""),
        ),
    )


def build_summary(
    delta_rows_list: list[dict[str, str]],
    context_rows_list: list[dict[str, str]],
    bucket_rows_list: list[dict[str, str]],
    large_rows: list[dict[str, str]],
    terminal_rows_list: list[dict[str, str]],
    *,
    issue_count: int,
) -> dict[str, str]:
    target_runs = len({row.get("target_id", "") for row in delta_rows_list})
    delta_pairs = len(delta_rows_list)
    small = sum(int_value(row, "small_delta_le3") for row in delta_rows_list)
    high_high_large = sum(1 for row in large_rows if row.get("tail_state") == "high_prefix")
    tail_large = sum(1 for row in large_rows if row.get("tail_state") == "tail_or_mixed")
    mode_pairs = ",".join(sorted({row.get("mode_pair", "") for row in large_rows if row.get("mode_pair")}))
    best_insample = best_context(context_rows_list, "insample")
    best_loo = best_context(context_rows_list, "leave_one_run_out")
    if delta_pairs and int_value(best_loo, "exact_samples") == delta_pairs:
        verdict = "frontier80_clean_nonzero_palette_walk_delta_state_ready"
        next_probe = "promote compact palette-walk delta-state producer with terminal guards"
    elif large_rows and not high_high_large:
        verdict = "frontier80_clean_nonzero_palette_walk_delta_state_tail_split_needed"
        next_probe = "split palette-walk low-tail large-delta anchors before exact delta-state promotion"
    elif delta_pairs:
        verdict = "frontier80_clean_nonzero_palette_walk_delta_state_context_partial"
        next_probe = "expand palette-walk delta-state contexts beyond local value and phase"
    else:
        verdict = "frontier80_clean_nonzero_palette_walk_delta_state_no_pairs"
        next_probe = "return to generated palette-walk sequence profile"
    return {
        "scope": "total",
        "target_runs": str(target_runs),
        "delta_pairs": str(delta_pairs),
        "small_delta_le3_pairs": str(small),
        "small_delta_le3_ratio": f"{small / delta_pairs:.6f}" if delta_pairs else "0.000000",
        "large_delta_pairs": str(len(large_rows)),
        "high_high_large_delta_pairs": str(high_high_large),
        "tail_large_delta_pairs": str(tail_large),
        "large_delta_mode_pairs": mode_pairs,
        "best_delta_insample_context": best_insample.get("context_name", ""),
        "best_delta_insample_exact": f"{best_insample.get('exact_samples', '0')}/{best_insample.get('samples', '0')}",
        "best_delta_loo_context": best_loo.get("context_name", ""),
        "best_delta_loo_exact": f"{best_loo.get('exact_samples', '0')}/{best_loo.get('samples', '0')}",
        "best_delta_loo_missing": best_loo.get("missing_samples", "0"),
        "best_delta_loo_conflicted": best_loo.get("conflicted_samples", "0"),
        "state_bucket_rows": str(len(bucket_rows_list)),
        "terminal_contexts": str(len(terminal_rows_list)),
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
    context_rows_list: list[dict[str, str]],
    bucket_rows_list: list[dict[str, str]],
    large_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "contexts": context_rows_list,
        "state_buckets": bucket_rows_list,
        "large_deltas": large_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("context_scores.csv", output_dir / "context_scores.csv"),
            ("state_buckets.csv", output_dir / "state_buckets.csv"),
            ("large_deltas.csv", output_dir / "large_deltas.csv"),
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
    <div class="sub">Scores delta-state contexts and isolates large low-tail palette-walk jumps.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Delta <= 3</div><div class="value">{html.escape(summary['small_delta_le3_pairs'])}/{html.escape(summary['delta_pairs'])}</div></div>
    <div class="stat"><div class="label">Large tail deltas</div><div class="value warn">{html.escape(summary['tail_large_delta_pairs'])}</div></div>
    <div class="stat"><div class="label">Best Delta LOO</div><div class="value">{html.escape(summary['best_delta_loo_context'])}: {html.escape(summary['best_delta_loo_exact'])}</div></div>
    <div class="stat"><div class="label">Mode pairs</div><div class="value">{html.escape(summary['large_delta_mode_pairs'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div><div class="sub">{html.escape(summary['review_verdict'])}: {html.escape(summary['next_probe'])}</div></section>
  <section class="panel"><h2>Large Deltas</h2>{render_table(large_rows, LARGE_FIELDNAMES)}</section>
  <section class="panel"><h2>Context Scores</h2>{render_table(context_rows_list, CONTEXT_FIELDNAMES)}</section>
  <section class="panel"><h2>State Buckets</h2>{render_table(bucket_rows_list, BUCKET_FIELDNAMES)}</section>
</main>
<script type="application/json" id="palette-walk-delta-state-data">{data_json}</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    deltas_path: Path,
    terminals_path: Path,
    *,
    title: str,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    try:
        delta_rows_list = read_csv(deltas_path)
    except OSError as exc:
        issues.append(f"read_deltas_failed:{exc}")
        delta_rows_list = []
    try:
        terminal_rows_list = read_csv(terminals_path)
    except OSError as exc:
        issues.append(f"read_terminals_failed:{exc}")
        terminal_rows_list = []
    sequences = load_sequences(delta_rows_list)
    context_rows_list = context_rows(sequences)
    bucket_rows_list = bucket_rows(sequences)
    large_rows = large_delta_rows(delta_rows_list, terminal_rows_list)
    summary = build_summary(
        delta_rows_list,
        context_rows_list,
        bucket_rows_list,
        large_rows,
        terminal_rows_list,
        issue_count=len(issues),
    )
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "context_scores.csv", CONTEXT_FIELDNAMES, context_rows_list)
    write_csv(output_dir / "state_buckets.csv", BUCKET_FIELDNAMES, bucket_rows_list)
    write_csv(output_dir / "large_deltas.csv", LARGE_FIELDNAMES, large_rows)
    (output_dir / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""))
    (output_dir / "index.html").write_text(
        build_html(summary, context_rows_list, bucket_rows_list, large_rows, output_dir, title)
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile compact delta-state support for palette-walk runs.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--deltas", type=Path, default=DEFAULT_DELTAS)
    parser.add_argument("--terminals", type=Path, default=DEFAULT_TERMINALS)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Clean Nonzero Palette Walk Delta-State Probe",
    )
    args = parser.parse_args()

    summary = write_report(args.output, args.deltas, args.terminals, title=args.title)
    print(f"Delta <=3: {summary['small_delta_le3_pairs']}/{summary['delta_pairs']}")
    print(f"Large tail deltas: {summary['tail_large_delta_pairs']}")
    print(f"Best delta LOO: {summary['best_delta_loo_context']} {summary['best_delta_loo_exact']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
