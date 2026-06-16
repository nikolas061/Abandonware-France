#!/usr/bin/env python3
"""Score source-side selectors for post-large32 medium8 internal zero targets."""

from __future__ import annotations

import argparse
import html
import json
from collections import defaultdict
from pathlib import Path

from lolg_tex_gap_decoder_len64_promoted_large32_selector_probe import (
    CANDIDATE_FIELDNAMES,
    GREEDY_FIELDNAMES,
    TARGET_FIELDNAMES,
    annotate_targets,
    candidate_row,
    feature_text,
    operation_key,
    read_csv,
    render_table,
    source_features,
    target_key,
)
from lolg_tex_gap_decoder_unresolved_zero_queue import length_bucket
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_len64_promoted_medium8_selector_probe")
DEFAULT_TARGETS = Path("output/tex_gap_decoder_len64_promoted_large32_zero_source_probe/targets.csv")
DEFAULT_OPERATIONS = Path("output/tex_gap_segmentation_control_correlation_probe/operations.csv")
TARGET_SIGNATURE = "internal|medium8|left_nonzero|right_nonzero"
TARGET_BUCKET = "medium8"
PAIR_FAMILY = "medium8_pair"
GREEDY_MIN_TARGET_ROWS = 2

Feature = tuple[str, str]
CandidateKey = tuple[str, tuple[Feature, ...]]
OperationKey = tuple[str, str, str, str]

SUMMARY_FIELDNAMES = [
    "scope",
    "target_signature",
    "target_bucket",
    "operation_rows",
    "source_target_rows",
    "target_rows",
    "target_bytes",
    "joined_target_rows",
    "bucket_operation_rows",
    "bucket_zero_rows",
    "bucket_false_rows",
    "candidate_rows",
    "false_free_candidate_rows",
    "best_selector",
    "best_selector_family",
    "best_selector_target_rows",
    "best_selector_target_bytes",
    "best_selector_operation_rows",
    "best_selector_zero_bytes",
    "best_selector_false_bytes",
    "greedy_min_target_rows",
    "greedy_selector_rows",
    "greedy_target_rows",
    "greedy_target_bytes",
    "greedy_operation_rows",
    "greedy_zero_bytes",
    "greedy_false_bytes",
    "issue_rows",
]


def candidate_keys(row: dict[str, str]) -> list[CandidateKey]:
    features = source_features(row)
    keys: list[CandidateKey] = [("single", (feature,)) for feature in features]
    bucket_feature = ("bucket", TARGET_BUCKET)
    if bucket_feature in features:
        for feature in features:
            if feature == bucket_feature:
                continue
            keys.append((PAIR_FAMILY, tuple(sorted((bucket_feature, feature)))))
    return keys


def build_candidates(
    operation_rows: list[dict[str, str]],
    target_keys: set[OperationKey],
) -> tuple[list[dict[str, str]], dict[str, set[OperationKey]], dict[str, set[OperationKey]]]:
    grouped: dict[CandidateKey, list[dict[str, str]]] = defaultdict(list)
    for operation in operation_rows:
        for key in candidate_keys(operation):
            grouped[key].append(operation)

    candidate_rows: list[dict[str, str]] = []
    selector_targets: dict[str, set[OperationKey]] = {}
    selector_operations: dict[str, set[OperationKey]] = {}
    for (family, features), rows in grouped.items():
        if not any(operation_key(row) in target_keys for row in rows):
            continue
        row = candidate_row(family, features, rows, target_keys, len(target_keys))
        candidate_rows.append(row)
        selector_targets[row["selector"]] = {
            operation_key(item) for item in rows if operation_key(item) in target_keys
        }
        selector_operations[row["selector"]] = {operation_key(item) for item in rows}

    candidate_rows.sort(
        key=lambda row: (
            row.get("promotion_class") not in {"source_false_free", "target_only_false_free"},
            -int_value(row, "target_bytes"),
            int_value(row, "false_bytes"),
            -int_value(row, "operation_bytes"),
            int_value(row, "feature_count"),
            row.get("selector", ""),
        )
    )
    return candidate_rows, selector_targets, selector_operations


def greedy_rows(
    candidate_rows: list[dict[str, str]],
    selector_targets: dict[str, set[OperationKey]],
    selector_operations: dict[str, set[OperationKey]],
    operations_by_key: dict[OperationKey, dict[str, str]],
) -> tuple[list[dict[str, str]], set[OperationKey], set[OperationKey]]:
    eligible = [
        row
        for row in candidate_rows
        if row.get("family") == PAIR_FAMILY
        and row.get("promotion_class") in {"source_false_free", "target_only_false_free"}
        and int_value(row, "target_rows") >= GREEDY_MIN_TARGET_ROWS
    ]
    covered_targets: set[OperationKey] = set()
    covered_operations: set[OperationKey] = set()
    output_rows: list[dict[str, str]] = []

    while True:
        best: dict[str, str] | None = None
        best_gain = 0
        for row in eligible:
            gain = len(selector_targets.get(row["selector"], set()) - covered_targets)
            if gain <= 0:
                continue
            if best is None:
                best = row
                best_gain = gain
                continue
            best_sort = (
                best_gain,
                int_value(best, "target_rows"),
                int_value(best, "operation_bytes"),
                -int_value(best, "feature_count"),
                best.get("selector", ""),
            )
            row_sort = (
                gain,
                int_value(row, "target_rows"),
                int_value(row, "operation_bytes"),
                -int_value(row, "feature_count"),
                row.get("selector", ""),
            )
            if row_sort > best_sort:
                best = row
                best_gain = gain
        if best is None:
            break
        selector = best["selector"]
        covered_targets.update(selector_targets.get(selector, set()))
        covered_operations.update(selector_operations.get(selector, set()))
        output_rows.append(
            {
                "order": str(len(output_rows) + 1),
                "selector": selector,
                "family": best.get("family", ""),
                "added_target_rows": str(best_gain),
                "cumulative_target_rows": str(len(covered_targets)),
                "operation_rows": best.get("operation_rows", "0"),
                "zero_bytes": best.get("zero_bytes", "0"),
                "false_bytes": best.get("false_bytes", "0"),
                "sample_rank": best.get("sample_rank", ""),
                "sample_pcx": best.get("sample_pcx", ""),
                "sample_frontier_id": best.get("sample_frontier_id", ""),
                "sample_op_index": best.get("sample_op_index", ""),
            }
        )

    existing_operations = {key for key in covered_operations if key in operations_by_key}
    return output_rows, covered_targets, existing_operations


def select_targets(target_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        row
        for row in target_rows
        if not row.get("issues")
        and row.get("signature") == TARGET_SIGNATURE
        and row.get("queue_class") == "review_internal_zero"
        and row.get("length_bucket") == TARGET_BUCKET
    ]


def build_rows(
    source_target_rows: list[dict[str, str]],
    operation_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    target_rows = select_targets(source_target_rows)
    target_keys = {target_key(row) for row in target_rows}
    operations_by_key = {operation_key(row): row for row in operation_rows}
    candidate_rows, selector_targets, selector_operations = build_candidates(operation_rows, target_keys)
    false_free = [
        row
        for row in candidate_rows
        if row.get("promotion_class") in {"source_false_free", "target_only_false_free"}
    ]
    best = false_free[0] if false_free else {}
    greedy, greedy_targets, greedy_operations = greedy_rows(
        candidate_rows,
        selector_targets,
        selector_operations,
        operations_by_key,
    )
    greedy_operation_rows = [operations_by_key[key] for key in greedy_operations]
    bucket_rows = [
        row for row in operation_rows if length_bucket(int_value(row, "length")) == TARGET_BUCKET
    ]
    joined_targets = sum(1 for key in target_keys if key in operations_by_key)
    annotated_targets = annotate_targets(
        target_rows,
        best.get("selector", ""),
        greedy,
        selector_targets,
        candidate_rows,
    )
    issue_rows = sum(1 for row in target_rows if row.get("issues")) + sum(
        1 for row in operation_rows if row.get("issues")
    )
    if joined_targets != len(target_rows):
        issue_rows += len(target_rows) - joined_targets

    summary = {
        "scope": "total",
        "target_signature": TARGET_SIGNATURE,
        "target_bucket": TARGET_BUCKET,
        "operation_rows": str(len(operation_rows)),
        "source_target_rows": str(len(source_target_rows)),
        "target_rows": str(len(target_rows)),
        "target_bytes": str(sum(int_value(row, "length") for row in target_rows)),
        "joined_target_rows": str(joined_targets),
        "bucket_operation_rows": str(len(bucket_rows)),
        "bucket_zero_rows": str(sum(1 for row in bucket_rows if row.get("op_kind") == "zero")),
        "bucket_false_rows": str(sum(1 for row in bucket_rows if row.get("op_kind") != "zero")),
        "candidate_rows": str(len(candidate_rows)),
        "false_free_candidate_rows": str(len(false_free)),
        "best_selector": best.get("selector", ""),
        "best_selector_family": best.get("family", ""),
        "best_selector_target_rows": best.get("target_rows", "0"),
        "best_selector_target_bytes": best.get("target_bytes", "0"),
        "best_selector_operation_rows": best.get("operation_rows", "0"),
        "best_selector_zero_bytes": best.get("zero_bytes", "0"),
        "best_selector_false_bytes": best.get("false_bytes", "0"),
        "greedy_min_target_rows": str(GREEDY_MIN_TARGET_ROWS),
        "greedy_selector_rows": str(len(greedy)),
        "greedy_target_rows": str(len(greedy_targets)),
        "greedy_target_bytes": str(
            sum(int_value(operations_by_key[key], "length") for key in greedy_targets if key in operations_by_key)
        ),
        "greedy_operation_rows": str(len(greedy_operations)),
        "greedy_zero_bytes": str(
            sum(int_value(row, "length") for row in greedy_operation_rows if row.get("op_kind") == "zero")
        ),
        "greedy_false_bytes": str(
            sum(int_value(row, "length") for row in greedy_operation_rows if row.get("op_kind") != "zero")
        ),
        "issue_rows": str(issue_rows),
    }
    return summary, candidate_rows, greedy, annotated_targets


def build_html(
    summary: dict[str, str],
    candidates: list[dict[str, str]],
    greedy: list[dict[str, str]],
    targets: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "candidates": candidates,
        "greedy": greedy,
        "targets": targets,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("candidates.csv", output_dir / "candidates.csv"),
            ("greedy.csv", output_dir / "greedy.csv"),
            ("targets.csv", output_dir / "targets.csv"),
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
  --ok: #80df94;
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
.ok {{ color: var(--ok); }}
.panel {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; min-width: 1440px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Scores source-side selectors for post-large32 medium8 internal zero targets.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Target bytes</div><div class="value">{summary['target_bytes']}</div></div>
    <div class="stat"><div class="label">Best target bytes</div><div class="value">{summary['best_selector_target_bytes']}</div></div>
    <div class="stat"><div class="label">Best false bytes</div><div class="value ok">{summary['best_selector_false_bytes']}</div></div>
    <div class="stat"><div class="label">Greedy target bytes</div><div class="value">{summary['greedy_target_bytes']}</div></div>
    <div class="stat"><div class="label">Greedy selectors</div><div class="value">{summary['greedy_selector_rows']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2><div>{links}</div></section>
  <section class="panel"><h2>Greedy false-free union</h2>{render_table(greedy, GREEDY_FIELDNAMES, 120)}</section>
  <section class="panel"><h2>Candidates</h2>{render_table(candidates, CANDIDATE_FIELDNAMES, 180)}</section>
  <section class="panel"><h2>Targets</h2>{render_table(targets, TARGET_FIELDNAMES, 120)}</section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_SELECTOR_PROBE = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Score source-side selectors for post-large32 medium8 internal zero targets."
    )
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("--operations", type=Path, default=DEFAULT_OPERATIONS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Len64 Promoted Medium8 Selector Probe")
    args = parser.parse_args()

    summary, candidates, greedy, targets = build_rows(read_csv(args.targets), read_csv(args.operations))
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "candidates.csv", CANDIDATE_FIELDNAMES, candidates)
    write_csv(args.output / "greedy.csv", GREEDY_FIELDNAMES, greedy)
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, targets)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, candidates, greedy, targets, args.output, args.title))

    print(f"Target rows: {summary['target_rows']}")
    print(f"Best selector: {summary['best_selector']}")
    print(f"Best target bytes: {summary['best_selector_target_bytes']}")
    print(f"Greedy target bytes: {summary['greedy_target_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
