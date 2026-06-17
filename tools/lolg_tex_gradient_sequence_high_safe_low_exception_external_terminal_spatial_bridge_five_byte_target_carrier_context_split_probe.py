#!/usr/bin/env python3
"""Split target-carrier local switch samples by simple local context."""

from __future__ import annotations

import argparse
import csv
import html
import json
from pathlib import Path

from lolg_tex_gap_opcode_probe import relative_href, write_csv


DEFAULT_LOCAL_SWITCH_SUMMARY = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_carrier_local_switch/summary.csv"
)
DEFAULT_LOCAL_SWITCH_SAMPLES = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_carrier_local_switch/samples.csv"
)
DEFAULT_OUTPUT = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_carrier_context_split"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "target_spans",
    "target_bytes",
    "carrier_shape",
    "target_carrier",
    "switch_position",
    "sample_rows",
    "target_sample_rows",
    "non_target_sample_rows",
    "target_min_start",
    "target_max_start",
    "non_target_min_start",
    "non_target_max_start",
    "best_context",
    "best_threshold",
    "best_direction",
    "best_correct_rows",
    "best_false_rows",
    "best_unknown_rows",
    "false_free_context_rows",
    "best_target_atoms",
    "best_non_target_atoms",
    "review_verdict",
    "next_probe",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

SPLIT_FIELDNAMES = [
    "rank",
    "context",
    "threshold",
    "direction",
    "correct_rows",
    "false_rows",
    "unknown_rows",
    "target_rows",
    "non_target_rows",
    "target_atoms",
    "non_target_atoms",
    "split_verdict",
]

SAMPLE_FIELDNAMES = [
    "rank",
    "variant_rank",
    "template_key",
    "switch_atom",
    "frontier_id",
    "sample_class",
    "span_start",
    "span_end",
    "sample_hex",
    "best_context_match",
]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def int_value(row: dict[str, str], field: str, default: int = 0) -> int:
    try:
        return int(row.get(field, ""))
    except (TypeError, ValueError):
        return default


def atom_text(rows: list[dict[str, str]]) -> str:
    return ";".join(sorted({row.get("switch_atom", "") for row in rows if row.get("switch_atom", "")}))


def evaluate_threshold(
    rows: list[dict[str, str]],
    *,
    threshold: int,
    direction: str,
) -> dict[str, str]:
    predicted_target: list[dict[str, str]] = []
    predicted_non_target: list[dict[str, str]] = []
    for row in rows:
        start = int_value(row, "span_start")
        if (direction == "lte" and start <= threshold) or (direction == "gte" and start >= threshold):
            predicted_target.append(row)
        else:
            predicted_non_target.append(row)
    correct = sum(1 for row in predicted_target if row.get("sample_class") == "target")
    false = sum(1 for row in predicted_target if row.get("sample_class") != "target")
    unknown = sum(1 for row in predicted_non_target if row.get("sample_class") == "target")
    return {
        "rank": "",
        "context": "span_start",
        "threshold": str(threshold),
        "direction": direction,
        "correct_rows": str(correct),
        "false_rows": str(false),
        "unknown_rows": str(unknown),
        "target_rows": str(sum(1 for row in rows if row.get("sample_class") == "target")),
        "non_target_rows": str(sum(1 for row in rows if row.get("sample_class") != "target")),
        "target_atoms": atom_text(predicted_target),
        "non_target_atoms": atom_text(predicted_non_target),
        "split_verdict": "false_free_context_split" if correct > 0 and false == 0 and unknown == 0 else "context_split_reject",
    }


def build_splits(sample_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    starts = sorted({int_value(row, "span_start") for row in sample_rows})
    rows: list[dict[str, str]] = []
    for threshold in starts:
        rows.append(evaluate_threshold(sample_rows, threshold=threshold, direction="lte"))
        rows.append(evaluate_threshold(sample_rows, threshold=threshold, direction="gte"))
    rows.sort(
        key=lambda row: (
            row.get("split_verdict") != "false_free_context_split",
            -int_value(row, "correct_rows"),
            int_value(row, "false_rows"),
            int_value(row, "unknown_rows"),
            row.get("direction", ""),
            int_value(row, "threshold"),
        )
    )
    for index, row in enumerate(rows, start=1):
        row["rank"] = str(index)
    return rows


def mark_samples(sample_rows: list[dict[str, str]], best: dict[str, str]) -> list[dict[str, str]]:
    threshold = int_value(best, "threshold")
    direction = best.get("direction", "")
    rows: list[dict[str, str]] = []
    for sample in sample_rows:
        start = int_value(sample, "span_start")
        match = (direction == "lte" and start <= threshold) or (direction == "gte" and start >= threshold)
        row = dict(sample)
        row["best_context_match"] = "1" if match else "0"
        rows.append(row)
    rows.sort(
        key=lambda row: (
            row.get("sample_class") != "target",
            int_value(row, "span_start"),
            int_value(row, "variant_rank"),
        )
    )
    for index, row in enumerate(rows, start=1):
        row["rank"] = str(index)
    return rows


def build(
    local_summary_rows: list[dict[str, str]],
    sample_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    local_summary = local_summary_rows[0] if local_summary_rows else {}
    splits = build_splits(sample_rows)
    best = splits[0] if splits else {}
    marked_samples = mark_samples(sample_rows, best) if best else sample_rows
    target_rows = [row for row in sample_rows if row.get("sample_class") == "target"]
    non_target_rows = [row for row in sample_rows if row.get("sample_class") != "target"]
    false_free = [row for row in splits if row.get("split_verdict") == "false_free_context_split"]
    if false_free:
        verdict = "carrier_local_false_free_context_split_found"
        next_probe = "review carrier-local start-threshold split for promotion"
    elif sample_rows:
        verdict = "carrier_local_context_split_rejected"
        next_probe = "expand carrier-local context features for target family 29"
    else:
        verdict = "carrier_local_context_split_has_no_samples"
        next_probe = "fix carrier-local context split sample inputs"
    summary = {
        "scope": "total",
        "candidate_mode": "external_terminal_spatial_bridge_five_byte_target_carrier_context_split",
        "target_spans": local_summary.get("target_spans", "0"),
        "target_bytes": local_summary.get("target_bytes", "0"),
        "carrier_shape": local_summary.get("carrier_shape", ""),
        "target_carrier": local_summary.get("target_carrier", ""),
        "switch_position": local_summary.get("switch_position", ""),
        "sample_rows": str(len(sample_rows)),
        "target_sample_rows": str(len(target_rows)),
        "non_target_sample_rows": str(len(non_target_rows)),
        "target_min_start": str(min((int_value(row, "span_start") for row in target_rows), default=0)),
        "target_max_start": str(max((int_value(row, "span_start") for row in target_rows), default=0)),
        "non_target_min_start": str(min((int_value(row, "span_start") for row in non_target_rows), default=0)),
        "non_target_max_start": str(max((int_value(row, "span_start") for row in non_target_rows), default=0)),
        "best_context": best.get("context", ""),
        "best_threshold": best.get("threshold", ""),
        "best_direction": best.get("direction", ""),
        "best_correct_rows": best.get("correct_rows", "0"),
        "best_false_rows": best.get("false_rows", "0"),
        "best_unknown_rows": best.get("unknown_rows", "0"),
        "false_free_context_rows": str(len(false_free)),
        "best_target_atoms": best.get("target_atoms", ""),
        "best_non_target_atoms": best.get("non_target_atoms", ""),
        "review_verdict": verdict,
        "next_probe": next_probe,
        "promotion_candidate_bytes": "0",
        "promotion_ready_bytes": "0",
        "issue_rows": "0",
    }
    return summary, splits, marked_samples


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 260) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    splits: list[dict[str, str]],
    samples: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "splits": splits, "samples": samples}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("splits.csv", output_dir / "splits.csv"),
            ("samples.csv", output_dir / "samples.csv"),
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
  --bg: #111416;
  --panel: #182023;
  --line: #314247;
  --text: #edf4f2;
  --muted: #a4b2b5;
  --accent: #7bd5b4;
  --warn: #eebb70;
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
table {{ width: 100%; min-width: 1300px; border-collapse: collapse; }}
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
    <div class="muted">Tests simple local context thresholds for target-carrier samples.</div>
  </header>
  <section class="stats">
    <div class="stat"><div class="muted">Samples</div><div class="value">{summary['sample_rows']}</div></div>
    <div class="stat"><div class="muted">False-free splits</div><div class="value">{summary['false_free_context_rows']}</div></div>
    <div class="stat"><div class="muted">Best threshold</div><div class="value">{html.escape(summary['best_threshold'])}</div></div>
    <div class="stat"><div class="muted">False rows</div><div class="value warn">{summary['best_false_rows']}</div></div>
    <div class="stat"><div class="muted">Promotion-ready</div><div class="value warn">{summary['promotion_ready_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2>{links}</section>
  <section class="panel">
    <h2>Verdict</h2>
    <p><code>{html.escape(summary['review_verdict'])}</code></p>
    <p class="muted">Next: <code>{html.escape(summary['next_probe'])}</code>.</p>
  </section>
  <section class="panel"><h2>Splits</h2>{render_table(splits, SPLIT_FIELDNAMES)}</section>
  <section class="panel"><h2>Samples</h2>{render_table(samples, SAMPLE_FIELDNAMES)}</section>
  <script type="application/json" id="external-terminal-spatial-bridge-five-byte-target-carrier-context-split-data">{html.escape(data_json)}</script>
</main>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Split target-carrier local switch samples by context.")
    parser.add_argument("--local-switch-summary", type=Path, default=DEFAULT_LOCAL_SWITCH_SUMMARY)
    parser.add_argument("--local-switch-samples", type=Path, default=DEFAULT_LOCAL_SWITCH_SAMPLES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex External Terminal Spatial Bridge Five-Byte Target Carrier Context Split Probe",
    )
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    summary, splits, samples = build(
        read_rows(args.local_switch_summary),
        read_rows(args.local_switch_samples),
    )
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "splits.csv", SPLIT_FIELDNAMES, splits)
    write_csv(args.output / "samples.csv", SAMPLE_FIELDNAMES, samples)
    (args.output / "index.html").write_text(
        build_html(summary, splits, samples, args.output, args.title),
        encoding="utf-8",
    )
    print(
        "External terminal spatial bridge five-byte target carrier context split probe: "
        f"samples={summary['sample_rows']} "
        f"false_free={summary['false_free_context_rows']} "
        f"best={summary['best_context']}:{summary['best_direction']}:{summary['best_threshold']} "
        f"promotion_ready={summary['promotion_ready_bytes']} "
        f"issues={summary['issue_rows']}"
    )
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
