#!/usr/bin/env python3
"""Probe residual local actions after the shared 0x2700302b extended split."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
from pathlib import Path

import lolg_tex_large_shared_2700302b_op4_emitarg1_local_context_action_probe as action_probe
from score_te_raw_layouts import row_score


DEFAULT_OUTPUT = Path("output/tex_large_shared_2700302b_op4_emitarg1_extended_split_residual_probe")
DEFAULT_ACTION_SUMMARY = action_probe.DEFAULT_OUTPUT / "summary.csv"

LOW = 0x30
HIGH = 0xBF
ACTIONS = (
    "deny_reprocess",
    "deny_skip1",
    "deny_skip2",
    "deny_skip3",
    "deny_skip4",
    "deny_skip5",
    "deny_skip6",
    "emit_arg2_reprocess",
    "emit_arg2_skip1",
    "emit_arg3_reprocess",
)
FIELDS = ("prev2", "prev1", "arg1", "arg2", "arg3", "arg4")
PAIRS = (
    ("prev2", "prev1"),
    ("prev1", "arg1"),
    ("arg1", "arg2"),
    ("arg2", "arg3"),
    ("arg3", "arg4"),
    ("prev1", "arg2"),
    ("prev1", "arg3"),
    ("arg1", "arg3"),
)

SUMMARY_FIELDNAMES = [
    "scope",
    "segment_rows",
    "base_action_id",
    "base_avg_score",
    "base_max_score",
    "candidate_rows",
    "source_candidate_conditions",
    "candidate_limit",
    "min_count",
    "best_condition_id",
    "best_action",
    "best_avg_score",
    "best_max_score",
    "best_delta_vs_base",
    "best_max_delta_vs_base",
    "best_total_guard_events",
    "best_total_action_emit_events",
    "issue_rows",
    "residual_verdict",
    "next_action",
]

CANDIDATE_FIELDNAMES = [
    "rank",
    "condition_id",
    "condition_count",
    "action",
    "avg_score",
    "max_score",
    "min_score",
    "delta_vs_base",
    "max_delta_vs_base",
    "total_guard_events",
    "total_action_emit_events",
    "segment_scores",
    "verdict",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


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


def condition_name(key: tuple[object, ...]) -> str:
    if len(key) == 2:
        return f"{key[0]}_{int(key[1]):02x}"
    return f"{key[0]}_{int(key[1]):02x}_{int(key[2]):02x}"


def condition_match(key: tuple[object, ...], context: dict[str, int]) -> bool:
    if len(key) == 2:
        return context[str(key[0])] == int(key[1])
    field1, field2 = str(key[0]).split("_", 1)
    return context[field1] == int(key[1]) and context[field2] == int(key[2])


def existing_condition_keys() -> set[tuple[object, ...]]:
    keys: set[tuple[object, ...]] = set()
    for condition_id, _action in action_probe.EXTENDED_SPLIT_RULES:
        parts = condition_id.split("_")
        if len(parts) == 2:
            keys.add((parts[0], int(parts[1], 16)))
        elif len(parts) == 4:
            keys.add((f"{parts[0]}_{parts[1]}", int(parts[2], 16), int(parts[3], 16)))
    return keys


def base_select(condition_id: str, context: dict[str, int]) -> str:
    return action_probe.extended_split_action(condition_id, context)


def selected_action(
    condition_id: str,
    context: dict[str, int],
    extra: tuple[tuple[object, ...], str] | None,
) -> str:
    action = base_select(condition_id, context)
    if action:
        return action
    if extra and condition_match(extra[0], context):
        return extra[1]
    return ""


def load_segments(offset: int) -> list[tuple[str, bytes, int, int, list[str]]]:
    trace_rows = read_csv(action_probe.DEFAULT_TRACE_CANDIDATES)
    segment_rows = [
        row for row in read_csv(action_probe.DEFAULT_SEGMENTS) if row.get("control_path") == action_probe.TARGET_CONTROL_PATH
    ]
    payload_cache: dict[Path, bytes] = {}
    segments: list[tuple[str, bytes, int, int, list[str]]] = []
    for source in segment_rows:
        body, issues = action_probe.load_body(source, payload_cache, action_probe.DEFAULT_MIX_ENTRY_INDEX)
        width, height = action_probe.trace_dimensions(trace_rows, source.get("segment_id", ""), offset)
        payload = b"" if offset < 0 or offset >= len(body) else body[offset:]
        if not payload:
            issues = [*issues, "empty_payload"]
        segments.append((source.get("segment_id", ""), payload, width, height, issues))
    return segments


def apply_action(
    pixels: bytearray,
    width: int,
    height: int,
    x: int,
    y: int,
    pos: int,
    payload: bytes,
    action: str,
) -> tuple[int, int, int, int]:
    emitted = 0
    if action.startswith("deny_skip"):
        pos = min(len(payload), pos + int(action.replace("deny_skip", "")))
    elif action == "emit_arg2_reprocess" and pos + 1 < len(payload) and LOW <= payload[pos + 1] <= HIGH:
        action_probe.put_pixel(pixels, width, height, x, y, payload[pos + 1])
        x, y = action_probe.advance(x, y, width, 1)
        emitted = 1
    elif action == "emit_arg2_skip1" and pos + 1 < len(payload) and LOW <= payload[pos + 1] <= HIGH:
        action_probe.put_pixel(pixels, width, height, x, y, payload[pos + 1])
        x, y = action_probe.advance(x, y, width, 1)
        pos = min(len(payload), pos + 1)
        emitted = 1
    elif action == "emit_arg3_reprocess" and pos + 2 < len(payload) and LOW <= payload[pos + 2] <= HIGH:
        action_probe.put_pixel(pixels, width, height, x, y, payload[pos + 2])
        x, y = action_probe.advance(x, y, width, 1)
        emitted = 1
    return x, y, pos, emitted


def decode_residual(
    payload: bytes,
    width: int,
    height: int,
    base_condition_id: str,
    extra: tuple[tuple[object, ...], str] | None = None,
) -> tuple[bytes, dict[str, int]]:
    pixels = bytearray(width * height)
    x = y = pos = 0
    guard_events = 0
    action_emit_events = 0
    while pos < len(payload) and y < height:
        stream_pos = pos
        byte = payload[pos]
        pos += 1
        if pos < len(payload) and (byte, payload[pos]) in action_probe.KNOWN_MARKER_PAIRS:
            pos += 1
            continue
        if byte == 0x20:
            arg1 = payload[pos] if pos < len(payload) else None
            arg2 = payload[pos + 1] if pos + 1 < len(payload) else None
            arg3 = payload[pos + 2] if pos + 2 < len(payload) else None
            if action_probe.is_cmd20_signature(arg1, arg2, arg3):
                pos = min(len(payload), pos + 4)
            continue
        if action_probe.is_op4_candidate(byte):
            if pos < len(payload) and LOW <= payload[pos] <= HIGH:
                context = action_probe.event_context(payload, pos, stream_pos, byte)
                action = selected_action(base_condition_id, context, extra)
                if action:
                    guard_events += 1
                    x, y, pos, emitted = apply_action(pixels, width, height, x, y, pos, payload, action)
                    action_emit_events += emitted
                else:
                    action_probe.put_pixel(pixels, width, height, x, y, payload[pos])
                    x, y = action_probe.advance(x, y, width, 1)
            continue
        if LOW <= byte <= HIGH:
            action_probe.put_pixel(pixels, width, height, x, y, byte)
            x, y = action_probe.advance(x, y, width, 1)
    return bytes(pixels), {"guard_events": guard_events, "action_emit_events": action_emit_events}


def collect_candidate_conditions(
    segments: list[tuple[str, bytes, int, int, list[str]]],
    base_condition_id: str,
    min_count: int,
    candidate_limit: int,
) -> list[tuple[tuple[object, ...], int]]:
    frequencies: dict[tuple[object, ...], int] = {}
    for _segment_id, payload, width, height, issues in segments:
        if issues:
            continue
        x = y = pos = 0
        while pos < len(payload) and y < height:
            stream_pos = pos
            byte = payload[pos]
            pos += 1
            if pos < len(payload) and (byte, payload[pos]) in action_probe.KNOWN_MARKER_PAIRS:
                pos += 1
                continue
            if byte == 0x20:
                arg1 = payload[pos] if pos < len(payload) else None
                arg2 = payload[pos + 1] if pos + 1 < len(payload) else None
                arg3 = payload[pos + 2] if pos + 2 < len(payload) else None
                if action_probe.is_cmd20_signature(arg1, arg2, arg3):
                    pos = min(len(payload), pos + 4)
                continue
            if action_probe.is_op4_candidate(byte):
                if pos < len(payload) and LOW <= payload[pos] <= HIGH:
                    context = action_probe.event_context(payload, pos, stream_pos, byte)
                    if not base_select(base_condition_id, context):
                        for field in FIELDS:
                            value = context[field]
                            if value >= 0:
                                key = (field, value)
                                frequencies[key] = frequencies.get(key, 0) + 1
                        for field1, field2 in PAIRS:
                            value1 = context[field1]
                            value2 = context[field2]
                            if value1 >= 0 and value2 >= 0:
                                key = (f"{field1}_{field2}", value1, value2)
                                frequencies[key] = frequencies.get(key, 0) + 1
                continue
            if LOW <= byte <= HIGH:
                x, y = action_probe.advance(x, y, width, 1)
    existing = existing_condition_keys()
    candidates = [(key, count) for key, count in frequencies.items() if key not in existing and count >= min_count]
    candidates.sort(key=lambda item: (-item[1], item[0]))
    return candidates[:candidate_limit]


def candidate_rows(
    segments: list[tuple[str, bytes, int, int, list[str]]],
    base_condition_id: str,
    base_avg: float,
    base_max: float,
    conditions: list[tuple[tuple[object, ...], int]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for key, count in conditions:
        for action in ACTIONS:
            scores: list[float] = []
            guard_events = 0
            action_emit_events = 0
            for _segment_id, payload, width, height, issues in segments:
                if issues:
                    continue
                pixels, stats = decode_residual(payload, width, height, base_condition_id, (key, action))
                scores.append(row_score(pixels, width, height))
                guard_events += stats["guard_events"]
                action_emit_events += stats["action_emit_events"]
            if not scores:
                continue
            avg = sum(scores) / len(scores)
            max_score = max(scores)
            if avg >= base_avg - 0.00005:
                continue
            verdict = "candidate"
            if avg < base_avg - 0.05 and max_score <= base_max:
                verdict = "strong_residual_improvement"
            elif avg < base_avg - 0.01:
                verdict = "weak_residual_improvement"
            rows.append(
                {
                    "rank": "",
                    "condition_id": condition_name(key),
                    "condition_count": str(count),
                    "action": action,
                    "avg_score": f"{avg:.4f}",
                    "max_score": f"{max_score:.4f}",
                    "min_score": f"{min(scores):.4f}",
                    "delta_vs_base": f"{avg - base_avg:.4f}",
                    "max_delta_vs_base": f"{max_score - base_max:.4f}",
                    "total_guard_events": str(guard_events),
                    "total_action_emit_events": str(action_emit_events),
                    "segment_scores": "|".join(f"{score:.4f}" for score in scores),
                    "verdict": verdict,
                }
            )
    rows.sort(
        key=lambda row: (
            action_probe.float_text(row.get("avg_score")),
            action_probe.float_text(row.get("max_score")),
            row.get("condition_id", ""),
            row.get("action", ""),
        )
    )
    for rank, row in enumerate(rows, 1):
        row["rank"] = str(rank)
    return rows


def build_summary(
    *,
    action_summary: dict[str, str],
    segments: list[tuple[str, bytes, int, int, list[str]]],
    base_scores: list[float],
    candidates: list[dict[str, str]],
    source_candidate_conditions: int,
    candidate_limit: int,
    min_count: int,
) -> dict[str, str]:
    issue_rows = sum(1 for _segment_id, _payload, _width, _height, issues in segments if issues)
    best = candidates[0] if candidates else {}
    base_avg = sum(base_scores) / max(1, len(base_scores))
    base_max = max(base_scores) if base_scores else 0.0
    if issue_rows:
        verdict = "shared_2700302b_op4_extended_split_residual_probe_issues"
        next_action = "fix shared 0x2700302b op4 extended split residual probe inputs"
    elif not candidates:
        verdict = "shared_2700302b_op4_extended_split_residual_no_improvement"
        next_action = "switch shared 0x2700302b from local op4 sweep to reference-guided gap grammar"
    elif action_probe.float_text(best.get("delta_vs_base")) <= -0.05 and action_probe.float_text(best.get("max_delta_vs_base")) <= 0:
        verdict = "shared_2700302b_op4_extended_split_residual_improves"
        next_action = (
            "promote next shared 0x2700302b op4 residual rule candidate "
            f"{best.get('condition_id', '')}->{best.get('action', '')}; "
            f"avg delta {action_probe.float_text(best.get('delta_vs_base')):.4f}"
        )
    else:
        verdict = "shared_2700302b_op4_extended_split_residual_plateau"
        next_action = (
            "review shared 0x2700302b op4 residual plateau before adding narrow rules; "
            f"best candidate {best.get('condition_id', '')}->{best.get('action', '')} "
            f"avg delta {action_probe.float_text(best.get('delta_vs_base')):.4f}"
        )
    return {
        "scope": "total",
        "segment_rows": str(len(segments)),
        "base_action_id": action_summary.get("best_action_id", ""),
        "base_avg_score": f"{base_avg:.4f}",
        "base_max_score": f"{base_max:.4f}",
        "candidate_rows": str(len(candidates)),
        "source_candidate_conditions": str(source_candidate_conditions),
        "candidate_limit": str(candidate_limit),
        "min_count": str(min_count),
        "best_condition_id": best.get("condition_id", ""),
        "best_action": best.get("action", ""),
        "best_avg_score": best.get("avg_score", ""),
        "best_max_score": best.get("max_score", ""),
        "best_delta_vs_base": best.get("delta_vs_base", ""),
        "best_max_delta_vs_base": best.get("max_delta_vs_base", ""),
        "best_total_guard_events": best.get("total_guard_events", ""),
        "best_total_action_emit_events": best.get("total_action_emit_events", ""),
        "issue_rows": str(issue_rows),
        "residual_verdict": verdict,
        "next_action": next_action,
    }


def build_html(summary: dict[str, str], candidates: list[dict[str, str]], output_dir: Path, title: str) -> str:
    payload = {"summary": summary, "candidates": candidates}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    rows = "\n".join(
        "<tr>"
        f"<td>{html.escape(row.get('rank', ''))}</td>"
        f"<td>{html.escape(row.get('condition_id', ''))}</td>"
        f"<td>{html.escape(row.get('action', ''))}</td>"
        f"<td>{html.escape(row.get('avg_score', ''))}</td>"
        f"<td>{html.escape(row.get('delta_vs_base', ''))}</td>"
        f"<td>{html.escape(row.get('max_delta_vs_base', ''))}</td>"
        f"<td>{html.escape(row.get('verdict', ''))}</td>"
        "</tr>"
        for row in candidates[:100]
    )
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (("summary", output_dir / "summary.csv"), ("candidates", output_dir / "candidates.csv"))
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
  <div class="stat"><div class="label">Base</div><div class="value">{html.escape(summary['base_action_id'])}</div></div>
  <div class="stat"><div class="label">Base Avg</div><div class="value">{html.escape(summary['base_avg_score'])}</div></div>
  <div class="stat"><div class="label">Best Delta</div><div class="value">{html.escape(summary['best_delta_vs_base'])}</div></div>
  <div class="stat"><div class="label">Verdict</div><div class="value">{html.escape(summary['residual_verdict'])}</div></div>
</div>
<p>{html.escape(summary['next_action'])}</p>
<table>
<thead><tr><th>Rank</th><th>Condition</th><th>Action</th><th>Avg</th><th>Delta</th><th>Max Delta</th><th>Verdict</th></tr></thead>
<tbody>{rows}</tbody>
</table>
<script type="application/json" id="data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> tuple[dict[str, str], list[dict[str, str]]]:
    args.output.mkdir(parents=True, exist_ok=True)
    action_summary = action_probe.read_summary(args.action_summary)
    base_condition_id = action_summary.get("best_condition_id") or f"extended_split_greedy_{len(action_probe.EXTENDED_SPLIT_RULES)}"
    offset = action_probe.int_value(action_summary, "offset", 4)
    segments = load_segments(offset)
    base_scores: list[float] = []
    for _segment_id, payload, width, height, issues in segments:
        if issues:
            continue
        pixels, _stats = decode_residual(payload, width, height, base_condition_id)
        base_scores.append(row_score(pixels, width, height))
    conditions = collect_candidate_conditions(segments, base_condition_id, args.min_count, args.candidate_limit)
    candidates = candidate_rows(segments, base_condition_id, sum(base_scores) / max(1, len(base_scores)), max(base_scores), conditions)
    summary = build_summary(
        action_summary=action_summary,
        segments=segments,
        base_scores=base_scores,
        candidates=candidates,
        source_candidate_conditions=len(conditions),
        candidate_limit=args.candidate_limit,
        min_count=args.min_count,
    )
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "candidates.csv", CANDIDATE_FIELDNAMES, candidates)
    (args.output / "index.html").write_text(
        build_html(summary, candidates, args.output, args.title),
        encoding="utf-8",
    )
    return summary, candidates


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe residual actions after shared 0x2700302b extended split.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--action-summary", type=Path, default=DEFAULT_ACTION_SUMMARY)
    parser.add_argument("--candidate-limit", type=int, default=80)
    parser.add_argument("--min-count", type=int, default=3)
    parser.add_argument("--title", default="Lands of Lore II .tex Shared 0x2700302b OP4 Extended Split Residual Probe")
    args = parser.parse_args()
    summary, _candidates = write_report(args)
    print(f"Segments: {summary['segment_rows']}")
    print(f"Base action: {summary['base_action_id']}")
    print(f"Base avg score: {summary['base_avg_score']}")
    print(f"Candidate rows: {summary['candidate_rows']}")
    print(f"Best candidate: {summary['best_condition_id']} -> {summary['best_action']}")
    print(f"Best avg score: {summary['best_avg_score']}")
    print(f"Best delta vs base: {summary['best_delta_vs_base']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"Residual verdict: {summary['residual_verdict']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
