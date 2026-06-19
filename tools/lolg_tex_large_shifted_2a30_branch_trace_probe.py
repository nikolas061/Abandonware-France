#!/usr/bin/env python3
"""Trace bounded 0x2a30 branch renderer candidates for command fingerprints."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_large_shifted_2a30_branch_bounded_family_probe import (
    catalog_payloads,
    float_text,
    int_text,
    key_for,
    read_csv,
    safe_name,
    write_csv,
)
from trace_te_stream import trace_payload


DEFAULT_OUTPUT = Path("output/tex_large_shifted_2a30_branch_trace_probe")
DEFAULT_BOUNDED_SUMMARY = Path("output/tex_large_shifted_2a30_branch_bounded_family_probe/summary.csv")
DEFAULT_BOUNDED_FAMILY = Path("output/tex_large_shifted_2a30_branch_bounded_family_probe/family.csv")
DEFAULT_BOUNDED_CANDIDATES = Path("output/tex_large_shifted_2a30_branch_bounded_family_probe/candidates.csv")
DEFAULT_CATALOG = Path("reports/te_resources.tsv")

SUMMARY_FIELDNAMES = [
    "scope",
    "bounded_family_rows",
    "bounded_candidate_rows",
    "trace_candidate_rows",
    "trace_action_rows",
    "trace_event_sample_rows",
    "issue_rows",
    "family_marker",
    "family_b3",
    "target_archive_tag",
    "target_pcx_name",
    "target_rank",
    "target_start",
    "target_mode",
    "target_score",
    "target_fingerprint",
    "target_events",
    "target_pixels",
    "target_cmd20",
    "target_op4",
    "target_control",
    "target_taken_commands",
    "target_command_density",
    "target_sig_skip",
    "target_sig_noop",
    "support_rank1_fingerprints",
    "support_rank1_taken_command_min",
    "support_rank1_taken_command_max",
    "support_rank1_cmd20_max",
    "support_rank1_op4_max",
    "target_fingerprint_supported_by_rank1",
    "visual_status",
    "next_action",
]

CANDIDATE_FIELDNAMES = [
    "rank",
    "archive_tag",
    "pcx_name",
    "is_target",
    "source",
    "start",
    "marker_extra",
    "mode",
    "width",
    "height",
    "score",
    "filled_ratio",
    "payload_bytes",
    "trace_bytes",
    "events",
    "pixels",
    "trace_fill_ratio",
    "cmd20",
    "op4",
    "control",
    "ignored_low",
    "ignored_high",
    "pixel",
    "taken_commands",
    "command_density",
    "cmd20_skip",
    "cmd20_sig_skip",
    "cmd20_sig_noop",
    "op4_small_skip",
    "op4_skip",
    "markerknown_skip",
    "first_pixel_pos",
    "first_cmd20_pos",
    "first_op4_pos",
    "first_control_pos",
    "final_x",
    "final_y",
    "fingerprint",
    "dominant_actions",
]

ACTION_FIELDNAMES = [
    "archive_tag",
    "pcx_name",
    "rank",
    "start",
    "mode",
    "kind",
    "action",
    "count",
]

EVENT_FIELDNAMES = [
    "archive_tag",
    "pcx_name",
    "rank",
    "start",
    "mode",
    "event_index",
    "stream_pos",
    "x",
    "y",
    "byte",
    "kind",
    "action",
    "skip",
    "arg1",
    "arg2",
    "arg3",
    "emit",
    "x_after",
    "y_after",
    "next8",
]


def hex_byte(value: object) -> str:
    if value is None:
        return ""
    return f"{int(value):02x}"


def fmt_ratio(numerator: int, denominator: int) -> str:
    return f"{numerator / max(1, denominator):.6f}"


def unique_text(values: list[str]) -> str:
    seen: set[str] = set()
    output = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            output.append(value)
    return "|".join(output)


def classify_fingerprint(counts: Counter[tuple[str, str]], kind_counts: Counter[str], taken_commands: int) -> str:
    events = max(1, sum(kind_counts.values()))
    op4 = kind_counts.get("op4", 0)
    cmd20 = kind_counts.get("cmd20", 0)
    sig_skip = counts.get(("cmd20", "sig_skip"), 0)
    sig_noop = counts.get(("cmd20", "sig_noop"), 0)
    if op4 / events >= 0.02:
        return "op4_heavy"
    if sig_skip or sig_noop:
        if taken_commands <= 4:
            return "cmd20_sig_sparse"
        return "cmd20_sig_mixed"
    if cmd20:
        return "cmd20_skip"
    if taken_commands:
        return "control_or_command_sparse"
    return "filter_like"


def first_pos(events: list[dict[str, object]], kind: str) -> str:
    for event in events:
        if event.get("kind") == kind:
            return str(event.get("stream_pos", ""))
    return ""


def dominant_actions(counts: Counter[tuple[str, str]], limit: int = 5) -> str:
    return "|".join(f"{kind}:{action}:{count}" for (kind, action), count in counts.most_common(limit))


def family_payload_rows(family_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [{"level": row.get("archive_tag", ""), "name": row.get("pcx_name", "")} for row in family_rows]


def trace_candidate(
    row: dict[str, str],
    payloads: dict[tuple[str, str], bytes],
    low: int,
    high: int,
    max_events: int,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], str | None]:
    key = key_for(row.get("archive_tag", ""), row.get("pcx_name", ""))
    payload = payloads.get(key, b"")
    start = int_text(row.get("start"), -1)
    width = int_text(row.get("width"))
    height = int_text(row.get("height"))
    mode = row.get("mode", "")
    if not payload:
        return {}, [], [], f"missing_payload:{key[0]}/{key[1]}"
    if start < 0 or start >= len(payload):
        return {}, [], [], f"invalid_start:{key[0]}/{key[1]}:{start}"
    if width <= 0 or height <= 0 or not mode:
        return {}, [], [], f"invalid_candidate:{key[0]}/{key[1]}:{start}:{mode}"

    traced_payload = payload[start:]
    events = list(trace_payload(traced_payload, width, height, mode, low, high, max_events))
    kind_counts: Counter[str] = Counter(str(event["kind"]) for event in events)
    action_counts: Counter[tuple[str, str]] = Counter(
        (str(event["kind"]), str(event["action"])) for event in events
    )
    pixels = sum(int(event["emit"]) for event in events)
    taken_commands = sum(
        1
        for event in events
        if event["kind"] in {"cmd20", "op4", "control"}
        and (int(event.get("skip") or 0) > 0 or str(event.get("action", "")).endswith("advance"))
    )
    last = events[-1] if events else {}
    fingerprint = classify_fingerprint(action_counts, kind_counts, taken_commands)
    candidate = {
        "rank": row.get("rank", ""),
        "archive_tag": row.get("archive_tag", ""),
        "pcx_name": row.get("pcx_name", ""),
        "is_target": row.get("is_target", ""),
        "source": row.get("source", ""),
        "start": row.get("start", ""),
        "marker_extra": row.get("marker_extra", ""),
        "mode": mode,
        "width": row.get("width", ""),
        "height": row.get("height", ""),
        "score": row.get("score", ""),
        "filled_ratio": row.get("filled_ratio", ""),
        "payload_bytes": str(len(payload)),
        "trace_bytes": str(len(traced_payload)),
        "events": str(len(events)),
        "pixels": str(pixels),
        "trace_fill_ratio": fmt_ratio(pixels, width * height),
        "cmd20": str(kind_counts.get("cmd20", 0)),
        "op4": str(kind_counts.get("op4", 0)),
        "control": str(kind_counts.get("control", 0)),
        "ignored_low": str(kind_counts.get("ignored_low", 0)),
        "ignored_high": str(kind_counts.get("ignored_high", 0)),
        "pixel": str(kind_counts.get("pixel", 0)),
        "taken_commands": str(taken_commands),
        "command_density": fmt_ratio(taken_commands, len(events)),
        "cmd20_skip": str(action_counts.get(("cmd20", "skip"), 0)),
        "cmd20_sig_skip": str(action_counts.get(("cmd20", "sig_skip"), 0)),
        "cmd20_sig_noop": str(action_counts.get(("cmd20", "sig_noop"), 0)),
        "op4_small_skip": str(action_counts.get(("op4", "small_skip"), 0)),
        "op4_skip": str(action_counts.get(("op4", "skip"), 0)),
        "markerknown_skip": str(action_counts.get(("control", "markerknown_skip"), 0)),
        "first_pixel_pos": first_pos(events, "pixel"),
        "first_cmd20_pos": first_pos(events, "cmd20"),
        "first_op4_pos": first_pos(events, "op4"),
        "first_control_pos": first_pos(events, "control"),
        "final_x": str(last.get("x_after", "")),
        "final_y": str(last.get("y_after", "")),
        "fingerprint": fingerprint,
        "dominant_actions": dominant_actions(action_counts),
    }
    action_rows = [
        {
            "archive_tag": row.get("archive_tag", ""),
            "pcx_name": row.get("pcx_name", ""),
            "rank": row.get("rank", ""),
            "start": row.get("start", ""),
            "mode": mode,
            "kind": kind,
            "action": action,
            "count": str(count),
        }
        for (kind, action), count in sorted(action_counts.items())
    ]
    event_rows = []
    for event in events:
        event_row = {
            "archive_tag": row.get("archive_tag", ""),
            "pcx_name": row.get("pcx_name", ""),
            "rank": row.get("rank", ""),
            "start": row.get("start", ""),
            "mode": mode,
            **event,
        }
        for field in ["byte", "arg1", "arg2", "arg3"]:
            event_row[field] = hex_byte(event_row[field])
        event_rows.append({field: str(event_row.get(field, "")) for field in EVENT_FIELDNAMES})
    return candidate, action_rows, event_rows, None


def build_summary(
    bounded_summary: dict[str, str],
    family_rows: list[dict[str, str]],
    trace_rows: list[dict[str, str]],
    action_rows: list[dict[str, str]],
    event_rows: list[dict[str, str]],
    issues: list[str],
) -> dict[str, str]:
    target_rows = [row for row in trace_rows if row.get("is_target") == "yes"]
    target_best = min(target_rows, key=lambda row: (int_text(row.get("rank")), float_text(row.get("score"))), default={})
    support_rank1 = [
        row for row in trace_rows if row.get("is_target") != "yes" and int_text(row.get("rank")) == 1
    ]
    support_fingerprints = [row.get("fingerprint", "") for row in support_rank1]
    supported = target_best.get("fingerprint", "") in set(support_fingerprints)
    if issues:
        visual_status = "blocked_trace_probe_issues"
        next_action = "fix shifted 0x2a30 branch trace probe inputs"
    elif not target_best:
        visual_status = "blocked_trace_no_target"
        next_action = "fix shifted 0x2a30 branch trace target selection"
    elif not supported:
        visual_status = "blocked_trace_fingerprint_not_supported"
        next_action = (
            "derive a pre-render branch selector for "
            f"{bounded_summary.get('family_marker', '')}/b3={bounded_summary.get('family_b3', '')}; "
            f"target rank{target_best.get('rank', '')} start{target_best.get('start', '')} "
            f"{target_best.get('mode', '')} fingerprint {target_best.get('fingerprint', '')} "
            f"is not in support rank1 fingerprints {unique_text(support_fingerprints)}"
        )
    else:
        visual_status = "blocked_trace_fingerprint_supported_but_visual_noisy"
        next_action = (
            "derive a stricter 0x2a30 branch command guard; "
            f"target fingerprint {target_best.get('fingerprint', '')} is supported but previews remain noisy"
        )
    return {
        "scope": "total",
        "bounded_family_rows": str(len(family_rows)),
        "bounded_candidate_rows": bounded_summary.get("candidate_rows", ""),
        "trace_candidate_rows": str(len(trace_rows)),
        "trace_action_rows": str(len(action_rows)),
        "trace_event_sample_rows": str(len(event_rows)),
        "issue_rows": str(len(issues)),
        "family_marker": bounded_summary.get("family_marker", ""),
        "family_b3": bounded_summary.get("family_b3", ""),
        "target_archive_tag": target_best.get("archive_tag", ""),
        "target_pcx_name": target_best.get("pcx_name", ""),
        "target_rank": target_best.get("rank", ""),
        "target_start": target_best.get("start", ""),
        "target_mode": target_best.get("mode", ""),
        "target_score": target_best.get("score", ""),
        "target_fingerprint": target_best.get("fingerprint", ""),
        "target_events": target_best.get("events", ""),
        "target_pixels": target_best.get("pixels", ""),
        "target_cmd20": target_best.get("cmd20", ""),
        "target_op4": target_best.get("op4", ""),
        "target_control": target_best.get("control", ""),
        "target_taken_commands": target_best.get("taken_commands", ""),
        "target_command_density": target_best.get("command_density", ""),
        "target_sig_skip": target_best.get("cmd20_sig_skip", ""),
        "target_sig_noop": target_best.get("cmd20_sig_noop", ""),
        "support_rank1_fingerprints": unique_text(support_fingerprints),
        "support_rank1_taken_command_min": str(
            min((int_text(row.get("taken_commands")) for row in support_rank1), default=0)
        ),
        "support_rank1_taken_command_max": str(
            max((int_text(row.get("taken_commands")) for row in support_rank1), default=0)
        ),
        "support_rank1_cmd20_max": str(max((int_text(row.get("cmd20")) for row in support_rank1), default=0)),
        "support_rank1_op4_max": str(max((int_text(row.get("op4")) for row in support_rank1), default=0)),
        "target_fingerprint_supported_by_rank1": "yes" if supported else "no",
        "visual_status": visual_status,
        "next_action": next_action,
    }


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    path = Path(path_text)
    try:
        relative = path.relative_to(base_dir)
    except ValueError:
        relative = Path(os.path.relpath(path, base_dir))
    return relative.as_posix()


def render_table(rows: list[dict[str, str]], columns: list[str]) -> str:
    head = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    body = []
    for row in rows:
        cells = "".join(f"<td>{html.escape(row.get(column, ''))}</td>" for column in columns)
        body.append(f"<tr>{cells}</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def build_html(
    summary: dict[str, str],
    trace_rows: list[dict[str, str]],
    action_rows: list[dict[str, str]],
    issues: list[str],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "candidates": trace_rows, "actions": action_rows, "issues": issues}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("candidates.csv", output_dir / "candidates.csv"),
            ("actions.csv", output_dir / "actions.csv"),
            ("events.csv", output_dir / "events.csv"),
        )
    )
    issue_html = ""
    if issues:
        issue_html = "<h2>Issues</h2><ul>" + "".join(f"<li>{html.escape(issue)}</li>" for issue in issues) + "</ul>"
    top_rows = [row for row in trace_rows if row.get("rank") == "1"]
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root {{ color-scheme: dark; --bg: #101214; --panel: #171b1f; --line: #2b3339; --text: #edf2f4; --muted: #aab5ba; --accent: #7cc7ff; }}
body {{ margin: 0; background: var(--bg); color: var(--text); font: 14px/1.45 system-ui, -apple-system, Segoe UI, sans-serif; }}
main {{ max-width: 1500px; margin: 0 auto; padding: 28px; }}
h1 {{ font-size: 24px; margin: 0 0 8px; }}
h2 {{ font-size: 18px; margin: 26px 0 10px; }}
.muted {{ color: var(--muted); }}
a {{ color: var(--accent); text-decoration: none; margin-right: 10px; }}
table {{ width: 100%; border-collapse: collapse; background: var(--panel); border: 1px solid var(--line); margin-top: 10px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; font-size: 12px; }}
th {{ color: var(--muted); background: #20262b; }}
td {{ max-width: 520px; overflow-wrap: anywhere; }}
</style>
</head>
<body>
<main>
<h1>{html.escape(title)}</h1>
<p class="muted">Command-trace fingerprints for bounded 0x2a30 branch renderer candidates. This report is evidence only.</p>
<p>{links}</p>
<h2>Summary</h2>
{render_table([summary], SUMMARY_FIELDNAMES)}
{issue_html}
<h2>Rank 1 Fingerprints</h2>
{render_table(top_rows, CANDIDATE_FIELDNAMES)}
<h2>All Candidates</h2>
{render_table(trace_rows, CANDIDATE_FIELDNAMES)}
</main>
<script>const TEX_LARGE_SHIFTED_2A30_BRANCH_TRACE_PROBE = {data_json};</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> tuple[dict[str, str], list[str]]:
    args.output.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    bounded_summary = (read_csv(args.bounded_summary) or [{}])[0]
    family_rows = read_csv(args.bounded_family)
    candidate_rows = read_csv(args.bounded_candidates)
    if not bounded_summary:
        issues.append("missing_bounded_summary")
    if not family_rows:
        issues.append("missing_bounded_family_rows")
    if not candidate_rows:
        issues.append("missing_bounded_candidate_rows")
    payloads = catalog_payloads(args.catalog, family_payload_rows(family_rows))

    trace_rows: list[dict[str, str]] = []
    action_rows: list[dict[str, str]] = []
    event_rows: list[dict[str, str]] = []
    sampled_by_candidate: defaultdict[tuple[str, str, str, str], int] = defaultdict(int)
    for row in candidate_rows:
        trace_row, candidate_actions, candidate_events, issue = trace_candidate(
            row,
            payloads,
            args.low,
            args.high,
            args.max_events,
        )
        if issue:
            issues.append(issue)
            continue
        trace_rows.append(trace_row)
        action_rows.extend(candidate_actions)
        sample_key = (
            row.get("archive_tag", ""),
            row.get("pcx_name", ""),
            row.get("rank", ""),
            row.get("start", ""),
        )
        for event in candidate_events:
            if sampled_by_candidate[sample_key] >= args.event_sample_per_candidate:
                break
            event_rows.append(event)
            sampled_by_candidate[sample_key] += 1

    summary = build_summary(bounded_summary, family_rows, trace_rows, action_rows, event_rows, issues)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "candidates.csv", CANDIDATE_FIELDNAMES, trace_rows)
    write_csv(args.output / "actions.csv", ACTION_FIELDNAMES, action_rows)
    write_csv(args.output / "events.csv", EVENT_FIELDNAMES, event_rows)
    (args.output / "index.html").write_text(
        build_html(summary, trace_rows, action_rows, issues, args.output, args.title),
        encoding="utf-8",
    )
    return summary, issues


def main() -> None:
    parser = argparse.ArgumentParser(description="Trace shifted 0x2a30 branch bounded-family candidates.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--bounded-summary", type=Path, default=DEFAULT_BOUNDED_SUMMARY)
    parser.add_argument("--bounded-family", type=Path, default=DEFAULT_BOUNDED_FAMILY)
    parser.add_argument("--bounded-candidates", type=Path, default=DEFAULT_BOUNDED_CANDIDATES)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--low", type=lambda value: int(value, 0), default=0x30)
    parser.add_argument("--high", type=lambda value: int(value, 0), default=0xBF)
    parser.add_argument("--max-events", type=int, default=20000)
    parser.add_argument("--event-sample-per-candidate", type=int, default=128)
    parser.add_argument("--title", default="Lands of Lore II .tex Large Shifted 2a30 Branch Trace Probe")
    args = parser.parse_args()

    summary, issues = write_report(args)
    print(f"Trace candidates: {summary['trace_candidate_rows']}")
    print(f"Target fingerprint: {summary['target_fingerprint']}")
    print(f"Support fingerprints: {summary['support_rank1_fingerprints']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"Visual status: {summary['visual_status']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")
    if issues:
        print("Issues: " + "; ".join(issues))


if __name__ == "__main__":
    main()
