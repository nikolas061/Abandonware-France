#!/usr/bin/env python3
"""Review the final relative guard for a small nonzero external source byte."""

from __future__ import annotations

import argparse
import csv
import html
import json
from pathlib import Path

from lolg_tex_gap_opcode_probe import relative_href, write_csv
from lolg_tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_selector_probe import (
    int_value,
)


DEFAULT_BROADER_SUMMARY = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_broader_evidence/summary.csv"
)
DEFAULT_BROADER_FORMULAS = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_broader_evidence/formulas.csv"
)
DEFAULT_BROADER_GUARDS = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_broader_evidence/guards.csv"
)
DEFAULT_TARGETS = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_selector/targets.csv"
)
DEFAULT_OUTPUT = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_relative_guard_review"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "target_spans",
    "target_bytes",
    "formula_rows",
    "guard_rows",
    "best_target_span",
    "best_formula",
    "best_guard_key",
    "best_guard_verdict",
    "best_guard_target_rows",
    "best_guard_known_exact_rows",
    "best_guard_known_false_rows",
    "best_guard_reference_exact_rows",
    "best_guard_reference_false_rows",
    "ablation_rows",
    "ablation_false_rows",
    "review_verdict",
    "next_probe",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

TARGET_FIELDNAMES = [
    "rank",
    "span_key",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "span_start",
    "span_end",
    "span_length",
    "expected_hex",
    "best_formula",
    "best_guard_key",
    "review_verdict",
    "promotion_ready",
    "issues",
]

ABLATION_FIELDNAMES = [
    "rank",
    "removed_condition",
    "remaining_guard_key",
    "known_exact_rows",
    "known_false_rows",
    "reference_exact_rows",
    "reference_false_rows",
    "verdict",
]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def split_guard_key(key: str) -> list[str]:
    return [part for part in key.split("+") if part]


def guard_lookup_key(formula: str, key: str) -> tuple[str, str]:
    return formula, key


def select_guard(guard_rows: list[dict[str, str]]) -> dict[str, str]:
    candidates = [
        row
        for row in guard_rows
        if row.get("verdict", "") in {"promotion_ready_guard", "target_and_known_only_guard"}
        and int_value(row, "known_exact_rows") > 0
        and int_value(row, "known_false_rows") == 0
        and int_value(row, "reference_false_rows") == 0
        and int_value(row, "target_rows") > 0
    ]
    candidates.sort(
        key=lambda row: (
            row.get("verdict", "") != "promotion_ready_guard",
            -int_value(row, "reference_exact_rows"),
            -int_value(row, "known_exact_rows"),
            len(split_guard_key(row.get("guard_key", ""))),
            row.get("guard_key", ""),
        )
    )
    return candidates[0] if candidates else {}


def review_verdict(guard: dict[str, str]) -> str:
    if not guard:
        return "missing_relative_guard"
    if int_value(guard, "known_exact_rows") <= 0:
        return "relative_guard_missing_known_support"
    if int_value(guard, "known_false_rows") > 0:
        return "relative_guard_known_false"
    if int_value(guard, "reference_false_rows") > 0:
        return "relative_guard_reference_false"
    if int_value(guard, "reference_exact_rows") <= 0:
        return "relative_guard_target_only"
    return "relative_guard_review_promotion_ready"


def next_probe_for(verdict: str) -> str:
    if verdict == "relative_guard_review_promotion_ready":
        return "promote final reviewed relative small-nonzero external terminal source byte"
    if verdict == "relative_guard_reference_false":
        return "split relative previous-literal guard by remaining reference-false rows"
    if verdict == "relative_guard_target_only":
        return "seek additional known support for relative previous-literal small-nonzero guard"
    return "derive safer relative guard for final small-nonzero external terminal source"


def build(
    summary_rows: list[dict[str, str]],
    formula_rows: list[dict[str, str]],
    guard_rows: list[dict[str, str]],
    target_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    broader_summary = summary_rows[0] if summary_rows else {}
    guard = select_guard(guard_rows)
    verdict = review_verdict(guard)
    target_bytes = sum(int_value(row, "span_length") for row in target_rows)
    promotion_ready = target_bytes if verdict == "relative_guard_review_promotion_ready" else 0
    issue_rows = int_value(broader_summary, "issue_rows")
    if not guard:
        issue_rows += 1

    guards_by_key = {
        guard_lookup_key(row.get("formula", ""), row.get("guard_key", "")): row for row in guard_rows
    }
    ablation_rows: list[dict[str, str]] = []
    if guard:
        conditions = split_guard_key(guard.get("guard_key", ""))
        for condition in conditions:
            remaining = "+".join(part for part in conditions if part != condition)
            row = guards_by_key.get(guard_lookup_key(guard.get("formula", ""), remaining), {})
            ablation_rows.append(
                {
                    "rank": str(len(ablation_rows) + 1),
                    "removed_condition": condition,
                    "remaining_guard_key": remaining,
                    "known_exact_rows": row.get("known_exact_rows", "0"),
                    "known_false_rows": row.get("known_false_rows", "0"),
                    "reference_exact_rows": row.get("reference_exact_rows", "0"),
                    "reference_false_rows": row.get("reference_false_rows", "0"),
                    "verdict": row.get("verdict", "missing_ablation_guard"),
                }
            )

    target_output_rows: list[dict[str, str]] = []
    for index, target in enumerate(target_rows, start=1):
        issues = []
        if not guard:
            issues.append("missing_relative_guard")
        elif promotion_ready == 0:
            issues.append(verdict)
        target_output_rows.append(
            {
                "rank": str(index),
                "span_key": target.get("span_key", ""),
                "archive": target.get("archive", ""),
                "archive_tag": target.get("archive_tag", ""),
                "pcx_name": target.get("pcx_name", ""),
                "frontier_id": target.get("frontier_id", ""),
                "span_start": target.get("span_start", ""),
                "span_end": target.get("span_end", ""),
                "span_length": target.get("span_length", ""),
                "expected_hex": target.get("expected_hex", ""),
                "best_formula": guard.get("formula", ""),
                "best_guard_key": guard.get("guard_key", ""),
                "review_verdict": verdict,
                "promotion_ready": str(promotion_ready),
                "issues": ";".join(issues),
            }
        )

    summary = {
        "scope": "total",
        "candidate_mode": "external_terminal_small_nonzero_relative_guard_review",
        "target_spans": str(len(target_rows)),
        "target_bytes": str(target_bytes),
        "formula_rows": str(len(formula_rows)),
        "guard_rows": str(len(guard_rows)),
        "best_target_span": guard.get("target_span", broader_summary.get("best_target_span", "")),
        "best_formula": guard.get("formula", ""),
        "best_guard_key": guard.get("guard_key", ""),
        "best_guard_verdict": guard.get("verdict", ""),
        "best_guard_target_rows": guard.get("target_rows", "0"),
        "best_guard_known_exact_rows": guard.get("known_exact_rows", "0"),
        "best_guard_known_false_rows": guard.get("known_false_rows", "0"),
        "best_guard_reference_exact_rows": guard.get("reference_exact_rows", "0"),
        "best_guard_reference_false_rows": guard.get("reference_false_rows", "0"),
        "ablation_rows": str(len(ablation_rows)),
        "ablation_false_rows": str(sum(int_value(row, "reference_false_rows") for row in ablation_rows)),
        "review_verdict": verdict,
        "next_probe": next_probe_for(verdict),
        "promotion_candidate_bytes": str(promotion_ready),
        "promotion_ready_bytes": str(promotion_ready),
        "issue_rows": str(issue_rows),
    }
    return summary, target_output_rows, ablation_rows


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 220) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    target_rows: list[dict[str, str]],
    ablation_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "targets": target_rows, "ablations": ablation_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("targets.csv", output_dir / "targets.csv"),
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
  --bg: #101417;
  --panel: #171f22;
  --line: #31424a;
  --text: #edf5f4;
  --muted: #9dafb5;
  --accent: #77d3b1;
  --warn: #f0b36c;
}}
body {{ margin: 0; background: var(--bg); color: var(--text); font: 14px/1.45 system-ui, sans-serif; }}
main {{ width: min(1500px, calc(100vw - 28px)); margin: 0 auto; padding: 22px 0 32px; display: grid; gap: 16px; }}
h1 {{ margin: 0; font-size: 22px; }}
h2 {{ margin: 0 0 10px; font-size: 16px; }}
.muted {{ color: var(--muted); }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 10px; }}
.stat, .panel {{ border: 1px solid var(--line); border-radius: 8px; background: var(--panel); padding: 10px; }}
.value {{ font-size: 22px; font-weight: 760; color: var(--accent); }}
.warn {{ color: var(--warn); }}
.panel {{ overflow-x: auto; }}
table {{ width: 100%; min-width: 1100px; border-collapse: collapse; }}
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
    <div class="muted">Reviews whether the relative previous-literal guard is ready to promote.</div>
  </header>
  <section class="stats">
    <div class="stat"><div class="muted">Known exact/false</div><div class="value">{summary['best_guard_known_exact_rows']}/{summary['best_guard_known_false_rows']}</div></div>
    <div class="stat"><div class="muted">Reference exact/false</div><div class="value">{summary['best_guard_reference_exact_rows']}/{summary['best_guard_reference_false_rows']}</div></div>
    <div class="stat"><div class="muted">Promotion-ready</div><div class="value warn">{summary['promotion_ready_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2>{links}</section>
  <section class="panel">
    <h2>Verdict</h2>
    <p><code>{html.escape(summary['review_verdict'])}</code></p>
    <p class="muted">Guard: <code>{html.escape(summary['best_guard_key'])}</code>. Next: <code>{html.escape(summary['next_probe'])}</code>.</p>
  </section>
  <section class="panel"><h2>Targets</h2>{render_table(target_rows, TARGET_FIELDNAMES)}</section>
  <section class="panel"><h2>Ablations</h2>{render_table(ablation_rows, ABLATION_FIELDNAMES)}</section>
  <script type="application/json" id="external-terminal-small-nonzero-relative-guard-review-data">{html.escape(data_json)}</script>
</main>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Review final relative small nonzero external source guard.")
    parser.add_argument("--broader-summary", type=Path, default=DEFAULT_BROADER_SUMMARY)
    parser.add_argument("--broader-formulas", type=Path, default=DEFAULT_BROADER_FORMULAS)
    parser.add_argument("--broader-guards", type=Path, default=DEFAULT_BROADER_GUARDS)
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex External Terminal Small Nonzero Relative Guard Review",
    )
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    summary, target_rows, ablation_rows = build(
        read_rows(args.broader_summary),
        read_rows(args.broader_formulas),
        read_rows(args.broader_guards),
        read_rows(args.targets),
    )
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, target_rows)
    write_csv(args.output / "ablations.csv", ABLATION_FIELDNAMES, ablation_rows)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, target_rows, ablation_rows, args.output, args.title), encoding="utf-8")
    print(
        "Relative small-nonzero guard review: "
        f"verdict={summary['review_verdict']} "
        f"known={summary['best_guard_known_exact_rows']}/{summary['best_guard_known_false_rows']} "
        f"reference={summary['best_guard_reference_exact_rows']}/{summary['best_guard_reference_false_rows']} "
        f"promotion_ready={summary['promotion_ready_bytes']} "
        f"issues={summary['issue_rows']}"
    )
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
