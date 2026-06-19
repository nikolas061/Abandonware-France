#!/usr/bin/env python3
"""Compare LLSE 2730 marker guard replay impact across trace heights."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

from lolg_tex_large_body_control_grammar_probe import int_value, write_csv
from lolg_tex_large_llse_higharg2_refinement_probe import float_text, relative_href
from lolg_tex_large_llse_marker_field_semantics_probe import (
    DEFAULT_FIELD_PROFILE_SUMMARY,
    DEFAULT_OUTPUT as _FIELD_SEMANTICS_OUTPUT,
    DEFAULT_PAIR_LENGTH_SUMMARY,
    build_variants,
    evaluate_variant,
    load_body,
    read_csv,
    read_summary,
)
from lolg_tex_large_llse_marker_field_state_probe import DEFAULT_OUTPUT as _FIELD_STATE_OUTPUT
from lolg_tex_large_llse_marker_semantics_probe import (
    DEFAULT_HIGHARG2_SUMMARY,
    DEFAULT_MIX_ENTRY_INDEX,
    DEFAULT_SEGMENTS,
    TARGET_CONTROL_PATH,
)


DEFAULT_OUTPUT = Path("output/tex_large_llse_marker_guard_replay_impact_probe")
DEFAULT_FIELD_SEMANTICS_SUMMARY = _FIELD_SEMANTICS_OUTPUT / "summary.csv"
DEFAULT_FIELD_STATE_SUMMARY = _FIELD_STATE_OUTPUT / "summary.csv"

SUMMARY_FIELDNAMES = [
    "scope",
    "segment_rows",
    "height_rows",
    "candidate_action",
    "height_list",
    "score_512_delta",
    "score_1024_delta",
    "score_2048_delta",
    "candidate_512_actions",
    "candidate_1024_actions",
    "candidate_2048_actions",
    "max_diff_ratio",
    "issue_rows",
    "replay_impact_verdict",
    "next_action",
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


def parse_heights(value: str) -> list[int]:
    heights = []
    for item in value.split(","):
        item = item.strip()
        if item:
            heights.append(int(item, 0))
    return heights or [512, 1024, 2048]


def choose_variant(variants, action: str):
    selected = next((variant for variant in variants if variant.action == action), None)
    if selected is not None:
        return selected
    return next((variant for variant in variants if variant.action == "baseline"), variants[0])


def diff_pixels(left: bytes, right: bytes) -> int:
    return sum(1 for a, b in zip(left, right) if a != b)


def row_from_evaluation(
    row: dict[str, str],
    pixels: bytes,
    baseline_score: float,
    baseline_pixels: bytes,
) -> dict[str, str]:
    changed = diff_pixels(pixels, baseline_pixels) if baseline_pixels and pixels else 0
    total = max(1, min(len(pixels), len(baseline_pixels)) if baseline_pixels and pixels else len(pixels))
    return {
        "rank": "",
        "segment_id": row.get("segment_id", ""),
        "height": row.get("height", ""),
        "action": row.get("action", ""),
        "variant_id": row.get("variant_id", ""),
        "score": row.get("score", ""),
        "delta_vs_height_baseline": f"{float_text(row.get('score')) - baseline_score:.4f}",
        "visible_pixels": row.get("visible_pixels", ""),
        "filled_ratio": row.get("filled_ratio", ""),
        "unique_colors": row.get("unique_colors", ""),
        "emitted": row.get("emitted", ""),
        "final_x": row.get("final_x", ""),
        "final_y": row.get("final_y", ""),
        "target_seen": row.get("target_seen", ""),
        "actions_applied": row.get("actions_applied", ""),
        "cmd20_higharg2_applied": row.get("cmd20_higharg2_applied", ""),
        "marker_pair_seen": row.get("marker_pair_seen", ""),
        "diff_pixels": str(changed),
        "diff_ratio": f"{changed / max(1, total):.6f}",
        "issues": row.get("issues", ""),
    }


def summary_row(rows: list[dict[str, str]], candidate_action: str, heights: list[int]) -> dict[str, str]:
    issue_rows = sum(1 for row in rows if row.get("issues"))
    candidate_rows = [row for row in rows if row.get("action") == candidate_action]
    deltas = {int_value(row, "height"): row.get("delta_vs_height_baseline", "") for row in candidate_rows}
    actions = {int_value(row, "height"): row.get("actions_applied", "") for row in candidate_rows}
    max_diff_ratio = max((float_text(row.get("diff_ratio")) for row in candidate_rows), default=0.0)
    height_set = sorted({int_value(row, "height") for row in rows if row.get("height")})
    if issue_rows:
        verdict = "llse_marker_guard_replay_impact_issues"
        next_action = "fix LLSE marker guard replay impact inputs"
    elif candidate_rows and all(float_text(row.get("delta_vs_height_baseline")) <= 0 for row in candidate_rows):
        verdict = "llse_marker_guard_replay_impact_stable"
        next_action = (
            "inspect LLSE static guard replay visuals and remaining command grammar before decoder promotion; "
            f"candidate {candidate_action}"
        )
    elif candidate_rows:
        verdict = "llse_marker_guard_replay_impact_mixed"
        next_action = (
            "split LLSE static guard replay by height/context before decoder promotion; "
            f"candidate {candidate_action}"
        )
    else:
        verdict = "llse_marker_guard_replay_impact_no_rows"
        next_action = "review LLSE marker guard replay impact inputs"
    return {
        "scope": "total",
        "segment_rows": str(len({row.get("segment_id", "") for row in rows if row.get("segment_id")})),
        "height_rows": str(len(height_set)),
        "candidate_action": candidate_action,
        "height_list": "|".join(str(height) for height in heights),
        "score_512_delta": deltas.get(512, ""),
        "score_1024_delta": deltas.get(1024, ""),
        "score_2048_delta": deltas.get(2048, ""),
        "candidate_512_actions": actions.get(512, ""),
        "candidate_1024_actions": actions.get(1024, ""),
        "candidate_2048_actions": actions.get(2048, ""),
        "max_diff_ratio": f"{max_diff_ratio:.6f}",
        "issue_rows": str(issue_rows),
        "replay_impact_verdict": verdict,
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


def build_html(summary: dict[str, str], rows: list[dict[str, str]], output_dir: Path, title: str) -> str:
    payload = {"summary": summary, "rows": rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f"<a href=\"{html.escape(relative_href(path, output_dir))}\">{html.escape(label)}</a>"
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
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
  <div class="muted">Replay impact for the LLSE 2730 static marker guard.</div>
  <p>{links}</p>
</header>
<main>
  <section class="grid">
    <div class="stat"><div class="label">Candidate</div><div class="value">{html.escape(summary['candidate_action'])}</div></div>
    <div class="stat"><div class="label">512 Delta</div><div class="value warn">{html.escape(summary['score_512_delta'])}</div></div>
    <div class="stat"><div class="label">2048 Delta</div><div class="value warn">{html.escape(summary['score_2048_delta'])}</div></div>
    <div class="stat"><div class="label">Issues</div><div class="value ok">{html.escape(summary['issue_rows'])}</div></div>
  </section>
  <section class="panel"><h2>Summary</h2>{render_table([summary], SUMMARY_FIELDNAMES)}</section>
  <section class="panel"><h2>Rows</h2>{render_table(rows, ROW_FIELDNAMES)}</section>
</main>
<script type="application/json" id="llse-marker-guard-replay-impact-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> tuple[dict[str, str], list[dict[str, str]]]:
    args.output.mkdir(parents=True, exist_ok=True)
    higharg2_summary = read_summary(args.higharg2_summary)
    pair_summary = read_summary(args.pair_length_summary)
    field_summary = read_summary(args.field_profile_summary)
    semantics_summary = read_summary(args.field_semantics_summary)
    state_summary = read_summary(args.field_state_summary)
    candidate_action = args.action or state_summary.get("candidate_action") or semantics_summary.get("best_action", "")
    variants = build_variants(higharg2_summary, pair_summary, field_summary)
    baseline_variant = choose_variant(variants, "baseline")
    candidate_variant = choose_variant(variants, candidate_action)
    segment_rows = [row for row in read_csv(args.segments) if row.get("control_path") == TARGET_CONTROL_PATH]
    payload_cache: dict[Path, bytes] = {}
    rows: list[dict[str, str]] = []
    for source in segment_rows:
        body, issues = load_body(source, payload_cache, args.mix_entry_index)
        for height in args.heights:
            baseline_row, baseline_pixels = evaluate_variant(
                source, body, issues, baseline_variant, args.width, height, args.low, args.high, 0.0
            )
            baseline_row["height"] = str(height)
            baseline_score = float_text(baseline_row.get("score"))
            rows.append(row_from_evaluation(baseline_row, baseline_pixels, baseline_score, baseline_pixels))
            candidate_row, candidate_pixels = evaluate_variant(
                source, body, issues, candidate_variant, args.width, height, args.low, args.high, baseline_score
            )
            candidate_row["height"] = str(height)
            rows.append(row_from_evaluation(candidate_row, candidate_pixels, baseline_score, baseline_pixels))
    for rank, row in enumerate(rows, 1):
        row["rank"] = str(rank)
    summary = summary_row(rows, candidate_variant.action, args.heights)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "rows.csv", ROW_FIELDNAMES, rows)
    (args.output / "index.html").write_text(build_html(summary, rows, args.output, args.title), encoding="utf-8")
    return summary, rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare LLSE 2730 marker guard replay impact.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--segments", type=Path, default=DEFAULT_SEGMENTS)
    parser.add_argument("--higharg2-summary", type=Path, default=DEFAULT_HIGHARG2_SUMMARY)
    parser.add_argument("--pair-length-summary", type=Path, default=DEFAULT_PAIR_LENGTH_SUMMARY)
    parser.add_argument("--field-profile-summary", type=Path, default=DEFAULT_FIELD_PROFILE_SUMMARY)
    parser.add_argument("--field-semantics-summary", type=Path, default=DEFAULT_FIELD_SEMANTICS_SUMMARY)
    parser.add_argument("--field-state-summary", type=Path, default=DEFAULT_FIELD_STATE_SUMMARY)
    parser.add_argument("--mix-entry-index", type=int, default=DEFAULT_MIX_ENTRY_INDEX)
    parser.add_argument("--width", type=int, default=64)
    parser.add_argument("--heights", type=parse_heights, default=parse_heights("512,1024,2048"))
    parser.add_argument("--low", type=lambda value: int(value, 0), default=0x30)
    parser.add_argument("--high", type=lambda value: int(value, 0), default=0xBF)
    parser.add_argument("--action", default="")
    parser.add_argument("--title", default="Lands of Lore II .tex LLSE Marker Guard Replay Impact Probe")
    args = parser.parse_args()

    summary, _rows = write_report(args)
    print(f"Segments: {summary['segment_rows']}")
    print(f"Candidate action: {summary['candidate_action']}")
    print(f"512 delta: {summary['score_512_delta']}")
    print(f"1024 delta: {summary['score_1024_delta']}")
    print(f"2048 delta: {summary['score_2048_delta']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"Replay impact verdict: {summary['replay_impact_verdict']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
