#!/usr/bin/env python3
"""Replay selected per-segment shared 0x2700302b OP4 residual rules."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
from pathlib import Path

import lolg_tex_large_shared_2700302b_op4_emitarg1_extended_split_residual_probe as residual_probe
from score_te_raw_layouts import row_score


DEFAULT_OUTPUT = Path("output/tex_large_shared_2700302b_op4_emitarg1_extended_split_residual_segment_rule_replay_probe")
DEFAULT_ACTION_SUMMARY = residual_probe.DEFAULT_ACTION_SUMMARY
DEFAULT_RESIDUAL_SUMMARY = residual_probe.DEFAULT_OUTPUT / "summary.csv"
DEFAULT_SEGMENT_SPLIT_SUMMARY = Path(
    "output/tex_large_shared_2700302b_op4_emitarg1_extended_split_residual_segment_split_probe/summary.csv"
)
DEFAULT_SEGMENT_SPLIT_SEGMENTS = Path(
    "output/tex_large_shared_2700302b_op4_emitarg1_extended_split_residual_segment_split_probe/segments.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "segment_rows",
    "base_action_id",
    "base_avg_score",
    "base_max_score",
    "global_best_avg_score",
    "global_best_delta_vs_base",
    "selected_segment_rows",
    "replay_avg_score",
    "replay_max_score",
    "replay_delta_vs_base_avg",
    "replay_delta_vs_base_max",
    "replay_delta_vs_global_best_avg",
    "improved_segments",
    "degraded_segments",
    "unchanged_segments",
    "best_segment_id",
    "best_condition_id",
    "best_action",
    "best_delta_vs_base",
    "source_issue_rows",
    "issue_rows",
    "segment_rule_replay_verdict",
    "next_action",
]

SEGMENT_FIELDNAMES = [
    "segment_id",
    "width",
    "height",
    "selected_condition_id",
    "selected_action",
    "base_score",
    "replay_score",
    "delta_vs_base",
    "guard_events",
    "action_emit_events",
    "issue_rows",
    "segment_verdict",
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


def parse_condition_id(condition_id: str) -> tuple[object, ...] | None:
    parts = condition_id.split("_")
    try:
        if len(parts) == 2:
            return (parts[0], int(parts[1], 16))
        if len(parts) == 4:
            return (f"{parts[0]}_{parts[1]}", int(parts[2], 16), int(parts[3], 16))
    except ValueError:
        return None
    return None


def selected_rules(segment_rows: list[dict[str, str]]) -> dict[str, tuple[tuple[object, ...], str, str]]:
    rules: dict[str, tuple[tuple[object, ...], str, str]] = {}
    for row in segment_rows:
        if int_value(row, "strong_candidate_rows") <= 0:
            continue
        condition_id = row.get("best_condition_id", "")
        action = row.get("best_action", "")
        key = parse_condition_id(condition_id)
        if key and action:
            rules[row.get("segment_id", "")] = (key, action, condition_id)
    return rules


def build_report(args: argparse.Namespace) -> tuple[dict[str, str], list[dict[str, str]]]:
    action_summary = residual_probe.action_probe.read_summary(args.action_summary)
    residual_summary = read_summary(args.residual_summary)
    split_summary = read_summary(args.segment_split_summary)
    split_segments = read_csv(args.segment_split_segments)
    rules = selected_rules(split_segments)
    base_action_id = split_summary.get("base_action_id") or residual_summary.get("base_action_id")
    if not base_action_id:
        base_action_id = f"extended_split_greedy_{len(residual_probe.action_probe.EXTENDED_SPLIT_RULES)}"
    offset = residual_probe.action_probe.int_value(action_summary, "offset", 4)

    segment_rows: list[dict[str, str]] = []
    base_scores: list[float] = []
    replay_scores: list[float] = []
    source_issue_rows = int_value(residual_summary, "issue_rows") + int_value(split_summary, "issue_rows")

    for segment_id, payload, width, height, issues in residual_probe.load_segments(offset):
        issue_rows = len(issues)
        selected = rules.get(segment_id)
        selected_condition_id = selected[2] if selected else ""
        selected_action = selected[1] if selected else ""
        base_score = 0.0
        replay_score = 0.0
        stats = {"guard_events": 0, "action_emit_events": 0}
        if not issues:
            base_pixels, _base_stats = residual_probe.decode_residual(payload, width, height, base_action_id)
            base_score = row_score(base_pixels, width, height)
            base_scores.append(base_score)
            replay_pixels, stats = residual_probe.decode_residual(payload, width, height, base_action_id, selected)
            replay_score = row_score(replay_pixels, width, height)
            replay_scores.append(replay_score)
        delta = replay_score - base_score
        if issue_rows:
            verdict = "segment_rule_replay_issues"
        elif delta < -0.00005:
            verdict = "segment_rule_replay_improves"
        elif delta > 0.00005:
            verdict = "segment_rule_replay_regresses"
        else:
            verdict = "segment_rule_replay_unchanged"
        segment_rows.append(
            {
                "segment_id": segment_id,
                "width": str(width),
                "height": str(height),
                "selected_condition_id": selected_condition_id,
                "selected_action": selected_action,
                "base_score": f"{base_score:.4f}",
                "replay_score": f"{replay_score:.4f}",
                "delta_vs_base": f"{delta:.4f}",
                "guard_events": str(stats["guard_events"]),
                "action_emit_events": str(stats["action_emit_events"]),
                "issue_rows": str(issue_rows),
                "segment_verdict": verdict,
            }
        )

    base_avg = sum(base_scores) / max(1, len(base_scores))
    replay_avg = sum(replay_scores) / max(1, len(replay_scores))
    base_max = max(base_scores) if base_scores else 0.0
    replay_max = max(replay_scores) if replay_scores else 0.0
    replay_delta_avg = replay_avg - base_avg
    replay_delta_max = replay_max - base_max
    global_best_avg = float_value(residual_summary, "best_avg_score")
    replay_delta_global = replay_avg - global_best_avg
    improved_segments = sum(1 for row in segment_rows if row.get("segment_verdict") == "segment_rule_replay_improves")
    degraded_segments = sum(1 for row in segment_rows if row.get("segment_verdict") == "segment_rule_replay_regresses")
    unchanged_segments = sum(1 for row in segment_rows if row.get("segment_verdict") == "segment_rule_replay_unchanged")
    issue_rows = source_issue_rows + sum(int_value(row, "issue_rows") for row in segment_rows)
    selected_segment_rows = len(rules)
    best_segment = min(segment_rows, key=lambda row: float_value(row, "delta_vs_base"), default={})

    if issue_rows:
        verdict = "shared_2700302b_op4_segment_rule_replay_issues"
        next_action = "fix shared 0x2700302b op4 segment rule replay inputs"
    elif selected_segment_rows != len(segment_rows):
        verdict = "shared_2700302b_op4_segment_rule_replay_partial_selection"
        next_action = "derive missing shared 0x2700302b segment-specific op4 rule before replay promotion"
    elif degraded_segments:
        verdict = "shared_2700302b_op4_segment_rule_replay_regresses"
        next_action = "split shared 0x2700302b segment-specific op4 replay by narrower guard"
    elif replay_delta_avg <= -args.promote_delta_threshold and replay_delta_max <= 0.0:
        verdict = "shared_2700302b_op4_segment_rule_replay_improves"
        next_action = (
            "validate previews for shared 0x2700302b segment-specific op4 rules; "
            f"avg delta {replay_delta_avg:.4f} beats global residual by {replay_delta_global:.4f}"
        )
    else:
        verdict = "shared_2700302b_op4_segment_rule_replay_weak"
        next_action = "continue shared 0x2700302b segment-specific op4 guard search before promotion"

    summary = {
        "scope": "total",
        "segment_rows": str(len(segment_rows)),
        "base_action_id": base_action_id,
        "base_avg_score": f"{base_avg:.4f}",
        "base_max_score": f"{base_max:.4f}",
        "global_best_avg_score": residual_summary.get("best_avg_score", ""),
        "global_best_delta_vs_base": residual_summary.get("best_delta_vs_base", ""),
        "selected_segment_rows": str(selected_segment_rows),
        "replay_avg_score": f"{replay_avg:.4f}",
        "replay_max_score": f"{replay_max:.4f}",
        "replay_delta_vs_base_avg": f"{replay_delta_avg:.4f}",
        "replay_delta_vs_base_max": f"{replay_delta_max:.4f}",
        "replay_delta_vs_global_best_avg": f"{replay_delta_global:.4f}",
        "improved_segments": str(improved_segments),
        "degraded_segments": str(degraded_segments),
        "unchanged_segments": str(unchanged_segments),
        "best_segment_id": best_segment.get("segment_id", ""),
        "best_condition_id": best_segment.get("selected_condition_id", ""),
        "best_action": best_segment.get("selected_action", ""),
        "best_delta_vs_base": best_segment.get("delta_vs_base", ""),
        "source_issue_rows": str(source_issue_rows),
        "issue_rows": str(issue_rows),
        "segment_rule_replay_verdict": verdict,
        "next_action": next_action,
    }
    return summary, segment_rows


def build_html(summary: dict[str, str], segment_rows: list[dict[str, str]], output_dir: Path, title: str) -> str:
    payload = {"summary": summary, "segments": segment_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    rows = "\n".join(
        "<tr>"
        f"<td>{html.escape(row.get('segment_id', ''))}</td>"
        f"<td>{html.escape(row.get('selected_condition_id', ''))}</td>"
        f"<td>{html.escape(row.get('selected_action', ''))}</td>"
        f"<td>{html.escape(row.get('base_score', ''))}</td>"
        f"<td>{html.escape(row.get('replay_score', ''))}</td>"
        f"<td>{html.escape(row.get('delta_vs_base', ''))}</td>"
        f"<td>{html.escape(row.get('segment_verdict', ''))}</td>"
        "</tr>"
        for row in segment_rows
    )
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (("summary", output_dir / "summary.csv"), ("segments", output_dir / "segments.csv"))
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
  <div class="stat"><div class="label">Replay Avg</div><div class="value">{html.escape(summary['replay_avg_score'])}</div></div>
  <div class="stat"><div class="label">Avg Delta</div><div class="value">{html.escape(summary['replay_delta_vs_base_avg'])}</div></div>
  <div class="stat"><div class="label">Degraded</div><div class="value">{html.escape(summary['degraded_segments'])}</div></div>
  <div class="stat"><div class="label">Verdict</div><div class="value">{html.escape(summary['segment_rule_replay_verdict'])}</div></div>
</div>
<p>{html.escape(summary['next_action'])}</p>
<table>
<thead><tr><th>Segment</th><th>Condition</th><th>Action</th><th>Base</th><th>Replay</th><th>Delta</th><th>Verdict</th></tr></thead>
<tbody>{rows}</tbody>
</table>
<script type="application/json" id="data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> tuple[dict[str, str], list[dict[str, str]]]:
    args.output.mkdir(parents=True, exist_ok=True)
    summary, segment_rows = build_report(args)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "segments.csv", SEGMENT_FIELDNAMES, segment_rows)
    (args.output / "index.html").write_text(
        build_html(summary, segment_rows, args.output, args.title),
        encoding="utf-8",
    )
    return summary, segment_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay selected shared 0x2700302b OP4 segment-specific rules.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--action-summary", type=Path, default=DEFAULT_ACTION_SUMMARY)
    parser.add_argument("--residual-summary", type=Path, default=DEFAULT_RESIDUAL_SUMMARY)
    parser.add_argument("--segment-split-summary", type=Path, default=DEFAULT_SEGMENT_SPLIT_SUMMARY)
    parser.add_argument("--segment-split-segments", type=Path, default=DEFAULT_SEGMENT_SPLIT_SEGMENTS)
    parser.add_argument("--promote-delta-threshold", type=float, default=0.05)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Shared 0x2700302b OP4 Segment Rule Replay Probe",
    )
    args = parser.parse_args()
    summary, _segment_rows = write_report(args)
    print(f"Segments: {summary['segment_rows']}")
    print(f"Selected segments: {summary['selected_segment_rows']}")
    print(f"Replay avg score: {summary['replay_avg_score']}")
    print(f"Replay delta vs base avg: {summary['replay_delta_vs_base_avg']}")
    print(f"Replay delta vs global best avg: {summary['replay_delta_vs_global_best_avg']}")
    print(f"Degraded segments: {summary['degraded_segments']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"Segment rule replay verdict: {summary['segment_rule_replay_verdict']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
