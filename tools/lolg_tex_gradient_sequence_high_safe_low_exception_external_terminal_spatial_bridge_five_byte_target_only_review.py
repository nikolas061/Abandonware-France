#!/usr/bin/env python3
"""Review target-only support for the frontier 80 five-byte bridge guard."""

from __future__ import annotations

import argparse
import csv
import html
import itertools
import json
from pathlib import Path

from lolg_tex_gap_opcode_probe import relative_href, write_csv
from lolg_tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_support_probe import (
    parse_guard_key,
)


DEFAULT_SUPPORT_SUMMARY = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_support/summary.csv"
)
DEFAULT_SUPPORT_TARGETS = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_support/targets.csv"
)
DEFAULT_SUPPORT_ROWS = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_support/support.csv"
)
DEFAULT_OUTPUT = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_only_review"
)

GUARD_FEATURES = [
    "gap_role",
    "span_length",
    "control_ref_mod64",
    "anchor_rel",
    "segment_pair",
]

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "target_spans",
    "target_bytes",
    "support_rows",
    "guard_feature_count",
    "feature_rows",
    "ablation_rows",
    "full_guard_rows",
    "full_guard_spans",
    "full_guard_reference_exact_rows",
    "full_guard_reference_false_rows",
    "full_guard_known_full_rows",
    "full_guard_non_target_rows",
    "exact_non_target_rows",
    "known_exact_rows",
    "known_false_rows",
    "unique_single_features",
    "target_unique_single_feature_keys",
    "relaxed_non_target_rows",
    "relaxed_known_rows",
    "relaxed_false_rows",
    "best_relaxed_feature_set",
    "best_relaxed_rows",
    "best_relaxed_known_rows",
    "best_relaxed_false_rows",
    "review_verdict",
    "next_probe",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

TARGET_FIELDNAMES = [
    "rank",
    "span_key",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "expected_hex",
    "guard_key",
    "support_verdict",
    "full_guard_rows",
    "full_guard_known_full_rows",
    "full_guard_non_target_rows",
    "full_guard_reference_exact_rows",
    "unique_single_features",
    "review_verdict",
    "promotion_ready",
    "issues",
]

FEATURE_FIELDNAMES = [
    "rank",
    "feature",
    "target_value",
    "match_rows",
    "match_spans",
    "target_rows",
    "non_target_rows",
    "exact_rows",
    "false_rows",
    "known_full_rows",
    "known_exact_rows",
    "known_false_rows",
    "verdict",
    "sample_spans",
]

ABLATION_FIELDNAMES = [
    "rank",
    "feature_count",
    "feature_set",
    "match_rows",
    "match_spans",
    "target_rows",
    "non_target_rows",
    "exact_rows",
    "false_rows",
    "known_full_rows",
    "known_exact_rows",
    "known_false_rows",
    "verdict",
    "sample_spans",
]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def int_value(row: dict[str, str], field: str, default: int = 0) -> int:
    try:
        return int(row.get(field, ""))
    except (TypeError, ValueError):
        return default


def feature_sets(features: list[str]) -> list[tuple[str, ...]]:
    output: list[tuple[str, ...]] = []
    for size in range(1, len(features) + 1):
        output.extend(itertools.combinations(features, size))
    return output


def matching_rows(
    rows: list[dict[str, str]],
    guard_parts: dict[str, str],
    fields: tuple[str, ...],
) -> list[dict[str, str]]:
    return [row for row in rows if all(row.get(field, "") == guard_parts.get(field, "") for field in fields)]


def sample_spans(rows: list[dict[str, str]], limit: int = 8) -> str:
    spans = sorted({row.get("span_key", "") for row in rows if row.get("span_key", "")})
    return ",".join(spans[:limit])


def verdict_for(rows: list[dict[str, str]], target_rows: int, non_target_rows: int) -> str:
    if not rows:
        return "no_match"
    false_rows = sum(1 for row in rows if row.get("formula_exact") != "1")
    known_exact_rows = sum(1 for row in rows if row.get("known_full") == "1" and row.get("formula_exact") == "1")
    known_false_rows = sum(1 for row in rows if row.get("known_full") == "1" and row.get("formula_exact") != "1")
    if non_target_rows == 0 and target_rows > 0:
        return "target_only"
    if known_exact_rows > 0 and known_false_rows == 0 and false_rows == 0:
        return "known_exact_candidate"
    if known_false_rows > 0:
        return "known_false_relaxed"
    if false_rows > 0:
        return "reference_false_relaxed"
    return "unresolved_relaxed"


def metrics_for(
    rows: list[dict[str, str]],
    guard_parts: dict[str, str],
    fields: tuple[str, ...],
) -> dict[str, str]:
    matches = matching_rows(rows, guard_parts, fields)
    target_rows = sum(1 for row in matches if row.get("is_target") == "1")
    non_target_rows = sum(1 for row in matches if row.get("is_target") != "1")
    exact_rows = sum(1 for row in matches if row.get("formula_exact") == "1")
    false_rows = len(matches) - exact_rows
    known_full_rows = sum(1 for row in matches if row.get("known_full") == "1")
    known_exact_rows = sum(1 for row in matches if row.get("known_full") == "1" and row.get("formula_exact") == "1")
    known_false_rows = sum(1 for row in matches if row.get("known_full") == "1" and row.get("formula_exact") != "1")
    return {
        "feature_count": str(len(fields)),
        "feature_set": "+".join(fields),
        "match_rows": str(len(matches)),
        "match_spans": str(len({row.get("span_key", "") for row in matches})),
        "target_rows": str(target_rows),
        "non_target_rows": str(non_target_rows),
        "exact_rows": str(exact_rows),
        "false_rows": str(false_rows),
        "known_full_rows": str(known_full_rows),
        "known_exact_rows": str(known_exact_rows),
        "known_false_rows": str(known_false_rows),
        "verdict": verdict_for(matches, target_rows, non_target_rows),
        "sample_spans": sample_spans(matches),
    }


def sort_ablation_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    rows.sort(
        key=lambda row: (
            int_value(row, "feature_count"),
            int_value(row, "non_target_rows") > 0,
            int_value(row, "match_rows"),
            -int_value(row, "exact_rows"),
            row.get("feature_set", ""),
        )
    )
    for index, row in enumerate(rows, start=1):
        row["rank"] = str(index)
    return rows


def review_verdict(
    full_guard: dict[str, str],
    unique_single_features: int,
    exact_non_target_rows: int,
    known_false_rows: int,
) -> str:
    if int_value(full_guard, "known_exact_rows") > 0 and int_value(full_guard, "false_rows") == 0:
        return "known_support_ready"
    if exact_non_target_rows > 0 and known_false_rows == 0:
        return "non_target_exact_review"
    if unique_single_features > 0:
        return "target_unique_features_block_promotion"
    if known_false_rows > 0:
        return "relaxed_known_false_block_promotion"
    return "target_only_support_unresolved"


def next_probe_for(verdict: str) -> str:
    if verdict == "known_support_ready":
        return "promote independently supported frontier 80 five-byte guard"
    if verdict == "non_target_exact_review":
        return "promote non-target exact frontier 80 five-byte guard after fixture replay"
    if verdict == "target_unique_features_block_promotion":
        return "seek independent non-target evidence for frontier 80 five-byte guard"
    if verdict == "relaxed_known_false_block_promotion":
        return "derive safer five-byte guard from relaxed false support"
    return "expand five-byte guard support search outside current operation corpus"


def build(
    support_summary_rows: list[dict[str, str]],
    support_target_rows: list[dict[str, str]],
    support_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    support_summary = support_summary_rows[0] if support_summary_rows else {}
    target = support_target_rows[0] if support_target_rows else {}
    guard_parts = parse_guard_key(target.get("guard_key", support_summary.get("best_guard_key", "")))

    feature_rows: list[dict[str, str]] = []
    for feature in GUARD_FEATURES:
        row = metrics_for(support_rows, guard_parts, (feature,))
        row = {
            "rank": "",
            "feature": feature,
            "target_value": guard_parts.get(feature, ""),
            **{field: row[field] for field in FEATURE_FIELDNAMES if field in row},
        }
        feature_rows.append(row)
    feature_rows.sort(
        key=lambda row: (
            int_value(row, "non_target_rows") > 0,
            int_value(row, "match_rows"),
            row.get("feature", ""),
        )
    )
    for index, row in enumerate(feature_rows, start=1):
        row["rank"] = str(index)

    ablation_rows = []
    for fields in feature_sets(GUARD_FEATURES):
        ablation_rows.append({"rank": "", **metrics_for(support_rows, guard_parts, fields)})
    ablation_rows = sort_ablation_rows(ablation_rows)

    full_guard = metrics_for(support_rows, guard_parts, tuple(GUARD_FEATURES))
    exact_non_target_rows = sum(
        1 for row in support_rows if row.get("is_target") != "1" and row.get("formula_exact") == "1"
    )
    known_exact_rows = sum(
        1 for row in support_rows if row.get("known_full") == "1" and row.get("formula_exact") == "1"
    )
    known_false_rows = sum(
        1 for row in support_rows if row.get("known_full") == "1" and row.get("formula_exact") != "1"
    )
    unique_feature_rows = [
        row for row in feature_rows if row.get("non_target_rows") == "0" and int_value(row, "target_rows") > 0
    ]
    relaxed_rows = [row for row in ablation_rows if row.get("non_target_rows") != "0"]
    relaxed_non_target_rows = max((int_value(row, "non_target_rows") for row in relaxed_rows), default=0)
    relaxed_known_rows = max((int_value(row, "known_full_rows") for row in relaxed_rows), default=0)
    relaxed_false_rows = max((int_value(row, "false_rows") for row in relaxed_rows), default=0)
    best_relaxed = max(
        relaxed_rows,
        key=lambda row: (
            int_value(row, "known_full_rows"),
            int_value(row, "exact_rows"),
            -int_value(row, "false_rows"),
            -int_value(row, "feature_count"),
        ),
        default={},
    )
    verdict = review_verdict(full_guard, len(unique_feature_rows), exact_non_target_rows, known_false_rows)
    promotion_ready = (
        int_value(support_summary, "target_bytes")
        if verdict == "known_support_ready" and int_value(full_guard, "non_target_rows") > 0
        else 0
    )
    summary = {
        "scope": "total",
        "candidate_mode": "external_terminal_spatial_bridge_five_byte_target_only_review",
        "target_spans": support_summary.get("target_spans", str(len(support_target_rows))),
        "target_bytes": support_summary.get("target_bytes", "0"),
        "support_rows": str(len(support_rows)),
        "guard_feature_count": str(len(GUARD_FEATURES)),
        "feature_rows": str(len(feature_rows)),
        "ablation_rows": str(len(ablation_rows)),
        "full_guard_rows": full_guard.get("match_rows", "0"),
        "full_guard_spans": full_guard.get("match_spans", "0"),
        "full_guard_reference_exact_rows": full_guard.get("exact_rows", "0"),
        "full_guard_reference_false_rows": full_guard.get("false_rows", "0"),
        "full_guard_known_full_rows": full_guard.get("known_full_rows", "0"),
        "full_guard_non_target_rows": full_guard.get("non_target_rows", "0"),
        "exact_non_target_rows": str(exact_non_target_rows),
        "known_exact_rows": str(known_exact_rows),
        "known_false_rows": str(known_false_rows),
        "unique_single_features": str(len(unique_feature_rows)),
        "target_unique_single_feature_keys": ",".join(row.get("feature", "") for row in unique_feature_rows),
        "relaxed_non_target_rows": str(relaxed_non_target_rows),
        "relaxed_known_rows": str(relaxed_known_rows),
        "relaxed_false_rows": str(relaxed_false_rows),
        "best_relaxed_feature_set": best_relaxed.get("feature_set", ""),
        "best_relaxed_rows": best_relaxed.get("match_rows", "0"),
        "best_relaxed_known_rows": best_relaxed.get("known_full_rows", "0"),
        "best_relaxed_false_rows": best_relaxed.get("false_rows", "0"),
        "review_verdict": verdict,
        "next_probe": next_probe_for(verdict),
        "promotion_candidate_bytes": "0",
        "promotion_ready_bytes": str(promotion_ready),
        "issue_rows": support_summary.get("issue_rows", "0"),
    }

    target_output_rows = []
    for index, target_row in enumerate(support_target_rows, start=1):
        target_output_rows.append(
            {
                "rank": str(index),
                "span_key": target_row.get("span_key", ""),
                "archive_tag": target_row.get("archive_tag", ""),
                "pcx_name": target_row.get("pcx_name", ""),
                "frontier_id": target_row.get("frontier_id", ""),
                "expected_hex": target_row.get("expected_hex", ""),
                "guard_key": target_row.get("guard_key", ""),
                "support_verdict": target_row.get("support_verdict", ""),
                "full_guard_rows": full_guard.get("match_rows", "0"),
                "full_guard_known_full_rows": full_guard.get("known_full_rows", "0"),
                "full_guard_non_target_rows": full_guard.get("non_target_rows", "0"),
                "full_guard_reference_exact_rows": full_guard.get("exact_rows", "0"),
                "unique_single_features": str(len(unique_feature_rows)),
                "review_verdict": verdict,
                "promotion_ready": str(promotion_ready),
                "issues": "" if promotion_ready else "target_only_support",
            }
        )

    return summary, target_output_rows, feature_rows, ablation_rows


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 260) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    target_rows: list[dict[str, str]],
    feature_rows: list[dict[str, str]],
    ablation_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "targets": target_rows,
        "features": feature_rows,
        "ablations": ablation_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("targets.csv", output_dir / "targets.csv"),
            ("features.csv", output_dir / "features.csv"),
            ("ablations.csv", output_dir / "ablations.csv"),
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
  --panel: #172022;
  --line: #314247;
  --text: #edf5f1;
  --muted: #9faeb2;
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
    <div class="muted">Reviews whether target-only support can be generalized by relaxing guard features.</div>
  </header>
  <section class="stats">
    <div class="stat"><div class="muted">Full guard rows</div><div class="value">{summary['full_guard_rows']}</div></div>
    <div class="stat"><div class="muted">Known full support</div><div class="value warn">{summary['full_guard_known_full_rows']}</div></div>
    <div class="stat"><div class="muted">Non-target exact</div><div class="value warn">{summary['exact_non_target_rows']}</div></div>
    <div class="stat"><div class="muted">Unique single features</div><div class="value warn">{summary['unique_single_features']}</div></div>
    <div class="stat"><div class="muted">Promotion-ready</div><div class="value warn">{summary['promotion_ready_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2>{links}</section>
  <section class="panel">
    <h2>Verdict</h2>
    <p><code>{html.escape(summary['review_verdict'])}</code></p>
    <p class="muted">Next: <code>{html.escape(summary['next_probe'])}</code>.</p>
  </section>
  <section class="panel"><h2>Targets</h2>{render_table(target_rows, TARGET_FIELDNAMES)}</section>
  <section class="panel"><h2>Features</h2>{render_table(feature_rows, FEATURE_FIELDNAMES)}</section>
  <section class="panel"><h2>Ablations</h2>{render_table(ablation_rows, ABLATION_FIELDNAMES)}</section>
  <script type="application/json" id="external-terminal-spatial-bridge-five-byte-target-only-review-data">{html.escape(data_json)}</script>
</main>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Review target-only support for the frontier 80 five-byte guard.")
    parser.add_argument("--support-summary", type=Path, default=DEFAULT_SUPPORT_SUMMARY)
    parser.add_argument("--support-targets", type=Path, default=DEFAULT_SUPPORT_TARGETS)
    parser.add_argument("--support-rows", type=Path, default=DEFAULT_SUPPORT_ROWS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex External Terminal Spatial Bridge Five-Byte Target-Only Review",
    )
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    summary, target_rows, feature_rows, ablation_rows = build(
        read_rows(args.support_summary),
        read_rows(args.support_targets),
        read_rows(args.support_rows),
    )
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, target_rows)
    write_csv(args.output / "features.csv", FEATURE_FIELDNAMES, feature_rows)
    write_csv(args.output / "ablations.csv", ABLATION_FIELDNAMES, ablation_rows)
    (args.output / "index.html").write_text(
        build_html(summary, target_rows, feature_rows, ablation_rows, args.output, args.title),
        encoding="utf-8",
    )
    print(
        "External terminal spatial bridge five-byte target-only review: "
        f"full_guard={summary['full_guard_rows']} "
        f"known={summary['full_guard_known_full_rows']} "
        f"unique_features={summary['unique_single_features']} "
        f"promotion_ready={summary['promotion_ready_bytes']} "
        f"issues={summary['issue_rows']}"
    )
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
