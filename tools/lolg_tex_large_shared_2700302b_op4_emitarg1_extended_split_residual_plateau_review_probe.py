#!/usr/bin/env python3
"""Review the shared 0x2700302b OP4 extended split residual plateau."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
from collections import Counter
from pathlib import Path


DEFAULT_OUTPUT = Path(
    "output/tex_large_shared_2700302b_op4_emitarg1_extended_split_residual_plateau_review_probe"
)
DEFAULT_RESIDUAL_SUMMARY = Path(
    "output/tex_large_shared_2700302b_op4_emitarg1_extended_split_residual_probe/summary.csv"
)
DEFAULT_RESIDUAL_CANDIDATES = Path(
    "output/tex_large_shared_2700302b_op4_emitarg1_extended_split_residual_probe/candidates.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "segment_rows",
    "base_action_id",
    "base_avg_score",
    "base_max_score",
    "residual_candidate_rows",
    "source_candidate_conditions",
    "reviewed_candidate_rows",
    "weak_residual_rows",
    "strong_residual_rows",
    "promotable_candidate_rows",
    "max_regression_rows",
    "nonpositive_max_delta_rows",
    "candidate_count_matches_summary",
    "best_condition_id",
    "best_action",
    "best_avg_score",
    "best_max_score",
    "best_delta_vs_base",
    "best_max_delta_vs_base",
    "second_delta_vs_base",
    "promote_delta_threshold",
    "top_condition_family",
    "top_condition_family_rows",
    "top_action_family",
    "top_action_family_rows",
    "source_issue_rows",
    "issue_rows",
    "plateau_verdict",
    "next_action",
]

DETAIL_FIELDNAMES = [
    "rank",
    "condition_id",
    "condition_family",
    "condition_count",
    "action",
    "action_family",
    "avg_score",
    "max_score",
    "delta_vs_base",
    "max_delta_vs_base",
    "total_guard_events",
    "total_action_emit_events",
    "segment_scores",
    "source_verdict",
    "review_class",
    "issues",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_summary(path: Path) -> dict[str, str]:
    rows = read_csv(path)
    return rows[0] if rows else {}


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    try:
        return os.path.relpath(Path(path_text), base_dir)
    except ValueError:
        return str(path_text)


def int_value(row: dict[str, str], field: str) -> int:
    raw = row.get(field, "")
    try:
        return int(raw, 0) if raw else 0
    except ValueError:
        return 0


def float_value(row: dict[str, str], field: str) -> float:
    raw = row.get(field, "")
    try:
        return float(raw) if raw else 0.0
    except ValueError:
        return 0.0


def hex_byte(text: str) -> bool:
    if len(text) != 2:
        return False
    try:
        value = int(text, 16)
    except ValueError:
        return False
    return 0 <= value <= 0xFF


def condition_family(condition_id: str) -> str:
    parts = condition_id.split("_")
    while parts and hex_byte(parts[-1]):
        parts.pop()
    return "_".join(parts) or condition_id


def action_family(action: str) -> str:
    if action.startswith("deny_"):
        return "deny"
    if action.startswith("emit_"):
        return "emit"
    return action or "none"


def review_class(row: dict[str, str], promote_delta_threshold: float) -> str:
    delta = float_value(row, "delta_vs_base")
    max_delta = float_value(row, "max_delta_vs_base")
    if delta <= -promote_delta_threshold and max_delta <= 0.0:
        return "promotable_global_rule"
    if delta < 0.0 and max_delta <= 0.0:
        return "weak_non_regressing_rule"
    if delta < 0.0:
        return "weak_mixed_rule"
    return "flat_or_regressing_rule"


def ranked_candidates(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    def rank_key(row: dict[str, str]) -> tuple[int, float, str, str]:
        rank = int_value(row, "rank")
        return (
            rank if rank else 999999,
            float_value(row, "avg_score"),
            row.get("condition_id", ""),
            row.get("action", ""),
        )

    return sorted(rows, key=rank_key)


def top_item(counter: Counter[str]) -> tuple[str, int]:
    if not counter:
        return "", 0
    item, count = counter.most_common(1)[0]
    return item, count


def build_review(
    residual_summary: dict[str, str],
    candidates: list[dict[str, str]],
    promote_delta_threshold: float,
) -> tuple[dict[str, str], list[dict[str, str]]]:
    ordered = ranked_candidates(candidates)
    detail_rows: list[dict[str, str]] = []
    condition_counter: Counter[str] = Counter()
    action_counter: Counter[str] = Counter()

    for row in ordered:
        family = condition_family(row.get("condition_id", ""))
        action_group = action_family(row.get("action", ""))
        klass = review_class(row, promote_delta_threshold)
        condition_counter[family] += 1
        action_counter[action_group] += 1
        issues: list[str] = []
        if float_value(row, "delta_vs_base") >= 0.0:
            issues.append("not_improved")
        detail_rows.append(
            {
                "rank": row.get("rank", ""),
                "condition_id": row.get("condition_id", ""),
                "condition_family": family,
                "condition_count": row.get("condition_count", ""),
                "action": row.get("action", ""),
                "action_family": action_group,
                "avg_score": row.get("avg_score", ""),
                "max_score": row.get("max_score", ""),
                "delta_vs_base": row.get("delta_vs_base", ""),
                "max_delta_vs_base": row.get("max_delta_vs_base", ""),
                "total_guard_events": row.get("total_guard_events", ""),
                "total_action_emit_events": row.get("total_action_emit_events", ""),
                "segment_scores": row.get("segment_scores", ""),
                "source_verdict": row.get("verdict", ""),
                "review_class": klass,
                "issues": "|".join(issues),
            }
        )

    best = ordered[0] if ordered else {}
    second = ordered[1] if len(ordered) > 1 else {}
    top_condition, top_condition_rows = top_item(condition_counter)
    top_action, top_action_rows = top_item(action_counter)

    source_candidate_rows = int_value(residual_summary, "candidate_rows")
    source_issue_rows = int_value(residual_summary, "issue_rows")
    candidate_count_matches = 1 if source_candidate_rows == len(ordered) else 0
    weak_rows = sum(1 for row in ordered if row.get("verdict") == "weak_residual_improvement")
    strong_rows = sum(1 for row in ordered if row.get("verdict") == "strong_residual_improvement")
    promotable_rows = sum(
        1 for row in detail_rows if row.get("review_class") == "promotable_global_rule"
    )
    max_regression_rows = sum(1 for row in ordered if float_value(row, "max_delta_vs_base") > 0.0)
    nonpositive_max_delta_rows = len(ordered) - max_regression_rows
    issue_rows = source_issue_rows + (0 if candidate_count_matches else 1)

    best_delta = float_value(best, "delta_vs_base")
    if source_issue_rows:
        verdict = "shared_2700302b_op4_extended_split_residual_plateau_review_issues"
        next_action = "fix shared 0x2700302b op4 residual plateau review inputs"
    elif not candidate_count_matches:
        verdict = "shared_2700302b_op4_extended_split_residual_plateau_review_stale"
        next_action = "rerun shared 0x2700302b op4 residual plateau review after residual probe"
    elif promotable_rows:
        verdict = "shared_2700302b_op4_extended_split_residual_global_rule_promotable"
        next_action = (
            "promote shared 0x2700302b op4 residual rule "
            f"{best.get('condition_id', '')}->{best.get('action', '')}; "
            f"avg delta {best_delta:.4f}"
        )
    elif ordered and best_delta < 0.0:
        verdict = "shared_2700302b_op4_extended_split_residual_plateau_confirmed"
        next_action = (
            "split shared 0x2700302b op4 residual by segment before narrow rules; "
            f"global residual tweaks plateau at {best_delta:.4f} avg"
        )
    else:
        verdict = "shared_2700302b_op4_extended_split_residual_no_actionable_candidates"
        next_action = "switch shared 0x2700302b op4 residual work to segment-specific grammar tracing"

    summary = {
        "scope": "total",
        "segment_rows": residual_summary.get("segment_rows", "0"),
        "base_action_id": residual_summary.get("base_action_id", ""),
        "base_avg_score": residual_summary.get("base_avg_score", ""),
        "base_max_score": residual_summary.get("base_max_score", ""),
        "residual_candidate_rows": str(source_candidate_rows),
        "source_candidate_conditions": residual_summary.get("source_candidate_conditions", ""),
        "reviewed_candidate_rows": str(len(ordered)),
        "weak_residual_rows": str(weak_rows),
        "strong_residual_rows": str(strong_rows),
        "promotable_candidate_rows": str(promotable_rows),
        "max_regression_rows": str(max_regression_rows),
        "nonpositive_max_delta_rows": str(nonpositive_max_delta_rows),
        "candidate_count_matches_summary": str(candidate_count_matches),
        "best_condition_id": best.get("condition_id", ""),
        "best_action": best.get("action", ""),
        "best_avg_score": best.get("avg_score", ""),
        "best_max_score": best.get("max_score", ""),
        "best_delta_vs_base": best.get("delta_vs_base", ""),
        "best_max_delta_vs_base": best.get("max_delta_vs_base", ""),
        "second_delta_vs_base": second.get("delta_vs_base", ""),
        "promote_delta_threshold": f"{promote_delta_threshold:.4f}",
        "top_condition_family": top_condition,
        "top_condition_family_rows": str(top_condition_rows),
        "top_action_family": top_action,
        "top_action_family_rows": str(top_action_rows),
        "source_issue_rows": str(source_issue_rows),
        "issue_rows": str(issue_rows),
        "plateau_verdict": verdict,
        "next_action": next_action,
    }
    return summary, detail_rows


def build_html(summary: dict[str, str], detail_rows: list[dict[str, str]], output_dir: Path, title: str) -> str:
    payload = {"summary": summary, "details": detail_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    rows = "\n".join(
        "<tr>"
        f"<td>{html.escape(row.get('rank', ''))}</td>"
        f"<td>{html.escape(row.get('condition_id', ''))}</td>"
        f"<td>{html.escape(row.get('condition_family', ''))}</td>"
        f"<td>{html.escape(row.get('action', ''))}</td>"
        f"<td>{html.escape(row.get('delta_vs_base', ''))}</td>"
        f"<td>{html.escape(row.get('max_delta_vs_base', ''))}</td>"
        f"<td>{html.escape(row.get('review_class', ''))}</td>"
        "</tr>"
        for row in detail_rows[:100]
    )
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (("summary", output_dir / "summary.csv"), ("details", output_dir / "details.csv"))
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body {{ margin: 24px; font-family: system-ui, sans-serif; background: #111; color: #eee; }}
a {{ color: #8ec5ff; margin-right: 12px; }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin: 18px 0; }}
.stat {{ background: #1d1d1d; border: 1px solid #333; padding: 12px; border-radius: 6px; }}
.label {{ color: #aaa; font-size: 12px; text-transform: uppercase; }}
.value {{ font-size: 20px; font-weight: 700; }}
table {{ border-collapse: collapse; width: 100%; background: #181818; }}
th, td {{ border-bottom: 1px solid #333; padding: 7px 9px; text-align: left; font-size: 13px; }}
th {{ color: #ccc; background: #222; }}
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<p>{links}</p>
<div class="stats">
  <div class="stat"><div class="label">Candidates</div><div class="value">{html.escape(summary['reviewed_candidate_rows'])}</div></div>
  <div class="stat"><div class="label">Best Delta</div><div class="value">{html.escape(summary['best_delta_vs_base'])}</div></div>
  <div class="stat"><div class="label">Promotable</div><div class="value">{html.escape(summary['promotable_candidate_rows'])}</div></div>
  <div class="stat"><div class="label">Verdict</div><div class="value">{html.escape(summary['plateau_verdict'])}</div></div>
</div>
<p>{html.escape(summary['next_action'])}</p>
<table>
<thead><tr><th>Rank</th><th>Condition</th><th>Family</th><th>Action</th><th>Delta</th><th>Max Delta</th><th>Class</th></tr></thead>
<tbody>{rows}</tbody>
</table>
<script type="application/json" id="data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> tuple[dict[str, str], list[dict[str, str]]]:
    args.output.mkdir(parents=True, exist_ok=True)
    residual_summary = read_summary(args.residual_summary)
    candidates = read_csv(args.residual_candidates)
    summary, detail_rows = build_review(residual_summary, candidates, args.promote_delta_threshold)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "details.csv", DETAIL_FIELDNAMES, detail_rows)
    (args.output / "index.html").write_text(
        build_html(summary, detail_rows, args.output, args.title),
        encoding="utf-8",
    )
    return summary, detail_rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Review shared 0x2700302b OP4 extended split residual plateau candidates."
    )
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--residual-summary", type=Path, default=DEFAULT_RESIDUAL_SUMMARY)
    parser.add_argument("--residual-candidates", type=Path, default=DEFAULT_RESIDUAL_CANDIDATES)
    parser.add_argument("--promote-delta-threshold", type=float, default=0.05)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Shared 0x2700302b OP4 Residual Plateau Review",
    )
    args = parser.parse_args()
    summary, _detail_rows = write_report(args)
    print(f"Segments: {summary['segment_rows']}")
    print(f"Reviewed candidates: {summary['reviewed_candidate_rows']}")
    print(f"Best candidate: {summary['best_condition_id']} -> {summary['best_action']}")
    print(f"Best delta vs base: {summary['best_delta_vs_base']}")
    print(f"Promotable candidates: {summary['promotable_candidate_rows']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"Plateau verdict: {summary['plateau_verdict']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
