#!/usr/bin/env python3
"""Split shared 0x2700302b OP4 residual candidates by segment."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
from pathlib import Path

import lolg_tex_large_shared_2700302b_op4_emitarg1_extended_split_residual_probe as residual_probe
from score_te_raw_layouts import row_score


DEFAULT_OUTPUT = Path("output/tex_large_shared_2700302b_op4_emitarg1_extended_split_residual_segment_split_probe")
DEFAULT_ACTION_SUMMARY = residual_probe.DEFAULT_ACTION_SUMMARY
DEFAULT_RESIDUAL_SUMMARY = residual_probe.DEFAULT_OUTPUT / "summary.csv"
DEFAULT_PLATEAU_SUMMARY = Path(
    "output/tex_large_shared_2700302b_op4_emitarg1_extended_split_residual_plateau_review_probe/summary.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "segment_rows",
    "base_action_id",
    "base_avg_score",
    "base_max_score",
    "residual_plateau_verdict",
    "candidate_limit",
    "min_count",
    "segment_candidate_rows",
    "strong_segment_candidate_rows",
    "segments_with_candidates",
    "segments_with_strong_candidates",
    "segments_with_issues",
    "best_segment_id",
    "best_condition_id",
    "best_action",
    "best_score",
    "best_delta_vs_base",
    "worst_best_delta_vs_base",
    "source_issue_rows",
    "issue_rows",
    "segment_split_verdict",
    "next_action",
]

SEGMENT_FIELDNAMES = [
    "segment_id",
    "width",
    "height",
    "base_score",
    "candidate_conditions",
    "candidate_rows",
    "strong_candidate_rows",
    "best_condition_id",
    "best_action",
    "best_score",
    "best_delta_vs_base",
    "best_total_guard_events",
    "best_total_action_emit_events",
    "issue_rows",
    "segment_verdict",
    "next_action",
]

CANDIDATE_FIELDNAMES = [
    "segment_id",
    "segment_rank",
    "condition_id",
    "condition_count",
    "action",
    "score",
    "delta_vs_base",
    "total_guard_events",
    "total_action_emit_events",
    "source_verdict",
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


def strong_candidate(row: dict[str, str], threshold: float) -> bool:
    return float_value(row, "delta_vs_base") <= -threshold and float_value(row, "max_delta_vs_base") <= 0.0


def segment_next_action(segment_id: str, best: dict[str, str], strong_rows: int) -> str:
    if not best:
        return f"trace shared 0x2700302b op4 segment grammar for {segment_id}; no local residual candidate improved"
    if strong_rows:
        return (
            f"review segment-specific shared 0x2700302b op4 rule for {segment_id}; "
            f"best {best.get('condition_id', '')}->{best.get('action', '')} "
            f"delta {best.get('delta_vs_base', '')}"
        )
    return (
        f"trace shared 0x2700302b op4 segment grammar for {segment_id}; "
        f"only weak local candidate {best.get('condition_id', '')}->{best.get('action', '')} "
        f"delta {best.get('delta_vs_base', '')}"
    )


def build_report(args: argparse.Namespace) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    action_summary = residual_probe.action_probe.read_summary(args.action_summary)
    residual_summary = read_summary(args.residual_summary)
    plateau_summary = read_summary(args.plateau_summary)
    base_action_id = residual_summary.get("base_action_id") or action_summary.get("best_condition_id")
    if not base_action_id:
        base_action_id = f"extended_split_greedy_{len(residual_probe.action_probe.EXTENDED_SPLIT_RULES)}"
    offset = residual_probe.action_probe.int_value(action_summary, "offset", 4)
    segments = residual_probe.load_segments(offset)

    segment_rows: list[dict[str, str]] = []
    candidate_rows: list[dict[str, str]] = []
    base_scores: list[float] = []
    source_issue_rows = int_value(residual_summary, "issue_rows") + int_value(plateau_summary, "issue_rows")

    for segment_id, payload, width, height, issues in segments:
        issue_rows = len(issues)
        base_score = 0.0
        conditions: list[tuple[tuple[object, ...], int]] = []
        candidates: list[dict[str, str]] = []
        if not issues:
            pixels, _stats = residual_probe.decode_residual(payload, width, height, base_action_id)
            base_score = row_score(pixels, width, height)
            base_scores.append(base_score)
            conditions = residual_probe.collect_candidate_conditions([(
                segment_id,
                payload,
                width,
                height,
                issues,
            )], base_action_id, args.min_count, args.candidate_limit)
            candidates = residual_probe.candidate_rows([(
                segment_id,
                payload,
                width,
                height,
                issues,
            )], base_action_id, base_score, base_score, conditions)

        strong_rows = sum(1 for row in candidates if strong_candidate(row, args.promote_delta_threshold))
        best = candidates[0] if candidates else {}
        if issue_rows:
            verdict = "shared_2700302b_op4_segment_split_issues"
            next_action = f"fix shared 0x2700302b op4 segment input for {segment_id}"
        elif strong_rows:
            verdict = "shared_2700302b_op4_segment_specific_candidates_ready"
            next_action = segment_next_action(segment_id, best, strong_rows)
        elif candidates:
            verdict = "shared_2700302b_op4_segment_specific_candidates_weak"
            next_action = segment_next_action(segment_id, best, strong_rows)
        else:
            verdict = "shared_2700302b_op4_segment_specific_no_candidates"
            next_action = segment_next_action(segment_id, best, strong_rows)

        segment_rows.append(
            {
                "segment_id": segment_id,
                "width": str(width),
                "height": str(height),
                "base_score": f"{base_score:.4f}",
                "candidate_conditions": str(len(conditions)),
                "candidate_rows": str(len(candidates)),
                "strong_candidate_rows": str(strong_rows),
                "best_condition_id": best.get("condition_id", ""),
                "best_action": best.get("action", ""),
                "best_score": best.get("avg_score", ""),
                "best_delta_vs_base": best.get("delta_vs_base", ""),
                "best_total_guard_events": best.get("total_guard_events", ""),
                "best_total_action_emit_events": best.get("total_action_emit_events", ""),
                "issue_rows": str(issue_rows),
                "segment_verdict": verdict,
                "next_action": next_action,
            }
        )
        for row in candidates:
            candidate_rows.append(
                {
                    "segment_id": segment_id,
                    "segment_rank": row.get("rank", ""),
                    "condition_id": row.get("condition_id", ""),
                    "condition_count": row.get("condition_count", ""),
                    "action": row.get("action", ""),
                    "score": row.get("avg_score", ""),
                    "delta_vs_base": row.get("delta_vs_base", ""),
                    "total_guard_events": row.get("total_guard_events", ""),
                    "total_action_emit_events": row.get("total_action_emit_events", ""),
                    "source_verdict": row.get("verdict", ""),
                }
            )

    valid_segment_rows = [row for row in segment_rows if int_value(row, "issue_rows") == 0]
    best_segments = [
        row for row in valid_segment_rows if row.get("best_delta_vs_base")
    ]
    best_segments.sort(key=lambda row: float_value(row, "best_delta_vs_base"))
    best_segment = best_segments[0] if best_segments else {}
    worst_best_delta = max((float_value(row, "best_delta_vs_base") for row in best_segments), default=0.0)
    segment_candidate_rows = sum(int_value(row, "candidate_rows") for row in segment_rows)
    strong_segment_candidate_rows = sum(int_value(row, "strong_candidate_rows") for row in segment_rows)
    segments_with_candidates = sum(1 for row in segment_rows if int_value(row, "candidate_rows") > 0)
    segments_with_strong = sum(1 for row in segment_rows if int_value(row, "strong_candidate_rows") > 0)
    segments_with_issues = sum(1 for row in segment_rows if int_value(row, "issue_rows") > 0)
    issue_rows = source_issue_rows + segments_with_issues

    if issue_rows:
        verdict = "shared_2700302b_op4_segment_split_probe_issues"
        next_action = "fix shared 0x2700302b op4 segment split probe inputs"
    elif segments_with_strong:
        verdict = "shared_2700302b_op4_segment_split_candidates_ready"
        next_action = (
            f"review segment-specific shared 0x2700302b op4 rule for {best_segment.get('segment_id', '')}; "
            f"best {best_segment.get('best_condition_id', '')}->{best_segment.get('best_action', '')} "
            f"delta {best_segment.get('best_delta_vs_base', '')}"
        )
    elif segment_candidate_rows:
        verdict = "shared_2700302b_op4_segment_split_candidates_weak"
        next_action = (
            "trace shared 0x2700302b op4 segment-specific grammar; "
            f"best weak candidate {best_segment.get('best_condition_id', '')}->{best_segment.get('best_action', '')} "
            f"delta {best_segment.get('best_delta_vs_base', '')}"
        )
    else:
        verdict = "shared_2700302b_op4_segment_split_no_candidates"
        next_action = "switch shared 0x2700302b op4 residual work to non-op4 segment grammar tracing"

    summary = {
        "scope": "total",
        "segment_rows": str(len(segments)),
        "base_action_id": base_action_id,
        "base_avg_score": f"{(sum(base_scores) / max(1, len(base_scores))):.4f}",
        "base_max_score": f"{(max(base_scores) if base_scores else 0.0):.4f}",
        "residual_plateau_verdict": plateau_summary.get("plateau_verdict", ""),
        "candidate_limit": str(args.candidate_limit),
        "min_count": str(args.min_count),
        "segment_candidate_rows": str(segment_candidate_rows),
        "strong_segment_candidate_rows": str(strong_segment_candidate_rows),
        "segments_with_candidates": str(segments_with_candidates),
        "segments_with_strong_candidates": str(segments_with_strong),
        "segments_with_issues": str(segments_with_issues),
        "best_segment_id": best_segment.get("segment_id", ""),
        "best_condition_id": best_segment.get("best_condition_id", ""),
        "best_action": best_segment.get("best_action", ""),
        "best_score": best_segment.get("best_score", ""),
        "best_delta_vs_base": best_segment.get("best_delta_vs_base", ""),
        "worst_best_delta_vs_base": f"{worst_best_delta:.4f}",
        "source_issue_rows": str(source_issue_rows),
        "issue_rows": str(issue_rows),
        "segment_split_verdict": verdict,
        "next_action": next_action,
    }
    return summary, segment_rows, candidate_rows


def build_html(
    summary: dict[str, str],
    segment_rows: list[dict[str, str]],
    candidate_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "segments": segment_rows, "candidates": candidate_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    rows = "\n".join(
        "<tr>"
        f"<td>{html.escape(row.get('segment_id', ''))}</td>"
        f"<td>{html.escape(row.get('base_score', ''))}</td>"
        f"<td>{html.escape(row.get('candidate_rows', ''))}</td>"
        f"<td>{html.escape(row.get('strong_candidate_rows', ''))}</td>"
        f"<td>{html.escape(row.get('best_condition_id', ''))}</td>"
        f"<td>{html.escape(row.get('best_action', ''))}</td>"
        f"<td>{html.escape(row.get('best_delta_vs_base', ''))}</td>"
        f"<td>{html.escape(row.get('segment_verdict', ''))}</td>"
        "</tr>"
        for row in segment_rows
    )
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary", output_dir / "summary.csv"),
            ("segments", output_dir / "segments.csv"),
            ("candidates", output_dir / "candidates.csv"),
        )
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
  <div class="stat"><div class="label">Segments</div><div class="value">{html.escape(summary['segment_rows'])}</div></div>
  <div class="stat"><div class="label">Strong Rows</div><div class="value">{html.escape(summary['strong_segment_candidate_rows'])}</div></div>
  <div class="stat"><div class="label">Best Delta</div><div class="value">{html.escape(summary['best_delta_vs_base'])}</div></div>
  <div class="stat"><div class="label">Verdict</div><div class="value">{html.escape(summary['segment_split_verdict'])}</div></div>
</div>
<p>{html.escape(summary['next_action'])}</p>
<table>
<thead><tr><th>Segment</th><th>Base</th><th>Candidates</th><th>Strong</th><th>Condition</th><th>Action</th><th>Delta</th><th>Verdict</th></tr></thead>
<tbody>{rows}</tbody>
</table>
<script type="application/json" id="data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    args.output.mkdir(parents=True, exist_ok=True)
    summary, segment_rows, candidate_rows = build_report(args)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "segments.csv", SEGMENT_FIELDNAMES, segment_rows)
    write_csv(args.output / "candidates.csv", CANDIDATE_FIELDNAMES, candidate_rows)
    (args.output / "index.html").write_text(
        build_html(summary, segment_rows, candidate_rows, args.output, args.title),
        encoding="utf-8",
    )
    return summary, segment_rows, candidate_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Split shared 0x2700302b OP4 residual candidates by segment.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--action-summary", type=Path, default=DEFAULT_ACTION_SUMMARY)
    parser.add_argument("--residual-summary", type=Path, default=DEFAULT_RESIDUAL_SUMMARY)
    parser.add_argument("--plateau-summary", type=Path, default=DEFAULT_PLATEAU_SUMMARY)
    parser.add_argument("--candidate-limit", type=int, default=80)
    parser.add_argument("--min-count", type=int, default=3)
    parser.add_argument("--promote-delta-threshold", type=float, default=0.05)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Shared 0x2700302b OP4 Residual Segment Split Probe",
    )
    args = parser.parse_args()
    summary, _segment_rows, _candidate_rows = write_report(args)
    print(f"Segments: {summary['segment_rows']}")
    print(f"Segment candidate rows: {summary['segment_candidate_rows']}")
    print(f"Strong segment candidate rows: {summary['strong_segment_candidate_rows']}")
    print(f"Best segment: {summary['best_segment_id']}")
    print(f"Best candidate: {summary['best_condition_id']} -> {summary['best_action']}")
    print(f"Best delta vs base: {summary['best_delta_vs_base']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"Segment split verdict: {summary['segment_split_verdict']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
