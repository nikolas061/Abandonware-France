#!/usr/bin/env python3
"""Sweep LLSE 2730 marker guard replay impact across actions and heights."""

from __future__ import annotations

import argparse
import html
import json
from collections import defaultdict
from pathlib import Path

from lolg_tex_large_body_control_grammar_probe import int_value, write_csv
from lolg_tex_large_llse_higharg2_refinement_probe import float_text, relative_href
from lolg_tex_large_llse_marker_field_semantics_probe import (
    DEFAULT_FIELD_PROFILE_SUMMARY,
    DEFAULT_PAIR_LENGTH_SUMMARY,
    build_variants,
    evaluate_variant,
    load_body,
    read_csv,
    read_summary,
)
from lolg_tex_large_llse_marker_guard_replay_impact_probe import (
    DEFAULT_FIELD_SEMANTICS_SUMMARY,
    DEFAULT_FIELD_STATE_SUMMARY,
    parse_heights,
    row_from_evaluation,
)
from lolg_tex_large_llse_marker_semantics_probe import (
    DEFAULT_HIGHARG2_SUMMARY,
    DEFAULT_MIX_ENTRY_INDEX,
    DEFAULT_SEGMENTS,
    TARGET_CONTROL_PATH,
)


DEFAULT_OUTPUT = Path("output/tex_large_llse_marker_guard_replay_sweep_probe")
DEFAULT_ACTIONS = [
    "setxy_f1div4_f0_if_f1mod4_f0ge40",
    "setxy_f1div4_f0_if_f1mod4_f0ge40_ylt128",
    "setxy_f1div4_f0_if_f1mod4_f0ge40_ylt256",
    "setxy_f1div4_f0_if_f1mod4_f0ge40_ylt320",
    "setxy_f1div4_f0_if_f1mod4_f0ge40_ylt384",
    "setxy_f1div4_f0_if_f1mod4_f0ge40_ylt448",
    "setxy_f1div4_f0_if_f1mod4_f0ge40_ylt512",
    "setxy_f1div4_f0_if_f1mod4_f0ge40_f0ltf0_ylt512",
    "setxy_f1div4_f0_if_f1mod4_f0ge40_f2ge10_ylt512",
    "setxy_f1div4_f0_if_f1mod4_f0ge40_f2ge10_f0ltf0_ylt512",
    "setxy_f1div4_f0_if_f1mod4_f0ge40_f0ltf0_f2ge40_f3ge30_ylt512",
    "setxy_f1div4_f0_if_f1mod4_f0ge40_f0ltf0_f4ge80_ylt512",
    "setxy_f1div4_f0_if_f1mod4_f0gec0_f0ltf0_ylt512",
    "setxy_f1div4_f0_if_f1mod4_f0ge60",
    "setxy_f1div4_f0_if_f1mod4_f0ge80",
    "setxy_f1div4_f0_if_f1mod4_yforward_f0ge40",
    "setxy_f1div4_f0_if_f1mod4_yforward_f0ge80",
]

SUMMARY_FIELDNAMES = [
    "scope",
    "segment_rows",
    "action_rows",
    "height_rows",
    "height_list",
    "best_action",
    "best_verdict",
    "best_positive_height_rows",
    "best_max_positive_delta",
    "best_max_delta",
    "best_min_delta",
    "best_mean_delta",
    "best_512_delta",
    "best_1024_delta",
    "best_2048_delta",
    "issue_rows",
    "sweep_verdict",
    "next_action",
]

ACTION_FIELDNAMES = [
    "rank",
    "action",
    "variant_id",
    "height_rows",
    "positive_height_rows",
    "nonpositive_height_rows",
    "max_positive_delta",
    "max_delta",
    "min_delta",
    "mean_delta",
    "sum_delta",
    "score_512_delta",
    "score_768_delta",
    "score_1024_delta",
    "score_1536_delta",
    "score_2048_delta",
    "actions_512",
    "actions_768",
    "actions_1024",
    "actions_1536",
    "actions_2048",
    "height_deltas",
    "height_actions",
    "max_diff_ratio",
    "issue_rows",
    "action_verdict",
]

ROW_FIELDNAMES = [
    "rank",
    "segment_id",
    "height",
    "action",
    "variant_id",
    "score",
    "delta_vs_height_baseline",
    "visible_pixels",
    "filled_ratio",
    "unique_colors",
    "emitted",
    "final_x",
    "final_y",
    "target_seen",
    "actions_applied",
    "cmd20_higharg2_applied",
    "marker_pair_seen",
    "diff_pixels",
    "diff_ratio",
    "issues",
]


def parse_actions(value: str) -> list[str]:
    actions = [item.strip() for item in value.split(",") if item.strip()]
    return actions or list(DEFAULT_ACTIONS)


def source_with_resolved_archive(source: dict[str, str]) -> dict[str, str]:
    archive = Path(source.get("archive", ""))
    candidates = [
        archive,
        Path(archive.name),
        Path("C") / archive.name,
        Path("C") / "LOLG" / archive.name,
    ]
    resolved = next((candidate for candidate in candidates if candidate.exists()), archive)
    if resolved == archive:
        return source
    updated = dict(source)
    updated["archive"] = resolved.as_posix()
    return updated


def fmt(value: float) -> str:
    return f"{value:.4f}"


def action_rows(rows: list[dict[str, str]], heights: list[int]) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row.get("action") != "baseline":
            grouped[row.get("action", "")].append(row)
    output_rows: list[dict[str, str]] = []
    for action, action_group in grouped.items():
        clean_rows = [row for row in action_group if not row.get("issues")]
        deltas = [float_text(row.get("delta_vs_height_baseline")) for row in clean_rows]
        positive_rows = [delta for delta in deltas if delta > 0]
        delta_by_height = {int_value(row, "height"): float_text(row.get("delta_vs_height_baseline")) for row in clean_rows}
        actions_by_height = {int_value(row, "height"): row.get("actions_applied", "") for row in clean_rows}
        max_diff_ratio = max((float_text(row.get("diff_ratio")) for row in clean_rows), default=0.0)
        issue_rows = sum(1 for row in action_group if row.get("issues"))
        if issue_rows:
            verdict = "llse_marker_guard_sweep_action_issues"
        elif deltas and not positive_rows:
            verdict = "llse_marker_guard_sweep_action_stable"
        elif deltas:
            verdict = "llse_marker_guard_sweep_action_mixed"
        else:
            verdict = "llse_marker_guard_sweep_action_no_rows"
        output_rows.append(
            {
                "rank": "",
                "action": action,
                "variant_id": clean_rows[0].get("variant_id", "") if clean_rows else "",
                "height_rows": str(len(clean_rows)),
                "positive_height_rows": str(len(positive_rows)),
                "nonpositive_height_rows": str(len(deltas) - len(positive_rows)),
                "max_positive_delta": fmt(max(positive_rows, default=0.0)),
                "max_delta": fmt(max(deltas, default=0.0)),
                "min_delta": fmt(min(deltas, default=0.0)),
                "mean_delta": fmt(sum(deltas) / max(1, len(deltas))),
                "sum_delta": fmt(sum(deltas)),
                "score_512_delta": fmt(delta_by_height[512]) if 512 in delta_by_height else "",
                "score_768_delta": fmt(delta_by_height[768]) if 768 in delta_by_height else "",
                "score_1024_delta": fmt(delta_by_height[1024]) if 1024 in delta_by_height else "",
                "score_1536_delta": fmt(delta_by_height[1536]) if 1536 in delta_by_height else "",
                "score_2048_delta": fmt(delta_by_height[2048]) if 2048 in delta_by_height else "",
                "actions_512": actions_by_height.get(512, ""),
                "actions_768": actions_by_height.get(768, ""),
                "actions_1024": actions_by_height.get(1024, ""),
                "actions_1536": actions_by_height.get(1536, ""),
                "actions_2048": actions_by_height.get(2048, ""),
                "height_deltas": "|".join(f"{height}:{fmt(delta_by_height[height])}" for height in heights if height in delta_by_height),
                "height_actions": "|".join(
                    f"{height}:{actions_by_height[height]}" for height in heights if height in actions_by_height
                ),
                "max_diff_ratio": f"{max_diff_ratio:.6f}",
                "issue_rows": str(issue_rows),
                "action_verdict": verdict,
            }
        )
    output_rows.sort(
        key=lambda row: (
            int_value(row, "issue_rows") > 0,
            int_value(row, "positive_height_rows"),
            float_text(row.get("max_positive_delta")),
            float_text(row.get("mean_delta")),
            float_text(row.get("max_delta")),
            row.get("action", ""),
        )
    )
    for rank, row in enumerate(output_rows, 1):
        row["rank"] = str(rank)
    return output_rows


def summary_row(action_summary_rows: list[dict[str, str]], rows: list[dict[str, str]], heights: list[int]) -> dict[str, str]:
    issue_rows = sum(1 for row in rows if row.get("issues"))
    best = action_summary_rows[0] if action_summary_rows else {}
    if issue_rows:
        verdict = "llse_marker_guard_replay_sweep_issues"
        next_action = "fix LLSE marker guard replay sweep inputs"
    elif best and best.get("action_verdict") == "llse_marker_guard_sweep_action_stable":
        verdict = "llse_marker_guard_replay_sweep_stable_candidate"
        next_action = f"inspect stable LLSE marker guard replay visuals before decoder promotion; candidate {best.get('action', '')}"
    elif best:
        verdict = "llse_marker_guard_replay_sweep_mixed_candidates"
        next_action = (
            "isolate residual positive-height LLSE guard triggers before decoder promotion; "
            f"best candidate {best.get('action', '')} max_positive_delta {best.get('max_positive_delta', '')}"
        )
    else:
        verdict = "llse_marker_guard_replay_sweep_no_candidates"
        next_action = "review LLSE marker guard replay sweep candidate list"
    return {
        "scope": "total",
        "segment_rows": str(len({row.get("segment_id", "") for row in rows if row.get("segment_id")})),
        "action_rows": str(len(action_summary_rows)),
        "height_rows": str(len(heights)),
        "height_list": "|".join(str(height) for height in heights),
        "best_action": best.get("action", ""),
        "best_verdict": best.get("action_verdict", ""),
        "best_positive_height_rows": best.get("positive_height_rows", ""),
        "best_max_positive_delta": best.get("max_positive_delta", ""),
        "best_max_delta": best.get("max_delta", ""),
        "best_min_delta": best.get("min_delta", ""),
        "best_mean_delta": best.get("mean_delta", ""),
        "best_512_delta": best.get("score_512_delta", ""),
        "best_1024_delta": best.get("score_1024_delta", ""),
        "best_2048_delta": best.get("score_2048_delta", ""),
        "issue_rows": str(issue_rows),
        "sweep_verdict": verdict,
        "next_action": next_action,
    }


def render_table(rows: list[dict[str, str]], fieldnames: list[str]) -> str:
    if not rows:
        return "<p class=\"muted\">No rows.</p>"
    head = "".join(f"<th>{html.escape(field)}</th>" for field in fieldnames)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fieldnames) + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    action_summary_rows: list[dict[str, str]],
    rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "actions": action_summary_rows, "rows": rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f"<a href=\"{html.escape(relative_href(path, output_dir))}\">{html.escape(label)}</a>"
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("actions.csv", output_dir / "actions.csv"),
            ("rows.csv", output_dir / "rows.csv"),
        )
    )
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
:root {{ color-scheme: dark; --bg: #101317; --panel: #181d23; --text: #e8edf2; --muted: #98a4b3; --accent: #74b8ff; --ok: #6fd08c; --warn: #f0b35a; }}
body {{ margin: 0; font-family: system-ui, sans-serif; background: var(--bg); color: var(--text); }}
header, main {{ max-width: 1450px; margin: 0 auto; padding: 24px; }}
h1 {{ margin: 0 0 8px; font-size: 26px; }}
h2 {{ margin: 0 0 12px; font-size: 18px; }}
.muted {{ color: var(--muted); }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin: 20px 0; }}
.stat, .panel {{ background: var(--panel); border: 1px solid #29313b; border-radius: 8px; padding: 14px; }}
.label {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }}
.value {{ font-size: 24px; font-weight: 700; }}
.ok {{ color: var(--ok); }}
.warn {{ color: var(--warn); }}
a {{ color: var(--accent); text-decoration: none; margin-right: 10px; }}
table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
th, td {{ border-bottom: 1px solid #29313b; padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); position: sticky; top: 0; background: var(--panel); }}
td {{ max-width: 560px; overflow-wrap: anywhere; }}
section {{ margin-bottom: 20px; }}
</style>
</head>
<body>
<header>
  <h1>{html.escape(title)}</h1>
  <div class="muted">Replay sweep for LLSE 2730 marker guard candidates across heights.</div>
  <p>{links}</p>
</header>
<main>
  <section class="grid">
    <div class="stat"><div class="label">Best Action</div><div class="value">{html.escape(summary['best_action'])}</div></div>
    <div class="stat"><div class="label">Positive Heights</div><div class="value warn">{html.escape(summary['best_positive_height_rows'])}</div></div>
    <div class="stat"><div class="label">Max Positive Delta</div><div class="value warn">{html.escape(summary['best_max_positive_delta'])}</div></div>
    <div class="stat"><div class="label">Issues</div><div class="value ok">{html.escape(summary['issue_rows'])}</div></div>
  </section>
  <section class="panel"><h2>Summary</h2>{render_table([summary], SUMMARY_FIELDNAMES)}</section>
  <section class="panel"><h2>Actions</h2>{render_table(action_summary_rows, ACTION_FIELDNAMES)}</section>
  <section class="panel"><h2>Rows</h2>{render_table(rows, ROW_FIELDNAMES)}</section>
</main>
<script type="application/json" id="llse-marker-guard-sweep-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    args.output.mkdir(parents=True, exist_ok=True)
    higharg2_summary = read_summary(args.higharg2_summary)
    pair_summary = read_summary(args.pair_length_summary)
    field_summary = read_summary(args.field_profile_summary)
    variants = build_variants(higharg2_summary, pair_summary, field_summary)
    variant_by_action = {variant.action: variant for variant in variants}
    baseline_variant = variant_by_action.get("baseline", variants[0])
    segment_rows = [row for row in read_csv(args.segments) if row.get("control_path") == TARGET_CONTROL_PATH]
    payload_cache: dict[Path, bytes] = {}
    rows: list[dict[str, str]] = []
    for raw_source in segment_rows:
        source = source_with_resolved_archive(raw_source)
        body, issues = load_body(source, payload_cache, args.mix_entry_index)
        for height in args.heights:
            baseline_row, baseline_pixels = evaluate_variant(
                source, body, issues, baseline_variant, args.width, height, args.low, args.high, 0.0
            )
            baseline_row["height"] = str(height)
            baseline_score = float_text(baseline_row.get("score"))
            rows.append(row_from_evaluation(baseline_row, baseline_pixels, baseline_score, baseline_pixels))
            for action in args.actions:
                variant = variant_by_action.get(action)
                if variant is None:
                    rows.append(
                        {
                            "rank": "",
                            "segment_id": source.get("segment_id", ""),
                            "height": str(height),
                            "action": action,
                            "variant_id": "",
                            "score": "",
                            "delta_vs_height_baseline": "",
                            "visible_pixels": "",
                            "filled_ratio": "",
                            "unique_colors": "",
                            "emitted": "",
                            "final_x": "",
                            "final_y": "",
                            "target_seen": "",
                            "actions_applied": "",
                            "cmd20_higharg2_applied": "",
                            "marker_pair_seen": "",
                            "diff_pixels": "",
                            "diff_ratio": "",
                            "issues": "unknown_action",
                        }
                    )
                    continue
                candidate_row, candidate_pixels = evaluate_variant(
                    source, body, issues, variant, args.width, height, args.low, args.high, baseline_score
                )
                candidate_row["height"] = str(height)
                rows.append(row_from_evaluation(candidate_row, candidate_pixels, baseline_score, baseline_pixels))
    for rank, row in enumerate(rows, 1):
        row["rank"] = str(rank)
    actions = action_rows(rows, args.heights)
    summary = summary_row(actions, rows, args.heights)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "actions.csv", ACTION_FIELDNAMES, actions)
    write_csv(args.output / "rows.csv", ROW_FIELDNAMES, rows)
    (args.output / "index.html").write_text(build_html(summary, actions, rows, args.output, args.title), encoding="utf-8")
    return summary, actions, rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Sweep LLSE 2730 marker guard replay impact.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--segments", type=Path, default=DEFAULT_SEGMENTS)
    parser.add_argument("--higharg2-summary", type=Path, default=DEFAULT_HIGHARG2_SUMMARY)
    parser.add_argument("--pair-length-summary", type=Path, default=DEFAULT_PAIR_LENGTH_SUMMARY)
    parser.add_argument("--field-profile-summary", type=Path, default=DEFAULT_FIELD_PROFILE_SUMMARY)
    parser.add_argument("--field-semantics-summary", type=Path, default=DEFAULT_FIELD_SEMANTICS_SUMMARY)
    parser.add_argument("--field-state-summary", type=Path, default=DEFAULT_FIELD_STATE_SUMMARY)
    parser.add_argument("--mix-entry-index", type=int, default=DEFAULT_MIX_ENTRY_INDEX)
    parser.add_argument("--width", type=int, default=64)
    parser.add_argument("--heights", type=parse_heights, default=parse_heights("512,768,1024,1536,2048"))
    parser.add_argument("--actions", type=parse_actions, default=list(DEFAULT_ACTIONS))
    parser.add_argument("--low", type=lambda value: int(value, 0), default=0x30)
    parser.add_argument("--high", type=lambda value: int(value, 0), default=0xBF)
    parser.add_argument("--title", default="Lands of Lore II .tex LLSE Marker Guard Replay Sweep")
    args = parser.parse_args()

    summary, actions, _rows = write_report(args)
    print(f"Segments: {summary['segment_rows']}")
    print(f"Actions: {summary['action_rows']}")
    print(f"Heights: {summary['height_list']}")
    print(f"Best action: {summary['best_action']}")
    print(f"Best max positive delta: {summary['best_max_positive_delta']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"Sweep verdict: {summary['sweep_verdict']}")
    print(f"Next action: {summary['next_action']}")
    if actions:
        print(
            "Top row: "
            f"{actions[0]['action']} positives {actions[0]['positive_height_rows']} "
            f"max_positive {actions[0]['max_positive_delta']}"
        )
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
