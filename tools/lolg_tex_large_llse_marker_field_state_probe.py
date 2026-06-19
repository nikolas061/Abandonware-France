#!/usr/bin/env python3
"""Trace cursor state around LLSE 2730 marker-field hypotheses."""

from __future__ import annotations

import argparse
import html
import json
from collections import Counter
from pathlib import Path

from lolg_tex_large_body_control_grammar_probe import int_value, write_csv
from lolg_tex_large_llse_higharg2_refinement_probe import (
    advance,
    apply_x_policy,
    float_text,
    is_known_marker_pair,
    marker_payload_start,
    marker_symmetric_header,
    relative_href,
    signed_byte,
)
from lolg_tex_large_llse_marker_field_semantics_probe import (
    DEFAULT_FIELD_PROFILE_SUMMARY,
    DEFAULT_OUTPUT as _FIELD_SEMANTICS_OUTPUT,
    DEFAULT_PAIR_LENGTH_SUMMARY,
    apply_field_action,
    build_variants,
    load_body,
    read_summary,
    skip_total,
)
from lolg_tex_large_llse_marker_semantics_probe import (
    DEFAULT_HIGHARG2_SUMMARY,
    DEFAULT_MIX_ENTRY_INDEX,
    DEFAULT_SEGMENTS,
    TARGET_CONTROL_PATH,
    read_csv,
)


DEFAULT_OUTPUT = Path("output/tex_large_llse_marker_field_state_probe")
DEFAULT_FIELD_SEMANTICS_SUMMARY = _FIELD_SEMANTICS_OUTPUT / "summary.csv"

SUMMARY_FIELDNAMES = [
    "scope",
    "segment_rows",
    "event_rows",
    "sample_rows",
    "candidate_action",
    "candidate_variant",
    "candidate_score",
    "candidate_delta",
    "target_pair",
    "target_record_len",
    "actions_applied",
    "tuple2000_seen",
    "f1_mod4_zero",
    "f1_mod4_zero_ratio",
    "x_delta_zero",
    "x_delta_zero_ratio",
    "x_delta_abs_le4",
    "x_delta_abs_le4_ratio",
    "y_delta_zero",
    "y_delta_zero_ratio",
    "y_delta_abs_le4",
    "y_delta_abs_le4_ratio",
    "y_forward",
    "y_backward",
    "y_same",
    "candidate_y_min",
    "candidate_y_max",
    "f0_zero",
    "f0_low",
    "f0_high",
    "final_x",
    "final_y",
    "emitted",
    "issue_rows",
    "state_verdict",
    "next_action",
]

EVENT_FIELDNAMES = [
    "rank",
    "event_index",
    "segment_id",
    "archive",
    "archive_tag",
    "pcx_name",
    "record_offset",
    "record_hex",
    "fields_hex",
    "field0",
    "field1",
    "field2",
    "field3",
    "field4",
    "f1_mod4",
    "f1_div4",
    "tuple2000",
    "applied",
    "x_before",
    "y_before",
    "x_after",
    "y_after",
    "x_delta",
    "x_delta_abs",
    "y_delta",
    "y_delta_abs",
    "before4_hex",
    "after4_hex",
    "next_byte",
]

BUCKET_FIELDNAMES = [
    "rank",
    "bucket",
    "value",
    "count",
    "ratio",
]


def ratio(count: int, total: int) -> str:
    return f"{count / max(1, total):.6f}"


def choose_variant(
    higharg2_summary: dict[str, str],
    pair_summary: dict[str, str],
    field_summary: dict[str, str],
    action: str,
):
    variants = build_variants(higharg2_summary, pair_summary, field_summary)
    selected = next((variant for variant in variants if variant.action == action), None)
    if selected is not None:
        return selected
    return next((variant for variant in variants if variant.action == "baseline"), variants[0])


def context_hex(body: bytes, start: int, total: int) -> tuple[str, str, str]:
    before = body[max(0, start - 4) : start].hex()
    end = min(len(body), start + total)
    after = body[end : min(len(body), end + 4)].hex()
    next_byte = f"{body[end]:02x}" if end < len(body) else ""
    return before, after, next_byte


def add_bucket(counters: dict[str, Counter[str]], bucket: str, value: str) -> None:
    counters.setdefault(bucket, Counter())[value] += 1


def trace_body(
    source: dict[str, str],
    body: bytes,
    body_issues: list[str],
    variant,
    width: int,
    height: int,
    low: int,
    high: int,
) -> tuple[list[dict[str, str]], dict[str, int], dict[str, Counter[str]], list[str]]:
    if body_issues:
        return [], {}, {}, body_issues
    payload_base = marker_payload_start(body)
    payload = body[payload_base:]
    x = y = 0
    pos = 0
    emitted = 0
    event_index = 0
    events: list[dict[str, str]] = []
    counters: dict[str, Counter[str]] = {}
    stats = {
        "actions_applied": 0,
        "tuple2000_seen": 0,
        "target_seen": 0,
        "final_x": 0,
        "final_y": 0,
        "emitted": 0,
    }
    while pos < len(payload) and y < height:
        start = pos
        byte = payload[pos]
        pos += 1
        if marker_symmetric_header(payload, byte, pos):
            pos = min(len(payload), start + 2)
            continue
        if pos < len(payload) and is_known_marker_pair(byte, payload[pos]):
            pair = f"{byte:02x}{payload[pos]:02x}"
            total = skip_total(variant.policy_for_pair(pair))
            fields = payload[start + 2 : min(len(payload), start + total)]
            pos = min(len(payload), start + total)
            if pair == variant.target_pair and total == variant.target_record_len:
                stats["target_seen"] += 1
                if len(fields) >= 5:
                    event_index += 1
                    f0, f1, f2, f3, f4 = fields[:5]
                    before_x, before_y = x, y
                    action_stats = {"actions_applied": 0, "tuple2000_seen": 0}
                    after_x, after_y = apply_field_action(
                        x,
                        y,
                        width,
                        height,
                        fields,
                        variant.action,
                        action_stats,
                    )
                    stats["actions_applied"] += action_stats["actions_applied"]
                    stats["tuple2000_seen"] += action_stats["tuple2000_seen"]
                    applied = action_stats["actions_applied"] > 0
                    dx = after_x - before_x
                    dy = after_y - before_y
                    absolute_start = payload_base + start
                    before4, after4, next_byte = context_hex(body, absolute_start, total)
                    tuple2000 = f2 == 0x20 and f3 == 0
                    add_bucket(counters, "f1_mod4", str(f1 % 4))
                    add_bucket(counters, "f0", f"{f0:02x}")
                    add_bucket(counters, "field2", f"{f2:02x}")
                    add_bucket(counters, "field3", f"{f3:02x}")
                    add_bucket(counters, "applied", "yes" if applied else "no")
                    add_bucket(counters, "y_direction", "forward" if dy > 0 else "backward" if dy < 0 else "same")
                    add_bucket(counters, "x_delta_abs", "<=4" if abs(dx) <= 4 else ">4")
                    add_bucket(counters, "y_delta_abs", "<=4" if abs(dy) <= 4 else ">4")
                    events.append(
                        {
                            "rank": "",
                            "event_index": str(event_index),
                            "segment_id": source.get("segment_id", ""),
                            "archive": source.get("archive", ""),
                            "archive_tag": source.get("archive_tag", ""),
                            "pcx_name": source.get("pcx_name", ""),
                            "record_offset": str(absolute_start),
                            "record_hex": body[absolute_start : absolute_start + total].hex(),
                            "fields_hex": fields[:5].hex(),
                            "field0": f"{f0:02x}",
                            "field1": f"{f1:02x}",
                            "field2": f"{f2:02x}",
                            "field3": f"{f3:02x}",
                            "field4": f"{f4:02x}",
                            "f1_mod4": str(f1 % 4),
                            "f1_div4": str(f1 // 4),
                            "tuple2000": "yes" if tuple2000 else "no",
                            "applied": "yes" if applied else "no",
                            "x_before": str(before_x),
                            "y_before": str(before_y),
                            "x_after": str(after_x),
                            "y_after": str(after_y),
                            "x_delta": str(dx),
                            "x_delta_abs": str(abs(dx)),
                            "y_delta": str(dy),
                            "y_delta_abs": str(abs(dy)),
                            "before4_hex": before4,
                            "after4_hex": after4,
                            "next_byte": next_byte,
                        }
                    )
                    x, y = after_x, after_y
            continue
        if byte == 0x20:
            arg1 = payload[pos] if pos < len(payload) else 0
            arg2 = payload[pos + 1] if pos + 1 < len(payload) else 0
            arg3 = payload[pos + 2] if pos + 2 < len(payload) else 0
            if (arg1, arg2, arg3) == (0, 0, 0):
                if variant.zero_policy == "line":
                    x = 0
                    y = min(height, y + 1)
                    pos = min(len(payload), pos + variant.skip)
                    continue
                if variant.zero_policy == "skip":
                    pos = min(len(payload), pos + variant.skip)
                    continue
                continue
            if arg2 >= variant.threshold:
                dy = signed_byte(arg2)
                next_y = y + dy if variant.dy_policy == "add" else y - dy
                if 0 <= next_y < height:
                    x = apply_x_policy(x, width, arg1, variant.x_policy)
                    y = next_y
                    pos = min(len(payload), pos + variant.skip)
                    continue
            pos = min(len(payload), pos + variant.skip)
            continue
        if low <= byte <= high:
            x, y = advance(x, y, width, 1)
            emitted += 1
    stats["final_x"] = x
    stats["final_y"] = y
    stats["emitted"] = emitted
    return events, stats, counters, []


def bucket_rows(counters: dict[str, Counter[str]], event_count: int) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for bucket, counter in sorted(counters.items()):
        for value, count in counter.most_common(32):
            rows.append(
                {
                    "rank": "",
                    "bucket": bucket,
                    "value": value,
                    "count": str(count),
                    "ratio": ratio(count, event_count),
                }
            )
    for rank, row in enumerate(rows, 1):
        row["rank"] = str(rank)
    return rows


def summary_row(
    events: list[dict[str, str]],
    stats: dict[str, int],
    semantics_summary: dict[str, str],
    variant,
    issue_rows: int,
    sample_limit: int,
    segment_count: int,
) -> dict[str, str]:
    total = len(events)
    f1_mod4_zero = sum(1 for row in events if row.get("f1_mod4") == "0")
    x_delta_zero = sum(1 for row in events if int_value(row, "x_delta_abs") == 0)
    y_delta_zero = sum(1 for row in events if int_value(row, "y_delta_abs") == 0)
    x_delta_abs_le4 = sum(1 for row in events if int_value(row, "x_delta_abs") <= 4)
    y_delta_abs_le4 = sum(1 for row in events if int_value(row, "y_delta_abs") <= 4)
    y_forward = sum(1 for row in events if int_value(row, "y_delta") > 0)
    y_backward = sum(1 for row in events if int_value(row, "y_delta") < 0)
    y_same = total - y_forward - y_backward
    y_values = [int_value(row, "y_after") for row in events]
    f0_values = [int(row.get("field0", "0"), 16) for row in events]
    best_delta = semantics_summary.get("best_delta_vs_pair", "")
    if issue_rows:
        verdict = "llse_marker_field_state_probe_issues"
        next_action = "fix LLSE marker field state probe inputs"
    elif total and f1_mod4_zero / max(1, total) >= 0.5 and float_text(best_delta) < 0:
        verdict = "llse_marker_field_state_guard_signal"
        if "_yforward" in variant.action:
            next_action = (
                "isolate LLSE 2730 yforward field/context guard "
                f"for {stats.get('actions_applied', 0)} events before decoder promotion; "
                f"candidate {variant.action}"
            )
        else:
            next_action = (
                "split LLSE 2730 field semantics by f1 mod4 and cursor jump direction; "
                f"candidate {variant.action}"
            )
    elif total:
        verdict = "llse_marker_field_state_weak_signal"
        next_action = (
            "derive alternate LLSE 2730 state fields; current candidate "
            f"{variant.action} has weak cursor correlation"
        )
    else:
        verdict = "llse_marker_field_state_no_events"
        next_action = "review LLSE marker field state probe inputs"
    return {
        "scope": "total",
        "segment_rows": str(segment_count),
        "event_rows": str(total),
        "sample_rows": str(min(sample_limit, total)),
        "candidate_action": variant.action,
        "candidate_variant": semantics_summary.get("best_variant", ""),
        "candidate_score": semantics_summary.get("best_score", ""),
        "candidate_delta": best_delta,
        "target_pair": variant.target_pair,
        "target_record_len": str(variant.target_record_len),
        "actions_applied": str(stats.get("actions_applied", 0)),
        "tuple2000_seen": str(stats.get("tuple2000_seen", 0)),
        "f1_mod4_zero": str(f1_mod4_zero),
        "f1_mod4_zero_ratio": ratio(f1_mod4_zero, total),
        "x_delta_zero": str(x_delta_zero),
        "x_delta_zero_ratio": ratio(x_delta_zero, total),
        "x_delta_abs_le4": str(x_delta_abs_le4),
        "x_delta_abs_le4_ratio": ratio(x_delta_abs_le4, total),
        "y_delta_zero": str(y_delta_zero),
        "y_delta_zero_ratio": ratio(y_delta_zero, total),
        "y_delta_abs_le4": str(y_delta_abs_le4),
        "y_delta_abs_le4_ratio": ratio(y_delta_abs_le4, total),
        "y_forward": str(y_forward),
        "y_backward": str(y_backward),
        "y_same": str(y_same),
        "candidate_y_min": str(min(y_values)) if y_values else "",
        "candidate_y_max": str(max(y_values)) if y_values else "",
        "f0_zero": str(sum(1 for value in f0_values if value == 0)),
        "f0_low": str(sum(1 for value in f0_values if value < 0x30)),
        "f0_high": str(sum(1 for value in f0_values if value >= 0xC0)),
        "final_x": str(stats.get("final_x", "")),
        "final_y": str(stats.get("final_y", "")),
        "emitted": str(stats.get("emitted", "")),
        "issue_rows": str(issue_rows),
        "state_verdict": verdict,
        "next_action": next_action,
    }


def render_table(rows: list[dict[str, str]], fieldnames: list[str]) -> str:
    if not rows:
        return "<p class=\"muted\">No rows.</p>"
    head = "".join(f"<th>{html.escape(field)}</th>" for field in fieldnames)
    body = "\n".join(
        "<tr>"
        + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fieldnames)
        + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    events: list[dict[str, str]],
    buckets: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "events": events, "buckets": buckets}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f"<a href=\"{html.escape(relative_href(path, output_dir))}\">{html.escape(label)}</a>"
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("events.csv", output_dir / "events.csv"),
            ("buckets.csv", output_dir / "buckets.csv"),
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
  <div class="muted">Cursor-state trace for LLSE 2730 marker field hypotheses.</div>
  <p>{links}</p>
</header>
<main>
  <section class="grid">
    <div class="stat"><div class="label">Events</div><div class="value">{html.escape(summary['event_rows'])}</div></div>
    <div class="stat"><div class="label">Action</div><div class="value">{html.escape(summary['candidate_action'])}</div></div>
    <div class="stat"><div class="label">f1 mod4=0</div><div class="value warn">{html.escape(summary['f1_mod4_zero_ratio'])}</div></div>
    <div class="stat"><div class="label">Issues</div><div class="value ok">{html.escape(summary['issue_rows'])}</div></div>
  </section>
  <section class="panel"><h2>Summary</h2>{render_table([summary], SUMMARY_FIELDNAMES)}</section>
  <section class="panel"><h2>Buckets</h2>{render_table(buckets, BUCKET_FIELDNAMES)}</section>
  <section class="panel"><h2>Events</h2>{render_table(events, EVENT_FIELDNAMES)}</section>
</main>
<script type="application/json" id="llse-marker-field-state-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    args.output.mkdir(parents=True, exist_ok=True)
    higharg2_summary = read_summary(args.higharg2_summary)
    pair_summary = read_summary(args.pair_length_summary)
    field_summary = read_summary(args.field_profile_summary)
    semantics_summary = read_summary(args.field_semantics_summary)
    action = args.action if args.action != "best" else semantics_summary.get("best_action", "baseline")
    variant = choose_variant(higharg2_summary, pair_summary, field_summary, action)
    segment_rows = [row for row in read_csv(args.segments) if row.get("control_path") == TARGET_CONTROL_PATH]
    payload_cache: dict[Path, bytes] = {}
    all_events: list[dict[str, str]] = []
    merged_stats: Counter[str] = Counter()
    merged_counters: dict[str, Counter[str]] = {}
    issue_rows = 0
    for source in segment_rows:
        body, issues = load_body(source, payload_cache, args.mix_entry_index)
        events, stats, counters, trace_issues = trace_body(
            source,
            body,
            issues,
            variant,
            args.width,
            args.height,
            args.low,
            args.high,
        )
        if trace_issues:
            issue_rows += 1
        all_events.extend(events)
        merged_stats.update(stats)
        for bucket, counter in counters.items():
            merged_counters.setdefault(bucket, Counter()).update(counter)
    for rank, row in enumerate(all_events, 1):
        row["rank"] = str(rank)
    buckets = bucket_rows(merged_counters, len(all_events))
    summary = summary_row(
        all_events,
        dict(merged_stats),
        semantics_summary,
        variant,
        issue_rows,
        args.sample_limit,
        len(segment_rows),
    )
    sampled_events = all_events[: args.sample_limit]
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "events.csv", EVENT_FIELDNAMES, sampled_events)
    write_csv(args.output / "buckets.csv", BUCKET_FIELDNAMES, buckets)
    (args.output / "index.html").write_text(
        build_html(summary, sampled_events, buckets, args.output, args.title),
        encoding="utf-8",
    )
    return summary, sampled_events, buckets


def main() -> None:
    parser = argparse.ArgumentParser(description="Trace LLSE 2730 marker-field cursor states.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--segments", type=Path, default=DEFAULT_SEGMENTS)
    parser.add_argument("--higharg2-summary", type=Path, default=DEFAULT_HIGHARG2_SUMMARY)
    parser.add_argument("--pair-length-summary", type=Path, default=DEFAULT_PAIR_LENGTH_SUMMARY)
    parser.add_argument("--field-profile-summary", type=Path, default=DEFAULT_FIELD_PROFILE_SUMMARY)
    parser.add_argument("--field-semantics-summary", type=Path, default=DEFAULT_FIELD_SEMANTICS_SUMMARY)
    parser.add_argument("--mix-entry-index", type=int, default=DEFAULT_MIX_ENTRY_INDEX)
    parser.add_argument("--width", type=int, default=64)
    parser.add_argument("--height", type=int, default=512)
    parser.add_argument("--low", type=lambda value: int(value, 0), default=0x30)
    parser.add_argument("--high", type=lambda value: int(value, 0), default=0xBF)
    parser.add_argument("--action", default="best")
    parser.add_argument("--sample-limit", type=int, default=240)
    parser.add_argument("--title", default="Lands of Lore II .tex LLSE Marker Field State Probe")
    args = parser.parse_args()

    summary, _events, _buckets = write_report(args)
    print(f"Events: {summary['event_rows']}")
    print(f"Candidate action: {summary['candidate_action']}")
    print(f"Candidate delta: {summary['candidate_delta']}")
    print(f"Actions applied: {summary['actions_applied']}/{summary['event_rows']}")
    print(f"f1 mod4 zero: {summary['f1_mod4_zero']} ({summary['f1_mod4_zero_ratio']})")
    print(f"x delta <=4: {summary['x_delta_abs_le4']} ({summary['x_delta_abs_le4_ratio']})")
    print(f"y delta <=4: {summary['y_delta_abs_le4']} ({summary['y_delta_abs_le4_ratio']})")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"State verdict: {summary['state_verdict']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
