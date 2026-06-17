#!/usr/bin/env python3
"""Review the target-carrier start-threshold split for promotion."""

from __future__ import annotations

import argparse
import csv
import html
import json
from pathlib import Path

from lolg_tex_gap_opcode_probe import relative_href, write_csv


DEFAULT_CONTEXT_SUMMARY = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_carrier_context_split/summary.csv"
)
DEFAULT_CONTEXT_SPLITS = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_carrier_context_split/splits.csv"
)
DEFAULT_CONTEXT_SAMPLES = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_carrier_context_split/samples.csv"
)
DEFAULT_OUTPUT = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_carrier_context_review"
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
    "best_context",
    "best_threshold",
    "best_direction",
    "best_correct_rows",
    "best_false_rows",
    "best_unknown_rows",
    "threshold_support_ready_rows",
    "threshold_non_oracle_rows",
    "validated_target_rows",
    "validated_non_target_rows",
    "validated_false_rows",
    "validated_unknown_rows",
    "target_atoms",
    "non_target_atoms",
    "review_verdict",
    "next_probe",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

TARGET_FIELDNAMES = [
    "rank",
    "variant_rank",
    "template_key",
    "switch_atom",
    "frontier_id",
    "span_start",
    "span_end",
    "sample_hex",
    "context_match",
    "review_verdict",
    "promotion_ready",
    "issues",
]

REVIEW_FIELDNAMES = [
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
    "review_verdict",
    "promotion_ready_bytes",
]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def int_value(row: dict[str, str], field: str, default: int = 0) -> int:
    try:
        return int(row.get(field, ""))
    except (TypeError, ValueError):
        return default


def context_match(row: dict[str, str], context: str, threshold: int, direction: str) -> bool:
    if context != "span_start":
        return False
    value = int_value(row, "span_start")
    if direction == "lte":
        return value <= threshold
    if direction == "gte":
        return value >= threshold
    return False


def is_threshold_non_oracle(summary: dict[str, str]) -> bool:
    return (
        summary.get("best_context") == "span_start"
        and summary.get("best_direction") in {"lte", "gte"}
        and summary.get("best_threshold", "").isdigit()
    )


def review_verdict(
    summary: dict[str, str],
    samples: list[dict[str, str]],
    best_split: dict[str, str],
) -> str:
    if not samples:
        return "context_review_missing_samples"
    if not best_split:
        return "context_review_missing_split"
    if not is_threshold_non_oracle(summary):
        return "context_review_oracle_or_invalid_threshold"
    if int_value(summary, "best_false_rows") > 0:
        return "context_review_false_rows_block_promotion"
    if int_value(summary, "best_unknown_rows") > 0:
        return "context_review_unknown_rows_block_promotion"
    if int_value(summary, "best_correct_rows") != int_value(summary, "target_sample_rows"):
        return "context_review_incomplete_target_rows"
    if int_value(summary, "non_target_sample_rows") <= 0:
        return "context_review_missing_non_target_validation"
    if int_value(summary, "false_free_context_rows") <= 0:
        return "context_review_no_false_free_split"
    return "context_review_promotion_ready"


def next_probe_for(verdict: str) -> str:
    if verdict == "context_review_promotion_ready":
        return "promote carrier-local start-threshold compact-control five-byte split"
    if verdict == "context_review_missing_non_target_validation":
        return "expand carrier-local non-target validation before promotion"
    if verdict == "context_review_unknown_rows_block_promotion":
        return "tighten carrier-local start-threshold context"
    if verdict == "context_review_false_rows_block_promotion":
        return "reject carrier-local start-threshold split and derive safer context"
    return "fix carrier-local start-threshold promotion review inputs"


def build(
    context_summary_rows: list[dict[str, str]],
    split_rows: list[dict[str, str]],
    sample_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    context_summary = context_summary_rows[0] if context_summary_rows else {}
    best_split = split_rows[0] if split_rows else {}
    threshold = int_value(context_summary, "best_threshold")
    context = context_summary.get("best_context", "")
    direction = context_summary.get("best_direction", "")
    verdict = review_verdict(context_summary, sample_rows, best_split)
    ready = verdict == "context_review_promotion_ready"
    promotion_ready_bytes = int_value(context_summary, "target_bytes") if ready else 0

    target_rows: list[dict[str, str]] = []
    for sample in sample_rows:
        if sample.get("sample_class") != "target":
            continue
        match = context_match(sample, context, threshold, direction)
        issues = "" if ready and match else "context_review_not_ready"
        target_rows.append(
            {
                "rank": "",
                "variant_rank": sample.get("variant_rank", ""),
                "template_key": sample.get("template_key", ""),
                "switch_atom": sample.get("switch_atom", ""),
                "frontier_id": sample.get("frontier_id", ""),
                "span_start": sample.get("span_start", ""),
                "span_end": sample.get("span_end", ""),
                "sample_hex": sample.get("sample_hex", ""),
                "context_match": "1" if match else "0",
                "review_verdict": verdict,
                "promotion_ready": "1" if ready and match else "0",
                "issues": issues,
            }
        )
    target_rows.sort(key=lambda row: (int_value(row, "span_start"), int_value(row, "variant_rank")))
    for index, row in enumerate(target_rows, start=1):
        row["rank"] = str(index)

    reviewed_splits: list[dict[str, str]] = []
    for row in split_rows:
        row_verdict = (
            verdict
            if row.get("context") == context
            and row.get("threshold") == context_summary.get("best_threshold", "")
            and row.get("direction") == direction
            else "context_review_not_selected"
        )
        reviewed_splits.append(
            {
                "rank": "",
                "context": row.get("context", ""),
                "threshold": row.get("threshold", ""),
                "direction": row.get("direction", ""),
                "correct_rows": row.get("correct_rows", "0"),
                "false_rows": row.get("false_rows", "0"),
                "unknown_rows": row.get("unknown_rows", "0"),
                "target_rows": row.get("target_rows", "0"),
                "non_target_rows": row.get("non_target_rows", "0"),
                "target_atoms": row.get("target_atoms", ""),
                "non_target_atoms": row.get("non_target_atoms", ""),
                "split_verdict": row.get("split_verdict", ""),
                "review_verdict": row_verdict,
                "promotion_ready_bytes": str(promotion_ready_bytes if row_verdict == verdict and ready else 0),
            }
        )
    reviewed_splits.sort(
        key=lambda row: (
            row.get("review_verdict") != verdict,
            -int_value(row, "promotion_ready_bytes"),
            int_value(row, "false_rows"),
            int_value(row, "unknown_rows"),
            -int_value(row, "correct_rows"),
        )
    )
    for index, row in enumerate(reviewed_splits, start=1):
        row["rank"] = str(index)

    summary = {
        "scope": "total",
        "candidate_mode": "external_terminal_spatial_bridge_five_byte_target_carrier_context_review",
        "target_spans": context_summary.get("target_spans", "0"),
        "target_bytes": context_summary.get("target_bytes", "0"),
        "carrier_shape": context_summary.get("carrier_shape", ""),
        "target_carrier": context_summary.get("target_carrier", ""),
        "switch_position": context_summary.get("switch_position", ""),
        "sample_rows": context_summary.get("sample_rows", str(len(sample_rows))),
        "target_sample_rows": context_summary.get("target_sample_rows", "0"),
        "non_target_sample_rows": context_summary.get("non_target_sample_rows", "0"),
        "best_context": context,
        "best_threshold": context_summary.get("best_threshold", ""),
        "best_direction": direction,
        "best_correct_rows": context_summary.get("best_correct_rows", "0"),
        "best_false_rows": context_summary.get("best_false_rows", "0"),
        "best_unknown_rows": context_summary.get("best_unknown_rows", "0"),
        "threshold_support_ready_rows": "1" if ready else "0",
        "threshold_non_oracle_rows": "1" if is_threshold_non_oracle(context_summary) else "0",
        "validated_target_rows": str(sum(1 for row in target_rows if row.get("context_match") == "1")),
        "validated_non_target_rows": context_summary.get("non_target_sample_rows", "0"),
        "validated_false_rows": context_summary.get("best_false_rows", "0"),
        "validated_unknown_rows": context_summary.get("best_unknown_rows", "0"),
        "target_atoms": context_summary.get("best_target_atoms", ""),
        "non_target_atoms": context_summary.get("best_non_target_atoms", ""),
        "review_verdict": verdict,
        "next_probe": next_probe_for(verdict),
        "promotion_candidate_bytes": context_summary.get("target_bytes", "0") if ready else "0",
        "promotion_ready_bytes": str(promotion_ready_bytes),
        "issue_rows": context_summary.get("issue_rows", "0"),
    }
    return summary, target_rows, reviewed_splits


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 260) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    targets: list[dict[str, str]],
    splits: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "targets": targets, "splits": splits}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("targets.csv", output_dir / "targets.csv"),
            ("splits.csv", output_dir / "splits.csv"),
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
table {{ width: 100%; min-width: 1320px; border-collapse: collapse; }}
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
    <div class="muted">Reviews the false-free start threshold before allowing promotion.</div>
  </header>
  <section class="stats">
    <div class="stat"><div class="muted">Threshold ready</div><div class="value">{summary['threshold_support_ready_rows']}</div></div>
    <div class="stat"><div class="muted">Validated target</div><div class="value">{summary['validated_target_rows']}</div></div>
    <div class="stat"><div class="muted">False rows</div><div class="value warn">{summary['validated_false_rows']}</div></div>
    <div class="stat"><div class="muted">Unknown rows</div><div class="value warn">{summary['validated_unknown_rows']}</div></div>
    <div class="stat"><div class="muted">Promotion-ready</div><div class="value">{summary['promotion_ready_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2>{links}</section>
  <section class="panel">
    <h2>Verdict</h2>
    <p><code>{html.escape(summary['review_verdict'])}</code></p>
    <p class="muted">Next: <code>{html.escape(summary['next_probe'])}</code>.</p>
  </section>
  <section class="panel"><h2>Targets</h2>{render_table(targets, TARGET_FIELDNAMES)}</section>
  <section class="panel"><h2>Splits</h2>{render_table(splits, REVIEW_FIELDNAMES)}</section>
  <script type="application/json" id="external-terminal-spatial-bridge-five-byte-target-carrier-context-review-data">{html.escape(data_json)}</script>
</main>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Review the target-carrier context split for promotion.")
    parser.add_argument("--context-summary", type=Path, default=DEFAULT_CONTEXT_SUMMARY)
    parser.add_argument("--context-splits", type=Path, default=DEFAULT_CONTEXT_SPLITS)
    parser.add_argument("--context-samples", type=Path, default=DEFAULT_CONTEXT_SAMPLES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex External Terminal Spatial Bridge Five-Byte Target Carrier Context Review",
    )
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    summary, targets, splits = build(
        read_rows(args.context_summary),
        read_rows(args.context_splits),
        read_rows(args.context_samples),
    )
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, targets)
    write_csv(args.output / "splits.csv", REVIEW_FIELDNAMES, splits)
    (args.output / "index.html").write_text(
        build_html(summary, targets, splits, args.output, args.title),
        encoding="utf-8",
    )
    print(
        "External terminal spatial bridge five-byte target carrier context review: "
        f"ready={summary['threshold_support_ready_rows']} "
        f"validated={summary['validated_target_rows']} "
        f"promotion_ready={summary['promotion_ready_bytes']} "
        f"issues={summary['issue_rows']}"
    )
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
